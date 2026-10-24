"""User story 4: a person sees their profile and withdraws consent.

See specs/008-teacher-management-consent/spec.md US4 (scenarios 1–8), FR-043–FR-047 and
contracts/http-routes.md §4. Every case runs on both engines.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.models import (
    AccessLevel,
    ConsentRecord,
    Enrolment,
    Institution,
    Role,
    User,
    UserSession,
)
from app.routers.profile import NOTHING_TO_WITHDRAW
from app.services.classes import set_class_active
from app.services.consent import get_cutoff
from app.services.email import EmailMessage
from app.services.teachers import remove_teacher
from app.services.users import get_roles
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    enrol_student,
    invite_and_accept,
    make_class,
    make_institution,
    make_teacher,
    sign_in_directly,
)

OLENA = "olena@example.org"


@pytest.fixture
def places(client: TestClient) -> dict[str, int]:
    engine = app.state.engine
    return {
        "kyiv": make_institution(engine, "Kyiv Lyceum", "Kyiv"),
        "lviv": make_institution(engine, "Lviv School", "Lviv"),
    }


def a_teacher(places: dict[str, int], email: str = OLENA) -> int:
    return invite_and_accept(
        app.state.engine,
        app.state.settings,
        email=email,
        institutions={places["kyiv"]: AccessLevel.WRITE, places["lviv"]: AccessLevel.READ},
        can_create=True,
    )


def signed_in(email: str, role: Role | None = None) -> TestClient:
    browser = TestClient(app)
    if role is None:
        sign_in_directly(browser, email)
    else:
        sign_in_directly(browser, email, role)
    return browser


def person(user_id: int) -> User:
    with Session(app.state.engine) as session:
        found = session.get(User, user_id)
        assert found is not None
        return found


def test_a_teacher_sees_everything_stored_on_their_consent(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US4-1, FR-043."""
    a_teacher(places)
    lviv = places["lviv"]
    with Session(app.state.engine) as session:
        region_id = session.get(Institution, lviv).region_id  # type: ignore[union-attr]
    admin_client.post(
        f"/admin/institutions/regions/{region_id}/institutions/{lviv}/deactivate",
        follow_redirects=False,
    )
    body = signed_in(OLENA).get("/profile").text
    main = html.text(body, "main")
    for shown in (
        OLENA,
        "Olena",
        "Kovalenko",
        "Kyiv Lyceum (Kyiv) — Write",
        "Lviv School (Lviv) — Read Deactivated",
        "Accepted ",
        " UTC · Teacher · version 1",
        "Resend",
        "Corrections to teacher data are made by an administrator.",
    ):
        assert shown in main
    assert ("Roles", "Teacher") in html.details(body)
    assert ("Can create competitions", "Yes") in html.details(body)
    assert html.badges(body) == ["Deactivated"]
    assert "/profile/withdraw" in [a.href for a in html.content_links(body)]


def test_an_administrator_without_consent_data_sees_only_the_basics(
    admin_client: TestClient,
) -> None:
    """US4-2, FR-045."""
    body = admin_client.get("/profile").text
    assert ADMIN_EMAIL in body
    assert ("Roles", "Administrator") in html.details(body)
    assert "First name" not in body
    assert "Your consent" not in body
    assert "/profile/withdraw" not in body


@pytest.mark.parametrize("email", [STUDENT_EMAIL, TEACHER_EMAIL])
def test_every_role_can_open_its_profile(client_as: ClientAs, email: str) -> None:
    response = client_as(email).get("/profile")
    assert response.status_code == 200
    assert email in response.text


def test_the_profile_is_read_only(places: dict[str, int], client: TestClient) -> None:
    """FR-044: no form at all; withdrawing starts from a link."""
    a_teacher(places)
    body = signed_in(OLENA).get("/profile").text
    (main,) = html.parse(body).find_all("main")
    assert main.find_all("form") == []
    assert main.find_all("input") == []


def test_the_withdraw_confirmation_changes_nothing(
    places: dict[str, int], client: TestClient
) -> None:
    """US4-3, FR-046."""
    user_id = a_teacher(places)
    page = signed_in(OLENA).get("/profile/withdraw")
    assert page.status_code == 200
    for shown in (
        "Your first name (Olena) and last name (Kovalenko)",
        f"Your email address ({OLENA})",
        "These roles are removed: Teacher.",
        "You will be signed out everywhere.",
        "You will no longer be able to sign in.",
    ):
        assert shown in page.text
    assert person(user_id).first_name == "Olena"


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_with_nothing_stored_there_is_nothing_to_withdraw(
    admin_client: TestClient, method: str
) -> None:
    """FR-045."""
    response = admin_client.request(method, "/profile/withdraw", follow_redirects=False)
    assert response.status_code == 409
    assert NOTHING_TO_WITHDRAW in response.text


def test_a_teacher_withdraws(
    client: TestClient, outbox: list[EmailMessage], places: dict[str, int]
) -> None:
    """US4-4, US4-5, FR-046: erased, signed out everywhere, and can no longer sign in."""
    user_id = a_teacher(places)
    browser, other = signed_in(OLENA), signed_in(OLENA)
    response = browser.post("/profile/withdraw", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/data-erased"
    cleared = response.headers["set-cookie"]
    assert cleared.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "Max-Age=0" in cleared
    assert other.get("/", follow_redirects=False).status_code == 303
    erased = person(user_id)
    assert (erased.first_name, erased.last_name) == (None, None)
    assert erased.email == f"erased-{user_id}"
    assert erased.is_active is False
    with Session(app.state.engine) as session:
        assert session.exec(select(UserSession).where(UserSession.user_id == user_id)).all() == []
        assert len(session.exec(select(ConsentRecord)).all()) == 1
    landed = browser.get("/data-erased")
    assert "Your data has been erased." in landed.text
    assert "kept as proof" in landed.text
    assert browser.get("/data-erased").text == landed.text

    client.post("/login", data={"email": OLENA})
    assert outbox == []


def test_an_administrator_who_teaches_withdraws(
    admin_client: TestClient, places: dict[str, int]
) -> None:
    """US4-6, FR-047: keeps the administrator role and the email; leaves the Teachers tab."""
    user_id = a_teacher(places, email=ADMIN_STUDENT_EMAIL)
    browser = signed_in(ADMIN_STUDENT_EMAIL, Role.ADMIN)
    confirmation = browser.get("/profile/withdraw").text
    assert (
        "Your administrator role and email stay: they come from the deployment configuration."
        in confirmation
    )
    assert "You will no longer be able to sign in." not in confirmation
    assert "Teacher" in admin_client.get("/admin/teachers").text
    assert browser.post("/profile/withdraw", follow_redirects=False).status_code == 303
    after = person(user_id)
    assert after.email == ADMIN_STUDENT_EMAIL
    assert after.is_active is True
    assert after.first_name is None
    with Session(app.state.engine) as session:
        # The cast seeds this person's student role directly. Since milestone 9 the student is an
        # invitable role too, so withdrawal removes it with the teacher role (milestone 9 FR-044).
        assert get_roles(session, user_id) == (Role.ADMIN,)
    assert "No teachers yet" in admin_client.get("/admin/teachers").text
    assert browser.get("/", follow_redirects=False).status_code == 303


def test_a_removed_teacher_who_is_still_an_administrator_can_withdraw(
    places: dict[str, int], client: TestClient
) -> None:
    """US4-7."""
    user_id = a_teacher(places, email=ADMIN_EMAIL)
    with Session(app.state.engine) as session:
        remove_teacher(session, app.state.settings, user_id)
    body = signed_in(ADMIN_EMAIL).get("/profile").text
    assert "/profile/withdraw" in [a.href for a in html.content_links(body)]
    assert ("Roles", "Administrator") in html.details(body)
    assert "Kyiv Lyceum" not in body


# ---------------------------------------------------------------------------------------------
# Milestone 9: a student's profile and withdrawal (US7, US5-3)
# ---------------------------------------------------------------------------------------------

TARAS = "taras@example.org"
STUDENT_NOTE = "Corrections to student data are made by a teacher of your educational institution."
TEACHER_NOTE = "Corrections to teacher data are made by an administrator."


def a_student(places: dict[str, int], email: str = TARAS) -> tuple[int, int, int]:
    """A real student of "KN-21" (year 2) of "Kyiv Lyceum", invited by a real Write teacher; the
    student's, the teacher's and the class's ids."""
    engine, settings = app.state.engine, app.state.settings
    teacher_id = make_teacher(
        engine,
        settings,
        email="petro@example.org",
        institutions={places["kyiv"]: AccessLevel.WRITE},
        first="Petro",
        last="Bondar",
    )
    class_id = make_class(engine, places["kyiv"], "KN-21", 2)
    student_id = enrol_student(
        engine, settings, email=email, class_id=class_id, inviter_email="petro@example.org"
    )
    return student_id, teacher_id, class_id


def test_a_student_sees_their_enrolment_and_record(
    places: dict[str, int], client: TestClient
) -> None:
    """US7-1, US7-2, FR-045, FR-046."""
    a_student(places)
    body = signed_in(TARAS).get("/profile").text
    main = html.text(body, "main")
    for shown in (
        TARAS,
        "Taras",
        "Shevchenko",
        " UTC · Student · version 1",
        "and your class, which also records",
        STUDENT_NOTE,
    ):
        assert shown in main
    for pair in (
        ("Roles", "Student"),
        ("Educational institution", "Kyiv Lyceum (Kyiv)"),
        ("Class", "KN-21"),
        ("Year of study", "2"),
    ):
        assert pair in html.details(body)
    assert "/profile/withdraw" in [a.href for a in html.content_links(body)]
    assert TEACHER_NOTE not in body


def test_a_teacher_and_student_sees_both_notes(places: dict[str, int], client: TestClient) -> None:
    """US7-2."""
    a_teacher(places, email=TARAS)
    a_student(places)
    body = signed_in(TARAS, Role.TEACHER).get("/profile").text
    assert STUDENT_NOTE in body
    assert TEACHER_NOTE in body
    assert ("Roles", "Teacher, Student") in html.details(body)


def test_a_blocked_teacher_and_student_sees_the_enrolment_marked(
    places: dict[str, int], client: TestClient
) -> None:
    """US5-3, FR-045: the enrolment is shown, marked; the student role is not offered."""
    a_teacher(places, email=TARAS)
    _, teacher_id, class_id = a_student(places)
    with Session(app.state.engine) as session:
        set_class_active(session, teacher_id, class_id, False)
    body = signed_in(TARAS, Role.TEACHER).get("/profile").text
    assert ("Class", "KN-21 Deactivated") in html.details(body)
    assert html.badges(body) == ["Deactivated"]
    assert ("Roles", "Teacher") in html.details(body)
    assert STUDENT_NOTE in body


def test_a_student_withdraws(places: dict[str, int], client: TestClient) -> None:
    """US7-3, FR-044: the enrolment goes with the milestone 8 erasure."""
    student_id, _, class_id = a_student(places)
    browser, other = signed_in(TARAS), signed_in(TARAS)
    confirmation = browser.get("/profile/withdraw").text
    assert "These roles are removed: Student." in confirmation
    assert browser.post("/profile/withdraw", follow_redirects=False).status_code == 303
    assert other.get("/", follow_redirects=False).status_code == 303
    erased = person(student_id)
    assert (erased.first_name, erased.last_name, erased.email, erased.is_active) == (
        None,
        None,
        f"erased-{student_id}",
        False,
    )
    with Session(app.state.engine) as session:
        assert get_roles(session, student_id) == ()
        assert session.get(Enrolment, student_id) is None
        assert (
            session.exec(select(UserSession).where(UserSession.user_id == student_id)).all() == []
        )
        records = session.exec(select(ConsentRecord).where(ConsentRecord.user_id == student_id))
        assert len(records.all()) == 1
        secret = app.state.settings.secret_key
        assert get_cutoff(session, secret, TARAS, Role.STUDENT) is not None
        region = session.get(Institution, places["kyiv"]).region_id  # type: ignore[union-attr]
    teacher = signed_in("petro@example.org")
    page = teacher.get(
        f"/teacher/students?region={region}&institution={places['kyiv']}&class={class_id}"
    ).text
    assert "Shevchenko" not in page
    assert "No students in this class yet" in page


def test_a_teacher_and_student_withdraws_both_roles(
    places: dict[str, int], client: TestClient
) -> None:
    """US7-4."""
    a_teacher(places, email=TARAS)
    student_id, _, _ = a_student(places)
    browser = signed_in(TARAS, Role.STUDENT)
    assert "These roles are removed: Teacher, Student." in browser.get("/profile/withdraw").text
    assert browser.post("/profile/withdraw", follow_redirects=False).status_code == 303
    with Session(app.state.engine) as session:
        assert get_roles(session, student_id) == ()
        assert session.get(Enrolment, student_id) is None
    assert person(student_id).is_active is False
