"""Subject operations: what the `/admin/subjects` routes call, and milestones 9 and 10 build on.

See specs/006-admin-area/contracts/subject-service.md and research D3–D4. These functions enforce
no authorization: every route that calls them is `@allow_roles(Role.ADMIN)`, and a later caller
must put its own role check in front.

Every function takes an open session as its first argument; the caller owns the session. Each
write is one committed unit of work, rolled back on error. Names are cleaned here with
`clean_subject_name`, so callers pass the value exactly as submitted. The unique constraint on
`name_key`, not the lookup before an insert, is the guarantee against simultaneous submissions.

Each successful change logs one line with the subject id only; a no-op logs nothing.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import utc_now
from app.models import Subject
from app.schemas.subject import clean_subject_name, subject_name_key

logger = logging.getLogger("uvicorn.error")


class SubjectNotFound(LookupError):
    """No subject has this id. Raised instead of returning `None`."""

    def __init__(self, subject_id: int) -> None:
        super().__init__(f"Subject {subject_id} not found")
        self.subject_id = subject_id


class DuplicateSubjectName(ValueError):
    """Another subject already has this name, ignoring case; `message` names it as stored."""

    def __init__(self, existing_name: str) -> None:
        self.existing_name = existing_name
        self.message = f"A subject named “{existing_name}” already exists."
        super().__init__(self.message)


class SubjectInUse(ValueError):
    """The subject is referred to `uses` times, so it cannot be deleted (FR-029)."""

    def __init__(self, subject: Subject, uses: int) -> None:
        super().__init__(f"Subject {subject.id} is in use")
        self.subject = subject
        self.uses = uses


def list_subjects(session: Session) -> list[Subject]:
    """All subjects, active and inactive, sorted ignoring case, ties by id.

    Sorted in Python on `name_key` rather than with `ORDER BY`, which follows each engine's
    collation: this way SQLite and PostgreSQL give the same order (research D3).
    """
    subjects = session.exec(select(Subject)).all()
    return sorted(subjects, key=lambda subject: (subject.name_key, subject.id))


def get_subject(session: Session, subject_id: int) -> Subject:
    """The stored subject."""
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise SubjectNotFound(subject_id)
    return subject


def _find_by_key(session: Session, name_key: str) -> Subject | None:
    return session.exec(select(Subject).where(Subject.name_key == name_key)).first()


def _duplicate_after_conflict(
    session: Session, name_key: str, fallback: str
) -> DuplicateSubjectName:
    """Roll back a commit the unique constraint refused, and name the subject that won."""
    session.rollback()
    winner = _find_by_key(session, name_key)
    return DuplicateSubjectName(winner.name if winner is not None else fallback)


def create_subject(session: Session, raw_name: str) -> Subject:
    """Store a new, active subject named `raw_name` (cleaned) and return it with its new id."""
    name = clean_subject_name(raw_name)
    key = subject_name_key(name)
    existing = _find_by_key(session, key)
    if existing is not None:
        raise DuplicateSubjectName(existing.name)
    now = utc_now()
    subject = Subject(name=name, name_key=key, is_active=True, created_at=now, updated_at=now)
    session.add(subject)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, key, name) from None
    session.refresh(subject)
    logger.info("Subject created: id=%d", subject.id)
    return subject


def rename_subject(session: Session, subject_id: int, raw_name: str) -> Subject:
    """Rename the subject, keeping its status. The subject itself never counts as a duplicate, so
    a change of case is allowed; an unchanged name writes nothing."""
    subject = get_subject(session, subject_id)
    name = clean_subject_name(raw_name)
    key = subject_name_key(name)
    existing = _find_by_key(session, key)
    if existing is not None and existing.id != subject.id:
        raise DuplicateSubjectName(existing.name)
    if subject.name == name and subject.name_key == key:
        return subject
    subject.name = name
    subject.name_key = key
    subject.updated_at = utc_now()
    session.add(subject)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, key, name) from None
    session.refresh(subject)
    logger.info("Subject renamed: id=%d", subject.id)
    return subject


def set_subject_active(session: Session, subject_id: int, active: bool) -> Subject:
    """Activate or deactivate the subject. Already in that status: nothing changes (FR-026)."""
    subject = get_subject(session, subject_id)
    if subject.is_active == active:
        return subject
    subject.is_active = active
    subject.updated_at = utc_now()
    session.add(subject)
    session.commit()
    session.refresh(subject)
    logger.info("Subject %s: id=%d", "activated" if active else "deactivated", subject.id)
    return subject


def count_subject_uses(session: Session, subject_id: int) -> int:
    """How many records refer to the subject. Nothing does yet, so this is `0` (research D4).

    Milestone 9 (questions) and milestone 10 (competitions) each add their count here when they
    add a `subject_id` reference. Do not rely on the foreign key alone: SQLite does not enforce
    foreign keys in this application, so without a count here a subject in use could be deleted.
    """
    return 0


def delete_subject(session: Session, subject_id: int) -> None:
    """Delete the subject permanently, freeing its name; refused while anything refers to it."""
    subject = get_subject(session, subject_id)
    uses = count_subject_uses(session, subject_id)
    if uses > 0:
        raise SubjectInUse(subject, uses)
    session.delete(subject)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise SubjectInUse(get_subject(session, subject_id), 1) from None
    logger.info("Subject deleted: id=%d", subject_id)
