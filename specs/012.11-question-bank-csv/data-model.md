# Data Model: Exporting and Importing a Subject's Questions as CSV Files (Milestone 12.11)

**No schema change and no migration.** Nothing new is stored. The milestone reads and writes the
existing `questions` table (milestones 11 and 12.9), and the rest are values in memory during one
request.

## 1. Stored tables used (unchanged)

### `questions` (milestone 11, 12.9)

| Column | Read by | Written by the import |
|---|---|---|
| `id` | export order (ascending), counts | new ids, in file order, from the sequence / `AUTOINCREMENT`; never reused |
| `subject_id` | every query | the subject imported |
| `text` | export column `question` | the row's cleaned `question` |
| `reference_answer` | export column `answer` | the row's cleaned `answer` |
| `is_additional` | export column `additional` (`1`/`0`) | the row's `additional` |
| `created_at`, `updated_at` | — | the import's `now`, the same for every row |
| `deleted_at` | `IS NULL` for the export and the counts | set to `now` on every listed question of the subject (soft delete); never cleared |

The rules that matter:

- A soft-deleted question stays stored unchanged apart from `deleted_at`. The competitions'
  copies (`competition_questions`, milestone 12.2) are separate rows and are never written.
- `count_subject_uses` (milestone 6) counts every question, deleted ones included, so a subject
  that has had questions can never be deleted.

### `subjects` (milestone 6)

Read only: its `name` goes into the export file name and onto the import page. It is read `FOR
SHARE` at the start of an import (research R6). Both active and deactivated subjects are allowed.

## 2. Values in memory

### `QuestionRow` (`app/services/question_csv.py`)

```text
QuestionRow(text: str, reference_answer: str, is_additional: bool)   # frozen
```

One question of a file: written by the export and produced by a check that found no error. The
text and answer are already cleaned by `clean_question_field`: 1–2,000 characters, `\n` line
endings, no NUL. A `QuestionRow` has no field for a bank number or a competition (spec FR-021).

### `QuestionFileError`

```text
QuestionFileError(row: int | None, message: Text)                     # frozen
```

- `row is None`: an error of the whole file (no file, too large, not UTF-8, the header, no
  question, too many). There is at most one per check, and it is shown on the file field and
  first in the summary.
- `row` set: a row error, already worded "Row N: …", shown unlinked in the summary. The unclosed
  quote is a row error whose message names its row itself.

### `QuestionFileCheck`

```text
QuestionFileCheck(rows: tuple[QuestionRow, ...], errors: tuple[QuestionFileError, ...])
  .ok -> bool                      # no errors; rows is then 1..1000 long
  .file_error -> Text | None       # the whole-file error, if any
  .row_errors -> tuple[Text, ...]  # the first ERRORS_SHOWN (20) errors in all, minus the file error
  .more -> int                     # max(0, len(errors) - ERRORS_SHOWN)
```

The limit counts every error, the whole-file one included: 20 errors are shown at most, in all.
When `errors` is not empty, `rows` is empty, so a refused file can never reach
`replace_questions`.

### `Upload` (`app/routers/uploads.py`)

```text
Upload(data: bytes | None, too_large: bool)
```

`data is None` and `not too_large` means no file was chosen. With `too_large`, `data` is `None`
and the body was never kept. The check turns these into the first two errors of research R3.

### `Replaced` (`app/services/question_bank_files.py`)

```text
Replaced(deleted: int, added: int)
```

What one import did, for the log line.

## 3. Constants (`app/services/question_csv.py`)

| Name | Value | Used by |
|---|---|---|
| `HEADER` | `("question", "answer", "additional")` | writer, header check, README test |
| `MAX_FILE_BYTES` | `2 * 1024 * 1024` | upload, check, hint, README test |
| `MAX_QUESTIONS` | `1000` | check, README test |
| `ERRORS_SHOWN` | `20` | `QuestionFileCheck` |
| `QUESTION_FIELD_MAX_LENGTH` | `2000` (existing, `app.schemas.question`) | check, README test |

## 4. State transitions

A question of the imported subject goes from listed (`deleted_at IS NULL`) to deleted
(`deleted_at = now`), the same one-way transition as a teacher's deletion. Each row of the file
becomes a new listed question. Nothing else changes state: the subject, competitions, their
copies, answers, grades and results files all stay as they were.
