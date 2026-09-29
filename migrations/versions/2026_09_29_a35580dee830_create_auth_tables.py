"""create auth tables

Revision ID: a35580dee830
Revises: bba0b3665864
Create Date: 2026-09-29 10:43:53.984591+00:00

Creates the four sign-in tables: `users`, `sessions`, `login_codes` and `rate_limit_hits`. Purely
additive and data-free: no user is seeded, because administrators come from `ADMIN_EMAILS` at
startup, and milestone 3's code never touches these tables, so the previous release keeps working
on this schema during a deploy overlap. Written with plain SQLAlchemy types rather than the
application's, so it stays valid however the models change later.
See specs/004-email-otp-auth/data-model.md#7-schema-version-introduced-by-this-milestone.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a35580dee830"
down_revision: str | Sequence[str] | None = "bba0b3665864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"])
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"])

    op.create_table(
        "login_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_login_codes_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_codes")),
    )
    op.create_index(op.f("ix_login_codes_user_id"), "login_codes", ["user_id"])
    op.create_index(op.f("ix_login_codes_expires_at"), "login_codes", ["expires_at"])

    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bucket", sa.String(32), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hits")),
    )
    # Named explicitly, as in the model: the naming convention covers only the first column.
    op.create_index(
        "ix_rate_limit_hits_bucket_key_hash_created_at",
        "rate_limit_hits",
        ["bucket", "key_hash", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema. Dropping a table drops its indexes; reverse dependency order."""
    op.drop_table("rate_limit_hits")
    op.drop_table("login_codes")
    op.drop_table("sessions")
    op.drop_table("users")
