---

description: "Task list for milestone 12.9: additional questions in the question bank (teacher)"
---

# Tasks: Additional Questions in the Question Bank (Teacher) (Milestone 12.9)

**Input**: Design documents from `/specs/012.9-additional-questions/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III makes them non-negotiable, and FR-035 asks for the
acceptance scenarios and the milestone's "_Test:_" line. The scenario-to-module mapping is research
R9.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`.
- **Seeders** (existing):
  - `make_teacher(engine, settings, email=..., institutions={...}, can_manage=...)`;
  - `make_subject`, `make_question`, `make_competition`, `add_competition_question`,
    `add_competition_team`, `save_team_answer`, `grade_answer`, `store_results_files`.
  - **Changed** (T009): `make_question(..., additional=False)`.
- **Scenes**:
  - `tests/integration/test_teacher_questions.py` has `Scene`, with `manager` (the setting, Read
    link) and `reader` (no setting, Write link), and the helpers `snapshot`, `stored`, `cards`,
    `card_ids`, `empty_state`, `denied`, `remove_setting`.
  - `tests/integration/test_teacher_competition_entries.py` has `Scene`, with `olena` (the setting)
    and `mykola` (no setting, Write link), and the `clock` fixture.
  - Extend these; do not build new scenes.
- **Response bodies**: "nothing leaks" is asserted on the raw `response.text`. It must not contain
  an additional question's text, its reference answer, `question-<id>`, "Question <id>", or the
  badge word ("Additional" in English, «Додаткове» in Ukrainian).

**Organization**: tasks are grouped by user story (US1–US6 in spec.md).

- **Phase 1** delivers **US6**: the badge and the text card's badge, in the library and the
  gallery, checked against the guidelines (constitution Principle II).
- **Phase 2** is the column, its migration, the seeder and the view field. Every story needs them.
- **US1** (marking), **US2** (other teachers do not get them) and **US3** (crafted requests) are the
  MVP: the mark exists and is kept back.
- **US4** (the mix in a competition) and **US5** (the setting changes) complete the rules.

**Reference implementation**: milestones 11 and 12.2 set every pattern used here. Match their
docstring style, naming, comment density and error handling:

- **Services**:
  - `app/services/questions.py`: `question_page`, `_listed`, `create_question`, `update_question`
    (the `changed` tuple), `_require_manage`, `get_question`;
  - `app/services/competition_entries.py`: `question_page` (the join selecting
    `Question.deleted_at`), `CompetitionQuestionView`, `get_competition_question`.
- **Routers**:
  - `app/routers/teacher_questions.py`: `_form`, `_can_manage`, `_require_manage`, the plain-string
    `Form("")` reading;
  - `app/routers/teacher_competition_entries.py`: `competition_questions_page` (`can_change`),
    `add_questions_page`.
- **Templates**:
  - `components/badge.html`: `status_badge`, which uses `pgettext` with a context per kind;
  - `components/card.html`: `text_card`;
  - `components/form.html`: `checkbox_field`;
  - pages: `pages/teacher/questions.html`, `question_form.html`, `competition_questions.html`,
    `competition_questions_add.html`;
  - the gallery: `pages/admin/components.html` with `app/routers/admin_components.py`.
- **Migration**: `migrations/versions/2026_10_27_3e32707ed794_question_bank.py`, for
  `batch_alter_table("questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True})`;
  the head is `c730fd883079`.
- **Tests**: `tests/integration/test_teacher_questions.py`, `test_question_service.py`,
  `test_teacher_competition_entries.py`, `test_competition_entries_service.py`,
  `test_migrations.py`, `test_form_contract.py` (its docstring's list of deliberate changes),
  `test_component_gallery.py`, `tests/unit/test_templates.py`, `tests/html.py`.

**Rules for every task** (plan Constraints; contracts/http-routes.md §Order of checks):

- **Order of checks**: the role (`@allow_roles(Role.TEACHER)`), then on a manage route the setting
  as the first statement of the handler, before any id is parsed or looked up. No task changes this
  order.
- **Left out, not hidden**: for a teacher without **Can manage competitions**, an additional
  question is never read into a view (`include_additional=False`), and the bank's mark on a
  competition page is never read (`with_bank_mark=False`). A template never hides an additional
  question or a mark it was given (constitution IV).
- **Required keywords**:
  - `questions.question_page(..., include_additional=)`,
    `competition_entries.question_page(..., with_bank_mark=)` and
    `questions.update_question(..., is_additional=)` take keyword-only arguments with **no
    default**;
  - `create_question(..., is_additional=False)` keeps a default;
  - every existing caller, tests included, is updated in the task that changes the signature, so
    the suite stays green after each task.
- **Values**: the checkbox is read as `additional: str | None = Form(None)`; marked means a non-empty
  string (`bool(additional)`). It is never a `bool` parameter, so no input produces FastAPI's 422.
- **Messages**: every new user-facing text goes through `_()`, `pgettext()` or `{{ _("…") }}` as one
  whole message. Run `scripts/translations.sh update`, translate the Ukrainian entry in
  `app/locale/uk/LC_MESSAGES/messages.po` (never left fuzzy), then
  `scripts/translations.sh compile`.
- **Logging**: unchanged lines carrying ids only ("Question created: id=%d subject=%d", "Question
  updated: id=%d"). The mark is not logged.
- **Components first**: the badge and the text card's badge are in the library and the gallery
  before any teacher page uses them. CSS only if needed, tokens only (research R7).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US6)

---

## Phase 1: Setup (Components first)

**Purpose**: the **Additional** badge and the text card's optional badge, in the library and the
gallery, checked against `docs/requirements/ui-guidelines.md` (already updated in `3a4e5bb`)
(research R7, contracts/components.md §1, §2). Nothing here touches the database. Delivers **US6**.

- [ ] T001 [P] Add `additional_badge()` to `app/templates/components/badge.html` per contracts/components.md §1:
  - after `access_badge`: `{% macro additional_badge() -%}{{ badge(pgettext("question", "Additional"), "info") }}{%- endmacro %}`;
  - a comment above it, in the style of the file: "The mark of an additional question (milestone
    12.9 contracts/components.md §1): a mark of a record, not a status. The context `question` lets
    the Ukrainian word agree with «питання» («Додаткове»). Pages show it only to teachers with
    **Can manage competitions**; the macro does not decide that."
  - No CSS: `.badge-info` exists.
- [ ] T002 [P] Add the optional `badge` to `text_card` in `app/templates/components/card.html` per contracts/components.md §2:
  - the signature becomes `text_card(heading, id=None, badge=None)`;
  - the heading becomes `<h3>{{ heading }}{% if badge %} {{ badge }}{% endif %}</h3>`;
  - without `badge` the output must stay byte-for-byte as before;
  - extend the macro's comment: the badge is a rendered badge (markup), placed after the heading's
    text inside the `h3`, so it is read with the heading and wraps below it as one unit on a narrow
    screen.
- [ ] T003 Add the gallery entries in `app/templates/pages/admin/components.html` (depends on T001, T002):
  - import `additional_badge` with the other badges;
  - in `#badges`, after the "Competition statuses" row, add `<h3>Marks</h3>` and a `button-row`
    holding `{{ additional_badge() }}`;
  - in `#cards` → "Text cards", give the "Question 58" card `badge=additional_badge()`, keeping its
    long-word sample;
  - add nothing to `app/routers/admin_components.py` unless a sample value is needed.
- [ ] T004 Extract and translate the badge's message (depends on T001):
  - `scripts/translations.sh update`;
  - in `app/locale/uk/LC_MESSAGES/messages.po`, `msgctxt "question"` / `msgid "Additional"` →
    «Додаткове»;
  - `scripts/translations.sh compile`; `tests/unit/test_catalogues.py` passes.
- [ ] T005 [P] Extend `tests/unit/test_templates.py` (depends on T001, T002, T004):
  - `additional_badge()` renders exactly one `<span class="badge badge-info">Additional</span>`, and
    «Додаткове» under the Ukrainian language (use the file's existing language switching for
    `status_badge`);
  - `text_card("Question 57")` without `badge` renders the same markup as before (`<h3>Question
    57</h3>`);
  - `text_card("Question 57", badge=additional_badge())` puts the badge inside the `h3`, after the
    text and one space, and escapes the heading text but not the badge markup.
- [ ] T006 [P] Extend `tests/integration/test_component_gallery.py` (depends on T003):
  - `SECTIONS["badges"]` gains "Marks" and "Additional";
  - a new test, `test_the_additional_badge_and_the_text_card_badge`: in `#badges`, one
    `span.badge.badge-info` reads "Additional"; in `#cards`, the `h3` of `#gallery-question-58`
    reads "Question 58" followed by that badge.
- [ ] T007 Check `docs/requirements/ui-guidelines.md` §Badges and §Cards against T001–T003 (depends on T003). The signature `text_card(heading, id=None, badge=None)`, the `info` kind and the wording "Question 57 Additional" must match what was built; fix the guidelines if they differ. Then open `/admin/components` at 360 px and at desktop width, in light and dark. If the badge crowds the heading's text, add only `.text-card h3 .badge { margin-inline-start: var(--sc-space-1); }` to the Components section of `app/static/css/app.css`, and run `tests/unit/test_stylesheet.py` and `tests/unit/test_frame_stylesheet.py`.

**Checkpoint**: the gallery shows the badge and the text card with it; the guidelines match; the
whole existing suite is green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the column, its migration and tests, the seeder, and the mark in `QuestionView`
(research R1, R2; data-model.md §1, §2, §4). Every story needs them.

- [ ] T008 Add the column to `app/models/question.py` per data-model.md §1:
  - `is_additional: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default=false()))`,
    importing `Boolean` and `false` from `sqlalchemy`;
  - **constraint, verbatim**: "`is_additional` | boolean | not null | default `false` (server
    default)";
  - docstring: "The mark **additional question** (milestone 12.9): seen only by teachers with **Can
    manage competitions** until a competition that holds it starts; for every other teacher the bank
    is read without these questions. Changed only through the edit form; a deleted question or one
    of a deactivated subject keeps it. A competition's copy never takes it.";
  - extend the module docstring's bullet list with one bullet on the mark.
- [ ] T009 Create the migration `migrations/versions/2026_11_<dd>_<rev>_additional_questions.py` (`down_revision = "c730fd883079"`) per data-model.md §4 and research R2 (depends on T008):
  - generate the revision id with `uv run alembic revision -m "additional questions"`, then rename
    the file to the dated pattern;
  - **upgrade**: `with op.batch_alter_table("questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True}) as batch:`
    then `batch.add_column(sa.Column("is_additional", sa.Boolean(), nullable=False, server_default=sa.false()))`;
  - **downgrade**: the same block with `batch.drop_column("is_additional")`; the docstring says it
    is lossy (every mark is dropped);
  - the module docstring explains the column, why the server default (every existing row, deleted
    ones included, becomes not additional, FR-002, so no data step), and why `table_kwargs` (keeps
    SQLite `AUTOINCREMENT` when the downgrade copies the table). It is a frozen snapshot: plain
    SQLAlchemy types, nothing imported from `app`.
- [ ] T010 [P] Extend `tests/integration/test_migrations.py` (depends on T009):
  - in `test_the_questions_table_at_head`: `columns["is_additional"]["nullable"] is False`;
  - a new test: upgrade to `c730fd883079`, insert one listed and one deleted question with plain SQL
    (as the file's milestone 11 tests do), upgrade to head, and assert both have
    `is_additional = false` and `SELECT count(*) FROM questions WHERE is_additional` is 0 (SC-004);
  - a new SQLite-only test: upgrade to head, downgrade `-1`, upgrade to head again, and `sqlite_master`
    for `questions` still holds `AUTOINCREMENT` (skip on PostgreSQL, as
    `test_sqlite_never_reuses_a_question_id` does);
  - the stairway, single-head and drift tests pass unchanged.
- [ ] T011 [P] Add the parameter to the seeder `make_question` in `tests/conftest.py` (depends on T008): the signature `make_question(engine, subject_id, text="Question?", reference_answer="Answer.", *, deleted=False, additional=False)` sets `is_additional=additional`; the docstring names it.
- [ ] T012 Add the mark to `QuestionView` in `app/services/questions.py` per contracts/services.md (depends on T008):
  - the field `is_additional: bool` with a docstring;
  - `_view` fills it;
  - nothing else changes yet. Existing tests stay green: `QuestionView` is built only by `_view`.

**Checkpoint**: the column is on both engines; the migration goes up, down and up; the whole
existing suite is green.

---

## Phase 3: User Story 1 - A teacher with the setting marks a question as additional (Priority: P1) 🎯 MVP

**Goal**: the checkbox on the add and edit form, the mark stored and cleared, the badge on the
**Questions** tab for a teacher with the setting.

**Independent Test**: as a teacher with the setting, add questions with and without the checkbox,
edit one to set and to clear the mark, send an invalid form with the checkbox checked, and check
what is stored and how the list shows each question.

- [ ] T013 [P] [US1] Add the service tests to `tests/integration/test_question_service.py` (depends on T011, T012):
  - `create_question` without `is_additional` stores false; with `is_additional=True` stores true,
    and the view says so;
  - `update_question(..., is_additional=True)` marks, `False` clears;
  - changing only the mark resets `updated_at` (the clock patched as the file already does) and logs
    "Question updated: id=…";
  - an update repeating every value changes nothing and logs nothing;
  - `update_question` on a deleted question, or on one of a deactivated subject, raises
    `QuestionNotFound`, and the stored mark (seeded `additional=True`) is unchanged (FR-005);
  - `delete_question` keeps the mark.
- [ ] T014 [US1] Change `create_question` and `update_question` in `app/services/questions.py` per contracts/services.md and research R5 (depends on T013):
  - `create_question(..., *, is_additional: bool = False)` stores it;
  - `update_question(..., *, is_additional: bool)` takes it as a **required keyword-only argument,
    no default**;
  - `changed` compares `(question.text, question.reference_answer, question.is_additional)` with
    the new three, and when anything differs all three are written and `updated_at` is reset;
  - the docstrings say so;
  - update every existing caller of `update_question` with `is_additional=False` (the question was
    not additional) in the same task:
    - `tests/integration/test_question_service.py` (every call);
    - `tests/integration/test_grade_service.py:455`;
    - `tests/integration/test_team_answer_service.py:497`;
    - `tests/integration/test_teacher_competition_entries.py:545` and `:1075`;
    - `app/routers/teacher_questions.py` (passes the parsed value; T015).
- [ ] T015 [US1] Read the checkbox in `app/routers/teacher_questions.py` per contracts/http-routes.md §The question bank (depends on T014):
  - **Parameters**: `create_question_action` and `update_question_action` gain
    `additional: str | None = Form(None)`, and `marked = bool(additional)`.
  - **On a 400**: `values = {"text": …, "reference_answer": …, "additional": marked}`.
  - **On success**: `create_question(..., is_additional=marked)` and
    `update_question(..., is_additional=marked)`.
  - **Opening the forms**: `new_question_page` sets `"additional": False`; `edit_question_page`
    sets `"additional": question.is_additional`.
  - **Docstring**: the module's "Every teacher reads the bank…" paragraph becomes "Every teacher
    reads the questions that are not additional; only a teacher with Can manage competitions sees
    the additional ones (milestone 12.9) and changes the bank."
- [ ] T016 [US1] Add the checkbox to `app/templates/pages/teacher/question_form.html` per contracts/components.md §4 (depends on T015):
  - import `checkbox_field`;
  - after the `reference_answer` field and before `form_actions`, add
    `{{ checkbox_field("additional", _("Additional question"), checked=values.additional, value="1", hint=_("Additional questions and their answers are not given to participants before a competition.")) }}`.
- [ ] T017 [US1] Show the badge on the list in `app/templates/pages/teacher/questions.html` (depends on T002, T001, T012):
  - import `additional_badge`;
  - the card becomes `text_card(_("Question %(number)d", number=q.id), id="question-" ~ q.id, badge=additional_badge() if q.is_additional else none)`.
- [ ] T018 [US1] Extract and translate the form's messages (depends on T016):
  - `scripts/translations.sh update`;
  - in `app/locale/uk/LC_MESSAGES/messages.po`:
    - "Additional question" → «Додаткове питання»;
    - "Additional questions and their answers are not given to participants before a competition."
      → «Додаткові питання та відповіді на них не надаються учасникам до змагання.»;
  - `scripts/translations.sh compile`; `tests/unit/test_catalogues.py` and
    `tests/unit/test_template_text.py` pass.
- [ ] T019 [US1] Add the route tests to `tests/integration/test_teacher_questions.py` (depends on T016–T018):
  - **The add form** (US1-1): the checkbox `additional` with value `1`, unchecked, labelled
    "Additional question", after the reference answer, with the hint linked by `aria-describedby`.
  - **Saving on add** (US1-2, US1-3): `additional=1` with `then=list` and with `then=another` stores
    true; no `additional` field, and `additional=` (empty), store false.
  - **Save and add one more** (US1-4): after `then=another` with the box checked, the form at the
    redirect is unchecked.
  - **The edit form** (US1-5): checked for a question seeded `additional=True`, unchecked for one
    that is not.
  - **Saving on edit** (US1-6): checking and saving marks; sending without the field clears.
  - **An invalid form** (US1-7), on add and on edit: an empty text with `additional=1` answers 400
    with the box checked and stores nothing; without the field, 400 with the box unchecked.
  - **The badge** (US1-8): on the list as `scene.manager`, the `h3` of an additional question reads
    "Question <id> Additional" with one `span.badge.badge-info`; an ordinary question has no badge.
  - **Deleted or deactivated subject** (US1-10): edit and save of a deleted question, and of a
    question of a deactivated subject, seeded `additional=True` and sent without the field, answer
    "Question not found" and the stored mark stays true.
  - **Ukrainian**: «Додаткове питання», the hint, and «Додаткове» on the badge.
- [ ] T020 [US1] Update the form contract in `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json` (depends on T016):
  - regenerate with `UPDATE_FORM_CONTRACT=1` for the cases `teacher-question-new`,
    `teacher-question-new-invalid`, `teacher-question-new-saved`, `teacher-question-edit` and
    `teacher-question-edit-invalid` **only**. Each gains the field `additional`; check the diff
    shows nothing else;
  - add to the docstring's list of deliberate changes: "**Milestone 12.9**: the question form's
    cases (`teacher-question-new*`, `teacher-question-edit*`) gain the checkbox `additional`,
    regenerated once with `UPDATE_FORM_CONTRACT=1` for those cases only."

**Checkpoint**: a teacher with the setting marks and unmarks questions and sees the badge; nothing
is kept back yet.

---

## Phase 4: User Story 2 - Every other teacher does not get the additional questions (Priority: P1) 🎯 MVP

**Goal**: for a teacher without the setting, the **Questions** tab is read, counted and paged
without the additional questions.

**Independent Test**: as a teacher without the setting, with Read and with Write access, open every
page of a subject that mixes additional and other questions, and of a subject with only additional
questions, and check the responses, the counts and the page navigation.

- [ ] T021 [P] [US2] Add the listing tests to `tests/integration/test_question_service.py` (depends on T011, T012):
  - **Mixed subject**: 23 listed questions, 3 of them additional (one of them the newest), one
    additional question deleted.
    - `question_page(..., 1, include_additional=False)`: `paging.total == 20`, 10 rows, none
      additional.
    - Page 2: 10 rows.
    - Page 9 clamps to page 2.
    - `include_additional=True`: `total == 23`, with the additional rows' `is_additional` true.
  - **All-additional subject**: `include_additional=False` gives `total == 0` and no rows.
- [ ] T022 [US2] Add `include_additional` to `question_page` in `app/services/questions.py` per contracts/services.md and research R3 (depends on T021):
  - the signature becomes `question_page(session, subject_id, page, *, include_additional: bool)`:
    keyword-only, **no default**;
  - when false, `col(Question.is_additional).is_(False)` is added to the `where` of both the count
    and the page statement (build the condition tuple once);
  - the docstring states the rule and FR-014 / constitution IV ("left out, never hidden");
  - update every caller in the same task:
    - `app/routers/teacher_questions.py`: `questions_page` passes
      `include_additional=_can_manage(request, session)`, computed once and reused for
      `"can_manage"`;
    - `app/routers/teacher_competition_entries.py`: `add_questions_page` passes
      `include_additional=True`, with a comment saying the setting was checked first;
    - `tests/integration/test_question_service.py` (every existing call, `include_additional=True`).
- [ ] T023 [US2] Add the route tests to `tests/integration/test_teacher_questions.py` (depends on T022, T019):
  - **Setup**: extend `Scene` with one subject "Astronomy" holding two additional questions only,
    and mark three Mathematics questions additional through `make_question(..., additional=True)`
    (add them, or flip three of `maths_ids` with a direct update). Keep the existing tests' counts
    valid, adjusting the asserted numbers where they count Mathematics.
  - **The list** (US2-1, US2-2): as `scene.reader` (Write, no setting), Mathematics shows only the
    other questions. The page navigation's "Questions 1–10 of N" counts them. The raw
    `response.text` of every page contains no additional question's text, reference answer,
    `question-<id>`, "Question <id>" or the word "Additional".
  - **Empty** (US2-3): Astronomy shows the empty state "No questions yet" with no hint and no page
    navigation.
  - **Past the end** (US2-4): `?page=99` opens the reader's last page.
  - **Read access, no link** (US2-5): a teacher with **Read** access only, and one with no linked
    institution (both `make_teacher` without `can_manage`), see the same as the reader.
  - **The manager** (US2-6): `scene.manager` sees every question, the count including the
    additional ones, each with the badge.
  - **Opening it changes nothing**: the existing `snapshot` is unchanged.

**Checkpoint**: the bank keeps the additional questions back from every teacher without the setting.

---

## Phase 5: User Story 3 - A crafted request shows nothing about additional questions (Priority: P1) 🎯 MVP

**Goal**: proof that every single-question endpoint and **Add questions** refuse a teacher without
the setting the same way for an additional question (research R4: no code change expected).

**Independent Test**: as a teacher without the setting, send every single-question request of the
bank and every request of **Add questions** for an additional, ordinary, deleted and missing
question, and compare the responses.

- [ ] T024 [P] [US3] Extend the denial tests in `tests/integration/test_teacher_questions.py` (depends on T011, T023):
  - `test_a_teacher_without_the_setting_is_refused_before_anything_is_looked_up` gains the target
    `"additional"`: an additional question of Mathematics;
  - a new test compares the response bodies of the four targets `listed`, `additional`, `missing`
    and `deleted` for each `MANAGE_ROUTES` entry: identical status (403) and identical body;
  - **US3-3**: `POST /teacher/questions` with `additional=1` by the reader answers 403 and stores
    nothing (`snapshot` unchanged).
- [ ] T025 [P] [US3] Extend `test_a_teacher_without_the_setting_is_refused_before_any_id_is_read` in `tests/integration/test_teacher_competition_entries.py` (depends on T011):
  - the target `"additional"` (a Chemistry question seeded `additional=True`) for the **Add
    questions** page and its add;
  - the response for it equals the response for `"listed"`, and nothing changes.
- [ ] T026 [US3] If T024 or T025 fails, fix the order of checks in the route it names in `app/routers/teacher_questions.py` or `app/routers/teacher_competition_entries.py`, so the setting is checked before any id is read (contracts/http-routes.md §Order of checks), and record the fix in research.md R4. Otherwise mark this task done with no change.

**Checkpoint**: MVP complete. The mark exists, is shown only to teachers with the setting, and is
kept back in the bank and on every crafted request.

---

## Phase 6: User Story 4 - A teacher with the setting chooses and reviews a mix for a competition (Priority: P2)

**Goal**: the badge on **Add questions** and on a competition's **Questions** page (managers only,
live from the bank); nothing stored in a competition follows the mark.

**Independent Test**: as a teacher with the setting, add additional and other questions to an
**Upcoming** competition, then view its **Questions** page with and without the setting in every
status, change a mark in the bank, and compare the page and the stored copies.

- [ ] T027 [P] [US4] Add the service tests to `tests/integration/test_competition_entries_service.py` (depends on T011):
  - **The mark per question**: a competition with three copied questions (one additional, one
    ordinary, one additional and then deleted from the bank).
    - `question_page(..., with_bank_mark=True)` gives `is_additional` True / False / True, and
      `deleted_from_bank` as before.
    - `with_bank_mark=False` gives `None` for each.
  - **It follows the bank**: after clearing the first question's mark in the bank (a direct update),
    `with_bank_mark=True` gives False.
  - **Nothing stored changes** (FR-023, SC-005): for a competition in each status (Upcoming,
    In progress, Finished with answers and grades, Published with `store_results_files`), set and
    clear the mark of its questions in the bank. The rows of `competition_questions`,
    `team_answers` and `competition_results_files` for it are identical before and after.
  - **The remove confirmation**: `get_competition_question` gives `is_additional is None`.
- [ ] T028 [US4] Add `with_bank_mark` to `app/services/competition_entries.py` per contracts/services.md and research R6 (depends on T027, T012):
  - `CompetitionQuestionView` gains `is_additional: bool | None`, with a docstring ("the bank's
    current mark, read only for a teacher with the setting; `None` when not read");
  - `question_page(session, competition_id, p, *, with_bank_mark: bool)`: keyword-only, **no
    default**. With it, select `CompetitionQuestion, Question.deleted_at, Question.is_additional`;
    without it, the 12.2 statement, and the view gets `None`;
  - `get_competition_question` fills `is_additional=None`;
  - update every caller in the same task:
    - `app/routers/teacher_competition_entries.py`: `competition_questions_page` computes
      `manage = can_manage(request, session)` once, passes `with_bank_mark=manage`, and uses
      `manage` in `can_change`;
    - `tests/integration/test_competition_entries_service.py` (every existing call,
      `with_bank_mark=False` unless the test reads the mark).
- [ ] T029 [US4] Show the badge in `app/templates/pages/teacher/competition_questions.html` and `app/templates/pages/teacher/competition_questions_add.html` (depends on T028, T022, T001, T002):
  - import `additional_badge` in both;
  - `competition_questions.html`: the card gets `badge=additional_badge() if q.is_additional else none`.
    `None` and `False` show nothing; "Deleted from the question bank" stays as it is;
  - `competition_questions_add.html`: the card gets `badge=additional_badge() if q.is_additional else none`;
  - update each template's top comment with one line on the badge (milestone 12.9).
- [ ] T030 [US4] Add the route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T029):
  - **Add questions** (US4-1, US4-2): as `scene.olena` on the **Upcoming** competition, the page
    lists the additional questions with the badge, each with **Add**. Adding one copies it, with
    the notice "Question <id> was added to “…”". Afterwards it shows "Already in this competition"
    and still the badge.
  - **The competition's Questions page** (US4-3, US4-4):
    - as `scene.olena`, the badge is shown beside each additional question's number in each status
      (Upcoming, In progress, Finished, Published, Cancelled, using `scene.clock` and the existing
      seeders), and for a finished competition of a deactivated subject;
    - as `scene.mykola`, the same questions, and the raw `response.text` contains no
      `badge-info` badge reading "Additional" and no word "Additional".
  - **Badge and note together** (US4-5): a copied additional question then deleted from the bank
    shows the badge and "Deleted from the question bank".
  - **It follows the bank** (US4-6): clearing the mark through the edit form (as Olena) removes the
    badge on the next load; the copy's text is unchanged.
  - **Nowhere else** (US4-7): the remove confirmation of an additional question's copy shows no
    badge.
- [ ] T031 [P] [US4] Add the "never shown" tests (US4-7, FR-026) to `tests/integration/test_teacher_team_answers.py` and `tests/integration/test_teacher_grades.py` for a Finished competition holding an additional question, with one team's answers saved and graded and the teacher linked to the team's institution:
  - in `tests/integration/test_teacher_team_answers.py`: the read-only answer sheet;
  - in `tests/integration/test_teacher_grades.py`: the **Grades** page and the grading sheet, as a
    teacher with the setting;
  - both responses contain no "Additional" and no `badge-info` badge.

**Checkpoint**: a teacher with the setting chooses a mix and reviews it; competitions never change
with the mark.

---

## Phase 7: User Story 5 - Changing the setting changes what a teacher sees (Priority: P2)

**Goal**: the setting is read on every request, both ways.

**Independent Test**: give a teacher the setting and take it away between two requests, and check
the **Questions** tab and a competition's **Questions** page after each change.

- [ ] T032 [P] [US5] Add the setting tests to `tests/integration/test_teacher_questions.py` (depends on T023):
  - add a helper `give_setting(engine, email)` beside `remove_setting`, using `update_teacher(...,
    can_manage_competitions=True)` in the same way, and generalise `remove_setting` to take the email
    if needed;
  - **Given** (US5-1): `scene.reader`'s list counts only the other questions; after
    `give_setting(READER)` the next request lists every question with the badges;
  - **Taken away** (US5-2): `scene.manager` opens an edit form; after `remove_setting(MANAGER)` the
    next list counts only the other questions, and sending the edit form answers 403 and changes
    nothing.
- [ ] T033 [P] [US5] Add the setting test to `tests/integration/test_teacher_competition_entries.py` (depends on T030): with a competition holding an additional question, Mykola's **Questions** page has no badge; after giving Mykola the setting, the next load shows it; after taking it away, it is gone again.

**Checkpoint**: every story works on its own and together.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: the cross-cutting checks, the documents, the whole suite on both engines, and the
walk-through.

- [ ] T034 [P] Run `tests/integration/test_routes.py`, `tests/integration/test_page_patterns.py`, `tests/integration/test_cross_site.py` and `tests/unit/test_ukrainian_wording.py` (depends on T029). No route was added, so they need no new entry. If `test_page_patterns.py` sweeps the question pages, add a case for the list with an additional question as a teacher with the setting, so the badge inside the `h3` passes the heading checks.
- [ ] T035 [P] Update `README.md` per research R10 (depends on T029). In the **Questions** paragraph:
  - replace "is the shared question bank, one subject at a time. Every teacher can read it; it is not
    limited to their institutions." with: the question bank, one subject at a time, not limited to
    institutions; every teacher reads its questions that are not additional;
  - add a bullet **Additional questions**: the checkbox, the badge, who sees them (only **Can manage
    competitions**, also on **Add questions** and a competition's **Questions** page), and that
    other teachers get the bank without them, counted and paged without them;
  - in the **Competitions** paragraph, one line: every teacher still reads a competition's
    **Questions** page until milestone 12.10.
- [ ] T036 [P] Finish `docs/requirements/ui-guidelines.md` against the pages as built (depends on T029, T007): the text card example shows the badge as `questions.html` renders it.
- [ ] T037 Run ruff and the whole `tests/` suite on both engines (depends on everything above):
  - `uv run ruff check && uv run ruff format --check`;
  - `TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest`;
  - fix any failure.
- [ ] T038 Walk through [quickstart.md](./quickstart.md) §2–§4 by hand:
  - the migration up, down and up on a copy of a 12.8 database;
  - the full flow as Olena, Petro and Taras, including Ukrainian;
  - 360 px and both themes, with screenshots from the ad hoc headless Playwright recipe;
  - fix what it finds.
- [ ] T039 On delivery (after the PR's merge), in `docs/requirements/milestones.md` (FR-034):
  - move 12.9 to **Delivered** with the spec link and a one-paragraph summary in the style of
    12.8's, saying who sees the additional questions;
  - in the milestone 11 summary, replace "where every teacher browses the shared question bank by
    subject" with wording that every teacher browses the question bank by subject and that its
    additional questions are seen only with **Can manage competitions** (from milestone 12.9);
  - remove the full 12.9 entry from **Upcoming**.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup, US6)**: no dependency. T001, T002 together; then T003 → T006, T007; T001 → T004
  → T005.
- **Phase 2 (Foundational)**: independent of Phase 1. T008 → T009 → T010; T008 → T011, T012.
- **US1 (Phase 3)**: after Phase 2; T017 also needs T001, T002. T013 → T014 → T015 → T016 → T018
  → T019; T016 → T020.
- **US2 (Phase 4)**: after Phase 2. T021 → T022 → T023 (T023 after T019, since both extend the same
  module and `Scene`).
- **US3 (Phase 5)**: T024 after T023; T025 after T011; T026 after both.
- **US4 (Phase 6)**: T027 after T011; T028 after T027 and T012; T029 after T028, T022, T001, T002;
  T030 after T029; T031 after T029.
- **US5 (Phase 7)**: T032 after T023; T033 after T030.
- **Polish (Phase 8)**: after the stories it covers. T039 last, after merge.

### Within each story

- Service tests first, and they fail; then the service change with every caller updated; then the
  routes and templates; then the messages; then the route tests.
- A signature change and its callers are one task, so the suite is green after every task.

### Parallel opportunities

- **Phase 1 and Phase 2** run side by side (templates vs. model and migration).
- **Phase 1**: T001 and T002 together; T005 and T006 together.
- **Phase 2**: T010, T011 and T012 together after T008 / T009.
- **After Phase 2**: T013 (US1), T021 (US2) and T027 (US4) are service tests in three different
  modules and can be written together; T025 (US3, another module) too.
- **Polish**: T034, T035 and T036 together.

## Parallel Example: after Phase 2

```text
Developer A: T013 → T014 → T015 → T016 → T017 → T018 → T019 → T020   (US1: the mark)
Developer B: T021 → T022                                              (US2: the service filter)
Developer C: T027 → T028                                              (US4: the bank mark on competitions)
Then:        T023 (US2 routes), T024–T026 (US3), T029–T031 (US4 pages), T032–T033 (US5)
```

## Implementation Strategy

### MVP first (Phase 1 + Phase 2 + US1 + US2 + US3)

1. The components (Phase 1) and the column with its migration (Phase 2).
2. US1: mark and unmark questions; the badge for teachers with the setting.
3. US2: every other teacher gets the bank without them.
4. US3: prove that crafted requests show nothing.
5. **Stop and validate**: as Olena and as Petro, compare the **Questions** tab and the page source.

### Incremental delivery

1. US4: the mix on **Add questions** and the competition's **Questions** page; competitions never
   change.
2. US5: the setting both ways.
3. Polish, the whole suite on both engines, the quickstart walk-through.
4. Merge; T039 on delivery.
