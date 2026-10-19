"""The deactivation chain: which classes are available, which students are blocked, and what that
means for sign-in and sessions.

See specs/009-classes-students-management/research.md D2–D4 and contracts/services.md
§`app/services/availability.py`. This module is the one place that decides the chain rule
(FR-011–FR-016):

- a class is **available** ⇔ the class, its institution and its region are all active;
- a student is **blocked** ⇔ they have an enrolment whose class is not available.

Statuses are never cascaded: deactivating an object writes only its own `is_active`, so activating
it again gives back exactly the statuses below it (FR-012, FR-017). The rule is computed on every
read and can never drift from the statuses it is computed from.

**Usable roles** are the roles held, without the student role while the person is blocked. They
replace the roles held in session lookup, at the start of a session, and at sign-in (research
D3); everything about *holding* a role keeps using `users.get_roles`.

A student role **without** an enrolment counts as usable. In the application that state cannot
occur, because the role and the enrolment are granted and revoked together; it exists only for the
test cast, whose student roles are seeded directly (research D2).

Imports only `app.models` and `app.services.users`, so `regions` and `institutions` can call it
without a cycle (research D4). Nothing here logs: the callers log their own change.
"""

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.models import Enrolment, Institution, Region, Role, SchoolClass, User, UserSession
from app.services.users import get_active_user_by_email, get_roles


def is_student_blocked(session: Session, user_id: int) -> bool:
    """Whether the person has an enrolment whose class, institution or region is inactive. One
    query; `False` for a person with no enrolment."""
    statement = (
        select(SchoolClass.is_active, Institution.is_active, Region.is_active)
        .select_from(Enrolment)
        .join(SchoolClass, col(SchoolClass.id) == col(Enrolment.class_id))
        .join(Institution, col(Institution.id) == col(SchoolClass.institution_id))
        .join(Region, col(Region.id) == col(Institution.region_id))
        .where(Enrolment.user_id == user_id)
    )
    row = session.exec(statement).first()
    return row is not None and not all(row)


def usable_roles(session: Session, user_id: int) -> tuple[Role, ...]:
    """The roles held, in the fixed order, without the student role while the person is blocked
    (research D3)."""
    roles = get_roles(session, user_id)
    if Role.STUDENT in roles and is_student_blocked(session, user_id):
        return tuple(role for role in roles if role != Role.STUDENT)
    return roles


def get_signable_user_by_email(session: Session, email: str) -> User | None:
    """The active user with this (already normalised) address who has at least one usable role.
    Used only by sign-in: a blocked student with no other role is an unknown address (US5-2)."""
    user = get_active_user_by_email(session, email)
    if user is None or user.id is None or not usable_roles(session, user.id):
        return None
    return user


def class_is_available(session: Session, class_id: int, lock: bool = False) -> bool:
    """Whether the class exists and it, its institution and its region are all active.

    With `lock`, the three rows are read `FOR SHARE` for the rest of the transaction, so a
    concurrent deactivation or deletion of any of them waits until this transaction ends (FR-035).
    On SQLite the lock renders nothing; SQLite already serialises writers.
    """
    statement = (
        select(SchoolClass.is_active, Institution.is_active, Region.is_active)
        .select_from(SchoolClass)
        .join(Institution, col(Institution.id) == col(SchoolClass.institution_id))
        .join(Region, col(Region.id) == col(Institution.region_id))
        .where(SchoolClass.id == class_id)
    )
    if lock:
        statement = statement.with_for_update(read=True)
    row = session.exec(statement).first()
    return row is not None and all(row)


def sign_out_students_below(
    session: Session,
    *,
    region_id: int | None = None,
    institution_id: int | None = None,
    class_id: int | None = None,
) -> int:
    """Delete every session of every person enrolled in a class below the one object named, and
    return how many were deleted (research D4). Exactly one keyword must be given.

    Everyone enrolled there is signed out, including people who also hold another role, as on a
    role removal (milestone 5). Does not commit: the caller runs it in the transaction of the
    status change.
    """
    given = [value for value in (region_id, institution_id, class_id) if value is not None]
    assert len(given) == 1, "name exactly one of region_id, institution_id, class_id"
    enrolled = select(Enrolment.user_id).join(
        SchoolClass, col(SchoolClass.id) == col(Enrolment.class_id)
    )
    if class_id is not None:
        enrolled = enrolled.where(SchoolClass.id == class_id)
    elif institution_id is not None:
        enrolled = enrolled.where(SchoolClass.institution_id == institution_id)
    else:
        enrolled = enrolled.join(
            Institution, col(Institution.id) == col(SchoolClass.institution_id)
        ).where(Institution.region_id == region_id)
    result = session.execute(delete(UserSession).where(col(UserSession.user_id).in_(enrolled)))
    return result.rowcount
