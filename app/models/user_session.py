"""The `sessions` table: one row per signed-in browser.

See specs/004-email-otp-auth/data-model.md#2-usersession--table-sessions-appmodelsuser_sessionpy.
Named `UserSession` so it cannot be confused with `sqlmodel.Session`. The row holds only the
SHA-256 of the session token; the token itself exists only in the signed cookie (FR-021).
Each row also carries the role that browser is currently using (milestone 5), so two browsers of
one person can use different roles.
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime


class UserSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    token_hash: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    created_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    expires_at: datetime = Field(sa_type=UTCDateTime, nullable=False, index=True)
    """`created_at` + 14 days, absolute (FR-023). Indexed for cleanup."""
    current_role: str | None = Field(default=None, sa_column=Column(String(20), nullable=True))
    """The role this browser is using (a `Role` value); `NULL` = signed in, no role chosen yet.
    No CHECK constraint: it is validated against the person's roles on every request, and
    anything else ends the session (specs/005-roles-authorization/data-model.md#4)."""
