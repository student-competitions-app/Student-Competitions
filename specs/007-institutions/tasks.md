---

description: "Task list for milestone 7: administrator area — Educational institutions"
---

# Tasks: Administrator Area — Educational Institutions (Milestone 7)

**Input**: Design documents from `/specs/007-institutions/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/institution-service.md](./contracts/institution-service.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III requires test-backed delivery and role-access tests
for every protected route. Database tests run on SQLite and, when `TEST_POSTGRES_URL` is set, on
PostgreSQL, through the existing `database_url` fixture. Signed-in clients come from the
`client_as` / `admin_client` fixtures in `tests/conftest.py`.

**Reference implementation**: the Subjects tab from milestone 6 is the template for almost every
file below. Before writing an institution file, open its subject counterpart and copy its
structure, docstring style and error handling:

| Institution file (new) | Subject counterpart (copy from) |
|---|---|
| `app/models/institution.py` | `app/models/subject.py` |
| `app/services/institutions.py` | `app/services/subjects.py` |
| `app/routers/admin_institutions.py` | `app/routers/admin_subjects.py` |
| `app/templates/pages/admin/institutions.html` | `app/templates/pages/admin/subjects.html` |
| `app/templates/pages/admin/institution_form.html` | `app/templates/pages/admin/subject_form.html` |
| `app/templates/pages/admin/institution_delete.html` | `app/templates/pages/admin/subject_delete.html` |
| `app/templates/pages/admin/institution_not_found.html` | `app/templates/pages/admin/subject_not_found.html` |
| `migrations/versions/…_create_institutions.py` | `migrations/versions/2026_10_02_2a84d288f9e6_create_subjects.py` |
| `tests/integration/test_institution_service.py` | `tests/integration/test_subject_service.py` |
| `tests/integration/test_admin_institutions.py` | `tests/integration/test_admin_subjects.py` |

Texts differ: use exactly the texts in research.md D8 and contracts/http-routes.md. Tests assert
them verbatim.

**Organization**: tasks are grouped by user story. The shared name rules, the table and the
service are Foundational: every story needs them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to the repository root (single FastAPI application, see plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the starting point. The milestone adds no dependency and no new top-level
directory (plan, Technical Context).

- [ ] T001 On branch `007-institutions`, run `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` and confirm all are green before any change; record any pre-existing failure instead of fixing it here (no file changes)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared name rules, the `institutions` table and the institution service. US1–US3
all build on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### 2a. Shared name rules (research D1; contracts/institution-service.md)

- [ ] T002 Create `app/schemas/names.py` by **moving** the body of `app/schemas/subject.py` into it, renamed: `NAME_MAX_LENGTH = 200`, `NAME_KEY_MAX_LENGTH = 600`, `class NameRuleError(ValueError)` (with `message: str`), `clean_name(raw: str) -> str`, `name_key(name: str) -> str`, and the private `_CONTROL_CATEGORIES` / `_is_control`. Behaviour and messages stay byte-for-byte identical: "The name cannot contain tabs, line breaks or other control characters.", "Enter a name.", "The name can be at most {NAME_MAX_LENGTH} characters.". Rewrite the module docstring to say these rules are shared by subjects and institutions (specs/006-admin-area/research.md D1–D2, specs/007-institutions/research.md D1)
- [ ] T003 Replace the body of `app/schemas/subject.py` with aliases of `app.schemas.names`: `SUBJECT_NAME_MAX_LENGTH = NAME_MAX_LENGTH`, `SUBJECT_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH`, `SubjectNameError = NameRuleError`, `clean_subject_name = clean_name`, `subject_name_key = name_key`, with a short module docstring pointing to `app.schemas.names`. Do not change any importer. Run `uv run pytest tests/unit/test_subject_schemas.py tests/integration/test_subject_service.py tests/integration/test_admin_subjects.py` and confirm they pass unchanged
- [ ] T004 [P] Create `app/schemas/institution.py` with aliases of `app.schemas.names`: `INSTITUTION_NAME_MAX_LENGTH = NAME_MAX_LENGTH`, `INSTITUTION_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH`, `InstitutionNameError = NameRuleError`, `clean_institution_name = clean_name`, `institution_name_key = name_key`; module docstring as in T003, naming institutions
- [ ] T005 [P] Create `tests/unit/test_name_rules.py`: assert `app.schemas.subject` and `app.schemas.institution` expose the very same objects as `app.schemas.names` (`is` comparisons for the error class and both functions, `==` for both limits, which are 200 and 600), so the two lists cannot drift; plus one smoke check that `clean_institution_name("  Lviv Polytechnic  ") == "Lviv Polytechnic"` and `institution_name_key("Київський університет") == institution_name_key("КИЇВСЬКИЙ УНІВЕРСИТЕТ")`

### 2b. Institution table (data-model §1, §3)

- [ ] T006 Create `app/models/institution.py`, copying `app/models/subject.py`: `class Institution(SQLModel, table=True)`, `__tablename__ = "institutions"`; `id: int | None` primary key ("The identity other records refer to; never changes"); `name` `Column(String(INSTITUTION_NAME_MAX_LENGTH), nullable=False)` ("As entered after trimming. Shown everywhere."); `name_key` `Column(String(INSTITUTION_NAME_KEY_MAX_LENGTH), nullable=False, unique=True)` so the naming convention yields `uq_institutions_name_key` ("Never shown"); `is_active: bool` not null, default `True` ("`False` once deactivated: kept, but not offered for new teacher or student links"); `created_at` and `updated_at` with `default_factory=utc_now, sa_type=UTCDateTime, nullable=False`. Import the limits from `app.schemas.institution`. Module docstring: only administrators change institutions; other records refer to an institution by `id` only, so a rename never breaks a link (FR-018); milestones 8 (teacher links) and 9 (student details) must extend `app.services.institutions.count_institution_uses`
- [ ] T007 Export `Institution` from `app/models/__init__.py` (import and `__all__`, alphabetical), so `SQLModel.metadata` and the drift test see it
- [ ] T008 Create the Alembic revision `migrations/versions/2026_10_06_<rev>_create_institutions.py` with `uv run alembic revision -m "create institutions"` (hand-written, not autogenerate), `down_revision = "2a84d288f9e6"`. Upgrade: `op.create_table("institutions", sa.Column("id", sa.Integer(), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("name_key", sa.String(600), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name=op.f("pk_institutions")), sa.UniqueConstraint("name_key", name=op.f("uq_institutions_name_key")))`. Downgrade: `op.drop_table("institutions")`. No data inserted (the list starts empty). Use only `sqlalchemy as sa` and `alembic.op`; module docstring as in the subjects revision, naming specs/007-institutions/data-model.md
- [ ] T009 In `tests/integration/test_migrations.py` change `APPLICATION_TABLES` to `{"questions", "boot_counter", "subjects", "institutions"}`; run `uv run pytest tests/integration/test_migrations.py` and confirm empty → head, stairway, single head and the drift test pass

### 2c. Institution service (contracts/institution-service.md; research D4, D5)

- [ ] T010 Create `app/services/institutions.py`, copying `app/services/subjects.py` function for function: exceptions `InstitutionNotFound(LookupError)` (`institution_id`), `DuplicateInstitutionName(ValueError)` (`existing_name`, `message` = "An educational institution named “{existing_name}” already exists." using the **stored** name), `InstitutionInUse(ValueError)` (`institution`, `uses`); functions taking `session: Session` first: `list_institutions` (all rows, `sorted(key=lambda i: (i.name_key, i.id))` in Python, no `ORDER BY`), `get_institution`, `create_institution` (clean with `clean_institution_name` → pre-check same key → insert `is_active=True` → commit; `IntegrityError` → rollback → re-query by key → `DuplicateInstitutionName`), `rename_institution` (load first so `InstitutionNotFound` wins, then clean; duplicate = **other** institution with same key; no write when `name` and `name_key` are unchanged; else set both plus `updated_at = utc_now()`, keeping `id` and `is_active`; `IntegrityError` → rollback → `DuplicateInstitutionName`), `set_institution_active(session, institution_id, active)` (no write if already that status, else set + `updated_at`), `count_institution_uses(session, institution_id) -> int` returning `0` with a docstring naming milestone 8 (teacher links) and milestone 9 (student details) as the places to add counts and warning that SQLite foreign keys are off in this application, `delete_institution` (load; `count_institution_uses(...) > 0` → `InstitutionInUse`; delete + commit; `IntegrityError` → rollback → `InstitutionInUse`). Call `count_institution_uses` and the private `_find_by_key` through the module globals so tests can monkeypatch them. Each successful write logs one `INFO` line on `logging.getLogger("uvicorn.error")` with id only: `Institution created: id=%d`, `Institution renamed: id=%d`, `Institution deactivated: id=%d`, `Institution activated: id=%d`, `Institution deleted: id=%d` (no-ops log nothing). Module docstring: no authorization here; callers must be `@allow_roles(Role.ADMIN)`; no "active only" query until milestone 8 (research D6)
- [ ] T011 Create `tests/integration/test_institution_service.py`, copying the cases of `tests/integration/test_subject_service.py` (uses the `session` fixture, so it runs on both engines): create stores trimmed name, `name_key`, `is_active=True`; create duplicate in other case, in Cyrillic case ("Київський університет" / "КИЇВСЬКИЙ УНІВЕРСИТЕТ") and of an inactive institution → `DuplicateInstitutionName` with the stored name in `message`; invalid names → `InstitutionNameError`; an institution named "Physics" can be created while a subject "Physics" exists (create the subject with `app.services.subjects.create_subject`); list order for "Lviv Polytechnic", "alpha College", "Kyiv Polytechnic Institute" is alpha College, Kyiv Polytechnic Institute, Lviv Polytechnic; rename to other case succeeds; rename keeps `id` and `is_active`, including for an inactive institution (SC-007, FR-017); rename to own unchanged name leaves `updated_at` unchanged; rename onto another institution's name → `DuplicateInstitutionName` and the row is unchanged; rename/set_active/delete/get of a missing id → `InstitutionNotFound` (rename of a missing id with an invalid name still raises `InstitutionNotFound`); `set_institution_active` no-op leaves `updated_at` unchanged; a direct `session.add(Institution(... same name_key ...))` + commit raises `IntegrityError`; `create_institution` turns an `IntegrityError` into `DuplicateInstitutionName` (monkeypatch `_find_by_key` as the subject test does); `count_institution_uses` returns `0`; `delete_institution` removes the row and frees the name; with `monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda *_: 1)` delete raises `InstitutionInUse` and the row remains (SC-004); log lines contain the id and no name

**Checkpoint**: `uv run pytest` is green; the institution service works on both engines; no page
changed yet.

---

## Phase 3: User Story 1 - An administrator builds the list of educational institutions (Priority: P1) 🎯 MVP

**Goal**: `/admin/institutions` lists institutions and lets an administrator create them, with
invalid and duplicate names refused.

**Independent Test**: as an administrator, open `/admin/institutions`, see "No educational
institutions yet", create institutions, see them sorted; submit invalid and duplicate names and
see each refused with the right message and the entered value kept.

### Tests for User Story 1

> Write these first and confirm they fail before the implementation.

- [ ] T012 [P] [US1] Create `tests/integration/test_admin_institutions.py` (module docstring naming spec 007 user stories 1 and 2 and contracts/http-routes.md; helpers `stored(session)`, `create(client, name)` and `current_tabs(body)` as in `test_admin_subjects.py`; constants `DUPLICATE = "An educational institution named “{}” already exists."`, `CONTROL`, `EMPTY`, `TOO_LONG` with the shared messages) with US1 cases: empty list shows "No educational institutions yet" and a **Create** link to `/admin/institutions/new` (US1-1); `GET /admin/institutions/new` shows heading "New educational institution", one `name` input with `maxlength="200"` and `required`, **Save**, and **Cancel** to `/admin/institutions`; `POST /admin/institutions` with "Kyiv Polytechnic Institute" → `303` to `/admin/institutions`, then listed as "Active" (US1-2); order "alpha College", "Kyiv Polytechnic Institute", "Lviv Polytechnic" (US1-3); "  LVIV POLYTECHNIC  " → `400`, the form with `DUPLICATE.format("Lviv Polytechnic")` and the entered value, nothing added (US1-4); "", "   ", 201 characters, "Kyiv\tInstitute", "Kyiv\nInstitute" → `400` with the right message and the value kept (HTML-escaped), nothing added (US1-5); "  Odesa College  " stored and shown as "Odesa College" (US1-6); "Київський університет" then "КИЇВСЬКИЙ УНІВЕРСИТЕТ" → second refused; a missing `name` field is treated as empty; the list page and the new form mark only the `/admin/institutions` tab current; reloading the list after a create does not add a second row

### Implementation for User Story 1

- [ ] T013 [P] [US1] Create `app/templates/pages/admin/institutions.html`, copying `subjects.html`: title "Educational institutions — {{ app_name }}", `<h1>Educational institutions</h1>`, `<p><a href="/admin/institutions/new" role="button">Create</a></p>`; with rows, a table `class="institutions-table"` (Name, Status, Actions) where each row shows the name, "Active"/"Inactive", and in `class="institutions-actions"`: a **Rename** link to `/admin/institutions/{{ i.id }}/rename`, a one-button POST form to `/deactivate` (when active) or `/activate` (when inactive) with `class="secondary outline"`, and a **Delete** link to `/admin/institutions/{{ i.id }}/delete`; without rows, `<p class="institutions-empty">No educational institutions yet</p>`. (The rename/activate/deactivate/delete targets are served in US2.)
- [ ] T014 [P] [US1] Create `app/templates/pages/admin/institution_form.html`, copying `subject_form.html`: `{{ heading }}`, a form `method="post" action="{{ action }}"` with label "Name", `<input type="text" name="name" id="name" maxlength="200" required value="{{ value }}">` plus `aria-invalid`/`aria-describedby="name-error"` and `<small id="name-error">{{ error }}</small>` when there is an error, a **Save** button and a **Cancel** link to `/admin/institutions`
- [ ] T015 [P] [US1] In `app/static/css/app.css`, extend each subject list rule to also match the institution classes (research D9): `.subjects-table td, .institutions-table td`, `.subjects-actions, .institutions-actions`, `.subjects-actions form, .institutions-actions form`, `.subjects-actions button, .institutions-actions button`, `.subjects-empty, .institutions-empty`; update the comment above them to say "The subject and institution lists"
- [ ] T016 [US1] Create `app/routers/admin_institutions.py`, copying `admin_subjects.py`: module docstring (spec 007, contracts/http-routes.md); `router = APIRouter(prefix="/admin/institutions")`, `TAB = "institutions"`, `LIST_PATH = "/admin/institutions"`; helpers `_to_list()` (303), `_form(...)` rendering `pages/admin/institution_form.html` through `render_admin`; handlers, each `@allow_roles(Role.ADMIN)`: `GET ""` → `institutions.html` with `institutions=list_institutions(session)`; `GET "/new"` → form with heading "New educational institution" and action `LIST_PATH`; `POST ""` with `name: str = Form("")` → `create_institution`, on `InstitutionNameError` or `DuplicateInstitutionName` re-render the form with `refused.message`, the submitted value and status `400`, else `_to_list()`
- [ ] T017 [US1] In `app/routers/admin.py` delete the `admin_institutions` placeholder handler for `GET /admin/institutions` (research D7); keep `ADMIN_TABS`, `render_admin`, the `/admin` redirect and the Teachers placeholder unchanged; update the module docstring to say Teachers is a placeholder until milestone 8 and that the Educational institutions tab lives in `app.routers.admin_institutions`
- [ ] T018 [US1] In `app/main.py` import `admin_institutions` and add `app.include_router(admin_institutions.router)` right after `admin_subjects.router`
- [ ] T019 [US1] In `tests/integration/test_admin_area.py`: remove `/admin/institutions` from `PLACEHOLDERS` (Teachers stays); add `test_every_institution_page_marks_the_institutions_tab` checking `/admin/institutions` and `/admin/institutions/new` render the tab row with `current_tabs(body) == ["/admin/institutions"]` and exactly one `aria-current="page"` (US2 extends this list in T026); update the module docstring to say only Teachers is a placeholder
- [ ] T020 [US1] In `tests/integration/test_routes.py::test_the_write_routes_are_exact` add `("POST", "/admin/institutions")` to the expected set and mention institutions in its docstring

**Checkpoint**: US1 tests green. An administrator can list and create institutions at
`/admin/institutions`. MVP is shippable.

---

## Phase 4: User Story 2 - An administrator renames, deactivates, reactivates and deletes institutions (Priority: P2)

**Goal**: rename (any status, case-only allowed), deactivate/activate (idempotent), delete with
confirmation, refusal when in use, and a friendly not-found page.

**Independent Test**: with a few institutions, rename one (and refuse a duplicate), deactivate and
reactivate one, delete an unused one after confirming, and see an in-use institution refused.

### Tests for User Story 2

- [ ] T021 [P] [US2] Add US2 cases to `tests/integration/test_admin_institutions.py`: `GET /admin/institutions/{id}/rename` shows heading "Rename educational institution" and the current name pre-filled (US2-1); rename "Lviv Politechnic" → "Lviv Polytechnic" → `303`, listed with the new name (US2-2); rename "Odesa College" → "lviv polytechnic" → `400` with `DUPLICATE.format("Lviv Polytechnic")` and the entered value, row unchanged (US2-3); "odesa college" → "Odesa College" succeeds (US2-4); renaming an inactive institution succeeds and it stays "Inactive" with the same id (US2-5, SC-007); invalid rename → `400` with the message and value; **Deactivate** → `303`, row shows "Inactive" and an **Activate** form (US2-6); **Activate** → "Active" and a **Deactivate** form (US2-7); deactivating an inactive and activating an active institution → `303`, nothing changes (FR-021); `GET …/delete` names the institution, says "Deleting an educational institution cannot be undone.", has a POST **Delete** form and a **Cancel** link to `/admin/institutions`, and deletes nothing (US2-8); `POST …/delete` → `303`, gone, name free again (US2-9); with `monkeypatch.setattr(app.services.institutions, "count_institution_uses", lambda *_: 1)`, `POST …/delete` → `409`, the page says "“{name}” is in use and cannot be deleted. You can deactivate it instead.", shows a **Deactivate** form when active and no **Delete** button, and the row is unchanged (US2-10, SC-004); for a missing id (999), every rename/delete `GET` and every rename/deactivate/activate/delete `POST` → `404` with `<h1>Educational institution not found</h1>`, "This educational institution does not exist. It may have been deleted." and a link "Back to the educational institutions" to `/admin/institutions`, and no internal details; `/admin/institutions/abc/rename` → the application's normal 404 (no JSON); reloading the list after each action repeats nothing

### Implementation for User Story 2

- [ ] T022 [P] [US2] Create `app/templates/pages/admin/institution_not_found.html`, copying `subject_not_found.html`: title "Educational institution not found — {{ app_name }}", `<h1>Educational institution not found</h1>`, `<p>This educational institution does not exist. It may have been deleted.</p>`, `<p><a href="/admin/institutions">Back to the educational institutions</a></p>`
- [ ] T023 [P] [US2] Create `app/templates/pages/admin/institution_delete.html`, copying `subject_delete.html` with context `institution` and `in_use`: heading `Delete “{{ institution.name }}”?`; when `in_use`, "“{{ institution.name }}” is in use and cannot be deleted. You can deactivate it instead.", a **Deactivate** POST form to `/admin/institutions/{{ institution.id }}/deactivate` only if active, and "Back to the educational institutions"; otherwise "Deleting an educational institution cannot be undone.", a POST form to `/admin/institutions/{{ institution.id }}/delete` with a **Delete** button and a **Cancel** link to `/admin/institutions`
- [ ] T024 [US2] In `app/routers/admin_institutions.py` add, each `@allow_roles(Role.ADMIN)` and with ids declared as `{institution_id:int}`: `_not_found(request)` rendering `institution_not_found.html` with status `404`; `GET /{institution_id:int}/rename` (form, heading "Rename educational institution", current name; `InstitutionNotFound` → `_not_found`); `POST /{institution_id:int}/rename` (`InstitutionNotFound` → `_not_found`; `InstitutionNameError`/`DuplicateInstitutionName` → form again with message, submitted value, `400`; else `_to_list()`); `POST /{institution_id:int}/deactivate` and `/activate` through a shared `_set_active` helper calling `set_institution_active` (`InstitutionNotFound` → `_not_found`; else `_to_list()`); `GET /{institution_id:int}/delete` (confirmation with `in_use=False`, changes nothing); `POST /{institution_id:int}/delete` (`InstitutionNotFound` → `_not_found`; `InstitutionInUse` → confirmation page with `institution=refused.institution`, `in_use=True`, status `409`; else `_to_list()`)
- [ ] T025 [US2] In `tests/integration/test_routes.py::test_the_write_routes_are_exact` add `("POST", "/admin/institutions/{institution_id:int}/rename")`, `("POST", "/admin/institutions/{institution_id:int}/deactivate")`, `("POST", "/admin/institutions/{institution_id:int}/activate")` and `("POST", "/admin/institutions/{institution_id:int}/delete")`
- [ ] T026 [US2] In `tests/integration/test_admin_area.py::test_every_institution_page_marks_the_institutions_tab` add the rename page, the delete confirmation (for an institution created with `create_institution(session, "Lviv Polytechnic")`) and `/admin/institutions/999/rename` (the not-found page) to the checked paths

**Checkpoint**: US1 and US2 tests green. The whole tab works for an administrator.

---

## Phase 5: User Story 3 - Only administrators reach the Educational institutions tab (Priority: P3)

**Goal**: every new page and action refuses every role except a person currently using the
administrator role, and a refused request changes nothing.

**Independent Test**: for each role and for an anonymous visitor, request every new page and send
every new form; only an administrator using the administrator role succeeds, and the institution
rows are unchanged after every refusal.

### Tests for User Story 3

- [ ] T027 [US3] In `tests/integration/test_access_control.py` (milestone 6 user story 4 section): add an `institution_id` fixture (`create_institution(session, "Lviv Polytechnic")`) and `institution_rows(session)` (`session.expire_all()`, then `(id, name, name_key, is_active, updated_at)` for `list_institutions(session)`); change the `{id}` placeholders in `ADMIN_PAGES` / `ADMIN_ACTIONS` to `{subject}` and add `"/admin/institutions/new"`, `"/admin/institutions/{institution}/rename"`, `"/admin/institutions/{institution}/delete"` to `ADMIN_PAGES` and `("/admin/institutions", {"name": "Hacked"})`, `("/admin/institutions/{institution}/rename", {"name": "Hacked"})`, `("/admin/institutions/{institution}/deactivate", {})`, `("/admin/institutions/{institution}/activate", {})`, `("/admin/institutions/{institution}/delete", {})` to `ADMIN_ACTIONS`; format every path with `template.format(subject=subject_id, institution=institution_id)` in the four tests that use them, request the `institution_id` fixture there too, and in the two "changes nothing" tests compare `institution_rows` before and after as well as `subject_rows` (US3-1, US3-2, US3-4, FR-031)
- [ ] T028 [US3] In `tests/integration/test_access_control.py` add `test_an_administrator_using_another_role_is_denied_the_institutions_tab_until_they_switch`, copying the subject version: `client_as(ADMIN_STUDENT_EMAIL, STUDENT)` gets `403` on `/admin/institutions`, then `POST /role` with `role=admin` → `303`, then `200` (US3-3). Note in its docstring that the test cast has no administrator–teacher person, and the rule under test (access follows the current role, not the roles held) is the same for any other role
- [ ] T029 [P] [US3] In `tests/integration/test_cross_site.py` add `test_a_cross_site_institution_action_changes_nothing`, copying the subject version: create "Lviv Polytechnic" with `create_institution`, then for each forged header send `POST /admin/institutions` (`name=Forged`), `…/{id}/rename` (`name=Forged`), `…/{id}/deactivate` and `…/{id}/delete` from `admin_client`; each → `403` with `<h1>Request refused</h1>` and the institution rows unchanged (FR-029)

**Checkpoint**: all user stories green; the route-table sweep in `test_routes.py` (unchanged)
confirms every new route declares `Role.ADMIN`.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T030 [P] Update `README.md`: in "Roles and access", say the **Educational institutions** tab lets administrators create, rename, deactivate/activate and delete institutions, with names unique ignoring case and an institution in use refused deletion, and that **Teachers** is the only remaining placeholder; mention the institution actions in the cross-site paragraph; in the project tree add `schemas/names.py` (shared name rules), `routers/admin_institutions.py`, the `services/` institutions entry, the four institution templates under `pages/admin/`, the `create_institutions` revision, and the new test modules (`test_name_rules.py`, `test_institution_service.py`, `test_admin_institutions.py`)
- [ ] T031 [P] Check that no new log line contains an institution name (`grep -n "logger" app/services/institutions.py app/routers/admin_institutions.py`) and that every new module docstring names specs/007-institutions
- [ ] T032 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`, and, with `TEST_POSTGRES_URL` set, `uv run pytest` again so every database test also runs on PostgreSQL; fix anything red
- [ ] T033 Walk through [quickstart.md](./quickstart.md) section 2 by hand in a browser (institutions list, rename/deactivate/delete, access), and record any deviation as a fix in this branch

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. Internally: 2a (T002 → T003; T004 ∥ T005 after
  T002) → 2b (T006 → T007 → T008 → T009) → 2c (T010 → T011). **Blocks every user story.**
- **US1 (Phase 3)**: depends on Phase 2.
- **US2 (Phase 4)**: depends on US1 (it extends `admin_institutions.py`, `test_admin_institutions.py`,
  `test_admin_area.py` and the write-route test that US1 touches).
- **US3 (Phase 5)**: depends on US1 and US2 (it exercises every institution route).
- **Polish (Phase 6)**: depends on all stories.

### User Story Dependencies

- **US1 (P1)**: independent after Foundational. MVP.
- **US2 (P2)**: builds on US1's router and list template; testable on its own once US1 exists.
- **US3 (P3)**: verification only; covers the routes of US1 and US2.

### Within Each User Story

- Tests are written first and fail before the implementation.
- Templates before the router handlers that render them.
- Router before `main.py` registration and the write-route test update.

### Same-file sequencing to respect

- `app/schemas/subject.py` and `app/schemas/names.py`: T002 → T003.
- `tests/integration/test_admin_institutions.py`: T012 → T021.
- `tests/integration/test_admin_area.py`: T019 → T026.
- `tests/integration/test_routes.py`: T020 → T025.
- `tests/integration/test_access_control.py`: T027 → T028.
- `app/routers/admin_institutions.py`: T016 → T024.

### Parallel Opportunities

- 2a: T004 ∥ T005 after T002.
- US1: T012 ∥ T013 ∥ T014 ∥ T015.
- US2: T021 ∥ T022 ∥ T023.
- US3: T029 ∥ T027.
- Polish: T030 ∥ T031.

---

## Parallel Example: User Story 1

```bash
# Tests, templates and CSS together (different files):
Task: "T012 [US1] US1 HTTP tests in tests/integration/test_admin_institutions.py"
Task: "T013 [US1] Institution list template in app/templates/pages/admin/institutions.html"
Task: "T014 [US1] Create/rename form template in app/templates/pages/admin/institution_form.html"
Task: "T015 [US1] Institution list CSS in app/static/css/app.css"

# Then, in order:
Task: "T016 [US1] List, new and create handlers in app/routers/admin_institutions.py"
Task: "T017 [US1] Remove the placeholder handler from app/routers/admin.py"
Task: "T018 [US1] Register admin_institutions.router in app/main.py"
```

## Parallel Example: User Story 2

```bash
Task: "T021 [US2] US2 HTTP tests in tests/integration/test_admin_institutions.py"
Task: "T022 [US2] Not-found page in app/templates/pages/admin/institution_not_found.html"
Task: "T023 [US2] Delete confirmation in app/templates/pages/admin/institution_delete.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (baseline green).
2. Phase 2: Foundational — shared name rules, table, service.
3. Phase 3: US1 — list and create.
4. **STOP and VALIDATE**: US1 tests green; an administrator creates institutions at
   `/admin/institutions` and sees them sorted, with invalid and duplicate names refused.

### Incremental Delivery

1. Setup + Foundational → shared rules, table and service; suite green; no visible change.
2. + US1 → institutions can be listed and created (MVP).
3. + US2 → rename, deactivate/activate, delete with confirmation and in-use refusal.
4. + US3 tests → access matrix and cross-site refusal pinned for every new route.
5. Polish → README, ruff, both engines, manual walk-through.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- Commit after each checkpoint (end of Phase 2, end of each story).
- Keep messages exactly as written in research.md D8 and contracts/http-routes.md; the tests assert
  them verbatim.
- Do not change subject behaviour, subject templates or subject tests: T003 must leave every
  subject test passing unchanged.
- Do not build anything for milestones 8 and 9: no teacher or student links, no "active
  institutions only" query, no `count_institution_uses` sources.
