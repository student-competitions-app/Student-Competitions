"""The Educational institutions tab over HTTP: list, create, rename, deactivate/activate, delete.

See specs/007-institutions/spec.md user stories 1 and 2, and contracts/http-routes.md. The
messages are asserted verbatim. Every test runs once per engine; the `session` fixture opens the
same database the application serves, so tests can arrange and inspect rows directly.
"""

import html
import re

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

import app.services.institutions
from app.services.institutions import list_institutions, set_institution_active

LIST = "/admin/institutions"
DUPLICATE = "An educational institution named “{}” already exists."
CONTROL = "The name cannot contain tabs, line breaks or other control characters."
EMPTY = "Enter a name."
TOO_LONG = "The name can be at most 200 characters."


def stored(session: Session) -> list[tuple[str, bool]]:
    session.expire_all()
    return [(institution.name, institution.is_active) for institution in list_institutions(session)]


def create(client: TestClient, name: str) -> None:
    response = client.post(LIST, data={"name": name}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == LIST


def current_tabs(body: str) -> list[str]:
    """The `href` of every tab marked current."""
    nav = re.search(r'<nav class="admin-tabs".*?</nav>', body, re.DOTALL)
    assert nav is not None, "the page has no admin tab row"
    return re.findall(r'<a href="([^"]+)" aria-current="page">', nav.group(0))


def table_names(body: str) -> list[str]:
    """The institution names in the order the list shows them."""
    return re.findall(r'<td class="institution-name">([^<]*)</td>', body)


def assert_form_refused(response: Response, message: str, value: str) -> None:
    assert response.status_code == 400
    assert html.escape(message, quote=False) in response.text
    assert f'value="{html.escape(value)}"' in response.text
    assert 'aria-invalid="true"' in response.text
    assert current_tabs(response.text) == [LIST]


# ---------------------------------------------------------------------------------------------
# User story 1: list and create
# ---------------------------------------------------------------------------------------------


def test_the_empty_list(admin_client: TestClient) -> None:
    """US1-1, FR-001, FR-003."""
    response = admin_client.get(LIST)
    assert response.status_code == 200
    assert "<h1>Educational institutions</h1>" in response.text
    assert "No educational institutions yet" in response.text
    assert '<a href="/admin/institutions/new" role="button">Create</a>' in response.text
    assert "will arrive in a later milestone" not in response.text
    assert current_tabs(response.text) == [LIST]


def test_the_create_form(admin_client: TestClient) -> None:
    """FR-011."""
    response = admin_client.get("/admin/institutions/new")
    assert response.status_code == 200
    body = response.text
    assert "<h1>New educational institution</h1>" in body
    assert '<form method="post" action="/admin/institutions">' in body
    fields = re.findall(r"<input[^>]*>", body)
    assert len(fields) == 1
    field = fields[0]
    assert 'name="name"' in field
    assert 'maxlength="200"' in field
    assert "required" in field
    assert 'value=""' in field
    assert ">Save</button>" in body
    assert '<a href="/admin/institutions">Cancel</a>' in body
    assert "aria-invalid" not in body
    assert current_tabs(body) == [LIST]


def test_create_returns_to_the_list(admin_client: TestClient, session: Session) -> None:
    """US1-2, FR-012: Post/Redirect/Get, and a new institution is active."""
    create(admin_client, "Kyiv Polytechnic Institute")
    assert stored(session) == [("Kyiv Polytechnic Institute", True)]
    body = admin_client.get(LIST).text
    assert table_names(body) == ["Kyiv Polytechnic Institute"]
    assert "Active" in body
    assert "No educational institutions yet" not in body


def test_the_list_is_sorted_ignoring_case(admin_client: TestClient) -> None:
    """US1-3, FR-001."""
    for name in ("Lviv Polytechnic", "alpha College", "Kyiv Polytechnic Institute"):
        create(admin_client, name)
    body = admin_client.get(LIST).text
    assert table_names(body) == ["alpha College", "Kyiv Polytechnic Institute", "Lviv Polytechnic"]


def test_a_duplicate_is_refused_with_the_value_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-4, FR-009."""
    create(admin_client, "Lviv Polytechnic")
    response = admin_client.post(LIST, data={"name": "  LVIV POLYTECHNIC  "})
    assert_form_refused(response, DUPLICATE.format("Lviv Polytechnic"), "  LVIV POLYTECHNIC  ")
    assert '<form method="post" action="/admin/institutions">' in response.text
    assert stored(session) == [("Lviv Polytechnic", True)]


def test_a_cyrillic_duplicate_is_refused(admin_client: TestClient, session: Session) -> None:
    """Edge case "Name with letters outside English"."""
    create(admin_client, "Київський університет")
    response = admin_client.post(LIST, data={"name": "КИЇВСЬКИЙ УНІВЕРСИТЕТ"})
    assert_form_refused(
        response, DUPLICATE.format("Київський університет"), "КИЇВСЬКИЙ УНІВЕРСИТЕТ"
    )
    assert stored(session) == [("Київський університет", True)]


def test_the_name_of_an_inactive_institution_is_taken(
    admin_client: TestClient, session: Session
) -> None:
    create(admin_client, "Lviv Polytechnic")
    set_institution_active(session, list_institutions(session)[0].id, False)
    response = admin_client.post(LIST, data={"name": "lviv polytechnic"})
    assert_form_refused(response, DUPLICATE.format("Lviv Polytechnic"), "lviv polytechnic")


def test_invalid_names_are_refused_with_the_value_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-5, FR-008, FR-013."""
    cases = [
        ("", EMPTY),
        ("   ", EMPTY),
        ("a" * 201, TOO_LONG),
        ("Kyiv\tInstitute", CONTROL),
        ("Kyiv\nInstitute", CONTROL),
        ("<b>Lyceum</b>\n", CONTROL),
    ]
    for value, message in cases:
        response = admin_client.post(LIST, data={"name": value})
        assert_form_refused(response, message, value)
    assert stored(session) == []


def test_a_name_of_200_characters_is_accepted(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "a" * 200)
    assert stored(session) == [("a" * 200, True)]


def test_a_missing_field_is_an_empty_name(admin_client: TestClient, session: Session) -> None:
    response = admin_client.post(LIST, data={})
    assert_form_refused(response, EMPTY, "")
    assert stored(session) == []


def test_outer_spaces_are_removed_and_inner_ones_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-6, FR-007."""
    create(admin_client, "  Odesa College  ")
    create(admin_client, "Odesa  College")
    assert sorted(stored(session)) == [("Odesa  College", True), ("Odesa College", True)]


def test_reloading_the_list_adds_nothing(admin_client: TestClient, session: Session) -> None:
    """SC-006: after the redirect, a reload repeats only the `GET`."""
    response = admin_client.post(LIST, data={"name": "Odesa College"})
    assert response.status_code == 200  # the redirect was followed to the list
    assert response.url.path == LIST
    admin_client.get(LIST)
    admin_client.get(LIST)
    assert stored(session) == [("Odesa College", True)]


# ---------------------------------------------------------------------------------------------
# User story 2: rename, deactivate/activate, delete
# ---------------------------------------------------------------------------------------------

IN_USE = "“{}” is in use and cannot be deleted. You can deactivate it instead."
MISSING = 999


def institution_id(session: Session, name: str) -> int:
    session.expire_all()
    found = [i.id for i in list_institutions(session) if i.name == name]
    assert len(found) == 1, f"no single institution named {name!r}"
    return found[0]


def snapshot(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    return [
        (i.id, i.name, i.name_key, i.is_active, i.updated_at) for i in list_institutions(session)
    ]


def post(client: TestClient, path: str, data: dict[str, str] | None = None) -> Response:
    return client.post(path, data=data or {}, follow_redirects=False)


def assert_back_to_the_list(response: Response) -> None:
    assert response.status_code == 303, response.text
    assert response.headers["location"] == LIST


def test_each_row_offers_its_actions(admin_client: TestClient, session: Session) -> None:
    """FR-004."""
    create(admin_client, "Lviv Polytechnic")
    create(admin_client, "Alpha College")
    lviv, alpha = (
        institution_id(session, "Lviv Polytechnic"),
        institution_id(session, "Alpha College"),
    )
    set_institution_active(session, alpha, False)
    body = admin_client.get(LIST).text
    for iid in (lviv, alpha):
        assert f'<a href="/admin/institutions/{iid}/rename" role="button" class="secondary outline">Rename</a>' in body
        assert f'<a href="/admin/institutions/{iid}/delete" role="button" class="secondary outline">Delete</a>' in body
    assert f'<form method="post" action="/admin/institutions/{lviv}/deactivate">' in body
    assert f'<form method="post" action="/admin/institutions/{alpha}/activate">' in body
    assert f"/admin/institutions/{lviv}/activate" not in body
    assert f"/admin/institutions/{alpha}/deactivate" not in body
    assert "Inactive" in body


def test_the_rename_form_is_filled_in(admin_client: TestClient, session: Session) -> None:
    """US2-1, FR-014."""
    create(admin_client, "Lviv Politechnic")
    iid = institution_id(session, "Lviv Politechnic")
    response = admin_client.get(f"/admin/institutions/{iid}/rename")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Rename educational institution</h1>" in body
    assert f'<form method="post" action="/admin/institutions/{iid}/rename">' in body
    assert 'value="Lviv Politechnic"' in body
    assert '<a href="/admin/institutions">Cancel</a>' in body
    assert current_tabs(body) == [LIST]


def test_rename(admin_client: TestClient, session: Session) -> None:
    """US2-2, FR-016."""
    create(admin_client, "Lviv Politechnic")
    iid = institution_id(session, "Lviv Politechnic")
    assert_back_to_the_list(
        post(admin_client, f"/admin/institutions/{iid}/rename", {"name": "Lviv Polytechnic"})
    )
    assert stored(session) == [("Lviv Polytechnic", True)]
    assert institution_id(session, "Lviv Polytechnic") == iid
    assert table_names(admin_client.get(LIST).text) == ["Lviv Polytechnic"]


def test_rename_onto_another_institution_is_refused(
    admin_client: TestClient, session: Session
) -> None:
    """US2-3."""
    create(admin_client, "Lviv Polytechnic")
    create(admin_client, "Odesa College")
    iid = institution_id(session, "Odesa College")
    before = snapshot(session)
    response = post(admin_client, f"/admin/institutions/{iid}/rename", {"name": "lviv polytechnic"})
    assert_form_refused(response, DUPLICATE.format("Lviv Polytechnic"), "lviv polytechnic")
    assert f'<form method="post" action="/admin/institutions/{iid}/rename">' in response.text
    assert snapshot(session) == before


def test_a_change_of_case_is_a_rename(admin_client: TestClient, session: Session) -> None:
    """US2-4, FR-015."""
    create(admin_client, "odesa college")
    iid = institution_id(session, "odesa college")
    assert_back_to_the_list(
        post(admin_client, f"/admin/institutions/{iid}/rename", {"name": "Odesa College"})
    )
    assert stored(session) == [("Odesa College", True)]


def test_an_unchanged_rename_writes_nothing(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "Odesa College")
    iid = institution_id(session, "Odesa College")
    before = snapshot(session)
    assert_back_to_the_list(
        post(admin_client, f"/admin/institutions/{iid}/rename", {"name": " Odesa College "})
    )
    assert snapshot(session) == before


def test_rename_keeps_an_inactive_institution_inactive(
    admin_client: TestClient, session: Session
) -> None:
    """US2-5, FR-017, SC-007: same id, same status."""
    create(admin_client, "Alpha College")
    iid = institution_id(session, "Alpha College")
    set_institution_active(session, iid, False)
    assert_back_to_the_list(
        post(admin_client, f"/admin/institutions/{iid}/rename", {"name": "Alpha Lyceum"})
    )
    assert stored(session) == [("Alpha Lyceum", False)]
    assert institution_id(session, "Alpha Lyceum") == iid


def test_an_invalid_rename_is_refused(admin_client: TestClient, session: Session) -> None:
    create(admin_client, "Odesa College")
    iid = institution_id(session, "Odesa College")
    before = snapshot(session)
    for value, message in [("  ", EMPTY), ("b" * 201, TOO_LONG), ("Odesa\nCollege", CONTROL)]:
        response = post(admin_client, f"/admin/institutions/{iid}/rename", {"name": value})
        assert_form_refused(response, message, value)
    assert_form_refused(post(admin_client, f"/admin/institutions/{iid}/rename"), EMPTY, "")
    assert snapshot(session) == before


def test_deactivate_and_activate(admin_client: TestClient, session: Session) -> None:
    """US2-6, US2-7, FR-019, FR-020."""
    create(admin_client, "Alpha College")
    iid = institution_id(session, "Alpha College")
    assert_back_to_the_list(post(admin_client, f"/admin/institutions/{iid}/deactivate"))
    assert stored(session) == [("Alpha College", False)]
    body = admin_client.get(LIST).text
    assert table_names(body) == ["Alpha College"]
    assert "Inactive" in body
    assert re.search(
        rf'action="/admin/institutions/{iid}/activate">\s*<button[^>]*>Activate</button>', body
    )
    assert_back_to_the_list(post(admin_client, f"/admin/institutions/{iid}/activate"))
    assert stored(session) == [("Alpha College", True)]
    body = admin_client.get(LIST).text
    assert re.search(
        rf'action="/admin/institutions/{iid}/deactivate">\s*<button[^>]*>Deactivate</button>', body
    )


def test_repeating_a_status_change_changes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """FR-021: e.g. a second tab still showing the old button."""
    create(admin_client, "Alpha College")
    iid = institution_id(session, "Alpha College")
    before = snapshot(session)
    assert_back_to_the_list(post(admin_client, f"/admin/institutions/{iid}/activate"))
    assert snapshot(session) == before
    post(admin_client, f"/admin/institutions/{iid}/deactivate")
    before = snapshot(session)
    assert_back_to_the_list(post(admin_client, f"/admin/institutions/{iid}/deactivate"))
    assert snapshot(session) == before


def test_the_delete_confirmation_deletes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """US2-8, FR-023."""
    create(admin_client, "Test School")
    iid = institution_id(session, "Test School")
    before = snapshot(session)
    response = admin_client.get(f"/admin/institutions/{iid}/delete")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Delete “Test School”?</h1>" in body
    assert "Deleting an educational institution cannot be undone." in body
    assert f'<form method="post" action="/admin/institutions/{iid}/delete">' in body
    assert ">Delete</button>" in body
    assert '<a href="/admin/institutions">Cancel</a>' in body
    assert current_tabs(body) == [LIST]
    assert snapshot(session) == before


def test_delete(admin_client: TestClient, session: Session) -> None:
    """US2-9, FR-026: gone from the list, and the name is free again."""
    create(admin_client, "Test School")
    iid = institution_id(session, "Test School")
    assert_back_to_the_list(post(admin_client, f"/admin/institutions/{iid}/delete"))
    assert stored(session) == []
    assert "No educational institutions yet" in admin_client.get(LIST).text
    create(admin_client, "test school")
    assert stored(session) == [("test school", True)]


def test_an_institution_in_use_cannot_be_deleted(
    admin_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US2-10, FR-024, SC-004: a stand-in for the links of milestones 8 and 9."""
    create(admin_client, "Lviv Polytechnic")
    iid = institution_id(session, "Lviv Polytechnic")
    before = snapshot(session)
    monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda *_: 1)
    response = post(admin_client, f"/admin/institutions/{iid}/delete")
    assert response.status_code == 409
    body = response.text
    assert IN_USE.format("Lviv Polytechnic") in body
    assert ">Delete</button>" not in body
    assert f'action="/admin/institutions/{iid}/delete"' not in body
    assert f'<form method="post" action="/admin/institutions/{iid}/deactivate">' in body
    assert '<a href="/admin/institutions">' in body
    assert current_tabs(body) == [LIST]
    assert snapshot(session) == before


def test_an_inactive_institution_in_use_offers_no_deactivate(
    admin_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create(admin_client, "Lviv Polytechnic")
    iid = institution_id(session, "Lviv Polytechnic")
    set_institution_active(session, iid, False)
    monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda *_: 2)
    response = post(admin_client, f"/admin/institutions/{iid}/delete")
    assert response.status_code == 409
    assert IN_USE.format("Lviv Polytechnic") in response.text
    assert "/deactivate" not in response.text
    assert stored(session) == [("Lviv Polytechnic", False)]


NOT_FOUND_REQUESTS = [
    ("GET", f"/admin/institutions/{MISSING}/rename"),
    ("POST", f"/admin/institutions/{MISSING}/rename"),
    ("POST", f"/admin/institutions/{MISSING}/deactivate"),
    ("POST", f"/admin/institutions/{MISSING}/activate"),
    ("GET", f"/admin/institutions/{MISSING}/delete"),
    ("POST", f"/admin/institutions/{MISSING}/delete"),
]


@pytest.mark.parametrize(("method", "path"), NOT_FOUND_REQUESTS)
def test_a_missing_institution_is_not_found(
    admin_client: TestClient, method: str, path: str
) -> None:
    """FR-030: e.g. deleted in another tab. A friendly page inside the area, never a traceback."""
    response = admin_client.request(
        method, path, data={"name": "Odesa College"}, follow_redirects=False
    )
    assert response.status_code == 404
    body = response.text
    assert "<h1>Educational institution not found</h1>" in body
    assert "This educational institution does not exist. It may have been deleted." in body
    assert '<a href="/admin/institutions">Back to the educational institutions</a>' in body
    assert current_tabs(body) == [LIST]
    assert "Traceback" not in body


def test_a_non_integer_id_is_the_normal_not_found(admin_client: TestClient) -> None:
    response = admin_client.get("/admin/institutions/abc/rename")
    assert response.status_code == 404
    assert "application/json" not in response.headers["content-type"]
    assert "admin-tabs" not in response.text


def test_reloading_the_list_after_each_action_repeats_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """SC-006."""
    create(admin_client, "Lviv Politechnic")
    iid = institution_id(session, "Lviv Politechnic")
    for path, data in [
        (f"/admin/institutions/{iid}/rename", {"name": "Lviv Polytechnic"}),
        (f"/admin/institutions/{iid}/deactivate", {}),
        (f"/admin/institutions/{iid}/activate", {}),
    ]:
        response = admin_client.post(path, data=data)
        assert response.url.path == LIST
        after = snapshot(session)
        admin_client.get(LIST)
        assert snapshot(session) == after
    admin_client.post(f"/admin/institutions/{iid}/delete")
    admin_client.get(LIST)
    assert stored(session) == []
