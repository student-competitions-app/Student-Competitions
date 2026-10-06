"""The migration history: correct from empty, idempotent, reversible, linear, drift-free and safe
to run twice at once.

See specs/003-database-questions/research.md#d5, #d6 and #d14. Every case runs on both engines,
except the concurrent upgrade, which relies on PostgreSQL's advisory lock by design.
"""

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401 — every table on SQLModel.metadata, for the drift check
from app.core.config import PROJECT_ROOT
from app.core.db import create_db_engine, utc_now
from app.core.migrations import (
    MIGRATION_LOCK_KEY,
    alembic_config,
    current_revision,
    head_revision,
)
from app.models import BootCounter, Question

APPLICATION_TABLES = {"questions", "boot_counter", "subjects"}


@pytest.fixture
def migration_engine(empty_database_url: str) -> Iterator[Engine]:
    engine = create_db_engine(empty_database_url)
    yield engine
    engine.dispose()


def run_alembic(
    monkeypatch: pytest.MonkeyPatch, database_url: str, action: str, target: str
) -> None:
    """`alembic upgrade|downgrade <target>` against `database_url`, as the command line runs it."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    getattr(command, action)(alembic_config(), target)


def stored_questions(engine: Engine) -> list[tuple[str, str]]:
    with Session(engine) as session:
        rows = session.exec(select(Question).order_by(Question.created_at, Question.id))
        return [(row.text, row.reference_answer) for row in rows]


def snapshot(engine: Engine) -> tuple[str | None, list[tuple[Any, ...]], int]:
    """Revision, every question row including timestamps, and the boot count."""
    with Session(engine) as session:
        rows = session.exec(select(Question).order_by(Question.id)).all()
        counter = session.get(BootCounter, 1)
        return (
            current_revision(session.connection()),
            [(q.id, q.text, q.reference_answer, q.created_at, q.updated_at) for q in rows],
            counter.boots if counter else -1,
        )


def application_tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) & APPLICATION_TABLES


def samples_as_pairs(sample_questions: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(sample["text"], sample["reference_answer"]) for sample in sample_questions]


def test_empty_to_head(
    monkeypatch: pytest.MonkeyPatch,
    empty_database_url: str,
    migration_engine: Engine,
    sample_questions: list[dict[str, str]],
) -> None:
    """US3-1, SC-006: the tables, the sample questions (Cyrillic and line break intact) and a
    zero boot count."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    revision, _, boots = snapshot(migration_engine)
    assert revision == head_revision()
    assert application_tables(migration_engine) == APPLICATION_TABLES
    assert stored_questions(migration_engine) == samples_as_pairs(sample_questions)
    assert boots == 0
    assert "role" not in {c["name"] for c in inspect(migration_engine).get_columns("users")}


def test_head_to_head_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """US3-2, FR-008, FR-020: re-applying the migrations is a no-op — no error, no re-seed."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    before = snapshot(migration_engine)
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    after = snapshot(migration_engine)
    assert after == before
    assert len(after[1]) == 6


def test_stairway(
    monkeypatch: pytest.MonkeyPatch,
    empty_database_url: str,
    migration_engine: Engine,
    sample_questions: list[dict[str, str]],
) -> None:
    """Every revision's downgrade undoes its upgrade, one step at a time, then all the way."""
    script = ScriptDirectory.from_config(alembic_config())
    revisions = [revision.revision for revision in script.walk_revisions()][::-1]
    for revision in revisions:
        run_alembic(monkeypatch, empty_database_url, "upgrade", revision)
        run_alembic(monkeypatch, empty_database_url, "downgrade", "-1")
        run_alembic(monkeypatch, empty_database_url, "upgrade", revision)
        assert snapshot(migration_engine)[0] == revision

    run_alembic(monkeypatch, empty_database_url, "downgrade", "base")
    assert application_tables(migration_engine) == set()

    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    assert stored_questions(migration_engine) == samples_as_pairs(sample_questions)


def test_single_head() -> None:
    """Two branches that each add a migration cannot both merge unnoticed."""
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1


def test_models_match_the_migrated_schema(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """FR-007: a model changed without a migration fails here, on both engines."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    with migration_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, SQLModel.metadata) == []


def _waiting_on_migration_lock(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted "
                "AND database = (SELECT oid FROM pg_database WHERE datname = current_database())"
            )
        ).scalar_one()


def test_concurrent_upgrades_apply_once(
    request: pytest.FixtureRequest,
    empty_database_url: str,
    migration_engine: Engine,
    sample_questions: list[dict[str, str]],
) -> None:
    """Two instances starting at once during a deploy overlap (spec edge case).

    Two real `alembic upgrade head` processes, as two containers would run. The test holds the
    migration lock itself until both are queued behind it, so the race is certain rather than
    left to timing; releasing it lets them through one at a time.
    """
    if request.node.callspec.params["empty_database_url"] == "sqlite":
        pytest.skip("the advisory lock is PostgreSQL-only by design (research D5, D12)")

    environment = {**os.environ, "DATABASE_URL": empty_database_url}
    holder = migration_engine.connect()
    transaction = holder.begin()
    holder.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(2)
    ]
    try:
        deadline = time.monotonic() + 30
        while _waiting_on_migration_lock(migration_engine) < 2:
            assert time.monotonic() < deadline, "both upgrades should queue on the lock"
            assert all(process.poll() is None for process in processes), "an upgrade exited early"
            time.sleep(0.1)
    finally:
        transaction.rollback()
        holder.close()

    for process in processes:
        output, _ = process.communicate(timeout=60)
        assert process.returncode == 0, output

    with migration_engine.connect() as connection:
        versions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    assert [row[0] for row in versions] == [head_revision()]
    assert stored_questions(migration_engine) == samples_as_pairs(sample_questions)


# ---------------------------------------------------------------------------------------------
# Milestone 5: roles move to `user_roles` without losing an administrator
# ---------------------------------------------------------------------------------------------
#
# Lightweight table constructs, never the ORM models: the models describe head, and these tests
# write rows at older revisions too. See
# specs/005-roles-authorization/data-model.md#7-schema-revision-introduced-by-this-milestone.

AUTH_REVISION = "a35580dee830"
ROLES_REVISION = "50f17535d874"
"""Milestone 5's head. These tests write `users.role`, which milestone 6 drops (research D8)."""

users_t = sa.table(
    "users",
    sa.column("id", sa.Integer()),
    sa.column("email", sa.String()),
    sa.column("role", sa.String()),
    sa.column("is_active", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
user_roles_t = sa.table(
    "user_roles",
    sa.column("user_id", sa.Integer()),
    sa.column("role", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
sessions_t = sa.table(
    "sessions",
    sa.column("id", sa.Integer()),
    sa.column("user_id", sa.Integer()),
    sa.column("token_hash", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("expires_at", sa.DateTime(timezone=True)),
)
login_codes_t = sa.table(
    "login_codes",
    sa.column("user_id", sa.Integer()),
    sa.column("code_hash", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("expires_at", sa.DateTime(timezone=True)),
    sa.column("attempts", sa.Integer()),
)


def add_user(connection: Connection, email: str, role: str | None, active: bool) -> int:
    now = utc_now()
    return connection.execute(
        users_t.insert()
        .values(email=email, role=role, is_active=active, created_at=now, updated_at=now)
        .returning(users_t.c.id)
    ).scalar_one()


def add_session(connection: Connection, user_id: int, token_hash: str) -> None:
    now = utc_now()
    connection.execute(
        sessions_t.insert().values(
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(days=14),
        )
    )


def add_role(connection: Connection, user_id: int, role: str) -> None:
    connection.execute(
        user_roles_t.insert().values(user_id=user_id, role=role, created_at=utc_now())
    )


def test_upgrade_keeps_the_active_administrators(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """Every active milestone 4 administrator holds the administrator role at head; an inactive
    one holds none; existing sessions survive with no role chosen yet (SC-010)."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", AUTH_REVISION)
    with migration_engine.begin() as connection:
        active = add_user(connection, "active@example.com", "admin", True)
        inactive = add_user(connection, "inactive@example.com", "admin", False)
        add_session(connection, active, "a" * 64)

    run_alembic(monkeypatch, empty_database_url, "upgrade", ROLES_REVISION)

    with migration_engine.begin() as connection:
        roles = connection.execute(sa.select(user_roles_t.c.user_id, user_roles_t.c.role)).all()
        assert [tuple(row) for row in roles] == [(active, "admin")]
        assert inactive != active
        current = connection.execute(
            sa.select(sa.column("user_id"), sa.column("current_role")).select_from(
                sa.table("sessions")
            )
        ).all()
        assert [tuple(row) for row in current] == [(active, None)]
        add_user(connection, "new@example.com", None, True)  # `users.role` is now nullable


def test_downgrade_deactivates_everyone_who_is_not_an_administrator(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """Milestone 4 treats every active user as an administrator, so the way back must not leave
    a teacher or a student active."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", ROLES_REVISION)
    with migration_engine.begin() as connection:
        admin = add_user(connection, "admin@example.com", None, True)
        add_role(connection, admin, "admin")
        add_session(connection, admin, "a" * 64)
        both = add_user(connection, "admin.student@example.com", None, True)
        add_role(connection, both, "admin")
        add_role(connection, both, "student")
        teacher = add_user(connection, "teacher@example.com", None, True)
        add_role(connection, teacher, "teacher")
        add_session(connection, teacher, "t" * 64)
        now = utc_now()
        connection.execute(
            login_codes_t.insert().values(
                user_id=teacher,
                code_hash="c" * 64,
                created_at=now,
                expires_at=now + timedelta(minutes=20),
                attempts=0,
            )
        )
        former = add_user(connection, "former@example.com", None, False)

    run_alembic(monkeypatch, empty_database_url, "downgrade", AUTH_REVISION)

    with migration_engine.begin() as connection:
        found = {
            row.id: (row.role, row.is_active)
            for row in connection.execute(
                sa.select(users_t.c.id, users_t.c.role, users_t.c.is_active)
            )
        }
        assert found == {
            admin: ("admin", True),
            both: ("admin", True),
            teacher: ("teacher", False),
            former: ("admin", False),
        }
        session_owners = connection.execute(sa.select(sessions_t.c.user_id)).scalars().all()
        assert session_owners == [admin]
        assert connection.execute(sa.select(login_codes_t.c.user_id)).scalars().all() == []
        tables = set(inspect(connection).get_table_names())
        assert "user_roles" not in tables
        assert "current_role" not in {
            c["name"] for c in inspect(connection).get_columns("sessions")
        }

    with pytest.raises(IntegrityError), migration_engine.begin() as connection:
        add_user(connection, "nobody@example.com", None, False)
