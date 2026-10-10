"""The `institutions` table: the schools, colleges and universities of each region.

See specs/007-region-and-institutions-management/data-model.md §2 and §5. Every institution
belongs to exactly one region for its whole life. Names are unique within the region, ignoring
case, through the composite constraint on `(region_id, name_key)`; the same name may exist in
another region. Its leading `region_id` column also serves the per-region queries, so there is no
separate index (research D3).

An institution is available for selection only when the institution and its region are both
active. Nothing selects institutions yet; milestone 8's picker must compute exactly this rule.

Nothing refers to institutions yet. Milestones 8 (teacher links) and 9 (students) add references,
and each must extend `app.services.institutions.count_institution_uses`, so an institution in use
can never be deleted.
"""

from datetime import datetime

from sqlalchemy import Column, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.names import NAME_KEY_MAX_LENGTH, NAME_MAX_LENGTH


class Institution(SQLModel, table=True):
    __tablename__ = "institutions"
    __table_args__ = (
        UniqueConstraint("region_id", "name_key", name="uq_institutions_region_id_name_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    region_id: int = Field(foreign_key="regions.id", nullable=False)
    """Set at creation and never changed: an institution cannot move to another region (FR-030)."""
    name: str = Field(sa_column=Column(String(NAME_MAX_LENGTH), nullable=False))
    """As entered after trimming. Shown everywhere."""
    name_key: str = Field(sa_column=Column(String(NAME_KEY_MAX_LENGTH), nullable=False))
    """`name_key(name)`. Never shown: unique within the region only, with `region_id`."""
    is_active: bool = Field(default=True, nullable=False)
    """`False` once deactivated: kept and listed. Independent of the region's status (FR-033)."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by a rename or status change that actually changes something."""
