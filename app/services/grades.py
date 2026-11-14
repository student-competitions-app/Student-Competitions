"""The grades of a finished competition's answers: the Grades page (every team with its progress),
a team's grading sheet, and saving its grades. Only a teacher with **Can manage competitions**
grades, every team of the competition whatever the teacher's links, and only once the
competition is **Finished**.

See specs/012.4-finish-and-grade/contracts/services.md §`grades` and research R2–R6. Reading needs
the setting and a finished competition, which the routes check first (the caller has found the
competition with `find_context` and checked its status).

- **A grade belongs to an answer** (R2): `team_answers.grade`, a whole number 0–10 or `NULL` for
  not graded. A question with no answer has no row, so nothing to grade. Who graded an answer, or
  when, is not stored (FR-028).
- **Answered, Graded and Score are counted, never stored** (R5): `grade_counts` reads the rows of
  the whole competition in one grouped query. A team is **fully graded** when every answer it gave
  has a grade, so a team with no answers is.
- **Every team is listed and graded** (R6): the 12.2 `team_entries`, deleted teams and teams of a
  deactivated institution or region included, grouped and paged by `group_by_region`. **Ungraded
  only** lists the teams with an answer still to grade.
- **The clock** is `app.services.competitions.utc_now`, read through that module once per call,
  so tests that move the 12.1 clock move this one too.
- **The save, in this order** (R3, FR-043): the setting `FOR SHARE` (`ManageRequired`); the
  competition `FOR SHARE` and its subject `FOR SHARE` (`competitions.lock_competition(share=True)`,
  `CompetitionNotFound`); the status with a fresh clock, which must be **Finished**
  (`GradingClosed`); the team, then its link to the competition `FOR UPDATE`
  (`GradedTeamNotFound`); the named questions, each a copy of the competition that the team
  answered (`GradedQuestionNotFound`); the grades (`InvalidGrades`); then the change and one
  commit. Every refusal rolls back first, so no lock outlives it and nothing is stored. On SQLite
  the locks render nothing, and SQLite serialises writers anyway.
- **The last save wins** (R3, FR-030): the link's `FOR UPDATE` queues two saves of one team, and
  each writes exactly the grades it names, compared against the rows read again under the lock.
  An answer the save does not name keeps its grade. Saves of different teams do not wait for each
  other: the competition is held `FOR SHARE` only. The save never writes an answer's text.

A save logs one line with ids and counts only: `Grades saved: competition=%d team=%d graded=%d
changed=%d`, also when nothing changed. A refusal logs nothing; no name, question text, answer
text or grade value is ever logged (FR-045).

**The imports run one way**: `team_answers` → `grades` → `competition_entries`. This module never
imports `app.services.team_answers`, which reads `grade_counts` for its finished pages.

**Contract for later milestones**: milestone 14 proposes a grade for each row of a **Finished**
competition; the stored `team_answers.grade`, proposed or adjusted through `save_grades`, is the
one that counts. Milestone 15 reads a team's score as `grade_counts(…)[team].score` and works out
places from it, never storing them apart from the grades.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import CompetitionQuestion, CompetitionTeam, Institution, Team, TeamAnswer
from app.schemas.grade import InvalidGrade, clean_grade
from app.services import competitions
from app.services.competition_entries import (
    RegionGroup,
    TeamEntry,
    group_by_region,
    question_copies,
    team_entries,
)
from app.services.competitions import CompetitionStatus, ManageRequired
from app.services.paging import PAGE_SIZE, Paging
from app.services.teacher_access import can_manage_competitions
from app.services.teams import count_active_members

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GradeCount:
    """A team's progress in a competition."""

    answered: int
    """The team's answers."""
    graded: int
    """Its answers with a grade."""
    score: int
    """The sum of its grades, 0 when none is graded."""

    @property
    def fully_graded(self) -> bool:
        """Every answer has a grade; so a team with no answers is fully graded."""
        return self.graded == self.answered


NO_ANSWERS = GradeCount(0, 0, 0)
"""The count of a team with no answer, which `grade_counts` leaves out."""


class GradeFilter(StrEnum):
    """The filter of the Grades page; the value is the address's `show=`."""

    ALL = "all"
    UNGRADED = "ungraded"


def parse_grade_filter(raw: str | None) -> GradeFilter:
    """`"ungraded"`, exactly, is **Ungraded only**; anything else, or nothing, **All teams**."""
    return GradeFilter.UNGRADED if raw == GradeFilter.UNGRADED.value else GradeFilter.ALL


@dataclass(frozen=True)
class GradeTeamRow:
    team_id: int
    name: str
    institution_name: str
    active_members: int
    is_deleted: bool
    answered: int
    questions: int
    """The competition's questions."""
    graded: int
    score: int


@dataclass(frozen=True)
class GradeTeamPage:
    groups: list[RegionGroup[GradeTeamRow]]
    """This page: regions, then teams, by name ignoring case."""
    paging: Paging
    """Counts the teams listed under the filter."""
    teams_total: int
    """All the competition's teams, whatever the filter."""
    teams_graded: int
    """The fully graded ones among them."""


@dataclass(frozen=True)
class GradingQuestion:
    competition_question_id: int
    """The grade field is `grade-<id>`."""
    number: int
    """1, 2, 3, … in the order of adding."""
    text: str
    """The competition's copy."""
    reference_answer: str
    """The competition's copy; shown on the grading sheet only."""
    answer: str | None
    """The team's answer; `None` when not answered (no grade field)."""
    grade: int | None


@dataclass(frozen=True)
class GradingSheet:
    team_id: int
    team_name: str
    institution_name: str
    is_deleted: bool
    questions: list[GradingQuestion]
    count: GradeCount


@dataclass(frozen=True)
class GradeSaveResult:
    graded: int
    """The team's graded answers after the save."""
    changed: int
    """The grades the save set, changed or emptied."""


# ---------------------------------------------------------------------------------------------
# Errors (`competitions.ManageRequired` and `competitions.CompetitionNotFound` are re-used)
# ---------------------------------------------------------------------------------------------


class GradingClosed(ValueError):
    """The competition is not Finished, so its answers cannot be graded (409)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class GradedTeamNotFound(LookupError):
    """Unknown, or not in the competition. Unlike `team_answers.TeamNotFound`, a deleted team, or
    one of a deactivated institution or region, is found: a finished competition keeps every
    team, and every one is graded."""


class GradedQuestionNotFound(LookupError):
    """Not one of the competition's questions, or one the team did not answer. Unlike
    `team_answers.QuestionNotFound`, an unanswered question is refused: it has no answer to
    grade."""


class InvalidGrades(ValueError):
    """Some grades are not whole numbers from 0 to 10; nothing was saved."""

    def __init__(self, errors: dict[int, str]) -> None:
        super().__init__(f"{len(errors)} invalid grades")
        self.errors = errors
        """The message of each invalid grade, by `competition_question_id`, in question order."""


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def _rollback(session: Session, error: Exception) -> Exception:
    """`error`, after a rollback, so no lock outlives the refusal."""
    session.rollback()
    return error


def _stored_answers(
    session: Session, competition_id: int, team_id: int, *, refresh: bool = False
) -> dict[int, TeamAnswer]:
    """The team's answers in the competition, by `competition_question_id`. With `refresh`, the
    rows are read again, so a save under the link's lock sees what an earlier save committed."""
    statement = select(TeamAnswer).where(
        TeamAnswer.competition_id == competition_id, TeamAnswer.team_id == team_id
    )
    if refresh:
        statement = statement.execution_options(populate_existing=True)
    return {answer.competition_question_id: answer for answer in session.exec(statement)}


def count_of(counts: Mapping[int, GradeCount], team_id: int) -> GradeCount:
    """The team's count from `grade_counts`, `GradeCount(0, 0, 0)` for a team with no answer."""
    return counts.get(team_id, NO_ANSWERS)


def _listed(
    session: Session, competition_id: int, show: GradeFilter
) -> tuple[list[TeamEntry], list[TeamEntry], dict[int, GradeCount]]:
    """`(all entries, the entries listed under show, the counts)`: every team of the competition
    (`team_entries`, nothing filtered out), and under **Ungraded only** those with an answer still
    to grade."""
    entries = team_entries(session, competition_id)
    counts = grade_counts(session, competition_id)
    if show is GradeFilter.ALL:
        return entries, entries, counts
    listed = [
        entry
        for entry in entries
        if entry[0].id is not None and not count_of(counts, entry[0].id).fully_graded
    ]
    return entries, listed, counts


# ---------------------------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------------------------


def grade_counts(session: Session, competition_id: int) -> dict[int, GradeCount]:
    """Each team's answered, graded and score in the competition, in one grouped query. A team
    with no answer is absent from the result: read it with `count_of`."""
    statement = (
        select(
            TeamAnswer.team_id,
            func.count(),
            func.count(TeamAnswer.grade),
            func.coalesce(func.sum(TeamAnswer.grade), 0),
        )
        .where(TeamAnswer.competition_id == competition_id)
        .group_by(TeamAnswer.team_id)
    )
    return {
        team_id: GradeCount(answered, graded, int(score))
        for team_id, answered, graded, score in session.exec(statement)
    }


def grade_team_page(
    session: Session, competition_id: int, show: GradeFilter, p: int
) -> GradeTeamPage:
    """One page of the competition's teams listed under `show`, ten per page, the page clamped to
    1..last, grouped by region; the region totals and the paging count only the listed teams,
    while `teams_total` and `teams_graded` count all of them (FR-015–FR-019). The active members
    are counted for the page's teams in one query."""
    entries, listed, counts = _listed(session, competition_id, show)
    questions = session.exec(
        select(func.count()).where(CompetitionQuestion.competition_id == competition_id)
    ).one()

    def make_rows(shown: list[TeamEntry]) -> list[GradeTeamRow]:
        members = count_active_members(session, [team.id for team, _, _ in shown if team.id])
        rows = []
        for team, institution, _ in shown:
            assert team.id is not None
            count = count_of(counts, team.id)
            rows.append(
                GradeTeamRow(
                    team_id=team.id,
                    name=team.name,
                    institution_name=institution.name,
                    active_members=members.get(team.id, 0),
                    is_deleted=team.deleted_at is not None,
                    answered=count.answered,
                    questions=questions,
                    graded=count.graded,
                    score=count.score,
                )
            )
        return rows

    groups, paging = group_by_region(listed, p, make_rows)
    graded = sum(1 for team, _, _ in entries if team.id and count_of(counts, team.id).fully_graded)
    return GradeTeamPage(groups, paging, teams_total=len(entries), teams_graded=graded)


def is_listed(session: Session, competition_id: int, team_id: int, show: GradeFilter) -> bool:
    """Whether the Grades page under `show` lists the team: it is in the competition and, under
    **Ungraded only**, has an answer still to grade. The grading sheet's back link is anchored at
    the team only then (FR-020)."""
    _, listed, _ = _listed(session, competition_id, show)
    return any(team.id == team_id for team, _, _ in listed)


def team_page_of(session: Session, competition_id: int, team_id: int, show: GradeFilter) -> int:
    """The page of the Grades page under `show` that holds the team, 1 if it is not listed: the
    grading sheet's way back when its address carries no valid page (as 12.3's
    `team_answers.team_page_of`)."""
    _, listed, _ = _listed(session, competition_id, show)
    ids = [team.id for team, _, _ in listed]
    return ids.index(team_id) // PAGE_SIZE + 1 if team_id in ids else 1


def grading_sheet(session: Session, competition_id: int, team_id: int) -> GradingSheet:
    """The team's grading sheet: every question of the competition in the order of adding, each
    with its reference answer, the team's answer (or `None`) and its grade. `GradedTeamNotFound`
    for an unknown team or one not in the competition; a deleted team, or one of a deactivated
    institution or region, is found. No access check: the caller holds the setting and has
    checked the competition and its status."""
    team = session.get(Team, team_id)
    if team is None or session.get(CompetitionTeam, (competition_id, team_id)) is None:
        raise GradedTeamNotFound()
    institution = session.get(Institution, team.institution_id)
    assert institution is not None
    stored = _stored_answers(session, competition_id, team_id)
    questions = []
    for index, copy in enumerate(question_copies(session, competition_id)):
        assert copy.id is not None
        answer = stored.get(copy.id)
        questions.append(
            GradingQuestion(
                competition_question_id=copy.id,
                number=index + 1,
                text=copy.text,
                reference_answer=copy.reference_answer,
                answer=answer.text if answer is not None else None,
                grade=answer.grade if answer is not None else None,
            )
        )
    count = GradeCount(
        answered=len(stored),
        graded=sum(1 for answer in stored.values() if answer.grade is not None),
        score=sum(answer.grade for answer in stored.values() if answer.grade is not None),
    )
    return GradingSheet(
        team_id=team_id,
        team_name=team.name,
        institution_name=institution.name,
        is_deleted=team.deleted_at is not None,
        questions=questions,
        count=count,
    )


# ---------------------------------------------------------------------------------------------
# The save
# ---------------------------------------------------------------------------------------------


def save_grades(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    team_id: int,
    raw_grades: Mapping[int, str],
) -> GradeSaveResult:
    """Save the grades of the team's answers that `raw_grades` names (by
    `competition_question_id`, the values as sent), as a teacher with the setting, while the
    competition is Finished: every check of R3 in order, under lock, then the change and one
    commit. Raises `ManageRequired`, `CompetitionNotFound`, `GradingClosed`,
    `GradedTeamNotFound`, `GradedQuestionNotFound` or `InvalidGrades`; nothing is stored then."""
    if not can_manage_competitions(session, teacher_id, lock=True):
        raise _rollback(session, ManageRequired())
    competition, _ = competitions.lock_competition(session, competition_id, subject_id, share=True)
    status = competitions.status_of(competition, competitions.utc_now())
    if status is not CompetitionStatus.FINISHED:
        raise _rollback(session, GradingClosed(status))
    if session.get(Team, team_id) is None:
        raise _rollback(session, GradedTeamNotFound())
    link = session.get(
        CompetitionTeam, (competition_id, team_id), with_for_update=True, populate_existing=True
    )
    if link is None:
        raise _rollback(session, GradedTeamNotFound())
    numbers = {
        copy.id: index + 1 for index, copy in enumerate(question_copies(session, competition_id))
    }
    stored = _stored_answers(session, competition_id, team_id, refresh=True)
    if any(question_id not in numbers or question_id not in stored for question_id in raw_grades):
        raise _rollback(session, GradedQuestionNotFound())
    cleaned: dict[int, int | None] = {}
    errors: dict[int, str] = {}
    for question_id in sorted(raw_grades, key=numbers.__getitem__):
        try:
            cleaned[question_id] = clean_grade(raw_grades[question_id])
        except InvalidGrade as error:
            errors[question_id] = error.message
    if errors:
        raise _rollback(session, InvalidGrades(errors))
    changed = 0
    for question_id, grade in cleaned.items():
        answer = stored[question_id]
        if answer.grade != grade:
            answer.grade = grade
            session.add(answer)
            changed += 1
    graded = sum(1 for answer in stored.values() if answer.grade is not None)
    session.commit()
    logger.info(
        "Grades saved: competition=%d team=%d graded=%d changed=%d",
        competition_id,
        team_id,
        graded,
        changed,
    )
    return GradeSaveResult(graded=graded, changed=changed)
