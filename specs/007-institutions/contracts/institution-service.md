# Contract: Institution Service and Name Rules (Milestone 7)

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md) |
**Research**: [research.md](../research.md) D1–D6

This is the internal interface that the institution routes call, and that milestones 8 and 9 build
on. It mirrors the subject service from milestone 6
([specs/006-admin-area/contracts/subject-service.md](../../006-admin-area/contracts/subject-service.md))
one for one.

These modules enforce no authorization. Authorization is done by `@allow_roles(Role.ADMIN)` on
every route that calls them (Principle IV). A later caller must put its own role check in front.

## `app/schemas/names.py` — pure, no I/O (new, moved from `app/schemas/subject.py`)

```python
NAME_MAX_LENGTH = 200
NAME_KEY_MAX_LENGTH = 600


class NameRuleError(ValueError):
    message: str  # ready to show in the form


def clean_name(raw: str) -> str: ...
def name_key(name: str) -> str: ...
```

| Function | Contract |
|---|---|
| `clean_name(raw)` | Exactly milestone 6's `clean_subject_name`: control characters (on the raw value), then trim, then empty, then length. Returns the trimmed name. Raises `NameRuleError` with the message from [data-model.md](../data-model.md#validation-rules-applied-by-clean_name-research-d1). |
| `name_key(name)` | Exactly milestone 6's `subject_name_key`: `unicodedata.normalize("NFC", name).casefold()`. Called on an already cleaned name. |

## `app/schemas/subject.py` — changed, same public names

Its body becomes aliases of `app.schemas.names`, so every existing import keeps working:

```python
SUBJECT_NAME_MAX_LENGTH = NAME_MAX_LENGTH
SUBJECT_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH
SubjectNameError = NameRuleError
clean_subject_name = clean_name
subject_name_key = name_key
```

Behaviour is unchanged. `tests/unit/test_subject_schemas.py` passes as it is.

## `app/schemas/institution.py` — new, aliases

```python
INSTITUTION_NAME_MAX_LENGTH = NAME_MAX_LENGTH
INSTITUTION_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH
InstitutionNameError = NameRuleError
clean_institution_name = clean_name
institution_name_key = name_key
```

## `app/services/institutions.py` — new

Every function takes an open `Session` first. The caller owns the session. Each write is one
committed unit of work, and is rolled back on error. Each successful change logs one `INFO` line
with the institution id only (for example `Institution created: id=3`). A no-op logs nothing.

```python
class InstitutionNotFound(LookupError):
    institution_id: int


class DuplicateInstitutionName(ValueError):
    existing_name: str
    message: str  # "An educational institution named “…” already exists."


class InstitutionInUse(ValueError):
    institution: Institution
    uses: int


def list_institutions(session) -> list[Institution]: ...
def get_institution(session, institution_id: int) -> Institution: ...
def create_institution(session, raw_name: str) -> Institution: ...
def rename_institution(session, institution_id: int, raw_name: str) -> Institution: ...
def set_institution_active(session, institution_id: int, active: bool) -> Institution: ...
def count_institution_uses(session, institution_id: int) -> int: ...
def delete_institution(session, institution_id: int) -> None: ...
```

| Function | Behaviour | Raises |
|---|---|---|
| `list_institutions` | All institutions, active and inactive, sorted by `(name_key, id)` in Python (milestone 6 research D3). | — |
| `get_institution` | The institution. | `InstitutionNotFound` |
| `create_institution` | Cleans the name. If another institution has the same key, refuses. Otherwise inserts with `is_active=True` and commits. An `IntegrityError` on commit (a concurrent insert) → rollback, then `DuplicateInstitutionName`, naming the institution that now exists. | `InstitutionNameError`, `DuplicateInstitutionName` |
| `rename_institution` | Loads the institution, then cleans the name. A duplicate is any **other** institution with the same key. If both `name` and `name_key` are unchanged: no write. Otherwise updates `name`, `name_key` and `updated_at`, keeping `id` and `is_active`, then commits. An `IntegrityError` on commit → rollback, then `DuplicateInstitutionName`. | `InstitutionNotFound`, `InstitutionNameError`, `DuplicateInstitutionName` |
| `set_institution_active` | If the status is already `active`: no write. Otherwise sets it, updates `updated_at` and commits. | `InstitutionNotFound` |
| `count_institution_uses` | How many records refer to the institution. **Returns `0` in this milestone.** Milestones 8 (teacher links) and 9 (student details) add their counts here (research D5). | — |
| `delete_institution` | Loads the institution. If `count_institution_uses > 0`, refuses. Otherwise deletes and commits. An `IntegrityError` on commit (a future foreign key) → rollback, then `InstitutionInUse`. | `InstitutionNotFound`, `InstitutionInUse` |

Validation happens before any duplicate lookup. For `rename_institution`, `InstitutionNotFound`
comes first, so a rename of a deleted institution reports "not found" rather than a name error.

## Tests the contract implies

- **`tests/unit/test_name_rules.py`** (new): a short check that `app.schemas.subject` and
  `app.schemas.institution` expose the same functions and limits as `app.schemas.names`, so the two
  lists cannot drift. The full rule table stays in `test_subject_schemas.py`, which already covers
  the shared functions.
- **`tests/integration/test_institution_service.py`** (new, both engines):
  - each function's behaviour and errors;
  - a no-op rename or status change leaves `updated_at` unchanged;
  - a rename keeps the `id` and the status (SC-007, FR-017);
  - the unique constraint rejects a direct duplicate insert (the concurrency guarantee), and a
    simulated race in `create_institution` ends in `DuplicateInstitutionName`;
  - "Київський університет" and "КИЇВСЬКИЙ УНІВЕРСИТЕТ" are duplicates;
  - an institution may share its name with a subject;
  - sorting is case-insensitive and stable;
  - `count_institution_uses` returns `0`, and `delete_institution` is refused when it is
    monkeypatched to return `1` (SC-004).
