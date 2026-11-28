"""The question bank's CSV files, on the database: counts, export, the replacement and its lock.

See specs/012.11-question-bank-csv/contracts/services.md §2 and research R5, R6. Every test runs
once per engine; the lock tests are PostgreSQL-only, except the one that checks SQLite's own write
lock. No test sleeps: a lock that is not granted in 300 ms fails instead of waiting.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.core.config import AuthSettings
from app.core.i18n import Language, use_language
from app.models import (
    AccessLevel,
    CompetitionQuestion,
    CompetitionResultsFile,
    Question,
    Subject,
    TeamAnswer,
)
from app.services.competition_entries import add_question
from app.services.question_bank_files import (
    Replaced,
    export_file_name,
    export_rows,
    lock_question_bank,
    question_counts,
    replace_questions,
    today_in_kyiv,
)
from app.services.question_csv import MAX_QUESTIONS, QuestionRow
from app.services.questions import (
    create_question,
    delete_question,
    question_page,
    update_question,
)
from app.services.subjects import SubjectInUse, SubjectNotFound, delete_subject
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

MISSING = 999_999
LATER = datetime(2100, 1, 1, 9, 0, tzinfo=UTC)
EARLIER = datetime(2000, 1, 1, 9, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Scene:
    engine: Engine
    manager: int
    """A teacher with **Can manage competitions**."""
    history: int
    physics: int


@pytest.fixture
def scene(engine: Engine, auth_settings: AuthSettings) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    institution = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    manager = make_teacher(
        engine,
        auth_settings,
        email="manager@example.org",
        institutions={institution: AccessLevel.WRITE},
        can_manage=True,
    )
    return Scene(
        engine=engine,
        manager=manager,
        history=make_subject(engine, "History"),
        physics=make_subject(engine, "Physics"),
    )


def bank(engine: Engine, subject_id: int) -> list[tuple[object, ...]]:
    """Every stored question of the subject, deleted ones included, by id."""
    with Session(engine) as session:
        return [
            (q.id, q.text, q.reference_answer, q.is_additional, q.deleted_at, q.updated_at)
            for q in session.exec(
                select(Question).where(Question.subject_id == subject_id).order_by(col(Question.id))
            )
        ]


def listed(engine: Engine, subject_id: int) -> list[tuple[int, str, str, bool]]:
    with Session(engine) as session:
        return [
            (q.id, q.text, q.reference_answer, q.is_additional)
            for q in session.exec(
                select(Question)
                .where(Question.subject_id == subject_id, col(Question.deleted_at).is_(None))
                .order_by(col(Question.id))
            )
        ]


def replace(engine: Engine, subject_id: int, rows: list[QuestionRow]) -> Replaced:
    with Session(engine) as session:
        return replace_questions(session, subject_id, rows)


FILE = [
    QuestionRow("Хто написав «Кобзар»?", "Тарас Шевченко.", False),
    QuestionRow("Second?", "Two.", True),
    QuestionRow("Third?", "Line one\nline two", False),
]


# ---------------------------------------------------------------------------------------------
# Counts and the export (User Stories 1 and 5)
# ---------------------------------------------------------------------------------------------


def test_the_counts(scene: Scene, session: Session) -> None:
    """FR-001: listed questions, additional included, deleted left out; none is missing (0)."""
    make_question(scene.engine, scene.history, "One?")
    make_question(scene.engine, scene.history, "Two?", additional=True)
    make_question(scene.engine, scene.history, "Gone?", deleted=True)
    make_question(scene.engine, scene.physics, "Gone too?", deleted=True)
    assert question_counts(session) == {scene.history: 2}


def test_the_export_rows(scene: Scene, session: Session) -> None:
    """FR-014: every listed question, oldest first, with its mark; nothing of another subject."""
    make_question(scene.engine, scene.history, "B?", "b")
    make_question(scene.engine, scene.history, "Gone?", deleted=True)
    make_question(scene.engine, scene.history, "A?", "a", additional=True)
    make_question(scene.engine, scene.physics, "Other?")
    assert export_rows(session, scene.history) == [
        QuestionRow("B?", "b", False),
        QuestionRow("A?", "a", True),
    ]
    assert export_rows(session, make_subject(scene.engine, "Empty")) == []


@pytest.mark.parametrize(
    ("language", "name", "expected"),
    [
        (Language.EN, "History", "History 2026-11-28 question bank.csv"),
        (Language.UK, "Історія", "Історія 2026-11-28 банк питань.csv"),
        (Language.EN, "A/B: History?", "A_B_ History_ 2026-11-28 question bank.csv"),
    ],
)
def test_the_file_name(language: Language, name: str, expected: str) -> None:
    """FR-016: the subject and the date in the current language; unsafe characters replaced."""
    with use_language(language):
        assert export_file_name(name, date(2026, 11, 28)) == expected


def test_today_is_the_date_in_kyiv(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = datetime(2026, 11, 27, 22, 30, tzinfo=UTC)
    monkeypatch.setattr("app.services.competitions.utc_now", lambda: clock)
    assert today_in_kyiv() == date(2026, 11, 28)


# ---------------------------------------------------------------------------------------------
# The replacement (User Story 2, FR-041–FR-047)
# ---------------------------------------------------------------------------------------------


def test_the_listed_questions_are_soft_deleted_and_the_file_added_in_order(scene: Scene) -> None:
    old = [make_question(scene.engine, scene.history, f"Old {n}?") for n in range(3)]
    gone = make_question(scene.engine, scene.history, "Long gone?", deleted=True)
    before = {row[0]: row for row in bank(scene.engine, scene.history)}
    assert replace(scene.engine, scene.history, FILE) == Replaced(deleted=3, added=3)
    after = {row[0]: row for row in bank(scene.engine, scene.history)}
    for question in old:
        text_, answer, additional, deleted_at, updated_at = after[question][1:]
        assert (text_, answer, additional, updated_at) == (
            before[question][1],
            before[question][2],
            before[question][3],
            before[question][5],
        )
        assert deleted_at is not None
    assert after[gone] == before[gone]
    new = listed(scene.engine, scene.history)
    assert [(t, a, m) for _, t, a, m in new] == [
        (row.text, row.reference_answer, row.is_additional) for row in FILE
    ]
    assert min(question for question, *_ in new) > max(before)


def test_a_thousand_rows_keep_the_file_order(scene: Scene) -> None:
    """Research R5: the ids follow the file on both engines."""
    rows = [QuestionRow(f"Q{n:04}", f"A{n}", n % 7 == 0) for n in range(MAX_QUESTIONS)]
    assert replace(scene.engine, scene.history, rows).added == MAX_QUESTIONS
    assert [t for _, t, _, _ in listed(scene.engine, scene.history)] == [r.text for r in rows]


def test_the_numbers_of_deleted_questions_are_never_used_again(scene: Scene) -> None:
    """FR-042: after a replacement, the next replacement's ids are above every earlier id."""
    replace(scene.engine, scene.history, FILE)
    first = {row[0] for row in bank(scene.engine, scene.history)}
    replace(scene.engine, scene.history, FILE)
    second = [question for question, *_ in listed(scene.engine, scene.history)]
    assert min(second) > max(first)


def test_other_subjects_are_untouched(scene: Scene) -> None:
    make_question(scene.engine, scene.physics, "Physics?")
    make_question(scene.engine, scene.history, "History?")
    before = bank(scene.engine, scene.physics)
    replace(scene.engine, scene.history, FILE)
    assert bank(scene.engine, scene.physics) == before


def test_a_deactivated_subject_is_imported(scene: Scene, session: Session) -> None:
    deactivated = make_subject(scene.engine, "Latin", active=False)
    make_question(scene.engine, deactivated, "Old?")
    assert replace(scene.engine, deactivated, FILE) == Replaced(deleted=1, added=3)


def test_an_unknown_subject_changes_nothing(scene: Scene) -> None:
    make_question(scene.engine, scene.history, "History?")
    before = bank(scene.engine, scene.history)
    with pytest.raises(SubjectNotFound):
        replace(scene.engine, MISSING, FILE)
    assert bank(scene.engine, scene.history) == before
    with Session(scene.engine) as session:
        assert session.exec(select(Question).where(Question.subject_id == MISSING)).all() == []


def test_competitions_keep_their_copies_answers_grades_and_files(scene: Scene) -> None:
    """FR-043: an upcoming competition and a published one hold replaced questions; their copies,
    answers, grades and stored results files are unchanged, and each copy still points at the
    question it came from, now deleted."""
    question = make_question(scene.engine, scene.history, "Old?", "Old answer.")
    upcoming = make_competition(scene.engine, scene.history, "Spring round", starts_at=LATER)
    upcoming_copy = add_competition_question(scene.engine, upcoming, question)
    published = make_competition(
        scene.engine,
        scene.history,
        "Autumn round",
        starts_at=EARLIER,
        stopped=True,
        published=True,
    )
    copy = add_competition_question(scene.engine, published, question)
    team = make_team(scene.engine, make_institution(scene.engine, "School No. 5", "Lviv"))
    add_competition_team(scene.engine, published, team)
    save_team_answer(scene.engine, published, team, copy, "Our answer.")
    grade_answer(scene.engine, published, team, copy, 7)
    store_results_files(scene.engine, published)

    def kept() -> tuple[object, ...]:
        with Session(scene.engine) as session:
            copies = [
                (c.id, c.competition_id, c.question_id, c.text, c.reference_answer)
                for c in session.exec(
                    select(CompetitionQuestion).order_by(col(CompetitionQuestion.id))
                )
            ]
            answers = [(a.text, a.grade) for a in session.exec(select(TeamAnswer))]
            files = sorted(
                (f.language, f.content) for f in session.exec(select(CompetitionResultsFile))
            )
            return copies, answers, files

    before = kept()
    replace(scene.engine, scene.history, FILE)
    assert kept() == before
    with Session(scene.engine) as session:
        stored = session.get(Question, question)
        assert stored is not None and stored.deleted_at is not None
    assert {upcoming_copy, copy} == {c[0] for c in before[0]}


def test_the_subject_still_cannot_be_deleted(scene: Scene) -> None:
    """FR-045."""
    make_question(scene.engine, scene.history, "Old?")
    replace(scene.engine, scene.history, FILE)
    with Session(scene.engine) as session, pytest.raises(SubjectInUse):
        delete_subject(session, scene.history)


def test_one_log_line_with_ids_and_counts_only(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-047."""
    make_question(scene.engine, scene.history, "Old?")
    make_question(scene.engine, scene.history, "Older?")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        replace(scene.engine, scene.history, FILE)
    lines = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert lines == [f"Questions imported: subject={scene.history} deleted=2 added=3"]
    for row in FILE:
        assert row.text not in caplog.text and row.reference_answer not in caplog.text


# ---------------------------------------------------------------------------------------------
# The bank lock (User Story 7, FR-048–FR-050, research R6)
# ---------------------------------------------------------------------------------------------


def postgresql_only(database_url: str) -> None:
    if not database_url.startswith("postgresql"):
        pytest.skip("the table lock is a PostgreSQL behaviour")


def short_lock_timeout(session: Session) -> None:
    """A lock that is not granted in 300 ms fails, instead of waiting: no test sleeps."""
    session.execute(text("SET LOCAL lock_timeout = '300ms'"))


def times_out(engine: Engine, write: Callable[[Session], object]) -> None:
    with Session(engine) as waiting:
        short_lock_timeout(waiting)
        with pytest.raises(OperationalError, match="lock timeout"):
            write(waiting)
        waiting.rollback()


def hold_lock(scene: Scene) -> Session:
    """A session in the middle of an import of History: the subject read `FOR SHARE` and the bank
    locked, not yet committed. Taken after the test has seeded its rows, which would wait too."""
    holding = Session(scene.engine)
    holding.get(Subject, scene.history, with_for_update={"read": True})
    lock_question_bank(holding)
    return holding


def test_every_bank_write_waits_for_an_import(scene: Scene, database_url: str) -> None:
    """FR-048: a teacher's add, edit, mark and deletion, of any subject, another import, and adding
    a question to a competition all wait; nothing changes."""
    postgresql_only(database_url)
    physics_question = make_question(scene.engine, scene.physics, "Physics?")
    upcoming = make_competition(scene.engine, scene.physics, starts_at=LATER)
    before = (bank(scene.engine, scene.history), bank(scene.engine, scene.physics))
    held_lock = hold_lock(scene)
    try:
        times_out(
            scene.engine,
            lambda s: create_question(s, scene.manager, scene.history, "New?", "New."),
        )
        times_out(
            scene.engine,
            lambda s: create_question(s, scene.manager, scene.physics, "New?", "New."),
        )
        times_out(
            scene.engine,
            lambda s: update_question(
                s, scene.manager, physics_question, "Edited?", "Edited.", is_additional=True
            ),
        )
        times_out(scene.engine, lambda s: delete_question(s, scene.manager, physics_question))
        times_out(scene.engine, lambda s: replace_questions(s, scene.physics, FILE))
        times_out(
            scene.engine,
            lambda s: add_question(s, scene.manager, upcoming, scene.physics, physics_question),
        )
    finally:
        held_lock.rollback()
        held_lock.close()
    assert (bank(scene.engine, scene.history), bank(scene.engine, scene.physics)) == before


def test_reading_the_bank_does_not_wait(scene: Scene, database_url: str) -> None:
    postgresql_only(database_url)
    make_question(scene.engine, scene.history, "Readable?")
    held_lock = hold_lock(scene)
    try:
        with Session(scene.engine) as reading:
            short_lock_timeout(reading)
            page = question_page(reading, scene.history, 1, include_additional=True)
            assert [q.text for q in page.questions] == ["Readable?"]
            assert [r.text for r in export_rows(reading, scene.history)] == ["Readable?"]
            assert question_counts(reading) == {scene.history: 1}
    finally:
        held_lock.rollback()
        held_lock.close()


def test_an_import_waits_for_a_teachers_edit(scene: Scene, database_url: str) -> None:
    """A teacher's edit holding its question `FOR UPDATE` makes the import wait."""
    postgresql_only(database_url)
    question = make_question(scene.engine, scene.history, "Old?")
    with Session(scene.engine) as editing:
        editing.get(Question, question, with_for_update=True)
        times_out(scene.engine, lambda s: replace_questions(s, scene.history, FILE))
        editing.rollback()
    assert [t for _, t, _, _ in listed(scene.engine, scene.history)] == ["Old?"]


def test_an_import_into_a_subject_being_deleted(scene: Scene, database_url: str) -> None:
    """Research R6: a deletion holding the subject row makes the import wait, without a
    deadlock; once it commits, the import finds no subject."""
    postgresql_only(database_url)
    empty = make_subject(scene.engine, "Empty")
    with Session(scene.engine) as deleting:
        subject = deleting.get(Subject, empty)
        deleting.delete(subject)
        deleting.flush()
        times_out(scene.engine, lambda s: replace_questions(s, empty, FILE))
        deleting.commit()
    with pytest.raises(SubjectNotFound):
        replace(scene.engine, empty, FILE)


def test_sqlite_writers_wait_for_an_import(scene: Scene, database_url: str) -> None:
    """FR-050 on SQLite: the import's first write takes the database's write lock, so a teacher's
    add waits (here: fails after a 300 ms busy timeout) while reading goes on."""
    if database_url.startswith("postgresql"):
        pytest.skip("SQLite's own write lock")
    make_question(scene.engine, scene.history, "Old?")
    quick = create_engine(
        scene.engine.url, connect_args={"check_same_thread": False, "timeout": 0.3}
    )
    try:
        with Session(scene.engine) as importing:
            importing.execute(
                text("UPDATE questions SET deleted_at = :now WHERE subject_id = :subject"),
                {"now": datetime.now(UTC), "subject": scene.history},
            )
            with Session(quick) as teacher:
                with pytest.raises(OperationalError, match="database is locked"):
                    create_question(teacher, scene.manager, scene.physics, "New?", "New.")
                teacher.rollback()
                page = question_page(teacher, scene.history, 1, include_additional=True)
                assert [q.text for q in page.questions] == ["Old?"]
            importing.rollback()
        with Session(quick) as teacher:
            create_question(teacher, scene.manager, scene.physics, "New?", "New.")
    finally:
        quick.dispose()
    assert [t for _, t, _, _ in listed(scene.engine, scene.physics)] == ["New?"]
