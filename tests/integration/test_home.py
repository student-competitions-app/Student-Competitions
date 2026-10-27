"""HTTP contract for the home page and the friendly not-found page.

See specs/001-hello-world-page/contracts/http-routes.md and
specs/003-database-questions/contracts/http-routes.md#get---home-page. Milestone 11 removed the
sample question list (specs/011-question-bank/spec.md US8); its replacements are at the end.
Every test that uses `client` runs once per database engine.

The home page is private since milestone 4, so its tests use `admin_client`, signed in through a
session created directly in the database; `client` stays anonymous
(specs/004-email-otp-auth/research.md#d15).
"""

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import app.routers.pages as pages
from app.core.config import APP_NAME, APP_TAGLINE, APP_VERSION, COMMIT_SHA
from app.core.migrations import head_revision
from app.core.templates import SHORT_COMMIT_LENGTH
from app.main import app
from app.models import Role
from app.routers.areas import areas_for
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    TEACHER_STUDENT_EMAIL,
    ClientAs,
    make_question,
    make_subject,
)

VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def test_app_name_is_non_empty() -> None:
    """Guard the containment assertion below from passing vacuously."""
    assert APP_NAME


def test_home_returns_ok(admin_client: TestClient) -> None:
    assert admin_client.get("/").status_code == 200


def test_home_redirects_anonymous_visitors_to_login(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F"


def test_home_header_shows_the_signed_in_email_and_a_logout_form(
    admin_client: TestClient,
) -> None:
    body = admin_client.get("/").text
    assert ADMIN_EMAIL in html.text(body, "header")
    logout = [f for f in html.forms(body, within="header") if f.action == "/logout"]
    assert len(logout) == 1
    assert logout[0].method == "post"
    assert [b.text for b in logout[0].buttons] == ["Log out"]


@pytest.mark.parametrize(
    ("email", "label"),
    [(ADMIN_EMAIL, "Administrator"), (TEACHER_EMAIL, "Teacher"), (STUDENT_EMAIL, "Student")],
)
def test_home_header_shows_the_current_role(client_as: ClientAs, email: str, label: str) -> None:
    """FR-031, US1-5: the application name and the current role, still with the address and
    Log out."""
    header = html.text(client_as(email).get("/").text, "header")
    assert APP_NAME in header
    assert label in header.replace(APP_NAME, "")
    assert email in header
    assert "Log out" in header


def test_home_is_html(admin_client: TestClient) -> None:
    response = admin_client.get("/")
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_home_shows_the_application_name(admin_client: TestClient) -> None:
    assert APP_NAME in admin_client.get("/").text


def test_home_headline_is_the_application_name(admin_client: TestClient) -> None:
    """Asserted against the <h1>, not the whole body: the shared layout and the error page also
    carry APP_NAME, so a body-wide check alone cannot tell the home page from a 404."""
    assert APP_NAME in html.h1(admin_client.get("/").text)


def test_home_has_a_non_empty_title(admin_client: TestClient) -> None:
    match = re.search(r"<title>(.*?)</title>", admin_client.get("/").text, re.DOTALL)
    assert match is not None, "the page has no <title>"
    assert match.group(1).strip()


def test_home_head_carries_the_viewport_meta(admin_client: TestClient) -> None:
    head = re.search(r"<head>(.*?)</head>", admin_client.get("/").text, re.DOTALL)
    assert head is not None, "the page has no <head>"
    assert VIEWPORT_META in head.group(1)


def test_unknown_path_returns_a_rendered_not_found_page(client: TestClient) -> None:
    response = client.get("/about")
    assert response.status_code == 404
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<html" in response.text


def _footer(body: str) -> str:
    return html.region(body, "footer")


def test_home_footer_reports_the_release(admin_client: TestClient) -> None:
    """The version and the commit are on the page itself, so which release is serving is visible
    without calling /healthz (FR-025)."""
    footer = _footer(admin_client.get("/").text)
    assert f"v{APP_VERSION}" in footer
    assert COMMIT_SHA[:SHORT_COMMIT_LENGTH] in footer


def test_home_footer_carries_the_full_commit(admin_client: TestClient) -> None:
    """The short form is what is read; the full value stays available on hover."""
    assert f'title="{COMMIT_SHA}"' in _footer(admin_client.get("/").text)


def test_error_page_reports_the_release_too(admin_client: TestClient) -> None:
    """The footer lives in the shared layout, so every page inherits it — including this one,
    which is rendered by an exception handler rather than by a router."""
    footer = _footer(admin_client.get("/about").text)
    assert f"v{APP_VERSION}" in footer
    assert COMMIT_SHA[:SHORT_COMMIT_LENGTH] in footer


# ---------------------------------------------------------------------------------------------
# The unavailable notice (milestone 3; the question list itself went in milestone 11)
# ---------------------------------------------------------------------------------------------

UNAVAILABLE_NOTICE = (
    "status",
    "Question data is temporarily unavailable. Please try again in a moment.",
)


def _questions_section(body: str) -> html.Element | None:
    sections = [s for s in html.parse(body).find_all("section") if s.attrs.get("id") == "questions"]
    assert len(sections) <= 1, f"expected at most one questions section, found {len(sections)}"
    return sections[0] if sections else None


def _status_lines(body: str) -> list[html.Element]:
    """The database status line: the one element carrying the machine-readable attributes."""
    return [e for e in html.parse(body).iter() if "data-engine" in e.attrs]


def _fail_database_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(pages, "read_database_status", failing)


def test_home_has_no_write_affordance(admin_client: TestClient) -> None:
    """No form or button in the page's content: only the header's own forms (the theme switch
    and Log out) (US1-2, FR-018)."""
    body = admin_client.get("/").text
    assert [f.action for f in html.forms(body, within="header")] == ["/theme", "/logout"]
    main = html.parse(body).find_all("main")[0]
    assert main.find_all("form") == []
    assert main.find_all("button") == []


def test_home_degrades_when_the_database_fails(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database blip still renders the page, with a notice and no error detail (FR-026)."""
    _fail_database_reads(monkeypatch)
    response = admin_client.get("/")
    body = response.text
    assert response.status_code == 200
    assert html.h1(body)
    assert html.region(body, "footer")
    assert UNAVAILABLE_NOTICE in html.notices(body)
    for detail in ("OperationalError", "boom", "SELECT"):
        assert detail not in body


# ---------------------------------------------------------------------------------------------
# The database status line (milestone 3)
# ---------------------------------------------------------------------------------------------

DISPLAY_NAMES = {"sqlite": "SQLite", "postgresql": "PostgreSQL"}


def _status_line(body: str) -> html.Element:
    lines = _status_lines(body)
    assert len(lines) == 1, f"expected one status line, found {len(lines)}"
    return lines[0]


def test_status_line_carries_the_machine_readable_attributes(
    admin_client: TestClient, request: pytest.FixtureRequest
) -> None:
    engine = request.node.callspec.params["database_url"]
    attributes = _status_line(admin_client.get("/").text).attrs
    assert attributes["data-engine"] == engine
    assert attributes["data-revision"] == head_revision()
    assert attributes["data-boots"] == "1"


def test_status_line_reads_as_text(
    admin_client: TestClient, request: pytest.FixtureRequest
) -> None:
    engine = request.node.callspec.params["database_url"]
    body = admin_client.get("/").text
    line = _status_line(body)
    assert body[line.inner_start : line.inner_end] == (
        f"Database: {DISPLAY_NAMES[engine]} · schema revision <code>{head_revision()}</code>"
        " · boot #1"
    )


def test_status_line_is_in_the_footer(admin_client: TestClient) -> None:
    """Milestone 10 FR-036: the database line moved from under the questions into the footer of
    the home page, in muted text (contracts/pages.md §4.1)."""
    body = admin_client.get("/").text
    status = _status_line(body)
    footer = html.parse(body).find_all("footer")[0]
    assert footer.inner_end is not None
    assert footer.inner_start < status.inner_start < footer.inner_end


def test_a_failing_read_replaces_the_status_line_with_the_notice(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_database_reads(monkeypatch)
    body = admin_client.get("/").text
    assert UNAVAILABLE_NOTICE in html.notices(body)
    assert _status_lines(body) == []


# ---------------------------------------------------------------------------------------------
# Milestone 10: the start page (US6-2 to US6-4, FR-035)
# ---------------------------------------------------------------------------------------------


def area_cards(body: str) -> list[tuple[str, str, str]]:
    """`(href, title, description)` of each card in the areas section."""
    sections = [s for s in html.parse(body).find_all("section") if s.attrs.get("id") == "areas"]
    assert len(sections) == 1
    found = []
    for card in sections[0].find_all("article"):
        (link,) = [a for a in card.find_all("a") if "href" in a.attrs]
        (description,) = [p for p in card.find_all("p") if "card-description" in p.classes()]
        found.append((link.attrs["href"], link.text(), description.text()))
    return found


@pytest.mark.parametrize(
    ("email", "role"),
    [
        (ADMIN_EMAIL, Role.ADMIN),
        (TEACHER_EMAIL, Role.TEACHER),
        (STUDENT_EMAIL, Role.STUDENT),
        (ADMIN_STUDENT_EMAIL, Role.ADMIN),
        (ADMIN_STUDENT_EMAIL, Role.STUDENT),
        (TEACHER_STUDENT_EMAIL, Role.TEACHER),
        (TEACHER_STUDENT_EMAIL, Role.STUDENT),
    ],
)
def test_one_card_per_allowed_area_with_its_description(
    client_as: ClientAs, email: str, role: Role
) -> None:
    body = client_as(email, role).get("/").text
    expected = [(area.path, area.title, area.description) for area in areas_for(role)]
    assert expected, "every role has at least one area"
    assert area_cards(body) == expected


def test_the_greeting_and_the_tagline(admin_client: TestClient) -> None:
    body = admin_client.get("/").text
    assert html.h1(body) == f"Welcome to {APP_NAME}"
    assert APP_TAGLINE in html.text(body, "main")


def test_unavailable_data_keeps_the_cards_and_drops_the_database_line(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_database_reads(monkeypatch)
    response = admin_client.get("/")
    assert response.status_code == 200
    assert UNAVAILABLE_NOTICE in html.notices(response.text)
    assert [href for href, _, _ in area_cards(response.text)] == ["/admin", "/staff"]
    assert _status_lines(response.text) == []


# ---------------------------------------------------------------------------------------------
# Milestone 11: the sample questions are gone (US8)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("email", [ADMIN_EMAIL, TEACHER_EMAIL, STUDENT_EMAIL])
def test_the_home_page_lists_no_questions(client_as: ClientAs, email: str) -> None:
    """US8-2, SC-007: no questions section, with the database line still in the footer."""
    body = client_as(email).get("/").text
    assert _questions_section(body) is None
    assert "Sample questions" not in body
    assert len(_status_lines(body)) == 1


def test_an_anonymous_visitor_sees_no_questions(client: TestClient) -> None:
    """US8-2: the home page sends them to sign in, and that page lists nothing either."""
    body = client.get("/").text
    assert _questions_section(body) is None
    assert "Sample questions" not in body


def test_a_stored_question_never_reaches_the_home_page(admin_client: TestClient) -> None:
    subject = make_subject(app.state.engine, "Physics")
    make_question(app.state.engine, subject, "A secret question?", "A secret answer.")
    body = admin_client.get("/").text
    assert "A secret question?" not in body
    assert "A secret answer." not in body


def test_the_unavailable_message_is_kept(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US8-3, FR-043: the page still renders, with its existing message."""
    _fail_database_reads(monkeypatch)
    response = admin_client.get("/")
    assert response.status_code == 200
    assert UNAVAILABLE_NOTICE in html.notices(response.text)


def test_the_teacher_card_mentions_the_question_bank(client_as: ClientAs) -> None:
    """US8-4, FR-044."""
    body = client_as(TEACHER_EMAIL).get("/").text
    assert (
        "/teacher",
        "Teacher area",
        "Manage your classes and students, and see the question bank.",
    ) in area_cards(body)
