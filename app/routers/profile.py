"""The signed-in person's own profile, and withdrawing consent.

See specs/008-teacher-management-consent/contracts/http-routes.md §4 (FR-043–FR-047). Every route
is open to every role and acts only on `request.state.user`, the person the session belongs to:
there is no id in any address here. The profile is read-only; corrections to teacher data are
made by an administrator.

Withdrawal erases the data stored on consent (`app.services.consent.erase_personal_data`), signs
the person out everywhere, clears this browser's cookie, and redirects to `/data-erased`.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.auth import allow_roles, clear_session_cookie
from app.core.config import APP_NAME
from app.core.db import SessionDep
from app.core.templates import templates
from app.models import ALL_ROLES, Role, User
from app.services.consent import (
    describe_erasure,
    erase_personal_data,
    has_consent_data,
    list_consent_records,
)
from app.services.teachers import TeacherNotFound, get_teacher

router = APIRouter()

NOTHING_TO_WITHDRAW = "There is no data stored on your consent to withdraw."


def _person(request: Request, session: SessionDep) -> User:
    """The signed-in person, read afresh."""
    user = session.get(User, request.state.user.id)
    assert user is not None
    return user


@router.get("/profile", response_class=HTMLResponse)
@allow_roles(*ALL_ROLES)
def profile_page(request: Request, session: SessionDep) -> HTMLResponse:
    person = _person(request, session)
    assert person.id is not None
    teacher = None
    if Role.TEACHER in request.state.roles:
        try:
            teacher = get_teacher(session, person.id)
        except TeacherNotFound:
            teacher = None
    return templates.TemplateResponse(
        request,
        "pages/profile.html",
        {
            "app_name": APP_NAME,
            "person": person,
            "roles": request.state.roles,
            "teacher": teacher,
            "records": list_consent_records(session, person.id),
            "can_withdraw": has_consent_data(person),
        },
    )


def _withdraw_page(request: Request, plan: object, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/profile_withdraw.html",
        {"app_name": APP_NAME, "plan": plan},
        status_code=status_code,
    )


@router.get("/profile/withdraw", response_class=HTMLResponse)
@allow_roles(*ALL_ROLES)
def withdraw_page(request: Request, session: SessionDep) -> HTMLResponse:
    """The confirmation: what will be erased and which roles go. Changes nothing (FR-046)."""
    person = _person(request, session)
    if not has_consent_data(person):
        return _withdraw_page(request, None, 409)
    return _withdraw_page(request, describe_erasure(session, person))


@router.post("/profile/withdraw", response_class=HTMLResponse)
@allow_roles(*ALL_ROLES)
def withdraw_action(request: Request, session: SessionDep) -> Response:
    person = _person(request, session)
    if not has_consent_data(person):
        return _withdraw_page(request, None, 409)
    assert person.id is not None
    erase_personal_data(session, request.app.state.settings, person.id)
    response = RedirectResponse("/data-erased", status_code=303)
    clear_session_cookie(response, request.app.state.settings)
    return response
