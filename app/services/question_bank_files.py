"""A subject's question bank as a CSV file, for administrators: the counts on the Subjects tab, the
export, and the import that replaces the bank (milestone 12.11).

See specs/012.11-question-bank-csv/contracts/services.md §2 and research R5, R6, R8. The format
itself is `app.services.question_csv`.

- **No authorization here**, as in `app.services.subjects`: every route that calls these
  functions is `@allow_roles(Role.ADMIN)`, and a later caller must put its own role check in
  front. Administrators see the questions only in these files (constitution IV): the pages show
  them counts.
- **The export** reads the bank as it is: every question of the subject that is not deleted,
  additional ones included, oldest first (`id` ascending, the order the study materials of
  milestone 12.10 follow). It is never stored and never logged.
- **The import** (`replace_questions`) replaces the subject's questions in one transaction: the
  listed ones are soft-deleted exactly as a teacher deletes one (`deleted_at` and nothing else, so
  the competitions that hold them keep their copies, answers, grades and results files, and the
  subject can never be deleted again), then every row of the file becomes a new question in the
  file's order, so the first row is the oldest. New ids come after every existing one, so the
  number of a deleted question is never used again. It logs one line, with ids and counts only.
- **The bank lock** (`lock_question_bank`, research R6): while an import runs, every other write of
  the bank waits, of any subject; reading it does not.

**The clock** is `app.services.competitions.utc_now`, read through that module, so tests that move
the 12.1 clock move this one too.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, insert, text, update
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.core.i18n import _
from app.core.time_zone import KYIV
from app.models import Question, Subject
from app.services import competitions
from app.services.file_names import clean_file_stem
from app.services.question_csv import MAX_QUESTIONS, QuestionRow
from app.services.subjects import SubjectNotFound

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class Replaced:
    """What one import did, for its log line."""

    deleted: int
    added: int


def question_counts(session: Session) -> dict[int, int]:
    """Every subject's number of listed questions (not deleted), the additional ones included, in
    one query. A subject with none is missing from the result: its count is 0."""
    rows = session.exec(
        select(Question.subject_id, func.count())
        .where(col(Question.deleted_at).is_(None))
        .group_by(col(Question.subject_id))
    ).all()
    return {subject_id: count for subject_id, count in rows}


def export_rows(session: Session, subject_id: int) -> list[QuestionRow]:
    """The subject's listed questions, additional ones included with their mark, oldest first. The
    caller has found the subject; an active and a deactivated subject are alike. The bank number is
    never read (FR-021)."""
    rows = session.exec(
        select(Question.text, Question.reference_answer, Question.is_additional)
        .where(Question.subject_id == subject_id, col(Question.deleted_at).is_(None))
        .order_by(col(Question.id))
    ).all()
    return [QuestionRow(text, answer, additional) for text, answer, additional in rows]


def today_in_kyiv() -> date:
    """Today's date in Kyiv, for the export's file name."""
    return competitions.utc_now().astimezone(KYIV).date()


def export_file_name(subject_name: str, today: date) -> str:
    """ "<subject> <YYYY-MM-DD> question bank.csv" in the current language («… банк питань.csv»)
    (FR-016). Characters a file name cannot hold are replaced, as in milestone 12.8."""
    stem = _(
        "%(subject)s %(date)s question bank",
        subject=clean_file_stem(subject_name, str(_("Subject"))),
        date=f"{today:%Y-%m-%d}",
    )
    return f"{clean_file_stem(str(stem), str(_('Subject')))}.csv"


def lock_question_bank(session: Session) -> None:
    """Lock the question bank for writing until the transaction ends (FR-048–FR-050, research R6).

    - **PostgreSQL**: `LOCK TABLE questions IN EXCLUSIVE MODE` conflicts with `ROW EXCLUSIVE`
      (every `INSERT`, `UPDATE`, `DELETE`) and `ROW SHARE` (`SELECT … FOR UPDATE / FOR SHARE`),
      and allows `ACCESS SHARE` (a plain `SELECT`). So a teacher's add, edit, deletion or mark,
      another import, and a question added to a competition all wait for the import, and reading
      the bank does not. Row locks cannot make the `INSERT` of a new question wait, so only a table
      lock gives "either before the import and replaced, or after it". This is the
      database-specific feature justified in plan.md (constitution VII).
    - **SQLite**: nothing to do. The import's first write takes the database's write lock, other
      writers wait for it (the busy timeout), and readers are not blocked.

    **The order**: the caller has already read the subject `FOR SHARE`. Taking the table first
    would let an import and a subject deletion, which holds the subject row and then checks the
    questions' foreign key, deadlock.
    """
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("LOCK TABLE questions IN EXCLUSIVE MODE"))


def replace_questions(session: Session, subject_id: int, rows: Sequence[QuestionRow]) -> Replaced:
    """Replace the subject's questions with `rows`, in one transaction (FR-041–FR-047).

    `rows` comes from a check that found no error, so it holds 1 to `MAX_QUESTIONS` cleaned rows.
    An unknown subject, perhaps deleted since the page was opened, is `SubjectNotFound`, after a
    rollback, and nothing changes."""
    assert 1 <= len(rows) <= MAX_QUESTIONS
    subject = session.get(
        Subject, subject_id, with_for_update={"read": True}, populate_existing=True
    )
    if subject is None:
        session.rollback()
        raise SubjectNotFound(subject_id)
    lock_question_bank(session)
    now = utc_now()
    deleted = session.execute(
        update(Question)
        .where(col(Question.subject_id) == subject_id, col(Question.deleted_at).is_(None))
        .values(deleted_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    session.execute(
        insert(Question),
        [
            {
                "subject_id": subject_id,
                "text": row.text,
                "reference_answer": row.reference_answer,
                "is_additional": row.is_additional,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            for row in rows
        ],
    )
    session.commit()
    logger.info(
        "Questions imported: subject=%d deleted=%d added=%d", subject_id, deleted, len(rows)
    )
    return Replaced(deleted=deleted, added=len(rows))
