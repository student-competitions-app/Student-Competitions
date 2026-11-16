---

description: "Task list for milestone 12.6: each role lands in its own area"
---

# Tasks: Each Role Lands in Its Own Area (Milestone 12.6)

**Input**: Design documents from `/specs/012.6-role-landing-area/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/templates.md](./contracts/templates.md), [contracts/pipeline.md](./contracts/pipeline.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III, spec FR-025 and FR-026. Research R7 maps the tests to
modules.

- **Engines**: every database test runs on SQLite, and on PostgreSQL too when `TEST_POSTGRES_URL` is
  set (the `sc-pg` container), through the fixtures in `tests/conftest.py` (`client`, `client_as`,
  `admin_client`, `session`, `outbox`).
- **The suite runs in English** (milestone 12.5 FR-067). A test that needs Ukrainian sets the cookie
  `sc_lang=uk` on its client.
- **The cast** (`tests/conftest.py`): `ADMIN_EMAIL`, `TEACHER_EMAIL` and `STUDENT_EMAIL` have one role
  each. `ADMIN_STUDENT_EMAIL` is administrator + student, and `TEACHER_STUDENT_EMAIL` is teacher +
  student. Nobody in the cast is administrator + teacher. Make one with
  `seed_roles_directly(app.state.engine, {ADMIN_STUDENT_EMAIL: [Role.TEACHER]})`.
  `client_as(email, role)` signs in with a chosen current role, and `client_as(email, None)` with none.
- **HTML helpers**: `tests/html.py` (`links`, `link_pairs`, `region`, `h1`, `notices`, `forms`,
  `role_label`, `parse`).
- **Catalogue edits are serialised.** Only the tasks named "catalogue" run `scripts/translations.sh
  update`, translate new Ukrainian entries in `app/locale/uk/LC_MESSAGES/messages.po` and run
  `scripts/translations.sh compile`. Never edit the `.po` files from two tasks at once.
- **`TestClient` follows redirects by default.** `client.get("/")` for an administrator now ends on
  `/admin/teachers`. Pass `follow_redirects=False` wherever the first answer is the point.

**Organization**: tasks are grouped by user story (US1–US6 in spec.md).

- **Phase 2** builds what several stories share: the area declarations' new fields, the back-link
  rule, the status reader, and the database line in the administrator area. The line therefore moves
  **before** the redirect, so no step leaves administrators or the CI `image` job without it.
- **US1** (P1) is the redirect, and also rewrites the tests that relied on `/` being a page for staff.
  **US2** (P1) adds the tests for people with several roles; it needs no new code.
- **US3** (P2) removes the Staff area. **US4** (P2) adds the database-line tests (the code is in
  Phase 2). **US5** (P3) adds the back links. **US6** (P3) does the cleanup and the documentation.

**Reference implementation**: match the docstring style, naming and comment density of:

- `app/routers/areas.py` (the `Area` dataclass, `areas_for`) and `app/routers/admin.py`
  (`render_admin`, `AdminTab`).
- `app/routers/pages.py` (`home`, its milestone 3 error handling) and
  `app/services/database_status.py`.
- `app/main.py` (`_error_page`, `access_denied_handler`) and `app/routers/profile.py` (`profile_page`).
- `tests/integration/test_access_control.py` (access tables, `client_as` per role),
  `tests/integration/test_home.py` (`_fail_database_reads`, `_status_lines`, `area_cards`), and
  `tests/integration/test_login_flow.py` (`request_code`, `submit_code`, `code_from`, `sign_in`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US6)

---

## Phase 1: Setup

**Purpose**: Start from a known-good baseline.

- [X] T001 Confirm the baseline on branch `012.6-role-landing-area`:
  - run `uv run pytest` with `TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres`, plus
    `uv run ruff check .` and `uv run ruff format --check .`; all must pass;
  - run `gh run list --branch main --limit 3` and check that the deploy of the 12.5 merge (`da141ce`)
    succeeded;
  - record any failure in the PR description before changing code.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared declarations and the database line in the administrator area. Behaviour seen by
people changes in one way only: administrator pages gain the database line.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Extend the area declarations in `app/routers/areas.py` (data-model §1–§3). Do **not** remove
  `STAFF_AREA` yet (US3), and keep the administrator and teacher descriptions for now (US1).
  - `Area` fields become, in this order: `path: str`, `title: Text`, `roles: frozenset[Role]`,
    `description: Text | None = None`, `back_label: Text | None = None`.
  - `ADMIN_AREA` gets `back_label=_("Back to the administrator area")`, and `TEACHER_AREA` gets
    `back_label=_("Back to the teacher area")`.
  - Add `LANDINGS: dict[Role, Area] = {Role.ADMIN: ADMIN_AREA, Role.TEACHER: TEACHER_AREA}` and
    `landing_area(role: Role | None) -> Area | None`, which returns `LANDINGS.get(role)` when `role`
    is not `None`, and `None` otherwise.
  - Add `@dataclass(frozen=True) class BackLink` with `path: str` and `label: Text`, and
    `HOME_BACK_LINK = BackLink("/", _("Back to the home page"))`.
  - Add `back_link_for(role: Role | None) -> BackLink`. It returns
    `BackLink(area.path, area.back_label)` for a role in `LANDINGS`, and `HOME_BACK_LINK` for
    `Role.STUDENT` and `None`.
  - Give each new name a one-line docstring in the module's style.
- [X] T003 [P] Create `tests/unit/test_areas.py` (data-model §2–§3):
  - for every `(role, area)` in `LANDINGS`: `role in area.roles` and `area.back_label is not None`;
  - `landing_area(None)` and `landing_area(Role.STUDENT)` are `None`;
  - `landing_area(Role.ADMIN).path == "/admin"` and `landing_area(Role.TEACHER).path == "/teacher"`;
  - `(b.path, str(b.label))` for `back_link_for(...)` equals:
    - `("/admin", "Back to the administrator area")` for `Role.ADMIN`;
    - `("/teacher", "Back to the teacher area")` for `Role.TEACHER`;
    - `("/", "Back to the home page")` for `Role.STUDENT` and for `None`.

  Render the labels with `use_language(Language.EN)` from `app.core.i18n`, as other unit tests do.
- [X] T004 [P] Add `read_database_status_or_none(session: Session) -> DatabaseStatus | None` to
  `app/services/database_status.py` (data-model §4, research R4).
  - It calls the module-level `read_database_status(session)`, so tests can patch that one name.
  - On `SQLAlchemyError` it logs `logger.error("Database status unavailable: %s: %s",
    type(exc).__name__, exc)` and returns `None`. Use `logger = logging.getLogger(__name__)`.
  - The log text changes on purpose: `home` logs "Question data unavailable: …" today, a leftover
    from before milestone 11. What stays as today (spec FR-013) is the shape: the type name and the
    message, never the database address. No test reads the old text. Mention the rename in the PR
    description.
  - It catches nothing else.
  - Its docstring cites milestone 3 FR-026.
- [X] T005 Use the helper in `home`, `app/routers/pages.py`:
  - `db_status = read_database_status_or_none(session)`;
  - the context gets `"db_status": db_status` and `"data_available": db_status is not None`;
  - delete the inline `try/except`, the `SQLAlchemyError` import and the module `logger` if they are
    no longer used.

  Depends on T004.
- [X] T006 Move the database line into the shared footer (contracts/templates.md):
  - in `app/templates/layouts/base.html`, replace `{% block footer_extra %}{% endblock %}` with
    `{% if db_status %}…{% endif %}`, holding the `{%- set revision %}…{% endset %}` and the
    `<p data-engine=… data-revision=… data-boots=…>` line moved **unchanged** from
    `app/templates/pages/home.html`;
  - delete the whole `{% block footer_extra %}` override from `home.html`.
- [X] T007 Give every administrator page the line. In `render_admin`, `app/routers/admin.py`, open
  `with Session(request.app.state.engine) as session:`, compute
  `read_database_status_or_none(session)`, and add `"db_status"` to the context **before**
  `**(context or {})`.
  - Import `Session` from `sqlmodel`.
  - Update the docstring: every administrator page shows the database line, and a failed read leaves
    it out (spec FR-010, FR-013).

  Depends on T004.
- [X] T008 [P] Point the existing failure patches at the new seam. In `tests/integration/test_home.py`
  (`_fail_database_reads`) and `tests/integration/test_health.py`, replace
  `monkeypatch.setattr(pages, "read_database_status", failing)` with
  `monkeypatch.setattr(database_status, "read_database_status", failing)`, where
  `from app.services import database_status`. Remove the `pages` imports if they become unused.

  Depends on T005: until `home` calls `read_database_status_or_none`, it holds its own imported
  `read_database_status`, and patching the service module does not reach it.
- [X] T009 Catalogue: run `scripts/translations.sh update`, then set the Ukrainian `msgstr` in
  `app/locale/uk/LC_MESSAGES/messages.po`:
  - "Back to the administrator area" → «Назад до розділу адміністратора»;
  - "Back to the teacher area" → «Назад до розділу педагога».

  Clear any `fuzzy` flag, then run `scripts/translations.sh compile` and `scripts/translations.sh
  check`.
- [X] T010 Checkpoint: `uv run pytest` passes. Fix any test that asserted an administrator page has
  **no** database line; none is expected.

**Checkpoint**: The foundation is ready. Administrator pages show the database line, and nothing else
has changed.

---

## Phase 3: User Story 1 - An administrator or a teacher lands in their own area (Priority: P1) 🎯 MVP

**Goal**: `/` redirects an administrator to `/admin` and a teacher to `/teacher`. A student keeps the
home page.

**Independent Test**: Sign in as the single-role administrator and the single-role teacher. Each lands
on their area's first tab with no home page in between, and the brand link brings them back there
(spec US1).

### Tests for User Story 1 ⚠️

> Write these first and make sure they fail before T012.

- [X] T011 [P] [US1] Create `tests/integration/test_landing.py` with:
  - **per role**, `follow_redirects=False`:
    - `client_as(ADMIN_EMAIL).get("/")` is 303 with `location == "/admin"`, and following it ends on
      `/admin/teachers` with the **Teachers** tab `aria-current="page"`;
    - `client_as(TEACHER_EMAIL).get("/")` is 303 → `/teacher`, ending on `/teacher/students`;
    - `client_as(STUDENT_EMAIL).get("/")` is 200 with exactly one area card, `/student`, and one
      database line;
    - `client.get("/")` (signed out) is 303 → `/login?next=%2F`.

    Do not test `HEAD /`: `home` is a plain `@router.get`, which FastAPI answers with 405 for `HEAD`,
    today and after this milestone (spec Out of Scope: no routing change beyond where `/` leads).
  - **sign-in without `next`**: through `request_code` / `submit_code` / `code_from` from
    `tests/integration/test_login_flow.py`, the administrator and the teacher each get 303 → `/`, and
    following it ends on their first tab.
  - **sign-in with `next=/teacher/competitions`** for the teacher goes there (spec FR-007).
  - **brand link**: on `/admin/subjects` the top bar's brand link has `href="/"`. Following `/` as
    the administrator ends on `/admin/teachers`.
  - **`/role` with one role**: `client_as(TEACHER_EMAIL).get("/role", follow_redirects=False)` is
    303 → `/`, and following it ends on `/teacher/students`.
  - **no database read**: patch `database_status.read_database_status` to raise `OperationalError`.
    The administrator's `GET /` is still 303 → `/admin`, and `caplog` holds no "Database status
    unavailable" record from that request (spec plan constraint, research R1).

### Implementation for User Story 1

- [X] T012 [US1] Redirect in `home`, `app/routers/pages.py`. Before any database read, set
  `area = landing_area(current_role)`, and when it is not `None` return
  `RedirectResponse(area.path, status_code=303)`. The return type becomes `Response`. Rewrite the
  docstring: `/` lands an administrator or a teacher in their area (spec FR-001, research R1) and shows
  the student's home page otherwise.
- [X] T013 [US1] In `app/routers/areas.py`, remove the `description=` of `ADMIN_AREA` and
  `TEACHER_AREA`, so they default to `None`. Only `STUDENT_AREA` keeps one (data-model §1).
- [X] T014 [US1] Catalogue: `scripts/translations.sh update`. Check that "Manage teachers, educational
  institutions and subjects." and "Manage your classes, students and teams, and work with the question
  bank and competitions." are gone from `app/locale/messages.pot` and both `.po` files. Then compile
  and check.

### Tests rewritten for User Story 1

- [X] T015 [P] [US1] Rewrite `tests/integration/test_home.py` for a student-only home page:
  - Every test that reads the home page's content through `admin_client.get("/")` uses
    `client_as(STUDENT_EMAIL)` instead. That covers the header, title, viewport, headline, footer,
    status line, unavailable notice, no-write-affordance and greeting tests.
  - `test_home_returns_ok` uses `client_as(STUDENT_EMAIL)` too. With `admin_client` it would follow
    the new redirect to `/admin/teachers` and pass for the wrong reason.
  - The error-page tests that use `/about` keep their client.
  - `test_one_card_per_allowed_area_with_its_description` keeps only the student cases:
    `STUDENT_EMAIL`, and `ADMIN_STUDENT_EMAIL` and `TEACHER_STUDENT_EMAIL` with `Role.STUDENT`.
  - `test_unavailable_data_keeps_the_cards_and_drops_the_database_line` expects `["/student"]`.
  - `test_the_home_page_lists_no_questions` is parametrised with `STUDENT_EMAIL` only.
  - **Delete** `test_the_teacher_card_names_students_teams_the_question_bank_and_competitions`.
- [X] T016 [P] [US1] Update `tests/integration/test_access_control.py`:
  - In `test_the_access_table`, add a `LANDING = {ADMIN: "/admin", TEACHER: "/teacher"}` branch for
    path `/`: for those roles, assert 303 with that `location`.
  - `HOME_LINKS` keeps only `STUDENT`.
  - `test_the_home_page_lists_exactly_the_allowed_areas` is parametrised with `STUDENT` only.
  - Leave the `/staff` rows for US3.
- [X] T017 [P] [US1] Replace the `GET /` probes that meant "still signed in" or "signed out" (research
  R7 item 5):
  - **signed-in probes** become `get("/profile", follow_redirects=False).status_code == 200`;
  - **signed-out probes** assert status 303 **and** `response.headers["location"].startswith("/login")`.

  Files:
  - `tests/integration/test_admin_teachers.py` (≈ lines 324, 376, 390);
  - `tests/integration/test_profile.py` (≈ 184, 224, 327);
  - `tests/integration/test_cross_site.py` (≈ 81, 124: the cross-site `GET` probe moves to
    `/profile`);
  - `tests/integration/test_self_invitation.py` (≈ 71);
  - `tests/integration/test_user_reconcile.py` (≈ 389);
  - `tests/integration/test_sessions.py` (≈ 266; lines 276 and 287 already assert the `location` and
    stay).
- [X] T018 [P] [US1] Move the tests that used `/` as a sample staff page to the page staff now see:
  - `tests/integration/test_layout.py` (≈ 45, 54, 63, 152) → `"/admin/teachers"`; the line at 152
    keeps its database-line assertion there;
  - `tests/integration/test_form_contract.py`, cases `frame-with-role-switch` and `frame-single-role`
    → `.get("/admin/teachers")`;
  - `tests/integration/test_health.py` (`test_healthz_stays_ok_while_the_database_is_failing`) reads
    the unavailable notice from `client_as(STUDENT_EMAIL).get("/")`;
  - `tests/integration/test_admin_area.py`:
    - `test_no_tab_row_outside_the_area` is parametrised with `["/profile"]` only, because `/` and
      `/role` now land inside the area for an administrator;
    - **delete** `test_the_home_page_still_links_to_admin`.

  Run, and adjust only if they fail: `test_login_flow.py` (≈ 120, 454), `test_role_switch.py`
  (≈ 61, 83, 124), `test_language.py` (≈ 234), `test_boot_counter.py` and `test_routes.py`. They
  follow redirects, so they should still pass.

  The switches on area pages (spec edge case "The language and theme switches") need no new test.
  These existing tests already prove that a switch used on an area page returns to that page, and
  must keep passing unchanged:
  - `test_language.py`: `test_the_page_and_its_query_are_kept` (`/admin/subjects?…`) and
    `test_the_switch_on_every_role_s_pages_comes_before_the_user_menu` (`/admin/teachers`,
    `/teacher/students`);
  - `test_theme.py`: `test_a_signed_in_person_returns_to_their_page` (`/admin/subjects`).
- [X] T019 [US1] Update the pipeline per contracts/pipeline.md:
  - In `.github/workflows/checks.yml`, job `image`, rename the step to "Sign in, smoke test the
    landing, restart, and again".
  - Rename `check_home` to `check_landing`. It first asserts that `GET /` with the cookie jar answers
    `303` with `redirect_url` `$base/admin`, then runs today's content checks on
    `$base/admin/teachers`: application name, signed-in address, logout form, no "temporarily
    unavailable", `data-engine="postgresql"`, `data-boots`, and the role label "Administrator".
  - Replace the area-links check with: no `href="/staff"`, `href="/student"` or `href="/teacher"`.
  - Change `check_page / 200 'class="brand-role"'` to `check_page /admin/teachers 200
    'class="brand-role"'`.
  - Keep the anonymous and after-logout `GET /` checks.
  - Reword the step's leading comment, and the comment in `.github/workflows/deploy.yml` (≈ line 55),
    to say the status is read on the administrator area's first tab.
- [X] T020 [US1] Checkpoint: `uv run pytest` and `uv run ruff check .` pass. T011 is green.

**Checkpoint**: User Story 1 is complete. Staff land in their area, and students are unchanged.

---

## Phase 4: User Story 2 - A person with several roles lands in the area of the role they chose (Priority: P1)

**Goal**: The role choice and the role switch land in the chosen role's area. No new code is expected:
both already return to `/`.

**Independent Test**: As an administrator–teacher, choose a role after sign-in, then switch to the
other role from the user menu. Each step lands in the right area (spec US2).

### Tests for User Story 2 ⚠️

- [X] T021 [P] [US2] Add to `tests/integration/test_landing.py`:
  - **no role yet**: `seed_roles_directly(app.state.engine, {ADMIN_STUDENT_EMAIL: [Role.TEACHER]})`,
    then `client_as(ADMIN_STUDENT_EMAIL, None).get("/", follow_redirects=False)` is 303 →
    `/role?next=%2F`;
  - **choose**: from that state, `POST /role` with `role=admin, next=/` ends on `/admin/teachers`, and
    with `role=teacher, next=/` on `/teacher/students`;
  - **switch from the user menu**: `POST /role` with only `role`, as the menu sends it, from teacher
    to administrator ends on `/admin/teachers`, and the other way round on `/teacher/students`;
  - **current role only** (spec FR-005): `client_as(ADMIN_STUDENT_EMAIL, Role.ADMIN).get("/")` → 303
    `/admin`, never `/teacher`;
  - **teacher and student**: `client_as(TEACHER_STUDENT_EMAIL, Role.STUDENT).get("/")` is 200 with
    the home page, and switching to `teacher` ends on `/teacher/students`;
  - **real sign-in with several roles**: `submit_code` for `ADMIN_STUDENT_EMAIL` → 303
    `/role?next=%2F`, and choosing `admin` ends on `/admin/teachers`.
- [X] T022 [US2] Run T021. If any case fails, fix it in `app/routers/roles.py` without adding a
  role-specific address (spec FR-006). None is expected to fail. Then review
  `tests/integration/test_role_switch.py` and `tests/integration/test_role_choice.py` for assertions
  that an administrator or a teacher "lands on the home page", and update them to the area.

**Checkpoint**: User Stories 1 and 2 are complete.

---

## Phase 5: User Story 3 - The empty Staff area is gone (Priority: P2)

**Goal**: `/staff` is an unknown address for everyone, and the Staff area is named nowhere.

**Independent Test**: `/staff` answers 404 for the administrator, the teacher, the student and a
signed-out visitor, and no page links to it, in either language (spec US3).

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] In `tests/integration/test_access_control.py`:
  - Remove `/staff` from `ACCESS_TABLE`, `TITLES` and `PLACEHOLDER_AREAS`.
  - Add **one** test, `test_the_staff_area_is_an_unknown_address`. It is the only test under `tests/`
    that mentions `/staff`, "Staff area" or «Розділ працівників» (spec FR-023, US6 scenario 3, the
    milestone's _Test:_ line), so every `/staff` check lives in it. Parametrise it with
    `"anonymous"`, `ADMIN_EMAIL`, `TEACHER_EMAIL` and `STUDENT_EMAIL`, and follow the gallery test in
    `tests/integration/test_component_gallery.py`:
    - **404** (spec FR-008): `browser.get("/staff", follow_redirects=False)` and
      `browser.get("/no-such-page", …)` are both 404, and
      `response.text.replace("/staff", "/no-such-page") == unknown.text`;
    - **no link, no name** (spec FR-009): for the signed-in visitors, the page they land on (`/`
      followed) and `/profile` hold no link to `/staff` (`html.links`), and neither "Staff area" nor,
      with the cookie `sc_lang=uk`, «Розділ працівників» appears;
    - **old bookmark** (spec US3 scenario 3): for `"anonymous"`, sign in as `TEACHER_EMAIL` through
      `request_code` / `submit_code(…, next_path="/staff")` / `code_from`. The answer is 303 →
      `/staff`, and following it ends on 404 **Page not found** with the link
      `("/", "Back to the home page")`.
- [X] T024 [P] [US3] Update `tests/integration/test_role_choice.py`:
  - in the parametrisation at ≈ line 110, replace `("/staff?x=1", "/role?next=%2Fstaff%3Fx%3D1")` with
    `("/teacher/teams?x=1", "/role?next=%2Fteacher%2Fteams%3Fx%3D1")`;
  - at ≈ lines 213–216, use `next_path="/teacher/teams"`, expect `location == "/teacher/teams"`, and
    expect 200 there. The `/staff` return address is tested in T023 instead.

### Implementation for User Story 3

- [X] T025 [US3] In `app/routers/areas.py`:
  - delete `STAFF_AREA` and the `staff_area` handler;
  - set `AREAS = (ADMIN_AREA, TEACHER_AREA, STUDENT_AREA)`;
  - `_render` and `student_area` stay.
- [X] T026 [US3] Catalogue: `scripts/translations.sh update`. Check that "Staff area" («Розділ
  працівників») and "Pages shared by administrators and teachers." are gone from
  `app/locale/messages.pot` and both `.po` files. Then compile and check.

**Checkpoint**: The Staff area is gone, and the suite passes.

---

## Phase 6: User Story 4 - Administrators still see the database line (Priority: P2)

**Goal**: Every administrator page shows the database line, no teacher page does, and a student keeps
it on the home page. The code was done in T004–T007; this phase proves it.

**Independent Test**: Read the footers of administrator pages, teacher pages and the student's home
page, then make the read fail (spec US4).

### Tests for User Story 4 ⚠️

- [X] T027 [P] [US4] Create `tests/integration/test_database_line.py`. Reuse the `_status_lines`
  pattern: elements with a `data-engine` attribute.
  - **Administrator pages** (`admin_client`): each of `[tab.path for tab in ADMIN_TABS]`,
    `/admin/subjects/new`, the 400 page from `POST /admin/subjects` with an empty name, and
    `/admin/components` each have exactly one line inside `html.region(body, "footer")`, with
    `data-engine` the engine's dialect name and `data-boots` a positive integer.
  - **Teacher pages** (`client_as(TEACHER_EMAIL)`): each of `[tab.path for tab in TEACHER_TABS]` has
    none.
  - **The student's home page** has one.
  - **Failure**: patch `database_status.read_database_status` to raise
    `OperationalError("SELECT 1", {}, Exception("boom"))`. Then `admin_client.get("/admin/subjects")`
    is 200, has no line, and its body holds none of "OperationalError", "boom" and "SELECT".
    `caplog` holds `"Database status unavailable: OperationalError: …"`, and no record contains
    `DATABASE_URL`'s value.
- [X] T028 [P] [US4] Make `tests/integration/test_boot_counter.py` (≈ lines 65, 71, 83, 86) read the
  line from `/admin/teachers` explicitly, where the pipeline now reads it (contracts/pipeline.md),
  instead of following `/`.

**Checkpoint**: The database line is where the spec says, and fails safely.

---

## Phase 7: User Story 5 - Back links lead to the person's area (Priority: P3)

**Goal**: The profile page and the error page link back to the person's area.

**Independent Test**: Read the back link on `/profile` and on the 403 page per role, and on
`/no-such-page` (spec US5).

### Tests for User Story 5 ⚠️

- [X] T029 [P] [US5] In `tests/integration/test_page_patterns.py`, replace the single administrator
  assertion (≈ line 132) with a test parametrised over `(email, role, href, text)`:
  - `(ADMIN_EMAIL, ADMIN, "/admin", "Back to the administrator area")`;
  - `(TEACHER_EMAIL, TEACHER, "/teacher", "Back to the teacher area")`;
  - `(STUDENT_EMAIL, STUDENT, "/", "Back to the home page")`;
  - `(ADMIN_STUDENT_EMAIL, STUDENT, "/", "Back to the home page")`.

  The milestone's _Test:_ line also asks for "Back to the home page" on the profile page for a
  person with several roles who has not chosen one. That case cannot happen: `/profile` sends them
  to the role choice first (spec US5 scenario 4). The last row stands in for it: a person with
  several roles whose current role is not a staff role. Say so in the PR description. The _Test:_
  line disappears when T043 compacts the milestone.

  Each calls `assert_back_link(client_as(email, role).get("/profile").text, href, text)`. Add two
  cases with the cookie `sc_lang=uk` (spec FR-021, SC-007):
  - the administrator, expecting «Назад до розділу адміністратора»;
  - the teacher, expecting «Назад до розділу педагога».
- [X] T030 [P] [US5] In `tests/integration/test_access_control.py`, `test_the_access_denied_page`
  expects `BACK = {ADMIN: ("/admin", "Back to the administrator area"), TEACHER: ("/teacher", "Back
  to the teacher area"), STUDENT: ("/", "Back to the home page")}[role]` in
  `html.link_pairs(body, "main")`. Add `test_an_unknown_address_links_home`:
  - `admin_client.get("/no-such-page")` has `("/", "Back to the home page")`;
  - `admin_client.post("/logout", headers={"Origin": "https://evil.example"})` (403 cross-site) has
    the same link.

  Both are answered before the session is read (research R3).

### Implementation for User Story 5

- [X] T031 [P] [US5] Profile back link:
  - In `profile_page`, `app/routers/profile.py`, add `"back": back_link_for(request.state.current_role)`
    to the context. The route is `@allow_roles(*ALL_ROLES)`, so a role is set.
  - In `app/templates/pages/profile.html`, replace `{{ back_link("/", _("Back to the home page")) }}`
    with `{{ back_link(back.path, back.label) }}`.
- [X] T032 [P] [US5] Error page back link:
  - In `_error_page`, `app/main.py`, add
    `"back": back_link_for(getattr(request.state, "current_role", None))` to the context.
  - In `app/templates/pages/error.html`, replace the fixed link with
    `<p><a href="{{ back.path }}">{{ back.label }}</a></p>`.
  - Leave `app/templates/pages/data_erased.html` unchanged (spec FR-017).
- [X] T033 [US5] Checkpoint: T029, T030 and `tests/unit/test_template_text.py` pass, so no English
  text is left in a template outside a message. The "Back to the home page" message stays in the
  catalogues, now used from `areas.py`.

**Checkpoint**: Back links follow the role.

---

## Phase 8: User Story 6 - Nothing is left of what was removed (Priority: P3)

**Goal**: No code, message, test or document still serves or describes the Staff area or a staff home
page (spec FR-019 to FR-030).

**Independent Test**: The leftover searches in quickstart §2 return only the allowed hits, the catalogue
check passes, and the whole suite passes.

- [X] T034 [P] [US6] Correct the comments and docstrings (research R10):
  - `app/routers/areas.py`: the module docstring describes three areas, the landings and the back
    links, with no "four areas" and no "home page keeps its link";
  - `app/routers/admin.py` and `app/routers/teacher.py`: the module docstrings drop "the home page
    links to it"; the area address is where `/` sends the role;
  - `app/routers/pages.py`: the module docstring;
  - `app/routers/roles.py`: the `role_choice` docstring ("a person with one role … goes to `/`,
    which opens their area") and `choose_role`;
  - `app/static/css/app.css` (≈ line 839): the footer comment says the database line is on the
    administrator area's pages and the student's home page;
  - `tests/integration/test_routes.py` (≈ line 408): the docstring.
- [X] T035 [P] [US6] Update `README.md` (research R9):
  - the access table (≈ lines 74–80): delete the `/staff` row; the `/` row says "administrator →
    `/admin`, teacher → `/teacher`, student → home page";
  - the areas paragraph (≈ line 82): "The student area is a placeholder…"; administrators and teachers
    land in their own area; the home page is the student's; the database line is in the
    administrator area's footer and on the student's home page;
  - the **Switching** bullet (≈ line 85): it lands in the new role's area;
  - "Service status" (≈ line 315): the boot count is read on the administrator area's first tab;
  - the source tree (≈ lines 418, 421): `pages.py` "GET / → landing redirect for staff, the
    student's home page"; `areas.py` "/student placeholder; the areas, their landings and back
    links".
- [X] T036 [P] [US6] Update `docs/requirements/ui-guidelines.md` (research R9):
  - frame item 1 (≈ line 172): the wordmark links to `/`, which opens the current role's area
    (milestone 12.6);
  - frame item 5 (≈ line 179): the footer has the version and build, and on the administrator area's
    pages and the student's home page the database line;
  - check the card section (≈ line 309): "as on the home page" stays true for students.
- [X] T037 [P] [US6] In `docs/requirements/milestones.md`, Delivered, milestone 3: "The home page
  shows a database status line…" becomes "The database status line (in the footer of the
  administrator area and the student's home page since milestone 12.6) …". Keep its link and style.
  Check the other Delivered summaries; none should name the home page or the Staff area. Leave
  `product-requirements.md` and `technical-requirements.md` unchanged (they mention neither) and every
  `specs/` file except this feature's.
- [X] T038 [US6] Dead-code sweep (spec FR-019, FR-023):
  - `uv run ruff check .` reports no unused import;
  - `grep -rn` each test constant and helper touched in T015–T030 (`HOME_LINKS`, `PLACEHOLDER_AREAS`,
    `area_cards`, `area_links`, `_questions_section`, `pages` imports) and delete any left without a
    caller;
  - check `app/static/css/app.css` for rules used only by staff home cards (`card-grid` stays: the
    student's home page uses it).
- [X] T039 [US6] Run the leftover searches in quickstart §2. The only `/staff` or "Staff area" hits
  allowed are the single T023 test and milestone 12.6's text in `docs/requirements/milestones.md`. Every
  "home page" hit is about the student's page, the back or "Go to" links, or the signed-out redirect.

**Checkpoint**: Clean.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T040 Run the full gate: `TEST_POSTGRES_URL=… uv run pytest` on both engines (0 skipped
  because of this milestone), `uv run ruff check .`, `uv run ruff format --check .` and
  `scripts/translations.sh check`.
- [X] T041 Walk through quickstart §3 by hand, or take headless screenshots of the administrator's
  landing, the teacher's landing, the student's home page and `/staff` in both languages (memory: Playwright via `uv run --with playwright`, a database
  copy, port 8765).
- [ ] T042 Push the branch, open the PR (body ends with the attribution line), and check that the
  `image` job of `checks.yml` passes with `check_landing` (quickstart §4). The PR description notes:
  - the log text rename "Question data unavailable" → "Database status unavailable" (T004);
  - the _Test:_ line's "several roles, no role chosen" profile case, which cannot happen, and the
    case that stands in for it (T029).
- [ ] T043 After acceptance, compact milestone 12.6 into the Delivered section of
  `docs/requirements/milestones.md`: a short product summary with a link to
  `specs/012.6-role-landing-area/spec.md` and no _Test:_ line, as the file's top note says.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup. **Blocks all stories.** Within it, T004 comes before T005
  and T007; T005 comes before T008; T002 comes before T003; T009 comes after T002.
- **US1 (Phase 3)**: after Phase 2. It is the MVP.
- **US2 (Phase 4)**: after US1, because the landing must exist.
- **US3 (Phase 5)**: after Phase 2. It can run beside US1 or US2, but T023 edits
  `test_access_control.py` after T016, so do them in that order.
- **US4 (Phase 6)**: after Phase 2. T028 is meaningful after US1.
- **US5 (Phase 7)**: after Phase 2 (T002 provides `back_link_for`). T030 edits
  `test_access_control.py` after T023.
- **US6 (Phase 8)**: after US1–US5, because it cleans up what they leave.
- **Polish (Phase 9)**: last.

### Serialised resources

- **Catalogues**: T009 → T014 → T026, one at a time.
- **`tests/integration/test_access_control.py`**: T016 → T023 → T030.
- **`tests/integration/test_landing.py`**: T011 → T021.
- **`app/routers/areas.py`**: T002 → T013 → T025 → T034.
- **`app/routers/pages.py`**: T005 → T012 → T034.

### Parallel Opportunities

- Phase 2: T003 and T004 together, and T008 (after T005) beside T006–T007.
- US1: T011 first, then T015, T016, T017 and T018 in parallel (different files). T019 is independent of
  them.
- US4: T027 and T028 in parallel.
- US5: T029 with T031–T032, which are different files from each other.
- US6: T034, T035, T036 and T037 in parallel.

### Parallel Example: User Story 1

```text
After T012–T014:
  T015  tests/integration/test_home.py
  T016  tests/integration/test_access_control.py
  T017  test_admin_teachers.py, test_profile.py, test_cross_site.py, test_self_invitation.py,
        test_user_reconcile.py, test_sessions.py
  T018  test_layout.py, test_form_contract.py, test_health.py, test_admin_area.py
  T019  .github/workflows/checks.yml, deploy.yml
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 → Phase 2. Administrator pages show the database line, and nothing else changes.
2. Phase 3 (US1). Staff land in their area, every rewritten test passes, and the CI `image` job checks
   the landing.
3. **Stop and validate**: the US1 independent test, and the PR's CI.

### Incremental Delivery

US1 → US2 (tests only) → US3 (Staff area removed) → US4 (line tests) → US5 (back links) → US6 (cleanup,
docs) → Polish. Each phase ends with a green suite, so the branch can be reviewed at any checkpoint. The
milestone ships as one PR, as a single Spec Kit feature.

---

## Notes

- [P] tasks touch different files and depend on no unfinished task.
- Story labels map tasks to spec.md's user stories for traceability.
- Never skip a failing test to get past a phase. Rewrite it for the new behaviour or delete it (spec
  FR-023).
- Specs of delivered milestones are never edited (spec FR-024).
