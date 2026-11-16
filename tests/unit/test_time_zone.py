"""The time-zone helpers (specs/012.1-teacher-competitions research R4, R10): only known zone names
are accepted, and a stored time is shown in the zone, or in Kyiv time labelled so (milestone 12.5
research R9)."""

import zoneinfo
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.i18n import Language, use_language
from app.core.time_zone import (
    format_local_date,
    format_local_time,
    parse_time_zone,
    utc_iso,
    zone_name,
)

KYIV = ZoneInfo("Europe/Kyiv")
MOMENT = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)


def test_the_runtime_has_the_time_zone_database() -> None:
    """A machine or image without the database fails here, not in production (research R4)."""
    assert ZoneInfo("Europe/Kyiv").key == "Europe/Kyiv"
    assert "Europe/Kyiv" in zoneinfo.available_timezones()


@pytest.mark.parametrize("value", ["Europe/Kyiv", "UTC", "America/Argentina/Buenos_Aires"])
def test_known_zones_are_accepted(value: str) -> None:
    zone = parse_time_zone(value)
    assert zone is not None
    assert zone.key == value


@pytest.mark.parametrize(
    "value",
    [None, "", "utc", "europe/kyiv", "posixrules", "../etc/passwd", "Europe/Nowhere", "A" * 65],
)
def test_anything_else_is_no_zone(value: str | None) -> None:
    assert parse_time_zone(value) is None


def test_zone_name() -> None:
    assert zone_name(KYIV) == "Europe/Kyiv"
    assert zone_name(None) == "Europe/Kyiv"


def test_a_time_in_a_zone() -> None:
    assert format_local_time(MOMENT, KYIV) == "14 March 2027, 10:00"
    assert format_local_time(MOMENT, ZoneInfo("UTC")) == "14 March 2027, 08:00"


def test_a_time_with_no_zone_is_kyiv_time_labelled() -> None:
    assert format_local_time(MOMENT, None) == "14 March 2027, 10:00 (Kyiv time)"


def test_a_single_digit_day_and_midnight() -> None:
    assert format_local_time(datetime(2027, 3, 1, 7, 5, tzinfo=UTC), None) == (
        "1 March 2027, 09:05 (Kyiv time)"
    )
    assert format_local_time(datetime(2027, 3, 1, 22, 0, tzinfo=UTC), KYIV) == (
        "2 March 2027, 00:00"
    )


def test_utc_iso() -> None:
    assert utc_iso(MOMENT) == "2027-03-14T08:00Z"
    assert utc_iso(MOMENT.astimezone(KYIV)) == "2027-03-14T08:00Z"


# ---------------------------------------------------------------------------------------------
# Milestone 12.5: both languages and the Kyiv fallback (research R9, contracts/i18n.md §Times)
# ---------------------------------------------------------------------------------------------

GENITIVE_MONTHS = [
    "січня",
    "лютого",
    "березня",
    "квітня",
    "травня",
    "червня",
    "липня",
    "серпня",
    "вересня",
    "жовтня",
    "листопада",
    "грудня",
]


def test_ukrainian_times() -> None:
    with use_language(Language.UK):
        assert format_local_time(MOMENT, KYIV) == "14 березня 2027, 10:00"
        assert format_local_time(datetime(2027, 2, 28, 22, 5, tzinfo=UTC), KYIV) == (
            "1 березня 2027, 00:05"
        )
        assert format_local_time(MOMENT, None) == "14 березня 2027, 10:00 (за київським часом)"
        assert format_local_date(datetime(2026, 10, 15, 9, 0, tzinfo=UTC), None) == (
            "15 жовтня 2026"
        )


@pytest.mark.parametrize("month", range(1, 13))
def test_every_month_is_in_the_genitive(month: int) -> None:
    moment = datetime(2027, month, 10, 9, 0, tzinfo=UTC)
    with use_language(Language.UK):
        assert format_local_date(moment, KYIV) == f"10 {GENITIVE_MONTHS[month - 1]} 2027"


def test_english_times_and_dates() -> None:
    assert format_local_time(MOMENT, None) == "14 March 2027, 10:00 (Kyiv time)"
    assert format_local_date(datetime(2026, 10, 15, 9, 0, tzinfo=UTC), None) == "15 October 2026"
    with use_language(Language.EN):
        assert format_local_time(MOMENT, None) == "14 March 2027, 10:00 (Kyiv time)"


@pytest.mark.parametrize(
    ("moment", "shown"),
    [
        (datetime(2027, 3, 28, 0, 30, tzinfo=UTC), "28 March 2027, 02:30"),
        (datetime(2027, 3, 28, 1, 30, tzinfo=UTC), "28 March 2027, 04:30"),
        (datetime(2027, 10, 31, 0, 30, tzinfo=UTC), "31 October 2027, 03:30"),
        (datetime(2027, 10, 31, 1, 30, tzinfo=UTC), "31 October 2027, 03:30"),
    ],
)
def test_both_sides_of_the_kyiv_clock_changes(moment: datetime, shown: str) -> None:
    """Research R9: daylight saving is the time-zone database's, both in spring and autumn."""
    assert format_local_time(moment, None) == f"{shown} (Kyiv time)"
    assert format_local_time(moment, KYIV) == shown


def test_a_date_near_midnight_utc_is_the_kyiv_date() -> None:
    late = datetime(2026, 10, 14, 22, 30, tzinfo=UTC)
    assert format_local_date(late, None) == "15 October 2026"
    assert format_local_date(late, ZoneInfo("UTC")) == "14 October 2026"
    assert format_local_time(datetime(2027, 2, 28, 22, 5, tzinfo=UTC), None) == (
        "1 March 2027, 00:05 (Kyiv time)"
    )
