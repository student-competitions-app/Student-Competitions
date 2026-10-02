---

description: "Task list for milestone 6: administrator area — Teachers, Educational institutions, Subjects"
---

# Tasks: Administrator Area — Teachers, Educational Institutions, Subjects (Milestone 6)

**Input**: Design documents from `/specs/006-admin-area/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/subject-service.md](./contracts/subject-service.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-040 lists the automated tests, and constitution Principle III requires
test-backed delivery. Database tests run on SQLite and, when `TEST_POSTGRES_URL` is set, on
PostgreSQL, through the existing `database_url` fixture. Signed-in clients come from the
`client_as` / `admin_client` fixtures in `tests/conftest.py`.

**Organization**: Tasks are grouped by user story. The area shell (tab row, `/admin` redirect,
placeholder tabs) is in the Foundational phase: every administrator page renders the tab row, so
its three targets must exist before any subject page is useful. The US3 phase then holds the
acceptance tests that prove the shell.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Paths are relative to the repository root (single FastAPI application, see plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the starting point. The milestone adds no dependency and no new top-level
directory (plan, Technical Context).

- [X] T001 On branch `006-admin-area`, run `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` and confirm all are green before any change; record any pre-existing failure instead of fixing it here (no file changes)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The contraction migration, the subject name rules, table and service, and the
administrator area shell. US1–US4 all build on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### 2a. Contraction: drop `users.role` (research D8)

- [X] T002 Create the Alembic revision `migrations/versions/2026_10_02_<rev>_drop_legacy_user_role.py` with `uv run alembic revision -m "drop legacy user role"` (hand-written, not autogenerate), `down_revision = "50f17535d874"`. Upgrade: `with op.batch_alter_table("users") as batch: batch.drop_column("role")`. Downgrade: `batch.add_column(sa.Column("role", sa.String(20), nullable=True))`. Use only `sqlalchemy as sa` and `alembic.op`, never the ORM models, as `2026_10_01_50f17535d874_add_user_roles.py` does; module docstring names spec 006 and research D8
- [X] T003 Remove the `legacy_role` field (the `Column("role", String(20), nullable=True)` mapping) from `User` in `app/models/user.py`, together with its docstring and any module-docstring sentence that promises milestone 6 will drop the column; drop imports that become unused
- [X] T004 [P] In `tests/integration/test_user_reconcile.py`: delete the `assert all(user.legacy_role is None …)` line (around line 87), and in `test_s8_a_migrated_administrator_is_unchanged` remove the `legacy_role="admin"` argument and the "old column" wording from its docstring (delete the whole case only if it then duplicates s1)
- [X] T005 [P] In `tests/integration/test_migrations.py`: pin `test_upgrade_keeps_the_active_administrators` and `test_downgrade_deactivates_everyone_who_is_not_an_administrator` to revision `"50f17535d874"` instead of `"head"` (they write `users.role`, which no longer exists at head); in `test_empty_to_head` also assert that `"role"` is not among `inspect(engine).get_columns("users")` names

**Checkpoint**: `uv run pytest` is green; stairway and drift tests pass with the new revision.

### 2b. Subject name rules (research D1, D2)

- [X] T006 [P] Create `app/schemas/subject.py` (pure, no I/O, only `unicodedata` from the standard library): `SUBJECT_NAME_MAX_LENGTH = 200`, `SUBJECT_NAME_KEY_MAX_LENGTH = 600`; `class SubjectNameError(ValueError)` with a `message: str` attribute ready for the form; `clean_subject_name(raw: str) -> str` applying, in this order: (1) refuse if **any** character of the raw value has Unicode category starting with `C` or equal to `Zl`/`Zp` → "The name cannot contain tabs, line breaks or other control characters."; (2) `str.strip()`; (3) empty → "Enter a name."; (4) more than 200 code points → "The name can be at most 200 characters."; return the trimmed name with inner spaces untouched. `subject_name_key(name: str) -> str` returns `unicodedata.normalize("NFC", name).casefold()`. Module docstring points to specs/006-admin-area/research.md D1–D2
- [X] T007 [P] Create `tests/unit/test_subject_schemas.py` covering every row of the data-model validation table with the exact messages: "  Computer Science  " → "Computer Science"; "Computer  Science" keeps its double space; "", "   " → "Enter a name."; 200 code points accepted, 201 refused (also with 200 Cyrillic letters); leading `\t`, inner `\n`, U+2028, U+202E, U+0000 refused with the control-character message even when the rest is valid; `subject_name_key`: "Фізика" == "ФІЗИКА", "ß" == "SS" (casefold), NFC "é" (U+00E9) == NFD "é", "Physics" == "PHYSICS"

### 2c. Subject table (data-model §1, §3)

- [X] T008 Create `app/models/subject.py`: `class Subject(SQLModel, table=True)`, `__tablename__ = "subjects"`; `id: int | None` primary key; `name` `Column(String(SUBJECT_NAME_MAX_LENGTH), nullable=False)` ("As entered after trimming"); `name_key` `Column(String(SUBJECT_NAME_KEY_MAX_LENGTH), nullable=False, unique=True)` so the naming convention yields `uq_subjects_name_key` ("Never shown"); `is_active: bool` not null, default `True`; `created_at` and `updated_at` with `default_factory=utc_now, sa_type=UTCDateTime, nullable=False` as in `app/models/question.py`. Import the limits from `app.schemas.subject`. Module docstring: only administrators change subjects; milestones 9 and 10 add references and must extend `count_subject_uses`
- [X] T009 Export `Subject` from `app/models/__init__.py` (import and `__all__`, alphabetical), so `SQLModel.metadata` and the drift test see it
- [X] T010 Create the Alembic revision `migrations/versions/2026_10_02_<rev>_create_subjects.py` with `down_revision` = the T002 revision. Upgrade: `op.create_table("subjects", sa.Column("id", sa.Integer(), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("name_key", sa.String(600), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")), sa.UniqueConstraint("name_key", name=op.f("uq_subjects_name_key")))`. Downgrade: `op.drop_table("subjects")`. No data inserted (the list starts empty)
- [X] T011 In `tests/integration/test_migrations.py` add `"subjects"` to `APPLICATION_TABLES`; run `uv run pytest tests/integration/test_migrations.py` and confirm empty → head, stairway, single head and `test_models_match_the_migrated_schema` (drift) pass (depends on T005, same file)

### 2d. Subject service (contracts/subject-service.md, research D3, D4)

- [X] T012 Create `app/services/subjects.py` per contracts/subject-service.md: exceptions `SubjectNotFound(LookupError)` (`subject_id`), `DuplicateSubjectName(ValueError)` (`existing_name`, `message` = "A subject named “{existing_name}” already exists." using the **stored** name), `SubjectInUse(ValueError)` (`subject`, `uses`); functions taking `session: Session` first: `list_subjects` (all rows, `sorted(key=lambda s: (s.name_key, s.id))` in Python, no `ORDER BY`), `get_subject`, `create_subject` (clean → pre-check same key → insert `is_active=True` → commit; `IntegrityError` → rollback → re-query by key → `DuplicateSubjectName`), `rename_subject` (load first so `SubjectNotFound` wins, then clean; duplicate = **other** subject with same key; no write when `name` and `name_key` are unchanged; else set both plus `updated_at = utc_now()`; `IntegrityError` → rollback → `DuplicateSubjectName`), `set_subject_active(session, subject_id, active)` (no write if already that status, else set + `updated_at`), `count_subject_uses(session, subject_id) -> int` returning `0` with a docstring naming milestone 9 (questions) and 10 (competitions) as the places to add counts and warning that SQLite foreign keys are off, `delete_subject` (load; `count_subject_uses(...) > 0` → `SubjectInUse`; delete + commit; `IntegrityError` → rollback → `SubjectInUse`). Call `count_subject_uses` through the module global so tests can monkeypatch it. Each successful write logs one `INFO` line on `logging.getLogger("uvicorn.error")` with id only: `Subject created: id=%d`, `Subject renamed: id=%d`, `Subject deactivated: id=%d`, `Subject activated: id=%d`, `Subject deleted: id=%d` (no-ops log nothing). Module docstring: no authorization here; callers must be `@allow_roles(Role.ADMIN)`
- [X] T013 Create `tests/integration/test_subject_service.py` (uses the `session` fixture, so it runs on both engines): create stores trimmed name, `name_key`, `is_active=True`; create duplicate in other case / Cyrillic case / of an inactive subject → `DuplicateSubjectName` with the stored name in `message`; invalid names → `SubjectNameError`; list order for "Physics", "chemistry", "Mathematics" is chemistry, Mathematics, Physics, and equal keys cannot occur but ties sort by id; rename to other case succeeds; rename to own unchanged name leaves `updated_at` unchanged; rename onto another subject's name → `DuplicateSubjectName` and the row is unchanged; rename/set_active/delete/get of a missing id → `SubjectNotFound` (rename of a missing id with an invalid name still raises `SubjectNotFound`); rename keeps `is_active`; `set_subject_active` no-op leaves `updated_at` unchanged; a direct `session.add(Subject(... same name_key ...))` + commit raises `IntegrityError` (the concurrency guarantee); `create_subject` turns an `IntegrityError` into `DuplicateSubjectName` (monkeypatch the pre-check lookup away, or insert the rival row through a second session between check and commit); `delete_subject` removes the row and frees the name; with `monkeypatch.setattr(app.services.subjects, "count_subject_uses", lambda *_: 1)` delete raises `SubjectInUse` and the row remains; log lines contain the id and no name

### 2e. Administrator area shell (research D6, D7; contracts/http-routes.md "Area shell", "Admin layout")

- [X] T014 Create `app/routers/admin.py`: module docstring (spec 006, research D6); `@dataclass(frozen=True) class AdminTab: key: str; label: str; path: str`; `ADMIN_TABS = (AdminTab("teachers", "Teachers", "/admin/teachers"), AdminTab("institutions", "Educational institutions", "/admin/institutions"), AdminTab("subjects", "Subjects", "/admin/subjects"))` in that order; a helper `render_admin(request, template, active_tab: str, context: dict | None = None, status_code: int = 200) -> HTMLResponse` that adds `app_name=APP_NAME`, `admin_tabs=ADMIN_TABS`, `active_tab`; `router = APIRouter()`; `GET /admin` declared with `@allow_roles(*ADMIN_AREA.roles)` (import `ADMIN_AREA` from `app.routers.areas`) returning `RedirectResponse("/admin/teachers", status_code=303)`; `GET /admin/teachers` and `GET /admin/institutions`, each `@allow_roles(Role.ADMIN)`, rendering `pages/admin/placeholder.html` with the tab key and the heading ("Teachers" / "Educational institutions") and one sentence ("Teacher management will arrive in a later milestone." / "Managing educational institutions will arrive in a later milestone.")
- [X] T015 [P] Create `app/templates/layouts/admin.html`: `{% extends "layouts/base.html" %}`; in `{% block content %}` first render `<nav class="admin-tabs" aria-label="Administrator area"><ul>` with one `<li><a href="{{ tab.path }}">{{ tab.label }}</a></li>` per `admin_tabs`, adding `aria-current="page"` only when `tab.key == active_tab`; then `{% block admin_content %}{% endblock %}`. No script, no `hx-` attributes
- [X] T016 [P] Create `app/templates/pages/admin/placeholder.html` extending `layouts/admin.html`: title block `{{ heading }} — {{ app_name }}`, `<h1>{{ heading }}</h1>` and `<p>{{ note }}</p>`; no forms or buttons (FR-007)
- [X] T017 [P] In `app/static/css/app.css` add `.admin-tabs` styles: horizontal row of links that wraps at phone width (no horizontal page scroll), a clear visual highlight on `.admin-tabs a[aria-current="page"]` (e.g. bottom border + bold, Pico colour variables), and a `.subjects-table` style for the list (status column, compact inline action forms with `display: inline` and no extra margin)
- [X] T018 In `app/routers/areas.py` delete the `admin_area` handler for `ADMIN_AREA.path`; keep `ADMIN_AREA` in `AREAS` so the home page link "Administrator area" → `/admin` is unchanged (FR-008); update the module docstring to say `/admin` is now served by `app/routers/admin.py`
- [X] T019 In `app/main.py` import `admin` from `app.routers` and add `app.include_router(admin.router)` after `areas.router`
- [X] T020 In `tests/integration/test_routes.py` change `test_every_declared_page_admits_exactly_its_roles` (research D9): for an allowed role assert `status != 403`; for any other role assert `status == 403`; update its docstring to cite research D9 (a 303 redirect and a 404 for a missing subject both prove access was granted)
- [X] T021 In `tests/integration/test_access_control.py`: in `ACCESS_TABLE` and `TITLES` replace `"/admin"` with `"/admin/teachers"` (title "Teachers"); restrict the `PLACEHOLDER` assertion in `test_the_access_table` and `test_the_access_denied_page` to the milestone 5 areas (the admin tab has its own sentence); make `test_anonymous_visitors_are_sent_to_sign_in` build the expected `next` with `urllib.parse.quote(path, safe="")` so nested paths work; add `test_admin_redirects_to_the_teachers_tab` (administrator: `GET /admin` → 303, `Location: /admin/teachers`; teacher and student: 403); keep `HOME_LINKS` and `test_a_denial_is_logged_without_identity` (route `/admin`) unchanged

**Checkpoint**: `uv run pytest` is green. An administrator can open `/admin` and land on the
Teachers tab with the three-tab row; Subjects links to a page that US1 delivers.

---

## Phase 3: User Story 1 - An administrator manages the list of subjects (Priority: P1) 🎯 MVP

**Goal**: The Subjects tab lists every subject (name, Active/Inactive, sorted ignoring case),
shows "No subjects yet" when empty, and creates subjects through a form that refuses invalid and
duplicate names with the entered value kept.

**Independent Test**: As an administrator, open `/admin/subjects`, create "Mathematics",
"Physics", "chemistry", check the order, then submit "  PHYSICS  ", "", 201 characters and a
name with a tab, and check each is refused with its message and the value kept.

### Tests for User Story 1 ⚠️

> Write these first and confirm they fail before implementing.

- [X] T022 [P] [US1] Create `tests/integration/test_admin_subjects.py` (`admin_client`, `session` fixtures) with US1 acceptance scenarios 1–6: empty list shows "No subjects yet" and a Create link to `/admin/subjects/new`; `GET /admin/subjects/new` → 200 with `<form method="post" action="/admin/subjects">`, a `name` input with `maxlength="200"` and `required`, Save and a Cancel link to `/admin/subjects`; `POST /admin/subjects` `name=Mathematics` → 303 `Location: /admin/subjects`, then the list shows "Mathematics" and "Active"; order chemistry, Mathematics, Physics (assert positions in the HTML); "  PHYSICS  " after "Physics" → 400, body contains "A subject named “Physics” already exists." and `value="  PHYSICS  "`, count unchanged; empty, spaces only, 201 chars, "Math\tematics" → 400 with the matching message from data-model.md and the submitted value (HTML-escaped) kept, nothing stored; missing `name` field treated as empty; "  Computer Science  " stored as "Computer Science"; "ФІЗИКА" after "Фізика" refused; "Computer  Science" and "Computer Science" both accepted; duplicate of an inactive subject (deactivate via `set_subject_active`) refused; reloading `GET /admin/subjects` after a create does not add a row (SC-007); the list, the create form and its 400 re-render each show the tab row with only Subjects carrying `aria-current="page"`

### Implementation for User Story 1

- [X] T023 [P] [US1] Create `app/templates/pages/admin/subjects.html` extending `layouts/admin.html`: `<h1>Subjects</h1>`, a Create link (`<a href="/admin/subjects/new" role="button">Create</a>`); when `subjects` is empty `<p>No subjects yet</p>`; otherwise `<table class="subjects-table">` with a Name and a Status column ("Active"/"Inactive") per subject, rows in the order received; leave an Actions column for US2
- [X] T024 [P] [US1] Create `app/templates/pages/admin/subject_form.html` extending `layouts/admin.html`, driven by context `heading`, `action`, `value`, `error`: `<h1>{{ heading }}</h1>`, `<form method="post" action="{{ action }}">` with a labelled `<input type="text" name="name" id="name" maxlength="200" required value="{{ value }}">`, the error (when present) shown with `aria-invalid="true"` on the input and `aria-describedby` pointing to a `<small id="name-error">{{ error }}</small>`, a Save button and `<a href="/admin/subjects">Cancel</a>`; must work for both create (US1) and rename (US2) without changes
- [X] T025 [US1] Create `app/routers/admin_subjects.py`: module docstring (spec 006, contracts/http-routes.md; routers only parse, call the service, map errors, redirect); `router = APIRouter(prefix="/admin/subjects")`; every handler `@allow_roles(Role.ADMIN)` and rendered through `render_admin(..., active_tab="subjects")` from `app.routers.admin`; `GET ""` → `subjects.html` with `list_subjects(session)`; `GET "/new"` → `subject_form.html` with heading "New subject", action `/admin/subjects`, empty value; `POST ""` with `name: str = Form("")` → `create_subject`; success `RedirectResponse("/admin/subjects", status_code=303)`; `SubjectNameError` / `DuplicateSubjectName` → form again with `status_code=400`, its `message` and the raw submitted value (depends on T014, T023, T024)
- [X] T026 [US1] In `app/main.py` import `admin_subjects` from `app.routers` and add `app.include_router(admin_subjects.router)` after `admin.router`
- [X] T027 [US1] In `tests/integration/test_routes.py` rename `test_the_write_routes_are_exactly_signing_in_and_out_and_choosing_a_role` to `test_the_write_routes_are_exact` and add `("POST", "/admin/subjects")` to the expected set

**Checkpoint**: US1 acceptance scenarios pass; the MVP (list + create) is usable at
`/admin/subjects`.

---

## Phase 4: User Story 2 - An administrator renames, deactivates and deletes subjects (Priority: P2)

**Goal**: Each listed subject offers Rename, Deactivate/Activate and Delete; deletion goes
through a confirmation page and is refused (409) for a subject in use; a missing subject shows a
friendly 404 inside the area.

**Independent Test**: With a few subjects, rename one (including to a duplicate, refused, and a
case-only change, accepted), deactivate and reactivate one, cancel and then confirm deletion of
one; with `count_subject_uses` monkeypatched to 1, confirm the deletion is refused.

### Tests for User Story 2 ⚠️

- [X] T028 [P] [US2] Extend `tests/integration/test_admin_subjects.py` with US2 acceptance scenarios 1–9 and edge cases: each list row has a Rename link `/admin/subjects/{id}/rename`, a Delete link `/admin/subjects/{id}/delete`, and a `<form method="post">` to `/deactivate` (active) or `/activate` (inactive); rename form is pre-filled with the current name; rename "Mathmatics" → "Mathematics" → 303 and listed; rename "Chemistry" → "physics" → 400 with "A subject named “Physics” already exists.", value kept, row unchanged; case-only rename "physics" → "Physics" succeeds; unchanged rename → 303 and `updated_at` unchanged; renaming an inactive subject keeps it Inactive; invalid rename → 400 with message; deactivate → Inactive with Activate button; activate → Active; deactivate an inactive / activate an active → 303, no change; `GET /delete` → 200 page naming the subject with "Deleting a subject cannot be undone.", a Delete form and a Cancel link to `/admin/subjects`, and nothing deleted; `POST /delete` → 303, row gone, name reusable; with `monkeypatch.setattr(app.services.subjects, "count_subject_uses", lambda *_: 1)`: `POST /delete` → 409, “{name}” is in use and cannot be deleted. You can deactivate it instead., no Delete button, a Deactivate form only when the subject is active, row unchanged; every `GET`/`POST` on `/admin/subjects/999/...` (rename, deactivate, activate, delete) → 404 with `<h1>Subject not found</h1>`, "This subject does not exist. It may have been deleted.", a link to `/admin/subjects`, the tab row with Subjects current, and no traceback; `GET /admin/subjects/abc/rename` → the application's HTML 404 page, not JSON 422; rename/delete/not-found pages show only Subjects with `aria-current="page"`; reloading the list after each action repeats nothing

### Implementation for User Story 2

- [X] T029 [P] [US2] Create `app/templates/pages/admin/subject_not_found.html` extending `layouts/admin.html`: title "Subject not found — {{ app_name }}", `<h1>Subject not found</h1>`, `<p>This subject does not exist. It may have been deleted.</p>`, `<a href="/admin/subjects">Back to the subjects</a>`
- [X] T030 [P] [US2] Create `app/templates/pages/admin/subject_delete.html` extending `layouts/admin.html`, context `subject`, `in_use: bool`: `<h1>Delete “{{ subject.name }}”?</h1>`; when not `in_use`: `<p>Deleting a subject cannot be undone.</p>`, `<form method="post" action="/admin/subjects/{{ subject.id }}/delete">` with a Delete button, and `<a href="/admin/subjects">Cancel</a>`; when `in_use`: `<p>“{{ subject.name }}” is in use and cannot be deleted. You can deactivate it instead.</p>`, no Delete button, a Deactivate form posting to `/admin/subjects/{{ subject.id }}/deactivate` only if `subject.is_active`, and a link back to `/admin/subjects`
- [X] T031 [US2] In `app/routers/admin_subjects.py` add, all `@allow_roles(Role.ADMIN)` with `{subject_id:int}` in the path: a local helper rendering `subject_not_found.html` with `status_code=404` for `SubjectNotFound`; `GET "/{subject_id:int}/rename"` → `subject_form.html` with heading "Rename subject", action `/admin/subjects/{id}/rename`, value = current name; `POST "/{subject_id:int}/rename"` (`name: str = Form("")`) → `rename_subject`, 303 on success, 400 form re-render with message and submitted value on `SubjectNameError`/`DuplicateSubjectName`; `POST "/{subject_id:int}/deactivate"` and `POST "/{subject_id:int}/activate"` → `set_subject_active(..., False/True)` → 303; `GET "/{subject_id:int}/delete"` → `subject_delete.html` with `in_use=False` (no write); `POST "/{subject_id:int}/delete"` → `delete_subject` → 303; `SubjectInUse` → `subject_delete.html` with `in_use=True`, `status_code=409` (depends on T025, T029, T030)
- [X] T032 [US2] In `app/templates/pages/admin/subjects.html` add the Actions column: `<a href="/admin/subjects/{{ s.id }}/rename">Rename</a>`; a one-button `<form method="post" action="/admin/subjects/{{ s.id }}/deactivate">` labelled Deactivate when `s.is_active`, else `.../activate` labelled Activate; `<a href="/admin/subjects/{{ s.id }}/delete">Delete</a>`
- [X] T033 [US2] In `tests/integration/test_routes.py` add to `test_the_write_routes_are_exact` the five routes `("POST", "/admin/subjects/{subject_id:int}/rename")`, `.../deactivate`, `.../activate`, `.../delete` — use the exact path strings the route table reports (check with `endpoints()`), so the set holds all six subject `POST`s

**Checkpoint**: US1 and US2 pass together; the full subject lifecycle works over HTTP.

---

## Phase 5: User Story 3 - The administrator area is a set of tabs with their own addresses (Priority: P3)

**Goal**: Prove the shell built in Phase 2e: `/admin` redirects to Teachers, every tab has its
own address and exactly one highlighted tab, placeholders offer no actions, and the tabs appear
only inside the area.

**Independent Test**: As an administrator request `/admin`, `/admin/teachers`,
`/admin/institutions`, `/admin/subjects`; check the redirect, the three tabs in order on each
page and exactly one `aria-current="page"` on the matching link.

### Tests for User Story 3 ⚠️

- [X] T034 [P] [US3] Create `tests/integration/test_admin_area.py` (`admin_client`): `GET /admin` → 303 `Location: /admin/teachers` and following it lands on the Teachers tab (US3-1, FR-005); parametrized over the three tab paths: 200, a `<nav class="admin-tabs" aria-label="Administrator area">` whose links (regex on the nav block) are exactly `[("/admin/teachers","Teachers"), ("/admin/institutions","Educational institutions"), ("/admin/subjects","Subjects")]` in that order, exactly one `aria-current="page"` and it is on the requested path (US3-2, SC-004); tabs are plain `<a href>` links: the nav contains no `<form>`, no `hx-` attribute, and the page has no `<script>` (FR-003); Teachers and Educational institutions show their `<h1>` and placeholder sentence and the content after the nav has no `<form>` or `<button>` (US3-4, FR-007); two consecutive `GET`s of each tab return the same body (reload/bookmark); the home page `/`, `/staff` and the role page for an administrator contain no `admin-tabs`; `/admin/unknown` → 404 with the application's normal not-found page and no `admin-tabs`; the home page "Administrator area" link still points to `/admin` (FR-008)
- [X] T035 [US3] In `tests/integration/test_admin_area.py` add the subject-page highlight cases (US3-5, FR-004): create a subject through the service, then for `/admin/subjects/new`, `/admin/subjects/{id}/rename`, `/admin/subjects/{id}/delete` and `/admin/subjects/999/rename` assert the tab row is present and the only `aria-current="page"` is on `/admin/subjects` (depends on US1 and US2 pages)

**Checkpoint**: US3 acceptance scenarios 1–5 pass.

---

## Phase 6: User Story 4 - Only administrators reach the administrator area (Priority: P4)

**Goal**: Prove that every new page and action is open only to a person currently using the
administrator role, that refusals change nothing, and that cross-site posts are refused.
Enforcement already comes from `@allow_roles` + `resolve_access` (milestone 5); if any test here
fails, fix the declaration on the offending handler in `app/routers/admin.py` or
`app/routers/admin_subjects.py`, never the test.

**Independent Test**: For teacher, student, administrator-using-student and anonymous visitors,
request every new page and post every new form; only the administrator in the administrator role
succeeds and the subject table is identical after every refusal.

### Tests for User Story 4 ⚠️

- [X] T036 [P] [US4] In `tests/integration/test_access_control.py` add `ADMIN_PAGES = ["/admin", "/admin/teachers", "/admin/institutions", "/admin/subjects", "/admin/subjects/new", "/admin/subjects/{id}/rename", "/admin/subjects/{id}/delete"]` and `ADMIN_ACTIONS = [("/admin/subjects", {"name": "Hacked"}), ("/admin/subjects/{id}/rename", {"name": "Hacked"}), ("/admin/subjects/{id}/deactivate", {}), ("/admin/subjects/{id}/activate", {}), ("/admin/subjects/{id}/delete", {})]` with `{id}` filled from a subject created through `create_subject`; tests: teacher and student get 403 with "Your current role, {label}, cannot open this page." on every page (US4-1, FR-037); teacher and student get 403 on every action and the `(id, name, name_key, is_active, updated_at)` rows of `subjects` are identical before and after (US4-2); a person holding administrator + student (`ADMIN_STUDENT_EMAIL`) using the student role gets 403 on `/admin/subjects`, then after `POST /role` `role=admin` gets 200 (US4-3, FR-036); anonymous `GET` of every page → 303 `Location: /login?next=<quote(path, safe="")>` (US4-4, FR-038), anonymous `POST` of every action → 303 to `/login` and nothing changes; after signing in as an administrator through the real code flow (as `tests/integration/test_login_flow.py` does, with `next=/admin/subjects`) the browser lands on `/admin/subjects`
- [X] T037 [US4] In `tests/integration/test_access_control.py` add `test_no_admin_tabs_for_other_roles` (US4-5, FR-006): for the teacher and the student, every page they may open (`/`, `/teacher`, `/student`, `/staff` where allowed) and the 403 page for `/admin/subjects` contain no `admin-tabs` and no link to `/admin/teachers`, `/admin/institutions` or `/admin/subjects` (same file as T036)
- [X] T038 [P] [US4] In `tests/integration/test_cross_site.py` add `test_a_cross_site_subject_action_changes_nothing` (FR-034), in the style of `test_a_cross_site_switch_changes_nothing` with the `forged` headers: an administrator browser posting `POST /admin/subjects` `name=Forged`, and `POST /admin/subjects/{id}/delete` / `/deactivate` / `/rename` for an existing subject, each → 403 with `<h1>Request refused</h1>`, and the `subjects` rows are unchanged

**Checkpoint**: All four user stories pass independently; SC-003 holds for every new route.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, lint and end-to-end validation.

- [X] T039 [P] Update `README.md` section "Roles and access": in the page table replace the `/admin` row with `/admin` (redirects to `/admin/teachers`), `/admin/teachers`, `/admin/institutions`, `/admin/subjects` (all administrator only); change "The four areas are placeholders" so it says the administrator area now has three tabs, Teachers and Educational institutions are placeholders, and Subjects lets administrators create, rename, deactivate/activate and delete subjects (names unique ignoring case, a subject in use cannot be deleted); mention that `users.role` was dropped if the README documents the schema
- [X] T040 [P] Grep the repository (`app/`, `tests/`, `README.md`, `docs/`) for `legacy_role`, the `admin_area` handler and the old "Administrator area" placeholder text, and remove or update any stale reference left behind (excluding `specs/` history and old migrations)
- [X] T041 Run `uv run ruff check .` and `uv run ruff format .` and fix any finding in the new and changed files
- [X] T042 Run the full suite on both engines: `uv run pytest` and `TEST_POSTGRES_URL=<local postgres> uv run pytest`; all green, including the milestone 1–5 tests (SC-008)
- [X] T043 Run the manual walk-through in `specs/006-admin-area/quickstart.md` section 2 (Tabs, Subjects, Access) with the four local accounts, including phone-width layout of the tab row and the subjects table, and record any deviation as a fix task. Done 2026-10-02 as a script against a live uvicorn server (real code sign-in): all steps pass, no deviation. Phone-width layout not checked visually (no browser available); still to be eyeballed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. Internally: 2a (T002 → T003 → T004, T005) →
  2b (T006, T007) → 2c (T008 → T009 → T010 → T011) → 2d (T012 → T013); 2e (T014–T021) needs
  only 2a done and can run alongside 2b–2d. **Blocks every user story.**
- **US1 (Phase 3)**: depends on Phase 2.
- **US2 (Phase 4)**: depends on Phase 2 and on US1 (it extends `admin_subjects.py`,
  `subjects.html` and the write-route test that US1 creates).
- **US3 (Phase 5)**: T034 depends only on Phase 2 (plus `/admin/subjects` from US1 for the
  Subjects tab case); T035 depends on US1 and US2.
- **US4 (Phase 6)**: depends on US1 and US2 (it exercises every subject route).
- **Polish (Phase 7)**: depends on all stories.

### User Story Dependencies

- **US1 (P1)**: independent after Foundational. MVP.
- **US2 (P2)**: builds on US1's router and list template; testable on its own once US1 exists.
- **US3 (P3)**: implementation is in Foundational 2e; its tests are independent apart from the
  subject-page highlight case (T035).
- **US4 (P4)**: verification only; covers the routes of US1–US3.

### Within Each User Story

- Tests are written first and fail before the implementation.
- Templates before the router handlers that render them.
- Router before `main.py` registration and the write-route test update.

### Same-file sequencing to respect

- `tests/integration/test_migrations.py`: T005 → T011.
- `tests/integration/test_routes.py`: T020 → T027 → T033.
- `tests/integration/test_access_control.py`: T021 → T036 → T037.
- `tests/integration/test_admin_subjects.py`: T022 → T028.
- `tests/integration/test_admin_area.py`: T034 → T035.
- `app/routers/admin_subjects.py`: T025 → T031.
- `app/templates/pages/admin/subjects.html`: T023 → T032.
- `app/main.py`: T019 → T026.

### Parallel Opportunities

- 2a: T004 ∥ T005 after T003.
- 2b: T006 ∥ T007.
- 2e: T015 ∥ T016 ∥ T017 (templates and CSS), alongside 2b–2d.
- US1: T022 ∥ T023 ∥ T024.
- US2: T028 ∥ T029 ∥ T030.
- US4: T036 ∥ T038.
- Polish: T039 ∥ T040.

---

## Parallel Example: User Story 1

```bash
# Tests and templates together (different files):
Task: "T022 [US1] US1 HTTP tests in tests/integration/test_admin_subjects.py"
Task: "T023 [US1] Subject list template in app/templates/pages/admin/subjects.html"
Task: "T024 [US1] Create/rename form template in app/templates/pages/admin/subject_form.html"

# Then, in order:
Task: "T025 [US1] List, new and create handlers in app/routers/admin_subjects.py"
Task: "T026 [US1] Register admin_subjects.router in app/main.py"
Task: "T027 [US1] Add POST /admin/subjects to the write-route test in tests/integration/test_routes.py"
```

## Parallel Example: User Story 2

```bash
Task: "T028 [US2] US2 HTTP tests in tests/integration/test_admin_subjects.py"
Task: "T029 [US2] Not-found page in app/templates/pages/admin/subject_not_found.html"
Task: "T030 [US2] Delete confirmation in app/templates/pages/admin/subject_delete.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (baseline green).
2. Phase 2: Foundational — contraction migration, name rules, table, service, area shell.
3. Phase 3: US1 — list and create.
4. **STOP and VALIDATE**: US1 tests green; an administrator creates subjects at
   `/admin/subjects` and sees them sorted, with invalid and duplicate names refused.

### Incremental Delivery

1. Setup + Foundational → the area exists with three tabs; suite green.
2. + US1 → subjects can be listed and created (MVP).
3. + US2 → rename, deactivate/activate, delete with confirmation and in-use refusal.
4. + US3 tests → the shell's contract is pinned for milestones 7 and 8.
5. + US4 tests → access matrix and cross-site refusal pinned for every new route.
6. Polish → README, ruff, both engines, manual walk-through.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- Commit after each checkpoint (end of 2a, end of Phase 2, end of each story).
- Keep messages exactly as written in data-model.md and contracts/http-routes.md; the tests
  assert them verbatim.
- Do not build anything for the Teachers or Educational institutions tabs beyond their
  placeholders (FR-041), and do not add `count_subject_uses` sources (milestones 9, 10).
