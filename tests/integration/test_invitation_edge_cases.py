"""The invitation edge cases of specs/008-teacher-management-consent/spec.md (Edge Cases, FR-018,
FR-028, FR-031), through the routes, on both engines.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.main import app
from app.models import ConsentRecord, Role, User, UserRole
from app.services.consent import current_consent_text
from app.services.email import EmailDeliveryError, EmailMessage
from app.services.users import get_roles
from tests import html
from tests.conftest import TEACHER_EMAIL, ClientAs, make_institution, token_from

OLENA = "olena@example.org"


@pytest.fixture
def school(client: TestClient) -> int:
    return make_institution(app.state.engine, "School 5", "Kyiv")


def form(school: int, email: str = OLENA, **overrides: str) -> dict[str, object]:
    return {
        "email": email,
        "first_name": "Olena",
        "last_name": "Kovalenko",
        "institution": [str(school)],
        "access": [f"{school}:read"],
        **overrides,
    }


def send(admin: TestClient, school: int, email: str = OLENA, **overrides: str) -> int:
    response = admin.post(
        "/admin/teachers/invite", data=form(school, email, **overrides), follow_redirects=False
    )
    return response.status_code


def consent_id() -> str:
    with Session(app.state.engine) as session:
        return str(current_consent_text(session, Role.TEACHER).id)


def agree(browser: TestClient, token: str) -> int:
    response = browser.post(
        f"/invitations/{token}", data={"consent_text_id": consent_id()}, follow_redirects=False
    )
    return response.status_code


def count(model: type) -> int:
    with Session(app.state.engine) as session:
        return session.exec(select(func.count()).select_from(model)).one()


def test_an_existing_teacher_is_told_so(
    client: TestClient, admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """Edge case: the invitation is sent; the page says "already a teacher"; pressing I agree
    changes nothing."""
    assert send(admin_client, school) == 303
    assert agree(client, token_from(outbox[-1])) == 303
    assert send(admin_client, school) == 303
    second = token_from(outbox[-1])
    page = client.get(f"/invitations/{second}")
    assert page.status_code == 200
    assert "You are already a teacher." in page.text
    assert ("/login", "Sign in") in html.link_pairs(page.text, "main")
    response = client.post(
        f"/invitations/{second}", data={"consent_text_id": consent_id()}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/invitations/{second}"
    assert count(ConsentRecord) == 1


def test_pressing_i_agree_twice_stores_once(
    client: TestClient, admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """FR-031."""
    send(admin_client, school)
    token = token_from(outbox[-1])
    assert agree(client, token) == 303
    assert agree(client, token) == 303
    with Session(app.state.engine) as session:
        [olena] = session.exec(select(User).where(User.email == OLENA)).all()
        rows = select(func.count()).select_from(UserRole).where(UserRole.user_id == olena.id)
        assert session.exec(rows).one() == 1
    assert count(ConsentRecord) == 1


def test_of_two_invitations_the_first_accepted_wins(
    client: TestClient, admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    other = make_institution(app.state.engine, "Lyceum", "Lviv")
    send(admin_client, school)
    send(admin_client, other)
    first, second = token_from(outbox[0]), token_from(outbox[1])
    assert agree(client, second) == 303
    assert "You are already a teacher." in client.get(f"/invitations/{first}").text
    assert count(ConsentRecord) == 1


def test_a_removed_teacher_accepts_a_newer_invitation(
    client: TestClient, admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """FR-028: the inactive person is reactivated with the role and the new names."""
    send(admin_client, school)
    agree(client, token_from(outbox[-1]))
    with Session(app.state.engine) as session:
        olena = session.exec(select(User).where(User.email == OLENA)).one()
    removed = admin_client.post(f"/admin/teachers/{olena.id}/remove", follow_redirects=False)
    assert removed.status_code == 303
    send(admin_client, school, first_name="Olha")
    assert agree(client, token_from(outbox[-1])) == 303
    with Session(app.state.engine) as session:
        back = session.get(User, olena.id)
        assert back is not None and back.is_active and back.first_name == "Olha"
        assert get_roles(session, olena.id) == (Role.TEACHER,)


def test_the_inviter_limit_is_twenty_an_hour(
    admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """FR-018."""
    for number in range(20):
        assert send(admin_client, school, f"person{number}@example.org") == 303
    response = admin_client.post("/admin/teachers/invite", data=form(school, "late@example.org"))
    assert response.status_code == 429
    assert "Too many invitations. Please try again later." in response.text
    assert html.control(response.text, "email")["value"] == "late@example.org"
    assert len(outbox) == 20


def test_the_address_limit_is_five_an_hour(
    admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """FR-018."""
    for _ in range(5):
        assert send(admin_client, school) == 303
    assert send(admin_client, school) == 429
    assert len(outbox) == 5


def test_a_send_failure_stores_nothing_and_still_counts(
    admin_client: TestClient,
    outbox: list[EmailMessage],
    school: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edge case: `503` with every value; nothing stored; the attempt counts against the limit."""
    sender = app.state.email_sender

    def fail(message: EmailMessage) -> None:
        raise EmailDeliveryError("Resend returned HTTP 500")

    monkeypatch.setattr(sender, "send", fail)
    response = admin_client.post("/admin/teachers/invite", data=form(school))
    assert response.status_code == 503
    assert "The invitation email could not be sent. Please try again." in response.text
    assert html.control(response.text, "email")["value"] == OLENA
    assert html.control(response.text, "last_name")["value"] == "Kovalenko"
    monkeypatch.undo()
    with Session(app.state.engine) as session:
        assert session.exec(select(User).where(User.email == OLENA)).first() is None
    for _ in range(4):
        assert send(admin_client, school) == 303
    assert send(admin_client, school) == 429
    assert len(outbox) == 4


def test_the_address_is_normalised(
    admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    assert send(admin_client, school, "  Olena@Example.org ") == 303
    assert outbox[-1].to == OLENA


def test_a_signed_in_teacher_accepting_someone_elses_invitation(
    client_as: ClientAs, admin_client: TestClient, outbox: list[EmailMessage], school: int
) -> None:
    """FR-055: the page shows the invited person's data, and acceptance acts only on them; the
    browser's own session is unchanged."""
    teacher = client_as(TEACHER_EMAIL)
    send(admin_client, school)
    token = token_from(outbox[-1])
    page = teacher.get(f"/invitations/{token}")
    assert page.status_code == 200
    assert OLENA in page.text
    assert agree(teacher, token) == 303
    assert teacher.get("/teacher").status_code == 200
    assert "Teacher" in html.role_label(teacher.get("/teacher").text)
    with Session(app.state.engine) as session:
        cast = session.exec(select(User).where(User.email == TEACHER_EMAIL)).one()
        assert cast.first_name is None
        olena = session.exec(select(User).where(User.email == OLENA)).one()
        assert olena.first_name == "Olena"
