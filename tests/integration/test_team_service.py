"""Teams and memberships: the reach of a team, the lookups, and every change, each checked against
the teacher's reach and the team and membership rules.

See specs/011.1-teacher-teams/contracts/services.md, research R2–R7 and R17. The teacher is real:
Write to "Kyiv Polytechnic Institute" and "Kyiv Lyceum", Read to "Lviv Academy", no link to
"Odesa College". Students, their enrolments, teams and memberships are seeded directly, so the
service is never checked through itself. Every case runs on both engines; the concurrent addition
runs on PostgreSQL only.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import Engine, MetaData, func
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

import app.services.teams as teams_service
from app.core.config import AuthSettings
from app.core.db import utc_now
from app.models import (
    AccessLevel,
    Enrolment,
    Institution,
    Role,
    SchoolClass,
    Team,
    TeamMembership,
    User,
    UserSession,
)
from app.schemas.names import InvalidName
from app.services.institutions import set_institution_active
from app.services.regions import set_region_active
from app.services.sessions import create_session
from app.services.students import update_student
from app.services.teacher_access import NotReachable, WriteRequired, reach_team
from app.services.teams import (
    MAX_MEMBERS,
    AlreadyMember,
    DuplicateTeamName,
    MemberRow,
    StudentTeam,
    TeamFull,
    add_member,
    count_members,
    create_team,
    delete_team,
    get_member,
    is_full,
    list_active_members,
    list_student_teams,
    list_teams,
    member_ids,
    remove_member,
    rename_team,
)
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    make_class,
    make_institution,
    make_member,
    make_teacher,
    make_team,
    seed_roles_directly,
)

REACH_ERRORS = (NotReachable, WriteRequired)


@dataclass(frozen=True)
class Scene:
    teacher: int
    reader: int
    """Read to "Kyiv Polytechnic Institute"."""
    a: int
    a2: int
    b: int
    c: int
    kn21: int
    kn31: int
    lyceum: int
    lviv: int
    odesa: int


@pytest.fixture
def scene(engine: Engine, auth_settings: AuthSettings) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    a = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    a2 = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    b = make_institution(engine, "Lviv Academy", "Lviv")
    c = make_institution(engine, "Odesa College", "Odesa")
    teacher = make_teacher(
        engine,
        auth_settings,
        email="olena@example.org",
        institutions={a: AccessLevel.WRITE, a2: AccessLevel.WRITE, b: AccessLevel.READ},
    )
    reader = make_teacher(
        engine,
        auth_settings,
        email="mykola@example.org",
        institutions={a: AccessLevel.READ},
        first="Mykola",
        last="Read",
    )
    return Scene(
        teacher=teacher,
        reader=reader,
        a=a,
        a2=a2,
        b=b,
        c=c,
        kn21=make_class(engine, a, "KN-21", 2),
        kn31=make_class(engine, a, "KN-31", 3),
        lyceum=make_class(engine, a2, "LY-1", 1),
        lviv=make_class(engine, b, "LA-1", 1),
        odesa=make_class(engine, c, "OC-1", 1),
    )


def enrolled(
    engine: Engine, email: str, class_id: int, first: str = "Taras", last: str = "Shevchenko"
) -> int:
    """A student of the class, seeded directly (role, names and enrolment), signed in once."""
    seed_roles_directly(engine, {email: [Role.STUDENT]})
    now = utc_now()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.id is not None
        user.first_name, user.last_name = first, last
        session.add(user)
        session.add(Enrolment(user_id=user.id, class_id=class_id, created_at=now, updated_at=now))
        session.commit()
        create_session(session, user, Role.STUDENT)
        return user.id


def set_class(engine: Engine, class_id: int, active: bool) -> None:
    with Session(engine) as session:
        school_class = session.get(SchoolClass, class_id)
        assert school_class is not None
        school_class.is_active = active
        session.add(school_class)
        session.commit()


def region_of(engine: Engine, institution_id: int) -> int:
    with Session(engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


def stored_team(engine: Engine, team_id: int) -> Team:
    with Session(engine) as session:
        team = session.get(Team, team_id)
        assert team is not None
        return team


def memberships(engine: Engine, team_id: int | None = None) -> list[tuple[int, int]]:
    with Session(engine) as session:
        statement = select(TeamMembership)
        if team_id is not None:
            statement = statement.where(TeamMembership.team_id == team_id)
        return sorted((m.team_id, m.user_id) for m in session.exec(statement))


def team_count(engine: Engine) -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(Team)).one()


SNAPSHOT_TABLES = ("teams", "team_memberships", "enrolments", "user_roles", "sessions", "users")


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(sa_select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


# ---------------------------------------------------------------------------------------------
# reach_team (research R4)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("lock", [False, True])
def test_a_live_team_is_reached_with_write_and_read(
    engine: Engine, scene: Scene, lock: bool
) -> None:
    team = make_team(engine, scene.a)
    with Session(engine) as session:
        institution, row = reach_team(session, scene.teacher, team, write=True, lock=lock)
        assert (institution.id, institution.can_write, row.id) == (scene.a, True, team)
        institution, row = reach_team(session, scene.reader, team, institution_id=scene.a)
        assert (institution.id, institution.can_write, row.name) == (scene.a, False, "Rockets")


@pytest.mark.parametrize("lock", [False, True])
@pytest.mark.parametrize(
    "case",
    ["unknown", "deleted", "unlinked", "institution-deactivated", "region-deactivated", "mismatch"],
)
def test_a_team_out_of_reach_is_not_reachable(
    engine: Engine, scene: Scene, case: str, lock: bool
) -> None:
    institution = scene.c if case == "unlinked" else scene.a
    team = make_team(engine, institution, deleted=case == "deleted")
    with Session(engine) as session:
        if case == "institution-deactivated":
            set_institution_active(session, region_of(engine, scene.a), scene.a, False)
        if case == "region-deactivated":
            set_region_active(session, region_of(engine, scene.a), False)
    with Session(engine) as session, pytest.raises(NotReachable):
        reach_team(
            session,
            scene.teacher,
            999999 if case == "unknown" else team,
            institution_id=scene.a2 if case == "mismatch" else None,
            lock=lock,
        )


def test_read_access_is_not_enough_to_change_a_team(engine: Engine, scene: Scene) -> None:
    team = make_team(engine, scene.b)
    with Session(engine) as session:
        reach_team(session, scene.teacher, team)
        with pytest.raises(WriteRequired):
            reach_team(session, scene.teacher, team, write=True, lock=True)


# ---------------------------------------------------------------------------------------------
# Lookups (research R6, R14)
# ---------------------------------------------------------------------------------------------


def test_the_live_teams_are_listed_ignoring_case(engine: Engine, scene: Scene) -> None:
    for name in ("gamma", "Beta", "alpha"):
        make_team(engine, scene.a, name)
    make_team(engine, scene.a, "Aardvark", deleted=True)
    make_team(engine, scene.a2, "Another institution")
    with Session(engine) as session:
        assert [t.name for t in list_teams(session, scene.a)] == ["alpha", "Beta", "gamma"]


def test_the_active_members_are_listed_by_last_then_first_name(
    engine: Engine, scene: Scene
) -> None:
    team = make_team(engine, scene.a)
    ids = [
        enrolled(engine, "b@example.org", scene.kn21, "bohdan", "Kovalenko"),
        enrolled(engine, "a@example.org", scene.kn31, "Andriy", "kovalenko"),
        enrolled(engine, "c@example.org", scene.kn21, "Iryna", "Antonenko"),
        enrolled(engine, "d@example.org", scene.kn31, "Andriy", "Kovalenko"),
    ]
    for user_id in ids:
        make_member(engine, team, user_id)
    with Session(engine) as session:
        assert list_active_members(session, team) == [
            MemberRow(ids[2], "Iryna", "Antonenko", "KN-21 · year 2"),
            MemberRow(ids[1], "Andriy", "kovalenko", "KN-31 · year 3"),
            MemberRow(ids[3], "Andriy", "Kovalenko", "KN-31 · year 3"),
            MemberRow(ids[0], "bohdan", "Kovalenko", "KN-21 · year 2"),
        ]


def test_the_counts_include_a_blocked_member_whom_the_list_hides(
    engine: Engine, scene: Scene
) -> None:
    """FR-004, FR-010, US6-3."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    lesia = enrolled(engine, "lesia@example.org", scene.kn31, "Lesia", "Ukrainka")
    make_member(engine, team, taras)
    make_member(engine, team, lesia)
    set_class(engine, scene.kn21, False)
    with Session(engine) as session:
        assert [m.user_id for m in list_active_members(session, team)] == [lesia]
        assert count_members(session, team) == 2
        assert member_ids(session, team) == {taras, lesia}
        assert not is_full(session, team)


def test_a_students_teams_include_deleted_ones(engine: Engine, scene: Scene) -> None:
    """FR-013, US7-1."""
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    for name, deleted in (("Rockets", False), ("comets", True), ("Alpha", False), ("Other", False)):
        team = make_team(engine, scene.a, name, deleted=deleted)
        if name != "Other":
            make_member(engine, team, taras)
    with Session(engine) as session:
        assert list_student_teams(session, taras) == [
            StudentTeam("Alpha", False),
            StudentTeam("comets", True),
            StudentTeam("Rockets", False),
        ]
        assert list_student_teams(session, scene.teacher) == []


# ---------------------------------------------------------------------------------------------
# Create (US1, US3)
# ---------------------------------------------------------------------------------------------


def test_a_team_is_created_trimmed_and_logged_by_id(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        view = create_team(session, scene.teacher, scene.a, "  Rockets  ")
    assert (view.institution_id, view.name) == (scene.a, "Rockets")
    team = stored_team(engine, view.id)
    assert (team.name, team.name_key, team.deleted_at) == ("Rockets", "rockets", None)
    assert team.created_at == team.updated_at
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Team")]
    assert lines == [f"Team created: id={view.id} institution_id={scene.a}"]
    assert "Rockets" not in caplog.text


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("", "Enter a name."),
        ("   ", "Enter a name."),
        (" " + "x" * 201 + " ", "The name can be at most 200 characters."),
        ("Rock\tets", "The name cannot contain tabs, line breaks or other control characters."),
    ],
)
def test_an_invalid_name_stores_nothing(
    engine: Engine, scene: Scene, raw: str, message: str
) -> None:
    """US3-3."""
    with Session(engine) as session, pytest.raises(InvalidName) as caught:
        create_team(session, scene.teacher, scene.a, raw)
    assert caught.value.message == message
    assert team_count(engine) == 0


def test_200_characters_after_trimming_are_accepted(engine: Engine, scene: Scene) -> None:
    with Session(engine) as session:
        view = create_team(session, scene.teacher, scene.a, "  " + "x" * 200 + "  ")
    assert view.name == "x" * 200


@pytest.mark.parametrize("institution", ["read", "unlinked", "unknown"])
def test_creating_needs_write_to_a_reachable_institution(
    engine: Engine, scene: Scene, institution: str
) -> None:
    target = {"read": scene.b, "unlinked": scene.c, "unknown": 999999}[institution]
    with Session(engine) as session, pytest.raises(REACH_ERRORS):
        create_team(session, scene.teacher, target, "Rockets")
    assert team_count(engine) == 0


@pytest.mark.parametrize("where", ["another-institution", "same-institution"])
def test_a_live_name_is_taken_everywhere_ignoring_case(
    engine: Engine, scene: Scene, where: str
) -> None:
    """US3-1, FR-002: the message repeats the entered name and names no institution."""
    make_team(engine, scene.c if where == "another-institution" else scene.a, "Comets")
    with Session(engine) as session, pytest.raises(DuplicateTeamName) as caught:
        create_team(session, scene.teacher, scene.a, " comets ")
    assert caught.value.message == "A team named “comets” already exists."
    assert "Odesa" not in caught.value.message and "Kyiv" not in caught.value.message
    assert team_count(engine) == 1


def test_a_deleted_teams_name_is_free_again(engine: Engine, scene: Scene) -> None:
    """US3-2: and any number of deleted teams may share the name with one live team."""
    make_team(engine, scene.c, "Comets", deleted=True)
    make_team(engine, scene.a2, "COMETS", deleted=True)
    with Session(engine) as session:
        view = create_team(session, scene.teacher, scene.a, "comets")
    assert view.name == "comets"
    with Session(engine) as session:
        keys = session.exec(select(Team.name_key)).all()
    assert keys == ["comets", "comets", "comets"]


def test_a_name_taken_in_a_race_is_a_duplicate_with_nothing_stored(
    engine: Engine, scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Research R2, SC-005: with the lookup bypassed, the partial unique index refuses the
    second live team."""
    make_team(engine, scene.c, "Comets")
    monkeypatch.setattr(teams_service, "_find_live", lambda session, key: None)
    with Session(engine) as session, pytest.raises(DuplicateTeamName) as caught:
        create_team(session, scene.teacher, scene.a, "comets")
    assert caught.value.message == "A team named “comets” already exists."
    assert team_count(engine) == 1


# ---------------------------------------------------------------------------------------------
# Rename (US2, US3)
# ---------------------------------------------------------------------------------------------


def test_a_rename_changes_the_name_its_key_and_the_time(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    team = make_team(engine, scene.a)
    before = stored_team(engine, team)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        view = rename_team(session, scene.teacher, team, " Comets ")
    after = stored_team(engine, team)
    assert (view.name, after.name, after.name_key) == ("Comets", "Comets", "comets")
    assert after.updated_at > before.updated_at
    assert (after.created_at, after.institution_id) == (before.created_at, before.institution_id)
    assert [r.getMessage() for r in caplog.records] == [f"Team renamed: id={team}"]


def test_an_unchanged_rename_writes_nothing(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    team = make_team(engine, scene.a)
    before = stored_team(engine, team)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        assert rename_team(session, scene.teacher, team, "  Rockets ").name == "Rockets"
    assert stored_team(engine, team).updated_at == before.updated_at
    assert caplog.records == []


def test_a_change_of_case_is_a_rename(engine: Engine, scene: Scene) -> None:
    """US3-5."""
    team = make_team(engine, scene.a, "comets")
    with Session(engine) as session:
        assert rename_team(session, scene.teacher, team, "Comets").name == "Comets"
    assert stored_team(engine, team).name == "Comets"


def test_a_rename_to_another_live_name_is_a_duplicate(engine: Engine, scene: Scene) -> None:
    team = make_team(engine, scene.a)
    make_team(engine, scene.c, "Comets")
    with Session(engine) as session, pytest.raises(DuplicateTeamName) as caught:
        rename_team(session, scene.teacher, team, "COMETS")
    assert caught.value.message == "A team named “COMETS” already exists."
    assert stored_team(engine, team).name == "Rockets"


def test_a_rename_to_a_deleted_teams_name_is_accepted(engine: Engine, scene: Scene) -> None:
    team = make_team(engine, scene.a)
    make_team(engine, scene.a, "Comets", deleted=True)
    with Session(engine) as session:
        assert rename_team(session, scene.teacher, team, "comets").name == "comets"


def test_a_rename_refused_by_the_index_is_a_duplicate(
    engine: Engine, scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = make_team(engine, scene.a)
    make_team(engine, scene.c, "Comets")
    monkeypatch.setattr(teams_service, "_find_live", lambda session, key: None)
    with Session(engine) as session, pytest.raises(DuplicateTeamName):
        rename_team(session, scene.teacher, team, "comets")
    assert stored_team(engine, team).name == "Rockets"


def test_an_invalid_rename_changes_nothing(engine: Engine, scene: Scene) -> None:
    team = make_team(engine, scene.a)
    with Session(engine) as session, pytest.raises(InvalidName):
        rename_team(session, scene.teacher, team, "   ")
    assert stored_team(engine, team).name == "Rockets"


# ---------------------------------------------------------------------------------------------
# Delete (US2)
# ---------------------------------------------------------------------------------------------


def test_a_deletion_sets_only_the_deletion_time(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-007, FR-009, US2-7, US2-9: the row, every membership and the members are unchanged."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    lesia = enrolled(engine, "lesia@example.org", scene.kn21, "Lesia", "Ukrainka")
    make_member(engine, team, taras)
    make_member(engine, team, lesia)
    set_class(engine, scene.kn21, False)
    before = snapshot(engine)
    team_before = stored_team(engine, team)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        view = delete_team(session, scene.teacher, team)
    after = stored_team(engine, team)
    assert view.name == "Rockets"
    assert after.deleted_at is not None
    for column in ("name", "name_key", "institution_id", "created_at", "updated_at"):
        assert getattr(after, column) == getattr(team_before, column), column
    changed = snapshot(engine)
    assert {name: rows for name, rows in changed.items() if name != "teams"} == {
        name: rows for name, rows in before.items() if name != "teams"
    }
    assert [r.getMessage() for r in caplog.records] == [f"Team deleted: id={team} members=2"]


def test_a_deleted_team_cannot_be_changed_again(engine: Engine, scene: Scene) -> None:
    """FR-008, US2-8: delete, rename, add and remove are all out of reach."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    lesia = enrolled(engine, "lesia@example.org", scene.kn21, "Lesia", "Ukrainka")
    make_member(engine, team, taras)
    with Session(engine) as session:
        delete_team(session, scene.teacher, team)
    before = snapshot(engine)
    attempts = (
        lambda session: delete_team(session, scene.teacher, team),
        lambda session: rename_team(session, scene.teacher, team, "Comets"),
        lambda session: add_member(session, scene.teacher, team, str(lesia)),
        lambda session: remove_member(session, scene.teacher, team, taras),
        lambda session: get_member(session, scene.teacher, team, taras),
    )
    for attempt in attempts:
        with Session(engine) as session, pytest.raises(NotReachable):
            attempt(session)
    assert snapshot(engine) == before


def test_deleting_needs_write(engine: Engine, scene: Scene) -> None:
    team = make_team(engine, scene.a)
    with Session(engine) as session, pytest.raises(WriteRequired):
        delete_team(session, scene.reader, team)
    assert stored_team(engine, team).deleted_at is None


# ---------------------------------------------------------------------------------------------
# Add a member (US1, US4, US5)
# ---------------------------------------------------------------------------------------------


def test_adding_stores_one_membership_and_nothing_else(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-005: the class, enrolment, role and sessions are unchanged."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    before = snapshot(engine)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        member = add_member(session, scene.teacher, team, str(taras))
    assert member == MemberRow(taras, "Taras", "Shevchenko", "KN-21 · year 2")
    after = snapshot(engine)
    assert len(after["team_memberships"]) == len(before["team_memberships"]) + 1
    assert {k: v for k, v in after.items() if k != "team_memberships"} == {
        k: v for k, v in before.items() if k != "team_memberships"
    }
    assert memberships(engine) == [(team, taras)]
    assert [r.getMessage() for r in caplog.records] == [
        f"Team member added: team_id={team} user_id={taras}"
    ]
    assert "Taras" not in caplog.text and "taras@" not in caplog.text


def test_a_student_may_be_in_several_teams_of_the_institution(engine: Engine, scene: Scene) -> None:
    """US1-14, US5-5."""
    rockets = make_team(engine, scene.a)
    comets = make_team(engine, scene.a, "Comets")
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    with Session(engine) as session:
        add_member(session, scene.teacher, rockets, str(taras))
        add_member(session, scene.teacher, comets, str(taras))
    assert memberships(engine) == sorted([(rockets, taras), (comets, taras)])


@pytest.mark.parametrize(
    "who",
    [
        "empty",
        "abc",
        "arabic-digit",
        "huge",
        "unknown",
        "teacher",
        "other-institution",
        "unlinked-institution",
        "deactivated-class",
        "not-enrolled",
    ],
)
def test_a_student_out_of_reach_is_not_added(engine: Engine, scene: Scene, who: str) -> None:
    """US4-5, FR-003, FR-011, FR-022: and nothing is stored."""
    team = make_team(engine, scene.a)
    if who == "deactivated-class":
        user = enrolled(engine, "blocked@example.org", scene.kn21)
        set_class(engine, scene.kn21, False)
    elif who == "other-institution":
        user = enrolled(engine, "lyceum@example.org", scene.lyceum)
    elif who == "unlinked-institution":
        user = enrolled(engine, "odesa@example.org", scene.odesa)
    elif who == "not-enrolled":
        seed_roles_directly(engine, {"loose@example.org": [Role.STUDENT]})
        with Session(engine) as session:
            loose = session.exec(select(User).where(User.email == "loose@example.org")).one()
            assert loose.id is not None
            user = loose.id
    else:
        user = scene.teacher
    raw = {
        "empty": "",
        "abc": "abc",
        "arabic-digit": "٢",
        "huge": "9" * 40,
        "unknown": "999999",
    }.get(who, str(user))
    before = snapshot(engine)
    with Session(engine) as session, pytest.raises(REACH_ERRORS):
        add_member(session, scene.teacher, team, raw)
    assert snapshot(engine) == before


@pytest.mark.parametrize("case", ["read-teacher", "deleted-team", "read-institution"])
def test_adding_needs_write_to_a_live_team(engine: Engine, scene: Scene, case: str) -> None:
    institution = scene.b if case == "read-institution" else scene.a
    team = make_team(engine, institution, deleted=case == "deleted-team")
    student = enrolled(
        engine, "s@example.org", scene.lviv if case == "read-institution" else scene.kn21
    )
    teacher = scene.reader if case == "read-teacher" else scene.teacher
    with Session(engine) as session, pytest.raises(REACH_ERRORS):
        add_member(session, teacher, team, str(student))
    assert memberships(engine) == []


def test_a_member_added_again_is_already_a_member(engine: Engine, scene: Scene) -> None:
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    make_member(engine, team, taras)
    with Session(engine) as session, pytest.raises(AlreadyMember) as caught:
        add_member(session, scene.teacher, team, str(taras))
    assert (caught.value.team_id, caught.value.user_id) == (team, taras)
    assert memberships(engine) == [(team, taras)]


def test_a_membership_taken_in_a_race_is_already_a_member(
    engine: Engine, scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-004: with the lookup bypassed, the primary key refuses the second membership."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    make_member(engine, team, taras)
    monkeypatch.setattr(teams_service, "_membership", lambda session, team_id, user_id: None)
    with Session(engine) as session, pytest.raises(AlreadyMember):
        add_member(session, scene.teacher, team, str(taras))
    assert memberships(engine) == [(team, taras)]


def fill(engine: Engine, team: int, count: int, blocked_class: int, prefix: str = "") -> list[int]:
    """`count` members: three students of `blocked_class` (deactivated afterwards by the caller),
    the rest people with no enrolment, inserted directly."""
    emails = [f"{prefix}filler{n}@example.org" for n in range(count - 3)]
    seed_roles_directly(engine, {email: [Role.STUDENT] for email in emails})
    with Session(engine) as session:
        ids = [
            u.id
            for u in session.exec(select(User).where(col(User.email).in_(emails)))
            if u.id is not None
        ]
    ids += [
        enrolled(engine, f"{prefix}blocked{n}@example.org", blocked_class, "B", f"Blocked {n}")
        for n in range(3)
    ]
    for user_id in ids:
        make_member(engine, team, user_id)
    return ids


def test_the_51st_member_is_refused_blocked_members_counted(engine: Engine, scene: Scene) -> None:
    """FR-004, US5-2, US6-3."""
    team = make_team(engine, scene.a)
    fill(engine, team, MAX_MEMBERS, scene.kn31)
    set_class(engine, scene.kn31, False)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    with Session(engine) as session:
        assert is_full(session, team)
        assert len(list_active_members(session, team)) == 0
    with Session(engine) as session, pytest.raises(TeamFull):
        add_member(session, scene.teacher, team, str(taras))
    assert len(memberships(engine, team)) == MAX_MEMBERS


def test_a_member_of_a_full_team_is_already_a_member(engine: Engine, scene: Scene) -> None:
    """Contracts §9: "already" is checked before the limit."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    make_member(engine, team, taras)
    filler = fill(engine, team, MAX_MEMBERS - 1, scene.kn31)
    assert len(filler) == MAX_MEMBERS - 1
    with Session(engine) as session, pytest.raises(AlreadyMember):
        add_member(session, scene.teacher, team, str(taras))
    assert len(memberships(engine, team)) == MAX_MEMBERS


def test_moving_to_another_class_keeps_every_team(engine: Engine, scene: Scene) -> None:
    """US5-4, FR-005."""
    rockets = make_team(engine, scene.a)
    comets = make_team(engine, scene.a, "Comets")
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    make_member(engine, rockets, taras)
    make_member(engine, comets, taras)
    with Session(engine) as session:
        update_student(session, scene.teacher, taras, "Taras", "Shevchenko", str(scene.kn31))
    assert memberships(engine) == sorted([(rockets, taras), (comets, taras)])
    with Session(engine) as session:
        assert list_active_members(session, rockets)[0].class_label == "KN-31 · year 3"


def test_the_50th_and_51st_added_at_once_store_exactly_one(
    engine: Engine, scene: Scene, database_url: str
) -> None:
    """SC-004, research R5: the count is taken under the team row's lock. PostgreSQL only: on
    SQLite the locks render nothing, and writers are serialised anyway."""
    if not database_url.startswith("postgresql"):
        pytest.skip("row locks are a PostgreSQL behaviour")
    for attempt in range(3):
        team = make_team(engine, scene.a, f"Race {attempt}")
        fill(engine, team, MAX_MEMBERS - 1, scene.kn31, prefix=f"race{attempt}-")
        rivals = [
            enrolled(engine, f"rival{attempt}{n}@example.org", scene.kn21, "R", f"Rival {n}")
            for n in range(2)
        ]
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def adding(
            user_id: int,
            team_id: int = team,
            barrier: threading.Barrier = barrier,
            outcomes: list[str] = outcomes,
        ) -> None:
            with Session(engine) as session:
                barrier.wait()
                try:
                    add_member(session, scene.teacher, team_id, str(user_id))
                except TeamFull:
                    outcomes.append("full")
                except BaseException as error:  # noqa: BLE001 — reported below
                    outcomes.append(repr(error))
                else:
                    outcomes.append("added")

        threads = [threading.Thread(target=adding, args=(user_id,)) for user_id in rivals]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert sorted(outcomes) == ["added", "full"]
        assert len(memberships(engine, team)) == MAX_MEMBERS


# ---------------------------------------------------------------------------------------------
# Remove a member (US2, US4)
# ---------------------------------------------------------------------------------------------


def test_removing_deletes_that_membership_only(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-006, US2-4: the role, enrolment, class, other teams and sessions stay."""
    rockets = make_team(engine, scene.a)
    comets = make_team(engine, scene.a, "Comets")
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    lesia = enrolled(engine, "lesia@example.org", scene.kn31, "Lesia", "Ukrainka")
    for team, user_id in ((rockets, taras), (comets, taras), (rockets, lesia)):
        make_member(engine, team, user_id)
    before = snapshot(engine)
    with Session(engine) as session:
        institution, view, member = get_member(session, scene.teacher, rockets, taras)
    assert (institution.id, view.name, member.class_label) == (scene.a, "Rockets", "KN-21 · year 2")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), Session(engine) as session:
        remove_member(session, scene.teacher, rockets, taras)
    assert memberships(engine) == sorted([(comets, taras), (rockets, lesia)])
    after = snapshot(engine)
    assert {k: v for k, v in after.items() if k != "team_memberships"} == {
        k: v for k, v in before.items() if k != "team_memberships"
    }
    with Session(engine) as session:
        sessions = session.exec(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == taras)
        ).one()
    assert sessions == 1
    assert [r.getMessage() for r in caplog.records] == [
        f"Team member removed: team_id={rockets} user_id={taras}"
    ]


@pytest.mark.parametrize("case", ["non-member", "blocked-member", "read-teacher", "unknown"])
def test_a_removal_out_of_reach_changes_nothing(engine: Engine, scene: Scene, case: str) -> None:
    """FR-011, US4-5."""
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    if case != "non-member":
        make_member(engine, team, taras)
    if case == "blocked-member":
        set_class(engine, scene.kn21, False)
    teacher = scene.reader if case == "read-teacher" else scene.teacher
    user_id = 999999 if case == "unknown" else taras
    before = snapshot(engine)
    for attempt in (get_member, remove_member):
        with Session(engine) as session, pytest.raises(REACH_ERRORS):
            attempt(session, teacher, team, user_id)
    assert snapshot(engine) == before


def test_a_member_of_another_institution_is_not_removed(engine: Engine, scene: Scene) -> None:
    """A membership that breaks the institution rule (seeded directly) is still refused."""
    team = make_team(engine, scene.a)
    other = enrolled(engine, "lyceum@example.org", scene.lyceum)
    make_member(engine, team, other)
    with Session(engine) as session, pytest.raises(NotReachable):
        remove_member(session, scene.teacher, team, other)
    assert memberships(engine) == [(team, other)]


# ---------------------------------------------------------------------------------------------
# The deactivation chain (US6, FR-010)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["class", "institution", "region"])
def test_a_blocked_member_is_hidden_and_listed_again_on_activation(
    engine: Engine, scene: Scene, level: str
) -> None:
    team = make_team(engine, scene.a)
    taras = enrolled(engine, "taras@example.org", scene.kn21)
    make_member(engine, team, taras)
    region = region_of(engine, scene.a)
    before = snapshot(engine)["team_memberships"]

    def toggle(active: bool) -> None:
        if level == "class":
            set_class(engine, scene.kn21, active)
            return
        with Session(engine) as session:
            if level == "institution":
                set_institution_active(session, region, scene.a, active)
            else:
                set_region_active(session, region, active)

    toggle(False)
    with Session(engine) as session:
        assert list_active_members(session, team) == []
        assert count_members(session, team) == 1
    assert snapshot(engine)["team_memberships"] == before
    toggle(True)
    with Session(engine) as session:
        assert [m.user_id for m in list_active_members(session, team)] == [taras]
    assert snapshot(engine)["team_memberships"] == before
