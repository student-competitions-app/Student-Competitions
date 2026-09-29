"""Shared test fixtures: every database test runs on SQLite and on PostgreSQL.

`database_url` is parametrized over both engines, so any test that uses it — directly, or through
`engine`, `session` or `client` — runs twice, as `[sqlite]` and `[postgresql]` (FR-030). Each test
gets its own clone of a database migrated to head once per session **with Alembic**, so every run
also exercises the migrations, and no test sees another's writes.

PostgreSQL comes from `TEST_POSTGRES_URL`, a server whose role may `CREATE DATABASE`. It is never
`DATABASE_URL`, so a test can never reach a developer's data or production (FR-031). Without it
the PostgreSQL cases are skipped locally; under `CI=true` the session refuses to start.

See specs/003-database-questions/research.md#d12.

Sign-in (milestone 4): every test runs with `EMAIL_BACKEND=memory`, so no email leaves the
process and the code can be read from the `outbox`. `client` is anonymous; `admin_client` is
signed in as `ADMIN_EMAIL` through a session created directly in the database, the suite's only
sign-in shortcut (specs/004-email-otp-auth/research.md#d15).
"""

import itertools
import os
import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from app.core.config import resolve_database_url
from app.core.db import create_db_engine
from app.core.migrations import alembic_config
from app.core.security import SESSION_COOKIE_NAME, sign_cookie_value
from app.main import app
from app.services.email import EmailMessage, MemoryEmailSender
from app.services.sessions import create_session
from app.services.users import get_active_user_by_email

ENGINES = ["sqlite", "postgresql"]

POSTGRES_SKIP_REASON = "set TEST_POSTGRES_URL to run the PostgreSQL cases (see README)"

ADMIN_EMAIL = "admin@example.com"
"""The one administrator every application fixture is started with (`ADMIN_EMAILS`)."""

AUTH_VARIABLES = ("SECRET_KEY", "ADMIN_EMAILS", "RESEND_API_KEY", "EMAIL_FROM")

RUN_TOKEN = secrets.token_hex(4)
"""In every PostgreSQL database name, so parallel or repeated runs against one server never
collide, and a leftover from a crashed run is recognisable."""

_database_numbers = itertools.count(1)


def pytest_sessionstart(session: pytest.Session) -> None:
    """CI must run both halves of the matrix; skipping PostgreSQL there would go green on half."""
    if os.environ.get("CI") == "true" and not os.environ.get("TEST_POSTGRES_URL"):
        pytest.exit(
            "CI=true but TEST_POSTGRES_URL is not set: the PostgreSQL half of the suite would be "
            "skipped. Configure the postgres service in the workflow.",
            returncode=1,
        )


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test inherits a developer's `DATABASE_URL`, `RENDER` flag or sign-in settings from the
    shell, and no test can send a real email: the backend is always `memory`."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    for name in AUTH_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMAIL_BACKEND", "memory")


# ---------------------------------------------------------------------------------------------
# Migrations and servers
# ---------------------------------------------------------------------------------------------


def migrate(database_url: str, target: str = "head") -> None:
    """Run `alembic upgrade <target>` against `database_url`, exactly as the entrypoint does."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", database_url)
        command.upgrade(alembic_config(), target)


def _postgres_admin_url() -> str:
    raw = os.environ.get("TEST_POSTGRES_URL")
    if not raw:
        pytest.skip(POSTGRES_SKIP_REASON)
    return resolve_database_url({"DATABASE_URL": raw})


def _postgres_database_url(admin_url: str, name: str) -> str:
    return make_url(admin_url).set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def _postgres_admin() -> Iterator[tuple[str, Engine]]:
    """An `AUTOCOMMIT` engine on the test server: `CREATE`/`DROP DATABASE` cannot run in a
    transaction."""
    url = _postgres_admin_url()
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    yield url, engine
    engine.dispose()


def _create_postgres_database(admin: tuple[str, Engine], name: str, template: str | None) -> str:
    admin_url, engine = admin
    statement = f'CREATE DATABASE "{name}"'
    if template is not None:
        statement += f' TEMPLATE "{template}"'
    with engine.connect() as connection:
        connection.execute(text(statement))
    return _postgres_database_url(admin_url, name)


def _drop_postgres_database(admin: tuple[str, Engine], name: str) -> None:
    with admin[1].connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


# ---------------------------------------------------------------------------------------------
# Templates: one migrated database per engine per session
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _sqlite_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("sqlite-template") / "template.sqlite3"
    migrate(f"sqlite:///{path}")
    return path


@pytest.fixture(scope="session")
def _postgres_template(_postgres_admin: tuple[str, Engine]) -> Iterator[str]:
    name = f"sc_test_{RUN_TOKEN}_template"
    migrate(_create_postgres_database(_postgres_admin, name, template=None))
    yield name
    _drop_postgres_database(_postgres_admin, name)


# ---------------------------------------------------------------------------------------------
# Per-test databases
# ---------------------------------------------------------------------------------------------


@pytest.fixture(params=ENGINES, ids=ENGINES)
def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[str]:
    """A private database at head, as the migrations leave it: samples present, `boots = 0`.

    The yielded URL is in the form the application uses (`postgresql+psycopg://`).
    """
    if request.param == "sqlite":
        template: Path = request.getfixturevalue("_sqlite_template")
        clone = tmp_path / "test.sqlite3"
        shutil.copy(template, clone)
        yield f"sqlite:///{clone}"
        return
    admin = request.getfixturevalue("_postgres_admin")
    template_name = request.getfixturevalue("_postgres_template")
    name = f"sc_test_{RUN_TOKEN}_{next(_database_numbers)}"
    yield _create_postgres_database(admin, name, template=template_name)
    _drop_postgres_database(admin, name)


@pytest.fixture(params=ENGINES, ids=ENGINES)
def empty_database_url(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[str]:
    """A database with no migration applied, for the startup and migration tests."""
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'empty.sqlite3'}"
        return
    admin = request.getfixturevalue("_postgres_admin")
    name = f"sc_test_{RUN_TOKEN}_{next(_database_numbers)}_empty"
    yield _create_postgres_database(admin, name, template=None)
    _drop_postgres_database(admin, name)


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    db_engine = create_db_engine(database_url)
    yield db_engine
    db_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Iterator[TestClient]:
    """Drive the real ASGI application in-process — no live server, no bound port.

    The database is given the way production gives it, through `DATABASE_URL`, so `lifespan`
    resolves, guards and counts the start exactly as it does on Render. `ADMIN_EMAIL` is the one
    administrator, reconciled at start. The client itself is anonymous.
    """
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def outbox(client: TestClient) -> list[EmailMessage]:
    """Every email the running application has sent, oldest first."""
    sender = app.state.email_sender
    assert isinstance(sender, MemoryEmailSender)
    return sender.outbox


def sign_in_directly(test_client: TestClient, email: str) -> str:
    """Give `test_client` a session for the active user `email` without the email step, and
    return the plain session token.

    **Test-only.** It calls `create_session` directly on the application's database and sets the
    signed cookie by hand. No route or setting of the running application offers anything like
    it: there is no login bypass (FR-034, FR-046). Requires the application to be started (the
    `client` fixture).
    """
    with Session(app.state.engine) as db_session:
        user = get_active_user_by_email(db_session, email)
        assert user is not None, "no active user with that address"
        token = create_session(db_session, user)
    test_client.cookies.set(
        SESSION_COOKIE_NAME, sign_cookie_value(app.state.settings.secret_key, token)
    )
    return token


@pytest.fixture
def admin_client(client: TestClient) -> Iterator[TestClient]:
    """A second client for the same running application, signed in as `ADMIN_EMAIL`.

    It shares the application `client` started (one start, one boot, one outbox) but has its own
    cookie jar, so `client` stays anonymous. The session is created directly in the database by
    `sign_in_directly`: the only sign-in shortcut, and it exists only in `tests/`.
    """
    # Not entered as a context manager: that would run `lifespan` a second time (a second boot,
    # a fresh outbox). Requests still go through the application `client` started.
    signed_in = TestClient(app)
    sign_in_directly(signed_in, ADMIN_EMAIL)
    yield signed_in
    signed_in.close()


# ---------------------------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_questions() -> list[dict[str, Any]]:
    """The seeded sample questions, read from the migration that inserts them.

    The migration is the single source of truth; tests never keep a copy that could drift
    (research D6).
    """
    script = ScriptDirectory.from_config(alembic_config())
    for revision in script.walk_revisions():
        samples = getattr(revision.module, "SAMPLE_QUESTIONS", None)
        if samples is not None:
            return samples
    raise LookupError("no revision in migrations/versions/ defines SAMPLE_QUESTIONS")
