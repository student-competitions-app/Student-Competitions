---

description: "Task list for milestone 12.4: finishing a competition and grading its answers by hand (teacher)"
---

# Tasks: Finishing a Competition and Grading Its Answers by Hand (Teacher) (Milestone 12.4)

**Input**: Design documents from `/specs/012.4-finish-and-grade/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-051 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R15.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`. The two-session concurrency tests run on PostgreSQL only (skip on SQLite),
  with the `threading.Barrier` pattern of `tests/integration/test_competition_entries_service.py`
  and `tests/integration/test_team_answer_service.py`.
- **Seeders**: `make_teacher(engine, settings, email=..., institutions={}, can_manage=True | False)`,
  `make_subject`, `make_question`, `make_institution(..., region="Kyiv", region_active=...)`,
  `make_class`, `make_team(engine, institution_id, name, deleted=...)`, `make_member`,
  `make_competition(engine, subject_id, name, starts_at=..., cancelled=..., stopped=...)`,
  `add_competition_question`, `add_competition_team`, `save_team_answer`, and the new
  `grade_answer` (T012).
- **The clock**: tests control "now" with
  `monkeypatch.setattr("app.services.competitions.utc_now", lambda: fixed)`. `app/services/grades.py`
  reads the clock **through that module attribute** (`competitions.utc_now()`), as
  `team_answers.py` does, so the same patch moves it. No test sleeps.
- **Finished competitions** for grading tests are made either through the new finish (US1 tests) or
  directly with `make_competition(..., stopped=True)`, then `add_competition_question`,
  `add_competition_team`, `save_team_answer` and `grade_answer`.

**Organization**: tasks are grouped by user story (US1–US14 in spec.md).

- **Phase 1 is the three new patterns and the guidelines**, because the constitution puts the
  library, the gallery and the guidelines before any page (FR-048). It delivers **US14**.
- **Phase 2** is the grade column and its migration, the grade cleaning rule, the `grades` service
  skeleton with `grade_counts`, the shared address and form-field helpers, the grades router
  skeleton and the seeder.
- **US1** (finishing) then **US3** (the Grades page) and **US4** (the grading sheet) are the MVP:
  a competition can be finished and its answers graded. **US2**, **US5**, **US6** complete those
  flows (refusals and races, invalid grades, the filter). **US7** and **US8** change the 12.3
  Answers pages (Read access, read-only after finishing). **US9** pins the whole menu. **US10**
  (grading refusals), **US11** (access) and **US13** (deactivated subjects) are enforced inside every
  route and service as they are built (the rules below); their phases add the cross-cutting tests.
  **US12** proves the last save wins under concurrency.

**Reference implementation**: milestones 12.1–12.3 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**: `app/services/competitions.py` (`cancel_competition` step by step: `_require_manage`,
  `lock_competition`, `status_of` with a fresh clock, `_listed` before and after, the conditional
  `update(...)` with `rowcount`, `_reread_status`, `landing`, the log line; `_refuse`; the module's
  "Contract for later milestones"), `app/services/team_answers.py` (`save_answers`'s lock order and
  refusals that roll back first, `_stored_answers(refresh=True)`, `_question_copies` (moved to
  `competition_entries.question_copies` in T013),
  `answer_team_page`, `answer_sheet`, `count_answered`), `app/services/competition_entries.py`
  (`team_entries`, `group_by_region`, `RegionGroup`, `TeamRow.is_deleted`), `app/services/teams.py`
  (`count_active_members`), `app/services/teacher_access.py` (`can_manage_competitions(lock=)`,
  `reach_institution(write=, lock=)`, `NotReachable`, `WriteRequired`), `app/services/paging.py`
  (`parse_page`, `Paging.build`), `app/schemas/answer.py` (a pure cleaning module).
- **Routers**: `app/routers/teacher_competitions.py` (the cancel pair `cancel_competition_page` /
  `cancel_competition_action`, `CANCEL_REFUSALS`, `_cancel_refused`, `_refused`, `NOTICES`,
  `_notice_token`, `require_manage`, `list_path`, `parse_id`, `not_found`, `redirect`),
  `app/routers/teacher_competition_entries.py` (`ListContext`, `address`, `find_context`,
  `render_competition_page`, `page_prefix`), `app/routers/teacher_team_answers.py` (`_open`,
  `answers_refused`, `answers_path`, `sheet_path`, `_back_page`, the sealed notice,
  `answer_fields`, `_parse_answers`, `_render_sheet`).
- **Templates**: `pages/teacher/competition_cancel.html`, `competition_refused.html`,
  `competition_teams.html` (region groups, the "(deleted)" row note), `competition_answers.html`,
  `team_answer_sheet.html`; components `confirmation.html`, `answer_sheet.html`, `card.html`
  (`text_card`, `text_box`), `form.html` (`field`, `error_summary`, `form_actions`),
  `pagination.html`, `group.html`, `table.html`, `menu.html`, `details.html`, `feedback.html`; the
  gallery `app/templates/pages/admin/components.html` with `app/routers/admin_components.py`
  (`_samples`); `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Migration**: `migrations/versions/2026_11_13_b709653d1111_team_answers.py` (frozen snapshot,
  `op.f` names); earlier `batch_alter_table` uses in `2026_10_02_656ef4aab46f_drop_legacy_user_role.py`.
- **Tests**: `tests/integration/test_teacher_team_answers.py` (its `Scene`, `actions(...)` and row
  parsers), `test_team_answer_service.py` (the clock fixture, the PostgreSQL races),
  `test_teacher_competitions.py` (the menu and cancel assertions, the landing cases),
  `test_competition_service.py`, `test_routes.py`, `test_form_contract.py` with
  `form_contract.json`, `test_page_patterns.py`, `test_component_gallery.py`, `test_migrations.py`,
  `tests/unit/test_answer_schemas.py`, `tests/unit/test_templates.py`, `tests/html.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks, finishing and grading** (FR-043): role (`@allow_roles(Role.TEACHER)`, 403
  before any id is read) → the setting (`require_manage(request, session)`, first statement of the
  handler, 403 before any value is parsed, also for unknown ids) → the subject and the competition
  (404) → the status (409 refusal) → on the grading sheet and save, the team (404 "Team not found")
  and the named questions (404 "Question not found") → on the save, the grades (400) → the service
  write, which repeats every check under lock and raises the same outcomes.
- **Order of checks, Answers pages** (FR-041): role → subject and competition → status (**Upcoming**,
  **Cancelled** → 12.3 refusal; **In progress** and **Finished** open the pages; a save on
  **Finished** → 12.3 refusal) → team → access (unlinked → 403; Read → read-only sheet, save 403;
  Write → the answer sheet while **In progress**). **No setting check** on the Answers pages.
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON. Ids through `parse_id`, pages through `parse_page`, the
  filter through `grades.parse_grade_filter` (`"ungraded"` → **Ungraded only**, anything else →
  **All teams**).
- **Addresses**: `subject`, `status`, `page` keep their 12.1 meaning and are carried everywhere;
  `p` is the Grades page's page; `show=ungraded` the filter (left out for **All teams**); `back` the
  Grades page's page the grading sheet returns to; `notice` the sealed notice. Every address is
  built by `list_path`, `grades_path`, `grading_sheet_path`, `answers_path` or `sheet_path` from
  looked-up ids and parsed values only.
- **Redirects**: every change is a `POST` through the existing cross-site check, answering `303`, so
  a reload never repeats it (FR-045, SC-010).
- **Notices** travel sealed, holding ids and the outcome only; the text is built when the page is
  shown (research R11).
- **Logging**: services log ids and counts only, exactly: `Competition finished: id=%d` and
  `Grades saved: competition=%d team=%d graded=%d changed=%d`. A refusal logs nothing. No email,
  person's name, competition, team or institution name, question text, answer text or grade value
  of a named team ever reaches a log line or an address (FR-045).
- **Components first**: the three patterns are in the library, their CSS in the Components section
  of `app/static/css/app.css` (tokens only, no inline style, no literal colour or pixel length, no
  new token), the gallery and `ui-guidelines.md` **before** a page uses them (FR-048).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US14)

---

## Phase 1: Setup (Components and documents first)

**Purpose**: the non-destructive confirmation, the grading sheet with its read-only variant, the
filter links, the gallery and the guidelines with the changes of FR-047 (research R13,
contracts/components.md §1–§5). Nothing here touches the database. Delivers **US14**.

- [ ] T001 Add the `kind` argument to `confirmation` in `app/templates/components/confirmation.html` per contracts/components.md §1: signature `confirmation(question, consequence, action, verb, cancel_href, hidden={}, back_label="Cancel", kind="destructive")` (new argument last, so every existing call is unchanged); `kind` must be `"destructive"` or `"primary"`, anything else is `template_error("confirmation: kind must be destructive or primary")`; pass it to `post_button(action, verb, kind=kind, hidden=hidden)`. With the default the markup is byte-for-byte the current one. Rewrite the header comment: every action that cannot be undone goes through a confirmation page; its button is destructive when the action removes, hides or calls off something (**Delete**, **Deactivate**, **Withdraw consent**, **Cancel competition**), primary when it is the normal next step of the work (**Finish competition**); the link back says what is kept whenever the verb ends something (**Keep competition**, **Keep in progress**).
- [ ] T002 Create `app/templates/components/grading_sheet.html` per contracts/components.md §2 and research R13:
  - a header comment in the style of `answer_sheet.html`'s (the answer sheet's counterpart; always shows the reference answer; the read-only variant never does; items' keys; the page renders the `error_summary` and its own empty state);
  - `grading_sheet(items, action, hidden, submit_label="Save grades")`: an empty `items` is `template_error("grading_sheet: at least one question is required")`; `<ol class="answer-sheet">` with, per item, `<li>` holding `{% call text_card("Question " ~ item.number) %}` with `text_box("Question", item.text)`, `text_box("Reference answer", item.reference_answer)`, then, when `item.answer is not none`, `text_box("Answer to question " ~ item.number, item.answer)` and `field(item.field_id, "Grade for question " ~ item.number, value=item.value, error=item.error, hint="A whole number from 0 to 10.", placeholder="Not graded", attrs={"inputmode": "numeric", "autocomplete": "off"})` (`type="text"`; no `pattern`, `maxlength`, `min`, `max`), else `<p class="grade-line">Not answered</p>` and no field; when at least one item is answered the `<ol>` is inside `<form method="post" action="{{ action }}">` with one `<input type="hidden">` per `hidden` item and `form_actions(submit_label)` after the list (one primary button, no **Cancel**); when none is answered, no form and no button;
  - `answers_read_only(items, grades=True)`: the same `<ol class="answer-sheet">` of text cards with `text_box("Question", item.text)` and either `text_box("Answer to question " ~ item.number, item.answer)` or `<p class="grade-line">Not answered</p>`; with `grades`, under each answered question `<p class="grade-line">Grade: {{ item.grade }} of 10</p>` or `<p class="grade-line">Not graded yet</p>`; never a reference answer, no form, no field, no button; an empty `items` is a template error;
  - CSS in the Components section of `app/static/css/app.css`, tokens only: `.grade-line` (the body text colour, the spacing of `.text-box`), and the grade `input` inside `.answer-sheet` at the width of a short field on wide screens and `width: 100%` below 768 px; long texts already wrap through `.text-box`.
- [ ] T003 Create `app/templates/components/filter.html` with `filter_links(links, label)` per contracts/components.md §3: `links` is a list of `(text, href, current)`; exactly one `current`, else `template_error("filter_links: exactly one link must be current")`; markup `<nav class="filter-links" aria-label="{{ label }}"><ul>` with one `<li><a href="…">text</a></li>` per link, the current one with `aria-current="true"` (never `"page"`). A header comment: each link is a filter of the list below, following one goes to page 1, `aria-current="true"` because the link on page 3 of a filter leads to page 1 and the page navigation already marks the current page; no JavaScript, no **Show** button. CSS in `app/static/css/app.css`: `.filter-links ul` a horizontal row with the page navigation's gap and no bullets; extend the existing `nav.pagination li a[aria-current="page"]` rule's selector list with `nav.filter-links li a[aria-current="true"]`, so both share one look in both themes.
- [ ] T004 Add the gallery entries (depends on T001–T003):
  - `app/routers/admin_components.py` (`_samples`): a grading-sheet sample of three items (question 1 answered with a two-line answer and value "7"; question 2 not answered; question 3 answered with value "11" and the error "Enter a whole number from 0 to 10.") with the matching `errors` / `order` for an `error_summary`; a read-only sample of the same questions with grades (7, `None`) for `grades=True`; the filter links `[("All teams", "#filter-links", True), ("Ungraded only", "#filter-links", False)]`;
  - `app/templates/pages/admin/components.html`: in `#confirmations`, a second sample `confirmation("Finish competition “Spring round” of Chemistry, started 14 March 2027, 10:00?", "The competition will be marked Finished. …", "#", "Finish competition", "#confirmations", back_label="Keep in progress", kind="primary")`; a new `<section id="grading-sheet" aria-labelledby="grading-sheet-heading">` after `#answer-sheet` with the `error_summary` above the `grading_sheet`, then `answers_read_only` with grades and again without (`grades=False`); a new `<section id="filter-links" aria-labelledby="filter-links-heading">` before `#pagination`; in `#actions-menu`, the full example menu becomes **Edit**, **Questions**, **Teams**, **Answers**, **Grades**, **Finish competition** (not destructive), **Cancel competition**; add the new sections to the gallery's table of contents if it has one.
- [ ] T005 [P] Update `docs/requirements/ui-guidelines.md` per contracts/components.md §1, §2, §3, §5 and FR-047 (depends on T001–T003's markup being settled):
  - §5 **Confirmations**: the `kind` argument; replace "Every destructive action goes through a confirmation page." with the rule of contracts/components.md §1; the link back says what is kept whenever the verb ends something (**Cancel competition** / **Keep competition**, **Finish competition** / **Keep in progress**);
  - §3 **Forgiving**: the bullet "Every destructive action asks for confirmation…" becomes "Every action that cannot be undone asks for confirmation on its own page, names the item and says what will happen.";
  - §6 **Buttons**: the **destructive** row reads "actions with a high impact that cannot be reverted and that the person may regret: they remove, hide or call off something (**Delete**, **Remove**, **Deactivate**, **Withdraw consent**, **Cancel competition**)", and a note that an action that cannot be undone but is the normal next step of the work (**Finish competition**) is primary;
  - §5 new subsections "Grading sheet (`components/grading_sheet.html`)" after "Answer sheet" and "Filter links (`components/filter.html`)" before "Page navigation", each with when to use it, its wording ("Reference answer", "Answer to question <n>", "Grade for question <n>", the hint, "Not graded", "Not answered", "Grade: 7 of 10", "Not graded yet"), the phone behaviour and its gallery link (`/admin/components#grading-sheet`, `#filter-links`);
  - §5 **Actions menu**: the Competitions entries in the order **Edit**, **Questions**, **Teams**, **Answers**, **Grades**, **Finish competition**, **Cancel competition**, and the example template showing **Answers** on in progress and finished, **Grades**, and **Finish competition** without `destructive=True`;
  - §7 **Wording patterns**: **Confirmations** — "The consequence says plainly what will happen in one to three short sentences, the first saying what happens to the item." replaces "The consequence is one plain sentence"; **Row notes** — remove "Read access" from the examples.
- [ ] T006 [P] Extend the component tests (depends on T004): `tests/integration/test_component_gallery.py` — `#confirmations` has a second confirmation whose submit is primary (not the destructive class) with the link **Keep in progress**; `#grading-sheet` holds a `form[method=post]` with an `ol.answer-sheet` of three text cards headed "Question 1"…"Question 3", each with "Reference answer"; questions 1 and 3 have an `input[type=text][inputmode=numeric]` labelled "Grade for question <n>" (`label[for]` equals the id) with the hint and `placeholder="Not graded"`; question 2 shows "Not answered" and no input; question 3's input has `aria-invalid="true"` and its message, linked from the `error_summary`; one primary submit "Save grades"; the read-only samples have no form, no input, no "Reference answer", and show "Grade: 7 of 10" and "Not graded yet" only in the `grades=True` sample; `#filter-links` has a `nav.filter-links` with exactly one `a[aria-current="true"]` and no `aria-current="page"`; `#actions-menu` lists the seven entries in order with **Finish competition** not destructive. `tests/unit/test_templates.py` — `confirmation` without `kind` renders byte-for-byte as before, with `kind="primary"` renders a primary button, with another value is a template error; `grading_sheet` with no answered item renders no `form` and no button; `grading_sheet` and `answers_read_only` with no items are template errors; `filter_links` with zero or two current links is a template error. `tests/unit/test_stylesheet.py` stays green.

**Checkpoint**: the three patterns are in the library, the gallery and the guidelines; every
existing page renders as before. US14 is done.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the grade column and its migration, the grade rule, the `grades` service skeleton with
`grade_counts`, the shared helpers, the grades router skeleton and the seeder (data-model.md,
research R2, R4, R5, R8, R9, R11, contracts/services.md, contracts/http-routes.md §Order of checks,
§Address parameters).

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end.

- [ ] T007 Create `app/schemas/grade.py` per contracts/services.md §`app/schemas/grade.py` and research R4: a module docstring (pure, no database; a grade is an integer from 0 to 10 written with ASCII digits only, trimmed of the whitespace around it, leading zeros ignored, empty means not graded; why a text field and not a number field); `GRADE_MAX = 10`; `GRADE_ERROR = "Enter a whole number from 0 to 10."`; `class InvalidGrade(ValueError)` with `message: str` (always `GRADE_ERROR`); `clean_grade(raw: str) -> int | None`: `value = raw.strip()`; `""` → `None`; not `value.isascii() and value.isdigit()` → `InvalidGrade`; `significant = value.lstrip("0") or "0"` (leading zeros ignored, however many; "000" is 0); `len(significant) <= 2 and int(significant) <= GRADE_MAX` → `int(significant)`; else `InvalidGrade` (the length check comes before `int()`, so a very long digit string never reaches the integer parser).
- [ ] T008 [P] Create `tests/unit/test_grade_schemas.py` (depends on T007): "0" → 0, "10" → 10, "7" → 7, " 7 " → 7, "\t7\n" → 7, "07" → 7, "0007" → 7, "010" → 10, "0010" → 10, "000" → 0, "0" * 5000 + "7" → 7, "" → `None`, "   " → `None`; each of "7.5", "-1", "11", "011", "seven", "+7", "7.0", "1e1", "٧" (Arabic-Indic seven), "７" (full-width seven), "1000000", "9" * 5000, "7 5", "7\x00" raises `InvalidGrade` with exactly "Enter a whole number from 0 to 10.".
- [ ] T009 Add the grade to `app/models/competition.py` per data-model.md §1–§2: `TeamAnswer.grade: int | None = Field(default=None, sa_type=SmallInteger, nullable=True)` with the docstring "`NULL`: not graded. A whole number 0–10 (`grade_range`), written only by `app.services.grades.save_grades`, only while the competition is Finished. Who graded it, or when, is not stored."; add `CheckConstraint("grade IS NULL OR (grade >= 0 AND grade <= 10)", name="grade_range")` to `__table_args__` (the convention names it `ck_team_answers_grade_range`); `TeamAnswer`'s class docstring names the new writer and that `save_answers` writes `text` only; `Competition`'s and `stopped_at`'s docstrings say `stopped_at` is written once by `competitions.finish_competition` (milestone 12.4), dropping "a later 12.x milestone; in milestone 12.1 only tests set it"; the module docstring cites specs/012.4-finish-and-grade/data-model.md §1.
- [ ] T010 Create the migration `migrations/versions/2026_11_<dd>_<rev>_answer_grades.py` (`down_revision = "b709653d1111"`) per data-model.md §6 (depends on T009): generate the id with `uv run alembic revision -m "answer grades"` and write the operations by hand as a frozen snapshot (plain SQLAlchemy types, nothing imported from `app`); upgrade: `with op.batch_alter_table("team_answers") as batch:` `batch.add_column(sa.Column("grade", sa.SmallInteger(), nullable=True))` and `batch.create_check_constraint(op.f("ck_team_answers_grade_range"), "grade IS NULL OR (grade >= 0 AND grade <= 10)")`; no data step; downgrade drops the constraint and the column in a batch. A module docstring in the style of `b709653d1111`'s. Run `uv run alembic upgrade head` locally.
- [ ] T011 [P] Extend `tests/integration/test_migrations.py` (depends on T010): the head is the new revision; the stairway and drift checks cover it on both engines; after upgrade an existing answer row (inserted at `b709653d1111`) is kept with `grade` `NULL`; a `grade` of 0 and 10 is accepted, `-1` and `11` fail with an integrity error; downgrade to `b709653d1111` drops the column and keeps every answer's text.
- [ ] T012 [P] Add the seeder to `tests/conftest.py` in a new "Milestone 12.4: grades" section after the 12.3 helpers (depends on T009): `grade_answer(engine, competition_id, team_id, competition_question_id, grade: int | None) -> None` sets `grade` on the existing `TeamAnswer` row (an assertion if the row does not exist). Docstring: "**Test-only**: it skips the setting, status, team and question checks that `test_grade_service.py` covers."
- [ ] T013 Create `app/services/grades.py` with its skeleton per contracts/services.md §`grades` (Types, Errors, `grade_counts`) and research R3, R5 (depends on T007, T009): a module docstring in the style of `team_answers.py`'s (who grades: a teacher with **Can manage competitions**, every team whatever their links; only on a **Finished** competition; the clock is `competitions.utc_now`; the write order of research R3 — setting `FOR SHARE` → competition `FOR SHARE` → status → team and its link `FOR UPDATE` → named questions answered by the team → grades → change; every refusal rolls back first; the one log line; the "Contract for later milestones" of contracts/services.md for milestones 14 and 15); `from app.services import competitions`; **no import from `app.services.team_answers`** (that module imports `grades.grade_counts` in T043, so the dependency runs one way only: `team_answers` → `grades` → `competition_entries`); move the private `team_answers._question_copies` to `app/services/competition_entries.py` as the public `question_copies(session, competition_id) -> list[CompetitionQuestion]` (same query, the order of adding by `CompetitionQuestion.id`, a docstring naming both callers) and update `team_answers.py` to import it from there (no behaviour change; the 12.3 suite stays green); the frozen dataclasses `GradeCount(answered, graded, score)` with the property `fully_graded` (`graded == answered`), `GradeTeamRow`, `GradeTeamPage(groups, paging, teams_total, teams_graded)`, `GradingQuestion`, `GradingSheet`, `GradeSaveResult` exactly as contracts/services.md §Types; `class GradeFilter(StrEnum)` with `ALL = "all"` and `UNGRADED = "ungraded"`, and `parse_grade_filter(raw: str | None) -> GradeFilter` (`"ungraded"` exactly → `UNGRADED`, anything else → `ALL`); the errors `GradingClosed(status: CompetitionStatus)`, `GradedTeamNotFound(LookupError)` (docstring: "Unknown, or not in the competition. Unlike `team_answers.TeamNotFound`, a deleted team, or one of a deactivated institution or region, is found: a finished competition keeps every team, and every one is graded."), `GradedQuestionNotFound(LookupError)` (docstring: "Not one of the competition's questions, or one the team did not answer. Unlike `team_answers.QuestionNotFound`, an unanswered question is refused: it has no answer to grade."), `InvalidGrades(errors: dict[int, str])` (by copy id, in question order); `grade_counts(session, competition_id) -> dict[int, GradeCount]`: one `select(TeamAnswer.team_id, func.count(), func.count(TeamAnswer.grade), func.coalesce(func.sum(TeamAnswer.grade), 0)).where(TeamAnswer.competition_id == competition_id).group_by(TeamAnswer.team_id)`; a team with no row is absent (read as `GradeCount(0, 0, 0)` through a small `count_of(counts, team_id)` helper).
- [ ] T014 [P] Create `tests/integration/test_grade_service.py` with the `grade_counts` and `parse_grade_filter` tests (depends on T012, T013): a team with 4 answers, 3 graded 5, 7, 5 → `GradeCount(4, 3, 17)`, not fully graded; a team with 2 answers both graded 0 → `(2, 2, 0)`, fully graded; a team with no answers → absent, read as `(0, 0, 0)`, fully graded; another competition's answers are not counted; `parse_grade_filter` maps `"ungraded"` to `UNGRADED` and `None`, `""`, `"all"`, `"Ungraded"`, `"x"` to `ALL`.
- [ ] T015 [P] Add the `show` argument to `address` in `app/routers/teacher_competition_entries.py` per contracts/http-routes.md §Address parameters: `address(path, context, *, back=1, region=None, p=1, show: str | None = None, notice=None, anchor=None)`, appending `&show=<value>` after `region` and before `p` when given; every existing caller is unchanged. Update the module docstring's "Shared with" paragraph to name `teacher_grades` (milestone 12.4) as an importer.
- [ ] T016 [P] Generalise the form-field reading in `app/routers/teacher_team_answers.py` per research R9 (no behaviour change): `prefixed_fields(prefix: str)` returns an async dependency yielding every `(name, value)` pair of the form whose name starts with `prefix`, in the order sent, repeated names included (the body of today's `answer_fields`); `AnswerFields = Annotated[list[tuple[str, str]], Depends(prefixed_fields(ANSWER_FIELD_PREFIX))]`; `_parse_answers` becomes the public `parse_prefixed(fields, prefix) -> dict[int, str] | None` (a suffix that is not an id via `parse_id`, or an id given twice → `None`); `_back_page` becomes the public `back_page`. Update callers; the 12.3 suite stays green unchanged.
- [ ] T017 Create `app/routers/teacher_grades.py` with its skeleton and include it in `app/main.py` next to `teacher_team_answers.router` (depends on T013, T015, T016), per contracts/http-routes.md §Order of checks, §Address parameters, §Refusals and research R8, R11:
  - module docstring in the style of `teacher_team_answers.py`'s (the Grades page, the grading sheet and its save; only a teacher with **Can manage competitions**, every team whatever their links; the order of checks with the setting first; the addresses `subject`/`status`/`page`/`p`/`show`/`back`/`notice`; the sealed notice; nothing logged here);
  - `router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")`; pages render through `render_competition_page`;
  - `TEAM_NOT_FOUND` and `QUESTION_NOT_FOUND` imported from `teacher_team_answers` (same texts); `GRADE_FIELD_PREFIX = "grade-"`; `GradeFields = Annotated[..., Depends(prefixed_fields(GRADE_FIELD_PREFIX))]`;
  - `grades_path(competition_id, context, show: GradeFilter, p=1, anchor=None) -> str` → `/teacher/competitions/17/grades?subject=3&status=finished&page=2&show=ungraded&p=2#team-31` (`show` left out for `ALL`, `p` for 1, anchor `team-<id>`) and `grading_sheet_path(competition_id, team_id, context, show, back, notice=None)` → `/teacher/competitions/17/grades/31?subject=3&show=ungraded&back=2&notice=…`, both through `address`;
  - the notice: `GRADES_NOTICE_PURPOSE = "grades-notice"`, `GRADES_NOTICE_TTL = timedelta(minutes=10)`, `grades_notice_token(request, competition_id, team_id)` sealing `{"competition": id, "team": id, "outcome": "saved"}`, `read_grades_notice(request, token, competition_id, team_id, team_name) -> str | None` → "Grades of “<team>” were saved", `None` for a missing, tampered, expired, other competition's or team's, or malformed token;
  - `GRADE_REFUSALS` with the three reasons of contracts/http-routes.md §Refusals verbatim (**Upcoming** "“{name}” has not started yet, so its answers cannot be graded.", **In progress** "“{name}” is still in progress, so its answers cannot be graded until it is finished.", **Cancelled** "“{name}” has been cancelled, so its answers cannot be graded.") and `grades_refused(request, competition, status, context)` → 409 `pages/teacher/competition_refused.html` with `question = "Grade answers of “<name>”?"`, `back = context.back_to_list(competition.id)`, `back_text = "Back to competitions"`, `back_link_text = "Back to the competitions"`;
  - a private `_open(request, session, competition_id, subject, status, page)`: `require_manage(request, session)` first (raises 403), then `find_context(...)` (its not-found response passed through), then `competition.status is not FINISHED` → `grades_refused(...)`; else `(context, competition)`.

**Checkpoint**: the column exists on both engines, the grade rule, `grade_counts` and the shared
helpers are in place, the skeletons import cleanly, and the whole existing suite is green.

---

## Phase 3: User Story 1 - A teacher with the setting finishes a competition (Priority: P1) 🎯 MVP

**Goal**: **Finish competition** in the menu of an **In progress** competition, a primary
confirmation, and finishing with the notice and the landing of the status filter.

**Independent Test**: as a teacher with the setting, finish an **In progress** competition under
each status filter and check the confirmation, **Keep in progress**, the notice, the landing, the
new status and menu, and that it can no longer be cancelled or edited.

- [ ] T018 [P] [US1] Add the `finish_competition` service tests to `tests/integration/test_competition_service.py` (depends on T017): an **In progress** competition is finished with `stopped_at` = the patched now and `status_of` → **Finished**; only `stopped_at` changes (`updated_at`, name, start unchanged); the returned `Landing` for the filter `None` and **Finished** is the competition itself, for **In progress** the row that took its place, the row before when it was last, the previous page's last row when its page empties (11 in progress, the 11th finished from page 2), `competition_id=None` when none is left; a teacher without the setting → `ManageRequired` and nothing changes; afterwards `cancel_competition` raises `NotCancellable(FINISHED)` and `update_competition` raises `NotEditable(FINISHED)`; a new competition of the subject can take the finished one's name; exactly one log line `Competition finished: id=<id>` and no name in it.
- [ ] T019 [US1] Add `finish_competition` and `NotFinishable` to `app/services/competitions.py` per contracts/services.md §`competitions` and research R1 (depends on T018): `class NotFinishable(ValueError)` carrying `status`, as `NotCancellable`; `finish_competition(session, teacher_id, competition_id, subject_id, status) -> Landing`: `_require_manage`; `row, subject = lock_competition(...)`; `now = utc_now()`; `current = status_of(row, now)`; not `IN_PROGRESS` → `raise _refuse(session, True, NotFinishable(current))`; `before, _ = _listed(session, subject, status, now)` and the old index; `update(Competition).where(id == competition_id, cancelled_at IS NULL, stopped_at IS NULL, starts_at <= now).values(stopped_at=now)`; `rowcount == 0` → `raise NotFinishable(_reread_status(session, competition_id))`; `after, _ = _listed(...)`; commit; `logger.info("Competition finished: id=%d", competition_id)`; `return landing(after, competition_id, old_index)`. A docstring as `cancel_competition`'s. Update the module docstring (finishing joins creating, editing and cancelling; "Contract for later milestones": stopping is `finish_competition`; grading reads only **Finished** competitions, under the share lock).
- [ ] T020 [US1] Add the finish routes to `app/routers/teacher_competitions.py` and the template `app/templates/pages/teacher/competition_finish.html` per contracts/http-routes.md §7–§8 (depends on T001, T019):
  - `FINISH_REFUSALS = {UPCOMING: "“{name}” has not started yet and cannot be finished.", CANCELLED: "“{name}” has been cancelled and cannot be finished.", FINISHED: "“{name}” has already finished."}` and `_finish_refused(...)` with the question "Finish competition “<name>”?" through `_refused`; `NOTICES["finished"] = "Competition “{name}” was finished"`;
  - `GET /{competition_id:int}/finish` (`finish_competition_page`) and `POST /{competition_id:int}/finish` (`finish_competition_action`), each a copy of the cancel pair's structure: `require_manage` first, `offered_subject`, `find_competition`, the status (`competition.status in FINISH_REFUSALS` → refusal), then the page or `finish_competition(...)` mapping `ManageRequired` → `AccessDenied`, `CompetitionNotFound` → 404, `NotFinishable` → `_finish_refused` with its status; success → `redirect(list_path(selected.id, status_filter, landing.page, landing.competition_id, _notice_token(request, competition_id, "finished")))`;
  - the template, as `competition_cancel.html`: back link "Back to the competitions"; question "Finish competition “{{ competition.name }}” of {{ subject.name }}, started {{ local_time(competition.starts_at) }}?"; consequence "The competition will be marked Finished. Its answers can no longer be entered or changed, and it cannot be cancelled or restarted. Its answers can then be graded."; `confirmation(..., "Finish competition", back, hidden={"subject", "status", "page"}, back_label="Keep in progress", kind="primary")`; a header comment citing contracts/http-routes.md §7;
  - update the module docstring (finishing joins cancelling; the manage routes).
- [ ] T021 [US1] Add **Finish competition** to the row menu in `app/templates/pages/teacher/competitions.html` per research R12 (depends on T020): after **Answers** and before **Cancel competition**, `{%- if can_manage and c.status == "in_progress" %}{{ menu_link("Finish competition", "/teacher/competitions/" ~ c.id ~ "/finish?" ~ return_query) }}{% endif -%}` (not destructive); update the template's header comment with the menu order of FR-004.
- [ ] T022 [US1] Add the finishing route tests to `tests/integration/test_teacher_competitions.py` (depends on T021): the confirmation names the competition, its subject and its start in the browser's zone, with the consequence verbatim, a primary (not destructive) submit **Finish competition** and the link **Keep in progress** to the list at the competition; **Keep in progress** changes nothing; confirming under **All** and **Finished** redirects (303) to the same subject, filter and page, at `#competition-<id>`, with the notice "Competition “Spring round” was finished" and the badge **Finished**; under **In progress** the four landings of US1 scenario 4 (the row that took its place, the row before, the previous page's last row, the empty state); afterwards the menu has no **Finish competition** or **Cancel competition**, the edit and cancel addresses show their refusals, the competition's **Questions** and **Teams** pages are read-only for a teacher with the setting too (no **Add question**, **Add team** or **Remove**) and their add and remove addresses show the 12.2 refusal for a finished competition (spec US1 scenario 7), and a new competition of the subject takes the name; reloading the landing page sends nothing again.

**Checkpoint**: a competition can be finished from the menu, with its confirmation, notice and
landing. US1 is done.

---

## Phase 4: User Story 2 - Finishing is refused for the wrong status, and happens once (Priority: P1)

**Goal**: the finish refusals for **Upcoming**, **Cancelled** and **Finished**, the start passing,
and exactly one change under races.

**Independent Test**: as in spec US2: typed addresses and forms for each status; the start passing;
two finishes, finish and cancel, and the same form twice at the same moment.

- [ ] T023 [P] [US2] Add the refusal tests to `tests/integration/test_teacher_competitions.py` (depends on T020): for an **Upcoming** (typed address), a **Cancelled** and a **Finished** competition, both `GET …/finish` and `POST …/finish` answer 409 with the question "Finish competition “<name>”?", the reason verbatim and **Back to competitions** to the list at the competition, and the competition is unchanged; with the clock moved past the start, the same `GET` shows the confirmation and the `POST` finishes; the `POST` sent twice → the first 303, the second 409 "“<name>” has already finished.".
- [ ] T024 [P] [US2] Add the PostgreSQL-only race tests to `tests/integration/test_competition_service.py` (depends on T019): two sessions finishing the same competition behind a `threading.Barrier` → exactly one returns a `Landing`, the other raises `NotFinishable(FINISHED)`; a finish and a cancel at the same moment → exactly one succeeds and the other raises `NotCancellable(FINISHED)` or `NotFinishable(CANCELLED)`, and `one_end` holds; a session holding `lock_competition(share=True)` (an answer save in progress) makes `finish_competition` in a second session wait until it commits; a `save_answers` started after the finish committed raises `AnswersClosed(FINISHED)` and stores nothing.

**Checkpoint**: finishing is refused where it must be and is never applied twice. US2 is done.

---

## Phase 5: User Story 3 - The Grades page lists every team with its progress (Priority: P1) 🎯 MVP

**Goal**: "Grades of “…”": every team of a finished competition in region boxes, with **Answered**,
**Graded**, **Score**, **Grade answers**, the overall progress and the filter links.

**Independent Test**: as in spec US3: a finished competition with teams of linked, unlinked,
deactivated and deleted institutions in several regions, answers and grades in every combination.

- [ ] T025 [P] [US3] Add the `grade_team_page` tests to `tests/integration/test_grade_service.py` (depends on T013): every team is listed, deleted ones (`is_deleted`) and those of a deactivated institution or region included, in the order and region groups of `team_entries`; 25 teams page as 10/10/5 with the region totals across pages; the row values (answered, questions, graded, score, active members); `teams_total` and `teams_graded` count all teams whatever the filter, a team with no answers among the graded; under `UNGRADED` only teams with `graded < answered` are listed (not a team with no answers), and the paging total and region totals count only those; no teams → empty groups, `teams_total == 0`; `is_listed` is true for a listed team under both filters and false for a fully graded team under `UNGRADED` and for a team not in the competition; `team_page_of` returns the page that holds the team under the filter (1, 2 or 3 of 25 teams), and 1 for a team not listed under it.
- [ ] T026 [US3] Implement `grade_team_page(session, competition_id, show, p) -> GradeTeamPage`, `is_listed(session, competition_id, team_id, show) -> bool` and `team_page_of(session, competition_id, team_id, show) -> int` in `app/services/grades.py` per contracts/services.md §Reads and research R5, R6 (depends on T025): `entries = team_entries(session, competition_id)` unfiltered; `counts = grade_counts(...)`; the question count of the competition (one `select(func.count())`); `listed = entries` or, for `UNGRADED`, the entries whose count is not fully graded; `group_by_region(listed, p, make_rows)` with `make_rows` counting active members of the page's teams in one `count_active_members` call and building `GradeTeamRow`s; `teams_total = len(entries)`, `teams_graded` the fully graded of all entries. `is_listed`: the team is among the entries and, under `UNGRADED`, not fully graded. `team_page_of`: the page of the Grades page under `show` that holds the team (`index // PAGE_SIZE + 1` in the listed entries), 1 when the team is not listed: the grading sheet's way back when its address carries no valid `back`, as 12.3's `team_answers.team_page_of`. The three share one private helper that builds the listed entries for a filter.
- [ ] T027 [US3] Add the Grades page to `app/routers/teacher_grades.py` and the template `app/templates/pages/teacher/competition_grades.html` per contracts/http-routes.md §1 (depends on T003, T017, T026):
  - `GET /grades` (`competition_grades_page`) with `subject`, `status`, `page`, `p`, `show` as `Query(None)`: `_open(...)`; `show = parse_grade_filter(show)`; `listing = grade_team_page(session, competition.id, show, parse_page(p))`; `grade_hrefs` per row `grading_sheet_path(competition.id, row.team_id, context, show, back=listing.paging.number)`; `filter_links = [("All teams", grades_path(..., ALL), show is ALL), ("Ungraded only", grades_path(..., UNGRADED), show is UNGRADED)]`; `page_href = page_prefix(grades_path(competition.id, context, show))`; `back = context.back_to_list(competition.id)`;
  - the template (header comment citing §1): back link "Back to the competitions"; `page_heading("Grades of “" ~ competition.name ~ "”")`; `details_list` Subject, Start (`local_time`), Status (badge); `<p>Graded {{ listing.teams_graded }} of {{ listing.teams_total }} {{ "team" if listing.teams_total == 1 else "teams" }}</p>`; if `teams_total == 0` → `empty_state("No teams in this competition")` and nothing else; else `filter_links(filter_links, "Show")`, then if no group → `empty_state("All teams are graded")`, else the two page navigations ("Teams", "Pages, top"/"Pages, bottom") around the region groups with `data_table(["Team", "Educational institution", "Active members", "Answered", "Graded", "Score", "Actions"])`; each row `<tr id="team-{{ row.team_id }}">` with `cell("Answered", row.answered ~ " of " ~ row.questions, nowrap=True)`, `cell("Graded", row.graded ~ " of " ~ row.answered, nowrap=True)`, `cell("Score", row.score, nowrap=True)`, and an `actions_cell` with `row_note("(deleted)")` for a deleted team then `link_button("Grade answers", grade_hrefs[row.team_id], kind="secondary", outline=True, small=True)`.
- [ ] T028 [US3] Add **Grades** to the row menu in `app/templates/pages/teacher/competitions.html` per research R10, R12 (depends on T027): after **Answers** and before **Finish competition**, `{%- if can_manage and c.status == "finished" %}{{ menu_link("Grades", "/teacher/competitions/" ~ c.id ~ "/grades?" ~ return_query) }}{% endif -%}` — `can_manage`, not `can_add`, so a finished competition of a deactivated subject offers it.
- [ ] T029 [US3] Create `tests/integration/test_teacher_grades.py` with its `Scene` (a finished competition of 4 questions; 25 teams in three regions of linked, unlinked, deactivated-institution, deactivated-region and deleted teams; answers and grades in every combination; Olena with the setting and no links; Taras without it) and the Grades page tests (depends on T028): the heading, details, back link to the list at the competition; "Graded <n> of 25 teams"; every team listed incl. unlinked, deactivated and "(deleted)" (row note in the actions cell); region boxes, order, headers and counts as the Teams page; "Teams 1–10 of 25", the page in the address (`p`) and reload; the three columns per row incl. "0 of 0" and "0" for a team with no answers and "0" for a team with no grades; **Grade answers** on every row; "No teams in this competition" with "Graded 0 of 0 teams" under both filters; phone labels "Answered", "Graded", "Score" on the cells.

**Checkpoint**: a teacher with the setting sees every team of a finished competition with its
progress. US3 is done.

---

## Phase 6: User Story 4 - A teacher grades a team's answers on one sheet (Priority: P1) 🎯 MVP

**Goal**: the grading sheet with the reference answers, a grade field under each answered question,
and **Save grades**.

**Independent Test**: as in spec US4: open the sheet of a team with answered and unanswered
questions, save, change and empty grades in one save, and check everything that follows.

- [ ] T030 [P] [US4] Add the `grading_sheet` and `save_grades` success tests to `tests/integration/test_grade_service.py` (depends on T013): `grading_sheet` lists every copy in order with number, copied text and reference answer (also after the bank question is edited or deleted), the team's answer and grade, `answer=None` for an unanswered one, the team's institution, `is_deleted`, and the `GradeCount`; `GradedTeamNotFound` for an unknown team and one not in the competition; a deleted team and one of a deactivated institution or region are found; `save_grades` stores, changes and empties grades in one call (`{q1: "5", q2: "", q3: " 10 "}`), leaves an unnamed answered question's grade as it was, never changes any `text`, returns `GradeSaveResult(graded, changed)` with `changed` counting only real changes (0 for an unchanged save), and logs exactly `Grades saved: competition=<id> team=<id> graded=<n> changed=<n>` with no name or text.
- [ ] T031 [US4] Implement `grading_sheet(session, competition_id, team_id) -> GradingSheet` in `app/services/grades.py` per contracts/services.md §Reads (depends on T030): the team (`session.get(Team, ...)`, `GradedTeamNotFound` if `None`), its link (`session.get(CompetitionTeam, (competition_id, team_id))`, `GradedTeamNotFound` if `None`); the institution (for its name; deactivated is fine); the team's `TeamAnswer` rows by copy id; every copy of `competition_entries.question_copies` (moved there in T013; never import from `team_answers`) numbered from 1 with text and reference answer, the answer text or `None`, the grade; the `GradeCount` counted from those rows. No access check (docstring: the caller holds the setting and has checked the competition and its status).
- [ ] T032 [US4] Implement `save_grades(...)` in `app/services/grades.py` per contracts/services.md §Write and research R3 (depends on T031): in order, each refusal through a `_rollback(session, error)` helper: `if not teacher_access.can_manage_competitions(session, teacher_id, lock=True)` → `ManageRequired`; `competition, _ = competitions.lock_competition(session, competition_id, subject_id, share=True)`; `status = competitions.status_of(competition, competitions.utc_now())`, not `FINISHED` → `GradingClosed(status)`; `session.get(Team, team_id)` is `None` → `GradedTeamNotFound`; the link `session.get(CompetitionTeam, (competition_id, team_id), with_for_update=True, populate_existing=True)` is `None` → `GradedTeamNotFound`; `numbers` = copy id → number from `competition_entries.question_copies`; `stored` = the team's rows re-read with `populate_existing`; any named id not in `numbers` or not in `stored` → `GradedQuestionNotFound`; `clean_grade` on each named value in question order, collecting `InvalidGrade.message` by copy id → `InvalidGrades(errors)`; then for each named id set `stored[id].grade` where it differs, `session.add`, count `changed`; `graded` = the stored rows with a grade after the change; commit; the log line; `GradeSaveResult(graded, changed)`.
- [ ] T033 [US4] Add the grading sheet routes to `app/routers/teacher_grades.py` and the template `app/templates/pages/teacher/team_grading_sheet.html` per contracts/http-routes.md §2–§3 (depends on T002, T032):
  - a private `_render_sheet(request, competition, context, sheet, show, back, *, sent=None, errors=None, notice=None)`: items per contracts/components.md §2 (`field_id = f"grade-{id}"`, `value` = `sent.get(id)` or the saved grade as text or `""`, `error`), `field_errors` and `field_order` for the `error_summary`, `action`, `hidden = context.hidden() | {"show": show.value if UNGRADED else "", "back": back}`, the back link `grades_path(competition.id, context, show, p=back, anchor=sheet.team_id if is_listed(...) else None)`; status 400 when `errors`, else 200;
  - `GET /grades/{team_id:int}` (`team_grading_sheet_page`) with `subject`, `status`, `page`, `show`, `back`, `notice`: `_open`; `team_id > MAX_ID` → `not_found(TEAM_NOT_FOUND)`; `grading_sheet(...)` (`GradedTeamNotFound` → 404); `back = back_page(back) or grades.team_page_of(session, competition.id, team_id, show)`; the notice via `read_grades_notice`;
  - `POST /grades/{team_id:int}` (`save_grades_action`) with `fields: GradeFields`, `subject`, `status`, `page`, `show`, `back` as `Form("")`: `_open`; `MAX_ID` check; `parse_prefixed(fields, GRADE_FIELD_PREFIX)` is `None` → `not_found(QUESTION_NOT_FOUND)`; `save_grades(...)` mapping `ManageRequired` → `AccessDenied(Role.TEACHER)`, `CompetitionNotFound` → 404, `GradingClosed` → `grades_refused`, `GradedTeamNotFound` → `not_found(TEAM_NOT_FOUND)`, `GradedQuestionNotFound` → `not_found(QUESTION_NOT_FOUND)`, `InvalidGrades` → `_render_sheet(..., sent=grades, errors=invalid.errors)`; success → `redirect(grading_sheet_path(..., notice=grades_notice_token(...)))`;
  - the template (header comment citing §2): back link "Back to the grades"; `page_heading("Grade answers of “" ~ sheet.team_name ~ "” in “" ~ competition.name ~ "”")`; `details_list([("Educational institution", sheet.institution_name)])` followed by `row_note("(deleted)")` for a deleted team; `error_summary(errors, order=field_order)`; the success notice; then `empty_state("No questions in this competition")` when there are no questions; else, when the team has no answers, the text "“{{ sheet.team_name }}” gave no answers, so there is nothing to grade" above the `grading_sheet` (which renders no form); else the `grading_sheet(items, action, hidden)`.
- [ ] T034 [US4] Add the grading sheet tests to `tests/integration/test_teacher_grades.py` (depends on T033): **Grade answers** opens the sheet with the heading, the institution, "(deleted)" for a deleted team, the back link to the Grades page at the page and filter, at the team; every question numbered in order with its copied text, "Reference answer" and "Answer to question <n>" with line breaks kept; a field "Grade for question <n>" with the hint, `inputmode="numeric"` and the placeholder "Not graded" only under answered questions, the saved grade in its field; "Not answered" and no field on the others; one save storing, changing and emptying grades → 303 to the sheet with the notice "Grades of “Comets” were saved" and the values in the fields, also when nothing changed; " 7 ", "0" and "10" accepted; the Grades page's **Graded**, **Score** and overall progress follow; reloading does not save again; a team with no answers shows every "Not answered", the text "“Comets” gave no answers, so there is nothing to grade" and no **Save grades**; a competition with no questions shows "No questions in this competition" and no **Save grades**.

**Checkpoint**: a teacher with the setting finishes a competition and grades every team. The MVP
(US1, US3, US4) is done.

---

## Phase 7: User Story 5 - Invalid grades save nothing (Priority: P1)

**Goal**: an invalid grade saves nothing and shows the sheet again with every value kept.

**Independent Test**: as in spec US5.

- [ ] T035 [P] [US5] Add the invalid-grade service tests to `tests/integration/test_grade_service.py` (depends on T032): each of "7.5", "-1", "11", "seven" among valid changes raises `InvalidGrades` with "Enter a whole number from 0 to 10." at its copy id and stores nothing (the other grades unchanged); two invalid grades are both in `errors`, in question order; nothing is logged.
- [ ] T036 [US5] Add the invalid-grade route tests to `tests/integration/test_teacher_grades.py` (depends on T033): each of "7.5", "-1", "11", "seven" → 400, the sheet with every sent value kept (also the valid ones, e.g. "6"), the error at that field (`aria-invalid="true"`, the message) and the error summary "There is a problem" linking to `#grade-<id>`; two invalid grades → two errors and two summary links in question order; nothing stored; then a valid save stores all.

**Checkpoint**: US5 is done.

---

## Phase 8: User Story 6 - A grader shows only the teams that still need grading (Priority: P2)

**Goal**: the **Ungraded only** filter, kept in every address, and the back-link landings.

**Independent Test**: as in spec US6.

- [ ] T037 [US6] Add the filter tests to `tests/integration/test_teacher_grades.py` (depends on T033): the page from the menu has **All teams** current (`aria-current="true"`), drawn like the current page; following **Ungraded only** from page 2 goes to page 1 of the filter with `show=ungraded` in the address, and **All teams** back to page 1 without `show`; under **Ungraded only** only teams with an ungraded answer are listed (not a team with no answers), "Teams 1–10 of 14" and the region counts count only them, and the overall progress still counts all; the page navigation's links, the **Grade answers** links and the grading sheet's back link and hidden fields keep `show=ungraded`; "All teams are graded" when none needs grading; after grading the last ungraded answer of a team from **Ungraded only**, the back link leads to the same page without the team (no anchor), to the last page when that page no longer exists (it is clamped), and to "All teams are graded" when no team is left; an unknown `show` value reads as **All teams**.

**Checkpoint**: US6 is done.

---

## Phase 9: User Story 7 - Read access opens a team's answers while the competition is in progress (Priority: P1)

**Goal**: **View answers** for a **Read** institution's team while **In progress**, and the
read-only sheet with the access notice.

**Independent Test**: as in spec US7.

- [ ] T038 [P] [US7] Update the service tests in `tests/integration/test_team_answer_service.py` (depends on T016): `answer_sheet` with **Read** access returns the sheet with `can_write=False` (no longer `AnswersDenied`); with **Write**, `can_write=True`; an unlinked institution still raises `AnswersDenied`; `answer_team_page` rows keep `can_write`; `save_answers` with **Read** still raises `AnswersDenied` and stores nothing. Remove or rewrite the 12.3 assertions that **Read** gets `AnswersDenied` on the sheet (SC-011), naming the change in the test docstring.
- [ ] T039 [US7] Change `app/services/team_answers.py` per contracts/services.md §`team_answers` and research R7 (depends on T038): `AnswerSheet` gains `institution_id: int`, `can_write: bool`, `count: GradeCount | None = None`; `SheetQuestion` gains `grade: int | None = None`; `answer_sheet(session, teacher_id, competition_id, team_id, *, finished: bool = False)`: the same team checks; `reach_institution(session, teacher_id, team.institution_id)` without `write` (`NotReachable` → `AnswersDenied`), `can_write` from the result; the module docstring: **Read** reads the answers, only **Write** saves.
- [ ] T040 [US7] Change the sheet route and the Answers page in `app/routers/teacher_team_answers.py` and the templates per contracts/http-routes.md §4–§5 (depends on T002, T039):
  - `team_answer_sheet_page`: when `competition.status is IN_PROGRESS and sheet.can_write` → `_render_sheet` as today; otherwise → `_render_read_only(request, competition, context, sheet, back_page)` rendering the new `pages/teacher/team_answers_read_only.html`;
  - the new template (header comment citing §5): back link "Back to the answers"; `page_heading("Answers of “" ~ sheet.team_name ~ "” in “" ~ competition.name ~ "”")`; `details_list` with the institution; while **In progress**, `notice("You have Read access to “" ~ sheet.institution_name ~ "”, so you cannot change these answers.", "info")`; when `sheet.count` is set (Finished, US8), "Score: {{ count.score }}" and "Graded {{ count.graded }} of {{ count.answered }} {{ 'answer' if count.answered == 1 else 'answers' }}"; `empty_state("No questions in this competition")` or `answers_read_only(items, grades=sheet.count is not none)`;
  - `competition_answers.html`: the actions cell holds **Enter answers** when `row.can_write and competition.status == "in_progress"`, else **View answers** (both `link_button(..., kind="secondary", outline=True, small=True)` to `sheet_hrefs[row.team_id]`); no `row_note("Read access")`; `competition_answers_page` builds `sheet_hrefs` for every row; update the header comments.
- [ ] T041 [US7] Update `tests/integration/test_teacher_team_answers.py` for US7 (depends on T040): replace the 12.3 "Read access" row-note and "access denied on the sheet" assertions (US3 of 12.3, the mixed-access cases, the lowered-access case) with: a **Read** team has **View answers**, a **Write** team **Enter answers**, also for mixed access, no row note anywhere; the read-only sheet shows the notice verbatim, every question with the answer (line breaks kept) or "Not answered", no grade, no score, no "Reference answer", no `form`, no `textarea`, no button; it shows answers saved since when opened again; a typed save for a **Read** team, and one from a sheet opened before the access was lowered, → 403 and nothing stored; after raising the access to **Write** the row has **Enter answers**; an unlinked teacher's sheet → 403 and the team no longer listed; a competition with no questions shows "No questions in this competition". Name each replaced 12.3 assertion in the test docstrings (SC-011).

**Checkpoint**: US7 is done.

---

## Phase 10: User Story 8 - After finishing, a team's teachers see its answers, grades and score (Priority: P1)

**Goal**: the Answers pages of a **Finished** competition, read-only, with **Graded**, **Score** and
the grades.

**Independent Test**: as in spec US8.

- [ ] T042 [P] [US8] Add the finished-competition service tests to `tests/integration/test_team_answer_service.py` (depends on T012, T038): `answer_team_page(..., finished=True)` rows carry `graded` and `score` from `grade_counts` (`None` when not finished); `answer_sheet(..., finished=True)` fills each question's `grade` and `count`; the reference answer appears nowhere in the returned objects.
- [ ] T043 [US8] Change `app/services/team_answers.py` for finished competitions (depends on T042): `AnswerTeamRow` gains `graded: int | None = None` and `score: int | None = None`; `answer_team_page(session, teacher_id, competition_id, p, *, finished: bool = False)`: with `finished`, `make_rows` reads `grades.grade_counts` once and fills `answered`, `graded`, `score` from it; `answer_sheet(..., finished=True)` fills grades and the `GradeCount` from the team's rows. Update the module docstring's "Contract for later milestones" (grading by `app.services.grades`).
- [ ] T044 [US8] Change `app/routers/teacher_team_answers.py` and the templates for finished competitions per contracts/http-routes.md §4–§6 and research R7 (depends on T040, T043):
  - `_open(request, session, competition_id, subject, status, page, *, saving: bool = False)`: **Upcoming** and **Cancelled** → `answers_refused`; **Finished** → `answers_refused` only when `saving`; the save route passes `saving=True`, the two pages `False`;
  - both pages pass `finished=competition.status is FINISHED` to the service; the sheet renders the read-only template for **Finished** whatever the access;
  - `competition_answers.html`: on a **Finished** competition the table's headers are `["Team", "Educational institution", "Active members", "Answered", "Graded", "Score", "Actions"]` with `cell("Graded", row.graded ~ " of " ~ row.answered, nowrap=True)` and `cell("Score", row.score, nowrap=True)`;
  - `competitions.html`: **Answers** is offered when `c.status in ("in_progress", "finished")`;
  - update the router's module docstring (the order of checks of FR-041; **Finished** opens the read-only pages and refuses a save).
- [ ] T045 [US8] Add the finished-competition tests to `tests/integration/test_teacher_team_answers.py` (depends on T044): replace the 12.3 cases that refuse a **Finished** competition's Answers pages (SC-011, named in docstrings); a teacher with **Write** or **Read**, with or without the setting, sees only their institutions' teams with **Answered**, **Graded**, **Score** and **View answers**; deleted teams and teams of a deactivated institution or region are not listed and their sheets → 404; a team of an institution the teacher is not linked to → 403 even with the setting; the read-only sheet shows "Score: 17" and "Graded 3 of 4 answers", "Grade: 7 of 10" and "Not graded yet" under answered questions, "Not answered" on the others, no reference answer, no form, no notice of Read access; a team with no answers → every "Not answered" and "Score: 0"; a grade saved through the grading sheet appears on the next opening; an answer save from a sheet opened before the finish and a typed save afterwards → 409 "“Spring round” has finished, so its answers can no longer be entered." and nothing stored, the answers saved before the finish kept; **Upcoming** and **Cancelled** keep the 12.3 refusals on both pages and the save.

**Checkpoint**: US8 is done.

---

## Phase 11: User Story 9 - The menu offers the right entries per status and setting (Priority: P1)

**Goal**: the full menu order of FR-004 for every status and both kinds of teacher.

**Independent Test**: as in spec US9.

- [ ] T046 [US9] Replace the menu assertions in `tests/integration/test_teacher_competitions.py` (depends on T021, T028, T044): with the setting, **Upcoming** → **Edit**, **Questions**, **Teams**, **Cancel competition**; **In progress** → **Questions**, **Teams**, **Answers**, **Finish competition**, **Cancel competition**; **Finished** → **Questions**, **Teams**, **Answers**, **Grades**; **Cancelled** → **Questions**, **Teams**; without the setting, **In progress** and **Finished** → **Questions**, **Teams**, **Answers**, the others → **Questions**, **Teams**; **Finish competition** has no destructive class and **Cancel competition** has it; every entry's address carries the list's subject, status and page; when an administrator gives a teacher the setting (through the teacher form of milestone 8), the next list page shows **Finish competition** on the **In progress** competition and **Grades** on the **Finished** one, and when it is taken away they disappear on the next page (spec Edge Cases "The setting is given to a teacher"). Name the replaced 12.3 menu assertions in the docstring (SC-011).

**Checkpoint**: US9 is done.

---

## Phase 12: User Story 10 - Grading is possible only on a finished competition (Priority: P1)

**Goal**: the grading refusals for **Upcoming**, **In progress** and **Cancelled**.

**Independent Test**: as in spec US10.

- [ ] T047 [P] [US10] Add the grading refusal tests to `tests/integration/test_teacher_grades.py` and `tests/integration/test_grade_service.py` (depends on T033): for an **Upcoming**, an **In progress** and a **Cancelled** competition (with teams and answers stored directly), `GET …/grades`, `GET …/grades/<team>` and `POST …/grades/<team>` → 409 "Grade answers of “<name>”?" with the reason verbatim and **Back to competitions** to the list at the competition; `save_grades` raises `GradingClosed(<status>)`, stores nothing and logs nothing; an **In progress** competition with an unknown team shows the refusal, not "not found" (check order).

**Checkpoint**: US10 is done.

---

## Phase 13: User Story 11 - Only the right teacher reaches finishing and grading (Priority: P1)

**Goal**: "access denied" and "not found" everywhere they belong, in the order of FR-043.

**Independent Test**: as in spec US11.

- [ ] T048 [P] [US11] Add the access and not-found tests to `tests/integration/test_teacher_grades.py`, `tests/integration/test_teacher_competitions.py` and `tests/integration/test_grade_service.py` (depends on T020, T033): administrators and students get 403 on all five finishing and grading routes, also with unknown ids; a teacher without the setting gets 403 on the finish confirmation, the finish, the Grades page, a grading sheet and a save, also with unknown ids (before any id is read); the setting taken away while a sheet is open → the save 403 and the grades saved before kept (`save_grades` raises `ManageRequired`); unknown subject, unknown competition, another subject's competition, a hidden competition of a deactivated subject → 404; an unknown team, a team not in the competition, `team_id > MAX_ID` → "Team not found"; a save naming a copy of another competition, a question the team did not answer, the same `grade-<id>` twice, `grade-041` with `grade-41`, or `grade-x` → "Question not found", nothing stored; a teacher with the setting not linked to the team's institution grades it normally; a deleted team and a team of a deactivated institution are graded normally; a finish and a save without a valid cross-site token are refused and change nothing.
- [ ] T049 [P] [US11] Update `tests/integration/test_routes.py` per contracts/http-routes.md §Route table changes (depends on T020, T033): `test_the_write_routes_are_exact` gains `("POST", "/teacher/competitions/{competition_id:int}/finish")` and `("POST", "/teacher/competitions/{competition_id:int}/grades/{team_id:int}")` (docstring: "finishing and grading (milestone 12.4)"); the teacher manage-route sweeps gain `…/finish`, `…/grades` and `…/grades/{team_id:int}` (403 for administrators and students and for a cast teacher without the setting); the found-pages sweep covers them.

**Checkpoint**: US11 is done.

---

## Phase 14: User Story 12 - Two teachers grade the same team (Priority: P2)

**Goal**: the last save wins, never a mix.

**Independent Test**: as in spec US12.

- [ ] T050 [P] [US12] Add the two-teacher tests (depends on T032, T033): in `tests/integration/test_teacher_grades.py`, two clients open the same sheet, the first saves question 2 = 8, the second empties question 1 and saves question 3 = 6 → the stored grades are exactly the second page's (q1 and q2 not graded, q3 = 6), with no warning; in `tests/integration/test_grade_service.py` (PostgreSQL only), two sessions saving different grades of the same team behind a `threading.Barrier` → the stored grades equal one save's exactly, never a mix; two sessions saving different teams of one competition do not wait for each other.

**Checkpoint**: US12 is done.

---

## Phase 15: User Story 13 - A finished competition of a deactivated subject stays usable (Priority: P2)

**Goal**: **Answers** and **Grades** keep working for a finished competition of a deactivated
subject; other competitions of it stay hidden.

**Independent Test**: as in spec US13.

- [ ] T051 [P] [US13] Add the deactivated-subject tests to `tests/integration/test_teacher_grades.py`, `tests/integration/test_teacher_team_answers.py` and `tests/integration/test_teacher_competitions.py` (depends on T028, T044): with the subject deactivated, the finished competition is listed under "Deactivated subjects" with **Answers** (every teacher) and **Grades** (the setting) and no **Edit**, **Finish** or **Cancel**; its Grades page, a grading sheet and a save work and change nothing but grades; its Answers page and read-only sheets open; an **In progress** competition of the subject → 404 on its Answers pages, the finish confirmation and the finish.

**Checkpoint**: US13 is done.

---

## Phase 16: Polish & Cross-Cutting Concerns

**Purpose**: the form contract, the page patterns, logging, the README, the manual checks and the
whole suite.

- [ ] T052 [P] Extend `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json` (depends on T020, T033, T040): new cases `teacher-competition-finish` (the confirmation: `POST /teacher/competitions/{id}/finish` with `page`, `status`, `subject`), `teacher-grades-sheet` (`POST /teacher/competitions/{id}/grades/{id}` with `back`, `grade-{id}`…, `page`, `show`, `status`, `subject`), `teacher-grades-sheet-invalid` (the 400 page, same fields), and `teacher-team-answers-read-only` (no form); generated once with `UPDATE_FORM_CONTRACT=1` for these cases only; record "**Milestone 12.4**: finishing and grading (`teacher-competition-finish`, `teacher-grades*`, `teacher-team-answers-read-only` cases) are new" in the module docstring's list of deliberate changes. The existing cases stay unchanged.
- [ ] T053 [P] Extend `tests/integration/test_page_patterns.py` with this milestone's pages: the finish confirmation uses `confirmation` with a primary submit and **Keep in progress**; the Grades page has a back link, a `page_heading`, the details list with the status badge, the "Graded … of … teams" line, `filter_links` with exactly one `aria-current="true"`, `region_group` and two page navigations; the grading sheet has a back link, a `page_heading`, the details list, either an empty state or the `grading_sheet` with exactly one primary submit, every grade input labelled with its hint, and the `error_summary` only on the 400 page; the read-only sheet has no `form`; **Save grades** and **Finish competition** are `<button type="submit">` inside `POST` forms, never `disabled` and with no inline script, so the milestone 10.1 `loading-feedback.js` marks them busy and keeps them from being sent twice; the refusals use `refusal` with **Back to competitions**.
- [ ] T054 [P] Add the logging tests to `tests/integration/test_grade_service.py` and `tests/integration/test_competition_service.py`, with `caplog` on `uvicorn.error`: `finish_competition` logs exactly `Competition finished: id=<id>`; `save_grades` exactly `Grades saved: competition=<id> team=<id> graded=<n> changed=<n>`, also when nothing changed; no record contains the competition, team or institution name, a question, reference answer or answer text; every refusal logs nothing.
- [ ] T055 [P] Update `README.md`: finishing a competition (who, the primary confirmation, final, answers frozen) and grading (who, every team whatever the links, 0–10 per answer, the score is the sum, the **Ungraded only** filter, the last save wins, nothing stores who or when), and that on the Competitions tab **Read** access reads a team's answers, grades and score while only **Write** enters answers.
- [ ] T056 Run the manual and ad hoc browser checks of [quickstart.md](./quickstart.md) §2–§5 (the upgrade and downgrade of a 12.3 database; the walk-through; the Grades page and the grading sheet at 360 px and 375 px as labelled cards with no sideways scroll; the digit keypad; the filter links' current link in Light and Dark; **Finish competition** and **Save grades** busy while the next page loads; the gallery's `#confirmations`, `#grading-sheet` and `#filter-links`; reload and repeat) with an ad hoc Playwright run (`uv run --with playwright`, a copy of the database, port 8765) as in milestones 10.1–12.3, and record the results, with any deviation, in `specs/012.4-finish-and-grade/pr-notes.md`.
- [ ] T057 Run `uv run ruff check`, `uv run ruff format --check` and the whole suite on SQLite and on PostgreSQL (`TEST_POSTGRES_URL`); fix anything red (SC-011: only the 12.3 assertions named in T038, T041, T045 and T046 were changed). On delivery, move milestone 12.4 to **Delivered** in `docs/requirements/milestones.md` with a short summary and its spec link, as the other delivered milestones have.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup, US14)**: no dependency; blocks every page that uses the new patterns (T020,
  T027, T033, T040).
- **Phase 2 (Foundational)**: after Phase 1 is merged into the working tree (T017 needs nothing
  from Phase 1, but the suite must be green); blocks every user story.
- **US1 (Phase 3)** → **US2 (Phase 4)**: the refusals and races test the finish routes and service.
- **US3 (Phase 5)** → **US4 (Phase 6)** → **US5 (Phase 7)**, **US6 (Phase 8)**: the sheet's back link
  lands on the Grades page; the filter's landings need the sheet.
- **US7 (Phase 9)** → **US8 (Phase 10)**: the read-only sheet and template are built in US7 and
  gain grades in US8.
- **US9 (Phase 11)**: after T021, T028 and T044 (all three menu changes).
- **US10, US11, US12, US13**: after US4 (and US8 for US13's Answers checks).
- **Polish (Phase 16)**: after every story.

US1–US4 do not depend on US7–US8: finishing and grading work without the Answers changes, and the
Answers changes work on competitions finished directly by tests.

### Within each story

Service tests ([P]) → service → route and template → route tests. Each service task lists its
tests as a dependency so the tests are written first and seen failing.

### Parallel opportunities

- Phase 1: T005 and T006 in parallel once T004 is done.
- Phase 2: T008, T011, T012, T014, T015, T016 in parallel (different files) after their single
  dependency.
- US1 and US3 service work in parallel: T018/T019 (`competitions.py`) and T025/T026 (`grades.py`).
- US7 (T038–T041, `team_answers` and its router) in parallel with US3–US6 (`grades` and its router).
- The cross-cutting test phases US10–US13 and the polish tasks T052–T055 in parallel (different
  files or different test functions).

## Parallel Example: after Phase 2

```text
Developer A (finishing):   T018 → T019 → T020 → T021 → T022 → T023 → T024
Developer B (grading):     T025 → T026 → T027 → T028 → T029 → T030 → T031 → T032 → T033 → T034
Developer C (Answers):     T038 → T039 → T040 → T041 → T042 → T043 → T044 → T045
Then: T046 (menu), T047–T051, T052–T057
```

## Implementation Strategy

### MVP first (US14 + Phase 2 + US1 + US3 + US4)

1. Phase 1: the three patterns in the library, gallery and guidelines.
2. Phase 2: the column, the grade rule, the shared helpers, the skeletons.
3. US1: finish a competition. US3: the Grades page. US4: the grading sheet and its save.
4. **Stop and validate**: finish a competition, grade every team, check the scores (quickstart §3
   steps 3, 5, 6).

### Incremental delivery

1. MVP → demo finishing and grading.
2. US2, US5, US6: refusals and races, invalid grades, the filter.
3. US7, US8: Read access and the read-only Answers pages after finishing.
4. US9–US13: the menu, the cross-cutting checks, concurrency, deactivated subjects.
5. Polish, the whole suite on both engines, the manual checks, then the PR.
