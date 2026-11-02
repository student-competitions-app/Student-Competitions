---

description: "Task list for milestone 12.1: creating, editing and cancelling competitions (teacher)"
---

# Tasks: Creating, Editing and Cancelling Competitions (Teacher) (Milestone 12.1)

**Input**: Design documents from `/specs/012.1-teacher-competitions/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-050 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R16.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`.
- **Signed-in clients**: `admin_client` and `client_as`. Real teachers come from
  `make_teacher(engine, settings, email=..., institutions={}, can_manage=True | False)`; subjects
  from `make_subject(engine, name, active=...)`; competitions from the new `make_competition`
  (T020).
- **The clock**: tests control "now" with
  `monkeypatch.setattr("app.services.competitions.utc_now", lambda: fixed)`, as
  `tests/integration/test_question_service.py::clock` does. No test sleeps.
- **The zone**: tests set the browser's zone with `client.cookies.set("sc_time_zone",
  "Europe/Kyiv")`, or leave it unset for UTC.

**Organization**: tasks are grouped by user story (US1–US10 in spec.md).

- **Phase 1 is the components and the time helpers they need**, because the constitution puts the
  library, the gallery and the guidelines before any page (FR-048). It delivers US10.
- **Phase 2** is the table, the migration, the start parsing, the read side of the service and the
  test helper.
- **US1** builds the tab (subject list, table, page navigation), the add form and the create action:
  the MVP. **US2** completes the list (status filter, empty states, address rules).
- **US3** adds the actions menu and editing; **US5** cancelling. **US4** and **US6** are mostly rule
  tests over services and routes built in US1, US3 and US5 (the rules are in the services from the
  start).
- **US7** (access, P1) is enforced inside every route as it is built (the rules below); its own
  phase is the cross-cutting sweep, after the last route (US5).
- **US8** adds the script; the server side of time zones is in Phase 1, so every earlier story
  already shows times in the cookie's zone.

**Reference implementation**: milestones 10–11.1 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**: `app/services/questions.py` (`_refuse`, `_require_manage`, `get_active_subject`
  with `lock=`, `with_for_update`, `populate_existing`, `Landing`, the module-level `utc_now`),
  `app/services/teams.py` (`create_team` / `rename_team`: the name lookup, the `IntegrityError`
  branch, the unchanged-name no-op), `app/services/paging.py` (`parse_page`, `Paging.build`,
  `PAGE_SIZE`), `app/services/teacher_access.py::can_manage_competitions`,
  `app/services/subjects.py`.
- **Core**: `app/core/theme.py` (a browser cookie read per request), `app/core/templates.py`
  (context processors, globals, `template_error`), `app/core/sealing.py` (`seal` / `unseal`).
- **Routers**: `app/routers/teacher_questions.py` (thin handlers, `_require_manage` first,
  `list_path`, `_not_found`, values as plain strings, 303 redirects), `app/routers/teacher_teams.py`
  (the sealed notice token: `TEAM_NOTICE_PURPOSE`, `TEAM_NOTICE_TTL`), `app/routers/teacher.py`
  (`TEACHER_TABS`, `render_teacher`).
- **Templates**: `app/templates/pages/teacher/questions.html`, `question_form.html`,
  `question_delete.html`, `question_not_found.html`; `app/templates/pages/admin/subject_delete.html`
  (`refusal`); components `frame.html` (`user_menu` is the `<details>` pattern, `page_heading`,
  `back_link`, `section_heading`'s blank-caller test), `table.html`, `selectors.html`, `form.html`,
  `badge.html`, `confirmation.html`, `feedback.html`, `pagination.html`; the gallery
  `app/templates/pages/admin/components.html` with `app/routers/admin_components.py`;
  `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Script**: `app/static/js/loading-feedback.js` and `tests/unit/test_loading_script.py`.
- **Migration**: `migrations/versions/2026_10_29_09cbcbe472be_teams.py` (the partial unique index
  with `sqlite_where` / `postgresql_where`, frozen snapshot, `op.f` names).
- **Tests**: `tests/integration/test_teacher_questions.py`, `test_question_service.py`,
  `test_teacher_teams.py`, `test_routes.py` (`test_the_write_routes_are_exact`, `MANAGE_PATHS`),
  `test_teacher_access.py` (`QUESTIONS_TAB` exclusion, `TEACHER_POSTS`), `test_form_contract.py`
  with `form_contract.json`, `test_page_patterns.py`, `test_component_gallery.py`,
  `test_migrations.py`, `test_layout.py`, `tests/html.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks** in every handler: role (`@allow_roles(Role.TEACHER)`, 403 for administrator
  and student) → on a *manage* route, `_require_manage` as the **first line**, before any value is
  parsed (403 `AccessDenied(Role.TEACHER)`, unknown ids too) → the subject (404 "Subject not
  found") → the competition (404 "Competition not found") → the status (409 refusal) → the fields
  (400, the form again) → the service write, which repeats the checks under lock and raises the
  same outcomes.
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON. Ids are ASCII digits ≤ `MAX_ID`
  (`app.schemas.teachers.MAX_ID`), else "not found".
- **Redirects**: every change is a `POST` through the existing cross-site check, answering `303`.
  Every redirect, Cancel, **Keep competition**, **Back to competitions** and back link is built by
  `list_path(subject_id, status, page, anchor, notice)` from looked-up ids and parsed values only
  (research R9).
- **Time**: every stored or compared time is UTC (`UTCDateTime`); the services read the clock only
  through `app.services.competitions.utc_now`, once per call (research R2). Display goes through
  `format_local_time` / `local_time` only.
- **Logging**: services log ids only, exactly: `Competition created: id=%d subject=%d`,
  `Competition updated: id=%d`, `Competition cancelled: id=%d`. A no-op logs nothing. No email,
  person's name or competition name ever reaches a log line or an address (FR-046).
- **Components first**: a new macro is in the library, its CSS in the Components section of
  `app/static/css/app.css` (tokens only, no inline style, no literal colour or pixel length), the
  gallery and `ui-guidelines.md` **before** a page uses it (FR-048).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US10)

---

## Phase 1: Setup (Time helpers and components first)

**Purpose**: the server-side time-zone helpers, and every new or changed component in the library,
the gallery and the guidelines (FR-048, FR-049, research R4, R10, R14, R15,
contracts/components.md §1–§6, contracts/services.md §`app/core/time_zone.py`). Nothing here
touches the database. Delivers **US10**.

- [X] T001 Create `app/core/time_zone.py` per contracts/services.md §`app/core/time_zone.py` and research R4, with a module docstring in the style of `app/core/theme.py` (the cookie is written by the browser, not `HttpOnly`, holds no identifier, is never stored or logged):
  - `TIME_ZONE_COOKIE_NAME = "sc_time_zone"`, `TIME_ZONE_MAX_LENGTH = 64`, `UTC_ZONE = ZoneInfo("UTC")`;
  - `_known_zones()`: `zoneinfo.available_timezones()` computed once (`functools.cache`);
  - `parse_time_zone(value: str | None) -> ZoneInfo | None`: `None` unless `value` is a `str` of 1–64 characters that is **in** `_known_zones()` exactly (so `utc`, `posixrules`, `../etc`, `europe/kyiv` are `None`); never raises;
  - `read_time_zone(request: Request) -> ZoneInfo | None`: `parse_time_zone(request.cookies.get(TIME_ZONE_COOKIE_NAME))`;
  - `zone_name(zone: ZoneInfo | None) -> str`: `zone.key`, or `"UTC"` for `None`;
  - `MONTHS`: the twelve English month names as a tuple (not `%B`, which follows the process locale);
  - `format_local_time(moment: datetime, zone: ZoneInfo | None) -> str`: `moment` must be aware (assert); converted to `zone`, or to UTC when `None`; `f"{d.day} {MONTHS[d.month - 1]} {d.year}, {d:%H:%M}"`, plus `" UTC"` when `zone is None` → "14 March 2027, 10:00" / "14 March 2027, 08:00 UTC";
  - `utc_iso(moment: datetime) -> str`: `moment.astimezone(UTC)` as `"%Y-%m-%dT%H:%MZ"` → `2027-03-14T08:00Z`.
- [X] T002 [P] Create `tests/unit/test_time_zone.py`: `parse_time_zone` accepts `Europe/Kyiv`, `UTC`, `America/Argentina/Buenos_Aires`; refuses `None`, `""`, `utc`, `europe/kyiv`, `posixrules`, `../etc/passwd`, `Europe/Nowhere`, a 65-character string; `zone_name`; `format_local_time` for 2027-03-14 08:00 UTC in `Europe/Kyiv` ("14 March 2027, 10:00"), with `None` ("14 March 2027, 08:00 UTC"), a single-digit day ("1 March 2027, …"), midnight ("00:00"); `utc_iso`; and that the runtime knows `Europe/Kyiv` (`ZoneInfo("Europe/Kyiv")` loads and is in `available_timezones()`), so a machine without the time-zone database fails here (research R4).
- [X] T003 Extend `app/core/templates.py` (depends on T001): a context processor `_time_zone(request)` returning `{"time_zone": read_time_zone(request)}`, added to `context_processors` after `_theme`; register `format_local_time` and `utc_iso` as `templates.env.globals`. Update the module docstring's paragraph on context processors to name the zone (research R4, R10).
- [X] T004 [P] Create `app/templates/components/time.html` with `local_time(moment, zone=time_zone)` per contracts/components.md §4 (depends on T003): emits `<time datetime="{{ utc_iso(moment) }}">{{ format_local_time(moment, zone) }}</time>` on one line; a `None` moment is a `template_error("local_time: the moment is required")`. A header comment: import it `with context`; in a heading, capture the heading with `{% set … %}…{% endset %}` and pass it on, never build it in Python.
- [X] T005 [P] Add `competition_status_badge(status)` to `app/templates/components/badge.html` per contracts/components.md §3: maps `"upcoming"` → `badge("Upcoming", "info")`, `"in_progress"` → `badge("In progress", "success")`, `"finished"` → `badge("Finished", "neutral")`, `"cancelled"` → `badge("Cancelled", "muted")`; it accepts the enum or its string value (compare `status | string`); anything else is `template_error("competition_status_badge: unknown status …")`. No new CSS and no new token.
- [X] T006 [P] Create `app/templates/components/menu.html` with `actions_menu(item_name, label="Actions")` and `menu_link(label, href, destructive=False)` per contracts/components.md §1 and research R14:
  - `actions_menu` renders `caller()` once into a variable; if it is blank after `trim`, it emits nothing (as `section_heading` does); an empty `item_name` is a `template_error`;
  - otherwise `<details class="actions-menu" name="row-actions"><summary>{{ label }}<span class="visually-hidden"> for “{{ item_name }}”</span></summary><ul class="actions-menu-panel">{{ entries }}</ul></details>`;
  - `menu_link` emits `<li><a href="{{ href }}" class="actions-menu-link[ actions-menu-link-destructive]">{{ label }}</a></li>`, the destructive class built from literal strings in a `{% set …_class = … %}` (the stylesheet check's rule for dynamic classes).
  - CSS in the Components section of `app/static/css/app.css`, tokens only: `.actions-menu` `position: relative; display: inline-block`; its `summary` styled as a small outline secondary button, `min-height: var(--sc-touch-target)`, with a chevron drawn like `details.user-menu > summary::after` and Pico's accordion marker hidden (copy the `details.user-menu > summary` colour overrides so Pico's accordion colours do not apply); `.actions-menu-panel` `position: absolute; right: 0; top: calc(100% + var(--sc-space-1)); z-index` as `.user-menu-panel`, `min-width: 12rem; max-width: calc(100vw - 2 * var(--sc-space-2))`, `list-style: none`, `background: var(--sc-surface)`, `border`, `border-radius: var(--sc-radius-card)`, `box-shadow: var(--sc-shadow-menu)`; `.actions-menu-link` `display: flex; align-items: center; min-height: var(--sc-touch-target); padding-inline: var(--sc-space-2); overflow-wrap: anywhere`, the focus ring as other links, hover on `--sc-neutral-tint`; `.actions-menu-link-destructive` `color: var(--sc-danger)`. Below 768 px, inside `.data-table td.row-actions`, the menu takes the full width of the actions part and the panel stays within the card (`left: 0; right: 0`).
  - **The table corners** (research R14): in the `@media (min-width: 768px)` `.data-table` rule, remove `overflow: hidden` and round the corner cells instead — `thead th:first-child { border-top-left-radius: var(--sc-radius-card) }`, `thead th:last-child { border-top-right-radius: … }`, `tbody tr:last-child td:first-child { border-bottom-left-radius: … }`, `tbody tr:last-child td:last-child { border-bottom-right-radius: … }` — so the table looks the same and an open panel is not clipped.
- [X] T007 [P] Extend `app/templates/components/form.html` per contracts/components.md §2 and §6 and research R15:
  - `select_field(..., groups=())`: after the plain `options` and before `extra_options`, each `(label, options)` pair renders `<optgroup label="{{ label }}">` with its options, marking `selected` exactly as the plain options do. A call without `groups` renders byte-for-byte as before;
  - new `date_time_fields(prefix, legend, values, errors, zone_label)`: `<fieldset class="date-time-fields"><legend>{{ legend }}</legend>` then `field(prefix ~ "_date", legend ~ " date", value=values[prefix ~ "_date"], error=errors[prefix ~ "_date"], type="date", attrs={"required": True})` and `field(prefix ~ "_time", legend ~ " time", value=…, error=…, hint="Time zone: " ~ zone_label, type="time", attrs={"required": True})`, then `<input type="hidden" name="time_zone" value="{{ zone_label }}">`, `</fieldset>`; a header comment as the other macros have.
  - CSS in `app/static/css/app.css`: `.date-time-fields` with no fieldset border or padding of its own beyond the form's rhythm; from 768 px the two label/field pairs stand side by side (a two-column grid, each pair in its own column), below 768 px they stack. Tokens only.
- [X] T008 [P] Extend `chained_lists` in `app/templates/components/selectors.html` (depends on T007): pass `groups=level.groups or ()` to `select_field`; update the header comment to list `groups` (`(label, options)` pairs) among a level's keys. Existing callers (students, teams, team add-students, questions, the gallery) render exactly as before.
- [X] T009 [P] Extend `confirmation` in `app/templates/components/confirmation.html` with `back_label="Cancel"` (last parameter): the link back reads `{{ back_label }}`. Update the header comment. Every existing call keeps **Cancel**.
- [X] T010 Add the gallery entries (depends on T004–T009):
  - `app/routers/admin_components.py` (`_samples`): a sample moment `datetime(2027, 3, 14, 8, 0, tzinfo=UTC)`, `ZoneInfo("Europe/Kyiv")`, a 200-character competition name, the four status values, a subject list with a group `("Deactivated subjects", [(7, "Astronomy")])`, and form `values`/`errors` for the date and time pair (one with "Enter a real start date." and the gap message "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward. Enter another time.");
  - `app/templates/pages/admin/components.html`: a new `<section id="actions-menu">` (a closed menu; an open one with the `open` attribute holding **Edit** and the destructive **Cancel competition**; a data table row with the menu in its actions cell and a 200-character name); a new `<section id="time">` (`local_time(sample, zone=kyiv)` and `local_time(sample, zone=none)`); `#badges` gains the four competition statuses; `#forms` gains `date_time_fields` empty, filled with `Europe/Kyiv`, and with the two errors; `#confirmations` gains a confirmation with `back_label="Keep competition"`; `#selectors` gains a `chained_lists` level with the "Deactivated subjects" group. Import `time.html` `with context`. Add the new sections to the gallery's table of contents if it has one.
- [X] T011 [P] Update `docs/requirements/ui-guidelines.md` per contracts/components.md §8 (depends on T004–T009): §4 Layout (the base layout loads two scripts, `loading-feedback.js` and `time-zone.js`; T048 adds the second), §5 a new "Actions menu (`components/menu.html`)" subsection, `date_time_fields` under Forms, `competition_status_badge` under Badges, a new "Local time (`components/time.html`)" subsection with the `{% set %}…{% endset %}` heading rule, `back_label` under Confirmations, option groups under Selectors; §7 the statuses rule rewritten to "Statuses use one short term each, everywhere: **Active** or **Deactivated**; **Read** or **Write**; **Upcoming**, **In progress**, **Finished** or **Cancelled**.", a **Times** pattern and a **Menus** pattern; §8 the actions menu in a table card, its 44 px entries; §10 the time-zone script's static checks. Each gallery link (`/admin/components#actions-menu`, `#time`) as the other subsections have.
- [X] T012 [P] Extend the component tests (depends on T010): `tests/integration/test_component_gallery.py` — `#actions-menu` (a `details.actions-menu` with `name="row-actions"`, the summary's text "Actions for “…”" through `tests/html.py`, an open variant, a destructive link), `#time` (one `<time datetime="2027-03-14T08:00Z">` reading "14 March 2027, 10:00" and one reading "14 March 2027, 08:00 UTC"), the four badges, the date and time pair (types `date` and `time`, the hint "Time zone: Europe/Kyiv", the hidden `time_zone`), the **Keep competition** confirmation, the `<optgroup label="Deactivated subjects">`; `tests/unit/test_templates.py` — `actions_menu` emits nothing for a blank call block, `menu_link` destructive class, `competition_status_badge` for each status and a template error for `"unknown"`, `local_time` with and without a zone and an error for `None`, `select_field` without `groups` unchanged and with a selected value inside a group, `confirmation` default **Cancel** and custom label; `tests/unit/test_stylesheet.py` stays green (every new class defined and used; no literal colour or pixel length) and asserts `.data-table` no longer has `overflow: hidden`.

**Checkpoint**: every new and changed component is in the library, the gallery and the guidelines;
existing pages render as before (`test_page_patterns.py`, `test_form_contract.py` green). US10 is
done.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the table, the migration, the start parsing, the read side of the service and the
test helper (data-model.md, research R1–R3, R6, R7, R11, R13, contracts/services.md).

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end.

- [X] T013 Create `app/models/competition.py` per data-model.md §1 and research R1, and export `Competition` from `app/models/__init__.py` (and its `__all__`):
  - `class Competition(SQLModel, table=True)`, `__tablename__ = "competitions"`, a class docstring (status derived, never stored; live ⇔ `cancelled_at IS NULL AND stopped_at IS NULL`; no creator; not personal data; `stopped_at` written by a later 12.x milestone);
  - `__table_args__`: `Index("uq_competitions_subject_name_live", "subject_id", "name_key", unique=True, sqlite_where=text("cancelled_at IS NULL AND stopped_at IS NULL"), postgresql_where=text("cancelled_at IS NULL AND stopped_at IS NULL"))` and `CheckConstraint("cancelled_at IS NULL OR stopped_at IS NULL", name="ck_competitions_one_end")`;
  - `id: int | None` primary key; `subject_id: int = Field(foreign_key="subjects.id", index=True, nullable=False)` ("Set at creation, never written again (FR-001). No `ON DELETE`"); `name` `String(NAME_MAX_LENGTH)` (200) not null; `name_key` `String(NAME_KEY_MAX_LENGTH)` (600) not null, from `app.schemas.names`; `starts_at: datetime` `UTCDateTime` not null ("always a whole minute"); `cancelled_at: datetime | None` and `stopped_at: datetime | None` `UTCDateTime` nullable; `created_at`, `updated_at` `UTCDateTime` not null with `default_factory=utc_now`.
  - Update the docstring of `app/models/subject.py`, which still says competitions add references "in milestone 10": competitions refer to subjects from milestone 12.1.
- [X] T014 Create the migration `migrations/versions/2026_11_02_<rev>_competitions.py` (`down_revision = "09cbcbe472be"`) per data-model.md §7, following `2026_10_29_09cbcbe472be_teams.py`: create `competitions` with every column of T013, the foreign key, `ck_competitions_one_end`, `op.f("ix_competitions_subject_id")` and the partial unique index with both `sqlite_where` and `postgresql_where`; the downgrade drops the indexes and the table. Generate the revision id with `uv run alembic revision -m "competitions"` and write the operations by hand (a frozen snapshot, no model imports). Run `uv run alembic upgrade head` locally.
- [X] T015 [P] Extend `tests/integration/test_migrations.py` (depends on T014): the head is the new revision; the stairway and drift checks cover it on both engines; after upgrade, inserting two live competitions with the same `(subject_id, name_key)` fails, one live plus any number with `cancelled_at` or `stopped_at` set succeeds, the same key in another subject succeeds, and a row with both `cancelled_at` and `stopped_at` set fails (the check constraint); downgrade to `09cbcbe472be` drops the table.
- [X] T016 [P] Create `app/schemas/competition.py` per contracts/services.md §`app/schemas/competition.py`, data-model.md §6 and research R6 (pure, no I/O; module docstring):
  - `StartErrors(date: str | None, time: str | None)` frozen dataclass;
  - `parse_start(raw_date, raw_time, zone) -> datetime | StartErrors`, collecting both fields' errors before returning:
    - date: stripped; empty → "Enter the start date."; not matching `^\d{4}-\d{2}-\d{2}$` or not a calendar date (`date.fromisoformat` fails, e.g. 31 April) → "Enter a real start date.";
    - time: stripped; empty → "Enter the start time."; not matching `^(\d{1,2}):(\d{2})(?::(\d{2}))?$` with hour 0–23, minute 0–59, second 0–59 → "Enter a real start time."; seconds are dropped;
    - with both valid: `local = datetime.combine(d, time(h, m))`; `aware = local.replace(tzinfo=zone, fold=0)`; if `aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local` → `StartErrors(None, gap_message(local, zone_name))` where the zone name is `zone.key`; an `OverflowError` or `ValueError` from the conversion → "Enter a real start date."; else return `aware.astimezone(UTC)` (seconds and microseconds 0);
  - `gap_message(local, zone_name)`: "There is no {HH:MM} on {d Month yyyy} in {zone} because the clocks go forward. Enter another time." (reuse `MONTHS` from `app.core.time_zone`);
  - `local_parts(moment, zone) -> tuple[str, str]`: `("YYYY-MM-DD", "HH:MM")` of `moment` in `zone` (UTC when `None`), for filling the edit form.
- [X] T017 [P] Create `tests/unit/test_competition_schemas.py` (depends on T016): every message of data-model.md §6 for dates and times (empty, `2027-02-30`, `2027-04-31`, `14.03.2027`, `24:00`, `10:60`, `ab:cd`), `10:00:59` accepted with seconds dropped, `9:30` accepted, both errors at once; 14 March 2027 10:00 in `Europe/Kyiv` → 08:00 UTC; the same in UTC → 10:00 UTC; 28 March 2027 03:30 in `Europe/Kyiv` → exactly "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward. Enter another time." on the time field; 31 October 2027 03:30 in `Europe/Kyiv` → 2027-10-31 00:30 UTC (the earlier moment); 9999-12-31 23:59 in `America/New_York` → "Enter a real start date."; `local_parts` round-trips.
- [X] T018 Create the read side of `app/services/competitions.py` per contracts/services.md §`app/services/competitions.py` (Types, Errors, Pure functions, Reads) and research R2, R7, R11, R13, with a module docstring like `app/services/questions.py`'s (the clock, the order of checks, visibility, the contract for later milestones):
  - `from app.core.db import utc_now` at module level (tests patch `app.services.competitions.utc_now`);
  - `CompetitionStatus(StrEnum)` with `label`; `parse_status_filter(raw)`;
  - the errors `ManageRequired`, `SubjectUnavailable`, `CompetitionNotFound`, `NotEditable(status)`, `NotCancellable(status)`, `StartNotInFuture`, `DuplicateCompetitionName(entered)` (with `message` = "A competition named “{entered}” already exists in this subject.");
  - `CompetitionView`, `CompetitionPage(competitions, paging, subject_total)`, `SubjectChoices(active, deactivated)` with `is_offered`, `get`, `only`, and `Landing(page, competition_id)`;
  - `status_of(row, now)` in the order Cancelled, Finished, Upcoming (`starts_at > now`), In progress; `sort_key(view)` = `(-view.starts_at.timestamp(), name_key, id)` (carry `name_key` in the view or a private row tuple); `landing(rows, competition_id, old_index)` per research R13, page `index // PAGE_SIZE + 1`;
  - `offered_subjects(session)`: the active subjects (`list_active_subjects`) and the deactivated subjects with at least one competition with `stopped_at IS NOT NULL` (one query with `EXISTS` or a join), each sorted by `(name_key, id)` in Python;
  - `_visible(subject_is_active)` rule: all competitions of an active subject; only `stopped_at IS NOT NULL` ones of a deactivated subject;
  - `competition_page(session, subject, status, page)`: read the subject's visible rows (one query on `subject_id`), `now = utc_now()` once, derive statuses, `subject_total` = all visible, filter by `status`, sort with `sort_key`, `Paging.build(page, len(filtered))`, slice;
  - `get_competition(session, competition_id, subject_id, *, lock=False)`: `CompetitionNotFound` for unknown, other subject, or invisible (the subject read too; with `lock`, the competition `FOR UPDATE` and the subject `FOR SHARE`, both `populate_existing`, rolling back before raising, as `questions.get_question` does);
  - `locate(session, subject, status, competition_id, old_index=None) -> Landing`.
- [X] T019 Extend `app/services/subjects.py::count_subject_uses` (depends on T013) to add `select(func.count()).select_from(Competition).where(Competition.subject_id == subject_id)` to the question count, in any status; rewrite the docstring sentence "Competitions add their count in milestone 12" and the module docstring's "competitions add theirs in milestone 12" as statements of what is counted (FR-039, research R11).
- [X] T020 Add `make_competition(engine, subject_id, name="Spring round", starts_at=..., *, cancelled=False, stopped=False) -> int` to `tests/conftest.py`, in a new "Milestone 12.1: competitions" section after the teams helpers (depends on T013): inserted directly with `name_key(name)`, `starts_at` required (aware UTC, whole minute), `cancelled_at`/`stopped_at` = `utc_now()` when asked; docstring "**Test-only**, but harmless: a competition carries no personal data; this is the only way to store a **Finished** competition before stopping exists".
- [X] T021 Create `tests/integration/test_competition_service.py` for the read side (depends on T018, T020), with a `clock` fixture patching `app.services.competitions.utc_now`: `status_of` for every status, the start minute itself being In progress, Cancelled winning over a passed start; `competition_page` order (15, 1 and 25 March listed 25, 15, 1; equal starts by name ignoring case, then id; "Ärger" and "apple" in the same order on both engines), 25 competitions → 10/10/5, page clamping, each status filter; `subject_total`; `offered_subjects` (active sorted; a deactivated subject offered only with a finished competition; `only`); visibility (an upcoming, in-progress and cancelled competition of a deactivated subject are `CompetitionNotFound`; a finished one is found; another subject's id is `CompetitionNotFound`); `landing` (in the list; the row that took its place; the row before; the previous page when a page empties; the empty list → `Landing(1, None)`); `count_subject_uses` counts a competition.

**Checkpoint**: the table exists on both engines, statuses and pages are computed, and the whole
existing suite is green.

---

## Phase 3: User Story 1 - A teacher creates a competition (Priority: P1) 🎯 MVP

**Goal**: the **Competitions** tab lists a subject's competitions; a teacher with the setting adds
one and lands at it with the notice (FR-009–FR-016, FR-024–FR-026).

**Independent Test**: with the zone cookie `Europe/Kyiv`, create "Spring round" on 14 March 2027
10:00 and check the landing page, the anchor, the notice, the row, "14 March 2027, 10:00",
**Upcoming**, and `starts_at` = 08:00 UTC in the database.

### Implementation for User Story 1

- [X] T022 [US1] Add the write `create_competition(session, teacher_id, subject_id, raw_name, starts_at)` to `app/services/competitions.py` per contracts/services.md §Writes and research R8 (depends on T018): `_require_manage` (`can_manage_competitions(..., lock=True)`, else roll back and `ManageRequired`); the subject `FOR SHARE` with `populate_existing`, unknown or not active → `SubjectUnavailable`; `now = utc_now()`; `starts_at <= now` → `StartNotInFuture`; `clean_name` (`InvalidName` after rolling back); a live competition of the subject with the same `name_key` (a private helper `_find_live(session, subject_id, key)`, reused by T032) → `DuplicateCompetitionName(name)`; insert with `created_at = updated_at = now`; an `IntegrityError` on commit → roll back, `DuplicateCompetitionName(name)`; log `Competition created: id=%d subject=%d`; return the view.
- [X] T023 [US1] Create `app/routers/teacher_competitions.py` per contracts/http-routes.md (depends on T018, T022), docstring in the style of `teacher_questions.py` (the order of checks, return addresses, notices, no logging in the router):
  - `router = APIRouter(prefix="/teacher/competitions")`, `TAB = "competitions"`, `TAB_PATH`; `SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist, or it is deactivated and has no finished competitions.")`; `COMPETITION_NOT_FOUND = ("Competition not found", "This competition does not exist, or its subject is deactivated.")`; `FIELD_ORDER = ["name", "start_date", "start_time"]`;
  - helpers `_parse_id`, `_teacher`, `_can_manage`, `_require_manage`, `_redirect`, `_not_found`, and `list_path(subject_id, status=None, page=1, anchor=None, notice=None)` (leaves out `status` for All, `page` for 1);
  - the notice token: `COMPETITION_NOTICE_PURPOSE = "competition-notice"`, `COMPETITION_NOTICE_TTL = timedelta(minutes=10)`, `_notice_token(competition_id, outcome)` and `_read_notice(session, raw, subject)` returning the text "Competition “{name}” was added" / "… was saved" / "… was cancelled" only for a valid, fresh token whose competition is visible in `subject` (research R12);
  - `GET ""` (`competitions_page`): `offered_subjects`; `subject` missing/empty → none chosen (then `choices.only` if exactly one); otherwise parsed and checked against `choices` → 404 `SUBJECT_NOT_FOUND` when not offered; `status = parse_status_filter(...)`; `competition_page(...)`; render `pages/teacher/competitions.html` with `subjects` (active `(id, name)` pairs), `groups` (`[("Deactivated subjects", …)]` when any), `selected`, `selected_active`, `status`, `listing`, `can_manage`, `can_add = can_manage and selected_active`, `notice`, `page_href`;
  - `GET /new` and `POST ""` (create): `_require_manage` first; the subject must be offered **and active** (else 404); the form context `values`, `errors`, `zone_label` (`zone_name(read_time_zone(request))` for `GET`; the submitted `time_zone` parsed with `parse_time_zone`, `UTC` when unknown, for `POST`), `back = list_path(subject, status, page)`; on `POST`: `parse_start(start_date, start_time, zone)`, then `create_competition`, mapping `InvalidName` / `DuplicateCompetitionName` to `errors["name"]`, `StartNotInFuture` to `errors["start_date"] = "The start must be in the future."`, `ManageRequired` to `AccessDenied`, `SubjectUnavailable` to 404; errors → 400 with the values as typed; success → 303 to `list_path(subject, None, landing.page, anchor=id, notice=_notice_token(id, "added"))` using `locate(session, subject, None, id)`.
- [X] T024 [P] [US1] Create `app/templates/pages/teacher/competitions.html` per contracts/http-routes.md §1 (depends on T004, T005, T008): extends `layouts/teacher.html`; `auto-submit.js` in `{% block scripts %}`; `page_heading("Competitions", action=("Add competition", "/teacher/competitions/new?subject=…&status=…&page=…") if can_add)`; `chained_lists` with the subject level (label "Subject", placeholder "Choose a subject", `groups`); exactly one of the empty states "No subjects yet" / "Select a subject" with the hints of FR-011; for a chosen subject: the notice (`notice(text, "success")`), then "No competitions yet" (hint only when `can_add`), or the table between `page_navigation(listing.paging, page_href, "Competitions", "Pages, top")` and "Pages, bottom": `data_table(["Name", "Start", "Status", "Actions"])`, each `<tr id="competition-{{ c.id }}">` with `cell("Name", c.name)`, `local_time(c.starts_at)` in the "Start" cell, `competition_status_badge(c.status)` in "Status", and an `actions_cell()` left empty for now (US3 fills it). Import `time.html` `with context`. (The status list and the "No competitions with this status" state come in US2.)
- [X] T025 [P] [US1] Create `app/templates/pages/teacher/competition_form.html` per contracts/http-routes.md §2 and §4 (depends on T007): `back_link(back, "Back to the competitions")`; `page_heading(heading)` ("Add competition", or "Edit competition “{name}”" when `competition_id`); `error_summary(errors, order=field_order)`; `<p>Subject: {{ subject.name }}</p>`; the form posting to `/teacher/competitions` (or `/teacher/competitions/{id}/edit`) with hidden `subject`, `status`, `page`; `field("name", "Name", value=values.name, error=errors.name, hint="Up to 200 characters.", attrs={"required": True, "maxlength": "200"})`; `date_time_fields("start", "Start", values, errors, zone_label)`; `form_actions("Save competition", cancel_href=back)`.
- [X] T026 [P] [US1] Create `app/templates/pages/teacher/competition_not_found.html` like `question_not_found.html`: `back_link("/teacher/competitions", "Back to the competitions")`, `page_heading(heading)`, `<p>{{ text }}</p>`.
- [X] T027 [US1] Wire the tab (depends on T023): in `app/routers/teacher.py` remove the placeholder `competitions_page` and its imports that become unused, and update the module docstring to name `app.routers.teacher_competitions`; include `teacher_competitions.router` in `app/main.py` next to the other teacher routers; delete `app/templates/pages/teacher/placeholder.html` (its only user was the placeholder).
- [X] T028 [US1] Keep the route-table tests green (depends on T027): in `tests/integration/test_routes.py` add `("POST", "/teacher/competitions")` to `test_the_write_routes_are_exact`, add `"/teacher/competitions/new"` to `MANAGE_PATHS` and extend its docstring and the module docstring ("…and the competitions' add, edit and cancel pages (milestone 12.1)"); in `tests/integration/test_teacher_access.py` add `COMPETITIONS_TAB = "/teacher/competitions"` with a docstring like `QUESTIONS_TAB`'s (its access rule is the setting; `test_teacher_competitions.py` sweeps it), keep `/teacher/competitions` itself in `TEACHER_GETS` and `AREA_PAGES`, and exclude every path under `/teacher/competitions/` from `TEACHER_GETS` and every `/teacher/competitions…` path from `TEACHER_POSTS`, so `len(TEACHER_POSTS) == 13` still holds; in `tests/integration/test_teacher_classes.py` replace `test_competitions_is_a_placeholder` with `test_competitions_is_the_competitions_list` (the `h1` "Competitions", the subject list, the current tab, no placeholder sentence).
- [X] T029 [US1] Create `tests/integration/test_teacher_competitions.py` with its setup and the US1 tests (depends on T023–T027): fixtures for a teacher with the setting (`make_teacher(..., can_manage=True)`), one without, the subjects "Chemistry" and "Physics", the `clock` (fixed at 2027-03-01 09:00 UTC) and the zone cookie; tests for US1-1 to US1-8: the tab opens `/teacher/competitions` with the four tabs unchanged; **Add competition** shown for an active subject with the setting; the form's title, back link, subject as text, fields and "Time zone: Europe/Kyiv" with the hidden `time_zone`; create → 303 to `/teacher/competitions?subject=…&notice=…#competition-<id>` (no `status`, page of the competition), the list shows the notice "Competition “Spring round” was added", the row, "14 March 2027, 10:00" in a `<time datetime="2027-03-14T08:00Z">` and **Upcoming**; `starts_at` stored as 08:00 UTC; with no cookie the same row reads "14 March 2027, 08:00 UTC" and the form "Time zone: UTC"; **Cancel** returns to the page the teacher came from and stores nothing; a single offered subject is chosen automatically; a created competition on the third page of 25 lands on page 3 at it; a tampered or expired notice token shows no notice; the access log rule: no competition name in any redirect address.

**Checkpoint**: a teacher with the setting can add a competition and find it in the list (MVP).

---

## Phase 4: User Story 2 - The list of competitions (Priority: P1)

**Goal**: the status filter, the page navigation kept with the status, every empty state, and the
address rules (FR-013–FR-018).

**Independent Test**: seed every status with equal and different starts; check the order, paging,
filter, address and empty states as teachers with and without the setting.

### Implementation for User Story 2

- [X] T030 [US2] Add the **Status** list to `app/templates/pages/teacher/competitions.html` and its router context (depends on T024): a second `chained_lists` level for a chosen subject — `id`/`name` `status`, label "Status", options `("", "All")`, `("upcoming", "Upcoming")`, `("in_progress", "In progress")`, `("finished", "Finished")`, `("cancelled", "Cancelled")`, no placeholder, `selected` the current value, `carry` `[("subject", id)]` and no page (so choosing opens page 1); the subject level carries nothing (choosing a subject drops status and page). Between "No competitions yet" (`listing.subject_total == 0`) and the table, add `empty_state("No competitions with this status", "Choose another status, or All.")` when the filtered list is empty; `page_href` keeps `subject` and `status`. In `app/routers/teacher_competitions.py`, an unknown `status` value reads as All, and a non-numeric or unknown `subject` is 404 (http-routes.md §Address parameters).
- [X] T031 [US2] Add the US2 tests to `tests/integration/test_teacher_competitions.py` (depends on T030): US2-1 to US2-13 — the table columns and no creator column; 15/1/25 March order whatever the status; equal starts by name ignoring case; 25 competitions: "Competitions 11–20 of 25", **Previous**/**Next**, navigation above and below; the status list's five options and **All** by default; each status shows only matching rows (with the clock moved so one is In progress and a `make_competition(..., stopped=True)` is Finished); the status kept across pages in the navigation links; subject, status and page in the address and restored on reload; choosing another subject or status opens page 1 (the forms carry no `page`); "No competitions yet" with the hint for the setting and without for another teacher; "No competitions with this status" with its hint; "Select a subject" and "No subjects yet" with their hints; no **Add competition** and no menus for the teacher without the setting; `status=bogus` reads as All; `subject=abc` and an unknown subject id are 404 "Subject not found"; without JavaScript each list has the `<noscript>` **Show** button.

**Checkpoint**: the list is complete; US1 and US2 work on their own.

---

## Phase 5: User Story 3 - A teacher edits an upcoming competition (Priority: P1)

**Goal**: the actions menu on each row and editing (FR-027–FR-032).

**Independent Test**: edit the name and start of an upcoming competition so it moves to another
page; check the menu, the filled form, the landing, the notice and the stored start.

### Implementation for User Story 3

- [X] T032 [US3] Add `update_competition(session, teacher_id, competition_id, subject_id, raw_name, starts_at)` to `app/services/competitions.py` per contracts/services.md §Writes and research R8 (depends on T018): `_require_manage`; `get_competition(..., lock=True)` (subject `FOR SHARE`, row `FOR UPDATE`); `now = utc_now()`; status not Upcoming → roll back, `NotEditable(status)`; `starts_at <= now` → `StartNotInFuture`; `clean_name`; a live competition of the subject with the same `name_key` and another id → `DuplicateCompetitionName(name)`; nothing changed → roll back and return the view (no write, no log); else `session.execute(update(Competition).where(Competition.id == competition_id, col(Competition.cancelled_at).is_(None), col(Competition.stopped_at).is_(None), Competition.starts_at > now).values(name=…, name_key=…, starts_at=…, updated_at=now))`; row count 0 → roll back, re-read, `NotEditable(status_of(row, utc_now()))`; `IntegrityError` → `DuplicateCompetitionName(name)`; commit; log `Competition updated: id=%d`.
- [X] T033 [US3] Add the edit routes to `app/routers/teacher_competitions.py` per contracts/http-routes.md §4–§5 (depends on T023, T032): `GET /{competition_id:int}/edit` and `POST /{competition_id:int}/edit`, `_require_manage` first; the subject from `subject` (query or form) must be offered (404); `get_competition(session, id, subject.id)` (404); status not Upcoming → 409 `pages/teacher/competition_refused.html` with the question "Edit competition “{name}”?", the reason for the status (In progress: "“{name}” has already started and can no longer be edited."; Cancelled: "“{name}” has been cancelled and can no longer be edited."; Finished: "“{name}” has finished and can no longer be edited.") and `back = list_path(subject, status, page, anchor=id)`; the `GET` form is filled with `local_parts(starts_at, read_time_zone(request))` and the zone label of the cookie; the `POST` reads only `subject`, `status`, `page`, `name`, `start_date`, `start_time`, `time_zone`, parses the start in the form's zone, calls `update_competition` and maps errors as in T023 (`NotEditable` → the 409 refusal); success → 303 to `list_path(subject, status, landing.page, anchor=id, notice=_notice_token(id, "saved"))` with `locate(session, subject, status, id)`. Add `"/teacher/competitions/{competition_id:int}/edit"` to `MANAGE_PATHS` and `("POST", "/teacher/competitions/{competition_id:int}/edit")` to `test_the_write_routes_are_exact` in `tests/integration/test_routes.py`.
- [X] T034 [P] [US3] Create `app/templates/pages/teacher/competition_refused.html` (depends on T009): `back_link(back, "Back to the competitions")`, then `refusal(question, reason, back, "Back to competitions")`; the title is the question. One template serves the edit and the cancel refusals.
- [X] T035 [US3] Fill the actions cell in `app/templates/pages/teacher/competitions.html` (depends on T006, T030): when `can_add` (the setting and an active subject), `{% call actions_menu(c.name) %}{% if c.status == "upcoming" %}{{ menu_link("Edit", edit_href) }}{% endif %}{% endcall %}`, with `edit_href = "/teacher/competitions/" ~ c.id ~ "/edit?subject=…&status=…&page=…"` (current subject, status and page); no menu otherwise. (US5 adds **Cancel competition** after **Edit**.)
- [X] T036 [US3] Add the US3 tests to `tests/integration/test_teacher_competitions.py` (depends on T033–T035): US3-1 to US3-5 — the **Actions** menu on an upcoming row with the accessible name "Actions for “Spring round”" and **Edit**; no menu for the teacher without the setting; the edit form's title, filled name, date and time in `Europe/Kyiv` (and in UTC without the cookie), the subject as text; saving a new name and a start that moves it from page 1 to page 2 lands on page 2 at `#competition-<id>` with "Competition “Spring final” was saved" and the same status in the address; saving its own name and a change of case only are valid; an unchanged save writes nothing (`updated_at` unchanged); **Cancel** returns to the page the teacher came from at the competition; a `subject` field of another subject in the edit form is 404 and changes nothing.

**Checkpoint**: upcoming competitions can be edited from the row menu.

---

## Phase 6: User Story 4 - Names, dates and times are validated (Priority: P1)

**Goal**: every validation rule through the create and edit forms (FR-002–FR-004, FR-022, FR-023,
FR-026).

**Independent Test**: submit the create and edit forms with every invalid input and check the
errors, the kept values and that nothing is stored.

### Tests for User Story 4

- [X] T037 [P] [US4] Add the US4 tests to `tests/integration/test_teacher_competitions.py` (depends on T029, T036): for both create and edit, US4-1 to US4-11 — an empty name, spaces only, 201 characters, a tab or line break (each with its exact message beside the field and in "There is a problem", the values kept, status 400, nothing stored); a trimmed name stored trimmed; "spring ROUND" against a live "Spring round" of the same subject → "A competition named “spring ROUND” already exists in this subject."; the same name accepted when the only other one is cancelled or finished, and in another subject; "Enter the start date.", "Enter a real start date.", "Enter the start time.", "Enter a real start time."; a start equal to the clock's current minute and one in the past → "The start must be in the future."; 28 March 2027 03:30 with `time_zone=Europe/Kyiv` → the gap message on `start_time`; 31 October 2027 03:30 stored as 00:30 UTC; the form shown in `Europe/Kyiv` with the cookie changed to `UTC` before saving is still read in `Europe/Kyiv` (FR-022); `time_zone=Mars/Base` is read in UTC.
- [X] T038 [P] [US4] Add the concurrency and rule tests to `tests/integration/test_competition_service.py` (depends on T022, T032): `create_competition` and `update_competition` refuse `ManageRequired` for a teacher without the setting; `create_competition` refuses `SubjectUnavailable` for a deactivated subject, also one still offered through a finished competition; after its subject is deactivated, `update_competition` refuses an upcoming competition with `CompetitionNotFound` (hidden) and a finished one with `NotEditable(FINISHED)` (research R8, R11); the lost edit race: cancel the row directly in the database, then patch `app.services.competitions.status_of` to answer Upcoming on its first call only (the real function after that), so the check under lock passes and the conditional `UPDATE` matches no row → `NotEditable(CANCELLED)`, the session usable afterwards, and `name`, `starts_at` and `updated_at` unchanged (FR-032, SC-005); `StartNotInFuture` at the boundary (`starts_at == now`) and accepted one minute later; a race on the name: patch the service's live-name lookup (the private helper T022 adds, e.g. `_find_live`) to return `None`, so the insert reaches the partial unique index while a live competition with the same key exists → `DuplicateCompetitionName` from the `IntegrityError` branch, the session usable afterwards, nothing stored (US4-11, SC-004).

**Checkpoint**: every rule of data-model.md §6 is enforced and tested.

---

## Phase 7: User Story 5 - A teacher cancels a competition (Priority: P1)

**Goal**: cancelling with a confirmation, the landing, and the final **Cancelled** state
(FR-033–FR-036).

**Independent Test**: cancel an upcoming and an in-progress competition, use **Keep competition**,
cancel under a filter that hides the row, repeat a cancellation.

### Implementation for User Story 5

- [X] T039 [US5] Add `cancel_competition(session, teacher_id, competition_id, subject_id, status) -> Landing` to `app/services/competitions.py` per contracts/services.md §Writes and research R8, R13 (depends on T018): `_require_manage`; `get_competition(..., lock=True)`; `now = utc_now()`; status Cancelled or Finished → roll back, `NotCancellable(status)`; the competition's index in the subject's visible list filtered by `status` before the change (`old_index`, `None` if not in it); `session.execute(update(Competition).where(Competition.id == competition_id, col(Competition.cancelled_at).is_(None), col(Competition.stopped_at).is_(None)).values(cancelled_at=now))`; row count 0 → roll back, re-read, `NotCancellable(status_of(row, utc_now()))`; the filtered list after the change; commit; log `Competition cancelled: id=%d`; return `landing(after, competition_id, old_index)`. `updated_at` is not touched.
- [X] T040 [US5] Add the cancel routes to `app/routers/teacher_competitions.py` per contracts/http-routes.md §6–§7 (depends on T033, T039): `GET /{competition_id:int}/cancel` and `POST /{competition_id:int}/cancel`, `_require_manage` first, subject (404), competition (404); Cancelled → 409 refusal "Cancel competition “{name}”?" with "“{name}” is already cancelled."; Finished → 409 with "“{name}” has finished and cannot be cancelled."; both with **Back to competitions** to `list_path(subject, status, page, anchor=id)`; the `GET` renders `pages/teacher/competition_cancel.html`; the `POST` reads only `subject`, `status`, `page`, calls `cancel_competition`, maps `NotCancellable` to the 409 refusal, and on success redirects 303 to `list_path(subject, status, landing.page, anchor=landing.competition_id, notice=_notice_token(id, "cancelled"))`. Add `"/teacher/competitions/{competition_id:int}/cancel"` to `MANAGE_PATHS` and `("POST", "/teacher/competitions/{competition_id:int}/cancel")` to `test_the_write_routes_are_exact` in `tests/integration/test_routes.py`.
- [X] T041 [P] [US5] Create `app/templates/pages/teacher/competition_cancel.html` (depends on T004, T009): `back_link(back, "Back to the competitions")`; `{% set question %}Cancel competition “{{ c.name }}” of {{ subject.name }}, starting {{ local_time(c.starts_at) }}?{% endset %}`; `confirmation(question, "The competition will be marked Cancelled and stays in the list. It cannot be edited, started or restored.", "/teacher/competitions/" ~ c.id ~ "/cancel", "Cancel competition", back, hidden={"subject": subject.id, "status": status or "", "page": page}, back_label="Keep competition")`. Import `time.html` `with context`. The `<title>` is "Cancel competition “{name}”" without the time.
- [X] T042 [US5] Add **Cancel competition** to the row menu in `app/templates/pages/teacher/competitions.html` (depends on T035): `{{ menu_link("Cancel competition", cancel_href, destructive=True) }}` for `upcoming` and `in_progress`, after **Edit**, `cancel_href` carrying subject, status and page. A Finished or Cancelled row renders an empty call block, so no menu button.
- [X] T043 [US5] Add the US5 tests to `tests/integration/test_teacher_competitions.py` (depends on T040–T042): US5-1 to US5-10 — the confirmation's `h1` "Cancel competition “Spring final” of Chemistry, starting 2 April 2027, 09:30?" with a `<time>` element, the consequence sentence, the destructive **Cancel competition** and the link **Keep competition**; **Keep competition** changes nothing; cancelling an upcoming and an in-progress competition → **Cancelled**, no menu, the notice, at the competition on the same page; under the **Upcoming** filter, landing at the row that took its place, at the row before when it was last, on the previous page when its page empties, on the empty state when none is left; an upcoming competition whose start passes between opening and sending is cancelled; a cancelled competition stays **Cancelled** after its start passes; opening or sending the cancel of a cancelled competition → 409 "“…” is already cancelled." with **Back to competitions**, nothing changed; a finished one → "“…” has finished and cannot be cancelled."; its name is then accepted for a new competition of the subject; the **Cancelled** filter lists it with no menu.
- [X] T044 [P] [US5] Add the cancel rule and log tests to `tests/integration/test_competition_service.py` (depends on T022, T032, T039): `cancel_competition` sets only `cancelled_at` (not `updated_at`, `name`, `starts_at`); a second call → `NotCancellable(CANCELLED)`; the lost cancel race: cancel the row directly in the database, then patch `app.services.competitions.status_of` to answer Upcoming on its first call only, so the check under lock passes and the conditional `UPDATE` matches no row → `NotCancellable(CANCELLED)` and the first `cancelled_at` value kept; a finished competition → `NotCancellable(FINISHED)`; the returned `Landing` for each filter case of research R13; the log lines (FR-046), with `caplog` on `uvicorn.error` as `test_question_service.py` does: create, update and cancel each log exactly `Competition created: id=%d subject=%d`, `Competition updated: id=%d` and `Competition cancelled: id=%d`, no record contains the competition name, and an unchanged edit and every refusal log nothing.

**Checkpoint**: competitions can be cancelled for good, and every repeat is refused.

---

## Phase 8: User Story 6 - A competition starts on its own (Priority: P1)

**Goal**: the derived **In progress** status and its effect on the menu and on editing (FR-006,
FR-028, FR-032).

**Independent Test**: with the clock controlled, let a start pass and check the badge, the filter,
the menu, the edit page and the edit action.

### Tests for User Story 6

- [X] T045 [US6] Add the US6 tests to `tests/integration/test_teacher_competitions.py` (depends on T043): US6-1 to US6-4 — with the clock moved past the start (no write in between), the row shows **In progress** and the **In progress** filter lists it; its menu lists only **Cancel competition**; opening its edit page and sending its edit form (opened before the start, sent after) → 409 "Edit competition “Spring round”?" with "“Spring round” has already started and can no longer be edited." and **Back to competitions**, nothing stored; a cancelled and a finished competition have no menu and their edit pages give "has been cancelled …" / "has finished …"; an edit form opened while upcoming and sent after another teacher cancelled the competition → 409 "“Spring round” has been cancelled and can no longer be edited.", nothing stored (spec Edge Cases); the database row of the started competition is unchanged (nothing is written when a start passes).

**Checkpoint**: statuses follow time with nobody acting.

---

## Phase 9: User Story 7 - Only teachers see competitions, and only managers change them (Priority: P1)

**Goal**: the access rules on every route, in the spec's order (FR-040–FR-044).

**Independent Test**: every route as each role and as teachers with and without the setting,
through addresses and submitted forms, including unknown, mismatched and hidden ids.

### Tests for User Story 7

- [X] T046 [US7] Add the access sweep to `tests/integration/test_teacher_competitions.py` (depends on T040): every `GET` and `POST` of the router (built from `ALL_ROUTES` filtered on `/teacher/competitions`, so a later route is covered) → 403 naming the role for the administrator and the student, with a snapshot of `competitions` unchanged; every manage route → 403 for the teacher without the setting, also with an unknown competition id and an unknown subject (the setting is checked first); a teacher with the setting gets 404 "Subject not found" for an unknown or non-offered subject and "Competition not found" for an unknown id, a competition of another subject than the address's, and a hidden one, before any status refusal; a teacher with the setting edits and cancels a competition another teacher created; a `POST` without the cross-site token is refused and changes nothing; the setting removed (with `update_teacher`) between opening a form and saving it → 403 and nothing stored (US7-1 to US7-7); no page answers with FastAPI's JSON errors for odd values (`subject=1e9999`, `page=-1`, `status=%00`, a 30-digit id).

**Checkpoint**: every page and action is refused to everyone it must be.

---

## Phase 10: User Story 8 - Times follow the teacher's time zone (Priority: P1)

**Goal**: the script that reports the zone, loaded on every page (FR-020, FR-021, FR-049).

**Independent Test**: set the cookie to valid, invalid and no values and check every place a start
is shown; check the script statically and the layout loads it.

### Implementation for User Story 8

- [X] T047 [US8] Create `app/static/js/time-zone.js` per contracts/components.md §7 and research R5: a header comment like `loading-feedback.js`'s; `const COOKIE = "sc_time_zone";` the zone from `Intl.DateTimeFormat().resolvedOptions().timeZone`; stop unless it is a string of at most 64 characters matching `/^[A-Za-z0-9_+\-]+(?:\/[A-Za-z0-9_+\-]+)*$/`; read the current value from `document.cookie`; if different, `document.cookie = COOKIE + "=" + zone + "; Path=/; Max-Age=31536000; SameSite=Lax" + (location.protocol === "https:" ? "; Secure" : "");`. No request, no other storage, no reload, no DOM change.
- [X] T048 [US8] Load it from `app/templates/layouts/base.html` (depends on T047): `<script src="/static/js/time-zone.js" defer></script>` right after the `loading-feedback.js` script tag.
- [X] T049 [P] [US8] Create `tests/unit/test_time_zone_script.py` per contracts/components.md §7 (depends on T047), modelled on `tests/unit/test_loading_script.py`: a plain script (no `import`/`export`); none of `fetch(`, `XMLHttpRequest`, `sendBeacon`, `localStorage`, `sessionStorage`, `location.reload`, `innerHTML`; no URL to another site; `document.cookie` assigned exactly once, with `sc_time_zone`, `Path=/`, `SameSite=Lax`, `Max-Age=31536000` and `Secure` only under `https:`; `resolvedOptions().timeZone` and the name check present; at most 30 non-empty lines.
- [X] T050 [P] [US8] Extend `tests/integration/test_layout.py` (depends on T048): every kind of page (signed out, each role, an error page) loads `/static/js/time-zone.js` exactly once, `defer`, in the head, after `loading-feedback.js`, and the file is served as JavaScript.
- [X] T051 [US8] Add the US8 tests to `tests/integration/test_teacher_competitions.py` (depends on T043): US8-2 to US8-5 — with `sc_time_zone=Europe/Kyiv` every start on the tab (list, edit form values and hint, confirmation heading, refusal page) is in Kyiv time inside `<time datetime="…Z">`; with no cookie, with `sc_time_zone=Mars/Base`, `utc` or `../etc/passwd`, every start reads "… UTC" and the form "Time zone: UTC"; with `America/New_York` the same competition reads in New York time; a start entered in a zone is stored in UTC and compared with the clock in UTC.

**Checkpoint**: times are right in every zone, with and without the script.

---

## Phase 11: User Story 9 - Deactivated subjects keep only their finished competitions (Priority: P2)

**Goal**: the "Deactivated subjects" group, the read-only list, and "not found" for hidden
competitions (FR-037–FR-039).

**Independent Test**: with a finished competition stored directly, deactivate its subject; check
the subject list, the listed competitions, "not found" for the others, no actions, and the delete
refusal.

### Implementation for User Story 9

- [X] T052 [US9] Make the tab read-only for a deactivated subject (depends on T042): in `app/routers/teacher_competitions.py`, `selected_active` is false for a subject offered under "Deactivated subjects", so `can_add` is false (no **Add competition**, no menus, no "Add the first competition…" hint); `GET /new` and `POST ""` answer 404 `SUBJECT_NOT_FOUND` for it (the create path requires an active subject; spec Assumptions); confirm the subject `chained_lists` level passes `groups=[("Deactivated subjects", [(id, name), …])]` only when the list is not empty.
- [X] T053 [US9] Add the US9 tests to `tests/integration/test_teacher_competitions.py` (depends on T052): US9-1 to US9-6 — after `set_subject_active(…, False)`, an upcoming, an in-progress and a cancelled competition are not listed and their edit, cancel and list anchors give 404 "Competition not found"; a finished one (`make_competition(..., stopped=True)`) stays listed under the subject offered in `<optgroup label="Deactivated subjects">` (sorted by name ignoring case, after the active subjects), with the status filter and page navigation, no **Add competition**, no menus; `/teacher/competitions/new?subject=<deactivated>` → 404 for a teacher with the setting; its edit and cancel pages → 409 "has finished …"; forms opened before the deactivation and sent after it — the create form, the edit form of an upcoming competition, the cancel confirmation of an upcoming and of an in-progress competition — → 404, nothing stored or changed (spec Edge Cases); a deactivated subject without a finished competition is not offered and its address is 404; an upcoming competition of a deactivated subject shows **In progress** after the clock passes its start and the subject is activated again; a deactivated subject that is the only offered one is chosen automatically.
- [X] T054 [P] [US9] Extend `tests/integration/test_admin_subjects.py` and `tests/integration/test_subject_service.py` (depends on T019): a subject with one competition (upcoming, cancelled or finished) cannot be deleted — `count_subject_uses` counts it, `POST /admin/subjects/{id}/delete` answers 409 with "is in use and cannot be deleted. You can deactivate it instead.", and the subject stays.

**Checkpoint**: finished competitions survive their subject's deactivation, read-only; everything
else is hidden.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: contracts, documents, CI and the manual browser checks.

- [X] T055 [P] Extend `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json`: new cases `teacher-competitions` (the list with the subject and status `GET` forms), `teacher-competition-new`, `teacher-competition-new-invalid`, `teacher-competition-edit`, `teacher-competition-cancel` and `teacher-competition-refused`, generated once with `UPDATE_FORM_CONTRACT=1` for those cases only; add a "**Milestone 12.1**: the Competitions tab's pages (`teacher-competition*` cases) are new, generated once …" line to the module docstring; every existing case unchanged.
- [X] T056 [P] Extend `tests/integration/test_page_patterns.py` with the tab's pages: the add and edit forms have the error summary and the back link "Back to the competitions"; the cancel page is a confirmation with a destructive button and a back link; the refusal page uses `refusal`; the list uses badges for statuses, never coloured text.
- [X] T057 [P] Add the time-zone check to the `image` job of `.github/workflows/checks.yml`, right after "Build the image": a step "The image has the time-zone database" running `docker run --rm --entrypoint python student-competitions:ci -c "import zoneinfo; zoneinfo.ZoneInfo('Europe/Kyiv')"`, with a comment pointing to specs/012.1-teacher-competitions/research.md R4.
- [X] T058 [P] Update `README.md`: the **Competitions** tab (who sees it, who adds, edits and cancels), the `sc_time_zone` cookie (written by the browser, only the zone, never stored on the server, times shown in UTC without it), and that the image relies on Debian's `tzdata`.
- [X] T059 Run the manual and ad hoc browser checks of [quickstart.md](./quickstart.md) §4–§7 (the walk-through, without JavaScript, the menu by keyboard and on a phone card, the open menu on the last table row not clipped, the pickers, the cookie written and updated, 360 px and 375 px in Light and Dark, the gallery) with an ad hoc Playwright run (`uv run --with playwright`, a copy of the database, port 8765) as in milestone 10.1, and record the results, with any deviation, in `specs/012.1-teacher-competitions/pr-notes.md`.
- [X] T060 Run `uv run ruff check`, `uv run ruff format --check` and the whole suite on SQLite and on PostgreSQL (`TEST_POSTGRES_URL`); fix anything red (SC-010). On delivery, move milestone 12.1 to **Delivered** in `docs/requirements/milestones.md` with a short summary and its spec link, as the other delivered milestones have.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. T001 → T003 → T004; T005–T009 in parallel; T010 after
  T004–T009; T011, T012 after T010.
- **Phase 2 (Foundational)**: after Phase 1 (T016 needs T001's `MONTHS`). T013 → T014 → T015;
  T016 → T017; T013 → T018, T019, T020 → T021. Blocks every story.
- **US1 (Phase 3)**: after Phase 2. T022 → T023 → T027 → T028; T024–T026 in parallel with T023;
  T029 last.
- **US2 (Phase 4)**: after US1 (it extends the list page).
- **US3 (Phase 5)**: after US2 (the menu goes in the list built there).
- **US4 (Phase 6)**: after US3 (it tests create and edit).
- **US5 (Phase 7)**: after US3 (it adds to the same menu and router).
- **US6 (Phase 8)**: after US5 (it checks the menu without **Edit**).
- **US7 (Phase 9)**: after US5, the last route.
- **US8 (Phase 10)**: T047–T050 can start any time after Phase 1; T051 after US5.
- **US9 (Phase 11)**: after US5.
- **US10**: delivered by Phase 1.
- **Polish (Phase 12)**: after every story.

### Within each story

- The service write before the routes that call it; templates in parallel with the routes; the
  route-table test updates in the same task as the routes they cover, so the suite stays green;
  the story's tests last.

### Parallel opportunities

- Phase 1: T002, T005, T006, T007, T009 together; then T008; then T011 and T012 together.
- Phase 2: T015 and T017 alongside T018.
- US1: T024, T025, T026 together while T023 is written.
- US5: T041 alongside T040; T044 alongside T043.
- US8: T047–T050 alongside US3–US7 (different files).
- Polish: T055–T058 together.

## Parallel Example: User Story 1

```bash
# After T022 (create_competition) is done, in parallel:
Task: "T023 Create app/routers/teacher_competitions.py (list, new, create)"
Task: "T024 Create app/templates/pages/teacher/competitions.html"
Task: "T025 Create app/templates/pages/teacher/competition_form.html"
Task: "T026 Create app/templates/pages/teacher/competition_not_found.html"
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1: components and time helpers in the library, the gallery and the guidelines.
2. Phase 2: the table, the migration, start parsing, the read side, the helper.
3. Phase 3: the tab and creating. **Stop and validate**: create a competition in Kyiv time, find it
   in the list, check UTC in the database.

### Incremental delivery

1. US2 (the full list) → US3 (edit) → US4 (validation proof) → US5 (cancel) → US6 (start passing)
   → US7 (access sweep) → US8 (the script) → US9 (deactivated subjects).
2. Each story ends with its tests green on both engines and the whole suite green.
3. Polish: contracts, README, CI, the manual browser run, delivery.
