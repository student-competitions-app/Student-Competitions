"""The teacher tables: one profile per current teacher, and the links to educational institutions.

See specs/008-teacher-management-consent/data-model.md §3 and §4, and research D9. A teacher has
three things, always written and deleted together, in one transaction, by
`TEACHER_INVITATION.grant` and `.revoke` (`app.services.teachers`):

- the `user_roles` row `(user_id, 'teacher')`;
- one `teacher_profiles` row;
- one or more `teacher_institutions` rows.

Invariant: the profile row exists ⇔ the user holds `teacher` ⇔ the user has at least one link.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now


class AccessLevel(StrEnum):
    """A teacher's access to one educational institution (FR-006). The stored value is what
    `teacher_institutions.access_level` holds."""

    READ = "read"
    WRITE = "write"

    @property
    def label(self) -> str:
        """The name shown to people: `Read`, `Write`."""
        return self.value.capitalize()


class TeacherProfile(SQLModel, table=True):
    __tablename__ = "teacher_profiles"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    can_manage_competitions: bool = Field(default=False, nullable=False)
    """**Can manage competitions** (renamed in milestone 11, FR-009). True: the teacher may
    change the question bank, and competitions from milestone 12. False, or no profile row: the
    teacher reads the bank only. Read for access decisions only through
    `app.services.teacher_access.can_manage_competitions`."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Changed only when the setting changes."""


class TeacherInstitution(SQLModel, table=True):
    __tablename__ = "teacher_institutions"
    __table_args__ = (CheckConstraint("access_level IN ('read', 'write')", name="access_level"),)

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    institution_id: int = Field(foreign_key="institutions.id", primary_key=True, index=True)
    """No cascade: an institution with links cannot be deleted (FR-012). Indexed for
    `count_institution_uses`."""
    access_level: str = Field(sa_column=Column(String(5), nullable=False))
    """An `AccessLevel` value."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Changed only when this link's level changes (FR-040)."""
