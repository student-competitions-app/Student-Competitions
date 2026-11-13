---

description: "Task list for milestone 12.3: entering a team's answers (teacher)"
---

# Tasks: Entering a Team's Answers (Teacher) (Milestone 12.3)

**Input**: Design documents from `/specs/012.3-team-answers/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-036 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R17.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`. The two-session concurrency tests run on PostgreSQL only (skip on SQLite),
  with the `threading.Barrier` pattern of `tests/integration/test_team_service.py` and
  `tests/integration/test_competition_entries_service.py`.
- **Seeders**: `make_teacher(engine, settings, email=..., institutions={}, can_manage=True | False)`,
  `make_subject`, `make_question`, `make_institution(..., region="Kyiv", region_active=...)`,
  `make_class`, `make_team(engine, institution_id, name, deleted=...)`, `make_member`,
  `make_competition(engine, subject_id, name, starts_at=..., cancelled=..., stopped=...)`,
  `add_competition_question`, `add_competition_team`, and the new `save_team_answer` (T014).
- **The clock**: tests control "now" with
  `monkeypatch.setattr("app.services.competitions.utc_now", lambda: fixed)`, as
  `test_competition_entries_service.py` does. `app/services/team_answers.py` reads the clock
  **through that module attribute** (`competitions.utc_now()`), never through its own import, so
  the same patch moves it. No test sleeps.
- **Finished and Cancelled competitions** with answers are stored directly: `make_competition(...,
  stopped=True | cancelled=True)`, `add_competition_question`, `add_competition_team`, then
  `save_team_answer` (stopping does not exist yet; spec Assumptions).

**Organization**: tasks are grouped by user story (US1–US12 in spec.md).

- **Phase 1 is the answer sheet, the placeholder and the guidelines**, because the constitution puts
  the library, the gallery and the guidelines before any page (FR-034). It delivers **US12**.
- **Phase 2** is the table and its migration, the answer cleaning rules, the shared helpers
  (`lock_competition(share=True)`, `team_entries`, `group_by_region`, the 12.2 router's helpers),
  the service and router skeletons and the seeder.
- **US2** builds the team answers page (the listing and its progress) and **US1** the answer sheet
  and its save on top of it: together they are the MVP. US2 comes first although US1 is the story
  the milestone exists for, because the sheet's back link lands on the team answers page and
  **Enter answers** is its only way in. **US3** adds the "Read access" note; **US4** the menu entry.
- **US6** (too long), **US7** (status), **US8** (access) and **US9** (empty states) are enforced
  inside every route and service as they are built (the rules below); their own phases add the
  remaining branch where there is one, and the cross-cutting tests. **US5** proves the **Teams**
  page is unchanged; **US10** proves the last save wins under concurrency; **US11** changes the
  team deletion.

**Reference implementation**: milestones 11–12.2 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**: `app/services/competition_entries.py` (`_upcoming`, `team_page`, `_team_entries`,
  `_team_row`, `add_team`'s lock order with `with_for_update={"read": True}` and
  `populate_existing=True`, the refusals that roll back first), `app/services/competitions.py`
  (`_find`, `lock_competition`, `status_of`, the module's "Contract for later milestones"),
  `app/services/teams.py` (`delete_team`, `count_active_members`), `app/services/teacher_access.py`
  (`list_reachable_institutions`, `reach_institution(write=, lock=)`, `ReachableInstitution.can_write`,
  `NotReachable`, `WriteRequired`), `app/services/paging.py` (`parse_page`, `Paging.build`,
  `landing_index`), `app/schemas/question.py` (`clean_question_field`, `InvalidQuestionField`,
  `QUESTION_FIELD_MAX_LENGTH`, the cleaning order line endings → NUL → trim → length).
- **Routers**: `app/routers/teacher_competition_entries.py` (`ListContext`, `_address`, `_found`,
  `_render`, `_page_prefix`, `entries_refused`, `entry_notice_token` / `read_entry_notice`, the
  team routes), `app/routers/teacher_competitions.py` (`parse_id`, `not_found`, `redirect`,
  `teacher_id`, `settings_of`, `list_path`, `_refused`, `TAB`, `SUBJECT_NOT_FOUND`,
  `COMPETITION_NOT_FOUND`), `app/routers/teacher.py::render_teacher`.
- **Templates**: `app/templates/pages/teacher/competition_teams.html` (region groups, the data
  table, the actions cell), `competition_questions.html` (the text-card list, the details list),
  `competition_refused.html`, `competition_not_found.html`, `question_form.html` (the
  `error_summary` + `textarea_field` pattern); components `form.html` (`field`, `textarea_field`,
  `error_summary`, `form_actions`), `card.html` (`text_card`, `text_box`), `group.html`
  (`region_group`), `table.html` (`data_table`, `cell`, `actions_cell`, `row_note`), `button.html`
  (`link_button`), `frame.html`, `details.html`, `feedback.html`, `pagination.html`, `time.html`,
  `menu.html`; the gallery `app/templates/pages/admin/components.html` with
  `app/routers/admin_components.py`; `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Migration**: `migrations/versions/2026_11_06_59c636929942_competition_questions_and_teams.py`
  (frozen snapshot, `op.f` names, a frozen length constant).
- **Tests**: `tests/integration/test_teacher_competition_entries.py` (its `Scene`, the region-group
  and row parsers), `test_competition_entries_service.py` (the `clock` fixture, the PostgreSQL
  races), `test_teacher_competitions.py` (the menu assertions), `test_team_service.py`,
  `test_teacher_teams.py`, `test_routes.py` (`test_the_write_routes_are_exact`, `MANAGE_PATHS`,
  `ENTRY_READ_PATHS`, `test_the_manage_pages_are_found`), `test_form_contract.py` with
  `form_contract.json`, `test_page_patterns.py`, `test_component_gallery.py`, `test_migrations.py`,
  `tests/unit/test_question_schemas.py`, `tests/unit/test_templates.py`, `tests/html.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks** in every handler: role (`@allow_roles(Role.TEACHER)`, 403 for administrator
  and student, before any id is read) → the subject (404 "Subject not found") and the competition
  (404 "Competition not found") through `find_context` → the status (not **In progress** → 409
  refusal) → on the sheet and the save, the team (404 "Team not found") and, on the save, the named
  questions (404 "Question not found") → the **Write** access to the team's institution (403
  `AccessDenied(Role.TEACHER)`) → on the save, the lengths (400) → the service write, which repeats
  every check under lock and raises the same outcomes. **No Can manage competitions check** anywhere
  in this milestone (FR-002).
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON. Ids go through `parse_id` (ASCII digits ≤ `MAX_ID`), else
  "not found"; page numbers through `parse_page`.
- **Addresses**: `subject`, `status`, `page` keep their 12.1 meaning (the competitions list the
  teacher came from) and are carried through every page, form, refusal and redirect; `p` is the
  team answers page's page; `back` is the page of the team answers page the sheet returns to;
  `notice` the sealed notice (research R10). Every address is built by `list_path`, `answers_path`
  or `sheet_path` from looked-up ids and parsed values only.
- **Redirects**: the save is a `POST` through the existing cross-site check, answering `303` to the
  sheet, so a reload never repeats it (FR-030, SC-010).
- **Notices** travel sealed (`ANSWERS_NOTICE_PURPOSE = "team-answers-notice"`, 10 minutes), holding
  ids and the outcome only; the text is built when the page is shown (research R12).
- **Logging**: services log ids and counts only, exactly: `Team answers saved: competition=%d
  team=%d answered=%d changed=%d` and `Team deleted: id=%d members=%d competitions=%d answers=%d`. A
  refusal logs nothing. No email, person's name, competition name, team name, question text or
  answer text ever reaches a log line or an address (FR-031).
- **Components first**: the answer sheet and the placeholder are in the library, their CSS in the
  Components section of `app/static/css/app.css` (tokens only, no inline style, no literal colour or
  pixel length, no new token), the gallery and `ui-guidelines.md` **before** a page uses them
  (FR-034).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US12)

---

## Phase 1: Setup (Components and documents first)

**Purpose**: the placeholder argument, the answer sheet in the library, the gallery and the
guidelines, and the guidelines' wording changes (FR-034, research R15,
contracts/components.md §1–§4). Nothing here touches the database. Delivers **US12**.

- [ ] T001 Add the `placeholder` argument to `field` and `textarea_field` in `app/templates/components/form.html` per contracts/components.md §2: signatures `field(id, label, value="", error=None, hint=None, type="text", name=None, attrs={}, placeholder=None)` and `textarea_field(id, label, value="", error=None, hint=None, name=None, rows=6, attrs={}, placeholder=None)` (the new argument last, so every existing positional call is unchanged); when `placeholder` is given, the control gets `placeholder="{{ placeholder }}"` (escaped) after `_described(...)` and before `_attrs(attrs)`; the label and the `_messages` (hint, error) are rendered exactly as before; with `placeholder=None` the markup is byte-for-byte the current one. Update the macros' comments: the placeholder only says that the field is empty and never replaces the label or the hint.
- [ ] T002 Create `app/templates/components/answer_sheet.html` with `answer_sheet(items, action, hidden, submit_label="Save answers")` per contracts/components.md §1 and research R15 (depends on T001):
  - a header comment in the style of `group.html`'s (what it is: every answer of one participant to a list of questions, saved at once; that the page renders the `error_summary` under its heading and the empty state itself when there is no question; that milestone 13 will reuse it for students);
  - an empty `items` is `template_error("answer_sheet: at least one question is required")`, as `region_group` refuses;
  - markup: `<form method="post" action="{{ action }}">`, one `<input type="hidden" name="…" value="…">` per `hidden` item, then `<ol class="answer-sheet">` with, per item, `<li>` holding `{% call text_card("Question " ~ item.number) %}` with `text_box("Question", item.text)` and, under it, `textarea_field(item.field_id, "Answer to question " ~ item.number, value=item.value, error=item.error, hint="Up to 2,000 characters.", placeholder="Not answered", attrs={"maxlength": "2000"})`; then `form_actions(submit_label)` (one primary button, no **Cancel**) after the list; each item is a mapping with `number`, `field_id`, `text`, `value`, `error`;
  - CSS in the Components section of `app/static/css/app.css`, tokens only, no new token: `.answer-sheet` with `list-style: none`, `padding: 0`, `margin` as `.text-card-list`, consecutive items spaced as `.text-card-list` spaces its cards; the `textarea` inside `.answer-sheet` at `width: 100%`; long texts wrap (`overflow-wrap: anywhere`); below 768 px nothing changes but the widths (one column, no sideways scroll).
- [ ] T003 Add the gallery entries (depends on T002):
  - `app/routers/admin_components.py` (`_samples`): an `answer_sheet` sample of three items — question 1 answered with a two-line value ("Sodium chloride\nNaCl"), question 2 empty (`value=""`), question 3 with the error "Answer to question 3 can be at most 2,000 characters." and a long value — and the matching `errors` / `order` for an `error_summary`;
  - `app/templates/pages/admin/components.html`: a new `<section id="answer-sheet" aria-labelledby="answer-sheet-heading">` right after `#forms`, with the `error_summary` above the `answer_sheet` posting to `#` with one hidden field; import `components/answer_sheet.html`; in `#forms`, an empty `textarea_field("gallery-placeholder", "Answer to question 2", hint="Up to 2,000 characters.", placeholder="Not answered")`;
  - in `#actions-menu`, the five-entry menu example becomes **Edit**, **Questions**, **Teams**, **Answers**, **Cancel competition** where it shows the full menu (contracts/components.md §4);
  - add `#answer-sheet` to the gallery's table of contents if it has one.
- [ ] T004 [P] Update `docs/requirements/ui-guidelines.md` per contracts/components.md §1, §2, §4 (depends on T002's markup being settled):
  - §5 a new "Answer sheet (`components/answer_sheet.html`)" subsection right after "Forms": when to use it (every answer of one participant to a list of questions, saved at once), the numbering "Question <n>", the labels "Answer to question <n>", the hint "Up to 2,000 characters.", the placeholder "Not answered", one primary save button below the list and no **Cancel**, the `error_summary` under the page heading linking to each field, never a reference answer, and the gallery link `/admin/components#answer-sheet`;
  - §5 "Forms": the `placeholder` argument of `field` and `textarea_field`;
  - §7 "Wording patterns": a new bullet, verbatim: "**Placeholders** only say that a field is empty: "Not answered". A placeholder never replaces the field's label or hint, and never holds an example, an instruction or a value.";
  - §7 **Row notes**: the examples gain "Read access";
  - phone behaviour: "The answer sheet stays one column: each question card with its answer field under the text, the save button below the list.";
  - §5 "Actions menu": the example lists **Edit**, **Questions**, **Teams**, **Answers**, **Cancel competition**.
- [ ] T005 [P] Extend the component tests (depends on T003): `tests/integration/test_component_gallery.py` — `#answer-sheet` holds a `form[method=post]` with an `ol.answer-sheet` of three `li`, each a text card headed "Question 1"…"Question 3" with a `textarea` labelled "Answer to question <n>" (`label[for]` equals the `textarea` id), the hint "Up to 2,000 characters.", `placeholder="Not answered"` and `maxlength="2000"`; the third field has `aria-invalid="true"` and its message, and the `error_summary` above links to `#<its id>`; one primary submit "Save answers" after the `ol`; `#forms` has the empty field with the placeholder under its label and hint; `#actions-menu` has the five entries in order. `tests/unit/test_templates.py` — `textarea_field` and `field` without `placeholder` render byte-for-byte as before (compare against the current output), with it render the attribute once and keep the label and hint; `answer_sheet` with no items is a template error; a value starting with a line break keeps it. `tests/unit/test_stylesheet.py` stays green (every new class defined and used, no literal colour or pixel length).

**Checkpoint**: the answer sheet and the placeholder are in the library, the gallery and the
guidelines; every existing page renders as before. US12 is done.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the table and its migration, the answer cleaning rules, the shared helpers, the
service and router skeletons, and the seeder (data-model.md, research R1–R5, R8–R12,
contracts/services.md, contracts/http-routes.md §Order of checks, §Address parameters).

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end.

- [ ] T006 Create `app/schemas/answer.py` per contracts/services.md §`app/schemas/answer.py` and research R5: a module docstring (the question bank's rules of milestone 11 with an empty answer allowed; pure, no database); `ANSWER_MAX_LENGTH = QUESTION_FIELD_MAX_LENGTH` (2,000, imported from `app/schemas/question.py`; also the column length); `class InvalidAnswer(ValueError)` with a `message: str` "ready to show beside the field", as `InvalidQuestionField`; `clean_answer(raw: str, number: int) -> str` in `clean_question_field`'s order: `\r\n` and `\r` become `\n`; a `\x00` → `InvalidAnswer("Answer to question <number> cannot contain a null character.")`; `strip()` (inner line breaks kept); `""` means not answered and is returned; more than `ANSWER_MAX_LENGTH` code points (`len`) → `InvalidAnswer("Answer to question <number> can be at most 2,000 characters.")`.
- [ ] T007 [P] Create `tests/unit/test_answer_schemas.py` (depends on T006): `clean_answer` turns `\r\n` and `\r` into `\n`; keeps inner line breaks; trims spaces and line breaks around; spaces and line breaks only → `""`; `""` → `""`; exactly 2,000 code points saved; 2,001 refused with "Answer to question 3 can be at most 2,000 characters."; 2,000 plus a trailing space saved (2,001 before trimming); 2,000 Cyrillic characters saved and 2,001 refused (code points, not bytes); a NUL refused with "Answer to question 3 cannot contain a null character." before the length check; the number in the message is the one passed; `ANSWER_MAX_LENGTH == 2000`.
- [ ] T008 Add the model `TeamAnswer` to `app/models/competition.py` per data-model.md §1 and research R1, R2, and export it from `app/models/__init__.py` (and its `__all__`): `__tablename__ = "team_answers"`; a class docstring (one team's text answer to one question of one competition; a row exists only for an answered question; neither who saved it nor when is stored (FR-023); not personal data; its writers are `team_answers.save_answers` while **In progress** and `teams.delete_team`); `__table_args__ = (ForeignKeyConstraint(["competition_id", "team_id"], ["competition_teams.competition_id", "competition_teams.team_id"]), CheckConstraint("text <> ''", name="answered"))` so the convention names them `fk_team_answers_competition_id_competition_teams` and `ck_team_answers_answered`; columns: `competition_id: int = Field(primary_key=True)` and `team_id: int = Field(primary_key=True)` ("With the other, a foreign key to `competition_teams`: the team is in the competition. No `ON DELETE`."); `competition_question_id: int = Field(foreign_key="competition_questions.id", primary_key=True, index=True)` ("The competition's copy of the question (R2). No `ON DELETE`. Indexed for the foreign-key check when a question is removed."); `text: str` as `String(ANSWER_MAX_LENGTH)`, not null ("Trimmed, line breaks as `\n`, 1–2,000 code points, no NUL. Never empty: an emptied answer deletes the row."). Primary key named `pk_team_answers`. In the docstrings of `CompetitionTeam` and `CompetitionQuestion`, name `team_answers` as the table that references them (data-model.md §2).
- [ ] T009 Create the migration `migrations/versions/2026_11_<dd>_<rev>_team_answers.py` (`down_revision = "59c636929942"`) per data-model.md §5, following `2026_11_06_59c636929942_competition_questions_and_teams.py` (depends on T008): generate the revision id with `uv run alembic revision -m "team answers"` and write the operations by hand as a frozen snapshot (plain SQLAlchemy types, nothing imported from `app`, `ANSWER_MAX_LENGTH = 2000` as a frozen module constant); upgrade creates `team_answers` with the composite primary key `pk_team_answers`, the composite foreign key `(competition_id, team_id)` → `competition_teams` and the foreign key `competition_question_id` → `competition_questions.id` (no `ON DELETE`), `text` `String(2000)` not null, the check constraint `ck_team_answers_answered` (`text <> ''`) and the index `ix_team_answers_competition_question_id`, all names through `op.f`; no data step; downgrade drops the index and the table. Run `uv run alembic upgrade head` locally.
- [ ] T010 [P] Extend `tests/integration/test_migrations.py` (depends on T009): the head is the new revision; the stairway and drift checks cover it on both engines; after upgrade, a second row with the same `(competition_id, team_id, competition_question_id)` fails; a row whose `(competition_id, team_id)` is not in `competition_teams` fails; a row with an unknown `competition_question_id` fails; a row with `text = ''` fails; the index exists; downgrade to `59c636929942` drops the table and leaves `competition_teams` and `competition_questions` unchanged.
- [ ] T011 [P] Add the `share` flag to `lock_competition` in `app/services/competitions.py` per contracts/services.md §`app/services/competitions.py` and research R3: `lock_competition(session, competition_id, subject_id, *, share=False)`; with `share`, `_find` reads the competition `FOR SHARE` (`with_for_update={"read": True}`) instead of `FOR UPDATE`; the subject stays `FOR SHARE`; both refreshed (`populate_existing=True`); `CompetitionNotFound` after a rollback otherwise, unchanged. Update its docstring (a save of answers takes the competition `FOR SHARE`, so saves of one competition do not wait for each other while cancelling and stopping, which take it `FOR UPDATE`, still serialise with them) and the module's "Contract for later milestones": answers are entered only while **In progress**, under the competition's share lock (`app.services.team_answers`).
- [ ] T012 [P] Add the `lock_competition(share=True)` tests to `tests/integration/test_competition_service.py` (depends on T011): it returns the competition and subject as `share=False` does; `CompetitionNotFound` for an unknown id, another subject's id and a hidden competition, with the session usable afterwards; on PostgreSQL only, two sessions both holding `share=True` on the same competition do not block each other (the second returns while the first is still open), and `cancel_competition` in a second session waits until the first session's share lock is released (a `threading.Barrier` and a short `lock_timeout` or a join with a timeout, no sleep).
- [ ] T013 Extract the 12.2 grouping in `app/services/competition_entries.py` per contracts/services.md §`app/services/competition_entries.py` and research R11 (no behaviour change for 12.2):
  - rename `_team_entries` → public `team_entries(session, competition_id) -> list[tuple[Team, Institution, Region]]` (same query, same sort; docstring: deleted teams and deactivated institutions and regions included; the caller filters) and update its callers;
  - make `RegionGroup` generic in its row type (`class RegionGroup(Generic[Row])` with `rows: list[Row]`, a module-level `Row = TypeVar("Row")`); `CompetitionTeamPage.groups: list[RegionGroup[TeamRow]]`;
  - add `group_by_region(entries, p, make_rows) -> tuple[list[RegionGroup[Row]], Paging]`: the per-region totals over the whole `entries`, `Paging.build(p, len(entries))`, the page's slice, then `make_rows(shown)` called **once** with the page's `(team, institution, region)` entries, returning their rows in order (batched, so the caller counts members and answers in one query each), grouped into consecutive `RegionGroup(region_id, region_name, total, rows)`;
  - re-express `team_page` through `group_by_region` with a `make_rows` that calls `count_active_members` and `_team_row`;
  - the module docstring's "Contract for later milestones" points to `app.services.team_answers` for the answers. The 12.2 suite stays green unchanged.
- [ ] T014 [P] Add the seeder to `tests/conftest.py` in a new "Milestone 12.3: a team's answers" section after the 12.2 helpers (depends on T008): `save_team_answer(engine, competition_id, team_id, competition_question_id, text) -> None` inserts a `TeamAnswer` row as given. Docstring: "**Test-only**, but harmless: no personal data; it skips the status, team and access checks that `test_team_answer_service.py` covers, and is the only way to give a **Finished** or **Cancelled** competition answers."
- [ ] T015 Make the 12.2 router's helpers public in `app/routers/teacher_competition_entries.py` per contracts/http-routes.md §Changed routes and research R8: `_found` → `find_context`, `_render` → `render_competition_page`, `_address` → `address`, `_page_prefix` → `page_prefix`; update every caller in the module; update the module docstring to say milestone 12.3's router (`teacher_team_answers`) imports `ListContext`, `find_context`, `render_competition_page`, `address` and `page_prefix`, so both build the same addresses. No behaviour change; the 12.2 suite stays green.
- [ ] T016 Create `app/services/team_answers.py` with its skeleton per contracts/services.md §Types, §Errors and research R3, R11 (depends on T006, T008, T011, T013): a module docstring in the style of `competition_entries.py`'s (what the module holds; the clock is `competitions.utc_now`, read once per call; the write order competition `FOR SHARE` → status with a fresh clock → team `FOR SHARE` → its link `FOR UPDATE` → institution and region `FOR SHARE` → the named questions → **Write** access under lock → the texts → the change; every refusal rolls back first; the one log line; the "Contract for later milestones" of contracts/services.md: grading, milestone 13 students through steps 1–4 and 6–7, milestone 14 scoring changed rows, milestone 15 results); `from app.services import competitions`; the frozen dataclasses `AnswerTeamRow(team_id, name, institution_name, active_members, answered, questions, can_write)`, `AnswerTeamPage(groups: list[RegionGroup[AnswerTeamRow]], paging, linked)`, `SheetQuestion(competition_question_id, number, text, answer)`, `AnswerSheet(team_id, team_name, institution_name, questions)`, `SaveResult(answered, changed)` exactly as contracts/services.md §Types; the errors `AnswersClosed(status)` (carrying a `CompetitionStatus`), `TeamNotFound`, `QuestionNotFound`, `AnswersDenied`, `InvalidAnswers(errors: dict[int, str])` (by `competition_question_id`, in question order), re-using `competitions.CompetitionNotFound`; `count_answered(session, competition_id, team_ids: Collection[int]) -> dict[int, int]`: one grouped `select(TeamAnswer.team_id, func.count())` for the competition and `team_ids`, `{}` without a query for no ids, a team with no answer absent (read as 0); a private `_question_copies(session, competition_id) -> list[CompetitionQuestion]` in the order of adding (`CompetitionQuestion.id`).
- [ ] T017 Create `app/routers/teacher_team_answers.py` with its skeleton and include it in `app/main.py` next to `teacher_competition_entries.router` (depends on T015, T016), per contracts/http-routes.md §Order of checks, §Address parameters, §Refusal and research R8–R12, R14:
  - module docstring in the style of `teacher_competition_entries.py`'s (the team answers page and the sheet, who reads and who saves, the order of checks, no **Can manage competitions** check, the addresses `subject`/`status`/`page`/`p`/`back`/`notice`, the sealed notice, nothing logged here);
  - `router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")`; every page renders through `render_competition_page` (the **Competitions** tab);
  - not-found pages (`not_found` with `competition_not_found.html`): `TEAM_NOT_FOUND = ("Team not found", "This team does not exist, or it is not in this competition.")`, `QUESTION_NOT_FOUND = ("Question not found", "This question is not in this competition.")`;
  - `answers_path(competition_id, context, p=1, anchor=None) -> str` → `/teacher/competitions/17/answers?subject=3&status=in_progress&page=2&p=3#team-31` (`p` left out when 1, the anchor `team-<id>` when given) and `sheet_path(competition_id, team_id, context, back, notice=None) -> str` → `/teacher/competitions/17/answers/31?subject=3&back=3&notice=…`, both through `address`;
  - the notice: `ANSWERS_NOTICE_PURPOSE = "team-answers-notice"`, `ANSWERS_NOTICE_TTL = timedelta(minutes=10)`, `answers_notice_token(request, competition_id, team_id)` sealing `{"competition": id, "team": id, "outcome": "saved"}`, and `read_answers_notice(request, token, competition_id, team_id, team_name) -> str | None` returning "Answers of “<team>” were saved" — `None` for a missing, tampered or expired token, another competition's or team's, an unknown outcome or a non-integer id;
  - `ANSWER_REFUSALS: dict[CompetitionStatus, str]` with the three reasons of research R14 verbatim ("“{name}” has not started yet, so its answers cannot be entered yet.", "“{name}” has been cancelled, so its answers can no longer be entered.", "“{name}” has finished, so its answers can no longer be entered.") and `answers_refused(request, competition, status, context) -> HTMLResponse`: 409 `pages/teacher/competition_refused.html` with `question = "Enter answers for “<name>”?"`, the reason, `back = context.back_to_list(competition.id)`, `back_text = "Back to competitions"`, `back_link_text = "Back to the competitions"` (as the 12.1 edit refusal);
  - a private `_open(request, session, competition_id, subject, status, page)` doing checks 2–3: `find_context(...)` (its not-found response passed through), then `competition.status is not IN_PROGRESS` → `answers_refused(...)`; else `(context, competition)`.

**Checkpoint**: the table exists on both engines, the cleaning rules and the shared helpers are in
place, the skeletons import cleanly, and the whole existing suite is green.

---

## Phase 3: User Story 2 - A teacher sees their institutions' teams with their progress (Priority: P1) 🎯 MVP (with US1)

**Goal**: "Answers of “…”": only the teacher's reachable institutions' teams, grouped by region,
10 per page, with "<answered> of <questions>" and **Enter answers** (FR-004–FR-013).

**Independent Test**: seed a competition with teams of linked and unlinked institutions in several
regions, 12 of them listable, and check which teams are listed, the grouping, the order, the paging,
the headers and their counts, the rows, the progress and the phone layout.

### Implementation for User Story 2

- [ ] T018 [US2] Add the listing reads to `app/services/team_answers.py` per contracts/services.md §Reads and research R6, R11 (depends on T016): `answer_team_page(session, teacher_id, competition_id, p) -> AnswerTeamPage` — `reachable = {i.id: i for i in teacher_access.list_reachable_institutions(session, teacher_id)}`; `entries = [e for e in competition_entries.team_entries(session, competition_id) if e[0].deleted_at is None and e[1].id in reachable]` (live teams of reachable institutions only; the reachable list already drops deactivated institutions and regions, FR-005); `questions = ` the competition's `CompetitionQuestion` count; `group_by_region(entries, p, make_rows)` where `make_rows(shown)` calls `teams.count_active_members` and `count_answered` once each for the page's teams and builds `AnswerTeamRow(team_id, name, institution_name, active_members or 0, answered or 0, questions, can_write=reachable[institution.id].can_write)`; `linked = bool(reachable)`. `team_page_of(session, teacher_id, competition_id, team_id) -> int`: the same filtered listing, the page (`index // PAGE_SIZE + 1`) holding the team, 1 if it is not listed.
- [ ] T019 [US2] Add `GET /answers` to `app/routers/teacher_team_answers.py` per contracts/http-routes.md §1 (depends on T017, T018): query `subject`, `status`, `page`, `p`; `@allow_roles(Role.TEACHER)`; `_open(...)` (404 / 409); `answer_team_page(session, teacher_id(request), competition.id, parse_page(p))`; context: `listing`, `header` as on the 12.2 pages (the subject's name, the start, the status), `back = context.back_to_list(competition.id)`, `page_href = page_prefix(answers_path(competition.id, context))`, and per row the **Enter answers** href `sheet_path(competition.id, row.team_id, context, back=listing.paging.number)` (precomputed or a template helper). Opening it changes nothing.
- [ ] T020 [P] [US2] Create `app/templates/pages/teacher/competition_answers.html` per contracts/http-routes.md §1 (depends on T017): extends `layouts/teacher.html`; header comment; `{% block title %}Answers of “{{ competition.name }}” — {{ app_name }}{% endblock %}`; `back_link(back, "Back to the competitions")`; `page_heading("Answers of “" ~ competition.name ~ "”")` with no action; the `details_list` Subject, Start (`local_time`), Status (`competition_status_badge`) as in `competition_teams.html`; empty states, the first that applies: `empty_state("You are not linked to any educational institution")` when `not listing.linked`, else `empty_state("No teams from your educational institutions")` when no group (no hint for either); otherwise `page_navigation(listing.paging, page_href, "Teams", "Pages, top")`, for each group `{% call region_group(g.region_name, g.total, "region-" ~ g.region_id ~ "-p" ~ listing.paging.number) %}` holding `data_table(["Team", "Educational institution", "Active members", "Answered", "Actions"])`, rows `<tr id="team-{{ row.team_id }}">` with `cell("Team", row.name)`, `cell("Educational institution", row.institution_name)`, `cell("Active members", row.active_members)`, `cell("Answered", row.answered ~ " of " ~ row.questions)` (plain text, labelled "Answered" on a phone: "Answered 3 of 6"), and an `actions_cell()` holding `link_button("Enter answers", row.href, kind="secondary", outline=True, small=True)` when `row.can_write` (US3 adds the note otherwise); the bottom navigation. No **Add team**, no **Remove** (FR-011).
- [ ] T021 [US2] Keep the route-table tests green (depends on T019): in `tests/integration/test_routes.py` add `"/teacher/competitions/{competition_id:int}/answers"` to `ENTRY_READ_PATHS` and extend its docstring ("…and a competition's team answers page and answer sheets (milestone 12.3), which every teacher may open: id 1 names no competition and answers 404, not 403"); `test_the_manage_pages_are_found` keeps comparing against `MANAGE_PATHS` after removing `ENTRY_READ_PATHS`.
- [ ] T022 [P] [US2] Create `tests/integration/test_team_answer_service.py` with its setup and the US2 service tests (depends on T014, T018): a module docstring (research R17); a `clock` fixture patching `app.services.competitions.utc_now` (fixed after the competition's start, so it is **In progress**); seeds of a subject "Chemistry", regions "Kyiv", "Lviv", "Odesa", institutions School No. 5 and Gymnasium No. 1 (Kyiv), Lyceum No. 2 (Lviv) and others, a teacher Taras with **Write** to the two Kyiv institutions and **Read** to Lyceum No. 2, and an In progress "Spring round" of 6 copies; tests: of 30 teams in five regions, the 12 of Taras's institutions are listed, 9 in Kyiv and 3 in Lviv, page 1 Kyiv (total 9, 9 rows) then Lviv (total 3, 1 row), page 2 Lviv (total 3, 2 rows); regions and teams sorted by name ignoring case, ties by id; a deleted team, a team of a deactivated institution and one of a deactivated region not listed, and not counted in the totals; `can_write` per level; `active_members` per team; `answered` 0, 3 and 2 (after an emptying, seeded with `save_team_answer`), `questions` 6, and 0 of 0 for a competition with no copies; `linked=False` for a teacher with no link and for one linked only to a deactivated institution; a link removed or lowered to Read is seen on the next call; `team_page_of` for a team on page 2, and 1 for a team not listed; `count_answered` returns `{}` for no ids.
- [ ] T023 [US2] Create `tests/integration/test_teacher_team_answers.py` with its setup and the US2 route tests (depends on T019–T021): a module docstring; a `Scene` fixture as in `test_teacher_competition_entries.py` (Taras with Write and Read links and no setting, Olena with the setting, the `clock` fixture, `client.cookies.set("sc_time_zone", "Europe/Kyiv")`, an In progress "Spring round" of "Chemistry" with 6 copies, teams of linked and unlinked institutions); parsing helpers on `tests/html.py` for the region groups and rows with the **Answered** column; tests for US2-1 to US2-9: the title "Answers of “Spring round”", the subject, the start in a `<time>` in Kyiv time and the **In progress** badge under the heading, the back link to the competitions list with the context in the address at `#competition-<id>`; only the 12 teams of Taras's institutions, "Teams 1–10 of 12", the headers "Kyiv · 9 teams" and "Lviv · 3 teams" (repeated on page 2) and "Kyiv · 1 team" for one team; unique `aria-labelledby` ids; the columns Team, Educational institution, Active members, Answered, Actions; "0 of 6", "3 of 6"; the phone label "Answered" on the progress cell (`data-label`); no **Add team** and no **Remove** for Taras and for Olena; **Enter answers** on a Write row links to `/teacher/competitions/<id>/answers/<team>?subject=…&back=<page>`; `p` kept in the address and restored on reload; `p=99` and `p=x` open the nearest valid page; with no `subject`, the back link falls back as in 12.2; no team name or competition name in any address.

**Checkpoint**: every teacher sees the progress of their own institutions' teams.

---

## Phase 4: User Story 1 - A teacher with Write access enters a team's answers (Priority: P1) 🎯 MVP

**Goal**: "Answers of “<team>” in “<competition>”": every question numbered with its answer field,
one **Save answers** that saves them all, the notice, the trimmed answers, no reference answer
(FR-014–FR-024, FR-030).

**Independent Test**: as a teacher with **Write** access to one institution, open the answer sheet
of one of its teams in an **In progress** competition, save, change and empty answers, and check the
fields, the notice, the stored answers, the progress and the back link.

### Implementation for User Story 1

- [ ] T024 [US1] Add `answer_sheet(session, teacher_id, competition_id, team_id) -> AnswerSheet` to `app/services/team_answers.py` per contracts/services.md §Reads and research R3, R6 (depends on T016): checks without locks, in order — the team (`session.get(Team, team_id)` unknown or `deleted_at` set), its link to the competition (no `CompetitionTeam` row), its institution or region inactive → `TeamNotFound`; then `teacher_access.reach_institution(session, teacher_id, institution_id, write=True)`: `NotReachable` or `WriteRequired` → `AnswersDenied`; then `_question_copies(...)` with the team's `TeamAnswer` rows in the competition, as `SheetQuestion(id, number=index + 1, text=copy.text, answer=stored or "")` — never the copy's `reference_answer`.
- [ ] T025 [US1] Add `save_answers(session, teacher_id, competition_id, subject_id, team_id, raw_answers: Mapping[int, str]) -> SaveResult` per contracts/services.md §Write and research R3, R4 (depends on T024), in one transaction:
  1. `competitions.lock_competition(session, competition_id, subject_id, share=True)` (`CompetitionNotFound` passes through);
  2. `status_of(competition, competitions.utc_now())` not `IN_PROGRESS` → roll back, `AnswersClosed(status)`;
  3. the team `session.get(Team, team_id, with_for_update={"read": True}, populate_existing=True)`, then its `CompetitionTeam` row `with_for_update=True` (`FOR UPDATE`, `populate_existing=True`), then its institution and region `with_for_update={"read": True}`: unknown, `deleted_at` set, no link, or inactive institution or region → roll back, `TeamNotFound`;
  4. every key of `raw_answers` must be one of the competition's copy ids, else roll back, `QuestionNotFound`;
  5. `teacher_access.reach_institution(..., write=True, lock=True)`: `NotReachable` or `WriteRequired` → `AnswersDenied` (it rolls back itself);
  6. `clean_answer(raw, number)` for each named question, `number` its position in the order of adding; any `InvalidAnswer` → roll back, `InvalidAnswers({copy_id: message, …})` in question order;
  7. read the team's stored answers in the competition; for each named question: `""` deletes the row if there is one, a text equal to the stored one writes nothing, any other inserts or updates it; unnamed questions keep their rows; commit; log `Team answers saved: competition=%d team=%d answered=%d changed=%d`; return `SaveResult(answered=<rows after>, changed=<rows written or deleted>)`.
- [ ] T026 [US1] Add the sheet routes to `app/routers/teacher_team_answers.py` per contracts/http-routes.md §2–§3 and research R9, R12 (depends on T017, T025):
  - `async def answer_fields(request: Request) -> list[tuple[str, str]]`: awaits `request.form()` and returns `form.multi_items()` filtered on names starting with `answer-`, **every** pair in the order sent — never a `dict` or `form.items()`, which keep one value per name and would silently drop a repeated `answer-41` (HTTP parameter pollution; research R9);
  - `GET /answers/{team_id:int}` (checks 1–5): query `subject`, `status`, `page`, `back`, `notice`; `_open(...)`; `team_id > MAX_ID` → 404 `TEAM_NOT_FOUND`; `answer_sheet(...)`: `TeamNotFound` → 404 `TEAM_NOT_FOUND`, `AnswersDenied` → `raise AccessDenied(Role.TEACHER)`; `back` parsed with `parse_page`-style digits, missing or invalid → `team_page_of(...)`; context: the sheet, `items` (`number`, `field_id = "answer-<id>"`, `text`, `value = answer`, `error = None`), `action = "/teacher/competitions/<id>/answers/<team>"`, `hidden = context.hidden() | {"back": back}`, `back_href = answers_path(competition.id, context, p=back, anchor=team_id)`, the notice text from `read_answers_notice`;
  - `POST /answers/{team_id:int}` (checks 1–6): form `subject`, `status`, `page`, `back` as `Form("")` and `fields: list[tuple[str, str]] = Depends(answer_fields)`; the handler is a plain `def`; `_open(...)`; `team_id > MAX_ID` → 404 `TEAM_NOT_FOUND` before any answer field is read or the service is called (as the `GET`; the id never reaches a query, where SQLite would raise `OverflowError`); parse each `answer-<suffix>` with `parse_id` into a `{copy id: text}` mapping built pair by pair: a suffix that is not an id, or an id already in the mapping (the same name sent twice, or two spellings of one id such as `answer-41` and `answer-041`) → 404 `QUESTION_NOT_FOUND` before the service is called, so nothing is saved; `save_answers(...)` mapping `CompetitionNotFound` → 404 `COMPETITION_NOT_FOUND`, `AnswersClosed(status)` → `answers_refused(...)`, `TeamNotFound` → 404 `TEAM_NOT_FOUND`, `QuestionNotFound` → 404 `QUESTION_NOT_FOUND`, `AnswersDenied` → `AccessDenied(Role.TEACHER)` (US6 adds `InvalidAnswers`); success → `redirect(sheet_path(competition.id, team_id, context, back, notice=answers_notice_token(...)))` (303), also when nothing changed.
- [ ] T027 [P] [US1] Create `app/templates/pages/teacher/team_answer_sheet.html` (the answer sheet; the team answers page is `competition_answers.html`) per contracts/http-routes.md §2 (depends on T002, T017): extends `layouts/teacher.html`; header comment; `{% block title %}Answers of “{{ sheet.team_name }}” in “{{ competition.name }}” — {{ app_name }}{% endblock %}`; `back_link(back_href, "Back to the answers")`; `page_heading("Answers of “" ~ sheet.team_name ~ "” in “" ~ competition.name ~ "”")`; `details_list([("Educational institution", sheet.institution_name)])`; `error_summary(errors, order=field_order)` when there are errors (US6 passes them); the notice (`notice(text, "success")`); `empty_state("No questions in this competition")` and no form when `not items` (FR-021); otherwise `answer_sheet(items, action, hidden)`. No reference answer anywhere on the page.
- [ ] T028 [US1] Keep the route-table tests green (depends on T026): in `tests/integration/test_routes.py` add `("POST", "/teacher/competitions/{competition_id:int}/answers/{team_id:int}")` to `test_the_write_routes_are_exact` (and its docstring: "…and a team's answers (milestone 12.3)"), and `"/teacher/competitions/{competition_id:int}/answers/{team_id:int}"` to `ENTRY_READ_PATHS`.
- [ ] T029 [P] [US1] Add the US1 service tests to `tests/integration/test_team_answer_service.py` (depends on T025): `answer_sheet` lists the 6 copies in the order of adding, numbered 1–6, with the copy's text after the bank question is edited, and a copy whose bank question is deleted like any other; `answer` is `""` for unanswered and the stored text otherwise; no `reference_answer` on any `SheetQuestion`; `save_answers` stores questions 1, 2, 3 at once (`answered=3, changed=3`); a second save that changes one, empties another and fills a new one stores all three changes (`answered=3`, the emptied row gone); trimmed with inner line breaks kept (`"  a\r\nb  "` → `"a\nb"`); spaces and line breaks only → not answered and no row; an unchanged save writes nothing (`changed=0`); a question left out of `raw_answers` keeps its row; `count_answered` follows each save; the session is usable after every refusal.
- [ ] T030 [US1] Add the US1 route tests to `tests/integration/test_teacher_team_answers.py` (depends on T026–T028): US1-1 to US1-9 — **Enter answers** opens "Answers of “Comets” in “Spring round”" with "School No. 5" under the heading and the back link "Back to the answers" to the team answers page at `p=<back>` and `#team-<id>`; six `li` in the `ol.answer-sheet`, "Question 1"…"Question 6", each with its copied text and a field labelled "Answer to question <n>" with `placeholder="Not answered"`, the hint "Up to 2,000 characters." and `maxlength="2000"`; no reference answer text anywhere in the HTML; answering questions 1–3 and pressing **Save answers** → 303 to `/teacher/competitions/<id>/answers/<team>?subject=…&back=…&notice=…`, the page then shows "Answers of “Comets” were saved" (success) with the three answers in their fields; the back link page then reads "3 of 6"; change one, empty another, fill a new one → all three stored, the emptied field empty with the placeholder, "3 of 6"; a value with spaces and line breaks around it and a line break inside it is stored trimmed, with the inner line break kept, and shown that way in its field; spaces only → not answered; reloading the 303 target changes nothing (row count unchanged) and a tampered, expired or another team's `notice` shows no notice; `back` missing or `back=x` → the back link leads to the page holding the team; no team name, competition name or answer text in any address.

**Checkpoint**: a teacher with **Write** access enters and corrects a team's answers (MVP).

---

## Phase 5: User Story 3 - A teacher with Read access follows the progress only (Priority: P1)

**Goal**: "Read access" in the actions cell of a **Read**-access team, and "access denied" on its
sheet and save (FR-010, FR-025 step 5, SC-004).

**Independent Test**: as teachers with only **Read** access and with mixed access, check the actions
cell of every row, and try the answer sheet and a save of a **Read**-access team through a typed
address and a crafted form.

### Implementation for User Story 3

- [ ] T031 [US3] In `app/templates/pages/teacher/competition_answers.html` (depends on T020), the actions cell holds `row_note("Read access")` when `not row.can_write`, and **Enter answers** otherwise; every row has exactly one of the two.
- [ ] T032 [US3] Add the US3 route tests to `tests/integration/test_teacher_team_answers.py` (depends on T026, T031): US3-1 to US3-4 — Taras sees **Enter answers** on the Kyiv teams and "Read access" with no button on the Lyceum No. 2 teams; Iryna, with only **Read** access to Lyceum No. 2, sees its three teams with their progress and no **Enter answers** at all; Iryna's typed `GET …/answers/<team>` → 403 naming the teacher role, and her crafted `POST` with `answer-<id>` fields → 403 with `team_answers` unchanged (snapshot before and after); the 403 page shows no question text and no answer.

**Checkpoint**: **Read** access shows the progress and never an answer.

---

## Phase 6: User Story 4 - The menu offers Answers on a competition in progress (Priority: P1)

**Goal**: **Answers** after **Teams** and before **Cancel competition** on every **In progress** row,
for every teacher (FR-001, FR-002).

**Independent Test**: list competitions of every status as teachers with and without the setting and
check each menu's entries and their order.

### Implementation for User Story 4

- [ ] T033 [US4] Add the entry to `app/templates/pages/teacher/competitions.html` per research R16 (depends on T019): after the **Teams** `menu_link` and before **Cancel competition**, `{%- if c.status == "in_progress" %}{{ menu_link("Answers", "/teacher/competitions/" ~ c.id ~ "/answers?" ~ return_query) }}{% endif -%}`, with no `can_add` condition; update the template's header comment (the menu's five entries and who sees each). The router passes nothing new.
- [ ] T034 [US4] Update `tests/integration/test_teacher_competitions.py` for the replaced 12.2 rule (SC-011) and add the US4 tests (depends on T033): rewrite the assertions that expect the In progress menu to be **Questions**, **Teams**, **Cancel competition** (with the setting) or **Questions**, **Teams** (without), naming each in a comment as replaced by milestone 12.3 FR-001; then US4-1 to US4-4: with the setting, Upcoming lists **Edit**, **Questions**, **Teams**, **Cancel competition**; In progress **Questions**, **Teams**, **Answers**, **Cancel competition**; Finished and Cancelled **Questions**, **Teams**; without the setting In progress **Questions**, **Teams**, **Answers** and every other status **Questions**, **Teams**; a teacher with no institution link still gets **Answers**; the **Answers** href is `/teacher/competitions/<id>/answers?subject=…&status=…&page=…` with the list's context, and following it opens the page whose back link returns to that list at `#competition-<id>`.

**Checkpoint**: the answers are reachable from the competitions list.

---

## Phase 7: User Story 6 - Answers that are too long save nothing (Priority: P1)

**Goal**: a sheet with any answer over 2,000 characters after trimming saves nothing and shows
again with every text kept, each error at its field and the summary (FR-018, FR-019, SC-005).

**Independent Test**: save a sheet with one answer of 2,001 characters after trimming among other
changes, and then with exactly 2,000; check that nothing, then everything, is stored, and the kept
texts, the error and the summary.

### Implementation for User Story 6

- [ ] T035 [US6] Add the `InvalidAnswers` branch to `POST /answers/{team_id:int}` in `app/routers/teacher_team_answers.py` per contracts/http-routes.md §3 and research R13 (depends on T026, T027): read the sheet again after the service's rollback (`answer_sheet(...)`, mapping its errors as in the `GET`), then render `team_answer_sheet.html` with status 400: every item's `value` is the text **as sent** (not cleaned) for the questions the form named, else the stored answer; each invalid item its `error`; `errors = {"answer-<id>": message}` and `field_order = ["answer-<id>", …]` in question order for the `error_summary` ("There is a problem") under the heading; no notice; the same `hidden` and `back`.
- [ ] T036 [P] [US6] Add the US6 service tests to `tests/integration/test_team_answer_service.py` (depends on T025): an answer of 2,001 characters after trimming among changes to questions 1 and 5 → `InvalidAnswers` with one message keyed by its copy id, and `team_answers` unchanged (also the rows of questions 1 and 5); two too-long answers → both keyed, in question order; exactly 2,000 after trimming (2,001 before) → saved; a NUL → `InvalidAnswers` with the NUL message; the length is checked only after the access (a **Read**-access teacher with a too-long answer → `AnswersDenied`).
- [ ] T037 [US6] Add the US6 route tests to `tests/integration/test_teacher_team_answers.py` (depends on T035): US6-1 to US6-4 — a 2,001-character answer to question 4 with changes to questions 1 and 5 → 400, every field holds exactly the text sent (including surrounding spaces), question 4's field has `aria-invalid="true"` and "Answer to question 4 can be at most 2,000 characters.", the summary "There is a problem" under the heading links to `#answer-<id>`, and nothing is stored; two too-long answers → both errors, the summary in question order; exactly 2,000 characters → 303 and saved; the 400 page keeps the hidden context and `back`, and a resubmission from it saves. US6-5 — every answer field of the sheet (also on the 400 page) carries `maxlength="2000"`; the test client ignores that attribute, so the cases above prove the server check stands on its own (spec FR-018).

**Checkpoint**: a long paste never costs the teacher their typing, and never saves part of a sheet.

---

## Phase 8: User Story 7 - Answers are entered only while the competition is In progress (Priority: P1)

**Goal**: both pages and the save refuse an **Upcoming**, **Cancelled** or **Finished** competition
with the 12.1 refusal, under lock for the save (FR-025 step 3, FR-026, SC-003).

**Independent Test**: with the current time controlled by the test, open both pages and send saves
for an **Upcoming** competition, one cancelled while the sheet is open and a **Finished** one
(stored directly by the test); check the refusals, their reasons and links, that nothing is saved,
and that the **Upcoming** refusal turns into the page when the start passes.

### Tests for User Story 7

- [ ] T038 [P] [US7] Add the US7 service tests to `tests/integration/test_team_answer_service.py` (depends on T025): `save_answers` on an Upcoming (clock before the start), a Cancelled and a Finished competition (answers seeded with `save_team_answer`) → `AnswersClosed(status)` with the right status and `team_answers` unchanged; the start minute itself is In progress; `CompetitionNotFound` for another subject's id and a hidden competition, before the status; the status before the team (a cancelled competition with an unknown team → `AnswersClosed`) and before the access (a cancelled competition with a team of an unlinked institution → `AnswersClosed`); on PostgreSQL only: `save_answers` racing `competitions.cancel_competition` with a `threading.Barrier` → either the save commits first and the competition is then cancelled with the answers kept, or the cancellation commits first and the save gets `AnswersClosed(CANCELLED)` with nothing stored — never answers changed after the cancellation; two saves of different teams of one competition do not wait for each other (research R3).
- [ ] T039 [US7] Add the US7 route tests to `tests/integration/test_teacher_team_answers.py` (depends on T026): US7-1 to US7-5 — for an Upcoming "Autumn round", `GET …/answers`, `GET …/answers/<team>` and a `POST` → 409 "Enter answers for “Autumn round”?" with "“Autumn round” has not started yet, so its answers cannot be entered yet.", the link **Back to competitions** and the back link "Back to the competitions" both to the competitions list with the context at `#competition-<id>`, nothing stored; "has been cancelled, so its answers can no longer be entered." for a Cancelled one and "has finished, so its answers can no longer be entered." for a Finished one; the sheet opened, then `cancel_competition` in the service, then **Save answers** → the cancelled refusal and the answers saved before unchanged; the Upcoming address opened again after the clock passes the start → 200 and the page.

**Checkpoint**: nothing changes outside **In progress**.

---

## Phase 9: User Story 8 - Only the right teacher reaches the right team (Priority: P1)

**Goal**: the access and not-found rules on all three routes, in the spec's order (FR-025, FR-027,
FR-030, SC-002).

**Independent Test**: for every page and save of this milestone, send requests as each role and as
teachers with **Write**, **Read** and no link, including typed addresses and crafted forms for
unknown, mismatched and hidden subjects, competitions, teams and questions, and links changed while
a page is open; check the result, the check order and that nothing is saved.

### Tests for User Story 8

- [ ] T040 [P] [US8] Add the US8 service tests to `tests/integration/test_team_answer_service.py` (depends on T025): `TeamNotFound` for an unknown team, a deleted one, one not in the competition, one of a deactivated institution and one of a deactivated region (also of a **Read**-access institution: not found before access), with nothing stored; `QuestionNotFound` for another competition's copy id and an unknown id, nothing stored; `AnswersDenied` for an unlinked institution and a **Read** link, with the answers saved before unchanged; a link removed or lowered to Read between `answer_sheet` and `save_answers` → `AnswersDenied` (FR-027); deactivation keeps the answers (FR-029): seed "Comets" with three answers in the In progress competition and one in a Finished one (`save_team_answer`), snapshot every `team_answers` row of the team, then for the institution (`institutions.set_institution_active(..., False)`) and, separately, the region (`regions.set_region_active(..., False)`): the rows equal the snapshot, `answer_sheet` and a `save_answers` with changed, emptied and new answers → `TeamNotFound`, and the rows still equal the snapshot; after reactivation, the rows equal the snapshot, `answer_team_page` lists the team with `answered=3`, and `answer_sheet` returns the same texts; on PostgreSQL only: `save_answers` racing `teachers.update_teacher` lowering the link to Read (or removing it) and racing the deactivation of the team's institution → either the save commits first and the deactivation then keeps its rows, or the deactivation commits first and the save gets `AnswersDenied` / `TeamNotFound` with the rows equal to the snapshot taken before the race.
- [ ] T041 [US8] Add the access sweep to `tests/integration/test_teacher_team_answers.py` (depends on T026, T035): every `GET` and `POST` of the router (built from `ALL_ROUTES` filtered on `/teacher/competitions/{competition_id:int}/answers`, so a later route is covered) → 403 naming the role for the administrator and the student, through typed addresses and submitted forms, also with unknown ids, with a snapshot of `team_answers` unchanged; for Taras: 404 "Subject not found" for an unknown subject, 404 "Competition not found" for an unknown competition, one of another subject and one hidden by a deactivated subject (seeded both ways as the 12.2 sweep does, with and without a finished competition of the subject), each before a status refusal; the status refusal before an unknown team (a cancelled competition with team 999999 → 409); 404 "Team not found" for an unknown, a deleted, a not-in-the-competition team and a team of a deactivated institution or region, before access (a deleted team of a **Read**-access institution → 404); 404 "Question not found" for a form naming another competition's copy, an unknown id, `answer-abc`, the identical name sent twice (`answer-41=A&answer-41=B`, as a raw `application/x-www-form-urlencoded` body, since a `dict` of form data cannot repeat a key) whether the two values are equal or differ, and two spellings of one id (`answer-41` and `answer-041`), with nothing stored in each case; 403 for a team of an unlinked institution on the sheet and the save; the link lowered to Read (through `teachers.update_teacher`) or removed between opening the sheet and **Save answers** → 403, the answers saved before stay; after unlinking, the team answers page no longer lists the institution's teams, after lowering it shows "Read access" (FR-013); the subject deactivated while the sheet is open → 404 on save, answers kept; deactivation through the routes, for the team's institution (`institutions.set_institution_active(..., False)`) and, separately, its region (`regions.set_region_active(..., False)`), with "Comets" at "3 of 6": the team answers page no longer lists it, its sheet → 404 "Team not found" with no team name, question text or answer text in the HTML, and a crafted **Save answers** with changed, emptied and new answers → 404; then reactivated: the page lists "Comets" at "3 of 6" again, and the sheet shows exactly the three answers it had before (FR-029, spec Edge Cases); a `POST` without the cross-site check passing is refused and changes nothing; no route answers with FastAPI's JSON errors for odd values (`subject=1e9999`, `p=-1`, `back=%00`); a team id above `MAX_ID` (`MAX_ID + 1` and a 30-digit id) → 404 "Team not found" on both the `GET` and the `POST` of the sheet, on both engines, with `team_answers` unchanged; a path id that is not a number (`/teacher/competitions/abc/answers`, `…/answers/abc`) matches no route and answers 404 for every role, without "Competition not found".

**Checkpoint**: every page and save is refused to everyone it must be.

---

## Phase 10: User Story 5 - The Teams page stays as it is (Priority: P1)

**Goal**: the 12.2 **Teams** page lists every team of the competition and never offers **Enter
answers** (FR-003).

**Independent Test**: open the **Teams** page of competitions of every status as teachers with and
without the setting and with and without links, and check the teams and the buttons.

### Tests for User Story 5

- [ ] T042 [US5] Add the US5 tests to `tests/integration/test_teacher_competition_entries.py` (depends on T019): US5-1 and US5-2 — Mykola without the setting, and a teacher with no link, see every team of the In progress competition from every institution, with no **Add team**, no **Remove** and no "Enter answers" anywhere in the HTML; Olena with the setting sees **Add team** and **Remove** on an Upcoming competition and, on Upcoming, In progress, Cancelled and Finished competitions, never "Enter answers"; the **Teams** page HTML has no "Answered" column.

**Checkpoint**: the two views stay apart.

---

## Phase 11: User Story 9 - The empty states (Priority: P2)

**Goal**: "You are not linked to any educational institution", "No teams from your educational
institutions", and "No questions in this competition" with no **Save answers** (FR-012, FR-021).

**Independent Test**: open the team answers page as a teacher with no available link and as one
whose institutions have no team in the competition, and open the answer sheet of a competition with
no questions.

### Tests for User Story 9

- [ ] T043 [US9] Add the US9 route tests to `tests/integration/test_teacher_team_answers.py` (depends on T020, T027): US9-1 to US9-3 — Nadiia, linked only to a deactivated institution (and a teacher with no link at all), sees "You are not linked to any educational institution" with no hint and no table; Bohdan, with **Write** to a school none of whose teams is in the competition (and a teacher whose institution's teams are all deleted), sees "No teams from your educational institutions"; a competition with no questions: the team answers page reads "0 of 0" for every team, the sheet shows "No questions in this competition", no `form` and no **Save answers**; a `POST` to it with no `answer-` field → 303 and the notice (nothing to change).

**Checkpoint**: every empty page says why.

---

## Phase 12: User Story 10 - Two teachers save the same team (Priority: P2)

**Goal**: the last save wins, emptied answers included, and two simultaneous saves never mix
(FR-024, SC-006).

**Independent Test**: open the same team's sheet twice, save different answers from each,
including an emptied one, and check that the stored answers are exactly those of the later save.

### Tests for User Story 10

- [ ] T044 [P] [US10] Add the US10 service tests to `tests/integration/test_team_answer_service.py` (depends on T025): "Comets" answered question 1; Oksana's save answers question 2 (with question 1 as stored); Taras's later save, from a page that did not show her answer, empties question 1, sends question 2 empty and answers question 3 → the stored answers are exactly question 3; neither save is refused; on PostgreSQL only: two sessions saving different full sheets of the same team at once with a `threading.Barrier` (repeated a few times) → the stored answers equal exactly one of the two sheets, never a mix (research R4).
- [ ] T045 [US10] Add the US10 route test to `tests/integration/test_teacher_team_answers.py` (depends on T026): two teachers with **Write** to School No. 5 open the same sheet; the first saves, then the second saves its page with question 1 emptied → both 303 with the notice, and the sheet then shows exactly the second save's answers.

**Checkpoint**: the behaviour of concurrent saves is predictable.

---

## Phase 13: User Story 11 - Deleting a team deletes its answers in unfinished competitions (Priority: P2)

**Goal**: `delete_team` deletes the team's answers in every competition that is not **Finished**,
before its links; **Finished** keeps both (FR-028, SC-008).

**Independent Test**: give a team answers in an **In progress**, a **Cancelled** and a **Finished**
competition (the last two stored directly by the test), delete it, and check the stored answers in
each; send a save from a sheet opened before the deletion.

### Implementation for User Story 11

- [ ] T046 [US11] Change `delete_team` in `app/services/teams.py` per contracts/services.md §`app/services/teams.py` and research R7 (depends on T008): keep its checks and lock order; before deleting the links, `answers = session.execute(delete(TeamAnswer).where(col(TeamAnswer.team_id) == team_id, col(TeamAnswer.competition_id).in_(unfinished)))` with the same `unfinished` subquery (`stopped_at IS NULL`); log `Team deleted: id=%d members=%d competitions=%d answers=%d`. Update the docstring (deleting also deletes the team's answers in every competition that is not finished, before its links, which the composite foreign key requires; finished competitions keep the team and its answers) and the module docstring's milestone-12 paragraph.
- [ ] T047 [US11] Add the deletion tests to `tests/integration/test_team_service.py` (depends on T014, T025, T046): a team with answers in an In progress (clock past the start), a Cancelled and a Finished competition → after `delete_team`, no answer of it in the first two, all its answers in the Finished one, and the link kept only there; another team's answers untouched; the log line `Team deleted: id=<id> members=<n> competitions=2 answers=<n>` with no name; on PostgreSQL only: `delete_team` racing `team_answers.save_answers` for the same team with a `threading.Barrier` → afterwards the team has no answer in the In progress competition (either the save committed first and its rows were deleted, or it waited and got `TeamNotFound`).
- [ ] T048 [US11] Add the US11 route tests (depends on T046): in `tests/integration/test_teacher_team_answers.py`, US11-1 to US11-3 — after "Comets" is deleted on the **Teams** tab, its answers are gone from "Spring round" (In progress) and "Autumn round" (Cancelled), and "Summer round" (Finished) keeps it marked "(deleted)" on its **Teams** page with its answers in the table; a sheet opened before the deletion → **Save answers** → 404 "Team not found" and nothing stored; "Comets" is no longer listed on "Answers of “Spring round”". In `tests/integration/test_teacher_teams.py`, the deletion confirmation wording stays as in 12.2 (spec Assumptions) — assert it unchanged.

**Checkpoint**: deleted teams leave no answers behind except in finished competitions.

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: contracts, page patterns, logging, documents, the manual browser checks and delivery.

- [ ] T049 [P] Extend `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json`: new cases `teacher-team-answers` (the team answers page), `teacher-team-answers-sheet` (the sheet with answers, so the form, its hidden fields and the `answer-<id>` fields are captured), `teacher-team-answers-sheet-invalid` (the 400 page) and `teacher-team-answers-refused`, generated once with `UPDATE_FORM_CONTRACT=1` for those cases only; update `teacher-competitions` for the new menu entry only if the case records links; add a "**Milestone 12.3**: a team's answers (`teacher-team-answers*` cases) are new, generated once …" line to the module docstring; every other case unchanged.
- [ ] T050 [P] Extend `tests/integration/test_page_patterns.py` with this milestone's pages: the team answers page has a back link, a `page_heading`, the details list with the status badge, `region_group` (never a table caption) and two page navigations; the sheet has a back link, a `page_heading`, the details list, either the empty state or the `answer_sheet` with exactly one primary submit, every `textarea` labelled, with the hint and the placeholder, and the `error_summary` only on the 400 page; **Save answers** is a `<button type="submit">` inside a `POST` form, never `disabled` and with no inline script, so the milestone 10.1 `loading-feedback.js` marks it busy and keeps the form from being sent twice (FR-032, spec Edge Cases "Pressing Save answers twice"); the refusal uses `refusal` with **Back to competitions**.
- [ ] T051 [P] Add the logging tests (FR-031) to `tests/integration/test_team_answer_service.py`, with `caplog` on `uvicorn.error` as `test_competition_entries_service.py` does: `save_answers` logs exactly one line `Team answers saved: competition=<id> team=<id> answered=<n> changed=<n>`, also when nothing changed; no record contains the competition name, the team name, the institution name, a question text or an answer text; every refusal logs nothing.
- [ ] T052 [P] Update `README.md`: entering a team's answers (who sees the team answers page and which teams, **Write** enters and **Read** sees only the progress, only while **In progress**, the last save wins, nothing stores who or when, and deleting a team deletes its answers in every competition that has not finished).
- [ ] T053 Run the manual and ad hoc browser checks of [quickstart.md](./quickstart.md) §2–§5 (the upgrade and downgrade of a 12.2 database; the walk-through; the team answers page at 360 px and 375 px as labelled cards with "Answered 3 of 6"; the sheet one column with full-width fields and long names, questions and answers wrapping with no sideways scroll; **Save answers** busy while the next page loads; the placeholder "Not answered" under the label and hint in Light and Dark; the gallery's `#answer-sheet`; reload and repeat) with an ad hoc Playwright run (`uv run --with playwright`, a copy of the database, port 8765) as in milestones 10.1–12.2, and record the results, with any deviation, in `specs/012.3-team-answers/pr-notes.md`.
- [ ] T054 Run `uv run ruff check`, `uv run ruff format --check` and the whole suite on SQLite and on PostgreSQL (`TEST_POSTGRES_URL`); fix anything red (SC-011: only the 12.2 In progress menu assertions were changed, each named). On delivery, move milestone 12.3 to **Delivered** in `docs/requirements/milestones.md` with a short summary and its spec link, as the other delivered milestones have.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. T001 → T002 → T003 → T005; T004 after T002's markup is
  settled.
- **Phase 2 (Foundational)**: after Phase 1 (the sheet template uses T002). T006 → T007;
  T008 → T009 → T010; T008 → T014; T011 → T012; T013; T015; T006, T008, T011, T013 → T016;
  T015, T016 → T017. Blocks every story.
- **US2 (Phase 3)**: after Phase 2. T018 → T019 → T021; T020 in parallel with T019; T022 after
  T018; T023 last.
- **US1 (Phase 4)**: after US2 (the sheet's back link and **Enter answers** live on the team
  answers page). T024 → T025 → T026 → T028; T027 in parallel with T026; T029 after T025; T030 last.
- **US3 (Phase 5)**: after US1 (it tests the sheet's and save's 403).
- **US4 (Phase 6)**: after US2 (the menu links to the team answers page); independent of US1.
- **US6 (Phase 7)**: after US1 (it completes the save's handler).
- **US7 (Phase 8)**, **US8 (Phase 9)**: after US6, the last change to the routes.
- **US5 (Phase 10)**: after US2 (the "Enter answers" text exists).
- **US9 (Phase 11)**: after US1.
- **US10 (Phase 12)**: after US1.
- **US11 (Phase 13)**: T046 any time after T008; T047 after T025 (the race); T048 after US1.
- **US12**: delivered by Phase 1.
- **Polish (Phase 14)**: after every story.

### Within each story

- The service read or write before the routes that call it; templates in parallel with the routes;
  the route-table test updates in the same phase as the routes they cover, so the suite stays green;
  the story's tests last.

### Parallel opportunities

- Phase 1: T004 alongside T003; T005 after T003.
- Phase 2: T007, T010, T012, T014 and T015 alongside each other once T006, T008, T009 and T011 are
  done; T011 and T013 together.
- US2: T020 while T019 is written; T022 alongside T023's setup.
- US1: T027 while T026 is written; T029 alongside T030.
- US6–US10: the service-test tasks (T036, T038, T040, T044) all touch
  `test_team_answer_service.py`, so they are [P] against the route tests, not against each other.
- US11: T046 alongside any story after Phase 2.
- Polish: T049–T052 together.

## Parallel Example: User Story 1

```bash
# After T025 (save_answers) is done, in parallel:
Task: "T026 Add GET and POST /answers/{team_id:int} to app/routers/teacher_team_answers.py"
Task: "T027 Create app/templates/pages/teacher/team_answer_sheet.html"
Task: "T029 Add the US1 service tests to tests/integration/test_team_answer_service.py"
```

## Parallel Example: User Story 2

```bash
# After T018 (answer_team_page) is done, in parallel:
Task: "T019 Add GET /answers to app/routers/teacher_team_answers.py"
Task: "T020 Create app/templates/pages/teacher/competition_answers.html"
Task: "T022 Create tests/integration/test_team_answer_service.py (US2 service tests)"
```

## Implementation Strategy

### MVP first (User Stories 2 and 1)

1. Phase 1: the placeholder, the answer sheet, the gallery and the guidelines.
2. Phase 2: the table, the migration, the cleaning rules, the shared helpers, the skeletons, the
   seeder.
3. Phase 3 and Phase 4: the team answers page, then the sheet and its save. **Stop and validate**:
   as a teacher with **Write** access, enter, change and empty a team's answers through a typed
   **Answers** address, and see the progress follow.

### Incremental delivery

1. US3 ("Read access") → US4 (the menu entry) → US6 (too long) → US7 (status proof) → US8 (access
   sweep) → US5 (the **Teams** page unchanged) → US9 (empty states) → US10 (last save wins) → US11
   (team deletion).
2. Each story ends with its tests green on both engines and the whole suite green.
3. Polish: contracts, page patterns, logging, README, the manual browser run, delivery.

## Notes

- [P] tasks = different files, no dependency on an unfinished task.
- [Story] label maps each task to its user story for traceability.
- Commit after each task or logical group; stop at any checkpoint to validate the story on its own.
- Avoid vague tasks, same-file conflicts, and cross-story dependencies that break independence.
