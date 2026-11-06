# PR notes: Questions and teams of a competition (teacher), milestone 12.2

For the PR description. The spec, plan and contracts are in this folder.

## What changed

- **Every competition row has an actions menu**, in this order: **Edit**, **Questions**,
  **Teams**, **Cancel competition**. Every teacher gets **Questions** and **Teams** on every row,
  in every status. **Edit** and **Cancel competition** keep their 12.1 rules.
- **Two new pages per competition**, "Questions of “…”" and "Teams of “…”"
  (`/teacher/competitions/{id}/questions`, `…/teams`). Every teacher reads them. They show the
  subject, the start and the status, and a back link to the exact competitions list the teacher
  came from.
- **Questions are copied** into the competition when added. A bank edit or deletion changes
  nothing; a copy whose bank question was deleted is marked "Deleted from the question bank".
- **Teams are linked, not copied**, and listed in region boxes ("Kyiv · 14 teams"), 10 teams per
  page. A region that continues on the next page repeats its header with the same total.
- **Changing them** needs **Can manage competitions** and an **Upcoming** competition:
  - "Add questions" lists the subject's bank questions;
  - "Add teams" offers a **Region** list, then that region's live teams of active institutions,
    from every institution, linked to the teacher or not;
  - **Remove** asks for a confirmation.

  Every write locks the competition and re-checks the status. Adding twice stores once; removing
  twice changes nothing.
- **Deleting a team** (Teams tab) now also takes it out of every competition that has not finished.
  Finished competitions keep it, marked "(deleted)". The 11.1 confirmation says so.
- **One migration** (`59c636929942`) creates `competition_questions` (the copies; the `id` is the
  order of adding) and `competition_teams` (the links). No `ON DELETE` cascades.
- **Components first**: the new `region_group` (`components/group.html`) is in the library, the
  gallery (`#region-group`) and `ui-guidelines.md`. The guidelines' "Menus" and "Row notes"
  wording changed. The refusal page takes its link texts from the route.
- **Documents**: the product requirements ("Competition statuses", "Question", "Team"), the UI
  guidelines, the README, and `milestones.md` (12.2 moved to Delivered).

## Replaced and updated tests (SC-009)

- `test_teacher_competitions.py`: the 12.1 assertions that expected no menu now expect the
  read-only **Questions** and **Teams** menu. Each one carries a comment naming milestone 12.2
  FR-002:
  - `test_without_the_setting_no_add_and_no_menus` is renamed `…_no_add_and_read_only_menus`;
  - the cancelled rows, the In progress menu, the finished and cancelled rows, and the
    deactivated-subject list.

  Its route sweep now leaves out the 12.2 routes. `test_teacher_competition_entries.py` sweeps
  them with their own order of checks.
- `test_teacher_teams.py`: the delete confirmation's new first sentence (FR-041).
- `test_team_service.py`, `test_teacher_teams.py`: the log line is now
  `Team deleted: id=… members=… competitions=…`.
- `test_migrations.py`: `test_the_head_is_the_competitions_revision` is replaced by
  `test_the_head_is_the_competition_entries_revision`.
- `test_component_gallery.py`: the actions-menu section now shows the four-entry menu and the
  two-entry read-only one. The 12.1 row with no menu is gone, since a competition row always has a
  menu now; the unit test of an empty menu stays.
- `test_routes.py`: four new writes, four new `MANAGE_PATHS`, and `ENTRY_READ_PATHS` for the two
  lists every teacher reads.
- `form_contract.json`: seven new `teacher-competition-questions*`, `-teams*` and `-entry-*`
  cases. No existing case changed.

## Browser checks (T067, quickstart §2–§5)

**Migration (§2)**, on a copy of the local database:

- downgraded to `72e46cb10175`, then upgrade, `downgrade -1` and upgrade again;
- both tables exist and are empty, with the unique constraint, the primary key and the `team_id`
  index.

**The browser run (§3–§5)**:

- An ad hoc Playwright script (`uv run --no-project --with playwright`, Chromium) on port 8765.
- The scratch database was seeded with:
  - two real teachers;
  - 25 questions;
  - 26 teams in four regions, one region with a 200-character name, one team with a long name;
  - a finished competition with a deleted team.
- 78 checks passed. The one failure was the script's own: it did not wait for the navigation. A
  rerun passed. The screenshots are in the git-ignored `screenshots/012.2/`.

What passed:

- **No sideways scroll** at 1280, 375 and 360 px, in Light and Dark, on every page:
  - both lists, pages 1–3 of the teams;
  - both add pages;
  - the team remove confirmation;
  - the refusal (409);
  - the competitions list;
  - the gallery's `#region-group`.
- **Phone**: below 768 px the rows of every region group are labelled cards inside the box. The
  200-character region header wraps inside it.
- **Without JavaScript**, the **Region** list shows **Show**. Choosing Kyiv and pressing it opens
  the region's first page, with no `p` and ten teams.
- **With JavaScript**, choosing a region opens it at once, with no **Show** button.
- **Keyboard**: Enter opens a row's menu. Tab reaches **Edit**, **Questions**, **Teams** and
  **Cancel competition** in order, and Enter on **Questions** opens "Questions of “Spring round”".
- **Reload**: after **Add**, reloading the result twice changes nothing.

**Observations, not fixed**:

- **A 200-character team name** in a desktop data table leaves the narrow columns little room.
  Their headers then break inside a word ("Educationa l institution"), as any `data-table` does
  with a very long value (`overflow-wrap: anywhere`, milestone 10). The shared table rule is left
  as it is.
- **The region header's padding** is the table cell's (`--sc-space-2`), not the card's
  (`--sc-space-3`), so the header lines up with the cells below it.

## Things to know

- **The clock**: `app.services.competition_entries` reads it through
  `app.services.competitions.utc_now`, so the 12.1 clock patch moves both.
- **Concurrency tests** (two sessions with a `threading.Barrier`) run on PostgreSQL only:
  - two additions, and two removals, at once;
  - an addition racing a cancellation, a bank deletion or a bank edit;
  - a team deletion racing its addition.
- **`add_competition_question` and `add_competition_team`** (`tests/conftest.py`) are the only
  way to give a cancelled or finished competition questions and teams.
