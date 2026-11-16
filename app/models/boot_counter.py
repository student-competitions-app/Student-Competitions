"""The `boot_counter` table: how many times the application has started against this database.

It makes persistence observable: the database status line shows the count (in the footer of the
administrator area and of the student's home page since milestone 12.6), and it rises by exactly
one per start and never per page view (FR-027, FR-028). See
specs/003-database-questions/data-model.md#2-bootcounter--table-boot_counter.
"""

from sqlalchemy import BigInteger, CheckConstraint, Column
from sqlmodel import Field, SQLModel

# Imported for its side effect: the constraint naming convention must be on the metadata before
# this table is defined, or its constraints would get different names on each engine.
import app.core.db  # noqa: F401


class BootCounter(SQLModel, table=True):
    __tablename__ = "boot_counter"
    # A single row, always id 1: the first migration inserts it and nothing can add a second.
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: int = Field(primary_key=True, sa_column_kwargs={"autoincrement": False})
    boots: int = Field(sa_column=Column(BigInteger(), nullable=False))
    """Starts at 0; only ever incremented, atomically, by `record_boot`."""
