"""Educational institution operations: what the `/admin/institutions` routes call, and milestones
8 and 9 build on.

See specs/007-institutions/contracts/institution-service.md and research D4–D6. These functions
enforce no authorization: every route that calls them is `@allow_roles(Role.ADMIN)`, and a later
caller must put its own role check in front.

Every function takes an open session as its first argument; the caller owns the session. Each
write is one committed unit of work, rolled back on error. Names are cleaned here with
`clean_institution_name`, so callers pass the value exactly as submitted. The unique constraint on
`name_key`, not the lookup before an insert, is the guarantee against simultaneous submissions.

There is no "active institutions only" query yet: nothing offers institutions for a link until
milestone 8, which adds the one its forms need (research D6).

Each successful change logs one line with the institution id only; a no-op logs nothing.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import utc_now
from app.models import Institution
from app.schemas.institution import clean_institution_name, institution_name_key

logger = logging.getLogger("uvicorn.error")


class InstitutionNotFound(LookupError):
    """No institution has this id. Raised instead of returning `None`."""

    def __init__(self, institution_id: int) -> None:
        super().__init__(f"Institution {institution_id} not found")
        self.institution_id = institution_id


class DuplicateInstitutionName(ValueError):
    """Another institution already has this name, ignoring case; `message` names it as stored."""

    def __init__(self, existing_name: str) -> None:
        self.existing_name = existing_name
        self.message = f"An educational institution named “{existing_name}” already exists."
        super().__init__(self.message)


class InstitutionInUse(ValueError):
    """The institution is referred to `uses` times, so it cannot be deleted (FR-024)."""

    def __init__(self, institution: Institution, uses: int) -> None:
        super().__init__(f"Institution {institution.id} is in use")
        self.institution = institution
        self.uses = uses


def list_institutions(session: Session) -> list[Institution]:
    """All institutions, active and inactive, sorted ignoring case, ties by id.

    Sorted in Python on `name_key` rather than with `ORDER BY`, which follows each engine's
    collation: this way SQLite and PostgreSQL give the same order.
    """
    institutions = session.exec(select(Institution)).all()
    return sorted(institutions, key=lambda institution: (institution.name_key, institution.id))


def get_institution(session: Session, institution_id: int) -> Institution:
    """The stored institution."""
    institution = session.get(Institution, institution_id)
    if institution is None:
        raise InstitutionNotFound(institution_id)
    return institution


def _find_by_key(session: Session, name_key: str) -> Institution | None:
    return session.exec(select(Institution).where(Institution.name_key == name_key)).first()


def _duplicate_after_conflict(
    session: Session, name_key: str, fallback: str
) -> DuplicateInstitutionName:
    """Roll back a commit the unique constraint refused, and name the institution that won."""
    session.rollback()
    winner = _find_by_key(session, name_key)
    return DuplicateInstitutionName(winner.name if winner is not None else fallback)


def create_institution(session: Session, raw_name: str) -> Institution:
    """Store a new, active institution named `raw_name` (cleaned) and return it with its new id."""
    name = clean_institution_name(raw_name)
    key = institution_name_key(name)
    existing = _find_by_key(session, key)
    if existing is not None:
        raise DuplicateInstitutionName(existing.name)
    now = utc_now()
    institution = Institution(
        name=name, name_key=key, is_active=True, created_at=now, updated_at=now
    )
    session.add(institution)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, key, name) from None
    session.refresh(institution)
    logger.info("Institution created: id=%d", institution.id)
    return institution


def rename_institution(session: Session, institution_id: int, raw_name: str) -> Institution:
    """Rename the institution, keeping its id and status. The institution itself never counts as
    a duplicate, so a change of case is allowed; an unchanged name writes nothing."""
    institution = get_institution(session, institution_id)
    name = clean_institution_name(raw_name)
    key = institution_name_key(name)
    existing = _find_by_key(session, key)
    if existing is not None and existing.id != institution.id:
        raise DuplicateInstitutionName(existing.name)
    if institution.name == name and institution.name_key == key:
        return institution
    institution.name = name
    institution.name_key = key
    institution.updated_at = utc_now()
    session.add(institution)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, key, name) from None
    session.refresh(institution)
    logger.info("Institution renamed: id=%d", institution.id)
    return institution


def set_institution_active(session: Session, institution_id: int, active: bool) -> Institution:
    """Activate or deactivate the institution. Already in that status: nothing changes (FR-021)."""
    institution = get_institution(session, institution_id)
    if institution.is_active == active:
        return institution
    institution.is_active = active
    institution.updated_at = utc_now()
    session.add(institution)
    session.commit()
    session.refresh(institution)
    logger.info("Institution %s: id=%d", "activated" if active else "deactivated", institution.id)
    return institution


def count_institution_uses(session: Session, institution_id: int) -> int:
    """How many records refer to the institution. Nothing does yet, so this is `0` (research D5).

    Milestone 8 (teacher links) and milestone 9 (student details) each add their count here when
    they add an `institution_id` reference. Do not rely on the foreign key alone: SQLite does not
    enforce foreign keys in this application, so without a count here an institution in use could
    be deleted.
    """
    return 0


def delete_institution(session: Session, institution_id: int) -> None:
    """Delete the institution permanently, freeing its name; refused while anything refers to it."""
    institution = get_institution(session, institution_id)
    uses = count_institution_uses(session, institution_id)
    if uses > 0:
        raise InstitutionInUse(institution, uses)
    session.delete(institution)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise InstitutionInUse(get_institution(session, institution_id), 1) from None
    logger.info("Institution deleted: id=%d", institution_id)
