# PR notes: Entering a team's answers (teacher), milestone 12.3

For the PR description. The spec, plan and contracts are in this folder.

## What changed

- **The actions menu gains Answers** on every **In progress** row, for every teacher, in the order
  **Edit**, **Questions**, **Teams**, **Answers**, **Cancel competition**.
- **The team answers page**, "Answers of “…”" (`/teacher/competitions/{id}/answers`): only the
  competition's teams of the teacher's own reachable institutions, in region boxes like **Teams**,
  10 per page, each with its progress "3 of 6" in an **Answered** column. **Write** institutions'
  teams have **Enter answers**; **Read** ones the row note "Read access". No **Add team**, no
  **Remove**. Two empty states.
- **The answer sheet**, "Answers of “Comets” in “…”" (`…/answers/{team_id}`): every question,
  numbered, each a text card with its answer field ("Not answered" when empty, hint "Up to 2,000
  characters.", `maxlength="2000"`), never the reference answer, and one **Save answers**. A save
  redirects (303) back to the sheet with a sealed notice. An answer that is too long saves nothing
  and shows the sheet again (400) with every text as sent, the error at each field and the
  summary.
- **The rules**: the last save wins (the team's link row is locked `FOR UPDATE`, so two saves never
  mix); who saved and when are not stored; answers are entered only while **In progress**, checked
  again under the competition's new **share** lock (saves of one competition do not wait for each
  other, but a cancellation waits for them and they for it); every check runs again on each page
  and save, in the spec's order: role → subject and competition (404) → status (409) → team and
  questions (404) → **Write** access (403) → lengths (400).
- **The form reads every `answer-…` pair** (`form.multi_items()`): a field name sent twice, or two
  spellings of one id (`answer-41`, `answer-041`), is "Question not found", never collapsed to one
  value. A team id above `MAX_ID` is "Team not found" on the sheet and on the save.
- **Deleting a team** also deletes its answers in every competition that has not finished, before
  its links; finished competitions keep the team and its answers. The log line gains `answers=%d`.
  The confirmation's wording is unchanged.
- **One migration** (`b709653d1111`) creates `team_answers`: primary key `(competition_id, team_id,
  competition_question_id)`, a composite foreign key to `competition_teams`, a foreign key to
  `competition_questions`, `text <> ''`, and the `competition_question_id` index. No cascades.
- **Components first**: the **answer sheet** (`components/answer_sheet.html`), the `placeholder`
  argument of `field` and `textarea_field`, and `cell(…, nowrap=True)` (a short value on one line,
  for the progress) are in the library, the gallery (`#answer-sheet`, `#forms`, `#table`) and
  `ui-guidelines.md`, with the "Placeholders" wording rule and "Read access" among the row notes.
- **Shared helpers**: `lock_competition(share=True)`; `competition_entries.team_entries` and
  `group_by_region` (generic `RegionGroup[Row]`, a batched `make_rows`); the 12.2 router's
  `find_context`, `render_competition_page` (now with `status_code`), `address` and `page_prefix`
  made public.
- **Documents**: the UI guidelines, the README, and `milestones.md` (12.3 moved to Delivered).

## Replaced and updated tests (SC-011)

- `test_teacher_competitions.py`: the In progress menu assertions now expect **Answers**, each
  docstring naming milestone 12.3 FR-001 (`test_without_the_setting_no_add_and_read_only_menus`,
  `test_a_started_competition_is_in_progress`). Its route sweep leaves out the answer routes, which
  `test_teacher_team_answers.py` sweeps with their own order of checks.
- `test_teacher_competition_entries.py`: `test_the_menu_entries_per_status_and_setting` expects
  **Answers** on the In progress row (named in its docstring).
- `test_team_service.py`, `test_teacher_teams.py`: the log line is now
  `Team deleted: id=… members=… competitions=… answers=…`.
- `test_migrations.py`: the head test moves to `test_the_head_is_the_team_answers_revision`; the
  12.2 one keeps checking its own `down_revision`.
- `test_component_gallery.py`: the actions-menu example lists **Answers**.
- `test_routes.py`: one new write, and the two answer pages in `ENTRY_READ_PATHS`.
- `form_contract.json`: four new `teacher-team-answers*` cases (an answer field is recorded as
  `answer-{id}`). No existing case changed.

## Browser checks (T053, quickstart §2–§5)

**Migration (§2)**, on a copy of the local database: downgrade to `59c636929942`, upgrade, `downgrade
-1`, upgrade. `team_answers` exists and is empty, with its primary key, both foreign keys, the check
constraint and the index.

**The browser run (§3–§5)**: an ad hoc Playwright script (`uv run --no-project --with playwright`,
headless Chromium 1248 from the local cache) on port 8765, against a scratch SQLite database seeded
with Taras (Write to two Kyiv institutions, Read to a Lviv one), a 130-character competition name,
a 113-character team name, a 140-character institution name, six questions (one long, one with a
240-character unbroken word) and three answers (one long, one unbroken).

- **No sideways scroll** (`scrollWidth − innerWidth = 0`) at 1280 and 360 px on the team answers
  page, the sheet, the sheet in Dark, and the 400 page.
- **Phone**: the team answers page is labelled cards, "Answered 3 of 6"; the sheet is one column,
  each field at the card's full width, the button below the list.
- **The placeholder** "Not answered" sits in the empty fields under the label and hint, in Light and
  Dark.
- **The 400 page** (an answer of 2,001 characters set by script past `maxlength`): the summary under
  the heading, the error at question 4, every text kept.
- **The browser limit**: typing past 2,000 characters keeps 2,000.
- **Busy button**: with the save held 1.5 s, **Save answers** reports `aria-busy="true"` (through a
  `MutationObserver`, since Playwright waits for the navigation before reading attributes); the next
  page shows "Answers of “Comets” were saved".

**Fixed during the run**: on a wide screen, beside long names, the narrow **Answered** column broke
"3 of 6" over three lines. `cell(…, nowrap=True)` keeps it on one line (library, gallery, guidelines
first).

**Observation, not fixed**: as on the 12.2 **Teams** page, the short column headers ("Active
members", "Answered") break inside a word beside very long names (`overflow-wrap: anywhere`, the
shared table rule of milestone 10).

## Things to know

- **The clock**: `app.services.team_answers` reads it through `app.services.competitions.utc_now`,
  so the 12.1 clock patch moves it too.
- **SQLite does not enforce foreign keys here** (no `PRAGMA foreign_keys`), so the migration tests
  check the composite foreign key's refusals on PostgreSQL only; the service checks the team and the
  questions under lock on both engines.
- **Concurrency tests** run on PostgreSQL only: two share locks together and a cancellation waiting
  for them; a save racing a cancellation, a lowered or removed link, an institution's deactivation
  and a team deletion; two saves of one team at once (never a mix); saves of two teams not waiting
  for each other.
- **`save_team_answer`** (`tests/conftest.py`) is the only way to give a cancelled or finished
  competition answers.
- **Python 3.13 generics**: `RegionGroup[Row]` and `group_by_region[Row]` use the PEP 695 syntax
  (ruff's `UP` rules), not the `TypeVar`/`Generic` form the task described.
