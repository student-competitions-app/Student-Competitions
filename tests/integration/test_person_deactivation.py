"""Deactivating a teacher (by an administrator) and a student (by a teacher with Write access).

Each person's own status keeps the role and everything attached to it (a teacher's links and
setting, a student's enrolment), but the role stops being usable: the person is signed out
everywhere at once, and cannot sign in with that role until activated again. Other roles stay
usable. Teachers and students are real: invited and accepted. Every case runs on both engines.
"""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.main import app
from app.models import (
    AccessLevel,
    Enrolment,
    Institution,
    Role,
    TeacherInstitution,
    TeacherProfile,
    User,
    UserSession,
)
from app.services.availability import usable_roles
from app.services.consent import current_consent_text
from app.services.email import EmailMessage
from app.services.invitations import Accepted, accept_invitation
from app.services.users import get_roles
from tests.conftest import (
    ADMIN_STUDENT_EMAIL,
    ClientAs,
    enrol_student,
    invite_student,
    make_class,
    make_institution,
    make_teacher,
)
from tests.integration.test_login_flow import code_from, request_code, submit_code

OLENA = "olena@example.org"
PETRO = "petro@example.org"
TARAS = "taras@example.org"
READ, WRITE = AccessLevel.READ, AccessLevel.WRITE


@dataclass(frozen=True)
class Scene:
    olena: int
    """Write to Kyiv, Read to Lviv."""
    petro: int
    """Write to Lviv."""
    kyiv: int
    lviv: int
    region: int
    kn21: int
    kn22: int
    la1: int

    def selection(self, class_id: int) -> str:
        return f"/teacher/students?region={self.region}&institution={self.kyiv}&class={class_id}"

    def carried(self, class_id: int) -> dict[str, str]:
        return {"region": str(self.region), "institution": str(self.kyiv), "class": str(class_id)}


@pytest.fixture
def scene(client: TestClient) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    kyiv = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    lviv = make_institution(engine, "Lviv Academy", "Lviv")
    olena = make_teacher(engine, settings, email=OLENA, institutions={kyiv: WRITE, lviv: READ})
    petro = make_teacher(
        engine, settings, email=PETRO, institutions={lviv: WRITE}, first="Petro", last="Bondar"
    )
    with Session(engine) as session:
        institution = session.get(Institution, kyiv)
        assert institution is not None
        region = institution.region_id
    return Scene(
        olena=olena,
        petro=petro,
        kyiv=kyiv,
        lviv=lviv,
        region=region,
        kn21=make_class(engine, kyiv, "KN-21", 2),
        kn22=make_class(engine, kyiv, "KN-22", 2),
        la1=make_class(engine, lviv, "LA-1", 1),
    )


def student(email: str, class_id: int, by: str = OLENA) -> int:
    return enrol_student(
        app.state.engine, app.state.settings, email=email, class_id=class_id, inviter_email=by
    )


def sessions_of(user_id: int) -> int:
    with Session(app.state.engine) as session:
        statement = select(func.count()).select_from(UserSession)
        return session.exec(statement.where(UserSession.user_id == user_id)).one()


def roles_of(user_id: int) -> tuple[tuple[Role, ...], tuple[Role, ...]]:
    """The roles held, and the usable ones."""
    with Session(app.state.engine) as session:
        return get_roles(session, user_id), usable_roles(session, user_id)


def person(user_id: int) -> User:
    with Session(app.state.engine) as session:
        found = session.get(User, user_id)
        assert found is not None
        return found


def profile(user_id: int) -> TeacherProfile:
    with Session(app.state.engine) as session:
        found = session.get(TeacherProfile, user_id)
        assert found is not None
        return found


def enrolment(user_id: int) -> Enrolment:
    with Session(app.state.engine) as session:
        found = session.get(Enrolment, user_id)
        assert found is not None
        return found


def cannot_get_a_code(client: TestClient, outbox: list[EmailMessage], email: str) -> bool:
    """The address is treated as unknown: the neutral answer, and no email is sent."""
    sent = len(outbox)
    assert request_code(client, email=email).status_code == 200
    return len(outbox) == sent


def signs_in_as(client: TestClient, outbox: list[EmailMessage], email: str, user_id: int) -> Role:
    assert request_code(client, email=email).status_code == 200
    assert submit_code(client, code_from(outbox[-1]), email=email).status_code == 303
    with Session(app.state.engine) as session:
        [row] = session.exec(select(UserSession).where(UserSession.user_id == user_id))
    assert row.current_role is not None
    return Role(row.current_role)


# ---------------------------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------------------------


def test_the_teacher_confirmation_explains_and_changes_nothing(
    admin_client: TestClient, scene: Scene
) -> None:
    body = admin_client.get(f"/admin/teachers/{scene.olena}/deactivate").text
    assert "Deactivate Olena Kovalenko as a teacher?" in body
    assert "They are signed out everywhere and cannot sign in as a teacher" in body
    assert profile(scene.olena).is_active


def test_deactivating_a_teacher_signs_them_out_and_keeps_everything(
    admin_client: TestClient, client_as: ClientAs, scene: Scene
) -> None:
    browser = client_as(OLENA)
    client_as(OLENA)
    before = profile(scene.olena)
    response = admin_client.post(
        f"/admin/teachers/{scene.olena}/deactivate", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/teachers"
    assert sessions_of(scene.olena) == 0
    assert browser.get("/teacher", follow_redirects=False).status_code == 303
    after = profile(scene.olena)
    assert not after.is_active
    assert after.updated_at > before.updated_at
    assert after.can_create_competitions == before.can_create_competitions
    assert person(scene.olena).is_active
    assert roles_of(scene.olena) == ((Role.TEACHER,), ())
    with Session(app.state.engine) as session:
        links = session.exec(
            select(TeacherInstitution).where(TeacherInstitution.user_id == scene.olena)
        ).all()
    assert {link.institution_id for link in links} == {scene.kyiv, scene.lviv}

    listed = admin_client.get("/admin/teachers").text
    assert '<td class="status">Deactivated</td>' in listed
    assert f'action="/admin/teachers/{scene.olena}/activate"' in listed
    assert f'href="/admin/teachers/{scene.olena}/deactivate"' not in listed
    assert "Deactivated" in admin_client.get(f"/admin/teachers/{scene.olena}").text


def test_a_deactivated_teacher_signs_in_again_once_activated(
    admin_client: TestClient, client: TestClient, outbox: list[EmailMessage], scene: Scene
) -> None:
    admin_client.post(f"/admin/teachers/{scene.olena}/deactivate")
    assert cannot_get_a_code(client, outbox, OLENA)
    response = admin_client.post(f"/admin/teachers/{scene.olena}/activate", follow_redirects=False)
    assert response.status_code == 303
    assert profile(scene.olena).is_active
    assert signs_in_as(client, outbox, OLENA, scene.olena) == Role.TEACHER


def test_an_administrator_who_teaches_keeps_the_administrator_role(
    admin_client: TestClient, client_as: ClientAs, scene: Scene
) -> None:
    user_id = make_teacher(
        app.state.engine,
        app.state.settings,
        email=ADMIN_STUDENT_EMAIL,
        institutions={scene.kyiv: READ},
    )
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.TEACHER)
    admin_client.post(f"/admin/teachers/{user_id}/deactivate")
    assert browser.get("/teacher", follow_redirects=False).status_code == 303
    held, usable = roles_of(user_id)
    assert held == (Role.ADMIN, Role.TEACHER, Role.STUDENT)
    assert usable == (Role.ADMIN, Role.STUDENT)
    assert client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN).get("/admin").status_code == 200


def test_activating_an_active_teacher_changes_nothing(
    admin_client: TestClient, scene: Scene
) -> None:
    before = profile(scene.olena)
    response = admin_client.post(f"/admin/teachers/{scene.olena}/activate", follow_redirects=False)
    assert response.status_code == 303
    assert profile(scene.olena).updated_at == before.updated_at


@pytest.mark.parametrize(
    ("method", "action"), [("GET", "deactivate"), ("POST", "deactivate"), ("POST", "activate")]
)
def test_not_a_current_teacher_cannot_be_deactivated(
    admin_client: TestClient, scene: Scene, method: str, action: str
) -> None:
    response = admin_client.request(method, f"/admin/teachers/999999/{action}")
    assert response.status_code == 404
    assert "Teacher not found" in response.text


def test_a_deactivated_teachers_student_invitation_cannot_be_accepted(
    admin_client: TestClient, scene: Scene
) -> None:
    engine, settings = app.state.engine, app.state.settings
    token = invite_student(engine, settings, email=TARAS, class_id=scene.kn21, inviter_email=OLENA)
    admin_client.post(f"/admin/teachers/{scene.olena}/deactivate")
    with Session(engine) as session:
        consent_text_id = current_consent_text(session, Role.STUDENT).id
        assert consent_text_id is not None
        outcome = accept_invitation(session, settings, token, consent_text_id)
    assert not isinstance(outcome, Accepted)


# ---------------------------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def teacher(client_as: ClientAs, scene: Scene) -> TestClient:
    return client_as(OLENA)


def test_the_student_list_shows_the_status_and_the_actions(
    teacher: TestClient, scene: Scene
) -> None:
    user_id = student(TARAS, scene.kn21)
    body = teacher.get(scene.selection(scene.kn21)).text.replace("&amp;", "&")
    assert '<th scope="col">Status</th>' in body
    assert "<td>Active</td>" in body
    assert f'href="/teacher/students/{user_id}/deactivate?region=' in body


def test_the_student_confirmation_names_the_student_and_changes_nothing(
    teacher: TestClient, scene: Scene
) -> None:
    user_id = student(TARAS, scene.kn21)
    path = f"/teacher/students/{user_id}/deactivate"
    body = teacher.get(path, params=scene.carried(scene.kn21)).text
    for shown in (
        "Deactivate Taras Shevchenko as a student?",
        "KN-21 · year 2",
        "Kyiv Polytechnic",
    ):
        assert shown in body
    assert enrolment(user_id).is_active


def test_deactivating_a_student_signs_them_out_and_keeps_the_enrolment(
    teacher: TestClient, client_as: ClientAs, scene: Scene
) -> None:
    user_id = student(TARAS, scene.kn21)
    browser = client_as(TARAS)
    client_as(TARAS)
    response = teacher.post(
        f"/teacher/students/{user_id}/deactivate",
        data=scene.carried(scene.kn21),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(scene.kn21)
    assert sessions_of(user_id) == 0
    assert browser.get("/profile", follow_redirects=False).status_code == 303
    after = enrolment(user_id)
    assert (after.is_active, after.class_id) == (False, scene.kn21)
    assert person(user_id).is_active
    assert roles_of(user_id) == ((Role.STUDENT,), ())

    listed = teacher.get(scene.selection(scene.kn21)).text
    assert "<td>Shevchenko Taras</td>" in listed
    assert "<td>Deactivated</td>" in listed
    assert f'action="/teacher/students/{user_id}/activate"' in listed


def test_a_deactivated_student_signs_in_again_once_activated(
    teacher: TestClient, client: TestClient, outbox: list[EmailMessage], scene: Scene
) -> None:
    user_id = student(TARAS, scene.kn21)
    teacher.post(f"/teacher/students/{user_id}/deactivate", data=scene.carried(scene.kn21))
    assert cannot_get_a_code(client, outbox, TARAS)
    response = teacher.post(
        f"/teacher/students/{user_id}/activate",
        data=scene.carried(scene.kn21),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(scene.kn21)
    assert enrolment(user_id).is_active
    assert signs_in_as(client, outbox, TARAS, user_id) == Role.STUDENT


def test_a_teacher_and_student_keeps_the_teacher_role_and_sees_the_status(
    teacher: TestClient, client_as: ClientAs, scene: Scene
) -> None:
    user_id = student(PETRO, scene.kn21)
    assert user_id == scene.petro
    teacher.post(f"/teacher/students/{user_id}/deactivate", data=scene.carried(scene.kn21))
    assert roles_of(user_id) == ((Role.TEACHER, Role.STUDENT), (Role.TEACHER,))
    body = client_as(PETRO).get("/profile").text
    assert "Student status" in body
    assert "Deactivated" in body


def test_a_deactivated_student_stays_deactivated_when_moved(
    teacher: TestClient, scene: Scene
) -> None:
    user_id = student(TARAS, scene.kn21)
    teacher.post(f"/teacher/students/{user_id}/deactivate", data=scene.carried(scene.kn21))
    data = {"first_name": "Taras", "last_name": "Shevchenko", "class_id": str(scene.kn22)}
    response = teacher.post(
        f"/teacher/students/{user_id}",
        data=data | scene.carried(scene.kn21),
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = enrolment(user_id)
    assert (after.class_id, after.is_active) == (scene.kn22, False)


@pytest.mark.parametrize(
    ("method", "action"), [("GET", "deactivate"), ("POST", "deactivate"), ("POST", "activate")]
)
def test_read_access_cannot_change_a_students_status(
    teacher: TestClient, scene: Scene, method: str, action: str
) -> None:
    user_id = student(TARAS, scene.la1, by=PETRO)
    response = teacher.request(method, f"/teacher/students/{user_id}/{action}")
    assert response.status_code == 403
    assert enrolment(user_id).is_active


def test_read_access_shows_the_status_without_actions(teacher: TestClient, scene: Scene) -> None:
    user_id = student(TARAS, scene.la1, by=PETRO)
    path = f"/teacher/students?region={_region_of(scene.lviv)}&institution={scene.lviv}"
    body = teacher.get(f"{path}&class={scene.la1}").text
    assert "<td>Active</td>" in body
    assert f"/teacher/students/{user_id}/deactivate" not in body


def _region_of(institution_id: int) -> int:
    with Session(app.state.engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id
