"""Nothing personal before consent, nothing personal in a log, nothing left after erasure.

See specs/008-teacher-management-consent/spec.md SC-002, SC-005, SC-007, FR-001–FR-004 and
research D14. Every table is scanned column by column, and every log record the application emits
during every flow of this milestone is captured at `DEBUG` on the root logger.

The test client's own loggers (`httpx`, `httpcore`) are left out of the log scan: they record the
URLs the test requests, on the client side, and are not part of the application.
"""

import logging
import re
from collections.abc import Iterable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, select
from sqlmodel import Session

from app.main import app
from app.models import Role
from app.services.consent import current_consent_text
from app.services.email import EmailDeliveryError, EmailMessage
from app.services.users import get_user_by_email
from tests.conftest import ADMIN_EMAIL, ClientAs, make_institution, sign_in_directly, token_from

INVITED = "zoryana.test@example.org"
ADMIN_TEACHER = "admin.student@example.com"
FIRST, LAST = "Zoryana", "Hrytsenko"
SECRETS = [INVITED, "zoryana.test", FIRST, LAST]
CLIENT_LOGGERS = ("httpx", "httpcore")


def every_value(engine: Engine) -> Iterable[tuple[str, str, str]]:
    """`(table, column, value)` for every non-null value of every table."""
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.connect() as connection:
        for table in metadata.sorted_tables:
            for row in connection.execute(select(table)):
                for column, value in row._mapping.items():
                    if value is not None:
                        yield table.name, str(column), str(value)


def found_in_tables(engine: Engine, needles: Iterable[str]) -> list[str]:
    lowered = [needle.lower() for needle in needles]
    return [
        f"{table}.{column}"
        for table, column, value in every_value(engine)
        if any(needle in value.lower() for needle in lowered)
    ]


def form(school: int, email: str = INVITED, **overrides: str) -> dict[str, object]:
    return {
        "email": email,
        "first_name": FIRST,
        "last_name": LAST,
        "institution": [str(school)],
        "access": [f"{school}:write"],
        **overrides,
    }


def consent_text_id() -> str:
    with Session(app.state.engine) as session:
        return str(current_consent_text(session, Role.TEACHER).id)


def test_nothing_personal_is_stored_before_acceptance(
    client: TestClient, admin_client: TestClient, outbox: list[EmailMessage]
) -> None:
    """SC-002, FR-001–FR-003."""
    school = make_institution(app.state.engine, "School 5", "Kyiv")
    assert admin_client.post("/admin/teachers/invite", data=form(school)).status_code == 200
    link = f"/invitations/{token_from(outbox[-1])}"
    for _ in range(2):
        assert client.get(link).status_code == 200
    assert found_in_tables(app.state.engine, SECRETS) == []


def test_no_flow_logs_an_address_a_name_or_a_token(
    client: TestClient,
    admin_client: TestClient,
    client_as: ClientAs,
    outbox: list[EmailMessage],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC-007, FR-004: every flow of the milestone, with every record captured."""
    caplog.set_level(logging.DEBUG)
    school = make_institution(app.state.engine, "School 5", "Kyiv")
    sealed_values: list[str] = []

    def invite(email: str, **overrides: str) -> str:
        response = admin_client.post(
            "/admin/teachers/invite", data=form(school, email, **overrides), follow_redirects=False
        )
        if response.status_code == 303:
            sealed_values.append(response.headers["location"].split("sent=")[1])
        return token_from(outbox[-1])

    # Invitations: invalid, success, rate-limited, and a send failure.
    admin_client.post("/admin/teachers/invite", data=form(school, "bad", first_name=""))
    token = invite(INVITED)
    for number in range(4):
        invite(INVITED, first_name=f"{FIRST}{number}")
    admin_client.post("/admin/teachers/invite", data=form(school))
    sender = app.state.email_sender

    def fail(message: EmailMessage) -> None:
        raise EmailDeliveryError("Resend returned HTTP 500")

    monkeypatch.setattr(sender, "send", fail)
    admin_client.post("/admin/teachers/invite", data=form(school, "other.person@example.org"))
    monkeypatch.undo()

    # Opening, refusals, accepting, and "already a teacher".
    client.get(f"/invitations/{token}")
    client.get(f"/invitations/{token[:-3]}xyz")
    accepted = client.post(
        f"/invitations/{token}", data={"consent_text_id": consent_text_id()}, follow_redirects=False
    )
    sealed_values.append(accepted.headers["location"].split("prefill=")[1])
    client.get(accepted.headers["location"])
    client.post(f"/invitations/{token}", data={"consent_text_id": consent_text_id()})
    client.get(f"/invitations/{token}")

    # Edit, profile, remove.
    with Session(app.state.engine) as session:
        invited = get_user_by_email(session, INVITED)
        assert invited is not None
    admin_client.post(
        f"/admin/teachers/{invited.id}", data=form(school, first_name="Zoryana-Maria")
    )
    browser = TestClient(app)
    sign_in_directly(browser, INVITED)
    browser.get("/profile")
    browser.get("/profile/withdraw")
    admin_client.post(f"/admin/teachers/{invited.id}/remove")

    # Data deletion: known and unknown addresses, the link, and its confirmation.
    client.post("/data-deletion", data={"email": INVITED})
    client.post("/data-deletion", data={"email": "nobody.at.all@example.org"})
    deletion = token_from(outbox[-1])
    client.get(f"/data-deletion/confirm/{deletion}")
    client.post(f"/data-deletion/confirm/{deletion}")

    # Withdrawal by an administrator who teaches.
    admin_teacher_token = invite(ADMIN_TEACHER)
    client.post(f"/invitations/{admin_teacher_token}", data={"consent_text_id": consent_text_id()})
    client_as(ADMIN_TEACHER, Role.ADMIN).post("/profile/withdraw")

    tokens = [token_from(message) for message in outbox]
    forbidden = [*SECRETS, ADMIN_TEACHER, ADMIN_EMAIL, *tokens, *sealed_values]
    application_records = [
        record for record in caplog.records if not record.name.startswith(CLIENT_LOGGERS)
    ]
    assert application_records, "the flows should log something"
    for record in application_records:
        text = record.getMessage()
        for needle in forbidden:
            assert needle.lower() not in text.lower(), (record.name, text)
    assert any(
        re.match(r"Invitation accepted: user_id=\d+", r.getMessage()) for r in caplog.records
    )


def test_nothing_is_left_after_withdrawal_and_deletion(
    client: TestClient,
    admin_client: TestClient,
    client_as: ClientAs,
    outbox: list[EmailMessage],
) -> None:
    """SC-005: after erasure the names are nowhere, and the address stays only for an
    administrator."""
    school = make_institution(app.state.engine, "School 5", "Kyiv")
    admin_client.post("/admin/teachers/invite", data=form(school))
    client.post(
        f"/invitations/{token_from(outbox[-1])}", data={"consent_text_id": consent_text_id()}
    )
    admin_client.post(
        "/admin/teachers/invite", data=form(school, ADMIN_TEACHER, first_name="Bohdana")
    )
    client.post(
        f"/invitations/{token_from(outbox[-1])}", data={"consent_text_id": consent_text_id()}
    )
    assert found_in_tables(app.state.engine, [INVITED, LAST, "Bohdana"])

    client.post("/data-deletion", data={"email": INVITED})
    client.post(f"/data-deletion/confirm/{token_from(outbox[-1])}")
    client_as(ADMIN_TEACHER, Role.ADMIN).post("/profile/withdraw")

    assert found_in_tables(app.state.engine, [INVITED, "zoryana", FIRST, LAST, "Bohdana"]) == []
    assert found_in_tables(app.state.engine, [ADMIN_TEACHER]) == ["users.email"]
