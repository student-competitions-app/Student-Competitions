---

description: "Task list for milestone 11: the question bank (teacher)"
---

# Tasks: Question Bank (Teacher) (Milestone 11)

**Input**: Design documents from `/specs/011-question-bank/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-048 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R15.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`.
- **Signed-in clients**: `admin_client` and `client_as`. A teacher **with** the setting is a real
  teacher made by `make_teacher(..., can_manage=True)` (T014); the cast teacher has no profile row,
  so it has no setting.

**Organization**: tasks are grouped by user story (US1–US8 in spec.md).

- **Story order**: US2 (reading the bank) comes before US1 (adding), although both are P1, because
  every add, edit and delete returns to the list. US5 (access, P1) is enforced inside every route
  as it is built (Order of checks below); its own phase is the cross-cutting sweep, so it follows
  the last management route (US4).
- **Phases 1–2 come first**, because every story needs them:
  - the pure field rules and paging;
  - the reshaped tables and the migration, with the setting renamed in code;
  - the retirement of the milestone 3 question code;
  - the read-side services and the test helpers.

**Reference implementation**: milestones 6–10.1 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**: `app/services/teacher_access.py` (`_refuse`, `lock=`, `populate_existing`),
  `app/services/subjects.py` (`delete_subject`'s `IntegrityError` branch), `app/services/classes.py`
  (a teacher write in one transaction).
- **Routers**: `app/routers/teacher.py` (`TEACHER_TABS`, `render_teacher`),
  `app/routers/teacher_students.py` (`_parse_id`-style id parsing against `MAX_ID`, the
  `chained_lists` selection, confirmations, Post/Redirect/Get), `app/routers/admin_subjects.py` (the
  not-found page).
- **Components**: `app/templates/components/form.html` (`field`, `form_actions`),
  `card.html`, `selectors.html` (`chained_lists`), `confirmation.html`, `feedback.html`
  (`notice`, `empty_state`, `error_summary`); the gallery `app/templates/pages/admin/components.html`
  with `app/routers/admin_components.py`; `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Migration**: `migrations/versions/2026_10_24_596ead9f1205_drop_teacher_and_student_status.py`
  (batch mode, frozen snapshot, `op.f` names).
- **Tests**: `tests/integration/test_teacher_classes.py`, `test_teacher_students.py`,
  `test_teacher_access.py` (scene, `snapshot`), `test_routes.py`, `test_form_contract.py`,
  `test_page_patterns.py`, `test_component_gallery.py`, `test_migrations.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks** in every handler: role (`@allow_roles(Role.TEACHER)`) → on *manage* routes,
  the setting (`AccessDenied(Role.TEACHER)`, 403) **before any query value, form value or path id
  is read** → ids (404 "Subject not found" / "Question not found") → fields (400) → the service
  write, which re-checks the setting and the ids under lock and maps refusals to the same 403/404.
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON.
- **Redirects**: every change is a `POST` through the existing cross-site check, answering `303`.
  Every redirect, Cancel and back link to the list is built by `list_path` from server-side values
  only; `page` from a request has been through `paging.parse_page` (FR-035).
- **Logging**: services log ids only: `Question created: id=%d subject=%d`,
  `Question updated: id=%d`, `Question deleted: id=%d`.
- **SQL**: no engine-specific SQL; row locks via `with_for_update` (a no-op on SQLite).
- **No new JavaScript**: the subject list reuses `auto-submit.js`; paging and anchors are links.
- **Components first**: each new or extended macro is in the library, its CSS in the Components
  section of `app/static/css/app.css` (tokens only, no inline style), the gallery and
  `ui-guidelines.md` **before** a Questions page uses it (FR-025, FR-030, FR-047).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US8)

---

## Phase 1: Setup (Pure modules)

**Purpose**: the field rules and paging. Nothing here touches the database. No dependency is added.

- [ ] T001 [P] In `app/schemas/question.py`, add the milestone 11 field rules per contracts/services.md §`app/schemas/question.py` and research R4. Keep the milestone 3 types for now (T009 removes them):
  - `QUESTION_FIELD_MAX_LENGTH = 2000`, documented as "also both column lengths";
  - `class InvalidQuestionField(ValueError)` with a `.message`, like `app.schemas.names.InvalidName`;
  - `clean_question_field(raw: str, field: Literal["text", "reference_answer"]) -> str`, in this order: `\r\n` and lone `\r` → `\n`; refuse `\x00`; `str.strip()`; refuse empty; refuse more than 2,000 code points. Inner line breaks, tabs, `<`, `&` and any script are kept.
  - `question_field_errors(text: str, reference_answer: str) -> tuple[dict[str, str], str, str]`: checks **both** fields every time; returns errors keyed by field id (`"text"`, `"reference_answer"`) and the two cleaned values (the raw value where the field failed).
  - **Messages, verbatim**:
    - `text`: "Enter the question text." / "The question text can be at most 2,000 characters." / "The question text cannot contain a null character."
    - `reference_answer`: "Enter the reference answer." / "The reference answer can be at most 2,000 characters." / "The reference answer cannot contain a null character."
- [ ] T002 [P] Rewrite `tests/unit/test_question_schemas.py` for T001 (delete the milestone 3 pydantic cases):
  - trimmed: `"  a \n"` → `"a"`; inner `"a\n\nb"` kept;
  - `"a\r\nb"` and `"a\rb"` → `"a\nb"`, and a 2,000-character value with CRLF line breaks counts each break once;
  - refused with the exact message: `""`, `"   "`, `"\n\t "`, `"a\x00b"`, 2,001 characters (ASCII and Cyrillic `"ї" * 2001`);
  - accepted: exactly 2,000 characters (ASCII, Cyrillic, one including a line break); `"<b>&</b>"` unchanged;
  - `question_field_errors` returns both errors at once, and only the failing one otherwise;
  - text equal to the answer is accepted (spec Edge Cases). Depends on T001.
- [ ] T003 [P] Create `app/services/paging.py` per contracts/services.md §`app/services/paging.py` and research R9. Pure, no imports from `app.models`:
  - `PAGE_SIZE = 10`, `MAX_PAGE = 999_999_999`;
  - `parse_page(raw: str | None) -> int`: `1` for `None`, empty, not `isascii() and isdigit()`, or a value of `0`; `MAX_PAGE` for more than 9 digits; else `int(raw)`;
  - `@dataclass(frozen=True) class PageLink: number: int | None; current: bool` (`None` is a gap);
  - `@dataclass(frozen=True) class Paging` with `number`, `last`, `total`, `size`, `first_item`, `last_item`, `previous`, `next`, `links`, `offset`, and `Paging.build(page, total, size=PAGE_SIZE)`:
    - `last = max(1, ceil(total / size))`, `number = min(max(page, 1), last)`, `offset = (number - 1) * size`;
    - `first_item = offset + 1` and `last_item = min(offset + size, total)`, both `0` when `total == 0`;
    - `previous`/`next` are `None` at the ends;
    - `links`: always the first page, the last page, the current page and one page on each side; a hidden run of **two or more** pages becomes one gap; a run of exactly one is shown as its number.
  - The module docstring says the logic belongs to the page navigation component, not to questions (milestones 12 and 15 reuse it).
- [ ] T004 [P] Create `tests/unit/test_paging.py` (depends on T003):
  - `parse_page`: `None`, `""`, `"abc"`, `"-1"`, `"0"`, `"+2"`, `"1.5"`, `"٣"` → 1; `"1"` → 1; `"4"` → 4; `"999999999"` → 999,999,999; `"1" * 10` and `"9" * 5000` → `MAX_PAGE` (no `ValueError` from Python's integer-string limit);
  - `Paging.build`: ranges for page 4 of 200 (`first_item=31`, `last_item=40`), the last partial page (25 items, page 3: 21–25), one item (1–1 of 1), `total == 0` (page 1 of 1, items 0–0); clamping of page 0 and page 99 to 1 and last; `previous`/`next` at both ends;
  - **The gap table**, as `(page, last) → rendered string` with `…` for gaps, for `last` 1–12 and every page, plus 200: e.g. `(10, 20) → "1 … 9 10 11 … 20"`, `(3, 20) → "1 2 3 4 … 20"`, `(1, 4) → "1 2 3 4"`, `(4, 7) → "1 2 3 4 5 6 7"` (the single hidden pages are shown), and never more than 7 entries;
  - exactly one link is `current`, and it is `number`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the reshaped tables and their migration, the setting renamed in code, the milestone 3
question code retired, the read-side services and the test helpers.

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end, apart from the tests this phase retires (SC-010).

### 2a. Tables, the rename in code, and the migration

- [ ] T005 Update `app/models/question.py` per data-model.md §1:
  - `__table_args__ = {"sqlite_autoincrement": True}`;
  - `subject_id: int = Field(foreign_key="subjects.id", index=True, nullable=False)`: "set at creation and never changed (FR-001)"; no `ON DELETE`;
  - `text` and `reference_answer` both `String(QUESTION_FIELD_MAX_LENGTH)` NOT NULL (were 1000 and 5000);
  - `deleted_at: datetime | None`, `UTCDateTime`, nullable: "`NULL` while listed; set once by a deletion and never cleared (FR-004)";
  - the docstring: the number shown is the id, global and never reused (R1); a deleted question stays stored unchanged; "never rendered on a public page" becomes "shown only in the teacher area"; not personal data, so untouched by data erasure. Depends on T001.
- [ ] T006 Rename the setting **in code** (identifiers only; the visible wording, the sealed payload key and the `describe` lines change in US6):
  - `app/models/teacher.py`: `can_create_competitions` → `can_manage_competitions: bool = Field(default=False, nullable=False)`, docstring per data-model.md §3 (True: may change the question bank, and competitions from milestone 12; False or no profile row: reads the bank only);
  - `app/schemas/teachers.py`: `TeacherDetails.can_manage_competitions`;
  - `app/services/teachers.py`: `TeacherView.can_manage_competitions`, the `update_teacher(..., can_manage_competitions)` parameter, and every attribute read; `details_to_payload`/`details_from_payload` keep the key `"can_create_competitions"` for now (T054);
  - `app/routers/admin_teachers.py`: the form parameter `can_manage_competitions: str | None = Form(None)`, local names, and the `values` keys;
  - `app/templates/pages/admin/teacher_invite.html` and `teacher_form.html`: `checkbox_field("can_manage_competitions", "Can create competitions", checked=values.can_manage_competitions)` (label unchanged until T055); `teachers.html` and `profile.html`: the attribute name only.
- [ ] T007 Follow the rename in the tests (depends on T006):
  - `tests/conftest.py`: `invite(..., can_manage: bool = False)` and `invite_and_accept(..., can_manage=...)`, passing `TeacherDetails(..., can_manage_competitions=can_manage)`;
  - `tests/integration/test_access_control.py`: `p.can_manage_competitions`;
  - every test that posts the checkbox (`grep -rn "can_create_competitions" tests/`): `test_admin_teachers.py`, `test_teacher_invitation.py`, `test_invitation_refusals.py`, `test_form_contract.py` cases;
  - `tests/integration/form_contract.json`: the two teacher forms' field `can_create_competitions` → `can_manage_competitions` (a deliberate contract change: note it in the JSON-adjacent test docstring as milestone 11 FR-009). Leave label assertions ("Can create competitions") alone until US6.
- [ ] T008 Create `migrations/versions/2026_10_27_<rev>_question_bank.py`, generating the id with `uv run alembic revision -m "question bank"`, `down_revision = "596ead9f1205"`, per data-model.md §6 and research R3. A frozen snapshot: plain SQLAlchemy types, no imports from `app`, names via `op.f(...)` matching the naming convention:
  - **Upgrade**:
    1. `op.execute("DELETE FROM questions")`: the milestone 3 sample questions (FR-042);
    2. `with op.batch_alter_table("questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True})` (research R3: SQLite rebuilds the table because of the column changes and picks up `AUTOINCREMENT`; PostgreSQL gets plain `ALTER TABLE` statements, and its id sequence is left alone): add `subject_id INTEGER NOT NULL` with FK `fk_questions_subject_id_subjects` → `subjects.id` and index `ix_questions_subject_id`; add `deleted_at` `sa.DateTime(timezone=True)` nullable; alter `text` to `sa.String(2000)` and `reference_answer` to `sa.String(2000)`;
    3. `with op.batch_alter_table("teacher_profiles")`: `alter_column("can_create_competitions", new_column_name="can_manage_competitions")`, keeping every value.
  - **Downgrade** (lossy by design, R3; say so in the docstring): rename the setting back; `DELETE FROM questions`; drop `deleted_at`, the index, the FK and `subject_id`; restore `String(1000)` and `String(5000)` without `AUTOINCREMENT`. The samples are not re-inserted.
  - The seed revision `bba0b3665864` is **not** edited. Depends on T005, T006.
- [ ] T009 Retire the milestone 3 question code, so the suite runs against the new model (depends on T005, T008):
  - `app/services/questions.py`: delete `list_questions` and the unscoped `create_question`, `get_question`, `update_question`, `delete_question` (and the hard delete); leave a module with the new docstring (the bank's service: teacher-scoped, setting checked inside each write, soft deletion; see contracts/services.md) for T013;
  - `app/schemas/question.py`: remove `QuestionCreate`, `QuestionUpdate`, `QuestionPublic`, `QUESTION_TEXT_MAX_LENGTH`, `REFERENCE_ANSWER_MAX_LENGTH`;
  - `app/routers/pages.py`: `home` no longer imports `list_questions` or `QuestionPublic`; the `try` block reads only `read_database_status`; the `SQLAlchemyError` branch, its log line and its notice "Question data is temporarily unavailable. Please try again in a moment." stay **unchanged** (FR-043, R13); no `questions` in the context;
  - `app/templates/pages/home.html`: remove the `#questions` section; keep the footer database line and the notice;
  - `tests/conftest.py`: remove the `sample_questions` fixture; `tests/unit/test_consent_texts.py`: reword the docstring that mentions it;
  - `tests/integration/test_health.py::test_healthz_stays_ok_while_the_database_is_failing`: monkeypatch `pages.read_database_status` instead of `pages.list_questions`; the assertions stay;
  - `tests/integration/test_home.py`: delete the sample-question, escaping and 500-question list tests and the `Question`/`QuestionCreate` imports (US8 adds the replacements, T061);
  - `tests/integration/test_question_service.py`: delete the milestone 3 cases (rewritten from T014 on).
- [ ] T010 Update `tests/integration/test_migrations.py` (depends on T008, T009):
  - drop the `sample_questions` expectations; at head `questions` is empty;
  - add `test_upgrading_deletes_the_samples_and_keeps_the_setting`: migrate to `596ead9f1205` (the seed's sample questions are present), insert two `teacher_profiles` rows with `can_create_competitions` `true` and `false` (with their `users` rows), upgrade to head, then: `questions` is empty (US8-1, SC-007), and each user keeps their value under `can_manage_competitions` (US6-1, SC-006);
  - a case that, at head, `questions` has `subject_id` NOT NULL with `ix_questions_subject_id`, `deleted_at` nullable and both text columns length 2,000;
  - on SQLite, the `questions` table SQL contains `AUTOINCREMENT`;
  - on PostgreSQL, `questions.id` still takes its default from the original `questions_id_seq`, and a question inserted after the upgrade gets an id greater than every seed sample's id (the table was altered, not rebuilt);
  - the stairway, empty→head and drift checks pass on both engines. Run this module with `TEST_POSTGRES_URL` set before moving on: the migration's PostgreSQL path is only proven there.

### 2b. Read-side services and test helpers

- [ ] T011 [P] In `app/services/teacher_access.py`, add `can_manage_competitions(session, teacher_id, *, lock=False) -> bool` per contracts/services.md and research R5, R7: true only if a `TeacherProfile` row exists for the teacher and its `can_manage_competitions` is true; with `lock`, read the row `.with_for_update(read=True)` and `execution_options(populate_existing=True)`. The docstring says it is the one authority for the setting, and that no profile row means no setting (the test cast's seeded teachers). Depends on T006.
- [ ] T012 [P] In `app/services/subjects.py` (depends on T005):
  - add `list_active_subjects(session) -> list[Subject]`: active subjects only, sorted exactly like `list_subjects` (`name_key`, then `id`, in Python);
  - make `count_subject_uses` return `SELECT count(*) FROM questions WHERE subject_id = :id`, deleted rows included (FR-040, R16), and update its docstring: questions count from milestone 11, deleted ones too, because milestone 15 shows them; competitions add theirs in milestone 12; the FK is the PostgreSQL backstop, the count is the rule on SQLite. `delete_subject` and its refusal are unchanged. This is done here, not in US7, so that from the first stored question no build lets a subject with questions be deleted on SQLite;
  - update the module docstring's "milestones 9 and 10 add references" note: questions count from milestone 11, competitions add theirs in milestone 12.
- [ ] T013 In `app/services/questions.py`, add the read side per contracts/services.md §`app/services/questions.py` (depends on T003, T005, T009):
  - exceptions `SubjectUnavailable(LookupError)`, `QuestionNotFound(LookupError)`, `ManageRequired(PermissionError)`, each with the docstring from the contract;
  - `@dataclass(frozen=True)` `QuestionView` (`id`, `subject_id`, `text`, `reference_answer`), `QuestionPage` (`questions`, `paging`), `Landing` (`page`, `question_id: int | None`);
  - `get_active_subject(session, subject_id, *, lock=False) -> Subject`: `SubjectUnavailable` unless it exists and `is_active`; with `lock`, `FOR SHARE` + `populate_existing`;
  - `question_page(session, subject_id, page) -> QuestionPage`: one `count(*)` and one page query, both `WHERE subject_id = :s AND deleted_at IS NULL`, `ORDER BY id DESC`, `LIMIT size OFFSET paging.offset`, the page clamped by `Paging.build`;
  - `get_question(session, question_id, *, lock=False) -> tuple[QuestionView, Subject]`: `QuestionNotFound` if unknown, `deleted_at` set, or its subject inactive; with `lock`, the question `FOR UPDATE` then the subject `FOR SHARE`, both `populate_existing`;
  - the milestone 12 contract in the docstring: a question may join a new competition only if `deleted_at IS NULL` and it is of the competition's subject.
- [ ] T014 [P] Add test helpers to `tests/conftest.py`, in a new "Milestone 11: the question bank" section (depends on T005, T007):
  - `make_subject(engine, name="Physics", active=True) -> int`: inserted through `app.services.subjects.create_subject` (then `set_subject_active` when `active=False`);
  - `make_question(engine, subject_id, text="Question?", reference_answer="Answer.", *, deleted=False) -> int`: inserted directly (test-only; a question carries no personal data), with `created_at = updated_at = utc_now()` and `deleted_at` set when `deleted`; returns the id;
  - `make_teacher(..., institutions=..., can_manage: bool = False)` passing `can_manage` through `invite_and_accept`;
  - a docstring on each, in the style of `make_class`.
- [ ] T015 Write the read-side service tests (depends on T011–T014):
  - `tests/integration/test_teacher_access_service.py`: `can_manage_competitions` is true for a teacher invited with the setting, false without it, false for a teacher with no profile row (the cast teacher), and `lock=True` returns the same;
  - `tests/integration/test_subject_service.py`: `list_active_subjects` leaves out deactivated subjects and orders like `list_subjects` (mixed case, equal keys by id); `count_subject_uses` counts listed and deleted questions; a subject with only deleted questions raises `SubjectInUse`; a never-used subject is deleted as before (FR-040, SC-004);
  - `tests/integration/test_question_service.py` (rewritten module): `question_page` lists only the subject's undeleted questions, newest first (id DESC), 10/10/5 for 25 questions with 3 in another subject (US2-8), clamps page 0 and 99; `get_active_subject` and `get_question` raise for unknown, deleted, and deactivated-subject cases (FR-038).

**Checkpoint**: run `uv run pytest` on both engines. Everything passes except what this phase
deliberately removed. The question bank has no pages yet.

---

## Phase 3: User Story 2 - A teacher reads the question bank of a subject (Priority: P1) 🎯 MVP

**Goal**: every teacher opens **Questions**, picks an active subject, and reads its questions,
newest first, ten per page, with page navigation, without JavaScript too.

**Independent Test**: with a subject of 25 questions, open the tab as a teacher without the
setting, select the subject, walk the pages, check order, content and navigation, then open
addresses with different `subject` and `page` values (spec US2 Independent Test).

### Components first (library → CSS → gallery → guidelines)

- [ ] T016 [P] [US2] Extend `chained_lists` in `app/templates/components/selectors.html` per contracts/components.md §5: inside each level's `<form>`, after the select, `<noscript>{{ button("Show", kind="secondary", small=True) }}</noscript>` (no `name`). In `app/templates/pages/admin/components.html` `#selectors`, add the note that **Show** appears without JavaScript. In `docs/requirements/ui-guidelines.md` §5 Selectors, add "Without JavaScript, each list shows a **Show** button." (research R11; this also restores the Students tab without JavaScript).
- [ ] T017 [P] [US2] Create `app/templates/components/pagination.html` with `page_navigation(paging, href, noun, label)` per contracts/components.md §1:
  - emits nothing when `paging.total == 0`;
  - `<nav class="pagination" aria-label="{label}">`, then `<p class="pagination-range">{noun} {first_item}–{last_item} of {total}</p>` (en dash, no spaces), then a `<ul>`;
  - **Previous** as `<a href="{href}{previous}" rel="prev">` or `<span class="pagination-off">Previous</span>`; each `PageLink` as a link (`aria-current="page"` on the current one) or `<span class="pagination-gap" aria-hidden="true">…</span>`; **Next** likewise with `rel="next"`;
  - CSS in the Components section of `app/static/css/app.css`, tokens only: `.pagination` (range on its own line; the `ul` a wrapping flex row, no bullets), links and spans at least `--sc-touch-target` high and wide, the current page bold with the primary underline of the area tabs, `.pagination-off` in the muted colour, never a disabled link.
- [ ] T018 [P] [US2] Add `text_card(heading, id=None)` (body via `{% call %}`) and `text_box(label, text)` to `app/templates/components/card.html` per contracts/components.md §4: `<article class="text-card" id=…><h3>…</h3>{{ caller() }}</article>` and `<section class="text-box"><h4 class="text-box-label">…</h4><p class="keep-lines">…</p></section>`, texts escaped. CSS in `app/static/css/app.css`, tokens only: `.text-card` a surface with the card radius and border; `.text-box` with `--sc-neutral-tint`, the control radius, stacked at full width; `.text-box-label` small, semibold, muted. Reuse the existing `.keep-lines` (`white-space: pre-line; overflow-wrap: anywhere`); add it only if missing.
- [ ] T019 [US2] Add the gallery sections (depends on T017, T018):
  - `app/routers/admin_components.py`: sample data built with `Paging.build` for page 1 of 1 (5 items), page 4 of 20 (200 items) and page 20 of 20, and two sample texts: one with several lines and one with a 300-character unbroken word;
  - `app/templates/pages/admin/components.html`: a new `#pagination` section with the three variants (link prefix `"/admin/components?page="`, so every link stays on the gallery), and in `#cards` a text card with two boxes and row actions, and one with the long word and several lines. The gallery still reads no data (`test_the_gallery_reads_no_data`).
- [ ] T020 [US2] In `docs/requirements/ui-guidelines.md` (depends on T019):
  - §5 Components: a "Page navigation" entry (when to use it, above and below a long list, the range, Previous/Next, gaps rule, current page) and a "Text card" entry under Card (long entered texts, such as a question with its reference answer; boxes stack; line breaks kept; anchors land below the pinned frame);
  - §7 Wording: "<Noun> 31–40 of 200", **Previous** and **Next**;
  - §8 Phone behaviour: page navigation wraps; text boxes wrap long words.
- [ ] T021 [US2] Extend `tests/integration/test_component_gallery.py` (depends on T019): `pagination` joins the expected sections with "Questions 31–40 of 200"-style range text for each variant, Previous/Next off at the ends, `aria-current="page"` once per nav, gap marks; `cards` expects the text-card labels; `selectors` still renders. `tests/unit/test_stylesheet.py` and `tests/unit/test_frame_stylesheet.py` pass unchanged (every new class defined and used, tokens only).

### The tab

- [ ] T022 [US2] In `app/routers/teacher.py`, insert `TeacherTab("questions", "Questions", "/teacher/questions")` between Students and Competitions (FR-010). `GET /teacher` still redirects to `/teacher/students`.
- [ ] T023 [US2] Create `app/routers/teacher_questions.py` (`APIRouter(prefix="/teacher/questions")`) and include it in `app/main.py` after `teacher_students.router` (depends on T013, T022):
  - module docstring: the Questions tab; order of checks; why the setting is checked before ids; links to the contracts;
  - `list_path(subject_id: int, page: int = 1, anchor: int | None = None) -> str` → `/teacher/questions?subject=<id>[&page=<n> when n > 1][#question-<anchor>]` (http-routes.md §Helper);
  - `_parse_subject(raw: str | None) -> int | None`: an ASCII integer ≤ `MAX_ID` (from `app.schemas.teachers`), else `None`;
  - `_can_manage(request) -> bool` reading `teacher_access.can_manage_competitions` for `request.state.user`, and `_require_manage(request)` raising `AccessDenied(Role.TEACHER)` without it (used from T031 on);
  - `GET ""` (`/teacher/questions`), `@allow_roles(Role.TEACHER)`, `subject: str | None = Query(None)`, `page: str | None = Query(None)`: the subject is the valid active subject in `subject`, else the only active subject when exactly one is active, else none (FR-014, FR-015, R11; no redirect); the page `parse_page(page)` clamped by `question_page`; renders `pages/teacher/questions.html` via `render_teacher(..., active_tab="questions")` with the subjects, the selection, the `QuestionPage`, `can_manage`, and the page-link prefix `page_href = "/teacher/questions?subject=<id>&page="`. Opening it changes nothing.
- [ ] T024 [US2] Create `app/templates/pages/teacher/questions.html` per http-routes.md §`GET /teacher/questions` (depends on T016–T018, T023):
  - `page_heading("Questions", action=("Add question", "/teacher/questions/new?subject=<id>&page=<current>"))` only with `can_manage` and a selected subject; otherwise no action;
  - `chained_lists` with one level: `id="subject"`, `name="subject"`, label **Subject**, placeholder "Choose a subject", the active subjects, the selected one marked, no `carry` values (so changing the subject drops `page`, FR-017);
  - then exactly one of: `empty_state("No subjects yet", "Ask an administrator to add a subject.")`; `empty_state("Select a subject", "Choose a subject in the list above to see its questions.")`; `empty_state("No questions yet", …)` with the hint "Add the first question with Add question." only with the setting; or `page_navigation(paging, page_href, "Questions", "Pages, top")`, `<ol class="question-list">` of `<li>{% call text_card("Question <id>", id="question-<id>") %}` with `text_box("Question", text)`, `text_box("Reference answer", reference_answer)` and, with the setting, a `row-actions` row of `link_button("Edit", "/teacher/questions/<id>/edit?page=<p>", kind="secondary", small=True)` and `link_button("Delete", "/teacher/questions/<id>/delete?page=<p>", kind="destructive", outline=True, small=True)`, then `page_navigation(…, "Pages, bottom")`;
  - add `.question-list` (no bullets, the card gap) to `app/static/css/app.css` if a class is needed; tokens only.
- [ ] T025 [US2] Update the tests that pin the teacher tabs and route sweeps (depends on T023):
  - `tests/integration/test_teacher_classes.py`: the tab row is Students, Questions, Competitions, in that order, and **Questions** links to `/teacher/questions` (US2-1);
  - `tests/integration/test_teacher_access.py`: exclude paths starting with `/teacher/questions` from `TEACHER_GETS`/`TEACHER_POSTS` (they are swept with real subject and question ids in `test_teacher_questions.py`), with a comment saying so; keep `len(TEACHER_POSTS) == 8`;
  - `tests/integration/test_routes.py`: `/teacher/questions` is a declared teacher page and passes the generic sweep unchanged.
- [ ] T026 [US2] Create `tests/integration/test_teacher_questions.py` with a `Scene` fixture in the style of `test_teacher_access.py`: subjects "Mathematics" (25 questions), "Physics" (3) and a deactivated "Chemistry" (with questions); a teacher with the setting (`make_teacher(..., can_manage=True)`), a teacher without it, and `snapshot(engine)` over `questions` and `teacher_profiles`. Read-side tests (depends on T024, T025):
  - US2-1 the three tabs and their order; `/teacher` still opens Students;
  - US2-2 the list offers only active subjects, in `list_subjects` order;
  - US2-3 exactly one active subject and no `subject` → selected automatically, its list shown (with a separate DB state);
  - US2-4 "Select a subject" with its hint; US2-5 "No subjects yet" with its hint;
  - US2-6 `subject=abc`, `subject=٢`, `subject=` + 40 nines, an unknown id and the deactivated subject → as no selection (and the single-subject auto-selection still applies);
  - US2-7 "No questions yet" for a subject with none and for a subject with only deleted questions; the hint only for the teacher with the setting;
  - US2-8 order, 10/10/5 for Mathematics, nothing from Physics;
  - US2-9 each card has `id="question-<id>"`, heading "Question <id>", the full text then the reference answer, line breaks kept, HTML escaped;
  - US2-10 with 200 questions on page 4: both navs say "Questions 31–40 of 200", Previous → page 3, Next → page 5, the gap marks, `aria-current` on 4, labels "Pages, top" and "Pages, bottom";
  - US2-11 `page` missing, `abc`, `0`, `-1` → page 1; `999` → the last page, without a redirect;
  - US2-12 the subject form has no `page` field (changing the subject opens page 1);
  - US2-13 a reload or a fresh client at `?subject=<id>&page=2` shows the same subject and page;
  - US2-14 without JavaScript: the subject form is a GET form whose action is `/teacher/questions` with a `<noscript>` **Show** submit button; page links are plain `href`s;
  - US2-15 no **Add question**, **Edit** or **Delete** for the teacher without the setting; all three for the teacher with it, Edit/Delete carrying `?page=<current>`;
  - opening the list changes nothing (`snapshot` equal).
- [ ] T027 [P] [US2] In `tests/integration/test_teacher_students.py` (or `test_page_patterns.py`), assert that the Students tab's lists now carry the `<noscript>` **Show** button (research R11); in `tests/integration/test_form_contract.py` and `form_contract.json`, add a case for the Questions list page (its GET subject form) and confirm the noscript button adds no named field.

**Checkpoint**: any teacher can read the bank; nothing can change it yet. Seed questions with
`make_question` or a Python shell to look at it (quickstart §3 step 4).

---

## Phase 4: User Story 1 - A teacher adds questions to a subject (Priority: P1)

**Goal**: a teacher with the setting adds questions with **Save question** and **Save and add one
more question**, with field errors and a Cancel back to the page they came from.

**Independent Test**: as a teacher with the setting, select a subject, add two questions with the
two save buttons, and check where each save leads and what the list shows (spec US1).

### Components first

- [ ] T028 [P] [US1] In `app/templates/components/form.html`, add `textarea_field(id, label, value="", error=None, hint=None, name=None, rows=6, attrs={})` per contracts/components.md §3: the same label, hint, error and `aria-describedby`/`aria-invalid` wiring as `field`, then `<textarea id name rows …>{value}</textarea>` with **no whitespace** between the tags and the value, and `"\n" ~ value` when the value starts with a newline (HTML drops one leading newline). In `app/static/css/app.css`: textareas get `max-width: var(--sc-measure)` instead of `--sc-form-width`, and `resize: vertical`.
- [ ] T029 [P] [US1] Extend `form_actions` in `app/templates/components/form.html` per contracts/components.md §2: signature `form_actions(submit_label, cancel_href=None, kind="primary", name=None, value=None, secondary=None)`; `name`/`value` go on the main button; `secondary` (`{"label", "name", "value"}`) renders a `class="secondary"` submit button right after the main one, before **Cancel**. Existing calls render byte-for-byte as before. On a phone the buttons wrap, each with its full label (CSS only if the existing `.form-actions` rule does not already wrap).
- [ ] T030 [US1] Gallery and guidelines for both (depends on T028, T029):
  - `app/templates/pages/admin/components.html` `#forms`: textarea variants (empty with a hint, filled with line breaks, with an error) and a second form with the two-button actions ("Save question" / "Save and add one more question" / Cancel);
  - `docs/requirements/ui-guidelines.md` §5 Forms: `textarea_field` for multi-line text, keeping line breaks; the second save button is for "save and continue with another", at most one secondary save, the main one returns to the list and comes first (Enter submits it);
  - `tests/integration/test_component_gallery.py`: `forms` expects the textarea labels and "Save and add one more question".

### Service

- [ ] T031 [US1] In `app/services/questions.py`, add `create_question(session, teacher_id, subject_id, text, reference_answer) -> QuestionView` per contracts/services.md: values already cleaned; in one transaction: `can_manage_competitions(lock=True)` → else roll back and `ManageRequired`; `get_active_subject(lock=True)` → else roll back and `SubjectUnavailable`; insert with `created_at = updated_at = utc_now()`, `deleted_at = None`; commit; log `Question created: id=%d subject=%d`. Depends on T013.
- [ ] T032 [P] [US1] In `tests/integration/test_question_service.py`, add create tests (depends on T031): stored in the subject with both timestamps; ids increase and a new question after the newest is deleted (soft) never gets its id (FR-003); duplicates accepted (US1-6); `ManageRequired` for a teacher without the setting and for the cast teacher; `SubjectUnavailable` for unknown and deactivated subjects; nothing stored after each refusal.

### Routes and pages

- [ ] T033 [US1] In `app/routers/teacher_questions.py`, add (depends on T023, T031):
  - a not-found renderer `_not_found(request, heading, text) -> HTMLResponse` (status 404) for `pages/teacher/question_not_found.html`;
  - `GET /new` (*manage*): `_require_manage` first; then `subject` (`_parse_subject` + `get_active_subject`, else 404 "Subject not found" / "This subject does not exist or is deactivated."), `page = parse_page(page)`, `saved == "1"`; renders `pages/teacher/question_form.html` in add mode;
  - `POST ""` (*manage*): `_require_manage` first; form `subject`, `page`, `text`, `reference_answer`, `then` (all `Form("")`, anything else ignored); subject as above (404); `question_field_errors` → 400 with the form, errors beside fields and in the summary, the values **as typed**, no notice; else `create_question` (mapping `ManageRequired` → 403, `SubjectUnavailable` → 404); `then == "another"` → 303 `/teacher/questions/new?subject=<id>&page=<page>&saved=1`, any other `then` → 303 `list_path(subject)`.
- [ ] T034 [P] [US1] Create `app/templates/pages/teacher/question_not_found.html` per http-routes.md §The not-found page: in the teacher frame (Questions current), the heading and text passed in, and the back link `/teacher/questions` "Back to the questions", following `pages/admin/subject_not_found.html`.
- [ ] T035 [US1] Create `app/templates/pages/teacher/question_form.html` for add mode (edit mode is added in T042) per http-routes.md §`GET /teacher/questions/new` (depends on T028–T030, T033):
  - back link `list_path(subject, page)` "Back to the questions"; heading "Add question"; `error_summary`;
  - with `saved`, `notice("The question was saved.", "success")`;
  - "Subject: <name>" as text, not a control (FR-026);
  - a form posting to `/teacher/questions` with hidden `subject` and `page`; `textarea_field("text", "Question", …)` and `textarea_field("reference_answer", "Reference answer", …)`, both `attrs={"required": True, "maxlength": "2000"}` and hint "Up to 2,000 characters.";
  - `form_actions("Save question", cancel_href=list_path(subject, page), name="then", value="list", secondary={"label": "Save and add one more question", "name": "then", "value": "another"})`.
- [ ] T036 [US1] Update the route and form sweeps for the add routes (depends on T033):
  - `tests/integration/test_routes.py`: `("POST", "/teacher/questions")` joins `test_the_write_routes_are_exact`; add `MANAGE_PATHS = frozenset({"/teacher/questions/new"})` (grown by T043 and T049) to the allowed-teacher skip in `test_every_declared_page_admits_exactly_its_roles`, with a guard test naming them and the module docstring explaining it (the cast teacher has no profile, so gets 403; `test_teacher_questions.py` checks them with a real teacher);
  - `tests/integration/test_form_contract.py` + `form_contract.json`: cases for the empty add form, the add form with `saved=1`, and the add form after field errors (fields `page`, `reference_answer`, `subject`, `text`, `then`; buttons `("then", "another")`, `("then", "list")`);
  - `tests/integration/test_page_patterns.py`: an invalid question form is summarised in field order (text, then reference answer) with links to the fields; the add page starts with its back link; at most one primary action.
- [ ] T037 [US1] Add the US1 tests to `tests/integration/test_teacher_questions.py` (depends on T035, T036):
  - US1-1 **Add question** from Physics opens the form with "Subject: Physics", two empty textareas and both buttons;
  - US1-2 **Save question** → 303 to `/teacher/questions?subject=<physics>`, and the new question is first on page 1;
  - US1-3 **Save and add one more question** → 303 to `/new?subject=<physics>&page=<p>&saved=1`; the empty form shows "The question was saved."; its Cancel still returns to page `<p>`;
  - US1-4 empty and spaces-only text or answer, with either button → 400, nothing stored, errors beside the field and in the summary, the values kept;
  - US1-5 2,001 characters after trimming → 400 with the field error and values kept; exactly 2,000 → stored;
  - US1-6 a duplicate text is accepted and both are listed;
  - US1-7 surrounding spaces and line breaks are trimmed; CRLF inner breaks are stored as LF;
  - US1-8 from page 3, Cancel's href is `list_path(subject, 3)`; `page=https://evil.example` or `page=abc` in the form → treated as page 1, never an address (spec Edge Cases);
  - an unknown `then` behaves as **Save question**; reloading the 303 target stores nothing more (SC-009);
  - the list story's end-to-end flow (spec US1 narrative) passes in one test.

**Checkpoint**: a teacher with the setting can fill the bank. SC-001 can be tried by hand.

---

## Phase 5: User Story 3 - A teacher edits a question (Priority: P1)

**Goal**: a teacher with the setting edits any question; the subject cannot change; saving and
Cancel return to the page they came from, at the question.

**Independent Test**: as a teacher with the setting, edit a question added by another teacher from
a page other than the first, and check the stored values, the number and where saving and Cancel
lead (spec US3).

- [ ] T038 [US3] In `app/services/questions.py`, add `update_question(session, teacher_id, question_id, text, reference_answer) -> QuestionView`: in one transaction: setting (`lock=True`) → `ManageRequired`; `get_question(lock=True)` → `QuestionNotFound`; set both fields; `updated_at = utc_now()` only if something changed; the subject and id never touched; commit; log `Question updated: id=%d`. Each refusal rolls back first. Depends on T031.
- [ ] T039 [P] [US3] In `tests/integration/test_question_service.py`, add update tests (depends on T038): fields changed, id and subject kept, `created_at` kept, `updated_at` changed only when a value changed; `ManageRequired` without the setting; `QuestionNotFound` for unknown, deleted and deactivated-subject questions; nothing changed after each refusal.
- [ ] T040 [US3] In `app/routers/teacher_questions.py`, add `GET /{question_id:int}/edit` and `POST /{question_id:int}/edit` (*manage*) per http-routes.md (depends on T033, T038):
  - `_require_manage` first, then `get_question` → 404 "Question not found" / "This question does not exist, was deleted, or its subject is deactivated.";
  - GET: `page = parse_page(page)`; render the form in edit mode with the stored values;
  - POST: form `page`, `text`, `reference_answer` only; a `subject` field is **never read** (FR-031, US3-5); field errors → 400 with the values as typed; `update_question` (`ManageRequired` → 403, `QuestionNotFound` → 404); 303 → `list_path(subject_id, page, anchor=question_id)`.
- [ ] T041 [P] [US3] In `tests/integration/test_page_patterns.py`, cover the not-found page (depends on T034, T040): `/teacher/questions/new?subject=999999` and `/teacher/questions/999999/edit` as a teacher with the setting answer 404 with the headings "Subject not found" and "Question not found" and their texts from http-routes.md, the Questions tab current, and the back link `/teacher/questions` "Back to the questions".
- [ ] T042 [US3] Extend `app/templates/pages/teacher/question_form.html` with edit mode (depends on T035, T040): back link `list_path(subject, page, anchor=id)`; heading "Edit question <id>"; "Subject: <name>" as text; a form posting to `/teacher/questions/<id>/edit` with hidden `page` only (no `subject` field); the textareas filled with the stored values; `form_actions("Save question", cancel_href=list_path(subject, page, anchor=id))` with **no** second button and no `name`/`value`.
- [ ] T043 [US3] Update the sweeps for the edit routes (depends on T040): `("POST", "/teacher/questions/{question_id:int}/edit")` in `test_the_write_routes_are_exact`; `/teacher/questions/{question_id:int}/edit` joins `MANAGE_PATHS` and its guard; `form_contract.json` cases for the edit form and the edit form after field errors (fields `page`, `reference_answer`, `text`); `test_page_patterns.py`: the edit page starts with its back link to the question's anchor.
- [ ] T044 [US3] Add the US3 tests to `tests/integration/test_teacher_questions.py` (depends on T042, T043):
  - US3-1 **Edit** on a question made by another teacher opens the form with the current values (line breaks intact, including a leading newline value) and "Subject: …" as text;
  - US3-2 a valid save updates, keeps the id and subject, and redirects to `?subject=<id>&page=2#question-<id>`;
  - US3-3 Cancel's href from page 2 is the same anchored address; nothing changes;
  - US3-4 emptied or 2,001-character fields → 400, nothing changes, values kept;
  - US3-5 a crafted `subject=<other id>` in the POST is ignored; the question stays in its subject;
  - editing does not move the question in the list (spec Assumptions "newest first").

**Checkpoint**: add and edit work end to end.

---

## Phase 6: User Story 4 - A teacher deletes a question (Priority: P2)

**Goal**: a teacher with the setting deletes a question after a confirmation; it is hidden but
stored unchanged; the list returns to the position the question held.

**Independent Test**: delete questions in each position (middle of a page, last of the whole list,
only one on the last page, only one of the subject) and check the confirmation text, the landing,
that the question is not listed, and that it is stored unchanged (spec US4).

- [ ] T045 [US4] In `app/services/questions.py`, add `delete_question(session, teacher_id, question_id) -> Landing` per contracts/services.md and research R8: in one transaction: setting (`lock=True`) → `ManageRequired`; `get_question(lock=True)` → `QuestionNotFound`; `i` = the number of listed questions of its subject with `id > q.id`; set `deleted_at = utc_now()` and **nothing else** (not `updated_at`); then the next question (largest listed `id < q.id`) at index `i`, else the previous (smallest listed `id > q.id`) at index `i − 1`, else none; `page = target_index // PAGE_SIZE + 1`; commit; log `Question deleted: id=%d`. Depends on T038.
- [ ] T046 [P] [US4] In `tests/integration/test_question_service.py`, add delete tests (depends on T045):
  - the row stays with text, reference answer, subject, id, `created_at` and `updated_at` unchanged, `deleted_at` set (SC-003); never listed again; `get_question` raises;
  - landings with 25 questions: the middle of page 2 → page 2 at the question now at that index; the last on page 1 → page 1 at the question moved up from page 2; the last of the whole list with others on its page → the question before it; the only question on page 3 → page 2 at its last question; the only question of the subject → `Landing(page=1, question_id=None)` (US4-4 to US4-7);
  - `ManageRequired`, `QuestionNotFound` (unknown, already deleted, deactivated subject), nothing changed after each.
- [ ] T047 [US4] In `app/routers/teacher_questions.py`, add `GET /{question_id:int}/delete` and `POST /{question_id:int}/delete` (*manage*) per http-routes.md (depends on T040, T045): `_require_manage` first, then `get_question` → 404; GET renders `pages/teacher/question_delete.html` with `page = parse_page(page)`; POST reads **no** form field, calls `delete_question` (403/404 mapped), and redirects 303 to `list_path(subject, landing.page, anchor=landing.question_id)`, or `list_path(subject)` when `question_id is None`.
- [ ] T048 [P] [US4] Create `app/templates/pages/teacher/question_delete.html`: back link `list_path(subject, page, anchor=id)`; `confirmation("Delete question <id>?", "The question will be hidden from this list and can no longer be added to new competitions. It is not erased, but it cannot be restored.", "/teacher/questions/<id>/delete", "Delete", list_path(subject, page, anchor=id))`. It shows nothing else (FR-033).
- [ ] T049 [US4] Update the sweeps for the delete routes (depends on T047): `("POST", "/teacher/questions/{question_id:int}/delete")` in the exact write list; `/teacher/questions/{question_id:int}/delete` joins `MANAGE_PATHS` and its guard; `form_contract.json` case for the confirmation (no fields); `tests/integration/test_page_patterns.py::test_the_teacher_confirmations` gains the question confirmation (heading, consequence text, destructive **Delete**, Cancel link).
- [ ] T050 [US4] Add the US4 tests to `tests/integration/test_teacher_questions.py` (depends on T048, T049):
  - US4-1 the exact heading "Delete question <id>?" and the exact consequence text;
  - US4-2 Cancel's href is `?subject=<id>&page=<p>#question-<id>`; nothing changes;
  - US4-3 after confirming, the row is stored unchanged with `deleted_at` set and is not listed on any page;
  - US4-4 to US4-7 each landing, by the 303 `location` (page and anchor) and by the anchored card existing on that page;
  - US4-8 the deleted question's edit and delete addresses (GET and POST) → 404 "Question not found";
  - reloading the landing repeats nothing (SC-009); a second POST to delete → 404.

**Checkpoint**: the bank is complete for teachers with the setting.

---

## Phase 7: User Story 5 - Only the right people reach the question bank (Priority: P1)

**Goal**: every page and action is checked on the server, in the order access → existence →
fields, including crafted requests and changes between a form and its save.

**Independent Test**: for every page and action of the tab, send requests as each role and as a
teacher with and without the setting, including typed addresses and crafted submissions for
unknown, deleted and deactivated-subject questions (spec US5).

- [ ] T051 [US5] In `tests/integration/test_teacher_questions.py`, add the access sweep, parametrised over the 7 endpoints built from the router's own route table (with a guard that there are exactly 7, 4 GET and 3 POST), with real subject and question ids (depends on T047):
  - US5-1 administrator, student and administrator-using-the-student-role → 403 on all 7, naming the current role; anonymous → 303 `/login`;
  - US5-2 teacher without the setting → 403 on the 3 manage pages and 3 manage actions, also with an unknown id (`999999`), a deleted question and a deactivated subject (access before existence), and nothing changes (`snapshot`);
  - the teacher with the setting is admitted to all 7 (SC-002);
  - US5-3 with the setting, add to `subject=abc`, an unknown subject and the deactivated subject (GET `/new` and POST) → 404 "Subject not found", nothing stored;
  - US5-4 with the setting, open, edit and delete an unknown question, a deleted question and a question of the deactivated subject → 404 "Question not found", nothing changed;
  - `/teacher/questions/abc/edit` → the application's 404 for everyone;
  - no response anywhere is FastAPI's JSON 422 (odd values for `page`, `subject`, `then`, missing fields).
- [ ] T052 [US5] In the same module, add the race cases (US5-5, US5-6): open the edit form, then, directly through the services, delete the question / deactivate its subject / remove the teacher's setting (`update_teacher(..., can_manage_competitions=False)`), then POST the form → 404 / 404 / 403, and nothing changes. The same for the add form (subject deactivated → 404; setting removed → 403) and the delete confirmation. Add service-level counterparts in `tests/integration/test_question_service.py` if not already covered by T032, T039, T046.
- [ ] T053 [US5] Review `app/routers/teacher_questions.py` against http-routes.md §Order of checks: every *manage* handler calls `_require_manage` before reading any id, query or form value (FastAPI parses parameters before the body runs, so ids must arrive as plain strings or path ints that are not looked up before the check); fix any handler that looks something up first. Add one test per manage route that monkeypatches `get_active_subject`/`get_question` to fail loudly and shows a teacher without the setting still gets 403.

**Checkpoint**: SC-002 holds; all US1–US5 scenarios are covered.

---

## Phase 8: User Story 6 - The setting becomes "Can manage competitions" (Priority: P2)

**Goal**: the setting is called **Can manage competitions** everywhere it is shown or set, keeps
every value, and old invitations still carry theirs.

**Independent Test**: compare every teacher's value before and after the upgrade (T010), then
check every place where the setting is shown or set for the new name (spec US6).

- [ ] T054 [US6] Rename the sealed key and the describe lines in `app/services/teachers.py` per contracts/services.md §`app/services/teachers.py` and research R12:
  - `details_to_payload` writes `"can_manage_competitions"`;
  - `details_from_payload` accepts exactly `{"institutions", "can_manage_competitions"}` or the legacy `{"institutions", "can_create_competitions"}` (comment: milestone 8 invitations, removable after 2026-11-03 with its test); any other key set raises `ValueError` as today;
  - `describe`: "Can manage competitions: Yes" explained as "You will be able to manage competitions and change the question bank."; "Can manage competitions: No" explained as "You will not be able to manage competitions or change the question bank.";
  - `app/services/invitations.py`: the docstring example becomes "Can manage competitions: Yes".
- [ ] T055 [P] [US6] Rename the label in the templates: `app/templates/pages/admin/teachers.html` (column heading and `cell` label), `teacher_invite.html` and `teacher_form.html` (checkbox label), `app/templates/pages/profile.html` (details label), and the gallery checkbox in `app/templates/pages/admin/components.html`. The invitation email gets the new lines through `describe` (check `app/services/email.py` / its template for any literal).
- [ ] T056 [US6] Update the tests for the new wording (depends on T054, T055):
  - `tests/integration/test_admin_teachers.py`: the column heading and both checkbox labels (US6-2);
  - `tests/integration/test_teacher_invitation.py`: the acceptance page detail line and the explanation (US6-2); a new case accepting an invitation sealed with the **legacy** payload (`can_create_competitions: true`) stores `can_manage_competitions = True` (US6-3);
  - `tests/unit/test_sealing.py`: payload round-trip with the new key; the legacy key set accepted; mixed or extra keys refused;
  - `tests/integration/test_invitation_refusals.py`, `tests/unit/test_email.py`, `tests/integration/test_profile.py`, `tests/integration/test_component_gallery.py` (`forms` expects "Can manage competitions");
  - `tests/unit/test_consent_texts.py` is **unchanged**: the published teacher consent text v1 keeps "create competitions" (append-only, research R12).
- [ ] T057 [P] [US6] Add a guard test in `tests/unit/test_templates.py` (or a new `tests/unit/test_setting_name.py`): no file under `app/` (templates and Python) contains "Can create competitions" or `can_create_competitions`, except the one legacy key in `app/services/teachers.py`'s `details_from_payload` (SC-006). Migrations are out of scope (frozen).

**Checkpoint**: SC-006 holds.

---

## Phase 9: User Story 7 - A subject with questions can only be deactivated (Priority: P3)

**Goal**: any question, deleted or not, makes its subject undeletable; deactivating and activating
hide and show its questions.

**Independent Test**: try to delete a subject with listed questions, with only deleted questions,
and with none (spec US7).

The rule itself (`count_subject_uses` counting every question) and its service tests are in T012 and
T015, so this phase covers it through the pages.

- [ ] T058 [US7] In `tests/integration/test_admin_subjects.py`, through the admin pages (depends on T012, T014): deleting a subject whose questions are all deleted gets the 409 refusal "“<name>” is in use and cannot be deleted. You can deactivate it instead." (US7-1); deleting a subject with listed questions gets the same refusal; a never-used subject is deleted (US7-2). The existing monkeypatched cases stay.
- [ ] T059 [US7] In the same module (depends on T024): deactivate then activate a subject through the admin pages, and the teacher's list shows its undeleted questions again, unchanged, and still not its deleted ones (US7-3, FR-041).

---

## Phase 10: User Story 8 - The sample questions are removed (Priority: P3)

**Goal**: the home page lists no questions, keeps its database line and unavailable message, and
the teacher card mentions the question bank. (The code removal and the migration were done in
T008–T010.)

**Independent Test**: upgrade a database holding the samples; check they are gone; inspect the home
page for each role, with the database reachable and unreachable (spec US8).

- [ ] T060 [US8] In `app/routers/areas.py`, set `TEACHER_AREA.description` to "Manage your classes and students, and see the question bank." (FR-044, R13).
- [ ] T061 [US8] In `tests/integration/test_home.py`, add (depends on T009, T060):
  - for each single-role cast member and anonymous: the home page has no `#questions` section and no question text, and the footer still has the database line (US8-2, SC-007);
  - with a question stored through `make_question`, the home page still lists nothing;
  - with `read_database_status` failing, the page is 200 with "Question data is temporarily unavailable. Please try again in a moment." (US8-3);
  - a teacher's home page card reads "Manage your classes and students, and see the question bank." (US8-4).
  `tests/integration/test_layout.py::test_the_database_line_is_in_the_footer_of_the_home_page_only` passes unchanged.

---

## Phase 11: Polish & Cross-Cutting Concerns

- [ ] T062 Measure the three-tab row (FR-011, R14, quickstart §6) with headless Playwright, following the memory recipe (`uv run --no-project --with playwright -- python -I <script>` from the scratchpad, a database copy, port 8765; never add Playwright to the project): `/teacher/questions` at 360 × 640 and 375 × 667 with Questions current and with Competitions current — the frame's `getBoundingClientRect().bottom`, the tab row's row count, whether it wraps; then follow a `#question-<id>` link and a field-error link and check the target sits below the frame. Record the numbers in `specs/011-question-bank/pr-notes.md`; update the clearance note in `docs/requirements/ui-guidelines.md` only if the result changes it.
- [ ] T063 [P] Take review screenshots with the same recipe into the git-ignored `screenshots/` folder: the list with page navigation, the add form with errors and with the saved notice, the edit form, the delete confirmation, a question with a 300-character word, and `/admin/components#pagination`, `#forms`, `#cards`, at 1280 × 800 and 360 × 640, Light and Dark, and once with JavaScript disabled (the **Show** buttons). Check no sideways scroll (SC-008).
- [ ] T064 [P] Update `README.md`: the teacher area's **Questions** tab (subject list, paging, add/edit/delete for teachers with **Can manage competitions**, soft deletion), the renamed setting, and the removal of the home page sample questions.
- [ ] T065 Final pass over `docs/requirements/ui-guidelines.md`: every new or extended component (page navigation, two-button `form_actions`, `textarea_field`, `text_card`/`text_box`, the `chained_lists` **Show** fallback) is in §5, with §7 wording and §8 phone behaviour, and matches the gallery.
- [ ] T066 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest`, then the same with `TEST_POSTGRES_URL` set. Everything passes on both engines (SC-010).
- [ ] T067 Walk through [quickstart.md](./quickstart.md) §2–§5 and §7 not already covered by T062–T063, including a real upgrade of a copy of `data/app.db` (quickstart §2). Complete `specs/011-question-bank/pr-notes.md` for the PR description: what changed, the tab-row measurements, the no-script **Show** fallback (and that it also restores the Students tab), the replaced tests (sample questions, old setting name; SC-010), the lossy downgrade (R3), and the legacy invitation key with its removal date.
- [ ] T068 On delivery, update `docs/requirements/milestones.md`: move 11 from **Upcoming** to **Delivered** as a short summary in the style of the others, with `_Spec:_ [011-question-bank](../../specs/011-question-bank/spec.md)`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001–T004 are all parallel (two pairs of module + test).
- **Foundational (Phase 2)**: after Setup; blocks every story.
  - T005 and T006 first; T007 after T006; T008 after T005 and T006; T009 after T005 and T008;
    T010 after T008 and T009.
  - T011, T012 and T014 can run alongside each other once T006/T007 are done; T013 after T009;
    T015 last.
- **US2 (Phase 3)**: after Foundational. The components (T016–T021) come before the page
  (T024), per Principle II.
- **US1 (Phase 4)**: after US2 (the save returns to the list). T028–T030 before T035.
- **US3 (Phase 5)**: after US1 (it reuses the form template, the not-found page and
  `MANAGE_PATHS`).
- **US4 (Phase 6)**: after US3 (`get_question` locking and the edit-mode anchors); its service can
  start after T038.
- **US5 (Phase 7)**: after US4 (it sweeps all 7 endpoints). The checks themselves are built in
  T033, T040 and T047.
- **US6 (Phase 8)**: after Foundational (T006–T008). Independent of US1–US5; can run in parallel
  with them.
- **US7 (Phase 9)**: after Foundational (the rule is in T012); T059's US7-3 case needs the list
  page (US2).
- **US8 (Phase 10)**: after Foundational (T009). Independent of the other stories.
- **Polish (Phase 11)**: after every story.

### User Story Dependencies

- **US2 (P1)**: Foundational only.
- **US1 (P1)**: US2.
- **US3 (P1)**: US1.
- **US4 (P2)**: US3.
- **US5 (P1)**: US1, US3, US4 (all management routes exist).
- **US6 (P2)**: Foundational only.
- **US7 (P3)**: Foundational; US2 for its activation case.
- **US8 (P3)**: Foundational only.

### Within Each User Story

- Components (macro → CSS → gallery → guidelines) before any page that uses them.
- Service before routes; routes before templates that post to them; route-table and form-contract
  tests updated in the same story that adds the route, so the exact sweeps never go red.
- Tests are written alongside and must fail before the implementation where practical.
- `app.css`, `components.html`, `form.html`, `test_teacher_questions.py`, `test_routes.py` and
  `form_contract.json` are touched by several stories: tasks on the same file are not [P] against
  each other.

### Parallel Opportunities

- **Phase 1**: all four tasks.
- **Phase 2**: T011, T012, T014.
- **US2**: T016, T017, T018 (three different component files; T017 and T018 both add CSS, so merge
  the `app.css` edits in order); T027 alongside T026.
- **US1**: T028 and T029 are in the same file (`form.html`) — do them in sequence; T032 and T034
  alongside the routes.
- **Cross-story**: US6 (T054–T057) and US8 (T060–T061) can run in parallel with US2→US1→US3→US4.

---

## Parallel Example: after Foundational

```bash
# Stream A, the bank (US2 → US1 → US3 → US4 → US5):
Task: "T016 Extend chained_lists with a <noscript> Show button in app/templates/components/selectors.html"
Task: "T017 Create page_navigation in app/templates/components/pagination.html"
Task: "T018 Add text_card and text_box to app/templates/components/card.html"

# Stream B, the rename in words (US6):
Task: "T054 Rename the sealed key and describe lines in app/services/teachers.py"
Task: "T055 Rename the label in the admin, profile and gallery templates"

# Stream C, the home page (US8):
Task: "T060 Set TEACHER_AREA.description in app/routers/areas.py"
Task: "T061 Add the home page tests in tests/integration/test_home.py"
```

---

## Implementation Strategy

### MVP First (User Story 2)

1. Phase 1 (T001–T004) and Phase 2 (T005–T015): the new tables, the migration, the setting renamed
   in code, the samples gone, the read services.
2. Phase 3 (T016–T027): the components and the read-only **Questions** tab.
3. **Stop and validate**: every teacher can browse a seeded bank, with and without JavaScript.

### Incremental Delivery

1. **+ US1**: adding questions (the bank can be filled through the website).
2. **+ US3**: editing.
3. **+ US4**: soft deletion with the landing rule.
4. **+ US5**: the full access and race sweep.
5. **+ US6, US7, US8** (in parallel if staffed): the visible rename, the subject in-use rule, the home
   page card.
6. **Polish**: the tab-row measurement, screenshots, README, both engines, PR notes, and
   `milestones.md` on delivery.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Commit after each task or logical group. Each story phase ends at a checkpoint that can be
  validated on its own.
- Nothing from milestone 12 is built: the **Competitions** placeholder is untouched (FR-049).
- The manual checks (T062, T063, T067) are part of the milestone's _Test:_ line; the suite has no
  browser before milestone 16.
