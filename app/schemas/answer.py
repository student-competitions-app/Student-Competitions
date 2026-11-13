"""Answer rules: the validation boundary for a team's answers. Pure, no I/O.

See specs/012.3-team-answers/research.md R5 and contracts/services.md §schemas/answer. The rules
are the question bank's (milestone 11, `app.schemas.question`), in the same order, with one
difference: an empty answer is allowed and means "not answered". Line endings become `\\n` (a
browser sends a textarea's line breaks as CRLF, so each would otherwise count twice); a NUL
character is refused (PostgreSQL cannot store it); the value is trimmed; then it must be at most
2,000 characters, counted in Unicode code points. Everything else is kept exactly: inner line
breaks, tabs, Cyrillic, `<`, `&`.

The answer field also limits its text to 2,000 characters in the browser (`maxlength`); this check
never relies on that limit (spec FR-018).
"""

from app.schemas.question import QUESTION_FIELD_MAX_LENGTH

ANSWER_MAX_LENGTH = QUESTION_FIELD_MAX_LENGTH
"""2,000; also the column length in `app.models.competition.TeamAnswer`."""


class InvalidAnswer(ValueError):
    """The answer breaks a rule; `message` is ready to show beside the field."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def clean_answer(raw: str, number: int) -> str:
    """The cleaned answer to question `number` (its position on the sheet, for the message), `""`
    when it is not answered, or `InvalidAnswer` with the first rule it breaks."""
    value = raw.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in value:
        raise InvalidAnswer(f"Answer to question {number} cannot contain a null character.")
    value = value.strip()
    if len(value) > ANSWER_MAX_LENGTH:
        raise InvalidAnswer(f"Answer to question {number} can be at most 2,000 characters.")
    return value
