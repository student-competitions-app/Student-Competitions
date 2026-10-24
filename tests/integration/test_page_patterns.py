"""The shared page patterns, page by page (specs/010-design-system-ui-guidelines FR-003,
FR-025–FR-032, SC-006, SC-007; contracts/pages.md §1–§3).

- **Forms**: an invalid submission shows the summary "There is a problem", one link per field
  error to `#field`, the same message beside the field, a message about the whole submission as
  text without a link, and every value kept.
- **Confirmations**: a question naming the item, a consequence, a destructive button repeating the
  verb, then Cancel.
- **Back links**: every page below an area's main page starts with one, to a fixed address.

`assert_form_errors` and `assert_confirmation` are shared by the later cases in this module. Every
test runs once per database engine.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.routers.auth as auth_router
from app.main import app
from app.models import AccessLevel
from tests import html
from tests.conftest import TEACHER_STUDENT_EMAIL, ClientAs, make_institution, make_teacher
from tests.integration.test_login_flow import INVALID_CODE, INVALID_EMAIL, code_from

SUMMARY_HEADING = "There is a problem"
OLENA = "olena@example.org"


def assert_form_errors(
    body: str,
    errors: dict[str, str],
    form_error: str | None = None,
    values: dict[str, str] | None = None,
) -> None:
    """The summary lists each field error as a link to its field, then the form error as text;
    each field shows its own message; every value entered is kept."""
    summary = html.error_summary(body)
    assert summary is not None, "the page has no error summary"
    assert summary.heading == SUMMARY_HEADING
    expected = [(f"#{field}", message) for field, message in errors.items()]
    if form_error is not None:
        expected.append((None, form_error))
    assert summary.items == expected
    for field, message in errors.items():
        assert html.field_error(body, field) == message, field
    for name, value in (values or {}).items():
        assert html.control(body, name)["value"] == value, name


def assert_confirmation(
    body: str, question: str, verb: str, cancel_href: str, action: str | None = None
) -> None:
    """The question as the page's heading, one destructive button repeating the verb, and Cancel
    as a plain link back."""
    assert html.h1(body) == question
    buttons = [
        (form, button)
        for form in html.forms(body, "main")
        for button in form.buttons
        if button.text == verb
    ]
    assert len(buttons) == 1, f"expected one {verb!r} button, found {len(buttons)}"
    form, button = buttons[0]
    assert form.method == "post"
    if action is not None:
        assert form.action == action
    assert "destructive" in button.attrs.get("class", "").split()
    assert (cancel_href, "Cancel") in html.link_pairs(body, "main")


def assert_back_link(body: str, href: str, text: str) -> None:
    """The page's content starts with the back link."""
    first = html.content_links(body)[0]
    assert (first.href, first.text) == (href, f"← {text}")


# ---------------------------------------------------------------------------------------------
# User story 2: sign-in, role choice, profile and withdrawal
# ---------------------------------------------------------------------------------------------


def test_an_invalid_email_is_summarised_and_shown_beside_the_field(client: TestClient) -> None:
    response = client.post("/login", data={"email": "not-an-email", "next": "/"})
    assert response.status_code == 400
    assert_form_errors(response.text, {"email": INVALID_EMAIL}, values={"email": "not-an-email"})


def test_a_wrong_code_links_to_the_code_field(client: TestClient, outbox: list[Any]) -> None:
    client.post("/login", data={"email": "admin@example.com", "next": "/"})
    wrong = f"{(int(code_from(outbox[-1])) + 1) % 1_000_000:06d}"
    response = client.post(
        "/login/code", data={"email": "admin@example.com", "code": wrong, "next": "/"}
    )
    assert response.status_code == 400
    assert_form_errors(response.text, {"code": INVALID_CODE})


def test_a_rate_limit_is_a_form_error_beside_no_field(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_router, "allow_code_request", lambda *args, **kwargs: False)
    response = client.post("/login", data={"email": "admin@example.com", "next": "/"})
    assert response.status_code == 429
    assert_form_errors(response.text, {}, form_error=auth_router.TOO_MANY)
    assert html.field_error(response.text, "email") is None


def test_an_invalid_role_is_a_form_error(client_as: ClientAs) -> None:
    browser = client_as(TEACHER_STUDENT_EMAIL)
    response = browser.post("/role", data={"role": "admin", "next": "/"})
    assert response.status_code == 400
    assert_form_errors(response.text, {}, form_error="Choose one of your roles.")


def test_the_profile_starts_with_a_back_link_home(admin_client: TestClient) -> None:
    assert_back_link(admin_client.get("/profile").text, "/", "Back to the home page")


def test_the_withdrawal_is_a_confirmation(client: TestClient, client_as: ClientAs) -> None:
    engine, settings = app.state.engine, app.state.settings
    school = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    make_teacher(engine, settings, email=OLENA, institutions={school: AccessLevel.READ})
    body = client_as(OLENA).get("/profile/withdraw").text
    assert_back_link(body, "/profile", "Back to your profile")
    assert_confirmation(
        body, "Withdraw consent", "Withdraw consent", "/profile", action="/profile/withdraw"
    )
    assert "Withdrawing your consent erases this data:" in html.text(body, "main")


def test_nothing_to_withdraw_is_a_form_error(admin_client: TestClient) -> None:
    response = admin_client.get("/profile/withdraw")
    assert response.status_code == 409
    assert_back_link(response.text, "/profile", "Back to your profile")
    assert_form_errors(
        response.text, {}, form_error="There is no data stored on your consent to withdraw."
    )
