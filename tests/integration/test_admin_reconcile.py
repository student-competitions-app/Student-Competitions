"""Administrators come from `ADMIN_EMAILS`, reconciled on every start.

See specs/004-email-otp-auth/contracts/auth-services.md#behaviour-matrix (rows S1–S6) and
research D13. Every case runs on both engines, except the truly concurrent start, which needs
two independent PostgreSQL connections; on SQLite the same conflict is staged step by step.
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
from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.models import LoginCode, Role, User, UserSession
from app.services.login import issue_code
from app.services.sessions import create_session
from app.services.users import ReconcileResult, reconcile_admins
from tests.conftest import sign_in_directly

A = "a@example.com"
B = "b@example.com"
KEY = "k" * 32


def all_users(session: Session) -> dict[str, User]:
    session.expire_all()
    return {user.email: user for user in session.exec(select(User))}


def count(session: Session, model: type[Any]) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def test_s1_listed_addresses_become_active_admins(session: Session) -> None:
    assert reconcile_admins(session, [A, B]) == ReconcileResult(2, 0, 0, 0)
    found = all_users(session)
    assert set(found) == {A, B}
    assert all(user.is_active and user.role == Role.ADMIN for user in found.values())


def test_s2_a_second_run_changes_nothing(session: Session) -> None:
    """SC-007: not even `updated_at`."""
    reconcile_admins(session, [A, B])
    before = {email: user.updated_at for email, user in all_users(session).items()}
    later = utc_now() + timedelta(minutes=5)
    assert reconcile_admins(session, [A, B], now=later) == ReconcileResult(0, 0, 0, 2)
    after = {email: user.updated_at for email, user in all_users(session).items()}
    assert after == before


def test_s3_an_unlisted_admin_is_deactivated_and_loses_everything(session: Session) -> None:
    reconcile_admins(session, [A, B])
    a = all_users(session)[A]
    create_session(session, a)
    create_session(session, a)
    issue_code(session, KEY, a)
    later = utc_now() + timedelta(minutes=5)

    assert reconcile_admins(session, [B], now=later) == ReconcileResult(0, 0, 1, 1)

    found = all_users(session)
    assert found[A].is_active is False
    assert found[A].updated_at == later
    assert found[B].is_active is True
    assert count(session, UserSession) == 0
    assert count(session, LoginCode) == 0


def test_s4_a_relisted_admin_is_reactivated(session: Session) -> None:
    reconcile_admins(session, [A, B])
    reconcile_admins(session, [B])
    assert reconcile_admins(session, [A, B]) == ReconcileResult(0, 1, 0, 1)
    assert all_users(session)[A].is_active is True


def test_s5_spelling_variants_are_one_user(session: Session) -> None:
    settings = resolve_auth_settings({"ADMIN_EMAILS": " A@X.org ,a@x.org"})
    reconcile_admins(session, settings.admin_emails)
    assert list(all_users(session)) == ["a@x.org"]


def test_an_empty_list_deactivates_everyone(session: Session) -> None:
    reconcile_admins(session, [A, B])
    assert reconcile_admins(session, []) == ReconcileResult(0, 0, 2, 0)
    assert not any(user.is_active for user in all_users(session).values())


def test_users_are_never_deleted(session: Session) -> None:
    reconcile_admins(session, [A, B])
    reconcile_admins(session, [])
    assert set(all_users(session)) == {A, B}


# ---------------------------------------------------------------------------------------------
# S6: two instances starting at once
# ---------------------------------------------------------------------------------------------


def test_s6_a_conflicting_insert_is_retried_once(
    engine: Engine, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staged on both engines: another instance inserts the same new address between this
    run's read and its commit. The commit fails, and the one retry reaches the same end state."""
    original = users._users_by_email
    other_engine = create_db_engine(database_url)
    interfered = False

    def read_then_interfere(session: Session, emails: set[str]) -> dict[str, User]:
        nonlocal interfered
        found = original(session, emails)
        if not interfered:
            interfered = True
            with Session(other_engine) as other:
                reconcile_admins(other, [A])
        return found

    monkeypatch.setattr(users, "_users_by_email", read_then_interfere)
    try:
        result = main.reconcile_admins_with_retry(engine, (A,))
    finally:
        other_engine.dispose()

    assert interfered
    assert result == ReconcileResult(0, 0, 0, 1)
    with Session(engine) as check:
        assert list(all_users(check)) == [A]


def test_s6_concurrent_starts_on_postgresql(
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
            main.reconcile_admins_with_retry(engine, (A, B))
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
    finally:
        for engine in engines:
            engine.dispose()


# ---------------------------------------------------------------------------------------------
# At startup
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def start(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Iterator[Any]:
    """Start the application against `database_url` with the given `ADMIN_EMAILS`."""
    monkeypatch.setenv("DATABASE_URL", database_url)

    def starter(admin_emails: str) -> TestClient:
        monkeypatch.setenv("ADMIN_EMAILS", admin_emails)
        return TestClient(app)

    yield starter


def test_startup_logs_counts_only(start: Any, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"), start(f"{A},{B}"):
        pass
    lines = [
        r.getMessage() for r in caplog.records if "Administrators reconciled" in r.getMessage()
    ]
    assert lines == [
        "Administrators reconciled: 2 created, 0 reactivated, 0 deactivated, 0 unchanged"
    ]
    for record in caplog.records:
        assert "@" not in record.getMessage()


def test_reconciliation_runs_after_the_migration_check_and_before_the_boot_count(
    start: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def spy(name: str) -> Any:
        original = getattr(main, name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            return original(*args, **kwargs)

        return wrapper

    for name in ("ensure_at_head", "reconcile_admins_with_retry", "record_boot"):
        monkeypatch.setattr(main, name, spy(name))
    with start(A):
        pass
    assert calls == ["ensure_at_head", "reconcile_admins_with_retry", "record_boot"]


def test_a_removed_admin_loses_access_on_the_next_start(start: Any) -> None:
    """FR-045, US3-3/4/5: removed from the list, a restart ends their session and no code is
    sent to them any more; listed again, they can sign in again."""
    with start(f"{A},{B}") as first:
        sign_in_directly(first, B)
        cookie = first.cookies[SESSION_COOKIE_NAME]
        assert first.get("/", follow_redirects=False).status_code == 200

    with start(A) as second:
        second.cookies.set(SESSION_COOKIE_NAME, cookie)
        response = second.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login?next=%2F"

        removed = second.post("/login", data={"email": B})
        known = second.post("/login", data={"email": A})
        assert removed.status_code == known.status_code == 200
        assert removed.text.replace(B, "X") == known.text.replace(A, "X")
        assert [message.to for message in app.state.email_sender.outbox] == [A]

    with start(f"{A},{B}") as third:
        third.post("/login", data={"email": B})
        [message] = app.state.email_sender.outbox
        code = re.search(r"code is: ([0-9]{6})", message.text)
        assert code is not None
        response = third.post(
            "/login/code", data={"email": B, "code": code.group(1)}, follow_redirects=False
        )
        assert response.status_code == 303
