"""Name rules shared by subjects, regions and institutions: the validation boundary for their
writes. Pure, no I/O.

See specs/007-region-and-institutions-management/research.md D1 (and specs/006-admin-area
research D1–D2, where the rules were first set). Control characters are refused on the value as
submitted, so a tab or line break at either end is reported rather than silently trimmed away.
Only then is the name trimmed and its length (1–200, counted in Unicode code points) checked.
Inner spaces are kept exactly.

Uniqueness ignores case for every alphabet, and the apostrophe's spelling (milestone 12.5):
`name_key` gives the value the tables' unique constraints hold, computed here in Python so SQLite
and PostgreSQL agree. Lists follow the Ukrainian alphabet through `name_sort_key` and
`person_sort_key`, never the code points of `name_key` (milestone 12.5 research R12, R13).
"""

import unicodedata

from app.core.i18n import Text, _

NAME_MAX_LENGTH = 200
NAME_KEY_MAX_LENGTH = 600
"""3 × 200: the most Unicode case folding can expand a name. Both are also the column lengths in
the models, so the rules and the columns cannot drift."""

_CONTROL_CATEGORIES = frozenset({"Zl", "Zp"})


class InvalidName(ValueError):
    """The name breaks a rule; `message` is ready to show in the form."""

    def __init__(self, message: Text) -> None:
        super().__init__(message)
        self.message = message


def _is_control(character: str) -> bool:
    category = unicodedata.category(character)
    return category.startswith("C") or category in _CONTROL_CATEGORIES


def has_control_character(raw: str) -> bool:
    """Whether `raw` holds a control character: any `C*` category, a line separator (`Zl`) or a
    paragraph separator (`Zp`). Shared with the person names of milestone 8."""
    return any(_is_control(character) for character in raw)


def clean_name(raw: str) -> str:
    """The trimmed name, or `InvalidName` with the first rule it breaks."""
    if has_control_character(raw):
        raise InvalidName(
            _("The name cannot contain tabs, line breaks or other control characters.")
        )
    name = raw.strip()
    if not name:
        raise InvalidName(_("Enter a name."))
    if len(name) > NAME_MAX_LENGTH:
        raise InvalidName(_("The name can be at most %(max)d characters.", max=NAME_MAX_LENGTH))
    return name


APOSTROPHES = frozenset("'’ʼ‘`")
"""The five characters people type as the Ukrainian apostrophe (milestone 12.5 FR-054): U+0027,
U+2019, U+02BC, U+2018 and U+0060. In a key each is the letter apostrophe ʼ (U+02BC)."""

LETTER_APOSTROPHE = "ʼ"

UKRAINIAN_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
"""The 33 letters, in order (milestone 12.5 data-model §6)."""

_UKRAINIAN_RANK = {letter: rank for rank, letter in enumerate(UKRAINIAN_ALPHABET)}


def name_key(name: str) -> str:
    """The uniqueness key of an already cleaned name: NFC-normalised, then case-folded, so
    "Фізика" = "ФІЗИКА", "ß" = "SS", and composed and decomposed "é" are the same; and every
    apostrophe the same (milestone 12.5 FR-054), so «Мар'яна» = «Марʼяна». One character stays
    one character, so the key's length is the folded name's."""
    folded = unicodedata.normalize("NFC", name).casefold()
    return "".join(LETTER_APOSTROPHE if c in APOSTROPHES else c for c in folded)


def _character_order(character: str) -> tuple[int, int]:
    if not character.isalpha():
        return (0, ord(character))
    if unicodedata.name(character, "").startswith("LATIN"):
        return (1, ord(character))
    rank = _UKRAINIAN_RANK.get(character)
    if rank is not None:
        return (2, rank)
    return (3, ord(character))


def name_sort_key(name: str) -> tuple[tuple[int, int], ...]:
    """Where a name stands in a list (milestone 12.5 FR-052, data-model §6), ignoring case and
    apostrophes: anything that is not a letter first (digits, spaces, punctuation), then Latin
    letters in their usual order, then the Ukrainian alphabet а … я, then any other letter (Ё, Ъ,
    Ы, Э…). Computed for sorting only, never stored; lists add the record's id as the last
    tie-break."""
    folded = unicodedata.normalize("NFC", name).casefold()
    return tuple(_character_order(c) for c in folded if c not in APOSTROPHES)


def person_sort_key(last_name: str, first_name: str) -> tuple[tuple[tuple[int, int], ...], ...]:
    """People in a list: by last name, then first name, each in the Ukrainian order."""
    return (name_sort_key(last_name), name_sort_key(first_name))
