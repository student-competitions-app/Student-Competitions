"""The sign-in services against a real database: the behaviour matrix, row by row.

See specs/004-email-otp-auth/contracts/auth-services.md#behaviour-matrix and, for roles,
specs/005-roles-authorization/contracts/auth-services.md. Every test runs once per database
engine. Time moves through the services' `now` parameter, never by patching.
"""

import re
from datetime import timedelta

import pytest
from sqlalchemy import Engine, func
from sqlmodel import Session, select

from app.core.db import utc_now
from app.core.security import hash_code, hash_token
from app.models import LoginCode, RateLimitHit, Role, User, UserRole, UserSession
from app.services.login import CODE_TTL, issue_code, purge_expired, verify_code
from app.services.rate_limits import BUCKET_CODE_CLIENT, BUCKET_CODE_EMAIL, allow_code_request
from app.services.sessions import (
    create_session,
    get_session_identity,
    set_current_role,
    start_session,
)
from app.services.users import get_roles, reconcile_users

KEY = "k" * 32


def make_user(
    session: Session, email: str, active: bool = True, roles: tuple[Role, ...] = (Role.ADMIN,)
) -> User:
    """A user holding `roles` (none when inactive, as reconciliation keeps it)."""
    user = User(email=email, is_active=active)
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    for role in roles if active else ():
        session.add(UserRole(user_id=user.id, role=role, created_at=utc_now()))
    session.commit()
    return user


def codes(session: Session) -> list[LoginCode]:
    session.expire_all()
    return list(session.exec(select(LoginCode)))


def test_issue_code_stores_only_a_hash(session: Session) -> None:
    user = make_user(session, "a@x.org")
    now = utc_now()
    code = issue_code(session, KEY, user, now=now)
    assert re.fullmatch(r"[0-9]{6}", code)
    [row] = codes(session)
    assert re.fullmatch(r"[0-9a-f]{64}", row.code_hash)
    assert code not in row.code_hash
    assert row.expires_at == now + CODE_TTL
    assert row.attempts == 0
    assert row.used_at is None


def test_l1_the_newest_code_wins(session: Session) -> None:
    user = make_user(session, "a@x.org")
    first = issue_code(session, KEY, user)
    second = issue_code(session, KEY, user)
    assert len(codes(session)) == 1
    if first != second:
        assert verify_code(session, KEY, "a@x.org", first) is None
    assert verify_code(session, KEY, "a@x.org", second) is not None


def test_l2_a_correct_code_signs_in_once(session: Session) -> None:
    user = make_user(session, "a@x.org")
    code = issue_code(session, KEY, user)
    verified = verify_code(session, KEY, "a@x.org", code)
    assert verified is not None and verified.email == "a@x.org"
    [row] = codes(session)
    assert row.used_at is not None
    assert verify_code(session, KEY, "a@x.org", code) is None


def test_l4_expiry_is_inclusive(session: Session) -> None:
    user = make_user(session, "a@x.org")
    issued = utc_now()
    code = issue_code(session, KEY, user, now=issued)
    assert verify_code(session, KEY, "a@x.org", code, now=issued + CODE_TTL) is None
    assert verify_code(session, KEY, "a@x.org", code, now=issued + CODE_TTL - timedelta(seconds=1))


def test_l6_a_code_only_works_for_its_own_address(session: Session) -> None:
    a = make_user(session, "a@x.org")
    make_user(session, "b@x.org")
    code = issue_code(session, KEY, a)
    assert verify_code(session, KEY, "b@x.org", code) is None
    assert verify_code(session, KEY, "a@x.org", code) is not None


def test_an_inactive_user_cannot_verify(session: Session) -> None:
    user = make_user(session, "a@x.org")
    code = issue_code(session, KEY, user)
    user.is_active = False
    session.add(user)
    session.commit()
    assert verify_code(session, KEY, "a@x.org", code) is None


def test_no_code_at_all_is_refused(session: Session) -> None:
    make_user(session, "a@x.org")
    assert verify_code(session, KEY, "a@x.org", "123456") is None
    assert verify_code(session, KEY, "nobody@x.org", "123456") is None


def test_l5_a_deactivated_user_cannot_use_an_issued_code(session: Session) -> None:
    user = make_user(session, "a@x.org")
    code = issue_code(session, KEY, user)
    reconcile_users(session, {})
    assert codes(session) == []
    assert verify_code(session, KEY, "a@x.org", code) is None


def test_p1_purge_removes_only_what_is_over(session: Session) -> None:
    now = utc_now()
    live_user = make_user(session, "a@x.org")
    other = make_user(session, "b@x.org")
    expired_session = create_session(session, live_user, Role.ADMIN, now=now - timedelta(days=15))
    live_session = create_session(session, live_user, Role.ADMIN, now=now)
    issue_code(session, KEY, live_user, now=now - timedelta(hours=1))  # expired
    used = issue_code(session, KEY, other, now=now)
    assert verify_code(session, KEY, "b@x.org", used, now=now) is not None  # now used
    live_code = issue_code(session, KEY, make_user(session, "c@x.org"), now=now)
    session.add(
        RateLimitHit(bucket="code_email", key_hash="0" * 64, created_at=now - timedelta(hours=2))
    )
    session.add(RateLimitHit(bucket="code_email", key_hash="1" * 64, created_at=now))
    session.commit()

    purge_expired(session, now=now)

    session.expire_all()
    assert [row.token_hash for row in session.exec(select(UserSession))] == [
        hash_token(live_session)
    ]
    assert hash_token(expired_session) != hash_token(live_session)
    [remaining_code] = codes(session)
    assert remaining_code.code_hash == hash_code(KEY, "c@x.org", live_code)
    assert [hit.key_hash for hit in session.exec(select(RateLimitHit))] == ["1" * 64]


def test_p2_an_expired_session_is_refused_before_it_is_purged(session: Session) -> None:
    user = make_user(session, "a@x.org")
    token = create_session(session, user, Role.ADMIN, now=utc_now() - timedelta(days=14, seconds=1))
    assert get_session_identity(session, token) is None


def test_x1_a_session_of_an_inactive_user_is_refused(session: Session) -> None:
    user = make_user(session, "a@x.org")
    token = create_session(session, user, Role.ADMIN)
    assert get_session_identity(session, token) is not None
    user.is_active = False
    session.add(user)
    session.commit()
    assert get_session_identity(session, token) is None


def test_l3_five_wrong_codes_kill_the_code(session: Session) -> None:
    user = make_user(session, "a@x.org")
    code = issue_code(session, KEY, user)
    wrong = "000000" if code != "000000" else "111111"
    for attempt in [wrong, wrong, "12", "abcdef", wrong]:  # malformed codes count too
        assert verify_code(session, KEY, "a@x.org", attempt) is None
    assert verify_code(session, KEY, "a@x.org", code) is None
    [row] = codes(session)
    assert row.attempts == 5
    assert row.used_at is None


def test_r1_five_requests_per_address(session: Session) -> None:
    now = utc_now()
    for i in range(5):
        assert allow_code_request(session, KEY, "e@x.org", f"client-{i}", now=now)
    assert not allow_code_request(session, KEY, "e@x.org", "client-new", now=now)
    assert hits(session, BUCKET_CODE_EMAIL) == 5


def test_r2_twenty_requests_per_client(session: Session) -> None:
    now = utc_now()
    for i in range(20):
        assert allow_code_request(session, KEY, f"user{i}@x.org", "c", now=now)
    assert not allow_code_request(session, KEY, "user20@x.org", "c", now=now)
    assert hits(session, BUCKET_CODE_CLIENT) == 20


def test_r3_the_window_slides(session: Session) -> None:
    t = utc_now()
    for _ in range(5):
        allow_code_request(session, KEY, "e@x.org", "c", now=t)
    assert not allow_code_request(session, KEY, "e@x.org", "c", now=t + timedelta(minutes=59))
    assert allow_code_request(session, KEY, "e@x.org", "c", now=t + timedelta(minutes=61))


def test_r4_the_limit_is_in_the_database(session: Session, engine: Engine) -> None:
    now = utc_now()
    for _ in range(5):
        allow_code_request(session, KEY, "e@x.org", "c", now=now)
    with Session(engine) as fresh:
        assert not allow_code_request(fresh, KEY, "e@x.org", "c", now=now)


def hits(session: Session, bucket: str) -> int:
    session.expire_all()
    statement = select(func.count()).select_from(RateLimitHit).where(RateLimitHit.bucket == bucket)
    return session.exec(statement).one()


# ---------------------------------------------------------------------------------------------
# Roles and the current role (milestone 5)
# ---------------------------------------------------------------------------------------------


def stored_role(session: Session, token: str) -> str | None:
    session.expire_all()
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    return row.one().current_role


def test_a_single_role_starts_in_that_role(session: Session) -> None:
    """FR-012."""
    user = make_user(session, "t@example.org", roles=(Role.TEACHER,))
    token, current = start_session(session, user)
    assert current == Role.TEACHER
    assert stored_role(session, token) == "teacher"


@pytest.mark.parametrize(
    "roles", [(Role.TEACHER, Role.STUDENT), (Role.ADMIN, Role.TEACHER, Role.STUDENT)]
)
def test_several_roles_start_with_none_chosen(session: Session, roles: tuple[Role, ...]) -> None:
    """FR-013."""
    user = make_user(session, "m@example.org", roles=roles)
    token, current = start_session(session, user)
    assert current is None
    assert stored_role(session, token) is None


def test_get_roles_uses_the_fixed_order(session: Session) -> None:
    user = make_user(session, "m@example.org", roles=(Role.STUDENT, Role.ADMIN, Role.TEACHER))
    assert user.id is not None
    assert get_roles(session, user.id) == (Role.ADMIN, Role.TEACHER, Role.STUDENT)
    nobody = make_user(session, "n@example.org", roles=())
    assert nobody.id is not None
    assert get_roles(session, nobody.id) == ()


def test_set_current_role_changes_only_that_session(session: Session) -> None:
    """FR-011: each browser has its own current role."""
    user = make_user(session, "m@example.org", roles=(Role.ADMIN, Role.STUDENT))
    laptop = create_session(session, user, Role.ADMIN)
    phone = create_session(session, user, Role.ADMIN)
    set_current_role(session, laptop, Role.STUDENT)
    assert stored_role(session, laptop) == "student"
    assert stored_role(session, phone) == "admin"
