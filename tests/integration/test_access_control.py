"""Each role opens exactly its own pages, judged by the current role.

The access table below is a literal copy of the spec's (user story 1), kept independent of
`app.routers.areas.AREAS` on purpose: a wrong declaration in the application must fail here, not
be mirrored by it. See specs/005-roles-authorization/contracts/http-routes.md. Every test runs
once per database engine.
"""

import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.models import Role
from tests.conftest import ADMIN_EMAIL, STUDENT_EMAIL, TEACHER_EMAIL, ClientAs

ADMIN, TEACHER, STUDENT = Role.ADMIN, Role.TEACHER, Role.STUDENT

ACCESS_TABLE: dict[str, set[Role]] = {
    "/": {ADMIN, TEACHER, STUDENT},
    "/admin": {ADMIN},
    "/teacher": {TEACHER},
    "/student": {STUDENT},
    "/staff": {ADMIN, TEACHER},
}

TITLES = {
    "/admin": "Administrator area",
    "/teacher": "Teacher area",
    "/student": "Student area",
    "/staff": "Staff area",
}

PLACEHOLDER = "The features of this area will arrive in a later milestone."

SINGLE_ROLE = {ADMIN: ADMIN_EMAIL, TEACHER: TEACHER_EMAIL, STUDENT: STUDENT_EMAIL}

HOME_LINKS = {
    ADMIN: [("/admin", "Administrator area"), ("/staff", "Staff area")],
    TEACHER: [("/teacher", "Teacher area"), ("/staff", "Staff area")],
    STUDENT: [("/student", "Student area")],
}

CASES = [(role, path) for role in SINGLE_ROLE for path in ACCESS_TABLE]


def header(body: str) -> str:
    match = re.search(r"<header.*?</header>", body, re.DOTALL)
    assert match is not None, "the page has no <header>"
    return match.group(0)


@pytest.mark.parametrize(("role", "path"), CASES, ids=[f"{r.value}-{p}" for r, p in CASES])
def test_the_access_table(client_as: ClientAs, role: Role, path: str) -> None:
    """SC-001, US1-2, US1-3: 3 roles × 5 pages."""
    response = client_as(SINGLE_ROLE[role]).get(path, follow_redirects=False)
    if role in ACCESS_TABLE[path]:
        assert response.status_code == 200
        if path in TITLES:
            assert f"<h1>{TITLES[path]}</h1>" in response.text
            assert PLACEHOLDER in response.text
    else:
        assert response.status_code == 403
        assert f"Your current role, {role.label}, cannot open this page." in response.text


@pytest.mark.parametrize("role", list(SINGLE_ROLE))
def test_the_access_denied_page(client_as: ClientAs, role: Role) -> None:
    """FR-025: it names the current role, links home, keeps the header, and reveals nothing of
    the page it refused."""
    denied = next(path for path in TITLES if role not in ACCESS_TABLE[path])
    response = client_as(SINGLE_ROLE[role]).get(denied)
    body = response.text
    assert response.status_code == 403
    assert "<h1>Access denied</h1>" in body
    assert re.search(r"<title>Access denied — ", body)
    assert f"Your current role, {role.label}, cannot open this page." in body
    assert '<a href="/">Back to the home page</a>' in body
    top = header(body)
    assert SINGLE_ROLE[role] in top
    assert 'action="/logout"' in top
    assert TITLES[denied] not in body
    assert PLACEHOLDER not in body


@pytest.mark.parametrize("role", list(SINGLE_ROLE))
def test_the_home_page_lists_exactly_the_allowed_areas(client_as: ClientAs, role: Role) -> None:
    """FR-027, US1-4."""
    body = client_as(SINGLE_ROLE[role]).get("/").text
    section = re.search(r'<section id="areas".*?</section>', body, re.DOTALL)
    assert section is not None, "the home page has no areas section"
    assert '<h2 id="areas-heading">Your areas</h2>' in section.group(0)
    links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', section.group(0))
    assert links == HOME_LINKS[role]


@pytest.mark.parametrize("path", list(TITLES))
def test_anonymous_visitors_are_sent_to_sign_in(client: TestClient, path: str) -> None:
    """US1-6, FR-023: authentication first, so never "access denied"."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next=%2F{path[1:]}"


def test_an_unknown_page_is_not_found_not_denied(client_as: ClientAs) -> None:
    """Spec edge case."""
    response = client_as(STUDENT_EMAIL).get("/does-not-exist")
    assert response.status_code == 404


def test_a_denial_is_logged_without_identity(
    client_as: ClientAs, caplog: pytest.LogCaptureFixture
) -> None:
    """SC-008: the role and the route template, never the address or the user id."""
    student = client_as(STUDENT_EMAIL)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert student.get("/admin").status_code == 403
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Access denied")]
    assert lines == ["Access denied: role=student route=/admin"]
    for record in caplog.records:
        assert "@" not in record.getMessage()
