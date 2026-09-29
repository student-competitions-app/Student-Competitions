"""The `login_codes` table: the one-time codes sent by email.

See specs/004-email-otp-auth/data-model.md#3-logincode--table-login_codes-appmodelslogin_codepy.
Only a keyed hash of the code is stored (FR-027). A code is live while `used_at IS NULL AND
attempts < 5 AND expires_at > now`, and issuing a new one deletes the user's older unused codes,
so each user has at most one code that could be live.
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime


class LoginCode(SQLModel, table=True):
    __tablename__ = "login_codes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    code_hash: str = Field(sa_column=Column(String(64), nullable=False))
    created_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    expires_at: datetime = Field(sa_type=UTCDateTime, nullable=False, index=True)
    """`created_at` + 20 minutes (FR-011)."""
    attempts: int = Field(default=0, nullable=False)
    """Wrong submissions so far; the code is dead at 5 (FR-016)."""
    used_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)
    """Set once, atomically, on successful verification."""
