# Implementation Plan: Administrator Area — Teachers, Educational Institutions, Subjects (Milestone 6)

**Branch**: `006-admin-area` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-admin-area/spec.md`

## Summary

Turn milestone 5's administrator placeholder into a tabbed administrator area, and give the
**Subjects** tab real features.

**Area shell**:

- `ADMIN_TABS` in a new `app/routers/admin.py` declares the three tabs (Teachers, Educational
  institutions, Subjects), each with its own address.
- A new `templates/layouts/admin.html` renders the tab row. It marks the current tab with
  `aria-current="page"`.
- `GET /admin` answers `303` → `/admin/teachers`. Teachers and Educational institutions are
  placeholder pages.
- Tabs are ordinary links: no HTMX, no script.
- The home page link from milestone 5 is unchanged.

**Subjects**:

- A new `subjects` table: `name`, a unique `name_key` (`NFC(name).casefold()`), `is_active`, and
  timestamps.
  - The key gives case-insensitive uniqueness across all Unicode letters on both SQLite and
    PostgreSQL ("Фізика" = "ФІЗИКА").
  - The unique constraint, not a pre-check, is the guarantee against simultaneous submissions.
- The name is validated by one pure function. Control characters are checked on the raw value,
  then the name is trimmed and its length (1–200) is checked.
- A new `app/routers/admin_subjects.py` serves the list, the create and rename forms, the delete
  confirmation, and four `POST` actions: create, rename, deactivate/activate and delete.
  - It follows Post/Redirect/Get: `303` back to the list on success.
  - Errors re-render with the entered value: `400` for invalid or duplicate names, `409` for a
    refused deletion, and a `404` "Subject not found" page inside the area.
- Deletion is refused when `count_subject_uses` (one function, `0` until milestones 9 and 10) is
  above zero.

**Access**: every new route is `@allow_roles(Role.ADMIN)`. Milestone 5's `resolve_access` handles
the rest: sign-in redirect, role choice, current role only, 403, and the cross-site check on every
`POST`. Nothing is added to the public allowlist.

**Contraction**: the milestone's first migration drops the unused `users.role` column, as
milestone 5 committed (research D8).

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**: FastAPI, Jinja2, Pico.css, SQLModel, Alembic, psycopg 3,
python-multipart. All are already in `pyproject.toml`. **No new dependency.** Unicode handling
uses the standard library's `unicodedata`.

**Storage**: SQLite (local, tests) / PostgreSQL (production, Neon via Render). Two new Alembic
revisions: drop `users.role`, then create `subjects`.

**Testing**: pytest with FastAPI `TestClient`. Database tests run on both engines through the
existing `database_url` fixture. Signed-in clients come from `client_as` / `admin_client`
(milestone 5 test support).

**Target Platform**: Linux container on Render. Any modern browser, including phone width.

**Project Type**: Server-rendered web application (single FastAPI application).

**Performance Goals**: none beyond the defaults. The subject list holds tens of rows. Every page
makes at most two queries.

**Constraints**:

- Same behaviour on SQLite and PostgreSQL (Principle VII), hence the Python-computed key and the
  Python sort.
- No JavaScript.
- Every page must work with Post/Redirect/Get and survive a reload.

**Scale/Scope**:

- 5 new pages (2 placeholders, list, create/rename form, delete confirmation) and 1 not-found page.
- 6 new `POST` routes.
- 1 new table, 1 dropped column.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 5 is merged. This is one vertical slice: table → service → routes → pages → tests. Teachers and institutions stay placeholders (FR-041). Nothing from milestones 7, 9 or 10 is built. `count_subject_uses` is only the hook those milestones extend. | ✅ |
| II. Server-rendered simplicity | Jinja2 pages, plain forms and links, Pico.css. No HTMX, because none is needed (research D5). No custom JavaScript. No new dependency. No speculative abstraction: one usage-count function, no registry (research D4). | ✅ |
| III. Test-backed delivery | Unit tests for the name rules. Service tests on both engines. HTTP tests for every acceptance scenario of US1–US4. Allowed and denied access per role for every new route. Migration stairway and drift tests. No external service involved. | ✅ |
| IV. Role-based access | Every route is `@allow_roles(Role.ADMIN)`, enforced server-side by `resolve_access`, and judged by the current role. The route-table sweep keeps deny-by-default. Only administrators edit the subject list (product requirements). | ✅ |
| V. Secure authentication & secrets | No change to sign-in. Every new `POST` goes through the existing application-wide cross-site check (FR-034). Logs carry subject ids only. No new secret. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | `Subject` is a SQLModel model with Alembic migrations. Portable SQL only: the unique key is computed in Python (research D1), and sorting is done in Python (research D3). Timestamps use `UTCDateTime`. A subject in use can never be deleted (FR-029, FR-030). This protects future questions and competitions from orphaned references. | ✅ |
| Workflow gates | The plan lists the role-access tests, the migrations and the README update. | ✅ |

**Post-design re-check (after Phase 1)**: still all ✅. The design added no dependency, no
engine-specific SQL and no public route. The one deliberate test change, relaxing the
"allowed role sees 200" sweep to "allowed role is not denied", keeps deny-by-default exact. It is
justified in research D9 and backed by explicit per-page status tests.

## Project Structure

### Documentation (this feature)

```text
specs/006-admin-area/
├── plan.md                      # This file
├── research.md                  # Phase 0: decisions D1–D10
├── data-model.md                # Phase 1: subjects table, users change, revisions, tabs
├── quickstart.md                # Phase 1: automated and manual validation
├── contracts/
│   ├── http-routes.md           # Phase 1: every route, status and page
│   └── subject-service.md       # Phase 1: schema functions and service interface
├── checklists/requirements.md   # From /speckit-specify
└── tasks.md                     # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── __init__.py              # CHANGED: export Subject
│   ├── subject.py               # NEW: Subject table
│   └── user.py                  # CHANGED: remove legacy_role and its docstring
├── schemas/
│   └── subject.py               # NEW: limits, SubjectNameError, clean_subject_name, subject_name_key
├── services/
│   └── subjects.py              # NEW: list/get/create/rename/set_active/count_uses/delete + errors
├── routers/
│   ├── admin.py                 # NEW: ADMIN_TABS, GET /admin redirect, two placeholder tabs
│   ├── admin_subjects.py        # NEW: /admin/subjects pages and actions
│   └── areas.py                 # CHANGED: drop the admin_area handler; ADMIN_AREA stays in AREAS
├── main.py                      # CHANGED: include admin and admin_subjects routers
├── templates/
│   ├── layouts/admin.html       # NEW: base + tab row
│   └── pages/admin/
│       ├── placeholder.html     # NEW: Teachers / Educational institutions
│       ├── subjects.html        # NEW: list
│       ├── subject_form.html    # NEW: create and rename (one template, two modes)
│       ├── subject_delete.html  # NEW: confirmation, and the in-use refusal
│       └── subject_not_found.html  # NEW: 404 inside the area
└── static/css/app.css           # CHANGED: .admin-tabs, current-tab highlight, subject table

migrations/versions/
├── 2026_10_xx_<rev>_drop_legacy_user_role.py   # NEW
└── 2026_10_xx_<rev>_create_subjects.py         # NEW

tests/
├── unit/
│   └── test_subject_schemas.py          # NEW
└── integration/
    ├── test_subject_service.py          # NEW
    ├── test_admin_area.py               # NEW: tabs, redirect, placeholders, no tabs elsewhere
    ├── test_admin_subjects.py           # NEW: US1/US2 over HTTP
    ├── test_routes.py                   # CHANGED: write-route list; sweep relaxed (research D9)
    ├── test_access_control.py           # CHANGED: /admin → /admin/teachers in the table; new admin routes × roles
    ├── test_cross_site.py               # CHANGED: a cross-site subject POST is refused
    ├── test_migrations.py               # CHANGED: APPLICATION_TABLES += subjects; milestone 5 tests pinned to 50f17535d874
    └── test_user_reconcile.py           # CHANGED: drop the legacy_role case (s8)

README.md                                # CHANGED: "Roles and access" mentions the admin area tabs and subjects
```

**Structure Decision**: the existing single-application layout from the constitution, with no new
top-level directories.

- The area shell (`admin.py`) and the Subjects tab (`admin_subjects.py`) are separate routers, so
  milestone 7 can add `admin_teachers.py` and `admin_institutions.py` beside them without editing
  the subject code.
- Business rules live in `services/subjects.py` and `schemas/subject.py`. Routers only parse the
  form, call the service, map its exceptions to a status and template, and redirect.

### Changes to existing tests (why they change)

| Test | Change | Reason |
|---|---|---|
| `test_routes.py::test_the_write_routes_are_exactly_…` | Add the six `POST /admin/subjects…` routes. | The write surface grows on purpose. The test still pins it exactly. |
| `test_routes.py::test_every_declared_page_admits_exactly_its_roles` | Allowed role: status ≠ 403. Denied role: 403. | `/admin` is now a 303, and `/admin/subjects/1/…` is a 404 with no subject 1 (research D9). |
| `test_access_control.py` | `ACCESS_TABLE` and `TITLES` use `/admin/teachers`. Add: `/admin` → 303 `/admin/teachers` for administrators, 403 for others. The `HOME_LINKS` "Administrator area" link still points to `/admin`. Update the denied-log assertion (`route=/admin`) if it targets the placeholder. | The placeholder is gone. The redirect is the new contract. |
| `test_migrations.py` | Add `subjects` to `APPLICATION_TABLES`. Pin `test_upgrade_keeps_the_active_administrators` and `test_downgrade_deactivates_…` to revision `50f17535d874` instead of `head`. | At head, `users.role` no longer exists, and those tests insert into it. |
| `test_user_reconcile.py::test_s8_a_migrated_administrator_is_unchanged` | Remove the `legacy_role=` argument, or the whole case if it adds nothing over s1. | The model field is gone. |
| `test_user_reconcile.py` line 87 | Remove the `legacy_role is None` assertion. | Same. |

## Implementation Order (for /speckit-tasks)

1. **Contraction**: migration that drops `users.role`, the model change, and the test fixes.
   The suite is green.
2. **Subject foundation** (blocks US1 and US2):
   - `schemas/subject.py` and its unit tests;
   - `models/subject.py` and the `create_subjects` migration (drift and stairway green);
   - `services/subjects.py` and its service tests.
3. **US3 shell** (blocks the UI of US1 and US2):
   - `admin.py` with `ADMIN_TABS`, the redirect and the placeholders;
   - `layouts/admin.html`, the placeholder template and the CSS;
   - remove the `/admin` handler from `areas.py`;
   - update `test_routes.py` and `test_access_control.py`, and add `test_admin_area.py`.
4. **US1**: the list, the create form and `POST /admin/subjects`, with the HTTP tests.
5. **US2**: rename, deactivate/activate and delete (confirmation, in-use refusal, not-found page),
   with the HTTP tests.
6. **US4**: role × route matrix for every new route and action, the cross-site `POST` test, and
   "nothing changed" assertions.
7. **Docs and polish**: README; `ruff`; manual walk-through ([quickstart.md](./quickstart.md)).

## Complexity Tracking

> No constitution violations. Two choices that look like extra complexity are recorded here.

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| Extra `name_key` column next to `name` | Unicode-correct, case-insensitive uniqueness that behaves the same on SQLite and PostgreSQL, and is enforced by a constraint under concurrency (research D1). | `UNIQUE(lower(name))` folds only ASCII on SQLite and depends on the locale on PostgreSQL. A service-only check races. |
| Sorting in Python rather than `ORDER BY` | The same order on both engines (research D3). | `ORDER BY` follows each engine's collation, so tests and production would disagree. |
