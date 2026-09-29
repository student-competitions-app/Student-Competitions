"""The login email and the three ways of sending it.

See specs/004-email-otp-auth/contracts/email-sender.md. No test here, or anywhere in the suite,
reaches a real email service: the Resend sender is exercised through a fake transport.
"""

import json
from collections.abc import Mapping
from urllib.error import URLError

import pytest

from app.core.config import APP_VERSION, AuthSettings
from app.services.email import (
    ConsoleEmailSender,
    EmailDeliveryError,
    EmailMessage,
    MemoryEmailSender,
    ResendEmailSender,
    build_email_sender,
    login_code_message,
)

SUBJECT = "Your Student Competitions sign-in code"


def settings(backend: str) -> AuthSettings:
    return AuthSettings(
        production=False,
        email_backend=backend,  # type: ignore[arg-type]
        secret_key="k" * 32,
        admin_emails=(),
        resend_api_key="re_test" if backend == "resend" else None,
        email_from="Sender <login@example.org>" if backend == "resend" else None,
    )


def test_the_login_message() -> None:
    message = login_code_message("a@x.org", "042917", 20)
    assert message.to == "a@x.org"
    assert message.subject == SUBJECT
    assert "Your Student Competitions sign-in code is: 042917" in message.text.splitlines()
    assert "20 minutes" in message.text
    assert "can be used once" in message.text
    assert "If you did not try to sign in, you can ignore this email." in message.text


def test_the_subject_never_carries_the_code() -> None:
    message = login_code_message("a@x.org", "042917", 20)
    assert not any(char.isdigit() for char in message.subject)


def test_the_login_message_has_no_link() -> None:
    text = login_code_message("a@x.org", "042917", 20).text
    for marker in ("http", "www.", "://"):
        assert marker not in text


def test_the_console_sender_prints_the_documented_block(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ConsoleEmailSender().send(login_code_message("admin@example.com", "042917", 20))
    assert capsys.readouterr().out == (
        "======== EMAIL (console backend: not sent) ========\n"
        "To: admin@example.com\n"
        "Subject: Your Student Competitions sign-in code\n"
        "\n"
        "Your Student Competitions sign-in code is: 042917\n"
        "\n"
        "It is valid for 20 minutes and can be used once.\n"
        "If you did not try to sign in, you can ignore this email.\n"
        "======== END EMAIL ========\n"
    )


def test_the_memory_sender_keeps_messages_in_order() -> None:
    sender = MemoryEmailSender()
    first = EmailMessage(to="a@x.org", subject="s", text="1")
    second = EmailMessage(to="b@x.org", subject="s", text="2")
    sender.send(first)
    sender.send(second)
    assert sender.outbox == [first, second]


def test_build_email_sender_maps_console_and_memory() -> None:
    assert isinstance(build_email_sender(settings("console")), ConsoleEmailSender)
    assert isinstance(build_email_sender(settings("memory")), MemoryEmailSender)


# ---------------------------------------------------------------------------------------------
# Resend, through a fake transport: no test reaches the real service
# ---------------------------------------------------------------------------------------------

API_KEY = "re_secret_test_key"
SENDER = "Student Competitions <login@example.org>"


class FakePost:
    """Records each call and answers with a chosen status, or raises a chosen exception."""

    def __init__(self, status: int = 200, error: BaseException | None = None) -> None:
        self.status = status
        self.error = error
        self.calls: list[tuple[str, bytes, dict[str, str], float]] = []

    def __call__(self, url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> int:
        self.calls.append((url, body, dict(headers), timeout))
        if self.error is not None:
            raise self.error
        return self.status


def resend(post: FakePost) -> ResendEmailSender:
    return ResendEmailSender(API_KEY, SENDER, post=post)


MESSAGE = login_code_message("a@x.org", "042917", 20)


def test_resend_request_shape() -> None:
    post = FakePost(200)
    resend(post).send(MESSAGE)
    [(url, body, headers, timeout)] = post.calls
    assert url == "https://api.resend.com/emails"
    assert json.loads(body) == {
        "from": SENDER,
        "to": ["a@x.org"],
        "subject": SUBJECT,
        "text": MESSAGE.text,
    }
    assert headers == {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": f"student-competitions/{APP_VERSION}",
    }
    assert timeout == 10


@pytest.mark.parametrize("status", [200, 201, 202, 299])
def test_resend_2xx_is_success(status: int) -> None:
    resend(FakePost(status)).send(MESSAGE)


def assert_reveals_nothing(error: EmailDeliveryError) -> None:
    text = str(error)
    for secret in (API_KEY, "a@x.org", "042917", MESSAGE.text):
        assert secret not in text


@pytest.mark.parametrize("status", [400, 401, 422, 429, 500, 503])
def test_resend_non_2xx_raises_with_the_status_only(status: int) -> None:
    with pytest.raises(EmailDeliveryError) as caught:
        resend(FakePost(status)).send(MESSAGE)
    assert str(caught.value) == f"Resend returned HTTP {status}"
    assert_reveals_nothing(caught.value)


@pytest.mark.parametrize(
    "error", [URLError("connection refused a@x.org"), TimeoutError("timed out"), OSError("x")]
)
def test_resend_network_errors_raise_with_the_type_only(error: BaseException) -> None:
    with pytest.raises(EmailDeliveryError) as caught:
        resend(FakePost(error=error)).send(MESSAGE)
    assert str(caught.value) == type(error).__name__
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    assert_reveals_nothing(caught.value)


def test_build_email_sender_maps_resend() -> None:
    sender = build_email_sender(settings("resend"))
    assert isinstance(sender, ResendEmailSender)
    assert sender.api_key == "re_test"
    assert sender.sender == "Sender <login@example.org>"
