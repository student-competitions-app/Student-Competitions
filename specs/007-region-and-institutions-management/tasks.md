---

description: "Task list for milestone 7: regions and educational institutions"
---

# Tasks: Administrator Area — Regions and Educational Institutions (Milestone 7)

**Input**: Design documents from `/specs/007-region-and-institutions-management/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/institution-service.md](./contracts/institution-service.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-048 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. Every database test runs on SQLite, and also on
PostgreSQL when `TEST_POSTGRES_URL` is set, through the existing `database_url` / `session` /
`client` fixtures in `tests/conftest.py`. Signed-in clients come from `admin_client` and
`client_as`.

**Organization**: tasks are grouped by user story. Service functions, routes and template parts
are added in the story that first needs them, so each story is a working, testable increment.

**Reference implementation**: milestone 6's Subjects tab is the pattern for everything here. Read
these before starting:

- `app/models/subject.py`, `app/schemas/subject.py`, `app/services/subjects.py`;
- `app/routers/admin.py`, `app/routers/admin_subjects.py`;
- `app/templates/pages/admin/subject_*.html`, `subjects.html`;
- `migrations/versions/2026_10_02_2a84d288f9e6_create_subjects.py`;
- `tests/integration/test_subject_service.py`, `test_admin_subjects.py`, `test_admin_area.py`,
  `test_access_control.py`.

Match their docstring style, naming, comment density and error handling.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US5)

In the tasks below, `R` = `/admin/institutions/regions/{region_id:int}` and
`I` = `R/institutions/{institution_id:int}`. Route paths in `app/routers/admin_institutions.py`
are relative to the router prefix `/admin/institutions`.

---

## Phase 1: Setup (Shared name rules)

**Purpose**: one set of name rules for subjects, regions and institutions (research D1), with no
change to subject behaviour.

- [ ] T001 Create `app/schemas/names.py` by moving the body of `app/schemas/subject.py` into it under generic names: `NAME_MAX_LENGTH = 200`, `NAME_KEY_MAX_LENGTH = 600` (keep the "3 × 200" docstring), `class InvalidName(ValueError)` with `.message`, `_CONTROL_CATEGORIES`, `_is_control`, `clean_name(raw: str) -> str` and `name_key(name: str) -> str`. Keep the rules, their order and the messages exactly: "The name cannot contain tabs, line breaks or other control characters." (any character of the raw value in Unicode category `C*`, `Zl` or `Zp`), then `str.strip()`, then "Enter a name." (empty after trimming), then "The name can be at most 200 characters." (over 200 code points). `name_key` is `unicodedata.normalize("NFC", name).casefold()`. The module docstring says it is shared by subjects, regions and institutions, and points to specs/007-region-and-institutions-management/research.md D1.
- [ ] T002 Rewrite `app/schemas/subject.py` as aliases of `app/schemas/names.py`: `SUBJECT_NAME_MAX_LENGTH = NAME_MAX_LENGTH`, `SUBJECT_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH`, `SubjectNameError = InvalidName`, `clean_subject_name = clean_name`, `subject_name_key = name_key`. Keep a short docstring explaining the aliases. No other file changes. `tests/unit/test_subject_schemas.py` must pass unchanged (depends on T001).
- [ ] T003 [P] Create `tests/unit/test_name_schemas.py`. Assert that the subject names are the shared objects (`SubjectNameError is InvalidName`, `clean_subject_name is clean_name`, `subject_name_key is name_key`, and the equal length constants). Spot-check `clean_name` and `name_key` directly: "  Kyiv  " → "Kyiv"; "Kyiv  Region" keeps both inner spaces; `name_key("Київ") == name_key("КИЇВ")`; 200 characters accepted, 201 refused; "\tKyiv" refused with the control-character message (depends on T001, T002).

**Checkpoint**: `uv run pytest tests/unit` is green. Subject behaviour is unchanged.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the tables, the read-side services, and the tab page that shows the two lists. Every
user story builds on these.

**⚠️ CRITICAL**: no user story can start until this phase is complete.

### Tables and migration

- [ ] T004 [P] Create `app/models/region.py` with `class Region(SQLModel, table=True)`, `__tablename__ = "regions"`, modelled on `app/models/subject.py`:
  - `id: int | None` primary key;
  - `name`: `Column(String(NAME_MAX_LENGTH), nullable=False)`, "As entered after trimming. Shown everywhere.";
  - `name_key`: `Column(String(NAME_KEY_MAX_LENGTH), nullable=False, unique=True)`, "`name_key(name)`. Never shown.";
  - `is_active: bool` default `True`, not null;
  - `created_at` / `updated_at` with `default_factory=utc_now`, `sa_type=UTCDateTime`, not null.

  Import the limits from `app.schemas.names`. The module docstring links to data-model.md §1, and says a region cannot be deleted while it holds institutions and that deactivating it never changes its institutions' statuses.
- [ ] T005 [P] Create `app/models/institution.py` with `class Institution(SQLModel, table=True)`, `__tablename__ = "institutions"`:
  - `id` primary key;
  - `region_id: int = Field(foreign_key="regions.id", nullable=False)`, with a docstring saying it is set at creation and never changed (FR-030);
  - `name`, `name_key` (both `nullable=False`, lengths from `app.schemas.names`; `name_key` NOT individually unique);
  - `is_active` default `True`;
  - `created_at` / `updated_at` as in `Region`;
  - `__table_args__ = (UniqueConstraint("region_id", "name_key", name="uq_institutions_region_id_name_key"),)`.

  No `Relationship`, and no separate index on `region_id` (the unique constraint's leading column serves it, research D3). The module docstring links to data-model.md §2 and §5. It states the availability rule ("available for selection only when the institution and its region are both active", for milestone 8), and that milestones 8 and 9 must extend `app.services.institutions.count_institution_uses`.
- [ ] T006 Export `Region` and `Institution` from `app/models/__init__.py`: import them and add them to `__all__` in alphabetical order (depends on T004, T005).
- [ ] T007 Generate the migration with `uv run alembic revision --autogenerate -m "create regions and institutions"`. Then hand-edit the new file in `migrations/versions/` to match `2026_10_02_2a84d288f9e6_create_subjects.py`:
  - `down_revision = "2a84d288f9e6"`;
  - plain SQLAlchemy types (`sa.String(200)`, `sa.String(600)`, `sa.Boolean()`, `sa.DateTime(timezone=True)`), not application types;
  - `upgrade()` creates `regions` (`pk_regions`, `uq_regions_name_key`), then `institutions`. For `institutions`: `pk_institutions`, `sa.ForeignKeyConstraint(["region_id"], ["regions.id"], name=op.f("fk_institutions_region_id_regions"))` with no `ondelete`, and `sa.UniqueConstraint("region_id", "name_key", name=op.f("uq_institutions_region_id_name_key"))`;
  - `downgrade()` drops `institutions`, then `regions`;
  - no data inserted;
  - a module docstring like the subjects one, linking to data-model.md §7 and research D3, D4, D14.

  Run `uv run alembic upgrade head` locally to check it (depends on T006).
- [ ] T008 Update `tests/integration/test_migrations.py`: `APPLICATION_TABLES = {"questions", "boot_counter", "subjects", "regions", "institutions"}`. Run `uv run pytest tests/integration/test_migrations.py`: empty → head, stairway and drift must be green (depends on T007).

### Read-side services

- [ ] T009 [P] Create `app/services/regions.py`, modelled on `app/services/subjects.py`. The module docstring links to contracts/institution-service.md and says the module enforces no authorization. Add `logger = logging.getLogger("uvicorn.error")`, and:
  - `class RegionNotFound(LookupError)` with `.region_id`;
  - `list_regions(session) -> list[Region]`: all regions, sorted in Python by `(name_key, id)` (research D6);
  - `get_region(session, region_id) -> Region`: raises `RegionNotFound`;
  - a private `_find_by_key(session, key) -> Region | None` for later stories.

  (Depends on T006.)
- [ ] T010 Create `app/services/institutions.py` with:
  - `class InstitutionNotFound(LookupError)` with `.region_id` and `.institution_id`;
  - `list_institutions(session, region_id) -> list[Institution]`: only rows where `Institution.region_id == region_id`, sorted in Python by `(name_key, id)`;
  - `get_institution(session, region_id, institution_id) -> Institution`: calls `regions.get_region` first (so `RegionNotFound` comes first), then `session.get(Institution, institution_id)`. Raise `InstitutionNotFound` if it is missing **or** `institution.region_id != region_id` (research D7).

  Import `get_region` and `RegionNotFound` from `app.services.regions`. `regions.py` must not import this module (depends on T009).
- [ ] T011 [P] Create `tests/integration/test_region_service.py`. Add a local helper `add_region(session, name, active=True) -> Region` that inserts a `Region` directly, with `name_key=name_key(name)`. Test:
  - `list_regions` is empty at first;
  - `list_regions` sorts "Odesa", "kyiv", "Lviv" as kyiv, Lviv, Odesa, and includes deactivated rows;
  - `get_region` returns the row;
  - `get_region(session, 999)` raises `RegionNotFound`;
  - a direct duplicate `Region` insert with an equal `name_key` raises `IntegrityError` (the concurrency guarantee, FR-020).

  (Depends on T009.)
- [ ] T012 [P] Create `tests/integration/test_institution_service.py`. Add the local helpers `add_region(...)` and `add_institution(session, region, name, active=True)`, which insert rows directly. Test:
  - `list_institutions` returns only the given region's rows, sorted: "Zaporizhzhia College", "art school", "Academy" → Academy, art school, Zaporizhzhia College (US2-7);
  - `get_institution` with the right region returns the row;
  - with another existing region it raises `InstitutionNotFound`;
  - with a missing region it raises `RegionNotFound`;
  - with a missing institution it raises `InstitutionNotFound`;
  - a direct duplicate `(region_id, name_key)` insert raises `IntegrityError`, but the same `name_key` in another region is accepted (FR-019, FR-020).

  (Depends on T010.)

### Tab shell

- [ ] T013 Remove the `admin_institutions` placeholder handler (`GET /admin/institutions`) from `app/routers/admin.py`. Update its module docstring: the Teachers tab is a placeholder until milestone 8, and the Educational institutions tab lives in `app.routers.admin_institutions`. Keep `ADMIN_TABS`, `render_admin`, `_placeholder` and `admin_teachers` unchanged.
- [ ] T014 Create `app/routers/admin_institutions.py`: `router = APIRouter(prefix="/admin/institutions")`, `TAB = "institutions"`, `TAB_PATH = "/admin/institutions"`, and a helper `region_path(region_id) -> str` returning `f"/admin/institutions/regions/{region_id}"`. The module docstring follows `admin_subjects.py`: thin handlers, Post/Redirect/Get, `{region_id:int}` / `{institution_id:int}` converters, every route `@allow_roles(Role.ADMIN)`, and a link to contracts/http-routes.md. Add:
  - `_region_not_found(request)`: renders `pages/admin/institutions_not_found.html` with `{"heading": "Region not found", "message": "This region does not exist. It may have been deleted."}`, status 404;
  - `_institution_not_found(request)`: heading "Educational institution not found", message "This educational institution does not exist in this region. It may have been deleted.", status 404;
  - `_tab(request, session, region: Region | None, status_code=200)`: renders `pages/admin/institutions.html` with `regions=list_regions(session)`, `selected=region`, and `institutions=list_institutions(session, region.id) if region else []`;
  - `GET ""` (the tab, no region selected): `@allow_roles(Role.ADMIN)`, returns `_tab(request, session, None)`;
  - `GET "/regions/{region_id:int}"`: `get_region`, and `RegionNotFound` → `_region_not_found`. Otherwise `_tab(request, session, region)`.

  Register it in `app/main.py`: import `admin_institutions` from `app.routers`, and `app.include_router(admin_institutions.router)` after `admin.router` (depends on T010, T013).
- [ ] T015 [P] Create `app/templates/pages/admin/institutions.html`. It extends `layouts/admin.html`, with title "Educational institutions — {{ app_name }}". Inside `{% block admin_content %}`, a `<div class="institutions-layout">` with two sections:
  - **Left**, `<section aria-labelledby="regions-heading">`: `<h2 id="regions-heading">Regions</h2>`. If `regions`, a `<ul class="regions-list">`. Each `<li>` holds `<a href="/admin/institutions/regions/{{ r.id }}">{{ r.name }}</a>`; add `aria-current="true"` and the `<li>` class `selected` when `selected and r.id == selected.id`. Show `<small class="status-deactivated">Deactivated</small>` when `not r.is_active`. Otherwise, `<p class="list-empty">No regions yet</p>`.
  - **Right**, `<section aria-labelledby="institutions-heading">`:
    - with no `selected`: `<h2 id="institutions-heading">Educational institutions</h2>` and `<p class="list-empty">Select a region</p>`, with no forms or buttons;
    - with `selected`: `<h2 id="institutions-heading">Educational institutions in “{{ selected.name }}”</h2>` (plus the Deactivated mark if the region is deactivated). If `institutions`, a `<div class="overflow-auto"><table class="institutions-table">` with the columns Name, Status ("Active" / "Deactivated") and Actions (left empty for now). Otherwise, `<p class="list-empty">No educational institutions yet</p>`.

  Put a visible `<h1>Educational institutions</h1>` above the layout, as the subjects page has an `<h1>`, and use `<h2>` inside the two sections. Leave clearly marked `{# US1: … #}`-style spots for the Create links and row actions that later stories add.
- [ ] T016 [P] Create `app/templates/pages/admin/institutions_not_found.html`. It extends `layouts/admin.html`, with title "{{ heading }} — {{ app_name }}", then `<h1>{{ heading }}</h1>`, `<p>{{ message }}</p>` and `<p><a href="/admin/institutions">Back to the educational institutions</a></p>`. No internal details (FR-043).
- [ ] T017 [P] Append to `app/static/css/app.css` a commented block for the institutions tab (research D12, specs/007 FR-002, FR-006):
  - `.institutions-layout { display: grid; gap: 2rem; grid-template-columns: 1fr; }`;
  - `@media (min-width: 768px) { .institutions-layout { grid-template-columns: minmax(14rem, 1fr) 2fr; } }`;
  - `.regions-list` with no bullets and no padding, items with `overflow-wrap: anywhere`;
  - `.regions-list li.selected` and `.regions-list a[aria-current="true"]` highlighted (bold, `var(--pico-primary)` left border or background `var(--pico-primary-background)` with readable text);
  - `.status-deactivated` muted (`var(--pico-muted-color)`);
  - `.institutions-table td { overflow-wrap: anywhere; }`;
  - `.list-empty` muted;
  - `.row-actions` (inline one-button forms with `display: inline; margin: 0`, small buttons with `width: auto`), mirroring `.subjects-actions`.
- [ ] T018 Update `tests/integration/test_admin_area.py`:
  - remove `/admin/institutions` from `PLACEHOLDERS` (Teachers stays);
  - add `test_the_institutions_tab_is_no_longer_a_placeholder`: `/admin/institutions` returns 200 without "Managing educational institutions will arrive in a later milestone.", and contains "No regions yet" and "Select a region";
  - add `test_every_institutions_page_marks_the_institutions_tab`, modelled on `test_every_subject_page_marks_the_subjects_tab`. Create a region through `Region` rows or the service, and check `/admin/institutions`, `/admin/institutions/regions/{id}` and `/admin/institutions/regions/999`: each has `NAV_OPEN`, `current_tabs(body) == ["/admin/institutions"]` and exactly one `aria-current="page"`. Keep the path list in a module-level `INSTITUTION_PAGES` that later stories extend.

  (Depends on T014–T016.)
- [ ] T019 Create `tests/integration/test_admin_institutions.py`, with a module docstring linking to spec.md and contracts/http-routes.md, and helpers to insert regions and institutions directly through `session` (as in T011/T012). Add the foundational layout tests:
  - empty tab: "No regions yet" and "Select a region" (US1-1, FR-004, FR-009);
  - regions "Odesa", "kyiv", "Lviv" appear in the order kyiv, Lviv, Odesa (US1-3, FR-007);
  - a deactivated region shows "Deactivated" (FR-008);
  - `/admin/institutions/regions/{id}` marks exactly that region's link with `aria-current="true"` and no other (FR-002, research D11);
  - the right side shows only that region's institutions, sorted, with "Active"/"Deactivated" (FR-011, FR-012, US2-7);
  - a region with none shows "No educational institutions yet" (FR-013);
  - `/admin/institutions` (no selection) has no `<form` and no `<button` in the right-hand section (FR-004);
  - getting `/admin/institutions/regions/{id}` twice returns identical bodies (FR-003, SC-004);
  - `/admin/institutions/regions/999` returns 404 with "Region not found" and a link to `/admin/institutions`, and no traceback text;
  - `/admin/institutions/regions/abc` returns the ordinary 404 page (no `admin-tabs`).

  (Depends on T014–T017.)

**Checkpoint**: `uv run pytest` is green. The tab shows the two lists from rows inserted directly.

---

## Phase 3: User Story 1 — An administrator builds the list of regions (Priority: P1) 🎯 MVP

**Goal**: administrators create regions with valid, unique names (ignoring case).

**Independent Test**: open the tab, create "Kyiv", "Lviv" and "Odesa", and see them listed in
order. "kyiv", an empty name, 201 characters and a tab are each refused with the right message,
and the entered value is kept.

### Tests for User Story 1

- [ ] T020 [P] [US1] Add to `tests/integration/test_region_service.py`:
  - `create_region` stores an active region with the trimmed name ("  Kharkiv Region  " → "Kharkiv Region") and `name_key`;
  - "Kyiv" then "  KYIV  " → `DuplicateRegionName` with `.message == "A region named “Kyiv” already exists."`;
  - "Київ" then "КИЇВ" → duplicate;
  - a duplicate of a **deactivated** region → refused;
  - "Kyiv Region" and "Kyiv  Region" are both accepted;
  - empty, "   ", 201 characters and "Ky\tiv" → `InvalidName` with the data-model.md §3 message;
  - exactly 200 characters accepted;
  - nothing is stored after a refusal;
  - a commit that hits the unique constraint (simulate by monkeypatching `_find_by_key` to return `None` once, after inserting the winner) → `DuplicateRegionName` naming the stored winner, with the session still usable.
- [ ] T021 [P] [US1] Add to `tests/integration/test_admin_institutions.py`, US1-1 to US1-6 over HTTP:
  - the tab shows a **Create** link to `/admin/institutions/regions/new`;
  - `GET /admin/institutions/regions/new` → 200, a form posting to `/admin/institutions/regions` with `name="name"` and `maxlength="200"`, and **Cancel** to `/admin/institutions`;
  - `POST /admin/institutions/regions` with "Kyiv" → 303, `Location` `/admin/institutions/regions/{new id}` (FR-022); following it shows "Kyiv" selected and active;
  - "  KYIV  " → 400, the message "A region named “Kyiv” already exists.", and `value="  KYIV  "` kept;
  - empty, 201 characters, and "Ky\tiv" → 400 with the matching message and the value kept, and no row added;
  - "  Kharkiv Region  " is stored as "Kharkiv Region";
  - reloading the redirected page (GET again) creates nothing more (FR-041, SC-008).

### Implementation for User Story 1

- [ ] T022 [US1] In `app/services/regions.py`, add:
  - `class DuplicateRegionName(ValueError)` with `.existing_name` and `.message = f"A region named “{existing_name}” already exists."`;
  - `_duplicate_after_conflict(session, key, fallback)` (rollback, look up the winner);
  - `create_region(session, raw_name) -> Region`: `clean_name` → `name_key` → `_find_by_key` (duplicate → raise) → insert `Region(name, name_key, is_active=True, created_at=now, updated_at=now)` → commit. `IntegrityError` → `raise _duplicate_after_conflict(...) from None`. Then refresh and log `"Region created: id=%d"`.

  Exactly mirror `create_subject` (depends on T009).
- [ ] T023 [US1] Create `app/templates/pages/admin/region_form.html`, modelled on `subject_form.html`. It takes the context `heading`, `action`, `value`, `error` and `cancel`. Title "{{ heading }} — {{ app_name }}", then `<h1>{{ heading }}</h1>`, then a form `method="post" action="{{ action }}"` with a `Name` label, `<input type="text" name="name" id="name" maxlength="200" required value="{{ value }}">` (with `aria-invalid="true" aria-describedby="name-error"` and `<small id="name-error">{{ error }}</small>` when there is an error), a **Save** button, and `<a href="{{ cancel }}">Cancel</a>`.
- [ ] T024 [US1] In `app/routers/admin_institutions.py`, add:
  - `_region_form(request, heading, action, value, cancel, error=None, status_code=200)`;
  - `GET "/regions/new"`: `_region_form(request, "New region", "/admin/institutions/regions", "", TAB_PATH)`;
  - `POST "/regions"` with `name: str = Form("")`: `create_region`. `InvalidName` / `DuplicateRegionName` → `_region_form(..., name, refused.message, 400)`. Success → `RedirectResponse(region_path(region.id), status_code=303)`.

  Both routes are `@allow_roles(Role.ADMIN)`. Declare `GET /regions/new` before `GET /regions/{region_id:int}`. The int converter already prevents a clash, but the order keeps it readable (depends on T022, T023).
- [ ] T025 [US1] In `app/templates/pages/admin/institutions.html`, add `<p><a href="/admin/institutions/regions/new" role="button">Create</a></p>` under the "Regions" heading. It is always shown (FR-010).
- [ ] T026 [US1] In `tests/integration/test_routes.py::test_the_write_routes_are_exact`, add `("POST", "/admin/institutions/regions")`. In `tests/integration/test_admin_area.py`, add `/admin/institutions/regions/new` to `INSTITUTION_PAGES`.

**Checkpoint**: US1 works end to end. `uv run pytest` is green.

---

## Phase 4: User Story 2 — An administrator adds educational institutions to a region (Priority: P1)

**Goal**: institutions are created in the selected, active region, with names unique within that
region.

**Independent Test**: with two regions in place, create institutions in one region. They appear
only there. The same name is accepted in the other region and refused in the same one. **Create**
is not offered with no region selected, and creating in a deactivated region (including by a
direct POST) is refused.

### Tests for User Story 2

- [ ] T027 [P] [US2] Add to `tests/integration/test_institution_service.py`:
  - `create_institution(session, kyiv.id, "  Kyiv Polytechnic Institute  ")` stores an active row with `region_id == kyiv.id` and a trimmed name;
  - the same name in Lviv is accepted;
  - "KYIV POLYTECHNIC INSTITUTE" in Kyiv → `DuplicateInstitutionName` with `.message == "An educational institution named “Kyiv Polytechnic Institute” already exists in this region."`;
  - a duplicate of a deactivated institution in the same region → refused;
  - invalid names → `InvalidName`;
  - a missing region → `RegionNotFound`, which comes before the name check (an invalid name still gives `RegionNotFound`);
  - a deactivated region → `RegionInactive` (with `.region`), which comes before the name check;
  - nothing is stored after any refusal;
  - a commit that hits the composite constraint (monkeypatch the pre-check as in T020) → `DuplicateInstitutionName`.
- [ ] T028 [P] [US2] Add to `tests/integration/test_admin_institutions.py`, US2-1 to US2-8 plus FR-024:
  - with regions but none selected, no link to `/institutions/new` (US2-1);
  - selecting an active region shows **Create** linking to `R/institutions/new` (US2-2);
  - `GET R/institutions/new` → 200, with the heading "New educational institution in “Kyiv”", a form posting to `R/institutions`, and **Cancel** to `R`;
  - the POST "Kyiv Polytechnic Institute" → 303 to `R`, listed as Active (US2-3);
  - the same name in Lviv → 303, and each region lists only its own (US2-4);
  - "  KYIV POLYTECHNIC INSTITUTE  " in Kyiv → 400, the "already exists in this region" message, and the value kept (US2-5);
  - invalid names → 400 with the value kept (US2-6);
  - set Kyiv's `is_active = False` directly in the database:
    - the region page shows no **Create** and shows "This region is deactivated. New educational institutions cannot be added to it.";
    - `GET R/institutions/new` → 409 with that text and no `<form`;
    - a direct `POST R/institutions` → 409, with no row added (FR-024, SC-007);
  - `POST /admin/institutions/regions/999/institutions` → 404 "Region not found", with no row added.

### Implementation for User Story 2

- [ ] T029 [US2] In `app/services/institutions.py`, add:
  - `class DuplicateInstitutionName(ValueError)` (`.existing_name`; `.message = f"An educational institution named “{existing_name}” already exists in this region."`);
  - `class RegionInactive(ValueError)` (`.region`);
  - `_find_in_region(session, region_id, key)`;
  - `create_institution(session, region_id, raw_name) -> Institution`:
    1. `region = session.get(Region, region_id, with_for_update=True)`: `None` → `RegionNotFound`; `not region.is_active` → `RegionInactive(region)` (research D5);
    2. `clean_name` → `name_key` → duplicate pre-check within the region;
    3. insert an active `Institution(region_id=region_id, …)` and commit;
    4. `IntegrityError` → rollback; if `session.get(Region, region_id)` is `None`, raise `RegionNotFound`, else raise `DuplicateInstitutionName` naming the stored winner;
    5. refresh, then log `"Institution created: id=%d region_id=%d"`.

  (Depends on T010.)
- [ ] T030 [US2] Create `app/templates/pages/admin/institution_form.html`. It takes the context `heading`, `action`, `value`, `error`, `cancel`, `region` and `refused` (bool). Title and `<h1>{{ heading }}</h1>`. If `refused`, show `<p>This region is deactivated. New educational institutions cannot be added to it.</p>` and `<p><a href="{{ cancel }}">Back to “{{ region.name }}”</a></p>`, with no form. Otherwise show the same form markup as `region_form.html`. There is **no region field**, ever (FR-030).
- [ ] T031 [US2] In `app/routers/admin_institutions.py`, add:
  - `_institution_form(request, heading, action, value, region, error=None, refused=False, status_code=200)` with `cancel=region_path(region.id)`;
  - `GET "/regions/{region_id:int}/institutions/new"`: `get_region`, with `RegionNotFound` → 404 page. A deactivated region renders the form template with `refused=True`, status 409. Otherwise the empty form, with the heading `f"New educational institution in “{region.name}”"` and the action `f"{region_path(region_id)}/institutions"`;
  - `POST "/regions/{region_id:int}/institutions"` with `name: str = Form("")`: `create_institution`. `RegionNotFound` → 404 page. `RegionInactive` → the refusal at 409, using `refused.region`. `InvalidName` / `DuplicateInstitutionName` → the form at 400 (load the region with `get_region` for the heading). Success → 303 to `region_path(region_id)`.

  Both routes are `@allow_roles(Role.ADMIN)` (depends on T029, T030).
- [ ] T032 [US2] In `app/templates/pages/admin/institutions.html` (right section, with `selected`): if `selected.is_active`, show `<p><a href="/admin/institutions/regions/{{ selected.id }}/institutions/new" role="button">Create</a></p>`. Otherwise show `<p class="list-empty">This region is deactivated. New educational institutions cannot be added to it.</p>` (FR-014).
- [ ] T033 [US2] Add `("POST", "/admin/institutions/regions/{region_id:int}/institutions")` to `tests/integration/test_routes.py::test_the_write_routes_are_exact`. In `tests/integration/test_admin_area.py`, add `R/institutions/new` (for an active region) to `INSTITUTION_PAGES`.

**Checkpoint**: US1 + US2 together give a usable list of regions and institutions (the MVP).

---

## Phase 5: User Story 3 — An administrator renames, deactivates and deletes regions (Priority: P2)

**Goal**: regions can be renamed, deactivated and activated (without touching their
institutions), and deleted only while empty.

**Independent Test**: rename a region, including to a duplicate (refused) and to a change of case
only (accepted). Deactivate and activate a region. Delete an empty region after confirming. A
region holding an active or a deactivated institution cannot be deleted.

### Tests for User Story 3

- [ ] T034 [P] [US3] Add to `tests/integration/test_region_service.py`:
  - **rename**:
    - "Lvov" → "Lviv" works;
    - "Lviv" → "KYIV" when Kyiv exists → `DuplicateRegionName`, and the region is unchanged;
    - "kyiv" → "Kyiv" (case only) works;
    - renaming to the same name changes nothing (`updated_at` unchanged);
    - an invalid name → `InvalidName`;
    - a missing id → `RegionNotFound`, which comes before the name check;
    - a rename keeps `is_active`;
  - **set_region_active**:
    - deactivate, then activate, works;
    - a repeat changes nothing (`updated_at` unchanged);
    - a missing id → `RegionNotFound`;
    - **no cascade**: with one active and one deactivated institution, deactivating then activating the region leaves both `is_active` values exactly as they were (FR-033);
  - **count_region_institutions** counts active and deactivated institutions;
  - **delete_region**:
    - an empty region is removed, and its name can be reused;
    - a region with an active institution → `RegionNotEmpty` (`.institutions == 1`), unchanged;
    - a region with only a deactivated institution → `RegionNotEmpty` (FR-036);
    - a missing id → `RegionNotFound`.
- [ ] T035 [P] [US3] Add to `tests/integration/test_admin_institutions.py`, US3-1 to US3-11:
  - every region row offers **Rename** (`R/rename`), **Delete** (`R/delete`), and a Deactivate or Activate form (FR-010);
  - `GET R/rename` is pre-filled with the name (US3-1);
  - the POST "Lviv" → 303 to `R`, and the list shows "Lviv" (US3-2);
  - a duplicate → 400 with the value kept, unchanged (US3-3);
  - a case-only rename → 303 (US3-4);
  - `POST R/deactivate` → 303 to `R`, showing "Deactivated" and an Activate form (US3-5);
  - the deactivated, selected region still lists its institutions, has no **Create**, and shows the note (US3-6);
  - a direct institution POST is refused (US3-7, already covered by T028; reference it rather than duplicate it);
  - `POST R/activate` → **Create** is back (US3-8);
  - a repeated deactivate → 303, no error;
  - `GET R/delete` names the region, says "Deleting a region cannot be undone.", has a form posting to `R/delete`, and **Cancel** to `R`; nothing is deleted (US3-9);
  - `POST R/delete` on an empty region → 303 to `/admin/institutions`, and the region is gone (US3-10);
  - on a region with an active or a deactivated institution → 409 with "“Kyiv” still holds educational institutions and cannot be deleted. Delete its institutions first.", no Delete button, and the region unchanged (US3-11);
  - rename, deactivate and delete of `/regions/999/…` → 404 "Region not found".

### Implementation for User Story 3

- [ ] T036 [US3] In `app/services/regions.py`, add:
  - `rename_region(session, region_id, raw_name) -> Region`, mirroring `rename_subject` (get → clean → key → duplicate only if `existing.id != region.id` → no-op if unchanged → update `name`, `name_key`, `updated_at` → commit; `IntegrityError` → `DuplicateRegionName`). Log `"Region renamed: id=%d"`;
  - `set_region_active(session, region_id, active) -> Region`, mirroring `set_subject_active`, changing only the region row. Log `"Region activated: id=%d"` / `"Region deactivated: id=%d"`;
  - `count_region_institutions(session, region_id) -> int`: `select(func.count()).select_from(Institution).where(Institution.region_id == region_id)`, importing `Institution` from `app.models`;
  - `class RegionNotEmpty(ValueError)` with `.region` and `.institutions`;
  - `delete_region(session, region_id) -> None`: get → count → `> 0` raises `RegionNotEmpty` → `session.delete` → commit. `IntegrityError` → rollback, then `RegionNotEmpty(get_region(...), count_region_institutions(...) or 1)`. Log `"Region deleted: id=%d"`.

  Docstrings name FR-033 (no cascade) and FR-036 (depends on T022).
- [ ] T037 [US3] Create `app/templates/pages/admin/region_delete.html`, modelled on `subject_delete.html`. Title and `<h1>Delete region “{{ region.name }}”?</h1>`.
  - If `not_empty`: `<p>“{{ region.name }}” still holds educational institutions and cannot be deleted. Delete its institutions first.</p>` and `<p><a href="/admin/institutions/regions/{{ region.id }}">Back to “{{ region.name }}”</a></p>`.
  - Otherwise: `<p>Deleting a region cannot be undone.</p>` and a form posting to `/admin/institutions/regions/{{ region.id }}/delete`, with a **Delete** button and `<a href="/admin/institutions/regions/{{ region.id }}">Cancel</a>`.
- [ ] T038 [US3] In `app/routers/admin_institutions.py`, add (all `@allow_roles(Role.ADMIN)`, with `RegionNotFound` → `_region_not_found`):
  - `GET "/regions/{region_id:int}/rename"`: the form with the heading "Rename region", the action `f"{region_path(id)}/rename"`, the current name, and cancel `region_path(id)`;
  - `POST` the same path with `name: str = Form("")`: `rename_region`; a refusal → the form at 400 with the submitted value; success → 303 to `region_path(id)`;
  - `POST "/regions/{region_id:int}/deactivate"` and `/activate`: through one `_set_region_active` helper → 303 to `region_path(id)`;
  - `GET "/regions/{region_id:int}/delete"`: the confirmation (`not_empty=False`), status 200;
  - `POST` the same path: `delete_region`; `RegionNotEmpty` → the confirmation with `not_empty=True`, status 409; success → 303 to `TAB_PATH`.

  (Depends on T036, T037.)
- [ ] T039 [US3] In `app/templates/pages/admin/institutions.html`, add a `<div class="row-actions">` to each region `<li>`. It holds `<a href="/admin/institutions/regions/{{ r.id }}/rename">Rename</a>`; a one-button form posting to `…/deactivate` (when `r.is_active`, label "Deactivate") or `…/activate` (label "Activate"), with `class="secondary outline"`; and `<a href="/admin/institutions/regions/{{ r.id }}/delete">Delete</a>`.
- [ ] T040 [US3] Add the four region `POST` routes (`/rename`, `/deactivate`, `/activate`, `/delete` under `/admin/institutions/regions/{region_id:int}`) to `tests/integration/test_routes.py::test_the_write_routes_are_exact`. Add `R/rename` and `R/delete` to `INSTITUTION_PAGES` in `tests/integration/test_admin_area.py`, and also the 409 refusal pages (region delete refused, institution create in a deactivated region).

**Checkpoint**: US1–US3 work. Regions are fully manageable.

---

## Phase 6: User Story 4 — An administrator renames, deactivates and deletes institutions (Priority: P2)

**Goal**: institutions can be renamed (never moved), deactivated, activated and deleted (unless in
use), whatever their region's status.

**Independent Test**: in a region with several institutions:

- rename one to a name used in the same region (refused) and to a name used in another region
  (accepted);
- deactivate and activate one;
- delete one after confirming.

An institution named together with the wrong region is "not found".

### Tests for User Story 4

- [ ] T041 [P] [US4] Add to `tests/integration/test_institution_service.py`:
  - **rename_institution**:
    - works;
    - a duplicate in the same region (ignoring case) → `DuplicateInstitutionName`, unchanged;
    - the name of an institution in another region → accepted;
    - a case-only rename → accepted;
    - an unchanged name → no write (`updated_at` unchanged);
    - `region_id` never changes;
  - **set_institution_active**: works, and a repeat is a no-op;
  - **in a deactivated region**: rename, deactivate, activate and delete all succeed (US4-9);
  - **wrong region**: every function taking `(region_id, institution_id)` raises `InstitutionNotFound` when given another existing region, and nothing changes;
  - **count_institution_uses** returns `0`;
  - **delete_institution**:
    - removes the row, and its name can be reused in that region;
    - with `count_institution_uses` monkeypatched (`monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda session, institution_id: 1)`) → `InstitutionInUse` (`.uses == 1`), and the row is unchanged (FR-037).
- [ ] T042 [P] [US4] Add to `tests/integration/test_admin_institutions.py`, US4-1 to US4-9:
  - each institution row offers Rename (`I/rename`), Delete (`I/delete`), and a Deactivate or Activate form, also when the region is deactivated (FR-015);
  - `GET I/rename` is pre-filled, has no `<select` and no field other than `name`, and names the region (US4-1);
  - a valid rename → 303 to `R` (US4-2);
  - a same-region duplicate → 400 with the value kept (US4-3);
  - another region's name → 303 (US4-4);
  - deactivate → "Deactivated" with Activate; activate → "Active" (US4-5);
  - `GET I/delete` names the institution, shows "Region: Kyiv" and "Deleting an educational institution cannot be undone.", and **Cancel** goes to `R` (US4-6);
  - confirming → 303 to `R`, and the row is gone. Deleting the last one → "No educational institutions yet", with the region still selected (US4-7);
  - with `count_institution_uses` monkeypatched to 1 → 409 with "“…” is in use and cannot be deleted. You can deactivate it instead." and a Deactivate form to `I/deactivate` (US4-8);
  - rename, deactivate and delete work while the region is deactivated (US4-9);
  - **wrong region**: GET and POST on `/admin/institutions/regions/{lviv}/institutions/{kyiv_institution}/rename` (and `/deactivate`, `/delete`) → 404 "Educational institution not found", and nothing changes;
  - posting `region_id=<other>` along with `name` to `I/rename` leaves `region_id` unchanged (FR-030);
  - a missing institution → 404, and a missing region → 404 "Region not found".

### Implementation for User Story 4

- [ ] T043 [US4] In `app/services/institutions.py`, add:
  - `rename_institution(session, region_id, institution_id, raw_name) -> Institution`: `get_institution` → clean → key → duplicate = `_find_in_region` result with a different id → no-op if unchanged → update `name`, `name_key`, `updated_at` (never `region_id`) → commit; `IntegrityError` → `DuplicateInstitutionName`. Log `"Institution renamed: id=%d region_id=%d"`;
  - `set_institution_active(session, region_id, institution_id, active)`: no-op if unchanged. Log `"Institution activated|deactivated: id=%d region_id=%d"`;
  - `count_institution_uses(session, institution_id) -> int`: returns `0`, with a docstring saying milestone 8 (teacher links) and milestone 9 (students) must add their counts here, and not rely on a foreign key alone because SQLite does not enforce foreign keys in this application (research D9, FR-038);
  - `class InstitutionInUse(ValueError)` with `.institution` and `.uses`;
  - `delete_institution(session, region_id, institution_id)`: get → count → `> 0` raises → delete → commit; `IntegrityError` → rollback, then `InstitutionInUse(get_institution(...), 1)`. Log `"Institution deleted: id=%d region_id=%d"`.

  Call `count_institution_uses` through the module namespace, so that monkeypatching works (as `delete_subject` does) (depends on T029).
- [ ] T044 [US4] Create `app/templates/pages/admin/institution_delete.html`. Title and `<h1>Delete educational institution “{{ institution.name }}”?</h1>`, then `<p>Region: {{ region.name }}</p>`.
  - If `in_use`: `<p>“{{ institution.name }}” is in use and cannot be deleted. You can deactivate it instead.</p>`. If `institution.is_active`, add a Deactivate form posting to `…/institutions/{{ institution.id }}/deactivate`. Then a "Back to “{{ region.name }}”" link to `R`.
  - Otherwise: `<p>Deleting an educational institution cannot be undone.</p>`, a form posting to `…/delete` with a **Delete** button, and **Cancel** to `R`.
- [ ] T045 [US4] In `app/routers/admin_institutions.py`, add (all `@allow_roles(Role.ADMIN)`; `RegionNotFound` → `_region_not_found`, `InstitutionNotFound` → `_institution_not_found`):
  - `GET` and `POST "/regions/{region_id:int}/institutions/{institution_id:int}/rename"`: the heading "Rename educational institution", the form also showing `Region: {region.name}` (pass `region` to `institution_form.html`, and render that line when not refused). The POST reads only `name: str = Form("")`. Success → 303 to `region_path(region_id)`. A refusal → 400 with the submitted value;
  - `POST …/deactivate` and `…/activate` through one helper → 303 to `region_path(region_id)`;
  - `GET …/delete` → the confirmation, 200;
  - `POST …/delete` → `InstitutionInUse` gives the confirmation with `in_use=True` at 409; success → 303 to `region_path(region_id)`.

  (Depends on T043, T044.)
- [ ] T046 [US4] In `app/templates/pages/admin/institutions.html`, fill the institution Actions cell with `<td class="row-actions">`. It holds a Rename link to `…/institutions/{{ i.id }}/rename`; a Deactivate or Activate one-button form (`class="secondary outline"`); and a Delete link to `…/institutions/{{ i.id }}/delete`. These are offered whatever `selected.is_active` is (FR-015).
- [ ] T047 [US4] Add the four institution `POST` routes (`/rename`, `/deactivate`, `/activate`, `/delete` under `/admin/institutions/regions/{region_id:int}/institutions/{institution_id:int}`) to `tests/integration/test_routes.py::test_the_write_routes_are_exact`. That makes 10 new write routes in total. Add `I/rename`, `I/delete` and the "Educational institution not found" page to `INSTITUTION_PAGES` in `tests/integration/test_admin_area.py`.

**Checkpoint**: US1–US4 work. Every page and action of the tab exists.

---

## Phase 7: User Story 5 — Only administrators manage regions and institutions (Priority: P3)

**Goal**: prove that every new page and action follows milestone 5's access rules.

**Independent Test**: for each role and for an anonymous visitor, request every new page and send
every new form. Only an administrator using the administrator role succeeds, and no region or
institution changes after a refused request.

### Tests for User Story 5

- [ ] T048 [P] [US5] In `tests/integration/test_access_control.py`, add a "Milestone 7" section modelled on the milestone 6 one:
  - fixtures `region_id` and `institution_id` (an active region "Kyiv" with an institution, created through the services);
  - `INSTITUTION_PAGES` templates: `/admin/institutions`, `/admin/institutions/regions/new`, `R`, `R/rename`, `R/delete`, `R/institutions/new`, `I/rename`, `I/delete`;
  - `INSTITUTION_ACTIONS`: `POST /admin/institutions/regions` `{"name": "Hacked"}`, `R/rename` `{"name": "Hacked"}`, `R/deactivate`, `R/activate`, `R/delete`, `R/institutions` `{"name": "Hacked"}`, `I/rename` `{"name": "Hacked"}`, `I/deactivate`, `I/activate`, `I/delete`;
  - `institution_rows(session)`, which snapshots `(id, name, name_key, is_active, updated_at)` for regions and `(id, region_id, name, name_key, is_active, updated_at)` for institutions, after `session.expire_all()`.

  Tests:
  - teacher and student get 403 with "Your current role, {label}, cannot open this page." on every page (US5-1, FR-045);
  - teacher and student get 403 on every action, and the rows are unchanged (US5-2);
  - `client_as(ADMIN_STUDENT_EMAIL, STUDENT)` gets 403 on `/admin/institutions`, then 200 after `POST /role` `{"role": "admin"}` (US5-3, FR-044). The test cast in `tests/conftest.py` has no administrator + teacher person. `ADMIN_STUDENT_EMAIL` exercises the same rule (the current role counts, not every role held), and milestone 6 used it the same way. Do not change the cast;
  - an anonymous visitor gets 303 to `/login?next=<quoted path>` on every page, and the actions go to `/login` with nothing changed;
  - the full sign-in round trip with `sign_in(client, outbox, next_path=f"/admin/institutions/regions/{region_id}")` (imported from `tests.integration.test_login_flow`, as the file already does) lands on that same address with the region selected (`aria-current="true"` on its link) (US5-4, FR-046).
- [ ] T049 [P] [US5] In `tests/integration/test_cross_site.py`, add `test_a_cross_site_region_or_institution_change_is_refused`, parametrised over `CROSS_SITE_HEADERS`. As an administrator, `POST /admin/institutions/regions` `{"name": "Evil"}` and `POST I/delete` each answer 403 with `REFUSED`, no region is added, and the institution still exists (FR-042).
- [ ] T050 [US5] Run `uv run pytest tests/integration/test_routes.py`. The sweeps must cover the new routes with no further change: every new route declares `Role.ADMIN`; anonymous requests redirect; the declared-page sweep gets ≠ 403 for an administrator (404 for `regions/1`) and 403 for the others (FR-047, SC-003). If a route is missing from the exact write list, fix it there, not in the sweep.

**Checkpoint**: all five stories are complete and verified.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Update `README.md`:
  - in "Roles and access", rewrite the administrator-area paragraph. **Educational institutions** now manages regions and the institutions of each region: names unique ignoring case (institutions within their region); a deactivated region accepts no new institutions; a region holding institutions or an institution in use cannot be deleted. **Teachers** is still a placeholder;
  - in "Repository layout", add `app/routers/admin_institutions.py`, `app/services/regions.py`, `app/services/institutions.py`, `app/schemas/names.py`, `app/models/region.py`, `app/models/institution.py` and the new templates, and update the `admin.py` line (only Teachers is a placeholder now).
- [ ] T052 [P] Check FR-049 with `git diff main --stat -- app/routers/admin_subjects.py app/services/subjects.py app/models/subject.py app/templates/pages/admin/subject* app/templates/pages/admin/subjects.html app/routers/areas.py tests/unit/test_subject_schemas.py tests/integration/test_admin_subjects.py tests/integration/test_subject_service.py`. The result must be empty. Then check that `app/schemas/subject.py` only aliases.
- [ ] T053 Run `uv run ruff check .` and `uv run ruff format --check .`, and fix any findings (line length, import order).
- [ ] T054 Run the full suite, `uv run pytest`, on SQLite, and with `TEST_POSTGRES_URL` set if a local PostgreSQL is available. Everything must pass (SC-009).
- [ ] T055 Do the manual walk-through in [quickstart.md](./quickstart.md) §2 (Regions, Institutions, Changing regions, Changing institutions, Access), including phone width: the two lists stack, regions first (FR-006).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: depends on Setup. It blocks every story.
- **US1 (Phase 3)** and **US2 (Phase 4)**: both depend only on Foundational. US2's tests insert
  regions directly, so US2 does not need US1. They both edit `admin_institutions.py`,
  `institutions.html` and `test_routes.py`, so run them one after the other, US1 first.
- **US3 (Phase 5)**: depends on Foundational. It extends `regions.py` after T022 (same file),
  so it runs after US1.
- **US4 (Phase 6)**: depends on Foundational. It extends `institutions.py` after T029 (same
  file), so it runs after US2.
- **US5 (Phase 7)**: depends on US1–US4, because it covers every route.
- **Polish (Phase 8)**: after all stories.

### Story completion order

```text
Setup → Foundational → US1 → US2 → US3 → US4 → US5 → Polish
                         (MVP = US1 + US2)
```

### Within each story

Write the tests first (marked [P]) and see them fail. Then work in order: service → template →
routes → list-page additions → route-list and tab-marking updates.

### Parallel Opportunities

- Phase 1: T003 runs after T001 and T002 (it checks both).
- Phase 2:
  - T004 ∥ T005;
  - T009 ∥ T013 ∥ T015 ∥ T016 ∥ T017 (different files);
  - T011 ∥ T012 once their services exist.
- Each story: its two test tasks ([P]) are in different files and can be written in parallel.
  Its service task and its new template can also be written in parallel.
- US3's service work (`regions.py`) and US4's (`institutions.py`) touch different files. With two
  developers, they can run in parallel once US1 and US2 are done, provided the shared edits to
  `admin_institutions.py`, `institutions.html` and `test_routes.py` are merged carefully.
- Phase 7: T048 ∥ T049.
- Phase 8: T051 ∥ T052.

---

## Parallel Example: User Story 1

```text
# Tests first, together:
T020 [US1] region service create tests in tests/integration/test_region_service.py
T021 [US1] region create HTTP tests in tests/integration/test_admin_institutions.py

# Then, together:
T022 [US1] create_region in app/services/regions.py
T023 [US1] app/templates/pages/admin/region_form.html

# Then in sequence:
T024 → T025 → T026
```

## Parallel Example: User Story 4

```text
T041 [US4] institution service tests   ∥   T042 [US4] institution HTTP tests
T043 [US4] institutions.py service     ∥   T044 [US4] institution_delete.html
T045 → T046 → T047
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1, then Phase 2. The tab shows the lists, with data inserted directly.
2. US1: administrators can build the region list. Stop and validate with quickstart "Regions".
3. US2: administrators can add institutions to regions. Stop and validate with quickstart
   "Institutions". This is the smallest result milestone 8 can use.

### Incremental Delivery

4. US3: manage regions (rename, status, guarded delete).
5. US4: manage institutions (rename, status, in-use guarded delete, wrong-region 404).
6. US5: the access matrix and the cross-site checks. The protections already work through
   `@allow_roles` and `resolve_access`; this phase proves it.
7. Polish: README, ruff, full suite, manual walk-through. Then open the PR to `main`.

Keep the suite green at every checkpoint. `test_routes.py::test_the_write_routes_are_exact` fails
the moment a `POST` route is added without being listed, so update it in the same story.

---

## Notes

- [P] = a different file and no dependency on an unfinished task.
- Never add a route to `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES`.
- Never use `ORDER BY` on names, `lower()` in SQL, or engine-specific SQL (research D2, D6).
- Never cascade a region's status to its institutions, and never write `Institution.region_id`
  after the insert.
- Log ids only, never names.
- Commit after each task or logical group.
