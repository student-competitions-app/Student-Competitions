"""A competition's questions and teams, end to end through the test client.

See specs/012.2-competition-questions-teams/spec.md US1–US10, contracts/http-routes.md and
research R16. Every case runs on both engines. The clock is fixed at 1 March 2027 09:00 UTC by
patching `app.services.competitions.utc_now`, and moved forward where a start must pass; no test
waits. The browser's zone is the `sc_time_zone` cookie, set as `time-zone.js` would.

- Olena: a real teacher with **Can manage competitions**, linked only to "Lviv Academy";
- Mykola: a real teacher without it;
- "Chemistry" and "Physics": active subjects; "Spring round": an upcoming competition of
  Chemistry starting 14 March 2027, 10:00 in Kyiv;
- "School No. 5" and "Kyiv Lyceum" in Kyiv, which nobody is linked to.

The access sweep is built from the router's own route table, so a later route is covered too.
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

from app.main import app
from app.models import AccessLevel, Institution, Role
from app.services.competitions import cancel_competition
from app.services.institutions import set_institution_active
from app.services.questions import delete_question, update_question
from app.services.regions import set_region_active
from app.services.subjects import set_subject_active
from app.services.teachers import get_teacher, update_teacher
from app.services.teams import rename_team
from app.services.users import get_user_by_email
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    AUTO,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    add_competition_question,
    add_competition_team,
    make_class,
    make_competition,
    make_institution,
    make_member,
    make_question,
    make_subject,
    make_teacher,
    make_team,
)
from tests.integration.test_routes import ALL_ROUTES
from tests.integration.test_team_service import enrolled

OLENA = "olena@example.org"
MYKOLA = "mykola@example.org"
TAB = "/teacher/competitions"
KYIV = "Europe/Kyiv"
NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
START = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
"""14 March 2027, 10:00 in Kyiv."""
MISSING = 999_999

COMPETITION_NOT_FOUND = ("Competition not found", "This competition does not exist")
SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist")
REGION_NOT_FOUND = ("Region not found", "This region does not exist, or it is deactivated.")
QUESTION_NOT_FOUND = (
    "Question not found",
    "This question does not exist, or it cannot be added to this competition.",
)
TEAM_NOT_FOUND = (
    "Team not found",
    "This team does not exist, or it cannot be added to this competition.",
)


@dataclass(frozen=True)
class Scene:
    engine: Engine
    olena: TestClient
    mykola: TestClient
    chemistry: int
    physics: int
    competition: int
    school: int
    lyceum: int
    academy: int
    clock: Callable[[timedelta], datetime]

    @property
    def ctx(self) -> str:
        """The competitions-list context of the competition's subject, status All, page 1."""
        return f"subject={self.chemistry}"


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    now = [NOW]
    monkeypatch.setattr("app.services.competitions.utc_now", lambda: now[0])

    def advance(by: timedelta = timedelta(0)) -> datetime:
        now[0] += by
        return now[0]

    return advance


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs, clock: Callable[[timedelta], datetime]) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    academy = make_institution(engine, "Lviv Academy", "Lviv")
    make_teacher(
        engine, settings, email=OLENA, institutions={academy: AccessLevel.READ}, can_manage=True
    )
    make_teacher(
        engine,
        settings,
        email=MYKOLA,
        institutions={academy: AccessLevel.WRITE},
        first="Mykola",
        last="Read",
    )
    olena, mykola = client_as(OLENA), client_as(MYKOLA)
    for browser in (olena, mykola):
        browser.cookies.set("sc_time_zone", KYIV)
    chemistry = make_subject(engine, "Chemistry")
    return Scene(
        engine=engine,
        olena=olena,
        mykola=mykola,
        chemistry=chemistry,
        physics=make_subject(engine, "Physics"),
        competition=make_competition(engine, chemistry, starts_at=START),
        school=make_institution(engine, "School No. 5", "Kyiv"),
        lyceum=make_institution(engine, "Kyiv Lyceum", "Kyiv"),
        academy=academy,
        clock=clock,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

SNAPSHOT_TABLES = ("competition_questions", "competition_teams", "questions", "teams")


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def region_of(engine: Engine, institution_id: int) -> int:
    with Session(engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


def at(day: int, hour: int = 10) -> datetime:
    return datetime(2027, 3, day, hour, 0, tzinfo=UTC)


def page_of(scene: Scene, kind: str, query: str = "", competition: int | None = None) -> str:
    """The address of a competition's list or page, with the context."""
    return f"{TAB}/{competition or scene.competition}/{kind}?{scene.ctx}{query}"


def get(browser: TestClient, url: str) -> str:
    response = browser.get(url)
    assert response.status_code == 200, (url, response.status_code)
    return response.text


def follow(browser: TestClient, response: Any) -> str:
    assert response.status_code == 303, response.text
    return get(browser, response.headers["location"])


def address(response: Any) -> tuple[str, dict[str, list[str]], str]:
    """The redirect's path, its query (without the notice) and its anchor."""
    assert response.status_code == 303, response.text
    parts = urlsplit(response.headers["location"])
    query = parse_qs(parts.query)
    query.pop("notice", None)
    return parts.path, query, parts.fragment


class Card(NamedTuple):
    id: str
    heading: str
    boxes: list[str]
    notes: list[str]
    actions: list[str]


def cards(body: str) -> list[Card]:
    """The text cards of the page: heading, the boxes' texts, row notes and actions."""
    found = []
    for article in html.parse(body).find_all("article"):
        if "text-card" not in article.classes():
            continue
        found.append(
            Card(
                id=article.attrs.get("id", ""),
                heading=article.find_all("h3")[0].text(),
                boxes=[p.text() for p in article.find_all("p")],
                notes=[s.text() for s in article.find_all("span") if "row-note" in s.classes()],
                actions=[e.text() for e in article.iter() if e.tag in ("a", "button")],
            )
        )
    return found


def card_ids(body: str) -> list[int]:
    return [int(c.id.removeprefix("question-")) for c in cards(body)]


class Group(NamedTuple):
    header: str
    heading_id: str
    rows: list[dict[str, str]]
    row_ids: list[str]


def region_groups(body: str) -> list[Group]:
    found = []
    for section in html.parse(body).find_all("section"):
        if "region-group" not in section.classes():
            continue
        (header,) = section.find_all("h2")
        assert header.attrs["id"] == section.attrs["aria-labelledby"]
        rows, ids = [], []
        for tr in section.find_all("tr"):
            if not tr.attrs.get("id", "").startswith("team-"):
                continue
            ids.append(tr.attrs["id"])
            rows.append({td.attrs.get("data-label", ""): td.text() for td in tr.find_all("td")})
        found.append(Group(header.text(), header.attrs["id"], rows, ids))
    return found


def team_rows(body: str) -> dict[str, dict[str, str]]:
    """The rows of the page's tables keyed by their `team-<id>`."""
    found = {}
    for tr in html.parse(body).find_all("tr"):
        if tr.attrs.get("id", "").startswith("team-"):
            found[tr.attrs["id"]] = {
                td.attrs.get("data-label", ""): td.text() for td in tr.find_all("td")
            }
    return found


def notices(body: str) -> list[tuple[str, str]]:
    """`(kind, text)` of every notice: success, info or error."""
    found = []
    for div in html.parse(body).find_all("div"):
        kinds = [c.removeprefix("notice-") for c in div.classes() if c.startswith("notice-")]
        if "notice" in div.classes() and kinds:
            found.append((kinds[0], div.text()))
    return found


def empty_state(body: str) -> tuple[str, str | None] | None:
    states = [d for d in html.parse(body).find_all("div") if "empty-state" in d.classes()]
    if not states:
        return None
    (state,) = states
    message = [p.text() for p in state.find_all("p") if "empty-state-message" in p.classes()]
    hint = [p.text() for p in state.find_all("p") if "empty-state-hint" in p.classes()]
    return message[0], hint[0] if hint else None


def heading_action(body: str) -> list[tuple[str, str]]:
    """The `(href, text)` of the button beside the page heading."""
    headings = [d for d in html.parse(body).find_all("div") if "page-heading" in d.classes()]
    return [(a.attrs["href"], a.text()) for d in headings for a in d.find_all("a")]


def back_link(body: str) -> tuple[str, str]:
    (link,) = [a for a in html.parse(body).find_all("a") if "back-link" in a.attrs.get("class", "")]
    return link.attrs["href"], link.text()


def not_found(response: Any, page: tuple[str, str]) -> None:
    assert response.status_code == 404, response.text
    assert html.h1(response.text) == page[0]
    assert page[1] in response.text
    current = [t for t in html.nav(response.text, "Teacher area") if t.attrs.get("aria-current")]
    assert [t.text for t in current] == ["Competitions"]


def denied(response: Any, label: str = "Teacher") -> None:
    assert response.status_code == 403, response.text
    assert f"Your current role, {label}, cannot open this page." in response.text


def refused(response: Any, kind: str, reason: str, back: str) -> None:
    """The 409 refusal of a change to `kind` ("questions" or "teams")."""
    assert response.status_code == 409, response.text
    assert html.h1(response.text) == f"Change the {kind} of “Spring round”?"
    assert reason in html.text(response.text, "main")
    pairs = html.link_pairs(response.text, "main")
    assert (back, "Back to the competition") in pairs
    assert (back, f"Back to the {kind}") in pairs


def form(scene: Scene, **values: Any) -> dict[str, str]:
    data = {"subject": str(scene.chemistry), "status": "", "page": "1", "back": "1", "p": "1"}
    return data | {key: str(value) for key, value in values.items()}


def add_question(
    browser: TestClient,
    scene: Scene,
    question: int | str,
    competition: int | None = None,
    **kw: Any,
) -> Any:
    return browser.post(
        f"{TAB}/{competition or scene.competition}/questions",
        data=form(scene, question=question, **kw),
        follow_redirects=False,
    )


def add_team(
    browser: TestClient,
    scene: Scene,
    team: int | str,
    region: int | str,
    competition: int | None = None,
    **kw: Any,
) -> Any:
    return browser.post(
        f"{TAB}/{competition or scene.competition}/teams",
        data=form(scene, team=team, region=region, **kw),
        follow_redirects=False,
    )


def remove(
    browser: TestClient,
    scene: Scene,
    kind: str,
    entry: int | str,
    competition: int | None = None,
    **kw: Any,
) -> Any:
    return browser.post(
        f"{TAB}/{competition or scene.competition}/{kind}/{entry}/remove",
        data=form(scene, **kw),
        follow_redirects=False,
    )


def questions_of(scene: Scene, n: int, **kw: Any) -> list[int]:
    return [make_question(scene.engine, scene.chemistry, f"Text {i}", f"Answer {i}", **kw)
            for i in range(n)]  # fmt: skip


# ---------------------------------------------------------------------------------------------
# User story 1: a teacher adds questions to an upcoming competition
# ---------------------------------------------------------------------------------------------


def test_the_questions_page_of_a_competition(scene: Scene) -> None:
    """US1-1, US3-1, FR-003, FR-009: the title, the subject, the start in the teacher's zone and
    the status under the heading, Add question for Olena, and the empty state with its hint."""
    body = get(scene.olena, page_of(scene, "questions"))
    assert html.h1(body) == "Questions of “Spring round”"
    assert "<title>Questions of “Spring round” — " in body
    assert html.details(body) == [
        ("Subject", "Chemistry"),
        ("Start", "14 March 2027, 10:00"),
        ("Status", "Upcoming"),
    ]
    assert '<time datetime="2027-03-14T08:00Z">' in body
    add = f"{TAB}/{scene.competition}/questions/add?{scene.ctx}"
    assert heading_action(body) == [(add, "Add question")]
    assert empty_state(body) == (
        "No questions in this competition yet",
        "Add questions with Add question.",
    )
    current = [t for t in html.nav(body, "Teacher area") if t.attrs.get("aria-current")]
    assert [t.text for t in current] == ["Competitions"]


def test_the_add_questions_page(scene: Scene) -> None:
    """US1-2, US1-3, FR-016, FR-017: newest first, deleted ones left out, 10 per page with the
    navigation above and below, each in full with its number and an Add button."""
    ids = questions_of(scene, 12)
    make_question(scene.engine, scene.chemistry, "Gone", deleted=True)
    make_question(scene.engine, scene.physics, "Physics question")
    body = get(scene.olena, page_of(scene, "questions/add"))
    assert html.h1(body) == "Add questions to “Spring round”"
    assert back_link(body) == (page_of(scene, "questions"), "Back to the questions")
    assert card_ids(body) == list(reversed(ids))[:10]
    first = cards(body)[0]
    assert first.heading == f"Question {ids[-1]}"
    assert first.boxes == ["Text 11", "Answer 11"]
    assert first.actions == ["Add"]
    for label in ("Pages, top", "Pages, bottom"):
        found = html.pagination(body, label)
        assert found is not None and found[0] == "Questions 1–10 of 12"
    assert "Gone" not in body and "Physics question" not in body
    forms = [f for f in html.forms(body, "main") if f.method == "post"]
    assert forms[0].action == f"{TAB}/{scene.competition}/questions"
    assert [(i.name, i.value) for i in forms[0].inputs] == [
        ("subject", str(scene.chemistry)),
        ("status", ""),
        ("page", "1"),
        ("back", "1"),
        ("p", "1"),
        ("question", str(ids[-1])),
    ]


def test_adding_a_question_stays_on_the_page_at_it(scene: Scene) -> None:
    """US1-4, FR-018: the copy at the end, the same page, at the question, with the notice and
    "Already in this competition" with no Add."""
    ids = questions_of(scene, 3)
    response = add_question(scene.olena, scene, ids[1])
    assert address(response) == (
        f"{TAB}/{scene.competition}/questions/add",
        {"subject": [str(scene.chemistry)]},
        f"question-{ids[1]}",
    )
    body = follow(scene.olena, response)
    assert notices(body) == [("success", f"Question {ids[1]} was added to “Spring round”")]
    by_id = {c.id: c for c in cards(body)}
    assert by_id[f"question-{ids[1]}"].notes == ["Already in this competition"]
    assert by_id[f"question-{ids[1]}"].actions == []
    assert by_id[f"question-{ids[0]}"].actions == ["Add"]
    location = response.headers["location"]
    for secret in ("Spring", "Text", "Chemistry"):
        assert secret not in location


def test_questions_are_listed_in_the_order_they_were_added(scene: Scene) -> None:
    """US1 story, FR-005: added as 12, 9, 15."""
    nine, twelve, fifteen = questions_of(scene, 3)
    for question in (twelve, nine, fifteen):
        assert add_question(scene.olena, scene, question).status_code == 303
    body = get(scene.olena, page_of(scene, "questions"))
    assert card_ids(body) == [twelve, nine, fifteen]
    assert [c.boxes for c in cards(body)][0] == ["Text 1", "Answer 1"]


def test_the_add_page_keeps_its_page_and_way_back(scene: Scene) -> None:
    """US1-5, FR-004: 25 bank questions; adding from page 2 returns to page 2, and the way back
    leads to the page of the competition's list it came from."""
    ids = questions_of(scene, 25)
    response = add_question(scene.olena, scene, ids[5], p="2", back="3", status="upcoming",
                            page="2")  # fmt: skip
    assert address(response) == (
        f"{TAB}/{scene.competition}/questions/add",
        {
            "subject": [str(scene.chemistry)],
            "status": ["upcoming"],
            "page": ["2"],
            "back": ["3"],
            "p": ["2"],
        },
        f"question-{ids[5]}",
    )
    body = follow(scene.olena, response)
    assert ids[5] in card_ids(body)
    nav = html.pagination(body, "Pages, top")
    assert nav is not None and [e.text for e in nav[1] if e.current] == ["2"]
    prefix = f"{TAB}/{scene.competition}/questions/add?subject={scene.chemistry}"
    assert (f"{prefix}&status=upcoming&page=2&back=3&p=3", "Next") in [
        (e.href, e.text) for e in nav[1]
    ]
    assert back_link(body) == (
        f"{TAB}/{scene.competition}/questions?subject={scene.chemistry}&status=upcoming&page=2&p=3",
        "Back to the questions",
    )


def test_a_subject_with_no_questions(scene: Scene) -> None:
    """US1-6, FR-019."""
    make_question(scene.engine, scene.chemistry, deleted=True)
    body = get(scene.olena, page_of(scene, "questions/add"))
    assert empty_state(body) == ("No questions in this subject yet", None)


# ---------------------------------------------------------------------------------------------
# User story 3: every teacher reads a competition's questions
# ---------------------------------------------------------------------------------------------


def test_a_teacher_without_the_setting_reads_the_same_list(scene: Scene) -> None:
    """US3 story, FR-015: the same cards, no Add question and no Remove."""
    for question in questions_of(scene, 2):
        add_competition_question(scene.engine, scene.competition, question)
    olena = get(scene.olena, page_of(scene, "questions"))
    mykola = get(scene.mykola, page_of(scene, "questions"))
    assert [c[:3] for c in cards(olena)] == [c[:3] for c in cards(mykola)]
    assert heading_action(mykola) == []
    assert all(c.actions == [] for c in cards(mykola))
    assert all(c.actions == ["Remove"] for c in cards(olena))


def test_23_questions_are_paged_with_the_page_in_the_address(scene: Scene) -> None:
    """US3-2, FR-005, FR-004."""
    ids = questions_of(scene, 23)
    for question in reversed(ids):
        add_competition_question(scene.engine, scene.competition, question)
    first = get(scene.mykola, page_of(scene, "questions"))
    second = get(scene.mykola, page_of(scene, "questions", "&p=2"))
    for body, expected in ((first, "Questions 1–10 of 23"), (second, "Questions 11–20 of 23")):
        for label in ("Pages, top", "Pages, bottom"):
            found = html.pagination(body, label)
            assert found is not None and found[0] == expected
    assert card_ids(second) == list(reversed(ids))[10:20]
    nav = html.pagination(first, "Pages, top")
    assert nav is not None
    assert (page_of(scene, "questions", "&p=2"), "2") in [(e.href, e.text) for e in nav[1]]
    for value in ("99", "x", "-1"):
        body = get(scene.mykola, page_of(scene, "questions", f"&p={value}"))
        expected = "Questions 21–23 of 23" if value == "99" else "Questions 1–10 of 23"
        found = html.pagination(body, "Pages, top")
        assert found is not None and found[0] == expected, value


def test_the_copies_survive_a_bank_edit_and_a_deletion(scene: Scene) -> None:
    """US3-3–US3-5, FR-006–FR-008, SC-002."""
    edited, deleted = questions_of(scene, 2)
    for question in (edited, deleted):
        add_question(scene.olena, scene, question)
    user_id = olena_id(scene.engine)
    with Session(scene.engine) as session:
        update_question(session, user_id, edited, "New text", "New answer")
        delete_question(session, user_id, deleted)
    body = get(scene.mykola, page_of(scene, "questions"))
    assert [(c.heading, c.boxes, c.notes) for c in cards(body)] == [
        (f"Question {edited}", ["Text 0", "Answer 0"], []),
        (f"Question {deleted}", ["Text 1", "Answer 1"], ["Deleted from the question bank"]),
    ]


def test_the_empty_hint_only_for_a_teacher_who_can_make_changes(
    scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US3-6, FR-009."""
    assert empty_state(get(scene.mykola, page_of(scene, "questions"))) == (
        "No questions in this competition yet",
        None,
    )
    clock(START - NOW)
    assert empty_state(get(scene.olena, page_of(scene, "questions"))) == (
        "No questions in this competition yet",
        None,
    )


def test_the_back_link_leads_to_the_list_the_teacher_came_from(scene: Scene) -> None:
    """US3-7, FR-004."""
    for kind in ("questions", "teams"):
        body = get(scene.mykola, page_of(scene, kind, "&status=upcoming&page=2"))
        assert back_link(body) == (
            f"{TAB}?subject={scene.chemistry}&status=upcoming&page=2"
            f"#competition-{scene.competition}",
            "Back to the competitions",
        )


def test_without_a_subject_the_way_back_falls_back_to_the_competition(scene: Scene) -> None:
    """Spec Edge Cases, Assumptions: the competition's subject, All, the page that holds it."""
    for day in range(15, 30):
        make_competition(scene.engine, scene.chemistry, f"Day {day}", starts_at=at(day))
    for query in ("", "?subject=", "?subject=&status=finished&page=7"):
        body = get(scene.mykola, f"{TAB}/{scene.competition}/questions{query}")
        assert back_link(body) == (
            f"{TAB}?subject={scene.chemistry}&page=2#competition-{scene.competition}",
            "Back to the competitions",
        )
    not_found(scene.mykola.get(f"{TAB}/{MISSING}/questions"), COMPETITION_NOT_FOUND)


def test_a_mismatched_or_unknown_subject_is_not_found(scene: Scene) -> None:
    for kind in ("questions", "teams"):
        url = f"{TAB}/{scene.competition}/{kind}"
        not_found(scene.mykola.get(f"{url}?subject={scene.physics}"), COMPETITION_NOT_FOUND)
        not_found(scene.mykola.get(f"{url}?subject=abc"), SUBJECT_NOT_FOUND)
        assert scene.mykola.get(f"{url}?subject={scene.chemistry}&status=bogus").status_code == 200


# ---------------------------------------------------------------------------------------------
# User story 4: every teacher reads a competition's teams, grouped by region
# ---------------------------------------------------------------------------------------------


def seed_regions(scene: Scene) -> dict[str, list[int]]:
    """25 teams: "Dnipro" 4, "Kyiv" 14, "Lviv" 7, named "<region> 01" …"""
    institutions = {
        "Dnipro": make_institution(scene.engine, "Dnipro School", "Dnipro"),
        "Kyiv": scene.school,
        "Lviv": scene.academy,
    }
    teams: dict[str, list[int]] = {}
    for region, size in (("Lviv", 7), ("Kyiv", 14), ("Dnipro", 4)):
        teams[region] = [
            make_team(scene.engine, institutions[region], f"{region} {n:02}")
            for n in range(1, size + 1)
        ]
        for team in teams[region]:
            add_competition_team(scene.engine, scene.competition, team)
    return teams


def test_the_teams_page_of_a_competition(scene: Scene) -> None:
    """US4-1, US4-9, US2-1, FR-014."""
    body = get(scene.olena, page_of(scene, "teams"))
    assert html.h1(body) == "Teams of “Spring round”"
    assert html.details(body) == [
        ("Subject", "Chemistry"),
        ("Start", "14 March 2027, 10:00"),
        ("Status", "Upcoming"),
    ]
    assert heading_action(body) == [
        (f"{TAB}/{scene.competition}/teams/add?{scene.ctx}", "Add team")
    ]
    assert empty_state(body) == ("No teams in this competition yet", "Add teams with Add team.")
    mykola = get(scene.mykola, page_of(scene, "teams"))
    assert heading_action(mykola) == []
    assert empty_state(mykola) == ("No teams in this competition yet", None)


def test_25_teams_in_region_groups_across_pages(scene: Scene) -> None:
    """US4 story, US4-2–US4-5, FR-010, FR-011."""
    seed_regions(scene)
    first = get(scene.mykola, page_of(scene, "teams"))
    second = get(scene.mykola, page_of(scene, "teams", "&p=2"))
    third = get(scene.mykola, page_of(scene, "teams", "&p=3"))
    shape = [[(g.header, len(g.rows)) for g in region_groups(b)] for b in (first, second, third)]
    assert shape == [
        [("Dnipro · 4 teams", 4), ("Kyiv · 14 teams", 6)],
        [("Kyiv · 14 teams", 8), ("Lviv · 7 teams", 2)],
        [("Lviv · 7 teams", 5)],
    ]
    for body, expected in ((first, "Teams 1–10 of 25"), (second, "Teams 11–20 of 25")):
        for label in ("Pages, top", "Pages, bottom"):
            found = html.pagination(body, label)
            assert found is not None and found[0] == expected
    heading_ids = [g.heading_id for b in (first, second) for g in region_groups(b)]
    assert len(set(heading_ids)) == 4
    assert [r["Team"] for r in region_groups(second)[0].rows][0] == "Kyiv 07"
    assert "<caption>" not in first


def test_a_team_row_shows_its_name_institution_and_active_members(scene: Scene) -> None:
    """US4-6, FR-012: no region in the row and no member names; one team reads "1 team"."""
    kn21 = make_class(scene.engine, scene.school)
    comets = make_team(scene.engine, scene.school, "Comets")
    for n in range(2):
        make_member(
            scene.engine, comets, enrolled(scene.engine, f"s{n}@example.org", kn21, "Iryna", "Zub")
        )
    add_competition_team(scene.engine, scene.competition, comets)
    body = get(scene.mykola, page_of(scene, "teams"))
    (group,) = region_groups(body)
    assert group.header == "Kyiv · 1 team"
    assert group.rows == [
        {"Team": "Comets", "Educational institution": "School No. 5", "Active members": "2"}
    ]
    (table,) = html.parse(body).find_all("table")
    assert [th.text() for th in table.find_all("th")] == [
        "Team",
        "Educational institution",
        "Active members",
    ]
    assert "Zub" not in body and "Iryna" not in body


def test_teams_show_their_current_state(scene: Scene) -> None:
    """US4-7, spec Edge Cases, FR-013, FR-042: a renamed team and one whose members moved show
    their current name and count; a deactivated institution or region keeps its teams."""
    kn21 = make_class(scene.engine, scene.school)
    comets = make_team(scene.engine, scene.school, "Comets")
    lions = make_team(scene.engine, scene.academy, "Lions")
    member = enrolled(scene.engine, "taras@example.org", kn21)
    make_member(scene.engine, comets, member)
    for team in (comets, lions):
        add_competition_team(scene.engine, scene.competition, team)
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, scene.school), scene.school, False)
        set_region_active(session, region_of(scene.engine, scene.academy), False)
    rows = team_rows(get(scene.mykola, page_of(scene, "teams")))
    assert rows[f"team-{comets}"]["Active members"] == "0"
    assert rows[f"team-{lions}"]["Team"] == "Lions"
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, scene.school), scene.school, True)
    writer = make_teacher(
        scene.engine,
        app.state.settings,
        email="taras.teacher@example.org",
        institutions={scene.school: AccessLevel.WRITE},
    )
    with Session(scene.engine) as session:
        rename_team(session, writer, comets, "Comets Prime")
    rows = team_rows(get(scene.mykola, page_of(scene, "teams")))
    assert rows[f"team-{comets}"] == {
        "Team": "Comets Prime",
        "Educational institution": "School No. 5",
        "Active members": "1",
    }


def test_a_finished_competition_marks_its_deleted_teams(scene: Scene) -> None:
    """US4-8, spec Edge Cases: all of its teams deleted, grouped as usual."""
    finished = make_competition(
        scene.engine, scene.chemistry, "Summer round", starts_at=at(1, 7), stopped=True
    )
    for name in ("Comets", "Novas"):
        add_competition_team(
            scene.engine, finished, make_team(scene.engine, scene.school, name, deleted=True)
        )
    body = get(scene.olena, page_of(scene, "teams", competition=finished))
    (group,) = region_groups(body)
    assert group.header == "Kyiv · 2 teams"
    assert [(r["Team"], r[""]) for r in group.rows] == [
        ("Comets", "(deleted)"),
        ("Novas", "(deleted)"),
    ]
    assert heading_action(body) == []


# ---------------------------------------------------------------------------------------------
# User story 2: a teacher adds teams of a region
# ---------------------------------------------------------------------------------------------


def test_the_add_teams_page_before_a_region_is_chosen(scene: Scene) -> None:
    """US2-2, US2-3, US2-4, FR-021, FR-022: every active region, sorted ignoring case, no "all
    regions", and the Show button without JavaScript."""
    closed = make_institution(scene.engine, "Odesa College", "Odesa")
    with Session(scene.engine) as session:
        set_region_active(session, region_of(scene.engine, closed), False)
    make_institution(scene.engine, "Dnipro School", "dnipro")
    body = get(scene.olena, page_of(scene, "teams/add"))
    assert html.h1(body) == "Add teams to “Spring round”"
    assert back_link(body) == (page_of(scene, "teams"), "Back to the teams")
    assert [o.text for o in html.options(body, "region")] == [
        "Choose a region",
        "dnipro",
        "Kyiv",
        "Lviv",
    ]
    assert empty_state(body) == (
        "Select a region",
        "Choose a region in the list above to see its teams.",
    )
    (region_form,) = [f for f in html.forms(body, "main") if f.method == "get"]
    assert region_form.action == f"{TAB}/{scene.competition}/teams/add"
    assert [(i.name, i.value) for i in region_form.inputs if i.type == "hidden"] == [
        ("subject", str(scene.chemistry)),
        ("status", ""),
        ("page", "1"),
        ("back", "1"),
    ]
    assert [b.text for b in region_form.buttons] == ["Show"]
    assert "<noscript>" in body


def test_a_regions_teams_come_from_every_institution(scene: Scene) -> None:
    """US2-5, US2-6, FR-023, FR-025: 14 Kyiv teams of two institutions Olena is not linked to,
    sorted ignoring case, 10 per page; deleted teams and a deactivated institution's are left
    out; no region in the rows."""
    for n in range(14):
        make_team(scene.engine, scene.school if n % 2 else scene.lyceum, f"team {n:02}".title())
    make_team(scene.engine, scene.school, "Deleted", deleted=True)
    closed = make_institution(scene.engine, "Closed School", "Kyiv")
    make_team(scene.engine, closed, "Closed team")
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, closed), closed, False)
    kyiv = region_of(scene.engine, scene.school)
    body = get(scene.olena, page_of(scene, "teams/add", f"&region={kyiv}"))
    found = html.pagination(body, "Pages, top")
    assert found is not None and found[0] == "Teams 1–10 of 14"
    rows = list(team_rows(body).values())
    assert [r["Team"] for r in rows] == [f"Team {n:02}" for n in range(10)]
    assert rows[0] == {
        "Team": "Team 00",
        "Educational institution": "Kyiv Lyceum",
        "Active members": "0",
        "": "Add",
    }
    assert "Deleted" not in body and "Closed team" not in body
    assert [o.text for o in html.options(body, "region") if o.selected] == ["Kyiv"]


def test_adding_a_team_stays_on_the_region_and_page(scene: Scene) -> None:
    """US2 story, US2-7, US2-8, US2-11, FR-026, FR-027: a team with no members too."""
    teams = [make_team(scene.engine, scene.school, f"Team {n:02}") for n in range(12)]
    comets = make_team(scene.engine, scene.lyceum, "Zeta Comets")
    kyiv = region_of(scene.engine, scene.school)
    response = add_team(scene.olena, scene, comets, kyiv, p="2")
    assert address(response) == (
        f"{TAB}/{scene.competition}/teams/add",
        {"subject": [str(scene.chemistry)], "region": [str(kyiv)], "p": ["2"]},
        f"team-{comets}",
    )
    body = follow(scene.olena, response)
    assert notices(body) == [("success", "Team “Zeta Comets” was added to “Spring round”")]
    rows = team_rows(body)
    assert rows[f"team-{comets}"][""] == "Already in this competition"
    assert [o.text for o in html.options(body, "region") if o.selected] == ["Kyiv"]
    assert add_team(scene.olena, scene, teams[0], kyiv).status_code == 303
    assert "Zeta Comets" not in response.headers["location"]


def test_a_team_sharing_a_member_is_added(scene: Scene) -> None:
    """US2-11, FR-027."""
    kn21 = make_class(scene.engine, scene.school)
    taras = enrolled(scene.engine, "taras@example.org", kn21)
    comets, rockets = (make_team(scene.engine, scene.school, n) for n in ("Comets", "Rockets"))
    for team in (comets, rockets):
        make_member(scene.engine, team, taras)
    kyiv = region_of(scene.engine, scene.school)
    for team in (comets, rockets):
        assert add_team(scene.olena, scene, team, kyiv).status_code == 303
    rows = team_rows(get(scene.olena, page_of(scene, "teams")))
    assert sorted(r["Team"] for r in rows.values()) == ["Comets", "Rockets"]


def test_the_only_region_is_chosen_without_a_redirect(
    client: TestClient, client_as: ClientAs, clock: Callable[[timedelta], datetime]
) -> None:
    """US2-9, FR-022: no region in the address; the forms and page links carry its id."""
    engine, settings = app.state.engine, app.state.settings
    school = make_institution(engine, "School No. 5", "Kyiv")
    make_teacher(engine, settings, email=OLENA, institutions={school: AccessLevel.READ},
                 can_manage=True)  # fmt: skip
    chemistry = make_subject(engine, "Chemistry")
    competition = make_competition(engine, chemistry, starts_at=START)
    for n in range(12):
        make_team(engine, school, f"Team {n:02}")
    olena = client_as(OLENA)
    url = f"{TAB}/{competition}/teams/add?subject={chemistry}"
    response = olena.get(url, follow_redirects=False)
    assert response.status_code == 200
    kyiv = region_of(engine, school)
    assert [o.selected for o in html.options(response.text, "region")] == [False, True]
    posts = [f for f in html.forms(response.text, "main") if f.method == "post"]
    assert all(("region", "hidden", str(kyiv)) in f.inputs for f in posts)
    nav = html.pagination(response.text, "Pages, top")
    assert nav is not None
    assert f"{url}&region={kyiv}&p=2" in [e.href for e in nav[1]]


def test_no_region_offered_and_a_region_with_no_teams(scene: Scene) -> None:
    """US2-9, US2-10, FR-022, FR-023."""
    make_team(scene.engine, scene.school, "Gone", deleted=True)
    kyiv = region_of(scene.engine, scene.school)
    body = get(scene.olena, page_of(scene, "teams/add", f"&region={kyiv}"))
    assert empty_state(body) == ("No teams in this region yet", "Choose another region.")
    with Session(scene.engine) as session:
        for region in {kyiv, region_of(scene.engine, scene.academy)}:
            set_region_active(session, region, False)
    body = get(scene.olena, page_of(scene, "teams/add"))
    assert empty_state(body) == ("No teams yet", None)
    assert "disabled" in html.control(body, "region")


@pytest.mark.parametrize("value", ["deactivated", "abc", str(MISSING), "٣"])
def test_an_unknown_or_deactivated_region_is_not_found(scene: Scene, value: str) -> None:
    """FR-024, US9-4."""
    if value == "deactivated":
        closed = make_institution(scene.engine, "Odesa College", "Odesa")
        value = str(region_of(scene.engine, closed))
        with Session(scene.engine) as session:
            set_region_active(session, int(value), False)
    team = make_team(scene.engine, scene.school, "Comets")
    not_found(scene.olena.get(page_of(scene, "teams/add", f"&region={value}")), REGION_NOT_FOUND)
    before = snapshot(scene.engine)
    not_found(add_team(scene.olena, scene, team, value), REGION_NOT_FOUND)
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 6: every row has a menu with the competition's lists
# ---------------------------------------------------------------------------------------------


def menus(body: str) -> dict[str, list[tuple[str, str]]]:
    """`competition-<id>` → `(text, href)` of each menu entry."""
    found = {}
    for tr in html.parse(body).find_all("tr"):
        if tr.attrs.get("id", "").startswith("competition-"):
            found[tr.attrs["id"]] = [(a.text(), a.attrs["href"]) for a in tr.find_all("a")]
    return found


def test_the_menu_entries_per_status_and_setting(
    scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US6-1–US6-4, FR-001, FR-002. The In progress menus replaced by milestone 12.3 FR-001
    (SC-011): they gain **Answers** after **Teams**, for every teacher."""
    running = make_competition(scene.engine, scene.chemistry, "Running", starts_at=at(1, 8))
    finished = make_competition(
        scene.engine, scene.chemistry, "Done", starts_at=at(1, 7), stopped=True
    )
    cancelled = make_competition(
        scene.engine, scene.chemistry, "Off", starts_at=at(14), cancelled=True
    )
    url = f"{TAB}?{scene.ctx}"
    olena = {k: [t for t, _ in v] for k, v in menus(get(scene.olena, url)).items()}
    assert olena == {
        f"competition-{scene.competition}": ["Edit", "Questions", "Teams", "Cancel competition"],
        f"competition-{cancelled}": ["Questions", "Teams"],
        f"competition-{running}": ["Questions", "Teams", "Answers", "Cancel competition"],
        f"competition-{finished}": ["Questions", "Teams"],
    }
    mykola = {k: [t for t, _ in v] for k, v in menus(get(scene.mykola, url)).items()}
    assert mykola.pop(f"competition-{running}") == ["Questions", "Teams", "Answers"]
    assert set(map(tuple, mykola.values())) == {("Questions", "Teams")}
    assert len(mykola) == 3


def test_the_menu_links_keep_the_list_and_lead_back_to_it(scene: Scene) -> None:
    """US6-6, FR-004."""
    for day in range(15, 30):
        make_competition(scene.engine, scene.chemistry, f"Day {day}", starts_at=at(day))
    url = f"{TAB}?{scene.ctx}&status=upcoming&page=2"
    entries = dict(menus(get(scene.mykola, url))[f"competition-{scene.competition}"])
    query = f"subject={scene.chemistry}&status=upcoming&page=2"
    assert entries == {
        "Questions": f"{TAB}/{scene.competition}/questions?{query}",
        "Teams": f"{TAB}/{scene.competition}/teams?{query}",
    }
    for href in entries.values():
        assert back_link(get(scene.mykola, href)) == (
            f"{TAB}?{query}#competition-{scene.competition}",
            "Back to the competitions",
        )


# ---------------------------------------------------------------------------------------------
# User story 5: a teacher removes a question or a team
# ---------------------------------------------------------------------------------------------


def test_every_question_and_team_has_remove_for_a_manager(scene: Scene) -> None:
    """US5-1, FR-015."""
    question = make_question(scene.engine, scene.chemistry)
    team = make_team(scene.engine, scene.school, "Comets")
    add_competition_question(scene.engine, scene.competition, question)
    add_competition_team(scene.engine, scene.competition, team)
    questions = get(scene.olena, page_of(scene, "questions"))
    assert (
        f"{TAB}/{scene.competition}/questions/{question}/remove?{scene.ctx}",
        "Remove",
    ) in html.link_pairs(questions, "main")
    teams = get(scene.olena, page_of(scene, "teams"))
    assert team_rows(teams)[f"team-{team}"][""] == "Remove"
    assert (
        f"{TAB}/{scene.competition}/teams/{team}/remove?{scene.ctx}",
        "Remove",
    ) in html.link_pairs(teams, "main")


def test_the_remove_confirmations(scene: Scene) -> None:
    """US5-2–US5-5, FR-029–FR-031: the texts, Remove and Cancel at the entry."""
    kept, deleted = questions_of(scene, 2)
    comets = make_team(scene.engine, scene.school, "Comets")
    for question in (kept, deleted):
        add_competition_question(scene.engine, scene.competition, question)
    add_competition_team(scene.engine, scene.competition, comets)
    with Session(scene.engine) as session:
        delete_question(session, olena_id(scene.engine), deleted)
    cases = [
        ("questions", kept, f"Remove question {kept} from “Spring round”?",
         "The question stays in the question bank and can be added again."),
        ("questions", deleted, f"Remove question {deleted} from “Spring round”?",
         "The question was deleted from the question bank and cannot be added again."),
        ("teams", comets, "Remove team “Comets” of School No. 5, Kyiv from “Spring round”?",
         "The team and its members are not changed, and the team can be added again."),
    ]  # fmt: skip
    before = snapshot(scene.engine)
    for kind, entry, question, consequence in cases:
        body = get(scene.olena, page_of(scene, f"{kind}/{entry}/remove", "&back=2"))
        assert html.h1(body) == question
        assert consequence in html.text(body, "main")
        cancel = f"{TAB}/{scene.competition}/{kind}?{scene.ctx}&p=2#{kind[:-1]}-{entry}"
        assert (cancel, "Cancel") in html.link_pairs(body, "main")
        assert back_link(body) == (cancel, f"Back to the {kind}")
        (post,) = [f for f in html.forms(body, "main") if f.method == "post"]
        assert post.action == f"{TAB}/{scene.competition}/{kind}/{entry}/remove"
        assert [b.text for b in post.buttons] == ["Remove"]
        assert "destructive" in post.buttons[0].attrs.get("class", "")
        assert [(i.name, i.value) for i in post.inputs] == [
            ("subject", str(scene.chemistry)),
            ("status", ""),
            ("page", "1"),
            ("back", "2"),
        ]
    assert snapshot(scene.engine) == before


def test_removing_lands_at_the_row_that_took_its_place(scene: Scene) -> None:
    """US5-6, US5-7, FR-032, FR-033."""
    ids = questions_of(scene, 12)
    for question in ids:
        add_competition_question(scene.engine, scene.competition, question)
    bank = snapshot(scene.engine)["questions"]
    response = remove(scene.olena, scene, "questions", ids[3])
    assert address(response) == (
        f"{TAB}/{scene.competition}/questions",
        {"subject": [str(scene.chemistry)]},
        f"question-{ids[4]}",
    )
    body = follow(scene.olena, response)
    assert notices(body) == [("success", f"Question {ids[3]} was removed from “Spring round”")]
    assert ids[3] not in card_ids(body)
    assert snapshot(scene.engine)["questions"] == bank
    # 11 left: removing the only one of page 2 leads to page 1, at its last row.
    response = remove(scene.olena, scene, "questions", ids[11], back="2")
    assert address(response)[1:] == ({"subject": [str(scene.chemistry)]}, f"question-{ids[10]}")
    response = remove(scene.olena, scene, "questions", ids[10], back="2")
    assert address(response)[1:] == ({"subject": [str(scene.chemistry)]}, f"question-{ids[9]}")


def test_removing_the_last_one_shows_the_empty_state(scene: Scene) -> None:
    """FR-032, spec Edge Cases."""
    kn21 = make_class(scene.engine, scene.school)
    comets = make_team(scene.engine, scene.school, "Comets")
    make_member(scene.engine, comets, enrolled(scene.engine, "taras@example.org", kn21))
    add_competition_team(scene.engine, scene.competition, comets)
    before = snapshot(scene.engine)
    response = remove(scene.olena, scene, "teams", comets)
    assert address(response) == (
        f"{TAB}/{scene.competition}/teams",
        {"subject": [str(scene.chemistry)]},
        "",
    )
    body = follow(scene.olena, response)
    assert notices(body) == [("success", "Team “Comets” was removed from “Spring round”")]
    assert empty_state(body) == ("No teams in this competition yet", "Add teams with Add team.")
    after = snapshot(scene.engine)
    assert after["teams"] == before["teams"]
    assert after["competition_teams"] == []


def test_removed_questions_are_offered_again_unless_deleted(scene: Scene) -> None:
    """US5-8, US5-9."""
    kept, deleted, other = questions_of(scene, 3)
    for question in (kept, deleted, other):
        add_question(scene.olena, scene, question)
    with Session(scene.engine) as session:
        delete_question(session, olena_id(scene.engine), deleted)
        update_question(session, olena_id(scene.engine), kept, "Current", "Current answer")
    for question in (kept, deleted):
        assert remove(scene.olena, scene, "questions", question).status_code == 303
    offered = card_ids(get(scene.olena, page_of(scene, "questions/add")))
    assert kept in offered and deleted not in offered
    not_found(add_question(scene.olena, scene, deleted), QUESTION_NOT_FOUND)
    add_question(scene.olena, scene, kept)
    body = get(scene.olena, page_of(scene, "questions"))
    assert card_ids(body) == [other, kept]
    assert cards(body)[-1].boxes == ["Current", "Current answer"]


def test_a_stale_confirmation_is_not_in(scene: Scene) -> None:
    """US7-5, FR-036, research R10: another teacher removed it first."""
    question = make_question(scene.engine, scene.chemistry)
    add_competition_question(scene.engine, scene.competition, question)
    url = page_of(scene, f"questions/{question}/remove")
    assert scene.olena.get(url).status_code == 200
    assert remove(scene.olena, scene, "questions", question).status_code == 303
    for response in (
        scene.olena.get(url, follow_redirects=False),
        remove(scene.olena, scene, "questions", question),
    ):
        assert address(response) == (
            f"{TAB}/{scene.competition}/questions",
            {"subject": [str(scene.chemistry)]},
            "",
        )
        assert notices(follow(scene.olena, response)) == [
            ("info", f"Question {question} is not in “Spring round”")
        ]


# ---------------------------------------------------------------------------------------------
# User story 7: changes stop when the competition leaves Upcoming
# ---------------------------------------------------------------------------------------------

REASONS = {
    "in_progress": "“Spring round” has already started and its {kind} can no longer be changed.",
    "cancelled": "“Spring round” has been cancelled and its {kind} can no longer be changed.",
    "finished": "“Spring round” has finished and its {kind} can no longer be changed.",
}


def entries_of(scene: Scene, competition: int) -> tuple[int, int, int, int]:
    """A question and a team in the competition, and one of each to add."""
    in_question, new_question = questions_of(scene, 2)
    in_team = make_team(scene.engine, scene.school, f"In {competition}")
    new_team = make_team(scene.engine, scene.school, f"New {competition}")
    add_competition_question(scene.engine, competition, in_question)
    add_competition_team(scene.engine, competition, in_team)
    return in_question, new_question, in_team, new_team


@pytest.mark.parametrize("status", ["in_progress", "cancelled", "finished"])
def test_nothing_changes_once_the_competition_is_not_upcoming(
    scene: Scene, clock: Callable[[timedelta], datetime], status: str
) -> None:
    """US7-1–US7-3, FR-034: the lists are read-only for every teacher; every add and remove page
    and action is refused, with the way back to the list at `back`."""
    competition = make_competition(
        scene.engine,
        scene.chemistry,
        "Spring round",
        starts_at=START,
        cancelled=status == "cancelled",
        stopped=status == "finished",
    ) if status != "in_progress" else scene.competition  # fmt: skip
    in_question, new_question, in_team, new_team = entries_of(scene, competition)
    if status == "in_progress":
        scene.clock(START - NOW)
    for browser in (scene.olena, scene.mykola):
        for kind in ("questions", "teams"):
            body = get(browser, page_of(scene, kind, competition=competition))
            assert heading_action(body) == []
            assert "Remove" not in html.text(body, "main")
    kyiv = region_of(scene.engine, scene.school)
    before = snapshot(scene.engine)
    for kind, response in [
        ("questions", scene.olena.get(page_of(scene, "questions/add", "&back=2", competition))),
        ("questions", add_question(scene.olena, scene, new_question, competition, back="2")),
        ("questions", scene.olena.get(
            page_of(scene, f"questions/{in_question}/remove", "&back=2", competition))),
        ("questions", remove(scene.olena, scene, "questions", in_question, competition, back="2")),
        ("teams", scene.olena.get(page_of(scene, "teams/add", "&back=2", competition))),
        ("teams", add_team(scene.olena, scene, new_team, kyiv, competition, back="2")),
        ("teams", scene.olena.get(
            page_of(scene, f"teams/{in_team}/remove", "&back=2", competition))),
        ("teams", remove(scene.olena, scene, "teams", in_team, competition, back="2")),
    ]:  # fmt: skip
        back = f"{TAB}/{competition}/{kind}?{scene.ctx}&p=2"
        refused(response, kind, REASONS[status].format(kind=kind), back)
    assert snapshot(scene.engine) == before


def test_the_start_passing_with_the_add_page_open(scene: Scene) -> None:
    """US7 story, spec Edge Cases: opened at 09:58, sent at 10:01."""
    question = make_question(scene.engine, scene.chemistry)
    scene.clock(START - NOW - timedelta(minutes=2))
    assert scene.olena.get(page_of(scene, "questions/add")).status_code == 200
    scene.clock(timedelta(minutes=3))
    before = snapshot(scene.engine)
    refused(
        add_question(scene.olena, scene, question),
        "questions",
        REASONS["in_progress"].format(kind="questions"),
        page_of(scene, "questions"),
    )
    assert snapshot(scene.engine) == before


def test_a_cancellation_with_the_remove_confirmation_open(scene: Scene) -> None:
    """Spec Edge Cases."""
    team = make_team(scene.engine, scene.school, "Comets")
    add_competition_team(scene.engine, scene.competition, team)
    assert scene.olena.get(page_of(scene, f"teams/{team}/remove")).status_code == 200
    with Session(scene.engine) as session:
        cancel_competition(session, olena_id(scene.engine), scene.competition, scene.chemistry,
                           None)  # fmt: skip
    before = snapshot(scene.engine)
    refused(
        remove(scene.olena, scene, "teams", team),
        "teams",
        REASONS["cancelled"].format(kind="teams"),
        page_of(scene, "teams"),
    )
    assert snapshot(scene.engine) == before


def test_sending_twice_and_reloading_change_once(scene: Scene) -> None:
    """US7-4–US7-6, FR-035, FR-036, FR-038, SC-008."""
    question = make_question(scene.engine, scene.chemistry)
    comets = make_team(scene.engine, scene.school, "Comets")
    kyiv = region_of(scene.engine, scene.school)
    first = add_question(scene.olena, scene, question)
    second = add_question(scene.olena, scene, question)
    assert notices(follow(scene.olena, second)) == [
        ("info", f"Question {question} is already in “Spring round”")
    ]
    add_team(scene.olena, scene, comets, kyiv)
    assert notices(follow(scene.olena, add_team(scene.olena, scene, comets, kyiv))) == [
        ("info", "Team “Comets” is already in “Spring round”")
    ]
    after_adding = snapshot(scene.engine)
    assert len(after_adding["competition_questions"]) == 1
    assert len(after_adding["competition_teams"]) == 1
    follow(scene.olena, first)
    assert snapshot(scene.engine) == after_adding
    removed = remove(scene.olena, scene, "teams", comets)
    assert notices(follow(scene.olena, remove(scene.olena, scene, "teams", comets))) == [
        ("info", "Team “Comets” is not in “Spring round”")
    ]
    after_removing = snapshot(scene.engine)
    for _ in range(2):
        follow(scene.olena, removed)
    assert snapshot(scene.engine) == after_removing


def test_a_notice_of_another_competition_or_kind_is_ignored(scene: Scene) -> None:
    """Research R9."""
    question = make_question(scene.engine, scene.chemistry)
    other = make_competition(scene.engine, scene.chemistry, "Autumn round", starts_at=START)
    response = add_question(scene.olena, scene, question)
    token = parse_qs(urlsplit(response.headers["location"]).query)["notice"][0]
    for url in (
        page_of(scene, "questions/add", f"&notice={token}", other),
        page_of(scene, "teams", f"&notice={token}"),
        page_of(scene, "questions", f"&notice={token}x"),
    ):
        assert notices(get(scene.olena, url)) == []
    assert notices(get(scene.olena, page_of(scene, "questions", f"&notice={token}"))) == [
        ("success", f"Question {question} was added to “Spring round”")
    ]


# ---------------------------------------------------------------------------------------------
# User story 8: deleting a team or a question elsewhere
# ---------------------------------------------------------------------------------------------


def test_deleting_a_team_on_the_teams_tab(scene: Scene, client_as: ClientAs) -> None:
    """US8-1–US8-4, FR-040, FR-041: by a teacher with Write and without the setting."""
    make_teacher(
        scene.engine,
        app.state.settings,
        email="taras@example.org",
        institutions={scene.school: AccessLevel.WRITE},
        first="Taras",
        last="Writer",
    )
    taras = client_as("taras@example.org")
    comets = make_team(scene.engine, scene.school, "Comets")
    competitions = {
        "upcoming": scene.competition,
        "in_progress": make_competition(scene.engine, scene.chemistry, "Winter round",
                                        starts_at=at(1, 8)),
        "cancelled": make_competition(scene.engine, scene.chemistry, "Autumn round",
                                      starts_at=START, cancelled=True),
        "finished": make_competition(scene.engine, scene.chemistry, "Summer round",
                                     starts_at=at(1, 7), stopped=True),
    }  # fmt: skip
    for competition in competitions.values():
        add_competition_team(scene.engine, competition, comets)
    page = get(taras, f"/teacher/teams/{comets}/delete")
    assert (
        "The team will be hidden and taken out of every competition that has not finished. It can"
        " no longer join new competitions." in html.text(page, "main")
    )
    assert taras.post(f"/teacher/teams/{comets}/delete", follow_redirects=False).status_code == 303
    for status, competition in competitions.items():
        rows = team_rows(get(scene.mykola, page_of(scene, "teams", competition=competition)))
        if status == "finished":
            assert rows[f"team-{comets}"][""] == "(deleted)"
        else:
            assert rows == {}, status
    kyiv = region_of(scene.engine, scene.school)
    assert "Comets" not in get(scene.olena, page_of(scene, "teams/add", f"&region={kyiv}"))
    before = snapshot(scene.engine)
    not_found(add_team(scene.olena, scene, comets, kyiv), TEAM_NOT_FOUND)
    assert snapshot(scene.engine) == before


def test_deleting_a_question_in_the_bank(scene: Scene) -> None:
    """US8-5, FR-039: the copy stays, marked; it is no longer offered or addable anywhere; the
    bank's confirmation keeps its wording."""
    question = make_question(scene.engine, scene.chemistry)
    other = make_competition(scene.engine, scene.chemistry, "Autumn round", starts_at=START)
    add_question(scene.olena, scene, question)
    confirmation = get(scene.olena, f"/teacher/questions/{question}/delete")
    assert "can no longer be added to new competitions" in html.text(confirmation, "main")
    with Session(scene.engine) as session:
        delete_question(session, olena_id(scene.engine), question)
    (card,) = cards(get(scene.mykola, page_of(scene, "questions")))
    assert card.notes == ["Deleted from the question bank"]
    for competition in (scene.competition, other):
        assert question not in card_ids(
            get(scene.olena, page_of(scene, "questions/add", competition=competition))
        )
    not_found(add_question(scene.olena, scene, question, other), QUESTION_NOT_FOUND)


def test_deactivating_takes_no_team_out(scene: Scene) -> None:
    """US8-6, FR-042."""
    comets = make_team(scene.engine, scene.school, "Comets")
    add_competition_team(scene.engine, scene.competition, comets)
    kyiv = region_of(scene.engine, scene.school)
    with Session(scene.engine) as session:
        set_institution_active(session, kyiv, scene.school, False)
    assert f"team-{comets}" in team_rows(get(scene.mykola, page_of(scene, "teams")))
    with Session(scene.engine) as session:
        set_region_active(session, kyiv, False)
    assert f"team-{comets}" in team_rows(get(scene.mykola, page_of(scene, "teams")))


# ---------------------------------------------------------------------------------------------
# User story 9: only teachers read, and only managers change
# ---------------------------------------------------------------------------------------------

PREFIX = f"{TAB}/{{competition_id:int}}/"
ENTRY_ROUTES = sorted(
    (method, path)
    for path, methods, _ in ALL_ROUTES
    if path.startswith((f"{PREFIX}questions", f"{PREFIX}teams"))
    for method in methods
    if method in ("GET", "POST")
)
READ_ROUTES = [("GET", f"{PREFIX}questions"), ("GET", f"{PREFIX}teams")]
MANAGE_ROUTES = [route for route in ENTRY_ROUTES if route not in READ_ROUTES]


def concrete(path: str, competition: int | str, entry: int | str, query: str) -> str:
    path = path.replace("{competition_id:int}", str(competition))
    path = re.sub(r"\{(question|team)_id:int\}", str(entry), path)
    return f"{path}?{query}"


def send(browser: TestClient, method: str, url: str, data: dict[str, str], **kw: Any) -> Any:
    if method == "POST":
        return browser.post(url.split("?")[0], data=data, follow_redirects=False, **kw)
    return browser.get(url, follow_redirects=False, **kw)


def sweep_form(subject: int | str, entry: int | str, region: int | str) -> dict[str, str]:
    return {
        "subject": str(subject),
        "status": "",
        "page": "1",
        "back": "1",
        "p": "1",
        "region": str(region),
        "question": str(entry),
        "team": str(entry),
    }


def test_the_sweep_has_every_route() -> None:
    assert len(ENTRY_ROUTES) == 10
    assert len(MANAGE_ROUTES) == 8


@pytest.mark.parametrize(("method", "path"), ENTRY_ROUTES)
def test_other_roles_are_refused(
    scene: Scene, client: TestClient, client_as: ClientAs, method: str, path: str
) -> None:
    """US9-1, FR-044: through addresses and forms, nothing changes; anonymous visitors are sent
    to sign in."""
    question = make_question(scene.engine, scene.chemistry)
    add_competition_question(scene.engine, scene.competition, question)
    url = concrete(path, scene.competition, question, scene.ctx)
    data = sweep_form(scene.chemistry, question, region_of(scene.engine, scene.school))
    before = snapshot(scene.engine)
    for email, role, label in (
        (ADMIN_EMAIL, AUTO, "Administrator"),
        (STUDENT_EMAIL, AUTO, "Student"),
        (ADMIN_STUDENT_EMAIL, Role.STUDENT, "Student"),
    ):
        denied(send(client_as(email, role), method, url, data), label)
    anonymous = send(client, method, url, data)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"].split("?")[0] == "/login"
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), MANAGE_ROUTES)
@pytest.mark.parametrize("target", ["listed", "missing", "unknown-subject", "hidden"])
def test_a_teacher_without_the_setting_is_refused_before_any_id_is_read(
    scene: Scene, method: str, path: str, target: str
) -> None:
    """US9-2, FR-045 step 2, SC-003."""
    question = make_question(scene.engine, scene.chemistry)
    biology = make_subject(scene.engine, "Biology")
    hidden = make_competition(scene.engine, biology, starts_at=START)
    with Session(scene.engine) as session:
        set_subject_active(session, biology, False)
    competition, subject, entry = {
        "listed": (scene.competition, scene.chemistry, question),
        "missing": (MISSING, scene.chemistry, MISSING),
        "unknown-subject": (scene.competition, "abc", "abc"),
        "hidden": (hidden, biology, question),
    }[target]
    url = concrete(
        path, competition, entry if str(entry).isdigit() else MISSING, f"subject={subject}"
    )
    before = snapshot(scene.engine)
    denied(send(scene.mykola, method, url, sweep_form(subject, entry, "abc")))
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), READ_ROUTES)
def test_every_teacher_reads_both_lists(scene: Scene, method: str, path: str) -> None:
    for browser in (scene.olena, scene.mykola):
        url = concrete(path, scene.competition, 0, scene.ctx)
        assert send(browser, method, url, {}).status_code == 200


@pytest.mark.parametrize(("method", "path"), ENTRY_ROUTES)
def test_the_subject_and_the_competition_come_before_the_status(
    scene: Scene, method: str, path: str
) -> None:
    """US9-3, US9-8, FR-045 step 3: unknown, mismatched and hidden competitions are not found,
    before any status refusal (each one here is cancelled or hidden)."""
    cancelled = make_competition(
        scene.engine, scene.physics, "Autumn round", starts_at=START, cancelled=True
    )
    biology = make_subject(scene.engine, "Biology")
    make_competition(scene.engine, biology, "Old", starts_at=at(1, 7), stopped=True)
    offered_hidden = make_competition(scene.engine, biology, starts_at=START, cancelled=True)
    astronomy = make_subject(scene.engine, "Astronomy")
    unoffered_hidden = make_competition(scene.engine, astronomy, starts_at=START)
    with Session(scene.engine) as session:
        set_subject_active(session, biology, False)
        set_subject_active(session, astronomy, False)
    region = region_of(scene.engine, scene.school)
    before = snapshot(scene.engine)
    for competition, subject, page in [
        (cancelled, scene.chemistry, COMPETITION_NOT_FOUND),
        (MISSING, scene.chemistry, COMPETITION_NOT_FOUND),
        (int("9" * 12), scene.chemistry, COMPETITION_NOT_FOUND),
        (offered_hidden, biology, COMPETITION_NOT_FOUND),
        (unoffered_hidden, astronomy, SUBJECT_NOT_FOUND),
        (scene.competition, MISSING, SUBJECT_NOT_FOUND),
        (scene.competition, "1e9999", SUBJECT_NOT_FOUND),
    ]:
        url = concrete(path, competition, MISSING, f"subject={subject}")
        not_found(send(scene.olena, method, url, sweep_form(subject, MISSING, region)), page)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), MANAGE_ROUTES)
def test_the_status_comes_before_the_entry(scene: Scene, method: str, path: str) -> None:
    """FR-045 step 4: a cancelled competition with unknown question, team and region ids."""
    cancelled = make_competition(
        scene.engine, scene.chemistry, "Spring round", starts_at=START, cancelled=True
    )
    url = concrete(path, cancelled, MISSING, scene.ctx)
    response = send(scene.olena, method, url, sweep_form(scene.chemistry, MISSING, MISSING))
    assert response.status_code == 409


@pytest.mark.parametrize("case", ["other-region", "deleted", "institution", "region", "abc"])
def test_a_team_that_cannot_be_added_is_not_found(scene: Scene, case: str) -> None:
    """US9-6, FR-045 step 5."""
    comets = make_team(scene.engine, scene.school, "Comets", deleted=case == "deleted")
    kyiv = region_of(scene.engine, scene.school)
    region = region_of(scene.engine, scene.academy) if case == "other-region" else kyiv
    if case in ("institution", "region"):
        other = make_institution(scene.engine, "Odesa College", "Odesa")
        comets = make_team(scene.engine, other, "Odesa team")
        odesa = region_of(scene.engine, other)
        with Session(scene.engine) as session:
            if case == "institution":
                set_institution_active(session, odesa, other, False)
            else:
                set_region_active(session, odesa, False)
    before = snapshot(scene.engine)
    not_found(
        add_team(scene.olena, scene, "abc" if case == "abc" else comets, region), TEAM_NOT_FOUND
    )
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("case", ["other-subject", "deleted", "abc", "unknown"])
def test_a_question_that_cannot_be_added_is_not_found(scene: Scene, case: str) -> None:
    """US9-5, FR-045 step 5."""
    question = {
        "other-subject": lambda: make_question(scene.engine, scene.physics),
        "deleted": lambda: make_question(scene.engine, scene.chemistry, deleted=True),
        "abc": lambda: "abc",
        "unknown": lambda: MISSING,
    }[case]()
    before = snapshot(scene.engine)
    not_found(add_question(scene.olena, scene, question), QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == before


def test_unknown_entries_are_not_found_on_removal(scene: Scene) -> None:
    """FR-045 step 5, research R10: an id that names nothing at all, also above any id."""
    for kind, page in (("questions", QUESTION_NOT_FOUND), ("teams", TEAM_NOT_FOUND)):
        for entry in (MISSING, "9" * 30):
            not_found(scene.olena.get(page_of(scene, f"{kind}/{entry}/remove")), page)
            not_found(remove(scene.olena, scene, kind, entry), page)


def test_a_question_deleted_from_the_bank_can_be_removed(scene: Scene) -> None:
    """US9-7."""
    question = make_question(scene.engine, scene.chemistry)
    add_competition_question(scene.engine, scene.competition, question)
    with Session(scene.engine) as session:
        delete_question(session, olena_id(scene.engine), question)
    assert scene.olena.get(page_of(scene, f"questions/{question}/remove")).status_code == 200
    assert remove(scene.olena, scene, "questions", question).status_code == 303


@pytest.mark.parametrize(("method", "path"), [r for r in MANAGE_ROUTES if r[0] == "POST"])
@pytest.mark.parametrize(
    "forged", [{"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://evil.example"}]
)
def test_a_cross_site_action_changes_nothing(
    scene: Scene, method: str, path: str, forged: dict[str, str]
) -> None:
    """US9-9, FR-047."""
    question = make_question(scene.engine, scene.chemistry)
    team = make_team(scene.engine, scene.school, "Comets")
    add_competition_question(scene.engine, scene.competition, question)
    add_competition_team(scene.engine, scene.competition, team)
    entry = team if "teams" in path else question
    url = concrete(path, scene.competition, entry, scene.ctx)
    data = sweep_form(scene.chemistry, entry, region_of(scene.engine, scene.school))
    before = snapshot(scene.engine)
    assert send(scene.olena, method, url, data, headers=forged).status_code == 403
    assert snapshot(scene.engine) == before


def olena_id(engine: Engine) -> int:
    with Session(engine) as session:
        user = get_user_by_email(session, OLENA)
        assert user is not None and user.id is not None
        return user.id


def test_the_setting_removed_with_the_add_page_open(scene: Scene) -> None:
    """Spec Edge Cases, FR-046."""
    question = make_question(scene.engine, scene.chemistry)
    assert scene.olena.get(page_of(scene, "questions/add")).status_code == 200
    with Session(scene.engine) as session:
        view = get_teacher(session, olena_id(scene.engine))
        update_teacher(
            session,
            olena_id(scene.engine),
            view.first_name,
            view.last_name,
            {link.institution_id: link.access_level for link in view.links},
            can_manage_competitions=False,
        )
    before = snapshot(scene.engine)
    denied(add_question(scene.olena, scene, question))
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    ("method", "suffix", "data"),
    [
        ("GET", "questions?subject=1e9999&p=-1&status=%00", None),
        ("GET", "teams?subject=%00&p=%FF&notice=%FF&page=x", None),
        ("GET", "questions/add?subject={s}&back=%00&p=x", None),
        ("GET", "teams/add?subject={s}&region=%D9%A3&back=-1", None),
        ("GET", "questions/{big}/remove?subject={s}&back=x", None),
        ("POST", "questions", {}),
        ("POST", "teams", {"subject": "{s}", "region": "x", "team": "y", "p": "%"}),
        ("POST", "questions/{big}/remove", {"subject": "{s}", "back": "1e9"}),
        ("POST", "teams/1/remove", {}),
    ],
)
def test_no_input_gets_a_json_422(
    scene: Scene, method: str, suffix: str, data: dict[str, str] | None
) -> None:
    """Every value is read as a string: odd values get a page, never FastAPI's JSON."""
    big = "9" * 30
    url = f"{TAB}/{scene.competition}/" + suffix.format(s=scene.chemistry, big=big)
    for browser in (scene.olena, scene.mykola):
        if method == "GET":
            response = browser.get(url, follow_redirects=False)
        else:
            values = {k: v.format(s=scene.chemistry) for k, v in (data or {}).items()}
            response = browser.post(url, data=values, follow_redirects=False)
        assert response.status_code != 422, (url, response.text)
        assert "application/json" not in response.headers.get("content-type", "")


def test_a_path_id_that_is_not_a_number_matches_no_route(scene: Scene) -> None:
    """Contracts http-routes.md §Order of checks: the same plain 404 for every role."""
    for browser in (scene.olena, scene.mykola):
        for suffix in ("abc/questions", f"{scene.competition}/questions/abc/remove",
                       f"{scene.competition}/teams/abc/remove"):  # fmt: skip
            response = browser.get(f"{TAB}/{suffix}?{scene.ctx}")
            assert response.status_code == 404
            assert "Competition not found" not in response.text


# ---------------------------------------------------------------------------------------------
# User story 10: deactivated subjects
# ---------------------------------------------------------------------------------------------


def test_a_deactivated_subject(scene: Scene) -> None:
    """US10-1, US10-2, FR-043: its competitions that are not finished are not found on every
    page and action, forms opened before included; its finished one shows both lists
    read-only, with the copies the bank now hides, and its changes are refused."""
    finished = make_competition(
        scene.engine, scene.chemistry, "Summer round", starts_at=at(1, 7), stopped=True
    )
    running = make_competition(scene.engine, scene.chemistry, "Winter", starts_at=at(1, 8))
    cancelled = make_competition(
        scene.engine, scene.chemistry, "Autumn", starts_at=START, cancelled=True
    )
    question = make_question(scene.engine, scene.chemistry, "Hidden by the bank")
    team = make_team(scene.engine, scene.school, "Comets")
    for competition in (scene.competition, running, cancelled, finished):
        add_competition_question(scene.engine, competition, question)
        add_competition_team(scene.engine, competition, team)
    assert scene.olena.get(page_of(scene, "questions/add")).status_code == 200
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    kyiv = region_of(scene.engine, scene.school)
    before = snapshot(scene.engine)
    for competition in (scene.competition, running, cancelled):
        for response in (
            scene.mykola.get(page_of(scene, "questions", competition=competition)),
            scene.mykola.get(page_of(scene, "teams", competition=competition)),
            scene.olena.get(page_of(scene, "questions/add", competition=competition)),
            scene.olena.get(page_of(scene, "teams/add", competition=competition)),
            scene.olena.get(page_of(scene, f"teams/{team}/remove", competition=competition)),
            add_question(scene.olena, scene, question, competition),
            add_team(scene.olena, scene, team, kyiv, competition),
            remove(scene.olena, scene, "questions", question, competition),
            remove(scene.olena, scene, "teams", team, competition),
        ):
            not_found(response, COMPETITION_NOT_FOUND)
    questions = get(scene.mykola, page_of(scene, "questions", competition=finished))
    assert [c.boxes[0] for c in cards(questions)] == ["Hidden by the bank"]
    teams = get(scene.olena, page_of(scene, "teams", competition=finished))
    assert [r["Team"] for r in team_rows(teams).values()] == ["Comets"]
    assert heading_action(teams) == []
    row_menu = menus(get(scene.mykola, f"{TAB}?{scene.ctx}"))[f"competition-{finished}"]
    assert [text for text, _ in row_menu] == ["Questions", "Teams"]
    for kind, response in (
        ("questions", scene.olena.get(page_of(scene, "questions/add", competition=finished))),
        ("teams", scene.olena.get(page_of(scene, "teams/add", competition=finished))),
        ("questions", remove(scene.olena, scene, "questions", question, finished)),
        ("teams", remove(scene.olena, scene, "teams", team, finished)),
    ):
        assert response.status_code == 409
        reason = f"“Summer round” has finished and its {kind} can no longer be changed."
        assert reason in html.text(response.text, "main")
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# Milestone 12.3: the Teams page stays as it is (specs/012.3-team-answers US5, FR-003)
# ---------------------------------------------------------------------------------------------


def test_the_teams_page_never_offers_enter_answers(scene: Scene, client_as: ClientAs) -> None:
    """US5-1, US5-2: every team from every institution, read-only without the setting, with Add
    team and Remove only for Olena on an Upcoming competition, and in no status Enter answers or
    an Answered column; a teacher with no link (the cast teacher) sees the same."""
    competitions = {
        "upcoming": scene.competition,
        "in_progress": make_competition(
            scene.engine, scene.chemistry, "Running", starts_at=at(1, 8)
        ),
        "cancelled": make_competition(
            scene.engine, scene.chemistry, "Off", starts_at=at(14), cancelled=True
        ),
        "finished": make_competition(
            scene.engine, scene.chemistry, "Done", starts_at=at(1, 7), stopped=True
        ),
    }
    teams = [
        make_team(scene.engine, scene.school, "Comets"),
        make_team(scene.engine, scene.academy, "Lions"),
        make_team(scene.engine, scene.lyceum, "Novas"),
    ]
    for competition in competitions.values():
        for team in teams:
            add_competition_team(scene.engine, competition, team)
    for status, competition in competitions.items():
        for browser in (scene.olena, scene.mykola, client_as(TEACHER_EMAIL)):
            body = get(browser, page_of(scene, "teams", competition=competition))
            listed = sorted(row["Team"] for g in region_groups(body) for row in g.rows)
            assert listed == ["Comets", "Lions", "Novas"], status
            assert "Enter answers" not in body and "Answered" not in body, status
            can_change = browser is scene.olena and status == "upcoming"
            assert ("Add team" in body) is can_change, status
            assert (">Remove<" in body) is can_change, status
