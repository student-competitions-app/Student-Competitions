"""The `competitions` table: a named event of one subject with a start, which teams of students
take part in; a competition's questions and teams (milestone 12.2); and the teams' answers
(milestone 12.3).

See specs/012.1-teacher-competitions/data-model.md §1 and research R1–R3,
specs/012.2-competition-questions-teams/data-model.md §1–§2 and research R1, and
specs/012.3-team-answers/data-model.md §1 and research R1–R2.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.answer import ANSWER_MAX_LENGTH
from app.schemas.names import NAME_KEY_MAX_LENGTH, NAME_MAX_LENGTH
from app.schemas.question import QUESTION_FIELD_MAX_LENGTH

LIVE = "cancelled_at IS NULL AND stopped_at IS NULL"
"""The condition of a **live** competition: neither cancelled nor stopped."""


class Competition(SQLModel, table=True):
    """A competition of one subject.

    The status is derived, never stored (`app.services.competitions.status_of`): **Cancelled**
    once `cancelled_at` is set, **Finished** once `stopped_at` is set, otherwise **Upcoming**
    before `starts_at` and **In progress** from it. Nothing is written when a start passes.

    A competition is **live** ⇔ `cancelled_at IS NULL AND stopped_at IS NULL` (Upcoming or In
    progress). Names are unique among the live competitions of a subject, ignoring case, through
    the partial unique index on `(subject_id, name_key)`, so a cancelled or finished competition's
    name is free again (FR-003). The check constraint keeps a competition from being both
    cancelled and finished.

    Who created or changed it is not stored (FR-001), so it is not personal data. `stopped_at` is
    written by stopping, a later 12.x milestone; in milestone 12.1 only tests set it.
    Competitions are never deleted.
    """

    __tablename__ = "competitions"
    __table_args__ = (
        Index(
            "uq_competitions_subject_name_live",
            "subject_id",
            "name_key",
            unique=True,
            sqlite_where=text(LIVE),
            postgresql_where=text(LIVE),
        ),
        CheckConstraint("cancelled_at IS NULL OR stopped_at IS NULL", name="one_end"),
    )

    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True, nullable=False)
    """Set at creation, never written again (FR-001). No `ON DELETE`: a subject with a
    competition cannot be deleted (FR-039)."""
    name: str = Field(sa_column=Column(String(NAME_MAX_LENGTH), nullable=False))
    """As entered after `clean_name`: trimmed, 1–200 code points, no control characters
    (FR-002). Shown everywhere."""
    name_key: str = Field(sa_column=Column(String(NAME_KEY_MAX_LENGTH), nullable=False))
    """`name_key(name)`: NFC, then case-folded. Never shown. Unique among the subject's live
    competitions."""
    starts_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    """The start, UTC, always a whole minute (seconds and microseconds 0) (FR-004, FR-019)."""
    cancelled_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)
    """Set once by cancelling; never cleared (FR-007)."""
    stopped_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)
    """Set once by stopping, a later 12.x milestone (FR-008)."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by an edit that changes the name or the start; cancelling leaves
    it alone."""


class CompetitionQuestion(SQLModel, table=True):
    """A question as one competition holds it: a copy of the bank question's text and reference
    answer, taken when it was added and never written again, so editing or deleting the bank
    question changes nothing here (FR-007, FR-008). The `id` is the order of adding. Its writers
    are `app.services.competition_entries` (insert, delete), only while the competition is
    Upcoming. `team_answers` refers to it (milestone 12.3): an answer is keyed by the copy, so a
    question with answers cannot be removed, and a competition's questions never change after it
    starts anyway. Not personal data: no column names a person."""

    __tablename__ = "competition_questions"
    __table_args__ = (
        UniqueConstraint(
            "competition_id",
            "question_id",
            name="uq_competition_questions_competition_id_question_id",
        ),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    """The order of adding: the list is sorted by it (FR-005). Never shown. `AUTOINCREMENT` on
    SQLite and the sequence on PostgreSQL never hand out a smaller id again, so a question
    removed and added again goes to the end."""
    competition_id: int = Field(foreign_key="competitions.id", nullable=False)
    """No `ON DELETE`: competitions are never deleted. The unique constraint's leading column
    serves the per-competition reads, so it has no index of its own."""
    question_id: int = Field(foreign_key="questions.id", nullable=False)
    """The bank question it was copied from: its number ("Question 12"), its "Deleted from the
    question bank" mark and the "Already in this competition" check. No `ON DELETE`: questions
    are only soft-deleted. At most once per competition (the unique constraint, FR-035)."""
    text: str = Field(sa_column=Column(String(QUESTION_FIELD_MAX_LENGTH), nullable=False))
    """The bank's text at the moment of adding; never written again (FR-007)."""
    reference_answer: str = Field(
        sa_column=Column(String(QUESTION_FIELD_MAX_LENGTH), nullable=False)
    )
    """The bank's reference answer at the moment of adding; never written again. Shown only in
    the teacher area."""
    added_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """When it was added. Never shown."""


class CompetitionTeam(SQLModel, table=True):
    """The fact that a team takes part in a competition. The team's name, institution, region and
    number of active members are read from the team, never copied. Its writers are
    `app.services.competition_entries` (insert, delete), only while the competition is Upcoming,
    and `app.services.teams.delete_team`, which removes a deleted team from every competition
    that is not finished (constitution Principle IV). `team_answers` refers to it through a
    composite foreign key (milestone 12.3), so `delete_team` deletes the team's answers in those
    competitions before their links. Not personal data: it names a team, not its members."""

    __tablename__ = "competition_teams"

    competition_id: int = Field(foreign_key="competitions.id", primary_key=True)
    """No `ON DELETE`: competitions are never deleted."""
    team_id: int = Field(foreign_key="teams.id", primary_key=True, index=True)
    """No `ON DELETE`: teams are only soft-deleted. Indexed for the deletion of a team's links
    (research R5). The primary key keeps a team at most once per competition (FR-035)."""
    added_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """When it was added. Never shown."""


class TeamAnswer(SQLModel, table=True):
    """One team's text answer to one question of one competition (milestone 12.3). A row exists
    only for an answered question: an emptied answer deletes it, so a team's progress is a count
    of its rows. Neither who saved it nor when is stored (FR-023): it belongs to the team and is
    not personal data. Its writers are `app.services.team_answers.save_answers` (insert, update,
    delete), only while the competition is In progress, and `app.services.teams.delete_team`,
    which deletes a deleted team's answers in every competition that is not finished."""

    __tablename__ = "team_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["competition_id", "team_id"],
            ["competition_teams.competition_id", "competition_teams.team_id"],
        ),
        CheckConstraint("text <> ''", name="answered"),
    )

    competition_id: int = Field(primary_key=True)
    """With `team_id`, a foreign key to `competition_teams`: the team is in the competition. No
    `ON DELETE`."""
    team_id: int = Field(primary_key=True)
    """With `competition_id`, a foreign key to `competition_teams`. No `ON DELETE`."""
    competition_question_id: int = Field(
        foreign_key="competition_questions.id", primary_key=True, index=True
    )
    """The competition's copy of the question (research R2). No `ON DELETE`. Indexed for the
    foreign-key check when a question is removed."""
    text: str = Field(sa_column=Column(String(ANSWER_MAX_LENGTH), nullable=False))
    """Trimmed, line breaks as `\n`, 1–2,000 code points, no NUL (`app.schemas.answer`). Never
    empty: an emptied answer deletes the row."""
