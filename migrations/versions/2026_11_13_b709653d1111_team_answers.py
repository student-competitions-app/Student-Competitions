"""team answers

Revision ID: b709653d1111
Revises: 59c636929942
Create Date: 2026-11-13 09:00:11.769412+00:00

Milestone 12.3 (specs/012.3-team-answers/data-model.md §5, research R1–R2): a team's answers.

`team_answers`: one team's text answer to one question of one competition, keyed by
`(competition_id, team_id, competition_question_id)`. A row exists only for an answered question
(the check constraint keeps the text non-empty). The composite foreign key to `competition_teams`
keeps every answer's team in the competition; the foreign key to `competition_questions` keys the
answer by the competition's copy of the question, with an index for its check when a question is
removed. Nothing names a person or a time.

No foreign key cascades: a team's answers are deleted before its links (`teams.delete_team`).

No data step: no answer exists yet. The downgrade drops the table, so every answer is lost; no
other table changes.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b709653d1111"
down_revision: str | Sequence[str] | None = "59c636929942"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANSWER_MAX_LENGTH = 2000
"""`app.schemas.answer.ANSWER_MAX_LENGTH` when this revision was written."""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "team_answers",
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("competition_question_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(_ANSWER_MAX_LENGTH), nullable=False),
        sa.CheckConstraint("text <> ''", name=op.f("ck_team_answers_answered")),
        sa.ForeignKeyConstraint(
            ["competition_id", "team_id"],
            ["competition_teams.competition_id", "competition_teams.team_id"],
            name=op.f("fk_team_answers_competition_id_competition_teams"),
        ),
        sa.ForeignKeyConstraint(
            ["competition_question_id"],
            ["competition_questions.id"],
            name=op.f("fk_team_answers_competition_question_id_competition_questions"),
        ),
        sa.PrimaryKeyConstraint(
            "competition_id", "team_id", "competition_question_id", name=op.f("pk_team_answers")
        ),
    )
    op.create_index(
        op.f("ix_team_answers_competition_question_id"),
        "team_answers",
        ["competition_question_id"],
    )


def downgrade() -> None:
    """Downgrade schema. Lossy: every answer of every team is dropped."""
    op.drop_index(op.f("ix_team_answers_competition_question_id"), table_name="team_answers")
    op.drop_table("team_answers")
