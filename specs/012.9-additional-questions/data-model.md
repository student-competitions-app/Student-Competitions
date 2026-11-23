# Data Model: Additional Questions in the Question Bank (Milestone 12.9)

What changes in the stored data and in the views the services return. Decisions:
[research.md](./research.md) R1, R2, R3, R6.

## 1. `questions` (changed)

| Column | Type | Null | Default | New | Notes |
|---|---|---|---|---|---|
| `id` | integer, PK | no | `AUTOINCREMENT` / sequence | | The number shown, "Question 57" (milestone 11) |
| `subject_id` | integer, FK → `subjects.id` | no | | | Never changes |
| `text` | varchar(2000) | no | | | |
| `reference_answer` | varchar(2000) | no | | | |
| `created_at` | timestamptz | no | | | |
| `updated_at` | timestamptz | no | | | Reset by an edit that changes the text, the answer **or the mark** |
| `deleted_at` | timestamptz | yes | | | Soft deletion (milestone 11) |
| **`is_additional`** | **boolean** | **no** | **`false`** (server default) | ✅ | The mark **additional question** |

Model (`app/models/question.py`):

- `is_additional: bool`, declared with `nullable=False`, the Python default `False` and the server
  default `false()`.
- Its docstring: the mark is part of the question, changed only through the edit form by a teacher
  with **Can manage competitions**, read for other teachers only to leave the question out.

**Rules**:

- A new question is not additional unless the form marks it (FR-001).
- The mark changes only through `update_question`. That needs a listed question (not deleted) of an
  active subject, so a deleted question and a question of a deactivated subject keep their mark
  (FR-005). `delete_question` sets `deleted_at` only.
- The mark is not personal data: who set it, and when, is not stored. Data erasure leaves it alone.
- `competition_questions` is **unchanged**: a copy holds no mark (FR-022).

## 2. Views (service return types)

### `QuestionView` (`app/services/questions.py`), changed

| Field | Type | New | Notes |
|---|---|---|---|
| `id` | int | | Also the number shown |
| `subject_id` | int | | |
| `text` | str | | |
| `reference_answer` | str | | |
| **`is_additional`** | **bool** | ✅ | Always filled: every reader of a `QuestionView` either has the setting (forms, **Add questions**, the list with additional questions) or never gets an additional one (the list without them) |

`QuestionPage` is unchanged. It holds the views and the `Paging`, built from the count of exactly
the questions listed (R3).

### `CompetitionQuestionView` (`app/services/competition_entries.py`), changed

| Field | Type | New | Notes |
|---|---|---|---|
| `question_id` | int | | The bank number shown |
| `text`, `reference_answer` | str | | The copy |
| `deleted_from_bank` | bool | | Live from the bank (012.2 R11) |
| **`is_additional`** | **bool \| None** | ✅ | Live from the bank when the caller asked for the mark (`with_bank_mark=True`); `None` when it did not, so it was never read |

## 3. Who reads what

| Reader | Bank questions read | Mark read |
|---|---|---|
| **Questions** tab, teacher with the setting | every listed question | yes |
| **Questions** tab, every other teacher | listed questions with `is_additional = false` only (count and rows) | no (all are false) |
| Add / edit / delete pages and actions | only after the setting check | yes (forms) |
| **Add questions** page of a competition | every listed question (setting checked first) | yes |
| A competition's **Questions** page, teacher with the setting | the copies, joined to the bank | yes, live |
| A competition's **Questions** page, every other teacher | the copies, joined to the bank for `deleted_at` only | no (`None`) |
| Remove confirmation, answer and grading sheets, results files | the copies | no |

## 4. Migration

One Alembic revision, `down_revision = "c730fd883079"`, file
`migrations/versions/2026_11_<dd>_<rev>_additional_questions.py`.

- **Upgrade**:
  `batch_alter_table("questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True})`,
  then `add_column(Column("is_additional", Boolean(), nullable=False, server_default=sa.false()))`.
  Every existing row, deleted ones included, gets `false` (FR-002). On SQLite no table copy is
  needed; on PostgreSQL it is one `ALTER TABLE`.
- **Downgrade**: the same batch block with `drop_column("is_additional")`. On SQLite the table is
  copied with `AUTOINCREMENT` kept (R2). Lossy: every mark is dropped.
- **No data step and no index.**
- A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.

## 5. Invariants checked by tests

- After the upgrade, `count(*) WHERE is_additional` is 0 (SC-004).
- For a teacher without the setting, the paging total of a subject equals
  `count(*) WHERE subject_id = ? AND deleted_at IS NULL AND NOT is_additional` (SC-001).
- Changing `questions.is_additional` changes no row of `competition_questions`, `team_answers`
  (grades included) or `competition_results_files` (SC-005).
- SQLite: `questions` keeps `AUTOINCREMENT` at head and after the downgrade and upgrade again.
