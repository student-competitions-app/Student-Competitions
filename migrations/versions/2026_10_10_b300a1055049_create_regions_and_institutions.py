"""create regions and institutions

Revision ID: b300a1055049
Revises: 4c689ca0b481
Create Date: 2026-10-10 11:01:46.656712+00:00

Replaces the region-less `institutions` table of 4c689ca0b481 (applied in production, then
reverted in code) by dropping it first. That table cannot be carried over, since its rows have no
region. Downgrading recreates it empty.

Creates the `regions` and `institutions` tables
(specs/007-region-and-institutions-management/data-model.md §7), in one revision because neither
is useful alone (research D14). `name_key` is `NFC(name).casefold()`, computed by the application:
unique on its own for regions, and unique with `region_id` for institutions, so a name repeats
only across regions (research D3). The composite constraint is named explicitly, because the naming
convention would use only its first column.

`institutions.region_id` refers to `regions.id` with no cascade: a region holding institutions is
never deleted. The services enforce that on both engines, and on PostgreSQL the foreign key is a
backstop (research D4). No data is inserted: both lists start empty.

Written with plain SQLAlchemy types rather than the application's, so it stays valid however the
models change later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b300a1055049"
down_revision: str | Sequence[str] | None = "4c689ca0b481"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("institutions")
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regions")),
        sa.UniqueConstraint("name_key", name=op.f("uq_regions_name_key")),
    )
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["region_id"], ["regions.id"], name=op.f("fk_institutions_region_id_regions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institutions")),
        sa.UniqueConstraint(
            "region_id", "name_key", name=op.f("uq_institutions_region_id_name_key")
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("institutions")
    op.drop_table("regions")
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
