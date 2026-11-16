"""Both catalogues hold every message, translated (specs/012.5-ukrainian-localisation US12,
FR-059, FR-060; research R5, R17).

The messages are extracted here exactly as `scripts/translations.sh update` extracts them (the same
mapping, `babel.cfg`, and the same keywords), so a message added to a template or to the code
without running the update fails this test, and so does one left untranslated, marked fuzzy, or
translated with other placeholders than its identifier's. Nothing obsolete may linger, and the
component gallery is never extracted (FR-027).
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from babel.messages.catalog import Catalog, Message
from babel.messages.extract import extract_from_dir
from babel.messages.frontend import parse_keywords, parse_mapping_cfg
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parents[2]
LOCALE = ROOT / "app" / "locale"

KEYWORDS = [
    "_",
    "_n:1,2",
    "_p:1c,2",
    "gettext",
    "ngettext:1,2",
    "pgettext:1c,2",
    "npgettext:1c,2,3",
]
"""Mirrors `KEYWORDS` in `scripts/translations.sh`: change both together."""

PLURAL_FORMS = {
    "uk": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),
    "en": "nplurals=2; plural=(n != 1);",
}
"""data-model §3."""

GALLERY_FILES = ("app/templates/pages/admin/components.html", "app/routers/admin_components.py")

PLACEHOLDER = re.compile(r"%\((\w+)\)[sd]")


def _extracted() -> dict[tuple[str | None, str], tuple[tuple[str, ...], list[str]]]:
    """`(context, identifier)` → (every identifier form, locations)."""
    with (ROOT / "babel.cfg").open() as handle:
        method_map, options_map = parse_mapping_cfg(handle)
    found: dict[tuple[str | None, str], tuple[tuple[str, ...], list[str]]] = {}
    for filename, lineno, message, _comments, context in extract_from_dir(
        ROOT,
        method_map,
        options_map,
        keywords=parse_keywords(KEYWORDS),
        directory_filter=lambda path: not Path(path).name.startswith((".", "_")),
    ):
        forms = message if isinstance(message, tuple) else (message,)
        key = (context, forms[0])
        _, locations = found.setdefault(key, (forms, []))
        locations.append(f"{filename}:{lineno}")
    return found


EXTRACTED = _extracted()


def _catalogue(language: str) -> Catalog:
    with (LOCALE / language / "LC_MESSAGES" / "messages.po").open("rb") as handle:
        return read_po(handle, locale=language)


def _entries(catalogue: Catalog) -> Iterator[Message]:
    return (message for message in catalogue if message.id)


def _key(message: Message) -> tuple[str | None, str]:
    identifier = message.id[0] if isinstance(message.id, tuple | list) else message.id
    return message.context, identifier


def test_there_are_messages() -> None:
    assert len(EXTRACTED) > 400


def test_the_gallery_is_never_extracted() -> None:
    for _forms, locations in EXTRACTED.values():
        for location in locations:
            assert not location.startswith(GALLERY_FILES), location


@pytest.mark.parametrize("language", ["uk", "en"])
def test_the_plural_rule(language: str) -> None:
    assert _catalogue(language).plural_forms == PLURAL_FORMS[language]


@pytest.mark.parametrize("language", ["uk", "en"])
def test_every_message_is_in_the_catalogue_and_nothing_else(language: str) -> None:
    keys = {_key(message) for message in _entries(_catalogue(language))}
    missing = sorted(set(EXTRACTED) - keys, key=str)
    obsolete = sorted(keys - set(EXTRACTED), key=str)
    assert missing == [], "run scripts/translations.sh update and translate"
    assert obsolete == [], "run scripts/translations.sh update"


@pytest.mark.parametrize("language", ["uk", "en"])
def test_every_message_is_translated_with_its_placeholders(language: str) -> None:
    catalogue = _catalogue(language)
    nplurals = catalogue.num_plurals
    problems = []
    for message in _entries(catalogue):
        key = _key(message)
        if message.fuzzy:
            problems.append(f"fuzzy: {key}")
        translations = (
            list(message.string) if isinstance(message.string, tuple) else [message.string]
        )
        if isinstance(message.id, tuple | list) and len(translations) != nplurals:
            problems.append(f"plural forms: {key}")
        identifiers = message.id if isinstance(message.id, tuple | list) else [message.id]
        expected = set(PLACEHOLDER.findall(" ".join(identifiers)))
        for translation in translations:
            if not translation:
                problems.append(f"untranslated: {key}")
            elif set(PLACEHOLDER.findall(translation)) != expected:
                problems.append(f"placeholders: {key} → {translation!r}")
    assert problems == []


def test_the_english_catalogue_is_the_identifiers() -> None:
    """English is filled from the identifiers (`scripts/fill_english_catalogue.py`); a deliberate
    English wording would be listed here."""
    for message in _entries(_catalogue("en")):
        if isinstance(message.id, tuple | list):
            assert tuple(message.string) == tuple(message.id), message.id
        else:
            assert message.string == message.id, message.id
