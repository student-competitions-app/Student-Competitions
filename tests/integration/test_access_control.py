"""Each role opens exactly its own pages, judged by the current role.

The access table below is a literal copy of the spec's (user story 1), kept independent of
`app.routers.areas.AREAS` on purpose: a wrong declaration in the application must fail here, not
be mirrored by it. See specs/005-roles-authorization/contracts/http-routes.md. Every test runs
once per database engine.
"""

import logging
import re
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import (
    AccessLevel,
    ConsentRecord,
    Role,
    TeacherInstitution,
    TeacherProfile,
    User,
    UserRole,
)
from app.services.consent import current_consent_text
from app.services.email import EmailMessage
from app.services.institutions import create_institution, list_institutions
from app.services.regions import create_region, list_regions
from app.services.subjects import create_subject, list_subjects
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    invite,
    invite_and_accept,
    make_institution,
)
from tests.integration.test_login_flow import sign_in

ADMIN, TEACHER, STUDENT = Role.ADMIN, Role.TEACHER, Role.STUDENT

ACCESS_TABLE: dict[str, set[Role]] = {
    "/": {ADMIN, TEACHER, STUDENT},
    "/admin/teachers": {ADMIN},
    "/teacher": {TEACHER},
    "/student": {STUDENT},
    "/staff": {ADMIN, TEACHER},
}

TITLES = {
    "/admin/teachers": "Teachers",
    "/teacher": "Teacher area",
    "/student": "Student area",
    "/staff": "Staff area",
}

PLACEHOLDER = "The features of this area will arrive in a later milestone."
"""The milestone 5 areas' sentence. The administrator area's tabs have their own (milestone 6)."""

PLACEHOLDER_AREAS = {"/student", "/staff"}

REDIRECTS = {"/teacher": "/teacher/students"}
"""Areas whose own address opens their first tab: since milestone 9 the teacher area (FR-047)."""

SINGLE_ROLE = {ADMIN: ADMIN_EMAIL, TEACHER: TEACHER_EMAIL, STUDENT: STUDENT_EMAIL}

HOME_LINKS = {
    ADMIN: [("/admin", "Administrator area"), ("/staff", "Staff area")],
    TEACHER: [("/teacher", "Teacher area"), ("/staff", "Staff area")],
    STUDENT: [("/student", "Student area")],
}

CASES = [(role, path) for role in SINGLE_ROLE for path in ACCESS_TABLE]


def header(body: str) -> str:
    return html.region(body, "header")


@pytest.mark.parametrize(("role", "path"), CASES, ids=[f"{r.value}-{p}" for r, p in CASES])
def test_the_access_table(client_as: ClientAs, role: Role, path: str) -> None:
    """SC-001, US1-2, US1-3: 3 roles × 5 pages."""
    signed_in = client_as(SINGLE_ROLE[role])
    response = signed_in.get(path, follow_redirects=False)
    if role in ACCESS_TABLE[path] and path in REDIRECTS:
        assert response.status_code == 303
        assert response.headers["location"] == REDIRECTS[path]
        tab = signed_in.get(REDIRECTS[path])
        assert tab.status_code == 200
        current = [t for t in html.links(tab.text) if t.attrs.get("aria-current") == "page"]
        assert [(t.href, t.text) for t in current] == [(REDIRECTS[path], "Students")]
    elif role in ACCESS_TABLE[path]:
        assert response.status_code == 200
        if path in TITLES:
            assert html.h1(response.text) == TITLES[path]
        if path in PLACEHOLDER_AREAS:
            assert PLACEHOLDER in response.text
    else:
        assert response.status_code == 403
        assert f"Your current role, {role.label}, cannot open this page." in response.text


@pytest.mark.parametrize("role", list(SINGLE_ROLE))
def test_the_access_denied_page(client_as: ClientAs, role: Role) -> None:
    """FR-025: it names the current role, links home, keeps the header, and reveals nothing of
    the page it refused."""
    denied = next(path for path in TITLES if role not in ACCESS_TABLE[path])
    response = client_as(SINGLE_ROLE[role]).get(denied)
    body = response.text
    assert response.status_code == 403
    assert html.h1(body) == "Access denied"
    assert re.search(r"<title>Access denied — ", body)
    assert f"Your current role, {role.label}, cannot open this page." in body
    assert ("/", "Back to the home page") in html.link_pairs(body, "main")
    assert SINGLE_ROLE[role] in html.text(body, "header")
    assert ("post", "/logout") in html.form_targets(body, "header")
    assert TITLES[denied] not in body
    assert PLACEHOLDER not in body


@pytest.mark.parametrize("role", list(SINGLE_ROLE))
def test_the_home_page_lists_exactly_the_allowed_areas(client_as: ClientAs, role: Role) -> None:
    """FR-027, US1-4."""
    body = client_as(SINGLE_ROLE[role]).get("/").text
    sections = [s for s in html.parse(body).find_all("section") if s.attrs.get("id") == "areas"]
    assert len(sections) == 1, "the home page has no areas section"
    assert [h.text() for h in sections[0].find_all("h2")] == ["Your areas"]
    links = [(a.attrs["href"], a.text()) for a in sections[0].find_all("a")]
    assert links == HOME_LINKS[role]


@pytest.mark.parametrize("path", list(TITLES))
def test_anonymous_visitors_are_sent_to_sign_in(client: TestClient, path: str) -> None:
    """US1-6, FR-023: authentication first, so never "access denied"."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next={quote(path, safe='')}"


def test_admin_redirects_to_the_teachers_tab(client_as: ClientAs) -> None:
    """Milestone 6 FR-005: `/admin` opens the first tab; other roles are still denied."""
    response = client_as(ADMIN_EMAIL).get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/teachers"
    for email in (TEACHER_EMAIL, STUDENT_EMAIL):
        assert client_as(email).get("/admin", follow_redirects=False).status_code == 403


def test_an_unknown_page_is_not_found_not_denied(client_as: ClientAs) -> None:
    """Spec edge case."""
    response = client_as(STUDENT_EMAIL).get("/does-not-exist")
    assert response.status_code == 404


def test_a_denial_is_logged_without_identity(
    client_as: ClientAs, caplog: pytest.LogCaptureFixture
) -> None:
    """SC-008: the role and the route template, never the address or the user id."""
    student = client_as(STUDENT_EMAIL)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert student.get("/admin").status_code == 403
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Access denied")]
    assert lines == ["Access denied: role=student route=/admin"]
    for record in caplog.records:
        assert "@" not in record.getMessage()


# ---------------------------------------------------------------------------------------------
# Milestone 6: only administrators reach the administrator area (user story 4)
# ---------------------------------------------------------------------------------------------
#
# See specs/006-admin-area/spec.md user story 4 and contracts/http-routes.md "Access". Every page
# and every action of the area, for every role, with the subject rows compared before and after
# each refusal.

ADMIN_PAGES = [
    "/admin",
    "/admin/teachers",
    "/admin/institutions",
    "/admin/subjects",
    "/admin/subjects/new",
    "/admin/subjects/{id}/rename",
    "/admin/subjects/{id}/delete",
]

ADMIN_ACTIONS = [
    ("/admin/subjects", {"name": "Hacked"}),
    ("/admin/subjects/{id}/rename", {"name": "Hacked"}),
    ("/admin/subjects/{id}/deactivate", {}),
    ("/admin/subjects/{id}/activate", {}),
    ("/admin/subjects/{id}/delete", {}),
]

OTHER_ROLES = [TEACHER, STUDENT]


@pytest.fixture
def subject_id(session: Session) -> int:
    """One active subject, for the pages and actions that need an id."""
    subject = create_subject(session, "Physics")
    assert subject.id is not None
    return subject.id


def subject_rows(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    return [(s.id, s.name, s.name_key, s.is_active, s.updated_at) for s in list_subjects(session)]


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_other_roles_are_denied_every_admin_page(
    client_as: ClientAs, subject_id: int, role: Role
) -> None:
    """US4-1, FR-037."""
    browser = client_as(SINGLE_ROLE[role])
    for template in ADMIN_PAGES:
        path = template.format(id=subject_id)
        response = browser.get(path, follow_redirects=False)
        assert response.status_code == 403, path
        assert f"Your current role, {role.label}, cannot open this page." in response.text


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_other_roles_are_denied_every_admin_action(
    client_as: ClientAs, session: Session, subject_id: int, role: Role
) -> None:
    """US4-2: refused, and nothing changes."""
    browser = client_as(SINGLE_ROLE[role])
    before = subject_rows(session)
    for template, data in ADMIN_ACTIONS:
        path = template.format(id=subject_id)
        response = browser.post(path, data=data, follow_redirects=False)
        assert response.status_code == 403, path
        assert subject_rows(session) == before, path


def test_an_administrator_using_another_role_is_denied_until_they_switch(
    client_as: ClientAs,
) -> None:
    """US4-3, FR-036: access follows the current role, not the roles held."""
    browser = client_as(ADMIN_STUDENT_EMAIL, STUDENT)
    assert browser.get("/admin/subjects").status_code == 403
    assert browser.post("/role", data={"role": "admin"}, follow_redirects=False).status_code == 303
    assert browser.get("/admin/subjects").status_code == 200


def test_anonymous_visitors_are_sent_to_sign_in_from_every_admin_page(
    client: TestClient, subject_id: int
) -> None:
    """US4-4, FR-038."""
    for template in ADMIN_PAGES:
        path = template.format(id=subject_id)
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == f"/login?next={quote(path, safe='')}"


def test_anonymous_actions_change_nothing(
    client: TestClient, session: Session, subject_id: int
) -> None:
    before = subject_rows(session)
    for template, data in ADMIN_ACTIONS:
        path = template.format(id=subject_id)
        response = client.post(path, data=data, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/login"
        assert subject_rows(session) == before, path


def test_signing_in_returns_to_the_subjects_tab(
    client: TestClient, outbox: list[EmailMessage]
) -> None:
    """US4-4: through the real code flow, the browser lands where it was going."""
    response = sign_in(client, outbox, next_path="/admin/subjects")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/subjects"
    assert client.get("/admin/subjects").status_code == 200


ADMIN_TAB_PATHS = ("/admin/teachers", "/admin/institutions", "/admin/subjects")


def admin_tab_traces(body: str) -> list[str]:
    """Anything of the administrator tab row on the page: the labelled nav, or a link to a tab."""
    traces = ["tab row"] if html.nav(body, "Administrator area") else []
    return traces + [link.href for link in html.links(body) if link.href in ADMIN_TAB_PATHS]


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_no_admin_tabs_for_other_roles(client_as: ClientAs, role: Role) -> None:
    """US4-5, FR-006: not on any page they may open, nor on the refusal."""
    browser = client_as(SINGLE_ROLE[role])
    pages = [path for path, roles in ACCESS_TABLE.items() if role in roles]
    for path in pages:
        response = browser.get(path)
        assert response.status_code == 200, path
        assert admin_tab_traces(response.text) == [], path
    denied = browser.get("/admin/subjects")
    assert denied.status_code == 403
    assert admin_tab_traces(denied.text) == []


# ---------------------------------------------------------------------------------------------
# Milestone 7: only administrators manage regions and institutions (user story 5)
# ---------------------------------------------------------------------------------------------
#
# See specs/007-region-and-institutions-management/spec.md user story 5 and
# contracts/http-routes.md "Access". Every page and every action of the Educational institutions
# tab, for every role, with the region and institution rows compared before and after each
# refusal. `{r}` is a region and `{i}` an institution in it.

REGION = "/admin/institutions/regions/{r}"
INSTITUTION = REGION + "/institutions/{i}"

INSTITUTION_PAGES = [
    "/admin/institutions",
    "/admin/institutions/regions/new",
    REGION,
    REGION + "/rename",
    REGION + "/delete",
    REGION + "/institutions/new",
    INSTITUTION + "/rename",
    INSTITUTION + "/delete",
]

INSTITUTION_ACTIONS = [
    ("/admin/institutions/regions", {"name": "Hacked"}),
    (REGION + "/rename", {"name": "Hacked"}),
    (REGION + "/deactivate", {}),
    (REGION + "/activate", {}),
    (REGION + "/delete", {}),
    (REGION + "/institutions", {"name": "Hacked"}),
    (INSTITUTION + "/rename", {"name": "Hacked"}),
    (INSTITUTION + "/deactivate", {}),
    (INSTITUTION + "/activate", {}),
    (INSTITUTION + "/delete", {}),
]


@pytest.fixture
def region_id(session: Session) -> int:
    """One active region, "Kyiv", holding one institution."""
    region = create_region(session, "Kyiv")
    assert region.id is not None
    return region.id


@pytest.fixture
def institution_id(session: Session, region_id: int) -> int:
    institution = create_institution(session, region_id, "Kyiv Polytechnic Institute")
    assert institution.id is not None
    return institution.id


def institution_rows(session: Session) -> list[list[tuple[object, ...]]]:
    session.expire_all()
    regions = list_regions(session)
    return [
        [(r.id, r.name, r.name_key, r.is_active, r.updated_at) for r in regions],
        [
            (i.id, i.region_id, i.name, i.name_key, i.is_active, i.updated_at)
            for r in regions
            for i in list_institutions(session, r.id)
        ],
    ]


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_other_roles_are_denied_every_institutions_page(
    client_as: ClientAs, region_id: int, institution_id: int, role: Role
) -> None:
    """US5-1, FR-045."""
    browser = client_as(SINGLE_ROLE[role])
    for template in INSTITUTION_PAGES:
        path = template.format(r=region_id, i=institution_id)
        response = browser.get(path, follow_redirects=False)
        assert response.status_code == 403, path
        assert f"Your current role, {role.label}, cannot open this page." in response.text


@pytest.mark.parametrize("role", OTHER_ROLES)
def test_other_roles_are_denied_every_institutions_action(
    client_as: ClientAs, session: Session, region_id: int, institution_id: int, role: Role
) -> None:
    """US5-2: refused, and nothing changes."""
    browser = client_as(SINGLE_ROLE[role])
    before = institution_rows(session)
    for template, data in INSTITUTION_ACTIONS:
        path = template.format(r=region_id, i=institution_id)
        response = browser.post(path, data=data, follow_redirects=False)
        assert response.status_code == 403, path
        assert institution_rows(session) == before, path


def test_an_administrator_using_another_role_is_denied_the_institutions_tab(
    client_as: ClientAs,
) -> None:
    """US5-3, FR-044: access follows the current role, not the roles held."""
    browser = client_as(ADMIN_STUDENT_EMAIL, STUDENT)
    assert browser.get("/admin/institutions").status_code == 403
    assert browser.post("/role", data={"role": "admin"}, follow_redirects=False).status_code == 303
    assert browser.get("/admin/institutions").status_code == 200


def test_anonymous_visitors_are_sent_to_sign_in_from_every_institutions_page(
    client: TestClient, region_id: int, institution_id: int
) -> None:
    """FR-046: the return address keeps the selected region."""
    for template in INSTITUTION_PAGES:
        path = template.format(r=region_id, i=institution_id)
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == f"/login?next={quote(path, safe='')}"


def test_anonymous_institutions_actions_change_nothing(
    client: TestClient, session: Session, region_id: int, institution_id: int
) -> None:
    before = institution_rows(session)
    for template, data in INSTITUTION_ACTIONS:
        path = template.format(r=region_id, i=institution_id)
        response = client.post(path, data=data, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/login"
        assert institution_rows(session) == before, path


def test_signing_in_returns_to_the_selected_region(
    client: TestClient, outbox: list[EmailMessage], region_id: int
) -> None:
    """US5-4, FR-046: through the real code flow, the same region is selected again."""
    path = f"/admin/institutions/regions/{region_id}"
    response = sign_in(client, outbox, next_path=path)
    assert response.status_code == 303
    assert response.headers["location"] == path
    page = client.get(path)
    assert page.status_code == 200
    selected = [link for link in html.links(page.text) if link.attrs.get("aria-current") == "true"]
    assert [(link.href, link.text) for link in selected] == [(path, "Kyiv")]


# ---------------------------------------------------------------------------------------------
# Milestone 8: teacher management, the profile and the link pages
# ---------------------------------------------------------------------------------------------
#
# See specs/008-teacher-management-consent/spec.md user story 8 and contracts/http-routes.md
# "Access summary". `{t}` is a real teacher, created through the invitation services.

TEACHER_PAGES = [
    "/admin/teachers",
    "/admin/teachers/invite",
    "/admin/teachers/{t}",
    "/admin/teachers/{t}/remove",
]


def teacher_actions(school: int) -> list[tuple[str, dict[str, object]]]:
    picker = {"institution": [str(school)], "access": [f"{school}:write"]}
    return [
        (
            "/admin/teachers/invite",
            {"email": "new@example.org", "first_name": "N", "last_name": "N", **picker},
        ),
        ("/admin/teachers/{t}", {"first_name": "Hacked", "last_name": "Hacked", **picker}),
        ("/admin/teachers/{t}/remove", {}),
    ]


@pytest.fixture
def school(client: TestClient) -> int:
    return make_institution(app.state.engine, "School 5", "Kyiv")


@pytest.fixture
def teacher_id(school: int) -> int:
    return invite_and_accept(
        app.state.engine,
        app.state.settings,
        email="olena@example.org",
        institutions={school: AccessLevel.READ},
    )


def teacher_state(session: Session) -> list[list[tuple[object, ...]]]:
    """Users, roles, links, profiles and consent records: everything teacher management writes."""
    session.expire_all()
    return [
        [
            (u.id, u.email, u.is_active, u.first_name, u.last_name, u.updated_at)
            for u in session.exec(select(User).order_by(User.id))
        ],
        sorted((r.user_id, r.role) for r in session.exec(select(UserRole))),
        sorted(
            (link.user_id, link.institution_id, link.access_level, link.updated_at)
            for link in session.exec(select(TeacherInstitution))
        ),
        sorted(
            (p.user_id, p.can_create_competitions, p.updated_at)
            for p in session.exec(select(TeacherProfile))
        ),
        sorted((c.id, c.user_id) for c in session.exec(select(ConsentRecord))),
    ]


@pytest.mark.parametrize("who", ["teacher", "student", "admin-as-student"])
def test_others_are_denied_every_teacher_page_and_action(
    client_as: ClientAs,
    session: Session,
    outbox: list[EmailMessage],
    school: int,
    teacher_id: int,
    who: str,
) -> None:
    """US8-1, US8-2, FR-063, FR-064: `403`, and nothing changes, nothing is sent."""
    if who == "admin-as-student":
        browser, label = client_as(ADMIN_STUDENT_EMAIL, STUDENT), STUDENT.label
    else:
        role = TEACHER if who == "teacher" else STUDENT
        browser, label = client_as(SINGLE_ROLE[role]), role.label
    for template in TEACHER_PAGES:
        response = browser.get(template.format(t=teacher_id), follow_redirects=False)
        assert response.status_code == 403, template
        assert f"Your current role, {label}, cannot open this page." in response.text
    before, sent = teacher_state(session), len(outbox)
    for template, data in teacher_actions(school):
        response = browser.post(template.format(t=teacher_id), data=data, follow_redirects=False)
        assert response.status_code == 403, template
        assert teacher_state(session) == before, template
    assert len(outbox) == sent


def test_anonymous_visitors_are_sent_to_sign_in_from_teacher_pages_and_actions(
    client: TestClient, session: Session, outbox: list[EmailMessage], school: int, teacher_id: int
) -> None:
    for template in [*TEACHER_PAGES, "/profile", "/profile/withdraw"]:
        path = template.format(t=teacher_id)
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == f"/login?next={quote(path, safe='')}"
    before, sent = teacher_state(session), len(outbox)
    for template, data in [*teacher_actions(school), ("/profile/withdraw", {})]:
        response = client.post(template.format(t=teacher_id), data=data, follow_redirects=False)
        assert response.status_code == 303, template
        assert response.headers["location"] == "/login"
    assert teacher_state(session) == before
    assert len(outbox) == sent


@pytest.mark.parametrize("email", [ADMIN_EMAIL, TEACHER_EMAIL, STUDENT_EMAIL])
def test_every_role_opens_only_its_own_profile(client_as: ClientAs, email: str) -> None:
    """FR-062: the profile and the withdrawal step show the signed-in person only."""
    browser = client_as(email)
    for path in ("/profile", "/profile/withdraw"):
        response = browser.get(path)
        assert response.status_code in {200, 409}, path
        others = {ADMIN_EMAIL, TEACHER_EMAIL, STUDENT_EMAIL} - {email}
        for other in others:
            assert f">{other}<" not in response.text.replace(f">{email}<", "")


def test_a_person_without_a_current_role_chooses_one_first(
    client_as: ClientAs, outbox: list[EmailMessage], school: int
) -> None:
    """Milestone 5's rule for every private page; the link pages are served directly."""
    browser = client_as(ADMIN_STUDENT_EMAIL, None)
    for path in ("/profile", "/admin/teachers"):
        response = browser.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/role?next={quote(path, safe='')}"
    for path in ("/data-deletion", "/data-deletion/requested", "/data-erased"):
        assert browser.get(path, follow_redirects=False).status_code == 200, path
    token = invite(
        app.state.engine,
        app.state.settings,
        email="olena@example.org",
        institutions={school: AccessLevel.READ},
    )
    assert browser.get(f"/invitations/{token}", follow_redirects=False).status_code == 200


@pytest.mark.parametrize("who", ["anonymous", ADMIN_EMAIL, TEACHER_EMAIL])
def test_link_pages_act_only_on_the_person_in_the_link(
    client: TestClient, client_as: ClientAs, school: int, who: str
) -> None:
    """US8-4, FR-055."""
    browser = client if who == "anonymous" else client_as(who)
    token = invite(
        app.state.engine,
        app.state.settings,
        email="olena@example.org",
        institutions={school: AccessLevel.READ},
    )
    page = browser.get(f"/invitations/{token}")
    assert page.status_code == 200
    assert "olena@example.org" in page.text
    with Session(app.state.engine) as session:
        text_id = current_consent_text(session, TEACHER).id
    browser.post(f"/invitations/{token}", data={"consent_text_id": str(text_id)})
    with Session(app.state.engine) as session:
        olena = session.exec(select(User).where(User.email == "olena@example.org")).one()
        assert olena.first_name == "Olena"
        for email in (ADMIN_EMAIL, TEACHER_EMAIL):
            other = session.exec(select(User).where(User.email == email)).one()
            assert other.first_name is None
