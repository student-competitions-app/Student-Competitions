"""Class operations: create, edit, deactivate, activate and delete, each checked against the
teacher's reach.

See specs/009-classes-students-management/contracts/services.md §`app/services/classes.py` and
research D8. The teacher is real: Write to "Kyiv Polytechnic Institute" and "Kyiv Lyceum", Read to
"Lviv Academy", no link to "Odesa College". Enrolments and sessions are seeded directly. Every case
runs on both engines.
"""

from dataclasses import dataclass

import pytest
from sqlalchemy import Engine, func
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.models import AccessLevel, Enrolment, Role, SchoolClass, User, UserSession
from app.schemas.classes import INVALID_YEAR, InvalidYear
from app.schemas.names import InvalidName
from app.services.classes import (
    ClassInUse,
    DuplicateClassName,
    count_institution_classes,
    create_class,
    delete_class,
    list_classes,
    set_class_active,
    update_class,
)
from app.services.sessions import create_session
from app.services.teacher_access import NotReachable, WriteRequired
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    make_class,
    make_institution,
    make_teacher,
    seed_roles_directly,
)


@dataclass(frozen=True)
class Scene:
    teacher: int
    a: int
    a2: int
    b: int
    c: int


@pytest.fixture
def scene(engine: Engine, auth_settings: AuthSettings) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    a = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    a2 = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    b = make_institution(engine, "Lviv Academy", "Lviv")
    c = make_institution(engine, "Odesa College", "Odesa")
    teacher = make_teacher(
        engine,
        auth_settings,
        email="olena@example.org",
        institutions={a: AccessLevel.WRITE, a2: AccessLevel.WRITE, b: AccessLevel.READ},
    )
    return Scene(teacher=teacher, a=a, a2=a2, b=b, c=c)


def classes_of(engine: Engine, institution_id: int) -> list[tuple[str, int, bool]]:
    with Session(engine) as session:
        return [
            (c.name, c.year_of_study, c.is_active) for c in list_classes(session, institution_id)
        ]


def stored(engine: Engine, class_id: int) -> SchoolClass | None:
    with Session(engine) as session:
        return session.get(SchoolClass, class_id)


def enrolled(engine: Engine, email: str, class_id: int) -> int:
    seed_roles_directly(engine, {email: [Role.STUDENT]})
    now = utc_now()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.id is not None
        session.add(Enrolment(user_id=user.id, class_id=class_id, created_at=now, updated_at=now))
        session.commit()
        create_session(session, user, Role.STUDENT)
        return user.id


# ---------------------------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------------------------


def test_a_class_is_created_trimmed_and_active(engine: Engine, scene: Scene) -> None:
    with Session(engine) as session:
        view = create_class(session, scene.teacher, scene.a, "  KN-21  ", " 2 ")
    assert (view.name, view.year_of_study, view.is_active, view.label) == (
        "KN-21",
        2,
        True,
        "KN-21 · year 2",
    )
    assert classes_of(engine, scene.a) == [("KN-21", 2, True)]


def test_the_same_name_is_accepted_in_another_institution(engine: Engine, scene: Scene) -> None:
    """US1-8."""
    with Session(engine) as session:
        create_class(session, scene.teacher, scene.a, "KN-21", "2")
        create_class(session, scene.teacher, scene.a2, "KN-21", "3")
    assert classes_of(engine, scene.a2) == [("KN-21", 3, True)]


@pytest.mark.parametrize(
    ("existing", "submitted", "active"),
    [("KN-21", "kn-21", True), ("KN-21", "KN-21", False), ("Клас", "КЛАС", True)],
    ids=["case", "deactivated", "cyrillic"],
)
def test_a_duplicate_in_the_institution_is_refused_naming_the_stored_class(
    engine: Engine, scene: Scene, existing: str, submitted: str, active: bool
) -> None:
    """FR-002: ignoring case, in any alphabet, deactivated classes included."""
    make_class(engine, scene.a, existing, active=active)
    with Session(engine) as session, pytest.raises(DuplicateClassName) as refused:
        create_class(session, scene.teacher, scene.a, submitted, "2")
    assert (
        refused.value.message == f"A class named “{existing}” already exists in this institution."
    )
    assert len(classes_of(engine, scene.a)) == 1


@pytest.mark.parametrize(
    ("name", "year", "error"),
    [
        ("", "2", InvalidName),
        ("x" * 201, "2", InvalidName),
        ("KN\t21", "2", InvalidName),
        ("KN-21", "0", InvalidYear),
        ("KN-21", "13", InvalidYear),
        ("KN-21", "2.5", InvalidYear),
        ("KN-21", "", InvalidYear),
    ],
)
def test_invalid_names_and_years_store_nothing(
    engine: Engine, scene: Scene, name: str, year: str, error: type[Exception]
) -> None:
    with Session(engine) as session, pytest.raises(error):
        create_class(session, scene.teacher, scene.a, name, year)
    assert classes_of(engine, scene.a) == []


def test_the_year_message() -> None:
    assert InvalidYear().message == INVALID_YEAR


# ---------------------------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------------------------


def test_the_name_and_year_change_and_a_case_change_is_a_rename(
    engine: Engine, scene: Scene
) -> None:
    """US1-9, FR-002."""
    class_id = make_class(engine, scene.a, "KN-21", 2)
    with Session(engine) as session:
        update_class(session, scene.teacher, class_id, "KN-22", "3")
        view = update_class(session, scene.teacher, class_id, "kn-22", "3")
    assert view.name == "kn-22"
    assert classes_of(engine, scene.a) == [("kn-22", 3, True)]


def test_another_class_name_is_a_duplicate_on_update(engine: Engine, scene: Scene) -> None:
    make_class(engine, scene.a, "KN-21")
    class_id = make_class(engine, scene.a, "KN-22")
    with Session(engine) as session, pytest.raises(DuplicateClassName):
        update_class(session, scene.teacher, class_id, "KN-21", "2")
    found = stored(engine, class_id)
    assert found is not None and found.name == "KN-22"


def test_an_unchanged_form_writes_nothing(engine: Engine, scene: Scene) -> None:
    class_id = make_class(engine, scene.a, "KN-21", 2)
    before = stored(engine, class_id)
    with Session(engine) as session:
        update_class(session, scene.teacher, class_id, " KN-21 ", "02")
    after = stored(engine, class_id)
    assert before is not None and after is not None
    assert after.updated_at == before.updated_at


def test_a_year_change_is_every_students_year(engine: Engine, scene: Scene) -> None:
    """Spec Edge Cases: the year is read from the class."""
    class_id = make_class(engine, scene.a, "KN-21", 2)
    student = enrolled(engine, "taras@example.org", class_id)
    with Session(engine) as session:
        update_class(session, scene.teacher, class_id, "KN-21", "3")
    with Session(engine) as session:
        year = session.exec(
            select(SchoolClass.year_of_study)
            .join(Enrolment, Enrolment.class_id == SchoolClass.id)
            .where(Enrolment.user_id == student)
        ).one()
    assert year == 3


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------


def session_owners(engine: Engine) -> set[int]:
    with Session(engine) as session:
        return set(session.exec(select(UserSession.user_id)))


def test_deactivating_signs_out_the_class_students_only(engine: Engine, scene: Scene) -> None:
    """FR-015, research D4: and a second call changes nothing."""
    class_id = make_class(engine, scene.a, "KN-21")
    other = make_class(engine, scene.a, "KN-22")
    taras = enrolled(engine, "taras@example.org", class_id)
    ivan = enrolled(engine, "ivan@example.org", other)
    with Session(engine) as session:
        teacher = session.get(User, scene.teacher)
        assert teacher is not None
        create_session(session, teacher, Role.TEACHER)
    with Session(engine) as session:
        view = set_class_active(session, scene.teacher, class_id, False)
    assert not view.is_active
    assert session_owners(engine) == {ivan, scene.teacher}
    first = stored(engine, class_id)
    with Session(engine) as session:
        set_class_active(session, scene.teacher, class_id, False)
    second = stored(engine, class_id)
    assert first is not None and second is not None
    assert second.updated_at == first.updated_at
    with Session(engine) as session:
        enrolment = session.get(Enrolment, taras)
        assert enrolment is not None and enrolment.class_id == class_id


def test_activating_writes_only_the_status(engine: Engine, scene: Scene) -> None:
    class_id = make_class(engine, scene.a, "KN-21", active=False)
    with Session(engine) as session:
        assert set_class_active(session, scene.teacher, class_id, True).is_active
    assert classes_of(engine, scene.a) == [("KN-21", 2, True)]


# ---------------------------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("active", [True, False])
def test_a_class_with_a_student_cannot_be_deleted(
    engine: Engine, scene: Scene, active: bool
) -> None:
    """FR-006: a blocked student counts too."""
    class_id = make_class(engine, scene.a, "KN-21", active=active)
    enrolled(engine, "taras@example.org", class_id)
    with Session(engine) as session, pytest.raises(ClassInUse) as refused:
        delete_class(session, scene.teacher, class_id)
    assert refused.value.students == 1
    assert refused.value.school_class.id == class_id
    assert stored(engine, class_id) is not None


def test_an_empty_class_is_deleted(engine: Engine, scene: Scene) -> None:
    class_id = make_class(engine, scene.a, "KN-21")
    with Session(engine) as session:
        delete_class(session, scene.teacher, class_id)
        assert count_institution_classes(session, scene.a) == 0
    assert stored(engine, class_id) is None


def test_the_institution_classes_are_counted(engine: Engine, scene: Scene) -> None:
    make_class(engine, scene.a, "KN-21")
    make_class(engine, scene.a, "KN-22", active=False)
    make_class(engine, scene.b, "LA-1")
    with Session(engine) as session:
        assert count_institution_classes(session, scene.a) == 2


# ---------------------------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------------------------


def every_write(session: Session, teacher: int, institution_id: int, class_id: int) -> list:
    return [
        lambda: create_class(session, teacher, institution_id, "New", "1"),
        lambda: update_class(session, teacher, class_id, "Renamed", "3"),
        lambda: set_class_active(session, teacher, class_id, False),
        lambda: delete_class(session, teacher, class_id),
    ]


@pytest.mark.parametrize(
    ("target", "error"), [("b", WriteRequired), ("c", NotReachable)], ids=["read", "unlinked"]
)
def test_every_write_needs_write_access(
    engine: Engine, scene: Scene, target: str, error: type[Exception]
) -> None:
    """FR-020, FR-021: Read gives `WriteRequired`; no link gives `NotReachable`; nothing
    changes."""
    institution_id = getattr(scene, target)
    class_id = make_class(engine, institution_id, "KN-21")
    with Session(engine) as session:
        for write in every_write(session, scene.teacher, institution_id, class_id):
            with pytest.raises(error):
                write()
    assert classes_of(engine, institution_id) == [("KN-21", 2, True)]


def test_an_unknown_class_is_not_reachable(engine: Engine, scene: Scene) -> None:
    with Session(engine) as session:
        with pytest.raises(NotReachable):
            update_class(session, scene.teacher, 999_999, "X", "1")
        with pytest.raises(NotReachable):
            delete_class(session, scene.teacher, 999_999)
        count = session.exec(select(func.count()).select_from(SchoolClass)).one()
    assert count == 0
