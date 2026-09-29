# Email Sender Contract: one interface, three backends

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](../plan.md)

Module: `app/services/email.py`. The login flow sends email **only** through
`app.state.email_sender.send(message)` and never inspects which backend it is (FR-035). Rationale:
[research D1](../research.md#d1--email-delivery-service-resend-through-its-http-api-called-with-the-standard-library),
[D6](../research.md#d6--email-sending-one-small-protocol-three-implementations-chosen-at-startup).

---

## Types

```python
@dataclass(frozen=True)
class EmailMessage:
    to: str  # normalised recipient address
    subject: str
    text: str  # plain-text body


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...  # raises EmailDeliveryError


class EmailDeliveryError(RuntimeError): ...  # message: status code or exception type only
```

## Backends

| `EMAIL_BACKEND` | Class | Behaviour | May output the body? |
|---|---|---|---|
| `console` | `ConsoleEmailSender()` | `print`s to stdout, flushed: a start marker, `To:`, `Subject:`, a blank line, the body, an end marker (below). Never raises. | **yes, the only one** (FR-037) |
| `memory` | `MemoryEmailSender()` | appends to `self.outbox: list[EmailMessage]`. Never raises. Nothing leaves the process. | no (keeps it in memory for tests) |
| `resend` | `ResendEmailSender(api_key, sender, post=_urllib_post)` | `POST https://api.resend.com/emails` with a JSON body `{"from": sender, "to": [to], "subject": …, "text": …}`, headers `Authorization: Bearer <key>`, `Content-Type: application/json`, `User-Agent: student-competitions/<APP_VERSION>`, 10 s timeout. A 2xx status is success. Otherwise it raises `EmailDeliveryError("Resend returned HTTP <status>")`. A network or timeout error raises `EmailDeliveryError("<ExceptionType>")` `from None`. | **no**; never logs the request, the response body or the key |

`build_email_sender(settings: AuthSettings) -> EmailSender` maps the setting to the class. It runs
once in `lifespan`.

`post` is `Callable[[str, bytes, Mapping[str, str], float], int]` (url, body, headers, timeout →
status). The default uses `urllib.request`. Unit tests pass a fake that records the call and
returns a chosen status or raises, so **no test ever reaches Resend** (Principle III).

**Console output format** (what a developer sees, and what the CI image job greps):

```text
======== EMAIL (console backend: not sent) ========
To: admin@example.com
Subject: Your Student Competitions sign-in code

Your Student Competitions sign-in code is: 042917

It is valid for 20 minutes and can be used once.
If you did not try to sign in, you can ignore this email.
======== END EMAIL ========
```

## The login message

`login_code_message(email: str, code: str, minutes: int) -> EmailMessage`:

- **Subject**: `Your Student Competitions sign-in code`. It never contains the code.
- **Body**: the line `Your Student Competitions sign-in code is: <code>`, the validity in minutes,
  single use, and the ignore note (FR-015).
- **No URL of any kind** (FR-015, edge case "email clients that pre-fetch links").

## Failure handling (caller side, `deliver_login_code`)

- `EmailDeliveryError` or any other exception → `logger.error("Login email not sent: %s", exc)`,
  where the message contains only the status or the type. No address, code or body (FR-039).
- The issued code stays valid. The user can wait, or request a new one within limits (US6-6).
- The user-visible response is unaffected, because it was already sent (research D10).

## Verification

| Test | Covers |
|---|---|
| `tests/unit/test_email.py` | message text (code present, minutes, ignore note, no `http`, code absent from subject); console output format (via `capsys`); memory outbox; Resend request shape, headers and timeout via the fake `post`; non-2xx and network errors raise `EmailDeliveryError` without the key, the address or the body in the message; `build_email_sender` mapping |
| `tests/integration/test_login_privacy.py` | a sender whose `send` raises: the response is unchanged, and the log (`caplog`) contains neither the code nor the address |
