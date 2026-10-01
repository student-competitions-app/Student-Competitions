"""The two-step sign-in, end to end: email → code from the outbox → session → logout.

See specs/004-email-otp-auth/contracts/http-routes.md (`/login`, `/login/code`, `/logout`) and
the spec's user stories 1 and 2. Every test runs once per database engine.
"""

import re
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from markupsafe import escape
from sqlalchemy import func, update
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

import app.routers.auth as auth_router
from app.core.db import utc_now
from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.models import LoginCode, UserSession
from app.services.email import EmailMessage
from tests.conftest import ADMIN_EMAIL, STUDENT_EMAIL, TEACHER_EMAIL

SENT_NOTICE = (
    "If this address belongs to an account, we have sent a code to it. "
    "The code is valid for 20 minutes."
)
INVALID_CODE = "Invalid or expired code. Request a new code if needed."
INVALID_EMAIL = "Enter a valid email address."
UNAVAILABLE = "Sign-in is temporarily unavailable. Please try again in a moment."


def code_from(message: EmailMessage) -> str:
    match = re.search(r"sign-in code is: ([0-9]{6})", message.text)
    assert match is not None, "the email carries no code"
    return match.group(1)


def request_code(
    client: TestClient, email: str = ADMIN_EMAIL, next_path: str = "/"
) -> httpx2.Response:
    return client.post("/login", data={"email": email, "next": next_path})


def submit_code(
    client: TestClient, code: str, email: str = ADMIN_EMAIL, next_path: str = "/"
) -> httpx2.Response:
    return client.post(
        "/login/code",
        data={"email": email, "code": code, "next": next_path},
        follow_redirects=False,
    )


def sign_in(
    client: TestClient, outbox: list[EmailMessage], next_path: str = "/"
) -> httpx2.Response:
    assert request_code(client, next_path=next_path).status_code == 200
    return submit_code(client, code_from(outbox[-1]), next_path=next_path)


def session_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(UserSession)).one()


def fail(*args: Any, **kwargs: Any) -> Any:
    raise OperationalError("SELECT 1", {}, Exception("boom"))


# ---------------------------------------------------------------------------------------------
# End to end (US1-1, US1-3)
# ---------------------------------------------------------------------------------------------


def test_the_login_page_has_the_email_form(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    body = response.text
    assert 'action="/login"' in body
    assert 'name="email"' in body
    assert 'type="email"' in body
    assert '<input type="hidden" name="next" value="/">' in body


def test_sign_in_end_to_end(client: TestClient, outbox: list[EmailMessage]) -> None:
    step2 = request_code(client)
    assert step2.status_code == 200
    assert SENT_NOTICE in step2.text
    assert len(outbox) == 1
    assert outbox[0].to == ADMIN_EMAIL

    signed_in = submit_code(client, code_from(outbox[0]))
    assert signed_in.status_code == 303
    assert signed_in.headers["location"] == "/"
    assert f"{SESSION_COOKIE_NAME}=" in signed_in.headers["set-cookie"]

    home = client.get("/")
    assert home.status_code == 200
    header = re.search(r"<header.*?</header>", home.text, re.DOTALL)
    assert header is not None
    assert ADMIN_EMAIL in header.group(0)
    assert 'action="/logout"' in header.group(0)


def test_the_next_page_is_carried_through_both_steps(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US1-2."""
    page = client.get("/login", params={"next": "/?x=1"})
    assert 'name="next" value="/?x=1"' in page.text
    step2 = request_code(client, next_path="/?x=1")
    assert 'name="next" value="/?x=1"' in step2.text
    response = submit_code(client, code_from(outbox[-1]), next_path="/?x=1")
    assert response.headers["location"] == "/?x=1"


def test_the_address_is_normalised(client: TestClient, outbox: list[EmailMessage]) -> None:
    """US1-4."""
    assert request_code(client, email="  Admin@Example.COM ").status_code == 200
    assert [message.to for message in outbox] == [ADMIN_EMAIL]
    response = submit_code(client, code_from(outbox[-1]), email=" ADMIN@example.com")
    assert response.status_code == 303


def test_a_used_code_cannot_be_reused(client: TestClient, outbox: list[EmailMessage]) -> None:
    """US1-5."""
    assert sign_in(client, outbox).status_code == 303
    again = submit_code(client, code_from(outbox[-1]))
    assert again.status_code == 400
    assert INVALID_CODE in again.text


def test_an_expired_code_is_refused(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    """US1-6: the code's expiry moved into the past, as if 20 minutes had gone by."""
    request_code(client)
    session.execute(update(LoginCode).values(expires_at=utc_now()))
    session.commit()
    response = submit_code(client, code_from(outbox[-1]))
    assert response.status_code == 400
    assert INVALID_CODE in response.text


def test_step_two_offers_a_new_code_and_a_different_email(client: TestClient) -> None:
    """US1-7, FR-014."""
    body = request_code(client, next_path="/?x=1").text
    forms = re.findall(r'<form method="post" action="(/login(?:/code)?)">(.*?)</form>', body, re.S)
    actions = [action for action, _ in forms]
    assert actions == ["/login/code", "/login"]
    resend_form = forms[1][1]
    assert f'name="email" value="{ADMIN_EMAIL}"' in resend_form
    assert 'name="next" value="/?x=1"' in resend_form
    assert "Send a new code" in resend_form
    code_form = forms[0][1]
    assert 'name="code"' in code_form
    assert 'autocomplete="one-time-code"' in code_form
    assert 'inputmode="numeric"' in code_form
    assert '<a href="/login?next=/%3Fx%3D1">Use a different email</a>' in body


def test_the_code_may_have_surrounding_spaces(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """L7."""
    request_code(client)
    assert submit_code(client, f"  {code_from(outbox[-1])} ").status_code == 303


def test_a_double_submit_creates_one_session(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    request_code(client)
    code = code_from(outbox[-1])
    assert submit_code(client, code).status_code == 303
    assert submit_code(client, code).status_code == 400
    assert session_count(session) == 1


@pytest.mark.parametrize("email", ["", "   ", "not-an-email", "a@b"])
def test_an_invalid_address_is_refused_without_side_effects(
    client: TestClient, outbox: list[EmailMessage], session: Session, email: str
) -> None:
    response = request_code(client, email=email)
    assert response.status_code == 400
    assert INVALID_EMAIL in response.text
    assert 'action="/login"' in response.text
    assert f'value="{escape(email)}"' in response.text
    assert outbox == []
    assert session.exec(select(func.count()).select_from(LoginCode)).one() == 0


def test_an_unknown_address_gets_the_same_page_and_no_email(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    response = request_code(client, email="nobody@example.com")
    assert response.status_code == 200
    assert SENT_NOTICE in response.text
    assert outbox == []


def test_a_tampered_hidden_email_does_not_verify(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    request_code(client)
    response = submit_code(client, code_from(outbox[-1]), email="other@example.com")
    assert response.status_code == 400
    assert INVALID_CODE in response.text


def test_the_email_has_no_link(client: TestClient, outbox: list[EmailMessage]) -> None:
    request_code(client)
    assert "http" not in outbox[-1].text


def test_requesting_a_code_while_the_database_is_down_is_a_friendly_503(
    client: TestClient, outbox: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_router, "allow_code_request", fail)
    response = request_code(client)
    assert response.status_code == 503
    assert UNAVAILABLE in response.text
    assert 'action="/login"' in response.text
    for detail in ("OperationalError", "boom", "Traceback"):
        assert detail not in response.text
    assert outbox == []


def test_verifying_while_the_database_is_down_is_a_friendly_503(
    client: TestClient, outbox: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
    request_code(client)
    monkeypatch.setattr(auth_router, "verify_code", fail)
    response = submit_code(client, code_from(outbox[-1]))
    assert response.status_code == 503
    assert UNAVAILABLE in response.text
    for detail in ("OperationalError", "boom", "Traceback"):
        assert detail not in response.text


def test_logout_ends_the_session(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    sign_in(client, outbox)
    assert session_count(session) == 1
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "Max-Age=0" in cookie
    assert session_count(session) == 0


# ---------------------------------------------------------------------------------------------
# Every page is private unless explicitly public (US2)
# ---------------------------------------------------------------------------------------------


def test_the_home_page_sends_anonymous_visitors_to_login(client: TestClient) -> None:
    """US2-1."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F"


def test_the_query_string_survives_the_whole_round_trip(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US2-1, edge case: a protected page's own query string is preserved exactly."""
    response = client.get("/?a=1&b=2", follow_redirects=False)
    assert response.headers["location"] == "/login?next=%2F%3Fa%3D1%26b%3D2"
    login = client.get(response.headers["location"])
    assert 'name="next" value="/?a=1&amp;b=2"' in login.text
    signed_in = sign_in(client, outbox, next_path="/?a=1&b=2")
    assert signed_in.headers["location"] == "/?a=1&b=2"


def test_the_public_routes_are_served_anonymously(client: TestClient) -> None:
    """US2-2: none of them is redirected to the login page with a `next`."""
    assert client.get("/login", follow_redirects=False).status_code == 200
    logout = client.post("/logout", follow_redirects=False)
    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"
    assert client.get("/healthz", follow_redirects=False).status_code == 200
    assert client.get("/static/css/app.css", follow_redirects=False).status_code == 200


@pytest.mark.parametrize(
    "next_path", ["https://evil.example/", "//evil.example", "/\\evil.example", "/login", "/logout"]
)
def test_an_unsafe_next_lands_on_the_home_page(
    client: TestClient, outbox: list[EmailMessage], next_path: str
) -> None:
    """US2-3."""
    assert sign_in(client, outbox, next_path=next_path).headers["location"] == "/"


def test_a_signed_in_user_opening_login_goes_where_they_were_heading(
    admin_client: TestClient,
) -> None:
    """US2-5, FR-031."""
    response = admin_client.get("/login", params={"next": "/?x=1"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/?x=1"
    response = admin_client.get("/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_an_unknown_path_is_a_not_found_page_not_a_redirect(client: TestClient) -> None:
    response = client.get("/no-such-page", follow_redirects=False)
    assert response.status_code == 404
    assert "<html" in response.text


def test_a_garbage_cookie_is_simply_anonymous(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, "garbage")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F"


# ---------------------------------------------------------------------------------------------
# Roles (milestone 5)
# ---------------------------------------------------------------------------------------------


def test_a_single_role_person_signs_in_exactly_as_before(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    """SC-003, US1-1, FR-012: no role-choice step; the session starts in the one role held."""
    start = client.get("/teacher", follow_redirects=False)
    assert start.headers["location"] == "/login?next=%2Fteacher"
    assert request_code(client, email=TEACHER_EMAIL, next_path="/teacher").status_code == 200
    response = submit_code(client, code_from(outbox[-1]), email=TEACHER_EMAIL, next_path="/teacher")
    assert response.status_code == 303
    assert response.headers["location"] == "/teacher"
    [row] = session.exec(select(UserSession)).all()
    assert row.current_role == "teacher"
    landed = client.get("/teacher")
    assert landed.status_code == 200
    assert '<span class="site-role">· Teacher</span>' in landed.text


def test_a_person_on_no_list_gets_no_code(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """FR-010, US2-5: removed from every list, a person is answered like anyone else, is sent
    nothing, and a code they already had stops working."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("STUDENT_EMAILS", STUDENT_EMAIL)
    with TestClient(app) as before:
        request_code(before, email=STUDENT_EMAIL)
        old_code = code_from(app.state.email_sender.outbox[-1])

    monkeypatch.setenv("STUDENT_EMAILS", "")
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)
    with TestClient(app) as after:
        removed = request_code(after, email=STUDENT_EMAIL)
        unknown = request_code(after, email="nobody@example.com")
        assert removed.status_code == unknown.status_code == 200
        assert removed.text.replace(STUDENT_EMAIL, "X") == unknown.text.replace(
            "nobody@example.com", "X"
        )
        assert app.state.email_sender.outbox == []
        response = submit_code(after, old_code, email=STUDENT_EMAIL)
        assert response.status_code == 400
        assert INVALID_CODE in response.text
