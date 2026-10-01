"""No write submitted from another site is processed (FR-021, research D7).

The rule runs before the session is read, for every unsafe request: choosing or switching a
role, logging out, and signing in. Every test runs once per database engine.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.core.auth as auth
from app.core.security import SESSION_COOKIE_NAME, hash_token
from app.models import Role, UserSession
from tests.conftest import ADMIN_EMAIL, ADMIN_STUDENT_EMAIL, ClientAs

REFUSED = "This request was refused because it did not come from this site."
CROSS_SITE_HEADERS = [
    {"Sec-Fetch-Site": "cross-site"},
    {"Origin": "https://evil.example"},
]


def current_role(session: Session, browser: TestClient) -> str | None:
    token = browser.cookies[SESSION_COOKIE_NAME].split(".")[0]
    session.expire_all()
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    return row.one().current_role


@pytest.mark.parametrize("forged", CROSS_SITE_HEADERS)
def test_a_cross_site_switch_changes_nothing(
    client_as: ClientAs, session: Session, forged: dict[str, str]
) -> None:
    """US4-6."""
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)
    response = browser.post("/role", data={"role": "student"}, headers=forged)
    assert response.status_code == 403
    assert "<h1>Request refused</h1>" in response.text
    assert REFUSED in response.text
    assert current_role(session, browser) == "admin"


def test_a_cross_site_logout_changes_nothing(client_as: ClientAs) -> None:
    browser = client_as(ADMIN_EMAIL)
    response = browser.post("/logout", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert browser.get("/", follow_redirects=False).status_code == 200


def test_a_cross_site_sign_in_is_refused(client: TestClient) -> None:
    """Closes milestone 4's accepted login-CSRF risk."""
    response = client.post(
        "/login/code",
        data={"email": ADMIN_EMAIL, "code": "123456"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert REFUSED in response.text


def test_the_refusal_happens_before_any_database_access(
    client_as: ClientAs, monkeypatch: pytest.MonkeyPatch
) -> None:
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)

    def failing(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a cross-site request must not look up a session")

    monkeypatch.setattr(auth, "get_session_identity", failing)
    monkeypatch.setattr(auth, "Session", failing)
    response = browser.post(
        "/role", data={"role": "student"}, headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize("own", [{"Sec-Fetch-Site": "same-origin"}, {}])
def test_this_sites_own_writes_are_accepted(
    client_as: ClientAs, session: Session, own: dict[str, str]
) -> None:
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)
    response = browser.post("/role", data={"role": "student"}, headers=own, follow_redirects=False)
    assert response.status_code == 303
    assert current_role(session, browser) == "student"


def test_a_cross_site_page_view_is_unaffected(client_as: ClientAs) -> None:
    """Arriving by a link from another site still works: `GET` changes nothing."""
    browser = client_as(ADMIN_EMAIL)
    assert browser.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200
