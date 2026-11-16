"""Where the database status line is shown (milestone 12.6, user story 4).

See specs/012.6-role-landing-area/contracts/http-routes.md "Every administrator area page". The
line moved from the home page to the footer of every administrator area page; a teacher never sees
it, and a student keeps it on the home page. A failed read leaves only the line out. Every test runs
once per database engine.
"""

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.routers.admin import ADMIN_TABS
from app.routers.teacher import TEACHER_TABS
from app.services import database_status
from tests import html
from tests.conftest import STUDENT_EMAIL, TEACHER_EMAIL, ClientAs

ADMIN_PAGES = [
    *[tab.path for tab in ADMIN_TABS],
    "/admin/subjects/new",
    "/admin/components",
]
"""Every tab, a page inside a tab, and the component gallery (served outside production)."""


def footer_lines(body: str) -> list[html.Element]:
    """The status line: the elements carrying `data-engine`, which must all be in the footer."""
    lines = [e for e in html.parse(body).iter() if "data-engine" in e.attrs]
    footer = html.region(body, "footer")
    for line in lines:
        assert f'data-boots="{line.attrs["data-boots"]}"' in footer, "the line is not in the footer"
    return lines


def assert_one_line(body: str, engine: str) -> None:
    (line,) = footer_lines(body)
    assert line.attrs["data-engine"] == engine
    assert int(line.attrs["data-boots"]) > 0


def engine_of(request: pytest.FixtureRequest) -> str:
    return request.node.callspec.params["database_url"]


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_every_administrator_page_shows_the_line(
    admin_client: TestClient, request: pytest.FixtureRequest, path: str
) -> None:
    """US4 scenario 1, FR-010."""
    response = admin_client.get(path)
    assert response.status_code == 200
    assert_one_line(response.text, engine_of(request))


def test_a_page_shown_again_with_form_errors_shows_the_line(
    admin_client: TestClient, request: pytest.FixtureRequest
) -> None:
    """FR-010: pages shown again with form errors keep the line."""
    response = admin_client.post("/admin/subjects", data={"name": ""})
    assert response.status_code == 400
    assert_one_line(response.text, engine_of(request))


@pytest.mark.parametrize("path", [tab.path for tab in TEACHER_TABS])
def test_no_teacher_page_shows_the_line(client_as: ClientAs, path: str) -> None:
    """US4 scenario 2, FR-011."""
    response = client_as(TEACHER_EMAIL).get(path)
    assert response.status_code == 200
    assert footer_lines(response.text) == []


def test_the_student_s_home_page_keeps_the_line(
    client_as: ClientAs, request: pytest.FixtureRequest
) -> None:
    """US4 scenario 3, FR-012."""
    assert_one_line(client_as(STUDENT_EMAIL).get("/").text, engine_of(request))


def test_a_failed_read_leaves_only_the_line_out(
    admin_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    database_url: str,
) -> None:
    """US4 scenario 4, FR-013, SC-005: the page renders, without the line and without any error
    detail, and the log names the error by type and message, never the database address."""

    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(database_status, "read_database_status", failing)
    with caplog.at_level(logging.ERROR):
        response = admin_client.get("/admin/subjects")
    assert response.status_code == 200
    assert html.h1(response.text)
    assert footer_lines(response.text) == []
    for detail in ("OperationalError", "boom", "SELECT"):
        assert detail not in response.text
    messages = [record.getMessage() for record in caplog.records]
    assert any(m.startswith("Database status unavailable: OperationalError: ") for m in messages)
    assert not [m for m in messages if database_url in m]
