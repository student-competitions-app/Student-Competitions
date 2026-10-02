"""The subject operations on SQLite and on PostgreSQL.

See specs/006-admin-area/contracts/subject-service.md. Every test runs once per engine through
the `session` fixture, so the case-insensitive uniqueness and the order are proven on both.
"""

import logging
from collections.abc import Callable

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

import app.services.subjects
from app.core.db import utc_now
from app.models import Subject
from app.schemas.subject import SubjectNameError, subject_name_key
from app.services.subjects import (
    DuplicateSubjectName,
    SubjectInUse,
    SubjectNotFound,
    count_subject_uses,
    create_subject,
    delete_subject,
    get_subject,
    list_subjects,
    rename_subject,
    set_subject_active,
)

MISSING = 999


def names(session: Session) -> list[str]:
    return [subject.name for subject in list_subjects(session)]


def row(session: Session, subject_id: int) -> tuple[object, ...]:
    session.expire_all()
    subject = get_subject(session, subject_id)
    return (subject.name, subject.name_key, subject.is_active, subject.updated_at)


# ---------------------------------------------------------------------------------------------
# Create and list
# ---------------------------------------------------------------------------------------------


def test_create_stores_the_trimmed_name_its_key_and_active(session: Session) -> None:
    subject = create_subject(session, "  Computer Science  ")
    assert subject.id is not None
    stored = get_subject(session, subject.id)
    assert stored.name == "Computer Science"
    assert stored.name_key == "computer science"
    assert stored.is_active is True
    assert stored.created_at == stored.updated_at


def test_the_list_starts_empty(session: Session) -> None:
    assert list_subjects(session) == []


@pytest.mark.parametrize(
    ("first", "second", "stored"),
    [("Physics", "PHYSICS", "Physics"), ("Фізика", "ФІЗИКА", "Фізика"), ("ß", "SS", "ß")],
    ids=["latin", "cyrillic", "sharp-s"],
)
def test_create_refuses_a_name_differing_only_in_case(
    session: Session, first: str, second: str, stored: str
) -> None:
    create_subject(session, first)
    with pytest.raises(DuplicateSubjectName) as caught:
        create_subject(session, second)
    assert caught.value.existing_name == stored
    assert caught.value.message == f"A subject named “{stored}” already exists."
    assert names(session) == [stored]


def test_create_refuses_the_name_of_an_inactive_subject(session: Session) -> None:
    physics = create_subject(session, "Physics")
    set_subject_active(session, physics.id, False)
    with pytest.raises(DuplicateSubjectName):
        create_subject(session, "physics")


@pytest.mark.parametrize("raw", ["", "   ", "a" * 201, "Math\tematics"])
def test_create_refuses_an_invalid_name(session: Session, raw: str) -> None:
    with pytest.raises(SubjectNameError):
        create_subject(session, raw)
    assert list_subjects(session) == []


def test_the_list_ignores_case(session: Session) -> None:
    for name in ("Physics", "chemistry", "Mathematics"):
        create_subject(session, name)
    assert names(session) == ["chemistry", "Mathematics", "Physics"]


def test_the_list_includes_inactive_subjects(session: Session) -> None:
    create_subject(session, "Physics")
    biology = create_subject(session, "Biology")
    set_subject_active(session, biology.id, False)
    assert [(s.name, s.is_active) for s in list_subjects(session)] == [
        ("Biology", False),
        ("Physics", True),
    ]


def test_ties_on_the_key_are_broken_by_id(session: Session) -> None:
    """Equal keys cannot be stored; the sort key still ends in the id, so the order is total."""
    create_subject(session, "Algebra")
    create_subject(session, "Geometry")
    subjects = list_subjects(session)
    assert [s.id for s in subjects] == sorted(s.id for s in subjects)


def test_the_unique_constraint_refuses_a_direct_duplicate(session: Session) -> None:
    """The guarantee against simultaneous submissions is the constraint, not the pre-check."""
    create_subject(session, "Physics")
    now = utc_now()
    session.add(
        Subject(
            name="PHYSICS", name_key=subject_name_key("PHYSICS"), created_at=now, updated_at=now
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_concurrent_create_becomes_a_duplicate_error(
    session: Session, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rival inserts the same name between the pre-check and the commit."""
    real_find = app.services.subjects._find_by_key
    calls = 0

    def find_then_race(db: Session, key: str) -> Subject | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            found = real_find(db, key)
            with Session(engine) as rival:
                create_subject(rival, "PHYSICS")
            return found
        return real_find(db, key)

    monkeypatch.setattr(app.services.subjects, "_find_by_key", find_then_race)
    with pytest.raises(DuplicateSubjectName) as caught:
        create_subject(session, "Physics")
    assert caught.value.existing_name == "PHYSICS"
    assert names(session) == ["PHYSICS"]


# ---------------------------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------------------------


def test_rename(session: Session) -> None:
    subject = create_subject(session, "Mathmatics")
    renamed = rename_subject(session, subject.id, "  Mathematics ")
    assert (renamed.name, renamed.name_key) == ("Mathematics", "mathematics")
    assert names(session) == ["Mathematics"]


def test_rename_to_a_change_of_case_is_allowed(session: Session) -> None:
    subject = create_subject(session, "physics")
    renamed = rename_subject(session, subject.id, "Physics")
    assert (renamed.name, renamed.name_key) == ("Physics", "physics")


def test_rename_to_the_same_name_writes_nothing(session: Session) -> None:
    subject = create_subject(session, "Physics")
    before = row(session, subject.id)
    rename_subject(session, subject.id, "  Physics  ")
    assert row(session, subject.id) == before


def test_rename_onto_another_subject_is_refused(session: Session) -> None:
    create_subject(session, "Physics")
    chemistry = create_subject(session, "Chemistry")
    before = row(session, chemistry.id)
    with pytest.raises(DuplicateSubjectName) as caught:
        rename_subject(session, chemistry.id, "physics")
    assert caught.value.message == "A subject named “Physics” already exists."
    assert row(session, chemistry.id) == before


def test_rename_refuses_an_invalid_name(session: Session) -> None:
    subject = create_subject(session, "Physics")
    before = row(session, subject.id)
    with pytest.raises(SubjectNameError):
        rename_subject(session, subject.id, "")
    assert row(session, subject.id) == before


def test_rename_keeps_the_status(session: Session) -> None:
    subject = create_subject(session, "Physics")
    set_subject_active(session, subject.id, False)
    assert rename_subject(session, subject.id, "Astronomy").is_active is False


def test_rename_of_a_missing_subject_is_not_found_even_with_an_invalid_name(
    session: Session,
) -> None:
    with pytest.raises(SubjectNotFound):
        rename_subject(session, MISSING, "Physics")
    with pytest.raises(SubjectNotFound):
        rename_subject(session, MISSING, "")


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------


def test_deactivate_and_activate(session: Session) -> None:
    subject = create_subject(session, "Physics")
    assert set_subject_active(session, subject.id, False).is_active is False
    assert set_subject_active(session, subject.id, True).is_active is True


@pytest.mark.parametrize("active", [True, False])
def test_setting_the_current_status_writes_nothing(session: Session, active: bool) -> None:
    subject = create_subject(session, "Physics")
    if not active:
        set_subject_active(session, subject.id, False)
    before = row(session, subject.id)
    set_subject_active(session, subject.id, active)
    assert row(session, subject.id) == before


# ---------------------------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------------------------


def test_nothing_uses_a_subject_yet(session: Session) -> None:
    subject = create_subject(session, "Physics")
    assert count_subject_uses(session, subject.id) == 0


def test_delete_removes_the_row_and_frees_the_name(session: Session) -> None:
    subject = create_subject(session, "Physics")
    delete_subject(session, subject.id)
    assert list_subjects(session) == []
    assert create_subject(session, "PHYSICS").name == "PHYSICS"


def test_a_subject_in_use_cannot_be_deleted(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = create_subject(session, "Physics")
    monkeypatch.setattr(app.services.subjects, "count_subject_uses", lambda *_: 1)
    with pytest.raises(SubjectInUse) as caught:
        delete_subject(session, subject.id)
    assert caught.value.subject.id == subject.id
    assert caught.value.uses == 1
    assert names(session) == ["Physics"]


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: get_subject(s, MISSING),
        lambda s: set_subject_active(s, MISSING, False),
        lambda s: set_subject_active(s, MISSING, True),
        lambda s: delete_subject(s, MISSING),
    ],
    ids=["get", "deactivate", "activate", "delete"],
)
def test_a_missing_subject_is_not_found(
    session: Session, operation: Callable[[Session], object]
) -> None:
    with pytest.raises(SubjectNotFound) as caught:
        operation(session)
    assert caught.value.subject_id == MISSING


# ---------------------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_the_id_and_never_the_name(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        subject = create_subject(session, "Astrophysics")
        sid = subject.id
        rename_subject(session, subject.id, "Cosmology")
        rename_subject(session, subject.id, "Cosmology")  # no-op
        set_subject_active(session, subject.id, False)
        set_subject_active(session, subject.id, False)  # no-op
        set_subject_active(session, subject.id, True)
        delete_subject(session, subject.id)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [
        f"Subject created: id={sid}",
        f"Subject renamed: id={sid}",
        f"Subject deactivated: id={sid}",
        f"Subject activated: id={sid}",
        f"Subject deleted: id={sid}",
    ]
    assert not any("Astrophysics" in m or "Cosmology" in m for m in messages)
