"""The page frame: the top bar and its user menu (specs/010-design-system-ui-guidelines FR-018,
FR-019, US2-2, US2-3, US6; contracts/components.md §1).

The user menu is a native `<details>`, so it opens without JavaScript. It holds, in order, the
email linking to the profile, the role switch (only for a person with several roles who has
chosen one), the theme switch, and the logout form. Every test runs once per database engine.
"""

from fastapi.testclient import TestClient

from app.models import Role
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
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
