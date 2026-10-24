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
from sqlmodel import Session

import app.routers.auth as auth_router
import app.services.institutions as app_institutions
import app.services.subjects as app_subjects
import tests.integration.test_form_contract as contract
from app.main import app
from app.models import AccessLevel
from app.services.regions import create_region
from tests import html
from tests.conftest import (
    TEACHER_STUDENT_EMAIL,
    ClientAs,
    make_class,
    make_institution,
    make_teacher,
)
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
    assert (first.href, first.text) == (href, text)
    assert "back-link" in first.attrs.get("class", "").split()


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


# ---------------------------------------------------------------------------------------------
# User story 3: the administrator and teacher areas
# ---------------------------------------------------------------------------------------------


def world(
    client: TestClient, client_as: ClientAs, outbox: list[Any], monkeypatch: pytest.MonkeyPatch
) -> contract.World:
    return contract.World(client, client_as, outbox, monkeypatch)


def assert_summary_matches_fields(
    body: str, fields: list[str], form_error: str | None = None
) -> None:
    """The summary links exactly `fields`, in page order, each with the message shown beside
    that field, then `form_error` as text."""
    summary = html.error_summary(body)
    assert summary is not None, "the page has no error summary"
    assert summary.heading == SUMMARY_HEADING
    links = [(href, text) for href, text in summary.items if href is not None]
    assert [href for href, _ in links] == [f"#{field}" for field in fields]
    for (_, text), field in zip(links, fields, strict=True):
        assert html.field_error(body, field) == text, field
    unlinked = [text for href, text in summary.items if href is None]
    assert unlinked == ([form_error] if form_error else [])


def primary_actions(body: str) -> list[str]:
    """The texts of the primary buttons and link buttons in the page's content."""
    (main,) = html.parse(body).find_all("main")
    found = []
    for element in main.iter():
        is_button = element.tag == "button" or element.attrs.get("role") == "button"
        kinds = {"secondary", "destructive"} & set(element.classes())
        if is_button and not kinds:
            found.append(element.text())
    return found


def test_a_duplicate_subject_is_summarised(admin_client: TestClient) -> None:
    admin_client.post("/admin/subjects", data={"name": "Physics"})
    response = admin_client.post("/admin/subjects", data={"name": "physics"})
    assert response.status_code == 400
    assert_form_errors(
        response.text,
        {"name": "A subject named “Physics” already exists."},
        values={"name": "physics"},
    )


@pytest.mark.parametrize(
    "path",
    ["/admin/institutions/regions", "/admin/institutions/regions/{region}/institutions"],
    ids=["region", "institution"],
)
def test_an_empty_region_or_institution_name_is_summarised(
    admin_client: TestClient, path: str
) -> None:
    region = make_institution(app.state.engine, "Academy", "Kyiv")
    region_id = contract.region_of(region)
    response = admin_client.post(path.format(region=region_id), data={"name": " "})
    assert response.status_code == 400
    assert_summary_matches_fields(response.text, ["name"])
    assert html.control(response.text, "name")["value"] == " "


def test_an_invalid_teacher_invitation_is_summarised_in_field_order(
    client: TestClient, admin_client: TestClient
) -> None:
    make_institution(app.state.engine, "Kyiv Lyceum", "Kyiv")
    response = admin_client.post(
        "/admin/teachers/invite", data={"email": "bad", "first_name": "", "last_name": ""}
    )
    assert response.status_code == 400
    assert_summary_matches_fields(response.text, ["email", "first_name", "last_name", "picker"])
    assert html.control(response.text, "email")["value"] == "bad"


def test_an_invalid_teacher_edit_is_summarised(
    client: TestClient,
    client_as: ClientAs,
    outbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    admin_client: TestClient,
) -> None:
    user_id = contract.a_teacher(world(client, client_as, outbox, monkeypatch))
    response = admin_client.post(
        f"/admin/teachers/{user_id}", data={"first_name": "", "last_name": "Kovalenko"}
    )
    assert response.status_code == 400
    fields = [href[1:] for href, _ in html.error_summary(response.text).items if href]  # type: ignore[union-attr]
    assert fields[0] == "first_name"
    assert_summary_matches_fields(response.text, fields)
    assert html.control(response.text, "last_name")["value"] == "Kovalenko"


def test_an_invalid_class_is_summarised(
    client: TestClient, client_as: ClientAs, outbox: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = contract.a_teacher_with_a_class(world(client, client_as, outbox, monkeypatch))
    response = scene.teacher.post(
        f"/teacher/students/institutions/{scene.institution}/classes",
        data={"name": "", "year_of_study": "two"},
    )
    assert response.status_code == 400
    assert_summary_matches_fields(response.text, ["name", "year_of_study"])
    assert html.control(response.text, "year_of_study")["value"] == "two"


def test_an_invalid_student_invitation_is_summarised(
    client: TestClient, client_as: ClientAs, outbox: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = contract.a_teacher_with_a_class(world(client, client_as, outbox, monkeypatch))
    response = scene.teacher.post(
        f"/teacher/students/classes/{scene.school_class}/invite",
        data={"email": "bad", "first_name": "", "last_name": ""},
    )
    assert response.status_code == 400
    assert_summary_matches_fields(response.text, ["email", "first_name", "last_name"])


def test_an_invalid_student_edit_is_summarised(
    client: TestClient, client_as: ClientAs, outbox: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = contract.a_teacher_with_a_class(world(client, client_as, outbox, monkeypatch))
    response = scene.teacher.post(
        f"/teacher/students/{scene.student}",
        data={"first_name": "", "last_name": "", "class_id": str(scene.school_class)},
    )
    assert response.status_code == 400
    assert_summary_matches_fields(response.text, ["first_name", "last_name"])


def test_the_administrator_confirmations(
    client: TestClient,
    client_as: ClientAs,
    outbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    admin_client: TestClient,
) -> None:
    w = world(client, client_as, outbox, monkeypatch)
    physics, _ = contract.subjects(w)
    region, academy, _ = contract.institutions(w)
    teacher_id = contract.a_teacher(w)
    region_page = f"/admin/institutions/regions/{region}"
    institution = contract.institution_path(region, academy)
    with Session(app.state.engine) as session:
        empty = create_region(session, "Empty").id
    cases = [
        (f"/admin/subjects/{physics}/delete", "Delete “Physics”?", "Delete", "/admin/subjects"),
        (f"{region_page}/deactivate", "Deactivate region “Kyiv”?", "Deactivate", region_page),
        (
            f"/admin/institutions/regions/{empty}/delete",
            "Delete region “Empty”?",
            "Delete",
            f"/admin/institutions/regions/{empty}",
        ),
        (
            f"{institution}/deactivate",
            "Deactivate educational institution “Academy”?",
            "Deactivate",
            region_page,
        ),
        (
            f"{institution}/delete",
            "Delete educational institution “Academy”?",
            "Delete",
            region_page,
        ),
        (
            f"/admin/teachers/{teacher_id}/remove",
            "Remove Olena Kovalenko as a teacher?",
            "Remove",
            f"/admin/teachers/{teacher_id}",
        ),
    ]
    for path, question, verb, cancel in cases:
        body = admin_client.get(path).text
        assert_confirmation(body, question, verb, cancel, action=path)
        assert html.text(body, "main").replace(question, "").strip(), path


def test_the_teacher_confirmations(
    client: TestClient, client_as: ClientAs, outbox: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = contract.a_teacher_with_a_class(world(client, client_as, outbox, monkeypatch))
    empty = make_class(app.state.engine, scene.institution, "KN-22", 2)
    classes = "/teacher/students/classes"
    cases = [
        (f"{classes}/{scene.school_class}/deactivate", "Deactivate class “KN-21”?", "Deactivate"),
        (f"{classes}/{empty}/delete", "Delete class “KN-22”?", "Delete"),
        (
            f"/teacher/students/{scene.student}/remove",
            "Remove Taras Shevchenko as a student?",
            "Remove",
        ),
    ]
    for path, question, verb in cases:
        body = scene.teacher.get(path).text
        (cancel,) = [link.href for link in html.links(body, "main") if link.text == "Cancel"]
        assert_confirmation(body, question, verb, cancel, action=path)


def test_refusals_offer_deactivate(
    client: TestClient,
    client_as: ClientAs,
    outbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    admin_client: TestClient,
) -> None:
    w = world(client, client_as, outbox, monkeypatch)
    physics, _ = contract.subjects(w)
    region, academy, _ = contract.institutions(w)
    monkeypatch.setattr(app_subjects, "count_subject_uses", lambda *_: 1)
    monkeypatch.setattr(app_institutions, "count_institution_uses", lambda *_: 1)
    subject = admin_client.post(f"/admin/subjects/{physics}/delete").text
    assert html.h1(subject) == "Delete “Physics”?"
    reason = "“Physics” is in use and cannot be deleted. You can deactivate it instead."
    assert ("status", reason) in html.notices(subject)
    assert ("post", f"/admin/subjects/{physics}/deactivate") in html.form_targets(subject, "main")
    institution = contract.institution_path(region, academy)
    refused = admin_client.post(f"{institution}/delete").text
    deactivate = [a for a in html.links(refused, "main") if a.text == "Deactivate"]
    assert [(a.href, a.attrs.get("role")) for a in deactivate] == [
        (f"{institution}/deactivate", "button")
    ]
    scene = contract.a_teacher_with_a_class(w)
    in_use = scene.teacher.post(f"/teacher/students/classes/{scene.school_class}/delete").text
    assert "has students and cannot be deleted" in html.text(in_use, "main")
    assert "Deactivate" in [a.text for a in html.links(in_use, "main")]


BACK_LINKS = [
    ("/admin/subjects/new", "/admin/subjects", "Back to the subjects"),
    (
        "/admin/institutions/regions/new",
        "/admin/institutions",
        "Back to the educational institutions",
    ),
    ("/admin/teachers/invite", "/admin/teachers", "Back to the teachers"),
    ("/admin/subjects/999999/rename", "/admin/subjects", "Back to the subjects"),
    ("/admin/teachers/999999", "/admin/teachers", "Back to the teachers"),
    (
        "/admin/institutions/regions/999999",
        "/admin/institutions",
        "Back to the educational institutions",
    ),
]


@pytest.mark.parametrize(("path", "href", "text"), BACK_LINKS, ids=[p for p, _, _ in BACK_LINKS])
def test_every_lower_administrator_page_starts_with_its_back_link(
    admin_client: TestClient, path: str, href: str, text: str
) -> None:
    assert_back_link(admin_client.get(path).text, href, text)


def test_region_and_teacher_pages_link_back_to_their_item(
    client: TestClient,
    client_as: ClientAs,
    outbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    admin_client: TestClient,
) -> None:
    w = world(client, client_as, outbox, monkeypatch)
    region, academy, _ = contract.institutions(w)
    teacher_id = contract.a_teacher(w)
    region_page = f"/admin/institutions/regions/{region}"
    institution = contract.institution_path(region, academy)
    for path in (
        f"{region_page}/rename",
        f"{region_page}/deactivate",
        f"{region_page}/delete",
        f"{region_page}/institutions/new",
        f"{institution}/rename",
        f"{institution}/deactivate",
        f"{institution}/delete",
    ):
        assert_back_link(admin_client.get(path).text, region_page, "Back to “Kyiv”")
    assert_back_link(
        admin_client.get(f"/admin/teachers/{teacher_id}").text,
        "/admin/teachers",
        "Back to the teachers",
    )
    assert_back_link(
        admin_client.get(f"/admin/teachers/{teacher_id}/remove").text,
        f"/admin/teachers/{teacher_id}",
        "Back to Olena Kovalenko",
    )


def test_teacher_pages_link_back_to_the_class(
    client: TestClient, client_as: ClientAs, outbox: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = contract.a_teacher_with_a_class(world(client, client_as, outbox, monkeypatch))
    classes = f"/teacher/students/classes/{scene.school_class}"
    for path in (
        f"{classes}/edit",
        f"{classes}/deactivate",
        f"{classes}/delete",
        f"{classes}/invite",
        f"/teacher/students/{scene.student}",
        f"/teacher/students/{scene.student}/remove",
    ):
        assert_back_link(scene.teacher.get(path).text, scene.selection, "Back to “KN-21”")
    new = scene.teacher.get(f"/teacher/students/institutions/{scene.institution}/classes/new")
    assert_back_link(new.text, scene.selection.split("&class=")[0], "Back to Students")


def test_statuses_and_access_levels_are_badges(
    client: TestClient,
    client_as: ClientAs,
    outbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    admin_client: TestClient,
) -> None:
    w = world(client, client_as, outbox, monkeypatch)
    contract.subjects(w)
    contract.a_teacher(w)
    assert html.badges(admin_client.get("/admin/subjects").text) == ["Deactivated", "Active"]
    assert {"Read", "Write"} <= set(html.badges(admin_client.get("/admin/teachers").text))


@pytest.mark.parametrize(
    ("path", "primary"),
    [
        ("/admin/subjects", ["Create subject"]),
        ("/admin/teachers", ["Invite teacher"]),
        ("/admin/subjects/new", ["Save"]),
    ],
)
def test_a_page_has_one_heading_and_at_most_one_primary_action(
    admin_client: TestClient, path: str, primary: list[str]
) -> None:
    body = admin_client.get(path).text
    assert html.h1(body)
    assert primary_actions(body) == primary


def test_empty_lists_show_the_message_and_a_hint_not_a_table(admin_client: TestClient) -> None:
    for path, message, hint in (
        ("/admin/subjects", "No subjects yet", "Create the first subject with Create subject."),
        ("/admin/teachers", "No teachers yet", "Invite the first teacher with Invite teacher."),
        ("/admin/institutions", "No regions yet", "Create the first region with Create region."),
    ):
        body = admin_client.get(path).text
        text = html.text(body, "main")
        assert message in text and hint in text, path
        assert html.parse(body).find_all("table") == [], path


def test_links_to_forms_and_confirmations_look_like_buttons(
    client: TestClient,
    client_as: ClientAs,
    outbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    admin_client: TestClient,
) -> None:
    physics, _ = contract.subjects(world(client, client_as, outbox, monkeypatch))
    links = {a.href: a for a in html.content_links(admin_client.get("/admin/subjects").text)}
    for href in (
        "/admin/subjects/new",
        f"/admin/subjects/{physics}/rename",
        f"/admin/subjects/{physics}/delete",
    ):
        assert links[href].attrs.get("role") == "button", href
