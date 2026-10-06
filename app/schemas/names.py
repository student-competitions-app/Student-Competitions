"""Name rules shared by every administrator-kept list: subjects and educational institutions.

See specs/006-admin-area/research.md D1–D2 (the rules) and specs/007-institutions/research.md D1
(why they are shared). Pure, no I/O. Control characters are refused on the value as submitted, so
a tab or line break at either end is reported rather than silently trimmed away. Only then is the
name trimmed and its length (1–200, counted in Unicode code points) checked. Inner spaces are kept
exactly.

Uniqueness ignores case for every alphabet: `name_key` gives the value each list's unique
constraint holds, computed here in Python so SQLite and PostgreSQL agree. `app.schemas.subject`
and `app.schemas.institution` expose these under their own names.
"""

import unicodedata

NAME_MAX_LENGTH = 200
NAME_KEY_MAX_LENGTH = 600
"""3 × 200: the most Unicode case folding can expand a name. Both are also the column lengths of
every table that stores such a name, so the rules and the columns cannot drift."""

_CONTROL_CATEGORIES = frozenset({"Zl", "Zp"})


class NameRuleError(ValueError):
    """The name breaks a rule; `message` is ready to show in the form."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_control(character: str) -> bool:
    category = unicodedata.category(character)
    return category.startswith("C") or category in _CONTROL_CATEGORIES


def clean_name(raw: str) -> str:
    """The trimmed name, or `NameRuleError` with the first rule it breaks."""
    if any(_is_control(character) for character in raw):
        raise NameRuleError(
            "The name cannot contain tabs, line breaks or other control characters."
        )
    name = raw.strip()
    if not name:
        raise NameRuleError("Enter a name.")
    if len(name) > NAME_MAX_LENGTH:
        raise NameRuleError(f"The name can be at most {NAME_MAX_LENGTH} characters.")
    return name


def name_key(name: str) -> str:
    """The uniqueness key of an already cleaned name: NFC-normalised, then case-folded, so
    "Фізика" = "ФІЗИКА", "ß" = "SS", and composed and decomposed "é" are the same."""
    return unicodedata.normalize("NFC", name).casefold()
