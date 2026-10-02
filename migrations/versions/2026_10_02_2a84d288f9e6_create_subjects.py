"""create subjects

Revision ID: 2a84d288f9e6
Revises: 656ef4aab46f
Create Date: 2026-10-02 15:17:16.370634+00:00

Creates the `subjects` table (specs/006-admin-area/data-model.md#1-subject--table-subjects-new).
`name_key` is `NFC(name).casefold()`, computed by the application, and its unique constraint makes
names unique ignoring case on both engines, even under simultaneous submissions (research D1).
No data is inserted: the subject list starts empty.

Written with plain SQLAlchemy types rather than the application's, so it stays valid however the
models change later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a84d288f9e6"
down_revision: str | Sequence[str] | None = "656ef4aab46f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("name_key", name=op.f("uq_subjects_name_key")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("subjects")
