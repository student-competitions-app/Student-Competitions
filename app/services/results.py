"""The published results of a competition: publishing them, the snapshot they hold, and the stored
files every teacher downloads (milestone 12.8).

See specs/012.8-publishing-results/contracts/services.md §1, data-model.md §2, §4, §5 and research
R3, R5, R7, R9.

- **Who publishes**: a teacher with **Can manage competitions**, any competition whoever created
  it, and only a **Finished** competition every team of which is fully graded (`grades`
  `grading_progress`). Publishing is permanent: the competition becomes **Published**, and from
  then on `grades.save_grades` refuses every change.
- **The publish, in this order** (research R5): the setting `FOR SHARE`; the competition `FOR
  UPDATE` and its subject `FOR SHARE` (`competitions.lock_competition`); the status with a fresh
  clock, which must be **Finished**; the grading, complete; the snapshot and both files rendered
  in memory; the conditional update of `published_at`; the two file rows; one commit. Every
  refusal rolls back first, so no lock outlives it and nothing is stored. A grade save holds the
  competition `FOR SHARE`, so a save and a publish never interleave: a save that came first is
  in the files, and a save that comes after reads **Published**.
- **The files are snapshots** (constitution Principle VII): made once, in the publishing
  transaction, one per language, and never made again, updated or deleted. Every download hands
  out the stored bytes, so nothing is calculated again and a later rename, deactivation or
  deletion changes nothing in them. The primary key `(competition_id, language)` keeps a lost race
  on SQLite, where the row locks render nothing, from storing a second pair.
- **The clock** is `app.services.competitions.utc_now`, read through that module once per call,
  so tests that move the 12.1 clock move this one too.

A publish logs one line with ids, counts and sizes only: `Results published: id=%d teams=%d
bytes=%d`. A refusal and a download log nothing; no name of any kind is ever logged.

**The imports run one way**: `results` → `results_pdf`, `grades`, `competitions`,
`competition_entries`. Only the routers and the sample script import this module.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.i18n import Language
from app.core.time_zone import KYIV
from app.models import Competition, CompetitionQuestion, CompetitionResultsFile, Subject
from app.schemas.grade import GRADE_MAX
from app.schemas.names import name_sort_key
from app.services import competitions, results_pdf
from app.services.competition_entries import team_entries
from app.services.competitions import CompetitionStatus, Landing, ManageRequired
from app.services.file_names import clean_file_stem
from app.services.grades import GradingProgress, count_of, grade_counts, grading_progress
from app.services.teacher_access import can_manage_competitions

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultLine:
    """One team in the results: "School No. 5, Comets, 17"."""

    institution: str
    team: str
    score: int
    """The sum of the team's grades; 0 for a team with no answers."""


@dataclass(frozen=True)
class RegionResults:
    name: str
    lines: tuple[ResultLine, ...]
    """Institutions, then teams within each, in the Ukrainian alphabet order."""


@dataclass(frozen=True)
class ResultsSnapshot:
    """Everything a results file shows, read once at publishing (data-model.md §5). Plain
    strings and numbers only, so the renderer never touches the database and the sample script
    can build one in memory."""

    competition_name: str
    subject_name: str
    starts_at: datetime
    """UTC."""
    finished_at: datetime
    """UTC: `competitions.stopped_at`."""
    published_at: datetime
    """UTC: the publishing moment."""
    max_score: int
    """The highest score a team could reach: the grade scale's maximum (10) for each of the
    competition's questions (design review round 1)."""
    regions: tuple[RegionResults, ...]
    """In the Ukrainian alphabet order; empty for a competition with no teams."""


# ---------------------------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------------------------


class NotPublishable(ValueError):
    """The competition is not **Finished**: Upcoming, In progress, Cancelled or already
    Published (409)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class NotFullyGraded(ValueError):
    """A team of the competition still has an answer without a grade (409)."""

    def __init__(self, progress: GradingProgress) -> None:
        super().__init__(f"{progress.graded} of {progress.total}")
        self.progress = progress


# ---------------------------------------------------------------------------------------------
# The snapshot
# ---------------------------------------------------------------------------------------------


def build_snapshot(
    session: Session, competition: Competition, subject: Subject, published_at: datetime
) -> ResultsSnapshot:
    """The results of every team of the competition, as the names and grades are now: deleted
    teams and teams of deactivated institutions or regions included, with no mark (FR-025).
    Regions, institutions within a region and teams within an institution by name in the
    Ukrainian alphabet order (milestone 12.5), ties by id (FR-026). Reads nothing else about a
    team: no member, answer or grade per question (FR-027). The maximum score is 10 for each of
    the competition's questions."""
    assert competition.id is not None and competition.stopped_at is not None
    questions = session.exec(
        select(func.count()).where(CompetitionQuestion.competition_id == competition.id)
    ).one()
    counts = grade_counts(session, competition.id)
    entries = sorted(
        team_entries(session, competition.id),
        key=lambda entry: (
            name_sort_key(entry[2].name),
            entry[2].id or 0,
            name_sort_key(entry[1].name),
            entry[1].id or 0,
            name_sort_key(entry[0].name),
            entry[0].id or 0,
        ),
    )
    regions = []
    for _, group in groupby(entries, key=lambda entry: entry[2].id):
        rows = list(group)
        lines = tuple(
            ResultLine(
                institution=institution.name,
                team=team.name,
                score=count_of(counts, team.id).score if team.id is not None else 0,
            )
            for team, institution, _ in rows
        )
        regions.append(RegionResults(name=rows[0][2].name, lines=lines))
    return ResultsSnapshot(
        competition_name=competition.name,
        subject_name=subject.name,
        starts_at=competition.starts_at,
        finished_at=competition.stopped_at,
        published_at=published_at,
        max_score=GRADE_MAX * questions,
        regions=tuple(regions),
    )


# ---------------------------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------------------------


def _refuse(session: Session, error: Exception) -> Exception:
    """`error`, after rolling back, so no lock outlives the refusal."""
    session.rollback()
    return error


def publish_results(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    status: CompetitionStatus | None,
) -> Landing:
    """Publish the results of a fully graded Finished competition, as a teacher with the
    setting: `published_at` is written once, and both results files are stored in the same
    transaction. Raises `ManageRequired`, `CompetitionNotFound`, `NotPublishable` or
    `NotFullyGraded`; nothing is stored then. If a file cannot be made, the error is raised after
    a rollback, and the competition stays Finished (FR-009).

    The competition is read `FOR UPDATE`, so a publish waits for every grade save in progress
    (they hold it `FOR SHARE`), and every later save sees it Published. The conditional update
    repeats the status check in the database, so of two publishes exactly one changes the row.

    Returns where the list filtered by `status` (the request's filter) lands, as
    `competitions.finish_competition` does: under **Finished** the competition leaves the list.
    """
    if not can_manage_competitions(session, teacher_id, lock=True):
        raise _refuse(session, ManageRequired())
    row, subject = competitions.lock_competition(session, competition_id, subject_id)
    now = competitions.utc_now()
    current = competitions.status_of(row, now)
    if current is not CompetitionStatus.FINISHED:
        raise _refuse(session, NotPublishable(current))
    progress = grading_progress(session, competition_id)
    if not progress.complete:
        raise _refuse(session, NotFullyGraded(progress))
    try:
        snapshot = build_snapshot(session, row, subject, now)
        files = {
            language: results_pdf.render_results_pdf(snapshot, language) for language in Language
        }
    except Exception:
        session.rollback()
        raise
    ids = [view.id for view in competitions.listed_views(session, subject, status, now)]
    old_index = ids.index(competition_id) if competition_id in ids else None
    result = session.execute(
        update(Competition)
        .where(
            col(Competition.id) == competition_id,
            col(Competition.stopped_at).is_not(None),
            col(Competition.cancelled_at).is_(None),
            col(Competition.published_at).is_(None),
        )
        .values(published_at=now)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotPublishable(competitions.reread_status(session, competition_id))
    for language, content in files.items():
        session.add(
            CompetitionResultsFile(
                competition_id=competition_id, language=language.value, content=content
            )
        )
    try:
        session.flush()
    except IntegrityError:
        raise _refuse(session, NotPublishable(CompetitionStatus.PUBLISHED)) from None
    after = competitions.listed_views(session, subject, status, now)
    session.commit()
    logger.info(
        "Results published: id=%d teams=%d bytes=%d",
        competition_id,
        sum(len(region.lines) for region in snapshot.regions),
        sum(len(content) for content in files.values()),
    )
    return competitions.landing(after, competition_id, old_index)


# ---------------------------------------------------------------------------------------------
# The download
# ---------------------------------------------------------------------------------------------


def results_file(session: Session, competition_id: int, language: Language) -> bytes | None:
    """The stored file of the competition in `language`, exactly as it was made at publishing;
    `None` when there is none. No status check: the caller has found a Published competition."""
    stored = session.get(CompetitionResultsFile, (competition_id, language.value))
    return stored.content if stored is not None else None


def results_file_name(name: str, starts_at: datetime) -> str:
    """ "<name> <YYYY-MM-DD>.pdf": the competition's name and its start date in Kyiv time (FR-032).
    The name is cleaned by `file_names.clean_file_stem` (an empty name becomes "results"); every
    other character, Cyrillic included, is kept."""
    return f"{clean_file_stem(name, 'results')} {starts_at.astimezone(KYIV):%Y-%m-%d}.pdf"
