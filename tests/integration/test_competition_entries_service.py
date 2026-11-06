"""A competition's questions and teams: the copies and their independence from the bank, the order
of adding, the teams grouped by region, the addable teams, the landing after a removal, and every
refusal, under concurrency too.

See specs/012.2-competition-questions-teams/contracts/services.md and research R1–R5, R10–R14,
R16. Every case runs on both engines; the two-session races run on PostgreSQL only (on SQLite the
locks render nothing, and writers are serialised anyway). The clock is fixed at 1 March 2027 09:00
UTC by patching `app.services.competitions.utc_now`, which the service reads; no test waits.

- the manager: a real teacher with **Can manage competitions**, linked only to "Lviv Academy";
- the reader: a real teacher without it;
- "Chemistry" and "Physics": active subjects; "Spring round": an upcoming competition of Chemistry
  starting 14 March 2027 08:00 UTC.

Questions, teams, members, finished competitions and the entries of a cancelled or finished
competition are seeded directly (`tests/conftest.py`), so the service is never checked through
itself.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, MetaData
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.models import AccessLevel, CompetitionQuestion, Institution, Question
from app.services import competition_entries as entries
from app.services.competition_entries import (
    AddableTeam,
    AlreadyIn,
    CompetitionQuestionView,
    EntryNotFound,
    Landing,
    NotChangeable,
    NotIn,
    TeamRow,
)
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    ManageRequired,
    cancel_competition,
)
from app.services.institutions import set_institution_active
from app.services.questions import delete_question, update_question
from app.services.questions import question_page as bank_page
from app.services.regions import set_region_active
from app.services.subjects import set_subject_active
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
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
from tests.integration.test_team_service import enrolled

NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
START = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
MISSING = 999_999


@dataclass(frozen=True)
class Scene:
    engine: Engine
    manager: int
    reader: int
    chemistry: int
    physics: int
    competition: int
    """"Spring round", Upcoming."""
    school: int
    """"School No. 5", Kyiv; nobody is linked to it."""
    lyceum: int
    """"Kyiv Lyceum", Kyiv; nobody is linked to it."""
    academy: int
    """"Lviv Academy", Lviv; the manager reads it."""


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    """A controllable `utc_now`, starting at 1 March 2027 09:00 UTC; call it to advance, and it
    returns the new time."""
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
    academy = make_institution(engine, "Lviv Academy", "Lviv")
    manager = make_teacher(
        engine,
        auth_settings,
        email="manager@example.org",
        institutions={academy: AccessLevel.READ},
        can_manage=True,
    )
    reader = make_teacher(
        engine,
        auth_settings,
        email="reader@example.org",
        institutions={academy: AccessLevel.WRITE},
    )
    chemistry = make_subject(engine, "Chemistry")
    return Scene(
        engine=engine,
        manager=manager,
        reader=reader,
        chemistry=chemistry,
        physics=make_subject(engine, "Physics"),
        competition=make_competition(engine, chemistry, starts_at=START),
        school=make_institution(engine, "School No. 5", "Kyiv"),
        lyceum=make_institution(engine, "Kyiv Lyceum", "Kyiv"),
        academy=academy,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

SNAPSHOT_TABLES = (
    "competition_questions",
    "competition_teams",
    "competitions",
    "questions",
    "teams",
    "team_memberships",
)


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(sa_select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def region_of(engine: Engine, institution_id: int) -> int:
    with Session(engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


def copies(engine: Engine, competition_id: int) -> list[tuple[int, str, str]]:
    """`(question_id, text, reference_answer)` of every copy, in the order of adding."""
    with Session(engine) as session:
        rows = session.exec(
            select(CompetitionQuestion)
            .where(CompetitionQuestion.competition_id == competition_id)
            .order_by(CompetitionQuestion.id)  # type: ignore[arg-type]
        )
        return [(c.question_id, c.text, c.reference_answer) for c in rows]


def listed_questions(engine: Engine, competition_id: int, p: int = 1) -> list[int]:
    with Session(engine) as session:
        return [q.question_id for q in entries.question_page(session, competition_id, p).questions]


def linked(engine: Engine, competition_id: int) -> set[int]:
    with Session(engine) as session:
        return entries.team_ids(session, competition_id)


def groups(engine: Engine, competition_id: int, p: int) -> list[tuple[str, int, list[str]]]:
    """`(region, total, team names)` of each region group on page `p`."""
    with Session(engine) as session:
        listing = entries.team_page(session, competition_id, p)
        return [(g.region_name, g.total, [r.name for r in g.rows]) for g in listing.groups]


def call(engine: Engine, action: Callable[..., Any], *args: Any) -> Any:
    """`action(session, *args)` in a fresh session; the session must stay usable after a
    refusal, so a read follows in the same session."""
    with Session(engine) as session:
        try:
            return action(session, *args)
        finally:
            session.exec(select(Question.id)).all()


def race(engine: Engine, *actions: Callable[[Session], Any]) -> list[str]:
    """Run the actions at once, each in its own session, released together by a barrier; each
    outcome is "ok" or the name of the exception it raised."""
    barrier = threading.Barrier(len(actions))
    outcomes: list[str] = [""] * len(actions)

    def run(index: int) -> None:
        with Session(engine) as session:
            barrier.wait()
            try:
                actions[index](session)
            except BaseException as error:  # noqa: BLE001 — reported in the outcomes
                outcomes[index] = type(error).__name__
            else:
                outcomes[index] = "ok"

    threads = [threading.Thread(target=run, args=(index,)) for index in range(len(actions))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return outcomes


def postgresql_only(database_url: str) -> None:
    if not database_url.startswith("postgresql"):
        pytest.skip("row locks are a PostgreSQL behaviour")


# ---------------------------------------------------------------------------------------------
# User story 1: adding questions
# ---------------------------------------------------------------------------------------------


def test_adding_copies_the_question_as_the_bank_holds_it(scene: Scene) -> None:
    """FR-007, FR-018, US1-4."""
    question = make_question(scene.engine, scene.chemistry, "Why is the sky blue?", "Rayleigh.")
    call(scene.engine, entries.add_question, scene.manager, scene.competition, scene.chemistry,
         question)  # fmt: skip
    assert copies(scene.engine, scene.competition) == [
        (question, "Why is the sky blue?", "Rayleigh.")
    ]
    with Session(scene.engine) as session:
        listing = entries.question_page(session, scene.competition, 1)
    assert listing.questions == [
        CompetitionQuestionView(question, "Why is the sky blue?", "Rayleigh.", False)
    ]


def test_questions_are_listed_in_the_order_of_adding(scene: Scene) -> None:
    """FR-005, US1: added as 12, 9, 15, listed as 12, 9, 15, not by id."""
    nine, twelve, fifteen = (make_question(scene.engine, scene.chemistry) for _ in range(3))
    for question in (twelve, nine, fifteen):
        entries.add_question(
            Session(scene.engine), scene.manager, scene.competition, scene.chemistry, question
        )
    assert listed_questions(scene.engine, scene.competition) == [twelve, nine, fifteen]
    with Session(scene.engine) as session:
        assert entries.question_ids(session, scene.competition) == {nine, twelve, fifteen}
        assert entries.question_ids(session, MISSING) == set()


@pytest.mark.parametrize("case", ["other-subject", "deleted", "unknown"])
def test_a_question_that_cannot_be_added_is_not_found(scene: Scene, case: str) -> None:
    """FR-045 step 5, research R3: nothing is stored, and the session stays usable."""
    question = {
        "other-subject": lambda: make_question(scene.engine, scene.physics),
        "deleted": lambda: make_question(scene.engine, scene.chemistry, deleted=True),
        "unknown": lambda: MISSING,
    }[case]()
    before = snapshot(scene.engine)
    with pytest.raises(EntryNotFound) as refused:
        call(scene.engine, entries.add_question, scene.manager, scene.competition,
             scene.chemistry, question)  # fmt: skip
    assert refused.value.kind == "question"
    assert snapshot(scene.engine) == before


def test_adding_twice_is_already_in_and_stores_once(scene: Scene) -> None:
    """FR-035."""
    question = make_question(scene.engine, scene.chemistry)
    args = (scene.manager, scene.competition, scene.chemistry, question)
    call(scene.engine, entries.add_question, *args)
    with pytest.raises(AlreadyIn) as already:
        call(scene.engine, entries.add_question, *args)
    assert (already.value.kind, already.value.entry_id) == ("question", question)
    assert len(copies(scene.engine, scene.competition)) == 1


def test_25_questions_are_paged_ten_by_ten(scene: Scene) -> None:
    """FR-005: 10, 10 and 5; a page past the end opens the last."""
    for _ in range(25):
        add_competition_question(
            scene.engine, scene.competition, make_question(scene.engine, scene.chemistry)
        )
    with Session(scene.engine) as session:
        sizes = [
            len(entries.question_page(session, scene.competition, p).questions) for p in (1, 2, 3)
        ]
        last = entries.question_page(session, scene.competition, 99)
    assert sizes == [10, 10, 5]
    assert (last.paging.number, len(last.questions)) == (3, 5)


# ---------------------------------------------------------------------------------------------
# User story 3: the copies, whatever happens in the bank
# ---------------------------------------------------------------------------------------------


def test_a_bank_edit_leaves_the_copy(scene: Scene) -> None:
    """FR-007, US3-4, SC-002."""
    question = make_question(scene.engine, scene.chemistry, "Old text", "Old answer")
    call(scene.engine, entries.add_question, scene.manager, scene.competition, scene.chemistry,
         question)  # fmt: skip
    with Session(scene.engine) as session:
        update_question(session, scene.manager, question, "New text", "New answer")
    with Session(scene.engine) as session:
        (view,) = entries.question_page(session, scene.competition, 1).questions
    assert (view.text, view.reference_answer, view.deleted_from_bank) == (
        "Old text",
        "Old answer",
        False,
    )


def test_a_bank_deletion_leaves_the_copy_marked(scene: Scene) -> None:
    """FR-008, FR-039, US3-5."""
    question = make_question(scene.engine, scene.chemistry, "Kept", "Kept answer")
    add_competition_question(scene.engine, scene.competition, question)
    with Session(scene.engine) as session:
        delete_question(session, scene.manager, question)
    with Session(scene.engine) as session:
        (view,) = entries.question_page(session, scene.competition, 1).questions
    assert view == CompetitionQuestionView(question, "Kept", "Kept answer", True)


def test_23_copies_in_the_order_of_adding(scene: Scene) -> None:
    """US3-2: "Questions 11–20 of 23" on page 2."""
    ids = [make_question(scene.engine, scene.chemistry) for _ in range(23)]
    for question in reversed(ids):
        add_competition_question(scene.engine, scene.competition, question)
    with Session(scene.engine) as session:
        listing = entries.question_page(session, scene.competition, 2)
    paging = listing.paging
    assert (paging.first_item, paging.last_item, paging.total) == (11, 20, 23)
    assert [q.question_id for q in listing.questions] == list(reversed(ids))[10:20]


def test_a_question_added_again_goes_to_the_end(scene: Scene) -> None:
    """FR-005, research R1: a new, larger id."""
    first, second = (make_question(scene.engine, scene.chemistry) for _ in range(2))
    add_competition_question(scene.engine, scene.competition, first)
    add_competition_question(scene.engine, scene.competition, second)
    call(scene.engine, entries.remove_question, scene.manager, scene.competition,
         scene.chemistry, first)  # fmt: skip
    add_competition_question(scene.engine, scene.competition, first)
    assert listed_questions(scene.engine, scene.competition) == [second, first]


# ---------------------------------------------------------------------------------------------
# User story 4: the teams, grouped by region
# ---------------------------------------------------------------------------------------------


def seed_regions(scene: Scene) -> dict[str, list[int]]:
    """25 teams in the competition: "Dnipro" 4, "Kyiv" 14, "Lviv" 7, each region's teams named
    "<region> 01" … in an order the ids do not follow."""
    institutions = {
        "Dnipro": make_institution(scene.engine, "Dnipro School", "Dnipro"),
        "Kyiv": scene.school,
        "Lviv": scene.academy,
    }
    teams: dict[str, list[int]] = {}
    for region, size in (("Lviv", 7), ("Kyiv", 14), ("Dnipro", 4)):
        teams[region] = []
        for n in reversed(range(1, size + 1)):
            team = make_team(scene.engine, institutions[region], f"{region} {n:02}")
            add_competition_team(scene.engine, scene.competition, team)
            teams[region].insert(0, team)
    return teams


def test_teams_are_grouped_by_region_across_pages(scene: Scene) -> None:
    """FR-010, FR-011, US4-3–US4-5: a region spanning a page break repeats its total."""
    seed_regions(scene)
    assert [(name, total, len(rows)) for name, total, rows in groups(scene.engine,
            scene.competition, 1)] == [("Dnipro", 4, 4), ("Kyiv", 14, 6)]  # fmt: skip
    page_two = groups(scene.engine, scene.competition, 2)
    assert [(name, total, len(rows)) for name, total, rows in page_two] == [
        ("Kyiv", 14, 8),
        ("Lviv", 7, 2),
    ]
    assert page_two[0][2][0] == "Kyiv 07"
    assert [(n, t, len(r)) for n, t, r in groups(scene.engine, scene.competition, 3)] == [
        ("Lviv", 7, 5)
    ]
    with Session(scene.engine) as session:
        paging = entries.team_page(session, scene.competition, 1).paging
    assert (paging.total, paging.last) == (25, 3)


def test_regions_and_teams_are_sorted_ignoring_case(scene: Scene) -> None:
    """FR-010: the same order on both engines, ties by id."""
    zaporizhzhia = make_institution(scene.engine, "Zaporizhzhia College", "zaporizhzhia")
    apple = make_institution(scene.engine, "Apple School", "Ärger")
    for institution, name in (
        (zaporizhzhia, "zebra"),
        (scene.school, "ärger"),
        (scene.school, "Banana"),
        (scene.school, "apple"),
        (apple, "Cherry"),
    ):
        add_competition_team(
            scene.engine, scene.competition, make_team(scene.engine, institution, name)
        )
    assert groups(scene.engine, scene.competition, 1) == [
        ("Kyiv", 3, ["apple", "Banana", "ärger"]),
        ("zaporizhzhia", 1, ["zebra"]),
        ("Ärger", 1, ["Cherry"]),
    ]


def test_each_team_shows_its_institution_and_active_members(scene: Scene) -> None:
    """FR-012, research R13: 0 for a team without members."""
    kn21 = make_class(scene.engine, scene.school)
    comets = make_team(scene.engine, scene.school, "Comets")
    novas = make_team(scene.engine, scene.lyceum, "Novas")
    for n in range(3):
        make_member(scene.engine, comets, enrolled(scene.engine, f"s{n}@example.org", kn21))
    for team in (comets, novas):
        add_competition_team(scene.engine, scene.competition, team)
    with Session(scene.engine) as session:
        (group,) = entries.team_page(session, scene.competition, 1).groups
    assert group.rows == [
        TeamRow(comets, "Comets", "School No. 5", 3, False),
        TeamRow(novas, "Novas", "Kyiv Lyceum", 0, False),
    ]


def test_a_team_of_a_deactivated_institution_or_region_is_still_listed(scene: Scene) -> None:
    """FR-013, FR-042, US4-7."""
    comets = make_team(scene.engine, scene.school, "Comets")
    lions = make_team(scene.engine, scene.academy, "Lions")
    for team in (comets, lions):
        add_competition_team(scene.engine, scene.competition, team)
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, scene.school), scene.school, False)
        set_region_active(session, region_of(scene.engine, scene.academy), False)
    assert [(n, t, r) for n, t, r in groups(scene.engine, scene.competition, 1)] == [
        ("Kyiv", 1, ["Comets"]),
        ("Lviv", 1, ["Lions"]),
    ]


def test_a_deleted_team_of_a_finished_competition_is_marked(scene: Scene) -> None:
    """FR-013, US4-8."""
    finished = make_competition(
        scene.engine, scene.chemistry, "Summer round", starts_at=START, stopped=True
    )
    comets = make_team(scene.engine, scene.school, "Comets", deleted=True)
    add_competition_team(scene.engine, finished, comets)
    with Session(scene.engine) as session:
        (group,) = entries.team_page(session, finished, 1).groups
    assert group.rows == [TeamRow(comets, "Comets", "School No. 5", 0, True)]


# ---------------------------------------------------------------------------------------------
# User story 2: adding teams
# ---------------------------------------------------------------------------------------------


def test_the_addable_teams_of_a_region_come_from_every_institution(scene: Scene) -> None:
    """FR-023, US2-5: two institutions nobody is linked to, by name ignoring case, 10 per page;
    deleted teams and teams of a deactivated institution are left out."""
    names = [f"Team {chr(ord('a') + n)}" for n in range(14)]
    for n, name in enumerate(names):
        make_team(scene.engine, scene.school if n % 2 else scene.lyceum, name.swapcase())
    make_team(scene.engine, scene.school, "Deleted", deleted=True)
    closed = make_institution(scene.engine, "Closed School", "Kyiv")
    make_team(scene.engine, closed, "Closed team")
    make_team(scene.engine, scene.academy, "Lviv team")
    with Session(scene.engine) as session:
        set_institution_active(session, region_of(scene.engine, closed), closed, False)
    kyiv = region_of(scene.engine, scene.school)
    with Session(scene.engine) as session:
        first = entries.addable_teams(session, kyiv, 1)
        second = entries.addable_teams(session, kyiv, 2)
    assert [t.name for t in first.teams + second.teams] == [n.swapcase() for n in names]
    assert (len(first.teams), len(second.teams), first.paging.total) == (10, 4, 14)
    assert first.teams[0] == AddableTeam(first.teams[0].team_id, "tEAM A", "Kyiv Lyceum", 0)
    assert {t.institution_name for t in first.teams} == {"School No. 5", "Kyiv Lyceum"}


def test_teams_with_no_members_or_a_shared_member_are_added(scene: Scene) -> None:
    """FR-027, US2-11: no member check, and no link check (the manager reaches only Lviv)."""
    kn21 = make_class(scene.engine, scene.school)
    taras = enrolled(scene.engine, "taras@example.org", kn21)
    comets = make_team(scene.engine, scene.school, "Comets")
    rockets = make_team(scene.engine, scene.school, "Rockets")
    novas = make_team(scene.engine, scene.lyceum, "Novas")
    make_member(scene.engine, comets, taras)
    make_member(scene.engine, rockets, taras)
    kyiv = region_of(scene.engine, scene.school)
    for team in (comets, rockets, novas):
        call(scene.engine, entries.add_team, scene.manager, scene.competition, scene.chemistry,
             kyiv, team)  # fmt: skip
    assert linked(scene.engine, scene.competition) == {comets, rockets, novas}


@pytest.mark.parametrize(
    "case",
    ["unknown", "deleted", "other-region", "institution-deactivated", "region-deactivated"],
)
def test_a_team_that_cannot_be_added_is_not_found(scene: Scene, case: str) -> None:
    """FR-045 step 5, research R4: nothing is stored, and the session stays usable."""
    team = make_team(scene.engine, scene.school, "Comets", deleted=case == "deleted")
    kyiv = region_of(scene.engine, scene.school)
    region = region_of(scene.engine, scene.academy) if case == "other-region" else kyiv
    with Session(scene.engine) as session:
        if case == "institution-deactivated":
            set_institution_active(session, kyiv, scene.school, False)
        if case == "region-deactivated":
            set_region_active(session, kyiv, False)
    before = snapshot(scene.engine)
    with pytest.raises(EntryNotFound) as refused:
        call(scene.engine, entries.add_team, scene.manager, scene.competition, scene.chemistry,
             region, MISSING if case == "unknown" else team)  # fmt: skip
    assert refused.value.kind == "team"
    assert snapshot(scene.engine) == before


def test_adding_a_team_twice_is_already_in(scene: Scene) -> None:
    """FR-035."""
    team = make_team(scene.engine, scene.school, "Comets")
    args = (
        scene.manager,
        scene.competition,
        scene.chemistry,
        region_of(scene.engine, scene.school),
        team,
    )
    call(scene.engine, entries.add_team, *args)
    with pytest.raises(AlreadyIn) as already:
        call(scene.engine, entries.add_team, *args)
    assert (already.value.kind, already.value.entry_id) == ("team", team)
    assert linked(scene.engine, scene.competition) == {team}


# ---------------------------------------------------------------------------------------------
# User story 5: removing
# ---------------------------------------------------------------------------------------------


def test_removing_a_question_leaves_the_bank(scene: Scene) -> None:
    """FR-033, US5-7."""
    question = make_question(scene.engine, scene.chemistry, "Stays", "In the bank")
    add_competition_question(scene.engine, scene.competition, question)
    with Session(scene.engine) as session:
        bank_before = session.get(Question, question)
        assert bank_before is not None
        bank_row = bank_before.model_dump()
    landing = call(scene.engine, entries.remove_question, scene.manager, scene.competition,
                   scene.chemistry, question)  # fmt: skip
    assert landing == Landing(1, None)
    assert copies(scene.engine, scene.competition) == []
    with Session(scene.engine) as session:
        bank_after = session.get(Question, question)
        assert bank_after is not None
        assert bank_after.model_dump() == bank_row


def test_removing_a_team_leaves_the_team_and_its_members(scene: Scene) -> None:
    """FR-033, US5-7."""
    kn21 = make_class(scene.engine, scene.school)
    comets = make_team(scene.engine, scene.school, "Comets")
    make_member(scene.engine, comets, enrolled(scene.engine, "taras@example.org", kn21))
    add_competition_team(scene.engine, scene.competition, comets)
    before = snapshot(scene.engine)
    landing = call(scene.engine, entries.remove_team, scene.manager, scene.competition,
                   scene.chemistry, comets)  # fmt: skip
    assert landing == Landing(1, None)
    after = snapshot(scene.engine)
    assert after["competition_teams"] == []
    for table in ("teams", "team_memberships"):
        assert after[table] == before[table]


def test_a_question_deleted_from_the_bank_is_removed_and_no_longer_offered(scene: Scene) -> None:
    """FR-033, FR-045 step 5, US5-8."""
    question = make_question(scene.engine, scene.chemistry)
    add_competition_question(scene.engine, scene.competition, question)
    with Session(scene.engine) as session:
        delete_question(session, scene.manager, question)
    call(scene.engine, entries.remove_question, scene.manager, scene.competition,
         scene.chemistry, question)  # fmt: skip
    with Session(scene.engine) as session:
        assert question not in entries.question_ids(session, scene.competition)
        assert question not in [q.id for q in bank_page(session, scene.chemistry, 1).questions]
    with pytest.raises(EntryNotFound):
        call(scene.engine, entries.add_question, scene.manager, scene.competition,
             scene.chemistry, question)  # fmt: skip


def test_a_removed_question_added_again_has_the_banks_current_text(scene: Scene) -> None:
    """FR-007, US5-9."""
    first = make_question(scene.engine, scene.chemistry, "Old", "Old answer")
    second = make_question(scene.engine, scene.chemistry)
    for question in (first, second):
        add_competition_question(scene.engine, scene.competition, question)
    args = (scene.manager, scene.competition, scene.chemistry, first)
    call(scene.engine, entries.remove_question, *args)
    with Session(scene.engine) as session:
        update_question(session, scene.manager, first, "New", "New answer")
    call(scene.engine, entries.add_question, *args)
    assert [c[:2] for c in copies(scene.engine, scene.competition)] == [
        (second, "Question?"),
        (first, "New"),
    ]


def test_the_landing_after_removing_a_question(scene: Scene) -> None:
    """FR-032, research R11: the row that took its place, the row before it when it was last, the
    previous page's last row when a page empties, and the empty state."""
    ids = [make_question(scene.engine, scene.chemistry) for _ in range(11)]
    for question in ids:
        add_competition_question(scene.engine, scene.competition, question)

    def remove(question: int) -> Landing:
        return call(scene.engine, entries.remove_question, scene.manager, scene.competition,
                    scene.chemistry, question)  # fmt: skip

    assert remove(ids[3]) == Landing(1, ids[4])
    assert remove(ids[10]) == Landing(1, ids[9])
    assert remove(ids[9]) == Landing(1, ids[8])
    for question in ids[:2]:
        remove(question)
    remaining = [q for q in ids if q not in (ids[0], ids[1], ids[3], ids[9], ids[10])]
    for question in remaining[:-1]:
        remove(question)
    assert remove(remaining[-1]) == Landing(1, None)


def test_removing_a_team_of_a_region_spanning_a_page_break_changes_both_totals(
    scene: Scene,
) -> None:
    """Spec Edge Cases; FR-011."""
    teams = seed_regions(scene)
    landing = call(scene.engine, entries.remove_team, scene.manager, scene.competition,
                   scene.chemistry, teams["Kyiv"][0])  # fmt: skip
    assert landing == Landing(1, teams["Kyiv"][1])
    assert [(n, t) for n, t, _ in groups(scene.engine, scene.competition, 1)] == [
        ("Dnipro", 4),
        ("Kyiv", 13),
    ]
    assert [(n, t) for n, t, _ in groups(scene.engine, scene.competition, 2)] == [
        ("Kyiv", 13),
        ("Lviv", 7),
    ]


def test_the_landing_after_removing_the_only_team_of_the_last_page(scene: Scene) -> None:
    """FR-032: the previous page, at its last row."""
    teams = [make_team(scene.engine, scene.school, f"Team {n:02}") for n in range(11)]
    for team in teams:
        add_competition_team(scene.engine, scene.competition, team)
    landing = call(scene.engine, entries.remove_team, scene.manager, scene.competition,
                   scene.chemistry, teams[10])  # fmt: skip
    assert landing == Landing(1, teams[9])


def test_an_entry_is_looked_up_for_the_confirmation(scene: Scene) -> None:
    """Research R10: unknown ids are not found; known ones that are not in, "not in"; a deleted
    team and a question deleted from the bank are found."""
    question = make_question(scene.engine, scene.chemistry, "Text", "Answer")
    absent_question = make_question(scene.engine, scene.chemistry)
    comets = make_team(scene.engine, scene.school, "Comets")
    absent_team = make_team(scene.engine, scene.school, "Novas")
    add_competition_question(scene.engine, scene.competition, question)
    add_competition_team(scene.engine, scene.competition, comets)
    with Session(scene.engine) as session:
        delete_question(session, scene.manager, question)
    with Session(scene.engine) as session:
        assert entries.get_competition_question(
            session, scene.competition, question
        ) == CompetitionQuestionView(question, "Text", "Answer", True)
        assert entries.get_competition_team(session, scene.competition, comets) == (
            TeamRow(comets, "Comets", "School No. 5", 0, False),
            "Kyiv",
        )
        with pytest.raises(EntryNotFound):
            entries.get_competition_question(session, scene.competition, MISSING)
        with pytest.raises(NotIn):
            entries.get_competition_question(session, scene.competition, absent_question)
        with pytest.raises(EntryNotFound):
            entries.get_competition_team(session, scene.competition, MISSING)
        with pytest.raises(NotIn):
            entries.get_competition_team(session, scene.competition, absent_team)


@pytest.mark.parametrize("kind", ["question", "team"])
def test_removing_twice_is_not_in(scene: Scene, kind: str) -> None:
    """FR-036; an id that names nothing at all is not found."""
    if kind == "question":
        entry = make_question(scene.engine, scene.chemistry)
        add_competition_question(scene.engine, scene.competition, entry)
        remove: Callable[..., Any] = entries.remove_question
    else:
        entry = make_team(scene.engine, scene.school, "Comets")
        add_competition_team(scene.engine, scene.competition, entry)
        remove = entries.remove_team
    args = (scene.manager, scene.competition, scene.chemistry)
    call(scene.engine, remove, *args, entry)
    before = snapshot(scene.engine)
    with pytest.raises(NotIn) as absent:
        call(scene.engine, remove, *args, entry)
    assert (absent.value.kind, absent.value.entry_id) == (kind, entry)
    with pytest.raises(EntryNotFound):
        call(scene.engine, remove, *args, MISSING)
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 7: changes stop when the competition leaves Upcoming
# ---------------------------------------------------------------------------------------------


def writes(scene: Scene, competition: int) -> list[tuple[Callable[..., Any], tuple[Any, ...]]]:
    """Each of the four writes, with an entry ready for it: a question and a team in the
    competition, and one of each to add."""
    in_question = make_question(scene.engine, scene.chemistry)
    new_question = make_question(scene.engine, scene.chemistry)
    in_team = make_team(scene.engine, scene.school, f"In {competition}")
    new_team = make_team(scene.engine, scene.school, f"New {competition}")
    add_competition_question(scene.engine, competition, in_question)
    add_competition_team(scene.engine, competition, in_team)
    kyiv = region_of(scene.engine, scene.school)
    return [
        (entries.add_question, (competition, scene.chemistry, new_question)),
        (entries.remove_question, (competition, scene.chemistry, in_question)),
        (entries.add_team, (competition, scene.chemistry, kyiv, new_team)),
        (entries.remove_team, (competition, scene.chemistry, in_team)),
    ]


@pytest.mark.parametrize("status", ["in_progress", "cancelled", "finished"])
def test_nothing_changes_once_the_competition_is_not_upcoming(
    scene: Scene, clock: Callable[[timedelta], datetime], status: str
) -> None:
    """FR-034, US7-2, US7-3, SC-004."""
    competition = make_competition(
        scene.engine,
        scene.chemistry,
        "Autumn round",
        starts_at=START,
        cancelled=status == "cancelled",
        stopped=status == "finished",
    )
    actions = writes(scene, competition)
    if status == "in_progress":
        clock(START - NOW)
    before = snapshot(scene.engine)
    for action, args in actions:
        with pytest.raises(NotChangeable) as refused:
            call(scene.engine, action, scene.manager, *args)
        assert refused.value.status is CompetitionStatus(status), action.__name__
    assert snapshot(scene.engine) == before


def test_the_start_minute_itself_is_in_progress(
    scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    question = make_question(scene.engine, scene.chemistry)
    clock(START - NOW - timedelta(minutes=1))
    call(scene.engine, entries.add_question, scene.manager, scene.competition, scene.chemistry,
         question)  # fmt: skip
    clock(timedelta(minutes=1))
    with pytest.raises(NotChangeable):
        call(scene.engine, entries.remove_question, scene.manager, scene.competition,
             scene.chemistry, question)  # fmt: skip


def test_the_setting_is_checked_before_anything_else(scene: Scene) -> None:
    """FR-045 step 2: before the competition, its status and the entry, so unknown ids and a
    cancelled competition give `ManageRequired` too."""
    cancelled = make_competition(
        scene.engine, scene.chemistry, "Autumn round", starts_at=START, cancelled=True
    )
    before = snapshot(scene.engine)
    for competition in (scene.competition, cancelled, MISSING):
        for action, args in [
            (entries.add_question, (competition, scene.chemistry, MISSING)),
            (entries.remove_question, (competition, scene.chemistry, MISSING)),
            (entries.add_team, (competition, scene.chemistry, MISSING, MISSING)),
            (entries.remove_team, (competition, scene.chemistry, MISSING)),
        ]:
            with pytest.raises(ManageRequired):
                call(scene.engine, action, scene.reader, *args)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("case", ["other-subject", "hidden", "unknown"])
def test_a_competition_not_found_is_refused(scene: Scene, case: str) -> None:
    """FR-045 step 3: before the status, so a hidden cancelled competition is not found."""
    biology = make_subject(scene.engine, "Biology")
    hidden = make_competition(scene.engine, biology, starts_at=START, cancelled=True)
    with Session(scene.engine) as session:
        set_subject_active(session, biology, False)
    competition, subject = {
        "other-subject": (scene.competition, scene.physics),
        "hidden": (hidden, biology),
        "unknown": (MISSING, scene.chemistry),
    }[case]
    question = make_question(scene.engine, scene.chemistry)
    before = snapshot(scene.engine)
    for action, args in [
        (entries.add_question, (competition, subject, question)),
        (entries.remove_question, (competition, subject, question)),
        (entries.add_team, (competition, subject, MISSING, MISSING)),
        (entries.remove_team, (competition, subject, MISSING)),
    ]:
        with pytest.raises(CompetitionNotFound):
            call(scene.engine, action, scene.manager, *args)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("kind", ["question", "team"])
def test_two_additions_at_once_store_one(scene: Scene, database_url: str, kind: str) -> None:
    """FR-035, SC-004: one row, one `AlreadyIn`."""
    postgresql_only(database_url)
    if kind == "question":
        entry = make_question(scene.engine, scene.chemistry)
        action: Callable[..., Any] = entries.add_question
        args: tuple[Any, ...] = (scene.chemistry, entry)
    else:
        entry = make_team(scene.engine, scene.school, "Comets")
        action = entries.add_team
        args = (scene.chemistry, region_of(scene.engine, scene.school), entry)
    outcomes = race(
        scene.engine,
        *[lambda s: action(s, scene.manager, scene.competition, *args) for _ in range(2)],
    )
    assert sorted(outcomes) == ["AlreadyIn", "ok"]
    if kind == "question":
        assert len(copies(scene.engine, scene.competition)) == 1
    else:
        assert linked(scene.engine, scene.competition) == {entry}


@pytest.mark.parametrize("kind", ["question", "team"])
def test_two_removals_at_once_change_once(scene: Scene, database_url: str, kind: str) -> None:
    """FR-036: one `Landing`, one `NotIn`."""
    postgresql_only(database_url)
    if kind == "question":
        entry = make_question(scene.engine, scene.chemistry)
        add_competition_question(scene.engine, scene.competition, entry)
        action: Callable[..., Any] = entries.remove_question
    else:
        entry = make_team(scene.engine, scene.school, "Comets")
        add_competition_team(scene.engine, scene.competition, entry)
        action = entries.remove_team
    outcomes = race(
        scene.engine,
        *[
            lambda s: action(s, scene.manager, scene.competition, scene.chemistry, entry)
            for _ in range(2)
        ],
    )
    assert sorted(outcomes) == ["NotIn", "ok"]
    assert copies(scene.engine, scene.competition) == []
    assert linked(scene.engine, scene.competition) == set()


def test_an_addition_racing_a_cancellation(scene: Scene, database_url: str) -> None:
    """Research R2: whichever commits first is seen by the other; never a cancelled competition
    that gains an entry after its cancellation."""
    postgresql_only(database_url)
    for attempt in range(3):
        competition = make_competition(
            scene.engine, scene.chemistry, f"Race {attempt}", starts_at=START
        )
        question = make_question(scene.engine, scene.chemistry)
        added, cancelled = race(
            scene.engine,
            lambda s, c=competition, q=question: entries.add_question(
                s, scene.manager, c, scene.chemistry, q
            ),
            lambda s, c=competition: cancel_competition(s, scene.manager, c, scene.chemistry, None),
        )
        assert cancelled == "ok"
        assert added in ("ok", "NotChangeable")
        assert len(copies(scene.engine, competition)) == (1 if added == "ok" else 0)


def test_an_addition_racing_a_bank_deletion(scene: Scene, database_url: str) -> None:
    """Spec Assumptions, research R3: the copy is kept and marked, or the addition is not
    found."""
    postgresql_only(database_url)
    for _ in range(3):
        question = make_question(scene.engine, scene.chemistry)
        added, deleted = race(
            scene.engine,
            lambda s, q=question: entries.add_question(
                s, scene.manager, scene.competition, scene.chemistry, q
            ),
            lambda s, q=question: delete_question(s, scene.manager, q),
        )
        assert deleted == "ok"
        with Session(scene.engine) as session:
            views = {
                v.question_id: v
                for v in entries.question_page(session, scene.competition, 1).questions
            }
        if added == "ok":
            assert views[question].deleted_from_bank
        else:
            assert added == "EntryNotFound"
            assert question not in views


def test_an_addition_racing_a_bank_edit_copies_one_version(scene: Scene, database_url: str) -> None:
    """Spec Edge Cases, research R3: the old text and answer, or the new ones, never a mix."""
    postgresql_only(database_url)
    for attempt in range(3):
        question = make_question(scene.engine, scene.chemistry, "Old", "Old answer")
        added, edited = race(
            scene.engine,
            lambda s, q=question: entries.add_question(
                s, scene.manager, scene.competition, scene.chemistry, q
            ),
            lambda s, q=question: update_question(s, scene.manager, q, "New", "New answer"),
        )
        assert (added, edited) == ("ok", "ok"), attempt
        (copy,) = [c for c in copies(scene.engine, scene.competition) if c[0] == question]
        assert copy[1:] in (("Old", "Old answer"), ("New", "New answer"))


# ---------------------------------------------------------------------------------------------
# Logging (FR-048)
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_one_line_with_ids_only(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    question = make_question(scene.engine, scene.chemistry, "Secret question text", "Secret")
    team = make_team(scene.engine, scene.school, "Secret team name")
    kyiv = region_of(scene.engine, scene.school)
    competition, subject = scene.competition, scene.chemistry
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        call(scene.engine, entries.add_question, scene.manager, competition, subject, question)
        call(scene.engine, entries.add_team, scene.manager, competition, subject, kyiv, team)
        call(scene.engine, entries.remove_question, scene.manager, competition, subject, question)
        call(scene.engine, entries.remove_team, scene.manager, competition, subject, team)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Competition")]
    assert lines == [
        f"Competition question added: competition={competition} question={question}",
        f"Competition team added: competition={competition} team={team}",
        f"Competition question removed: competition={competition} question={question}",
        f"Competition team removed: competition={competition} team={team}",
    ]
    for secret in ("Secret", "Spring round", "School No. 5", "manager@example.org"):
        assert secret not in caplog.text


def test_no_ops_and_refusals_log_nothing(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    question = make_question(scene.engine, scene.chemistry)
    team = make_team(scene.engine, scene.school, "Comets")
    add_competition_question(scene.engine, scene.competition, question)
    kyiv = region_of(scene.engine, scene.school)
    args = (scene.competition, scene.chemistry)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        for action, rest, error in [
            (entries.add_question, (question,), AlreadyIn),
            (entries.remove_team, (team,), NotIn),
            (entries.add_team, (kyiv, MISSING), EntryNotFound),
        ]:
            with pytest.raises(error):
                call(scene.engine, action, scene.manager, *args, *rest)
        with pytest.raises(ManageRequired):
            call(scene.engine, entries.add_team, scene.reader, *args, kyiv, team)
    assert [r for r in caplog.records if r.getMessage().startswith("Competition")] == []
