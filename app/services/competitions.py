"""Competitions: the subjects offered on the Competitions tab, one page of a subject's
competitions, and creating, editing, cancelling and finishing them.

See specs/012.1-teacher-competitions/contracts/services.md §`app/services/competitions.py` and
research R2, R3, R7, R8, R11, R13; finishing is specs/012.4-finish-and-grade/contracts/services.md
§`competitions` and research R1. Every teacher reads every competition; reading needs only the
teacher role, which the routes check.

- **The status is derived, never stored** (`status_of`): Cancelled, Finished, Upcoming before the
  start, In progress from it. **The clock** is this module's `utc_now`, read once per call and used
  for every row that call derives, so tests replace it with
  `monkeypatch.setattr("app.services.competitions.utc_now", …)` and nothing ever waits.
- **Visibility**: every competition of an active subject; only the finished ones of a deactivated
  subject. An invisible competition is `CompetitionNotFound`, exactly like an unknown one, or one
  of another subject. The subjects offered are the active ones and the deactivated ones with a
  finished competition.
- **Every write checks the setting itself**: **Can manage competitions**, read through
  `teacher_access.can_manage_competitions` with `lock=True` inside the write's own transaction.
  Then the subject is read `FOR SHARE` and, for an edit, a cancellation or a finish, the
  competition `FOR UPDATE`, both refreshed; the status is derived with a fresh clock. The change
  itself is a conditional `UPDATE` whose row count tells a lost race, so "already cancelled" and
  "has already started" hold on both engines (on SQLite the locks render nothing). Each refusal
  rolls back before it raises, so no lock outlives it.
- **Names** follow the subject-name rules (`clean_name`, `name_key`) and are unique among the live
  competitions of a subject, ignoring case; the partial unique index
  `uq_competitions_subject_name_live`, not the lookup before a write, is the guarantee.

Every function takes an open session first; the caller owns it. Each successful change logs one
line with ids only, never a name; a no-op and a refusal log nothing (FR-046).

**Contract for later milestones**: stopping is `finish_competition` (milestone 12.4), which
writes `stopped_at` once with a conditional update on `cancelled_at IS NULL AND stopped_at IS NULL
AND starts_at <= :now`; the questions and teams of a competition may change only while `status_of`
is Upcoming, under the competition's lock (`lock_competition`), which
`app.services.competition_entries` (milestone 12.2) is the first to use; a team's answers are
entered only while it is In progress, under the competition's share lock
(`lock_competition(share=True)`, `app.services.team_answers`, milestone 12.3), and students
(milestone 13) may answer only so too, while it is visible; answers are graded only once it is
Finished, under the same share lock (`app.services.grades`, milestone 12.4).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ColumnElement, exists, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.models import Competition, Subject
from app.schemas.names import InvalidName, clean_name, name_key
from app.services.paging import Paging, landing_index
from app.services.subjects import list_active_subjects
from app.services.teacher_access import can_manage_competitions

logger = logging.getLogger("uvicorn.error")


class CompetitionStatus(StrEnum):
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        """The one word shown for the status, everywhere."""
        return _LABELS[self]


_LABELS = {
    CompetitionStatus.UPCOMING: "Upcoming",
    CompetitionStatus.IN_PROGRESS: "In progress",
    CompetitionStatus.FINISHED: "Finished",
    CompetitionStatus.CANCELLED: "Cancelled",
}


def parse_status_filter(raw: str | None) -> CompetitionStatus | None:
    """A status from the address, exactly as written; anything else is `None`, meaning All."""
    if raw is None:
        return None
    try:
        return CompetitionStatus(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------------------------


class ManageRequired(PermissionError):
    """The teacher lacks **Can manage competitions** (403)."""


class SubjectUnavailable(LookupError):
    """The subject is unknown, or not active where a new competition is made (404)."""


class CompetitionNotFound(LookupError):
    """Unknown, of another subject, or invisible: "Competition not found" (404). Never says
    which."""


class NotEditable(ValueError):
    """The competition is not Upcoming (409)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(f"Not editable: {status}")
        self.status = status


class NotCancellable(ValueError):
    """The competition is already Cancelled, or Finished (409)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(f"Not cancellable: {status}")
        self.status = status


class NotFinishable(ValueError):
    """The competition is not In progress: Upcoming, Cancelled or already Finished (409)."""

    def __init__(self, status: CompetitionStatus) -> None:
        super().__init__(f"Not finishable: {status}")
        self.status = status


class StartNotInFuture(ValueError):
    """The start is not later than the moment of saving (400)."""


class DuplicateCompetitionName(ValueError):
    """A live competition of the subject already has this name, ignoring case. `message` repeats
    the name as entered (after trimming)."""

    def __init__(self, entered_name: str) -> None:
        self.message = f"A competition named “{entered_name}” already exists in this subject."
        super().__init__(self.message)


# ---------------------------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CompetitionView:
    id: int
    subject_id: int
    name: str
    starts_at: datetime
    """UTC."""
    status: CompetitionStatus
    name_key: str
    """For the order only; never shown."""


@dataclass(frozen=True)
class CompetitionPage:
    competitions: list[CompetitionView]
    """One page, latest start first."""
    paging: Paging
    subject_total: int
    """The subject's visible competitions, in any status: none means "No competitions yet"."""


@dataclass(frozen=True)
class SubjectChoices:
    """The subjects offered on the tab."""

    active: list[Subject]
    """Sorted by name ignoring case, then id."""
    deactivated: list[Subject]
    """Deactivated subjects with at least one finished competition; the same order."""

    def get(self, subject_id: int) -> Subject | None:
        for subject in (*self.active, *self.deactivated):
            if subject.id == subject_id:
                return subject
        return None

    def is_offered(self, subject_id: int) -> bool:
        return self.get(subject_id) is not None

    @property
    def only(self) -> Subject | None:
        """The single offered subject, if exactly one is offered."""
        offered = [*self.active, *self.deactivated]
        return offered[0] if len(offered) == 1 else None


@dataclass(frozen=True)
class Landing:
    """Where the list lands after a change (R13)."""

    page: int
    competition_id: int | None
    """The competition to show at its anchor; `None` for the empty state."""


# ---------------------------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------------------------


def status_of(row: Competition, now: datetime) -> CompetitionStatus:
    """The competition's status at `now`: a cancelled one stays Cancelled after its start, and at
    the start minute itself it is In progress (R2)."""
    if row.cancelled_at is not None:
        return CompetitionStatus.CANCELLED
    if row.stopped_at is not None:
        return CompetitionStatus.FINISHED
    if row.starts_at > now:
        return CompetitionStatus.UPCOMING
    return CompetitionStatus.IN_PROGRESS


def sort_key(view: CompetitionView) -> tuple[float, str, int]:
    """Latest start first, whatever the status; equal starts by name ignoring case, then id
    (FR-014). Sorted in Python, so both engines agree."""
    return (-view.starts_at.timestamp(), view.name_key, view.id)


def landing(rows: Sequence[CompetitionView], competition_id: int, old_index: int | None) -> Landing:
    """The landing on `rows`, the sorted list after a change: the competition itself if listed;
    else the row that took its place (`old_index`), else the row before it; else the empty state
    (R13). The page is `index // PAGE_SIZE + 1`, so a page that empties leads to the previous
    one (`paging.landing_index`)."""
    return Landing(*landing_index([row.id for row in rows], competition_id, old_index))


def _view(row: Competition, now: datetime) -> CompetitionView:
    assert row.id is not None
    return CompetitionView(
        id=row.id,
        subject_id=row.subject_id,
        name=row.name,
        starts_at=row.starts_at,
        status=status_of(row, now),
        name_key=row.name_key,
    )


def _refuse(session: Session, lock: bool, error: Exception) -> Exception:
    """`error`, after rolling back when a lock was taken, so no lock outlives the refusal."""
    if lock:
        session.rollback()
    return error


def _is_visible(row: Competition, subject: Subject) -> bool:
    """A competition of an active subject, or a finished one (R11)."""
    return subject.is_active or row.stopped_at is not None


def _visible(subject: Subject) -> tuple[ColumnElement[bool], ...]:
    """The conditions for the subject's visible competitions."""
    conditions: tuple[ColumnElement[bool], ...] = (Competition.subject_id == subject.id,)
    if not subject.is_active:
        conditions += (col(Competition.stopped_at).is_not(None),)
    return conditions


# ---------------------------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------------------------


def offered_subjects(session: Session) -> SubjectChoices:
    """The active subjects, and the deactivated subjects with at least one finished competition
    (FR-010, FR-037), each sorted by name ignoring case, then id."""
    finished = exists().where(
        Competition.subject_id == Subject.id, col(Competition.stopped_at).is_not(None)
    )
    deactivated = session.exec(select(Subject).where(~col(Subject.is_active), finished)).all()
    return SubjectChoices(
        active=list_active_subjects(session),
        deactivated=sorted(deactivated, key=lambda subject: (subject.name_key, subject.id)),
    )


def _listed(
    session: Session, subject: Subject, status: CompetitionStatus | None, now: datetime
) -> tuple[list[CompetitionView], int]:
    """The subject's visible competitions matching `status` (All for `None`), sorted, and the
    number of visible competitions in any status."""
    rows = session.exec(select(Competition).where(*_visible(subject))).all()
    views = [_view(row, now) for row in rows]
    matching = [view for view in views if status is None or view.status is status]
    return sorted(matching, key=sort_key), len(views)


def competition_page(
    session: Session, subject: Subject, status: CompetitionStatus | None, page: int
) -> CompetitionPage:
    """One page of the subject's visible competitions matching `status`, the page clamped to
    1..last. The caller has already checked that the subject is offered."""
    listed, total = _listed(session, subject, status, utc_now())
    paging = Paging.build(page, len(listed))
    return CompetitionPage(listed[paging.offset : paging.offset + paging.size], paging, total)


def _find(
    session: Session, competition_id: int, subject_id: int, *, lock: bool, share: bool = False
) -> tuple[Competition, Subject]:
    """The competition and its subject, if the competition belongs to `subject_id` and is
    visible; `CompetitionNotFound` otherwise. With `lock`, the competition is read `FOR UPDATE`
    (`FOR SHARE` with `share`), then the subject `FOR SHARE`, both refreshed."""
    if lock:
        row = session.get(
            Competition,
            competition_id,
            with_for_update={"read": True} if share else True,
            populate_existing=True,
        )
    else:
        row = session.get(Competition, competition_id)
    if row is None or row.subject_id != subject_id:
        raise _refuse(session, lock, CompetitionNotFound())
    if lock:
        subject = session.get(
            Subject, subject_id, with_for_update={"read": True}, populate_existing=True
        )
    else:
        subject = session.get(Subject, subject_id)
    if subject is None or not _is_visible(row, subject):
        raise _refuse(session, lock, CompetitionNotFound())
    return row, subject


def lock_competition(
    session: Session, competition_id: int, subject_id: int, *, share: bool = False
) -> tuple[Competition, Subject]:
    """The competition `FOR UPDATE`, then its subject `FOR SHARE`, both refreshed, if the
    competition belongs to `subject_id` and is visible; `CompetitionNotFound`, after a rollback,
    otherwise. The first step of every change to a competition or to its questions and teams,
    so a change and a cancellation never interleave.

    With `share` (milestone 12.3 research R3), the competition is read `FOR SHARE` instead: a
    save of a team's answers takes it so, so the saves of one competition do not wait for each
    other, while cancelling and stopping, which take it `FOR UPDATE`, still wait for every save
    in progress, and every save waits for them."""
    return _find(session, competition_id, subject_id, lock=True, share=share)


def get_competition(session: Session, competition_id: int, subject_id: int) -> CompetitionView:
    """The competition, with its status now, if it belongs to `subject_id` and is visible;
    `CompetitionNotFound` otherwise."""
    row, _ = _find(session, competition_id, subject_id, lock=False)
    return _view(row, utc_now())


def subject_id_of(session: Session, competition_id: int) -> int | None:
    """The competition's subject id, or `None` for an unknown id. Only for the fallback of an
    address that names no subject (milestone 12.2 spec Edge Cases): the caller then checks the
    subject and the competition as usual."""
    row = session.get(Competition, competition_id)
    return row.subject_id if row is not None else None


def locate(
    session: Session,
    subject: Subject,
    status: CompetitionStatus | None,
    competition_id: int,
    old_index: int | None = None,
) -> Landing:
    """The landing on the subject's list filtered by `status`, after a change (R13)."""
    listed, _ = _listed(session, subject, status, utc_now())
    return landing(listed, competition_id, old_index)


# ---------------------------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------------------------


def _require_manage(session: Session, teacher_id: int) -> None:
    if not can_manage_competitions(session, teacher_id, lock=True):
        raise _refuse(session, True, ManageRequired())


def _cleaned(session: Session, raw_name: str) -> tuple[str, str]:
    """The cleaned name and its key; on a refusal, roll back first and re-raise
    `InvalidName`."""
    try:
        name = clean_name(raw_name)
    except InvalidName:
        session.rollback()
        raise
    return name, name_key(name)


def _find_live(session: Session, subject_id: int, key: str) -> Competition | None:
    """The live competition of the subject with this name key."""
    statement = select(Competition).where(
        Competition.subject_id == subject_id,
        Competition.name_key == key,
        col(Competition.cancelled_at).is_(None),
        col(Competition.stopped_at).is_(None),
    )
    return session.exec(statement).first()


def _reread_status(session: Session, competition_id: int) -> CompetitionStatus:
    """After a conditional update that matched no row: roll back, and the row's status now."""
    session.rollback()
    row = session.get(Competition, competition_id, populate_existing=True)
    assert row is not None
    status = status_of(row, utc_now())
    session.rollback()
    return status


def create_competition(
    session: Session, teacher_id: int, subject_id: int, raw_name: str, starts_at: datetime
) -> CompetitionView:
    """Add a competition to an active subject, as a teacher with the setting. `starts_at` is UTC
    and must be later than now. Raises `ManageRequired`, `SubjectUnavailable`,
    `StartNotInFuture`, `InvalidName` or `DuplicateCompetitionName`; nothing is stored then."""
    _require_manage(session, teacher_id)
    subject = session.get(
        Subject, subject_id, with_for_update={"read": True}, populate_existing=True
    )
    if subject is None or not subject.is_active:
        raise _refuse(session, True, SubjectUnavailable())
    now = utc_now()
    if starts_at <= now:
        raise _refuse(session, True, StartNotInFuture())
    name, key = _cleaned(session, raw_name)
    if _find_live(session, subject_id, key) is not None:
        raise _refuse(session, True, DuplicateCompetitionName(name))
    competition = Competition(
        subject_id=subject_id,
        name=name,
        name_key=key,
        starts_at=starts_at,
        created_at=now,
        updated_at=now,
    )
    session.add(competition)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateCompetitionName(name) from None
    session.refresh(competition)
    logger.info("Competition created: id=%d subject=%d", competition.id, subject_id)
    return _view(competition, now)


def update_competition(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    raw_name: str,
    starts_at: datetime,
) -> CompetitionView:
    """Replace the name and the start of an upcoming competition, as a teacher with the setting.
    The competition itself never counts as a duplicate, so a change of case is valid; an
    unchanged save writes nothing. Raises `ManageRequired`, `CompetitionNotFound`,
    `NotEditable`, `StartNotInFuture`, `InvalidName` or `DuplicateCompetitionName`; nothing
    changes then."""
    _require_manage(session, teacher_id)
    row, _ = lock_competition(session, competition_id, subject_id)
    now = utc_now()
    status = status_of(row, now)
    if status is not CompetitionStatus.UPCOMING:
        raise _refuse(session, True, NotEditable(status))
    if starts_at <= now:
        raise _refuse(session, True, StartNotInFuture())
    name, key = _cleaned(session, raw_name)
    existing = _find_live(session, subject_id, key)
    if existing is not None and existing.id != competition_id:
        raise _refuse(session, True, DuplicateCompetitionName(name))
    if (row.name, row.name_key, row.starts_at) == (name, key, starts_at):
        view = _view(row, now)
        session.rollback()
        return view
    result = session.execute(
        update(Competition)
        .where(
            col(Competition.id) == competition_id,
            col(Competition.cancelled_at).is_(None),
            col(Competition.stopped_at).is_(None),
            col(Competition.starts_at) > now,
        )
        .values(name=name, name_key=key, starts_at=starts_at, updated_at=now)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotEditable(_reread_status(session, competition_id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateCompetitionName(name) from None
    logger.info("Competition updated: id=%d", competition_id)
    row = session.get(Competition, competition_id, populate_existing=True)
    assert row is not None
    return _view(row, now)


def cancel_competition(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    status: CompetitionStatus | None,
) -> Landing:
    """Cancel an upcoming or in-progress competition, as a teacher with the setting: only
    `cancelled_at` is written, and never again. Raises `ManageRequired`, `CompetitionNotFound` or
    `NotCancellable`; nothing changes then.

    Returns where the list filtered by `status` (the request's filter) lands (R13): with `i` the
    competition's index in that list before the change, the competition itself if the filter
    still shows it; else the row now at `i`, else the one before it, else the empty state.
    """
    _require_manage(session, teacher_id)
    row, subject = lock_competition(session, competition_id, subject_id)
    now = utc_now()
    current = status_of(row, now)
    if current in (CompetitionStatus.CANCELLED, CompetitionStatus.FINISHED):
        raise _refuse(session, True, NotCancellable(current))
    before, _ = _listed(session, subject, status, now)
    ids = [view.id for view in before]
    old_index = ids.index(competition_id) if competition_id in ids else None
    result = session.execute(
        update(Competition)
        .where(
            col(Competition.id) == competition_id,
            col(Competition.cancelled_at).is_(None),
            col(Competition.stopped_at).is_(None),
        )
        .values(cancelled_at=now)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotCancellable(_reread_status(session, competition_id))
    after, _ = _listed(session, subject, status, now)
    session.commit()
    logger.info("Competition cancelled: id=%d", competition_id)
    return landing(after, competition_id, old_index)


def finish_competition(
    session: Session,
    teacher_id: int,
    competition_id: int,
    subject_id: int,
    status: CompetitionStatus | None,
) -> Landing:
    """Finish an in-progress competition, as a teacher with the setting: only `stopped_at` is
    written, and never again. Raises `ManageRequired`, `CompetitionNotFound` or `NotFinishable`;
    nothing changes then.

    The competition is read `FOR UPDATE`, so a finish waits for every answer save in progress
    (they hold it `FOR SHARE`), and every later save sees it Finished (milestone 12.4 research
    R1). The conditional update repeats the status check in the database, so of two finishes, or a
    finish and a cancel, exactly one changes the row.

    Returns where the list filtered by `status` (the request's filter) lands, as
    `cancel_competition` does (R13).
    """
    _require_manage(session, teacher_id)
    row, subject = lock_competition(session, competition_id, subject_id)
    now = utc_now()
    current = status_of(row, now)
    if current is not CompetitionStatus.IN_PROGRESS:
        raise _refuse(session, True, NotFinishable(current))
    before, _ = _listed(session, subject, status, now)
    ids = [view.id for view in before]
    old_index = ids.index(competition_id) if competition_id in ids else None
    result = session.execute(
        update(Competition)
        .where(
            col(Competition.id) == competition_id,
            col(Competition.cancelled_at).is_(None),
            col(Competition.stopped_at).is_(None),
            col(Competition.starts_at) <= now,
        )
        .values(stopped_at=now)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotFinishable(_reread_status(session, competition_id))
    after, _ = _listed(session, subject, status, now)
    session.commit()
    logger.info("Competition finished: id=%d", competition_id)
    return landing(after, competition_id, old_index)
