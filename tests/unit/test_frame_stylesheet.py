"""Static checks of the pinned frame and the loading bar in `app.css`
(specs/010.1-loading-feedback-pinned-frame FR-005, FR-012–FR-016, SC-007; research R5, R7–R10).

The stylesheet is read as text, as `test_stylesheet.py` does: the frame sticks only on screens at
least 600 px tall and never in print, targets keep their distance from it, the bar stands still
under reduced motion, and the user menu scrolls inside itself. How it looks in a browser is
checked by hand from the quickstart.
"""

import re

from tests.unit.test_stylesheet import APP_CSS

PINNED = "screen and (min-height: 600px)"


def _css() -> str:
    return re.sub(r"/\*.*?\*/", " ", APP_CSS, flags=re.DOTALL)


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _blocks(css: str) -> list[tuple[str, str]]:
    """The top-level `(prelude, body)` pairs, matched by braces, so `@media` blocks keep their
    nested rules in their body."""
    found, depth, start, prelude_start = [], 0, 0, 0
    for index, char in enumerate(css):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                found.append((_collapse(css[prelude_start:start]), css[start + 1 : index]))
                prelude_start = index + 1
        elif char == ";" and depth == 0:
            prelude_start = index + 1
    return found


def media_blocks(prelude: str) -> list[str]:
    """The bodies of every `@media` block whose condition is exactly `prelude`."""
    return [body for head, body in _blocks(_css()) if head == f"@media {prelude}"]


def rules(css: str) -> list[tuple[str, str]]:
    """Every innermost rule of `css` as `(selector, body)`."""
    return [(_collapse(s), body) for s, body in re.findall(r"([^{};]+)\{([^{}]*)\}", css)]


def top_level_rules() -> list[tuple[str, str]]:
    return [(head, body) for head, body in _blocks(_css()) if not head.startswith("@")]


def rule(selector: str, css_rules: list[tuple[str, str]]) -> str:
    (body,) = [body for s, body in css_rules if s == selector]
    return body


def test_only_the_page_frame_sticks_and_only_on_tall_screens() -> None:
    (pinned,) = media_blocks(PINNED)
    sticky = [s for s, body in rules(pinned) if re.search(r"position:\s*sticky", body)]
    assert sticky == ["body > .frame"]
    body = rule("body > .frame", rules(pinned))
    assert re.search(r"top:\s*0\s*;", body)
    assert re.search(r"z-index:\s*\d+", body)
    everywhere = [
        s
        for s, body in rules(_css())
        if re.search(r"position:\s*(?:sticky|fixed)", body)
        and s not in ("body > .frame", ".loading-bar[data-detached]")
    ]
    assert everywhere == []
    assert len(re.findall(r"position:\s*sticky", _css())) == 1


def test_the_bar_is_still_under_reduced_motion_and_hidden_in_print() -> None:
    (still,) = media_blocks("(prefers-reduced-motion: reduce)")
    assert re.search(r"animation:\s*none", rule(".loading-bar::before", rules(still)))
    (printed,) = media_blocks("print")
    assert re.search(r"display:\s*none", rule(".loading-bar", rules(printed)))


def test_the_user_menu_scrolls_inside_itself() -> None:
    body = rule(".user-menu-panel", top_level_rules())
    assert re.search(r"max-height:\s*calc\(100dvh - var\(--sc-frame-clearance\)\)", body)
    assert re.search(r"overflow-y:\s*auto", body)


def test_phone_tabs_are_touch_target_high() -> None:
    """SC-007: the wrapped administrator tabs keep the pinned frame under a quarter of a
    375 × 667 screen."""
    body = rule("nav.area-tabs li a", top_level_rules())
    assert re.search(r"min-height:\s*var\(--sc-touch-target\)", body)
    wide = [b for b in media_blocks("(min-width: 768px)") if "nav.area-tabs li a" in b]
    assert len(wide) == 1
    assert re.search(r"min-height:\s*3rem", rule("nav.area-tabs li a", rules(wide[0])))


def test_targets_clear_the_frame() -> None:
    """FR-015 (WCAG 2.2, 2.4.11): the page keeps room above every `#` target and focused element,
    more on an area page, whose tabs make the frame taller."""
    (pinned,) = media_blocks(PINNED)
    pinned_rules = rules(pinned)
    assert re.search(
        r"scroll-padding-top:\s*var\(--sc-frame-clearance\)\s*;", rule("html", pinned_rules)
    )
    assert re.search(
        r"scroll-padding-top:\s*var\(--sc-frame-clearance-tabs\)",
        rule("html:has(body > .frame .area-tabs)", pinned_rules),
    )


def test_fields_keep_their_label_in_view() -> None:
    controls = [
        body
        for selector, body in top_level_rules()
        if {"input", "select", "textarea"} <= {part.strip() for part in selector.split(",")}
        and "scroll-margin-top" in body
    ]
    assert len(controls) == 1
    assert re.search(r"scroll-margin-top:\s*var\(--sc-field-clearance\)", controls[0])


def test_the_skip_link_is_above_the_frame() -> None:
    skip = re.search(r"z-index:\s*(\d+)", rule(".skip-link", top_level_rules()))
    (pinned,) = media_blocks(PINNED)
    frame = re.search(r"z-index:\s*(\d+)", rule("body > .frame", rules(pinned)))
    assert skip and frame
    assert int(skip.group(1)) > int(frame.group(1))
