"""The grade rule, `app.schemas.grade.clean_grade` (specs/012.4-finish-and-grade research R4,
contracts/services.md §schemas/grade, FR-025): an integer from 0 to 10 in ASCII digits, trimmed,
leading zeros ignored, empty meaning not graded."""

import pytest

from app.schemas.grade import GRADE_ERROR, InvalidGrade, clean_grade


@pytest.mark.parametrize(
    ("raw", "grade"),
    [
        ("0", 0),
        ("10", 10),
        ("7", 7),
        (" 7 ", 7),
        ("\t7\n", 7),
        ("07", 7),
        ("0007", 7),
        ("010", 10),
        ("0010", 10),
        ("000", 0),
        ("0" * 5000 + "7", 7),
        ("", None),
        ("   ", None),
    ],
)
def test_a_grade_is_cleaned(raw: str, grade: int | None) -> None:
    assert clean_grade(raw) == grade


@pytest.mark.parametrize(
    "raw",
    [
        "7.5",
        "-1",
        "11",
        "011",
        "seven",
        "+7",
        "7.0",
        "1e1",
        "٧",
        "７",
        "1000000",
        "9" * 5000,
        "7 5",
        "7\x00",
    ],
)
def test_anything_else_is_refused(raw: str) -> None:
    with pytest.raises(InvalidGrade) as refused:
        clean_grade(raw)
    assert refused.value.message == GRADE_ERROR == "Enter a whole number from 0 to 10."
