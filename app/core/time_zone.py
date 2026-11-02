"""The browser's time zone, and showing a stored time in it (specs/012.1-teacher-competitions
research R4, R10).

The zone lives in one browser cookie, `sc_time_zone`, holding an IANA name such as `Europe/Kyiv`.
It is written by the browser (`app/static/js/time-zone.js`), never by the server, so it is not
`HttpOnly`. The server reads it on every request and stores nothing: the cookie names a zone, not
a person, holds no identifier and is not linked to an account or a session, so it is not personal
data (the same reasoning as the theme cookie, `app.core.theme`). No log line ever names it.

Only a name in `zoneinfo.available_timezones()` is accepted, exactly as written; anything else
(missing, empty, unknown, a path, another case) means "no zone known", and times are then shown in
UTC with the label "UTC". Every stored time is UTC; this module only converts for display.
"""

import functools
import zoneinfo
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import Request

TIME_ZONE_COOKIE_NAME = "sc_time_zone"
TIME_ZONE_MAX_LENGTH = 64
UTC_ZONE = ZoneInfo("UTC")

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""The month names, written out here rather than taken from `%B`, which follows the process
locale."""


@functools.cache
def _known_zones() -> frozenset[str]:
    """The zone names the runtime's time-zone database knows; read once."""
    return frozenset(zoneinfo.available_timezones())


def parse_time_zone(value: str | None) -> ZoneInfo | None:
    """The zone `value` names, if it is a known name of 1–64 characters, exactly; `None`
    otherwise. Never raises."""
    if not isinstance(value, str) or not 0 < len(value) <= TIME_ZONE_MAX_LENGTH:
        return None
    if value not in _known_zones():
        return None
    return ZoneInfo(value)


def read_time_zone(request: Request) -> ZoneInfo | None:
    """The browser's zone, from its cookie; `None` when none is known. Never raises."""
    return parse_time_zone(request.cookies.get(TIME_ZONE_COOKIE_NAME))


def zone_name(zone: ZoneInfo | None) -> str:
    """The zone's IANA name, or `UTC` when no zone is known: the hint and hidden value of a
    form."""
    return zone.key if zone is not None else "UTC"


def format_local_time(moment: datetime, zone: ZoneInfo | None) -> str:
    """`moment` in `zone`: "14 March 2027, 10:00". With no zone, the UTC value labelled so:
    "14 March 2027, 08:00 UTC"."""
    assert moment.tzinfo is not None, "format_local_time needs an aware datetime"
    local = moment.astimezone(zone or UTC_ZONE)
    text = f"{local.day} {MONTHS[local.month - 1]} {local.year}, {local:%H:%M}"
    return text if zone is not None else f"{text} UTC"


def utc_iso(moment: datetime) -> str:
    """`moment` in UTC to the minute, for a `<time datetime>` attribute: `2027-03-14T08:00Z`."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")
