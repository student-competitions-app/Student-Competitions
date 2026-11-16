"""The page frame: the top bar and its user menu (specs/010-design-system-ui-guidelines FR-018,
FR-019, US2-2, US2-3, US6; contracts/components.md §1), and from milestone 10.1 the one frame
block and the loading script on every page (specs/010.1-loading-feedback-pinned-frame FR-001,
FR-012, FR-019, FR-020; contracts/components.md §1), and from milestone 12.1 the time-zone script
after it (specs/012.1-teacher-competitions contracts/components.md §7).

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
    STUDENT_EMAIL,
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
    menus = user_menus(admin_client.get("/admin/teachers").text)
    assert len(menus) == 1
    summaries = menus[0].find_all("summary")
    assert len(summaries) == 1
    assert ADMIN_EMAIL in summaries[0].text()
    assert "Account menu" in summaries[0].text()


def test_a_single_role_menu_holds_the_profile_link_and_log_out(admin_client: TestClient) -> None:
    body = admin_client.get("/admin/teachers").text
    assert menu_parts(body) == [("link", "/profile"), ("form", "/theme"), ("form", "/logout")]
    assert ("/profile", ADMIN_EMAIL) in html.link_pairs(body, "details")
    logout = [f for f in html.forms(body, "details") if f.action == "/logout"]
    assert [(f.method, [b.text for b in f.buttons]) for f in logout] == [("post", ["Log out"])]


def test_several_roles_add_the_role_switch_between_them(client_as: ClientAs) -> None:
    """US2-3: one button per other role, posted to the existing `POST /role`."""
    body = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN).get("/admin/teachers").text
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
    assert [f.action for f in html.forms(body, "header")] == ["/language"]


# ---------------------------------------------------------------------------------------------
# User story 6: the identity on every kind of page (FR-008, FR-018, FR-021, FR-036)
# ---------------------------------------------------------------------------------------------

ICON_LINKS = [
    {"rel": "icon", "href": "/static/img/logo/favicon.ico", "sizes": "16x16 32x32 48x48"},
    {
        "rel": "icon",
        "href": "/static/img/logo/favicon-16.png",
        "sizes": "16x16",
        "type": "image/png",
    },
    {
        "rel": "icon",
        "href": "/static/img/logo/favicon-32.png",
        "sizes": "32x32",
        "type": "image/png",
    },
    {
        "rel": "icon",
        "href": "/static/img/logo/favicon-48.png",
        "sizes": "48x48",
        "type": "image/png",
    },
    {"rel": "apple-touch-icon", "href": "/static/img/logo/apple-touch-icon.png"},
    {"rel": "manifest", "href": "/static/img/logo/site.webmanifest"},
]
"""Milestone 12.7 FR-015, contracts/static-assets.md §2: the favicons, the touch icon and the
manifest, on every page."""


def brand(body: str) -> html.Element:
    """The header's link home, which holds the logo mark and the name."""
    (header,) = html.parse(body).find_all("header")
    homes = [a for a in header.find_all("a") if a.attrs.get("href") == "/"]
    assert len(homes) == 1, "the header has no single link home"
    return homes[0]


def srcset_urls(srcset: str) -> list[str]:
    """The URL of each candidate in a `srcset`, without its descriptor."""
    return [candidate.split()[0] for candidate in srcset.split(",") if candidate.strip()]


def assert_top_bar_mark(home: html.Element) -> None:
    """Milestone 12.7 FR-001, FR-005, contracts/components.md: the brand link holds one logo mark,
    the emblem image in light ink, decorative, sized for the slot it has at each width."""
    marks = [element for element in home.iter() if "logo-mark" in element.classes()]
    assert len(marks) == 1, "the brand link has no single logo mark"
    (mark,) = marks
    assert mark.tag == "img"
    assert "logo-mark-top-bar" in mark.classes()
    assert mark.attrs.get("alt") == "" and "alt" in mark.attrs
    assert mark.attrs.get("aria-hidden") == "true"
    assert (mark.attrs.get("width"), mark.attrs.get("height")) == ("32", "32")
    assert mark.attrs.get("sizes") == "(min-width: 768px) 2rem, 2.75rem"
    urls = [mark.attrs.get("src", ""), *srcset_urls(mark.attrs.get("srcset", ""))]
    assert len(urls) > 1
    assert all(url.startswith("/static/img/logo/logo-light-") for url in urls), urls


def assert_identity(body: str) -> None:
    home = brand(body)
    assert "Student Competitions" in home.text()
    assert_top_bar_mark(home)
    page = html.parse(body)
    assert not [svg for svg in page.find_all("svg") if "logo-mark" in svg.classes()]
    links = [link.attrs for link in page.find_all("link")]
    for expected in ICON_LINKS:
        assert any(expected.items() <= attrs.items() for attrs in links), expected
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


@pytest.mark.parametrize("signed_in", [False, True], ids=["signed-out", "signed-in"])
@pytest.mark.parametrize(
    ("language", "name"), [("uk", "Студентські змагання"), (None, "Student Competitions")]
)
def test_the_brand_link_is_named_in_the_pages_language(
    client: TestClient,
    admin_client: TestClient,
    signed_in: bool,
    language: str | None,
    name: str,
) -> None:
    """Milestone 12.7 FR-001, FR-005: the image adds no text, so the brand link reads as the
    application's name in the page's language, signed out and signed in."""
    browser = admin_client if signed_in else client
    if language:
        browser.cookies.set("sc_lang", language)
    body = browser.get("/" if signed_in else "/login").text
    home = brand(body)
    assert home.text() == name
    assert_top_bar_mark(home)


def test_the_database_line_is_in_the_footer_of_administrator_pages_only(
    admin_client: TestClient,
) -> None:
    """Milestone 12.6 FR-010: the line moved from the home page to the administrator area. The
    student's home page keeps it too (`test_database_line.py`)."""

    def database_lines(body: str) -> list[html.Element]:
        return [e for e in html.parse(body).iter() if "data-engine" in e.attrs]

    for path in ("/admin/teachers", "/admin/subjects"):
        (line,) = database_lines(admin_client.get(path).text)
        assert line.parent is not None and line.parent.tag == "footer", path
    assert database_lines(admin_client.get("/profile").text) == []


SCRIPT_SRC = "/static/js/loading-feedback.js"

PAGE_KINDS = [
    (None, "/login"),
    (None, "/no-such-page"),
    (None, "/data-deletion"),
    (STUDENT_EMAIL, "/"),
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


ZONE_SCRIPT_SRC = "/static/js/time-zone.js"


@pytest.mark.parametrize(("email", "path"), [*PAGE_KINDS, (TEACHER_EMAIL, "/teacher/competitions")])
def test_every_page_loads_the_time_zone_script_once_after_the_loading_script(
    client: TestClient, client_as: ClientAs, email: str | None, path: str
) -> None:
    """Milestone 12.1 FR-020, contracts/components.md §7: one deferred script from the base
    layout, in the head, right after `loading-feedback.js`."""
    (head,) = html.parse(page(client, client_as, email, path)).find_all("head")
    sources = [e.attrs.get("src") for e in head.find_all("script") if e.attrs.get("src")]
    assert sources.count(ZONE_SCRIPT_SRC) == 1
    assert sources.index(ZONE_SCRIPT_SRC) == sources.index(SCRIPT_SRC) + 1
    scripts = [e.attrs for e in head.find_all("script") if e.attrs.get("src") == ZONE_SCRIPT_SRC]
    assert scripts == [{"src": ZONE_SCRIPT_SRC, "defer": ""}]


def test_the_time_zone_script_is_served(client: TestClient) -> None:
    response = client.get(ZONE_SCRIPT_SRC)
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
