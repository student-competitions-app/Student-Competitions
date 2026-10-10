# Contract: Name Rules, Region Service and Institution Service (Milestone 7)

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md) |
**Research**: [research.md](../research.md) D1–D6, D9, D10

This is the internal interface that the routes call, and that milestones 8 and 9 build on.

These modules enforce no authorization. Every route that calls them is `@allow_roles(Role.ADMIN)`
(Principle IV). A later caller must put its own role check in front.

## `app/schemas/names.py` — pure, no I/O (new; research D1)

```python
NAME_MAX_LENGTH = 200
NAME_KEY_MAX_LENGTH = 600


class InvalidName(ValueError):
    message: str  # ready to show in the form


def clean_name(raw: str) -> str: ...
def name_key(name: str) -> str: ...
```

This is the code moved from `app/schemas/subject.py`, unchanged in behaviour. The rules are in
[data-model.md §3](../data-model.md#3-name-rules--shared-by-subjects-regions-and-institutions).

`app/schemas/subject.py` keeps the following names, so milestone 6 code and tests do not change:

| Name | Is |
|---|---|
| `SUBJECT_NAME_MAX_LENGTH` | `NAME_MAX_LENGTH` |
| `SUBJECT_NAME_KEY_MAX_LENGTH` | `NAME_KEY_MAX_LENGTH` |
| `SubjectNameError` | `InvalidName` (the same class) |
| `clean_subject_name` | `clean_name` |
| `subject_name_key` | `name_key` |

## `app/services/regions.py` (new)

Every function takes an open `Session` first. The caller owns the session. Each write is one
committed unit of work, rolled back on error. Names are passed exactly as submitted, and cleaned
here.

```python
class RegionNotFound(LookupError):
    region_id: int


class DuplicateRegionName(ValueError):
    existing_name: str
    message: str  # "A region named “{existing_name}” already exists."


class RegionNotEmpty(ValueError):
    region: Region
    institutions: int


def list_regions(session) -> list[Region]: ...
def get_region(session, region_id: int) -> Region: ...
def create_region(session, raw_name: str) -> Region: ...
def rename_region(session, region_id: int, raw_name: str) -> Region: ...
def set_region_active(session, region_id: int, active: bool) -> Region: ...
def count_region_institutions(session, region_id: int) -> int: ...
def delete_region(session, region_id: int) -> None: ...
```

| Function | Behaviour | Raises |
|---|---|---|
| `list_regions` | All regions, active and deactivated, sorted by `(name_key, id)` in Python. | — |
| `get_region` | The region. | `RegionNotFound` |
| `create_region` | Cleans the name and refuses a duplicate key. Otherwise inserts an active region and commits. An `IntegrityError` on commit → rollback, then `DuplicateRegionName` naming the region that now exists. | `InvalidName`, `DuplicateRegionName` |
| `rename_region` | Loads the region, cleans the name, and refuses if **another** region has the key. Unchanged `name` and `name_key` → no write. Otherwise updates `name`, `name_key` and `updated_at`, then commits. An `IntegrityError` → `DuplicateRegionName`. | `RegionNotFound`, `InvalidName`, `DuplicateRegionName` |
| `set_region_active` | Same status already → no write. Otherwise sets it and `updated_at`, then commits. **Never touches institutions** (FR-033). | `RegionNotFound` |
| `count_region_institutions` | The number of institutions with this `region_id`, active and deactivated. | — |
| `delete_region` | Loads the region. If `count_region_institutions > 0`, refuses. Otherwise deletes and commits. An `IntegrityError` on commit (the PostgreSQL foreign key, in a race) → rollback, then `RegionNotEmpty`. | `RegionNotFound`, `RegionNotEmpty` |

## `app/services/institutions.py` (new)

The same conventions apply. Every function that names an institution also names its region. An
institution whose `region_id` differs from the given region is treated exactly as a missing one
(research D7).

```python
class InstitutionNotFound(LookupError):
    region_id: int
    institution_id: int


class DuplicateInstitutionName(ValueError):
    existing_name: str
    message: str  # "An educational institution named “{existing_name}” already exists in
    # this region."


class RegionInactive(ValueError):
    region: Region  # new institutions cannot be added to it (FR-024)


class InstitutionInUse(ValueError):
    institution: Institution
    uses: int


def list_institutions(session, region_id: int) -> list[Institution]: ...
def get_institution(session, region_id: int, institution_id: int) -> Institution: ...
def create_institution(session, region_id: int, raw_name: str) -> Institution: ...
def rename_institution(
    session, region_id: int, institution_id: int, raw_name: str
) -> Institution: ...
def set_institution_active(
    session, region_id: int, institution_id: int, active: bool
) -> Institution: ...
def count_institution_uses(session, institution_id: int) -> int: ...
def delete_institution(session, region_id: int, institution_id: int) -> None: ...
```

| Function | Behaviour | Raises |
|---|---|---|
| `list_institutions` | The region's institutions only, active and deactivated, sorted by `(name_key, id)`. The caller has already loaded the region, so this function does not check that it exists. | — |
| `get_institution` | Loads the region (`RegionNotFound` first), then the institution. Missing, or `institution.region_id != region_id` → `InstitutionNotFound`. | `RegionNotFound`, `InstitutionNotFound` |
| `create_institution` | Loads the region with `with_for_update=True` (research D5). Missing → `RegionNotFound`. Deactivated → `RegionInactive`. Then cleans the name, and refuses a duplicate key within the region. Inserts an active institution with this `region_id` and commits. An `IntegrityError` on commit → rollback. If the region is now gone (the PostgreSQL foreign key), raise `RegionNotFound`. Otherwise raise `DuplicateInstitutionName`. | `RegionNotFound`, `RegionInactive`, `InvalidName`, `DuplicateInstitutionName` |
| `rename_institution` | `get_institution`, then cleans the name. A duplicate is **another** institution of the **same** region with the key. Unchanged → no write. Otherwise updates `name`, `name_key` and `updated_at` (**never** `region_id`), then commits. An `IntegrityError` → `DuplicateInstitutionName`. Allowed whatever the region's status. | `RegionNotFound`, `InstitutionNotFound`, `InvalidName`, `DuplicateInstitutionName` |
| `set_institution_active` | `get_institution`. Same status → no write. Otherwise sets it and `updated_at`, then commits. Allowed whatever the region's status. | `RegionNotFound`, `InstitutionNotFound` |
| `count_institution_uses` | How many records use the institution. **Returns `0` in this milestone.** Milestones 8 (teacher links) and 9 (students) add their counts here (research D9, FR-038). | — |
| `delete_institution` | `get_institution`. If `count_institution_uses > 0`, refuses. Otherwise deletes and commits. An `IntegrityError` on commit (a future foreign key) → rollback, then `InstitutionInUse`. Allowed whatever the region's status. | `RegionNotFound`, `InstitutionNotFound`, `InstitutionInUse` |

**Order of checks**: existence (region, then institution) comes before the region-status check,
which comes before name validation, which comes before the duplicate lookup. So a request for a
deleted region reports "not found" rather than a name error. A create in a deactivated region
reports the deactivation rather than a name error.

**No `is_available` helper** in this milestone (research D10). Milestone 8 adds the first query
that needs "active institution in an active region".

## Tests the contract implies

- **`tests/unit/test_name_schemas.py`** (new):
  - the subject aliases are the shared objects (`SubjectNameError is InvalidName`, and so on);
  - the shared functions apply the rules. The existing `tests/unit/test_subject_schemas.py` keeps
    covering every rule through the aliases and does not change.
- **`tests/integration/test_region_service.py`** (both engines):
  - create, rename (including a change of case only, and a no-op that leaves `updated_at`
    unchanged), deactivate and activate (repeats are no-ops), delete;
  - duplicates ignoring case, including Cyrillic, and a duplicate of a deactivated region;
  - the unique constraint rejects a direct duplicate insert;
  - sorting;
  - `delete_region` is refused with one active institution, and with one deactivated institution;
  - deactivating a region leaves its institutions' `is_active` unchanged, and activating it gives
    back exactly the same statuses.
- **`tests/integration/test_institution_service.py`** (both engines):
  - create, rename, deactivate, activate, delete;
  - the same name in two regions is accepted, and in the same region is refused (also after a
    change of case, and against a deactivated institution);
  - the composite constraint rejects a direct duplicate insert in the same region and accepts it in
    another;
  - `create_institution` is refused for a missing region and for a deactivated region;
  - `RegionNotFound` comes before the name error;
  - every function that takes `(region_id, institution_id)` raises `InstitutionNotFound` when the
    institution belongs to another region, and changes nothing;
  - `rename_institution` never changes `region_id`;
  - rename, deactivate, activate and delete all work in a deactivated region;
  - `delete_institution` is refused when `count_institution_uses` is monkeypatched to return `1`;
  - the list contains only the region's institutions, sorted.
