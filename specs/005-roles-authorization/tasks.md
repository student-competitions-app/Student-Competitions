---

description: "Task list for Roles and Authorization (Milestone 5)"
---

# Tasks: Roles and Authorization (Milestone 5)

**Input**: Design documents from `/specs/005-roles-authorization/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle III is non-negotiable, FR-040 and FR-041 list the
required automated checks, and [plan.md](./plan.md#technical-context) names the test modules: new
`test_access_control.py`, `test_role_choice.py`, `test_role_switch.py`, `test_cross_site.py`,
`tests/unit/test_cross_site_rule.py`; renamed `test_admin_reconcile.py` → `test_user_reconcile.py`;
changed `test_routes.py`, `test_sessions.py`, `test_login_flow.py`, `test_home.py`,
`test_auth_config.py`, `test_safe_next.py`, `test_migrations.py`, `test_startup.py`, plus the
mechanical updates to `test_auth_services.py`, `test_health.py` and `test_login_privacy.py` that
the replaced interfaces force. Every database-touching test runs on **both** engines (`[sqlite]`
and `[postgresql]`) through the existing parametrised `database_url` fixture. Four checks are
once-per-milestone **manual procedures** (quickstart V6–V9, see the plan's *Complexity
Tracking*), plus the rollout gate R1 and the local walkthroughs V1–V2. Those tasks are marked
**[MANUAL]**.

**Organization**: Tasks are grouped by user story so each can be implemented and validated
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- **[MANUAL]**: A human procedure or a platform-console action; not automatable at this milestone
- Include exact file paths in descriptions

## Path Conventions

Single server-rendered web application, repository root: `app/` (application), `migrations/`
(Alembic), `tests/` (suite), `scripts/` (release helpers), `.github/workflows/` (pipeline), and
`render.yaml` / `README.md` at the root. See the plan's *Project Structure* for every new and
changed file.

**Running the PostgreSQL half locally** (needed by every "run the suite" task below):

```bash
docker run -d --name sc-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:17
export TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres
```

**Facts about the current code that shape these tasks** (verified while generating them):

1. `reconcile_admins`, `get_session_user` and `User.role` are used outside the files the plan
   lists: `tests/integration/test_auth_services.py` (both functions, `User(role=…)`),
   `tests/integration/test_health.py` (monkeypatches `auth.get_session_user`) and
   `tests/integration/test_login_privacy.py` (`User(role=Role.ADMIN, …)`). They must be updated in
   the same phase that replaces the interfaces (T007), or the Foundational checkpoint is red.
2. `create_session(session, user, current_role, now=None)` gains a **required** `current_role`
   argument ([contracts/auth-services.md](./contracts/auth-services.md#appservicessessionspy)).
   Every existing caller (`app/routers/auth.py`, `tests/conftest.py`,
   `tests/integration/test_sessions.py::use_session_created_at`,
   `tests/integration/test_auth_services.py`, `tests/integration/test_admin_reconcile.py`) must
   pass it.
3. `app.routes` holds included routers as `fastapi.routing._IncludedRouter` wrappers;
   `tests/integration/test_routes.py` already flattens them with `original_router.routes` and
   `include_context.prefix`. Reuse that helper for every new sweep.
4. Routes added to the running app with `app.get(...)` / `app.add_api_route(...)` inherit the
   application-wide `dependencies=[Depends(resolve_access)]`, because `FastAPI.__init__` hands
   them to `app.router`. The undeclared probe route of US5 relies on that.
5. Constraint names come from `SQLModel.metadata.naming_convention` in `app/core/db.py`:
   `CheckConstraint(..., name="role")` on table `user_roles` becomes `ck_user_roles_role`, and the
   primary key becomes `pk_user_roles`. `migrations/env.py` already uses `render_as_batch` on
   SQLite.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the milestone 4 baseline. There is **no** new runtime or dev dependency and
no new infrastructure ([plan](./plan.md#technical-context)).

- [X] T001 Confirm the milestone 4 baseline is green from the repository root with `TEST_POSTGRES_URL` set: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, and `uv run alembic heads` printing the single head `a35580dee830`. All must pass before any change is made. `pyproject.toml` and `uv.lock` must stay unchanged for the whole milestone

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Everything every story rides on: the extended `Role` enum, the `user_roles` table and
`sessions.current_role`, the one additive migration, parsing of the three role lists,
`reconcile_users` (replacing `reconcile_admins`), session identity with a current role (replacing
`get_session_user`), the resolver publishing `request.state.roles` / `.current_role`, the template
context, and the test cast with `client_as`.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. At the end of this
phase **no page is restricted by role yet**: every milestone 4 test still passes, single-role
administrators behave exactly as before, and the five cast addresses exist with their roles.

### Tests (write first, confirm they FAIL)

- [X] T002 [P] Extend `tests/integration/test_migrations.py` with the data-preserving revision tests of [data-model.md §7](./data-model.md#7-schema-revision-introduced-by-this-milestone), on both engines, using lightweight `sa.table`/`sa.column` SQL (never the ORM models, which describe head): **upgrade** — migrate an empty database to `a35580dee830`, insert an active user `role='admin'`, an inactive user `role='admin'`, and a session for the active one; upgrade to head; assert `user_roles` holds exactly one row `(active_id, 'admin')` and none for the inactive user, the session survives with `current_role IS NULL`, and a new `users` row with `role = NULL` is accepted. **downgrade** — at head, create an admin-only user, an admin+student user, a teacher-only user with a session and a login code, and an inactive user with no roles and `role = NULL`; downgrade to `a35580dee830`; assert both admin holders have `role='admin'` and stay active, the teacher-only user has `role='teacher'`, `is_active = false`, no sessions and no codes, the inactive user has `role='admin'`, `user_roles` and `sessions.current_role` no longer exist, and inserting a `users` row with `role = NULL` now fails. The existing drift (`test_models_match_the_migrated_schema`), stairway, single-head and concurrent-upgrade tests must cover the new revision unchanged
- [X] T003 [P] Rename `tests/integration/test_admin_reconcile.py` to `tests/integration/test_user_reconcile.py` with `git mv`, then rewrite it against `reconcile_users(session, role_lists, now=None)` and `ReconcileResult(created, reactivated, deactivated, roles_added, roles_removed, unchanged)`: one test per row **S1–S11** of the [behaviour matrix](./contracts/auth-services.md#appservicesuserspy), asserting the end state through `get_roles` and the exact counts. S2 asserts no `users.updated_at` changed and no session was deleted (SC-007); S3 asserts **both** sessions of `a` are deleted and its login codes kept; S4 asserts the session is kept; S5 asserts the row still exists, inactive, with no roles, sessions or codes (FR-008); S7 feeds addresses already normalised by `resolve_auth_settings` (`" X@Ex.com "` on `ADMIN_EMAILS` and `x@ex.com` on `STUDENT_EMAILS`) and expects one user with two roles; S9 adapts the existing competing-session test to `app.main.reconcile_users_with_retry(engine, role_lists)`; S10 adapts the existing concurrent-start test (PostgreSQL); S11 empties all three lists. Keep the startup-order test, now expecting `["ensure_at_head", "reconcile_users_with_retry", "record_boot"]`, and the log test, now expecting the line `Users reconciled: <c> created, <r> reactivated, <d> deactivated, <ra> roles added, <rr> roles removed, <u> unchanged` and no `@` in any record
- [X] T004 [P] Update `tests/integration/test_auth_services.py` to the new interfaces ([contracts/auth-services.md](./contracts/auth-services.md)): its user helper creates `User(email=…, is_active=…)` (no `role=`) plus one `UserRole` row per role given; replace `reconcile_admins(session, [])` with `reconcile_users(session, {})`; pass `current_role` to every `create_session` call; replace `get_session_user` with `get_session_identity` (the expiry and deactivation assertions stay). Add: `start_session` returns `(token, Role.TEACHER)` for a teacher-only user and `(token, None)` for a two-role and a three-role user, and the stored row matches; `get_roles` returns roles in the fixed order administrator, teacher, student, and `()` for a user without rows; `set_current_role` changes only the row of the given token (a second session of the same user keeps its value)
- [X] T005 [P] Extend `tests/integration/test_sessions.py`: pass `Role.ADMIN` to `create_session` in `use_session_created_at`; add service-level tests for rows **G1–G6** of the [resolution table](./contracts/auth-services.md#appservicessessionspy) (G3 asserts the row now stores the single role; G6 covers both a role not held, e.g. `'student'` for `admin@example.com`, and an unknown string `'superuser'`, and asserts the session row is deleted); and request-level tests: a **pre-milestone session** of `admin@example.com` (`current_role = NULL`) gets `GET /` → 200 with no sign-in, and afterwards its row stores `'admin'` (SC-010, spec edge case); a session whose `current_role` is not held gets `GET /` → 303 to `/login?next=%2F` and its row is gone (FR-017)
- [X] T006 [P] Extend `tests/unit/test_auth_config.py` with the parsing of the two new lists, calling `resolve_auth_settings(environ)` with an explicit dict: `TEACHER_EMAILS=" B@x.org, a@x.org ,A@X.ORG,"` → `teacher_emails == ("a@x.org", "b@x.org")`, the same for `STUDENT_EMAILS`; unset and empty strings give `()`; with no variables at all locally both are `()` and the start is allowed (FR-037). (The rules C9, C10, W3, W4 and the no-echo checks are added in US2, T037)
- [X] T007 [P] Make the remaining milestone 4 tests compile against the replaced interfaces without changing what they assert: in `tests/integration/test_health.py` monkeypatch `auth.get_session_identity` instead of `auth.get_session_user`; in `tests/integration/test_login_privacy.py` create the inactive user as `User(email=INACTIVE, is_active=False)` (no `role=`, and no `UserRole` row, per the invariant "active ⇔ at least one role")

### Models and migration

- [X] T008 [P] Extend `app/models/user.py`: `Role(StrEnum)` gains `TEACHER = "teacher"` and `STUDENT = "student"` after `ADMIN = "admin"` (definition order **is** the fixed order administrator, teacher, student); add a `label` property returning `"Administrator"`, `"Teacher"`, `"Student"`; add module-level `ALL_ROLES = frozenset(Role)`. Rename the `role` attribute to `legacy_role: str | None` mapped to the **same** column, `Column("role", String(20), nullable=True)`, documented as "unused from milestone 5 on: never read, never written, `NULL` on new rows; dropped by milestone 6's first migration" ([data-model §2](./data-model.md#2-user--table-users-changed)). Rewrite the module and `Role` docstrings (roles come from three lists via `reconcile_users`; invariant active ⇔ at least one role)
- [X] T009 [P] Create `app/models/user_role.py` with `UserRole(SQLModel, table=True)`, `__tablename__ = "user_roles"`: `user_id: int` = PK part 1 and FK → `users.id` (no separate index: the composite PK leads with it); `role: str` = PK part 2, `Column(String(20), primary_key=True, nullable=False)`; `created_at: datetime` (`UTCDateTime`, NOT NULL); `__table_args__ = (CheckConstraint("role IN ('admin', 'teacher', 'student')", name="role"),)` so the names come out as `pk_user_roles`, `fk_user_roles_user_id_users`, `ck_user_roles_role` ([data-model §3](./data-model.md#3-userrole--table-user_roles-new-appmodelsuser_rolepy)). Docstring: rows are written only by `reconcile_users` (FR-003, FR-009)
- [X] T010 [P] Add `current_role: str | None` to `app/models/user_session.py` as `Column(String(20), nullable=True)` with **no** CHECK constraint, documented as "the role this browser is using; `NULL` = signed in, no role chosen yet; validated against the person's roles on every request" ([data-model §4](./data-model.md#4-usersession--table-sessions-changed))
- [X] T011 Export `UserRole` and `ALL_ROLES` from `app/models/__init__.py` (add to imports and `__all__`) so `SQLModel.metadata` is complete for Alembic and the drift test (depends on T008–T010)
- [X] T012 Generate and hand-finish the revision with `uv run alembic revision -m "add user roles"` → `migrations/versions/YYYY_MM_DD_<rev>_add_user_roles.py`, `down_revision = "a35580dee830"`, plain SQLAlchemy only (no app model imports, no engine-specific SQL). **Upgrade**, in order: (1) `op.create_table("user_roles", …)` with the composite PK, FK and CHECK named via `op.f(...)` exactly as the models produce them; (2) `INSERT INTO user_roles (user_id, role, created_at) SELECT id, 'admin', :now FROM users WHERE role = 'admin' AND is_active` with `now` = the migration's UTC time; (3) `op.add_column("sessions", sa.Column("current_role", sa.String(20), nullable=True))`; (4) `with op.batch_alter_table("users") as batch: batch.alter_column("role", existing_type=sa.String(20), nullable=True)`. **Downgrade**, in order: (1) `users.role = 'admin'` for every user with an `admin` row; (2) for every user without an `admin` row: `users.role` = their first remaining role in the order teacher, student, or `'admin'` if none, `is_active = false`, and delete their `sessions` and `login_codes`; (3) drop `sessions.current_role`, drop `user_roles`, make `users.role` NOT NULL again (batch mode). Module docstring explains expand-now/contract-later ([research D2](./research.md#d2--migration-expand-now-contract-later-the-old-usersrole-column-stays-nullable)). Run T002 and the existing migration tests until green (depends on T011)

### Settings

- [X] T013 [P] Extend `app/core/config.py`: `AuthSettings` gains `teacher_emails: tuple[str, ...]` and `student_emails: tuple[str, ...]`; replace the inline `ADMIN_EMAILS` loop in `resolve_auth_settings` with **one** helper (e.g. `_parse_email_list(name, raw, problems) -> tuple[str, ...]`) used for all three lists: empty string = unset, entries trimmed and lowercased, empty entries ignored, duplicates collapsed, result sorted, and each malformed entry appending `"<NAME> entry <n> is not a valid email address."` (1-based over non-empty entries, never the value) to the single `AuthConfigError`, in every environment, in the order C1…C10 ([contracts/configuration.md](./contracts/configuration.md#rules-changes)). Both new lists are optional everywhere (FR-036, FR-037); the Render rule "`ADMIN_EMAILS` non-empty" is unchanged. `__repr__` shows `<n addresses>` for all three lists. Update the docstring's rule reference to C1–C10

### Services

- [X] T014 Rewrite `app/services/users.py` per [research D8](./research.md#d8--reconciliation-generalised-to-three-lists) and [contracts/auth-services.md](./contracts/auth-services.md#appservicesuserspy): `ReconcileResult` with the six counts; **remove** `reconcile_admins`; add `reconcile_users(session, role_lists: Mapping[Role, Sequence[str]], now=None)` running in one transaction and committing once: build `desired[email] = {roles}` (a role missing from the mapping = empty list); create listed users (`is_active=True`, `legacy_role` left `None`), reactivate inactive ones, deactivate every active user who is not listed; load all `user_roles` rows, insert missing ones (`created_at=now`) and delete extra ones per user (unlisted users' desired set is empty); delete every session of every user who **lost any role**; delete every session and login code of every inactive user (finishes partial runs); set `updated_at=now` only for users whose active flag or role set changed; count `unchanged` as users with no change of any kind. Add `get_roles(session, user_id) -> tuple[Role, ...]` in the fixed order. Keep `get_active_user_by_email` unchanged. No log line here. Module docstring updated (depends on T011)
- [X] T015 [P] Rewrite `app/services/sessions.py` per [research D9](./research.md#d9--session-resolution-one-query-the-role-check-and-the-pre-milestone-upgrade): frozen dataclass `SessionIdentity(user: User, roles: tuple[Role, ...], current_role: Role | None)`; `create_session(session, user, current_role, now=None)` storing `current_role` (value or `None`); `start_session(session, user, now=None) -> tuple[str, Role | None]` (the single role held, or `None` when several are held; reads roles with one query on `user_roles`); `get_session_identity(session, token, now=None)` replacing `get_session_user`: **one** query joining `sessions` ⋈ `users` ⋈ `user_roles` on the token hash, unexpired, active user (inner join, so no roles → `None`), then rows G1–G6: G6 (current role set and not held, or not a valid `Role` value) **deletes this session row** and returns `None`; G3 (`NULL` and exactly one role) **writes** that role and returns it; otherwise return as is with roles sorted in the fixed order; `set_current_role(session, token, role)` updating only that token's row and committing. `delete_session` unchanged. No log line contains a token or hash (depends on T011)
- [X] T016 Update `app/main.py`: replace `reconcile_admins_with_retry` with `reconcile_users_with_retry(engine, role_lists)` (same one-retry-on-`IntegrityError` shape); in `lifespan`, build `{Role.ADMIN: settings.admin_emails, Role.TEACHER: settings.teacher_emails, Role.STUDENT: settings.student_emails}` and log exactly `Users reconciled: %d created, %d reactivated, %d deactivated, %d roles added, %d roles removed, %d unchanged` (counts only, FR-007); update the module docstring's startup order to `… → ensure_at_head → reconcile_users (one retry) → purge_expired → record_boot` (FR-038) (depends on T013, T014)
- [X] T017 Update `app/core/auth.py` to resolve, **not yet enforce**, roles: `_user_from_cookie` becomes `_identity_from_cookie` calling `get_session_identity`; `resolve_access` sets `request.state.user`, `request.state.roles` (`()` when anonymous) and `request.state.current_role` (`None` when anonymous), and otherwise keeps milestone 4's behaviour (healthz skip, `PUBLIC_ROUTES`, `LoginRequired`). Add `get_current_role(request) -> Role | None` and `CurrentRole = Annotated[Role | None, Depends(get_current_role)]` beside `CurrentUser` (depends on T015)
- [X] T018 [P] Extend the context processor in `app/core/templates.py` to expose `current_user`, `current_role` and `user_roles` (from `request.state.user`, `.current_role`, `.roles`, defaulting to `None`, `None`, `()` when the resolver did not run, e.g. a 404); update the module docstring
- [X] T019 Update `POST /login/code` in `app/routers/auth.py` to call `start_session(session, user)` instead of `create_session(session, user)` and use the returned token; the redirect stays `next` for now (the multi-role redirect is added in US3, T052) (depends on T015)

### Test fixtures

- [X] T020 Update `tests/conftest.py` per [research D12](./research.md#d12--tests-a-fixed-cast-a-role-aware-shortcut-and-sweeps-over-the-route-table): add `TEACHER_EMAILS` and `STUDENT_EMAILS` to `AUTH_VARIABLES`; define the cast constants `ADMIN_EMAIL = "admin@example.com"`, `TEACHER_EMAIL = "teacher@example.com"`, `STUDENT_EMAIL = "student@example.com"`, `ADMIN_STUDENT_EMAIL = "admin.student@example.com"`, `TEACHER_STUDENT_EMAIL = "teacher.student@example.com"`; the `client` fixture sets `ADMIN_EMAILS` = admin + admin.student, `TEACHER_EMAILS` = teacher + teacher.student, `STUDENT_EMAILS` = student + admin.student + teacher.student. Add `AUTO = object()` and change `sign_in_directly(test_client, email, current_role=AUTO)`: `AUTO` → `start_session`, an explicit `Role` or `None` → `create_session(..., current_role)`; docstring keeps "test-only, no login bypass" (FR-041). Add the factory fixture `client_as(client)` returning `client_as(email, current_role=AUTO) -> TestClient` (a non-context-managed `TestClient(app)` per call, all closed at teardown); re-implement `admin_client` via `client_as(ADMIN_EMAIL)` with unchanged meaning. Update the module docstring. Fix any existing assertion that assumed exactly one user exists after start (depends on T015, T016)
- [X] T021 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` with `TEST_POSTGRES_URL` set. T002–T007 and every milestone 4 test must pass on both engines. **Checkpoint**: roles exist and are resolved; nothing is restricted by role yet

---

## Phase 3: User Story 1 - Each role opens exactly its own pages (Priority: P1) 🎯 MVP

**Goal**: The access table of the spec holds: every route is judged by the session's **current**
role, the four placeholder areas exist, the home page lists exactly the allowed areas, the header
shows `Student Competitions · <Role>`, and a forbidden page shows the friendly 403 "Access
denied".

**Independent Test**: With the cast, open every page of the access table as `admin@`, `teacher@`
and `student@` (via `client_as`): each ✅ answers 200, each ❌ answers 403 naming the current role,
and the home page lists exactly the allowed links. An anonymous request for any area redirects to
login.

### Tests for User Story 1 (write first, confirm they FAIL)

- [X] T022 [P] [US1] Create `tests/integration/test_access_control.py` with a literal copy of the spec's access table (`ACCESS_TABLE = {"/": {ADMIN, TEACHER, STUDENT}, "/admin": {ADMIN}, "/teacher": {TEACHER}, "/student": {STUDENT}, "/staff": {ADMIN, TEACHER}}`), **independent** of `AREAS`: (a) the 3 × 5 = 15 parametrised cases with single-role clients from `client_as` — allowed → 200 (areas show their `<h1>` title and the sentence "The features of this area will arrive in a later milestone."), denied → 403 (SC-001, US1-2, US1-3); (b) the 403 page shows the heading `Access denied`, the message `Your current role, <Label>, cannot open this page.`, a link to `/`, the header with the email and **Log out**, and does **not** contain the denied area's title (FR-025); (c) home links per role are exactly Administrator area + Staff area / Teacher area + Staff area / Student area, read from `section#areas` hrefs, in that order (FR-027, US1-4); (d) an anonymous `GET` of each area → 303 to `/login?next=%2F<area>` (US1-6, FR-023); (e) a signed-in `GET /does-not-exist` → 404, not 403 (spec edge case); (f) a denial writes the log line `Access denied: role=<value> route=<path template>` and no record contains `@` (SC-008, `caplog`)
- [X] T023 [P] [US1] Extend `tests/integration/test_home.py`: for `admin_client` the header contains an element with class `site-role` whose text is `Administrator`, next to `Student Competitions`, and still shows the email and **Log out** (FR-031, US1-5); the same for teacher and student via `client_as`; all existing milestone 4 assertions keep passing unchanged through `admin_client`
- [X] T024 [P] [US1] Extend `tests/integration/test_login_flow.py`: a **single-role** person (`teacher@example.com`) signs in through the full flow with the `memory` outbox starting from `GET /teacher`; `POST /login/code` answers 303 to `/teacher` exactly as in milestone 4 (no role-choice step, SC-003, US1-1, FR-012), the stored session has `current_role = 'teacher'`, and the landed page shows `· Teacher`

### Implementation for User Story 1

- [X] T025 [US1] Implement the access declaration and the decision order in `app/core/auth.py` ([research D4, D5](./research.md#d5--one-decision-order-for-every-request), [contracts/http-routes.md](./contracts/http-routes.md#access-rule-applies-to-every-route)): `allow_roles(*roles: Role)` records a non-empty `frozenset[Role]` as `endpoint.allowed_roles` and returns the function unchanged (works above or below the route decorator), raising `ValueError` at import time when called with no roles; `declared_roles(endpoint) -> frozenset[Role] | None`; `ROLE_CHOICE_ROUTES = frozenset({("GET", "/role"), ("POST", "/role")})`; exceptions `RoleChoiceRequired(location)` and `AccessDenied(current_role: Role)`. `resolve_access` applies, first match wins: (1) healthz skip; (3) anonymous + `PUBLIC_ROUTES` → served; (4) anonymous → `LoginRequired` (unchanged); (5) signed in + `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES` → served; (6) signed in, no current role → `RoleChoiceRequired("/role?next=<quote(path?query, safe='')>")` for `GET`/`HEAD`, `"/role"` otherwise; (7) current role ∈ `declared_roles(request.scope["route"].endpoint)` → served; (8) anything else, **including no marker** → log `Access denied: role=<value> route=<path template>` (no email, no user id) and raise `AccessDenied` (FR-022–FR-024). Leave a slot for rule 2 (cross-site, added in US4). Rewrite the module docstring around "deny by default: every route declares its roles"
- [X] T026 [P] [US1] Create `app/routers/areas.py` per [contracts/auth-services.md](./contracts/auth-services.md#approutersareaspy): frozen dataclass `Area(path, title, roles: frozenset[Role])`; `ADMIN_AREA = Area("/admin", "Administrator area", {ADMIN})`, `TEACHER_AREA = Area("/teacher", "Teacher area", {TEACHER})`, `STUDENT_AREA = Area("/student", "Student area", {STUDENT})`, `STAFF_AREA = Area("/staff", "Staff area", {ADMIN, TEACHER})`; `AREAS` in that order; `areas_for(role) -> list[Area]`; one thin handler per area decorated `@router.get(AREA.path, response_class=HTMLResponse)` + `@allow_roles(*AREA.roles)`, rendering `pages/area.html` with the area title (FR-028–FR-030)
- [X] T027 [P] [US1] Create `app/templates/pages/area.html` extending `layouts/base.html`: `<title>` = area title + app name, `<h1>{{ area.title }}</h1>` and one paragraph "The features of this area will arrive in a later milestone." — nothing else, no personal data (FR-030)
- [X] T028 [P] [US1] Change `app/templates/pages/error.html` to show an optional `heading` (e.g. `Access denied`) in the `<h1>` and `<title>` instead of the bare status code when one is given; the 404 and other errors render exactly as before when `heading` is absent
- [X] T029 [US1] Update `app/routers/pages.py`: decorate `home` with `@allow_roles(*ALL_ROLES)` and add `areas = areas_for(current_role)` to the context (via `CurrentRole`); the rest of the handler is unchanged (FR-027) (depends on T025, T026)
- [X] T030 [P] [US1] Add the "Your areas" section to `app/templates/pages/home.html` after the introduction, exactly as in [contracts/http-routes.md](./contracts/http-routes.md#get---the-home-page): `<section id="areas" aria-labelledby="areas-heading">`, `<h2 id="areas-heading">Your areas</h2>`, one `<li><a href="{{ area.path }}">{{ area.title }}</a></li>` per area; the rest of the page is unchanged
- [X] T031 [P] [US1] Update `app/templates/layouts/base.html`: when `current_role` is set, render `<strong>{{ app_name }}</strong> <span class="site-role">· {{ current_role.label }}</span>` on the left; anonymous visitors and sessions without a current role keep the bare name (FR-031, FR-032); the right side (email, **Log out**) is unchanged
- [X] T032 [P] [US1] Add a small `.site-role` override to `app/static/css/app.css` (muted colour, normal weight) so the role reads as part of the title line
- [X] T033 [US1] Update `app/main.py`: `include_router(areas.router)`; register handlers for `RoleChoiceRequired` (303 to `exc.location`) and `AccessDenied` (render `pages/error.html` with status 403, `heading="Access denied"`, `detail=f"Your current role, {exc.current_role.label}, cannot open this page."`); the full header (with `current_user`/`current_role`) is rendered because the resolver already ran (FR-025, FR-026: no automatic switch) (depends on T025, T026)
- [X] T034 [P] [US1] Extend step 8 of the `image` job in `.github/workflows/checks.yml` per [contracts/pipeline.md](./contracts/pipeline.md#checksyml--image): `check_home` also asserts `class="site-role"` and `Administrator` in the header, `href="/admin"` and `href="/staff"` present and `href="/student"`, `href="/teacher"` absent; after the first `check_home 1`, `curl -b jar /admin` → 200 containing `Administrator area` and `curl -b jar /student` → 403 containing `Access denied`. Add one sentence to the step comment naming the role checks and linking the contract
- [X] T035 [P] [US1] Add the fourth assertion to `scripts/verify_private.sh` inside the existing retry loop: anonymous `GET <base>/admin` → status 303 with `Location` ending in `/login?next=%2Fadmin`; name it in the header comment; output and failure format unchanged ([contracts/pipeline.md](./contracts/pipeline.md#scriptsverify_privatesh-changed))
- [X] T036 [US1] Run lint, format check and the full suite on both engines; T022–T024 now pass with everything earlier. **Checkpoint**: the access table holds for single-role people; this is the MVP

---

## Phase 4: User Story 2 - Operations assigns roles through deployment configuration (Priority: P2)

**Goal**: The three lists are validated at start, reconciled on every start with exact
end-to-end effects (role removal logs out everywhere, removal from every list blocks sign-in,
added roles keep sessions), logged as counts only, and declared on Render.

**Independent Test**: Start the app with the cast, restart it with changed lists against the same
database, and observe each person's roles, sessions and ability to obtain a code; start it with a
malformed `TEACHER_EMAILS` and see the start refused without the value.

### Tests for User Story 2 (write first, confirm they FAIL)

- [X] T037 [P] [US2] Extend `tests/unit/test_auth_config.py` with the rules of [contracts/configuration.md](./contracts/configuration.md#rules-changes): **C9** `TEACHER_EMAILS="ok@x.org,bad,also@@bad"` → `TEACHER_EMAILS entry 2 is not a valid email address.` and `… entry 3 …`, locally **and** on Render; **C10** the same for `STUDENT_EMAILS`; all violations of all lists in **one** `AuthConfigError`, in the order C1…C10; both new lists optional on Render (a valid Render environ without them starts); **W3** reworded: with `ADMIN_EMAILS` empty and another list set, locally, the warning is `ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator.`; **W4**: with all three lists empty, locally, the warning is `No role lists are set; nobody will be able to sign in.` and W3 is **not** emitted; neither warning on Render. **No-echo**: plant `teacher-planted@@bad` and `student-planted@@bad` and assert neither appears in `str(exc)` or any `caplog` record; `repr(settings)` shows `<n addresses>` for all three lists and no address. Update the existing `W3` constant
- [X] T038 [P] [US2] Extend `tests/integration/test_startup.py`: with `TEACHER_EMAILS="not-an-address"` (and separately `STUDENT_EMAILS`) the start is refused **locally** before any database access, the error names the list and position but not the value, and the boot is **not** counted (FR-035); a local start with neither new variable set succeeds (FR-037)
- [X] T039 [P] [US2] Add restart-based end-to-end tests to `tests/integration/test_user_reconcile.py` (a helper that starts `TestClient(app)` again against the **same** `database_url` with changed `ADMIN_EMAILS`/`TEACHER_EMAILS`/`STUDENT_EMAILS`): US2-1/US2-2 after the first start each cast address is one active user holding exactly its roles; US2-3 a restart with the same lists changes nothing (no `updated_at` change, existing sessions still answer 200); US2-4 `admin.student@` signed in on **two** clients, restart without it on `STUDENT_EMAILS` → both clients get 303 to `/login`, and signing in again through the outbox gives a session with `current_role='admin'` and roles `(ADMIN,)`; US2-5 `student@` signed in, restart without it on any list → its session is gone, `POST /login` still renders step 2 but the outbox stays empty; US2-6 `teacher@` signed in, restart adding it to `STUDENT_EMAILS` → its session still answers 200 and `request`-level roles now include student (assert via `get_roles` and the session row unchanged); US2-7 re-adding a removed address lets it sign in again; US2-8 the startup log line has the six counts and no `@` (SC-006, SC-008)
- [X] T040 [P] [US2] Extend `tests/integration/test_login_flow.py`: a person removed from every list (restart with `STUDENT_EMAILS` without `student@`) requests a code and sees the same step-2 response as anyone else, the outbox stays empty, and any old code no longer verifies (FR-010, US2-5)

### Implementation for User Story 2

- [X] T041 [US2] Update the local warnings in `app/core/config.py`: W3 reworded to `ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator.` (only when another list is non-empty); new W4 `No role lists are set; nobody will be able to sign in.` when all three are empty (replacing W3 in that case); both only when not on Render, logged at WARNING on `uvicorn.error`
- [X] T042 [P] [US2] Add `TEACHER_EMAILS` and `STUDENT_EMAILS` (`sync: false`) under `envVars` in `render.yaml`, after `ADMIN_EMAILS`, with exactly the comment in [contracts/configuration.md](./contracts/configuration.md#render-renderyaml-added-under-envvars); update the header comment's count of declared secrets from five to seven (FR-034). No value is ever written
- [X] T043 [US2] Run lint, format check and the full suite on both engines. **Checkpoint**: operations controls who holds which role, and removals take effect at the restart

---

## Phase 5: User Story 3 - A person with several roles chooses one after signing in (Priority: P3)

**Goal**: A multi-role person is sent to `GET /role` after the code check, sees only their roles,
and choosing one lands on the originally requested page. Until they choose, every other page
redirects to the role choice.

**Independent Test**: Sign `teacher.student@` in through the outbox starting from `/teacher`: the
role choice offers exactly Teacher and Student, and choosing Teacher lands on `/teacher` with
`· Teacher`. A single-role person never sees the role choice.

### Tests for User Story 3 (write first, confirm they FAIL)

- [X] T044 [P] [US3] Create `tests/integration/test_role_choice.py` against [contracts/http-routes.md](./contracts/http-routes.md#get-role--the-role-choice): (a) full flow via the outbox for `teacher.student@` from `GET /teacher`: `POST /login/code` → 303 `/role?next=%2Fteacher` (FR-013, SC-004); `GET /role?next=%2Fteacher` → 200 with `<h1>Choose a role</h1>`, buttons `value="teacher"` then `value="student"` only, a hidden `next` = `/teacher`, the email and **Log out** in the header and **no** `site-role` element (US3-1, FR-032); `POST /role role=teacher next=/teacher` → 303 `/teacher`, which answers 200 with `· Teacher` (US3-2); (b) before choosing, `GET /` → 303 `/role?next=%2F` and `GET /staff?x=1` → 303 `/role?next=%2Fstaff%3Fx%3D1`, a non-GET → 303 `/role` (US3-3, FR-014); (c) `POST /logout` from the role choice logs out (US3-4); (d) tampered `role=admin`, missing `role`, and `role=superuser` → 400 role choice page with `Choose one of your roles.` and `current_role` still `NULL` in the database (US3-5, FR-020); (e) `GET /role?role=student` changes nothing (FR-020); (f) single-role `teacher@` opening `GET /role` → 303 `/` (US3-6, FR-016); (g) `next` of `/role`, `/login`, `/logout`, `//evil.example` and `https://evil.example` all land on `/` (FR-015); (h) `next=/admin` with role student → lands on `/admin` and gets 403, role not switched (edge case); (i) after choosing, `GET /role` (no `next`) → 200 again, and choosing there lands on `/` (edge case); (j) a single-role full flow never visits `/role` (SC-003)
- [X] T045 [P] [US3] Extend `tests/unit/test_safe_next.py`: `/role`, `/role?next=%2Fadmin` and `/role/` handling per the existing `AUTH_PATHS` rule → `/`
- [X] T046 [P] [US3] Update `tests/integration/test_routes.py`: rename `test_the_write_routes_are_exactly_login_and_logout` to cover exactly `POST /login`, `POST /login/code`, `POST /logout`, `POST /role`; add `ROLE_CHOICE_ROUTES` is exactly `{("GET", "/role"), ("POST", "/role")}` and every entry exists in the flattened route table
- [X] T047 [P] [US3] Extend `tests/integration/test_sessions.py`: a **pre-milestone** session (`current_role = NULL`) of the multi-role `admin.student@` is **not** ended: `GET /` → 303 `/role?next=%2F`, and the row still exists with `NULL` (spec edge case "session from before this milestone")

### Implementation for User Story 3

- [X] T048 [P] [US3] Add `"/role"` to `AUTH_PATHS` in `app/core/security.py` so `safe_next_path` replaces it with `/` (FR-015); update the docstring
- [X] T049 [P] [US3] Create `app/templates/pages/role_choice.html` extending `layouts/base.html`: `<h1>Choose a role</h1>`, the sentence "You have more than one role. Choose the one to use now. You can switch at any time from the header.", an optional `message` (for the 400), and one `<form method="post" action="/role">` with the hidden `next` field **only** when a `next` was given and one `<button type="submit" name="role" value="{{ role.value }}">{{ role.label }}</button>` per role held, in the fixed order
- [X] T050 [US3] Create `app/routers/roles.py` with thin handlers ([research D6](./research.md#d6--choosing-and-switching-one-form-route-post-role)): `GET /role` (`next` query, optional) → 303 `/` when exactly one role is held (FR-016), otherwise the role choice with `next = safe_next_path(next)` if given; `POST /role` (form `role`, optional `next`) → if `role` is a valid `Role` held by `request.state.roles`, call `set_current_role(session, token, role)` for **this** session's token (read from the signed cookie) and redirect 303 to `safe_next_path(next)` (`/` when absent); otherwise re-render the role choice with status 400 and `Choose one of your roles.` and change nothing. Database errors render a friendly 503 and are logged by exception type only. No log line contains an address (depends on T049)
- [X] T051 [US3] Update `app/main.py`: `include_router(roles.router)` (depends on T050)
- [X] T052 [US3] Update `POST /login/code` in `app/routers/auth.py`: when `start_session` returns `None` as the current role, redirect 303 to `/role?next=<quote(next, safe='')>`; otherwise redirect to `next` as before (FR-012, FR-013). Every failure response is unchanged (FR-042)
- [X] T053 [US3] Run lint, format check and the full suite on both engines. **Checkpoint**: multi-role people can sign in and choose a role

---

## Phase 6: User Story 4 - A person with several roles switches role from the header (Priority: P4)

**Goal**: Multi-role people switch role in one click from the header, per browser, landing on
`/`; a cross-site submission can never change the role (and, application-wide, no cross-site
unsafe request is processed).

**Independent Test**: As `admin.student@` using Administrator, switch to Student from the header:
`/admin` now answers 403 and home lists only Student area; switch back and `/admin` opens. A
cross-site `POST /role` answers 403 and changes nothing.

**Depends on**: US3 (`POST /role`).

### Tests for User Story 4 (write first, confirm they FAIL)

- [X] T054 [P] [US4] Create `tests/integration/test_role_switch.py`: with `client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN)`: the header has `form.role-switch` posting to `/role` with the label "Switch to", exactly one button `value="student"` and **no** `next` field (US4-1, FR-018); `POST /role role=student` → 303 `/`, same cookie and same session row id, header `· Student`, home lists only Student area, `/admin` → 403 naming Student (US4-3, US4-4, SC-005); switching back → `/admin` 200; switching to the current role → 303 `/`, role unchanged (edge case); `role=teacher` (not held) → 400, role unchanged (US4-6); the 403 page also shows the switch form (FR-026); single-role `teacher@` has no `role-switch` form (US4-2); **two browsers** (`client_as` twice for the same person) — switching one leaves the other's role and its database row unchanged (US4-5, FR-011); a GET link `GET /role?role=student` changes nothing (FR-020)
- [X] T055 [P] [US4] Create `tests/unit/test_cross_site_rule.py`: one parametrised case per row of the [`is_cross_site` table](./contracts/auth-services.md#appcoresecuritypy) (safe methods never cross-site; `Sec-Fetch-Site` `same-origin`/`none` allowed, `same-site`/`cross-site`/unknown refused, and the header wins over a matching `Origin`; without it, `Origin` host[:port] equal to `Host` allowed, different host or `null` refused; neither header allowed), with `PUT`, `PATCH`, `DELETE` behaving as `POST`, and header names matched case-insensitively (Starlette `Headers`)
- [X] T056 [P] [US4] Create `tests/integration/test_cross_site.py`: signed in as `admin.student@` using Administrator, `POST /role role=student` with `Sec-Fetch-Site: cross-site` → 403 with "This request was refused because it did not come from this site." and `current_role` still `'admin'` in the database (FR-021, US4-6); the same with `Origin: https://evil.example` and no `Sec-Fetch-Site`; a cross-site `POST /logout` → 403 and the session still answers `GET /` 200; a cross-site `POST /login/code` → 403 (closes milestone 4's login-CSRF risk); the refusal happens **before** any database access (monkeypatch `auth.get_session_identity` to fail the test if called); `Sec-Fetch-Site: same-origin` and no headers at all are accepted; a cross-site `GET /` is unaffected

### Implementation for User Story 4

- [X] T057 [P] [US4] Add the pure function `is_cross_site(method: str, headers: Mapping[str, str]) -> bool` to `app/core/security.py` exactly per [research D7](./research.md#d7--cross-site-forgery-an-application-wide-fetch-metadata-and-origin-check): no I/O, standard library only (`urllib.parse` to compare `Origin`'s host[:port] with `Host`), with a docstring naming the Go `CrossOriginProtection` design and the header-less fallback recorded in Complexity Tracking
- [X] T058 [US4] Add rule 2 to `resolve_access` in `app/core/auth.py`: right after the healthz skip and **before** reading the cookie, `if is_cross_site(request.method, request.headers): raise CrossSiteRequest()`; define `CrossSiteRequest(Exception)` (depends on T057)
- [X] T059 [US4] Register the `CrossSiteRequest` handler in `app/main.py`: render `pages/error.html` with status 403, `heading="Request refused"`, `detail="This request was refused because it did not come from this site."` (depends on T058)
- [X] T060 [P] [US4] Add the switch form to `app/templates/layouts/base.html`, between the email and **Log out**, only when `current_role` is set and `user_roles | length > 1`: `<form method="post" action="/role" class="role-switch">`, a visible "Switch to" label, and one `<button type="submit" name="role" value="{{ role.value }}">{{ role.label }}</button>` per held role other than the current one, in the fixed order, with **no** `next` field (FR-018, FR-019, FR-033)
- [X] T061 [P] [US4] Add a small `.role-switch` override to `app/static/css/app.css` (inline form, compact buttons beside the email) so it fits the header at phone width
- [X] T062 [P] [US4] Extend step 8 of the `image` job in `.github/workflows/checks.yml` (after the US1 role checks): `curl -b jar -X POST -H 'Origin: https://evil.example' /logout` → 403, then `curl -b jar /` → 200, proving the session survived; the existing legitimate logout (no `Origin`) is still accepted ([contracts/pipeline.md](./contracts/pipeline.md#checksyml--image)) (after T034)
- [X] T063 [US4] Run lint, format check and the full suite on both engines. **Checkpoint**: switching works per browser and cross-site writes are refused application-wide

---

## Phase 7: User Story 5 - Every page declares who may open it; denied by default (Priority: P5)

**Goal**: The build fails, naming the route, when a route is neither public, role choice, nor
declared; every declared route admits exactly its roles; an undeclared route that reaches a
running app is denied to everyone.

**Independent Test**: The route sweep passes on the real app, and fails naming a deliberately
undeclared probe route, which signed-in people get 403 for.

**Depends on**: US1 (`allow_roles`, rule 8). The role-choice routes it allowlists exist after US3.

### Tests for User Story 5 (write first, confirm they FAIL where new)

- [X] T064 [US5] Extend `tests/integration/test_routes.py` per [research D12](./research.md#d12--tests-a-fixed-cast-a-role-aware-shortcut-and-sweeps-over-the-route-table): add a helper `undeclared_routes(app) -> list[str]` over the flattened route table returning `"<METHOD> <path>"` for every route that is not in `PUBLIC_ROUTES`, not in `ROLE_CHOICE_ROUTES`, and has no non-empty `declared_roles`; assert it is empty with a message naming each offender (US5-1, US5-3, SC-002); a fixture `undeclared_probe` that adds `GET /__undeclared_probe` to the running app via `app.add_api_route` and removes it from `app.router.routes` on teardown — with it, `undeclared_routes(app)` names exactly that route, and every single-role client gets 403 for it (US5-3, US5-4, FR-024); for **every** declared `GET` route, the single-role cast clients in `allowed_roles` get 200 and the others 403 (US5-2); `allow_roles()` with no roles raises `ValueError`; the marker is found whether `@allow_roles` is written above or below `@router.get`. The existing anonymous sweep stays unchanged

### Implementation for User Story 5

- [X] T065 [US5] Finish `app/core/auth.py` for declarers: `allow_roles` also rejects non-`Role` arguments with `TypeError`; the module docstring states the rule for every future route ("decorate with `@allow_roles(...)`, or add it to `PUBLIC_ROUTES` in a reviewed change; an undeclared route is denied at runtime and fails `test_routes.py`") and links research D4/D5
- [X] T066 [US5] Run lint, format check and the full suite on both engines; then, locally only, remove `@allow_roles` from the `/staff` handler, confirm `test_routes.py` fails naming `GET /staff` and that `/staff` answers 403 for an administrator, and restore it. **Checkpoint**: all five stories are complete

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, scope and privacy reviews, the full gate, and the manual
once-per-milestone checks.

- [X] T067 [P] Update `README.md` (FR-039, SC-009): document `TEACHER_EMAILS` and `STUDENT_EMAILS` (purpose, comma-separated format, local default "empty: nobody holds that role", production rule "optional, may be empty, every entry must be well-formed", temporary until milestone 7, removing an address logs that person out everywhere at the restart); the reworded and new warnings; "Signing in locally as each role" with the command and steps from [contracts/configuration.md](./contracts/configuration.md#local-sign-in-as-each-role-readme-fr-039-sc-009); the three roles, the access table, current role / role choice / switch; "Adding a page": `@allow_roles(...)` or the public allowlist, deny by default, the route sweep; and the cross-site rule for every unsafe request
- [X] T068 [P] Sweep for stale references with `grep -rn "reconcile_admins\|get_session_user\|Administrators reconciled\|\.role\b\|role=Role" app tests scripts .github`: only `legacy_role` and the migrations may mention the old column; fix every remaining docstring and comment (e.g. `app/models/user.py`, `app/services/users.py`, `app/main.py`, `app/core/templates.py`, `app/core/auth.py`)
- [X] T069 [P] Scope and secrets review of `git diff main...`: `pyproject.toml` and `uv.lock` unchanged (no new dependency); no HTMX attribute and no `<script>` added (FR-033); no route reads or writes `user_roles` except through `reconcile_users` at start and the per-request resolver (FR-009); no user, institution or profile management and nothing behind the placeholders (FR-042); no login or code rule, rate limit or session lifetime changed (FR-042); the only addresses in the diff are `@example.com` / `@example.org` test values and `ci-admin@example.com`
- [X] T070 [P] Log review: list every `logger.` call added or changed in this milestone (`app/main.py`, `app/core/auth.py`, `app/core/config.py`, `app/routers/roles.py`) and confirm none can contain an email address, a user id, a token, a hash or a setting's value (FR-007, SC-008)
- [X] T071 Run the full gate from the repository root with `TEST_POSTGRES_URL` set: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`; every test passes on both engines (quickstart V3)
- [X] T072 [MANUAL] Do quickstart **V1** (sign in locally as `admin@`, `teacher@`, `student@`, check the access table and the 403 page) and **V2** (multi-role choice, switch, two browsers) with the console backend, timing V1 against SC-009 (under 15 minutes from the README alone). **Result (2026-10-01)**: V1 passed in under 6 minutes from the README (SC-009); the one slip was a first start without the role lists, which the W4 warning made visible. V2 passed, including two browsers keeping different current roles (US4-5)
- [X] T073 [MANUAL] **Before merge**: rollout gate **R1** — if real teachers or students should sign in on release day, enter `TEACHER_EMAILS` and `STUDENT_EMAILS` in Render → `student-competitions` → *Environment*, checking every entry for typos; and start **V6** by signing in on production as an administrator in a browser that stays open through the release. **Result (2026-10-01)**: `TEACHER_EMAILS` and `STUDENT_EMAILS` entered in Render (values only there); the milestone 4 release restarted normally; an administrator browser signed in on production and kept open for V6
- [ ] T074 [MANUAL] Open the single milestone PR into `main`; confirm the `quality` job (V3) and the `image` job (V4) are green; in the PR description list the Complexity Tracking deviations (the question service's write functions still unguarded until milestone 6; `users.role` kept nullable as `legacy_role` until milestone 6; header-less CSRF fallback; any role removal ends all sessions; session resolution may write during a `GET`; manual checks V6–V9; milestone 4 residual risks carried, login-CSRF closed)
- [ ] T075 [MANUAL] **After merge**: confirm the release's *Verify access control* (V5) passes; complete **V6** (the pre-release administrator session still works with `· Administrator`), **V7** (real teacher and multi-role sign-in), **V8** (role removal on production logs out both browsers; removal from every list sends no code; the deploy log shows counts only) and **V9** (no `@` in any application log line of the release window); record the results in the PR and tick the [milestone acceptance checklist](./quickstart.md#milestone-acceptance-checklist)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup; **blocks every story**
- **US1 (Phase 3)**: after Foundational. It writes the whole decision order in `resolve_access`
  (rules 1, 3–8), including the role-choice gate that US3 fills with a page
- **US2 (Phase 4)**: after Foundational; independent of US1 (its tests use the outbox, the
  database and the resolver, not role pages)
- **US3 (Phase 5)**: after US1 (rule 6, `RoleChoiceRequired`, `ROLE_CHOICE_ROUTES` and the
  header live there)
- **US4 (Phase 6)**: after US3 (`POST /role` is the switch target)
- **US5 (Phase 7)**: after US1 (marker, rule 8); its sweep allowlists `ROLE_CHOICE_ROUTES`, whose
  routes exist after US3
- **Polish (Phase 8)**: after all stories. T073 must happen **before** merge, T075 after

### Story Order

```text
Setup → Foundational ─┬─► US1 ─┬─► US3 ─► US4
                      │        └─► US5 (after US3 for the full sweep)
                      └─► US2
                                        all ─► Polish
```

### Within Each Phase

- **Phase 2**: T002–T007 first; T008, T009, T010 together → T011 → T012; T013 anytime; T014 and
  T015 after T011; T016 after T013, T014; T017 and T019 after T015; T018 anytime; T020 after
  T015, T016; T021 last
- **Phase 3**: T022–T024 first; T025, T026, T027, T028 together; T029 after T025, T026; T030–T032
  anytime; T033 after T025, T026; T034, T035 anytime; T036 last
- **Phase 4**: T037–T040 first; T041 and T042 together; T043 last
- **Phase 5**: T044–T047 first; T048, T049 together; T050 after T049; T051 after T050; T052
  anytime; T053 last
- **Phase 6**: T054–T056 first; T057 → T058 → T059; T060, T061, T062 together; T063 last
- **Phase 7**: T064 → T065 → T066
- **Phase 8**: T067–T070 together; T071 after them; T072 anytime after T071; T073 before T074;
  T075 after merge

### Shared files (never edit in parallel)

- `app/core/auth.py`: T017 → T025 → T058 → T065
- `app/main.py`: T016 → T033 → T051 → T059
- `app/routers/auth.py`: T019 → T052
- `app/core/config.py`: T013 → T041
- `app/core/security.py`: T048 → T057
- `app/templates/layouts/base.html`: T031 → T060
- `app/static/css/app.css`: T032 → T061
- `.github/workflows/checks.yml`: T034 → T062
- `tests/integration/test_routes.py`: T046 → T064
- `tests/integration/test_sessions.py`: T005 → T047
- `tests/integration/test_login_flow.py`: T024 → T040
- `tests/integration/test_user_reconcile.py`: T003 → T039
- `tests/unit/test_auth_config.py`: T006 → T037

### Parallel Opportunities

- **Phase 2**: T002–T007 (six test files); T008–T010 (three models); T013, T015 and T018 alongside
  the model work once T011 is in
- **Phase 3**: T022–T024; then T026, T027, T028, T030, T031, T032, T034, T035 alongside T025
- **Phase 4**: T037–T040; T041 with T042
- **Phase 5**: T044–T047; T048 with T049
- **Phase 6**: T054–T056; T057 with T060, T061, T062
- **Across stories**: US2 can run in parallel with US1 → US3 → US4, respecting the shared-file
  order above (`test_login_flow.py`, `config.py`)
- **Phase 8**: T067–T070 together

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Six test files together:
Task: "Extend tests/integration/test_migrations.py — admin backfill on upgrade; downgrade deactivates non-admins"
Task: "git mv test_admin_reconcile.py → test_user_reconcile.py; S1–S11 against reconcile_users"
Task: "Update tests/integration/test_auth_services.py — start_session, get_roles, get_session_identity"
Task: "Extend tests/integration/test_sessions.py — G1–G6, pre-milestone upgrade, FR-017"
Task: "Extend tests/unit/test_auth_config.py — TEACHER_EMAILS / STUDENT_EMAILS parsing"
Task: "Update test_health.py and test_login_privacy.py to the replaced interfaces"

# Three models together:
Task: "Extend app/models/user.py — Role TEACHER/STUDENT, label, ALL_ROLES, legacy_role"
Task: "Create app/models/user_role.py — UserRole (composite PK, FK, CHECK)"
Task: "Add current_role to app/models/user_session.py"
```

## Parallel Example: User Story 1

```bash
Task: "Create tests/integration/test_access_control.py — 15-case matrix, home links, 403 page"
Task: "Extend tests/integration/test_home.py — site-role header"
Task: "Extend tests/integration/test_login_flow.py — single-role flow unchanged"

Task: "Create app/routers/areas.py — Area, AREAS, areas_for, four placeholders"
Task: "Create app/templates/pages/area.html"
Task: "Add optional heading to app/templates/pages/error.html"
Task: "Add Your areas section to app/templates/pages/home.html"
Task: "Show · <Role> in app/templates/layouts/base.html"
Task: "Role checks in the checks.yml image job"
Task: "Anonymous /admin check in scripts/verify_private.sh"
```

## Parallel Example: User Story 4

```bash
Task: "Create tests/integration/test_role_switch.py"
Task: "Create tests/unit/test_cross_site_rule.py"
Task: "Create tests/integration/test_cross_site.py"

Task: "Add is_cross_site to app/core/security.py"
Task: "Add the switch form to app/templates/layouts/base.html"
Task: "Add .role-switch to app/static/css/app.css"
```

---

## Implementation Strategy

### MVP First (Phases 1–3)

1. Phase 1: Setup (baseline green, single head `a35580dee830`)
2. Phase 2: Foundational (models, migration, three lists, `reconcile_users`, session identity,
   cast and `client_as`)
3. Phase 3: User Story 1 (the access table for single-role people, areas, header, 403)
4. **STOP and VALIDATE**: the 15-case matrix and the home links (T022), and a local sign-in as
   `teacher@example.com` with the console backend

### Incremental Delivery

1. Setup + Foundational → roles exist and are resolved; nothing is restricted yet
2. **+ US1 → each role opens exactly its pages** (MVP)
3. + US2 → operations' lists are validated, reconciled with exact end-to-end effects, and declared
   on Render
4. + US3 → multi-role people choose a role after signing in
5. + US4 → multi-role people switch from the header; cross-site writes are refused everywhere
6. + US5 → the route sweep keeps "every page declares its roles" true for later milestones
7. + Polish → README, reviews, full gate
8. T073 (rollout gate, before merge) → PR (T074) → merge → post-merge checks (T075)

The milestone ships as **one** pull request (constitution *Branching*), so "incremental" here means
checkpoints on the branch. Each one leaves the suite green and the app runnable. Between US1 and
US3, a multi-role person who signs in is redirected to `/role`, which answers 404 until T050: no
test exercises that path before US3, and no such state is pushed to a PR expecting a release.

---

## Notes

- **[MANUAL] tasks are not optional.** T073 must happen **before** merge (R1 and the start of V6).
  T072 and T075 are the validation procedures that the plan's *Complexity Tracking* justifies as
  procedures rather than tests
- **Values that do not exist until generated**: the Alembic revision id (T012). Real teacher and
  student addresses are entered only in Render (T073) and never written into any file, issue,
  commit, chat or log
- **No login bypass of any kind** (FR-041): the only shortcuts are `sign_in_directly` and
  `client_as` in `tests/conftest.py`
- `[P]` tasks touch different files and depend on nothing unfinished
- Commit after each task or logical group. Stop at any checkpoint to validate the story
  independently
