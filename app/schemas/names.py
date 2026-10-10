"""Name rules shared by subjects, regions and institutions: the validation boundary for their
writes. Pure, no I/O.

See specs/007-region-and-institutions-management/research.md D1 (and specs/006-admin-area
research D1–D2, where the rules were first set). Control characters are refused on the value as
submitted, so a tab or line break at either end is reported rather than silently trimmed away.
Only then is the name trimmed and its length (1–200, counted in Unicode code points) checked.
Inner spaces are kept exactly.

Uniqueness ignores case for every alphabet: `name_key` gives the value the tables' unique
constraints hold, computed here in Python so SQLite and PostgreSQL agree.
"""

import unicodedata

NAME_MAX_LENGTH = 200
NAME_KEY_MAX_LENGTH = 600
"""3 × 200: the most Unicode case folding can expand a name. Both are also the column lengths in
the models, so the rules and the columns cannot drift."""

_CONTROL_CATEGORIES = frozenset({"Zl", "Zp"})


class InvalidName(ValueError):
    """The name breaks a rule; `message` is ready to show in the form."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_control(character: str) -> bool:
    category = unicodedata.category(character)
    return category.startswith("C") or category in _CONTROL_CATEGORIES


def clean_name(raw: str) -> str:
    """The trimmed name, or `InvalidName` with the first rule it breaks."""
    if any(_is_control(character) for character in raw):
        raise InvalidName("The name cannot contain tabs, line breaks or other control characters.")
    name = raw.strip()
    if not name:
        raise InvalidName("Enter a name.")
    if len(name) > NAME_MAX_LENGTH:
        raise InvalidName(f"The name can be at most {NAME_MAX_LENGTH} characters.")
    return name


def name_key(name: str) -> str:
    """The uniqueness key of an already cleaned name: NFC-normalised, then case-folded, so
    "Фізика" = "ФІЗИКА", "ß" = "SS", and composed and decomposed "é" are the same."""
    return unicodedata.normalize("NFC", name).casefold()
