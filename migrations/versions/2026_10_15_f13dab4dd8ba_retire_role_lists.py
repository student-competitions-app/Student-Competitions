"""retire role lists

Revision ID: f13dab4dd8ba
Revises: f3bd41a67737
Create Date: 2026-10-15 09:05:00.000000+00:00

The one-time data step of milestone 8 (specs/008-teacher-management-consent/data-model.md §10,
research D16). Before this milestone every teacher and student role came from `TEACHER_EMAILS`
and `STUDENT_EMAILS`; from now on they come only from consent, and the code can no longer tell the
two apart. So every such grant is removed here, exactly once, before that code starts:

1. the sessions of everyone holding `teacher` or `student` are deleted (signed out everywhere);
2. every `teacher` and `student` row of `user_roles` is deleted;
3. every user left with no role at all is deactivated, their email is replaced with
   `erased-<id>` (as on withdrawal: no address that never consented remains), `data_erased_at`
   and `updated_at` are set, and their sessions and login codes are deleted.

Administrators keep their role, their email and, unless they also held a removed role, their
sessions. No invitation cut-off is written: no invitation can predate this revision (research
D5).

The downgrade is a no-op: the removed grants came from configuration that no longer exists, so
there is nothing to restore them from.

Written with SQLAlchemy Core table stubs, never the application's models, so it stays valid
however the models change later. The new email is built with Core concatenation, which renders
portably on SQLite and PostgreSQL.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f13dab4dd8ba"
down_revision: str | Sequence[str] | None = "f3bd41a67737"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETIRED_ROLES = ("teacher", "student")

users = sa.table(
    "users",
    sa.column("id", sa.Integer()),
    sa.column("email", sa.String()),
    sa.column("is_active", sa.Boolean()),
    sa.column("data_erased_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
user_roles = sa.table("user_roles", sa.column("user_id", sa.Integer()), sa.column("role"))
sessions = sa.table("sessions", sa.column("user_id", sa.Integer()))
login_codes = sa.table("login_codes", sa.column("user_id", sa.Integer()))


def upgrade() -> None:
    """Remove every list-granted teacher and student role."""
    now = datetime.now(UTC)
    holders = sa.select(user_roles.c.user_id).where(user_roles.c.role.in_(RETIRED_ROLES))
    op.execute(sessions.delete().where(sessions.c.user_id.in_(holders)))
    op.execute(user_roles.delete().where(user_roles.c.role.in_(RETIRED_ROLES)))

    with_a_role = sa.select(user_roles.c.user_id)
    roleless = sa.select(users.c.id).where(users.c.id.not_in(with_a_role))
    op.execute(sessions.delete().where(sessions.c.user_id.in_(roleless)))
    op.execute(login_codes.delete().where(login_codes.c.user_id.in_(roleless)))
    op.execute(
        users.update()
        .where(users.c.id.not_in(with_a_role))
        .values(
            is_active=False,
            email=sa.literal("erased-") + sa.cast(users.c.id, sa.String()),
            data_erased_at=now,
            updated_at=now,
        )
    )


def downgrade() -> None:
    """Nothing to restore: the removed grants came from configuration that no longer exists."""
