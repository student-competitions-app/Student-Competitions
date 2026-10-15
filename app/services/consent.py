"""Consent: the published texts, the records, the invitation cut-offs, and erasure.

See specs/008-teacher-management-consent/contracts/services.md §consent and research D5, D7, D8.

- **Texts** are append-only, inserted by migrations; the current text of a role is its highest
  version.
- **Records** are written only by acceptance (`app.services.invitations`) and never changed.
- **Cut-offs** remember, per keyed hash of an address and per role, the latest removal or
  withdrawal, so that no older invitation can be accepted afterwards, even once the address
  itself is erased (FR-027, FR-034).
- **Erasure** is the one function behind withdrawing consent and deleting one's data (FR-046,
  FR-053): every role granted by consent is removed, the names are cleared, the address is
  replaced unless it is an administrator's, and the person is signed out everywhere.

"Has data stored on consent" is `first_name IS NOT NULL`: names are required on every invitation
and written only by acceptance, so they are present exactly between an acceptance and an erasure
(research D8).

The registry of invitable roles is read through `app.services.invitations.invitable_roles`,
imported lazily, because that module imports this one. Nothing here logs an address or a name.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.security import hash_invitation_cutoff_key
from app.models import ConsentRecord, ConsentText, InvitationCutoff, LoginCode, Role, User
from app.services.users import end_all_sessions, get_roles

logger = logging.getLogger("uvicorn.error")


def current_consent_text(session: Session, role: Role) -> ConsentText:
    """The text a person must agree to now for `role`: its highest version."""
    statement = (
        select(ConsentText)
        .where(ConsentText.role == role.value)
        .order_by(col(ConsentText.version).desc())
    )
    text = session.exec(statement).first()
    if text is None:
        raise LookupError(f"No consent text is published for role {role.value}")
    return text


@dataclass(frozen=True)
class ConsentRecordView:
    """A consent record with the text it refers to, as the profile shows it."""

    accepted_at: datetime
    role: Role
    version: int
    text: str
    inviter_id: int


def list_consent_records(session: Session, user_id: int) -> list[ConsentRecordView]:
    """Every consent record of the person, newest first, each with its exact text (FR-043)."""
    statement = (
        select(ConsentRecord, ConsentText)
        .join(ConsentText, col(ConsentText.id) == col(ConsentRecord.consent_text_id))
        .where(ConsentRecord.user_id == user_id)
        .order_by(col(ConsentRecord.accepted_at).desc(), col(ConsentRecord.id).desc())
    )
    return [
        ConsentRecordView(
            accepted_at=record.accepted_at,
            role=Role(text.role),
            version=text.version,
            text=text.text,
            inviter_id=record.inviter_id,
        )
        for record, text in session.exec(statement)
    ]


def latest_consent_at(session: Session, user_id: int, role: Role) -> datetime | None:
    """When the person last agreed to a text of `role`, if ever."""
    statement = (
        select(ConsentRecord.accepted_at)
        .join(ConsentText, col(ConsentText.id) == col(ConsentRecord.consent_text_id))
        .where(ConsentRecord.user_id == user_id, ConsentText.role == role.value)
        .order_by(col(ConsentRecord.accepted_at).desc())
    )
    return session.exec(statement).first()


def has_consent_data(user: User) -> bool:
    """Whether data stored on the person's consent is held and not yet erased (research D8)."""
    return user.first_name is not None


def get_cutoff(session: Session, secret_key: str, email: str, role: Role) -> datetime | None:
    """The latest removal or withdrawal for this (normalised) address and role, if any."""
    row = session.get(InvitationCutoff, (hash_invitation_cutoff_key(secret_key, email), role.value))
    return row.cutoff_at if row is not None else None


def set_cutoff(session: Session, secret_key: str, email: str, role: Role, now: datetime) -> None:
    """Raise the cut-off for this address and role to `now`; an earlier `now` changes nothing.
    Does not commit.

    The callers hold the person's row lock, so two writers for one address are already
    serialised; a lost insert race still ends in `IntegrityError` at commit (research D5).
    """
    key = (hash_invitation_cutoff_key(secret_key, email), role.value)
    row = session.get(InvitationCutoff, key)
    if row is None:
        session.add(InvitationCutoff(email_hash=key[0], role=key[1], cutoff_at=now))
    elif now > row.cutoff_at:
        row.cutoff_at = now
        session.add(row)
    session.flush()


@dataclass(frozen=True)
class ErasureResult:
    roles_removed: tuple[Role, ...]
    email_kept: bool
    """The person holds the administrator role, whose address comes from the configuration."""
    deactivated: bool


@dataclass(frozen=True)
class ErasurePlan:
    """What an erasure of this person would do, for the confirmation pages (FR-046, FR-053)."""

    first_name: str | None
    last_name: str | None
    email: str
    roles_to_remove: tuple[Role, ...]
    email_kept: bool
    will_deactivate: bool


def _invitable() -> tuple[Role, ...]:
    from app.services.invitations import invitable_roles

    return tuple(invitable_roles())


def describe_erasure(session: Session, user: User) -> ErasurePlan:
    """What `erase_personal_data` would do to `user` now. Writes nothing."""
    assert user.id is not None
    held = get_roles(session, user.id)
    removed = tuple(role for role in held if role in _invitable())
    return ErasurePlan(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        roles_to_remove=removed,
        email_kept=Role.ADMIN in held,
        will_deactivate=not set(held) - set(removed),
    )


def erase_personal_data(
    session: Session, settings: AuthSettings, user_id: int, now: datetime | None = None
) -> ErasureResult:
    """Erase the data stored on the person's consent, in one transaction (research D8).

    1. Lock the person's row.
    2. Revoke every invitable role held, and raise the cut-off of **every** invitable role for the
       current address, held or not, so no older invitation can be accepted afterwards.
    3. Clear the names and record the erasure time.
    4. Replace the address with `erased-<id>`, unless the person holds the administrator role.
    5. Deactivate the person if no role is left.
    6. Delete every session and login code: signed out everywhere. Commit.

    Consent records are never touched: they are the proof of consent.
    """
    from app.services.invitations import invitable_roles

    now = now or utc_now()
    user = session.get(User, user_id, with_for_update=True, populate_existing=True)
    if user is None:
        session.rollback()
        raise LookupError(f"User {user_id} not found")
    held = get_roles(session, user_id)
    registry = invitable_roles()
    removed = tuple(role for role in held if role in registry)
    for role in removed:
        registry[role].revoke(session, user_id)
    for role in registry:
        set_cutoff(session, settings.secret_key, user.email, role, now)
    email_kept = Role.ADMIN in held
    deactivated = not set(held) - set(removed)
    user.first_name = None
    user.last_name = None
    user.data_erased_at = now
    user.updated_at = now
    if not email_kept:
        user.email = f"erased-{user_id}"
    if deactivated:
        user.is_active = False
    session.add(user)
    end_all_sessions(session, user_id)
    session.execute(delete(LoginCode).where(col(LoginCode.user_id) == user_id))
    session.commit()
    logger.info(
        "Personal data erased: user_id=%s roles_removed=%s email_kept=%s",
        user_id,
        ",".join(role.value for role in removed) or "none",
        email_kept,
    )
    return ErasureResult(roles_removed=removed, email_kept=email_kept, deactivated=deactivated)
