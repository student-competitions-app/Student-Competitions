"""The grades of a finished competition's answers: the counts, the Grades page (which teams, their
grouping, paging, filter and progress), the grading sheet, and the save (what it stores, the order
of its checks, the last save wins), under concurrency too.

See specs/012.4-finish-and-grade/contracts/services.md §`grades` and research R2–R6. Every case
runs on both engines; the two-session races run on PostgreSQL only (on SQLite the locks render
nothing, and writers are serialised anyway). The clock is fixed at 1 March 2027 09:00 UTC by
patching `app.services.competitions.utc_now`, which the service reads; no test waits.

- Olena: a real teacher with **Can manage competitions**, linked (Read) only to Kharkiv Gymnasium,
  which has no team in the competition;
- Taras: a real teacher without it, with **Write** access to School No. 5;
- "Spring round": a Finished competition of Chemistry with 4 questions;
- "Comets" (School No. 5, Kyiv), "Lions" (Lyceum No. 2, Lviv), "Novas" (a deactivated institution
  in Kyiv), "Rockets" (deleted, School No. 5) and "Stars" (an institution of the deactivated region
  Odesa) are in it.

Answers and grades are seeded directly (`save_team_answer`, `grade_answer`), so the service is
never checked through itself.
"""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.models import AccessLevel, CompetitionTeam, Team, TeamAnswer
from app.services import grades
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    ManageRequired,
    lock_competition,
)
from app.services.grades import (
    GradeCount,
    GradedQuestionNotFound,
    GradedTeamNotFound,
    GradeFilter,
    GradeSaveResult,
    GradingClosed,
    InvalidGrades,
    count_of,
    parse_grade_filter,
)
from app.services.questions import delete_question, update_question
from app.services.subjects import set_subject_active
from app.services.teachers import get_teacher, update_teacher
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
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
from tests.integration.test_competition_entries_service import postgresql_only, race

NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 7, 0, tzinfo=UTC)
MISSING = 999_999
GRADE_ERROR = "Enter a whole number from 0 to 10."
LOCK_TIMEOUT = text("SET lock_timeout = '300ms'")
"""A lock that is not granted in 300 ms fails, instead of waiting: no test sleeps."""


@dataclass(frozen=True)
class Scene:
    engine: Engine
    olena: int
    taras: int
    chemistry: int
    competition: int
    """"Spring round", Finished, 4 questions."""
    copies: list[int]
    """Its copies, in the order of adding: questions 1–4."""
    question_ids: list[int]
    """The bank questions they were copied from."""
    school: int
    comets: int
    lions: int
    novas: int
    """Of a deactivated institution."""
    rockets: int
    """Deleted."""
    stars: int
    """Of an institution in a deactivated region."""


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    """A controllable `utc_now`, starting at 1 March 2027 09:00 UTC."""
    now = [NOW]
    monkeypatch.setattr("app.services.competitions.utc_now", lambda: now[0])

    def advance(by: timedelta = timedelta(0)) -> datetime:
        now[0] += by
        return now[0]

    return advance


@pytest.fixture
def scene(
    engine: Engine, auth_settings: AuthSettings, clock: Callable[[timedelta], datetime]
) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    school = make_institution(engine, "School No. 5", "Kyiv")
    lyceum = make_institution(engine, "Lyceum No. 2", "Lviv")
    closed = make_institution(engine, "Kyiv Lyceum", "Kyiv", active=False)
    odesa = make_institution(engine, "Odesa College", "Odesa", region_active=False)
    gymnasium = make_institution(engine, "Kharkiv Gymnasium", "Kharkiv")
    olena = make_teacher(
        engine,
        auth_settings,
        email="olena@example.org",
        institutions={gymnasium: AccessLevel.READ},
        can_manage=True,
    )
    taras = make_teacher(
        engine,
        auth_settings,
        email="taras@example.org",
        institutions={school: AccessLevel.WRITE},
        first="Taras",
        last="Shevchenko",
    )
    chemistry = make_subject(engine, "Chemistry")
    competition = make_competition(engine, chemistry, starts_at=STARTED, stopped=True)
    question_ids = [
        make_question(engine, chemistry, f"Question {n}?", f"Reference {n}.") for n in range(1, 5)
    ]
    copies = [add_competition_question(engine, competition, q) for q in question_ids]
    comets = make_team(engine, school, "Comets")
    lions = make_team(engine, lyceum, "Lions")
    novas = make_team(engine, closed, "Novas")
    rockets = make_team(engine, school, "Rockets")
    stars = make_team(engine, odesa, "Stars")
    for team in (comets, lions, novas, rockets, stars):
        add_competition_team(engine, competition, team)
    # Rockets is deleted after it joined: a finished competition keeps it (12.2 delete_team).
    with Session(engine) as session:
        row = session.get(Team, rockets)
        assert row is not None
        row.deleted_at = NOW
        session.add(row)
        session.commit()
    return Scene(
        engine=engine,
        olena=olena,
        taras=taras,
        chemistry=chemistry,
        competition=competition,
        copies=copies,
        question_ids=question_ids,
        school=school,
        comets=comets,
        lions=lions,
        novas=novas,
        rockets=rockets,
        stars=stars,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def answer(s: Scene, team: int, copy: int, text: str = "Answer", grade: int | None = None) -> None:
    save_team_answer(s.engine, s.competition, team, copy, text)
    if grade is not None:
        grade_answer(s.engine, s.competition, team, copy, grade)


def stored(engine: Engine, competition_id: int, team_id: int) -> dict[int, tuple[str, int | None]]:
    """The team's stored answers and grades in the competition, by copy id."""
    with Session(engine) as session:
        rows = session.exec(
            select(TeamAnswer).where(
                TeamAnswer.competition_id == competition_id, TeamAnswer.team_id == team_id
            )
        )
        return {row.competition_question_id: (row.text, row.grade) for row in rows}


def snapshot(engine: Engine) -> list[tuple[Any, ...]]:
    with Session(engine) as session:
        return sorted(
            (a.competition_id, a.team_id, a.competition_question_id, a.text, a.grade)
            for a in session.exec(select(TeamAnswer))
        )


def save(
    s: Scene,
    raw: Mapping[int, str],
    *,
    teacher: int | None = None,
    team: int | None = None,
    competition: int | None = None,
    subject: int | None = None,
) -> GradeSaveResult:
    """`save_grades` in a fresh session, as Olena for Comets in Spring round unless told; the
    session must stay usable after a refusal, so a read follows in the same session."""
    with Session(s.engine) as session:
        try:
            return grades.save_grades(
                session,
                s.olena if teacher is None else teacher,
                s.competition if competition is None else competition,
                s.chemistry if subject is None else subject,
                s.comets if team is None else team,
                raw,
            )
        finally:
            session.exec(select(TeamAnswer.team_id)).all()


def counts(s: Scene, competition: int | None = None) -> dict[int, GradeCount]:
    with Session(s.engine) as session:
        return grades.grade_counts(session, s.competition if competition is None else competition)


def page(s: Scene, show: GradeFilter = GradeFilter.ALL, p: int = 1) -> grades.GradeTeamPage:
    with Session(s.engine) as session:
        return grades.grade_team_page(session, s.competition, show, p)


def sheet(s: Scene, team: int | None = None) -> grades.GradingSheet:
    with Session(s.engine) as session:
        return grades.grading_sheet(session, s.competition, s.comets if team is None else team)


def names(listing: grades.GradeTeamPage) -> list[str]:
    return [row.name for group in listing.groups for row in group.rows]


# ---------------------------------------------------------------------------------------------
# The counts and the filter (research R5)
# ---------------------------------------------------------------------------------------------


def test_grade_counts(scene: Scene) -> None:
    for copy, grade in zip(scene.copies, (5, 7, 5, None), strict=True):
        answer(scene, scene.comets, copy, grade=grade)
    for copy in scene.copies[:2]:
        answer(scene, scene.lions, copy, grade=0)
    other = make_competition(
        scene.engine, scene.chemistry, "Other", starts_at=STARTED, stopped=True
    )
    other_copy = add_competition_question(scene.engine, other, scene.question_ids[0])
    add_competition_team(scene.engine, other, scene.comets)
    save_team_answer(scene.engine, other, scene.comets, other_copy, "Elsewhere")
    grade_answer(scene.engine, other, scene.comets, other_copy, 10)
    found = counts(scene)
    assert found == {scene.comets: GradeCount(4, 3, 17), scene.lions: GradeCount(2, 2, 0)}
    assert not found[scene.comets].fully_graded
    assert found[scene.lions].fully_graded
    assert scene.novas not in found
    assert count_of(found, scene.novas) == GradeCount(0, 0, 0)
    assert count_of(found, scene.novas).fully_graded


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ungraded", GradeFilter.UNGRADED),
        (None, GradeFilter.ALL),
        ("", GradeFilter.ALL),
        ("all", GradeFilter.ALL),
        ("Ungraded", GradeFilter.ALL),
        ("x", GradeFilter.ALL),
    ],
)
def test_parse_grade_filter(raw: str | None, expected: GradeFilter) -> None:
    assert parse_grade_filter(raw) is expected


# ---------------------------------------------------------------------------------------------
# User story 3: the Grades page
# ---------------------------------------------------------------------------------------------


def test_every_team_is_listed_in_region_groups(scene: Scene) -> None:
    """US3-1, FR-016: deleted teams and teams of a deactivated institution or region included,
    in the order and region groups of the Teams page."""
    listing = page(scene)
    groups = [(g.region_name, g.total, [r.name for r in g.rows]) for g in listing.groups]
    assert groups == [
        ("Kyiv", 3, ["Comets", "Novas", "Rockets"]),
        ("Lviv", 1, ["Lions"]),
        ("Odesa", 1, ["Stars"]),
    ]
    deleted = {row.name: row.is_deleted for g in listing.groups for row in g.rows}
    assert deleted == {
        "Comets": False,
        "Novas": False,
        "Rockets": True,
        "Lions": False,
        "Stars": False,
    }


def test_the_row_values_and_the_overall_progress(scene: Scene) -> None:
    """US3-2–US3-4, FR-015, FR-018: answered of the questions, graded of the answered, the score;
    a team with no answers is fully graded."""
    for copy, grade in zip(scene.copies, (5, 7, 5, None), strict=True):
        answer(scene, scene.comets, copy, grade=grade)
    answer(scene, scene.lions, scene.copies[0], grade=0)
    answer(scene, scene.stars, scene.copies[1])
    listing = page(scene)
    rows = {row.name: row for g in listing.groups for row in g.rows}
    comets = rows["Comets"]
    assert (comets.answered, comets.questions, comets.graded, comets.score) == (4, 4, 3, 17)
    assert (rows["Lions"].answered, rows["Lions"].graded, rows["Lions"].score) == (1, 1, 0)
    assert (rows["Novas"].answered, rows["Novas"].graded, rows["Novas"].score) == (0, 0, 0)
    assert (rows["Stars"].answered, rows["Stars"].graded, rows["Stars"].score) == (1, 0, 0)
    assert (listing.teams_total, listing.teams_graded) == (5, 3)


def test_ungraded_only_lists_the_teams_still_to_grade(scene: Scene) -> None:
    """US6-1, FR-019: a team with an ungraded answer; not a team with no answers, nor a fully
    graded one. The paging and the region totals count only those; the progress counts all."""
    answer(scene, scene.comets, scene.copies[0], grade=6)
    answer(scene, scene.comets, scene.copies[1])
    answer(scene, scene.lions, scene.copies[0], grade=3)
    answer(scene, scene.stars, scene.copies[0])
    listing = page(scene, GradeFilter.UNGRADED)
    groups = [(g.region_name, g.total, [r.name for r in g.rows]) for g in listing.groups]
    assert groups == [("Kyiv", 1, ["Comets"]), ("Odesa", 1, ["Stars"])]
    assert listing.paging.total == 2
    assert (listing.teams_total, listing.teams_graded) == (5, 3)
    with Session(scene.engine) as session:
        for team, listed in (
            (scene.comets, True),
            (scene.lions, False),
            (scene.novas, False),
            (MISSING, False),
        ):
            assert grades.is_listed(session, scene.competition, team, GradeFilter.UNGRADED) is (
                listed
            )
        assert grades.is_listed(session, scene.competition, scene.lions, GradeFilter.ALL)
        assert not grades.is_listed(session, scene.competition, MISSING, GradeFilter.ALL)


def test_no_teams(scene: Scene) -> None:
    empty = make_competition(
        scene.engine, scene.chemistry, "Empty", starts_at=STARTED, stopped=True
    )
    for show in GradeFilter:
        with Session(scene.engine) as session:
            listing = grades.grade_team_page(session, empty, show, 1)
        assert (listing.groups, listing.teams_total, listing.teams_graded) == ([], 0, 0)


def test_twenty_five_teams_page_as_ten_ten_five(scene: Scene) -> None:
    """US3-5, FR-017: region totals across pages; `team_page_of` under each filter."""
    competition = make_competition(
        scene.engine, scene.chemistry, "Big", starts_at=STARTED, stopped=True
    )
    copy = add_competition_question(scene.engine, competition, scene.question_ids[0])
    regions = [
        make_institution(scene.engine, f"School in {region}", region)
        for region in ("Kharkiv", "Kyiv", "Lviv")
    ]
    teams = []
    for n in range(25):
        team = make_team(scene.engine, regions[n // 9], f"Team {n:02}")
        add_competition_team(scene.engine, competition, team)
        teams.append(team)
    for team in teams[::2]:
        save_team_answer(scene.engine, competition, team, copy, "Answer")
    with Session(scene.engine) as session:
        pages = [
            grades.grade_team_page(session, competition, GradeFilter.ALL, p) for p in (1, 2, 3)
        ]
        assert [sum(len(g.rows) for g in listing.groups) for listing in pages] == [10, 10, 5]
        assert [(g.region_name, g.total) for g in pages[1].groups] == [("Kyiv", 9), ("Lviv", 7)]
        assert [
            grades.team_page_of(session, competition, t, GradeFilter.ALL)
            for t in (
                teams[0],
                teams[10],
                teams[24],
            )
        ] == [1, 2, 3]
        ungraded = grades.grade_team_page(session, competition, GradeFilter.UNGRADED, 1)
        assert ungraded.paging.total == 13
        assert grades.team_page_of(session, competition, teams[24], GradeFilter.UNGRADED) == 2
        assert grades.team_page_of(session, competition, teams[1], GradeFilter.UNGRADED) == 1
        assert grades.team_page_of(session, competition, MISSING, GradeFilter.ALL) == 1


# ---------------------------------------------------------------------------------------------
# User story 4: the grading sheet and the save
# ---------------------------------------------------------------------------------------------


def test_the_grading_sheet(scene: Scene) -> None:
    """US4-1, FR-021, FR-022: every copy in order with its text and reference answer, also after
    the bank question changes; the answer or `None`; the grade; the count."""
    answer(scene, scene.comets, scene.copies[0], "Sodium chloride\nNaCl", grade=7)
    answer(scene, scene.comets, scene.copies[2], "Gas")
    with Session(scene.engine) as session:
        update_question(session, scene.olena, scene.question_ids[0], "Changed?", "Changed.")
        delete_question(session, scene.olena, scene.question_ids[1])
    found = sheet(scene)
    assert (found.team_id, found.team_name, found.institution_name, found.is_deleted) == (
        scene.comets,
        "Comets",
        "School No. 5",
        False,
    )
    assert [
        (q.competition_question_id, q.number, q.text, q.reference_answer, q.answer, q.grade)
        for q in found.questions
    ] == [
        (scene.copies[0], 1, "Question 1?", "Reference 1.", "Sodium chloride\nNaCl", 7),
        (scene.copies[1], 2, "Question 2?", "Reference 2.", None, None),
        (scene.copies[2], 3, "Question 3?", "Reference 3.", "Gas", None),
        (scene.copies[3], 4, "Question 4?", "Reference 4.", None, None),
    ]
    assert found.count == GradeCount(2, 1, 7)


def test_every_team_of_the_competition_has_a_sheet(scene: Scene) -> None:
    """FR-043 step 5: deleted teams and teams of a deactivated institution or region are found;
    an unknown team and one not in the competition are not."""
    assert sheet(scene, scene.rockets).is_deleted
    assert sheet(scene, scene.novas).team_name == "Novas"
    assert sheet(scene, scene.stars).institution_name == "Odesa College"
    outsider = make_team(scene.engine, scene.school, "Outsiders")
    for team in (MISSING, outsider):
        with pytest.raises(GradedTeamNotFound):
            sheet(scene, team)


def test_one_save_stores_changes_and_empties_grades(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """US4-3–US4-6, FR-024, FR-026–FR-028: stored, changed and emptied in one save; an answered
    question the save does not name keeps its grade; the text is never written."""
    q1, q2, q3, q4 = scene.copies
    answer(scene, scene.comets, q1, "One")
    answer(scene, scene.comets, q2, "Two", grade=4)
    answer(scene, scene.comets, q3, "Three", grade=9)
    answer(scene, scene.comets, q4, "Four", grade=2)
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    result = save(scene, {q1: "5", q2: "", q3: " 10 "})
    assert result == GradeSaveResult(graded=3, changed=3)
    assert stored(scene.engine, scene.competition, scene.comets) == {
        q1: ("One", 5),
        q2: ("Two", None),
        q3: ("Three", 10),
        q4: ("Four", 2),
    }
    assert save(scene, {q1: "5", q2: "", q3: "10"}) == GradeSaveResult(graded=3, changed=0)
    assert save(scene, {q1: "05", q4: "0"}) == GradeSaveResult(graded=3, changed=1)
    messages = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Grades")]
    assert messages == [
        f"Grades saved: competition={scene.competition} team={scene.comets} graded=3 changed=3",
        f"Grades saved: competition={scene.competition} team={scene.comets} graded=3 changed=0",
        f"Grades saved: competition={scene.competition} team={scene.comets} graded=3 changed=1",
    ]


def test_deleted_and_deactivated_teams_are_graded(scene: Scene) -> None:
    """US11-8, FR-043 step 5."""
    for team in (scene.rockets, scene.novas, scene.stars):
        answer(scene, team, scene.copies[0])
        assert save(scene, {scene.copies[0]: "8"}, team=team) == GradeSaveResult(1, 1)
        assert stored(scene.engine, scene.competition, team) == {scene.copies[0]: ("Answer", 8)}


def test_a_finished_competition_of_a_deactivated_subject_is_graded(scene: Scene) -> None:
    """US13-2, FR-042."""
    answer(scene, scene.comets, scene.copies[0])
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    assert save(scene, {scene.copies[0]: "6"}) == GradeSaveResult(1, 1)


# ---------------------------------------------------------------------------------------------
# User story 5: invalid grades save nothing
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["7.5", "-1", "11", "seven"])
def test_an_invalid_grade_saves_nothing(
    scene: Scene, bad: str, caplog: pytest.LogCaptureFixture
) -> None:
    """US5-1, FR-025."""
    q1, q2, q3, _ = scene.copies
    for copy in (q1, q2, q3):
        answer(scene, scene.comets, copy, grade=1)
    before = snapshot(scene.engine)
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    with pytest.raises(InvalidGrades) as refused:
        save(scene, {q1: "6", q2: bad, q3: ""})
    assert refused.value.errors == {q2: GRADE_ERROR}
    assert snapshot(scene.engine) == before
    assert not [r for r in caplog.records if r.getMessage().startswith("Grades")]


def test_two_invalid_grades_in_question_order(scene: Scene) -> None:
    q1, q2, q3, _ = scene.copies
    for copy in (q1, q2, q3):
        answer(scene, scene.comets, copy)
    with pytest.raises(InvalidGrades) as refused:
        save(scene, {q3: "x", q2: "6", q1: "99"})
    assert list(refused.value.errors.items()) == [(q1, GRADE_ERROR), (q3, GRADE_ERROR)]


# ---------------------------------------------------------------------------------------------
# User stories 10 and 11: the order of the checks
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"starts_at": datetime(2027, 3, 14, 8, 0, tzinfo=UTC)}, CompetitionStatus.UPCOMING),
        ({"starts_at": STARTED}, CompetitionStatus.IN_PROGRESS),
        ({"starts_at": STARTED, "cancelled": True}, CompetitionStatus.CANCELLED),
    ],
)
def test_grading_needs_a_finished_competition(
    scene: Scene,
    kwargs: dict[str, Any],
    status: CompetitionStatus,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """US10-1–US10-3, FR-039: refused with the status, before the team is looked at."""
    competition = make_competition(scene.engine, scene.chemistry, "Open", **kwargs)
    copy = add_competition_question(scene.engine, competition, scene.question_ids[0])
    add_competition_team(scene.engine, competition, scene.comets)
    save_team_answer(scene.engine, competition, scene.comets, copy, "Answer")
    before = snapshot(scene.engine)
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    for team in (scene.comets, MISSING):
        with pytest.raises(GradingClosed) as refused:
            save(scene, {copy: "5"}, competition=competition, team=team)
        assert refused.value.status is status
    assert snapshot(scene.engine) == before
    assert not [r for r in caplog.records if r.getMessage().startswith("Grades")]


def test_the_setting_comes_first(scene: Scene) -> None:
    """US11-2, FR-002, FR-043: a teacher without the setting is refused whatever the ids."""
    answer(scene, scene.comets, scene.copies[0])
    before = snapshot(scene.engine)
    for competition, team in ((scene.competition, scene.comets), (MISSING, MISSING)):
        with pytest.raises(ManageRequired):
            save(
                scene,
                {scene.copies[0]: "5"},
                teacher=scene.taras,
                competition=competition,
                team=team,
            )
    assert snapshot(scene.engine) == before


def test_the_setting_taken_away_refuses_the_next_save(scene: Scene) -> None:
    """US11-3: the grades saved before are kept."""
    answer(scene, scene.comets, scene.copies[0])
    save(scene, {scene.copies[0]: "5"})
    with Session(scene.engine) as session:
        view = get_teacher(session, scene.olena)
        update_teacher(
            session,
            scene.olena,
            view.first_name,
            view.last_name,
            {link.institution_id: link.access_level for link in view.links},
            can_manage_competitions=False,
        )
    with pytest.raises(ManageRequired):
        save(scene, {scene.copies[0]: "9"})
    assert stored(scene.engine, scene.competition, scene.comets) == {scene.copies[0]: ("Answer", 5)}


def test_not_found_refusals(scene: Scene) -> None:
    """US11-4–US11-6: an unknown competition, one of another subject or hidden; an unknown team or
    one not in the competition; a copy of another competition or a question the team did not
    answer. Nothing is stored."""
    answer(scene, scene.comets, scene.copies[0])
    physics = make_subject(scene.engine, "Physics")
    other = make_competition(
        scene.engine, scene.chemistry, "Other", starts_at=STARTED, stopped=True
    )
    other_copy = add_competition_question(scene.engine, other, scene.question_ids[0])
    outsider = make_team(scene.engine, scene.school, "Outsiders")
    before = snapshot(scene.engine)
    for kwargs in ({"competition": MISSING}, {"subject": physics}):
        with pytest.raises(CompetitionNotFound):
            save(scene, {scene.copies[0]: "5"}, **kwargs)
    for team in (MISSING, outsider):
        with pytest.raises(GradedTeamNotFound):
            save(scene, {scene.copies[0]: "5"}, team=team)
    for copy in (other_copy, scene.copies[1], MISSING):
        with pytest.raises(GradedQuestionNotFound):
            save(scene, {scene.copies[0]: "5", copy: "5"})
    assert snapshot(scene.engine) == before


def test_the_session_is_usable_after_every_refusal(scene: Scene) -> None:
    answer(scene, scene.comets, scene.copies[0])
    with Session(scene.engine) as session:
        for teacher, team, raw, error in (
            (scene.taras, scene.comets, {}, ManageRequired),
            (scene.olena, MISSING, {}, GradedTeamNotFound),
            (scene.olena, scene.comets, {MISSING: "5"}, GradedQuestionNotFound),
            (scene.olena, scene.comets, {scene.copies[0]: "x"}, InvalidGrades),
        ):
            with pytest.raises(error):
                grades.save_grades(session, teacher, scene.competition, scene.chemistry, team, raw)
            assert session.exec(select(TeamAnswer)).all()


# ---------------------------------------------------------------------------------------------
# User story 12: the last save wins
# ---------------------------------------------------------------------------------------------


def test_the_later_save_replaces_every_grade_it_names(scene: Scene) -> None:
    """US12-1, FR-030: the second sheet, opened before the first save, wins exactly."""
    q1, q2, q3, _ = scene.copies
    for copy in (q1, q2, q3):
        answer(scene, scene.comets, copy)
    grade_answer(scene.engine, scene.competition, scene.comets, q1, 3)
    save(scene, {q1: "3", q2: "8", q3: ""})
    save(scene, {q1: "", q2: "", q3: "6"})
    assert stored(scene.engine, scene.competition, scene.comets) == {
        q1: ("Answer", None),
        q2: ("Answer", None),
        q3: ("Answer", 6),
    }


def test_two_saves_at_the_same_moment_never_mix(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    """US12-2, FR-030: two full sheets of the same team saved at once."""
    postgresql_only(database_url)
    for copy in scene.copies:
        answer(scene, scene.comets, copy)
    first = {copy: str(n) for n, copy in enumerate(scene.copies)}
    second = {copy: ("" if n % 2 else "9") for n, copy in enumerate(scene.copies)}
    expected = [
        {copy: ("Answer", int(v) if v else None) for copy, v in sheet_.items()}
        for sheet_ in (first, second)
    ]
    for _ in range(4):
        outcomes = race(
            engine,
            lambda session: grades.save_grades(
                session, scene.olena, scene.competition, scene.chemistry, scene.comets, first
            ),
            lambda session: grades.save_grades(
                session, scene.olena, scene.competition, scene.chemistry, scene.comets, second
            ),
        )
        assert outcomes == ["ok", "ok"]
        assert stored(engine, scene.competition, scene.comets) in expected


def test_saves_of_different_teams_do_not_wait(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    """Research R3: the competition is held `FOR SHARE`, a team's link `FOR UPDATE`."""
    postgresql_only(database_url)
    answer(scene, scene.comets, scene.copies[0])
    answer(scene, scene.lions, scene.copies[0])
    with Session(engine) as first:
        # Comets' link held as a save holds it: a save of Lions goes through, one of Comets
        # waits (and times out here).
        lock_competition(first, scene.competition, scene.chemistry, share=True)
        first.get(CompetitionTeam, (scene.competition, scene.comets), with_for_update=True)
        with Session(engine) as second:
            second.execute(LOCK_TIMEOUT)
            grades.save_grades(
                second,
                scene.olena,
                scene.competition,
                scene.chemistry,
                scene.lions,
                {scene.copies[0]: "4"},
            )
        with Session(engine) as third:
            third.execute(LOCK_TIMEOUT)
            with pytest.raises(OperationalError, match="lock timeout"):
                grades.save_grades(
                    third,
                    scene.olena,
                    scene.competition,
                    scene.chemistry,
                    scene.comets,
                    {scene.copies[0]: "4"},
                )
        first.rollback()
    assert stored(engine, scene.competition, scene.lions) == {scene.copies[0]: ("Answer", 4)}


# ---------------------------------------------------------------------------------------------
# Logging (FR-045)
# ---------------------------------------------------------------------------------------------


def test_logs_carry_ids_and_counts_only(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    answer(scene, scene.comets, scene.copies[0], "Secret answer")
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    save(scene, {scene.copies[0]: "7"})
    for raw, error in (
        ({scene.copies[0]: "x"}, InvalidGrades),
        ({MISSING: "1"}, GradedQuestionNotFound),
    ):
        with pytest.raises(error):
            save(scene, raw)
    assert [r.getMessage() for r in caplog.records if r.getMessage().startswith("Grades")] == [
        f"Grades saved: competition={scene.competition} team={scene.comets} graded=1 changed=1"
    ]
    for record in caplog.records:
        message = record.getMessage()
        for secret in (
            "Spring round",
            "Comets",
            "School No. 5",
            "Question 1?",
            "Reference 1.",
            "Secret answer",
            "olena@example.org",
            "Olena",
        ):
            assert secret not in message, (secret, message)
