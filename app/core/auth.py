"""Access control: every route is private unless it is listed in `PUBLIC_ROUTES`.

`resolve_access` is registered as an application-wide dependency in `app.main`, so FastAPI runs
it before every route the application has or will ever include. It reads the signed `sc_session`
cookie, puts the signed-in user, or `None`, on `request.state.user`, and turns an anonymous
request for any route outside the allowlist into `LoginRequired`, which `app.main` answers with a
303 to the login page. See specs/004-email-otp-auth/research.md#d3 and #d4.

Protection is structural: a route added later, in any router, is private without anyone having
to remember it. Making a route public is a one-line, reviewed change to `PUBLIC_ROUTES`, and the
route-table sweep in `tests/integration/test_routes.py` fails the build if the allowlist and the
routes disagree.

`GET /healthz` is skipped entirely: Render's health check must stay free of I/O (milestone 2),
with or without a cookie.

Nothing here logs a cookie value, a token or a hash.
"""

import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.config import AuthSettings
from app.core.security import (
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    sign_cookie_value,
    unsign_cookie_value,
)
from app.models import User
from app.services.sessions import get_session_user

logger = logging.getLogger("uvicorn.error")

HEALTH_PATH = "/healthz"

PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/login"),
        ("POST", "/login"),
        ("POST", "/login/code"),
        ("POST", "/logout"),
        ("GET", HEALTH_PATH),
    }
)
"""The complete allowlist of `(method, path)` pairs served to anonymous visitors (FR-028).
`HEAD` is treated as `GET`. The `/static` mount is not a route and is always public."""


class LoginRequired(Exception):
    """An anonymous request for a private route; answered with a 303 to `location`."""

    def __init__(self, location: str) -> None:
        super().__init__(location)
        self.location = location


def _login_location(request: Request) -> str:
    """`/login?next=<this page>` for a page view; plain `/login` for anything else, since a
    return address is only useful for something a browser can open again (FR-029)."""
    if request.method not in {"GET", "HEAD"}:
        return "/login"
    target = request.url.path
    if request.url.query:
        target += "?" + request.url.query
    return f"/login?next={quote(target, safe='')}"


def _route_path(request: Request) -> str | None:
    """The matched route's path template (e.g. `/login`), not the requested URL."""
    route = request.scope.get("route")
    return getattr(route, "path", None)


def resolve_access(request: Request) -> None:
    """Resolve the signed-in user into `request.state.user`, and refuse anonymous requests for
    any route outside `PUBLIC_ROUTES` by raising `LoginRequired`.

    Sync on purpose: FastAPI runs it in the thread pool, so the blocking session lookup never
    stalls the event loop. A cookie with a bad signature is rejected before any database access.
    A database error during the lookup leaves the request anonymous rather than failing it.
    """
    method = "GET" if request.method == "HEAD" else request.method
    route = (method, _route_path(request))
    if route == ("GET", HEALTH_PATH):
        return
    request.state.user = _user_from_cookie(request)
    if request.state.user is None and route not in PUBLIC_ROUTES:
        raise LoginRequired(_login_location(request))


def _user_from_cookie(request: Request) -> User | None:
    value = request.cookies.get(SESSION_COOKIE_NAME)
    if not value:
        return None
    settings: AuthSettings = request.app.state.settings
    token = unsign_cookie_value(settings.secret_key, value)
    if token is None:
        return None
    try:
        with Session(request.app.state.engine) as session:
            return get_session_user(session, token)
    except SQLAlchemyError as exc:
        logger.error("Session lookup failed: %s", type(exc).__name__)
        return None


def get_current_user(request: Request) -> User | None:
    """The user `resolve_access` found for this request, or `None`."""
    return getattr(request.state, "user", None)


CurrentUser = Annotated[User | None, Depends(get_current_user)]
"""The signed-in user, for a handler's signature. Milestone 5 builds role checks on it."""


def set_session_cookie(response: Response, settings: AuthSettings, token: str) -> None:
    """Attach the signed session cookie for `token`: 14 days, whole site, not readable by
    scripts, not sent on cross-site posts, and HTTPS-only in production (FR-024)."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sign_cookie_value(settings.secret_key, token),
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.production,
    )


def clear_session_cookie(response: Response, settings: AuthSettings) -> None:
    """Remove the session cookie, with the same name, path and flags it was set with."""
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.production,
    )
