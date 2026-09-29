"""The `users` table: who can sign in, and as what.

See specs/004-email-otp-auth/data-model.md#1-user--table-users-appmodelsuserpy. Rows are filled
only by `reconcile_admins` from the `ADMIN_EMAILS` setting, never by a route, and are never
hard-deleted: a user who loses access is deactivated, so later records can still refer to them.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.core.security import EMAIL_MAX_LENGTH


class Role(StrEnum):
    """Only administrators exist in this milestone. Milestone 5 adds teachers and students; the
    column has no CHECK constraint, so that needs no migration."""

    ADMIN = "admin"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(sa_column=Column(String(EMAIL_MAX_LENGTH), nullable=False, unique=True))
    """Always stored normalised: trimmed and lowercased (FR-001)."""
    role: str = Field(sa_column=Column(String(20), nullable=False))
    """A `Role` value."""
    is_active: bool = Field(nullable=False)
    """Only an active user can obtain a code or keep a session (FR-002, FR-022)."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Changed only when a field actually changes, so a no-op reconciliation writes nothing."""
