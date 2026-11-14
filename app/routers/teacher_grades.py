"""A finished competition's grades, on the Competitions tab of the teacher area: the Grades page
(every team with its progress), a team's grading sheet, and saving it.

See specs/012.4-finish-and-grade/contracts/http-routes.md §1–§3 and research R6, R8, R9, R11. Thin
handlers only, as in `teacher_team_answers`: each reads its values as plain strings (so no input
ever gets FastAPI's 422), calls `app.services.grades`, maps its outcomes to a status and a page,
and on success redirects with a 303, so a reload never repeats a save.

**Only a teacher with Can manage competitions grades, every team of the competition whatever
their links, and only once the competition is Finished.** Every route here is a *manage* route.

**Order of checks** (http-routes.md §Order of checks, FR-043): the role (`@allow_roles`, before any
id is read); the setting, first thing in the handler, before any value is parsed (403 for an
unknown id too); the subject ("Subject not found") and the competition ("Competition not found"),
404, through the 12.2 `find_context`; the status (the refusal, 409); on the sheet and the save,
the team ("Team not found") and, on the save, the named questions ("Question not found"), 404;
then, on the save, the grades (400). The service's save checks everything again under lock, in the
same order. A deleted team, or one of a deactivated institution or region, is found and graded.

**Addresses** (http-routes.md §Address parameters): `subject`, `status` and `page` keep their 12.1
meaning, the competitions list the teacher came from; `p` is the page of the Grades page; `show`
is its filter (`ungraded` for **Ungraded only**, left out for **All teams**); `back` is the page of
it the sheet returns to; `notice` the sealed notice after a save. Every address is built by
`grades_path` or `grading_sheet_path` from looked-up ids and parsed values only, through the 12.2
`address`.

**The form** (research R9): one field per answered question, `grade-<copy id>`, read through the
12.3 `prefixed_fields`, so a name sent twice, or two spellings of one id, is "Question not found".

**The notice after a save** travels as a sealed, 10-minute token holding the competition's and the
team's ids and the outcome; the text is built when the page is shown (research R11), so no name
ever reaches an address or a log line (FR-045). Nothing here logs; the service logs ids.
"""

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from app.core.auth import AccessDenied, allow_roles
from app.core.db import SessionDep
from app.core.sealing import SealExpired, SealInvalid, seal, unseal
from app.models import Role
from app.routers.teacher import render_teacher
from app.routers.teacher_competition_entries import (
    ListContext,
    address,
    find_context,
    page_prefix,
    render_competition_page,
)
from app.routers.teacher_competitions import (
    COMPETITION_NOT_FOUND,
    TAB,
    not_found,
    redirect,
    require_manage,
    settings_of,
    teacher_id,
)
from app.routers.teacher_team_answers import (
    QUESTION_NOT_FOUND,
    TEAM_NOT_FOUND,
    back_page,
    parse_prefixed,
    prefixed_fields,
)
from app.schemas.teachers import MAX_ID
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    CompetitionView,
    ManageRequired,
)
from app.services.grades import (
    GradedQuestionNotFound,
    GradedTeamNotFound,
    GradeFilter,
    GradingClosed,
    GradingSheet,
    InvalidGrades,
    grade_team_page,
    grading_sheet,
    is_listed,
    parse_grade_filter,
    save_grades,
    team_page_of,
)
from app.services.paging import parse_page

router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")

GRADE_REFUSALS = {
    CompetitionStatus.UPCOMING: "“{name}” has not started yet, so its answers cannot be graded.",
    CompetitionStatus.IN_PROGRESS: "“{name}” is still in progress, so its answers cannot be graded"
    " until it is finished.",
    CompetitionStatus.CANCELLED: "“{name}” has been cancelled, so its answers cannot be graded.",
}
"""The reason of the refusal, by the competition's status (http-routes.md §Refusals)."""

GRADES_NOTICE_PURPOSE = "grades-notice"
GRADES_NOTICE_TTL = timedelta(minutes=10)
GRADE_FIELD_PREFIX = "grade-"

GradeFields = Annotated[list[tuple[str, str]], Depends(prefixed_fields(GRADE_FIELD_PREFIX))]


# ---------------------------------------------------------------------------------------------
# Addresses (http-routes.md §Address parameters)
# ---------------------------------------------------------------------------------------------


def _show(show: GradeFilter) -> str | None:
    """The `show` value of the address: `ungraded`, or nothing for **All teams**."""
    return show.value if show is GradeFilter.UNGRADED else None


def grades_path(
    competition_id: int,
    context: ListContext,
    show: GradeFilter,
    p: int = 1,
    anchor: int | None = None,
) -> str:
    """The Grades page under `show` at page `p`, scrolled to the `anchor` team:
    `/teacher/competitions/17/grades?subject=3&status=finished&page=2&show=ungraded&p=2#team-31`."""
    path = f"/teacher/competitions/{competition_id}/grades"
    anchor_id = f"team-{anchor}" if anchor is not None else None
    return address(path, context, show=_show(show), p=p, anchor=anchor_id)


def grading_sheet_path(
    competition_id: int,
    team_id: int,
    context: ListContext,
    show: GradeFilter,
    back: int,
    notice: str | None = None,
) -> str:
    """A team's grading sheet, returning to page `back` of the Grades page under `show`, with the
    sealed `notice`:
    `/teacher/competitions/17/grades/31?subject=3&back=2&show=ungraded&notice=…`."""
    path = f"/teacher/competitions/{competition_id}/grades/{team_id}"
    return address(path, context, back=back, show=_show(show), notice=notice)


# ---------------------------------------------------------------------------------------------
# The notice after a save (research R11)
# ---------------------------------------------------------------------------------------------


def grades_notice_token(request: Request, competition_id: int, team_id: int) -> str:
    """The `notice` value after a save: ids and the outcome only."""
    payload = {"competition": competition_id, "team": team_id, "outcome": "saved"}
    return seal(settings_of(request).secret_key, GRADES_NOTICE_PURPOSE, payload)


def read_grades_notice(
    request: Request, token: str | None, competition_id: int, team_id: int, team_name: str
) -> str | None:
    """ "Grades of “<team>” were saved" for a valid, fresh token of this competition and team, the
    team named as the database names it now; `None` for anything else, which is not an error."""
    if not token:
        return None
    try:
        payload = unseal(
            settings_of(request).secret_key, GRADES_NOTICE_PURPOSE, token, GRADES_NOTICE_TTL
        )
    except (SealInvalid, SealExpired):
        return None
    competition, team = payload.get("competition"), payload.get("team")
    if type(competition) is not int or type(team) is not int:
        return None
    if (competition, team) != (competition_id, team_id) or payload.get("outcome") != "saved":
        return None
    return f"Grades of “{team_name}” were saved"


# ---------------------------------------------------------------------------------------------
# The refusal (http-routes.md §Refusals) and the first checks
# ---------------------------------------------------------------------------------------------


def grades_refused(
    request: Request,
    competition: CompetitionView,
    status: CompetitionStatus,
    context: ListContext,
) -> HTMLResponse:
    """The 409 refusal for a competition that is not Finished, with the way back to the
    competitions list, at the competition (FR-039)."""
    return render_teacher(
        request,
        "pages/teacher/competition_refused.html",
        TAB,
        {
            "question": f"Grade answers of “{competition.name}”?",
            "reason": GRADE_REFUSALS[status].format(name=competition.name),
            "back": context.back_to_list(competition.id),
            "back_link_text": "Back to the competitions",
            "back_text": "Back to competitions",
        },
        status_code=409,
    )


def _open(
    request: Request,
    session: Session,
    competition_id: int,
    subject: str | None,
    status: str | None,
    page: str | None,
) -> tuple[ListContext, CompetitionView] | HTMLResponse:
    """Checks 2–4: the setting (403, raised before any value is parsed); the context and the
    competition, or the not-found page; then the refusal for a competition that is not
    Finished."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    if competition.status is not CompetitionStatus.FINISHED:
        return grades_refused(request, competition, competition.status, context)
    return context, competition


# ---------------------------------------------------------------------------------------------
# The Grades page (http-routes.md §1)
# ---------------------------------------------------------------------------------------------


@router.get("/grades", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def competition_grades_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    p: str | None = Query(None),
    show: str | None = Query(None),
) -> HTMLResponse:
    """Every team of the finished competition in region boxes, ten per page, each with
    **Answered**, **Graded**, **Score** and **Grade answers**, the overall progress, and the
    filter links **All teams** / **Ungraded only** (FR-014–FR-020). Opening it changes
    nothing."""
    opened = _open(request, session, competition_id, subject, status, page)
    if isinstance(opened, HTMLResponse):
        return opened
    context, competition = opened
    shown = parse_grade_filter(show)
    listing = grade_team_page(session, competition.id, shown, parse_page(p))
    current = listing.paging.number
    grade_hrefs = {
        row.team_id: grading_sheet_path(competition.id, row.team_id, context, shown, current)
        for group in listing.groups
        for row in group.rows
    }
    filter_links = [
        (
            "All teams",
            grades_path(competition.id, context, GradeFilter.ALL),
            shown is GradeFilter.ALL,
        ),
        (
            "Ungraded only",
            grades_path(competition.id, context, GradeFilter.UNGRADED),
            shown is GradeFilter.UNGRADED,
        ),
    ]
    return render_competition_page(
        request,
        "pages/teacher/competition_grades.html",
        competition,
        context,
        {
            "listing": listing,
            "grade_hrefs": grade_hrefs,
            "filter_links": filter_links,
            "back": context.back_to_list(competition.id),
            "page_href": page_prefix(grades_path(competition.id, context, shown)),
        },
    )


# ---------------------------------------------------------------------------------------------
# The grading sheet (http-routes.md §2–§3)
# ---------------------------------------------------------------------------------------------


def _render_sheet(
    request: Request,
    session: Session,
    competition: CompetitionView,
    context: ListContext,
    sheet: GradingSheet,
    show: GradeFilter,
    back: int,
    *,
    sent: dict[int, str] | None = None,
    errors: dict[int, str] | None = None,
    notice: str | None = None,
) -> HTMLResponse:
    """The sheet: every question with its reference answer and the team's answer, a grade field
    under each answered one holding the saved grade, or after a refused save, the value as it was
    sent, each error at its field and the summary in question order."""
    sent, errors = sent or {}, errors or {}
    items = []
    for q in sheet.questions:
        saved = str(q.grade) if q.grade is not None else ""
        items.append(
            {
                "number": q.number,
                "text": q.text,
                "reference_answer": q.reference_answer,
                "answer": q.answer,
                "field_id": f"{GRADE_FIELD_PREFIX}{q.competition_question_id}",
                "value": sent.get(q.competition_question_id, saved),
                "error": errors.get(q.competition_question_id),
            }
        )
    field_errors: dict[str, Any] = {
        item["field_id"]: item["error"] for item in items if item["error"]
    }
    listed = is_listed(session, competition.id, sheet.team_id, show)
    return render_competition_page(
        request,
        "pages/teacher/team_grading_sheet.html",
        competition,
        context,
        {
            "sheet": sheet,
            "items": items,
            "action": f"/teacher/competitions/{competition.id}/grades/{sheet.team_id}",
            "hidden": context.hidden() | {"show": _show(show) or "", "back": back},
            "back": grades_path(
                competition.id, context, show, p=back, anchor=sheet.team_id if listed else None
            ),
            "errors": field_errors,
            "field_order": [item["field_id"] for item in items if item["answer"] is not None],
            "notice": notice,
        },
        status_code=400 if errors else 200,
    )


@router.get("/grades/{team_id:int}", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def team_grading_sheet_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    team_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    show: str | None = Query(None),
    back: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """A team's grading sheet: every question with its reference answer, the team's answer and a
    grade field, and one **Save grades** (FR-021–FR-024). Opening it changes nothing."""
    opened = _open(request, session, competition_id, subject, status, page)
    if isinstance(opened, HTMLResponse):
        return opened
    context, competition = opened
    if team_id > MAX_ID:
        return not_found(request, TEAM_NOT_FOUND)
    try:
        sheet = grading_sheet(session, competition.id, team_id)
    except GradedTeamNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    shown = parse_grade_filter(show)
    back_to = back_page(back) or team_page_of(session, competition.id, team_id, shown)
    return _render_sheet(
        request,
        session,
        competition,
        context,
        sheet,
        shown,
        back_to,
        notice=read_grades_notice(request, notice, competition.id, team_id, sheet.team_name),
    )


@router.post("/grades/{team_id:int}", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def save_grades_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    team_id: int,
    fields: GradeFields,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    show: str = Form(""),
    back: str = Form(""),
) -> Response:
    """Saves every grade of the sheet at once and stays on it with the notice, also when nothing
    changed (FR-024, FR-026); an invalid grade saves nothing and shows the sheet again with every
    value as sent (FR-025)."""
    opened = _open(request, session, competition_id, subject, status, page)
    if isinstance(opened, HTMLResponse):
        return opened
    context, competition = opened
    if team_id > MAX_ID:
        return not_found(request, TEAM_NOT_FOUND)
    grades = parse_prefixed(fields, GRADE_FIELD_PREFIX)
    if grades is None:
        return not_found(request, QUESTION_NOT_FOUND)
    shown = parse_grade_filter(show)
    back_to = back_page(back) or team_page_of(session, competition.id, team_id, shown)
    assert context.subject.id is not None
    try:
        save_grades(
            session, teacher_id(request), competition.id, context.subject.id, team_id, grades
        )
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except CompetitionNotFound:
        return not_found(request, COMPETITION_NOT_FOUND)
    except GradingClosed as refused:
        return grades_refused(request, competition, refused.status, context)
    except GradedTeamNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    except GradedQuestionNotFound:
        return not_found(request, QUESTION_NOT_FOUND)
    except InvalidGrades as invalid:
        try:
            sheet = grading_sheet(session, competition.id, team_id)
        except GradedTeamNotFound:
            return not_found(request, TEAM_NOT_FOUND)
        return _render_sheet(
            request,
            session,
            competition,
            context,
            sheet,
            shown,
            back_to,
            sent=grades,
            errors=invalid.errors,
        )
    token = grades_notice_token(request, competition.id, team_id)
    return redirect(
        grading_sheet_path(competition.id, team_id, context, shown, back_to, notice=token)
    )
