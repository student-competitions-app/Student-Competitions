"""The question bank's field rules: the question text and the reference answer.

See specs/011-question-bank/research.md R4 and contracts/services.md §schemas/question. Cyrillic
`ї` is used for the length limit because it is two bytes in UTF-8: the limit counts characters,
not bytes.
"""

import pytest

from app.schemas.question import (
    QUESTION_FIELD_MAX_LENGTH,
    InvalidQuestionField,
    clean_question_field,
    question_field_errors,
)

MESSAGES = {
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
FIELDS = ["text", "reference_answer"]


def test_the_limit_is_two_thousand() -> None:
    assert QUESTION_FIELD_MAX_LENGTH == 2000


@pytest.mark.parametrize("field", FIELDS)
def test_surrounding_whitespace_is_trimmed_and_inner_line_breaks_kept(field: str) -> None:
    assert clean_question_field("  a \n", field) == "a"
    assert clean_question_field("a\n\nb", field) == "a\n\nb"
    assert clean_question_field("a\tb", field) == "a\tb"


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("raw", ["a\r\nb", "a\rb"], ids=["crlf", "cr"])
def test_line_endings_become_line_feeds(field: str, raw: str) -> None:
    assert clean_question_field(raw, field) == "a\nb"


@pytest.mark.parametrize("field", FIELDS)
def test_a_crlf_line_break_counts_once(field: str) -> None:
    raw = ("a" * 99 + "\r\n") * 19 + "a" * 100  # 2,019 sent, 2,000 once each break is one
    cleaned = clean_question_field(raw, field)
    assert cleaned == raw.replace("\r\n", "\n")
    assert len(cleaned) == 2000


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize(
    ("raw", "rule"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("\n\t ", "empty"),
        ("a\x00b", "null"),
        ("a" * 2001, "long"),
        ("ї" * 2001, "long"),
    ],
    ids=["empty", "spaces", "whitespace", "null", "long-ascii", "long-cyrillic"],
)
def test_a_refused_value_has_its_message(field: str, raw: str, rule: str) -> None:
    with pytest.raises(InvalidQuestionField) as caught:
        clean_question_field(raw, field)
    assert caught.value.message == MESSAGES[field][rule]


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize(
    "raw",
    ["a" * 2000, "ї" * 2000, "a" * 1000 + "\n" + "a" * 999],
    ids=["ascii", "cyrillic", "line-break"],
)
def test_exactly_two_thousand_characters_are_accepted(field: str, raw: str) -> None:
    assert clean_question_field(raw, field) == raw


@pytest.mark.parametrize("field", FIELDS)
def test_markup_is_kept_unchanged(field: str) -> None:
    assert clean_question_field("<b>&</b>", field) == "<b>&</b>"


def test_both_fields_are_checked_at_once() -> None:
    errors, text, answer = question_field_errors(" ", "")
    assert errors == {
        "text": MESSAGES["text"]["empty"],
        "reference_answer": MESSAGES["reference_answer"]["empty"],
    }
    assert (text, answer) == (" ", "")


def test_only_the_failing_field_is_reported() -> None:
    errors, text, answer = question_field_errors("  Why?\r\n", "x" * 2001)
    assert errors == {"reference_answer": MESSAGES["reference_answer"]["long"]}
    assert text == "Why?"
    assert answer == "x" * 2001


def test_valid_fields_are_returned_cleaned() -> None:
    assert question_field_errors(" Why? ", "\nBecause.\n") == ({}, "Why?", "Because.")


def test_a_text_equal_to_its_answer_is_accepted() -> None:
    assert question_field_errors("Same", "Same") == ({}, "Same", "Same")
