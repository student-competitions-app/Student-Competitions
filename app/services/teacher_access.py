"""Teacher reach: which institutions, classes and students a teacher may see, and where they may
change anything.

See specs/009-classes-students-management/research.md D5 and contracts/services.md
§`app/services/teacher_access.py`. This module is the only authority for a teacher's scope
(Constitution IV, FR-021, FR-022):

- **reachable institution**: a `teacher_institutions` row for (teacher, institution), and the
  institution is available (it and its region are active);
- **reachable class**: any class, active or deactivated, of a reachable institution;
- **reachable student**: a person holding the student role whose enrolment's class is available
  and belongs to a reachable institution;
- **reachable team** (milestone 11.1): a live team (not deleted) of a reachable institution.

Anything else raises `NotReachable`, and a management action without Write raises
`WriteRequired`. Unknown and unreachable are deliberately indistinguishable: the routers turn both
errors into the same "Access denied" page, so nothing reveals whether an object exists.

From milestone 11 this module also decides the **Can manage competitions** setting
(`can_manage_competitions`), which every change to the question bank requires.

The class and student services call these checks **in their own transaction**, with `lock=True`
for writes: the link, the institution and the region are then read `FOR SHARE`, so an
administrator who lowers the level or deactivates the institution at the same moment either
commits first and is seen, or waits until the write commits (FR-022). Every function rolls back
before raising when it took a lock, so no lock outlives a refusal. On SQLite the locks render
nothing; SQLite already serialises writers.

Nothing here logs: the callers log their own change, with ids only.
"""

from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.models import (
    AccessLevel,
    Enrolment,
    Institution,
    Region,
    Role,
    SchoolClass,
    TeacherInstitution,
    TeacherProfile,
    Team,
    User,
)
from app.services.users import get_roles


class NotReachable(LookupError):
    """Unknown, not linked, unavailable, or not inside the parent named: the teacher may not
    reach it. Carries no detail on purpose."""


class WriteRequired(PermissionError):
    """The teacher reaches the institution with Read access only, and the action needs Write."""


@dataclass(frozen=True)
class ReachableInstitution:
    """A linked, available institution, as the Students tab shows it."""

    id: int
    name: str
    region_id: int
    region_name: str
    access_level: AccessLevel
    label: str
    """"Name — Read" or "Name — Write"."""

    @property
    def can_write(self) -> bool:
        return self.access_level == AccessLevel.WRITE


def _reachable(
    link: TeacherInstitution, institution: Institution, region: Region
) -> ReachableInstitution:
    assert institution.id is not None and region.id is not None
    level = AccessLevel(link.access_level)
    return ReachableInstitution(
        id=institution.id,
        name=institution.name,
        region_id=region.id,
        region_name=region.name,
        access_level=level,
        label=f"{institution.name} — {level.label}",
    )


def _refuse(session: Session, lock: bool, error: Exception) -> Exception:
    """`error`, after rolling back when a lock was taken, so no lock outlives the refusal."""
    if lock:
        session.rollback()
    return error


def can_manage_competitions(session: Session, teacher_id: int, *, lock: bool = False) -> bool:
    """Whether the teacher has **Can manage competitions**: the one authority for the setting
    (specs/011-question-bank/research.md R5, R7).

    True only if the teacher has a `teacher_profiles` row and its `can_manage_competitions` is
    true. No profile row means no setting; that covers the test cast's directly seeded teachers.
    With `lock`, the row is read `FOR SHARE` and refreshed, so an administrator removing the
    setting at the same moment either commits first and is seen, or waits. Never rolls back: the
    caller decides what a `False` means.
    """
    statement = select(TeacherProfile).where(TeacherProfile.user_id == teacher_id)
    if lock:
        statement = statement.with_for_update(read=True)
    statement = statement.execution_options(populate_existing=True)
    profile = session.exec(statement).first()
    return profile is not None and profile.can_manage_competitions


def list_reachable_institutions(session: Session, teacher_id: int) -> list[ReachableInstitution]:
    """The teacher's linked institutions that are available, sorted by region name, then
    institution name, ignoring case, ties by id. Sorted in Python, as everywhere else. Empty for
    a teacher with no links, which includes the test cast's directly seeded teachers."""
    statement = (
        select(TeacherInstitution, Institution, Region)
        .join(Institution, col(Institution.id) == col(TeacherInstitution.institution_id))
        .join(Region, col(Region.id) == col(Institution.region_id))
        .where(
            TeacherInstitution.user_id == teacher_id,
            col(Institution.is_active),
            col(Region.is_active),
        )
    )
    rows = session.exec(statement).all()
    rows = sorted(rows, key=lambda row: (row[2].name_key, row[1].name_key, row[1].id))
    return [_reachable(link, institution, region) for link, institution, region in rows]


def reachable_regions(institutions: list[ReachableInstitution]) -> list[tuple[int, str]]:
    """The distinct regions of `institutions`, as `(id, name)`, sorted by name ignoring case,
    ties by id."""
    regions = {item.region_id: item.region_name for item in institutions}
    return sorted(regions.items(), key=lambda region: (region[1].casefold(), region[0]))


def reach_institution(
    session: Session,
    teacher_id: int,
    institution_id: int,
    *,
    region_id: int | None = None,
    write: bool = False,
    lock: bool = False,
) -> ReachableInstitution:
    """The institution, if the teacher is linked to it, it is available, and it is in `region_id`
    when one is given; `NotReachable` otherwise. `WriteRequired` when `write` is set and the
    level is Read. With `lock`, the link, institution and region rows are read `FOR SHARE`."""
    statement = (
        select(TeacherInstitution, Institution, Region)
        .join(Institution, col(Institution.id) == col(TeacherInstitution.institution_id))
        .join(Region, col(Region.id) == col(Institution.region_id))
        .where(
            TeacherInstitution.user_id == teacher_id,
            TeacherInstitution.institution_id == institution_id,
        )
    )
    if lock:
        statement = statement.with_for_update(read=True)
    # Rows loaded earlier in this transaction are refreshed, so the check sees the current
    # level and statuses, not what an earlier read of the same request found.
    statement = statement.execution_options(populate_existing=True)
    row = session.exec(statement).first()
    if row is None:
        raise _refuse(session, lock, NotReachable())
    link, institution, region = row
    if not (institution.is_active and region.is_active):
        raise _refuse(session, lock, NotReachable())
    if region_id is not None and region.id != region_id:
        raise _refuse(session, lock, NotReachable())
    reachable = _reachable(link, institution, region)
    if write and not reachable.can_write:
        raise _refuse(session, lock, WriteRequired())
    return reachable


def _class_row(session: Session, class_id: int, lock: dict[str, bool] | bool | None) -> SchoolClass:
    if lock is None:
        found = session.get(SchoolClass, class_id)
    else:
        found = session.get(SchoolClass, class_id, with_for_update=lock, populate_existing=True)
    if found is None:
        raise NotReachable()
    return found


def reach_class(
    session: Session,
    teacher_id: int,
    class_id: int,
    *,
    institution_id: int | None = None,
    write: bool = False,
    lock: bool = False,
) -> tuple[ReachableInstitution, SchoolClass]:
    """The class, active or deactivated, of a reachable institution; `NotReachable` if it is
    unknown or not in `institution_id` when one is given. `WriteRequired` as for
    `reach_institution`. With `lock`, the class row is locked `FOR UPDATE` first, then the
    institution's rows `FOR SHARE`."""
    try:
        school_class = _class_row(session, class_id, True if lock else None)
    except NotReachable as missing:
        raise _refuse(session, lock, missing) from None
    if institution_id is not None and school_class.institution_id != institution_id:
        raise _refuse(session, lock, NotReachable())
    institution = reach_institution(
        session, teacher_id, school_class.institution_id, write=write, lock=lock
    )
    return institution, school_class


def reach_student(
    session: Session,
    teacher_id: int,
    user_id: int,
    *,
    write: bool = False,
    lock: bool = False,
) -> tuple[ReachableInstitution, SchoolClass, User]:
    """The person, if they hold the student role and are enrolled in an available class of a
    reachable institution; `NotReachable` otherwise. `WriteRequired` as for `reach_institution`.

    With `lock`, the user row is locked `FOR UPDATE` before anything else is read, then the
    enrolment's class `FOR SHARE` and the institution's rows `FOR SHARE`. The class takes a share
    lock, not `reach_class`'s update lock: two teachers changing two students of one class at the
    same moment must not deadlock, and a share lock already keeps the class from being
    deactivated or deleted until this transaction ends.
    """
    if lock:
        user = session.get(User, user_id, with_for_update=True, populate_existing=True)
    else:
        user = session.get(User, user_id)
    if user is None or Role.STUDENT not in get_roles(session, user_id):
        raise _refuse(session, lock, NotReachable())
    enrolment = session.get(Enrolment, user_id, populate_existing=lock)
    if enrolment is None:
        raise _refuse(session, lock, NotReachable())
    try:
        school_class = _class_row(session, enrolment.class_id, {"read": True} if lock else None)
    except NotReachable as missing:
        raise _refuse(session, lock, missing) from None
    if not school_class.is_active:
        raise _refuse(session, lock, NotReachable())
    institution = reach_institution(
        session, teacher_id, school_class.institution_id, write=write, lock=lock
    )
    return institution, school_class, user


def reach_team(
    session: Session,
    teacher_id: int,
    team_id: int,
    *,
    institution_id: int | None = None,
    write: bool = False,
    lock: bool = False,
) -> tuple[ReachableInstitution, Team]:
    """The live team, if its institution is reachable and, when given, is `institution_id`
    (specs/011.1-teacher-teams/research.md R4).

    `NotReachable` for an unknown team, a deleted team (`deleted_at` set), a team of another
    institution than `institution_id`, or an institution the teacher may not reach.
    `WriteRequired` when `write` is set and the level is Read.

    With `lock`, the team row is read `FOR UPDATE` (refreshed) first, then the link, institution
    and region `FOR SHARE` through `reach_institution`. That is the first lock of every team
    change (research R5). Rolls back before raising when it took a lock.
    """
    if lock:
        team = session.get(Team, team_id, with_for_update=True, populate_existing=True)
    else:
        team = session.get(Team, team_id)
    if team is None or team.deleted_at is not None:
        raise _refuse(session, lock, NotReachable())
    if institution_id is not None and team.institution_id != institution_id:
        raise _refuse(session, lock, NotReachable())
    institution = reach_institution(
        session, teacher_id, team.institution_id, write=write, lock=lock
    )
    return institution, team
