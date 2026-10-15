"""Person names and addresses for invitations and teacher edits.

See specs/008-teacher-management-consent/research.md#d11 and data-model.md §1.
"""

import pytest

from app.schemas.people import (
    PERSON_NAME_MAX_LENGTH,
    InvalidEmail,
    InvalidPersonName,
    clean_email,
    clean_person_name,
)


def test_the_length_limit_counts_after_trimming() -> None:
    assert PERSON_NAME_MAX_LENGTH == 100
    assert clean_person_name("  " + "a" * 100 + "  ", "first name") == "a" * 100
    with pytest.raises(InvalidPersonName) as refused:
        clean_person_name("a" * 101, "first name")
    assert refused.value.message == "The first name can be at most 100 characters."


def test_surrounding_spaces_are_trimmed_and_inner_ones_kept() -> None:
    assert clean_person_name("  Olena  ", "first name") == "Olena"
    assert clean_person_name("Anna  Maria", "first name") == "Anna  Maria"


@pytest.mark.parametrize("raw", ["\tOlena", "Ole\nna", "Olena ", "Olena\x00"])
def test_control_characters_are_refused_before_trimming(raw: str) -> None:
    with pytest.raises(InvalidPersonName) as refused:
        clean_person_name(raw, "last name")
    assert refused.value.message == (
        "The last name cannot contain tabs, line breaks or other control characters."
    )


@pytest.mark.parametrize("raw", ["", "   "])
def test_an_empty_name_is_refused(raw: str) -> None:
    with pytest.raises(InvalidPersonName) as refused:
        clean_person_name(raw, "first name")
    assert refused.value.message == "Enter a first name."


@pytest.mark.parametrize("label", ["first name", "last name"])
def test_every_message_names_the_field(label: str) -> None:
    for raw in ["", "a" * 101, "\t"]:
        with pytest.raises(InvalidPersonName) as refused:
            clean_person_name(raw, label)
        assert label in refused.value.message


def test_cyrillic_names_are_accepted() -> None:
    assert clean_person_name("Олена", "first name") == "Олена"
    assert clean_person_name("Ковалёнко-Їжак", "last name") == "Ковалёнко-Їжак"


def test_the_email_is_normalised() -> None:
    assert clean_email("  Olena@Example.org ") == "olena@example.org"


@pytest.mark.parametrize(
    "raw", ["not-an-email", "erased-12", "", "a" * 64 + "@" + "d" * 186 + ".com"]
)
def test_invalid_addresses_are_refused(raw: str) -> None:
    with pytest.raises(InvalidEmail) as refused:
        clean_email(raw)
    assert refused.value.message == "Enter a valid email address."
