"""Reading a competition's start as typed (specs/012.1-teacher-competitions research R6,
data-model.md §6): every message, the zone, the gap, the overlap and the overflow."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.schemas.competition import StartErrors, gap_message, local_parts, parse_start

KYIV = ZoneInfo("Europe/Kyiv")
GAP = (
    "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward."
    " Enter another time."
)


@pytest.mark.parametrize(
    ("raw_date", "message"),
    [
        ("", "Enter the start date."),
        ("   ", "Enter the start date."),
        ("2027-02-30", "Enter a real start date."),
        ("2027-04-31", "Enter a real start date."),
        ("14.03.2027", "Enter a real start date."),
        ("2027-3-14", "Enter a real start date."),
        ("0000-01-01", "Enter a real start date."),
        ("٢٠٢٧-٠٣-١٤", "Enter a real start date."),
    ],
)
def test_date_errors(raw_date: str, message: str) -> None:
    assert parse_start(raw_date, "10:00", KYIV) == StartErrors(message, None)


@pytest.mark.parametrize(
    ("raw_time", "message"),
    [
        ("", "Enter the start time."),
        ("24:00", "Enter a real start time."),
        ("10:60", "Enter a real start time."),
        ("10:00:60", "Enter a real start time."),
        ("ab:cd", "Enter a real start time."),
        ("10", "Enter a real start time."),
        ("100:00", "Enter a real start time."),
    ],
)
def test_time_errors(raw_time: str, message: str) -> None:
    assert parse_start("2027-03-14", raw_time, KYIV) == StartErrors(None, message)


def test_both_errors_at_once() -> None:
    assert parse_start("", "ab:cd", KYIV) == StartErrors(
        "Enter the start date.", "Enter a real start time."
    )


def test_a_start_in_kyiv_is_stored_in_utc() -> None:
    assert parse_start("2027-03-14", "10:00", KYIV) == datetime(2027, 3, 14, 8, 0, tzinfo=UTC)


def test_a_start_in_utc() -> None:
    assert parse_start("2027-03-14", "10:00", ZoneInfo("UTC")) == datetime(
        2027, 3, 14, 10, 0, tzinfo=UTC
    )


def test_seconds_are_dropped_and_one_hour_digit_is_read() -> None:
    assert parse_start(" 2027-03-14 ", "10:00:59", KYIV) == datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
    start = parse_start("2027-03-14", "9:30", KYIV)
    assert start == datetime(2027, 3, 14, 7, 30, tzinfo=UTC)
    assert isinstance(start, datetime) and (start.second, start.microsecond) == (0, 0)


def test_a_time_the_clocks_skip_is_refused_on_the_time() -> None:
    assert parse_start("2027-03-28", "03:30", KYIV) == StartErrors(None, GAP)
    assert gap_message(datetime(2027, 3, 28, 3, 30), "Europe/Kyiv") == GAP


def test_a_time_that_happens_twice_is_the_earlier_moment() -> None:
    assert parse_start("2027-10-31", "03:30", KYIV) == datetime(2027, 10, 31, 0, 30, tzinfo=UTC)


def test_a_date_too_far_ahead_to_convert() -> None:
    assert parse_start("9999-12-31", "23:59", ZoneInfo("America/New_York")) == StartErrors(
        "Enter a real start date.", None
    )


def test_local_parts_round_trips() -> None:
    moment = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
    assert local_parts(moment, KYIV) == ("2027-03-14", "10:00")
    assert local_parts(moment, None) == ("2027-03-14", "08:00")
    assert parse_start(*local_parts(moment, KYIV), KYIV) == moment
