"""Sign-in resists guessing, flooding and account discovery.

See the spec's user story 5, specs/004-email-otp-auth/research.md#d5 and #d10. Known, unknown
and inactive addresses get the same response and the same timing; a code dies after 5 wrong
attempts; code requests are limited per address and per client, in the database. Every test runs
once per database engine.
"""

import logging
import re
import statistics
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, text, update
from sqlmodel import Session, select

from app.core.db import utc_now
from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.models import LoginCode, RateLimitHit, Role, User, UserSession
from app.services.email import EmailDeliveryError, EmailMessage
from tests.conftest import ADMIN_EMAIL
from tests.integration.test_login_flow import (
    INVALID_CODE,
    code_from,
    request_code,
    submit_code,
)

TOO_MANY = "Too many attempts. Please try again later."
UNKNOWN = "nobody@example.com"
INACTIVE = "former@example.com"


def anonymised(body: str, email: str) -> str:
    return body.replace(email, "someone@example.com")


def clear_rate_limits(session: Session) -> None:
    session.execute(delete(RateLimitHit))
    session.commit()


@pytest.fixture
def inactive_user(session: Session) -> None:
    session.add(User(email=INACTIVE, role=Role.ADMIN, is_active=False))
    session.commit()


def test_us5_1_known_unknown_and_inactive_addresses_look_the_same(
    client: TestClient, inactive_user: None
) -> None:
    responses = {
        email: request_code(client, email=email) for email in (ADMIN_EMAIL, UNKNOWN, INACTIVE)
    }
    statuses = {response.status_code for response in responses.values()}
    bodies = {anonymised(response.text, email) for email, response in responses.items()}
    cookies = {"set-cookie" in response.headers for response in responses.values()}
    assert statuses == {200}
    assert len(bodies) == 1
    assert cookies == {False}


def test_sc004_known_and_unknown_addresses_take_the_same_time(
    client: TestClient, session: Session
) -> None:
    """Medians of 50 interleaved submissions each differ by less than 100 ms."""
    timings: dict[str, list[float]] = {ADMIN_EMAIL: [], UNKNOWN: []}
    for _ in range(50):
        for email in timings:
            clear_rate_limits(session)
            started = time.perf_counter()
            assert request_code(client, email=email).status_code == 200
            timings[email].append(time.perf_counter() - started)
    difference = abs(statistics.median(timings[ADMIN_EMAIL]) - statistics.median(timings[UNKNOWN]))
    assert difference < 0.1, f"medians differ by {difference * 1000:.1f} ms"


def test_us5_2_a_code_dies_after_five_wrong_attempts(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    request_code(client)
    code = code_from(outbox[-1])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        response = submit_code(client, wrong)
        assert response.status_code == 400
        assert INVALID_CODE in response.text
    response = submit_code(client, code)
    assert response.status_code == 400
    assert INVALID_CODE in response.text
    session.expire_all()
    assert session.exec(select(LoginCode.attempts)).one() == 5
    assert session.exec(select(func.count()).select_from(UserSession)).one() == 0


def test_us5_3_at_most_five_code_requests_per_address_per_hour(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    known = [request_code(client, email=ADMIN_EMAIL) for _ in range(6)]
    unknown = [request_code(client, email=UNKNOWN) for _ in range(6)]
    assert [r.status_code for r in known] == [200] * 5 + [429]
    assert TOO_MANY in known[-1].text
    assert len(outbox) == 5
    assert [r.status_code for r in unknown] == [r.status_code for r in known]
    assert [anonymised(r.text, UNKNOWN) for r in unknown] == [
        anonymised(r.text, ADMIN_EMAIL) for r in known
    ]


def test_us5_4_at_most_twenty_code_requests_per_client_per_hour(client: TestClient) -> None:
    statuses = [request_code(client, email=f"user{i}@example.com").status_code for i in range(21)]
    assert statuses == [200] * 20 + [429]


def test_us5_5_the_limits_survive_a_restart(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    """R4: the hits are in the database, not in the process."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)
    with TestClient(app) as first:
        assert [request_code(first).status_code for _ in range(5)] == [200] * 5
    with TestClient(app) as second:
        response = request_code(second)
        assert response.status_code == 429
        assert TOO_MANY in response.text


def test_us5_6_only_the_newest_code_works(client: TestClient, outbox: list[EmailMessage]) -> None:
    request_code(client)
    first = code_from(outbox[-1])
    request_code(client)
    second = code_from(outbox[-1])
    if first != second:
        assert submit_code(client, first).status_code == 400
    assert submit_code(client, second).status_code == 303


def test_us5_7_every_bad_code_gets_the_identical_page(
    client: TestClient, outbox: list[EmailMessage], session: Session
) -> None:
    bodies: dict[str, str] = {}

    request_code(client)
    code = code_from(outbox[-1])
    bodies["wrong"] = submit_code(client, "999999" if code != "999999" else "888888").text
    bodies["malformed"] = submit_code(client, "abc").text

    session.execute(update(LoginCode).values(expires_at=utc_now()))
    session.commit()
    bodies["expired"] = submit_code(client, code).text

    request_code(client)
    code = code_from(outbox[-1])
    assert submit_code(client, code).status_code == 303
    client.cookies.clear()
    bodies["used"] = submit_code(client, code).text

    request_code(client)
    code = code_from(outbox[-1])
    session.execute(update(LoginCode).values(attempts=5))
    session.commit()
    bodies["exhausted"] = submit_code(client, code).text

    bodies["no such address"] = anonymised(submit_code(client, code, email=UNKNOWN).text, UNKNOWN)
    bodies = {k: anonymised(v, ADMIN_EMAIL) for k, v in bodies.items()}
    assert len(set(bodies.values())) == 1, sorted(bodies)


def test_malformed_addresses_are_not_counted(client: TestClient, session: Session) -> None:
    for _ in range(10):
        assert request_code(client, email="not-an-email").status_code == 400
    assert session.exec(select(func.count()).select_from(RateLimitHit)).one() == 0


def test_rate_limit_keys_are_stored_hashed(client: TestClient, session: Session) -> None:
    request_code(client)
    rows = session.exec(select(RateLimitHit)).all()
    assert {row.bucket for row in rows} == {"code_email", "code_client"}
    for row in rows:
        assert re.fullmatch(r"[0-9a-f]{64}", row.key_hash)
    dump = " ".join(
        str(value)
        for row in session.execute(text("SELECT * FROM rate_limit_hits"))
        for value in row
    )
    assert ADMIN_EMAIL not in dump
    assert "testclient" not in dump


# ---------------------------------------------------------------------------------------------
# Delivery failures and secrets in output (US6-5, US6-6)
# ---------------------------------------------------------------------------------------------


class FailingSender:
    def send(self, message: EmailMessage) -> None:
        raise EmailDeliveryError("Resend returned HTTP 500")


def test_us6_6_a_delivery_failure_is_invisible_and_logged_without_detail(
    client: TestClient,
    inactive_user: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    usual = request_code(client, email=UNKNOWN)
    memory = app.state.email_sender
    monkeypatch.setattr(app.state, "email_sender", FailingSender())
    with caplog.at_level(logging.DEBUG):
        failed = request_code(client, email=ADMIN_EMAIL)
    assert failed.status_code == usual.status_code == 200
    assert anonymised(failed.text, ADMIN_EMAIL) == anonymised(usual.text, UNKNOWN)
    messages = [record.getMessage() for record in caplog.records]
    assert "Login email not sent: Resend returned HTTP 500" in messages
    for message in messages:
        assert ADMIN_EMAIL not in message
        assert not re.search(r"\b[0-9]{6}\b", message)

    monkeypatch.setattr(app.state, "email_sender", memory)
    assert request_code(client).status_code == 200
    assert code_from(memory.outbox[-1])


def test_us6_5_nothing_secret_reaches_the_logs_or_the_output(
    client: TestClient,
    outbox: list[EmailMessage],
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with caplog.at_level(logging.DEBUG):
        request_code(client)
        code = code_from(outbox[-1])
        response = submit_code(client, code)
        cookie = client.cookies[SESSION_COOKIE_NAME]
        token = cookie.split(".")[0]
        client.get("/")
        client.post("/logout")
    captured = capsys.readouterr()
    output = "\n".join(
        [captured.out, captured.err, *(record.getMessage() for record in caplog.records)]
    )
    assert response.status_code == 303
    for secret in (code, token, cookie, app.state.settings.secret_key, ADMIN_EMAIL):
        assert secret not in output
