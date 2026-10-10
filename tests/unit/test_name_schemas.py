"""The shared name rules, and the subject names that alias them.

See specs/007-region-and-institutions-management/research.md D1 and data-model.md §3. Every rule
is covered in detail through the subject aliases by `test_subject_schemas.py`; this module proves
the aliases are the shared objects and spot-checks the shared functions directly.
"""

import pytest

from app.schemas import subject
from app.schemas.names import (
    NAME_KEY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    InvalidName,
    clean_name,
    name_key,
)

CONTROL = "The name cannot contain tabs, line breaks or other control characters."
TOO_LONG = "The name can be at most 200 characters."


def test_the_subject_names_are_the_shared_objects() -> None:
    assert subject.SubjectNameError is InvalidName
    assert subject.clean_subject_name is clean_name
    assert subject.subject_name_key is name_key
    assert subject.SUBJECT_NAME_MAX_LENGTH == NAME_MAX_LENGTH == 200
    assert subject.SUBJECT_NAME_KEY_MAX_LENGTH == NAME_KEY_MAX_LENGTH == 600


def test_surrounding_spaces_are_trimmed_and_inner_ones_kept() -> None:
    assert clean_name("  Kyiv  ") == "Kyiv"
    assert clean_name("Kyiv  Region") == "Kyiv  Region"


def test_the_key_ignores_case_in_any_alphabet() -> None:
    assert name_key("Київ") == name_key("КИЇВ")


def test_the_length_limit() -> None:
    assert clean_name("a" * 200) == "a" * 200
    with pytest.raises(InvalidName) as caught:
        clean_name("a" * 201)
    assert caught.value.message == TOO_LONG


def test_a_control_character_is_refused() -> None:
    with pytest.raises(InvalidName) as caught:
        clean_name("\tKyiv")
    assert caught.value.message == CONTROL
