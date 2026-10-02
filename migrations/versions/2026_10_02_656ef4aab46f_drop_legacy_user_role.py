"""drop legacy user role

Revision ID: 656ef4aab46f
Revises: 50f17535d874
Create Date: 2026-10-02 15:16:11.530962+00:00

The contraction milestone 5 promised (specs/006-admin-area/research.md D8): `users.role` has been
unused since roles moved to `user_roles`, always `NULL` on new rows and never read, so it is
dropped. The downgrade adds it back nullable; milestone 5's downgrade then fills it.

Written with plain SQLAlchemy constructs rather than the application's models, so it stays valid
however the models change later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "656ef4aab46f"
down_revision: str | Sequence[str] | None = "50f17535d874"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users") as batch:
        batch.drop_column("role")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(20), nullable=True))
