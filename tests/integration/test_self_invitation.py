"""User story 6: an administrator who also teaches invites themselves, with no shortcut.

See specs/008-teacher-management-consent/spec.md US6 (scenarios 1–3) and FR-022. The same browser
sends, opens and accepts the invitation; nothing about it differs from inviting anyone else.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import ConsentRecord, Role, User
from app.services.consent import current_consent_text
from app.services.email import EmailMessage
from app.services.users import get_roles
from tests import html
from tests.conftest import ADMIN_EMAIL, make_institution, token_from


def test_an_administrator_invites_accepts_and_withdraws_for_themselves(
    admin_client: TestClient, outbox: list[EmailMessage]
) -> None:
    school = make_institution(app.state.engine, "School 5", "Kyiv")
    sent = admin_client.post(
        "/admin/teachers/invite",
        data={
            "email": ADMIN_EMAIL,
            "first_name": "Iryna",
            "last_name": "Admin",
            "institution": [str(school)],
            "access": [f"{school}:write"],
        },
        follow_redirects=False,
    )
    assert sent.status_code == 303
    link = f"/invitations/{token_from(outbox[-1])}"
    page = admin_client.get(link)
    assert page.status_code == 200
    assert "I agree" in page.text
    with Session(app.state.engine) as session:
        text_id = current_consent_text(session, Role.TEACHER).id
    accepted = admin_client.post(
        link, data={"consent_text_id": str(text_id)}, follow_redirects=False
    )
    assert accepted.status_code == 303

    with Session(app.state.engine) as session:
        me = session.exec(select(User).where(User.email == ADMIN_EMAIL)).one()
        assert me.id is not None
        assert get_roles(session, me.id) == (Role.ADMIN, Role.TEACHER)
        assert (me.first_name, me.last_name) == ("Iryna", "Admin")
        [record] = session.exec(select(ConsentRecord)).all()
        assert record.inviter_id == record.user_id == me.id

    # The session is untouched: still signed in, and the sign-in page sends the browser on.
    login = admin_client.get(accepted.headers["location"], follow_redirects=False)
    assert login.status_code == 303
    home = admin_client.get("/admin/teachers")
    assert home.status_code == 200
    switch = [b for f in html.forms(home.text, "header") if f.action == "/role" for b in f.buttons]
    assert ("role", "teacher") in [(b.name, b.value) for b in switch]
    assert "Iryna Admin" in home.text

    withdrawn = admin_client.post("/profile/withdraw", follow_redirects=False)
    assert withdrawn.status_code == 303
    with Session(app.state.engine) as session:
        me = session.exec(select(User).where(User.email == ADMIN_EMAIL)).one()
        assert me.id is not None
        assert get_roles(session, me.id) == (Role.ADMIN,)
        assert me.first_name is None
        assert me.is_active is True
    assert admin_client.get("/", follow_redirects=False).status_code == 303
