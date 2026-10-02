"""Subject name rules: the validation boundary for subject writes. Pure, no I/O.

See specs/006-admin-area/research.md D1–D2 and data-model.md "Validation rules". Control
characters are refused on the value as submitted, so a tab or line break at either end is reported
rather than silently trimmed away. Only then is the name trimmed and its length (1–200, counted in
Unicode code points) checked. Inner spaces are kept exactly.

Uniqueness ignores case for every alphabet: `subject_name_key` gives the value the `subjects`
table's unique constraint holds, computed here in Python so SQLite and PostgreSQL agree.
"""

import unicodedata

SUBJECT_NAME_MAX_LENGTH = 200
SUBJECT_NAME_KEY_MAX_LENGTH = 600
"""3 × 200: the most Unicode case folding can expand a name. Both are also the column lengths in
`app.models.subject`, so the rules and the columns cannot drift."""

_CONTROL_CATEGORIES = frozenset({"Zl", "Zp"})


class SubjectNameError(ValueError):
    """The name breaks a rule; `message` is ready to show in the form."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_control(character: str) -> bool:
    category = unicodedata.category(character)
    return category.startswith("C") or category in _CONTROL_CATEGORIES


def clean_subject_name(raw: str) -> str:
    """The trimmed name, or `SubjectNameError` with the first rule it breaks."""
    if any(_is_control(character) for character in raw):
        raise SubjectNameError(
            "The name cannot contain tabs, line breaks or other control characters."
        )
    name = raw.strip()
    if not name:
        raise SubjectNameError("Enter a name.")
    if len(name) > SUBJECT_NAME_MAX_LENGTH:
        raise SubjectNameError(f"The name can be at most {SUBJECT_NAME_MAX_LENGTH} characters.")
    return name


def subject_name_key(name: str) -> str:
    """The uniqueness key of an already cleaned name: NFC-normalised, then case-folded, so
    "Фізика" = "ФІЗИКА", "ß" = "SS", and composed and decomposed "é" are the same."""
    return unicodedata.normalize("NFC", name).casefold()
