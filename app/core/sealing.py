"""Sealed values: small JSON payloads encrypted and authenticated into a URL-safe token.

See specs/008-teacher-management-consent/research.md#d1. A sealed token can be neither read nor
changed by whoever holds it: AES-256-GCM with a key derived from `SECRET_KEY` (HKDF-SHA256), a
random 96-bit nonce per token, and the purpose label bound as associated data, so a token sealed
for one purpose never opens as another. Every payload carries `"at"`, the issue time in integer
microseconds since the epoch, and the age is checked against it.

The purposes and their lifetimes; each constant lives beside the code that uses it:

- `invitation`: 7 days (`app.services.invitations`);
- `data-deletion`: 1 hour (`app.services.data_deletion`);
- `invitation-sent`: 10 minutes (`app.routers.admin_teachers`, the "Invitation sent" banner);
- `login-prefill`: 10 minutes (`app.routers.invitations` and `app.routers.auth`).

Pure functions, no I/O, nothing logged. Exception messages never contain the token or the payload.
"""

import base64
import binascii
import functools
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SEAL_VERSION = 1

_KEY_INFO = b"student-competitions/sealed/v1"
_NONCE_LENGTH = 12
_TAG_LENGTH = 16
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class SealInvalid(ValueError):
    """The token is tampered with, malformed, sealed for another purpose or with another key, or
    of an unknown version."""


class SealExpired(ValueError):
    """The token is authentic, but at least `max_age` old."""


@functools.lru_cache(maxsize=4)
def _key(secret_key: str) -> bytes:
    """The 256-bit AES key derived from `secret_key`; derived once per key."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_KEY_INFO).derive(
        secret_key.encode()
    )


def _associated_data(purpose: str) -> bytes:
    return bytes([SEAL_VERSION]) + purpose.encode()


def _microseconds(moment: datetime) -> int:
    return (moment - _EPOCH) // timedelta(microseconds=1)


def from_microseconds(value: int) -> datetime:
    """The UTC time an `"at"` value stands for."""
    return _EPOCH + timedelta(microseconds=value)


def _encrypt(secret_key: str, purpose: str, plaintext: bytes) -> str:
    nonce = os.urandom(_NONCE_LENGTH)
    sealed = AESGCM(_key(secret_key)).encrypt(nonce, plaintext, _associated_data(purpose))
    token = base64.urlsafe_b64encode(bytes([SEAL_VERSION]) + nonce + sealed)
    return token.rstrip(b"=").decode()


def _decrypt(secret_key: str, purpose: str, token: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        raise SealInvalid("not a sealed value") from None
    if len(raw) < 1 + _NONCE_LENGTH + _TAG_LENGTH or raw[0] != SEAL_VERSION:
        raise SealInvalid("not a sealed value")
    nonce, sealed = raw[1 : 1 + _NONCE_LENGTH], raw[1 + _NONCE_LENGTH :]
    try:
        return AESGCM(_key(secret_key)).decrypt(nonce, sealed, _associated_data(purpose))
    except InvalidTag:
        raise SealInvalid("not a sealed value") from None


def seal(
    secret_key: str, purpose: str, payload: Mapping[str, Any], now: datetime | None = None
) -> str:
    """`payload` plus `"at"` (now, in microseconds since the epoch), sealed for `purpose`."""
    moment = now or datetime.now(UTC)
    body = {**payload, "at": _microseconds(moment)}
    return _encrypt(
        secret_key, purpose, json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    )


def unseal(
    secret_key: str,
    purpose: str,
    token: str,
    max_age: timedelta,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The payload sealed in `token` for `purpose`, including `"at"`.

    Checks, in order: the token decodes, its version is known, the tag verifies, and the
    plaintext is a JSON object with an integer `"at"`. Any failure raises `SealInvalid`. Only a
    token that passes all four is checked for age, so `SealExpired` is reported only for a value
    this server really sealed: `now - at >= max_age` raises it.
    """
    plaintext = _decrypt(secret_key, purpose, token)
    try:
        payload = json.loads(plaintext)
    except ValueError:
        raise SealInvalid("not a sealed value") from None
    if not isinstance(payload, dict):
        raise SealInvalid("not a sealed value")
    at = payload.get("at")
    if not isinstance(at, int) or isinstance(at, bool):
        raise SealInvalid("not a sealed value")
    moment = now or datetime.now(UTC)
    if _microseconds(moment) - at >= max_age // timedelta(microseconds=1):
        raise SealExpired("the sealed value has expired")
    return payload
