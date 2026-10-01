"""A person with several roles chooses one after signing in (user story 3).

See specs/005-roles-authorization/contracts/http-routes.md#get-role--the-role-choice. Every test
runs once per database engine.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import SESSION_COOKIE_NAME, hash_token
from app.main import app
from app.models import Role, UserSession
from app.services.email import EmailMessage
from tests.conftest import (
    ADMIN_STUDENT_EMAIL,
    TEACHER_EMAIL,
    TEACHER_STUDENT_EMAIL,
    ClientAs,
)
from tests.integration.test_login_flow import code_from, request_code, submit_code

CHOOSE_ONE = "Choose one of your roles."


def stored_role(session: Session, browser: TestClient) -> str | None:
    token = browser.cookies[SESSION_COOKIE_NAME].split(".")[0]
    session.expire_all()
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    return row.one().current_role


def header(body: str) -> str:
    match = re.search(r"<header.*?</header>", body, re.DOTALL)
    assert match is not None, "the page has no <header>"
    return match.group(0)


def role_buttons(body: str) -> list[str]:
    form = re.search(r'<main.*?<form method="post" action="/role"[^>]*>(.*?)</form>', body, re.S)
    assert form is not None, "the page has no role form"
    return re.findall(r'<button type="submit" name="role" value="([a-z]+)">', form.group(1))


def unchosen(client_as: ClientAs, email: str = TEACHER_STUDENT_EMAIL) -> TestClient:
    """Signed in with several roles and none chosen yet, as right after the code check."""
    return client_as(email)


def test_the_full_flow_from_a_requested_page(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    """FR-013, SC-004, US3-1, US3-2, FR-032."""
    assert client.get("/teacher", follow_redirects=False).headers["location"] == (
        "/login?next=%2Fteacher"
    )
    request_code(client, email=TEACHER_STUDENT_EMAIL, next_path="/teacher")
    signed_in = submit_code(
        client, code_from(outbox[-1]), email=TEACHER_STUDENT_EMAIL, next_path="/teacher"
    )
    assert signed_in.status_code == 303
    assert signed_in.headers["location"] == "/role?next=%2Fteacher"
    assert stored_role(session, client) is None

    page = client.get(signed_in.headers["location"])
    assert page.status_code == 200
    assert "<h1>Choose a role</h1>" in page.text
    assert role_buttons(page.text) == ["teacher", "student"]
    assert '<input type="hidden" name="next" value="/teacher">' in page.text
    top = header(page.text)
    assert TEACHER_STUDENT_EMAIL in top
    assert "Log out" in top
    assert "site-role" not in top

    chosen = client.post(
        "/role", data={"role": "teacher", "next": "/teacher"}, follow_redirects=False
    )
    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/teacher"
    landed = client.get("/teacher")
    assert landed.status_code == 200
    assert '<span class="site-role">· Teacher</span>' in landed.text
    assert stored_role(session, client) == "teacher"


@pytest.mark.parametrize(
    ("path", "location"),
    [("/", "/role?next=%2F"), ("/staff?x=1", "/role?next=%2Fstaff%3Fx%3D1")],
)
def test_every_page_waits_for_the_choice(client_as: ClientAs, path: str, location: str) -> None:
    """US3-3, FR-014."""
    response = unchosen(client_as).get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == location


def test_a_write_waits_for_the_choice_without_a_return_address(client_as: ClientAs) -> None:
    """FR-014: a form post cannot be replayed, so it is sent to the plain role choice. No write
    route needs a role yet, so a temporary one stands in, as the route sweep's probe does."""
    app.add_api_route("/__probe_write", lambda: "x", methods=["POST"])
    try:
        response = unchosen(client_as).post("/__probe_write", follow_redirects=False)
    finally:
        app.router.routes.pop()
    assert response.status_code == 303
    assert response.headers["location"] == "/role"


def test_logging_out_from_the_role_choice(client_as: ClientAs, session: Session) -> None:
    """US3-4."""
    browser = unchosen(client_as)
    assert browser.get("/role").status_code == 200
    response = browser.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert browser.get("/", follow_redirects=False).headers["location"] == "/login?next=%2F"


@pytest.mark.parametrize("data", [{"role": "admin"}, {}, {"role": "superuser"}])
def test_a_role_not_held_changes_nothing(
    client_as: ClientAs, session: Session, data: dict[str, str]
) -> None:
    """US3-5, FR-020: a tampered, missing or unknown role."""
    browser = unchosen(client_as)
    response = browser.post("/role", data={**data, "next": "/teacher"}, follow_redirects=False)
    assert response.status_code == 400
    assert CHOOSE_ONE in response.text
    assert "<h1>Choose a role</h1>" in response.text
    assert role_buttons(response.text) == ["teacher", "student"]
    assert stored_role(session, browser) is None


def test_a_plain_link_changes_nothing(client_as: ClientAs, session: Session) -> None:
    """FR-020: only `POST` changes the role."""
    browser = unchosen(client_as)
    assert browser.get("/role", params={"role": "student"}).status_code == 200
    assert stored_role(session, browser) is None


def test_one_role_has_nothing_to_choose(client_as: ClientAs) -> None:
    """US3-6, FR-016."""
    response = client_as(TEACHER_EMAIL).get("/role", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


@pytest.mark.parametrize(
    "next_path", ["/role", "/login", "/logout", "//evil.example", "https://evil.example"]
)
def test_an_unsafe_next_lands_on_the_home_page(client_as: ClientAs, next_path: str) -> None:
    """FR-015: no loop back into the role choice or sign-in, and never another site."""
    browser = unchosen(client_as)
    page = browser.get("/role", params={"next": next_path})
    assert '<input type="hidden" name="next" value="/">' in page.text
    response = browser.post(
        "/role", data={"role": "student", "next": next_path}, follow_redirects=False
    )
    assert response.headers["location"] == "/"


def test_the_requested_page_is_not_adjusted_to_the_role(client_as: ClientAs) -> None:
    """Spec edge case: chosen as student while heading for /admin, the person lands there and is
    denied; the role is not switched for them."""
    browser = unchosen(client_as, ADMIN_STUDENT_EMAIL)
    response = browser.post(
        "/role", data={"role": "student", "next": "/admin"}, follow_redirects=False
    )
    assert response.headers["location"] == "/admin"
    denied = browser.get("/admin")
    assert denied.status_code == 403
    assert "Your current role, Student, cannot open this page." in denied.text


def test_choosing_again_after_a_choice_works_like_a_switch(
    client_as: ClientAs, session: Session
) -> None:
    """Spec edge case: opened directly, the page has no `next`, so it lands on `/`."""
    browser = client_as(TEACHER_STUDENT_EMAIL, Role.TEACHER)
    page = browser.get("/role")
    assert page.status_code == 200
    assert 'name="next"' not in page.text.split("<main", 1)[1]
    response = browser.post("/role", data={"role": "student"}, follow_redirects=False)
    assert response.headers["location"] == "/"
    assert stored_role(session, browser) == "student"


def test_a_single_role_sign_in_never_visits_the_role_choice(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """SC-003."""
    request_code(client, email=TEACHER_EMAIL, next_path="/staff")
    response = submit_code(client, code_from(outbox[-1]), email=TEACHER_EMAIL, next_path="/staff")
    assert response.headers["location"] == "/staff"
    assert client.get("/staff", follow_redirects=False).status_code == 200
