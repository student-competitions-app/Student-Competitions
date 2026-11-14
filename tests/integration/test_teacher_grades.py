"""A finished competition's grades, end to end through the test client: the Grades page, its
filter, the grading sheet and its save, invalid grades, the refusals, the access rules, two
graders at once and a deactivated subject.

See specs/012.4-finish-and-grade/spec.md US3–US6, US10–US13, contracts/http-routes.md §1–§3 and
research R15. Every case runs on both engines. The clock is fixed at 1 March 2027 09:00 UTC by
patching `app.services.competitions.utc_now`; no test waits. The browser's zone is the
`sc_time_zone` cookie, set as `time-zone.js` would.

- Olena: a real teacher with **Can manage competitions**, linked only to "District Office"
  (Kyiv), which has no team;
- Taras: a real teacher without it, with **Write** access to School No. 5;
- "Spring round": a Finished competition of Chemistry, started 1 March 2027, 09:00 in Kyiv, with
  4 questions, and 25 teams in three regions (sorted as the Teams page sorts them):
  - Kyiv (12): "Comets" and "Kyiv 01"–"Kyiv 09" (School No. 5), "Novas" (Closed School, a
    deactivated institution) and "Rockets" (School No. 5, deleted);
  - Lviv (8): "Lions" and "Lviv 01"–"Lviv 07" (Lyceum No. 2);
  - Odesa (5): "Odesa 01"–"Odesa 04" and "Stars" (Odesa College, in the deactivated region);
- the answers and grades: Comets answered all 4, graded 5, 7, 5 and not graded (score 17); Lions
  2, both graded 0; Kyiv 01 nothing; Kyiv 02–09, Novas, Odesa 01–03 and Stars one answer each,
  not graded; Lviv 01–07 one each graded 10; Rockets one graded 3; Odesa 04 one graded 4. So 11
  of 25 teams are fully graded, and **Ungraded only** lists 14: 10 in Kyiv, 4 in Odesa.

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
from app.models import AccessLevel, Role, TeamAnswer
from app.schemas.teachers import MAX_ID
from app.services.subjects import set_subject_active
from app.services.teachers import get_teacher, update_teacher
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
    make_competition,
    make_institution,
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
)

OLENA = "olena@example.org"
TARAS = "taras@example.org"
TAB = "/teacher/competitions"
KYIV = "Europe/Kyiv"
NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 7, 0, tzinfo=UTC)
"""1 March 2027, 09:00 in Kyiv."""
LATER = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
MISSING = 999_999
GRADE_ERROR = "Enter a whole number from 0 to 10."

SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist")
COMPETITION_NOT_FOUND = ("Competition not found", "This competition does not exist")
TEAM_NOT_FOUND = ("Team not found", "This team does not exist, or it is not in this competition.")
QUESTION_NOT_FOUND = ("Question not found", "This question is not in this competition.")


@dataclass(frozen=True)
class Scene:
    engine: Engine
    olena: TestClient
    taras: TestClient
    chemistry: int
    physics: int
    competition: int
    copies: list[int]
    question_ids: list[int]
    school: int
    teams: dict[str, int]
    """Every team of the competition, by name."""
    clock: Callable[[timedelta], datetime]

    @property
    def ctx(self) -> str:
        """The competitions-list context of the competition's subject, status All, page 1."""
        return f"subject={self.chemistry}"

    @property
    def comets(self) -> int:
        return self.teams["Comets"]


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
    closed = make_institution(engine, "Closed School", "Kyiv", active=False)
    lyceum = make_institution(engine, "Lyceum No. 2", "Lviv")
    odesa = make_institution(engine, "Odesa College", "Odesa", region_active=False)
    office = make_institution(engine, "District Office", "Kyiv")
    make_teacher(
        engine, settings, email=OLENA, institutions={office: AccessLevel.READ}, can_manage=True
    )
    make_teacher(
        engine,
        settings,
        email=TARAS,
        institutions={school: AccessLevel.WRITE},
        first="Taras",
        last="Shevchenko",
    )
    browsers = [client_as(email) for email in (OLENA, TARAS)]
    for browser in browsers:
        browser.cookies.set("sc_time_zone", KYIV)
    chemistry = make_subject(engine, "Chemistry")
    competition = make_competition(engine, chemistry, starts_at=STARTED, stopped=True)
    question_ids = [
        make_question(engine, chemistry, f"Question text {n}?", f"Reference answer {n}.")
        for n in range(1, 5)
    ]
    copies = [add_competition_question(engine, competition, q) for q in question_ids]
    plan: list[tuple[str, int, bool]] = [
        ("Comets", school, False),
        *((f"Kyiv {n:02}", school, False) for n in range(1, 10)),
        ("Novas", closed, False),
        ("Rockets", school, True),
        ("Lions", lyceum, False),
        *((f"Lviv {n:02}", lyceum, False) for n in range(1, 8)),
        *((f"Odesa {n:02}", odesa, False) for n in range(1, 5)),
        ("Stars", odesa, False),
    ]
    teams = {}
    for name, institution, deleted in plan:
        teams[name] = make_team(engine, institution, name, deleted=deleted)
        add_competition_team(engine, competition, teams[name])

    def answer(name: str, copy: int, grade: int | None = None) -> None:
        save_team_answer(engine, competition, teams[name], copy, f"Answer of {name}")
        if grade is not None:
            grade_answer(engine, competition, teams[name], copy, grade)

    for copy, grade in zip(copies, (5, 7, 5, None), strict=True):
        answer("Comets", copy, grade)
    answer("Lions", copies[0], 0)
    answer("Lions", copies[1], 0)
    for name in (*(f"Kyiv {n:02}" for n in range(2, 10)), "Novas", "Stars"):
        answer(name, copies[0])
    for name in (f"Odesa {n:02}" for n in range(1, 4)):
        answer(name, copies[0])
    for name in (f"Lviv {n:02}" for n in range(1, 8)):
        answer(name, copies[0], 10)
    answer("Rockets", copies[0], 3)
    answer("Odesa 04", copies[0], 4)
    return Scene(
        engine,
        *browsers,
        chemistry=chemistry,
        physics=make_subject(engine, "Physics"),
        competition=competition,
        copies=copies,
        question_ids=question_ids,
        school=school,
        teams=teams,
        clock=clock,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def grades_url(s: Scene, query: str = "", competition: int | None = None) -> str:
    return f"{TAB}/{competition or s.competition}/grades?{s.ctx}{query}"


def sheet_url(
    s: Scene, team: int | str | None = None, query: str = "", competition: int | None = None
) -> str:
    return f"{TAB}/{competition or s.competition}/grades/{team or s.comets}?{s.ctx}{query}"


def grade_form(s: Scene, grades: dict[int, str], back: str = "1", show: str = "") -> dict[str, str]:
    """The sheet's form: the context, `show`, `back` and one `grade-<id>` per question given."""
    form = {"subject": str(s.chemistry), "status": "", "page": "1", "show": show, "back": back}
    return form | {f"grade-{copy}": value for copy, value in grades.items()}


def post_grades(
    s: Scene,
    browser: TestClient,
    grades: dict[int, str],
    team: int | str | None = None,
    competition: int | None = None,
    back: str = "1",
    show: str = "",
    **kw: Any,
) -> Any:
    url = f"{TAB}/{competition or s.competition}/grades/{team or s.comets}"
    return browser.post(url, data=grade_form(s, grades, back, show), follow_redirects=False, **kw)


def post_raw(s: Scene, browser: TestClient, pairs: list[tuple[str, str]]) -> Any:
    """A hand-made body, which may repeat a field name."""
    body = urlencode([("subject", str(s.chemistry)), ("back", "1"), *pairs])
    return browser.post(
        f"{TAB}/{s.competition}/grades/{s.comets}",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def stored(s: Scene, team: int | None = None) -> dict[int, tuple[str, int | None]]:
    with Session(s.engine) as session:
        rows = session.exec(
            select(TeamAnswer).where(
                TeamAnswer.competition_id == s.competition,
                TeamAnswer.team_id == (team or s.comets),
            )
        )
        return {row.competition_question_id: (row.text, row.grade) for row in rows}


def snapshot(engine: Engine) -> list[tuple[Any, ...]]:
    with Session(engine) as session:
        return sorted(
            (a.competition_id, a.team_id, a.competition_question_id, a.text, a.grade)
            for a in session.exec(select(TeamAnswer))
        )


def sheet_forms(body: str) -> list[html.Form]:
    """The grading sheet's form, if the page has one (not the frame's theme or sign-out forms)."""
    return [f for f in html.forms(body, "main") if "/grades/" in f.action]


def fields(body: str) -> dict[str, str]:
    """The sheet's grade fields: `grade-<id>` → the value in the field."""
    (form,) = sheet_forms(body)
    return {i.name: i.value for i in form.inputs if i.type == "text" and i.name}


def cards(body: str) -> list[str]:
    """The text of each question card of the sheet."""
    (sheet,) = [o for o in html.parse(body).find_all("ol") if "answer-sheet" in o.classes()]
    return [item.text() for item in sheet.find_all("li")]


def rows(body: str) -> dict[str, dict[str, str]]:
    """Each listed row's cells by label, by team name."""
    return {r["Team"]: r for g in region_groups(body) for r in g.rows}


def filter_state(body: str) -> list[tuple[str, str, str | None]]:
    """`(text, href, aria-current)` of each filter link."""
    (nav,) = [n for n in html.parse(body).find_all("nav") if "filter-links" in n.classes()]
    return [(a.text(), a.attrs["href"], a.attrs.get("aria-current")) for a in nav.find_all("a")]


def location(response: Any) -> tuple[str, dict[str, list[str]], str]:
    assert response.status_code == 303, response.text
    parts = urlsplit(response.headers["location"])
    return parts.path, parse_qs(parts.query), parts.fragment


def refused(response: Any, name: str, reason: str, s: Scene, competition: int) -> None:
    """The 409 grading refusal (FR-039), with both ways back to the competitions list."""
    assert response.status_code == 409, response.text
    assert html.h1(response.text) == f"Grade answers of “{name}”?"
    assert reason in html.text(response.text, "main")
    back = f"{TAB}?{s.ctx}#competition-{competition}"
    pairs = html.link_pairs(response.text, "main")
    assert (back, "Back to competitions") in pairs
    assert (back, "Back to the competitions") in pairs


def no_names_in_addresses(body: str) -> None:
    for href in [link.href for link in html.links(body, "main")]:
        for name in ("Spring", "Comets", "Lions", "School", "Chemistry"):
            assert name not in href, href


# ---------------------------------------------------------------------------------------------
# User story 3: the Grades page
# ---------------------------------------------------------------------------------------------


def test_the_grades_page(scene: Scene) -> None:
    """US3-1–US3-4, FR-014–FR-018: the heading, the details, the back link, the overall progress,
    the filter links, the first page's region group and its rows."""
    before = snapshot(scene.engine)
    body = get(scene.olena, grades_url(scene))
    assert html.h1(body) == "Grades of “Spring round”"
    assert ("Subject", "Chemistry") in html.details(body)
    assert ("Start", "1 March 2027, 09:00") in html.details(body)
    assert ("Status", "Finished") in html.details(body)
    back = f"{TAB}?{scene.ctx}#competition-{scene.competition}"
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")
    assert "Graded 11 of 25 teams" in html.text(body, "main")
    assert filter_state(body) == [
        ("All teams", grades_url(scene), "true"),
        ("Ungraded only", grades_url(scene, "&show=ungraded"), None),
    ]
    groups = region_groups(body)
    assert [g.header for g in groups] == ["Kyiv · 12 teams"]
    listed = rows(body)
    assert list(listed) == ["Comets", *(f"Kyiv {n:02}" for n in range(1, 10))]
    assert listed["Comets"] == {
        "Team": "Comets",
        "Educational institution": "School No. 5",
        "Active members": "0",
        "Answered": "4 of 4",
        "Graded": "3 of 4",
        "Score": "17",
        "": "Grade answers",
    }
    assert (listed["Kyiv 01"]["Answered"], listed["Kyiv 01"]["Graded"]) == ("0 of 4", "0 of 0")
    assert listed["Kyiv 01"]["Score"] == "0"
    assert (listed["Kyiv 02"]["Graded"], listed["Kyiv 02"]["Score"]) == ("0 of 1", "0")
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
    for label, value in (("Answered", "4 of 4"), ("Graded", "3 of 4"), ("Score", "17")):
        assert f'<td data-label="{label}" class="cell-nowrap">{value}</td>' in body
    grade = [link.href for link in html.links(body, "main") if link.text == "Grade answers"]
    assert grade[0] == f"{TAB}/{scene.competition}/grades/{scene.comets}?{scene.ctx}"
    assert len(grade) == 10
    no_names_in_addresses(body)
    assert snapshot(scene.engine) == before


def test_every_team_is_listed_across_three_pages(scene: Scene) -> None:
    """US3-1, US3-5, FR-016, FR-017: deleted teams and teams of a deactivated institution or region,
    and teams of institutions Olena is not linked to; the region totals across pages."""
    second = get(scene.olena, grades_url(scene, "&p=2"))
    assert html.pagination(second, "Pages, top") is not None
    range_text, _ = html.pagination(second, "Pages, top") or ("", [])
    assert range_text == "Teams 11–20 of 25"
    assert [g.header for g in region_groups(second)] == ["Kyiv · 12 teams", "Lviv · 8 teams"]
    listed = rows(second)
    assert list(listed)[:4] == ["Novas", "Rockets", "Lions", "Lviv 01"]
    assert listed["Rockets"][""] == "(deleted) Grade answers"
    assert listed["Novas"][""] == "Grade answers"
    assert listed["Lions"]["Score"] == "0" and listed["Lions"]["Graded"] == "2 of 2"
    notes = [e.text() for e in html.parse(second).iter() if "row-note" in e.classes()]
    assert notes == ["(deleted)"]
    third = get(scene.olena, grades_url(scene, "&p=3"))
    assert [g.header for g in region_groups(third)] == ["Odesa · 5 teams"]
    assert list(rows(third)) == ["Odesa 01", "Odesa 02", "Odesa 03", "Odesa 04", "Stars"]
    beyond = get(scene.olena, grades_url(scene, "&p=9"))
    assert list(rows(beyond)) == list(rows(third))


def test_no_teams_in_the_competition(scene: Scene) -> None:
    """US3-6: whatever the filter, with no filter links."""
    empty = make_competition(
        scene.engine, scene.chemistry, "Empty round", starts_at=STARTED, stopped=True
    )
    for query in ("", "&show=ungraded"):
        body = get(scene.olena, grades_url(scene, query, competition=empty))
        text = html.text(body, "main")
        assert "No teams in this competition" in text
        assert "Graded 0 of 0 teams" in text
        assert "filter-links" not in body
        assert region_groups(body) == []


def test_the_back_link_falls_back_without_a_subject(scene: Scene) -> None:
    body = get(scene.olena, f"{TAB}/{scene.competition}/grades")
    back = f"{TAB}?{scene.ctx}#competition-{scene.competition}"
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")


# ---------------------------------------------------------------------------------------------
# User story 4: the grading sheet and its save
# ---------------------------------------------------------------------------------------------


def test_the_grading_sheet(scene: Scene) -> None:
    """US4-1, US4-2, FR-021–FR-023: from **Grade answers**; the heading, the institution, the back
    link; every question with its reference answer and the answer; a field only under answered
    ones, holding the saved grade."""
    page = get(scene.olena, grades_url(scene, "&p=1"))
    (href,) = [
        link.href
        for link in html.links(page, "main")
        if link.text == "Grade answers" and f"/grades/{scene.comets}?" in link.href
    ]
    body = get(scene.olena, href)
    assert html.h1(body) == "Grade answers of “Comets” in “Spring round”"
    assert ("Educational institution", "School No. 5") in html.details(body)
    back = f"{TAB}/{scene.competition}/grades?{scene.ctx}#team-{scene.comets}"
    assert (back, "Back to the grades") in html.link_pairs(body, "main")
    texts = cards(body)
    for n, text in enumerate(texts, start=1):
        assert text.startswith(f"Question {n} Question Question text {n}?")
        assert f"Reference answer Reference answer {n}." in text
        assert f"Answer to question {n} Answer of Comets" in text
        assert f"Grade for question {n}" in text
    assert fields(body) == {
        f"grade-{scene.copies[0]}": "5",
        f"grade-{scene.copies[1]}": "7",
        f"grade-{scene.copies[2]}": "5",
        f"grade-{scene.copies[3]}": "",
    }
    for copy in scene.copies:
        attrs = html.control(body, f"grade-{copy}")
        assert (attrs["type"], attrs["inputmode"], attrs["placeholder"]) == (
            "text",
            "numeric",
            "Not graded",
        )
    assert html.text(body, "main").count("A whole number from 0 to 10.") == 4
    (form,) = sheet_forms(body)
    assert form.action == f"{TAB}/{scene.competition}/grades/{scene.comets}"
    hidden = {i.name: i.value for i in form.inputs if i.type == "hidden"}
    assert hidden == {
        "subject": str(scene.chemistry),
        "status": "",
        "page": "1",
        "show": "",
        "back": "1",
    }
    assert [b.text for b in form.buttons] == ["Save grades"]
    no_names_in_addresses(body)


def test_line_breaks_and_unanswered_questions(scene: Scene) -> None:
    """US4-2: "Not answered" and no field; the answer keeps its line breaks."""
    team = scene.teams["Kyiv 02"]
    save_team_answer(scene.engine, scene.competition, team, scene.copies[2], "Line one\nLine two")
    body = get(scene.olena, sheet_url(scene, team))
    texts = cards(body)
    assert "Not answered" in texts[1] and "Grade for question 2" not in texts[1]
    assert "Not answered" in texts[3]
    assert set(fields(body)) == {f"grade-{scene.copies[0]}", f"grade-{scene.copies[2]}"}
    assert '<p class="keep-lines">Line one\nLine two</p>' in body


def test_one_save_stores_changes_and_empties(scene: Scene) -> None:
    """US4-3–US4-6, FR-024, FR-026: one save; the sheet again with the notice and the values;
    the Grades page follows; a reload saves nothing again."""
    q1, q2, q3, q4 = scene.copies
    response = post_grades(scene, scene.olena, {q1: "", q2: "0", q3: " 10 ", q4: "7"})
    path, query, _ = location(response)
    assert path == f"{TAB}/{scene.competition}/grades/{scene.comets}"
    assert query["subject"] == [str(scene.chemistry)] and "notice" in query
    body = follow(scene.olena, response)
    assert ("status", "Grades of “Comets” were saved") in html.notices(body)
    assert fields(body) == {
        f"grade-{q1}": "",
        f"grade-{q2}": "0",
        f"grade-{q3}": "10",
        f"grade-{q4}": "7",
    }
    assert {copy: grade for copy, (_, grade) in stored(scene).items()} == {
        q1: None,
        q2: 0,
        q3: 10,
        q4: 7,
    }
    before = snapshot(scene.engine)
    get(scene.olena, response.headers["location"])
    assert snapshot(scene.engine) == before
    listed = rows(get(scene.olena, grades_url(scene)))
    assert (listed["Comets"]["Graded"], listed["Comets"]["Score"]) == ("3 of 4", "17")
    post_grades(scene, scene.olena, {q1: "1", q2: "0", q3: "10", q4: "7"})
    page = get(scene.olena, grades_url(scene))
    assert (rows(page)["Comets"]["Graded"], rows(page)["Comets"]["Score"]) == ("4 of 4", "18")
    assert "Graded 12 of 25 teams" in html.text(page, "main")
    for value in ("Comets", "Spring"):
        assert value not in response.headers["location"]


def test_a_save_that_changes_nothing_shows_the_notice(scene: Scene) -> None:
    q1, q2, q3, q4 = scene.copies
    before = snapshot(scene.engine)
    body = follow(scene.olena, post_grades(scene, scene.olena, {q1: "5", q2: "7", q3: "5", q4: ""}))
    assert ("status", "Grades of “Comets” were saved") in html.notices(body)
    assert snapshot(scene.engine) == before


def test_a_team_with_no_answers_has_nothing_to_grade(scene: Scene) -> None:
    """US4-7, FR-022."""
    body = get(scene.olena, sheet_url(scene, scene.teams["Kyiv 01"]))
    text = html.text(body, "main")
    assert "“Kyiv 01” gave no answers, so there is nothing to grade" in text
    assert text.count("Not answered") == 4
    assert sheet_forms(body) == []
    assert "Save grades" not in text
    assert text.count("Reference answer Reference answer") == 4


def test_a_competition_with_no_questions(scene: Scene) -> None:
    """US4-8."""
    empty = make_competition(
        scene.engine, scene.chemistry, "Empty round", starts_at=STARTED, stopped=True
    )
    add_competition_team(scene.engine, empty, scene.comets)
    body = get(scene.olena, sheet_url(scene, competition=empty))
    assert "No questions in this competition" in html.text(body, "main")
    assert sheet_forms(body) == []


def test_a_deleted_team_is_marked_and_graded(scene: Scene) -> None:
    """US11-8, FR-043 step 5: "(deleted)" under the institution; the save works."""
    rockets = scene.teams["Rockets"]
    body = get(scene.olena, sheet_url(scene, rockets))
    notes = [e.text() for e in html.parse(body).iter() if "row-note" in e.classes()]
    assert notes == ["(deleted)"]
    assert post_grades(scene, scene.olena, {scene.copies[0]: "9"}, team=rockets).status_code == 303
    assert stored(scene, rockets) == {scene.copies[0]: ("Answer of Rockets", 9)}
    for name in ("Novas", "Stars"):
        team = scene.teams[name]
        assert post_grades(scene, scene.olena, {scene.copies[0]: "2"}, team=team).status_code == 303
        assert stored(scene, team)[scene.copies[0]][1] == 2


def test_the_back_page_is_kept_and_falls_back(scene: Scene) -> None:
    """FR-020: the sheet returns to `back`; without it, to the page that holds the team."""
    lions = scene.teams["Lions"]
    body = get(scene.olena, sheet_url(scene, lions))
    back = f"{TAB}/{scene.competition}/grades?{scene.ctx}&p=2#team-{lions}"
    assert (back, "Back to the grades") in html.link_pairs(body, "main")
    body = get(scene.olena, sheet_url(scene, lions, "&back=3"))
    back = f"{TAB}/{scene.competition}/grades?{scene.ctx}&p=3#team-{lions}"
    assert (back, "Back to the grades") in html.link_pairs(body, "main")


# ---------------------------------------------------------------------------------------------
# User story 5: invalid grades save nothing
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["7.5", "-1", "11", "seven"])
def test_an_invalid_grade_saves_nothing_and_keeps_every_value(scene: Scene, bad: str) -> None:
    """US5-1, FR-025."""
    q1, q2, q3, q4 = scene.copies
    before = snapshot(scene.engine)
    response = post_grades(scene, scene.olena, {q1: "6", q2: bad, q3: "", q4: "2"})
    assert response.status_code == 400
    body = response.text
    assert fields(body) == {
        f"grade-{q1}": "6",
        f"grade-{q2}": bad,
        f"grade-{q3}": "",
        f"grade-{q4}": "2",
    }
    assert html.field_error(body, f"grade-{q2}") == GRADE_ERROR
    assert html.control(body, f"grade-{q2}")["aria-invalid"] == "true"
    summary = html.error_summary(body)
    assert summary == html.Summary("There is a problem", [(f"#grade-{q2}", GRADE_ERROR)])
    assert snapshot(scene.engine) == before
    assert post_grades(scene, scene.olena, {q1: "6", q2: "8", q3: "", q4: "2"}).status_code == 303
    assert {copy: grade for copy, (_, grade) in stored(scene).items()} == {
        q1: 6,
        q2: 8,
        q3: None,
        q4: 2,
    }


def test_two_invalid_grades_in_question_order(scene: Scene) -> None:
    q1, q2, q3, q4 = scene.copies
    response = post_grades(scene, scene.olena, {q4: "x", q2: "6", q1: "99"})
    assert response.status_code == 400
    summary = html.error_summary(response.text)
    assert summary is not None
    assert summary.items == [(f"#grade-{q1}", GRADE_ERROR), (f"#grade-{q4}", GRADE_ERROR)]


# ---------------------------------------------------------------------------------------------
# User story 6: Ungraded only
# ---------------------------------------------------------------------------------------------


def test_ungraded_only(scene: Scene) -> None:
    """US6-1–US6-4, FR-019: from page 2 to page 1 of the filter; only the teams still to grade,
    counted on their own; the progress still counts all; the filter kept everywhere."""
    second = get(scene.olena, grades_url(scene, "&p=2"))
    (_, href, _), (_, ungraded_href, _) = filter_state(second)
    assert href == grades_url(scene)
    assert ungraded_href == grades_url(scene, "&show=ungraded")
    body = get(scene.olena, ungraded_href)
    assert filter_state(body) == [
        ("All teams", grades_url(scene), None),
        ("Ungraded only", grades_url(scene, "&show=ungraded"), "true"),
    ]
    assert 'aria-current="page"' not in html.outer_html(
        body, [n for n in html.parse(body).find_all("nav") if "filter-links" in n.classes()][0]
    )
    range_text, entries = html.pagination(body, "Pages, top") or ("", [])
    assert range_text == "Teams 1–10 of 14"
    assert [e.href for e in entries if e.text == "2"] == [grades_url(scene, "&show=ungraded&p=2")]
    assert [g.header for g in region_groups(body)] == ["Kyiv · 10 teams"]
    assert list(rows(body)) == ["Comets", *(f"Kyiv {n:02}" for n in range(2, 10)), "Novas"]
    assert "Graded 11 of 25 teams" in html.text(body, "main")
    page2 = get(scene.olena, grades_url(scene, "&show=ungraded&p=2"))
    assert [g.header for g in region_groups(page2)] == ["Odesa · 4 teams"]
    grade = [link.href for link in html.links(body, "main") if link.text == "Grade answers"]
    assert grade[0] == f"{TAB}/{scene.competition}/grades/{scene.comets}?{scene.ctx}&show=ungraded"
    sheet = get(scene.olena, grade[0])
    back = f"{TAB}/{scene.competition}/grades?{scene.ctx}&show=ungraded#team-{scene.comets}"
    assert (back, "Back to the grades") in html.link_pairs(sheet, "main")
    (form,) = sheet_forms(sheet)
    assert {i.name: i.value for i in form.inputs if i.type == "hidden"}["show"] == "ungraded"


def test_grading_the_last_answer_drops_the_team_from_the_filter(scene: Scene) -> None:
    """US6-5, FR-020: the way back leads to the same page without the team and no anchor."""
    q4 = scene.copies[3]
    response = post_grades(scene, scene.olena, {q4: "3"}, back="1", show="ungraded")
    path, query, _ = location(response)
    assert query["show"] == ["ungraded"]
    body = follow(scene.olena, response)
    back = f"{TAB}/{scene.competition}/grades?{scene.ctx}&show=ungraded"
    assert (back, "Back to the grades") in html.link_pairs(body, "main")
    listed = get(scene.olena, back)
    assert "Comets" not in rows(listed)
    assert "Graded 12 of 25 teams" in html.text(listed, "main")


def test_the_back_link_to_a_page_that_no_longer_exists_is_clamped(scene: Scene) -> None:
    """FR-020: back to page 2 of **Ungraded only**, which has emptied: the last page."""
    for name in ("Odesa 01", "Odesa 02", "Odesa 03", "Stars"):
        post_grades(
            scene,
            scene.olena,
            {scene.copies[0]: "1"},
            team=scene.teams[name],
            back="2",
            show="ungraded",
        )
    body = get(scene.olena, sheet_url(scene, scene.teams["Stars"], "&show=ungraded&back=2"))
    back = f"{TAB}/{scene.competition}/grades?{scene.ctx}&show=ungraded&p=2"
    assert (back, "Back to the grades") in html.link_pairs(body, "main")
    listed = get(scene.olena, back)
    range_text, _ = html.pagination(listed, "Pages, top") or ("", [])
    assert range_text == "Teams 1–10 of 10"


def test_all_teams_are_graded(scene: Scene) -> None:
    """US6-6."""
    with Session(scene.engine) as session:
        for answer in session.exec(select(TeamAnswer)):
            answer.grade = 1
            session.add(answer)
        session.commit()
    body = get(scene.olena, grades_url(scene, "&show=ungraded"))
    assert "All teams are graded" in html.text(body, "main")
    assert "Graded 25 of 25 teams" in html.text(body, "main")
    assert region_groups(body) == []


@pytest.mark.parametrize("value", ["all", "Ungraded", "x", ""])
def test_an_unknown_filter_reads_as_all_teams(scene: Scene, value: str) -> None:
    body = get(scene.olena, grades_url(scene, f"&show={value}"))
    assert [current for _, _, current in filter_state(body)] == ["true", None]
    assert len(rows(body)) == 10


# ---------------------------------------------------------------------------------------------
# User story 10: grading only on a finished competition
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seed", "reason"),
    [
        (
            {"starts_at": LATER},
            "“Open round” has not started yet, so its answers cannot be graded.",
        ),
        (
            {"starts_at": STARTED},
            "“Open round” is still in progress, so its answers cannot be graded until it is"
            " finished.",
        ),
        (
            {"starts_at": STARTED, "cancelled": True},
            "“Open round” has been cancelled, so its answers cannot be graded.",
        ),
    ],
)
def test_grading_is_refused_unless_finished(
    scene: Scene, seed: dict[str, Any], reason: str
) -> None:
    """US10-1–US10-4, FR-039: the three routes, also with an unknown team (the status first)."""
    competition = make_competition(scene.engine, scene.chemistry, "Open round", **seed)
    copy = add_competition_question(scene.engine, competition, scene.question_ids[0])
    add_competition_team(scene.engine, competition, scene.comets)
    save_team_answer(scene.engine, competition, scene.comets, copy, "Answer")
    before = snapshot(scene.engine)
    for response in (
        scene.olena.get(grades_url(scene, competition=competition)),
        scene.olena.get(sheet_url(scene, competition=competition)),
        scene.olena.get(sheet_url(scene, MISSING, competition=competition)),
        post_grades(scene, scene.olena, {copy: "5"}, competition=competition),
        post_grades(scene, scene.olena, {copy: "5"}, team=MISSING, competition=competition),
    ):
        refused(response, "Open round", reason, scene, competition)
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 11: only the right teacher
# ---------------------------------------------------------------------------------------------

PREFIX = f"{TAB}/{{competition_id:int}}/grades"
GRADE_ROUTES = sorted(
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
    assert GRADE_ROUTES == [
        ("GET", PREFIX),
        ("GET", f"{PREFIX}/{{team_id:int}}"),
        ("POST", f"{PREFIX}/{{team_id:int}}"),
    ]


@pytest.mark.parametrize(("method", "path"), GRADE_ROUTES)
@pytest.mark.parametrize("ids", ["real", "unknown"])
def test_other_roles_are_refused_before_any_id_is_read(
    scene: Scene, client: TestClient, client_as: ClientAs, method: str, path: str, ids: str
) -> None:
    """US11-1: administrators and students, also with unknown ids; nothing changes; anonymous
    visitors are sent to sign in."""
    competition, team = (scene.competition, scene.comets) if ids == "real" else (MISSING, MISSING)
    url = concrete(path, competition, team, scene.ctx)
    data = grade_form(scene, {scene.copies[0]: "1"})
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


@pytest.mark.parametrize(("method", "path"), GRADE_ROUTES)
@pytest.mark.parametrize("target", ["real", "unknown", "bad-subject", "in-progress"])
def test_a_teacher_without_the_setting_is_refused_before_anything_is_looked_up(
    scene: Scene, client_as: ClientAs, method: str, path: str, target: str
) -> None:
    """US11-2, FR-002, FR-043: Taras, and the cast teacher, whatever the ids."""
    running = make_competition(scene.engine, scene.chemistry, "Running", starts_at=STARTED)
    competition, team, query = {
        "real": (scene.competition, scene.comets, scene.ctx),
        "unknown": (MISSING, MISSING, scene.ctx),
        "bad-subject": (scene.competition, scene.comets, "subject=abc"),
        "in-progress": (running, MISSING, scene.ctx),
    }[target]
    url = concrete(path, competition, team, query)
    data = grade_form(scene, {scene.copies[0]: "1"})
    before = snapshot(scene.engine)
    for browser in (scene.taras, client_as(TEACHER_EMAIL)):
        denied(send(browser, method, url, data))
    assert snapshot(scene.engine) == before


def remove_setting(engine: Engine) -> None:
    with Session(engine) as session:
        user = get_user_by_email(session, OLENA)
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


def test_the_setting_taken_away_while_a_sheet_is_open(scene: Scene) -> None:
    """US11-3: the save is denied and the grades saved before stay."""
    post_grades(scene, scene.olena, {scene.copies[3]: "4"})
    get(scene.olena, sheet_url(scene))
    remove_setting(scene.engine)
    before = snapshot(scene.engine)
    denied(post_grades(scene, scene.olena, {scene.copies[3]: "9"}))
    assert snapshot(scene.engine) == before
    assert stored(scene)[scene.copies[3]][1] == 4


@pytest.mark.parametrize(("method", "path"), GRADE_ROUTES)
def test_unknown_mismatched_and_hidden_subjects_and_competitions(
    scene: Scene, method: str, path: str
) -> None:
    """US11-4, FR-043 step 3: each before the status."""
    biology = make_subject(scene.engine, "Biology")
    hidden = make_competition(scene.engine, biology, "Hidden round", starts_at=LATER)
    make_competition(scene.engine, biology, "Finished round", starts_at=STARTED, stopped=True)
    with Session(scene.engine) as session:
        set_subject_active(session, biology, False)
    data = grade_form(scene, {scene.copies[0]: "1"})
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
    before = snapshot(scene.engine)
    for url, page in cases:
        form = data | {"subject": parse_qs(urlsplit(url).query).get("subject", [""])[0]}
        not_found(send(scene.olena, method, url, form), page)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), [r for r in GRADE_ROUTES if "team_id" in r[1]])
def test_unknown_and_foreign_teams_are_not_found(scene: Scene, method: str, path: str) -> None:
    """US11-5: an unknown team, one not in the competition, ids above `MAX_ID`."""
    outside = make_team(scene.engine, scene.school, "Outside")
    data = grade_form(scene, {scene.copies[0]: "1"})
    before = snapshot(scene.engine)
    for team in (MISSING, outside, MAX_ID + 1, "9" * 30):
        url = concrete(path, scene.competition, team, scene.ctx)
        not_found(send(scene.olena, method, url, data), TEAM_NOT_FOUND)
    assert snapshot(scene.engine) == before


def test_questions_that_cannot_be_graded_are_not_found(scene: Scene) -> None:
    """US11-6, FR-043 step 5: another competition's copy, a question the team did not answer,
    an unknown id, a name that is no id, the same name twice and two spellings of one id."""
    other = make_competition(
        scene.engine, scene.chemistry, "Other", starts_at=STARTED, stopped=True
    )
    foreign = add_competition_question(scene.engine, other, scene.question_ids[0])
    q1 = scene.copies[0]
    kyiv02 = scene.teams["Kyiv 02"]
    before = snapshot(scene.engine)
    for grades in ({q1: "1", foreign: "2"}, {q1: "1", MISSING: "2"}):
        not_found(post_grades(scene, scene.olena, grades), QUESTION_NOT_FOUND)
    not_found(
        post_grades(scene, scene.olena, {q1: "1", scene.copies[1]: "2"}, team=kyiv02),
        QUESTION_NOT_FOUND,
    )
    for pairs in (
        [(f"grade-{q1}", "1"), ("grade-x", "2")],
        [(f"grade-{q1}", "1"), (f"grade-{q1}", "2")],
        [(f"grade-{q1}", "1"), (f"grade-0{q1}", "2")],
        [("grade-", "1")],
    ):
        not_found(post_raw(scene, scene.olena, pairs), QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == before
    assert post_raw(scene, scene.olena, [(f"grade-{q1}", "1")]).status_code == 303
    assert stored(scene)[q1][1] == 1


def test_a_teacher_with_the_setting_grades_any_team(scene: Scene) -> None:
    """US11-7, FR-001: Olena is linked to none of these teams' institutions."""
    lions = scene.teams["Lions"]
    assert post_grades(scene, scene.olena, {scene.copies[0]: "6"}, team=lions).status_code == 303
    assert stored(scene, lions)[scene.copies[0]][1] == 6


@pytest.mark.parametrize(
    "forged", [{"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://evil.example"}]
)
def test_a_cross_site_save_changes_nothing(scene: Scene, forged: dict[str, str]) -> None:
    """US11-9."""
    before = snapshot(scene.engine)
    response = post_grades(scene, scene.olena, {scene.copies[3]: "1"}, headers=forged)
    assert response.status_code == 403
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    "query", ["subject=1e9999", "subject=%00", "p=-1", "p=1e9", "back=%00", "show=%00"]
)
def test_odd_values_never_get_a_json_error(scene: Scene, query: str) -> None:
    for url in (
        f"{TAB}/{scene.competition}/grades?{query}",
        f"{TAB}/{scene.competition}/grades/{scene.comets}?{query}",
    ):
        response = scene.olena.get(url)
        assert response.status_code in (200, 404), (url, response.status_code)
        assert response.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("email", [TEACHER_EMAIL, ADMIN_EMAIL, STUDENT_EMAIL])
def test_a_path_id_that_is_no_number_matches_no_route(client_as: ClientAs, email: str) -> None:
    for url in (f"{TAB}/abc/grades", f"{TAB}/1/grades/abc"):
        response = client_as(email).get(url, follow_redirects=False)
        assert response.status_code == 404
        assert "Competition not found" not in response.text


# ---------------------------------------------------------------------------------------------
# User story 12: two teachers grade the same team
# ---------------------------------------------------------------------------------------------


def test_the_later_save_wins(scene: Scene, client_as: ClientAs) -> None:
    """US12-1, FR-030: both open the sheet; the first grades question 2; the second, from its
    page, empties question 1 and grades question 3: the second page's grades, exactly."""
    institution = make_institution(scene.engine, "Lviv Office", "Lviv")
    make_teacher(
        scene.engine,
        app.state.settings,
        email="second@example.org",
        institutions={institution: AccessLevel.READ},
        can_manage=True,
    )
    second = client_as("second@example.org")
    q1, q2, q3, q4 = scene.copies
    first_page = fields(get(scene.olena, sheet_url(scene)))
    second_page = fields(get(second, sheet_url(scene)))
    assert first_page == second_page
    assert post_grades(scene, scene.olena, {q1: "5", q2: "8", q3: "5", q4: ""}).status_code == 303
    response = post_grades(scene, second, {q1: "", q2: "7", q3: "6", q4: ""})
    body = follow(second, response)
    assert "warning" not in body.lower()
    assert {copy: grade for copy, (_, grade) in stored(scene).items()} == {
        q1: None,
        q2: 7,
        q3: 6,
        q4: None,
    }


# ---------------------------------------------------------------------------------------------
# User story 13: a finished competition of a deactivated subject
# ---------------------------------------------------------------------------------------------


def test_a_deactivated_subject_keeps_its_finished_competition_gradable(scene: Scene) -> None:
    """US13-1, US13-2, FR-042: the menu offers **Answers** and **Grades** only; the Grades page,
    the sheet and the save work; an In progress competition of it is not found."""
    running = make_competition(scene.engine, scene.chemistry, "Running", starts_at=STARTED)
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    listing = get(scene.olena, f"{TAB}?{scene.ctx}")
    menu = [
        link.text for link in html.links(listing, "main") if f"/{scene.competition}/" in link.href
    ]
    assert menu == ["Questions", "Teams", "Answers", "Grades"]
    assert "Graded 11 of 25 teams" in html.text(get(scene.olena, grades_url(scene)), "main")
    get(scene.olena, sheet_url(scene))
    before = snapshot(scene.engine)
    assert post_grades(scene, scene.olena, {scene.copies[3]: "2"}).status_code == 303
    changed = [row for row in snapshot(scene.engine) if row not in before]
    assert [(row[1], row[2], row[4]) for row in changed] == [(scene.comets, scene.copies[3], 2)]
    for url in (
        grades_url(scene, competition=running),
        f"{TAB}/{running}/finish?{scene.ctx}",
    ):
        not_found(scene.olena.get(url), COMPETITION_NOT_FOUND)
