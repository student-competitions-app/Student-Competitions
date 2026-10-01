"""A person with several roles switches role from the header, per browser (user story 4).

See specs/005-roles-authorization/contracts/http-routes.md#layout-header-every-page and
#post-role--choose-or-switch. Every test runs once per database engine.
"""

import re

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import SESSION_COOKIE_NAME, hash_token
from app.models import Role, UserSession
from tests.conftest import ADMIN_STUDENT_EMAIL, TEACHER_EMAIL, ClientAs


def token_of(browser: TestClient) -> str:
    return browser.cookies[SESSION_COOKIE_NAME].split(".")[0]


def session_row(session: Session, browser: TestClient) -> UserSession:
    session.expire_all()
    statement = select(UserSession).where(UserSession.token_hash == hash_token(token_of(browser)))
    return session.exec(statement).one()


def switch_form(body: str) -> str | None:
    header = re.search(r"<header.*?</header>", body, re.DOTALL)
    assert header is not None, "the page has no <header>"
    form = re.search(
        r'<form method="post" action="/role" class="role-switch">(.*?)</form>',
        header.group(0),
        re.DOTALL,
    )
    return form.group(1) if form else None


def area_links(body: str) -> list[str]:
    section = re.search(r'<section id="areas".*?</section>', body, re.DOTALL)
    assert section is not None
    return re.findall(r'<a href="([^"]+)">', section.group(0))


def admin_student(client_as: ClientAs) -> TestClient:
    return client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)


def test_the_header_offers_the_other_role(client_as: ClientAs) -> None:
    """US4-1, FR-018: one button per other role, and no `next`, so a switch lands on `/`."""
    form = switch_form(admin_student(client_as).get("/").text)
    assert form is not None
    assert "Switch to" in form
    assert re.findall(r'name="role" value="([a-z]+)"', form) == ["student"]
    assert 'name="next"' not in form


def test_a_switch_changes_what_this_browser_may_open(client_as: ClientAs, session: Session) -> None:
    """US4-3, US4-4, SC-005: one click; same cookie, same session row."""
    browser = admin_student(client_as)
    cookie = browser.cookies[SESSION_COOKIE_NAME]
    row_id = session_row(session, browser).id
    assert browser.get("/admin").status_code == 200

    response = browser.post("/role", data={"role": "student"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "set-cookie" not in response.headers
    assert browser.cookies[SESSION_COOKIE_NAME] == cookie
    row = session_row(session, browser)
    assert (row.id, row.current_role) == (row_id, "student")

    home = browser.get("/").text
    assert '<span class="site-role">· Student</span>' in home
    assert area_links(home) == ["/student"]
    denied = browser.get("/admin")
    assert denied.status_code == 403
    assert "Your current role, Student, cannot open this page." in denied.text

    browser.post("/role", data={"role": "admin"})
    assert browser.get("/admin").status_code == 200


def test_switching_to_the_current_role_is_harmless(client_as: ClientAs, session: Session) -> None:
    browser = admin_student(client_as)
    response = browser.post("/role", data={"role": "admin"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert session_row(session, browser).current_role == "admin"


def test_a_role_not_held_is_refused(client_as: ClientAs, session: Session) -> None:
    """US4-6."""
    browser = admin_student(client_as)
    response = browser.post("/role", data={"role": "teacher"}, follow_redirects=False)
    assert response.status_code == 400
    assert "Choose one of your roles." in response.text
    assert session_row(session, browser).current_role == "admin"


def test_the_access_denied_page_still_offers_the_switch(client_as: ClientAs) -> None:
    """FR-026: the person may switch by hand; the page never switches for them."""
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.STUDENT)
    denied = browser.get("/admin")
    assert denied.status_code == 403
    form = switch_form(denied.text)
    assert form is not None
    assert 'value="admin"' in form


def test_a_single_role_header_has_no_switch(client_as: ClientAs) -> None:
    """US4-2."""
    assert switch_form(client_as(TEACHER_EMAIL).get("/").text) is None


def test_each_browser_keeps_its_own_role(client_as: ClientAs, session: Session) -> None:
    """US4-5, FR-011."""
    laptop = admin_student(client_as)
    phone = admin_student(client_as)
    laptop.post("/role", data={"role": "student"})
    assert session_row(session, laptop).current_role == "student"
    assert session_row(session, phone).current_role == "admin"
    assert phone.get("/admin").status_code == 200
    assert laptop.get("/admin").status_code == 403


def test_a_plain_link_cannot_switch(client_as: ClientAs, session: Session) -> None:
    """FR-020."""
    browser = admin_student(client_as)
    assert browser.get("/role", params={"role": "student"}).status_code == 200
    assert session_row(session, browser).current_role == "admin"
