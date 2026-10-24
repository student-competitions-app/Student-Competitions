"""The theme choice cookie (specs/010-design-system-ui-guidelines data-model §1, research D5)."""

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.core.theme import (
    THEME_COOKIE_MAX_AGE,
    THEME_COOKIE_NAME,
    Theme,
    apply_theme,
    parse_theme,
    read_theme,
)


@pytest.mark.parametrize(("value", "theme"), [("light", Theme.LIGHT), ("dark", Theme.DARK)])
def test_light_and_dark_are_read_exactly(value: str, theme: Theme) -> None:
    assert parse_theme(value) is theme


@pytest.mark.parametrize("value", ["device", None, "", "purple", "Dark", " dark"])
def test_anything_else_is_the_device(value: str | None) -> None:
    assert parse_theme(value) is Theme.DEVICE


def request_with(cookie: str | None) -> Request:
    headers = [(b"cookie", cookie.encode())] if cookie is not None else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


@pytest.mark.parametrize(
    ("cookie", "theme"),
    [
        ("sc_theme=dark", Theme.DARK),
        ("sc_theme=light; other=1", Theme.LIGHT),
        ("sc_theme=Dark", Theme.DEVICE),
        ("sc_theme=", Theme.DEVICE),
        ("unrelated=1", Theme.DEVICE),
        (None, Theme.DEVICE),
        ("not a cookie header ;;; =", Theme.DEVICE),
    ],
)
def test_the_cookie_is_read_with_the_same_rule_and_never_raises(
    cookie: str | None, theme: Theme
) -> None:
    assert read_theme(request_with(cookie)) is theme


def set_cookie(response: Response) -> str:
    [header] = [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]
    return header


@pytest.mark.parametrize("secure", [True, False])
@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_light_and_dark_set_the_cookie(theme: Theme, secure: bool) -> None:
    response = Response()
    apply_theme(response, theme, secure=secure)
    header = set_cookie(response)
    assert header.startswith(f"{THEME_COOKIE_NAME}={theme.value};")
    assert f"Max-Age={THEME_COOKIE_MAX_AGE}" in header
    assert "Path=/" in header
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert ("Secure" in header) is secure


@pytest.mark.parametrize("secure", [True, False])
def test_the_device_deletes_the_cookie(secure: bool) -> None:
    response = Response()
    apply_theme(response, Theme.DEVICE, secure=secure)
    header = set_cookie(response)
    assert header.startswith(f'{THEME_COOKIE_NAME}="";')
    assert "Max-Age=0" in header
    assert "Path=/" in header
    assert "HttpOnly" in header
    assert ("Secure" in header) is secure
