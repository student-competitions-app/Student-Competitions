"""Where a switch sends the browser back to (milestone 12.5 FR-012; moved unchanged from
`app/routers/theme.py`, milestone 10 research D6).

The theme switch and the language switch post the page's own address as `next`. It is checked
twice: by `safe_return_path`, which refuses anything that is not a plain local path (and the
`POST`-only sign-in steps), and against the route table, so a page that was only ever shown by a
`POST` (a form after an error) never becomes a 405. Anything refused returns to `/` signed in, or
to `/login` signed out.
"""

from fastapi import Request
from starlette.routing import Match

from app.core.security import safe_return_path


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


def resolve_return(request: Request, raw: str) -> str:
    """The address to send the browser back to: `raw` when it is a safe local path to a page
    shown by `GET`, its query kept; else `/` signed in and `/login` signed out."""
    target = safe_return_path(raw)
    if target is None or not _has_get_page(request, target.split("?", 1)[0]):
        target = "/" if getattr(request.state, "user", None) is not None else "/login"
    return target
