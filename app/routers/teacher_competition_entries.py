"""A competition's questions and teams, on the Competitions tab of the teacher area: the two lists,
"Add questions" and "Add teams", and removing a question or a team.

See specs/012.2-competition-questions-teams/contracts/http-routes.md and research R7–R12, R14.
Thin handlers only, as in `teacher_competitions`: each reads its values as plain strings (so no
input ever gets FastAPI's 422), calls `app.services.competition_entries`, maps its outcomes to a
status and a page, and on success redirects with a 303, so a reload never repeats a change.

**Every teacher reads both lists; only a teacher with Can manage competitions changes them, and
only while the competition is Upcoming.** The add pages, the additions, the remove confirmations
and the removals are *manage* routes.

**Order of checks** (http-routes.md §Order of checks): the role (`@allow_roles`); then, on a
manage route, the setting, first thing in the handler, before any value is parsed (403 for an
unknown id too); then the subject ("Subject not found") and the competition ("Competition not
found"), 404; then, on a manage route, the status (the refusal, 409); then the region, the
question or the team (404); then the service write, which checks the setting, the competition,
the status and the entry again under lock.

**Addresses** (research R8): `subject`, `status` and `page` keep their 12.1 meaning, the
competitions list the teacher came from, and travel through every page, form, refusal and
redirect, so the back link always leads to that list; a missing `subject` falls back to the
competition's own subject, the status All and the page holding it. `p` is the page of the list a
page shows; `back` is the page of the competition's list the add pages and confirmations return
to; `region` is the region of "Add teams". Every address is built by `entries_path`,
`add_page_path` or `remove_path` from looked-up ids and parsed values only.

**The notice after a change** travels as a sealed, 10-minute token holding the competition's id,
the question's or team's id and the outcome; the texts are built when the page is shown (research
R9), so no name ever reaches an address or a log line (FR-048). Nothing here logs; the service
logs ids.

**Shared with milestones 12.3 and 12.4**: `teacher_team_answers` (a competition's team answers)
and `teacher_grades` (its grades) import `ListContext`, `find_context`, `render_competition_page`,
`address` and `page_prefix`, so the three routers build the same addresses and pages.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from app.core.auth import AccessDenied, allow_roles
from app.core.db import SessionDep
from app.core.sealing import SealExpired, SealInvalid, seal, unseal
from app.models import Region, Role, Subject, Team
from app.routers.teacher import render_teacher
from app.routers.teacher_competitions import (
    COMPETITION_NOT_FOUND,
    SUBJECT_NOT_FOUND,
    TAB,
    can_manage,
    find_competition,
    list_path,
    list_query,
    not_found,
    offered_subject,
    parse_id,
    redirect,
    require_manage,
    settings_of,
    teacher_id,
)
from app.schemas.teachers import MAX_ID
from app.services import questions as question_bank
from app.services.competition_entries import (
    AlreadyIn,
    EntryNotFound,
    NotChangeable,
    NotIn,
    add_question,
    add_team,
    addable_teams,
    get_competition_question,
    get_competition_team,
    question_ids,
    question_page,
    remove_question,
    remove_team,
    team_ids,
    team_page,
)
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    CompetitionView,
    ManageRequired,
    locate,
    offered_subjects,
    parse_status_filter,
    subject_id_of,
)
from app.services.paging import parse_page
from app.services.regions import list_active_regions

router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")

ListKind = Literal["questions", "teams"]
"""The list an address names; its entries are a `question` or a `team`."""

REGION_NOT_FOUND = ("Region not found", "This region does not exist, or it is deactivated.")
QUESTION_NOT_FOUND = (
    "Question not found",
    "This question does not exist, or it cannot be added to this competition.",
)
TEAM_NOT_FOUND = (
    "Team not found",
    "This team does not exist, or it cannot be added to this competition.",
)
"""The not-found page's heading and text (http-routes.md §Order of checks)."""

ENTRY_REFUSALS = {
    CompetitionStatus.IN_PROGRESS: "“{name}” has already started and its {kind} can no longer be"
    " changed.",
    CompetitionStatus.CANCELLED: "“{name}” has been cancelled and its {kind} can no longer be"
    " changed.",
    CompetitionStatus.FINISHED: "“{name}” has finished and its {kind} can no longer be changed.",
}
"""The reason of the refusal, by the competition's status (http-routes.md §Refusal)."""

ENTRY_NOTICE_PURPOSE = "competition-entry-notice"
ENTRY_NOTICE_TTL = timedelta(minutes=10)
ENTRY_NOTICES = {
    "added": ("{entry} was added to “{name}”", "success"),
    "already": ("{entry} is already in “{name}”", "info"),
    "removed": ("{entry} was removed from “{name}”", "success"),
    "absent": ("{entry} is not in “{name}”", "info"),
}
"""The notice of each outcome, with its kind (research R9); `entry` is "Question 12" or
"Team “Comets”", read when the page is shown."""

BACK_LINKS = {"questions": "Back to the questions", "teams": "Back to the teams"}


# ---------------------------------------------------------------------------------------------
# The competitions-list context and the addresses (research R8)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ListContext:
    """The competitions list the teacher came from: its subject, status filter and page."""

    subject: Subject
    status: CompetitionStatus | None
    page: int

    @property
    def query(self) -> str:
        assert self.subject.id is not None
        return list_query(self.subject.id, self.status, self.page)

    def hidden(self) -> dict[str, Any]:
        """The context as a form's hidden fields."""
        return {
            "subject": self.subject.id,
            "status": self.status.value if self.status is not None else "",
            "page": self.page,
        }

    def back_to_list(self, competition_id: int) -> str:
        """The competitions list, at the competition: the back link of both lists (FR-004)."""
        assert self.subject.id is not None
        return list_path(self.subject.id, self.status, self.page, anchor=competition_id)


def _entry(kind: ListKind) -> str:
    return "question" if kind == "questions" else "team"


def address(
    path: str,
    context: ListContext,
    *,
    back: int = 1,
    region: int | None = None,
    p: int = 1,
    show: str | None = None,
    notice: str | None = None,
    anchor: str | None = None,
) -> str:
    """`path` with the context, then `back`, `region`, `show` (the Grades page's filter,
    milestone 12.4) and `p` (each left out at its default), the notice and the anchor."""
    built = f"{path}?{context.query}"
    if back > 1:
        built += f"&back={back}"
    if region is not None:
        built += f"&region={region}"
    if show:
        built += f"&show={show}"
    if p > 1:
        built += f"&p={p}"
    if notice:
        built += f"&notice={notice}"
    if anchor:
        built += f"#{anchor}"
    return built


def _anchor(kind: ListKind, entry_id: int | None) -> str | None:
    return f"{_entry(kind)}-{entry_id}" if entry_id is not None else None


def entries_path(
    kind: ListKind,
    competition_id: int,
    context: ListContext,
    p: int = 1,
    anchor: int | None = None,
    notice: str | None = None,
) -> str:
    """The competition's questions or teams at page `p`, with the sealed `notice`, scrolled to
    the `anchor` entry: `/teacher/competitions/17/questions?subject=3&p=2#question-12`."""
    path = f"/teacher/competitions/{competition_id}/{kind}"
    return address(path, context, p=p, notice=notice, anchor=_anchor(kind, anchor))


def add_page_path(
    kind: ListKind,
    competition_id: int,
    context: ListContext,
    back: int,
    p: int = 1,
    region: int | None = None,
    anchor: int | None = None,
    notice: str | None = None,
) -> str:
    """ "Add questions" or "Add teams" at page `p` (of `region`), returning to page `back` of the
    competition's list."""
    path = f"/teacher/competitions/{competition_id}/{kind}/add"
    return address(
        path, context, back=back, region=region, p=p, notice=notice, anchor=_anchor(kind, anchor)
    )


def remove_path(
    kind: ListKind, competition_id: int, entry_id: int, context: ListContext, back: int
) -> str:
    """The remove confirmation of one question or team, returning to page `back`."""
    path = f"/teacher/competitions/{competition_id}/{kind}/{entry_id}/remove"
    return address(path, context, back=back)


def page_prefix(path: str) -> str:
    """The address `path` a page number completes, for the page navigation."""
    return f"{path}&p="


# ---------------------------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------------------------


def _fallback(session: Session, competition_id: int) -> ListContext | None:
    """With no subject in the address: the competition's own subject, if offered, the status All
    and the page that holds the competition (spec Edge Cases, Assumptions)."""
    subject_id = subject_id_of(session, competition_id) if competition_id <= MAX_ID else None
    subject = offered_subjects(session).get(subject_id) if subject_id is not None else None
    if subject is None:
        return None
    return ListContext(subject, None, locate(session, subject, None, competition_id).page)


def find_context(
    request: Request,
    session: Session,
    competition_id: int,
    raw_subject: str | None,
    raw_status: str | None,
    raw_page: str | None,
) -> tuple[ListContext, CompetitionView] | HTMLResponse:
    """Check 3: the context and the competition, or the not-found page. A missing or empty
    subject falls back to the competition's own (`_fallback`); any other subject that is not
    offered is "Subject not found"; a competition unknown, of another subject or hidden is
    "Competition not found"."""
    if not raw_subject:
        context = _fallback(session, competition_id)
        if context is None:
            return not_found(request, COMPETITION_NOT_FOUND)
    else:
        subject = offered_subject(offered_subjects(session), raw_subject)
        if subject is None:
            return not_found(request, SUBJECT_NOT_FOUND)
        context = ListContext(subject, parse_status_filter(raw_status), parse_page(raw_page))
    competition = find_competition(session, competition_id, context.subject)
    if competition is None:
        return not_found(request, COMPETITION_NOT_FOUND)
    return context, competition


def _region(regions: list[Region], raw: str) -> Region | None:
    """The active region `raw` names, else `None`."""
    region_id = parse_id(raw)
    return next((region for region in regions if region.id == region_id), None)


# ---------------------------------------------------------------------------------------------
# The notice after a change (research R9)
# ---------------------------------------------------------------------------------------------


def entry_notice_token(
    request: Request, competition_id: int, kind: ListKind, entry_id: int, outcome: str
) -> str:
    """The `notice` value after a change: ids and the outcome only."""
    payload = {"competition": competition_id, _entry(kind): entry_id, "outcome": outcome}
    return seal(settings_of(request).secret_key, ENTRY_NOTICE_PURPOSE, payload)


def read_entry_notice(
    request: Request,
    session: Session,
    token: str | None,
    competition: CompetitionView,
    kind: ListKind,
) -> tuple[str, str] | None:
    """The notice text and its kind for a valid, fresh token of this competition and this kind
    of entry, the team named as the database names it now, deleted or not; `None` for anything
    else, which is not an error."""
    if not token:
        return None
    try:
        payload = unseal(
            settings_of(request).secret_key, ENTRY_NOTICE_PURPOSE, token, ENTRY_NOTICE_TTL
        )
    except (SealInvalid, SealExpired):
        return None
    entry_id, outcome = payload.get(_entry(kind)), payload.get("outcome")
    if payload.get("competition") != competition.id or outcome not in ENTRY_NOTICES:
        return None
    if type(entry_id) is not int or not 0 < entry_id <= MAX_ID:
        return None
    if kind == "questions":
        entry = f"Question {entry_id}"
    else:
        team = session.get(Team, entry_id)
        if team is None:
            return None
        entry = f"Team “{team.name}”"
    text, notice_kind = ENTRY_NOTICES[outcome]
    return text.format(entry=entry, name=competition.name), notice_kind


# ---------------------------------------------------------------------------------------------
# The refusal (http-routes.md §Refusal)
# ---------------------------------------------------------------------------------------------


def entries_refused(
    request: Request,
    kind: ListKind,
    competition: CompetitionView,
    status: CompetitionStatus,
    context: ListContext,
    back: int,
) -> HTMLResponse:
    """The 409 refusal of a change to a competition that is not Upcoming, with the way back to
    the competition's questions or teams at page `back`."""
    back_href = entries_path(kind, competition.id, context, p=back)
    return render_teacher(
        request,
        "pages/teacher/competition_refused.html",
        TAB,
        {
            "question": f"Change the {kind} of “{competition.name}”?",
            "reason": ENTRY_REFUSALS[status].format(name=competition.name, kind=kind),
            "back": back_href,
            "back_link_text": BACK_LINKS[kind],
            "back_text": "Back to the competition",
        },
        status_code=409,
    )


def render_competition_page(
    request: Request,
    template: str,
    competition: CompetitionView,
    context: ListContext,
    values: dict[str, Any],
    status_code: int = 200,
) -> HTMLResponse:
    """A page of this router: the competition, its subject and the context's hidden fields, with
    the page's own values."""
    return render_teacher(
        request,
        template,
        TAB,
        {"competition": competition, "subject": context.subject, "hidden": context.hidden()}
        | values,
        status_code=status_code,
    )


# ---------------------------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------------------------


@router.get("/questions", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def competition_questions_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    p: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """The competition's questions in the order of adding, ten per page, for every teacher;
    **Add question** and **Remove** only for a teacher who can make changes (FR-003–FR-009,
    FR-015). Opening it changes nothing."""
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    listing = question_page(session, competition.id, parse_page(p))
    current = listing.paging.number
    can_change = competition.status is CompetitionStatus.UPCOMING and can_manage(request, session)
    remove_hrefs = (
        {
            q.question_id: remove_path("questions", competition.id, q.question_id, context, current)
            for q in listing.questions
        }
        if can_change
        else {}
    )
    return render_competition_page(
        request,
        "pages/teacher/competition_questions.html",
        competition,
        context,
        {
            "listing": listing,
            "can_change": can_change,
            "notice": read_entry_notice(request, session, notice, competition, "questions"),
            "back": context.back_to_list(competition.id),
            "add_href": add_page_path("questions", competition.id, context, back=current),
            "page_href": page_prefix(entries_path("questions", competition.id, context)),
            "remove_hrefs": remove_hrefs,
        },
    )


@router.get("/questions/add", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def add_questions_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    back: str | None = Query(None),
    p: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """ "Add questions": the subject's listed questions, newest first, ten per page, each with
    **Add** or "Already in this competition" (FR-016–FR-019); the refusal for a competition
    that is not Upcoming (FR-034)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page = parse_page(back)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "questions", competition, competition.status, context, back_page
        )
    assert context.subject.id is not None
    listing = question_bank.question_page(session, context.subject.id, parse_page(p))
    return render_competition_page(
        request,
        "pages/teacher/competition_questions_add.html",
        competition,
        context,
        {
            "listing": listing,
            "in_competition": question_ids(session, competition.id),
            "notice": read_entry_notice(request, session, notice, competition, "questions"),
            "back": back_page,
            "back_href": entries_path("questions", competition.id, context, p=back_page),
            "page_href": page_prefix(
                add_page_path("questions", competition.id, context, back=back_page)
            ),
        },
    )


@router.post("/questions", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def add_question_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    back: str = Form(""),
    p: str = Form(""),
    question: str = Form(""),
) -> Response:
    """Copies one question to the end of the competition's list, and stays on the same page of
    "Add questions", at the question, with the notice (FR-018); "already in" lands there too,
    with its notice (FR-035)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page, add_page = parse_page(back), parse_page(p)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "questions", competition, competition.status, context, back_page
        )
    question_id = parse_id(question)
    if question_id is None:
        return not_found(request, QUESTION_NOT_FOUND)
    assert context.subject.id is not None
    try:
        add_question(session, teacher_id(request), competition.id, context.subject.id, question_id)
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except CompetitionNotFound:
        return not_found(request, COMPETITION_NOT_FOUND)
    except NotChangeable as refused:
        return entries_refused(
            request, "questions", competition, refused.status, context, back_page
        )
    except EntryNotFound:
        return not_found(request, QUESTION_NOT_FOUND)
    except AlreadyIn:
        outcome = "already"
    else:
        outcome = "added"
    token = entry_notice_token(request, competition.id, "questions", question_id, outcome)
    return redirect(
        add_page_path(
            "questions",
            competition.id,
            context,
            back_page,
            p=add_page,
            anchor=question_id,
            notice=token,
        )
    )


@router.get("/questions/{question_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_question_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    question_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    back: str | None = Query(None),
) -> Response:
    """The confirmation (FR-029); "is not in" for a known question that is not in the
    competition, which only redirects (research R10)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page = parse_page(back)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "questions", competition, competition.status, context, back_page
        )
    if question_id > MAX_ID:
        return not_found(request, QUESTION_NOT_FOUND)
    try:
        entry = get_competition_question(session, competition.id, question_id)
    except EntryNotFound:
        return not_found(request, QUESTION_NOT_FOUND)
    except NotIn:
        token = entry_notice_token(request, competition.id, "questions", question_id, "absent")
        return redirect(entries_path("questions", competition.id, context, back_page, None, token))
    consequence = (
        "The question was deleted from the question bank and cannot be added again."
        if entry.deleted_from_bank
        else "The question stays in the question bank and can be added again."
    )
    return _confirmation(
        request,
        "questions",
        competition,
        context,
        back_page,
        question_id,
        f"Remove question {question_id} from “{competition.name}”?",
        consequence,
    )


@router.post("/questions/{question_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_question_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    question_id: int,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    back: str = Form(""),
) -> Response:
    """Takes the question out of the competition and lands on the same page of its list at the
    row that took its place, else the one before it, with the notice (FR-032)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page = parse_page(back)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "questions", competition, competition.status, context, back_page
        )
    if question_id > MAX_ID:
        return not_found(request, QUESTION_NOT_FOUND)
    assert context.subject.id is not None
    try:
        landing = remove_question(
            session, teacher_id(request), competition.id, context.subject.id, question_id
        )
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except CompetitionNotFound:
        return not_found(request, COMPETITION_NOT_FOUND)
    except NotChangeable as refused:
        return entries_refused(
            request, "questions", competition, refused.status, context, back_page
        )
    except EntryNotFound:
        return not_found(request, QUESTION_NOT_FOUND)
    except NotIn:
        token = entry_notice_token(request, competition.id, "questions", question_id, "absent")
        return redirect(entries_path("questions", competition.id, context, back_page, None, token))
    token = entry_notice_token(request, competition.id, "questions", question_id, "removed")
    return redirect(
        entries_path("questions", competition.id, context, landing.p, landing.entry_id, token)
    )


def _confirmation(
    request: Request,
    kind: ListKind,
    competition: CompetitionView,
    context: ListContext,
    back: int,
    entry_id: int,
    question: str,
    consequence: str,
) -> HTMLResponse:
    """The remove confirmation of a question or a team; **Cancel** returns to the page it came
    from, at the entry (FR-031)."""
    return render_competition_page(
        request,
        "pages/teacher/competition_entry_remove.html",
        competition,
        context,
        {
            "question": question,
            "consequence": consequence,
            "action": f"/teacher/competitions/{competition.id}/{kind}/{entry_id}/remove",
            "cancel_href": entries_path(kind, competition.id, context, p=back, anchor=entry_id),
            "back_link_text": BACK_LINKS[kind],
            "hidden": context.hidden() | {"back": back},
        },
    )


# ---------------------------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------------------------


@router.get("/teams", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def competition_teams_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    p: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """The competition's teams in region boxes, ten teams per page, for every teacher; **Add
    team** and **Remove** only for a teacher who can make changes (FR-010–FR-015). Opening it
    changes nothing."""
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    listing = team_page(session, competition.id, parse_page(p))
    current = listing.paging.number
    can_change = competition.status is CompetitionStatus.UPCOMING and can_manage(request, session)
    rows = [row for group in listing.groups for row in group.rows]
    remove_hrefs = (
        {
            row.team_id: remove_path("teams", competition.id, row.team_id, context, current)
            for row in rows
        }
        if can_change
        else {}
    )
    return render_competition_page(
        request,
        "pages/teacher/competition_teams.html",
        competition,
        context,
        {
            "listing": listing,
            "can_change": can_change,
            "show_actions": can_change or any(row.is_deleted for row in rows),
            "notice": read_entry_notice(request, session, notice, competition, "teams"),
            "back": context.back_to_list(competition.id),
            "add_href": add_page_path("teams", competition.id, context, back=current),
            "page_href": page_prefix(entries_path("teams", competition.id, context)),
            "remove_hrefs": remove_hrefs,
        },
    )


@router.get("/teams/add", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def add_teams_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    back: str | None = Query(None),
    region: str | None = Query(None),
    p: str | None = Query(None),
    notice: str | None = Query(None),
) -> HTMLResponse:
    """ "Add teams": the **Region** list, then the chosen region's live teams of active
    institutions, from every institution, ten per page, each with **Add** or "Already in this
    competition" (FR-020–FR-027). With no region in the address, the only region offered is
    chosen, without a redirect: its id travels in every form and page link instead."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page = parse_page(back)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "teams", competition, competition.status, context, back_page
        )
    regions = list_active_regions(session)
    if not region:
        selected = regions[0] if len(regions) == 1 else None
    else:
        selected = _region(regions, region)
        if selected is None:
            return not_found(request, REGION_NOT_FOUND)
    values: dict[str, Any] = {
        "regions": [(r.id, r.name) for r in regions],
        "selected": selected,
        "listing": None,
        "in_competition": set(),
        "notice": read_entry_notice(request, session, notice, competition, "teams"),
        "back": back_page,
        "back_href": entries_path("teams", competition.id, context, p=back_page),
    }
    if selected is not None:
        assert selected.id is not None
        values |= {
            "listing": addable_teams(session, selected.id, parse_page(p)),
            "in_competition": team_ids(session, competition.id),
            "page_href": page_prefix(
                add_page_path("teams", competition.id, context, back_page, region=selected.id)
            ),
        }
    return render_competition_page(
        request, "pages/teacher/competition_teams_add.html", competition, context, values
    )


@router.post("/teams", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def add_team_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    back: str = Form(""),
    region: str = Form(""),
    p: str = Form(""),
    team: str = Form(""),
) -> Response:
    """Adds one team, and stays on the same region and page of "Add teams", at the team, with
    the notice (FR-026); "already in" lands there too, with its notice (FR-035)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page, add_page = parse_page(back), parse_page(p)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "teams", competition, competition.status, context, back_page
        )
    selected = _region(list_active_regions(session), region)
    if selected is None:
        return not_found(request, REGION_NOT_FOUND)
    team_id = parse_id(team)
    if team_id is None:
        return not_found(request, TEAM_NOT_FOUND)
    assert context.subject.id is not None and selected.id is not None
    try:
        add_team(
            session,
            teacher_id(request),
            competition.id,
            context.subject.id,
            selected.id,
            team_id,
        )
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except CompetitionNotFound:
        return not_found(request, COMPETITION_NOT_FOUND)
    except NotChangeable as refused:
        return entries_refused(request, "teams", competition, refused.status, context, back_page)
    except EntryNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    except AlreadyIn:
        outcome = "already"
    else:
        outcome = "added"
    token = entry_notice_token(request, competition.id, "teams", team_id, outcome)
    return redirect(
        add_page_path(
            "teams",
            competition.id,
            context,
            back_page,
            p=add_page,
            region=selected.id,
            anchor=team_id,
            notice=token,
        )
    )


@router.get("/teams/{team_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_team_page(
    request: Request,
    session: SessionDep,
    competition_id: int,
    team_id: int,
    subject: str | None = Query(None),
    status: str | None = Query(None),
    page: str | None = Query(None),
    back: str | None = Query(None),
) -> Response:
    """The confirmation, naming the team, its institution and its region (FR-030); "is not in"
    for a known team that is not in the competition, which only redirects (research R10)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page = parse_page(back)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "teams", competition, competition.status, context, back_page
        )
    if team_id > MAX_ID:
        return not_found(request, TEAM_NOT_FOUND)
    try:
        row, region_name = get_competition_team(session, competition.id, team_id)
    except EntryNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    except NotIn:
        token = entry_notice_token(request, competition.id, "teams", team_id, "absent")
        return redirect(entries_path("teams", competition.id, context, back_page, None, token))
    return _confirmation(
        request,
        "teams",
        competition,
        context,
        back_page,
        team_id,
        f"Remove team “{row.name}” of {row.institution_name}, {region_name} from"
        f" “{competition.name}”?",
        "The team and its members are not changed, and the team can be added again.",
    )


@router.post("/teams/{team_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_team_action(
    request: Request,
    session: SessionDep,
    competition_id: int,
    team_id: int,
    subject: str = Form(""),
    status: str = Form(""),
    page: str = Form(""),
    back: str = Form(""),
) -> Response:
    """Takes the team out of the competition, leaving the team and its members unchanged, and
    lands on the same page of its list at the row that took its place, else the one before it,
    with the notice (FR-032, FR-033)."""
    require_manage(request, session)
    found = find_context(request, session, competition_id, subject, status, page)
    if isinstance(found, HTMLResponse):
        return found
    context, competition = found
    back_page = parse_page(back)
    if competition.status is not CompetitionStatus.UPCOMING:
        return entries_refused(
            request, "teams", competition, competition.status, context, back_page
        )
    if team_id > MAX_ID:
        return not_found(request, TEAM_NOT_FOUND)
    assert context.subject.id is not None
    try:
        landing = remove_team(
            session, teacher_id(request), competition.id, context.subject.id, team_id
        )
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except CompetitionNotFound:
        return not_found(request, COMPETITION_NOT_FOUND)
    except NotChangeable as refused:
        return entries_refused(request, "teams", competition, refused.status, context, back_page)
    except EntryNotFound:
        return not_found(request, TEAM_NOT_FOUND)
    except NotIn:
        token = entry_notice_token(request, competition.id, "teams", team_id, "absent")
        return redirect(entries_path("teams", competition.id, context, back_page, None, token))
    token = entry_notice_token(request, competition.id, "teams", team_id, "removed")
    return redirect(
        entries_path("teams", competition.id, context, landing.p, landing.entry_id, token)
    )
