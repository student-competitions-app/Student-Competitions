"""The `teams` and `team_memberships` tables: named groups of students of one educational
institution, the participants of competitions from milestone 12.

See specs/011.1-teacher-teams/data-model.md §1–§2 and research R1–R3.
"""

from datetime import datetime

from sqlalchemy import Column, Index, String, text
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime, utc_now
from app.schemas.names import NAME_KEY_MAX_LENGTH, NAME_MAX_LENGTH


class Team(SQLModel, table=True):
    """A team of one educational institution.

    A team is **live** ⇔ `deleted_at IS NULL`. Deletion is soft: a deleted team stays stored with
    its name, its institution and every membership, so completed competitions can keep showing it
    (milestones 12–15), but nothing lists, changes or fills it again. Milestone 12 may add only a
    live team to a competition (FR-007, FR-008).

    Names are unique among live teams across all institutions, ignoring case, through the partial
    unique index on `name_key` (research R2), so a deleted team's name is free again.

    The team itself is not personal data, its memberships are; no creator is stored. Every team,
    deleted ones included, counts as a use of its institution, which then cannot be deleted
    (FR-017).
    """

    __tablename__ = "teams"
    __table_args__ = (
        Index(
            "uq_teams_name_key_live",
            "name_key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key="institutions.id", index=True, nullable=False)
    """Set at creation and never changed: no function writes it after the insert (FR-001). No
    `ON DELETE`: an institution with a team cannot be deleted."""
    name: str = Field(sa_column=Column(String(NAME_MAX_LENGTH), nullable=False))
    """As entered after `clean_name`: trimmed, 1–200 code points, no control characters
    (FR-002). Shown everywhere."""
    name_key: str = Field(sa_column=Column(String(NAME_KEY_MAX_LENGTH), nullable=False))
    """`name_key(name)`: NFC, then case-folded. Never shown. Unique among live teams."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set once at creation; never changes."""
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """Set at creation and reset by a rename that changes something; a deletion leaves it
    alone."""
    deleted_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)
    """`NULL` while live; set once by a deletion and never cleared (FR-007, R1)."""


class TeamMembership(SQLModel, table=True):
    """One student in one team: personal data of the student (FR-012).

    Its only writers are `teams.add_member` (insert), and `teams.remove_member` and
    `STUDENT_INVITATION.revoke` (delete), so removal, withdrawal and data deletion erase it, in
    deleted teams too (FR-014). Its team belongs to the student's enrolled institution: checked on
    insert, and kept, since a student's institution never changes while they hold the role
    (research R3). It is kept unchanged when the team is deleted or the student is blocked.
    """

    __tablename__ = "team_memberships"

    team_id: int = Field(foreign_key="teams.id", primary_key=True)
    """No `ON DELETE`: teams are never deleted for good."""
    user_id: int = Field(foreign_key="users.id", primary_key=True, index=True)
    """At most once per team, by the primary key (FR-003). Indexed for the profile and the
    erasure."""
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, nullable=False)
    """When the student was added. Never shown."""
