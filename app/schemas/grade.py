"""Grade rules: the validation boundary for the grades of a team's answers. Pure, no I/O.

See specs/012.4-finish-and-grade/research.md R4 and contracts/services.md §schemas/grade. A grade
is an integer from 0 to 10, written with ASCII digits only. The whitespace around it (spaces, tabs,
line breaks) is trimmed, leading zeros are ignored however many there are ("07" and "0007" are 7,
"000" is 0), and an empty value means "not graded". Anything else is refused with one message:
"7.5", "-1", "11", "+7", "7.0", "1e1", "seven" and digits of other scripts ("٧", "７").

The grade field is a text field with `inputmode="numeric"`, not a number field: a browser sends an
empty string for a number field holding "seven" or "7.5" in some locales, which would empty a
grade silently instead of showing this error. So the server is the only check, and it never
relies on the browser.
"""

GRADE_MAX = 10
"""The highest grade; the lowest is 0. Also the `grade_range` check constraint of
`app.models.competition.TeamAnswer`."""

GRADE_ERROR = "Enter a whole number from 0 to 10."


class InvalidGrade(ValueError):
    """The value is not a grade; `message` is ready to show beside the field."""

    def __init__(self) -> None:
        super().__init__(GRADE_ERROR)
        self.message = GRADE_ERROR


def clean_grade(raw: str) -> int | None:
    """The grade written in `raw`, `None` when it is empty (not graded), or `InvalidGrade`.

    The length of the significant digits is checked before `int()`, so a very long string of
    digits never reaches Python's integer parser (which refuses more than 4,300 digits); a value
    with more than two significant digits is above 10 anyway."""
    value = raw.strip()
    if not value:
        return None
    if not (value.isascii() and value.isdigit()):
        raise InvalidGrade
    significant = value.lstrip("0") or "0"
    if len(significant) <= 2 and int(significant) <= GRADE_MAX:
        return int(significant)
    raise InvalidGrade
