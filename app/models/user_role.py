"""The `user_roles` table: one row per role a person holds.

See specs/005-roles-authorization/data-model.md, section 3.
A person holds a role exactly when the row exists. The composite primary key allows each role at
most once per person, and is also what rejects a concurrently starting instance's duplicate
insert (research D8). Rows are written only by `reconcile_users`, from the deployment's role
lists (FR-003, FR-009); no route grants, revokes or lists roles.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, String
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    __table_args__ = (CheckConstraint("role IN ('admin', 'teacher', 'student')", name="role"),)

    # No separate index: the composite primary key leads with `user_id`.
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    role: str = Field(sa_column=Column(String(20), primary_key=True, nullable=False))
    """A `Role` value."""
    created_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    """When the assignment first appeared."""
