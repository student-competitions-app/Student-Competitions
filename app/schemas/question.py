"""Question field rules: the validation boundary for the question bank's writes. Pure, no I/O.

See specs/011-question-bank/research.md R4 and contracts/services.md §schemas/question. Each
field is cleaned in this order: line endings become `\\n` (a browser sends a textarea's line
breaks as CRLF, so each would otherwise count twice); a NUL character is refused (PostgreSQL
cannot store it); the value is trimmed; then it must be 1–2,000 characters, counted in Unicode
code points. Everything else is kept exactly: inner line breaks, tabs, Cyrillic, `<`, `&`.

Both fields are checked on every submission, so the form can show every error at once.
"""

from typing import Literal

QUESTION_FIELD_MAX_LENGTH = 2000
"""Also both column lengths in `app.models.question`, so the rule and the columns cannot drift."""

QuestionField = Literal["text", "reference_answer"]

_MESSAGES: dict[QuestionField, dict[str, str]] = {
    "text": {
        "empty": "Enter the question text.",
        "long": "The question text can be at most 2,000 characters.",
        "null": "The question text cannot contain a null character.",
    },
    "reference_answer": {
        "empty": "Enter the reference answer.",
        "long": "The reference answer can be at most 2,000 characters.",
        "null": "The reference answer cannot contain a null character.",
    },
}


class InvalidQuestionField(ValueError):
    """The value breaks a rule; `message` is ready to show beside the field."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def clean_question_field(raw: str, field: QuestionField) -> str:
    """The cleaned value, or `InvalidQuestionField` with the first rule it breaks."""
    messages = _MESSAGES[field]
    value = raw.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in value:
        raise InvalidQuestionField(messages["null"])
    value = value.strip()
    if not value:
        raise InvalidQuestionField(messages["empty"])
    if len(value) > QUESTION_FIELD_MAX_LENGTH:
        raise InvalidQuestionField(messages["long"])
    return value


def question_field_errors(text: str, reference_answer: str) -> tuple[dict[str, str], str, str]:
    """Both fields checked: the errors keyed by field id, then the cleaned text and answer (the
    raw value where a field failed)."""
    errors: dict[str, str] = {}
    cleaned: dict[QuestionField, str] = {"text": text, "reference_answer": reference_answer}
    for field, raw in (("text", text), ("reference_answer", reference_answer)):
        try:
            cleaned[field] = clean_question_field(raw, field)
        except InvalidQuestionField as error:
            errors[field] = error.message
    return errors, cleaned["text"], cleaned["reference_answer"]
