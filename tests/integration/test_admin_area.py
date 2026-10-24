"""The administrator area's shell: the `/admin` redirect and the tab row.

Since milestone 8 no tab is a placeholder: the last one, Teachers, is replaced by teacher
management (specs/008-teacher-management-consent SC-010).

See specs/006-admin-area/spec.md user story 3 and contracts/http-routes.md "Area shell" and "Admin
layout". The expected tabs are a literal copy of the spec's, kept independent of
`app.routers.admin.ADMIN_TABS`, so a wrong declaration fails here rather than being mirrored.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models import AccessLevel
from app.services.institutions import create_institution
from app.services.regions import create_region, set_region_active
from app.services.subjects import create_subject
from tests import html
from tests.conftest import invite_and_accept

TABS = [
    ("/admin/teachers", "Teachers"),
    ("/admin/institutions", "Educational institutions"),
    ("/admin/subjects", "Subjects"),
]

NAV_LABEL = "Administrator area"


def tab_row(body: str) -> list[html.Link]:
    tabs = html.nav(body, NAV_LABEL)
    assert tabs, "the page has no admin tab row"
    return tabs


def has_tab_row(body: str) -> bool:
    return bool(html.nav(body, NAV_LABEL))


def current_tabs(body: str) -> list[str]:
    return [tab.href for tab in tab_row(body) if tab.attrs.get("aria-current") == "page"]


def current_page_marks(body: str) -> int:
    """How many links on the whole page claim to be the current page."""
    return sum(1 for link in html.links(body) if link.attrs.get("aria-current") == "page")


def tab_navs(body: str) -> list[html.Element]:
    return [n for n in html.parse(body).find_all("nav") if n.attrs.get("aria-label") == NAV_LABEL]


def test_admin_opens_the_teachers_tab(admin_client: TestClient) -> None:
    """US3-1, FR-005."""
    response = admin_client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/teachers"
    followed = admin_client.get("/admin")
    assert followed.url.path == "/admin/teachers"
    assert current_tabs(followed.text) == ["/admin/teachers"]


@pytest.mark.parametrize("path", [path for path, _ in TABS])
def test_every_tab_shows_the_row_with_itself_current(admin_client: TestClient, path: str) -> None:
    """US3-2, FR-002, FR-004, SC-004."""
    response = admin_client.get(path)
    assert response.status_code == 200
    body = response.text
    assert [(tab.href, tab.text) for tab in tab_row(body)] == TABS
    assert current_page_marks(body) == 1
    assert current_tabs(body) == [path]


@pytest.mark.parametrize("path", [path for path, _ in TABS])
def test_tabs_are_plain_links(admin_client: TestClient, path: str) -> None:
    """FR-003: no HTMX; each tab has its own address. The page's only script is the base
    layout's loading feedback (specs/010.1-loading-feedback-pinned-frame FR-020, FR-023); the
    tabs are plain links and work without it (FR-021)."""
    body = admin_client.get(path).text
    (row,) = tab_navs(body)
    assert row.find_all("form") == []
    assert not any(name.startswith("hx-") for e in row.iter() for name in e.attrs)
    scripts = [e.attrs for e in html.parse(body).find_all("script")]
    assert scripts == [{"src": "/static/js/loading-feedback.js", "defer": ""}]


@pytest.mark.parametrize("path", [path for path, _ in TABS])
def test_a_tab_can_be_reloaded_and_bookmarked(admin_client: TestClient, path: str) -> None:
    assert admin_client.get(path).text == admin_client.get(path).text


@pytest.mark.parametrize("path", ["/", "/staff", "/role"])
def test_no_tab_row_outside_the_area(admin_client: TestClient, path: str) -> None:
    """FR-006."""
    response = admin_client.get(path)
    assert response.status_code == 200
    assert not has_tab_row(response.text)


def test_an_unknown_admin_page_is_the_normal_not_found(admin_client: TestClient) -> None:
    response = admin_client.get("/admin/unknown")
    assert response.status_code == 404
    assert not has_tab_row(response.text)


def test_the_home_page_still_links_to_admin(admin_client: TestClient) -> None:
    """FR-008."""
    assert ("/admin", "Administrator area") in html.link_pairs(admin_client.get("/").text, "main")


def test_every_subject_page_marks_the_subjects_tab(
    admin_client: TestClient, session: Session
) -> None:
    """US3-5, FR-004: pages deeper than the tab itself keep it current."""
    sid = create_subject(session, "Physics").id
    for path in [
        "/admin/subjects/new",
        f"/admin/subjects/{sid}/rename",
        f"/admin/subjects/{sid}/delete",
        "/admin/subjects/999/rename",
    ]:
        body = admin_client.get(path).text
        assert has_tab_row(body), path
        assert current_tabs(body) == ["/admin/subjects"], path
        assert current_page_marks(body) == 1, path


# ---------------------------------------------------------------------------------------------
# Milestone 7: the Educational institutions tab
# ---------------------------------------------------------------------------------------------

INSTITUTION_PAGES = [
    ("GET", "/admin/institutions"),
    ("GET", "/admin/institutions/regions/new"),
    ("GET", "/admin/institutions/regions/{region}"),
    ("GET", "/admin/institutions/regions/{region}/rename"),
    ("GET", "/admin/institutions/regions/{region}/delete"),
    ("POST", "/admin/institutions/regions/{region}/delete"),  # refused: it holds an institution
    ("GET", "/admin/institutions/regions/{region}/institutions/new"),
    ("GET", "/admin/institutions/regions/{inactive}/institutions/new"),  # refused: deactivated
    ("GET", "/admin/institutions/regions/{region}/institutions/{institution}/rename"),
    ("GET", "/admin/institutions/regions/{region}/institutions/{institution}/delete"),
    ("GET", "/admin/institutions/regions/999"),  # region not found
    ("GET", "/admin/institutions/regions/{inactive}/institutions/{institution}/rename"),  # wrong
]
"""Every page of the tab, including its refusals and both not-found pages (`{inactive}` is a
deactivated region that does not hold `{institution}`)."""


def test_the_institutions_tab_is_no_longer_a_placeholder(admin_client: TestClient) -> None:
    """Milestone 7 FR-001."""
    response = admin_client.get("/admin/institutions")
    assert response.status_code == 200
    body = response.text
    assert "Managing educational institutions will arrive in a later milestone." not in body
    assert "No regions yet" in body
    assert "Select a region" in body


def test_every_institutions_page_marks_the_institutions_tab(
    admin_client: TestClient, session: Session
) -> None:
    """Milestone 7 FR-005: every page of the tab, refusals and not-found pages included."""
    region = create_region(session, "Kyiv")
    institution = create_institution(session, region.id, "Academy")
    inactive = create_region(session, "Odesa")
    set_region_active(session, inactive.id, False)
    ids = {"region": region.id, "institution": institution.id, "inactive": inactive.id}
    for method, template in INSTITUTION_PAGES:
        path = template.format(**ids)
        response = admin_client.request(method, path, follow_redirects=False)
        assert response.status_code in {200, 404, 409}, (method, path, response.status_code)
        body = response.text
        assert has_tab_row(body), path
        assert current_tabs(body) == ["/admin/institutions"], path
        assert current_page_marks(body) == 1, path


def test_the_teachers_tab_is_no_longer_a_placeholder(admin_client: TestClient) -> None:
    """Milestone 8 SC-010: the cast's directly seeded teachers have no teacher profile, so the
    list is empty."""
    response = admin_client.get("/admin/teachers")
    assert response.status_code == 200
    body = response.text
    main = html.text(body, "main")
    assert "Teacher management will arrive in a later milestone." not in main
    assert html.h1(body) == "Teachers"
    assert "No teachers yet" in main
    invite = [link for link in html.links(body, "main") if link.href == "/admin/teachers/invite"]
    assert [(link.text, link.attrs.get("role")) for link in invite] == [
        ("Invite teacher", "button")
    ]


TEACHER_PAGES = ["/admin/teachers", "/admin/teachers/invite", "/admin/teachers/999999"]
"""Every page of the tab that needs no teacher, including the not-found page."""


@pytest.mark.parametrize("path", TEACHER_PAGES)
def test_every_teachers_page_marks_the_teachers_tab(admin_client: TestClient, path: str) -> None:
    """Milestone 8: every page of the tab is inside the area, with Teachers current."""
    response = admin_client.get(path)
    assert response.status_code in {200, 404}
    assert has_tab_row(response.text)
    assert current_tabs(response.text) == ["/admin/teachers"]
    assert current_page_marks(response.text) == 1


def test_every_page_of_a_teacher_marks_the_teachers_tab(
    admin_client: TestClient, session: Session
) -> None:
    """Milestone 8: the teacher page, the remove confirmation and their not-found pages."""
    region = create_region(session, "Kyiv")
    institution = create_institution(session, region.id, "Academy")
    user_id = invite_and_accept(
        app.state.engine,
        app.state.settings,
        email="olena@example.org",
        institutions={institution.id: AccessLevel.READ},
    )
    for path in (
        f"/admin/teachers/{user_id}",
        f"/admin/teachers/{user_id}/remove",
        "/admin/teachers/999999/remove",
    ):
        response = admin_client.get(path)
        assert response.status_code in {200, 404}, path
        assert current_tabs(response.text) == ["/admin/teachers"], path
        assert current_page_marks(response.text) == 1, path
