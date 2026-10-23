"""Students: the student's invitable-role definition, and listing, viewing, editing, deactivating
and removing students.

See specs/009-classes-students-management/contracts/services.md §`app/services/students.py` and
research D9, D12, D16. A student has two things, always written and deleted together
(`STUDENT_INVITATION.grant` and `.revoke`): the `student` role row and one `enrolments` row. The
student joins the milestone 8 flow as its second invitable role: invitation, acceptance, cut-offs,
erasure and data deletion work unchanged (FR-024).

Every function that acts for a teacher checks the teacher's reach through
`app.services.teacher_access`, in its own transaction, under lock for a change (research D5); the
routes are `@allow_roles(Role.TEACHER)`. Each change logs one line with ids only.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.models import (
    AccessLevel,
    Enrolment,
    Role,
    SchoolClass,
    TeacherInstitution,
    User,
    UserRole,
)
from app.schemas.students import StudentDetails
from app.schemas.teachers import MAX_ID
from app.services.availability import class_is_available, usable_roles
from app.services.classes import ClassView
from app.services.consent import set_cutoff
from app.services.institutions import describe_institutions
from app.services.invitations import DetailLine
from app.services.teacher_access import NotReachable, ReachableInstitution, reach_student
from app.services.users import end_all_sessions, get_roles, get_user_by_email

logger = logging.getLogger("uvicorn.error")

NOT_A_NEW_STUDENT = "This email already belongs to a student"
"""The invitation form's refusal (FR-026). It never names the institution or the class."""

CLASS_DEACTIVATED = "This class is deactivated."
"""A student edit that moves the student into a deactivated class of the same institution."""


class _StudentInvitation:
    """The student's `InvitableRole` (research D9). Its details are a `StudentDetails`."""

    role = Role.STUDENT

    def details_to_payload(self, details: StudentDetails) -> dict[str, Any]:
        return {"institution": details.institution_id, "class": details.class_id}

    def details_from_payload(self, raw: Any) -> StudentDetails:
        if not isinstance(raw, dict) or set(raw) != {"institution", "class"}:
            raise ValueError("not student details")
        institution_id, class_id = raw["institution"], raw["class"]
        for value in (institution_id, class_id):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError("not student details")
        return StudentDetails(institution_id=institution_id, class_id=class_id)

    def inviter_may_invite(self, session: Session, inviter: User, details: StudentDetails) -> bool:
        """An active teacher, not deactivated, with Write access to the institution (FR-032).
        Administrator status plays no part (US3-9)."""
        assert inviter.id is not None
        if not inviter.is_active or Role.TEACHER not in usable_roles(session, inviter.id):
            return False
        link = session.get(TeacherInstitution, (inviter.id, details.institution_id))
        return link is not None and link.access_level == AccessLevel.WRITE

    def details_acceptable(self, session: Session, details: StudentDetails, lock: bool) -> bool:
        """The class exists, still belongs to the institution, and is available (FR-032). With
        `lock`, the class, institution and region rows are read `FOR SHARE`, so a deletion or
        deactivation of any of them waits until the acceptance commits (FR-035)."""
        if not class_is_available(session, details.class_id, lock=lock):
            return False
        school_class = session.get(SchoolClass, details.class_id)
        return school_class is not None and school_class.institution_id == details.institution_id

    def describe(self, session: Session, details: StudentDetails) -> list[DetailLine]:
        """ "Educational institution: Name (Region)" and "Class: KN-21 · year 2", by current names
        (FR-031). A missing row gives no line, though the checks refuse such links first."""
        lines = []
        described = describe_institutions(session, [details.institution_id])
        if details.institution_id in described:
            label = described[details.institution_id].label
            lines.append(DetailLine(f"Educational institution: {label}"))
        school_class = session.get(SchoolClass, details.class_id)
        if school_class is not None:
            lines.append(DetailLine(f"Class: {ClassView.from_row(school_class).label}"))
        return lines

    def grant(self, session: Session, user: User, details: StudentDetails, now: datetime) -> None:
        assert user.id is not None
        session.add(UserRole(user_id=user.id, role=Role.STUDENT, created_at=now))
        session.add(
            Enrolment(user_id=user.id, class_id=details.class_id, created_at=now, updated_at=now)
        )
        session.flush()

    def revoke(self, session: Session, user_id: int) -> None:
        session.execute(delete(Enrolment).where(col(Enrolment.user_id) == user_id))
        session.execute(
            delete(UserRole).where(
                col(UserRole.user_id) == user_id, col(UserRole.role) == Role.STUDENT
            )
        )


STUDENT_INVITATION = _StudentInvitation()
"""Registered in `app.services.invitations.invitable_roles`."""


def is_student_address(session: Session, email: str) -> bool:
    """Whether someone with this (already normalised) address holds the student role, blocked or
    not (FR-026)."""
    user = get_user_by_email(session, email)
    return user is not None and user.id is not None and Role.STUDENT in get_roles(session, user.id)


# ---------------------------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StudentRow:
    user_id: int
    first_name: str
    last_name: str
    email: str
    class_id: int
    is_active: bool
    """The student's own status: `False` while a teacher has deactivated them."""


def _row(user: User, enrolment: Enrolment) -> StudentRow:
    assert user.id is not None
    return StudentRow(
        user_id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        email=user.email,
        class_id=enrolment.class_id,
        is_active=enrolment.is_active,
    )


def list_students(session: Session, class_id: int) -> list[StudentRow]:
    """The students enrolled in the class, sorted by last name, then first name, ignoring case,
    ties by id (FR-054). It checks no reach: the router lists only an active class of a reachable
    institution."""
    statement = (
        select(User, Enrolment)
        .join(Enrolment, col(Enrolment.user_id) == col(User.id))
        .where(Enrolment.class_id == class_id)
    )
    rows = [_row(user, enrolment) for user, enrolment in session.exec(statement)]
    return sorted(
        rows, key=lambda row: (row.last_name.casefold(), row.first_name.casefold(), row.user_id)
    )


class ClassNotActive(ValueError):
    """The target class of a move is deactivated, or no longer available; nothing was changed."""

    def __init__(self) -> None:
        super().__init__(CLASS_DEACTIVATED)
        self.message = CLASS_DEACTIVATED


def get_student(
    session: Session, teacher_id: int, user_id: int, *, write: bool = False
) -> tuple[ReachableInstitution, ClassView, StudentRow]:
    """The student, their class and institution, if the teacher reaches them; `NotReachable`
    otherwise, and `WriteRequired` when `write` is set and the level is Read (the student pages
    are management pages: contracts/http-routes.md §2.4)."""
    institution, school_class, user = reach_student(session, teacher_id, user_id, write=write)
    enrolment = session.get(Enrolment, user_id)
    assert enrolment is not None
    return institution, ClassView.from_row(school_class), _row(user, enrolment)


def _class_id(raw: str) -> int:
    """The submitted class id; anything that is not an id is a class out of reach."""
    value = raw.strip()
    if not value or not value.isascii() or not value.isdigit() or int(value) > MAX_ID:
        raise NotReachable()
    return int(value)


def update_student(
    session: Session,
    teacher_id: int,
    user_id: int,
    first_name: str,
    last_name: str,
    raw_class_id: str,
    now: datetime | None = None,
) -> int:
    """Save a teacher's edit of a student, writing only what changed, and return the student's
    class id after the save (FR-041, research D12).

    The names are already cleaned by the router. The student's row is locked and checked to be
    reachable with Write. The target class must be in the same institution (else `NotReachable`,
    as for an unknown class), and active and available (else `ClassNotActive`); it is read
    `FOR SHARE`, so it cannot be deactivated or deleted until the move commits. Sessions and
    cut-offs are never touched: the student stays signed in, and no new consent is asked (FR-010,
    FR-042).
    """
    now = now or utc_now()
    institution, current, user = reach_student(session, teacher_id, user_id, write=True, lock=True)
    try:
        target_id = _class_id(raw_class_id)
    except NotReachable:
        session.rollback()
        raise
    target = session.get(
        SchoolClass, target_id, with_for_update={"read": True}, populate_existing=True
    )
    if target is None or target.institution_id != institution.id:
        session.rollback()
        raise NotReachable()
    if not target.is_active or not class_is_available(session, target_id, lock=True):
        session.rollback()
        raise ClassNotActive()
    if (user.first_name, user.last_name) != (first_name, last_name):
        user.first_name = first_name
        user.last_name = last_name
        user.updated_at = now
        session.add(user)
    moved = target_id != current.id
    if moved:
        enrolment = session.get(Enrolment, user_id)
        assert enrolment is not None
        enrolment.class_id = target_id
        enrolment.updated_at = now
        session.add(enrolment)
    session.commit()
    logger.info("Student updated: user_id=%d moved=%s", user_id, moved)
    return target_id


def set_student_active(
    session: Session, teacher_id: int, user_id: int, active: bool, now: datetime | None = None
) -> None:
    """Activate or deactivate the student; already in that status, nothing changes.

    The student's row is locked and checked to be reachable with Write. Deactivating keeps the
    role and the enrolment, but the student is blocked (`app.services.availability`) and signed
    out everywhere in the same transaction, as when their class is deactivated.
    """
    now = now or utc_now()
    reach_student(session, teacher_id, user_id, write=True, lock=True)
    enrolment = session.get(Enrolment, user_id)
    assert enrolment is not None
    if enrolment.is_active == active:
        session.rollback()
        return
    enrolment.is_active = active
    enrolment.updated_at = now
    session.add(enrolment)
    if not active:
        end_all_sessions(session, user_id)
    session.commit()
    if active:
        logger.info("Student activated: user_id=%d", user_id)
    else:
        logger.info("Student deactivated: user_id=%d", user_id)


def remove_student(
    session: Session,
    settings: AuthSettings,
    teacher_id: int,
    user_id: int,
    now: datetime | None = None,
) -> None:
    """Take the student role and the enrolment away (FR-043), as `teachers.remove_teacher` does
    for a teacher.

    The cut-off for the person's address is raised, so no student invitation issued before now
    can be accepted (FR-030). The person is deactivated if no role is left, and signed out
    everywhere either way. The email, the names and the consent records stay until the person
    deletes their data.
    """
    now = now or utc_now()
    _, _, user = reach_student(session, teacher_id, user_id, write=True, lock=True)
    STUDENT_INVITATION.revoke(session, user_id)
    set_cutoff(session, settings.secret_key, user.email, Role.STUDENT, now)
    deactivated = not get_roles(session, user_id)
    if deactivated:
        user.is_active = False
    user.updated_at = now
    session.add(user)
    end_all_sessions(session, user_id)
    session.commit()
    logger.info("Student removed: user_id=%d deactivated=%s", user_id, deactivated)


# ---------------------------------------------------------------------------------------------
# The profile
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrolmentView:
    """A student's enrolment, as their profile shows it (FR-045)."""

    institution_label: str
    """"Name (Region)"."""
    class_name: str
    year_of_study: int
    is_available: bool
    """`False` while the class is not available: shown, marked "(deactivated)"."""
    is_active: bool
    """The student's own status: `False` while a teacher has deactivated them."""


def get_enrolment_view(session: Session, user_id: int) -> EnrolmentView | None:
    """The person's enrolment by current names, blocked or not; `None` when there is none."""
    enrolment = session.get(Enrolment, user_id)
    if enrolment is None:
        return None
    school_class = session.get(SchoolClass, enrolment.class_id)
    assert school_class is not None
    described = describe_institutions(session, [school_class.institution_id])
    return EnrolmentView(
        institution_label=described[school_class.institution_id].label,
        class_name=school_class.name,
        year_of_study=school_class.year_of_study,
        is_available=class_is_available(session, school_class.id or 0),
        is_active=enrolment.is_active,
    )
