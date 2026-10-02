"""Each role opens exactly its own pages, judged by the current role.

The access table below is a literal copy of the spec's (user story 1), kept independent of
`app.routers.areas.AREAS` on purpose: a wrong declaration in the application must fail here, not
be mirrored by it. See specs/005-roles-authorization/contracts/http-routes.md. Every test runs
once per database engine.
"""

import logging
import re
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Role
from app.services.email import EmailMessage
from app.services.subjects import create_subject, list_subjects
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
)
from tests.integration.test_login_flow import sign_in

ADMIN, TEACHER, STUDENT = Role.ADMIN, Role.TEACHER, Role.STUDENT

ACCESS_TABLE: dict[str, set[Role]] = {
    "/": {ADMIN, TEACHER, STUDENT},
    "/admin/teachers": {ADMIN},
    "/teacher": {TEACHER},
    "/student": {STUDENT},
    "/staff": {ADMIN, TEACHER},
}

TITLES = {
    "/admin/teachers": "Teachers",
    "/teacher": "Teacher area",
    "/student": "Student area",
    "/staff": "Staff area",
}

PLACEHOLDER = "The features of this area will arrive in a later milestone."
"""The milestone 5 areas' sentence. The administrator area's tabs have their own (milestone 6)."""

PLACEHOLDER_AREAS = {"/teacher", "/student", "/staff"}

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
        if path in PLACEHOLDER_AREAS:
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
    assert response.headers["location"] == f"/login?next={quote(path, safe='')}"


def test_admin_redirects_to_the_teachers_tab(client_as: ClientAs) -> None:
    """Milestone 6 FR-005: `/admin` opens the first tab; other roles are still denied."""
    response = client_as(ADMIN_EMAIL).get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/teachers"
    for email in (TEACHER_EMAIL, STUDENT_EMAIL):
        assert client_as(email).get("/admin", follow_redirects=False).status_code == 403


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


# ---------------------------------------------------------------------------------------------
# Milestone 6: only administrators reach the administrator area (user story 4)
# ---------------------------------------------------------------------------------------------
#
# See specs/006-admin-area/spec.md user story 4 and contracts/http-routes.md "Access". Every page
# and every action of the area, for every role, with the subject rows compared before and after
# each refusal.

ADMIN_PAGES = [
    "/admin",
    "/admin/teachers",
    "/admin/institutions",
    "/admin/subjects",
    "/admin/subjects/new",
    "/admin/subjects/{id}/rename",
    "/admin/subjects/{id}/delete",
]

ADMIN_ACTIONS = [
    ("/admin/subjects", {"name": "Hacked"}),
    ("/admin/subjects/{id}/rename", {"name": "Hacked"}),
    ("/admin/subjects/{id}/deactivate", {}),
    ("/admin/subjects/{id}/activate", {}),
    ("/admin/subjects/{id}/delete", {}),
]

OTHER_ROLES = [TEACHER, STUDENT]


@pytest.fixture
def subject_id(session: Session) -> int:
    """One active subject, for the pages and actions that need an id."""
    subject = create_subject(session, "Physics")
    assert subject.id is not None
    return subject.id


def subject_rows(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    return [(s.id, s.name, s.name_key, s.is_active, s.updated_at) for s in list_subjects(session)]


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_other_roles_are_denied_every_admin_page(
    client_as: ClientAs, subject_id: int, role: Role
) -> None:
    """US4-1, FR-037."""
    browser = client_as(SINGLE_ROLE[role])
    for template in ADMIN_PAGES:
        path = template.format(id=subject_id)
        response = browser.get(path, follow_redirects=False)
        assert response.status_code == 403, path
        assert f"Your current role, {role.label}, cannot open this page." in response.text


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_other_roles_are_denied_every_admin_action(
    client_as: ClientAs, session: Session, subject_id: int, role: Role
) -> None:
    """US4-2: refused, and nothing changes."""
    browser = client_as(SINGLE_ROLE[role])
    before = subject_rows(session)
    for template, data in ADMIN_ACTIONS:
        path = template.format(id=subject_id)
        response = browser.post(path, data=data, follow_redirects=False)
        assert response.status_code == 403, path
        assert subject_rows(session) == before, path


def test_an_administrator_using_another_role_is_denied_until_they_switch(
    client_as: ClientAs,
) -> None:
    """US4-3, FR-036: access follows the current role, not the roles held."""
    browser = client_as(ADMIN_STUDENT_EMAIL, STUDENT)
    assert browser.get("/admin/subjects").status_code == 403
    assert browser.post("/role", data={"role": "admin"}, follow_redirects=False).status_code == 303
    assert browser.get("/admin/subjects").status_code == 200


def test_anonymous_visitors_are_sent_to_sign_in_from_every_admin_page(
    client: TestClient, subject_id: int
) -> None:
    """US4-4, FR-038."""
    for template in ADMIN_PAGES:
        path = template.format(id=subject_id)
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == f"/login?next={quote(path, safe='')}"


def test_anonymous_actions_change_nothing(
    client: TestClient, session: Session, subject_id: int
) -> None:
    before = subject_rows(session)
    for template, data in ADMIN_ACTIONS:
        path = template.format(id=subject_id)
        response = client.post(path, data=data, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/login"
        assert subject_rows(session) == before, path


def test_signing_in_returns_to_the_subjects_tab(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US4-4: through the real code flow, the browser lands where it was going."""
    response = sign_in(client, outbox, next_path="/admin/subjects")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/subjects"
    assert client.get("/admin/subjects").status_code == 200


ADMIN_TAB_LINKS = ["admin-tabs", 'href="/admin/teachers"', 'href="/admin/institutions"']


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_no_admin_tabs_for_other_roles(client_as: ClientAs, role: Role) -> None:
    """US4-5, FR-006: not on any page they may open, nor on the refusal."""
    browser = client_as(SINGLE_ROLE[role])
    pages = [path for path, roles in ACCESS_TABLE.items() if role in roles]
    for path in pages:
        response = browser.get(path)
        assert response.status_code == 200, path
        for marker in [*ADMIN_TAB_LINKS, 'href="/admin/subjects"']:
            assert marker not in response.text, (path, marker)
    denied = browser.get("/admin/subjects")
    assert denied.status_code == 403
    for marker in ADMIN_TAB_LINKS:
        assert marker not in denied.text, marker
    assert '<a href="/admin/subjects"' not in denied.text
