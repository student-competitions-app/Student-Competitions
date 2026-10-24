"""`POST /theme`: choose Light, Dark or Device (specs/010-design-system-ui-guidelines research D6,
contracts/http-routes.md §1).

A small form in the user menu and on the sign-in page posts here; no JavaScript is involved. The
route is public, because the switch works signed out and for every role, and it goes through the
application-wide cross-site check like every other `POST`. It reads and writes no data: it sets
or deletes the browser's `sc_theme` cookie and returns the browser where it was.

The return address is checked twice: by `safe_return_path`, which refuses anything that is not a
plain local path (and the `POST`-only sign-in steps), and against the route table, so a page that
was only ever shown by a `POST` (a form after an error) never becomes a 405. Anything refused
returns to `/` signed in, or to `/login` signed out.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.routing import Match

from app.core.security import safe_return_path
from app.core.theme import apply_theme, parse_theme

router = APIRouter()


def _has_get_page(request: Request, path: str) -> bool:
    """Whether a `GET` request for `path` would reach a page: the routes are asked exactly as
    they are when a request arrives, so included routers and their prefixes are covered."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "root_path": "",
        "headers": [],
        "query_string": b"",
        "app": request.app,
    }
    return any(route.matches(scope)[0] == Match.FULL for route in request.app.router.routes)


@router.post("/theme")
def choose_theme(
    request: Request, theme: str = Form(""), next_path: str = Form("", alias="next")
) -> RedirectResponse:
    target = safe_return_path(next_path)
    if target is None or not _has_get_page(request, target.split("?", 1)[0]):
        target = "/" if getattr(request.state, "user", None) is not None else "/login"
    response = RedirectResponse(target, status_code=303)
    apply_theme(response, parse_theme(theme), secure=request.app.state.settings.production)
    return response
