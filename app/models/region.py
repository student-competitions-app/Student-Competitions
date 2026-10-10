"""The `regions` table: the geographic groupings educational institutions belong to.

See specs/007-region-and-institutions-management/data-model.md#1-region--table-regions-new.
Only administrators create or change regions; there is no preset list. Names are validated by
`app.schemas.names` before they reach this model; `name_key` is what makes names unique ignoring
case, enforced by the database on both engines.

A region cannot be deleted while it holds institutions, active or deactivated. Deactivating it
never changes its institutions' statuses: each keeps its own (FR-033).
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.names import NAME_KEY_MAX_LENGTH, NAME_MAX_LENGTH


class Region(SQLModel, table=True):
    __tablename__ = "regions"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(NAME_MAX_LENGTH), nullable=False))
    """As entered after trimming. Shown everywhere."""
    name_key: str = Field(
        sa_column=Column(String(NAME_KEY_MAX_LENGTH), nullable=False, unique=True)
    )
    """`name_key(name)`. Never shown: it only enforces uniqueness ignoring case."""
    is_active: bool = Field(default=True, nullable=False)
    """`False` once deactivated: kept and listed, but no new institution can be added to it."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by a rename or status change that actually changes something."""
