"""`POST /language`: choose Українська or English (milestone 12.5 research R7,
contracts/http-routes.md §1).

The language switch in the top bar of every page posts here; no JavaScript is involved. Like
`POST /theme`, the route is public (the switch works signed out and for every role), goes through
the application-wide cross-site check, and reads and writes no data: it sets the browser's
`sc_lang` cookie and returns the browser where it was, through the same return-address check.

A known language is always stored, the default one too, so a later change of the deployment's
default never changes a choice already made (FR-015). Anything else stores nothing and still
returns (FR-013). Nothing here logs the value (FR-016).
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.core.i18n import apply_language, parse_language
from app.core.return_path import resolve_return

router = APIRouter()


@router.post("/language")
def choose_language(
    request: Request, language: str = Form(""), next_path: str = Form("", alias="next")
) -> RedirectResponse:
    response = RedirectResponse(resolve_return(request, next_path), status_code=303)
    chosen = parse_language(language)
    if chosen is not None:
        apply_language(response, chosen, secure=request.app.state.settings.production)
    return response
