"""The Competitions tab, end to end through the test client.

See specs/012.1-teacher-competitions/spec.md US1–US9, contracts/http-routes.md and research R16.
Every case runs on both engines. The clock is fixed at 1 March 2027 09:00 UTC by patching
`app.services.competitions.utc_now`, and moved forward where a start must pass; no test waits.
The browser's zone is the `sc_time_zone` cookie, set by the test as `time-zone.js` would.

- the manager: a real teacher with **Can manage competitions**, in `Europe/Kyiv`;
- the reader: a real teacher without it;
- "Chemistry" and "Physics": active subjects, no competitions to start with.

The access sweep is built from the router's own route table, with real subject and competition
ids (the generic sweeps in `test_routes.py` and `test_teacher_access.py` leave this tab's
management routes out).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, select
from sqlmodel import Session

from app.core.sealing import seal
from app.main import app
from app.models import AccessLevel, Competition, Role
from app.routers.teacher_competitions import COMPETITION_NOTICE_PURPOSE
from app.services.subjects import set_subject_active
from app.services.teachers import get_teacher, update_teacher
from app.services.users import get_user_by_email
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    AUTO,
    STUDENT_EMAIL,
    ClientAs,
    make_competition,
    make_institution,
    make_subject,
    make_teacher,
)
from tests.integration.test_routes import ALL_ROUTES

MANAGER = "manager@example.org"
READER = "reader@example.org"
TAB = "/teacher/competitions"
KYIV = "Europe/Kyiv"
NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
MISSING = 999_999

SUBJECT_NOT_FOUND = (
    "Subject not found",
    "This subject does not exist, or it is deactivated and has no finished competitions.",
)
COMPETITION_NOT_FOUND = (
    "Competition not found",
    "This competition does not exist, or its subject is deactivated.",
)
CANCEL_CONSEQUENCE = (
    "The competition will be marked Cancelled and stays in the list. It cannot be edited, "
    "started or restored."
)
GAP = (
    "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward."
    " Enter another time."
)

ENTRY_ROUTES = (f"{TAB}/{{competition_id:int}}/questions", f"{TAB}/{{competition_id:int}}/teams")
"""A competition's questions and teams (milestone 12.2), swept in
`test_teacher_competition_entries.py` with their own order of checks."""
COMPETITION_ROUTES = sorted(
    (method, path)
    for path, methods, _ in ALL_ROUTES
    if path.startswith(TAB) and not path.startswith(ENTRY_ROUTES)
    for method in methods
    if method in ("GET", "POST")
)
MANAGE_ROUTES = [route for route in COMPETITION_ROUTES if route != ("GET", TAB)]


def lists(competition: int, query: str) -> list[tuple[str, str]]:
    """The menu entries every teacher gets on every row since milestone 12.2 (FR-001, FR-002):
    the competition's **Questions** and **Teams**, with the list's context."""
    return [
        ("Questions", f"{TAB}/{competition}/questions?{query}"),
        ("Teams", f"{TAB}/{competition}/teams?{query}"),
    ]


def at(day: int, hour: int = 10, minute: int = 0, month: int = 3) -> datetime:
    """A moment in 2027, UTC."""
    return datetime(2027, month, day, hour, minute, tzinfo=UTC)


@dataclass(frozen=True)
class Scene:
    engine: Engine
    manager: TestClient
    reader: TestClient
    chemistry: int
    physics: int
    clock: Callable[[timedelta], datetime]


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    """A controllable `utc_now` for the service; call it to advance, and it returns the new
    time."""
    now = [NOW]
    monkeypatch.setattr("app.services.competitions.utc_now", lambda: now[0])

    def advance(by: timedelta = timedelta(0)) -> datetime:
        now[0] += by
        return now[0]

    return advance


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs, clock: Callable[[timedelta], datetime]) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(
        engine,
        settings,
        email=MANAGER,
        institutions={institution: AccessLevel.READ},
        can_manage=True,
    )
    make_teacher(engine, settings, email=READER, institutions={institution: AccessLevel.WRITE})
    manager = client_as(MANAGER)
    manager.cookies.set("sc_time_zone", KYIV)
    return Scene(
        engine=engine,
        manager=manager,
        reader=client_as(READER),
        chemistry=make_subject(engine, "Chemistry"),
        physics=make_subject(engine, "Physics"),
        clock=clock,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

SNAPSHOT_TABLES = ("competitions", "subjects", "teacher_profiles")


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def stored(engine: Engine, competition_id: int) -> Competition:
    with Session(engine) as session:
        competition = session.get(Competition, competition_id)
        assert competition is not None
        return competition


def count(engine: Engine) -> int:
    with Session(engine) as session:
        return len(session.execute(select(Competition.id)).all())


def only_id(engine: Engine) -> int:
    with Session(engine) as session:
        (competition_id,) = session.execute(select(Competition.id)).scalars().all()
        return competition_id


class Row(NamedTuple):
    id: int
    name: str
    start: str
    datetime: str | None
    status: str
    menu: list[tuple[str, str]]
    """`(text, href)` of each menu entry; empty when the row has no menu."""
    menu_label: str | None
    """The menu button's accessible text, or `None` without a menu."""


def rows(body: str) -> list[Row]:
    found = []
    for tr in html.parse(body).find_all("tr"):
        if not tr.attrs.get("id", "").startswith("competition-"):
            continue
        cells = {c.attrs.get("data-label"): c for c in tr.find_all("td")}
        times = cells["Start"].find_all("time")
        menus = [d for d in tr.find_all("details") if "actions-menu" in d.classes()]
        found.append(
            Row(
                id=int(tr.attrs["id"].removeprefix("competition-")),
                name=cells["Name"].text(),
                start=cells["Start"].text(),
                datetime=times[0].attrs.get("datetime") if times else None,
                status=cells["Status"].text(),
                menu=[(a.text(), a.attrs["href"]) for m in menus for a in m.find_all("a")],
                menu_label=menus[0].find_all("summary")[0].text() if menus else None,
            )
        )
    return found


def names(body: str) -> list[str]:
    return [row.name for row in rows(body)]


def empty_state(body: str) -> tuple[str, str | None] | None:
    states = [d for d in html.parse(body).find_all("div") if "empty-state" in d.classes()]
    if not states:
        return None
    (state,) = states
    message = [p.text() for p in state.find_all("p") if "empty-state-message" in p.classes()]
    hint = [p.text() for p in state.find_all("p") if "empty-state-hint" in p.classes()]
    return message[0], hint[0] if hint else None


def success_notices(body: str) -> list[str]:
    return [text for role, text in html.notices(body) if role == "status"]


def add_button(body: str) -> list[tuple[str, str]]:
    return [
        (link.href, link.text)
        for link in html.content_links(body)
        if link.text == "Add competition"
    ]


def not_found(response: Any, page: tuple[str, str]) -> None:
    assert response.status_code == 404
    assert html.h1(response.text) == page[0]
    assert page[1] in response.text
    assert (TAB, "Back to the competitions") in html.link_pairs(response.text)
    current = [t for t in html.nav(response.text, "Teacher area") if t.attrs.get("aria-current")]
    assert [t.text for t in current] == ["Competitions"]


def denied(response: Any) -> None:
    assert response.status_code == 403
    assert "Your current role, Teacher, cannot open this page." in response.text


def refused(response: Any, question: str, reason: str, back: str) -> None:
    assert response.status_code == 409
    assert html.h1(response.text) == question
    assert reason in html.text(response.text, "main")
    pairs = html.link_pairs(response.text, "main")
    assert (back, "Back to competitions") in pairs
    assert (back, "Back to the competitions") in pairs


def create(
    browser: TestClient,
    subject: int | str,
    name: str = "Spring round",
    start_date: str = "2027-03-14",
    start_time: str = "10:00",
    time_zone: str = KYIV,
    status: str = "",
    page: str = "1",
) -> Any:
    data = {
        "subject": str(subject),
        "status": status,
        "page": page,
        "name": name,
        "start_date": start_date,
        "start_time": start_time,
        "time_zone": time_zone,
    }
    return browser.post(TAB, data=data, follow_redirects=False)


def edit(
    browser: TestClient,
    competition_id: int,
    subject: int | str,
    name: str = "Spring round",
    start_date: str = "2027-03-14",
    start_time: str = "10:00",
    time_zone: str = KYIV,
    status: str = "",
    page: str = "1",
) -> Any:
    data = {
        "subject": str(subject),
        "status": status,
        "page": page,
        "name": name,
        "start_date": start_date,
        "start_time": start_time,
        "time_zone": time_zone,
    }
    return browser.post(f"{TAB}/{competition_id}/edit", data=data, follow_redirects=False)


def cancel(
    browser: TestClient, competition_id: int, subject: int | str, status: str = "", page: str = "1"
) -> Any:
    data = {"subject": str(subject), "status": status, "page": page}
    return browser.post(f"{TAB}/{competition_id}/cancel", data=data, follow_redirects=False)


def follow(browser: TestClient, response: Any) -> str:
    assert response.status_code == 303, response.text
    return browser.get(response.headers["location"]).text


def address(response: Any) -> tuple[str, dict[str, list[str]], str]:
    """The redirect's path, its query (without the notice) and its anchor."""
    assert response.status_code == 303
    parts = urlsplit(response.headers["location"])
    query = parse_qs(parts.query)
    query.pop("notice", None)
    return parts.path, query, parts.fragment


def seed(engine: Engine, subject_id: int, days: range, **kwargs: Any) -> list[int]:
    """One competition per day of March 2027 at 12:00 UTC, "Day 01" …; their ids."""
    return [
        make_competition(engine, subject_id, f"Day {day:02}", starts_at=at(day, 12), **kwargs)
        for day in days
    ]


# ---------------------------------------------------------------------------------------------
# User story 1: a teacher creates a competition
# ---------------------------------------------------------------------------------------------


def test_the_tab_and_its_address(scene: Scene) -> None:
    """US1-1: the fourth tab, current here; the tab row unchanged."""
    body = scene.manager.get(TAB).text
    assert html.h1(body) == "Competitions"
    tabs = html.nav(body, "Teacher area")
    assert [(t.href, t.text) for t in tabs] == [
        ("/teacher/students", "Students"),
        ("/teacher/teams", "Teams"),
        ("/teacher/questions", "Questions"),
        (TAB, "Competitions"),
    ]
    assert [t.text for t in tabs if t.attrs.get("aria-current") == "page"] == ["Competitions"]
    assert empty_state(body) == (
        "Select a subject",
        "Choose a subject in the list above to see its competitions.",
    )


def test_add_competition_is_offered_for_an_active_subject_with_the_setting(scene: Scene) -> None:
    """US1-2, US2-9."""
    body = scene.manager.get(f"{TAB}?subject={scene.chemistry}").text
    assert add_button(body) == [(f"{TAB}/new?subject={scene.chemistry}", "Add competition")]
    assert empty_state(body) == (
        "No competitions yet",
        "Add the first competition with Add competition.",
    )
    other = scene.reader.get(f"{TAB}?subject={scene.chemistry}").text
    assert add_button(other) == []
    assert empty_state(other) == ("No competitions yet", None)


def test_the_add_form(scene: Scene) -> None:
    """US1-3: the title, the back link, the subject as text, the fields and the zone."""
    response = scene.manager.get(f"{TAB}/new?subject={scene.chemistry}&status=upcoming&page=2")
    assert response.status_code == 200
    body = response.text
    assert html.h1(body) == "Add competition"
    back = f"{TAB}?subject={scene.chemistry}&status=upcoming&page=2"
    assert (back, "Back to the competitions") in html.link_pairs(body)
    assert "Subject: Chemistry" in html.text(body, "main")
    (form,) = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == TAB
    assert {i.name: (i.type, i.value) for i in form.inputs} == {
        "subject": ("hidden", str(scene.chemistry)),
        "status": ("hidden", "upcoming"),
        "page": ("hidden", "2"),
        "name": ("text", ""),
        "start_date": ("date", ""),
        "start_time": ("time", ""),
        "time_zone": ("hidden", KYIV),
    }
    assert "Time zone: Europe/Kyiv" in html.text(body, "main")
    assert [b.text for b in form.buttons] == ["Save competition"]
    assert (back, "Cancel") in html.link_pairs(body, "main")
    assert html.control(body, "name").get("maxlength") == "200"


def test_creating_lands_at_the_competition_with_the_notice(scene: Scene) -> None:
    """US1-4, US1-5, US1-6: 14 March 2027 10:00 in Kyiv is stored as 08:00 UTC."""
    response = create(scene.manager, scene.chemistry, status="upcoming", page="3")
    competition = only_id(scene.engine)
    assert address(response) == (
        TAB,
        {"subject": [str(scene.chemistry)]},
        f"competition-{competition}",
    )
    assert "notice=" in response.headers["location"]
    body = follow(scene.manager, response)
    assert success_notices(body) == ["Competition “Spring round” was added"]
    assert rows(body) == [
        Row(
            competition,
            "Spring round",
            "14 March 2027, 10:00",
            "2027-03-14T08:00Z",
            "Upcoming",
            [
                ("Edit", f"{TAB}/{competition}/edit?subject={scene.chemistry}"),
                *lists(competition, f"subject={scene.chemistry}"),
                ("Cancel competition", f"{TAB}/{competition}/cancel?subject={scene.chemistry}"),
            ],
            "Actions for “Spring round”",
        )
    ]
    row = stored(scene.engine, competition)
    assert (row.name, row.starts_at, row.subject_id) == ("Spring round", at(14, 8), scene.chemistry)
    assert (row.cancelled_at, row.stopped_at) == (None, None)


def test_without_a_known_zone_times_are_utc(scene: Scene) -> None:
    """US1-7, US8-3: no cookie, so the form says UTC and the list shows UTC."""
    scene.manager.cookies.delete("sc_time_zone")
    body = scene.manager.get(f"{TAB}/new?subject={scene.chemistry}").text
    assert "Time zone: UTC" in html.text(body, "main")
    assert html.control(body, "time_zone")["value"] == "UTC"
    body = follow(scene.manager, create(scene.manager, scene.chemistry, time_zone="UTC"))
    assert [(r.start, r.datetime) for r in rows(body)] == [
        ("14 March 2027, 10:00 UTC", "2027-03-14T10:00Z")
    ]


def test_cancel_on_the_form_stores_nothing(scene: Scene) -> None:
    """US1-8: the Cancel link goes back where the teacher came from; nothing is sent."""
    body = scene.manager.get(f"{TAB}/new?subject={scene.chemistry}&page=2").text
    assert (f"{TAB}?subject={scene.chemistry}&page=2", "Cancel") in html.link_pairs(body, "main")
    assert count(scene.engine) == 0


def test_a_single_offered_subject_is_chosen(client_as: ClientAs, scene: Scene) -> None:
    with Session(scene.engine) as session:
        set_subject_active(session, scene.physics, False)
    body = scene.manager.get(TAB).text
    assert [o for o in html.options(body, "subject") if o.selected][0].text == "Chemistry"
    assert empty_state(body) == (
        "No competitions yet",
        "Add the first competition with Add competition.",
    )


def test_a_new_competition_lands_on_its_page(scene: Scene) -> None:
    """FR-025: among 26 competitions, the new one, third from last, lands on page 3."""
    seed(scene.engine, scene.chemistry, range(5, 30))
    response = create(scene.manager, scene.chemistry, "Early", "2027-03-04", "10:00")
    with Session(scene.engine) as session:
        competition = max(session.execute(select(Competition.id)).scalars())
    _, query, anchor = address(response)
    assert query == {"subject": [str(scene.chemistry)], "page": ["3"]}
    assert anchor == f"competition-{competition}"
    body = follow(scene.manager, response)
    assert names(body)[-1] == "Early"


@pytest.mark.parametrize(
    "token",
    ["tampered", "expired", "other-subject", "unknown-outcome", "not-a-token"],
)
def test_a_bad_notice_shows_nothing(scene: Scene, token: str) -> None:
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    other = make_competition(scene.engine, scene.physics, starts_at=at(14))
    key = app.state.settings.secret_key
    valid = seal(key, COMPETITION_NOTICE_PURPOSE, {"competition": competition, "outcome": "added"})
    value = {
        "tampered": valid[:-2] + ("AA" if not valid.endswith("AA") else "BB"),
        "expired": seal(
            key,
            COMPETITION_NOTICE_PURPOSE,
            {"competition": competition, "outcome": "added"},
            now=datetime.now(UTC) - timedelta(minutes=11),
        ),
        "other-subject": seal(
            key, COMPETITION_NOTICE_PURPOSE, {"competition": other, "outcome": "added"}
        ),
        "unknown-outcome": seal(
            key, COMPETITION_NOTICE_PURPOSE, {"competition": competition, "outcome": "won"}
        ),
        "not-a-token": "hello",
    }[token]
    body = scene.manager.get(f"{TAB}?subject={scene.chemistry}&notice={value}").text
    assert success_notices(body) == []
    assert names(body) == ["Spring round"]
    assert scene.manager.get(f"{TAB}?subject={scene.chemistry}&notice={valid}").status_code == 200
    assert success_notices(
        scene.manager.get(f"{TAB}?subject={scene.chemistry}&notice={valid}").text
    ) == ["Competition “Spring round” was added"]


def test_no_competition_name_reaches_an_address(scene: Scene) -> None:
    """FR-046: the redirects after a change carry ids and a sealed token only."""
    secret = "Secretname"
    response = create(scene.manager, scene.chemistry, secret)
    assert secret.casefold() not in response.headers["location"].casefold()
    competition = only_id(scene.engine)
    response = edit(scene.manager, competition, scene.chemistry, secret + " two")
    assert secret.casefold() not in response.headers["location"].casefold()
    response = cancel(scene.manager, competition, scene.chemistry)
    assert secret.casefold() not in response.headers["location"].casefold()


# ---------------------------------------------------------------------------------------------
# User story 2: the list of competitions
# ---------------------------------------------------------------------------------------------


def listed(scene: Scene, query: str = "", browser: TestClient | None = None) -> str:
    response = (browser or scene.manager).get(f"{TAB}?subject={scene.chemistry}{query}")
    assert response.status_code == 200
    return response.text


def test_the_table_columns(scene: Scene) -> None:
    """US2-1: name, start, status and actions; no creator is stored or shown."""
    make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    body = listed(scene)
    (table,) = html.parse(body).find_all("table")
    assert [th.text() for th in table.find_all("th")] == ["Name", "Start", "Status", "Actions"]
    assert MANAGER not in html.text(body, "main")


def test_latest_start_first_whatever_the_status(scene: Scene) -> None:
    """US2-2, US2-3."""
    make_competition(scene.engine, scene.chemistry, "Fifteenth", starts_at=at(15))
    make_competition(scene.engine, scene.chemistry, "First", starts_at=at(1, 7), stopped=True)
    make_competition(
        scene.engine, scene.chemistry, "Twenty-fifth", starts_at=at(25), cancelled=True
    )
    for name in ("beta", "Alpha", "apple"):
        make_competition(scene.engine, scene.chemistry, name, starts_at=at(20))
    assert names(listed(scene)) == [
        "Twenty-fifth",
        "Alpha",
        "apple",
        "beta",
        "Fifteenth",
        "First",
    ]
    assert [r.status for r in rows(listed(scene))] == [
        "Cancelled",
        "Upcoming",
        "Upcoming",
        "Upcoming",
        "Upcoming",
        "Finished",
    ]


def test_pages_of_ten_with_navigation_above_and_below(scene: Scene) -> None:
    """US2-4, US2-5."""
    seed(scene.engine, scene.chemistry, range(2, 27))
    body = listed(scene, "&page=2")
    assert len(rows(body)) == 10
    href = f"{TAB}?subject={scene.chemistry}&page="
    for label in ("Pages, top", "Pages, bottom"):
        found = html.pagination(body, label)
        assert found is not None
        range_text, entries = found
        assert range_text == "Competitions 11–20 of 25"
        assert [(e.text, e.href) for e in entries if e.text in ("Previous", "Next")] == [
            ("Previous", f"{href}1"),
            ("Next", f"{href}3"),
        ]
        assert [e.text for e in entries if e.current] == ["2"]
    assert names(listed(scene, "&page=99"))[-1] == "Day 02"


def test_the_status_list(scene: Scene) -> None:
    """US2-6: five options, All by default; the form keeps the subject and drops the page."""
    make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    body = listed(scene, "&page=2")
    assert [(o.value, o.text, o.selected) for o in html.options(body, "status")] == [
        ("", "All", True),
        ("upcoming", "Upcoming", False),
        ("in_progress", "In progress", False),
        ("finished", "Finished", False),
        ("cancelled", "Cancelled", False),
    ]
    subject_form, status_form = [f for f in html.forms(body, "main") if f.method == "get"]
    assert subject_form.action == status_form.action == TAB
    assert [(i.name, i.type) for i in subject_form.inputs] == [("subject", "select")]
    assert [(i.name, i.type, i.value) for i in status_form.inputs] == [
        ("subject", "hidden", str(scene.chemistry)),
        ("status", "select", ""),
    ]
    for form in (subject_form, status_form):
        assert [b.text for b in form.buttons] == ["Show"]
    assert body.count("<noscript>") == 2


def test_each_status_shows_only_its_competitions(scene: Scene) -> None:
    """US2-7, with the clock moved so one has started."""
    make_competition(scene.engine, scene.chemistry, "Upcoming one", starts_at=at(20))
    make_competition(scene.engine, scene.chemistry, "Running one", starts_at=at(1, 10))
    make_competition(
        scene.engine, scene.chemistry, "Finished one", starts_at=at(1, 7), stopped=True
    )
    make_competition(
        scene.engine, scene.chemistry, "Cancelled one", starts_at=at(10), cancelled=True
    )
    scene.clock(timedelta(hours=2))
    expected = {
        "upcoming": (["Upcoming one"], "Upcoming"),
        "in_progress": (["Running one"], "In progress"),
        "finished": (["Finished one"], "Finished"),
        "cancelled": (["Cancelled one"], "Cancelled"),
    }
    for value, (listed_names, badge) in expected.items():
        body = listed(scene, f"&status={value}")
        assert names(body) == listed_names
        assert [r.status for r in rows(body)] == [badge]
        assert [o.value for o in html.options(body, "status") if o.selected] == [value]
    assert len(rows(listed(scene))) == 4


def test_the_status_is_kept_across_pages(scene: Scene) -> None:
    """US2-8, US2-10: the address holds subject, status and page, and a reload restores them."""
    seed(scene.engine, scene.chemistry, range(2, 27))
    body = listed(scene, "&status=upcoming&page=2")
    found = html.pagination(body, "Pages, top")
    assert found is not None
    hrefs = {e.text: e.href for e in found[1]}
    assert hrefs["Next"] == f"{TAB}?subject={scene.chemistry}&status=upcoming&page=3"
    assert [e.text for e in found[1] if e.current] == ["2"]
    assert [o.value for o in html.options(body, "subject") if o.selected] == [str(scene.chemistry)]
    assert [o.value for o in html.options(body, "status") if o.selected] == ["upcoming"]
    menu = rows(body)[0].menu
    assert menu[0][1].endswith(f"/edit?subject={scene.chemistry}&status=upcoming&page=2")


def test_no_competitions_with_this_status(scene: Scene) -> None:
    """US2-11."""
    make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    body = listed(scene, "&status=cancelled")
    assert empty_state(body) == (
        "No competitions with this status",
        "Choose another status, or All.",
    )
    assert html.pagination(body, "Pages, top") is None
    assert rows(body) == []


def test_no_subjects_yet(scene: Scene) -> None:
    """US2-12: nothing offered; the list is disabled."""
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
        set_subject_active(session, scene.physics, False)
    body = scene.manager.get(TAB).text
    assert empty_state(body) == ("No subjects yet", "Ask an administrator to add a subject.")
    assert "disabled" in html.control(body, "subject")
    assert add_button(body) == []


def test_without_the_setting_no_add_and_read_only_menus(scene: Scene) -> None:
    """US2-9, US2-13. Replaced by milestone 12.2 FR-002 (SC-009): a teacher without the setting
    no longer gets rows with no menu, but a menu with only **Questions** and **Teams**."""
    spring = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    running = make_competition(scene.engine, scene.chemistry, "Running", starts_at=at(1, 8))
    body = listed(scene, browser=scene.reader)
    assert add_button(body) == []
    query = f"subject={scene.chemistry}"
    assert [(r.name, r.menu, r.menu_label) for r in rows(body)] == [
        ("Spring round", lists(spring, query), "Actions for “Spring round”"),
        ("Running", lists(running, query), "Actions for “Running”"),
    ]
    assert len(rows(listed(scene))[0].menu) == 4


def test_an_unknown_status_reads_as_all(scene: Scene) -> None:
    make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    for value in ("bogus", "Upcoming", "%00"):
        body = listed(scene, f"&status={value}")
        assert names(body) == ["Spring round"]
        assert [o.text for o in html.options(body, "status") if o.selected] == ["All"]


@pytest.mark.parametrize("value", ["abc", str(MISSING), "9" * 40, "-1", "1e9999"])
def test_an_unknown_subject_is_not_found(scene: Scene, value: str) -> None:
    not_found(scene.manager.get(f"{TAB}?subject={value}"), SUBJECT_NOT_FOUND)
    not_found(scene.reader.get(f"{TAB}?subject={value}"), SUBJECT_NOT_FOUND)


def test_an_empty_subject_is_none_chosen(scene: Scene) -> None:
    body = scene.manager.get(f"{TAB}?subject=&status=upcoming").text
    assert empty_state(body) == (
        "Select a subject",
        "Choose a subject in the list above to see its competitions.",
    )
    with pytest.raises(AssertionError):
        html.options(body, "status")


def test_opening_the_list_changes_nothing(scene: Scene) -> None:
    make_competition(scene.engine, scene.chemistry, starts_at=at(1, 10))
    scene.clock(timedelta(hours=1))
    before = snapshot(scene.engine)
    listed(scene)
    listed(scene, browser=scene.reader)
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 3: a teacher edits an upcoming competition
# ---------------------------------------------------------------------------------------------


def test_the_menu_of_an_upcoming_competition(scene: Scene) -> None:
    """US3-1: the Actions button, announced with the name, and Edit."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    (row,) = rows(listed(scene, "&page=1"))
    assert row.menu_label == "Actions for “Spring round”"
    assert row.menu[0] == ("Edit", f"{TAB}/{competition}/edit?subject={scene.chemistry}")
    (details,) = [
        d for d in html.parse(listed(scene)).find_all("details") if "actions-menu" in d.classes()
    ]
    assert details.attrs.get("name") == "row-actions"


def test_the_edit_form(scene: Scene) -> None:
    """US3-2: the title, the stored name, the start in the browser's zone, the subject as
    text."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14, 8))
    url = f"{TAB}/{competition}/edit?subject={scene.chemistry}&status=upcoming&page=2"
    body = scene.manager.get(url).text
    assert html.h1(body) == "Edit competition “Spring round”"
    assert "Subject: Chemistry" in html.text(body, "main")
    back = f"{TAB}?subject={scene.chemistry}&status=upcoming&page=2#competition-{competition}"
    assert (back, "Back to the competitions") in html.link_pairs(body)
    assert (back, "Cancel") in html.link_pairs(body, "main")
    (form,) = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == f"{TAB}/{competition}/edit"
    assert {i.name: i.value for i in form.inputs} == {
        "subject": str(scene.chemistry),
        "status": "upcoming",
        "page": "2",
        "name": "Spring round",
        "start_date": "2027-03-14",
        "start_time": "10:00",
        "time_zone": KYIV,
    }
    scene.manager.cookies.delete("sc_time_zone")
    body = scene.manager.get(url).text
    assert html.control(body, "start_time")["value"] == "08:00"
    assert "Time zone: UTC" in html.text(body, "main")


def test_saving_lands_on_the_page_that_now_holds_it(scene: Scene) -> None:
    """US3-3: renamed and moved from page 1 to page 2, at it, with the notice, same status."""
    seed(scene.engine, scene.chemistry, range(5, 25))
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(28))
    assert rows(listed(scene, "&status=upcoming"))[0].id == competition
    response = edit(
        scene.manager,
        competition,
        scene.chemistry,
        "Spring final",
        "2027-03-06",
        "09:30",
        status="upcoming",
    )
    assert address(response) == (
        TAB,
        {"subject": [str(scene.chemistry)], "status": ["upcoming"], "page": ["2"]},
        f"competition-{competition}",
    )
    body = follow(scene.manager, response)
    assert success_notices(body) == ["Competition “Spring final” was saved"]
    assert competition in [r.id for r in rows(body)]
    row = stored(scene.engine, competition)
    assert (row.name, row.starts_at, row.updated_at) == ("Spring final", at(6, 7, 30), NOW)


def test_its_own_name_and_a_change_of_case(scene: Scene) -> None:
    """US3-4."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14, 8))
    assert (
        edit(
            scene.manager, competition, scene.chemistry, "Spring round", start_time="11:00"
        ).status_code
        == 303
    )
    assert (
        edit(
            scene.manager, competition, scene.chemistry, "SPRING round", start_time="11:00"
        ).status_code
        == 303
    )
    assert stored(scene.engine, competition).name == "SPRING round"


def test_an_unchanged_save_writes_nothing(scene: Scene) -> None:
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14, 8))
    before = snapshot(scene.engine)
    scene.clock(timedelta(minutes=5))
    response = edit(scene.manager, competition, scene.chemistry)
    assert response.status_code == 303
    assert snapshot(scene.engine) == before


def test_another_subject_in_the_edit_form_is_not_found(scene: Scene) -> None:
    """US3-5, FR-001: a competition never changes subject."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    before = snapshot(scene.engine)
    not_found(
        scene.manager.get(f"{TAB}/{competition}/edit?subject={scene.physics}"),
        COMPETITION_NOT_FOUND,
    )
    not_found(edit(scene.manager, competition, scene.physics, "Moved"), COMPETITION_NOT_FOUND)
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 4: names, dates and times are validated
# ---------------------------------------------------------------------------------------------


@pytest.fixture(params=["create", "edit"])
def submit(request: pytest.FixtureRequest, scene: Scene) -> Callable[..., Any]:
    """Send the create form, or the edit form of an upcoming competition "Existing" of
    Chemistry (14 April 2027 10:00 UTC), with the given fields."""
    if request.param == "create":
        return lambda **fields: create(scene.manager, scene.chemistry, **fields)
    competition = make_competition(
        scene.engine, scene.chemistry, "Existing", starts_at=at(14, month=4)
    )
    return lambda **fields: edit(scene.manager, competition, scene.chemistry, **fields)


def assert_invalid(
    scene: Scene, response: Any, field: str, message: str, values: dict[str, str], before: Any
) -> None:
    assert response.status_code == 400
    body = response.text
    assert html.field_error(body, field) == message
    summary = html.error_summary(body)
    assert summary is not None and summary.heading == "There is a problem"
    assert (f"#{field}", message) in summary.items
    for name, value in values.items():
        assert html.control(body, name).get("value") == value, name
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "Enter a name."),
        ("   ", "Enter a name."),
        ("x" * 201, "The name can be at most 200 characters."),
        ("Spring\tround", "The name cannot contain tabs, line breaks or other control characters."),
        ("Spring\nround", "The name cannot contain tabs, line breaks or other control characters."),
    ],
)
def test_invalid_names(scene: Scene, submit: Callable[..., Any], name: str, message: str) -> None:
    """US4-1 to US4-4."""
    before = snapshot(scene.engine)
    response = submit(name=name, start_date="2027-03-20", start_time="12:30")
    values = {"start_date": "2027-03-20", "start_time": "12:30", "time_zone": KYIV}
    if "\n" not in name:
        values["name"] = name
    assert_invalid(scene, response, "name", message, values, before)


def test_a_name_is_stored_trimmed(scene: Scene, submit: Callable[..., Any]) -> None:
    """US4-5."""
    assert submit(name="  Spring round  ").status_code == 303
    with Session(scene.engine) as session:
        assert "Spring round" in session.execute(select(Competition.name)).scalars().all()


def test_a_live_name_is_taken_ignoring_case(scene: Scene, submit: Callable[..., Any]) -> None:
    """US4-6."""
    make_competition(scene.engine, scene.chemistry, "Spring round", starts_at=at(1, 8))
    before = snapshot(scene.engine)
    response = submit(name=" spring ROUND ")
    assert_invalid(
        scene,
        response,
        "name",
        "A competition named “spring ROUND” already exists in this subject.",
        {"name": " spring ROUND "},
        before,
    )


@pytest.mark.parametrize("other", ["cancelled", "finished", "other-subject"])
def test_a_free_name_is_accepted(scene: Scene, submit: Callable[..., Any], other: str) -> None:
    """US4-7."""
    if other == "other-subject":
        make_competition(scene.engine, scene.physics, "Spring round", starts_at=at(20))
    else:
        make_competition(
            scene.engine,
            scene.chemistry,
            "Spring round",
            starts_at=at(1, 7),
            cancelled=other == "cancelled",
            stopped=other == "finished",
        )
    assert submit(name="Spring round").status_code == 303


@pytest.mark.parametrize(
    ("start_date", "start_time", "field", "message"),
    [
        ("", "10:00", "start_date", "Enter the start date."),
        ("2027-02-30", "10:00", "start_date", "Enter a real start date."),
        ("14.03.2027", "10:00", "start_date", "Enter a real start date."),
        ("2027-03-14", "", "start_time", "Enter the start time."),
        ("2027-03-14", "24:00", "start_time", "Enter a real start time."),
        ("2027-03-14", "ab:cd", "start_time", "Enter a real start time."),
        ("2027-03-01", "11:00", "start_date", "The start must be in the future."),
        ("2027-02-28", "10:00", "start_date", "The start must be in the future."),
        ("2027-03-28", "03:30", "start_time", GAP),
    ],
)
def test_invalid_starts(
    scene: Scene,
    submit: Callable[..., Any],
    start_date: str,
    start_time: str,
    field: str,
    message: str,
) -> None:
    """US4-8 to US4-10: the current minute (11:00 in Kyiv) is not in the future."""
    before = snapshot(scene.engine)
    response = submit(name="Spring final", start_date=start_date, start_time=start_time)
    values = {"name": "Spring final", "start_date": start_date, "start_time": start_time}
    assert_invalid(scene, response, field, message, values, before)


def test_both_start_errors_and_a_name_error_at_once(
    scene: Scene, submit: Callable[..., Any]
) -> None:
    response = submit(name="", start_date="", start_time="99:99")
    assert response.status_code == 400
    summary = html.error_summary(response.text)
    assert summary is not None
    assert [href for href, _ in summary.items] == ["#name", "#start_date", "#start_time"]


def test_a_time_that_happens_twice_is_the_earlier(scene: Scene, submit: Callable[..., Any]) -> None:
    """FR-023: 31 October 2027 03:30 in Kyiv is stored as 00:30 UTC."""
    assert submit(name="Autumn", start_date="2027-10-31", start_time="03:30").status_code == 303
    assert saved_start(scene, "Autumn") == datetime(2027, 10, 31, 0, 30, tzinfo=UTC)


def saved_start(scene: Scene, name: str) -> datetime:
    with Session(scene.engine) as session:
        statement = select(Competition.starts_at).where(Competition.name == name)
        return session.execute(statement).scalar_one().astimezone(UTC)


def test_the_form_is_read_in_the_zone_it_was_shown_in(
    scene: Scene, submit: Callable[..., Any]
) -> None:
    """FR-022: the cookie changed to UTC after the form was shown in Kyiv; the hidden field
    wins. An unknown zone is UTC."""
    scene.manager.cookies.set("sc_time_zone", "UTC")
    response = submit(name="Kyiv", start_date="2027-03-20", start_time="12:00", time_zone=KYIV)
    assert response.status_code == 303
    assert saved_start(scene, "Kyiv") == at(20, 10)
    response = submit(
        name="Mars", start_date="2027-03-21", start_time="12:00", time_zone="Mars/Base"
    )
    assert response.status_code == 303
    assert saved_start(scene, "Mars") == at(21, 12)


def test_an_unknown_zone_shows_utc_again(scene: Scene) -> None:
    response = create(scene.manager, scene.chemistry, name="", time_zone="Mars/Base")
    assert response.status_code == 400
    assert html.control(response.text, "time_zone")["value"] == "UTC"
    assert "Time zone: UTC" in html.text(response.text, "main")


# ---------------------------------------------------------------------------------------------
# User story 5: a teacher cancels a competition
# ---------------------------------------------------------------------------------------------


def test_the_cancel_confirmation(scene: Scene) -> None:
    """US5-1: the question names the competition, the subject and the start in the browser's
    zone; the destructive button and Keep competition."""
    competition = make_competition(
        scene.engine, scene.chemistry, "Spring final", starts_at=at(2, 7, 30, month=4)
    )
    url = f"{TAB}/{competition}/cancel?subject={scene.chemistry}&status=upcoming&page=2"
    body = scene.manager.get(url).text
    assert (
        html.h1(body)
        == "Cancel competition “Spring final” of Chemistry, starting 2 April 2027, 10:30?"
    )
    (heading,) = html.parse(body).find_all("h1")
    assert [t.attrs.get("datetime") for t in heading.find_all("time")] == ["2027-04-02T07:30Z"]
    assert "<title>Cancel competition “Spring final” — " in body
    assert CANCEL_CONSEQUENCE in html.text(body, "main")
    back = f"{TAB}?subject={scene.chemistry}&status=upcoming&page=2#competition-{competition}"
    assert (back, "Keep competition") in html.link_pairs(body, "main")
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")
    (form,) = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == f"{TAB}/{competition}/cancel"
    assert [b.text for b in form.buttons] == ["Cancel competition"]
    assert "destructive" in form.buttons[0].attrs.get("class", "")
    assert {i.name: i.value for i in form.inputs} == {
        "subject": str(scene.chemistry),
        "status": "upcoming",
        "page": "2",
    }


def test_keep_competition_changes_nothing(scene: Scene) -> None:
    """US5-2: opening the confirmation and following its link back writes nothing."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    before = snapshot(scene.engine)
    body = scene.manager.get(f"{TAB}/{competition}/cancel?subject={scene.chemistry}").text
    (keep,) = [href for href, text in html.link_pairs(body, "main") if text == "Keep competition"]
    assert scene.manager.get(keep).status_code == 200
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("start", ["upcoming", "in_progress"])
def test_cancelling_lands_at_it_with_the_notice(scene: Scene, start: str) -> None:
    """US5-3, US5-4."""
    starts_at = at(14) if start == "upcoming" else at(1, 8)
    competition = make_competition(
        scene.engine, scene.chemistry, "Spring final", starts_at=starts_at
    )
    response = cancel(scene.manager, competition, scene.chemistry)
    assert address(response) == (
        TAB,
        {"subject": [str(scene.chemistry)]},
        f"competition-{competition}",
    )
    body = follow(scene.manager, response)
    assert success_notices(body) == ["Competition “Spring final” was cancelled"]
    (row,) = rows(body)
    # Replaced by milestone 12.2 FR-002 (SC-009): a cancelled row keeps a read-only menu.
    assert (row.status, row.menu, row.menu_label) == (
        "Cancelled",
        lists(competition, f"subject={scene.chemistry}"),
        "Actions for “Spring final”",
    )
    assert stored(scene.engine, competition).cancelled_at == NOW


def test_cancelling_under_a_filter_that_hides_it(scene: Scene) -> None:
    """US5-5: the row that took its place, the row before it, the previous page, the empty
    state."""
    ids = seed(scene.engine, scene.chemistry, range(2, 13))  # listed Day 12 … Day 02
    upcoming = "upcoming"

    def landing_of(competition: int, page: str = "1") -> tuple[dict[str, list[str]], str]:
        _, query, anchor = address(
            cancel(scene.manager, competition, scene.chemistry, upcoming, page)
        )
        return query, anchor

    base = {"subject": [str(scene.chemistry)], "status": [upcoming]}
    assert landing_of(ids[5]) == (base, f"competition-{ids[4]}")
    assert landing_of(ids[0], "2") == (base, f"competition-{ids[1]}")
    for competition in ids[2:5] + ids[6:]:
        cancel(scene.manager, competition, scene.chemistry)
    assert landing_of(ids[1]) == (base, "")
    body = scene.manager.get(f"{TAB}?subject={scene.chemistry}&status=upcoming").text
    assert empty_state(body) == (
        "No competitions with this status",
        "Choose another status, or All.",
    )


def test_cancelling_the_only_row_of_the_last_page(scene: Scene) -> None:
    """FR-034: the page empties, so the list lands on the previous page at its last row."""
    ids = seed(scene.engine, scene.chemistry, range(2, 13))
    response = cancel(scene.manager, ids[0], scene.chemistry, "upcoming", "2")
    _, query, anchor = address(response)
    assert "page" not in query
    assert anchor == f"competition-{ids[1]}"


def test_a_start_passing_while_the_confirmation_is_open(scene: Scene) -> None:
    """US5-6: an upcoming competition whose start passed meanwhile is still cancelled, and stays
    Cancelled."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(1, 10))
    assert (
        scene.manager.get(f"{TAB}/{competition}/cancel?subject={scene.chemistry}").status_code
        == 200
    )
    scene.clock(timedelta(hours=2))
    assert cancel(scene.manager, competition, scene.chemistry).status_code == 303
    scene.clock(timedelta(days=30))
    assert [r.status for r in rows(listed(scene))] == ["Cancelled"]


def test_a_cancelled_competition_cannot_be_cancelled_again(scene: Scene) -> None:
    """US5-7: opening or sending the cancel again is refused; nothing changes."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    assert cancel(scene.manager, competition, scene.chemistry).status_code == 303
    before = snapshot(scene.engine)
    back = f"{TAB}?subject={scene.chemistry}#competition-{competition}"
    question, reason = "Cancel competition “Spring round”?", "“Spring round” is already cancelled."
    refused(
        scene.manager.get(f"{TAB}/{competition}/cancel?subject={scene.chemistry}"),
        question,
        reason,
        back,
    )
    refused(cancel(scene.manager, competition, scene.chemistry), question, reason, back)
    assert snapshot(scene.engine) == before


def test_a_finished_competition_cannot_be_cancelled(scene: Scene) -> None:
    """US5-8."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(1, 7), stopped=True)
    before = snapshot(scene.engine)
    back = f"{TAB}?subject={scene.chemistry}&status=finished#competition-{competition}"
    question = "Cancel competition “Spring round”?"
    reason = "“Spring round” has finished and cannot be cancelled."
    url = f"{TAB}/{competition}/cancel?subject={scene.chemistry}&status=finished"
    refused(scene.manager.get(url), question, reason, back)
    refused(cancel(scene.manager, competition, scene.chemistry, "finished"), question, reason, back)
    assert snapshot(scene.engine) == before


def test_a_cancelled_name_is_free_again(scene: Scene) -> None:
    """US5-9, US5-10."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    cancel(scene.manager, competition, scene.chemistry)
    assert create(scene.manager, scene.chemistry, "Spring round").status_code == 303
    body = listed(scene, "&status=cancelled")
    # Replaced by milestone 12.2 FR-002 (SC-009): a cancelled row keeps a read-only menu.
    query = f"subject={scene.chemistry}&status=cancelled"
    assert [(r.id, r.status, r.menu) for r in rows(body)] == [
        (competition, "Cancelled", lists(competition, query))
    ]


# ---------------------------------------------------------------------------------------------
# User story 6: a competition starts on its own
# ---------------------------------------------------------------------------------------------


def test_a_started_competition_is_in_progress(scene: Scene) -> None:
    """US6-1, US6-2: nothing is written when the start passes; the menu offers no Edit, only the
    competition's lists (milestone 12.2) and Cancel competition."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(1, 10))
    before = snapshot(scene.engine)
    scene.clock(timedelta(hours=1))
    (row,) = rows(listed(scene))
    assert row.status == "In progress"
    assert row.menu == [
        *lists(competition, f"subject={scene.chemistry}"),
        ("Cancel competition", f"{TAB}/{competition}/cancel?subject={scene.chemistry}"),
    ]
    assert [r.id for r in rows(listed(scene, "&status=in_progress"))] == [competition]
    assert rows(listed(scene, "&status=upcoming")) == []
    assert snapshot(scene.engine) == before


def test_a_started_competition_cannot_be_edited(scene: Scene) -> None:
    """US6-3: the form opened before the start and sent after it."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(1, 10))
    assert (
        scene.manager.get(f"{TAB}/{competition}/edit?subject={scene.chemistry}").status_code == 200
    )
    scene.clock(timedelta(hours=1))
    before = snapshot(scene.engine)
    question = "Edit competition “Spring round”?"
    reason = "“Spring round” has already started and can no longer be edited."
    back = f"{TAB}?subject={scene.chemistry}#competition-{competition}"
    refused(
        scene.manager.get(f"{TAB}/{competition}/edit?subject={scene.chemistry}"),
        question,
        reason,
        back,
    )
    refused(
        edit(scene.manager, competition, scene.chemistry, "Late", "2027-03-20"),
        question,
        reason,
        back,
    )
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    ("end", "reason"),
    [
        ("cancelled", "“Spring round” has been cancelled and can no longer be edited."),
        ("stopped", "“Spring round” has finished and can no longer be edited."),
    ],
)
def test_cancelled_and_finished_competitions_cannot_be_edited(
    scene: Scene, end: str, reason: str
) -> None:
    """US6-4."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14), **{end: True})
    (row,) = rows(listed(scene))
    # Replaced by milestone 12.2 FR-002 (SC-009): no Edit, but a read-only menu.
    assert (row.menu, row.menu_label) == (
        lists(competition, f"subject={scene.chemistry}"),
        "Actions for “Spring round”",
    )
    before = snapshot(scene.engine)
    back = f"{TAB}?subject={scene.chemistry}#competition-{competition}"
    url = f"{TAB}/{competition}/edit?subject={scene.chemistry}"
    refused(scene.manager.get(url), "Edit competition “Spring round”?", reason, back)
    refused(
        edit(scene.manager, competition, scene.chemistry, "New"),
        "Edit competition “Spring round”?",
        reason,
        back,
    )
    assert snapshot(scene.engine) == before


def test_an_edit_sent_after_another_teacher_cancelled(scene: Scene) -> None:
    """Spec Edge Cases: the edit form opened while upcoming, the competition cancelled by
    another teacher before the save."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    assert (
        scene.manager.get(f"{TAB}/{competition}/edit?subject={scene.chemistry}").status_code == 200
    )
    assert cancel(scene.manager, competition, scene.chemistry).status_code == 303
    before = snapshot(scene.engine)
    refused(
        edit(scene.manager, competition, scene.chemistry, "Late"),
        "Edit competition “Spring round”?",
        "“Spring round” has been cancelled and can no longer be edited.",
        f"{TAB}?subject={scene.chemistry}#competition-{competition}",
    )
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 7: only teachers see competitions, and only managers change them
# ---------------------------------------------------------------------------------------------


def concrete(path: str, competition_id: int | str, subject_id: int | str) -> str:
    """The route's address with real ids; a page shown by `GET` carries the subject."""
    return re.sub(r"\{competition_id:int\}", str(competition_id), path) + f"?subject={subject_id}"


def form_for(subject_id: int | str) -> dict[str, str]:
    return {
        "subject": str(subject_id),
        "status": "",
        "page": "1",
        "name": "Hacked",
        "start_date": "2027-05-01",
        "start_time": "10:00",
        "time_zone": KYIV,
    }


def send(browser: TestClient, method: str, url: str, subject_id: int | str, **kw: Any) -> Any:
    if method == "POST":
        return browser.post(
            url.split("?")[0], data=form_for(subject_id), follow_redirects=False, **kw
        )
    return browser.get(url, follow_redirects=False, **kw)


def test_the_sweep_has_every_route() -> None:
    assert len(COMPETITION_ROUTES) == 7
    assert len(MANAGE_ROUTES) == 6


@pytest.mark.parametrize(("method", "path"), COMPETITION_ROUTES)
def test_other_roles_are_refused(
    scene: Scene, client: TestClient, client_as: ClientAs, method: str, path: str
) -> None:
    """US7-1, FR-040: administrators and students get "access denied" naming their role, and
    nothing changes; anonymous visitors are sent to sign in."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    url = concrete(path, competition, scene.chemistry)
    before = snapshot(scene.engine)
    for email, role, label in (
        (ADMIN_EMAIL, AUTO, "Administrator"),
        (STUDENT_EMAIL, AUTO, "Student"),
        (ADMIN_STUDENT_EMAIL, Role.STUDENT, "Student"),
    ):
        response = send(client_as(email, role), method, url, scene.chemistry)
        assert response.status_code == 403, (email, method, url)
        assert f"Your current role, {label}, cannot open this page." in response.text
    anonymous = send(client, method, url, scene.chemistry)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"].split("?")[0] == "/login"
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), MANAGE_ROUTES)
@pytest.mark.parametrize("target", ["listed", "missing", "unknown-subject", "hidden"])
def test_a_teacher_without_the_setting_is_refused_before_anything_is_looked_up(
    scene: Scene, method: str, path: str, target: str
) -> None:
    """US7-2, FR-042: 403 whether the ids exist or not; nothing changes."""
    listed_id = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    hidden_subject = make_subject(scene.engine, "Biology")
    hidden = make_competition(scene.engine, hidden_subject, starts_at=at(14))
    with Session(scene.engine) as session:
        set_subject_active(session, hidden_subject, False)
    competition, subject = {
        "listed": (listed_id, scene.chemistry),
        "missing": (MISSING, scene.chemistry),
        "unknown-subject": (listed_id, "abc"),
        "hidden": (hidden, hidden_subject),
    }[target]
    url = concrete(path, competition, subject)
    before = snapshot(scene.engine)
    denied(send(scene.reader, method, url, subject))
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), COMPETITION_ROUTES)
def test_a_teacher_with_the_setting_is_admitted(scene: Scene, method: str, path: str) -> None:
    """SC-002: every route, with real ids."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    response = send(
        scene.manager, method, concrete(path, competition, scene.chemistry), scene.chemistry
    )
    assert response.status_code in (200, 303), (method, path, response.status_code)


@pytest.mark.parametrize(("method", "path"), MANAGE_ROUTES)
@pytest.mark.parametrize("subject", ["abc", "", str(MISSING), "9" * 40, "hidden"])
def test_an_unknown_subject_is_not_found_for_a_manager(
    scene: Scene, method: str, path: str, subject: str
) -> None:
    """US7-4: before the competition and its status are looked at."""
    hidden_subject = make_subject(scene.engine, "Biology", active=False)
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14), cancelled=True)
    value = str(hidden_subject) if subject == "hidden" else subject
    before = snapshot(scene.engine)
    not_found(
        send(scene.manager, method, concrete(path, competition, value), value), SUBJECT_NOT_FOUND
    )
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    ("method", "path"), [r for r in MANAGE_ROUTES if "{competition_id" in r[1]]
)
@pytest.mark.parametrize("target", ["missing", "huge", "other-subject", "hidden"])
def test_an_unknown_competition_is_not_found_for_a_manager(
    scene: Scene, method: str, path: str, target: str
) -> None:
    """US7-5: unknown, of another subject, or hidden; before any status refusal (the other
    subject's competition is cancelled)."""
    other = make_competition(scene.engine, scene.physics, starts_at=at(14), cancelled=True)
    finished_subject = make_subject(scene.engine, "Biology")
    make_competition(scene.engine, finished_subject, "Old", starts_at=at(1, 7), stopped=True)
    hidden = make_competition(scene.engine, finished_subject, starts_at=at(14))
    with Session(scene.engine) as session:
        set_subject_active(session, finished_subject, False)
    competition, subject = {
        "missing": (MISSING, scene.chemistry),
        "huge": (10**30, scene.chemistry),
        "other-subject": (other, scene.chemistry),
        "hidden": (hidden, finished_subject),
    }[target]
    before = snapshot(scene.engine)
    url = concrete(path, competition, subject)
    not_found(send(scene.manager, method, url, subject), COMPETITION_NOT_FOUND)
    assert snapshot(scene.engine) == before


def test_a_manager_changes_a_competition_another_teacher_created(
    scene: Scene, client_as: ClientAs
) -> None:
    """US7-3: no per-competition rights."""
    institution = make_institution(scene.engine, "Odesa College", "Odesa")
    make_teacher(
        scene.engine,
        app.state.settings,
        email="second@example.org",
        institutions={institution: AccessLevel.READ},
        can_manage=True,
    )
    assert create(client_as("second@example.org"), scene.chemistry).status_code == 303
    competition = only_id(scene.engine)
    assert edit(scene.manager, competition, scene.chemistry, "Renamed").status_code == 303
    assert cancel(scene.manager, competition, scene.chemistry).status_code == 303
    row = stored(scene.engine, competition)
    assert (row.name, row.cancelled_at) == ("Renamed", NOW)


@pytest.mark.parametrize(("method", "path"), [r for r in COMPETITION_ROUTES if r[0] == "POST"])
@pytest.mark.parametrize(
    "forged", [{"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://evil.example"}]
)
def test_a_cross_site_action_changes_nothing(
    scene: Scene, method: str, path: str, forged: dict[str, str]
) -> None:
    """US7-6, FR-044."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    before = snapshot(scene.engine)
    response = send(
        scene.manager,
        method,
        concrete(path, competition, scene.chemistry),
        scene.chemistry,
        headers=forged,
    )
    assert response.status_code == 403
    assert snapshot(scene.engine) == before


def remove_setting(engine: Engine) -> None:
    with Session(engine) as session:
        user = get_user_by_email(session, MANAGER)
        assert user is not None and user.id is not None
        view = get_teacher(session, user.id)
        update_teacher(
            session,
            user.id,
            view.first_name,
            view.last_name,
            {link.institution_id: link.access_level for link in view.links},
            can_manage_competitions=False,
        )


@pytest.mark.parametrize("action", ["create", "edit", "cancel"])
def test_the_setting_removed_between_the_form_and_the_save(scene: Scene, action: str) -> None:
    """US7-7: the save is refused; nothing is stored."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    page = {
        "create": f"{TAB}/new",
        "edit": f"{TAB}/{competition}/edit",
        "cancel": f"{TAB}/{competition}/cancel",
    }[action]
    assert scene.manager.get(f"{page}?subject={scene.chemistry}").status_code == 200
    remove_setting(scene.engine)
    before = snapshot(scene.engine)
    response = {
        "create": lambda: create(scene.manager, scene.chemistry, "Late"),
        "edit": lambda: edit(scene.manager, competition, scene.chemistry, "Late"),
        "cancel": lambda: cancel(scene.manager, competition, scene.chemistry),
    }[action]()
    denied(response)
    assert snapshot(scene.engine) == before


def test_a_path_id_that_is_not_a_number_matches_no_route(scene: Scene) -> None:
    for browser in (scene.manager, scene.reader):
        response = browser.get(f"{TAB}/abc/edit?subject={scene.chemistry}")
        assert response.status_code == 404
        assert "Competition not found" not in response.text


@pytest.mark.parametrize(
    ("method", "url", "data"),
    [
        ("GET", f"{TAB}?subject=1e9999&page=-1&status=%00", None),
        ("GET", f"{TAB}?subject=%00&page=%FF&notice=%FF", None),
        ("GET", f"{TAB}/new?subject=x&page=x&status=x", None),
        ("GET", f"{TAB}/{'9' * 30}/edit?subject=1", None),
        ("POST", TAB, {}),
        ("POST", TAB, {"subject": "x", "page": "y", "start_date": "z", "time_zone": "../etc"}),
        ("POST", f"{TAB}/1/edit", {}),
        ("POST", f"{TAB}/{'9' * 30}/cancel", {"anything": "x"}),
    ],
)
def test_no_input_gets_a_json_422(
    scene: Scene, method: str, url: str, data: dict[str, str] | None
) -> None:
    for browser in (scene.manager, scene.reader):
        response = browser.request(method, url, data=data, follow_redirects=False)
        assert response.status_code != 422
        assert not response.headers.get("content-type", "").startswith("application/json")


# ---------------------------------------------------------------------------------------------
# User story 8: times follow the teacher's time zone
# ---------------------------------------------------------------------------------------------


def starts_shown(scene: Scene, competition: int) -> list[tuple[str, str | None]]:
    """`(text, datetime)` of the start on the list, then the edit form's date, time and hint,
    then the confirmation's heading."""
    query = f"subject={scene.chemistry}"
    (row,) = rows(scene.manager.get(f"{TAB}?{query}").text)
    form = scene.manager.get(f"{TAB}/{competition}/edit?{query}").text
    confirmation = scene.manager.get(f"{TAB}/{competition}/cancel?{query}").text
    (heading,) = html.parse(confirmation).find_all("h1")
    (time,) = heading.find_all("time")
    hint = html.text(form, "main").split("Time zone: ")[1].split()[0]
    return [
        (row.start, row.datetime),
        (html.control(form, "start_date")["value"], None),
        (html.control(form, "start_time")["value"], hint),
        (time.text(), time.attrs.get("datetime")),
    ]


def test_every_start_is_shown_in_the_cookies_zone(scene: Scene) -> None:
    """US8-2."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14, 8))
    assert starts_shown(scene, competition) == [
        ("14 March 2027, 10:00", "2027-03-14T08:00Z"),
        ("2027-03-14", None),
        ("10:00", KYIV),
        ("14 March 2027, 10:00", "2027-03-14T08:00Z"),
    ]


@pytest.mark.parametrize("cookie", [None, "Mars/Base", "utc", "../etc/passwd", "europe/kyiv"])
def test_without_a_known_zone_every_start_is_utc(scene: Scene, cookie: str | None) -> None:
    """US8-3, US8-4."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14, 8))
    scene.manager.cookies.delete("sc_time_zone")
    if cookie is not None:
        scene.manager.cookies.set("sc_time_zone", cookie)
    assert starts_shown(scene, competition) == [
        ("14 March 2027, 08:00 UTC", "2027-03-14T08:00Z"),
        ("2027-03-14", None),
        ("08:00", "UTC"),
        ("14 March 2027, 08:00 UTC", "2027-03-14T08:00Z"),
    ]


def test_another_zone(scene: Scene) -> None:
    """US8-5: New York has moved its clocks on 14 March 2027, so 08:00 UTC is 04:00 there."""
    competition = make_competition(scene.engine, scene.chemistry, starts_at=at(14, 8))
    scene.manager.cookies.set("sc_time_zone", "America/New_York")
    assert starts_shown(scene, competition)[0] == ("14 March 2027, 04:00", "2027-03-14T08:00Z")
    assert starts_shown(scene, competition)[2] == ("04:00", "America/New_York")


def test_a_start_entered_in_a_zone_is_compared_in_utc(scene: Scene) -> None:
    """US8-1: 1 March 2027 04:30 in New York (UTC−5) is 09:30 UTC, after the clock's 09:00;
    03:59 is 08:59 UTC, before it."""
    zone = "America/New_York"
    late = create(scene.manager, scene.chemistry, "Late", "2027-03-01", "04:30", time_zone=zone)
    assert late.status_code == 303
    assert stored(scene.engine, only_id(scene.engine)).starts_at == at(1, 9, 30)
    early = create(scene.manager, scene.chemistry, "Early", "2027-03-01", "03:59", time_zone=zone)
    assert early.status_code == 400
    assert html.field_error(early.text, "start_date") == "The start must be in the future."


# ---------------------------------------------------------------------------------------------
# User story 9: deactivated subjects keep only their finished competitions
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Deactivated:
    upcoming: int
    running: int
    cancelled: int
    finished: int


@pytest.fixture
def deactivated(scene: Scene) -> Deactivated:
    """Chemistry with one competition of each status, then deactivated."""
    found = Deactivated(
        upcoming=make_competition(scene.engine, scene.chemistry, "Upcoming", starts_at=at(14)),
        running=make_competition(scene.engine, scene.chemistry, "Running", starts_at=at(1, 8)),
        cancelled=make_competition(
            scene.engine, scene.chemistry, "Cancelled", starts_at=at(14), cancelled=True
        ),
        finished=make_competition(
            scene.engine, scene.chemistry, "Finished", starts_at=at(1, 7), stopped=True
        ),
    )
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    return found


def test_a_deactivated_subject_lists_only_its_finished_competitions(
    scene: Scene, deactivated: Deactivated
) -> None:
    """US9-1, US9-2: under "Deactivated subjects", read-only, with the status list."""
    astronomy = make_subject(scene.engine, "astronomy", active=False)
    make_competition(scene.engine, astronomy, "Old", starts_at=at(1, 7), stopped=True)
    body = listed(scene)
    options = html.parse(body)
    (select_element,) = [s for s in options.find_all("select") if s.attrs.get("name") == "subject"]
    (group,) = select_element.find_all("optgroup")
    assert group.attrs["label"] == "Deactivated subjects"
    assert [o.text() for o in group.find_all("option")] == ["astronomy", "Chemistry"]
    assert [o.text for o in html.options(body, "subject")] == [
        "Choose a subject",
        "Physics",
        "astronomy",
        "Chemistry",
    ]
    # Replaced by milestone 12.2 FR-002 (SC-009): a finished row of a deactivated subject keeps
    # a read-only menu.
    assert [(r.id, r.status, r.menu) for r in rows(body)] == [
        (
            deactivated.finished,
            "Finished",
            lists(deactivated.finished, f"subject={scene.chemistry}"),
        )
    ]
    assert add_button(body) == []
    assert [o.text for o in html.options(body, "status")][0] == "All"
    assert names(listed(scene, "&status=finished")) == ["Finished"]
    assert empty_state(listed(scene, "&status=upcoming")) == (
        "No competitions with this status",
        "Choose another status, or All.",
    )


def test_its_other_competitions_are_not_found(scene: Scene, deactivated: Deactivated) -> None:
    """US9-3."""
    before = snapshot(scene.engine)
    for competition in (deactivated.upcoming, deactivated.running, deactivated.cancelled):
        for page in ("edit", "cancel"):
            not_found(
                scene.manager.get(f"{TAB}/{competition}/{page}?subject={scene.chemistry}"),
                COMPETITION_NOT_FOUND,
            )
        not_found(edit(scene.manager, competition, scene.chemistry, "New"), COMPETITION_NOT_FOUND)
        not_found(cancel(scene.manager, competition, scene.chemistry), COMPETITION_NOT_FOUND)
    assert snapshot(scene.engine) == before


def test_its_finished_competition_is_refused_not_hidden(
    scene: Scene, deactivated: Deactivated
) -> None:
    """US9-4: the subject and the competition are found; the status refuses."""
    competition = deactivated.finished
    back = f"{TAB}?subject={scene.chemistry}#competition-{competition}"
    refused(
        scene.manager.get(f"{TAB}/{competition}/edit?subject={scene.chemistry}"),
        "Edit competition “Finished”?",
        "“Finished” has finished and can no longer be edited.",
        back,
    )
    refused(
        cancel(scene.manager, competition, scene.chemistry),
        "Cancel competition “Finished”?",
        "“Finished” has finished and cannot be cancelled.",
        back,
    )


def test_nothing_can_be_added_to_it(scene: Scene, deactivated: Deactivated) -> None:
    """Spec Assumptions: the create page and action answer "Subject not found"."""
    before = snapshot(scene.engine)
    not_found(scene.manager.get(f"{TAB}/new?subject={scene.chemistry}"), SUBJECT_NOT_FOUND)
    not_found(create(scene.manager, scene.chemistry), SUBJECT_NOT_FOUND)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("form", ["create", "edit-upcoming", "cancel-upcoming", "cancel-running"])
def test_forms_sent_after_the_deactivation(scene: Scene, form: str) -> None:
    """Spec Edge Cases: each form opened while the subject was active."""
    upcoming = make_competition(scene.engine, scene.chemistry, "Upcoming", starts_at=at(14))
    running = make_competition(scene.engine, scene.chemistry, "Running", starts_at=at(1, 8))
    query = f"?subject={scene.chemistry}"
    opened = {
        "create": f"{TAB}/new{query}",
        "edit-upcoming": f"{TAB}/{upcoming}/edit{query}",
        "cancel-upcoming": f"{TAB}/{upcoming}/cancel{query}",
        "cancel-running": f"{TAB}/{running}/cancel{query}",
    }[form]
    assert scene.manager.get(opened).status_code == 200
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    before = snapshot(scene.engine)
    response = {
        "create": lambda: create(scene.manager, scene.chemistry, "Late"),
        "edit-upcoming": lambda: edit(scene.manager, upcoming, scene.chemistry, "Late"),
        "cancel-upcoming": lambda: cancel(scene.manager, upcoming, scene.chemistry),
        "cancel-running": lambda: cancel(scene.manager, running, scene.chemistry),
    }[form]()
    assert response.status_code == 404
    assert snapshot(scene.engine) == before


def test_a_deactivated_subject_without_a_finished_competition_is_not_offered(
    scene: Scene,
) -> None:
    """US9-5."""
    make_competition(scene.engine, scene.chemistry, starts_at=at(14))
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    body = scene.manager.get(TAB).text
    assert [o.text for o in html.options(body, "subject")] == ["Choose a subject", "Physics"]
    not_found(scene.manager.get(f"{TAB}?subject={scene.chemistry}"), SUBJECT_NOT_FOUND)


def test_activating_again_brings_everything_back(scene: Scene, deactivated: Deactivated) -> None:
    """US9-6: an upcoming competition whose start passed meanwhile shows In progress."""
    scene.clock(timedelta(days=20))
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, True)
    body = listed(scene)
    assert {r.name: r.status for r in rows(body)} == {
        "Upcoming": "In progress",
        "Running": "In progress",
        "Cancelled": "Cancelled",
        "Finished": "Finished",
    }
    assert add_button(body) != []


def test_a_deactivated_subject_that_is_the_only_offered_is_chosen(
    scene: Scene, deactivated: Deactivated
) -> None:
    with Session(scene.engine) as session:
        set_subject_active(session, scene.physics, False)
    body = scene.manager.get(TAB).text
    assert [o.text for o in html.options(body, "subject") if o.selected] == ["Chemistry"]
    assert names(body) == ["Finished"]
