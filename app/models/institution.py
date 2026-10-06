"""The `institutions` table: the educational institutions teachers and students belong to.

See specs/007-institutions/data-model.md#1-institution--table-institutions-new. Only
administrators create or change institutions. Names are validated by `app.schemas.institution`
before they reach this model; `name_key` is what makes names unique ignoring case, enforced by the
database on both engines.

Other records refer to an institution by `id` only, never by its name, so a rename never breaks a
link (FR-018). Nothing refers to institutions yet. Milestones 8 (teacher links) and 9 (student
details) add references, and each must extend
`app.services.institutions.count_institution_uses`, so an institution in use can never be deleted.
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.institution import INSTITUTION_NAME_KEY_MAX_LENGTH, INSTITUTION_NAME_MAX_LENGTH


class Institution(SQLModel, table=True):
    __tablename__ = "institutions"

    id: int | None = Field(default=None, primary_key=True)
    """The identity other records refer to; never changes."""
    name: str = Field(sa_column=Column(String(INSTITUTION_NAME_MAX_LENGTH), nullable=False))
    """As entered after trimming. Shown everywhere."""
    name_key: str = Field(
        sa_column=Column(String(INSTITUTION_NAME_KEY_MAX_LENGTH), nullable=False, unique=True)
    )
    """`institution_name_key(name)`. Never shown: it only enforces uniqueness ignoring case."""
    is_active: bool = Field(default=True, nullable=False)
    """`False` once deactivated: kept, but not offered for new teacher or student links."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by a rename or status change that actually changes something."""
