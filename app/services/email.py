"""Sending email: one small interface, a backend per environment, chosen once at startup.

See specs/004-email-otp-auth/contracts/email-sender.md and research D1, D6. The login flow sends
only through `app.state.email_sender.send(message)` and never looks at which backend it is
(FR-035):

- `console` (the local default) prints the message. It is the **only** code path that ever
  outputs a message body (FR-037).
- `memory` (the test suite) keeps messages in `outbox`; nothing leaves the process.
- `resend` (production) posts to Resend's HTTP API.

Milestone 8 adds two messages, the invitation and the data-deletion link
(specs/008-teacher-management-consent/contracts/services.md §email). Both are plain text, carry
their link as given with no tracking, and are never stored: the `memory` outbox exists only in
tests.

Milestone 12.5 (research R10): the sign-in code and the deletion link are written in the
request's language, at build time; the invitation in Ukrainian then English, joined by a
separator line, with the subject "<Ukrainian> / <English>". Every time is Kyiv time, labelled.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.core.config import APP_NAME, APP_VERSION, AuthSettings
from app.core.i18n import Language, Text, _, _n, use_language
from app.core.time_zone import format_local_time
from app.models import Role


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


CONSOLE_START = "======== EMAIL (console backend: not sent) ========"
CONSOLE_END = "======== END EMAIL ========"

LANGUAGE_SEPARATOR = "\n\n———\n\n"
"""Between the Ukrainian and the English part of a bilingual email."""


def _lines(*parts: object) -> str:
    """The email text: each part on its own line, an empty string for a blank line."""
    return "\n".join(str(part) for part in parts)


def login_code_message(email: str, code: str, minutes: int) -> EmailMessage:
    """The sign-in email, in the request's language (milestone 12.5 FR-041). The code is in the
    body only, never in the subject, so it does not show in lock-screen previews; and there is no
    link of any kind (FR-015)."""
    text = _lines(
        _("Your %(app)s sign-in code is: %(code)s", app=APP_NAME, code=code),
        "",
        _n(
            "It is valid for %(num)d minute and can be used once.",
            "It is valid for %(num)d minutes and can be used once.",
            minutes,
        ),
        _("If you did not try to sign in, you can ignore this email."),
    )
    subject = _("Your %(app)s sign-in code", app=APP_NAME)
    return EmailMessage(to=email, subject=str(subject), text=text)


def _invitation_subject(role: Role) -> Text:
    """One whole subject per role (milestone 12.5 FR-021)."""
    if role is Role.TEACHER:
        return _("You are invited to %(app)s as a teacher", app=APP_NAME)
    return _("You are invited to %(app)s as a student", app=APP_NAME)


def _invitation_opening(role: Role, inviter: str, email: str) -> Text:
    """One whole opening sentence per role, the inviter in the present tense, so nothing agrees
    with the inviter's gender in Ukrainian (milestone 12.5 FR-034, research R10)."""
    if role is Role.TEACHER:
        return _(
            "%(inviter)s (%(email)s) invites you to %(app)s as a teacher.",
            inviter=inviter,
            email=email,
            app=APP_NAME,
        )
    return _(
        "%(inviter)s (%(email)s) invites you to %(app)s as a student.",
        inviter=inviter,
        email=email,
        app=APP_NAME,
    )


def invitation_message(
    to: str,
    inviter_display: str,
    inviter_email: str,
    role: Role,
    detail_lines: Sequence[Text],
    link: str,
    expires_at: datetime,
) -> EmailMessage:
    """The invitation email (FR-021), in Ukrainian then in English, since the invited person has
    not chosen a language yet (milestone 12.5 FR-042). The subject names the role only, never the
    invited person, so it reveals nothing in a preview; the body says who invites, to what, what
    will be stored, and that nothing is stored unless the person accepts. Every time is Kyiv
    time, labelled."""

    def part() -> tuple[str, str]:
        text = _lines(
            _invitation_opening(role, inviter_display, inviter_email),
            "",
            _("Role: %(role)s", role=role.label),
            *(f"- {line}" for line in detail_lines),
            "",
            _(
                "Nothing about you is stored unless you accept. Open this link to see exactly "
                "what will be stored and to accept:"
            ),
            "",
            link,
            "",
            _(
                "This invitation expires on %(time)s.",
                time=format_local_time(expires_at, None),
            ),
            _("If you were not expecting it, you can ignore this email."),
        )
        return str(_invitation_subject(role)), text

    with use_language(Language.UK):
        uk_subject, uk_text = part()
    with use_language(Language.EN):
        en_subject, en_text = part()
    return EmailMessage(
        to=to, subject=f"{uk_subject} / {en_subject}", text=uk_text + LANGUAGE_SEPARATOR + en_text
    )


def deletion_message(to: str, link: str, expires_at: datetime) -> EmailMessage:
    """The data-deletion email (FR-051), in the request's language: what the link does, that it
    works once and for one hour, and that it can be ignored. The expiry is Kyiv time, labelled."""
    text = _lines(
        _(
            "Someone asked to delete the data %(app)s stores about this email address.",
            app=APP_NAME,
        ),
        "",
        _(
            "Opening this link and confirming erases your first and last name and this email "
            "address, and removes the roles granted with your consent. The record that you once "
            "agreed is kept as proof of consent."
        ),
        "",
        link,
        "",
        _(
            "The link works once, within one hour, until %(time)s.",
            time=format_local_time(expires_at, None),
        ),
        _("If you did not ask for this, you can ignore this email."),
    )
    subject = _("Delete your %(app)s data", app=APP_NAME)
    return EmailMessage(to=to, subject=str(subject), text=text)


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
