"""additional questions

Revision ID: ab0a6304cc28
Revises: c730fd883079
Create Date: 2026-11-23 13:23:16.452610+00:00

Milestone 12.9 (specs/012.9-additional-questions/data-model.md §1 and §4, research R1–R2): the
mark **additional question** on the questions of the bank.

`questions.is_additional`: a boolean, never `NULL`. Only teachers with **Can manage competitions**
see an additional question; every other teacher's bank is read without it. A competition's copy
(`competition_questions`) takes no copy of the mark, so that table is unchanged.

The server default `false` fills every existing row, deleted questions included, in the same
statement: no question is additional after the upgrade (FR-002), so there is no data step. It also
keeps a row inserted without the column not additional.

Batch mode with `table_kwargs={"sqlite_autoincrement": True}`, as the question bank revision
(`3e32707ed794`) does: adding the column needs no table copy on SQLite, but dropping it in the
downgrade does, and the copy must keep `AUTOINCREMENT` so a question number is never handed out
twice. On PostgreSQL both are a plain `ALTER TABLE`.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab0a6304cc28"
down_revision: str | Sequence[str] | None = "c730fd883079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table(
        "questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True}
    ) as batch:
        batch.add_column(
            sa.Column("is_additional", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    """Downgrade schema. Lossy: every mark is dropped."""
    with op.batch_alter_table(
        "questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True}
    ) as batch:
        batch.drop_column("is_additional")
