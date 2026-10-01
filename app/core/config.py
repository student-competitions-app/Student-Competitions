"""Application constants and configuration read from the environment.

Single source of truth for the name, tagline and description that appear on the page, in the
browser tab and in the test assertions — those are literals.

This module is the only place that reads the environment, for three things:

- `COMMIT_SHA` answers "which commit is live" (FR-025), resolved once at import time. See
  specs/002-public-deploy-cicd/data-model.md#1-configuration-read-from-the-environment.
- `resolve_database_url` decides where the database is, for both the application's startup and
  `migrations/env.py`, so the two always target the same database. It is a function rather than a
  constant because it creates the local data directory and may refuse to run. See
  specs/003-database-questions/contracts/configuration.md.
- `resolve_auth_settings` reads and validates the sign-in settings (email backend, secret key,
  the three role lists, Resend key and sender), refusing an unsafe production setup. See
  specs/004-email-otp-auth/contracts/configuration.md and
  specs/005-roles-authorization/contracts/configuration.md.

No error, warning or `repr` produced here ever contains a setting's value: in production those
values are secrets, and these messages reach the deploy log.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Literal, cast

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.core.security import MIN_SECRET_KEY_LENGTH, is_valid_email, normalize_email

APP_NAME = "Student Competitions"

APP_TAGLINE = "Online knowledge competitions for students."

APP_DESCRIPTION = (
    "Student Competitions is a web application for running online knowledge competitions in "
    "schools and universities. Teachers build a question bank and open a competition, students "
    "answer the questions in writing, and every answer is scored automatically."
)

APP_VERSION = "0.1.0"
"""The release number reported by `/healthz`. Equals `project.version` in `pyproject.toml`,
which `tests/unit/test_config.py` asserts."""

COMMIT_SHA = os.environ.get("APP_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "unknown"
"""The commit the running instance was built from.

`APP_COMMIT` (a local or CI `docker build --build-arg`) wins, then `RENDER_GIT_COMMIT` (set
automatically by Render for every deploy), then the literal `"unknown"`. `or` rather than a
default argument is deliberate: the Dockerfile declares `ARG APP_COMMIT=""`, so an unstamped
build sets the variable to an empty string, and empty must fall through rather than win.
"""


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
"""The directory that contains the `app` package: the repository root locally, `/app` in the
image. Anchored to the package rather than to the working directory, like the templates."""

DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "student_competitions.sqlite3"
"""The local database used when `DATABASE_URL` is not set and the app is not on Render (FR-002).
`data/` is git-ignored and excluded from the image's build context."""

SUPPORTED_SCHEMES = frozenset({"sqlite", "postgres", "postgresql", "postgresql+psycopg"})

POSTGRESQL_DRIVER = "postgresql+psycopg"
"""The one PostgreSQL driver installed (psycopg 3). Neon and CI hand out `postgresql://` URLs,
which SQLAlchemy would otherwise map to psycopg2, so they are rewritten to name it explicitly."""


class DatabaseConfigError(RuntimeError):
    """The database location is missing or unusable, so the application must not start.

    Its message never contains the URL or any part of it: the URL is a secret in production, and
    this message reaches the deploy log (FR-004, FR-032).
    """


def resolve_database_url(environ: Mapping[str, str] = os.environ) -> str:
    """Return the SQLAlchemy URL of the database, or raise `DatabaseConfigError`.

    First match wins:

    1. `DATABASE_URL` is set and non-empty: its scheme is checked, and `postgres://` or
       `postgresql://` is rewritten to `postgresql+psycopg://` with every other part preserved.
    2. `RENDER` is set: refuse. A production start without its database must fail the release,
       not silently serve from a throw-away file inside the container (FR-004).
    3. Otherwise the local SQLite file under `data/`, which is created if missing (FR-002).

    The guard keys on `RENDER` because Render is the recorded host. Moving to another host means
    adding that platform's always-set variable (for example `RAILWAY_ENVIRONMENT` or
    `FLY_APP_NAME`) to the guard, in the same pull request as the move.
    """
    raw = environ.get("DATABASE_URL", "")
    if raw:
        return _normalise(raw)
    if environ.get("RENDER"):
        raise DatabaseConfigError(
            "DATABASE_URL is required when running on Render; "
            "refusing to fall back to a local SQLite file."
        )
    DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def _normalise(raw: str) -> str:
    """Check the scheme of a configured URL and name the psycopg driver explicitly.

    Only the scheme is rewritten, as a string prefix: re-rendering the parsed URL would reorder
    the query string and re-quote the password, and the contract is that everything after the
    scheme is preserved exactly.

    Errors are raised `from None`: SQLAlchemy's own parse error quotes the URL, and chaining it
    would print the password in the traceback.
    """
    try:
        url = make_url(raw)
    except (ArgumentError, ValueError):
        raise DatabaseConfigError("DATABASE_URL is not a valid database URL.") from None
    scheme = url.drivername
    if scheme not in SUPPORTED_SCHEMES:
        raise DatabaseConfigError(
            f"DATABASE_URL uses unsupported scheme '{scheme}'; expected sqlite or postgresql."
        ) from None
    if scheme in {"postgres", "postgresql"}:
        return POSTGRESQL_DRIVER + raw[len(scheme) :]
    return raw


# ---------------------------------------------------------------------------------------------
# Authentication settings (milestone 4)
# ---------------------------------------------------------------------------------------------

EmailBackend = Literal["console", "memory", "resend"]

EMAIL_BACKENDS: tuple[EmailBackend, ...] = ("console", "memory", "resend")

DEV_SECRET_KEY = "insecure-development-only-secret-key-never-use-in-production"
"""The key used locally when `SECRET_KEY` is unset. A constant, so local sessions survive
`--reload` and container restarts (the CI image job relies on that). It can never reach
production: on Render `SECRET_KEY` is required."""

# Uvicorn's general-purpose logger, the one that is configured to print under uvicorn.
_logger = logging.getLogger("uvicorn.error")


class AuthConfigError(RuntimeError):
    """The sign-in settings are unusable, so the application must not start.

    The message lists every problem by setting name, never by value (FR-041, SC-008).
    """


@dataclass(frozen=True)
class AuthSettings:
    """The validated sign-in settings, stored on `app.state.settings`."""

    production: bool
    """`RENDER` is set: the refusal rules apply, the cookie is `Secure`, and `X-Forwarded-For`
    is trusted for the per-client limit."""
    email_backend: EmailBackend
    secret_key: str
    admin_emails: tuple[str, ...]
    """Normalised, de-duplicated and sorted, like the two lists below."""
    resend_api_key: str | None
    email_from: str | None
    teacher_emails: tuple[str, ...] = ()
    """Temporary until milestone 7, which manages teachers in the application."""
    student_emails: tuple[str, ...] = ()
    """Temporary until milestone 7, as above."""

    def __repr__(self) -> str:
        # Masks every value that is a secret in production, so an accidental log line or
        # traceback cannot print one.
        return (
            f"AuthSettings(production={self.production}, "
            f"email_backend={self.email_backend!r}, secret_key='***', "
            f"admin_emails=<{len(self.admin_emails)} addresses>, "
            f"teacher_emails=<{len(self.teacher_emails)} addresses>, "
            f"student_emails=<{len(self.student_emails)} addresses>, "
            f"resend_api_key={'***' if self.resend_api_key else None}, "
            f"email_from={'***' if self.email_from else None})"
        )

    __str__ = __repr__


def _entries(raw: str | None) -> list[str]:
    """The non-empty entries of a comma-separated list, as written."""
    return [entry for entry in (raw or "").split(",") if entry.strip()]


def _parse_email_list(name: str, raw: str | None, errors: list[str]) -> tuple[str, ...]:
    """One comma-separated address list, the same way for all three role lists.

    Entries are trimmed and lowercased, empty entries are ignored, duplicates collapse, and the
    result is sorted. Each malformed entry adds one error naming the list and its 1-based position
    among the non-empty entries, never the value (FR-035).
    """
    addresses: set[str] = set()
    for position, entry in enumerate(_entries(raw), start=1):
        address = normalize_email(entry)
        if is_valid_email(address):
            addresses.add(address)
        else:
            errors.append(f"{name} entry {position} is not a valid email address.")
    return tuple(sorted(addresses))


def resolve_auth_settings(environ: Mapping[str, str] = os.environ) -> AuthSettings:
    """Read and validate the sign-in settings, or raise one `AuthConfigError` listing them all.

    Rules C1–C10 and warnings W1–W4 of specs/004-email-otp-auth/contracts/configuration.md and
    specs/005-roles-authorization/contracts/configuration.md, in that order. Empty strings count
    as unset. On Render every setting is required and the email must really be sent, except
    `TEACHER_EMAILS` and `STUDENT_EMAILS`, which are optional everywhere; locally every setting is
    optional, but a value that is present and invalid is still refused, so a typo fails fast
    instead of silently falling back.
    """

    def read(name: str) -> str | None:
        return environ.get(name) or None

    production = bool(read("RENDER"))
    backend_raw = read("EMAIL_BACKEND")
    secret_key = read("SECRET_KEY")
    resend_api_key = read("RESEND_API_KEY")
    email_from = read("EMAIL_FROM")
    admin_raw = read("ADMIN_EMAILS")

    errors: list[str] = []
    if backend_raw is not None and backend_raw not in EMAIL_BACKENDS:
        errors.append("EMAIL_BACKEND must be one of console, memory, resend.")
    if production and backend_raw in (None, "console", "memory"):
        errors.append("EMAIL_BACKEND must be 'resend' when running on Render.")
    if production and secret_key is None:
        errors.append("SECRET_KEY is required when running on Render.")
    if secret_key is not None and len(secret_key) < MIN_SECRET_KEY_LENGTH:
        errors.append(f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters long.")
    if production and not _entries(admin_raw):
        errors.append("ADMIN_EMAILS must list at least one address when running on Render.")
    admin_emails = _parse_email_list("ADMIN_EMAILS", admin_raw, errors)
    needs_resend = production or backend_raw == "resend"
    if needs_resend and resend_api_key is None:
        errors.append("RESEND_API_KEY is required for the resend email backend.")
    if needs_resend and (email_from is None or not is_valid_email(parseaddr(email_from)[1])):
        errors.append(
            "EMAIL_FROM is required for the resend email backend and must be a valid sender "
            "address."
        )
    teacher_emails = _parse_email_list("TEACHER_EMAILS", read("TEACHER_EMAILS"), errors)
    student_emails = _parse_email_list("STUDENT_EMAILS", read("STUDENT_EMAILS"), errors)
    if errors:
        raise AuthConfigError(
            "Invalid authentication configuration:\n" + "\n".join(f"- {e}" for e in errors)
        )

    if not production:
        if secret_key is None:
            _logger.warning(
                "SECRET_KEY is not set; using an insecure development key. "
                "Never do this in production."
            )
        if backend_raw is None:
            _logger.warning(
                "EMAIL_BACKEND is not set; login emails will be printed to this console."
            )
        if not (admin_emails or teacher_emails or student_emails):
            _logger.warning("No role lists are set; nobody will be able to sign in.")
        elif not admin_emails:
            _logger.warning(
                "ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator."
            )

    return AuthSettings(
        production=production,
        email_backend=cast(EmailBackend, backend_raw or "console"),
        secret_key=secret_key or DEV_SECRET_KEY,
        admin_emails=admin_emails,
        resend_api_key=resend_api_key,
        email_from=email_from,
        teacher_emails=teacher_emails,
        student_emails=student_emails,
    )
