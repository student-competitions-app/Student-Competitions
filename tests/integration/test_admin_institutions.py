"""The Educational institutions tab over HTTP: the two lists, and creating, renaming,
deactivating, activating and deleting regions and institutions.

See specs/007-region-and-institutions-management/spec.md user stories 1–4, and
contracts/http-routes.md. The messages are asserted verbatim. Every test runs once per engine; the
`session` fixture opens the same database the application serves, so tests can arrange and inspect
rows directly.
"""

import html
import re

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session, select

import app.services.institutions
from app.core.db import utc_now
from app.models import Institution, Region
from app.schemas.names import name_key

TAB = "/admin/institutions"
MISSING = 999

REGION_DUPLICATE = "A region named “{}” already exists."
INSTITUTION_DUPLICATE = "An educational institution named “{}” already exists in this region."
CONTROL = "The name cannot contain tabs, line breaks or other control characters."
EMPTY = "Enter a name."
TOO_LONG = "The name can be at most 200 characters."
REGION_INACTIVE = "This region is deactivated. New educational institutions cannot be added to it."
NOT_EMPTY = (
    "“{}” still holds educational institutions and cannot be deleted. "
    "Delete its institutions first."
)
IN_USE = "“{}” is in use and cannot be deleted. You can deactivate it instead."
KPI = "Kyiv Polytechnic Institute"


# ---------------------------------------------------------------------------------------------
# Arranging and inspecting rows
# ---------------------------------------------------------------------------------------------


def add_region(session: Session, name: str, active: bool = True) -> int:
    """A region inserted directly; its id."""
    now = utc_now()
    region = Region(
        name=name, name_key=name_key(name), is_active=active, created_at=now, updated_at=now
    )
    session.add(region)
    session.commit()
    assert region.id is not None
    return region.id


def add_institution(session: Session, region_id: int, name: str, active: bool = True) -> int:
    """An institution inserted directly; its id."""
    now = utc_now()
    institution = Institution(
        region_id=region_id,
        name=name,
        name_key=name_key(name),
        is_active=active,
        created_at=now,
        updated_at=now,
    )
    session.add(institution)
    session.commit()
    assert institution.id is not None
    return institution.id


def set_active(
    session: Session, model: type[Region] | type[Institution], id: int, active: bool
) -> None:
    session.expire_all()
    row = session.get(model, id)
    assert row is not None
    row.is_active = active
    session.add(row)
    session.commit()


def regions(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    rows = session.exec(select(Region).order_by(Region.id)).all()
    return [(r.id, r.name, r.name_key, r.is_active, r.updated_at) for r in rows]


def institutions(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    rows = session.exec(select(Institution).order_by(Institution.id)).all()
    return [(i.id, i.region_id, i.name, i.name_key, i.is_active, i.updated_at) for i in rows]


def region_names(session: Session) -> list[tuple[str, bool]]:
    return [(name, active) for _, name, _, active, _ in regions(session)]


def institution_names(session: Session, region_id: int) -> list[tuple[str, bool]]:
    return [(n, a) for _, r, n, _, a, _ in institutions(session) if r == region_id]


def region_id(session: Session, name: str) -> int:
    found = [rid for rid, stored, _, _, _ in regions(session) if stored == name]
    assert len(found) == 1, f"no single region named {name!r}"
    return found[0]


def institution_id(session: Session, region: int, name: str) -> int:
    found = [
        iid for iid, r, stored, _, _, _ in institutions(session) if (r, stored) == (region, name)
    ]
    assert len(found) == 1, f"no single institution named {name!r}"
    return found[0]


# ---------------------------------------------------------------------------------------------
# Reading pages
# ---------------------------------------------------------------------------------------------


def region_path(rid: int) -> str:
    return f"{TAB}/regions/{rid}"


def institution_path(rid: int, iid: int) -> str:
    return f"{region_path(rid)}/institutions/{iid}"


def current_tabs(body: str) -> list[str]:
    nav = re.search(r'<nav class="admin-tabs".*?</nav>', body, re.DOTALL)
    assert nav is not None, "the page has no admin tab row"
    return re.findall(r'<a href="([^"]+)" aria-current="page">', nav.group(0))


def left(body: str) -> str:
    match = re.search(r'<section aria-labelledby="regions-heading">.*?</section>', body, re.DOTALL)
    assert match is not None, "the page has no region list"
    return match.group(0)


def right(body: str) -> str:
    match = re.search(
        r'<section aria-labelledby="institutions-heading">.*?</section>', body, re.DOTALL
    )
    assert match is not None, "the page has no institution list"
    return match.group(0)


def listed_regions(body: str) -> list[str]:
    """The region names in the order the left list shows them."""
    return re.findall(r'<a href="/admin/institutions/regions/\d+"[^>]*>([^<]*)</a>', left(body))


def selected_regions(body: str) -> list[str]:
    return re.findall(r'<a href="([^"]+)" aria-current="true">', body)


def region_item(body: str, rid: int) -> str:
    match = re.search(
        rf'<li[^>]*>\s*<a href="/admin/institutions/regions/{rid}"[^>]*>.*?</li>', body, re.DOTALL
    )
    assert match is not None, f"region {rid} is not listed"
    return match.group(0)


def listed_institutions(body: str) -> list[str]:
    """The institution names in the order the right list shows them."""
    return re.findall(r'<td class="institution-name">([^<]*)</td>', right(body))


def institution_row(body: str, iid: int) -> str:
    rows = re.findall(r"<tr>.*?</tr>", right(body), re.DOTALL)
    found = [row for row in rows if f"/institutions/{iid}/" in row]
    assert len(found) == 1, f"institution {iid} is not listed"
    return found[0]


def post(client: TestClient, path: str, data: dict[str, str] | None = None) -> Response:
    return client.post(path, data=data or {}, follow_redirects=False)


def assert_redirect(response: Response, location: str) -> None:
    assert response.status_code == 303, response.text
    assert response.headers["location"] == location


def assert_form_refused(response: Response, message: str, value: str) -> None:
    assert response.status_code == 400
    assert html.escape(message, quote=False) in response.text
    assert f'value="{html.escape(value)}"' in response.text
    assert 'aria-invalid="true"' in response.text
    assert current_tabs(response.text) == [TAB]


def assert_region_not_found(response: Response) -> None:
    assert response.status_code == 404
    body = response.text
    assert "<h1>Region not found</h1>" in body
    assert "This region does not exist. It may have been deleted." in body
    assert '<a href="/admin/institutions">' in body
    assert current_tabs(body) == [TAB]
    assert "Traceback" not in body


def assert_institution_not_found(response: Response) -> None:
    assert response.status_code == 404
    body = response.text
    assert "<h1>Educational institution not found</h1>" in body
    assert (
        "This educational institution does not exist in this region. It may have been deleted."
        in body
    )
    assert '<a href="/admin/institutions">' in body
    assert current_tabs(body) == [TAB]
    assert "Traceback" not in body


# ---------------------------------------------------------------------------------------------
# The two lists
# ---------------------------------------------------------------------------------------------


def test_the_empty_tab(admin_client: TestClient) -> None:
    """US1-1, FR-004, FR-009."""
    response = admin_client.get(TAB)
    assert response.status_code == 200
    body = response.text
    assert "<h1>Educational institutions</h1>" in body
    assert "No regions yet" in left(body)
    assert "Select a region" in right(body)
    assert current_tabs(body) == [TAB]


def test_regions_are_sorted_ignoring_case(admin_client: TestClient, session: Session) -> None:
    """US1-3, FR-007."""
    for name in ("Odesa", "kyiv", "Lviv"):
        add_region(session, name)
    assert listed_regions(admin_client.get(TAB).text) == ["kyiv", "Lviv", "Odesa"]


def test_a_deactivated_region_is_marked(admin_client: TestClient, session: Session) -> None:
    """FR-008."""
    kyiv = add_region(session, "Kyiv")
    odesa = add_region(session, "Odesa", active=False)
    body = admin_client.get(TAB).text
    assert "Deactivated" in region_item(body, odesa)
    assert "Deactivated" not in region_item(body, kyiv)


def test_the_selected_region_is_highlighted(admin_client: TestClient, session: Session) -> None:
    """FR-002, research D11: one link marked, and it is that region's."""
    add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    body = admin_client.get(region_path(lviv)).text
    assert selected_regions(body) == [region_path(lviv)]
    assert 'class="selected"' in region_item(body, lviv)
    assert selected_regions(admin_client.get(TAB).text) == []


def test_the_right_side_lists_only_the_selected_regions_institutions(
    admin_client: TestClient, session: Session
) -> None:
    """US2-7, FR-011, FR-012."""
    kyiv = add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    add_institution(session, kyiv, "Zaporizhzhia College")
    add_institution(session, kyiv, "art school", active=False)
    add_institution(session, kyiv, "Academy")
    add_institution(session, lviv, "Lviv University")
    body = admin_client.get(region_path(kyiv)).text
    assert "Educational institutions in “Kyiv”" in right(body)
    assert listed_institutions(body) == ["Academy", "art school", "Zaporizhzhia College"]
    statuses = re.findall(r"<td>(Active|Deactivated)</td>", right(body))
    assert statuses == ["Active", "Deactivated", "Active"]


def test_a_region_with_no_institutions(admin_client: TestClient, session: Session) -> None:
    """FR-013."""
    kyiv = add_region(session, "Kyiv")
    assert "No educational institutions yet" in right(admin_client.get(region_path(kyiv)).text)


def test_with_no_region_selected_there_are_no_institution_actions(
    admin_client: TestClient, session: Session
) -> None:
    """US2-1, FR-004."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy")
    section = right(admin_client.get(TAB).text)
    assert "Select a region" in section
    assert "<form" not in section
    assert "<button" not in section
    assert "/institutions/new" not in section
    assert "Academy" not in section


def test_the_selection_survives_a_reload(admin_client: TestClient, session: Session) -> None:
    """US2-8, FR-003, SC-004."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy")
    assert admin_client.get(region_path(kyiv)).text == admin_client.get(region_path(kyiv)).text


def test_an_unknown_region_is_not_found(admin_client: TestClient) -> None:
    assert_region_not_found(admin_client.get(region_path(MISSING)))


def test_a_non_integer_id_gets_the_normal_not_found_page(admin_client: TestClient) -> None:
    response = admin_client.get(f"{TAB}/regions/abc")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "admin-tabs" not in response.text


# ---------------------------------------------------------------------------------------------
# User story 1: create regions
# ---------------------------------------------------------------------------------------------


def test_the_tab_offers_create_for_regions(admin_client: TestClient) -> None:
    """FR-010."""
    assert '<a href="/admin/institutions/regions/new" role="button">Create</a>' in left(
        admin_client.get(TAB).text
    )


def test_the_region_create_form(admin_client: TestClient) -> None:
    response = admin_client.get(f"{TAB}/regions/new")
    assert response.status_code == 200
    body = response.text
    assert "<h1>New region</h1>" in body
    assert '<form method="post" action="/admin/institutions/regions">' in body
    field = re.search(r'<input[^>]*name="name"[^>]*>', body)
    assert field is not None
    assert 'maxlength="200"' in field.group(0)
    assert "required" in field.group(0)
    assert 'value=""' in field.group(0)
    assert ">Save</button>" in body
    assert '<a href="/admin/institutions">Cancel</a>' in body
    assert "aria-invalid" not in body
    assert current_tabs(body) == [TAB]


def test_create_a_region_selects_it(admin_client: TestClient, session: Session) -> None:
    """US1-2, FR-022."""
    response = post(admin_client, f"{TAB}/regions", {"name": "Kyiv"})
    kyiv = region_id(session, "Kyiv")
    assert_redirect(response, region_path(kyiv))
    assert region_names(session) == [("Kyiv", True)]
    body = admin_client.get(region_path(kyiv)).text
    assert listed_regions(body) == ["Kyiv"]
    assert selected_regions(body) == [region_path(kyiv)]
    assert "Deactivated" not in region_item(body, kyiv)
    assert "No regions yet" not in body


def test_a_duplicate_region_is_refused_with_the_value_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US1-4."""
    add_region(session, "Kyiv")
    before = regions(session)
    response = post(admin_client, f"{TAB}/regions", {"name": "  KYIV  "})
    assert_form_refused(response, REGION_DUPLICATE.format("Kyiv"), "  KYIV  ")
    assert '<form method="post" action="/admin/institutions/regions">' in response.text
    assert regions(session) == before


def test_a_cyrillic_duplicate_region_is_refused(admin_client: TestClient, session: Session) -> None:
    add_region(session, "Київ")
    response = post(admin_client, f"{TAB}/regions", {"name": "КИЇВ"})
    assert_form_refused(response, REGION_DUPLICATE.format("Київ"), "КИЇВ")


@pytest.mark.parametrize(
    ("value", "message"),
    [("", EMPTY), ("   ", EMPTY), ("a" * 201, TOO_LONG), ("Ky\tiv", CONTROL)],
    ids=["empty", "spaces", "too-long", "tab"],
)
def test_an_invalid_region_name_is_refused_with_the_value_kept(
    admin_client: TestClient, session: Session, value: str, message: str
) -> None:
    """US1-5, FR-025."""
    assert_form_refused(post(admin_client, f"{TAB}/regions", {"name": value}), message, value)
    assert regions(session) == []


def test_outer_spaces_are_removed_from_a_region_name(
    admin_client: TestClient, session: Session
) -> None:
    """US1-6."""
    post(admin_client, f"{TAB}/regions", {"name": "  Kharkiv Region  "})
    assert region_names(session) == [("Kharkiv Region", True)]


def test_reloading_after_creating_a_region_adds_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """FR-041, SC-008: after the redirect, a reload repeats only the `GET`."""
    response = admin_client.post(f"{TAB}/regions", data={"name": "Kyiv"})
    assert response.status_code == 200  # the redirect was followed to the region
    admin_client.get(response.url.path)
    admin_client.get(response.url.path)
    assert region_names(session) == [("Kyiv", True)]


# ---------------------------------------------------------------------------------------------
# User story 2: create institutions
# ---------------------------------------------------------------------------------------------


def test_a_selected_active_region_offers_create(admin_client: TestClient, session: Session) -> None:
    """US2-2, FR-014."""
    kyiv = add_region(session, "Kyiv")
    section = right(admin_client.get(region_path(kyiv)).text)
    assert f'<a href="{region_path(kyiv)}/institutions/new" role="button">Create</a>' in section
    assert REGION_INACTIVE not in section


def test_the_institution_create_form(admin_client: TestClient, session: Session) -> None:
    """FR-023: it names the region, and has no way to choose another."""
    kyiv = add_region(session, "Kyiv")
    response = admin_client.get(f"{region_path(kyiv)}/institutions/new")
    assert response.status_code == 200
    body = response.text
    assert "<h1>New educational institution in “Kyiv”</h1>" in body
    assert f'<form method="post" action="{region_path(kyiv)}/institutions">' in body
    assert re.findall(r"<input[^>]*name=\"([^\"]+)\"", body) == ["name"]
    assert "<select" not in body
    assert ">Save</button>" in body
    assert f'<a href="{region_path(kyiv)}">Cancel</a>' in body
    assert current_tabs(body) == [TAB]


def test_create_an_institution(admin_client: TestClient, session: Session) -> None:
    """US2-3."""
    kyiv = add_region(session, "Kyiv")
    response = post(admin_client, f"{region_path(kyiv)}/institutions", {"name": KPI})
    assert_redirect(response, region_path(kyiv))
    assert institution_names(session, kyiv) == [(KPI, True)]
    body = admin_client.get(region_path(kyiv)).text
    assert listed_institutions(body) == [KPI]
    assert selected_regions(body) == [region_path(kyiv)]
    assert "<td>Active</td>" in right(body)


def test_the_same_institution_name_in_two_regions(
    admin_client: TestClient, session: Session
) -> None:
    """US2-4."""
    kyiv = add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    post(admin_client, f"{region_path(kyiv)}/institutions", {"name": KPI})
    post(admin_client, f"{region_path(kyiv)}/institutions", {"name": "Academy"})
    response = post(admin_client, f"{region_path(lviv)}/institutions", {"name": KPI})
    assert_redirect(response, region_path(lviv))
    assert listed_institutions(admin_client.get(region_path(kyiv)).text) == ["Academy", KPI]
    assert listed_institutions(admin_client.get(region_path(lviv)).text) == [KPI]


def test_a_duplicate_institution_is_refused_with_the_value_kept(
    admin_client: TestClient, session: Session
) -> None:
    """US2-5, FR-021."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, KPI)
    before = institutions(session)
    value = f"  {KPI.upper()}  "
    response = post(admin_client, f"{region_path(kyiv)}/institutions", {"name": value})
    assert_form_refused(response, INSTITUTION_DUPLICATE.format(KPI), value)
    assert "<h1>New educational institution in “Kyiv”</h1>" in response.text
    assert institutions(session) == before


@pytest.mark.parametrize(
    ("value", "message"),
    [("", EMPTY), ("a" * 201, TOO_LONG), ("Aca\ndemy", CONTROL)],
    ids=["empty", "too-long", "newline"],
)
def test_an_invalid_institution_name_is_refused_with_the_value_kept(
    admin_client: TestClient, session: Session, value: str, message: str
) -> None:
    """US2-6."""
    kyiv = add_region(session, "Kyiv")
    response = post(admin_client, f"{region_path(kyiv)}/institutions", {"name": value})
    assert_form_refused(response, message, value)
    assert institutions(session) == []


def test_a_deactivated_region_refuses_new_institutions(
    admin_client: TestClient, session: Session
) -> None:
    """US3-6, US3-7, FR-014, FR-024, SC-007: no button, and a direct submission is refused."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy")
    set_active(session, Region, kyiv, False)
    before = institutions(session)

    section = right(admin_client.get(region_path(kyiv)).text)
    assert "/institutions/new" not in section
    assert REGION_INACTIVE in section
    assert listed_institutions(section) == ["Academy"]

    page = admin_client.get(f"{region_path(kyiv)}/institutions/new")
    assert page.status_code == 409
    assert REGION_INACTIVE in page.text
    assert "<form" not in page.text.split("</nav>", 1)[1].split("</main>")[0]
    assert f'<a href="{region_path(kyiv)}">Back to “Kyiv”</a>' in page.text
    assert current_tabs(page.text) == [TAB]

    for name in ("College", ""):
        response = post(admin_client, f"{region_path(kyiv)}/institutions", {"name": name})
        assert response.status_code == 409
        assert REGION_INACTIVE in response.text
    assert institutions(session) == before


def test_creating_in_a_missing_region_is_not_found(
    admin_client: TestClient, session: Session
) -> None:
    for name in ("Academy", ""):
        assert_region_not_found(
            post(admin_client, f"{region_path(MISSING)}/institutions", {"name": name})
        )
    assert_region_not_found(admin_client.get(f"{region_path(MISSING)}/institutions/new"))
    assert institutions(session) == []


# ---------------------------------------------------------------------------------------------
# User story 3: rename, deactivate/activate and delete regions
# ---------------------------------------------------------------------------------------------


def test_each_region_offers_its_actions(admin_client: TestClient, session: Session) -> None:
    """FR-010."""
    kyiv = add_region(session, "Kyiv")
    odesa = add_region(session, "Odesa", active=False)
    body = admin_client.get(TAB).text
    for rid in (kyiv, odesa):
        item = region_item(body, rid)
        assert f'<a href="{region_path(rid)}/rename">Rename</a>' in item
        assert f'<a href="{region_path(rid)}/delete">Delete</a>' in item
    assert f'<form method="post" action="{region_path(kyiv)}/deactivate">' in body
    assert f'<form method="post" action="{region_path(odesa)}/activate">' in body
    assert f"{region_path(kyiv)}/activate" not in body
    assert f"{region_path(odesa)}/deactivate" not in body


def test_the_region_rename_form_is_filled_in(admin_client: TestClient, session: Session) -> None:
    """US3-1, FR-026."""
    lvov = add_region(session, "Lvov")
    response = admin_client.get(f"{region_path(lvov)}/rename")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Rename region</h1>" in body
    assert f'<form method="post" action="{region_path(lvov)}/rename">' in body
    assert 'value="Lvov"' in body
    assert f'<a href="{region_path(lvov)}">Cancel</a>' in body
    assert current_tabs(body) == [TAB]


def test_rename_a_region(admin_client: TestClient, session: Session) -> None:
    """US3-2, FR-028."""
    lvov = add_region(session, "Lvov")
    assert_redirect(
        post(admin_client, f"{region_path(lvov)}/rename", {"name": "Lviv"}), region_path(lvov)
    )
    assert region_names(session) == [("Lviv", True)]
    assert listed_regions(admin_client.get(region_path(lvov)).text) == ["Lviv"]


def test_rename_onto_another_region_is_refused(admin_client: TestClient, session: Session) -> None:
    """US3-3."""
    add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    before = regions(session)
    response = post(admin_client, f"{region_path(lviv)}/rename", {"name": "KYIV"})
    assert_form_refused(response, REGION_DUPLICATE.format("Kyiv"), "KYIV")
    assert f'<form method="post" action="{region_path(lviv)}/rename">' in response.text
    assert regions(session) == before


def test_a_change_of_case_renames_a_region(admin_client: TestClient, session: Session) -> None:
    """US3-4, FR-027."""
    kyiv = add_region(session, "kyiv")
    assert_redirect(
        post(admin_client, f"{region_path(kyiv)}/rename", {"name": "Kyiv"}), region_path(kyiv)
    )
    assert region_names(session) == [("Kyiv", True)]


def test_an_invalid_region_rename_is_refused(admin_client: TestClient, session: Session) -> None:
    kyiv = add_region(session, "Kyiv")
    before = regions(session)
    for value, message in [("  ", EMPTY), ("b" * 201, TOO_LONG), ("Ky\niv", CONTROL)]:
        response = post(admin_client, f"{region_path(kyiv)}/rename", {"name": value})
        assert_form_refused(response, message, value)
    assert regions(session) == before


def test_deactivate_and_activate_a_region(admin_client: TestClient, session: Session) -> None:
    """US3-5, US3-6, US3-8."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy")
    assert_redirect(post(admin_client, f"{region_path(kyiv)}/deactivate"), region_path(kyiv))
    assert region_names(session) == [("Kyiv", False)]
    body = admin_client.get(region_path(kyiv)).text
    item = region_item(body, kyiv)
    assert "Deactivated" in item
    assert re.search(
        rf'action="{region_path(kyiv)}/activate">\s*<button[^>]*>Activate</button>', item
    )
    assert listed_institutions(body) == ["Academy"]
    assert "/institutions/new" not in right(body)
    assert REGION_INACTIVE in right(body)

    assert_redirect(post(admin_client, f"{region_path(kyiv)}/activate"), region_path(kyiv))
    assert region_names(session) == [("Kyiv", True)]
    body = admin_client.get(region_path(kyiv)).text
    assert f"{region_path(kyiv)}/institutions/new" in right(body)
    assert re.search(
        rf'action="{region_path(kyiv)}/deactivate">\s*<button[^>]*>Deactivate</button>', body
    )


def test_a_region_status_never_changes_its_institutions(
    admin_client: TestClient, session: Session
) -> None:
    """FR-033."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy")
    add_institution(session, kyiv, "College", active=False)
    before = institutions(session)
    post(admin_client, f"{region_path(kyiv)}/deactivate")
    assert institutions(session) == before
    post(admin_client, f"{region_path(kyiv)}/activate")
    assert institutions(session) == before


def test_repeating_a_region_status_change_changes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """FR-032."""
    kyiv = add_region(session, "Kyiv")
    before = regions(session)
    assert_redirect(post(admin_client, f"{region_path(kyiv)}/activate"), region_path(kyiv))
    assert regions(session) == before
    post(admin_client, f"{region_path(kyiv)}/deactivate")
    before = regions(session)
    assert_redirect(post(admin_client, f"{region_path(kyiv)}/deactivate"), region_path(kyiv))
    assert regions(session) == before


def test_the_region_delete_confirmation_deletes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """US3-9, FR-035."""
    test = add_region(session, "Test")
    before = regions(session)
    response = admin_client.get(f"{region_path(test)}/delete")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Delete region “Test”?</h1>" in body
    assert "Deleting a region cannot be undone." in body
    assert f'<form method="post" action="{region_path(test)}/delete">' in body
    assert ">Delete</button>" in body
    assert f'<a href="{region_path(test)}">Cancel</a>' in body
    assert current_tabs(body) == [TAB]
    assert regions(session) == before


def test_delete_an_empty_region(admin_client: TestClient, session: Session) -> None:
    """US3-10, FR-039: no region selected afterwards, and the name is free again."""
    test = add_region(session, "Test")
    assert_redirect(post(admin_client, f"{region_path(test)}/delete"), TAB)
    assert regions(session) == []
    assert "No regions yet" in admin_client.get(TAB).text
    post(admin_client, f"{TAB}/regions", {"name": "TEST"})
    assert region_names(session) == [("TEST", True)]


@pytest.mark.parametrize("active", [True, False], ids=["active", "deactivated"])
def test_a_region_holding_an_institution_cannot_be_deleted(
    admin_client: TestClient, session: Session, active: bool
) -> None:
    """US3-11, FR-036."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy", active=active)
    before = (regions(session), institutions(session))
    response = post(admin_client, f"{region_path(kyiv)}/delete")
    assert response.status_code == 409
    body = response.text
    assert NOT_EMPTY.format("Kyiv") in body
    assert ">Delete</button>" not in body
    assert f'action="{region_path(kyiv)}/delete"' not in body
    assert f'<a href="{region_path(kyiv)}">Back to “Kyiv”</a>' in body
    assert current_tabs(body) == [TAB]
    assert (regions(session), institutions(session)) == before


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("GET", "/rename"),
        ("POST", "/rename"),
        ("POST", "/deactivate"),
        ("POST", "/activate"),
        ("GET", "/delete"),
        ("POST", "/delete"),
        ("GET", "/institutions/new"),
        ("POST", "/institutions"),
    ],
)
def test_a_missing_region_is_not_found(admin_client: TestClient, method: str, suffix: str) -> None:
    """FR-043: e.g. deleted in another tab, even with an invalid name."""
    for name in ("Kyiv", ""):
        response = admin_client.request(
            method, f"{region_path(MISSING)}{suffix}", data={"name": name}, follow_redirects=False
        )
        assert_region_not_found(response)


# ---------------------------------------------------------------------------------------------
# User story 4: rename, deactivate/activate and delete institutions
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("region_active", [True, False], ids=["active-region", "inactive-region"])
def test_each_institution_offers_its_actions(
    admin_client: TestClient, session: Session, region_active: bool
) -> None:
    """FR-015: whatever the region's status."""
    kyiv = add_region(session, "Kyiv", active=region_active)
    academy = add_institution(session, kyiv, "Academy")
    college = add_institution(session, kyiv, "College", active=False)
    body = admin_client.get(region_path(kyiv)).text
    for iid in (academy, college):
        row = institution_row(body, iid)
        assert f'<a href="{institution_path(kyiv, iid)}/rename">Rename</a>' in row
        assert f'<a href="{institution_path(kyiv, iid)}/delete">Delete</a>' in row
    academy_row = institution_row(body, academy)
    college_row = institution_row(body, college)
    assert f'<form method="post" action="{institution_path(kyiv, academy)}/deactivate">' in (
        academy_row
    )
    assert f'<form method="post" action="{institution_path(kyiv, college)}/activate">' in (
        college_row
    )
    assert "/activate" not in academy_row
    assert "/deactivate" not in college_row


def test_the_institution_rename_form(admin_client: TestClient, session: Session) -> None:
    """US4-1, FR-026, FR-030: filled in, naming the region, with no way to choose another."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Acadmy")
    response = admin_client.get(f"{institution_path(kyiv, academy)}/rename")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Rename educational institution</h1>" in body
    assert "Region: Kyiv" in body
    assert f'<form method="post" action="{institution_path(kyiv, academy)}/rename">' in body
    assert 'value="Acadmy"' in body
    assert re.findall(r"<input[^>]*name=\"([^\"]+)\"", body) == ["name"]
    assert "<select" not in body
    assert f'<a href="{region_path(kyiv)}">Cancel</a>' in body
    assert current_tabs(body) == [TAB]


def test_rename_an_institution(admin_client: TestClient, session: Session) -> None:
    """US4-2."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Acadmy")
    response = post(admin_client, f"{institution_path(kyiv, academy)}/rename", {"name": "Academy"})
    assert_redirect(response, region_path(kyiv))
    assert institution_names(session, kyiv) == [("Academy", True)]
    assert listed_institutions(admin_client.get(region_path(kyiv)).text) == ["Academy"]


def test_rename_onto_another_institution_of_the_region_is_refused(
    admin_client: TestClient, session: Session
) -> None:
    """US4-3."""
    kyiv = add_region(session, "Kyiv")
    add_institution(session, kyiv, "Academy")
    college = add_institution(session, kyiv, "College")
    before = institutions(session)
    response = post(admin_client, f"{institution_path(kyiv, college)}/rename", {"name": "academy"})
    assert_form_refused(response, INSTITUTION_DUPLICATE.format("Academy"), "academy")
    assert "Region: Kyiv" in response.text
    assert institutions(session) == before


def test_rename_to_a_name_used_in_another_region(
    admin_client: TestClient, session: Session
) -> None:
    """US4-4."""
    kyiv = add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    add_institution(session, kyiv, "Academy")
    college = add_institution(session, lviv, "College")
    response = post(admin_client, f"{institution_path(lviv, college)}/rename", {"name": "Academy"})
    assert_redirect(response, region_path(lviv))
    assert institution_names(session, lviv) == [("Academy", True)]


def test_an_invalid_institution_rename_is_refused(
    admin_client: TestClient, session: Session
) -> None:
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    before = institutions(session)
    for value, message in [("", EMPTY), ("c" * 201, TOO_LONG), ("Aca\tdemy", CONTROL)]:
        response = post(admin_client, f"{institution_path(kyiv, academy)}/rename", {"name": value})
        assert_form_refused(response, message, value)
    assert institutions(session) == before


def test_rename_ignores_a_submitted_region(admin_client: TestClient, session: Session) -> None:
    """FR-030: an institution cannot be moved, even by a forged field."""
    kyiv = add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    academy = add_institution(session, kyiv, "Academy")
    response = post(
        admin_client,
        f"{institution_path(kyiv, academy)}/rename",
        {"name": "College", "region_id": str(lviv)},
    )
    assert_redirect(response, region_path(kyiv))
    assert institution_names(session, kyiv) == [("College", True)]
    assert institution_names(session, lviv) == []


def test_deactivate_and_activate_an_institution(admin_client: TestClient, session: Session) -> None:
    """US4-5."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    path = institution_path(kyiv, academy)
    assert_redirect(post(admin_client, f"{path}/deactivate"), region_path(kyiv))
    assert institution_names(session, kyiv) == [("Academy", False)]
    row = institution_row(admin_client.get(region_path(kyiv)).text, academy)
    assert "<td>Deactivated</td>" in row
    assert re.search(rf'action="{path}/activate">\s*<button[^>]*>Activate</button>', row)
    assert_redirect(post(admin_client, f"{path}/activate"), region_path(kyiv))
    assert institution_names(session, kyiv) == [("Academy", True)]
    row = institution_row(admin_client.get(region_path(kyiv)).text, academy)
    assert "<td>Active</td>" in row


def test_repeating_an_institution_status_change_changes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    kyiv = add_region(session, "Kyiv")
    path = institution_path(kyiv, add_institution(session, kyiv, "Academy"))
    before = institutions(session)
    assert_redirect(post(admin_client, f"{path}/activate"), region_path(kyiv))
    assert institutions(session) == before


def test_the_institution_delete_confirmation_deletes_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """US4-6, FR-035."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    before = institutions(session)
    response = admin_client.get(f"{institution_path(kyiv, academy)}/delete")
    assert response.status_code == 200
    body = response.text
    assert "<h1>Delete educational institution “Academy”?</h1>" in body
    assert "Region: Kyiv" in body
    assert "Deleting an educational institution cannot be undone." in body
    assert f'<form method="post" action="{institution_path(kyiv, academy)}/delete">' in body
    assert ">Delete</button>" in body
    assert f'<a href="{region_path(kyiv)}">Cancel</a>' in body
    assert current_tabs(body) == [TAB]
    assert institutions(session) == before


def test_delete_an_institution(admin_client: TestClient, session: Session) -> None:
    """US4-7, FR-039: the region stays selected, and the name is free again."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    college = add_institution(session, kyiv, "College")
    assert_redirect(
        post(admin_client, f"{institution_path(kyiv, academy)}/delete"), region_path(kyiv)
    )
    assert listed_institutions(admin_client.get(region_path(kyiv)).text) == ["College"]
    post(admin_client, f"{institution_path(kyiv, college)}/delete")
    body = admin_client.get(region_path(kyiv)).text
    assert "No educational institutions yet" in right(body)
    assert selected_regions(body) == [region_path(kyiv)]
    post(admin_client, f"{region_path(kyiv)}/institutions", {"name": "ACADEMY"})
    assert institution_names(session, kyiv) == [("ACADEMY", True)]


def test_an_institution_in_use_cannot_be_deleted(
    admin_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US4-8, FR-037."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    before = institutions(session)
    monkeypatch.setattr(
        app.services.institutions, "count_institution_uses", lambda session, institution_id: 1
    )
    response = post(admin_client, f"{institution_path(kyiv, academy)}/delete")
    assert response.status_code == 409
    body = response.text
    assert IN_USE.format("Academy") in body
    assert ">Delete</button>" not in body
    assert f'action="{institution_path(kyiv, academy)}/delete"' not in body
    assert f'<form method="post" action="{institution_path(kyiv, academy)}/deactivate">' in body
    assert f'<a href="{region_path(kyiv)}">Back to “Kyiv”</a>' in body
    assert current_tabs(body) == [TAB]
    assert institutions(session) == before


def test_a_deactivated_institution_in_use_offers_no_deactivate(
    admin_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy", active=False)
    monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda *_: 2)
    response = post(admin_client, f"{institution_path(kyiv, academy)}/delete")
    assert response.status_code == 409
    assert IN_USE.format("Academy") in response.text
    assert "/deactivate" not in response.text


def test_institutions_of_a_deactivated_region_stay_manageable(
    admin_client: TestClient, session: Session
) -> None:
    """US4-9."""
    kyiv = add_region(session, "Kyiv", active=False)
    path = institution_path(kyiv, add_institution(session, kyiv, "Academy"))
    assert_redirect(post(admin_client, f"{path}/rename", {"name": "College"}), region_path(kyiv))
    assert_redirect(post(admin_client, f"{path}/deactivate"), region_path(kyiv))
    assert institution_names(session, kyiv) == [("College", False)]
    assert_redirect(post(admin_client, f"{path}/activate"), region_path(kyiv))
    assert admin_client.get(f"{path}/delete").status_code == 200
    assert_redirect(post(admin_client, f"{path}/delete"), region_path(kyiv))
    assert institution_names(session, kyiv) == []


INSTITUTION_REQUESTS = [
    ("GET", "/rename"),
    ("POST", "/rename"),
    ("POST", "/deactivate"),
    ("POST", "/activate"),
    ("GET", "/delete"),
    ("POST", "/delete"),
]


@pytest.mark.parametrize(("method", "suffix"), INSTITUTION_REQUESTS)
def test_an_institution_named_with_another_region_is_not_found(
    admin_client: TestClient, session: Session, method: str, suffix: str
) -> None:
    """Spec edge case, FR-043: nothing changes, and nothing moves."""
    kyiv = add_region(session, "Kyiv")
    lviv = add_region(session, "Lviv")
    academy = add_institution(session, kyiv, "Academy")
    before = institutions(session)
    response = admin_client.request(
        method,
        f"{institution_path(lviv, academy)}{suffix}",
        data={"name": "Hacked"},
        follow_redirects=False,
    )
    assert_institution_not_found(response)
    assert institutions(session) == before


@pytest.mark.parametrize(("method", "suffix"), INSTITUTION_REQUESTS)
def test_a_missing_institution_is_not_found(
    admin_client: TestClient, session: Session, method: str, suffix: str
) -> None:
    kyiv = add_region(session, "Kyiv")
    response = admin_client.request(
        method,
        f"{institution_path(kyiv, MISSING)}{suffix}",
        data={"name": "Academy"},
        follow_redirects=False,
    )
    assert_institution_not_found(response)


@pytest.mark.parametrize(("method", "suffix"), INSTITUTION_REQUESTS)
def test_an_institution_in_a_missing_region_is_region_not_found(
    admin_client: TestClient, session: Session, method: str, suffix: str
) -> None:
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    response = admin_client.request(
        method,
        f"{institution_path(MISSING, academy)}{suffix}",
        data={"name": "Academy"},
        follow_redirects=False,
    )
    assert_region_not_found(response)


def test_reloading_after_each_action_repeats_nothing(
    admin_client: TestClient, session: Session
) -> None:
    """SC-008: every action ends on a `GET` through a 303, so a reload changes nothing."""
    kyiv = add_region(session, "Kyiv")
    path = institution_path(kyiv, add_institution(session, kyiv, "Academy"))
    for action, data in [
        (f"{region_path(kyiv)}/rename", {"name": "Kyiv Region"}),
        (f"{region_path(kyiv)}/institutions", {"name": "College"}),
        (f"{path}/rename", {"name": "Academy of Arts"}),
        (f"{path}/deactivate", {}),
        (f"{path}/activate", {}),
        (f"{path}/delete", {}),
    ]:
        response = admin_client.post(action, data=data)
        assert response.url.path == region_path(kyiv), action
        before = (regions(session), institutions(session))
        admin_client.get(region_path(kyiv))
        assert (regions(session), institutions(session)) == before, action
