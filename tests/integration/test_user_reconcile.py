"""People and their roles come from the three role lists, reconciled on every start.

See specs/005-roles-authorization/contracts/auth-services.md#appservicesuserspy (rows S1–S11) and
research D8. Every case runs on both engines, except the truly concurrent start, which needs two
independent PostgreSQL connections; on SQLite the same conflict is staged step by step.
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
from app.core.config import resolve_auth_settings
from app.core.db import create_db_engine, utc_now
from app.core.security import SESSION_COOKIE_NAME, hash_token
from app.main import app
from app.models import LoginCode, Role, User, UserRole, UserSession
from app.services.login import issue_code
from app.services.sessions import create_session
from app.services.users import ReconcileResult, get_roles, reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    CAST_ADMIN_EMAILS,
    CAST_STUDENT_EMAILS,
    CAST_TEACHER_EMAILS,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    TEACHER_STUDENT_EMAIL,
    sign_in_directly,
)

A = "a@example.com"
T = "t@example.com"
S = "s@example.com"
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


def s1_lists() -> dict[Role, list[str]]:
    return {ADMIN: [A], TEACHER: [T], STUDENT: [A, S]}


def test_s1_listed_addresses_become_active_people_with_their_roles(session: Session) -> None:
    assert reconcile_users(session, s1_lists()) == result(created=3, roles_added=4)
    found = all_users(session)
    assert set(found) == {A, T, S}
    assert all(user.is_active for user in found.values())
    assert all(user.legacy_role is None for user in found.values())
    assert roles_of(session, A) == (ADMIN, STUDENT)
    assert roles_of(session, T) == (TEACHER,)
    assert roles_of(session, S) == (STUDENT,)


def test_s2_a_second_run_changes_nothing(session: Session) -> None:
    """FR-006, SC-007: not even `updated_at`, and no session ends."""
    reconcile_users(session, s1_lists())
    for email in (A, T, S):
        create_session(session, all_users(session)[email], None)
    before = {email: user.updated_at for email, user in all_users(session).items()}
    later = utc_now() + timedelta(minutes=5)
    assert reconcile_users(session, s1_lists(), now=later) == result(unchanged=3)
    after = {email: user.updated_at for email, user in all_users(session).items()}
    assert after == before
    assert count(session, UserSession) == 3


def test_s3_losing_one_role_ends_every_session(session: Session) -> None:
    """FR-005, US2-4: logged out everywhere, though the person keeps a role; codes are kept."""
    reconcile_users(session, {ADMIN: [A], STUDENT: [A]})
    a = all_users(session)[A]
    create_session(session, a, ADMIN)
    create_session(session, a, STUDENT)
    issue_code(session, KEY, a)
    later = utc_now() + timedelta(minutes=5)

    assert reconcile_users(session, {ADMIN: [A], STUDENT: []}, now=later) == result(roles_removed=1)

    assert roles_of(session, A) == (ADMIN,)
    assert all_users(session)[A].is_active is True
    assert all_users(session)[A].updated_at == later
    assert count(session, UserSession) == 0
    assert count(session, LoginCode) == 1


def test_s4_gaining_a_role_keeps_the_sessions(session: Session) -> None:
    """US2-6."""
    reconcile_users(session, {TEACHER: [T]})
    create_session(session, all_users(session)[T], TEACHER)
    assert reconcile_users(session, {TEACHER: [T], STUDENT: [T]}) == result(roles_added=1)
    assert roles_of(session, T) == (TEACHER, STUDENT)
    assert sessions_of(session, T) == 1


def test_s5_on_no_list_deactivates_and_removes_everything_but_the_row(session: Session) -> None:
    """FR-005, FR-008, US2-5."""
    reconcile_users(session, {STUDENT: [S]})
    s = all_users(session)[S]
    create_session(session, s, STUDENT)
    issue_code(session, KEY, s)

    assert reconcile_users(session, {}) == result(deactivated=1, roles_removed=1)

    found = all_users(session)
    assert set(found) == {S}
    assert found[S].is_active is False
    assert roles_of(session, S) == ()
    assert count(session, UserSession) == 0
    assert count(session, LoginCode) == 0


def test_s6_a_relisted_person_is_reactivated(session: Session) -> None:
    """US2-7."""
    reconcile_users(session, {STUDENT: [S]})
    reconcile_users(session, {})
    assert reconcile_users(session, {STUDENT: [S]}) == result(reactivated=1, roles_added=1)
    assert all_users(session)[S].is_active is True
    assert roles_of(session, S) == (STUDENT,)


def test_s7_one_address_on_two_lists_is_one_person(session: Session) -> None:
    """US2-2, edge case: spelling variants on different lists, normalised by the settings."""
    settings = resolve_auth_settings(
        {"ADMIN_EMAILS": " X@Example.com ", "STUDENT_EMAILS": "x@example.com"}
    )
    role_lists = {ADMIN: settings.admin_emails, STUDENT: settings.student_emails}
    assert reconcile_users(session, role_lists) == result(created=1, roles_added=2)
    assert list(all_users(session)) == ["x@example.com"]
    assert roles_of(session, "x@example.com") == (ADMIN, STUDENT)


def test_s8_a_migrated_administrator_is_unchanged(session: Session) -> None:
    """A milestone 4 administrator, as the migration leaves them: the old column and one row."""
    now = utc_now()
    user = User(email=A, legacy_role="admin", is_active=True, created_at=now, updated_at=now)
    session.add(user)
    session.commit()
    assert user.id is not None
    session.add(UserRole(user_id=user.id, role=ADMIN, created_at=now))
    session.commit()
    assert reconcile_users(session, {ADMIN: [A]}) == result(unchanged=1)
    assert roles_of(session, A) == (ADMIN,)


def test_s11_empty_lists_deactivate_everyone(session: Session) -> None:
    reconcile_users(session, s1_lists())
    assert reconcile_users(session, {ADMIN: [], TEACHER: [], STUDENT: []}) == result(
        deactivated=3, roles_removed=4
    )
    assert not any(user.is_active for user in all_users(session).values())
    assert count(session, UserRole) == 0


def test_users_are_never_deleted(session: Session) -> None:
    reconcile_users(session, s1_lists())
    reconcile_users(session, {})
    assert set(all_users(session)) == {A, T, S}


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
                reconcile_users(other, s1_lists())
        return found

    monkeypatch.setattr(users, "_all_users", read_then_interfere)
    try:
        reconciled = main.reconcile_users_with_retry(engine, s1_lists())
    finally:
        other_engine.dispose()

    assert interfered
    assert reconciled == result(unchanged=3)
    with Session(engine) as check:
        assert sorted(all_users(check)) == sorted([A, T, S])
        assert roles_of(check, A) == (ADMIN, STUDENT)
        assert count(check, UserRole) == 4


def test_s10_concurrent_starts_on_postgresql(
    database_url: str, request: pytest.FixtureRequest
) -> None:
    """Two independent connections reconcile the same new lists at the same moment."""
    if request.node.callspec.params["database_url"] != "postgresql":
        pytest.skip("true concurrency needs two server connections; staged above for SQLite")
    engines = [create_db_engine(database_url) for _ in range(2)]
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def start(engine: Engine) -> None:
        try:
            barrier.wait()
            main.reconcile_users_with_retry(engine, s1_lists())
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
            assert sorted(all_users(check)) == sorted([A, T, S])
            assert count(check, User) == 3
            assert count(check, UserRole) == 4
    finally:
        for engine in engines:
            engine.dispose()


# ---------------------------------------------------------------------------------------------
# At startup
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def start(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Iterator[Any]:
    """Start the application against `database_url` with the given role lists. Each call is a
    fresh start (a restart) against the same database."""
    monkeypatch.setenv("DATABASE_URL", database_url)

    def starter(admins: str = "", teachers: str = "", students: str = "") -> TestClient:
        monkeypatch.setenv("ADMIN_EMAILS", admins)
        monkeypatch.setenv("TEACHER_EMAILS", teachers)
        monkeypatch.setenv("STUDENT_EMAILS", students)
        return TestClient(app)

    yield starter


def test_startup_logs_counts_only(start: Any, caplog: pytest.LogCaptureFixture) -> None:
    """FR-007, SC-008."""
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), start(A, T, f"{A},{S}"):
        pass
    lines = [r.getMessage() for r in caplog.records if "reconciled" in r.getMessage()]
    assert lines == [
        "Users reconciled: 3 created, 0 reactivated, 0 deactivated, 4 roles added, "
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
# End to end across restarts (user story 2)
# ---------------------------------------------------------------------------------------------

CAST = (CAST_ADMIN_EMAILS, CAST_TEACHER_EMAILS, CAST_STUDENT_EMAILS)
"""The three lists the shared fixtures start with."""


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


def stored_roles(session: Session) -> dict[str, tuple[Role, ...]]:
    return {email: roles_of(session, email) for email in all_users(session)}


def test_us2_1_us2_2_the_cast_holds_exactly_its_roles(start: Any, session: Session) -> None:
    with start(*CAST):
        pass
    assert stored_roles(session) == {
        ADMIN_EMAIL: (ADMIN,),
        TEACHER_EMAIL: (TEACHER,),
        STUDENT_EMAIL: (STUDENT,),
        ADMIN_STUDENT_EMAIL: (ADMIN, STUDENT),
        TEACHER_STUDENT_EMAIL: (TEACHER, STUDENT),
    }
    assert all(user.is_active for user in all_users(session).values())


def test_us2_3_a_restart_with_the_same_lists_changes_nothing(start: Any, session: Session) -> None:
    with start(*CAST):
        browser = signed_in_client(TEACHER_EMAIL)
        cookie = browser.cookies[SESSION_COOKIE_NAME]
    before = {email: user.updated_at for email, user in all_users(session).items()}
    with start(*CAST):
        browser = TestClient(app)
        browser.cookies.set(SESSION_COOKIE_NAME, cookie)
        assert browser.get("/", follow_redirects=False).status_code == 200
    assert {email: user.updated_at for email, user in all_users(session).items()} == before


def test_us2_4_losing_a_role_logs_out_everywhere(start: Any, session: Session) -> None:
    """FR-005: both browsers, though the person keeps the administrator role."""
    with start(*CAST):
        laptop = signed_in_client(ADMIN_STUDENT_EMAIL)
        phone = signed_in_client(ADMIN_STUDENT_EMAIL)
        cookies = [laptop.cookies[SESSION_COOKIE_NAME], phone.cookies[SESSION_COOKIE_NAME]]
    students = without(CAST_STUDENT_EMAILS, ADMIN_STUDENT_EMAIL)
    with start(CAST_ADMIN_EMAILS, CAST_TEACHER_EMAILS, students):
        for cookie in cookies:
            browser = TestClient(app)
            browser.cookies.set(SESSION_COOKIE_NAME, cookie)
            assert returns_to_login(browser)
        again = TestClient(app)
        assert sign_in_by_email(again, ADMIN_STUDENT_EMAIL) == 303
        token = again.cookies[SESSION_COOKIE_NAME].split(".")[0]
    assert roles_of(session, ADMIN_STUDENT_EMAIL) == (ADMIN,)
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert row.one().current_role == "admin"


def test_us2_5_on_no_list_means_no_session_and_no_code(start: Any, session: Session) -> None:
    """FR-010: the response is the same as for anyone, and nothing is sent."""
    with start(*CAST):
        cookie = signed_in_client(STUDENT_EMAIL).cookies[SESSION_COOKIE_NAME]
    with start(CAST_ADMIN_EMAILS, CAST_TEACHER_EMAILS, without(CAST_STUDENT_EMAILS, STUDENT_EMAIL)):
        browser = TestClient(app)
        browser.cookies.set(SESSION_COOKIE_NAME, cookie)
        assert returns_to_login(browser)
        removed = browser.post("/login", data={"email": STUDENT_EMAIL})
        assert removed.status_code == 200
        assert "we have sent a code" in removed.text
        assert app.state.email_sender.outbox == []
    assert sessions_of(session, STUDENT_EMAIL) == 0
    assert all_users(session)[STUDENT_EMAIL].is_active is False


def test_us2_6_gaining_a_role_keeps_the_session(start: Any, session: Session) -> None:
    with start(*CAST):
        browser = signed_in_client(TEACHER_EMAIL)
        cookie = browser.cookies[SESSION_COOKIE_NAME]
    with start(CAST_ADMIN_EMAILS, CAST_TEACHER_EMAILS, f"{CAST_STUDENT_EMAILS},{TEACHER_EMAIL}"):
        browser = TestClient(app)
        browser.cookies.set(SESSION_COOKIE_NAME, cookie)
        assert browser.get("/teacher", follow_redirects=False).status_code == 200
    assert roles_of(session, TEACHER_EMAIL) == (TEACHER, STUDENT)
    token = cookie.split(".")[0]
    row = session.exec(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    assert row.one().current_role == "teacher"


def test_us2_7_a_re_added_person_can_sign_in_again(start: Any) -> None:
    students = without(CAST_STUDENT_EMAILS, STUDENT_EMAIL)
    with start(CAST_ADMIN_EMAILS, CAST_TEACHER_EMAILS, students):
        pass
    with start(*CAST):
        browser = TestClient(app)
        assert sign_in_by_email(browser, STUDENT_EMAIL) == 303
        assert browser.get("/student", follow_redirects=False).status_code == 200


def test_us2_8_restarts_log_counts_only(start: Any, caplog: pytest.LogCaptureFixture) -> None:
    """SC-006, SC-008."""
    with start(*CAST):
        pass
    students = without(CAST_STUDENT_EMAILS, ADMIN_STUDENT_EMAIL)
    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        start(CAST_ADMIN_EMAILS, CAST_TEACHER_EMAILS, students),
    ):
        pass
    lines = [r.getMessage() for r in caplog.records if "reconciled" in r.getMessage()]
    assert lines == [
        "Users reconciled: 0 created, 0 reactivated, 0 deactivated, 0 roles added, "
        "1 roles removed, 4 unchanged"
    ]
    for record in caplog.records:
        assert "@" not in record.getMessage()
