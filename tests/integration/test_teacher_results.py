"""Publishing a competition's results and downloading them, end to end through the test client
(milestone 12.8).

See specs/012.8-publishing-results/spec.md US1–US3, US7 and contracts/http-routes.md §1–§3. Every
case runs on both engines. The clock is fixed at 1 March 2027 09:00 UTC by patching
`app.services.competitions.utc_now`; no test waits. The manager's browser zone is `Europe/Kyiv`.

- Olena: a teacher with **Can manage competitions**, linked (Read) only to Kharkiv Gymnasium,
  which has no team in the competition;
- Taras: a teacher without it, with **Write** access to Odesa College, which has no team in it;
- the cast teacher (`TEACHER_EMAIL`): no link at all;
- "Spring round": a Finished competition of Chemistry, started 1 March 2027 09:30 Kyiv time, with
  2 questions; "Comets" (School No. 5, Kyiv) and "Lions" (Lyceum No. 2, Lviv) are in it.

The publish routes are also in the access sweep of `test_teacher_competitions.py` (manage
routes); the download is swept here, since every teacher may open it.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, select
from sqlmodel import Session

from app.main import app
from app.models import AccessLevel, Competition, CompetitionResultsFile, Role, Subject
from app.routers.teacher_competition_entries import ListContext
from app.routers.teacher_grades import grades_path
from app.services.competitions import CompetitionStatus
from app.services.grades import GradeFilter
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    AUTO,
    EN_FILE,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    UK_FILE,
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
    store_results_files,
)
from tests.integration.test_routes import ALL_ROUTES
from tests.integration.test_teacher_competitions import set_setting
from tests.pdf import pdf_text

TAB = "/teacher/competitions"
OLENA = "olena@example.org"
TARAS = "taras@example.org"
KYIV = "Europe/Kyiv"
NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 7, 30, tzinfo=UTC)
"""09:30 in Kyiv."""
MISSING = 999_999

CONSEQUENCE = (
    "The results will be published for every teacher as PDF files in Ukrainian and English. "
    "Publishing is permanent: the results cannot be unpublished, and the grades can no longer be "
    "changed."
)
BLOCKED = "Every team must be graded before the results can be published."
COMPETITION_NOT_FOUND = (
    "Competition not found",
    "This competition does not exist, or its subject is deactivated.",
)
SUBJECT_NOT_FOUND = (
    "Subject not found",
    "This subject does not exist, or it is deactivated and has no finished competitions.",
)
RESULTS_ROUTE = f"{TAB}/{{competition_id:int}}/results"


@dataclass(frozen=True)
class Scene:
    engine: Engine
    olena: TestClient
    taras: TestClient
    chemistry: int
    competition: int
    copies: list[int]
    comets: int
    lions: int


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
    lyceum = make_institution(engine, "Lyceum No. 2", "Lviv")
    gymnasium = make_institution(engine, "Kharkiv Gymnasium", "Kharkiv")
    odesa = make_institution(engine, "Odesa College", "Odesa")
    make_teacher(
        engine,
        settings,
        email=OLENA,
        institutions={gymnasium: AccessLevel.READ},
        can_manage=True,
    )
    make_teacher(engine, settings, email=TARAS, institutions={odesa: AccessLevel.WRITE})
    chemistry = make_subject(engine, "Chemistry")
    competition = make_competition(engine, chemistry, starts_at=STARTED, stopped=True)
    questions = [make_question(engine, chemistry, f"Question {n}?", f"Ref {n}.") for n in (1, 2)]
    copies = [add_competition_question(engine, competition, q) for q in questions]
    comets = make_team(engine, school, "Comets")
    lions = make_team(engine, lyceum, "Lions")
    for team in (comets, lions):
        add_competition_team(engine, competition, team)
    olena = client_as(OLENA)
    olena.cookies.set("sc_time_zone", KYIV)
    return Scene(
        engine=engine,
        olena=olena,
        taras=client_as(TARAS),
        chemistry=chemistry,
        competition=competition,
        copies=copies,
        comets=comets,
        lions=lions,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

SNAPSHOT_TABLES = ("competitions", "competition_results_files", "team_answers")


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def answer(s: Scene, team: int, copy: int, grade: int | None) -> None:
    save_team_answer(s.engine, s.competition, team, copy, "An answer")
    if grade is not None:
        grade_answer(s.engine, s.competition, team, copy, grade)


def grade_everything(s: Scene) -> None:
    """Comets 7 + 10 = 17; Lions 4."""
    answer(s, s.comets, s.copies[0], 7)
    answer(s, s.comets, s.copies[1], 10)
    answer(s, s.lions, s.copies[0], 4)


def confirmation(s: Scene, query: str = "", browser: TestClient | None = None) -> Any:
    return (browser or s.olena).get(f"{TAB}/{s.competition}/publish?subject={s.chemistry}{query}")


def publish(
    browser: TestClient, competition: int, subject: int | str, status: str = "", page: str = "1"
) -> Any:
    data = {"subject": str(subject), "status": status, "page": page}
    return browser.post(f"{TAB}/{competition}/publish", data=data, follow_redirects=False)


def published_at(engine: Engine, competition: int) -> datetime | None:
    with Session(engine) as session:
        row = session.get(Competition, competition)
        assert row is not None
        return row.published_at


def files(engine: Engine) -> dict[tuple[int, str], bytes]:
    with Session(engine) as session:
        return {
            (f.competition_id, f.language): f.content
            for f in session.exec(select(CompetitionResultsFile)).scalars()
        }


def address(response: Any) -> tuple[str, dict[str, list[str]], str]:
    assert response.status_code == 303, response.text
    parts = urlsplit(response.headers["location"])
    query = parse_qs(parts.query)
    query.pop("notice", None)
    return parts.path, query, parts.fragment


def denied(response: Any) -> None:
    assert response.status_code == 403
    assert "Your current role, Teacher, cannot open this page." in response.text


def not_found(response: Any, page: tuple[str, str]) -> None:
    assert response.status_code == 404
    assert html.h1(response.text) == page[0]
    assert page[1] in response.text


def refused(response: Any, name: str, reason: str, back: str) -> None:
    assert response.status_code == 409
    assert html.h1(response.text) == f"Publish the results of “{name}”?"
    assert reason in html.text(response.text, "main")
    pairs = html.link_pairs(response.text, "main")
    assert (back, "Back to competitions") in pairs


def menu(body: str, competition: int) -> list[tuple[str, str, bool]]:
    """`(text, href, marked as a download)` of the row's menu entries."""
    for tr in html.parse(body).find_all("tr"):
        if tr.attrs.get("id") == f"competition-{competition}":
            return [
                (a.text(), a.attrs["href"], "download" in a.attrs)
                for d in tr.find_all("details")
                for a in d.find_all("a")
            ]
    raise AssertionError(f"no row for competition {competition}")


# ---------------------------------------------------------------------------------------------
# User story 1: publishing (FR-004–FR-010)
# ---------------------------------------------------------------------------------------------


def test_the_confirmation(scene: Scene) -> None:
    """US1-1, FR-007, FR-008: the question with the start in the browser's zone, the badge, the
    progress, the consequence; a primary **Publish results** and **Keep unpublished**."""
    grade_everything(scene)
    body = confirmation(scene, "&status=finished&page=2").text
    assert html.h1(body) == (
        "Publish the results of “Spring round” of Chemistry, started 1 March 2027, 09:30?"
    )
    assert "<title>Publish the results of “Spring round”? — " in body
    main = html.text(body, "main")
    assert CONSEQUENCE in main
    assert "Graded 2 of 2 teams" in main
    assert html.badges(body) == ["Finished"]
    back = f"{TAB}?subject={scene.chemistry}&status=finished&page=2#competition-{scene.competition}"
    assert (back, "Keep unpublished") in html.link_pairs(body, "main")
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")
    (form,) = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == f"{TAB}/{scene.competition}/publish"
    assert [b.text for b in form.buttons] == ["Publish results"]
    assert "destructive" not in form.buttons[0].attrs.get("class", "")
    assert {i.name: i.value for i in form.inputs} == {
        "subject": str(scene.chemistry),
        "status": "finished",
        "page": "2",
    }
    assert files(scene.engine) == {}


@pytest.mark.parametrize("status", ["", "published"])
def test_publishing_under_all_or_published_lands_at_the_competition(
    scene: Scene, status: str
) -> None:
    """US1-3, FR-010: the same list, at the competition, with its notice and new badge."""
    grade_everything(scene)
    response = publish(scene.olena, scene.competition, scene.chemistry, status)
    path, query, anchor = address(response)
    expected = {"subject": [str(scene.chemistry)]} | ({"status": [status]} if status else {})
    assert (path, query, anchor) == (TAB, expected, f"competition-{scene.competition}")
    body = scene.olena.get(response.headers["location"]).text
    assert ("status", "The results of “Spring round” were published") in html.notices(body)
    assert "Published" in html.badges(body)
    assert published_at(scene.engine, scene.competition) == NOW
    assert sorted(files(scene.engine)) == [
        (scene.competition, "en"),
        (scene.competition, "uk"),
    ]


def test_publishing_under_finished_lands_where_it_was(scene: Scene) -> None:
    """US1-4: the row that took its place; then, with none left, the empty state."""
    grade_everything(scene)
    earlier = make_competition(
        scene.engine,
        scene.chemistry,
        "Earlier",
        starts_at=STARTED - timedelta(days=1),
        stopped=True,
    )
    _, query, anchor = address(publish(scene.olena, scene.competition, scene.chemistry, "finished"))
    assert (query, anchor) == (
        {"subject": [str(scene.chemistry)], "status": ["finished"]},
        f"competition-{earlier}",
    )
    response = publish(scene.olena, earlier, scene.chemistry, "finished")
    _, _, anchor = address(response)
    assert anchor == ""
    body = scene.olena.get(response.headers["location"]).text
    assert ("status", "The results of “Earlier” were published") in html.notices(body)


def test_after_publishing_the_menu_changes_and_a_reload_sends_nothing(scene: Scene) -> None:
    """US1-6, FR-005, FR-006: no **Publish results**; **Download results** for every teacher."""
    grade_everything(scene)
    response = publish(scene.olena, scene.competition, scene.chemistry)
    location = response.headers["location"]
    body = scene.olena.get(location).text
    download = f"{TAB}/{scene.competition}/results?subject={scene.chemistry}"
    entries = menu(body, scene.competition)
    assert [text for text, _, _ in entries] == [
        "Questions",
        "Teams",
        "Answers",
        "Grades",
        "Download results",
    ]
    assert entries[-1] == ("Download results", download, True)
    before = snapshot(scene.engine)
    assert scene.olena.get(location).status_code == 200
    assert snapshot(scene.engine) == before


def test_keep_unpublished_changes_nothing(scene: Scene) -> None:
    grade_everything(scene)
    before = snapshot(scene.engine)
    body = confirmation(scene).text
    back = f"{TAB}?subject={scene.chemistry}#competition-{scene.competition}"
    assert scene.olena.get(back).status_code == 200
    assert (back, "Keep unpublished") in html.link_pairs(body, "main")
    assert snapshot(scene.engine) == before


def test_without_the_setting_there_is_no_publish(scene: Scene) -> None:
    """FR-003: no entry, and 403 before any id is read, for an unknown competition too."""
    grade_everything(scene)
    body = scene.taras.get(f"{TAB}?subject={scene.chemistry}").text
    assert "Publish results" not in [text for text, _, _ in menu(body, scene.competition)]
    before = snapshot(scene.engine)
    for competition in (scene.competition, MISSING):
        denied(scene.taras.get(f"{TAB}/{competition}/publish?subject={scene.chemistry}"))
        denied(publish(scene.taras, competition, scene.chemistry))
    assert snapshot(scene.engine) == before


def test_the_setting_taken_away_while_the_confirmation_is_open(scene: Scene) -> None:
    """FR-003, spec Edge Cases: the publish gets 403 and stores nothing; so does the next page."""
    grade_everything(scene)
    assert confirmation(scene).status_code == 200
    set_setting(scene.engine, OLENA, False)
    denied(publish(scene.olena, scene.competition, scene.chemistry))
    assert published_at(scene.engine, scene.competition) is None
    assert files(scene.engine) == {}
    denied(confirmation(scene))


# ---------------------------------------------------------------------------------------------
# User story 2: only when fully graded (FR-011–FR-014)
# ---------------------------------------------------------------------------------------------


def blocked_links(body: str) -> list[tuple[str, str]]:
    (section,) = [s for s in html.parse(body).find_all("section") if "confirmation" in s.classes()]
    return [(a.attrs["href"], a.text()) for a in section.find_all("a")]


def test_the_blocked_confirmation(scene: Scene) -> None:
    """US2-1, FR-012: the progress, the explanation, **Grade the remaining teams** then **Keep
    unpublished**, and no button."""
    answer(scene, scene.comets, scene.copies[0], 7)
    answer(scene, scene.lions, scene.copies[0], None)
    body = confirmation(scene, "&status=finished&page=2").text
    assert "Graded 1 of 2 teams" in html.text(body, "main")
    assert BLOCKED in html.text(body, "main")
    assert [f for f in html.forms(body, "main") if f.method == "post"] == []
    query = f"subject={scene.chemistry}&status=finished&page=2"
    assert blocked_links(body) == [
        (f"{TAB}/{scene.competition}/grades?{query}&show=ungraded", "Grade the remaining teams"),
        (f"{TAB}?{query}#competition-{scene.competition}", "Keep unpublished"),
    ]


@pytest.mark.parametrize(("status", "page"), [(None, 1), (CompetitionStatus.FINISHED, 2)])
def test_grade_the_remaining_teams_is_the_grades_address(
    scene: Scene, status: CompetitionStatus | None, page: int
) -> None:
    """The link is built by hand in `teacher_competitions` (no circular import); it must equal
    what `teacher_grades.grades_path` builds for the same list context."""
    answer(scene, scene.lions, scene.copies[0], None)
    query = f"&status={status.value}" if status else ""
    query += f"&page={page}" if page > 1 else ""
    (href, _), _ = blocked_links(confirmation(scene, query).text)
    with Session(scene.engine) as session:
        subject = session.get(Subject, scene.chemistry)
        assert subject is not None
        context = ListContext(subject=subject, status=status, page=page)
        expected = grades_path(scene.competition, context, GradeFilter.UNGRADED)
    assert href == expected


def test_grade_the_remaining_teams_opens_ungraded_only_and_leads_back(scene: Scene) -> None:
    """US2-2: the Grades page under **Ungraded only**, whose back link returns to the list."""
    answer(scene, scene.lions, scene.copies[0], None)
    (href, _), _ = blocked_links(confirmation(scene, "&status=finished&page=2").text)
    body = scene.olena.get(href).text
    assert html.h1(body) == "Grades of “Spring round”"
    current = [a.text() for a in html.parse(body).find_all("a") if a.attrs.get("aria-current")]
    assert "Ungraded only" in current
    back = f"{TAB}?subject={scene.chemistry}&status=finished&page=2#competition-{scene.competition}"
    assert (back, "Back to the competitions") in html.link_pairs(body, "main")


def test_a_publish_sent_while_a_team_is_ungraded_is_refused(scene: Scene) -> None:
    """US2-3, FR-013: the blocked page again, 409; nothing changes."""
    answer(scene, scene.lions, scene.copies[0], None)
    before = snapshot(scene.engine)
    response = publish(scene.olena, scene.competition, scene.chemistry, "finished")
    assert response.status_code == 409
    assert BLOCKED in html.text(response.text, "main")
    assert "Graded 1 of 2 teams" in html.text(response.text, "main")
    assert snapshot(scene.engine) == before
    grade_answer(scene.engine, scene.competition, scene.lions, scene.copies[0], 5)
    body = confirmation(scene).text
    assert [b.text for f in html.forms(body, "main") for b in f.buttons] == ["Publish results"]


def test_a_competition_with_no_teams_is_published(scene: Scene) -> None:
    """US2-5, FR-014."""
    empty = make_competition(
        scene.engine, scene.chemistry, "Empty", starts_at=STARTED, stopped=True
    )
    body = scene.olena.get(f"{TAB}/{empty}/publish?subject={scene.chemistry}").text
    assert "Graded 0 of 0 teams" in html.text(body, "main")
    assert publish(scene.olena, empty, scene.chemistry).status_code == 303
    english = pdf_text(files(scene.engine)[(empty, "en")])
    assert "No teams took part in this competition." in english


# ---------------------------------------------------------------------------------------------
# User story 3: refusals (FR-015, FR-016)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        (
            {"starts_at": datetime(2027, 3, 14, 8, 0, tzinfo=UTC)},
            "“Other” has not started yet, so it has no results to publish.",
        ),
        (
            {"starts_at": STARTED},
            "“Other” is still in progress. Finish it and grade its answers before publishing its "
            "results.",
        ),
        (
            {"starts_at": STARTED, "cancelled": True},
            "“Other” has been cancelled, so it has no results to publish.",
        ),
        (
            {"starts_at": STARTED, "stopped": True, "published": True},
            "The results of “Other” are already published.",
        ),
    ],
)
def test_the_refusals_for_each_status(scene: Scene, kwargs: dict[str, Any], reason: str) -> None:
    other = make_competition(scene.engine, scene.chemistry, "Other", **kwargs)
    back = f"{TAB}?subject={scene.chemistry}#competition-{other}"
    before = snapshot(scene.engine)
    refused(
        scene.olena.get(f"{TAB}/{other}/publish?subject={scene.chemistry}"), "Other", reason, back
    )
    refused(publish(scene.olena, other, scene.chemistry), "Other", reason, back)
    assert snapshot(scene.engine) == before


def test_the_same_form_twice_publishes_once(scene: Scene) -> None:
    grade_everything(scene)
    assert publish(scene.olena, scene.competition, scene.chemistry).status_code == 303
    stored = files(scene.engine)
    back = f"{TAB}?subject={scene.chemistry}#competition-{scene.competition}"
    refused(
        publish(scene.olena, scene.competition, scene.chemistry),
        "Spring round",
        "The results of “Spring round” are already published.",
        back,
    )
    assert files(scene.engine) == stored


# ---------------------------------------------------------------------------------------------
# User story 7: every teacher downloads the results (FR-002, FR-030–FR-033)
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def published(scene: Scene) -> int:
    """A Published competition of Chemistry with known stored bytes."""
    competition = make_competition(
        scene.engine,
        scene.chemistry,
        "Весняний тур: фінал",
        starts_at=STARTED,
        stopped=True,
        published=True,
    )
    store_results_files(scene.engine, competition)
    return competition


def download(browser: TestClient, competition: int, subject: int | str) -> Any:
    return browser.get(f"{TAB}/{competition}/results?subject={subject}", follow_redirects=False)


@pytest.mark.parametrize("who", ["olena", "taras", "unlinked"])
def test_every_teacher_downloads_the_stored_file(
    scene: Scene, client_as: ClientAs, published: int, who: str
) -> None:
    """US7-1, US7-2, FR-002, FR-030: with or without the setting, linked or not to the teams'
    institutions; the stored bytes of the current language, with the four headers."""
    browser = {"olena": scene.olena, "taras": scene.taras}.get(who) or client_as(TEACHER_EMAIL)
    response = download(browser, published, scene.chemistry)
    assert response.status_code == 200
    assert response.content == EN_FILE
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    browser.cookies.set("sc_lang", "uk")
    assert download(browser, published, scene.chemistry).content == UK_FILE


def test_the_file_name(scene: Scene, published: int) -> None:
    """FR-032: "<name> <YYYY-MM-DD>.pdf", the date in Kyiv time; ":" replaced; Cyrillic kept in
    `filename*`, an ASCII fallback in `filename`."""
    disposition = download(scene.olena, published, scene.chemistry).headers["content-disposition"]
    name = "Весняний тур_ фінал 2027-03-01.pdf"
    assert disposition == (
        f"attachment; filename=\"_ _ _ 2027-03-01.pdf\"; filename*=UTF-8''{quote(name, safe='')}"
    )
    latin = make_competition(
        scene.engine, scene.chemistry, "Spring round 2", starts_at=STARTED, stopped=True,
        published=True,
    )  # fmt: skip
    store_results_files(scene.engine, latin)
    disposition = download(scene.olena, latin, scene.chemistry).headers["content-disposition"]
    assert disposition == (
        'attachment; filename="Spring round 2 2027-03-01.pdf"; '
        "filename*=UTF-8''Spring%20round%202%202027-03-01.pdf"
    )


def test_the_menu_offers_the_download_on_published_rows_only(scene: Scene, published: int) -> None:
    """US7-1, US7-4, FR-006, FR-031: a link marked as a download, for every teacher."""
    for browser in (scene.olena, scene.taras):
        body = browser.get(f"{TAB}?subject={scene.chemistry}").text
        entries = menu(body, published)
        assert (
            "Download results",
            f"{TAB}/{published}/results?subject={scene.chemistry}",
            True,
        ) in entries
        assert "Download results" not in [t for t, _, _ in menu(body, scene.competition)]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"starts_at": datetime(2027, 3, 14, 8, 0, tzinfo=UTC)},
        {"starts_at": STARTED},
        {"starts_at": STARTED, "stopped": True},
        {"starts_at": STARTED, "cancelled": True},
    ],
    ids=["upcoming", "in_progress", "finished", "cancelled"],
)
def test_the_download_of_any_other_status_is_not_found(
    scene: Scene, kwargs: dict[str, Any]
) -> None:
    """FR-033."""
    other = make_competition(scene.engine, scene.chemistry, "Other", **kwargs)
    not_found(download(scene.taras, other, scene.chemistry), COMPETITION_NOT_FOUND)


def test_unknown_and_other_subjects_downloads_are_not_found(scene: Scene, published: int) -> None:
    physics = make_subject(scene.engine, "Physics")
    not_found(download(scene.taras, MISSING, scene.chemistry), COMPETITION_NOT_FOUND)
    not_found(download(scene.taras, published, physics), COMPETITION_NOT_FOUND)
    for subject in ("abc", "", str(MISSING)):
        not_found(download(scene.taras, published, subject), SUBJECT_NOT_FOUND)


def test_a_published_competition_of_a_deactivated_subject_downloads(
    scene: Scene, published: int
) -> None:
    from app.services.subjects import set_subject_active

    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    assert download(scene.taras, published, scene.chemistry).content == EN_FILE


@pytest.mark.parametrize(
    ("email", "role", "label"),
    [
        (ADMIN_EMAIL, AUTO, "Administrator"),
        (STUDENT_EMAIL, AUTO, "Student"),
        (ADMIN_STUDENT_EMAIL, Role.STUDENT, "Student"),
    ],
)
def test_administrators_and_students_are_refused_before_any_id(
    scene: Scene, client_as: ClientAs, published: int, email: str, role: Any, label: str
) -> None:
    """FR-003: also with unknown ids."""
    browser = client_as(email, role)
    for competition, subject in ((published, scene.chemistry), (MISSING, "abc")):
        response = download(browser, competition, subject)
        assert response.status_code == 403
        assert f"Your current role, {label}, cannot open this page." in response.text


def test_anonymous_visitors_are_sent_to_sign_in(client: TestClient, scene: Scene) -> None:
    response = client.get(f"{TAB}/1/results?subject=1", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].split("?")[0] == "/login"


def test_the_download_changes_nothing(scene: Scene, published: int) -> None:
    before = snapshot(scene.engine)
    for _ in range(2):
        assert download(scene.taras, published, scene.chemistry).status_code == 200
    assert snapshot(scene.engine) == before


def test_a_real_publish_then_its_download(scene: Scene) -> None:
    """End to end: the download hands out exactly the bytes stored at publishing."""
    grade_everything(scene)
    assert publish(scene.olena, scene.competition, scene.chemistry).status_code == 303
    stored = files(scene.engine)
    response = download(scene.taras, scene.competition, scene.chemistry)
    assert response.content == stored[(scene.competition, "en")]
    assert "School No. 5, Comets, 17" in pdf_text(response.content)
    scene.taras.cookies.set("sc_lang", "uk")
    response = download(scene.taras, scene.competition, scene.chemistry)
    assert response.content == stored[(scene.competition, "uk")]


def test_the_results_route_is_in_the_route_table() -> None:
    assert any(path == RESULTS_ROUTE and "GET" in methods for path, methods, _ in ALL_ROUTES)
    assert re.fullmatch(r"/teacher/competitions/\{competition_id:int\}/results", RESULTS_ROUTE)
