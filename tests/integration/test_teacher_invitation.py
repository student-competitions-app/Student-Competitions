"""User story 1: an administrator invites a teacher, who accepts and signs in.

See specs/008-teacher-management-consent/spec.md US1 and contracts/http-routes.md §1–§3. Every
case runs on both engines. Links are read from the `memory` outbox.
"""

import re
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import utc_now
from app.core.sealing import seal
from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.models import (
    ConsentRecord,
    ConsentText,
    Role,
    TeacherInstitution,
    TeacherProfile,
    User,
)
from app.services.email import EmailMessage
from app.services.users import get_roles
from tests.conftest import ADMIN_EMAIL, make_institution, token_from

OLENA = "olena@example.org"


@pytest.fixture
def institutions(client: TestClient) -> dict[str, int]:
    """Two selectable institutions, and two that are not."""
    engine = app.state.engine
    return {
        "kyiv": make_institution(engine, "Kyiv Lyceum", "Kyiv"),
        "lviv": make_institution(engine, "Lviv School", "Lviv"),
        "closed": make_institution(engine, "Closed School", "Kyiv", active=False),
        "odesa": make_institution(engine, "Odesa College", "Odesa", region_active=False),
    }


def invite_form(institutions: dict[str, int], **overrides: Any) -> dict[str, Any]:
    form: dict[str, Any] = {
        "email": OLENA,
        "first_name": "Olena",
        "last_name": "Kovalenko",
        "institution": [str(institutions["kyiv"]), str(institutions["lviv"])],
        "access": [f"{institutions['kyiv']}:write", f"{institutions['lviv']}:read"],
        "can_create_competitions": "on",
    }
    form.update(overrides)
    return {key: value for key, value in form.items() if value is not None}


def users_with(email: str) -> list[User]:
    with Session(app.state.engine) as session:
        return list(session.exec(select(User).where(User.email == email)))


def code_from(message: EmailMessage) -> str:
    found = re.search(r"code is: ([0-9]{6})", message.text)
    assert found is not None
    return found.group(1)


# ---------------------------------------------------------------------------------------------
# The invitation form
# ---------------------------------------------------------------------------------------------


def test_the_form_offers_only_selectable_institutions_with_read_preselected(
    admin_client: TestClient, institutions: dict[str, int]
) -> None:
    """US1-1, FR-006, FR-009, FR-014."""
    body = admin_client.get("/admin/teachers/invite").text
    for field in ('name="email"', 'name="first_name"', 'name="last_name"'):
        assert field in body
    assert (
        '<input type="checkbox" id="can_create_competitions" name="can_create_competitions">'
        in (body)
    )
    assert "Kyiv Lyceum (Kyiv)" in body
    assert "Lviv School (Lviv)" in body
    assert "Closed School" not in body
    assert "Odesa College" not in body
    for key in ("kyiv", "lviv"):
        institution_id = institutions[key]
        assert f'name="institution" value="{institution_id}"' in body
        assert f'<option value="{institution_id}:read" selected>Read</option>' in body
        assert f'<option value="{institution_id}:write">Write</option>' in body
    assert body.index("Kyiv Lyceum (Kyiv)") < body.index("Lviv School (Lviv)")


# ---------------------------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------------------------


def test_an_invitation_is_sent_opened_accepted_and_used_to_sign_in(
    client: TestClient,
    admin_client: TestClient,
    outbox: list[EmailMessage],
    institutions: dict[str, int],
) -> None:
    """US1-2 to US1-9."""
    response = admin_client.post(
        "/admin/teachers/invite", data=invite_form(institutions), follow_redirects=False
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/admin/teachers?sent=")
    assert "@" not in location
    assert "olena" not in location.lower()
    banner = admin_client.get(location)
    assert f"Invitation sent to {OLENA}" in banner.text

    [message] = outbox
    assert message.to == OLENA
    for statement in (
        f"({ADMIN_EMAIL}) invites you",
        "Role: Teacher",
        "Kyiv Lyceum (Kyiv) — Write",
        "Lviv School (Lviv) — Read",
        "You will be able to create competitions.",
        "Nothing about you is stored unless you accept.",
        "This invitation expires on",
    ):
        assert statement in message.text
    token = token_from(message)
    link = f"/invitations/{token}"
    assert f"http://testserver{link}" in message.text

    for _ in range(2):
        page = client.get(link)
        assert page.status_code == 200
    assert users_with(OLENA) == []
    body = page.text
    for shown in (
        "Invitation to Student Competitions",
        f"{ADMIN_EMAIL} ({ADMIN_EMAIL}) invites you to join as a teacher.",
        OLENA,
        "Olena",
        "Kovalenko",
        "Kyiv Lyceum (Kyiv) — Write",
        "Lviv School (Lviv) — Read",
        "Can create competitions: Yes",
        "This invitation expires on ",
        " UTC.",
        "Resend",
        "I agree",
        "If any detail is wrong, ask the person who invited you for a new invitation, or accept "
        "and ask them to correct it.",
    ):
        assert shown in body
    with Session(app.state.engine) as session:
        current = session.exec(select(ConsentText).where(ConsentText.role == "teacher")).one()
    assert f'<input type="hidden" name="consent_text_id" value="{current.id}">' in body
    assert body.count("<input") == 1
    assert "<select" not in body and "<textarea" not in body

    accepted = client.post(link, data={"consent_text_id": str(current.id)}, follow_redirects=False)
    assert accepted.status_code == 303
    location = accepted.headers["location"]
    assert location.startswith("/login?prefill=")
    assert "@" not in location
    assert SESSION_COOKIE_NAME not in client.cookies

    [olena] = users_with(OLENA)
    assert olena.is_active
    assert (olena.first_name, olena.last_name) == ("Olena", "Kovalenko")
    with Session(app.state.engine) as session:
        assert olena.id is not None
        assert get_roles(session, olena.id) == (Role.TEACHER,)
        links = {
            row.institution_id: row.access_level
            for row in session.exec(
                select(TeacherInstitution).where(TeacherInstitution.user_id == olena.id)
            )
        }
        assert links == {institutions["kyiv"]: "write", institutions["lviv"]: "read"}
        profile = session.get(TeacherProfile, olena.id)
        assert profile is not None and profile.can_create_competitions is True
        [record] = session.exec(select(ConsentRecord)).all()
        admin = session.exec(select(User).where(User.email == ADMIN_EMAIL)).one()
        assert record.user_id == olena.id
        assert record.consent_text_id == current.id
        assert record.inviter_id == admin.id
        issued = record.invitation_issued_at
        assert utc_now() - timedelta(minutes=1) < issued <= record.accepted_at

    login = client.get(location)
    assert login.status_code == 200
    assert f'value="{OLENA}"' in login.text
    assert "Your account is ready. Send yourself a sign-in code to continue." in login.text

    client.post("/login", data={"email": OLENA})
    signed_in = client.post(
        "/login/code",
        data={"email": OLENA, "code": code_from(outbox[-1])},
        follow_redirects=False,
    )
    assert signed_in.status_code == 303
    assert client.get("/teacher").status_code == 200


@pytest.mark.parametrize(
    "prefill",
    ["garbage", "", "stale", "other-purpose"],
)
def test_an_invalid_or_stale_prefill_is_ignored(client: TestClient, prefill: str) -> None:
    key = app.state.settings.secret_key
    if prefill == "stale":
        prefill = seal(
            key, "login-prefill", {"email": OLENA}, now=utc_now() - timedelta(minutes=10)
        )
    elif prefill == "other-purpose":
        prefill = seal(key, "invitation-sent", {"email": OLENA})
    body = client.get(f"/login?prefill={prefill}").text
    assert OLENA not in body
    assert "Your account is ready" not in body


def test_a_stale_sent_banner_is_ignored(admin_client: TestClient) -> None:
    key = app.state.settings.secret_key
    stale = seal(key, "invitation-sent", {"email": OLENA}, now=utc_now() - timedelta(minutes=10))
    for value in (stale, "garbage", seal(key, "login-prefill", {"email": OLENA})):
        assert "Invitation sent" not in admin_client.get(f"/admin/teachers?sent={value}").text


# ---------------------------------------------------------------------------------------------
# Invalid forms
# ---------------------------------------------------------------------------------------------

LONG = "a" * 101


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"email": "not-an-email"}, "Enter a valid email address."),
        ({"first_name": LONG}, "The first name can be at most 100 characters."),
        ({"last_name": "Ko\tvalenko"}, "The last name cannot contain tabs"),
        ({"first_name": "   "}, "Enter a first name."),
        ({"institution": None}, "Pick at least one educational institution."),
        ({"institution": ["{kyiv}", "{kyiv}"]}, "can be picked only once."),
        ({"access": ["{kyiv}:admin", "{lviv}:read"]}, "Choose Read or Write access"),
        ({"institution": ["{closed}"], "access": ["{closed}:read"]}, "cannot be selected."),
        ({"institution": ["{odesa}"], "access": ["{odesa}:read"]}, "cannot be selected."),
        ({"institution": ["999999"], "access": ["999999:read"]}, "cannot be selected."),
    ],
    ids=[
        "email",
        "long-name",
        "control",
        "blank-name",
        "none-picked",
        "duplicate",
        "bad-level",
        "deactivated",
        "inactive-region",
        "unknown",
    ],
)
def test_an_invalid_form_is_shown_again_and_sends_nothing(
    admin_client: TestClient,
    outbox: list[EmailMessage],
    institutions: dict[str, int],
    overrides: dict[str, Any],
    message: str,
) -> None:
    """US1, FR-015–FR-017: every error and every entered value; no email, nothing stored."""
    resolved = {
        key: [item.format(**institutions) for item in value] if isinstance(value, list) else value
        for key, value in overrides.items()
    }
    form = invite_form(institutions, **resolved)
    response = admin_client.post("/admin/teachers/invite", data=form)
    assert response.status_code == 400
    assert message in response.text
    for field in ("email", "first_name", "last_name"):
        assert f'value="{form[field]}"' in response.text
    assert outbox == []
    assert users_with(OLENA) == []


def test_every_error_is_shown_at_once(admin_client: TestClient, outbox: list[EmailMessage]) -> None:
    form = {"email": "bad", "first_name": "", "last_name": LONG}
    body = admin_client.post("/admin/teachers/invite", data=form).text
    for message in (
        "Enter a valid email address.",
        "Enter a first name.",
        "The last name can be at most 100 characters.",
        "Pick at least one educational institution.",
    ):
        assert message in body
    assert outbox == []


def test_the_picked_rows_and_levels_are_kept(
    admin_client: TestClient, institutions: dict[str, int]
) -> None:
    form = invite_form(institutions, email="bad")
    body = admin_client.post("/admin/teachers/invite", data=form).text
    kyiv = institutions["kyiv"]
    assert f'value="{kyiv}" id="institution-{kyiv}" checked' in body
    assert f'<option value="{kyiv}:write" selected>Write</option>' in body
    assert 'name="can_create_competitions" checked' in body


# ---------------------------------------------------------------------------------------------
# After acceptance: the profile (US1-10) and the header link
# ---------------------------------------------------------------------------------------------


def test_the_new_teacher_sees_their_data_on_the_profile(
    client: TestClient,
    admin_client: TestClient,
    outbox: list[EmailMessage],
    institutions: dict[str, int],
) -> None:
    """US1-10."""
    admin_client.post("/admin/teachers/invite", data=invite_form(institutions))
    token = token_from(outbox[-1])
    with Session(app.state.engine) as session:
        text = session.exec(select(ConsentText).where(ConsentText.role == "teacher")).one()
    client.post(f"/invitations/{token}", data={"consent_text_id": str(text.id)})
    client.post("/login", data={"email": OLENA})
    client.post("/login/code", data={"email": OLENA, "code": code_from(outbox[-1])})
    body = client.get("/profile").text
    for shown in (
        OLENA,
        "Olena",
        "Kovalenko",
        "<dd>Teacher</dd>",
        "Kyiv Lyceum (Kyiv) — Write",
        "Lviv School (Lviv) — Read",
        "<dt>Can create competitions</dt>\n    <dd>Yes</dd>",
        "Teacher · version 1",
        text.text.split("\n\n")[1],
    ):
        assert shown in body


@pytest.mark.parametrize("path", ["/", "/admin/teachers", "/profile"])
def test_the_header_email_links_to_the_profile(admin_client: TestClient, path: str) -> None:
    body = admin_client.get(path).text
    assert f'<a href="/profile" class="site-session-email">{ADMIN_EMAIL}</a>' in body
