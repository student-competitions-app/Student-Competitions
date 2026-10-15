"""User story 2 (scenarios 6–8): a removal or withdrawal always beats an older invitation.

See specs/008-teacher-management-consent/research.md#d5, FR-027, FR-034 and FR-048. Times are
given explicitly through the services' `now`, so "before", "after" and "at the same microsecond"
are exact. Every case runs on both engines.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.models import AccessLevel, Role, TeacherInstitution, User
from app.services.consent import current_consent_text, erase_personal_data
from app.services.invitations import Accepted, Refused, accept_invitation, evaluate_invitation
from app.services.teachers import remove_teacher
from app.services.users import get_roles, reconcile_users
from tests.conftest import ADMIN_EMAIL, invite, invite_and_accept, make_institution

OLENA = "olena@example.org"


@pytest.fixture
def school(engine: Engine) -> int:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    return make_institution(engine, "School 5")


@pytest.fixture
def t0() -> datetime:
    return utc_now() - timedelta(days=1)


def at(t0: datetime, minutes: int) -> datetime:
    return t0 + timedelta(minutes=minutes)


def try_accept(engine: Engine, settings: AuthSettings, token: str, now: datetime) -> object:
    with Session(engine) as session:
        text_id = current_consent_text(session, Role.TEACHER).id
        assert text_id is not None
        return accept_invitation(session, settings, token, text_id, now=now)


def user(engine: Engine, user_id: int) -> User:
    with Session(engine) as session:
        found = session.get(User, user_id)
        assert found is not None
        return found


def test_an_older_invitation_is_refused_after_removal(
    engine: Engine, auth_settings: AuthSettings, school: int, t0: datetime
) -> None:
    """US2-6: the teacher is now inactive."""
    teacher_id = invite_and_accept(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=t0
    )
    older = invite(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.WRITE}, now=at(t0, 1)
    )
    with Session(engine) as session:
        remove_teacher(session, auth_settings, teacher_id, now=at(t0, 2))
    assert isinstance(try_accept(engine, auth_settings, older, at(t0, 3)), Refused)
    with Session(engine) as session:
        assert isinstance(evaluate_invitation(session, auth_settings, older, at(t0, 3)), Refused)
    assert user(engine, teacher_id).is_active is False


def test_an_older_invitation_is_refused_for_an_administrator_who_lost_the_teacher_role(
    engine: Engine, auth_settings: AuthSettings, school: int, t0: datetime
) -> None:
    """US2-6: the person stays active as an administrator."""
    teacher_id = invite_and_accept(
        engine, auth_settings, email=ADMIN_EMAIL, institutions={school: AccessLevel.READ}, now=t0
    )
    older = invite(
        engine,
        auth_settings,
        email=ADMIN_EMAIL,
        institutions={school: AccessLevel.READ},
        now=at(t0, 1),
    )
    with Session(engine) as session:
        remove_teacher(session, auth_settings, teacher_id, now=at(t0, 2))
    assert isinstance(try_accept(engine, auth_settings, older, at(t0, 3)), Refused)
    with Session(engine) as session:
        assert get_roles(session, teacher_id) == (Role.ADMIN,)


def test_an_older_invitation_is_refused_after_withdrawal_though_the_email_is_gone(
    engine: Engine, auth_settings: AuthSettings, school: int, t0: datetime
) -> None:
    """US2-7: the cut-off is keyed by the address, which the erasure replaced."""
    teacher_id = invite_and_accept(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=t0
    )
    older = invite(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=at(t0, 1)
    )
    with Session(engine) as session:
        erase_personal_data(session, auth_settings, teacher_id, now=at(t0, 2))
    assert user(engine, teacher_id).email == f"erased-{teacher_id}"
    assert isinstance(try_accept(engine, auth_settings, older, at(t0, 3)), Refused)
    with Session(engine) as session:
        assert session.exec(select(User).where(User.email == OLENA)).first() is None


def test_a_re_invitation_is_refused_once_the_person_deletes_their_data(
    engine: Engine, auth_settings: AuthSettings, school: int, t0: datetime
) -> None:
    """US2-8, FR-048: removed, re-invited (link B), then the data is deleted: B is refused."""
    teacher_id = invite_and_accept(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=t0
    )
    with Session(engine) as session:
        remove_teacher(session, auth_settings, teacher_id, now=at(t0, 1))
    link_b = invite(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=at(t0, 2)
    )
    with Session(engine) as session:
        erase_personal_data(session, auth_settings, teacher_id, now=at(t0, 3))
    assert isinstance(try_accept(engine, auth_settings, link_b, at(t0, 4)), Refused)


def test_a_newer_invitation_succeeds_and_reactivates_with_the_new_data(
    engine: Engine, auth_settings: AuthSettings, school: int, t0: datetime
) -> None:
    """US2-6, FR-028: issued strictly after the removal."""
    other = make_institution(engine, "Lyceum", "Lviv")
    teacher_id = invite_and_accept(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=t0
    )
    with Session(engine) as session:
        remove_teacher(session, auth_settings, teacher_id, now=at(t0, 1))
    newer = invite(
        engine,
        auth_settings,
        email=OLENA,
        first="Olha",
        last="Bondar",
        institutions={other: AccessLevel.WRITE},
        now=at(t0, 2),
    )
    outcome = try_accept(engine, auth_settings, newer, at(t0, 3))
    assert isinstance(outcome, Accepted)
    assert outcome.user_id == teacher_id
    back = user(engine, teacher_id)
    assert back.is_active is True
    assert (back.first_name, back.last_name) == ("Olha", "Bondar")
    with Session(engine) as session:
        links = session.exec(select(TeacherInstitution)).all()
        assert [(link.institution_id, link.access_level) for link in links] == [(other, "write")]


def test_at_the_same_microsecond_the_removal_wins(
    engine: Engine, auth_settings: AuthSettings, school: int, t0: datetime
) -> None:
    """Research D5: refused unless issued strictly after the cut-off."""
    teacher_id = invite_and_accept(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=t0
    )
    same = invite(
        engine, auth_settings, email=OLENA, institutions={school: AccessLevel.READ}, now=at(t0, 1)
    )
    later = invite(
        engine,
        auth_settings,
        email=OLENA,
        institutions={school: AccessLevel.READ},
        now=at(t0, 1) + timedelta(microseconds=1),
    )
    with Session(engine) as session:
        remove_teacher(session, auth_settings, teacher_id, now=at(t0, 1))
    assert isinstance(try_accept(engine, auth_settings, same, at(t0, 2)), Refused)
    assert isinstance(try_accept(engine, auth_settings, later, at(t0, 2)), Accepted)
