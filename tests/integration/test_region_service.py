"""The region operations on SQLite and on PostgreSQL.

See specs/007-region-and-institutions-management/contracts/institution-service.md. Every test runs
once per engine through the `session` fixture, so the case-insensitive uniqueness and the order are
proven on both.
"""

import logging
from collections.abc import Callable

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import app.services.regions
from app.core.db import utc_now
from app.models import Institution, Region
from app.schemas.names import InvalidName, name_key
from app.services.regions import (
    DuplicateRegionName,
    RegionNotEmpty,
    RegionNotFound,
    count_region_institutions,
    create_region,
    delete_region,
    get_region,
    list_regions,
    rename_region,
    set_region_active,
)

MISSING = 999
CONTROL = "The name cannot contain tabs, line breaks or other control characters."
EMPTY = "Enter a name."
TOO_LONG = "The name can be at most 200 characters."


def add_region(session: Session, name: str, active: bool = True) -> Region:
    """A region inserted directly, bypassing the service."""
    now = utc_now()
    region = Region(
        name=name, name_key=name_key(name), is_active=active, created_at=now, updated_at=now
    )
    session.add(region)
    session.commit()
    session.refresh(region)
    return region


def add_institution(session: Session, region: Region, name: str, active: bool = True) -> int:
    """An institution inserted directly; its id."""
    now = utc_now()
    institution = Institution(
        region_id=region.id,
        name=name,
        name_key=name_key(name),
        is_active=active,
        created_at=now,
        updated_at=now,
    )
    session.add(institution)
    session.commit()
    assert institution.id is not None
    return institution.id


def names(session: Session) -> list[str]:
    return [region.name for region in list_regions(session)]


def row(session: Session, region_id: int) -> tuple[object, ...]:
    session.expire_all()
    region = get_region(session, region_id)
    return (region.name, region.name_key, region.is_active, region.updated_at)


def institution_statuses(session: Session, region_id: int) -> dict[int, bool]:
    session.expire_all()
    rows = session.exec(select(Institution).where(Institution.region_id == region_id)).all()
    return {institution.id: institution.is_active for institution in rows}


# ---------------------------------------------------------------------------------------------
# List and get
# ---------------------------------------------------------------------------------------------


def test_the_list_starts_empty(session: Session) -> None:
    assert list_regions(session) == []


def test_the_list_ignores_case_and_includes_deactivated_regions(session: Session) -> None:
    add_region(session, "Odesa")
    add_region(session, "kyiv", active=False)
    add_region(session, "Lviv")
    assert [(r.name, r.is_active) for r in list_regions(session)] == [
        ("kyiv", False),
        ("Lviv", True),
        ("Odesa", True),
    ]


def test_get_returns_the_region(session: Session) -> None:
    region = add_region(session, "Kyiv")
    assert get_region(session, region.id).name == "Kyiv"


def test_the_unique_constraint_refuses_a_direct_duplicate(session: Session) -> None:
    """The guarantee against simultaneous submissions is the constraint, not the pre-check
    (FR-020)."""
    add_region(session, "Kyiv")
    with pytest.raises(IntegrityError):
        add_region(session, "KYIV")
    session.rollback()


# ---------------------------------------------------------------------------------------------
# Create (user story 1)
# ---------------------------------------------------------------------------------------------


def test_create_stores_the_trimmed_name_its_key_and_active(session: Session) -> None:
    region = create_region(session, "  Kharkiv Region  ")
    stored = get_region(session, region.id)
    assert stored.name == "Kharkiv Region"
    assert stored.name_key == "kharkiv region"
    assert stored.is_active is True
    assert stored.created_at == stored.updated_at


@pytest.mark.parametrize(
    ("first", "second"),
    [("Kyiv", "  KYIV  "), ("Київ", "КИЇВ")],
    ids=["latin", "cyrillic"],
)
def test_create_refuses_a_name_differing_only_in_case(
    session: Session, first: str, second: str
) -> None:
    create_region(session, first)
    with pytest.raises(DuplicateRegionName) as caught:
        create_region(session, second)
    assert caught.value.existing_name == first
    assert caught.value.message == f"A region named “{first}” already exists."
    assert names(session) == [first]


def test_create_refuses_the_name_of_a_deactivated_region(session: Session) -> None:
    add_region(session, "Kyiv", active=False)
    with pytest.raises(DuplicateRegionName):
        create_region(session, "kyiv")


def test_inner_spaces_make_a_different_name(session: Session) -> None:
    create_region(session, "Kyiv Region")
    create_region(session, "Kyiv  Region")
    assert sorted(names(session)) == ["Kyiv  Region", "Kyiv Region"]


@pytest.mark.parametrize(
    ("raw", "message"),
    [("", EMPTY), ("   ", EMPTY), ("a" * 201, TOO_LONG), ("Ky\tiv", CONTROL)],
    ids=["empty", "spaces", "too-long", "tab"],
)
def test_create_refuses_an_invalid_name(session: Session, raw: str, message: str) -> None:
    with pytest.raises(InvalidName) as caught:
        create_region(session, raw)
    assert caught.value.message == message
    assert list_regions(session) == []


def test_a_name_of_exactly_200_characters_is_accepted(session: Session) -> None:
    assert create_region(session, "a" * 200).name == "a" * 200


def test_a_concurrent_create_becomes_a_duplicate_error(
    session: Session, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rival inserts the same name between the pre-check and the commit (FR-020)."""
    real_find = app.services.regions._find_by_key
    calls = 0

    def find_then_race(db: Session, key: str) -> Region | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            found = real_find(db, key)
            with Session(engine) as rival:
                create_region(rival, "KYIV")
            return found
        return real_find(db, key)

    monkeypatch.setattr(app.services.regions, "_find_by_key", find_then_race)
    with pytest.raises(DuplicateRegionName) as caught:
        create_region(session, "Kyiv")
    assert caught.value.existing_name == "KYIV"
    assert names(session) == ["KYIV"]
    assert create_region(session, "Lviv").name == "Lviv"  # the session is still usable


# ---------------------------------------------------------------------------------------------
# Rename, status, delete (user story 3)
# ---------------------------------------------------------------------------------------------


def test_rename(session: Session) -> None:
    region = create_region(session, "Lvov")
    renamed = rename_region(session, region.id, "Lviv")
    assert (renamed.name, renamed.name_key) == ("Lviv", "lviv")
    assert names(session) == ["Lviv"]


def test_rename_onto_another_region_is_refused(session: Session) -> None:
    create_region(session, "Kyiv")
    lviv = create_region(session, "Lviv")
    before = row(session, lviv.id)
    with pytest.raises(DuplicateRegionName) as caught:
        rename_region(session, lviv.id, "KYIV")
    assert caught.value.message == "A region named “Kyiv” already exists."
    assert row(session, lviv.id) == before


def test_rename_to_a_change_of_case_is_allowed(session: Session) -> None:
    region = create_region(session, "kyiv")
    assert rename_region(session, region.id, "Kyiv").name == "Kyiv"


def test_rename_to_the_same_name_writes_nothing(session: Session) -> None:
    region = create_region(session, "Kyiv")
    before = row(session, region.id)
    rename_region(session, region.id, "  Kyiv  ")
    assert row(session, region.id) == before


def test_rename_refuses_an_invalid_name(session: Session) -> None:
    region = create_region(session, "Kyiv")
    before = row(session, region.id)
    with pytest.raises(InvalidName):
        rename_region(session, region.id, "")
    assert row(session, region.id) == before


def test_rename_of_a_missing_region_is_not_found_even_with_an_invalid_name(
    session: Session,
) -> None:
    with pytest.raises(RegionNotFound):
        rename_region(session, MISSING, "Kyiv")
    with pytest.raises(RegionNotFound):
        rename_region(session, MISSING, "")


def test_rename_keeps_the_status(session: Session) -> None:
    region = create_region(session, "Kyiv")
    set_region_active(session, region.id, False)
    assert rename_region(session, region.id, "Kyiv Region").is_active is False


def test_deactivate_and_activate(session: Session) -> None:
    region = create_region(session, "Kyiv")
    assert set_region_active(session, region.id, False).is_active is False
    assert set_region_active(session, region.id, True).is_active is True


@pytest.mark.parametrize("active", [True, False])
def test_setting_the_current_status_writes_nothing(session: Session, active: bool) -> None:
    region = create_region(session, "Kyiv")
    if not active:
        set_region_active(session, region.id, False)
    before = row(session, region.id)
    set_region_active(session, region.id, active)
    assert row(session, region.id) == before


def test_the_region_status_never_cascades_to_its_institutions(session: Session) -> None:
    """FR-033: each institution keeps its own status, and gets it back exactly."""
    region = create_region(session, "Kyiv")
    add_institution(session, region, "Academy")
    add_institution(session, region, "College", active=False)
    before = institution_statuses(session, region.id)
    assert sorted(before.values()) == [False, True]
    set_region_active(session, region.id, False)
    assert institution_statuses(session, region.id) == before
    set_region_active(session, region.id, True)
    assert institution_statuses(session, region.id) == before


def test_count_region_institutions_counts_active_and_deactivated(session: Session) -> None:
    region = create_region(session, "Kyiv")
    other = create_region(session, "Lviv")
    assert count_region_institutions(session, region.id) == 0
    add_institution(session, region, "Academy")
    add_institution(session, region, "College", active=False)
    add_institution(session, other, "Academy")
    assert count_region_institutions(session, region.id) == 2


def test_delete_removes_an_empty_region_and_frees_the_name(session: Session) -> None:
    region = create_region(session, "Test")
    delete_region(session, region.id)
    assert list_regions(session) == []
    assert create_region(session, "TEST").name == "TEST"


@pytest.mark.parametrize("active", [True, False], ids=["active", "deactivated"])
def test_a_region_holding_an_institution_cannot_be_deleted(session: Session, active: bool) -> None:
    """FR-036: a deactivated institution counts too."""
    region = create_region(session, "Kyiv")
    add_institution(session, region, "Academy", active=active)
    before = row(session, region.id)
    with pytest.raises(RegionNotEmpty) as caught:
        delete_region(session, region.id)
    assert caught.value.region.id == region.id
    assert caught.value.institutions == 1
    assert row(session, region.id) == before


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: get_region(s, MISSING),
        lambda s: set_region_active(s, MISSING, False),
        lambda s: set_region_active(s, MISSING, True),
        lambda s: delete_region(s, MISSING),
    ],
    ids=["get", "deactivate", "activate", "delete"],
)
def test_a_missing_region_is_not_found(
    session: Session, operation: Callable[[Session], object]
) -> None:
    with pytest.raises(RegionNotFound) as caught:
        operation(session)
    assert caught.value.region_id == MISSING


# ---------------------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_the_id_and_never_the_name(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        region = create_region(session, "Kyiv")
        rid = region.id
        rename_region(session, rid, "Kyiv Region")
        rename_region(session, rid, "Kyiv Region")  # no-op
        set_region_active(session, rid, False)
        set_region_active(session, rid, False)  # no-op
        set_region_active(session, rid, True)
        delete_region(session, rid)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [
        f"Region created: id={rid}",
        f"Region renamed: id={rid}",
        f"Region deactivated: id={rid}",
        f"Region activated: id={rid}",
        f"Region deleted: id={rid}",
    ]
    assert not any("Kyiv" in m for m in messages)
