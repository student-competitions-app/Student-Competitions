---

description: "Task list for milestone 12.11: exporting and importing a subject's questions as CSV files (administrator)"
---

# Tasks: Exporting and Importing a Subject's Questions as CSV Files (Administrator) (Milestone 12.11)

**Input**: Design documents from `/specs/012.11-question-bank-csv/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/csv-format.md](./contracts/csv-format.md), [contracts/services.md](./contracts/services.md),
[contracts/components.md](./contracts/components.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III makes them non-negotiable, and FR-061 asks for the
acceptance scenarios and the milestone's "_Test:_" line. Research R13 maps the scenarios to test
modules.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when
  `TEST_POSTGRES_URL` is set, through the existing `database_url` / `engine` / `session` /
  `client` fixtures in `tests/conftest.py`. The PostgreSQL lock tests use the
  `postgresql_only(database_url)` and `short_lock_timeout(session)` pattern of
  `tests/integration/test_results_service.py` (`SET LOCAL lock_timeout = '300ms'`). The one SQLite
  lock test skips on PostgreSQL and uses `PRAGMA busy_timeout = 300`. No test sleeps.
- **Seeders** (existing, unchanged):
  - `make_subject(engine, name, active=True)`;
  - `make_question(engine, subject_id, text, reference_answer, *, deleted=False, additional=False)`;
  - `make_teacher(engine, settings, ...)`;
  - `make_competition(...)` and `add_competition_question(...)`;
  - `admin_client` and `client_as(email)` (cast: `admin@example.com`, `teacher@example.com`,
    `student@example.com`).
- **The clock**: patch `app.services.competitions.utc_now`, as the `clock` fixtures of
  `tests/integration/test_teacher_question_files.py` do.
- **HTML helpers**: `tests/html.py` (`dom.links`, `dom.form_targets`, `dom.link_pairs`, ...), as
  `tests/integration/test_admin_subjects.py` uses them.

**Organization**: tasks are grouped by the user stories of spec.md (US1–US9). The phase order
follows what each story needs, not only its priority:

- **Phase 1** delivers the components of **US9** first (constitution Principle II).
- **Phase 2** holds the format's constants and the shared download helper.
- **US5** (the tab, the menu and the confirmations) comes first among the stories, because its
  menu is the way into US1 and US2.
- **US1** is the export, the MVP.
- **US4 → US3** give the pure reader and its checks.
- **US2** is the import page and the replacement.
- **US7** adds the bank lock, **US8** the access sweep, and **US6** the README section.
- **US9 (manual)** is the product owner's screenshot check.

**Reference implementation**: milestones 6, 7, 12.8 and 12.10 set every pattern used here. Match
their docstring style, naming, comment density and error handling:

- **Router**: `app/routers/admin_subjects.py` (thin handlers, `_not_found`, 303 to the list),
  `app/routers/admin_institutions.py` (the institution's GET deactivate confirmation),
  `app/routers/teacher_question_files.py` (a download route) and `app/routers/downloads.py`.
- **Services**:
  - `app/services/subjects.py`: `SubjectNotFound`, one log line with ids only;
  - `app/services/questions.py`: locks with `populate_existing`, `_refuse` rolls back before
    raising;
  - `app/services/question_files.py`: the Kyiv date and `clean_file_stem` in file names.
- **Templates**: `app/templates/pages/admin/institution_deactivate.html` (a confirmation page),
  `app/templates/pages/teacher/competitions.html` (an `actions_menu` per row).
- **Tests**:
  - `tests/integration/test_admin_subjects.py` (the tab over HTTP);
  - `tests/integration/test_teacher_question_files.py` (download headers, file names, the clock);
  - `tests/integration/test_results_service.py` (PostgreSQL lock tests).

**Rules for every task** (plan Constraints; contracts/http-routes.md):

- **Order of checks**:
  1. cross-site and the role, through the existing `resolve_access` and
     `@allow_roles(Role.ADMIN)`;
  2. the subject (404, `pages/admin/subject_not_found.html`);
  3. the file.

  The upload body is read only by the `uploaded_file` dependency, never by a `File(...)` or
  `Form(...)` parameter (research R7).
- **Kept out by construction**: `QuestionRow` has no field for a bank number or a competition.
  Administrators never see a question on a page, only counts.
- **Messages**: every new user-facing text is one whole message through `_()`, `_n()` or
  `ngettext`. Then:
  1. run `scripts/translations.sh update`;
  2. translate each Ukrainian entry in `app/locale/uk/LC_MESSAGES/messages.po` with the proposals
     given in the tasks, never left fuzzy;
  3. run `scripts/translations.sh compile`.

  The CSV header row `question,answer,additional` is never translated.
- **Logging**: exactly one line per successful import, `Questions imported: subject=%d
  deleted=%d added=%d`. Nothing on an export, a refused file or a page view.
- **Tokens only** in CSS.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US9)

---

## Phase 1: Setup (Components first) — delivers US9 scenarios 1–4

**Purpose**: the three new patterns, in the library, the gallery and the UI guidelines, before the
import page uses them (research R9, contracts/components.md §1–§3, §5). Nothing here touches the
database.

- [X] T001 [P] [US9] Extend `confirmation` in `app/templates/components/confirmation.html` per contracts/components.md §1:
  - **First, before any edit**: render one existing destructive call (`confirmation("Delete “Physics”?", "This cannot be undone.", "/x", "Delete", "/back")`) and one blocked primary call, and save their exact markup as expected strings for T005 (`tests/unit/test_templates.py`), so the "unchanged" check compares with the output from before this task.
  - **Signature**: `confirmation(question, consequence, action, verb, cancel_href, hidden={}, back_label=None, kind="destructive", blocked=None, alternative=None, form_content=False, sends_file=False, summary=None)`.
  - **`summary`**: rendered right after the `<h1>` and before the consequence `<p>`; nothing when `None`.
  - **`form_content=True`**:
    - after the consequence, open `<form method="post" action="{{ action }}"{% if sends_file %} enctype="multipart/form-data"{% endif %}>`;
    - render the hidden inputs, then `{{ caller() }}`;
    - then `<div class="form-actions">` with `button(verb, kind=kind)` (import `button` from `components/button.html`) and the back link;
    - close the form.
  - **`form_content=False`**: everything renders exactly as today.
  - **Template errors**: `sends_file` without `form_content` → `template_error("confirmation: sends_file needs form_content")`; `form_content` with `blocked` → `template_error("confirmation: a blocked confirmation has no form")`.
  - **The top comment**: add a paragraph "**With a form** (milestone 12.11): when the action needs input, such as a file, `form_content=True` puts the caller's block and the buttons in one form (`sends_file=True` makes it `multipart/form-data`), and `summary` places the error summary under the question."
  - **Byte-identical**: every existing caller's output is unchanged.
- [X] T002 [P] [US9] Add `file_field` and extend `error_summary` in `app/templates/components/form.html` per contracts/components.md §2–§3:
  - **First, before any edit**: render one existing `error_summary({"name": "Enter a name."}, form_error="Try again later.")` call and save its exact markup as an expected string for T005, so the "unchanged" check compares with the output from before this task.
  - **`file_field(id, label, error=None, hint=None, accept=None, name=None, attrs={})`**:
    - `<label for>`, then `_messages(id, hint, error)`, then `<input type="file" id="{{ id }}" name="{{ name or id }}"{% if accept %} accept="{{ accept }}"{% endif %}{{ _described(id, hint, error) }}{{ _attrs(attrs) }}>`;
    - never a `value` attribute.
  - **`error_summary(errors, form_error=None, order=None, row_errors=(), more=0)`**:
    - after the linked field errors and before `form_error`, one `<li>{{ message }}</li>` per `row_errors` entry, unlinked;
    - when `more > 0`, after `</ul>`, `<p class="error-summary-more">{{ ngettext("And %(num)d more error.", "And %(num)d more errors.", more) }}</p>`;
    - the summary renders when `errors or form_error or row_errors`;
    - without the new arguments the output is byte-identical.
  - **The top comment**: say that a file field is never refilled, and that row errors are errors about a row of a file, not about a field, so they are not linked.
- [X] T003 [US9] Add the CSS to `app/static/css/app.css`, in the Forms section (depends on T002):
  - `input[type="file"]` uses the existing field spacing, border, radius and focus-ring tokens, and is `max-width: 100%` so it never scrolls sideways at 360 px;
  - `.error-summary-more { margin: 0; }` with the summary's text colour token;
  - tokens only. `tests/unit/test_stylesheet.py` and `tests/unit/test_frame_stylesheet.py` pass.
- [X] T004 [US9] Add the gallery entries to `app/templates/pages/admin/components.html` and their sample data to `_samples()` in `app/routers/admin_components.py` (depends on T001–T003):
  - **New section `#file-field` "File field"**:
    - plain `file_field("sample-file", "CSV file", accept=".csv,text/csv")`;
    - with the hint "A CSV file in the format described in the README, at most 2 MB";
    - with the error "Choose a CSV file.".
  - **New section `#confirmation-with-form` "Confirmation with a form"**:
    - the import page's shape, `confirmation("Import questions: History", "History has 124 questions now. …", "/admin/components#confirmation-with-form", "Replace questions", "/admin/components", form_content=True, sends_file=True)` with a `file_field` inside;
    - a second copy with `summary=error_summary({"sample-file-2": "The file can be at most 2 MB."}, row_errors=["Row 7: Enter the reference answer.", "Row 12: Additional must be 0, 1 or empty.", "A quote opened in row 40 is never closed."], more=5)` and the field showing its error.
  - **In `#forms`**: one more `error_summary` sample with two row errors and `more=1`.
  - Add both new sections to the gallery's table of contents, in the order of the existing list.
- [X] T005 [P] [US9] Extend `tests/unit/test_templates.py` (depends on T001, T002):
  - **Unchanged without the new arguments**: an existing `confirmation(...)` call and an existing `error_summary(...)` call render byte-identically to the expected strings recorded at the start of T001 and T002, before their edits.
  - **`form_content`**: there is one `<form method="post">` around the caller's block and the buttons, the button is a submit `button` inside that form, and there is no nested `post_button` form.
  - **`sends_file`**: adds `enctype="multipart/form-data"`; `sends_file` without `form_content` and `form_content` with `blocked` raise the template errors.
  - **`summary`**: sits between `<h1>` and the consequence.
  - **`file_field`**: has `type="file"`, `accept`, `aria-describedby` naming the hint and the error, `aria-invalid="true"` only with an error, and never a `value`.
  - **`error_summary`**:
    - `row_errors` are `<li>`s without `<a>`, after the linked errors;
    - `more=1` reads "And 1 more error.", `more=5` reads "And 5 more errors.", and `more=0` renders no `.error-summary-more`.
- [X] T006 [P] [US9] Extend `tests/integration/test_component_gallery.py` (depends on T004):
  - `SECTIONS` gains `"file-field"` and `"confirmation-with-form"` with their variants;
  - a new test `test_the_file_field_and_the_confirmation_with_a_form`:
    - `#confirmation-with-form` holds a `form[method=post][enctype="multipart/form-data"]` containing an `input[type=file]` and the destructive button "Replace questions";
    - the second copy holds `.error-summary` with three unlinked `li`s and "And 5 more errors.";
    - `#file-field` holds three `input[type=file]`, none with a `value`.
- [X] T007 [US9] Update `docs/requirements/ui-guidelines.md` (depends on T004):
  - **Confirmations**: `form_content`, `sends_file` and `summary`, with the rule "a confirmation whose action needs input (a file) holds the input inside its form; the button still repeats the verb".
  - **Forms**:
    - `file_field`, with the rule "a file field is never refilled: after an error the person chooses the file again";
    - the row-error variant of `error_summary`, with the rule "an error about a field is linked to it; an error about a row of a file names its row and is not linked; at most 20 are listed, then 'And N more errors.'".
  - **Actions menu**: add the **Subjects** tab's entries and their order: **Rename**, **Export questions** (download), **Import questions** (destructive), **Deactivate** (destructive) or **Activate**, **Delete** (destructive).
  - **The glossary**:
    - **Export questions** «Експортувати питання»;
    - **Import questions** «Імпортувати питання»;
    - **Replace questions** «Замінити питання»;
    - **CSV file** «Файл CSV»;
    - "Row N: …" «Рядок N: …».
  - Then open `/admin/components` at 360 px and at desktop width, light and dark: no sideways scroll.

**Checkpoint**: the gallery shows the three patterns, the guidelines match, and the whole existing
suite is green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the format's constants and values, and the download helper, shared by the export and
the import (data-model.md §2–§3, contracts/services.md §1, §4).

- [X] T008 [P] Create `app/services/question_csv.py` with its module docstring and the shared values only (the functions come in US1, US4 and US3):
  - **Constants**:
    - `HEADER = ("question", "answer", "additional")`;
    - `MAX_FILE_BYTES = 2 * 1024 * 1024`;
    - `MAX_QUESTIONS = 1000`;
    - `ERRORS_SHOWN = 20`.
  - **`@dataclass(frozen=True) QuestionRow(text: str, reference_answer: str, is_additional: bool)`**, with a docstring: "No field for a bank number or a competition, so neither can reach a file (FR-021)".
  - **`@dataclass(frozen=True) QuestionFileError(row: int | None, message: Text)`**: `row is None` is a whole-file error.
  - **`@dataclass(frozen=True) QuestionFileCheck(rows, errors)`**:
    - `ok` is `not errors`;
    - `file_error` is the message of the error with `row is None`, or `None`;
    - `row_errors` holds the messages of the first `ERRORS_SHOWN` errors in all, minus the file error;
    - `more` is `max(0, len(errors) - ERRORS_SHOWN)`.
  - **`class UnclosedQuote(ValueError)`** with `row: int`.
  - **The docstring**: it is pure (no I/O, no database, no logging), it points to contracts/csv-format.md, and the README section "Question bank CSV files" must agree with it (a test checks that).
- [X] T009 [P] Add `csv_download(content: bytes, file_name: str) -> Response` to `app/routers/downloads.py` per research R4:
  - factor today's body of `pdf_download` into a private `_attachment(content, file_name, media_type)`;
  - `pdf_download` passes `"application/pdf"`, `csv_download` passes `"text/csv; charset=utf-8"`;
  - the headers stay exactly as they are;
  - extend the docstring with "the question bank CSV file (milestone 12.11), offered to administrators";
  - `tests/integration/test_teacher_results.py` and `tests/integration/test_teacher_question_files.py` stay green.
- [X] T010 [P] Create `app/services/question_bank_files.py` with its module docstring (contracts/services.md §2: no authorization here; the router is admin-only; it logs one line per import) and the first function:
  - `question_counts(session) -> dict[int, int]`: one `SELECT subject_id, count(*) FROM questions WHERE deleted_at IS NULL GROUP BY subject_id`, additional questions included;
  - add `@dataclass(frozen=True) Replaced(deleted: int, added: int)`.

**Checkpoint**: the new modules import cleanly; the suite is green.

---

## Phase 3: User Story 5 - The Subjects tab shows the count and puts actions in a menu (Priority: P2)

**Goal**: the **Questions** column, the actions menu in its order, and the **Deactivate** and
**Activate** confirmation pages. This comes first because the menu is the way into US1 and US2.

**Independent Test**: as an administrator, open the menu of an active and a deactivated subject
on a wide screen and at 360 px, check the entries and their order, then deactivate and activate
through the confirmation pages and with **Cancel**.

- [X] T011 [US5] Add the confirmation pages to `app/routers/admin_subjects.py` per contracts/http-routes.md §2:
  - `GET /{subject_id:int}/deactivate` → `pages/admin/subject_deactivate.html` and `GET /{subject_id:int}/activate` → `pages/admin/subject_activate.html`, both `@allow_roles(Role.ADMIN)`, using `get_subject` and `_not_found` for 404;
  - the pages are shown whatever the subject's status;
  - the POST handlers are unchanged;
  - `subjects_page` now also passes `counts=question_counts(session)` (T010).
- [X] T012 [P] [US5] Create `app/templates/pages/admin/subject_deactivate.html` and `subject_activate.html`, modelled on `institution_deactivate.html`:
  - **Deactivate**: `confirmation(_("Deactivate “%(name)s”?", name=subject.name), _("Its questions and every one of its competitions that is not finished are hidden from teachers until it is activated again."), path ~ "/deactivate", _("Deactivate"), "/admin/subjects")`, destructive;
  - **Activate**: `confirmation(_("Activate “%(name)s”?", name=subject.name), _("Its questions and its competitions that are not finished are shown to teachers again."), path ~ "/activate", _("Activate"), "/admin/subjects", kind="primary")`;
  - the title block is the question without "?", as `institution_deactivate.html` does it.
- [X] T013 [US5] Rewrite the table in `app/templates/pages/admin/subjects.html` per contracts/components.md §4 (depends on T011):
  - `data_table([_("Name"), _("Status"), _("Questions"), _("Actions")])`;
  - `cell(_("Questions"), counts.get(s.id, 0))`;
  - the actions cell holds `actions_menu(s.name)` with:
    - `menu_link(_("Rename"), path ~ "/rename")`;
    - `menu_link(_("Export questions"), path ~ "/questions/export", download=True)`;
    - `menu_link(_("Import questions"), path ~ "/questions/import", destructive=True)`;
    - `menu_link(_("Deactivate"), path ~ "/deactivate", destructive=True)` if `s.is_active`, else `menu_link(_("Activate"), path ~ "/activate")`;
    - `menu_link(_("Delete"), path ~ "/delete", destructive=True)`;
  - remove the `post_button` and `link_button` imports if unused.
- [X] T014 [US5] Add the messages, translate and compile (depends on T012, T013):
  - "Export questions" «Експортувати питання»;
  - "Import questions" «Імпортувати питання»;
  - "Deactivate “%(name)s”?" «Деактивувати «%(name)s»?»;
  - "Activate “%(name)s”?" «Активувати «%(name)s»?»;
  - "Its questions and every one of its competitions that is not finished are hidden from teachers until it is activated again." «Його питання та всі його незавершені змагання буде приховано від учителів, доки його не активують знову.»;
  - "Its questions and its competitions that are not finished are shown to teachers again." «Його питання та незавершені змагання знову буде видно вчителям.»;
  - reuse the existing "Questions", "Deactivate", "Activate", "Rename" and "Delete".
- [X] T015 [US5] Update `tests/integration/test_admin_subjects.py` (depends on T013, T014):
  - **The column**: shows `0`, then the count of listed questions, additional included and deleted left out (seed with `make_question(..., additional=True)` and `deleted=True`).
  - **The menu**:
    - an active subject's `menu_link`s, in order: Rename, Export questions (with `download`), Import questions, Deactivate, Delete;
    - a deactivated subject has Activate in place of Deactivate;
    - the danger class is on Import questions, Deactivate and Delete;
    - no `<form>` in `main`.
  - **`GET /deactivate` and `GET /activate`**: 200 with the question, the consequence, the post target and **Cancel** to `/admin/subjects`, for an active and a deactivated subject; 404 "Subject not found" for an unknown id.
  - **Confirming**: posting changes the status and returns 303; **Cancel** changes nothing.
  - **A status the subject already has** (FR-005): `GET /deactivate` of a deactivated subject still shows the page, and confirming it returns 303 with no change and no error; the same for **Activate** on an active subject.
  - **Existing tests** that read the old row buttons: change them to the menu links, not their meaning.
- [X] T016 [US5] Update `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json` (depends on T011–T013):
  - record in the docstring's "Deliberate changes" list: "**Milestone 12.11**: the Subjects tab's row actions moved into the actions menu, so `admin-subjects` lost its deactivate and activate forms; `admin-subject-deactivate`, `admin-subject-activate`, `admin-subject-import` and `admin-subject-import-errors` are new, generated once with `UPDATE_FORM_CONTRACT=1` for those cases only";
  - add the `admin-subject-deactivate` and `admin-subject-activate` cases now; the two import cases come with T036;
  - regenerate only those cases and the changed `admin-subjects` case.

**Checkpoint**: the tab shows counts and menus; deactivating and activating go through their
pages; the suite is green.

---

## Phase 4: User Story 1 - An administrator exports a subject's questions (Priority: P1) 🎯 MVP

**Goal**: **Export questions** downloads every listed question of the subject, oldest first,
additional ones with `1`, as UTF-8 CSV with a byte-order mark, named after the subject and the
Kyiv date.

**Independent Test**: as an administrator, export an active subject, a deactivated one and an
empty one in both languages, and check the download marking, the name, the bytes, the rows, their
order and the marks.

- [X] T017 [P] [US1] Add `write_question_csv(rows: Iterable[QuestionRow]) -> bytes` to `app/services/question_csv.py` per contracts/csv-format.md §2 (depends on T008):
  - write `"﻿"` into a `io.StringIO`, then `csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")`;
  - `writerow(HEADER)`, then `(row.text, row.reference_answer, "1" if row.is_additional else "0")` per row;
  - return `buffer.getvalue().encode("utf-8")`;
  - texts are written exactly as stored: line breaks stay `\n` inside the quoted field, and there is no formula prefix for `=`, `+`, `-` or `@` (FR-020).
- [X] T018 [P] [US1] Add to `app/services/question_bank_files.py` (depends on T008, T010):
  - **`export_rows(session, subject_id) -> list[QuestionRow]`**: the subject's questions with `deleted_at IS NULL`, additional included, `ORDER BY id ASC`;
  - **`today_in_kyiv() -> date`**: `competitions.utc_now().astimezone(KYIV).date()`, read through the module (`from app.services import competitions`) so the tests' clock patch applies;
  - **`export_file_name(subject_name: str, today: date) -> str`**: `f"{clean_file_stem(subject_name, _('Subject'))} {today:%Y-%m-%d} {_('question bank')}.csv"`, formatted inside the current language.
- [X] T019 [US1] Add the export route `GET /{subject_id:int}/questions/export` to `app/routers/admin_subjects.py` per contracts/http-routes.md §3 (depends on T009, T017, T018):
  - `@allow_roles(Role.ADMIN)`;
  - `get_subject` (404 via `_not_found`), then `csv_download(write_question_csv(export_rows(session, subject_id)), export_file_name(subject.name, today_in_kyiv()))`;
  - no log line; works for an active and a deactivated subject;
  - the docstring says it is a link marked as a download, read at every request and never stored.
- [X] T020 [US1] Add the message "question bank" «банк питань» (in the file name), translate and compile (depends on T018). The file name's fallback stem reuses the existing message "Subject" «Предмет»; add nothing for it.
- [X] T021 [P] [US1] Create `tests/unit/test_question_csv.py` with the writer tests (depends on T017):
  - the bytes start with `EF BB BF` and then `question,answer,additional\r\n`;
  - an empty iterable gives exactly the BOM and the header line;
  - a text with Cyrillic, `,`, `"` and `\n` is quoted, the quote doubled, and `\n` kept inside;
  - `=SUM(A1)`, `+1`, `-1` and `@x` are written unquoted and unprefixed;
  - `1` and `0` for the mark;
  - the order of the iterable is kept.
- [X] T022 [US1] Create `tests/integration/test_admin_question_files.py` with the export section (depends on T019, T020):
  - **The menu link** has `download` and points to `/admin/subjects/{id}/questions/export`.
  - **The response**: 200, `text/csv; charset=utf-8`, `attachment`, `no-store`, `nosniff`.
  - **The rows**: every listed question oldest first (seed out of text order to prove it is the id order), additional with `1`, deleted ones left out; another subject's questions are absent.
  - **Subjects**: a deactivated subject exports; an empty subject gives the header only.
  - **The name**: with the clock at 2026-11-28 in Kyiv, `filename*` decodes to "History 2026-11-28 question bank.csv" in English and "Історія 2026-11-28 банк питань.csv" in Ukrainian (language cookie); `A/B: History?` is cleaned as in milestone 12.8.
  - **Kyiv midnight**: the date follows Kyiv, not UTC (clock at 22:30 UTC on 2026-11-27 → `2026-11-28`).
  - **Unknown subject**: 404 "Subject not found".
  - **Nothing stored or logged** (`caplog` has no new line).
  - **Fresh**: a question added after a first export appears in the second.

**Checkpoint**: the MVP works on its own: an administrator can take any bank out as CSV.

---

## Phase 5: User Story 4 - A file saved back by a spreadsheet imports (Priority: P1)

**Goal**: the pure reader: decoding, the separator, the header, records with their spreadsheet
row numbers, empty rows and lenient reading (research R2, R3 steps 3–6; contracts/csv-format.md
§3). Errors come in US3; here a valid file gives its rows.

**Independent Test**: run the unit tests over files that differ only in separator, byte-order
mark, line endings, empty rows, spaces around `additional`, header case and spaces, and an
unquoted quote, and compare the rows.

- [X] T023 [US4] Implement `parse_records(text: str, separator: str) -> Iterator[tuple[int, list[str]]]` in `app/services/question_csv.py` per research R2 (depends on T008):
  - **Row numbers**: row 1 is the first record; every record counts, blank ones included.
  - **Quoted fields**: a field starting with `"` is quoted; `""` inside is `"`; `\r`, `\n` and the separator inside are characters; characters after the closing quote, up to the separator or line end, are appended (`"abc"def` → `abcdef`).
  - **Unquoted fields**: `"` anywhere else is a character; spaces before an opening quote make the field unquoted.
  - **Record ends**: `\r\n`, `\n` or a lone `\r` outside quotes.
  - **The end of the text**: a final line break does not start an empty record; a blank line before it does yield `[""]`.
  - **An open quote at the end** raises `UnclosedQuote(row)`, with the row where that record began.
  - **Speed**: scan with `str.find` and a compiled regular expression per state, not one Python step per character, so a 2 MB text parses in well under a second.
  - **The docstring**: the table of research R2, explaining why the `csv` module is not used for reading.
- [X] T024 [US4] Implement the reading path of `check_question_file(data: bytes | None, *, too_large: bool = False) -> QuestionFileCheck` in `app/services/question_csv.py` (depends on T023):
  - drop one leading `b"\xef\xbb\xbf"`, then `data.decode("utf-8")` (strict);
  - **The separator** is taken from the text up to the first `\r` or `\n`: `","` if it holds a comma, else `";"` if it holds a semicolon;
  - **The header** is the first record from `parse_records`; it must equal `HEADER` after `field.strip().casefold()`, with exactly 3 fields;
  - **Each further record**: skip it when every field `.strip()` is empty (the row number is still consumed); else build `QuestionRow` with `question` and `answer` through `app.schemas.question.clean_question_field(raw, "text" / "reference_answer")` and `additional.strip()` in `{"", "0"}` → `False`, `"1"` → `True`;
  - return `QuestionFileCheck(rows=tuple(rows), errors=())` for a valid file;
  - leave clearly marked places for the error steps of T026.
- [X] T025 [P] [US4] Add the reading tests to `tests/unit/test_question_csv.py` (depends on T024), each comparing the rows from `check_question_file`:
  - **Encoding and line endings**: the same three questions as UTF-8 with and without a BOM, with `\r\n` and with `\n`.
  - **Separators**: separated by `;` (header without a comma); a header with both `,` and `;` reads with `,`.
  - **The header**: `Question; ANSWER ;additional` is accepted.
  - **Empty rows**: a blank line and `;;` are skipped; a row with only `additional` filled is not empty (here only its row number matters, the errors come in US3).
  - **The `additional` value**: ` 1 ` is additional, and an empty cell is not.
  - **Quotes**: `The "Iliad"` unquoted keeps its quotes; `"abc"def` gives `abcdef`.
  - **Line breaks**: a multi-line quoted text is one row, and its `\r\n` becomes `\n`; the final line break adds no row.
  - **The round trip**: `check_question_file(write_question_csv(rows)).rows == rows`, including texts starting with `=`, `+`, `-` and `@`.
  - **The parser alone**: `parse_records` row numbers across a multi-line field and blank lines, and `UnclosedQuote.row`.

**Checkpoint**: any file a spreadsheet saves reads into the right rows.

---

## Phase 6: User Story 3 - A bad file is refused with every error, and nothing changes (Priority: P1)

**Goal**: every check of contracts/csv-format.md §3, with its message, row number, order and the
limit of 20 (research R3; spec FR-034–FR-040).

**Independent Test**: unit-test each kind of bad file and a file of 25 bad rows, checking the
messages, row numbers, order, `more` and that `rows` is empty.

- [X] T026 [US3] Add every error to `check_question_file` in `app/services/question_csv.py` (depends on T024), in this order. Steps 1–5 return at once:
  1. `data is None and not too_large` → `QuestionFileError(None, _("Choose a CSV file."))`.
  2. `too_large or len(data) > MAX_FILE_BYTES` → `_("The file can be at most 2 MB.")`.
  3. `UnicodeDecodeError` → `_("Save the file as CSV UTF-8.")`.
  4. No comma and no semicolon in the first line → the header error.
  5. An empty text, a header that is not exactly `HEADER`, or an `UnclosedQuote` inside the header → `_("The first row must be the header: question, answer, additional.")`.
  6. **Per row**:
     - a width other than 3 → `_("Row %(row)d: %(message)s", row=n, message=_("The row must have 3 fields."))`, and nothing else for that row;
     - else, in column order, the `InvalidQuestionField.message` of `question`, then of `answer`, then `additional` not in `{"", "0", "1"}` after `strip()` → `_("Additional must be 0, 1 or empty.")`, each wrapped in `"Row %(row)d: %(message)s"`.
  7. **`UnclosedQuote(row)`** from a data record → append `QuestionFileError(row, _("A quote opened in row %(row)d is never closed.", row=row))` and stop reading.
  8. **The count of non-empty rows**: `0` → `_("The file holds no questions.")`; more than `MAX_QUESTIONS` → `_("The file can hold at most 1,000 questions.")`. Either is put *first* in `errors`.

  - **Errors**: the whole-file error first, then the row errors in row order and, within a row, in column order.
  - **`rows`** is `()` whenever `errors` is not empty.
  - The function never raises.
- [X] T027 [US3] Add the messages, translate and compile (depends on T026):
  - "Choose a CSV file." «Виберіть файл CSV.»;
  - "The file can be at most 2 MB." «Файл може бути не більше 2 МБ.»;
  - "Save the file as CSV UTF-8." «Збережіть файл у форматі CSV UTF-8.»;
  - "The first row must be the header: question, answer, additional." «Перший рядок має бути заголовком: question, answer, additional.»;
  - "The file holds no questions." «У файлі немає питань.»;
  - "The file can hold at most 1,000 questions." «У файлі може бути не більше 1 000 питань.»;
  - "Row %(row)d: %(message)s" «Рядок %(row)d: %(message)s»;
  - "The row must have 3 fields." «Рядок має містити 3 поля.»;
  - "Additional must be 0, 1 or empty." «Значення additional має бути 0, 1 або порожнім.»;
  - "A quote opened in row %(row)d is never closed." «Лапки, відкриті в рядку %(row)d, не закрито.»;
  - "And %(num)d more error." / "And %(num)d more errors." «І ще %(num)d помилка.» / «І ще %(num)d помилки.» / «І ще %(num)d помилок.» (three Ukrainian plural forms).
- [X] T028 [P] [US3] Add the refusal tests to `tests/unit/test_question_csv.py` (depends on T026, T027), each asserting `rows == ()`:
  - **One test per whole-file error**:
    - `None`;
    - `too_large=True`;
    - `MAX_FILE_BYTES + 1` bytes;
    - UTF-16 with its BOM, and Windows-1251 Cyrillic;
    - an empty file, and only the BOM;
    - a header without a separator;
    - `question;answer;additional;` (four fields);
    - the names in another order;
    - the header only;
    - the header with only empty rows;
    - 1,001 valid rows.
  - **Each row error with its number and exact text**:
    - `x,y` → "Row 2: The row must have 3 fields.";
    - `x,y,yes`;
    - `,,0` → two errors, the text's first;
    - a 2,001-character text;
    - a NUL in an answer.
  - **Row numbers**: an error after a multi-line row and after two skipped empty rows names the spreadsheet row.
  - **The unclosed quote**: `ok,1,0` then `"open,x,1` → "A quote opened in row 3 is never closed."; an earlier bad row's error is kept before it, and nothing after it is read.
  - **More than 1,000 rows with bad rows**: the whole-file error first, then the row errors.
  - **25 bad rows** of one error each: `row_errors` has 20 entries, `more == 5`, and `file_error is None`.
  - **Ordering**: errors in rows 9, 3 and 3 (text and answer) come out 3-text, 3-answer, 9.
  - **Duplicates**: two equal rows are both accepted.

**Checkpoint**: the checker is complete and pinned by tests; nothing imports yet.

---

## Phase 7: User Story 2 - An administrator replaces a subject's questions with a file (Priority: P1)

**Goal**: the import page, the upload, and `replace_questions`: soft-delete every listed
question, add the file's rows in order, then one log line (research R5, R7, R8;
contracts/http-routes.md §4–§5). The lock comes in US7.

**Independent Test**: import a valid file into a subject with questions, some in competitions, and
check the bank, the other subjects, the deleted questions, the competitions, the subject's
deletion and the log line; import a bad file and check the page and the unchanged bank.

- [X] T029 [P] [US2] Create `app/routers/uploads.py` per research R7 and contracts/services.md §3 (depends on T008):
  - **`@dataclass(frozen=True) Upload(data: bytes | None, too_large: bool)`**.
  - **`uploaded_file(field="file", max_bytes=MAX_FILE_BYTES)`** returns an `async def read(request: Request) -> Upload`:
    - a `content-length` above `max_bytes + 16 * 1024`: drain `request.stream()` and discard it, stopping after 16 MiB, then return `Upload(None, True)`;
    - otherwise `form = await request.form(max_files=1, max_fields=2)`, catching `MultiPartException` and Starlette's `HTTPException` as no file;
    - the value under `field`: if it is not an `UploadFile`, or it has `filename == ""` and is empty, return `Upload(None, False)`;
    - otherwise `await value.read(max_bytes + 1)`, and more than `max_bytes` means `Upload(None, True)`;
    - `await form.close()` in a `finally`.
  - **`UploadedCsv = Annotated[Upload, Depends(uploaded_file())]`**.
  - **The docstring** says why it is a dependency and never a `File(...)` parameter: FastAPI reads such bodies before `resolve_access` runs, so a refused user's upload would be read first.
- [X] T030 [P] [US2] Add `replace_questions(session, subject_id: int, rows: Sequence[QuestionRow]) -> Replaced` to `app/services/question_bank_files.py` per research R5 (depends on T010):
  - `assert 1 <= len(rows) <= MAX_QUESTIONS`;
  - read the subject `session.get(Subject, subject_id, with_for_update={"read": True}, populate_existing=True)`; if it is missing, `session.rollback()` and raise `SubjectNotFound(subject_id)` from `app.services.subjects`;
  - `now = utc_now()` (from `app.core.db`);
  - `result = session.execute(update(Question).where(Question.subject_id == subject_id, col(Question.deleted_at).is_(None)).values(deleted_at=now))`, and `deleted = result.rowcount`;
  - `session.execute(insert(Question), [{"subject_id": subject_id, "text": r.text, "reference_answer": r.reference_answer, "is_additional": r.is_additional, "created_at": now, "updated_at": now, "deleted_at": None} for r in rows])`, in file order;
  - `session.commit()`, then `logger.info("Questions imported: subject=%d deleted=%d added=%d", subject_id, deleted, len(rows))` on `logging.getLogger("uvicorn.error")`;
  - return `Replaced(deleted, len(rows))`;
  - leave a comment where T037 inserts the lock, between the subject read and the `UPDATE`.
- [X] T031 [US2] Create `app/templates/pages/admin/subject_import.html` per contracts/http-routes.md §4 (depends on T001, T002):
  - **Title**: `_("Import questions: %(subject)s", subject=subject.name)`.
  - **The confirmation**: `{% call confirmation(title, none, path ~ "/questions/import", _("Replace questions"), "/admin/subjects", form_content=True, sends_file=True, summary=error_summary(errors, row_errors=row_errors, more=more)) %}`.
  - **Inside**:
    - first the count paragraph: `ngettext("%(subject)s has %(num)d question now.", "%(subject)s has %(num)d questions now.", count, subject=subject.name)`, or `_("%(subject)s has no questions yet.", subject=subject.name)` when `count == 0`;
    - then `<p>{{ _("Importing deletes all of them and replaces them with the questions of the file. This cannot be undone. Export the current questions first to keep them.") }}</p>`;
    - then `file_field("file", _("CSV file"), error=errors.get("file"), hint=_("A CSV file in the format described in the README, at most 2 MB"), accept=".csv,text/csv")`.
- [X] T032 [US2] Add the import routes to `app/routers/admin_subjects.py` per contracts/http-routes.md §4–§5 (depends on T026, T029, T030, T031):
  - **`_import_page(request, subject, count, check=None, status_code=200)`**: renders `subject_import.html` with:
    - `errors={"file": check.file_error} if check and check.file_error else {}`;
    - `row_errors=check.row_errors if check else ()`;
    - `more=check.more if check else 0`.
  - **`GET /{subject_id:int}/questions/import`**: `get_subject` (404), then `count = question_counts(session).get(subject_id, 0)`.
  - **`POST /{subject_id:int}/questions/import`**:
    - the parameter `upload: UploadedCsv`;
    - `get_subject` (404);
    - `check = check_question_file(upload.data, too_large=upload.too_large)`; on errors, return `_import_page(..., check, 400)` with the count read again;
    - else `replace_questions(...)`, where `SubjectNotFound` → `_not_found`; success → `_to_list()`.
  - Both are `@allow_roles(Role.ADMIN)`, and neither declares a `Form(...)` or `File(...)` parameter.
- [X] T033 [US2] Add the messages, translate and compile (depends on T031):
  - "Import questions: %(subject)s" «Імпорт питань: %(subject)s»;
  - "Replace questions" «Замінити питання»;
  - "%(subject)s has %(num)d question now." / "…questions now." «Зараз у предметі «%(subject)s» %(num)d питання.» / «…%(num)d питання.» / «…%(num)d питань.»;
  - "%(subject)s has no questions yet." «У предметі «%(subject)s» ще немає питань.»;
  - "Importing deletes all of them and replaces them with the questions of the file. This cannot be undone. Export the current questions first to keep them." «Імпорт видалить їх усі й замінить питаннями з файлу. Цю дію не можна скасувати. Щоб зберегти поточні питання, спершу експортуйте їх.»;
  - "CSV file" «Файл CSV»;
  - "A CSV file in the format described in the README, at most 2 MB" «Файл CSV у форматі, описаному в README, не більше 2 МБ».
- [X] T034 [P] [US2] Create `tests/integration/test_question_bank_files_service.py` with the replacement tests (depends on T030):
  - **The counts**: `question_counts` counts listed questions per subject, additional included, deleted left out.
  - **The replacement**:
    - every listed question of the subject gets `deleted_at` and keeps its text, answer, mark and `updated_at`; already-deleted questions keep their old `deleted_at`;
    - the new rows have the file's texts, answers and marks, and ids ascending in file order — with 1,000 rows on both engines;
    - every new id is above the old maximum;
    - `Replaced` has the right counts.
  - **What stays the same**:
    - another subject's questions are untouched;
    - a competition's copies (`add_competition_question`) are unchanged, and the copy's source question is the deleted one;
    - a published competition holding replaced questions (seeded with `save_team_answer`, `grade_answer` and `store_results_files`) keeps its answers, its grades and its stored results files byte for byte (FR-043);
    - `delete_subject` still raises `SubjectInUse`.
  - **Deactivated and missing subjects**: a deactivated subject imports; an unknown subject raises `SubjectNotFound` and nothing changes.
  - **The log line**: exactly one, "Questions imported: subject=<id> deleted=<n> added=<m>", with no text of any question.
- [X] T035 [US2] Add the import section to `tests/integration/test_admin_question_files.py` (depends on T032, T033):
  - **The page**:
    - the title, the count in both its forms and the empty form;
    - the warning;
    - `form[enctype="multipart/form-data"]` posting to the import address;
    - `input[type=file][accept=".csv,text/csv"]` with the hint;
    - the destructive button **Replace questions**, and **Cancel** to `/admin/subjects`;
    - works for a deactivated subject; 404 for an unknown one.
  - **A valid import** (`files={"file": ("bank.csv", data, "text/csv")}`):
    - 303 to `/admin/subjects`;
    - the tab's **Questions** cell shows the new count;
    - the teacher's **Questions** tab lists the new texts newest first;
    - an **Upcoming** competition holding an old question still holds it with "Deleted from the question bank" on its **Questions** page.
  - **The round trip**: export, then import the exported bytes unchanged; the bank has the same texts, answers, marks and order under new ids.
  - **A refused file**:
    - 400, the page with `.error-summary` listing the errors;
    - the whole-file error linked to `#file` and shown on the field;
    - row errors unlinked;
    - the `input[type=file]` has no `value`;
    - the bank is unchanged (compare all `questions` rows before and after);
    - 25 bad rows show 20 errors and "And 5 more errors.".
  - **No file chosen** (an empty `filename` part) → "Choose a CSV file.".
  - **An oversized `Content-Length`** → "The file can be at most 2 MB." and an unchanged bank.
  - **A cross-site post** (`Sec-Fetch-Site: cross-site`) is refused and changes nothing.
  - **The study materials**: after an import, a teacher's study materials download shows the new questions without the additional ones.
- [X] T036 [US2] Add the form-contract cases `admin-subject-import` and `admin-subject-import-errors` to `tests/integration/test_form_contract.py` and generate only them into `form_contract.json` (depends on T032; the docstring entry was added in T016).

**Checkpoint**: an administrator can replace a bank from a file; a bad file changes nothing.

---

## Phase 8: User Story 7 - An import and a teacher's change never mix (Priority: P2)

**Goal**: the bank is locked for writing while an import replaces it; reads are not blocked
(research R6; spec FR-048–FR-050).

**Independent Test**: on PostgreSQL, hold the import's lock and send each kind of bank write and a
read; on both engines, check that an edit of a replaced question gets the deleted-question page.

- [X] T037 [US7] Add `lock_question_bank(session) -> None` to `app/services/question_bank_files.py` and call it in `replace_questions` right after the subject read (depends on T030):
  - on PostgreSQL (`session.get_bind().dialect.name == "postgresql"`), run `session.execute(text("LOCK TABLE questions IN EXCLUSIVE MODE"))`; on SQLite, do nothing;
  - the docstring is research R6:
    - `EXCLUSIVE` blocks `ROW EXCLUSIVE` and `ROW SHARE` but not `ACCESS SHARE`, so every bank write waits and plain reads do not;
    - on SQLite, the first `UPDATE` takes the database write lock;
    - the lock order (the subject `FOR SHARE` first, then the table) avoids a deadlock with a subject deletion;
    - this is the database-specific feature justified in plan.md (constitution Principle VII).
- [X] T038 [US7] Add the lock tests to `tests/integration/test_question_bank_files_service.py` (depends on T037). The cases below run on PostgreSQL, with one session holding `lock_question_bank` uncommitted, except the last one, which runs on SQLite:
  - **Writes time out** in a second session with `short_lock_timeout`, and leave the bank unchanged:
    - a teacher's `create_question`, `update_question` (text and mark) and `delete_question` from `app.services.questions`;
    - a second `replace_questions`;
    - adding a question to an upcoming competition through `app.services.competition_entries`.
  - **Reads go on at once**: `question_page(...)` and `export_rows(...)` return.
  - **A teacher's edit first**: a session holding a question `FOR UPDATE` (as `update_question` does) makes `replace_questions` time out.
  - **A deletion first**: for a subject with no questions (the only kind that can be deleted), a session that has deleted the subject row through `delete_subject`'s statements, uncommitted, makes the import wait; after it commits, the import raises `SubjectNotFound`.
  - **On SQLite** (FR-050; the database's write lock, research R6): a first session opens a write transaction on `questions` (the import's soft-delete `UPDATE`, uncommitted), and a second session runs `PRAGMA busy_timeout = 300`. Then:
    - a teacher's `create_question` in the second session fails with "database is locked" and stores nothing;
    - `question_page(...)` in the second session reads at once;
    - after the first session commits, the add succeeds.
- [X] T039 [P] [US7] Add to `tests/integration/test_admin_question_files.py` (both engines) (depends on T032):
  - after an import, a teacher with **Can manage competitions** posting the edit form or the delete of a replaced question gets the milestone 11 "Question not found" page (404), and the bank is unchanged by that post;
  - a question a teacher adds right after the import is listed beside the imported ones, as the newest.

**Checkpoint**: on PostgreSQL every bank write waits for an import; reads do not.

---

## Phase 9: User Story 8 - Only administrators have the files (Priority: P2)

**Goal**: teachers and students get "access denied" from every new address, before any body is
read; unknown subjects answer 404 to administrators.

**Independent Test**: as a teacher with and without the setting, a student and an administrator,
request every new address and send the import form, for an existing and a missing subject.

- [X] T040 [P] [US8] Update `tests/integration/test_access_control.py` (depends on T011, T019, T032):
  - **`ADMIN_PAGES`** gains `/admin/subjects/{id}/deactivate`, `/admin/subjects/{id}/activate`, `/admin/subjects/{id}/questions/export` and `/admin/subjects/{id}/questions/import`.
  - **`ADMIN_ACTIONS`** gains `("/admin/subjects/{id}/questions/import", {})`.
  - **A new test** `test_other_roles_never_get_the_question_bank_file`, for a teacher with **Can manage competitions**, a teacher without it and a student, for an existing and a missing subject:
    - the export and the import page answer 403 "access denied", the response holds no question text, and nothing changes;
    - an import post with a valid file answers 403 and the bank is unchanged.
  - **A test that the body is never read before the role check**: monkeypatch `app.routers.uploads` so that reading the form fails the test; a teacher's post still gets 403.
- [X] T041 [P] [US8] Update `tests/integration/test_routes.py` (depends on T032):
  - `test_the_write_routes_are_exact` gains `("POST", "/admin/subjects/{subject_id:int}/questions/import")`, and its docstring names milestone 12.11 (the export is a read);
  - every new route declares `Role.ADMIN` only;
  - the 404 sweep covers the new addresses with an unknown id.
- [X] T042 [P] [US8] Add to `tests/integration/test_teacher_questions.py`: the teacher's **Questions** tab offers no export or import link, and has no `input[type=file]` (FR-012).

**Checkpoint**: the route table and the access sweep cover every new address.

---

## Phase 10: User Story 6 - An AI assistant writes a file from the README (Priority: P2)

**Goal**: the README section "Question bank CSV files", standing on its own, with every rule, an
example file and a checklist; tests keep it in step with the importer (research R12; spec
FR-056–FR-058).

**Independent Test**: read the section against US6 scenarios 1–3; the tests import its example and
compare its limits with the constants.

- [X] T043 [US6] Write the section `## Question bank CSV files` in `README.md`, after `## Requirements` and before `## Tech stack`. It is written for an AI assistant that has only this section. Subsections:
  - **What the file is for**: an administrator imports it on **Subjects → Actions → Import questions**, and it *replaces every question* of the subject, so a file holds the whole bank. To add questions, the administrator exports the bank and gives you the exported file to extend.
  - **The format**, stated exactly:
    - the header row `question,answer,additional`, in this order;
    - UTF-8, with the byte-order mark recommended;
    - commas as the separator;
    - a field is quoted with `"` when it holds a comma, a quote or a line break, and quoting every field is safe;
    - a `"` inside a field is doubled (`""`);
    - a line break inside a quoted field stays inside it;
    - the `.csv` extension;
    - `additional` is `0` or `1`.
  - **Limits**:
    - each text and answer is 1 to 2,000 characters, counted in Unicode characters after trimming, with no null character;
    - a file holds 1 to 1,000 questions and is at most 2 MB.
  - **What the import does**:
    - the rows become the bank in their order, oldest first, which the study materials follow;
    - an error refuses the whole file, with row numbers as a spreadsheet shows them.
  - **Writing good content**:
    - texts are shown exactly as written and never translated, so they are plain text in the language of the competition, with no Markdown and no number of their own (the files number the questions);
    - a text never starts with `=`, which a spreadsheet reads as a formula;
    - the reference answer is what a team's answer is graded against, so it is complete enough to grade by;
    - additional questions (`1`) are kept back from participants until a competition that holds them starts.
  - **Opening and saving in a spreadsheet**:
    - LibreOffice asks for the separator;
    - Excel with a Ukrainian regional setting: open through **Data → From Text/CSV**, and saving as CSV with semicolons is accepted.
  - **`### Example file`**: one ` ```csv ` block of four Ukrainian questions, one with `1`, with a comma, a doubled quote and a line break inside quoted fields.
  - **`### Checklist`** before handing the file over: the header; every row has 3 fields; quotes balanced and doubled inside; no text starts with `=`; `additional` is `0` or `1`; the count and the lengths are within the limits; the file is saved as UTF-8 with the `.csv` extension.
- [X] T044 [US6] Add the README tests to `tests/unit/test_question_csv.py` (depends on T043, T026):
  - **`test_readme_example_imports`**: read `README.md`, find the `## Question bank CSV files` section, take the first ` ```csv ` block, and run `check_question_file` on it with and without a BOM. There must be no error, the texts must be in the block's order, and exactly the expected row must be additional.
  - **`test_readme_states_the_limits`**: the section contains "2,000", "1,000" and "2 MB", matching `QUESTION_FIELD_MAX_LENGTH`, `MAX_QUESTIONS` and `MAX_FILE_BYTES // (1024 * 1024)`, and it contains the header `question,answer,additional`.
- [X] T045 [US6] In `tests/integration/test_admin_question_files.py`, import the README example through the route (reuse the extraction helper from T044) and check the bank: the questions in order, the additional one marked (depends on T035, T043).

**Checkpoint**: the README states the format, and the tests fail if it drifts from the importer.

---

## Phase 11: User Story 9 - The product owner checks the look (Priority: P3) — scenario 5, manual

**Goal**: the look of the file field and the **Import questions** page, approved from screenshots
(spec FR-062). This step is not automated.

- [X] T046 [US9] Take the screenshots with headless Playwright (`uv run --with playwright`, on a copy of the database, port 8765, as in the project's browser-screenshot notes):
  - **What**: the **Import questions** page clean and with errors (a file with a whole-file error, and one with 25 bad rows), the **Subjects** tab with the menu open, the two confirmation pages, and the gallery's `#file-field` and `#confirmation-with-form`;
  - **How**: in Ukrainian and English, light and dark, at desktop width and at 360 px;
  - save them under `specs/012.11-question-bank-csv/screenshots/`.
- [X] T047 [US9] **Manual, product owner**: review the screenshots and approve or ask for changes. Record the decision, the date and any follow-up in `specs/012.11-question-bank-csv/design-approval.md` (the `screenshots/` folder is git-ignored). Fix and re-shoot until approved. The milestone is not delivered before this approval.

---

## Phase 12: Polish & Cross-Cutting Concerns

- [X] T048 Check the catalogues: `uv run pytest tests/unit/test_catalogues.py tests/unit/test_ukrainian_wording.py`. There must be no untranslated, fuzzy, unused or obsolete entry, and the Ukrainian wording must follow the glossary of `docs/requirements/ui-guidelines.md`.
- [X] T049 [P] Measure once and record the results in this task's notes (research R11, SC-009):
  - the import of a 1,000-question file near 2 MB (900-character texts and answers), through `check_question_file` and `replace_questions`, on SQLite and PostgreSQL;
  - the export of 1,000 questions.

  Targets: 10 s and 2 s; expected under 1 s.

  **Measured on 2026-11-28** (1,000 questions, about 520 Cyrillic characters each in the text and the answer, a 1.88 MB file; local SQLite file and the local PostgreSQL 17 container): `check_question_file` 0.011 s; `replace_questions` 0.011 s on SQLite, 0.041 s on PostgreSQL; the export (`export_rows` and `write_question_csv`) 0.012 s and 0.016 s; the export reproduced the imported file byte for byte.
- [X] T050 [P] **Manual, product owner**: open an exported file in Excel with a Ukrainian regional setting, by double-click and through **Data → From Text/CSV**, and save it back as CSV and import it. Record the result in `specs/012.11-question-bank-csv/design-approval.md` (research R4, the accepted risk). Commas stay, as decided on 2026-11-28 (spec FR-019); this check confirms that **From Text/CSV** works and that the README's instructions match what Excel shows.
- [X] T051 [P] Update `README.md` beyond the new section:
  - the administrator part of **Roles and access** mentions exporting and importing a subject's questions on the **Subjects** tab;
  - the repository layout tree mentions `app/services/question_csv.py`, `app/services/question_bank_files.py` and `app/routers/uploads.py`.
- [X] T052 [P] Check that `docs/requirements/product-requirements.md` and `.specify/memory/constitution.md` (v2.8.0) agree with what was built (FR-060). Change nothing unless they contradict it; if they do, raise it rather than editing the constitution here.
- [X] T053 Run the whole suite on both engines: `TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest`, then `uv run ruff check` and `uv run ruff format --check`. All must be green, with no PostgreSQL case skipped.
- [X] T054 Walk through `specs/012.11-question-bank-csv/quickstart.md` §3 by hand, including with JavaScript off and at 360 px, and fix anything that differs.
- [X] T055 On delivery (after T047), update `docs/requirements/milestones.md`:
  - move 12.11 to **Delivered** as a short product summary with a link to `specs/012.11-question-bank-csv/spec.md`, with no _Test:_ line;
  - update the group paragraph of 12 if it still speaks of 12.11 as upcoming.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (US9 components)**: no dependency. It must finish before T031 uses the patterns.
- **Phase 2 (foundational)**: no dependency on Phase 1. It blocks every story.
- **US5 (Phase 3)**: needs T010. Its menu links point to the routes of US1 and US2, which answer
  404 until those phases land. That is acceptable on the branch, and the tests of T015 check only
  the links.
- **US1 (Phase 4)**: needs T008, T009 and T010. It is the MVP.
- **US4 (Phase 5)**: needs T008. **US3 (Phase 6)** needs US4.
- **US2 (Phase 7)**: needs Phase 1, US3 and T010.
- **US7 (Phase 8)**: needs T030.
- **US8 (Phase 9)**: needs US5, US1 and US2.
- **US6 (Phase 10)**: needs US3, and US2 for T045.
- **US9 manual (Phase 11)**: needs US2 and US5. T047 gates delivery.
- **Polish (Phase 12)**: after the stories. T055 only after T047.

### Within a story

The pure function comes first, then the messages, then the route and template, then the tests.
Unit tests of a pure function (T021, T025, T028) can be written alongside it.

### Shared files (run tasks on these one at a time)

- `app/services/question_csv.py`: T008 → T017 → T023 → T024 → T026.
- `app/services/question_bank_files.py`: T010 → T018 → T030 → T037.
- `app/routers/admin_subjects.py`: T011 → T019 → T032.
- `tests/unit/test_question_csv.py`: T021 → T025 → T028 → T044.
- `tests/integration/test_admin_question_files.py`: T022 → T035 → T039 → T045.
- `tests/integration/test_question_bank_files_service.py`: T034 → T038.
- `tests/integration/test_form_contract.py` and `form_contract.json`: T016 → T036.
- `README.md`: T043 → T051.
- `app/locale/uk/LC_MESSAGES/messages.po`: T014, T020, T027 and T033, one at a time.

## Parallel Example

```text
# At the start, three independent streams:
Stream A (US9):  T001, T002 in parallel → T003 → T004 → T005, T006 in parallel → T007
Stream B (base): T008, T009, T010 in parallel
Stream C (US4 → US3, pure): T023 → T024 → T025 ; T026 → T027 → T028

# Once Phase 2 is done:
T017 [US1 writer] alongside T018 [US1 service] alongside T011/T012 [US5 pages]

# Once US3 is done:
T029 [uploads] alongside T030 [replace_questions] alongside T031 [import page]
```

## Implementation Strategy

1. **MVP: US5 and US1** (Phases 1–4): the tab shows counts, the actions sit in a menu, and an
   administrator can export any bank. This is shippable on its own: it is a safe, read-only way
   out of the bank.
2. **Then the reader and its checks** (US4, US3): pure and fully tested before anything writes.
3. **Then the import** (US2), **made safe under concurrency** (US7) and **locked down** (US8).
4. **Then the README** (US6), so an AI assistant can write files that import.
5. **Then the screenshots** (US9, manual) and the polish. The milestone is delivered only after
   T047, the product owner's approval.
