"""The question bank's service: paging, the not-found rules, and adding, editing and deleting.

See specs/011-question-bank/contracts/services.md §`app/services/questions.py` and research R1,
R2, R7, R8 (US1, US3, US4, US5, SC-003). The milestone 3 cases (unscoped writes, the hard
delete, the home page list) were retired with that code. Every case runs on both engines. The
clock is controlled by patching `app.services.questions.utc_now`.

- the manager: a real teacher with **Can manage competitions**;
- the reader: a real teacher without it;
- the cast teacher: holds the role with no profile row, so has no setting either.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.core.config import AuthSettings
from app.models import AccessLevel, Question, Role, User
from app.services.paging import PAGE_SIZE
from app.services.questions import (
    Landing,
    ManageRequired,
    QuestionNotFound,
    QuestionView,
    SubjectUnavailable,
    create_question,
    delete_question,
    get_active_subject,
    get_question,
    question_page,
    update_question,
)
from app.services.subjects import set_subject_active
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    TEACHER_EMAIL,
    make_institution,
    make_question,
    make_subject,
    make_teacher,
    seed_roles_directly,
)

MISSING = 999_999


@dataclass(frozen=True)
class Scene:
    manager: int
    reader: int
    cast: int
    maths: int
    physics: int
    chemistry: int
    """Deactivated."""


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
    seed_roles_directly(engine, {TEACHER_EMAIL: [Role.TEACHER]})
    with Session(engine) as session:
        cast = session.exec(select(User).where(User.email == TEACHER_EMAIL)).one().id
    assert cast is not None
    return Scene(
        manager=manager,
        reader=reader,
        cast=cast,
        maths=make_subject(engine, "Mathematics"),
        physics=make_subject(engine, "Physics"),
        chemistry=make_subject(engine, "Chemistry", active=False),
    )


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    """A controllable `utc_now`; call it to advance, and it returns the new time."""
    now = [datetime(2100, 1, 1, 12, 0, tzinfo=UTC)]
    monkeypatch.setattr("app.services.questions.utc_now", lambda: now[0])

    def advance(by: timedelta = timedelta(0)) -> datetime:
        now[0] += by
        return now[0]

    return advance


def rows(engine: Engine) -> list[tuple[Any, ...]]:
    """Every stored question, every column, by id."""
    with Session(engine) as session:
        return [
            (
                q.id,
                q.subject_id,
                q.text,
                q.reference_answer,
                q.created_at,
                q.updated_at,
                q.deleted_at,
            )
            for q in session.exec(select(Question).order_by(col(Question.id)))
        ]


def seed(engine: Engine, subject_id: int, n: int) -> list[int]:
    """`n` questions of the subject, in creation order ("Q0", "Q1", …); their ids."""
    return [make_question(engine, subject_id, f"Q{i}", f"A{i}") for i in range(n)]


# ---------------------------------------------------------------------------------------------
# Reading: one page, and the not-found rules
# ---------------------------------------------------------------------------------------------


def test_a_page_lists_only_the_subjects_listed_questions_newest_first(
    engine: Engine, scene: Scene
) -> None:
    """US2-8: 25 questions give pages of 10, 10 and 5; another subject's and deleted ones never
    appear."""
    ids = seed(engine, scene.maths, 25)
    seed(engine, scene.physics, 3)
    make_question(engine, scene.maths, "gone", deleted=True)
    newest_first = ids[::-1]
    with Session(engine) as session:
        pages = [
            question_page(session, scene.maths, page, include_additional=True) for page in (1, 2, 3)
        ]
    assert [[q.id for q in p.questions] for p in pages] == [
        newest_first[:10],
        newest_first[10:20],
        newest_first[20:],
    ]
    assert all(p.paging.total == 25 and p.paging.last == 3 for p in pages)
    assert pages[0].questions[0] == QuestionView(ids[24], scene.maths, "Q24", "A24", False)


@pytest.mark.parametrize(("asked", "shown"), [(0, 1), (-5, 1), (99, 3)])
def test_a_page_out_of_range_is_clamped(
    engine: Engine, scene: Scene, asked: int, shown: int
) -> None:
    seed(engine, scene.maths, 25)
    with Session(engine) as session:
        assert (
            question_page(session, scene.maths, asked, include_additional=True).paging.number
            == shown
        )


def test_a_subject_without_listed_questions_has_an_empty_page(engine: Engine, scene: Scene) -> None:
    make_question(engine, scene.maths, deleted=True)
    with Session(engine) as session:
        page = question_page(session, scene.maths, 1, include_additional=True)
    assert page.questions == []
    assert (page.paging.total, page.paging.number, page.paging.last) == (0, 1, 1)


@pytest.mark.parametrize("lock", [False, True], ids=["plain", "locked"])
def test_only_an_active_subject_is_available(engine: Engine, scene: Scene, lock: bool) -> None:
    with Session(engine) as session:
        assert get_active_subject(session, scene.maths, lock=lock).name == "Mathematics"
        for subject_id in (MISSING, scene.chemistry):
            with pytest.raises(SubjectUnavailable):
                get_active_subject(session, subject_id, lock=lock)


@pytest.mark.parametrize("lock", [False, True], ids=["plain", "locked"])
def test_a_question_is_found_only_while_listed(engine: Engine, scene: Scene, lock: bool) -> None:
    """FR-038: unknown, deleted, and of a deactivated subject are all "not found"."""
    listed = make_question(engine, scene.maths, "Why?", "Because.")
    deleted = make_question(engine, scene.maths, deleted=True)
    hidden = make_question(engine, scene.chemistry)
    with Session(engine) as session:
        view, subject = get_question(session, listed, lock=lock)
        assert view == QuestionView(listed, scene.maths, "Why?", "Because.", False)
        assert subject.id == scene.maths
        for question_id in (MISSING, deleted, hidden):
            with pytest.raises(QuestionNotFound):
                get_question(session, question_id, lock=lock)


# ---------------------------------------------------------------------------------------------
# Adding
# ---------------------------------------------------------------------------------------------


def test_a_question_is_stored_in_its_subject_with_both_timestamps(
    engine: Engine, scene: Scene, clock: Callable[..., datetime]
) -> None:
    now = clock()
    with Session(engine) as session:
        view = create_question(session, scene.manager, scene.physics, "Why?", "Because.")
    assert view == QuestionView(view.id, scene.physics, "Why?", "Because.", False)
    assert rows(engine) == [(view.id, scene.physics, "Why?", "Because.", now, now, None)]


def test_numbers_increase_and_are_never_reused(engine: Engine, scene: Scene) -> None:
    """FR-003: a question added after the newest one was deleted gets a new number."""
    with Session(engine) as session:
        first = create_question(session, scene.manager, scene.maths, "One", "1").id
        second = create_question(session, scene.manager, scene.maths, "Two", "2").id
        assert second > first
        delete_question(session, scene.manager, second)
        third = create_question(session, scene.manager, scene.maths, "Three", "3").id
    assert third > second


def test_a_duplicate_text_is_accepted(engine: Engine, scene: Scene) -> None:
    """US1-6."""
    with Session(engine) as session:
        create_question(session, scene.manager, scene.maths, "Same?", "Yes.")
        create_question(session, scene.manager, scene.maths, "Same?", "Yes.")
        assert [
            q.text
            for q in question_page(session, scene.maths, 1, include_additional=True).questions
        ] == [
            "Same?",
            "Same?",
        ]


@pytest.mark.parametrize("who", ["reader", "cast"])
def test_adding_needs_the_setting(engine: Engine, scene: Scene, who: str) -> None:
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            create_question(session, getattr(scene, who), scene.maths, "Why?", "Because.")
    assert rows(engine) == []


@pytest.mark.parametrize("subject", ["missing", "chemistry"])
def test_adding_needs_an_active_subject(engine: Engine, scene: Scene, subject: str) -> None:
    subject_id = MISSING if subject == "missing" else scene.chemistry
    with Session(engine) as session:
        with pytest.raises(SubjectUnavailable):
            create_question(session, scene.manager, subject_id, "Why?", "Because.")
    assert rows(engine) == []


# ---------------------------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------------------------


def test_an_edit_replaces_both_fields_and_keeps_the_number_and_subject(
    engine: Engine, scene: Scene, clock: Callable[..., datetime]
) -> None:
    created = clock()
    with Session(engine) as session:
        question = create_question(session, scene.manager, scene.maths, "Old?", "Old.").id
    edited = clock(timedelta(hours=1))
    with Session(engine) as session:
        view = update_question(
            session, scene.manager, question, "New?", "New.", is_additional=False
        )
    assert view == QuestionView(question, scene.maths, "New?", "New.", False)
    assert rows(engine) == [(question, scene.maths, "New?", "New.", created, edited, None)]


def test_an_edit_that_changes_nothing_keeps_the_time(
    engine: Engine, scene: Scene, clock: Callable[..., datetime]
) -> None:
    with Session(engine) as session:
        question = create_question(session, scene.manager, scene.maths, "Same?", "Same.").id
    before = rows(engine)
    clock(timedelta(hours=1))
    with Session(engine) as session:
        update_question(session, scene.manager, question, "Same?", "Same.", is_additional=False)
    assert rows(engine) == before


@pytest.mark.parametrize("who", ["reader", "cast"])
def test_editing_needs_the_setting(engine: Engine, scene: Scene, who: str) -> None:
    question = make_question(engine, scene.maths)
    before = rows(engine)
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            update_question(
                session, getattr(scene, who), question, "New?", "New.", is_additional=False
            )
    assert rows(engine) == before


@pytest.mark.parametrize("case", ["missing", "deleted", "deactivated-subject"])
def test_editing_needs_a_listed_question(engine: Engine, scene: Scene, case: str) -> None:
    question = {
        "missing": MISSING,
        "deleted": make_question(engine, scene.maths, deleted=True),
        "deactivated-subject": make_question(engine, scene.chemistry),
    }[case]
    before = rows(engine)
    with Session(engine) as session:
        with pytest.raises(QuestionNotFound):
            update_question(session, scene.manager, question, "New?", "New.", is_additional=False)
    assert rows(engine) == before


# ---------------------------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------------------------


def test_a_deleted_question_stays_stored_unchanged(
    engine: Engine, scene: Scene, clock: Callable[..., datetime]
) -> None:
    """SC-003: only `deleted_at` changes; the question is never listed or found again."""
    question = make_question(engine, scene.maths, "Why?", "Because.")
    (before,) = rows(engine)
    deleted = clock(timedelta(days=1))
    with Session(engine) as session:
        delete_question(session, scene.manager, question)
    assert rows(engine) == [(*before[:6], deleted)]
    with Session(engine) as session:
        assert question_page(session, scene.maths, 1, include_additional=True).questions == []
        with pytest.raises(QuestionNotFound):
            get_question(session, question)


@pytest.mark.parametrize(
    ("count", "index", "landing_page", "landing_index"),
    [
        (25, 14, 2, 14),  # US4-4: middle of page 2, the next question takes its place
        (25, 9, 1, 9),  # US4-5: last on page 1, the first of page 2 moves up
        (25, 24, 3, 23),  # US4-6: last of the whole list, the question before it
        (21, 20, 2, 19),  # US4-7: the only one on page 3, the last of page 2
    ],
    ids=["middle", "last-on-page", "last-of-list", "only-on-last-page"],
)
def test_where_the_list_lands_after_a_deletion(
    engine: Engine, scene: Scene, count: int, index: int, landing_page: int, landing_index: int
) -> None:
    """R8: `index` is 0-based, newest first; the landing names the question now at
    `landing_index`, on its page."""
    newest_first = seed(engine, scene.maths, count)[::-1]
    with Session(engine) as session:
        landing = delete_question(session, scene.manager, newest_first[index])
        after = [
            q.id
            for q in question_page(
                session, scene.maths, landing.page, include_additional=True
            ).questions
        ]
    remaining = [q for q in newest_first if q != newest_first[index]]
    assert landing == Landing(landing_page, remaining[landing_index])
    assert landing_index // PAGE_SIZE + 1 == landing_page
    assert landing.question_id in after


def test_deleting_the_only_question_lands_on_the_empty_subject(
    engine: Engine, scene: Scene
) -> None:
    question = make_question(engine, scene.maths)
    with Session(engine) as session:
        assert delete_question(session, scene.manager, question) == Landing(1, None)


@pytest.mark.parametrize("who", ["reader", "cast"])
def test_deleting_needs_the_setting(engine: Engine, scene: Scene, who: str) -> None:
    question = make_question(engine, scene.maths)
    before = rows(engine)
    with Session(engine) as session:
        with pytest.raises(ManageRequired):
            delete_question(session, getattr(scene, who), question)
    assert rows(engine) == before


@pytest.mark.parametrize("case", ["missing", "deleted", "deactivated-subject"])
def test_deleting_needs_a_listed_question(engine: Engine, scene: Scene, case: str) -> None:
    question = {
        "missing": MISSING,
        "deleted": make_question(engine, scene.maths, deleted=True),
        "deactivated-subject": make_question(engine, scene.chemistry),
    }[case]
    before = rows(engine)
    with Session(engine) as session:
        with pytest.raises(QuestionNotFound):
            delete_question(session, scene.manager, question)
    assert rows(engine) == before


# ---------------------------------------------------------------------------------------------
# Changes between reading and writing (US5-5, US5-6)
# ---------------------------------------------------------------------------------------------


def test_a_subject_deactivated_after_the_form_refuses_the_write(
    engine: Engine, scene: Scene
) -> None:
    question = make_question(engine, scene.maths)
    with Session(engine) as session:
        set_subject_active(session, scene.maths, False)
    before = rows(engine)
    with Session(engine) as session:
        with pytest.raises(SubjectUnavailable):
            create_question(session, scene.manager, scene.maths, "Why?", "Because.")
        with pytest.raises(QuestionNotFound):
            update_question(session, scene.manager, question, "New?", "New.", is_additional=False)
        with pytest.raises(QuestionNotFound):
            delete_question(session, scene.manager, question)
    assert rows(engine) == before


def test_a_refusal_under_lock_rolls_back(engine: Engine, scene: Scene) -> None:
    """No lock outlives a refusal: the session holds nothing pending afterwards."""
    question = make_question(engine, scene.maths, "Why?")
    with Session(engine) as session:
        row = session.get(Question, question)
        assert row is not None
        row.text = "changed, never committed"
        session.add(row)
        with pytest.raises(ManageRequired):
            update_question(session, scene.reader, question, "New?", "New.", is_additional=False)
        assert not session.dirty
    assert rows(engine)[0][2] == "Why?"


# ---------------------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_ids_only(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        question = create_question(session, scene.manager, scene.maths, "Secret?", "Hidden.").id
        update_question(
            session, scene.manager, question, "Secret 2?", "Hidden 2.", is_additional=False
        )
        update_question(
            session, scene.manager, question, "Secret 2?", "Hidden 2.", is_additional=False
        )  # no-op
        delete_question(session, scene.manager, question)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [
        f"Question created: id={question} subject={scene.maths}",
        f"Question updated: id={question}",
        f"Question deleted: id={question}",
    ]


# ---------------------------------------------------------------------------------------------
# Milestone 12.9: the additional mark (specs/012.9-additional-questions/contracts/services.md)
# ---------------------------------------------------------------------------------------------


def stored_mark(engine: Engine, question_id: int) -> bool:
    with Session(engine) as session:
        question = session.get(Question, question_id)
        assert question is not None
        return question.is_additional


def test_a_new_question_is_not_additional_unless_marked(engine: Engine, scene: Scene) -> None:
    """FR-001."""
    with Session(engine) as session:
        plain = create_question(session, scene.manager, scene.maths, "Plain?", "Yes.")
        marked = create_question(
            session, scene.manager, scene.maths, "Hard?", "Yes.", is_additional=True
        )
    assert (plain.is_additional, marked.is_additional) == (False, True)
    assert (stored_mark(engine, plain.id), stored_mark(engine, marked.id)) == (False, True)


def test_an_edit_sets_and_clears_the_mark(engine: Engine, scene: Scene) -> None:
    """FR-003, FR-009."""
    question = make_question(engine, scene.maths, "Q?", "A.")
    with Session(engine) as session:
        view = update_question(session, scene.manager, question, "Q?", "A.", is_additional=True)
    assert view.is_additional and stored_mark(engine, question)
    with Session(engine) as session:
        view = update_question(session, scene.manager, question, "Q?", "A.", is_additional=False)
    assert not view.is_additional and not stored_mark(engine, question)


def test_changing_only_the_mark_is_a_change(
    engine: Engine,
    scene: Scene,
    clock: Callable[[timedelta], datetime],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Research R5: the mark joins the other two values; an edit that repeats all three changes
    nothing and logs nothing."""
    with Session(engine) as session:
        question = create_question(session, scene.manager, scene.maths, "Q?", "A.").id
    created = clock()
    later = clock(timedelta(minutes=5))
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        update_question(session, scene.manager, question, "Q?", "A.", is_additional=True)
    with Session(engine) as session:
        stored = session.get(Question, question)
        assert stored is not None and stored.updated_at == later != created
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [f"Question updated: id={question}"]

    clock(timedelta(minutes=5))
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        update_question(session, scene.manager, question, "Q?", "A.", is_additional=True)
    with Session(engine) as session:
        stored = session.get(Question, question)
        assert stored is not None and stored.updated_at == later
    assert [r for r in caplog.records if r.name == "uvicorn.error"] == []


@pytest.mark.parametrize("case", ["deleted", "deactivated-subject"])
def test_a_question_that_cannot_be_edited_keeps_its_mark(
    engine: Engine, scene: Scene, case: str
) -> None:
    """FR-005: a deleted question, or one of a deactivated subject, is not found, and its mark
    stays as it is."""
    if case == "deleted":
        question = make_question(engine, scene.maths, additional=True, deleted=True)
    else:
        question = make_question(engine, scene.chemistry, additional=True)
    with Session(engine) as session, pytest.raises(QuestionNotFound):
        update_question(session, scene.manager, question, "Q?", "A.", is_additional=False)
    assert stored_mark(engine, question)


def test_deleting_keeps_the_mark(engine: Engine, scene: Scene) -> None:
    question = make_question(engine, scene.maths, additional=True)
    with Session(engine) as session:
        delete_question(session, scene.manager, question)
    assert stored_mark(engine, question)


def mixed_subject(engine: Engine, subject_id: int) -> tuple[list[int], list[int]]:
    """20 ordinary questions, then 3 additional ones (the newest is additional), then one deleted
    additional question; the ordinary ids and the additional ids, in creation order."""
    ordinary = seed(engine, subject_id, 20)
    additional = [
        make_question(engine, subject_id, f"X{i}", "A.", additional=True) for i in range(3)
    ]
    make_question(engine, subject_id, "Gone?", "A.", additional=True, deleted=True)
    return ordinary, additional


def test_without_the_additional_questions_count_and_pages_cover_the_others(
    engine: Engine, scene: Scene
) -> None:
    """FR-014, FR-019, SC-001: left out of the count, the paging and the rows."""
    ordinary, _ = mixed_subject(engine, scene.maths)
    with Session(engine) as session:
        pages = [
            question_page(session, scene.maths, p, include_additional=False) for p in (1, 2, 9)
        ]
    assert all(p.paging.total == 20 and p.paging.last == 2 for p in pages)
    assert [q.id for q in pages[0].questions] == ordinary[::-1][:10]
    assert [q.id for q in pages[1].questions] == ordinary[::-1][10:]
    assert pages[2].paging.number == 2  # a page past the end is clamped to the last
    assert not any(q.is_additional for p in pages for q in p.questions)


def test_with_the_additional_questions_everything_is_listed(engine: Engine, scene: Scene) -> None:
    ordinary, additional = mixed_subject(engine, scene.maths)
    with Session(engine) as session:
        first = question_page(session, scene.maths, 1, include_additional=True)
    assert first.paging.total == 23
    assert [q.id for q in first.questions] == (ordinary + additional)[::-1][:10]
    assert [q.is_additional for q in first.questions[:3]] == [True, True, True]


def test_a_subject_with_only_additional_questions_is_empty_without_them(
    engine: Engine, scene: Scene
) -> None:
    for i in range(2):
        make_question(engine, scene.physics, f"X{i}", "A.", additional=True)
    with Session(engine) as session:
        without = question_page(session, scene.physics, 1, include_additional=False)
        with_them = question_page(session, scene.physics, 1, include_additional=True)
    assert (without.paging.total, without.questions) == (0, [])
    assert with_them.paging.total == 2
