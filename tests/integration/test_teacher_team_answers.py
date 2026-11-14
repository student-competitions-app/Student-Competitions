"""A competition's team answers, end to end through the test client: the team answers page, the
answer sheet and its save, the refusals, the access rules and team deletion.

See specs/012.3-team-answers/spec.md US1–US11, contracts/http-routes.md and research R17. Every
case runs on both engines. The clock is fixed at 1 March 2027 09:00 UTC by patching
`app.services.competitions.utc_now`, and moved forward where a start must pass; no test waits.
The browser's zone is the `sc_time_zone` cookie, set as `time-zone.js` would.

- Taras: a real teacher without **Can manage competitions**, with **Write** access to School
  No. 5 and Gymnasium No. 1 (Kyiv) and **Read** access to Lyceum No. 2 (Lviv);
- Oksana: **Write** access to School No. 5; Iryna: **Read** access to Lyceum No. 2 only;
- Olena: **Can manage competitions**, linked only to "District Office" (Kyiv), which has no team;
- "Spring round": an In progress competition of Chemistry, started 1 March 2027, 10:00 in Kyiv,
  with 6 questions; "Comets" (School No. 5), "Lions" (Lyceum No. 2) and "Novas" (Kyiv Lyceum,
  which nobody is linked to) are in it.

The access sweep is built from the router's own route table, so a later route is covered too.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.main import app
from app.models import AccessLevel, Role, Team, TeamAnswer
from app.schemas.teachers import MAX_ID
from app.services.competitions import cancel_competition, finish_competition
from app.services.institutions import set_institution_active
from app.services.regions import set_region_active
from app.services.subjects import set_subject_active
from app.services.teachers import update_teacher
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
    grade_answer,
    make_class,
    make_competition,
    make_institution,
    make_member,
    make_question,
    make_subject,
    make_teacher,
    make_team,
    save_team_answer,
)
from tests.integration.test_routes import ALL_ROUTES
from tests.integration.test_teacher_competition_entries import (
    denied,
    follow,
    get,
    not_found,
    region_groups,
    region_of,
)
from tests.integration.test_team_service import enrolled

TARAS = "taras@example.org"
OKSANA = "oksana@example.org"
IRYNA = "iryna@example.org"
OLENA = "olena@example.org"
TAB = "/teacher/competitions"
KYIV = "Europe/Kyiv"
NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 8, 0, tzinfo=UTC)
"""1 March 2027, 10:00 in Kyiv."""
LATER = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
MISSING = 999_999

SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist")
COMPETITION_NOT_FOUND = ("Competition not found", "This competition does not exist")
TEAM_NOT_FOUND = ("Team not found", "This team does not exist, or it is not in this competition.")
QUESTION_NOT_FOUND = ("Question not found", "This question is not in this competition.")
TOO_LONG = "Answer to question {n} can be at most 2,000 characters."


@dataclass(frozen=True)
class Scene:
    engine: Engine
    taras: TestClient
    oksana: TestClient
    iryna: TestClient
    olena: TestClient
    taras_id: int
    chemistry: int
    physics: int
    competition: int
    copies: list[int]
    school: int
    gymnasium: int
    lyceum: int
    unlinked: int
    comets: int
    lions: int
    novas: int
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
    school = make_institution(engine, "School No. 5", "Kyiv")
    gymnasium = make_institution(engine, "Gymnasium No. 1", "Kyiv")
    lyceum = make_institution(engine, "Lyceum No. 2", "Lviv")
    unlinked = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    office = make_institution(engine, "District Office", "Kyiv")
    taras_id = make_teacher(
        engine,
        settings,
        email=TARAS,
        institutions={
            school: AccessLevel.WRITE,
            gymnasium: AccessLevel.WRITE,
            lyceum: AccessLevel.READ,
        },
        first="Taras",
        last="Shevchenko",
    )
    make_teacher(
        engine, settings, email=OKSANA, institutions={school: AccessLevel.WRITE}, first="Oksana"
    )
    make_teacher(
        engine, settings, email=IRYNA, institutions={lyceum: AccessLevel.READ}, first="Iryna"
    )
    make_teacher(
        engine, settings, email=OLENA, institutions={office: AccessLevel.READ}, can_manage=True
    )
    browsers = [client_as(email) for email in (TARAS, OKSANA, IRYNA, OLENA)]
    for browser in browsers:
        browser.cookies.set("sc_time_zone", KYIV)
    chemistry = make_subject(engine, "Chemistry")
    competition = make_competition(engine, chemistry, starts_at=STARTED)
    copies = [
        add_competition_question(
            engine,
            competition,
            make_question(engine, chemistry, f"Question text {n}?", f"Reference answer {n}."),
        )
        for n in range(1, 7)
    ]
    comets = make_team(engine, school, "Comets")
    lions = make_team(engine, lyceum, "Lions")
    novas = make_team(engine, unlinked, "Novas")
    for team in (comets, lions, novas):
        add_competition_team(engine, competition, team)
    return Scene(
        engine,
        *browsers,
        taras_id=taras_id,
        chemistry=chemistry,
        physics=make_subject(engine, "Physics"),
        competition=competition,
        copies=copies,
        school=school,
        gymnasium=gymnasium,
        lyceum=lyceum,
        unlinked=unlinked,
        comets=comets,
        lions=lions,
        novas=novas,
        clock=clock,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def answers_url(s: Scene, query: str = "", competition: int | None = None) -> str:
    return f"{TAB}/{competition or s.competition}/answers?{s.ctx}{query}"


def sheet_url(
    s: Scene, team: int | str | None = None, query: str = "", competition: int | None = None
) -> str:
    return f"{TAB}/{competition or s.competition}/answers/{team or s.comets}?{s.ctx}{query}"


def answer_form(s: Scene, answers: dict[int, str], back: str = "1") -> dict[str, str]:
    """The sheet's form: the context, `back` and one `answer-<id>` per question given."""
    form = {"subject": str(s.chemistry), "status": "", "page": "1", "back": back}
    return form | {f"answer-{copy}": text for copy, text in answers.items()}


def post_answers(
    s: Scene,
    browser: TestClient,
    answers: dict[int, str],
    team: int | str | None = None,
    competition: int | None = None,
    **kw: Any,
) -> Any:
    url = f"{TAB}/{competition or s.competition}/answers/{team or s.comets}"
    return browser.post(url, data=answer_form(s, answers), follow_redirects=False, **kw)


def post_raw(s: Scene, browser: TestClient, pairs: list[tuple[str, str]]) -> Any:
    """A hand-made body, which may repeat a field name."""
    body = urlencode([("subject", str(s.chemistry)), ("back", "1"), *pairs])
    return browser.post(
        f"{TAB}/{s.competition}/answers/{s.comets}",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def stored(s: Scene, team: int | None = None, competition: int | None = None) -> dict[int, str]:
    with Session(s.engine) as session:
        rows = session.exec(
            select(TeamAnswer).where(
                TeamAnswer.competition_id == (competition or s.competition),
                TeamAnswer.team_id == (team or s.comets),
            )
        )
        return {row.competition_question_id: row.text for row in rows}


def snapshot(engine: Engine) -> list[tuple[int, int, int, str]]:
    with Session(engine) as session:
        return sorted(
            (a.competition_id, a.team_id, a.competition_question_id, a.text)
            for a in session.exec(select(TeamAnswer))
        )


def sheet_forms(body: str) -> list[html.Form]:
    """The answer sheet's form, if the page has one (not the frame's theme or sign-out forms)."""
    return [f for f in html.forms(body, "main") if "/answers/" in f.action]


def fields(body: str) -> dict[str, str]:
    """The sheet's answer fields: `answer-<id>` → the text in the field."""
    (form,) = sheet_forms(body)
    return {i.name: i.value for i in form.inputs if i.type == "textarea" and i.name}


def sheet_items(body: str) -> list[tuple[str, str, str]]:
    """`(card heading, question text, field label)` of every question of the sheet."""
    (sheet,) = [o for o in html.parse(body).find_all("ol") if "answer-sheet" in o.classes()]
    found = []
    for item in sheet.find_all("li"):
        heading = item.find_all("h3")[0].text()
        text = item.find_all("p")[0].text()
        label = item.find_all("label")[0].text()
        found.append((heading, text, label))
    return found


def actions(body: str) -> dict[str, str]:
    """Each row's actions cell, by team name."""
    found = {}
    for tr in html.parse(body).find_all("tr"):
        cells = {td.attrs.get("data-label"): td for td in tr.find_all("td")}
        if "Team" in cells:
            found[cells["Team"].text()] = cells[""].text()
    return found


def location(response: Any) -> tuple[str, dict[str, list[str]], str]:
    assert response.status_code == 303, response.text
    parts = urlsplit(response.headers["location"])
    return parts.path, parse_qs(parts.query), parts.fragment


def refused(response: Any, name: str, reason: str, s: Scene, competition: int) -> None:
    """The 409 refusal (FR-026), with both ways back to the competitions list."""
    assert response.status_code == 409, response.text
    assert html.h1(response.text) == f"Enter answers for “{name}”?"
    assert reason in html.text(response.text, "main")
    back = f"{TAB}?{s.ctx}#competition-{competition}"
    pairs = html.link_pairs(response.text, "main")
    assert (back, "Back to competitions") in pairs
    assert (back, "Back to the competitions") in pairs


def set_links(s: Scene, **changes: AccessLevel | None) -> None:
    """An administrator's edit of Taras's links (`None` removes one)."""
    links: dict[str, AccessLevel | None] = {
        "school": AccessLevel.WRITE,
        "gymnasium": AccessLevel.WRITE,
        "lyceum": AccessLevel.READ,
    } | changes
    ids = {"school": s.school, "gymnasium": s.gymnasium, "lyceum": s.lyceum}
    with Session(s.engine) as session:
        update_teacher(
            session,
            s.taras_id,
            "Taras",
            "Shevchenko",
            {ids[name]: level for name, level in links.items() if level is not None},
            False,
        )


def no_names_in_addresses(body: str) -> None:
    for href in [link.href for link in html.links(body, "main")]:
        for name in ("Spring", "Comets", "Lions", "School", "Chemistry"):
            assert name not in href, href


# ---------------------------------------------------------------------------------------------
# User story 2: the team answers page
# ---------------------------------------------------------------------------------------------


def test_the_team_answers_page(scene: Scene) -> None:
    """US2-1, US2-2, US2-5–US2-8, US3-1, US3-2: the heading, the details, the back link; only
    Taras's institutions' teams, with the columns, the progress and the actions cell."""
    body = get(scene.taras, answers_url(scene))
    assert html.h1(body) == "Answers of “Spring round”"
    assert ("Subject", "Chemistry") in html.details(body)
    assert ("Start", "1 March 2027, 10:00") in html.details(body)
    assert ("Status", "In progress") in html.details(body)
    assert '<time datetime="2027-03-01T08:00Z">1 March 2027, 10:00</time>' in body
    back = f"{TAB}?{scene.ctx}#competition-{scene.competition}"
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")
    groups = region_groups(body)
    assert [(g.header, [r["Team"] for r in g.rows]) for g in groups] == [
        ("Kyiv · 1 team", ["Comets"]),
        ("Lviv · 1 team", ["Lions"]),
    ]
    assert groups[0].rows == [
        {
            "Team": "Comets",
            "Educational institution": "School No. 5",
            "Active members": "0",
            "Answered": "0 of 6",
            "": "Enter answers",
        }
    ]
    (table,) = html.parse(body).find_all("table")[:1]
    assert [th.text() for th in table.find_all("th")] == [
        "Team",
        "Educational institution",
        "Active members",
        "Answered",
        "Actions",
    ]
    # Replaced by milestone 12.4 FR-036, research R7 (SC-011): a Read institution's team gets
    # **View answers** instead of the "Read access" row note.
    assert actions(body) == {"Comets": "Enter answers", "Lions": "View answers"}
    assert [e for e in html.parse(body).iter() if "row-note" in e.classes()] == []
    assert "Novas" not in body
    links = {link.text: link.href for link in html.links(body, "main") if "/answers/" in link.href}
    assert links == {
        "Enter answers": f"{TAB}/{scene.competition}/answers/{scene.comets}?{scene.ctx}",
        "View answers": f"{TAB}/{scene.competition}/answers/{scene.lions}?{scene.ctx}",
    }
    text = html.text(body, "main")
    assert "Add team" not in text and "Remove" not in text
    assert "<caption>" not in body
    no_names_in_addresses(body)


def test_a_manager_gets_no_add_team_and_no_remove(scene: Scene) -> None:
    """US2-8, FR-011: Olena, with the setting, linked to an institution with no team in it."""
    body = get(scene.olena, answers_url(scene))
    assert "Add team" not in body and ">Remove<" not in body
    assert html.text(body, "main").count("No teams from your educational institutions") == 1


def test_the_progress_column(scene: Scene) -> None:
    """US2-6, US2-7, FR-009: "3 of 6" as plain text in a cell labelled for the phone card."""
    for copy in scene.copies[:3]:
        save_team_answer(scene.engine, scene.competition, scene.comets, copy, "NaCl")
    body = get(scene.taras, answers_url(scene))
    assert '<td data-label="Answered" class="cell-nowrap">3 of 6</td>' in body
    assert region_groups(body)[1].rows[0]["Answered"] == "0 of 6"


def test_twelve_teams_in_two_regions_across_two_pages(scene: Scene) -> None:
    """US2 story, US2-3, US2-4, US2-9: "Teams 1–10 of 12"; Kyiv · 9 teams and Lviv · 3 teams,
    Lviv repeated on page 2; the page kept in the address; out-of-range pages land nearby."""
    for n in range(4):
        add_competition_team(
            scene.engine, scene.competition, make_team(scene.engine, scene.school, f"School {n}")
        )
    for n in range(4):
        add_competition_team(
            scene.engine, scene.competition, make_team(scene.engine, scene.gymnasium, f"Gym {n}")
        )
    for name in ("Leo", "Lynx"):
        add_competition_team(
            scene.engine, scene.competition, make_team(scene.engine, scene.lyceum, name)
        )
    first = get(scene.taras, answers_url(scene))
    second = get(scene.taras, answers_url(scene, "&p=2"))
    shape = [[(g.header, len(g.rows)) for g in region_groups(b)] for b in (first, second)]
    assert shape == [[("Kyiv · 9 teams", 9), ("Lviv · 3 teams", 1)], [("Lviv · 3 teams", 2)]]
    for body, expected in ((first, "Teams 1–10 of 12"), (second, "Teams 11–12 of 12")):
        for label in ("Pages, top", "Pages, bottom"):
            found = html.pagination(body, label)
            assert found is not None and found[0] == expected
    heading_ids = [g.heading_id for b in (first, second) for g in region_groups(b)]
    assert len(set(heading_ids)) == 3
    links = [e.href for e in html.pagination(first, "Pages, top")[1] if e.href]  # type: ignore[index]
    assert f"{TAB}/{scene.competition}/answers?{scene.ctx}&p=2" in links
    for query, expected_body in (("&p=99", second), ("&p=x", first), ("&p=0", first)):
        body = get(scene.taras, answers_url(scene, query))
        assert region_groups(body) == region_groups(expected_body), query
    # Replaced by milestone 12.4 FR-036 (SC-011): **View answers**, not "Read access".
    assert actions(second) == {"Lions": "View answers", "Lynx": "View answers"}


def test_the_back_link_falls_back_without_a_subject(scene: Scene) -> None:
    """Spec Edge Cases: no context in the address leads back to the competition's subject, the
    status All and the page holding it."""
    body = get(scene.taras, f"{TAB}/{scene.competition}/answers")
    back = f"{TAB}?subject={scene.chemistry}#competition-{scene.competition}"
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")


# ---------------------------------------------------------------------------------------------
# User story 1: the answer sheet and its save
# ---------------------------------------------------------------------------------------------


def test_the_answer_sheet(scene: Scene) -> None:
    """US1-1–US1-4, FR-014–FR-016: the heading, the institution, the back link, every question
    with its labelled empty field; no reference answer anywhere."""
    page = get(scene.taras, answers_url(scene))
    (href,) = [link.href for link in html.links(page, "main") if link.text == "Enter answers"]
    body = get(scene.taras, href)
    assert html.h1(body) == "Answers of “Comets” in “Spring round”"
    assert ("Educational institution", "School No. 5") in html.details(body)
    back = f"{TAB}/{scene.competition}/answers?{scene.ctx}#team-{scene.comets}"
    assert (back, "Back to the answers") in html.link_pairs(body, "main")
    assert sheet_items(body) == [
        (f"Question {n}", f"Question text {n}?", f"Answer to question {n}") for n in range(1, 7)
    ]
    for copy in scene.copies:
        attrs = html.control(body, f"answer-{copy}")
        assert attrs["placeholder"] == "Not answered"
        assert attrs["maxlength"] == "2000"
        assert attrs["id"] == f"answer-{copy}"
    assert html.text(body, "main").count("Up to 2,000 characters.") == 6
    assert fields(body) == {f"answer-{copy}": "" for copy in scene.copies}
    assert "Reference answer" not in body
    (form,) = sheet_forms(body)
    assert form.action == f"{TAB}/{scene.competition}/answers/{scene.comets}"
    hidden = {i.name: i.value for i in form.inputs if i.type == "hidden"}
    assert hidden == {"subject": str(scene.chemistry), "status": "", "page": "1", "back": "1"}
    assert [b.text for b in form.buttons] == ["Save answers"]
    no_names_in_addresses(body)


def test_saving_three_answers(scene: Scene) -> None:
    """US1 story, US1-5: all three saved at once; the teacher stays on the sheet with the notice
    and the answers; the team answers page then reads "3 of 6"."""
    q1, q2, q3 = scene.copies[:3]
    response = post_answers(
        scene, scene.taras, {q1: "Sodium", q2: "Water", q3: "Salt", scene.copies[3]: ""}
    )
    path, query, _ = location(response)
    assert path == f"{TAB}/{scene.competition}/answers/{scene.comets}"
    assert query["subject"] == [str(scene.chemistry)] and "notice" in query
    body = follow(scene.taras, response)
    assert ("status", "Answers of “Comets” were saved") in html.notices(body)
    assert fields(body)[f"answer-{q1}"] == "Sodium"
    assert fields(body)[f"answer-{q3}"] == "Salt"
    assert stored(scene) == {q1: "Sodium", q2: "Water", q3: "Salt"}
    assert region_groups(get(scene.taras, answers_url(scene)))[0].rows[0]["Answered"] == "3 of 6"
    for value in ("Sodium", "Water", "Salt"):
        assert value not in response.headers["location"]


def test_changing_emptying_and_filling_at_once(scene: Scene) -> None:
    """US1-6: all three changes by one save; the emptied field shows its placeholder again."""
    q1, q2, q3, q4 = scene.copies[:4]
    post_answers(scene, scene.taras, {q1: "Sodium", q2: "Water", q3: "Salt"})
    body = follow(
        scene.taras, post_answers(scene, scene.taras, {q1: "NaCl", q2: "", q3: "Salt", q4: "Ice"})
    )
    assert stored(scene) == {q1: "NaCl", q3: "Salt", q4: "Ice"}
    assert fields(body)[f"answer-{q2}"] == ""
    assert html.control(body, f"answer-{q2}")["placeholder"] == "Not answered"


def test_answers_are_trimmed_with_inner_line_breaks_kept(scene: Scene) -> None:
    """US1-7, US1-8: stored and shown trimmed, the inner line break kept; spaces only are not
    answered."""
    q1, q2 = scene.copies[:2]
    body = follow(
        scene.taras,
        post_answers(scene, scene.taras, {q1: "\r\n  Sodium\r\nchloride  \r\n", q2: "  \r\n "}),
    )
    assert stored(scene) == {q1: "Sodium\nchloride"}
    assert ">Sodium\nchloride</textarea>" in body
    assert fields(body)[f"answer-{q2}"] == ""


def test_a_reload_repeats_nothing_and_a_foreign_notice_shows_nothing(scene: Scene) -> None:
    """US1-9, FR-030, SC-010: the redirect's target, loaded again, stores nothing; a tampered,
    expired or another team's notice shows no notice."""
    response = post_answers(scene, scene.taras, {scene.copies[0]: "Sodium"})
    target = response.headers["location"]
    for _ in range(2):
        assert "Answers of “Comets” were saved" in get(scene.taras, target)
    assert snapshot(scene.engine) == [(scene.competition, scene.comets, scene.copies[0], "Sodium")]
    token = parse_qs(urlsplit(target).query)["notice"][0]
    for notice in (token[:-2] + "xx", "abc"):
        assert "were saved" not in get(scene.taras, sheet_url(scene, query=f"&notice={notice}"))
    gymnasium_team = make_team(scene.engine, scene.gymnasium, "Stars")
    add_competition_team(scene.engine, scene.competition, gymnasium_team)
    other = get(scene.taras, sheet_url(scene, gymnasium_team, f"&notice={token}"))
    assert "were saved" not in other


def test_an_expired_notice_shows_nothing(scene: Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    response = post_answers(scene, scene.taras, {scene.copies[0]: "Sodium"})
    token = parse_qs(urlsplit(response.headers["location"]).query)["notice"][0]
    monkeypatch.setattr(
        "app.routers.teacher_team_answers.ANSWERS_NOTICE_TTL", timedelta(seconds=-1)
    )
    assert "were saved" not in get(scene.taras, sheet_url(scene, query=f"&notice={token}"))


def test_the_back_page_is_kept_and_falls_back_to_the_page_holding_the_team(scene: Scene) -> None:
    """Spec Assumptions: `back` is kept through the save; missing or invalid, the back link leads
    to the page holding the team."""
    for n in range(10):
        add_competition_team(
            scene.engine, scene.competition, make_team(scene.engine, scene.school, f"A team {n}")
        )
    page_two = f"{TAB}/{scene.competition}/answers?{scene.ctx}&p=2#team-{scene.comets}"
    for query in ("", "&back=x", "&back=0"):
        body = get(scene.taras, sheet_url(scene, query=query))
        assert (page_two, "Back to the answers") in html.link_pairs(body, "main")
    second = get(scene.taras, answers_url(scene, "&p=2"))
    (href,) = [link.href for link in html.links(second, "main") if link.text == "Enter answers"]
    assert href.endswith("&back=2")
    response = scene.taras.post(
        href.split("?")[0],
        data=answer_form(scene, {scene.copies[0]: "x"}, back="2"),
        follow_redirects=False,
    )
    _, query, _ = location(response)
    assert query["back"] == ["2"]


# ---------------------------------------------------------------------------------------------
# User story 3: Read access follows the progress only
# ---------------------------------------------------------------------------------------------

READ_NOTICE = "You have Read access to “Lyceum No. 2”, so you cannot change these answers."


def read_only_items(body: str) -> list[str]:
    """The text of each question card of the read-only sheet."""
    (sheet,) = [o for o in html.parse(body).find_all("ol") if "answer-sheet" in o.classes()]
    return [item.text() for item in sheet.find_all("li")]


def test_read_access_shows_the_progress_and_never_the_answers(scene: Scene) -> None:
    """US3 story, US3-3, US3-4, SC-004: Iryna sees Lions with its progress and no Enter answers; a
    crafted save is denied and nothing changes. Replaced by milestone 12.4 US7, FR-034–FR-036,
    research R7 (SC-011): the row has **View answers** instead of "Read access", and the sheet
    opens read-only, with the access notice, instead of "access denied"."""
    save_team_answer(
        scene.engine, scene.competition, scene.lions, scene.copies[0], "Secret lion\nline two"
    )
    body = get(scene.iryna, answers_url(scene))
    assert [(g.header, g.rows[0]["Answered"]) for g in region_groups(body)] == [
        ("Lviv · 1 team", "1 of 6")
    ]
    assert actions(body) == {"Lions": "View answers"}
    assert "Enter answers" not in body
    before = snapshot(scene.engine)
    for browser in (scene.iryna, scene.taras):
        sheet = get(browser, sheet_url(scene, scene.lions))
        assert html.h1(sheet) == "Answers of “Lions” in “Spring round”"
        assert ("Educational institution", "Lyceum No. 2") in html.details(sheet)
        assert ("status", READ_NOTICE) in html.notices(sheet)
        items = read_only_items(sheet)
        assert (
            items[0]
            == "Question 1 Question Question text 1? Answer to question 1 Secret lion line two"
        )
        assert all(item.endswith("Not answered") for item in items[1:])
        assert '<p class="keep-lines">Secret lion\nline two</p>' in sheet
        main = html.region(sheet, "main")
        for absent in ("<form", "<textarea", "<button", "Reference answer", "Grade", "Score"):
            assert absent not in main, absent
        back = f"{TAB}/{scene.competition}/answers?{scene.ctx}#team-{scene.lions}"
        assert (back, "Back to the answers") in html.link_pairs(sheet, "main")
        denied(post_answers(scene, browser, {scene.copies[0]: "Changed"}, team=scene.lions))
    assert snapshot(scene.engine) == before


def test_the_read_only_sheet_shows_answers_saved_since(scene: Scene) -> None:
    """US7-3: opened again, it shows what a Write teacher saved meanwhile."""
    get(scene.iryna, sheet_url(scene, scene.lions))
    save_team_answer(scene.engine, scene.competition, scene.lions, scene.copies[1], "Later one")
    items = read_only_items(get(scene.iryna, sheet_url(scene, scene.lions)))
    assert items[1].endswith("Answer to question 2 Later one")


def test_raising_the_access_to_write_offers_enter_answers(scene: Scene) -> None:
    """US7-5."""
    set_links(scene, lyceum=AccessLevel.WRITE)
    assert actions(get(scene.taras, answers_url(scene)))["Lions"] == "Enter answers"
    assert sheet_forms(get(scene.taras, sheet_url(scene, scene.lions)))


# ---------------------------------------------------------------------------------------------
# User story 6: answers that are too long
# ---------------------------------------------------------------------------------------------


def test_a_too_long_answer_saves_nothing_and_keeps_every_text(scene: Scene) -> None:
    """US6 story, US6-1, US6-2, US6-5, FR-019: 400, every field as sent, the error at question 4,
    the summary linking to it, the context kept and the browser limit still on every field."""
    q1, _, _, q4, q5, _ = scene.copies
    save_team_answer(scene.engine, scene.competition, scene.comets, q1, "Old")
    before = snapshot(scene.engine)
    long = "  " + "x" * 2001 + "  "
    response = post_answers(scene, scene.taras, {q1: " New one ", q4: long, q5: "Five"})
    assert response.status_code == 400
    body = response.text
    assert fields(body)[f"answer-{q1}"] == " New one "
    assert fields(body)[f"answer-{q4}"] == long
    assert fields(body)[f"answer-{q5}"] == "Five"
    assert fields(body)[f"answer-{scene.copies[1]}"] == ""
    assert html.control(body, f"answer-{q4}")["aria-invalid"] == "true"
    assert html.field_error(body, f"answer-{q4}") == TOO_LONG.format(n=4)
    summary = html.error_summary(body)
    assert summary is not None
    assert summary == ("There is a problem", [(f"#answer-{q4}", TOO_LONG.format(n=4))])
    assert body.index("error-summary") < body.index("answer-sheet")
    assert snapshot(scene.engine) == before
    assert all(html.control(body, f"answer-{copy}")["maxlength"] == "2000" for copy in scene.copies)
    (form,) = sheet_forms(body)
    hidden = {i.name: i.value for i in form.inputs if i.type == "hidden"}
    assert hidden == {"subject": str(scene.chemistry), "status": "", "page": "1", "back": "1"}
    assert "were saved" not in body
    resubmitted = {
        int(name.removeprefix("answer-")): value for name, value in fields(body).items()
    } | {q4: "x" * 2000}
    assert post_answers(scene, scene.taras, resubmitted).status_code == 303
    assert stored(scene) == {q1: "New one", q4: "x" * 2000, q5: "Five"}


def test_several_too_long_answers_are_summarised_in_question_order(scene: Scene) -> None:
    """US6-3."""
    q1, q2, q3 = scene.copies[:3]
    response = post_answers(scene, scene.taras, {q3: "y" * 2001, q1: "x" * 2001, q2: "fine"})
    assert response.status_code == 400
    summary = html.error_summary(response.text)
    assert summary is not None
    assert summary.items == [
        (f"#answer-{q1}", TOO_LONG.format(n=1)),
        (f"#answer-{q3}", TOO_LONG.format(n=3)),
    ]
    assert stored(scene) == {}


def test_exactly_2000_characters_are_saved(scene: Scene) -> None:
    """US6-4."""
    assert post_answers(scene, scene.taras, {scene.copies[0]: "x" * 2000}).status_code == 303
    assert stored(scene) == {scene.copies[0]: "x" * 2000}


# ---------------------------------------------------------------------------------------------
# User story 7: only while In progress
# ---------------------------------------------------------------------------------------------


def closed_round(s: Scene, name: str, **seed: Any) -> tuple[int, int]:
    competition = make_competition(s.engine, s.chemistry, name, **seed)
    copy = add_competition_question(s.engine, competition, make_question(s.engine, s.chemistry))
    add_competition_team(s.engine, competition, s.comets)
    save_team_answer(s.engine, competition, s.comets, copy, "Kept")
    return competition, copy


@pytest.mark.parametrize(
    ("seed", "reason"),
    [
        (
            {"starts_at": LATER},
            "“{name}” has not started yet, so its answers cannot be entered yet.",
        ),
        (
            {"starts_at": STARTED, "cancelled": True},
            "“{name}” has been cancelled, so its answers can no longer be entered.",
        ),
    ],
)
def test_both_pages_and_the_save_refuse_a_competition_not_in_progress(
    scene: Scene, seed: dict[str, Any], reason: str
) -> None:
    """US7-1–US7-3, FR-026, SC-003: typed addresses and a save; nothing is saved. Replaced by
    milestone 12.4 FR-041 (SC-011): a Finished competition is no longer refused on the pages,
    only on the save (`test_a_save_after_the_finish_is_refused`)."""
    competition, copy = closed_round(scene, "Autumn round", **seed)
    before = snapshot(scene.engine)
    expected = reason.format(name="Autumn round")
    for response in (
        scene.taras.get(answers_url(scene, competition=competition)),
        scene.taras.get(sheet_url(scene, competition=competition)),
        post_answers(scene, scene.taras, {copy: "Changed"}, competition=competition),
    ):
        refused(response, "Autumn round", expected, scene, competition)
    assert snapshot(scene.engine) == before


def test_cancelled_while_the_sheet_is_open(scene: Scene) -> None:
    """US7 story, US7-4: the save is refused and the answers saved before stay."""
    post_answers(scene, scene.taras, {scene.copies[0]: "Before"})
    get(scene.taras, sheet_url(scene))
    with Session(scene.engine) as session:
        manager = get_user_by_email(session, OLENA)
        assert manager is not None and manager.id is not None
        cancel_competition(session, manager.id, scene.competition, scene.chemistry, None)
    response = post_answers(scene, scene.taras, {scene.copies[0]: "After"})
    refused(
        response,
        "Spring round",
        "“Spring round” has been cancelled, so its answers can no longer be entered.",
        scene,
        scene.competition,
    )
    assert stored(scene) == {scene.copies[0]: "Before"}


def test_an_upcoming_competition_opens_once_its_start_passes(scene: Scene) -> None:
    """US7-5."""
    autumn = make_competition(
        scene.engine, scene.chemistry, "Autumn round", starts_at=NOW + timedelta(hours=2)
    )
    add_competition_team(scene.engine, autumn, scene.comets)
    assert scene.taras.get(answers_url(scene, competition=autumn)).status_code == 409
    scene.clock(timedelta(hours=2))
    assert html.h1(get(scene.taras, answers_url(scene, competition=autumn))) == (
        "Answers of “Autumn round”"
    )


# ---------------------------------------------------------------------------------------------
# User story 8: only the right teacher reaches the right team
# ---------------------------------------------------------------------------------------------

PREFIX = f"{TAB}/{{competition_id:int}}/answers"
ANSWER_ROUTES = sorted(
    (method, path)
    for path, methods, _ in ALL_ROUTES
    if path.startswith(PREFIX)
    for method in methods
    if method in ("GET", "POST")
)


def concrete(path: str, competition: int | str, team: int | str, query: str) -> str:
    path = path.replace("{competition_id:int}", str(competition))
    return f"{path.replace('{team_id:int}', str(team))}?{query}"


def send(browser: TestClient, method: str, url: str, data: dict[str, str], **kw: Any) -> Any:
    if method == "POST":
        return browser.post(url.split("?")[0], data=data, follow_redirects=False, **kw)
    return browser.get(url, follow_redirects=False, **kw)


def test_the_sweep_has_every_route() -> None:
    assert ANSWER_ROUTES == [
        ("GET", PREFIX),
        ("GET", f"{PREFIX}/{{team_id:int}}"),
        ("POST", f"{PREFIX}/{{team_id:int}}"),
    ]


@pytest.mark.parametrize(("method", "path"), ANSWER_ROUTES)
@pytest.mark.parametrize("ids", ["real", "unknown"])
def test_other_roles_are_refused_before_any_id_is_read(
    scene: Scene, client: TestClient, client_as: ClientAs, method: str, path: str, ids: str
) -> None:
    """US8-1, SC-002: administrators and students, through addresses and forms, also with unknown
    ids; nothing changes; anonymous visitors are sent to sign in."""
    competition, team = (scene.competition, scene.comets) if ids == "real" else (MISSING, MISSING)
    url = concrete(path, competition, team, scene.ctx)
    data = answer_form(scene, {scene.copies[0]: "Forged"})
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


@pytest.mark.parametrize(("method", "path"), ANSWER_ROUTES)
def test_unknown_mismatched_and_hidden_subjects_and_competitions(
    scene: Scene, method: str, path: str
) -> None:
    """US8-2, FR-025 step 2: each before the status, for a teacher with Write access."""
    biology = make_subject(scene.engine, "Biology")
    hidden = make_competition(scene.engine, biology, "Hidden round", starts_at=LATER)
    make_competition(scene.engine, biology, "Finished round", starts_at=STARTED, stopped=True)
    with Session(scene.engine) as session:
        set_subject_active(session, biology, False)
    data = answer_form(scene, {scene.copies[0]: "x"})
    cases = [
        (concrete(path, scene.competition, scene.comets, "subject=abc"), SUBJECT_NOT_FOUND),
        (concrete(path, scene.competition, scene.comets, f"subject={MISSING}"), SUBJECT_NOT_FOUND),
        (concrete(path, MISSING, scene.comets, scene.ctx), COMPETITION_NOT_FOUND),
        (
            concrete(path, scene.competition, scene.comets, f"subject={scene.physics}"),
            COMPETITION_NOT_FOUND,
        ),
        (concrete(path, hidden, scene.comets, f"subject={biology}"), COMPETITION_NOT_FOUND),
        (concrete(path, hidden, scene.comets, ""), COMPETITION_NOT_FOUND),
    ]
    for url, page in cases:
        form = data | {"subject": parse_qs(urlsplit(url).query).get("subject", [""])[0]}
        not_found(send(scene.taras, method, url, form), page)
    assert snapshot(scene.engine) == []


@pytest.mark.parametrize(("method", "path"), [r for r in ANSWER_ROUTES if "team_id" in r[1]])
def test_the_status_comes_before_the_team(scene: Scene, method: str, path: str) -> None:
    """US8-8: a cancelled competition with an unknown team, or a team of an unlinked
    institution, shows the refusal."""
    competition, copy = closed_round(scene, "Autumn round", starts_at=STARTED, cancelled=True)
    for team in (MISSING, scene.novas):
        url = concrete(path, competition, team, scene.ctx)
        assert send(scene.taras, method, url, answer_form(scene, {copy: "x"})).status_code == 409


@pytest.mark.parametrize(("method", "path"), [r for r in ANSWER_ROUTES if "team_id" in r[1]])
def test_unknown_deleted_foreign_and_deactivated_teams_are_not_found(
    scene: Scene, method: str, path: str
) -> None:
    """US8-3, FR-025 step 4, before the access: a deleted team of a Read institution is not
    found; ids above `MAX_ID` too, on both routes and engines."""
    deleted = make_team(scene.engine, scene.lyceum, "Gone", deleted=True)
    add_competition_team(scene.engine, scene.competition, deleted)
    outside = make_team(scene.engine, scene.school, "Outside")
    closed = make_institution(scene.engine, "Closed School", "Kyiv")
    closed_team = make_team(scene.engine, closed, "Closed")
    add_competition_team(scene.engine, scene.competition, closed_team)
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, closed), closed, False)
    data = answer_form(scene, {scene.copies[0]: "x"})
    for team in (MISSING, deleted, outside, closed_team, MAX_ID + 1, "9" * 30):
        url = concrete(path, scene.competition, team, scene.ctx)
        not_found(send(scene.taras, method, url, data), TEAM_NOT_FOUND)
    assert snapshot(scene.engine) == []


def test_a_team_of_a_deactivated_region_is_not_found(scene: Scene) -> None:
    with Session(scene.engine) as session:
        set_region_active(session, region_of(scene.engine, scene.lyceum), False)
    not_found(scene.taras.get(sheet_url(scene, scene.lions)), TEAM_NOT_FOUND)


def test_questions_that_are_not_the_competitions_are_not_found(scene: Scene) -> None:
    """US8-4, FR-025 step 4, research R9 (I1): another competition's copy, an unknown id, a name
    that is no id, the same name twice (equal or different values) and two spellings of one id;
    nothing is stored."""
    other = make_competition(scene.engine, scene.chemistry, "Other round", starts_at=STARTED)
    foreign = add_competition_question(
        scene.engine, other, make_question(scene.engine, scene.chemistry)
    )
    q1 = scene.copies[0]
    for answers in ({q1: "ok", foreign: "x"}, {q1: "ok", MISSING: "x"}):
        not_found(post_answers(scene, scene.taras, answers), QUESTION_NOT_FOUND)
    for pairs in (
        [(f"answer-{q1}", "ok"), ("answer-abc", "x")],
        [(f"answer-{q1}", "A"), (f"answer-{q1}", "B")],
        [(f"answer-{q1}", "Same"), (f"answer-{q1}", "Same")],
        [(f"answer-{q1}", "A"), (f"answer-0{q1}", "B")],
        [("answer-", "x")],
    ):
        not_found(post_raw(scene, scene.taras, pairs), QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == []
    assert post_raw(scene, scene.taras, [(f"answer-{q1}", "Once")]).status_code == 303
    assert stored(scene) == {q1: "Once"}


def test_a_team_of_an_unlinked_institution_is_denied(scene: Scene) -> None:
    """US8-5: the sheet and the save of Novas."""
    denied(scene.taras.get(sheet_url(scene, scene.novas)))
    denied(post_answers(scene, scene.taras, {scene.copies[0]: "x"}, team=scene.novas))
    assert snapshot(scene.engine) == []


@pytest.mark.parametrize("change", [AccessLevel.READ, None])
def test_a_link_lowered_or_removed_while_the_sheet_is_open(
    scene: Scene, change: AccessLevel | None
) -> None:
    """US8-6, US8-7, FR-013, FR-027: the save is denied and the answers saved before stay; the
    team answers page then shows **View answers** (milestone 12.4), or no longer lists the
    team."""
    post_answers(scene, scene.taras, {scene.copies[0]: "Before"})
    get(scene.taras, sheet_url(scene))
    set_links(scene, school=change)
    denied(post_answers(scene, scene.taras, {scene.copies[0]: "After"}))
    assert stored(scene) == {scene.copies[0]: "Before"}
    rows = actions(get(scene.taras, answers_url(scene)))
    # Replaced by milestone 12.4 FR-036 (SC-011): **View answers**, not "Read access".
    assert rows.get("Comets") == ("View answers" if change else None)


def test_the_subject_deactivated_while_the_sheet_is_open(scene: Scene) -> None:
    """Spec Edge Cases: the next save is not found; the answers stay."""
    post_answers(scene, scene.taras, {scene.copies[0]: "Before"})
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    response = post_answers(scene, scene.taras, {scene.copies[0]: "After"})
    assert response.status_code == 404
    assert stored(scene) == {scene.copies[0]: "Before"}


@pytest.mark.parametrize("level", ["institution", "region"])
def test_deactivation_hides_the_team_and_reactivation_shows_the_same_answers(
    scene: Scene, level: str
) -> None:
    """FR-029, spec Edge Cases (G1): while deactivated, the team is not listed, its sheet is not
    found with nothing about it shown, and a crafted save with changed, emptied and new answers
    is not found; reactivated, the team reads "3 of 6" and the sheet shows the same answers."""
    q1, q2, q3, q4 = scene.copies[:4]
    post_answers(scene, scene.taras, {q1: "One", q2: "Two", q3: "Three"})
    before = snapshot(scene.engine)
    region = region_of(scene.engine, scene.school)

    def set_active(active: bool) -> None:
        with Session(scene.engine) as session:
            if level == "institution":
                set_institution_active(session, region, scene.school, active)
            else:
                set_region_active(session, region, active)

    set_active(False)
    assert "Comets" not in actions(get(scene.taras, answers_url(scene)))
    response = scene.taras.get(sheet_url(scene))
    not_found(response, TEAM_NOT_FOUND)
    for text in ("Comets", "Question text", "One", "Two"):
        assert text not in html.text(response.text, "main")
    not_found(post_answers(scene, scene.taras, {q1: "Changed", q2: "", q4: "New"}), TEAM_NOT_FOUND)
    assert snapshot(scene.engine) == before
    set_active(True)
    assert actions(get(scene.taras, answers_url(scene)))["Comets"] == "Enter answers"
    rows = [r for g in region_groups(get(scene.taras, answers_url(scene))) for r in g.rows]
    assert [r["Answered"] for r in rows if r["Team"] == "Comets"] == ["3 of 6"]
    shown = fields(get(scene.taras, sheet_url(scene)))
    assert [shown[f"answer-{copy}"] for copy in scene.copies] == ["One", "Two", "Three", "", "", ""]
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    "forged", [{"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://evil.example"}]
)
def test_a_cross_site_save_changes_nothing(scene: Scene, forged: dict[str, str]) -> None:
    """US8-9, FR-030."""
    response = post_answers(scene, scene.taras, {scene.copies[0]: "Forged"}, headers=forged)
    assert response.status_code == 403
    assert snapshot(scene.engine) == []


@pytest.mark.parametrize(
    "query", ["subject=1e9999", "subject=%00", "p=-1", "p=1e9", "back=%00", "status=nope"]
)
def test_odd_values_never_get_a_json_error(scene: Scene, query: str) -> None:
    for url in (
        f"{TAB}/{scene.competition}/answers?{query}",
        f"{TAB}/{scene.competition}/answers/{scene.comets}?{query}",
    ):
        response = scene.taras.get(url)
        assert response.status_code in (200, 404), (url, response.status_code)
        assert response.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("email", [TEACHER_EMAIL, ADMIN_EMAIL, STUDENT_EMAIL])
def test_a_path_id_that_is_no_number_matches_no_route(client_as: ClientAs, email: str) -> None:
    for url in (f"{TAB}/abc/answers", f"{TAB}/1/answers/abc"):
        response = client_as(email).get(url, follow_redirects=False)
        assert response.status_code == 404
        assert "Competition not found" not in response.text


# ---------------------------------------------------------------------------------------------
# User story 9: the empty states
# ---------------------------------------------------------------------------------------------


def test_the_empty_states(scene: Scene, client_as: ClientAs) -> None:
    """US9-1–US9-3, FR-012, FR-021."""
    engine, settings = scene.engine, app.state.settings
    closed = make_institution(engine, "Closed School", "Kyiv")
    make_teacher(
        engine, settings, email="nadiia@example.org", institutions={closed: AccessLevel.WRITE}
    )
    with Session(engine) as session:
        set_institution_active(session, region_of(engine, closed), closed, False)
    other = make_institution(engine, "School No. 9", "Odesa")
    make_team(engine, other, "Outsiders")
    make_team(engine, other, "Deleted ones", deleted=True)
    make_teacher(
        engine, settings, email="bohdan@example.org", institutions={other: AccessLevel.WRITE}
    )
    for email, message in (
        ("nadiia@example.org", "You are not linked to any educational institution"),
        ("bohdan@example.org", "No teams from your educational institutions"),
    ):
        browser = client_as(email)
        body = get(browser, answers_url(scene))
        assert message in html.text(body, "main")
        assert "<table" not in body and "empty-state-hint" not in body
    winter = make_competition(engine, scene.chemistry, "Winter round", starts_at=STARTED)
    add_competition_team(engine, winter, scene.comets)
    rows = region_groups(get(scene.taras, answers_url(scene, competition=winter)))[0].rows
    assert rows[0]["Answered"] == "0 of 0"
    body = get(scene.taras, sheet_url(scene, competition=winter))
    assert "No questions in this competition" in html.text(body, "main")
    assert sheet_forms(body) == []
    assert "Save answers" not in body
    response = post_answers(scene, scene.taras, {}, competition=winter)
    assert "Answers of “Comets” were saved" in follow(scene.taras, response)


# ---------------------------------------------------------------------------------------------
# User story 10: two teachers save the same team
# ---------------------------------------------------------------------------------------------


def test_the_later_save_wins(scene: Scene) -> None:
    """US10 story, US10-1, SC-006: both saves accepted with the notice; the sheet then shows
    exactly the second save's answers."""
    q1, q2, q3 = scene.copies[:3]
    save_team_answer(scene.engine, scene.competition, scene.comets, q1, "Old")
    get(scene.taras, sheet_url(scene))
    get(scene.oksana, sheet_url(scene))
    first = post_answers(scene, scene.oksana, {q1: "Old", q2: "Oksana's", q3: ""})
    second = post_answers(scene, scene.taras, {q1: "", q2: "", q3: "Taras's"})
    for browser, response in ((scene.oksana, first), (scene.taras, second)):
        assert "Answers of “Comets” were saved" in follow(browser, response)
    assert stored(scene) == {q3: "Taras's"}


# ---------------------------------------------------------------------------------------------
# User story 11: deleting a team
# ---------------------------------------------------------------------------------------------


def test_deleting_a_team_deletes_its_answers_where_it_has_not_finished(scene: Scene) -> None:
    """US11 story, US11-1–US11-3, FR-028: deleted on the Teams tab, Comets loses its answers in
    the In progress and the Cancelled competition; the Finished one keeps it, marked, with its
    answers; a sheet opened before is not found on save."""
    post_answers(scene, scene.taras, {scene.copies[0]: "Spring"})
    autumn, autumn_copy = closed_round(scene, "Autumn round", starts_at=STARTED, cancelled=True)
    summer, summer_copy = closed_round(scene, "Summer round", starts_at=STARTED, stopped=True)
    get(scene.taras, sheet_url(scene))
    deleted = scene.taras.post(f"/teacher/teams/{scene.comets}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert stored(scene) == {}
    assert stored(scene, competition=autumn) == {}
    assert stored(scene, competition=summer) == {summer_copy: "Kept"}
    assert autumn_copy != summer_copy
    teams = get(scene.taras, f"{TAB}/{summer}/teams?{scene.ctx}")
    assert actions(teams) == {"Comets": "(deleted)"}
    not_found(post_answers(scene, scene.taras, {scene.copies[0]: "Late"}), TEAM_NOT_FOUND)
    assert stored(scene) == {}
    assert "Comets" not in actions(get(scene.taras, answers_url(scene)))


# ---------------------------------------------------------------------------------------------
# Re-used by the page-pattern and form-contract tests
# ---------------------------------------------------------------------------------------------


def students(scene: Scene) -> None:
    """Two active members of Comets, for a row that reads "2"."""
    school_class = make_class(scene.engine, scene.school)
    for n in range(2):
        make_member(
            scene.engine,
            scene.comets,
            enrolled(scene.engine, f"s{n}@example.org", school_class, "Student", f"No{n}"),
        )


def test_a_rows_active_members(scene: Scene) -> None:
    students(scene)
    body = get(scene.taras, answers_url(scene))
    assert region_groups(body)[0].rows[0]["Active members"] == "2"
    assert "No0" not in body


# ---------------------------------------------------------------------------------------------
# Milestone 12.4: the Answers pages of a finished competition (specs/012.4-finish-and-grade US8)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Finished:
    competition: int
    copies: list[int]


@pytest.fixture
def finished(scene: Scene) -> Finished:
    """ "Autumn round", Finished, 4 questions; Comets answered all 4 (graded 5, 7, 5 and not
    graded), Lions answered nothing; Novas (unlinked) and a deleted team of School No. 5 are in
    it too."""
    competition = make_competition(
        scene.engine, scene.chemistry, "Autumn round", starts_at=STARTED, stopped=True
    )
    copies = [
        add_competition_question(
            scene.engine,
            competition,
            make_question(scene.engine, scene.chemistry, f"Autumn {n}?", f"Hidden reference {n}"),
        )
        for n in range(1, 5)
    ]
    gone = make_team(scene.engine, scene.school, "Gone", deleted=True)
    for team in (scene.comets, scene.lions, scene.novas, gone):
        add_competition_team(scene.engine, competition, team)
    for copy, grade in zip(copies, (5, 7, 5, None), strict=True):
        save_team_answer(scene.engine, competition, scene.comets, copy, f"Comets {copy}")
        if grade is not None:
            grade_answer(scene.engine, competition, scene.comets, copy, grade)
    return Finished(competition, copies)


def test_the_answers_page_of_a_finished_competition(
    scene: Scene, finished: Finished, client_as: ClientAs
) -> None:
    """US8-1, US8-2, FR-037: Write and Read, with or without the setting, see only their
    institutions' teams with **Answered**, **Graded**, **Score** and **View answers**."""
    body = get(scene.taras, answers_url(scene, competition=finished.competition))
    assert ("Status", "Finished") in html.details(body)
    (table,) = html.parse(body).find_all("table")[:1]
    assert [th.text() for th in table.find_all("th")] == [
        "Team",
        "Educational institution",
        "Active members",
        "Answered",
        "Graded",
        "Score",
        "Actions",
    ]
    listed = {r["Team"]: r for g in region_groups(body) for r in g.rows}
    assert listed == {
        "Comets": {
            "Team": "Comets",
            "Educational institution": "School No. 5",
            "Active members": "0",
            "Answered": "4 of 4",
            "Graded": "3 of 4",
            "Score": "17",
            "": "View answers",
        },
        "Lions": {
            "Team": "Lions",
            "Educational institution": "Lyceum No. 2",
            "Active members": "0",
            "Answered": "0 of 4",
            "Graded": "0 of 0",
            "Score": "0",
            "": "View answers",
        },
    }
    assert "Enter answers" not in body
    assert list(
        actions(get(scene.iryna, answers_url(scene, competition=finished.competition)))
    ) == ["Lions"]
    olena = get(scene.olena, answers_url(scene, competition=finished.competition))
    assert "No teams from your educational institutions" in html.text(olena, "main")


def test_the_read_only_sheet_of_a_finished_competition(scene: Scene, finished: Finished) -> None:
    """US8-3, US8-4, FR-038: the score, the graded count, each grade, "Not answered"; no reference
    answer, no form, no access notice; a grade saved by grading shows on the next opening."""
    for browser, team in ((scene.taras, scene.comets), (scene.oksana, scene.comets)):
        body = get(browser, sheet_url(scene, team, competition=finished.competition))
        text = html.text(body, "main")
        assert "Score: 17" in text
        assert "Graded 3 of 4 answers" in text
        items = read_only_items(body)
        assert [item.rsplit(" ", 4)[-4:] for item in items[:3]] == [
            ["Grade:", "5", "of", "10"],
            ["Grade:", "7", "of", "10"],
            ["Grade:", "5", "of", "10"],
        ]
        assert items[3].endswith("Not graded yet")
        main = html.region(body, "main")
        for absent in ("<form", "<textarea", "<button", "Hidden reference", "Read access to"):
            assert absent not in main, absent
    lions = get(scene.taras, sheet_url(scene, scene.lions, competition=finished.competition))
    text = html.text(lions, "main")
    assert "Score: 0" in text and "Graded 0 of 0 answers" in text
    assert "Read access to" not in text
    assert text.count("Not answered") == 4
    grade_answer(scene.engine, finished.competition, scene.comets, finished.copies[3], 9)
    again = get(scene.taras, sheet_url(scene, competition=finished.competition))
    assert "Score: 26" in html.text(again, "main")
    assert read_only_items(again)[3].endswith("Grade: 9 of 10")


def test_the_finished_pages_follow_the_links_only(
    scene: Scene, finished: Finished, client_as: ClientAs
) -> None:
    """US8-5, US8-6, FR-041: deleted, unlinked and deactivated teams; the setting gives
    nothing."""
    with Session(scene.engine) as session:
        deleted = session.exec(select(Team.id).where(Team.name == "Gone")).one()
    not_found(
        scene.taras.get(sheet_url(scene, deleted, competition=finished.competition)),
        TEAM_NOT_FOUND,
    )
    for browser in (scene.taras, scene.olena):
        denied(browser.get(sheet_url(scene, scene.novas, competition=finished.competition)))
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, scene.school), scene.school, False)
    not_found(scene.taras.get(sheet_url(scene, competition=finished.competition)), TEAM_NOT_FOUND)
    body = get(scene.taras, answers_url(scene, competition=finished.competition))
    assert "Comets" not in actions(body)


def test_a_save_after_the_finish_is_refused(scene: Scene, finished: Finished) -> None:
    """US8-7, FR-040: a typed save, and one from a sheet opened before the finish; the answers
    saved before are kept."""
    post_answers(scene, scene.taras, {scene.copies[0]: "Before"})
    get(scene.taras, sheet_url(scene))
    with Session(scene.engine) as session:
        manager = get_user_by_email(session, OLENA)
        assert manager is not None and manager.id is not None
        finish_competition(session, manager.id, scene.competition, scene.chemistry, None)
    before = snapshot(scene.engine)
    for competition, copy in (
        (scene.competition, scene.copies[0]),
        (finished.competition, finished.copies[0]),
    ):
        refused(
            post_answers(scene, scene.taras, {copy: "After"}, competition=competition),
            "Spring round" if competition == scene.competition else "Autumn round",
            "has finished, so its answers can no longer be entered.",
            scene,
            competition,
        )
    assert snapshot(scene.engine) == before
    assert stored(scene) == {scene.copies[0]: "Before"}


def test_a_finished_competition_of_a_deactivated_subject_stays_readable(
    scene: Scene, finished: Finished
) -> None:
    """US13-1, FR-042: its Answers page and read-only sheets open; an In progress competition of
    the subject is not found on both pages."""
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    body = get(scene.taras, answers_url(scene, competition=finished.competition))
    assert actions(body) == {"Comets": "View answers", "Lions": "View answers"}
    sheet = get(scene.taras, sheet_url(scene, competition=finished.competition))
    assert "Score: 17" in html.text(sheet, "main")
    for url in (answers_url(scene), sheet_url(scene)):
        not_found(scene.taras.get(url), COMPETITION_NOT_FOUND)
