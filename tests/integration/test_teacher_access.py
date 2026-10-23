"""User story 9: only the right people reach each teacher page and action.

See specs/009-classes-students-management/spec.md US9, FR-018–FR-023, SC-004 and research D5,
D17. The sweeps are built from the route table (`tests/integration/test_routes.py`), so a teacher
route added later is covered without a change here. Ids are real: a Write-reachable institution,
an active class and an enrolled student. Every case runs on both engines.

- Olena: Write to "Kyiv Polytechnic Institute" (Kyiv).
- Petro: Read to the same institution.
- Iryna: Write to "Odesa College" (Odesa) only.
"""

import re
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, select
from sqlmodel import Session

from app.main import app
from app.models import AccessLevel, Institution, Role
from app.services.classes import set_class_active
from app.services.teachers import update_teacher
from app.services.users import get_user_by_email
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    ClientAs,
    enrol_student,
    make_class,
    make_institution,
    make_teacher,
)
from tests.integration.test_routes import ALL_ROUTES

OLENA = "olena@example.org"
PETRO = "petro@example.org"
IRYNA = "iryna@example.org"

AREA_PAGES = {"/teacher", "/teacher/students", "/teacher/competitions"}
"""The teacher pages that name no object; every other teacher page is a management page."""

TEACHER_GETS = sorted(
    path for path, methods, _ in ALL_ROUTES if "GET" in methods and path.startswith("/teacher")
)
TEACHER_POSTS = sorted(
    path for path, methods, _ in ALL_ROUTES if "POST" in methods and path.startswith("/teacher")
)

SNAPSHOT_TABLES = ("classes", "enrolments", "users", "user_roles", "consent_records")


@dataclass(frozen=True)
class Scene:
    writer: TestClient
    reader: TestClient
    outsider: TestClient
    region: int
    institution: int
    school_class: int
    second_class: int
    student: int
    other_region: int
    other_institution: int
    other_class: int

    def ids(self) -> dict[str, int]:
        return {
            "institution_id": self.institution,
            "class_id": self.school_class,
            "user_id": self.student,
        }

    def concrete(self, path: str) -> str:
        values = self.ids()
        return re.sub(r"\{(\w+)(?::\w+)?\}", lambda m: str(values[m.group(1)]), path)


def region_of(institution_id: int) -> int:
    with Session(app.state.engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    other = make_institution(engine, "Odesa College", "Odesa")
    make_teacher(engine, settings, email=OLENA, institutions={institution: AccessLevel.WRITE})
    make_teacher(engine, settings, email=PETRO, institutions={institution: AccessLevel.READ})
    make_teacher(engine, settings, email=IRYNA, institutions={other: AccessLevel.WRITE})
    school_class = make_class(engine, institution, "KN-21")
    second_class = make_class(engine, institution, "KN-22")
    other_class = make_class(engine, other, "OC-1")
    student = enrol_student(
        engine, settings, email="taras@example.org", class_id=school_class, inviter_email=OLENA
    )
    enrol_student(
        engine,
        settings,
        email="odesa@example.org",
        class_id=other_class,
        inviter_email=IRYNA,
        first="Oksana",
        last="Moroz",
    )
    return Scene(
        writer=client_as(OLENA),
        reader=client_as(PETRO),
        outsider=client_as(IRYNA),
        region=region_of(institution),
        institution=institution,
        school_class=school_class,
        second_class=second_class,
        student=student,
        other_region=region_of(other),
        other_institution=other,
        other_class=other_class,
    )


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def test_the_sweeps_have_routes() -> None:
    """Guard the parametrized sweeps from passing vacuously."""
    assert len(TEACHER_GETS) >= 9
    assert len(TEACHER_POSTS) == 10


# ---------------------------------------------------------------------------------------------
# Every teacher page, with real ids (research D17)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", TEACHER_GETS)
def test_every_teacher_page_admits_a_write_teacher(scene: Scene, path: str) -> None:
    """FR-021, research D17: allowed for Write; every management page refused for Read and for
    a teacher not linked to the institution."""
    url = scene.concrete(path)
    status = scene.writer.get(url, follow_redirects=False).status_code
    assert status != 403, f"Write GET {url}: {status}"
    if path in AREA_PAGES:
        return
    for name, browser in (("Read", scene.reader), ("unlinked", scene.outsider)):
        refused = browser.get(url, follow_redirects=False)
        assert refused.status_code == 403, f"{name} GET {url}: {refused.status_code}"
        assert "Your current role, Teacher, cannot open this page." in refused.text


# ---------------------------------------------------------------------------------------------
# Every teacher action, for everyone who may not use it
# ---------------------------------------------------------------------------------------------

FORM = {
    "name": "Hacked",
    "year_of_study": "3",
    "email": "hacked@example.org",
    "first_name": "Hacked",
    "last_name": "Hacked",
}


@pytest.mark.parametrize("path", TEACHER_POSTS)
def test_every_teacher_action_is_refused_to_everyone_else(
    scene: Scene, client: TestClient, client_as: ClientAs, path: str
) -> None:
    """US9-1, US9-2, US9-3, FR-020: and nothing changes."""
    url = scene.concrete(path)
    data = {**FORM, "class_id": str(scene.second_class)}
    others = {
        "Read teacher": scene.reader,
        "unlinked teacher": scene.outsider,
        "administrator": client_as(ADMIN_EMAIL),
        "student": client_as(STUDENT_EMAIL),
        "administrator using the student role": client_as(ADMIN_STUDENT_EMAIL, Role.STUDENT),
    }
    before = snapshot(app.state.engine)
    for name, browser in others.items():
        response = browser.post(url, data=data, follow_redirects=False)
        assert response.status_code == 403, f"{name} POST {url}: {response.status_code}"
    anonymous = client.post(url, data=data, follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/login"
    assert snapshot(app.state.engine) == before


# ---------------------------------------------------------------------------------------------
# Hand-made addresses and form values
# ---------------------------------------------------------------------------------------------


def hand_made(scene: Scene) -> list[str]:
    base = "/teacher/students"
    return [
        f"{base}?region={scene.other_region}&institution={scene.institution}",
        f"{base}?institution={scene.institution}",
        f"{base}?region={scene.region}&class={scene.school_class}",
        f"{base}?region={scene.region}&institution={scene.institution}&class={scene.other_class}",
        f"{base}?region={scene.region}&institution={scene.other_institution}",
        f"{base}?region={scene.other_region}",
        f"{base}?region=abc",
        f"{base}?region=%D9%A2",
        f"{base}?region={'9' * 40}",
        f"{base}?region={scene.region}&institution={scene.institution}&class=999999",
        f"{base}/classes/999999/edit",
        f"{base}/classes/{scene.other_class}/edit",
        f"{base}/institutions/{scene.other_institution}/classes/new",
        f"{base}/999999",
    ]


def test_hand_made_addresses_are_access_denied(scene: Scene) -> None:
    """US9-2, FR-021, spec Edge Cases."""
    for url in hand_made(scene):
        response = scene.writer.get(url, follow_redirects=False)
        assert response.status_code == 403, url
        assert "Access denied" in response.text


def olena_id() -> int:
    with Session(app.state.engine) as session:
        teacher = get_user_by_email(session, OLENA)
        assert teacher is not None and teacher.id is not None
        return teacher.id


def test_a_student_of_a_deactivated_class_cannot_be_opened(scene: Scene) -> None:
    """US9-2: "a student of a deactivated class"."""
    scene.writer.post(f"/teacher/students/classes/{scene.school_class}/deactivate")
    for action in ("", "/deactivate", "/remove"):
        assert scene.writer.get(f"/teacher/students/{scene.student}{action}").status_code == 403


def test_a_class_of_another_institution_in_a_student_form_is_access_denied(
    scene: Scene,
) -> None:
    before = snapshot(app.state.engine)
    response = scene.writer.post(
        f"/teacher/students/{scene.student}",
        data={"first_name": "T", "last_name": "S", "class_id": str(scene.other_class)},
    )
    assert response.status_code == 403
    assert snapshot(app.state.engine) == before


def test_no_page_answers_with_fastapis_json_errors(scene: Scene) -> None:
    """Values are read as strings: a bad one is never a 422."""
    for url in (
        "/teacher/students?region=&institution=&class=",
        "/teacher/students?class=new",
    ):
        assert scene.writer.get(url).status_code in (200, 403)
    response = scene.writer.post(
        f"/teacher/students/classes/{scene.school_class}/edit", data={"year_of_study": "x"}
    )
    assert response.status_code == 400
    assert "application/json" not in response.headers["content-type"]


# ---------------------------------------------------------------------------------------------
# Access lowered or removed while a form is open (FR-022)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("change", ["lowered-to-read", "unlinked"])
def test_a_form_saved_after_the_access_changed_is_access_denied(scene: Scene, change: str) -> None:
    """US9-4."""
    edit = f"/teacher/students/classes/{scene.school_class}/edit"
    assert scene.writer.get(edit).status_code == 200
    engine = app.state.engine
    links = (
        {scene.institution: AccessLevel.READ}
        if change == "lowered-to-read"
        else {scene.other_institution: AccessLevel.READ}
    )
    with Session(engine) as session:
        update_teacher(session, olena_id(), "Olena", "Kovalenko", links, False)
    before = snapshot(engine)
    response = scene.writer.post(edit, data={"name": "KN-99", "year_of_study": "4"})
    assert response.status_code == 403
    assert snapshot(engine) == before
    remove = scene.writer.post(f"/teacher/students/{scene.student}/remove")
    assert remove.status_code == 403
    assert snapshot(engine) == before


def test_a_deactivated_class_can_still_be_reactivated_by_its_writer(scene: Scene) -> None:
    """FR-014: the class itself stays reachable, and so manageable."""
    with Session(app.state.engine) as session:
        set_class_active(session, olena_id(), scene.school_class, False)
    response = scene.writer.post(
        f"/teacher/students/classes/{scene.school_class}/activate", follow_redirects=False
    )
    assert response.status_code == 303


# ---------------------------------------------------------------------------------------------
# Administrators manage no classes and no students (FR-020)
# ---------------------------------------------------------------------------------------------


def test_the_administrator_area_links_to_no_teacher_page(scene: Scene, client_as: ClientAs) -> None:
    """US9-5."""
    admin = client_as(ADMIN_EMAIL)
    pages = [
        "/admin/teachers",
        "/admin/institutions",
        f"/admin/institutions/regions/{scene.region}",
        "/admin/subjects",
    ]
    for page in pages:
        body = admin.get(page).text
        assert "/teacher/students" not in body, page
        assert "KN-21" not in body, page
