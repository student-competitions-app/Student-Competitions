"""Code-request limits: at most 5 per address and 20 per client in any sliding hour.

See specs/004-email-otp-auth/research.md#d5 and data-model §4. The hits live in the application
database, so the limits survive restarts and are shared by every instance (FR-019). Every
submitted address counts, registered or not, so reaching the limit reveals nothing (FR-017).
Keys are stored only as keyed hashes. Wrong code attempts are limited on the code itself, not
here.
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.core.security import hash_rate_limit_key
from app.models import RateLimitHit

BUCKET_CODE_EMAIL = "code_email"
BUCKET_CODE_CLIENT = "code_client"

EMAIL_CODE_LIMIT = 5
CLIENT_CODE_LIMIT = 20

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


def allow_code_request(
    session: Session, secret_key: str, email: str, client: str, now: datetime | None = None
) -> bool:
    """Record a code request and return `True`, or return `False` if the address or the client
    has reached its limit in the last hour. A refused request is not recorded, so waiting is
    enough to be let in again. Commits.

    Two truly simultaneous requests at the last free slot can both pass; the bound is off by the
    concurrency degree, which is negligible for the guessing arithmetic (research D5).
    """
    now = now or utc_now()
    since = now - WINDOW
    buckets = (
        (
            BUCKET_CODE_EMAIL,
            hash_rate_limit_key(secret_key, BUCKET_CODE_EMAIL, email),
            EMAIL_CODE_LIMIT,
        ),
        (
            BUCKET_CODE_CLIENT,
            hash_rate_limit_key(secret_key, BUCKET_CODE_CLIENT, client),
            CLIENT_CODE_LIMIT,
        ),
    )
    if any(_hits(session, bucket, key_hash, since) >= limit for bucket, key_hash, limit in buckets):
        return False
    for bucket, key_hash, _ in buckets:
        session.add(RateLimitHit(bucket=bucket, key_hash=key_hash, created_at=now))
    session.commit()
    return True
