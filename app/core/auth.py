"""Access control: deny by default — every route declares the roles that may open it.

`resolve_access` is registered as an application-wide dependency in `app.main`, so FastAPI runs
it before every route the application has or will ever include. It reads the signed `sc_session`
cookie, puts the signed-in user, their roles and their current role on `request.state`, and then
decides, in one fixed order, whether the request is served, sent to sign in, sent to choose a
role, or denied. See specs/005-roles-authorization/research.md#d4 and #d5, and
specs/005-roles-authorization/contracts/http-routes.md#access-rule-applies-to-every-route.

Access follows the role the session is **currently** using, never the union of the roles held
(FR-022). Protection is structural: a route that declares no roles is denied to everyone signed
in, so forgetting the declaration fails closed, and the route-table sweep in
`tests/integration/test_routes.py` fails the build naming it.

**Adding a route**: decorate its handler with `@allow_roles(Role.X, ...)`, naming every role whose
current role may open it, or, for a page anyone may open signed out, add it to `PUBLIC_ROUTES` in
a reviewed change. There is no third option: an undeclared route is denied to everyone at runtime
and fails `test_routes.py`.

`GET /healthz` is skipped entirely: Render's health check must stay free of I/O (milestone 2),
with or without a cookie.

Nothing here logs a cookie value, a token, a hash, an address or a user id.
"""

import logging
from collections.abc import Callable
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.config import AuthSettings
from app.core.security import (
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    is_cross_site,
    sign_cookie_value,
    unsign_cookie_value,
)
from app.models import Role, User
from app.services.sessions import SessionIdentity, get_session_identity

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
"""The complete allowlist of `(method, path)` pairs served to anonymous visitors, and to anyone
signed in whatever their role. `HEAD` is treated as `GET`. The `/static` mount is not a route and
is always public. Adding a route here is a reviewed change."""

ROLE_CHOICE_ROUTES: frozenset[tuple[str, str]] = frozenset({("GET", "/role"), ("POST", "/role")})
"""Open to anyone signed in, with or without a current role: choosing one must be possible before
one is chosen (FR-014, FR-022)."""


def allow_roles[F: Callable[..., Any]](*roles: Role) -> Callable[[F], F]:
    """Declare the roles whose current role may open the decorated route.

    Records a non-empty `frozenset[Role]` as `endpoint.allowed_roles` and returns the function
    unchanged, so it works above or below the route decorator (both see the same function
    object). Raises at import time when given no roles, or anything that is not a `Role`.

    Every route outside `PUBLIC_ROUTES` and `ROLE_CHOICE_ROUTES` must carry it: an undeclared
    route is denied to everyone at runtime and fails `tests/integration/test_routes.py`.
    """
    if not roles:
        raise ValueError("allow_roles needs at least one role; a page nobody may open is a bug")
    for role in roles:
        if not isinstance(role, Role):
            raise TypeError(f"allow_roles takes Role members, not {type(role).__name__}")
    allowed = frozenset(roles)

    def mark(endpoint: F) -> F:
        endpoint.allowed_roles = allowed  # type: ignore[attr-defined]
        return endpoint

    return mark


def declared_roles(endpoint: Callable[..., Any]) -> frozenset[Role] | None:
    """The roles `endpoint` declared with `allow_roles`, or `None` when it declared none."""
    return getattr(endpoint, "allowed_roles", None) or None


class LoginRequired(Exception):
    """An anonymous request for a private route; answered with a 303 to `location`."""

    def __init__(self, location: str) -> None:
        super().__init__(location)
        self.location = location


class RoleChoiceRequired(Exception):
    """A signed-in person with several roles who has not chosen one yet; answered with a 303 to
    `location`, the role choice (FR-014)."""

    def __init__(self, location: str) -> None:
        super().__init__(location)
        self.location = location


class CrossSiteRequest(Exception):
    """An unsafe-method request from another site; answered with the 403 "Request refused" page
    before the session is even read, so nothing is changed (FR-021, research D7)."""


class AccessDenied(Exception):
    """The current role may not open this route; answered with the 403 "Access denied" page,
    which names the current role and nothing about the page (FR-025)."""

    def __init__(self, current_role: Role) -> None:
        super().__init__(current_role.value)
        self.current_role = current_role


def _return_target(request: Request) -> str:
    """This page's path and query, percent-encoded for a `next` parameter."""
    target = request.url.path
    if request.url.query:
        target += "?" + request.url.query
    return quote(target, safe="")


def _login_location(request: Request) -> str:
    """`/login?next=<this page>` for a page view; plain `/login` for anything else, since a
    return address is only useful for something a browser can open again (FR-029)."""
    if request.method not in {"GET", "HEAD"}:
        return "/login"
    return f"/login?next={_return_target(request)}"


def _role_choice_location(request: Request) -> str:
    """`/role?next=<this page>` for a page view; plain `/role` for anything else (FR-014)."""
    if request.method not in {"GET", "HEAD"}:
        return "/role"
    return f"/role?next={_return_target(request)}"


def _route_path(request: Request) -> str | None:
    """The matched route's path template (e.g. `/login`), not the requested URL."""
    route = request.scope.get("route")
    return getattr(route, "path", None)


def resolve_access(request: Request) -> None:
    """Resolve who is asking into `request.state`, then apply the access rules, first match wins:

    1. `GET /healthz`: served, with no session lookup;
    2. a method other than `GET`, `HEAD` or `OPTIONS` judged cross-site (`is_cross_site`):
       `CrossSiteRequest`, before any database access;
    3. anonymous, route in `PUBLIC_ROUTES`: served;
    4. anonymous, any other route: `LoginRequired`;
    5. signed in, route in `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES`: served;
    6. signed in, no current role: `RoleChoiceRequired`;
    7. signed in, current role among the route's declared roles: served;
    8. anything else, including a route that declares no roles: `AccessDenied` (FR-024).

    Authorization runs only after authentication, so an anonymous visitor is never told "access
    denied" (FR-023). A path that matches no route never reaches this dependency, so it keeps the
    friendly 404 for everyone.

    Sync on purpose: FastAPI runs it in the thread pool, so the blocking session lookup never
    stalls the event loop. A cookie with a bad signature is rejected before any database access.
    A database error during the lookup leaves the request anonymous rather than failing it.
    """
    method = "GET" if request.method == "HEAD" else request.method
    route = (method, _route_path(request))
    if route == ("GET", HEALTH_PATH):
        return
    if is_cross_site(request.method, request.headers):
        raise CrossSiteRequest()
    identity = _identity_from_cookie(request)
    request.state.user = identity.user if identity else None
    request.state.roles = identity.roles if identity else ()
    request.state.current_role = identity.current_role if identity else None
    if identity is None:
        if route in PUBLIC_ROUTES:
            return
        raise LoginRequired(_login_location(request))
    if route in PUBLIC_ROUTES or route in ROLE_CHOICE_ROUTES:
        return
    current_role = identity.current_role
    if current_role is None:
        raise RoleChoiceRequired(_role_choice_location(request))
    allowed = declared_roles(request.scope["route"].endpoint) or frozenset()
    if current_role in allowed:
        return
    logger.info("Access denied: role=%s route=%s", current_role.value, route[1])
    raise AccessDenied(current_role)


def session_token(request: Request) -> str | None:
    """The token in this request's correctly signed session cookie, or `None`. No database
    access: whether the session exists is for the caller to find out."""
    value = request.cookies.get(SESSION_COOKIE_NAME)
    if not value:
        return None
    settings: AuthSettings = request.app.state.settings
    return unsign_cookie_value(settings.secret_key, value)


def _identity_from_cookie(request: Request) -> SessionIdentity | None:
    token = session_token(request)
    if token is None:
        return None
    try:
        with Session(request.app.state.engine) as session:
            return get_session_identity(session, token)
    except SQLAlchemyError as exc:
        logger.error("Session lookup failed: %s", type(exc).__name__)
        return None


def get_current_user(request: Request) -> User | None:
    """The user `resolve_access` found for this request, or `None`."""
    return getattr(request.state, "user", None)


CurrentUser = Annotated[User | None, Depends(get_current_user)]
"""The signed-in user, for a handler's signature."""


def get_current_role(request: Request) -> Role | None:
    """The role this request's session is currently using, or `None`."""
    return getattr(request.state, "current_role", None)


CurrentRole = Annotated[Role | None, Depends(get_current_role)]
"""The current role, for a handler's signature."""


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
