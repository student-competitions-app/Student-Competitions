"""Where a sign-in may send the browser afterwards: only to a local page, never elsewhere.

See specs/004-email-otp-auth/research.md#d12--safe-return-to-addresses.
"""

import pytest

from app.core.security import safe_next_path

LONGEST = "/" + "a" * 2047


def test_the_longest_accepted_path_is_2048_characters() -> None:
    assert len(LONGEST) == 2048


@pytest.mark.parametrize("value", ["/", "/questions", "/a/b?x=1&y=%2F", LONGEST])
def test_local_paths_are_kept(value: str) -> None:
    assert safe_next_path(value) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        LONGEST + "a",
        "questions",
        "//evil.example",
        "///evil.example",
        "/\\evil.example",
        "\\\\evil.example",
        "https://evil.example/",
        "http:/evil.example",
        "javascript:alert(1)",
        "/ok\x00",
        "/a b",
        "/a\tb",
        "/login",
        "/login?next=/x",
        "/login/code",
        "/logout",
    ],
)
def test_anything_else_becomes_the_home_page(value: str | None) -> None:
    assert safe_next_path(value) == "/"
