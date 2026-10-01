"""Server-side sessions: start one at sign-in, resolve it on every request, end it at logout.

See specs/005-roles-authorization/contracts/auth-services.md#appservicessessionspy and research
D3, D9. The database stores only the SHA-256 of the token; the token itself travels in the signed
cookie. Each session row also carries the role that browser is currently using, so two browsers
of one person can use different roles (FR-011). Nothing here logs a token or a hash.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, update
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.core.security import SESSION_TTL, hash_token, new_session_token
from app.models import Role, User, UserRole, UserSession
from app.services.users import get_roles


@dataclass(frozen=True)
class SessionIdentity:
    """Who a request belongs to, and as what."""

    user: User
    roles: tuple[Role, ...]
    """Never empty, in the fixed order."""
    current_role: Role | None
    """`None` while a person with several roles has not chosen one yet."""


def create_session(
    session: Session, user: User, current_role: Role | None, now: datetime | None = None
) -> str:
    """Start a 14-day session for `user` using `current_role`, and return its plain token.

    The one place a session token is created. In the application only `start_session` calls it;
    the tests' sign-in shortcut calls it directly (FR-041). Commits.
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
            current_role=current_role,
        )
    )
    session.commit()
    return token


def start_session(
    session: Session, user: User, now: datetime | None = None
) -> tuple[str, Role | None]:
    """What a correct code starts: the token, and the initial current role, which is the single
    role held, or `None` when several are held and the person must choose (FR-012, FR-013)."""
    assert user.id is not None
    roles = get_roles(session, user.id)
    current_role = roles[0] if len(roles) == 1 else None
    return create_session(session, user, current_role, now), current_role


def get_session_identity(
    session: Session, token: str, now: datetime | None = None
) -> SessionIdentity | None:
    """Who the token belongs to, if the session is unexpired, the user active, and its current
    role, if set, still held.

    One indexed query returns one row per role held (at most three); a user with no roles matches
    nothing. Then (rows G1–G6 of the contract): a current role that is not held, or not a role at
    all, **deletes this session** and resolves to nobody (FR-017); no current role and exactly one
    role held **stores** that role, which upgrades a session from before milestone 5 (SC-010);
    otherwise the stored state is returned as is. Correct whether or not cleanup has run yet.
    """
    now = now or utc_now()
    statement = (
        select(User, UserSession.id, UserSession.current_role, UserRole.role)
        .join(UserSession, col(UserSession.user_id) == col(User.id))
        .join(UserRole, col(UserRole.user_id) == col(User.id))
        .where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > now,
            User.is_active,
        )
    )
    rows = session.exec(statement).all()
    if not rows:
        return None
    user, session_id, stored_role, _ = rows[0]
    held = {role for *_, role in rows}
    roles = tuple(role for role in Role if role in held)
    # Detached before any commit below, so its loaded attributes outlive this database session.
    session.expunge(user)

    if stored_role is None:
        if len(roles) != 1:
            return SessionIdentity(user=user, roles=roles, current_role=None)
        session.execute(
            update(UserSession)
            .where(col(UserSession.id) == session_id)
            .values(current_role=roles[0])
        )
        session.commit()
        return SessionIdentity(user=user, roles=roles, current_role=roles[0])
    if stored_role not in held:
        session.execute(delete(UserSession).where(col(UserSession.id) == session_id))
        session.commit()
        return None
    return SessionIdentity(user=user, roles=roles, current_role=Role(stored_role))


def set_current_role(session: Session, token: str, role: Role) -> None:
    """Make `role` current for this token's session only; the person's other browsers keep
    theirs (FR-011). The caller has already checked that the role is held. Commits."""
    session.execute(
        update(UserSession)
        .where(col(UserSession.token_hash) == hash_token(token))
        .values(current_role=role)
    )
    session.commit()


def delete_session(session: Session, token: str) -> None:
    """End the session this token belongs to, if it exists. Idempotent, and it leaves the
    user's other sessions (other browsers) alone (US4-6). Commits."""
    session.execute(delete(UserSession).where(col(UserSession.token_hash) == hash_token(token)))
    session.commit()
