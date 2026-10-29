"""The Teams tab, end to end through the test client: every user story of milestone 11.1 that a
page or an action shows.

See specs/011.1-teacher-teams/spec.md US1–US6, contracts/http-routes.md and research R17. The
people are real (invited and accepted):

- Olena: Write to "Kyiv Polytechnic Institute" (Kyiv) and "Lviv Academy" (Lviv), Read to "Odesa
  College" (Odesa);
- Mykola: Read to "Kyiv Polytechnic Institute";
- Iryna: Write to "Odesa College";
- Taras Shevchenko (class "KN-21", year 2) and Lesia Ukrainka ("KN-31", year 3), students of
  "Kyiv Polytechnic Institute".

Teams and memberships are created through the pages, or seeded with `make_team` and
`make_member` where the page is not what the case is about. Every case runs on both engines.
"""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, func
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from app.core.db import utc_now
from app.core.sealing import seal
from app.main import app
from app.models import (
    AccessLevel,
    Enrolment,
    Institution,
    Role,
    SchoolClass,
    Team,
    TeamMembership,
    User,
    UserRole,
)
from app.routers.teacher_teams import TEAM_NOTICE_PURPOSE, seal_member_notice
from app.services.institutions import set_institution_active
from app.services.regions import set_region_active
from app.services.teachers import update_teacher
from app.services.teams import MAX_MEMBERS, count_members
from app.services.users import get_roles
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    enrol_student,
    make_class,
    make_institution,
    make_member,
    make_teacher,
    make_team,
    seed_roles_directly,
)

OLENA = "olena@example.org"
MYKOLA = "mykola@example.org"
IRYNA = "iryna@example.org"
TARAS = "taras@example.org"
LESIA = "lesia@example.org"

TAB = "/teacher/teams"
DENIED = "Access denied"


@dataclass(frozen=True)
class Scene:
    olena: TestClient
    mykola: TestClient
    olena_id: int
    kyiv: int
    lviv: int
    odesa: int
    kpi: int
    academy: int
    college: int
    kn21: int
    kn31: int
    taras: int
    lesia: int

    def tab(self, team: int | None = None, *, institution: int | None = None) -> str:
        """The tab with `institution` (Kyiv Polytechnic Institute by default) and `team`."""
        institution = institution or self.kpi
        region = {self.kpi: self.kyiv, self.academy: self.lviv, self.college: self.odesa}[
            institution
        ]
        path = f"{TAB}?region={region}&institution={institution}"
        return path if team is None else f"{path}&team={team}"


def region_of(institution_id: int) -> int:
    with Session(app.state.engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    kpi = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    academy = make_institution(engine, "Lviv Academy", "Lviv")
    college = make_institution(engine, "Odesa College", "Odesa")
    olena_id = make_teacher(
        engine,
        settings,
        email=OLENA,
        institutions={
            kpi: AccessLevel.WRITE,
            academy: AccessLevel.WRITE,
            college: AccessLevel.READ,
        },
    )
    make_teacher(
        engine, settings, email=MYKOLA, institutions={kpi: AccessLevel.READ}, first="Mykola"
    )
    make_teacher(
        engine, settings, email=IRYNA, institutions={college: AccessLevel.WRITE}, first="Iryna"
    )
    kn21 = make_class(engine, kpi, "KN-21", 2)
    kn31 = make_class(engine, kpi, "KN-31", 3)
    return Scene(
        olena=client_as(OLENA),
        mykola=client_as(MYKOLA),
        olena_id=olena_id,
        kyiv=region_of(kpi),
        lviv=region_of(academy),
        odesa=region_of(college),
        kpi=kpi,
        academy=academy,
        college=college,
        kn21=kn21,
        kn31=kn31,
        taras=student(TARAS, kn21),
        lesia=student(LESIA, kn31, "Lesia", "Ukrainka"),
    )


def student(
    email: str, class_id: int, first: str = "Taras", last: str = "Shevchenko", by: str = OLENA
) -> int:
    return enrol_student(
        app.state.engine,
        app.state.settings,
        email=email,
        class_id=class_id,
        inviter_email=by,
        first=first,
        last=last,
    )


def team_row(team_id: int) -> Team:
    with Session(app.state.engine) as session:
        team = session.get(Team, team_id)
        assert team is not None
        return team


def teams() -> list[tuple[int, str, bool]]:
    with Session(app.state.engine) as session:
        rows = session.exec(select(Team).order_by(col(Team.id)))
        return [(t.institution_id, t.name, t.deleted_at is not None) for t in rows]


def memberships(team_id: int | None = None) -> list[tuple[int, int]]:
    with Session(app.state.engine) as session:
        statement = select(TeamMembership)
        if team_id is not None:
            statement = statement.where(TeamMembership.team_id == team_id)
        return sorted((m.team_id, m.user_id) for m in session.exec(statement))


SNAPSHOT_TABLES = ("teams", "team_memberships", "enrolments", "user_roles", "users", "classes")


def snapshot() -> dict[str, list[tuple[Any, ...]]]:
    engine: Engine = app.state.engine
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(sa_select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def create(scene: Scene, name: str, institution: int | None = None):  # type: ignore[no-untyped-def]
    institution = institution or scene.kpi
    return scene.olena.post(
        f"{TAB}/institutions/{institution}/new", data={"name": name}, follow_redirects=False
    )


def created_id(response: Any) -> int:
    assert response.status_code == 303, response.text
    found = re.search(r"&team=(\d+)$", response.headers["location"])
    assert found is not None, response.headers["location"]
    return int(found.group(1))


def add(  # type: ignore[no-untyped-def]
    scene: Scene, team: int, user: int | str, class_id: int | str | None = None, by=None
):
    data = {"student": str(user)}
    if class_id is not None:
        data["class"] = str(class_id)
    return (by or scene.olena).post(f"{TAB}/{team}/members", data=data, follow_redirects=False)


def notice_boxes(body: str) -> list[tuple[str, str]]:
    """`(kind, text)` of every notice on the page."""
    found = []
    for element in html.parse(body).iter():
        classes = element.classes()
        if "notice" in classes:
            kind = next(c.removeprefix("notice-") for c in classes if c.startswith("notice-"))
            found.append((kind, element.text()))
    return found


def members_shown(body: str) -> list[tuple[str, str]]:
    return [(row["Name"], row["Class"]) for row in html.table_rows(body)]


def empty_state(body: str) -> tuple[str, str | None]:
    (state,) = [e for e in html.parse(body).iter() if "empty-state" in e.classes()]
    message = [p.text() for p in state.find_all("p") if "empty-state-message" in p.classes()]
    hint = [p.text() for p in state.find_all("p") if "empty-state-hint" in p.classes()]
    return message[0], hint[0] if hint else None


def team_heading(body: str) -> str:
    (heading,) = [e for e in html.parse(body).find_all("h2") if e.attrs.get("id") == "team-heading"]
    return heading.text()


def disabled(body: str, name: str) -> bool:
    return "disabled" in html.control(body, name)


def set_class(class_id: int, active: bool) -> None:
    with Session(app.state.engine) as session:
        school_class = session.get(SchoolClass, class_id)
        assert school_class is not None
        school_class.is_active = active
        session.add(school_class)
        session.commit()


# ---------------------------------------------------------------------------------------------
# US1: the tab, the lists and the states
# ---------------------------------------------------------------------------------------------


def test_the_tab_row_holds_four_tabs_with_teams_second(scene: Scene) -> None:
    """US1-1, FR-025."""
    body = scene.olena.get(TAB).text
    tabs = html.nav(body, "Teacher area")
    assert [(t.href, t.text) for t in tabs] == [
        ("/teacher/students", "Students"),
        (TAB, "Teams"),
        ("/teacher/questions", "Questions"),
        ("/teacher/competitions", "Competitions"),
    ]
    assert [t.text for t in tabs if t.attrs.get("aria-current") == "page"] == ["Teams"]
    assert html.h1(body) == "Teams"
    assert scene.olena.get("/teacher", follow_redirects=False).headers["location"] == (
        "/teacher/students"
    )


def test_the_lists_are_disabled_in_turn_and_match_students(scene: Scene) -> None:
    """US1-2, FR-028: Region and Educational institution offer exactly what Students offers."""
    nothing = scene.olena.get(TAB).text
    assert not disabled(nothing, "region")
    assert disabled(nothing, "institution") and disabled(nothing, "team")
    assert empty_state(nothing) == (
        "Select a region to continue",
        "Choose a region in the first list.",
    )
    students = scene.olena.get("/teacher/students").text
    assert html.options(nothing, "region") == html.options(students, "region")

    region = scene.olena.get(f"{TAB}?region={scene.kyiv}").text
    assert not disabled(region, "institution") and disabled(region, "team")
    assert empty_state(region) == (
        "Select an educational institution to continue",
        "Choose an educational institution in the second list.",
    )
    students = scene.olena.get(f"/teacher/students?region={scene.kyiv}").text
    assert html.options(region, "institution") == html.options(students, "institution")
    assert [o.text for o in html.options(region, "institution")] == [
        "Select an educational institution",
        "Kyiv Polytechnic Institute — Write",
    ]
    odesa = scene.olena.get(f"{TAB}?region={scene.odesa}").text
    assert "Odesa College — Read" in [o.text for o in html.options(odesa, "institution")]

    chosen = scene.olena.get(scene.tab()).text
    assert not disabled(chosen, "team")
    assert empty_state(chosen) == ("No teams yet", "Create the first team with + Add team.")


def test_the_team_list_offers_live_teams_ignoring_case_then_add_team(scene: Scene) -> None:
    """US1-3, FR-028, FR-029."""
    ids = {
        name: make_team(app.state.engine, scene.kpi, name) for name in ("gamma", "Beta", "alpha")
    }
    make_team(app.state.engine, scene.kpi, "Aardvark", deleted=True)
    make_team(app.state.engine, scene.academy, "Elsewhere")
    body = scene.olena.get(scene.tab()).text
    assert [(o.value, o.text) for o in html.options(body, "team")] == [
        ("", "Select a team"),
        (str(ids["alpha"]), "alpha"),
        (str(ids["Beta"]), "Beta"),
        (str(ids["gamma"]), "gamma"),
        ("new", "+ Add team"),
    ]
    assert empty_state(body) == (
        "Select a team to see its members",
        "Choose a team in the third list.",
    )
    read = scene.mykola.get(scene.tab()).text
    assert [o.text for o in html.options(read, "team")][-1] == "gamma"


def test_a_teacher_with_no_link_sees_disabled_lists(scene: Scene, client_as: ClientAs) -> None:
    """Spec Edge Cases, FR-029: the cast teacher has no link."""
    body = client_as(TEACHER_EMAIL).get(TAB).text
    assert all(disabled(body, name) for name in ("region", "institution", "team"))
    assert empty_state(body) == (
        "You are not linked to any educational institution",
        "Ask an administrator to link you to an educational institution.",
    )


def test_without_javascript_each_list_has_a_show_button(scene: Scene) -> None:
    body = scene.olena.get(scene.tab()).text
    assert body.count("<noscript>") == 3
    forms = [f for f in html.forms(body) if f.method == "get"]
    assert [f.action for f in forms] == [TAB, TAB, TAB]
    assert ("institution", "hidden", str(scene.kpi)) in forms[2].inputs


def test_read_access_shows_the_read_hint_and_no_add_team(scene: Scene) -> None:
    """US4-2, FR-029."""
    body = scene.mykola.get(scene.tab()).text
    assert empty_state(body) == (
        "No teams yet",
        "A teacher with Write access to this institution creates its teams.",
    )
    assert "+ Add team" not in body


# ---------------------------------------------------------------------------------------------
# US1: creating a team
# ---------------------------------------------------------------------------------------------


def test_add_team_opens_the_form_with_write_and_is_denied_with_read(scene: Scene) -> None:
    """US1-4, FR-032."""
    response = scene.olena.get(f"{scene.tab()}&team=new", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{TAB}/institutions/{scene.kpi}/new"
    form = scene.olena.get(response.headers["location"]).text
    assert html.h1(form) == "New team in “Kyiv Polytechnic Institute”"
    assert "Educational institution: Kyiv Polytechnic Institute (Kyiv)" in form
    (post,) = [f for f in html.forms(form, "main") if f.method == "post"]
    assert post.action == f"{TAB}/institutions/{scene.kpi}/new"
    assert [i.name for i in post.inputs] == ["name"]
    assert html.control(form, "name")["maxlength"] == "200"
    links = html.link_pairs(form, "main")
    assert (scene.tab(), "Back to Teams") in links
    assert (scene.tab(), "Cancel") in links
    assert scene.mykola.get(f"{scene.tab()}&team=new").status_code == 403


def test_a_team_is_created_trimmed_and_selected(scene: Scene) -> None:
    """US1-5, US1-6, US3-4, FR-031."""
    response = create(scene, "  Rockets  ")
    team = created_id(response)
    assert response.headers["location"] == scene.tab(team)
    assert teams() == [(scene.kpi, "Rockets", False)]
    body = scene.olena.get(response.headers["location"]).text
    assert [(o.text, o.selected) for o in html.options(body, "team") if o.selected] == [
        ("Rockets", True)
    ]
    assert team_heading(body) == "Rockets"
    assert empty_state(body) == (
        "No members in this team yet",
        "Add the first student with Add students.",
    )


def test_only_the_name_is_read_from_the_form(scene: Scene) -> None:
    """FR-001: an institution in the form is ignored."""
    scene.olena.post(
        f"{TAB}/institutions/{scene.kpi}/new",
        data={"name": "Rockets", "institution_id": str(scene.academy)},
    )
    assert teams() == [(scene.kpi, "Rockets", False)]


# ---------------------------------------------------------------------------------------------
# US1: Add students and the addition
# ---------------------------------------------------------------------------------------------


def test_add_students_offers_the_active_classes(scene: Scene) -> None:
    """US1-7, FR-038."""
    team = make_team(app.state.engine, scene.kpi)
    make_class(app.state.engine, scene.kpi, "aa-1", 1)
    make_class(app.state.engine, scene.kpi, "KN-11", 1, active=False)
    body = scene.olena.get(f"{TAB}/{team}/add").text
    assert html.h1(body) == "Add students to “Rockets”"
    assert (scene.tab(team), "Back to “Rockets”") in html.link_pairs(body, "main")
    assert [o.text for o in html.options(body, "class")] == [
        "Select a class",
        "aa-1 · year 1",
        "KN-21 · year 2",
        "KN-31 · year 3",
    ]
    assert empty_state(body) == (
        "Select a class to see its students",
        "Choose a class in the list.",
    )
    (form,) = [f for f in html.forms(body) if f.method == "get"]
    assert form.action == f"{TAB}/{team}/add"
    assert "<noscript>" in body


def test_a_chosen_class_lists_its_students_with_add(scene: Scene) -> None:
    """US1-8, US1-9, FR-039."""
    team = make_team(app.state.engine, scene.kpi)
    andriy = student("andriy@example.org", scene.kn21, "Andriy", "Antonenko")
    make_member(app.state.engine, team, scene.taras)
    body = scene.olena.get(f"{TAB}/{team}/add?class={scene.kn21}").text
    assert [o.value for o in html.options(body, "class") if o.selected] == [str(scene.kn21)]
    rows = html.table_rows(body)
    assert [r["Name"] for r in rows] == ["Antonenko Andriy", "Shevchenko Taras"]
    adds = [f for f in html.forms(body, "main") if f.method == "post"]
    assert len(adds) == 1
    assert adds[0].action == f"{TAB}/{team}/members"
    assert ("student", "hidden", str(andriy)) in adds[0].inputs
    assert ("class", "hidden", str(scene.kn21)) in adds[0].inputs
    assert [b.text for b in adds[0].buttons] == ["Add"]
    notes = [e.text() for e in html.parse(body).iter() if "row-note" in e.classes()]
    assert notes == ["In this team"]


def test_an_empty_class_says_so(scene: Scene) -> None:
    """US1-13."""
    team = make_team(app.state.engine, scene.kpi)
    empty = make_class(app.state.engine, scene.kpi, "KN-41", 4)
    body = scene.olena.get(f"{TAB}/{team}/add?class={empty}").text
    assert empty_state(body) == ("No students in this class yet", None)


def test_adding_returns_to_the_team_with_a_notice(scene: Scene) -> None:
    """US1-10, US1-11, FR-040, FR-031: from two classes, listed by last name."""
    team = created_id(create(scene, "Rockets"))
    response = add(scene, team, scene.taras, scene.kn21)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"{scene.tab(team)}&notice=")
    body = scene.olena.get(location).text
    assert notice_boxes(body) == [("success", "Taras Shevchenko was added to the team.")]
    assert members_shown(body) == [("Shevchenko Taras", "KN-21 · year 2")]
    second = add(scene, team, scene.lesia, scene.kn31)
    body = scene.olena.get(second.headers["location"]).text
    assert notice_boxes(body) == [("success", "Lesia Ukrainka was added to the team.")]
    assert members_shown(body) == [
        ("Shevchenko Taras", "KN-21 · year 2"),
        ("Ukrainka Lesia", "KN-31 · year 3"),
    ]
    assert memberships() == sorted([(team, scene.taras), (team, scene.lesia)])


def test_adding_changes_nothing_about_the_student(scene: Scene) -> None:
    """US1-12, FR-005: Students still lists them in the same class."""
    team = make_team(app.state.engine, scene.kpi)
    before = {k: v for k, v in snapshot().items() if k in ("enrolments", "user_roles", "users")}
    add(scene, team, scene.taras, scene.kn21)
    after = {k: v for k, v in snapshot().items() if k in ("enrolments", "user_roles", "users")}
    assert after == before
    students = scene.olena.get(
        f"/teacher/students?region={scene.kyiv}&institution={scene.kpi}&class={scene.kn21}"
    ).text
    assert "Shevchenko Taras" in [r["Name"] for r in html.table_rows(students)]


@pytest.mark.parametrize("token", ["stale", "tampered", "other-team", "not-a-member", "outcome"])
def test_a_notice_shows_only_for_a_fresh_token_of_this_team_and_member(
    scene: Scene, token: str
) -> None:
    """Research R11: anything else shows no notice, and the page is not an error."""
    team = make_team(app.state.engine, scene.kpi)
    other = make_team(app.state.engine, scene.kpi, "Comets")
    make_member(app.state.engine, team, scene.taras)
    secret = app.state.settings.secret_key
    payload = {"team": team, "user": scene.taras, "outcome": "added"}
    value = {
        "stale": seal(secret, TEAM_NOTICE_PURPOSE, payload, now=utc_now() - timedelta(minutes=11)),
        "tampered": seal_member_notice(app.state.settings, team, scene.taras, "added")[:-3] + "AAA",
        "other-team": seal_member_notice(app.state.settings, other, scene.taras, "added"),
        "not-a-member": seal_member_notice(app.state.settings, team, scene.lesia, "added"),
        "outcome": seal_member_notice(app.state.settings, team, scene.taras, "removed"),
    }[token]
    response = scene.olena.get(f"{scene.tab(team)}&notice={value}")
    assert response.status_code == 200
    assert notice_boxes(response.text) == []
    fresh = seal_member_notice(app.state.settings, team, scene.taras, "already")
    assert notice_boxes(scene.olena.get(f"{scene.tab(team)}&notice={fresh}").text) == [
        ("info", "Taras Shevchenko is already in this team.")
    ]


def test_reloading_after_create_and_add_repeats_nothing(scene: Scene) -> None:
    """SC-010, FR-044."""
    created = create(scene, "Rockets")
    team = created_id(created)
    added = add(scene, team, scene.taras, scene.kn21)
    before = snapshot()
    for location in (created.headers["location"], added.headers["location"]):
        for _ in range(2):
            assert scene.olena.get(location).status_code == 200
    assert snapshot() == before


# ---------------------------------------------------------------------------------------------
# US2: the heading, rename, remove and delete
# ---------------------------------------------------------------------------------------------


def test_with_write_the_team_heading_has_every_action(scene: Scene) -> None:
    """US2-1, FR-034, FR-035: the `section_heading` markup."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    body = scene.olena.get(scene.tab(team)).text
    start = body.index('<section aria-labelledby="team-heading">')
    heading = re.sub(r">\s+<", "><", body[start : body.index("<table", start)]).strip()
    path = f"{TAB}/{team}"
    assert heading == (
        '<section aria-labelledby="team-heading"><div class="page-heading">'
        '<h2 id="team-heading">Rockets</h2>'
        f'<a href="{path}/add" role="button">Add students</a></div>'
        '<div class="row-actions">'
        f'<a href="{path}/rename" role="button" class="secondary outline small">Rename</a>'
        f'<a href="{path}/delete" role="button" class="destructive outline small">Delete</a>'
        "</div>"
    )
    assert (f"{path}/members/{scene.taras}/remove", "Remove") in html.link_pairs(body, "main")
    assert html.table_rows(body) == [
        {"Name": "Shevchenko Taras", "Class": "KN-21 · year 2", "Actions": "Remove"}
    ]


def test_with_read_the_team_has_no_action(scene: Scene) -> None:
    """US4-2, FR-024, FR-034, FR-035."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    body = scene.mykola.get(scene.tab(team)).text
    start = body.index('<section aria-labelledby="team-heading">')
    heading = re.sub(r">\s+<", "><", body[start : body.index("<table", start)]).strip()
    assert heading == (
        '<section aria-labelledby="team-heading"><div class="page-heading">'
        '<h2 id="team-heading">Rockets</h2></div>'
    )
    assert html.table_rows(body) == [{"Name": "Shevchenko Taras", "Class": "KN-21 · year 2"}]
    for word in ("+ Add team", "Add students", "Rename", "Delete", "Remove"):
        assert word not in html.text(body, "main"), word
    empty = make_team(app.state.engine, scene.kpi, "Comets")
    assert empty_state(scene.mykola.get(scene.tab(empty)).text) == (
        "No members in this team yet",
        None,
    )


def test_rename_opens_the_filled_form_and_returns_to_the_team(scene: Scene) -> None:
    """US2-2, FR-032."""
    team = make_team(app.state.engine, scene.kpi)
    form = scene.olena.get(f"{TAB}/{team}/rename").text
    assert html.h1(form) == "Rename team “Rockets”"
    assert html.control(form, "name")["value"] == "Rockets"
    assert (scene.tab(team), "Back to “Rockets”") in html.link_pairs(form, "main")
    assert (scene.tab(team), "Cancel") in html.link_pairs(form, "main")
    response = scene.olena.post(
        f"{TAB}/{team}/rename", data={"name": "Comets"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.tab(team)
    assert team_heading(scene.olena.get(scene.tab(team)).text) == "Comets"
    assert team_row(team).name == "Comets"


def test_remove_asks_then_takes_only_the_membership(scene: Scene, client_as: ClientAs) -> None:
    """US2-3, US2-4, FR-006, FR-036."""
    team = make_team(app.state.engine, scene.kpi, "Comets")
    other = make_team(app.state.engine, scene.kpi, "Rockets")
    for t in (team, other):
        make_member(app.state.engine, t, scene.taras)
    make_member(app.state.engine, team, scene.lesia)
    taras_browser = client_as(TARAS)
    page = scene.olena.get(f"{TAB}/{team}/members/{scene.taras}/remove").text
    assert html.h1(page) == "Remove Taras Shevchenko from team “Comets”?"
    assert ("Class", "KN-21 · year 2") in html.details(page)
    assert "They stay in their class and keep their account and their other teams." in page
    assert (scene.tab(team), "Back to “Comets”") in html.link_pairs(page, "main")
    assert html.form_targets(page, "main")[0] == (
        "post",
        f"{TAB}/{team}/members/{scene.taras}/remove",
    )
    before = snapshot()
    response = scene.olena.post(
        f"{TAB}/{team}/members/{scene.taras}/remove", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.tab(team)
    assert members_shown(scene.olena.get(scene.tab(team)).text) == [
        ("Ukrainka Lesia", "KN-31 · year 3")
    ]
    assert memberships() == sorted([(other, scene.taras), (team, scene.lesia)])
    after = snapshot()
    assert {k: v for k, v in after.items() if k != "team_memberships"} == {
        k: v for k, v in before.items() if k != "team_memberships"
    }
    assert taras_browser.get("/profile").status_code == 200
    with Session(app.state.engine) as session:
        assert get_roles(session, scene.taras) == (Role.STUDENT,)


def test_delete_asks_then_hides_the_team_and_keeps_everything(scene: Scene) -> None:
    """US2-5, US2-6, US2-7, US2-9, FR-007, FR-009, FR-037."""
    team = make_team(app.state.engine, scene.kpi, "Comets")
    make_member(app.state.engine, team, scene.lesia)
    page = scene.olena.get(f"{TAB}/{team}/delete").text
    assert html.h1(page) == "Delete team “Comets”?"
    assert html.details(page) == [
        ("Educational institution", "Kyiv Polytechnic Institute (Kyiv)"),
        ("Members", "1"),
    ]
    assert "The team will be hidden and can no longer join new competitions." in page
    assert (scene.tab(team), "Back to “Comets”") in html.link_pairs(page, "main")
    before, row = snapshot(), team_row(team)
    response = scene.olena.post(f"{TAB}/{team}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == scene.tab()
    after_row = team_row(team)
    assert after_row.deleted_at is not None
    for column in ("name", "name_key", "institution_id", "created_at", "updated_at"):
        assert getattr(after_row, column) == getattr(row, column), column
    after = snapshot()
    assert {k: v for k, v in after.items() if k != "teams"} == {
        k: v for k, v in before.items() if k != "teams"
    }
    body = scene.olena.get(scene.tab()).text
    assert "Comets" not in [o.text for o in html.options(body, "team")]
    assert empty_state(body) == ("No teams yet", "Create the first team with + Add team.")


def test_a_deleted_team_is_denied_everywhere(scene: Scene) -> None:
    """US2-8, FR-008."""
    team = make_team(app.state.engine, scene.kpi, "Comets")
    make_member(app.state.engine, team, scene.taras)
    scene.olena.post(f"{TAB}/{team}/delete")
    before = snapshot()
    for url in (
        scene.tab(team),
        f"{TAB}/{team}/rename",
        f"{TAB}/{team}/delete",
        f"{TAB}/{team}/add",
        f"{TAB}/{team}/members/{scene.taras}/remove",
    ):
        response = scene.olena.get(url)
        assert response.status_code == 403, url
        assert DENIED in response.text
    for url, data in (
        (f"{TAB}/{team}/rename", {"name": "Back"}),
        (f"{TAB}/{team}/delete", {}),
        (f"{TAB}/{team}/members", {"student": str(scene.lesia)}),
        (f"{TAB}/{team}/members/{scene.taras}/remove", {}),
    ):
        assert scene.olena.post(url, data=data).status_code == 403, url
    assert snapshot() == before


def test_cancel_and_back_links_return_to_the_tab(scene: Scene) -> None:
    """US2-11, FR-031, SC-003."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    before = snapshot()
    for page in (
        f"{TAB}/{team}/rename",
        f"{TAB}/{team}/delete",
        f"{TAB}/{team}/members/{scene.taras}/remove",
    ):
        links = html.link_pairs(scene.olena.get(page).text, "main")
        assert (scene.tab(team), "Back to “Rockets”") in links, page
        assert (scene.tab(team), "Cancel") in links, page
    add_page = html.link_pairs(scene.olena.get(f"{TAB}/{team}/add").text, "main")
    assert (scene.tab(team), "Back to “Rockets”") in add_page
    new = html.link_pairs(scene.olena.get(f"{TAB}/institutions/{scene.kpi}/new").text, "main")
    assert (scene.tab(), "Back to Teams") in new and (scene.tab(), "Cancel") in new
    assert snapshot() == before


def test_reloading_after_rename_remove_and_delete_repeats_nothing(scene: Scene) -> None:
    """SC-010."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    results = [
        scene.olena.post(f"{TAB}/{team}/rename", data={"name": "Comets"}, follow_redirects=False),
        scene.olena.post(f"{TAB}/{team}/members/{scene.taras}/remove", follow_redirects=False),
        scene.olena.post(f"{TAB}/{team}/delete", follow_redirects=False),
    ]
    before = snapshot()
    for result in results:
        assert result.status_code == 303
        location = result.headers["location"]
        status = scene.olena.get(location).status_code
        assert status in (200, 403), location
    assert snapshot() == before


# ---------------------------------------------------------------------------------------------
# US3: names
# ---------------------------------------------------------------------------------------------


def test_a_name_used_in_another_institution_is_refused(scene: Scene) -> None:
    """US3-1, FR-002, FR-033: the message names no institution, and the value is kept."""
    make_team(app.state.engine, scene.kpi, "Comets")
    response = create(scene, "comets", scene.academy)
    assert response.status_code == 400
    message = "A team named “comets” already exists."
    assert html.field_error(response.text, "name") == message
    summary = html.error_summary(response.text)
    assert summary is not None and summary.items == [("#name", message)]
    assert html.control(response.text, "name")["value"] == "comets"
    assert html.h1(response.text) == "New team in “Lviv Academy”"
    assert "Kyiv" not in (html.field_error(response.text, "name") or "")
    assert len(teams()) == 1


def test_a_rename_to_a_name_in_use_is_refused(scene: Scene) -> None:
    make_team(app.state.engine, scene.academy, "Comets")
    team = make_team(app.state.engine, scene.kpi)
    response = scene.olena.post(f"{TAB}/{team}/rename", data={"name": "COMETS"})
    assert response.status_code == 400
    assert html.field_error(response.text, "name") == "A team named “COMETS” already exists."
    assert html.control(response.text, "name")["value"] == "COMETS"
    assert html.h1(response.text) == "Rename team “Rockets”"
    assert team_row(team).name == "Rockets"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("", "Enter a name."),
        ("   ", "Enter a name."),
        (" " + "x" * 201 + " ", "The name can be at most 200 characters."),
        ("Rock\tets", "The name cannot contain tabs, line breaks or other control characters."),
    ],
)
def test_an_invalid_name_shows_the_form_again(scene: Scene, raw: str, message: str) -> None:
    """US3-3, FR-033: on create and on rename."""
    team = make_team(app.state.engine, scene.kpi)
    for response in (
        create(scene, raw),
        scene.olena.post(f"{TAB}/{team}/rename", data={"name": raw}),
    ):
        assert response.status_code == 400
        assert html.field_error(response.text, "name") == message
        summary = html.error_summary(response.text)
        assert summary is not None and summary.items == [("#name", message)]
        assert html.control(response.text, "name")["value"] == raw
    assert teams() == [(scene.kpi, "Rockets", False)]


def test_a_deleted_teams_name_can_be_used_again(scene: Scene) -> None:
    """US3-2, US3-5."""
    kyiv = make_team(app.state.engine, scene.kpi, "Comets")
    assert create(scene, "comets", scene.academy).status_code == 400
    scene.olena.post(f"{TAB}/{kyiv}/delete")
    lviv = created_id(create(scene, "comets", scene.academy))
    renamed = scene.olena.post(
        f"{TAB}/{lviv}/rename", data={"name": "Comets"}, follow_redirects=False
    )
    assert renamed.status_code == 303
    assert team_row(lviv).name == "Comets"


# ---------------------------------------------------------------------------------------------
# US4: access
# ---------------------------------------------------------------------------------------------


def endpoints(scene: Scene, team: int, member: int) -> list[tuple[str, str, dict[str, str]]]:
    """All 11 endpoints, with real ids and a valid form."""
    return [
        ("GET", scene.tab(team), {}),
        ("GET", f"{TAB}/institutions/{scene.kpi}/new", {}),
        ("POST", f"{TAB}/institutions/{scene.kpi}/new", {"name": "Hacked"}),
        ("GET", f"{TAB}/{team}/rename", {}),
        ("POST", f"{TAB}/{team}/rename", {"name": "Hacked"}),
        ("GET", f"{TAB}/{team}/delete", {}),
        ("POST", f"{TAB}/{team}/delete", {}),
        ("GET", f"{TAB}/{team}/add?class={scene.kn31}", {}),
        ("POST", f"{TAB}/{team}/members", {"student": str(scene.lesia), "class": str(scene.kn31)}),
        ("GET", f"{TAB}/{team}/members/{member}/remove", {}),
        ("POST", f"{TAB}/{team}/members/{member}/remove", {}),
    ]


def send(browser: TestClient, method: str, url: str, data: dict[str, str]):  # type: ignore[no-untyped-def]
    if method == "GET":
        return browser.get(url, follow_redirects=False)
    return browser.post(url, data=data, follow_redirects=False)


@pytest.mark.parametrize(
    ("email", "role"),
    [(ADMIN_EMAIL, Role.ADMIN), (STUDENT_EMAIL, Role.STUDENT), (ADMIN_STUDENT_EMAIL, Role.STUDENT)],
)
def test_other_roles_are_denied_every_endpoint(
    scene: Scene, client_as: ClientAs, email: str, role: Role
) -> None:
    """US4-1, FR-019: naming the current role; nothing changes."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    browser = client_as(email, role)
    before = snapshot()
    for method, url, data in endpoints(scene, team, scene.taras):
        response = send(browser, method, url, data)
        assert response.status_code == 403, (method, url)
        assert f"Your current role, {role.label}, cannot open this page." in response.text
    assert snapshot() == before


def test_read_access_is_denied_every_management_endpoint(scene: Scene) -> None:
    """US4-2, US4-3, FR-021: routes 2–11 and `team=new`; the tab itself opens."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    before = snapshot()
    tab, *manage = endpoints(scene, team, scene.taras)
    assert send(scene.mykola, *tab).status_code == 200
    for method, url, data in manage:
        assert send(scene.mykola, method, url, data).status_code == 403, (method, url)
    assert scene.mykola.get(f"{scene.tab()}&team=new").status_code == 403
    assert snapshot() == before


@pytest.mark.parametrize(
    "case", ["unknown", "deleted", "unlinked", "institution-deactivated", "region-deactivated"]
)
def test_a_team_out_of_reach_is_denied_in_addresses_and_forms(scene: Scene, case: str) -> None:
    """US4-4, FR-022."""
    institution = {
        "unknown": scene.kpi,
        "deleted": scene.kpi,
        "unlinked": make_institution(app.state.engine, "Kharkiv Lyceum", "Kharkiv"),
        "institution-deactivated": scene.academy,
        "region-deactivated": scene.academy,
    }[case]
    team = (
        999999
        if case == "unknown"
        else make_team(app.state.engine, institution, deleted=case == "deleted")
    )
    tab = f"{TAB}?region={region_of(institution)}&institution={institution}&team={team}"
    with Session(app.state.engine) as session:
        if case == "institution-deactivated":
            set_institution_active(session, scene.lviv, scene.academy, False)
        if case == "region-deactivated":
            set_region_active(session, scene.lviv, False)
    before = snapshot()
    assert scene.olena.get(tab).status_code == 403
    for method, url, data in endpoints(scene, team, scene.taras)[3:]:
        assert send(scene.olena, method, url, data).status_code == 403, (method, url)
    assert snapshot() == before


@pytest.mark.parametrize(
    "who",
    ["other-institution", "read-institution", "blocked", "unknown", "teacher", "abc", "missing"],
)
def test_a_crafted_student_is_denied(scene: Scene, who: str) -> None:
    """US4-5, FR-011, FR-022: and nothing changes."""
    team = make_team(app.state.engine, scene.kpi)
    if who == "other-institution":
        academy_class = make_class(app.state.engine, scene.academy, "LA-1", 1)
        value = str(student("ivan@example.org", academy_class, "Ivan", "Franko"))
    elif who == "read-institution":
        college_class = make_class(app.state.engine, scene.college, "OC-1", 1)
        value = str(student("oksana@example.org", college_class, "Oksana", "Moroz", by=IRYNA))
    elif who == "blocked":
        set_class(scene.kn21, False)
        value = str(scene.taras)
    else:
        value = {"unknown": "999999", "teacher": str(scene.olena_id), "abc": "abc", "missing": ""}[
            who
        ]
    before = snapshot()
    response = scene.olena.post(f"{TAB}/{team}/members", data={"student": value})
    assert response.status_code == 403
    assert "application/json" not in response.headers["content-type"]
    assert snapshot() == before


def test_a_blocked_member_cannot_be_removed(scene: Scene) -> None:
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    set_class(scene.kn21, False)
    before = snapshot()
    assert scene.olena.get(f"{TAB}/{team}/members/{scene.taras}/remove").status_code == 403
    assert scene.olena.post(f"{TAB}/{team}/members/{scene.taras}/remove").status_code == 403
    assert scene.olena.get(f"{TAB}/{team}/members/{scene.lesia}/remove").status_code == 403
    assert snapshot() == before


def lower(scene: Scene, change: str, team: int) -> None:
    if change == "deleted":
        scene.olena.post(f"{TAB}/{team}/delete")
        return
    links = (
        {scene.kpi: AccessLevel.READ}
        if change == "lowered-to-read"
        else {scene.academy: AccessLevel.WRITE}
    )
    with Session(app.state.engine) as session:
        update_teacher(session, scene.olena_id, "Olena", "Kovalenko", links, False)


@pytest.mark.parametrize("change", ["lowered-to-read", "unlinked", "deleted"])
def test_a_page_submitted_after_the_access_changed_is_denied(scene: Scene, change: str) -> None:
    """US4-6, FR-023: create, rename, delete, add and remove."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    pages = [url for method, url, _ in endpoints(scene, team, scene.taras) if method == "GET"]
    for url in pages[1:]:
        assert scene.olena.get(url).status_code == 200, url
    lower(scene, change, team)
    before = snapshot()
    for method, url, data in endpoints(scene, team, scene.taras):
        if method != "POST":
            continue
        if change == "deleted" and url.endswith("/new"):
            continue
        assert send(scene.olena, method, url, data).status_code == 403, (method, url)
    assert snapshot() == before


def test_a_broken_chain_in_the_address_is_denied(scene: Scene) -> None:
    """US4-7, FR-022."""
    team = make_team(app.state.engine, scene.kpi)
    academy_team = make_team(app.state.engine, scene.academy, "Comets")
    for url in (
        f"{TAB}?region={scene.lviv}&institution={scene.kpi}",
        f"{TAB}?institution={scene.kpi}",
        f"{TAB}?region={scene.kyiv}&team={team}",
        f"{scene.tab()}&team={academy_team}",
        f"{scene.tab()}&team=999999",
        f"{scene.tab()}&team=abc",
        f"{TAB}?region=abc",
        f"{TAB}?region={'9' * 40}",
    ):
        response = scene.olena.get(url)
        assert response.status_code == 403, url
        assert DENIED in response.text


def test_add_students_of_a_read_institution_is_denied(scene: Scene) -> None:
    """US4-8: Olena has Write to Kyiv and Read to Odesa."""
    team = make_team(app.state.engine, scene.college, "Dolphins")
    assert scene.olena.get(scene.tab(team, institution=scene.college)).status_code == 200
    assert scene.olena.get(f"{TAB}/{team}/add").status_code == 403


def test_a_class_of_another_institution_or_deactivated_is_denied_on_add_students(
    scene: Scene,
) -> None:
    """Spec Edge Cases."""
    team = make_team(app.state.engine, scene.kpi)
    academy_class = make_class(app.state.engine, scene.academy, "LA-1", 1)
    hidden = make_class(app.state.engine, scene.kpi, "KN-11", 1, active=False)
    for value in (academy_class, hidden, 999999, "abc"):
        assert scene.olena.get(f"{TAB}/{team}/add?class={value}").status_code == 403, value


def test_no_route_answers_with_fastapis_json_errors(scene: Scene) -> None:
    team = make_team(app.state.engine, scene.kpi)
    for url in (f"{TAB}?region=&institution=&team=", f"{TAB}?team=new", f"{TAB}/{team}/add?class="):
        response = scene.olena.get(url)
        assert response.status_code in (200, 403), url
        assert "application/json" not in response.headers["content-type"]
    for url in (f"{TAB}/{team}/rename", f"{TAB}/institutions/{scene.kpi}/new"):
        response = scene.olena.post(url, data={})
        assert response.status_code == 400, url
        assert "application/json" not in response.headers["content-type"]
    response = scene.olena.post(f"{TAB}/{team}/members", data={})
    assert response.status_code == 403
    assert "application/json" not in response.headers["content-type"]


def test_no_log_line_names_anyone(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """FR-016: create, rename, add, the "already" path, remove and delete."""
    with caplog.at_level(logging.DEBUG):
        team = created_id(create(scene, "Rockets"))
        scene.olena.post(f"{TAB}/{team}/rename", data={"name": "Comets"})
        for location in (
            add(scene, team, scene.taras, scene.kn21).headers["location"],
            add(scene, team, scene.taras, scene.kn21).headers["location"],
        ):
            scene.olena.get(location)
        scene.olena.post(f"{TAB}/{team}/members/{scene.taras}/remove")
        scene.olena.post(f"{TAB}/{team}/delete")
    text = caplog.text
    for secret in (TARAS, OLENA, "Taras", "Shevchenko", "Olena", "Kovalenko", "Rockets", "Comets"):
        assert secret not in text, secret
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Team ")]
    assert lines == [
        f"Team created: id={team} institution_id={scene.kpi}",
        f"Team renamed: id={team}",
        f"Team member added: team_id={team} user_id={scene.taras}",
        f"Team member removed: team_id={team} user_id={scene.taras}",
        f"Team deleted: id={team} members=0",
    ]


# ---------------------------------------------------------------------------------------------
# US5: membership rules
# ---------------------------------------------------------------------------------------------


def fill(team: int, count: int, blocked_class: int) -> None:
    """`count` members: two students of `blocked_class`, which the caller deactivates, and people
    with no enrolment, inserted directly."""
    engine = app.state.engine
    emails = [f"filler{n}@example.org" for n in range(count - 2)]
    seed_roles_directly(engine, {email: [Role.STUDENT] for email in emails})
    with Session(engine) as session:
        ids = [u.id for u in session.exec(select(User).where(col(User.email).in_(emails)))]
    ids += [
        student(f"blocked{n}@example.org", blocked_class, "B", f"Blocked {n}") for n in range(2)
    ]
    for user_id in ids:
        assert user_id is not None
        make_member(engine, team, user_id)


def test_a_full_team_offers_no_add(scene: Scene) -> None:
    """US5-1, FR-041: blocked members count."""
    team = make_team(app.state.engine, scene.kpi)
    blocked = make_class(app.state.engine, scene.kpi, "KN-99", 1)
    fill(team, MAX_MEMBERS - 1, blocked)
    make_member(app.state.engine, team, scene.taras)
    set_class(blocked, False)
    student("andriy@example.org", scene.kn21, "Andriy", "Antonenko")
    body = scene.olena.get(f"{TAB}/{team}/add?class={scene.kn21}").text
    assert notice_boxes(body) == [("info", "This team already has 50 members")]
    assert [f for f in html.forms(body, "main") if f.method == "post"] == []
    notes = [e.text() for e in html.parse(body).iter() if "row-note" in e.classes()]
    assert notes == ["In this team"]


@pytest.mark.parametrize("carried", ["active", "missing", "deactivated", "abc"])
def test_a_51st_addition_returns_to_add_students(scene: Scene, carried: str) -> None:
    """US5-2, FR-042: with the same class while it is still an active class."""
    team = make_team(app.state.engine, scene.kpi)
    fill(team, MAX_MEMBERS, scene.kn31)
    hidden = make_class(app.state.engine, scene.kpi, "KN-11", 1, active=False)
    class_value = {"active": scene.kn21, "missing": None, "deactivated": hidden, "abc": "abc"}[
        carried
    ]
    before = snapshot()
    response = add(scene, team, scene.taras, class_value)
    assert response.status_code == 303
    expected = f"{TAB}/{team}/add" + (f"?class={scene.kn21}" if carried == "active" else "")
    assert response.headers["location"] == expected
    assert snapshot() == before
    body = scene.olena.get(response.headers["location"]).text
    assert ("info", "This team already has 50 members") in notice_boxes(body)


def test_a_repeated_addition_says_already(scene: Scene) -> None:
    """US5-3, FR-042: as from two open pages."""
    team = make_team(app.state.engine, scene.kpi)
    first, second = (
        add(scene, team, scene.taras, scene.kn21),
        add(scene, team, scene.taras, scene.kn21),
    )
    assert second.status_code == 303
    assert second.headers["location"].startswith(f"{scene.tab(team)}&notice=")
    body = scene.olena.get(second.headers["location"]).text
    assert notice_boxes(body) == [("info", "Taras Shevchenko is already in this team.")]
    assert memberships() == [(team, scene.taras)]
    assert first.headers["location"] != second.headers["location"]


def test_one_student_in_two_teams(scene: Scene) -> None:
    """US5-5, US1-14."""
    rockets = make_team(app.state.engine, scene.kpi)
    comets = make_team(app.state.engine, scene.kpi, "Comets")
    for team in (rockets, comets):
        assert add(scene, team, scene.taras).status_code == 303
    assert memberships() == sorted([(rockets, scene.taras), (comets, scene.taras)])


# ---------------------------------------------------------------------------------------------
# US6: deactivation hides members
# ---------------------------------------------------------------------------------------------


def test_a_deactivated_class_hides_its_members_until_activated(scene: Scene) -> None:
    """US6-1, US6-2, US6-3, US6-4, US6-5, FR-010."""
    team = make_team(app.state.engine, scene.kpi, "Comets")
    make_member(app.state.engine, team, scene.taras)
    make_member(app.state.engine, team, scene.lesia)
    stored = memberships(team)
    notice = seal_member_notice(app.state.settings, team, scene.taras, "added")
    scene.olena.post(f"/teacher/students/classes/{scene.kn21}/deactivate")

    body = scene.olena.get(f"{scene.tab(team)}&notice={notice}").text
    assert members_shown(body) == [("Ukrainka Lesia", "KN-31 · year 3")]
    assert notice_boxes(body) == []
    assert "Taras" not in body
    assert ("Members", "1") in html.details(scene.olena.get(f"{TAB}/{team}/delete").text)
    with Session(app.state.engine) as session:
        assert count_members(session, team) == 2
    add_page = scene.olena.get(f"{TAB}/{team}/add").text
    assert "KN-21 · year 2" not in [o.text for o in html.options(add_page, "class")]
    assert scene.olena.get(f"{TAB}/{team}/add?class={scene.kn21}").status_code == 403

    scene.olena.post(f"/teacher/students/classes/{scene.kn21}/activate")
    body = scene.olena.get(scene.tab(team)).text
    assert [name for name, _ in members_shown(body)] == ["Shevchenko Taras", "Ukrainka Lesia"]
    assert memberships(team) == stored


def test_a_team_of_blocked_members_only_looks_empty(scene: Scene) -> None:
    """Spec Edge Cases."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    set_class(scene.kn21, False)
    assert empty_state(scene.olena.get(scene.tab(team)).text)[0] == "No members in this team yet"
    assert ("Members", "0") in html.details(scene.olena.get(f"{TAB}/{team}/delete").text)


def test_enrolments_and_roles_are_untouched_by_team_actions(scene: Scene) -> None:
    """FR-005, FR-006, FR-009 together: a full cycle leaves every student row as it was."""
    with Session(app.state.engine) as session:
        enrolments = sorted((e.user_id, e.class_id) for e in session.exec(select(Enrolment)))
        roles = session.exec(select(func.count()).select_from(UserRole)).one()
    team = created_id(create(scene, "Rockets"))
    add(scene, team, scene.taras)
    add(scene, team, scene.lesia)
    scene.olena.post(f"{TAB}/{team}/members/{scene.taras}/remove")
    scene.olena.post(f"{TAB}/{team}/delete")
    with Session(app.state.engine) as session:
        assert (
            sorted((e.user_id, e.class_id) for e in session.exec(select(Enrolment))) == enrolments
        )
        assert session.exec(select(func.count()).select_from(UserRole)).one() == roles
    assert memberships() == [(team, scene.lesia)]


# ---------------------------------------------------------------------------------------------
# US8: classes of an institution with teams
# ---------------------------------------------------------------------------------------------


def test_deleting_a_class_is_unaffected_by_teams(scene: Scene) -> None:
    """US8-3, FR-018: a class with students is still refused, an empty one still deleted."""
    team = make_team(app.state.engine, scene.kpi)
    make_member(app.state.engine, team, scene.taras)
    make_team(app.state.engine, scene.kpi, "Comets", deleted=True)
    empty = make_class(app.state.engine, scene.kpi, "KN-41", 4)
    refused = scene.olena.post(f"/teacher/students/classes/{scene.kn21}/delete")
    assert refused.status_code == 409
    deleted = scene.olena.post(f"/teacher/students/classes/{empty}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    with Session(app.state.engine) as session:
        assert session.get(SchoolClass, empty) is None
        assert session.get(SchoolClass, scene.kn21) is not None
    assert memberships() == [(team, scene.taras)]
