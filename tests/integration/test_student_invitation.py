"""User story 2: a teacher invites a student, who accepts and signs in.

See specs/009-classes-students-management/spec.md US2, FR-025–FR-029 and contracts/http-routes.md
§2.3. The teacher is real: Write to "Kyiv Polytechnic Institute" (Kyiv), where the class "KN-21"
(year 2) is. Links are read from the `memory` outbox. Every case runs on both engines.
"""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session, func, select

from app.main import app
from app.models import (
    AccessLevel,
    ConsentRecord,
    ConsentText,
    Enrolment,
    Institution,
    RateLimitHit,
    Role,
    SchoolClass,
    User,
)
from app.services.email import EmailDeliveryError, EmailMessage
from app.services.rate_limits import (
    BUCKET_INVITE_INVITER,
    BUCKET_INVITE_STUDENT_INVITER,
    INVITER_INVITE_LIMIT,
    STUDENT_INVITER_INVITE_LIMIT,
    LimitCheck,
    allow,
)
from app.services.students import remove_student
from app.services.users import get_roles, get_user_by_email
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    enrol_student,
    make_class,
    make_institution,
    make_teacher,
    token_from,
)
from tests.integration.test_consent_privacy import found_in_tables
from tests.integration.test_login_flow import code_from

OLENA = "olena@example.org"
TARAS = "taras@example.org"
FIRST, LAST = "Taras", "Shevchenko"


@dataclass(frozen=True)
class Scene:
    teacher: TestClient
    teacher_id: int
    institution: int
    region: int
    school_class: int

    @property
    def invite_path(self) -> str:
        return f"/teacher/students/classes/{self.school_class}/invite"

    @property
    def selection(self) -> str:
        return (
            f"/teacher/students?region={self.region}&institution={self.institution}"
            f"&class={self.school_class}"
        )


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs) -> Scene:
    engine = app.state.engine
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    teacher_id = make_teacher(
        engine, app.state.settings, email=OLENA, institutions={institution: AccessLevel.WRITE}
    )
    school_class = make_class(engine, institution, "KN-21", 2)
    with Session(engine) as session:
        row = session.get(Institution, institution)
        assert row is not None
        region = row.region_id
    return Scene(
        teacher=client_as(OLENA),
        teacher_id=teacher_id,
        institution=institution,
        region=region,
        school_class=school_class,
    )


def form(email: str = TARAS, **overrides: str) -> dict[str, str]:
    return {"email": email, "first_name": FIRST, "last_name": LAST, **overrides}


def send(scene: Scene, email: str = TARAS, **overrides: str):  # type: ignore[no-untyped-def]
    return scene.teacher.post(
        scene.invite_path, data=form(email, **overrides), follow_redirects=False
    )


def count(model: type) -> int:
    with Session(app.state.engine) as session:
        return session.exec(select(func.count()).select_from(model)).one()


def student_text_id() -> int:
    with Session(app.state.engine) as session:
        text = session.exec(select(ConsentText).where(ConsentText.role == "student")).one()
        assert text.id is not None
        return text.id


# ---------------------------------------------------------------------------------------------
# The form
# ---------------------------------------------------------------------------------------------


def test_add_student_opens_the_form_for_the_class(scene: Scene) -> None:
    """US2-1."""
    page = scene.teacher.get(scene.selection).text
    add = [a for a in html.links(page, "main") if a.href == scene.invite_path]
    assert [(a.text, a.attrs.get("role")) for a in add] == [("Add student", "button")]
    body = scene.teacher.get(scene.invite_path).text
    for shown in (
        "Invite a student to “KN-21”",
        "Kyiv Polytechnic Institute (Kyiv)",
        "KN-21 · year 2",
        "Send invitation",
        "Nothing about them is stored unless they accept.",
    ):
        assert shown in body
    names = [i.name for f in html.forms(body, "main") for i in f.inputs]
    assert {"email", "first_name", "last_name"} <= set(names)


# ---------------------------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------------------------


def test_a_valid_form_sends_the_invitation_and_stores_nothing(
    scene: Scene, outbox: list[EmailMessage]
) -> None:
    """US2-2, US2-7, FR-028, FR-029, SC-002."""
    response = send(scene)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"{scene.selection}&sent=")
    assert "@" not in location and "taras" not in location.lower()
    assert f"Invitation sent to {TARAS}" in scene.teacher.get(location).text

    [message] = outbox
    assert message.to == TARAS
    assert message.subject == "You are invited to Student Competitions as a student"
    for statement in (
        f"Olena Kovalenko ({OLENA}) invites you to Student Competitions as a student.",
        "Role: Student",
        "- Educational institution: Kyiv Polytechnic Institute (Kyiv)",
        "- Class: KN-21 · year 2",
        "Nothing about you is stored unless you accept",
        "http://testserver/invitations/",
        "This invitation expires on",
    ):
        assert statement in message.text
    assert "<" not in message.text
    assert found_in_tables(app.state.engine, [TARAS, "taras@", FIRST, LAST]) == []
    assert count(Enrolment) == 0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"email": "not-an-email"}, "Enter a valid email address."),
        ({"first_name": "   "}, "Enter a first name."),
        ({"last_name": "a" * 101}, "The last name can be at most 100 characters."),
        ({"first_name": "Ta\tras"}, "The first name cannot contain tabs"),
    ],
    ids=["email", "blank-first", "long-last", "control"],
)
def test_an_invalid_form_is_refused_with_the_values_kept(
    scene: Scene, outbox: list[EmailMessage], overrides: dict[str, str], message: str
) -> None:
    """US2-3."""
    submitted = form(**overrides)
    response = scene.teacher.post(scene.invite_path, data=submitted)
    assert response.status_code == 400
    assert message in response.text
    assert html.control(response.text, "email")["value"] == submitted["email"]
    assert outbox == []
    assert count(RateLimitHit) == 0


def test_an_existing_student_is_refused_without_naming_their_class(
    scene: Scene, client_as: ClientAs, outbox: list[EmailMessage]
) -> None:
    """US2-4, FR-026: the cast's student, and a real student of another institution who is now
    blocked."""
    engine = app.state.engine
    odesa = make_institution(engine, "Odesa College", "Odesa")
    make_teacher(
        engine,
        app.state.settings,
        email="petro@example.org",
        institutions={odesa: AccessLevel.WRITE},
        first="Petro",
        last="Bondar",
    )
    odesa_class = make_class(engine, odesa, "OC-7", 3)
    enrol_student(
        engine,
        app.state.settings,
        email="ivan@example.org",
        class_id=odesa_class,
        inviter_email="petro@example.org",
    )
    with Session(engine) as session:
        row = session.get(SchoolClass, odesa_class)
        assert row is not None
        row.is_active = False
        session.add(row)
        session.commit()
    for address in (STUDENT_EMAIL, "ivan@example.org"):
        response = send(scene, address)
        assert response.status_code == 400
        assert "This email already belongs to a student" in response.text
        assert html.control(response.text, "email")["value"] == address
        assert "Odesa" not in response.text
        assert "OC-7" not in response.text
    assert outbox == []


def test_a_teacher_an_administrator_and_a_former_student_can_be_invited(
    scene: Scene, outbox: list[EmailMessage]
) -> None:
    """US2-5."""
    former = enrol_student(
        app.state.engine,
        app.state.settings,
        email="former@example.org",
        class_id=scene.school_class,
        inviter_email=OLENA,
    )
    with Session(app.state.engine) as session:
        remove_student(session, app.state.settings, scene.teacher_id, former)
        user = session.get(User, former)
        assert user is not None and not user.is_active
    for address in (TEACHER_EMAIL, ADMIN_EMAIL, "former@example.org"):
        assert send(scene, address).status_code == 303
    assert [message.to for message in outbox] == [TEACHER_EMAIL, ADMIN_EMAIL, "former@example.org"]


# ---------------------------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------------------------


def fill(bucket: str, key: str, hits: int) -> None:
    """Record `hits` hits directly, as that many earlier requests would have."""
    with Session(app.state.engine) as session:
        for _ in range(hits):
            assert allow(session, app.state.settings.secret_key, [LimitCheck(bucket, key, 10**6)])


def test_a_teacher_has_100_student_invitations_an_hour(
    scene: Scene, outbox: list[EmailMessage]
) -> None:
    """US2-6, FR-027."""
    fill(BUCKET_INVITE_STUDENT_INVITER, str(scene.teacher_id), STUDENT_INVITER_INVITE_LIMIT - 1)
    assert send(scene, "one@example.org").status_code == 303
    response = send(scene, "two@example.org")
    assert response.status_code == 429
    assert "Too many invitations. Please try again later." in response.text
    assert html.control(response.text, "email")["value"] == "two@example.org"
    assert [message.to for message in outbox] == ["one@example.org"]


def test_an_address_has_5_invitations_an_hour_across_both_roles(
    scene: Scene, admin_client: TestClient, outbox: list[EmailMessage]
) -> None:
    """FR-027, spec Assumptions: the per-address limit is shared by teacher and student
    invitations."""
    for _ in range(3):
        admin_client.post(
            "/admin/teachers/invite",
            data={
                **form(),
                "institution": [str(scene.institution)],
                "access": [f"{scene.institution}:read"],
            },
        )
    for _ in range(2):
        assert send(scene).status_code == 303
    assert len(outbox) == 5
    assert send(scene).status_code == 429
    assert len(outbox) == 5


def test_an_administrator_who_teaches_has_separate_limits(
    scene: Scene, client_as: ClientAs, outbox: list[EmailMessage]
) -> None:
    """Spec Edge Cases: 20 teacher invitations and 100 student invitations, counted apart."""
    admin_id = make_teacher(
        app.state.engine,
        app.state.settings,
        email=ADMIN_EMAIL,
        institutions={scene.institution: AccessLevel.WRITE},
    )
    as_teacher = client_as(ADMIN_EMAIL, Role.TEACHER)
    as_admin = client_as(ADMIN_EMAIL, Role.ADMIN)

    def teacher_invite(address: str) -> int:
        return as_admin.post(
            "/admin/teachers/invite",
            data={
                **form(address),
                "institution": [str(scene.institution)],
                "access": [f"{scene.institution}:read"],
            },
            follow_redirects=False,
        ).status_code

    def student_invite(address: str) -> int:
        return as_teacher.post(
            f"/teacher/students/classes/{scene.school_class}/invite",
            data=form(address),
            follow_redirects=False,
        ).status_code

    fill(BUCKET_INVITE_STUDENT_INVITER, str(admin_id), STUDENT_INVITER_INVITE_LIMIT)
    assert student_invite("s1@example.org") == 429
    assert teacher_invite("t1@example.org") == 303
    fill(BUCKET_INVITE_INVITER, str(admin_id), INVITER_INVITE_LIMIT - 1)
    assert teacher_invite("t2@example.org") == 429


def test_a_send_failure_keeps_the_values_and_still_counts(
    scene: Scene, outbox: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec Edge Cases: 503 with every value; nothing stored; the attempt counts."""

    def fail(message: EmailMessage) -> None:
        raise EmailDeliveryError("Resend returned HTTP 500")

    monkeypatch.setattr(app.state.email_sender, "send", fail)
    response = send(scene)
    assert response.status_code == 503
    assert "The invitation email could not be sent. Please try again." in response.text
    assert html.control(response.text, "email")["value"] == TARAS
    assert html.control(response.text, "last_name")["value"] == LAST
    monkeypatch.undo()
    assert get_user_by_email(Session(app.state.engine), TARAS) is None
    assert count(RateLimitHit) == 2


def test_a_deactivated_class_takes_no_invitation(scene: Scene, outbox: list[EmailMessage]) -> None:
    """FR-005, spec Assumptions: 409 with no form."""
    scene.teacher.post(f"/teacher/students/classes/{scene.school_class}/deactivate")
    page = scene.teacher.get(scene.invite_path)
    assert page.status_code == 409
    assert "This class is deactivated. Students cannot be added to it." in page.text
    assert "email" not in [i.name for f in html.forms(page.text) for i in f.inputs]
    response = send(scene)
    assert response.status_code == 409
    assert outbox == []


# ---------------------------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------------------------


def invited(scene: Scene, outbox: list[EmailMessage]) -> str:
    assert send(scene).status_code == 303
    return f"/invitations/{token_from(outbox[-1])}"


def test_the_consent_text_names_team_memberships_and_is_still_version_1(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """Milestone 11.1 US7-4, FR-015: what is stored, who sees it, and what withdrawal erases."""
    text = html.text(client.get(invited(scene, outbox)).text, "main")
    for shown in (
        "and your team memberships: the teams of your educational institution that you belong to",
        "Your data, including your teams, is seen by the teachers linked to your educational "
        "institution",
        "Your names, your email address, your class and your team memberships are then erased",
    ):
        assert shown in text
    with Session(app.state.engine) as session:
        (row,) = session.exec(select(ConsentText).where(ConsentText.role == "student")).all()
    assert (row.version, row.published_at.date().isoformat()) == (1, "2026-10-19")


def test_the_acceptance_page_shows_everything_and_changes_nothing(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US2-8, FR-031, FR-038."""
    link = invited(scene, outbox)
    for _ in range(2):
        page = client.get(link)
        assert page.status_code == 200
    body = page.text
    for shown in (
        f"Olena Kovalenko ({OLENA}) invites you to join as a student.",
        TARAS,
        FIRST,
        LAST,
        "Educational institution: Kyiv Polytechnic Institute (Kyiv)",
        "Class: KN-21 · year 2",
        "your class, which also records your educational institution and your year of study, and "
        "your team memberships",
        "If you are already a teacher or a student, your current names are kept.",
        "I agree",
    ):
        assert shown in body
    assert ("Role", "Student") in html.details(body)
    assert html.control(body, "consent_text_id")["value"] == str(student_text_id())
    assert get_user_by_email(Session(app.state.engine), TARAS) is None
    assert count(Enrolment) == 0


def test_i_agree_creates_the_student_and_their_enrolment(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US2-9, US2-11, FR-033, FR-040."""
    link = invited(scene, outbox)
    accepted = client.post(
        link,
        data={"consent_text_id": str(student_text_id()), "class_id": "999", "institution_id": "7"},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    assert accepted.headers["location"].startswith("/login?prefill=")
    with Session(app.state.engine) as session:
        taras = get_user_by_email(session, TARAS)
        assert taras is not None and taras.id is not None and taras.is_active
        assert (taras.first_name, taras.last_name) == (FIRST, LAST)
        assert get_roles(session, taras.id) == (Role.STUDENT,)
        enrolment = session.get(Enrolment, taras.id)
        assert enrolment is not None and enrolment.class_id == scene.school_class
        [record] = session.exec(
            select(ConsentRecord).where(ConsentRecord.user_id == taras.id)
        ).all()
        assert record.user_id == taras.id
        assert record.consent_text_id == student_text_id()
        assert record.inviter_id == scene.teacher_id
    columns = {
        column["name"] for column in inspect(app.state.engine).get_columns("consent_records")
    }
    assert not {"institution_id", "class_id"} & columns


def test_the_student_signs_in_and_sees_their_profile(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US2-10, FR-045, FR-046."""
    link = invited(scene, outbox)
    client.post(link, data={"consent_text_id": str(student_text_id())})
    client.post("/login", data={"email": TARAS})
    signed_in = client.post(
        "/login/code",
        data={"email": TARAS, "code": code_from(outbox[-1])},
        follow_redirects=False,
    )
    assert signed_in.status_code == 303
    body = client.get("/profile").text
    for shown in (
        TARAS,
        FIRST,
        LAST,
        " UTC · Student · version 1",
        "your class, which also records",
        "Corrections to student data are made by a teacher of your educational institution.",
    ):
        assert shown in html.text(body, "main")
    for pair in (
        ("Roles", "Student"),
        ("Educational institution", "Kyiv Polytechnic Institute (Kyiv)"),
        ("Class", "KN-21"),
        ("Year of study", "2"),
    ):
        assert pair in html.details(body)
    assert "Corrections to teacher data" not in body
    assert client.get("/student").status_code == 200


def test_reloading_never_repeats_an_invitation_or_an_acceptance(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """SC-009, FR-056."""
    response = send(scene)
    for _ in range(2):
        assert scene.teacher.get(response.headers["location"]).status_code == 200
    assert len(outbox) == 1
    link = f"/invitations/{token_from(outbox[0])}"
    data = {"consent_text_id": str(student_text_id())}
    first = client.post(link, data=data, follow_redirects=False)
    assert first.status_code == 303
    again = client.post(link, data=data, follow_redirects=False)
    assert again.status_code == 303
    assert again.headers["location"] == link
    assert "You are already a student." in client.get(link).text
    with Session(app.state.engine) as session:
        [taras] = session.exec(select(User).where(User.email == TARAS)).all()
        assert taras.id is not None
        assert get_roles(session, taras.id) == (Role.STUDENT,)
        records = session.exec(select(ConsentRecord).where(ConsentRecord.user_id == taras.id))
        assert len(records.all()) == 1
    assert count(Enrolment) == 1


def test_the_students_of_the_class_are_listed(
    scene: Scene, client: TestClient, outbox: list[EmailMessage]
) -> None:
    """FR-054: name and email, once accepted."""
    link = invited(scene, outbox)
    client.post(link, data={"consent_text_id": str(student_text_id())})
    body = scene.teacher.get(scene.selection).text
    rows = [(row["Name"], row["Email"]) for row in html.table_rows(body)]
    assert (f"{LAST} {FIRST}", TARAS) in rows
    assert "No students in this class yet" not in body
