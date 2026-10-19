---

description: "Task list for milestone 9: user management with consent — classes and students"
---

# Tasks: User Management with Consent — Classes and Students (Milestone 9)

**Input**: Design documents from `/specs/009-classes-students-management/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-058 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`.
- **Signed-in clients**: `admin_client` and `client_as`.
- **Emails**: read from the `outbox` fixture (the `memory` backend).

**Organization**: tasks are grouped by user story (US1–US9 in spec.md). Phases 1–2 come first,
because every story needs them:

- the pure schemas;
- the two tables and the migration;
- the chain rule (`availability`);
- teacher reach (`teacher_access`);
- the test helpers.

**Reference implementation**: milestones 6–8 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**:
  - `app/services/teachers.py`: `_TeacherInvitation`, `_current_teacher`, `remove_teacher`;
  - `app/services/invitations.py`: the registry and `_accept_once`;
  - `app/services/consent.py`: `set_cutoff`, `erase_personal_data`;
  - `app/services/institutions.py`: `describe_institutions(lock=)`, `count_institution_uses`,
    `create_institution`'s lock and `IntegrityError` handling;
  - `app/services/sessions.py`, `app/services/login.py`, `app/services/rate_limits.py`.
- **Routers**:
  - `app/routers/admin.py`: `ADMIN_TABS`, `render_admin`;
  - `app/routers/admin_teachers.py`: the invite form, `_clean_names`, the sealed `sent` banner,
    `RepeatedField`;
  - `app/routers/admin_institutions.py`: confirmations and Post/Redirect/Get;
  - `app/routers/profile.py`.
- **Migration**: `migrations/versions/2026_10_15_f3bd41a67737_create_consent_and_teachers.py`, a
  schema plus a published consent text constant.
- **Tests**:
  - `tests/conftest.py`: `make_institution`, `invite`, `accept`, `invite_and_accept`, `client_as`;
  - `tests/integration/test_teacher_invitation.py`, `test_invitation_refusals.py`,
    `test_admin_teachers.py`;
  - `test_routes.py`, `test_access_control.py`, `test_consent_privacy.py`, `test_migrations.py`.

**Rules for every task** (plan Constraints, FR-055–FR-057):

- **Logging**: services log ids and counts only, never an email, a name, a token or a URL.
- **Writes**: every change is a `POST` through the existing cross-site check, answering `303` on
  success.
- **Form values**: read as plain strings (`Form("")`, `Query(None)`), so a bad value never produces
  FastAPI's 422 JSON.
- **SQL**: no engine-specific SQL. Keys and sorting in Python; `with_for_update` (a no-op on
  SQLite).
- **No script**: no JavaScript, no HTMX.
- **Teacher area**: every route is `@allow_roles(Role.TEACHER)`. Every object it names is checked
  through `app/services/teacher_access.py`. `NotReachable` and `WriteRequired` become
  `raise AccessDenied(Role.TEACHER)`, the milestone 5 403 page.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US9)

---

## Phase 1: Setup (Pure schemas)

**Purpose**: the pure building blocks. Nothing here touches the database. No dependency is added
(plan Technical Context).

- [ ] T001 [P] Create `app/schemas/classes.py` per contracts/services.md §`app/schemas/classes.py` and research D8:
  - constants `YEAR_MIN = 1`, `YEAR_MAX = 12`, and `INVALID_YEAR = "Enter a year of study from 1 to 12."`;
  - `class InvalidYear(ValueError)` with a `.message`, like `app.schemas.names.InvalidName`;
  - `parse_year_of_study(raw: str) -> int`: strip; the value must be non-empty, `isascii()` and `isdigit()`, then `int()` within 1–12; else `InvalidYear(INVALID_YEAR)`. `"02"` → 2.
  - The module docstring says class **names** reuse `app.schemas.names.clean_name` / `name_key` (FR-002).
- [ ] T002 [P] Create `tests/unit/test_class_schemas.py`:
  - accepted: `"1"`, `"12"`, `" 7 "`, `"02"` (→ 2);
  - refused with `INVALID_YEAR`: `""`, `"   "`, `"0"`, `"13"`, `"2.5"`, `"+2"`, `"-1"`, `"two"`, `"٢"` (Arabic-Indic digit), `"1e1"`;
  - the message is exactly the constant (depends on T001).
- [ ] T003 [P] Create `app/schemas/students.py` with `@dataclass(frozen=True) class StudentDetails: institution_id: int; class_id: int`. The docstring says what a student invitation grants besides the role (research D9).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the tables, the migration, the chain rule, usable roles, teacher reach and the test
helpers (plan Implementation Order steps 1–2).

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite (milestones 1–8) must be green at its end (SC-010).

### 2a. Tables and the migration

- [ ] T004 [P] Create `app/models/school_class.py` with `class SchoolClass(SQLModel, table=True)`, `__tablename__ = "classes"`, per data-model.md §1:
  - **Columns**:
    - `id: int | None` primary key;
    - `institution_id: int = Field(foreign_key="institutions.id", nullable=False)`: "Set at creation, never changed (FR-003)";
    - `name` `String(NAME_MAX_LENGTH)` NOT NULL;
    - `name_key` `String(NAME_KEY_MAX_LENGTH)` NOT NULL;
    - `year_of_study: int` NOT NULL;
    - `is_active: bool = True` NOT NULL;
    - `created_at` and `updated_at`, `UTCDateTime`, NOT NULL, `default_factory=utc_now`.
  - **Table args**:
    - `UniqueConstraint("institution_id", "name_key", name="uq_classes_institution_id_name_key")`;
    - `CheckConstraint("year_of_study BETWEEN 1 AND 12", name="year_of_study")`.
  - **Docstring** in the style of `app/models/institution.py`:
    - not personal data;
    - unique within the institution, ignoring case, deactivated classes included;
    - "available ⇔ class, institution and region active, computed by `app.services.availability`";
    - cannot be deleted while it holds a student.
  - Import `app.core.db` for the naming convention, as the other models do.
- [ ] T005 [P] Create `app/models/enrolment.py` with `class Enrolment(SQLModel, table=True)`, `__tablename__ = "enrolments"`, per data-model.md §2:
  - **Columns**:
    - `user_id: int = Field(foreign_key="users.id", primary_key=True)`: "at most one enrolment per person (FR-008)";
    - `class_id: int = Field(foreign_key="classes.id", index=True, nullable=False)`: "no cascade: a class with an enrolment cannot be deleted";
    - `created_at` and `updated_at`, `UTCDateTime`, NOT NULL. `updated_at` is changed by a move only.
  - **Docstring**:
    - personal data, written only by `STUDENT_INVITATION.grant` and deleted only by `.revoke`;
    - invariant: holds `student` ⇔ row exists, with the test-cast exception (research D2);
    - blocked ⇔ the row exists and its class is unavailable.
- [ ] T006 Export `SchoolClass` and `Enrolment` from `app/models/__init__.py`: the imports and `__all__`, kept sorted. Update the docstrings:
  - `app/models/user.py` and `app/models/user_role.py`: the student role is granted by an accepted student invitation (`STUDENT_INVITATION.grant`), and removed by student removal, withdrawal and data deletion;
  - `app/models/institution.py`: it holds classes, and `count_institution_uses` counts enrolments in its classes (depends on T004, T005).
- [ ] T007 Create `migrations/versions/2026_10_19_<rev>_create_classes_and_enrolments.py`, generating the revision id with `uv run alembic revision -m "create classes and enrolments"`, with `down_revision = "f13dab4dd8ba"`, per data-model.md §7 and research D13, D18:
  - **Upgrade**:
    1. `op.create_table("classes", …)`, with every column, `pk_classes`, the FK `fk_classes_institution_id_institutions`, `uq_classes_institution_id_name_key` and `ck_classes_year_of_study`, all via `op.f(...)` names matching the metadata convention;
    2. `op.create_table("enrolments", …)`, with `pk_enrolments`, FKs to `users` and `classes`, and `op.create_index(op.f("ix_enrolments_class_id"), …)`;
    3. `op.bulk_insert` of the student consent text: `role="student"`, `version=1`, `text=STUDENT_CONSENT_TEXT_V1`, `published_at=STUDENT_CONSENT_TEXT_V1_PUBLISHED_AT = datetime(2026, 10, 19, tzinfo=UTC)`. Use a lightweight `sa.table("consent_texts", …)`, as the milestone 8 migration does.
  - **`STUDENT_CONSENT_TEXT_V1`**: placeholder wording, paragraphs separated by blank lines, in the style of `TEACHER_CONSENT_TEXT_V1`. It covers every research D13 topic and never names a particular institution or class:
    - **What is stored**: email, first and last name, the class with its educational institution and year of study; when the person agreed, to which version, and who invited them.
    - **Why**: to sign in as a student and take part in the institution's competitions.
    - **Who sees it**: the teachers linked to the student's institution, and the student on their profile.
    - **Email delivery**: Resend, as in the teacher text.
    - **Withdrawal**: how to withdraw (**Withdraw consent** or **Delete my data**) and what is erased; the agreement record is kept.
  - The module docstring repeats the "published: never edit" warning of the milestone 8 migration.
  - **Downgrade**: delete the `('student', 1)` consent text row, drop the index, drop `enrolments`, drop `classes`.
  - Depends on T004, T005.
- [ ] T008 [P] Update `tests/integration/test_migrations.py`: `APPLICATION_TABLES` += `"classes"` and `"enrolments"`. The existing stairway, empty→head and drift tests must pass on both engines. Add a test that after `upgrade head` exactly one `consent_texts` row has `role = 'student'`, with version 1 (depends on T007).
- [ ] T009 [P] Update `tests/unit/test_consent_texts.py`: add `("student", 1): "<sha256>"` to `PUBLISHED`. Compute the hash from the constant once, after T007 is final. Add a test that the student v1 text contains neither "Kyiv" nor any `{`/`}` placeholder, and says "class" and "year of study" (FR-039) (depends on T007).

### 2b. The chain rule and usable roles

- [ ] T010 Create `app/services/availability.py` per contracts/services.md §`app/services/availability.py` and research D2–D4. It imports only `app.models` and `app.services.users`. The module docstring states the chain rule, that statuses are never cascaded, and the test-cast exception.
  - **Functions**:
    - `is_student_blocked(session, user_id) -> bool`: one query, `Enrolment` ⋈ `SchoolClass` ⋈ `Institution` ⋈ `Region` on `user_id`; `True` if a row exists and any of the three `is_active` is false.
    - `usable_roles(session, user_id) -> tuple[Role, ...]`: `get_roles` minus `Role.STUDENT` when blocked; fixed order.
    - `get_signable_user_by_email(session, email) -> User | None`: `get_active_user_by_email`, then `None` unless `usable_roles` is non-empty.
    - `class_is_available(session, class_id, lock=False) -> bool`: the class, institution and region read in one statement; with `lock`, `.with_for_update(read=True)`.
    - `sign_out_students_below(session, *, region_id=None, institution_id=None, class_id=None) -> int`:
      - asserts exactly one keyword is given;
      - builds the subquery of `Enrolment.user_id` joined to `SchoolClass` (and `Institution` for a region);
      - runs `delete(UserSession).where(col(UserSession.user_id).in_(subquery))` and returns `rowcount`;
      - does not commit.
  - Nothing logs here; callers log.
- [ ] T011 Update `app/services/sessions.py` per research D3:
  - **`get_session_identity`**:
    - after computing `held`, if `Role.STUDENT in held and is_student_blocked(session, user.id)`, remove it from `held`;
    - if `held` is then empty, delete this session and return `None`;
    - the existing "stored role not in held → delete session, return `None`" branch now also covers a blocked student's `student` current role.
  - **`start_session`**: use `usable_roles` instead of `get_roles`.
  - Update both docstrings (rows G1–G6 note: a held but unusable role counts as not held).
  - Depends on T010.
- [ ] T012 Update `app/services/login.py`: `verify_code` and `deliver_login_code` call `availability.get_signable_user_by_email` instead of `users.get_active_user_by_email`. Docstrings: "a blocked student with no other role is treated as an unknown address (milestone 9 research D3)". Keep `users.get_active_user_by_email`; `tests/conftest.py` uses it (depends on T010).
- [ ] T013 [P] Create `tests/integration/test_availability_service.py`. Seed region → institution → class → enrolment and a session row directly through the models (test-only):
  - `is_student_blocked` is false while all are active, and true when each of the three is deactivated in turn;
  - a person with no enrolment is never blocked;
  - `usable_roles` drops only the student role;
  - `get_signable_user_by_email` returns `None` for a blocked student-only person, and the user for a blocked teacher-and-student;
  - `sign_out_students_below` deletes exactly the sessions of the people below the given region, institution or class, leaves others (including a teacher's) untouched, and returns the count;
  - `get_session_identity` deletes a blocked student's student-role session, and keeps a blocked teacher-and-student's teacher-role session with `roles == (Role.TEACHER,)`.

  Depends on T010, T011.

### 2c. Teacher reach

- [ ] T014 Create `app/services/teacher_access.py` per contracts/services.md §`app/services/teacher_access.py` and research D5:
  - **Types**:
    - `class NotReachable(LookupError)`;
    - `class WriteRequired(PermissionError)`;
    - `@dataclass(frozen=True) class ReachableInstitution` with `id`, `name`, `region_id`, `region_name`, `access_level: AccessLevel`, `label` (`f"{name} — {access_level.label}"`), and a `can_write` property.
  - **Lookups**:
    - `list_reachable_institutions(session, teacher_id)`: `TeacherInstitution` ⋈ `Institution` ⋈ `Region`, where both are active; sorted by `(region.name_key, institution.name_key, id)` in Python.
    - `reachable_regions(institutions) -> list[tuple[int, str]]`: pure; distinct regions sorted by `(name.casefold(), id)`.
  - **Reach checks**:
    - `reach_institution(session, teacher_id, institution_id, *, region_id=None, write=False, lock=False)`:
      - one statement for the link, the institution and the region; with `lock`, `.with_for_update(read=True)`;
      - `NotReachable` if missing, inactive, or `region_id` given and different;
      - `WriteRequired` if `write` and the level is Read.
    - `reach_class(session, teacher_id, class_id, *, institution_id=None, write=False, lock=False) -> tuple[ReachableInstitution, SchoolClass]`:
      - loads the class (with `lock`: `session.get(SchoolClass, id, with_for_update=True, populate_existing=True)`);
      - `NotReachable` if unknown or not in `institution_id`;
      - then `reach_institution` for its institution.
    - `reach_student(session, teacher_id, user_id, *, write=False, lock=False) -> tuple[ReachableInstitution, SchoolClass, User]`:
      - with `lock`, the user row is locked `FOR UPDATE` first;
      - then requires `Role.STUDENT` held, an `Enrolment`, and `class_is_available`;
      - then `reach_class` for the enrolment's class.
  - **On refusal**: every function rolls back before raising when `lock` is set, so no lock outlives a refusal (the `teachers._current_teacher` pattern).
  - **Docstring**: the module says reach is the only authority for teacher scope (Constitution IV, FR-021, FR-022), and that unknown and unreachable are deliberately indistinguishable.
  - Depends on T004, T005, T010.
- [ ] T015 [P] Create `tests/integration/test_teacher_access_service.py`, with a teacher made through the real invitation services (Write to A in Kyiv, Read to B in Lviv) and rows seeded directly for classes and enrolments:
  - **Listing**: `list_reachable_institutions` lists A and B with their levels and leaves out C (not linked); A disappears when A or Kyiv is deactivated.
  - **`reach_institution`**: refuses B with `write=True` (`WriteRequired`), C, unknown ids, and A with the wrong `region_id` (`NotReachable`).
  - **`reach_class`**: accepts a deactivated class of A, and refuses a class of C or a mismatched `institution_id`.
  - **`reach_student`**: refuses a student of a deactivated class, someone without the student role, and an unknown id.

  Depends on T014 and T016.

### 2d. Test helpers

- [ ] T016 Extend `tests/conftest.py` (keep the cast unchanged; research D2):
  - **`make_class(engine, institution_id, name="KN-21", year=2, active=True) -> int`**: inserts a `SchoolClass` row directly (test-only; classes are not personal data), computing `name_key` with `app.schemas.names.name_key`, and returns its id.
  - **`make_teacher(engine, settings, *, email, institutions: Mapping[int, AccessLevel], first="Olena", last="Kovalenko") -> int`**: a thin wrapper over `invite_and_accept`.
  - **`accept`** gains `role: Role = Role.TEACHER` and uses `current_consent_text(db_session, role)`. Existing callers are unchanged.
- [ ] T017 Run the whole suite: `uv run ruff check .` and `uv run pytest`. Every milestone 1–8 test must pass before Phase 3 (SC-010). Usable roles (T011, T012) must not change any existing sign-in, role-choice or session test, because the cast's directly seeded student roles have no enrolment and stay usable (research D2). Depends on T006–T016.

**Checkpoint**: the foundation is ready. Usable roles are in effect everywhere, and the suite is
green.

---

## Phase 3: User Story 1 — A teacher chooses a class and manages classes (Priority: P1) 🎯 MVP

**Goal**: the teacher area with its two tabs. On **Students**: the three lists with every message,
and class create, edit, deactivate, activate and delete with Write access. Read access shows
everything with no actions.

**Independent Test**: as a teacher with one Write and one Read institution:

- walk the three lists and check every message;
- create, edit, deactivate, activate and delete classes, and check every validation error;
- reload and bookmark the page;
- check that the Read institution shows no actions.

### Tests for User Story 1

- [ ] T018 [P] [US1] Create `tests/integration/test_classes_service.py` for `app/services/classes.py` (T021):
  - **Create**: trims; "KN-21" in two institutions is accepted; "kn-21" in the same institution → `DuplicateClassName` with the stored name, including a deactivated "KN-21" and Cyrillic case pairs ("Клас"/"КЛАС"); invalid names and years are refused with nothing stored.
  - **Update**: a case-only rename succeeds; an unchanged form leaves `updated_at` unchanged; a year change is visible through the enrolment.
  - **Status**: `set_class_active(False)` deletes the sessions of the class's students only, and a second call is a no-op.
  - **Delete**: refuses a class with an enrolment (`ClassInUse.students == 1`), also when the class is deactivated; an empty class is deleted.
  - **Access**: each write with a Read link raises `WriteRequired`; with no link, `NotReachable`.
- [ ] T019 [P] [US1] Create `tests/integration/test_teacher_classes.py` (HTTP; the teacher made with `make_teacher`, Write to "Kyiv Polytechnic Institute" in Kyiv, Read to "Lviv Academy" in Lviv), covering US1-1 to US1-16:
  - **The shell**: `/teacher` → `303 /teacher/students`. The tabs "Students" and "Competitions" are links, with the current one marked `aria-current="page"`. `/teacher/competitions` shows the placeholder sentence.
  - **The empty states**: with nothing selected, Region is enabled, the other two lists are `disabled`, and "Select a region to continue" is shown. A cast teacher with no links sees "You are not linked to any educational institution" and three disabled lists.
  - **Region list**: active regions holding an active linked institution only, sorted ignoring case. It leaves out a region whose only linked institution is deactivated, and a deactivated region.
  - **Institution list**: "Kyiv Polytechnic Institute — Write" and "Select an educational institution to continue".
  - **Class list**:
    - for Write: "Select a class to see its students", and **+ Add class** as the last option (`value="new"`); `class=new` → 303 to the form;
    - for Read: no **+ Add class**, and `class=new` → 403.
  - **Create**: "KN-21" year 2 → 303 to `?region=…&institution=…&class=<id>`, the class selected, and "No students in this class yet".
  - **Validation**: each refusal is a 400 with the message and the values as typed; nothing is stored. The cases: an empty name, 201 characters, a tab, "kn-21" ("already exists in this institution"), and the years 0, 13, 2.5 and empty.
  - **Edit**: name and year both change; a case-only rename succeeds.
  - **Deactivate**: the confirmation page has the FR-052 sentence, and opening it changes nothing. After the `POST`, the bar shows "Deactivated" with **Activate**, no **Add student**, and the FR-054 message. **Activate** restores it.
  - **Delete**: the confirmation names the class and its institution. An empty class is deleted, then the page is selected at the institution with no class. A class with a student gives 409 and "You can deactivate it instead.", but not when the class is already deactivated.
  - **Reload safety**: reloading any result page changes nothing.
  - **Read access**: the Read institution's class has no Edit, Deactivate, Activate, Delete or Add student.

### Implementation for User Story 1

- [ ] T020 [US1] Create `app/routers/teacher.py`, modelled on `app/routers/admin.py`, per research D6 and contracts/http-routes.md §1:
  - **The tabs**: `@dataclass(frozen=True) class TeacherTab(key, label, path)` and `TEACHER_TABS = (TeacherTab("students", "Students", "/teacher/students"), TeacherTab("competitions", "Competitions", "/teacher/competitions"))`.
  - **`render_teacher(request, template, active_tab, context=None, status_code=200)`**: passes `app_name`, `teacher_tabs` and `active_tab`.
  - **`GET /teacher`**: `@allow_roles(*TEACHER_AREA.roles)`, returns `RedirectResponse("/teacher/students", 303)`.
  - **`GET /teacher/competitions`**: `@allow_roles(Role.TEACHER)`, renders `pages/teacher/placeholder.html` with "Competitions" and "Competitions will arrive in a later milestone."
  - **Housekeeping**:
    - remove `teacher_area` from `app/routers/areas.py`, keeping `TEACHER_AREA`, and update that module's docstring as for `ADMIN_AREA`;
    - include `teacher.router` in `app/main.py`, after `areas`;
    - create `app/templates/layouts/teacher.html`, mirroring `layouts/admin.html`, with `nav class="area-tabs"` and `aria-label="Teacher area"`;
    - in `app/static/css/app.css`, make every `.admin-tabs` rule also apply to `.area-tabs` (selector lists), and change `layouts/admin.html` to `class="admin-tabs area-tabs"`;
    - create `app/templates/pages/teacher/placeholder.html`.
- [ ] T021 [US1] Create `app/services/classes.py` per contracts/services.md §`app/services/classes.py` and research D8:
  - **Types**:
    - `DuplicateClassName(existing_name)`, whose `.message` is `f"A class named “{existing_name}” already exists in this institution."`;
    - `ClassInUse(school_class, students)`;
    - `@dataclass(frozen=True) ClassView`, with `label` = `f"{name} · year {year_of_study}"` and `from_row(SchoolClass)`.
  - **Lookups**:
    - `list_classes(session, institution_id)`: sorted by `(name_key, id)`;
    - `count_institution_classes(session, institution_id)`.
  - **Writes**: `create_class`, `update_class`, `set_class_active` and `delete_class`, exactly as the contract table says:
    - each starts with `reach_institution` or `reach_class` with `write=True, lock=True`;
    - names via `clean_name` / `name_key`, years via `parse_year_of_study`;
    - the duplicate lookup excludes the class itself on update;
    - an `IntegrityError` at commit is mapped as in `institutions.create_institution`;
    - `set_class_active(False)` calls `sign_out_students_below(class_id=…)` before the commit;
    - `delete_class` counts `Enrolment` rows of the class after the `FOR UPDATE` lock.
  - **Logging**, one line per change, with ids only: "Class created: id=%d institution_id=%d"; "Class updated", "Class deactivated" and "Class activated" (with the `sessions=%d` count for deactivation); "Class deleted".
- [ ] T022 [US1] Create `app/routers/teacher_students.py` (prefix `/teacher/students`) with the Students page per contracts/http-routes.md §2.1 and research D7:
  - **`GET ""` `students_page(request, session, region: str | None = Query(None), institution: str | None = Query(None), class_: str | None = Query(None, alias="class"), sent: str | None = Query(None))`**:
    - parse each value with a helper `_id(raw)`: `None` for empty, `int` for ASCII digits up to `MAX_ID`, else raise `AccessDenied(Role.TEACHER)`;
    - a child without its parent is denied;
    - resolve through `list_reachable_institutions`, `reach_institution(region_id=…)` and `reach_class(institution_id=…)`;
    - handle `class=new` (303 or 403);
    - render `pages/teacher/students.html` with `regions`, `institutions` (of the selected region), `classes`, the selected objects, `message` (the FR-049 texts as module constants), `students` (empty for now; T030 fills it), `can_write` and `sent_to`.
  - **`selection_path(region_id, institution_id, class_id=None) -> str`**: builds the canonical query, and is used by every redirect in this module.
  - **`_denied()`**: raises `AccessDenied(Role.TEACHER)`.
  - **Wiring**: include the router in `app/main.py`.
  - **The module docstring** cites research D5 and D7, and the "every route is `@allow_roles(Role.TEACHER)`" rule.
- [ ] T023 [US1] Create `app/templates/pages/teacher/students.html` (extends `layouts/teacher.html`):
  - **The list row**: `<div class="class-picker">` holding three `<form method="get" action="/teacher/students">`.
    - Each form has a labelled `<select>`; the first option is a placeholder with `value=""`.
    - The Institution form carries a hidden `region`; the Class form carries hidden `region` and `institution`.
    - Each form has a **Show** submit button.
    - A select and its button are `disabled` until the previous level is selected, or always when there is no reachable institution.
  - **The options**: institutions show the "Name — Write" label; classes show `ClassView.label` plus " (deactivated)"; **+ Add class** (`value="new"`) is last, only with `can_write`.
  - **Messages**: the `message` paragraph, an "Invitation sent to …" banner when `sent_to` is set, and the class bar (FR-051) for a selected class.
  - **Class bar actions**, Write only, carrying the selection: **Edit**, **Deactivate** (link), **Activate** (form `POST`), **Delete** (link), and **Add student** only when the class is active.
  - **Below the bar**: the FR-054 student area with the empty and deactivated messages.

  In `app/static/css/app.css`, add `.class-picker`: a grid of three columns at ≥ 768px, one column below, with the gap matching `.institutions-layout`.
- [ ] T024 [US1] Add the class form and confirmation routes to `app/routers/teacher_students.py` per contracts/http-routes.md §2.2:
  - **The routes**: `GET /institutions/{institution_id:int}/classes/new`, `POST /institutions/{institution_id:int}/classes`, `GET`/`POST /classes/{class_id:int}/edit`, `GET`/`POST /classes/{class_id:int}/deactivate`, `POST /classes/{class_id:int}/activate`, and `GET`/`POST /classes/{class_id:int}/delete`.
  - **Every `GET`** resolves with `reach_institution` / `reach_class(write=True)`, so Read and unreachable give 403.
  - **Every `POST`** calls the T021 service and maps the outcomes:
    - `NotReachable` / `WriteRequired` → `AccessDenied`;
    - `InvalidName`, `InvalidYear` and `DuplicateClassName` → 400, with the form showing every error and the values as typed;
    - `ClassInUse` → 409, the delete page in its refused state;
    - success → 303 to `selection_path(...)`: the created or affected class selected, or no class after a delete.
  - **Form fields**: only `name` and `year_of_study` are read (`Form("")`).
  - **Templates**, extending `layouts/teacher.html`:
    - `app/templates/pages/teacher/class_form.html`: heading, name and year (`type="number" min="1" max="12" step="1"`) inputs, per-field errors, and **Save** / **Cancel**;
    - `class_deactivate.html`: the FR-052 sentence, a **Deactivate** button and **Cancel**;
    - `class_delete.html`: names the class and its institution; in the refused state, "“{name}” has students and cannot be deleted.", plus "You can deactivate it instead." and a link to the deactivate confirmation only when `is_active`.
- [ ] T025 [US1] Update the route tests for the new teacher area:
  - **`tests/integration/test_routes.py`**:
    - add the five class `POST` routes to `test_the_write_routes_are_exact`;
    - compute `TEACHER_SCOPED_PATHS` = declared `GET` paths starting with `/teacher/students/` that contain `{`;
    - in `test_every_declared_page_admits_exactly_its_roles`, skip only the allowed-role branch for those paths (research D17), keeping the denied-role assertion for every path;
    - add a docstring line pointing to `test_teacher_access.py`.
  - **`tests/integration/test_access_control.py`**: remove `/teacher` from `PLACEHOLDER_AREAS`. Wherever the placeholder title is asserted for `/teacher`, assert instead that `GET /teacher` answers 303 to `/teacher/students` and that the followed page shows the "Students" tab. Leave the home-page link table unchanged.

**Checkpoint**: US1 works on its own. A Write teacher manages classes, and a Read teacher only sees
them.

---

## Phase 4: User Story 2 — A teacher invites a student, who accepts (Priority: P1)

**Goal**: the student role joins the milestone 8 invitation flow. A teacher invites into an active
class. Accepting creates the role, the enrolment and the consent record. The student's profile
shows the enrolment.

**Independent Test**:

- as a Write teacher, invite into an active class;
- read the link from the outbox, and check that no table holds the email, the names or an enrolment;
- accept;
- check the user, the role, the enrolment and the record;
- sign in as the student and open the profile.

### Tests for User Story 2

- [ ] T026 [P] [US2] Add the student helpers to `tests/conftest.py`, then create `tests/integration/test_student_invitation.py`.
  - **The helpers**, through the real services; usable once T027 and T028 register the student role:
    - `invite_student(engine, settings, *, email, class_id, inviter_email, first="Taras", last="Shevchenko", now=None) -> str`: looks up the class's institution, calls `issue_invitation(..., Role.STUDENT, ..., StudentDetails(institution_id, class_id))` with a `MemoryEmailSender`, and returns the token;
    - `enrol_student(...) -> int`: `invite_student`, then `accept(..., role=Role.STUDENT)`; returns the user id.
  - **The test module** covers US2-1 to US2-11, FR-026 and FR-027:
  - **The form**: **Add student** opens it, showing the class and the institution.
  - **Sending** a valid form:
    - 303 to the selection with `sent=`; the banner shows the address;
    - the outbox email is plain text and contains the inviter's name and email, "Student", "Kyiv Polytechnic Institute (Kyiv)", "Class: KN-21 · year 2", "Nothing about you is stored unless you accept", the link, and the expiry;
    - no table holds the email or the names (reuse the table-scan helper from `test_consent_privacy.py`, or import it), and `enrolments` is empty.
  - **Validation**: an invalid email or name gives 400 with the values kept, and no email is sent.
  - **Existing students**: an email that already holds the student role, including a blocked one, gives 400 "This email already belongs to a student"; the body names neither the institution nor the class.
  - **Allowed addresses**: a teacher's, an administrator's, and an inactive former student's address can be invited.
  - **Limits**:
    - 100 student invitations by one teacher, then the 101st gives 429 (seed `rate_limit_hits` via `allow` in a loop rather than 100 HTTP posts);
    - 5 to one address, counted across teacher and student invitations, then 429;
    - a teacher who is also an administrator has the 20 teacher invitations counted separately from the 100.
  - **Send failure**: the form comes back with 503 and the values, and the attempt counts.
  - **Acceptance page**: opening the link changes nothing. It shows the inviter, "Student", the email, the names, the institution with its region, the class and its year, the student consent text, and "If you are already a teacher or a student, your current names are kept." (US2-8, FR-038).
  - **I agree**:
    - creates an active user with the invited names, the student role, `Enrolment(user, class)`, and one `ConsentRecord` whose text is student v1;
    - redirects to `/login?prefill=…`;
    - the consent record row has no institution or class column.
  - **Sign-in**: the real code flow (outbox code) starts the session with the student role, and `/profile` shows the email, names, "Student", "Kyiv Polytechnic Institute (Kyiv)", "KN-21", year "2", and the student consent text.

### Implementation for User Story 2

- [ ] T027 [US2] Create `app/services/students.py` with the `InvitableRole` part per contracts/services.md §`STUDENT_INVITATION` and research D9:
  - **`class _StudentInvitation`**, with `role = Role.STUDENT`:
    - `details_to_payload` returns `{"institution": …, "class": …}`;
    - `details_from_payload` accepts a dict with exactly those keys, each a non-bool `int`, and raises `ValueError` otherwise;
    - `inviter_may_invite` requires `inviter.is_active`, `Role.TEACHER in get_roles(...)`, and a `TeacherInstitution` row for the institution with `AccessLevel.WRITE`;
    - `details_acceptable(session, d, lock)` requires the class to exist, `class.institution_id == d.institution_id`, and `class_is_available(session, d.class_id, lock=lock)`;
    - `describe` returns `DetailLine(f"Educational institution: {label}")`, where the label comes from `describe_institutions`, and `DetailLine(f"Class: {ClassView.label}")`;
    - `grant` adds `UserRole(student)` and `Enrolment(user_id, class_id, created_at=now, updated_at=now)`, then flushes;
    - `revoke` deletes the `Enrolment` and the student `UserRole`.
  - **Also**:
    - `STUDENT_INVITATION = _StudentInvitation()`;
    - `NOT_A_NEW_STUDENT = "This email already belongs to a student"`;
    - `is_student_address(session, email) -> bool`.
  - Module docstring in the style of `app/services/teachers.py`.
- [ ] T028 [US2] Update `app/services/invitations.py`:
  - `invitable_roles()` lazily imports `STUDENT_INVITATION` and returns both roles;
  - update the module docstring ("milestone 9 adds the student");
  - the `issue_invitation` log line adds `class_id=%s` (the details' `class_id`, or `-`).

  Also add `BUCKET_INVITE_STUDENT_INVITER = "invite_student_inviter"` and `STUDENT_INVITER_INVITE_LIMIT = 100` to `app/services/rate_limits.py`, with the docstring table row "`invite_student_inviter` | teacher's user id | 100". Depends on T027.
- [ ] T029 [US2] Implement the names rule and its note, per research D10 and FR-036–FR-038. The note promises what the rule does, so they ship together in US2, the MVP.
  - **The rule**, in `app/services/invitations.py` `_accept_once`:
    - compute `keep_names = user is not None and user.is_active and user.first_name is not None and bool({Role.TEACHER, Role.STUDENT} & set(get_roles(session, user.id)))` before granting;
    - write `read.first_name` / `read.last_name` only when `not keep_names`;
    - update the `accept_invitation` docstring (FR-036, a deliberate change to milestone 8 for teacher invitations).
  - **The note**: add "If you are already a teacher or a student, your current names are kept." to `app/templates/pages/invitation.html`, under the details list, for every role (FR-038). Milestone 8's teacher acceptance page shows it too.

- [ ] T030 [US2] Add the student list and the invitation form to `app/routers/teacher_students.py` per contracts/http-routes.md §2.1 and §2.3, and research D11:
  - **The list**: add `list_students(session, class_id) -> list[StudentRow]` to `app/services/students.py`, sorted by `(last.casefold(), first.casefold(), user_id)`. `students_page` passes it for an active selected class.
  - **The routes**: `GET`/`POST /classes/{class_id:int}/invite`. On `POST`, the first failure answers, in this order:
    1. `reach_class(write=True)`, else 403;
    2. the class is active, else 409 and the refusal template;
    3. `clean_email` and the names (reuse `_clean_names` from `admin_teachers.py` by moving it to `app/schemas/people.py` as `clean_person_names(first, last, errors)`, and update `admin_teachers.py` to call it), else 400;
    4. `allow(...)` with `LimitCheck(BUCKET_INVITE_STUDENT_INVITER, str(teacher.id), 100)` and `LimitCheck(BUCKET_INVITE_EMAIL, address, EMAIL_INVITE_LIMIT)`, else 429 `TOO_MANY`;
    5. `is_student_address`, else 400 `NOT_A_NEW_STUDENT`;
    6. `issue_invitation(..., Role.STUDENT, ..., StudentDetails(institution_id, class_id))`, where `EmailDeliveryError` → 503 `NOT_SENT` and `InvalidChoice` → 403;
    7. 303 to `selection_path(...) + "&sent=" + seal(..., "invitation-sent", {"email": address})`.
  - **The banner**: `students_page` reads `sent` through a shared `_sent_to` (import or move it from `admin_teachers.py`).
  - **Templates**:
    - `app/templates/pages/teacher/student_invite.html`: the class and the institution as text; email, first name and last name fields with errors; **Send invitation** and **Cancel**. In the 409 state, the deactivated-class sentence and no form.
    - In `students.html`, the student table: name ("Last First") and email, plus **Edit** / **Remove** links for Write (wired in T036).
  - **Route test**: add `POST /teacher/students/classes/{class_id:int}/invite` to the exact write set in `tests/integration/test_routes.py`.
- [ ] T031 [US2] Show the enrolment on the profile per research D16 and contracts/http-routes.md §4:
  - **The view**: add `@dataclass(frozen=True) EnrolmentView` and `get_enrolment_view(session, user_id)` to `app/services/students.py`, with the label from `describe_institutions` and `is_available` from `class_is_available`.
  - **The route**: in `app/routers/profile.py`, load it when `Role.STUDENT in get_roles(session, person.id)`; a blocked student no longer has it in `request.state.roles`.
  - **The template**, `app/templates/pages/profile.html`:
    - add "Educational institution", "Class" (with " (deactivated)" when not available) and "Year of study";
    - replace the single correction sentence with per-role sentences: "Corrections to student data are made by a teacher of your educational institution." when an enrolment is shown; "Corrections to teacher data are made by an administrator." when `teacher` is shown.
  - Update the module docstring of `profile.py`.

**Checkpoint**: US1 + US2 make the MVP. A teacher creates a class, and a student is invited,
accepts and signs in.

---

## Phase 5: User Story 3 — A student acceptance is refused when the invitation is no longer valid (Priority: P1)

**Goal**: every student-specific refusal at **I agree** works, and stores nothing.

**Independent Test**: create student links, then change the inviter or the class in each way below,
and check that **I agree** is refused with the right message and stores nothing; check the cases
that must still succeed.

### Tests for User Story 3

- [ ] T032 [P] [US3] Create `tests/integration/test_student_invitation_refusals.py`, covering US3-1 to US3-9 and SC-003. Each refusal asserts the milestone 8 neutral message, status 400, and no new `users`, `user_roles`, `enrolments` or `consent_records` rows:
  - **The link**: a tampered token → neutral; an expired one (`now` + 7 days via the service) → "This invitation has expired; ask for a new one."
  - **The inviter**: deactivated, removed as a teacher, unlinked from the institution, or lowered to Read.
  - **The class**: deleted, deactivated, its institution deactivated, or its region deactivated.
  - **Still valid**: the class renamed and its year changed → the page shows the new values, and **I agree** succeeds.
  - **The cut-off**:
    - a link issued before the person was removed as a student (via `remove_student`, T035) or withdrew → refused, whether or not they are still active;
    - a link issued after → succeeds.
  - **Already a student**:
    - accepted twice → "You are already a student.", with one enrolment and one record;
    - two links into different classes → the first wins, and the second shows "already a student".
  - **The consent text changed** between opening and pressing: insert a student v2 row in the test → 409 with the new text and nothing stored.
  - **Extra form fields**: `class_id=999` or `institution_id=…` posted with **I agree** are ignored.
  - **Teacher-only checks**: a student link whose inviter is not an administrator is still accepted (the teacher checks are not applied, US3-9).

### Implementation for User Story 3

- [ ] T033 [US3] Verify `STUDENT_INVITATION.inviter_may_invite` and `details_acceptable` cover every T032 case with no further code. If a case fails, fix it in `app/services/students.py`, never in `app/services/invitations.py`; the generic order of checks is unchanged (FR-024, FR-030). Confirm that `_accept_once` passes `lock=True`, so the class, institution and region are read `FOR SHARE` (FR-035).

**Checkpoint**: US1–US3 work. Old or forged student links cannot enrol anyone.

---

## Phase 6: User Story 4 — A teacher edits and removes students (Priority: P1)

**Goal**: with Write access, a teacher edits names, moves a student within the institution, and
removes a student.

**Independent Test**: with accepted students in place:

- check the list contents and order;
- edit names and class, and check the refused edits;
- remove a student and check the stored result.

### Tests for User Story 4

- [ ] T034 [P] [US4] Create `tests/integration/test_teacher_students.py`, covering US4-1 to US4-8 and the Edge Cases. Students are made with `enrol_student` (T026).
  - **The list**: three students sorted by last name, then first name, ignoring case; name and email shown; Write shows **Edit**/**Remove**, Read shows neither.
  - **Edit**:
    - the page shows the email and the institution as text, and a class select of active classes of the same institution only;
    - saving new names and another active class → both change, the student's existing session still resolves, and no new consent record or cut-off appears;
    - an invalid name → 400;
    - a deactivated class of the same institution → 400 "This class is deactivated.";
    - a class of another institution, an unknown id, or `abc` → 403; nothing changes in any case;
    - after a move, the redirect keeps the class the teacher was viewing selected.
  - **Remove**:
    - the confirmation names the student, the class and the institution;
    - a student-only person → enrolment gone, no student role, cut-off set, `is_active` false, all sessions deleted, email/names/consent records kept;
    - a teacher-and-student keeps the teacher role, stays active, and is signed out everywhere.
  - **Re-invite**: a removed student re-invited with a newer link → a new enrolment and a second consent record.
  - **Stale edit**: a student removed while the Edit is open → saving gives 403.
  - **Self-invite**: a teacher inviting their own address → after acceptance they appear in the list and can be edited and removed like anyone.

### Implementation for User Story 4

- [ ] T035 [US4] Add the management functions to `app/services/students.py` per contracts/services.md and research D12:
  - **Types and lookups**:
    - `CLASS_DEACTIVATED = "This class is deactivated."` and `class ClassNotActive(ValueError)` with a `.message`;
    - `get_student(session, teacher_id, user_id)` through `reach_student`.
  - **`update_student(session, teacher_id, user_id, first_name, last_name, raw_class_id, now=None) -> int`**:
    1. `reach_student(write=True, lock=True)`;
    2. parse `raw_class_id`, where a non-integer → `NotReachable`;
    3. load the target class `FOR SHARE`; if its `institution_id` differs → `NotReachable`; if it is unavailable or inactive → `ClassNotActive`;
    4. write only the changed names (`users.updated_at`) and the changed `class_id` (`enrolments.updated_at`), then commit;
    5. return the class id.

    It never touches sessions or cut-offs. Log "Student updated: user_id=%d moved=%s".
  - **`remove_student(session, settings, teacher_id, user_id, now=None)`**:
    - `reach_student(write=True, lock=True)`;
    - `STUDENT_INVITATION.revoke`;
    - `set_cutoff(..., user.email, Role.STUDENT, now)`;
    - deactivate if `not get_roles(...)`;
    - `end_all_sessions`; commit.

    Log "Student removed: user_id=%d deactivated=%s".
- [ ] T036 [US4] Add `GET`/`POST /{user_id:int}` and `GET`/`POST /{user_id:int}/remove` to `app/routers/teacher_students.py` per contracts/http-routes.md §2.4:
  - **Form fields**: only `first_name`, `last_name` and `class_id` are read (`Form("")`).
  - **The selection**: `region`, `institution` and `class` query values are carried through hidden fields for the redirect; when they are missing or unreachable, the redirect uses the student's class.
  - **Outcomes**:
    - names via `clean_person_names`;
    - `NotReachable` / `WriteRequired` → `AccessDenied`;
    - `ClassNotActive` → 400 with the form;
    - success → 303.
  - **Templates**:
    - `app/templates/pages/teacher/student_form.html`: the email and institution as text; first and last name; a class `<select name="class_id">` of the active classes of the institution, using `list_classes`, filtering `is_active`, and selecting the current one; **Save** / **Cancel**;
    - `student_remove.html`: names the student, the class and the institution, with **Remove** / **Cancel**.
  - **Wiring**:
    - `students.html`: wire **Edit**/**Remove** to these routes, with the selection in the query;
    - add both `POST` routes to the exact write set in `tests/integration/test_routes.py`.

**Checkpoint**: all P1 stories (US1–US4) work. This milestone could ship here, except for the chain
behaviour in the administrator area.

---

## Phase 7: User Story 5 — Deactivation blocks the students below it (Priority: P2)

**Goal**: deactivating a region, an institution or a class signs out and hides every student below
it. Blocked students cannot sign in with the student role, and reactivation restores them. The
administrator confirms region and institution deactivation (FR-017).

**Independent Test**: with students in classes of several institutions and regions:

- deactivate a class, an institution and a region in turn;
- check sign-out, sign-in, the teacher's view, the profile, data deletion and the effect of
  reactivation.

### Tests for User Story 5

- [ ] T037 [P] [US5] Create `tests/integration/test_availability.py` (HTTP, end to end), covering US5-1 to US5-8, SC-005 and the Edge Cases. Use students in two classes of two institutions in two regions.
  - **Signed out at once**: for each level, deactivation through its real route (the teacher route for a class; the admin `POST` for an institution or region) deletes every session of every student below. Those students' next request redirects to `/login`; students elsewhere stay signed in.
  - **Teacher's view**: the teacher no longer sees an unavailable institution in the lists, and its old address gives 403. A deactivated class in an available institution is listed and marked, but its students are hidden, and their Edit/Remove addresses give 403.
  - **No new students**: invite, move into, or accept into an unavailable class is refused.
  - **Reactivation**: the students can sign in with the student role and are listed again. All `is_active` values and enrolments are byte-for-byte unchanged.
  - **Nested statuses**: with the institution reactivated while its class stays deactivated, the students stay blocked.
  - **Quick flip**: a class deactivated and reactivated quickly → the students sign in again, and nothing else changed.
  - **Data deletion**: a blocked student can request **Delete my data**, receives the link, and erasure deletes the enrolment.
- [ ] T038 [P] [US5] Extend `tests/integration/test_login_flow.py`. Each case uses the real code flow and the outbox:
  - **Blocked, student only**: `POST /login` answers exactly as for an unknown address and sends no email; a code issued before the block no longer verifies.
  - **Blocked, also a teacher**: signs in straight into the teacher role (single usable role, no role choice); the header offers no "Student" switch.
  - **After reactivation**: the student-only person signs in as a student.

### Implementation for User Story 5

- [ ] T039 [US5] Update `app/services/regions.py` and `app/services/institutions.py` per research D4:
  - in `set_region_active` and `set_institution_active`, when the status actually changes to `False`, call `sign_out_students_below(session, region_id=…)` (or `institution_id=…`) before `session.commit()`;
  - add `sessions=%d` to the existing log line;
  - update both docstrings ("deactivation signs out the students below; statuses below are untouched").
- [ ] T040 [US5] Add the deactivation confirmations to `app/routers/admin_institutions.py` per research D15 and contracts/http-routes.md §3:
  - **The routes**: `GET /regions/{region_id:int}/deactivate` and `GET /regions/{region_id:int}/institutions/{institution_id:int}/deactivate`, both `@allow_roles(Role.ADMIN)`, with not-found pages as elsewhere; opening them changes nothing.
  - **The templates**:
    - `app/templates/pages/admin/region_deactivate.html`: "Deactivate region “{name}”?" and "Its students will be signed out and hidden until it is activated again.", a **Deactivate** form posting to the existing route, and **Cancel**;
    - `institution_deactivate.html`: the same, naming the institution and its region.
  - **The list and delete pages**:
    - in `institutions.html`, replace both **Deactivate** forms with links to the confirmations; **Activate** stays a form;
    - in `institution_delete.html`, the in-use **Deactivate** offer becomes a link to the confirmation.
- [ ] T041 [US5] Update `tests/integration/test_admin_institutions.py`:
  - every assertion of a direct `<form method="post" action="…/deactivate">` in the list or the delete page (around lines 548, 627, 748 and 918) now asserts the link `href="…/deactivate"`;
  - the "no deactivate offered" assertions are unchanged;
  - add tests: each confirmation page shows the FR-017 sentence and changes nothing; its button posts to the unchanged route; anonymous, teacher and student are refused as for the other admin pages.

**Checkpoint**: the chain works at every level, and the administrator is warned before blocking
students.

---

## Phase 8: User Story 6 — Names already held are kept on acceptance (Priority: P2)

**Goal**: a person who already holds the teacher or the student role keeps their names when
accepting any invitation (FR-036–FR-038).

**Independent Test**: accept student and teacher invitations for each kind of person, and check
which names are stored and which roles result.

### Tests for User Story 6

- [ ] T042 [P] [US6] Create `tests/integration/test_names_on_acceptance.py`, covering US6-1 to US6-4 and SC-007:
  - **A teacher** (real, with names "Olena Kovalenko") accepts a student invitation for "O. Kovalenko" → names unchanged, roles `(TEACHER, STUDENT)`, enrolment created.
  - **A student** (real) accepts a teacher invitation with other names → names unchanged, roles `(TEACHER, STUDENT)`, teacher links created.
  - **Invitation names stored**: a new person, a removed (inactive) former teacher, and an administrator with neither role each get the invitation's names.
  - **The note**: both roles' acceptance pages contain "If you are already a teacher or a student, your current names are kept."

### Implementation for User Story 6

- [ ] T043 [US6] Verify that the names rule and the note from T029 cover every T042 case with no further code. If a case fails, fix it in `app/services/invitations.py` `_accept_once` only; the rule is research D10, and nothing else in the generic flow changes (FR-024).

**Checkpoint**: people who hold both roles keep one stable name.

---

## Phase 9: User Story 7 — A student sees their profile and withdraws consent (Priority: P2)

**Goal**: the profile shows the enrolment and the right correction notes. Withdrawal and data
deletion remove the enrolment with the rest.

**Independent Test**: sign in as a student, open the profile, and withdraw; check the result. Repeat
through **Delete my data** without signing in.

### Tests for User Story 7

- [ ] T044 [P] [US7] Extend `tests/integration/test_profile.py`, covering US7-1 to US7-4 and US5-3:
  - **A student**: the profile shows the email, names, "Student", the institution with its region, the class, the year, the student record with its text, and the student correction note.
  - **A teacher-and-student**: both notes.
  - **Withdrawal** as a student:
    - the names are cleared, the email becomes `erased-<id>`, there is no student role and no enrolment;
    - the consent records are kept, all sessions are deleted, and the student cut-off is set;
    - the teacher's list no longer shows them.
  - **Teacher-and-student withdrawal**: both roles and their details are removed.
  - **Blocked teacher-and-student**: the profile shows the enrolment marked "(deactivated)", and "Student" is not in the roles line.

  Extend `tests/integration/test_data_deletion.py` with a student who deletes their data through the emailed link: enrolment deleted, the same erasure as a withdrawal.

### Implementation for User Story 7

- [ ] T045 [US7] Verify that `app/services/consent.py` needs no change: `erase_personal_data` and `describe_erasure` already iterate the registry, which now includes the student (contracts/services.md §consent). Make sure `app/templates/pages/profile_withdraw.html` lists "Student" among the roles to remove. Fix only what T044 shows missing.

**Checkpoint**: the milestone 8 rights apply to students unchanged.

---

## Phase 10: User Story 8 — An administrator deletes an institution that holds classes (Priority: P3)

**Goal**: empty classes no longer block deleting an institution and are deleted with it. Enrolled
students do block it.

**Independent Test**: delete institutions with no classes, with empty classes, with an enrolled
student, and with a teacher link, and check each outcome.

### Tests for User Story 8

- [ ] T046 [P] [US8] Extend `tests/integration/test_institution_service.py` and `tests/integration/test_admin_institutions.py`, covering US8-1 to US8-3:
  - **Empty classes**: an institution with two empty classes and no links → the confirmation page says "Its 2 classes will be deleted too."; after `POST`, the institution and both class rows are gone.
  - **Enrolled student**: one enrolled student, also when the class is deactivated (a blocked student) → 409 "in use", and nothing deleted.
  - **Teacher link**: still refused.
  - **`count_institution_uses`**: counts links plus enrolments.

### Implementation for User Story 8

- [ ] T047 [US8] Update `app/services/institutions.py` per research D14:
  - **`count_institution_uses`**: adds `select(func.count()).select_from(Enrolment).join(SchoolClass, …).where(SchoolClass.institution_id == institution_id)`; update its docstring, since milestone 9's count is now here.
  - **`delete_institution`**: after the zero-uses check, `session.execute(delete(SchoolClass).where(col(SchoolClass.institution_id) == institution_id))`, then delete the institution, in one commit. The existing `IntegrityError` → `InstitutionInUse` mapping stays.
  - **The confirmation**: `app/routers/admin_institutions.py` passes `classes=count_institution_classes(...)` to `institution_delete.html`, which shows "Its N classes will be deleted too." when N > 0 (FR-007).

**Checkpoint**: institution deletion follows the new in-use rule.

---

## Phase 11: User Story 9 — Only the right people reach each page (Priority: P3)

**Goal**: every new page and action refuses the wrong roles, unreachable objects and Read-only
management, including through hand-made addresses and forms.

**Independent Test**: for each role, an anonymous visitor, and teachers with Write, Read and no link
to an institution:

- request every new page and submit every new form, including hand-made addresses and form values;
- check the outcome.

### Tests for User Story 9

- [ ] T048 [US9] Create `tests/integration/test_teacher_access.py`, covering US9-1 to US9-5, FR-021–FR-023, SC-004 and research D17:
  - **The route-table sweep**: `test_every_teacher_page_admits_a_write_teacher` iterates every declared `GET` route starting with `/teacher`, using `iter_routes` from `tests/integration/test_routes.py` (import it). It substitutes `{institution_id}`, `{class_id}` and `{user_id}` with a real Write-reachable institution, active class and enrolled student, then asserts the status is not 403 for the Write teacher. For every management page (all teacher pages except `/teacher`, `/teacher/students` and `/teacher/competitions`), it asserts 403 for a Read teacher of that institution and for an unlinked teacher.
  - **Writes**: for every teacher `POST` route (from the route table), the Read teacher, an unlinked teacher, an administrator, a student, and an administrator-and-student using the student role each get 403. A snapshot of `classes`, `enrolments`, `users`, `user_roles` and `consent_records` is equal before and after. Anonymous → `303 /login`.
  - **Hand-made addresses**, each 403:
    - `?region=<other region>&institution=<A>`;
    - `?institution=<A>` without a region;
    - `?class=<class of B>` under A;
    - `?region=abc`;
    - an unknown class id;
    - the student Edit of a student in a deactivated class;
    - `class_id=<class of another institution>` in a student edit form.
  - **Lowered access**: a Write teacher opens the class edit form; the administrator lowers the link to Read (through `update_teacher`); the save → 403, and nothing changed. The same after the link is removed.
  - **Administrators**: the administrator area pages contain no link to any `/teacher/students` page (FR-020).

### Implementation for User Story 9

- [ ] T049 [US9] Fix any route in `app/routers/teacher_students.py` or `app/routers/teacher.py` that T048 shows answering other than 403, or changing data, for an unreachable or Read-only request. Confirm `test_the_write_routes_are_exact` in `tests/integration/test_routes.py` lists exactly the 8 new teacher `POST` routes, and that `PUBLIC_ROUTES` is unchanged. Add a cross-site class create and a cross-site student invite to `tests/integration/test_cross_site.py`: refused, and nothing stored (FR-055).

**Checkpoint**: all user stories are independently functional and access-tested.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: privacy checks, documentation and the final walk-through.

- [ ] T050 [P] Extend `tests/integration/test_consent_privacy.py` for SC-002 and SC-008:
  - before a student acceptance, the all-tables scan finds neither the invited student's email nor names, and `enrolments` has no row;
  - the log capture covers the new flows: class create, edit, deactivate and delete; student invite, accept, edit, move and remove; region and institution deactivation with sign-out; blocked sign-in;
  - no captured line contains an email, a first or last name, `/invitations/` followed by a token, or a deletion link.
- [ ] T051 [P] Update `README.md`:
  - the roles section: students come only from a teacher's invitation;
  - a short "Teacher area" section: Students tab, classes, inviting students, Read vs Write;
  - the deactivation chain in one paragraph;
  - the layout section: the new modules `availability`, `teacher_access`, `classes`, `students`, `teacher.py`, `teacher_students.py`.
- [ ] T052 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`, on SQLite and, when available, PostgreSQL (`TEST_POSTGRES_URL`). Fix every failure. Every milestone 1–8 test must still pass, apart from the teacher placeholder tests replaced in T025 (SC-010).
- [ ] T053 Walk through [quickstart.md](./quickstart.md) §2 manually in a browser, including phone width (the three lists stack). Record any deviation as a fix, not a note.
- [ ] T054 On delivery, move milestone 9 in `docs/requirements/milestones.md` from "Upcoming" to "Delivered" as a short product-only summary linking to `specs/009-classes-students-management/spec.md`, as was done for milestones 1–8.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001 is used from US1 (T021); T003 from US2 (T027).
- **Foundational (Phase 2)**: can start at once (it does not need Phase 1). It blocks every story. T017 ends with the full suite green.
- **US1 (Phase 3)**: depends on Phase 2.
- **US2 (Phase 4)**: depends on Phase 2. It also needs US1's `teacher_students.py` page, the `selection_path` helper and `classes.py` (T021, T022), because the invite form lives on the Students tab. Its service work (T027, T028) can start in parallel with US1.
- **US3 (Phase 5)**: depends on US2 (T027, T028). Its cut-off case needs `remove_student` (T035, US4); write that test last, or mark it until T035 is done.
- **US4 (Phase 6)**: depends on US2: real students come only from acceptance.
- **US5 (Phase 7)**: depends on US1 (class deactivation route) and US2 (students exist). T039–T041 are independent of US3 and US4.
- **US6 (Phase 8)**: depends on US2 (a student invitation exists).
- **US7 (Phase 9)**: depends on US2 (T031, the profile) and US4 (removal, for the teacher-list check).
- **US8 (Phase 10)**: depends on Phase 2 only, plus US2's helpers for an enrolled student.
- **US9 (Phase 11)**: depends on every route existing (US1, US2, US4, US5).
- **Polish (Phase 12)**: depends on all stories.

### Story completion order

US1 → US2 → (US3 ∥ US4) → (US5 ∥ US6 ∥ US8) → US7 → US9 → Polish

### Within each story

- Write the tests first, and see them fail for the right reason.
- Then services, then routes, then templates.
- Update `tests/integration/test_routes.py`'s exact write set in the same task that adds a `POST`
  route, so the suite stays green after every task.

### Parallel Opportunities

- **Phase 1**: T001, T002 and T003, which are different files.
- **Phase 2**:
  - T004 ∥ T005 (models);
  - T008 ∥ T009 after T007;
  - T013 ∥ T014 after T010 and T011;
  - T015 after T014 and T016;
  - T016 ∥ T010–T014 (a different file).
- **US1**: T018 ∥ T019 (tests) while T020 is written; T021 ∥ T020, which are different files.
- **US2**: T026 (tests) ∥ T027 (service).
- **Across stories**, once US2 is done:
  - T032 (US3 tests);
  - T034 (US4 tests);
  - T037 and T038 (US5 tests);
  - T042 (US6 tests);
  - T046 (US8 tests).

  They are different files and can be written in parallel.
- **Polish**: T050 ∥ T051.

---

## Parallel Example: User Story 1

```text
# Tests first, together:
Task: "T018 [US1] tests/integration/test_classes_service.py"
Task: "T019 [US1] tests/integration/test_teacher_classes.py"

# Then, in parallel (different files):
Task: "T020 [US1] app/routers/teacher.py + layouts/teacher.html + CSS"
Task: "T021 [US1] app/services/classes.py"

# Then, in order (same router module):
Task: "T022 [US1] the Students page in app/routers/teacher_students.py"
Task: "T023 [US1] app/templates/pages/teacher/students.html"
Task: "T024 [US1] the class forms and confirmations"
Task: "T025 [US1] test_routes.py and test_access_control.py"
```

## Parallel Example: after US2

```text
Task: "T032 [US3] tests/integration/test_student_invitation_refusals.py"
Task: "T034 [US4] tests/integration/test_teacher_students.py"
Task: "T037 [US5] tests/integration/test_availability.py"
Task: "T042 [US6] tests/integration/test_names_on_acceptance.py"
Task: "T046 [US8] tests in test_institution_service.py / test_admin_institutions.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1 and Phase 2. The existing suite must be green with usable roles in effect.
2. US1: the teacher area and classes. Validate: a Write teacher manages classes, and a Read teacher
   sees them.
3. US2: invite and accept. Validate the end to end through the outbox, and the profile.
4. **Stop and validate**. A teacher can create a class and bring a student in. This is the
   smallest demonstrable slice.

### Incremental Delivery

1. Add US3 and US4 (P1): the refusals and student management. Every P1 story is now done.
2. Add US5 (the chain and the admin confirmations), US6 (names) and US7 (the profile and
   withdrawal).
3. Add US8 (institution deletion) and US9 (the full access matrix).
4. Polish, then the pull request. The constitution gates: CI green, role-access tests, the
   migration, README.

## Notes

- `[P]` tasks touch different files and do not depend on an unfinished task.
- `teacher_students.py` grows across US1, US2 and US4. Tasks on it are sequential.
- Commit after each task or logical group. Each commit keeps the suite green.
- Never weaken a milestone 1–8 test to make it pass. Only the tests listed in plan.md "Changes to
  existing tests" change, and for the reasons given there.
