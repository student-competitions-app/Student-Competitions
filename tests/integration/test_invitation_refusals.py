"""User story 2: an invitation that is no longer valid is refused, and nothing is stored.

See specs/008-teacher-management-consent/spec.md US2 (scenarios 1–5, 9), FR-029, FR-033, FR-035,
FR-061, and contracts/http-routes.md §2. Every case runs on both engines.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import utc_now
from app.main import app
from app.models import (
    AccessLevel,
    ConsentRecord,
    ConsentText,
    Institution,
    Role,
    TeacherInstitution,
    TeacherProfile,
    User,
)
from app.routers.invitations import CONSENT_CHANGED, EXPIRED, NEUTRAL
from app.services.consent import current_consent_text
from app.services.institutions import delete_institution, rename_institution
from app.services.users import reconcile_users
from tests.conftest import ADMIN_EMAIL, ADMIN_STUDENT_EMAIL, invite, make_institution

OLENA = "olena@example.org"
LINK_HEADERS = {"referrer-policy": "no-referrer", "cache-control": "no-store"}


@pytest.fixture
def school(client: TestClient) -> int:
    return make_institution(app.state.engine, "School 5", "Kyiv")


def issue(school: int, **kwargs: object) -> str:
    return invite(
        app.state.engine,
        app.state.settings,
        email=OLENA,
        institutions={school: AccessLevel.WRITE},
        **kwargs,  # type: ignore[arg-type]
    )


def consent_id() -> int:
    with Session(app.state.engine) as session:
        text = current_consent_text(session, Role.TEACHER)
        assert text.id is not None
        return text.id


def nothing_stored() -> bool:
    with Session(app.state.engine) as session:
        no_user = session.exec(select(User).where(User.email == OLENA)).first() is None
        no_record = session.exec(select(func.count()).select_from(ConsentRecord)).one() == 0
        no_link = session.exec(select(func.count()).select_from(TeacherInstitution)).one() == 0
    return no_user and no_record and no_link


def assert_link_headers(response: object) -> None:
    for name, value in LINK_HEADERS.items():
        assert response.headers[name] == value  # type: ignore[attr-defined]


def tampered(token: str) -> str:
    position = len(token) // 2
    replacement = "A" if token[position] != "A" else "B"
    return token[:position] + replacement + token[position + 1 :]


def refused_both_ways(client: TestClient, token: str, status: int, message: str) -> str:
    """`GET` and `POST` of the link are refused with `status` and `message`; the `GET` body."""
    page = client.get(f"/invitations/{token}")
    assert page.status_code == status
    assert message in page.text
    assert_link_headers(page)
    posted = client.post(f"/invitations/{token}", data={"consent_text_id": str(consent_id())})
    assert posted.status_code == status
    assert message in posted.text
    assert_link_headers(posted)
    assert nothing_stored()
    return page.text


def test_a_tampered_link_is_refused(client: TestClient, school: int) -> None:
    """US2-1."""
    refused_both_ways(client, tampered(issue(school)), 400, NEUTRAL)


def test_an_expired_link_is_refused(client: TestClient, school: int) -> None:
    """US2-2: issued eight days ago."""
    token = issue(school, now=utc_now() - timedelta(days=8))
    refused_both_ways(client, token, 410, EXPIRED)


def test_an_inviter_who_is_no_longer_an_administrator_is_refused(
    client: TestClient, school: int
) -> None:
    """US2-3."""
    token = issue(school, inviter_email=ADMIN_STUDENT_EMAIL)
    with Session(app.state.engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    refused_both_ways(client, token, 400, NEUTRAL)


@pytest.mark.parametrize("change", ["deleted", "deactivated", "region-deactivated"])
def test_an_institution_no_longer_available_is_refused(
    client: TestClient, admin_client: TestClient, school: int, change: str
) -> None:
    """US2-4, FR-026."""
    token = issue(school)
    with Session(app.state.engine) as session:
        institution = session.get(Institution, school)
        assert institution is not None
        region_id = institution.region_id
    if change == "deleted":
        with Session(app.state.engine) as session:
            delete_institution(session, region_id, school)
    elif change == "deactivated":
        path = f"/admin/institutions/regions/{region_id}/institutions/{school}/deactivate"
        assert admin_client.post(path, follow_redirects=False).status_code == 303
    else:
        path = f"/admin/institutions/regions/{region_id}/deactivate"
        assert admin_client.post(path, follow_redirects=False).status_code == 303
    refused_both_ways(client, token, 400, NEUTRAL)


def test_a_renamed_institution_shows_its_new_name_and_is_accepted(
    client: TestClient, school: int
) -> None:
    """US2-5: the page shows current names."""
    token = issue(school)
    with Session(app.state.engine) as session:
        institution = session.get(Institution, school)
        assert institution is not None
        rename_institution(session, institution.region_id, school, "Lyceum 7")
    page = client.get(f"/invitations/{token}")
    assert "Lyceum 7 (Kyiv) — Write" in page.text
    assert "School 5" not in page.text
    posted = client.post(
        f"/invitations/{token}", data={"consent_text_id": str(consent_id())}, follow_redirects=False
    )
    assert posted.status_code == 303
    assert not nothing_stored()


def test_extra_fields_are_ignored(client: TestClient, school: int) -> None:
    """US2-9, FR-029: what is stored is exactly what the link holds."""
    other = make_institution(app.state.engine, "Other School", "Lviv")
    token = issue(school)
    posted = client.post(
        f"/invitations/{token}",
        data={
            "consent_text_id": str(consent_id()),
            "email": "evil@example.org",
            "first_name": "X",
            "last_name": "Y",
            "institution": str(other),
            "access": f"{other}:write",
            "can_create_competitions": "on",
        },
        follow_redirects=False,
    )
    assert posted.status_code == 303
    with Session(app.state.engine) as session:
        assert session.exec(select(User).where(User.email == "evil@example.org")).first() is None
        olena = session.exec(select(User).where(User.email == OLENA)).one()
        assert (olena.first_name, olena.last_name) == ("Olena", "Kovalenko")
        links = session.exec(select(TeacherInstitution)).all()
        assert [(link.institution_id, link.access_level) for link in links] == [(school, "write")]
        profile = session.get(TeacherProfile, olena.id)
        assert profile is not None and profile.can_create_competitions is False


def test_a_changed_consent_text_is_shown_again_and_nothing_is_stored(
    client: TestClient, school: int
) -> None:
    """FR-035: a stale `consent_text_id` gets 409 and the new text; the new id is accepted."""
    token = issue(school)
    old_id = consent_id()
    with Session(app.state.engine) as session:
        session.add(
            ConsentText(
                role="teacher", version=2, text="Version two wording.", published_at=utc_now()
            )
        )
        session.commit()
    new_id = consent_id()
    assert new_id != old_id

    for stale in (str(old_id), "", "not-a-number"):
        changed = client.post(f"/invitations/{token}", data={"consent_text_id": stale})
        assert changed.status_code == 409
        assert CONSENT_CHANGED in changed.text
        assert "Version two wording." in changed.text
        assert f'name="consent_text_id" value="{new_id}"' in changed.text
        assert_link_headers(changed)
        assert nothing_stored()

    accepted = client.post(
        f"/invitations/{token}", data={"consent_text_id": str(new_id)}, follow_redirects=False
    )
    assert accepted.status_code == 303
    with Session(app.state.engine) as session:
        record = session.exec(select(ConsentRecord)).one()
        assert record.consent_text_id == new_id


def test_the_refusals_do_not_reveal_which_check_failed(
    client: TestClient, admin_client: TestClient, school: int
) -> None:
    """FR-033: one body and one status for a tampered link, a refused inviter and a refused
    institution."""
    tampered_body = client.get(f"/invitations/{tampered(issue(school))}").text
    by_former_admin = issue(school, inviter_email=ADMIN_STUDENT_EMAIL)
    with Session(app.state.engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    inviter_body = client.get(f"/invitations/{by_former_admin}").text
    other = make_institution(app.state.engine, "Gone School", "Lviv")
    gone = invite(
        app.state.engine, app.state.settings, email=OLENA, institutions={other: AccessLevel.READ}
    )
    with Session(app.state.engine) as session:
        institution = session.get(Institution, other)
        assert institution is not None
        delete_institution(session, institution.region_id, other)
    institution_body = client.get(f"/invitations/{gone}").text
    assert tampered_body == inviter_body == institution_body


def test_the_acceptance_page_and_its_redirects_carry_the_link_headers(
    client: TestClient, school: int
) -> None:
    """FR-061: `200`, the `303` after acceptance, and the `303` back for "already a teacher"."""
    token = issue(school)
    page = client.get(f"/invitations/{token}")
    assert page.status_code == 200
    assert_link_headers(page)
    for _ in range(2):
        posted = client.post(
            f"/invitations/{token}",
            data={"consent_text_id": str(consent_id())},
            follow_redirects=False,
        )
        assert posted.status_code == 303
        assert_link_headers(posted)
