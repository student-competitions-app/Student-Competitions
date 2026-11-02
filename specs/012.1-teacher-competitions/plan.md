# Implementation Plan: Creating, Editing and Cancelling Competitions (Teacher) (Milestone 12.1)

**Branch**: `012.1-teacher-competitions` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.1-teacher-competitions/spec.md`

## Summary

The **Competitions** tab of the teacher area stops being a placeholder. Every teacher sees the
competitions of a subject; a teacher with **Can manage competitions** adds, edits and cancels them.
A competition has a subject, a name and a start; its status is derived, never stored; every time is
converted and formatted on the server in the browser's time zone.

**Data** (research R1–R3, [data-model.md](./data-model.md)):

- **One migration** creates `competitions`: `subject_id`, `name`, `name_key`, `starts_at` (UTC,
  whole minute), nullable `cancelled_at` and `stopped_at`, `created_at`, `updated_at`. No creator,
  no status column, no duration.
- **Names** are unique ignoring case among live competitions (not cancelled, not stopped) of a
  subject, through a partial unique index, the milestone 11.1 team pattern.
- **A check constraint** keeps a competition from being both cancelled and finished.
- **`stopped_at` exists now** so **Finished** is handled everywhere; a later 12.x milestone writes
  it, tests set it directly.

**Status** (R2): `status_of(row, now)` gives **Cancelled**, **Finished**, **Upcoming** (start in the
future) or **In progress**, with one `now` per service call. No job and no write on read; tests
control the clock through `app.services.competitions.utc_now`.

**Time zones** (R4–R6, R10):

- **A small script, `time-zone.js`**, loaded by the base layout, writes the browser's IANA zone to
  the cookie `sc_time_zone`. It sends nothing and reloads nothing.
- **`app/core/time_zone.py`** accepts only names in `zoneinfo.available_timezones()`, adds
  `time_zone` to every template, and formats "14 March 2027, 10:00", or "… UTC" with no zone.
- **The form** carries the zone it was shown in as a hidden field; `app/schemas/competition.py`
  reads the date and time in that zone, refuses a time skipped by the clocks going forward, and
  takes the earlier of a repeated time (PEP 495 `fold=0`).
- **The runtime has the database**: the image built from today's `Dockerfile` carries Debian
  `tzdata` 2026b and loads `Europe/Kyiv`, so no dependency is added; a CI image step keeps it so.

**Services** (R7, R8, R11, R13, [contracts/services.md](./contracts/services.md)):

- **`app/services/competitions.py`** (new): the offered subjects (active, plus deactivated ones with
  a finished competition), one page of a subject's visible competitions filtered by status and
  sorted in Python (latest start first, then name), the landing after a change, and create, update
  and cancel.
- **Every write** checks the setting, the subject and the row again under lock, then changes the
  row with a conditional `UPDATE` whose row count tells a lost race, so "already cancelled" and
  "has already started" hold on both engines.
- **`count_subject_uses`** counts competitions, so a subject used by one cannot be deleted.

**Routes** (R9, R12, [contracts/http-routes.md](./contracts/http-routes.md)):

- **A new router, `app/routers/teacher_competitions.py`**, serves 7 endpoints under
  `/teacher/competitions`, all `@allow_roles(Role.TEACHER)`; the placeholder handler and template
  are removed.
- **Order of checks**: role → setting (before any value is read) → subject (404) → competition
  (404) → status (409 refusal) → fields (400).
- **The subject, status and page** travel in every address and form; returns land at
  `#competition-<id>`. Notices travel as a sealed token, so no competition name enters an address
  or a log.

**Components first** (R14, R15, [contracts/components.md](./contracts/components.md)). Each is
added to the library, the gallery and `ui-guidelines.md` before the tab uses it:

- **New**: `actions_menu` and `menu_link` (`components/menu.html`, a `<details>` like the user
  menu, 44 px entries); `date_time_fields` (`components/form.html`); `competition_status_badge`
  (`components/badge.html`, existing kinds); `local_time` (`components/time.html`).
- **Changed**: `confirmation` gains `back_label` (**Keep competition**); `chained_lists` and
  `select_field` gain option groups ("Deactivated subjects"); `.data-table` rounds its corner cells
  instead of clipping with `overflow: hidden`, so an open menu is never cut off.

**Tests** (R16): new unit modules for the start parsing and formatting, the zone helper and the
script; new integration modules for the service and the tab; updates to the route sweeps, the form
contract, the gallery, the layout, the migrations and the subject delete rule.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, Alembic, Pico.css v2.1.1 (vendored, not edited).
- Python's standard `zoneinfo`, reading the system time-zone database (Debian `tzdata` in the
  image; `/usr/share/zoneinfo` on macOS).
- No new runtime or development dependency.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision after `09cbcbe472be`: the `competitions` table
  ([data-model.md](./data-model.md) §7).
- One browser cookie, `sc_time_zone`, never stored on the server.

**Testing**:

- pytest on both engines.
- New modules:
  - `tests/unit/test_competition_schemas.py`;
  - `tests/unit/test_time_zone.py`;
  - `tests/unit/test_time_zone_script.py`;
  - `tests/integration/test_competition_service.py`;
  - `tests/integration/test_teacher_competitions.py`.
- Updated modules: routes, teacher access, form contract (+ `form_contract.json`, new
  `teacher-competition*` cases generated once), gallery, page patterns, layout, migrations, admin
  subjects, subject service, teacher classes (the placeholder test is replaced).
- Browser behaviour (the menu, the pickers, the script) is checked by hand or with an ad hoc
  Playwright run, as in milestone 10.1 ([quickstart.md](./quickstart.md) §5).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **The list**: one indexed query for a subject's competitions, then filtering, sorting and
  slicing in Python; a subject holds tens to a few hundred competitions.
- **A write**: three short locked reads and one conditional update.

**Constraints**:

- **Access before existence**: the setting is checked before any id or value is read (FR-042).
- **No JavaScript needed**: every page works without it, with times in UTC (FR-049).
- **Server-side time**: the browser only reports its zone (FR-019).
- **Stylesheet rules**: tokens only; the milestone 10 and 10.1 stylesheet checks stay green.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.

**Scale/Scope**:

- 1 migration, 1 new model, 1 new service module, 1 new schema module, 1 new core module.
- 1 new router with 7 endpoints; the placeholder handler and template removed.
- 5 new page templates (list, form, confirmation, refusal, not found).
- Components: 2 new component files (`menu.html`, `time.html`), 2 new macros in existing files
  (`date_time_fields`, `competition_status_badge`), 3 changed macros (`confirmation`,
  `chained_lists`, `select_field`), one changed table rule.
- 1 new script; the base layout loads it.
- 2 documents updated (UI guidelines, README); `milestones.md` on delivery; one CI step.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 11.1 is merged and delivered. 12.1 is the first rung of the 12.x group, one end-to-end slice: the subject list, the list, add, edit and cancel, from the tab down to the table. Nothing from later milestones is built: no questions or teams in a competition, no stopping, no student view, no results (FR-051). `stopped_at` is a column only, so the rules for **Finished** can be tested now, as the milestone asks. | ✅ |
| II. Server-rendered simplicity | Every page is rendered by Jinja on the server with plain `GET` and `POST`; no HTMX partials are needed. One small script is added (`time-zone.js`, about 15 lines, no build step, no dependency); it only reports the zone, and every page works without it. The menu is a native `<details>`. No new dependency. | ✅ |
| UI guidelines | Every page is built from the component library with design tokens only and follows `docs/requirements/ui-guidelines.md`. The new and changed patterns (actions menu, date and time fields, competition status badge, local time, the confirmation back label, option groups, the table corner rule) are each added to the library, the gallery (`/admin/components`) and `ui-guidelines.md` before the tab uses them (FR-048, FR-049; research R14, R15). No new colour token. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ list map to pytest cases on both engines (R16), with a controlled clock, so "start passing" is tested without waiting. Access tests cover all 7 routes, allowed and denied, per role and per setting, through addresses and submitted forms. The replaced placeholder test is named (SC-010). No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`; administrators and students get 403. Create, edit and cancel need **Can manage competitions**, checked first in the router and again under lock in the service (R8). Every teacher reads all competitions; there are no per-competition rights (the constitution's competition rule). Only upcoming competitions are editable; any competition that is not finished can be cancelled; a cancelled one never changes again (R2, R8). Competitions of a deactivated subject are hidden unless finished, which stay read-only (R11). | ✅ |
| V. Secure authentication & secrets | No change to sign-in, sessions or the cross-site check; every `POST` passes it (FR-044). Notices use the existing sealing with a purpose and a 10-minute lifetime (R12). The zone cookie holds no identifier and no secret, is validated against a fixed list, and is never logged. Logs carry ids only, never a competition name (FR-046). | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines and covered by the stairway and drift checks. Every time is stored timezone-aware in UTC; the entered local time is converted to UTC on the server before it is stored or compared, and back only for display (the constitution's rule, R6). The status is derived from the stored start, stop and cancel, as the constitution requires (R2). Competitions are never deleted, and a subject used by one cannot be (R11). Two engine-specific details are justified: the partial unique index (R3, the milestone 11.1 pattern) and row locks that render nothing on SQLite, backed by conditional updates that work on both (R8). | ✅ |
| Stack | Only listed technologies; `zoneinfo` is the standard library. Pico is restyled only through `app.css`. | ✅ |
| Application Layout | `models/` (table), `schemas/` (start parsing), `services/` (business logic), `core/` (the zone cookie and formatting, like the theme), `routers/` (thin), `templates/components/` (new macros), `templates/pages/teacher/` (pages), `static/js/` (the script). | ✅ |
| Governance and workflow | README (the tab, the cookie) and `ui-guidelines.md` are updated in the PR, and `milestones.md` moves 12.1 to Delivered on delivery. The schema change ships with its migration. No constitution amendment is needed. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: the contracts keep every check server-side, in the spec's order, with the setting
  before ids ([http-routes.md](./contracts/http-routes.md) §Order of checks), and again under lock
  ([services.md](./contracts/services.md) §Writes).
- **Components**: every new or changed component is in [components.md](./contracts/components.md)
  with its gallery section and guidelines change.
- **Data**: the data model adds no personal data; the zone cookie is never stored on the server.
- **Time**: every comparison is in UTC with the service's clock; display conversion is in one
  helper.

## Project Structure

### Documentation (this feature)

```text
specs/012.1-teacher-competitions/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R16
├── data-model.md           # Phase 1: the table, the derived status, the cookie, the migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # the /teacher/competitions routes, checks, statuses, redirects, pages
│   ├── services.md         # competitions, schemas/competition, core/time_zone, subjects, notices
│   └── components.md       # actions menu, date and time fields, status badge, local time, changes, script
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── core/
│   ├── time_zone.py             # NEW: sc_time_zone cookie, parse/read, format_local_time, utc_iso
│   └── templates.py             # + time_zone context processor; format_local_time, utc_iso globals
├── models/
│   ├── competition.py           # NEW: Competition, partial unique index, check constraint
│   └── __init__.py              # + Competition
├── schemas/
│   └── competition.py           # NEW: parse_start (zone, gap, overlap), local_parts
├── services/
│   ├── competitions.py          # NEW: status, offered subjects, page, landing, create/update/cancel
│   └── subjects.py              # count_subject_uses counts competitions
├── routers/
│   ├── teacher_competitions.py  # NEW: the Competitions tab, 7 endpoints, notices
│   ├── teacher.py               # placeholder handler removed
│   └── admin_components.py      # gallery sample data for the new components
├── templates/
│   ├── components/
│   │   ├── menu.html            # NEW: actions_menu, menu_link
│   │   ├── time.html            # NEW: local_time
│   │   ├── form.html            # + date_time_fields; select_field groups
│   │   ├── badge.html           # + competition_status_badge
│   │   ├── confirmation.html    # confirmation back_label
│   │   └── selectors.html       # chained_lists groups
│   ├── layouts/base.html        # loads time-zone.js
│   └── pages/
│       ├── admin/components.html             # new gallery sections and variants
│       └── teacher/
│           ├── competitions.html             # NEW: subject and status lists, navigation, table
│           ├── competition_form.html         # NEW: add and edit
│           ├── competition_cancel.html       # NEW: confirmation
│           ├── competition_refused.html      # NEW: edit and cancel refusals (409)
│           ├── competition_not_found.html    # NEW: 404 in the teacher frame
│           └── placeholder.html              # REMOVED
├── static/
│   ├── css/app.css              # actions menu, date-time fieldset, table corners
│   └── js/time-zone.js          # NEW
└── main.py                      # include teacher_competitions router

migrations/versions/2026_11_02_<rev>_competitions.py   # NEW

tests/
├── unit/test_competition_schemas.py          # NEW
├── unit/test_time_zone.py                    # NEW
├── unit/test_time_zone_script.py             # NEW
├── integration/test_competition_service.py   # NEW
├── integration/test_teacher_competitions.py  # NEW: the tab, end to end
└── (updated) test_routes, test_teacher_access, test_form_contract + form_contract.json,
    test_component_gallery, test_page_patterns, test_layout, test_migrations,
    test_admin_subjects, test_subject_service, test_teacher_classes, conftest.py (make_competition)

.github/workflows/checks.yml         # image job: the zoneinfo check
docs/requirements/ui-guidelines.md   # the new components, statuses, times, menus
README.md                            # the Competitions tab, the time-zone cookie
```

**Structure Decision**: the existing single FastAPI application layout. The tab follows the
milestone 11 **Questions** tab: one router per tab, `render_teacher` for the tab row, a service
that takes the teacher id and checks the setting inside its own transaction, return addresses from
one path helper, and the milestone 11.1 sealed notice. The time-zone cookie follows the milestone
10 theme cookie, in `app/core/`.

## Complexity Tracking

No constitution violations to justify. The engine-specific details are justified in research: the
partial unique index (R3) and row locks that render nothing on SQLite, backed by conditional
updates (R8). One script is added under Principle II's "minimal JavaScript, no build step" (R5).
