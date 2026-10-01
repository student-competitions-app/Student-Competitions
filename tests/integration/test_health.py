"""HTTP contract for the service status endpoint.

See specs/002-public-deploy-cicd/contracts/http-routes.md#get-healthz--service-status.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import app.core.auth as auth
import app.routers.pages as pages
from app.core.config import APP_VERSION
from app.core.security import SESSION_COOKIE_NAME
from tests.conftest import ADMIN_EMAIL, sign_in_directly


def test_healthz_returns_ok(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_healthz_is_json(client: TestClient) -> None:
    """Render's health checker and a shell script are the audience — not a browser."""
    response = client.get("/healthz")
    assert response.headers["content-type"] == "application/json"


def test_healthz_has_exactly_the_three_documented_keys(client: TestClient) -> None:
    """Exactly three: anything varying per request would leak infrastructure detail on an
    unauthenticated endpoint and make the payload unstable to assert against."""
    assert set(client.get("/healthz").json()) == {"status", "version", "commit"}


def test_healthz_status_is_ok(client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"


def test_healthz_reports_the_application_version(client: TestClient) -> None:
    assert client.get("/healthz").json()["version"] == APP_VERSION


def test_healthz_commit_is_a_non_empty_string(client: TestClient) -> None:
    """`"unknown"` on an unstamped local run, a 40-character SHA once deployed — never empty."""
    commit = client.get("/healthz").json()["commit"]
    assert isinstance(commit, str)
    assert commit


def test_healthz_stays_ok_while_the_database_is_failing(
    client: TestClient, admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liveness never depends on the database, so a blip cannot make Render restart a healthy
    process in a loop (FR-029)."""

    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(pages, "list_questions", failing)

    home = admin_client.get("/")
    assert home.status_code == 200
    assert "Question data is temporarily unavailable" in home.text

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert set(health.json()) == {"status", "version", "commit"}


@pytest.mark.parametrize("cookie", ["signed", "garbage"])
def test_healthz_with_a_cookie_does_no_session_lookup(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, cookie: str
) -> None:
    """The health check stays free of I/O even when a browser sends its session cookie: the
    access dependency returns before reading it (milestone 2 contract, research D4)."""

    def failing(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("/healthz must not look up a session")

    if cookie == "signed":
        token = sign_in_directly(client, ADMIN_EMAIL)
        assert token
    else:
        client.cookies.set(SESSION_COOKIE_NAME, "garbage")
    monkeypatch.setattr(auth, "get_session_identity", failing)
    monkeypatch.setattr(auth, "Session", failing)

    response = client.get("/healthz")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "version", "commit"}
