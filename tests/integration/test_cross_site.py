"""No write submitted from another site is processed (FR-021, research D7).

The rule runs before the session is read, for every unsafe request: choosing or switching a
role, logging out, and signing in. Every test runs once per database engine.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.core.auth as auth
from app.core.sealing import seal
from app.core.security import SESSION_COOKIE_NAME, hash_token
from app.main import app
from app.models import AccessLevel, ConsentRecord, Role, User, UserRole, UserSession
from app.services.consent import current_consent_text
from app.services.email import EmailMessage
from app.services.institutions import create_institution, list_institutions
from app.services.regions import create_region, list_regions
from app.services.subjects import create_subject, list_subjects
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    ClientAs,
    invite,
    invite_and_accept,
    make_institution,
    sign_in_directly,
)

REFUSED = "This request was refused because it did not come from this site."
CROSS_SITE_HEADERS = [
    {"Sec-Fetch-Site": "cross-site"},
    {"Origin": "https://evil.example"},
]


def current_role(session: Session, browser: TestClient) -> str | None:
    token = browser.cookies[SESSION_COOKIE_NAME].split(".")[0]
    session.expire_all()
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    return row.one().current_role


@pytest.mark.parametrize("forged", CROSS_SITE_HEADERS)
def test_a_cross_site_switch_changes_nothing(
    client_as: ClientAs, session: Session, forged: dict[str, str]
) -> None:
    """US4-6."""
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)
    response = browser.post("/role", data={"role": "student"}, headers=forged)
    assert response.status_code == 403
    assert "<h1>Request refused</h1>" in response.text
    assert REFUSED in response.text
    assert current_role(session, browser) == "admin"


def test_a_cross_site_logout_changes_nothing(client_as: ClientAs) -> None:
    browser = client_as(ADMIN_EMAIL)
    response = browser.post("/logout", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert browser.get("/", follow_redirects=False).status_code == 200


def test_a_cross_site_sign_in_is_refused(client: TestClient) -> None:
    """Closes milestone 4's accepted login-CSRF risk."""
    response = client.post(
        "/login/code",
        data={"email": ADMIN_EMAIL, "code": "123456"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert REFUSED in response.text


def test_the_refusal_happens_before_any_database_access(
    client_as: ClientAs, monkeypatch: pytest.MonkeyPatch
) -> None:
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)

    def failing(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a cross-site request must not look up a session")

    monkeypatch.setattr(auth, "get_session_identity", failing)
    monkeypatch.setattr(auth, "Session", failing)
    response = browser.post(
        "/role", data={"role": "student"}, headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize("own", [{"Sec-Fetch-Site": "same-origin"}, {}])
def test_this_sites_own_writes_are_accepted(
    client_as: ClientAs, session: Session, own: dict[str, str]
) -> None:
    browser = client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)
    response = browser.post("/role", data={"role": "student"}, headers=own, follow_redirects=False)
    assert response.status_code == 303
    assert current_role(session, browser) == "student"


def test_a_cross_site_page_view_is_unaffected(client_as: ClientAs) -> None:
    """Arriving by a link from another site still works: `GET` changes nothing."""
    browser = client_as(ADMIN_EMAIL)
    assert browser.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


@pytest.mark.parametrize("forged", CROSS_SITE_HEADERS)
def test_a_cross_site_subject_action_changes_nothing(
    admin_client: TestClient, session: Session, forged: dict[str, str]
) -> None:
    """Milestone 6 FR-034: the administrator's subject actions are refused like any write."""
    physics = create_subject(session, "Physics")

    def rows() -> list[tuple[object, ...]]:
        session.expire_all()
        return [(s.id, s.name, s.is_active, s.updated_at) for s in list_subjects(session)]

    before = rows()
    for path, data in [
        ("/admin/subjects", {"name": "Forged"}),
        (f"/admin/subjects/{physics.id}/rename", {"name": "Forged"}),
        (f"/admin/subjects/{physics.id}/deactivate", {}),
        (f"/admin/subjects/{physics.id}/delete", {}),
    ]:
        response = admin_client.post(path, data=data, headers=forged, follow_redirects=False)
        assert response.status_code == 403, path
        assert "<h1>Request refused</h1>" in response.text
        assert rows() == before, path


@pytest.mark.parametrize("forged", CROSS_SITE_HEADERS)
def test_a_cross_site_region_or_institution_change_is_refused(
    admin_client: TestClient, session: Session, forged: dict[str, str]
) -> None:
    """Milestone 7 FR-042: region and institution actions are refused like any write."""
    kyiv = create_region(session, "Kyiv")
    academy = create_institution(session, kyiv.id, "Academy")
    for path, data in [
        ("/admin/institutions/regions", {"name": "Evil"}),
        (f"/admin/institutions/regions/{kyiv.id}/institutions/{academy.id}/delete", {}),
    ]:
        response = admin_client.post(path, data=data, headers=forged, follow_redirects=False)
        assert response.status_code == 403, path
        assert REFUSED in response.text
    session.expire_all()
    assert [r.name for r in list_regions(session)] == ["Kyiv"]
    assert [i.name for i in list_institutions(session, kyiv.id)] == ["Academy"]


# ---------------------------------------------------------------------------------------------
# Milestone 8: invitations, acceptance, withdrawal and data deletion (FR-059)
# ---------------------------------------------------------------------------------------------


def consent_state(session: Session) -> list[list[tuple[object, ...]]]:
    session.expire_all()
    return [
        [
            (u.id, u.email, u.is_active, u.first_name)
            for u in session.exec(select(User).order_by(User.id))
        ],
        sorted((r.user_id, r.role) for r in session.exec(select(UserRole))),
        sorted((c.id, c.user_id) for c in session.exec(select(ConsentRecord))),
    ]


@pytest.mark.parametrize("forged", CROSS_SITE_HEADERS)
def test_cross_site_consent_writes_change_nothing(
    client: TestClient,
    admin_client: TestClient,
    session: Session,
    outbox: list[EmailMessage],
    forged: dict[str, str],
) -> None:
    school = make_institution(app.state.engine, "School 5", "Kyiv")
    settings = app.state.settings
    teacher_email = "teacher.one@example.org"
    invite_and_accept(
        app.state.engine, settings, email=teacher_email, institutions={school: AccessLevel.READ}
    )
    pending = invite(
        app.state.engine,
        settings,
        email="olena@example.org",
        institutions={school: AccessLevel.READ},
    )
    with Session(app.state.engine) as db:
        user = db.exec(select(User).where(User.email == teacher_email)).one()
        text_id = current_consent_text(db, Role.TEACHER).id
    deletion = seal(settings.secret_key, "data-deletion", {"user": user.id})
    teacher_browser = TestClient(app)
    sign_in_directly(teacher_browser, teacher_email)

    before, sent = consent_state(session), len(outbox)
    attempts = [
        (
            admin_client,
            "/admin/teachers/invite",
            {
                "email": "new@example.org",
                "first_name": "N",
                "last_name": "N",
                "institution": str(school),
                "access": f"{school}:read",
            },
        ),
        (client, f"/invitations/{pending}", {"consent_text_id": str(text_id)}),
        (teacher_browser, "/profile/withdraw", {}),
        (client, f"/data-deletion/confirm/{deletion}", {}),
    ]
    for browser, path, data in attempts:
        response = browser.post(path, data=data, headers=forged, follow_redirects=False)
        assert response.status_code == 403, path
        assert REFUSED in response.text
    assert consent_state(session) == before
    assert len(outbox) == sent
