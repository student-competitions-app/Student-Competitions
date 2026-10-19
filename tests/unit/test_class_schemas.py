"""The year of study of a class.

See specs/009-classes-students-management/research.md D8 and contracts/services.md
§`app/schemas/classes.py`. Class names reuse the shared name rules, covered by
`test_name_schemas.py`.
"""

import pytest

from app.schemas.classes import INVALID_YEAR, InvalidYear, parse_year_of_study


@pytest.mark.parametrize(("raw", "year"), [("1", 1), ("12", 12), (" 7 ", 7), ("02", 2)], ids=repr)
def test_whole_numbers_from_1_to_12_are_accepted(raw: str, year: int) -> None:
    assert parse_year_of_study(raw) == year


@pytest.mark.parametrize(
    "raw", ["", "   ", "0", "13", "2.5", "+2", "-1", "two", "٢", "1e1"], ids=repr
)
def test_anything_else_is_refused_with_one_message(raw: str) -> None:
    with pytest.raises(InvalidYear) as refused:
        parse_year_of_study(raw)
    assert refused.value.message == INVALID_YEAR


def test_the_message() -> None:
    assert INVALID_YEAR == "Enter a year of study from 1 to 12."
