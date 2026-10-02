"""The administrator area's shell: the `/admin` redirect, the tab row, and the placeholders.

See specs/006-admin-area/spec.md user story 3 and contracts/http-routes.md "Area shell" and "Admin
layout". The expected tabs are a literal copy of the spec's, kept independent of
`app.routers.admin.ADMIN_TABS`, so a wrong declaration fails here rather than being mirrored.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.subjects import create_subject

TABS = [
    ("/admin/teachers", "Teachers"),
    ("/admin/institutions", "Educational institutions"),
    ("/admin/subjects", "Subjects"),
]

PLACEHOLDERS = {
    "/admin/teachers": ("Teachers", "Teacher management will arrive in a later milestone."),
    "/admin/institutions": (
        "Educational institutions",
        "Managing educational institutions will arrive in a later milestone.",
    ),
}

NAV_OPEN = '<nav class="admin-tabs" aria-label="Administrator area">'


def tab_row(body: str) -> str:
    match = re.search(r'<nav class="admin-tabs".*?</nav>', body, re.DOTALL)
    assert match is not None, "the page has no admin tab row"
    return match.group(0)


def after_tab_row(body: str) -> str:
    """The page content: everything between the tab row and the end of `<main>`."""
    start = body.index("</nav>") + len("</nav>")
    return body[start : body.index("</main>")]


def current_tabs(body: str) -> list[str]:
    return re.findall(r'<a href="([^"]+)" aria-current="page">', tab_row(body))


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
    assert NAV_OPEN in body
    row = tab_row(body)
    links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', row)
    assert links == TABS
    assert body.count('aria-current="page"') == 1
    assert current_tabs(body) == [path]


@pytest.mark.parametrize("path", [path for path, _ in TABS])
def test_tabs_are_plain_links(admin_client: TestClient, path: str) -> None:
    """FR-003: no script, no HTMX; each tab has its own address."""
    body = admin_client.get(path).text
    row = tab_row(body)
    assert "<form" not in row
    assert "hx-" not in row
    assert "<script" not in body


@pytest.mark.parametrize("path", list(PLACEHOLDERS))
def test_the_placeholder_tabs_offer_no_actions(admin_client: TestClient, path: str) -> None:
    """US3-4, FR-007."""
    heading, note = PLACEHOLDERS[path]
    body = admin_client.get(path).text
    assert f"<h1>{heading}</h1>" in body
    assert note in body
    content = after_tab_row(body)
    assert "<form" not in content
    assert "<button" not in content


@pytest.mark.parametrize("path", [path for path, _ in TABS])
def test_a_tab_can_be_reloaded_and_bookmarked(admin_client: TestClient, path: str) -> None:
    assert admin_client.get(path).text == admin_client.get(path).text


@pytest.mark.parametrize("path", ["/", "/staff", "/role"])
def test_no_tab_row_outside_the_area(admin_client: TestClient, path: str) -> None:
    """FR-006."""
    response = admin_client.get(path)
    assert response.status_code == 200
    assert "admin-tabs" not in response.text


def test_an_unknown_admin_page_is_the_normal_not_found(admin_client: TestClient) -> None:
    response = admin_client.get("/admin/unknown")
    assert response.status_code == 404
    assert "admin-tabs" not in response.text


def test_the_home_page_still_links_to_admin(admin_client: TestClient) -> None:
    """FR-008."""
    assert '<a href="/admin">Administrator area</a>' in admin_client.get("/").text


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
        assert NAV_OPEN in body, path
        assert current_tabs(body) == ["/admin/subjects"], path
        assert body.count('aria-current="page"') == 1, path
