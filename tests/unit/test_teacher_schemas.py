"""The institution picker's form values.

See specs/008-teacher-management-consent/research.md#d11 and contracts/services.md
§schemas/teachers.
"""

import pytest

from app.models import AccessLevel
from app.schemas.teachers import InvalidChoice, parse_institution_choices

READ, WRITE = AccessLevel.READ, AccessLevel.WRITE


@pytest.mark.parametrize(
    ("institution", "access", "message"),
    [
        ([], ["12:read"], "Pick at least one educational institution."),
        (["abc"], ["abc:read"], "This educational institution cannot be selected."),
        (["-1"], ["-1:read"], "This educational institution cannot be selected."),
        (["١٢"], ["١٢:read"], "This educational institution cannot be selected."),
        (["2147483648"], ["2147483648:read"], "This educational institution cannot be selected."),
        (["12", "12"], ["12:read"], "Each educational institution can be picked only once."),
        (["12"], [], "Choose Read or Write access for each educational institution."),
        (["12"], ["12:admin"], "Choose Read or Write access for each educational institution."),
        (
            ["12"],
            ["12:read", "12:write"],
            "Choose Read or Write access for each educational institution.",
        ),
    ],
    ids=[
        "none",
        "not-a-number",
        "negative",
        "non-ascii-digits",
        "too-large",
        "duplicate",
        "missing",
        "unknown",
        "conflicting",
    ],
)
def test_invalid_choices_are_refused(
    institution: list[str], access: list[str], message: str
) -> None:
    with pytest.raises(InvalidChoice) as refused:
        parse_institution_choices(institution, access)
    assert refused.value.message == message


def test_levels_of_unpicked_rows_are_ignored() -> None:
    assert parse_institution_choices(["12", "15"], ["12:write", "15:read", "99:write"]) == {
        12: WRITE,
        15: READ,
    }


def test_the_same_level_twice_is_one_level() -> None:
    assert parse_institution_choices(["12"], ["12:read", "12:read"]) == {12: READ}


def test_a_kept_link_keeps_its_stored_level() -> None:
    kept = {12: READ}
    assert parse_institution_choices(["12", "15"], ["12:write", "15:write"], kept) == {
        12: READ,
        15: WRITE,
    }
    assert parse_institution_choices(["12"], [], kept) == {12: READ}
