"""The `users` table: who can sign in. Their roles live in `user_roles`.

See specs/005-roles-authorization/data-model.md#2-user--table-users-changed and
specs/008-teacher-management-consent/data-model.md §1. The sources of each role:

- administrator: `reconcile_users`, from `ADMIN_EMAILS`;
- teacher: an accepted invitation (`app.services.invitations`), which also creates the user;
- student: nobody until milestone 9.

Rows are never hard-deleted: a person who loses every role is deactivated, so later records can
still refer to them. Invariant: active ⇔ at least one role.

On erasure (withdrawal of consent or data deletion), `email` is replaced by `erased-<id>` unless
the person holds the administrator role, whose address comes from the deployment configuration
(milestone 8 research D8).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.core.security import EMAIL_MAX_LENGTH
from app.schemas.people import PERSON_NAME_MAX_LENGTH


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
    first_name: str | None = Field(
        default=None, sa_column=Column(String(PERSON_NAME_MAX_LENGTH), nullable=True)
    )
    """Written only by acceptance and by an administrator's edit. `NULL` = no data stored on
    consent, or erased. Set and cleared together with `last_name`."""
    last_name: str | None = Field(
        default=None, sa_column=Column(String(PERSON_NAME_MAX_LENGTH), nullable=True)
    )
    """As `first_name`."""
    data_erased_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)
    """The time of the latest erasure. Makes every deletion link issued before it used
    (milestone 8 research D10). Not personal data."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Changed only when something about the person actually changes (the active flag, the role
    set, the names, an erasure), so a no-op reconciliation writes nothing (SC-007)."""
