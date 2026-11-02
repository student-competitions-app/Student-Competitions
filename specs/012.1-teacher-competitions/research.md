# Research: Creating, Editing and Cancelling Competitions (Teacher) (Milestone 12.1)

Phase 0 of [plan.md](./plan.md). The spec has no open clarifications, so each entry below records a
design decision, the reason for it and the alternatives considered.

---

## R1. One table, `competitions`, with the stored facts and no status column

**Decision**: one new table ([data-model.md](./data-model.md) §1):

- `id`, `subject_id` (required, indexed, a foreign key to `subjects`, no `ON DELETE`);
- `name` (200) and `name_key` (600), cleaned by the existing `app.schemas.names`;
- `starts_at`: required, `UTCDateTime`, always a whole minute (seconds and microseconds zero);
- `cancelled_at` and `stopped_at`: nullable `UTCDateTime`, the two stored facts that end a
  competition;
- `created_at`, `updated_at`.

`stopped_at` is created now, although no page of this milestone writes it, because the list, the
filter, the refusals and the deactivated-subject rules must already handle **Finished** (FR-008),
and tests store it directly. The milestone that adds stopping writes it and needs no migration.

- **No `created_by`**: who created a competition is neither stored nor shown (FR-001), so the table
  holds no personal data and data erasure leaves it alone.
- **No status column**: the status is derived (R2). A stored "in progress" would need a job or a
  write on read to stay true, which the milestone forbids ("with no background job").
- **A check constraint** `ck_competitions_one_end`: `cancelled_at IS NULL OR stopped_at IS NULL`. A
  competition is never both cancelled and finished; the database refuses it whatever the code does.

**Rationale**: the constitution (Principle VII) asks for exactly this: "Its status MUST be derived
on the server from the stored start and the stored stop or cancel". Every status rule then
follows from three columns.

**Alternatives considered**:

- **A `status` enum column updated at the start**: needs a scheduler or a write during a read.
- **`is_cancelled` / `is_finished` booleans**: the same checks, but they lose the time, which
  milestone 15 may show ("Finished on …").
- **A `finished_at` name**: the product calls the action "stop"; the column records the stop, and
  "Finished" is the status derived from it.

---

## R2. The status is a pure function of the row and one "now"

**Decision**: `app/services/competitions.py` has a `CompetitionStatus` enum (`upcoming`,
`in_progress`, `finished`, `cancelled`) and a pure `status_of(row, now)`:

1. `cancelled_at` set → **Cancelled**;
2. else `stopped_at` set → **Finished**;
3. else `starts_at > now` → **Upcoming**;
4. else → **In progress**.

- **One clock per request**: each service call reads `utc_now()` once and uses it for every row it
  derives, so a page never shows one competition as started and its neighbour, with the same
  start, as not.
- **The boundary**: at the start minute itself the competition is **In progress**; the form needs a
  start strictly later than the moment of saving (FR-004), so the two rules meet exactly.
- **Cancelled is checked first**, so a cancelled competition stays **Cancelled** when its start
  passes (FR-007).
- **The clock is `app.services.competitions.utc_now`**, imported from `app.core.db`, so tests
  replace it with `monkeypatch`, as the milestone 11 question service tests do. No sleeping, no
  real waiting.

**Rationale**: no job, no writes on read, and the same answer on every engine; the status is
checked again inside every write (R6), so a start that passes while a form is open is seen.

**Alternatives considered**:

- **Deriving in SQL with a `CASE`**: possible, but every list is sorted and filtered in Python
  anyway (R7), and one Python function is easier to test and to reuse in milestones 13–15.

---

## R3. Names: unique among live competitions of one subject

**Decision**: names follow the subject-name rules and messages through `app.schemas.names`
(`clean_name`, `name_key`). Uniqueness is a **partial unique index**
`uq_competitions_subject_name_live` on `(subject_id, name_key)` where `cancelled_at IS NULL AND
stopped_at IS NULL`.

- **"Upcoming or In progress" is exactly "not cancelled and not stopped"**, which depends only on
  stored columns, not on the time, so the database can hold the rule. A competition that starts
  keeps its name taken; one that is cancelled or stopped frees it at once (FR-003).
- **Same name in another subject**: `subject_id` is part of the index.
- **Its own name, or a change of case**: the service ignores the competition itself in the lookup,
  as `rename_team` does.
- **The message**: "A competition named “<entered name>” already exists in this subject." with the
  name as entered (after trimming).
- **Races**: the service looks the name up first for the friendly message; the index is the
  guarantee. An `IntegrityError` on commit is rolled back and reported as the same duplicate error
  (US4-11, SC-004).

**Engine-specific feature, justified (Constitution VII)**: the same partial index pattern as
`uq_teams_name_key_live` (milestone 11.1 research R2): declared once with `sqlite_where` and
`postgresql_where`, created by the migration on both engines and covered by the drift check.

**Alternatives considered**:

- **A unique index on `(subject_id, name_key)` for all rows**: would keep cancelled names taken
  for ever.
- **A check in code only**: two simultaneous saves would both pass it.

---

## R4. Time zones: a cookie the browser writes, and the server does the rest

**Decision**: a new module `app/core/time_zone.py`, the twin of `app/core/theme.py`:

- **The cookie** `sc_time_zone` holds an IANA name such as `Europe/Kyiv`. It is written by the
  browser (R5), never by the server, so it is not `HttpOnly`.
- **`parse_time_zone(value) -> ZoneInfo | None`** accepts only a name in
  `zoneinfo.available_timezones()` (computed once and cached), at most 64 characters. Anything else
  (missing, empty, unknown, a path, another case) is `None`: no zone known.
- **`read_time_zone(request)`** reads the cookie; never raises.
- **A context processor** in `app/core/templates.py` adds `time_zone` (a `ZoneInfo` or `None`) to
  every template, as `_theme` adds `theme`. The `local_time` component reads it (R10).
- **Not personal data, never stored, never logged**: the cookie names a zone, not a person, holds
  no identifier, and is not linked to an account; the server reads it per request and stores
  nothing (the same reasoning as the theme cookie, milestone 10 research D5).

**The runtime carries the database**: Python's `zoneinfo` reads the system time-zone database.
Checked on this machine:

- the application image built from the current `Dockerfile` (`python:3.13-slim-bookworm`) has
  Debian's `tzdata` package, version `2026b-0+deb12u1`, with 599 zones; `Europe/Kyiv` loads;
- macOS has `/usr/share/zoneinfo` (598 zones), so local runs and tests work too.

So **no new dependency** is added. To keep it true, the CI `image` job gains one step that runs
`python -c "import zoneinfo; zoneinfo.ZoneInfo('Europe/Kyiv')"` in the built image, and a unit test
asserts the same on the test machine; a base image without `tzdata` would fail the build, not
production.

**Rationale**: the milestone puts every conversion on the server ("the browser only says which
time zone it is in"), and the theme already proved the "browser-only cookie read on every request"
pattern.

**Alternatives considered**:

- **The `tzdata` PyPI package**: a new runtime dependency for data the image already has;
  `zoneinfo` would use it only as a fallback anyway.
- **Formatting times in the browser**: forbidden by the milestone, and it would break the
  no-JavaScript baseline differently on every page.
- **Storing the zone on the user**: a teacher moves between devices and zones; the browser knows
  its zone better than the account.
- **Accepting any name `ZoneInfo` can load**: `ZoneInfo` also loads names outside the list (such
  as `posixrules`) and touches the file system for each new key; a fixed allow-list is simpler to
  reason about.

---

## R5. The time-zone script

**Decision**: a new file `app/static/js/time-zone.js`, loaded by `layouts/base.html` on every page
with `defer`, right after `loading-feedback.js`. It is about 15 lines:

1. read `Intl.DateTimeFormat().resolvedOptions().timeZone`;
2. stop unless it matches `^[A-Za-z0-9_+\-]+(?:/[A-Za-z0-9_+\-]+)*$` and is at most 64 characters;
3. read the current `sc_time_zone` from `document.cookie`;
4. if it differs, write `sc_time_zone=<name>; Path=/; Max-Age=31536000; SameSite=Lax`, plus
   `; Secure` when the page is served over HTTPS.

- **When**: on every page load, so a changed zone (a teacher who travelled, or changed their
  computer's zone) is written on the next page. The sign-in page loads it too, so the first page
  after sign-in usually already knows the zone; a page shown before the script has run shows UTC,
  labelled "UTC" (spec Edge Cases).
- **No reload**: the page that wrote the cookie is not reloaded; the next page uses it. A reload
  would loop for a browser that refuses cookies.
- **The value is written raw**, not percent-encoded: IANA names use only cookie-safe characters
  (step 2 guarantees it), and Starlette does not percent-decode cookies.
- **It sends nothing**: no request, no storage other than the one cookie.

**Rationale**: smallest script that meets FR-020, with no build step and no dependency
(Constitution II).

**Alternatives considered**:

- **Putting it inside `loading-feedback.js`**: one fewer request, but that script's tests forbid
  `document.cookie` for good reason; two small files with one job each are easier to check.
- **A hidden field filled by script on each form**: the list needs the zone too, and it would fail
  without the script exactly where the cookie does.

---

## R6. Reading what the teacher typed: zone, gap and overlap

**Decision**: a pure module `app/schemas/competition.py`:

- **`parse_start(raw_date, raw_time, zone) -> datetime`** (UTC, whole minute) or `StartErrors`
  holding field errors:
  - date: empty → "Enter the start date."; not `YYYY-MM-DD` or not a calendar date (31 April) →
    "Enter a real start date.";
  - time: empty → "Enter the start time."; not `H:MM`, `HH:MM` or `HH:MM:SS` with real values →
    "Enter a real start time.". Seconds are accepted, because some browsers send them, and
    dropped: a start is to the minute;
  - the local date and time are combined in `zone`;
  - **a gap** (the clocks go forward): the local time does not survive a round trip through UTC
    (`local.replace(tzinfo=zone, fold=0)` → UTC → `zone` gives another wall time) → the error, on
    the time field, "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go
    forward. Enter another time.";
  - **an overlap** (the clocks go back): `fold=0`, which PEP 495 defines as the earlier of the two
    moments (FR-023);
  - a date so far ahead that the conversion overflows (year 9999 west of UTC) → "Enter a real
    start date.".
- **"In the future" is not checked here**: the service checks it with its own clock, inside the
  write (R8), so the time used is the moment of saving.
- **The zone a form is read in** is the hidden field `time_zone` the form was rendered with, not
  the cookie (FR-022). The router parses it with `parse_time_zone`; an unknown value is UTC (spec
  Assumptions), and `UTC` itself is a valid name.
- **The zone name in messages and hints** is the IANA key (`Europe/Kyiv`), or `UTC`.

**Where errors land**: "The start must be in the future." goes on the date field, the first of the
pair, so the summary link leads to the start; the gap message goes on the time field, which is the
part to change.

**Rationale**: PEP 495 `fold` is exactly the standard library's answer to both clock changes; the
round-trip test is the documented way to detect a gap with `zoneinfo`. Verified on this machine:
`Europe/Kyiv` has 28 March 2027 03:30 in a gap, 31 October 2027 03:30 twice, and 14 March 2027
10:00 is 08:00 UTC.

**Alternatives considered**:

- **A single `datetime-local` field**: one control instead of two, but the milestone names two
  fields (**Start date**, **Start time**), and their error messages differ.
- **Shifting a gap time forward (03:30 → 04:30)**: silently changes what the teacher typed; the
  milestone asks for a refusal.

---

## R7. The list: filtered, sorted and paged in Python

**Decision**: `competition_page(session, subject_id, status_filter, page, *, finished_only)` reads
the subject's competitions (only the columns needed), derives each status with one `now`, keeps
those matching the filter, sorts by `(-starts_at, name_key, id)` and slices one page with the
existing `Paging.build`. `finished_only` is set for a deactivated subject (R11).

- **Order**: latest start first, whatever the status (FR-014); equal starts by name ignoring case,
  ties by id, so the order is total and stable.
- **Why Python**: the status depends on "now", and name order must be the same on SQLite and
  PostgreSQL, whose collations differ. Every list in this application is sorted in Python for that
  reason (subjects, teams, students).
- **Scale**: a subject holds tens, at most a few hundred, competitions; reading them costs one
  indexed query on `subject_id`. If milestone 16 finds otherwise, a stored order key can follow.
- **The status filter** comes from the address as `status=upcoming|in_progress|finished|cancelled`;
  anything else, or nothing, is **All** (spec Edge Cases). Choosing another subject or status
  drops the page, so the first page opens (FR-017).
- **The page**: `paging.parse_page`, clamped to the last page, exactly as on **Questions**.
- **Landing** uses the same sorted list: the index of a competition gives its page,
  `index // 10 + 1`.

**Alternatives considered**:

- **SQL `ORDER BY starts_at DESC, name_key` with `LIMIT`/`OFFSET`**: cheaper per page, but the
  name order would differ between engines, and the status filter would need the `CASE` of R2.

---

## R8. Writes: the setting, the subject and the row, checked again inside the transaction

**Decision**: each write in `app/services/competitions.py` follows the milestone 11 pattern:

1. **The setting**: `teacher_access.can_manage_competitions(session, teacher_id, lock=True)`;
   without it, `ManageRequired` (403).
2. **The subject**: read `FOR SHARE`, refreshed. For **create**: it must be active, else
   `SubjectUnavailable` (404). For **edit** and **cancel**: the competition must belong to the
   subject in the request, and must not be hidden (R11), else `CompetitionNotFound` (404).
3. **The row**: read `FOR UPDATE`, refreshed; the status is derived with a fresh `now`.
4. **The change** is a conditional `UPDATE … WHERE id = :id AND <still allowed>` and the service
   checks the row count:
   - **edit**: `cancelled_at IS NULL AND stopped_at IS NULL AND starts_at > :now`;
   - **cancel**: `cancelled_at IS NULL AND stopped_at IS NULL`.

   A count of 0 means another request changed the row first; the service reads it again and raises
   the matching refusal (`NotEditable(status)` or `NotCancellable(status)`).
5. **The start** must be later than `now` (`StartNotInFuture`), checked after the row is locked.
6. **The name** is cleaned (`InvalidName`) and looked up (`DuplicateCompetitionName`); the unique
   index backs it on commit.

Every refusal rolls back before it raises, so no lock outlives it.

- **Why the conditional update as well as the lock**: on PostgreSQL the row lock alone serialises
  two cancels. On SQLite `FOR UPDATE` renders nothing; the conditional update makes the second of
  two simultaneous cancels change nothing and report "already cancelled" on both engines
  (FR-036, US5-7).
- **Cancelling an upcoming competition whose start just passed** is allowed: the cancel condition
  does not look at the start (FR-035).
- **An edit that changes nothing** writes nothing and does not touch `updated_at`, as for teams.

**Alternatives considered**:

- **Optimistic version numbers**: the same effect with an extra column and a hidden field; the
  conditional update needs neither.

---

## R9. Routes, addresses and the order of checks

**Decision**: a new router `app/routers/teacher_competitions.py` replaces the placeholder in
`app/routers/teacher.py`. Seven endpoints, all `@allow_roles(Role.TEACHER)`
([contracts/http-routes.md](./contracts/http-routes.md)):

| Method | Path | Kind |
|---|---|---|
| GET | `/teacher/competitions` | read |
| GET | `/teacher/competitions/new` | manage |
| POST | `/teacher/competitions` | manage |
| GET | `/teacher/competitions/{id}/edit` | manage |
| POST | `/teacher/competitions/{id}/edit` | manage |
| GET | `/teacher/competitions/{id}/cancel` | manage |
| POST | `/teacher/competitions/{id}/cancel` | manage |

- **The subject travels with every request**, in the query (`subject=`) or a form field, because
  "one of another subject than the one in the address" is "not found" (FR-042 step 4). The status
  and the page travel the same way, so every form, confirmation and refusal can return to the page
  the teacher came from.
- **The order of checks** is the spec's (FR-042): role (decorator) → setting (first line of a
  manage handler, before any value is parsed) → subject → competition → status. A teacher without
  the setting gets 403 for unknown ids too.
- **Statuses**: 403 access denied (the milestone 5 page), 404 "Subject not found" / "Competition
  not found" (a page in the teacher frame, like `question_not_found.html`), 409 for a refusal
  (as for a subject in use), 400 for a form shown again with errors, 303 after every change.
- **An unknown subject in the list's address** is 404, unlike **Questions**, which ignores it: the
  milestone says so. A missing or empty `subject` is "no subject chosen".
- **Return addresses** are built by one helper, `list_path(subject_id, status, page, anchor)`, from
  values that were looked up or parsed, never echoed from input. The anchor is
  `#competition-<id>`, which the milestone 10.1 scroll padding keeps below the pinned frame.

**Alternatives considered**:

- **Nesting under the subject** (`/teacher/competitions/subjects/{subject_id}/{id}/edit`): longer
  addresses for the same check; the query keeps the **Questions** pattern.

---

## R10. Showing a start: the `local_time` component

**Decision**: a new component file `components/time.html` with `local_time(moment, zone=time_zone)`,
imported `with context`, and two Python helpers registered as Jinja globals in
`app/core/templates.py`:

- `format_local_time(moment, zone)`: "14 March 2027, 10:00" in `zone`; with no zone, the UTC
  value with " UTC": "14 March 2027, 08:00 UTC". The day has no leading zero, the month is written
  in full from a fixed English list (not `%B`, which follows the process locale), the clock is
  24-hour.
- `utc_iso(moment)`: `2027-03-14T08:00Z`, for the `datetime` attribute.

The component emits `<time datetime="2027-03-14T08:00Z">14 March 2027, 10:00</time>`.

- **Inside the confirmation question** the start is part of the `h1`. The page captures the
  question with `{% set question %}…{{ local_time(c.starts_at) }}…{% endset %}`, which Jinja
  renders with autoescape into safe markup, and passes it to `confirmation`. This is template
  content, not an HTML string built in Python, so the guidelines' rule ("rich content goes through
  a block, never as an HTML string") holds; the guidelines gain this as the way to put a time in a
  heading.
- **The edit form** fills the date and time fields with the start in the teacher's zone
  (`YYYY-MM-DD` and `HH:MM`), or in UTC when no zone is known, and its hint names that zone.
- **The gallery** passes `zone` explicitly to show both variants.

**Alternatives considered**:

- **A Jinja filter**: shorter to call, but a component is what the library rule asks for, and the
  gallery and guidelines describe components.
- **The existing `utc` filter**: its format ("2026-10-22 14:05 UTC") is the profile's; changing it
  would change the profile, which is out of scope.

---

## R11. Deactivated subjects: which subjects are offered, which competitions are seen

**Decision**:

- **`offered_subjects(session) -> SubjectChoices`** in `app/services/competitions.py` returns the
  active subjects and, separately, the deactivated subjects that have at least one competition
  with `stopped_at IS NOT NULL`, each sorted by `name_key`, then id.
- **A subject is "offered"** if it is in either list. An id outside both is "Subject not found"
  (404), also for an unknown id and for a non-numeric value.
- **A competition is "visible"** if its subject is active, or if it is finished
  (`stopped_at IS NOT NULL`). An invisible competition is "Competition not found" (404), exactly
  like an unknown one; nothing tells them apart (FR-037).
- **In a deactivated subject** the list passes `finished_only=True`; the page shows no **Add
  competition** and no menus, even for a teacher with the setting (FR-038). The create page and
  action for such a subject answer 404 (spec Assumptions).
- **Edit and cancel of a finished competition of a deactivated subject** pass the subject and
  competition checks and get the status refusal ("has finished …").
- **An upcoming competition of a deactivated subject still starts**: nothing is stored about it;
  its status is derived when it is next seen (FR-037).
- **The subject's delete**: `count_subject_uses` adds every competition of the subject, in any
  status (FR-039). The admin page's text is unchanged.

**Alternatives considered**:

- **Storing a "hidden" flag on competitions when the subject is deactivated**: a second source of
  truth that the subject's activation must undo; deriving it is one condition.

---

## R12. Notices after a change: a sealed token, as for teams

**Decision**: the redirect after a create, an edit or a cancellation carries
`notice=<sealed token>`, built with `app.core.sealing` as in milestone 11.1 (research R11):

- purpose `competition-notice`, valid 10 minutes, payload
  `{"competition": <id>, "outcome": "added" | "saved" | "cancelled"}`;
- the list shows the notice only if the token is valid and fresh and its competition belongs to
  the listed subject and is visible; the name is read from the database at that moment:
  "Competition “Spring round” was added", "… was saved", "… was cancelled" (success notices);
- otherwise no notice, and the page is unchanged.

**Rationale**: no competition name ever enters an address, so access logs cannot hold one
(FR-046); a hand-made address cannot show a false notice; a reload within 10 minutes shows the
same notice and repeats nothing (SC-009).

**Alternatives considered**:

- **`added=<id>` in plain text**: can be crafted into a misleading notice.
- **The name in the address**: breaks the logging rule through access logs.

---

## R13. Landing after create, edit and cancel

**Decision**: one pure function, `landing(rows, competition_id, old_index) -> Landing(page,
anchor_id)`, over the sorted, filtered list after the change:

- **Create**: the list with status **All**; the new competition's index gives its page; the anchor
  is the competition (FR-025).
- **Edit**: the list with the same subject and status; the competition's new index gives its page
  (its start or name may have moved it). If the filter no longer shows it (only possible with a
  hand-made address), the rule for cancel applies.
- **Cancel**: if the filter still shows the competition (**All**, **Cancelled**), its index gives
  the page and the anchor. Otherwise, with `old_index` its index before the change: the row now at
  `old_index` (the one that took its place); else the row at `old_index - 1`; else, if the list is
  empty, page 1 with no anchor, which shows the empty state. Its page follows from the index, so a
  page that is now empty leads to the previous page at its last row (FR-034), as after deleting a
  question (milestone 11 research R8).
- **Cancel** (the link), **Keep competition** and **Back to competitions** return to the page the
  teacher came from with the competition's anchor, computed from the request's subject, status and
  page, not from a stored history.

**Alternatives considered**:

- **Returning to the page sent in the form**: wrong after an edit that moves the competition, and
  after a concurrent change by another teacher.

---

## R14. The actions menu

**Decision**: a new component file `components/menu.html`:

```jinja
{% call actions_menu("Spring round") %}
  {{ menu_link("Edit", edit_href) }}
  {{ menu_link("Cancel competition", cancel_href, destructive=True) }}
{% endcall %}
```

- **Markup**: `<details class="actions-menu" name="row-actions">` with
  `<summary>Actions<span class="visually-hidden"> for “Spring round”</span></summary>` and a
  `<ul class="actions-menu-panel">` of links. The visible label is "Actions"; the accessible name
  is "Actions for “Spring round”", which starts with the visible text (WCAG 2.5.3).
- **No JavaScript**: `<details>` opens and closes natively, like the user menu. The `name`
  attribute makes the row menus an exclusive group in current browsers, so opening one closes the
  others; older browsers ignore it and simply allow several open.
- **Entries are links** to the form and confirmation pages: the menu never sends a change itself,
  so every destructive action still goes through its confirmation page.
- **Touch and keyboard**: the summary and each entry are at least `--sc-touch-target` (44 px) tall;
  the summary is a focusable control and opens with Enter or Space; entries are reached with Tab.
- **Empty**: when the call block renders only white space, nothing is emitted (as
  `section_heading` does), so a row with no action has no menu button (FR-027).
- **Placement**: the panel is absolutely positioned under the summary, aligned to its right edge,
  above the following rows (`z-index` as the user menu's). On a phone card it sits in the card's
  actions part.
- **The table must not clip it**: `.data-table` has `overflow: hidden` from 768 px, only to round
  its corners. That rule is replaced by rounding the corner cells (`th:first-child`,
  `th:last-child`, and the last row's first and last cells), which draws the same corners without
  clipping. The gallery's table section shows the result, and `test_stylesheet.py` keeps passing.
- **Built for later actions**: the macro takes any number of entries; later 12.x milestones add
  **Questions**, **Teams** and **Stop competition** as more `menu_link` lines (FR-029).

**Alternatives considered**:

- **Buttons in the row, as on Questions**: three or four buttons per row will not fit a phone card
  once later milestones add their actions; the milestone asks for a menu.
- **A panel in the flow of the row (not absolute)**: never clipped, but opening it grows the row
  and moves the table, which reads as a layout jump.
- **A script-driven menu with `aria-haspopup`**: more behaviour to build and test, against the
  no-JavaScript baseline.

---

## R15. The other component changes

- **Date and time fields** (`components/form.html`): `date_time_fields(prefix, legend, values,
  errors, zone_label)` renders a `<fieldset>` with the legend "Start", **Start date**
  (`<input type="date">`) and **Start time** (`<input type="time">`), both `required`, their
  errors, the hint "Time zone: <zone>" under the time field, and the hidden field `time_zone`
  carrying the zone. Ids and names are `<prefix>_date`, `<prefix>_time`. The browser's own
  pickers do the work; without date input support they are text fields that accept the same
  values.
- **Competition status badge** (`components/badge.html`): `competition_status_badge(status)` maps
  each status to its word and an existing kind: **Upcoming** `info`, **In progress** `success`,
  **Finished** `neutral`, **Cancelled** `muted`. No new colour token: every badge is a word, so
  colour is never the only signal; an unknown status is a template error.
- **`confirmation(..., back_label="Cancel")`**: the link back reads `back_label`. Every existing
  call keeps **Cancel**.
- **`chained_lists` option groups**: a level may carry `groups`, a list of `(label, options)`;
  `select_field` gains `groups=()` and renders each as `<optgroup label="…">` after the plain
  options. A level without `groups` renders exactly as before.
- **`competition_status_badge`, `actions_menu`, `menu_link`, `date_time_fields`, `local_time`**,
  the back label and option groups are each added to the gallery and to `ui-guidelines.md` before
  the tab uses them ([contracts/components.md](./contracts/components.md)).
- **UI guidelines wording**: the statuses rule becomes "Statuses use one short term each,
  everywhere", with **Upcoming**, **In progress**, **Finished**, **Cancelled** added; a "Times"
  pattern states the format and the UTC fallback.

---

## R16. Tests

New modules (both engines unless pure):

- `tests/unit/test_competition_schemas.py`: `parse_start` (empty and invalid dates and times,
  seconds dropped, gap refused with the exact message, overlap stored as the earlier moment, Kyiv
  to UTC, UTC zone, overflow), and `format_local_time` / `utc_iso`.
- `tests/unit/test_time_zone.py`: `parse_time_zone` (known, unknown, path-like, too long, wrong
  case, `UTC`), and the runtime has `Europe/Kyiv`.
- `tests/unit/test_time_zone_script.py`: the script read as text, like `test_loading_script.py`:
  plain script, no request or other storage, names no other site, writes only `sc_time_zone`, with
  `Path=/`, `SameSite=Lax` and `Max-Age`, checks the name, stays small.
- `tests/integration/test_competition_service.py`: status derivation with a controlled clock,
  create, edit and cancel rules, uniqueness (case, other subject, freed by cancel and stop, race
  through the index), conditional updates, landing, offered subjects, visibility.
- `tests/integration/test_teacher_competitions.py`: the tab end to end, one test group per user
  story and the milestone's _Test:_ list, with the zone cookie set to `Europe/Kyiv` or absent and
  the clock controlled.

Updated modules: `test_routes.py` (three new writes; the manage paths and the scoped paths),
`test_teacher_access.py`, `test_access_control.py` if it lists teacher pages,
`test_form_contract.py` with new `teacher-competition*` cases generated once,
`test_component_gallery.py`, `test_page_patterns.py`, `test_layout.py` (both scripts once per
page), `test_admin_subjects.py` and `test_subject_service.py` (a competition is a use),
`test_migrations.py` (the new revision, the index and the check constraint), `test_stylesheet.py`
stays green, and `test_teacher_classes.py::test_competitions_is_a_placeholder` is replaced by a test
that the tab is the competitions list (SC-010). The CI `image` job gains the `zoneinfo` check of
R4.

What stays manual: the menu's look and keyboard use in a browser, the date and time pickers, and
the script writing the cookie, checked by hand and with an ad hoc Playwright run as in milestone
10.1 ([quickstart.md](./quickstart.md) §5), until end-to-end tests arrive in milestone 16.
