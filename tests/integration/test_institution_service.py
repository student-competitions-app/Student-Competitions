"""The institution operations on SQLite and on PostgreSQL.

See specs/007-region-and-institutions-management/contracts/institution-service.md. Every test runs
once per engine through the `session` fixture, so uniqueness within a region, the order, and the
"wrong region is not found" rule are proven on both.
"""

import logging
from collections.abc import Callable

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import app.services.institutions
from app.core.db import utc_now
from app.models import Institution, Region
from app.schemas.names import InvalidName, name_key
from app.services.institutions import (
    DuplicateInstitutionName,
    InstitutionInUse,
    InstitutionNotFound,
    RegionInactive,
    count_institution_uses,
    create_institution,
    delete_institution,
    get_institution,
    list_institutions,
    rename_institution,
    set_institution_active,
)
from app.services.regions import RegionNotFound, set_region_active

MISSING = 999
DUPLICATE = "An educational institution named “{}” already exists in this region."
KPI = "Kyiv Polytechnic Institute"


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


def add_institution(
    session: Session, region: Region, name: str, active: bool = True
) -> Institution:
    """An institution inserted directly, bypassing the service."""
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
    session.refresh(institution)
    return institution


def names(session: Session, region: Region) -> list[str]:
    session.expire_all()
    return [institution.name for institution in list_institutions(session, region.id)]


def all_rows(session: Session) -> list[tuple[object, ...]]:
    session.expire_all()
    rows = session.exec(select(Institution).order_by(Institution.id)).all()
    return [(i.id, i.region_id, i.name, i.name_key, i.is_active, i.updated_at) for i in rows]


@pytest.fixture
def kyiv(session: Session) -> Region:
    return add_region(session, "Kyiv")


@pytest.fixture
def lviv(session: Session) -> Region:
    return add_region(session, "Lviv")


# ---------------------------------------------------------------------------------------------
# List and get
# ---------------------------------------------------------------------------------------------


def test_the_list_holds_only_the_regions_institutions_sorted(
    session: Session, kyiv: Region, lviv: Region
) -> None:
    """US2-7, FR-011."""
    for name in ("Zaporizhzhia College", "art school", "Academy"):
        add_institution(session, kyiv, name)
    add_institution(session, lviv, "Lviv University")
    assert names(session, kyiv) == ["Academy", "art school", "Zaporizhzhia College"]
    assert names(session, lviv) == ["Lviv University"]


def test_get_returns_the_institution_of_its_region(session: Session, kyiv: Region) -> None:
    institution = add_institution(session, kyiv, "Academy")
    assert get_institution(session, kyiv.id, institution.id).name == "Academy"


def test_get_through_another_region_is_not_found(
    session: Session, kyiv: Region, lviv: Region
) -> None:
    institution = add_institution(session, kyiv, "Academy")
    with pytest.raises(InstitutionNotFound) as caught:
        get_institution(session, lviv.id, institution.id)
    assert (caught.value.region_id, caught.value.institution_id) == (lviv.id, institution.id)


def test_get_through_a_missing_region_is_region_not_found(session: Session, kyiv: Region) -> None:
    institution = add_institution(session, kyiv, "Academy")
    with pytest.raises(RegionNotFound):
        get_institution(session, MISSING, institution.id)
    with pytest.raises(RegionNotFound):
        get_institution(session, MISSING, MISSING)


def test_get_of_a_missing_institution_is_not_found(session: Session, kyiv: Region) -> None:
    with pytest.raises(InstitutionNotFound):
        get_institution(session, kyiv.id, MISSING)


def test_the_constraint_is_unique_within_a_region_only(
    session: Session, kyiv: Region, lviv: Region
) -> None:
    """FR-019, FR-020: the guarantee is the composite constraint, not the pre-check."""
    add_institution(session, kyiv, "Academy")
    add_institution(session, lviv, "ACADEMY")  # another region: accepted
    with pytest.raises(IntegrityError):
        add_institution(session, kyiv, "ACADEMY")
    session.rollback()


# ---------------------------------------------------------------------------------------------
# Create (user story 2)
# ---------------------------------------------------------------------------------------------


def test_create_stores_an_active_institution_in_the_region(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, f"  {KPI}  ")
    stored = get_institution(session, kyiv.id, institution.id)
    assert stored.region_id == kyiv.id
    assert stored.name == KPI
    assert stored.name_key == KPI.casefold()
    assert stored.is_active is True
    assert stored.created_at == stored.updated_at


def test_the_same_name_is_accepted_in_another_region(
    session: Session, kyiv: Region, lviv: Region
) -> None:
    create_institution(session, kyiv.id, KPI)
    create_institution(session, lviv.id, KPI)
    assert names(session, kyiv) == [KPI]
    assert names(session, lviv) == [KPI]


def test_a_duplicate_in_the_same_region_is_refused(session: Session, kyiv: Region) -> None:
    create_institution(session, kyiv.id, KPI)
    with pytest.raises(DuplicateInstitutionName) as caught:
        create_institution(session, kyiv.id, KPI.upper())
    assert caught.value.existing_name == KPI
    assert caught.value.message == DUPLICATE.format(KPI)
    assert names(session, kyiv) == [KPI]


def test_the_name_of_a_deactivated_institution_is_taken(session: Session, kyiv: Region) -> None:
    add_institution(session, kyiv, "Academy", active=False)
    with pytest.raises(DuplicateInstitutionName):
        create_institution(session, kyiv.id, "academy")


@pytest.mark.parametrize("raw", ["", "   ", "a" * 201, "Aca\ndemy"])
def test_create_refuses_an_invalid_name(session: Session, kyiv: Region, raw: str) -> None:
    with pytest.raises(InvalidName):
        create_institution(session, kyiv.id, raw)
    assert all_rows(session) == []


def test_create_in_a_missing_region_is_not_found_before_the_name_is_checked(
    session: Session,
) -> None:
    with pytest.raises(RegionNotFound):
        create_institution(session, MISSING, "Academy")
    with pytest.raises(RegionNotFound):
        create_institution(session, MISSING, "")
    assert all_rows(session) == []


def test_create_in_a_deactivated_region_is_refused_before_the_name_is_checked(
    session: Session,
) -> None:
    """FR-024, SC-007."""
    odesa = add_region(session, "Odesa", active=False)
    for raw in ("Academy", ""):
        with pytest.raises(RegionInactive) as caught:
            create_institution(session, odesa.id, raw)
        assert caught.value.region.id == odesa.id
    assert all_rows(session) == []


def test_a_concurrent_create_becomes_a_duplicate_error(
    session: Session, engine: Engine, kyiv: Region, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rival inserts the same name in the same region between the pre-check and the commit."""
    real_find = app.services.institutions._find_in_region
    calls = 0

    def find_then_race(db: Session, region_id: int, key: str) -> Institution | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            found = real_find(db, region_id, key)
            with Session(engine) as rival:
                rival.add(
                    Institution(
                        region_id=region_id,
                        name="ACADEMY",
                        name_key=key,
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                )
                rival.commit()
            return found
        return real_find(db, region_id, key)

    monkeypatch.setattr(app.services.institutions, "_find_in_region", find_then_race)
    with pytest.raises(DuplicateInstitutionName) as caught:
        create_institution(session, kyiv.id, "Academy")
    assert caught.value.existing_name == "ACADEMY"
    assert names(session, kyiv) == ["ACADEMY"]


# ---------------------------------------------------------------------------------------------
# Rename, status, delete (user story 4)
# ---------------------------------------------------------------------------------------------


def test_rename(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Acadmy")
    renamed = rename_institution(session, kyiv.id, institution.id, " Academy ")
    assert (renamed.name, renamed.name_key, renamed.region_id) == ("Academy", "academy", kyiv.id)


def test_rename_onto_another_institution_of_the_region_is_refused(
    session: Session, kyiv: Region
) -> None:
    create_institution(session, kyiv.id, "Academy")
    college = create_institution(session, kyiv.id, "College")
    before = all_rows(session)
    with pytest.raises(DuplicateInstitutionName) as caught:
        rename_institution(session, kyiv.id, college.id, "academy")
    assert caught.value.message == DUPLICATE.format("Academy")
    assert all_rows(session) == before


def test_rename_to_a_name_used_in_another_region_is_accepted(
    session: Session, kyiv: Region, lviv: Region
) -> None:
    create_institution(session, kyiv.id, "Academy")
    college = create_institution(session, lviv.id, "College")
    assert rename_institution(session, lviv.id, college.id, "Academy").name == "Academy"


def test_rename_to_a_change_of_case_is_allowed(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "academy")
    assert rename_institution(session, kyiv.id, institution.id, "Academy").name == "Academy"


def test_rename_to_the_same_name_writes_nothing(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    before = all_rows(session)
    rename_institution(session, kyiv.id, institution.id, "  Academy ")
    assert all_rows(session) == before


def test_rename_never_changes_the_region(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    rename_institution(session, kyiv.id, institution.id, "College")
    session.expire_all()
    assert get_institution(session, kyiv.id, institution.id).region_id == kyiv.id


def test_rename_refuses_an_invalid_name(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    before = all_rows(session)
    with pytest.raises(InvalidName):
        rename_institution(session, kyiv.id, institution.id, "\t")
    assert all_rows(session) == before


def test_deactivate_and_activate(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    assert set_institution_active(session, kyiv.id, institution.id, False).is_active is False
    assert set_institution_active(session, kyiv.id, institution.id, True).is_active is True


@pytest.mark.parametrize("active", [True, False])
def test_setting_the_current_status_writes_nothing(
    session: Session, kyiv: Region, active: bool
) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    if not active:
        set_institution_active(session, kyiv.id, institution.id, False)
    before = all_rows(session)
    set_institution_active(session, kyiv.id, institution.id, active)
    assert all_rows(session) == before


def test_everything_but_create_works_in_a_deactivated_region(
    session: Session, kyiv: Region
) -> None:
    """US4-9, FR-015."""
    institution = create_institution(session, kyiv.id, "Academy")
    set_region_active(session, kyiv.id, False)
    assert rename_institution(session, kyiv.id, institution.id, "College").name == "College"
    assert set_institution_active(session, kyiv.id, institution.id, False).is_active is False
    assert set_institution_active(session, kyiv.id, institution.id, True).is_active is True
    delete_institution(session, kyiv.id, institution.id)
    assert all_rows(session) == []


@pytest.mark.parametrize(
    "operation",
    [
        lambda s, r, i: get_institution(s, r, i),
        lambda s, r, i: rename_institution(s, r, i, "Hacked"),
        lambda s, r, i: set_institution_active(s, r, i, False),
        lambda s, r, i: set_institution_active(s, r, i, True),
        lambda s, r, i: delete_institution(s, r, i),
    ],
    ids=["get", "rename", "deactivate", "activate", "delete"],
)
def test_an_institution_named_with_another_region_is_not_found(
    session: Session,
    kyiv: Region,
    lviv: Region,
    operation: Callable[[Session, int, int], object],
) -> None:
    """Research D7: the region in the request must be the institution's, and nothing changes."""
    institution = create_institution(session, kyiv.id, "Academy")
    before = all_rows(session)
    with pytest.raises(InstitutionNotFound):
        operation(session, lviv.id, institution.id)
    assert all_rows(session) == before


def test_nothing_uses_an_institution_yet(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    assert count_institution_uses(session, institution.id) == 0


def test_delete_removes_the_row_and_frees_the_name(session: Session, kyiv: Region) -> None:
    institution = create_institution(session, kyiv.id, "Academy")
    delete_institution(session, kyiv.id, institution.id)
    assert names(session, kyiv) == []
    assert create_institution(session, kyiv.id, "ACADEMY").name == "ACADEMY"


def test_an_institution_in_use_cannot_be_deleted(
    session: Session, kyiv: Region, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-037: a stand-in for the teacher and student links of milestones 8 and 9."""
    institution = create_institution(session, kyiv.id, "Academy")
    before = all_rows(session)
    monkeypatch.setattr(
        app.services.institutions,
        "count_institution_uses",
        lambda session, institution_id: 1,
    )
    with pytest.raises(InstitutionInUse) as caught:
        delete_institution(session, kyiv.id, institution.id)
    assert caught.value.institution.id == institution.id
    assert caught.value.uses == 1
    assert all_rows(session) == before


@pytest.mark.parametrize(
    "operation",
    [
        lambda s, r: get_institution(s, r, MISSING),
        lambda s, r: rename_institution(s, r, MISSING, "Academy"),
        lambda s, r: set_institution_active(s, r, MISSING, False),
        lambda s, r: delete_institution(s, r, MISSING),
    ],
    ids=["get", "rename", "deactivate", "delete"],
)
def test_a_missing_institution_is_not_found(
    session: Session, kyiv: Region, operation: Callable[[Session, int], object]
) -> None:
    with pytest.raises(InstitutionNotFound) as caught:
        operation(session, kyiv.id)
    assert caught.value.institution_id == MISSING


# ---------------------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------------------


def test_each_change_logs_the_ids_and_never_the_name(
    session: Session, kyiv: Region, caplog: pytest.LogCaptureFixture
) -> None:
    rid = kyiv.id
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        iid = create_institution(session, rid, "Academy").id
        rename_institution(session, rid, iid, "College")
        rename_institution(session, rid, iid, "College")  # no-op
        set_institution_active(session, rid, iid, False)
        set_institution_active(session, rid, iid, False)  # no-op
        set_institution_active(session, rid, iid, True)
        delete_institution(session, rid, iid)
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert messages == [
        f"Institution created: id={iid} region_id={rid}",
        f"Institution renamed: id={iid} region_id={rid}",
        f"Institution deactivated: id={iid} region_id={rid}",
        f"Institution activated: id={iid} region_id={rid}",
        f"Institution deleted: id={iid} region_id={rid}",
    ]
    assert not any("Academy" in m or "College" in m for m in messages)
