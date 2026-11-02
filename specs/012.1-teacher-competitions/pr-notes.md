# PR notes: Creating, editing and cancelling competitions (teacher), milestone 12.1

For the PR description. The spec, plan and contracts are in this folder.

## What changed

- **The Competitions tab** (`/teacher/competitions`) is no longer a placeholder.
  - Every teacher sees a subject's competitions. A **Subject** list shows the active subjects,
    then, under "Deactivated subjects", the deactivated ones that have a finished competition. A
    **Status** list offers All, Upcoming, In progress, Finished and Cancelled.
  - The list puts the latest start first, ten per page, with page navigation above and below.
  - A teacher with **Can manage competitions** adds, edits (upcoming only) and cancels (upcoming
    or in progress) competitions. The row actions sit in a new **Actions** menu.
- **One migration** (`72e46cb10175`) creates `competitions`. It holds no status column and no
  creator.
  - Names are unique ignoring case among the live competitions of a subject, through the partial
    index `uq_competitions_subject_name_live`.
  - `ck_competitions_one_end` keeps a competition from being both cancelled and finished.
  - `stopped_at` exists so **Finished** is handled everywhere; a later 12.x milestone writes it.
- **The status is derived** (`status_of`) from the stored start, cancel and stop, with one clock
  per call. Nothing is written when a start passes.
- **Every write** checks the setting, the subject and the row again under lock, then makes a
  conditional `UPDATE`. A row count of 0 means another request won the race, and the request gets
  the matching refusal.
- **Time zones**:
  - `time-zone.js`, loaded on every page, writes the browser's IANA zone to the `sc_time_zone`
    cookie;
  - the server shows every time in that zone, or in UTC labelled "UTC";
  - a form carries the zone it was shown in and is read in it. A time the clocks skip is refused;
    a time that happens twice is the earlier one.
- **A subject with any competition** cannot be deleted (`count_subject_uses`).
- **Components first**, each in the library, the gallery and `ui-guidelines.md`:
  - new: `actions_menu` and `menu_link`, `local_time`, `date_time_fields` and
    `competition_status_badge`;
  - changed: `confirmation(back_label=…)`, option groups in `select_field` and `chained_lists`;
  - `.data-table` rounds its corner cells instead of `overflow: hidden`, so an open menu is not
    clipped.
- **CI**: the `image` job checks that the built image loads `Europe/Kyiv` (Debian `tzdata`).

## Replaced and updated tests (SC-010)

- `test_teacher_classes.py::test_competitions_is_a_placeholder` is replaced by
  `test_competitions_is_the_competitions_list`.
- `test_routes.py`: three new writes, and three new `MANAGE_PATHS`.
- `test_teacher_access.py`: the tab's management routes leave the institution sweeps (as
  Questions did), so `len(TEACHER_POSTS) == 13` still holds. `test_teacher_competitions.py`
  sweeps them instead.
- `test_admin_area.py::test_tabs_are_plain_links` pinned the page's only script; it now expects
  `loading-feedback.js` then `time-zone.js`.
- `form_contract.json`: six new `teacher-competition*` cases, generated once. No existing case
  changed.
- `specs/012.1-teacher-competitions/contracts/services.md`: its Python code block was reformatted
  by `ruff format`, which checks Markdown code blocks. Without it the format check failed.

## Browser checks (T059, quickstart §4–§7)

These ran as an ad hoc Playwright script (`uv run --no-project --with playwright`) against a
scratch database seeded with real teachers and 28 competitions, on port 8765. 53 checks passed.
The screenshots are in the git-ignored `screenshots/012.1/`.

- **The cookie**: written after the first page in Chromium, Firefox and WebKit, with `Path=/`,
  `SameSite=Lax`, not `HttpOnly`, and not `Secure` over HTTP. Changing the emulated zone to
  `America/New_York` updated it, and the next page showed New York times.
- **Without JavaScript**: no cookie, so every time is "… UTC" and the form reads "Time zone:
  UTC". The two **Show** buttons appear, the menu opens, and its **Edit** link opens the form.
- **The menu**:
  - Enter opens it and Tab reaches **Edit**;
  - the button and every entry are 44 px tall;
  - opening another row's menu closes the first (Chromium, `details[name]`);
  - the open menu of the last row on the page reaches 65 px below the table and is not clipped.
- **Phone, 360 and 375 px, Light and Dark**:
  - the list, the form and the confirmation never scroll sideways;
  - the menu takes the card's actions part, and its panel stays on screen;
  - the date and time fields stack.
- **1280 px**: the date and the time stand side by side, their inputs on one line. Filling the
  native pickers and saving landed at the new row, which read "14 March 2027, 10:00" and
  **Upcoming**.
- **Reader and deactivated subject**: a teacher without the setting gets no **Add competition**
  and no menus. A deactivated subject lists only its finished competition.
- **The gallery**: `#actions-menu` and `#forms` render at 1280 and 375 px with no sideways
  scroll.

**Fixed because of the run**:

- **"Cancel competition" wrapped onto two lines.** The absolutely positioned panel shrank to its
  `min-width`; it now has `width: max-content`, still capped at the screen width.
- **The Start column wrapped** "14 March 2027, 10:00" over three or four lines on desktop. A time
  in a data table now stays on one line (`.data-table time { white-space: nowrap }`).

**Deviations and observations**:

- **Chromium reports `Europe/Kiev`**, the database's legacy alias, where Firefox and WebKit report
  `Europe/Kyiv`. The alias is in `available_timezones()`, so it is accepted and times are right.
  The form hint then reads "Time zone: Europe/Kiev".
- **A form that is the very first page a browser loads** is shown, labelled and read in UTC,
  because the script has not run yet (spec Edge Cases). From the second page on, the browser's
  zone is used.
- **The menu is a native `<details>`**, like the user menu. Escape and a click outside do not close
  it; clicking its button again does. An open panel can cover the next row's button until it is
  closed. This was accepted in research R14, which chose no script.
- **Gallery menu variants**: the open variant is shown inside a table row rather than on its own.
  On its own, a right-aligned panel would run off the left edge of the page. `actions_menu` gained
  an `open=False` parameter that only the gallery passes, as `loading_bar(active=…)` does.
- **The actions panel's `z-index` is 2, not 5** as the user menu's is. That keeps it under the
  pinned frame (z-index 3) while the page scrolls.

## Things to know

- **Tests control the clock** with `monkeypatch.setattr("app.services.competitions.utc_now", …)`;
  no test waits.
- **`make_competition`** (in `tests/conftest.py`) is the only way to store a **Finished**
  competition until stopping exists.
- **The router pre-checks** the name and the start, so a form shows all its field errors at once.
  The service checks them again under lock, along with the duplicate name and "in the future".
