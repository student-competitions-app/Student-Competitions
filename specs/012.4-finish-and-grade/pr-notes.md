# PR notes: Finishing a competition and grading its answers by hand (teacher), milestone 12.4

For the PR description. The spec, plan and contracts are in this folder.

## What changed

- **Finishing.** A teacher with **Can manage competitions** gets **Finish competition** on every
  **In progress** row (not destructive), a confirmation with a primary button and **Keep in
  progress**, and lands where the competition was in the filtered list with "Competition “…” was
  finished". `competitions.finish_competition` mirrors the cancel: the setting under lock, the
  competition `FOR UPDATE`, the status with a fresh clock, a conditional update of `stopped_at`
  (`cancelled_at IS NULL AND stopped_at IS NULL AND starts_at <= now`). Refusals: "has not started
  yet and cannot be finished.", "has been cancelled and cannot be finished.", "has already
  finished." No schema change for finishing.
- **Grading.** On a **Finished** row the setting gives **Grades**: "Grades of “…”"
  (`/teacher/competitions/{id}/grades`), every team of the competition whatever the teacher's
  links (deleted ones marked "(deleted)", deactivated institutions and regions included), in region
  boxes, 10 per page, with **Answered**, **Graded**, **Score**, "Graded n of m teams", and the
  filter links **All teams** / **Ungraded only** (`show=ungraded`). **Grade answers** opens the
  grading sheet (`…/grades/{team_id}`): every question with its reference answer and the team's
  answer, a grade field (text, `inputmode="numeric"`, "Not graded") under each answered question,
  **Save grades**. Invalid grades → 400 with every value kept. The last save wins (the team's link
  row `FOR UPDATE`); nothing stores who graded or when. New router `teacher_grades.py`, service
  `grades.py`, schema `grade.py`.
- **Answers pages (12.3, changed).** **Read** access now opens a team's sheet read-only with the
  notice "You have Read access to “…”, so you cannot change these answers." (**View answers**
  replaces the "Read access" row note); only **Write** saves. On a **Finished** competition the
  Answers pages open (read-only) with **Graded** and **Score** columns, and the sheet shows "Score:
  17", "Graded 3 of 4 answers", "Grade: 7 of 10" / "Not graded yet"; a save is still refused with
  the 12.3 reason. Never the reference answer there.
- **One migration** (`04d5b638615c`): `team_answers.grade SMALLINT NULL` with
  `ck_team_answers_grade_range` (0–10), through batch mode. No data step.
- **Components first**: `confirmation(…, kind="primary")`; `components/grading_sheet.html`
  (`grading_sheet`, `answers_read_only`); `components/filter.html` (`filter_links`,
  `aria-current="true"`), with `.grade-line` and `.filter-links` CSS (tokens only), gallery
  sections `#grading-sheet`, `#filter-links` and a second `#confirmations` sample, and the
  `ui-guidelines.md` changes of FR-047 (confirmations, the destructive button kind, the menu order,
  wording).
- **Shared helpers**: `team_answers._question_copies` moved to
  `competition_entries.question_copies` (imports run `team_answers` → `grades` →
  `competition_entries`); `teacher_team_answers.answer_fields` generalised to
  `prefixed_fields(prefix)` / `parse_prefixed`, `_back_page` made public as `back_page`; the 12.2
  `address` gained `show`.
- **Documents**: the UI guidelines, the README, `milestones.md` (12.4 moved to Delivered).

## Replaced and updated tests (SC-011)

Each replaced assertion names milestone 12.4 in its docstring or comment.

- `test_teacher_competitions.py`: `test_a_started_competition_is_in_progress` (adds **Finish
  competition**), `test_cancelled_and_finished_competitions_cannot_be_edited` and
  `test_a_deactivated_subject_lists_only_its_finished_competitions` (a finished row adds
  **Answers** and **Grades**), `test_every_teacher_gets_answers_on_an_in_progress_row` (also the
  finished row); the sweep gains the finish pair (9/8 routes) and leaves the grades routes to
  `test_teacher_grades.py`.
- `test_teacher_competition_entries.py`: `test_the_menu_entries_per_status_and_setting` and
  `test_a_deactivated_subject` (finished rows gain **Answers**, and **Grades** with the setting).
- `test_team_answer_service.py`: `test_no_write_access_is_denied` (Read no longer gets
  `AnswersDenied` on the sheet).
- `test_teacher_team_answers.py`: the "Read access" row notes become **View answers**
  (`test_the_team_answers_page`, `test_twelve_teams_in_two_regions_across_two_pages`,
  `test_a_link_lowered_or_removed_while_the_sheet_is_open`);
  `test_read_access_shows_the_progress_and_never_the_answers` now expects the read-only sheet;
  `test_both_pages_and_the_save_refuse_a_competition_not_in_progress` loses its **Finished** case
  (covered by `test_a_save_after_the_finish_is_refused`).
- `test_migrations.py`: the 12.3 head test becomes `…_follows_the_competition_entries_revision`,
  and the 12.3 table test upgrades to its own revision; new 12.4 head, column, range and downgrade
  tests.
- `test_component_gallery.py`: the actions-menu example lists **Grades** and **Finish
  competition**; new section checks.
- `test_routes.py`: two new writes; the three new pages in `MANAGE_PATHS`.
- `form_contract.json`: five new cases (`teacher-competition-finish`, `teacher-grades`,
  `teacher-grades-sheet`, `-invalid`, `teacher-team-answers-read-only`; a grade field is recorded
  as `grade-{id}`). No existing case changed.

## Browser checks (T056, quickstart §2–§5)

**Migration (§2)**, on a copy of the local database: downgrade to `b709653d1111` (no `grade`
column), upgrade, `downgrade -1`, upgrade. `team_answers` has `grade SMALLINT` (nullable) and the
`ck_team_answers_grade_range` check; nothing else changed.

**The browser run (§3–§5)**: an ad hoc Playwright script (`uv run --no-project --with playwright`,
headless Chromium 1248 from the local cache) on port 8765, against a scratch SQLite database seeded
with Olena (the setting, linked only to a district office), Taras (Write to two Kyiv institutions,
Read to a Lviv one), a 130-character competition name, a 113-character team name, a 140-character
institution name, four questions (one long, one with an unbroken word, long reference answers), a
team with no answers and a deleted team; sessions created directly.

- **Menu**: as Olena, the In progress row reads **Questions**, **Teams**, **Answers**, **Finish
  competition**, **Cancel competition**, with only **Cancel competition** in the danger colour, in
  Light and Dark; after finishing, **Questions**, **Teams**, **Answers**, **Grades**. As Taras,
  **Questions**, **Teams**, **Answers**.
- **No sideways scroll** (`scrollWidth − innerWidth = 0`) at 1280 and 360 px on the Answers page
  and read-only sheet (in progress and finished), the finish confirmation, the Grades page (both
  filters, Light and Dark), the grading sheet, its 400 page, a team with no answers, and the
  gallery.
- **Phone**: the Grades table is labelled cards ("Answered", "Graded", "Score"); the grade field
  takes the card's width (278 of 328 px with the card's padding) and is 120 px wide on a wide
  screen; `type="text"`, `inputmode="numeric"`, `autocomplete="off"`, placeholder "Not graded".
- **Filter links**: the current link has the current page's primary underline and bold weight
  (`rgb(31, 86, 214)` / 700 in Light, `rgb(108, 156, 255)` / 700 in Dark, the same as the page
  navigation's current page).
- **Invalid grades** ("7.5", "11"): the summary with both errors, each field marked, every value
  kept ("7.5", "11", "6").
- **Busy buttons**: with the POST held 1.5 s, **Finish competition** and **Save grades** report
  `aria-busy="true"` (MutationObserver); the next pages show the list and the sheet with the
  notice.
- **After finishing**, as Taras: the Answers page has **Graded** and **Score** and only **View
  answers**; the sheet shows "Score: 17", "Grade: 7 of 10", "Not answered", and no reference
  answer.
- **JavaScript off**: the filter links work (`show=ungraded`), and a grade save shows "Grades of
  “Comets” were saved".
- **Gallery** (`#confirmations`, `#grading-sheet`, `#filter-links`, `#actions-menu`) at both widths.

**Observation, not fixed**: as on the 12.2 **Teams** and 12.3 **Answers** pages, the short column
headers ("Active members", "Answered", "Graded", "Score") break inside a word beside very long team
and institution names on a wide screen (`overflow-wrap: anywhere`, the shared table rule of
milestone 10).

## Things to know

- **The clock**: `app.services.grades` reads it through `app.services.competitions.utc_now`, so
  the 12.1 clock patch moves it too.
- **Concurrency tests** run on PostgreSQL only: two finishes, a finish and a cancel, a finish
  waiting for an answer save's share lock, two grade saves of one team (never a mix), and saves of
  two teams not waiting for each other.
- **`grade_answer`** (`tests/conftest.py`) sets a grade directly, skipping the checks
  `test_grade_service.py` covers.
- **A teacher needs at least one institution link** to be invited, so the tests' grader with "no
  links" is linked (Read) to an institution with no team in the competition.
- **The `12. Competitions (12.x)` group paragraph** stays under **Upcoming** in `milestones.md`;
  every 12.x milestone is now delivered, so the product owner may want to move or retire it.
