"""Deleting one's data without signing in: an emailed one-hour link, used once.

See specs/008-teacher-management-consent/contracts/services.md §data_deletion and research D10.
The link is sealed (`{"user": id}`, purpose `data-deletion`, one hour) and nothing about it is
stored. It is "used" through the erasure time: a link is usable only while the person still has
data stored on consent and was not erased after the link was issued, so it works once, even if
the person is re-invited and accepts within the hour.

The link is sent by a background task after the response (milestone 4's pattern), so the answer
and its timing are the same for a known, an unknown and an erased address (FR-050, SC-006).
Nothing here logs an address, a name, a token or a link.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.sealing import SealExpired, SealInvalid, from_microseconds, seal, unseal
from app.models import User
from app.services.consent import ErasureResult, erase_personal_data, has_consent_data
from app.services.email import EmailDeliveryError, EmailSender, deletion_message
from app.services.users import get_user_by_email

DELETION_PURPOSE = "data-deletion"
DELETION_TTL = timedelta(hours=1)

logger = logging.getLogger("uvicorn.error")


class LinkInvalid:
    """Tampered with or malformed: not a link this server issued."""


class LinkExpired:
    """Older than an hour, or already used: the data was erased after it was issued."""


def deliver_deletion_link(
    engine: Engine, sender: EmailSender, settings: AuthSettings, base_url: str, email: str
) -> None:
    """The background task behind `POST /data-deletion`, run after the response.

    For a person (active or not) with data stored on consent it seals and emails a deletion link;
    for anyone else it does nothing (FR-051). Every exception is caught and logged by type, or for
    a delivery failure by its status, never with the address or the link.
    """
    try:
        now = utc_now()
        with Session(engine) as session:
            user = get_user_by_email(session, email)
            if user is None or not has_consent_data(user):
                return
            user_id = user.id
        token = seal(settings.secret_key, DELETION_PURPOSE, {"user": user_id}, now)
        link = f"{base_url}/data-deletion/confirm/{token}"
        sender.send(deletion_message(email, link, now + DELETION_TTL))
        logger.info("Deletion link sent: user_id=%s", user_id)
    except EmailDeliveryError as exc:
        logger.error("Deletion email not sent: %s", exc)
    except Exception as exc:
        logger.error("Deletion email not sent: %s", type(exc).__name__)


def read_deletion_link(
    session: Session,
    settings: AuthSettings,
    token: str,
    now: datetime | None = None,
    lock: bool = False,
) -> LinkInvalid | LinkExpired | User:
    """The person a usable link names; with `lock`, their row is locked. Writes nothing."""
    try:
        payload = unseal(settings.secret_key, DELETION_PURPOSE, token, DELETION_TTL, now)
    except SealExpired:
        return LinkExpired()
    except SealInvalid:
        return LinkInvalid()
    user_id = payload.get("user")
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        return LinkInvalid()
    issued_at = from_microseconds(payload["at"])
    user = session.get(
        User, user_id, with_for_update=True if lock else None, populate_existing=lock
    )
    if user is None or not has_consent_data(user):
        return LinkExpired()
    if user.data_erased_at is not None and user.data_erased_at >= issued_at:
        return LinkExpired()
    return user


def confirm_deletion(
    session: Session, settings: AuthSettings, token: str, now: datetime | None = None
) -> LinkInvalid | LinkExpired | ErasureResult:
    """Erase the data of the person the link names, exactly as a withdrawal does (FR-053),
    after checking the link again under the person's row lock."""
    read = read_deletion_link(session, settings, token, now, lock=True)
    if not isinstance(read, User):
        session.rollback()
        return read
    assert read.id is not None
    return erase_personal_data(session, settings, read.id, now)
