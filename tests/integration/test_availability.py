"""User story 5: deactivating a region, an institution or a class blocks the students below it.

See specs/009-classes-students-management/spec.md US5, FR-011–FR-017, SC-005 and research D2–D4.
Everything goes through the real routes: a class is deactivated by its teacher, an institution or
a region by the administrator. Taras is in "KN-21" of "Kyiv Polytechnic Institute" (Kyiv); Ivan
is in "LA-1" of "Lviv Academy" (Lviv); Olena teaches both with Write access. Every case runs on
both engines.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import (
    AccessLevel,
    Enrolment,
    Institution,
    Region,
    Role,
    SchoolClass,
    User,
    UserSession,
)
from app.services.consent import current_consent_text
from app.services.email import EmailMessage
from tests import html
from tests.conftest import (
    ClientAs,
    enrol_student,
    invite_student,
    make_class,
    make_institution,
    make_teacher,
    token_from,
)
from tests.integration.test_login_flow import code_from, request_code, submit_code

OLENA = "olena@example.org"
TARAS = "taras@example.org"
IVAN = "ivan@example.org"


@dataclass(frozen=True)
class Scene:
    teacher: TestClient
    admin: TestClient
    taras: int
    ivan: int
    kyiv: int
    a: int
    kn21: int
    kn22: int
    lviv: int
    b: int
    la1: int

    def deactivate(self, level: str) -> None:
        """Through the real route of each level."""
        path = {
            "class": f"/teacher/students/classes/{self.kn21}/deactivate",
            "institution": f"/admin/institutions/regions/{self.kyiv}/institutions/{self.a}"
            "/deactivate",
            "region": f"/admin/institutions/regions/{self.kyiv}/deactivate",
        }[level]
        browser = self.teacher if level == "class" else self.admin
        assert browser.post(path, follow_redirects=False).status_code == 303

    def activate(self, level: str) -> None:
        path = {
            "class": f"/teacher/students/classes/{self.kn21}/activate",
            "institution": f"/admin/institutions/regions/{self.kyiv}/institutions/{self.a}"
            "/activate",
            "region": f"/admin/institutions/regions/{self.kyiv}/activate",
        }[level]
        browser = self.teacher if level == "class" else self.admin
        assert browser.post(path, follow_redirects=False).status_code == 303

    def selection(self, class_id: int | None = None) -> str:
        path = f"/teacher/students?region={self.kyiv}&institution={self.a}"
        return path if class_id is None else f"{path}&class={class_id}"


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs, admin_client: TestClient) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    a = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    b = make_institution(engine, "Lviv Academy", "Lviv")
    make_teacher(
        engine, settings, email=OLENA, institutions={a: AccessLevel.WRITE, b: AccessLevel.WRITE}
    )
    kn21, kn22, la1 = (
        make_class(engine, a, "KN-21"),
        make_class(engine, a, "KN-22"),
        make_class(engine, b, "LA-1"),
    )
    taras = enrol_student(engine, settings, email=TARAS, class_id=kn21, inviter_email=OLENA)
    ivan = enrol_student(
        engine, settings, email=IVAN, class_id=la1, inviter_email=OLENA, first="Ivan", last="Franko"
    )
    with Session(engine) as session:
        regions = {r.name: r.id for r in session.exec(select(Region))}
    return Scene(
        teacher=client_as(OLENA),
        admin=admin_client,
        taras=taras,
        ivan=ivan,
        kyiv=regions["Kyiv"],
        a=a,
        kn21=kn21,
        kn22=kn22,
        lviv=regions["Lviv"],
        b=b,
        la1=la1,
    )


LEVELS = ["class", "institution", "region"]


def sessions_of(user_id: int) -> int:
    with Session(app.state.engine) as session:
        return len(session.exec(select(UserSession).where(UserSession.user_id == user_id)).all())


def snapshot() -> dict[str, Any]:
    """Every status and every enrolment, byte for byte, but not the toggled rows' timestamps."""
    with Session(app.state.engine) as session:
        return {
            "regions": sorted((r.id, r.is_active) for r in session.exec(select(Region))),
            "institutions": sorted((i.id, i.is_active) for i in session.exec(select(Institution))),
            "classes": sorted(
                (c.id, c.name, c.year_of_study, c.is_active)
                for c in session.exec(select(SchoolClass))
            ),
            "enrolments": sorted(
                (e.user_id, e.class_id, e.created_at, e.updated_at)
                for e in session.exec(select(Enrolment))
            ),
            "users": sorted((u.id, u.is_active, u.first_name) for u in session.exec(select(User))),
        }


def sign_in(client: TestClient, outbox: list[EmailMessage], email: str) -> Any:
    assert request_code(client, email=email).status_code == 200
    return submit_code(client, code_from(outbox[-1]), email=email)


# ---------------------------------------------------------------------------------------------
# Signed out at once, and at sign-in
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_every_student_below_is_signed_out_at_once(
    scene: Scene, client_as: ClientAs, level: str
) -> None:
    """US5-1, FR-015: and only those below."""
    taras_browser = client_as(TARAS)
    ivan_browser = client_as(IVAN)
    client_as(TARAS)
    assert sessions_of(scene.taras) == 2
    scene.deactivate(level)
    assert sessions_of(scene.taras) == 0
    assert sessions_of(scene.ivan) == 1
    redirected = taras_browser.get("/profile", follow_redirects=False)
    assert redirected.status_code == 303
    assert redirected.headers["location"].startswith("/login")
    assert ivan_browser.get("/profile").status_code == 200


@pytest.mark.parametrize("level", LEVELS)
def test_a_blocked_student_signs_in_again_once_reactivated(
    scene: Scene, client: TestClient, outbox: list[EmailMessage], level: str
) -> None:
    """US5-2, US5-7, FR-016, SC-005: and nothing changed while deactivated."""
    before = snapshot()
    scene.deactivate(level)
    sent = len(outbox)
    assert request_code(client, email=TARAS).status_code == 200
    assert len(outbox) == sent
    scene.activate(level)
    assert snapshot() == before
    response = sign_in(client, outbox, TARAS)
    assert response.status_code == 303
    with Session(app.state.engine) as session:
        [row] = session.exec(select(UserSession).where(UserSession.user_id == scene.taras))
    assert row.current_role == Role.STUDENT
    rows = html.table_rows(scene.teacher.get(scene.selection(scene.kn21)).text)
    assert "Shevchenko Taras" in [row["Name"] for row in rows]


def test_a_class_reactivated_quickly_simply_needs_a_new_sign_in(
    scene: Scene, client: TestClient, client_as: ClientAs, outbox: list[EmailMessage]
) -> None:
    """Spec Edge Cases."""
    client_as(TARAS)
    before = snapshot()
    scene.deactivate("class")
    scene.activate("class")
    assert sessions_of(scene.taras) == 0
    assert snapshot() == before
    assert sign_in(client, outbox, TARAS).status_code == 303


def test_a_class_deactivated_below_a_reactivated_institution_stays_blocked(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """Spec Edge Cases, FR-012: each object keeps its own status."""
    scene.deactivate("class")
    scene.deactivate("institution")
    scene.activate("institution")
    sent = len(outbox)
    request_code(client, email=TARAS)
    assert len(outbox) == sent
    with Session(app.state.engine) as session:
        row = session.get(SchoolClass, scene.kn21)
        assert row is not None and not row.is_active


# ---------------------------------------------------------------------------------------------
# What the teacher sees
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["institution", "region"])
def test_an_unavailable_institution_disappears_from_the_teacher_lists(
    scene: Scene, level: str
) -> None:
    """US5-5, FR-013: not offered, and its address is access denied."""
    scene.deactivate(level)
    body = scene.teacher.get("/teacher/students").text
    assert "Kyiv" not in body
    assert "Lviv" in body
    for path in (
        scene.selection(),
        scene.selection(scene.kn21),
        f"/teacher/students/{scene.taras}",
        f"/teacher/students/{scene.taras}/remove",
        f"/teacher/students/classes/{scene.kn21}/edit",
        f"/teacher/students/institutions/{scene.a}/classes/new",
    ):
        assert scene.teacher.get(path).status_code == 403, path


def test_a_deactivated_class_is_listed_but_its_students_are_hidden(scene: Scene) -> None:
    """US5-6, FR-014."""
    scene.deactivate("class")
    body = scene.teacher.get(scene.selection(scene.kn21)).text
    assert "KN-21 · year 2 (deactivated)" in body
    assert "Shevchenko" not in body
    assert TARAS not in body
    for path in (f"/teacher/students/{scene.taras}", f"/teacher/students/{scene.taras}/remove"):
        assert scene.teacher.get(path).status_code == 403
    assert scene.teacher.post(f"/teacher/students/{scene.taras}/remove").status_code == 403
    assert sessions_of(scene.taras) == 0
    with Session(app.state.engine) as session:
        assert session.get(Enrolment, scene.taras) is not None


# ---------------------------------------------------------------------------------------------
# No new students in an unavailable class
# ---------------------------------------------------------------------------------------------


def test_no_one_is_invited_into_moved_into_or_accepted_into_an_unavailable_class(
    scene: Scene, client: TestClient
) -> None:
    """US5-8, FR-005."""
    engine, settings = app.state.engine, app.state.settings
    pending = invite_student(
        engine, settings, email="new@example.org", class_id=scene.kn22, inviter_email=OLENA
    )
    scene.teacher.post(f"/teacher/students/classes/{scene.kn22}/deactivate")
    invite = scene.teacher.post(
        f"/teacher/students/classes/{scene.kn22}/invite",
        data={"email": "other@example.org", "first_name": "A", "last_name": "B"},
    )
    assert invite.status_code == 409
    move = scene.teacher.post(
        f"/teacher/students/{scene.taras}",
        data={"first_name": "Taras", "last_name": "Shevchenko", "class_id": str(scene.kn22)},
    )
    assert move.status_code == 400
    assert "This class is deactivated." in move.text
    with Session(engine) as session:
        text_id = current_consent_text(session, Role.STUDENT).id
    accepted = client.post(f"/invitations/{pending}", data={"consent_text_id": str(text_id)})
    assert accepted.status_code == 400
    with Session(engine) as session:
        enrolment = session.get(Enrolment, scene.taras)
        assert enrolment is not None and enrolment.class_id == scene.kn21
        assert session.exec(select(User).where(User.email == "new@example.org")).first() is None


# ---------------------------------------------------------------------------------------------
# Data deletion
# ---------------------------------------------------------------------------------------------


def test_a_blocked_student_can_still_delete_their_data(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US5-4, FR-015: the link is sent, and erasure deletes the enrolment."""
    scene.deactivate("region")
    response = client.post("/data-deletion", data={"email": TARAS}, follow_redirects=False)
    assert response.status_code == 303
    assert outbox[-1].to == TARAS
    link = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    assert "These roles are removed: Student." in client.get(link).text
    assert client.post(link, follow_redirects=False).status_code == 303
    with Session(app.state.engine) as session:
        assert session.get(Enrolment, scene.taras) is None
        user = session.get(User, scene.taras)
        assert user is not None
        assert (user.email, user.first_name, user.is_active) == (
            f"erased-{scene.taras}",
            None,
            False,
        )
