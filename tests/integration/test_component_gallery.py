"""The component gallery, `GET /admin/components` (specs/010-design-system-ui-guidelines US7,
FR-037–FR-038a, SC-009; contracts/http-routes.md §2, contracts/components.md §12), with the
loading feedback of milestone 10.1 (specs/010.1-loading-feedback-pinned-frame FR-017,
contracts/components.md §5).

Outside production an administrator sees every component and variant; other roles are refused
as on any administrator page, and anonymous visitors are sent to sign in. In production the
address is unknown to everyone: the same 404 as an address that does not exist. Every test runs
once per database engine.
"""

import dataclasses
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from app.models import Role
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
)

GALLERY = "/admin/components"

SECTIONS = {
    "identity": ["Student Competitions", "--sc-page", "--sc-accent", "Heading 1", "Small text"],
    "frame": ["Account menu", "Switch to", "Light", "Dark", "Device", "Back to the frame"],
    "loading": ["Loading bar", "Busy button", "Send invitation"],
    "buttons": ["Primary button", "Secondary link", "Destructive form", "Destructive outline"],
    "cards": ["Card with a link", "Card without a link", "Card with a body"],
    "table": ["Physics", "Deactivated", "Rename", "Activate", "No subjects yet"],
    "badges": ["Active", "Deactivated", "Read", "Write"],
    "empty-states": ["No subjects yet", "Select a region"],
    "notices": ["Invitation sent to", "no longer valid", "temporarily unavailable"],
    "forms": ["There is a problem", "Enter a name.", "Can create competitions", "Save", "Cancel"],
    "confirmations": ["Delete “Physics”?", "is in use and cannot be deleted", "Deactivate"],
    "details": ["Email", "Olena", "Teacher, Student"],
    "selectors": ["Regions", "Kyiv", "Educational institutions in “Kyiv”", "+ Add class"],
}
"""components.md §12, in order: each section's id and texts of its variants."""


@pytest.fixture
def production(client: TestClient) -> Iterator[None]:
    settings = app.state.settings
    app.state.settings = dataclasses.replace(settings, production=True)
    try:
        yield
    finally:
        app.state.settings = settings


def sections(body: str) -> list[html.Element]:
    (main,) = html.parse(body).find_all("main")
    return [s for s in main.find_all("section") if s.attrs.get("id") in SECTIONS]


def test_an_administrator_sees_every_section_and_variant(admin_client: TestClient) -> None:
    response = admin_client.get(GALLERY)
    assert response.status_code == 200
    found = sections(response.text)
    assert [s.attrs["id"] for s in found] == list(SECTIONS)
    for section in found:
        text = section.text()
        for variant in SECTIONS[section.attrs["id"]]:
            assert variant in text, (section.attrs["id"], variant)


def test_the_loading_section_shows_both_components_in_their_loading_state(
    admin_client: TestClient,
) -> None:
    """The bar shown (not hidden) under a sample frame, and a busy button of each kind: never
    disabled, and outside any form, so pressing one does nothing."""
    (section,) = [s for s in sections(admin_client.get(GALLERY).text) if s.attrs["id"] == "loading"]
    bars = [e for e in section.find_all("div") if "loading-bar" in e.classes()]
    assert len(bars) == 1
    (bar,) = bars
    assert "hidden" not in bar.attrs
    assert bar.attrs.get("aria-hidden") == "true"
    assert bar.parent is not None and "frame" in bar.parent.classes()
    busy = [b for b in section.find_all("button") if b.attrs.get("aria-busy") == "true"]
    assert [b.text() for b in busy] == ["Send invitation", "Dark", "Delete"]
    assert not any("disabled" in b.attrs for b in busy)

    def in_form(element: html.Element) -> bool:
        parent = element.parent
        while parent is not None and parent.tag != "form":
            parent = parent.parent
        return parent is not None

    assert not any(in_form(b) for b in busy)


def test_the_gallery_is_no_tab(admin_client: TestClient) -> None:
    body = admin_client.get(GALLERY).text
    tabs = html.nav(body, "Administrator area")
    assert tabs, "the gallery is inside the administrator area"
    assert GALLERY not in [tab.href for tab in tabs]
    assert [tab for tab in tabs if tab.attrs.get("aria-current")] == []


@pytest.mark.parametrize(
    ("email", "role"),
    [
        (TEACHER_EMAIL, Role.TEACHER),
        (STUDENT_EMAIL, Role.STUDENT),
        (ADMIN_STUDENT_EMAIL, Role.STUDENT),
    ],
)
def test_other_current_roles_are_refused(client_as: ClientAs, email: str, role: Role) -> None:
    response = client_as(email, role).get(GALLERY)
    assert response.status_code == 403
    assert html.h1(response.text) == "Access denied"
    assert f"Your current role, {role.label}, cannot open this page." in response.text


def test_anonymous_visitors_are_sent_to_sign_in(client: TestClient) -> None:
    response = client.get(GALLERY, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fadmin%2Fcomponents"


def test_the_gallery_reads_no_data(admin_client: TestClient) -> None:
    """FR-037: the handler takes no session. Every request still reads the visitor's session and
    roles to authorise it (`resolve_access`), so those are the only statements allowed."""
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        assert admin_client.get(GALLERY).status_code == 200
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    tables = {table for statement in statements for table in re.findall(r"FROM (\w+)", statement)}
    assert tables, "no statement was recorded"
    assert tables <= {"sessions", "users", "user_roles"}, tables


@pytest.mark.usefixtures("production")
@pytest.mark.parametrize("who", ["anonymous", ADMIN_EMAIL, TEACHER_EMAIL, STUDENT_EMAIL])
def test_in_production_it_is_an_unknown_address_for_everyone(
    client: TestClient, client_as: ClientAs, who: str
) -> None:
    browser = client if who == "anonymous" else client_as(who)
    response = browser.get(GALLERY, follow_redirects=False)
    unknown = browser.get("/no-such-page", follow_redirects=False)
    assert response.status_code == unknown.status_code == 404
    assert response.text.replace(GALLERY, "/no-such-page") == unknown.text
