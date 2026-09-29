"""Sign-in and sign-out: the two-step email-code login and logout. Thin handlers only.

See specs/004-email-otp-auth/contracts/http-routes.md. Plain HTML forms with full-page
responses (no HTMX, no JavaScript). Step 1 renders step 2 directly rather than redirecting, so
the address travels in a hidden field instead of a URL, where access logs would record it
(research D11). The code is issued and emailed by a background task after the response, so the
response is the same whoever the address belongs to (research D10).

Sync handlers: the database calls block, so FastAPI runs them in its thread pool. Every database
failure renders a friendly 503 on the same page and is logged by exception type only. No
handler logs an address, a code, a token or a cookie.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import clear_session_cookie, set_session_cookie
from app.core.config import APP_NAME, AuthSettings
from app.core.db import SessionDep
from app.core.security import (
    SESSION_COOKIE_NAME,
    client_address,
    safe_next_path,
    unsign_cookie_value,
)
from app.core.templates import templates
from app.schemas.auth import CodeSubmission, EmailSubmission
from app.services.login import deliver_login_code, verify_code
from app.services.rate_limits import allow_code_request
from app.services.sessions import create_session, delete_session

router = APIRouter()

logger = logging.getLogger("uvicorn.error")

INVALID_EMAIL = "Enter a valid email address."
INVALID_CODE = "Invalid or expired code. Request a new code if needed."
UNAVAILABLE = "Sign-in is temporarily unavailable. Please try again in a moment."
TOO_MANY = "Too many attempts. Please try again later."

STEP_ONE = "pages/login.html"
STEP_TWO = "pages/login_code.html"


def _page(
    request: Request,
    template: str,
    *,
    email: str = "",
    next_path: str = "/",
    message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        {"app_name": APP_NAME, "email": email, "next": next_path, "message": message},
        status_code=status_code,
    )


def _settings(request: Request) -> AuthSettings:
    return request.app.state.settings


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next_path: str = Query("/", alias="next")) -> Response:
    """Step 1: the email form; a signed-in user is sent straight on to `next` (FR-031)."""
    next_path = safe_next_path(next_path)
    if request.state.user is not None:
        return RedirectResponse(next_path, status_code=303)
    return _page(request, STEP_ONE, next_path=next_path)


@router.post("/login", response_class=HTMLResponse)
def request_code(
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    email: str = Form(""),
    next_path: str = Form("/", alias="next"),
) -> Response:
    """Step 1 submitted (or "Send a new code"): check the limits, schedule the code, show step 2.

    For every well-formed address the in-request work is the same queries in the same order, and
    the limit applies to every address alike (FR-017, FR-020); whether a code is issued and sent
    is decided after the response, in `deliver_login_code`. A malformed address is refused before
    any query and is not counted.
    """
    next_path = safe_next_path(next_path)
    try:
        submission = EmailSubmission(email=email, next=next_path)
    except ValidationError:
        return _page(
            request,
            STEP_ONE,
            email=email,
            next_path=next_path,
            message=INVALID_EMAIL,
            status_code=400,
        )
    settings = _settings(request)
    try:
        allowed = allow_code_request(
            session,
            settings.secret_key,
            submission.email,
            client_address(request, trust_forwarded=settings.production),
        )
    except SQLAlchemyError as exc:
        logger.error("Sign-in unavailable: %s", type(exc).__name__)
        return _page(
            request,
            STEP_ONE,
            email=submission.email,
            next_path=next_path,
            message=UNAVAILABLE,
            status_code=503,
        )
    if not allowed:
        return _page(
            request,
            STEP_ONE,
            email=submission.email,
            next_path=next_path,
            message=TOO_MANY,
            status_code=429,
        )
    background_tasks.add_task(
        deliver_login_code,
        request.app.state.engine,
        request.app.state.email_sender,
        settings,
        submission.email,
    )
    return _page(request, STEP_TWO, email=submission.email, next_path=next_path)


@router.post("/login/code", response_class=HTMLResponse)
def submit_code(
    request: Request,
    session: SessionDep,
    email: str = Form(""),
    code: str = Form(""),
    next_path: str = Form("/", alias="next"),
) -> Response:
    """Step 2 submitted: a correct code starts a session and returns to the page asked for.

    Every failure (wrong, expired, used or exhausted code, unknown or inactive address, a lost
    double-submit race) gets the same message, so it reveals nothing (FR-013).
    """
    next_path = safe_next_path(next_path)
    try:
        submission = CodeSubmission(email=email, code=code, next=next_path)
    except ValidationError:
        return _page(
            request,
            STEP_TWO,
            email=email,
            next_path=next_path,
            message=INVALID_CODE,
            status_code=400,
        )
    settings = _settings(request)
    try:
        user = verify_code(session, settings.secret_key, submission.email, submission.code)
        token = create_session(session, user) if user is not None else None
    except SQLAlchemyError as exc:
        logger.error("Sign-in unavailable: %s", type(exc).__name__)
        return _page(
            request,
            STEP_TWO,
            email=submission.email,
            next_path=next_path,
            message=UNAVAILABLE,
            status_code=503,
        )
    if token is None:
        return _page(
            request,
            STEP_TWO,
            email=submission.email,
            next_path=next_path,
            message=INVALID_CODE,
            status_code=400,
        )
    response = RedirectResponse(next_path, status_code=303)
    set_session_cookie(response, settings, token)
    return response


@router.post("/logout")
def logout(request: Request, session: SessionDep) -> Response:
    """End this browser's session, if any, and clear its cookie. Harmless when signed out."""
    settings = _settings(request)
    value = request.cookies.get(SESSION_COOKIE_NAME)
    token = unsign_cookie_value(settings.secret_key, value) if value else None
    if token is not None:
        try:
            delete_session(session, token)
        except SQLAlchemyError as exc:
            # Keep the cookie: clearing it would look like a logout while the session lives on.
            logger.error("Sign-out unavailable: %s", type(exc).__name__)
            return _page(request, STEP_ONE, message=UNAVAILABLE, status_code=503)
    response = RedirectResponse("/login", status_code=303)
    clear_session_cookie(response, settings)
    return response
