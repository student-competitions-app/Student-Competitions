"""User story 5: a person deletes their data without signing in.

See specs/008-teacher-management-consent/spec.md US5 (scenarios 1–7 and the edge cases),
FR-049–FR-055, FR-061, research D10 and contracts/http-routes.md §5. Every case runs on both
engines. Links are read from the `memory` outbox; the background task runs before the test
client returns.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import utc_now
from app.core.sealing import seal
from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.models import AccessLevel, ConsentRecord, Enrolment, Role, User
from app.routers.data_deletion import LINK_EXPIRED, LINK_INVALID
from app.services.consent import erase_personal_data
from app.services.email import EmailMessage
from app.services.teachers import remove_teacher
from app.services.users import get_roles
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    ClientAs,
    accept,
    enrol_student,
    invite,
    invite_and_accept,
    make_class,
    make_institution,
    make_teacher,
    token_from,
)

OLENA = "olena@example.org"
REQUESTED = "If this email is registered, we have sent you a link."
LINK_HEADERS = {"referrer-policy": "no-referrer", "cache-control": "no-store"}


@pytest.fixture
def school(client: TestClient) -> int:
    return make_institution(app.state.engine, "School 5", "Kyiv")


def a_teacher(school: int, email: str = OLENA) -> int:
    return invite_and_accept(
        app.state.engine, app.state.settings, email=email, institutions={school: AccessLevel.READ}
    )


def request_link(browser: TestClient, email: str) -> TestClient:
    response = browser.post("/data-deletion", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/data-deletion/requested"
    return browser


def person(user_id: int) -> User:
    with Session(app.state.engine) as session:
        found = session.get(User, user_id)
        assert found is not None
        return found


def assert_link_headers(response: object) -> None:
    for name, value in LINK_HEADERS.items():
        assert response.headers[name] == value  # type: ignore[attr-defined]


def test_the_sign_in_page_offers_the_deletion(client: TestClient) -> None:
    """FR-049."""
    assert ("/data-deletion", "Delete my data") in html.link_pairs(
        client.get("/login").text, "main"
    )
    form = client.get("/data-deletion")
    assert form.status_code == 200
    assert ("post", "/data-deletion") in html.form_targets(form.text, "main")
    assert html.control(form.text, "email")["tag"] == "input"
    assert "Send link" in form.text


def test_every_address_gets_the_same_answer_and_only_a_consented_one_an_email(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """US5-1, US5-2, FR-050, FR-051, SC-006."""
    erased = a_teacher(school, "erased@example.org")
    with Session(app.state.engine) as session:
        erase_personal_data(session, app.state.settings, erased)
    a_teacher(school)
    bodies = []
    for email in (OLENA, "nobody@example.org", "erased@example.org", ADMIN_EMAIL):
        request_link(client, email)
        bodies.append(client.get("/data-deletion/requested").text)
    assert len(set(bodies)) == 1
    assert REQUESTED in bodies[0]
    [message] = outbox
    assert message.to == OLENA
    assert message.subject == "Delete your Student Competitions data"
    assert "/data-deletion/confirm/" in message.text
    assert "works once, within one hour, until" in message.text


def test_a_malformed_address_is_refused(client: TestClient, outbox: list[EmailMessage]) -> None:
    response = client.post("/data-deletion", data={"email": "not-an-email"})
    assert response.status_code == 400
    assert "Enter a valid email address." in response.text
    assert html.control(response.text, "email")["value"] == "not-an-email"
    assert outbox == []


def test_the_sixth_request_for_one_address_still_answers_but_sends_nothing(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    a_teacher(school)
    for _ in range(6):
        request_link(client, OLENA)
    assert len(outbox) == 5


def test_opening_the_link_changes_nothing_and_confirming_erases(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """US5-3, US5-4, FR-052, FR-053."""
    user_id = a_teacher(school)
    request_link(client, OLENA)
    link = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    page = client.get(link)
    assert page.status_code == 200
    assert_link_headers(page)
    for shown in (OLENA, "Olena", "Kovalenko", "These roles are removed: Teacher."):
        assert shown in page.text
    assert "Your administrator role and email stay." not in page.text
    assert person(user_id).first_name == "Olena"

    response = client.post(link, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/data-erased"
    assert_link_headers(response)
    erased = person(user_id)
    assert (erased.first_name, erased.email, erased.is_active) == (
        None,
        f"erased-{user_id}",
        False,
    )
    with Session(app.state.engine) as session:
        assert len(session.exec(select(ConsentRecord)).all()) == 1

    for method in ("GET", "POST"):
        again = client.request(method, link)
        assert again.status_code == 410
        assert LINK_EXPIRED in again.text
        assert "/data-deletion" in [link.href for link in html.content_links(again.text)]
        assert_link_headers(again)


def test_an_administrator_who_teaches_keeps_the_role_and_the_email(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    user_id = a_teacher(school, ADMIN_EMAIL)
    request_link(client, ADMIN_EMAIL)
    link = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    assert "Your administrator role and email stay." in client.get(link).text
    client.post(link)
    after = person(user_id)
    assert (after.email, after.is_active, after.first_name) == (ADMIN_EMAIL, True, None)


def test_an_old_link_is_expired_and_a_tampered_one_invalid(client: TestClient, school: int) -> None:
    """US5-5, US5-6."""
    user_id = a_teacher(school)
    key = app.state.settings.secret_key
    old = seal(key, "data-deletion", {"user": user_id}, now=utc_now() - timedelta(minutes=61))
    for method in ("GET", "POST"):
        expired = client.request(method, f"/data-deletion/confirm/{old}")
        assert expired.status_code == 410
        assert LINK_EXPIRED in expired.text
    fresh = seal(key, "data-deletion", {"user": user_id})
    middle = len(fresh) // 2
    tampered = fresh[:middle] + ("A" if fresh[middle] != "A" else "B") + fresh[middle + 1 :]
    for method in ("GET", "POST"):
        invalid = client.request(method, f"/data-deletion/confirm/{tampered}")
        assert invalid.status_code == 400
        assert LINK_INVALID in invalid.text
        assert_link_headers(invalid)
    assert person(user_id).first_name == "Olena"


def test_of_two_links_only_the_first_used_works(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    a_teacher(school)
    request_link(client, OLENA)
    request_link(client, OLENA)
    first, second = (f"/data-deletion/confirm/{token_from(m)}" for m in outbox)
    assert client.post(second, follow_redirects=False).status_code == 303
    assert client.get(first).status_code == 410


def test_a_removed_teacher_can_delete_their_data(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """US5-7: an inactive person with data stored on consent."""
    user_id = a_teacher(school)
    with Session(app.state.engine) as session:
        remove_teacher(session, app.state.settings, user_id)
    request_link(client, OLENA)
    link = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    assert client.post(link, follow_redirects=False).status_code == 303
    assert person(user_id).first_name is None


def test_the_cookie_is_cleared_only_for_the_erased_person(
    client_as: ClientAs, outbox: list[EmailMessage], school: int
) -> None:
    """FR-055: another person's browser posting the link keeps its session."""
    a_teacher(school, ADMIN_STUDENT_EMAIL)
    a_teacher(school)
    olena_browser = client_as(OLENA)
    admin_browser = client_as(ADMIN_EMAIL)

    request_link(admin_browser, ADMIN_STUDENT_EMAIL)
    someone_else = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    response = admin_browser.post(someone_else, follow_redirects=False)
    assert response.status_code == 303
    assert "set-cookie" not in response.headers
    assert admin_browser.get("/admin/teachers").status_code == 200

    request_link(olena_browser, OLENA)
    own = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    response = olena_browser.post(own, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["set-cookie"].startswith(f"{SESSION_COOKIE_NAME}=")
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_a_link_stays_used_after_a_re_invitation_within_the_hour(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """Research D10: the administrator keeps the email, is re-invited and accepts; the old link
    issued before the erasure is still used."""
    a_teacher(school, ADMIN_EMAIL)
    request_link(client, ADMIN_EMAIL)
    first = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    request_link(client, ADMIN_EMAIL)
    second = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    assert client.post(first, follow_redirects=False).status_code == 303
    token = invite(
        app.state.engine,
        app.state.settings,
        email=ADMIN_EMAIL,
        institutions={school: AccessLevel.READ},
    )
    user_id = accept(app.state.engine, app.state.settings, token)
    with Session(app.state.engine) as session:
        assert get_roles(session, user_id) == (Role.ADMIN, Role.TEACHER)
    assert client.get(second).status_code == 410
    assert person(user_id).first_name == "Olena"


def test_the_erased_page_can_be_reloaded(client: TestClient) -> None:
    first = client.get("/data-erased")
    assert first.status_code == 200
    assert first.text == client.get("/data-erased").text


def test_a_student_deletes_their_data_and_their_enrolment(
    client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """Milestone 9 US7-3, FR-044: the enrolment is erased with the rest, as on withdrawal."""
    engine, settings = app.state.engine, app.state.settings
    make_teacher(engine, settings, email=OLENA, institutions={school: AccessLevel.WRITE})
    class_id = make_class(engine, school, "KN-21")
    user_id = enrol_student(
        engine, settings, email="taras@example.org", class_id=class_id, inviter_email=OLENA
    )
    request_link(client, "taras@example.org")
    link = f"/data-deletion/confirm/{token_from(outbox[-1])}"
    assert "These roles are removed: Student." in client.get(link).text
    assert client.post(link, follow_redirects=False).status_code == 303
    erased = person(user_id)
    assert (erased.first_name, erased.email, erased.is_active) == (
        None,
        f"erased-{user_id}",
        False,
    )
    with Session(engine) as session:
        assert session.get(Enrolment, user_id) is None
        assert get_roles(session, user_id) == ()
        records = session.exec(select(ConsentRecord).where(ConsentRecord.user_id == user_id))
        assert len(records.all()) == 1
