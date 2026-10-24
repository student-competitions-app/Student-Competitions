"""Static checks of the templates and the stylesheet (specs/010-design-system-ui-guidelines
research D16; FR-004, FR-012, FR-041, FR-048, FR-049, SC-003, SC-004, SC-008).

They keep the UI guidelines binding in CI: every class a template uses is defined, every class
`app.css` defines is used, nothing is styled inline or loaded from another site, colours and
lengths come only from the token block, text stays readable, and emphasis is bold. No dependency:
the templates and the CSS are read as text.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
TEMPLATES = APP / "templates"
APP_CSS = (APP / "static" / "css" / "app.css").read_text()
PICO_CSS = (APP / "static" / "css" / "pico.min.css").read_text()

TOKENS_START = "/* == Tokens == */"
TOKENS_END = "/* == End of tokens == */"
BASE_START = "/* == Base == */"

PAGE_SPECIFIC = {
    "subjects-table",
    "teachers-table",
    "institutions-table",
    "students-table",
    "subjects-empty",
    "subjects-actions",
    "subject-name",
    "institution-name",
    "list-empty",
    "questions-empty",
    "question-list",
    "class-picker",
    "class-bar",
    "institutions-layout",
    "regions-list",
    "picker-table",
    "picker",
    "auth",
    "auth-message",
    "auth-alternatives",
    "hero",
    "tagline",
    "admin-tabs",
    "data-unavailable",
    "db-status",
    "status-deactivated",
    "form-error",
    "consent-text",
    "consent-record",
    "detail-lines",
    "role-switch",
    "role-switch-label",
    "release",
    "release-version",
}
"""Research D8's list, plus every other page-only class of the milestone 9 stylesheet."""

CLASS_NAME = r"-?[_a-zA-Z][-_a-zA-Z0-9]*"


def templates() -> dict[Path, str]:
    return {path: path.read_text() for path in sorted(TEMPLATES.rglob("*.html"))}


def without_jinja(markup: str) -> str:
    return re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", markup, flags=re.DOTALL)


def _literals(statement: str) -> list[str]:
    """The string literals of a Jinja expression, leaving out mapping keys (a literal followed by
    `:`), which are lookup keys, not classes."""
    found = []
    for match in re.finditer(r"\"([^\"]*)\"|'([^']*)'", statement):
        if not statement[match.end() :].lstrip().startswith(":"):
            found.append(match.group(1) if match.group(1) is not None else match.group(2))
    return found


def used_classes() -> dict[str, set[Path]]:
    """Class name → the templates using it: every `class="…"` (Jinja statements removed first,
    then the expressions inside the value), plus the string literals of the
    `{% set …_class(es) = … %}` statements in `components/`, the only place a class may be
    built dynamically."""
    used: dict[str, set[Path]] = {}
    for path, source in templates().items():
        names: list[str] = []
        markup = re.sub(r"\{%.*?%\}", " ", source, flags=re.DOTALL)
        markup = re.sub(r"\{#.*?#\}", " ", markup, flags=re.DOTALL)
        for value in re.findall(r'\bclass="([^"]*)"', markup):
            names += without_jinja(value).split()
        if "components" in path.parts:
            pattern = r"\{%-?\s*set\s+\w*_class(?:es)?\s*=(.*?)-?%\}"
            for statement in re.findall(pattern, source, re.S):
                for literal in _literals(statement):
                    names += literal.split()
        for name in names:
            used.setdefault(name, set()).add(path)
    return used


def without_values(css: str) -> str:
    """The CSS with comments, strings and `url(…)` removed, so only selectors and plain values
    are left to scan."""
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.DOTALL)
    css = re.sub(r"url\([^)]*\)", " ", css)
    return re.sub(r"\"[^\"]*\"|'[^']*'", " ", css)


def selectors(css: str) -> list[str]:
    """The selector of every rule (at-rule preludes left out)."""
    found = []
    for prelude in re.findall(r"([^{};]+)\{", without_values(css)):
        prelude = prelude.strip()
        if prelude and not prelude.startswith("@"):
            found.append(prelude)
    return found


def defined_classes(css: str) -> set[str]:
    return {
        name
        for selector in selectors(css)
        for name in re.findall(rf"\.({CLASS_NAME})", re.sub(r"\[[^\]]*\]", " ", selector))
    }


def token_block() -> str:
    return APP_CSS[APP_CSS.index(TOKENS_START) : APP_CSS.index(TOKENS_END)]


def outside_tokens() -> str:
    return APP_CSS[: APP_CSS.index(TOKENS_START)] + APP_CSS[APP_CSS.index(TOKENS_END) :]


def light_tokens() -> str:
    """The body of the token block's first `:root { … }`: the light values."""
    block = token_block()
    start = block.index(":root {")
    return block[start : block.index("}", start)]


def test_every_used_class_is_defined() -> None:
    defined = defined_classes(APP_CSS) | defined_classes(PICO_CSS)
    undefined = {
        name: sorted(str(p.relative_to(TEMPLATES)) for p in paths)
        for name, paths in used_classes().items()
        if name not in defined
    }
    assert not undefined, f"classes used but defined nowhere: {undefined}"


def test_every_app_css_class_is_used() -> None:
    unused = defined_classes(APP_CSS) - set(used_classes())
    assert not unused, f"classes in app.css that no template uses: {sorted(unused)}"


def test_no_inline_style() -> None:
    offenders = [str(p.relative_to(TEMPLATES)) for p, s in templates().items() if " style=" in s]
    assert not offenders, offenders


def test_nothing_loads_from_another_site() -> None:
    pattern = re.compile(r"""\b(?:src|href|action)\s*=\s*["'](?:https?:|//)""")
    offenders = [str(p.relative_to(TEMPLATES)) for p, s in templates().items() if pattern.search(s)]
    assert not offenders, offenders
    css = re.sub(r"/\*.*?\*/", " ", APP_CSS, flags=re.DOTALL)
    assert "@import" not in css
    for target in re.findall(r"url\(\s*[\"']?([^\"')]*)", css):
        assert target.startswith("/static/"), target


def _rem(declaration: str, css: str) -> float:
    found = re.search(rf"{re.escape(declaration)}:\s*([0-9.]+)rem", css)
    assert found is not None, f"{declaration} is not set in rem"
    return float(found.group(1))


def test_readable_text_tokens() -> None:
    """SC-008, FR-004: 16 px body text on a phone, 18 px from 1024 px, line height 1.5."""
    assert _rem("--sc-text-body", light_tokens()) >= 1
    desktop = re.search(r"@media \(min-width: 1024px\)\s*\{(.*?)\}\s*\}", token_block(), re.S)
    assert desktop is not None, "no 1024px block in the tokens"
    assert _rem("--sc-text-body", desktop.group(1)) >= 1.125
    line_height = re.search(r"--sc-line-height:\s*([0-9.]+)", light_tokens())
    assert line_height is not None and float(line_height.group(1)) >= 1.5


def test_tokens_are_defined_once() -> None:
    names = re.findall(r"(--sc-[a-z0-9-]+):", light_tokens())
    assert names, "no tokens on :root"
    repeated = sorted({name for name in names if names.count(name) > 1})
    assert not repeated, repeated
    later = re.findall(r"(--sc-[a-z0-9-]+):", outside_tokens())
    assert not later, f"tokens set outside the token block: {sorted(set(later))}"


def test_emphasis_is_bold_and_text_left_aligned() -> None:
    """FR-004: no italics, no underlined emphasis, no capitals, no justified text."""
    for path, source in templates().items():
        assert not re.search(r"<(i|u)[\s>]", source), path
    css = re.sub(r"/\*.*?\*/", " ", APP_CSS, flags=re.DOTALL)
    assert not re.search(r"font-style:\s*italic", css)
    assert not re.search(r"text-transform:\s*(uppercase|capitalize)", css)
    assert not re.search(r"text-align:\s*justify", css)
    base = css[css.index("em,\ni {") :]
    rule = base[: base.index("}")]
    assert re.search(r"font-style:\s*normal", rule)


def test_no_page_specific_classes_remain() -> None:
    in_templates = sorted(PAGE_SPECIFIC & set(used_classes()))
    in_css = sorted(PAGE_SPECIFIC & defined_classes(APP_CSS))
    site = sorted(
        name
        for name in set(used_classes()) | defined_classes(APP_CSS)
        if name.startswith("site-") and name != "site-footer"
    )
    assert not in_templates and not in_css and not site, (in_templates, in_css, site)


def test_only_tokens_hold_literal_values() -> None:
    """FR-012: no hex colour, `rgb(`/`hsl(` or pixel length outside the token block; the
    `768px` and `1024px` breakpoints and the `600px` height of the pinned frame (milestone 10.1)
    are the only exception."""
    css = without_values(outside_tokens())
    css = re.sub(r"@media[^{]*\{", " ", css)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.findall(r"\b(?:rgb|rgba|hsl|hsla)\(", css)
    assert not re.findall(r"\b\d+(?:\.\d+)?px\b", css)


def _rules(css: str) -> list[tuple[str, str]]:
    """Every innermost rule as `(selector, body)`, comments removed and strings kept, so attribute
    selectors such as `[aria-busy="true"]` survive."""
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.DOTALL)
    return [
        (" ".join(selector.split()), body)
        for selector, body in re.findall(r"([^{};]+)\{([^{}]*)\}", css)
    ]


def test_the_busy_spinner_takes_the_button_colour() -> None:
    """specs/010.1-loading-feedback-pinned-frame research R6: Pico draws its busy spinner white on
    every non-outline button, which hides it on the white secondary buttons. `app.css` redraws it
    as a mask in the button's text colour and cancels Pico's filter with a selector that outranks
    Pico's own."""
    shape = [
        body
        for selector, body in _rules(APP_CSS)
        if '[aria-busy="true"]' in selector
        and selector.endswith("::before")
        and "background-color: currentColor" in body
    ]
    assert len(shape) == 1
    assert re.search(r"(?<!-)mask:\s*var\(--pico-icon-loading\)", shape[0])
    filters = [
        body
        for selector, body in _rules(APP_CSS)
        if selector.startswith('html [aria-busy="true"]')
        and selector.endswith(":not(.outline)::before")
    ]
    assert len(filters) == 1
    assert re.search(r"filter:\s*none", filters[0])
