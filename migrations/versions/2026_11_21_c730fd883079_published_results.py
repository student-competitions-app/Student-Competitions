"""published results

Revision ID: c730fd883079
Revises: 7110bec350d2
Create Date: 2026-11-21 14:00:00.000000+00:00

Milestone 12.8 (specs/012.8-publishing-results/data-model.md §1, §2 and §6, research R3): the
published results of a competition.

`competitions.published_at`: the moment its results were published, UTC, `NULL` until then. The
status **Published** is derived from it, as **Finished** is from `stopped_at`. The check constraint
`ck_competitions_published_after_finish` publishes only a finished competition; with `one_end`, a
cancelled one never is. Who published is not stored.

`competition_results_files`: the stored snapshot of the results, one PDF per language (`uk`,
`en`), keyed by `(competition_id, language)` so there is at most one file per language. A separate
table, so listing competitions never reads a file. `content` is `BYTEA` on PostgreSQL and `BLOB` on
SQLite, never empty. No foreign key cascades: competitions are never deleted.

Batch mode copies `competitions` on SQLite and is a plain `ALTER TABLE` on PostgreSQL.

No data step: no competition is published before this revision, so every finished competition
stays **Finished**. The downgrade drops the table and the column, so every published competition
goes back to **Finished** and its files are lost.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c730fd883079"
down_revision: str | Sequence[str] | None = "7110bec350d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("competitions") as batch:
        batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            op.f("ck_competitions_published_after_finish"),
            "published_at IS NULL OR stopped_at IS NOT NULL",
        )
    op.create_table(
        "competition_results_files",
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "language IN ('uk', 'en')",
            name=op.f("ck_competition_results_files_results_file_language"),
        ),
        sa.CheckConstraint(
            "length(content) > 0", name=op.f("ck_competition_results_files_results_file_not_empty")
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_competition_results_files_competition_id_competitions"),
        ),
        sa.PrimaryKeyConstraint(
            "competition_id", "language", name=op.f("pk_competition_results_files")
        ),
    )


def downgrade() -> None:
    """Downgrade schema. Lossy: every results file is dropped, and every published competition
    is Finished again."""
    op.drop_table("competition_results_files")
    with op.batch_alter_table("competitions") as batch:
        batch.drop_constraint(op.f("ck_competitions_published_after_finish"), type_="check")
        batch.drop_column("published_at")
