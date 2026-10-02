"""The `users` table: who can sign in. Their roles live in `user_roles`.

See specs/005-roles-authorization/data-model.md#2-user--table-users-changed. Rows are filled only
by `reconcile_users` from the three role lists (`ADMIN_EMAILS`, `TEACHER_EMAILS`,
`STUDENT_EMAILS`), never by a route, and are never hard-deleted: a person who loses every role is
deactivated, so later records can still refer to them. Invariant: active ⇔ at least one role.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.core.security import EMAIL_MAX_LENGTH


class Role(StrEnum):
    """The three roles (FR-001). The stored value is what `user_roles.role` and
    `sessions.current_role` hold; `admin` is milestone 4's value, so existing data needs no
    translation. The definition order is the fixed order used wherever roles are listed: the role
    choice, the header switch and `SessionIdentity.roles`."""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

    @property
    def label(self) -> str:
        """The name shown to people: `Administrator`, `Teacher`, `Student`."""
        return _LABELS[self]


_LABELS = {Role.ADMIN: "Administrator", Role.TEACHER: "Teacher", Role.STUDENT: "Student"}

ALL_ROLES = frozenset(Role)
"""Every role, for pages open to everyone signed in, such as `/`."""


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(sa_column=Column(String(EMAIL_MAX_LENGTH), nullable=False, unique=True))
    """Always stored normalised: trimmed and lowercased (FR-002)."""
    is_active: bool = Field(nullable=False)
    """Only an active user can obtain a code or keep a session (FR-010). Active ⇔ holds at least
    one role."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Changed only when the active flag or the role set actually changes, so a no-op
    reconciliation writes nothing (SC-007)."""
