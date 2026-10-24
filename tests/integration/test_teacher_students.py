"""User story 4: a teacher edits and removes students.

See specs/009-classes-students-management/spec.md US4, FR-041–FR-043 and contracts/http-routes.md
§2.4. The teacher is real: Write to "Kyiv Polytechnic Institute" (classes "KN-21" and "KN-22", and
a deactivated "KN-11"), Read to "Lviv Academy". Students are real: invited and accepted. Every case
runs on both engines.
"""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.main import app
from app.models import (
    AccessLevel,
    ConsentRecord,
    Enrolment,
    Institution,
    InvitationCutoff,
    Role,
    User,
    UserSession,
)
from app.routers.invitations import NEUTRAL
from app.services.consent import current_consent_text, get_cutoff
from app.services.sessions import create_session, get_session_identity
from app.services.users import get_roles, get_user_by_email
from tests import html
from tests.conftest import (
    ClientAs,
    enrol_student,
    invite_student,
    make_class,
    make_institution,
    make_teacher,
)

OLENA = "olena@example.org"
PETRO = "petro@example.org"


@dataclass(frozen=True)
class Scene:
    teacher: TestClient
    teacher_id: int
    a: int
    b: int
    region: int
    kn21: int
    kn22: int
    kn11: int
    other_class: int

    def selection(self, class_id: int) -> str:
        return f"/teacher/students?region={self.region}&institution={self.a}&class={class_id}"

    def carried(self, class_id: int) -> str:
        return f"?region={self.region}&institution={self.a}&class={class_id}"


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    a = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    b = make_institution(engine, "Lviv Academy", "Lviv")
    teacher_id = make_teacher(
        engine, settings, email=OLENA, institutions={a: AccessLevel.WRITE, b: AccessLevel.READ}
    )
    make_teacher(
        engine, settings, email=PETRO, institutions={b: AccessLevel.WRITE}, first="Petro", last="B"
    )
    with Session(engine) as session:
        institution = session.get(Institution, a)
        assert institution is not None
        region = institution.region_id
    return Scene(
        teacher=client_as(OLENA),
        teacher_id=teacher_id,
        a=a,
        b=b,
        region=region,
        kn21=make_class(engine, a, "KN-21", 2),
        kn22=make_class(engine, a, "KN-22", 2),
        kn11=make_class(engine, a, "KN-11", 1, active=False),
        other_class=make_class(engine, b, "LA-1", 1),
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


def person(user_id: int) -> User:
    with Session(app.state.engine) as session:
        found = session.get(User, user_id)
        assert found is not None
        return found


def class_of(user_id: int) -> int | None:
    with Session(app.state.engine) as session:
        enrolment = session.get(Enrolment, user_id)
        return enrolment.class_id if enrolment else None


def count(model: type, **where: object) -> int:
    with Session(app.state.engine) as session:
        statement = select(func.count()).select_from(model)
        for name, value in where.items():
            statement = statement.where(getattr(model, name) == value)
        return session.exec(statement).one()


def signed_in_token(user_id: int) -> str:
    with Session(app.state.engine) as session:
        user = session.get(User, user_id)
        assert user is not None
        return create_session(session, user, None)


def edit(scene: Scene, user_id: int, viewing: int | None = None, **fields: str):  # type: ignore[no-untyped-def]
    viewing = viewing or scene.kn21
    data = {
        "first_name": "Taras",
        "last_name": "Shevchenko",
        "class_id": str(scene.kn21),
        "region": str(scene.region),
        "institution": str(scene.a),
        "class": str(viewing),
        **fields,
    }
    return scene.teacher.post(f"/teacher/students/{user_id}", data=data, follow_redirects=False)


# ---------------------------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------------------------


def test_the_students_are_listed_by_last_name_then_first_name(scene: Scene) -> None:
    """US4-1, US4-2, FR-054."""
    ids = [
        student("b@example.org", scene.kn21, "Bohdan", "kovalenko"),
        student("a@example.org", scene.kn21, "Andriy", "Kovalenko"),
        student("c@example.org", scene.kn21, "Iryna", "Antonenko"),
    ]
    body = scene.teacher.get(scene.selection(scene.kn21)).text
    rows = [(row["Name"], row["Email"]) for row in html.table_rows(body)]
    assert rows == [
        ("Antonenko Iryna", "c@example.org"),
        ("Kovalenko Andriy", "a@example.org"),
        ("kovalenko Bohdan", "b@example.org"),
    ]
    for user_id in ids:
        hrefs = [link.href for link in html.content_links(body)]
        assert f"/teacher/students/{user_id}{scene.carried(scene.kn21)}" in hrefs
        assert any(href.startswith(f"/teacher/students/{user_id}/remove") for href in hrefs)


def test_read_access_lists_students_without_actions(scene: Scene) -> None:
    """US4-2: the students of "Lviv Academy", invited by its Write teacher."""
    user_id = student("ivan@example.org", scene.other_class, "Ivan", "Franko", by=PETRO)
    with Session(app.state.engine) as session:
        lviv = session.get(Institution, scene.b)
        assert lviv is not None
        region = lviv.region_id
    path = f"/teacher/students?region={region}&institution={scene.b}&class={scene.other_class}"
    body = scene.teacher.get(path).text
    assert "Franko Ivan" in [row["Name"] for row in html.table_rows(body)]
    assert f"/teacher/students/{user_id}" not in body


# ---------------------------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------------------------


def test_the_edit_page_offers_the_active_classes_of_the_institution(scene: Scene) -> None:
    """US4-3."""
    user_id = student("taras@example.org", scene.kn21)
    body = scene.teacher.get(f"/teacher/students/{user_id}{scene.carried(scene.kn21)}").text
    assert "taras@example.org" in body
    assert "Kyiv Polytechnic Institute (Kyiv)" in body
    assert html.control(body, "first_name")["value"] == "Taras"
    assert html.control(body, "last_name")["value"] == "Shevchenko"
    classes = html.options(body, "class_id")
    assert html.Option(str(scene.kn21), "KN-21 · year 2", True) in classes
    assert html.Option(str(scene.kn22), "KN-22 · year 2", False) in classes
    assert "KN-11" not in body
    assert "LA-1" not in body
    assert "email" not in [i.name for f in html.forms(body) for i in f.inputs]


def test_saving_new_names_and_a_class_keeps_the_student_signed_in(scene: Scene) -> None:
    """US4-4, FR-010, FR-041, FR-042: and the class the teacher was viewing stays selected."""
    user_id = student("taras@example.org", scene.kn21)
    token = signed_in_token(user_id)
    records = count(ConsentRecord, user_id=user_id)
    cutoffs = count(InvitationCutoff)
    response = edit(
        scene, user_id, first_name=" Taras ", last_name="Shevchenko-Bilyk", class_id=str(scene.kn22)
    )
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(scene.kn21)
    after = person(user_id)
    assert (after.first_name, after.last_name) == ("Taras", "Shevchenko-Bilyk")
    assert class_of(user_id) == scene.kn22
    with Session(app.state.engine) as session:
        assert get_session_identity(session, token) is not None
    assert count(ConsentRecord, user_id=user_id) == records
    assert count(InvitationCutoff) == cutoffs
    assert "Shevchenko-Bilyk" in scene.teacher.get(scene.selection(scene.kn22)).text


def test_an_unchanged_edit_writes_nothing(scene: Scene) -> None:
    user_id = student("taras@example.org", scene.kn21)
    before = person(user_id).updated_at
    assert edit(scene, user_id).status_code == 303
    assert person(user_id).updated_at == before


def test_an_invalid_name_is_refused(scene: Scene) -> None:
    """US4-5."""
    user_id = student("taras@example.org", scene.kn21)
    response = edit(scene, user_id, first_name="", class_id=str(scene.kn22))
    assert response.status_code == 400
    assert "Enter a first name." in response.text
    assert class_of(user_id) == scene.kn21


def test_a_deactivated_class_is_refused_as_a_form_error(scene: Scene) -> None:
    """US4-5, spec Assumptions."""
    user_id = student("taras@example.org", scene.kn21)
    response = edit(scene, user_id, first_name="Changed", class_id=str(scene.kn11))
    assert response.status_code == 400
    assert "This class is deactivated." in response.text
    assert class_of(user_id) == scene.kn21
    assert person(user_id).first_name == "Taras"


@pytest.mark.parametrize("target", ["other-institution", "unknown", "abc", "empty", "huge"])
def test_a_class_out_of_the_institution_is_access_denied(scene: Scene, target: str) -> None:
    """US4-5, contracts §2.4: nothing changes, never a 422."""
    user_id = student("taras@example.org", scene.kn21)
    value = {
        "other-institution": str(scene.other_class),
        "unknown": "999999",
        "abc": "abc",
        "empty": "",
        "huge": "9" * 40,
    }[target]
    response = edit(scene, user_id, first_name="Changed", class_id=value)
    assert response.status_code == 403
    assert "Access denied" in response.text
    assert class_of(user_id) == scene.kn21
    assert person(user_id).first_name == "Taras"


def test_an_out_of_reach_selection_returns_to_the_students_class(scene: Scene) -> None:
    user_id = student("taras@example.org", scene.kn21)
    response = edit(scene, user_id, viewing=scene.other_class, class_id=str(scene.kn22))
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(scene.kn22)


# ---------------------------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------------------------


def remove(scene: Scene, user_id: int):  # type: ignore[no-untyped-def]
    return scene.teacher.post(
        f"/teacher/students/{user_id}/remove",
        data={"region": str(scene.region), "institution": str(scene.a), "class": str(scene.kn21)},
        follow_redirects=False,
    )


def test_the_confirmation_names_the_student_the_class_and_the_institution(scene: Scene) -> None:
    """FR-043: and opening it changes nothing."""
    user_id = student("taras@example.org", scene.kn21)
    body = scene.teacher.get(f"/teacher/students/{user_id}/remove{scene.carried(scene.kn21)}").text
    for shown in ("Remove Taras Shevchenko as a student?", "KN-21 · year 2", "Kyiv Polytechnic"):
        assert shown in body
    assert class_of(user_id) == scene.kn21


def test_removing_a_student_only_person(scene: Scene) -> None:
    """US4-6, FR-043."""
    user_id = student("taras@example.org", scene.kn21)
    signed_in_token(user_id)
    signed_in_token(user_id)
    response = remove(scene, user_id)
    assert response.status_code == 303
    assert response.headers["location"] == scene.selection(scene.kn21)
    after = person(user_id)
    assert not after.is_active
    assert (after.email, after.first_name, after.last_name) == (
        "taras@example.org",
        "Taras",
        "Shevchenko",
    )
    assert class_of(user_id) is None
    assert count(UserSession, user_id=user_id) == 0
    assert count(ConsentRecord, user_id=user_id) == 1
    with Session(app.state.engine) as session:
        assert get_roles(session, user_id) == ()
        secret = app.state.settings.secret_key
        assert get_cutoff(session, secret, "taras@example.org", Role.STUDENT) is not None
    assert "taras@example.org" not in scene.teacher.get(scene.selection(scene.kn21)).text


def test_removing_a_teacher_and_student_keeps_the_teacher(scene: Scene) -> None:
    """US4-7."""
    engine, settings = app.state.engine, app.state.settings
    user_id = make_teacher(
        engine, settings, email="both@example.org", institutions={scene.b: AccessLevel.READ}
    )
    assert student("both@example.org", scene.kn21) == user_id
    signed_in_token(user_id)
    assert remove(scene, user_id).status_code == 303
    after = person(user_id)
    assert after.is_active
    assert count(UserSession, user_id=user_id) == 0
    with Session(engine) as session:
        assert get_roles(session, user_id) == (Role.TEACHER,)


@pytest.mark.parametrize("also_teacher", [False, True], ids=["inactive", "still-active"])
def test_a_link_issued_before_a_removal_is_refused_and_a_newer_one_works(
    scene: Scene, client: TestClient, also_teacher: bool
) -> None:
    """US4-8, US3-5 (moved here because it needs a removal), FR-030."""
    engine, settings = app.state.engine, app.state.settings
    email = "taras@example.org"
    if also_teacher:
        make_teacher(engine, settings, email=email, institutions={scene.b: AccessLevel.READ})
    user_id = student(email, scene.kn21)
    old = invite_student(engine, settings, email=email, class_id=scene.kn22, inviter_email=OLENA)
    assert remove(scene, user_id).status_code == 303
    with Session(engine) as session:
        text_id = current_consent_text(session, Role.STUDENT).id
    refused = client.post(f"/invitations/{old}", data={"consent_text_id": str(text_id)})
    assert refused.status_code == 400
    assert NEUTRAL in refused.text
    assert class_of(user_id) is None

    newer = invite_student(engine, settings, email=email, class_id=scene.kn22, inviter_email=OLENA)
    accepted = client.post(
        f"/invitations/{newer}", data={"consent_text_id": str(text_id)}, follow_redirects=False
    )
    assert accepted.status_code == 303
    assert class_of(user_id) == scene.kn22
    assert person(user_id).is_active
    with Session(engine) as session:
        records = session.exec(select(ConsentRecord).where(ConsentRecord.user_id == user_id)).all()
        student_records = [
            r
            for r in records
            if r.consent_text_id == current_consent_text(session, Role.STUDENT).id
        ]
    assert len(student_records) == 2


# ---------------------------------------------------------------------------------------------
# Reloads, stale pages and the teacher's own address
# ---------------------------------------------------------------------------------------------


def test_following_a_result_page_again_changes_nothing(scene: Scene) -> None:
    """SC-009, FR-056."""
    user_id = student("taras@example.org", scene.kn21)
    moved = edit(scene, user_id, class_id=str(scene.kn22))
    stamp = person(user_id).updated_at
    for _ in range(2):
        assert scene.teacher.get(moved.headers["location"]).status_code == 200
    assert person(user_id).updated_at == stamp
    removed = remove(scene, user_id)
    for _ in range(2):
        assert scene.teacher.get(removed.headers["location"]).status_code == 200
    assert count(ConsentRecord, user_id=user_id) == 1
    assert count(UserSession, user_id=user_id) == 0


def test_saving_the_edit_of_a_removed_student_is_access_denied(scene: Scene) -> None:
    """Spec Edge Cases."""
    user_id = student("taras@example.org", scene.kn21)
    assert scene.teacher.get(f"/teacher/students/{user_id}").status_code == 200
    remove(scene, user_id)
    assert edit(scene, user_id, first_name="Late").status_code == 403
    assert person(user_id).first_name == "Taras"
    assert scene.teacher.post(f"/teacher/students/{user_id}/remove").status_code == 403


def test_a_teacher_can_invite_themselves_as_a_student(scene: Scene, client: TestClient) -> None:
    """Spec Edge Cases: names kept; listed, edited and removed like anyone."""
    token = invite_student(
        app.state.engine,
        app.state.settings,
        email=OLENA,
        class_id=scene.kn21,
        inviter_email=OLENA,
        first="O.",
        last="K.",
    )
    with Session(app.state.engine) as session:
        text_id = current_consent_text(session, Role.STUDENT).id
    assert (
        client.post(
            f"/invitations/{token}",
            data={"consent_text_id": str(text_id)},
            follow_redirects=False,
        ).status_code
        == 303
    )
    body = scene.teacher.get(scene.selection(scene.kn21)).text
    assert ("Kovalenko Olena", OLENA) in [(r["Name"], r["Email"]) for r in html.table_rows(body)]
    assert (
        edit(
            scene,
            scene.teacher_id,
            class_id=str(scene.kn22),
            first_name="Olena",
            last_name="Kovalenko",
        ).status_code
        == 303
    )
    assert class_of(scene.teacher_id) == scene.kn22
    with Session(app.state.engine) as session:
        assert get_user_by_email(session, OLENA) is not None
