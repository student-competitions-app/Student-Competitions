"""Cut-offs, erasure and teacher removal, at the service level, on both engines.

See specs/008-teacher-management-consent/contracts/services.md §consent and §teachers, and
research D5, D8, D9. Teachers are created through the real invitation services
(`invite_and_accept`).
"""

from datetime import timedelta

import pytest
from sqlalchemy import Engine, func
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.core.security import hash_invitation_cutoff_key
from app.models import (
    AccessLevel,
    ConsentRecord,
    InvitationCutoff,
    LoginCode,
    Role,
    TeacherInstitution,
    TeacherProfile,
    User,
    UserSession,
)
from app.services.consent import (
    current_consent_text,
    describe_erasure,
    erase_personal_data,
    get_cutoff,
    has_consent_data,
    set_cutoff,
)
from app.services.login import issue_code
from app.services.sessions import create_session
from app.services.teachers import TeacherNotFound, remove_teacher
from app.services.users import get_roles, reconcile_users
from tests.conftest import ADMIN_EMAIL, invite_and_accept, make_institution, seed_roles_directly

OLENA = "olena@example.org"


@pytest.fixture
def kyiv_school(engine: Engine) -> int:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    return make_institution(engine, "School 5")


def a_teacher(engine: Engine, settings: AuthSettings, institution: int, email: str = OLENA) -> int:
    return invite_and_accept(
        engine, settings, email=email, institutions={institution: AccessLevel.WRITE}
    )


def user(session: Session, user_id: int) -> User:
    session.expire_all()
    found = session.get(User, user_id)
    assert found is not None
    return found


def count(session: Session, model: type, **where: object) -> int:
    session.expire_all()
    statement = select(func.count()).select_from(model)
    for name, value in where.items():
        statement = statement.where(getattr(model, name) == value)
    return session.exec(statement).one()


def sign_in_twice(session: Session, user_id: int, settings: AuthSettings) -> None:
    person = user(session, user_id)
    create_session(session, person, None)
    create_session(session, person, None)
    issue_code(session, settings.secret_key, person)


# ---------------------------------------------------------------------------------------------
# Texts and cut-offs
# ---------------------------------------------------------------------------------------------


def test_the_current_teacher_text_is_version_one(session: Session) -> None:
    assert current_consent_text(session, Role.TEACHER).version == 1


def test_a_cutoff_is_only_ever_raised_and_holds_no_address(
    session: Session, auth_settings: AuthSettings
) -> None:
    now = utc_now()
    key = auth_settings.secret_key
    set_cutoff(session, key, OLENA, Role.TEACHER, now)
    set_cutoff(session, key, OLENA, Role.TEACHER, now - timedelta(hours=1))
    session.commit()
    assert get_cutoff(session, key, OLENA, Role.TEACHER) == now
    later = now + timedelta(microseconds=1)
    set_cutoff(session, key, OLENA, Role.TEACHER, later)
    session.commit()
    assert get_cutoff(session, key, OLENA, Role.TEACHER) == later
    [row] = session.exec(select(InvitationCutoff)).all()
    assert row.email_hash == hash_invitation_cutoff_key(key, OLENA)
    assert "olena" not in row.email_hash
    assert get_cutoff(session, key, "other@example.org", Role.TEACHER) is None


# ---------------------------------------------------------------------------------------------
# Erasure
# ---------------------------------------------------------------------------------------------


def test_erasing_a_teacher_with_no_other_role(
    engine: Engine, session: Session, auth_settings: AuthSettings, kyiv_school: int
) -> None:
    teacher_id = a_teacher(engine, auth_settings, kyiv_school)
    sign_in_twice(session, teacher_id, auth_settings)
    records_before = session.exec(select(ConsentRecord)).all()
    now = utc_now()

    plan = describe_erasure(session, user(session, teacher_id))
    assert (plan.first_name, plan.last_name, plan.email) == ("Olena", "Kovalenko", OLENA)
    assert plan.roles_to_remove == (Role.TEACHER,)
    assert (plan.email_kept, plan.will_deactivate) == (False, True)
    assert user(session, teacher_id).first_name == "Olena"

    result = erase_personal_data(session, auth_settings, teacher_id, now=now)

    assert result.roles_removed == (Role.TEACHER,)
    assert (result.email_kept, result.deactivated) == (False, True)
    erased = user(session, teacher_id)
    assert (erased.first_name, erased.last_name) == (None, None)
    assert erased.email == f"erased-{teacher_id}"
    assert erased.data_erased_at == now
    assert erased.is_active is False
    assert not has_consent_data(erased)
    assert get_roles(session, teacher_id) == ()
    assert count(session, TeacherProfile) == 0
    assert count(session, TeacherInstitution) == 0
    assert count(session, UserSession, user_id=teacher_id) == 0
    assert count(session, LoginCode, user_id=teacher_id) == 0
    assert session.exec(select(ConsentRecord)).all() == records_before
    assert get_cutoff(session, auth_settings.secret_key, OLENA, Role.TEACHER) == now


def test_erasing_an_administrator_who_teaches_keeps_the_role_and_the_address(
    engine: Engine, session: Session, auth_settings: AuthSettings, kyiv_school: int
) -> None:
    teacher_id = a_teacher(engine, auth_settings, kyiv_school, email=ADMIN_EMAIL)
    sign_in_twice(session, teacher_id, auth_settings)

    plan = describe_erasure(session, user(session, teacher_id))
    assert plan.roles_to_remove == (Role.TEACHER,)
    assert (plan.email_kept, plan.will_deactivate) == (True, False)

    result = erase_personal_data(session, auth_settings, teacher_id)

    assert (result.roles_removed, result.email_kept, result.deactivated) == (
        (Role.TEACHER,),
        True,
        False,
    )
    admin = user(session, teacher_id)
    assert admin.email == ADMIN_EMAIL
    assert admin.is_active is True
    assert admin.first_name is None
    assert get_roles(session, teacher_id) == (Role.ADMIN,)
    assert count(session, UserSession, user_id=teacher_id) == 0


def test_erasing_a_removed_teacher_who_is_still_an_administrator(
    engine: Engine, session: Session, auth_settings: AuthSettings, kyiv_school: int
) -> None:
    teacher_id = a_teacher(engine, auth_settings, kyiv_school, email=ADMIN_EMAIL)
    remove_teacher(session, auth_settings, teacher_id)
    assert user(session, teacher_id).first_name == "Olena"

    plan = describe_erasure(session, user(session, teacher_id))
    assert plan.roles_to_remove == ()
    assert (plan.email_kept, plan.will_deactivate) == (True, False)

    result = erase_personal_data(session, auth_settings, teacher_id)
    assert result.roles_removed == ()
    assert user(session, teacher_id).first_name is None
    assert user(session, teacher_id).email == ADMIN_EMAIL


# ---------------------------------------------------------------------------------------------
# Removing a teacher
# ---------------------------------------------------------------------------------------------


def test_removing_a_teacher_with_no_other_role(
    engine: Engine, session: Session, auth_settings: AuthSettings, kyiv_school: int
) -> None:
    teacher_id = a_teacher(engine, auth_settings, kyiv_school)
    sign_in_twice(session, teacher_id, auth_settings)
    now = utc_now()

    remove_teacher(session, auth_settings, teacher_id, now=now)

    removed = user(session, teacher_id)
    assert removed.is_active is False
    assert (removed.email, removed.first_name, removed.last_name) == (OLENA, "Olena", "Kovalenko")
    assert get_roles(session, teacher_id) == ()
    assert count(session, TeacherProfile) == 0
    assert count(session, TeacherInstitution) == 0
    assert count(session, UserSession, user_id=teacher_id) == 0
    assert count(session, ConsentRecord, user_id=teacher_id) == 1
    assert get_cutoff(session, auth_settings.secret_key, OLENA, Role.TEACHER) == now


def test_removing_an_administrator_who_teaches_keeps_them_active(
    engine: Engine, session: Session, auth_settings: AuthSettings, kyiv_school: int
) -> None:
    teacher_id = a_teacher(engine, auth_settings, kyiv_school, email=ADMIN_EMAIL)
    sign_in_twice(session, teacher_id, auth_settings)
    remove_teacher(session, auth_settings, teacher_id)
    assert user(session, teacher_id).is_active is True
    assert get_roles(session, teacher_id) == (Role.ADMIN,)
    assert count(session, UserSession, user_id=teacher_id) == 0


def test_only_a_current_teacher_can_be_removed(
    engine: Engine, session: Session, auth_settings: AuthSettings, kyiv_school: int
) -> None:
    seed_roles_directly(engine, {"cast.teacher@example.com": [Role.TEACHER]})
    cast = session.exec(select(User).where(User.email == "cast.teacher@example.com")).one()
    admin = session.exec(select(User).where(User.email == ADMIN_EMAIL)).one()
    for user_id in (999_999, cast.id, admin.id):
        assert user_id is not None
        with pytest.raises(TeacherNotFound):
            remove_teacher(session, auth_settings, user_id)
    teacher_id = a_teacher(engine, auth_settings, kyiv_school)
    remove_teacher(session, auth_settings, teacher_id)
    with pytest.raises(TeacherNotFound):
        remove_teacher(session, auth_settings, teacher_id)
