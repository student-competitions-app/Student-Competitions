# Implementation Plan: Administrator Area — Educational Institutions (Milestone 7)

**Branch**: `007-institutions` | **Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-institutions/spec.md`

## Summary

Turn milestone 6's **Educational institutions** placeholder into the list of educational
institutions. The technical requirements say the tab "works the same way as the **Subjects**
tab", so the design copies the subject design one for one, with one piece shared.

**Shared name rules** (research D1):

- The pure name rules move from `app/schemas/subject.py` into a new `app/schemas/names.py`
  (`clean_name`, `name_key`, `NameRuleError`, the 200/600 limits).
- `app/schemas/subject.py` keeps its public names as aliases, so no milestone 6 code or test
  changes. A new `app/schemas/institution.py` does the same for institutions.

**Institutions** (research D2–D5):

- A new `institutions` table: `name`, a unique `name_key` (`NFC(name).casefold()`), `is_active`,
  and timestamps. One Alembic revision on top of `create_subjects`.
- `app/services/institutions.py` mirrors `app/services/subjects.py`: list, get, create, rename,
  activate/deactivate and delete, with `InstitutionNotFound`, `DuplicateInstitutionName` and
  `InstitutionInUse`.
- Deletion is refused when `count_institution_uses` is above zero. It returns `0` until milestones
  8 (teacher links) and 9 (student details) extend it.
- Other records will refer to institutions by `id` only, so a rename never breaks a link.
- `app/routers/admin_institutions.py` serves the list, the create and rename forms, the delete
  confirmation, and five `POST` actions. It follows Post/Redirect/Get: `303` back to the list on
  success, `400` for an invalid or duplicate name, `409` for a refused deletion, and a `404`
  "Educational institution not found" page inside the area.
- The placeholder handler for `/admin/institutions` is removed from `app/routers/admin.py`. The tab
  row, the `/admin` redirect and the Teachers placeholder are unchanged.

**Access**: every new route is `@allow_roles(Role.ADMIN)`. Milestone 5's `resolve_access` handles
the rest: sign-in redirect, role choice, current role only, 403, and the cross-site check on every
`POST`. Nothing is added to the public allowlist.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**: FastAPI, Jinja2, Pico.css, SQLModel, Alembic, psycopg 3,
python-multipart. All are already in `pyproject.toml`. **No new dependency.**

**Storage**: SQLite (local, tests) / PostgreSQL (production, Neon via Render). One new Alembic
revision: create `institutions`.

**Testing**: pytest with FastAPI `TestClient`. Database tests run on both engines through the
existing `database_url` fixture. Signed-in clients come from `client_as` / `admin_client`
(milestone 5 test support).

**Target Platform**: Linux container on Render. Any modern browser, including phone width.

**Project Type**: Server-rendered web application (single FastAPI application).

**Performance Goals**: none beyond the defaults. The institution list holds tens of rows. Every
page makes at most two queries.

**Constraints**:

- Same behaviour on SQLite and PostgreSQL (Principle VII), hence the Python-computed key and the
  Python sort, as for subjects.
- No JavaScript.
- Every page must work with Post/Redirect/Get and survive a reload.

**Scale/Scope**:

- 3 new pages (list, create/rename form, delete confirmation) and 1 not-found page. The list
  replaces a placeholder.
- 5 new `POST` routes.
- 1 new table. 1 module of shared name rules, moved from the subject schema.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 6 is merged (`162c787`). This is one vertical slice: table → service → routes → pages → tests. Teachers stays a placeholder. Nothing from milestones 8 or 9 is built: no links, no "active only" query (research D6). `count_institution_uses` is only the hook those milestones extend. | ✅ |
| II. Server-rendered simplicity | Jinja2 pages, plain forms and links, Pico.css. No HTMX, no custom JavaScript, no new dependency. One shared module for the name rules, which now have two users (research D1). No generic catalog service or router, because the two lists' futures differ (research D2). | ✅ |
| III. Test-backed delivery | Service tests on both engines. HTTP tests for every acceptance scenario of US1–US3. Allowed and denied access per role for every new route. Migration stairway and drift tests. No external service involved. | ✅ |
| IV. Role-based access | Every route is `@allow_roles(Role.ADMIN)`, enforced server-side by `resolve_access` and judged by the current role. The route-table sweep keeps deny-by-default. Only administrators edit the institution list (product requirements, constitution IV). | ✅ |
| V. Secure authentication & secrets | No change to sign-in. Every new `POST` goes through the existing application-wide cross-site check (FR-029). Logs carry institution ids only. No new secret. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | `Institution` is a SQLModel model with an Alembic migration. Portable SQL only. Timestamps use `UTCDateTime`. An institution in use can never be deleted (FR-024, FR-025), and links will use `id` (FR-018). This protects milestone 8 and 9 links from orphaned references. | ✅ |
| Workflow gates | The plan lists the role-access tests, the migration and the README update. | ✅ |

**Post-design re-check (after Phase 1)**: still all ✅. The design added no dependency, no
engine-specific SQL and no public route. The only change to milestone 6 code outside the
placeholder is the move of the name rules behind unchanged aliases (research D1). Its
behaviour is pinned by the existing `test_subject_schemas.py`.

## Project Structure

### Documentation (this feature)

```text
specs/007-institutions/
├── plan.md                         # This file
├── research.md                     # Phase 0: decisions D1–D10
├── data-model.md                   # Phase 1: institutions table, shared name rules, revision
├── quickstart.md                   # Phase 1: automated and manual validation
├── contracts/
│   ├── http-routes.md              # Phase 1: every route, status and page
│   └── institution-service.md      # Phase 1: name rules and service interface
├── checklists/requirements.md      # From /speckit-specify
└── tasks.md                        # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── __init__.py                   # CHANGED: export Institution
│   └── institution.py                # NEW: Institution table
├── schemas/
│   ├── names.py                      # NEW: limits, NameRuleError, clean_name, name_key (moved)
│   ├── subject.py                    # CHANGED: aliases of app.schemas.names; same public names
│   └── institution.py                # NEW: aliases of app.schemas.names
├── services/
│   └── institutions.py               # NEW: list/get/create/rename/set_active/count_uses/delete + errors
├── routers/
│   ├── admin.py                      # CHANGED: drop the /admin/institutions placeholder; docstring
│   └── admin_institutions.py         # NEW: /admin/institutions pages and actions
├── main.py                           # CHANGED: include admin_institutions router
├── templates/pages/admin/
│   ├── institutions.html             # NEW: list
│   ├── institution_form.html         # NEW: create and rename (one template, two modes)
│   ├── institution_delete.html       # NEW: confirmation, and the in-use refusal
│   └── institution_not_found.html    # NEW: 404 inside the area
└── static/css/app.css                # CHANGED: subject list rules also match .institutions-*

migrations/versions/
└── 2026_10_xx_<rev>_create_institutions.py   # NEW, down_revision 2a84d288f9e6

tests/
├── unit/
│   └── test_name_rules.py                    # NEW: both schemas alias the shared rules
└── integration/
    ├── test_institution_service.py           # NEW
    ├── test_admin_institutions.py            # NEW: US1/US2 over HTTP
    ├── test_admin_area.py                    # CHANGED: institutions is no longer a placeholder
    ├── test_routes.py                        # CHANGED: write-route list += 5 institution POSTs
    ├── test_access_control.py                # CHANGED: institution pages/actions × roles
    ├── test_cross_site.py                    # CHANGED: a cross-site institution POST is refused
    └── test_migrations.py                    # CHANGED: APPLICATION_TABLES += institutions

README.md                                     # CHANGED: admin area text, project tree
```

**Structure Decision**: the existing single-application layout from the constitution, with no new
top-level directories.

- The Institutions tab lives in its own router, beside `admin_subjects.py`, as milestone 6
  planned. The area shell (`admin.py`) only loses a placeholder.
- Business rules live in `services/institutions.py` and the shared `schemas/names.py`. Routers only
  parse the form, call the service, map its exceptions to a status and template, and redirect.

### Changes to existing tests (why they change)

| Test | Change | Reason |
|---|---|---|
| `test_admin_area.py` | Remove `/admin/institutions` from `PLACEHOLDERS`. Add a test that every institution page (list, new, rename, delete, not found) marks only the **Educational institutions** tab current. | The placeholder is gone (SC-008 allows this). FR-005. |
| `test_routes.py::test_the_write_routes_are_exactly_…` | Add the five `POST /admin/institutions…` routes. | The write surface grows on purpose. The test still pins it exactly. |
| `test_access_control.py` | Add institution page and action paths with an `institution_id` fixture and `institution_rows` before/after comparison. Add an administrator-using-teacher case for `/admin/institutions`. | US3: every new page and action refuses every non-administrator role and changes nothing. |
| `test_cross_site.py` | Add a cross-site institution case alongside the subject one. | FR-029. |
| `test_migrations.py` | Add `institutions` to `APPLICATION_TABLES`. | The new table. |

## Implementation Order (for /speckit-tasks)

1. **Shared name rules**: `schemas/names.py`, then turn `schemas/subject.py` into aliases, add
   `schemas/institution.py` and `tests/unit/test_name_rules.py`. The whole suite, including
   `test_subject_schemas.py`, is green and unchanged.
2. **Institution foundation** (blocks US1 and US2):
   - `models/institution.py` and the `create_institutions` migration (drift and stairway green,
     `APPLICATION_TABLES` updated);
   - `services/institutions.py` and its service tests.
3. **US1**: the list (replacing the placeholder in `admin.py`), the create form and
   `POST /admin/institutions`, the CSS rules, with the HTTP tests and the `test_admin_area.py`
   changes.
4. **US2**: rename, deactivate/activate and delete (confirmation, in-use refusal, not-found page),
   with the HTTP tests.
5. **US3**: role × route matrix for every new route and action, the write-route list, the
   cross-site `POST` test, and "nothing changed" assertions.
6. **Docs and polish**: README; `ruff`; manual walk-through ([quickstart.md](./quickstart.md)).

## Complexity Tracking

> No constitution violations. One choice that adds a module is recorded here.

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| New `app/schemas/names.py` with subject and institution aliases | Subjects and institutions must follow identical name rules (FR-007 to FR-009). One implementation means the Unicode handling cannot drift between them (research D1). | Copying the subject rules duplicates the most subtle code of milestone 6. Renaming the subject functions churns milestone 6 code and tests. |
