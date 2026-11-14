"""The competitions service: statuses, the offered subjects, pages, visibility, landings, and the
rules of creating, editing, cancelling and finishing, under concurrency.

See specs/012.1-teacher-competitions/contracts/services.md §`app/services/competitions.py` and
research R2, R3, R7, R8, R11, R13; finishing is specs/012.4-finish-and-grade/contracts/services.md
§`competitions` and research R1. Every case runs on both engines. The clock is controlled by
patching `app.services.competitions.utc_now`; no test waits.

- the manager: a real teacher with **Can manage competitions**;
- the reader: a real teacher without it.
"""

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text, update
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

import app.services.competitions as competitions
from app.core.config import AuthSettings
from app.models import AccessLevel, Competition, Subject, TeamAnswer
from app.schemas.names import InvalidName
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    CompetitionView,
    DuplicateCompetitionName,
    Landing,
    ManageRequired,
    NotCancellable,
    NotEditable,
    NotFinishable,
    StartNotInFuture,
    SubjectUnavailable,
    cancel_competition,
    competition_page,
    create_competition,
    finish_competition,
    get_competition,
    landing,
    locate,
    lock_competition,
    offered_subjects,
    parse_status_filter,
    status_of,
    update_competition,
)
from app.services.subjects import count_subject_uses, set_subject_active
from app.services.team_answers import AnswersClosed, save_answers
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    add_competition_question,
    add_competition_team,
    make_competition,
    make_institution,
    make_question,
    make_subject,
    make_teacher,
    make_team,
)
from tests.integration.test_competition_entries_service import postgresql_only, race

NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
MISSING = 999_999


@dataclass(frozen=True)
class Scene:
    manager: int
    reader: int
    chemistry: int
    physics: int
    institution: int
    """Kyiv Polytechnic Institute: Read for the manager, Write for the reader."""


@pytest.fixture
def scene(engine: Engine, auth_settings: AuthSettings) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    manager = make_teacher(
        engine,
        auth_settings,
        email="manager@example.org",
        institutions={institution: AccessLevel.READ},
        can_manage=True,
    )
    reader = make_teacher(
        engine,
        auth_settings,
        email="reader@example.org",
        institutions={institution: AccessLevel.WRITE},
    )
    return Scene(
        manager=manager,
        reader=reader,
        chemistry=make_subject(engine, "Chemistry"),
        physics=make_subject(engine, "Physics"),
        institution=institution,
    )


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


def at(day: int, hour: int = 10, minute: int = 0, month: int = 3) -> datetime:
    return datetime(2027, month, day, hour, minute, tzinfo=UTC)


def subject(engine: Engine, subject_id: int) -> Subject:
    with Session(engine) as session:
        found = session.get(Subject, subject_id)
        assert found is not None
        session.expunge(found)
        return found


def page(
    engine: Engine, subject_id: int, status: CompetitionStatus | None = None, number: int = 1
) -> competitions.CompetitionPage:
    with Session(engine) as session:
        return competition_page(session, subject(engine, subject_id), status, number)


def names(listing: competitions.CompetitionPage) -> list[str]:
    return [c.name for c in listing.competitions]


def row(engine: Engine, competition_id: int) -> tuple[Any, ...]:
    with Session(engine) as session:
        c = session.get(Competition, competition_id)
        assert c is not None
        return (c.name, c.name_key, c.starts_at, c.cancelled_at, c.stopped_at, c.updated_at)


def snapshot(engine: Engine) -> list[tuple[Any, ...]]:
    with Session(engine) as session:
        return [
            (c.id, c.subject_id, c.name, c.starts_at, c.cancelled_at, c.stopped_at, c.updated_at)
            for c in session.exec(select(Competition).order_by(col(Competition.id)))
        ]


def deactivate(engine: Engine, subject_id: int) -> None:
    with Session(engine) as session:
        set_subject_active(session, subject_id, False)


# ---------------------------------------------------------------------------------------------
# Statuses
# ---------------------------------------------------------------------------------------------


def test_status_of_each_status() -> None:
    def competition(**fields: Any) -> Competition:
        return Competition(subject_id=1, name="x", name_key="x", **fields)

    assert status_of(competition(starts_at=at(2)), NOW) is CompetitionStatus.UPCOMING
    assert status_of(competition(starts_at=NOW), NOW) is CompetitionStatus.IN_PROGRESS
    assert status_of(competition(starts_at=at(1, 8)), NOW) is CompetitionStatus.IN_PROGRESS
    assert (
        status_of(competition(starts_at=at(1, 8), stopped_at=NOW), NOW)
        is CompetitionStatus.FINISHED
    )
    assert (
        status_of(competition(starts_at=at(2), cancelled_at=NOW), NOW)
        is CompetitionStatus.CANCELLED
    )
    assert (
        status_of(competition(starts_at=at(1, 8), cancelled_at=NOW), at(5))
        is CompetitionStatus.CANCELLED
    )


def test_status_labels_and_the_filter() -> None:
    assert [s.label for s in CompetitionStatus] == [
        "Upcoming",
        "In progress",
        "Finished",
        "Cancelled",
    ]
    assert parse_status_filter("in_progress") is CompetitionStatus.IN_PROGRESS
    for raw in (None, "", "bogus", "Upcoming", "UPCOMING", "\x00"):
        assert parse_status_filter(raw) is None


def test_a_start_passing_changes_the_status_and_writes_nothing(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 10))
    before = snapshot(engine)
    assert [c.status for c in page(engine, scene.chemistry).competitions] == ["upcoming"]
    clock(timedelta(hours=1))
    assert [c.status for c in page(engine, scene.chemistry).competitions] == ["in_progress"]
    with Session(engine) as session:
        view = get_competition(session, competition, scene.chemistry)
    assert view.status is CompetitionStatus.IN_PROGRESS
    assert snapshot(engine) == before


# ---------------------------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------------------------


def test_latest_start_first_whatever_the_status(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    make_competition(engine, scene.chemistry, "Fifteenth", starts_at=at(15))
    make_competition(engine, scene.chemistry, "First", starts_at=at(1, 8), stopped=True)
    make_competition(engine, scene.chemistry, "Twenty-fifth", starts_at=at(25), cancelled=True)
    assert names(page(engine, scene.chemistry)) == ["Twenty-fifth", "Fifteenth", "First"]


def test_equal_starts_by_name_ignoring_case_then_id(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    for name in ("beta", "Ärger", "Alpha", "apple"):
        make_competition(engine, scene.chemistry, name, starts_at=at(15))
    make_competition(engine, scene.chemistry, "alpha", starts_at=at(15), cancelled=True)
    listed = page(engine, scene.chemistry).competitions
    assert [c.name for c in listed] == ["Alpha", "alpha", "apple", "beta", "Ärger"]
    assert listed[0].id < listed[1].id


def test_pages_of_ten_clamped_to_the_last(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    for day in range(1, 26):
        make_competition(engine, scene.chemistry, f"Day {day:02}", starts_at=at(day, 12))
    sizes = [len(page(engine, scene.chemistry, number=n).competitions) for n in (1, 2, 3)]
    assert sizes == [10, 10, 5]
    second = page(engine, scene.chemistry, number=2)
    assert (second.paging.first_item, second.paging.last_item, second.paging.total) == (11, 20, 25)
    assert names(second)[0] == "Day 15"
    last = page(engine, scene.chemistry, number=99)
    assert (last.paging.number, names(last)[-1]) == (3, "Day 01")
    assert last.subject_total == 25


def test_each_status_filter(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    make_competition(engine, scene.chemistry, "Upcoming one", starts_at=at(20))
    make_competition(engine, scene.chemistry, "Running one", starts_at=at(1, 8))
    make_competition(engine, scene.chemistry, "Finished one", starts_at=at(1, 7), stopped=True)
    make_competition(engine, scene.chemistry, "Cancelled one", starts_at=at(10), cancelled=True)
    make_competition(engine, scene.physics, "Other subject", starts_at=at(20))
    expected = {
        CompetitionStatus.UPCOMING: ["Upcoming one"],
        CompetitionStatus.IN_PROGRESS: ["Running one"],
        CompetitionStatus.FINISHED: ["Finished one"],
        CompetitionStatus.CANCELLED: ["Cancelled one"],
    }
    for status, listed in expected.items():
        filtered = page(engine, scene.chemistry, status)
        assert names(filtered) == listed
        assert filtered.subject_total == 4
    assert len(page(engine, scene.chemistry).competitions) == 4


def test_an_empty_subject(engine: Engine, scene: Scene) -> None:
    empty = page(engine, scene.chemistry)
    assert (empty.competitions, empty.subject_total, empty.paging.number) == ([], 0, 1)


# ---------------------------------------------------------------------------------------------
# Offered subjects and visibility
# ---------------------------------------------------------------------------------------------


def test_offered_subjects(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    astronomy = make_subject(engine, "astronomy")
    biology = make_subject(engine, "Biology", active=False)
    geology = make_subject(engine, "Geology", active=False)
    ecology = make_subject(engine, "Ecology", active=False)
    make_competition(engine, biology, starts_at=at(1, 8), stopped=True)
    make_competition(engine, ecology, "Old", starts_at=at(1, 8), stopped=True)
    make_competition(engine, geology, starts_at=at(20))
    make_competition(engine, geology, "Cancelled", starts_at=at(20), cancelled=True)
    with Session(engine) as session:
        choices = offered_subjects(session)
    assert [s.name for s in choices.active] == ["astronomy", "Chemistry", "Physics"]
    assert [s.name for s in choices.deactivated] == ["Biology", "Ecology"]
    assert choices.is_offered(astronomy) and choices.is_offered(biology)
    assert not choices.is_offered(geology)
    assert not choices.is_offered(MISSING)
    assert choices.get(geology) is None
    assert choices.only is None


def test_the_only_offered_subject(engine: Engine, clock: Callable[[timedelta], datetime]) -> None:
    with Session(engine) as session:
        assert offered_subjects(session).only is None
    biology = make_subject(engine, "Biology", active=False)
    make_competition(engine, biology, starts_at=at(1, 8), stopped=True)
    with Session(engine) as session:
        only = offered_subjects(session).only
    assert only is not None and only.id == biology


def test_a_deactivated_subject_shows_only_its_finished_competitions(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    upcoming = make_competition(engine, scene.chemistry, "Upcoming", starts_at=at(20))
    running = make_competition(engine, scene.chemistry, "Running", starts_at=at(1, 8))
    cancelled = make_competition(
        engine, scene.chemistry, "Cancelled", starts_at=at(20), cancelled=True
    )
    finished = make_competition(
        engine, scene.chemistry, "Finished", starts_at=at(1, 7), stopped=True
    )
    deactivate(engine, scene.chemistry)
    listing = page(engine, scene.chemistry)
    assert (names(listing), listing.subject_total) == (["Finished"], 1)
    with Session(engine) as session:
        for hidden in (upcoming, running, cancelled):
            with pytest.raises(CompetitionNotFound):
                get_competition(session, hidden, scene.chemistry)
        assert get_competition(session, finished, scene.chemistry).status == "finished"


def test_unknown_and_other_subjects_competitions_are_not_found(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(20))
    with Session(engine) as session:
        with pytest.raises(CompetitionNotFound):
            get_competition(session, MISSING, scene.chemistry)
        with pytest.raises(CompetitionNotFound):
            get_competition(session, competition, scene.physics)
        view = get_competition(session, competition, scene.chemistry)
    assert view == CompetitionView(
        competition,
        scene.chemistry,
        "Spring round",
        at(20),
        CompetitionStatus.UPCOMING,
        "spring round",
    )


def test_a_competition_is_a_use_of_its_subject(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    with Session(engine) as session:
        assert count_subject_uses(session, scene.chemistry) == 0
    make_competition(engine, scene.chemistry, "A", starts_at=at(20))
    make_competition(engine, scene.chemistry, "B", starts_at=at(20), cancelled=True)
    make_competition(engine, scene.chemistry, "C", starts_at=at(1, 7), stopped=True)
    with Session(engine) as session:
        assert count_subject_uses(session, scene.chemistry) == 3
        assert count_subject_uses(session, scene.physics) == 0


# ---------------------------------------------------------------------------------------------
# Landing (R13)
# ---------------------------------------------------------------------------------------------


def views(n: int) -> list[CompetitionView]:
    return [
        CompetitionView(i, 1, f"C{i}", at(1), CompetitionStatus.UPCOMING, f"c{i}")
        for i in range(1, n + 1)
    ]


def test_landing_rules() -> None:
    rows = views(12)
    assert landing(rows, 11, None) == Landing(2, 11)
    assert landing(rows, 3, 5) == Landing(1, 3)
    assert landing(rows[:2] + rows[3:], 3, 2) == Landing(1, 4)
    assert landing(rows[:11], 12, 11) == Landing(2, 11)
    assert landing(rows[:10], 11, 10) == Landing(1, 10)
    assert landing([], 1, 0) == Landing(1, None)
    assert landing(rows, MISSING, None) == Landing(1, None)


def test_locate_gives_the_page_of_a_competition(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    ids = [
        make_competition(engine, scene.chemistry, f"Day {d:02}", starts_at=at(d, 12))
        for d in range(1, 26)
    ]
    with Session(engine) as session:
        chemistry = session.get(Subject, scene.chemistry)
        assert chemistry is not None
        assert locate(session, chemistry, None, ids[0]) == Landing(3, ids[0])
        assert locate(session, chemistry, None, ids[-1]) == Landing(1, ids[-1])


# ---------------------------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------------------------


def test_create_stores_the_trimmed_name_and_the_start(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    with Session(engine) as session:
        view = create_competition(
            session, scene.manager, scene.chemistry, "  Spring round ", at(14)
        )
    assert (view.name, view.starts_at, view.status) == ("Spring round", at(14), "upcoming")
    assert row(engine, view.id) == ("Spring round", "spring round", at(14), None, None, NOW)


def test_create_needs_the_setting(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            create_competition(session, scene.reader, scene.chemistry, "Spring", at(14))
        with pytest.raises(ManageRequired):
            create_competition(session, scene.reader, MISSING, "Spring", at(14))
    assert snapshot(engine) == []


def test_create_needs_an_active_subject(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    make_competition(engine, scene.chemistry, "Old", starts_at=at(1, 7), stopped=True)
    deactivate(engine, scene.chemistry)
    before = snapshot(engine)
    with Session(engine) as session:
        for subject_id in (scene.chemistry, MISSING):
            with pytest.raises(SubjectUnavailable):
                create_competition(session, scene.manager, subject_id, "New", at(14))
    assert snapshot(engine) == before


def test_the_start_must_be_in_the_future(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    with Session(engine) as session:
        for start in (NOW, NOW - timedelta(days=1)):
            with pytest.raises(StartNotInFuture):
                create_competition(session, scene.manager, scene.chemistry, "Spring", start)
        assert snapshot(engine) == []
        view = create_competition(
            session, scene.manager, scene.chemistry, "Spring", NOW + timedelta(minutes=1)
        )
    assert view.status is CompetitionStatus.UPCOMING


def test_names_are_checked(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    with Session(engine) as session:
        for raw, message in (
            ("", "Enter a name."),
            ("   ", "Enter a name."),
            ("x" * 201, "The name can be at most 200 characters."),
            (
                "Spring\tround",
                "The name cannot contain tabs, line breaks or other control characters.",
            ),
        ):
            with pytest.raises(InvalidName) as refused:
                create_competition(session, scene.manager, scene.chemistry, raw, at(14))
            assert refused.value.message == message
    assert snapshot(engine) == []


def test_live_names_are_unique_in_a_subject_ignoring_case(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    make_competition(engine, scene.chemistry, "Spring round", starts_at=at(1, 8))
    with Session(engine) as session:
        with pytest.raises(DuplicateCompetitionName) as refused:
            create_competition(session, scene.manager, scene.chemistry, " spring ROUND ", at(14))
        assert refused.value.message == (
            "A competition named “spring ROUND” already exists in this subject."
        )
        create_competition(session, scene.manager, scene.physics, "Spring round", at(14))


def test_a_cancelled_or_finished_name_is_free(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    make_competition(engine, scene.chemistry, "Spring round", starts_at=at(5), cancelled=True)
    make_competition(engine, scene.chemistry, "Autumn round", starts_at=at(1, 7), stopped=True)
    with Session(engine) as session:
        create_competition(session, scene.manager, scene.chemistry, "Spring round", at(14))
        create_competition(session, scene.manager, scene.chemistry, "autumn round", at(14))
    assert len(snapshot(engine)) == 4


def test_a_name_race_is_caught_by_the_index(
    engine: Engine,
    scene: Scene,
    clock: Callable[[timedelta], datetime],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US4-11, SC-004: the lookup misses the other live competition, as if it committed just
    after; the partial unique index refuses the insert, reported as the same duplicate."""
    make_competition(engine, scene.chemistry, "Spring round", starts_at=at(20))
    before = snapshot(engine)
    monkeypatch.setattr(competitions, "_find_live", lambda *args: None)
    with Session(engine) as session:
        with pytest.raises(DuplicateCompetitionName):
            create_competition(session, scene.manager, scene.chemistry, "SPRING ROUND", at(14))
        assert session.exec(select(Competition)).all() != []
    assert snapshot(engine) == before


# ---------------------------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------------------------


def test_update_changes_the_name_and_the_start(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(14))
    later = clock(timedelta(minutes=5))
    with Session(engine) as session:
        view = update_competition(
            session, scene.manager, competition, scene.chemistry, "Spring final", at(20)
        )
    assert (view.name, view.starts_at) == ("Spring final", at(20))
    assert row(engine, competition) == ("Spring final", "spring final", at(20), None, None, later)


def test_its_own_name_and_a_change_of_case_are_valid(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(14))
    with Session(engine) as session:
        update_competition(
            session, scene.manager, competition, scene.chemistry, "Spring round", at(15)
        )
        update_competition(
            session, scene.manager, competition, scene.chemistry, "SPRING round", at(15)
        )
    assert row(engine, competition)[0] == "SPRING round"


def test_an_unchanged_save_writes_nothing(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(14))
    before = row(engine, competition)
    clock(timedelta(minutes=5))
    with Session(engine) as session:
        update_competition(
            session, scene.manager, competition, scene.chemistry, " Spring round ", at(14)
        )
    assert row(engine, competition) == before


def test_update_refusals(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    upcoming = make_competition(engine, scene.chemistry, "Upcoming", starts_at=at(14))
    make_competition(engine, scene.chemistry, "Taken", starts_at=at(15))
    running = make_competition(engine, scene.chemistry, "Running", starts_at=at(1, 8))
    cancelled = make_competition(
        engine, scene.chemistry, "Cancelled", starts_at=at(14), cancelled=True
    )
    finished = make_competition(
        engine, scene.chemistry, "Finished", starts_at=at(1, 7), stopped=True
    )
    before = snapshot(engine)
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            update_competition(session, scene.reader, upcoming, scene.chemistry, "New", at(14))
        with pytest.raises(CompetitionNotFound):
            update_competition(session, scene.manager, upcoming, scene.physics, "New", at(14))
        for competition, status in (
            (running, CompetitionStatus.IN_PROGRESS),
            (cancelled, CompetitionStatus.CANCELLED),
            (finished, CompetitionStatus.FINISHED),
        ):
            with pytest.raises(NotEditable) as refused:
                update_competition(
                    session, scene.manager, competition, scene.chemistry, "New", at(14)
                )
            assert refused.value.status is status
        with pytest.raises(StartNotInFuture):
            update_competition(session, scene.manager, upcoming, scene.chemistry, "New", NOW)
        with pytest.raises(DuplicateCompetitionName):
            update_competition(session, scene.manager, upcoming, scene.chemistry, "taken", at(14))
        with pytest.raises(InvalidName):
            update_competition(session, scene.manager, upcoming, scene.chemistry, "", at(14))
    assert snapshot(engine) == before


def test_after_the_subject_is_deactivated_only_finished_ones_are_found(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    upcoming = make_competition(engine, scene.chemistry, "Upcoming", starts_at=at(14))
    finished = make_competition(
        engine, scene.chemistry, "Finished", starts_at=at(1, 7), stopped=True
    )
    deactivate(engine, scene.chemistry)
    with Session(engine) as session:
        with pytest.raises(CompetitionNotFound):
            update_competition(session, scene.manager, upcoming, scene.chemistry, "New", at(14))
        with pytest.raises(NotEditable) as refused:
            update_competition(session, scene.manager, finished, scene.chemistry, "New", at(14))
        assert refused.value.status is CompetitionStatus.FINISHED
        with pytest.raises(CompetitionNotFound):
            cancel_competition(session, scene.manager, upcoming, scene.chemistry, None)
        with pytest.raises(NotCancellable):
            cancel_competition(session, scene.manager, finished, scene.chemistry, None)


@pytest.fixture
def upcoming_once(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`status_of` answers Upcoming on its first call only, then the real function: the check
    under lock passes as if the other request had not committed yet."""
    real = competitions.status_of
    calls = [0]

    def fake(row: Competition, now: datetime) -> CompetitionStatus:
        calls[0] += 1
        return CompetitionStatus.UPCOMING if calls[0] == 1 else real(row, now)

    monkeypatch.setattr(competitions, "status_of", fake)
    yield
    assert calls[0] >= 2


def cancel_directly(engine: Engine, competition_id: int, moment: datetime) -> None:
    with Session(engine) as session:
        session.execute(
            update(Competition)
            .where(col(Competition.id) == competition_id)
            .values(cancelled_at=moment)
        )
        session.commit()


def test_a_lost_edit_race_is_refused(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime], upcoming_once: None
) -> None:
    """FR-032, SC-005: the competition was cancelled by another teacher after the check; the
    conditional update matches no row, and nothing changes."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(14))
    cancel_directly(engine, competition, NOW)
    before = row(engine, competition)
    with Session(engine) as session:
        with pytest.raises(NotEditable) as refused:
            update_competition(session, scene.manager, competition, scene.chemistry, "New", at(20))
        assert refused.value.status is CompetitionStatus.CANCELLED
        assert session.exec(select(Competition)).all() != []
    assert row(engine, competition) == before


# ---------------------------------------------------------------------------------------------
# Cancelling
# ---------------------------------------------------------------------------------------------


def test_cancel_sets_only_cancelled_at(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(14))
    name, key, starts_at, _, _, updated_at = row(engine, competition)
    later = clock(timedelta(minutes=5))
    with Session(engine) as session:
        assert cancel_competition(session, scene.manager, competition, scene.chemistry, None) == (
            Landing(1, competition)
        )
    assert row(engine, competition) == (name, key, starts_at, later, None, updated_at)
    with Session(engine) as session:
        with pytest.raises(NotCancellable) as refused:
            cancel_competition(session, scene.manager, competition, scene.chemistry, None)
    assert refused.value.status is CompetitionStatus.CANCELLED
    assert row(engine, competition)[3] == later


def test_cancel_an_in_progress_competition_and_refusals(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    running = make_competition(engine, scene.chemistry, "Running", starts_at=at(1, 8))
    finished = make_competition(
        engine, scene.chemistry, "Finished", starts_at=at(1, 7), stopped=True
    )
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            cancel_competition(session, scene.reader, running, scene.chemistry, None)
        with pytest.raises(CompetitionNotFound):
            cancel_competition(session, scene.manager, running, scene.physics, None)
        with pytest.raises(NotCancellable) as refused:
            cancel_competition(session, scene.manager, finished, scene.chemistry, None)
        assert refused.value.status is CompetitionStatus.FINISHED
        cancel_competition(session, scene.manager, running, scene.chemistry, None)
    assert row(engine, running)[3] == NOW


def test_an_upcoming_competition_whose_start_passed_is_cancelled(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """FR-035: the confirmation was opened before the start, sent after it."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 10))
    clock(timedelta(hours=2))
    with Session(engine) as session:
        cancel_competition(session, scene.manager, competition, scene.chemistry, None)
    clock(timedelta(days=30))
    assert [c.status for c in page(engine, scene.chemistry).competitions] == ["cancelled"]


def test_a_lost_cancel_race_is_refused(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime], upcoming_once: None
) -> None:
    """US5-7: another teacher cancelled first; the first `cancelled_at` is kept."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(14))
    first = NOW - timedelta(minutes=1)
    cancel_directly(engine, competition, first)
    with Session(engine) as session:
        with pytest.raises(NotCancellable) as refused:
            cancel_competition(session, scene.manager, competition, scene.chemistry, None)
        assert refused.value.status is CompetitionStatus.CANCELLED
    assert row(engine, competition)[3] == first


def test_cancel_landings_under_a_filter(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """Research R13: the row that took its place, the row before it, the previous page, the
    empty state; with All or Cancelled the competition itself."""
    ids = [
        make_competition(engine, scene.chemistry, f"Day {d:02}", starts_at=at(d, 12))
        for d in range(2, 13)
    ]  # 11 upcoming, listed Day 12 … Day 02; ids[0] is Day 02, last.
    upcoming = CompetitionStatus.UPCOMING

    def cancel(competition: int, status: CompetitionStatus | None) -> Landing:
        with Session(engine) as session:
            return cancel_competition(session, scene.manager, competition, scene.chemistry, status)

    assert cancel(ids[5], upcoming) == Landing(1, ids[4])
    assert cancel(ids[0], upcoming) == Landing(1, ids[1])
    assert cancel(ids[1], None) == Landing(1, ids[1])
    assert cancel(ids[2], CompetitionStatus.CANCELLED) == Landing(1, ids[2])
    for competition in ids[3:5] + ids[6:-1]:
        cancel(competition, None)
    assert cancel(ids[-1], upcoming) == Landing(1, None)


def test_cancel_landing_on_the_previous_page(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    ids = [
        make_competition(engine, scene.chemistry, f"Day {d:02}", starts_at=at(d, 12))
        for d in range(2, 13)
    ]
    with Session(engine) as session:
        landed = cancel_competition(
            session, scene.manager, ids[0], scene.chemistry, CompetitionStatus.UPCOMING
        )
    assert landed == Landing(1, ids[1])


# ---------------------------------------------------------------------------------------------
# Logging (FR-046)
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_ids_only(
    engine: Engine,
    scene: Scene,
    clock: Callable[[timedelta], datetime],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        competition = create_competition(
            session, scene.manager, scene.chemistry, "Secret round", at(14)
        ).id
        update_competition(session, scene.manager, competition, scene.chemistry, "Secret 2", at(15))
        update_competition(session, scene.manager, competition, scene.chemistry, "Secret 2", at(15))
        for refused in (
            lambda: create_competition(session, scene.reader, scene.chemistry, "Secret 3", at(14)),
            lambda: create_competition(session, scene.manager, scene.chemistry, "secret 2", at(14)),
            lambda: update_competition(
                session, scene.manager, competition, scene.chemistry, "", at(14)
            ),
        ):
            with pytest.raises((ManageRequired, DuplicateCompetitionName, InvalidName)):
                refused()
        cancel_competition(session, scene.manager, competition, scene.chemistry, None)
        with pytest.raises(NotCancellable):
            cancel_competition(session, scene.manager, competition, scene.chemistry, None)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [
        f"Competition created: id={competition} subject={scene.chemistry}",
        f"Competition updated: id={competition}",
        f"Competition cancelled: id={competition}",
    ]
    assert not any("Secret" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------------------------
# Milestone 12.3: the share lock of a save of answers (specs/012.3-team-answers research R3)
# ---------------------------------------------------------------------------------------------


def test_the_share_lock_finds_what_the_update_lock_finds(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    competition = make_competition(engine, scene.chemistry, starts_at=at(20))
    hidden = make_competition(engine, scene.physics, starts_at=at(20))
    deactivate(engine, scene.physics)
    for share in (False, True):
        with Session(engine) as session:
            row, found = lock_competition(session, competition, scene.chemistry, share=share)
            assert (row.id, found.id) == (competition, scene.chemistry)
            session.rollback()
            for competition_id, subject_id in (
                (MISSING, scene.chemistry),
                (competition, scene.physics),
                (hidden, scene.physics),
            ):
                with pytest.raises(CompetitionNotFound):
                    lock_competition(session, competition_id, subject_id, share=share)
                assert session.exec(select(Competition.id)).all()


def short_lock_timeout(session: Session) -> None:
    """A lock that is not granted in 300 ms fails, instead of waiting: no test sleeps."""
    session.execute(text("SET LOCAL lock_timeout = '300ms'"))


def test_share_locks_do_not_wait_for_each_other_but_cancelling_waits(
    engine: Engine,
    database_url: str,
    scene: Scene,
    clock: Callable[[timedelta], datetime],
) -> None:
    """Two saves of answers of one competition hold its share lock together; a cancellation
    waits until both have ended, and then goes through."""
    if not database_url.startswith("postgresql"):
        pytest.skip("row locks are a PostgreSQL behaviour")
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 8))
    with Session(engine) as first, Session(engine) as second:
        lock_competition(first, competition, scene.chemistry, share=True)
        short_lock_timeout(second)
        lock_competition(second, competition, scene.chemistry, share=True)
        with Session(engine) as cancelling:
            short_lock_timeout(cancelling)
            with pytest.raises(OperationalError, match="lock timeout"):
                cancel_competition(cancelling, scene.manager, competition, scene.chemistry, None)
        first.rollback()
        with Session(engine) as cancelling:
            short_lock_timeout(cancelling)
            with pytest.raises(OperationalError, match="lock timeout"):
                cancel_competition(cancelling, scene.manager, competition, scene.chemistry, None)
        second.rollback()
    with Session(engine) as cancelling:
        cancel_competition(cancelling, scene.manager, competition, scene.chemistry, None)
    with Session(engine) as session:
        row = session.get(Competition, competition)
        assert row is not None and row.cancelled_at is not None


# ---------------------------------------------------------------------------------------------
# Milestone 12.4: finishing (specs/012.4-finish-and-grade contracts/services.md §competitions,
# research R1)
# ---------------------------------------------------------------------------------------------


def finish(
    engine: Engine,
    teacher: int,
    competition: int,
    subject_id: int,
    status: CompetitionStatus | None = None,
) -> Landing:
    with Session(engine) as session:
        return finish_competition(session, teacher, competition, subject_id, status)


def test_finish_sets_only_stopped_at(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US1-3, FR-008: the moment of finishing, and nothing else."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 8))
    name, key, starts_at, _, _, updated_at = row(engine, competition)
    later = clock(timedelta(minutes=5))
    assert finish(engine, scene.manager, competition, scene.chemistry) == Landing(1, competition)
    assert row(engine, competition) == (name, key, starts_at, None, later, updated_at)
    assert [c.status for c in page(engine, scene.chemistry).competitions] == ["finished"]


def test_finish_landings_under_a_filter(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US1-4, research R13: under All and Finished the competition itself; under In progress the
    row that took its place, the row before it, and the empty state."""
    ids = [
        make_competition(engine, scene.chemistry, f"Feb {d:02}", starts_at=at(d, 12, month=2))
        for d in range(2, 9)
    ]  # 7 in progress, listed Feb 08 … Feb 02; ids[0] is Feb 02, last.
    in_progress = CompetitionStatus.IN_PROGRESS
    assert finish(engine, scene.manager, ids[3], scene.chemistry, in_progress) == (
        Landing(1, ids[2])
    )
    assert finish(engine, scene.manager, ids[0], scene.chemistry, in_progress) == (
        Landing(1, ids[1])
    )
    assert finish(engine, scene.manager, ids[1], scene.chemistry, None) == Landing(1, ids[1])
    assert finish(engine, scene.manager, ids[2], scene.chemistry, CompetitionStatus.FINISHED) == (
        Landing(1, ids[2])
    )
    for competition in ids[4:-1]:
        finish(engine, scene.manager, competition, scene.chemistry)
    assert finish(engine, scene.manager, ids[-1], scene.chemistry, in_progress) == (
        Landing(1, None)
    )


def test_finish_landing_on_the_previous_page(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US1-4: 11 in progress; finishing the 11th, alone on page 2, lands on page 1's last row."""
    ids = [
        make_competition(engine, scene.chemistry, f"Feb {d:02}", starts_at=at(d, 12, month=2))
        for d in range(2, 13)
    ]  # ids[0] is Feb 02, the 11th row, alone on page 2.
    assert finish(
        engine, scene.manager, ids[0], scene.chemistry, CompetitionStatus.IN_PROGRESS
    ) == (Landing(1, ids[1]))


def test_finish_needs_the_setting_and_an_in_progress_competition(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US2-1–US2-3, FR-002, FR-012: the reader is refused; an upcoming, a cancelled and a finished
    competition are refused with their status; nothing changes."""
    running = make_competition(engine, scene.chemistry, "Running", starts_at=at(1, 8))
    upcoming = make_competition(engine, scene.chemistry, "Upcoming", starts_at=at(14))
    cancelled = make_competition(
        engine, scene.chemistry, "Cancelled", starts_at=at(1, 7), cancelled=True
    )
    finished = make_competition(
        engine, scene.chemistry, "Finished", starts_at=at(1, 6), stopped=True
    )
    before = snapshot(engine)
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            finish_competition(session, scene.reader, running, scene.chemistry, None)
        with pytest.raises(CompetitionNotFound):
            finish_competition(session, scene.manager, running, scene.physics, None)
        with pytest.raises(CompetitionNotFound):
            finish_competition(session, scene.manager, MISSING, scene.chemistry, None)
        for competition, status in (
            (upcoming, CompetitionStatus.UPCOMING),
            (cancelled, CompetitionStatus.CANCELLED),
            (finished, CompetitionStatus.FINISHED),
        ):
            with pytest.raises(NotFinishable) as refused:
                finish_competition(session, scene.manager, competition, scene.chemistry, None)
            assert refused.value.status is status
            assert session.exec(select(Competition.id)).all()
    assert snapshot(engine) == before


def test_an_upcoming_competition_is_finished_once_its_start_passed(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US2-4, FR-012: refused before the start, finished after it with the clock moved."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 10))
    with pytest.raises(NotFinishable):
        finish(engine, scene.manager, competition, scene.chemistry)
    later = clock(timedelta(hours=2))
    finish(engine, scene.manager, competition, scene.chemistry)
    assert row(engine, competition)[4] == later


def test_a_finished_competition_is_final(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """FR-009, FR-010: no longer cancelled or edited, and its name is free again."""
    competition = make_competition(engine, scene.chemistry, "Spring round", starts_at=at(1, 8))
    finish(engine, scene.manager, competition, scene.chemistry)
    with Session(engine) as session:
        with pytest.raises(NotCancellable) as not_cancelled:
            cancel_competition(session, scene.manager, competition, scene.chemistry, None)
        assert not_cancelled.value.status is CompetitionStatus.FINISHED
        with pytest.raises(NotEditable) as not_edited:
            update_competition(
                session, scene.manager, competition, scene.chemistry, "Spring round", at(20)
            )
        assert not_edited.value.status is CompetitionStatus.FINISHED
        again = create_competition(session, scene.manager, scene.chemistry, "spring ROUND", at(20))
    assert again.name == "spring ROUND"
    assert row(engine, competition)[3] is None


def test_a_lost_finish_race_is_refused(
    engine: Engine,
    scene: Scene,
    clock: Callable[[timedelta], datetime],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Research R1: the status read under the lock says In progress, but the row was cancelled
    first; the conditional update matches nothing and the re-read status is reported."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 8))
    first = NOW - timedelta(minutes=1)
    real_status_of = competitions.status_of
    calls = [0]

    def in_progress_once(row_: Competition, now: datetime) -> CompetitionStatus:
        calls[0] += 1
        if calls[0] == 1:
            return CompetitionStatus.IN_PROGRESS
        return real_status_of(row_, now)

    cancel_directly(engine, competition, first)
    monkeypatch.setattr("app.services.competitions.status_of", in_progress_once)
    with pytest.raises(NotFinishable) as refused:
        finish(engine, scene.manager, competition, scene.chemistry)
    assert refused.value.status is CompetitionStatus.CANCELLED
    assert row(engine, competition)[3:5] == (first, None)


def test_finishing_logs_the_id_only(
    engine: Engine,
    scene: Scene,
    clock: Callable[[timedelta], datetime],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-045: one line with the id; a refusal logs nothing."""
    competition = make_competition(engine, scene.chemistry, "Secret round", starts_at=at(1, 8))
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with pytest.raises(ManageRequired):
            finish(engine, scene.reader, competition, scene.chemistry)
        finish(engine, scene.manager, competition, scene.chemistry)
        with pytest.raises(NotFinishable):
            finish(engine, scene.manager, competition, scene.chemistry)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [f"Competition finished: id={competition}"]
    assert not any("Secret" in r.getMessage() for r in caplog.records)


def test_two_finishes_at_the_same_moment_finish_once(
    engine: Engine, database_url: str, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US2-5, FR-013: exactly one finish changes the competition; the other is refused as
    already finished."""
    postgresql_only(database_url)
    for n in range(3):
        competition = make_competition(engine, scene.chemistry, f"Race {n}", starts_at=at(1, 8))
        outcomes = race(
            engine,
            lambda session, c=competition: finish_competition(
                session, scene.manager, c, scene.chemistry, None
            ),
            lambda session, c=competition: finish_competition(
                session, scene.manager, c, scene.chemistry, None
            ),
        )
        assert sorted(outcomes) == ["NotFinishable", "ok"]
        assert row(engine, competition)[4] == NOW


def test_a_finish_and_a_cancel_at_the_same_moment(
    engine: Engine, database_url: str, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US2-6, FR-013: exactly one succeeds; the competition is either finished or cancelled,
    never both (`one_end`)."""
    postgresql_only(database_url)
    for n in range(3):
        competition = make_competition(engine, scene.chemistry, f"Race {n}", starts_at=at(1, 8))
        outcomes = race(
            engine,
            lambda session, c=competition: finish_competition(
                session, scene.manager, c, scene.chemistry, None
            ),
            lambda session, c=competition: cancel_competition(
                session, scene.manager, c, scene.chemistry, None
            ),
        )
        assert outcomes in (["ok", "NotCancellable"], ["NotFinishable", "ok"])
        cancelled_at, stopped_at = row(engine, competition)[3:5]
        assert (cancelled_at is None) != (stopped_at is None)


def test_a_finish_waits_for_an_answer_save_in_progress(
    engine: Engine, database_url: str, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """Research R1, FR-011: a save of answers holds the competition's share lock; the finish
    waits until it ends, then goes through."""
    postgresql_only(database_url)
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 8))
    with Session(engine) as saving:
        lock_competition(saving, competition, scene.chemistry, share=True)
        with Session(engine) as finishing:
            short_lock_timeout(finishing)
            with pytest.raises(OperationalError, match="lock timeout"):
                finish_competition(finishing, scene.manager, competition, scene.chemistry, None)
        saving.commit()
    finish(engine, scene.manager, competition, scene.chemistry)
    assert row(engine, competition)[4] == NOW


def test_an_answer_save_after_the_finish_is_refused(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """FR-011, US8: once the finish committed, a save sees Finished and stores nothing."""
    competition = make_competition(engine, scene.chemistry, starts_at=at(1, 8))
    copy = add_competition_question(
        engine, competition, make_question(engine, scene.chemistry, "Salt?")
    )
    team = make_team(engine, scene.institution, "Comets")
    add_competition_team(engine, competition, team)
    finish(engine, scene.manager, competition, scene.chemistry)
    with Session(engine) as session:
        with pytest.raises(AnswersClosed) as refused:
            save_answers(session, scene.reader, competition, scene.chemistry, team, {copy: "NaCl"})
        assert refused.value.status is CompetitionStatus.FINISHED
        assert session.exec(select(TeamAnswer)).all() == []
