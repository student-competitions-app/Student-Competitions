"""The `rate_limit_hits` table: an append-only log of code requests, for sliding-window limits.

See specs/004-email-otp-auth/data-model.md, section 4.
It lives in the application database so the limits survive restarts (FR-019). Keys are stored
only as keyed hashes: neither an address nor a client IP is kept in plain form.
"""

from datetime import datetime

from sqlalchemy import Column, Index, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime


class RateLimitHit(SQLModel, table=True):
    __tablename__ = "rate_limit_hits"
    # Named explicitly: the naming convention's `ix` pattern covers only the first column.
    __table_args__ = (
        Index("ix_rate_limit_hits_bucket_key_hash_created_at", "bucket", "key_hash", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    bucket: str = Field(sa_column=Column(String(32), nullable=False))
    key_hash: str = Field(sa_column=Column(String(64), nullable=False))
    created_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
