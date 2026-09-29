# Implementation Plan: Email Code Authentication (Milestone 4)

**Branch**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-email-otp-auth/spec.md`

## Summary

Give the application a front door: passwordless sign-in by a 6-digit code sent by email, and make
every page private by default.

**Users**: a `users` table (normalised unique email, `role` = `admin` only for now, active flag).
It is filled **only** by reconciliation with the `ADMIN_EMAILS` deployment secret on every start,
after the migration check and before the boot count. Reconciliation creates, reactivates or
deactivates users, deletes the sessions and codes of deactivated users, is idempotent, is safe for
concurrent starts, and logs counts only. There is no sign-up and no admin UI.

**Login**: two plain forms. `POST /login` does **identical in-request work for every address**
(two database-backed rate-limit hits, then render step 2). A FastAPI background task, after the
response, looks the user up, issues the code and sends it. Timing therefore cannot reveal who is
registered. Codes are `HMAC-SHA256(SECRET_KEY, email+code)`, valid 20 minutes, single-use through a
conditional `UPDATE`, dead after 5 wrong attempts. The newest code deletes older ones. Requests are
limited to 5 per email and 20 per client per hour, sliding, in the database.

**Sessions**: a random 256-bit token. The database keeps its SHA-256. The `sc_session` cookie
carries `token.HMAC` (`HttpOnly`, `SameSite=Lax`, `Secure` on Render), with an absolute 14-day
lifetime. Every request checks the signature, then one indexed query checks unexpired and
active-user. Logout is a `POST` that deletes the row.

**Protection**: one **application-wide FastAPI dependency** resolves the user and turns anonymous
requests to any route outside a five-entry allowlist (`GET/POST /login`, `POST /login/code`,
`POST /logout`, `GET /healthz`) into 303 → `/login?next=…`. `next` is sanitised against open
redirects. A route-table test sweeps every route.

**Email**: an `EmailSender` protocol with `console` (local default: prints the email), `memory`
(tests: outbox) and `resend` (production: Resend's REST API through `urllib.request`) backends.
Resend closes the constitution's open "email delivery service" decision, with DKIM/SPF/DMARC set up
at NIC.UA. On Render the app refuses to start with a non-`resend` backend, a missing secret, a
short key or a bad admin list. The error names every bad setting and never shows a value.

**Pipeline**: `/` is private now, so the milestone-3 checks that read it anonymously move. The CI
`image` job **signs in for real**: it reads the code from the container's console output, then
proves boot 1 → 2 and that the session survives a restart. The release job's *Verify data* becomes
*Verify access control* (`/` → 303, `/login` → 200). `/healthz` is untouched.

## Technical Context

**Language/Version**: Python 3.13, unchanged (`.python-version`, `requires-python = ">=3.13,<3.14"`).

**Primary Dependencies**: FastAPI 0.141, Starlette 1.6, Jinja2, uvicorn 0.53, SQLModel, Alembic
and psycopg 3, all unchanged. **One new runtime dependency**: `python-multipart`, which FastAPI
requires to parse any HTML form body (justified below). Cryptography uses only the standard
library (`secrets`, `hmac`, `hashlib`, `base64`), as does the Resend call (`urllib.request`). No
new dev dependency ([research D1](./research.md#d1--email-delivery-service-resend-through-its-http-api-called-with-the-standard-library),
[D3](./research.md#d3--sessions-random-token-sha-256-in-the-database-hmac-signed-cookie),
[D11](./research.md#d11--plain-forms-no-redirect-between-the-steps-the-email-travels-in-a-hidden-field)).

**Storage**: the same SQLite (local/tests) and Neon PostgreSQL 17 (production). Four new tables,
`users`, `sessions`, `login_codes` and `rate_limit_hits`, in **one** additive Alembic revision
([data-model.md](./data-model.md)). All session, code and rate-limit state is in the application
database, as the constitution requires.

**Testing**: pytest with `TestClient`. Every database test runs on both engines through the
existing parametrised fixtures. New fixtures: `EMAIL_BACKEND=memory` (autouse), `outbox`, and
`admin_client`, which creates a session directly via `create_session`, a test-only shortcut that no
route exposes ([research D15](./research.md#d15--tests-an-anonymous-client-an-admin_client-with-a-directly-created-session)).
New modules:

- unit: `test_auth_config.py`, `test_security.py`, `test_safe_next.py`, `test_email.py`;
- integration: `test_login_flow.py`, `test_login_privacy.py`, `test_sessions.py`,
  `test_admin_reconcile.py`, `test_auth_services.py`.

`test_routes.py`, `test_home.py`, `test_health.py` and `test_startup.py` change. No test reaches
Resend.

**Target Platform**: a Linux container on Render (free, `frankfurt`) behind Render's proxy and
Cloudflare, unchanged. Resend's API is reached over HTTPS on port 443.

**Project Type**: a single server-rendered web application, unchanged.

**Performance Goals**:

- login pages respond in under 300 ms server-side (a handful of indexed queries);
- the session check adds one indexed query per request;
- known and unknown addresses: timing medians within 100 ms (SC-004); by construction there is no
  difference;
- the email arrives in under 1 minute, 95% in the inbox (SC-002, provider-dependent, verified
  manually);
- PR verification stays under 10 minutes (the image job adds about 20 s).

**Constraints**:

- The constitution requires server-side sessions and OTP state in the application database: no
  Redis, no scheduler.
- There is no login bypass of any kind (FR-034). The only shortcut is the `admin_client` fixture
  in `tests/`.
- No code, token, secret, address or email body in any log except the local console backend
  (FR-037, SC-008).
- The Render free tier: one small instance that sleeps when idle, a 5-second health check (so
  `/healthz` stays I/O-free, including with a cookie), and outbound SMTP possibly blocked (so we
  use the HTTP API).
- Render **appends** to client-supplied `X-Forwarded-For`, so the per-client key is spoofable
  (residual risk below).
- Same code and migrations on SQLite and PostgreSQL. **No** new engine-specific SQL.

**Scale/Scope**:

- 4 models, 1 migration, 1 new settings loader, 1 security helper module, 1 auth-dependency
  module, 5 service modules (`users`, `sessions`, `login`, `rate_limits`, `email`), 1 new router,
  2 new templates plus a layout change;
- 1 new script, 1 deleted script, and changes to `render.yaml`, `checks.yml`, `deploy.yml` and the
  README;
- about 9 new and 4 changed test modules;
- users: a handful of administrators. Data: kilobytes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Verdict | Evidence / Notes |
|---|---|---|---|
| I | Walking Skeleton & Vertical Slices | **PASS** | Milestone 4 of the ladder, on branch `004-email-otp-auth`, started after milestone 3 was merged and deployed (`24ab560` on `main`). It is a vertical slice: settings → tables → services → login pages → protected home page → production email. It is demonstrable end to end (quickstart V1, V5). There are no roles, role checks, student or teacher users, profiles or other write features (FR-047). The route test pins the write-route set to login and logout. |
| II | Server-Rendered Simplicity | **PASS** | Jinja2 pages with Pico.css. Plain forms and full-page responses, no HTMX, no JavaScript (FR-033). One new runtime dependency, `python-multipart`, justified below. Crypto and the HTTP call use the standard library instead of `itsdangerous`, the `resend` SDK or runtime `httpx`. There is one abstraction, `EmailSender`, and it has three concrete present implementations (console, memory, Resend), which is Principle II's bar. Services are plain functions. |
| III | Test-Backed Delivery (NON-NEGOTIABLE) | **PASS** | Every clause of the milestone's `_Test:_` is an automated pytest test (quickstart V2). The spec's acceptance scenarios map to the behaviour matrices in [auth-services.md](./contracts/auth-services.md) and [http-routes.md](./contracts/http-routes.md). The email sender is replaced by the `memory` backend in the suite, and the Resend sender is unit-tested with a fake transport, so **no test calls an external service**. The protected route `GET /` has allowed (`admin_client`) and denied (anonymous) tests, and the sweep covers every route. The once-per-milestone manual checks (real inbox, deliverability, production removal, spoofing probe) and the downgraded release data check are recorded in Complexity Tracking. |
| IV | Role-Based Access & Data Scoping (NON-NEGOTIABLE) | **PASS with one continuing deviation (Complexity Tracking)** | This milestone makes access **deny-by-default in structure**: an application-wide dependency protects every current and future route, and only a five-entry allowlist is public, verified by a sweep over the whole route table (FR-028, SC-003). It fulfils milestone 3's obligation that `GET /` and `/healthz` get an explicit access declaration. The administrator list comes only from deployment configuration, and no UI can change it (FR-003, FR-007). Per-role requirements ("a route without an explicit role requirement is a defect") cannot exist before roles, which arrive in milestone 5. Today "signed in" equals "administrator", because only administrators exist. The milestone-3 deviation for the question service's unguarded write functions also continues: they still have no HTTP caller. Both are recorded below, with the milestone that ends them. |
| V | Secure Authentication & Secrets | **PASS (CSRF per spec assumption)** | Email OTP only, no passwords. Codes are single-use (conditional `UPDATE`), short-lived (20 min), stored as a keyed HMAC, and rate-limited per email **and** per client in the database (research D2, D5). Sessions are server-side. The signed cookie is `HttpOnly`, `Secure` in production and `SameSite=Lax`. Logout deletes the server row. **CSRF**: the spec takes `SameSite=Lax` as sufficient for this milestone's only state-changing actions (login and logout), accepts the login-CSRF residual risk, and requires milestone 5 to revisit before HTMX writes arrive (recorded below). All four new secrets come from environment variables declared `sync: false`. No message, `repr` or log line shows a value. The application logs no code, token, key or address (FR-037, SC-008; quickstart V10). |
| VI | Trustworthy LLM Evaluation | **N/A** | No LLM usage (milestone 10). |
| VII | Data Integrity & Migrations | **PASS** | Four SQLModel tables in `app/models/`, created by one Alembic revision (no `create_all`). Portable SQL only, with no upsert or advisory lock added. Concurrency is handled by a unique constraint plus a retry (research D13), and the milestone-3 drift, stairway and single-head tests cover the new revision on both engines. Timestamps use `UTCDateTime`. Users are never hard-deleted (deactivated instead), so later results can reference them. The revision is additive, so the previous release keeps working during deploy overlap or a refused start. |
| — | Technology Stack table | **PASS** | Exactly the milestone-4 row is introduced: "Email one-time code (OTP) + server-side sessions in a signed cookie". Authorization (roles) stays in milestone 5. Nothing else changes. |
| — | Open stack decision: email delivery service | **RESOLVED** | **Resend, transactional-email HTTP API** (not SMTP), from the verified domain `brainring.org.ua` with DKIM, SPF and DMARC at NIC.UA, on the free plan ([research D1](./research.md#d1--email-delivery-service-resend-through-its-http-api-called-with-the-standard-library)). This is the choice the technical requirements name, within the constitution's "SMTP or transactional-email API" option, so no amendment is needed. |
| — | Application Layout | **PASS** | `core/`: settings (`config.py`), pure security helpers (`security.py`), the access dependency and allowlist (`auth.py`), and the templates' `current_user` context. `models/`: 4 tables. `schemas/auth.py`: form input models. `services/`: users, sessions, login, rate_limits, email, with all business logic there. `routers/auth.py`: thin handlers. `templates/pages/login.html` and `login_code.html`, plus the header in `layouts/base.html`. |
| — | Operational Constraints | **PASS** | One image, configured only by environment variables. Migrations still run in the entrypoint. A misconfiguration refuses to start. A database outage on the login pages renders a friendly 503 page, and no stack trace reaches users. |
| — | Development Workflow gate 3 (PR gates) | **PASS** | CI stays green-or-blocked on the same two contexts. The new tables come with a migration. New and changed routes have access tests (anonymous denied or allowed per the allowlist, signed-in allowed). No secret is in the diff: the CI dummy values are labelled fakes. The README is updated in the same PR (FR-044, Workflow §5). |

**New runtime dependency** (Principle II requires a justification):

| Dependency | Why it is needed now | Why it is the minimum |
|---|---|---|
| `python-multipart` | The login and logout forms post `application/x-www-form-urlencoded` bodies. FastAPI's `Form(...)` and Starlette's `request.form()` both refuse to parse forms without it. | It is the parser FastAPI documents for forms: small, pure Python, no transitive dependencies. Hand-parsing bodies with `urllib.parse` would reimplement a security-relevant parser. |

**New infrastructure dependencies**:

| Dependency | Where | Why it is the minimum |
|---|---|---|
| Resend free account + verified domain | production email | Named by the technical requirements. HTTP API on port 443, free plan far above need. |
| DNS records at NIC.UA (DKIM, SPF/MX on the bounce subdomain, DMARC) | domain registrar | Required for domain verification and inbox placement (FR-038, SC-002). |

**Post-Phase 1 re-check**: **PASS with the recorded deviations**. No verdict changed after writing
[data-model.md](./data-model.md), the [contracts](./contracts/) and
[quickstart.md](./quickstart.md). The design stayed inside the stack table and the layout. It
added exactly one dependency and no engine-specific SQL, and it did not alter `/healthz`. Three
design choices went beyond the spec's minimum without adding scope:

- moving code issuance into the background task makes FR-010's equal response structural, not
  just "send in the background" (V);
- hashing rate-limit keys keeps unregistered addresses and client IPs out of the database (V);
- the CI image job signs in through the console backend, which turns "sessions survive a restart"
  into a check on every PR (III).

## Project Structure

### Documentation (this feature)

```text
specs/004-email-otp-auth/
├── plan.md                      # This file (/speckit-plan command output)
├── spec.md                      # Feature specification (/speckit-specify)
├── research.md                  # Phase 0: D1…D15, decisions & rejected alternatives
├── data-model.md                # Phase 1: users, sessions, login_codes, rate_limit_hits; lifecycles; revision
├── quickstart.md                # Phase 1: Resend/DNS/Render bootstrap, local sign-in, validation V1…V10
├── contracts/
│   ├── http-routes.md           # Phase 1: access rule + allowlist, /login, /login/code, /logout, protected /
│   ├── auth-services.md         # Phase 1: internal service interfaces + behaviour matrix
│   ├── email-sender.md          # Phase 1: EmailSender protocol, console/memory/resend, message text
│   ├── configuration.md         # Phase 1: EMAIL_BACKEND, SECRET_KEY, ADMIN_EMAILS, RESEND_API_KEY, EMAIL_FROM rules
│   └── pipeline.md              # Phase 1: render.yaml, checks.yml image job, deploy.yml, verify_private.sh
├── checklists/
│   └── requirements.md          # Spec quality checklist
└── tasks.md                     # Phase 2 output (/speckit-tasks, NOT created here)
```

### Source Code (repository root)

```text
pyproject.toml                      # CHANGED: + python-multipart
uv.lock                             # CHANGED: regenerated by `uv add python-multipart`
render.yaml                         # CHANGED: + EMAIL_BACKEND=resend; SECRET_KEY, ADMIN_EMAILS, RESEND_API_KEY, EMAIL_FROM (sync: false)
README.md                           # CHANGED: new settings, local sign-in via console, private-by-default rule, status line
Dockerfile, .dockerignore           # unchanged

.github/workflows/
├── checks.yml                      # CHANGED: image job: two auth refusals; sign in via docker logs; restart keeps session; logout
├── ci.yml                          # unchanged
└── deploy.yml                      # CHANGED: drop uv/expected-revision/previous-boots; Verify data → Verify access control

scripts/
├── verify_private.sh               # NEW: `/` → 303 to /login?next=%2F, /login → 200 form, /healthz → 200
├── database_status.sh              # DELETED: the anonymous page no longer carries the status line
├── render_deploy.sh                # unchanged
├── wait_for_release.sh             # unchanged
└── setup_branch_protection.sh      # unchanged

migrations/versions/
└── YYYY_MM_DD_<rev>_create_auth_tables.py   # NEW: users, sessions, login_codes, rate_limit_hits (down: bba0b3665864)

app/
├── main.py                         # CHANGED: app-wide Depends(resolve_access); LoginRequired handler; lifespan: auth settings,
│                                   #          email sender, reconcile (+1 retry) → purge → boot; include auth router
├── core/
│   ├── config.py                   # CHANGED: + AuthSettings, resolve_auth_settings, AuthConfigError
│   ├── security.py                 # NEW: normalize/validate email, codes, token + cookie signing, key hashing, safe_next_path, client_address
│   ├── auth.py                     # NEW: PUBLIC_ROUTES, resolve_access, LoginRequired, CurrentUser, set/clear session cookie
│   ├── db.py, migrations.py        # unchanged
│   └── templates.py                # CHANGED: context processor exposing `current_user`
├── models/
│   ├── __init__.py                 # CHANGED: + User, UserSession, LoginCode, RateLimitHit
│   ├── user.py                     # NEW: User, Role(StrEnum) = {ADMIN}
│   ├── user_session.py             # NEW: UserSession (table `sessions`)
│   ├── login_code.py               # NEW: LoginCode
│   └── rate_limit_hit.py           # NEW: RateLimitHit
├── schemas/
│   └── auth.py                     # NEW: EmailSubmission, CodeSubmission (validated in handlers → friendly errors)
├── services/
│   ├── users.py                    # NEW: get_active_user_by_email, reconcile_admins, ReconcileResult
│   ├── sessions.py                 # NEW: create_session, get_session_user, delete_session
│   ├── login.py                    # NEW: issue_code, verify_code, deliver_login_code, purge_expired
│   ├── rate_limits.py              # NEW: allow_code_request
│   ├── email.py                    # NEW: EmailMessage, EmailSender, Console/Memory/Resend senders, build_email_sender, login_code_message
│   ├── questions.py, database_status.py   # unchanged
├── routers/
│   ├── auth.py                     # NEW: GET/POST /login, POST /login/code, POST /logout
│   ├── pages.py                    # unchanged (protected by the app-wide dependency)
│   └── health.py                   # unchanged (allowlisted; skips the session lookup)
└── templates/
    ├── layouts/base.html           # CHANGED: header shows email + logout form when signed in
    └── pages/
        ├── login.html              # NEW: step 1 (email), with error/limit/unavailable messages
        ├── login_code.html         # NEW: step 2 (code, send a new code, use a different email)
        ├── home.html, error.html   # unchanged

tests/
├── conftest.py                     # CHANGED: autouse auth env (memory backend), ADMIN_EMAILS, `outbox`, `admin_client`
├── unit/
│   ├── test_auth_config.py         # NEW: configuration rules C1–C8, W1–W3, no values in messages
│   ├── test_security.py            # NEW: hashing, signing, tokens, email rules, client_address
│   ├── test_safe_next.py           # NEW: open-redirect table
│   └── test_email.py               # NEW: message text, console format, memory outbox, Resend via fake post
└── integration/
    ├── test_login_flow.py          # NEW: end-to-end via outbox + US1 scenarios + edge cases
    ├── test_login_privacy.py       # NEW: equal responses/timing, rate limits, generic messages, send failure
    ├── test_sessions.py            # NEW: logout, replay, expiry, deactivation, tampering, cookie flags
    ├── test_admin_reconcile.py     # NEW: S1–S6, startup logging counts only, removal via restart
    ├── test_auth_services.py       # NEW: L1–L7, R1–R4, P1–P2, X1
    ├── test_routes.py              # CHANGED: write routes = exactly login/logout; anonymous sweep; allowlist exact
    ├── test_home.py                # CHANGED: `client` → `admin_client`; header assertions; logout form allowed
    ├── test_health.py              # CHANGED: DB-failure test uses `admin_client`; /healthz with a cookie does no lookup
    └── test_startup.py             # CHANGED: + refused on Render without auth settings, not counted
```

**Structure Decision**: the existing single FastAPI application and the constitution's `app/`
layout, extended in place. Security primitives with no I/O go in `core/security.py`, so they are
unit-testable without a database. The request-level access rule goes in `core/auth.py` beside the
settings and database modules, because it is infrastructure every router shares. Everything with
a business rule (codes, limits, sessions, reconciliation, email) goes in `services/`. There is no
new top-level directory.

## Complexity Tracking

Governance requires every deviation and residual risk to be visible here.

| Deviation / residual risk | Why it is needed | Simpler alternative rejected because |
|---|---|---|
| **Principle IV** (continuing from milestone 3): routes require "signed in", not a named role, and the question service's write functions still enforce no authorization. **Ends when**: milestone 5 adds role dependencies built on `CurrentUser` and gives every non-public route an explicit role; milestone 6 puts a teacher check in front of the question writes, with allowed and denied tests. | Roles are milestone 5 by the ladder, and the spec forbids role checks now (FR-047). Only administrators exist, so "signed in" currently equals "administrator". The question writes still have no HTTP caller: `test_routes.py` pins the write routes to login and logout. | A `require_role("admin")` on every route now would be milestone-5 work smuggled in (Principle I), and it would be rewritten when real roles land. |
| **Principle V / CSRF**: `SameSite=Lax` is the only CSRF defence, and login CSRF (being signed in as the attacker) is accepted. **Ends when**: milestone 5, which introduces data-changing pages and HTMX, adds a CSRF token or an Origin check (a spec obligation). | The spec's assumption, based on the technical requirements, is that the only state-changing actions are login and logout. `Lax` blocks cross-site `POST`s carrying the session cookie, so logout cannot be forced cross-site. Being signed in as an attacker exposes nothing yet, because there is nothing to enter. | A synchronizer-token system now means a token store or signed hidden fields on three forms, in scope that milestone 5 must redesign for HTMX anyway. |
| **Per-client limit is spoofable** (research D8): Render appends to a client-supplied `X-Forwarded-For`, and the first entry is used. | Behind the proxy the socket peer is shared by everyone. The first entry is what Render documents as the client, and no spoof-proof header is guaranteed. | *Last entry*: a Cloudflare edge address shared by many clients, which would let one client lock everyone out. The bounds that matter (SC-005: per-email and per-code limits) do not depend on the client address. Quickstart V9 measures the real behaviour once. |
| **Principle III — release-time data check downgraded**: `deploy.yml` no longer asserts "boot count rose, revision = head" on production. It asserts "new commit live" and "`/` is private". The data check moves to the per-PR `image` job (real container, sign-in, restart) and a once-before-acceptance production witness (quickstart V8). | The home page is private by design (spec assumption). A release cannot sign in without a real inbox. Storing a production session cookie in GitHub would be a standing credential. The startup guard still proves "database reachable and at head" for any instance that answers. | *Boot count in `/healthz`*: reverses milestone 2's deliberate three-key, no-detail contract for a public endpoint. *A public status page*: a new address outside FR-028's allowlist. *A CI login bypass*: forbidden (FR-034). |
| **Principle III — manual, once-per-milestone checks**: real-inbox sign-in (V5), administrator removal in production (V6), deliverability across providers (V7, SC-002), boot-count witness (V8), spoofing probe (V9) and the secrets review (V10, SC-008). | Each is about the real mail ecosystem, the real platform or real logs, not about application behaviour. The suite already covers the application side of each. | Automating them would need real inboxes and production credentials in CI, a larger standing risk than the checks remove. |
| **Refused start after migrating**: on Render, a missing secret stops uvicorn **after** the entrypoint has already applied the new migration. | The entrypoint must migrate before uvicorn (milestone 3, D4), and settings are validated by the app. | Validating auth settings inside `alembic/env.py` would couple migrations to unrelated configuration. The revision is additive, so the previous release keeps serving on the new schema (data-model §7), and the rollout gate (quickstart B1–B3) makes this a safety net, not a path. |
