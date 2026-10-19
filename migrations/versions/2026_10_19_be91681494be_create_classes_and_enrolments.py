"""create classes and enrolments

Revision ID: be91681494be
Revises: f13dab4dd8ba
Create Date: 2026-10-19 09:26:04.833500+00:00

The schema of milestone 9 (specs/009-classes-students-management/data-model.md §7, research D13,
D18):

- `classes`: per educational institution, a name unique ignoring case (`name_key`), a year of
  study from 1 to 12, and a status;
- `enrolments`: one row per student, keyed by `user_id`, pointing to a class;
- `consent_texts`, given the student's version 1.

Neither foreign key cascades: on PostgreSQL `enrolments.class_id` backs up the service's refusal
to delete a class that holds a student (FR-006), and `classes.institution_id` the institution's
in-use check (FR-007). There is no data step: nobody holds the student role after milestone 8.

**`STUDENT_CONSENT_TEXT_V1` is published.** Once applied anywhere shared it must never be edited:
a wording change is a new migration that inserts version 2 (milestone 8 research D7).
`tests/unit/test_consent_texts.py` pins its SHA-256 and fails the build if it changes. The
downgrade deletes it, which is only possible before any student consent record refers to it.

Written with plain SQLAlchemy constructs rather than the application's models, so it stays valid
however the models change later.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "be91681494be"
down_revision: str | Sequence[str] | None = "f13dab4dd8ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_CONSENT_TEXT_V1 = """\
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
"""The student's consent text, version 1: placeholder wording that covers every FR-039 topic and
never names an institution or a class. Published; never edit it (see the module docstring)."""

STUDENT_CONSENT_TEXT_V1_PUBLISHED_AT = datetime(2026, 10, 19, tzinfo=UTC)


def _consent_texts() -> sa.TableClause:
    """A lightweight stub of `consent_texts`: only what the insert and the delete need."""
    return sa.table(
        "consent_texts",
        sa.column("role", sa.String),
        sa.column("version", sa.Integer),
        sa.column("text", sa.Text),
        sa.column("published_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("year_of_study", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("year_of_study BETWEEN 1 AND 12", name=op.f("ck_classes_year_of_study")),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_classes_institution_id_institutions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classes")),
        sa.UniqueConstraint(
            "institution_id", "name_key", name=op.f("uq_classes_institution_id_name_key")
        ),
    )
    op.create_table(
        "enrolments",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], name=op.f("fk_enrolments_class_id_classes")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_enrolments_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_enrolments")),
    )
    op.create_index(op.f("ix_enrolments_class_id"), "enrolments", ["class_id"])
    op.bulk_insert(
        _consent_texts(),
        [
            {
                "role": "student",
                "version": 1,
                "text": STUDENT_CONSENT_TEXT_V1,
                "published_at": STUDENT_CONSENT_TEXT_V1_PUBLISHED_AT,
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    consent_texts = _consent_texts()
    op.execute(
        consent_texts.delete().where(
            consent_texts.c.role == "student", consent_texts.c.version == 1
        )
    )
    op.drop_index(op.f("ix_enrolments_class_id"), table_name="enrolments")
    op.drop_table("enrolments")
    op.drop_table("classes")
