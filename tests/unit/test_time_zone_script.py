"""Static checks of `time-zone.js` (specs/012.1-teacher-competitions FR-020, FR-021, FR-049;
contracts/components.md §7; research R5).

The suite has no browser before milestone 16, so the script is read as text: it stays a small,
self-contained script that sends nothing, stores nothing but the one cookie, writes only a checked
zone name, and changes nothing on the page. Its behaviour in a browser is checked by hand, or with
an ad hoc Playwright run, from the quickstart.
"""

import re
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2] / "app" / "static" / "js" / "time-zone.js"
).read_text()


def test_it_is_a_plain_script() -> None:
    assert not re.search(r"^\s*(?:import|export)\b", SCRIPT, re.MULTILINE)
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "sendBeacon",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "location.reload",
        "location.href =",
        "innerHTML",
        "querySelector",
        "addEventListener",
    ):
        assert forbidden not in SCRIPT, forbidden


def test_it_names_no_other_site() -> None:
    """A quote or backtick directly followed by `//` is a URL in a string; `//` comments are not."""
    assert re.search(r"[\"'`](?:https?:)?//", SCRIPT) is None


def test_it_writes_only_the_zone_cookie_once() -> None:
    assignments = re.findall(r"document\.cookie\s*=[^=]", SCRIPT)
    assert len(assignments) == 1
    assert re.search(r'\bconst\s+COOKIE\s*=\s*"sc_time_zone"\s*;', SCRIPT)
    (line,) = [line for line in SCRIPT.splitlines() if re.search(r"document\.cookie\s*=[^=]", line)]
    assert line.strip().startswith('document.cookie = COOKIE + "=" + zone')
    for attribute in ("Path=/", "Max-Age=31536000", "SameSite=Lax"):
        assert attribute in line, attribute
    assert "HttpOnly" not in SCRIPT


def test_secure_only_over_https() -> None:
    assert re.search(r'location\.protocol\s*===\s*"https:"\s*\?\s*"; Secure"\s*:\s*""', SCRIPT)


def test_it_reads_and_checks_the_zone_first() -> None:
    assert "Intl.DateTimeFormat().resolvedOptions().timeZone" in SCRIPT
    assert r"/^[A-Za-z0-9_+\-]+(?:\/[A-Za-z0-9_+\-]+)*$/" in SCRIPT
    assert "zone.length <= 64" in SCRIPT
    check = SCRIPT.index("NAME.test(zone)")
    assert check < SCRIPT.index("document.cookie =")


def test_it_writes_only_when_the_zone_changed() -> None:
    assert SCRIPT.index("document.cookie\n") < SCRIPT.index("document.cookie =")
    assert "!==" in SCRIPT


def test_it_stays_small() -> None:
    lines = [line for line in SCRIPT.splitlines() if line.strip()]
    assert len(lines) <= 30, len(lines)
