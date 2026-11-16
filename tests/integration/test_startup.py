"""Application startup: the effective readiness gate.

The application refuses to start without a usable database at head, or on Render without safe
sign-in settings, so an instance that answers at all has both. See
specs/003-database-questions/contracts/http-routes.md#application-startup-the-effective-readiness-
gate, specs/004-email-otp-auth/contracts/configuration.md,
specs/005-roles-authorization/contracts/configuration.md and
specs/008-teacher-management-consent/contracts/configuration.md.
"""

import logging
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.core.config as config
from app.core import i18n
from app.core.db import create_db_engine
from app.core.i18n import Language, LanguageMiddleware
from app.core.log_redaction import AccessLogRedactor
from app.core.migrations import alembic_config, head_revision
from app.main import app
from app.models import User, UserRole
from app.services.database_status import read_database_status
from tests.conftest import migrate


def test_refuses_to_start_on_an_unmigrated_database(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", empty_database_url)
    with pytest.raises(RuntimeError) as caught, TestClient(app):
        pass
    message = str(caught.value)
    assert "uv run alembic upgrade head" in message
    assert empty_database_url not in message


def test_refuses_to_start_on_render_without_a_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RENDER", "true")
    with (
        pytest.raises(config.DatabaseConfigError, match="DATABASE_URL is required"),
        TestClient(app),
    ):
        pass


def _revision_before_head() -> str:
    previous = ScriptDirectory.from_config(alembic_config()).get_revision(head_revision())
    assert previous is not None and isinstance(previous.down_revision, str)
    return previous.down_revision


def _boots(database_url: str) -> int:
    engine = create_db_engine(database_url)
    try:
        with Session(engine) as session:
            return read_database_status(session).boots
    finally:
        engine.dispose()


def test_a_refused_start_behind_head_is_not_counted(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str
) -> None:
    """A database one revision behind head: the tables exist, but the start is refused."""
    migrate(empty_database_url, _revision_before_head())
    monkeypatch.setenv("DATABASE_URL", empty_database_url)
    with pytest.raises(RuntimeError, match="uv run alembic upgrade head"), TestClient(app):
        pass
    assert _boots(empty_database_url) == 0


def test_a_refused_start_on_render_is_not_counted(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """`RENDER` without `DATABASE_URL` never reaches this database; its count stays at zero."""
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(config.DatabaseConfigError), TestClient(app):
        pass
    assert _boots(database_url) == 0


# ---------------------------------------------------------------------------------------------
# Sign-in settings (milestone 4)
# ---------------------------------------------------------------------------------------------

AUTH_SETTINGS = ("EMAIL_BACKEND", "SECRET_KEY", "ADMIN_EMAILS", "RESEND_API_KEY", "EMAIL_FROM")


def test_refuses_to_start_on_render_without_auth_settings(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """US6-4, FR-041: every missing setting named at once, and the database never touched."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("EMAIL_BACKEND")
    with pytest.raises(config.AuthConfigError) as caught, TestClient(app):
        pass
    for name in AUTH_SETTINGS:
        assert name in str(caught.value)
    assert _boots(database_url) == 0


def test_refuses_the_console_backend_on_render_without_echoing_values(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    for name, value in {
        "RENDER": "true",
        "DATABASE_URL": database_url,
        "EMAIL_BACKEND": "console",
        "SECRET_KEY": "ci-dummy-not-a-secret-0123456789abcdef",
        "ADMIN_EMAILS": "ci-admin@example.com",
        "RESEND_API_KEY": "ci-dummy-key",
        "EMAIL_FROM": "ci@example.com",
    }.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(config.AuthConfigError) as caught, TestClient(app):
        pass
    message = str(caught.value)
    assert "EMAIL_BACKEND" in message
    for value in ("ci-dummy-not-a-secret", "ci-dummy-key", "ci-admin@example.com"):
        assert value not in message
    assert _boots(database_url) == 0


def test_starts_locally_with_no_auth_settings(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """US6-1, FR-042: every sign-in setting is optional locally."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("EMAIL_BACKEND")
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert app.state.settings.email_backend == "console"
        assert app.state.settings.public_base_url is None
    assert _boots(database_url) == 1


@pytest.mark.parametrize("value", ["listed@example.com", "planted-not-an-address"])
def test_the_retired_role_lists_are_ignored(
    monkeypatch: pytest.MonkeyPatch, database_url: str, value: str
) -> None:
    """Milestone 8 FR-056, US7-4: a leftover `TEACHER_EMAILS` or `STUDENT_EMAILS` value, valid
    or not, neither refuses the start nor creates a user or a role."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv("TEACHER_EMAILS", value)
    monkeypatch.setenv("STUDENT_EMAILS", value)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
    engine = create_db_engine(database_url)
    try:
        with Session(engine) as session:
            assert [user.email for user in session.exec(select(User))] == ["admin@example.com"]
            roles = session.exec(select(UserRole.role)).all()
            assert roles == ["admin"]
    finally:
        engine.dispose()
    assert _boots(database_url) == 1


def test_the_access_log_redactor_is_installed_once(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """Milestone 8 research D14: one filter on `uvicorn.access`, also after a second start."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    access_logger = logging.getLogger("uvicorn.access")
    for _ in range(2):
        with TestClient(app):
            pass
        redactors = [f for f in access_logger.filters if isinstance(f, AccessLogRedactor)]
        assert len(redactors) == 1


# ---------------------------------------------------------------------------------------------
# Milestone 12.5: the default language and the catalogues (research R1, R5, R6)
# ---------------------------------------------------------------------------------------------


def test_the_language_middleware_is_registered() -> None:
    assert any(m.cls is LanguageMiddleware for m in app.user_middleware)


def test_an_unknown_default_language_stops_the_start(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DEFAULT_LANGUAGE", "fr")
    with pytest.raises(config.LanguageConfigError) as caught, TestClient(app):
        pass
    assert "DEFAULT_LANGUAGE" in str(caught.value)
    assert "fr" not in str(caught.value)
    assert _boots(database_url) == 0


def test_an_unset_default_language_is_ukrainian(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("DEFAULT_LANGUAGE")
    with TestClient(app):
        assert app.state.default_language is Language.UK


def test_uncompiled_translations_stop_the_start(
    monkeypatch: pytest.MonkeyPatch, database_url: str, tmp_path: Path
) -> None:
    """`load_translations` keeps what it loaded, so the cache is emptied too: otherwise an earlier
    load would hide the missing files."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(i18n, "LOCALE_DIR", tmp_path)
    monkeypatch.setattr(i18n, "_TRANSLATIONS", {})
    with pytest.raises(i18n.TranslationsNotCompiled) as caught, TestClient(app):
        pass
    assert str(caught.value) == "Translations are not compiled: run scripts/translations.sh compile"
    assert _boots(database_url) == 0
