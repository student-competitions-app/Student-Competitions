"""answer grades

Revision ID: 04d5b638615c
Revises: b709653d1111
Create Date: 2026-11-14 13:00:43.937237+00:00

Milestone 12.4 (specs/012.4-finish-and-grade/data-model.md §1 and §6, research R2): a grade on
each answer.

`team_answers.grade`: `SMALLINT NULL`, `NULL` meaning not graded, otherwise a whole number from 0
to 10 (the check constraint `ck_team_answers_grade_range`). Nothing names a person or a time: who
graded an answer, or when, is not stored. Finishing a competition needs no change: `stopped_at`
and its `one_end` check exist since milestone 12.1.

Batch mode copies the table on SQLite and is a plain `ALTER TABLE` on PostgreSQL.

No data step: no grade exists yet, so every existing answer is not graded. The downgrade drops the
constraint and the column, so every grade is lost; every answer's text is kept.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "04d5b638615c"
down_revision: str | Sequence[str] | None = "b709653d1111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("team_answers") as batch:
        batch.add_column(sa.Column("grade", sa.SmallInteger(), nullable=True))
        batch.create_check_constraint(
            op.f("ck_team_answers_grade_range"), "grade IS NULL OR (grade >= 0 AND grade <= 10)"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("team_answers") as batch:
        batch.drop_constraint(op.f("ck_team_answers_grade_range"), type_="check")
        batch.drop_column("grade")
