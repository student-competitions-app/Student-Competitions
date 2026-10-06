"""The Subjects tab over HTTP: list, create, rename, deactivate/activate and delete.

See specs/006-admin-area/spec.md user stories 1 and 2, and contracts/http-routes.md "Subjects".
The messages are asserted verbatim. Every test runs once per engine; the `session` fixture opens
the same database the application serves, so tests can arrange and inspect rows directly.
"""

import html
import re

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

import app.services.subjects
from app.services.subjects import list_subjects, set_subject_active

DUPLICATE = "A subject named “{}” already exists."
CONTROL = "The name cannot contain tabs, line breaks or other control characters."
EMPTY = "Enter a name."
TOO_LONG = "The name can be at most 200 characters."


def stored(session: Session) -> list[tuple[str, bool]]:
    session.expire_all()
    return [(subject.name, subject.is_active) for subject in list_subjects(session)]


def create(client: TestClient, name: str) -> None:
    response = client.post("/admin/subjects", data={"name": name}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/admin/subjects"


def current_tabs(body: str) -> list[str]:
    """The `href` of every tab marked current."""
    nav = re.search(r'<nav class="admin-tabs".*?</nav>', body, re.DOTALL)
    assert nav is not None, "the page has no admin tab row"
    return re.findall(r'<a href="([^"]+)" aria-current="page">', nav.group(0))


def table_names(body: str) -> list[str]:
    """The subject names in the order the list shows them."""
    return re.findall(r'<td class="subject-name">([^<]*)</td>', body)


def assert_form_refused(response: Response, message: str, value: str) -> None:
    assert response.status_code == 400
    assert html.escape(message, quote=False) in response.text
    assert f'value="{html.escape(value)}"' in response.text
    assert 'aria-invalid="true"' in response.text
    assert current_tabs(response.text) == ["/admin/subjects"]


# ---------------------------------------------------------------------------------------------
# User story 1: list and create
# ---------------------------------------------------------------------------------------------


def test_the_empty_list(admin_client: TestClient) -> None:
    """US1-1."""
    response = admin_client.get("/admin/subjects")
    assert response.status_code == 200
    assert "<h1>Subjects</h1>" in response.text
    assert "No subjects yet" in response.text
    assert '<a href="/admin/subjects/new" role="button">Create</a>' in response.text
    assert current_tabs(response.text) == ["/admin/subjects"]


def test_the_create_form(admin_client: TestClient) -> None:
    response = admin_client.get("/admin/subjects/new")
    assert response.status_code == 200
    body = response.text
    assert '<form method="post" action="/admin/subjects">' in body
    field = re.search(r'<input[^>]*name="name"[^>]*>', body)
    assert field is not None
    assert 'maxlength="200"' in field.group(0)
    assert "required" in field.group(0)
    assert 'value=""' in field.group(0)
    assert ">Save</button>" in body
    assert '<a href="/admin/subjects">Cancel</a>' in body
    assert "aria-invalid" not in body
    assert current_tabs(body) == ["/admin/subjects"]


def test_create_returns_to_the_list(admin_client: TestClient, session: Session) -> None:
    """US1-2, FR-018: Post/Redirect/Get."""
    create(admin_client, "Mathematics")
    assert stored(session) == [("Mathematics", True)]
    body = admin_client.get("/admin/subjects").text
    assert table_names(body) == ["Mathematics"]
    assert "Active" in body
    assert "No subjects yet" not in body


def test_the_list_is_sorted_ignoring_case(admin_client: TestClient) -> None:
    """US1-3."""
    for name in ("Physics", "chemistry", "Mathematics"):
        create(admin_client, name)
    body = admin_client.get("/admin/subjects").text
    assert table_names(body) == ["chemistry", "Mathematics", "Physics"]


def test_a_duplicate_is_refused_with_the_value_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-4."""
    create(admin_client, "Physics")
    response = admin_client.post("/admin/subjects", data={"name": "  PHYSICS  "})
    assert_form_refused(response, DUPLICATE.format("Physics"), "  PHYSICS  ")
    assert '<form method="post" action="/admin/subjects">' in response.text
    assert stored(session) == [("Physics", True)]


def test_a_cyrillic_duplicate_is_refused(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "Фізика")
    response = admin_client.post("/admin/subjects", data={"name": "ФІЗИКА"})
    assert_form_refused(response, DUPLICATE.format("Фізика"), "ФІЗИКА")
    assert stored(session) == [("Фізика", True)]


def test_the_name_of_an_inactive_subject_is_taken(
    admin_client: TestClient, session: Session
) -> None:
    create(admin_client, "Physics")
    set_subject_active(session, list_subjects(session)[0].id, False)
    response = admin_client.post("/admin/subjects", data={"name": "physics"})
    assert_form_refused(response, DUPLICATE.format("Physics"), "physics")


def test_invalid_names_are_refused_with_the_value_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-5, FR-019."""
    cases = [
        ("", EMPTY),
        ("   ", EMPTY),
        ("a" * 201, TOO_LONG),
        ("Math\tematics", CONTROL),
        ("<b>Physics</b>\n", CONTROL),
    ]
    for value, message in cases:
        response = admin_client.post("/admin/subjects", data={"name": value})
        assert_form_refused(response, message, value)
    assert stored(session) == []


def test_a_missing_field_is_an_empty_name(admin_client: TestClient, session: Session) -> None:
    response = admin_client.post("/admin/subjects", data={})
    assert_form_refused(response, EMPTY, "")
    assert stored(session) == []


def test_outer_spaces_are_removed_and_inner_ones_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-6."""
    create(admin_client, "  Computer Science  ")
    create(admin_client, "Computer  Science")
    assert sorted(stored(session)) == [("Computer  Science", True), ("Computer Science", True)]


def test_reloading_the_list_adds_nothing(admin_client: TestClient, session: Session) -> None:
    """SC-007: after the redirect, a reload repeats only the `GET`."""
    response = admin_client.post("/admin/subjects", data={"name": "Mathematics"})
    assert response.status_code == 200  # the redirect was followed to the list
    assert response.url.path == "/admin/subjects"
    admin_client.get("/admin/subjects")
    admin_client.get("/admin/subjects")
    assert stored(session) == [("Mathematics", True)]


# ---------------------------------------------------------------------------------------------
# User story 2: rename, deactivate/activate, delete
# ---------------------------------------------------------------------------------------------

IN_USE = "“{}” is in use and cannot be deleted. You can deactivate it instead."
MISSING = 999


def subject_id(session: Session, name: str) -> int:
    session.expire_all()
    found = [s.id for s in list_subjects(session) if s.name == name]
    assert len(found) == 1, f"no single subject named {name!r}"
    return found[0]


def snapshot(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    return [(s.id, s.name, s.name_key, s.is_active, s.updated_at) for s in list_subjects(session)]


def post(client: TestClient, path: str, data: dict[str, str] | None = None) -> Response:
    return client.post(path, data=data or {}, follow_redirects=False)


def assert_back_to_the_list(response: Response) -> None:
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/admin/subjects"


def test_each_row_offers_its_actions(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "Physics")
    create(admin_client, "Biology")
    physics, biology = subject_id(session, "Physics"), subject_id(session, "Biology")
    set_subject_active(session, biology, False)
    body = admin_client.get("/admin/subjects").text
    for sid in (physics, biology):
        assert f'<a href="/admin/subjects/{sid}/rename" role="button" class="secondary outline">Rename</a>' in body
        assert f'<a href="/admin/subjects/{sid}/delete" role="button" class="secondary outline">Delete</a>' in body
    assert f'<form method="post" action="/admin/subjects/{physics}/deactivate">' in body
    assert f'<form method="post" action="/admin/subjects/{biology}/activate">' in body
    assert f"/admin/subjects/{physics}/activate" not in body
    assert f"/admin/subjects/{biology}/deactivate" not in body
    assert "Inactive" in body


def test_the_rename_form_is_filled_in(admin_client: TestClient, session: Session) -> None:
    """US2-1, FR-020."""
    create(admin_client, "Mathmatics")
    sid = subject_id(session, "Mathmatics")
    response = admin_client.get(f"/admin/subjects/{sid}/rename")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Rename subject</h1>" in body
    assert f'<form method="post" action="/admin/subjects/{sid}/rename">' in body
    assert 'value="Mathmatics"' in body
    assert '<a href="/admin/subjects">Cancel</a>' in body
    assert current_tabs(body) == ["/admin/subjects"]


def test_rename(admin_client: TestClient, session: Session) -> None:
    """US2-2."""
    create(admin_client, "Mathmatics")
    sid = subject_id(session, "Mathmatics")
    assert_back_to_the_list(
        post(admin_client, f"/admin/subjects/{sid}/rename", {"name": "Mathematics"})
    )
    assert stored(session) == [("Mathematics", True)]
    assert table_names(admin_client.get("/admin/subjects").text) == ["Mathematics"]


def test_rename_onto_another_subject_is_refused(admin_client: TestClient, session: Session) -> None:
    """US2-3, FR-022."""
    create(admin_client, "Physics")
    create(admin_client, "Chemistry")
    sid = subject_id(session, "Chemistry")
    before = snapshot(session)
    response = post(admin_client, f"/admin/subjects/{sid}/rename", {"name": "physics"})
    assert_form_refused(response, DUPLICATE.format("Physics"), "physics")
    assert f'<form method="post" action="/admin/subjects/{sid}/rename">' in response.text
    assert snapshot(session) == before


def test_a_change_of_case_is_a_rename(admin_client: TestClient, session: Session) -> None:
    """US2-4, FR-021."""
    create(admin_client, "physics")
    sid = subject_id(session, "physics")
    assert_back_to_the_list(
        post(admin_client, f"/admin/subjects/{sid}/rename", {"name": "Physics"})
    )
    assert stored(session) == [("Physics", True)]


def test_an_unchanged_rename_writes_nothing(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    before = snapshot(session)
    assert_back_to_the_list(
        post(admin_client, f"/admin/subjects/{sid}/rename", {"name": " Physics "})
    )
    assert snapshot(session) == before


def test_rename_keeps_an_inactive_subject_inactive(
    admin_client: TestClient, session: Session
) -> None:
    """FR-023."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    set_subject_active(session, sid, False)
    assert_back_to_the_list(
        post(admin_client, f"/admin/subjects/{sid}/rename", {"name": "Astronomy"})
    )
    assert stored(session) == [("Astronomy", False)]


def test_an_invalid_rename_is_refused(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    before = snapshot(session)
    for value, message in [("  ", EMPTY), ("b" * 201, TOO_LONG), ("Phy\nsics", CONTROL)]:
        response = post(admin_client, f"/admin/subjects/{sid}/rename", {"name": value})
        assert_form_refused(response, message, value)
    assert_form_refused(post(admin_client, f"/admin/subjects/{sid}/rename"), EMPTY, "")
    assert snapshot(session) == before


def test_deactivate_and_activate(admin_client: TestClient, session: Session) -> None:
    """US2-5, US2-6."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    assert_back_to_the_list(post(admin_client, f"/admin/subjects/{sid}/deactivate"))
    assert stored(session) == [("Physics", False)]
    body = admin_client.get("/admin/subjects").text
    assert table_names(body) == ["Physics"]
    assert "Inactive" in body
    assert re.search(
        rf'action="/admin/subjects/{sid}/activate">\s*<button[^>]*>Activate</button>', body
    )
    assert_back_to_the_list(post(admin_client, f"/admin/subjects/{sid}/activate"))
    assert stored(session) == [("Physics", True)]
    body = admin_client.get("/admin/subjects").text
    assert re.search(
        rf'action="/admin/subjects/{sid}/deactivate">\s*<button[^>]*>Deactivate</button>', body
    )


def test_repeating_a_status_change_changes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """FR-026: e.g. a second tab still showing the old button."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    before = snapshot(session)
    assert_back_to_the_list(post(admin_client, f"/admin/subjects/{sid}/activate"))
    assert snapshot(session) == before
    post(admin_client, f"/admin/subjects/{sid}/deactivate")
    before = snapshot(session)
    assert_back_to_the_list(post(admin_client, f"/admin/subjects/{sid}/deactivate"))
    assert snapshot(session) == before


def test_the_delete_confirmation_deletes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """US2-7, FR-028."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    before = snapshot(session)
    response = admin_client.get(f"/admin/subjects/{sid}/delete")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Delete “Physics”?</h1>" in body
    assert "Deleting a subject cannot be undone." in body
    assert f'<form method="post" action="/admin/subjects/{sid}/delete">' in body
    assert ">Delete</button>" in body
    assert '<a href="/admin/subjects">Cancel</a>' in body
    assert current_tabs(body) == ["/admin/subjects"]
    assert snapshot(session) == before


def test_delete(admin_client: TestClient, session: Session) -> None:
    """US2-8, FR-031: gone from the list, and the name is free again."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    assert_back_to_the_list(post(admin_client, f"/admin/subjects/{sid}/delete"))
    assert stored(session) == []
    assert "No subjects yet" in admin_client.get("/admin/subjects").text
    create(admin_client, "physics")
    assert stored(session) == [("physics", True)]


def test_a_subject_in_use_cannot_be_deleted(
    admin_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US2-9, FR-029."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    before = snapshot(session)
    monkeypatch.setattr(app.services.subjects, "count_subject_uses", lambda *_: 1)
    response = post(admin_client, f"/admin/subjects/{sid}/delete")
    assert response.status_code == 409
    body = response.text
    assert IN_USE.format("Physics") in body
    assert ">Delete</button>" not in body
    assert f'action="/admin/subjects/{sid}/delete"' not in body
    assert f'<form method="post" action="/admin/subjects/{sid}/deactivate">' in body
    assert '<a href="/admin/subjects">' in body
    assert current_tabs(body) == ["/admin/subjects"]
    assert snapshot(session) == before


def test_an_inactive_subject_in_use_offers_no_deactivate(
    admin_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    set_subject_active(session, sid, False)
    monkeypatch.setattr(app.services.subjects, "count_subject_uses", lambda *_: 2)
    response = post(admin_client, f"/admin/subjects/{sid}/delete")
    assert response.status_code == 409
    assert IN_USE.format("Physics") in response.text
    assert "/deactivate" not in response.text
    assert stored(session) == [("Physics", False)]


NOT_FOUND_REQUESTS = [
    ("GET", f"/admin/subjects/{MISSING}/rename"),
    ("POST", f"/admin/subjects/{MISSING}/rename"),
    ("POST", f"/admin/subjects/{MISSING}/deactivate"),
    ("POST", f"/admin/subjects/{MISSING}/activate"),
    ("GET", f"/admin/subjects/{MISSING}/delete"),
    ("POST", f"/admin/subjects/{MISSING}/delete"),
]


@pytest.mark.parametrize(("method", "path"), NOT_FOUND_REQUESTS)
def test_a_missing_subject_is_not_found(admin_client: TestClient, method: str, path: str) -> None:
    """FR-035: e.g. deleted in another tab. A friendly page inside the area, never a traceback."""
    response = admin_client.request(method, path, data={"name": "Physics"}, follow_redirects=False)
    assert response.status_code == 404
    body = response.text
    assert "<h1>Subject not found</h1>" in body
    assert "This subject does not exist. It may have been deleted." in body
    assert '<a href="/admin/subjects">' in body
    assert current_tabs(body) == ["/admin/subjects"]
    assert "Traceback" not in body


def test_a_rename_of_a_missing_subject_with_an_invalid_name_is_not_found(
    admin_client: TestClient,
) -> None:
    response = post(admin_client, f"/admin/subjects/{MISSING}/rename", {"name": ""})
    assert response.status_code == 404
    assert "<h1>Subject not found</h1>" in response.text


def test_a_non_integer_id_gets_the_normal_not_found_page(admin_client: TestClient) -> None:
    response = admin_client.get("/admin/subjects/abc/rename")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "admin-tabs" not in response.text


def test_reloading_after_each_action_repeats_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """SC-007: every action ends on the list through a 303, so a reload is a plain `GET`."""
    create(admin_client, "Physics")
    sid = subject_id(session, "Physics")
    for path, data in [
        (f"/admin/subjects/{sid}/rename", {"name": "Astronomy"}),
        (f"/admin/subjects/{sid}/deactivate", {}),
        (f"/admin/subjects/{sid}/activate", {}),
    ]:
        response = admin_client.post(path, data=data)
        assert response.url.path == "/admin/subjects"
        before = snapshot(session)
        admin_client.get("/admin/subjects")
        assert snapshot(session) == before
    admin_client.post(f"/admin/subjects/{sid}/delete")
    admin_client.get("/admin/subjects")
    assert stored(session) == []
