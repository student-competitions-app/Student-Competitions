# Research: Exporting and Importing a Subject's Questions as CSV Files (Milestone 12.11)

**Date**: 2026-11-28 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Every decision below follows the spec and the milestone; the spec's assumptions are taken as
decided unless `/speckit-clarify` changes them. No `NEEDS CLARIFICATION` remains.

## R1. Where the code goes

**Decision**: one pure module and one database module, both new, plus the existing admin router.

- `app/services/question_csv.py`, pure, with no I/O and no database: the format's constants, the
  writer, the parser and every check of a file. It is tested without a database, the README
  example included.
- `app/services/question_bank_files.py`, the database side: the counts per subject, the rows to
  export, the export file name, the bank lock and `replace_questions`.
- `app/routers/admin_subjects.py` gains the new routes. It stays thin and keeps the milestone 6
  shape: a handler maps the service's exceptions to a status and a page.
- `app/routers/uploads.py`, new: the dependency that reads one uploaded file (R7).
- `app/routers/downloads.py` gains `csv_download`, next to `pdf_download` (R4).

**Rationale**: the format is the part most likely to be wrong and the part the README must agree
with, so it is kept pure and tested hard. The database work is small and follows
`app/services/questions.py`.

**Alternatives considered**:

- **Adding the functions to `questions.py`**: rejected. That module is the teacher's bank, and
  every write there checks **Can manage competitions**. The import is an administrator's write
  with different rules.
- **Adding them to `subjects.py`**: rejected. That module is about subjects themselves.

## R2. Parsing: a small parser of our own, not the `csv` module

**Decision**: `question_csv.parse_records(text, separator)` is a small RFC 4180 state machine. It
yields `(row, fields)` per record and raises `UnclosedQuote(row)` at the end of the text while a
quoted field is still open. `row` is the record's number as a spreadsheet shows it: the header is
row 1, and every record counts, empty ones included. Its rules:

- A field that starts with `"` is quoted. Inside it, `""` is a quote and `\r`, `\n` and the
  separator are characters. The quote that closes it may be followed by more characters before
  the next separator or line break; they are kept after the text, as spreadsheets read
  `"abc"def`.
- A `"` anywhere else in a field is a character (FR-029). Spaces before an opening quote make the
  field unquoted, as in the `csv` module and in spreadsheets.
- A record ends at `\r\n`, `\n` or a lone `\r` outside quotes. A line break at the very end of
  the text does not start an empty record; a blank line before it does.
- The scanning uses `str.find` and regular expressions over the text, not one Python step per
  character, so a 2 MB file is parsed in well under a second (R11).

**Rationale**: the standard `csv` module was tried on the spec's cases:

| Case | `csv`, `strict=False` | `csv`, `strict=True` | Needed |
|---|---|---|---|
| Unclosed quote | rest of the file silently becomes one field | `Error` at end of data, with no opening row | refused at the row where it opens (FR-037) |
| `"abc"def` | `abcdef` | `Error` | `abcdef` (spreadsheets) |
| `The "Iliad"` unquoted | kept | kept | kept |
| Blank line | `[]` record | `[]` | empty row, counted |

No single mode gives FR-037 together with the lenient reading a spreadsheet's file needs. A parser
of about 60 lines gives both, and tests can pin it exactly.

**Alternatives considered**:

- **`csv` plus a pre-scan for unbalanced quotes**: rejected. The pre-scan is the same state
  machine, and the two would have to agree.
- **A third-party CSV library**: rejected. It would be a new runtime dependency (constitution
  Principle II), with the same gaps.

## R3. Reading and checking a file

**Decision**: `question_csv.check_question_file(data: bytes | None) -> QuestionFileCheck` runs
these steps in order ([contracts/csv-format.md](./contracts/csv-format.md) §3):

1. **No file** (`None`, R7): "Choose a CSV file." Stop.
2. **Size**: more than `MAX_FILE_BYTES = 2 * 1024 * 1024` bytes gives "The file can be at most
   2 MB." Stop.
3. **Decoding**: one leading UTF-8 byte-order mark is dropped, then the bytes are decoded as
   strict UTF-8. A failure gives "Save the file as CSV UTF-8." Stop. UTF-16 (whose BOM is not
   valid UTF-8) and Windows-1251 Cyrillic both fail here.
4. **Separator**: taken from the text up to the first line break. A comma means `,`; otherwise a
   semicolon means `;`; otherwise the header is wrong. Stop.
5. **Header**: the first record, each name stripped of spaces and case-folded, must be exactly
   `question`, `answer`, `additional`. An empty text, a missing header or any other header (a
   fourth, empty field included) gives "The first row must be the header: question, answer,
   additional." Stop.
6. **Rows**: every further record, in order:
   - empty when every field is empty after `strip()`: skipped, but it keeps its row number;
   - a width other than 3: "Row N: The row must have 3 fields.", and nothing else for that row;
   - otherwise `question`, then `answer`, cleaned by `app.schemas.question.clean_question_field`
     (the add form's rules and messages); then `additional`, stripped, where `""` and `"0"` mean
     not additional and `"1"` means additional, and anything else is "Row N: Additional must be 0,
     1 or empty.".
7. **Unclosed quote**: `UnclosedQuote(row)` from the parser adds "A quote opened in row N is
   never closed." after the errors already found, and the check stops.
8. **Count**: no non-empty row gives "The file holds no questions."; more than `MAX_QUESTIONS =
   1000` gives "The file can hold at most 1,000 questions.". Either is a whole-file error, placed
   before the row errors. The rows are still checked.

The result holds either the clean rows (no error) or the errors: at most one whole-file error,
then the row errors in row order and, within a row, in column order. A row error's text is one
catalogue message, `"Row %(row)d: %(message)s"`, around the field's own translated message.

**Rationale**: FR-034 to FR-040 and the spec's assumptions. Steps 1 to 5 stop because nothing
after them can be read. Step 8 keeps checking, so one round fixes every bad row.

**Alternatives considered**: guessing the encoding (`chardet`) or accepting Windows-1251. Both
are rejected by the milestone: it asks for one clear message.

## R4. The export file and its response

**Decision**:

- `question_csv.write_question_csv(rows) -> bytes`: `"﻿"`, then `csv.writer` with
  `QUOTE_MINIMAL`, `lineterminator="\r\n"`, the header `question,answer,additional`, one row per
  question with `1`/`0`, encoded UTF-8. The `csv` module's writer is exactly RFC 4180 for
  writing: it quotes a field holding `,`, `"`, `\r` or `\n` and doubles the quotes. Texts are
  written exactly as stored, line breaks as `\n`, with no formula prefix (FR-020).
- `question_bank_files.export_rows(session, subject_id)`: the subject's questions with
  `deleted_at IS NULL`, additional ones included, ordered by `id` ascending ("oldest first",
  as the study materials in milestone 12.10).
- `question_bank_files.export_file_name(subject_name, today)`: `f"{clean_file_stem(name,
  fallback)} {today:%Y-%m-%d} {_('question bank')}.csv"`. `today` is the date in Kyiv from
  `app.services.competitions.utc_now`, the clock the 12.10 files use, so tests move it the same
  way.
- `downloads.csv_download(content, file_name)`: the same headers as `pdf_download`
  (`attachment` with the ASCII and RFC 5987 names, `no-store`, `nosniff`), with media type
  `text/csv; charset=utf-8`. Both share one private `_attachment(content, file_name, media_type)`.
- Nothing is logged on an export, as for the 12.10 downloads.

**Rationale**: FR-013 to FR-021. The same response shape as the existing downloads, so the
browser saves the file at once and the loading script skips `a[download]`.

**Known risk (not changed, for the product owner)**: Excel with a Ukrainian regional setting uses
`;` as its list separator. Opening the comma-separated export by **double-click** may then put
each whole row into column A. Opening it through **Data → From Text/CSV** splits it correctly, and
LibreOffice asks for the separator. The milestone fixes commas for the export, and the README
section says how to open the file. A `sep=,` first line would fix the double-click, but it breaks
the header row, and Excel then ignores the byte-order mark (Cyrillic breaks). It is therefore not
used. The product owner checks this on a real Excel during the screenshot step and may change the
milestone.

## R5. Replacing the questions in one transaction

**Decision**: `replace_questions(session, subject_id, rows) -> Replaced(deleted, added)`:

1. The subject is read `FOR SHARE` with `populate_existing`. If it is missing:
   `SubjectNotFound`, after a rollback. An active or a deactivated subject is fine.
2. `lock_question_bank(session)` (R6).
3. A single `UPDATE questions SET deleted_at = :now WHERE subject_id = :id AND deleted_at IS
   NULL`. Its row count is `deleted`. Only `deleted_at` changes, exactly as a teacher's deletion
   does (milestone 11 FR-004).
4. One `INSERT` of every row in file order, through `session.execute(insert(Question), [...])`.
   SQLAlchemy sends it as a multi-row `VALUES` (insertmanyvalues), one statement per 1,000 rows.
   Each row has `created_at = updated_at = now`, `deleted_at = NULL` and its `is_additional`.
5. Commit, then one log line: `Questions imported: subject=%d deleted=%d added=%d`.

Ids, and so the order: on SQLite, `AUTOINCREMENT` gives ids in insert order. On PostgreSQL,
`nextval` is evaluated per row while the `VALUES` list is scanned in order. A test inserts 1,000
rows on both engines and checks that the ids follow the file. New ids are always above every
existing id, so the numbers of deleted questions are never reused (FR-042).

**Rationale**: FR-041 to FR-047. Two statements, whatever the file's size, keep the transaction
short (R11). Competitions are never touched: their copies (milestone 12.2) are independent rows,
and a deleted source shows "Deleted from the question bank" as today. The study materials cache
(12.10 R6) compares what it reads, so it shows the new bank at the next download with no code
change. `count_subject_uses` already counts deleted questions, so the subject stays undeletable.

**Alternatives considered**:

- **An ORM `add_all`**: rejected. It is the same statements, plus a refresh per row that is not
  needed.
- **Diffing the file against the bank to keep unchanged questions**: rejected. The milestone
  says the import replaces, and the file holds no numbers.

## R6. Locking the bank for writing

**Decision**: `lock_question_bank(session)` does the following on each engine:

- **PostgreSQL**: `LOCK TABLE questions IN EXCLUSIVE MODE`. It conflicts with `ROW EXCLUSIVE`
  (every `INSERT`/`UPDATE`/`DELETE`) and `ROW SHARE` (`SELECT … FOR UPDATE / FOR SHARE`), and
  allows `ACCESS SHARE` (a plain `SELECT`). So every write of the bank waits, and reading it does
  not (FR-048). That covers a teacher's add, edit, delete and mark (their `FOR UPDATE`/`FOR SHARE`
  reads wait at the start), another import, and adding a question to a competition (which reads
  the question `FOR SHARE`, milestone 12.2). These wait a moment, since an import takes well under
  a second. The lock is released at commit or rollback.
- **SQLite**: nothing. The `UPDATE` of step 3 is the transaction's first write, so pysqlite opens
  it there and takes the database's write lock. Other writers wait for it (the busy timeout,
  5 s), and readers are not blocked. The subject read in step 1 runs outside a transaction under
  pysqlite's default transaction handling, so no read-to-write lock upgrade can fail.

**Lock order and deadlocks (PostgreSQL)**: the import takes the subject `FOR SHARE` first, then
the table.

- A teacher's add holds the subject `FOR SHARE` too; the two are compatible, and the add's
  `INSERT` simply waits for the import.
- A subject deletion takes the subject row `FOR UPDATE` and then checks `questions` for the
  foreign key. If it starts first, the import waits on the subject row, the deletion finishes, and
  the import answers "Subject not found". If the import starts first, the deletion waits on the
  subject row.
- Taking the table first would let a deletion and an import deadlock, so the order is fixed and
  commented in the code.

**Rationale**: constitution Principle VII allows a database-specific feature when it is justified
in the plan. Row locks cannot make an `INSERT` of a new question wait, so only a table lock gives
"either before the import and replaced, or after it".

**Alternatives considered**:

- **An advisory lock taken by every bank write**: rejected. Every existing write would need to
  take it, and a missed one would be silent.
- **`SHARE ROW EXCLUSIVE`**: rejected. It allows `ROW SHARE`, so a teacher's edit could take the
  question row `FOR UPDATE` and then deadlock with the import's `UPDATE`.
- **`SERIALIZABLE`**: rejected. It fails instead of waiting, and the milestone asks for waiting.

## R7. Reading the upload after the access check

**Decision**: a dependency in `app/routers/uploads.py`,
`uploaded_file(field="file", max_bytes=MAX_FILE_BYTES)`, returns `Upload(data: bytes | None,
too_large: bool)`:

- **The handler declares no `Form`/`File` parameter.** FastAPI parses such bodies *before*
  solving dependencies, so the application-wide `resolve_access` (role and cross-site checks)
  would run after a teacher's 2 MB upload had been read. As a dependency listed after it, the body
  is read only once the request is allowed (FR-007, FR-008).
- **Too large.** A `Content-Length` above `max_bytes + 16 KiB` (the multipart overhead) means
  `too_large`. The body is drained and discarded, up to 16 MiB, so the browser receives the page
  rather than a reset connection; it is never stored. Otherwise the dependency calls
  `request.form(max_files=1, max_fields=2)`. A `MultiPartException` (a malformed body) is read as
  no file.
- **No file.** The file part is an `UploadFile`. A filename of `""` with empty content is "no
  file chosen", which is what a browser sends for an empty file field. Otherwise up to
  `max_bytes + 1` bytes are read, and more than `max_bytes` means `too_large`. The form is closed
  in a `finally`.
- **The extension is not checked**: the content decides (spec assumption).

The handler stays a sync `def`, like every admin handler. Only the dependency is `async`, like
`prefixed_fields` in `teacher_team_answers.py`.

**Rationale**: the existing access design (milestone 5) relies on dependency order. Starlette's
own `max_part_size` limits non-file fields only, and files are spooled to a temporary file above
1 MB, so the size has to be limited by us.

## R8. Routes and pages

**Decision** ([contracts/http-routes.md](./contracts/http-routes.md)): all under
`/admin/subjects/{subject_id:int}`, all `@allow_roles(Role.ADMIN)`:

| Method | Path | Answer |
|---|---|---|
| GET | `/deactivate` | confirmation page (new) |
| POST | `/deactivate` | unchanged |
| GET | `/activate` | confirmation page (new) |
| POST | `/activate` | unchanged |
| GET | `/questions/export` | the CSV file |
| GET | `/questions/import` | the import page |
| POST | `/questions/import` | 303 to `/admin/subjects`, or 400 with the page and the errors |

- An unknown subject gives the milestone 6 "Subject not found" page with 404, on every route.
- A GET confirmation page is shown whatever the subject's status. Confirming a status it already
  has changes nothing (milestone 6 FR-026, spec FR-005).
- The list gets the counts from one grouped query, `question_counts(session) -> dict[int, int]`
  (`deleted_at IS NULL`, additional included). A subject missing from the dict has `0`.

## R9. Components

**Decision** ([contracts/components.md](./contracts/components.md)):

- **`confirmation(...)`** gains three keyword arguments:
  - `form_content=False`: when it is set, the caller's block and the buttons are inside one
    `<form method="post">`, and the confirming button is a plain submit `button`, not a
    `post_button`;
  - `sends_file=False`: adds `enctype="multipart/form-data"`, and needs `form_content`;
  - `summary=None`: an already-rendered error summary, placed right under the `h1`, as the
    guidelines put it on every form page.

  Without the new arguments the output is byte-identical, which the gallery test checks.
- **`file_field(id, label, error=None, hint=None, accept=None, name=None, attrs={})`** in
  `form.html`: label, hint, error and a native `<input type="file">` with `aria-describedby`, and
  never a `value`.
- **`error_summary(errors, form_error=None, order=None, row_errors=(), more=0)`**: after the
  linked field errors, each `row_errors` entry is a plain `<li>` (not linked). With `more > 0`,
  "And %(num)d more error(s)." follows the list, as an `ngettext` message.
- **CSS**: the file input takes the field's spacing and focus ring from the existing tokens. The
  "more" line is in the summary's text colour. No new token.
- **Gallery**: new sections `#file-field`, `#confirmation-with-form`, and row errors with the
  "more" line in the existing `#forms` section.

**Rationale**: FR-051 to FR-054. `summary` is a slot rather than three more error arguments, so
the confirmation does not need to know the summary's variants.

## R10. The Subjects tab

**Decision**: `subjects.html` uses `data_table([Name, Status, Questions, Actions])`, where
**Questions** is a plain number cell. The actions are `actions_menu(s.name)` with:

- `menu_link(Rename)`;
- `menu_link(Export questions, download=True)`;
- `menu_link(Import questions, destructive=True)`;
- `menu_link(Deactivate, destructive=True)` or `menu_link(Activate)`;
- `menu_link(Delete, destructive=True)`.

`post_button` is no longer used on the page. The two new confirmation pages,
`subject_deactivate.html` and `subject_activate.html`, follow `institution_deactivate.html`, with
the question as the `h1`, the consequence, and the verb and **Cancel** back to `/admin/subjects`.

**Form contract**: the `admin-subjects` case loses its two post forms. That is a deliberate
contract change, recorded in `test_form_contract.py`'s docstring. The new cases
`admin-subject-deactivate`, `admin-subject-activate`, `admin-subject-import` and
`admin-subject-import-errors` are generated once with `UPDATE_FORM_CONTRACT=1` for those cases
only, as in earlier milestones.

## R11. Performance

**Decision and measurement plan**:

- **The worst file**: 1,000 questions, each with a 900-character text and answer, close to 2 MB.
- **Parse and check**: the regular-expression scanner (R2) and `clean_question_field` on 2,000
  fields; expected well under 1 s.
- **Replace**: two statements on PostgreSQL. On Neon with about 20 ms round trips, under 1 s.
- **Export of 1,000 questions**: one query and `csv.writer`; expected about 100 ms.

The timings of the import (parse plus replace) and the export are measured once on both engines
and recorded in the task's notes, against SC-009 (10 s and 2 s).

## R12. The README section and its test

**Decision**:

- **The section**: README gets `## Question bank CSV files` after `## Requirements`, written to
  the spec's US6 and FR-056 to FR-058. Its subsections are: what the file is for; the format; the
  limits; what the import does; how to write good content; how to open and save the file in a
  spreadsheet (including Excel's **From Text/CSV** with a Ukrainian regional setting, R4); the
  example; the checklist.
- **The example**: one fenced block marked ` ```csv ` under `### Example file`. It holds four
  Ukrainian questions, one additional, with a comma, a doubled quote and a line break inside
  quoted fields.
- **The test** (`tests/unit/test_question_csv.py::test_readme_example_imports`):
  - it reads `README.md`, finds the section by its heading and the first `csv` block in it;
  - it checks the block's text both with and without a byte-order mark, and expects no error;
  - it checks the rows' order and that only the expected row is additional;
  - an integration test also imports the block through the route.
- **The limits**: a second test checks that the numbers written in the section (2,000 characters,
  1,000 questions, 2 MB) are the constants of `question_csv`. If a limit changes, the README has
  to change with it.

## R13. Tests

**Decision**: pytest on both engines.

- **`tests/unit/test_question_csv.py`** (new, pure):
  - the parser on every case of R2: the unclosed quote's row, multi-line rows, blank and `;;`
    rows, `"abc"def`, an unquoted quote, a final line break;
  - every check and message of R3, the order of the errors, the row numbers and two errors from
    one row;
  - the writer: BOM, CRLF, quoting, the `=` text, the header only;
  - a round trip through the writer and the checker;
  - the README example and its limits.
- **`tests/integration/test_question_bank_files_service.py`** (new):
  - the counts, the export rows and the file name;
  - `replace_questions`: the deleted questions stay stored, the order and ids of 1,000 rows,
    other subjects untouched, competition copies untouched, the subject still undeletable, and
    the log line;
  - on PostgreSQL, with `SET LOCAL lock_timeout = '300ms'` as in `test_results_service.py`:
    - a held bank lock makes a teacher's `create_question`, `update_question`,
      `delete_question` and a second import time out, while `question_page` reads at once;
    - a teacher's held question `FOR UPDATE` makes the import wait;
    - an import into a subject being deleted gets `SubjectNotFound`.
- **`tests/integration/test_admin_question_files.py`** (new): through the routes:
  - access for every role and the 404;
  - the menu and its order, and the column;
  - the confirmation pages;
  - the download headers and the name in both languages;
  - the import page and its count;
  - every refused file with its row numbers and an unchanged bank, and 25 bad rows;
  - the spreadsheet variants;
  - the empty file field after an error;
  - an oversized `Content-Length`;
  - a cross-site post refused.
- **Updated**:
  - `test_admin_subjects.py`: the list markup, deactivate and activate through the pages;
  - `test_routes.py` and `test_access_control.py`: the new routes;
  - `test_component_gallery.py`: the three patterns, and the confirmation unchanged without its
    new arguments;
  - `test_form_contract.py` and its JSON (R10);
  - the catalogue checks.
- **By hand**: the screenshots of the file field and the import page in both languages and
  themes, and the Excel double-click check (R4).
