"""The student's role details. Pure, no I/O.

See specs/009-classes-students-management/research.md D9 and data-model.md §6.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StudentDetails:
    """What a student invitation grants, besides the role: the enrolment in one class of one
    educational institution. Sealed in the link as `{"institution": …, "class": …}`, and stored
    only on acceptance, as the `enrolments` row. The institution is kept beside the class so that
    acceptance can check the class still belongs to it."""

    institution_id: int
    class_id: int
