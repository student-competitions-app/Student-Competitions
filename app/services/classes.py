"""Class operations: what the Students tab of the teacher area calls to list and manage classes.

See specs/009-classes-students-management/contracts/services.md §`app/services/classes.py` and
research D8. Class names follow the milestone 6 and 7 rules (`clean_name`, `name_key`), unique
within the institution ignoring case, deactivated classes included (FR-002); the year of study is
1–12 (`parse_year_of_study`). A class never moves: no function writes `institution_id` after the
insert (FR-003).

Every change starts with the teacher's reach (`app.services.teacher_access`) with Write and under
lock, in the change's own transaction (research D5), and refuses with `NotReachable` or
`WriteRequired`. The conventions of `app.services.regions` apply otherwise: values are cleaned
here, passed exactly as submitted; the unique constraint, not the lookup before a write, is the
guarantee against simultaneous submissions; one commit per successful change, and a rollback on
every refusal, so no lock outlives it.

The lookups (`list_classes`, `count_institution_classes`) check no reach: their callers do.

Each successful change logs one line with ids and counts only; a no-op logs nothing.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.models import Enrolment, SchoolClass
from app.schemas.classes import parse_year_of_study
from app.schemas.names import clean_name, name_key
from app.services.availability import sign_out_students_below
from app.services.teacher_access import reach_class, reach_institution

logger = logging.getLogger("uvicorn.error")


class DuplicateClassName(ValueError):
    """Another class of the same institution already has this name, ignoring case; `message`
    names it as stored."""

    def __init__(self, existing_name: str) -> None:
        self.existing_name = existing_name
        self.message = f"A class named “{existing_name}” already exists in this institution."
        super().__init__(self.message)


class ClassInUse(ValueError):
    """The class holds `students` students, blocked ones included, so it cannot be deleted
    (FR-006)."""

    def __init__(self, school_class: SchoolClass, students: int) -> None:
        super().__init__(f"Class {school_class.id} holds students")
        self.school_class = school_class
        self.students = students


@dataclass(frozen=True)
class ClassView:
    """A class as the teacher pages show it."""

    id: int
    institution_id: int
    name: str
    year_of_study: int
    is_active: bool

    @property
    def label(self) -> str:
        """ "KN-21 · year 2", wherever a class is listed (spec Assumptions)."""
        return f"{self.name} · year {self.year_of_study}"

    @classmethod
    def from_row(cls, row: SchoolClass) -> "ClassView":
        assert row.id is not None
        return cls(
            id=row.id,
            institution_id=row.institution_id,
            name=row.name,
            year_of_study=row.year_of_study,
            is_active=row.is_active,
        )


def list_classes(session: Session, institution_id: int) -> list[ClassView]:
    """The institution's classes, active and deactivated, sorted ignoring case, ties by id.
    Sorted in Python, as everywhere else."""
    statement = select(SchoolClass).where(SchoolClass.institution_id == institution_id)
    rows = sorted(session.exec(statement), key=lambda row: (row.name_key, row.id))
    return [ClassView.from_row(row) for row in rows]


def count_institution_classes(session: Session, institution_id: int) -> int:
    """How many classes the institution holds, active and deactivated: for the administrator's
    delete confirmation (research D14)."""
    statement = (
        select(func.count())
        .select_from(SchoolClass)
        .where(col(SchoolClass.institution_id) == institution_id)
    )
    return session.exec(statement).one()


def _find_in_institution(session: Session, institution_id: int, key: str) -> SchoolClass | None:
    statement = select(SchoolClass).where(
        SchoolClass.institution_id == institution_id, SchoolClass.name_key == key
    )
    return session.exec(statement).first()


def _duplicate_after_conflict(
    session: Session, institution_id: int, key: str, fallback: str
) -> DuplicateClassName:
    """Roll back a commit the unique constraint refused, and name the class that won."""
    session.rollback()
    winner = _find_in_institution(session, institution_id, key)
    return DuplicateClassName(winner.name if winner is not None else fallback)


def _cleaned(session: Session, raw_name: str, raw_year: str) -> tuple[str, str, int]:
    """The cleaned name, its key and the year; on a refusal, roll back first (the reach check
    holds locks) and re-raise `InvalidName` or `InvalidYear`."""
    try:
        name = clean_name(raw_name)
        year = parse_year_of_study(raw_year)
    except ValueError:
        session.rollback()
        raise
    return name, name_key(name), year


def create_class(
    session: Session, teacher_id: int, institution_id: int, raw_name: str, raw_year: str
) -> ClassView:
    """Store a new, active class in the institution, which the teacher must reach with Write
    (FR-004). The link, institution and region rows are read `FOR SHARE` (research D5), so the
    institution cannot be deactivated or deleted, nor the level lowered, until the insert
    commits. Raises `NotReachable`, `WriteRequired`, `InvalidName`, `InvalidYear` or
    `DuplicateClassName`; nothing is stored then."""
    reach_institution(session, teacher_id, institution_id, write=True, lock=True)
    name, key, year = _cleaned(session, raw_name, raw_year)
    existing = _find_in_institution(session, institution_id, key)
    if existing is not None:
        session.rollback()
        raise DuplicateClassName(existing.name)
    now = utc_now()
    school_class = SchoolClass(
        institution_id=institution_id,
        name=name,
        name_key=key,
        year_of_study=year,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(school_class)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, institution_id, key, name) from None
    session.refresh(school_class)
    logger.info("Class created: id=%d institution_id=%d", school_class.id, institution_id)
    return ClassView.from_row(school_class)


def update_class(
    session: Session, teacher_id: int, class_id: int, raw_name: str, raw_year: str
) -> ClassView:
    """Change the class's name and year of study, keeping its status and its institution. The
    class itself never counts as a duplicate, so a change of case is a valid rename (FR-002); an
    unchanged form writes nothing. The year is read from the class, so every student's year
    changes with it (spec Edge Cases)."""
    _, school_class = reach_class(session, teacher_id, class_id, write=True, lock=True)
    name, key, year = _cleaned(session, raw_name, raw_year)
    existing = _find_in_institution(session, school_class.institution_id, key)
    if existing is not None and existing.id != school_class.id:
        session.rollback()
        raise DuplicateClassName(existing.name)
    if (school_class.name, school_class.name_key, school_class.year_of_study) == (name, key, year):
        view = ClassView.from_row(school_class)
        session.rollback()
        return view
    school_class.name = name
    school_class.name_key = key
    school_class.year_of_study = year
    school_class.updated_at = utc_now()
    session.add(school_class)
    institution_id = school_class.institution_id
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, institution_id, key, name) from None
    session.refresh(school_class)
    logger.info("Class updated: id=%d institution_id=%d", class_id, institution_id)
    return ClassView.from_row(school_class)


def set_class_active(session: Session, teacher_id: int, class_id: int, active: bool) -> ClassView:
    """Activate or deactivate the class; already in that status, nothing changes. Deactivating
    signs out every student of the class in the same transaction (FR-015, research D4); the
    enrolments themselves never change (FR-017)."""
    _, school_class = reach_class(session, teacher_id, class_id, write=True, lock=True)
    if school_class.is_active == active:
        view = ClassView.from_row(school_class)
        session.rollback()
        return view
    school_class.is_active = active
    school_class.updated_at = utc_now()
    session.add(school_class)
    signed_out = 0 if active else sign_out_students_below(session, class_id=class_id)
    session.commit()
    session.refresh(school_class)
    if active:
        logger.info("Class activated: id=%d", class_id)
    else:
        logger.info("Class deactivated: id=%d sessions=%d", class_id, signed_out)
    return ClassView.from_row(school_class)


def _count_students(session: Session, class_id: int) -> int:
    statement = (
        select(func.count()).select_from(Enrolment).where(col(Enrolment.class_id) == class_id)
    )
    return session.exec(statement).one()


def delete_class(session: Session, teacher_id: int, class_id: int) -> None:
    """Delete the class permanently, freeing its name in the institution; refused with
    `ClassInUse` while it holds any student, blocked ones included (FR-006).

    The class row is locked `FOR UPDATE` before the count, so an acceptance into it either
    commits first and is counted, or waits and then finds the class gone (FR-035). On PostgreSQL
    the foreign key from `enrolments` is the backstop: an `IntegrityError` is reported as
    `ClassInUse` too.
    """
    _, school_class = reach_class(session, teacher_id, class_id, write=True, lock=True)
    students = _count_students(session, class_id)
    if students > 0:
        session.rollback()
        raise ClassInUse(school_class, students)
    institution_id = school_class.institution_id
    session.delete(school_class)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        remaining = session.get(SchoolClass, class_id)
        assert remaining is not None
        raise ClassInUse(remaining, _count_students(session, class_id) or 1) from None
    logger.info("Class deleted: id=%d institution_id=%d", class_id, institution_id)
