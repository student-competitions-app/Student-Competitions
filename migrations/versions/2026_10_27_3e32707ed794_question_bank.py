"""question bank

Revision ID: 3e32707ed794
Revises: 596ead9f1205
Create Date: 2026-10-27 12:07:47.136893+00:00

Milestone 11. See specs/011-question-bank/data-model.md §6 and research R3. In this order:

1. Every row of `questions` is deleted: the milestone 3 sample questions, the only rows that can
   exist, since nothing could add a question before this milestone (FR-042). The seed revision
   `bba0b3665864` is left as it is; a fresh database still runs it, and this revision then
   removes its rows.
2. `questions` gains `subject_id` (required, indexed, a foreign key to `subjects` with no
   `ON DELETE`) and `deleted_at`, and both text columns become 2,000 characters. The table is
   empty, so the required column needs no default. `recreate="auto"`: SQLite rebuilds the table
   (the type changes and the foreign key need it) and the rebuild turns on `AUTOINCREMENT`, so an
   id is never handed out twice; PostgreSQL gets plain `ALTER TABLE` statements, so the table, its
   id sequence and its constraints stay the ones it has.
3. `teacher_profiles.can_create_competitions` is renamed `can_manage_competitions`, keeping every
   value (FR-009).

The downgrade is lossy by design: questions with a subject and up to 2,000 characters of answer do
not fit the old shape, so every question is deleted, and the sample questions are not re-inserted.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e32707ed794"
down_revision: str | Sequence[str] | None = "596ead9f1205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM questions")
    with op.batch_alter_table(
        "questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True}
    ) as batch_op:
        batch_op.add_column(sa.Column("subject_id", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column(
            "text", existing_type=sa.String(1000), type_=sa.String(2000), existing_nullable=False
        )
        batch_op.alter_column(
            "reference_answer",
            existing_type=sa.String(5000),
            type_=sa.String(2000),
            existing_nullable=False,
        )
        batch_op.create_foreign_key(
            op.f("fk_questions_subject_id_subjects"), "subjects", ["subject_id"], ["id"]
        )
        batch_op.create_index(op.f("ix_questions_subject_id"), ["subject_id"])
    with op.batch_alter_table("teacher_profiles") as batch_op:
        batch_op.alter_column(
            "can_create_competitions",
            new_column_name="can_manage_competitions",
            existing_type=sa.Boolean(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema. Lossy: every question is deleted (see the module docstring)."""
    with op.batch_alter_table("teacher_profiles") as batch_op:
        batch_op.alter_column(
            "can_manage_competitions",
            new_column_name="can_create_competitions",
            existing_type=sa.Boolean(),
            existing_nullable=False,
        )
    op.execute("DELETE FROM questions")
    with op.batch_alter_table(
        "questions", recreate="auto", table_kwargs={"sqlite_autoincrement": False}
    ) as batch_op:
        batch_op.drop_index(op.f("ix_questions_subject_id"))
        batch_op.drop_constraint(op.f("fk_questions_subject_id_subjects"), type_="foreignkey")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("subject_id")
        batch_op.alter_column(
            "text", existing_type=sa.String(2000), type_=sa.String(1000), existing_nullable=False
        )
        batch_op.alter_column(
            "reference_answer",
            existing_type=sa.String(2000),
            type_=sa.String(5000),
            existing_nullable=False,
        )
