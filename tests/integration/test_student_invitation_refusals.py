"""User story 3: a student acceptance is refused when the invitation is no longer valid.

See specs/009-classes-students-management/spec.md US3, FR-030–FR-035 and SC-003. Each refusal
answers with the milestone 8 neutral message, and stores no user, role, enrolment or consent
record. The teacher is real: Write to "Kyiv Polytechnic Institute" (Kyiv), with the class "KN-21"
(year 2). Every case runs on both engines, except the race at the end, which is PostgreSQL-only.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
    Enrolment,
    Institution,
    Region,
    Role,
    SchoolClass,
    User,
    UserRole,
)
from app.routers.invitations import CONSENT_CHANGED, EXPIRED, NEUTRAL
from app.services.classes import ClassInUse, delete_class, set_class_active, update_class
from app.services.consent import erase_personal_data
from app.services.institutions import set_institution_active
from app.services.invitations import accept_invitation
from app.services.regions import set_region_active
from app.services.teachers import remove_teacher, update_teacher
from app.services.users import get_roles, get_user_by_email
from tests.conftest import (
    invite_student,
    make_class,
    make_institution,
    make_teacher,
)

OLENA = "olena@example.org"
TARAS = "taras@example.org"


@dataclass(frozen=True)
class Scene:
    teacher_id: int
    institution: int
    other: int
    school_class: int


@pytest.fixture
def scene(client: TestClient) -> Scene:
    engine = app.state.engine
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    other = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    teacher_id = make_teacher(
        engine,
        app.state.settings,
        email=OLENA,
        institutions={institution: AccessLevel.WRITE, other: AccessLevel.WRITE},
    )
    return Scene(
        teacher_id=teacher_id,
        institution=institution,
        other=other,
        school_class=make_class(engine, institution, "KN-21", 2),
    )


def issue(scene: Scene, email: str = TARAS, class_id: int | None = None, **kwargs: object) -> str:
    return invite_student(
        app.state.engine,
        app.state.settings,
        email=email,
        class_id=class_id or scene.school_class,
        inviter_email=OLENA,
        **kwargs,  # type: ignore[arg-type]
    )


def student_text_id() -> int:
    with Session(app.state.engine) as session:
        text = session.exec(
            select(ConsentText).where(ConsentText.role == "student").order_by(ConsentText.version)
        ).first()
        assert text is not None and text.id is not None
        return text.id


def stored() -> tuple[int, int, int, int]:
    """Users, role rows, enrolments and consent records."""
    with Session(app.state.engine) as session:
        return tuple(  # type: ignore[return-value]
            session.exec(select(func.count()).select_from(model)).one()
            for model in (User, UserRole, Enrolment, ConsentRecord)
        )


def agree(client: TestClient, token: str, consent_text_id: int | None = None) -> object:
    return client.post(
        f"/invitations/{token}",
        data={"consent_text_id": str(consent_text_id or student_text_id())},
        follow_redirects=False,
    )


def assert_refused(client: TestClient, token: str) -> None:
    before = stored()
    response = agree(client, token)
    assert response.status_code == 400  # type: ignore[attr-defined]
    assert NEUTRAL in response.text  # type: ignore[attr-defined]
    assert stored() == before
    assert get_user_by_email(Session(app.state.engine), TARAS) is None


def tampered(token: str) -> str:
    position = len(token) // 2
    replacement = "A" if token[position] != "A" else "B"
    return token[:position] + replacement + token[position + 1 :]


# ---------------------------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------------------------


def test_a_tampered_link_is_refused(client: TestClient, scene: Scene) -> None:
    """US3-1."""
    assert_refused(client, tampered(issue(scene)))


def test_an_expired_link_has_its_own_message(client: TestClient, scene: Scene) -> None:
    """US3-1."""
    token = issue(scene, now=utc_now() - timedelta(days=7))
    before = stored()
    response = agree(client, token)
    assert EXPIRED in response.text  # type: ignore[attr-defined]
    assert stored() == before


# ---------------------------------------------------------------------------------------------
# The inviter
# ---------------------------------------------------------------------------------------------


def _deactivate_inviter(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        user = session.get(User, scene.teacher_id)
        assert user is not None
        user.is_active = False
        session.add(user)
        session.commit()


def _remove_inviter(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        remove_teacher(session, app.state.settings, scene.teacher_id)


def _unlink_inviter(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        update_teacher(
            session, scene.teacher_id, "Olena", "Kovalenko", {scene.other: AccessLevel.WRITE}, False
        )


def _lower_inviter(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        update_teacher(
            session,
            scene.teacher_id,
            "Olena",
            "Kovalenko",
            {scene.institution: AccessLevel.READ, scene.other: AccessLevel.WRITE},
            False,
        )


INVITER_CHANGES: dict[str, Callable[[Scene], None]] = {
    "deactivated": _deactivate_inviter,
    "removed": _remove_inviter,
    "unlinked": _unlink_inviter,
    "lowered-to-read": _lower_inviter,
}


@pytest.mark.parametrize("change", list(INVITER_CHANGES))
def test_the_inviter_must_still_be_a_write_teacher(
    client: TestClient, scene: Scene, change: str
) -> None:
    """US3-2, FR-032."""
    token = issue(scene)
    INVITER_CHANGES[change](scene)
    assert_refused(client, token)


# ---------------------------------------------------------------------------------------------
# The class
# ---------------------------------------------------------------------------------------------


def _delete_class(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        delete_class(session, scene.teacher_id, scene.school_class)


def _deactivate_class(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        set_class_active(session, scene.teacher_id, scene.school_class, False)


def _deactivate_institution(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        institution = session.get(Institution, scene.institution)
        assert institution is not None
        set_institution_active(session, institution.region_id, scene.institution, False)


def _deactivate_region(scene: Scene) -> None:
    with Session(app.state.engine) as session:
        region = session.exec(select(Region).where(Region.name == "Kyiv")).one()
        assert region.id is not None
        set_region_active(session, region.id, False)


CLASS_CHANGES: dict[str, Callable[[Scene], None]] = {
    "class-deleted": _delete_class,
    "class-deactivated": _deactivate_class,
    "institution-deactivated": _deactivate_institution,
    "region-deactivated": _deactivate_region,
}


@pytest.mark.parametrize("change", list(CLASS_CHANGES))
def test_the_class_must_still_be_available(client: TestClient, scene: Scene, change: str) -> None:
    """US3-3, FR-005, FR-032."""
    token = issue(scene)
    CLASS_CHANGES[change](scene)
    assert_refused(client, token)


def test_a_class_moved_out_of_its_institution_is_refused(client: TestClient, scene: Scene) -> None:
    """A class never moves (FR-003); should the row ever disagree with the link, it is refused."""
    token = issue(scene)
    with Session(app.state.engine) as session:
        row = session.get(SchoolClass, scene.school_class)
        assert row is not None
        row.institution_id = scene.other
        session.add(row)
        session.commit()
    assert_refused(client, token)


def test_a_renamed_class_still_works_and_shows_its_new_values(
    client: TestClient, scene: Scene
) -> None:
    """US3-4, FR-031."""
    token = issue(scene)
    with Session(app.state.engine) as session:
        update_class(session, scene.teacher_id, scene.school_class, "KN-22", "3")
    page = client.get(f"/invitations/{token}").text
    assert "Class: KN-22 · year 3" in page
    assert "KN-21" not in page
    assert agree(client, token).status_code == 303  # type: ignore[attr-defined]
    with Session(app.state.engine) as session:
        taras = get_user_by_email(session, TARAS)
        assert taras is not None and taras.id is not None
        enrolment = session.get(Enrolment, taras.id)
        assert enrolment is not None and enrolment.class_id == scene.school_class


# ---------------------------------------------------------------------------------------------
# The cut-off
# ---------------------------------------------------------------------------------------------


def test_a_link_issued_before_a_withdrawal_is_refused_and_a_later_one_works(
    client: TestClient, scene: Scene
) -> None:
    """US3-5, FR-030: withdrawal raises the student cut-off too, whatever role was withdrawn.
    The removal case is in `test_teacher_students.py`."""
    engine, settings = app.state.engine, app.state.settings
    teacher_id = make_teacher(
        engine, settings, email=TARAS, institutions={scene.institution: AccessLevel.READ}
    )
    earlier = issue(scene, now=utc_now() - timedelta(minutes=5))
    with Session(engine) as session:
        erase_personal_data(session, settings, teacher_id, now=utc_now() - timedelta(minutes=1))
    assert_refused(client, earlier)
    later = issue(scene)
    assert agree(client, later).status_code == 303  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------------------------
# Already a student
# ---------------------------------------------------------------------------------------------


def test_accepting_twice_changes_nothing_the_second_time(client: TestClient, scene: Scene) -> None:
    """US3-6, FR-034, FR-035."""
    token = issue(scene)
    assert agree(client, token).status_code == 303  # type: ignore[attr-defined]
    before = stored()
    again = agree(client, token)
    assert again.status_code == 303  # type: ignore[attr-defined]
    assert "You are already a student." in client.get(f"/invitations/{token}").text
    assert stored() == before


def test_of_two_links_into_two_classes_the_first_accepted_wins(
    client: TestClient, scene: Scene
) -> None:
    """Spec Edge Cases: a student is never in two places."""
    second_class = make_class(app.state.engine, scene.other, "KL-5", 5)
    first = issue(scene)
    second = issue(scene, class_id=second_class)
    assert agree(client, first).status_code == 303  # type: ignore[attr-defined]
    before = stored()
    agree(client, second)
    assert "You are already a student." in client.get(f"/invitations/{second}").text
    assert stored() == before
    with Session(app.state.engine) as session:
        enrolments = session.exec(select(Enrolment)).all()
    assert [row.class_id for row in enrolments] == [scene.school_class]


# ---------------------------------------------------------------------------------------------
# What I agree reads
# ---------------------------------------------------------------------------------------------


def test_a_changed_consent_text_shows_the_page_again(client: TestClient, scene: Scene) -> None:
    """US3-7, FR-030."""
    token = issue(scene)
    shown = student_text_id()
    with Session(app.state.engine) as session:
        session.add(
            ConsentText(
                role="student",
                version=2,
                text="A new student text, version 2.",
                published_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
        )
        session.commit()
    before = stored()
    response = agree(client, token, shown)
    assert response.status_code == 409  # type: ignore[attr-defined]
    assert CONSENT_CHANGED in response.text  # type: ignore[attr-defined]
    assert "A new student text, version 2." in response.text  # type: ignore[attr-defined]
    assert stored() == before


def test_extra_form_fields_are_ignored(client: TestClient, scene: Scene) -> None:
    """US3-8."""
    other_class = make_class(app.state.engine, scene.other, "KL-5", 5)
    token = issue(scene)
    response = client.post(
        f"/invitations/{token}",
        data={
            "consent_text_id": str(student_text_id()),
            "class_id": str(other_class),
            "institution_id": str(scene.other),
            "first_name": "Hacked",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(app.state.engine) as session:
        taras = get_user_by_email(session, TARAS)
        assert taras is not None and taras.id is not None
        assert taras.first_name == "Taras"
        enrolment = session.get(Enrolment, taras.id)
        assert enrolment is not None and enrolment.class_id == scene.school_class


def test_the_teacher_checks_do_not_apply_to_a_student_link(
    client: TestClient, scene: Scene
) -> None:
    """US3-9: the inviter is no administrator, and that is fine."""
    with Session(app.state.engine) as session:
        assert Role.ADMIN not in get_roles(session, scene.teacher_id)
    assert agree(client, issue(scene)).status_code == 303  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------------------------
# Acceptance against a concurrent class deletion (FR-035)
# ---------------------------------------------------------------------------------------------


def _race(scene: Scene, attempt: int) -> int:
    """Run one acceptance and one deletion of the same empty class at the same moment, each in
    its own database session; the class id."""
    engine, settings = app.state.engine, app.state.settings
    class_id = make_class(engine, scene.institution, f"Race-{attempt}")
    token = issue(scene, email=f"race{attempt}@example.org", class_id=class_id)
    text_id = student_text_id()
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def accepting() -> None:
        try:
            with Session(engine) as session:
                barrier.wait()
                accept_invitation(session, settings, token, text_id)
        except BaseException as error:  # noqa: BLE001 — reported below
            errors.append(error)

    def deleting() -> None:
        try:
            with Session(engine) as session:
                barrier.wait()
                delete_class(session, scene.teacher_id, class_id)
        except ClassInUse:
            pass
        except BaseException as error:  # noqa: BLE001 — reported below
            errors.append(error)

    threads = [threading.Thread(target=accepting), threading.Thread(target=deleting)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    return class_id


def test_acceptance_and_class_deletion_at_once_never_leave_a_student_without_a_class(
    scene: Scene, database_url: str
) -> None:
    """Spec Edge Cases, FR-035: either the class stays with one enrolment, or it is gone and so
    is every enrolment. PostgreSQL only: on SQLite the locks render nothing, and writers are
    serialised anyway."""
    if not database_url.startswith("postgresql"):
        pytest.skip("row locks are a PostgreSQL behaviour")
    for attempt in range(5):
        class_id = _race(scene, attempt)
        with Session(app.state.engine) as session:
            remaining = session.get(SchoolClass, class_id)
            enrolled = session.exec(
                select(func.count()).select_from(Enrolment).where(Enrolment.class_id == class_id)
            ).one()
            orphans = session.exec(
                select(func.count())
                .select_from(Enrolment)
                .outerjoin(SchoolClass, SchoolClass.id == Enrolment.class_id)
                .where(SchoolClass.id.is_(None))  # type: ignore[union-attr]
            ).one()
        assert (remaining is not None and enrolled == 1) or (remaining is None and enrolled == 0)
        assert orphans == 0
