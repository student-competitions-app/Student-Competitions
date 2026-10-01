# Implementation Plan: Roles and Authorization (Milestone 5)

**Branch**: `005-roles-authorization` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-roles-authorization/spec.md`

## Summary

Add the three roles (administrator, teacher, student) and make every page open only to the roles
it declares, judged by the role the person is **currently** using.

**Who holds which role**: a new `user_roles` table, one row per role held, filled **only** by
reconciliation with three deployment lists on every start: `ADMIN_EMAILS` (existing), and the new
`TEACHER_EMAILS` and `STUDENT_EMAILS`. `reconcile_users` replaces `reconcile_admins`. In one
transaction it creates, reactivates or deactivates people, adds and removes role rows, and
deletes every session of anyone who lost any role. It is idempotent, safe under concurrent starts
(unique constraints plus one retry, as before), and logs counts only. Invariant: active ⇔ at least
one role, so milestone 4's login code needs no change.

**Current role**: a nullable `sessions.current_role`, so each browser has its own. A correct code
starts a single-role person in their role and sends a multi-role person to `GET /role` (the role
choice). Until a role is chosen, every page except the role choice, logout and the public
allowlist redirects there. `POST /role` both chooses (lands on `next`) and switches from the
header (no `next`, lands on `/`). Every request checks that the current role is still held, ends
the session if not, and silently upgrades milestone 4 sessions of single-role people.

**Access**: each page is marked `@allow_roles(...)`. The existing application-wide dependency
`resolve_access` reads the matched route's marker and decides, in one fixed order:
authenticated → role chosen → role allowed. An unmarked route is denied to everyone (deny by
default), and a route-table sweep fails the build naming it. "Access denied" is the friendly error
page with 403, naming the current role.

**CSRF**: one application-wide Fetch Metadata / `Origin` check refuses cross-site unsafe-method
requests before any database access. It covers the role forms, login and logout, and every future
write, including HTMX. This closes milestone 4's accepted login-CSRF risk.

**Pages**: `/admin`, `/teacher`, `/student`, `/staff` placeholders declared once in `AREAS`, which
also drives the home page's links. The header shows `Student Competitions · <Role>` and, for
multi-role people, a one-click switch.

**Schema**: one additive revision: create `user_roles` and copy the existing administrators, add
`sessions.current_role`, and make the old `users.role` nullable (unused, dropped in milestone 6),
so the previous release keeps working during the deploy overlap.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**: FastAPI 0.141, Starlette, Jinja2, uvicorn, SQLModel, Alembic, psycopg 3
and python-multipart, all unchanged. **No new runtime or dev dependency.** The cross-site check
and the role marker use only the standard library and Starlette's request API
([research D4](./research.md#d4--declaring-access-an-allow_roles-marker-read-by-the-one-application-wide-check),
[D7](./research.md#d7--cross-site-forgery-an-application-wide-fetch-metadata-and-origin-check)).

**Storage**: the same SQLite (local and tests) and Neon PostgreSQL 17 (production). One new table
(`user_roles`), one new nullable column (`sessions.current_role`), and one relaxed constraint
(`users.role` nullable), all in **one** additive Alembic revision ([data-model.md](./data-model.md)).
There is no engine-specific SQL.

**Testing**: pytest with `TestClient`, both engines through the existing parametrised fixtures.
The application fixtures start with a fixed cast of five addresses covering every role and both
multi-role combinations. `sign_in_directly` gains a `current_role` argument, and a `client_as`
factory is added. `admin_client` keeps its meaning, so existing page tests keep passing
([research D12](./research.md#d12--tests-a-fixed-cast-a-role-aware-shortcut-and-sweeps-over-the-route-table)).
Test modules:

- new: `test_access_control.py` (15-case matrix, home links, 403 page),
  `test_role_choice.py`, `test_role_switch.py`, `test_cross_site.py` (integration);
  `test_cross_site_rule.py` (unit);
- renamed and extended: `test_admin_reconcile.py` → `test_user_reconcile.py`;
- changed: `test_routes.py` (declaration sweep, write routes + `/role`), `test_sessions.py`
  (G1–G6, pre-milestone upgrade), `test_login_flow.py` (role step after the code), `test_home.py`
  (role header and links), `test_auth_config.py`, `test_safe_next.py`, `test_migrations.py`
  (data-preserving upgrade/downgrade), `test_startup.py`.

No test reaches an external service.

**Target Platform**: a Linux container on Render (free, `frankfurt`) behind Render's proxy and
Cloudflare, unchanged. Both preserve the `Host` header, which the `Origin` fallback compares
against.

**Project Type**: a single server-rendered web application, unchanged.

**Performance Goals**:

- still one indexed query per request to resolve the session: it now joins `user_roles` and
  returns at most three rows;
- at most one extra write per session, ever: the pre-milestone upgrade, or ending a session whose
  role is no longer held;
- the cross-site check is a header comparison with no I/O;
- reconciliation stays well under a second at the expected scale (hundreds of people);
- PR verification time is essentially unchanged (a few more `curl` calls in the image job).

**Constraints**:

- Roles come **only** from deployment configuration. No route grants, revokes or lists roles
  (FR-009).
- No login bypass. The only shortcut is `sign_in_directly` in `tests/` (FR-041).
- No email address in any log line: reconciliation, role choice and switch, and denial
  (FR-007, SC-008).
- `/healthz` stays I/O-free, with or without a cookie (milestone 2).
- Single-role administrators signed in before the release must not be signed out (SC-010).
- The schema change must not break the previous release during a deploy overlap or a refused
  start (milestone 4 data-model §7).
- No change to the login or code rules, rate limits or session lifetime (FR-042).

**Scale/Scope**:

- 1 new model (`UserRole`), 2 changed models, 1 migration;
- changed `core/config.py`, `core/security.py`, `core/auth.py`, `core/templates.py`, `main.py`;
- changed `services/users.py`, `services/sessions.py`;
- 2 new routers (`roles.py`, `areas.py`), 2 changed routers (`auth.py`, `pages.py`);
- 2 new templates (`role_choice.html`, `area.html`), 3 changed templates (`base.html`,
  `home.html`, `error.html`);
- changes to `render.yaml`, `checks.yml`, `verify_private.sh` and the README;
- about 5 new and 9 changed test modules;
- users: a handful of administrators now, teachers and students as entered. Data: kilobytes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Verdict | Evidence / Notes |
|---|---|---|---|
| I | Walking Skeleton & Vertical Slices | **PASS** | Milestone 5 of the ladder, on branch `005-roles-authorization`, started after milestone 4 was merged and deployed (`57bd304`). It is a vertical slice: settings → tables → reconciliation → session role → access check → role choice and switch → placeholder pages → header. It is demonstrable end to end (quickstart V1, V2). There are no features behind the placeholders and no user, institution or profile management (FR-042). The route sweep pins the write routes to login, logout and `/role`. |
| II | Server-Rendered Simplicity | **PASS** | Jinja2 pages with Pico.css. Plain forms and 303 redirects, no HTMX, no JavaScript (FR-033). **No new dependency.** No new abstraction without a present need: `allow_roles` is a decorator that sets one attribute, `Area` has four present instances, and `SessionIdentity` replaces a `User` return value that no longer carries enough. Services remain plain functions. |
| III | Test-Backed Delivery (NON-NEGOTIABLE) | **PASS** | Every clause of the milestone's `_Test:_` line is an automated pytest test (quickstart V3 table). Every protected route has allowed **and** denied tests per role: the 15-case matrix, plus a sweep proving every declared route admits exactly its roles. The email sender stays the `memory` fake. Once-per-milestone production checks (V6–V9) are recorded in Complexity Tracking. |
| IV | Role-Based Access & Data Scoping (NON-NEGOTIABLE) | **PASS, ending milestone 4's route-level deviation; one continuing deviation (Complexity Tracking)** | Authorization is enforced **server-side on every route** by one reusable application-wide FastAPI dependency (`resolve_access`), and access follows the **current** role only (FR-022). It is **deny-by-default**: a route without a non-empty `@allow_roles` declaration, outside the explicit allowlist and the two role-choice routes, is refused at runtime *and* fails the build (FR-024, SC-002). Links are hidden on the home page too, but the server check is what closes the page (US5-5). The administrator list still comes only from configuration, and no UI changes roles (FR-009). Teacher and student lists in configuration are temporary by the technical requirements (milestone 7). Institution scoping, competition rights and student data rules have no data to apply to yet (milestones 7–11). **Continuing**: the question service's write functions still have no HTTP caller and no role check. Milestone 6 adds both. |
| V | Secure Authentication & Secrets | **PASS** | No change to OTP, sessions, cookie flags or logout. **CSRF**: every unsafe-method request is checked application-wide with Fetch Metadata (`Sec-Fetch-Site`) and an `Origin`/`Host` fallback, before any database access ([research D7](./research.md#d7--cross-site-forgery-an-application-wide-fetch-metadata-and-origin-check)). Choosing and switching are `POST`-only and validated against the roles held (FR-020, FR-021). This fulfils milestone 4's obligation to revisit CSRF and covers milestone 6's HTMX writes without per-form work. The two new secrets are declared `sync: false` and never echoed (`repr` shows counts only, errors show positions only). No log line contains an address, a token or a code. |
| VI | Trustworthy LLM Evaluation | **N/A** | No LLM usage (milestone 10). |
| VII | Data Integrity & Migrations | **PASS (one deferred contraction, Complexity Tracking)** | One SQLModel table added in `app/models/`, and one Alembic revision (no `create_all`). Portable SQL only: composite primary key, CHECK, nullable column; concurrency through unique constraints plus a retry, with no upsert and no advisory lock. Timestamps are `UTCDateTime`. People are never hard-deleted (FR-008). The revision is additive, keeps existing administrators (data-preserving upgrade, tested), and has a safe downgrade that deactivates non-administrators. The drift, stairway, single-head and concurrent-upgrade tests cover it on both engines. |
| — | Technology Stack table | **PASS** | Exactly the milestone-5 row is introduced: "Roles: student / teacher / administrator; administrator list from deploy-time configuration; enforced server-side, deny-by-default". Nothing is replaced or added. |
| — | Open stack decisions | **N/A** | None is due in milestone 5. |
| — | Application Layout | **PASS** | `core/`: the access decision, the marker and the role-choice allowlist (`auth.py`); the pure cross-site rule (`security.py`); settings (`config.py`); template context (`templates.py`). `models/`: `user_role.py`. `services/`: reconciliation (`users.py`) and session identity (`sessions.py`). `routers/`: `roles.py` (role choice and switch), `areas.py` (placeholders by area), thin handlers only. `templates/pages/`: `role_choice.html`, `area.html`. |
| — | Operational Constraints | **PASS** | One image, configured only by environment variables. Migrations still run in the entrypoint. A malformed list refuses the start before any database access. Errors (403, 400, 404) render friendly pages, with no stack trace. |
| — | Development Workflow gate 3 (PR gates) | **PASS** | CI stays green-or-blocked on the same contexts. The schema change has a migration. Every new and changed route has per-role access tests. No secret is in the diff. The README is updated in the same PR (FR-039, Workflow §5). |

**New runtime dependencies**: none. **New infrastructure**: none. Two new Render environment keys
(`TEACHER_EMAILS`, `STUDENT_EMAILS`), declared `sync: false`.

**Post-Phase 1 re-check**: **PASS with the recorded deviations**. No verdict changed after writing
[data-model.md](./data-model.md), the [contracts](./contracts/) and
[quickstart.md](./quickstart.md). The design stayed inside the stack table and the layout, added
no dependency and no engine-specific SQL, and left `/healthz` untouched. Three choices go beyond
the spec's minimum without adding scope:

- the cross-site check applies to **every** unsafe request rather than only `/role`. This closes
  milestone 4's login-CSRF residual risk, and milestone 6 inherits it (V);
- the home links come from the same `AREAS` declaration as the enforcement, so they cannot drift
  (IV);
- the CI image job and the release script each gain a role check, so authorization is verified
  against the real container and the real address, not only in-process (III).

## Project Structure

### Documentation (this feature)

```text
specs/005-roles-authorization/
├── plan.md                      # This file (/speckit-plan command output)
├── spec.md                      # Feature specification (/speckit-specify)
├── research.md                  # Phase 0: D1…D13, decisions and rejected alternatives
├── data-model.md                # Phase 1: Role, users (changed), user_roles (new), sessions (changed); revision
├── quickstart.md                # Phase 1: rollout gate, local sign-in per role, validation V1…V9
├── contracts/
│   ├── http-routes.md           # Phase 1: access rule, cross-site rule, header, /role, areas, 403 page
│   ├── auth-services.md         # Phase 1: reconcile_users, session identity, allow_roles, is_cross_site; matrices
│   ├── configuration.md         # Phase 1: TEACHER_EMAILS, STUDENT_EMAILS; rules C9–C10, W3–W4; startup order
│   └── pipeline.md              # Phase 1: render.yaml, checks.yml image job, verify_private.sh
├── checklists/
│   └── requirements.md          # Spec quality checklist
└── tasks.md                     # Phase 2 output (/speckit-tasks, NOT created here)
```

### Source Code (repository root)

```text
render.yaml                         # CHANGED: + TEACHER_EMAILS, STUDENT_EMAILS (sync: false)
README.md                           # CHANGED: the two settings (temporary until M7), local sign-in per role, roles & access rule
pyproject.toml, uv.lock, Dockerfile # unchanged

.github/workflows/
├── checks.yml                      # CHANGED: image job: role header/links, /admin 200, /student 403, cross-site logout 403
├── ci.yml, deploy.yml              # unchanged

scripts/
└── verify_private.sh               # CHANGED: + anonymous GET /admin → 303 /login?next=%2Fadmin

migrations/versions/
└── YYYY_MM_DD_<rev>_add_user_roles.py   # NEW: user_roles + admin backfill; sessions.current_role; users.role nullable

app/
├── main.py                         # CHANGED: reconcile_users_with_retry(role lists); handlers for RoleChoiceRequired (303),
│                                   #          AccessDenied and CrossSiteRequest (403); include roles + areas routers
├── core/
│   ├── config.py                   # CHANGED: teacher_emails, student_emails; one list parser; C9–C10, W3–W4; repr counts
│   ├── security.py                 # CHANGED: AUTH_PATHS + "/role"; NEW is_cross_site(method, headers)
│   ├── auth.py                     # CHANGED: ROLE_CHOICE_ROUTES, allow_roles, declared_roles, decision order, CurrentRole,
│   │                               #          RoleChoiceRequired / AccessDenied / CrossSiteRequest
│   ├── templates.py                # CHANGED: context adds current_role, user_roles
│   └── db.py, migrations.py        # unchanged
├── models/
│   ├── __init__.py                 # CHANGED: + UserRole
│   ├── user.py                     # CHANGED: Role + TEACHER, STUDENT, labels; role → legacy_role (nullable, unused)
│   ├── user_role.py                # NEW: UserRole (table user_roles)
│   └── user_session.py             # CHANGED: + current_role
├── services/
│   ├── users.py                    # CHANGED: reconcile_users (replaces reconcile_admins), get_roles, ReconcileResult counts
│   ├── sessions.py                 # CHANGED: SessionIdentity, start_session, get_session_identity (replaces
│   │                               #          get_session_user), set_current_role; create_session(current_role)
│   └── login.py, email.py, rate_limits.py, questions.py, database_status.py   # unchanged
├── routers/
│   ├── auth.py                     # CHANGED: POST /login/code → start_session; multi-role → /role?next=…
│   ├── roles.py                    # NEW: GET /role, POST /role
│   ├── areas.py                    # NEW: Area, AREAS, areas_for; /admin, /teacher, /student, /staff
│   ├── pages.py                    # CHANGED: GET / @allow_roles(all three); passes areas_for(current_role)
│   └── health.py                   # unchanged
└── templates/
    ├── layouts/base.html           # CHANGED: "· <Role>" beside the name; switch form for multi-role
    └── pages/
        ├── role_choice.html        # NEW
        ├── area.html               # NEW: title + one sentence
        ├── home.html               # CHANGED: + "Your areas" list
        ├── error.html              # CHANGED: optional heading (e.g. "Access denied")
        └── login.html, login_code.html   # unchanged
app/static/css/app.css              # CHANGED: .site-role, .role-switch (small overrides)

tests/
├── conftest.py                     # CHANGED: cast of 5 addresses; TEACHER/STUDENT_EMAILS isolated; sign_in_directly(current_role);
│                                   #          client_as factory; admin_client via client_as
├── unit/
│   ├── test_auth_config.py         # CHANGED: C9, C10, W3, W4; repr counts
│   ├── test_safe_next.py           # CHANGED: /role → "/"
│   └── test_cross_site_rule.py     # NEW: is_cross_site table
└── integration/
    ├── test_access_control.py      # NEW: 3×5 matrix, home links per role, 403 page content, anonymous → login, 404 stays 404
    ├── test_role_choice.py         # NEW: US3 + login flow via outbox; next kept; tampered role; single-role → /
    ├── test_role_switch.py         # NEW: US4; two browsers; switch lands on /; plain link changes nothing
    ├── test_cross_site.py          # NEW: cross-site POST /role and /logout refused, nothing changes
    ├── test_user_reconcile.py      # RENAMED from test_admin_reconcile.py: S1–S11, restart removes role → logged out, counts-only log
    ├── test_routes.py              # CHANGED: every route public / role-choice / declared; undeclared probe route; writes + /role
    ├── test_sessions.py            # CHANGED: G1–G6; pre-milestone session upgraded, not ended
    ├── test_login_flow.py          # CHANGED: single-role unchanged redirect; removed from every list → no code
    ├── test_home.py                # CHANGED: header shows role; existing assertions via admin_client
    ├── test_migrations.py          # CHANGED: admins backfilled into user_roles; downgrade deactivates non-admins
    └── test_startup.py             # CHANGED: malformed TEACHER_EMAILS refuses the start, not counted
```

**Structure Decision**: the existing single FastAPI application and the constitution's `app/`
layout, extended in place. The access decision stays where milestone 4 put it (`core/auth.py`),
because it is infrastructure every router shares. The cross-site rule is a pure function in
`core/security.py`, unit-testable without an application. Role and session business rules live in
`services/`. The role choice and the placeholders get their own routers, so later milestones can
replace a placeholder without touching unrelated handlers. There is no new top-level directory.

## Complexity Tracking

Governance requires every deviation and residual risk to be visible here.

| Deviation / residual risk | Why it is needed | Simpler alternative rejected because |
|---|---|---|
| **Principle IV** (continuing from milestones 3–4, now narrowed): the question service's write functions enforce no role. **Ends when**: milestone 6 puts the teacher question bank behind `@allow_roles(Role.TEACHER)` with allowed and denied tests. | They still have no HTTP caller: `test_routes.py` pins the write routes to login, logout and `/role`. The route-level half of milestone 4's deviation ends here: every route now declares its roles. | Adding service-level role checks with no caller would be milestone-6 work smuggled in (Principle I), designed before its first use. |
| **Principle VII, deferred contraction**: `users.role` stays in the schema, nullable and unused (`legacy_role`). **Ends when**: milestone 6's first migration drops it. | The previous release reads that column on every request. During a deploy overlap, or after a refused start that already migrated, it must keep working ([research D2](./research.md#d2--migration-expand-now-contract-later-the-old-usersrole-column-stays-nullable)). | *Drop it now*: would break sign-in on the old release for the overlap window, the failure mode milestone 4's additive-revision rule exists to prevent. |
| **CSRF fallback allows requests carrying neither `Sec-Fetch-Site` nor `Origin`** (non-browser clients, very old browsers). | Every current browser sends `Sec-Fetch-Site` on form posts. Refusing header-less requests would break `curl`-based CI sign-in and add nothing against browser-borne forgery. `SameSite=Lax` still keeps the session cookie off cross-site posts. | *Synchronizer tokens*: a per-form burden for every form and every future HTMX call, and a forgotten token fails open only for that form ([research D7](./research.md#d7--cross-site-forgery-an-application-wide-fetch-metadata-and-origin-check)). |
| **Any role removal ends all of the person's sessions**, including sessions using a role they still hold. | The technical requirements say "removing a person from a list … logged out everywhere" (spec assumption). | *Ending only sessions using the removed role*: gentler, but it contradicts the requirement and needs per-session logic for no benefit at this scale. |
| **Session resolution may write during a `GET`**: once per pre-milestone session (setting the single role) and once when ending a session whose role is no longer held. | SC-010 forbids signing administrators out at release, and FR-017 requires ending stale sessions on the request that finds them. | *A one-off backfill in the migration*: leaves the upgrade path untested. It also cannot handle the FR-017 race between a configuration change and the cleanup. |
| **Principle III, manual once-per-milestone checks**: pre-release session survives (V6), real teacher and student sign-in (V7), role removal on production (V8), log review (V9). | Each is about the real platform, real inboxes or real logs. The suite already covers the application side of each. | Automating them needs real inboxes and production credentials in CI, a larger standing risk than the checks remove. |
| **Milestone 4 residual risks carried unchanged**: spoofable per-client rate-limit key; release-time data check downgraded; refused start after migrating. | Nothing in this milestone touches them ([specs/004-email-otp-auth/plan.md](../004-email-otp-auth/plan.md#complexity-tracking)). The login-CSRF risk is **closed** by the cross-site check. | — |
