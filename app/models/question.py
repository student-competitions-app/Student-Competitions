"""The `questions` table: the question bank, one subject per question.

See specs/011-question-bank/data-model.md §1 and research R1–R2. Input is cleaned by
`app.schemas.question` before it reaches this model; the column lengths below are a backstop that
PostgreSQL enforces and SQLite does not.

- **The number shown is the id** ("Question 57"): global across the bank, given once in creation
  order and never reused. On SQLite the table has `AUTOINCREMENT` for that; on PostgreSQL the
  sequence never goes back.
- **Deletion is soft**: a deleted question stays stored unchanged, with `deleted_at` set, so the
  competitions of milestone 12 and their results (milestone 15) can still show it.
- **Shown only in the teacher area**: the reference answer never reaches a student.
- **Not personal data**: who added or changed a question is not stored, so data erasure leaves
  questions alone.
"""

from datetime import datetime

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.question import QUESTION_FIELD_MAX_LENGTH


class Question(SQLModel, table=True):
    __tablename__ = "questions"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True, nullable=False)
    """Set at creation and never changed (FR-001). No `ON DELETE`: a subject with questions
    cannot be deleted (FR-040)."""
    text: str = Field(sa_column=Column(String(QUESTION_FIELD_MAX_LENGTH), nullable=False))
    reference_answer: str = Field(
        sa_column=Column(String(QUESTION_FIELD_MAX_LENGTH), nullable=False)
    )
    """The correct answer used for scoring. Shown only in the teacher area."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by an edit that changes something; a deletion leaves it alone."""
    deleted_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)
    """`NULL` while listed; set once by a deletion and never cleared (FR-004)."""
