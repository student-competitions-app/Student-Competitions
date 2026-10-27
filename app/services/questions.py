"""The question bank: one page of a subject's questions, and adding, editing and deleting them.

See specs/011-question-bank/contracts/services.md §`app/services/questions.py` and research
R1, R2, R7, R8. The bank is shared by every teacher and not scoped to institutions; reading it
needs only the teacher role, which the routes check.

- **Every write checks the setting itself**: **Can manage competitions**, read through
  `teacher_access.can_manage_competitions` with `lock=True` inside the write's own transaction,
  so a setting removed between the form and the save is seen (US5-6). Then the subject or the
  question is read under lock too: the question `FOR UPDATE`, its subject `FOR SHARE`, so a
  subject deactivated or a question deleted at the same moment either commits first and is seen,
  or waits (US5-5). Each refusal rolls back before it raises, so no lock outlives it. On SQLite
  the locks render nothing; SQLite already serialises writers.
- **Not found**: an unknown or deactivated subject is `SubjectUnavailable`; an unknown question,
  a deleted one, or one whose subject is deactivated is `QuestionNotFound`.
- **Deletion is soft**: it sets `deleted_at` and nothing else. A deleted question is never listed
  and can never be edited or deleted again.

**Contract for milestone 12** (enforced there): a question may join a new competition only if
`deleted_at IS NULL` and it belongs to the competition's subject. `get_question` already gives the
first rule.

Every function takes an open session first; the caller owns it. Input arrives already cleaned by
`app.schemas.question`. Each successful change logs one line with ids only.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.models import Question, Subject
from app.services.paging import PAGE_SIZE, Paging
from app.services.teacher_access import can_manage_competitions

logger = logging.getLogger("uvicorn.error")


class SubjectUnavailable(LookupError):
    """Unknown or deactivated subject: "Subject not found" (404)."""


class QuestionNotFound(LookupError):
    """Unknown, deleted, or of a deactivated subject: "Question not found" (404)."""


class ManageRequired(PermissionError):
    """The teacher lacks **Can manage competitions** (403)."""


@dataclass(frozen=True)
class QuestionView:
    id: int
    """Also the number shown: "Question 57"."""
    subject_id: int
    text: str
    reference_answer: str


@dataclass(frozen=True)
class QuestionPage:
    questions: list[QuestionView]
    """Newest first (id descending), at most `PAGE_SIZE`."""
    paging: Paging


@dataclass(frozen=True)
class Landing:
    """Where the list lands after a deletion (R8)."""

    page: int
    question_id: int | None
    """The question to show at its anchor; `None` when the subject has no listed question left."""


def _view(question: Question) -> QuestionView:
    assert question.id is not None
    return QuestionView(
        id=question.id,
        subject_id=question.subject_id,
        text=question.text,
        reference_answer=question.reference_answer,
    )


def _refuse(session: Session, lock: bool, error: Exception) -> Exception:
    """`error`, after rolling back when a lock was taken, so no lock outlives the refusal."""
    if lock:
        session.rollback()
    return error


def _listed(subject_id: int) -> tuple[ColumnElement[bool], ...]:
    """The conditions for the subject's listed (not deleted) questions."""
    return (Question.subject_id == subject_id, col(Question.deleted_at).is_(None))


def _require_manage(session: Session, teacher_id: int) -> None:
    if not can_manage_competitions(session, teacher_id, lock=True):
        raise _refuse(session, True, ManageRequired())


def get_active_subject(session: Session, subject_id: int, *, lock: bool = False) -> Subject:
    """The subject, if it exists and is active; `SubjectUnavailable` otherwise. With `lock`, the
    row is read `FOR SHARE` and refreshed."""
    if lock:
        subject = session.get(
            Subject, subject_id, with_for_update={"read": True}, populate_existing=True
        )
    else:
        subject = session.get(Subject, subject_id)
    if subject is None or not subject.is_active:
        raise _refuse(session, lock, SubjectUnavailable())
    return subject


def question_page(session: Session, subject_id: int, page: int) -> QuestionPage:
    """One page of the subject's listed questions, newest first, the page clamped to 1..last.
    The caller has already checked that the subject is active."""
    total = session.exec(
        select(func.count()).select_from(Question).where(*_listed(subject_id))
    ).one()
    paging = Paging.build(page, total)
    statement = (
        select(Question)
        .where(*_listed(subject_id))
        .order_by(col(Question.id).desc())
        .limit(paging.size)
        .offset(paging.offset)
    )
    return QuestionPage([_view(question) for question in session.exec(statement)], paging)


def get_question(
    session: Session, question_id: int, *, lock: bool = False
) -> tuple[QuestionView, Subject]:
    """The question and its subject, if the question exists, is not deleted, and its subject is
    active; `QuestionNotFound` otherwise. With `lock`, the question row is read `FOR UPDATE`, then
    the subject `FOR SHARE`, both refreshed."""
    if lock:
        question = session.get(Question, question_id, with_for_update=True, populate_existing=True)
    else:
        question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise _refuse(session, lock, QuestionNotFound())
    try:
        subject = get_active_subject(session, question.subject_id, lock=lock)
    except SubjectUnavailable:
        raise QuestionNotFound() from None
    return _view(question), subject


def create_question(
    session: Session, teacher_id: int, subject_id: int, text: str, reference_answer: str
) -> QuestionView:
    """Add a question to an active subject, as a teacher with the setting. `ManageRequired` or
    `SubjectUnavailable` otherwise, and nothing is stored."""
    _require_manage(session, teacher_id)
    get_active_subject(session, subject_id, lock=True)
    now = utc_now()
    question = Question(
        subject_id=subject_id,
        text=text,
        reference_answer=reference_answer,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    logger.info("Question created: id=%d subject=%d", question.id, subject_id)
    return _view(question)


def update_question(
    session: Session, teacher_id: int, question_id: int, text: str, reference_answer: str
) -> QuestionView:
    """Replace both fields of a listed question, as a teacher with the setting. The subject and
    the number never change; `updated_at` changes only if a value did. `ManageRequired` or
    `QuestionNotFound` otherwise, and nothing changes."""
    _require_manage(session, teacher_id)
    get_question(session, question_id, lock=True)
    question = session.get(Question, question_id)
    assert question is not None
    changed = (question.text, question.reference_answer) != (text, reference_answer)
    if changed:
        question.text = text
        question.reference_answer = reference_answer
        question.updated_at = utc_now()
        session.add(question)
    session.commit()
    if changed:
        logger.info("Question updated: id=%d", question_id)
    session.refresh(question)
    return _view(question)


def delete_question(session: Session, teacher_id: int, question_id: int) -> Landing:
    """Delete a listed question softly, as a teacher with the setting: `deleted_at` is set and
    nothing else changes. `ManageRequired` or `QuestionNotFound` otherwise.

    Returns where the list lands (R8). With `i` the question's index among its subject's listed
    questions, newest first: the next question, now at index `i`; else the previous one, at
    `i - 1`; else none, the subject being empty. The page is `index // PAGE_SIZE + 1`.
    """
    _require_manage(session, teacher_id)
    view, _ = get_question(session, question_id, lock=True)
    listed = _listed(view.subject_id)
    index = session.exec(
        select(func.count()).select_from(Question).where(*listed, col(Question.id) > question_id)
    ).one()
    question = session.get(Question, question_id)
    assert question is not None
    question.deleted_at = utc_now()
    session.add(question)
    next_id = session.exec(
        select(func.max(Question.id)).where(*listed, col(Question.id) < question_id)
    ).one()
    previous_id = session.exec(
        select(func.min(Question.id)).where(*listed, col(Question.id) > question_id)
    ).one()
    if next_id is not None:
        landing = Landing(index // PAGE_SIZE + 1, next_id)
    elif previous_id is not None:
        landing = Landing((index - 1) // PAGE_SIZE + 1, previous_id)
    else:
        landing = Landing(1, None)
    session.commit()
    logger.info("Question deleted: id=%d", question_id)
    return landing
