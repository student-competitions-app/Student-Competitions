"""Each role lands in its own area (milestone 12.6, user stories 1 and 2).

See specs/012.6-role-landing-area/contracts/http-routes.md. `/` sends an administrator to `/admin`
and a teacher to `/teacher`, which open their first tabs; a student still gets the home page. Every
way in that ends at `/` (sign-in, role choice, role switch, brand link, `/role` with one role) lands
in the area with no change of its own. Every test runs once per database engine.
"""

import logging

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.models import Role
from app.services import database_status
from app.services.email import EmailMessage
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    TEACHER_STUDENT_EMAIL,
    ClientAs,
    seed_roles_directly,
)
from tests.integration.test_login_flow import code_from, request_code, submit_code

FIRST_TAB = {ADMIN_EMAIL: "/admin/teachers", TEACHER_EMAIL: "/teacher/students"}
AREA = {ADMIN_EMAIL: "/admin", TEACHER_EMAIL: "/teacher"}


def assert_landed(response: httpx2.Response, first_tab: str) -> None:
    """The browser ended on the area's first tab, shown as the current tab."""
    assert response.status_code == 200
    assert response.url.path == first_tab
    current = [link.href for link in html.links(response.text) if link.attrs.get("aria-current")]
    assert current == [first_tab]


def database_lines(body: str) -> list[html.Element]:
    return [e for e in html.parse(body).iter() if "data-engine" in e.attrs]


@pytest.mark.parametrize("email", [ADMIN_EMAIL, TEACHER_EMAIL])
def test_staff_are_sent_to_their_area(client_as: ClientAs, email: str) -> None:
    """US1 scenarios 1–2, FR-001, FR-002."""
    browser = client_as(email)
    response = browser.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == AREA[email]
    assert_landed(browser.get("/"), FIRST_TAB[email])


def test_a_student_still_gets_the_home_page(client_as: ClientAs) -> None:
    """FR-003: one area card, the student's, and the database line."""
    response = client_as(STUDENT_EMAIL).get("/", follow_redirects=False)
    assert response.status_code == 200
    cards = [link.href for link in html.links(response.text, "main")]
    assert cards == ["/student"]
    assert len(database_lines(response.text)) == 1


def test_a_signed_out_visitor_is_sent_to_sign_in(client: TestClient) -> None:
    """FR-004."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F"


@pytest.mark.parametrize("email", [ADMIN_EMAIL, TEACHER_EMAIL])
def test_signing_in_without_a_return_address_lands_in_the_area(
    client: TestClient, outbox: list[EmailMessage], email: str
) -> None:
    """US1 scenarios 3–4, SC-001: no home page on the way."""
    assert request_code(client, email=email).status_code == 200
    response = submit_code(client, code_from(outbox[-1]), email=email)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert_landed(client.get("/"), FIRST_TAB[email])


def test_signing_in_with_a_return_address_goes_there(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US1 scenario 7, FR-007."""
    request_code(client, email=TEACHER_EMAIL, next_path="/teacher/competitions")
    code = code_from(outbox[-1])
    response = submit_code(client, code, email=TEACHER_EMAIL, next_path="/teacher/competitions")
    assert response.headers["location"] == "/teacher/competitions"
    assert client.get("/teacher/competitions").status_code == 200


def test_the_brand_link_leads_to_the_area(admin_client: TestClient) -> None:
    """US1 scenario 5: the brand still links to `/`, which now opens the area."""
    body = admin_client.get("/admin/subjects").text
    brands = [
        link
        for link in html.links(body, "header")
        if "brand" in link.attrs.get("class", "").split()
    ]
    assert [link.href for link in brands] == ["/"]
    assert_landed(admin_client.get(brands[0].href), FIRST_TAB[ADMIN_EMAIL])


def test_the_role_choice_with_one_role_lands_in_the_area(client_as: ClientAs) -> None:
    """US1 scenario 6."""
    browser = client_as(TEACHER_EMAIL)
    response = browser.get("/role", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert_landed(browser.get("/role"), FIRST_TAB[TEACHER_EMAIL])


def test_the_redirect_reads_no_database_status(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Plan constraint, research R1: the redirect is answered before the status is read."""

    def failing(*args: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(database_status, "read_database_status", failing)
    with caplog.at_level(logging.ERROR):
        response = admin_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert not [r for r in caplog.records if "Database status unavailable" in r.getMessage()]


# ---------------------------------------------------------------------------------------------
# User story 2: a person with several roles lands in the area of the role they chose
# ---------------------------------------------------------------------------------------------

ROLE_FIRST_TAB = {"admin": "/admin/teachers", "teacher": "/teacher/students"}


@pytest.fixture
def admin_teacher() -> str:
    """Nobody in the cast is administrator and teacher: give the administrator–student the
    teacher role too."""
    seed_roles_directly(app.state.engine, {ADMIN_STUDENT_EMAIL: [Role.TEACHER]})
    return ADMIN_STUDENT_EMAIL


def test_no_role_chosen_yet_means_the_role_choice(client_as: ClientAs, admin_teacher: str) -> None:
    """US2 scenario 4, FR-004: `/` and the brand link still lead to the role choice."""
    response = client_as(admin_teacher, None).get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/role?next=%2F"


@pytest.mark.parametrize("role", ["admin", "teacher"])
def test_choosing_a_role_lands_in_its_area(
    client_as: ClientAs, admin_teacher: str, role: str
) -> None:
    """US2 scenario 2."""
    browser = client_as(admin_teacher, None)
    assert_landed(browser.post("/role", data={"role": role, "next": "/"}), ROLE_FIRST_TAB[role])


@pytest.mark.parametrize(("current", "other"), [(Role.TEACHER, "admin"), (Role.ADMIN, "teacher")])
def test_switching_role_from_the_user_menu_lands_in_the_new_area(
    client_as: ClientAs, admin_teacher: str, current: Role, other: str
) -> None:
    """US2 scenario 3: the user menu posts only `role`, so the switch returns to `/`."""
    browser = client_as(admin_teacher, current)
    assert_landed(browser.post("/role", data={"role": other}), ROLE_FIRST_TAB[other])


def test_the_current_role_decides_not_the_roles_held(
    client_as: ClientAs, admin_teacher: str
) -> None:
    """FR-005, edge case "several roles, current role chosen"."""
    response = client_as(admin_teacher, Role.ADMIN).get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def test_a_teacher_working_as_a_student_sees_the_home_page(client_as: ClientAs) -> None:
    """US2 scenario 5."""
    browser = client_as(TEACHER_STUDENT_EMAIL, Role.STUDENT)
    home = browser.get("/", follow_redirects=False)
    assert home.status_code == 200
    assert [link.href for link in html.links(home.text, "main")] == ["/student"]
    assert_landed(browser.post("/role", data={"role": "teacher"}), ROLE_FIRST_TAB["teacher"])


def test_signing_in_with_several_roles_goes_through_the_role_choice(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US2 scenario 1, then scenario 2 through the real sign-in."""
    assert request_code(client, email=ADMIN_STUDENT_EMAIL).status_code == 200
    response = submit_code(client, code_from(outbox[-1]), email=ADMIN_STUDENT_EMAIL)
    assert response.status_code == 303
    assert response.headers["location"] == "/role?next=%2F"
    assert_landed(client.post("/role", data={"role": "admin", "next": "/"}), "/admin/teachers")
