---

description: "Task list for milestone 11.1: teams (teacher)"
---

# Tasks: Teams (Teacher) (Milestone 11.1)

**Input**: Design documents from `/specs/011.1-teacher-teams/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-047 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R17.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`.
- **Signed-in clients**: `admin_client` and `client_as`. Real teachers come from
  `make_teacher(engine, settings, email=..., institutions={id: AccessLevel.WRITE | READ})`, real
  students from `enrol_student(...)`, classes from `make_class(...)`, institutions from
  `make_institution(...)`; teams and memberships from the new `make_team` / `add_member` (T011).

**Organization**: tasks are grouped by user story (US1–US9 in spec.md).

- **Phase 1 is the components**, because the constitution puts the library, the gallery and the
  guidelines before any page, and **Students** must switch to `section_heading` (FR-046) before
  **Teams** uses it.
- **Phase 2** is the tables, the one migration (with the consent text rewrite and its test fence),
  `reach_team`, the read-side team services and the test helpers.
- **US1** builds the tab, the new-team form, **Add students** and the addition: the MVP.
- **US2** adds rename, delete and remove. **US3** and **US5** are mostly the rule tests over the
  services and routes built in US1–US2 (the rules themselves are in the services from the start, so
  no request can reach an unhandled database error).
- **US4** (access, P1) is enforced inside every route as it is built (the order of checks below);
  its own phase is the cross-cutting sweep, so it follows the last route (US2).

**Reference implementation**: milestones 7–11 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**: `app/services/teacher_access.py` (`reach_institution`, `reach_class`,
  `reach_student`, `_refuse`, `lock=`, `populate_existing`), `app/services/classes.py`
  (`create_class`/`update_class`: a teacher write in one transaction, the `IntegrityError` branch,
  `ClassView.label`), `app/services/students.py` (`list_students`, `remove_student`,
  `_StudentInvitation.revoke`), `app/services/questions.py` (soft deletion with `deleted_at`).
- **Routers**: `app/routers/teacher.py` (`TEACHER_TABS`, `render_teacher`),
  `app/routers/teacher_students.py` (`selection_path`, `_id`/`_quiet_id` parsing against `MAX_ID`,
  `_denied`, `_redirect`, the `chained_lists` selection, the class form, confirmations,
  Post/Redirect/Get, `seal(... INVITATION_SENT_PURPOSE ...)` for a sealed banner).
- **Components**: `app/templates/components/frame.html` (`page_heading`, `back_link`),
  `table.html` (`data_table`, `cell`, `actions_cell`), `selectors.html` (`chained_lists`, with the
  **Show** fallback), `confirmation.html`, `details.html`, `feedback.html` (`notice`, `empty_state`,
  `error_summary`), `form.html`, `button.html` (`link_button`, `post_button`), `badge.html`
  (`status_badge`); the gallery `app/templates/pages/admin/components.html` with
  `app/routers/admin_components.py`; `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Migration**: `migrations/versions/2026_10_27_3e32707ed794_question_bank.py` (frozen snapshot,
  `op.f` names) and `2026_10_19_be91681494be_create_classes_and_enrolments.py` (where
  `STUDENT_CONSENT_TEXT_V1` lives).
- **Tests**: `tests/integration/test_teacher_students.py`, `test_teacher_classes.py`,
  `test_teacher_access.py` (`Scene`, `snapshot`, `AREA_PAGES`, `TEACHER_GETS`/`TEACHER_POSTS`),
  `test_routes.py` (`test_the_write_routes_are_exact`, `TEACHER_SCOPED_PATHS`),
  `test_form_contract.py` with `form_contract.json`, `test_page_patterns.py`,
  `test_component_gallery.py`, `test_migrations.py`, `tests/unit/test_consent_texts.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks** in every handler: role (`@allow_roles(Role.TEACHER)`, 403 for administrator
  and student) → ids (query/form values that are not ASCII digits ≤ `MAX_ID` are 403
  `AccessDenied(Role.TEACHER)`) → the team via `reach_team` (or the institution via
  `reach_institution` for the new-team form), with `write=True` on every *manage* route, **before
  any student id, class id or name is read** (FR-023) → the student or class, checked against the
  team's institution (403) → fields and rules (400 for name errors; "already" and "full" are
  redirects) → the service write, which repeats the reach checks under lock and maps
  `NotReachable`/`WriteRequired` to 403.
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON.
- **Redirects**: every change is a `POST` through the existing cross-site check, answering `303`.
  Every redirect, Cancel and back link to the tab is built by `selection_path` / `team_path` from
  the team's own institution, never from request values (research R10).
- **Logging**: services log ids and counts only, exactly: `Team created: id=%d institution_id=%d`,
  `Team renamed: id=%d`, `Team deleted: id=%d members=%d`, `Team member added: team_id=%d
  user_id=%d`, `Team member removed: team_id=%d user_id=%d`. A no-op logs nothing. No email, first
  or last name ever reaches a log line or an address (FR-016).
- **Locks**: team → user → class → institution and region (research R5), via `with_for_update`
  (a no-op on SQLite). No engine-specific SQL other than the partial index (research R2).
- **No new JavaScript**: the lists reuse `auto-submit.js` and the `chained_lists` **Show** button.
- **Components first**: a new macro is in the library, its CSS in the Components section of
  `app/static/css/app.css` (tokens only, no inline style), the gallery and `ui-guidelines.md`
  **before** a page uses it (FR-046).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US9)

---

## Phase 1: Setup (Components first)

**Purpose**: `section_heading` and `row_note` in the library, the gallery and the guidelines, and
**Students** switched to `section_heading` with its markup unchanged (FR-046, research R12, R13,
contracts/components.md). Nothing here touches the database.

- [ ] T001 Pin the **Students** class heading **before** changing it, in `tests/integration/test_teacher_students.py` (research R12). Render `/teacher/students?region=…&institution=…&class=…` in four states: Write + active class, Write + deactivated class, Read + active class, Read + deactivated class. For each, extract the fragment from `<section aria-labelledby="class-heading">` up to the first `empty_state`/`data_table` output and assert it equals a literal expected string captured from the current template (`app/templates/pages/teacher/students.html` lines 47–62): the `<div class="page-heading">` with `<h2 id="class-heading">`, the `status_badge(False)` only when deactivated, **Add student** only for Write + active, and the `<div class="row-actions">` with Edit, Deactivate/Activate (a `post_button`), Delete only for Write; no `row-actions` div at all for Read. Normalise only insignificant whitespace between tags. The test must pass on the current code.
- [ ] T002 Add `section_heading(title, heading_id, action=None, deactivated=False)` to `app/templates/components/frame.html`, next to `page_heading`, per contracts/components.md §1:
  - emits `<div class="page-heading"><h2 id="{heading_id}">{title}[ {{ status_badge(False) }}]</h2>[{{ link_button(label, href) }}]</div>`, the title escaped, the badge only with `deactivated`, the button only when `action` is a `(label, href)` pair;
  - then, only when `caller` is defined and `caller()` rendered is not blank after `trim`, `<div class="row-actions">{{ caller() }}</div>` (render `caller()` once into a variable, then test it);
  - a docstring-style comment like `page_heading`'s: at most one primary button beside the title; small outline secondary/destructive buttons below; the page owns the `<section aria-labelledby>`.
  No new CSS (`.page-heading` and `div.row-actions` already exist).
- [ ] T003 [P] Add `row_note(text)` to `app/templates/components/table.html` per contracts/components.md §2: emits `<span class="row-note">{{ text }}</span>`; an empty `text` calls `template_error`, as `badge` does. Add one rule to the Components section of `app/static/css/app.css`: `.row-note { color: var(--sc-muted); }` (tokens only; it keeps the row's text size).
- [ ] T004 Add the gallery entries (depends on T002, T003):
  - `app/routers/admin_components.py`: sample data for a 200-character section title and a two-row "Students of KN-21 · year 2" table;
  - `app/templates/pages/admin/components.html`: a new `<section id="section-heading">` right after `#frame` with four variants — (1) action **Add student** plus a row of **Edit** and **Delete**; (2) `deactivated=True` with a row of **Edit**, **Activate** (a `post_button`) and **Delete**; (3) no action and no row; (4) the 200-character title with an action, showing the wrap — and, in `#table`, a second small table with one row holding an **Add** `post_button` and one row holding `row_note("In this team")`. Add `#section-heading` to the gallery's table of contents if it has one.
- [ ] T005 [P] Update `docs/requirements/ui-guidelines.md` (depends on T002, T003):
  - §5 Frame: the `section_heading` paragraph verbatim from contracts/components.md §1 ("**`section_heading(title, heading_id, action=None, deactivated=False)`**: the `h2` of a section that is one selected item, …");
  - §5 Data table: "**`row_note(text)`** stands in the actions cell where a row's action is not available, as "In this team"; muted text, never a disabled button.";
  - §7 Wording: "a row note is a short plain phrase, with no full stop".
- [ ] T006 [P] Extend the component tests (depends on T004): `tests/integration/test_component_gallery.py` — `#section-heading` exists with its four variants (one with the badge, one without any `row-actions`, one 200-character title) and `#table` contains `class="row-note"` with "In this team"; `tests/unit/test_stylesheet.py` — `.row-note` is defined and used, uses `var(--sc-muted)`, no literal colour; add a template test (in `tests/unit/test_templates.py`) that `section_heading` leaves out the `row-actions` div for a `{% call %}` whose content is only white space or an `{% if false %}` block, and that `row_note("")` raises.
- [ ] T007 Switch `app/templates/pages/teacher/students.html` lines 48–62 to `{% call section_heading(selected_class.label, "class-heading", ("Add student", class_path ~ "/invite") if can_write and selected_class.is_active else None, deactivated=not selected_class.is_active) %}{% if can_write %}…Edit, Deactivate/Activate, Delete exactly as today…{% endif %}{% endcall %}`, keeping `<section aria-labelledby="class-heading">` on the page. Import `section_heading` from `components/frame.html`. T001's four pins and the whole of `test_teacher_students.py`, `test_teacher_classes.py`, `test_page_patterns.py` and `test_form_contract.py` pass unchanged (depends on T001, T002).

**Checkpoint**: both components are in the library, gallery and guidelines; **Students** uses
`section_heading` and renders byte-for-byte the same heading.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the tables, the migration (with the consent rewrite and its test fence), `reach_team`,
the read-side team services and the test helpers.

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end.

### 2a. Tables and the migration

- [ ] T008 Create `app/models/team.py` per data-model.md §1–§2, and export `Team` and `TeamMembership` from `app/models/__init__.py`:
  - `class Team(SQLModel, table=True)`, `__tablename__ = "teams"`:
    - `id: int | None` primary key;
    - `institution_id: int = Field(foreign_key="institutions.id", index=True, nullable=False)` (no `ON DELETE`; "Set at creation and never changed: no function writes it after the insert (FR-001)"); the index name must come out as `ix_teams_institution_id`;
    - `name`: `Column(String(NAME_MAX_LENGTH), nullable=False)` — "As entered after `clean_name`: trimmed, 1–200 code points, no control characters (FR-002)";
    - `name_key`: `Column(String(NAME_KEY_MAX_LENGTH), nullable=False)` — "`name_key(name)`: NFC, then case-folded. Never shown. Unique among live teams";
    - `created_at`, `updated_at`: `UTCDateTime`, NOT NULL;
    - `deleted_at: datetime | None`: `UTCDateTime`, nullable — "`NULL` while live; set once by a deletion and never cleared (FR-007, R1)";
    - `__table_args__ = (Index("uq_teams_name_key_live", "name_key", unique=True, sqlite_where=text("deleted_at IS NULL"), postgresql_where=text("deleted_at IS NULL")),)`;
    - docstring: the live rule (`deleted_at IS NULL`) and that milestone 12 may add only live teams; the team is not personal data, its memberships are; no creator is stored; every team, deleted ones included, counts as a use of its institution.
  - `class TeamMembership(SQLModel, table=True)`, `__tablename__ = "team_memberships"`:
    - `team_id: int = Field(foreign_key="teams.id", primary_key=True)`; `user_id: int = Field(foreign_key="users.id", primary_key=True, index=True)` (index `ix_team_memberships_user_id`); no `ON DELETE`;
    - `created_at`: `UTCDateTime`, NOT NULL, never shown;
    - docstring: personal data of the student; its only writers are `teams.add_member` (insert) and `teams.remove_member` and `STUDENT_INVITATION.revoke` (delete); its team belongs to the student's enrolled institution; kept unchanged when the team is deleted or the student is blocked.
- [ ] T009 Create `migrations/versions/2026_10_29_<rev>_teams.py`, generating the id with `uv run alembic revision -m "teams"`, `down_revision = "3e32707ed794"`, per data-model.md §7 and research R9. A frozen snapshot: plain SQLAlchemy types, no imports from `app`, names via `op.f(...)` following the naming convention (depends on T008):
  - **Upgrade**:
    1. `op.create_table("teams", …)` with the columns of data-model §1 (`sa.String(200)`, `sa.String(600)`, `sa.DateTime(timezone=True)`), `pk_teams`, `fk_teams_institution_id_institutions`; then `op.create_index("ix_teams_institution_id", …)`; then `op.create_index("uq_teams_name_key_live", "teams", ["name_key"], unique=True, sqlite_where=sa.text("deleted_at IS NULL"), postgresql_where=sa.text("deleted_at IS NULL"))`;
    2. `op.create_table("team_memberships", …)` with `team_id`, `user_id`, `created_at`, `pk_team_memberships` on `(team_id, user_id)`, `fk_team_memberships_team_id_teams`, `fk_team_memberships_user_id_users`; then `ix_team_memberships_user_id`;
    3. `UPDATE consent_texts SET text = :text WHERE role = 'student' AND version = 1` with `STUDENT_CONSENT_TEXT_V1_REWRITE`, a module-level constant holding the new wording **verbatim** from data-model.md §5 (five paragraphs separated by `"\n\n"`; the fourth, about Resend, unchanged). `version` and `published_at` are not touched.
  - **Downgrade** (lossy by design; say so in the docstring): write `_STUDENT_CONSENT_TEXT_V1_ORIGINAL` — a private, byte-for-byte copy of `STUDENT_CONSENT_TEXT_V1` from `2026_10_19_be91681494be_create_classes_and_enrolments.py` (one revision cannot import another) — back into the same row; drop `team_memberships`, then `teams`, with their indexes.
  - The milestone 9 migration is **not** edited.
- [ ] T010 Fence the one-time rewrite in `tests/unit/test_consent_texts.py` per research R9 (depends on T009):
  - collect originals with `^([A-Z]+)_CONSENT_TEXT_V([0-9]+)$` and rewrites with `^([A-Z]+)_CONSENT_TEXT_V([0-9]+)_REWRITE$`, each defined in at most one migration;
  - a rewrite of a version with no original fails;
  - the published text of a version is its rewrite when one exists, else its original; `PUBLISHED[("student", 1)]` becomes the SHA-256 of `STUDENT_CONSENT_TEXT_V1_REWRITE` (compute it once with `hashlib`);
  - a new `SUPERSEDED = {("student", 1): "0a518ef06fe972985ec55b131ceac238cd61c755404f47a7acb6dab758f06040"}` pins the original, so the milestone 9 migration still cannot change unnoticed;
  - `REWRITES_ALLOWED = {("student", 1)}`: any other rewrite fails with a message saying the exception is one-time (milestone 11.1 FR-015);
  - a test that `_STUDENT_CONSENT_TEXT_V1_ORIGINAL` in the teams migration hashes to the `SUPERSEDED` pin;
  - `test_the_student_text_covers_every_required_topic` reads the published (rewritten) text and also requires "team memberships", "teams" and "erased";
  - update the module docstring for the rewrite rule.
  Also update `ConsentText`'s docstring in `app/models/consent.py`: "append-only" gains the one exception, student version 1 rewritten in place by the teams migration (milestone 11.1 FR-015, research R9).
- [ ] T011 Update `tests/integration/test_migrations.py` for the new head (depends on T009): `teams` and `team_memberships` exist at head with `ix_teams_institution_id`, `uq_teams_name_key_live` (unique, partial) and `ix_team_memberships_user_id`; the existing drift (`compare_metadata`) and stairway tests pass on both engines with no change to them. (The consent rewrite cases are T082.)

### 2b. Access, read-side services and test helpers

- [ ] T012 Add `make_team` and `add_member` to `tests/conftest.py` in a new "Milestone 11.1: teams" section (depends on T008):
  - `make_team(engine, institution_id, name="Rockets", *, deleted=False) -> int`: inserted directly with `name_key(name)`, `created_at = updated_at = utc_now()`, `deleted_at = utc_now() if deleted else None`;
  - `add_member(engine, team_id, user_id) -> None`: a `TeamMembership` inserted directly;
  - docstrings say **test-only** and why it is harmless (a team carries no personal data; seeding skips only the reach and rule checks that `test_team_service.py` and `test_teacher_teams.py` cover), in the style of `make_class` and `make_question`.
- [ ] T013 Add `reach_team(session, teacher_id, team_id, *, institution_id=None, write=False, lock=False) -> tuple[ReachableInstitution, Team]` to `app/services/teacher_access.py` per contracts/services.md (depends on T008):
  - read the team with `session.get(Team, team_id, with_for_update=True, populate_existing=True)` when `lock`, plain `session.get` otherwise;
  - `NotReachable` (through `_refuse(session, lock, …)`) when unknown, when `deleted_at is not None`, or when `institution_id` is given and differs;
  - then `reach_institution(session, teacher_id, team.institution_id, write=write, lock=lock)` (which raises `NotReachable`/`WriteRequired` and rolls back when locked);
  - docstring per the contract; the module docstring gains the fourth definition: **reachable team** = a live team of a reachable institution.
- [ ] T014 Create `app/services/teams.py` with the read side per contracts/services.md (depends on T008, T013):
  - module docstring: the teams service; teacher-scoped writes checked in their own transaction under lock (team → user → class → institution, research R5); soft deletion; memberships are personal data erased by `STUDENT_INVITATION.revoke`; **for milestone 12**, only a team returned by `reach_team` (a live team of an institution the teacher is linked to) may be added to a competition;
  - `MAX_MEMBERS = 50`;
  - exceptions `DuplicateTeamName(ValueError)` with `.message = f"A team named “{entered}” already exists."` (the entered, trimmed name — never the stored name, never an institution), `AlreadyMember(ValueError)` carrying `team_id`, `user_id`, `TeamFull(ValueError)`;
  - frozen dataclasses `TeamView(id, institution_id, name)`, `MemberRow(user_id, first_name, last_name, class_label)`, `StudentTeam(name, is_deleted)`;
  - `list_teams(session, institution_id) -> list[TeamView]`: live teams only, sorted by `name_key`, ties by id;
  - `list_active_members(session, team_id) -> list[MemberRow]`: one query joining `TeamMembership` → `User` → `Enrolment` → `SchoolClass` → `Institution` → `Region`, keeping rows where the class, institution and region are all active (the milestone 9 chain), sorted in Python by `(last_name.casefold(), first_name.casefold(), user_id)`; `class_label` = `"<name> · year <n>"` (reuse `ClassView.label`'s format);
  - `count_members(session, team_id) -> int`: `count(*)` of all memberships, blocked included;
  - `member_ids(session, team_id) -> set[int]`: every member, blocked included;
  - `is_full(session, team_id) -> bool`: `count_members(...) >= MAX_MEMBERS`;
  - `list_student_teams(session, user_id) -> list[StudentTeam]`: every team of the person, deleted included, sorted by `name_key`, ties by team id.
- [ ] T015 Extend the access sweep's scene in `tests/integration/test_teacher_access.py` so it is ready for team routes (depends on T012): `Scene` gains `team` (a live team of `institution` holding `student` as a member, via `make_team`/`add_member`), `deleted_team`, and `other_team` (a live team of `other_institution`); `ids()` gains `"team_id": self.team` (so `{team_id}` and `{user_id}` resolve to a real team and a real member); `AREA_PAGES` gains `"/teacher/teams"`; `SNAPSHOT_TABLES` gains `"teams"` and `"team_memberships"`; `FORM` gains `"student": str(student)` (set per test from the scene). The existing sweeps stay green (no team route exists yet).
- [ ] T016 Create `tests/integration/test_team_service.py` with the read-side cases (depends on T013, T014): `reach_team` returns the team and institution for Write and Read; `NotReachable` for an unknown id, a deleted team, a team of an unlinked institution, a team whose institution or region is deactivated, a mismatched `institution_id`; `WriteRequired` for Read with `write=True`; `list_teams` excludes deleted teams and sorts "alpha", "Beta", "gamma" ignoring case; `list_active_members` order (last name, then first name, case-folded, ties by id) and each `class_label`; `count_members`/`member_ids` include a member whose class is deactivated while `list_active_members` hides them; `list_student_teams` includes a deleted team with `is_deleted=True`, sorted by name ignoring case.

**Checkpoint**: the suite is green on both engines; the tables exist with the rewritten consent text,
fenced by its test.

---

## Phase 3: User Story 1 - A teacher creates a team and adds students to it (Priority: P1) 🎯 MVP

**Goal**: the **Teams** tab with its chained lists and states, **+ Add team**, the new-team form,
the selected team with its members, **Add students** with its class list, and the addition with its
notice.

**Independent Test**: as a Write teacher, create a team, add students from two classes, and check the
member list, the notice, the selection after every step, and that the students' classes are unchanged
(spec US1).

### Service

- [ ] T017 [US1] Add `create_team(session, teacher_id, institution_id, raw_name) -> TeamView` to `app/services/teams.py` per contracts/services.md: `reach_institution(..., write=True, lock=True)`; `clean_name` (roll back and re-raise `InvalidName`); a live team with the same `name_key` in **any** institution → roll back, `DuplicateTeamName(cleaned)`; insert with `created_at = updated_at = utc_now()` and commit; an `IntegrityError` (the partial index in a race) → roll back, `DuplicateTeamName(cleaned)`. Logs `Team created: id=%d institution_id=%d`.
- [ ] T018 [US1] Add `add_member(session, teacher_id, team_id, raw_user_id) -> MemberRow` to `app/services/teams.py` per contracts/services.md, in this order: (1) `reach_team(..., write=True, lock=True)`; (2) `raw_user_id` must be ASCII digits ≤ `MAX_ID` else roll back and `NotReachable`; (3) `reach_student(..., write=True, lock=True)`; (4) the student's class must be in `team.institution_id`, else `NotReachable`; (5) an existing membership → roll back, `AlreadyMember`; (6) `count_members(...) >= MAX_MEMBERS` → roll back, `TeamFull` (blocked members count); (7) insert `TeamMembership(created_at=utc_now())` and commit; an `IntegrityError` → roll back, `AlreadyMember`. Writes nothing else about the student. Logs `Team member added: team_id=%d user_id=%d`. Returns the member's `MemberRow`.
- [ ] T019 [P] [US1] Add US1 service cases to `tests/integration/test_team_service.py`: create trims "  Rockets  " to "Rockets" and logs no name; every `InvalidName` (empty, spaces only, 201 characters after trimming, a control character) stores nothing; `add_member` stores one row and leaves the student's `enrolments`, `user_roles` and sessions unchanged (FR-005); a student in another team of the institution is added and stays in both (US1-14, US5-5); refusals with nothing stored: a non-numeric id, an unknown user, a teacher (not a student), a student of another institution the same teacher reaches (US4-5), a student of a deactivated class (FR-011), a Read teacher, a deleted team.

### Routes and pages

- [ ] T020 [US1] Add **Teams** second to `TEACHER_TABS` in `app/routers/teacher.py`: Students, Teams (`TeacherTab("teams", "Teams", "/teacher/teams")`), Questions, Competitions; `GET /teacher` still answers `303 /teacher/students`; the module docstring names the new router. Update the tab-order assertions in `tests/integration/test_layout.py` and `tests/integration/test_teacher_classes.py` to the four tabs in that order (US1-1; replaced, not deleted: SC-011).
- [ ] T021 [US1] Create `app/routers/teacher_teams.py` (`APIRouter(prefix="/teacher/teams")`) with its shared helpers, and include it in `app/main.py` after `teacher_students` (depends on T013, T014):
  - `selection_path(region_id, institution_id, team_id=None) -> str` → `/teacher/teams?region=<r>&institution=<i>[&team=<t>]`, and `team_path(institution: ReachableInstitution, team_id) -> str`;
  - id parsing, `_denied()`, `_teacher(request)`, `_redirect(path)` (303) as in `teacher_students.py` (import the shared ones rather than copy where they are module-public; otherwise mirror them);
  - `TEAM_NOTICE_PURPOSE = "team-member-notice"`, `TEAM_NOTICE_TTL = timedelta(minutes=10)`, `seal_member_notice(settings, team_id, user_id, outcome)` (payload `{"team": …, "user": …, "outcome": "added" | "already"}`) and `member_notice(session, settings, token, team_id) -> tuple[str, str] | None` returning `("<First> <Last> was added to the team.", "success")` or `("<First> <Last> is already in this team.", "info")` only for a valid, fresh token of this team whose student is in `list_active_members`; `None` for a tampered, expired, other-team or unknown-outcome token (research R11);
  - module docstring: the tab, the order of checks, sealed notices carry ids only.
- [ ] T022 [US1] Implement route 1 `GET /teacher/teams` in `app/routers/teacher_teams.py` per contracts/http-routes.md §1 (depends on T021): query `region`, `institution`, `team`, `notice` as optional strings; the selection validated as on **Students** (institution without region, team without institution, unreachable region, institution not reachable or not in region, team not a live team of the institution → 403); `team=new` → Write: `303 /teacher/teams/institutions/<id>/new`, Read: 403; the team via `reach_team(..., institution_id=…)`; context: regions, institutions labelled "Name — Read"/"Name — Write", `list_teams`, `can_write`, the state message and hint, the selected team, `list_active_members`, the notice. Render through `render_teacher(..., active_tab="teams")`. Opening the page changes nothing.
- [ ] T023 [US1] Create `app/templates/pages/teacher/teams.html` per contracts/http-routes.md §1 (depends on T007, T022): `page_heading("Teams")`; the notice; `chained_lists` with three levels (`region` "Region"/"Select a region"; `institution` "Educational institution"/"Select an educational institution"; `team` "Team"/"Select a team", with `("new", "+ Add team")` last only with Write), each disabled until the previous is chosen and all disabled with no link; one `empty_state` from the table: "You are not linked to any educational institution" / "Ask an administrator to link you to an educational institution."; "Select a region to continue" / "Choose a region in the first list."; "Select an educational institution to continue" / "Choose an educational institution in the second list."; "No teams yet" / Write "Create the first team with + Add team." or Read "A teacher with Write access to this institution creates its teams."; "Select a team to see its members" / "Choose a team in the third list.". The selected team in `<section aria-labelledby="team-heading">` with `{% call section_heading(team.name, "team-heading", ("Add students", "/teacher/teams/<id>/add") if can_write else None) %}{% if can_write %}Rename, Delete (link_button, secondary/destructive, outline, small){% endif %}{% endcall %}`; then "No members in this team yet" (hint "Add the first student with Add students." with Write, none with Read) or `data_table(["Name", "Class", "Actions"] if can_write else ["Name", "Class"])` with `cell("Name", last ~ " " ~ first)`, `cell("Class", class_label)` and, with Write, `actions_cell()` holding `link_button("Remove", "/teacher/teams/<id>/members/<user_id>/remove", kind="destructive", outline=True, small=True)`. (Rename, Delete and Remove target routes that US2 adds; until then they 404.)
- [ ] T024 [US1] Implement routes 2 and 3 (`GET`/`POST /teacher/teams/institutions/{institution_id:int}/new`) per contracts/http-routes.md §2–§3, and create `app/templates/pages/teacher/team_form.html` shared with rename (depends on T017, T021):
  - the page: `back_link(selection_path(region, institution), "Back to Teams")`, `page_heading("New team in “<institution>”")`, `error_summary(errors, order=["name"])`, the text "Educational institution: <name> (<region>)", a form posting to the same address with `field("name", "Name", attrs={"maxlength": "200", "required": True})`, `form_actions("Save", cancel_href=selection_path(region, institution))`;
  - GET: `reach_institution(..., write=True)` else 403;
  - POST: reads only `name` (any other field ignored, FR-001); `create_team`; `NotReachable`/`WriteRequired` → 403; `InvalidName` or `DuplicateTeamName` → 400 with the error beside the field, in the summary, and the value as typed; success → `303 selection_path(region, institution, new_id)`.
- [ ] T025 [US1] Implement route 8 `GET /teacher/teams/{team_id:int}/add` per contracts/http-routes.md §8, and create `app/templates/pages/teacher/team_add_students.html` (depends on T003, T018, T021): `reach_team(..., write=True)` else 403; `class` query optional, when given `reach_class(..., institution_id=team.institution_id)` and active, else 403; page: `back_link(team_path(...), "Back to “<team>”")`, `page_heading("Add students to “<team>”")`, when `is_full` the notice "This team already has 50 members" (`info`), a one-level `chained_lists` (`name="class"`, "Class", "Select a class", the institution's **active** classes from `classes.list_classes` filtered to `is_active`, sorted ignoring case, labelled "KN-21 · year 2", posting to the page's own address); then "Select a class to see its students" / "Choose a class in the list.", or "No students in this class yet", or `data_table(["Name", "Actions"])` over `students.list_students(class)` with `cell("Name", last ~ " " ~ first)` and in `actions_cell()`: `row_note("In this team")` for a member (`member_ids`), else when not full `post_button("/teacher/teams/<id>/members", "Add", kind="secondary", outline=True, small=True, hidden={"student": user_id, "class": class_id})`, else nothing.
- [ ] T026 [US1] Implement route 9 `POST /teacher/teams/{team_id:int}/members` per contracts/http-routes.md §9 (depends on T018, T021): form `student` (required) and `class` (optional, only for the return address); the team with Write first (403), then `add_member`; `NotReachable`/`WriteRequired` → 403; `AlreadyMember` → `303 team_path(...) + "&notice=" + seal_member_notice(..., "already")`; `TeamFull` → `303 /teacher/teams/<id>/add?class=<class>`, dropping `class` when missing, not an id, or no longer an active class of the institution; success → `303 team_path(...) + "&notice=" + seal_member_notice(..., "added")`.

### Tests for the routes

- [ ] T027 [US1] Update the route tables (depends on T024, T026): `tests/integration/test_routes.py` — `test_the_write_routes_are_exact` gains `POST /teacher/teams/institutions/{institution_id:int}/new` and `POST /teacher/teams/{team_id:int}/members`; `TEACHER_SCOPED_PATHS` also takes every `/teacher/teams/` path containing `{` (the declared-page sweep then checks only the denied roles for them), and `test_the_teacher_scoped_pages_are_found` asserts `/teacher/teams/{team_id:int}/add` is in it and `/teacher/teams` is not; `tests/integration/test_teacher_access.py` — `test_the_sweeps_have_routes` expects `len(TEACHER_POSTS) == 10` and the POST sweep posts `student` as the scene's student.
- [ ] T028 [US1] Create `tests/integration/test_teacher_teams.py` with the US1 scenarios (depends on T022–T026), using a scene like `test_teacher_access.py`'s (Olena Write on "Kyiv Polytechnic Institute" with classes "KN-21" year 2 and "KN-31" year 3, students Taras Shevchenko and Lesia Ukrainka):
  - US1-1: the tab row holds Students, Teams, Questions, Competitions in that order and Teams links `/teacher/teams`;
  - US1-2/3: the three lists, disabled in turn; Region and Institution offer exactly what `/teacher/students` offers, each institution marked Read/Write; Team lists live teams sorted ignoring case with "+ Add team" last;
  - every state message and hint of FR-029 (no link, no region, no institution, "No teams yet" with the Write hint, teams but none selected);
  - US1-4/5: `team=new` redirects to the form; saving "  Rockets  " lands on `selection_path(region, institution, id)` with "Rockets" selected and "No members in this team yet" (US1-6);
  - US1-7/8/13: **Add students** shows the back link, the active classes "KN-21 · year 2", "KN-31 · year 3" sorted ignoring case, "Select a class to see its students"; with `class=` the students by last name then first name with **Add**; an empty class shows "No students in this class yet"; the class stays in the address;
  - US1-9: a member shows "In this team" (`class="row-note"`) and no **Add**;
  - US1-10/11: **Add** lands on the tab with the same region, institution and team, the success notice "Taras Shevchenko was added to the team.", and members from two classes listed by last name with "KN-21 · year 2" / "KN-31 · year 3";
  - US1-12: after adding, `/teacher/students` still lists the student in the same class; their enrolment and roles rows are unchanged;
  - the notice: a stale (TTL passed, via the `now` of `seal`/`unseal` or by monkeypatching the clock), tampered, other-team, or no-longer-listed-member token shows no notice and the page is 200;
  - Cancel and the back link on the new-team form return to `selection_path(region, institution)`; the back link on **Add students** returns to `team_path`;
  - SC-010: reloading the redirect target after create and after add repeats nothing (row counts unchanged);
  - the Read teacher sees the tab with no "+ Add team", no Add students/Rename/Delete/Remove, the Read hint, and the member table without the Actions column (US4-2).
- [ ] T029 [P] [US1] Add form-contract cases to `tests/integration/test_form_contract.py` and regenerate only those entries in `tests/integration/form_contract.json` (record that in the module docstring): `teacher-team-new`, `teacher-team-new-invalid` (empty name), `teacher-team-add-students` (with a class chosen: the hidden `student`/`class` fields of the Add buttons), `teacher-teams-selected` (the tab with a team selected: the chained-list form).
- [ ] T030 [P] [US1] Add the new pages to `tests/integration/test_page_patterns.py`: `/teacher/teams` (each state), the new-team form, and **Add students** follow the page patterns (one `h1`, the back link where required, the busy-button and loading-feedback hooks, no inline style).

**Checkpoint**: a Write teacher can create a team and fill it from two classes; the MVP is usable.

---

## Phase 4: User Story 2 - A teacher renames a team, removes a member and deletes a team (Priority: P1)

**Goal**: **Rename**, **Delete** (soft) and **Remove**, each with its form or confirmation and its
return to the tab.

**Independent Test**: rename a team, remove one member, delete the team; check the selection after
every step, the confirmation texts, that the removed student is unaffected, and that the deleted
team stays stored with its memberships while no page lists it (spec US2).

### Services

- [ ] T031 [US2] Add `rename_team(session, teacher_id, team_id, raw_name) -> TeamView` to `app/services/teams.py`: `reach_team(..., write=True, lock=True)`; `clean_name`; another live team (any institution, `id != team_id`) with the key → `DuplicateTeamName(cleaned)` (the team itself never counts, so "comets" → "Comets" is valid, US3-5); unchanged name and key → roll back and return without writing or logging; otherwise set `name`, `name_key`, `updated_at = utc_now()` and commit; `IntegrityError` → roll back, `DuplicateTeamName`. Logs `Team renamed: id=%d`.
- [ ] T032 [US2] Add `delete_team(session, teacher_id, team_id) -> TeamView` to `app/services/teams.py`: `reach_team(..., write=True, lock=True)`; set only `deleted_at = utc_now()` and commit — `name`, `institution_id`, `updated_at` and every membership unchanged (FR-007, FR-009); a second deletion is `NotReachable`. Logs `Team deleted: id=%d members=%d` with `count_members`.
- [ ] T033 [US2] Add `get_member(session, teacher_id, team_id, user_id) -> tuple[ReachableInstitution, TeamView, MemberRow]` (no lock: `reach_team(..., write=True)`, `reach_student(..., write=True)`, the institution check, the membership must exist, else `NotReachable`) and `remove_member(session, teacher_id, team_id, user_id) -> None` (`reach_team(..., write=True, lock=True)`, `reach_student(..., write=True, lock=True)`, the institution check, the membership must exist else `NotReachable`; delete that one row and commit) to `app/services/teams.py`. Logs `Team member removed: team_id=%d user_id=%d`. Nothing else about the student changes (FR-006).
- [ ] T034 [P] [US2] Add US2 service cases to `tests/integration/test_team_service.py`: rename changes `name`, `name_key`, `updated_at`; an unchanged rename writes nothing (same `updated_at`, no log line); delete sets only `deleted_at` (snapshot of the team row and its memberships before and after); a second delete, a rename, an add and a remove of a deleted team are `NotReachable` with nothing changed; remove deletes one row and keeps the student's role, enrolment, class, other memberships and `sessions` rows; removing a non-member, a blocked member, or a member via a Read teacher is refused with nothing changed.

### Routes and pages

- [ ] T035 [US2] Implement routes 4 and 5 (`GET`/`POST /teacher/teams/{team_id:int}/rename`) in `app/routers/teacher_teams.py` with `team_form.html` per contracts/http-routes.md §4–§5 (depends on T031): heading "Rename team “<name>”", back link `team_path(...)` "Back to “<name>”", the field filled with the current name, Cancel to `team_path(...)`; POST: `rename_team`; 403 on refusal; 400 with error and value on `InvalidName`/`DuplicateTeamName`; `303 team_path(...)` on success or no change.
- [ ] T036 [US2] Implement routes 6 and 7 (`GET`/`POST /teacher/teams/{team_id:int}/delete`) and create `app/templates/pages/teacher/team_delete.html` per contracts/http-routes.md §6–§7 (depends on T032): `back_link(team_path(...), "Back to “<name>”")`; `confirmation("Delete team “<name>”?", none, "/teacher/teams/<id>/delete", "Delete", team_path(...))` with `details_list([("Educational institution", "<name> (<region>)"), ("Members", "<n>")])` where `n = len(list_active_members(...))` (blocked not counted, FR-037), and the text "The team will be hidden and can no longer join new competitions. Its members keep their accounts, classes and other teams. A deleted team cannot be restored."; POST: `delete_team`, 403 on refusal, `303 selection_path(region, institution)` (no team) on success.
- [ ] T037 [US2] Implement routes 10 and 11 (`GET`/`POST /teacher/teams/{team_id:int}/members/{user_id:int}/remove`) and create `app/templates/pages/teacher/team_member_remove.html` per contracts/http-routes.md §10–§11 (depends on T033): GET via `get_member`; `back_link(team_path(...), "Back to “<team>”")`; `confirmation("Remove <First> <Last> from team “<team>”?", none, "/teacher/teams/<id>/members/<user_id>/remove", "Remove", team_path(...))` with `details_list([("Class", class_label)])` and "They stay in their class and keep their account and their other teams."; POST: `remove_member`, 403 on any refusal, `303 team_path(...)` on success.

### Tests for the routes

- [ ] T038 [US2] Update the route tables (depends on T035–T037): `test_the_write_routes_are_exact` in `tests/integration/test_routes.py` gains `POST /teacher/teams/{team_id:int}/rename`, `/delete` and `/members/{user_id:int}/remove`; `test_the_sweeps_have_routes` in `tests/integration/test_teacher_access.py` expects `len(TEACHER_POSTS) == 13`.
- [ ] T039 [US2] Add the US2 scenarios to `tests/integration/test_teacher_teams.py` (depends on T035–T037):
  - US2-1: with Write the heading is the `section_heading` markup with **Add students** beside the name, **Rename** and **Delete** in `row-actions`, and **Remove** per member;
  - US2-2: **Rename** opens the form filled with "Rockets"; saving "Comets" returns to `team_path` showing "Comets";
  - US2-3/4: the remove confirmation names "Taras Shevchenko" and "Comets" and shows the class; confirming returns to `team_path` without Taras; Taras keeps his student role, class, enrolment, other teams, and his session still opens `/profile`;
  - US2-5/6: the delete confirmation names "Comets", "Kyiv Polytechnic Institute (Kyiv)" and "Members" with the active count; confirming returns to `selection_path(region, institution)` and "Comets" is gone from the Team list;
  - US2-7/9: the `teams` row (name, institution, `updated_at`) and every `team_memberships` row are unchanged and `deleted_at` is set; the former members' rows are unchanged;
  - US2-8: after deletion the tab with `team=<id>`, rename, delete, add, remove (GET and POST) and an addition all answer 403 with nothing changed;
  - US2-10: a deleted only team gives "No teams yet" with its hint;
  - US2-11: Cancel and back link on rename, delete, remove and **Add students** return to `team_path`, and on the new-team form to `selection_path(region, institution)`; nothing changes;
  - SC-010: reloading after rename, remove and delete repeats nothing.
- [ ] T040 [P] [US2] Add form-contract cases `teacher-team-rename`, `teacher-team-rename-invalid`, `teacher-team-delete`, `teacher-team-member-remove` to `tests/integration/test_form_contract.py` and regenerate only those entries in `tests/integration/form_contract.json`; add the rename form and both confirmations to `tests/integration/test_page_patterns.py`.

**Checkpoint**: the whole tab works for a Write teacher: every endpoint exists.

---

## Phase 5: User Story 3 - Team names are unique across all institutions (Priority: P1)

**Goal**: duplicate names refused everywhere, ignoring case, among live teams only; a deleted
team's name is free again. The rule is already in `create_team`/`rename_team` (T017, T031) and the
partial index (T008–T009); this phase proves it.

**Independent Test**: create and rename teams to names that repeat an existing name in another and
in the same institution, in another case, before and after the existing team is deleted (spec US3).

- [ ] T041 [P] [US3] Add uniqueness cases to `tests/integration/test_team_service.py`: "comets" refused when a live "Comets" exists in another institution (US3-1) and in the same institution; the `DuplicateTeamName.message` is exactly "A team named “comets” already exists." and names no institution; accepted once the other "Comets" is deleted (US3-2), and two deleted teams plus one live team may share a key; rename to another live team's name refused, to a deleted team's name accepted; case-only rename "comets" → "Comets" accepted (US3-5); **the race**: with the lookup bypassed (monkeypatch the duplicate lookup to find nothing), a second live insert is refused by `uq_teams_name_key_live` and surfaces as `DuplicateTeamName` with nothing stored, on both engines.
- [ ] T042 [US3] Add the US3 HTTP scenarios to `tests/integration/test_teacher_teams.py`: creating "comets" in "Lviv Academy" while "Comets" lives in Kyiv gives 400, the form again with "A team named “comets” already exists." beside the field and in the error summary, the entered value kept, and no institution name in the message (US3-1); the same for rename; every invalid name (empty, only spaces, 201 characters after trimming, a control character) gives 400 with the error beside the field, in the summary and the value kept (US3-3, FR-033); "  Rockets  " is stored trimmed (US3-4); after the Kyiv team is deleted, "comets" is accepted (US3-2).

**Checkpoint**: SC-005 holds through the pages, the services and the index.

---

## Phase 6: User Story 4 - Only the right people see and change teams (Priority: P1)

**Goal**: the cross-cutting access sweep over all 11 endpoints. The checks themselves are built into
every route (T022–T026, T035–T037) and every service write.

**Independent Test**: for every page and action, send requests as each role and as teachers with
Write, Read and no link to the team's institution, including typed-in addresses and crafted forms for
unknown, deleted and unreachable teams and students (spec US4).

- [ ] T043 [US4] Extend `tests/integration/test_teacher_access.py` (depends on T038): the existing `TEACHER_GETS`/`TEACHER_POSTS` sweeps now cover the team routes with the scene's real team and member (check they do: `test_every_teacher_page_admits_a_write_teacher` lets Olena through every team page and refuses Read and unlinked on every management page; the POST sweep refuses Read, unlinked, administrator, student and administrator-as-student with the snapshot, `teams` and `team_memberships` included, unchanged); add team hand-made addresses to `hand_made(scene)`: `/teacher/teams?region=<other>&institution=<inst>`, `?institution=<inst>`, `?region=<r>&team=<team>`, `?region=<r>&institution=<inst>&team=<other_team>`, `…&team=<deleted_team>`, `…&team=999999`, `…&team=abc`, `/teacher/teams/999999/rename`, `/teacher/teams/<deleted_team>/add`, `/teacher/teams/<other_team>/delete`, `/teacher/teams/institutions/<other_institution>/new`, `/teacher/teams/<team>/add?class=<other_class>`, `/teacher/teams/<team>/members/999999/remove`.
- [ ] T044 [US4] Add the access matrix to `tests/integration/test_teacher_teams.py`:
  - US4-1: the administrator, a student, and an administrator using the student role get 403 on all 11 endpoints (GET and POST), naming their current role;
  - US4-2/3, FR-024: Mykola (Read) gets 403 on all 9 *manage* endpoints with real ids and `team=new`, and sees no action on the tab; nothing changes;
  - US4-4: unknown, deleted and unlinked-institution team ids, and a team whose institution or region is deactivated, get 403 in addresses and in submitted forms;
  - US4-5: a Write teacher posting `student` = a student of another institution the teacher also reaches, a blocked student, an unknown id, a teacher's id, or `"abc"` to `/members`, or removing a blocked member, gets 403 and nothing changes;
  - US4-6: open a form, confirmation or **Add students** page, then lower the link to Read / remove it / delete the team, then submit: 403 and nothing changes, for create, rename, delete, add and remove;
  - US4-7: a region, institution and team that do not belong together → 403;
  - US4-8: a teacher with Write on one institution and Read on another opening **Add students** of a team of the Read institution → 403;
  - no route answers FastAPI's 422 JSON for any malformed id or missing field.
- [ ] T045 [US4] Add the logging check (FR-016) to `tests/integration/test_teacher_teams.py`: with `caplog` at DEBUG, walk create, rename, add, the "already" path, remove and delete; no log record contains a student's or teacher's email, first or last name, or a team name; the five service lines appear with ids only.

**Checkpoint**: SC-002 holds: 100% of denied cases refuse with nothing changed.

---

## Phase 7: User Story 5 - Membership rules are enforced (Priority: P1)

**Goal**: once per team, same institution only, at most 50 members with blocked members counted. The
rules are in `add_member` (T018) and route 9 (T026); this phase proves them, including the full
state of **Add students**.

**Independent Test**: fill a team to 50 members, blocked ones included, and try a 51st through the
page and a crafted request; add an existing member twice; add a student of another institution
(spec US5).

- [ ] T046 [P] [US5] Add rule cases to `tests/integration/test_team_service.py`: the 51st addition (50 seeded with `add_member`, some in a deactivated class) raises `TeamFull` and stores nothing (FR-004, US6-3); a member re-added to a full team raises `AlreadyMember` (checked before the limit); the `IntegrityError` path: with the existing-membership lookup bypassed, a duplicate insert is refused by the primary key and surfaces as `AlreadyMember` with one row stored; moving a student to another class of the institution with `students.update_student` keeps every membership (US5-4, FR-005); on PostgreSQL only (skip on SQLite), two threads adding the 50th and 51st member to a 49-member team at once store exactly one (SC-004, research R5).
- [ ] T047 [US5] Add the US5 HTTP scenarios to `tests/integration/test_teacher_teams.py`: with 50 members (blocked included) **Add students** says "This team already has 50 members" and shows no **Add** button, while members still show "In this team" (US5-1, FR-041); a crafted 51st addition with `class=<id>` redirects to `/teacher/teams/<id>/add?class=<id>`, which shows the full notice, and stores nothing (US5-2); with a missing or deactivated `class` it redirects to `/teacher/teams/<id>/add` without `class`; a repeated addition from two open pages lands on `team_path` with "Taras Shevchenko is already in this team." (`info`) and one row (US5-3); the same student added to two teams of the institution is in both (US5-5).

**Checkpoint**: SC-004 holds through crafted requests and concurrent additions.

---

## Phase 8: User Story 6 - Deactivation hides and blocks members (Priority: P2)

**Goal**: the milestone 9 chain applied to members. `list_active_members` (T014), the active count
on the delete confirmation (T036) and the active-class list on **Add students** (T025) already
implement it; this phase proves it.

**Independent Test**: deactivate a member's class, institution and region in turn; check the member
list, the delete count and **Add students**; activate again and check the member is back and the
membership never changed (spec US6).

- [ ] T048 [US6] Add the US6 scenarios to `tests/integration/test_teacher_teams.py`: deactivating Taras's class "KN-21" (through `/teacher/students/classes/<id>/deactivate`) hides him from "Comets" with no notice, and a sealed "added" notice for him shows nothing (US6-1); the delete confirmation's "Members" counts only active members while `count_members` still counts him (US6-2, US6-3); **Add students** no longer offers "KN-21" and `?class=<KN-21>` is 403 (US6-5); activating "KN-21" lists Taras again and the `team_memberships` row is byte-for-byte the same (US6-4); a team whose only members are blocked shows "No members in this team yet" and "Members" 0 (spec Edge Cases).
- [ ] T049 [P] [US6] Add the institution and region branches to `tests/integration/test_team_service.py`: `list_active_members` hides a member when their institution or their region is deactivated (set directly with `set_institution_active` / `set_region_active` or the admin services) and lists them again on activation; the membership row is unchanged throughout.

**Checkpoint**: FR-010 holds for class, institution and region.

---

## Phase 9: User Story 7 - Team memberships are personal data (Priority: P2)

**Goal**: the profile lists the student's teams; every path out of the student role erases the
memberships, in deleted teams too; the consent text names them (the rewrite itself is T009–T010).

**Independent Test**: add a student to several teams, delete one, check the profile; then withdraw
consent, delete the data without signing in and remove the student role in turn, and check no
membership is left; read the consent text on a student invitation (spec US7).

- [ ] T050 [US7] In `app/services/students.py`, make `_StudentInvitation.revoke` first `delete(TeamMembership).where(col(TeamMembership.user_id) == user_id)`, then the enrolment and the role as today (research R7); update the module docstring to say removal, withdrawal and data deletion all erase the memberships through `revoke`, in deleted teams too, and the teams are kept.
- [ ] T051 [US7] Add the profile's **Teams** row (research R14, contracts/http-routes.md §"The profile's Teams row"): in `app/routers/profile.py`, when `Role.STUDENT in get_roles(...)` (blocked or not), add `teams = list_student_teams(session, person.id)` to the context; in `app/templates/pages/profile.html`, a `details_list` row "Teams" holding a `<ul>` of names in the service's order with a deleted team as "<name> (deleted)", or "You are not in any team." when empty. Update the router's module docstring.
- [ ] T052 [P] [US7] Add profile cases to `tests/integration/test_profile.py`: a student in "Rockets", "comets" (deleted) and "Alpha" sees "Alpha", "comets (deleted)", "Rockets" in that order (US7-1); a student with no team sees "You are not in any team." (US7-2); a student whose class is deactivated still sees their teams (US7-6); a teacher's and an administrator's profile has no Teams row.
- [ ] T053 [P] [US7] Add erasure cases (US7-3, SC-007): in `tests/integration/test_consent_privacy.py`, a student in a live and a deleted team withdraws consent → no `team_memberships` row with their `user_id`, both `teams` rows unchanged; in `tests/integration/test_data_deletion.py`, the same through "Delete my data" without signing in; in `tests/integration/test_teacher_students.py`, **Remove** on **Students** erases the memberships and keeps the teams.
- [ ] T054 [P] [US7] Add the consent text cases: in `tests/integration/test_student_invitation.py` (or wherever the shown student consent text is asserted), the invitation page shows version 1 with "team memberships", "the teachers linked to your educational institution" and the withdrawal sentence naming team memberships (US7-4); in `tests/integration/test_migrations.py`, an upgrade from `3e32707ed794` of a database holding a student consent record rewrites the student text to `STUDENT_CONSENT_TEXT_V1_REWRITE`, keeps `version = 1`, `published_at` (2026-10-19) and the row id, and leaves the record's `consent_text_id` unchanged (US7-5); a downgrade back to `3e32707ed794` restores the original wording byte for byte, and `upgrade head` brings the rewrite back.

**Checkpoint**: SC-007 holds; the consent promise covers team memberships.

---

## Phase 10: User Story 8 - An institution with teams can only be deactivated (Priority: P3)

**Goal**: every team, deleted ones included, is a use of its institution.

**Independent Test**: try to delete an institution with a team, one with only deleted teams, and one
that never had a team and has no other use (spec US8).

- [ ] T055 [US8] In `app/services/institutions.py`, `count_institution_uses` adds `select(func.count()).select_from(Team).where(col(Team.institution_id) == institution_id)` (deleted teams included; import `Team` from `app.models`, not `app.services.teams`), and its docstring names teams among the uses (milestone 11.1 FR-017, research R8). `delete_institution` is unchanged.
- [ ] T056 [P] [US8] Add cases (US8-1/2/3, SC-008): `tests/integration/test_institution_service.py` — `count_institution_uses` counts a live and a deleted team; `delete_institution` raises `InstitutionInUse` for an institution with only a deleted team and succeeds for one that never had a team; `tests/integration/test_admin_institutions.py` — the admin delete page for "Lviv Academy" (only a deleted team) answers 409 with "is in use and cannot be deleted. You can deactivate it instead."; deleting a class with students is refused as before and an empty class of an institution with teams is deleted as before (FR-018).

**Checkpoint**: SC-008 holds.

---

## Phase 11: User Story 9 - The teacher area shows its new work (Priority: P3)

**Goal**: the home card names the new work; the four-tab row fits the pinned frame.

**Independent Test**: inspect the home page as a teacher; measure the tab row at 360 px and 375 px
and check the targets against the clearances (spec US9).

- [ ] T057 [US9] Set `TEACHER_AREA.description` in `app/routers/areas.py` to "Manage your classes, students and teams, and work with the question bank and competitions." (research R16), and replace the old card text assertion in `tests/integration/test_home.py` with the new text (US9-1; replaced, not deleted: SC-011).
- [ ] T058 [US9] Measure the four-tab row (FR-026, R15, quickstart §6) with headless Playwright, following the memory recipe (`uv run --no-project --with playwright -- python -I <script>` from the scratchpad, a copy of the database, port 8765; never add Playwright to the project): `/teacher/teams` at 360 × 640 and 375 × 667, with **Teams** current and with **Competitions** current — the frame's `getBoundingClientRect().bottom`, the tab row count, whether the page scrolls sideways; then follow the skip link, submit an empty team name and follow the error-summary link, and tab to a field, checking each target lands below the frame (US9-2, US9-3). Expected: two rows, about 158.5 px, under `--sc-frame-clearance-tabs` (176 px below 768 px). Record the numbers in `specs/011.1-teacher-teams/pr-notes.md` and in the clearance note of `docs/requirements/ui-guidelines.md`; raise the token in `app/static/css/app.css` (and its tests) only if a measurement exceeds it.

**Checkpoint**: every story is complete.

---

## Phase 12: Polish & Cross-Cutting Concerns

- [ ] T059 [P] Take review screenshots with the same Playwright recipe into the git-ignored `screenshots/` folder: the tab in each state (Write and Read), the new-team form with an error, **Add students** with "In this team" and in the full state, both confirmations, a 200-character team name and long student names, the profile Teams row, `/admin/components#section-heading` and `#table`, and `/teacher/students` with a class selected (unchanged heading); at 1280 × 800 and 360 × 640, Light and Dark, and once with JavaScript disabled (the **Show** buttons). Check no sideways scroll (SC-009).
- [ ] T060 [P] Update `README.md`: the teacher area's **Teams** tab (teams per institution, unique names everywhere, Write manages / Read sees, soft deletion, 50-member limit, memberships as personal data erased with the student's data), and the rewritten student consent text version 1.
- [ ] T061 Final pass over `docs/requirements/ui-guidelines.md`: `section_heading` and `row_note` in §5, the §7 wording, §8 phone behaviour (the row note sits in the card's actions part), and the clearance note from T058, all matching the gallery.
- [ ] T062 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest`, then the same with `TEST_POSTGRES_URL` set. Everything passes on both engines; the only replaced tests are the old student consent checksum, the three-tab row and the old teacher card wording (SC-011).
- [ ] T063 Walk through [quickstart.md](./quickstart.md) §2–§5 and §7 not already covered by T058–T059, including a real upgrade and downgrade of a copy of `data/app.db` (quickstart §2). Complete `specs/011.1-teacher-teams/pr-notes.md` for the PR description: what changed, the tab-row measurements, the `section_heading` refactor of **Students** (markup pinned), the consent text rewrite as a one-time exception with its test fence, the lossy downgrade, and the replaced tests.
- [ ] T064 On delivery, update `docs/requirements/milestones.md`: move 11.1 from **Upcoming** to **Delivered** as a short summary in the style of the others, with `_Spec:_ [011.1-teacher-teams](../../specs/011.1-teacher-teams/spec.md)`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001 before T007; T002 and T003 in parallel; T004 after
  both; T005 and T006 after T004 (T005 can start after T002/T003); T007 last.
- **Foundational (Phase 2)**: after Setup; blocks every story.
  - T008 first; T009 after T008; T010 and T011 after T009.
  - T012 and T013 after T008, in parallel; T014 after T013; T015 after T012; T016 after T014.
- **US1 (Phase 3)**: after Foundational. T017 and T018 first (same file, in sequence); T020 and
  T021 alongside; T022 → T023; T024, T025, T026 after T021 (same router file: in sequence); T027
  after T024/T026; T028–T030 last.
- **US2 (Phase 4)**: after US1 (it shares the router, `team_form.html` and the tab's buttons).
  T031–T033 in sequence (same file), then T035–T037, then T038–T040.
- **US3 (Phase 5)**: after US2 (it tests rename).
- **US4 (Phase 6)**: after US2 (it sweeps all 11 endpoints).
- **US5 (Phase 7)**: after US1; its HTTP cases need only routes 8 and 9.
- **US6 (Phase 8)**: after US2 (the delete confirmation's count).
- **US7 (Phase 9)**: after Foundational (T014 for `list_student_teams`, T012 for the helpers).
  Independent of US1–US6; can run in parallel with them.
- **US8 (Phase 10)**: after Foundational (T008). Independent of the other stories.
- **US9 (Phase 11)**: T057 after Foundational; T058 after US1 (it needs `/teacher/teams` and the
  four tabs) and ideally after US2.
- **Polish (Phase 12)**: after every story.

### User Story Dependencies

- **US1 (P1)**: Foundational only.
- **US2 (P1)**: US1.
- **US3 (P1)**: US1 for create, US2 for rename.
- **US4 (P1)**: US1 and US2 (all endpoints exist).
- **US5 (P1)**: US1.
- **US6 (P2)**: US1; US2 for the delete count.
- **US7 (P2)**: Foundational only.
- **US8 (P3)**: Foundational only.
- **US9 (P3)**: Foundational for the card; US1 for the measurement.

### Within Each User Story

- Components (macro → CSS → gallery → guidelines) before any page that uses them (Phase 1).
- Service before routes; routes before templates that post to them; route-table, access-sweep and
  form-contract tests updated in the same story that adds the route, so the exact sweeps
  (`test_the_write_routes_are_exact`, `test_the_sweeps_have_routes`) never go red.
- Tests are written alongside and must fail before the implementation where practical.
- `app/services/teams.py`, `app/routers/teacher_teams.py`, `tests/integration/test_team_service.py`,
  `tests/integration/test_teacher_teams.py`, `tests/integration/test_routes.py`,
  `tests/integration/test_teacher_access.py` and `form_contract.json` are touched by several
  stories: tasks on the same file are not [P] against each other.

### Parallel Opportunities

- **Phase 1**: T002 and T003; T005 and T006.
- **Phase 2**: T012 and T013; T010 and T011.
- **US1**: T019 alongside the routes; T029 and T030 alongside T028.
- **US2**: T034 alongside the routes; T040 alongside T039.
- **Cross-story**: US7 (T050–T054), US8 (T055–T056) and T057 can run in parallel with
  US1→US2→US3→US4→US5→US6.

---

## Parallel Example: after Foundational

```bash
# Stream A, the tab (US1 → US2 → US3 → US4 → US5 → US6):
Task: "T017 Add create_team to app/services/teams.py"
Task: "T020 Add Teams second to TEACHER_TABS in app/routers/teacher.py"
Task: "T021 Create app/routers/teacher_teams.py with its helpers and notice token"

# Stream B, personal data (US7):
Task: "T050 Make STUDENT_INVITATION.revoke delete memberships in app/services/students.py"
Task: "T051 Add the Teams row to app/routers/profile.py and app/templates/pages/profile.html"

# Stream C, the institution rule and the card (US8, US9):
Task: "T055 Count teams in count_institution_uses in app/services/institutions.py"
Task: "T057 Set TEACHER_AREA.description in app/routers/areas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (T001–T007): `section_heading` and `row_note` in the library, gallery and guidelines;
   **Students** switched with its heading pinned.
2. Phase 2 (T008–T016): the tables, the migration with the consent rewrite and its fence,
   `reach_team`, the read services, the helpers.
3. Phase 3 (T017–T030): the **Teams** tab, creating a team and adding students.
4. **Stop and validate**: a Write teacher creates a team and fills it from two classes, with and
   without JavaScript; a Read teacher sees it with no actions.

### Incremental Delivery

1. **+ US2**: rename, remove and soft deletion (every endpoint exists).
2. **+ US3, US5**: the name and membership rules proven, including races.
3. **+ US4**: the full access sweep.
4. **+ US6**: the deactivation chain for members.
5. **+ US7, US8, US9** (in parallel if staffed): the profile and erasure, the institution in-use
   rule, the home card and the tab-row measurement.
6. **Polish**: screenshots, README, guidelines, both engines, PR notes, and `milestones.md` on
   delivery.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Commit after each task or logical group. Each story phase ends at a checkpoint that can be
  validated on its own.
- Nothing from milestone 12 is built: the **Competitions** placeholder is untouched, and teams are
  not used in competitions (FR-048).
- The manual checks (T058, T059, T063) are part of the milestone's _Test:_ line; the suite has no
  browser before milestone 16.
