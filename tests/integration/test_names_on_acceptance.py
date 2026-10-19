"""User story 6: names already held are kept on acceptance, for both invitable roles.

See specs/009-classes-students-management/spec.md US6, FR-036–FR-038, SC-007 and research D10. A
person who already holds the teacher or the student role keeps their names; a new person, an
inactive person and an administrator with neither role get the invitation's names. Every case
runs on both engines.
"""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import AccessLevel, Enrolment, Role, TeacherInstitution, User
from app.services.teachers import remove_teacher
from app.services.users import get_roles, get_user_by_email
from tests.conftest import (
    ADMIN_EMAIL,
    accept,
    enrol_student,
    invite,
    invite_student,
    make_class,
    make_institution,
    make_teacher,
)

OLENA = "olena@example.org"
NOTE = "If you are already a teacher or a student, your current names are kept."


@dataclass(frozen=True)
class Scene:
    institution: int
    other: int
    school_class: int


@pytest.fixture
def scene(client: TestClient) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    other = make_institution(engine, "Lviv Academy", "Lviv")
    make_teacher(engine, settings, email=OLENA, institutions={institution: AccessLevel.WRITE})
    return Scene(
        institution=institution,
        other=other,
        school_class=make_class(engine, institution, "KN-21"),
    )


def names(user_id: int) -> tuple[str | None, str | None]:
    with Session(app.state.engine) as session:
        user = session.get(User, user_id)
        assert user is not None
        return user.first_name, user.last_name


def roles(user_id: int) -> tuple[Role, ...]:
    with Session(app.state.engine) as session:
        return get_roles(session, user_id)


def student_link(scene: Scene, email: str, first: str, last: str) -> str:
    return invite_student(
        app.state.engine,
        app.state.settings,
        email=email,
        class_id=scene.school_class,
        inviter_email=OLENA,
        first=first,
        last=last,
    )


def test_a_teacher_accepting_a_student_invitation_keeps_their_names(scene: Scene) -> None:
    """US6-1: Olena is invited into an evening course as "O. Kovalenko"."""
    engine, settings = app.state.engine, app.state.settings
    teacher_id = make_teacher(
        engine,
        settings,
        email="evening@example.org",
        institutions={scene.other: AccessLevel.READ},
        first="Olena",
        last="Kovalenko",
    )
    token = student_link(scene, "evening@example.org", "O.", "Kovalenko")
    assert accept(engine, settings, token, role=Role.STUDENT) == teacher_id
    assert names(teacher_id) == ("Olena", "Kovalenko")
    assert roles(teacher_id) == (Role.TEACHER, Role.STUDENT)
    with Session(engine) as session:
        enrolment = session.get(Enrolment, teacher_id)
        assert enrolment is not None and enrolment.class_id == scene.school_class


def test_a_student_accepting_a_teacher_invitation_keeps_their_names(scene: Scene) -> None:
    """US6-2."""
    engine, settings = app.state.engine, app.state.settings
    student_id = enrol_student(
        engine,
        settings,
        email="taras@example.org",
        class_id=scene.school_class,
        inviter_email=OLENA,
    )
    token = invite(
        engine,
        settings,
        email="taras@example.org",
        first="T.",
        last="S.",
        institutions={scene.other: AccessLevel.WRITE},
    )
    assert accept(engine, settings, token) == student_id
    assert names(student_id) == ("Taras", "Shevchenko")
    assert roles(student_id) == (Role.TEACHER, Role.STUDENT)
    with Session(engine) as session:
        links = session.exec(
            select(TeacherInstitution).where(TeacherInstitution.user_id == student_id)
        ).all()
    assert [(link.institution_id, link.access_level) for link in links] == [(scene.other, "write")]


def test_a_new_person_gets_the_invitation_names(scene: Scene) -> None:
    """US6-3."""
    engine, settings = app.state.engine, app.state.settings
    user_id = accept(
        engine, settings, student_link(scene, "new@example.org", "Iryna", "Lys"), role=Role.STUDENT
    )
    assert names(user_id) == ("Iryna", "Lys")


def test_an_inactive_former_teacher_gets_the_invitation_names(scene: Scene) -> None:
    """US6-3: removed, so no longer a teacher, and inactive."""
    engine, settings = app.state.engine, app.state.settings
    former = make_teacher(
        engine,
        settings,
        email="former@example.org",
        institutions={scene.other: AccessLevel.READ},
        first="Old",
        last="Name",
    )
    with Session(engine) as session:
        remove_teacher(session, settings, former)
    with Session(engine) as session:
        removed = get_user_by_email(session, "former@example.org")
        assert removed is not None and not removed.is_active
    token = student_link(scene, "former@example.org", "New", "Name")
    assert accept(engine, settings, token, role=Role.STUDENT) == former
    assert names(former) == ("New", "Name")
    assert roles(former) == (Role.STUDENT,)


def test_an_administrator_with_neither_role_gets_the_invitation_names(scene: Scene) -> None:
    """US6-3: an administrator who once taught, with names stored, but holds neither role now."""
    engine, settings = app.state.engine, app.state.settings
    admin_id = make_teacher(
        engine,
        settings,
        email=ADMIN_EMAIL,
        institutions={scene.other: AccessLevel.READ},
        first="Ada",
        last="Admin",
    )
    with Session(engine) as session:
        remove_teacher(session, settings, admin_id)
    assert roles(admin_id) == (Role.ADMIN,)
    assert names(admin_id) == ("Ada", "Admin")
    token = student_link(scene, ADMIN_EMAIL, "Adelina", "Adminova")
    accept(engine, settings, token, role=Role.STUDENT)
    assert names(admin_id) == ("Adelina", "Adminova")
    assert roles(admin_id) == (Role.ADMIN, Role.STUDENT)


def test_both_acceptance_pages_carry_the_note(scene: Scene, client: TestClient) -> None:
    """US6-4, FR-038."""
    engine, settings = app.state.engine, app.state.settings
    teacher = invite(
        engine, settings, email="t@example.org", institutions={scene.other: AccessLevel.READ}
    )
    student = student_link(scene, "s@example.org", "Iryna", "Lys")
    for token in (teacher, student):
        assert NOTE in client.get(f"/invitations/{token}").text
