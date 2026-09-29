"""The pure security helpers: addresses, codes, tokens, cookie signatures and client addresses.

See specs/004-email-otp-auth/contracts/auth-services.md#appcoresecuritypy-pure-no-io.
"""

import base64
import re

import pytest
from starlette.requests import Request

import app.core.security as security
from app.core.security import (
    client_address,
    generate_code,
    hash_code,
    hash_rate_limit_key,
    hash_token,
    is_valid_email,
    new_session_token,
    normalize_email,
    sign_cookie_value,
    unsign_cookie_value,
)

KEY = "k" * 32
OTHER_KEY = "o" * 32
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_normalize_email_trims_and_lowercases() -> None:
    assert normalize_email("  A@X.Org ") == "a@x.org"


LOCAL_64 = "l" * 64
DOMAIN_189 = "d" * 185 + ".com"


@pytest.mark.parametrize(
    "value",
    [
        "a@b.c",
        "admin@example.com",
        "first.last+tag@sub.example.org",
        f"{LOCAL_64}@example.com",
        f"{LOCAL_64}@{DOMAIN_189}",  # exactly 254 characters
    ],
)
def test_valid_emails(value: str) -> None:
    assert is_valid_email(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a@",
        "@b.c",
        "a@b",
        "a@.b",
        "a@b.",
        "a@b..c",
        "a b@c.d",
        "a@b@c.d",
        "a@b.c\x00",
        "a\t@b.c",
        " a@b.c",
        "ab.c",
        f"{'l' * 65}@example.com",
        f"{LOCAL_64}@{DOMAIN_189}x",  # 255 characters
    ],
)
def test_invalid_emails(value: str) -> None:
    assert not is_valid_email(value)


def test_the_boundary_cases_have_the_intended_lengths() -> None:
    assert len(f"{LOCAL_64}@{DOMAIN_189}") == 254


def test_generate_code_is_six_digits() -> None:
    for _ in range(200):
        assert re.fullmatch(r"[0-9]{6}", generate_code())


def test_generate_code_keeps_leading_zeros(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security.secrets, "randbelow", lambda _: 42)
    assert generate_code() == "000042"


def test_hash_code_is_deterministic_hex_and_keyed() -> None:
    digest = hash_code(KEY, "a@x.org", "123456")
    assert HEX64.fullmatch(digest)
    assert digest == hash_code(KEY, "a@x.org", "123456")
    assert digest != hash_code(OTHER_KEY, "a@x.org", "123456")
    assert digest != hash_code(KEY, "b@x.org", "123456")
    assert digest != hash_code(KEY, "a@x.org", "123457")


def test_session_tokens_are_long_and_distinct() -> None:
    tokens = {new_session_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(token) >= 43 for token in tokens)


def test_hash_token_is_sha256_hex() -> None:
    digest = hash_token("abc")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_cookie_signature_round_trips() -> None:
    token = new_session_token()
    assert unsign_cookie_value(KEY, sign_cookie_value(KEY, token)) == token


def _flip(char: str) -> str:
    return "A" if char != "A" else "B"


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda v: _flip(v[0]) + v[1:], id="changed-token"),
        pytest.param(lambda v: v[:-1] + _flip(v[-1]), id="changed-signature"),
        pytest.param(lambda v: sign_cookie_value(OTHER_KEY, v.split(".")[0]), id="other-key"),
        pytest.param(lambda v: "", id="empty"),
        pytest.param(lambda v: v.replace(".", ""), id="no-dot"),
        pytest.param(lambda v: v + ".extra", id="several-dots"),
        pytest.param(lambda v: "é" + v, id="non-ascii"),
        pytest.param(lambda v: v.split(".")[0] + ".", id="empty-signature"),
        pytest.param(lambda v: "." + v.split(".")[1], id="empty-token"),
    ],
)
def test_unsign_rejects_anything_tampered(tamper) -> None:  # type: ignore[no-untyped-def]
    value = sign_cookie_value(KEY, new_session_token())
    assert unsign_cookie_value(KEY, tamper(value)) is None


def test_code_hashes_and_cookie_signatures_are_domain_separated() -> None:
    """Inputs that would be byte-identical without the per-purpose prefixes still yield
    different values, so one can never stand in for the other."""
    signature = sign_cookie_value(KEY, "x\x00y").split(".")[1]
    signature_hex = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)).hex()
    assert signature_hex != hash_code(KEY, "x", "y")
    assert hash_code(KEY, "x", "y") != hash_rate_limit_key(KEY, "x", "y")


def test_hash_rate_limit_key_is_hex_and_differs_per_bucket() -> None:
    first = hash_rate_limit_key(KEY, "code_email", "a@x.org")
    assert HEX64.fullmatch(first)
    assert first != hash_rate_limit_key(KEY, "code_client", "a@x.org")
    assert first != hash_rate_limit_key(OTHER_KEY, "code_email", "a@x.org")


def _request(forwarded: str | None = None, peer: str | None = "10.0.0.1") -> Request:
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    scope = {"type": "http", "headers": headers, "client": (peer, 1234) if peer else None}
    return Request(scope)


def test_client_address_trusts_the_first_forwarded_entry_on_render() -> None:
    request = _request(" 203.0.113.7 , 10.0.0.1")
    assert client_address(request, trust_forwarded=True) == "203.0.113.7"


@pytest.mark.parametrize("forwarded", [None, "", "  "])
def test_client_address_falls_back_to_the_peer(forwarded: str | None) -> None:
    assert client_address(_request(forwarded), trust_forwarded=True) == "10.0.0.1"


def test_client_address_ignores_the_header_locally() -> None:
    assert client_address(_request("203.0.113.7"), trust_forwarded=False) == "10.0.0.1"


def test_client_address_without_a_peer_is_unknown() -> None:
    assert client_address(_request(peer=None), trust_forwarded=False) == "unknown"
