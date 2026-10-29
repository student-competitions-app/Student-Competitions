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
from datetime import datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

import app.models  # noqa: F401 — every table on SQLModel.metadata, for the drift check
from app.core.config import PROJECT_ROOT
from app.core.db import create_db_engine, utc_now
from app.core.migrations import (
    MIGRATION_LOCK_KEY,
    alembic_config,
    current_revision,
    head_revision,
)

APPLICATION_TABLES = {
    "questions",
    "boot_counter",
    "subjects",
    "regions",
    "institutions",
    "teacher_profiles",
    "teacher_institutions",
    "consent_texts",
    "consent_records",
    "invitation_cutoffs",
    "classes",
    "enrolments",
    "teams",
    "team_memberships",
}


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


questions_t = sa.table(
    "questions",
    sa.column("id", sa.Integer()),
    sa.column("text", sa.String()),
    sa.column("reference_answer", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
"""The columns `questions` has at every revision: the models describe head only, and milestone
11 added `subject_id` and `deleted_at`."""


def stored_questions(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(questions_t.c.text, questions_t.c.reference_answer).order_by(
                questions_t.c.created_at, questions_t.c.id
            )
        )
        return [tuple(row) for row in rows]


def snapshot(engine: Engine) -> tuple[str | None, list[tuple[Any, ...]], int]:
    """Revision, every question row including timestamps, and the boot count."""
    with engine.connect() as connection:
        rows = connection.execute(sa.select(questions_t).order_by(questions_t.c.id)).all()
        boots = connection.execute(text("SELECT boots FROM boot_counter WHERE id = 1")).scalar()
        return (
            current_revision(connection),
            [tuple(row) for row in rows],
            boots if boots is not None else -1,
        )


def application_tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) & APPLICATION_TABLES


def test_empty_to_head(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """US3-1: the tables, no questions (milestone 11 deletes the samples, SC-007) and a zero boot
    count."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    revision, _, boots = snapshot(migration_engine)
    assert revision == head_revision()
    assert application_tables(migration_engine) == APPLICATION_TABLES
    assert stored_questions(migration_engine) == []
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
    assert after[1] == []


def test_stairway(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
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
    assert stored_questions(migration_engine) == []


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
    request: pytest.FixtureRequest, empty_database_url: str, migration_engine: Engine
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
    assert stored_questions(migration_engine) == []


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


# ---------------------------------------------------------------------------------------------
# Milestone 8: the teacher and student lists are retired, once
# ---------------------------------------------------------------------------------------------
#
# See specs/008-teacher-management-consent/data-model.md §10 and research D16. Seeded at the schema
# revision, before the data step, with `users` as it is from milestone 6 on (no `role` column).

CONSENT_SCHEMA_REVISION = "f3bd41a67737"
RETIREMENT_REVISION = "f13dab4dd8ba"

users_m8_t = sa.table(
    "users",
    sa.column("id", sa.Integer()),
    sa.column("email", sa.String()),
    sa.column("is_active", sa.Boolean()),
    sa.column("data_erased_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def add_m8_user(connection: Connection, email: str, active: bool, *roles: str) -> int:
    now = utc_now()
    user_id = connection.execute(
        users_m8_t.insert()
        .values(email=email, is_active=active, created_at=now, updated_at=now)
        .returning(users_m8_t.c.id)
    ).scalar_one()
    for role in roles:
        add_role(connection, user_id, role)
    return user_id


def add_login_code(connection: Connection, user_id: int) -> None:
    now = utc_now()
    connection.execute(
        login_codes_t.insert().values(
            user_id=user_id,
            code_hash="c" * 64,
            created_at=now,
            expires_at=now + timedelta(minutes=20),
            attempts=0,
        )
    )


def retirement_state(engine: Engine) -> dict[str, Any]:
    with engine.begin() as connection:
        found = {
            row.id: (row.email, row.is_active, row.data_erased_at is not None)
            for row in connection.execute(
                sa.select(
                    users_m8_t.c.id,
                    users_m8_t.c.email,
                    users_m8_t.c.is_active,
                    users_m8_t.c.data_erased_at,
                )
            )
        }
        roles = sorted(
            tuple(row)
            for row in connection.execute(sa.select(user_roles_t.c.user_id, user_roles_t.c.role))
        )
        session_owners = sorted(connection.execute(sa.select(sessions_t.c.user_id)).scalars())
        code_owners = sorted(connection.execute(sa.select(login_codes_t.c.user_id)).scalars())
        cutoffs = connection.execute(text("SELECT count(*) FROM invitation_cutoffs")).scalar_one()
    return {
        "users": found,
        "roles": roles,
        "sessions": session_owners,
        "codes": code_owners,
        "cutoffs": cutoffs,
    }


def test_the_role_lists_are_retired_once(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """FR-058, US7-1: list-granted teacher and student roles are gone; administrators keep their
    role and email; people left with no role are deactivated with their email replaced; everyone
    affected is signed out; and the way back changes nothing."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", CONSENT_SCHEMA_REVISION)
    with migration_engine.begin() as connection:
        admin = add_m8_user(connection, "admin@example.com", True, "admin")
        admin_teacher = add_m8_user(
            connection, "admin.teacher@example.com", True, "admin", "teacher"
        )
        teacher = add_m8_user(connection, "teacher@example.com", True, "teacher")
        student = add_m8_user(connection, "student@example.com", True, "student")
        both = add_m8_user(connection, "teacher.student@example.com", True, "teacher", "student")
        former = add_m8_user(connection, "former@example.com", False)
        for user_id, token in zip(
            (admin, admin_teacher, teacher, student, both, former), "abcdef", strict=True
        ):
            add_session(connection, user_id, token * 64)
        add_login_code(connection, teacher)
        add_login_code(connection, admin)

    run_alembic(monkeypatch, empty_database_url, "upgrade", RETIREMENT_REVISION)

    state = retirement_state(migration_engine)
    assert state["roles"] == [(admin, "admin"), (admin_teacher, "admin")]
    assert state["users"] == {
        admin: ("admin@example.com", True, False),
        admin_teacher: ("admin.teacher@example.com", True, False),
        teacher: (f"erased-{teacher}", False, True),
        student: (f"erased-{student}", False, True),
        both: (f"erased-{both}", False, True),
        former: (f"erased-{former}", False, True),
    }
    assert state["sessions"] == [admin]
    assert state["codes"] == [admin]
    assert state["cutoffs"] == 0

    run_alembic(monkeypatch, empty_database_url, "downgrade", "-1")
    assert retirement_state(migration_engine) == state


def test_the_student_consent_text_is_published_once(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """Milestone 9 research D13, D18: head holds exactly one student text, version 1."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    with migration_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT version FROM consent_texts WHERE role = 'student'")
        ).all()
    assert [tuple(row) for row in rows] == [(1,)]


# ---------------------------------------------------------------------------------------------
# Milestone 11: the question bank (the samples go, the setting is renamed)
# ---------------------------------------------------------------------------------------------
#
# See specs/011-question-bank/data-model.md §6 and research R3.

BEFORE_QUESTION_BANK = "596ead9f1205"

teacher_profiles_t = sa.table(
    "teacher_profiles",
    sa.column("user_id", sa.Integer()),
    sa.column("can_create_competitions", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def test_upgrading_deletes_the_samples_and_keeps_the_setting(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """US8-1, SC-007: the sample questions are gone. US6-1, SC-006: each teacher keeps their
    value under the new name."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", BEFORE_QUESTION_BANK)
    assert len(stored_questions(migration_engine)) == 6
    with migration_engine.begin() as connection:
        now = utc_now()
        values = {}
        for email, value in (("yes@example.com", True), ("no@example.com", False)):
            user_id = add_m8_user(connection, email, True, "teacher")
            connection.execute(
                teacher_profiles_t.insert().values(
                    user_id=user_id, can_create_competitions=value, created_at=now, updated_at=now
                )
            )
            values[user_id] = value

    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")

    assert stored_questions(migration_engine) == []
    with migration_engine.connect() as connection:
        found = connection.execute(
            text("SELECT user_id, can_manage_competitions FROM teacher_profiles")
        ).all()
    assert {row[0]: bool(row[1]) for row in found} == values
    columns = {c["name"] for c in inspect(migration_engine).get_columns("teacher_profiles")}
    assert "can_create_competitions" not in columns


def test_the_questions_table_at_head(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    inspector = inspect(migration_engine)
    columns = {c["name"]: c for c in inspector.get_columns("questions")}
    assert columns["subject_id"]["nullable"] is False
    assert columns["deleted_at"]["nullable"] is True
    assert columns["text"]["type"].length == 2000
    assert columns["reference_answer"]["type"].length == 2000
    indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("questions")}
    assert indexes["ix_questions_subject_id"] == ["subject_id"]
    [foreign_key] = inspector.get_foreign_keys("questions")
    assert foreign_key["name"] == "fk_questions_subject_id_subjects"
    assert (foreign_key["referred_table"], foreign_key["referred_columns"]) == ("subjects", ["id"])


def test_sqlite_never_reuses_a_question_id(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    empty_database_url: str,
    migration_engine: Engine,
) -> None:
    """R1: the rebuilt table has `AUTOINCREMENT`, so a rowid is never handed out twice."""
    if request.node.callspec.params["empty_database_url"] != "sqlite":
        pytest.skip("AUTOINCREMENT is SQLite's; PostgreSQL's sequence is checked below")
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    with migration_engine.connect() as connection:
        sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'questions'")
        ).scalar_one()
    assert "AUTOINCREMENT" in sql


def test_postgresql_keeps_the_question_id_sequence(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    empty_database_url: str,
    migration_engine: Engine,
) -> None:
    """R3: the table was altered, not rebuilt, so ids still come from the original sequence and
    continue past the seed's samples."""
    if request.node.callspec.params["empty_database_url"] != "postgresql":
        pytest.skip("the id sequence is PostgreSQL's")
    run_alembic(monkeypatch, empty_database_url, "upgrade", BEFORE_QUESTION_BANK)
    with migration_engine.connect() as connection:
        largest_sample = connection.execute(text("SELECT max(id) FROM questions")).scalar_one()
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    with migration_engine.begin() as connection:
        default = connection.execute(
            text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = 'questions' AND column_name = 'id'"
            )
        ).scalar_one()
        assert default == "nextval('questions_id_seq'::regclass)"
        subject_id = connection.execute(
            text(
                "INSERT INTO subjects (name, name_key, is_active, created_at, updated_at) "
                "VALUES ('Physics', 'physics', true, now(), now()) RETURNING id"
            )
        ).scalar_one()
        new_id = connection.execute(
            text(
                "INSERT INTO questions (subject_id, text, reference_answer, created_at, "
                "updated_at) VALUES (:s, 'Why?', 'Because.', now(), now()) RETURNING id"
            ),
            {"s": subject_id},
        ).scalar_one()
    assert new_id > largest_sample


# ---------------------------------------------------------------------------------------------
# Milestone 11.1: teams, and the student consent text rewritten in place
# ---------------------------------------------------------------------------------------------
#
# See specs/011.1-teacher-teams/data-model.md §7 and research R2, R9.

BEFORE_TEAMS = "3e32707ed794"


def test_the_teams_tables_at_head(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    inspector = inspect(migration_engine)
    columns = {c["name"]: c["nullable"] for c in inspector.get_columns("teams")}
    assert columns == {
        "id": False,
        "institution_id": False,
        "name": False,
        "name_key": False,
        "created_at": False,
        "updated_at": False,
        "deleted_at": True,
    }
    indexes = {
        i["name"]: (i["column_names"], bool(i["unique"])) for i in inspector.get_indexes("teams")
    }
    assert indexes == {
        "ix_teams_institution_id": (["institution_id"], False),
        "uq_teams_name_key_live": (["name_key"], True),
    }
    [foreign_key] = inspector.get_foreign_keys("teams")
    assert foreign_key["name"] == "fk_teams_institution_id_institutions"
    memberships = inspector.get_pk_constraint("team_memberships")
    assert (memberships["name"], memberships["constrained_columns"]) == (
        "pk_team_memberships",
        ["team_id", "user_id"],
    )
    assert {i["name"]: i["column_names"] for i in inspector.get_indexes("team_memberships")} == {
        "ix_team_memberships_user_id": ["user_id"]
    }
    assert sorted(fk["name"] for fk in inspector.get_foreign_keys("team_memberships")) == [
        "fk_team_memberships_team_id_teams",
        "fk_team_memberships_user_id_users",
    ]


regions_t = sa.table(
    "regions",
    sa.column("id", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column("name_key", sa.String()),
    sa.column("is_active", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
institutions_t = sa.table(
    "institutions",
    sa.column("id", sa.Integer()),
    sa.column("region_id", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column("name_key", sa.String()),
    sa.column("is_active", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
teams_t = sa.table(
    "teams",
    sa.column("id", sa.Integer()),
    sa.column("institution_id", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column("name_key", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
)


def add_institution(connection: Connection) -> int:
    now = utc_now()
    stamps = {"is_active": True, "created_at": now, "updated_at": now}
    region_id = connection.execute(
        regions_t.insert().values(name="Kyiv", name_key="kyiv", **stamps).returning(regions_t.c.id)
    ).scalar_one()
    return connection.execute(
        institutions_t.insert()
        .values(region_id=region_id, name="KPI", name_key="kpi", **stamps)
        .returning(institutions_t.c.id)
    ).scalar_one()


def test_the_live_name_index_is_partial(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """Research R2: any number of deleted teams share a key with each other and with one live
    team; a second live team with the key is refused."""
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")

    def comets(institution_id: int, deleted: datetime | None) -> sa.Insert:
        now = utc_now()
        return teams_t.insert().values(
            institution_id=institution_id,
            name="Comets",
            name_key="comets",
            created_at=now,
            updated_at=now,
            deleted_at=deleted,
        )

    with migration_engine.begin() as connection:
        institution_id = add_institution(connection)
        for deleted in (utc_now(), utc_now(), None):
            connection.execute(comets(institution_id, deleted))
    with pytest.raises(IntegrityError), migration_engine.begin() as connection:
        connection.execute(comets(institution_id, None))
    with migration_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM teams")).scalar_one() == 3


consent_texts_t = sa.table(
    "consent_texts",
    sa.column("id", sa.Integer()),
    sa.column("role", sa.String()),
    sa.column("version", sa.Integer()),
    sa.column("text", sa.Text()),
    sa.column("published_at", sa.DateTime(timezone=True)),
)
consent_records_t = sa.table(
    "consent_records",
    sa.column("id", sa.Integer()),
    sa.column("user_id", sa.Integer()),
    sa.column("consent_text_id", sa.Integer()),
    sa.column("accepted_at", sa.DateTime(timezone=True)),
    sa.column("inviter_id", sa.Integer()),
    sa.column("invitation_issued_at", sa.DateTime(timezone=True)),
)


def student_text(engine: Engine) -> tuple[int, int, str, datetime]:
    with engine.connect() as connection:
        row = connection.execute(
            sa.select(
                consent_texts_t.c.id,
                consent_texts_t.c.version,
                consent_texts_t.c.text,
                consent_texts_t.c.published_at,
            ).where(consent_texts_t.c.role == "student")
        ).one()
    return row[0], row[1], row[2], row[3]


def test_the_student_text_is_rewritten_in_place_and_back(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str, migration_engine: Engine
) -> None:
    """Milestone 11.1 US7-5, FR-015, research R9: the same row, version 1, published
    2026-10-19, with every consent record still pointing at it; the downgrade restores the
    original wording byte for byte, and the upgrade brings the rewrite back."""
    module = ScriptDirectory.from_config(alembic_config()).get_revision("09cbcbe472be").module
    rewrite, original = (
        module.STUDENT_CONSENT_TEXT_V1_REWRITE,
        module._STUDENT_CONSENT_TEXT_V1_ORIGINAL,
    )
    run_alembic(monkeypatch, empty_database_url, "upgrade", BEFORE_TEAMS)
    text_id, version, text_before, published = student_text(migration_engine)
    assert (version, text_before) == (1, original)
    with migration_engine.begin() as connection:
        teacher = add_m8_user(connection, "olena@example.com", True, "teacher")
        student = add_m8_user(connection, "taras@example.com", True, "student")
        now = utc_now()
        record_id = connection.execute(
            consent_records_t.insert()
            .values(
                user_id=student,
                consent_text_id=text_id,
                accepted_at=now,
                inviter_id=teacher,
                invitation_issued_at=now,
            )
            .returning(consent_records_t.c.id)
        ).scalar_one()

    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    assert student_text(migration_engine) == (text_id, 1, rewrite, published)
    assert published.date().isoformat() == "2026-10-19"
    with migration_engine.connect() as connection:
        pointed = connection.execute(
            sa.select(consent_records_t.c.consent_text_id).where(
                consent_records_t.c.id == record_id
            )
        ).scalar_one()
    assert pointed == text_id

    run_alembic(monkeypatch, empty_database_url, "downgrade", BEFORE_TEAMS)
    assert student_text(migration_engine) == (text_id, 1, original, published)
    run_alembic(monkeypatch, empty_database_url, "upgrade", "head")
    assert student_text(migration_engine)[2] == rewrite
