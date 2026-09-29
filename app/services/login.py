"""Login codes: issue one, verify one, and deliver one by email after the response.

See specs/004-email-otp-auth/contracts/auth-services.md#appservicesloginpy and research D2, D10.
A code is six digits, stored only as a keyed hash bound to the address, valid for 20 minutes,
usable once, and dead after 5 wrong attempts. Issuing a code deletes the user's older unused
ones, so the newest code wins. Nothing here logs an address, a code or an email body.
"""

import hmac
import logging
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Engine, delete, update
from sqlmodel import Session, col, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.security import generate_code, hash_code
from app.models import LoginCode, RateLimitHit, User, UserSession
from app.services.email import EmailDeliveryError, EmailSender, login_code_message
from app.services.users import get_active_user_by_email

CODE_TTL = timedelta(minutes=20)
CODE_MAX_ATTEMPTS = 5

RATE_LIMIT_RETENTION = timedelta(hours=1)
"""Rate-limit hits older than the limits' sliding window count for nothing and are purged."""

logger = logging.getLogger("uvicorn.error")


def issue_code(session: Session, secret_key: str, user: User, now: datetime | None = None) -> str:
    """Replace the user's unused codes with a new one and return it in plain form, for the
    email only. Commits."""
    now = now or utc_now()
    assert user.id is not None
    session.execute(
        delete(LoginCode).where(col(LoginCode.user_id) == user.id, col(LoginCode.used_at).is_(None))
    )
    code = generate_code()
    session.add(
        LoginCode(
            user_id=user.id,
            code_hash=hash_code(secret_key, user.email, code),
            created_at=now,
            expires_at=now + CODE_TTL,
            attempts=0,
        )
    )
    session.commit()
    return code


def _live(now: datetime) -> tuple[ColumnElement[bool], ...]:
    """The conditions under which a code can still be used."""
    return (
        col(LoginCode.used_at).is_(None),
        col(LoginCode.attempts) < CODE_MAX_ATTEMPTS,
        col(LoginCode.expires_at) > now,
    )


def verify_code(
    session: Session, secret_key: str, email: str, code: str, now: datetime | None = None
) -> User | None:
    """The user, if `code` is the live code of the active user `email`; otherwise `None`.

    A match is consumed with one conditional `UPDATE`, so of two simultaneous submissions only
    the one that changes the row signs in. A wrong code against a live one counts an attempt.
    Every other case (no user, inactive, no live code) changes nothing. Commits.
    """
    now = now or utc_now()
    user = get_active_user_by_email(session, email)
    if user is None:
        return None
    live = session.exec(
        select(LoginCode)
        .where(col(LoginCode.user_id) == user.id, *_live(now))
        .order_by(col(LoginCode.id).desc())
    ).first()
    if live is None:
        return None
    if hmac.compare_digest(live.code_hash, hash_code(secret_key, email, code)):
        consumed = session.execute(
            update(LoginCode).where(col(LoginCode.id) == live.id, *_live(now)).values(used_at=now)
        )
        session.commit()
        return user if consumed.rowcount == 1 else None
    session.execute(
        update(LoginCode)
        .where(col(LoginCode.id) == live.id, col(LoginCode.attempts) < CODE_MAX_ATTEMPTS)
        .values(attempts=col(LoginCode.attempts) + 1)
    )
    session.commit()
    return None


def purge_expired(session: Session, now: datetime | None = None) -> None:
    """Delete what can no longer be used: expired sessions, expired or used codes, and rate-limit
    hits older than the window (research D9). Commits.

    Runs at startup and after every code request, so the tables stay small without a scheduler.
    Correctness never depends on it: every read checks expiry itself (FR-026).
    """
    now = now or utc_now()
    session.execute(delete(UserSession).where(col(UserSession.expires_at) <= now))
    session.execute(
        delete(LoginCode).where(
            (col(LoginCode.expires_at) <= now) | col(LoginCode.used_at).is_not(None)
        )
    )
    session.execute(
        delete(RateLimitHit).where(col(RateLimitHit.created_at) <= now - RATE_LIMIT_RETENTION)
    )
    session.commit()


def deliver_login_code(
    engine: Engine, sender: EmailSender, settings: AuthSettings, email: str
) -> None:
    """The background task behind `POST /login`, run after the response is sent (research D10).

    For an active user it issues a code and emails it; for anyone else it does nothing. Because
    all of that happens after the response, the response and its timing are the same for every
    address (FR-010). It cleans up on every run, for known and unknown addresses alike. Every
    exception is caught and logged by type, or for a delivery failure by its status, and never
    with the address, the code or the body (FR-039).
    """
    try:
        with Session(engine) as session:
            user = get_active_user_by_email(session, email)
            code = issue_code(session, settings.secret_key, user) if user is not None else None
            purge_expired(session)
        if code is not None:
            minutes = int(CODE_TTL.total_seconds() // 60)
            sender.send(login_code_message(email, code, minutes))
    except EmailDeliveryError as exc:
        logger.error("Login email not sent: %s", exc)
    except Exception as exc:
        logger.error("Login email not sent: %s", type(exc).__name__)
