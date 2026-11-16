"""Names in the Ukrainian order, and apostrophes in the duplicate key (specs/012.5-ukrainian-
localisation US6, FR-052–FR-054; research R12, R13; data-model §5–§6).

The last test guards every later milestone: no list in `app/services` or `app/routers` may be
ordered by `.casefold()` or by the stored `name_key`, which follow code points, not the alphabet.
"""

import ast
import random
import unicodedata
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

from app.core.migrations import alembic_config
from app.schemas.names import (
    APOSTROPHES,
    name_key,
    name_sort_key,
    person_sort_key,
)

APP = Path(__file__).resolve().parents[2] / "app"
LOCALISATION_REVISION = "7110bec350d2"


def ordered(names: list[str]) -> list[str]:
    return sorted(names, key=name_sort_key)


def test_the_ukrainian_alphabet() -> None:
    names = ["Яковенко", "Ющенко", "Їжакевич", "Іваненко", "Євтушенко", "Ґудзь", "Гончаренко"]
    shuffled = names[:]
    random.Random(12).shuffle(shuffled)
    assert ordered(shuffled) == [
        "Гончаренко",
        "Ґудзь",
        "Євтушенко",
        "Іваненко",
        "Їжакевич",
        "Ющенко",
        "Яковенко",
    ]


def test_every_letter_in_order() -> None:
    alphabet = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
    letters = list(alphabet)
    random.Random(5).shuffle(letters)
    assert "".join(ordered(letters)) == alphabet


def test_case_is_ignored() -> None:
    assert name_sort_key("ФІЗИКА") == name_sort_key("фізика")
    assert ordered(["бета", "Альфа", "АЛЬФА-2"]) == ["Альфа", "АЛЬФА-2", "бета"]


def test_latin_names_come_first_in_their_order() -> None:
    assert ordered(["Біологія", "Physics", "Астрономія", "Algebra"]) == [
        "Algebra",
        "Physics",
        "Астрономія",
        "Біологія",
    ]


def test_other_letters_come_after_the_ukrainian_alphabet() -> None:
    """Ё, Ъ, Ы and Э are not Ukrainian letters: after я, in code point order (ъ, ы, э, ё)."""
    assert ordered(["Эра", "Ёлка", "Яр", "Ъ", "Ыж", "Ар"]) == ["Ар", "Яр", "Ъ", "Ыж", "Эра", "Ёлка"]


def test_digits_and_punctuation_come_before_letters() -> None:
    assert ordered(["Зоря", "«Зоря»", "5-А", "Альфа"]) == ["5-А", "«Зоря»", "Альфа", "Зоря"]


@pytest.mark.parametrize("apostrophe", sorted(APOSTROPHES))
def test_apostrophes_are_ignored_in_the_order(apostrophe: str) -> None:
    assert (
        name_sort_key(f"Мар{apostrophe}яна") == name_sort_key("Марʼяна") == name_sort_key("Маряна")
    )


def test_the_five_apostrophes() -> None:
    assert APOSTROPHES == frozenset({"'", "’", "ʼ", "‘", "`"})
    assert [unicodedata.name(c) for c in sorted(APOSTROPHES)] == [
        "APOSTROPHE",
        "GRAVE ACCENT",
        "MODIFIER LETTER APOSTROPHE",
        "LEFT SINGLE QUOTATION MARK",
        "RIGHT SINGLE QUOTATION MARK",
    ]


@pytest.mark.parametrize("apostrophe", sorted(APOSTROPHES))
def test_the_duplicate_key_folds_every_apostrophe(apostrophe: str) -> None:
    name = f"Мар{apostrophe}яна"
    assert name_key(name) == "марʼяна"
    assert len(name_key(name)) == len(name)


def test_the_duplicate_key_keeps_nfc_and_casefold() -> None:
    assert name_key("ФІЗИКА") == name_key("фізика")
    assert name_key("Straße") == name_key("STRASSE")
    assert name_key("é") == name_key("é")


def test_people_by_last_then_first_name() -> None:
    people = [("Шевченко", "Тарас"), ("Коваленко", "Олена"), ("Коваленко", "Ігор")]
    assert sorted(people, key=lambda p: person_sort_key(*p)) == [
        ("Коваленко", "Ігор"),
        ("Коваленко", "Олена"),
        ("Шевченко", "Тарас"),
    ]


SAMPLES = [
    "Фізика",
    "Мар'яна",
    "Мар’яна",
    "Марʼяна",
    "Мар‘яна",
    "Мар`яна",
    "STRASSE",
    "Straße",
    "é",
    "Ґрунт",
    "КН-21",
    "  інший  ",
]


def test_the_migration_computes_the_same_key() -> None:
    module = (
        ScriptDirectory.from_config(alembic_config()).get_revision(LOCALISATION_REVISION).module
    )
    for sample in SAMPLES:
        assert module._new_name_key(sample) == name_key(sample), sample
        assert module._old_name_key(sample) == unicodedata.normalize("NFC", sample).casefold()


# ---------------------------------------------------------------------------------------------
# The guard (research R13)
# ---------------------------------------------------------------------------------------------


def _sort_keys(tree: ast.AST) -> list[ast.AST]:
    """The `key=` argument of every `sorted(...)` and `.sort(...)` call."""
    keys = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        named = (isinstance(node.func, ast.Name) and node.func.id == "sorted") or (
            isinstance(node.func, ast.Attribute) and node.func.attr == "sort"
        )
        if named:
            keys.extend(keyword.value for keyword in node.keywords if keyword.arg == "key")
    return keys


def _code_point_orders(key: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(key):
        if isinstance(node, ast.Attribute) and node.attr in ("casefold", "name_key"):
            found.append(node.attr)
        if isinstance(node, ast.Name) and node.id == "name_key":
            found.append("name_key")
    return found


@pytest.mark.parametrize(
    "path",
    sorted([*(APP / "services").glob("*.py"), *(APP / "routers").glob("*.py")]),
    ids=lambda p: p.relative_to(APP).as_posix(),
)
def test_no_list_is_ordered_by_code_points(path: Path) -> None:
    tree = ast.parse(path.read_text())
    offenders = [
        f"{path.name}:{key.lineno}: {attribute}"
        for key in _sort_keys(tree)
        for attribute in _code_point_orders(key)
    ]
    assert offenders == [], "sort by name_sort_key or person_sort_key (milestone 12.5 FR-052)"


def test_the_guard_finds_a_casefold_sort() -> None:
    tree = ast.parse("rows = sorted(rows, key=lambda r: (r.name.casefold(), r.id))")
    assert [_code_point_orders(key) for key in _sort_keys(tree)] == [["casefold"]]
    tree = ast.parse("rows.sort(key=lambda r: (r.name_key, r.id))")
    assert [_code_point_orders(key) for key in _sort_keys(tree)] == [["name_key"]]
