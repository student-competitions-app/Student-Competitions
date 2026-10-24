"""HTTP contract for the home page and the friendly not-found page.

See specs/001-hello-world-page/contracts/http-routes.md and, for the question list,
specs/003-database-questions/contracts/http-routes.md#get---home-page. Every test that uses
`client` runs once per database engine.

The home page is private since milestone 4, so its tests use `admin_client`, signed in through a
session created directly in the database; `client` stays anonymous
(specs/004-email-otp-auth/research.md#d15).
"""

import re
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, delete

import app.routers.pages as pages
from app.core.config import APP_NAME, APP_VERSION, COMMIT_SHA
from app.core.migrations import head_revision
from app.core.templates import SHORT_COMMIT_LENGTH
from app.models import Question
from app.schemas.question import QuestionCreate
from app.services.questions import create_question
from tests import html
from tests.conftest import ADMIN_EMAIL, STUDENT_EMAIL, TEACHER_EMAIL, ClientAs

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
# The question list (milestone 3)
# ---------------------------------------------------------------------------------------------

UNAVAILABLE_NOTICE = (
    "status",
    "Question data is temporarily unavailable. Please try again in a moment.",
)


def _questions_section(body: str) -> html.Element | None:
    sections = [s for s in html.parse(body).find_all("section") if s.attrs.get("id") == "questions"]
    assert len(sections) <= 1, f"expected at most one questions section, found {len(sections)}"
    return sections[0] if sections else None


def _question_lists(body: str) -> list[html.Element]:
    section = _questions_section(body)
    return section.find_all("ol") if section is not None else []


def _question_items(body: str) -> list[str]:
    """The raw (still escaped, line breaks kept) contents of each item of the question list."""
    lists = _question_lists(body)
    assert len(lists) == 1, f"expected one question list, found {len(lists)}"
    return [body[li.inner_start : li.inner_end] for li in lists[0].find_all("li")]


def _status_lines(body: str) -> list[html.Element]:
    """The database status line: the one element carrying the machine-readable attributes."""
    return [e for e in html.parse(body).iter() if "data-engine" in e.attrs]


def _fail_database_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(pages, "list_questions", failing)


def test_home_has_the_questions_section(admin_client: TestClient) -> None:
    section = _questions_section(admin_client.get("/").text)
    assert section is not None
    headings = section.find_all("h2")
    assert [h.text() for h in headings] == ["Sample questions"]
    assert section.attrs.get("aria-labelledby") == headings[0].attrs.get("id")


def test_home_lists_the_sample_questions_once_each_in_order(
    admin_client: TestClient, sample_questions: list[dict[str, str]]
) -> None:
    """Compared with `markupsafe.escape`, which is what Jinja uses (`"` becomes `&#34;`)."""
    expected = [str(escape(sample["text"])) for sample in sample_questions]
    assert _question_items(admin_client.get("/").text) == expected


def test_home_keeps_the_line_break_inside_the_ukrainian_sample(
    admin_client: TestClient, sample_questions: list[dict[str, str]]
) -> None:
    multiline = [sample["text"] for sample in sample_questions if "\n" in sample["text"]]
    assert multiline, "the samples should include a multi-line question"
    assert all(text in _question_items(admin_client.get("/").text) for text in multiline)


def test_home_never_shows_a_reference_answer(
    admin_client: TestClient, sample_questions: list[dict[str, str]]
) -> None:
    body = admin_client.get("/").text
    for sample in sample_questions:
        answer = sample["reference_answer"]
        assert answer not in body
        assert str(escape(answer)) not in body


def test_home_has_no_write_affordance(admin_client: TestClient) -> None:
    """No form or button in the page's content: only the header's own forms (Log out), and no
    link out of a list item (US1-2, FR-018)."""
    body = admin_client.get("/").text
    assert [f.action for f in html.forms(body, within="header")] == ["/logout"]
    main = html.parse(body).find_all("main")[0]
    assert main.find_all("form") == []
    assert main.find_all("button") == []
    assert all("<a" not in item for item in _question_items(body))


def test_question_text_is_escaped(admin_client: TestClient, session: Session) -> None:
    session.add(Question(text="<b>bold</b> & more", reference_answer="x"))
    session.commit()
    body = admin_client.get("/").text
    assert "&lt;b&gt;bold&lt;/b&gt; &amp; more" in body
    assert "<b>bold</b>" not in body


def test_home_shows_an_empty_state_when_there_are_no_questions(
    admin_client: TestClient, session: Session
) -> None:
    session.exec(delete(Question))
    session.commit()
    body = admin_client.get("/").text
    assert "No questions yet." in html.text(body, "main")
    assert _question_lists(body) == []


def test_home_shows_the_same_list_on_every_load(admin_client: TestClient) -> None:
    lists = [_question_items(admin_client.get("/").text) for _ in range(3)]
    assert lists[0] == lists[1] == lists[2]


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
    assert _question_lists(body) == []
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


@pytest.mark.parametrize("failing_read", ["list_questions", "read_database_status"])
def test_a_failing_read_replaces_both_the_list_and_the_status_line(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch, failing_read: str
) -> None:
    def failing(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(pages, failing_read, failing)
    body = admin_client.get("/").text
    assert UNAVAILABLE_NOTICE in html.notices(body)
    assert _question_lists(body) == []
    assert _status_lines(body) == []


def test_home_lists_500_questions_quickly(
    admin_client: TestClient, session: Session, sample_questions: list[dict[str, str]]
) -> None:
    """SC-005: the page stays fast with a realistic bank, samples first, then creation order."""
    for i in range(500):
        create_question(
            session, QuestionCreate(text=f"Question {i:03d}", reference_answer="Answer.")
        )

    started = time.perf_counter()
    response = admin_client.get("/")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 3, f"GET / took {elapsed:.2f}s with 506 questions"
    items = _question_items(response.text)
    assert len(items) == 506
    assert items[:6] == [str(escape(sample["text"])) for sample in sample_questions]
    assert items[6:] == [f"Question {i:03d}" for i in range(500)]
