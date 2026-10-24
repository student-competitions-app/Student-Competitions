"""User story 3: an administrator lists, edits and removes teachers.

See specs/008-teacher-management-consent/spec.md US3 (scenarios 1–10) and contracts/http-routes.md
§1. Teachers are created through the real invitation services (`invite_and_accept`). Every case
runs on both engines.
"""

import re
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import utc_now
from app.main import app
from app.models import (
    AccessLevel,
    ConsentRecord,
    Institution,
    Role,
    TeacherInstitution,
    TeacherProfile,
    User,
    UserSession,
)
from app.services.users import get_roles, get_user_by_email
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    invite_and_accept,
    make_institution,
    sign_in_directly,
)

READ, WRITE = AccessLevel.READ, AccessLevel.WRITE
OLENA = "olena@example.org"


def picked(body: str) -> list[tuple[str, bool]]:
    """`(value, checked)` of each institution checkbox of the picker."""
    return [
        (e.attrs.get("value", ""), "checked" in e.attrs)
        for e in html.parse(body).find_all("input")
        if e.attrs.get("name") == "institution"
    ]


def access_options(body: str) -> list[html.Option]:
    """Every option of every access select of the picker."""
    return [
        html.Option(o.attrs.get("value", ""), o.text(), "selected" in o.attrs)
        for select in html.parse(body).find_all("select")
        if select.attrs.get("name") == "access"
        for o in select.find_all("option")
    ]


@pytest.fixture
def places(client: TestClient) -> dict[str, int]:
    engine = app.state.engine
    return {
        "kyiv": make_institution(engine, "Kyiv Lyceum", "Kyiv"),
        "lviv": make_institution(engine, "Lviv School", "Lviv"),
        "odesa": make_institution(engine, "Odesa College", "Odesa"),
    }


def teacher(email: str = OLENA, first: str = "Olena", last: str = "Kovalenko", **kw: Any) -> int:
    return invite_and_accept(
        app.state.engine, app.state.settings, email=email, first=first, last=last, **kw
    )


def links_of(user_id: int) -> dict[int, tuple[str, Any, Any]]:
    with Session(app.state.engine) as session:
        rows = session.exec(select(TeacherInstitution).where(TeacherInstitution.user_id == user_id))
        return {
            row.institution_id: (row.access_level, row.created_at, row.updated_at) for row in rows
        }


def region_of(institution_id: int) -> int:
    with Session(app.state.engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


def edit_form(places: dict[str, int], **overrides: Any) -> dict[str, Any]:
    form: dict[str, Any] = {
        "first_name": "Olena",
        "last_name": "Kovalenko",
        "institution": [str(places["kyiv"]), str(places["lviv"])],
        "access": [f"{places['kyiv']}:write", f"{places['lviv']}:read"],
        "can_create_competitions": "on",
    }
    form.update(overrides)
    return {key: value for key, value in form.items() if value is not None}


def a_kyiv_lviv_teacher(places: dict[str, int]) -> int:
    return teacher(institutions={places["kyiv"]: WRITE, places["lviv"]: READ}, can_create=True)


# ---------------------------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------------------------


def test_with_no_teacher_the_tab_offers_the_invitation(admin_client: TestClient) -> None:
    """US3-1: the cast's directly seeded teachers are not current teachers."""
    body = admin_client.get("/admin/teachers").text
    assert "No teachers yet" in body
    assert "Invite teacher" in body
    assert TEACHER_EMAIL not in body


def test_the_list_is_sorted_and_shows_every_column(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US3-2, FR-038."""
    first = teacher("k@example.org", "Olena", "kovalenko", institutions={places["kyiv"]: WRITE})
    second = teacher(
        "a@example.org",
        "Petro",
        "Antonenko",
        institutions={places["lviv"]: READ, places["odesa"]: WRITE},
        can_create=True,
    )
    third = teacher("b@example.org", "Iryna", "bondar", institutions={places["odesa"]: READ})
    admin_client.post(
        f"/admin/institutions/regions/{region_of(places['odesa'])}/deactivate",
        follow_redirects=False,
    )
    body = admin_client.get("/admin/teachers").text
    order = [
        int(found[1])
        for link in html.content_links(body)
        if (found := re.fullmatch(r"/admin/teachers/(\d+)", link.href))
    ]
    assert order == [second, third, first]
    assert "Petro Antonenko" in body
    assert "a@example.org" in body
    assert "Lviv School (Lviv) — Read" in body
    assert "Odesa College (Odesa) — Write (deactivated)" in html.text(body, "main")
    cells = [value for row in html.table_rows(body) for value in row.values()]
    assert "Yes" in cells and "No" in cells
    assert utc_now().strftime("%Y-%m-%d") in cells
    assert "No teachers yet" not in body


# ---------------------------------------------------------------------------------------------
# The teacher page and editing
# ---------------------------------------------------------------------------------------------


def test_the_teacher_page_shows_the_email_but_not_as_a_field(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US3-3, FR-039."""
    user_id = a_kyiv_lviv_teacher(places)
    body = admin_client.get(f"/admin/teachers/{user_id}").text
    assert f"Email: {OLENA}" in body
    assert "email" not in [i.name for f in html.forms(body) for i in f.inputs]
    assert html.control(body, "first_name")["value"] == "Olena"
    assert html.control(body, "last_name")["value"] == "Kovalenko"
    kyiv = places["kyiv"]
    assert (str(kyiv), True) in picked(body)
    assert html.Option(f"{kyiv}:write", "Write", True) in access_options(body)
    assert "checked" in html.control(body, "can_create_competitions")


def test_an_edit_changes_only_what_changed(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US3-4, FR-040: Kyiv Write→Read and the setting off; Lviv byte-for-byte the same."""
    user_id = a_kyiv_lviv_teacher(places)
    before = links_of(user_id)
    response = admin_client.post(
        f"/admin/teachers/{user_id}",
        data=edit_form(
            places,
            access=[f"{places['kyiv']}:read", f"{places['lviv']}:read"],
            can_create_competitions=None,
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/teachers"
    after = links_of(user_id)
    assert after[places["lviv"]] == before[places["lviv"]]
    assert after[places["kyiv"]][0] == "read"
    assert after[places["kyiv"]][2] > before[places["kyiv"]][2]
    with Session(app.state.engine) as session:
        profile = session.get(TeacherProfile, user_id)
        assert profile is not None and profile.can_create_competitions is False


def test_adding_an_institution_adds_one_link(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US3-5."""
    user_id = a_kyiv_lviv_teacher(places)
    before = links_of(user_id)
    form = edit_form(
        places,
        institution=[str(places["kyiv"]), str(places["lviv"]), str(places["odesa"])],
        access=[f"{places['kyiv']}:write", f"{places['lviv']}:read", f"{places['odesa']}:write"],
    )
    assert admin_client.post(f"/admin/teachers/{user_id}", data=form).status_code == 200
    after = links_of(user_id)
    assert set(after) == {places["kyiv"], places["lviv"], places["odesa"]}
    assert after[places["odesa"]][0] == "write"
    for kept in ("kyiv", "lviv"):
        assert after[places[kept]] == before[places[kept]]


def test_a_deactivated_link_is_kept_with_its_level_and_can_be_removed(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US3-6, FR-011."""
    user_id = a_kyiv_lviv_teacher(places)
    lviv = places["lviv"]
    admin_client.post(
        f"/admin/institutions/regions/{region_of(lviv)}/institutions/{lviv}/deactivate",
        follow_redirects=False,
    )
    page = admin_client.get(f"/admin/teachers/{user_id}").text
    assert "Lviv School (Lviv) (deactivated)" in html.text(page, "main")
    assert f"{lviv}:read" not in [o.value for o in access_options(page)]
    before = links_of(user_id)

    kept = edit_form(places, access=[f"{places['kyiv']}:read", f"{lviv}:write"])
    response = admin_client.post(f"/admin/teachers/{user_id}", data=kept, follow_redirects=False)
    assert response.status_code == 303
    assert links_of(user_id)[lviv] == before[lviv]

    dropped = edit_form(
        places, institution=[str(places["kyiv"])], access=[f"{places['kyiv']}:read"]
    )
    response = admin_client.post(f"/admin/teachers/{user_id}", data=dropped, follow_redirects=False)
    assert response.status_code == 303
    assert set(links_of(user_id)) == {places["kyiv"]}
    assert "Lviv School" not in admin_client.get(f"/admin/teachers/{user_id}").text


@pytest.mark.parametrize("target", ["deactivated", "inactive-region", "unknown"])
def test_an_unavailable_institution_cannot_be_added(
    admin_client: TestClient, places: dict[str, int], target: str
) -> None:
    """US3-7, FR-009."""
    user_id = a_kyiv_lviv_teacher(places)
    if target == "deactivated":
        added = make_institution(app.state.engine, "Closed", "Kyiv", active=False)
    elif target == "inactive-region":
        added = make_institution(app.state.engine, "Far", "Kharkiv", region_active=False)
    else:
        added = 999_999
    before = links_of(user_id)
    form = edit_form(
        places,
        institution=[str(places["kyiv"]), str(places["lviv"]), str(added)],
        access=[f"{places['kyiv']}:write", f"{places['lviv']}:read", f"{added}:read"],
    )
    response = admin_client.post(f"/admin/teachers/{user_id}", data=form)
    assert response.status_code == 400
    assert "This educational institution cannot be selected." in response.text
    assert links_of(user_id) == before


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"institution": None}, "Pick at least one educational institution."),
        ({"access": ["{kyiv}:admin", "{lviv}:read"]}, "Choose Read or Write access"),
        ({"first_name": ""}, "Enter a first name."),
        ({"last_name": "a" * 101}, "The last name can be at most 100 characters."),
    ],
    ids=["none", "bad-level", "empty-name", "long-name"],
)
def test_an_invalid_edit_changes_nothing(
    admin_client: TestClient, places: dict[str, int], overrides: dict[str, Any], message: str
) -> None:
    """US3-9."""
    user_id = a_kyiv_lviv_teacher(places)
    before = links_of(user_id)
    resolved = {
        key: [item.format(**places) for item in value] if isinstance(value, list) else value
        for key, value in overrides.items()
    }
    form = edit_form(places, **resolved)
    response = admin_client.post(f"/admin/teachers/{user_id}", data=form)
    assert response.status_code == 400
    assert message in response.text
    for field in ("first_name", "last_name"):
        assert html.control(response.text, field)["value"] == form[field]
    assert links_of(user_id) == before
    with Session(app.state.engine) as session:
        olena = session.get(User, user_id)
        assert olena is not None and (olena.first_name, olena.last_name) == ("Olena", "Kovalenko")


def test_editing_keeps_the_teacher_signed_in(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """FR-041."""
    user_id = a_kyiv_lviv_teacher(places)
    browser = TestClient(app)
    sign_in_directly(browser, OLENA)
    form = edit_form(places, first_name="Olha")
    assert admin_client.post(f"/admin/teachers/{user_id}", data=form).status_code == 200
    assert browser.get("/", follow_redirects=False).status_code == 200


def test_a_reload_after_saving_repeats_nothing(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """FR-060: the 303 lands on the list, whose reload is a plain GET."""
    user_id = a_kyiv_lviv_teacher(places)
    landed = admin_client.post(f"/admin/teachers/{user_id}", data=edit_form(places))
    assert landed.url.path == "/admin/teachers"
    before = links_of(user_id)
    admin_client.get(landed.url.path)
    assert links_of(user_id) == before


# ---------------------------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------------------------


def test_the_confirmation_explains_the_removal_and_changes_nothing(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    user_id = a_kyiv_lviv_teacher(places)
    body = admin_client.get(f"/admin/teachers/{user_id}/remove").text
    assert "Remove Olena Kovalenko as a teacher?" in body
    assert (
        "They lose the teacher role, their institutions and the competitions setting. If they "
        "have no other role, they can no longer sign in. Their email, names and consent records "
        "stay until they delete their data."
    ) in body
    assert links_of(user_id)


def test_removing_a_teacher_with_no_other_role(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US3-10, FR-042."""
    user_id = a_kyiv_lviv_teacher(places)
    browser = TestClient(app)
    sign_in_directly(browser, OLENA)
    response = admin_client.post(f"/admin/teachers/{user_id}/remove", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/teachers"
    assert "No teachers yet" in admin_client.get("/admin/teachers").text
    with Session(app.state.engine) as session:
        olena = session.get(User, user_id)
        assert olena is not None
        assert olena.is_active is False
        assert (olena.email, olena.first_name) == (OLENA, "Olena")
        assert session.exec(select(UserSession).where(UserSession.user_id == user_id)).all() == []
        assert len(session.exec(select(ConsentRecord)).all()) == 1
    assert browser.get("/", follow_redirects=False).status_code == 303


def test_removing_an_administrator_who_teaches(
    admin_client: TestClient, client_as: ClientAs, places: dict[str, int]
) -> None:
    """US3-10: stays active as administrator, signed out everywhere."""
    user_id = teacher(ADMIN_STUDENT_EMAIL, institutions={places["kyiv"]: READ})
    other_browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)
    admin_client.post(f"/admin/teachers/{user_id}/remove")
    with Session(app.state.engine) as session:
        person = session.get(User, user_id)
        assert person is not None and person.is_active
        assert get_roles(session, user_id) == (Role.ADMIN, Role.STUDENT)
    assert other_browser.get("/", follow_redirects=False).status_code == 303


@pytest.mark.parametrize("who", ["unknown", "cast-teacher", "administrator", "removed"])
def test_not_a_current_teacher_is_not_found(
    admin_client: TestClient, places: dict[str, int], who: str
) -> None:
    """`404` "Teacher not found" for every page and action."""
    with Session(app.state.engine) as session:
        if who == "unknown":
            user_id = 999_999
        elif who == "cast-teacher":
            found = get_user_by_email(session, TEACHER_EMAIL)
            assert found is not None and found.id is not None
            user_id = found.id
        elif who == "administrator":
            found = get_user_by_email(session, ADMIN_EMAIL)
            assert found is not None and found.id is not None
            user_id = found.id
    if who == "removed":
        user_id = a_kyiv_lviv_teacher(places)
        admin_client.post(f"/admin/teachers/{user_id}/remove")
    for method, path, data in (
        ("GET", f"/admin/teachers/{user_id}", None),
        ("POST", f"/admin/teachers/{user_id}", edit_form(places)),
        ("GET", f"/admin/teachers/{user_id}/remove", None),
        ("POST", f"/admin/teachers/{user_id}/remove", None),
    ):
        response = admin_client.request(method, path, data=data)
        assert response.status_code == 404, (method, path)
        assert "Teacher not found" in response.text


def test_the_consent_date_is_the_latest_teacher_record(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    earlier = utc_now() - timedelta(days=3)
    invite_and_accept(
        app.state.engine,
        app.state.settings,
        email=OLENA,
        institutions={places["kyiv"]: READ},
        now=earlier,
    )
    rows = html.table_rows(admin_client.get("/admin/teachers").text)
    assert earlier.strftime("%Y-%m-%d") in [value for row in rows for value in row.values()]
