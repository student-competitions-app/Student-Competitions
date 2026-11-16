"""No untranslated text in the templates (specs/012.5-ukrainian-localisation research R17, FR-018,
FR-005).

Every template but the component gallery is read with Jinja's own lexer. What is left of the
template once its Jinja constructs are removed is the HTML it writes as it stands; any Latin
letter in that HTML's text, or in an `aria-label`, `title`, `alt` or `placeholder` value, is
English that no message covers. The allow-list is the doctype and the language switch's literal
"English" (FR-007: each language is named in its own language), the consent text's heading
"English" (part of the stored wording, FR-047), and the gallery swatches' token
prefix `--sc-`, which is code.

A second guard: `ua` is a country, never a language code (FR-005).
"""

import bisect
import itertools
import re
from pathlib import Path

import pytest
from jinja2 import Environment

APP = Path(__file__).resolve().parents[2] / "app"
TEMPLATES = APP / "templates"
GALLERY = TEMPLATES / "pages" / "admin" / "components.html"

CHECKED_ATTRIBUTES = ("aria-label", "title", "alt", "placeholder")
ALLOWED = {
    ("components/frame.html", "English"),
    ("partials/consent_text.html", "English"),
    ("components/palette.html", "--sc-"),
}
"""(template, text) pairs allowed to hold Latin letters."""

PLACEHOLDER = "\x00"


def templates() -> list[Path]:
    return sorted(p for p in TEMPLATES.rglob("*.html") if p != GALLERY)


def _html_only(source: str) -> list[tuple[int, str]]:
    """The template's data, each Jinja construct replaced by a placeholder, with the line each
    data token starts on."""
    environment = Environment(extensions=["jinja2.ext.i18n"])
    pieces: list[tuple[int, str]] = []
    for line, kind, value in environment.lex(source):
        pieces.append((line, value if kind == "data" else PLACEHOLDER))
    return pieces


def offenders(name: str, source: str) -> list[str]:
    """Every Latin text or checked attribute value of `source` outside a message, as
    `"<name>:<line>: <text>"`."""
    pieces = _html_only(source)
    text = "".join(value for _, value in pieces)
    starts = list(itertools.accumulate((len(value) for _, value in pieces), initial=0))

    def line_of(position: int) -> int:
        index = bisect.bisect_right(starts, position) - 1
        return pieces[index][0] + text[starts[index] : position].count("\n")

    found: list[str] = []
    text = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), text, flags=re.DOTALL)
    for tag in re.finditer(r"<[^<>]*>", text):
        if tag.group(0).lower() == "<!doctype html>":
            continue
        for attribute in CHECKED_ATTRIBUTES:
            for value in re.findall(rf'\b{attribute}="([^"]*)"', tag.group(0)):
                if re.search(r"[A-Za-z]", value.replace(PLACEHOLDER, "")):
                    shown = re.sub(f"{PLACEHOLDER}+", "{…}", value)
                    found.append(f"{name}:{line_of(tag.start())}: {attribute}={shown!r}")
    outside = re.sub(r"<[^<>]*>", lambda m: PLACEHOLDER * len(m.group(0)), text)
    outside = re.sub(r"&[A-Za-z]+;|&#\d+;", " ", outside)
    for run in re.finditer(r"[^\x00]+", outside):
        words = run.group(0)
        # A macro may write attributes outside a whole tag: `{% if x %} title="{{ x }}"{% endif %}`
        for attribute in re.finditer(r'\b([a-z-]+)="([^"]*)"?', words):
            if attribute.group(1) in CHECKED_ATTRIBUTES and re.search(
                r"[A-Za-z]", attribute.group(2)
            ):
                found.append(f"{name}:{line_of(run.start())}: {attribute.group(0)!r}")
        words = re.sub(r'\b[a-z-]+="[^"]*"?', " ", words).strip()
        if re.search(r"[A-Za-z]", words) and (name, words) not in ALLOWED:
            found.append(f"{name}:{line_of(run.start())}: {words!r}")
    return found


@pytest.mark.parametrize("path", templates(), ids=lambda p: p.relative_to(TEMPLATES).as_posix())
def test_no_english_text_outside_a_message(path: Path) -> None:
    assert offenders(path.relative_to(TEMPLATES).as_posix(), path.read_text()) == []


def test_the_gallery_is_the_only_template_left_out() -> None:
    assert GALLERY.is_file()
    assert GALLERY not in templates()
    assert len(templates()) > 80


def test_the_check_finds_text_and_attributes() -> None:
    source = (
        '{% if x %}<p>Hello {{ name }}</p>{% endif %}\n<a aria-label="Open {{ x }}">'
        '{{ _("Go") }}</a><img alt="" src="/a.png"><p>{{ _("Fine") }} &mdash; 12</p>'
    )
    assert offenders("sample.html", source) == [
        "sample.html:2: aria-label='Open {…}'",
        "sample.html:1: 'Hello'",
    ]


# ---------------------------------------------------------------------------------------------
# FR-005: `uk` is the language; `ua` is only ever the flag's file name
# ---------------------------------------------------------------------------------------------

UA_AS_LANGUAGE = [
    re.compile(r"""lang=["']ua["']"""),
    re.compile(r"""Language\(\s*["']ua["']\s*\)"""),
    re.compile(r"""use_language\(\s*["']ua["']\s*\)"""),
    re.compile(r"sc_lang=ua\b"),
]


def test_ua_is_never_a_language_code() -> None:
    offenders = []
    for path in sorted(APP.rglob("*")):
        if path.suffix not in (".py", ".html", ".css", ".js"):
            continue
        text = path.read_text()
        for pattern in UA_AS_LANGUAGE:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(APP)}: {pattern.pattern}")
        for match in re.finditer(r"\bua\b", text):
            context = text[max(0, match.start() - 5) : match.end() + 4]
            if context != "flag-ua.svg"[: len(context)] and "flag-ua.svg" not in context:
                offenders.append(f"{path.relative_to(APP)}: {context!r}")
    assert offenders == []
