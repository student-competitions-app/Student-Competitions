"""Subjects and educational institutions share one set of name rules.

See specs/007-institutions/research.md D1. The rules themselves are covered in
`test_subject_schemas.py`; here, only that both lists use the very same objects, so they cannot
drift apart.
"""

from app.schemas import institution, names, subject


def test_both_lists_use_the_shared_rules() -> None:
    assert subject.SubjectNameError is names.NameRuleError
    assert subject.clean_subject_name is names.clean_name
    assert subject.subject_name_key is names.name_key
    assert institution.InstitutionNameError is names.NameRuleError
    assert institution.clean_institution_name is names.clean_name
    assert institution.institution_name_key is names.name_key


def test_both_lists_have_the_same_limits() -> None:
    assert names.NAME_MAX_LENGTH == 200
    assert names.NAME_KEY_MAX_LENGTH == 600
    assert subject.SUBJECT_NAME_MAX_LENGTH == institution.INSTITUTION_NAME_MAX_LENGTH == 200
    assert subject.SUBJECT_NAME_KEY_MAX_LENGTH == institution.INSTITUTION_NAME_KEY_MAX_LENGTH == 600


def test_institution_names_are_cleaned_and_keyed() -> None:
    assert institution.clean_institution_name("  Lviv Polytechnic  ") == "Lviv Polytechnic"
    assert institution.institution_name_key(
        "Київський університет"
    ) == institution.institution_name_key("КИЇВСЬКИЙ УНІВЕРСИТЕТ")
