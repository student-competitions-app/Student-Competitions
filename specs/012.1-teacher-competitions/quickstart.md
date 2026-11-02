# Quickstart: Creating, Editing and Cancelling Competitions (Teacher) (Milestone 12.1)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **The addresses, the page contents and the wording**:
  [contracts/http-routes.md](./contracts/http-routes.md).
- **The services and the time-zone helpers**: [contracts/services.md](./contracts/services.md).
- **The components and the script**: [contracts/components.md](./contracts/components.md).
- **The table and the migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`.
- For the PostgreSQL cases, the local container (`sc-pg`) running and `TEST_POSTGRES_URL` set (see
  the README).
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–11.1.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_competition_schemas.py tests/unit/test_time_zone.py \
              tests/unit/test_time_zone_script.py tests/unit/test_stylesheet.py
uv run pytest tests/integration/test_competition_service.py \
              tests/integration/test_teacher_competitions.py
uv run pytest tests/integration/test_migrations.py tests/integration/test_routes.py \
              tests/integration/test_teacher_access.py tests/integration/test_admin_subjects.py \
              tests/integration/test_subject_service.py tests/integration/test_layout.py \
              tests/integration/test_form_contract.py tests/integration/test_component_gallery.py \
              tests/integration/test_page_patterns.py
uv run pytest                                   # the whole suite (SC-010)
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from spec scenarios to tests is in [research.md](./research.md) R16.

## 2. Upgrade a database from milestone 11.1

```bash
cp data/app.db /tmp/before-m12-1.db        # or any database at revision 09cbcbe472be
uv run alembic upgrade head
```

**Check**:

- `competitions` exists and is empty, with `uq_competitions_subject_name_live` and
  `ck_competitions_one_end`.
- `uv run alembic downgrade 09cbcbe472be` drops it, and `upgrade head` creates it again.

## 3. The time-zone database in the image

```bash
docker build -t student-competitions:local .
docker run --rm --entrypoint python student-competitions:local \
  -c "import zoneinfo; print(zoneinfo.ZoneInfo('Europe/Kyiv'))"
```

**Expected**: `Europe/Kyiv`. The CI `image` job runs the same check (research R4).

## 4. Run the application and walk through the tab

```bash
uv run uvicorn app.main:app --reload
```

Use a browser whose time zone is `Europe/Kyiv` (on Chrome: DevTools → More tools → Sensors →
**Timezone ID** `Europe/Kyiv`, or start the browser with `TZ=Europe/Kyiv`).

**As an administrator**: create the subjects "Chemistry" and "Physics"; invite teacher A with **Can
manage competitions** and teacher B without it; accept both.

**As teacher A** (US1–US6, US8):

1. **The tab**: **Competitions** opens `/teacher/competitions`, "Select a subject" with its hint.
   After any page has loaded, the browser has the cookie `sc_time_zone=Europe/Kyiv`.
2. **Create**: choose "Chemistry" (no button needed), see "No competitions yet" with its hint,
   press **Add competition**. The form says "Time zone: Europe/Kyiv". Enter "Spring round", a date
   a few days ahead and 10:00, and save. You land on the list, status **All**, at the row, with
   "Competition “Spring round” was added"; the row shows the date, "10:00" and **Upcoming**. In the
   database, `starts_at` is two or three hours earlier (UTC).
3. **Validation**: try an empty name, 201 characters, "spring ROUND" (duplicate), a past date, the
   current minute, and 28 March 2027 03:30 (gap message). Then try "Spring round" in "Physics":
   accepted. Try 31 October 2027 03:30: stored as 00:30 UTC (the earlier moment).
4. **Order and pages**: create competitions on 15 March, 1 March and 25 March 2027; they list as
   25, 15, 1 March. With 25 competitions there are three pages, "Competitions 11–20 of 25" on the
   second, and the navigation above and below.
5. **Edit**: open **Actions** on an upcoming row ("Actions for “…”" to a screen reader), choose
   **Edit**, move the start to another page's range and rename it; you land on the page that now
   holds it, at it, with "… was saved". **Cancel** on the form returns you to where you came from.
6. **Start passing**: create a competition starting in two minutes, wait, reload: **In progress**,
   and its menu offers only **Cancel competition**. Open its old edit address: the refusal "…has
   already started and can no longer be edited." with **Back to competitions**.
7. **Cancel**: cancel an upcoming and the in-progress one. The confirmation names the competition,
   "Chemistry" and the start in Kyiv time, and offers **Cancel competition** and **Keep
   competition**. After cancelling: **Cancelled**, no menu, the notice. Under the **Upcoming**
   filter, cancelling lands at the row that took its place. Send the cancel form again (Back, then
   submit): "…is already cancelled.". Create a new "Spring round": accepted.
8. **Status filter**: each status shows only its rows and is kept across pages; a status with no
   rows shows "No competitions with this status".

**As teacher B** (US2, US7): the list shows the same competitions, with no **Add competition** and
no menus. Typing `/teacher/competitions/new?subject=<id>`, an edit address or a cancel address
gives "access denied".

**As an administrator and as a student**: `/teacher/competitions` gives "access denied".

**Deactivated subject** (US9): store a finished competition directly
(`UPDATE competitions SET stopped_at = CURRENT_TIMESTAMP WHERE id = <id>` on an in-progress one),
then deactivate "Chemistry". As teacher A: "Chemistry" is under "Deactivated subjects"; only the
finished competition is listed, with no **Add competition** and no menus; the other competitions'
addresses give "Competition not found". Deleting "Chemistry" as an administrator is refused as in
use. Activate it again: everything is back, and an upcoming one whose start passed meanwhile shows
**In progress**.

## 5. Without JavaScript, and the menu in a browser

Turn JavaScript off and remove the `sc_time_zone` cookie.

- Every start shows as "… UTC"; the form says "Time zone: UTC" and reads entries in UTC.
- The subject and status lists show **Show** buttons and work.
- The actions menu opens and closes (it is a `<details>`); its entries are links that work.

With JavaScript on, in a browser (by hand, or an ad hoc Playwright run as in milestone 10.1:
`uv run --with playwright`, a copy of the database, port 8765):

- the cookie appears after the first page; changing the emulated zone changes it on the next page;
- opening one row's menu closes another (where the browser supports `details[name]`);
- the menu is reachable with Tab, opens with Enter or Space, and its entries are 44 px tall;
- an open menu on the last row of the table is not clipped.

## 6. Phone width and themes

At 360 px and 375 px width, in Light and Dark:

- the table becomes cards; the **Actions** button sits in the card's actions part and its panel
  stays inside the screen;
- the date and time fields stack, each with its label, the hint under the time;
- a 200-character competition name wraps in the card, the menu's accessible label, the
  confirmation and the notice, with no sideways scroll (SC-008).

## 7. The component gallery

Open `/admin/components` outside production:

- `#actions-menu`: closed, open, destructive entry, inside a table row;
- `#forms`: the date and time pair, empty, filled, with errors;
- `#badges`: **Upcoming**, **In progress**, **Finished**, **Cancelled**;
- `#time`: the same moment with a zone and with "UTC";
- `#confirmations`: a confirmation with **Keep competition**;
- `#selectors`: a list with the group "Deactivated subjects".

Check that each is described in `docs/requirements/ui-guidelines.md` (FR-048, FR-049).
