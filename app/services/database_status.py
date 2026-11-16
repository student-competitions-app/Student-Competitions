"""The database status line: which engine, which schema revision, how many starts.

It makes persistence observable to anyone: the boot count rises by exactly one per application
start and never per page view, so a number that went up across a redeploy while the questions
stayed put proves the data survived (FR-025, FR-027, FR-028). See
specs/003-database-questions/data-model.md#4-databasestatus--the-status-line-view.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.migrations import current_revision
from app.models import BootCounter

logger = logging.getLogger(__name__)

DISPLAY_NAMES = {"sqlite": "SQLite", "postgresql": "PostgreSQL"}


@dataclass(frozen=True)
class DatabaseStatus:
    engine: str
    """SQLAlchemy's dialect name, `sqlite` or `postgresql`: the machine-readable value."""
    revision: str | None
    boots: int

    @property
    def display_name(self) -> str:
        return DISPLAY_NAMES.get(self.engine, self.engine)


def record_boot(session: Session) -> int:
    """Count one application start and return the new total. Called once, from `lifespan`.

    One `UPDATE … SET boots = boots + 1` evaluated by the database, never a read-modify-write
    here, so starts that overlap during a deploy each count (FR-028). A counter row that is
    missing is a broken database, and fails the start.
    """
    result = session.execute(
        update(BootCounter).where(BootCounter.id == 1).values(boots=BootCounter.boots + 1)
    )
    if result.rowcount != 1:
        raise RuntimeError(f"boot_counter update touched {result.rowcount} rows, expected 1")
    session.commit()
    counter = session.get(BootCounter, 1)
    assert counter is not None
    return counter.boots


def read_database_status(session: Session) -> DatabaseStatus:
    """Read the status line's three values. Read-only: a page view never changes the count."""
    counter = session.get(BootCounter, 1)
    return DatabaseStatus(
        engine=session.get_bind().dialect.name,
        revision=current_revision(session.connection()),
        boots=counter.boots if counter is not None else 0,
    )


def read_database_status_or_none(session: Session) -> DatabaseStatus | None:
    """Read the status line, or log and return `None` when the database cannot be read.

    The line never fails the page that shows it: the home page and every administrator page
    render without it instead (specs/012.6-role-landing-area FR-013). The error is logged by type
    and message only, never with the database URL (milestone 3 FR-026). Any other exception is a
    bug and still propagates.
    """
    try:
        return read_database_status(session)
    except SQLAlchemyError as exc:
        logger.error("Database status unavailable: %s: %s", type(exc).__name__, exc)
        return None
