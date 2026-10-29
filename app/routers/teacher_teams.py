"""The Teams tab of the teacher area: choosing a team, creating, renaming and deleting teams, and
adding and removing their members.

See specs/011.1-teacher-teams/contracts/http-routes.md and research R4, R10, R11. Thin handlers
only: each reads its values as plain strings, so no input ever gets FastAPI's 422, calls
`app.services.teacher_access` and `app.services.teams`, maps their outcomes to a status and a
page, and on success redirects with a 303 (Post/Redirect/Get), so a reload never repeats a change
(FR-044). An invalid name shows the form again with the error and the value as typed.

**The selection lives in the address**, as on Students: `/teacher/teams?region=…&institution=…
&team=…`, built by `selection_path` and `team_path`. Every redirect, Cancel and back link is built
from the team's own institution, never from request values, so the region and the institution
stay selected after every action (FR-030, FR-031, research R10).

**The order of checks**, on every route (contracts §Order of checks): the role
(`@allow_roles(Role.TEACHER)`); the ids, where anything that is not an ASCII integer up to
`MAX_ID` is "access denied"; the team (or, for a new team, the institution), with Write on every
management page and action, before any student, class or name is read (FR-023); then the student
or the class, checked against the team's institution; then the rules. Every service write repeats
the reach checks under lock. Unknown, deleted and out of reach, and Read access on a management
page, all answer with the same milestone 5 "Access denied" page (403), so nothing reveals whether
a team exists (FR-022).

**The notice after an addition** travels as a sealed, 10-minute token holding ids only, so no name
ever reaches an address or a log line (FR-016, research R11). Nothing here logs.
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
from app.models import Role, Team, User
from app.routers.teacher import render_teacher
from app.schemas.names import InvalidName, clean_name
from app.schemas.teachers import MAX_ID
from app.services.classes import ClassView, list_classes
from app.services.students import list_students
from app.services.teacher_access import (
    NotReachable,
    ReachableInstitution,
    WriteRequired,
    list_reachable_institutions,
    reach_class,
    reach_institution,
    reach_team,
    reachable_regions,
)
from app.services.teams import (
    AlreadyMember,
    DuplicateTeamName,
    TeamFull,
    TeamView,
    add_member,
    create_team,
    delete_team,
    get_member,
    is_full,
    list_active_members,
    list_teams,
    member_ids,
    remove_member,
    rename_team,
)

router = APIRouter(prefix="/teacher/teams")

TAB = "teams"
TAB_PATH = "/teacher/teams"

NOT_LINKED = "You are not linked to any educational institution"
SELECT_REGION = "Select a region to continue"
SELECT_INSTITUTION = "Select an educational institution to continue"
NO_TEAMS = "No teams yet"
SELECT_TEAM = "Select a team to see its members"
NO_MEMBERS = "No members in this team yet"
"""The messages of the tab in each state (FR-029, FR-035)."""

SELECT_CLASS = "Select a class to see its students"
NO_STUDENTS = "No students in this class yet"
TEAM_IS_FULL = "This team already has 50 members"
"""The messages of the Add students page (FR-039, FR-041)."""

NEW_TEAM = "new"
"""The `team` value of the **+ Add team** entry (research R10)."""

TEAM_NOTICE_PURPOSE = "team-member-notice"
TEAM_NOTICE_TTL = timedelta(minutes=10)
NOTICES = {
    "added": ("{name} was added to the team.", "success"),
    "already": ("{name} is already in this team.", "info"),
}
"""The notice of each outcome of an addition, with its kind (FR-040, FR-042)."""


def selection_path(region_id: int, institution_id: int, team_id: int | None = None) -> str:
    """The Teams tab with this region, institution and, if given, team selected."""
    path = f"{TAB_PATH}?region={region_id}&institution={institution_id}"
    if team_id is not None:
        path += f"&team={team_id}"
    return path


def team_path(institution: ReachableInstitution, team_id: int) -> str:
    """The Teams tab with the team selected, in its own region and institution."""
    return selection_path(institution.region_id, institution.id, team_id)


def _denied() -> AccessDenied:
    """The milestone 5 403 page: the same for unknown, deleted, unreachable and read-only."""
    return AccessDenied(Role.TEACHER)


def _id(raw: str | None) -> int | None:
    """An id from the address or a form: `None` when absent or empty, an `int` for ASCII digits
    up to `MAX_ID`, and "access denied" for anything else."""
    if raw is None or raw == "":
        return None
    if not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        raise _denied()
    return int(raw)


def _quiet_id(raw: str | None) -> int | None:
    """An id carried through for the redirect: `None` for anything that is not one."""
    if not raw or not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        return None
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
    session: SessionDep, teacher_id: int, institution_id: int
) -> ReachableInstitution:
    try:
        return reach_institution(session, teacher_id, institution_id, write=True)
    except (NotReachable, WriteRequired):
        raise _denied() from None


def _reach_team(
    session: SessionDep, teacher_id: int, team_id: int
) -> tuple[ReachableInstitution, Team]:
    """The team, with Write: every page and action of a team but the tab is a management one."""
    try:
        return reach_team(session, teacher_id, team_id, write=True)
    except (NotReachable, WriteRequired):
        raise _denied() from None


# ---------------------------------------------------------------------------------------------
# The notice after an addition (research R11)
# ---------------------------------------------------------------------------------------------


def seal_member_notice(settings: AuthSettings, team_id: int, user_id: int, outcome: str) -> str:
    """The `notice` value for the tab after an addition: ids and the outcome only."""
    payload = {"team": team_id, "user": user_id, "outcome": outcome}
    return seal(settings.secret_key, TEAM_NOTICE_PURPOSE, payload)


def member_notice(
    session: Session, settings: AuthSettings, token: str | None, team_id: int
) -> tuple[str, str] | None:
    """`(text, kind)` for a valid, fresh token of this team whose student is a listed member,
    named as the database names them now; `None` for anything else, which is not an error."""
    if not token:
        return None
    try:
        payload = unseal(settings.secret_key, TEAM_NOTICE_PURPOSE, token, TEAM_NOTICE_TTL)
    except (SealInvalid, SealExpired):
        return None
    team, user, outcome = payload.get("team"), payload.get("user"), payload.get("outcome")
    if type(team) is not int or team != team_id or type(user) is not int:
        return None
    if outcome not in NOTICES:
        return None
    for member in list_active_members(session, team_id):
        if member.user_id == user:
            text, kind = NOTICES[outcome]
            return text.format(name=f"{member.first_name} {member.last_name}"), kind
    return None


# ---------------------------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def teams_page(
    request: Request,
    session: SessionDep,
    region: str | None = Query(None),
    institution: str | None = Query(None),
    team: str | None = Query(None),
    notice: str | None = Query(None),
) -> Response:
    """The three lists, the message of the current state, and the selected team with its active
    members (FR-028–FR-030, FR-034, FR-035). Opening it changes nothing."""
    teacher_id = _teacher(request)
    region_id = _id(region)
    institution_id = _id(institution)
    adding = team == NEW_TEAM
    team_id = None if adding else _id(team)
    if institution_id is not None and region_id is None:
        raise _denied()
    if (adding or team_id is not None) and institution_id is None:
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
        return _redirect(f"{TAB_PATH}/institutions/{selected_institution.id}/new")

    selected_team: TeamView | None = None
    if team_id is not None:
        try:
            _, row = reach_team(session, teacher_id, team_id, institution_id=institution_id)
        except NotReachable:
            raise _denied() from None
        selected_team = TeamView.from_row(row)

    teams = list_teams(session, selected_institution.id) if selected_institution else []
    members = list_active_members(session, selected_team.id) if selected_team else []
    if not reachable:
        message = NOT_LINKED
    elif region_id is None:
        message = SELECT_REGION
    elif selected_institution is None:
        message = SELECT_INSTITUTION
    elif not teams:
        message = NO_TEAMS
    elif selected_team is None:
        message = SELECT_TEAM
    else:
        message = NO_MEMBERS if not members else None

    return render_teacher(
        request,
        "pages/teacher/teams.html",
        TAB,
        {
            "regions": regions,
            "institutions": [item for item in reachable if item.region_id == region_id],
            "teams": teams,
            "selected_region": region_id,
            "selected_institution": selected_institution,
            "selected_team": selected_team,
            "message": message,
            "members": members,
            "can_write": selected_institution is not None and selected_institution.can_write,
            "notice": member_notice(session, _settings(request), notice, selected_team.id)
            if selected_team
            else None,
        },
    )


# ---------------------------------------------------------------------------------------------
# Creating and renaming a team
# ---------------------------------------------------------------------------------------------


def _team_form(
    request: Request,
    heading: str,
    action: str,
    institution: ReachableInstitution,
    value: str,
    cancel: str,
    back_text: str,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The new-team or rename form: one field, the name (FR-032). It names the institution and
    offers no way to change it (FR-001)."""
    return render_teacher(
        request,
        "pages/teacher/team_form.html",
        TAB,
        {
            "heading": heading,
            "action": action,
            "institution": institution,
            "values": {"name": value},
            "errors": errors or {},
            "cancel": cancel,
            "back_text": back_text,
        },
        status_code=status_code,
    )


def _name_error(name: str) -> dict[str, str]:
    try:
        clean_name(name)
    except InvalidName as invalid:
        return {"name": invalid.message}
    return {}


def _new_team_heading(institution: ReachableInstitution) -> str:
    return f"New team in “{institution.name}”"


BACK_TO_TEAMS = "Back to Teams"


@router.get("/institutions/{institution_id:int}/new", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def new_team_page(request: Request, session: SessionDep, institution_id: int) -> HTMLResponse:
    institution = _reach_institution(session, _teacher(request), institution_id)
    return _team_form(
        request,
        _new_team_heading(institution),
        f"{TAB_PATH}/institutions/{institution.id}/new",
        institution,
        "",
        selection_path(institution.region_id, institution.id),
        BACK_TO_TEAMS,
    )


@router.post("/institutions/{institution_id:int}/new", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def create_team_action(
    request: Request, session: SessionDep, institution_id: int, name: str = Form("")
) -> Response:
    """On success the new team is selected (US1-5). Only `name` is read: any other field, such as
    an institution, is ignored (FR-001)."""
    teacher_id = _teacher(request)
    institution = _reach_institution(session, teacher_id, institution_id)
    back = selection_path(institution.region_id, institution.id)

    def refused(errors: dict[str, str]) -> HTMLResponse:
        return _team_form(
            request,
            _new_team_heading(institution),
            f"{TAB_PATH}/institutions/{institution.id}/new",
            institution,
            name,
            back,
            BACK_TO_TEAMS,
            errors,
            400,
        )

    errors = _name_error(name)
    if errors:
        return refused(errors)
    try:
        created = create_team(session, teacher_id, institution_id, name)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except (InvalidName, DuplicateTeamName) as invalid:
        return refused({"name": invalid.message})
    return _redirect(selection_path(institution.region_id, institution.id, created.id))


def _back_to(team: Team) -> str:
    return f"Back to “{team.name}”"


@router.get("/{team_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def rename_team_page(request: Request, session: SessionDep, team_id: int) -> HTMLResponse:
    institution, team = _reach_team(session, _teacher(request), team_id)
    return _team_form(
        request,
        f"Rename team “{team.name}”",
        f"{TAB_PATH}/{team_id}/rename",
        institution,
        team.name,
        team_path(institution, team_id),
        _back_to(team),
    )


@router.post("/{team_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def rename_team_action(
    request: Request, session: SessionDep, team_id: int, name: str = Form("")
) -> Response:
    """A change of case alone is a valid rename (US3-5); an unchanged name writes nothing."""
    teacher_id = _teacher(request)
    institution, team = _reach_team(session, teacher_id, team_id)
    heading, back_text = f"Rename team “{team.name}”", _back_to(team)
    back = team_path(institution, team_id)

    def refused(errors: dict[str, str]) -> HTMLResponse:
        return _team_form(
            request,
            heading,
            f"{TAB_PATH}/{team_id}/rename",
            institution,
            name,
            back,
            back_text,
            errors,
            400,
        )

    errors = _name_error(name)
    if errors:
        return refused(errors)
    try:
        rename_team(session, teacher_id, team_id, name)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except (InvalidName, DuplicateTeamName) as invalid:
        return refused({"name": invalid.message})
    return _redirect(back)


# ---------------------------------------------------------------------------------------------
# Deleting a team
# ---------------------------------------------------------------------------------------------


@router.get("/{team_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def delete_team_page(request: Request, session: SessionDep, team_id: int) -> HTMLResponse:
    """The confirmation step, naming the team, its institution and its active members, blocked
    ones not counted (FR-037): opening it changes nothing."""
    institution, team = _reach_team(session, _teacher(request), team_id)
    return render_teacher(
        request,
        "pages/teacher/team_delete.html",
        TAB,
        {
            "team": team,
            "institution": institution,
            "members": len(list_active_members(session, team_id)),
            "cancel": team_path(institution, team_id),
        },
    )


@router.post("/{team_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def delete_team_action(request: Request, session: SessionDep, team_id: int) -> RedirectResponse:
    """The team is only marked deleted (FR-007); the institution stays selected, with no team
    (US2-6)."""
    teacher_id = _teacher(request)
    institution, _ = _reach_team(session, teacher_id, team_id)
    try:
        delete_team(session, teacher_id, team_id)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    return _redirect(selection_path(institution.region_id, institution.id))


# ---------------------------------------------------------------------------------------------
# Adding students
# ---------------------------------------------------------------------------------------------


def _active_class(
    session: SessionDep, teacher_id: int, class_id: int, institution_id: int
) -> ClassView:
    """An active class of the team's institution; `NotReachable` for anything else."""
    _, row = reach_class(session, teacher_id, class_id, institution_id=institution_id)
    if not row.is_active:
        raise NotReachable()
    return ClassView.from_row(row)


@router.get("/{team_id:int}/add", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def add_students_page(
    request: Request,
    session: SessionDep,
    team_id: int,
    class_: str | None = Query(None, alias="class"),
) -> HTMLResponse:
    """One list, Class, of the institution's active classes; once one is chosen, its students,
    each with Add or "In this team" (FR-038–FR-041). Opening it changes nothing."""
    teacher_id = _teacher(request)
    institution, team = _reach_team(session, teacher_id, team_id)
    class_id = _id(class_)
    selected_class: ClassView | None = None
    if class_id is not None:
        try:
            selected_class = _active_class(session, teacher_id, class_id, team.institution_id)
        except NotReachable:
            raise _denied() from None
    students: list[Any] = list_students(session, selected_class.id) if selected_class else []
    if selected_class is None:
        message = SELECT_CLASS
    else:
        message = NO_STUDENTS if not students else None
    return render_teacher(
        request,
        "pages/teacher/team_add_students.html",
        TAB,
        {
            "team": team,
            "institution": institution,
            "classes": [c for c in list_classes(session, institution.id) if c.is_active],
            "selected_class": selected_class,
            "students": students,
            "members": member_ids(session, team_id),
            "full": is_full(session, team_id),
            "message": message,
            "back": team_path(institution, team_id),
        },
    )


@router.post("/{team_id:int}/members", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def add_member_action(
    request: Request,
    session: SessionDep,
    team_id: int,
    student: str = Form(""),
    class_: str = Form("", alias="class"),
) -> RedirectResponse:
    """Add one student, then return to the tab with a notice (FR-040). Already a member: the tab
    with the "already" notice; the team full: Add students again, with the same class while it is
    still an active class of the institution (FR-042). `class` is used for nothing else."""
    settings = _settings(request)
    teacher_id = _teacher(request)
    institution, team = _reach_team(session, teacher_id, team_id)
    try:
        member = add_member(session, teacher_id, team_id, student)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    except AlreadyMember as already:
        notice = seal_member_notice(settings, team_id, already.user_id, "already")
        return _redirect(f"{team_path(institution, team_id)}&notice={notice}")
    except TeamFull:
        back = f"{TAB_PATH}/{team_id}/add"
        class_id = _quiet_id(class_)
        if class_id is not None:
            try:
                _active_class(session, teacher_id, class_id, team.institution_id)
            except NotReachable:
                return _redirect(back)
            return _redirect(f"{back}?class={class_id}")
        return _redirect(back)
    notice = seal_member_notice(settings, team_id, member.user_id, "added")
    return _redirect(f"{team_path(institution, team_id)}&notice={notice}")


# ---------------------------------------------------------------------------------------------
# Removing a member
# ---------------------------------------------------------------------------------------------


@router.get("/{team_id:int}/members/{user_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_member_page(
    request: Request, session: SessionDep, team_id: int, user_id: int
) -> HTMLResponse:
    """The confirmation step, naming the student and the team (FR-036): opening it changes
    nothing. A blocked member, a non-member or an unknown person is "access denied" (FR-011)."""
    try:
        institution, team, member = get_member(session, _teacher(request), team_id, user_id)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    return render_teacher(
        request,
        "pages/teacher/team_member_remove.html",
        TAB,
        {
            "team": team,
            "member": member,
            "cancel": team_path(institution, team_id),
        },
    )


@router.post("/{team_id:int}/members/{user_id:int}/remove", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def remove_member_action(
    request: Request, session: SessionDep, team_id: int, user_id: int
) -> RedirectResponse:
    """Only the membership goes: the student keeps their role, class, enrolment, other teams and
    sessions (FR-006). The same team stays selected."""
    teacher_id = _teacher(request)
    institution, _ = _reach_team(session, teacher_id, team_id)
    try:
        remove_member(session, teacher_id, team_id, user_id)
    except (NotReachable, WriteRequired):
        raise _denied() from None
    return _redirect(team_path(institution, team_id))
