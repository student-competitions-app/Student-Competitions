# Implementation Plan: Exporting and Importing a Subject's Questions as CSV Files (Milestone 12.11)

**Branch**: `012.11_csv_export_import` | **Date**: 2026-11-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.11-question-bank-csv/spec.md`

## Summary

Administrators export a subject's question bank to a CSV file, and import a CSV file that
replaces it, from the **Subjects** tab. There is no schema change.

- **The Subjects tab** ([research R10](./research.md)):
  - a **Questions** column shows the counts, from one grouped query;
  - each row's actions move into the 12.1 actions menu: **Rename**, **Export questions**,
    **Import questions**, **Deactivate**/**Activate**, **Delete**;
  - **Deactivate** and **Activate** get confirmation pages; their POST routes are unchanged.
- **The format** (R2–R4, [contracts/csv-format.md](./contracts/csv-format.md)):
  - a pure module, `app/services/question_csv.py`, holds the format's constants, the writer
    (the `csv` module, UTF-8 with a byte-order mark, commas, CRLF) and the checker;
  - the reader is a small parser of our own, because the standard `csv` module cannot both report
    an unclosed quote at the row where it opens and read `"abc"def` and stray quotes leniently,
    as spreadsheets do;
  - the checker reuses the add form's `clean_question_field`, so the rules and messages are
    shared.
- **Export** (R4): `GET /admin/subjects/{id}/questions/export`, a link marked as a download. The
  response helper is shared with the PDF downloads (`downloads.csv_download`). The file is named
  "<subject> <Kyiv date> question bank.csv" in the site language.
- **Import** (R5–R8, [contracts/http-routes.md](./contracts/http-routes.md)):
  - `GET /questions/import` shows the page, a destructive confirmation with a file field inside;
  - `POST /questions/import` reads the upload in a dependency that runs after the access check
    (R7), checks the whole file, and either shows every error (at most 20, then "And N more
    errors.") or replaces the questions;
  - `question_bank_files.replace_questions` runs in one transaction: the subject `FOR SHARE`,
    then the bank lock, then one soft-delete `UPDATE`, then one multi-row `INSERT` in file order,
    then one log line.
- **The bank lock** (R6): on PostgreSQL, `LOCK TABLE questions IN EXCLUSIVE MODE`, so every bank
  write waits and plain reads do not. On SQLite, the database's write lock already does this.
  This is justified under Principle VII below.
- **Components first** (R9, [contracts/components.md](./contracts/components.md)):
  - `confirmation` gains `form_content`, `sends_file` and `summary`;
  - `form.html` gains `file_field`;
  - `error_summary` gains `row_errors` and `more`.

  All three go into the library, the gallery and the UI guidelines before the import page uses
  them.
- **README** (R12): a section "Question bank CSV files" for an AI assistant, ending with an
  example file that a test imports, and a test that its limits match the constants.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**: unchanged:

- FastAPI 0.141, Starlette 1.6 and python-multipart 0.0.32 (already a dependency, now used for
  the first file upload);
- Jinja2, SQLModel and SQLAlchemy, Alembic, Babel and Pico.css v2.

The standard library's `csv` is used for writing only. There is no new runtime or development
dependency.

**Storage**: SQLite (local, tests) and PostgreSQL (production). There is no migration. The
import writes the existing `questions` table: a soft delete, then new rows.

**Testing**: pytest on both engines.

- **New modules**:
  - `tests/unit/test_question_csv.py`;
  - `tests/integration/test_question_bank_files_service.py`;
  - `tests/integration/test_admin_question_files.py`.
- **Updated modules**:
  - `test_admin_subjects.py`;
  - `test_routes.py` and `test_access_control.py`;
  - `test_component_gallery.py`;
  - `test_form_contract.py` with `form_contract.json`;
  - the catalogue checks.
- **Lock checks**: PostgreSQL only, with `SET LOCAL lock_timeout`, as in
  `test_results_service.py`.
- **By hand**: the screenshots, the Excel check and the timings.

**Target Platform**: the Linux container on Render: one uvicorn process, sync handlers in its
thread pool. Current desktop and phone browsers, with and without JavaScript. The export is a
plain link, and the import is a plain multipart form post.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals** (SC-009, R11): an export of 1,000 questions starts within 2 s, and an
import of a valid 1,000-question file finishes within 10 s. Both are expected well under 1 s;
they are measured once and recorded.

**Constraints**:

- **Check order**: cross-site, then role, then subject, then the file. The body is never read
  before the role check (R7).
- **All or nothing**: the whole file is checked before any write.
- **Soft deletion only**: nothing is erased, and competitions are never written.
- **The lock order**: the subject before the table (R6).
- **Upload limits**: at most 2 MB is kept in memory, and a larger body is drained and discarded,
  never stored.
- **One log line**: per import, with ids and counts only; nothing on an export.
- **Tokens only** in CSS.
- **Both engines.**

**Scale/Scope**:

- **Router**: 1 changed router (`admin_subjects.py`, 5 new routes).
- **Helpers**: 1 new helper module (`routers/uploads.py`) and 1 changed (`routers/downloads.py`).
- **Services**: 2 new (`question_csv.py`, `question_bank_files.py`).
- **Templates**:
  - 3 new pages (`subject_deactivate.html`, `subject_activate.html`, `subject_import.html`);
  - 1 changed page (`subjects.html`);
  - 2 changed components (`confirmation.html`, `form.html`);
  - the gallery page;
  - CSS.
- **Catalogues**: about 25 new messages in each language.
- **Documents**: the README section, the UI guidelines, and `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.10 is merged. 12.11 is one end-to-end slice: the **Subjects** tab, through the routes and the services, to the bank and back to a file. Nothing from later milestones is built. | ✅ |
| II. Server-rendered simplicity | Plain links and a plain multipart `POST`, with no HTMX, no new script and no new dependency. The custom parser (R2) is about 60 lines, justified by two needs the standard library cannot meet together. | ✅ |
| UI guidelines | The page is built from the library. The three new patterns (confirmation with a form, file field, row errors) are added to the library, the gallery and `ui-guidelines.md` first (FR-054). The menu reuses `actions_menu` and `menu_link(download=…, destructive=…)`. Tokens only. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ line map to pytest cases on both engines (R13). That includes allowed and denied access on the 5 new routes per role, the lock on PostgreSQL, and the README example. Screenshots are checked by hand, as the milestone says. | ✅ |
| IV. Role-based access & data scoping | Administrators only, enforced server-side. The body is read only after the role check (R7). Teachers and students get 403 from every route, for any subject or a missing one. The export holds the additional questions with their mark, the one exception v2.8.0 names. It holds no bank numbers and nothing about competitions. An administrator sees no question on any page, only counts. The import soft-deletes. | ✅ |
| V. Secure authentication & secrets | No change to sign-in. The import passes the existing cross-site check. The upload is limited to 2 MB in memory, and larger bodies are drained and discarded. The log line holds ids and counts, never text. | ✅ |
| VI. LLM evaluation | Not involved. The README section is for an external assistant; the application calls no LLM. | n/a |
| VII. Data integrity & migrations | No schema change. The replaced questions are soft-deleted, so competitions keep their copies, answers, grades and stored results files, and the subject stays undeletable. One transaction. **Database-specific feature, justified**: `LOCK TABLE questions IN EXCLUSIVE MODE` on PostgreSQL. Only a table lock makes the `INSERT` of a teacher's new question wait (row locks cannot), which FR-048 and FR-049 require. Plain reads are not blocked. SQLite gets the same behaviour from its database write lock, so the function does nothing there (R6). | ✅ (justified) |
| Stack | Uses the listed stack only. The CSV files are made at download and not stored, as the constitution says. | ✅ |
| Application Layout | `routers/` stays thin (`admin_subjects`, `uploads`, `downloads`). The logic is in `services/` (`question_csv`, `question_bank_files`). `templates/components/` and `templates/pages/admin/` are changed. | ✅ |
| Governance and workflow | The amendment this milestone needs is already on the branch (constitution v2.8.0, with the product requirements and `milestones.md`). Whether it goes through a dedicated pull request is the product owner's decision, as recorded in its sync report. The UI guidelines and the README are updated in this PR, and `milestones.md` on delivery. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: [http-routes.md](./contracts/http-routes.md) lists each route's checks in FR-008
  order. `uploaded_file` is a dependency, never a `File(...)` parameter
  ([services.md](./contracts/services.md) §3).
- **Content**: `QuestionRow` ([data-model.md](./data-model.md)) has no field for a bank number
  or a competition, so neither can reach a file.
- **All or nothing**: `QuestionFileCheck.rows` is empty whenever there is an error, and
  `replace_questions` asserts a non-empty, bounded list.
- **Lock**: the order (subject, then table) and the reason are in research R6, and the
  PostgreSQL tests cover waiting, reading and deletion.
- **Components**: [components.md](./contracts/components.md) keeps every existing confirmation
  and summary byte-identical without the new arguments.

## Project Structure

### Documentation (this feature)

```text
specs/012.11-question-bank-csv/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R13
├── data-model.md        # Phase 1: no schema change; the values in memory
├── quickstart.md        # Phase 1: how to see and check the milestone
├── contracts/
│   ├── http-routes.md   # the tab, the confirmations, export, import
│   ├── csv-format.md    # the format, every check and message, examples
│   ├── services.md      # question_csv, question_bank_files, uploads, downloads
│   └── components.md    # confirmation with a form, file_field, row errors, the tab
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── routers/
│   ├── admin_subjects.py                  # + GET deactivate/activate pages, export, import page, import
│   ├── uploads.py                         # new: uploaded_file dependency (R7)
│   └── downloads.py                       # + csv_download; shared _attachment
├── services/
│   ├── question_csv.py                    # new, pure: format, writer, parser, checks
│   └── question_bank_files.py             # new: counts, export rows/name, lock, replace_questions
├── templates/
│   ├── components/confirmation.html       # form_content, sends_file, summary
│   ├── components/form.html               # file_field; error_summary row_errors, more
│   ├── pages/admin/subjects.html          # Questions column; actions menu
│   ├── pages/admin/subject_deactivate.html  # new
│   ├── pages/admin/subject_activate.html    # new
│   ├── pages/admin/subject_import.html      # new
│   └── pages/admin/components.html        # gallery: file field, confirmation with a form, row errors
├── static/css/app.css                     # file input, .error-summary-more (tokens only)
└── locale/{uk,en}/LC_MESSAGES/messages.po # new messages

tests/
├── unit/test_question_csv.py                          # new
├── integration/test_question_bank_files_service.py    # new
├── integration/test_admin_question_files.py           # new
└── integration/…                                      # updated, as in Technical Context

docs/requirements/ui-guidelines.md         # confirmation with a form, file field, row errors, Subjects menu, glossary
README.md                                  # section "Question bank CSV files"
```

**Structure Decision**: the existing single FastAPI application and its `app/` layout
(constitution, Application Layout). The work is split as in earlier milestones:

- a thin router with one input dependency;
- a pure format module that carries every rule of the file;
- a small database service;
- component additions before page use.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| PostgreSQL-specific `LOCK TABLE questions IN EXCLUSIVE MODE` (Principle VII: database-specific feature) | FR-048 and FR-049: every bank write, including a teacher's `INSERT` of a new question, must wait for a running import, while reads go on | Row locks cannot make an `INSERT` of a new row wait. An advisory lock would need every existing bank write to take it, and a missed one fails silently. `SERIALIZABLE` fails instead of waiting. |
| A custom CSV parser instead of the standard `csv` reader (Principle II: simplest design) | FR-037 (an unclosed quote at the row where it opens) together with spreadsheet-lenient reading (`"abc"def`, stray quotes) | No mode of the `csv` module does both (R2, tested); a pre-scan would duplicate the state machine. |
