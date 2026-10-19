"""The Students tab of the teacher area: choosing a class, managing classes, inviting students,
and editing and removing them.

See specs/009-classes-students-management/contracts/http-routes.md §2 and research D5, D7. Thin
handlers only: each reads its values as plain strings, calls `app.services.teacher_access`,
`app.services.classes` or `app.services.students`, maps their outcomes to a status and a page,
and on success redirects with a 303 (Post/Redirect/Get), so a reload never repeats a change
(FR-056). An invalid form is shown again with every error and every value as typed.

**The selection lives in the address** (research D7): `/teacher/students?region=…&institution=…
&class=…`, built by `selection_path` for every redirect, so it survives reloads and bookmarks
(FR-050). Three small `GET` forms with **Show** buttons change it, with no script.

**Access**: every route is `@allow_roles(Role.TEACHER)` and acts as `request.state.user`. Every
object an address or a form names is checked through `app.services.teacher_access`, inside the
services for every change (research D5). An id that is not an ASCII integer, unknown, out of
reach, or not inside its parent, and any management page or action with Read access, all answer
with the same milestone 5 "Access denied" page (`AccessDenied`, 403), so nothing reveals whether
an object exists (FR-021). Nothing here logs an address, a name or a token.
"""

from typing import Any

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.auth import AccessDenied, allow_roles
from app.core.config import AuthSettings
from app.core.db import SessionDep
from app.core.sealing import seal
from app.models import Role, SchoolClass, User
from app.routers.admin_teachers import (
    INVITATION_SENT_PURPOSE,
    NOT_SENT,
    TOO_MANY,
    sent_notice_email,
)
from app.routers.teacher import render_teacher
from app.schemas.classes import InvalidYear, parse_year_of_study
from app.schemas.names import InvalidName, clean_name
from app.schemas.people import InvalidEmail, clean_email, clean_person_names
from app.schemas.students import StudentDetails
from app.schemas.teachers import MAX_ID, InvalidChoice
from app.services.classes import (
    ClassInUse,
    ClassView,
    DuplicateClassName,
    create_class,
    delete_class,
    list_classes,
    set_class_active,
    update_class,
)
from app.services.email import EmailDeliveryError
from app.services.invitations import issue_invitation
from app.services.rate_limits import (
    BUCKET_INVITE_EMAIL,
    BUCKET_INVITE_STUDENT_INVITER,
    EMAIL_INVITE_LIMIT,
    STUDENT_INVITER_INVITE_LIMIT,
    LimitCheck,
    allow,
)
from app.services.students import (
    NOT_A_NEW_STUDENT,
    ClassNotActive,
    StudentRow,
    get_student,
    is_student_address,
    list_students,
    remove_student,
    update_student,
)
from app.services.teacher_access import (
    NotReachable,
    ReachableInstitution,
    WriteRequired,
    list_reachable_institutions,
    reach_class,
    reach_institution,
    reachable_regions,
)

router = APIRouter(prefix="/teacher/students")

TAB = "students"
TAB_PATH = "/teacher/students"

NOT_LINKED = "You are not linked to any educational institution"
SELECT_REGION = "Select a region to continue"
SELECT_INSTITUTION = "Select an educational institution to continue"
SELECT_CLASS = "Select a class to see its students"
NO_STUDENTS = "No students in this class yet"
CLASS_HIDDEN = "This class is deactivated; its students are hidden until it is activated again"
"""The messages of the page in each state (FR-049, FR-054)."""

NEW_CLASS = "new"
"""The `class` value of the **+ Add class** entry (research D7)."""

NO_NEW_STUDENTS = "This class is deactivated. Students cannot be added to it."
"""The invitation form of a deactivated class (spec Assumptions)."""


def selection_path(region_id: int, institution_id: int, class_id: int | None = None) -> str:
    """The Students tab with this region, institution and, if given, class selected."""
    path = f"{TAB_PATH}?region={region_id}&institution={institution_id}"
    if class_id is not None:
        path += f"&class={class_id}"
    return path


def _denied() -> AccessDenied:
    """The milestone 5 403 page: the same for unknown, unreachable and read-only (FR-021)."""
    return AccessDenied(Role.TEACHER)


def _id(raw: str | None) -> int | None:
    """An id from the address or a form: `None` when absent or empty, an `int` for ASCII digits
    up to `MAX_ID`, and "access denied" for anything else."""
    if raw is None or raw == "":
        return None
    if not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        raise _denied()
    return int(raw)


def _settings(request: Request) -> AuthSettings:
    return request.app.state.settings


def _teacher(request: Request) -> int:
    user: User = request.state.user
    assert user.id is not None
    return user.id


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _reach_institution(
    session: SessionDep, teacher_id: int, institution_id: int, write: bool = True
) -> ReachableInstitution:
    try:
        return reach_institution(session, teacher_id, institution_id, write=write)
    except (NotReachable, WriteRequired):
        raise _denied() from None


def _reach_class(
    session: SessionDep, teacher_id: int, class_id: int, write: bool = True
) -> tuple[ReachableInstitution, SchoolClass]:
    try:
        return reach_class(session, teacher_id, class_id, write=write)
    except (NotReachable, WriteRequired):
        raise _denied() from None


# ---------------------------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def students_page(
    request: Request,
    session: SessionDep,
    region: str | None = Query(None),
    institution: str | None = Query(None),
    class_: str | None = Query(None, alias="class"),
    sent: str | None = Query(None),
) -> Response:
    """The three lists, the message of the current state, and the selected class with its
    students (FR-048–FR-054). Opening it changes nothing."""
    teacher_id = _teacher(request)
    region_id = _id(region)
    institution_id = _id(institution)
    adding = class_ == NEW_CLASS
    class_id = None if adding else _id(class_)
    if institution_id is not None and region_id is None:
        raise _denied()
    if (adding or class_id is not None) and institution_id is None:
        raise _denied()

    reachable = list_reachable_institutions(session, teacher_id)
    regions = reachable_regions(reachable)
    if region_id is not None and region_id not in {id_ for id_, _ in regions}:
        raise _denied()

    selected_institution: ReachableInstitution | None = None
    if institution_id is not None:
        try:
            selected_institution = reach_institution(
                session, teacher_id, institution_id, region_id=region_id
            )
        except NotReachable:
            raise _denied() from None
    if adding:
        assert selected_institution is not None
        if not selected_institution.can_write:
            raise _denied()
        return _redirect(f"{TAB_PATH}/institutions/{selected_institution.id}/classes/new")

    selected_class: ClassView | None = None
    if class_id is not None:
        try:
            _, row = reach_class(session, teacher_id, class_id, institution_id=institution_id)
        except NotReachable:
            raise _denied() from None
        selected_class = ClassView.from_row(row)

    students: list[Any] = []
    if selected_class is not None and selected_class.is_active:
        students = list_students(session, selected_class.id)
    if not reachable:
        message = NOT_LINKED
    elif region_id is None:
        message = SELECT_REGION
    elif selected_institution is None:
        message = SELECT_INSTITUTION
    elif selected_class is None:
        message = SELECT_CLASS
    elif not selected_class.is_active:
        message = CLASS_HIDDEN
    else:
        message = NO_STUDENTS if not students else None

    return render_teacher(
        request,
        "pages/teacher/students.html",
        TAB,
        {
            "regions": regions,
            "institutions": [item for item in reachable if item.region_id == region_id],
            "classes": list_classes(session, selected_institution.id)
            if selected_institution
            else [],
            "selected_region": region_id,
            "selected_institution": selected_institution,
            "selected_class": selected_class,
            "message": message,
            "students": students,
            "can_write": selected_institution is not None and selected_institution.can_write,
            "sent_to": sent_notice_email(_settings(request), sent),
        },
    )


# ---------------------------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------------------------


def _class_form(
    request: Request,
    heading: str,
    action: str,
    institution: ReachableInstitution,
    values: dict[str, str],
    cancel: str,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The create or edit form, naming the institution and offering no way to change it
    (FR-003)."""
    return render_teacher(
        request,
        "pages/teacher/class_form.html",
        TAB,
        {
            "heading": heading,
            "action": action,
            "institution": institution,
            "values": values,
            "errors": errors or {},
            "cancel": cancel,
        },
        status_code=status_code,
    )


def _class_errors(name: str, year_of_study: str) -> dict[str, str]:
    """Every rule the submitted values break, by field, for showing the form again."""
    errors: dict[str, str] = {}
    try:
        clean_name(name)
    except InvalidName as invalid:
        errors["name"] = invalid.message
    try:
        parse_year_of_study(year_of_study)
    except InvalidYear as invalid:
        errors["year_of_study"] = invalid.message
    return errors


def _new_class_heading(institution: ReachableInstitution) -> str:
    return f"New class in “{institution.name}”"


@router.get("/institutions/{institution_id:int}/classes/new", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def new_class_page(request: Request, session: SessionDep, institution_id: int) -> HTMLResponse:
    institution = _reach_institution(session, _teacher(request), institution_id)
    return _class_form(
        request,
        _new_class_heading(institution),
        f"{TAB_PATH}/institutions/{institution.id}/classes",
        institution,
        {"name": "", "year_of_study": ""},
        selection_path(institution.region_id, institution.id),
    )


@router.post("/institutions/{institution_id:int}/classes", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def create_class_action(
    request: Request,
    session: SessionDep,
    institution_id: int,
    name: str = Form(""),
    year_of_study: str = Form(""),
) -> Response:
    """On success the new class is selected (US1-6). Only `name` and `year_of_study` are read:
    any other field, such as an institution, is ignored (FR-003)."""
    teacher_id = _teacher(request)
    institution = _reach_institution(session, teacher_id, institution_id)
    values = {"name": name, "year_of_study": year_of_study}

    def refused(errors: dict[str, str]) -> HTMLResponse:
        return _class_form(
            request,
            _new_class_heading(institution),
            f"{TAB_PATH}/institutions/{institution.id}/classes",
            institution,
            values,
            selection_path(institution.region_id, institution.id),
            errors,
            400,
        )

    errors = _class_errors(name, year_of_study)
    if errors:
        return refused(errors)
    try:
        created = create_class(session, teacher_id, institution_id, name, year_of_study)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except DuplicateClassName as duplicate:
        return refused({"name": duplicate.message})
    return _redirect(selection_path(institution.region_id, institution.id, created.id))


def _edit_heading(school_class: SchoolClass) -> str:
    return f"Edit class “{school_class.name}”"


@router.get("/classes/{class_id:int}/edit", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def edit_class_page(request: Request, session: SessionDep, class_id: int) -> HTMLResponse:
    institution, school_class = _reach_class(session, _teacher(request), class_id)
    return _class_form(
        request,
        _edit_heading(school_class),
        f"{TAB_PATH}/classes/{class_id}/edit",
        institution,
        {"name": school_class.name, "year_of_study": str(school_class.year_of_study)},
        selection_path(institution.region_id, institution.id, class_id),
    )


@router.post("/classes/{class_id:int}/edit", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def edit_class_action(
    request: Request,
    session: SessionDep,
    class_id: int,
    name: str = Form(""),
    year_of_study: str = Form(""),
) -> Response:
    """Name and year of study; a change of case alone is a valid rename (US1-9)."""
    teacher_id = _teacher(request)
    institution, school_class = _reach_class(session, teacher_id, class_id)
    heading = _edit_heading(school_class)
    back = selection_path(institution.region_id, institution.id, class_id)
    values = {"name": name, "year_of_study": year_of_study}

    def refused(errors: dict[str, str]) -> HTMLResponse:
        return _class_form(
            request,
            heading,
            f"{TAB_PATH}/classes/{class_id}/edit",
            institution,
            values,
            back,
            errors,
            400,
        )

    errors = _class_errors(name, year_of_study)
    if errors:
        return refused(errors)
    try:
        update_class(session, teacher_id, class_id, name, year_of_study)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except DuplicateClassName as duplicate:
        return refused({"name": duplicate.message})
    return _redirect(back)


@router.get("/classes/{class_id:int}/deactivate", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def deactivate_class_page(request: Request, session: SessionDep, class_id: int) -> HTMLResponse:
    """The confirmation step: opening it changes nothing (FR-052)."""
    institution, school_class = _reach_class(session, _teacher(request), class_id)
    return render_teacher(
        request,
        "pages/teacher/class_deactivate.html",
        TAB,
        {
            "school_class": school_class,
            "institution": institution,
            "cancel": selection_path(institution.region_id, institution.id, class_id),
        },
    )


def _set_class_active(
    request: Request, session: SessionDep, class_id: int, active: bool
) -> RedirectResponse:
    """Already in that status: nothing changes, and it is not an error."""
    teacher_id = _teacher(request)
    institution, _ = _reach_class(session, teacher_id, class_id)
    try:
        set_class_active(session, teacher_id, class_id, active)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    return _redirect(selection_path(institution.region_id, institution.id, class_id))


@router.post("/classes/{class_id:int}/deactivate", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def deactivate_class_action(
    request: Request, session: SessionDep, class_id: int
) -> RedirectResponse:
    """Its students are signed out at once (FR-015)."""
    return _set_class_active(request, session, class_id, False)


@router.post("/classes/{class_id:int}/activate", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def activate_class_action(request: Request, session: SessionDep, class_id: int) -> RedirectResponse:
    return _set_class_active(request, session, class_id, True)


def _class_delete_page(
    request: Request,
    school_class: SchoolClass,
    institution: ReachableInstitution,
    in_use: bool,
    status_code: int = 200,
) -> HTMLResponse:
    return render_teacher(
        request,
        "pages/teacher/class_delete.html",
        TAB,
        {
            "school_class": school_class,
            "institution": institution,
            "in_use": in_use,
            "cancel": selection_path(institution.region_id, institution.id, school_class.id),
        },
        status_code=status_code,
    )


@router.get("/classes/{class_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def delete_class_page(request: Request, session: SessionDep, class_id: int) -> HTMLResponse:
    """The confirmation step, naming the class and its institution: opening it changes nothing
    (FR-053)."""
    institution, school_class = _reach_class(session, _teacher(request), class_id)
    return _class_delete_page(request, school_class, institution, in_use=False)


@router.post("/classes/{class_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def delete_class_action(request: Request, session: SessionDep, class_id: int) -> Response:
    """A class with students is refused with 409, suggesting deactivation while it is active
    (US1-13). On success the institution stays selected and no class is (spec Edge Cases)."""
    teacher_id = _teacher(request)
    institution, _ = _reach_class(session, teacher_id, class_id)
    try:
        delete_class(session, teacher_id, class_id)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except ClassInUse as refused:
        return _class_delete_page(
            request, refused.school_class, institution, in_use=True, status_code=409
        )
    return _redirect(selection_path(institution.region_id, institution.id))


# ---------------------------------------------------------------------------------------------
# Inviting a student
# ---------------------------------------------------------------------------------------------


def _invite_form(
    request: Request,
    school_class: SchoolClass,
    institution: ReachableInstitution,
    values: dict[str, str],
    errors: dict[str, str] | None = None,
    form_error: str | None = None,
    refused: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    """The invitation form for one class, naming the class and the institution (US2-1). With
    `refused`, the class is deactivated and there is no form at all."""
    return render_teacher(
        request,
        "pages/teacher/student_invite.html",
        TAB,
        {
            "school_class": ClassView.from_row(school_class),
            "institution": institution,
            "values": values,
            "errors": errors or {},
            "form_error": form_error,
            "refused": refused,
            "cancel": selection_path(institution.region_id, institution.id, school_class.id),
        },
        status_code=status_code,
    )


@router.get("/classes/{class_id:int}/invite", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def invite_page(request: Request, session: SessionDep, class_id: int) -> HTMLResponse:
    institution, school_class = _reach_class(session, _teacher(request), class_id)
    values = {"email": "", "first_name": "", "last_name": ""}
    if not school_class.is_active:
        return _invite_form(
            request, school_class, institution, values, refused=True, status_code=409
        )
    return _invite_form(request, school_class, institution, values)


@router.post("/classes/{class_id:int}/invite", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def invite_action(
    request: Request,
    session: SessionDep,
    class_id: int,
    email: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
) -> Response:
    """Seal and send a student invitation into this class (FR-025–FR-029). The first failing
    step answers, in the order of research D11: reach with Write (403), an active class (409),
    the fields (400), the limits (429), not a student already (400), then sending (503, or 403
    for a race lost to a change of access). Nothing from the form is stored; every attempt that
    passed the fields counts against the limits."""
    settings = _settings(request)
    teacher: User = request.state.user
    teacher_id = _teacher(request)
    institution, school_class = _reach_class(session, teacher_id, class_id)
    values = {"email": email, "first_name": first_name, "last_name": last_name}

    def refused(
        status: int, errors: dict[str, str] | None = None, message: str | None = None
    ) -> HTMLResponse:
        return _invite_form(
            request,
            school_class,
            institution,
            values,
            errors,
            message,
            refused=not school_class.is_active,
            status_code=status,
        )

    if not school_class.is_active:
        return refused(409)
    errors: dict[str, str] = {}
    try:
        address = clean_email(email)
    except InvalidEmail as invalid:
        errors["email"] = invalid.message
        address = ""
    first, last = clean_person_names(first_name, last_name, errors)
    if errors:
        return refused(400, errors)

    allowed = allow(
        session,
        settings.secret_key,
        (
            LimitCheck(
                BUCKET_INVITE_STUDENT_INVITER, str(teacher_id), STUDENT_INVITER_INVITE_LIMIT
            ),
            LimitCheck(BUCKET_INVITE_EMAIL, address, EMAIL_INVITE_LIMIT),
        ),
    )
    if not allowed:
        return refused(429, message=TOO_MANY)
    if is_student_address(session, address):
        return refused(400, {"email": NOT_A_NEW_STUDENT})
    base_url = settings.public_base_url or str(request.base_url).rstrip("/")
    try:
        issue_invitation(
            session,
            settings,
            request.app.state.email_sender,
            base_url,
            teacher,
            Role.STUDENT,
            address,
            first,
            last,
            StudentDetails(institution_id=institution.id, class_id=class_id),
        )
    except InvalidChoice:
        raise _denied() from None
    except EmailDeliveryError:
        return refused(503, message=NOT_SENT)
    sent = seal(settings.secret_key, INVITATION_SENT_PURPOSE, {"email": address})
    return _redirect(
        f"{selection_path(institution.region_id, institution.id, class_id)}&sent={sent}"
    )


# ---------------------------------------------------------------------------------------------
# A student
# ---------------------------------------------------------------------------------------------


def _quiet_id(raw: str | None) -> int | None:
    """An id carried through for the redirect: `None` for anything that is not one."""
    if not raw or not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        return None
    return int(raw)


def _viewing(
    session: SessionDep,
    teacher_id: int,
    region: str | None,
    institution: str | None,
    class_: str | None,
    fallback: tuple[ReachableInstitution, int],
) -> str:
    """Where to return after a student action: the selection the teacher was viewing, carried
    through the page, when it is still reachable; otherwise the student's own class (FR-050)."""
    region_id, institution_id, class_id = (
        _quiet_id(region),
        _quiet_id(institution),
        _quiet_id(class_),
    )
    if region_id is not None and institution_id is not None and class_id is not None:
        try:
            reached, _ = reach_class(session, teacher_id, class_id, institution_id=institution_id)
        except NotReachable:
            pass
        else:
            if reached.region_id == region_id:
                return selection_path(region_id, institution_id, class_id)
    reached, own_class = fallback
    return selection_path(reached.region_id, reached.id, own_class)


FoundStudent = tuple[ReachableInstitution, ClassView, StudentRow]


def _get_student(session: SessionDep, teacher_id: int, user_id: int) -> FoundStudent:
    try:
        return get_student(session, teacher_id, user_id, write=True)
    except (NotReachable, WriteRequired):
        raise _denied() from None


def _student_form(
    request: Request,
    session: SessionDep,
    found: FoundStudent,
    values: dict[str, str],
    carried: dict[str, str],
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """First name, last name and a class among the institution's **active** classes; the email
    and the institution are shown and cannot be edited (FR-041, US4-3)."""
    institution, school_class, student = found
    active = [c for c in list_classes(session, institution.id) if c.is_active]
    return render_teacher(
        request,
        "pages/teacher/student_form.html",
        TAB,
        {
            "student": student,
            "institution": institution,
            "classes": active,
            "values": values,
            "carried": carried,
            "errors": errors or {},
            "cancel": _viewing(
                session,
                _teacher(request),
                carried["region"],
                carried["institution"],
                carried["class"],
                (institution, school_class.id),
            ),
        },
        status_code=status_code,
    )


@router.get("/{user_id:int}", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def student_page(
    request: Request,
    session: SessionDep,
    user_id: int,
    region: str | None = Query(None),
    institution: str | None = Query(None),
    class_: str | None = Query(None, alias="class"),
) -> HTMLResponse:
    found = _get_student(session, _teacher(request), user_id)
    _, school_class, student = found
    values = {
        "first_name": student.first_name,
        "last_name": student.last_name,
        "class_id": str(school_class.id),
    }
    carried = {"region": region or "", "institution": institution or "", "class": class_ or ""}
    return _student_form(request, session, found, values, carried)


@router.post("/{user_id:int}", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def update_student_action(
    request: Request,
    session: SessionDep,
    user_id: int,
    first_name: str = Form(""),
    last_name: str = Form(""),
    class_id: str = Form(""),
    region: str = Form(""),
    institution: str = Form(""),
    class_: str = Form("", alias="class"),
) -> Response:
    """Save the edit: names and class only; an email or institution field is ignored (FR-041).
    The student stays signed in (FR-042). A class of another institution, an unknown class, or a
    value that is not an id is "access denied"; a deactivated class of the same institution is a
    form error (US4-5)."""
    teacher_id = _teacher(request)
    found = _get_student(session, teacher_id, user_id)
    institution_view, own_class, _ = found
    values = {"first_name": first_name, "last_name": last_name, "class_id": class_id}
    carried = {"region": region, "institution": institution, "class": class_}
    errors: dict[str, str] = {}
    first, last = clean_person_names(first_name, last_name, errors)
    if errors:
        return _student_form(request, session, found, values, carried, errors, 400)
    try:
        moved_to = update_student(session, teacher_id, user_id, first, last, class_id)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except ClassNotActive as invalid:
        return _student_form(
            request, session, found, values, carried, {"class_id": invalid.message}, 400
        )
    return _redirect(
        _viewing(session, teacher_id, region, institution, class_, (institution_view, moved_to))
    )


@router.get("/{user_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_page(
    request: Request,
    session: SessionDep,
    user_id: int,
    region: str | None = Query(None),
    institution: str | None = Query(None),
    class_: str | None = Query(None, alias="class"),
) -> HTMLResponse:
    """The confirmation step, naming the student, the class and the institution: opening it
    changes nothing (FR-043)."""
    teacher_id = _teacher(request)
    found = _get_student(session, teacher_id, user_id)
    institution_view, school_class, student = found
    carried = {"region": region or "", "institution": institution or "", "class": class_ or ""}
    return render_teacher(
        request,
        "pages/teacher/student_remove.html",
        TAB,
        {
            "student": student,
            "school_class": school_class,
            "institution": institution_view,
            "carried": carried,
            "cancel": _viewing(
                session,
                teacher_id,
                region,
                institution,
                class_,
                (institution_view, school_class.id),
            ),
        },
    )


@router.post("/{user_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_action(
    request: Request,
    session: SessionDep,
    user_id: int,
    region: str = Form(""),
    institution: str = Form(""),
    class_: str = Form("", alias="class"),
) -> Response:
    """The student role and the enrolment go; the person is signed out everywhere, and
    deactivated if no role is left (FR-043)."""
    teacher_id = _teacher(request)
    institution_view, school_class, _ = _get_student(session, teacher_id, user_id)
    try:
        remove_student(session, _settings(request), teacher_id, user_id)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    return _redirect(
        _viewing(
            session, teacher_id, region, institution, class_, (institution_view, school_class.id)
        )
    )
