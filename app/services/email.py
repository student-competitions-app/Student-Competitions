"""Sending email: one small interface, a backend per environment, chosen once at startup.

See specs/004-email-otp-auth/contracts/email-sender.md and research D1, D6. The login flow sends
only through `app.state.email_sender.send(message)` and never looks at which backend it is
(FR-035):

- `console` (the local default) prints the message. It is the **only** code path that ever
  outputs a message body (FR-037).
- `memory` (the test suite) keeps messages in `outbox`; nothing leaves the process.
- `resend` (production) posts to Resend's HTTP API.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import APP_VERSION, AuthSettings


@dataclass(frozen=True)
class EmailMessage:
    to: str
    """The normalised recipient address."""
    subject: str
    text: str
    """The plain-text body."""


class EmailDeliveryError(RuntimeError):
    """A message could not be delivered. Its text is an HTTP status or an exception type only:
    never the key, the address or the body."""


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None:
        """Deliver `message`, or raise `EmailDeliveryError`."""
        ...


LOGIN_SUBJECT = "Your Student Competitions sign-in code"

CONSOLE_START = "======== EMAIL (console backend: not sent) ========"
CONSOLE_END = "======== END EMAIL ========"


def login_code_message(email: str, code: str, minutes: int) -> EmailMessage:
    """The sign-in email. The code is in the body only, never in the subject, so it does not
    show in lock-screen previews; and there is no link of any kind (FR-015)."""
    text = (
        f"Your Student Competitions sign-in code is: {code}\n"
        "\n"
        f"It is valid for {minutes} minutes and can be used once.\n"
        "If you did not try to sign in, you can ignore this email."
    )
    return EmailMessage(to=email, subject=LOGIN_SUBJECT, text=text)


class ConsoleEmailSender:
    """Prints the message for a developer to read. `print`, not `logging`: the application's
    loggers have no handler under uvicorn's default configuration, and the CI image job reads
    the code from `docker logs`."""

    def send(self, message: EmailMessage) -> None:
        print(
            f"{CONSOLE_START}\nTo: {message.to}\nSubject: {message.subject}\n\n"
            f"{message.text}\n{CONSOLE_END}",
            flush=True,
        )


@dataclass
class MemoryEmailSender:
    """Keeps every message in `outbox`, in order, for the tests to read the code from."""

    outbox: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)


RESEND_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 10

Post = Callable[[str, bytes, Mapping[str, str], float], int]
"""`(url, body, headers, timeout) -> HTTP status`: the transport, replaced by a fake in tests."""


def _urllib_post(url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> int:
    """POST with the standard library and return the status, 2xx or not. The response body is
    never read, so nothing the provider echoes back can end up in a log."""
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code


class ResendEmailSender:
    """Sends through Resend's HTTP API (research D1): HTTPS on port 443, which free hosting
    tiers do not block, with no SDK. It never logs the request, the response or the key."""

    def __init__(self, api_key: str, sender: str, post: Post = _urllib_post) -> None:
        self.api_key = api_key
        self.sender = sender
        self._post = post

    def send(self, message: EmailMessage) -> None:
        body = json.dumps(
            {
                "from": self.sender,
                "to": [message.to],
                "subject": message.subject,
                "text": message.text,
            }
        ).encode()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Some Cloudflare-fronted APIs refuse urllib's default agent.
            "User-Agent": f"student-competitions/{APP_VERSION}",
        }
        try:
            status = self._post(RESEND_URL, body, headers, RESEND_TIMEOUT_SECONDS)
        except OSError as exc:
            # `from None`: the original error's text may quote the request.
            raise EmailDeliveryError(type(exc).__name__) from None
        if not 200 <= status < 300:
            raise EmailDeliveryError(f"Resend returned HTTP {status}")

    def __repr__(self) -> str:
        return "ResendEmailSender(api_key='***')"


def build_email_sender(settings: AuthSettings) -> EmailSender:
    """The sender for the configured backend. Called once, in `lifespan`."""
    if settings.email_backend == "console":
        return ConsoleEmailSender()
    if settings.email_backend == "memory":
        return MemoryEmailSender()
    # Guaranteed by `resolve_auth_settings`: the resend backend has a key and a sender.
    assert settings.resend_api_key is not None and settings.email_from is not None
    return ResendEmailSender(settings.resend_api_key, settings.email_from)
