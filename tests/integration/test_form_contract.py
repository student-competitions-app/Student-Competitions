"""The form contract: every page keeps its forms' methods, actions and field names.

See specs/010-design-system-ui-guidelines/research.md D17, FR-040 and SC-011. The milestone 1–9
tests post to the server by field name and never read the names from the rendered page, so a field
renamed or lost in a template would still pass them; after the milestone 10 rebuild the names are
macro arguments, so comparing template sources proves nothing either. Only rendering every page
state that shows a form, and comparing what the browser would submit, catches it.

Each case below produces one such state, as the person who sees it. For every form on the page it
records the method, the action (empty means the request path; numeric path segments become
`{id}`, and invitation and deletion tokens `{token}`), the sorted field names of its inputs,
selects, textareas and named buttons, and the sorted `(name, value)` pairs of its named buttons.
A case's records are compared as a sorted list, so moving a form on the page is not a change.
The theme switch's forms (`/theme`) are left out: they are new in milestone 10.

The expected records live in `form_contract.json`, generated once from the milestone 9 templates
with `UPDATE_FORM_CONTRACT=1` and never regenerated in milestone 10: a mismatch means a template
lost or renamed a field, so the template is fixed, not the file.

Deliberate changes since (each is a contract change, recorded here):

- **Milestone 11 FR-009**: the teacher forms' checkbox `can_create_competitions` was renamed
  `can_manage_competitions`, with the setting.
- **Milestone 11**: the question bank's pages (`teacher-question*` cases) are new, generated once
  with `UPDATE_FORM_CONTRACT=1` for those cases only.
- **Milestone 11.1**: the Teams tab's pages (`teacher-team*` cases) are new, generated once with
  `UPDATE_FORM_CONTRACT=1` for those cases only.
"""

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

import app.services.institutions
import app.services.subjects
from app.main import app as application
from app.models import AccessLevel, Institution, Role
from app.services.email import EmailMessage
from app.services.regions import create_region
from app.services.subjects import create_subject, set_subject_active
from tests import html
from tests.conftest import (
    ADMIN_STUDENT_EMAIL,
    TEACHER_STUDENT_EMAIL,
    ClientAs,
    enrol_student,
    invite,
    invite_student,
    make_class,
    make_institution,
    make_member,
    make_question,
    make_subject,
    make_teacher,
    make_team,
    token_from,
)
from tests.integration.test_login_flow import code_from

CONTRACT = Path(__file__).with_name("form_contract.json")
OLENA = "olena@example.org"
TARAS = "taras@example.org"
TOKEN_PATHS = re.compile(r"^/(invitations|data-deletion/confirm)/[^/?]+")


@dataclass
class World:
    """What a case may use: the anonymous browser, signed-in browsers and the outbox."""

    client: TestClient
    client_as: ClientAs
    outbox: list[EmailMessage]
    monkeypatch: pytest.MonkeyPatch

    @property
    def admin(self) -> TestClient:
        return self.client_as("admin@example.com")


Case = Callable[[World], Response]
CASES: dict[str, Case] = {}


def case(name: str) -> Callable[[Case], Case]:
    def register(produce: Case) -> Case:
        assert name not in CASES, name
        CASES[name] = produce
        return produce

    return register


# ---------------------------------------------------------------------------------------------
# Normalising what the page would submit
# ---------------------------------------------------------------------------------------------


def normalise_action(action: str, request_path: str) -> str:
    path, _, query = (action or request_path).partition("?")
    path = TOKEN_PATHS.sub(lambda m: f"/{m[1]}/{{token}}", path)
    path = "/".join("{id}" if part.isdigit() else part for part in path.split("/"))
    if query:
        query = re.sub(r"=\d+", "={id}", query)
        return f"{path}?{query}"
    return path


def records(response: Response) -> list[dict[str, Any]]:
    request_path = response.url.path
    found = []
    for form in html.forms(response.text):
        if form.action == "/theme":
            continue
        fields = {i.name for i in form.inputs if i.name} | {b.name for b in form.buttons if b.name}
        found.append(
            {
                "method": form.method,
                "action": normalise_action(form.action, request_path),
                "fields": sorted(fields),
                "buttons": sorted(
                    [b.name, b.value or ""] for b in form.buttons if b.name is not None
                ),
            }
        )
    return sorted(found, key=lambda record: json.dumps(record, sort_keys=True))


# ---------------------------------------------------------------------------------------------
# Scenes the cases share
# ---------------------------------------------------------------------------------------------


def region_of(institution_id: int) -> int:
    with Session(application.state.engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


@dataclass(frozen=True)
class TeacherScene:
    teacher: TestClient
    institution: int
    region: int
    school_class: int
    student: int

    @property
    def selection(self) -> str:
        return (
            f"/teacher/students?region={self.region}&institution={self.institution}"
            f"&class={self.school_class}"
        )


def a_teacher_with_a_class(world: World) -> TeacherScene:
    """Olena, with Write on one institution, and one class with one accepted student."""
    engine, settings = application.state.engine, application.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(engine, settings, email=OLENA, institutions={institution: AccessLevel.WRITE})
    school_class = make_class(engine, institution, "KN-21", 2)
    student = enrol_student(
        engine, settings, email=TARAS, class_id=school_class, inviter_email=OLENA
    )
    return TeacherScene(
        world.client_as(OLENA),
        institution,
        region_of(institution),
        school_class,
        student,
    )


def a_teacher(world: World) -> int:
    """Olena as a real teacher of two institutions, for the administrator's pages."""
    engine, settings = application.state.engine, application.state.settings
    kyiv = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    lviv = make_institution(engine, "Lviv School", "Lviv")
    return make_teacher(
        engine,
        settings,
        email=OLENA,
        institutions={kyiv: AccessLevel.WRITE, lviv: AccessLevel.READ},
    )


def subjects(world: World) -> tuple[int, int]:
    """An active and a deactivated subject."""
    with Session(application.state.engine) as session:
        physics = create_subject(session, "Physics")
        biology = create_subject(session, "Biology")
        assert physics.id is not None and biology.id is not None
        set_subject_active(session, biology.id, False)
        return physics.id, biology.id


def institutions(world: World) -> tuple[int, int, int]:
    """A region holding an active and a deactivated institution; `(region, active, other)`."""
    engine = application.state.engine
    academy = make_institution(engine, "Academy", "Kyiv")
    college = make_institution(engine, "College", "Kyiv", active=False)
    make_institution(engine, "Odesa College", "Odesa", region_active=False)
    return region_of(academy), academy, college


def institution_path(region: int, institution: int) -> str:
    return f"/admin/institutions/regions/{region}/institutions/{institution}"


# ---------------------------------------------------------------------------------------------
# Public and personal pages
# ---------------------------------------------------------------------------------------------


@case("login")
def _(w: World) -> Response:
    return w.client.get("/login", params={"next": "/profile"})


@case("login-invalid-email")
def _(w: World) -> Response:
    return w.client.post("/login", data={"email": "not-an-email", "next": "/"})


@case("login-code")
def _(w: World) -> Response:
    return w.client.post("/login", data={"email": "admin@example.com", "next": "/"})


@case("login-code-wrong")
def _(w: World) -> Response:
    w.client.post("/login", data={"email": "admin@example.com", "next": "/"})
    wrong = f"{(int(code_from(w.outbox[-1])) + 1) % 1_000_000:06d}"
    return w.client.post(
        "/login/code", data={"email": "admin@example.com", "code": wrong, "next": "/"}
    )


@case("role-choice")
def _(w: World) -> Response:
    return w.client_as(TEACHER_STUDENT_EMAIL).get("/role", params={"next": "/teacher"})


@case("role-choice-refused")
def _(w: World) -> Response:
    return w.client_as(TEACHER_STUDENT_EMAIL).post("/role", data={"role": "admin", "next": "/"})


@case("frame-with-role-switch")
def _(w: World) -> Response:
    return w.client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN).get("/")


@case("frame-single-role")
def _(w: World) -> Response:
    return w.admin.get("/")


@case("profile-teacher")
def _(w: World) -> Response:
    a_teacher(w)
    return w.client_as(OLENA).get("/profile")


@case("profile-withdraw")
def _(w: World) -> Response:
    a_teacher(w)
    return w.client_as(OLENA).get("/profile/withdraw")


@case("profile-withdraw-nothing-stored")
def _(w: World) -> Response:
    return w.admin.post("/profile/withdraw")


@case("teacher-invitation")
def _(w: World) -> Response:
    engine, settings = application.state.engine, application.state.settings
    school = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    token = invite(engine, settings, email=OLENA, institutions={school: AccessLevel.READ})
    return w.client.get(f"/invitations/{token}")


@case("teacher-invitation-consent-changed")
def _(w: World) -> Response:
    engine, settings = application.state.engine, application.state.settings
    school = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    token = invite(engine, settings, email=OLENA, institutions={school: AccessLevel.READ})
    return w.client.post(f"/invitations/{token}", data={"consent_text_id": "stale"})


@case("student-invitation")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    token = invite_student(
        application.state.engine,
        application.state.settings,
        email="ivan@example.org",
        class_id=scene.school_class,
        inviter_email=OLENA,
    )
    return w.client.get(f"/invitations/{token}")


@case("data-deletion-request")
def _(w: World) -> Response:
    return w.client.get("/data-deletion")


@case("data-deletion-request-invalid")
def _(w: World) -> Response:
    return w.client.post("/data-deletion", data={"email": "not-an-email"})


@case("data-deletion-confirm")
def _(w: World) -> Response:
    a_teacher(w)
    w.client.post("/data-deletion", data={"email": OLENA})
    return w.client.get(f"/data-deletion/confirm/{token_from(w.outbox[-1])}")


# ---------------------------------------------------------------------------------------------
# The administrator area
# ---------------------------------------------------------------------------------------------


@case("admin-subjects")
def _(w: World) -> Response:
    subjects(w)
    return w.admin.get("/admin/subjects")


@case("admin-subject-new")
def _(w: World) -> Response:
    return w.admin.get("/admin/subjects/new")


@case("admin-subject-new-duplicate")
def _(w: World) -> Response:
    subjects(w)
    return w.admin.post("/admin/subjects", data={"name": "physics"})


@case("admin-subject-rename")
def _(w: World) -> Response:
    physics, _ = subjects(w)
    return w.admin.get(f"/admin/subjects/{physics}/rename")


@case("admin-subject-delete")
def _(w: World) -> Response:
    physics, _ = subjects(w)
    return w.admin.get(f"/admin/subjects/{physics}/delete")


@case("admin-subject-delete-in-use")
def _(w: World) -> Response:
    physics, _ = subjects(w)
    w.monkeypatch.setattr(app.services.subjects, "count_subject_uses", lambda *_: 1)
    return w.admin.post(f"/admin/subjects/{physics}/delete")


@case("admin-institutions-region-selected")
def _(w: World) -> Response:
    region, _, _ = institutions(w)
    return w.admin.get(f"/admin/institutions/regions/{region}")


@case("admin-region-new")
def _(w: World) -> Response:
    return w.admin.get("/admin/institutions/regions/new")


@case("admin-region-new-invalid")
def _(w: World) -> Response:
    return w.admin.post("/admin/institutions/regions", data={"name": " "})


@case("admin-region-rename")
def _(w: World) -> Response:
    region, _, _ = institutions(w)
    return w.admin.get(f"/admin/institutions/regions/{region}/rename")


@case("admin-region-deactivate")
def _(w: World) -> Response:
    region, _, _ = institutions(w)
    return w.admin.get(f"/admin/institutions/regions/{region}/deactivate")


@case("admin-region-delete")
def _(w: World) -> Response:
    with Session(application.state.engine) as session:
        region = create_region(session, "Empty")
    return w.admin.get(f"/admin/institutions/regions/{region.id}/delete")


@case("admin-region-delete-not-empty")
def _(w: World) -> Response:
    region, _, _ = institutions(w)
    return w.admin.get(f"/admin/institutions/regions/{region}/delete")


@case("admin-institution-new")
def _(w: World) -> Response:
    region, _, _ = institutions(w)
    return w.admin.get(f"/admin/institutions/regions/{region}/institutions/new")


@case("admin-institution-new-invalid")
def _(w: World) -> Response:
    region, _, _ = institutions(w)
    return w.admin.post(f"/admin/institutions/regions/{region}/institutions", data={"name": ""})


@case("admin-institution-rename")
def _(w: World) -> Response:
    region, academy, _ = institutions(w)
    return w.admin.get(f"{institution_path(region, academy)}/rename")


@case("admin-institution-deactivate")
def _(w: World) -> Response:
    region, academy, _ = institutions(w)
    return w.admin.get(f"{institution_path(region, academy)}/deactivate")


@case("admin-institution-delete")
def _(w: World) -> Response:
    region, academy, _ = institutions(w)
    return w.admin.get(f"{institution_path(region, academy)}/delete")


@case("admin-institution-delete-in-use")
def _(w: World) -> Response:
    region, academy, _ = institutions(w)
    w.monkeypatch.setattr(
        app.services.institutions, "count_institution_uses", lambda session, institution_id: 1
    )
    return w.admin.post(f"{institution_path(region, academy)}/delete")


@case("admin-teachers")
def _(w: World) -> Response:
    a_teacher(w)
    return w.admin.get("/admin/teachers")


@case("admin-teacher-invite")
def _(w: World) -> Response:
    a_teacher(w)
    return w.admin.get("/admin/teachers/invite")


@case("admin-teacher-invite-invalid")
def _(w: World) -> Response:
    a_teacher(w)
    return w.admin.post(
        "/admin/teachers/invite", data={"email": "bad", "first_name": "", "last_name": ""}
    )


@case("admin-teacher-edit")
def _(w: World) -> Response:
    user_id = a_teacher(w)
    return w.admin.get(f"/admin/teachers/{user_id}")


@case("admin-teacher-edit-invalid")
def _(w: World) -> Response:
    user_id = a_teacher(w)
    return w.admin.post(f"/admin/teachers/{user_id}", data={"first_name": "", "last_name": ""})


@case("admin-teacher-remove")
def _(w: World) -> Response:
    user_id = a_teacher(w)
    return w.admin.get(f"/admin/teachers/{user_id}/remove")


# ---------------------------------------------------------------------------------------------
# The teacher area
# ---------------------------------------------------------------------------------------------


@case("teacher-students-nothing-selected")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get("/teacher/students")


@case("teacher-students-class-selected")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(scene.selection)


@case("teacher-class-new")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/institutions/{scene.institution}/classes/new")


@case("teacher-class-new-invalid")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.post(
        f"/teacher/students/institutions/{scene.institution}/classes",
        data={"name": "", "year_of_study": "two"},
    )


@case("teacher-class-edit")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/classes/{scene.school_class}/edit")


@case("teacher-class-deactivate")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/classes/{scene.school_class}/deactivate")


@case("teacher-class-deactivated-selected")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    scene.teacher.post(f"/teacher/students/classes/{scene.school_class}/deactivate")
    return scene.teacher.get(scene.selection)


@case("teacher-class-delete")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    empty = make_class(application.state.engine, scene.institution, "KN-22", 2)
    return scene.teacher.get(f"/teacher/students/classes/{empty}/delete")


@case("teacher-class-delete-has-students")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/classes/{scene.school_class}/delete")


@case("teacher-student-invite")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/classes/{scene.school_class}/invite")


@case("teacher-student-invite-invalid")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.post(
        f"/teacher/students/classes/{scene.school_class}/invite",
        data={"email": "bad", "first_name": "", "last_name": ""},
    )


@case("teacher-student-edit")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/{scene.student}")


@case("teacher-student-edit-invalid")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.post(
        f"/teacher/students/{scene.student}",
        data={"first_name": "", "last_name": "", "class_id": str(scene.school_class)},
    )


@case("teacher-student-remove")
def _(w: World) -> Response:
    scene = a_teacher_with_a_class(w)
    return scene.teacher.get(f"/teacher/students/{scene.student}/remove")


def a_question_manager(world: World) -> tuple[TestClient, int, int]:
    """Milestone 11: Olena with Can manage competitions, and Physics with one question;
    `(browser, subject, question)`."""
    engine, settings = application.state.engine, application.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(
        engine, settings, email=OLENA, institutions={institution: AccessLevel.READ}, can_manage=True
    )
    physics = make_subject(engine, "Physics")
    make_subject(engine, "Biology")
    question = make_question(engine, physics, "Why?", "Because.")
    return world.client_as(OLENA), physics, question


@case("teacher-questions-list")
def _(w: World) -> Response:
    """Its GET subject form: the no-script Show button adds no named field (research R11)."""
    browser, subject, _ = a_question_manager(w)
    return browser.get(f"/teacher/questions?subject={subject}")


@case("teacher-question-new")
def _(w: World) -> Response:
    browser, subject, _ = a_question_manager(w)
    return browser.get(f"/teacher/questions/new?subject={subject}&page=2")


@case("teacher-question-new-saved")
def _(w: World) -> Response:
    browser, subject, _ = a_question_manager(w)
    return browser.get(f"/teacher/questions/new?subject={subject}&page=2&saved=1")


@case("teacher-question-new-invalid")
def _(w: World) -> Response:
    browser, subject, _ = a_question_manager(w)
    return browser.post(
        "/teacher/questions",
        data={"subject": str(subject), "page": "2", "text": "", "reference_answer": ""},
    )


@case("teacher-question-edit")
def _(w: World) -> Response:
    browser, _, question = a_question_manager(w)
    return browser.get(f"/teacher/questions/{question}/edit?page=2")


@case("teacher-question-edit-invalid")
def _(w: World) -> Response:
    browser, _, question = a_question_manager(w)
    return browser.post(
        f"/teacher/questions/{question}/edit",
        data={"page": "2", "text": "", "reference_answer": ""},
    )


@case("teacher-question-delete")
def _(w: World) -> Response:
    browser, _, question = a_question_manager(w)
    return browser.get(f"/teacher/questions/{question}/delete?page=2")


def a_team(world: World) -> tuple[TeacherScene, int]:
    """Milestone 11.1: the class scene, with a team "Rockets" holding its student."""
    scene = a_teacher_with_a_class(world)
    team = make_team(application.state.engine, scene.institution)
    make_member(application.state.engine, team, scene.student)
    return scene, team


@case("teacher-teams-selected")
def _(w: World) -> Response:
    """The three GET lists, with the team selected."""
    scene, team = a_team(w)
    return scene.teacher.get(
        f"/teacher/teams?region={scene.region}&institution={scene.institution}&team={team}"
    )


@case("teacher-team-new")
def _(w: World) -> Response:
    scene, _ = a_team(w)
    return scene.teacher.get(f"/teacher/teams/institutions/{scene.institution}/new")


@case("teacher-team-new-invalid")
def _(w: World) -> Response:
    scene, _ = a_team(w)
    return scene.teacher.post(
        f"/teacher/teams/institutions/{scene.institution}/new", data={"name": ""}
    )


@case("teacher-team-add-students")
def _(w: World) -> Response:
    """With a class chosen: the hidden `student` and `class` of each Add."""
    scene, team = a_team(w)
    enrol_student(
        application.state.engine,
        application.state.settings,
        email="lesia@example.org",
        class_id=scene.school_class,
        inviter_email=OLENA,
        first="Lesia",
        last="Ukrainka",
    )
    return scene.teacher.get(f"/teacher/teams/{team}/add?class={scene.school_class}")


@case("teacher-team-rename")
def _(w: World) -> Response:
    scene, team = a_team(w)
    return scene.teacher.get(f"/teacher/teams/{team}/rename")


@case("teacher-team-rename-invalid")
def _(w: World) -> Response:
    scene, team = a_team(w)
    return scene.teacher.post(f"/teacher/teams/{team}/rename", data={"name": ""})


@case("teacher-team-delete")
def _(w: World) -> Response:
    scene, team = a_team(w)
    return scene.teacher.get(f"/teacher/teams/{team}/delete")


@case("teacher-team-member-remove")
def _(w: World) -> Response:
    scene, team = a_team(w)
    return scene.teacher.get(f"/teacher/teams/{team}/members/{scene.student}/remove")


# ---------------------------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------------------------


def _load() -> dict[str, list[dict[str, Any]]]:
    return json.loads(CONTRACT.read_text()) if CONTRACT.exists() else {}


@pytest.mark.parametrize("name", list(CASES))
def test_every_form_keeps_its_method_action_and_fields(
    name: str,
    client: TestClient,
    client_as: ClientAs,
    outbox: list[EmailMessage],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    response = CASES[name](World(client, client_as, outbox, monkeypatch))
    assert response.status_code < 500, (name, response.status_code)
    found = records(response)
    assert found, f"{name}: the page shows no form"

    if os.environ.get("UPDATE_FORM_CONTRACT") == "1":
        if request.node.callspec.params["database_url"] == "sqlite":
            contract = _load()
            contract[name] = found
            CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        return

    expected = _load().get(name)
    assert expected is not None, f"{name}: no entry in {CONTRACT.name}"
    missing = [record for record in expected if record not in found]
    added = [record for record in found if record not in expected]
    assert not missing and not added, (
        f"{name}: the forms changed.\nIn the contract, not on the page: {missing}\n"
        f"On the page, not in the contract: {added}"
    )


def test_the_contract_has_no_stale_cases() -> None:
    """Every entry of the file is still produced by a case, so none is silently dropped."""
    assert sorted(_load()) == sorted(CASES)
