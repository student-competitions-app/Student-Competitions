"""Sealed values: unreadable, tamper-proof, purpose-bound and time-limited.

See specs/008-teacher-management-consent/research.md#d1 and contracts/services.md
§`app/core/sealing.py`.
"""

import base64
import json
import re
from datetime import UTC, datetime, timedelta

import pytest

from app.core import sealing
from app.core.sealing import SEAL_VERSION, SealExpired, SealInvalid, seal, unseal

KEY = "k" * 32
OTHER_KEY = "o" * 32
PURPOSE = "invitation"
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)
URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def _decode(token: str) -> bytes:
    return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_round_trip_returns_the_payload_and_the_issue_time() -> None:
    token = seal(KEY, PURPOSE, {"email": "olena@example.org", "n": [1, 2]}, now=NOW)
    payload = unseal(KEY, PURPOSE, token, DAY, now=NOW)
    assert payload["email"] == "olena@example.org"
    assert payload["n"] == [1, 2]
    assert sealing.from_microseconds(payload["at"]) == NOW


def test_the_token_is_url_safe_and_holds_no_plaintext() -> None:
    token = seal(KEY, PURPOSE, {"email": "olena@example.org", "first": "Olena"}, now=NOW)
    assert URL_SAFE.match(token)
    for secret in ("olena@example.org", "Olena", "olena"):
        assert secret not in token
        assert base64.urlsafe_b64encode(secret.encode()).decode().rstrip("=") not in token
        assert secret.encode() not in _decode(token)


def test_changing_any_byte_makes_the_token_invalid() -> None:
    raw = _decode(seal(KEY, PURPOSE, {"x": 1}, now=NOW))
    for position in range(len(raw)):
        flipped = bytearray(raw)
        flipped[position] ^= 0x01
        with pytest.raises(SealInvalid):
            unseal(KEY, PURPOSE, _encode(bytes(flipped)), DAY, now=NOW)


@pytest.mark.parametrize(
    "token",
    ["", "a", "not base64!", "%%%", _encode(b"\x01" + b"\x00" * 20)],
    ids=["empty", "one-char", "punctuation", "percent", "too-short"],
)
def test_malformed_tokens_are_invalid(token: str) -> None:
    with pytest.raises(SealInvalid):
        unseal(KEY, PURPOSE, token, DAY, now=NOW)


def test_a_truncated_token_is_invalid() -> None:
    token = seal(KEY, PURPOSE, {"x": 1}, now=NOW)
    with pytest.raises(SealInvalid):
        unseal(KEY, PURPOSE, token[:-4], DAY, now=NOW)


def test_an_unknown_version_is_invalid() -> None:
    raw = bytearray(_decode(seal(KEY, PURPOSE, {"x": 1}, now=NOW)))
    raw[0] = SEAL_VERSION + 1
    with pytest.raises(SealInvalid):
        unseal(KEY, PURPOSE, _encode(bytes(raw)), DAY, now=NOW)


def test_another_purpose_or_key_cannot_open_it() -> None:
    token = seal(KEY, PURPOSE, {"x": 1}, now=NOW)
    with pytest.raises(SealInvalid):
        unseal(KEY, "data-deletion", token, DAY, now=NOW)
    with pytest.raises(SealInvalid):
        unseal(OTHER_KEY, PURPOSE, token, DAY, now=NOW)


@pytest.mark.parametrize(
    "plaintext",
    [b'{"x":1}', b'{"at":"1"}', b'{"at":true}', b'{"at":1.5}', b"[1,2]", b"not json"],
    ids=["no-at", "string-at", "bool-at", "float-at", "list", "not-json"],
)
def test_a_payload_without_an_integer_issue_time_is_invalid(plaintext: bytes) -> None:
    forged = sealing._encrypt(KEY, PURPOSE, plaintext)
    with pytest.raises(SealInvalid):
        unseal(KEY, PURPOSE, forged, DAY, now=NOW)


def test_age_exactly_max_age_is_expired_and_one_microsecond_less_is_not() -> None:
    token = seal(KEY, PURPOSE, {"x": 1}, now=NOW)
    with pytest.raises(SealExpired):
        unseal(KEY, PURPOSE, token, DAY, now=NOW + DAY)
    assert unseal(KEY, PURPOSE, token, DAY, now=NOW + DAY - timedelta(microseconds=1))["x"] == 1


def test_an_expired_tampered_token_is_invalid_not_expired() -> None:
    raw = bytearray(_decode(seal(KEY, PURPOSE, {"x": 1}, now=NOW)))
    raw[-1] ^= 0x01
    with pytest.raises(SealInvalid):
        unseal(KEY, PURPOSE, _encode(bytes(raw)), DAY, now=NOW + 30 * DAY)


def test_two_seals_of_the_same_payload_differ() -> None:
    assert seal(KEY, PURPOSE, {"x": 1}, now=NOW) != seal(KEY, PURPOSE, {"x": 1}, now=NOW)


def test_messages_never_quote_the_token() -> None:
    token = seal(KEY, PURPOSE, {"email": "olena@example.org"}, now=NOW)
    with pytest.raises(SealInvalid) as invalid:
        unseal(OTHER_KEY, PURPOSE, token, DAY, now=NOW)
    with pytest.raises(SealExpired) as expired:
        unseal(KEY, PURPOSE, token, DAY, now=NOW + DAY)
    for error in (invalid.value, expired.value):
        assert token not in str(error)
        assert "olena" not in str(error)


def test_a_worst_case_invitation_fits_in_a_url() -> None:
    payload = {
        "v": 1,
        "role": "teacher",
        "email": "l" * 64 + "@" + "d" * 185 + ".com",
        "first": "Ї" * 100,
        "last": "Щ" * 100,
        "details": {
            "institutions": [[1_000 + i, "write"] for i in range(40)],
            "can_create_competitions": True,
        },
        "inviter": 123_456,
    }
    token = seal(KEY, PURPOSE, payload, now=NOW)
    assert len(token) < 2000
    assert json.dumps(unseal(KEY, PURPOSE, token, DAY, now=NOW)["details"]) == json.dumps(
        payload["details"]
    )
