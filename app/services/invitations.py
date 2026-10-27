"""Invitations: issue one by email, read and evaluate one, and accept one with consent.

See specs/008-teacher-management-consent/contracts/services.md §invitations and research D2–D6.
The invitation is never stored: it exists only inside its sealed link (`app.core.sealing`), so
nothing about the invited person is in the database until they press **I agree** (FR-001–FR-003).

The flow is the same for every invitable role (FR-005). It knows a role only through an
`InvitableRole` definition: who may invite, which role details are acceptable, how they are
described, granted and revoked. `invitable_roles()` is the registry, the `INVITABLE_ROLES` of the
plan: milestone 8 registered the teacher (`app.services.teachers.TEACHER_INVITATION`), and
milestone 9 adds the student (`app.services.students.STUDENT_INVITATION`). The registry imports
both modules lazily, because they import this one.

The flow changed in one place only for milestone 9: the names rule of `accept_invitation`
(specs/009-classes-students-management/research.md D10).

These functions enforce no route authorization: the invitation form is administrator-only, and
the link pages are public because the sealed token is their authority (FR-055). They log ids,
roles and counts only — never an address, a name, a token or a link (FR-004).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.sealing import SealExpired, SealInvalid, from_microseconds, seal, unseal
from app.models import ConsentRecord, Role, User
from app.schemas.people import clean_email, clean_person_name
from app.schemas.teachers import NOT_SELECTABLE, InvalidChoice
from app.services.consent import current_consent_text, get_cutoff
from app.services.email import EmailSender, invitation_message
from app.services.users import display_name, get_roles, get_user_by_email

INVITATION_PURPOSE = "invitation"
INVITATION_TTL = timedelta(days=7)

PAYLOAD_VERSION = 1
"""The `"v"` of the sealed payload (data-model §9)."""

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class DetailLine:
    """One line describing a role's details to the invited person."""

    text: str
    """As shown on the acceptance page and the profile, e.g. "Can manage competitions: Yes"."""
    email_text: str | None = None
    """The wording in the invitation email, when it differs from `text`."""

    @property
    def for_email(self) -> str:
        return self.email_text or self.text


class InvitableRole(Protocol):
    """What the generic flow needs to know about one invitable role (FR-005, research D3)."""

    role: Role

    def details_to_payload(self, details: Any) -> dict[str, Any]:
        """The role details as JSON-ready values, for the sealed payload."""
        ...

    def details_from_payload(self, raw: Any) -> Any:
        """The role details read back from a payload; `ValueError` if they do not parse."""
        ...

    def inviter_may_invite(self, session: Session, inviter: User, details: Any) -> bool:
        """Whether `inviter` may invite with these details, now."""
        ...

    def details_acceptable(self, session: Session, details: Any, lock: bool) -> bool:
        """Whether the details can be granted now; with `lock`, what they refer to stays so
        until the transaction ends."""
        ...

    def describe(self, session: Session, details: Any) -> list[DetailLine]:
        """The lines that tell the invited person what will be stored, by current names."""
        ...

    def grant(self, session: Session, user: User, details: Any, now: datetime) -> None:
        """Give `user` the role and its details. Does not commit."""
        ...

    def revoke(self, session: Session, user_id: int) -> None:
        """Take the role and its details away, whichever of them are present. Does not commit."""
        ...


def invitable_roles() -> dict[Role, InvitableRole]:
    """The registry of invitable roles (`INVITABLE_ROLES`): the teacher and the student."""
    from app.services.students import STUDENT_INVITATION
    from app.services.teachers import TEACHER_INVITATION

    return {Role.TEACHER: TEACHER_INVITATION, Role.STUDENT: STUDENT_INVITATION}


def invitable_role(role: Role) -> InvitableRole:
    """The definition of `role`; `KeyError` if it is not invitable."""
    return invitable_roles()[role]


@dataclass(frozen=True)
class Invitation:
    """What a valid sealed link holds, read back and re-validated."""

    role: Role
    email: str
    first_name: str
    last_name: str
    details: Any
    inviter_id: int
    issued_at: datetime

    @property
    def expires_at(self) -> datetime:
        return self.issued_at + INVITATION_TTL


class Invalid:
    """Tampered with, malformed, or not a payload this server can read."""


class Expired:
    """Authentic, but older than seven days."""


class Refused:
    """Authentic and in time, but no longer acceptable: the inviter is no longer an
    administrator, a detail is no longer available, or a removal or withdrawal came later."""


@dataclass(frozen=True)
class AlreadyHeld:
    """The person already holds the role."""

    invitation: Invitation


@dataclass(frozen=True)
class Acceptable:
    invitation: Invitation


@dataclass(frozen=True)
class Accepted:
    user_id: int
    email: str


@dataclass(frozen=True)
class ConsentChanged:
    """The consent text changed since the page was shown (FR-035); nothing was stored."""

    invitation: Invitation


Evaluation = Invalid | Expired | Refused | AlreadyHeld | Acceptable
Acceptance = Invalid | Expired | Refused | AlreadyHeld | ConsentChanged | Accepted


def issue_invitation(
    session: Session,
    settings: AuthSettings,
    sender: EmailSender,
    base_url: str,
    inviter: User,
    role: Role,
    email: str,
    first_name: str,
    last_name: str,
    details: Any,
    now: datetime | None = None,
) -> None:
    """Seal an invitation and email its link to `email` (FR-019–FR-021).

    The router has already validated the form and checked the rate limits. Here the inviter and
    the details are checked once more, and anything no longer acceptable raises `InvalidChoice`.
    Nothing is written to the database. `EmailDeliveryError` propagates.
    """
    now = now or utc_now()
    role_def = invitable_role(role)
    acceptable = role_def.inviter_may_invite(session, inviter, details) and (
        role_def.details_acceptable(session, details, lock=False)
    )
    if not acceptable:
        raise InvalidChoice(NOT_SELECTABLE)
    assert inviter.id is not None
    payload = {
        "v": PAYLOAD_VERSION,
        "role": role.value,
        "email": email,
        "first": first_name,
        "last": last_name,
        "details": role_def.details_to_payload(details),
        "inviter": inviter.id,
    }
    token = seal(settings.secret_key, INVITATION_PURPOSE, payload, now)
    lines = role_def.describe(session, details)
    message = invitation_message(
        email,
        display_name(inviter),
        inviter.email,
        role.label,
        [line.for_email for line in lines],
        f"{base_url}/invitations/{token}",
        now + INVITATION_TTL,
    )
    sender.send(message)
    logger.info(
        "Invitation sent: inviter_id=%s role=%s institutions=%s class_id=%s",
        inviter.id,
        role.value,
        len(getattr(details, "institutions", ())),
        getattr(details, "class_id", "-"),
    )


def _read(settings: AuthSettings, token: str, now: datetime) -> Invalid | Expired | Invitation:
    """Unseal `token` and validate its payload again, as if it were untrusted (research D2)."""
    try:
        payload = unseal(settings.secret_key, INVITATION_PURPOSE, token, INVITATION_TTL, now)
    except SealExpired:
        return Expired()
    except SealInvalid:
        return Invalid()
    try:
        if payload["v"] != PAYLOAD_VERSION:
            return Invalid()
        role = Role(payload["role"])
        role_def = invitable_role(role)
        email = clean_email(payload["email"])
        if email != payload["email"]:
            return Invalid()
        first_name = clean_person_name(payload["first"], "first name")
        last_name = clean_person_name(payload["last"], "last name")
        details = role_def.details_from_payload(payload["details"])
        inviter_id = payload["inviter"]
        if not isinstance(inviter_id, int) or isinstance(inviter_id, bool):
            return Invalid()
    except (KeyError, TypeError, ValueError, AttributeError):
        return Invalid()
    return Invitation(
        role=role,
        email=email,
        first_name=first_name,
        last_name=last_name,
        details=details,
        inviter_id=inviter_id,
        issued_at=from_microseconds(payload["at"]),
    )


def _check(
    session: Session, settings: AuthSettings, invitation: Invitation, lock: bool
) -> Refused | AlreadyHeld | Acceptable:
    """Steps 3–7 of research D4, in order; the first failure wins."""
    role_def = invitable_role(invitation.role)
    inviter = session.get(User, invitation.inviter_id)
    if inviter is None or not role_def.inviter_may_invite(session, inviter, invitation.details):
        return Refused()
    if not role_def.details_acceptable(session, invitation.details, lock):
        return Refused()
    cutoff = get_cutoff(session, settings.secret_key, invitation.email, invitation.role)
    if cutoff is not None and not invitation.issued_at > cutoff:
        return Refused()
    user = get_user_by_email(session, invitation.email)
    if user is not None and user.id is not None and invitation.role in get_roles(session, user.id):
        return AlreadyHeld(invitation)
    return Acceptable(invitation)


def evaluate_invitation(
    session: Session,
    settings: AuthSettings,
    token: str,
    now: datetime | None = None,
    lock: bool = False,
) -> Evaluation:
    """What opening this link leads to (research D4). Writes nothing."""
    read = _read(settings, token, now or utc_now())
    if not isinstance(read, Invitation):
        return read
    return _check(session, settings, read, lock)


def _accept_once(
    session: Session, settings: AuthSettings, token: str, consent_text_id: int, now: datetime
) -> Acceptance:
    read = _read(settings, token, now)
    if not isinstance(read, Invitation):
        return read
    # Locks the person's row, if there is one, so a removal or withdrawal of the same person
    # either finishes first (and its cut-off is seen) or waits for this acceptance (research D6).
    user = session.exec(select(User).where(User.email == read.email).with_for_update()).first()
    outcome = _check(session, settings, read, lock=True)
    if not isinstance(outcome, Acceptable):
        session.rollback()
        return outcome
    if consent_text_id != current_consent_text(session, read.role).id:
        session.rollback()
        return ConsentChanged(read)

    # The names rule (milestone 9 FR-036, FR-037, research D10): a person who already holds the
    # teacher or the student role keeps their names; anyone else gets the invitation's.
    keep_names = (
        user is not None
        and user.id is not None
        and user.is_active
        and user.first_name is not None
        and bool({Role.TEACHER, Role.STUDENT} & set(get_roles(session, user.id)))
    )
    if user is None:
        user = User(email=read.email, is_active=True, created_at=now, updated_at=now)
        change = "created"
    elif not user.is_active:
        user.is_active = True
        change = "reactivated"
    else:
        change = "added"
    if not keep_names:
        user.first_name = read.first_name
        user.last_name = read.last_name
    user.updated_at = now
    session.add(user)
    session.flush()
    assert user.id is not None
    invitable_role(read.role).grant(session, user, read.details, now)
    session.add(
        ConsentRecord(
            user_id=user.id,
            consent_text_id=consent_text_id,
            accepted_at=now,
            inviter_id=read.inviter_id,
            invitation_issued_at=read.issued_at,
        )
    )
    session.commit()
    logger.info("Invitation accepted: user_id=%s role=%s %s", user.id, read.role.value, change)
    return Accepted(user_id=user.id, email=read.email)


def accept_invitation(
    session: Session,
    settings: AuthSettings,
    token: str,
    consent_text_id: int,
    now: datetime | None = None,
) -> Acceptance:
    """Accept the invitation with the consent text `consent_text_id`, in one transaction
    (research D6, FR-028–FR-031).

    The person is created, or the role is added, or an inactive person is reactivated; the names,
    the role, its details and a consent record are written together. A person who already holds
    the teacher or the student role keeps their current names, and the invitation's are not used
    (milestone 9 FR-036, a deliberate change to milestone 8 for teacher invitations too); a new
    person, an inactive person and an administrator with neither role get the invitation's names
    (FR-037). Sessions are never touched:
    nobody is signed in or out (FR-032). If a concurrent acceptance wins a unique constraint, the
    transaction is rolled back and run once more, which then finds the role held.
    """
    now = now or utc_now()
    try:
        return _accept_once(session, settings, token, consent_text_id, now)
    except IntegrityError:
        session.rollback()
        return _accept_once(session, settings, token, consent_text_id, now)
