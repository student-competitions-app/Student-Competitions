"""The `enrolments` table: the class each student belongs to.

See specs/009-classes-students-management/data-model.md §2 and research D1, D2, D9. Personal data
(FR-009): it reveals the institution, the class and the year of study. It is written only by
`STUDENT_INVITATION.grant`, in the acceptance transaction, and deleted only by
`STUDENT_INVITATION.revoke`, which removal, withdrawal and data deletion call
(`app.services.students`).

Only the class is stored: the student's institution is the class's institution, and a class never
moves, so it can never change.

Invariant: a person holds the `student` role ⇔ an enrolment row exists; `grant` and `revoke`
write both together. The one exception is the test cast's directly seeded student roles, which
have no row and count as usable (research D2).

A student is **blocked** ⇔ the row exists and either the student's own status (`is_active`, set by
a teacher) is off or its class is not available, computed by `app.services.availability`, never
stored (FR-015).
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now


class Enrolment(SQLModel, table=True):
    __tablename__ = "enrolments"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    """At most one enrolment per person, under any concurrency (FR-008, SC-006)."""
    class_id: int = Field(foreign_key="classes.id", index=True, nullable=False)
    """No cascade: a class with an enrolment cannot be deleted (FR-006). Indexed for the class's
    student list and for `delete_class`'s count."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """The acceptance time."""
    is_active: bool = Field(default=True, nullable=False)
    """The student's own status, set by a teacher with Write access, independent of the class's.
    Kept on a move to another class."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Changed by a move to another class or a status change only (FR-041)."""
