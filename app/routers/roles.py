"""Choosing and switching the current role: `GET /role` and `POST /role`. Thin handlers only.

See specs/005-roles-authorization/contracts/http-routes.md#get-role--the-role-choice and research
D6. Choosing (after sign-in) and switching (from the header) are the same state change, so they
share one route: the role choice carries a `next` and lands there, the header switch carries none
and lands on `/`. Only `POST` changes anything (FR-020), only to a role the person holds, and
only for this browser's session (FR-011). Both routes are in `ROLE_CHOICE_ROUTES`: open to anyone
signed in, with or without a current role.

Sync handlers: the database call blocks, so FastAPI runs them in its thread pool. A database
failure renders a friendly 503 and is logged by exception type only. Nothing here logs an
address, a role choice or a token.
"""

import logging

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import session_token
from app.core.config import APP_NAME
from app.core.db import SessionDep
from app.core.security import safe_next_path
from app.core.templates import templates
from app.models import Role
from app.services.sessions import set_current_role

router = APIRouter()

logger = logging.getLogger("uvicorn.error")

CHOOSE_ONE = "Choose one of your roles."
UNAVAILABLE = "Choosing a role is temporarily unavailable. Please try again in a moment."


def _page(
    request: Request, next_path: str | None, message: str | None = None, status_code: int = 200
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/role_choice.html",
        {
            "app_name": APP_NAME,
            "roles": request.state.roles,
            "next": next_path,
            "message": message,
        },
        status_code=status_code,
    )


def _safe_next(value: str | None) -> str | None:
    """The sanitised return address, or `None` when none was given."""
    return safe_next_path(value) if value else None


@router.get("/role", response_class=HTMLResponse)
def role_choice(request: Request, next_path: str | None = Query(None, alias="next")) -> Response:
    """The role choice: one button per role held, in the fixed order. A person with one role has
    nothing to choose and goes to the home page (FR-016)."""
    held: tuple[Role, ...] = request.state.roles
    if len(held) == 1:
        return RedirectResponse("/", status_code=303)
    return _page(request, _safe_next(next_path))


@router.post("/role", response_class=HTMLResponse)
def choose_role(
    request: Request,
    session: SessionDep,
    role: str = Form(""),
    next_path: str | None = Form(None, alias="next"),
) -> Response:
    """Make `role` this browser's current role and go to `next`, or `/` without one.

    A missing, unknown or not-held role changes nothing and shows the role choice again with a
    400 (US3-5, US4-6). The landing page is never adjusted to the new role: if it may not open
    it, the person gets the access denied page there.
    """
    next_path = _safe_next(next_path)
    held: tuple[Role, ...] = request.state.roles
    chosen = next((candidate for candidate in held if candidate == role), None)
    token = session_token(request)
    if chosen is None or token is None:
        return _page(request, next_path, message=CHOOSE_ONE, status_code=400)
    try:
        set_current_role(session, token, chosen)
    except SQLAlchemyError as exc:
        logger.error("Role change unavailable: %s", type(exc).__name__)
        return _page(request, next_path, message=UNAVAILABLE, status_code=503)
    return RedirectResponse(next_path or "/", status_code=303)
