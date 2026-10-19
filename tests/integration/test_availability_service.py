"""The chain rule, usable roles and signing out the students below an object.

See specs/009-classes-students-management/research.md D2–D4 and contracts/services.md
§`app/services/availability.py`. The rows are seeded directly through the models (test-only):
these tests are about the rule, not about how students arrive. Every case runs on both engines.
"""

from dataclasses import dataclass

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.core.db import utc_now
from app.models import Enrolment, Institution, Region, Role, SchoolClass, User, UserSession
from app.services.availability import (
    class_is_available,
    get_signable_user_by_email,
    is_student_blocked,
    sign_out_students_below,
    usable_roles,
)
from app.services.sessions import create_session, get_session_identity
from tests.conftest import make_class, make_institution, seed_roles_directly

STUDENT = "taras@example.org"
BOTH = "olena@example.org"
ELSEWHERE = "ivan@example.org"
TEACHER = "petro@example.org"


@dataclass(frozen=True)
class World:
    region: int
    institution: int
    school_class: int
    other_region: int
    other_institution: int
    other_class: int
    users: dict[str, int]


def user_id(engine: Engine, email: str) -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.id is not None
        return user.id


def enrol(engine: Engine, user: int, class_id: int) -> None:
    now = utc_now()
    with Session(engine) as session:
        session.add(Enrolment(user_id=user, class_id=class_id, created_at=now, updated_at=now))
        session.commit()


def set_active(engine: Engine, model: type, row_id: int, active: bool) -> None:
    with Session(engine) as session:
        row = session.get(model, row_id)
        assert row is not None
        row.is_active = active
        session.add(row)
        session.commit()


@pytest.fixture
def world(engine: Engine) -> World:
    """KN-21 of Kyiv Polytechnic in Kyiv holds a student and a teacher-and-student; KN-31 of Lviv
    Academy in Lviv holds another student; a teacher holds no enrolment."""
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    other_institution = make_institution(engine, "Lviv Academy", "Lviv")
    with Session(engine) as session:
        regions = {region.name: region.id for region in session.exec(select(Region))}
    school_class = make_class(engine, institution, "KN-21")
    other_class = make_class(engine, other_institution, "KN-31")
    seed_roles_directly(
        engine,
        {
            STUDENT: [Role.STUDENT],
            BOTH: [Role.TEACHER, Role.STUDENT],
            ELSEWHERE: [Role.STUDENT],
            TEACHER: [Role.TEACHER],
        },
    )
    users = {email: user_id(engine, email) for email in (STUDENT, BOTH, ELSEWHERE, TEACHER)}
    enrol(engine, users[STUDENT], school_class)
    enrol(engine, users[BOTH], school_class)
    enrol(engine, users[ELSEWHERE], other_class)
    assert regions["Kyiv"] is not None and regions["Lviv"] is not None
    return World(
        region=regions["Kyiv"],
        institution=institution,
        school_class=school_class,
        other_region=regions["Lviv"],
        other_institution=other_institution,
        other_class=other_class,
        users=users,
    )


LEVELS = [("class", SchoolClass), ("institution", Institution), ("region", Region)]


def level_id(world: World, level: str) -> int:
    return {"class": world.school_class, "institution": world.institution, "region": world.region}[
        level
    ]


def test_nobody_is_blocked_while_the_chain_is_active(engine: Engine, world: World) -> None:
    with Session(engine) as session:
        for user in world.users.values():
            assert not is_student_blocked(session, user)
        assert class_is_available(session, world.school_class)
        assert class_is_available(session, world.school_class, lock=True)


@pytest.mark.parametrize(("level", "model"), LEVELS, ids=[level for level, _ in LEVELS])
def test_each_level_blocks_the_students_below_it(
    engine: Engine, world: World, level: str, model: type
) -> None:
    """FR-011, FR-015: the class, its institution or its region deactivated."""
    set_active(engine, model, level_id(world, level), False)
    with Session(engine) as session:
        assert is_student_blocked(session, world.users[STUDENT])
        assert is_student_blocked(session, world.users[BOTH])
        assert not is_student_blocked(session, world.users[ELSEWHERE])
        assert not class_is_available(session, world.school_class)
        assert class_is_available(session, world.other_class)
    set_active(engine, model, level_id(world, level), True)
    with Session(engine) as session:
        assert not is_student_blocked(session, world.users[STUDENT])


def test_a_person_with_no_enrolment_is_never_blocked(engine: Engine, world: World) -> None:
    """Research D2: the test cast's directly seeded student roles stay usable."""
    set_active(engine, Region, world.region, False)
    seed_roles_directly(engine, {"cast.student@example.org": [Role.STUDENT]})
    with Session(engine) as session:
        cast = user_id(engine, "cast.student@example.org")
        assert not is_student_blocked(session, cast)
        assert not is_student_blocked(session, world.users[TEACHER])
        assert usable_roles(session, cast) == (Role.STUDENT,)


def test_an_unknown_class_is_not_available(engine: Engine, world: World) -> None:
    with Session(engine) as session:
        assert not class_is_available(session, world.other_class + 1000)


def test_usable_roles_drop_only_the_student_role(engine: Engine, world: World) -> None:
    """Research D3."""
    with Session(engine) as session:
        assert usable_roles(session, world.users[BOTH]) == (Role.TEACHER, Role.STUDENT)
    set_active(engine, SchoolClass, world.school_class, False)
    with Session(engine) as session:
        assert usable_roles(session, world.users[BOTH]) == (Role.TEACHER,)
        assert usable_roles(session, world.users[STUDENT]) == ()
        assert usable_roles(session, world.users[ELSEWHERE]) == (Role.STUDENT,)


def test_a_blocked_student_with_no_other_role_cannot_sign_in(engine: Engine, world: World) -> None:
    """US5-2: sign-in finds an unknown address; a teacher-and-student is still found."""
    set_active(engine, Institution, world.institution, False)
    with Session(engine) as session:
        assert get_signable_user_by_email(session, STUDENT) is None
        found = get_signable_user_by_email(session, BOTH)
        assert found is not None and found.id == world.users[BOTH]
        assert get_signable_user_by_email(session, ELSEWHERE) is not None
        assert get_signable_user_by_email(session, "nobody@example.org") is None


def sessions_of(engine: Engine) -> dict[int, int]:
    with Session(engine) as session:
        counts: dict[int, int] = {}
        for row in session.exec(select(UserSession)):
            counts[row.user_id] = counts.get(row.user_id, 0) + 1
        return counts


def sign_in_everyone(engine: Engine, world: World) -> None:
    """Two browsers each."""
    with Session(engine) as session:
        for user_id_ in world.users.values():
            user = session.get(User, user_id_)
            assert user is not None
            for _ in range(2):
                create_session(session, user, None)


@pytest.mark.parametrize("level", ["class", "institution", "region"])
def test_signing_out_below_an_object_deletes_exactly_its_students_sessions(
    engine: Engine, world: World, level: str
) -> None:
    """Research D4: every session of everyone enrolled below, other roles included; nobody
    else's. Not committed by the function."""
    sign_in_everyone(engine, world)
    with Session(engine) as session:
        deleted = sign_out_students_below(session, **{f"{level}_id": level_id(world, level)})
        session.commit()
    assert deleted == 4
    remaining = sessions_of(engine)
    assert world.users[STUDENT] not in remaining
    assert world.users[BOTH] not in remaining
    assert remaining == {world.users[ELSEWHERE]: 2, world.users[TEACHER]: 2}


def test_signing_out_is_rolled_back_with_its_transaction(engine: Engine, world: World) -> None:
    sign_in_everyone(engine, world)
    with Session(engine) as session:
        sign_out_students_below(session, class_id=world.school_class)
        session.rollback()
    assert len(sessions_of(engine)) == 4


def test_signing_out_needs_exactly_one_object(engine: Engine, world: World) -> None:
    with Session(engine) as session, pytest.raises(AssertionError):
        sign_out_students_below(session)
    with Session(engine) as session, pytest.raises(AssertionError):
        sign_out_students_below(
            session, class_id=world.school_class, institution_id=world.institution
        )


def test_a_blocked_students_session_resolves_to_nobody_and_is_deleted(
    engine: Engine, world: World
) -> None:
    """Research D3: the student role is no longer held, so the session goes."""
    with Session(engine) as session:
        user = session.get(User, world.users[STUDENT])
        assert user is not None
        token = create_session(session, user, Role.STUDENT)
    set_active(engine, SchoolClass, world.school_class, False)
    with Session(engine) as session:
        assert get_session_identity(session, token) is None
    assert world.users[STUDENT] not in sessions_of(engine)


def test_a_blocked_teacher_and_students_teacher_session_is_kept(
    engine: Engine, world: World
) -> None:
    """FR-015: not offered the student role, but still a teacher; a student-role session of the
    same person goes, and an undecided one settles on the teacher role."""
    with Session(engine) as session:
        user = session.get(User, world.users[BOTH])
        assert user is not None
        as_teacher = create_session(session, user, Role.TEACHER)
        as_student = create_session(session, user, Role.STUDENT)
        undecided = create_session(session, user, None)
    set_active(engine, Region, world.region, False)
    with Session(engine) as session:
        identity = get_session_identity(session, as_teacher)
        assert identity is not None
        assert identity.roles == (Role.TEACHER,)
        assert identity.current_role == Role.TEACHER
        assert get_session_identity(session, as_student) is None
        settled = get_session_identity(session, undecided)
        assert settled is not None and settled.current_role == Role.TEACHER
    assert sessions_of(engine) == {world.users[BOTH]: 2}
