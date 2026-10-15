"""The invitation link: the acceptance page and **I agree**. Public: the sealed token is the
authority, and it acts only on the person it names (FR-055, FR-065).

See specs/008-teacher-management-consent/contracts/http-routes.md §2 and research D4, D13.
`GET` evaluates the link and never writes; `POST` reads only `consent_text_id` and ignores every
other field (FR-029), so what is stored is exactly what the link holds.

Every refusal other than expiry gets one neutral message with one status, so the response does
not reveal which check failed (FR-033). After a successful acceptance the browser is sent to the
sign-in page with the address sealed in `?prefill=…` (purpose `login-prefill`, 10 minutes), never
in plain form. Acceptance signs nobody in or out (FR-032).

Every response carries `Referrer-Policy: no-referrer` and `Cache-Control: no-store`, so the token
leaks neither to another site nor into a cache (FR-061). Nothing here logs the token.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import APP_NAME, AuthSettings
from app.core.db import SessionDep
from app.core.sealing import seal
from app.core.templates import templates
from app.models import User
from app.routers.auth import LOGIN_PREFILL_PURPOSE
from app.services.consent import current_consent_text
from app.services.invitations import (
    Acceptable,
    Accepted,
    AlreadyHeld,
    ConsentChanged,
    Expired,
    Invitation,
    accept_invitation,
    evaluate_invitation,
    invitable_role,
)
from app.services.users import display_name

router = APIRouter()

NEUTRAL = "This invitation cannot be accepted. Ask the person who invited you to send a new one."
EXPIRED = "This invitation has expired; ask for a new one."
CONSENT_CHANGED = "The consent text has changed since you opened this page. Please read it again."

LINK_HEADERS = {"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}
"""Sent with every response of a page opened from an emailed link (FR-061)."""


def with_link_headers[R: Response](response: R) -> R:
    """`response` with the link-page headers; shared with the data-deletion link."""
    response.headers.update(LINK_HEADERS)
    return response


def _settings(request: Request) -> AuthSettings:
    return request.app.state.settings


def _status_page(
    request: Request,
    heading: str,
    message: str,
    status_code: int,
    link: dict[str, str] | None = None,
) -> HTMLResponse:
    return with_link_headers(
        templates.TemplateResponse(
            request,
            "pages/invitation_status.html",
            {"app_name": APP_NAME, "heading": heading, "message": message, "link": link},
            status_code=status_code,
        )
    )


def _neutral(request: Request) -> HTMLResponse:
    return _status_page(request, "Invitation", NEUTRAL, 400)


def _expired(request: Request) -> HTMLResponse:
    return _status_page(request, "Invitation expired", EXPIRED, 410)


def _already_held(request: Request, invitation: Invitation) -> HTMLResponse:
    return _status_page(
        request,
        "Invitation",
        f"You are already a {invitation.role.label.lower()}.",
        200,
        {"href": "/login", "text": "Sign in"},
    )


def _acceptance_page(
    request: Request,
    session: SessionDep,
    invitation: Invitation,
    notice: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Exactly what will be stored, by current names, the current consent text, and **I agree**
    (FR-024). Nothing on it is editable, and it shows nothing about the signed-in session."""
    inviter = session.get(User, invitation.inviter_id)
    assert inviter is not None
    return with_link_headers(
        templates.TemplateResponse(
            request,
            "pages/invitation.html",
            {
                "app_name": APP_NAME,
                "invitation": invitation,
                "inviter_name": display_name(inviter),
                "inviter_email": inviter.email,
                "role_label": invitation.role.label,
                "lines": invitable_role(invitation.role).describe(session, invitation.details),
                "consent_text": current_consent_text(session, invitation.role),
                "notice": notice,
            },
            status_code=status_code,
        )
    )


@router.get("/invitations/{token}", response_class=HTMLResponse)
def invitation_page(request: Request, session: SessionDep, token: str) -> HTMLResponse:
    """Evaluate the link; never writes (research D4)."""
    outcome = evaluate_invitation(session, _settings(request), token)
    if isinstance(outcome, Acceptable):
        return _acceptance_page(request, session, outcome.invitation)
    if isinstance(outcome, AlreadyHeld):
        return _already_held(request, outcome.invitation)
    if isinstance(outcome, Expired):
        return _expired(request)
    return _neutral(request)


@router.post("/invitations/{token}", response_class=HTMLResponse)
def accept_action(
    request: Request, session: SessionDep, token: str, consent_text_id: str = Form("")
) -> Response:
    """**I agree**: only `consent_text_id` is read (FR-029). A value that is not an integer is
    treated as a stale text."""
    settings = _settings(request)
    shown = int(consent_text_id) if consent_text_id.isascii() and consent_text_id.isdigit() else -1
    outcome = accept_invitation(session, settings, token, shown)
    if isinstance(outcome, Accepted):
        prefill = seal(settings.secret_key, LOGIN_PREFILL_PURPOSE, {"email": outcome.email})
        return with_link_headers(RedirectResponse(f"/login?prefill={prefill}", status_code=303))
    if isinstance(outcome, AlreadyHeld):
        return with_link_headers(RedirectResponse(f"/invitations/{token}", status_code=303))
    if isinstance(outcome, ConsentChanged):
        return _acceptance_page(request, session, outcome.invitation, CONSENT_CHANGED, 409)
    if isinstance(outcome, Expired):
        return _expired(request)
    return _neutral(request)
