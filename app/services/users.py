"""Users and their roles: looking them up, and making the administrators match the deployment
configuration.

See specs/005-roles-authorization/contracts/auth-services.md#appservicesuserspy and
specs/008-teacher-management-consent/contracts/services.md#appservicesuserspy-changed (research
D16). `reconcile_users`, run at every start from `ADMIN_EMAILS`, is the only writer of the
administrator role, and it never reads or writes any other role: teachers are granted by accepted
invitations (`app.services.invitations`) and removed by `app.services.teachers` and
`app.services.consent`. Every writer keeps the invariant "active ⇔ holds at least one role", so
the milestone 4 checks on `is_active` still decide who may obtain a code (FR-010). Nothing here
logs an address.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.models import LoginCode, Role, User, UserRole, UserSession


@dataclass(frozen=True)
class ReconcileResult:
    created: int
    reactivated: int
    deactivated: int
    roles_added: int
    roles_removed: int
    unchanged: int
    """People whose active flag and role set did not change."""


def get_active_user_by_email(session: Session, email: str) -> User | None:
    """The active user with this (already normalised) address, if any."""
    return session.exec(select(User).where(User.email == email, User.is_active)).first()


def get_roles(session: Session, user_id: int) -> tuple[Role, ...]:
    """The roles held, in the fixed order (administrator, teacher, student); `()` for none."""
    held = set(session.exec(select(UserRole.role).where(UserRole.user_id == user_id)))
    return tuple(role for role in Role if role in held)


def get_user_by_email(session: Session, email: str) -> User | None:
    """The user with this (already normalised) address, active or not."""
    return session.exec(select(User).where(User.email == email)).first()


def end_all_sessions(session: Session, user_id: int) -> None:
    """Delete every session of the user: signed out in every browser. Does not commit."""
    session.execute(delete(UserSession).where(col(UserSession.user_id) == user_id))


def display_name(user: User) -> str:
    """How a person is named to others: "<first> <last>" when names are stored, otherwise the
    email."""
    if user.first_name is not None:
        return f"{user.first_name} {user.last_name}"
    return user.email


def _all_users(session: Session) -> dict[str, User]:
    """Every user, by address. The table holds hundreds of rows at most."""
    return {user.email: user for user in session.exec(select(User))}


def reconcile_users(
    session: Session,
    admin_emails: Sequence[str],
    now: datetime | None = None,
) -> ReconcileResult:
    """Make the administrators exactly the people `ADMIN_EMAILS` lists, in one transaction.

    `admin_emails` holds addresses already normalised and de-duplicated by the settings loader.
    Only `admin` role rows are read and written (FR-057):

    - a listed address with no user is created, active;
    - an inactive listed user is reactivated;
    - the administrator role is added to every listed user who lacks it, and removed from every
      unlisted user who holds it;
    - a user who lost the administrator role is deactivated only when no role at all is left, so a
      teacher removed from the list stays a teacher.

    Every session of anyone who lost the administrator role is deleted, so a removal logs them out
    everywhere; adding it keeps their sessions (FR-005). Every session and code of every inactive
    user is deleted too, which also finishes any earlier partial run. `updated_at` changes only
    for people whose active flag or administrator role changed, so a second run writes nothing
    (SC-007). Users are never deleted.

    Commits once. If that fails with `IntegrityError` (another instance inserted the same new user
    or role at the same moment), the caller rolls back and calls this once more.
    """
    now = now or utc_now()
    listed = set(admin_emails)
    users = _all_users(session)
    created = 0
    for email in sorted(listed):
        if email not in users:
            users[email] = User(email=email, is_active=True, created_at=now, updated_at=now)
            session.add(users[email])
            created += 1
    session.flush()

    roles_by_user: dict[int, set[str]] = {}
    for row in session.exec(select(UserRole)):
        roles_by_user.setdefault(row.user_id, set()).add(row.role)

    reactivated = deactivated = roles_added = roles_removed = unchanged = 0
    lost_admin: set[int] = set()
    for email, user in users.items():
        assert user.id is not None
        held = roles_by_user.get(user.id, set())
        wanted = email in listed
        has_admin = Role.ADMIN in held
        changed = False
        if wanted and not has_admin:
            session.add(UserRole(user_id=user.id, role=Role.ADMIN, created_at=now))
            roles_added += 1
            changed = True
        elif not wanted and has_admin:
            session.execute(
                delete(UserRole).where(
                    col(UserRole.user_id) == user.id, col(UserRole.role) == Role.ADMIN
                )
            )
            roles_removed += 1
            lost_admin.add(user.id)
            changed = True
        remaining = (held - {Role.ADMIN}) | ({Role.ADMIN} if wanted else set())
        if remaining and not user.is_active:
            user.is_active = True
            reactivated += 1
            changed = True
        elif not remaining and user.is_active:
            user.is_active = False
            deactivated += 1
            changed = True
        if changed:
            user.updated_at = now
            session.add(user)
        else:
            unchanged += 1
    session.flush()

    if lost_admin:
        session.execute(delete(UserSession).where(col(UserSession.user_id).in_(lost_admin)))
    inactive = select(User.id).where(col(User.is_active).is_(False))
    session.execute(delete(UserSession).where(col(UserSession.user_id).in_(inactive)))
    session.execute(delete(LoginCode).where(col(LoginCode.user_id).in_(inactive)))
    session.commit()
    return ReconcileResult(
        created=created,
        reactivated=reactivated,
        deactivated=deactivated,
        roles_added=roles_added,
        roles_removed=roles_removed,
        unchanged=unchanged,
    )
