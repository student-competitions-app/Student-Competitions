"""Sliding-window rate limits: a request is allowed while every bucket it counts against has had
fewer than its limit of hits in the last hour.

See specs/004-email-otp-auth/research.md#d5 and data-model §4, and, for the invitation and
data-deletion buckets, specs/008-teacher-management-consent/research.md#d12. The hits live in the
application database, so the limits survive restarts and are shared by every instance (FR-019).
Every submitted key counts, registered address or not, so reaching a limit reveals nothing
(FR-017). Keys are stored only as keyed hashes. Wrong code attempts are limited on the code
itself, not here.

| Bucket | Key | Limit per hour |
|---|---|---|
| `code_email`, `code_client` | address, client | 5, 20 |
| `invite_inviter`, `invite_email` | inviter's user id, invited address | 20, 5 |
| `deletion_email`, `deletion_client` | address, client | 5, 20 |
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.core.security import hash_rate_limit_key
from app.models import RateLimitHit

BUCKET_CODE_EMAIL = "code_email"
BUCKET_CODE_CLIENT = "code_client"
BUCKET_INVITE_INVITER = "invite_inviter"
BUCKET_INVITE_EMAIL = "invite_email"
BUCKET_DELETION_EMAIL = "deletion_email"
BUCKET_DELETION_CLIENT = "deletion_client"

EMAIL_CODE_LIMIT = 5
CLIENT_CODE_LIMIT = 20
INVITER_INVITE_LIMIT = 20
EMAIL_INVITE_LIMIT = 5
EMAIL_DELETION_LIMIT = 5
CLIENT_DELETION_LIMIT = 20

WINDOW = timedelta(hours=1)


def _hits(session: Session, bucket: str, key_hash: str, since: datetime) -> int:
    statement = (
        select(func.count())
        .select_from(RateLimitHit)
        .where(
            col(RateLimitHit.bucket) == bucket,
            col(RateLimitHit.key_hash) == key_hash,
            col(RateLimitHit.created_at) > since,
        )
    )
    return session.exec(statement).one()


@dataclass(frozen=True)
class LimitCheck:
    """One bucket a request counts against."""

    bucket: str
    """At most 32 characters: `rate_limit_hits.bucket`."""
    key: str
    """In plain form; hashed with `hash_rate_limit_key` before any query or insert."""
    limit: int


def allow(
    session: Session,
    secret_key: str,
    checks: Sequence[LimitCheck],
    now: datetime | None = None,
) -> bool:
    """Record one hit per check and return `True`, or return `False` if any bucket has already
    reached its limit in the last hour. A refused request is not recorded, so waiting is enough to
    be let in again. Commits.

    Two truly simultaneous requests at the last free slot can both pass; the bound is off by the
    concurrency degree, which is negligible here (research D5).
    """
    now = now or utc_now()
    since = now - WINDOW
    hashed = [
        (check.bucket, hash_rate_limit_key(secret_key, check.bucket, check.key), check.limit)
        for check in checks
    ]
    if any(_hits(session, bucket, key_hash, since) >= limit for bucket, key_hash, limit in hashed):
        return False
    for bucket, key_hash, _ in hashed:
        session.add(RateLimitHit(bucket=bucket, key_hash=key_hash, created_at=now))
    session.commit()
    return True


def allow_code_request(
    session: Session, secret_key: str, email: str, client: str, now: datetime | None = None
) -> bool:
    """A sign-in code request: at most 5 per address and 20 per client in any hour (`allow`)."""
    return allow(
        session,
        secret_key,
        (
            LimitCheck(BUCKET_CODE_EMAIL, email, EMAIL_CODE_LIMIT),
            LimitCheck(BUCKET_CODE_CLIENT, client, CLIENT_CODE_LIMIT),
        ),
        now,
    )
