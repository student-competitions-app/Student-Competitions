"""FastAPI application construction: startup, static mount, router registration, error handling.

Startup needs a database at the schema this code expects and valid sign-in settings. The
`lifespan` runs, in this order (specs/004-email-otp-auth/contracts/configuration.md, FR-043):

    resolve_database_url → resolve_auth_settings → create engine → ensure_at_head
      → reconcile_admins (one retry) → purge_expired → record_boot

Both settings checks come before any database connection, so a refused start never touches the
data and is never counted. Only then does uvicorn open the port, so an instance that answers
`/healthz` at all has a usable database and a safe configuration. On Render that makes a
misconfigured or unmigrated release fail its deploy while the previous one keeps serving.
Migrations themselves are applied by the container entrypoint, not here.

Every route runs `resolve_access` first (registered application-wide below), which resolves the
signed-in user from the session cookie.

Paths are anchored to this package rather than to the working directory, so the application
serves the same files wherever it is started from (FR-011, research D14).
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from starlette.exceptions import HTTPException

from app.core.auth import LoginRequired, resolve_access
from app.core.config import (
    APP_DESCRIPTION,
    APP_NAME,
    resolve_auth_settings,
    resolve_database_url,
)
from app.core.db import create_db_engine
from app.core.migrations import ensure_at_head
from app.core.templates import templates
from app.routers import auth, health, pages
from app.services.database_status import record_boot
from app.services.email import build_email_sender
from app.services.login import purge_expired
from app.services.users import ReconcileResult, reconcile_admins

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Uvicorn's general-purpose logger (the name is historical), configured at INFO, so the startup
# line appears next to uvicorn's own "Application startup complete".
logger = logging.getLogger("uvicorn.error")


def reconcile_admins_with_retry(engine: Engine, emails: tuple[str, ...]) -> ReconcileResult:
    """Reconcile the administrators, retrying once if another instance got there first.

    The only conflict possible is a second instance, started at the same moment, inserting the
    same new address: the unique constraint rejects one of the two inserts. The retry then sees
    that row and counts it as unchanged, reaching the same end state. A second failure
    propagates, and the start is refused (FR-005, research D13).
    """
    with Session(engine) as session:
        try:
            return reconcile_admins(session, emails)
        except IntegrityError:
            session.rollback()
            return reconcile_admins(session, emails)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate the settings, connect, refuse to start unless at head, reconcile the
    administrators, clean up expired sign-in data, and count this start.

    Any failure propagates: uvicorn exits non-zero before binding the port, so a start that was
    refused is never counted. The log lines name the engine, the revision, the boot number and
    counts only — never the URL, a setting's value or an address.
    """
    database_url = resolve_database_url(os.environ)
    settings = resolve_auth_settings(os.environ)
    engine = create_db_engine(database_url)
    try:
        revision = ensure_at_head(engine)
        reconciled = reconcile_admins_with_retry(engine, settings.admin_emails)
        logger.info(
            "Administrators reconciled: %d created, %d reactivated, %d deactivated, %d unchanged",
            reconciled.created,
            reconciled.reactivated,
            reconciled.deactivated,
            reconciled.unchanged,
        )
        with Session(engine) as session:
            purge_expired(session)
            boots = record_boot(session)
        app.state.engine = engine
        app.state.settings = settings
        app.state.email_sender = build_email_sender(settings)
        logger.info(
            "Database: %s at schema revision %s, boot #%d", engine.dialect.name, revision, boots
        )
        yield
    finally:
        engine.dispose()


# The access dependency is given here, at construction, because an included router captures the
# application's dependencies when it is included: set later, it would miss every router.
#
# The built-in API docs (`/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`) are switched
# off: they are plain Starlette routes that application-wide dependencies do not cover, so leaving
# them on would publish routes outside the allowlist (FR-028).
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    dependencies=[Depends(resolve_access)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages.router)
app.include_router(health.router)
app.include_router(auth.router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired) -> RedirectResponse:
    """An anonymous request for a private page: 303, so the browser follows with a `GET`."""
    return RedirectResponse(exc.location, status_code=303)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse:
    """Render a friendly page for any HTTP error, never a stack trace or raw JSON.

    Registered for `HTTPException` in general rather than only 404, so routes added in later
    milestones inherit the same page.
    """
    return templates.TemplateResponse(
        request,
        "pages/error.html",
        {
            "app_name": APP_NAME,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
        status_code=exc.status_code,
    )
