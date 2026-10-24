"""add teacher and student status

Revision ID: 7d2c4e1a9b30
Revises: be91681494be
Create Date: 2026-10-23 10:00:00.000000+00:00

Gives each teacher and each student their own status, so an administrator can deactivate a
teacher and a teacher can deactivate a student without removing the role:

- `teacher_profiles.is_active`;
- `enrolments.is_active`.

Both are added as `true` for every existing row through a server default, which is then dropped,
so the models (which set the value in Python) and the schema match.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d2c4e1a9b30"
down_revision: str | Sequence[str] | None = "be91681494be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("teacher_profiles", "enrolments")


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
            )
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("is_active", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("is_active")
