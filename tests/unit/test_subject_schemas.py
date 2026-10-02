"""The subject name rules and the uniqueness key.

See specs/006-admin-area/data-model.md "Validation rules" and contracts/subject-service.md. The
messages are asserted verbatim: they are what the form shows.
"""

import pytest

from app.schemas.subject import (
    SUBJECT_NAME_MAX_LENGTH,
    SubjectNameError,
    clean_subject_name,
    subject_name_key,
)

CONTROL = "The name cannot contain tabs, line breaks or other control characters."
EMPTY = "Enter a name."
TOO_LONG = "The name can be at most 200 characters."


def refused(raw: str) -> str:
    with pytest.raises(SubjectNameError) as caught:
        clean_subject_name(raw)
    return caught.value.message


def test_surrounding_spaces_are_trimmed() -> None:
    assert clean_subject_name("  Computer Science  ") == "Computer Science"


def test_inner_spaces_are_kept() -> None:
    assert clean_subject_name("Computer  Science") == "Computer  Science"


@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "spaces"])
def test_a_blank_name_is_refused(blank: str) -> None:
    assert refused(blank) == EMPTY


@pytest.mark.parametrize("letter", ["a", "я"], ids=["latin", "cyrillic"])
def test_the_limit_counts_characters(letter: str) -> None:
    assert clean_subject_name(letter * SUBJECT_NAME_MAX_LENGTH) == letter * 200
    assert refused(letter * (SUBJECT_NAME_MAX_LENGTH + 1)) == TOO_LONG


def test_the_limit_applies_after_trimming() -> None:
    assert clean_subject_name("  " + "a" * 200 + "  ") == "a" * 200


@pytest.mark.parametrize(
    "raw",
    ["\tMathematics", "Math\nematics", "Math ematics", "Math‮ematics", "Math\x00"],
    ids=["leading-tab", "inner-newline", "line-separator", "rtl-override", "nul"],
)
def test_control_characters_are_refused(raw: str) -> None:
    assert refused(raw) == CONTROL


def test_control_characters_are_checked_before_anything_else() -> None:
    assert refused("\n") == CONTROL
    assert refused("a" * 300 + "\t") == CONTROL


def test_the_error_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="Enter a name."):
        clean_subject_name("")


@pytest.mark.parametrize(
    ("one", "other"),
    [
        ("Фізика", "ФІЗИКА"),
        ("ß", "SS"),
        ("é", "é"),
        ("Physics", "PHYSICS"),
    ],
    ids=["cyrillic", "sharp-s", "nfc-nfd", "latin"],
)
def test_names_differing_only_in_case_or_form_share_a_key(one: str, other: str) -> None:
    assert subject_name_key(one) == subject_name_key(other)


def test_different_names_have_different_keys() -> None:
    assert subject_name_key("Physics") != subject_name_key("Chemistry")
    assert subject_name_key("Computer  Science") != subject_name_key("Computer Science")
