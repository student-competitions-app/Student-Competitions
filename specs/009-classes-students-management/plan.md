# Implementation Plan: User Management with Consent — Classes and Students (Milestone 9)

**Branch**: `009-classes-students-management` | **Date**: 2026-10-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-classes-students-management/spec.md`

## Summary

Teachers get a real area. Its **Students** tab lets a teacher:

- pick a region, an institution and a class;
- manage the classes of the institutions where they have Write access;
- invite students into a class through the milestone 8 consent flow;
- edit, move and remove students.

Read access shows the same data with no actions. Deactivating a region, an institution or a class
blocks the students below it until it is activated again.

**Data** (research D1, D18): one migration adds two tables and one text.

- `classes`: per institution, with a name unique ignoring case, a year of study from 1 to 12, and a
  status.
- `enrolments`: one row per student, keyed by `user_id`, pointing to a class.
- Student consent text v1, inserted into `consent_texts`.

**The chain** (D2–D4) is computed, never stored. `app/services/availability.py` is the one place
that decides it.

- A student is blocked when their enrolment's class, institution or region is inactive.
- **Usable roles**: blocked students lose the student role in session lookup, sign-in and the role
  choice. A blocked student with no other role is an unknown address at sign-in.
- **Sign-out**: deactivating any level deletes the sessions of every student below it, in the same
  transaction.

**Teacher scope** (D5): `app/services/teacher_access.py` resolves what a teacher may reach.

- **Reachable**: available, linked institutions; all their classes; and the students of their
  available classes.
- **Where it runs**: inside each class and student service operation, under `FOR SHARE` locks for
  writes.
- **Outcome**: unknown, unreachable and Read-only management all give the same 403 "Access denied".

**The student role** (D9–D11) is the second `InvitableRole` (`STUDENT_INVITATION`), registered
beside the teacher.

- Its inviter check is "an active teacher with Write access to the institution".
- Its detail check is "the class still belongs to it and is available". Its grant and revoke write
  the role row and the enrolment together.
- **Unchanged from milestone 8**: invitation, acceptance, cut-off, erasure and data deletion work
  without change.
- **The only generic change**, the names rule: a person who already holds the teacher or student
  role keeps their names.

The invitation form also refuses addresses that already hold the student role, and has its own
limit of 100 per teacher per hour.

**Pages** (D6, D7, D15):

- **Teacher area**: `app/routers/teacher.py` is the tab shell. `app/routers/teacher_students.py`
  serves the Students tab.
- **Selection in the address**: the selection lives in the query string
  (`?region=&institution=&class=`). Three small `GET` forms change it, each submitted when its
  list changes by one small external script (`app/static/js/auto-submit.js`).
- **Administrator area**: confirmation pages are added before deactivating a region or an
  institution. Deleting an institution now deletes its empty classes, and is refused while a
  student is enrolled.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, Pico.css, SQLModel, Alembic, psycopg 3, python-multipart and
  `cryptography`.
- **No new dependency.** No HTMX and no script yet (research D7).

**Storage**:

- SQLite for local work and tests; PostgreSQL in production (Neon via Render).
- One new Alembic revision, `create_classes_and_enrolments`, on top of `f13dab4dd8ba`.

**Testing**:

- pytest with the FastAPI `TestClient`, on both engines through the `database_url` fixture.
- Invitation links come from the `memory` email backend's outbox.
- New `conftest.py` helpers:
  - `make_class`;
  - `invite_student` and `accept(..., role=…)`;
  - `make_teacher(levels)`: a real teacher, through the invitation services;
  - `enrol_student`: a real student, through invite and accept.

**Target Platform**: Linux container on Render. Any modern browser, including phone width; the
three lists stack on narrow screens.

**Project Type**: Server-rendered web application (a single FastAPI application).

**Performance Goals**: none beyond the defaults.

- Classes number tens per institution, and students about thirty per class.
- Session lookup gains one indexed query, only for people who hold the student role.
- Deactivation signs out with one `DELETE … WHERE user_id IN (subquery)`.

**Constraints**:

- **No personal data, enrolment included, before acceptance** (FR-009, SC-002).
- **No email, name or link in a log line** (FR-057).
- **The same behaviour on SQLite and PostgreSQL** (Principle VII):
  - sorting in Python;
  - locks through SQLAlchemy `with_for_update`, which is a no-op on SQLite.
- **Every change** is a `POST` through the cross-site check and ends in a 303 (FR-055, FR-056).
- **Every teacher route** is `@allow_roles(Role.TEACHER)` and checks scope in the service.

**Scale/Scope**:

- 11 new `GET` routes: 9 in the teacher area and 2 admin confirmations. `/teacher` becomes a
  redirect.
- 8 new `POST` routes.
- 2 new tables and 1 consent text row.
- 4 new service modules: `availability`, `teacher_access`, `classes` and `students`.
- 1 placeholder replaced: the teacher area.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 8 is merged into `main`, and its tables, services and migrations are this branch's base. This milestone is one vertical slice: tables → services → routes → pages → tests. It ends in a demonstrable path: create a class → invite a student → accept → sign in → edit, move or remove → deactivate and reactivate. It does not build Competitions content, bulk upload, pending invitations or any administrator pages for students (FR-059). Competition-side blocking is only noted for milestone 11. | ✅ |
| II. Server-rendered simplicity | Jinja2 pages and plain links and forms. The cascading lists are three `GET` forms, each submitted on change by one small static script with no build step and no HTMX (research D7). There is no new dependency. The new abstractions each have a present need: `availability` serves sessions, sign-in, three deactivation paths and the teacher views; `teacher_access` serves every teacher route; `STUDENT_INVITATION` is the protocol's planned second user. | ✅ |
| III. Test-backed delivery | Every spec story maps to a test module ([quickstart.md](./quickstart.md) §1), including the milestone _Test:_ items: the end-to-end invite through the outbox, no data before acceptance, every refusal, the names rule, the existing-student check, separate limits, the chain at every level, sign-in when blocked, and Read versus Write through addresses and forms. Every new route has allowed and denied tests per role, plus object-scope tests for Write, Read and unlinked teachers (research D17). Email uses the `memory` fake. | ✅ |
| IV. Role-based access & data scoping | Every new route is `@allow_roles(Role.TEACHER)` or `@allow_roles(Role.ADMIN)`, and `PUBLIC_ROUTES` is unchanged. Teachers see and manage only students of the available institutions they are linked to. This is enforced in the service operations, in the same transaction as the write (research D5), not only in templates. Only administrators link teachers and edit institutions (unchanged). Administrators get no class or student pages (FR-020). | ✅ |
| V. Secure authentication & secrets | Sign-in is unchanged except that blocked students count as unknown addresses (research D3). There are no new secrets or settings. The "Invitation sent" banner reuses the sealed notice, so no address appears in a URL. Logs carry ids only (research D19). Every write is behind the cross-site check. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | Two SQLModel models and one Alembic revision. Portable SQL only. Timestamps use `UTCDateTime`. The enrolment's primary key guarantees one per person. A class with students cannot be deleted: the service counts first, with the foreign key as backstop. Institution deletion counts enrolments. No historical results exist yet to protect. | ✅ |
| Workflow gates | The plan lists the role-access tests, the migration, the README update (the teacher area and inviting students) and the milestones document update on delivery. | ✅ |

**Post-design re-check (after Phase 1)**: still all ✅.

- No dependency or configuration is added. `PUBLIC_ROUTES` is unchanged. The write set grows by
  exactly the eight routes in [contracts/http-routes.md](./contracts/http-routes.md).
- The one test-harness change to the milestone 5 sweep (research D17) keeps its denied-role
  assertion for every page. A second sweep, built from the same route table, replaces the allowed
  check for object-scoped teacher pages with real ids. Coverage grows; it does not shrink.
- No engine-specific SQL. `FOR SHARE` and `FOR UPDATE` are SQLAlchemy constructs that are omitted
  on SQLite.

## Project Structure

### Documentation (this feature)

```text
specs/009-classes-students-management/
├── plan.md                         # This file
├── research.md                     # Phase 0: decisions D1–D19
├── data-model.md                   # Phase 1: classes, enrolments, consent text, derived views, payload, migration
├── quickstart.md                   # Phase 1: automated and manual validation, post-deploy check
├── contracts/
│   ├── http-routes.md              # Phase 1: every new and changed route, status and page
│   └── services.md                 # Phase 1: availability, teacher access, classes, students, changed services
├── checklists/requirements.md      # From /speckit-specify
└── tasks.md                        # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── __init__.py                    # CHANGED: export SchoolClass, Enrolment
│   ├── school_class.py                # NEW: SchoolClass (table `classes`)
│   ├── enrolment.py                   # NEW: Enrolment (table `enrolments`)
│   ├── user.py, user_role.py          # CHANGED: docstrings (student role source)
│   └── institution.py                 # CHANGED: docstring (classes, in-use count)
├── schemas/
│   ├── classes.py                     # NEW: parse_year_of_study
│   ├── students.py                    # NEW: StudentDetails
│   └── people.py                      # CHANGED: + clean_person_names (moved from admin_teachers._clean_names)
├── services/
│   ├── availability.py                # NEW: chain rule, usable roles, signable user, sign-out below
│   ├── teacher_access.py              # NEW: reachable institutions/classes/students, Read/Write
│   ├── classes.py                     # NEW: list/create/update/set active/delete, count per institution
│   ├── students.py                    # NEW: STUDENT_INVITATION; list/get/update/remove; enrolment view
│   ├── invitations.py                 # CHANGED: registry + student; names rule; log line
│   ├── sessions.py                    # CHANGED: usable roles in identity and start
│   ├── login.py                       # CHANGED: get_signable_user_by_email
│   ├── rate_limits.py                 # CHANGED: invite_student_inviter bucket (100/h)
│   ├── regions.py                     # CHANGED: deactivation signs out students below
│   └── institutions.py                # CHANGED: same; in-use counts enrolments; delete cascades classes
├── routers/
│   ├── teacher.py                     # NEW: TEACHER_TABS, render_teacher, /teacher, /teacher/competitions
│   ├── teacher_students.py            # NEW: the Students tab, classes, invite, student edit/remove
│   ├── areas.py                       # CHANGED: teacher placeholder handler removed (declaration kept)
│   ├── admin_institutions.py          # CHANGED: two deactivate confirmations; delete page class count
│   ├── admin_teachers.py              # CHANGED: uses clean_person_names; shares the "Invitation sent" reader
│   └── profile.py                     # CHANGED: enrolment view, student correction note
├── main.py                            # CHANGED: include the two teacher routers
├── static/css/app.css                 # CHANGED: .area-tabs shared with admin; .class-picker row/stack
└── templates/
    ├── layouts/admin.html             # CHANGED: tab class `area-tabs` (alongside `admin-tabs`)
    ├── layouts/teacher.html           # NEW
    ├── pages/teacher/
    │   ├── students.html              # NEW: three lists, message, class bar, student list, banner
    │   ├── class_form.html            # NEW: create and edit
    │   ├── class_deactivate.html      # NEW: confirmation
    │   ├── class_delete.html          # NEW: confirmation and refusal
    │   ├── student_invite.html        # NEW: form, deactivated-class refusal
    │   ├── student_form.html          # NEW: edit and move
    │   ├── student_remove.html        # NEW: confirmation
    │   └── placeholder.html           # NEW: Competitions
    ├── pages/admin/
    │   ├── region_deactivate.html     # NEW
    │   ├── institution_deactivate.html  # NEW
    │   ├── institutions.html          # CHANGED: Deactivate → confirmation link
    │   └── institution_delete.html    # CHANGED: "classes will be deleted too"; Deactivate link
    ├── pages/profile.html             # CHANGED: enrolment, notes per role
    └── pages/invitation.html          # CHANGED: names note

migrations/versions/
└── 2026_10_xx_<rev>_create_classes_and_enrolments.py   # NEW: two tables + student consent text v1

tests/
├── conftest.py                        # CHANGED: make_class, make_teacher, invite_student, accept(role=), enrol_student
├── unit/
│   ├── test_class_schemas.py          # NEW
│   └── test_consent_texts.py          # CHANGED: student v1 pinned
└── integration/
    ├── test_availability_service.py   # NEW (chain rule, usable roles, sign-out below)
    ├── test_teacher_access_service.py # NEW (teacher reach)
    ├── test_classes_service.py        # NEW (class service, US1)
    ├── test_availability.py           # NEW (US5)
    ├── test_teacher_classes.py        # NEW (US1)
    ├── test_student_invitation.py     # NEW (US2)
    ├── test_student_invitation_refusals.py  # NEW (US3)
    ├── test_teacher_students.py       # NEW (US4)
    ├── test_names_on_acceptance.py    # NEW (US6)
    ├── test_teacher_access.py         # NEW (US9)
    ├── test_profile.py                # CHANGED (US7)
    ├── test_data_deletion.py          # CHANGED (US7: a student deletes their data)
    ├── test_login_flow.py             # CHANGED (blocked sign-in)
    ├── test_admin_institutions.py     # CHANGED (confirmations, US8)
    ├── test_institution_service.py    # CHANGED (enrolments in use, classes deleted)
    ├── test_access_control.py         # CHANGED (/teacher no longer a placeholder)
    ├── test_routes.py                 # CHANGED (writes +8, sweep, research D17)
    ├── test_consent_privacy.py        # CHANGED (student flow)
    ├── test_cross_site.py             # CHANGED
    └── test_migrations.py             # CHANGED (+2 tables)

README.md                              # CHANGED: teacher area, inviting students, roles
docs/requirements/milestones.md        # CHANGED on delivery: milestone 9 moves to "Delivered"
```

**Structure Decision**: the existing single-application layout from the constitution, with no new
top-level directories.

- **Routers**: one router module per area or tab, as in milestones 6–8.
- **Services**: the chain rule (`availability`) and teacher scope (`teacher_access`) are their own
  modules, because sessions, sign-in, the administrator's deactivations and every teacher route all
  depend on them.
- **The student role** (`students.py`) sits beside the teacher (`teachers.py`), with the same split
  as milestone 8: the generic flow in `invitations.py` and `consent.py`, and the role definitions
  imported lazily by the registry.

### Changes to existing tests (why they change)

| Test | Change | Reason |
|---|---|---|
| `tests/conftest.py` | New helpers through the real services. `accept` takes the role, and the default stays the teacher. The cast is unchanged: its directly seeded student roles have no enrolment and stay usable. | Research D2. SC-010: milestone 5–8 tests keep their cast. |
| `test_routes.py` | `test_the_write_routes_are_exact` += 8. `test_the_allowlist_is_exact` is unchanged. The declared-page sweep skips the allowed-role check only for `TEACHER_SCOPED_PATHS`, which `test_teacher_access.py` covers with real ids. | Research D17: object-level denial is 403 by FR-021. |
| `test_access_control.py` | `/teacher` leaves `PLACEHOLDER_AREAS`. It now answers 303 to `/teacher/students`, whose page shows the tabs. The home-page link list is unchanged. | FR-047; SC-010 allows replacing tests of the teacher placeholder. |
| `test_admin_institutions.py` | Assertions that the list holds a direct `<form … /deactivate>` now expect a link to the confirmation. The in-use refusal's **Deactivate** is a link too. Direct `POST`s are unchanged. | FR-017 (clarified), research D15. |
| `test_institution_service.py` | Added: an enrolled student makes the institution in use; empty classes are deleted with it. | FR-007, research D14. |
| `test_consent_texts.py` | Student v1 pinned. | Research D13. |
| `test_login_flow.py`, `test_profile.py`, `test_data_deletion.py`, `test_consent_privacy.py`, `test_cross_site.py` | Cases added; existing ones unchanged. | Stories 5 and 7; SC-002, SC-008; FR-055. |
| `test_migrations.py` | `APPLICATION_TABLES` += `classes`, `enrolments`. | Research D18. |

## Implementation Order (for /speckit-tasks)

1. **Data**:
   - the models, the migration and the student consent text;
   - `test_migrations` (stairway, drift) and `test_consent_texts`, both green.
2. **Chain foundation** (blocks every story):
   - `availability.py`;
   - the `sessions.py` and `login.py` changes;
   - the `regions.py` and `institutions.py` sign-out hooks.

   The whole existing suite must be green again (SC-010).
3. **Teacher scope and classes**:
   - `schemas/classes.py`, `teacher_access.py` and `classes.py`, with service tests;
   - the `teacher.py` shell and layout;
   - the Students tab with the three lists, messages and class bar;
   - the class forms and confirmations;
   - `test_teacher_classes.py` (US1).
4. **Student invitation** (P1):
   - `schemas/students.py` and `STUDENT_INVITATION`, registered;
   - the names rule and acceptance-page note;
   - the rate-limit bucket;
   - the invite form and route, and the banner;
   - `test_student_invitation.py` and `test_student_invitation_refusals.py` (US2, US3).
5. **Student management** (P1):
   - the student list, edit and move, and remove;
   - `test_teacher_students.py` (US4).
6. **Chain behaviour** (P2):
   - `test_availability.py`;
   - blocked sign-in cases in `test_login_flow.py`;
   - the admin deactivation confirmations (US5).
7. **Names** (P2): `test_names_on_acceptance.py` (US6). No new code is expected after step 4.
8. **Profile** (P2): the enrolment view, the correction notes, and the withdrawal and deletion cases
   (US7).
9. **Institution deletion** (P3):
   - the in-use count, the class cascade, and the confirmation text;
   - the service and route tests (US8).
10. **Access** (P3):
    - `test_teacher_access.py`, the route-table changes and the cross-site cases (US9).
11. **Privacy and polish**:
    - the `test_consent_privacy.py` additions;
    - CSS for the list row and the narrow-screen stack;
    - the README;
    - `ruff`;
    - the manual walk-through ([quickstart.md](./quickstart.md)).

## Complexity Tracking

> No constitution violations. The choices below look like extra complexity, so each one is
> justified.

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| A computed chain (`availability.py`) checked on every session lookup | FR-012 and FR-016: reactivation must restore exactly the statuses below, and a blocked student must lose the student role at once (research D2, D3). | Cascading or storing a `blocked` flag loses each object's own status, and must be rewritten on every change. |
| Signing out every student below a deactivated object, in addition to the per-request check | FR-015 asks for a sign-out "at the moment of the deactivation" (research D4). | The per-request check alone leaves live sessions in the table and the header until the next request. |
| Scope checks inside the class and student services, with `FOR SHARE` locks on writes | Constitution IV requires authorization "on every route and every service operation". FR-022 requires the current access level, even when it changes at the same moment (research D5). | A route dependency runs before the write's transaction, so it cannot hold the lock that makes the check true at commit. |
| Three `GET` forms instead of one, each auto-submitted by a small static script | Choosing an entry must open it at once, with no **Show** button (FR-048, research D7). | One form would submit stale lower selections and hit "access denied". An inline `onchange` handler would block a later `script-src 'self'` CSP. |
| A second, route-table-driven access sweep for object-scoped teacher pages | FR-021 makes unknown ids "access denied" (403), which the milestone 5 sweep reads as a role denial (research D17). | Using 404 for unknown objects contradicts FR-021 and lets teachers probe for ids. Dropping the sweep's allowed check without a replacement loses coverage. |
| The student role without an enrolment counts as usable | It keeps the milestone 5–8 test cast valid (SC-010). The state cannot occur in production, because grant and revoke write both, and nobody holds the student role after milestone 8 (research D2). | Seeding the cast with enrolments creates regions and institutions that break milestone 7 tests that start from empty lists. |
