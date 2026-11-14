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
- **Milestone 12.1**: the Competitions tab's pages (`teacher-competition*` cases) are new,
  generated once with `UPDATE_FORM_CONTRACT=1` for those cases only.
- **Milestone 12.2**: a competition's questions and teams (`teacher-competition-questions*`,
  `-teams*`, `-entry-*` cases) are new, generated once with `UPDATE_FORM_CONTRACT=1` for those
  cases only. The new menu entries of `teacher-competitions` are links, not forms, so that case
  is unchanged.
- **Milestone 12.3**: a team's answers (`teacher-team-answers*` cases) are new, generated once
  with `UPDATE_FORM_CONTRACT=1` for those cases only. An answer field's name holds its question's
  id, `answer-<id>`, recorded as `answer-{id}`. The new **Answers** menu entry of
  `teacher-competitions` is a link, so that case is unchanged.
- **Milestone 12.4**: finishing and grading (`teacher-competition-finish`, `teacher-grades*`,
  `teacher-team-answers-read-only` cases) are new, generated once with `UPDATE_FORM_CONTRACT=1`
  for those cases only. A grade field's name holds its question's id, `grade-<id>`, recorded as
  `grade-{id}`. The new **Grades** and **Finish competition** menu entries of
  `teacher-competitions` are links, so that case is unchanged.
"""

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session, select

import app.services.institutions
import app.services.subjects
from app.main import app as application
from app.models import AccessLevel, CompetitionTeam, Institution, Role
from app.services.email import EmailMessage
from app.services.regions import create_region
from app.services.subjects import create_subject, set_subject_active
from tests import html
from tests.conftest import (
    ADMIN_STUDENT_EMAIL,
    TEACHER_STUDENT_EMAIL,
    ClientAs,
    add_competition_question,
    add_competition_team,
    enrol_student,
    invite,
    invite_student,
    make_class,
    make_competition,
    make_institution,
    make_member,
    make_question,
    make_subject,
    make_teacher,
    make_team,
    save_team_answer,
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
        fields = {re.sub(r"^(answer|grade)-\d+$", r"\1-{id}", name) for name in fields}
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
# Milestone 12.1: the Competitions tab
# ---------------------------------------------------------------------------------------------


def a_competition_manager(world: World, *, cancelled: bool = False) -> tuple[TestClient, int, int]:
    """Olena with Can manage competitions, and Chemistry with one upcoming competition (or a
    cancelled one); `(browser, subject, competition)`."""
    engine, settings = application.state.engine, application.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(
        engine, settings, email=OLENA, institutions={institution: AccessLevel.READ}, can_manage=True
    )
    chemistry = make_subject(engine, "Chemistry")
    make_subject(engine, "Physics")
    start = datetime(2100, 3, 14, 8, 0, tzinfo=UTC)
    competition = make_competition(engine, chemistry, starts_at=start, cancelled=cancelled)
    browser = world.client_as(OLENA)
    browser.cookies.set("sc_time_zone", "Europe/Kyiv")
    return browser, chemistry, competition


@case("teacher-competitions")
def _(w: World) -> Response:
    """Its two GET forms, subject and status: the no-script Show buttons add no named field."""
    browser, subject, _ = a_competition_manager(w)
    return browser.get(f"/teacher/competitions?subject={subject}&status=upcoming&page=2")


@case("teacher-competition-new")
def _(w: World) -> Response:
    browser, subject, _ = a_competition_manager(w)
    return browser.get(f"/teacher/competitions/new?subject={subject}&status=upcoming&page=2")


@case("teacher-competition-new-invalid")
def _(w: World) -> Response:
    browser, subject, _ = a_competition_manager(w)
    return browser.post(
        "/teacher/competitions",
        data={
            "subject": str(subject),
            "status": "upcoming",
            "page": "2",
            "name": "",
            "start_date": "",
            "start_time": "",
            "time_zone": "Europe/Kyiv",
        },
    )


@case("teacher-competition-edit")
def _(w: World) -> Response:
    browser, subject, competition = a_competition_manager(w)
    return browser.get(f"/teacher/competitions/{competition}/edit?subject={subject}&page=2")


@case("teacher-competition-cancel")
def _(w: World) -> Response:
    browser, subject, competition = a_competition_manager(w)
    return browser.get(f"/teacher/competitions/{competition}/cancel?subject={subject}&page=2")


@case("teacher-competition-refused")
def _(w: World) -> Response:
    """A refusal has no form of its own; the page keeps the frame's forms."""
    browser, subject, competition = a_competition_manager(w, cancelled=True)
    return browser.get(f"/teacher/competitions/{competition}/cancel?subject={subject}")


# ---------------------------------------------------------------------------------------------
# Milestone 12.2: a competition's questions and teams
# ---------------------------------------------------------------------------------------------


@dataclass
class Entries:
    browser: TestClient
    base: str
    """The competition's address."""
    context: str
    """The competitions list's subject, status and page."""
    question: int
    """A question in the competition."""
    team: int
    """A team in the competition."""
    region: int
    """Kyiv, where both teams are."""


def competition_entries(world: World, *, cancelled: bool = False) -> Entries:
    """`a_competition_manager`'s competition holding a question and a team of Kyiv, with another
    question and team to add."""
    browser, subject, competition = a_competition_manager(world, cancelled=cancelled)
    engine = application.state.engine
    with Session(engine) as session:
        (institution,) = session.exec(select(Institution)).all()
        assert institution.id is not None
    question = make_question(engine, subject, "Comets?")
    team = make_team(engine, institution.id, "Comets")
    make_question(engine, subject, "Novas?")
    make_team(engine, institution.id, "Novas")
    add_competition_question(engine, competition, question)
    add_competition_team(engine, competition, team)
    return Entries(
        browser,
        f"/teacher/competitions/{competition}",
        f"subject={subject}&status=upcoming&page=2",
        question,
        team,
        institution.region_id,
    )


@case("teacher-competition-questions")
def _(w: World) -> Response:
    """Its Remove entries are links: only the frame's forms."""
    e = competition_entries(w)
    return e.browser.get(f"{e.base}/questions?{e.context}")


@case("teacher-competition-questions-add")
def _(w: World) -> Response:
    e = competition_entries(w)
    return e.browser.get(f"{e.base}/questions/add?{e.context}&back=2")


@case("teacher-competition-teams")
def _(w: World) -> Response:
    e = competition_entries(w)
    return e.browser.get(f"{e.base}/teams?{e.context}")


@case("teacher-competition-teams-add")
def _(w: World) -> Response:
    """With a region chosen: the Region `GET` form and the Add forms."""
    e = competition_entries(w)
    return e.browser.get(f"{e.base}/teams/add?{e.context}&back=2&region={e.region}")


@case("teacher-competition-entry-remove-question")
def _(w: World) -> Response:
    e = competition_entries(w)
    return e.browser.get(f"{e.base}/questions/{e.question}/remove?{e.context}&back=2")


@case("teacher-competition-entry-remove-team")
def _(w: World) -> Response:
    e = competition_entries(w)
    return e.browser.get(f"{e.base}/teams/{e.team}/remove?{e.context}&back=2")


@case("teacher-competition-entry-refused")
def _(w: World) -> Response:
    """A refusal has no form of its own; the page keeps the frame's forms."""
    e = competition_entries(w, cancelled=True)
    return e.browser.get(f"{e.base}/questions/add?{e.context}")


def team_answers_scene(world: World, *, cancelled: bool = False) -> tuple[TestClient, str, str]:
    """Taras with Write access to School No. 5, and Chemistry's competition that started an hour
    ago (or was cancelled), holding two questions and the school's team "Comets", with one
    answer; `(browser, the competition's address, the competitions-list context)`."""
    engine, settings = application.state.engine, application.state.settings
    school = make_institution(engine, "School No. 5", "Kyiv")
    make_teacher(engine, settings, email=TARAS, institutions={school: AccessLevel.WRITE})
    chemistry = make_subject(engine, "Chemistry")
    start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(hours=1)
    competition = make_competition(engine, chemistry, starts_at=start, cancelled=cancelled)
    copies = [
        add_competition_question(engine, competition, make_question(engine, chemistry, text))
        for text in ("Salt?", "Water?")
    ]
    team = make_team(engine, school, "Comets")
    add_competition_team(engine, competition, team)
    save_team_answer(engine, competition, team, copies[0], "NaCl")
    browser = world.client_as(TARAS)
    browser.cookies.set("sc_time_zone", "Europe/Kyiv")
    return browser, f"/teacher/competitions/{competition}/answers", f"subject={chemistry}&page=2"


def team_of(base: str) -> int:
    competition = int(base.split("/")[3])
    with Session(application.state.engine) as session:
        return session.exec(
            select(CompetitionTeam.team_id).where(CompetitionTeam.competition_id == competition)
        ).one()


@case("teacher-team-answers")
def _(w: World) -> Response:
    """The team answers page: Enter answers is a link, so only the frame's forms."""
    browser, base, context = team_answers_scene(w)
    return browser.get(f"{base}?{context}")


@case("teacher-team-answers-sheet")
def _(w: World) -> Response:
    """The sheet with an answer: the save form, its hidden context and the answer fields."""
    browser, base, context = team_answers_scene(w)
    return browser.get(f"{base}/{team_of(base)}?{context}&back=2")


@case("teacher-team-answers-sheet-invalid")
def _(w: World) -> Response:
    """The 400 page after an answer that is too long: the same form."""
    browser, base, context = team_answers_scene(w)
    team = team_of(base)
    page = browser.get(f"{base}/{team}?{context}&back=2").text
    form = {i.name: i.value for f in html.forms(page) if "/answers/" in f.action for i in f.inputs}
    answer = next(name for name in form if name and name.startswith("answer-"))
    return browser.post(f"{base}/{team}", data=form | {answer: "x" * 2001})


@case("teacher-team-answers-refused")
def _(w: World) -> Response:
    """A refusal has no form of its own; the page keeps the frame's forms."""
    browser, base, context = team_answers_scene(w, cancelled=True)
    return browser.get(f"{base}?{context}")


# ---------------------------------------------------------------------------------------------
# Milestone 12.4: finishing and grading
# ---------------------------------------------------------------------------------------------


def grading_scene(world: World) -> tuple[TestClient, str, str, int]:
    """Olena with Can manage competitions, and Chemistry's finished competition holding two
    questions and School No. 5's team "Comets", which answered the first; `(browser, the
    competition's address, the competitions-list context, the team)`."""
    engine, settings = application.state.engine, application.state.settings
    school = make_institution(engine, "School No. 5", "Kyiv")
    make_teacher(
        engine, settings, email=OLENA, institutions={school: AccessLevel.READ}, can_manage=True
    )
    chemistry = make_subject(engine, "Chemistry")
    start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(hours=2)
    competition = make_competition(engine, chemistry, starts_at=start, stopped=True)
    copies = [
        add_competition_question(engine, competition, make_question(engine, chemistry, text))
        for text in ("Salt?", "Water?")
    ]
    team = make_team(engine, school, "Comets")
    add_competition_team(engine, competition, team)
    save_team_answer(engine, competition, team, copies[0], "NaCl")
    browser = world.client_as(OLENA)
    browser.cookies.set("sc_time_zone", "Europe/Kyiv")
    context = f"subject={chemistry}&status=finished&page=2"
    return browser, f"/teacher/competitions/{competition}", context, team


@case("teacher-competition-finish")
def _(w: World) -> Response:
    """The finish confirmation of an In progress competition: one post form, the context."""
    engine = application.state.engine
    browser, subject, _ = a_competition_manager(w)
    start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(hours=1)
    running = make_competition(engine, subject, "Running", starts_at=start)
    return browser.get(f"/teacher/competitions/{running}/finish?subject={subject}&page=2")


@case("teacher-grades")
def _(w: World) -> Response:
    """The Grades page: the filter and Grade answers are links, so only the frame's forms."""
    browser, base, context, _ = grading_scene(w)
    return browser.get(f"{base}/grades?{context}")


@case("teacher-grades-sheet")
def _(w: World) -> Response:
    """The grading sheet: the save form, its hidden context and one grade field per answer."""
    browser, base, context, team = grading_scene(w)
    return browser.get(f"{base}/grades/{team}?{context}&show=ungraded&back=2")


@case("teacher-grades-sheet-invalid")
def _(w: World) -> Response:
    """The 400 page after an invalid grade: the same form."""
    browser, base, context, team = grading_scene(w)
    page = browser.get(f"{base}/grades/{team}?{context}&show=ungraded&back=2").text
    form = {i.name: i.value for f in html.forms(page) if "/grades/" in f.action for i in f.inputs}
    grade = next(name for name in form if name and name.startswith("grade-"))
    return browser.post(f"{base}/grades/{team}", data=form | {grade: "11"})


@case("teacher-team-answers-read-only")
def _(w: World) -> Response:
    """The read-only sheet of a finished competition: no form of its own."""
    engine, settings = application.state.engine, application.state.settings
    browser, base, context, team = grading_scene(w)
    (school,) = application_institutions()
    make_teacher(engine, settings, email=TARAS, institutions={school: AccessLevel.WRITE})
    reader = w.client_as(TARAS)
    response = reader.get(f"{base}/answers/{team}?{context}")
    assert response.status_code == 200 and "Score: 0" in response.text
    return response


def application_institutions() -> list[int]:
    with Session(application.state.engine) as session:
        return [i.id for i in session.exec(select(Institution)).all() if i.id is not None]


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
