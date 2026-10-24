"""Static checks of `loading-feedback.js` (specs/010.1-loading-feedback-pinned-frame FR-001–FR-011,
FR-020; contracts/loading-script.md; research R1–R4).

The suite has no browser before milestone 16, so the script is read as text: it stays a small,
self-contained script that sends nothing, listens where the contract says, and never disables a
control, which would drop a button's value from the form it sends (FR-010). Its behaviour in a
browser is checked by hand from the quickstart.
"""

import re
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2] / "app" / "static" / "js" / "loading-feedback.js"
).read_text()


def test_it_is_a_plain_script() -> None:
    assert not re.search(r"^\s*(?:import|export)\b", SCRIPT, re.MULTILINE)
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "sendBeacon",
        "localStorage",
        "sessionStorage",
        "document.cookie",
    ):
        assert forbidden not in SCRIPT, forbidden


def test_it_names_no_other_site() -> None:
    """A quote or backtick directly followed by `//` is a URL in a string; `//` comments are not."""
    assert re.search(r"[\"'`](?:https?:)?//", SCRIPT) is None


def test_it_listens_for_links_forms_and_restores() -> None:
    for event in ("click", "submit", "pageshow"):
        assert f'addEventListener("{event}"' in SCRIPT, event
    assert "persisted" in SCRIPT


def test_the_delay_is_200_ms() -> None:
    """FR-002: nothing shows when the next page arrives within 200 ms."""
    assert re.search(r"\bconst\s+DELAY\s*=\s*200\s*;", SCRIPT)
    assert re.search(r"setTimeout\(\s*\w+\s*,\s*DELAY\s*\)", SCRIPT)


def test_it_never_disables_anything() -> None:
    """FR-010: the form data is built after the `submit` event, and a disabled button's value
    would be left out of it, which would break the role switch and the theme switch."""
    assert not re.search(r"\.(?:disabled|readOnly|inert)\s*=", SCRIPT)
    assert not re.search(r"(?:set|toggle)Attribute\(\s*[\"'](?:disabled|readonly|inert)", SCRIPT)


def test_it_stays_small() -> None:
    lines = [line for line in SCRIPT.splitlines() if line.strip()]
    assert len(lines) <= 120, len(lines)


def test_a_sending_post_form_cancels_a_second_submit() -> None:
    """FR-007, contracts/loading-script.md §3: a text-level guard; the behaviour is checked by
    hand from the quickstart."""
    for needle in ("submitter", "formmethod", "preventDefault()"):
        assert needle in SCRIPT, needle


def test_the_busy_state_is_aria_busy() -> None:
    """FR-008, FR-011: set when the bar shows, removed on a Back or Forward restore."""
    assert re.search(r"setAttribute\(\s*\"aria-busy\"\s*,\s*\"true\"\s*\)", SCRIPT)
    assert re.search(r"removeAttribute\(\s*\"aria-busy\"\s*\)", SCRIPT)


def test_a_restore_forgets_every_form_and_button() -> None:
    """FR-011, contracts/loading-script.md §5: a link followed after a slow form replaces the
    pending load, so the restore clears every sending form and every busy button, not only the
    latest."""
    assert re.search(r"\bsending\s*=\s*new\s+WeakSet\(\)", SCRIPT.split("function reset")[1])
    assert "busy.clear()" in SCRIPT
