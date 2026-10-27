"""Teacher reach: what a teacher may reach, and at which level.

See specs/009-classes-students-management/research.md D5 and contracts/services.md
§`app/services/teacher_access.py`. The teacher is real (invited and accepted): Write to "Kyiv
Polytechnic Institute" in Kyiv, Read to "Lviv Academy" in Lviv, and no link to "Odesa College".
Classes and enrolments are seeded directly. Every case runs on both engines.
"""

from dataclasses import dataclass

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.models import AccessLevel, Enrolment, Institution, Region, Role, SchoolClass, User
from app.services.teacher_access import (
    NotReachable,
    ReachableInstitution,
    WriteRequired,
    can_manage_competitions,
    list_reachable_institutions,
    reach_class,
    reach_institution,
    reach_student,
    reachable_regions,
)
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    TEACHER_EMAIL,
    make_class,
    make_institution,
    make_teacher,
    seed_roles_directly,
)


@dataclass(frozen=True)
class Scene:
    teacher: int
    a: int
    b: int
    c: int
    kyiv: int
    lviv: int


@pytest.fixture
def scene(engine: Engine, auth_settings: AuthSettings) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    a = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    b = make_institution(engine, "Lviv Academy", "Lviv")
    c = make_institution(engine, "Odesa College", "Odesa")
    teacher = make_teacher(
        engine,
        auth_settings,
        email="olena@example.org",
        institutions={a: AccessLevel.WRITE, b: AccessLevel.READ},
    )
    with Session(engine) as session:
        regions = {r.name: r.id for r in session.exec(select(Region))}
    kyiv, lviv = regions["Kyiv"], regions["Lviv"]
    assert kyiv is not None and lviv is not None
    return Scene(teacher=teacher, a=a, b=b, c=c, kyiv=kyiv, lviv=lviv)


def deactivate(engine: Engine, model: type, row_id: int) -> None:
    with Session(engine) as session:
        row = session.get(model, row_id)
        assert row is not None
        row.is_active = False
        session.add(row)
        session.commit()


def enrolled_student(engine: Engine, email: str, class_id: int) -> int:
    seed_roles_directly(engine, {email: [Role.STUDENT]})
    now = utc_now()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.id is not None
        session.add(Enrolment(user_id=user.id, class_id=class_id, created_at=now, updated_at=now))
        session.commit()
        return user.id


# ---------------------------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------------------------


def test_the_linked_available_institutions_are_listed_with_their_levels(
    engine: Engine, scene: Scene
) -> None:
    with Session(engine) as session:
        found = list_reachable_institutions(session, scene.teacher)
    assert [(item.id, item.label, item.can_write) for item in found] == [
        (scene.a, "Kyiv Polytechnic Institute — Write", True),
        (scene.b, "Lviv Academy — Read", False),
    ]
    assert reachable_regions(found) == [(scene.kyiv, "Kyiv"), (scene.lviv, "Lviv")]


@pytest.mark.parametrize("target", ["institution", "region"])
def test_an_unavailable_institution_is_not_listed(
    engine: Engine, scene: Scene, target: str
) -> None:
    if target == "institution":
        deactivate(engine, Institution, scene.a)
    else:
        deactivate(engine, Region, scene.kyiv)
    with Session(engine) as session:
        found = list_reachable_institutions(session, scene.teacher)
    assert [item.id for item in found] == [scene.b]


def test_a_teacher_with_no_links_reaches_nothing(engine: Engine, scene: Scene) -> None:
    seed_roles_directly(engine, {"cast.teacher@example.org": [Role.TEACHER]})
    with Session(engine) as session:
        cast = session.exec(select(User).where(User.email == "cast.teacher@example.org")).one()
        assert cast.id is not None
        assert list_reachable_institutions(session, cast.id) == []
        with pytest.raises(NotReachable):
            reach_institution(session, cast.id, scene.a)


def test_regions_are_sorted_ignoring_case_and_distinct() -> None:
    def item(institution_id: int, region_id: int, region: str) -> ReachableInstitution:
        return ReachableInstitution(
            institution_id, "X", region_id, region, AccessLevel.READ, "X — Read"
        )

    found = [item(1, 2, "lviv"), item(2, 1, "Kyiv"), item(3, 2, "lviv"), item(4, 3, "Київ")]
    assert reachable_regions(found) == [(1, "Kyiv"), (2, "lviv"), (3, "Київ")]


# ---------------------------------------------------------------------------------------------
# Institutions
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("lock", [False, True])
def test_write_and_read_institutions_are_reached_at_their_level(
    engine: Engine, scene: Scene, lock: bool
) -> None:
    with Session(engine) as session:
        found = reach_institution(
            session, scene.teacher, scene.a, region_id=scene.kyiv, write=True, lock=lock
        )
        assert found.id == scene.a and found.can_write
        assert reach_institution(session, scene.teacher, scene.b, lock=lock).id == scene.b
        with pytest.raises(WriteRequired):
            reach_institution(session, scene.teacher, scene.b, write=True, lock=lock)


@pytest.mark.parametrize("lock", [False, True])
def test_unlinked_unknown_and_misplaced_institutions_are_not_reached(
    engine: Engine, scene: Scene, lock: bool
) -> None:
    with Session(engine) as session:
        for institution_id, region_id in (
            (scene.c, None),
            (scene.c + 1000, None),
            (scene.a, scene.lviv),
        ):
            with pytest.raises(NotReachable):
                reach_institution(
                    session, scene.teacher, institution_id, region_id=region_id, lock=lock
                )


def test_a_deactivated_institution_is_not_reached(engine: Engine, scene: Scene) -> None:
    deactivate(engine, Institution, scene.a)
    with Session(engine) as session, pytest.raises(NotReachable):
        reach_institution(session, scene.teacher, scene.a)


# ---------------------------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("lock", [False, True])
def test_any_class_of_a_reachable_institution_is_reached(
    engine: Engine, scene: Scene, lock: bool
) -> None:
    """Research D5: a deactivated class too, so it can be activated again."""
    closed = make_class(engine, scene.a, "KN-11", 1, active=False)
    with Session(engine) as session:
        institution, school_class = reach_class(
            session, scene.teacher, closed, institution_id=scene.a, write=True, lock=lock
        )
    assert institution.id == scene.a
    assert school_class.id == closed and not school_class.is_active


@pytest.mark.parametrize("lock", [False, True])
def test_classes_out_of_reach_are_refused(engine: Engine, scene: Scene, lock: bool) -> None:
    of_a = make_class(engine, scene.a, "KN-21")
    of_b = make_class(engine, scene.b, "LA-1")
    of_c = make_class(engine, scene.c, "OC-1")
    with Session(engine) as session:
        with pytest.raises(NotReachable):
            reach_class(session, scene.teacher, of_c, lock=lock)
        with pytest.raises(NotReachable):
            reach_class(session, scene.teacher, of_c + 1000, lock=lock)
        with pytest.raises(NotReachable):
            reach_class(session, scene.teacher, of_a, institution_id=scene.b, lock=lock)
        with pytest.raises(WriteRequired):
            reach_class(session, scene.teacher, of_b, write=True, lock=lock)
        assert reach_class(session, scene.teacher, of_b, lock=lock)[1].id == of_b


# ---------------------------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("lock", [False, True])
def test_a_student_of_an_available_class_is_reached(
    engine: Engine, scene: Scene, lock: bool
) -> None:
    school_class = make_class(engine, scene.a, "KN-21")
    student = enrolled_student(engine, "taras@example.org", school_class)
    with Session(engine) as session:
        institution, found_class, user = reach_student(
            session, scene.teacher, student, write=True, lock=lock
        )
    assert (institution.id, found_class.id, user.id) == (scene.a, school_class, student)


def test_students_out_of_reach_are_refused(engine: Engine, scene: Scene) -> None:
    closed = make_class(engine, scene.a, "KN-11", active=False)
    blocked = enrolled_student(engine, "blocked@example.org", closed)
    of_c = enrolled_student(engine, "odesa@example.org", make_class(engine, scene.c, "OC-1"))
    of_b = enrolled_student(engine, "lviv@example.org", make_class(engine, scene.b, "LA-1"))
    seed_roles_directly(engine, {"not.student@example.org": [Role.TEACHER]})
    with Session(engine) as session:
        teacher_only = session.exec(
            select(User).where(User.email == "not.student@example.org")
        ).one()
        assert teacher_only.id is not None
        for user_id in (blocked, of_c, teacher_only.id, of_c + 1000):
            for lock in (False, True):
                with pytest.raises(NotReachable):
                    reach_student(session, scene.teacher, user_id, lock=lock)
        with pytest.raises(WriteRequired):
            reach_student(session, scene.teacher, of_b, write=True, lock=True)
        assert reach_student(session, scene.teacher, of_b)[2].id == of_b


def test_a_student_role_without_an_enrolment_is_not_reached(engine: Engine, scene: Scene) -> None:
    """The test cast's seeded students belong to no class, so no teacher reaches them."""
    seed_roles_directly(engine, {"cast.student@example.org": [Role.STUDENT]})
    with Session(engine) as session:
        cast = session.exec(select(User).where(User.email == "cast.student@example.org")).one()
        assert cast.id is not None
        with pytest.raises(NotReachable):
            reach_student(session, scene.teacher, cast.id)


def test_a_refusal_under_lock_rolls_back(engine: Engine, scene: Scene) -> None:
    """No lock outlives a refusal: the session holds nothing pending afterwards."""
    school_class = make_class(engine, scene.b, "LA-1")
    with Session(engine) as session:
        row = session.get(SchoolClass, school_class)
        assert row is not None
        row.name = "changed, never committed"
        session.add(row)
        with pytest.raises(WriteRequired):
            reach_class(session, scene.teacher, school_class, write=True, lock=True)
        assert not session.dirty
    with Session(engine) as session:
        stored = session.get(SchoolClass, school_class)
        assert stored is not None and stored.name == "LA-1"


# ---------------------------------------------------------------------------------------------
# Milestone 11: Can manage competitions (specs/011-question-bank/research.md R5)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("lock", [False, True], ids=["plain", "locked"])
def test_the_setting_is_read_from_the_profile(
    engine: Engine, auth_settings: AuthSettings, scene: Scene, lock: bool
) -> None:
    manager = make_teacher(
        engine,
        auth_settings,
        email="manager@example.org",
        institutions={scene.a: AccessLevel.READ},
        can_manage=True,
    )
    with Session(engine) as session:
        assert can_manage_competitions(session, manager, lock=lock) is True
        assert can_manage_competitions(session, scene.teacher, lock=lock) is False


@pytest.mark.parametrize("lock", [False, True], ids=["plain", "locked"])
def test_no_profile_means_no_setting(engine: Engine, scene: Scene, lock: bool) -> None:
    """The test cast's seeded teachers hold the role but have no profile row."""
    seed_roles_directly(engine, {TEACHER_EMAIL: [Role.TEACHER]})
    with Session(engine) as session:
        cast = session.exec(select(User).where(User.email == TEACHER_EMAIL)).one()
        assert cast.id is not None
        assert can_manage_competitions(session, cast.id, lock=lock) is False
        assert can_manage_competitions(session, 999_999, lock=lock) is False
