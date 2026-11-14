"""A competition's team answers, on the Competitions tab of the teacher area: the team answers page
(the teacher's own institutions' teams with their progress), a team's answer sheet, and saving it.

See specs/012.3-team-answers/contracts/http-routes.md and research R8–R14, and
specs/012.4-finish-and-grade/contracts/http-routes.md §4–§6 and research R7, R9. Thin handlers only,
as in `teacher_competition_entries`: each reads its values as plain strings (so no input ever gets
FastAPI's 422), calls `app.services.team_answers`, maps its outcomes to a status and a page, and on
success redirects with a 303, so a reload never repeats a save.

**Every teacher opens the team answers page, which lists only the teams of their own reachable
institutions; a teacher with Read or Write access to a team's institution opens its sheet, and
only one with Write access saves it, and only while the competition is In progress.** With Write
access while In progress the sheet is the answer sheet; otherwise it is the read-only sheet: with
Read access while In progress, with the access notice; on a Finished competition, for either
level, with the team's grades and score (milestone 12.4 R7). There is no **Can manage
competitions** check anywhere here (FR-002; milestone 12.4 FR-003).

**Order of checks** (milestone 12.4 http-routes.md §Order of checks: the Answers pages, FR-041):
the role (`@allow_roles`, before any id is read); the subject ("Subject not found") and the
competition ("Competition not found"), 404, through the 12.2 `find_context`; the status: Upcoming
and Cancelled get the refusal (409) on every page and save, In progress opens the pages and accepts
a save, Finished opens the pages read-only and refuses a save (409); on the sheet and the save, the
team ("Team not found") and, on the save, the named questions ("Question not found"), 404; then
access to the team's institution: not linked is 403, Read access reads and its save is 403; then,
on the save, the answers (400). The service's save checks everything again under lock, in the same
order.

**Addresses** (research R10): `subject`, `status` and `page` keep their 12.1 meaning, the
competitions list the teacher came from, and travel through every page, form, refusal and
redirect; `p` is the page of the team answers page; `back` is the page of it the sheet returns
to; `notice` the sealed notice after a save. Every address is built by `answers_path` or
`sheet_path` from looked-up ids and parsed values only, through the 12.2 `address`.

**The form** (research R9): one field per question, `answer-<copy id>`. Every `answer-…` pair of
the body is read, so a name sent twice, or two spellings of one id, is refused as "Question not
found" instead of collapsing to one value.

**The notice after a save** travels as a sealed, 10-minute token holding the competition's and
the team's ids and the outcome; the text is built when the page is shown (research R12), so no
name ever reaches an address or a log line (FR-031). Nothing here logs; the service logs ids.
"""

from collections.abc import Callable, Coroutine
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
    parse_id,
    redirect,
    settings_of,
    teacher_id,
)
from app.schemas.teachers import MAX_ID
from app.services.competitions import CompetitionNotFound, CompetitionStatus, CompetitionView
from app.services.paging import parse_page
from app.services.team_answers import (
    AnswersClosed,
    AnswersDenied,
    AnswerSheet,
    InvalidAnswers,
    QuestionNotFound,
    TeamNotFound,
    answer_sheet,
    answer_team_page,
    save_answers,
    team_page_of,
)

router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")

TEAM_NOT_FOUND = (
    "Team not found",
    "This team does not exist, or it is not in this competition.",
)
QUESTION_NOT_FOUND = ("Question not found", "This question is not in this competition.")
"""The not-found page's heading and text (http-routes.md §Order of checks)."""

ANSWER_REFUSALS = {
    CompetitionStatus.UPCOMING: "“{name}” has not started yet, so its answers cannot be entered"
    " yet.",
    CompetitionStatus.CANCELLED: "“{name}” has been cancelled, so its answers can no longer be"
    " entered.",
    CompetitionStatus.FINISHED: "“{name}” has finished, so its answers can no longer be entered.",
}
"""The reason of the refusal, by the competition's status (http-routes.md §Refusal)."""

ANSWERS_NOTICE_PURPOSE = "team-answers-notice"
ANSWERS_NOTICE_TTL = timedelta(minutes=10)
ANSWER_FIELD_PREFIX = "answer-"


# ---------------------------------------------------------------------------------------------
# Addresses (research R10)
# ---------------------------------------------------------------------------------------------


def answers_path(
    competition_id: int, context: ListContext, p: int = 1, anchor: int | None = None
) -> str:
    """The team answers page at page `p`, scrolled to the `anchor` team:
    `/teacher/competitions/17/answers?subject=3&status=in_progress&page=2&p=3#team-31`."""
    path = f"/teacher/competitions/{competition_id}/answers"
    return address(path, context, p=p, anchor=f"team-{anchor}" if anchor is not None else None)


def sheet_path(
    competition_id: int,
    team_id: int,
    context: ListContext,
    back: int,
    notice: str | None = None,
) -> str:
    """A team's answer sheet, returning to page `back` of the team answers page, with the sealed
    `notice`: `/teacher/competitions/17/answers/31?subject=3&back=3&notice=…`."""
    path = f"/teacher/competitions/{competition_id}/answers/{team_id}"
    return address(path, context, back=back, notice=notice)


def back_page(raw: str | None) -> int | None:
    """The `back` page from the address or the form, `None` when it is missing or invalid."""
    if raw is None or not raw.isascii() or not raw.isdigit() or not raw.strip("0"):
        return None
    return parse_page(raw)


# ---------------------------------------------------------------------------------------------
# The notice after a save (research R12)
# ---------------------------------------------------------------------------------------------


def answers_notice_token(request: Request, competition_id: int, team_id: int) -> str:
    """The `notice` value after a save: ids and the outcome only."""
    payload = {"competition": competition_id, "team": team_id, "outcome": "saved"}
    return seal(settings_of(request).secret_key, ANSWERS_NOTICE_PURPOSE, payload)


def read_answers_notice(
    request: Request, token: str | None, competition_id: int, team_id: int, team_name: str
) -> str | None:
    """ "Answers of “<team>” were saved" for a valid, fresh token of this competition and team,
    the team named as the database names it now; `None` for anything else, which is not an
    error."""
    if not token:
        return None
    try:
        payload = unseal(
            settings_of(request).secret_key, ANSWERS_NOTICE_PURPOSE, token, ANSWERS_NOTICE_TTL
        )
    except (SealInvalid, SealExpired):
        return None
    competition, team = payload.get("competition"), payload.get("team")
    if type(competition) is not int or type(team) is not int:
        return None
    if (competition, team) != (competition_id, team_id) or payload.get("outcome") != "saved":
        return None
    return f"Answers of “{team_name}” were saved"


# ---------------------------------------------------------------------------------------------
# The refusal (http-routes.md §Refusal) and the first checks
# ---------------------------------------------------------------------------------------------


def answers_refused(
    request: Request,
    competition: CompetitionView,
    status: CompetitionStatus,
    context: ListContext,
) -> HTMLResponse:
    """The 409 refusal for a competition that is not In progress, with the way back to the
    competitions list, at the competition, as the 12.1 edit refusal (FR-026)."""
    return render_teacher(
        request,
        "pages/teacher/competition_refused.html",
        TAB,
        {
            "question": f"Enter answers for “{competition.name}”?",
            "reason": ANSWER_REFUSALS[status].format(name=competition.name),
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
    *,
    saving: bool = False,
) -> tuple[ListContext, CompetitionView] | HTMLResponse:
    """Checks 2–3: the context and the competition, or the not-found page; then the refusal for an
    Upcoming or Cancelled competition, and, when `saving`, for a Finished one too (milestone 12.4
    FR-041): its pages open read-only."""
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    opens = (CompetitionStatus.IN_PROGRESS,) if saving else _PAGE_STATUSES
    if competition.status not in opens:
        return answers_refused(request, competition, competition.status, context)
    return context, competition


_PAGE_STATUSES = (CompetitionStatus.IN_PROGRESS, CompetitionStatus.FINISHED)
"""The statuses whose Answers pages open (milestone 12.4 FR-041)."""


# ---------------------------------------------------------------------------------------------
# The team answers page
# ---------------------------------------------------------------------------------------------


@router.get("/answers", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def competition_answers_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    p: str | None = Query(None),
) -> HTMLResponse:
    """The competition's teams of the teacher's reachable institutions in region boxes, ten per
    page, each with its progress and **Enter answers** (Write, In progress) or **View answers**
    (FR-004–FR-013; milestone 12.4 R7); on a Finished competition, also **Graded** and **Score**
    (milestone 12.4 FR-037). Opening it changes nothing."""
    opened = _open(request, session, competition_id, subject, status, page)
    if isinstance(opened, HTMLResponse):
        return opened
    context, competition = opened
    finished = competition.status is CompetitionStatus.FINISHED
    listing = answer_team_page(
        session, teacher_id(request), competition.id, parse_page(p), finished=finished
    )
    current = listing.paging.number
    sheet_hrefs = {
        row.team_id: sheet_path(competition.id, row.team_id, context, back=current)
        for group in listing.groups
        for row in group.rows
    }
    return render_competition_page(
        request,
        "pages/teacher/competition_answers.html",
        competition,
        context,
        {
            "listing": listing,
            "sheet_hrefs": sheet_hrefs,
            "back": context.back_to_list(competition.id),
            "page_href": page_prefix(answers_path(competition.id, context)),
        },
    )


# ---------------------------------------------------------------------------------------------
# The answer sheet
# ---------------------------------------------------------------------------------------------


def prefixed_fields(
    prefix: str,
) -> Callable[[Request], Coroutine[Any, Any, list[tuple[str, str]]]]:
    """A dependency reading every `<prefix>…` pair of the form, in the order sent, repeated names
    included (research R9; milestone 12.4 research R9 shares it with the grades): never a `dict`,
    which would keep one value per name and hide a repeated field. The body is parsed once;
    Starlette caches it for the other form values."""

    async def fields(request: Request) -> list[tuple[str, str]]:
        form = await request.form()
        return [
            (name, value)
            for name, value in form.multi_items()
            if name.startswith(prefix) and isinstance(value, str)
        ]

    return fields


AnswerFields = Annotated[list[tuple[str, str]], Depends(prefixed_fields(ANSWER_FIELD_PREFIX))]


def parse_prefixed(fields: list[tuple[str, str]], prefix: str) -> dict[int, str] | None:
    """The values by `competition_question_id`, or `None` when a name's suffix is not an id or
    names a question already given (the same name twice, or `<prefix>41` and `<prefix>041`)."""
    values: dict[int, str] = {}
    for name, value in fields:
        question_id = parse_id(name.removeprefix(prefix))
        if question_id is None or question_id in values:
            return None
        values[question_id] = value
    return values


def _render_sheet(
    request: Request,
    competition: CompetitionView,
    context: ListContext,
    sheet: AnswerSheet,
    back: int,
    *,
    sent: dict[int, str] | None = None,
    errors: dict[int, str] | None = None,
    notice: str | None = None,
) -> HTMLResponse:
    """The sheet: every question with the team's saved answer, or after a refused save, the text
    as it was sent for each question the form named, each error at its field and the summary in
    question order (research R13)."""
    sent, errors = sent or {}, errors or {}
    items = [
        {
            "number": q.number,
            "field_id": f"{ANSWER_FIELD_PREFIX}{q.competition_question_id}",
            "text": q.text,
            "value": sent.get(q.competition_question_id, q.answer),
            "error": errors.get(q.competition_question_id),
        }
        for q in sheet.questions
    ]
    field_errors: dict[str, Any] = {
        item["field_id"]: item["error"] for item in items if item["error"]
    }
    return render_competition_page(
        request,
        "pages/teacher/team_answer_sheet.html",
        competition,
        context,
        {
            "sheet": sheet,
            "items": items,
            "action": f"/teacher/competitions/{competition.id}/answers/{sheet.team_id}",
            "hidden": context.hidden() | {"back": back},
            "back": answers_path(competition.id, context, p=back, anchor=sheet.team_id),
            "errors": field_errors,
            "field_order": [item["field_id"] for item in items],
            "notice": notice,
        },
        status_code=400 if errors else 200,
    )


def _render_read_only(
    request: Request,
    competition: CompetitionView,
    context: ListContext,
    sheet: AnswerSheet,
    back: int,
) -> HTMLResponse:
    """The read-only sheet (milestone 12.4 http-routes.md §5): every question with the team's
    answer, never a field; with Read access while In progress, the access notice; on a Finished
    competition, the team's score and each answer's grade. Never a reference answer."""
    items = [
        {
            "number": q.number,
            "text": q.text,
            "answer": q.answer or None,
            "grade": q.grade,
        }
        for q in sheet.questions
    ]
    return render_competition_page(
        request,
        "pages/teacher/team_answers_read_only.html",
        competition,
        context,
        {
            "sheet": sheet,
            "items": items,
            "back": answers_path(competition.id, context, p=back, anchor=sheet.team_id),
        },
    )


@router.get("/answers/{team_id:int}", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def team_answer_sheet_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    team_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    back: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """A team's answer sheet: every question of the competition with its answer field, and one
    **Save answers** (FR-014–FR-021), for a Write institution's team while In progress; otherwise
    the read-only sheet (milestone 12.4 R7). The reference answer never. Opening it changes
    nothing."""
    opened = _open(request, session, competition_id, subject, status, page)
    if isinstance(opened, HTMLResponse):
        return opened
    context, competition = opened
    if team_id > MAX_ID:
        return not_found(request, TEAM_NOT_FOUND)
    teacher = teacher_id(request)
    finished = competition.status is CompetitionStatus.FINISHED
    try:
        sheet = answer_sheet(session, teacher, competition.id, team_id, finished=finished)
    except TeamNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    except AnswersDenied:
        raise AccessDenied(Role.TEACHER) from None
    back_to = back_page(back) or team_page_of(session, teacher, competition.id, team_id)
    if finished or not sheet.can_write:
        return _render_read_only(request, competition, context, sheet, back_to)
    return _render_sheet(
        request,
        competition,
        context,
        sheet,
        back_to,
        notice=read_answers_notice(request, notice, competition.id, team_id, sheet.team_name),
    )


@router.post("/answers/{team_id:int}", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def save_team_answers_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    team_id: int,
    fields: AnswerFields,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    back: str = Form(""),
) -> Response:
    """Saves every answer of the sheet at once and stays on it with the notice, also when
    nothing changed (FR-017, FR-020, FR-024); answers that are too long save nothing and show the
    sheet again with every text as sent (FR-019). A Finished competition is refused before the
    team is read (milestone 12.4 FR-040)."""
    opened = _open(request, session, competition_id, subject, status, page, saving=True)
    if isinstance(opened, HTMLResponse):
        return opened
    context, competition = opened
    if team_id > MAX_ID:
        return not_found(request, TEAM_NOT_FOUND)
    answers = parse_prefixed(fields, ANSWER_FIELD_PREFIX)
    if answers is None:
        return not_found(request, QUESTION_NOT_FOUND)
    teacher = teacher_id(request)
    back_to = back_page(back) or team_page_of(session, teacher, competition.id, team_id)
    assert context.subject.id is not None
    try:
        save_answers(session, teacher, competition.id, context.subject.id, team_id, answers)
    except CompetitionNotFound:
        return not_found(request, COMPETITION_NOT_FOUND)
    except AnswersClosed as refused:
        return answers_refused(request, competition, refused.status, context)
    except TeamNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    except QuestionNotFound:
        return not_found(request, QUESTION_NOT_FOUND)
    except AnswersDenied:
        raise AccessDenied(Role.TEACHER) from None
    except InvalidAnswers as invalid:
        try:
            sheet = answer_sheet(session, teacher, competition.id, team_id)
        except TeamNotFound:
            return not_found(request, TEAM_NOT_FOUND)
        except AnswersDenied:
            raise AccessDenied(Role.TEACHER) from None
        return _render_sheet(
            request, competition, context, sheet, back_to, sent=answers, errors=invalid.errors
        )
    token = answers_notice_token(request, competition.id, team_id)
    return redirect(sheet_path(competition.id, team_id, context, back_to, notice=token))
