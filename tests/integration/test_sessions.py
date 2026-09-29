"""Sessions end when they should: at logout, after 14 days, and when the user is deactivated.

See specs/004-email-otp-auth/contracts/http-routes.md#session-cookie and the spec's user story 4.
Every test runs once per database engine.
"""

from datetime import timedelta

from fastapi.responses import Response
from fastapi.testclient import TestClient
from sqlalchemy import func, update
from sqlmodel import Session, select

from app.core.auth import set_session_cookie
from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.security import (
    SESSION_COOKIE_NAME,
    new_session_token,
    sign_cookie_value,
)
from app.main import app
from app.models import User, UserSession
from app.services.email import EmailMessage
from app.services.sessions import create_session
from app.services.users import get_active_user_by_email
from tests.conftest import ADMIN_EMAIL, sign_in_directly
from tests.integration.test_login_flow import sign_in


def is_signed_in(client: TestClient) -> bool:
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {200, 303}, response.status_code
    return response.status_code == 200


def session_rows(session: Session) -> int:
    session.expire_all()
    return session.exec(select(func.count()).select_from(UserSession)).one()


def use_session_created_at(client: TestClient, created_at_offset: timedelta) -> None:
    with Session(app.state.engine) as db_session:
        user = get_active_user_by_email(db_session, ADMIN_EMAIL)
        assert user is not None
        token = create_session(db_session, user, now=utc_now() + created_at_offset)
    client.cookies.set(SESSION_COOKIE_NAME, sign_cookie_value(app.state.settings.secret_key, token))


def cookie_attributes(set_cookie: str) -> dict[str, str]:
    """The attributes of one `Set-Cookie` header, names lowercased, values as sent."""
    parts = [part.strip() for part in set_cookie.split(";")]
    attributes: dict[str, str] = {}
    for part in parts[1:]:
        name, _, value = part.partition("=")
        attributes[name.lower()] = value
    return attributes


def test_us4_1_logout_deletes_the_session_and_clears_the_cookie(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    sign_in(client, outbox)
    assert session_rows(session) == 1
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    cleared = cookie_attributes(response.headers["set-cookie"])
    assert cleared["max-age"] == "0"
    assert cleared["path"] == "/"
    assert "httponly" in cleared
    assert cleared["samesite"].lower() == "lax"
    assert session_rows(session) == 0
    assert not is_signed_in(client)


def test_us4_2_a_copied_cookie_is_useless_after_logout(admin_client: TestClient) -> None:
    copy = admin_client.cookies[SESSION_COOKIE_NAME]
    admin_client.post("/logout")
    replay = TestClient(app)
    replay.cookies.set(SESSION_COOKIE_NAME, copy)
    assert not is_signed_in(replay)


def test_us4_3_a_session_lasts_at_most_14_days(client: TestClient) -> None:
    use_session_created_at(client, -timedelta(days=14, seconds=1))
    assert not is_signed_in(client)
    use_session_created_at(client, -timedelta(days=13))
    assert is_signed_in(client)


def test_us4_4_deactivation_ends_the_session_on_the_next_request(
    admin_client: TestClient, session: Session
) -> None:
    assert is_signed_in(admin_client)
    session.execute(update(User).values(is_active=False))
    session.commit()
    assert not is_signed_in(admin_client)


def test_us4_6_logout_ends_only_that_browser(client: TestClient) -> None:
    laptop = TestClient(app)
    phone = TestClient(app)
    sign_in_directly(laptop, ADMIN_EMAIL)
    sign_in_directly(phone, ADMIN_EMAIL)
    laptop.post("/logout")
    assert not is_signed_in(laptop)
    assert is_signed_in(phone)


def _flip(char: str) -> str:
    return "A" if char != "A" else "B"


def test_a_tampered_or_foreign_cookie_is_simply_anonymous(admin_client: TestClient) -> None:
    good = admin_client.cookies[SESSION_COOKIE_NAME]
    token = good.split(".")[0]
    variants = {
        "flipped signature": good[:-1] + _flip(good[-1]),
        "rotated key": sign_cookie_value("r" * 32, token),
        "garbage": "garbage",
        "unknown token": sign_cookie_value(app.state.settings.secret_key, new_session_token()),
    }
    for name, value in variants.items():
        visitor = TestClient(app)
        visitor.cookies.set(SESSION_COOKIE_NAME, value)
        response = visitor.get("/", follow_redirects=False)
        assert response.status_code == 303, name
        assert response.headers["location"] == "/login?next=%2F", name


def test_a_plain_link_cannot_log_out(admin_client: TestClient) -> None:
    response = admin_client.get("/logout", follow_redirects=False)
    assert response.status_code == 405
    assert "<html" in response.text
    assert is_signed_in(admin_client)


def test_logging_out_while_anonymous_is_harmless(client: TestClient) -> None:
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_the_cookie_flags_locally(client: TestClient, outbox: list[EmailMessage]) -> None:
    response = sign_in(client, outbox)
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    attributes = cookie_attributes(set_cookie)
    assert "httponly" in attributes
    assert attributes["samesite"].lower() == "lax"
    assert attributes["path"] == "/"
    assert attributes["max-age"] == "1209600"
    assert "secure" not in attributes


def test_the_cookie_is_secure_in_production() -> None:
    settings = AuthSettings(
        production=True,
        email_backend="resend",
        secret_key="k" * 32,
        admin_emails=(),
        resend_api_key="re_x",
        email_from="login@example.org",
    )
    response = Response()
    set_session_cookie(response, settings, "token")
    assert "secure" in cookie_attributes(response.headers["set-cookie"])
