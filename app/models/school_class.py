"""The `classes` table: the named groups of students inside one educational institution.

See specs/009-classes-students-management/data-model.md §1 and research D1, D8. The model is
named `SchoolClass` because `class` is a Python keyword; the table and every word shown to people
stay "class". A class is not personal data: it is stored as soon as a teacher creates it (FR-003).

Names are unique within the institution, ignoring case, deactivated classes included, through the
composite constraint on `(institution_id, name_key)`; the same name may exist in another
institution. Its leading `institution_id` column also serves the per-institution list, so there is
no separate index.

A class is **available** ⇔ the class, its institution and its region are all active. The rule is
computed by `app.services.availability`, never stored, so each object keeps its own status
(FR-011, FR-012). A class cannot be deleted while it holds a student (FR-006); it is deleted
together with its institution when it holds none (FR-007).
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.names import NAME_KEY_MAX_LENGTH, NAME_MAX_LENGTH


class SchoolClass(SQLModel, table=True):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("institution_id", "name_key", name="uq_classes_institution_id_name_key"),
        CheckConstraint("year_of_study BETWEEN 1 AND 12", name="year_of_study"),
    )

    id: int | None = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key="institutions.id", nullable=False)
    """Set at creation, never changed: a class cannot move to another institution (FR-003)."""
    name: str = Field(sa_column=Column(String(NAME_MAX_LENGTH), nullable=False))
    """As entered after `clean_name`. Shown everywhere."""
    name_key: str = Field(sa_column=Column(String(NAME_KEY_MAX_LENGTH), nullable=False))
    """`name_key(name)`. Never shown: unique within the institution only, with `institution_id`."""
    year_of_study: int = Field(nullable=False)
    """1–12 (FR-001). Its students' year of study is read from here."""
    is_active: bool = Field(default=True, nullable=False)
    """The class's own status, independent of its institution's and region's (FR-012)."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by an edit or status change that actually changes something."""
