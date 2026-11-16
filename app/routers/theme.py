"""`POST /theme`: choose Light, Dark or Device (specs/010-design-system-ui-guidelines research D6,
contracts/http-routes.md §1).

A small form in the user menu and on the sign-in page posts here; no JavaScript is involved. The
route is public, because the switch works signed out and for every role, and it goes through the
application-wide cross-site check like every other `POST`. It reads and writes no data: it sets
or deletes the browser's `sc_theme` cookie and returns the browser where it was.

The return address is checked by `app.core.return_path.resolve_return`, shared with the language
switch (milestone 12.5 FR-012).
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.core.return_path import resolve_return
from app.core.theme import apply_theme, parse_theme

router = APIRouter()


@router.post("/theme")
def choose_theme(
    request: Request, theme: str = Form(""), next_path: str = Form("", alias="next")
) -> RedirectResponse:
    response = RedirectResponse(resolve_return(request, next_path), status_code=303)
    apply_theme(response, parse_theme(theme), secure=request.app.state.settings.production)
    return response
