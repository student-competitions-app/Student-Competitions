---

description: "Task list for milestone 12.10: a competition's questions only after it starts, and study materials (teacher)"
---

# Tasks: A Competition's Questions Only After It Starts, and Study Materials (Teacher) (Milestone 12.10)

**Input**: Design documents from `/specs/012.10-questions-study-materials/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/files.md](./contracts/files.md), [contracts/services.md](./contracts/services.md),
[contracts/components.md](./contracts/components.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III makes them non-negotiable, and FR-051 asks for the
acceptance scenarios and the milestone's "_Test:_" line. Research R10 maps the scenarios to test
modules.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when
  `TEST_POSTGRES_URL` is set, through the existing `database_url` / `engine` / `session` /
  `client` fixtures in `tests/conftest.py`.
- **Seeders** (existing, unchanged):
  - `make_teacher(engine, settings, email=..., institutions={...}, can_manage=...)`;
  - `make_subject(engine, name, active=True)`;
  - `make_question(engine, subject_id, text, reference_answer, *, deleted=False, additional=False)`;
  - `make_competition(..., starts_at=, cancelled=, stopped=)`, `add_competition_question`,
    `add_competition_team`, `store_results_files`;
  - `set_setting` (in `tests/integration/test_teacher_competitions.py`).
- **The clock**: patch `app.services.competitions.utc_now`, as the `clock` fixtures of
  `test_teacher_results.py` and `test_teacher_competition_entries.py` do. No test waits.
- **Reading files back**: `tests/pdf.py` (`pdf_text`, `pdf_page_texts`, `pdf_pages`,
  `pdf_metadata`).
- **Scenes**:
  - `test_teacher_competition_entries.py` has `Scene`, with `olena` (the setting) and `mykola`
    (no setting, Write link).
  - `test_teacher_results.py` has Olena (setting, Read link), Taras (no setting, Write link) and
    the unlinked cast teacher. Follow its layout for the new download tests.

**Organization**: tasks are grouped by the user stories of spec.md (US1–US8).

- **Phase 1** delivers **US8**: components first (constitution Principle II).
- **Phase 2** holds the shared refactors every download needs.
- **US1** (the Questions page closed) is the MVP: it closes the 12.9 gap on its own.
- **US3 → US2** give the questions file, then its download.
- **US5 → US4** give the study materials file, then its link and download.
- **US6** keeps the study materials in memory.
- **US7** is the product owner's design approval (manual).

**Reference implementation**: milestone 12.8 set every pattern used here. Match its docstring
style, naming, comment density and error handling:

- **Router**: `app/routers/teacher_results.py` (`download_results`, its docstring, the
  `Content-Disposition` headers).
- **Services**:
  - `app/services/results_pdf.py`: `_ResultsDocument`, `render_results_pdf`, `will_page_break`;
  - `app/services/results.py`: `results_file_name`, `ascii_file_name`, `_UNSAFE`.
- **Script**: `scripts/make_results_samples.py`.
- **Tests**: `tests/integration/test_teacher_results.py` (the download section from `published`
  on) and `tests/unit/test_results_pdf.py`.
- **Approval record**: `specs/012.8-publishing-results/design-approval.md`.

**Rules for every task** (plan Constraints; contracts/http-routes.md):

- **Order of checks**: always the role first (`@allow_roles(Role.TEACHER)`). On the `/questions`
  subtree the setting comes next, as the first statement of the handler, before any lookup. The
  downloads never read the setting.
- **Kept out by construction**: `QuestionsSheet` has no field for a reference answer, a bank
  number or a mark. `StudyMaterials` has no bank number. The study materials query filters
  `deleted_at IS NULL AND is_additional = FALSE` in SQL. A template or renderer never hides
  something it was given.
- **Messages**: every new user-facing text is one whole message through `_()`. Then:
  1. run `scripts/translations.sh update`;
  2. translate each Ukrainian entry in `app/locale/uk/LC_MESSAGES/messages.po` with the proposals
     of contracts/files.md §4, never left fuzzy;
  3. run `scripts/translations.sh compile`.
- **No markdown** in fpdf2 calls that draw user text: never pass `markdown=True`.
- **Logging**: none on a download.
- **Determinism**: the renderers read no clock and no randomness. The same input and language
  give the same bytes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US8)

---

## Phase 1: Setup (Components first) — delivers US8

**Purpose**: the two component additions, in the library, the gallery and the UI guidelines,
before the Competitions tab uses them (research R8, contracts/components.md §1–§3). Nothing here
touches the database.

- [ ] T001 [P] [US8] Add `download=False` to `link_button` in `app/templates/components/button.html` per contracts/components.md §2:
  - the signature becomes `link_button(label, href, kind="primary", outline=False, small=False, download=False)`;
  - with `download`, the `<a>` gains the bare attribute ` download` after `role="button"`;
  - `kind="destructive"` with `download=True` calls `template_error("link_button: a download is never destructive")`, as `menu_link` does in `app/templates/components/menu.html`;
  - without `download` the output stays byte-for-byte as before;
  - extend the file's top comment: "A download outside a menu (milestone 12.10) is a `link_button(download=True)` of the secondary kind: it opens no page, and the loading script skips `a[download]`."
- [ ] T002 [P] [US8] Add `aside=None` to `chained_lists` in `app/templates/components/selectors.html` per contracts/components.md §1:
  - the signature becomes `chained_lists(levels, action, aside=None)`;
  - after the levels' `{% endfor %}` and inside `div.selectors-chained`, `{% if aside %}<div class="selectors-aside">{{ aside }}</div>{% endif %}`;
  - without `aside` the output stays byte-for-byte as before;
  - extend the top comment: "`aside`: optional ready markup, usually a download `link_button`, rendered as one more grid cell after the levels: beside the lists on a wide screen, below them on a phone (milestone 12.10). Never a primary action."
- [ ] T003 [US8] Add the `.selectors-aside` rules to `app/static/css/app.css`, in the Selectors section after `.selectors-chained select` (depends on T002):
  - `.selectors-aside { align-self: end; }`;
  - `.selectors-aside [role="button"] { margin-bottom: 0; }`;
  - tokens only, no colour or size literals;
  - `tests/unit/test_stylesheet.py` and `tests/unit/test_frame_stylesheet.py` pass.
- [ ] T004 [US8] Add the gallery entries to `app/templates/pages/admin/components.html` (depends on T001–T003):
  - in `#buttons`, a row with `link_button("Download file", "/admin/components#buttons", kind="secondary", outline=True, small=True, download=True)`;
  - in `#selectors`, a second `chained_lists` sample with two levels and `aside=link_button("Download study materials", "/admin/components#selectors", kind="secondary", outline=True, small=True, download=True)`, after the existing samples, under the small heading "With an aside link".
- [ ] T005 [P] [US8] Extend `tests/unit/test_templates.py` (depends on T001, T002):
  - `link_button("X", "/x", kind="secondary", download=True)` has exactly one `download` attribute, and the default call has none;
  - `kind="destructive", download=True` raises the template error;
  - `chained_lists(levels, "/a")` renders the same markup as before, with no `.selectors-aside`;
  - with `aside="<a>…</a>"` there is one `div.selectors-aside`, the last child of `div.selectors-chained`, holding the markup unescaped.
- [ ] T006 [P] [US8] Extend `tests/integration/test_component_gallery.py` (depends on T004):
  - `SECTIONS["selectors"]` gains "With an aside link";
  - a new test `test_the_aside_and_the_download_link_button`: `#selectors` holds a `div.selectors-aside` with an `a[role=button][download]` reading "Download study materials", and `#buttons` holds an `a[role=button][download]`.
- [ ] T007 [US8] Update `docs/requirements/ui-guidelines.md` (depends on T004):
  - **Selectors** (§615 onwards): the `aside` parameter, with the rule of contracts/components.md §1.
  - **Buttons, and the download rule of 12.8**: `link_button(download=True)`, with the rule of §2.
  - **Actions menu** (around §394–§424):
    - the order becomes **Edit**, **Questions**, **Teams**, **Answers**, **Download questions**, **Grades**, **Publish results**, **Download results**, **Finish competition**, **Cancel competition**;
    - in the example, **Questions** is under `can_manage`, and a `menu_link(_("Download questions"), questions_file_href, download=True)` line for In progress, Finished and Published is added.
  - Then open `/admin/components` at 360 px and at desktop width, light and dark. The aside sits in the third column on desktop and under the lists on a phone, with no sideways scroll.

**Checkpoint**: the gallery shows both additions, the guidelines match, and the whole existing
suite is green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared helpers both downloads need, taken out of the 12.8 code with no change in
its output (research R2, R3, R7; contracts/services.md §1, §4, §5).

- [ ] T008 [P] Create `app/services/file_names.py` per contracts/services.md §4:
  - move `_UNSAFE` and `ascii_file_name` from `app/services/results.py` unchanged;
  - add `clean_file_stem(text: str, fallback: str) -> str`: the 12.8 rule ("each character a file name cannot hold (`/ \\ : * ? " < > |` and control characters) becomes `_`; spaces at the ends and trailing dots are removed; an empty name becomes `fallback`");
  - `results_file_name` in `app/services/results.py` becomes `f"{clean_file_stem(name, 'results')} {starts_at.astimezone(KYIV):%Y-%m-%d}.pdf"`, and `results.py` re-imports `ascii_file_name` from `file_names`;
  - update the import in `app/routers/teacher_results.py`;
  - module docstring as in `results.py`, naming milestones 12.8 and 12.10;
  - `tests/integration/test_results_service.py` and `tests/integration/test_teacher_results.py` stay green.
- [ ] T009 [P] Create `app/routers/downloads.py` with `pdf_download(content: bytes, file_name: str) -> Response` per contracts/services.md §5 (depends on T008):
  - build exactly the headers of `teacher_results.download_results`: `Content-Disposition: attachment; filename="<ascii_file_name(name)>"; filename*=UTF-8''<quote(name, safe='')>`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `media_type="application/pdf"`;
  - `download_results` uses it;
  - move the part of `teacher_results.py`'s docstring about the response into this module's docstring, and point the router's docstring to it;
  - `tests/integration/test_teacher_results.py` stays green.
- [ ] T010 Create `app/services/pdf_layout.py` and refactor `app/services/results_pdf.py` onto it per contracts/services.md §1 and research R3:
  - **Move into `pdf_layout`**: `STATIC`, `FONT_REGULAR`, `FONT_BOLD`, `LOGO`, `FAMILY`, `PRODUCER`, `PDF_LANGUAGE`, `MARGIN`, `LOGO_HEIGHT`, `INK`, `MUTED`, `RULE`, `HEADING_FILL`, every `*_SIZE`, `*_LEADING`, `REGION_GAP`, `CELL_PADDING`.
  - **`PdfDocument(FPDF)`**: the old `_ResultsDocument`, renamed.
  - **`open_document(title, language, created_at, running_title=None) -> PdfDocument`**: margins, auto page break, the two fonts, `alias_nb_pages`, `set_title(title)`, `set_lang`, `set_creation_date`, `set_producer`, `add_page`. The document's running title is `running_title if running_title is not None else title`; the results file passes none, so its output is unchanged.
  - **`draw_header(document, title, subject, meta)`**: the logo, the title, the subject, then the muted meta lines, with exactly today's sizes, leadings and `ln()` gaps; the text colour is back to `INK` at the end.
  - **What stays in `results_pdf.py`**: `render_results_pdf` calls these inside `use_language`, and keeps the regions, the table and `_column_widths`.
  - **Docstrings**: `pdf_layout` says it holds the design shared by the results file, the questions file and the study materials (milestones 12.8 and 12.10).
- [ ] T011 Verify that the refactor changes no byte (depends on T010):
  - run `uv run python scripts/make_results_samples.py`;
  - `git status --short specs/012.8-publishing-results/samples/` must print nothing. If it prints anything, fix T010, never the samples;
  - `uv run pytest tests/unit/test_results_pdf.py tests/integration/test_results_service.py` passes.

**Checkpoint**: three shared modules; the results files and their download are unchanged; the
suite is green.

---

## Phase 3: User Story 1 - Only teachers with the setting see a competition's questions (Priority: P1) 🎯 MVP

**Goal**: the **Questions** entry and page, and every page under it, for teachers with **Can manage
competitions** only, in every status. **Teams** stays open to every teacher.

**Independent Test**: as a teacher with the setting and as teachers without it, with **Read** and
**Write** access, open the menu, the **Questions** page, **Add questions** and every action under
them, for a competition in every status and for a missing one. Compare the menus and the
responses.

- [ ] T012 [US1] Close the page in `app/routers/teacher_competition_entries.py` per research R1 and contracts/services.md §7:
  - in `competition_questions_page`, `require_manage(request, session)` becomes the first statement, before `find_context`;
  - drop `manage = can_manage(...)` and pass `with_bank_mark=True`;
  - `can_change` becomes `competition.status is CompetitionStatus.UPCOMING`;
  - the handler's docstring becomes "only for a teacher with Can manage competitions (milestone 12.10 FR-001–FR-003)";
  - the module docstring's "**Every teacher reads both lists…**" becomes "Every teacher reads a competition's teams; only a teacher with Can manage competitions opens its questions (milestone 12.10) or changes either list, and only while the competition is Upcoming.", and the Order of checks paragraph names the questions page among the manage routes;
  - remove the now-dead "for everyone else it never reaches the page" comment.
- [ ] T013 [US1] Guard the menu entry in `app/templates/pages/teacher/competitions.html` (depends on T012):
  - the **Questions** `menu_link` gets `{%- if can_manage %}…{% endif -%}`;
  - in the template's top comment, "Questions and Teams are for every teacher" becomes "Questions only with the setting (milestone 12.10); Teams for every teacher".
- [ ] T014 [P] [US1] Move the questions page in `tests/integration/test_routes.py` (depends on T012):
  - `"/teacher/competitions/{competition_id:int}/questions"` leaves `ENTRY_READ_PATHS` and joins `MANAGE_PATHS`;
  - both docstrings name milestone 12.10;
  - `test_the_manage_pages_are_found` and `test_every_declared_page_admits_exactly_its_roles` pass.
- [ ] T015 [US1] Update the existing tests that assume every teacher reads the questions, in `tests/integration/test_teacher_competition_entries.py` (depends on T012):
  - the line numbers below are hints from the 12.9 state of the file; find each place by the test or section name, and by searching for `scene.mykola` together with `"questions"`;
  - the section "User story 3: every teacher reads a competition's questions" (around lines 500–590) and the reads at about lines 1309, 1690 and 1701 switch from `scene.mykola` to `scene.olena` where they check content;
  - `test_a_teacher_without_the_setting_reads_the_same_list` becomes `test_a_teacher_without_the_setting_is_refused_the_questions`: `denied(...)` for mykola, and the response text holds no question text;
  - `test_every_teacher_reads_both_lists`: `/questions` leaves `READ_ROUTES`, so it keeps `/teams` only;
  - the 404 case at about line 590 (missing competition for mykola) becomes a 403 case;
  - keep every Teams assertion for mykola unchanged.
- [ ] T016 [US1] Add the refusal tests to `tests/integration/test_teacher_competition_entries.py` (depends on T015):
  - **US1-1**: Olena sees **Questions** and gets 200 on the page in each status: Upcoming, In progress, Finished, Published (via `store_results_files`), Cancelled, and a finished competition of a deactivated subject. The **Additional** badge still shows, as in 12.9.
  - **US1-3 and US1-5**, for mykola (Write) and for a Read-only teacher without the setting, in every status, `denied(...)` on each of:
    - `GET …/questions`, `…/questions?p=2`;
    - `GET …/questions/add`, `POST …/questions`;
    - `GET` and `POST …/questions/<qid>/remove`.

    Every response text equals the first after replacing the requested address (as the existing sweep does), and `snapshot(scene.engine)` is unchanged.
  - **US1-4**: the same refusal for a missing competition id (`MISSING`), for an unknown `subject=`, and with no `subject`.
  - **No leak**: for the refused responses, none of the competition's question texts, reference answers, `question-<id>`, "Question <id>" or "Additional".
  - **US1-6**: `set_setting` takes the setting away from Olena → the next `GET …/questions` is denied; give it to mykola → 200.
  - **US1-7**: administrators and students are denied (already swept by `test_routes.py`; assert one direct case each).
- [ ] T017 [US1] Update the menu tests in `tests/integration/test_teacher_competitions.py` (depends on T013):
  - **Scope**: this task removes **Questions** from the menus of teachers without the setting and nothing else. **Download questions** is added to the same assertions in T027, so between T017 and T027 the tables describe the interim menu (no **Download questions** anywhere) and the suite is green.
  - in the per-status menu table (about lines 2064–2075, a hint; find it by the "Upcoming"/"Running" keys), **Questions** stays only in the manager's rows. The teacher without the setting now has Upcoming `["Teams"]`, Running `["Teams", "Answers"]`, Finished `["Teams", "Answers"]`, Published `["Teams", "Answers", "Download results"]` and Cancelled `["Teams"]`.
  - Update the other menu assertions the same way: about line 106 (`("Questions", …)` only when the setting is held) and about lines 1828–1831.
  - `tests/integration/test_teacher_grades.py:1007` is a manager's menu, so it keeps **Questions** and is not touched here; T027 adds **Download questions** to it. `tests/integration/test_teacher_results.py:329`: drop "Questions" only if that menu belongs to a teacher without the setting; otherwise leave it for T027.

**Checkpoint**: the 12.9 gap is closed. Only managers reach a competition's questions, and the
suite is green.

---

## Phase 4: User Story 3 - The questions file holds the question texts only (Priority: P1)

**Goal**: the questions file's input, renderer and name, with nothing but the texts.

**Independent Test**: render sheets with mixed, additional, deleted and no questions, long
Cyrillic texts and enough entries to fill several pages, in both languages. Read the text back
and compare it with the competition's copies.

- [ ] T018 [US3] Create `app/services/question_files.py` with `QuestionsSheet` and `questions_sheet` per data-model.md §1, §3 and contracts/services.md §3:
  - **`@dataclass(frozen=True) class QuestionsSheet`** with `competition_name: str`, `subject_name: str`, `starts_at: datetime` ("aware, UTC; shown in Kyiv time, labelled; also the PDF creation date") and `texts: tuple[str, ...]` ("the copies' texts in the competition's order; may be empty"). **No other field**: "It has no field for a bank number, a mark or a reference answer, so none can reach the file."
  - **`questions_sheet(session, competition: CompetitionView, subject: Subject) -> QuestionsSheet`**: the texts are `tuple(copy.text for copy in competition_entries.question_copies(session, competition.id))`, and `subject_name=subject.name`. It does not check the status (the router does).
  - **Module docstring**: in the style of `results.py`. The questions file is made at every download and never stored or kept (FR-018). The imports run one way (contracts/services.md).
- [ ] T019 [US3] Create `app/services/question_files_pdf.py` with `render_questions_pdf(sheet, language) -> bytes` per contracts/files.md §1, §3 and research R4 (depends on T010, T018):
  - **Inside `use_language(language)`**: `title = _("Questions of “%(name)s”", name=sheet.competition_name)`, then `open_document(title, language, sheet.starts_at)`, then `draw_header(document, title, sheet.subject_name, [_("Started: %(moment)s", moment=format_local_time(sheet.starts_at, None))])`.
  - **No questions**: after a `REGION_GAP`, the line `_("This competition has no questions.")` in `LINE_SIZE`.
  - **Otherwise**, a private `_numbered_entries(document, entries)` shared with T030:
    - the number column is as wide as the widest "<n>." in bold, plus a gap;
    - each entry draws its number in bold and its text with `multi_cell` to the right, wrapped lines aligned, `\n` kept.
  - **Keeping an entry whole** (FR-040): measure its height first (`multi_cell(..., dry_run=True, output="HEIGHT")` plus the gap). If it fits on an empty page (`height <= document.eph`) but `document.will_page_break(height)`, add a page before it. Otherwise draw it as it comes.
  - **Never** `markdown=True`.
  - **Docstring**: pure, no session, no request, no clock; the look is the starting point of the design rounds.
- [ ] T020 [US3] Add `questions_file_name(sheet, language) -> str` to `app/services/question_files.py` per research R7 (depends on T008, T018):
  - inside `use_language(language)`, `str(_("%(name)s %(date)s questions", name=clean_file_stem(sheet.competition_name, "questions"), date=f"{sheet.starts_at.astimezone(KYIV):%Y-%m-%d}"))`, then `+ ".pdf"`;
  - the whole stem passes `clean_file_stem` once more, so a translation never brings an unsafe character.
- [ ] T021 [US3] Extract and translate the questions file's messages (depends on T019, T020):
  - "Questions of “%(name)s”" → «Питання «%(name)s»»;
  - "This competition has no questions." → «У цьому змаганні немає питань.»;
  - "%(name)s %(date)s questions" → «%(name)s %(date)s питання»;
  - `tests/unit/test_catalogues.py` passes.
- [ ] T022 [P] [US3] Create `tests/unit/test_question_files_pdf.py` with the questions-file cases (depends on T019–T021). Build `QuestionsSheet`s in memory and read them back with `tests/pdf.py`:
  - **Header (US3-1)**: the first page holds the title, the subject and "Started: 21 November 2026, 10:00 (Kyiv time)", and no "Finished", "Published", "Maximum score" or "Answer".
  - **Order and numbering (US3-2)**: "1." to "6." each precede their texts in order.
  - **Nothing but the texts (US3-3)**: a sheet whose texts contain no digits holds no "Question " and no "Additional" / «Додаткове».
  - **Empty (US3-5)**: "This competition has no questions." / «У цьому змаганні немає питань.».
  - **Language (US3-7)**: the Ukrainian file says «Питання «…»» and «Початок: …», and a Cyrillic text with ґ, є, ї and the apostrophe reads back exactly.
  - **Several pages** (40 long texts): every page after the first carries the running title; every page has "Page n of N" with the right N.
  - **Kept whole**: a text that does not fit at the foot of page 1 starts on page 2 whole; a text longer than a page is split.
  - **No markdown**: a text with `**bold**` reads back with its asterisks.
  - **Determinism**: two renders of the same sheet give equal bytes.
  - **Metadata**: `/Lang` and `/Title`.
  - **The file name** (US3-8): "Spring round 2026-11-21 questions.pdf", «Spring round 2026-11-21 питання.pdf», and a name with `/:?` cleaned.
- [ ] T023 [P] [US3] Add a service test for `questions_sheet` to `tests/integration/test_competition_entries_service.py` (depends on T018):
  - a competition holding an ordinary question, an additional one (`additional=True`) and one deleted from the bank afterwards gives all three texts in order (US3-2);
  - editing a bank question after it was copied leaves the sheet's text as copied (US3-4);
  - renaming the subject changes `subject_name` (US3-6).

**Checkpoint**: the file can be made and checked without any route.

---

## Phase 5: User Story 2 - Every teacher downloads the questions of a started competition (Priority: P1)

**Goal**: **Download questions** in the menu and its route, for every teacher, on In progress,
Finished and Published competitions only.

**Independent Test**: as teachers with **Read** and **Write** access, with and without the setting,
linked and not linked, check the menu in every status, download in both languages, check the
download marking and the name, and request the download for every status, a deactivated subject
and a missing competition.

- [ ] T024 [US2] Create `app/routers/teacher_question_files.py` with `download_questions` per contracts/http-routes.md §2 and contracts/services.md §6 (depends on T009, T019, T020):
  - `router = APIRouter()`;
  - `@router.get("/teacher/competitions/{competition_id:int}/questions-file", response_class=Response)` and `@allow_roles(Role.TEACHER)`;
  - the parameter `subject: str | None = Query(None)`.
  - **Body**, in this order:
    1. `selected = offered_subject(offered_subjects(session), subject)`; if `None`, `not_found(request, SUBJECT_NOT_FOUND)`;
    2. `competition = find_competition(session, competition_id, selected)`;
    3. if it is `None` or its status is not in `{IN_PROGRESS, FINISHED, PUBLISHED}`, `not_found(request, COMPETITION_NOT_FOUND)`;
    4. `sheet = questions_sheet(session, competition, selected)`;
    5. `language = request.state.language`;
    6. return `pdf_download(render_questions_pdf(sheet, language), questions_file_name(sheet, language))`.
  - **Never** reads the setting; logs nothing.
  - **Module docstring** in the style of `teacher_results.py`: every teacher downloads; the order of checks; made at every download (FR-018); not under `/questions`, which is the managers' subtree (research R2).
- [ ] T025 [US2] Register the router in `app/main.py`: `app.include_router(teacher_question_files.router)` after `teacher_results.router`, with the import (depends on T024).
- [ ] T026 [US2] Add the menu entry to `app/templates/pages/teacher/competitions.html` (depends on T013, T025):
  - after **Answers** and before **Grades**, `{%- if c.status in ("in_progress", "finished", "published") %}{{ menu_link(_("Download questions"), "/teacher/competitions/" ~ c.id ~ "/questions-file?subject=" ~ selected.id, download=True) }}{% endif -%}`;
  - the template's top comment lists the order of FR-010 and says that Download questions is for every teacher on In progress, Finished and Published competitions, as a link marked as a download;
  - extract and translate "Download questions" → «Завантажити питання» (`scripts/translations.sh update`, translate, `compile`).
- [ ] T027 [US2] Update the menu tests in `tests/integration/test_teacher_competitions.py` (depends on T026):
  - the per-status tables become, for the manager:
    - Upcoming: Edit, Questions, Teams, Cancel competition;
    - Running: Questions, Teams, Answers, Download questions, Finish competition, Cancel competition;
    - Finished: Questions, Teams, Answers, Download questions, Grades, Publish results;
    - Published: Questions, Teams, Answers, Download questions, Grades, Download results;
    - Cancelled: Questions, Teams.
  - for the teacher without the setting:
    - Upcoming: Teams;
    - Running: Teams, Answers, Download questions;
    - Finished: Teams, Answers, Download questions;
    - Published: Teams, Answers, Download questions, Download results;
    - Cancelled: Teams.
  - the **Download questions** link carries the `download` attribute and `?subject=<id>` (US2-5);
  - a deactivated subject's Finished and Published rows offer it (US2-6);
  - US2-10: a full menu's order equals FR-010;
  - also fix `tests/integration/test_teacher_grades.py:1007` and `tests/integration/test_teacher_results.py:329` to include "Download questions".
- [ ] T028 [US2] Add `"/teacher/competitions/{competition_id:int}/questions-file"` to `ENTRY_READ_PATHS` in `tests/integration/test_routes.py`, with the docstring naming milestone 12.10 FR-006 (depends on T025).
- [ ] T029 [US2] Create `tests/integration/test_teacher_question_files.py` with the questions-download cases, following `test_teacher_results.py`'s scene, `clock`, `denied` and `not_found` helpers (depends on T024–T026). Scene: Olena (setting, Read), Taras (no setting, Write to an institution with no team in it), the unlinked cast teacher; "Spring round" of Chemistry with 3 questions, one additional.
  - **US2-1, US2-3, US3**: each of the three teachers downloads it In progress, Finished and Published. Expect:
    - 200 and `application/pdf`;
    - `Content-Disposition` with `filename*=UTF-8''Spring%20round%202027-03-01%20questions.pdf` in English (switch with the language cookie as `test_teacher_results.py` does), and `…%D0%BF%D0%B8%D1%82%D0%B0%D0%BD%D0%BD%D1%8F.pdf` in Ukrainian;
    - `Cache-Control: no-store`;
    - the file's text holds all three texts, numbered, with no reference answer, "Question <id>" or "Additional".
  - **US2-2**: Upcoming and Cancelled answer 404 "Competition not found" for all three teachers.
  - **US2-7**: a missing competition, a competition of another subject → "Competition not found"; an unknown `subject=`, none, and a deactivated subject with no finished competition → "Subject not found".
  - **US2-6**: of a deactivated subject, Finished and Published download, and In progress is 404.
  - **US2-8**: cancelling an In progress competition (`cancelled_at` set directly) makes the next download 404.
  - **US3-6**: renaming the subject changes the file's header and not the file name.
  - **US2-9**: an administrator and a student get 403 with `MISSING`, before any id is read.
  - **No write**: `snapshot(engine)` is unchanged by a download.
  - **No log** (FR-043): under `caplog.at_level(logging.DEBUG, logger="uvicorn.error")`, a successful download and a 404 download add no record from `uvicorn.error` (the application's logger), so no name can be logged.

**Checkpoint**: every teacher hands the teams their questions once a competition starts.

---

## Phase 6: User Story 5 - The study materials hold the bank to learn, and nothing more (Priority: P1)

**Goal**: the study materials' input, renderer and name, without additional or deleted questions
or bank numbers.

**Independent Test**: render the materials of a subject mixing ordinary, additional and deleted
questions, of an empty subject and of 150 questions, in both languages. Read the text back and
compare it with the bank.

- [ ] T030 [US5] Add `StudyMaterials` and `study_materials` to `app/services/question_files.py` per data-model.md §2, §4 (depends on T018):
  - **`@dataclass(frozen=True) class StudyMaterials`**:
    - `subject_name: str`;
    - `downloaded_on: date` ("today in Kyiv; shown as 'Downloaded: …'; its Kyiv midnight is the PDF creation date");
    - `entries: tuple[tuple[str, str], ...]` ("(text, reference_answer) per question, oldest first; may be empty").

    Its docstring: "Two values are equal exactly when the file they make would show the same things."
  - **`study_materials(session, subject: Subject) -> StudyMaterials`**:
    - one query, `select(Question.text, Question.reference_answer).where(Question.subject_id == subject.id, col(Question.deleted_at).is_(None), col(Question.is_additional).is_(False)).order_by(col(Question.id))`. It never selects `Question.id`;
    - `downloaded_on = competitions.utc_now().astimezone(KYIV).date()`, read through the module so tests move it;
    - the caller has checked that the subject is active.
- [ ] T031 [US5] Add `render_study_materials_pdf(materials, language) -> bytes` to `app/services/question_files_pdf.py` per contracts/files.md §2, §3 and research R4 (depends on T019, T030):
  - **Header**: `title = _("Study materials")`; `running = _("Study materials: %(subject)s", subject=materials.subject_name)`. `created_at = datetime.combine(materials.downloaded_on, time(), KYIV)`. Call `open_document(title, language, created_at, running_title=running)` (the parameter T010 adds), then `draw_header(document, title, materials.subject_name, [_("Downloaded: %(date)s", date=format_local_date(created_at, None))])`.
  - **No questions**: `_("This subject has no questions yet.")`.
  - **Otherwise**, `_numbered_entries` with an answer per entry. Below the text, at the text's indent, draw the bold label `_("Answer:")` and the answer in regular type, using `write()` with the left margin set to the indent while it is written and restored after. Line breaks are kept.
  - **Keeping it whole**: the entry's height counts the question and its answer together (FR-040).
- [ ] T032 [US5] Add `study_materials_file_name(materials, language) -> str` to `app/services/question_files.py`: `_("%(subject)s %(date)s study materials", subject=clean_file_stem(materials.subject_name, "study materials"), date=f"{materials.downloaded_on:%Y-%m-%d}")`, cleaned, plus `.pdf` (depends on T020, T030).
- [ ] T033 [US5] Extract and translate the study materials' messages (depends on T031, T032):
  - "Study materials" → «Навчальні матеріали»;
  - "Study materials: %(subject)s" → «Навчальні матеріали: %(subject)s»;
  - "Downloaded: %(date)s" → «Завантажено: %(date)s»;
  - "Answer:" → «Відповідь:»;
  - "This subject has no questions yet." → «З цього предмета ще немає питань.»;
  - "%(subject)s %(date)s study materials" → «%(subject)s %(date)s навчальні матеріали».
- [ ] T034 [P] [US5] Extend `tests/unit/test_question_files_pdf.py` with the study-materials cases (depends on T031–T033):
  - **Header (US5-1)**: only "Study materials", the subject and "Downloaded: 23 November 2026"; no "Started".
  - **Entries (US5-2)**: each numbered text is followed by "Answer:" and its answer, in order.
  - **Empty (US5-5)**: the empty sentence in both languages.
  - **150 entries (US5-6)**: several pages, a running title «Навчальні матеріали: Історія» after page 1, "Page n of N".
  - **Kept whole**: a question with its answer is not split unless taller than a page.
  - **No numbers**: no "Question " in the text.
  - **Determinism**: equal bytes for equal input; different bytes for a different `downloaded_on`.
  - **The file name (US5-7)**: "History 2026-11-23 study materials.pdf" and «Історія 2026-11-23 навчальні матеріали.pdf».
- [ ] T035 [P] [US5] Add service tests for `study_materials` to `tests/integration/test_question_service.py` (depends on T030):
  - **Mixed bank**: a subject with 5 ordinary questions, 2 additional and 2 deleted (one of them additional), plus a question of another subject, gives the 5 ordinary questions oldest first as `(text, reference_answer)` (US5-2, US5-4).
  - **Only excluded questions**: a subject of only additional or deleted questions gives `entries == ()`.
  - **The date**: `downloaded_on` follows the patched clock across Kyiv midnight (22:30 UTC on 22 November is 23 November in Kyiv).

**Checkpoint**: the materials can be made and checked without any route.

---

## Phase 7: User Story 4 - Every teacher downloads a subject's study materials (Priority: P1)

**Goal**: the link beside the subject list and its route, for every teacher, active subjects only.

**Independent Test**: as teachers with **Read** and **Write** access, with and without the setting,
open the tab before and after choosing an active subject, a subject with no competitions and a
deactivated subject. Download in both languages, check the link's marking, request an unknown and a
deactivated subject, and repeat at 360 px and without JavaScript.

- [ ] T036 [US4] Add `download_study_materials` to `app/routers/teacher_question_files.py` per contracts/http-routes.md §3 (depends on T024, T031, T032):
  - `@router.get("/teacher/competitions/study-materials", response_class=Response)`, `@allow_roles(Role.TEACHER)`, `subject: str | None = Query(None)`;
  - `subject_id = parse_id(subject)` (from `teacher_competitions`); `questions.get_active_subject(session, subject_id)` when it is not `None`;
  - a `None` id and `SubjectUnavailable` both answer the same 404: `not_found(request, teacher_questions.SUBJECT_NOT_FOUND)`, that is "Subject not found" / "This subject does not exist or is deactivated.", rendered by `teacher_competitions.not_found` on the Competitions tab's `competition_not_found.html`;
  - then `materials = study_materials(session, found)`, `language = request.state.language`, and `pdf_download(render_study_materials_pdf(materials, language), study_materials_file_name(materials, language))`. US6 replaces the render call with the cache;
  - never reads the setting; logs nothing;
  - extend the module docstring.
- [ ] T037 [US4] Show the link on the tab in `app/templates/pages/teacher/competitions.html` per contracts/components.md §4 (depends on T001–T004, T036):
  - import `link_button`;
  - set `aside` to the download `link_button(_("Download study materials"), "/teacher/competitions/study-materials?subject=" ~ selected.id, kind="secondary", outline=True, small=True, download=True)` when `selected and selected.is_active`, else `none`;
  - pass `aside=aside` to the `chained_lists` call when a subject is selected; the call without a subject is unchanged;
  - extract and translate "Download study materials" → «Завантажити навчальні матеріали».
- [ ] T038 [US4] Add `"/teacher/competitions/study-materials"` to `ENTRY_READ_PATHS` in `tests/integration/test_routes.py` (depends on T036, T028):
  - it is required: `test_the_manage_pages_are_found` asserts that every declared path under `/teacher/competitions/`, minus `ENTRY_READ_PATHS`, equals `MANAGE_PATHS`, so the new path must be in one of the two sets;
  - extend the set's docstring: "and a subject's study materials (milestone 12.10 FR-021), which every teacher may download; without `subject=` it answers 404, not 403";
  - `test_the_manage_pages_are_found`, `test_every_declared_page_admits_exactly_its_roles` and `test_every_declared_page_speaks_the_chosen_language` pass (the cast teacher gets the 404 HTML page, which carries `<html lang>` and the title).
- [ ] T039 [US4] Add the study-materials route and tab cases to `tests/integration/test_teacher_question_files.py` (depends on T036, T037):
  - **US4-1**: with an active subject chosen, `div.selectors-aside a[role=button][download]` reads "Download study materials" and points to `?subject=<id>`. This holds for Olena, Taras and the unlinked teacher, and for a subject with no competitions.
  - **US4-2**: no link before a subject is chosen, and none on a database with no subjects.
  - **US4-3**: no link when a subject of the "Deactivated subjects" group is chosen.
  - **US4-4**: the download answers 200 with the attachment headers and the name in each language.
  - **US4-6**: `subject=` unknown, malformed (`abc`), missing, or deactivated (with and without finished competitions) answers 404 with "Subject not found" and "This subject does not exist or is deactivated."
  - **US4-7**: an administrator and a student get 403.
  - **US5-3**: Olena's file equals Taras's byte for byte, and neither holds an additional question's text.
  - **No write**: a download changes nothing stored.
  - **No log** (FR-043): as in T029, a successful and a 404 download add no `uvicorn.error` record.
  - **No script needed** (FR-022): the link is a plain `<a href … download>` with no `hx-*` or `onclick` attribute and no `<noscript>` alternative, so it works the same with JavaScript off. The behaviour with JavaScript off in a browser is checked by hand in T054.

**Checkpoint**: every teacher hands students the bank to learn.

---

## Phase 8: User Story 6 - The study materials are kept but never out of date (Priority: P2)

**Goal**: the last file per subject and language kept in memory, given only while it matches what
the bank shows now, made once for simultaneous downloads, emptied at every start.

**Independent Test**:

1. Download twice and see the second does not render.
2. Make each kind of change, then download again and see a new file that shows it.
3. Overlap a change with a render.
4. Deactivate the subject.
5. Download twice at once.
6. Start a new application.

- [ ] T040 [US6] Add `StudyMaterialsCache` to `app/services/question_files.py` per data-model.md §5 and contracts/services.md §3 (depends on T030, T031):
  - **`@dataclass(frozen=True) class _Kept`**: `materials: StudyMaterials`, `content: bytes`.
  - **State**: `_kept: dict[tuple[int, Language], _Kept]`, `_locks: dict[tuple[int, Language], threading.Lock]`, `_guard = threading.Lock()`.
  - **`file_for(self, subject_id, language, materials) -> bytes`**:
    1. under `_guard`, get or create the key's lock;
    2. under the key's lock, return `kept.content` if `kept is not None and kept.materials == materials`;
    3. otherwise `content = question_files_pdf.render_study_materials_pdf(materials, language)`, called through the module attribute so tests can count it;
    4. `self._kept[key] = _Kept(materials, content)`; return `content`.
  - **Docstring**: the invariants of data-model §5. There is no invalidation and no logging. It is safe for the uvicorn thread pool, and one process is assumed (research R6).
- [ ] T041 [US6] Create the cache at start in `app/main.py` (depends on T040):
  - in `lifespan`, before `yield`, `app.state.study_materials = StudyMaterialsCache()`;
  - extend the docstring's list: "a fresh, empty study materials cache (milestone 12.10), so every start makes the files again".
- [ ] T042 [US6] Switch `download_study_materials` in `app/routers/teacher_question_files.py` to `request.app.state.study_materials.file_for(found.id, language, materials)` (depends on T036, T041):
  - the subject check stays before it, so a deactivated subject is 404 whatever is kept (US6-7);
  - the docstring describes the kept file.
- [ ] T043 [P] [US6] Create `tests/unit/test_study_materials_cache.py` (depends on T040). Monkeypatch `question_files_pdf.render_study_materials_pdf` with a counting fake:
  - equal materials give the same bytes after one render;
  - different materials render again, and the new file replaces the old (asking with the old materials renders a third time);
  - each language is kept on its own;
  - two threads asking for the same key at once, with the fake waiting on a `threading.Event` that the test sets once the second thread is queued (a two-party barrier would deadlock, since the second thread waits on the key's lock), render once and both get the bytes (US6-8);
  - two keys render independently.
- [ ] T044 [US6] Add the kept-file cases to `tests/integration/test_teacher_question_files.py`, counting renders through `monkeypatch` on `app.services.question_files_pdf.render_study_materials_pdf` (depends on T042):
  - **US6-1**: a second download renders nothing and gives equal bytes.
  - **US6-2**: after each of these, the next download renders once and the file shows the change:
    - adding a question;
    - editing a text or reference answer through `POST /teacher/questions/<id>/edit` as Olena;
    - deleting one;
    - marking or unmarking a question as additional;
    - renaming the subject through the admin route or `UPDATE`.
  - **US6-3**: `UPDATE questions SET reference_answer = … WHERE id = …` on the engine, outside the application, is shown at the next download.
  - **US6-4**: an English download after a Ukrainian one renders. Each language is kept on its own, so a Ukrainian download after that does not render.
  - **US6-5**: moving the clock past Kyiv midnight renders, with the new date in the header and the name.
  - **US6-6**: the counting fake commits an `UPDATE` to a reference answer while it renders the first file. The next download renders again and shows the updated answer.
  - **US6-7**: deactivating the subject after a file was kept gives 404.
  - **US6-9**: a second `TestClient(app)` (a fresh start) renders again.
  - **US6-8 through the route** (FR-036, SC-007):
    1. Make the counting fake wait on a `threading.Event` before it returns. Don't use a two-party barrier: the second request waits on the key's lock and never enters the renderer, so a barrier would deadlock.
    2. Start two downloads of the same subject and language in two threads, using the same `TestClient`.
    3. Wait until the fake has been entered once, then wait briefly so the second request is queued on the lock, then set the event.
    4. Expect one render, two 200 responses and equal bodies.

    The unit case in T043 stays; this one proves the route reaches the cache with a shared key.
- [ ] T045 [US6] Measure and record (depends on T044):
  - with a 150-question subject, time a kept download through the test client (assert under 1 s, SC-005) and a questions download of 10 questions (assert under 1 s, SC-008), in `tests/integration/test_teacher_question_files.py`;
  - time with `time.perf_counter()` and a plain `assert elapsed < 1, f"… took {elapsed:.2f} s"`, as the 500-team publish test does in `tests/integration/test_results_service.py` (about line 790); no extra markers.

**Checkpoint**: large banks render once per change, and every download is current.

---

## Phase 9: User Story 7 - The product owner approves both files and the link (Priority: P2)

**Goal**: repeatable samples and screenshots, review rounds, and the recorded approval (FR-046 to
FR-049). **The milestone is not delivered before T050.**

- [ ] T046 [US7] Create `scripts/make_question_file_samples.py` in the manner of `scripts/make_results_samples.py` per research R11 (depends on T031, T032):
  - no arguments, no database;
  - realistic invented data:
    - a Ukrainian competition of 24 long questions with ґ, є, ї and the apostrophe, some with line breaks;
    - a competition with no questions;
    - a subject «Історія України» of 150 questions with answers of varied length, a few longer than half a page;
    - a subject with no questions;
  - fixed dates;
  - writes `questions-long-{uk,en}.pdf`, `questions-empty-{uk,en}.pdf`, `study-materials-150-{uk,en}.pdf` and `study-materials-empty-{uk,en}.pdf` to `specs/012.10-questions-study-materials/samples/`;
  - prints the render time of the 150-question file;
  - running it twice leaves the files byte for byte unchanged.
- [ ] T047 [US7] Make the screenshots of the Competitions tab with a subject chosen:
  - desktop width and 360 px, Ukrainian and English, light and dark (8 images);
  - with the project's headless Playwright routine (`uv run --with playwright`, a copy of the development database, port 8765);
  - save them to `specs/012.10-questions-study-materials/samples/screenshots/`.
- [ ] T048 [US7] Create `specs/012.10-questions-study-materials/design-approval.md` in the format of `specs/012.8-publishing-results/design-approval.md`:
  - the open points from the spec's checklist: the Ukrainian texts, line breaks, the date format, the link's kind and place;
  - round 1 with the sample and screenshot list and the measured render time.
- [ ] T049 [US7] Hold review rounds with the product owner (manual):
  - make each requested change in the renderers, `pdf_layout`, the component call or the catalogues;
  - re-run T046 and T047;
  - record each round and its decision in `design-approval.md`;
  - rerun the affected tests after each round.
- [ ] T050 [US7] Record the product owner's approval of both files and the link in `design-approval.md`, naming the approved round (manual; not automated, FR-052).

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Update `README.md`:
  - **The Competitions tab's menu paragraph** (about line 115): the order of FR-010; **Questions** only with the setting; **Download questions** on every in-progress, finished or published row for every teacher.
  - **The "Questions and teams of a competition" paragraph** (about line 118): only a teacher with the setting opens **Questions**, in every status. Drop "until milestone 12.10 every teacher still reads…".
  - **A new bullet on the two downloads**:
    - the questions file holds the texts only, is made at every download, and is named "<name> <date> questions.pdf";
    - the study materials are made from the bank without additional or deleted questions and without numbers, kept in memory per subject and language, given only while nothing changed, emptied at every start, and named "<subject> <date> study materials.pdf";
    - the link sits beside the subject list.
  - **The templates and tests trees** (about lines 471 and 481): mention the new modules.
- [ ] T052 [P] Check that `docs/requirements/product-requirements.md`, `technical-requirements.md` and `.specify/memory/constitution.md` (v2.7.1) agree with what was built (FR-050). Change nothing unless they contradict it; if they do, raise it rather than editing the constitution here.
- [ ] T053 Run the whole suite on both engines: `TEST_POSTGRES_URL=… uv run pytest`, plus `uv run ruff check` and `uv run ruff format --check`. All green.
- [ ] T054 Walk through `specs/012.10-questions-study-materials/quickstart.md` §3 by hand, including JavaScript off and 360 px, and fix anything that differs.
- [ ] T055 On delivery (after T050), update `docs/requirements/milestones.md`:
  - move 12.10 to **Delivered** as a short product summary with a link to `specs/012.10-questions-study-materials/spec.md`;
  - in 12.9's summary, remove "Until milestone 12.10 every teacher still reads a competition's **Questions** page before it starts";
  - update the group paragraph of 12 if it still speaks of 12.10 as upcoming.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (US8, components)**: no dependency. It must finish before T037 uses the aside.
- **Phase 2 (foundational)**: no dependency on Phase 1. T008 → T009; T010 → T011. It blocks
  every download task.
- **US1 (Phase 3)**: independent of everything else; can start at once. It is the MVP.
- **US3 (Phase 4)** needs T008 and T010. **US2 (Phase 5)** needs US3, T009 and T013 (the menu
  file).
- **US5 (Phase 6)** needs T018 and T019 (the shared `_numbered_entries`). **US4 (Phase 7)** needs
  US5, T024 (the router) and Phase 1.
- **US6 (Phase 8)** needs US4.
- **US7 (Phase 9)** needs US3 and US5 for the samples, and US4 for the screenshots. T050 gates
  delivery.
- **Polish (Phase 10)**: after the stories. T055 only after T050.

### Within a story

The service or renderer comes first, then the messages, then the route and template, then the
tests. Tests that only need a pure function (T022, T034, T043) can be written alongside it.

### Shared files (run tasks on these one at a time)

- `app/templates/pages/teacher/competitions.html`: T013 → T026 → T037.
- `app/routers/teacher_question_files.py`: T024 → T036 → T042.
- `app/services/question_files.py`: T018 → T020 → T030 → T032 → T040.
- `app/services/question_files_pdf.py`: T019 → T031.
- `tests/integration/test_teacher_question_files.py`: T029 → T039 → T044 → T045.
- `tests/integration/test_teacher_competitions.py`: T017 → T027.
- `tests/integration/test_routes.py`: T014 → T028 → T038.
- `app/locale/uk/LC_MESSAGES/messages.po`: every message task, one at a time.

## Parallel Example

```text
# At the start, three independent streams:
Stream A (US8):  T001, T002 in parallel → T003 → T004 → T005, T006 in parallel → T007
Stream B (base): T008 → T009;  T010 → T011
Stream C (US1):  T012 → T013, T014 in parallel → T015 → T016 → T017

# Once T010 and T018 exist:
T022 [US3 unit tests] alongside T023 [US3 service test]
T034 [US5 unit tests] alongside T035 [US5 service tests]
```

## Implementation Strategy

1. **MVP: US1 alone** (Phase 3). It closes the 12.9 gap: only managers see a competition's
   questions. It is shippable on its own, since nobody else needed the page.
2. **Then the questions file** (Phases 2, 4, 5): teams get their questions once a competition
   starts.
3. **Then the study materials** (Phases 1, 6, 7): students get the bank to learn.
4. **Then the speed** (Phase 8): the kept file.
5. **Then the design rounds** (Phase 9) and the polish (Phase 10). The milestone is delivered only
   after T050, the product owner's approval.
