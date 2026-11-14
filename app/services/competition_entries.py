"""A competition's questions and teams: the two lists every teacher reads, and adding and removing
an entry, which only a teacher with **Can manage competitions** does, and only while the
competition is Upcoming.

See specs/012.2-competition-questions-teams/contracts/services.md and research R1–R5, R10–R14.
Every teacher reads every competition's lists; reading needs only the teacher role, which the
routes check, and a competition the caller has already found with
`competitions.get_competition` (its subject and visibility checked).

- **Questions are copied** (R1, R3): adding one stores the bank's text and reference answer as
  read under lock, and nothing ever writes the copy again, so editing or deleting the bank
  question changes nothing here. The list is in the order of adding, the copy's `id`.
- **Teams are linked** (R1, R4): their current name, institution, region and number of active
  members are always shown. Any live team of an active institution in an active region may be
  added, whether or not the teacher is linked to its institution: there is no link check and no
  member check (FR-023, FR-027).
- **The clock** is `app.services.competitions.utc_now`, read through that module once per call,
  so tests that move the 12.1 clock move this one too.
- **Every write, in this order** (R2): the setting with `lock=True` (`ManageRequired`); the
  competition `FOR UPDATE` and its subject `FOR SHARE` through `competitions.lock_competition`
  (`CompetitionNotFound`); the status with a fresh clock (`NotChangeable`); the question or team
  under lock (`EntryNotFound`); then the insert or delete and one commit. Cancelling takes the
  same competition lock, so a change and a cancellation never interleave. Every refusal rolls
  back before it raises, so no lock outlives it; on SQLite the locks render nothing, and SQLite
  serialises writers anyway. The unique constraint and the primary key, not the lookup before
  the insert, are the guarantee against a second copy or link (`AlreadyIn`).

Each successful change logs one line with ids only: `Competition question added: competition=%d
question=%d`, `Competition question removed: …`, `Competition team added: competition=%d
team=%d`, `Competition team removed: …`. A no-op ("already", "absent") and a refusal log nothing;
no name or text is ever logged (FR-048).

**Contract for later milestones**: stopping (a later 12.x) freezes a competition's questions and
teams for good, deleted teams included. Milestone 13 shows a student the competitions one of
their teams is linked to, with the copies in `competition_questions`, in their order, never the
bank's. Milestones 14–15 score against the copy's text and reference answer, and list every
linked team in the results, deleted ones marked. A team's answers (milestone 12.3) are in
`app.services.team_answers`, which lists the teams through `team_entries` and `group_by_region`;
their grades (milestone 12.4) are in `app.services.grades`, which does the same. Both read the
questions through `question_copies`.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    Competition,
    CompetitionQuestion,
    CompetitionTeam,
    Institution,
    Question,
    Region,
    Subject,
    Team,
)
from app.services import competitions
from app.services.competitions import (
    CompetitionStatus,
    ManageRequired,
    status_of,
)
from app.services.paging import Paging, landing_index
from app.services.teacher_access import can_manage_competitions
from app.services.teams import count_active_members

logger = logging.getLogger("uvicorn.error")

EntryKind = Literal["question", "team"]


# ---------------------------------------------------------------------------------------------
# Errors (`competitions.ManageRequired` and `competitions.CompetitionNotFound` are re-used)
# ---------------------------------------------------------------------------------------------


class NotChangeable(ValueError):
    """The competition is not Upcoming, so its questions and teams can no longer change (409)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(f"Not changeable: {status}")
        self.status = status


class EntryNotFound(LookupError):
    """The question or team cannot be added (unknown, deleted, of another subject or region, or
    of a deactivated institution or region), or, on removal, names nothing at all: "Question not
    found" / "Team not found" (404)."""

    def __init__(self, kind: EntryKind) -> None:
        super().__init__(f"{kind.capitalize()} not found")
        self.kind = kind


class AlreadyIn(ValueError):
    """The question or team is already in the competition; nothing was stored (FR-035)."""

    def __init__(self, kind: EntryKind, entry_id: int) -> None:
        super().__init__(f"{kind.capitalize()} {entry_id} is already in the competition")
        self.kind = kind
        self.entry_id = entry_id


class NotIn(ValueError):
    """A known question or team that is not in the competition; nothing changed (FR-036)."""

    def __init__(self, kind: EntryKind, entry_id: int) -> None:
        super().__init__(f"{kind.capitalize()} {entry_id} is not in the competition")
        self.kind = kind
        self.entry_id = entry_id


# ---------------------------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CompetitionQuestionView:
    question_id: int
    """The bank id, also the number shown: "Question 12"."""
    text: str
    """The copy."""
    reference_answer: str
    """The copy."""
    deleted_from_bank: bool


@dataclass(frozen=True)
class CompetitionQuestionPage:
    questions: list[CompetitionQuestionView]
    """In the order of adding."""
    paging: Paging


@dataclass(frozen=True)
class TeamRow:
    team_id: int
    name: str
    institution_name: str
    active_members: int
    is_deleted: bool
    """Only in a Finished competition: deleting a team takes it out of every other one."""


@dataclass(frozen=True)
class RegionGroup[Row]:
    """One region's rows on a page of teams: `TeamRow` here, `AnswerTeamRow` on the team answers
    page (milestone 12.3)."""

    region_id: int
    region_name: str
    """As stored."""
    total: int
    """The region's listed teams, across all pages."""
    rows: list[Row]
    """This page's rows of the region."""


@dataclass(frozen=True)
class CompetitionTeamPage:
    groups: list[RegionGroup[TeamRow]]
    """This page: regions, then teams, by name ignoring case."""
    paging: Paging
    """Counts teams, not regions."""


@dataclass(frozen=True)
class AddableTeam:
    team_id: int
    name: str
    institution_name: str
    active_members: int


@dataclass(frozen=True)
class AddableTeamPage:
    teams: list[AddableTeam]
    """By name ignoring case, ties by id."""
    paging: Paging


@dataclass(frozen=True)
class Landing:
    """Where the competition's list lands after a removal (R11, R12)."""

    p: int
    entry_id: int | None
    """The question or team to show at its anchor; `None` for the empty state."""


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def _upcoming(
    session: Session, teacher_id: int, competition_id: int, subject_id: int
) -> tuple[Competition, Subject, datetime]:
    """Steps 1–3 of every write (R2): the setting, the competition locked, the status with a
    fresh clock. Returns the competition, its subject and the clock read."""
    if not can_manage_competitions(session, teacher_id, lock=True):
        session.rollback()
        raise ManageRequired()
    row, subject = competitions.lock_competition(session, competition_id, subject_id)
    now = competitions.utc_now()
    status = status_of(row, now)
    if status is not CompetitionStatus.UPCOMING:
        session.rollback()
        raise NotChangeable(status)
    return row, subject, now


def _question_copy(
    session: Session, competition_id: int, question_id: int
) -> CompetitionQuestion | None:
    statement = select(CompetitionQuestion).where(
        CompetitionQuestion.competition_id == competition_id,
        CompetitionQuestion.question_id == question_id,
    )
    return session.exec(statement).first()


def _ordered_question_ids(session: Session, competition_id: int) -> list[int]:
    """The bank ids of the competition's questions, in the order of adding."""
    statement = (
        select(CompetitionQuestion.question_id)
        .where(CompetitionQuestion.competition_id == competition_id)
        .order_by(col(CompetitionQuestion.id))
    )
    return list(session.exec(statement))


TeamEntry = tuple[Team, Institution, Region]


def team_entries(session: Session, competition_id: int) -> list[TeamEntry]:
    """The competition's teams with their institutions and regions (deleted teams and
    deactivated institutions and regions included; the caller filters), sorted by region, then
    team, by name ignoring case, ties by id (R12). Sorted in Python, so both engines agree."""
    statement = (
        select(Team, Institution, Region)
        .select_from(CompetitionTeam)
        .join(Team, col(Team.id) == col(CompetitionTeam.team_id))
        .join(Institution, col(Institution.id) == col(Team.institution_id))
        .join(Region, col(Region.id) == col(Institution.region_id))
        .where(CompetitionTeam.competition_id == competition_id)
    )
    return sorted(
        session.exec(statement),
        key=lambda entry: (entry[2].name_key, entry[2].id, entry[0].name_key, entry[0].id),
    )


def _team_row(team: Team, institution: Institution, counts: dict[int, int]) -> TeamRow:
    assert team.id is not None
    return TeamRow(
        team_id=team.id,
        name=team.name,
        institution_name=institution.name,
        active_members=counts.get(team.id, 0),
        is_deleted=team.deleted_at is not None,
    )


def _is_linked(session: Session, competition_id: int, team_id: int) -> bool:
    return session.get(CompetitionTeam, (competition_id, team_id)) is not None


# ---------------------------------------------------------------------------------------------
# Reads (no setting needed: every teacher reads)
# ---------------------------------------------------------------------------------------------


def question_page(session: Session, competition_id: int, p: int) -> CompetitionQuestionPage:
    """One page of the competition's questions in the order of adding, the page clamped to
    1..last: each the copy's text and reference answer, never the bank's, with the bank's
    deletion as a mark (R11)."""
    total = session.exec(
        select(func.count())
        .select_from(CompetitionQuestion)
        .where(CompetitionQuestion.competition_id == competition_id)
    ).one()
    paging = Paging.build(p, total)
    statement = (
        select(CompetitionQuestion, Question.deleted_at)
        .join(Question, col(Question.id) == col(CompetitionQuestion.question_id))
        .where(CompetitionQuestion.competition_id == competition_id)
        .order_by(col(CompetitionQuestion.id))
        .limit(paging.size)
        .offset(paging.offset)
    )
    views = [
        CompetitionQuestionView(
            question_id=copy.question_id,
            text=copy.text,
            reference_answer=copy.reference_answer,
            deleted_from_bank=deleted_at is not None,
        )
        for copy, deleted_at in session.exec(statement)
    ]
    return CompetitionQuestionPage(views, paging)


def question_copies(session: Session, competition_id: int) -> list[CompetitionQuestion]:
    """The competition's copies of its questions, in the order of adding (`CompetitionQuestion.id`).
    The questions of a team's answer sheet (`app.services.team_answers`, milestone 12.3) and of
    its grading sheet (`app.services.grades`, milestone 12.4), numbered from 1 in this order."""
    return list(
        session.exec(
            select(CompetitionQuestion)
            .where(CompetitionQuestion.competition_id == competition_id)
            .order_by(col(CompetitionQuestion.id))
        )
    )


def question_ids(session: Session, competition_id: int) -> set[int]:
    """The bank ids of the competition's questions: "Already in this competition"."""
    return set(_ordered_question_ids(session, competition_id))


def get_competition_question(
    session: Session, competition_id: int, question_id: int
) -> CompetitionQuestionView:
    """The competition's copy of the question, for the remove confirmation. `EntryNotFound` when
    no bank question has this id; `NotIn` for a known one that is not in the competition (R10).
    A question deleted from the bank is found."""
    question = session.get(Question, question_id)
    if question is None:
        raise EntryNotFound("question")
    copy = _question_copy(session, competition_id, question_id)
    if copy is None:
        raise NotIn("question", question_id)
    return CompetitionQuestionView(
        question_id=question_id,
        text=copy.text,
        reference_answer=copy.reference_answer,
        deleted_from_bank=question.deleted_at is not None,
    )


def group_by_region[Row](
    entries: list[TeamEntry], p: int, make_rows: Callable[[list[TeamEntry]], list[Row]]
) -> tuple[list[RegionGroup[Row]], Paging]:
    """One page of `entries` (sorted as `team_entries` sorts them), ten teams per page, the page
    clamped to 1..last, grouped by region: each group the region's rows on this page, with its
    total across all of `entries`, so a region continuing from the previous page shows the same
    total (R12). `make_rows` is called once, with the page's entries, and returns their rows in
    the same order, so the caller counts what it shows for the whole page in one query each."""
    totals: dict[int, int] = {}
    for _, _, region in entries:
        assert region.id is not None
        totals[region.id] = totals.get(region.id, 0) + 1
    paging = Paging.build(p, len(entries))
    shown = entries[paging.offset : paging.offset + paging.size]
    rows = make_rows(shown)
    groups: list[RegionGroup[Row]] = []
    for (_, _, region), row in zip(shown, rows, strict=True):
        assert region.id is not None
        if not groups or groups[-1].region_id != region.id:
            groups.append(RegionGroup(region.id, region.name, totals[region.id], []))
        groups[-1].rows.append(row)
    return groups, paging


def team_page(session: Session, competition_id: int, p: int) -> CompetitionTeamPage:
    """One page of the competition's teams, grouped by region (`group_by_region`, R12). The
    active members are counted for this page's teams in one query (R13)."""

    def make_rows(shown: list[TeamEntry]) -> list[TeamRow]:
        counts = count_active_members(session, [team.id for team, _, _ in shown if team.id])
        return [_team_row(team, institution, counts) for team, institution, _ in shown]

    groups, paging = group_by_region(team_entries(session, competition_id), p, make_rows)
    return CompetitionTeamPage(groups, paging)


def team_ids(session: Session, competition_id: int) -> set[int]:
    """The ids of the competition's teams: "Already in this competition"."""
    statement = select(CompetitionTeam.team_id).where(
        CompetitionTeam.competition_id == competition_id
    )
    return set(session.exec(statement))


def get_competition_team(
    session: Session, competition_id: int, team_id: int
) -> tuple[TeamRow, str]:
    """The team as the competition lists it, and its region's name as stored, for the remove
    confirmation. `EntryNotFound` when no team has this id; `NotIn` for a known one that is not
    in the competition (R10). A deleted team that is still linked is found."""
    team = session.get(Team, team_id)
    if team is None:
        raise EntryNotFound("team")
    if not _is_linked(session, competition_id, team_id):
        raise NotIn("team", team_id)
    institution = session.get(Institution, team.institution_id)
    assert institution is not None
    region = session.get(Region, institution.region_id)
    assert region is not None
    return _team_row(team, institution, count_active_members(session, [team_id])), region.name


def addable_teams(session: Session, region_id: int, p: int) -> AddableTeamPage:
    """One page of the region's live teams of active institutions, from every institution
    whether or not any teacher is linked to it, by name ignoring case, ties by id, ten per page,
    the page clamped to 1..last (R14). The caller has checked that the region is active."""
    statement = (
        select(Team, Institution)
        .join(Institution, col(Institution.id) == col(Team.institution_id))
        .where(
            Institution.region_id == region_id,
            col(Institution.is_active),
            col(Team.deleted_at).is_(None),
        )
    )
    entries = sorted(session.exec(statement), key=lambda entry: (entry[0].name_key, entry[0].id))
    paging = Paging.build(p, len(entries))
    shown = entries[paging.offset : paging.offset + paging.size]
    counts = count_active_members(session, [team.id for team, _ in shown if team.id])
    teams = []
    for team, institution in shown:
        assert team.id is not None
        teams.append(AddableTeam(team.id, team.name, institution.name, counts.get(team.id, 0)))
    return AddableTeamPage(teams, paging)


# ---------------------------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------------------------


def add_question(
    session: Session, teacher_id: int, competition_id: int, subject_id: int, question_id: int
) -> None:
    """Copy one question to the end of an upcoming competition's list, as a teacher with the
    setting: its text and reference answer as the bank holds them now (R3). The question is read
    `FOR SHARE`, so an edit or a deletion at the same moment either commits first and is seen,
    or waits until the copy is stored. Raises `ManageRequired`, `CompetitionNotFound`,
    `NotChangeable`, `EntryNotFound` (unknown, deleted, or of another subject) or `AlreadyIn`;
    nothing is stored then."""
    _, _, now = _upcoming(session, teacher_id, competition_id, subject_id)
    question = session.get(
        Question, question_id, with_for_update={"read": True}, populate_existing=True
    )
    if question is None or question.deleted_at is not None or question.subject_id != subject_id:
        session.rollback()
        raise EntryNotFound("question")
    if _question_copy(session, competition_id, question_id) is not None:
        session.rollback()
        raise AlreadyIn("question", question_id)
    session.add(
        CompetitionQuestion(
            competition_id=competition_id,
            question_id=question_id,
            text=question.text,
            reference_answer=question.reference_answer,
            added_at=now,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AlreadyIn("question", question_id) from None
    logger.info(
        "Competition question added: competition=%d question=%d", competition_id, question_id
    )


def add_team(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    region_id: int,
    team_id: int,
) -> None:
    """Add one team to an upcoming competition, as a teacher with the setting, linked to the
    team's institution or not (R4). The team, then its institution, then its region are read
    `FOR SHARE`, so a deletion or a deactivation at the same moment either commits first and is
    seen, or waits until the link is stored (and a team deletion then takes it out again, R5).
    Raises `ManageRequired`, `CompetitionNotFound`, `NotChangeable`, `EntryNotFound` (unknown,
    deleted, of another region than `region_id`, or of a deactivated institution or region) or
    `AlreadyIn`; nothing is stored then."""
    _, _, now = _upcoming(session, teacher_id, competition_id, subject_id)
    team = session.get(Team, team_id, with_for_update={"read": True}, populate_existing=True)
    institution = (
        session.get(
            Institution,
            team.institution_id,
            with_for_update={"read": True},
            populate_existing=True,
        )
        if team is not None and team.deleted_at is None
        else None
    )
    region = (
        session.get(
            Region, institution.region_id, with_for_update={"read": True}, populate_existing=True
        )
        if institution is not None and institution.is_active
        else None
    )
    if region is None or not region.is_active or region.id != region_id:
        session.rollback()
        raise EntryNotFound("team")
    if _is_linked(session, competition_id, team_id):
        session.rollback()
        raise AlreadyIn("team", team_id)
    session.add(CompetitionTeam(competition_id=competition_id, team_id=team_id, added_at=now))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AlreadyIn("team", team_id) from None
    logger.info("Competition team added: competition=%d team=%d", competition_id, team_id)


def remove_question(
    session: Session, teacher_id: int, competition_id: int, subject_id: int, question_id: int
) -> Landing:
    """Take one question out of an upcoming competition, as a teacher with the setting: its copy
    is deleted, and the bank question is left as it is. A question deleted from the bank can be
    removed too. Raises `ManageRequired`, `CompetitionNotFound`, `NotChangeable`,
    `EntryNotFound` (no bank question has this id) or `NotIn`; nothing changes then.

    Returns where the competition's list lands (R11): with `i` the question's index in the order
    of adding, the row now at `i`, else the one before it, else the empty state.
    """
    _upcoming(session, teacher_id, competition_id, subject_id)
    if session.get(Question, question_id) is None:
        session.rollback()
        raise EntryNotFound("question")
    before = _ordered_question_ids(session, competition_id)
    if question_id not in before:
        session.rollback()
        raise NotIn("question", question_id)
    result = session.execute(
        delete(CompetitionQuestion).where(
            col(CompetitionQuestion.competition_id) == competition_id,
            col(CompetitionQuestion.question_id) == question_id,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        session.rollback()
        raise NotIn("question", question_id)
    after = _ordered_question_ids(session, competition_id)
    session.commit()
    logger.info(
        "Competition question removed: competition=%d question=%d", competition_id, question_id
    )
    return Landing(*landing_index(after, None, before.index(question_id)))


def remove_team(
    session: Session, teacher_id: int, competition_id: int, subject_id: int, team_id: int
) -> Landing:
    """Take one team out of an upcoming competition, as a teacher with the setting: only the
    link is deleted; the team and its members are left as they are. Raises `ManageRequired`,
    `CompetitionNotFound`, `NotChangeable`, `EntryNotFound` (no team has this id) or `NotIn`;
    nothing changes then.

    Returns where the competition's list lands (R12), in the list's order of regions, then
    teams: the row now at the team's index, else the one before it, else the empty state.
    """
    _upcoming(session, teacher_id, competition_id, subject_id)
    if session.get(Team, team_id) is None:
        session.rollback()
        raise EntryNotFound("team")
    before = [team.id for team, _, _ in team_entries(session, competition_id)]
    if team_id not in before:
        session.rollback()
        raise NotIn("team", team_id)
    result = session.execute(
        delete(CompetitionTeam).where(
            col(CompetitionTeam.competition_id) == competition_id,
            col(CompetitionTeam.team_id) == team_id,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        session.rollback()
        raise NotIn("team", team_id)
    after = [team.id for team, _, _ in team_entries(session, competition_id) if team.id]
    session.commit()
    logger.info("Competition team removed: competition=%d team=%d", competition_id, team_id)
    return Landing(*landing_index(after, None, before.index(team_id)))
