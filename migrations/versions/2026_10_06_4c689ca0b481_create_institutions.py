"""create institutions

Revision ID: 4c689ca0b481
Revises: 2a84d288f9e6
Create Date: 2026-10-06 08:05:44.571863+00:00

Creates the `institutions` table
(specs/007-institutions/data-model.md#1-institution--table-institutions-new). `name_key` is
`NFC(name).casefold()`, computed by the application, and its unique constraint makes names unique
ignoring case on both engines, even under simultaneous submissions. No data is inserted: the
institution list starts empty.

Written with plain SQLAlchemy types rather than the application's, so it stays valid however the
models change later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c689ca0b481"
down_revision: str | Sequence[str] | None = "2a84d288f9e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institutions")),
        sa.UniqueConstraint("name_key", name=op.f("uq_institutions_name_key")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("institutions")
