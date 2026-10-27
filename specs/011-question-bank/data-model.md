# Data Model: Question Bank (Teacher) (Milestone 11)

Phase 1 of [plan.md](./plan.md). The decisions are in [research.md](./research.md) R1–R3, R12 and
R16.

## 1. Question: table `questions` (changed)

| Column | Type | Null | Rules |
|---|---|---|---|
| `id` | `INTEGER` primary key | no | **The question's number.** Given once in creation order and never reused: a PostgreSQL sequence; SQLite `AUTOINCREMENT` (R1). Never changes. |
| `subject_id` | `INTEGER`, FK → `subjects.id` (no `ON DELETE`), index `ix_questions_subject_id` | no | **NEW.** Set at creation and never changed: an edit ignores any subject sent (FR-001, FR-031). |
| `text` | `VARCHAR(2000)` | no | **Was 1000.** Cleaned by `clean_question_field`: CR/CRLF become LF, NUL is refused, the value is trimmed, then 1–2,000 code points. Inner line breaks are kept (FR-002, R4). |
| `reference_answer` | `VARCHAR(2000)` | no | **Was 5000.** Same rules as `text`. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no | Set once at creation (UTC). |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no | Set at creation, and reset by an edit that changes something. A deletion leaves it alone. |
| `deleted_at` | `TIMESTAMP WITH TIME ZONE` | yes | **NEW.** `NULL` while listed; set once by a deletion and never cleared (FR-004, R2). |

**Model** (`app/models/question.py`):

- `__table_args__ = {"sqlite_autoincrement": True}`.
- Both text columns use `QUESTION_FIELD_MAX_LENGTH` from `app/schemas/question.py`.
- The milestone 3 docstring rule "never rendered on a public page" becomes "shown only in the
  teacher area".

**Derived states**:

| State | Condition | Listed | Edit or delete | Milestone 12 may add it |
|---|---|---|---|---|
| Listed | `deleted_at IS NULL` and subject active | yes | yes (with the setting) | yes |
| Hidden by its subject | `deleted_at IS NULL` and subject deactivated | no | no: "not found" | no (subject not offered) |
| Deleted | `deleted_at IS NOT NULL` | never | no: "not found" | **never** |

**Transitions**:

```text
(none) --create--> Listed --delete--> Deleted   (terminal; no restore, FR-004)
Listed <--subject deactivated / activated--> Hidden by its subject
```

- **An edit** keeps a question Listed and changes `text`, `reference_answer` and `updated_at`.
- **The subject and the number** never change.

**Queries**:

- **Listed questions of a subject**: `WHERE subject_id = :s AND deleted_at IS NULL`, with
  `ORDER BY id DESC LIMIT 10 OFFSET (page − 1) × 10`, plus a matching `count(*)`.
- **Uses of a subject**: `SELECT count(*) FROM questions WHERE subject_id = :s`, deleted rows
  included (FR-040, R16).
- **Where the list lands after a deletion**, for a deleted question `q` of subject `s` (R8):
  - its index `i` = the number of listed questions of `s` with `id > q.id`, counted before the
    deletion;
  - the next question = the largest listed `id < q.id`;
  - the previous question = the smallest listed `id > q.id`.

**Not stored**: who added or last changed a question (spec Assumptions, FR-049). Questions
therefore hold no personal data and are untouched by data erasure.

## 2. Subject: table `subjects` (unchanged schema)

- **Deactivated** (`is_active = false`):
  - the bank stops offering the subject and treats it as "not found" for every question page and
    action;
  - its questions are kept and come back unchanged when it is activated again (FR-041).
- **In use**: `count_subject_uses` now counts every question row of the subject. A subject with any
  question, deleted or not, cannot be deleted (FR-040, SC-004).
- **The foreign key** `questions.subject_id` is the PostgreSQL backstop under a race (R7, R16).

## 3. Teacher profile: table `teacher_profiles` (changed)

| Column | Change |
|---|---|
| `can_create_competitions` | **Renamed** `can_manage_competitions`, `BOOLEAN NOT NULL`. Every value is kept by the rename (FR-009, SC-006). |

**Meaning**:

- **True**: the teacher may add, edit and delete any question in the bank, and, from milestone 12,
  create and change competitions.
- **False, or no profile row** (the test cast's seeded teachers): the teacher reads the bank only.

**The one reader for access decisions**: `teacher_access.can_manage_competitions`. With `lock=True`
it reads the row `FOR SHARE` inside a write's transaction (R5, R7).

## 4. Teacher invitation (sealed, not stored)

**The payload's `details`**:

- **Written**: `{"institutions": [[id, "read"|"write"], …], "can_manage_competitions": bool}`.
- **Also read**: the milestone 8 key set `{"institutions", "can_create_competitions"}`. Its boolean
  becomes `TeacherDetails.can_manage_competitions` (US6-3, R12).
- **Refused**: any other key set, as today.

## 5. Validation rules (from the spec)

| Rule | Where | Refusal |
|---|---|---|
| Text and answer required, trimmed, 1–2,000 code points, line breaks kept, CR/CRLF become LF, NUL refused | `app/schemas/question.py` `clean_question_field` | field error, 400, values kept (FR-002, FR-029, FR-039) |
| Duplicate texts allowed | nowhere: no unique constraint | none (US1-6) |
| Subject active and existing (add) | `services.questions.create_question`, router | 404 "Subject not found" (FR-038) |
| Question existing, not deleted, subject active (edit, delete) | `services.questions` | 404 "Question not found" (FR-038) |
| Teacher has the setting (add, edit, delete, and their pages) | router first, then the service under lock | 403 (FR-007, FR-037) |
| Subject cannot change | the edit reads no subject | the value is ignored (FR-031) |
| A subject with questions cannot be deleted | `services.subjects.count_subject_uses` | 409 with "deactivate instead" (FR-040) |

## 6. Migration `question_bank` (revision after `596ead9f1205`)

**Upgrade**:

1. `DELETE FROM questions`: the milestone 3 sample questions (FR-042).
2. `batch_alter_table("questions", recreate="always", table_kwargs={"sqlite_autoincrement": True})`:
   - add `subject_id INTEGER NOT NULL`, with the FK `fk_questions_subject_id_subjects` and the
     index `ix_questions_subject_id`;
   - add `deleted_at TIMESTAMP WITH TIME ZONE NULL`;
   - alter `text` to `String(2000)` and `reference_answer` to `String(2000)`.
3. `batch_alter_table("teacher_profiles")`: rename `can_create_competitions` to
   `can_manage_competitions`.

The migration is a frozen snapshot: plain SQLAlchemy types, no imports from `app`, and constraint
names following the project's naming convention.

**Downgrade** (lossy by design, R3):

1. Rename the setting back.
2. `DELETE FROM questions`.
3. Drop `deleted_at`, the index, the FK and `subject_id`; restore `String(1000)` and
   `String(5000)`, without `AUTOINCREMENT`.

The sample questions are not re-inserted.

**Tests** (`test_migrations.py`):

- empty `questions` at head;
- an upgrade from the previous head with the samples and two teacher profiles (`true`, `false`):
  the samples are gone, and both values are kept under the new name;
- the stairway and the drift check, on both engines.
