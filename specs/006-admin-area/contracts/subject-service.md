# Contract: Subject Service and Name Rules (Milestone 6)

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md) |
**Research**: [research.md](../research.md) D1–D4

This is the internal interface that the subject routes call, and that milestones 9 and 10 build
on.

These modules enforce no authorization. Authorization is done by `@allow_roles(Role.ADMIN)` on
every route that calls them (Principle IV). A later caller must put its own role check in front.

## `app/schemas/subject.py` — pure, no I/O

```python
SUBJECT_NAME_MAX_LENGTH = 200
SUBJECT_NAME_KEY_MAX_LENGTH = 600


class SubjectNameError(ValueError):
    message: str  # ready to show in the form


def clean_subject_name(raw: str) -> str: ...
def subject_name_key(name: str) -> str: ...
```

| Function | Contract |
|---|---|
| `clean_subject_name(raw)` | Applies the rules in research D2, in order: control characters (on the raw value), then trim, then empty, then length. Returns the trimmed name. Raises `SubjectNameError` with the message from [data-model.md](../data-model.md#validation-rules-applied-by-clean_subject_name-research-d2). |
| `subject_name_key(name)` | `unicodedata.normalize("NFC", name).casefold()`. Called on an already cleaned name. |

## `app/services/subjects.py`

Every function takes an open `Session` first. The caller owns the session. Each write is one
committed unit of work, and is rolled back on error.

```python
class SubjectNotFound(LookupError):
    subject_id: int


class DuplicateSubjectName(ValueError):
    existing_name: str
    message: str


class SubjectInUse(ValueError):
    subject: Subject
    uses: int


def list_subjects(session) -> list[Subject]: ...
def get_subject(session, subject_id: int) -> Subject: ...
def create_subject(session, raw_name: str) -> Subject: ...
def rename_subject(session, subject_id: int, raw_name: str) -> Subject: ...
def set_subject_active(session, subject_id: int, active: bool) -> Subject: ...
def count_subject_uses(session, subject_id: int) -> int: ...
def delete_subject(session, subject_id: int) -> None: ...
```

| Function | Behaviour | Raises |
|---|---|---|
| `list_subjects` | All subjects, active and inactive, sorted by `(name_key, id)` in Python (research D3). | — |
| `get_subject` | The subject. | `SubjectNotFound` |
| `create_subject` | Cleans the name. If another subject has the same key, refuses. Otherwise inserts with `is_active=True` and commits. An `IntegrityError` on commit (a concurrent insert) → rollback, then `DuplicateSubjectName`, naming the subject that now exists. | `SubjectNameError`, `DuplicateSubjectName` |
| `rename_subject` | Loads the subject, then cleans the name. A duplicate is any **other** subject with the same key. If both `name` and `name_key` are unchanged: no write. Otherwise updates `name`, `name_key` and `updated_at`, then commits. An `IntegrityError` on commit → rollback, then `DuplicateSubjectName`. | `SubjectNotFound`, `SubjectNameError`, `DuplicateSubjectName` |
| `set_subject_active` | If the status is already `active`: no write. Otherwise sets it, updates `updated_at` and commits. | `SubjectNotFound` |
| `count_subject_uses` | How many records refer to the subject. **Returns `0` in this milestone.** Milestones 9 (questions) and 10 (competitions) add their counts here (research D4). | — |
| `delete_subject` | Loads the subject. If `count_subject_uses > 0`, refuses. Otherwise deletes and commits. An `IntegrityError` on commit (a future foreign key) → rollback, then `SubjectInUse`. | `SubjectNotFound`, `SubjectInUse` |

Validation happens before any duplicate lookup. For `rename_subject`, `SubjectNotFound` comes
first, so a rename of a deleted subject reports "not found" rather than a name error.

## Tests the contract implies

- **`tests/unit/test_subject_schemas.py`**: every row of the validation table, including:
  - "Фізика" and "ФІЗИКА" give the same key;
  - "ß" and "SS" give the same key;
  - NFC and NFD forms of "é" give the same key;
  - 200 code points is accepted and 201 is refused;
  - a leading tab, an inner line break, U+2028 and U+202E are refused;
  - inner double spaces are kept.
- **`tests/integration/test_subject_service.py`** (both engines):
  - each function's behaviour and errors;
  - a no-op rename or status change leaves `updated_at` unchanged;
  - the unique constraint rejects a direct duplicate insert (the concurrency guarantee);
  - sorting is case-insensitive and stable;
  - `delete_subject` is refused when `count_subject_uses` is monkeypatched to return `1`.
