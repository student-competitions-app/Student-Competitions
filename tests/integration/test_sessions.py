"""Sessions end when they should: at logout, after 14 days, when the user is deactivated, and
when their current role is no longer held.

See specs/004-email-otp-auth/contracts/http-routes.md#session-cookie, the spec's user story 4,
and, for the current role, specs/005-roles-authorization/contracts/auth-services.md (rows G1–G6).
Every test runs once per database engine.
"""

from datetime import timedelta

import pytest
from fastapi.responses import Response
from fastapi.testclient import TestClient
from sqlalchemy import func, update
from sqlmodel import Session, select

from app.core.auth import set_session_cookie
from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.security import (
    SESSION_COOKIE_NAME,
    hash_token,
    new_session_token,
    sign_cookie_value,
)
from app.main import app
from app.models import Role, User, UserRole, UserSession
from app.services.email import EmailMessage
from app.services.sessions import create_session, get_session_identity
from app.services.users import get_active_user_by_email
from tests.conftest import ADMIN_EMAIL, ADMIN_STUDENT_EMAIL, ClientAs, sign_in_directly
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
        token = create_session(db_session, user, Role.ADMIN, now=utc_now() + created_at_offset)
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


# ---------------------------------------------------------------------------------------------
# The current role (milestone 5): rows G1–G6
# ---------------------------------------------------------------------------------------------


def make_user(session: Session, email: str, *roles: Role) -> User:
    user = User(email=email, is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    for role in roles:
        session.add(UserRole(user_id=user.id, role=role, created_at=utc_now()))
    session.commit()
    return user


def stored_session(session: Session, token: str) -> UserSession | None:
    session.expire_all()
    statement = select(UserSession).where(UserSession.token_hash == hash_token(token))
    return session.exec(statement).first()


def store_current_role(session: Session, token: str, value: str | None) -> None:
    """Write any value, even one no code path writes, straight into the session row."""
    session.execute(
        update(UserSession)
        .where(UserSession.token_hash == hash_token(token))  # type: ignore[arg-type]
        .values(current_role=value)
    )
    session.commit()


def test_g1_an_unknown_or_expired_token_is_nobody(session: Session) -> None:
    user = make_user(session, "a@example.org", Role.ADMIN)
    assert get_session_identity(session, new_session_token()) is None
    expired = create_session(session, user, Role.ADMIN, now=utc_now() - timedelta(days=15))
    assert get_session_identity(session, expired) is None


def test_g2_a_user_with_no_roles_is_nobody(session: Session) -> None:
    user = make_user(session, "a@example.org")
    assert get_session_identity(session, create_session(session, user, None)) is None


def test_g3_no_role_and_one_held_stores_it(session: Session) -> None:
    """The upgrade of a session from before milestone 5 (SC-010)."""
    user = make_user(session, "t@example.org", Role.TEACHER)
    token = create_session(session, user, None)
    identity = get_session_identity(session, token)
    assert identity is not None
    assert identity.user.email == "t@example.org"
    assert identity.roles == (Role.TEACHER,)
    assert identity.current_role == Role.TEACHER
    row = stored_session(session, token)
    assert row is not None and row.current_role == "teacher"


def test_g4_no_role_and_several_held_stays_unchosen(session: Session) -> None:
    user = make_user(session, "m@example.org", Role.STUDENT, Role.ADMIN)
    token = create_session(session, user, None)
    identity = get_session_identity(session, token)
    assert identity is not None
    assert identity.roles == (Role.ADMIN, Role.STUDENT)
    assert identity.current_role is None
    row = stored_session(session, token)
    assert row is not None and row.current_role is None


def test_g5_a_held_current_role_is_kept(session: Session) -> None:
    user = make_user(session, "m@example.org", Role.ADMIN, Role.STUDENT)
    token = create_session(session, user, Role.STUDENT)
    identity = get_session_identity(session, token)
    assert identity is not None
    assert identity.current_role == Role.STUDENT


@pytest.mark.parametrize("value", ["student", "superuser"])
def test_g6_a_current_role_not_held_ends_the_session(session: Session, value: str) -> None:
    """FR-017: a role no longer held, or one that does not exist."""
    user = make_user(session, "a@example.org", Role.ADMIN)
    token = create_session(session, user, Role.ADMIN)
    store_current_role(session, token, value)
    assert get_session_identity(session, token) is None
    assert stored_session(session, token) is None


def test_a_pre_milestone_session_keeps_working(client: TestClient, session: Session) -> None:
    """SC-010, spec edge case: an administrator signed in before the release is not signed out,
    and their session now records the administrator role."""
    token = sign_in_directly(client, ADMIN_EMAIL, None)
    assert client.get("/", follow_redirects=False).status_code == 200
    row = stored_session(session, token)
    assert row is not None and row.current_role == "admin"


def test_a_current_role_no_longer_held_signs_out(client_as: ClientAs, session: Session) -> None:
    """FR-017: the request is anonymous and the session row is gone."""
    signed_in = client_as(ADMIN_EMAIL)
    token = signed_in.cookies[SESSION_COOKIE_NAME].split(".")[0]
    store_current_role(session, token, "student")
    response = signed_in.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F"
    assert stored_session(session, token) is None


def test_a_pre_milestone_session_with_several_roles_goes_to_the_role_choice(
    client: TestClient, session: Session
) -> None:
    """Spec edge case: the session is kept, with no role, until one is chosen."""
    token = sign_in_directly(client, ADMIN_STUDENT_EMAIL, None)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/role?next=%2F"
    row = stored_session(session, token)
    assert row is not None and row.current_role is None
