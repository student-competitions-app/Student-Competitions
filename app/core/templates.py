"""The shared Jinja2 environment.

Lives in `core/` rather than in `app.main`: `app.main` imports the routers, so a router importing
`templates` back from `app.main` would close an import cycle and fail at startup. Every router,
the error handler and every later milestone share this one instance.

The directory is anchored to this package rather than to the working directory, so the
application serves the same templates whether it is started from the repository root, from `/app`
in the container, or from anywhere else (FR-011, research D14).

The release identity is registered as a Jinja global rather than passed by each handler: the
footer in the shared layout is rendered by every page, including the error page, and a value
every template needs belongs to the environment rather than to each handler's context.

The signed-in user reaches every template the same way, through a context processor that reads
`request.state.user` (set by `app.core.auth.resolve_access`), so the layout header can show the
address and the logout form without each handler passing them (FR-032).
"""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import APP_VERSION, COMMIT_SHA

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

SHORT_COMMIT_LENGTH = 7
"""Enough to identify a commit by eye and to paste into `git show`; the full value stays in the
footer's `title` attribute and in `/healthz`."""


def _current_user(request: Request) -> dict[str, Any]:
    """`current_user` for every template: the signed-in user, or `None`. Pages that no route
    matched (a 404) never ran the resolver, so the attribute may be missing."""
    return {"current_user": getattr(request.state, "user", None)}


templates = Jinja2Templates(directory=TEMPLATES_DIR, context_processors=[_current_user])

templates.env.globals["app_version"] = APP_VERSION
templates.env.globals["commit_sha"] = COMMIT_SHA
templates.env.globals["commit_short"] = COMMIT_SHA[:SHORT_COMMIT_LENGTH]
