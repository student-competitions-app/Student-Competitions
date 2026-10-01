# Research & Decisions: Roles and Authorization (Milestone 5)

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](./plan.md)

The spec left five choices to the plan: how roles are stored and migrated, how a page declares
its roles, the cross-site forgery mechanism, the page addresses, and the setting names. The
Technical Context had no other unknowns. Each entry records the decision, why it was made, and
what was rejected. Everything builds on milestone 4's design
([specs/004-email-otp-auth/research.md](../004-email-otp-auth/research.md)), which is reused
unless an entry says otherwise.

---

## D1 — Role storage: a `user_roles` table, one row per role held

**Decision**: a new table `user_roles` with a composite primary key `(user_id, role)`, a foreign
key to `users.id`, a `role` column limited by a CHECK constraint to `admin`, `teacher` and
`student`, and a `created_at`. A person holds a role exactly when the row exists. The in-code
`Role` enum (`app/models/user.py`) gains `TEACHER` and `STUDENT`, keeps the stored value `admin`
for administrators, and defines the display labels and the fixed order (administrator, teacher,
student) used everywhere a list of roles is shown.

**Invariant**: an active user has at least one role row, and an inactive user has none.
Reconciliation (D8) maintains this inside one transaction, so `is_active` alone still answers
"may this person obtain a code" (FR-010). Milestone 4's login code needs no change.

**Rationale**:

- The spec's entities are "a person" and "a role assignment, at most one per role" (Key
  Entities). The composite primary key states that rule exactly, and it is also the unique
  constraint that makes concurrent reconciliation safe (D8).
- Portable: plain rows, no arrays, no JSON, no engine-specific types (Principle VII).
- Milestone 7 replaces the teacher and student lists with management in the application. A row
  per assignment is what that milestone will insert and delete. No reshaping is needed.

**Alternatives considered**:

- *Three boolean columns on `users`* (`is_admin`, `is_teacher`, `is_student`): one fewer table,
  but "which roles does this person hold" becomes column logic in every query, and the "at least
  one role" invariant would need a multi-column CHECK.
- *A comma-separated `users.role` string*: not queryable and not constrainable.
- *A PostgreSQL array or enum type*: not portable to SQLite.

---

## D2 — Migration: expand now, contract later; the old `users.role` column stays, nullable

**Decision**: one additive Alembic revision:

1. creates `user_roles`;
2. copies every active user's `users.role = 'admin'` into a `user_roles` row;
3. adds `sessions.current_role` (nullable);
4. makes `users.role` nullable (batch mode on SQLite, as `migrations/env.py` already configures).

The model keeps the old column mapped as `legacy_role: str | None`, documented as unused. The
application never reads it and never writes it. New users get `NULL`. The column is dropped by
the **first migration of milestone 6**. This is recorded in Complexity Tracking.

Existing sessions are **not** backfilled. Their `current_role` stays `NULL`, and the next request
upgrades them (D9). This is the path the spec's "session from before this milestone" edge case
requires anyway, so it is exercised and tested rather than bypassed.

**Rationale**:

- Milestone 4's plan relies on an additive schema. During a deploy overlap, or after a refused
  start (the entrypoint migrates before the application validates its settings), the previous
  release keeps serving on the new schema. The milestone 4 code selects `users.role` on every
  session lookup. Dropping the column now would break sign-in for every visitor of the old
  release during that window. A nullable column breaks nothing: milestone 4 always writes a
  value, and reads tolerate `NULL`.
- Mapping the column keeps the drift test (`test_models_match_the_migrated_schema`) honest,
  without an exclusion filter in Alembic's comparison.

**Downgrade** (exercised by the stairway test on both engines): set `users.role = 'admin'` for
holders of the administrator role. For people with no administrator role, set `users.role` to
their first remaining role, deactivate them, and delete their sessions and codes, because
milestone 4 would otherwise treat any active user as an administrator. Then drop
`sessions.current_role` and `user_roles`, and make `users.role` non-null again.

**Alternatives considered**:

- *Drop `users.role` in this revision*: simplest schema, but it breaks the previous release
  during overlap or a refused start (above).
- *Keep writing a "primary role" into `users.role`*: two sources of truth with different
  meanings.
- *Backfill `sessions.current_role = 'admin'`*: equivalent today, but it would leave the upgrade
  path in D9 untested until it is needed.

---

## D3 — The current role lives on the server-side session row

**Decision**: `sessions.current_role` (nullable `VARCHAR(20)`). `NULL` means "signed in, no role
chosen yet". It is set at sign-in for single-role people (FR-012), by the role choice and by the
header switch (FR-015, FR-019), and by the upgrade of a pre-milestone session (D9). Each browser
has its own session row, so each browser has its own current role (FR-011, US4-5).

**Rationale**: sessions are already server-side (Principle V). Keeping the role on the same row
means one lookup returns both, and ending the session ends the role. A request can never claim a
role the server did not record.

**Alternatives considered**:

- *The role in the cookie (signed)*: the server could not revoke or check it without a lookup
  anyway, and the cookie format would change.
- *A separate `session_roles` table*: a 1:1 table for one nullable value.
- *Per-user "current role"*: breaks US4-5 (two browsers, two roles).

---

## D4 — Declaring access: an `@allow_roles(...)` marker read by the one application-wide check

**Decision**: every page outside the public allowlist and the role choice routes is decorated
with `@allow_roles(Role.X, ...)` (`app/core/auth.py`). The decorator records a non-empty
`frozenset[Role]` on the endpoint function (`endpoint.allowed_roles`), raises at import time if
called with no roles, and returns the function unchanged. The existing application-wide
dependency `resolve_access` reads the marker from the matched route
(`request.scope["route"].endpoint`) and decides access (D5). A route with no marker is denied to
every signed-in person (FR-024).

A route-table sweep (`tests/integration/test_routes.py`) asserts that every route is in
`PUBLIC_ROUTES`, in `ROLE_CHOICE_ROUTES`, or carries a non-empty marker. It fails naming the
route otherwise (FR-040, SC-002). A probe confirmed that FastAPI 0.141's matched `APIRoute`
exposes the endpoint, and that the marker is seen whichever order the two decorators are
written in, because both decorate the same function object.

**Rationale**:

- **Deny by default stays structural.** Milestone 4 made "private" the default by putting the
  check in one place that runs for every route. This keeps that property: the check is still in
  one place, and forgetting the declaration fails closed at runtime *and* fails the build.
- **The declaration sits next to the route**, as the spec asks ("every page states which roles
  may open it"), so a reviewer sees it in the same diff as the handler.
- **One reusable FastAPI dependency** enforces it for every route (Principle IV). The marker is
  data, not a second enforcement path that could disagree with the first.

**Alternatives considered**:

- *A per-route `dependencies=[Depends(require_roles(...))]`*: idiomatic, but a forgotten
  dependency leaves the route **open** to every signed-in person. Detecting the absence
  centrally would mean walking FastAPI's internal dependency tree on every request.
- *A central `ROUTE_ROLES` table beside `PUBLIC_ROUTES`*: fails closed too, but it puts the
  declaration away from the handler. It is also a second list to keep in sync with the routes.
- *Router-level dependencies, one router per role*: does not express the staff area (two roles)
  without a fifth router, and still opens a route that is put in the wrong router.

---

## D5 — One decision order for every request

**Decision**: `resolve_access` applies these rules, first match wins:

| # | Request | Result |
|---|---|---|
| 1 | `GET`/`HEAD /healthz` | served; no session lookup (unchanged, milestone 2) |
| 2 | unsafe method (not `GET`/`HEAD`/`OPTIONS`) judged cross-site (D7) | **403** "request refused"; no session lookup, nothing changes |
| 3 | no valid session, route in `PUBLIC_ROUTES` | served |
| 4 | no valid session, any other route | **303** to `/login?next=…` (unchanged) |
| 5 | signed in, route in `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES` | served |
| 6 | signed in, no current role | **303** to `/role?next=…` (`GET`/`HEAD`), or `/role` (other methods) |
| 7 | signed in, current role in the route's `allowed_roles` | served |
| 8 | signed in, anything else (including no marker) | **403** "access denied" page naming the current role |

A path that matches no route never reaches the dependency, so it keeps the friendly 404 for
everyone (spec edge case "page that does not exist").

"Valid session" now also requires that the session's current role, if set, is one the person
holds (D9).

**Rationale**: this is the spec's access rules written as one table. Authorization runs only
after authentication (FR-023), so anonymous visitors never see "access denied". The role choice
gate (FR-014) runs before the role check, so a multi-role person without a role is redirected
rather than denied. The cross-site check runs before any database access, so a forged request
costs nothing.

---

## D6 — Choosing and switching: one form route, `POST /role`

**Decision**:

- `GET /role` renders the role choice: a heading, one sentence, and one form posting to `/role`
  with one submit button per role held (`name="role"`, `value="admin"|"teacher"|"student"`), in
  the fixed order. The form also carries the sanitised `next` as a hidden field. A person with
  one role is redirected to `/` (FR-016).
- `POST /role` (fields `role`, optional `next`) makes the role current if the person holds it,
  and redirects 303 to `safe_next_path(next)`, so `/` when `next` is absent. A role the person
  does not hold, or a missing or unknown value, changes nothing and re-renders the role choice
  with status 400 and a message (US3-5, US4-6).
- The **header switch** is a small form posting to the same `/role`, with one button per *other*
  role ("Switch to Teacher") and no `next` field, so a switch lands on `/` (FR-019). With at most
  two other roles, inline buttons fit the header and make a switch one click (SC-005).
- `/role` joins the paths `safe_next_path` refuses as return targets (it becomes `/`), next to
  `/login`, `/login/code` and `/logout`. So no landing step can loop back into the role choice
  (FR-015, edge case).
- After a successful code check, a multi-role person is redirected to `/role?next=<next>`
  instead of `next` (FR-013).

**Rationale**: choosing and switching are the same state change (make role X current). The only
difference is where the person lands, and the presence of `next` already expresses that. One
route means one validation path, one CSRF surface and one set of tests. The spec's edge case
"choosing a role on the role choice page after a role is already chosen works exactly like
switching" falls out of this: opened directly, the page has no `next`, so it lands on `/`. Plain
links (`GET /role?role=…`) change nothing, because only `POST` changes state (FR-020).

**Alternatives considered**:

- *Separate `POST /role/choose` and `POST /role/switch`*: two routes with identical rules.
- *A Pico `<details class="dropdown">` switcher*: tidier with many roles, but it takes two clicks
  and nobody has more than three roles.
- *Remembering the last-used role between sign-ins*: out of scope (spec).

---

## D7 — Cross-site forgery: an application-wide Fetch Metadata and `Origin` check

**Decision**: a pure function `is_cross_site(method, headers)` (`app/core/security.py`), applied
by `resolve_access` (rule 2 of D5) to every request with an unsafe method. It is not limited to
the role forms. The rule follows the design Go 1.25 ships as `net/http.CrossOriginProtection`:

1. Safe methods (`GET`, `HEAD`, `OPTIONS`) are never cross-site.
2. If `Sec-Fetch-Site` is present: allowed only when it is `same-origin` or `none`. `same-site`
   and `cross-site` are refused.
3. Otherwise, if `Origin` is present: allowed only when its host (and port) equals the request's
   `Host` header. `Origin: null` is refused.
4. Otherwise (neither header, which means a non-browser client or a very old browser): allowed.

A refused request gets the friendly error page with **403** and the message "This request was
refused because it did not come from this site." Nothing is read or written.

**Rationale**:

- **FR-021 needs a cross-site submission to change nothing.** `SameSite=Lax` already keeps the
  session cookie off cross-site `POST`s, so a forged switch arrives anonymous and is redirected
  to login. That is a browser behaviour, though, not a server rule. This check makes the refusal
  explicit and testable.
- **It covers every state-changing request from now on, including HTMX**, with no per-form work.
  HTMX requests are same-origin `fetch`es that send `Sec-Fetch-Site: same-origin`. Milestone 6
  inherits the protection without having to remember it, which is the obligation the spec
  records.
- **It also closes milestone 4's accepted login-CSRF risk**: a cross-site `POST /login/code` is
  now refused.
- **Stateless and dependency-free**: no token store, no hidden fields, no cookie. `Host` is
  correct behind Render and Cloudflare (both preserve it), and every browser the product
  targets sends `Sec-Fetch-Site`.
- **CI and tests keep working**: `curl` and `TestClient` send neither header (rule 4).

This is not a change to the login or code rules (FR-042). Every legitimate sign-in is a
same-origin form post and behaves exactly as before.

**Alternatives considered**:

- *A synchronizer token per session in a hidden field*: works everywhere, but every form,
  including logout, and every future HTMX request must carry it, and forgetting one breaks only
  that form. The token must also be stored or derived from the session.
- *A double-submit cookie*: a second cookie and the same per-form burden.
- *`SameSite=Lax` alone*: what milestone 4 accepted. The spec asks this milestone to add a server
  rule.
- *`SameSite=Strict`*: breaks arriving signed in from a link in an email or another site.

---

## D8 — Reconciliation, generalised to three lists

**Decision**: `reconcile_users(session, role_lists, now=None) -> ReconcileResult` replaces
`reconcile_admins`. It takes `role_lists: Mapping[Role, Sequence[str]]` (already normalised and
de-duplicated by the settings loader) and runs in **one transaction**:

1. **Desired state**: `desired[email] = {roles whose list contains email}`.
2. **People**: a listed address with no user is created active. An inactive one is reactivated.
   Every active user who is not listed is deactivated. No user is ever deleted (FR-008).
3. **Roles**: load every `user_roles` row (the table is tiny), compare with `desired` per user
   (an unlisted user's desired set is empty), insert the missing rows and delete the extra ones.
4. **Sessions**: delete every session of every user who **lost any role** in step 3, whether
   because one list dropped them or all of them did (FR-005, spec assumption "any role removal
   logs out everywhere"). Adding roles deletes nothing (US2-6).
5. **Inactive cleanup** (as milestone 4): delete every session and login code of every inactive
   user. This also finishes any earlier partial run.
6. `users.updated_at` changes only for people whose active flag or role set changed, so a second
   run writes nothing (FR-006, SC-007).

It returns `created`, `reactivated`, `deactivated`, `roles_added`, `roles_removed` and
`unchanged` (people with no change of any kind). The startup log prints those six counts and
nothing else (FR-007, SC-008).

**Concurrency** (FR-006, edge case "two instances starting at once"): unchanged in shape from
milestone 4 (research D13). `uq_users_email` and the `user_roles` primary key reject the second
of two identical inserts. The caller (`reconcile_users_with_retry` in `app/main.py`) rolls back
and runs once more. The retry sees the other instance's rows and reaches the same end state.
Deletes and the deactivation `UPDATE` are idempotent under concurrency. No advisory lock or
upsert is needed, so the SQL stays portable.

**Rationale**: one function, one transaction and one end state, whatever the starting state. The
invariant from D1 (active ⇔ at least one role row) holds at every commit.

**Alternatives considered**:

- *Three calls, one per list*: a person on two lists would be deactivated by the call for the
  list they are not on.
- *Ending only sessions whose current role was removed*: gentler, but the technical requirements
  say "logged out everywhere". It would also need per-session logic for no benefit at this
  scale.

---

## D9 — Session resolution: one query, the role check, and the pre-milestone upgrade

**Decision**: `get_session_identity(session, token, now=None) -> SessionIdentity | None`
(`app/services/sessions.py`) replaces `get_session_user`. One query joins `sessions` →
`users` → `user_roles` on the token hash, unexpired, active user, and returns one row per role
held (at most three). The inner join means a person with no roles resolves to nobody. Then:

- `current_role` set and **not** among the roles (or not a known role value): the session row is
  deleted and the request is anonymous (FR-017, edge case "current role no longer held").
- `current_role` `NULL` and **exactly one** role held: that role is written to the session and
  becomes current (edge case "session from before this milestone", SC-010).
- otherwise: returned as is (`current_role` may be `NULL` for a multi-role person who has not
  chosen yet).

`SessionIdentity` is a frozen dataclass: `user`, `roles` (a tuple in the fixed order) and
`current_role` (`Role | None`). `resolve_access` keeps `request.state.user` and adds
`request.state.roles` and `request.state.current_role`. The template context processor exposes
`current_user`, `current_role` and `user_roles`. `CurrentUser` stays, and `CurrentRole` is added
beside it.

**Rationale**: one indexed query per request, as in milestone 4. The writes happen at most once
per session (the upgrade) or once ever (the ending). Single-role administrators signed in before
the release keep working with no new step (SC-010).

**Alternatives considered**:

- *Ending pre-milestone sessions*: signs every administrator out at release, which SC-010
  forbids.
- *Two queries (session and user, then roles)*: simpler SQL, but it doubles the per-request
  database round trips on Neon.

---

## D10 — Pages: four placeholders declared once, one template, a 403 on the error page

**Decision**:

- Addresses: `/admin` (Administrator area, administrator), `/teacher` (Teacher area, teacher),
  `/student` (Student area, student), `/staff` (Staff area, administrator and teacher). `/` is
  declared open to all three roles.
- `app/routers/areas.py` defines each area once as a small frozen dataclass (`path`, `title`,
  `roles`) and collects them in `AREAS`. Each of the four handlers is decorated with
  `@allow_roles(*AREA.roles)` and renders the shared `pages/area.html` (a title and one sentence,
  FR-030). The home handler lists `[area for area in AREAS if current_role in area.roles]`, so the
  links and the enforcement come from the same declaration and cannot drift apart (FR-027). The
  tests still check both against an independent copy of the spec's access table.
- "Access denied" is the existing `pages/error.html` with status 403. The template gains an
  optional heading (`Access denied` instead of the bare status code), and the message names the
  current role: "Your current role, Teacher, cannot open this page." It says nothing about the
  page's content (FR-025). The header, with the role switch, is still shown, so a multi-role
  person can switch by hand (FR-026, no automatic switch).
- The header (`layouts/base.html`) shows `Student Competitions · <Role>` on the left once a role
  is current. On the right it shows the email, the switch form (multi-role only) and **Log out**
  (FR-031, FR-018). On the role choice page with no role yet, it shows no role and no switch
  (FR-032).

**Rationale**: the smallest thing that satisfies FR-027 to FR-033 with no new mechanism. One
router module for four placeholder pages, because milestone 6 and later will put real features in
their own routers, grouped by area (constitution Application Layout).

**Alternatives considered**: four router modules with one route each (premature); a separate
`forbidden.html` (duplicates `error.html`); hard-coding the home links per role in the template
(a second copy of the access rules that could drift).

---

## D11 — Settings: `TEACHER_EMAILS` and `STUDENT_EMAILS`, parsed like `ADMIN_EMAILS`

**Decision**: `AuthSettings` gains `teacher_emails` and `student_emails` (normalised,
de-duplicated, sorted tuples). The list parsing in `resolve_auth_settings` becomes one helper
used for all three lists. A malformed entry adds `"<NAME> entry <n> is not a valid email
address."` to the single `AuthConfigError`, in every environment, and never shows the value
(FR-035). Both new lists may be empty or unset anywhere (FR-036, FR-037). The production rule
"`ADMIN_EMAILS` non-empty" is unchanged. `__repr__` shows only counts. The local warning becomes
"ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator." because the old
wording is false once the other lists exist. A second warning, "No role lists are set; nobody
will be able to sign in.", is shown when all three lists are empty. `render.yaml` declares both
keys with `sync: false` (FR-034).

**Rationale**: the spec fixes the pattern, and these names are the ones it expects. Reusing one
parser means the three lists cannot drift in their rules.

---

## D12 — Tests: a fixed cast, a role-aware shortcut, and sweeps over the route table

**Decision**:

- `conftest.py` starts every application fixture with a fixed cast:
  - `admin@example.com`: administrator;
  - `teacher@example.com`: teacher;
  - `student@example.com`: student;
  - `admin.student@example.com`: administrator and student;
  - `teacher.student@example.com`: teacher and student.

  `TEACHER_EMAILS` and `STUDENT_EMAILS` join the isolated variables.
- `sign_in_directly(test_client, email, current_role=AUTO)` creates the session through the same
  service the code check uses. `AUTO` gives a single-role person their role and a multi-role
  person none. An explicit `Role` or `None` overrides it. A factory fixture,
  `client_as(email, current_role=AUTO)`, returns a signed-in client. `admin_client` stays, so
  existing page tests keep passing (FR-041). Like milestone 4's shortcut, these live only in
  `tests/`.
- **Access matrix**: 3 roles × 5 pages = 15 parametrised cases, each on both engines, against a
  literal copy of the spec's table (SC-001). Home-link assertions for each role.
- **Route sweeps** (`test_routes.py`): every route is public, role choice, or declares a non-empty
  role set. The write routes are exactly `POST /login`, `/login/code`, `/logout` and `/role`.
  Every declared route admits exactly its roles (US5-2). The anonymous sweep is unchanged.
- **Deny by default at runtime** (US5-3, US5-4): a fixture temporarily adds an undeclared route
  to the running application and removes it on teardown. The sweep helper must name it, and a
  signed-in request to it must get 403.
- **Cross-site** (D7): unit tests of `is_cross_site` over a header table, and integration tests
  that a cross-site `POST /role` and `POST /logout` change nothing.

**Rationale**: the cast covers every role and both multi-role combinations the stories use.
Building on milestone 4's shortcut keeps the "no login bypass in the application" property.

---

## D13 — Pipeline: the packaged image proves one role boundary; the release proves a role page is private

**Decision**:

- `checks.yml` image job: after its existing real sign-in as the single-role CI administrator,
  `GET /admin` must answer 200, `GET /student` must answer 403, and the home page header must
  contain `· Administrator`. A cross-site `POST /logout` with `Origin: https://evil.example` must
  answer 403, and the session must still work afterwards.
- `scripts/verify_private.sh` (release): an anonymous `GET /admin` must answer 303 to
  `/login?next=%2Fadmin`.
- `render.yaml`: `TEACHER_EMAILS` and `STUDENT_EMAILS` with `sync: false`.

**Rationale**: a few cheap `curl` checks prove, against the real container and the real
production address, that authorization is wired in. No credential is added anywhere.

---

## Summary of resolved unknowns

| Left to the plan by the spec | Resolved in |
|---|---|
| How roles are stored, and the migration keeping existing administrators | D1, D2 |
| Where the current role lives | D3 |
| How a page declares its roles; deny by default | D4, D5 |
| Choosing vs switching; landing pages; loops | D6 |
| CSRF mechanism (Principle V) | D7 |
| Reconciliation of three lists; session ending; concurrency | D8 |
| Pre-milestone sessions; "role no longer held" | D9 |
| Page addresses, home links, "access denied" | D10 |
| Setting names and rules | D11 |
| Test shortcut and sweeps | D12 |
| Pipeline changes | D13 |
