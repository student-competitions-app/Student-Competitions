"""Class rules: the year of study. Pure, no I/O.

See specs/009-classes-students-management/research.md D8 and contracts/services.md
§`app/schemas/classes.py`. Class **names** follow the subject-name rules of milestone 6 and reuse
`app.schemas.names.clean_name` and `name_key` (FR-002); only the year of study is new here.

The year is read as a plain string, never as an integer form field, so a bad value re-renders the
form with a message instead of FastAPI's 422 JSON. The form's `type="number"` input is a
convenience; this function is the authority.
"""

YEAR_MIN = 1
YEAR_MAX = 12

INVALID_YEAR = "Enter a year of study from 1 to 12."


class InvalidYear(ValueError):
    """The year of study breaks a rule; `message` is ready to show in the form."""

    def __init__(self, message: str = INVALID_YEAR) -> None:
        super().__init__(message)
        self.message = message


def parse_year_of_study(raw: str) -> int:
    """The year of study, trimmed: ASCII digits only, from 1 to 12, so `"02"` is 2. Anything else,
    such as `""`, `"0"`, `"13"`, `"2.5"`, `"+2"`, `"two"` or a non-ASCII digit, raises
    `InvalidYear`."""
    value = raw.strip()
    if not value or not value.isascii() or not value.isdigit():
        raise InvalidYear(INVALID_YEAR)
    year = int(value)
    if not YEAR_MIN <= year <= YEAR_MAX:
        raise InvalidYear(INVALID_YEAR)
    return year
