"""The administrators come from `ADMIN_EMAILS`, reconciled on every start; no other role is touched.

See specs/008-teacher-management-consent/contracts/services.md#appservicesuserspy-changed and
research D16, which narrow specs/005-roles-authorization/contracts/auth-services.md (rows
S1–S11) to the administrator role. Every case runs on both engines, except the truly concurrent
start, which needs two independent PostgreSQL connections; on SQLite the same conflict is staged
step by step.
"""

import logging
import re
import threading
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func
from sqlmodel import Session, select

import app.main as main
import app.services.users as users
from app.core.config import AuthSettings, resolve_auth_settings
from app.core.db import create_db_engine, utc_now
from app.core.security import SESSION_COOKIE_NAME, hash_token
from app.main import app
from app.models import AccessLevel, LoginCode, Role, User, UserRole, UserSession
from app.services.login import issue_code
from app.services.sessions import create_session
from app.services.teachers import list_teachers
from app.services.users import ReconcileResult, get_roles, reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    CAST_ADMIN_EMAILS,
    CAST_SEEDED_ROLES,
    invite_and_accept,
    make_institution,
    seed_roles_directly,
    sign_in_directly,
)

A = "a@example.com"
B = "b@example.com"
T = "t@example.com"
KEY = "k" * 32

ADMIN, TEACHER, STUDENT = Role.ADMIN, Role.TEACHER, Role.STUDENT


def result(**counts: int) -> ReconcileResult:
    """A `ReconcileResult` with every count not given at zero."""
    fields = ("created", "reactivated", "deactivated", "roles_added", "roles_removed", "unchanged")
    return ReconcileResult(**{name: counts.get(name, 0) for name in fields})


def all_users(session: Session) -> dict[str, User]:
    session.expire_all()
    return {user.email: user for user in session.exec(select(User))}


def roles_of(session: Session, email: str) -> tuple[Role, ...]:
    user = all_users(session)[email]
    assert user.id is not None
    return get_roles(session, user.id)


def count(session: Session, model: type[Any]) -> int:
    session.expire_all()
    return session.exec(select(func.count()).select_from(model)).one()


def sessions_of(session: Session, email: str) -> int:
    user = all_users(session)[email]
    statement = select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)
    return session.exec(statement).one()


def seed(session: Session, email: str, *roles: Role, active: bool = True) -> User:
    """A user holding `roles`, written directly: how a consent teacher or a cast student looks to
    the reconcile, which never writes those roles itself."""
    now = utc_now()
    user = User(email=email, is_active=active, created_at=now, updated_at=now)
    session.add(user)
    session.flush()
    assert user.id is not None
    for role in roles:
        session.add(UserRole(user_id=user.id, role=role, created_at=now))
    session.commit()
    session.refresh(user)
    return user


def non_admin_rows(session: Session) -> list[tuple[int, str]]:
    session.expire_all()
    rows = session.exec(select(UserRole).where(UserRole.role != ADMIN))
    return sorted((row.user_id, row.role) for row in rows)


def test_s1_listed_addresses_become_active_administrators(session: Session) -> None:
    assert reconcile_users(session, [A, B]) == result(created=2, roles_added=2)
    found = all_users(session)
    assert set(found) == {A, B}
    assert all(user.is_active for user in found.values())
    assert roles_of(session, A) == (ADMIN,)
    assert roles_of(session, B) == (ADMIN,)


def test_s2_a_second_run_changes_nothing(session: Session) -> None:
    """FR-006, SC-007: not even `updated_at`, and no session ends."""
    seed(session, T, TEACHER)
    reconcile_users(session, [A, B])
    for email in (A, B, T):
        create_session(session, all_users(session)[email], None)
    before = {email: user.updated_at for email, user in all_users(session).items()}
    later = utc_now() + timedelta(minutes=5)
    assert reconcile_users(session, [A, B], now=later) == result(unchanged=3)
    after = {email: user.updated_at for email, user in all_users(session).items()}
    assert after == before
    assert count(session, UserSession) == 3


def test_s3_losing_admin_keeps_a_teacher_active_and_ends_every_session(session: Session) -> None:
    """FR-057, US7-3: the teacher role stays, and the person is signed out everywhere; codes are
    kept."""
    seed(session, A, ADMIN, TEACHER)
    a = all_users(session)[A]
    create_session(session, a, ADMIN)
    create_session(session, a, TEACHER)
    issue_code(session, KEY, a)
    later = utc_now() + timedelta(minutes=5)

    assert reconcile_users(session, [], now=later) == result(roles_removed=1)

    assert roles_of(session, A) == (TEACHER,)
    assert all_users(session)[A].is_active is True
    assert all_users(session)[A].updated_at == later
    assert count(session, UserSession) == 0
    assert count(session, LoginCode) == 1


def test_s4_a_teacher_not_on_the_list_is_untouched(session: Session) -> None:
    """FR-057, US7-2: role, active flag, `updated_at` and sessions all stay."""
    teacher = seed(session, T, TEACHER)
    create_session(session, teacher, TEACHER)
    before = all_users(session)[T].updated_at

    assert reconcile_users(session, [A]) == result(created=1, roles_added=1, unchanged=1)

    assert roles_of(session, T) == (TEACHER,)
    assert all_users(session)[T].is_active is True
    assert all_users(session)[T].updated_at == before
    assert sessions_of(session, T) == 1


def test_s5_an_administrator_with_no_other_role_is_deactivated(session: Session) -> None:
    """FR-005, US2-5 of milestone 5: no role left, so no session, no code; the row stays."""
    reconcile_users(session, [A])
    a = all_users(session)[A]
    create_session(session, a, ADMIN)
    issue_code(session, KEY, a)

    assert reconcile_users(session, []) == result(deactivated=1, roles_removed=1)

    found = all_users(session)
    assert set(found) == {A}
    assert found[A].is_active is False
    assert roles_of(session, A) == ()
    assert count(session, UserSession) == 0
    assert count(session, LoginCode) == 0


def test_s6_a_relisted_person_is_reactivated(session: Session) -> None:
    reconcile_users(session, [A])
    reconcile_users(session, [])
    assert reconcile_users(session, [A]) == result(reactivated=1, roles_added=1)
    assert all_users(session)[A].is_active is True
    assert roles_of(session, A) == (ADMIN,)


def test_s7_a_teacher_gaining_admin_keeps_the_sessions(session: Session) -> None:
    teacher = seed(session, T, TEACHER)
    create_session(session, teacher, TEACHER)
    assert reconcile_users(session, [T]) == result(roles_added=1)
    assert roles_of(session, T) == (ADMIN, TEACHER)
    assert sessions_of(session, T) == 1


def test_s7_spelling_variants_are_one_person(session: Session) -> None:
    """Edge case: the settings loader normalises and de-duplicates the list."""
    settings = resolve_auth_settings({"ADMIN_EMAILS": " X@Example.com ,x@example.com"})
    assert reconcile_users(session, settings.admin_emails) == result(created=1, roles_added=1)
    assert list(all_users(session)) == ["x@example.com"]


def test_s8_a_migrated_administrator_is_unchanged(session: Session) -> None:
    """A milestone 4 administrator, as the migration leaves them: one `user_roles` row."""
    seed(session, A, ADMIN)
    assert reconcile_users(session, [A]) == result(unchanged=1)
    assert roles_of(session, A) == (ADMIN,)


def test_teacher_and_student_rows_are_never_written(session: Session) -> None:
    """FR-057: whatever the list says, the reconcile neither adds nor removes those rows."""
    seed(session, T, TEACHER, STUDENT)
    seed(session, A, ADMIN, STUDENT)
    before = non_admin_rows(session)
    for listing in ([A], [], [T], [A, T, B], []):
        reconcile_users(session, listing)
        assert non_admin_rows(session) == before


def test_users_are_never_deleted(session: Session) -> None:
    seed(session, T, TEACHER)
    reconcile_users(session, [A, B])
    reconcile_users(session, [])
    assert set(all_users(session)) == {A, B, T}


# ---------------------------------------------------------------------------------------------
# S9, S10: two instances starting at once
# ---------------------------------------------------------------------------------------------


def test_s9_a_conflicting_insert_is_retried_once(
    engine: Engine, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staged on both engines: another instance inserts the same new people and roles between
    this run's read and its write. The write fails, and the one retry reaches the S1 end state."""
    original = users._all_users
    other_engine = create_db_engine(database_url)
    interfered = False

    def read_then_interfere(session: Session) -> dict[str, User]:
        nonlocal interfered
        found = original(session)
        if not interfered:
            interfered = True
            with Session(other_engine) as other:
                reconcile_users(other, [A, B])
        return found

    monkeypatch.setattr(users, "_all_users", read_then_interfere)
    try:
        reconciled = main.reconcile_users_with_retry(engine, [A, B])
    finally:
        other_engine.dispose()

    assert interfered
    assert reconciled == result(unchanged=2)
    with Session(engine) as check:
        assert sorted(all_users(check)) == [A, B]
        assert count(check, UserRole) == 2


def test_s10_concurrent_starts_on_postgresql(
    database_url: str, request: pytest.FixtureRequest
) -> None:
    """Two independent connections reconcile the same new list at the same moment."""
    if request.node.callspec.params["database_url"] != "postgresql":
        pytest.skip("true concurrency needs two server connections; staged above for SQLite")
    engines = [create_db_engine(database_url) for _ in range(2)]
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def start(engine: Engine) -> None:
        try:
            barrier.wait()
            main.reconcile_users_with_retry(engine, [A, B])
        except BaseException as exc:  # surfaced by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=start, args=(engine,)) for engine in engines]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    try:
        assert not errors
        with Session(engines[0]) as check:
            assert sorted(all_users(check)) == [A, B]
            assert count(check, User) == 2
            assert count(check, UserRole) == 2
    finally:
        for engine in engines:
            engine.dispose()


# ---------------------------------------------------------------------------------------------
# At startup
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def start(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Iterator[Any]:
    """Start the application against `database_url` with the given administrator list. Each call
    is a fresh start (a restart) against the same database."""
    monkeypatch.setenv("DATABASE_URL", database_url)

    def starter(admins: str = "") -> TestClient:
        monkeypatch.setenv("ADMIN_EMAILS", admins)
        return TestClient(app)

    yield starter


def test_startup_logs_counts_only(start: Any, caplog: pytest.LogCaptureFixture) -> None:
    """FR-007, SC-008."""
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), start(f"{A},{B}"):
        pass
    lines = [r.getMessage() for r in caplog.records if "reconciled" in r.getMessage()]
    assert lines == [
        "Users reconciled: 2 created, 0 reactivated, 0 deactivated, 2 roles added, "
        "0 roles removed, 0 unchanged"
    ]
    for record in caplog.records:
        assert "@" not in record.getMessage()


def test_reconciliation_runs_after_the_migration_check_and_before_the_boot_count(
    start: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-038."""
    calls: list[str] = []

    def spy(name: str) -> Any:
        original = getattr(main, name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            return original(*args, **kwargs)

        return wrapper

    for name in ("ensure_at_head", "reconcile_users_with_retry", "record_boot"):
        monkeypatch.setattr(main, name, spy(name))
    with start(A):
        pass
    assert calls == ["ensure_at_head", "reconcile_users_with_retry", "record_boot"]


# ---------------------------------------------------------------------------------------------
# End to end across restarts
# ---------------------------------------------------------------------------------------------


def without(listing: str, email: str) -> str:
    return ",".join(entry for entry in listing.split(",") if entry != email)


def signed_in_client(email: str) -> TestClient:
    """A browser for the running application, signed in as `email`."""
    browser = TestClient(app)
    sign_in_directly(browser, email)
    return browser


def returns_to_login(browser: TestClient) -> bool:
    response = browser.get("/", follow_redirects=False)
    return response.status_code == 303 and response.headers["location"].startswith("/login")


def sign_in_by_email(browser: TestClient, email: str) -> int:
    """The real flow through the outbox; returns the status of the code submission."""
    browser.post("/login", data={"email": email})
    [message] = app.state.email_sender.outbox
    code = re.search(r"code is: ([0-9]{6})", message.text)
    assert code is not None
    response = browser.post(
        "/login/code", data={"email": email, "code": code.group(1)}, follow_redirects=False
    )
    return response.status_code


def seed_cast_roles() -> None:
    seed_roles_directly(app.state.engine, CAST_SEEDED_ROLES)


def test_a_restart_with_the_same_list_changes_nothing(start: Any, session: Session) -> None:
    with start(CAST_ADMIN_EMAILS):
        seed_cast_roles()
        browser = signed_in_client(ADMIN_EMAIL)
        cookie = browser.cookies[SESSION_COOKIE_NAME]
    before = {email: user.updated_at for email, user in all_users(session).items()}
    with start(CAST_ADMIN_EMAILS):
        browser = TestClient(app)
        browser.cookies.set(SESSION_COOKIE_NAME, cookie)
        assert browser.get("/", follow_redirects=False).status_code == 200
    assert {email: user.updated_at for email, user in all_users(session).items()} == before


def test_losing_admin_logs_out_everywhere_and_keeps_the_other_role(
    start: Any, session: Session
) -> None:
    """FR-005: both browsers, though the person keeps the student role."""
    with start(CAST_ADMIN_EMAILS):
        seed_cast_roles()
        laptop = signed_in_client(ADMIN_STUDENT_EMAIL)
        phone = signed_in_client(ADMIN_STUDENT_EMAIL)
        cookies = [laptop.cookies[SESSION_COOKIE_NAME], phone.cookies[SESSION_COOKIE_NAME]]
    with start(without(CAST_ADMIN_EMAILS, ADMIN_STUDENT_EMAIL)):
        for cookie in cookies:
            browser = TestClient(app)
            browser.cookies.set(SESSION_COOKIE_NAME, cookie)
            assert returns_to_login(browser)
        again = TestClient(app)
        assert sign_in_by_email(again, ADMIN_STUDENT_EMAIL) == 303
        token = again.cookies[SESSION_COOKIE_NAME].split(".")[0]
    assert roles_of(session, ADMIN_STUDENT_EMAIL) == (STUDENT,)
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert row.one().current_role == "student"


def test_an_unlisted_administrator_gets_no_session_and_no_code(
    start: Any, session: Session
) -> None:
    """FR-010: the response is the same as for anyone, and nothing is sent."""
    with start(CAST_ADMIN_EMAILS):
        cookie = signed_in_client(ADMIN_EMAIL).cookies[SESSION_COOKIE_NAME]
    with start(without(CAST_ADMIN_EMAILS, ADMIN_EMAIL)):
        browser = TestClient(app)
        browser.cookies.set(SESSION_COOKIE_NAME, cookie)
        assert returns_to_login(browser)
        removed = browser.post("/login", data={"email": ADMIN_EMAIL})
        assert removed.status_code == 200
        assert "we have sent a code" in removed.text
        assert app.state.email_sender.outbox == []
    assert sessions_of(session, ADMIN_EMAIL) == 0
    assert all_users(session)[ADMIN_EMAIL].is_active is False


def test_a_re_added_administrator_can_sign_in_again(start: Any) -> None:
    with start(without(CAST_ADMIN_EMAILS, ADMIN_EMAIL)):
        pass
    with start(CAST_ADMIN_EMAILS):
        browser = TestClient(app)
        assert sign_in_by_email(browser, ADMIN_EMAIL) == 303
        assert browser.get("/admin", follow_redirects=False).status_code == 303


def test_restarts_log_counts_only(start: Any, caplog: pytest.LogCaptureFixture) -> None:
    """SC-006, SC-008."""
    with start(CAST_ADMIN_EMAILS):
        seed_cast_roles()
    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        start(without(CAST_ADMIN_EMAILS, ADMIN_STUDENT_EMAIL)),
    ):
        pass
    lines = [r.getMessage() for r in caplog.records if "reconciled" in r.getMessage()]
    assert lines == [
        "Users reconciled: 0 created, 0 reactivated, 0 deactivated, 0 roles added, "
        "1 roles removed, 4 unchanged"
    ]
    for record in caplog.records:
        assert "@" not in record.getMessage()


# ---------------------------------------------------------------------------------------------
# Milestone 8, user story 7: real consent teachers across a reconcile
# ---------------------------------------------------------------------------------------------


def test_us7_2_a_consent_teacher_not_on_the_list_keeps_the_role(
    engine: Engine, session: Session, auth_settings: AuthSettings
) -> None:
    reconcile_users(session, [ADMIN_EMAIL])
    school = make_institution(engine, "School 5")
    teacher_id = invite_and_accept(
        engine, auth_settings, email=T, institutions={school: AccessLevel.READ}
    )
    reconcile_users(session, [ADMIN_EMAIL])
    assert roles_of(session, T) == (TEACHER,)
    assert all_users(session)[T].is_active is True
    assert user_ids_on_the_teachers_tab(session) == [teacher_id]


def test_us7_3_an_administrator_who_teaches_loses_only_admin(
    engine: Engine, session: Session, auth_settings: AuthSettings
) -> None:
    reconcile_users(session, [ADMIN_EMAIL, A])
    school = make_institution(engine, "School 5")
    teacher_id = invite_and_accept(
        engine, auth_settings, email=A, institutions={school: AccessLevel.READ}
    )
    person = all_users(session)[A]
    create_session(session, person, ADMIN)
    create_session(session, person, TEACHER)

    reconcile_users(session, [ADMIN_EMAIL])

    assert roles_of(session, A) == (TEACHER,)
    assert all_users(session)[A].is_active is True
    assert sessions_of(session, A) == 0
    assert user_ids_on_the_teachers_tab(session) == [teacher_id]


def test_a_reconcile_never_creates_a_student_row(session: Session) -> None:
    reconcile_users(session, [A, B])
    reconcile_users(session, [A])
    assert session.exec(select(UserRole).where(UserRole.role == STUDENT)).all() == []


def user_ids_on_the_teachers_tab(session: Session) -> list[int]:
    session.expire_all()
    return [view.user_id for view in list_teachers(session)]
