"""Server-side sessions: create one at sign-in, resolve it on every request, delete it at logout.

See specs/004-email-otp-auth/contracts/auth-services.md#appservicessessionspy and research D3.
The database stores only the SHA-256 of the token; the token itself travels in the signed
cookie. Nothing here logs a token or a hash.
"""

from datetime import datetime

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.core.security import SESSION_TTL, hash_token, new_session_token
from app.models import User, UserSession


def create_session(session: Session, user: User, now: datetime | None = None) -> str:
    """Start a 14-day session for `user` and return its plain token, for the cookie.

    The one place a session token is created. Only the code-verification route calls it in the
    application; the tests' `admin_client` fixture calls it directly (FR-034, FR-046).
    """
    now = now or utc_now()
    token = new_session_token()
    assert user.id is not None
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + SESSION_TTL,
        )
    )
    session.commit()
    return token


def get_session_user(session: Session, token: str, now: datetime | None = None) -> User | None:
    """The user a token belongs to, if the session is unexpired and the user is active.

    One indexed query, and correct whether or not cleanup has run yet (FR-022, FR-026).
    """
    now = now or utc_now()
    statement = (
        select(User)
        .join(UserSession, col(UserSession.user_id) == col(User.id))
        .where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > now,
            User.is_active,
        )
    )
    return session.exec(statement).first()


def delete_session(session: Session, token: str) -> None:
    """End the session this token belongs to, if it exists. Idempotent, and it leaves the
    user's other sessions (other browsers) alone (US4-6). Commits."""
    session.execute(delete(UserSession).where(col(UserSession.token_hash) == hash_token(token)))
    session.commit()
