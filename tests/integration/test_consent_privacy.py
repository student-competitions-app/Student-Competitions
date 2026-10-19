"""Nothing personal before consent, nothing personal in a log, nothing left after erasure.

See specs/008-teacher-management-consent/spec.md SC-002, SC-005, SC-007, FR-001–FR-004 and
research D14, and for the student flows of milestone 9, specs/009-classes-students-management
SC-002, SC-008 and FR-057. Every table is scanned column by column, and every log record the
application emits during every flow is captured at `DEBUG` on the root logger.

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
from app.models import AccessLevel, Enrolment, Institution, Role, SchoolClass
from app.services.consent import current_consent_text
from app.services.email import EmailDeliveryError, EmailMessage
from app.services.users import get_user_by_email
from tests.conftest import (
    ADMIN_EMAIL,
    ClientAs,
    make_institution,
    make_teacher,
    sign_in_directly,
    token_from,
)
from tests.integration.test_login_flow import code_from

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


# ---------------------------------------------------------------------------------------------
# Milestone 9: the student flows
# ---------------------------------------------------------------------------------------------

STUDENT = "lesya.test@example.org"
STUDENT_FIRST, STUDENT_LAST = "Lesya", "Ukrainka"
TEACHER = "olha.test@example.org"
TEACHER_FIRST, TEACHER_LAST = "Olha", "Kobylianska"


def student_text_id() -> str:
    with Session(app.state.engine) as session:
        return str(current_consent_text(session, Role.STUDENT).id)


def teacher_scene(client_as: ClientAs) -> tuple[TestClient, int, int, int]:
    """A real Write teacher of "School 5" (Kyiv) with the class "KN-21"; the teacher's browser,
    and the region, institution and class ids."""
    engine = app.state.engine
    school = make_institution(engine, "School 5", "Kyiv")
    make_teacher(
        engine,
        app.state.settings,
        email=TEACHER,
        institutions={school: AccessLevel.WRITE},
        first=TEACHER_FIRST,
        last=TEACHER_LAST,
    )
    teacher = client_as(TEACHER)
    created = teacher.post(
        f"/teacher/students/institutions/{school}/classes",
        data={"name": "KN-21", "year_of_study": "2"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    with Session(engine) as session:
        class_id = session.execute(select(SchoolClass.id)).scalar_one()
        institution = session.get(Institution, school)
        assert institution is not None and class_id is not None
        return teacher, institution.region_id, school, class_id


def test_nothing_about_a_student_is_stored_before_acceptance(
    client: TestClient, client_as: ClientAs, outbox: list[EmailMessage]
) -> None:
    """Milestone 9 SC-002, FR-009: no email, no names, and no enrolment."""
    teacher, _, _, class_id = teacher_scene(client_as)
    response = teacher.post(
        f"/teacher/students/classes/{class_id}/invite",
        data={"email": STUDENT, "first_name": STUDENT_FIRST, "last_name": STUDENT_LAST},
        follow_redirects=False,
    )
    assert response.status_code == 303
    link = f"/invitations/{token_from(outbox[-1])}"
    for _ in range(2):
        assert client.get(link).status_code == 200
    assert found_in_tables(app.state.engine, [STUDENT, "lesya", STUDENT_FIRST, STUDENT_LAST]) == []
    with Session(app.state.engine) as session:
        assert session.execute(select(Enrolment)).all() == []


def test_no_student_flow_logs_an_address_a_name_or_a_link(
    client: TestClient,
    admin_client: TestClient,
    client_as: ClientAs,
    outbox: list[EmailMessage],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Milestone 9 SC-008, FR-057: classes, student invitations, acceptance, edits, moves,
    removal, deactivation with sign-out at every level, blocked sign-in, and data deletion."""
    caplog.set_level(logging.DEBUG)
    teacher, region, school, class_id = teacher_scene(client_as)
    classes = f"/teacher/students/classes/{class_id}"
    sealed: list[str] = []

    # Classes: create (above), edit, a refused duplicate, a second class, deactivate, activate.
    teacher.post(f"{classes}/edit", data={"name": "KN-21a", "year_of_study": "3"})
    teacher.post(
        f"/teacher/students/institutions/{school}/classes",
        data={"name": "kn-21a", "year_of_study": "3"},
    )
    teacher.post(
        f"/teacher/students/institutions/{school}/classes",
        data={"name": "KN-22", "year_of_study": "2"},
    )
    with Session(app.state.engine) as session:
        second = session.execute(
            select(SchoolClass.id).where(SchoolClass.name == "KN-22")
        ).scalar_one()

    # Invite (refused, sent), open, accept, sign in.
    teacher.post(f"{classes}/invite", data={"email": "bad", "first_name": "", "last_name": ""})
    sent = teacher.post(
        f"{classes}/invite",
        data={"email": STUDENT, "first_name": STUDENT_FIRST, "last_name": STUDENT_LAST},
        follow_redirects=False,
    )
    sealed.append(sent.headers["location"].split("sent=")[1])
    teacher.get(sent.headers["location"])
    token = token_from(outbox[-1])
    client.get(f"/invitations/{token}")
    accepted = client.post(
        f"/invitations/{token}", data={"consent_text_id": student_text_id()}, follow_redirects=False
    )
    sealed.append(accepted.headers["location"].split("prefill=")[1])
    student_browser = TestClient(app)
    student_browser.post("/login", data={"email": STUDENT})
    student_browser.post("/login/code", data={"email": STUDENT, "code": code_from(outbox[-1])})
    student_browser.get("/profile")
    teacher.post(
        f"{classes}/invite",
        data={"email": STUDENT, "first_name": STUDENT_FIRST, "last_name": STUDENT_LAST},
    )

    # Edit and move, then deactivation at every level, with blocked sign-in in between.
    with Session(app.state.engine) as session:
        enrolment = session.execute(select(Enrolment)).scalar_one()
    student_id = enrolment.user_id
    teacher.post(
        f"/teacher/students/{student_id}",
        data={"first_name": "Larysa", "last_name": "Kosach", "class_id": str(second)},
    )
    teacher.post(f"/teacher/students/classes/{second}/deactivate")
    client.post("/login", data={"email": STUDENT})
    teacher.post(f"/teacher/students/classes/{second}/activate")
    student_browser.post("/login", data={"email": STUDENT})
    student_browser.post("/login/code", data={"email": STUDENT, "code": code_from(outbox[-1])})
    institution = f"/admin/institutions/regions/{region}/institutions/{school}"
    admin_client.post(f"{institution}/deactivate")
    admin_client.post(f"{institution}/activate")
    admin_client.post(f"/admin/institutions/regions/{region}/deactivate")
    admin_client.post(f"/admin/institutions/regions/{region}/activate")

    # Remove, then delete the data through the emailed link.
    teacher.post(f"/teacher/students/{student_id}/remove")
    teacher.post(f"/teacher/students/classes/{second}/delete")
    client.post("/data-deletion", data={"email": STUDENT})
    deletion = token_from(outbox[-1])
    client.get(f"/data-deletion/confirm/{deletion}")
    client.post(f"/data-deletion/confirm/{deletion}")

    tokens = [token_from(message) for message in outbox if "/invitations/" in message.text]
    forbidden = [
        STUDENT,
        "lesya",
        STUDENT_FIRST,
        STUDENT_LAST,
        "Larysa",
        "Kosach",
        TEACHER,
        TEACHER_FIRST,
        TEACHER_LAST,
        deletion,
        *tokens,
        *sealed,
    ]
    records = [record for record in caplog.records if not record.name.startswith(CLIENT_LOGGERS)]
    messages = [record.getMessage() for record in records]
    for text in messages:
        for needle in forbidden:
            assert needle.lower() not in text.lower(), text
        assert not re.search(r"/invitations/[A-Za-z0-9_-]{20,}", text), text
    for expected in (
        r"Class created: id=\d+ institution_id=\d+",
        r"Class updated: id=\d+",
        r"Class deactivated: id=\d+ sessions=\d+",
        r"Invitation sent: inviter_id=\d+ role=student institutions=0 class_id=\d+",
        r"Invitation accepted: user_id=\d+ role=student created",
        r"Student updated: user_id=\d+ moved=True",
        r"Students signed out: (institution|region)_id=\d+ sessions=\d+",
        r"Student removed: user_id=\d+ deactivated=True",
        r"Class deleted: id=\d+ institution_id=\d+",
    ):
        assert any(re.match(expected, text) for text in messages), expected
