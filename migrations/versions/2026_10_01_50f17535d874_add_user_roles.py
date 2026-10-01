"""add user roles

Revision ID: 50f17535d874
Revises: a35580dee830
Create Date: 2026-10-01 15:47:57.901418+00:00

Roles move from the single `users.role` column to a `user_roles` table, one row per role held,
and each session gains the role that browser is currently using. See
specs/005-roles-authorization/data-model.md#7-schema-revision-introduced-by-this-milestone.

Expand now, contract later (research D2): this revision only adds and relaxes. `users.role` stays,
made nullable and no longer used, because the previous release reads it on every request and must
keep working during a deploy overlap or after a refused start that already migrated. Milestone 6's
first migration drops it. Existing sessions are not backfilled: their `current_role` stays `NULL`
and the next request upgrades them, which is the path the spec's "session from before this
milestone" edge case requires anyway.

Written with plain SQLAlchemy table constructs rather than the application's models, so it stays
valid however the models change later, and with no engine-specific SQL.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50f17535d874"
down_revision: str | Sequence[str] | None = "a35580dee830"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

users = sa.table(
    "users",
    sa.column("id", sa.Integer()),
    sa.column("role", sa.String(20)),
    sa.column("is_active", sa.Boolean()),
)
user_roles = sa.table(
    "user_roles",
    sa.column("user_id", sa.Integer()),
    sa.column("role", sa.String(20)),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
sessions = sa.table("sessions", sa.column("user_id", sa.Integer()))
login_codes = sa.table("login_codes", sa.column("user_id", sa.Integer()))


def upgrade() -> None:
    """Upgrade schema, keeping every active administrator an administrator."""
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'teacher', 'student')", name=op.f("ck_user_roles_role")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_user_roles")),
    )

    # Inactive users get no row: an inactive user holds no role (the invariant).
    now = datetime.now(UTC)
    op.execute(
        user_roles.insert().from_select(
            ["user_id", "role", "created_at"],
            sa.select(
                users.c.id,
                sa.literal("admin", sa.String(20)),
                sa.literal(now, sa.DateTime(timezone=True)),
            ).where(users.c.role == "admin", users.c.is_active == sa.true()),
        )
    )

    op.add_column("sessions", sa.Column("current_role", sa.String(20), nullable=True))

    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(20), nullable=True)


def downgrade() -> None:
    """Downgrade schema. Milestone 4 treats every active user as an administrator, so anyone who
    is not one is deactivated and signed out first."""
    admin_ids = sa.select(user_roles.c.user_id).where(user_roles.c.role == "admin")

    def holds(role: str) -> sa.Exists:
        return (
            sa.select(user_roles.c.user_id)
            .where(user_roles.c.user_id == users.c.id, user_roles.c.role == role)
            .exists()
        )

    op.execute(users.update().where(users.c.id.in_(admin_ids)).values(role="admin"))

    non_admin_ids = sa.select(users.c.id).where(users.c.id.not_in(admin_ids))
    op.execute(sessions.delete().where(sessions.c.user_id.in_(non_admin_ids)))
    op.execute(login_codes.delete().where(login_codes.c.user_id.in_(non_admin_ids)))
    op.execute(
        users.update()
        .where(users.c.id.not_in(admin_ids))
        .values(
            role=sa.case(
                (holds("teacher"), "teacher"),
                (holds("student"), "student"),
                else_="admin",
            ),
            is_active=False,
        )
    )

    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("current_role")
    op.drop_table("user_roles")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(20), nullable=False)
