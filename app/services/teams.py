"""Teams: what the Teams tab of the teacher area calls to list and manage teams and their
members, and the student's own teams for the profile.

See specs/011.1-teacher-teams/contracts/services.md §`app/services/teams.py` and research R1–R7.
A team belongs to one educational institution for ever (no function writes `institution_id`
after the insert) and holds students of that institution only, each at most once, at most
`MAX_MEMBERS` (FR-001, FR-003, FR-004). Names follow the subject-name rules (`clean_name`,
`name_key`) and are unique among live teams across all institutions, ignoring case; the partial
unique index `uq_teams_name_key_live`, not the lookup before a write, is the guarantee (R2).
Deletion is soft: `deleted_at` is set and nothing else changes, memberships included (R1).

Every change acts for a teacher and checks the teacher's reach (`app.services.teacher_access`)
with Write, in its own transaction, under lock, in a fixed order: the team, then the user, then
the class, then the institution and the region (research R5). Adding counts the members while
the team row is locked, so the limit holds under concurrency. A refusal rolls back, so no lock
outlives it; a successful change commits once and logs one line with ids and counts only; a
no-op logs nothing (FR-016).

Memberships are personal data of the student (FR-012). Besides `remove_member`, their only
deleter is `STUDENT_INVITATION.revoke` (`app.services.students`), through which removal,
withdrawal and data deletion all erase them, in deleted teams too (R7).

The lookups check no reach: their callers do.

**For milestone 12**: only a team that `reach_team` returns, a live team of an institution the
teacher is linked to (Read or Write), may be added to a competition.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.models import (
    Enrolment,
    Institution,
    Region,
    SchoolClass,
    Team,
    TeamMembership,
    User,
)
from app.schemas.names import InvalidName, clean_name, name_key
from app.schemas.teachers import MAX_ID
from app.services.classes import ClassView
from app.services.teacher_access import (
    NotReachable,
    ReachableInstitution,
    reach_institution,
    reach_student,
    reach_team,
)

logger = logging.getLogger("uvicorn.error")

MAX_MEMBERS = 50
"""The most members a team may hold, blocked ones included (FR-004)."""


class DuplicateTeamName(ValueError):
    """A live team in any institution already has this name, ignoring case. `message` repeats
    the name as entered (after trimming), never the stored name or an institution, so nothing
    about another institution leaks (FR-002, research R2)."""

    def __init__(self, entered_name: str) -> None:
        self.message = f"A team named “{entered_name}” already exists."
        super().__init__(self.message)


class AlreadyMember(ValueError):
    """The student is already in the team; nothing was stored (FR-042)."""

    def __init__(self, team_id: int, user_id: int) -> None:
        super().__init__(f"User {user_id} is already in team {team_id}")
        self.team_id = team_id
        self.user_id = user_id


class TeamFull(ValueError):
    """The team already holds `MAX_MEMBERS` memberships, blocked ones included; nothing was
    stored (FR-004)."""

    def __init__(self, team_id: int) -> None:
        super().__init__(f"Team {team_id} is full")
        self.team_id = team_id


@dataclass(frozen=True)
class TeamView:
    """A team as the teacher pages show it."""

    id: int
    institution_id: int
    name: str

    @classmethod
    def from_row(cls, row: Team) -> "TeamView":
        assert row.id is not None
        return cls(id=row.id, institution_id=row.institution_id, name=row.name)


@dataclass(frozen=True)
class MemberRow:
    """An active member of a team, as the tab lists them."""

    user_id: int
    first_name: str
    last_name: str
    class_label: str
    """`ClassView.label`: "KN-21 · year 2"."""


@dataclass(frozen=True)
class StudentTeam:
    """One of the student's teams, as their profile lists it (FR-013)."""

    name: str
    is_deleted: bool


def _member_row(user: User, school_class: SchoolClass) -> MemberRow:
    assert user.id is not None
    return MemberRow(
        user_id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        class_label=ClassView.from_row(school_class).label,
    )


# ---------------------------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------------------------


def list_teams(session: Session, institution_id: int) -> list[TeamView]:
    """The institution's live teams, sorted ignoring case, ties by id (FR-028). Sorted in Python,
    as everywhere else."""
    statement = select(Team).where(
        Team.institution_id == institution_id, col(Team.deleted_at).is_(None)
    )
    rows = sorted(session.exec(statement), key=lambda row: (row.name_key, row.id))
    return [TeamView.from_row(row) for row in rows]


def list_active_members(session: Session, team_id: int) -> list[MemberRow]:
    """The team's members whose class, institution and region are all active (the milestone 9
    chain), sorted by last name, then first name, ignoring case, ties by id (FR-010, FR-035,
    research R6). A blocked member is left out with no trace; their membership is unchanged."""
    statement = (
        select(User, SchoolClass)
        .select_from(TeamMembership)
        .join(User, col(User.id) == col(TeamMembership.user_id))
        .join(Enrolment, col(Enrolment.user_id) == col(TeamMembership.user_id))
        .join(SchoolClass, col(SchoolClass.id) == col(Enrolment.class_id))
        .join(Institution, col(Institution.id) == col(SchoolClass.institution_id))
        .join(Region, col(Region.id) == col(Institution.region_id))
        .where(
            TeamMembership.team_id == team_id,
            col(SchoolClass.is_active),
            col(Institution.is_active),
            col(Region.is_active),
        )
    )
    rows = [_member_row(user, school_class) for user, school_class in session.exec(statement)]
    return sorted(
        rows, key=lambda row: (row.last_name.casefold(), row.first_name.casefold(), row.user_id)
    )


def count_members(session: Session, team_id: int) -> int:
    """Every membership of the team, blocked members included: what the limit counts (FR-004)."""
    statement = (
        select(func.count())
        .select_from(TeamMembership)
        .where(col(TeamMembership.team_id) == team_id)
    )
    return session.exec(statement).one()


def member_ids(session: Session, team_id: int) -> set[int]:
    """The user id of every member, blocked ones included: "In this team" (FR-039)."""
    statement = select(TeamMembership.user_id).where(TeamMembership.team_id == team_id)
    return set(session.exec(statement))


def is_full(session: Session, team_id: int) -> bool:
    """Whether the team holds `MAX_MEMBERS` members or more (FR-041)."""
    return count_members(session, team_id) >= MAX_MEMBERS


def list_student_teams(session: Session, user_id: int) -> list[StudentTeam]:
    """Every team the person belongs to, deleted ones included, sorted ignoring case, ties by id
    (FR-013, research R14)."""
    statement = (
        select(Team)
        .join(TeamMembership, col(TeamMembership.team_id) == col(Team.id))
        .where(TeamMembership.user_id == user_id)
    )
    rows = sorted(session.exec(statement), key=lambda row: (row.name_key, row.id))
    return [StudentTeam(name=row.name, is_deleted=row.deleted_at is not None) for row in rows]


# ---------------------------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------------------------


def _find_live(session: Session, key: str) -> Team | None:
    """The live team with this name key, in any institution."""
    statement = select(Team).where(Team.name_key == key, col(Team.deleted_at).is_(None))
    return session.exec(statement).first()


def _cleaned(session: Session, raw_name: str) -> tuple[str, str]:
    """The cleaned name and its key; on a refusal, roll back first (the reach check holds locks)
    and re-raise `InvalidName`."""
    try:
        name = clean_name(raw_name)
    except InvalidName:
        session.rollback()
        raise
    return name, name_key(name)


def create_team(session: Session, teacher_id: int, institution_id: int, raw_name: str) -> TeamView:
    """Store a new team in the institution, which the teacher must reach with Write. The link,
    institution and region rows are read `FOR SHARE`, so the institution cannot be deactivated
    or deleted, nor the level lowered, until the insert commits. Raises `NotReachable`,
    `WriteRequired`, `InvalidName` or `DuplicateTeamName`; nothing is stored then."""
    reach_institution(session, teacher_id, institution_id, write=True, lock=True)
    name, key = _cleaned(session, raw_name)
    if _find_live(session, key) is not None:
        session.rollback()
        raise DuplicateTeamName(name)
    now = utc_now()
    team = Team(
        institution_id=institution_id, name=name, name_key=key, created_at=now, updated_at=now
    )
    session.add(team)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateTeamName(name) from None
    session.refresh(team)
    logger.info("Team created: id=%d institution_id=%d", team.id, institution_id)
    return TeamView.from_row(team)


def rename_team(session: Session, teacher_id: int, team_id: int, raw_name: str) -> TeamView:
    """Change the team's name. The team itself never counts as a duplicate, so a change of case
    is a valid rename (US3-5); an unchanged name writes nothing. Raises `NotReachable`,
    `WriteRequired`, `InvalidName` or `DuplicateTeamName`."""
    _, team = reach_team(session, teacher_id, team_id, write=True, lock=True)
    name, key = _cleaned(session, raw_name)
    existing = _find_live(session, key)
    if existing is not None and existing.id != team.id:
        session.rollback()
        raise DuplicateTeamName(name)
    if (team.name, team.name_key) == (name, key):
        view = TeamView.from_row(team)
        session.rollback()
        return view
    team.name = name
    team.name_key = key
    team.updated_at = utc_now()
    session.add(team)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateTeamName(name) from None
    session.refresh(team)
    logger.info("Team renamed: id=%d", team_id)
    return TeamView.from_row(team)


def delete_team(session: Session, teacher_id: int, team_id: int) -> TeamView:
    """Mark the team deleted. Only `deleted_at` is written: the name, the institution,
    `updated_at` and every membership stay as they are (FR-007, FR-009). A deleted team is out of
    reach, so a second deletion is `NotReachable`."""
    _, team = reach_team(session, teacher_id, team_id, write=True, lock=True)
    members = count_members(session, team_id)
    team.deleted_at = utc_now()
    session.add(team)
    view = TeamView.from_row(team)
    session.commit()
    logger.info("Team deleted: id=%d members=%d", team_id, members)
    return view


# ---------------------------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------------------------


def _membership(session: Session, team_id: int, user_id: int) -> TeamMembership | None:
    return session.get(TeamMembership, (team_id, user_id))


def _user_id(raw: str) -> int:
    """The submitted student id; anything that is not an id is a student out of reach."""
    if not raw or not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        raise NotReachable()
    return int(raw)


def add_member(session: Session, teacher_id: int, team_id: int, raw_user_id: str) -> MemberRow:
    """Add one student to the team, and return them as a member.

    In this order: the team with Write (its row `FOR UPDATE`); the id; the student, who must hold
    the role, be enrolled in an available class (not blocked, FR-011) and be reachable with Write
    (the user row `FOR UPDATE`, the class and institution `FOR SHARE`); the student's class in the
    team's institution (FR-003); not already a member (`AlreadyMember`); fewer than `MAX_MEMBERS`
    members, blocked ones included (`TeamFull`). "Already" comes before the limit, so re-adding a
    member of a full team is "already". The primary key is the guarantee against a second
    membership in a race: its `IntegrityError` is `AlreadyMember` too.

    Nothing else about the student is written: class, enrolment, role, other teams and sessions
    stay as they are (FR-005).
    """
    _, team = reach_team(session, teacher_id, team_id, write=True, lock=True)
    try:
        user_id = _user_id(raw_user_id)
    except NotReachable:
        session.rollback()
        raise
    _, school_class, user = reach_student(session, teacher_id, user_id, write=True, lock=True)
    if school_class.institution_id != team.institution_id:
        session.rollback()
        raise NotReachable()
    if _membership(session, team_id, user_id) is not None:
        session.rollback()
        raise AlreadyMember(team_id, user_id)
    if count_members(session, team_id) >= MAX_MEMBERS:
        session.rollback()
        raise TeamFull(team_id)
    member = _member_row(user, school_class)
    session.add(TeamMembership(team_id=team_id, user_id=user_id, created_at=utc_now()))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AlreadyMember(team_id, user_id) from None
    logger.info("Team member added: team_id=%d user_id=%d", team_id, user_id)
    return member


def get_member(
    session: Session, teacher_id: int, team_id: int, user_id: int
) -> tuple[ReachableInstitution, TeamView, MemberRow]:
    """The member for the remove confirmation: the team with Write, then the student (reachable
    with Write and not blocked), who must be of the team's institution and a member;
    `NotReachable` or `WriteRequired` otherwise. No lock: it changes nothing."""
    institution, team = reach_team(session, teacher_id, team_id, write=True)
    _, school_class, user = reach_student(session, teacher_id, user_id, write=True)
    if school_class.institution_id != team.institution_id:
        raise NotReachable()
    if _membership(session, team_id, user_id) is None:
        raise NotReachable()
    return institution, TeamView.from_row(team), _member_row(user, school_class)


def remove_member(session: Session, teacher_id: int, team_id: int, user_id: int) -> None:
    """Take the student out of the team: that one membership is deleted. The checks of
    `get_member` are repeated under lock, in the order of `add_member`. The student keeps their
    role, class, enrolment, other teams and sessions (FR-006)."""
    _, team = reach_team(session, teacher_id, team_id, write=True, lock=True)
    _, school_class, _ = reach_student(session, teacher_id, user_id, write=True, lock=True)
    if school_class.institution_id != team.institution_id:
        session.rollback()
        raise NotReachable()
    membership = _membership(session, team_id, user_id)
    if membership is None:
        session.rollback()
        raise NotReachable()
    session.delete(membership)
    session.commit()
    logger.info("Team member removed: team_id=%d user_id=%d", team_id, user_id)
