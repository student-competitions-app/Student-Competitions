"""The browser's time zone, and showing a stored time in it (specs/012.1-teacher-competitions
research R4, R10).

The zone lives in one browser cookie, `sc_time_zone`, holding an IANA name such as `Europe/Kyiv`.
It is written by the browser (`app/static/js/time-zone.js`), never by the server, so it is not
`HttpOnly`. The server reads it on every request and stores nothing: the cookie names a zone, not
a person, holds no identifier and is not linked to an account or a session, so it is not personal
data (the same reasoning as the theme cookie, `app.core.theme`). No log line ever names it.

Only a name in `zoneinfo.available_timezones()` is accepted, exactly as written; anything else
(missing, empty, unknown, a path, another case) means "no zone known", and times are then shown in
Kyiv time, labelled "(Kyiv time)" / «(за київським часом)» (milestone 12.5 research R9). Emails
always use Kyiv time, labelled. Every stored time is UTC; this module only converts for display.

The format is a catalogue message in each language: "14 March 2027, 10:00" and
«14 березня 2027, 10:00», the month named in the genitive in Ukrainian (`_p("genitive month",
…)`), never taken from `%B`, which follows the process locale.
"""

import functools
import zoneinfo
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import Request

from app.core.i18n import Text, _, _p

TIME_ZONE_COOKIE_NAME = "sc_time_zone"
TIME_ZONE_MAX_LENGTH = 64
UTC_ZONE = ZoneInfo("UTC")
KYIV = ZoneInfo("Europe/Kyiv")
"""Where times are shown when the browser's zone is not known, and in every email."""

MONTHS: tuple[Text, ...] = (
    _p("genitive month", "January"),
    _p("genitive month", "February"),
    _p("genitive month", "March"),
    _p("genitive month", "April"),
    _p("genitive month", "May"),
    _p("genitive month", "June"),
    _p("genitive month", "July"),
    _p("genitive month", "August"),
    _p("genitive month", "September"),
    _p("genitive month", "October"),
    _p("genitive month", "November"),
    _p("genitive month", "December"),
)
"""The month names as they stand after a day: «14 березня» in Ukrainian, "14 March" in English."""


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
    """The zone's IANA name, or `Europe/Kyiv` when no zone is known: the hint and hidden value of
    a form, so a time entered with no known zone is read as Kyiv time."""
    return zone.key if zone is not None else KYIV.key


def format_local_time(moment: datetime, zone: ZoneInfo | None) -> str:
    """`moment` in `zone`, in the current language: "14 March 2027, 10:00" / «14 березня 2027,
    10:00». With no zone, Kyiv time labelled so: "14 March 2027, 10:00 (Kyiv time)"."""
    assert moment.tzinfo is not None, "format_local_time needs an aware datetime"
    local = moment.astimezone(zone or KYIV)
    text = _(
        "%(day)d %(month)s %(year)d, %(time)s",
        day=local.day,
        month=MONTHS[local.month - 1],
        year=local.year,
        time=f"{local:%H:%M}",
    )
    if zone is None:
        text = _("%(moment)s (Kyiv time)", moment=text)
    return str(text)


def format_local_date(moment: datetime, zone: ZoneInfo | None) -> str:
    """The date of `moment` in `zone` (Kyiv when `None`), with no label: "15 October 2026" /
    «15 жовтня 2026»."""
    assert moment.tzinfo is not None, "format_local_date needs an aware datetime"
    local = moment.astimezone(zone or KYIV)
    return str(
        _(
            "%(day)d %(month)s %(year)d",
            day=local.day,
            month=MONTHS[local.month - 1],
            year=local.year,
        )
    )


def local_date_iso(moment: datetime, zone: ZoneInfo | None) -> str:
    """The date of `moment` in `zone` (Kyiv when `None`), for a `<time datetime>` attribute:
    `2026-10-15`."""
    return moment.astimezone(zone or KYIV).strftime("%Y-%m-%d")


def utc_iso(moment: datetime) -> str:
    """`moment` in UTC to the minute, for a `<time datetime>` attribute: `2027-03-14T08:00Z`."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")
