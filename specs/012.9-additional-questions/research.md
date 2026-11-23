# Research: Additional Questions in the Question Bank (Milestone 12.9)

Phase 0 decisions for [plan.md](./plan.md). The spec left no `NEEDS CLARIFICATION`; each entry
below settles a design question the spec leaves to the plan, from the code as it stands after
milestone 12.8 (`main` at `3a4e5bb`).

## R1. How the mark is stored

- **Decision**: a column `questions.is_additional`, `BOOLEAN NOT NULL`, server default `false`,
  declared on the `Question` model with the same server default.
- **Rationale**: the mark is a yes/no property of one bank question (spec Key Entities), read on
  every list query, and the `is_…` name follows `subjects.is_active` and the other flags. A server
  default fills every existing row with "not additional" in the same statement (FR-002), so the
  migration needs no data step, and a row inserted without the column (the test seeders, a manual
  insert) is not additional (FR-001).
- **Alternatives considered**:
  - *A table of additional question ids*: one more join on every bank read and a second write
    on every edit, for a single boolean. Rejected.
  - *A "kind" column (ordinary / additional)*: no second kind is planned (YAGNI). Rejected.
  - *A copy of the mark on `competition_questions`*: the spec forbids it (FR-022).

## R2. The migration on SQLite

- **Decision**: one revision after `c730fd883079`, using
  `op.batch_alter_table("questions", recreate="auto", table_kwargs={"sqlite_autoincrement": True})`
  for both `add_column` and the downgrade's `drop_column`, as the milestone 11 revision does
  (`3e32707ed794`).
- **Rationale**: `questions` has `AUTOINCREMENT` on SQLite (milestone 11 R1, checked by
  `test_sqlite_never_reuses_a_question_id`). `ADD COLUMN` with a constant default needs no table
  copy, but the downgrade's `DROP COLUMN` makes batch mode copy the table. Without
  `table_kwargs` the copy would lose `AUTOINCREMENT`, so question numbers could be reused after a
  downgrade and upgrade. On PostgreSQL batch mode is a plain `ALTER TABLE`.
- **Alternatives considered**: a plain `op.add_column` with a raw `DROP COLUMN` in the downgrade:
  it depends on the SQLite version and breaks the pattern. Rejected.

## R3. Leaving the additional questions out for other teachers

- **Decision**: `app.services.questions.question_page` gains a required keyword-only argument,
  `include_additional: bool`. When it is false, the condition `is_additional IS false` is added to
  both the count and the page query, so the total, the paging (clamping a page past the end
  included) and the rows all count only the other questions.
  - The **Questions** tab passes `include_additional=can_manage_competitions(...)`, read once per
    request.
  - The **Add questions** page of a competition passes `True`, since it has already refused every
    teacher without the setting.
- **Rationale**: the constitution v2.6.0 (Principle IV) requires additional questions to be left
  out of what the server reads for other teachers, never only hidden in a template. A required
  argument with no default makes every caller decide: a new caller cannot leak by forgetting it,
  nor silently hide questions from a teacher with the setting. The setting is read without a lock,
  like every other page read; FR-017 asks only that the next request sees a change.
- **Alternatives considered**:
  - *Filtering in the template*: forbidden by Principle IV, and the count would still include them.
  - *Two functions (`manager_question_page`, `teacher_question_page`)*: duplicated paging code for
    one condition. Rejected.
  - *A default of `False` or `True`*: `False` would silently empty the **Add questions** page of
    additional questions; `True` would fail open. Rejected.
  - *An index on `(subject_id, is_additional)`*: subjects hold hundreds of questions at most; the
    existing `ix_questions_subject_id` serves both queries. Rejected (YAGNI).

## R4. The single-question endpoints

- **Decision**: no code change. The bank's edit, save, delete-confirmation and delete routes, the
  add form and its save, and the competition's **Add questions** page and its add already call
  `_require_manage` / `require_manage` first in the handler, before any id is parsed or looked up
  (011 http-routes §Order of checks, 012.2 likewise). `get_question` stays without a visibility
  filter, since only teachers with the setting reach it.
- **Rationale**: FR-020 is the current behaviour. What is new is the case to prove: the existing
  parametrised denial tests (`test_a_teacher_without_the_setting_is_refused_before_anything_is_looked_up`
  and its 12.2 counterpart) gain an `additional` target beside `listed`, `missing`, `deleted` and
  `deactivated-subject`, and compare the response bodies.
- **Alternatives considered**: a 404 for additional questions: it would show that the number exists.
  Rejected; the spec asks for the same "access denied" page for every target.

## R5. Saving the mark from the form

- **Decision**:
  - **The field**: the checkbox is named `additional`, with the value `1`. The add and edit
    handlers read it as `additional: str | None = Form(None)`, and the question is marked when a
    non-empty value arrives. FastAPI turns an empty form value into "missing" (0.141, `value == ""`
    → default), so an empty value clears the mark, as no value does. This is the spec's "any value
    marks; no value clears" (Edge Cases), with an empty string counting as no value.
  - **`create_question(..., is_additional: bool = False)`**: a new question is not additional
    unless marked (FR-001).
  - **`update_question(..., is_additional: bool)`** takes the argument as a *required* keyword, so
    an edit can never clear the mark by leaving it out. The mark joins the `changed` comparison:
    changing only the mark resets `updated_at` and logs "Question updated", like a change of the
    text.
  - **Re-rendering**: an invalid form is shown again with `values["additional"]` set to the boolean
    sent (FR-011). The edit form opens with the stored mark (FR-008). The add form, and the empty
    form after **Save and add one more question**, open with `False` (FR-007, FR-010): the redirect
    to `/teacher/questions/new` carries no mark.
- **Rationale**: plain strings keep the router's rule that no input gets FastAPI's 422 (011 R9). The
  service writes the mark under the same `FOR UPDATE` lock as the text, so the last save wins for
  all three values together.
- **Alternatives considered**: a `bool` form parameter. FastAPI's bool parsing answers 422 for
  values like `abc`, which breaks the 422-free rule. Rejected.

## R6. The mark on a competition's Questions page

- **Decision**: `app.services.competition_entries.question_page` gains a required keyword-only
  argument, `with_bank_mark: bool`. `CompetitionQuestionView` gains `is_additional: bool | None`.
  - **With the mark**: the query selects `Question.is_additional` beside `Question.deleted_at`,
    through the join it already makes, and fills the field.
  - **Without it**: the column is not selected, and the field is `None`.
  - **The router** passes `with_bank_mark=can_manage(request, session)`. The template shows the
    badge when `q.is_additional` is true.
  - **`get_competition_question`**, for the remove confirmation, which only teachers with the
    setting reach, fills `None`, since the confirmation shows no badge (FR-026).
- **Rationale**: the badge is the bank's current mark (FR-025), read like "Deleted from the question
  bank" (012.2 R11), so a later change of the mark shows on the next load and nothing in the
  competition changes (FR-023). Not reading the column for other teachers keeps the rule "left out
  of what the server reads", and `None` cannot be mistaken for "not additional".
- **Alternatives considered**:
  - *Always reading the mark and hiding it in the template*: against Principle IV. Rejected.
  - *Copying the mark onto the copy when it is added*: forbidden by FR-022, and it would not follow
    later changes. Rejected.

## R7. The badge and the text card

- **Decision**:
  - **`additional_badge()`** in `components/badge.html` returns
    `badge(pgettext("question", "Additional"), "info")`.
  - **`text_card(heading, id=None, badge=None)`** renders `<h3>{{ heading }} {{ badge }}</h3>` when
    `badge` is given (a rendered macro, already `Markup`), and the plain heading otherwise.
  - **CSS**: none expected. `.badge` is `inline-block`, `white-space: nowrap` and
    `vertical-align: middle`, so after the space it sits on the heading's line and wraps below it as
    one unit on a narrow screen. If the gallery check at 360 px shows the badge crowding the text,
    one token-only rule (`.text-card h3 .badge { margin-inline-start: var(--sc-space-1); }`) is the
    allowed fix.
  - **The gallery** (`/admin/components`): the badges section gains a "Marks" row with
    `additional_badge()`; the cards section shows "Question 58" with the badge.
  - **The guidelines**: already updated in `3a4e5bb` (Badges, Cards, Wording); they are checked
    against what is built.
- **Rationale**: `pgettext` with the context `question` lets the Ukrainian word agree with
  «питання» («Додаткове»), the method milestone 12.5 used for `status_badge`. A badge inside the
  `h3` is read with the heading, as FR-029 asks, and the anchor `#question-58` still lands on the
  card. `info` is fixed by the milestone.
- **Alternatives considered**:
  - *A row note* ("Additional question"): the guidelines keep row notes for records a row can no
    longer act on, and the product owner asked for a badge.
  - *A `caller`-based heading slot*: more general than the one present need (YAGNI). Rejected.

## R8. Texts and catalogues

- **Decision**: three new messages, extracted with Babel into both catalogues:

  | msgid (context) | English | Ukrainian |
  |---|---|---|
  | "Additional question" | Additional question | Додаткове питання |
  | "Additional questions and their answers are not given to participants before a competition." | (same) | Додаткові питання та відповіді на них не надаються учасникам до змагання. |
  | "Additional" (`question`) | Additional | Додаткове |

- **Rationale**: the glossary terms «учасники» and «змагання» (ui-guidelines §Glossary). The
  catalogue tests (`test_catalogues`, `test_ukrainian_wording`) require every message to be
  translated and compiled. The Ukrainian hint is an assumption of the spec, confirmed in review.

## R9. Tests

- **Decision**: no new test module; extend these.

  | Module | What it gains |
  |---|---|
  | `tests/conftest.py` | `make_question(..., additional=False)` |
  | `test_migrations.py` | the column at head (not null, default false); existing rows, deleted ones too, become not additional; `AUTOINCREMENT` kept after the downgrade and the upgrade again; the stairway and drift checks cover the revision |
  | `test_question_service.py` | `create_question` and `update_question` store and clear the mark; changing only the mark counts as a change; a deleted question or one of a deactivated subject cannot be updated and keeps its mark; `question_page(include_additional=False)` count, paging and clamp with a mixed subject and an all-additional subject; `include_additional=True` lists everything |
  | `test_teacher_questions.py` | the checkbox and hint on the add form (cleared) and the edit form (as stored); the mark saved by both save buttons and the edit; cleared by unchecking it; kept by an invalid form; cleared after "save and add one more"; the badge on the list for a teacher with the setting; for a teacher without the setting (Read, Write, no link) no additional question anywhere in the response body, counts and pages of the others only, "No questions yet" with no hint; the `additional` target in the denial test; giving and taking the setting between two requests |
  | `test_competition_entries_service.py` | `question_page(with_bank_mark=…)` fills `True`, `False` or `None`; marking and unmarking a question in the bank changes no stored copy, answer, grade or results file |
  | `test_teacher_competition_entries.py` | the badge on **Add questions**; adding an additional question; the badge on the competition's **Questions** page in all five statuses and on a finished competition of a deactivated subject, for a teacher with the setting only (absent from the response body for one without it); badge and "Deleted from the question bank" together; the badge follows a later change of the mark; the **Add questions** page and add refuse a teacher without the setting for an additional target too |
  | `test_teacher_team_answers.py`, `test_teacher_grades.py` | the answer and grading sheets of a competition holding an additional question show no mark |
  | `test_grade_service.py`, `test_team_answer_service.py` (and the existing calls in `test_teacher_competition_entries.py`) | the existing `update_question` calls pass `is_additional=False`, since the argument becomes required (T014); no new test |
  | `test_page_patterns.py` | only if it sweeps the question pages: a case for the list with an additional question, seen by a teacher with the setting (T034) |
  | `test_form_contract.py` + `form_contract.json` | the cases `teacher-question-new`, `-new-invalid`, `-new-saved`, `-edit` and `-edit-invalid` gain the field `additional`; regenerated for those cases only, recorded in the module's list of deliberate changes |
  | `test_component_gallery.py` | the **Additional** badge in the badges section, and the text card with the badge in its heading |
  | `tests/unit/test_templates.py` | `additional_badge()` gives **Additional** / «Додаткове» with `badge-info`; `text_card` with and without `badge` |

- **Rationale**: Principle III. Every changed route is tested allowed and denied, per role and
  setting (FR-021), on SQLite and PostgreSQL. No route is added, so `test_routes` needs no new
  entry, but it must stay green.

## R10. Documents

- **Decision**: in this pull request, the README's **Questions** paragraph says who sees the
  additional questions and drops "Every teacher can read it". On delivery (the "delivered" pull
  request, as for 12.8), `milestones.md` gets the 12.9 summary, and the milestone 11 summary
  drops "the shared question bank" (FR-034). The product requirements, the constitution v2.6.0 and
  the UI guidelines are already in `main` (`3a4e5bb`).
- **Rationale**: constitution, Development Workflow 5: documentation changes in the same PR as the
  behaviour; milestone summaries are written at delivery (milestones.md preamble).
