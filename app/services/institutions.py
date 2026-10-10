"""Institution operations: what the `/admin/institutions` routes call for the right-hand list,
and milestones 8 and 9 build on.

See specs/007-region-and-institutions-management/contracts/institution-service.md and research
D3–D5, D7, D9. These functions enforce no authorization: every route that calls them is
`@allow_roles(Role.ADMIN)`, and a later caller must put its own role check in front.

The conventions of `app.services.regions` apply. In addition, every function that names an
institution also names its region, and an institution of another region is treated exactly as a
missing one. No function writes `region_id` after the insert, so an institution can never move
(FR-030). The order of checks is: region exists, institution exists, region active (create only),
name valid, name unique.

Each successful change logs one line with the institution and region ids only; a no-op logs
nothing.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import utc_now
from app.models import Institution, Region
from app.schemas.names import clean_name, name_key
from app.services.regions import RegionNotFound, get_region

logger = logging.getLogger("uvicorn.error")


class InstitutionNotFound(LookupError):
    """No institution has this id in this region. Raised instead of returning `None`."""

    def __init__(self, region_id: int, institution_id: int) -> None:
        super().__init__(f"Institution {institution_id} not found in region {region_id}")
        self.region_id = region_id
        self.institution_id = institution_id


class DuplicateInstitutionName(ValueError):
    """Another institution of the same region already has this name, ignoring case; `message`
    names it as stored."""

    def __init__(self, existing_name: str) -> None:
        self.existing_name = existing_name
        self.message = (
            f"An educational institution named “{existing_name}” already exists in this region."
        )
        super().__init__(self.message)


class RegionInactive(ValueError):
    """The region is deactivated, so no institution can be added to it (FR-024)."""

    def __init__(self, region: Region) -> None:
        super().__init__(f"Region {region.id} is deactivated")
        self.region = region


class InstitutionInUse(ValueError):
    """The institution is referred to `uses` times, so it cannot be deleted (FR-037)."""

    def __init__(self, institution: Institution, uses: int) -> None:
        super().__init__(f"Institution {institution.id} is in use")
        self.institution = institution
        self.uses = uses


def list_institutions(session: Session, region_id: int) -> list[Institution]:
    """The region's institutions only, active and deactivated, sorted ignoring case, ties by id.

    Sorted in Python, as regions are (research D6). The caller has already loaded the region, so
    this does not check that it exists.
    """
    statement = select(Institution).where(Institution.region_id == region_id)
    institutions = session.exec(statement).all()
    return sorted(institutions, key=lambda institution: (institution.name_key, institution.id))


def get_institution(session: Session, region_id: int, institution_id: int) -> Institution:
    """The stored institution of this region. The region is looked up first, so a missing region
    is reported as such even when the institution is missing too."""
    get_region(session, region_id)
    institution = session.get(Institution, institution_id)
    if institution is None or institution.region_id != region_id:
        raise InstitutionNotFound(region_id, institution_id)
    return institution


def _find_in_region(session: Session, region_id: int, key: str) -> Institution | None:
    statement = select(Institution).where(
        Institution.region_id == region_id, Institution.name_key == key
    )
    return session.exec(statement).first()


def _duplicate_after_conflict(
    session: Session, region_id: int, key: str, fallback: str
) -> DuplicateInstitutionName:
    """Roll back a commit the unique constraint refused, and name the institution that won."""
    session.rollback()
    winner = _find_in_region(session, region_id, key)
    return DuplicateInstitutionName(winner.name if winner is not None else fallback)


def create_institution(session: Session, region_id: int, raw_name: str) -> Institution:
    """Store a new, active institution named `raw_name` (cleaned) in the region.

    The region row is locked for the rest of the transaction (research D5), so a deactivation,
    rename or deletion of the region running at the same moment either finishes first and is
    seen here, or waits for this insert. The lock is PostgreSQL's `FOR NO KEY UPDATE`: it
    conflicts with every update and delete of the region, but not with the key-share lock the
    foreign key takes when another transaction inserts an institution, so that insert reaches
    the unique constraint instead of waiting on this one. On SQLite the lock renders nothing;
    SQLite already serialises writers.
    """
    region = session.get(
        Region, region_id, with_for_update={"key_share": True}, populate_existing=True
    )
    if region is None:
        raise RegionNotFound(region_id)
    if not region.is_active:
        raise RegionInactive(region)
    name = clean_name(raw_name)
    key = name_key(name)
    existing = _find_in_region(session, region_id, key)
    if existing is not None:
        raise DuplicateInstitutionName(existing.name)
    now = utc_now()
    institution = Institution(
        region_id=region_id,
        name=name,
        name_key=key,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(institution)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.get(Region, region_id) is None:
            raise RegionNotFound(region_id) from None
        winner = _find_in_region(session, region_id, key)
        raise DuplicateInstitutionName(winner.name if winner is not None else name) from None
    session.refresh(institution)
    logger.info("Institution created: id=%d region_id=%d", institution.id, region_id)
    return institution


def rename_institution(
    session: Session, region_id: int, institution_id: int, raw_name: str
) -> Institution:
    """Rename the institution, keeping its status and its region, whatever the region's status.
    The institution itself never counts as a duplicate, so a change of case is allowed; an
    unchanged name writes nothing."""
    institution = get_institution(session, region_id, institution_id)
    name = clean_name(raw_name)
    key = name_key(name)
    existing = _find_in_region(session, region_id, key)
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
        raise _duplicate_after_conflict(session, region_id, key, name) from None
    session.refresh(institution)
    logger.info("Institution renamed: id=%d region_id=%d", institution.id, region_id)
    return institution


def set_institution_active(
    session: Session, region_id: int, institution_id: int, active: bool
) -> Institution:
    """Activate or deactivate the institution, whatever the region's status. Already in that
    status: nothing changes (FR-032)."""
    institution = get_institution(session, region_id, institution_id)
    if institution.is_active == active:
        return institution
    institution.is_active = active
    institution.updated_at = utc_now()
    session.add(institution)
    session.commit()
    session.refresh(institution)
    logger.info(
        "Institution %s: id=%d region_id=%d",
        "activated" if active else "deactivated",
        institution.id,
        region_id,
    )
    return institution


def count_institution_uses(session: Session, institution_id: int) -> int:
    """How many records refer to the institution. Nothing does yet, so this is `0` (research D9).

    Milestone 8 (teacher links) and milestone 9 (students) each add their count here when they
    add an `institution_id` reference: this is the single place that decides whether an
    institution may be deleted (FR-038). Do not rely on the foreign key alone: SQLite does not
    enforce foreign keys in this application, so without a count here an institution in use
    could be deleted.
    """
    return 0


def delete_institution(session: Session, region_id: int, institution_id: int) -> None:
    """Delete the institution permanently, freeing its name in the region, whatever the region's
    status; refused while anything refers to it."""
    institution = get_institution(session, region_id, institution_id)
    uses = count_institution_uses(session, institution_id)
    if uses > 0:
        raise InstitutionInUse(institution, uses)
    session.delete(institution)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise InstitutionInUse(get_institution(session, region_id, institution_id), 1) from None
    logger.info("Institution deleted: id=%d region_id=%d", institution_id, region_id)
