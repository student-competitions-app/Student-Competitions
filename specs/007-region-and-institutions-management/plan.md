# Implementation Plan: Administrator Area — Regions and Educational Institutions (Milestone 7)

**Branch**: `007-region-and-institutions-management` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-region-and-institutions-management/spec.md`

## Summary

Replace milestone 6's **Educational institutions** placeholder with two lists side by side:
regions on the left, and the institutions of the selected region on the right.

**Data**: two new tables in one Alembic revision (research D14).

- `regions`: `name`, a unique `name_key` (`NFC(name).casefold()`), `is_active` and timestamps.
  This is the subject pattern from milestone 6 (research D2).
- `institutions`: the same columns plus `region_id` (`NOT NULL`, foreign key to `regions`, no
  cascade). Uniqueness is `UNIQUE (region_id, name_key)`, so a name is unique within a region and
  may repeat across regions (research D3).
- The two statuses are independent. "Available for selection" (both active) is a rule recorded for
  milestone 8, not a column or a function (research D10).

**Name rules**: the milestone 6 rules move unchanged into a shared `app/schemas/names.py`.
`app/schemas/subject.py` keeps aliases, so no subject code or test changes (research D1).

**Services**: `app/services/regions.py` and `app/services/institutions.py` follow
`app/services/subjects.py`: list, get, create, rename, set active, delete. They also add:

- `delete_region` is refused while `count_region_institutions > 0` (FR-036).
- `create_institution` locks the region row (`with_for_update`). It refuses a missing or
  deactivated region (FR-024, SC-007; research D5).
- Every institution function takes `(region_id, institution_id)`. A mismatch is "not found", so
  an institution can never be moved (FR-030; research D7).
- `count_institution_uses` returns `0` until milestones 8 and 9 extend it (FR-037, FR-038;
  research D9).

**Routes**: a new `app/routers/admin_institutions.py`, with 8 `GET` and 10 `POST` routes under
`/admin/institutions`.

- The selected region is in the path, `/admin/institutions/regions/{id}`, so it survives reloads,
  bookmarks and the sign-in redirect (FR-003, FR-046; research D7).
- Post/Redirect/Get, back to the relevant region (research D8).
- Errors re-render: `400` for invalid or duplicate names, `409` for refused state changes, and
  `404` for the friendly "Region not found" and "Educational institution not found" pages.
- Plain links and forms. No HTMX, no script.

**Access**: every new route is `@allow_roles(Role.ADMIN)`. Milestone 5's `resolve_access`
handles the rest: sign-in redirect, role choice, current role only, 403, and the cross-site check
on every `POST`.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**: FastAPI, Jinja2, Pico.css, SQLModel, Alembic, psycopg 3,
python-multipart. All are already in `pyproject.toml`. **No new dependency.**

**Storage**: SQLite (local, tests) / PostgreSQL (production, Neon via Render). One new Alembic
revision on top of `2a84d288f9e6`: create `regions` and `institutions`.

**Testing**: pytest with FastAPI `TestClient`. Database tests run on both engines through the
existing `database_url` fixture. Signed-in clients come from `client_as` / `admin_client`.

**Target Platform**: Linux container on Render. Any modern browser, including phone width.

**Project Type**: Server-rendered web application (single FastAPI application).

**Performance Goals**: none beyond the defaults. Both lists hold tens of rows (spec Assumptions).
The tab page makes at most three queries: regions, the selected region, and its institutions.

**Constraints**:

- Same behaviour on SQLite and PostgreSQL (Principle VII). Keys are computed in Python, sorting is
  done in Python, and `with_for_update` is a no-op on SQLite.
- SQLite does not enforce foreign keys here, so every integrity rule is checked in the service
  (research D4).
- No JavaScript. Post/Redirect/Get. Every page survives a reload.

**Scale/Scope**:

- 8 new `GET` pages: the tab, the tab with a region, 2 region forms, 2 institution forms, and 2
  confirmations. Plus 2 not-found pages and 1 refusal page.
- 10 new `POST` routes.
- 2 new tables. 1 placeholder handler removed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 6 is merged into `main` (its subjects code and migrations are on this branch's base). This is one vertical slice: tables → services → routes → pages → tests. Teachers stays a placeholder, and Subjects is unchanged (FR-049). Nothing from milestones 8 and 9 is built: no picker, no availability helper. `count_institution_uses` is only the hook those milestones extend. | ✅ |
| II. Server-rendered simplicity | Jinja2 pages, plain links and forms, and Pico.css with a few override rules. No HTMX, because none is needed (research D7). No custom JavaScript. No new dependency. The one new abstraction, shared name rules, has three present users (research D1). | ✅ |
| III. Test-backed delivery | Unit tests for the shared name rules. Service tests on both engines. HTTP tests for every acceptance scenario of US1–US5. Allowed and denied access per role for every new route. Migration stairway and drift tests. No external service involved. | ✅ |
| IV. Role-based access | Every route is `@allow_roles(Role.ADMIN)`, enforced server-side and judged by the current role. The route-table sweeps keep deny-by-default. "Only administrators edit the institution list" is now real. | ✅ |
| V. Secure authentication & secrets | No change to sign-in. Every new `POST` goes through the application-wide cross-site check (FR-042). Logs carry ids only. No new secret. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | Two SQLModel models and one Alembic revision. Portable SQL only (research D2–D6). Timestamps use `UTCDateTime`. A region holding institutions, or an institution in use, can never be deleted. The PostgreSQL foreign key is a backstop against orphans (FR-038). | ✅ |
| Workflow gates | The plan lists the role-access tests, the migration and the README update. | ✅ |

**Post-design re-check (after Phase 1)**: still all ✅.

- No dependency, no engine-specific SQL and no public route was added.
- `with_for_update` is a SQLAlchemy construct that renders on PostgreSQL and is omitted on SQLite.
  It needs no `plan.md` justification as a database-specific feature, because behaviour on SQLite
  stays correct (SQLite serialises writers).
- The one change to milestone 6 code (moving the name rules) keeps every public subject name and
  every subject test unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/007-region-and-institutions-management/
├── plan.md                        # This file
├── research.md                    # Phase 0: decisions D1–D14
├── data-model.md                  # Phase 1: regions, institutions, shared name rules, revision
├── quickstart.md                  # Phase 1: automated and manual validation
├── contracts/
│   ├── http-routes.md             # Phase 1: every route, status and page
│   └── institution-service.md     # Phase 1: name rules, region and institution services
├── checklists/requirements.md     # From /speckit-specify
└── tasks.md                       # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── __init__.py                # CHANGED: export Region, Institution
│   ├── region.py                  # NEW: Region table
│   └── institution.py             # NEW: Institution table (region_id FK, UNIQUE(region_id, name_key))
├── schemas/
│   ├── names.py                   # NEW: NAME_*_LENGTH, InvalidName, clean_name, name_key (moved)
│   └── subject.py                 # CHANGED: now aliases of app.schemas.names (no behaviour change)
├── services/
│   ├── regions.py                 # NEW: list/get/create/rename/set_active/count_institutions/delete + errors
│   └── institutions.py            # NEW: list/get/create/rename/set_active/count_uses/delete + errors
├── routers/
│   ├── admin.py                   # CHANGED: remove the admin_institutions placeholder handler
│   └── admin_institutions.py      # NEW: /admin/institutions pages and actions
├── main.py                        # CHANGED: include admin_institutions router
├── templates/pages/admin/
│   ├── institutions.html          # NEW: the two lists (with or without a selected region)
│   ├── region_form.html           # NEW: create and rename region
│   ├── region_delete.html         # NEW: confirmation, and the "still holds institutions" refusal
│   ├── institution_form.html      # NEW: create and rename institution; deactivated-region refusal
│   ├── institution_delete.html    # NEW: confirmation, and the in-use refusal
│   └── institutions_not_found.html  # NEW: "Region not found" / "Educational institution not found"
└── static/css/app.css             # CHANGED: .institutions-layout, .regions-list, selected highlight

migrations/versions/
└── 2026_10_xx_<rev>_create_regions_and_institutions.py   # NEW

tests/
├── unit/
│   └── test_name_schemas.py               # NEW
└── integration/
    ├── test_region_service.py             # NEW
    ├── test_institution_service.py        # NEW
    ├── test_admin_institutions.py         # NEW: US1–US4 over HTTP
    ├── test_admin_area.py                 # CHANGED: institutions no longer a placeholder; tab marked on every new page
    ├── test_routes.py                     # CHANGED: write-route list += 10 POSTs
    ├── test_access_control.py             # CHANGED: new pages/actions × roles; anonymous return with region
    ├── test_cross_site.py                 # CHANGED: a cross-site region and institution POST are refused
    └── test_migrations.py                 # CHANGED: APPLICATION_TABLES += regions, institutions

README.md                                  # CHANGED: "Roles and access" paragraph; repository layout
```

**Structure Decision**: the existing single-application layout from the constitution, with no new
top-level directories.

- One router module per tab, as milestone 6 set up (`admin_subjects.py`, now
  `admin_institutions.py`). The shell (`admin.py`) only loses a placeholder handler.
- Two service modules, one per entity. `regions.py` does not import `institutions.py`. It counts
  institutions with a query on the `Institution` model. `institutions.py` imports
  `regions.get_region` and `RegionNotFound`. No import cycle.
- Templates are flat in `pages/admin/`, like the subject templates.

### Changes to existing tests (why they change)

| Test | Change | Reason |
|---|---|---|
| `test_admin_area.py` `PLACEHOLDERS` | Remove `/admin/institutions`. Teachers stays. | The placeholder is replaced (SC-009 allows this). |
| `test_admin_area.py` | Add: every page of this feature (tab, region page, forms, confirmations, both not-found pages) shows the tab row with **Educational institutions** current, exactly once. | FR-005. |
| `test_routes.py::test_the_write_routes_are_exact` | Add the 10 `POST` routes. | The write surface grows on purpose, and is still pinned exactly. |
| `test_routes.py` declared-page sweep | No change. `_concrete` makes `/admin/institutions/regions/1`, which is a `404` for an administrator (≠ 403) and a `403` for the others. | Already relaxed in milestone 6 (research D9 there). |
| `test_access_control.py` | Add `ADMIN_PAGES` / `ADMIN_ACTIONS` rows for regions and institutions, with region and institution rows compared before and after each refusal. Add the anonymous round trip to `/admin/institutions/regions/{id}`. `ADMIN_TAB_LINKS` is unchanged. | US5, FR-044–FR-047. |
| `test_cross_site.py` | Add: a cross-site `POST /admin/institutions/regions` and a cross-site institution delete are refused, and nothing changes. | FR-042. |
| `test_migrations.py` | `APPLICATION_TABLES` += `regions`, `institutions`. | Stairway and drift include the new tables. |

## Implementation Order (for /speckit-tasks)

1. **Shared name rules**: `schemas/names.py`, then `schemas/subject.py` as aliases, then
   `test_name_schemas.py`. The existing subject tests stay green unchanged.
2. **Foundation** (blocks every story):
   - `models/region.py`, `models/institution.py` and the migration (drift and stairway green);
   - `services/regions.py` with its service tests;
   - `services/institutions.py` with its service tests.
3. **Tab shell**:
   - remove the placeholder handler from `admin.py`;
   - add `admin_institutions.py` with `GET /admin/institutions` and `GET R`;
   - add `institutions.html`, the not-found template and the CSS;
   - update `test_admin_area.py`.
4. **US1**: region create form and `POST`, with HTTP tests.
5. **US2**: institution create form and `POST`, including the deactivated-region refusal, with
   HTTP tests.
6. **US3**: region rename, deactivate/activate and delete (confirmation, not-empty refusal), with
   HTTP tests.
7. **US4**: institution rename, deactivate/activate and delete (confirmation, in-use refusal,
   wrong-region 404), with HTTP tests.
8. **US5**: role × route matrix for every new route, the anonymous round trip with a region
   selected, the cross-site `POST` tests, and the write-route list in `test_routes.py`.
9. **Docs and polish**: README; `ruff`; manual walk-through ([quickstart.md](./quickstart.md)).

## Complexity Tracking

> No constitution violations. Choices that look like extra complexity are recorded here.

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| `SELECT … FOR UPDATE` on the region when creating an institution | SC-007 is absolute: no institution in a deactivated region, even when a deactivation runs at the same moment (research D5). | A check without a lock lets a concurrent deactivation slip between the check and the insert on PostgreSQL. |
| Explicitly named composite unique constraint | The project naming convention only uses the first column, which would give the misleading name `uq_institutions_region_id` (research D3). | Changing the global convention affects every table for one constraint. |
| Moving the name rules to `schemas/names.py`, with aliases left in `schemas/subject.py` | Three entities share identical rules (research D1). | Copying the rules lets them drift. Renaming every subject call touches milestone 6 code for no gain. |
