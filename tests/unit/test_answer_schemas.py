"""A team's answer rules (specs/012.3-team-answers research R5, contracts/services.md
§schemas/answer): the question bank's cleaning order, with an empty answer allowed. Cyrillic `ї`
is used for the length limit because it is two bytes in UTF-8: the limit counts characters, not
bytes.
"""

import pytest

from app.schemas.answer import ANSWER_MAX_LENGTH, InvalidAnswer, clean_answer

TOO_LONG = "Answer to question 3 can be at most 2,000 characters."
NULL = "Answer to question 3 cannot contain a null character."


def test_the_limit_is_the_question_banks() -> None:
    assert ANSWER_MAX_LENGTH == 2000


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("a\r\nb", "a\nb"),
        ("a\rb", "a\nb"),
        ("first\n\nthird", "first\n\nthird"),
        ("  \n Sodium chloride\nNaCl \r\n ", "Sodium chloride\nNaCl"),
        ("\tTab inside\tkept\t", "Tab inside\tkept"),
        ("<b>&amp;</b>", "<b>&amp;</b>"),
    ],
)
def test_line_endings_and_trimming(raw: str, cleaned: str) -> None:
    assert clean_answer(raw, 3) == cleaned


@pytest.mark.parametrize("raw", ["", " ", "\n", "\r\n \t \r\n", "   \n\n   "])
def test_an_empty_answer_is_not_answered(raw: str) -> None:
    assert clean_answer(raw, 3) == ""


def test_exactly_2000_characters_are_kept() -> None:
    assert clean_answer("a" * 2000, 3) == "a" * 2000
    assert clean_answer("ї" * 2000, 3) == "ї" * 2000


def test_2000_characters_after_trimming_are_kept() -> None:
    """2,001 before trimming, 2,000 after: only a save past the browser's limit can send it."""
    assert clean_answer("a" * 2000 + " ", 3) == "a" * 2000
    assert clean_answer("\r\n" + "a" * 2000, 3) == "a" * 2000


@pytest.mark.parametrize("raw", ["a" * 2001, "ї" * 2001, " " + "b" * 2001 + " "])
def test_more_than_2000_characters_are_refused(raw: str) -> None:
    with pytest.raises(InvalidAnswer) as error:
        clean_answer(raw, 3)
    assert error.value.message == TOO_LONG


def test_a_crlf_counts_as_one_character() -> None:
    raw = "a" * 999 + "\r\n" + "b" * 1000
    assert len(clean_answer(raw, 3)) == 2000


def test_a_null_character_is_refused_before_the_length() -> None:
    with pytest.raises(InvalidAnswer) as error:
        clean_answer("a\x00b", 3)
    assert error.value.message == NULL
    with pytest.raises(InvalidAnswer) as error:
        clean_answer("a" * 2001 + "\x00", 3)
    assert error.value.message == NULL


def test_the_message_names_the_question_passed() -> None:
    with pytest.raises(InvalidAnswer) as error:
        clean_answer("x" * 2001, 17)
    assert error.value.message == "Answer to question 17 can be at most 2,000 characters."
    assert str(error.value) == error.value.message
