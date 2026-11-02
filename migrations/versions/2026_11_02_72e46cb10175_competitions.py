"""competitions

Revision ID: 72e46cb10175
Revises: 09cbcbe472be
Create Date: 2026-11-02 17:31:16.519923+00:00

Milestone 12.1 (specs/012.1-teacher-competitions/data-model.md §7, research R1–R3): the
`competitions` table. Per subject, a name with its `name_key`, the start, and the two nullable
facts that end a competition, `cancelled_at` and `stopped_at`; no status column and no creator.

- Names are unique among the live competitions of a subject through the partial unique index
  `uq_competitions_subject_name_live` on `(subject_id, name_key)`
  (`WHERE cancelled_at IS NULL AND stopped_at IS NULL`), declared for both engines (research R3).
- The check constraint `ck_competitions_one_end` keeps a competition from being both cancelled
  and finished (research R1).
- The foreign key to `subjects` does not cascade: a subject with a competition cannot be deleted.

No data step. The downgrade drops the table, so every competition is lost; no other table changes.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72e46cb10175"
down_revision: str | Sequence[str] | None = "09cbcbe472be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIVE = "cancelled_at IS NULL AND stopped_at IS NULL"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cancelled_at IS NULL OR stopped_at IS NULL", name=op.f("ck_competitions_one_end")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_competitions_subject_id_subjects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitions")),
    )
    op.create_index(op.f("ix_competitions_subject_id"), "competitions", ["subject_id"])
    op.create_index(
        "uq_competitions_subject_name_live",
        "competitions",
        ["subject_id", "name_key"],
        unique=True,
        sqlite_where=sa.text(_LIVE),
        postgresql_where=sa.text(_LIVE),
    )


def downgrade() -> None:
    """Downgrade schema. Lossy: every competition is dropped."""
    op.drop_index("uq_competitions_subject_name_live", table_name="competitions")
    op.drop_index(op.f("ix_competitions_subject_id"), table_name="competitions")
    op.drop_table("competitions")
