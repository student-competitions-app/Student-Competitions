"""The Competitions tab of the teacher area: a subject's competitions, and adding, editing and
cancelling them.

See specs/012.1-teacher-competitions/contracts/http-routes.md and research R9, R11–R13. Thin
handlers only: each reads its values as plain strings (so no input ever gets FastAPI's 422),
calls `app.services.competitions`, maps its outcomes to a status and a page, and on success
redirects with a 303 (Post/Redirect/Get), so a reload never repeats a change. An invalid form is
shown again with every error and every value as typed.

**Every teacher reads every competition; only a teacher with Can manage competitions changes
them.** The list shows **Add competition** and the row menus only with the setting and an active
subject. Every other route is a *manage* route.

**Order of checks** (http-routes.md §Order of checks): the role (`@allow_roles`); then, on a
manage route, the setting, first thing in the handler, before any value is parsed, so a teacher
without it learns nothing about which subjects or competitions exist (403 for an unknown id too);
then the subject ("Subject not found", 404); then the competition ("Competition not found",
404); then the status (the refusal, 409); then the fields (400); then the service write, which
checks the setting, the subject, the competition and the status again under lock.

**Times**: the list, the forms and the confirmation show times in the browser's zone (the
`sc_time_zone` cookie, `app.core.time_zone`), or in UTC labelled so. A form carries the zone it
was shown in as a hidden field, and the start is read in that zone, not the cookie's (FR-022).

**Return addresses** are built by `list_path` from server-side values only: a subject that was
looked up, a status and a page that were parsed, ids. **The notice after a change** travels as a
sealed, 10-minute token holding the competition's id and the outcome, so no name ever reaches an
address or a log line (FR-046, research R12). Nothing here logs; the service logs ids.
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import Session

from app.core.auth import AccessDenied, allow_roles
from app.core.config import AuthSettings
from app.core.db import SessionDep
from app.core.sealing import SealExpired, SealInvalid, seal, unseal
from app.core.time_zone import UTC_ZONE, parse_time_zone, read_time_zone, zone_name
from app.models import Role, Subject, User
from app.routers.teacher import render_teacher
from app.schemas.competition import StartErrors, local_parts, parse_start
from app.schemas.names import InvalidName, clean_name
from app.schemas.teachers import MAX_ID
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    CompetitionView,
    DuplicateCompetitionName,
    ManageRequired,
    NotCancellable,
    NotEditable,
    StartNotInFuture,
    SubjectChoices,
    SubjectUnavailable,
    cancel_competition,
    competition_page,
    create_competition,
    get_competition,
    locate,
    offered_subjects,
    parse_status_filter,
    update_competition,
)
from app.services.paging import parse_page
from app.services.teacher_access import can_manage_competitions

router = APIRouter(prefix="/teacher/competitions")

TAB = "competitions"
TAB_PATH = "/teacher/competitions"

SUBJECT_NOT_FOUND = (
    "Subject not found",
    "This subject does not exist, or it is deactivated and has no finished competitions.",
)
COMPETITION_NOT_FOUND = (
    "Competition not found",
    "This competition does not exist, or its subject is deactivated.",
)
"""The not-found page's heading and text."""

FIELD_ORDER = ["name", "start_date", "start_time"]
"""The fields in page order, for the error summary."""

START_NOT_IN_FUTURE = "The start must be in the future."

STATUS_OPTIONS = [("", "All"), *((status.value, status.label) for status in CompetitionStatus)]
"""The Status list: All (no value), then each status."""

EDIT_REFUSALS = {
    CompetitionStatus.IN_PROGRESS: "“{name}” has already started and can no longer be edited.",
    CompetitionStatus.CANCELLED: "“{name}” has been cancelled and can no longer be edited.",
    CompetitionStatus.FINISHED: "“{name}” has finished and can no longer be edited.",
}
CANCEL_REFUSALS = {
    CompetitionStatus.CANCELLED: "“{name}” is already cancelled.",
    CompetitionStatus.FINISHED: "“{name}” has finished and cannot be cancelled.",
}
"""The reason of each refusal, by the competition's status (http-routes.md §4, §6)."""

COMPETITION_NOTICE_PURPOSE = "competition-notice"
COMPETITION_NOTICE_TTL = timedelta(minutes=10)
NOTICES = {
    "added": "Competition “{name}” was added",
    "saved": "Competition “{name}” was saved",
    "cancelled": "Competition “{name}” was cancelled",
}
"""The success notice of each outcome; the name is read when the list is shown."""


def _query(subject_id: int, status: CompetitionStatus | None = None, page: int = 1) -> str:
    """`subject=3&status=upcoming&page=2`, leaving out the status for All and the page for 1."""
    query = f"subject={subject_id}"
    if status is not None:
        query += f"&status={status.value}"
    if page > 1:
        query += f"&page={page}"
    return query


def list_path(
    subject_id: int,
    status: CompetitionStatus | None = None,
    page: int = 1,
    anchor: int | None = None,
    notice: str | None = None,
) -> str:
    """The list of `subject_id` filtered by `status` at `page`, with the sealed `notice`, scrolled
    to `anchor`'s competition when given."""
    path = f"{TAB_PATH}?{_query(subject_id, status, page)}"
    if notice:
        path += f"&notice={notice}"
    if anchor is not None:
        path += f"#competition-{anchor}"
    return path


def _parse_id(raw: str | None) -> int | None:
    """An id from the address or a form: an ASCII integer up to `MAX_ID`, else `None`."""
    if raw is None or not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        return None
    return int(raw)


def _settings(request: Request) -> AuthSettings:
    return request.app.state.settings


def _teacher(request: Request) -> int:
    user: User = request.state.user
    assert user.id is not None
    return user.id


def _can_manage(request: Request, session: SessionDep) -> bool:
    return can_manage_competitions(session, _teacher(request))


def _require_manage(request: Request, session: SessionDep) -> None:
    """The milestone 5 403 page for a teacher without the setting (FR-042)."""
    if not _can_manage(request, session):
        raise AccessDenied(Role.TEACHER)


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _not_found(request: Request, page: tuple[str, str]) -> HTMLResponse:
    heading, text = page
    return render_teacher(
        request,
        "pages/teacher/competition_not_found.html",
        TAB,
        {"heading": heading, "text": text},
        status_code=404,
    )


def _offered(choices: SubjectChoices, raw: str | None) -> Subject | None:
    """The offered subject `raw` names, else `None`."""
    subject_id = _parse_id(raw)
    return choices.get(subject_id) if subject_id is not None else None


def _active_subject(session: Session, raw: str | None) -> Subject | None:
    """The offered subject `raw` names, if it is active: where a competition can be added."""
    subject = _offered(offered_subjects(session), raw)
    return subject if subject is not None and subject.is_active else None


def _competition(session: Session, competition_id: int, subject: Subject) -> CompetitionView | None:
    if competition_id > MAX_ID:
        return None
    assert subject.id is not None
    try:
        return get_competition(session, competition_id, subject.id)
    except CompetitionNotFound:
        return None


# ---------------------------------------------------------------------------------------------
# The notice after a change (research R12)
# ---------------------------------------------------------------------------------------------


def _notice_token(request: Request, competition_id: int, outcome: str) -> str:
    """The `notice` value for the list after a change: the id and the outcome only."""
    payload = {"competition": competition_id, "outcome": outcome}
    return seal(_settings(request).secret_key, COMPETITION_NOTICE_PURPOSE, payload)


def _read_notice(
    request: Request, session: Session, token: str | None, subject: Subject
) -> str | None:
    """The notice for a valid, fresh token whose competition is visible in `subject`, named as
    the database names it now; `None` for anything else, which is not an error."""
    if not token:
        return None
    try:
        payload = unseal(
            _settings(request).secret_key,
            COMPETITION_NOTICE_PURPOSE,
            token,
            COMPETITION_NOTICE_TTL,
        )
    except (SealInvalid, SealExpired):
        return None
    competition_id, outcome = payload.get("competition"), payload.get("outcome")
    if type(competition_id) is not int or outcome not in NOTICES:
        return None
    competition = _competition(session, competition_id, subject)
    if competition is None:
        return None
    return NOTICES[outcome].format(name=competition.name)


# ---------------------------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def competitions_page(
    request: Request,
    session: SessionDep,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """The subject list, then the chosen subject's competitions, latest start first, ten per
    page, filtered by status (FR-010–FR-018). A missing or empty subject is "none chosen", then
    the only offered subject if there is exactly one; any other value that is not an offered
    subject is "Subject not found". An unknown status reads as All; an invalid page as the first,
    one past the end as the last. Opening it changes nothing."""
    choices = offered_subjects(session)
    if not subject:
        selected = choices.only
    else:
        selected = _offered(choices, subject)
        if selected is None:
            return _not_found(request, SUBJECT_NOT_FOUND)
    status_filter = parse_status_filter(status)
    can_manage = _can_manage(request, session)
    context: dict[str, Any] = {
        "subjects": [(s.id, s.name) for s in choices.active],
        "groups": (
            [("Deactivated subjects", [(s.id, s.name) for s in choices.deactivated])]
            if choices.deactivated
            else []
        ),
        "selected": selected,
        "status": status_filter,
        "status_options": STATUS_OPTIONS,
        "can_manage": can_manage,
        "can_add": False,
        "listing": None,
        "notice_text": None,
    }
    if selected is not None:
        assert selected.id is not None
        listing = competition_page(session, selected, status_filter, parse_page(page))
        context |= {
            "listing": listing,
            "can_add": can_manage and selected.is_active,
            "notice_text": _read_notice(request, session, notice, selected),
            "return_query": _query(selected.id, status_filter, listing.paging.number),
            "page_href": f"{TAB_PATH}?{_query(selected.id, status_filter)}&page=",
        }
    return render_teacher(request, "pages/teacher/competitions.html", TAB, context)


# ---------------------------------------------------------------------------------------------
# The add and edit forms
# ---------------------------------------------------------------------------------------------


def _form(
    request: Request,
    subject: Subject,
    status: CompetitionStatus | None,
    page: int,
    values: dict[str, str],
    zone_label: str,
    *,
    competition: CompetitionView | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The add form, or with `competition` the edit form. The subject is named, never offered
    for change (FR-001)."""
    assert subject.id is not None
    competition_id = competition.id if competition is not None else None
    return render_teacher(
        request,
        "pages/teacher/competition_form.html",
        TAB,
        {
            "subject": subject,
            "status_value": status.value if status is not None else "",
            "page": page,
            "competition": competition,
            "values": values,
            "errors": errors or {},
            "field_order": FIELD_ORDER,
            "zone_label": zone_label,
            "back": list_path(subject.id, status, page, anchor=competition_id),
        },
        status_code=status_code,
    )


def _refused(
    request: Request,
    question: str,
    reason: str,
    subject: Subject,
    status: CompetitionStatus | None,
    page: int,
    competition_id: int,
) -> HTMLResponse:
    """The 409 refusal of an edit or a cancellation, with the way back to the competition."""
    assert subject.id is not None
    return render_teacher(
        request,
        "pages/teacher/competition_refused.html",
        TAB,
        {
            "question": question,
            "reason": reason,
            "back": list_path(subject.id, status, page, anchor=competition_id),
        },
        status_code=409,
    )


def _edit_refused(
    request: Request,
    competition: CompetitionView,
    status: CompetitionStatus,
    subject: Subject,
    filter_status: CompetitionStatus | None,
    page: int,
) -> HTMLResponse:
    question = f"Edit competition “{competition.name}”?"
    reason = EDIT_REFUSALS[status].format(name=competition.name)
    return _refused(request, question, reason, subject, filter_status, page, competition.id)


def _cancel_refused(
    request: Request,
    competition: CompetitionView,
    status: CompetitionStatus,
    subject: Subject,
    filter_status: CompetitionStatus | None,
    page: int,
) -> HTMLResponse:
    question = f"Cancel competition “{competition.name}”?"
    reason = CANCEL_REFUSALS[status].format(name=competition.name)
    return _refused(request, question, reason, subject, filter_status, page, competition.id)


def _submitted_zone(raw: str) -> str:
    """The zone the form was shown in, from its hidden field; `UTC` when unknown (FR-022)."""
    return (parse_time_zone(raw) or UTC_ZONE).key


def _field_errors(
    name: str, start_date: str, start_time: str, zone_label: str
) -> tuple[dict[str, str], Any]:
    """Every field error at once, and the start in UTC when it was read."""
    errors: dict[str, str] = {}
    try:
        clean_name(name)
    except InvalidName as invalid:
        errors["name"] = invalid.message
    start = parse_start(start_date, start_time, parse_time_zone(zone_label) or UTC_ZONE)
    if isinstance(start, StartErrors):
        if start.date:
            errors["start_date"] = start.date
        if start.time:
            errors["start_time"] = start.time
        start = None
    return errors, start


@router.get("/new", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def new_competition_page(
    request: Request,
    session: SessionDep,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
) -> HTMLResponse:
    """The empty add form, in the browser's zone (FR-019–FR-021)."""
    _require_manage(request, session)
    selected = _active_subject(session, subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    values = {"name": "", "start_date": "", "start_time": ""}
    zone_label = zone_name(read_time_zone(request))
    return _form(
        request, selected, parse_status_filter(status), parse_page(page), values, zone_label
    )


@router.post("", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def create_competition_action(
    request: Request,
    session: SessionDep,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    name: str = Form(""),
    start_date: str = Form(""),
    start_time: str = Form(""),
    time_zone: str = Form(""),
) -> Response:
    """Adds the competition and lands at it in the list with status All, on its page, with the
    notice (FR-024–FR-026)."""
    _require_manage(request, session)
    selected = _active_subject(session, subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    assert selected.id is not None
    status_filter, return_page = parse_status_filter(status), parse_page(page)
    zone_label = _submitted_zone(time_zone)
    values = {"name": name, "start_date": start_date, "start_time": start_time}
    errors, starts_at = _field_errors(name, start_date, start_time, zone_label)
    if not errors:
        try:
            created = create_competition(session, _teacher(request), selected.id, name, starts_at)
        except ManageRequired:
            raise AccessDenied(Role.TEACHER) from None
        except SubjectUnavailable:
            return _not_found(request, SUBJECT_NOT_FOUND)
        except (InvalidName, DuplicateCompetitionName) as refused:
            errors["name"] = refused.message
        except StartNotInFuture:
            errors["start_date"] = START_NOT_IN_FUTURE
        else:
            landing = locate(session, selected, None, created.id)
            notice = _notice_token(request, created.id, "added")
            return _redirect(list_path(selected.id, None, landing.page, created.id, notice))
    return _form(
        request,
        selected,
        status_filter,
        return_page,
        values,
        zone_label,
        errors=errors,
        status_code=400,
    )


@router.get("/{competition_id:int}/edit", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def edit_competition_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
) -> HTMLResponse:
    """The edit form of an upcoming competition, filled with its name and its start in the
    browser's zone; the refusal for any other status (FR-027–FR-032)."""
    _require_manage(request, session)
    selected = _offered(offered_subjects(session), subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    competition = _competition(session, competition_id, selected)
    if competition is None:
        return _not_found(request, COMPETITION_NOT_FOUND)
    status_filter, return_page = parse_status_filter(status), parse_page(page)
    if competition.status is not CompetitionStatus.UPCOMING:
        return _edit_refused(
            request, competition, competition.status, selected, status_filter, return_page
        )
    zone = read_time_zone(request)
    start_date, start_time = local_parts(competition.starts_at, zone)
    values = {"name": competition.name, "start_date": start_date, "start_time": start_time}
    return _form(
        request,
        selected,
        status_filter,
        return_page,
        values,
        zone_name(zone),
        competition=competition,
    )


@router.post("/{competition_id:int}/edit", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def update_competition_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    name: str = Form(""),
    start_date: str = Form(""),
    start_time: str = Form(""),
    time_zone: str = Form(""),
) -> Response:
    """Saves the name and the start, and lands at the competition on the page that now holds it,
    with the same status, with the notice. Only these fields are read: a `subject` of another
    subject fails the competition check, so a competition never changes subject (FR-001)."""
    _require_manage(request, session)
    selected = _offered(offered_subjects(session), subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    assert selected.id is not None
    competition = _competition(session, competition_id, selected)
    if competition is None:
        return _not_found(request, COMPETITION_NOT_FOUND)
    status_filter, return_page = parse_status_filter(status), parse_page(page)
    if competition.status is not CompetitionStatus.UPCOMING:
        return _edit_refused(
            request, competition, competition.status, selected, status_filter, return_page
        )
    zone_label = _submitted_zone(time_zone)
    values = {"name": name, "start_date": start_date, "start_time": start_time}
    errors, starts_at = _field_errors(name, start_date, start_time, zone_label)
    if not errors:
        try:
            update_competition(
                session, _teacher(request), competition_id, selected.id, name, starts_at
            )
        except ManageRequired:
            raise AccessDenied(Role.TEACHER) from None
        except CompetitionNotFound:
            return _not_found(request, COMPETITION_NOT_FOUND)
        except NotEditable as refused:
            return _edit_refused(
                request, competition, refused.status, selected, status_filter, return_page
            )
        except (InvalidName, DuplicateCompetitionName) as refused:
            errors["name"] = refused.message
        except StartNotInFuture:
            errors["start_date"] = START_NOT_IN_FUTURE
        else:
            landing = locate(session, selected, status_filter, competition_id)
            notice = _notice_token(request, competition_id, "saved")
            return _redirect(
                list_path(selected.id, status_filter, landing.page, landing.competition_id, notice)
            )
    return _form(
        request,
        selected,
        status_filter,
        return_page,
        values,
        zone_label,
        competition=competition,
        errors=errors,
        status_code=400,
    )


# ---------------------------------------------------------------------------------------------
# Cancelling
# ---------------------------------------------------------------------------------------------


@router.get("/{competition_id:int}/cancel", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def cancel_competition_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
) -> HTMLResponse:
    """The confirmation, naming the competition, its subject and its start (FR-033); the
    refusal for a cancelled or finished competition (FR-036)."""
    _require_manage(request, session)
    selected = _offered(offered_subjects(session), subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    assert selected.id is not None
    competition = _competition(session, competition_id, selected)
    if competition is None:
        return _not_found(request, COMPETITION_NOT_FOUND)
    status_filter, return_page = parse_status_filter(status), parse_page(page)
    if competition.status in CANCEL_REFUSALS:
        return _cancel_refused(
            request, competition, competition.status, selected, status_filter, return_page
        )
    return render_teacher(
        request,
        "pages/teacher/competition_cancel.html",
        TAB,
        {
            "competition": competition,
            "subject": selected,
            "status_value": status_filter.value if status_filter is not None else "",
            "page": return_page,
            "back": list_path(selected.id, status_filter, return_page, anchor=competition_id),
        },
    )


@router.post("/{competition_id:int}/cancel", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def cancel_competition_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
) -> Response:
    """Cancels the competition for good and lands where it was in the filtered list: at it while
    the filter shows it, else at the row that took its place, else the one before it, else the
    empty state (FR-034, research R13)."""
    _require_manage(request, session)
    selected = _offered(offered_subjects(session), subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    assert selected.id is not None
    competition = _competition(session, competition_id, selected)
    if competition is None:
        return _not_found(request, COMPETITION_NOT_FOUND)
    status_filter, return_page = parse_status_filter(status), parse_page(page)
    if competition.status in CANCEL_REFUSALS:
        return _cancel_refused(
            request, competition, competition.status, selected, status_filter, return_page
        )
    try:
        landing = cancel_competition(
            session, _teacher(request), competition_id, selected.id, status_filter
        )
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except CompetitionNotFound:
        return _not_found(request, COMPETITION_NOT_FOUND)
    except NotCancellable as refused:
        return _cancel_refused(
            request, competition, refused.status, selected, status_filter, return_page
        )
    notice = _notice_token(request, competition_id, "cancelled")
    return _redirect(
        list_path(selected.id, status_filter, landing.page, landing.competition_id, notice)
    )
