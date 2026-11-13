"""A team's answers in a competition: the team answers page every teacher reads (their own
institutions' teams with their progress), the answer sheet, and saving it, which only a teacher
with **Write** access to the team's institution does, and only while the competition is **In
progress**.

See specs/012.3-team-answers/contracts/services.md and research R1–R7, R11. Reading needs only
the teacher role, which the routes check, and a competition the caller has already found with
`competitions.get_competition` (its subject and visibility checked).

- **An answer belongs to a team** (R1): one row per answered question of the competition, keyed
  by the competition's copy of the question (R2); an emptied answer deletes its row, so a team's
  progress is a count of its rows. Neither who saved an answer nor when is stored (FR-023).
- **The listing** (R6, R11): the competition's live teams whose institution the teacher reaches
  (`teacher_access.list_reachable_institutions`: linked, active, in an active region), grouped
  by region with the 12.2 grouping (`competition_entries.group_by_region`), each with its
  progress and whether the teacher may write. The links are read on every call (FR-013).
- **The clock** is `app.services.competitions.utc_now`, read through that module once per call,
  so tests that move the 12.1 clock move this one too.
- **The save, in this order** (R3, FR-025): the competition `FOR SHARE` and its subject `FOR
  SHARE` (`competitions.lock_competition(share=True)`, `CompetitionNotFound`); the status with a
  fresh clock (`AnswersClosed`); the team `FOR SHARE`, then its link to the competition `FOR
  UPDATE`, then its institution and region `FOR SHARE` (`TeamNotFound`); the named questions
  (`QuestionNotFound`); **Write** access under lock (`AnswersDenied`); the texts
  (`InvalidAnswers`); then the change and one commit. Every refusal rolls back first, so no lock
  outlives it and nothing is stored. On SQLite the locks render nothing, and SQLite serialises
  writers anyway.
- **The last save wins** (R4, FR-024): the link's `FOR UPDATE` queues two saves of one team, and
  each writes exactly the answers it names: an empty one deletes the row, an equal one writes
  nothing, any other inserts or updates it. A question the save does not name keeps its row.

A save logs one line with ids and counts only: `Team answers saved: competition=%d team=%d
answered=%d changed=%d`, also when nothing changed. A refusal logs nothing; no name, question
text or answer text is ever logged (FR-031).

**Contract for later milestones**: grading by hand (a later 12.x) grades these rows; a question
with no row has no answer to grade. Milestone 13 lets a team's students save through the same
steps, with the access step replaced by "the student is a member of the team", into the same
rows, the last save winning whoever made it. Milestone 14 scores each row against its copy's text
and reference answer; a changed row needs scoring again. Milestone 15 reads the answers of every
team, deleted ones included, of a finished competition.
"""

import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import CompetitionQuestion, CompetitionTeam, Institution, Region, Team, TeamAnswer
from app.schemas.answer import InvalidAnswer, clean_answer
from app.services import competitions
from app.services.competition_entries import (
    RegionGroup,
    TeamEntry,
    group_by_region,
    team_entries,
)
from app.services.competitions import CompetitionStatus
from app.services.paging import PAGE_SIZE, Paging
from app.services.teacher_access import (
    NotReachable,
    ReachableInstitution,
    WriteRequired,
    list_reachable_institutions,
    reach_institution,
)
from app.services.teams import count_active_members

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------------------------


class AnswersClosed(ValueError):
    """The competition is not In progress, so its answers cannot be entered (FR-026)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class TeamNotFound(LookupError):
    """The team is unknown, deleted, not in the competition, or of a deactivated institution or
    region."""


class QuestionNotFound(LookupError):
    """A save names a question that is not one of the competition's."""


class AnswersDenied(PermissionError):
    """The teacher is not linked to the team's institution, or only with Read access."""


class InvalidAnswers(ValueError):
    """Some answers break a rule (`app.schemas.answer`); nothing was saved."""

    def __init__(self, errors: dict[int, str]) -> None:
        super().__init__(f"{len(errors)} invalid answers")
        self.errors = errors
        """The message of each invalid answer, by `competition_question_id`, in question order."""


# ---------------------------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AnswerTeamRow:
    team_id: int
    name: str
    institution_name: str
    active_members: int
    answered: int
    """The team's answers in the competition."""
    questions: int
    """The competition's questions."""
    can_write: bool
    """Write access to the team's institution: **Enter answers**, else "Read access"."""


@dataclass(frozen=True)
class AnswerTeamPage:
    groups: list[RegionGroup[AnswerTeamRow]]
    """This page: regions, then teams, by name ignoring case."""
    paging: Paging
    """Counts the listed teams."""
    linked: bool
    """The teacher reaches at least one institution (linked, active, in an active region)."""


@dataclass(frozen=True)
class SheetQuestion:
    competition_question_id: int
    """The answer field is `answer-<id>`."""
    number: int
    """1, 2, 3, … in the order of adding."""
    text: str
    """The competition's copy; never the reference answer."""
    answer: str
    """The saved answer, `""` when the question is not answered."""


@dataclass(frozen=True)
class AnswerSheet:
    team_id: int
    team_name: str
    institution_name: str
    questions: list[SheetQuestion]


@dataclass(frozen=True)
class SaveResult:
    answered: int
    """The team's answered questions in the competition after the save."""
    changed: int
    """The answers the save inserted, updated or deleted."""


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def _question_copies(session: Session, competition_id: int) -> list[CompetitionQuestion]:
    """The competition's copies of its questions, in the order of adding."""
    return list(
        session.exec(
            select(CompetitionQuestion)
            .where(CompetitionQuestion.competition_id == competition_id)
            .order_by(col(CompetitionQuestion.id))
        )
    )


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


def _listed_entries(
    session: Session, competition_id: int, reachable: Mapping[int, ReachableInstitution]
) -> list[TeamEntry]:
    """The competition's live teams whose institution is in `reachable`, sorted as
    `team_entries` sorts them. The reachable institutions are active and in active regions, so
    the teams of a deactivated institution or region are dropped too (FR-005)."""
    return [
        entry
        for entry in team_entries(session, competition_id)
        if entry[0].deleted_at is None and entry[1].id in reachable
    ]


def _reachable(session: Session, teacher_id: int) -> dict[int, ReachableInstitution]:
    return {i.id: i for i in list_reachable_institutions(session, teacher_id)}


def _rollback(session: Session, error: Exception) -> Exception:
    """`error`, after a rollback, so no lock outlives the refusal."""
    session.rollback()
    return error


# ---------------------------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------------------------


def count_answered(
    session: Session, competition_id: int, team_ids: Collection[int]
) -> dict[int, int]:
    """The number of answered questions of each team in the competition, in one grouped query. A
    team with no answer is absent from the result: read it as 0. No query for no ids."""
    if not team_ids:
        return {}
    statement = (
        select(TeamAnswer.team_id, func.count())
        .where(
            TeamAnswer.competition_id == competition_id,
            col(TeamAnswer.team_id).in_(team_ids),
        )
        .group_by(TeamAnswer.team_id)
    )
    return {team_id: count for team_id, count in session.exec(statement)}


def answer_team_page(
    session: Session, teacher_id: int, competition_id: int, p: int
) -> AnswerTeamPage:
    """One page of the competition's teams the teacher reaches, ten per page, the page clamped
    to 1..last, grouped by region; the totals count only the listed teams (FR-005–FR-010). The
    active members and the answered questions are counted for the page's teams in one query
    each, and the progress is counted, never stored (FR-009)."""
    reachable = _reachable(session, teacher_id)
    entries = _listed_entries(session, competition_id, reachable)
    questions = session.exec(
        select(func.count()).where(CompetitionQuestion.competition_id == competition_id)
    ).one()

    def make_rows(shown: list[TeamEntry]) -> list[AnswerTeamRow]:
        team_ids = [team.id for team, _, _ in shown if team.id is not None]
        members = count_active_members(session, team_ids)
        answered = count_answered(session, competition_id, team_ids)
        rows = []
        for team, institution, _ in shown:
            assert team.id is not None and institution.id is not None
            rows.append(
                AnswerTeamRow(
                    team_id=team.id,
                    name=team.name,
                    institution_name=institution.name,
                    active_members=members.get(team.id, 0),
                    answered=answered.get(team.id, 0),
                    questions=questions,
                    can_write=reachable[institution.id].can_write,
                )
            )
        return rows

    groups, paging = group_by_region(entries, p, make_rows)
    return AnswerTeamPage(groups, paging, linked=bool(reachable))


def team_page_of(session: Session, teacher_id: int, competition_id: int, team_id: int) -> int:
    """The page of the teacher's team answers page that holds the team, 1 if it is not listed:
    the sheet's way back when its address carries no valid page (R10)."""
    entries = _listed_entries(session, competition_id, _reachable(session, teacher_id))
    ids = [team.id for team, _, _ in entries]
    return ids.index(team_id) // PAGE_SIZE + 1 if team_id in ids else 1


def answer_sheet(
    session: Session, teacher_id: int, competition_id: int, team_id: int
) -> AnswerSheet:
    """The team's answer sheet: every question of the competition in the order of adding, each
    with the team's saved answer, never the reference answer (FR-015, FR-016). Checks, without
    locks, in the save's order: the team (`TeamNotFound`), then **Write** access to its
    institution (`AnswersDenied`). The caller has checked the competition and its status."""
    team = session.get(Team, team_id)
    if team is None or team.deleted_at is not None:
        raise TeamNotFound()
    if session.get(CompetitionTeam, (competition_id, team_id)) is None:
        raise TeamNotFound()
    institution = session.get(Institution, team.institution_id)
    region = session.get(Region, institution.region_id) if institution is not None else None
    if institution is None or region is None or not (institution.is_active and region.is_active):
        raise TeamNotFound()
    try:
        reach_institution(session, teacher_id, team.institution_id, write=True)
    except (NotReachable, WriteRequired) as error:
        raise AnswersDenied() from error
    stored = _stored_answers(session, competition_id, team_id)
    questions = []
    for index, copy in enumerate(_question_copies(session, competition_id)):
        assert copy.id is not None
        answer = stored.get(copy.id)
        questions.append(
            SheetQuestion(
                competition_question_id=copy.id,
                number=index + 1,
                text=copy.text,
                answer=answer.text if answer is not None else "",
            )
        )
    return AnswerSheet(team_id, team.name, institution.name, questions)


# ---------------------------------------------------------------------------------------------
# The save
# ---------------------------------------------------------------------------------------------


def _lock_team(session: Session, competition_id: int, team_id: int) -> Team:
    """R3 step 3: the team `FOR SHARE`, its link to the competition `FOR UPDATE`, then its
    institution and region `FOR SHARE`, all refreshed; `TeamNotFound`, after a rollback, for an
    unknown, deleted or unlinked team, or one of a deactivated institution or region."""
    team = session.get(Team, team_id, with_for_update={"read": True}, populate_existing=True)
    if team is None or team.deleted_at is not None:
        raise _rollback(session, TeamNotFound())
    link = session.get(
        CompetitionTeam,
        (competition_id, team_id),
        with_for_update=True,
        populate_existing=True,
    )
    if link is None:
        raise _rollback(session, TeamNotFound())
    institution = session.get(
        Institution, team.institution_id, with_for_update={"read": True}, populate_existing=True
    )
    region = (
        session.get(
            Region, institution.region_id, with_for_update={"read": True}, populate_existing=True
        )
        if institution is not None
        else None
    )
    if institution is None or region is None or not (institution.is_active and region.is_active):
        raise _rollback(session, TeamNotFound())
    return team


def save_answers(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    team_id: int,
    raw_answers: Mapping[int, str],
) -> SaveResult:
    """Save the team's answers to the questions `raw_answers` names (by `competition_question_id`,
    the texts as sent), as a teacher with **Write** access to the team's institution, while the
    competition is In progress: every check of R3 in order, under lock, then the change of R4
    and one commit. Raises `CompetitionNotFound`, `AnswersClosed`, `TeamNotFound`,
    `QuestionNotFound`, `AnswersDenied` or `InvalidAnswers`; nothing is stored then."""
    competition, _ = competitions.lock_competition(session, competition_id, subject_id, share=True)
    status = competitions.status_of(competition, competitions.utc_now())
    if status is not CompetitionStatus.IN_PROGRESS:
        raise _rollback(session, AnswersClosed(status))
    team = _lock_team(session, competition_id, team_id)
    numbers = {
        copy.id: index + 1 for index, copy in enumerate(_question_copies(session, competition_id))
    }
    if any(question_id not in numbers for question_id in raw_answers):
        raise _rollback(session, QuestionNotFound())
    try:
        reach_institution(session, teacher_id, team.institution_id, write=True, lock=True)
    except (NotReachable, WriteRequired) as error:
        raise AnswersDenied() from error
    cleaned: dict[int, str] = {}
    errors: dict[int, str] = {}
    for question_id in sorted(raw_answers, key=numbers.__getitem__):
        try:
            cleaned[question_id] = clean_answer(raw_answers[question_id], numbers[question_id])
        except InvalidAnswer as error:
            errors[question_id] = error.message
    if errors:
        raise _rollback(session, InvalidAnswers(errors))
    stored = _stored_answers(session, competition_id, team_id, refresh=True)
    changed = 0
    for question_id, text in cleaned.items():
        current = stored.pop(question_id, None)
        if not text:
            if current is not None:
                session.delete(current)
                changed += 1
            continue
        if current is not None and current.text == text:
            stored[question_id] = current
            continue
        if current is None:
            current = TeamAnswer(
                competition_id=competition_id,
                team_id=team_id,
                competition_question_id=question_id,
                text=text,
            )
        else:
            current.text = text
        session.add(current)
        stored[question_id] = current
        changed += 1
    answered = len(stored)
    session.commit()
    logger.info(
        "Team answers saved: competition=%d team=%d answered=%d changed=%d",
        competition_id,
        team_id,
        answered,
        changed,
    )
    return SaveResult(answered=answered, changed=changed)
