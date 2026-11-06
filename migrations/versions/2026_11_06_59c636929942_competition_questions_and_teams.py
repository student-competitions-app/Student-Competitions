"""competition questions and teams

Revision ID: 59c636929942
Revises: 72e46cb10175
Create Date: 2026-11-06 11:27:31.664349+00:00

Milestone 12.2 (specs/012.2-competition-questions-teams/data-model.md §5, research R1): a
competition's questions and teams.

1. `competition_questions`: a copy of a bank question's `text` and `reference_answer`, taken when
   it is added to a competition, with the bank `question_id` it came from and `added_at`. The `id`
   is the order of adding, so the table has `AUTOINCREMENT` on SQLite. The unique constraint on
   `(competition_id, question_id)` keeps a question at most once per competition; its leading
   column serves the per-competition reads.
2. `competition_teams`: one row per (competition, team), keyed by both, with `added_at` and an
   index on `team_id` for removing a deleted team's links.

No foreign key cascades: competitions are never deleted, and questions and teams only softly.

No data step: no competition holds a question or a team yet. The downgrade drops both tables, so
every question and team of every competition is lost; no other table changes.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "59c636929942"
down_revision: str | Sequence[str] | None = "72e46cb10175"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_QUESTION_FIELD_MAX_LENGTH = 2000
"""`app.schemas.question.QUESTION_FIELD_MAX_LENGTH` when this revision was written."""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "competition_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(_QUESTION_FIELD_MAX_LENGTH), nullable=False),
        sa.Column("reference_answer", sa.String(_QUESTION_FIELD_MAX_LENGTH), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_competition_questions_competition_id_competitions"),
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_competition_questions_question_id_questions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competition_questions")),
        sa.UniqueConstraint(
            "competition_id",
            "question_id",
            name=op.f("uq_competition_questions_competition_id_question_id"),
        ),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "competition_teams",
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_competition_teams_competition_id_competitions"),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_competition_teams_team_id_teams")
        ),
        sa.PrimaryKeyConstraint("competition_id", "team_id", name=op.f("pk_competition_teams")),
    )
    op.create_index(op.f("ix_competition_teams_team_id"), "competition_teams", ["team_id"])


def downgrade() -> None:
    """Downgrade schema. Lossy: every question and team of every competition is dropped."""
    op.drop_index(op.f("ix_competition_teams_team_id"), table_name="competition_teams")
    op.drop_table("competition_teams")
    op.drop_table("competition_questions")
