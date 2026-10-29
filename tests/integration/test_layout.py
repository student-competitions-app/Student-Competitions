"""The page frame: the top bar and its user menu (specs/010-design-system-ui-guidelines FR-018,
FR-019, US2-2, US2-3, US6; contracts/components.md §1), and from milestone 10.1 the one frame
block and the loading script on every page (specs/010.1-loading-feedback-pinned-frame FR-001,
FR-012, FR-019, FR-020; contracts/components.md §1).

The user menu is a native `<details>`, so it opens without JavaScript. It holds, in order, the
email linking to the profile, the role switch (only for a person with several roles who has
chosen one), the theme switch, and the logout form. Every test runs once per database engine.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import APP_VERSION
from app.models import Role
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    TEACHER_EMAIL,
    TEACHER_STUDENT_EMAIL,
    ClientAs,
)


def user_menus(body: str) -> list[html.Element]:
    (header,) = html.parse(body).find_all("header")
    return [d for d in header.find_all("details") if "user-menu" in d.classes()]


def menu_parts(body: str) -> list[tuple[str, str]]:
    """The menu's links and forms in document order, as `("link", href)` / `("form", action)`."""
    (menu,) = user_menus(body)
    parts = []
    for element in menu.iter():
        if element.tag == "a" and "href" in element.attrs:
            parts.append(("link", element.attrs["href"]))
        elif element.tag == "form":
            parts.append(("form", element.attrs.get("action", "")))
    return parts


def test_the_user_menu_is_a_details_element_with_a_summary(admin_client: TestClient) -> None:
    menus = user_menus(admin_client.get("/").text)
    assert len(menus) == 1
    summaries = menus[0].find_all("summary")
    assert len(summaries) == 1
    assert ADMIN_EMAIL in summaries[0].text()
    assert "Account menu" in summaries[0].text()


def test_a_single_role_menu_holds_the_profile_link_and_log_out(admin_client: TestClient) -> None:
    body = admin_client.get("/").text
    assert menu_parts(body) == [("link", "/profile"), ("form", "/theme"), ("form", "/logout")]
    assert ("/profile", ADMIN_EMAIL) in html.link_pairs(body, "details")
    logout = [f for f in html.forms(body, "details") if f.action == "/logout"]
    assert [(f.method, [b.text for b in f.buttons]) for f in logout] == [("post", ["Log out"])]


def test_several_roles_add_the_role_switch_between_them(client_as: ClientAs) -> None:
    """US2-3: one button per other role, posted to the existing `POST /role`."""
    body = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN).get("/").text
    assert menu_parts(body) == [
        ("link", "/profile"),
        ("form", "/role"),
        ("form", "/theme"),
        ("form", "/logout"),
    ]
    (switch,) = [f for f in html.forms(body, "details") if f.action == "/role"]
    assert switch.method == "post"
    assert "Switch to" in switch.text
    assert [(b.name, b.value, b.text) for b in switch.buttons] == [("role", "student", "Student")]


def test_no_role_switch_before_a_role_is_chosen(client_as: ClientAs) -> None:
    """The role-choice page itself offers the choice; the menu does not repeat it."""
    body = client_as(TEACHER_STUDENT_EMAIL).get("/role").text
    assert menu_parts(body) == [("link", "/profile"), ("form", "/theme"), ("form", "/logout")]


def test_signed_out_there_is_no_user_menu(client: TestClient) -> None:
    body = client.get("/login").text
    assert user_menus(body) == []
    assert html.forms(body, "header") == []


# ---------------------------------------------------------------------------------------------
# User story 6: the identity on every kind of page (FR-008, FR-018, FR-021, FR-036)
# ---------------------------------------------------------------------------------------------

FAVICONS = [
    "/static/img/favicon.svg",
    "/static/img/favicon-32.png",
    "/static/img/apple-touch-icon.png",
]


def brand(body: str) -> html.Element:
    """The header's link home, which holds the logo mark and the name."""
    (header,) = html.parse(body).find_all("header")
    homes = [a for a in header.find_all("a") if a.attrs.get("href") == "/"]
    assert len(homes) == 1, "the header has no single link home"
    return homes[0]


def assert_identity(body: str) -> None:
    home = brand(body)
    assert "Student Competitions" in home.text()
    marks = [svg for svg in home.find_all("svg") if "logo-mark" in svg.classes()]
    assert len(marks) == 1 and marks[0].attrs.get("aria-hidden") == "true"
    icons = [link.attrs.get("href") for link in html.parse(body).find_all("link")]
    assert all(icon in icons for icon in FAVICONS)
    assert f"v{APP_VERSION}" in html.text(body, "footer")


def test_the_identity_on_the_sign_in_page(client: TestClient) -> None:
    body = client.get("/login").text
    assert_identity(body)
    assert html.role_label(body) == ""


def test_the_identity_on_signed_in_pages(admin_client: TestClient) -> None:
    for path in ("/", "/admin/subjects", "/profile"):
        body = admin_client.get(path).text
        assert_identity(body)
        assert html.role_label(body).startswith("Administrator"), path


@pytest.mark.parametrize("path", ["/no-such-page", "/admin/subjects/abc"])
def test_the_identity_on_the_not_found_page(admin_client: TestClient, path: str) -> None:
    response = admin_client.get(path)
    assert response.status_code == 404
    assert_identity(response.text)


def test_the_identity_on_the_refusal_pages(client_as: ClientAs, admin_client: TestClient) -> None:
    denied = client_as(TEACHER_EMAIL).get("/admin/subjects")
    assert denied.status_code == 403
    assert_identity(denied.text)
    refused = admin_client.post("/logout", headers={"Origin": "https://evil.example"})
    assert refused.status_code == 403
    assert_identity(refused.text)


def test_the_database_line_is_in_the_footer_of_the_home_page_only(
    admin_client: TestClient,
) -> None:
    def database_lines(body: str) -> list[html.Element]:
        return [e for e in html.parse(body).iter() if "data-engine" in e.attrs]

    (line,) = database_lines(admin_client.get("/").text)
    assert line.parent is not None and line.parent.tag == "footer"
    for path in ("/admin/subjects", "/profile"):
        assert database_lines(admin_client.get(path).text) == [], path


SCRIPT_SRC = "/static/js/loading-feedback.js"

PAGE_KINDS = [
    (None, "/login"),
    (None, "/no-such-page"),
    (None, "/data-deletion"),
    (ADMIN_EMAIL, "/"),
    (ADMIN_EMAIL, "/admin/subjects"),
    (ADMIN_EMAIL, "/profile"),
    (TEACHER_EMAIL, "/teacher/students"),
    (TEACHER_EMAIL, "/teacher/teams"),
]
"""Every kind of page: public, "not found", signed in, the administrator and the teacher areas."""

AREA_PAGES = {"/admin/subjects", "/teacher/students", "/teacher/teams"}


def page(client: TestClient, client_as: ClientAs, email: str | None, path: str) -> str:
    browser = client if email is None else client_as(email)
    return browser.get(path).text


@pytest.mark.parametrize(("email", "path"), PAGE_KINDS)
def test_every_page_loads_the_script_once(
    client: TestClient, client_as: ClientAs, email: str | None, path: str
) -> None:
    """FR-020: one deferred script from the base layout, in the head."""
    (head,) = html.parse(page(client, client_as, email, path)).find_all("head")
    scripts = [e.attrs for e in head.find_all("script") if e.attrs.get("src") == SCRIPT_SRC]
    assert scripts == [{"src": SCRIPT_SRC, "defer": ""}]


def test_the_script_is_served(client: TestClient) -> None:
    response = client.get(SCRIPT_SRC)
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


@pytest.mark.parametrize(("email", "path"), PAGE_KINDS)
def test_every_page_has_one_frame_with_a_hidden_bar(
    client: TestClient, client_as: ClientAs, email: str | None, path: str
) -> None:
    """FR-012, FR-019: the top bar, the area tabs on area pages and the loading bar, in one block
    that is a direct child of `<body>`; the bar is hidden until the script shows it."""
    (body,) = html.parse(page(client, client_as, email, path)).find_all("body")
    frames = [e for e in body.find_all("div") if "frame" in e.classes()]
    assert len(frames) == 1
    (frame,) = frames
    assert frame.parent is body
    children = [c for c in frame.children if isinstance(c, html.Element)]
    expected = [("header", "top-bar")]
    if path in AREA_PAGES:
        expected.append(("nav", "area-tabs"))
    expected.append(("div", "loading-bar"))
    assert [(c.tag, c.classes()[0]) for c in children] == expected
    bar = children[-1]
    assert "hidden" in bar.attrs
    assert bar.attrs.get("aria-hidden") == "true"
