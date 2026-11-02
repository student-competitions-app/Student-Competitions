"""The time-zone helpers (specs/012.1-teacher-competitions research R4, R10): only known zone names
are accepted, and a stored time is shown in the zone, or in UTC labelled so."""

import zoneinfo
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.time_zone import format_local_time, parse_time_zone, utc_iso, zone_name

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
    assert zone_name(None) == "UTC"


def test_a_time_in_a_zone() -> None:
    assert format_local_time(MOMENT, KYIV) == "14 March 2027, 10:00"


def test_a_time_with_no_zone_is_labelled_utc() -> None:
    assert format_local_time(MOMENT, None) == "14 March 2027, 08:00 UTC"


def test_a_single_digit_day_and_midnight() -> None:
    assert format_local_time(datetime(2027, 3, 1, 9, 5, tzinfo=UTC), None) == (
        "1 March 2027, 09:05 UTC"
    )
    assert format_local_time(datetime(2027, 3, 1, 22, 0, tzinfo=UTC), KYIV) == (
        "2 March 2027, 00:00"
    )


def test_utc_iso() -> None:
    assert utc_iso(MOMENT) == "2027-03-14T08:00Z"
    assert utc_iso(MOMENT.astimezone(KYIV)) == "2027-03-14T08:00Z"
