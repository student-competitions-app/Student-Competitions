"""teams

Revision ID: 09cbcbe472be
Revises: 3e32707ed794
Create Date: 2026-10-29 15:49:28.276508+00:00

Milestone 11.1 (specs/011.1-teacher-teams/data-model.md §7, research R1–R3, R9). In this order:

1. `teams`: per educational institution, a name with its `name_key`, and a nullable `deleted_at`
   (soft deletion). Names are unique among live teams across all institutions through the
   partial unique index `uq_teams_name_key_live` (`WHERE deleted_at IS NULL`), declared for both
   engines (research R2).
2. `team_memberships`: one row per (team, student), keyed by both, with an index on `user_id`.
   Neither foreign key cascades.
3. **The student consent text version 1 is rewritten in place** to name team memberships among
   the stored data, who sees them, and that withdrawal erases them (FR-015). Its `id`, `version`
   and `published_at` are kept, so every consent record keeps pointing at it. This is the one
   exception to milestone 8's rule that a published text never changes, allowed once because no
   real users exist yet; `tests/unit/test_consent_texts.py` pins `STUDENT_CONSENT_TEXT_V1_REWRITE`
   and refuses any other rewrite. The milestone 9 migration, which holds the original wording,
   is not edited.

The downgrade is lossy by design: it writes the original wording back
(`_STUDENT_CONSENT_TEXT_V1_ORIGINAL`, a private copy, since one revision cannot import another)
and drops both tables, so every team and membership is lost.

A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "09cbcbe472be"
down_revision: str | Sequence[str] | None = "3e32707ed794"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_CONSENT_TEXT_V1_REWRITE = """\
By pressing "I agree" you consent to Student Competitions storing the following data about you \
as a student: your email address, your first and last name, your class, which also records your \
educational institution and your year of study, and your team memberships: the teams of your \
educational institution that you belong to. The application also records when you agreed, to \
which version of this text, and who invited you.

We store this data so that you can sign in as a student and take part, as a member of your \
teams, in the competitions of your educational institution. Nothing about you was stored before \
you agreed.

Your data, including your teams, is seen by the teachers linked to your educational institution, \
and by you on your profile page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names, your email address, \
your class and your team memberships are then erased and your student role is removed. The \
record that you agreed to this text is kept as proof of your consent."""
"""The student's consent text, version 1, as rewritten by this milestone (FR-015). Published;
never edit it again."""

_STUDENT_CONSENT_TEXT_V1_ORIGINAL = """\
By pressing "I agree" you consent to Student Competitions storing the following data about you \
as a student: your email address, your first and last name, and your class, which also records \
your educational institution and your year of study. The application also records when you \
agreed, to which version of this text, and who invited you.

We store this data so that you can sign in as a student and take part in the competitions of \
your educational institution. Nothing about you was stored before you agreed.

Your data is seen by the teachers linked to your educational institution, and by you on your \
profile page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names, your email address and \
your class are then erased and your student role is removed. The record that you agreed to this \
text is kept as proof of your consent."""
"""A byte-for-byte copy of `STUDENT_CONSENT_TEXT_V1` of revision `be91681494be`, for the
downgrade. Its SHA-256 is pinned as superseded in `tests/unit/test_consent_texts.py`."""


def _consent_texts() -> sa.TableClause:
    """A lightweight stub of `consent_texts`: only what the update needs."""
    return sa.table(
        "consent_texts",
        sa.column("role", sa.String),
        sa.column("version", sa.Integer),
        sa.column("text", sa.Text),
    )


def _write_student_text_v1(text: str) -> None:
    consent_texts = _consent_texts()
    op.execute(
        consent_texts.update()
        .where(consent_texts.c.role == "student", consent_texts.c.version == 1)
        .values(text=text)
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_teams_institution_id_institutions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
    )
    op.create_index(op.f("ix_teams_institution_id"), "teams", ["institution_id"])
    op.create_index(
        "uq_teams_name_key_live",
        "teams",
        ["name_key"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "team_memberships",
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_team_memberships_team_id_teams")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_team_memberships_user_id_users")
        ),
        sa.PrimaryKeyConstraint("team_id", "user_id", name=op.f("pk_team_memberships")),
    )
    op.create_index(op.f("ix_team_memberships_user_id"), "team_memberships", ["user_id"])
    _write_student_text_v1(STUDENT_CONSENT_TEXT_V1_REWRITE)


def downgrade() -> None:
    """Downgrade schema. Lossy: every team and membership is dropped (see the module
    docstring)."""
    _write_student_text_v1(_STUDENT_CONSENT_TEXT_V1_ORIGINAL)
    op.drop_index(op.f("ix_team_memberships_user_id"), table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_index("uq_teams_name_key_live", table_name="teams")
    op.drop_index(op.f("ix_teams_institution_id"), table_name="teams")
    op.drop_table("teams")
