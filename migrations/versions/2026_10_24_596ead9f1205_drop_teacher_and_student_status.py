"""drop teacher and student status

Revision ID: 596ead9f1205
Revises: 7d2c4e1a9b30
Create Date: 2026-10-24 10:00:00.000000+00:00

Undoes `7d2c4e1a9b30` forward. That revision shipped with PR #34 and was applied to production
before the PR was reverted; reverting deleted its file, so `alembic upgrade head` could no longer
locate the revision the database was stamped with. `7d2c4e1a9b30` is restored unchanged so the
chain is whole again, and this revision drops the two columns the reverted code no longer sets:

- `teacher_profiles.is_active`;
- `enrolments.is_active`.

Both are `NOT NULL` without a server default, so leaving them would make every new teacher
profile and enrolment insert fail.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "596ead9f1205"
down_revision: str | Sequence[str] | None = "7d2c4e1a9b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("teacher_profiles", "enrolments")


def upgrade() -> None:
    """Upgrade schema."""
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("is_active")


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
            )
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("is_active", server_default=None)
