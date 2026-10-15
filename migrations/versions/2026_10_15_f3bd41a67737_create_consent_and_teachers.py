"""create consent and teachers

Revision ID: f3bd41a67737
Revises: b300a1055049
Create Date: 2026-10-15 09:00:00.000000+00:00

The schema of milestone 8 (specs/008-teacher-management-consent/data-model.md §10, research D18):

- `users` gains `first_name`, `last_name` and `data_erased_at`, all nullable (batch mode, for
  SQLite);
- `teacher_profiles` and `teacher_institutions`: the teacher's setting and institution links;
- `consent_texts`, seeded here with the teacher's version 1, and `consent_records`;
- `invitation_cutoffs`: a keyed hash of an address, a role and a time, with no foreign key.

`teacher_institutions.institution_id` refers to `institutions.id` with no cascade, so on
PostgreSQL the foreign key backs up the service's "in use" refusal (FR-012).

**`TEACHER_CONSENT_TEXT_V1` is published.** Once applied anywhere shared it must never be edited:
a wording change is a new migration that inserts version 2 (research D7).
`tests/unit/test_consent_texts.py` pins its SHA-256 and fails the build if it changes.

Written with plain SQLAlchemy constructs rather than the application's models, so it stays valid
however the models change later.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3bd41a67737"
down_revision: str | Sequence[str] | None = "b300a1055049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEACHER_CONSENT_TEXT_V1 = """\
By pressing "I agree" you consent to Student Competitions storing the following data about you \
as a teacher: your email address, your first and last name, the educational institutions you \
are linked to with your access level for each (Read or Write), and whether you may create \
competitions. The application also records when you agreed, to which version of this text, and \
who invited you.

We store this data so that you can sign in as a teacher and so that administrators can manage \
which educational institutions you work with. Nothing about you was stored before you agreed.

Your data is seen by the administrators of Student Competitions, and by you on your profile \
page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names and your email address \
are then erased and your teacher role is removed. The record that you agreed to this text is \
kept as proof of your consent."""
"""The teacher's consent text, version 1: placeholder wording that covers every FR-036 topic.
Published; never edit it (see the module docstring)."""

TEACHER_CONSENT_TEXT_V1_PUBLISHED_AT = datetime(2026, 10, 15, tzinfo=UTC)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("first_name", sa.String(100), nullable=True))
        batch.add_column(sa.Column("last_name", sa.String(100), nullable=True))
        batch.add_column(sa.Column("data_erased_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "teacher_profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("can_create_competitions", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_teacher_profiles_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_teacher_profiles")),
    )
    op.create_table(
        "teacher_institutions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("access_level", sa.String(5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "access_level IN ('read', 'write')",
            name=op.f("ck_teacher_institutions_access_level"),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_teacher_institutions_institution_id_institutions"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_teacher_institutions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", "institution_id", name=op.f("pk_teacher_institutions")),
    )
    op.create_index(
        op.f("ix_teacher_institutions_institution_id"),
        "teacher_institutions",
        ["institution_id"],
    )
    consent_texts = op.create_table(
        "consent_texts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('teacher', 'student')", name=op.f("ck_consent_texts_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_texts")),
        sa.UniqueConstraint("role", "version", name=op.f("uq_consent_texts_role_version")),
    )
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("consent_text_id", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inviter_id", sa.Integer(), nullable=False),
        sa.Column("invitation_issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["consent_text_id"],
            ["consent_texts.id"],
            name=op.f("fk_consent_records_consent_text_id_consent_texts"),
        ),
        sa.ForeignKeyConstraint(
            ["inviter_id"], ["users.id"], name=op.f("fk_consent_records_inviter_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_consent_records_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_records")),
    )
    op.create_index(op.f("ix_consent_records_user_id"), "consent_records", ["user_id"])
    op.create_table(
        "invitation_cutoffs",
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('teacher', 'student')", name=op.f("ck_invitation_cutoffs_role")
        ),
        sa.PrimaryKeyConstraint("email_hash", "role", name=op.f("pk_invitation_cutoffs")),
    )
    op.bulk_insert(
        consent_texts,
        [
            {
                "role": "teacher",
                "version": 1,
                "text": TEACHER_CONSENT_TEXT_V1,
                "published_at": TEACHER_CONSENT_TEXT_V1_PUBLISHED_AT,
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("invitation_cutoffs")
    op.drop_index(op.f("ix_consent_records_user_id"), table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_table("consent_texts")
    op.drop_index(op.f("ix_teacher_institutions_institution_id"), table_name="teacher_institutions")
    op.drop_table("teacher_institutions")
    op.drop_table("teacher_profiles")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("data_erased_at")
        batch.drop_column("last_name")
        batch.drop_column("first_name")
