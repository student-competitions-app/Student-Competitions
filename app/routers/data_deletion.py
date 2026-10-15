"""Deleting one's data without signing in, and the page shown once data is erased.

See specs/008-teacher-management-consent/contracts/http-routes.md §5 and research D10, D12.
Public: every route here is in `PUBLIC_ROUTES`. The request form answers the same way for every
well-formed address, registered or not, within the limits or not; the link is sent by a
background task after the response (FR-050). The emailed link carries its own authority, the
sealed token, and acts only on the person it names (FR-055): a signed-in browser's own session is
ended only when it belongs to that person.

Link pages carry `Referrer-Policy: no-referrer` and `Cache-Control: no-store` on every response
(FR-061). Nothing here logs an address or a token.
"""

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.auth import clear_session_cookie
from app.core.config import APP_NAME, AuthSettings
from app.core.db import SessionDep
from app.core.security import client_address
from app.core.templates import templates
from app.models import User
from app.routers.invitations import with_link_headers
from app.schemas.people import InvalidEmail, clean_email
from app.services.consent import ErasureResult, describe_erasure
from app.services.data_deletion import (
    LinkExpired,
    confirm_deletion,
    deliver_deletion_link,
    read_deletion_link,
)
from app.services.rate_limits import (
    BUCKET_DELETION_CLIENT,
    BUCKET_DELETION_EMAIL,
    CLIENT_DELETION_LIMIT,
    EMAIL_DELETION_LIMIT,
    LimitCheck,
    allow,
)

router = APIRouter()

LINK_EXPIRED = "This link has expired; request a new one."
LINK_INVALID = "This link cannot be used. Request a new one."


def _settings(request: Request) -> AuthSettings:
    return request.app.state.settings


def _page(
    request: Request,
    template: str,
    context: dict[str, object] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, template, {"app_name": APP_NAME, **(context or {})}, status_code=status_code
    )


@router.get("/data-deletion", response_class=HTMLResponse)
def request_page(request: Request) -> HTMLResponse:
    return _page(request, "pages/data_deletion_request.html", {"email": "", "message": None})


@router.post("/data-deletion", response_class=HTMLResponse)
def request_action(
    request: Request, background_tasks: BackgroundTasks, session: SessionDep, email: str = Form("")
) -> Response:
    """A malformed address is refused; anything else gets the same answer (FR-050). The link is
    sent only within the limits: 5 per address and 20 per client an hour (research D12)."""
    try:
        address = clean_email(email)
    except InvalidEmail as invalid:
        return _page(
            request,
            "pages/data_deletion_request.html",
            {"email": email, "message": invalid.message},
            400,
        )
    settings = _settings(request)
    client = client_address(request, trust_forwarded=settings.production)
    allowed = allow(
        session,
        settings.secret_key,
        (
            LimitCheck(BUCKET_DELETION_EMAIL, address, EMAIL_DELETION_LIMIT),
            LimitCheck(BUCKET_DELETION_CLIENT, client, CLIENT_DELETION_LIMIT),
        ),
    )
    if allowed:
        background_tasks.add_task(
            deliver_deletion_link,
            request.app.state.engine,
            request.app.state.email_sender,
            settings,
            settings.public_base_url or str(request.base_url).rstrip("/"),
            address,
        )
    return RedirectResponse("/data-deletion/requested", status_code=303)


@router.get("/data-deletion/requested", response_class=HTMLResponse)
def requested_page(request: Request) -> HTMLResponse:
    return _page(request, "pages/data_deletion_requested.html")


def _link_refused(request: Request, outcome: object) -> HTMLResponse:
    if isinstance(outcome, LinkExpired):
        context = {"heading": "Link expired", "message": LINK_EXPIRED}
        return with_link_headers(_page(request, "pages/link_status.html", context, 410))
    context = {"heading": "Link not valid", "message": LINK_INVALID}
    return with_link_headers(_page(request, "pages/link_status.html", context, 400))


@router.get("/data-deletion/confirm/{token}", response_class=HTMLResponse)
def confirm_page(request: Request, session: SessionDep, token: str) -> HTMLResponse:
    """What will be erased (FR-053). Never writes."""
    found = read_deletion_link(session, _settings(request), token)
    if not isinstance(found, User):
        return _link_refused(request, found)
    plan = describe_erasure(session, found)
    return with_link_headers(_page(request, "pages/data_deletion_confirm.html", {"plan": plan}))


@router.post("/data-deletion/confirm/{token}", response_class=HTMLResponse)
def confirm_action(request: Request, session: SessionDep, token: str) -> Response:
    """Erase, as a withdrawal does. This browser's cookie is cleared only when its session
    belongs to the erased person."""
    settings = _settings(request)
    found = read_deletion_link(session, settings, token)
    if not isinstance(found, User):
        return _link_refused(request, found)
    erased_id = found.id
    outcome = confirm_deletion(session, settings, token)
    if not isinstance(outcome, ErasureResult):
        return _link_refused(request, outcome)
    response = with_link_headers(RedirectResponse("/data-erased", status_code=303))
    signed_in = request.state.user
    if signed_in is not None and signed_in.id == erased_id:
        clear_session_cookie(response, settings)
    return response


@router.get("/data-erased", response_class=HTMLResponse)
def data_erased_page(request: Request) -> HTMLResponse:
    """Shown after a withdrawal or a data deletion; reloading it repeats nothing."""
    return _page(request, "pages/data_erased.html")
