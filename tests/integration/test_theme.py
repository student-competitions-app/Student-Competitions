"""The theme choice over HTTP (specs/010-design-system-ui-guidelines US5, FR-014–FR-017;
contracts/http-routes.md §1, §3).

`POST /theme` sets or deletes the `sc_theme` cookie and returns the browser where it was; every
page renders the choice as `data-theme` on `<html>` from the server, so there is no flash and no
script. The cookie is not tied to the account or the session. Every test that uses `client` runs
once per database engine.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from tests import html
from tests.conftest import ADMIN_STUDENT_EMAIL, ClientAs
from tests.integration.test_login_flow import code_from, request_code, submit_code


def choose(browser: TestClient, theme: str, next_path: str) -> Any:
    return browser.post("/theme", data={"theme": theme, "next": next_path}, follow_redirects=False)


def theme_cookie(response: Any) -> str | None:
    """The `sc_theme` Set-Cookie header of `response`, if any."""
    found = [h for h in response.headers.get_list("set-cookie") if h.startswith("sc_theme=")]
    assert len(found) <= 1
    return found[0] if found else None


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_choosing_light_or_dark_sets_the_cookie_and_returns(client: TestClient, theme: str) -> None:
    response = choose(client, theme, "/login?next=%2Fprofile")
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fprofile"
    cookie = theme_cookie(response)
    assert cookie is not None and cookie.startswith(f"sc_theme={theme};")


@pytest.mark.parametrize("theme", ["device", "purple", ""])
def test_the_device_or_an_unknown_value_deletes_the_cookie(client: TestClient, theme: str) -> None:
    client.cookies.set("sc_theme", "dark")
    response = choose(client, theme, "/login")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    cookie = theme_cookie(response)
    assert cookie is not None and "Max-Age=0" in cookie


def test_a_signed_in_person_returns_to_their_page(admin_client: TestClient) -> None:
    response = choose(admin_client, "dark", "/admin/subjects")
    assert response.headers["location"] == "/admin/subjects"


UNSAFE = [
    "https://evil.example/",
    "//evil.example",
    "/login/code",
    "/logout",
    "/theme",
    "/admin/subjects/7/deactivate",
    "",
]


@pytest.mark.parametrize("next_path", UNSAFE)
def test_an_unsafe_or_post_only_target_falls_back(
    client: TestClient, admin_client: TestClient, next_path: str
) -> None:
    assert choose(client, "dark", next_path).headers["location"] == "/login"
    assert choose(admin_client, "dark", next_path).headers["location"] == "/"


def test_the_switch_never_touches_the_database(client: TestClient) -> None:
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        assert choose(client, "dark", "/login").status_code == 303
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert statements == []


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_kind_of_page_renders_the_choice(
    client: TestClient, admin_client: TestClient, theme: str
) -> None:
    for browser, path in ((client, "/login"), (admin_client, "/"), (admin_client, "/no-such")):
        browser.cookies.set("sc_theme", theme)
        body = browser.get(path).text
        assert html.html_attrs(body).get("data-theme") == theme, path
        assert html.meta(body, "color-scheme") == theme, path


@pytest.mark.parametrize("value", [None, "", "purple"])
def test_no_or_an_unknown_choice_follows_the_device(client: TestClient, value: str | None) -> None:
    if value is not None:
        client.cookies.set("sc_theme", value)
    body = client.get("/login").text
    assert "data-theme" not in html.html_attrs(body)
    assert html.meta(body, "color-scheme") == "light dark"


def switches(body: str, within: str | None = None) -> list[html.Form]:
    return [f for f in html.forms(body, within) if f.action == "/theme"]


def pressed(form: html.Form) -> list[str]:
    return [b.value or "" for b in form.buttons if b.attrs.get("aria-pressed") == "true"]


def test_the_sign_in_page_has_the_switch_returning_to_itself(client: TestClient) -> None:
    client.cookies.set("sc_theme", "dark")
    body = client.get("/login", params={"next": "/profile"}).text
    (switch,) = switches(body, "main")
    assert switch.method == "post"
    assert [(b.name, b.value, b.text) for b in switch.buttons] == [
        ("theme", "light", "Light"),
        ("theme", "dark", "Dark"),
        ("theme", "device", "Device"),
    ]
    assert html.Input("next", "hidden", "/login?next=%2Fprofile") in switch.inputs
    assert pressed(switch) == ["dark"]
    assert "Theme" in switch.text


def test_the_user_menu_has_the_switch_between_the_role_switch_and_log_out(
    client_as: ClientAs,
) -> None:
    browser = client_as(ADMIN_STUDENT_EMAIL)
    browser.post("/role", data={"role": "admin"})
    body = browser.get("/admin/subjects?x=1").text
    actions = [f.action for f in html.forms(body, "details")]
    assert actions == ["/role", "/theme", "/logout"]
    (switch,) = switches(body, "details")
    assert html.Input("next", "hidden", "/admin/subjects?x=1") in switch.inputs
    assert pressed(switch) == ["device"]


@pytest.mark.parametrize(
    "path",
    ["/invitations/not-a-token", "/data-deletion", "/data-deletion/requested", "/no-such-page"],
)
def test_other_public_pages_have_no_switch(client: TestClient, path: str) -> None:
    assert switches(client.get(path).text) == []


def test_a_page_shown_after_a_post_returns_to_its_path_only(admin_client: TestClient) -> None:
    admin_client.post("/admin/subjects", data={"name": "Physics"})
    body = admin_client.post("/admin/subjects?from=form", data={"name": "physics"}).text
    (switch,) = switches(body, "details")
    assert html.Input("next", "hidden", "/admin/subjects") in switch.inputs


def test_signing_in_switching_and_logging_out_leave_the_choice_alone(
    client: TestClient, outbox: list[Any]
) -> None:
    """US5-4: the choice belongs to the browser, not to the account or the session."""
    client.cookies.set("sc_theme", "dark")
    responses = [request_code(client, email=ADMIN_STUDENT_EMAIL)]
    responses.append(submit_code(client, code_from(outbox[-1]), email=ADMIN_STUDENT_EMAIL))
    responses.append(client.post("/role", data={"role": "student"}, follow_redirects=False))
    responses.append(client.post("/logout", follow_redirects=False))
    assert all(theme_cookie(response) is None for response in responses)
    assert client.cookies.get("sc_theme") == "dark"
    assert html.html_attrs(client.get("/login").text).get("data-theme") == "dark"
