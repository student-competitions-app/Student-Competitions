"""The educational institution operations on SQLite and on PostgreSQL.

See specs/007-institutions/contracts/institution-service.md. Every test runs once per engine
through the `session` fixture, so the case-insensitive uniqueness and the order are proven on both.
"""

import logging
from collections.abc import Callable

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

import app.services.institutions
from app.core.db import utc_now
from app.models import Institution
from app.schemas.institution import InstitutionNameError, institution_name_key
from app.services.institutions import (
    DuplicateInstitutionName,
    InstitutionInUse,
    InstitutionNotFound,
    count_institution_uses,
    create_institution,
    delete_institution,
    get_institution,
    list_institutions,
    rename_institution,
    set_institution_active,
)
from app.services.subjects import create_subject

MISSING = 999


def names(session: Session) -> list[str]:
    return [institution.name for institution in list_institutions(session)]


def row(session: Session, institution_id: int) -> tuple[object, ...]:
    session.expire_all()
    institution = get_institution(session, institution_id)
    return (institution.name, institution.name_key, institution.is_active, institution.updated_at)


# ---------------------------------------------------------------------------------------------
# Create and list
# ---------------------------------------------------------------------------------------------


def test_create_stores_the_trimmed_name_its_key_and_active(session: Session) -> None:
    institution = create_institution(session, "  Odesa College  ")
    assert institution.id is not None
    stored = get_institution(session, institution.id)
    assert stored.name == "Odesa College"
    assert stored.name_key == "odesa college"
    assert stored.is_active is True
    assert stored.created_at == stored.updated_at


def test_the_list_starts_empty(session: Session) -> None:
    assert list_institutions(session) == []


@pytest.mark.parametrize(
    ("first", "second", "stored"),
    [
        ("Lviv Polytechnic", "LVIV POLYTECHNIC", "Lviv Polytechnic"),
        ("Київський університет", "КИЇВСЬКИЙ УНІВЕРСИТЕТ", "Київський університет"),
    ],
    ids=["latin", "cyrillic"],
)
def test_create_refuses_a_name_differing_only_in_case(
    session: Session, first: str, second: str, stored: str
) -> None:
    create_institution(session, first)
    with pytest.raises(DuplicateInstitutionName) as caught:
        create_institution(session, second)
    assert caught.value.existing_name == stored
    assert caught.value.message == f"An educational institution named “{stored}” already exists."
    assert names(session) == [stored]


def test_create_refuses_the_name_of_an_inactive_institution(session: Session) -> None:
    lviv = create_institution(session, "Lviv Polytechnic")
    set_institution_active(session, lviv.id, False)
    with pytest.raises(DuplicateInstitutionName):
        create_institution(session, "lviv polytechnic")


@pytest.mark.parametrize("raw", ["", "   ", "a" * 201, "Lviv\tPolytechnic"])
def test_create_refuses_an_invalid_name(session: Session, raw: str) -> None:
    with pytest.raises(InstitutionNameError):
        create_institution(session, raw)
    assert list_institutions(session) == []


def test_an_institution_may_share_its_name_with_a_subject(session: Session) -> None:
    """The two lists are independent (spec edge case "Same name as a subject")."""
    create_subject(session, "Physics")
    assert create_institution(session, "Physics").name == "Physics"


def test_the_list_ignores_case(session: Session) -> None:
    for name in ("Lviv Polytechnic", "alpha College", "Kyiv Polytechnic Institute"):
        create_institution(session, name)
    assert names(session) == ["alpha College", "Kyiv Polytechnic Institute", "Lviv Polytechnic"]


def test_the_list_includes_inactive_institutions(session: Session) -> None:
    create_institution(session, "Lviv Polytechnic")
    alpha = create_institution(session, "Alpha College")
    set_institution_active(session, alpha.id, False)
    assert [(i.name, i.is_active) for i in list_institutions(session)] == [
        ("Alpha College", False),
        ("Lviv Polytechnic", True),
    ]


def test_ties_on_the_key_are_broken_by_id(session: Session) -> None:
    """Equal keys cannot be stored; the sort key still ends in the id, so the order is total."""
    create_institution(session, "Alpha College")
    create_institution(session, "Beta School")
    institutions = list_institutions(session)
    assert [i.id for i in institutions] == sorted(i.id for i in institutions)


def test_the_unique_constraint_refuses_a_direct_duplicate(session: Session) -> None:
    """The guarantee against simultaneous submissions is the constraint, not the pre-check."""
    create_institution(session, "Lviv Polytechnic")
    now = utc_now()
    session.add(
        Institution(
            name="LVIV POLYTECHNIC",
            name_key=institution_name_key("LVIV POLYTECHNIC"),
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_concurrent_create_becomes_a_duplicate_error(
    session: Session, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rival inserts the same name between the pre-check and the commit."""
    real_find = app.services.institutions._find_by_key
    calls = 0

    def find_then_race(db: Session, key: str) -> Institution | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            found = real_find(db, key)
            with Session(engine) as rival:
                create_institution(rival, "LVIV POLYTECHNIC")
            return found
        return real_find(db, key)

    monkeypatch.setattr(app.services.institutions, "_find_by_key", find_then_race)
    with pytest.raises(DuplicateInstitutionName) as caught:
        create_institution(session, "Lviv Polytechnic")
    assert caught.value.existing_name == "LVIV POLYTECHNIC"
    assert names(session) == ["LVIV POLYTECHNIC"]


# ---------------------------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------------------------


def test_rename(session: Session) -> None:
    institution = create_institution(session, "Lviv Politechnic")
    renamed = rename_institution(session, institution.id, "  Lviv Polytechnic ")
    assert (renamed.name, renamed.name_key) == ("Lviv Polytechnic", "lviv polytechnic")
    assert names(session) == ["Lviv Polytechnic"]


def test_rename_keeps_the_id(session: Session) -> None:
    """SC-007, FR-018: whatever refers to the institution by id still finds it."""
    institution = create_institution(session, "Lviv Politechnic")
    original_id = institution.id
    rename_institution(session, original_id, "Lviv Polytechnic")
    assert get_institution(session, original_id).name == "Lviv Polytechnic"
    assert [i.id for i in list_institutions(session)] == [original_id]


def test_rename_to_a_change_of_case_is_allowed(session: Session) -> None:
    institution = create_institution(session, "odesa college")
    renamed = rename_institution(session, institution.id, "Odesa College")
    assert (renamed.name, renamed.name_key) == ("Odesa College", "odesa college")


def test_rename_to_the_same_name_writes_nothing(session: Session) -> None:
    institution = create_institution(session, "Odesa College")
    before = row(session, institution.id)
    rename_institution(session, institution.id, "  Odesa College  ")
    assert row(session, institution.id) == before


def test_rename_onto_another_institution_is_refused(session: Session) -> None:
    create_institution(session, "Lviv Polytechnic")
    odesa = create_institution(session, "Odesa College")
    before = row(session, odesa.id)
    with pytest.raises(DuplicateInstitutionName) as caught:
        rename_institution(session, odesa.id, "lviv polytechnic")
    assert caught.value.message == (
        "An educational institution named “Lviv Polytechnic” already exists."
    )
    assert row(session, odesa.id) == before


def test_rename_refuses_an_invalid_name(session: Session) -> None:
    institution = create_institution(session, "Odesa College")
    before = row(session, institution.id)
    with pytest.raises(InstitutionNameError):
        rename_institution(session, institution.id, "")
    assert row(session, institution.id) == before


def test_rename_keeps_the_status(session: Session) -> None:
    institution = create_institution(session, "Odesa College")
    set_institution_active(session, institution.id, False)
    renamed = rename_institution(session, institution.id, "Odesa Lyceum")
    assert renamed.is_active is False
    assert renamed.id == institution.id


def test_rename_of_a_missing_institution_is_not_found_even_with_an_invalid_name(
    session: Session,
) -> None:
    with pytest.raises(InstitutionNotFound):
        rename_institution(session, MISSING, "Odesa College")
    with pytest.raises(InstitutionNotFound):
        rename_institution(session, MISSING, "")


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------


def test_deactivate_and_activate(session: Session) -> None:
    institution = create_institution(session, "Odesa College")
    assert set_institution_active(session, institution.id, False).is_active is False
    assert set_institution_active(session, institution.id, True).is_active is True


@pytest.mark.parametrize("active", [True, False])
def test_setting_the_current_status_writes_nothing(session: Session, active: bool) -> None:
    institution = create_institution(session, "Odesa College")
    if not active:
        set_institution_active(session, institution.id, False)
    before = row(session, institution.id)
    set_institution_active(session, institution.id, active)
    assert row(session, institution.id) == before


# ---------------------------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------------------------


def test_nothing_uses_an_institution_yet(session: Session) -> None:
    institution = create_institution(session, "Odesa College")
    assert count_institution_uses(session, institution.id) == 0


def test_delete_removes_the_row_and_frees_the_name(session: Session) -> None:
    institution = create_institution(session, "Test School")
    delete_institution(session, institution.id)
    assert list_institutions(session) == []
    assert create_institution(session, "TEST SCHOOL").name == "TEST SCHOOL"


def test_an_institution_in_use_cannot_be_deleted(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-004: a stand-in for the teacher and student links of milestones 8 and 9."""
    institution = create_institution(session, "Lviv Polytechnic")
    monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda *_: 1)
    with pytest.raises(InstitutionInUse) as caught:
        delete_institution(session, institution.id)
    assert caught.value.institution.id == institution.id
    assert caught.value.uses == 1
    assert names(session) == ["Lviv Polytechnic"]


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: get_institution(s, MISSING),
        lambda s: set_institution_active(s, MISSING, False),
        lambda s: set_institution_active(s, MISSING, True),
        lambda s: delete_institution(s, MISSING),
    ],
    ids=["get", "deactivate", "activate", "delete"],
)
def test_a_missing_institution_is_not_found(
    session: Session, operation: Callable[[Session], object]
) -> None:
    with pytest.raises(InstitutionNotFound) as caught:
        operation(session)
    assert caught.value.institution_id == MISSING


# ---------------------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_the_id_and_never_the_name(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        institution = create_institution(session, "Astro Academy")
        iid = institution.id
        rename_institution(session, institution.id, "Cosmos Lyceum")
        rename_institution(session, institution.id, "Cosmos Lyceum")  # no-op
        set_institution_active(session, institution.id, False)
        set_institution_active(session, institution.id, False)  # no-op
        set_institution_active(session, institution.id, True)
        delete_institution(session, institution.id)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [
        f"Institution created: id={iid}",
        f"Institution renamed: id={iid}",
        f"Institution deactivated: id={iid}",
        f"Institution activated: id={iid}",
        f"Institution deleted: id={iid}",
    ]
    assert not any("Astro Academy" in m or "Cosmos Lyceum" in m for m in messages)
