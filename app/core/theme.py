"""The theme choice: Light, Dark or Device (specs/010-design-system-ui-guidelines research D5,
data-model §1).

The choice lives in one browser cookie, `sc_theme`, holding `light` or `dark`; no cookie means
Device, which follows the operating system's `prefers-color-scheme`. Choosing Device deletes the
cookie, so "no cookie means Device" is true in exactly one place, and anything unexpected in the
cookie is Device too.

The cookie holds only the choice: no identifier, nothing linked to an account or a session, and
nothing in the database. It is therefore not personal data and needs no consent of its own.
Signing in, switching role and signing out neither read nor change it. It is `HttpOnly`, since no
script needs it: the server reads it and renders `data-theme` on `<html>`, so the first paint is
already in the chosen theme. No log line ever names it.
"""

from enum import StrEnum

from fastapi import Request, Response

THEME_COOKIE_NAME = "sc_theme"
THEME_COOKIE_MAX_AGE = 31_536_000
"""One year, in seconds."""


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"
    DEVICE = "device"


def parse_theme(value: str | None) -> Theme:
    """`light` or `dark`, exactly, gives that theme; anything else (missing, empty, unknown, or
    another case) is Device."""
    if value == Theme.LIGHT.value:
        return Theme.LIGHT
    if value == Theme.DARK.value:
        return Theme.DARK
    return Theme.DEVICE


def read_theme(request: Request) -> Theme:
    """The browser's choice, from its cookie. Never raises."""
    return parse_theme(request.cookies.get(THEME_COOKIE_NAME))


def apply_theme(response: Response, theme: Theme, *, secure: bool) -> None:
    """Keep the choice in `response`: set the cookie for Light and Dark, delete it for Device.
    `secure` is the production flag, as for the session cookie."""
    if theme is Theme.DEVICE:
        response.delete_cookie(
            THEME_COOKIE_NAME, path="/", secure=secure, httponly=True, samesite="lax"
        )
        return
    response.set_cookie(
        THEME_COOKIE_NAME,
        theme.value,
        max_age=THEME_COOKIE_MAX_AGE,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
