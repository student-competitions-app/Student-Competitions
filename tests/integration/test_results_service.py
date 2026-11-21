"""Publishing a competition's results: the snapshot, the publish (what it stores, the order of its
checks, its landing), the files it stores and their permanence, under concurrency too (milestone
12.8).

See specs/012.8-publishing-results/contracts/services.md §1, data-model.md §4–§5 and research R5,
R7. Every case runs on both engines; the two-session races run on PostgreSQL only (on SQLite the
locks render nothing, and writers are serialised anyway). The clock is fixed at 1 March 2027 09:00
UTC by patching `app.services.competitions.utc_now`, which the service reads; no test waits.

- Olena: a real teacher with **Can manage competitions**, linked to none of the teams;
- Taras: a real teacher without it;
- "Spring round": a Finished competition of Chemistry with 2 questions;
- "Comets" and "Rockets" (deleted) of School No. 5 in Kyiv, "Lions" of Lyceum No. 2 in Lviv,
  "Novas" of a deactivated institution in Kyiv, and "Stars" of an institution of the deactivated
  region Odesa are in it.

Answers and grades are seeded directly (`save_team_answer`, `grade_answer`).
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

import app.services.results_pdf as results_pdf
from app.core.config import AuthSettings
from app.models import (
    AccessLevel,
    Competition,
    CompetitionQuestion,
    CompetitionResultsFile,
    CompetitionTeam,
    Institution,
    Region,
    Team,
    TeamAnswer,
)
from app.schemas.names import name_key
from app.services import grades, results
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    Landing,
    ManageRequired,
    NotCancellable,
    cancel_competition,
    lock_competition,
    status_of,
)
from app.services.grades import GradingClosed, GradingProgress
from app.services.results import (
    NotFullyGraded,
    NotPublishable,
    RegionResults,
    ResultLine,
    build_snapshot,
    publish_results,
)
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
    store_results_files,
)
from tests.integration.test_competition_entries_service import postgresql_only, race
from tests.pdf import pdf_text

NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 7, 0, tzinfo=UTC)
MISSING = 999_999


@dataclass(frozen=True)
class Scene:
    engine: Engine
    olena: int
    taras: int
    chemistry: int
    competition: int
    """"Spring round", Finished, 2 questions."""
    copies: list[int]
    school: int
    comets: int
    rockets: int
    """Deleted."""
    lions: int
    novas: int
    """Of a deactivated institution."""
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
    questions = [make_question(engine, chemistry, f"Question {n}?", f"Ref {n}.") for n in (1, 2)]
    copies = [add_competition_question(engine, competition, q) for q in questions]
    comets = make_team(engine, school, "Comets")
    rockets = make_team(engine, school, "Rockets")
    lions = make_team(engine, lyceum, "Lions")
    novas = make_team(engine, closed, "Novas")
    stars = make_team(engine, odesa, "Stars")
    for team in (comets, rockets, lions, novas, stars):
        add_competition_team(engine, competition, team)
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
        school=school,
        comets=comets,
        rockets=rockets,
        lions=lions,
        novas=novas,
        stars=stars,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def answer(s: Scene, team: int, copy: int, grade: int | None) -> None:
    save_team_answer(s.engine, s.competition, team, copy, "An answer")
    if grade is not None:
        grade_answer(s.engine, s.competition, team, copy, grade)


def grade_everything(s: Scene) -> None:
    """Comets 7 + 10 = 17, Rockets 4, Lions 0, Stars 9; Novas gave no answer."""
    answer(s, s.comets, s.copies[0], 7)
    answer(s, s.comets, s.copies[1], 10)
    answer(s, s.rockets, s.copies[0], 4)
    answer(s, s.lions, s.copies[1], 0)
    answer(s, s.stars, s.copies[0], 9)


def publish(
    s: Scene,
    *,
    teacher: int | None = None,
    competition: int | None = None,
    status: CompetitionStatus | None = None,
) -> Landing:
    """`publish_results` in a fresh session, as Olena for Spring round unless told; the session
    must stay usable after a refusal, so a read follows in the same session."""
    with Session(s.engine) as session:
        try:
            return publish_results(
                session,
                s.olena if teacher is None else teacher,
                s.competition if competition is None else competition,
                s.chemistry,
                status,
            )
        finally:
            session.exec(select(Competition.id)).all()


def competition_row(engine: Engine, competition_id: int) -> tuple[Any, ...]:
    with Session(engine) as session:
        c = session.get(Competition, competition_id)
        assert c is not None
        return (c.name, c.starts_at, c.cancelled_at, c.stopped_at, c.published_at, c.updated_at)


def files(engine: Engine, competition_id: int | None = None) -> dict[tuple[int, str], bytes]:
    with Session(engine) as session:
        statement = select(CompetitionResultsFile)
        if competition_id is not None:
            statement = statement.where(CompetitionResultsFile.competition_id == competition_id)
        return {(f.competition_id, f.language): f.content for f in session.exec(statement)}


def grades_snapshot(engine: Engine) -> list[tuple[Any, ...]]:
    with Session(engine) as session:
        return sorted(
            (a.competition_id, a.team_id, a.competition_question_id, a.grade)
            for a in session.exec(select(TeamAnswer))
        )


def snapshot_of(s: Scene, competition: int | None = None) -> results.ResultsSnapshot:
    with Session(s.engine) as session:
        row = session.get(Competition, s.competition if competition is None else competition)
        assert row is not None
        subject = row.subject_id
        from app.models import Subject

        found = session.get(Subject, subject)
        assert found is not None
        return build_snapshot(session, row, found, NOW)


def lines(snapshot: results.ResultsSnapshot) -> list[tuple[str, str, str, int]]:
    return [
        (region.name, line.institution, line.team, line.score)
        for region in snapshot.regions
        for line in region.lines
    ]


# ---------------------------------------------------------------------------------------------
# User story 1: publishing (FR-007–FR-010)
# ---------------------------------------------------------------------------------------------


def test_publishing_stores_the_moment_and_two_files(scene: Scene) -> None:
    """US1-5, FR-009: only `published_at` changes, in the same step as the two files."""
    grade_everything(scene)
    before = competition_row(scene.engine, scene.competition)
    landing = publish(scene)
    assert landing == Landing(page=1, competition_id=scene.competition)
    after = competition_row(scene.engine, scene.competition)
    assert after[4] == NOW
    assert after[:4] + after[5:] == before[:4] + before[5:]
    with Session(scene.engine) as session:
        row = session.get(Competition, scene.competition)
        assert row is not None
        assert status_of(row, NOW) is CompetitionStatus.PUBLISHED
    stored = files(scene.engine)
    assert sorted(stored) == [(scene.competition, "en"), (scene.competition, "uk")]
    for content in stored.values():
        assert content.startswith(b"%PDF-")
        assert "Spring round" in pdf_text(content)


def test_the_files_hold_the_scores_in_each_language(scene: Scene) -> None:
    grade_everything(scene)
    publish(scene)
    stored = files(scene.engine, scene.competition)
    english = pdf_text(stored[(scene.competition, "en")])
    ukrainian = pdf_text(stored[(scene.competition, "uk")])
    for line in (
        "School No. 5 Comets 17",
        "School No. 5 Rockets 4",
        "Lyceum No. 2 Lions 0",
        "Kyiv Lyceum Novas 0",
        "Odesa College Stars 9",
    ):
        assert line in english
        assert line in ukrainian
    assert "Results of “Spring round”" in english
    assert "Maximum score: 20" in english and "Максимальний бал: 20" in ukrainian
    assert "Результати «Spring round»" in ukrainian


@pytest.mark.parametrize("status", [None, CompetitionStatus.PUBLISHED])
def test_the_landing_is_the_competition_when_the_filter_shows_it(
    scene: Scene, status: CompetitionStatus | None
) -> None:
    for n in range(12):
        make_competition(
            scene.engine,
            scene.chemistry,
            f"Earlier {n:02d}",
            starts_at=STARTED - timedelta(days=n + 1),
            stopped=True,
        )
    landing = publish(scene, status=status)
    assert landing == Landing(page=1, competition_id=scene.competition)


def test_the_landings_under_finished(scene: Scene) -> None:
    """US1-4: the row that took its place, the row before when it was last, the previous page's
    last row when its page empties, the empty state when none is left."""
    finished = [scene.competition] + [
        make_competition(
            scene.engine,
            scene.chemistry,
            f"Earlier {n:02d}",
            starts_at=STARTED - timedelta(days=n + 1),
            stopped=True,
        )
        for n in range(10)
    ]
    # Eleven finished, latest start first: Spring round, then Earlier 00 … Earlier 09.
    assert publish(scene, status=CompetitionStatus.FINISHED) == Landing(1, finished[1])
    assert publish(scene, competition=finished[10], status=CompetitionStatus.FINISHED) == Landing(
        1, finished[9]
    )
    alone = make_subject(scene.engine, "Biology")
    only = make_competition(scene.engine, alone, "Only", starts_at=STARTED, stopped=True)
    with Session(scene.engine) as session:
        landing = publish_results(session, scene.olena, only, alone, CompetitionStatus.FINISHED)
    assert landing == Landing(1, None)


def test_the_landing_on_the_previous_page(scene: Scene) -> None:
    """Eleven finished competitions: publishing the eleventh (page 2) lands on page 1's last."""
    finished = [scene.competition] + [
        make_competition(
            scene.engine,
            scene.chemistry,
            f"Earlier {n:02d}",
            starts_at=STARTED - timedelta(days=n + 1),
            stopped=True,
        )
        for n in range(10)
    ]
    landing = publish(scene, competition=finished[10], status=CompetitionStatus.FINISHED)
    assert landing == Landing(page=1, competition_id=finished[9])


def test_publishing_needs_the_setting(scene: Scene) -> None:
    grade_everything(scene)
    before = competition_row(scene.engine, scene.competition)
    for competition in (scene.competition, MISSING):
        with pytest.raises(ManageRequired):
            publish(scene, teacher=scene.taras, competition=competition)
    assert competition_row(scene.engine, scene.competition) == before
    assert files(scene.engine) == {}


def test_unknown_and_other_subjects_competitions_are_not_found(scene: Scene) -> None:
    physics = make_subject(scene.engine, "Physics")
    other = make_competition(scene.engine, physics, "Other", starts_at=STARTED, stopped=True)
    for competition in (MISSING, other):
        with pytest.raises(CompetitionNotFound):
            publish(scene, competition=competition)
    assert files(scene.engine) == {}


def test_publishing_logs_ids_counts_and_sizes_only(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    grade_everything(scene)
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    publish(scene)
    total = sum(len(content) for content in files(scene.engine).values())
    messages = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Results")]
    assert messages == [f"Results published: id={scene.competition} teams=5 bytes={total}"]
    for name in ("Spring round", "Comets", "School No. 5", "Kyiv", "Chemistry"):
        assert name not in messages[0]


def test_a_file_that_cannot_be_made_stores_nothing(
    scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-009: the competition stays Finished, with no file."""
    grade_everything(scene)

    def broken(*_: object) -> bytes:
        raise RuntimeError("the renderer failed")

    monkeypatch.setattr(results_pdf, "render_results_pdf", broken)
    with pytest.raises(RuntimeError):
        publish(scene)
    assert competition_row(scene.engine, scene.competition)[4] is None
    assert files(scene.engine) == {}


# ---------------------------------------------------------------------------------------------
# User story 2: only when fully graded (FR-011–FR-014)
# ---------------------------------------------------------------------------------------------


def test_an_ungraded_answer_blocks_publishing(scene: Scene) -> None:
    grade_everything(scene)
    answer(scene, scene.lions, scene.copies[0], None)
    with pytest.raises(NotFullyGraded) as refused:
        publish(scene)
    assert refused.value.progress == GradingProgress(graded=4, total=5)
    assert competition_row(scene.engine, scene.competition)[4] is None
    assert files(scene.engine) == {}


def test_a_deleted_team_with_an_ungraded_answer_blocks_publishing(scene: Scene) -> None:
    answer(scene, scene.rockets, scene.copies[0], None)
    with pytest.raises(NotFullyGraded):
        publish(scene)


def test_a_team_with_no_answers_counts_as_graded(scene: Scene) -> None:
    """Nobody answered: every team is fully graded, every score 0."""
    publish(scene)
    english = pdf_text(files(scene.engine)[(scene.competition, "en")])
    assert "School No. 5 Comets 0" in english


@pytest.mark.parametrize(("language", "text"), [
    ("en", "No teams took part in this competition."),
    ("uk", "У цьому змаганні не брала участі жодна команда."),
])  # fmt: skip
def test_a_competition_with_no_teams_is_published(scene: Scene, language: str, text: str) -> None:
    empty = make_competition(
        scene.engine, scene.chemistry, "Empty", starts_at=STARTED, stopped=True
    )
    publish(scene, competition=empty)
    assert competition_row(scene.engine, empty)[4] == NOW
    assert text in pdf_text(files(scene.engine)[(empty, language)])


def test_a_competition_with_no_questions_is_published_with_every_score_0(scene: Scene) -> None:
    bare = make_competition(scene.engine, scene.chemistry, "Bare", starts_at=STARTED, stopped=True)
    add_competition_team(scene.engine, bare, scene.comets)
    publish(scene, competition=bare)
    assert "School No. 5 Comets 0" in pdf_text(files(scene.engine)[(bare, "en")])


# ---------------------------------------------------------------------------------------------
# User story 3: refusals and races (FR-015–FR-017)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"starts_at": datetime(2027, 3, 14, 8, 0, tzinfo=UTC)}, CompetitionStatus.UPCOMING),
        ({"starts_at": STARTED}, CompetitionStatus.IN_PROGRESS),
        ({"starts_at": STARTED, "cancelled": True}, CompetitionStatus.CANCELLED),
        ({"starts_at": STARTED, "stopped": True, "published": True}, CompetitionStatus.PUBLISHED),
    ],
)
def test_publishing_needs_a_finished_competition(
    scene: Scene, kwargs: dict[str, Any], status: CompetitionStatus
) -> None:
    competition = make_competition(scene.engine, scene.chemistry, "Other", **kwargs)
    before = competition_row(scene.engine, competition)
    with pytest.raises(NotPublishable) as refused:
        publish(scene, competition=competition)
    assert refused.value.status is status
    assert competition_row(scene.engine, competition) == before
    assert files(scene.engine) == {}


def test_the_same_publish_twice_publishes_once(scene: Scene) -> None:
    grade_everything(scene)
    publish(scene)
    stored = files(scene.engine)
    with pytest.raises(NotPublishable) as refused:
        publish(scene)
    assert refused.value.status is CompetitionStatus.PUBLISHED
    assert files(scene.engine) == stored


def test_a_lost_race_cannot_store_a_second_file(scene: Scene) -> None:
    """The primary key `(competition_id, language)` guards a lost race on SQLite, where the row
    locks render nothing. The state set up here (a file while `published_at` is empty) is not
    reachable through the application (data-model.md §4, invariant 1): it stands in for a
    concurrent publish that stored its files first."""
    store_results_files(scene.engine, scene.competition)
    stored = files(scene.engine)
    with pytest.raises(NotPublishable) as refused:
        publish(scene)
    assert refused.value.status is CompetitionStatus.PUBLISHED
    assert competition_row(scene.engine, scene.competition)[4] is None
    assert files(scene.engine) == stored


def test_two_publishes_at_the_same_moment_publish_once(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    postgresql_only(database_url)
    for n in range(3):
        competition = make_competition(
            engine, scene.chemistry, f"Race {n}", starts_at=STARTED, stopped=True
        )
        outcomes = race(
            engine,
            *[
                lambda session, c=competition: publish_results(
                    session, scene.olena, c, scene.chemistry, None
                )
            ]
            * 2,
        )
        assert sorted(outcomes) == ["NotPublishable", "ok"]
        assert sorted(files(engine, competition)) == [(competition, "en"), (competition, "uk")]


def short_lock_timeout(session: Session) -> None:
    """A lock that is not granted in 300 ms fails, instead of waiting: no test sleeps."""
    session.execute(text("SET LOCAL lock_timeout = '300ms'"))


def test_a_publish_waits_for_a_grade_save_in_progress(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    """Research R5: a grade save holds the competition's share lock; a publish waits for it."""
    postgresql_only(database_url)
    grade_everything(scene)
    with Session(engine) as saving:
        lock_competition(saving, scene.competition, scene.chemistry, share=True)
        with Session(engine) as publishing:
            short_lock_timeout(publishing)
            with pytest.raises(OperationalError, match="lock timeout"):
                publish_results(publishing, scene.olena, scene.competition, scene.chemistry, None)
        saving.commit()
    publish(scene)
    assert competition_row(engine, scene.competition)[4] == NOW


def save_grades(s: Scene, raw: dict[int, str]) -> grades.GradeSaveResult:
    with Session(s.engine) as session:
        return grades.save_grades(session, s.olena, s.competition, s.chemistry, s.comets, raw)


def test_a_grade_saved_first_is_in_the_files(scene: Scene) -> None:
    """FR-017: a grade saved before the publish counts in the files."""
    grade_everything(scene)
    save_grades(scene, {scene.copies[0]: "3"})
    publish(scene)
    assert "School No. 5 Comets 13" in pdf_text(files(scene.engine)[(scene.competition, "en")])


def test_a_grade_emptied_first_blocks_the_publish(scene: Scene) -> None:
    grade_everything(scene)
    save_grades(scene, {scene.copies[0]: ""})
    with pytest.raises(NotFullyGraded):
        publish(scene)
    assert files(scene.engine) == {}


def test_a_grade_save_after_the_publish_is_refused(scene: Scene) -> None:
    """FR-017, FR-021: the files and the grades never disagree."""
    grade_everything(scene)
    publish(scene)
    before = grades_snapshot(scene.engine)
    with pytest.raises(GradingClosed) as refused:
        save_grades(scene, {scene.copies[0]: "3"})
    assert refused.value.status is CompetitionStatus.PUBLISHED
    assert grades_snapshot(scene.engine) == before


def test_a_grade_save_racing_a_publish(engine: Engine, database_url: str, scene: Scene) -> None:
    """Whichever wins, the stored files agree with the stored grades."""
    postgresql_only(database_url)
    grade_everything(scene)
    outcomes = race(
        engine,
        lambda session: publish_results(
            session, scene.olena, scene.competition, scene.chemistry, None
        ),
        lambda session: grades.save_grades(
            session, scene.olena, scene.competition, scene.chemistry, scene.comets,
            {scene.copies[0]: "3"},
        ),
    )  # fmt: skip
    assert outcomes[0] == "ok"
    assert outcomes[1] in ("ok", "GradingClosed")
    score = 13 if outcomes[1] == "ok" else 17
    english = pdf_text(files(engine)[(scene.competition, "en")])
    assert f"School No. 5 Comets {score}" in english
    with Session(engine) as session:
        counts = grades.grade_counts(session, scene.competition)
    assert counts[scene.comets].score == score


def test_a_published_competition_is_never_cancelled(scene: Scene) -> None:
    publish(scene)
    with Session(scene.engine) as session, pytest.raises(NotCancellable) as refused:
        cancel_competition(session, scene.olena, scene.competition, scene.chemistry, None)
    assert refused.value.status is CompetitionStatus.PUBLISHED


# ---------------------------------------------------------------------------------------------
# User story 6: the snapshot and its permanence (FR-025–FR-029)
# ---------------------------------------------------------------------------------------------


def test_every_team_once_with_its_score_in_the_ukrainian_order(scene: Scene) -> None:
    """Regions, institutions, teams by `name_sort_key`: Latin before Cyrillic, Ґ after Г, Є after
    Е, І and Ї after И, apostrophes ignored; a deleted team and teams of deactivated institutions
    and regions included, with no mark."""
    grade_everything(scene)
    kharkiv = make_institution(scene.engine, "Ґрунтовний ліцей", "Харківська")
    gymnasium = make_institution(scene.engine, "Гімназія", "Харківська")
    for institution, names in (
        (kharkiv, ["Їжаки", "Єноти", "Ігуани"]),
        (gymnasium, ["Зʼєднані", "Еліта", "Ведмеді"]),
    ):
        for name in names:
            add_competition_team(
                scene.engine, scene.competition, make_team(scene.engine, institution, name)
            )
    found = lines(snapshot_of(scene))
    assert found == [
        ("Kyiv", "Kyiv Lyceum", "Novas", 0),
        ("Kyiv", "School No. 5", "Comets", 17),
        ("Kyiv", "School No. 5", "Rockets", 4),
        ("Lviv", "Lyceum No. 2", "Lions", 0),
        ("Odesa", "Odesa College", "Stars", 9),
        ("Харківська", "Гімназія", "Ведмеді", 0),
        ("Харківська", "Гімназія", "Еліта", 0),
        ("Харківська", "Гімназія", "Зʼєднані", 0),
        ("Харківська", "Ґрунтовний ліцей", "Єноти", 0),
        ("Харківська", "Ґрунтовний ліцей", "Ігуани", 0),
        ("Харківська", "Ґрунтовний ліцей", "Їжаки", 0),
    ]


def test_equal_names_are_ordered_by_id_and_kept_apart(scene: Scene) -> None:
    """Two teams named "Comets" in one school are ordered by id; a "Comets" of another region's
    "School No. 5" stays under its own region. The twins are deleted teams, the only way the
    live-name rule of milestone 11.1 lets two teams share a name; a finished competition keeps
    them."""
    other_school = make_institution(scene.engine, "School No. 5", "Lviv")
    twin = make_team(scene.engine, other_school, "Comets", deleted=True)
    deleted_twin = make_team(scene.engine, scene.school, "Comets", deleted=True)
    for team in (twin, deleted_twin):
        add_competition_team(scene.engine, scene.competition, team)
    found = lines(snapshot_of(scene))
    assert [line for line in found if line[2] == "Comets"] == [
        ("Kyiv", "School No. 5", "Comets", 0),
        ("Kyiv", "School No. 5", "Comets", 0),
        ("Lviv", "School No. 5", "Comets", 0),
    ]
    assert scene.comets < deleted_twin


def test_the_snapshot_header(scene: Scene) -> None:
    """The maximum score is 10 for each of the competition's questions (2 here)."""
    snapshot = snapshot_of(scene)
    assert (snapshot.competition_name, snapshot.subject_name) == ("Spring round", "Chemistry")
    assert snapshot.max_score == 20
    assert (snapshot.starts_at, snapshot.finished_at, snapshot.published_at) == (
        STARTED,
        competition_row(scene.engine, scene.competition)[3],
        NOW,
    )
    assert isinstance(snapshot.regions[0], RegionResults)
    assert isinstance(snapshot.regions[0].lines[0], ResultLine)


def test_nothing_but_the_results_reaches_a_file(scene: Scene) -> None:
    """FR-027: no question, reference answer, answer or member name."""
    save_team_answer(scene.engine, scene.competition, scene.comets, scene.copies[0], "MARKER-ANS")
    grade_answer(scene.engine, scene.competition, scene.comets, scene.copies[0], 5)
    publish(scene)
    for content in files(scene.engine).values():
        text = pdf_text(content)
        for secret in ("MARKER-ANS", "Question 1?", "Ref 1.", "Taras", "Shevchenko", "olena@"):
            assert secret not in text


def test_the_files_never_change_afterwards(scene: Scene) -> None:
    """FR-029, SC-004: renames, deactivations and deletions after publishing change nothing."""
    grade_everything(scene)
    publish(scene)
    stored = files(scene.engine)
    with Session(scene.engine) as session:
        for statement in (
            "UPDATE regions SET name = 'Renamed ' || name, name_key = 'renamed ' || name_key",
            "UPDATE institutions SET name = 'Renamed ' || name, name_key = 'renamed ' || name_key",
            "UPDATE teams SET name = 'Renamed ' || name, name_key = 'renamed ' || name_key",
            "UPDATE subjects SET name = 'Renamed ' || name, name_key = 'renamed ' || name_key",
            "UPDATE institutions SET is_active = false",
            "UPDATE subjects SET is_active = false",
        ):
            session.exec(text(statement))
        team = session.get(Team, scene.comets)
        assert team is not None
        team.deleted_at = NOW
        session.add(team)
        session.commit()
    assert files(scene.engine) == stored
    english = pdf_text(stored[(scene.competition, "en")])
    assert "School No. 5 Comets 17" in english and "Renamed" not in english


def test_no_code_updates_or_deletes_a_results_file() -> None:
    """Data-model.md §4 invariant 2: the table is insert-only."""
    from pathlib import Path

    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("app").rglob("*.py"))
    for forbidden in (
        "update(CompetitionResultsFile",
        "delete(CompetitionResultsFile",
        "UPDATE competition_results_files",
        "DELETE FROM competition_results_files",
    ):
        assert forbidden not in source


def _seed_500_teams(engine: Engine, competition: int, copies: list[int]) -> None:
    """500 teams in 10 regions (5 institutions of 10 teams each), every answer graded."""
    with Session(engine) as session:
        for r in range(10):
            region = Region(name=f"Region {r:02d}", name_key=name_key(f"Region {r:02d}"))
            session.add(region)
            session.flush()
            for i in range(5):
                institution = Institution(
                    region_id=region.id or 0,
                    name=f"Institution {r:02d}-{i}",
                    name_key=name_key(f"Institution {r:02d}-{i}"),
                )
                session.add(institution)
                session.flush()
                for t in range(10):
                    team = Team(
                        institution_id=institution.id or 0,
                        name=f"Team {r:02d}-{i}-{t}",
                        name_key=name_key(f"Team {r:02d}-{i}-{t}"),
                    )
                    session.add(team)
                    session.flush()
                    assert team.id is not None
                    session.add(CompetitionTeam(competition_id=competition, team_id=team.id))
                    session.flush()
                    for copy in copies:
                        session.add(
                            TeamAnswer(
                                competition_id=competition,
                                team_id=team.id,
                                competition_question_id=copy,
                                text="An answer",
                                grade=(t + copy) % 11,
                            )
                        )
        session.commit()


def test_publishing_500_teams_takes_under_5_seconds(scene: Scene) -> None:
    """SC-007: 500 teams in 10 regions with 10 graded answers each, files included. Runs
    everywhere and is never skipped; only the publish itself is timed."""
    big = make_competition(scene.engine, scene.chemistry, "Big", starts_at=STARTED, stopped=True)
    with Session(scene.engine) as session:
        bank = [
            make_question(scene.engine, scene.chemistry, f"Big question {n}?", "Ref.")
            for n in range(10)
        ]
        del session
    copies = [add_competition_question(scene.engine, big, q) for q in bank]
    _seed_500_teams(scene.engine, big, copies)
    started = time.perf_counter()
    publish(scene, competition=big)
    elapsed = time.perf_counter() - started
    assert elapsed < 5, f"publishing 500 teams took {elapsed:.2f} s"
    with Session(scene.engine) as session:
        teams = session.exec(
            select(CompetitionTeam).where(col(CompetitionTeam.competition_id) == big)
        ).all()
        questions = session.exec(
            select(CompetitionQuestion).where(col(CompetitionQuestion.competition_id) == big)
        ).all()
    assert (len(teams), len(questions)) == (500, 10)
    english = pdf_text(files(scene.engine)[(big, "en")])
    assert english.count("Institution ") == 500
