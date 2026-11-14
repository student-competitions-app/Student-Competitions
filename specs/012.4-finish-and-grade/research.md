# Research: Finishing a Competition and Grading Its Answers by Hand (Teacher) (Milestone 12.4)

Phase 0 of [plan.md](./plan.md). The spec has no open clarifications; its Assumptions section
settles the points the milestone left open. Each entry below records a design decision, the reason
for it and the alternatives considered.

---

## R1. Finishing writes `stopped_at`, as cancelling writes `cancelled_at`

**Decision** ([contracts/services.md](./contracts/services.md) §`competitions`):

- **No schema change for finishing.** `competitions.stopped_at` exists since milestone 12.1, the
  `one_end` check constraint keeps a competition from being both cancelled and finished, and
  `status_of` already derives **Finished** from it. Only tests have set it so far.
- **`competitions.finish_competition(session, teacher_id, competition_id, subject_id, status)`**
  follows `cancel_competition` step by step: `_require_manage` (the setting `FOR SHARE`);
  `lock_competition` (the competition `FOR UPDATE`, its subject `FOR SHARE`); the status with a
  fresh clock, which must be **In progress** (`NotFinishable(status)` otherwise); the list before
  the change, for the landing; then the conditional
  `UPDATE competitions SET stopped_at = :now WHERE id = :id AND cancelled_at IS NULL AND
  stopped_at IS NULL AND starts_at <= :now`; a row count of 0 re-reads the status
  (`_reread_status`) and raises `NotFinishable` with it; then the list after, the commit, one log
  line `Competition finished: id=%d`, and the `Landing`.
- **The update's condition is the one the 12.1 module docstring promised** ("Contract for later
  milestones"), so nothing else in the module changes.

**Rationale**:

- **Exactly one change when two requests race** (FR-013): the `FOR UPDATE` lock queues a finish and
  a cancel, or two finishes, of the same competition on PostgreSQL; the second re-reads the status
  under the lock and refuses. On SQLite, which renders no lock but serialises writers, the
  conditional update's row count decides. The same form sent twice finishes once and the second
  request gets "has already finished." The cancel path already refuses a **Finished** competition
  ("has finished and cannot be cancelled.").
- **Answer saves never cross a finish** (FR-011): a 12.3 save holds the competition `FOR SHARE` for
  its whole transaction (`lock_competition(share=True)`), so a finish waits for every save in
  progress, and every save that starts after the finish re-reads the status as **Finished** and is
  refused with the 12.3 "has finished" reason. This is the contract milestone 12.3 already wrote
  into `lock_competition`'s docstring.
- **The name is free again at once** (FR-010): the live-name partial index excludes rows with
  `stopped_at`, as it excludes cancelled ones.
- **An upcoming competition whose start passes** (FR-012): the status is derived with the clock of
  the request, so the next try sees **In progress**; the update's `starts_at <= :now` repeats the
  check in the database.

**Alternatives considered**:

- **A stored status column**: contradicts Principle VII ("derived on the server from the stored
  start and the stored stop or cancel") and the 12.1 design.
- **Finishing a competition on its own at a set time**: out of scope (the spec's Out of Scope); a
  competition has no duration.

---

## R2. A grade is a nullable column of `team_answers`

**Decision** ([data-model.md](./data-model.md) §1):

- **`team_answers.grade`**: `SMALLINT NULL`, with the check constraint
  `grade_range`: `grade IS NULL OR (grade >= 0 AND grade <= 10)`. `NULL` means "not graded".
- **No new table, no author, no time** (FR-028).

**Rationale**:

- **One grade per answer, and none for an unanswered question** (FR-023, FR-028), by construction: a
  row exists only for an answered question (12.3 R1), and it holds at most one grade. A grade can
  never outlive its answer, and a team's **Graded** and **Score** are a `COUNT(grade)` and a
  `SUM(grade)` over the rows already read for **Answered** (R5).
- **The rows never change once the competition is finished**: the 12.3 save refuses a **Finished**
  competition under lock (R1), and `teams.delete_team` touches only competitions that are not
  finished, where no grade exists. So the column needs no new rule in either writer. The 12.3 save
  writes `text` only and never `grade`.
- **Milestone 14** stores the LLM's proposed grade, justification and model in its own evaluation
  record (constitution, Principle VI); the stored grade that counts, proposed or adjusted, stays
  this column, so a team's score stays the sum of one column (FR-029, constitution Principle VII).
- **Both engines**: a plain column and a check constraint, added through Alembic's batch mode on
  SQLite (the project's `render_as_batch`), as earlier revisions do.

**Alternatives considered**:

- **A table `answer_grades` keyed like `team_answers`**: a one-to-one table with its own foreign key,
  a join on every read, and a second row to delete before an answer; it adds nothing a column does
  not give.
- **A grade on the competition team (one per team)**: the milestone grades each answer.
- **A database rule that grades exist only on finished competitions**: a check constraint cannot see
  another table; the service checks the status under lock, as 12.3 does for answers.

---

## R3. The grading save: one service write, every check under lock, in the spec's order

**Decision** ([contracts/services.md](./contracts/services.md) §`grades`):

`app/services/grades.py` (new), `save_grades(session, teacher_id, competition_id, subject_id,
team_id, raw_grades)`, in the order of FR-043, every refusal rolling back first:

1. **The setting**: `teacher_access.can_manage_competitions(…, lock=True)` (`ManageRequired`, the
   12.1 error), so a setting taken away while a sheet is open refuses the save (FR-002).
2. **The subject and the competition**: `competitions.lock_competition(…, share=True)`
   (`CompetitionNotFound`); a finished competition of a deactivated subject is visible (R10).
3. **The status** with a fresh clock: not **Finished** → `GradingClosed(status)`.
4. **The team and the questions**: the team row (`TeamNotFound` if unknown), its link to the
   competition `FOR UPDATE` (`TeamNotFound` if absent). **A deleted team, or one of a deactivated
   institution or region, is found** (FR-043 step 5): unlike 12.3, the team's own state is not
   checked. Then the named questions: each must be one of the competition's copies and have an
   answer of the team (`QuestionNotFound` otherwise).
5. **The grades**: `app.schemas.grade.clean_grade` on each named value, in question order
   (`InvalidGrades({copy id: message})`).
6. **The change**: the team's answers read again under the link's lock; each named answer gets its
   new grade (or `NULL` for an empty field) where it differs; one commit; one log line
   `Grades saved: competition=%d team=%d graded=%d changed=%d`, also when nothing changed.

**Rationale**:

- **The last save wins, never a mix** (FR-030): the link's `FOR UPDATE` queues two saves of the same
  team, and each writes every grade it names; the second save reads the rows again under the lock
  (`populate_existing`), so it compares against what the first committed. Saves of different teams
  do not wait for each other: the competition is held `FOR SHARE` only.
- **Why the competition `FOR SHARE` at all**: a **Finished** competition cannot change status any
  more (R1), but the lock keeps the 12.1–12.3 rule "every change to a competition's data takes the
  competition's lock first", and it makes the grading save wait for a finish that is committing.
- **A save that omits an answered question** (spec Assumptions) leaves its grade, as 12.3 leaves an
  omitted answer; only a crafted form can omit one.
- **The setting is checked first, before any id**, in the router as on every 12.1 manage route,
  and again under lock in the service.

**Alternatives considered**:

- **Grades in `team_answers.py`**: that module is the participants' side (12.3, and students in 13);
  grading has another actor (the setting, any institution) and another status, so a module of its
  own keeps each one's check order readable.
- **Saving one grade per request**: the milestone saves the sheet at once (FR-024).

---

## R4. Cleaning a grade: digits only, trimmed, 0 to 10, empty allowed

**Decision** ([contracts/services.md](./contracts/services.md) §`app/schemas/grade.py`):

- **`clean_grade(raw: str) -> int | None`**: `raw.strip()`; empty → `None` (not graded); otherwise
  it must be ASCII digits only (`isascii() and isdigit()`), at most 3 characters, and its value
  0–10; `"07"` is 7. Anything else raises `InvalidGrade` with the message `GRADE_ERROR = "Enter a
  whole number from 0 to 10."`.
- **The field is a text field**, `type="text"` with `inputmode="numeric"`, `autocomplete="off"`, no
  `pattern`, no `maxlength`, no `min`/`max`.

**Rationale**:

- **The spec's examples** (FR-025): "0", "7", "10" and " 7 " pass; "7.5", "-1", "11", "seven", "+7",
  "7.0", "1e1" and other-script digits ("٧", which `isdigit()` alone accepts) fail.
- **The length cap before `int()`** keeps a very long digit string from reaching Python's integer
  parser; any value with more than 3 characters is outside 0–10 anyway.
- **Not `type="number"`**: a browser sends an empty string for a number field holding "seven" or
  "7.5" in some locales, which would empty a grade silently instead of showing the error, and the
  page could not show "every entered value kept". Steppers and wheel scrolling would also change
  grades by accident. `inputmode="numeric"` still opens the digit keypad on a phone.
- **No `pattern`**: the browser would block the form with its own message instead of the error
  summary of the guidelines; the server is the guarantee either way.

**Alternatives considered**:

- **Accepting "7.0" or "+7"**: the milestone says "digits only".
- **A select of 0–10 per answer**: no "type over" correction, eleven options per question, and the
  milestone describes a field with a placeholder.

---

## R5. Counting Answered, Graded and Score in one grouped query

**Decision** ([contracts/services.md](./contracts/services.md) §`grades`):

- **`grade_counts(session, competition_id) -> dict[team_id, GradeCount]`**, `GradeCount(answered,
  graded, score)`: one `SELECT team_id, COUNT(*), COUNT(grade), COALESCE(SUM(grade), 0) FROM
  team_answers WHERE competition_id = :id GROUP BY team_id`. A team with no row reads as `(0, 0,
  0)`.
- **`GradeCount.fully_graded`** is `graded == answered`, so a team with no answers is graded
  (FR-015).
- **The overall progress** counts `fully_graded` over all the competition's teams (`team_entries`),
  whatever the filter or page.
- **The Answers page of a finished competition** uses the same counts for its listed teams
  (FR-037); 12.3's `count_answered` stays for the **In progress** page.

**Rationale**:

- **The filter needs every team's counts anyway**: **Ungraded only** and the overall progress look
  at all the competition's teams, not only the page's ten, so one query for the whole competition
  is both the simplest and the cheapest (a competition holds tens of teams).
- **Counted, never stored** (FR-018, FR-029, constitution Principle VII).
- **`COUNT(grade)` skips `NULL`** on both engines, and `SUM` over `SMALLINT` returns an integer on
  both; `COALESCE` turns a team with no grade into 0.

**Alternatives considered**:

- **Counting only the page's teams, as 12.3 does**: the filter and the overall progress would need
  a second pass anyway.

---

## R6. The Grades page: every team, the 12.2 grouping, a filter in the address

**Decision** ([contracts/http-routes.md](./contracts/http-routes.md) §1):

- **The teams**: `competition_entries.team_entries` unfiltered (deleted teams and deactivated
  institutions and regions included, FR-016), then, for **Ungraded only**, the teams whose
  `GradeCount` has `graded < answered`; grouped and paged by `competition_entries.group_by_region`,
  whose region totals count only the entries it is given (FR-017).
- **The rows** (`GradeTeamRow`): name, institution, active members (`teams.count_active_members`
  for the page's teams), `is_deleted`, answered, questions, graded, score.
- **The filter in the address**: `show=ungraded` for **Ungraded only**; absent (or any other value)
  for **All teams** (spec Assumptions). It travels with `p` through the page navigation and every
  back link.
- **The back link of a grading sheet** (FR-020): to the Grades page at `back` (its page) and `show`,
  anchored at the team only if the team is still listed under that filter
  (`grades.is_listed`); otherwise the same page without an anchor. `Paging.build` clamps a page
  beyond the last to the last, and an empty list shows "All teams are graded", so the three
  landings of FR-020 need no code of their own.

**Rationale**:

- **Reusing `team_entries` and `group_by_region`** gives the Teams page's order, region headers and
  counts, paging and phone layout for free, as 12.3 did.
- **A parameter that names the non-default filter** keeps the default address clean and the
  12.1–12.3 rule that an unknown value falls back to the default.

**Alternatives considered**:

- **A `filter=all|ungraded` pair**: the default would appear in addresses for nothing.
- **Recomputing the landing like `paging.landing_index`**: the grading sheet does not remove the
  team itself; the clamp already gives the spec's three landings.

---

## R7. Read access on the Competitions tab: one sheet address, two renderings

**Decision** ([contracts/http-routes.md](./contracts/http-routes.md) §4–§5):

- **The 12.3 address `GET /answers/{team_id}` stays the one address of a team's answers.** It
  renders the **answer sheet** (editable) for a team of a **Write** institution while the
  competition is **In progress**, and the **read-only sheet** otherwise: a **Read** institution's
  team while **In progress** (with the access notice, no grades), and any reachable team of a
  **Finished** competition (with its grades and score). **View answers** and **Enter answers** both
  link there.
- **`team_answers.answer_sheet`** no longer raises for **Read** access: it returns the sheet with
  `can_write`, and on a **Finished** competition each question's grade and the team's
  `GradeCount`. `NotReachable` still raises `AnswersDenied` (FR-035).
- **The team answers page** (`answer_team_page`): every row gets an action, **Enter answers** for
  `can_write` while **In progress**, **View answers** otherwise; on a **Finished** competition each
  row also carries `graded` and `score` (R5). The "Read access" row note is gone.
- **The 12.3 save is unchanged**: **Read** access still raises `AnswersDenied` under lock (403),
  and a **Finished** competition still gets the 12.3 refusal (FR-034, FR-040).

**Rationale**:

- **The spec's check order for the Answers pages** (FR-041) is exactly this: the status opens the
  pages on **In progress** and **Finished**, then the team, then the access decides between the
  answer sheet and the read-only sheet. One address keeps every 12.3 link, bookmark and test path
  valid, and the 12.3 refusal path for **Upcoming** and **Cancelled** unchanged.
- **The reference answer never reaches this sheet** (FR-038): `answer_sheet` does not read it.
- **Can manage competitions gives nothing here** (FR-003): the access step is still
  `reach_institution`, whatever the setting.

**Alternatives considered**:

- **A separate `/answers/{team_id}/view` address**: two addresses for one team's answers, and a
  typed sheet address of a **Read** team would still need an answer (403 or a redirect).

---

## R8. The routes: finishing in the 12.1 router, grading in a new router

**Decision** ([contracts/http-routes.md](./contracts/http-routes.md)):

- **`app/routers/teacher_competitions.py`** gains `GET /{id}/finish` (the confirmation) and
  `POST /{id}/finish`, mirroring the cancel pair: `require_manage` first, the subject, the
  competition, the status (`FINISH_REFUSALS`), then the service; the notice `finished`
  ("Competition “{name}” was finished") joins `NOTICES`; the redirect lands with the 12.1
  `list_path(…, landing.page, landing.competition_id, notice)`.
- **`app/routers/teacher_grades.py`** (new), under `/teacher/competitions/{competition_id:int}`:
  `GET /grades`, `GET /grades/{team_id:int}`, `POST /grades/{team_id:int}`. Each starts with
  `require_manage` (before any value is parsed), then the 12.2 `find_context`, then the status
  (`GRADE_REFUSALS`, 409), then the team and the questions (404), then the grades (400). It reuses
  the 12.2 `ListContext`, `address`, `page_prefix`, `render_competition_page` and the 12.3
  `_back_page`.
- **The form** (FR-024): one field per answered question, `grade-<copy id>`, read through a
  generalised form dependency (R9).

**Rationale**:

- **Finishing is a change of the competition itself**, as cancelling and editing are, so it belongs
  with them and shares their notice, landing and refusal code.
- **Grading is a page family of its own** with its own check (the setting) and status (**Finished**),
  as the 12.3 answers are; a router per family keeps each module's check order in one docstring.

**Alternatives considered**:

- **Grading routes in `teacher_team_answers.py`**: that router has no setting check by design (12.3
  FR-002); mixing the two would make its order of checks conditional.

---

## R9. The form fields: one prefix-aware dependency for answers and grades

**Decision**: `teacher_team_answers.answer_fields` becomes the generic `prefixed_fields(prefix)`
(returning every `(name, value)` pair whose name starts with `prefix`, repeated names included),
with `AnswerFields` and `GradeFields` as its two `Annotated` uses; `_parse_answers` becomes
`parse_prefixed(fields, prefix)` and serves both. A name whose suffix is not an id, or names a
question twice, is "Question not found" (404) for grades too.

**Rationale**: the 12.3 rule (research R9 there: never a `dict`, so a repeated field is refused
rather than collapsed) applies unchanged; one implementation keeps both forms honest.

**Alternatives considered**: a copy of the 12.3 functions in the new router.

---

## R10. Deactivated subjects: already handled by visibility

**Decision**: no change in `competitions._is_visible` (a competition of an active subject, or a
finished one): a finished competition of a deactivated subject is found by `find_context` and
`lock_competition`, so its Answers pages, Grades page, grading sheets and saves work (FR-042). The
menu must offer **Grades** with `can_manage` (the setting) and not the list's `can_add` (the setting
**and** an active subject), which gates **Edit** and **Cancel competition** (R12).

**Rationale**: milestone 12.1 built visibility for exactly this case; 12.3 refused the finished
competition by status, which this milestone lifts for the read-only pages.

---

## R11. The notices and the refusals

**Decision**:

- **Finish**: the 12.1 sealed list notice with the new outcome `finished`.
- **Grades saved**: a sealed, 10-minute token, purpose `grades-notice`, payload `{"competition":
  id, "team": id, "outcome": "saved"}`, read when the sheet is shown: "Grades of “{team}” were
  saved", the team named as stored (as 12.3 R12).
- **Finish refusals** (409, the 12.1 `_refused`): question "Finish competition “{name}”?", reasons
  by status: **Upcoming** "“{name}” has not started yet and cannot be finished.", **Cancelled**
  "“{name}” has been cancelled and cannot be finished.", **Finished** "“{name}” has already
  finished.".
- **Grading refusals** (409, `pages/teacher/competition_refused.html`): question "Grade answers of
  “{name}”?", reasons: **Upcoming** "“{name}” has not started yet, so its answers cannot be
  graded.", **In progress** "“{name}” is still in progress, so its answers cannot be graded until it
  is finished.", **Cancelled** "“{name}” has been cancelled, so its answers cannot be graded.";
  **Back to competitions** to the list, at the competition.

**Rationale**: the 12.1–12.3 patterns: no name in an address or a log, the text built when shown.

---

## R12. The menu

**Decision** (`pages/teacher/competitions.html`): in this order, **Edit** (`can_add` and
upcoming), **Questions**, **Teams**, **Answers** (in progress or finished, every teacher),
**Grades** (`can_manage` and finished), **Finish competition** (`can_manage` and in progress, not
destructive), **Cancel competition** (`can_add` and upcoming or in progress, destructive).

**Rationale**: FR-004–FR-006 and R10. An in-progress competition is always of an active subject
(otherwise it is hidden), so `can_manage` and `can_add` agree for **Finish competition**; the
template uses `can_manage` to say what it means.

---

## R13. Three new patterns, written first

**Decision** ([contracts/components.md](./contracts/components.md)):

- **The non-destructive confirmation**: `confirmation(…, kind="destructive")` gains the `kind`
  argument (`"destructive"` or `"primary"`), passed to its `post_button`. Every existing call keeps
  the default.
- **The grading sheet**: `components/grading_sheet.html`, `grading_sheet(items, action, hidden,
  submit_label="Save grades")` and `answers_read_only(items, grades)`: numbered text cards in an
  `<ol class="answer-sheet">`, the question, the reference answer (grading only) and the answer as
  `text_box`es, then the grade field (`field`, `inputmode="numeric"`, the hint and the "Not graded"
  placeholder) or the grade as text, or "Not answered" with no field. The form and **Save grades**
  appear only when at least one item is answered.
- **The filter links**: `components/filter.html`, `filter_links(links, label)`, a `<nav>` with a
  plain list of links, the current one `aria-current="true"`, drawn with the page navigation's
  current-page tokens.
- **Gallery** sections and **UI guidelines** entries for each, before any page uses them; the
  guideline changes of FR-047 in the same change.

**Rationale**: the project rule that pages use only library components (milestone 10), and the
spec's FR-048. `aria-current="true"` and not `"page"`, because the link on page 3 of a filter leads
to page 1 (the milestone's own reasoning).

**Alternatives considered**:

- **Extending `answer_sheet`** with grading flags: its contract (12.3) is "Never a reference
  answer"; the grading sheet always shows it, so a separate macro keeps both promises simple.
- **A `<select>` filter with a **Show** button**: the milestone asks for links that need no
  JavaScript and no button.

---

## R14. Documents

**Decision**: the constitution v2.3.0 and the product requirements already state the rules
(FR-050), so no amendment. `docs/requirements/ui-guidelines.md` gets the three patterns and the
changes of FR-047 in this PR; the README gets "finishing and grading" in its feature list;
`milestones.md` moves 12.4 to Delivered on delivery (as 12.3 did).

---

## R15. Test plan

**New modules**:

- `tests/unit/test_grade_schemas.py`: `clean_grade` on every value of FR-025 and the Assumptions
  ("0", "10", " 7 ", "07", "", "   " → `None`; "7.5", "-1", "11", "seven", "+7", "7.0", "1e1", "٧",
  "1000000" → error).
- `tests/integration/test_grade_service.py`: `finish_competition` (status, landing per filter,
  refusals, start passing, name free again); `save_grades` (store, change, empty, omit, the check
  order, deleted and deactivated teams found, unanswered or foreign question refused, setting taken
  away, nothing stored on any refusal); `grade_counts`; the PostgreSQL-only concurrency cases (two
  finishes, finish and cancel, finish during an answer save, two grade saves of one team).
- `tests/integration/test_teacher_grades.py`: the Grades page (listing, columns, overall progress,
  filters, region counts, paging, empty states, back links and landings), the grading sheet and
  its saves, invalid grades, refusals, not found, access denied, the cross-site check, deactivated
  subject.

**Updated modules**:

- `test_teacher_competitions.py`: the menu per status and setting (item 1), the finish
  confirmation, finish and landings (item 2), the finish refusals (item 3).
- `test_teacher_team_answers.py`: **View answers** for **Read** while **In progress** (item 6), the
  read-only sheet and the Answers page of a finished competition (item 5), saves after finishing
  (item 4); the 12.3 cases this milestone changes (SC-011) are replaced, not kept.
- `test_competition_service.py`, `test_team_answer_service.py`: `answer_sheet` with **Read** access
  and grades.
- `test_routes.py` (two new write routes, the new read routes in the teacher sweeps),
  `test_migrations.py` (the new revision), `test_form_contract.py` + `form_contract.json` (new
  `teacher-competition-finish*` and `teacher-grades*` cases, generated once for those cases only),
  `test_component_gallery.py`, `test_page_patterns.py`, `tests/conftest.py` (a `grade_answer`
  seeder; `make_competition(stopped=True)` exists).

**Browser checks** by hand or with an ad hoc Playwright run ([quickstart.md](./quickstart.md) §4):
the grading sheet at 360 px, the numeric keypad, the filter links in both themes, the busy button.

**Mapping**: each acceptance scenario of US1–US14 and each milestone _Test:_ item 1–17 has at least
one test in the modules above; item 17 is `test_component_gallery.py`.
