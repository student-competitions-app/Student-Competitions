"""The interface language (specs/012.5-ukrainian-localisation US1, US2, US3; research R1, R7, R8,
R17; contracts/http-routes.md §1).

Sections:

- **default**: with no choice, every page is in the deployment's default language, Ukrainian in
  production, whatever the browser prefers; an unknown cookie value is no choice.
- **route**: `POST /language` stores the choice and returns to the page; refused addresses fall
  back; an unknown value stores nothing; the cross-site check applies; the choice survives
  signing in, switching role and signing out; nothing logs the cookie.
- **switch on every page**: the switch is in the top bar of every kind of page, before the user
  menu, returning to the page itself.
- **entered content**: what people enter is shown exactly as entered in either language; a form
  with errors speaks the chosen language and keeps the typed values.

Expected Ukrainian texts are read from the catalogue (`ukrainian(...)`) wherever the wording itself
is not the point; the application's name is fixed by the spec.

Every case runs on both engines.
"""

import dataclasses
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.i18n import Language, _, use_language
from app.main import app
from app.models import AccessLevel
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    invite,
    make_institution,
    make_subject,
)
from tests.integration.test_login_flow import code_from, request_code, submit_code

UKRAINIAN_NAME = "Студентські змагання"
ENGLISH_NAME = "Student Competitions"
BROWSER_PREFERS_ENGLISH = {"Accept-Language": "en-GB,en;q=0.9"}


def ukrainian(msgid: str, **params: object) -> str:
    """The Ukrainian wording of a message, from the real catalogue."""
    with use_language(Language.UK):
        return str(_(msgid, **params))


def title(body: str) -> str:
    (element,) = html.parse(body).find_all("title")
    return element.text()


@pytest.fixture
def teacher_invitation(client: TestClient) -> Iterator[str]:
    """The path of a fresh teacher invitation, issued by the administrator."""
    institution = make_institution(app.state.engine, "Kyiv Polytechnic")
    token = invite(
        app.state.engine,
        app.state.settings,
        email="olena@example.org",
        institutions={institution: AccessLevel.READ},
    )
    yield f"/invitations/{token}"


# ---------------------------------------------------------------------------------------------
# The default (US1)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("/login", "Sign in"),
        ("/data-deletion", "Delete my data"),
        ("/no-such-page", "Page not found"),
    ],
)
def test_a_first_visit_is_ukrainian_whatever_the_browser_prefers(
    ukrainian_default: None, client: TestClient, path: str, heading: str
) -> None:
    response = client.get(path, headers=BROWSER_PREFERS_ENGLISH)
    assert html.html_attrs(response.text)["lang"] == "uk"
    assert html.h1(response.text) == ukrainian(heading)
    assert html.h1(response.text) != heading
    assert UKRAINIAN_NAME in title(response.text)


def test_an_invitation_opens_in_ukrainian(
    ukrainian_default: None, client: TestClient, teacher_invitation: str
) -> None:
    body = client.get(teacher_invitation, headers=BROWSER_PREFERS_ENGLISH).text
    assert html.html_attrs(body)["lang"] == "uk"
    assert html.h1(body) == ukrainian("Invitation to %(app)s", app=UKRAINIAN_NAME)
    assert UKRAINIAN_NAME in title(body)


@pytest.mark.parametrize("value", ["ua", "UK", "en-GB", "", "x" * 4000])
def test_an_unknown_cookie_value_is_no_choice(
    ukrainian_default: None, client: TestClient, value: str
) -> None:
    client.cookies.set("sc_lang", value)
    response = client.get("/login")
    assert response.status_code == 200
    assert html.html_attrs(response.text)["lang"] == "uk"
    assert html.h1(response.text) == ukrainian("Sign in")


def test_a_ukrainian_choice_over_an_english_default(client: TestClient) -> None:
    """The suite's default is English (FR-067); the cookie wins."""
    assert html.h1(client.get("/login").text) == "Sign in"
    client.cookies.set("sc_lang", "uk")
    body = client.get("/login").text
    assert html.html_attrs(body)["lang"] == "uk"
    assert html.h1(body) == ukrainian("Sign in")


def test_an_english_choice_over_a_ukrainian_default(
    ukrainian_default: None, client: TestClient
) -> None:
    client.cookies.set("sc_lang", "en")
    body = client.get("/login").text
    assert html.html_attrs(body)["lang"] == "en"
    assert html.h1(body) == "Sign in"
    assert ENGLISH_NAME in title(body)


# ---------------------------------------------------------------------------------------------
# The route (US2, contracts/http-routes.md §1)
# ---------------------------------------------------------------------------------------------


def choose(browser: TestClient, language: str | None, next_path: str, **headers: str) -> Any:
    data = {"next": next_path} if language is None else {"language": language, "next": next_path}
    return browser.post("/language", data=data, headers=headers, follow_redirects=False)


def language_cookie(response: Any) -> str | None:
    """The `sc_lang` Set-Cookie header of `response`, if any."""
    found = [h for h in response.headers.get_list("set-cookie") if h.startswith("sc_lang=")]
    assert len(found) <= 1
    return found[0] if found else None


@pytest.mark.parametrize("language", ["uk", "en"])
def test_choosing_a_language_stores_it_for_a_year_and_returns(
    client: TestClient, language: str
) -> None:
    """`uk` is stored too, although the suite's default is English (FR-015)."""
    response = choose(client, language, "/login?next=%2Fprofile")
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fprofile"
    cookie = language_cookie(response)
    assert cookie is not None
    assert cookie.startswith(f"sc_lang={language};")
    for attribute in ("Max-Age=31536000", "Path=/", "HttpOnly", "SameSite=lax"):
        assert attribute in cookie
    assert "Secure" not in cookie


def test_in_production_the_cookie_is_secure(client: TestClient) -> None:
    settings = app.state.settings
    app.state.settings = dataclasses.replace(settings, production=True)
    try:
        cookie = language_cookie(choose(client, "uk", "/login"))
    finally:
        app.state.settings = settings
    assert cookie is not None and "Secure" in cookie


def test_the_page_and_its_query_are_kept(admin_client: TestClient) -> None:
    target = "/admin/subjects?subject=3&status=upcoming&page=2"
    assert choose(admin_client, "uk", target).headers["location"] == target


@pytest.mark.parametrize(
    "next_path",
    ["https://evil.example/", "//evil.example", "/login/code", "/language", "/no-such-page", ""],
)
def test_a_refused_address_falls_back_and_the_choice_is_still_stored(
    client: TestClient, admin_client: TestClient, next_path: str
) -> None:
    signed_out = choose(client, "uk", next_path)
    assert signed_out.headers["location"] == "/login"
    assert language_cookie(signed_out) is not None
    signed_in = choose(admin_client, "uk", next_path)
    assert signed_in.headers["location"] == "/"
    assert language_cookie(signed_in) is not None


@pytest.mark.parametrize("language", ["ua", "EN", "", None])
def test_an_unknown_value_stores_nothing_and_still_returns(
    client: TestClient, language: str | None
) -> None:
    response = choose(client, language, "/login")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert language_cookie(response) is None


def test_choosing_the_current_language_again_stores_it(client: TestClient) -> None:
    client.cookies.set("sc_lang", "en")
    response = choose(client, "en", "/login")
    assert response.headers["location"] == "/login"
    assert language_cookie(response) is not None


def test_a_cross_site_choice_is_refused(client: TestClient) -> None:
    response = choose(client, "uk", "/login", **{"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert html.h1(response.text) == "Request refused"
    assert language_cookie(response) is None


def test_the_choice_survives_signing_in_switching_role_and_signing_out(
    ukrainian_default: None, client: TestClient, outbox: list[Any]
) -> None:
    choose(client, "en", "/login")
    assert client.cookies.get("sc_lang") == "en"
    request_code(client, email=ADMIN_STUDENT_EMAIL)
    signed_in = submit_code(client, code_from(outbox[-1]), email=ADMIN_STUDENT_EMAIL)
    assert language_cookie(signed_in) is None
    assert html.html_attrs(client.get("/role").text)["lang"] == "en"
    switched = client.post("/role", data={"role": "student"}, follow_redirects=False)
    assert language_cookie(switched) is None
    assert html.html_attrs(client.get("/").text)["lang"] == "en"
    signed_out = client.post("/logout", follow_redirects=False)
    assert language_cookie(signed_out) is None
    assert html.html_attrs(client.get("/login").text)["lang"] == "en"


def test_no_log_line_names_the_cookie(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """FR-016."""
    with caplog.at_level(logging.DEBUG):
        choose(client, "uk", "/login")
        client.cookies.set("sc_lang", "uk")
        client.get("/login")
        client.get("/no-such-page")
    assert all("sc_lang" not in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------------------------
# The switch on every page (US2, contracts/components.md §1–§2)
# ---------------------------------------------------------------------------------------------


def switch_of(body: str) -> html.Element:
    """The one language switch, which must be in the top bar."""
    (header,) = html.parse(body).find_all("header")
    found = [d for d in header.find_all("details") if "language-switch" in d.classes()]
    assert len(found) == 1
    assert len([d for d in html.parse(body).iter() if "language-switch" in d.classes()]) == 1
    return found[0]


def assert_switch(body: str, return_path: str, current: str = "en") -> None:
    switch = switch_of(body)
    (form,) = [f for f in html.forms(body, "header") if f.action == "/language"]
    assert form.method == "post"
    assert html.Input("next", "hidden", return_path) in form.inputs
    assert [(b.name, b.value, b.text) for b in form.buttons] == [
        ("language", "uk", "Українська"),
        ("language", "en", "English"),
    ]
    buttons = switch.find_all("button")
    assert [b.attrs["lang"] for b in buttons] == ["uk", "en"]
    assert [b.attrs.get("aria-current") for b in buttons] == [
        "true" if current == "uk" else None,
        "true" if current == "en" else None,
    ]
    flags = [i.attrs["src"] for i in switch.find_all("img")]
    assert flags[1:] == ["/static/img/flag-ua.svg", "/static/img/flag-gb.svg"]
    header = html.parse(body).find_all("header")[0]
    order = [
        e
        for e in header.iter()
        if {"language-switch", "user-menu"} & set(e.classes()) and e.tag == "details"
    ]
    assert order[0].start == switch.start


@pytest.mark.parametrize(
    ("path", "return_path"),
    [
        ("/login?next=%2Fprofile", "/login?next=%2Fprofile"),
        ("/data-deletion", "/data-deletion"),
        ("/no-such-page", "/no-such-page"),
    ],
)
def test_the_switch_on_signed_out_pages(client: TestClient, path: str, return_path: str) -> None:
    assert_switch(client.get(path).text, return_path)


def test_the_switch_on_an_invitation_and_the_code_entry(
    client: TestClient, teacher_invitation: str
) -> None:
    assert_switch(client.get(teacher_invitation).text, teacher_invitation)
    body = request_code(client, email=TEACHER_EMAIL).text
    assert_switch(body, "/login")


def test_the_switch_after_a_form_error_returns_to_the_path(client: TestClient) -> None:
    body = client.post("/login?from=form", data={"email": "not-an-address"}).text
    assert html.error_summary(body) is not None
    assert_switch(body, "/login")


@pytest.mark.parametrize(
    ("email", "path"),
    [
        ("admin@example.com", "/admin/teachers"),
        (TEACHER_EMAIL, "/teacher/students"),
        (TEACHER_EMAIL, "/profile"),
        (ADMIN_STUDENT_EMAIL, "/role"),
    ],
)
def test_the_switch_on_every_role_s_pages_comes_before_the_user_menu(
    client_as: ClientAs, email: str, path: str
) -> None:
    browser = client_as(email, current_role=None) if path == "/role" else client_as(email)
    body = browser.get(path).text
    assert_switch(body, path)
    header = html.parse(body).find_all("header")[0]
    menus = [d for d in header.find_all("details") if "user-menu" in d.classes()]
    assert len(menus) == 1


def test_the_switch_marks_ukrainian_when_it_is_current(client: TestClient) -> None:
    client.cookies.set("sc_lang", "uk")
    body = client.get("/login").text
    assert_switch(body, "/login", current="uk")
    summary = switch_of(body).find_all("summary")[0]
    (name,) = [s for s in summary.find_all("span") if "language-switch-name" in s.classes()]
    assert (name.attrs["lang"], name.text()) == ("uk", "Українська")


# ---------------------------------------------------------------------------------------------
# Entered content (US3, FR-025)
# ---------------------------------------------------------------------------------------------


def test_entered_names_are_never_translated(client_as: ClientAs) -> None:
    make_subject(app.state.engine, "Physics")
    make_subject(app.state.engine, "Фізика")
    admin = client_as(ADMIN_EMAIL)
    for language in ("uk", "en"):
        admin.cookies.set("sc_lang", language)
        column = ukrainian("Name") if language == "uk" else "Name"
        rows = [row[column] for row in html.table_rows(admin.get("/admin/subjects").text)]
        assert sorted(rows) == ["Physics", "Фізика"]


def test_a_form_with_errors_speaks_the_chosen_language_and_keeps_the_values(
    client_as: ClientAs,
) -> None:
    admin = client_as(ADMIN_EMAIL)
    admin.cookies.set("sc_lang", "uk")
    make_subject(app.state.engine, "Physics")
    response = admin.post("/admin/subjects", data={"name": "physics"})
    assert response.status_code == 400
    summary = html.error_summary(response.text)
    assert summary is not None
    assert summary.heading == ukrainian("There is a problem")
    assert [text for _, text in summary.items] == [
        ukrainian("A subject named “%(name)s” already exists.", name="Physics")
    ]
    assert html.control(response.text, "name")["value"] == "physics"
