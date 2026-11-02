"""The start of a competition as a teacher types it: the validation boundary for the start date
and time. Pure, no I/O.

See specs/012.1-teacher-competitions/research.md R6, data-model.md §6 and contracts/services.md
§`app/schemas/competition.py`. The date and the time are read in the zone the form was shown in
(its hidden `time_zone` field, not the cookie, FR-022), then converted to UTC:

- **A gap** (the clocks go forward, so the local time never happens) is refused on the time
  field, naming the time, the date and the zone.
- **An overlap** (the clocks go back, so the local time happens twice) is the earlier of the two
  moments: PEP 495's `fold=0` (FR-023).
- **Seconds** are accepted, because some browsers send them, and dropped: a start is to the
  minute.

Both fields are checked on every submission, so the form can show both errors at once. Whether
the start is in the future is not checked here: the service checks it with its own clock, inside
the write. The name is checked by `app.schemas.names`.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.core.time_zone import MONTHS

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", re.ASCII)

DATE_EMPTY = "Enter the start date."
DATE_INVALID = "Enter a real start date."
TIME_EMPTY = "Enter the start time."
TIME_INVALID = "Enter a real start time."


@dataclass(frozen=True)
class StartErrors:
    """The start's field errors; `None` for a field without one."""

    date: str | None
    time: str | None


def _parse_date(raw: str) -> date | str:
    """The date, or its error message."""
    value = raw.strip()
    if not value:
        return DATE_EMPTY
    if not _DATE.fullmatch(value):
        return DATE_INVALID
    try:
        return date.fromisoformat(value)
    except ValueError:
        return DATE_INVALID


def _parse_time(raw: str) -> time | str:
    """The time to the minute, or its error message."""
    value = raw.strip()
    if not value:
        return TIME_EMPTY
    match = _TIME.fullmatch(value)
    if match is None:
        return TIME_INVALID
    hour, minute, second = int(match[1]), int(match[2]), int(match[3] or 0)
    if hour > 23 or minute > 59 or second > 59:
        return TIME_INVALID
    return time(hour, minute)


def gap_message(local: datetime, zone_name: str) -> str:
    """The error for a local time the clocks skip in `zone_name`."""
    day = f"{local.day} {MONTHS[local.month - 1]} {local.year}"
    return (
        f"There is no {local:%H:%M} on {day} in {zone_name} because the clocks go forward."
        " Enter another time."
    )


def parse_start(raw_date: str, raw_time: str, zone: ZoneInfo) -> datetime | StartErrors:
    """The start in UTC, a whole minute, from the date and time as typed in `zone`; or the
    errors of both fields."""
    parsed_date = _parse_date(raw_date)
    parsed_time = _parse_time(raw_time)
    if isinstance(parsed_date, str) or isinstance(parsed_time, str):
        return StartErrors(
            parsed_date if isinstance(parsed_date, str) else None,
            parsed_time if isinstance(parsed_time, str) else None,
        )
    local = datetime.combine(parsed_date, parsed_time)
    aware = local.replace(tzinfo=zone, fold=0)
    try:
        moment = aware.astimezone(UTC)
        round_trip = moment.astimezone(zone).replace(tzinfo=None)
    except (OverflowError, ValueError):
        return StartErrors(DATE_INVALID, None)
    if round_trip != local:
        return StartErrors(None, gap_message(local, zone.key))
    return moment


def local_parts(moment: datetime, zone: ZoneInfo | None) -> tuple[str, str]:
    """`moment` in `zone` (UTC when `None`) as the edit form's values: `("2027-03-14",
    "10:00")`."""
    local = moment.astimezone(zone or UTC)
    return f"{local:%Y-%m-%d}", f"{local:%H:%M}"
