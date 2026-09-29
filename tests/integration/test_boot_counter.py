"""The boot counter: +1 per application start, never per page view, never a lost increment.

See specs/003-database-questions/contracts/question-service.md (behaviour matrix rows 14–16) and
research D7. Every case runs on both engines. The page is private since milestone 4, so it is
read signed in.
"""

import re
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from app.core.security import SESSION_COOKIE_NAME
from app.main import app
from app.services.database_status import read_database_status, record_boot
from tests.conftest import ADMIN_EMAIL, sign_in_directly

THREADS = 8


def _boots(body: str) -> str:
    match = re.search(r'data-boots="(\d+)"', body)
    assert match is not None, "the page has no data-boots attribute"
    return match.group(1)


def test_record_boot_counts_up_from_zero(session: Session) -> None:
    assert read_database_status(session).boots == 0
    assert record_boot(session) == 1
    assert record_boot(session) == 2


def test_concurrent_boots_are_all_counted(engine: Engine) -> None:
    """Overlapping starts, each on its own session, all count (FR-028)."""
    barrier = threading.Barrier(THREADS)
    errors: list[BaseException] = []

    def boot() -> None:
        try:
            with Session(engine) as own_session:
                barrier.wait()
                record_boot(own_session)
        except BaseException as exc:  # surfaced by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=boot) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    with Session(engine) as check:
        assert read_database_status(check).boots == THREADS


def test_reading_the_status_does_not_count(session: Session) -> None:
    assert read_database_status(session).boots == read_database_status(session).boots


def test_the_page_shows_the_first_start(admin_client: TestClient) -> None:
    assert _boots(admin_client.get("/").text) == "1"


def test_page_views_do_not_count(admin_client: TestClient) -> None:
    """US2-4: reloading the page leaves the number where it was."""
    for _ in range(3):
        body = admin_client.get("/").text
    assert _boots(body) == "1"


def test_a_restart_counts(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    """US2-2, FR-027: a second start against the same database shows the next number. The
    session from the first start still works after the restart: it is stored server-side."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)
    with TestClient(app) as first:
        sign_in_directly(first, ADMIN_EMAIL)
        cookie = first.cookies[SESSION_COOKIE_NAME]
        assert _boots(first.get("/").text) == "1"
    with TestClient(app) as second:
        second.cookies.set(SESSION_COOKIE_NAME, cookie)
        assert _boots(second.get("/").text) == "2"
