"""The Educational institutions tab over HTTP: the two lists, and creating, renaming,
deactivating, activating and deleting regions and institutions.

See specs/007-region-and-institutions-management/spec.md user stories 1–4, and
contracts/http-routes.md. The messages are asserted verbatim. Every test runs once per engine; the
`session` fixture opens the same database the application serves, so tests can arrange and inspect
rows directly.
"""

import re

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session, select

import app.services.institutions
from app.core.db import utc_now
from app.main import app as app_module
from app.models import (
    AccessLevel,
    Enrolment,
    Institution,
    Region,
    Role,
    SchoolClass,
    Team,
    User,
    UserRole,
)
from app.schemas.names import name_key
from tests import html as dom
from tests.conftest import ClientAs, invite_and_accept

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
    tabs = dom.nav(body, "Administrator area")
    assert tabs, "the page has no admin tab row"
    return [tab.href for tab in tabs if tab.attrs.get("aria-current") == "page"]


def _section(body: str, heading: str) -> dom.Element:
    """The section whose own heading starts with `heading`."""
    found = [
        section
        for section in dom.parse(body).find_all("section")
        if any(h.text().startswith(heading) for h in section.find_all("h2"))
    ]
    assert len(found) == 1, f"expected one section headed {heading!r}, found {len(found)}"
    return found[0]


def left(body: str) -> str:
    """The region list, as HTML that can be queried again."""
    return dom.outer_html(body, _section(body, "Regions"))


def right(body: str) -> str:
    """The institution list of the selected region, as HTML that can be queried again."""
    return dom.outer_html(body, _section(body, "Educational institutions"))


def _region_items(body: str) -> list[tuple[dom.Element, str]]:
    """Each region's list item, with the region link's `href`."""
    fragment = left(body)
    items = []
    for item in dom.parse(fragment).find_all("li"):
        hrefs = [a.attrs.get("href", "") for a in item.find_all("a")]
        if hrefs and re.fullmatch(r"/admin/institutions/regions/\d+", hrefs[0]):
            items.append((item, hrefs[0]))
    return items


def listed_regions(body: str) -> list[str]:
    """The region names in the order the left list shows them."""
    return [item.find_all("a")[0].text() for item, _ in _region_items(body)]


def selected_regions(body: str) -> list[str]:
    return [link.href for link in dom.links(body) if link.attrs.get("aria-current") == "true"]


def region_item(body: str, rid: int) -> str:
    fragment = left(body)
    found = [
        item
        for item in dom.parse(fragment).find_all("li")
        if [a.attrs.get("href") for a in item.find_all("a")][:1] == [f"{TAB}/regions/{rid}"]
    ]
    assert len(found) == 1, f"region {rid} is not listed"
    return dom.outer_html(fragment, found[0])


def listed_institutions(body: str) -> list[str]:
    """The institution names in the order the right list shows them."""
    return [row["Name"] for row in dom.table_rows(right(body))]


def institution_row(body: str, iid: int) -> str:
    fragment = right(body)
    rows = [
        tr
        for tbody in dom.parse(fragment).find_all("tbody")
        for tr in tbody.find_all("tr")
        if any(
            f"/institutions/{iid}/" in link.href for link in dom.links(dom.outer_html(fragment, tr))
        )
        or any(f"/institutions/{iid}/" in f.action for f in dom.forms(dom.outer_html(fragment, tr)))
    ]
    assert len(rows) == 1, f"institution {iid} is not listed"
    return dom.outer_html(fragment, rows[0])


def cells(row: str) -> list[str]:
    """The texts of a table row's cells."""
    return [cell.text() for cell in dom.parse(row).iter() if cell.tag in ("td", "th")]


def buttons(body: str) -> list[tuple[str, str]]:
    """`(form action, button text)` for every button inside a form."""
    return [(form.action, b.text) for form in dom.forms(body) for b in form.buttons]


def post(client: TestClient, path: str, data: dict[str, str] | None = None) -> Response:
    return client.post(path, data=data or {}, follow_redirects=False)


def assert_redirect(response: Response, location: str) -> None:
    assert response.status_code == 303, response.text
    assert response.headers["location"] == location


def assert_form_refused(response: Response, message: str, value: str) -> None:
    assert response.status_code == 400
    assert message in dom.text(response.text, "main")
    name = dom.control(response.text, "name")
    assert name["value"] == value
    assert name.get("aria-invalid") == "true"
    assert current_tabs(response.text) == [TAB]


def assert_region_not_found(response: Response) -> None:
    assert response.status_code == 404
    body = response.text
    assert dom.h1(body) == "Region not found"
    assert "This region does not exist. It may have been deleted." in body
    assert "/admin/institutions" in [a.href for a in dom.content_links(body)]
    assert current_tabs(body) == [TAB]
    assert "Traceback" not in body


def assert_institution_not_found(response: Response) -> None:
    assert response.status_code == 404
    body = response.text
    assert dom.h1(body) == "Educational institution not found"
    assert (
        "This educational institution does not exist in this region. It may have been deleted."
        in body
    )
    assert "/admin/institutions" in [a.href for a in dom.content_links(body)]
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
    assert dom.h1(body) == "Educational institutions"
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
    assert "selected" in dom.parse(region_item(body, lviv)).find_all("li")[0].classes()
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
    statuses = [row["Status"] for row in dom.table_rows(right(body))]
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
    assert dom.forms(section) == []
    assert dom.parse(section).find_all("button") == []
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
    assert dom.nav(response.text, "Administrator area") == []


# ---------------------------------------------------------------------------------------------
# User story 1: create regions
# ---------------------------------------------------------------------------------------------


def test_the_tab_offers_create_for_regions(admin_client: TestClient) -> None:
    """FR-010."""
    create = [
        a for a in dom.links(left(admin_client.get(TAB).text)) if a.href == f"{TAB}/regions/new"
    ]
    assert [(a.text, a.attrs.get("role")) for a in create] == [("Create region", "button")]


def test_the_region_create_form(admin_client: TestClient) -> None:
    response = admin_client.get(f"{TAB}/regions/new")
    assert response.status_code == 200
    body = response.text
    assert dom.h1(body) == "New region"
    assert ("post", "/admin/institutions/regions") in dom.form_targets(body)
    field = dom.control(body, "name")
    assert field["maxlength"] == "200"
    assert "required" in field
    assert field["value"] == ""
    assert "Save" in [b.text for f in dom.forms(body) for b in f.buttons]
    assert ("/admin/institutions", "Cancel") in dom.link_pairs(body)
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
    assert ("post", "/admin/institutions/regions") in dom.form_targets(response.text)
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
    assert (
        f"{region_path(kyiv)}/institutions/new",
        "Create educational institution",
        "button",
    ) in [(a.href, a.text, a.attrs.get("role")) for a in dom.links(section)]
    assert REGION_INACTIVE not in section


def test_the_institution_create_form(admin_client: TestClient, session: Session) -> None:
    """FR-023: it names the region, and has no way to choose another."""
    kyiv = add_region(session, "Kyiv")
    response = admin_client.get(f"{region_path(kyiv)}/institutions/new")
    assert response.status_code == 200
    body = response.text
    assert dom.h1(body) == "New educational institution in “Kyiv”"
    assert ("post", f"{region_path(kyiv)}/institutions") in dom.form_targets(body)
    assert [i.name for f in dom.forms(body, "main") for i in f.inputs] == ["name"]
    assert dom.parse(body).find_all("select") == []
    assert "Save" in [b.text for f in dom.forms(body) for b in f.buttons]
    assert (f"{region_path(kyiv)}", "Cancel") in dom.link_pairs(body)
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
    assert "Active" in [row["Status"] for row in dom.table_rows(right(body))]


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
    assert dom.h1(response.text) == "New educational institution in “Kyiv”"
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
    assert dom.forms(page.text, "main") == []
    assert (f"{region_path(kyiv)}", "Back to “Kyiv”") in dom.link_pairs(page.text)
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
        assert (f"{region_path(rid)}/rename", "Rename") in dom.link_pairs(item)
        assert (f"{region_path(rid)}/delete", "Delete") in dom.link_pairs(item)
    assert (f"{region_path(kyiv)}/deactivate", "Deactivate") in dom.link_pairs(body)
    assert ("post", f"{region_path(odesa)}/activate") in dom.form_targets(body)
    assert f"{region_path(kyiv)}/activate" not in body
    assert f"{region_path(odesa)}/deactivate" not in body


def test_the_region_rename_form_is_filled_in(admin_client: TestClient, session: Session) -> None:
    """US3-1, FR-026."""
    lvov = add_region(session, "Lvov")
    response = admin_client.get(f"{region_path(lvov)}/rename")
    assert response.status_code == 200
    body = response.text
    assert dom.h1(body) == "Rename region"
    assert ("post", f"{region_path(lvov)}/rename") in dom.form_targets(body)
    assert "Lvov" in [i.value for f in dom.forms(body) for i in f.inputs]
    assert (f"{region_path(lvov)}", "Cancel") in dom.link_pairs(body)
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
    assert ("post", f"{region_path(lviv)}/rename") in dom.form_targets(response.text)
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
    assert (f"{region_path(kyiv)}/activate", "Activate") in buttons(item)
    assert listed_institutions(body) == ["Academy"]
    assert "/institutions/new" not in right(body)
    assert REGION_INACTIVE in right(body)

    assert_redirect(post(admin_client, f"{region_path(kyiv)}/activate"), region_path(kyiv))
    assert region_names(session) == [("Kyiv", True)]
    body = admin_client.get(region_path(kyiv)).text
    assert f"{region_path(kyiv)}/institutions/new" in right(body)
    assert (f"{region_path(kyiv)}/deactivate", "Deactivate") in dom.link_pairs(body)


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
    assert dom.h1(body) == "Delete region “Test”?"
    assert "Deleting a region cannot be undone." in body
    assert ("post", f"{region_path(test)}/delete") in dom.form_targets(body)
    assert "Delete" in [b.text for f in dom.forms(body) for b in f.buttons]
    assert (f"{region_path(test)}", "Cancel") in dom.link_pairs(body)
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
    assert "Delete" not in [b.text for f in dom.forms(body) for b in f.buttons]
    assert f"{region_path(kyiv)}/delete" not in [f.action for f in dom.forms(body)]
    assert (f"{region_path(kyiv)}", "Back to “Kyiv”") in dom.link_pairs(body)
    assert current_tabs(body) == [TAB]
    assert (regions(session), institutions(session)) == before


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("GET", "/rename"),
        ("POST", "/rename"),
        ("GET", "/deactivate"),
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
        assert (f"{institution_path(kyiv, iid)}/rename", "Rename") in dom.link_pairs(row)
        assert (f"{institution_path(kyiv, iid)}/delete", "Delete") in dom.link_pairs(row)
    academy_row = institution_row(body, academy)
    college_row = institution_row(body, college)
    assert (f"{institution_path(kyiv, academy)}/deactivate", "Deactivate") in dom.link_pairs(
        academy_row
    )
    assert ("post", f"{institution_path(kyiv, college)}/activate") in dom.form_targets(college_row)
    assert "/activate" not in academy_row
    assert "/deactivate" not in college_row


def test_the_institution_rename_form(admin_client: TestClient, session: Session) -> None:
    """US4-1, FR-026, FR-030: filled in, naming the region, with no way to choose another."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Acadmy")
    response = admin_client.get(f"{institution_path(kyiv, academy)}/rename")
    assert response.status_code == 200
    body = response.text
    assert dom.h1(body) == "Rename educational institution"
    assert "Region: Kyiv" in body
    assert ("post", f"{institution_path(kyiv, academy)}/rename") in dom.form_targets(body)
    assert "Acadmy" in [i.value for f in dom.forms(body) for i in f.inputs]
    assert [i.name for f in dom.forms(body, "main") for i in f.inputs] == ["name"]
    assert dom.parse(body).find_all("select") == []
    assert (f"{region_path(kyiv)}", "Cancel") in dom.link_pairs(body)
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
    assert "Deactivated" in cells(row)
    assert (f"{path}/activate", "Activate") in buttons(row)
    assert_redirect(post(admin_client, f"{path}/activate"), region_path(kyiv))
    assert institution_names(session, kyiv) == [("Academy", True)]
    row = institution_row(admin_client.get(region_path(kyiv)).text, academy)
    assert "Active" in cells(row)


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
    assert dom.h1(body) == "Delete educational institution “Academy”?"
    assert "Region: Kyiv" in body
    assert "Deleting an educational institution cannot be undone." in body
    assert ("post", f"{institution_path(kyiv, academy)}/delete") in dom.form_targets(body)
    assert "Delete" in [b.text for f in dom.forms(body) for b in f.buttons]
    assert (f"{region_path(kyiv)}", "Cancel") in dom.link_pairs(body)
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
    assert "Delete" not in [b.text for f in dom.forms(body) for b in f.buttons]
    assert f"{institution_path(kyiv, academy)}/delete" not in [f.action for f in dom.forms(body)]
    assert (f"{institution_path(kyiv, academy)}/deactivate", "button") in [
        (a.href, a.attrs.get("role")) for a in dom.links(body)
    ]
    assert (f"{region_path(kyiv)}", "Back to “Kyiv”") in dom.link_pairs(body)
    assert current_tabs(body) == [TAB]
    assert institutions(session) == before


def test_an_institution_linked_to_a_teacher_cannot_be_deleted(
    admin_client: TestClient, session: Session
) -> None:
    """Milestone 8 FR-012, US3-8: a real teacher link, with no stand-in for the count."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    invite_and_accept(
        app_module.state.engine,
        app_module.state.settings,
        email="olena@example.org",
        institutions={academy: AccessLevel.READ},
    )
    before = institutions(session)
    response = post(admin_client, f"{institution_path(kyiv, academy)}/delete")
    assert response.status_code == 409
    assert IN_USE.format("Academy") in response.text
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
    ("GET", "/deactivate"),
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


# ---------------------------------------------------------------------------------------------
# Milestone 9: confirmation before deactivating a region or an institution
# ---------------------------------------------------------------------------------------------
#
# See specs/009-classes-students-management/spec.md FR-017 and research D15. Deactivation now
# signs out and hides the students below, so it is confirmed first; the `POST` is unchanged.

SIGNED_OUT = "Its students will be signed out and hidden until it is activated again."


def test_the_region_confirmation_changes_nothing_and_posts_to_the_route(
    admin_client: TestClient, session: Session
) -> None:
    kyiv = add_region(session, "Kyiv")
    before = regions(session)
    response = admin_client.get(f"{region_path(kyiv)}/deactivate")
    assert response.status_code == 200
    body = response.text
    assert dom.h1(body) == "Deactivate region “Kyiv”?"
    assert SIGNED_OUT in body
    assert ("post", f"{region_path(kyiv)}/deactivate") in dom.form_targets(body)
    assert (f"{region_path(kyiv)}", "Cancel") in dom.link_pairs(body)
    assert current_tabs(body) == [TAB]
    assert regions(session) == before
    assert_redirect(post(admin_client, f"{region_path(kyiv)}/deactivate"), region_path(kyiv))
    assert region_names(session) == [("Kyiv", False)]


def test_the_institution_confirmation_changes_nothing_and_posts_to_the_route(
    admin_client: TestClient, session: Session
) -> None:
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    path = institution_path(kyiv, academy)
    before = institutions(session)
    response = admin_client.get(f"{path}/deactivate")
    assert response.status_code == 200
    body = response.text
    assert dom.h1(body) == "Deactivate educational institution “Academy”?"
    assert "Region: Kyiv" in body
    assert SIGNED_OUT in body
    assert ("post", f"{path}/deactivate") in dom.form_targets(body)
    assert institutions(session) == before
    assert_redirect(post(admin_client, f"{path}/deactivate"), region_path(kyiv))
    assert institution_names(session, kyiv) == [("Academy", False)]


@pytest.mark.parametrize("email", ["teacher@example.com", "student@example.com"])
def test_the_confirmations_are_for_administrators_only(
    client: TestClient, client_as: ClientAs, session: Session, email: str
) -> None:
    """Anonymous visitors are sent to sign in; teachers and students are denied."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    for path in (
        f"{region_path(kyiv)}/deactivate",
        f"{institution_path(kyiv, academy)}/deactivate",
    ):
        anonymous = client.get(path, follow_redirects=False)
        assert anonymous.status_code == 303
        assert anonymous.headers["location"].startswith("/login?next=")
        assert client_as(email).get(path).status_code == 403


# ---------------------------------------------------------------------------------------------
# Milestone 9: deleting an institution that holds classes (user story 8)
# ---------------------------------------------------------------------------------------------


def add_class(session: Session, institution_id: int, name: str, active: bool = True) -> int:
    now = utc_now()
    school_class = SchoolClass(
        institution_id=institution_id,
        name=name,
        name_key=name_key(name),
        year_of_study=1,
        is_active=active,
        created_at=now,
        updated_at=now,
    )
    session.add(school_class)
    session.commit()
    assert school_class.id is not None
    return school_class.id


def stored_classes(session: Session) -> list[int]:
    session.expire_all()
    return sorted(c.id for c in session.exec(select(SchoolClass)) if c.id is not None)


@pytest.mark.parametrize(
    ("count", "sentence"),
    [
        (0, None),
        (1, "Its class will be deleted too."),
        (2, "Its 2 classes will be deleted too."),
    ],
)
def test_empty_classes_are_announced_and_deleted_with_the_institution(
    admin_client: TestClient, session: Session, count: int, sentence: str | None
) -> None:
    """US8-1, FR-007."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    for number in range(count):
        add_class(session, academy, f"KN-{number}", active=number == 0)
    path = institution_path(kyiv, academy)
    body = admin_client.get(f"{path}/delete").text
    if sentence is None:
        assert "will be deleted too." not in body
    else:
        assert sentence in body
    assert_redirect(post(admin_client, f"{path}/delete"), region_path(kyiv))
    assert institution_names(session, kyiv) == []
    assert stored_classes(session) == []


@pytest.mark.parametrize("active", [True, False], ids=["active-class", "deactivated-class"])
def test_an_institution_with_an_enrolled_student_is_in_use(
    admin_client: TestClient, session: Session, active: bool
) -> None:
    """US8-2: blocked or not; nothing is deleted."""
    kyiv = add_region(session, "Kyiv")
    academy = add_institution(session, kyiv, "Academy")
    class_id = add_class(session, academy, "KN-21", active=active)
    now = utc_now()
    user = User(email="taras@example.org", is_active=True, created_at=now, updated_at=now)
    session.add(user)
    session.flush()
    assert user.id is not None
    session.add(UserRole(user_id=user.id, role=Role.STUDENT, created_at=now))
    session.add(Enrolment(user_id=user.id, class_id=class_id, created_at=now, updated_at=now))
    session.commit()
    before = (institutions(session), stored_classes(session))
    response = post(admin_client, f"{institution_path(kyiv, academy)}/delete")
    assert response.status_code == 409
    assert IN_USE.format("Academy") in response.text
    assert (institutions(session), stored_classes(session)) == before


def test_an_institution_with_only_a_deleted_team_is_in_use(
    admin_client: TestClient, session: Session
) -> None:
    """Milestone 11.1 US8-1, FR-017: refused as "in use", suggesting deactivation."""
    lviv = add_region(session, "Lviv")
    academy = add_institution(session, lviv, "Lviv Academy")
    now = utc_now()
    session.add(
        Team(
            institution_id=academy,
            name="Comets",
            name_key="comets",
            created_at=now,
            updated_at=now,
            deleted_at=now,
        )
    )
    session.commit()
    before = institutions(session)
    response = post(admin_client, f"{institution_path(lviv, academy)}/delete")
    assert response.status_code == 409
    assert IN_USE.format("Lviv Academy") in response.text
    assert institutions(session) == before
