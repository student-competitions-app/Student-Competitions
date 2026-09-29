"""Security primitives for sign-in: addresses, codes, session tokens, signatures, return paths.

Pure functions with no I/O and no configuration of their own: every key is passed in, so they are
unit-testable without an application or a database, and this module never imports
`app.core.config` (which imports it). Nothing here logs anything.

Every keyed value uses HMAC-SHA256 over a message that starts with a fixed purpose label
(`login-code`, `session`, `rate-limit`) and a NUL, so a value computed for one purpose can never
be replayed as another, although one `SECRET_KEY` keys them all. See
specs/004-email-otp-auth/research.md#d2, #d3, #d5, #d8 and #d12.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from starlette.requests import Request

SESSION_COOKIE_NAME = "sc_session"

SESSION_TTL = timedelta(days=14)
"""Absolute: a session ends 14 days after sign-in, whatever the activity (FR-023)."""

MIN_SECRET_KEY_LENGTH = 32

EMAIL_MAX_LENGTH = 254
EMAIL_LOCAL_PART_MAX_LENGTH = 64

NEXT_PATH_MAX_LENGTH = 2048

AUTH_PATHS = frozenset({"/login", "/login/code", "/logout"})
"""Never a return target: sending a freshly signed-in user back to them would loop."""


def normalize_email(raw: str) -> str:
    """The one form an address is stored, compared and hashed in."""
    return raw.strip().lower()


def is_valid_email(value: str) -> bool:
    """A structural check, not RFC 5322 in full, and no DNS lookup (data-model §1).

    3 to 254 characters, exactly one `@`, a non-empty local part of at most 64 characters, and a
    domain containing at least one `.` with no empty label. No whitespace and no control
    characters anywhere.
    """
    if not 3 <= len(value) <= EMAIL_MAX_LENGTH:
        return False
    if any(char.isspace() or not char.isprintable() for char in value):
        return False
    if value.count("@") != 1:
        return False
    local, domain = value.split("@")
    if not local or len(local) > EMAIL_LOCAL_PART_MAX_LENGTH:
        return False
    labels = domain.split(".")
    return len(labels) >= 2 and all(labels)


def generate_code() -> str:
    """Six decimal digits from the operating system's CSPRNG; leading zeros are kept."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hmac_hex(secret_key: str, message: str) -> str:
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def hash_code(secret_key: str, email: str, code: str) -> str:
    """What is stored for a login code. Binding the address in means a code row can only ever
    match its own address (research D2)."""
    return _hmac_hex(secret_key, f"login-code\x00{email}\x00{code}")


def new_session_token() -> str:
    """256 random bits, URL-safe: the secret the session cookie carries."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """What is stored for a session. The token is already high-entropy, so a plain SHA-256 is a
    sufficient one-way function (research D3)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _cookie_signature(secret_key: str, token: str) -> str:
    digest = hmac.new(secret_key.encode(), f"session\x00{token}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode()


def sign_cookie_value(secret_key: str, token: str) -> str:
    """`<token>.<signature>`: the session cookie's value."""
    return f"{token}.{_cookie_signature(secret_key, token)}"


def unsign_cookie_value(secret_key: str, value: str) -> str | None:
    """The token inside a correctly signed cookie value, or `None` for anything else.

    Never raises: a malformed, tampered or foreign cookie simply means "not signed in".
    """
    if not value.isascii():
        return None
    parts = value.split(".")
    if len(parts) != 2 or not all(parts):
        return None
    token, signature = parts
    if not hmac.compare_digest(_cookie_signature(secret_key, token), signature):
        return None
    return token


def hash_rate_limit_key(secret_key: str, bucket: str, key: str) -> str:
    """What is stored for a rate-limit hit, so neither addresses nor client IPs are kept in
    plain form (research D5)."""
    return _hmac_hex(secret_key, f"rate-limit\x00{bucket}\x00{key}")


def safe_next_path(value: str | None) -> str:
    """`value` if it is a safe local return path, otherwise `/` (research D12).

    Refuses absolute and protocol-relative URLs, backslashes (browsers read them as `/`),
    whitespace and control characters, anything over 2,048 characters, and the sign-in pages
    themselves.
    """
    if not value or len(value) > NEXT_PATH_MAX_LENGTH:
        return "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    if "\\" in value or any(char.isspace() or not char.isprintable() for char in value):
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.path in AUTH_PATHS:
        return "/"
    return value


def client_address(request: Request, trust_forwarded: bool) -> str:
    """The client identity used as the per-client rate-limit key (research D8).

    Behind Render's proxy the socket peer is the proxy itself, so there the first
    `X-Forwarded-For` entry is used; it can be spoofed, which the plan records as a residual risk.
    Elsewhere the header is ignored, because any client can send it.
    """
    if trust_forwarded:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host
