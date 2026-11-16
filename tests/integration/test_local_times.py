"""Times on the pages (specs/012.5-ukrainian-localisation US7, FR-035–FR-040; research R9).

One format per language: "14 March 2027, 10:00" and «14 березня 2027, 10:00». In the browser's
zone when it is known, with no label; in Kyiv time, labelled, when it is not. A form reads a time
with no known zone as Kyiv time. Every `<time datetime>` stays UTC. No page shows "UTC" or a
`2026-10-22` style date any more.

Every case runs on both engines.
"""

import re
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import utc_now
from app.core.time_zone import format_local_date
from app.main import app
from app.models import AccessLevel, Competition
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ClientAs,
    invite,
    invite_and_accept,
    make_competition,
    make_institution,
    make_subject,
    make_teacher,
)

OLENA = "olena@example.org"
START = datetime(2099, 3, 14, 8, 0, tzinfo=UTC)
"""10:00 in Kyiv (UTC+2 in March, before the clocks change)."""
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@pytest.fixture
def manager(client_as: ClientAs) -> tuple[TestClient, int]:
    """A teacher who manages competitions, and a subject with one competition."""
    school = make_institution(app.state.engine, "Kyiv Lyceum")
    make_teacher(
        app.state.engine,
        app.state.settings,
        email=OLENA,
        institutions={school: AccessLevel.WRITE},
        can_manage=True,
    )
    subject = make_subject(app.state.engine, "Physics")
    make_competition(app.state.engine, subject, "Spring round", starts_at=START)
    browser = client_as(OLENA)
    browser.cookies.delete("sc_time_zone")
    return browser, subject


def starts(body: str) -> list[tuple[str | None, str]]:
    return [
        (t.attrs.get("datetime"), t.text())
        for t in html.parse(body).find_all("time")
        if t.attrs.get("datetime", "").endswith("Z")
    ]


def visible(body: str) -> str:
    return html.text(body, "main")


@pytest.mark.parametrize(
    ("language", "shown"),
    [
        ("en", "14 March 2099, 10:00 (Kyiv time)"),
        ("uk", "14 березня 2099, 10:00 (за київським часом)"),
    ],
)
def test_with_no_known_zone_the_list_shows_kyiv_time_labelled(
    manager: tuple[TestClient, int], language: str, shown: str
) -> None:
    browser, subject = manager
    browser.cookies.set("sc_lang", language)
    body = browser.get(f"/teacher/competitions?subject={subject}").text
    assert starts(body) == [("2099-03-14T08:00Z", shown)]
    assert "UTC" not in visible(body)


def test_with_a_known_zone_there_is_no_label(manager: tuple[TestClient, int]) -> None:
    browser, subject = manager
    browser.cookies.set("sc_time_zone", "Europe/Kyiv")
    body = browser.get(f"/teacher/competitions?subject={subject}").text
    assert starts(body) == [("2099-03-14T08:00Z", "14 March 2099, 10:00")]


@pytest.mark.parametrize(
    ("language", "hint"),
    [("en", "Time zone: Europe/Kyiv"), ("uk", "Часовий пояс: Europe/Kyiv")],
)
def test_a_start_entered_with_no_known_zone_is_kyiv_time(
    manager: tuple[TestClient, int], language: str, hint: str
) -> None:
    browser, subject = manager
    browser.cookies.set("sc_lang", language)
    form = browser.get(f"/teacher/competitions/new?subject={subject}").text
    assert hint in visible(form)
    assert html.control(form, "time_zone")["value"] == "Europe/Kyiv"
    response = browser.post(
        "/teacher/competitions",
        data={
            "subject": str(subject),
            "status": "",
            "page": "1",
            "name": "Autumn round",
            "start_date": "2099-10-15",
            "start_time": "10:00",
            "time_zone": "Europe/Kyiv",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(app.state.engine) as session:
        stored = session.exec(select(Competition).where(Competition.name == "Autumn round")).one()
    assert stored.starts_at.astimezone(UTC) == datetime(2099, 10, 15, 7, 0, tzinfo=UTC)


def test_the_profile_the_invitation_and_the_teachers_tab(
    client: TestClient, client_as: ClientAs
) -> None:
    """The three milestone 8 times: the consent record, the invitation's expiry and the date of
    consent, all in the new formats; nothing reads "UTC" or `2026-10-22`."""
    school = make_institution(app.state.engine, "Kyiv Lyceum")
    token = invite(
        app.state.engine,
        app.state.settings,
        email="taras@example.org",
        institutions={school: AccessLevel.READ},
    )
    invitation = visible(client.get(f"/invitations/{token}").text)
    assert "(Kyiv time)." in invitation
    assert "UTC" not in invitation and not ISO_DATE.search(invitation)

    invite_and_accept(
        app.state.engine, app.state.settings, email=OLENA, institutions={school: AccessLevel.READ}
    )
    now = utc_now()
    profile = visible(client_as(OLENA).get("/profile").text)
    assert re.search(r"Accepted \d{1,2} [A-Z][a-z]+ \d{4}, \d{2}:\d{2} \(Kyiv time\)", profile)
    assert "UTC" not in profile and not ISO_DATE.search(profile)

    teachers = client_as(ADMIN_EMAIL).get("/admin/teachers").text
    dates = [
        (t.attrs.get("datetime"), t.text())
        for t in html.parse(teachers).find_all("time")
        if not t.attrs.get("datetime", "").endswith("Z")
    ]
    assert (dates[0][1]) == format_local_date(now, None)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", dates[0][0] or "")
    assert "UTC" not in visible(teachers)
