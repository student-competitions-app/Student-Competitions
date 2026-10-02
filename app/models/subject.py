"""The `subjects` table: the knowledge areas competitions are held in, such as mathematics.

See specs/006-admin-area/data-model.md#1-subject--table-subjects-new. Only administrators create
or change subjects. Names are validated by `app.schemas.subject` before they reach this model;
`name_key` is what makes names unique ignoring case, enforced by the database on both engines.

Nothing refers to subjects yet. Milestones 9 (questions) and 10 (competitions) add references,
and each must extend `app.services.subjects.count_subject_uses`, so a subject in use can never be
deleted.
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.subject import SUBJECT_NAME_KEY_MAX_LENGTH, SUBJECT_NAME_MAX_LENGTH


class Subject(SQLModel, table=True):
    __tablename__ = "subjects"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(SUBJECT_NAME_MAX_LENGTH), nullable=False))
    """As entered after trimming. Shown everywhere."""
    name_key: str = Field(
        sa_column=Column(String(SUBJECT_NAME_KEY_MAX_LENGTH), nullable=False, unique=True)
    )
    """`subject_name_key(name)`. Never shown: it only enforces uniqueness ignoring case."""
    is_active: bool = Field(default=True, nullable=False)
    """`False` once deactivated: kept, but not offered for new questions or competitions."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by a rename or status change that actually changes something."""
