"""Users and their roles: looking them up, and making them match the deployment configuration.

See specs/005-roles-authorization/contracts/auth-services.md#appservicesuserspy and research D8.
No route creates, changes or lists users or roles (FR-009): `reconcile_users`, run at every start
from the three role lists, is the only writer. It keeps the invariant "active ⇔ holds at least
one role", so the milestone 4 checks on `is_active` still decide who may obtain a code (FR-010).
Nothing here logs an address.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
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


def _all_users(session: Session) -> dict[str, User]:
    """Every user, by address. The table holds hundreds of rows at most."""
    return {user.email: user for user in session.exec(select(User))}


def _roles_by_user(session: Session) -> dict[int, set[Role]]:
    """Every role assignment, by user id."""
    held: dict[int, set[Role]] = defaultdict(set)
    for row in session.exec(select(UserRole)):
        held[row.user_id].add(Role(row.role))
    return held


def reconcile_users(
    session: Session,
    role_lists: Mapping[Role, Sequence[str]],
    now: datetime | None = None,
) -> ReconcileResult:
    """Make the people and their roles exactly what the role lists say, in one transaction.

    `role_lists` holds addresses already normalised and de-duplicated by the settings loader; a
    role missing from the mapping counts as an empty list. An address on several lists is one
    person with several roles. A listed address with no user is created, an inactive one is
    reactivated, and every active user on no list is deactivated. Role rows are inserted and
    deleted so each person holds exactly the roles of the lists they are on.

    Every session of anyone who lost any role is deleted, so a removal logs them out everywhere;
    adding a role keeps their sessions (FR-005). Every session and code of every inactive user is
    deleted too, which also finishes any earlier partial run. `updated_at` changes only for people
    whose active flag or role set changed, so a second run writes nothing (FR-006, SC-007). Users
    are never deleted (FR-008).

    Commits once. If that fails with `IntegrityError` (another instance inserted the same new user
    or role at the same moment), the caller rolls back and calls this once more.
    """
    now = now or utc_now()
    desired: dict[str, set[Role]] = defaultdict(set)
    for role in Role:
        for email in role_lists.get(role, ()):
            desired[email].add(role)

    users = _all_users(session)
    created = 0
    for email in sorted(desired):
        if email not in users:
            users[email] = User(email=email, is_active=True, created_at=now, updated_at=now)
            session.add(users[email])
            created += 1
    session.flush()

    held = _roles_by_user(session)
    reactivated = deactivated = roles_added = roles_removed = unchanged = 0
    lost_a_role: set[int] = set()
    for email, user in users.items():
        assert user.id is not None
        wanted = desired.get(email, set())
        have = held.get(user.id, set())
        added, removed = wanted - have, have - wanted
        changed = bool(added or removed)
        if wanted and not user.is_active:
            user.is_active = True
            reactivated += 1
            changed = True
        elif not wanted and user.is_active:
            user.is_active = False
            deactivated += 1
            changed = True
        for role in sorted(added):
            session.add(UserRole(user_id=user.id, role=role, created_at=now))
        if removed:
            session.execute(
                delete(UserRole).where(
                    col(UserRole.user_id) == user.id, col(UserRole.role).in_(removed)
                )
            )
            lost_a_role.add(user.id)
        roles_added += len(added)
        roles_removed += len(removed)
        if changed:
            user.updated_at = now
            session.add(user)
        else:
            unchanged += 1
    session.flush()

    if lost_a_role:
        session.execute(delete(UserSession).where(col(UserSession.user_id).in_(lost_a_role)))
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
