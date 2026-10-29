"""The consent tables: the published texts, the records of who agreed to which, and the
invitation cut-offs.

See specs/008-teacher-management-consent/data-model.md §5–§7 and research D5, D7. The invitation
itself is never stored: it exists only inside its sealed link (FR-002).
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.db import UTCDateTime


class ConsentText(SQLModel, table=True):
    """One published version of the consent wording for an invitable role.

    Append-only: rows are inserted by migrations only, and nothing updates or deletes them; a
    test pins each published text's SHA-256. The current text of a role is the row with the
    highest `version`.

    One exception, once: the teams migration rewrote student version 1 in place, keeping its id,
    version and date, to name team memberships (milestone 11.1 FR-015,
    specs/011.1-teacher-teams/research.md R9). The test refuses any other rewrite.
    """

    __tablename__ = "consent_texts"
    __table_args__ = (
        CheckConstraint("role IN ('teacher', 'student')", name="role"),
        UniqueConstraint("role", "version", name="uq_consent_texts_role_version"),
    )

    id: int | None = Field(default=None, primary_key=True)
    role: str = Field(sa_column=Column(String(20), nullable=False))
    """An invitable `Role` value."""
    version: int = Field(nullable=False)
    text: str = Field(sa_column=Column(Text, nullable=False))
    """The full wording: plain text, paragraphs separated by blank lines."""
    published_at: datetime = Field(sa_type=UTCDateTime, nullable=False)


class ConsentRecord(SQLModel, table=True):
    """The proof that a person agreed to one version of a consent text.

    Written only by an acceptance that grants a role, in the same transaction (FR-030, FR-031).
    Never updated or deleted, including by withdrawal and data deletion.
    """

    __tablename__ = "consent_records"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    consent_text_id: int = Field(foreign_key="consent_texts.id", nullable=False)
    """The exact version accepted; its role is the role granted."""
    accepted_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    inviter_id: int = Field(foreign_key="users.id", nullable=False)
    """Equals `user_id` for a self-invitation."""
    invitation_issued_at: datetime = Field(sa_type=UTCDateTime, nullable=False)


class InvitationCutoff(SQLModel, table=True):
    """The latest removal or withdrawal for an address and a role: invitations issued at or
    before it are refused (FR-027, FR-034).

    Keyed by `hash_invitation_cutoff_key`, a keyed hash of the address, so the row holds no
    readable personal data (FR-003) and still matches after the address is erased. No foreign
    key.
    """

    __tablename__ = "invitation_cutoffs"
    __table_args__ = (CheckConstraint("role IN ('teacher', 'student')", name="role"),)

    email_hash: str = Field(sa_column=Column(String(64), primary_key=True))
    role: str = Field(sa_column=Column(String(20), primary_key=True))
    """An invitable `Role` value."""
    cutoff_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    """Only ever raised."""
