"""The Teachers tab of the administrator area: the list of teachers, the invitation form, the
teacher page (edit) and removal.

See specs/008-teacher-management-consent/contracts/http-routes.md §1. Thin handlers only: each
parses the form, calls `app.services.invitations` or `app.services.teachers`, maps their outcomes
to a status and a page, and on success redirects with a 303 (Post/Redirect/Get), so a reload never
repeats a change (FR-060). An invalid form is shown again with every error and every value as
typed.

After an invitation is sent, the address travels to the list page sealed in the query string
(`?sent=…`, purpose `invitation-sent`, 10 minutes), so it never appears in a URL or the access log
in plain form (research D13).

Every route is `@allow_roles(Role.ADMIN)`, and every page is rendered with the Teachers tab
current. Ids are declared `{user_id:int}`, so a non-integer id matches no route and gets the
friendly 404. Nothing here logs an address, a name or a token.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import allow_roles
from app.core.config import AuthSettings
from app.core.db import SessionDep
from app.core.sealing import SealExpired, SealInvalid, seal, unseal
from app.models import AccessLevel, Role, User
from app.routers.admin import render_admin
from app.schemas.people import InvalidEmail, clean_email, clean_person_names
from app.schemas.teachers import (
    NOT_SELECTABLE,
    InvalidChoice,
    TeacherDetails,
    parse_institution_choices,
)
from app.services.email import EmailDeliveryError
from app.services.institutions import (
    SelectableInstitution,
    describe_institutions,
    list_selectable_institutions,
)
from app.services.invitations import issue_invitation
from app.services.rate_limits import (
    BUCKET_INVITE_EMAIL,
    BUCKET_INVITE_INVITER,
    EMAIL_INVITE_LIMIT,
    INVITER_INVITE_LIMIT,
    LimitCheck,
    allow,
)
from app.services.teachers import (
    InstitutionNotSelectable,
    TeacherLink,
    TeacherNotFound,
    TeacherView,
    get_teacher,
    list_teachers,
    remove_teacher,
    update_teacher,
)

router = APIRouter(prefix="/admin/teachers")

TAB = "teachers"
TAB_PATH = "/admin/teachers"

INVITATION_SENT_PURPOSE = "invitation-sent"
NOTICE_TTL = timedelta(minutes=10)

RepeatedField = Annotated[list[str], Form(default_factory=list)]
"""A repeated form field (the picker's `institution` and `access`), read as plain strings so a
bad value re-renders the form instead of FastAPI's 422 JSON (research D11)."""

TOO_MANY = "Too many invitations. Please try again later."
NOT_SENT = "The invitation email could not be sent. Please try again."


@dataclass(frozen=True)
class PickerRow:
    id: int
    label: str
    checked: bool
    level: str
    """The selected option: `read` (the default for a new pick) or `write`."""
    kept: bool = False
    """A linked institution that is no longer selectable: level shown as text, no select."""

    @property
    def level_label(self) -> str:
        return AccessLevel(self.level).label


def _settings(request: Request) -> AuthSettings:
    return request.app.state.settings


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _submitted(institution: list[str], access: list[str]) -> tuple[set[int], dict[int, str]]:
    """The picked ids and chosen levels as submitted, for showing the form again."""
    picked = {int(raw) for raw in institution if raw.strip().isascii() and raw.strip().isdigit()}
    levels: dict[int, str] = {}
    for entry in access:
        raw_id, _, level = entry.partition(":")
        if raw_id.isascii() and raw_id.isdigit() and level in ("read", "write"):
            levels[int(raw_id)] = level
    return picked, levels


def _picker_rows(
    selectable: list[SelectableInstitution],
    picked: set[int],
    levels: dict[int, str],
    kept: Sequence[TeacherLink] = (),
) -> list[PickerRow]:
    rows = [
        PickerRow(
            id=item.id,
            label=item.label,
            checked=item.id in picked,
            level=levels.get(item.id, AccessLevel.READ.value),
        )
        for item in selectable
    ]
    rows += [
        PickerRow(
            id=link.institution_id,
            label=link.label,
            checked=link.institution_id in picked,
            level=link.access_level.value,
            kept=True,
        )
        for link in kept
    ]
    return sorted(rows, key=lambda row: (row.label.casefold(), row.id))


def _not_found(request: Request) -> HTMLResponse:
    return render_admin(request, "pages/admin/teacher_not_found.html", TAB, status_code=404)


# ---------------------------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------------------------


def sent_notice_email(settings: AuthSettings, sent: str | None) -> str | None:
    """The address in a valid, fresh `sent` value; `None` for anything else. Shared with the
    teacher's student invitations (`app.routers.teacher_students`)."""
    if not sent:
        return None
    try:
        payload = unseal(settings.secret_key, INVITATION_SENT_PURPOSE, sent, NOTICE_TTL)
    except (SealInvalid, SealExpired):
        return None
    email = payload.get("email")
    return email if isinstance(email, str) else None


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def teachers_page(
    request: Request, session: SessionDep, sent: str | None = Query(None)
) -> HTMLResponse:
    """The current teachers (FR-038), with the "Invitation sent" banner after an invitation."""
    return render_admin(
        request,
        "pages/admin/teachers.html",
        TAB,
        {
            "teachers": list_teachers(session),
            "sent_to": sent_notice_email(_settings(request), sent),
        },
    )


# ---------------------------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------------------------


def _invite_form(
    request: Request,
    session: SessionDep,
    values: dict[str, Any],
    picked: set[int] | None = None,
    levels: dict[int, str] | None = None,
    errors: dict[str, str] | None = None,
    form_error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    rows = _picker_rows(list_selectable_institutions(session), picked or set(), levels or {})
    return render_admin(
        request,
        "pages/admin/teacher_invite.html",
        TAB,
        {
            "values": values,
            "picker_rows": rows,
            "errors": errors or {},
            "form_error": form_error,
        },
        status_code=status_code,
    )


@router.get("/invite", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def invite_page(request: Request, session: SessionDep) -> HTMLResponse:
    values = {"email": "", "first_name": "", "last_name": "", "can_create_competitions": False}
    return _invite_form(request, session, values)


@router.post("/invite", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def invite_action(
    request: Request,
    session: SessionDep,
    institution: RepeatedField,
    access: RepeatedField,
    email: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    can_create_competitions: str | None = Form(None),
) -> HTMLResponse:
    """Validate (email, names, picker), check the limits, then seal and send (FR-014–FR-021).

    Nothing from the form is stored. A delivery failure still counts against the limits.
    """
    settings = _settings(request)
    inviter: User = request.state.user
    can_create = can_create_competitions is not None
    values = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "can_create_competitions": can_create,
    }
    picked, levels = _submitted(institution, access)

    def refused(
        status: int, errors: dict[str, str] | None = None, message: str | None = None
    ) -> HTMLResponse:
        return _invite_form(request, session, values, picked, levels, errors, message, status)

    errors: dict[str, str] = {}
    try:
        address = clean_email(email)
    except InvalidEmail as invalid:
        errors["email"] = invalid.message
        address = ""
    first, last = clean_person_names(first_name, last_name, errors)
    choices: dict[int, AccessLevel] = {}
    try:
        choices = parse_institution_choices(institution, access)
    except InvalidChoice as invalid:
        errors["picker"] = invalid.message
    else:
        described = describe_institutions(session, choices)
        if not all(i in described and described[i].is_selectable for i in choices):
            errors["picker"] = NOT_SELECTABLE
    if errors:
        return refused(400, errors)

    assert inviter.id is not None
    allowed = allow(
        session,
        settings.secret_key,
        (
            LimitCheck(BUCKET_INVITE_INVITER, str(inviter.id), INVITER_INVITE_LIMIT),
            LimitCheck(BUCKET_INVITE_EMAIL, address, EMAIL_INVITE_LIMIT),
        ),
    )
    if not allowed:
        return refused(429, message=TOO_MANY)
    base_url = settings.public_base_url or str(request.base_url).rstrip("/")
    try:
        issue_invitation(
            session,
            settings,
            request.app.state.email_sender,
            base_url,
            inviter,
            Role.TEACHER,
            address,
            first,
            last,
            TeacherDetails(institutions=choices, can_create_competitions=can_create),
        )
    except InvalidChoice as invalid:
        return refused(400, {"picker": invalid.message})
    except EmailDeliveryError:
        return refused(503, message=NOT_SENT)
    sent = seal(settings.secret_key, INVITATION_SENT_PURPOSE, {"email": address})
    return _redirect(f"{TAB_PATH}?sent={sent}")


# ---------------------------------------------------------------------------------------------
# The teacher page
# ---------------------------------------------------------------------------------------------


def _kept_levels(teacher: TeacherView) -> dict[int, AccessLevel]:
    """The links whose institution is no longer selectable: their level cannot change."""
    return {
        link.institution_id: link.access_level for link in teacher.links if not link.is_selectable
    }


def _teacher_form(
    request: Request,
    session: SessionDep,
    teacher: TeacherView,
    values: dict[str, Any],
    picked: set[int],
    levels: dict[int, str],
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    kept = [link for link in teacher.links if not link.is_selectable]
    rows = _picker_rows(list_selectable_institutions(session), picked, levels, kept)
    return render_admin(
        request,
        "pages/admin/teacher_form.html",
        TAB,
        {
            "heading": f"{teacher.first_name} {teacher.last_name}",
            "teacher": teacher,
            "values": values,
            "picker_rows": rows,
            "errors": errors or {},
        },
        status_code=status_code,
    )


@router.get("/{user_id:int}", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def teacher_page(request: Request, session: SessionDep, user_id: int) -> HTMLResponse:
    """The teacher's data as a form; the email is shown but cannot be changed (FR-039)."""
    try:
        teacher = get_teacher(session, user_id)
    except TeacherNotFound:
        return _not_found(request)
    values = {
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "can_create_competitions": teacher.can_create_competitions,
    }
    picked = {link.institution_id for link in teacher.links}
    levels = {link.institution_id: link.access_level.value for link in teacher.links}
    return _teacher_form(request, session, teacher, values, picked, levels)


@router.post("/{user_id:int}", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def update_teacher_action(
    request: Request,
    session: SessionDep,
    user_id: int,
    institution: RepeatedField,
    access: RepeatedField,
    first_name: str = Form(""),
    last_name: str = Form(""),
    can_create_competitions: str | None = Form(None),
) -> HTMLResponse:
    """Save the edit: only what changed is written, and the teacher stays signed in (FR-040,
    FR-041). Any field other than these, such as an email, is ignored."""
    try:
        teacher = get_teacher(session, user_id)
    except TeacherNotFound:
        return _not_found(request)
    can_create = can_create_competitions is not None
    values = {
        "first_name": first_name,
        "last_name": last_name,
        "can_create_competitions": can_create,
    }
    picked, levels = _submitted(institution, access)
    errors: dict[str, str] = {}
    first, last = clean_person_names(first_name, last_name, errors)
    choices: dict[int, AccessLevel] = {}
    try:
        choices = parse_institution_choices(institution, access, _kept_levels(teacher))
    except InvalidChoice as invalid:
        errors["picker"] = invalid.message
    if not errors:
        try:
            update_teacher(session, user_id, first, last, choices, can_create)
        except TeacherNotFound:
            return _not_found(request)
        except InstitutionNotSelectable as invalid:
            errors["picker"] = invalid.message
        else:
            return _redirect(TAB_PATH)
    return _teacher_form(request, session, teacher, values, picked, levels, errors, 400)


# ---------------------------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------------------------


@router.get("/{user_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def remove_page(request: Request, session: SessionDep, user_id: int) -> HTMLResponse:
    """The confirmation step: opening it changes nothing (FR-042)."""
    try:
        teacher = get_teacher(session, user_id)
    except TeacherNotFound:
        return _not_found(request)
    return render_admin(
        request,
        "pages/admin/teacher_remove.html",
        TAB,
        {"name": f"{teacher.first_name} {teacher.last_name}", "user_id": user_id},
    )


@router.post("/{user_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def remove_action(request: Request, session: SessionDep, user_id: int) -> HTMLResponse:
    try:
        remove_teacher(session, _settings(request), user_id)
    except TeacherNotFound:
        return _not_found(request)
    return _redirect(TAB_PATH)
