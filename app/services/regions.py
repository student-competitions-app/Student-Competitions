"""Region operations: what the `/admin/institutions` routes call for the left-hand list.

See specs/007-region-and-institutions-management/contracts/institution-service.md and research
D2, D4, D6. These functions enforce no authorization: every route that calls them is
`@allow_roles(Role.ADMIN)`, and a later caller must put its own role check in front.

Every function takes an open session as its first argument; the caller owns the session. Each
write is one committed unit of work, rolled back on error. Names are cleaned here with
`clean_name`, so callers pass the value exactly as submitted. The unique constraint on
`name_key`, not the lookup before an insert, is the guarantee against simultaneous submissions.

This module does not import `app.services.institutions` (which imports this one); it counts a
region's institutions with its own query on the `Institution` model.

Each successful change logs one line with the region id only; a no-op logs nothing.
"""

import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import utc_now
from app.models import Institution, Region
from app.schemas.names import clean_name, name_key

logger = logging.getLogger("uvicorn.error")


class RegionNotFound(LookupError):
    """No region has this id. Raised instead of returning `None`."""

    def __init__(self, region_id: int) -> None:
        super().__init__(f"Region {region_id} not found")
        self.region_id = region_id


class DuplicateRegionName(ValueError):
    """Another region already has this name, ignoring case; `message` names it as stored."""

    def __init__(self, existing_name: str) -> None:
        self.existing_name = existing_name
        self.message = f"A region named “{existing_name}” already exists."
        super().__init__(self.message)


class RegionNotEmpty(ValueError):
    """The region still holds `institutions` institutions, so it cannot be deleted (FR-036)."""

    def __init__(self, region: Region, institutions: int) -> None:
        super().__init__(f"Region {region.id} still holds institutions")
        self.region = region
        self.institutions = institutions


def list_regions(session: Session) -> list[Region]:
    """All regions, active and deactivated, sorted ignoring case, ties by id.

    Sorted in Python on `name_key` rather than with `ORDER BY`, which follows each engine's
    collation: this way SQLite and PostgreSQL give the same order (research D6).
    """
    regions = session.exec(select(Region)).all()
    return sorted(regions, key=lambda region: (region.name_key, region.id))


def get_region(session: Session, region_id: int) -> Region:
    """The stored region."""
    region = session.get(Region, region_id)
    if region is None:
        raise RegionNotFound(region_id)
    return region


def _find_by_key(session: Session, key: str) -> Region | None:
    return session.exec(select(Region).where(Region.name_key == key)).first()


def _duplicate_after_conflict(session: Session, key: str, fallback: str) -> DuplicateRegionName:
    """Roll back a commit the unique constraint refused, and name the region that won."""
    session.rollback()
    winner = _find_by_key(session, key)
    return DuplicateRegionName(winner.name if winner is not None else fallback)


def create_region(session: Session, raw_name: str) -> Region:
    """Store a new, active region named `raw_name` (cleaned) and return it with its new id."""
    name = clean_name(raw_name)
    key = name_key(name)
    existing = _find_by_key(session, key)
    if existing is not None:
        raise DuplicateRegionName(existing.name)
    now = utc_now()
    region = Region(name=name, name_key=key, is_active=True, created_at=now, updated_at=now)
    session.add(region)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, key, name) from None
    session.refresh(region)
    logger.info("Region created: id=%d", region.id)
    return region


def rename_region(session: Session, region_id: int, raw_name: str) -> Region:
    """Rename the region, keeping its status. The region itself never counts as a duplicate, so a
    change of case is allowed; an unchanged name writes nothing."""
    region = get_region(session, region_id)
    name = clean_name(raw_name)
    key = name_key(name)
    existing = _find_by_key(session, key)
    if existing is not None and existing.id != region.id:
        raise DuplicateRegionName(existing.name)
    if region.name == name and region.name_key == key:
        return region
    region.name = name
    region.name_key = key
    region.updated_at = utc_now()
    session.add(region)
    try:
        session.commit()
    except IntegrityError:
        raise _duplicate_after_conflict(session, key, name) from None
    session.refresh(region)
    logger.info("Region renamed: id=%d", region.id)
    return region


def set_region_active(session: Session, region_id: int, active: bool) -> Region:
    """Activate or deactivate the region. Already in that status: nothing changes (FR-032).

    Only the region row changes: its institutions keep their own statuses (FR-033), so activating
    it again gives back exactly the statuses they had.
    """
    region = get_region(session, region_id)
    if region.is_active == active:
        return region
    region.is_active = active
    region.updated_at = utc_now()
    session.add(region)
    session.commit()
    session.refresh(region)
    logger.info("Region %s: id=%d", "activated" if active else "deactivated", region.id)
    return region


def count_region_institutions(session: Session, region_id: int) -> int:
    """How many institutions the region holds, active and deactivated."""
    statement = (
        select(func.count()).select_from(Institution).where(Institution.region_id == region_id)
    )
    return session.exec(statement).one()


def delete_region(session: Session, region_id: int) -> None:
    """Delete the region permanently, freeing its name; refused while it holds any institution,
    active or deactivated (FR-036). On PostgreSQL the foreign key also refuses it, should an
    institution be added at the same moment."""
    region = get_region(session, region_id)
    institutions = count_region_institutions(session, region_id)
    if institutions > 0:
        raise RegionNotEmpty(region, institutions)
    session.delete(region)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise RegionNotEmpty(
            get_region(session, region_id), count_region_institutions(session, region_id) or 1
        ) from None
    logger.info("Region deleted: id=%d", region_id)
