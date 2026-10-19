"""User story 1: a teacher chooses a class and manages classes.

See specs/009-classes-students-management/spec.md US1 and contracts/http-routes.md §1, §2.1,
§2.2. The teacher is real: Write to "Kyiv Polytechnic Institute" (Kyiv), Read to "Lviv Academy"
(Lviv). Every case runs on both engines.
"""

import re
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import utc_now
from app.main import app
from app.models import AccessLevel, Enrolment, Institution, Region, Role, SchoolClass, User
from app.services.institutions import set_institution_active
from app.services.regions import set_region_active
from tests.conftest import (
    TEACHER_EMAIL,
    ClientAs,
    make_class,
    make_institution,
    make_teacher,
    seed_roles_directly,
)

OLENA = "olena@example.org"
STUDENTS = "/teacher/students"


@dataclass(frozen=True)
class Scene:
    teacher: TestClient
    kyiv: int
    lviv: int
    a: int
    b: int

    def selection(self, class_id: int | None = None, write: bool = True) -> str:
        region, institution = (self.kyiv, self.a) if write else (self.lviv, self.b)
        path = f"{STUDENTS}?region={region}&institution={institution}"
        return path if class_id is None else f"{path}&class={class_id}"


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs) -> Scene:
    engine = app.state.engine
    a = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    b = make_institution(engine, "Lviv Academy", "Lviv")
    make_institution(engine, "Odesa College", "Odesa")
    make_teacher(
        engine,
        app.state.settings,
        email=OLENA,
        institutions={a: AccessLevel.WRITE, b: AccessLevel.READ},
    )
    with Session(engine) as session:
        regions = {r.name: r.id for r in session.exec(select(Region))}
    return Scene(teacher=client_as(OLENA), kyiv=regions["Kyiv"], lviv=regions["Lviv"], a=a, b=b)


def classes(institution_id: int) -> list[tuple[str, int, bool]]:
    with Session(app.state.engine) as session:
        rows = session.exec(select(SchoolClass).where(SchoolClass.institution_id == institution_id))
        return sorted((row.name, row.year_of_study, row.is_active) for row in rows)


def class_row(class_id: int) -> SchoolClass | None:
    with Session(app.state.engine) as session:
        return session.get(SchoolClass, class_id)


def enrol(email: str, class_id: int) -> int:
    seed_roles_directly(app.state.engine, {email: [Role.STUDENT]})
    now = utc_now()
    with Session(app.state.engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.id is not None
        session.add(Enrolment(user_id=user.id, class_id=class_id, created_at=now, updated_at=now))
        session.commit()
        return user.id


def deactivate(institution_id: int, region_too: bool = False) -> None:
    """As an administrator would, after the teacher was linked."""
    with Session(app.state.engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        if region_too:
            set_region_active(session, institution.region_id, False)
        else:
            set_institution_active(session, institution.region_id, institution_id, False)


def select_tag(body: str, name: str) -> str:
    found = re.search(rf'<select id="{name}" name="{name}"[^>]*>', body)
    assert found is not None, f"no {name} list"
    return found.group(0)


def options(body: str, name: str) -> list[str]:
    found = re.search(rf'<select id="{name}" name="{name}"[^>]*>(.*?)</select>', body, re.DOTALL)
    assert found is not None
    return [text.strip() for text in re.findall(r"<option[^>]*>([^<]*)</option>", found.group(1))]


# ---------------------------------------------------------------------------------------------
# The shell
# ---------------------------------------------------------------------------------------------


def test_the_teacher_area_opens_the_students_tab(scene: Scene) -> None:
    """US1-1, FR-047."""
    response = scene.teacher.get("/teacher", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == STUDENTS
    body = scene.teacher.get(STUDENTS).text
    assert '<nav class="area-tabs" aria-label="Teacher area">' in body
    assert f'<a href="{STUDENTS}" aria-current="page">Students</a>' in body
    assert '<a href="/teacher/competitions">Competitions</a>' in body


def test_competitions_is_a_placeholder(scene: Scene) -> None:
    body = scene.teacher.get("/teacher/competitions").text
    assert "<h1>Competitions</h1>" in body
    assert "Competitions will arrive in a later milestone." in body
    assert '<a href="/teacher/competitions" aria-current="page">Competitions</a>' in body
    assert f'<a href="{STUDENTS}">Students</a>' in body


# ---------------------------------------------------------------------------------------------
# The three lists
# ---------------------------------------------------------------------------------------------


def test_nothing_selected(scene: Scene) -> None:
    """US1-2, US1-3: only Region is enabled; active regions with a linked institution only."""
    body = scene.teacher.get(STUDENTS).text
    assert "Select a region to continue" in body
    assert "disabled" not in select_tag(body, "region")
    assert select_tag(body, "institution").endswith(" disabled>")
    assert select_tag(body, "class").endswith(" disabled>")
    assert options(body, "region") == ["Select a region", "Kyiv", "Lviv"]


def test_regions_are_sorted_ignoring_case_and_need_an_available_linked_institution(
    client: TestClient, client_as: ClientAs
) -> None:
    """US1-3, FR-048: "kharkiv" before "Lviv"; Odesa's only institution is deactivated, and
    Dnipro itself is deactivated."""
    engine = app.state.engine
    odesa = make_institution(engine, "Odesa College", "Odesa")
    dnipro = make_institution(engine, "Dnipro Lyceum", "Dnipro")
    links = {
        make_institution(engine, "Lviv Academy", "Lviv"): AccessLevel.READ,
        make_institution(engine, "Kharkiv School", "kharkiv"): AccessLevel.READ,
        odesa: AccessLevel.WRITE,
        dnipro: AccessLevel.READ,
    }
    make_teacher(engine, app.state.settings, email=OLENA, institutions=links)
    deactivate(odesa)
    deactivate(dnipro, region_too=True)
    body = client_as(OLENA).get(STUDENTS).text
    assert options(body, "region") == ["Select a region", "kharkiv", "Lviv"]


def test_a_teacher_with_no_links_sees_disabled_lists(scene: Scene, client_as: ClientAs) -> None:
    """US1-15: the cast teacher has no links."""
    body = client_as(TEACHER_EMAIL).get(STUDENTS).text
    assert "You are not linked to any educational institution" in body
    for name in ("region", "institution", "class"):
        assert select_tag(body, name).endswith(" disabled>")
    assert "Show</button>" not in body


def test_choosing_from_a_list_opens_the_selection_at_once(
    scene: Scene, client_as: ClientAs
) -> None:
    """FR-048: each list submits its own form on change; there is no Show button."""
    client = client_as(TEACHER_EMAIL)
    body = client.get(STUDENTS).text
    for name in ("region", "institution", "class"):
        assert " data-auto-submit" in select_tag(body, name)
    assert '<script src="/static/js/auto-submit.js" defer></script>' in body
    script = client.get("/static/js/auto-submit.js")
    assert script.status_code == 200
    assert "requestSubmit()" in script.text


def test_links_to_unavailable_institutions_only_count_as_none(
    client: TestClient, client_as: ClientAs
) -> None:
    """Spec Edge Cases."""
    engine = app.state.engine
    closed = make_institution(engine, "Closed School", "Kyiv")
    hidden = make_institution(engine, "Odesa College", "Odesa")
    make_teacher(
        engine,
        app.state.settings,
        email=OLENA,
        institutions={closed: AccessLevel.WRITE, hidden: AccessLevel.WRITE},
    )
    deactivate(closed)
    deactivate(hidden, region_too=True)
    body = client_as(OLENA).get(STUDENTS).text
    assert "You are not linked to any educational institution" in body
    assert select_tag(body, "region").endswith(" disabled>")


def test_a_region_selected(scene: Scene) -> None:
    """US1-4."""
    body = scene.teacher.get(f"{STUDENTS}?region={scene.kyiv}").text
    assert "Select an educational institution to continue" in body
    assert f'<option value="{scene.kyiv}" selected>Kyiv</option>' in body
    assert "disabled" not in select_tag(body, "institution")
    assert select_tag(body, "class").endswith(" disabled>")
    assert options(body, "institution") == [
        "Select an educational institution",
        "Kyiv Polytechnic Institute — Write",
    ]
    assert f'<input type="hidden" name="region" value="{scene.kyiv}">' in body


def test_an_institution_selected_with_write(scene: Scene) -> None:
    """US1-5: + Add class comes last."""
    make_class(app.state.engine, scene.a, "kn-31", 3)
    make_class(app.state.engine, scene.a, "KN-21", 2, active=False)
    body = scene.teacher.get(scene.selection()).text
    assert "Select a class to see its students" in body
    assert "disabled" not in select_tag(body, "class")
    assert options(body, "class") == [
        "Select a class",
        "KN-21 · year 2 (deactivated)",
        "kn-31 · year 3",
        "+ Add class",
    ]
    assert '<option value="new">+ Add class</option>' in body


def test_add_class_opens_the_form_with_write_and_is_denied_with_read(scene: Scene) -> None:
    response = scene.teacher.get(f"{scene.selection()}&class=new", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{STUDENTS}/institutions/{scene.a}/classes/new"
    read = scene.teacher.get(f"{scene.selection(write=False)}&class=new")
    assert read.status_code == 403
    assert "+ Add class" not in scene.teacher.get(scene.selection(write=False)).text


# ---------------------------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------------------------


def create(scene: Scene, name: str = "KN-21", year: str = "2", **extra: str) -> object:
    return scene.teacher.post(
        f"{STUDENTS}/institutions/{scene.a}/classes",
        data={"name": name, "year_of_study": year, **extra},
        follow_redirects=False,
    )


def test_a_class_is_created_and_selected(scene: Scene) -> None:
    """US1-6, FR-050."""
    form = scene.teacher.get(f"{STUDENTS}/institutions/{scene.a}/classes/new").text
    assert "New class in “Kyiv Polytechnic Institute”" in form
    assert 'type="number" name="year_of_study" id="year_of_study" min="1" max="12" step="1"' in (
        form
    )
    response = create(scene, institution_id=str(scene.b))
    assert response.status_code == 303
    [(name, year, active)] = classes(scene.a)
    assert (name, year, active) == ("KN-21", 2, True)
    assert classes(scene.b) == []
    with Session(app.state.engine) as session:
        class_id = session.exec(select(SchoolClass.id)).one()
    assert response.headers["location"] == scene.selection(class_id)
    page = scene.teacher.get(response.headers["location"]).text
    assert f'<option value="{class_id}" selected>KN-21 · year 2</option>' in page
    assert "No students in this class yet" in page


@pytest.mark.parametrize(
    ("name", "year", "field", "message"),
    [
        ("", "2", "name", "Enter a name."),
        ("x" * 201, "2", "name", "The name can be at most 200 characters."),
        (
            "KN\t21",
            "2",
            "name",
            "The name cannot contain tabs, line breaks or other control characters.",
        ),
        ("KN-21", "0", "year_of_study", "Enter a year of study from 1 to 12."),
        ("KN-21", "13", "year_of_study", "Enter a year of study from 1 to 12."),
        ("KN-21", "2.5", "year_of_study", "Enter a year of study from 1 to 12."),
        ("KN-21", "", "year_of_study", "Enter a year of study from 1 to 12."),
    ],
    ids=["empty", "too-long", "tab", "year-0", "year-13", "year-decimal", "year-empty"],
)
def test_an_invalid_class_is_refused_with_the_values_kept(
    scene: Scene, name: str, year: str, field: str, message: str
) -> None:
    """US1-7, FR-004."""
    response = create(scene, name, year)
    assert response.status_code == 400
    assert message in response.text
    assert f'value="{year}"' in response.text
    assert classes(scene.a) == []


def test_both_errors_are_shown_at_once(scene: Scene) -> None:
    response = create(scene, "", "13")
    assert response.status_code == 400
    assert "Enter a name." in response.text
    assert "Enter a year of study from 1 to 12." in response.text


def test_a_duplicate_is_refused(scene: Scene) -> None:
    make_class(app.state.engine, scene.a, "KN-21", active=False)
    response = create(scene, "kn-21", "2")
    assert response.status_code == 400
    assert "A class named “KN-21” already exists in this institution." in response.text
    assert 'value="kn-21"' in response.text
    assert classes(scene.a) == [("KN-21", 2, False)]


# ---------------------------------------------------------------------------------------------
# Edit, deactivate, activate, delete
# ---------------------------------------------------------------------------------------------


def test_edit_changes_the_name_and_year(scene: Scene) -> None:
    """US1-9."""
    class_id = make_class(app.state.engine, scene.a, "KN-21", 2)
    form = scene.teacher.get(f"{STUDENTS}/classes/{class_id}/edit").text
    assert "Edit class “KN-21”" in form
    assert 'value="KN-21"' in form and 'value="2"' in form
    response = scene.teacher.post(
        f"{STUDENTS}/classes/{class_id}/edit",
        data={"name": "KN-22", "year_of_study": "3"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(class_id)
    renamed = scene.teacher.post(
        f"{STUDENTS}/classes/{class_id}/edit",
        data={"name": "kn-22", "year_of_study": "3"},
        follow_redirects=False,
    )
    assert renamed.status_code == 303
    assert classes(scene.a) == [("kn-22", 3, True)]


def test_an_invalid_edit_is_refused(scene: Scene) -> None:
    class_id = make_class(app.state.engine, scene.a, "KN-21", 2)
    response = scene.teacher.post(
        f"{STUDENTS}/classes/{class_id}/edit", data={"name": "KN-21", "year_of_study": "two"}
    )
    assert response.status_code == 400
    assert 'value="two"' in response.text
    assert classes(scene.a) == [("KN-21", 2, True)]


def test_deactivate_asks_first_then_marks_the_class(scene: Scene) -> None:
    """US1-10, US1-11, FR-052, FR-054."""
    class_id = make_class(app.state.engine, scene.a, "KN-21")
    confirm = scene.teacher.get(f"{STUDENTS}/classes/{class_id}/deactivate")
    assert confirm.status_code == 200
    assert "Deactivate class “KN-21”?" in confirm.text
    assert (
        "Its students will be signed out and hidden until the class is activated again."
        in confirm.text
    )
    assert classes(scene.a) == [("KN-21", 2, True)]
    response = scene.teacher.post(
        f"{STUDENTS}/classes/{class_id}/deactivate", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(class_id)
    page = scene.teacher.get(response.headers["location"]).text
    assert 'KN-21 · year 2 <small class="status-deactivated">Deactivated</small>' in page
    assert f'action="{STUDENTS}/classes/{class_id}/activate"' in page
    assert "Add student" not in page
    assert "This class is deactivated; its students are hidden until it is activated again" in page
    again = scene.teacher.post(f"{STUDENTS}/classes/{class_id}/activate", follow_redirects=False)
    assert again.status_code == 303
    page = scene.teacher.get(again.headers["location"]).text
    assert "Add student" in page
    assert "No students in this class yet" in page


def test_an_empty_class_is_deleted_and_the_institution_stays_selected(scene: Scene) -> None:
    """US1-12, spec Edge Cases."""
    class_id = make_class(app.state.engine, scene.a, "KN-21")
    confirm = scene.teacher.get(f"{STUDENTS}/classes/{class_id}/delete").text
    assert "Delete class “KN-21”?" in confirm
    assert "Kyiv Polytechnic Institute" in confirm
    assert class_row(class_id) is not None
    response = scene.teacher.post(f"{STUDENTS}/classes/{class_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection()
    assert class_row(class_id) is None
    assert "Select a class to see its students" in scene.teacher.get(scene.selection()).text


def test_a_class_with_a_student_is_not_deleted(scene: Scene) -> None:
    """US1-13, FR-053: deactivation is suggested only while the class is active."""
    class_id = make_class(app.state.engine, scene.a, "KN-21")
    enrol("taras@example.org", class_id)
    response = scene.teacher.post(f"{STUDENTS}/classes/{class_id}/delete")
    assert response.status_code == 409
    assert "“KN-21” has students and cannot be deleted." in response.text
    assert "You can deactivate it instead." in response.text
    assert f'href="{STUDENTS}/classes/{class_id}/deactivate"' in response.text
    scene.teacher.post(f"{STUDENTS}/classes/{class_id}/deactivate")
    refused = scene.teacher.post(f"{STUDENTS}/classes/{class_id}/delete")
    assert refused.status_code == 409
    assert "“KN-21” has students and cannot be deleted." in refused.text
    assert "You can deactivate it instead." not in refused.text
    assert class_row(class_id) is not None


# ---------------------------------------------------------------------------------------------
# Reloads, bookmarks and Read access
# ---------------------------------------------------------------------------------------------


def test_reloading_a_result_page_changes_nothing(scene: Scene) -> None:
    """US1-14, FR-056."""
    response = create(scene)
    location = response.headers["location"]  # type: ignore[attr-defined]
    for _ in range(2):
        assert scene.teacher.get(location).status_code == 200
    assert classes(scene.a) == [("KN-21", 2, True)]


def test_a_bookmarked_selection_opens_as_it_was(scene: Scene) -> None:
    class_id = make_class(app.state.engine, scene.a, "KN-21")
    body = scene.teacher.get(scene.selection(class_id)).text
    assert f'<option value="{scene.kyiv}" selected>Kyiv</option>' in body
    assert f'<option value="{scene.a}" selected>Kyiv Polytechnic Institute — Write</option>' in body
    assert f'<option value="{class_id}" selected>KN-21 · year 2</option>' in body


def test_read_access_shows_everything_without_actions(scene: Scene) -> None:
    """US1-16, FR-054."""
    class_id = make_class(app.state.engine, scene.b, "LA-1", 1)
    body = scene.teacher.get(scene.selection(class_id, write=False)).text
    assert "Lviv Academy — Read" in body
    assert "LA-1 · year 1" in body
    assert "No students in this class yet" in body
    for action in ("/edit", "/deactivate", "/activate", "/delete", "/invite", "Add student"):
        assert action not in body
