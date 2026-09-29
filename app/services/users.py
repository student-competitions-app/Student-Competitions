"""Users: looking one up, and making the administrators match the deployment configuration.

See specs/004-email-otp-auth/contracts/auth-services.md#appservicesuserspy and research D13.
No route creates, changes or lists users (FR-007): `reconcile_admins`, run at every start, is the
only writer. Nothing here logs an address.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, update
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.models import LoginCode, Role, User, UserSession


@dataclass(frozen=True)
class ReconcileResult:
    created: int
    reactivated: int
    deactivated: int
    unchanged: int


def get_active_user_by_email(session: Session, email: str) -> User | None:
    """The active user with this (already normalised) address, if any."""
    return session.exec(select(User).where(User.email == email, User.is_active)).first()


def _users_by_email(session: Session, emails: set[str]) -> dict[str, User]:
    """The existing users among `emails`, by address."""
    statement = select(User).where(col(User.email).in_(emails))
    return {user.email: user for user in session.exec(statement)}


def reconcile_admins(
    session: Session, emails: tuple[str, ...] | list[str], now: datetime | None = None
) -> ReconcileResult:
    """Make the active administrators exactly the listed addresses, in one transaction.

    `emails` is already normalised and de-duplicated by the settings loader. A listed address
    that is missing is created, an inactive one is reactivated, an active administrator is left
    untouched. Every active administrator not listed is deactivated, and every inactive user's
    sessions and codes are deleted, so a removed administrator loses access at once (FR-004).
    That cleanup covers all inactive users, not just the ones deactivated now, so it also
    finishes any earlier partial run. `updated_at` changes only on rows that actually change, so
    running this twice writes nothing the second time (SC-007). Users are never deleted.

    Commits. If the commit fails with `IntegrityError` (another instance inserted the same new
    address at the same moment), the caller rolls back and calls this once more.
    """
    now = now or utc_now()
    listed = set(emails)
    existing = _users_by_email(session, listed)
    created = reactivated = unchanged = 0
    for email in sorted(listed):
        user = existing.get(email)
        if user is None:
            session.add(
                User(email=email, role=Role.ADMIN, is_active=True, created_at=now, updated_at=now)
            )
            created += 1
        elif not user.is_active:
            user.is_active = True
            user.updated_at = now
            session.add(user)
            reactivated += 1
        else:
            unchanged += 1
    deactivated = session.execute(
        update(User)
        .where(col(User.role) == Role.ADMIN, col(User.is_active), col(User.email).not_in(listed))
        .values(is_active=False, updated_at=now)
    ).rowcount
    inactive = select(User.id).where(col(User.is_active).is_(False))
    session.execute(delete(UserSession).where(col(UserSession.user_id).in_(inactive)))
    session.execute(delete(LoginCode).where(col(LoginCode.user_id).in_(inactive)))
    session.commit()
    return ReconcileResult(
        created=created, reactivated=reactivated, deactivated=deactivated, unchanged=unchanged
    )
