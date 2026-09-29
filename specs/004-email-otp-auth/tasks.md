---

description: "Task list for Email Code Authentication (Milestone 4)"
---

# Tasks: Email Code Authentication (Milestone 4)

**Input**: Design documents from `/specs/004-email-otp-auth/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle III is non-negotiable, FR-045 lists the required
automated checks, and [plan.md](./plan.md) names the test modules: unit `test_auth_config.py`,
`test_security.py`, `test_safe_next.py`, `test_email.py`; integration `test_login_flow.py`,
`test_login_privacy.py`, `test_sessions.py`, `test_admin_reconcile.py`, `test_auth_services.py`;
changes to `test_routes.py`, `test_home.py`, `test_health.py`, `test_startup.py`. Every
database-touching test runs on **both** engines (`[sqlite]` and `[postgresql]`) through the
existing parametrised `database_url` fixture. Six checks are once-per-milestone **manual
procedures** (quickstart B1–B3, V5–V10; see the plan's *Complexity Tracking*). Those tasks are
marked **[MANUAL]**.

**Organization**: Tasks are grouped by user story so each can be implemented and validated
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US6)
- **[MANUAL]**: A human procedure or a platform-console action; not automatable at this milestone
- Include exact file paths in descriptions

## Path Conventions

Single server-rendered web application, repository root: `app/` (application), `migrations/`
(Alembic), `tests/` (suite), `scripts/` (release helpers), `.github/workflows/` (pipeline), and
`render.yaml` / `pyproject.toml` / `README.md` at the root. See the plan's *Project Structure* for
every new and changed file.

**Running the PostgreSQL half locally** (needed by every "run the suite" task below):

```bash
docker run -d --name sc-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:17
export TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres
```

**Two facts about the installed FastAPI 0.141 that the plan does not spell out** (verified while
generating these tasks; they shape T039 and T035):

1. The built-in `/openapi.json`, `/docs`, `/docs/oauth2-redirect` and `/redoc` routes are plain
   Starlette `Route`s. An application-wide `Depends(resolve_access)` does **not** run for them, so
   they would stay public outside the five-entry allowlist (FR-028). They must be switched off.
2. `app.routes` holds included routers as `fastapi.routing._IncludedRouter` wrappers, which have
   no `.path` or `.methods`. The real routes are in `wrapper.original_router.routes`, with
   `wrapper.include_context.prefix` prepended. The current `test_every_route_is_read_only` skips
   those wrappers, so today it checks only the docs routes. The new sweep must flatten them.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the milestone 3 baseline and add the one new runtime dependency

- [ ] T001 Confirm the milestone 3 baseline is green from the repository root with `TEST_POSTGRES_URL` set: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`. All four must pass before any change is made
- [ ] T002 Add the one new runtime dependency with `uv add python-multipart`, which updates `pyproject.toml` and regenerates `uv.lock` ([plan](./plan.md#constitution-check), *New runtime dependency*). **No** other runtime or dev dependency is added: no `itsdangerous`, no `resend`, no runtime `httpx`, no `pydantic-settings`, no `slowapi` ([research D1, D3, D5, D7](./research.md))

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Everything every story rides on: the authentication settings and their startup
validation, the pure security helpers, the four tables and their migration, the email-sender
interface with the `console` and `memory` backends, user lookup and "listed admins exist", the
session store, the application-wide user resolver (resolving only, **not yet enforcing**), the
`current_user` template context, and the test fixtures (`outbox`, `admin_client`).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. At the end of this
phase the home page is still public and every milestone-3 test still passes unchanged.

### Tests (write first, confirm they FAIL)

- [ ] T003 [P] Write `tests/unit/test_auth_config.py` covering every row of [contracts/configuration.md](./contracts/configuration.md#rules), calling `resolve_auth_settings(environ)` with an explicit dict (never `os.environ`): C1 unknown `EMAIL_BACKEND` everywhere; C2 unset/`console`/`memory` with `RENDER` set; C3 `SECRET_KEY` unset on Render; C4 a 31-character `SECRET_KEY` refused locally **and** on Render, 32 accepted; C5 `ADMIN_EMAILS` empty (including `" , ,"`) on Render; C6 malformed entries reported as `ADMIN_EMAILS entry <n> is not a valid email address.` with the 1-based position counted over non-empty entries, one line per bad entry, everywhere; C7 `resend` (or Render) without `RESEND_API_KEY`; C8 `resend` (or Render) without `EMAIL_FROM` or with a malformed address part, and `Display Name <addr@domain>` accepted. W1–W3: each warning emitted to the `uvicorn.error` logger at WARNING when running locally without the setting (use `caplog`), and **not** emitted on Render. Assert: empty strings count as unset; with no variables at all locally the result is `email_backend == "console"`, the fixed development key, `admin_emails == ()`, `production is False`; `ADMIN_EMAILS=" B@x.org, a@x.org ,A@X.ORG,"` → `("a@x.org", "b@x.org")` (trimmed, lowercased, de-duplicated, sorted); a Render environ with every variable missing yields **one** `AuthConfigError` whose message starts with `Invalid authentication configuration:` and names all five settings in the order C1…C8; `AuthConfigError` subclasses `RuntimeError`. **No-echo rule**: plant recognisable values (`SECRET_KEY="plantedsecret-0123456789-abcdefghij"` short and long variants, `RESEND_API_KEY="re_planted_key"`, `ADMIN_EMAILS="planted@@bad"`, `EMAIL_FROM="planted-from"`) and assert none of them appears in `str(exc)`, in any `caplog` record, or in `repr(settings)` for a valid set (`repr` masks `secret_key` and `resend_api_key`)
- [ ] T004 [P] Write `tests/unit/test_security.py` for every function of `app/core/security.py` in [contracts/auth-services.md](./contracts/auth-services.md#appcoresecuritypy-pure-no-io): `normalize_email("  A@X.Org ") == "a@x.org"`; an `is_valid_email` table from [data-model §1](./data-model.md#1-user--table-users-appmodelsuserpy) ("3 to 254 characters, exactly one `@`, a non-empty local part of at most 64 characters, and a domain containing at least one `.` whose labels are non-empty. No whitespace and no control characters") with accepted and rejected cases at each boundary (254/255 total, 64/65 local, `a@b`, `a@.b`, `a@b.`, `a@b..c`, `a b@c.d`, `a@b@c.d`, a `\x00`); `generate_code()` always matches `^[0-9]{6}$` and produces leading zeros (monkeypatch `secrets.randbelow` to return `42` → `"000042"`); `hash_code` returns 64 lowercase hex characters, is deterministic, and differs when the key, the email or the code changes; `new_session_token()` values are distinct and ≥ 43 characters; `hash_token` is 64-hex SHA-256; `sign_cookie_value`/`unsign_cookie_value` round-trip, and `unsign` returns `None` (never raises) for a changed token, a changed signature, a value signed with another key, an empty string, no `.`, several `.`, and non-ASCII input; a code hash and a cookie signature over the same input differ (domain separation, [research D2](./research.md#d2--codes-6-digits-from-secrets-keyed-hash-bound-to-the-address-newest-code-wins)); `hash_rate_limit_key` is 64 hex and differs per bucket; `client_address` with a minimal fake request: `trust_forwarded=True` returns the first `X-Forwarded-For` entry trimmed (`" 203.0.113.7 , 10.0.0.1"` → `"203.0.113.7"`) and falls back to the socket peer when the header is absent or empty; `trust_forwarded=False` ignores the header; no `request.client` → `"unknown"` ([research D8](./research.md#d8--the-client-address-for-the-per-client-limit))
- [ ] T005 [P] Write `tests/unit/test_safe_next.py` with the open-redirect table from [research D12](./research.md#d12--safe-return-to-addresses): kept unchanged: `/`, `/questions`, `/a/b?x=1&y=%2F`, a 2,048-character path; replaced by `/`: `None`, `""`, a 2,049-character path, `questions`, `//evil.example`, `///evil.example`, `/\evil.example`, `\\evil.example`, `https://evil.example/`, `http:/evil.example`, `javascript:alert(1)`, `/ok\x00`, `/a b`, `/a\tb`, `/login`, `/login?next=/x`, `/login/code`, `/logout`
- [ ] T006 [P] Write `tests/unit/test_email.py` (the `console`/`memory` half; the Resend half is T064): `login_code_message("a@x.org", "042917", 20)` has `to == "a@x.org"`, subject exactly `Your Student Competitions sign-in code` (no digits in it), a body containing the line `Your Student Competitions sign-in code is: 042917`, `20 minutes`, single use, and the "ignore this email" note, and **no** `http`, `www.` or `://` ([contracts/email-sender.md](./contracts/email-sender.md#the-login-message)); `ConsoleEmailSender().send(msg)` prints exactly the block in *Console output format* (start marker `======== EMAIL (console backend: not sent) ========`, `To:`, `Subject:`, blank line, body, `======== END EMAIL ========`), checked with `capsys`; `MemoryEmailSender` appends to `outbox` in order and never raises; `build_email_sender` returns a `ConsoleEmailSender` for `console` and a `MemoryEmailSender` for `memory`, given an `AuthSettings`

### Implementation

- [ ] T007 Create `app/core/security.py` (pure, no I/O, no import from `app.core.config`) with the functions and constants of [contracts/auth-services.md](./contracts/auth-services.md#appcoresecuritypy-pure-no-io): `normalize_email`, `is_valid_email` (the structural rule quoted in T004; no DNS, not full RFC 5322), `generate_code` (`f"{secrets.randbelow(1_000_000):06d}"`), `hash_code(secret_key, email, code)` = hex `HMAC-SHA256(secret_key, "login-code\x00" + email + "\x00" + code)`, `new_session_token` (`secrets.token_urlsafe(32)`), `hash_token` (hex SHA-256), `sign_cookie_value`/`unsign_cookie_value` (`<token>.<base64url(HMAC-SHA256(secret_key, "session\x00" + token))>`, `hmac.compare_digest`, `None` on any malformation), `hash_rate_limit_key(secret_key, bucket, key)` = hex `HMAC-SHA256(secret_key, "rate-limit\x00" + bucket + "\x00" + key)`, `safe_next_path` ([research D12](./research.md#d12--safe-return-to-addresses)) and `client_address(request, trust_forwarded)` ([research D8](./research.md#d8--the-client-address-for-the-per-client-limit)). Also define `SESSION_COOKIE_NAME = "sc_session"`, `SESSION_TTL = timedelta(days=14)` and `MIN_SECRET_KEY_LENGTH = 32`. No function logs anything. Make T004 and T005 pass
- [ ] T008 Extend `app/core/config.py` (depends on T007) with `AuthSettings` (frozen dataclass: `production: bool`, `email_backend: Literal["console", "memory", "resend"]`, `secret_key: str`, `admin_emails: tuple[str, ...]`, `resend_api_key: str | None`, `email_from: str | None`; a custom `__repr__` that masks `secret_key` and `resend_api_key`), `AuthConfigError(RuntimeError)`, a module-level development-only `DEV_SECRET_KEY` constant (≥ 32 characters, obviously labelled insecure; constant so local sessions survive `--reload` and container restarts), and `resolve_auth_settings(environ: Mapping[str, str] = os.environ) -> AuthSettings` implementing rules C1–C8 and warnings W1–W3 of [contracts/configuration.md](./contracts/configuration.md#rules) **verbatim**, collecting every violation and raising one error whose message is `Invalid authentication configuration:` followed by one line per violation in order C1…C8. `production` means `RENDER` is set (non-empty). Parse `ADMIN_EMAILS` by splitting on `,`, trimming, lowercasing, ignoring empty entries, validating each with `is_valid_email` (report by 1-based position only), de-duplicating and sorting. Validate `EMAIL_FROM`'s address part with `email.utils.parseaddr` + `is_valid_email`. Warnings go to `logging.getLogger("uvicorn.error")`. No message, warning or `repr` ever contains a value. Update the module docstring to name the new responsibility. Make T003 pass
- [ ] T009 [P] Create `app/models/user.py`: `class Role(StrEnum)` with only `ADMIN = "admin"`, and table model `User` (table `users`) per [data-model §1](./data-model.md#1-user--table-users-appmodelsuserpy): `id` Integer PK autoincrement; `email` `String(254)` "NOT NULL, **unique** (`uq_users_email`)" and "always stored normalised: trimmed, lowercased"; `role` `String(20)` NOT NULL, values from `Role`, with **no** CHECK constraint; `is_active` Boolean NOT NULL; `created_at` and `updated_at` `UTCDateTime` NOT NULL (from `app.core.db`)
- [ ] T010 [P] Create `app/models/user_session.py`: table model `UserSession` with `__tablename__ = "sessions"` per [data-model §2](./data-model.md#2-usersession--table-sessions-appmodelsuser_sessionpy): `id` Integer PK; `user_id` Integer "NOT NULL, FK → `users.id`, indexed"; `token_hash` `String(64)` "NOT NULL, **unique**"; `created_at` `UTCDateTime` NOT NULL; `expires_at` `UTCDateTime` "NOT NULL, indexed". Named `UserSession` to avoid colliding with `sqlmodel.Session`
- [ ] T011 [P] Create `app/models/login_code.py`: table model `LoginCode` (table `login_codes`) per [data-model §3](./data-model.md#3-logincode--table-login_codes-appmodelslogin_codepy): `id` Integer PK; `user_id` Integer "NOT NULL, FK → `users.id`, indexed"; `code_hash` `String(64)` NOT NULL; `created_at` `UTCDateTime` NOT NULL; `expires_at` `UTCDateTime` "NOT NULL, indexed"; `attempts` Integer "NOT NULL, default 0"; `used_at` `UTCDateTime` NULL
- [ ] T012 [P] Create `app/models/rate_limit_hit.py`: table model `RateLimitHit` (table `rate_limit_hits`) per [data-model §4](./data-model.md#4-ratelimithit--table-rate_limit_hits-appmodelsrate_limit_hitpy): `id` Integer PK; `bucket` `String(32)` NOT NULL; `key_hash` `String(64)` NOT NULL; `created_at` `UTCDateTime` NOT NULL; and a composite index declared **explicitly by name** `ix_rate_limit_hits_bucket_key_hash_created_at` on `(bucket, key_hash, created_at)` in `__table_args__` (the naming convention's `ix` pattern covers only the first column)
- [ ] T013 Update `app/models/__init__.py` to import and export `User`, `Role`, `UserSession`, `LoginCode` and `RateLimitHit` alongside `BootCounter` and `Question`, so `SQLModel.metadata` is complete for Alembic and the drift test (depends on T009–T012)
- [ ] T014 Generate the migration with `uv run alembic revision --autogenerate -m "create auth tables"` against a local SQLite database at head, producing `migrations/versions/YYYY_MM_DD_<rev>_create_auth_tables.py` with `down_revision = "bba0b3665864"`. Review it by hand per [data-model §7](./data-model.md#7-schema-version-introduced-by-this-milestone): creates `users`, `sessions`, `login_codes`, `rate_limit_hits` with the constraints and indexes of T009–T012 (constraint names from the `app/core/db.py` naming convention, the composite index by its explicit name); **no data** and no seeded user; portable types only (no dialect-specific SQL); `downgrade()` drops the four tables in reverse dependency order (`rate_limit_hits`, `login_codes`, `sessions`, `users`). Run `uv run pytest tests/integration/test_migrations.py` on both engines: the drift, stairway and single-head tests must pass unchanged
- [ ] T015 [P] Create `app/services/email.py` per [contracts/email-sender.md](./contracts/email-sender.md) and [research D6](./research.md#d6--email-sending-one-small-protocol-three-implementations-chosen-at-startup): frozen dataclass `EmailMessage(to, subject, text)`; `EmailSender(Protocol)` with `send(message) -> None`; `EmailDeliveryError(RuntimeError)`; `ConsoleEmailSender` (`print(..., flush=True)` of the exact block in *Console output format*; the **only** code path that ever outputs a body); `MemoryEmailSender` (`self.outbox: list[EmailMessage]`); `login_code_message(email, code, minutes) -> EmailMessage` (subject `Your Student Competitions sign-in code`, body with `Your Student Competitions sign-in code is: <code>`, `It is valid for <minutes> minutes and can be used once.`, `If you did not try to sign in, you can ignore this email.`, no URL); and `build_email_sender(settings: AuthSettings) -> EmailSender` mapping `console` and `memory` (the `resend` branch raises `NotImplementedError("resend backend arrives in T067")` until US6 replaces it). Make T006 pass
- [ ] T016 [P] Create `app/services/users.py` with `get_active_user_by_email(session, email) -> User | None` and `ReconcileResult` (frozen dataclass `created, reactivated, deactivated, unchanged`, all `int`), and `reconcile_admins(session, emails, now=utc_now()) -> ReconcileResult` implementing **step 1 only** of [research D13](./research.md#d13--administrator-reconciliation-idempotent-concurrency-safe-counts-only): for each listed (already normalised, de-duplicated) address, insert an active `Role.ADMIN` user if missing (**created**), activate an inactive one and set `updated_at = now` (**reactivated**), leave an active admin untouched (**unchanged**); commit; `deactivated` is always `0` until US3 (T049) adds steps 2–3. `updated_at` changes only on rows that actually change. No function logs an address
- [ ] T017 [P] Create `app/services/sessions.py` with `create_session(session, user, now=utc_now()) -> str` (new token via `new_session_token`, inserts `UserSession(token_hash=hash_token(token), created_at=now, expires_at=now + SESSION_TTL)`, commits, returns the **plain token**; "the one place a token is created") and `get_session_user(session, token, now=utc_now()) -> User | None` doing **one** query: session by `token_hash`, `expires_at > now`, joined to a user with `is_active = true` ([contracts/auth-services.md](./contracts/auth-services.md#appservicessessionspy), [data-model §2](./data-model.md#2-usersession--table-sessions-appmodelsuser_sessionpy) validity rule)
- [ ] T018 Create `app/core/auth.py` (depends on T007, T008, T017) with: `resolve_access(request: Request) -> None`, a **sync** dependency that (a) returns immediately without reading the cookie or opening a database session when the matched route (`request.scope["route"]`) is `GET`/`HEAD /healthz`; (b) otherwise sets `request.state.user = None`, reads the `sc_session` cookie, calls `unsign_cookie_value(request.app.state.settings.secret_key, value)` and, **only if the signature is valid**, opens `Session(request.app.state.engine)` and sets `request.state.user = get_session_user(...)`; (c) catches `SQLAlchemyError` from that lookup, logs the exception **type only**, and leaves the user anonymous. It does **not** yet refuse anonymous requests; US2 (T040) adds `PUBLIC_ROUTES` and the refusal. Also add `CurrentUser = Annotated[User | None, Depends(get_current_user)]` (returns `request.state.user`; milestone 5 builds role dependencies on it), `set_session_cookie(response, settings, token)` (`sc_session=<signed>; Max-Age=1209600; Path=/; HttpOnly; SameSite=Lax`, plus `Secure` when `settings.production`) and `clear_session_cookie(response, settings)` (same name, path and flags, `Max-Age=0`) per [contracts/http-routes.md](./contracts/http-routes.md#session-cookie). Never log a cookie value, token or hash
- [ ] T019 [P] Change `app/core/templates.py` to pass a context processor to `Jinja2Templates(directory=..., context_processors=[...])` that returns `{"current_user": getattr(request.state, "user", None)}`, so every template (layout header, error page) can read the signed-in user without each handler passing it ([research D4](./research.md#d4--deny-by-default-access-one-application-level-dependency-and-an-explicit-allowlist)); update the module docstring
- [ ] T020 Change `app/main.py` (depends on T008, T015–T018): in `lifespan`, after `resolve_database_url`, call `resolve_auth_settings(os.environ)` **before** creating the engine; build the sender with `build_email_sender(settings)`; after `ensure_at_head`, run `reconcile_admins(session, settings.admin_emails)` in its own `Session` and log `Administrators reconciled: %d created, %d reactivated, %d deactivated, %d unchanged` (counts only) on `uvicorn.error`; then `record_boot` as today. Store `app.state.settings` and `app.state.email_sender` next to `app.state.engine`. Register the resolver application-wide: `FastAPI(..., dependencies=[Depends(resolve_access)])` (it must be set **before** any `include_router` call, because included routers capture app dependencies at include time). Update the module docstring with the new startup order ([contracts/configuration.md](./contracts/configuration.md#startup-order-fr-043); `purge_expired` is inserted by US4, the retry by US3)
- [ ] T021 Change `tests/conftest.py` per [research D15](./research.md#d15--tests-an-anonymous-client-an-admin_client-with-a-directly-created-session): extend the autouse `_isolate_from_real_databases` fixture (rename to `_isolate_environment`) to also `delenv` `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`, `EMAIL_FROM` and `setenv("EMAIL_BACKEND", "memory")`; make `client` set `ADMIN_EMAILS=admin@example.com` (constant `ADMIN_EMAIL` exported for tests) before opening `TestClient(app)`, still anonymous; add `outbox` (returns `app.state.email_sender.outbox`, asserting the sender is a `MemoryEmailSender`) and `admin_client` (its own `TestClient(app)` on the same `database_url`, which looks up the reconciled `admin@example.com` user through `Session(app.state.engine)`, calls `create_session`, and sets the cookie `sc_session=sign_cookie_value(app.state.settings.secret_key, token)` on the client). Document in the fixture docstring that this is the **only** sign-in shortcut, lives only in `tests/`, and is not reachable in a running application (FR-034, FR-046). Update the module docstring
- [ ] T022 Run `uv run ruff check .`, `uv run ruff format --check .` and the full suite on both engines. Everything added so far is green and every milestone-3 test passes **unchanged** (the home page is still public at this checkpoint)

**Checkpoint**: Foundation ready. Settings validate, tables exist, listed admins exist after
start, sessions can be created and are resolved on every request, and tests have `outbox` and
`admin_client`.

---

## Phase 3: User Story 1 - An administrator signs in with a code sent by email (Priority: P1) 🎯 MVP

**Goal**: The two-step login (email → code) works end to end: a code is issued and emailed after
the response, the correct code creates a server-side session and redirects to `next` or `/`, and
the header shows the email and a **Log out** form that ends the session.

**Independent Test**: With `ADMIN_EMAILS=admin@example.com` and the `memory` backend, request a
code, read it from the outbox, submit it, and land on `/` signed in with the header showing the
address ([quickstart V2](./quickstart.md#v2-the-automated-suite-proves-the-flow-the-protection-and-the-rules-all-user-stories-fr-045-fr-046-sc-003-sc-004-sc-005-sc-007)); locally, the same with the code from the console ([V1](./quickstart.md#v1-a-developer-signs-in-locally-from-a-clean-checkout-us1-123-us6-1-fr-042-fr-044-sc-001-sc-009)).

### Tests for User Story 1 (write first, confirm they FAIL)

- [ ] T023 [P] [US1] Create `tests/integration/test_login_flow.py` (every test on both engines via `client`/`outbox`/`session`) covering US1 and [contracts/http-routes.md](./contracts/http-routes.md) for `/login`, `/login/code`, `/logout`: **end to end** (`GET /login` 200 with `name="email"`, `action="/login"`, hidden `next`; `POST /login` 200 step 2 with the text "If this address belongs to an account, we have sent a code to it. The code is valid for 20 minutes."; the outbox holds one message to `admin@example.com`; the 6-digit code extracted from its body; `POST /login/code` → 303 to `/`, `Set-Cookie: sc_session=…`; `GET /` → 200 with the address and `action="/logout"` in the header); **US1-2** `next=/?x=1` carried through both steps lands on exactly `/?x=1`; **US1-4** `"  Admin@Example.COM "` gets a code; **US1-5** reusing a consumed code → 400 with "Invalid or expired code. Request a new code if needed."; **US1-6** a code whose `expires_at` is moved into the past through the `session` fixture → 400 with the same message; **US1-7** step 2 contains a form posting hidden `email`/`next` to `/login` with a "Send a new code" button and a link "Use a different email" to `/login?next=…`; **L7** the correct code with surrounding spaces succeeds; **double submit** the same correct code posted twice → first 303, second 400, exactly one `sessions` row; **invalid email** empty or `not-an-email` → 400 step 1 with "Enter a valid email address.", the typed value kept, outbox empty, zero `login_codes` rows; **unknown address** → the same 200 page and an empty outbox; **tampered hidden email** (admin's code posted with `email=other@example.com`) → 400; **email has no link** (`http` absent from the body); **database unavailable** (monkeypatch the service used by each route to raise `OperationalError`) → 503 with "Sign-in is temporarily unavailable. Please try again in a moment." on `POST /login` and on `POST /login/code`, no stack trace text, nothing sent; **logout** → 303 `Location: /login`, cookie cleared (`Max-Age=0`), the `sessions` row gone
- [ ] T024 [P] [US1] Create `tests/integration/test_auth_services.py` with behaviour-matrix rows **L1, L2, L4, L6** of [contracts/auth-services.md](./contracts/auth-services.md#behaviour-matrix-each-row-is-a-test-on-sqlite-and-postgresql) against the both-engines `session` fixture, moving time via the `now` parameter (no patching): L1 `issue_code` twice → only the second verifies, one row left; L2 correct code → user returned, `used_at` set, second call `None`; L4 `verify_code(now = issued + 20 min)` → `None` (expiry inclusive); L6 `a`'s code submitted for `b` → `None`. Also assert `issue_code` returns 6 digits, the stored `code_hash` is 64 hex and not the code, and `expires_at == now + 20 min`. Create users directly with `User(...)` in the test

### Implementation for User Story 1

- [ ] T025 [P] [US1] Create `app/schemas/auth.py` with `EmailSubmission` (`email: str`, `next: str = "/"`; a validator that applies `normalize_email` and rejects `not is_valid_email`) and `CodeSubmission` (`email`, `code`, `next`; the code stripped of surrounding whitespace; **no** digit-format rejection, because a malformed code must still count as a wrong attempt against a live code per [research D2](./research.md#d2--codes-6-digits-from-secrets-keyed-hash-bound-to-the-address-newest-code-wins)). Handlers validate through these models so failures re-render the page instead of FastAPI's 422 JSON ([research D11](./research.md#d11--plain-forms-no-redirect-between-the-steps-the-email-travels-in-a-hidden-field))
- [ ] T026 [US1] Create `app/services/login.py` with `CODE_TTL = timedelta(minutes=20)`, `CODE_MAX_ATTEMPTS = 5` and, per [contracts/auth-services.md](./contracts/auth-services.md#appservicesloginpy) and [research D2](./research.md#d2--codes-6-digits-from-secrets-keyed-hash-bound-to-the-address-newest-code-wins): `issue_code(session, secret_key, user, now=…) -> str` (deletes the user's rows with `used_at IS NULL`, inserts a new `LoginCode`, commits, returns the plain code); `verify_code(session, secret_key, email, code, now=…) -> User | None` (looks up the **active** user and their single live code — `used_at IS NULL AND attempts < 5 AND expires_at > now` — compares `hash_code(...)` with `hmac.compare_digest`; on a match, consumes with one conditional `UPDATE login_codes SET used_at = :now WHERE id = :id AND used_at IS NULL AND attempts < 5 AND expires_at > :now` and returns the user only if exactly one row changed; on a mismatch, `UPDATE … SET attempts = attempts + 1 WHERE id = :id AND attempts < 5`; commits; `None` in every other case); and `deliver_login_code(engine, sender, settings, email) -> None`, the background task of [research D10](./research.md#d10--step-1-does-identical-work-for-every-address-the-email-is-issued-and-sent-after-the-response): its own `Session(engine)`, `get_active_user_by_email`, and for an active user `issue_code` + `sender.send(login_code_message(email, code, 20))`; it catches **every** exception and logs `Login email not sent: %s` with only the exception type or, for `EmailDeliveryError`, its status message, never the address, code or body (FR-039). `purge_expired` is added by US4 (T055). Make T024 pass
- [ ] T027 [US1] Add `delete_session(session, token) -> None` to `app/services/sessions.py`: deletes the row with `token_hash = hash_token(token)` if present, commits, idempotent, touches no other session of the user (US4-6)
- [ ] T028 [P] [US1] Create `app/templates/pages/login.html` (extends `layouts/base.html`, Pico.css, **no** JavaScript, no HTMX): heading "Sign in"; an optional message block (`message` context variable) used for "Enter a valid email address.", "Too many attempts. Please try again later." and "Sign-in is temporarily unavailable. Please try again in a moment."; a `<form method="post" action="/login">` with `<input type="email" name="email" required autocomplete="email" value="{{ email }}">`, `<input type="hidden" name="next" value="{{ next }}">` and a submit button "Send code". Autoescaping only; no `|safe`
- [ ] T029 [P] [US1] Create `app/templates/pages/login_code.html` (step 2, never reachable by `GET`): the "If this address belongs to an account…" notice or the error message; a `<form method="post" action="/login/code">` with hidden `email` and `next` and `<input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]*" maxlength="6" required>` and a submit button; a second `<form method="post" action="/login">` with hidden `email` and `next` and a button "Send a new code"; a link "Use a different email" to `/login?next={{ next | urlencode }}` ([contracts/http-routes.md](./contracts/http-routes.md#post-login--request-a-code-also-send-a-new-code))
- [ ] T030 [US1] Create `app/routers/auth.py` with thin, **sync** handlers and `str = Form("")` parameters (depends on T025–T029): `GET /login` → 200 step 1 with `next = safe_next_path(next)`; `POST /login` → invalid email: 400 step 1 with the message and the typed value; otherwise `background_tasks.add_task(deliver_login_code, request.app.state.engine, request.app.state.email_sender, request.app.state.settings, email)` and 200 step 2 (the rate-limit check is inserted **before** this by US5, T061); `POST /login/code` → `verify_code(...)`, on a user: `create_session`, 303 to `safe_next_path(next)` with `set_session_cookie`; otherwise 400 step 2 with "Invalid or expired code. Request a new code if needed."; `POST /logout` → `delete_session` when the cookie unsigns, `clear_session_cookie`, 303 `/login` (also when anonymous). Every database call is wrapped so `SQLAlchemyError` yields 503 with the "temporarily unavailable" message on the same page, logged by exception type only. No handler logs an address, code, token or cookie
- [ ] T031 [US1] In `app/main.py`, `app.include_router(auth.router)` (after the app-wide dependency is set, T020)
- [ ] T032 [US1] Change `app/templates/layouts/base.html` so the header shows, when `current_user` is set, the application name, `{{ current_user.email }}` and `<form method="post" action="/logout"><button type="submit">Log out</button></form>`; when anonymous, the application name only ([contracts/http-routes.md](./contracts/http-routes.md#layout-header-every-page)). Add minimal header layout rules to `app/static/css/app.css` if needed (no horizontal scroll at phone width). The home page body and footer stay unchanged (FR-032)
- [ ] T033 [US1] Run the suite on both engines (T023, T024 green; milestone-3 tests still green). Then sign in locally by hand per [quickstart *Running locally*](./quickstart.md#running-locally-sign-in-with-the-code-from-the-console): `ADMIN_EMAILS=you@example.com uv run uvicorn app.main:app --reload`, copy the code from the console email, land on `/` with the address and **Log out** in the header, log out
- [ ] T034 [US1] [MANUAL] **After the milestone's first release is green**: validate [quickstart V5](./quickstart.md#v5-an-administrator-signs-in-on-production-with-a-real-inbox-us1-fr-009-fr-012-fr-032-fr-038-sc-001-manual-required-once) from a device outside the team's network: real email from `login@brainring.org.ua` with the code and no link; sign-in lands on `/` with the address in the header; the cookie is `HttpOnly`, `Secure`, `SameSite=Lax`; after **Log out**, *Back* + reload shows the login page

**Checkpoint**: The login flow works end to end with the memory outbox and the console. The home
page is **still public** (US2 makes it private).

---

## Phase 4: User Story 2 - Every page is private unless explicitly public (Priority: P2)

**Goal**: Deny by default. Every route outside the five-entry allowlist answers an anonymous
request with 303 to `/login?next=…`; the sweep test fails the build if a new route is unprotected
or the allowlist drifts; the pipeline checks sign in or check privacy instead of reading `/`
anonymously.

**Independent Test**: The route-table sweep in `tests/integration/test_routes.py` walks every
route and asserts anonymous → 303 to `/login` outside the allowlist (SC-003); CI's `image` job
signs in for real; the release's *Verify access control* sees `/` → 303 ([quickstart V3, V4](./quickstart.md#v3-the-packaged-image-signs-in-for-real-and-refuses-unsafe-production-configs-us6-4-fr-041-sc-010-automated-on-every-pr)).

**Depends on**: US1 (the login page must exist to redirect to, and CI signs in through it).

### Tests for User Story 2 (write first, confirm they FAIL)

- [ ] T035 [P] [US2] Rewrite `tests/integration/test_routes.py`: add a helper `iter_routes(app)` that yields `(path, methods, route)` for every route, descending into `fastapi.routing._IncludedRouter` wrappers (`wrapper.original_router.routes` with `wrapper.include_context.prefix` prepended) and skipping `Mount`s (see the note at the top of this file); replace `test_every_route_is_read_only` with `test_the_write_routes_are_exactly_login_and_logout` (the set of `(method, path)` with a method outside `{GET, HEAD}` equals `{("POST", "/login"), ("POST", "/login/code"), ("POST", "/logout")}`; FR-047 guard); add `test_the_allowlist_is_exact` (`PUBLIC_ROUTES == {("GET","/login"), ("POST","/login"), ("POST","/login/code"), ("POST","/logout"), ("GET","/healthz")}`) and `test_every_allowlist_entry_exists`; add the **anonymous sweep** `test_every_route_outside_the_allowlist_redirects_anonymous_requests` (parametrised over both engines through `client`): for every route and every method not in `PUBLIC_ROUTES`, an anonymous request (no redirects followed) answers **303**, with `Location: /login?next=<percent-encoded path>` for `GET`/`HEAD` and `Location: /login` otherwise; add `test_the_api_docs_are_not_served` (`/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` → 404). Keep `test_the_static_files_are_the_only_mount`. Update the module docstring
- [ ] T036 [P] [US2] Add the US2 scenarios to `tests/integration/test_login_flow.py`: **US2-1** anonymous `GET /` → 303 `Location: /login?next=%2F`, and `GET /?a=1&b=2` → `next` = the percent-encoded `/?a=1&b=2`, which after a full sign-in lands on exactly `/?a=1&b=2` (query string preserved); **US2-2** anonymous `GET /login` 200, `POST /logout` 303 to plain `/login`, `GET /healthz` 200, `GET /static/css/app.css` 200 — none redirected to `/login?next=…`; **US2-3** sign-in with `next` = each of `https://evil.example/`, `//evil.example`, `/\evil.example`, `/login`, `/logout` → lands on `/`; **US2-5** a signed-in client (`admin_client`) opening `GET /login?next=/?x=1` → 303 to `/?x=1`, and `GET /login` → 303 to `/`; an unknown path anonymous → the friendly 404 page, not a redirect; an anonymous `GET /` with a garbage `sc_session` cookie → 303, not an error page
- [ ] T037 [US2] Change `tests/integration/test_home.py` (FR-046): every milestone-3 page test switches from `client` to `admin_client`, except `test_unknown_path_returns_a_rendered_not_found_page` (stays anonymous) and `test_error_page_reports_the_release_too` (keep whichever client its path needs); add `test_home_redirects_anonymous_visitors_to_login` (`client`: 303, `Location: /login?next=%2F`); add `test_home_header_shows_the_signed_in_email_and_a_logout_form`; narrow `test_home_has_no_write_affordance` to "no `<form>` or `<button>` other than the header's `action="/logout"` form" ([research D15](./research.md#d15--tests-an-anonymous-client-an-admin_client-with-a-directly-created-session))
- [ ] T038 [P] [US2] Change `tests/integration/test_health.py`: in `test_healthz_stays_ok_while_the_database_is_failing` request `/` through `admin_client`; add `test_healthz_with_a_cookie_does_no_session_lookup` (send a validly signed and a garbage `sc_session` cookie; monkeypatch `app.core.auth.get_session_user` and `app.core.auth.Session` to raise; `/healthz` still answers 200 with exactly the three keys)

### Implementation for User Story 2

- [ ] T039 [US2] In `app/main.py`, construct the app with `docs_url=None, redoc_url=None, openapi_url=None`, with a comment explaining that these built-in routes are plain Starlette routes that application-wide dependencies do not cover, so leaving them on would publish routes outside the allowlist (FR-028)
- [ ] T040 [US2] Extend `app/core/auth.py` (depends on T018): add `PUBLIC_ROUTES: frozenset[tuple[str, str]]` with exactly the five entries of [contracts/http-routes.md](./contracts/http-routes.md#access-rule-applies-to-every-route) (`HEAD` accepted wherever `GET` is) and `class LoginRequired(Exception)` carrying the redirect target; at the end of `resolve_access`, if `request.state.user is None` and the matched route's `(method, path)` is not public, raise `LoginRequired` with `/login?next=<urllib.parse.quote(path + ("?" + query if query else ""), safe="")>` for `GET`/`HEAD` and plain `/login` otherwise (FR-029). Document in the module docstring that adding a public route is a one-line, reviewed change to `PUBLIC_ROUTES` and that the sweep test enforces it
- [ ] T041 [US2] In `app/main.py`, register `@app.exception_handler(LoginRequired)` returning `RedirectResponse(exc.location, status_code=303)`
- [ ] T042 [US2] In `app/routers/auth.py`, make `GET /login` redirect a signed-in user (`request.state.user` set) with **303** to `safe_next_path(next)` instead of rendering the form (FR-031)
- [ ] T043 [P] [US2] Create `scripts/verify_private.sh` (executable, `set -euo pipefail`, `curl` only, never `-L`) per [contracts/pipeline.md](./contracts/pipeline.md#scriptsverify_privatesh-new-replaces-scriptsdatabase_statussh-which-is-deleted): usage `./scripts/verify_private.sh <base-url>`; retries for up to 60 s, then asserts `GET <base>/` → 303 with `Location` ending in `/login?next=%2F`, `GET <base>/login` → 200 with `name="email"` and `action="/login"` in the body, and `GET <base>/healthz` → 200; on failure prints the URL, status, `Location` and a 500-byte body excerpt and exits 1; needs and prints no credential. Delete `scripts/database_status.sh` with `git rm`
- [ ] T044 [US2] Change `.github/workflows/deploy.yml` per [contracts/pipeline.md](./contracts/pipeline.md#deployyml--deploy): remove *Install uv*, *Install dependencies*, *Expected revision* and *Previous boot count*; keep *Trigger the Render deploy* and *Verify the public address is serving this commit* unchanged; replace *Verify data* with *Verify access control* running `./scripts/verify_private.sh "${{ vars.PUBLIC_BASE_URL }}"`. Check nothing else in the workflow still references removed step outputs
- [ ] T045 [US2] Change the `image` job in `.github/workflows/checks.yml` per [contracts/pipeline.md](./contracts/pipeline.md#checksyml--image) steps 5 and 8: *Start the container* adds `-e ADMIN_EMAILS=ci-admin@example.com` (no `EMAIL_BACKEND`, no `SECRET_KEY`: the console backend and the constant development key, stable across the restart); replace *Smoke test GET /, restart, and again* with *Sign in, smoke test GET /, restart, and again*: anonymous `/` → `303` and `…/login?next=%2F`; `curl -c jar -d email=ci-admin@example.com …/login` → 200; poll `docker logs smoke` for up to 10 s for `Your Student Competitions sign-in code is: [0-9]{6}` and take the last match; `curl -b jar -c jar -d email=… -d code=… …/login/code` → 303 and the jar holds `sc_session`; `check_home 1` with `-b jar`, keeping every milestone-3 assertion and adding `ci-admin@example.com` and `action="/logout"`; `docker restart smoke`, wait for `/healthz`; `check_home 2` with the **same jar** (session and data survived the restart); `curl -b jar -c jar -X POST …/logout` → 303, then `GET /` with the jar → 303 to login. On failure print URL, status, a body excerpt and `docker logs smoke`. Update the step comments
- [ ] T046 [US2] Run the suite on both engines (T035–T038 green, including the whole-route-table sweep) and `bash -n scripts/verify_private.sh`. Optionally run `scripts/verify_private.sh http://127.0.0.1:8000` against a local `uvicorn` to see all three checks pass

**Checkpoint**: Every page is private by default and structurally so; CI and the release check
privacy or sign in for real.

---

## Phase 5: User Story 3 - Operations controls who is an administrator through deployment configuration (Priority: P3)

**Goal**: On every start the set of active administrators matches `ADMIN_EMAILS` exactly:
unlisted admins are deactivated and lose all sessions and codes; reconciliation is idempotent,
safe for two instances at once, and logs counts only.

**Independent Test**: Start with two addresses (both sign in), restart with the same list
(nothing changes), restart with one removed (their session is anonymous and no code is sent)
([spec US3](./spec.md#user-story-3---operations-controls-who-is-an-administrator-through-deployment-configuration-priority-p3)).

### Tests for User Story 3 (write first, confirm they FAIL)

- [ ] T047 [P] [US3] Create `tests/integration/test_admin_reconcile.py` with behaviour-matrix rows **S1–S6** of [contracts/auth-services.md](./contracts/auth-services.md#behaviour-matrix-each-row-is-a-test-on-sqlite-and-postgresql) on both engines: S1 `(2, 0, 0, 0)`; S2 second run `(0, 0, 0, 2)` and no `updated_at` changed (SC-007); S3 `a` with 2 sessions and 1 code, `reconcile_admins([b])` → `a` inactive, 0 sessions, 0 codes, `(0, 0, 1, 1)`, and `a`'s row still exists (never hard-deleted); S4 reactivation `(0, 1, 0, 1)`; S5 `ADMIN_EMAILS=" A@X.org ,a@x.org"` through `resolve_auth_settings` → one user `a@x.org`; S6 concurrency: on PostgreSQL two engines/connections reconcile the same new list concurrently (threads + a barrier) and both finish; on SQLite simulate the conflict path (insert the row from a second session between the first session's read and commit, or monkeypatch to raise `IntegrityError` once) — end state equals a single run, no duplicate. **Startup tests** (via `TestClient` restarts on one `database_url`): the log contains `Administrators reconciled:` with counts and **no** address (`caplog`); reconcile runs after `ensure_at_head` and before `record_boot`; **removal via restart** (FR-045): sign in as `b@example.com` with `ADMIN_EMAILS=a@example.com,b@example.com`, restart with `ADMIN_EMAILS=a@example.com`, the old cookie → `GET /` 303 to login (US3-3), `POST /login` for `b` → the identical 200 page and an empty outbox (US3-4); restart with `b` listed again → `b` can sign in (US3-5)
- [ ] T048 [P] [US3] Add row **L5** to `tests/integration/test_auth_services.py`: issue a code to `a`, `reconcile_admins([])`-style deactivation of `a`, then `verify_code` with the correct code → `None` (the code row was deleted)

### Implementation for User Story 3

- [ ] T049 [US3] Extend `reconcile_admins` in `app/services/users.py` with steps 2–3 of [research D13](./research.md#d13--administrator-reconciliation-idempotent-concurrency-safe-counts-only), in the same transaction: deactivate every active admin whose email is not in the list with one `UPDATE` (setting `updated_at = now` on those rows only; count → **deactivated**); then `DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE is_active = false)` and the same for `login_codes` (idempotent; also cleans up after any earlier partial run). Users are never deleted
- [ ] T050 [US3] In `app/main.py` `lifespan`, wrap the reconciliation call: on `IntegrityError` at commit, `session.rollback()` and call `reconcile_admins` **once more**; a second failure propagates (the start is refused and not counted) (FR-005, edge case "two instances starting at once")
- [ ] T051 [US3] Run the suite on both engines (T047, T048 green)
- [ ] T052 [US3] [MANUAL] **After the first release is green**: validate [quickstart V6](./quickstart.md#v6-removing-an-administrator-ends-their-access-within-one-restart-us3-345-fr-004-sc-006-manual-required-once): add a second address to `ADMIN_EMAILS` in Render, sign in with it in another browser, remove it; the Render log shows `… 1 deactivated …` and no address; that browser lands on `/login`; a code request shows the usual page and no email arrives; re-adding restores access (SC-006)

**Checkpoint**: The administrator list in configuration is the single source of truth, enforced
on every start.

---

## Phase 6: User Story 4 - Sessions end when they should (Priority: P4)

**Goal**: Sessions last at most 14 days, end on logout (only that browser), stop working the
moment the user is deactivated, and expired sessions, codes and rate-limit hits are cleaned up
without a scheduler.

**Independent Test**: Sign in, log out, replay the old cookie (anonymous); a session older than 14
days is rejected; a deactivated user's session stops working on the next request
([spec US4](./spec.md#user-story-4---sessions-end-when-they-should-priority-p4)).

### Tests for User Story 4 (write first, confirm they FAIL)

- [ ] T053 [P] [US4] Create `tests/integration/test_sessions.py` (both engines): **US4-1** logout deletes the server row, clears the cookie (`Max-Age=0`, same `Path`/`HttpOnly`/`SameSite`) and redirects to `/login`; **US4-2** a copy of the cookie replayed after logout → `GET /` 303; **US4-3** a session created with `create_session(now = utc_now() - 14 days - 1 s)` → anonymous, and one at `-13 days` still works; **US4-4** set the user's `is_active = false` directly → the next request is anonymous; **US4-6** two clients signed in as the same user, logout on one → the other still gets 200; **tampering**: a cookie with a flipped signature character, one signed with a different `SECRET_KEY` (rotation edge case), `sc_session=garbage`, and a well-signed unknown token → anonymous 303, never an error page; **GET /logout** → 405 friendly error page and the session still works (a plain link cannot log out); **logout while anonymous** → 303 `/login`; **cookie flags**: the `Set-Cookie` on sign-in has `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age=1209600` and no `Secure` locally; `set_session_cookie` with an `AuthSettings(production=True, …)` adds `Secure`
- [ ] T054 [P] [US4] Add rows **P1, P2, X1** to `tests/integration/test_auth_services.py`: P1 `purge_expired` removes an expired session, an expired code, a used code and a 2-hour-old rate-limit hit while keeping a live one of each; P2 an expired, **not yet purged** session → `get_session_user` returns `None` (FR-026); X1 a session row of an inactive user → `None`

### Implementation for User Story 4

- [ ] T055 [US4] Add `purge_expired(session, now=utc_now()) -> None` to `app/services/login.py` per [research D9](./research.md#d9--cleanup-without-a-scheduler): three indexed `DELETE`s — sessions with `expires_at <= now`; login codes with `expires_at <= now OR used_at IS NOT NULL`; rate-limit hits with `created_at <= now - 1 h`; commits
- [ ] T056 [US4] Wire cleanup: in `app/main.py` `lifespan` call `purge_expired` after reconciliation and before `record_boot` (final order: `resolve_database_url → resolve_auth_settings → engine → ensure_at_head → reconcile_admins → purge_expired → record_boot`, FR-043); in `deliver_login_code` (`app/services/login.py`) call `purge_expired` at the end of every run, for known and unknown addresses alike, inside the same catch-all
- [ ] T057 [US4] Run the suite on both engines (T053, T054 green)

**Checkpoint**: The whole session lifecycle is enforced on every request, independent of cleanup
timing.

---

## Phase 7: User Story 5 - Sign-in resists guessing, flooding and account discovery (Priority: P5)

**Goal**: Identical responses and timing for known, unknown and inactive addresses; at most 5
wrong attempts per code; at most 5 code requests per email and 20 per client per hour, stored in
the database so they survive restarts; one generic message for every bad-code case.

**Independent Test**: Compare known vs. unknown submissions; exhaust a code's attempts then send
the correct one (rejected); exceed the per-email limit (no more emails)
([spec US5](./spec.md#user-story-5---sign-in-resists-guessing-flooding-and-account-discovery-priority-p5)).

### Tests for User Story 5 (write first, confirm they FAIL)

- [ ] T058 [P] [US5] Create `tests/integration/test_login_privacy.py` (both engines): **US5-1** `POST /login` for the admin, an unknown address and an inactive user → identical status (200) and identical bodies once the echoed address is replaced by a placeholder, and identical `Set-Cookie` presence (none); **SC-004 timing**: 50 known and 50 unknown submissions interleaved, with the rate-limit table cleared between rounds (or distinct unknown addresses and a fresh `database_url`), medians differ by < 100 ms; **US5-2** 5 wrong codes then the correct one → all 400 with the generic message, no session, `attempts == 5`; **US5-3** 6 requests for one email within the hour → the 6th is 429 with "Too many attempts. Please try again later." and the outbox holds exactly 5 messages; the same sequence for an unknown address gives the same statuses and bodies; **US5-4** 21 requests for 21 different addresses from one client → the 21st is 429; **US5-5/R4** reach the per-email limit, close the `TestClient`, open a new one on the same `database_url` → still 429; **US5-6** request a code, request another, submit the first → 400; **US5-7** wrong, expired, used and exhausted codes produce byte-identical bodies; **invalid email not counted**: 10 malformed submissions leave `rate_limit_hits` empty; the stored `key_hash` values are 64 hex and neither the address nor `testclient` appears in any `rate_limit_hits` column
- [ ] T059 [P] [US5] Add rows **L3** and **R1–R4** to `tests/integration/test_auth_services.py`: L3 5 wrong codes then the correct one → all `None`, `attempts == 5`, and a non-6-digit code also counts as a wrong attempt; R1 5 hits for `e` → `allow_code_request` `False` and still 5 rows; R2 20 hits for client `c` across 20 emails → 21st `False`; R3 5 hits at `t`, `now = t + 61 min` → `True`; R4 limit reached, a new `Session` on the same engine → still `False`

### Implementation for User Story 5

- [ ] T060 [US5] Create `app/services/rate_limits.py` per [research D5](./research.md#d5--rate-limits-an-append-only-hit-log-in-the-database-sliding-one-hour-window) and [data-model §4](./data-model.md#4-ratelimithit--table-rate_limit_hits-appmodelsrate_limit_hitpy): constants `BUCKET_CODE_EMAIL = "code_email"`, `BUCKET_CODE_CLIENT = "code_client"`, `EMAIL_CODE_LIMIT = 5`, `CLIENT_CODE_LIMIT = 20`, `WINDOW = timedelta(hours=1)`; `allow_code_request(session, secret_key, email, client, now=utc_now()) -> bool` counts hits with `created_at > now - WINDOW` for both `(bucket, hash_rate_limit_key(secret_key, bucket, key))` pairs; if either count is at its limit returns `False` and writes nothing; otherwise inserts both hits, commits, returns `True`. Refused requests are never recorded
- [ ] T061 [US5] In `app/routers/auth.py` `POST /login`, after validation and **before** scheduling the background task, call `allow_code_request(session, settings.secret_key, email, client_address(request, settings.production))`; on `False` return **429** with step 1 and "Too many attempts. Please try again later." (identical for every address, FR-020); keep the in-request work identical for every well-formed address (the same queries in the same order, [research D10](./research.md#d10--step-1-does-identical-work-for-every-address-the-email-is-issued-and-sent-after-the-response)). Invalid emails return 400 before any rate-limit query
- [ ] T062 [US5] Run the suite on both engines (T058, T059 green); rerun `test_login_privacy.py` five times to confirm the timing test does not flake
- [ ] T063 [US5] [MANUAL] **After the first release is green**: validate [quickstart V9](./quickstart.md#v9-rate-limits-and-the-per-client-key-in-production-us534-fr-017-fr-018-research-d8-manual-required-once): 6 requests for your own address → the 6th shows "Too many attempts" and exactly 5 emails arrive; 21 step-1 requests for made-up `example.invalid` addresses with different fake `X-Forwarded-For` headers → record in the PR whether the 21st is refused (residual risk in the plan's *Complexity Tracking*)

**Checkpoint**: The login flow reveals nothing and bounds guessing below 0.1% per address per day
(SC-005).

---

## Phase 8: User Story 6 - Email delivery fits each environment, and production refuses an unsafe setup (Priority: P6)

**Goal**: Production sends real email through Resend's HTTP API from the verified domain; the
flow never knows which backend is in use; a provider outage is invisible to the user; a Render
start with console/memory delivery or a missing secret is refused without echoing values.

**Independent Test**: Locally the console prints the email; the suite reads the memory outbox and
never reaches Resend; `RENDER=true` with `EMAIL_BACKEND=console` refuses to start
([spec US6](./spec.md#user-story-6---email-delivery-fits-each-environment-and-production-refuses-an-unsafe-setup-priority-p6)).

### Tests for User Story 6 (write first, confirm they FAIL)

- [ ] T064 [P] [US6] Add the Resend half to `tests/unit/test_email.py` with a fake `post(url, body, headers, timeout) -> int` that records its call: the URL is `https://api.resend.com/emails`; the JSON body is exactly `{"from": sender, "to": [to], "subject": …, "text": …}`; headers `Authorization: Bearer <key>`, `Content-Type: application/json`, `User-Agent: student-competitions/<APP_VERSION>`; timeout `10`; a 2xx status returns; a 422 raises `EmailDeliveryError("Resend returned HTTP 422")`; a fake raising `URLError`/`TimeoutError` raises `EmailDeliveryError` naming the exception type with `__cause__ is None`; neither the key, the address nor the body appears in any error message; `build_email_sender` maps `resend` to a `ResendEmailSender` with the settings' key and sender. No test performs a real network call
- [ ] T065 [P] [US6] Add to `tests/integration/test_login_privacy.py` **US6-6/FR-039**: replace `app.state.email_sender` with a sender whose `send` raises `EmailDeliveryError("Resend returned HTTP 500")`, then `POST /login` for the admin → the same 200 page as usual; `caplog` contains `Login email not sent` and contains neither the address nor any 6-digit code; a later request (after restoring the memory sender) still delivers a code. Also add **US6-5**: across a full sign-in with `caplog` at `DEBUG` and `capsys`, no captured log record or output contains the code, the session token, the cookie value, the `SECRET_KEY` or the address
- [ ] T066 [P] [US6] Extend `tests/integration/test_startup.py`: with `RENDER=true`, a valid `DATABASE_URL` and **no** auth settings, `TestClient(app)` raises `AuthConfigError` naming all five settings and the boot is **not** counted (the database is untouched); with the full dummy set plus `EMAIL_BACKEND=console` → refused naming `EMAIL_BACKEND`, and `ci-dummy-not-a-secret` / `ci-dummy-key` appear nowhere in the message; locally with no auth settings the app starts (US6-1, FR-042). The milestone-3 refusal tests stay unchanged

### Implementation for User Story 6

- [ ] T067 [US6] In `app/services/email.py` add `_urllib_post(url, body, headers, timeout) -> int` (standard-library `urllib.request.Request` + `urlopen`; returns the status for 2xx and, via `HTTPError.code`, for non-2xx; never reads or logs the response body) and `ResendEmailSender(api_key, sender, post=_urllib_post)` per [contracts/email-sender.md](./contracts/email-sender.md#backends) and [research D1](./research.md#d1--email-delivery-service-resend-through-its-http-api-called-with-the-standard-library); replace the `NotImplementedError` placeholder in `build_email_sender` with the `resend` mapping. The sender never logs the request, the response or the key. Make T064 pass
- [ ] T068 [P] [US6] Change `render.yaml`: add `EMAIL_BACKEND` with `value: resend`, and `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`, `EMAIL_FROM` each with `sync: false` ([contracts/configuration.md](./contracts/configuration.md#render-renderyaml)); update the header comment from "one secret" to "five secrets". No value other than `resend` is written
- [ ] T069 [US6] Add image steps 3 and 4 to `.github/workflows/checks.yml` (after *Refuse to start on Render without a database*, before *Start the container*; depends on T045) per [contracts/pipeline.md](./contracts/pipeline.md#checksyml--image): **Refuse to start on Render without auth settings** (`docker run --rm --network host -e RENDER=true -e DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres …`; non-zero exit; output contains each of `EMAIL_BACKEND`, `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`, `EMAIL_FROM`); **Refuse the console backend on Render** (the same plus `EMAIL_BACKEND=console`, `SECRET_KEY=ci-dummy-not-a-secret-0123456789abcdef`, `ADMIN_EMAILS=ci-admin@example.com`, `RESEND_API_KEY=ci-dummy-key`, `EMAIL_FROM=ci@example.com`; non-zero exit; output contains `EMAIL_BACKEND` and does **not** contain `ci-dummy-not-a-secret` or `ci-dummy-key`). Comment that the values are labelled fakes and the workflow still references no secret
- [ ] T070 [US6] Run the suite on both engines (T064–T066 green) and confirm `grep -rn "api.resend.com" tests/` shows only the fake-`post` assertion
- [ ] T071 [US6] [MANUAL] **Before merging** (rollout gate): complete [quickstart B1–B3](./quickstart.md#one-time-bootstrap-production-do-this-before-merging-to-main): verify `brainring.org.ua` in Resend (DKIM `TXT`, bounce `MX` + SPF `TXT`, `_dmarc` `v=DMARC1; p=none;` at NIC.UA) until it shows **Verified**; create a sending-only API key restricted to the domain; enter `SECRET_KEY` (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`), `ADMIN_EMAILS`, `RESEND_API_KEY` and `EMAIL_FROM` in Render → *Environment*. The key and secret go only into Render, never into a file, chat or GitHub
- [ ] T072 [US6] [MANUAL] **After the first release is green**: validate [quickstart V7](./quickstart.md#v7-login-emails-reach-the-inbox-not-spam-fr-038-sc-002-manual-required-once): 10 codes over two inboxes at different providers, within the limits; ≥ 95% in the inbox within 1 minute; headers show `dkim=pass`, `spf=pass`, `dmarc=pass`; record the results in the PR (SC-002)

**Checkpoint**: All six stories are complete; production delivery and the refusal rules are in
place.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, scope and secret guards, and final acceptance

- [ ] T073 Update `README.md` (FR-044, Workflow §5): a settings table for `EMAIL_BACKEND`, `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`, `EMAIL_FROM` (purpose, allowed values, local default, production requirement, secret or not); *Signing in locally* (`ADMIN_EMAILS=you@example.com uv run uvicorn app.main:app --reload`, read the code from the console email); the **private-by-default rule** for new pages (every route is protected unless added to `PUBLIC_ROUTES` in `app/core/auth.py`, and the sweep in `tests/integration/test_routes.py` enforces it); the `admin_client` / `outbox` fixtures for page tests; that rotating `SECRET_KEY` signs everyone out; replace the milestone-3 note about watching the boot count on the public page (it now requires signing in; `scripts/database_status.sh` is gone, `scripts/verify_private.sh` is new); confirm a clean checkout can sign in in under 15 minutes following only the README (SC-009)
- [ ] T074 [P] Scope and bypass guard (FR-007, FR-034, FR-047): confirm `git grep -nE "magic|bypass|skip_email|DEV_LOGIN|TEST_LOGIN" app/` finds nothing that signs anyone in; `create_session` is called only from `app/routers/auth.py` and `tests/`; no route creates, edits or lists users; no `student`/`teacher` role value exists; no `|safe` in `app/templates/`; no `hx-` attribute or `<script>` was added
- [ ] T075 [P] Log-hygiene review (FR-037, SC-008): read every `logger.` and `print(` call added in `app/`; only `ConsoleEmailSender` prints a body; no call formats an address, code, token, cookie, hash, key or `settings` object; `AuthSettings`' `repr` is masked
- [ ] T076 Validate [quickstart V10](./quickstart.md#v10-no-codes-tokens-secrets-or-email-bodies-anywhere-fr-037-fr-040-sc-008-manual-required-once) part 1 before merging: `git grep -nE 're_[A-Za-z0-9]{8,}'` is empty; the diff against `main` contains no secret value (`render.yaml` holds keys only, except `EMAIL_BACKEND: resend`; the CI values are the labelled `ci-dummy-*` fakes); `checks.yml` still references no `secrets.`; after `docker build -t student-competitions:ci .`, `docker run --rm --entrypoint sh student-competitions:ci -c 'env; ls -a /app'` shows no auth variable and no `.env`
- [ ] T077 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` (with `TEST_POSTGRES_URL` set) from the repository root one final time; all three green. Stop and remove the local `sc-pg` container
- [ ] T078 [MANUAL] **After the first release is green**: validate [quickstart V8](./quickstart.md#v8-the-boot-count-still-rises-across-a-redeploy-seen-signed-in-milestone-3-sc-002-spec-assumption-manual-witness-required-once) (signed in on production, `boot #N` → `boot #N+1` or higher after a redeploy, questions intact), [V4](./quickstart.md#v4-the-release-proves-production-is-private-us212-fr-028-automated-on-every-release) (the Deploy run's *Verify access control* is green; `curl -sI https://brainring.org.ua/` → `303` with `location: /login?next=%2F`), and V10 part 2 (the Render logs covering V5–V9 contain no code, no `sc_session`, no address from `ADMIN_EMAILS`, no email body)
- [ ] T079 Work through the **Milestone acceptance checklist** in [quickstart.md](./quickstart.md#milestone-acceptance-checklist) and tick B1–B3, V1–V10 and the README item. The milestone's stated criterion is "A user can log in end to end, reading the code from the `memory` outbox. A route-table test asserts that every route outside the allowlist rejects anonymous requests. Existing page tests use a fixture that creates a session directly. Unknown and known emails get the same response. Running the reconcile twice changes nothing. An email removed from `ADMIN_EMAILS` can no longer log in and loses its sessions."

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Start immediately
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories**. It ends with the
  suite green and the home page still public (T022)
- **US1 (Phase 3)**: Depends on Foundational only
- **US2 (Phase 4)**: Depends on Foundational **and US1** (redirect target, CI sign-in through the
  login routes). It must land before the pipeline is next exercised, because the milestone-3
  `image` job and *Verify data* read `/` anonymously
- **US3 (Phase 5)**: Depends on Foundational; its HTTP removal test (T047) uses US1's login routes
- **US4 (Phase 6)**: Depends on Foundational and US1 (logout, sign-in)
- **US5 (Phase 7)**: Depends on Foundational and US1 (`POST /login`, `verify_code`)
- **US6 (Phase 8)**: Depends on Foundational; T065 adds to the file US5 creates (T058), and T069
  edits the job US2 rewrote (T045)
- **Polish (Phase 9)**: Depends on all stories
- **[MANUAL] tasks**: T071 must be done **before the merge** (otherwise the first release refuses
  to start, by design); T034, T052, T063, T072, T078 need the milestone merged and released

### User Story Dependencies

```text
Setup → Foundational → US1 (P1) ─┬─→ US2 (P2) ─────────────┐
                                 ├─→ US3 (P3) ─────────────┤
                                 ├─→ US4 (P4) ─────────────┼─→ Polish → T071 → merge → post-merge MANUAL
                                 └─→ US5 (P5) ─→ US6 (P6) ─┘
```

US1 comes first because every other story either redirects to its pages, signs in through them
or hardens them. After US1, US2, US3, US4 and US5 are independent increments; US6 only follows
US5 for one shared test file.

### Within Each Phase

- **Phase 2**: tests T003–T006 first; T007 before T008 (config imports `is_valid_email`); T009–T012
  together, then T013, then T014; T015, T016, T017 after T008/T013; T018 after T017; T019 anytime;
  T020 after T015–T018; T021 after T020; T022 last
- **Phase 3**: T023, T024 first; T025, T028, T029 together; T026 before T030; T027 before T030;
  T030 → T031 → T032 → T033
- **Phase 4**: T035–T038 first; T039, T040 → T041 → T042; T043 → T044; T045 after T042; T046 last
- **Phase 5**: T047, T048 → T049 → T050 → T051
- **Phase 6**: T053, T054 → T055 → T056 → T057
- **Phase 7**: T058, T059 → T060 → T061 → T062
- **Phase 8**: T064–T066 → T067; T068 anytime; T069 after T045; T070 after T067; T071 before merge

### Shared files (never edit in parallel)

- `app/main.py`: T020 → T031 → T039/T041 → T050 → T056
- `app/routers/auth.py`: T030 → T042 → T061
- `app/core/auth.py`: T018 → T040
- `app/services/login.py`: T026 → T055/T056
- `tests/integration/test_auth_services.py`: T024 → T048 → T054 → T059
- `tests/integration/test_login_flow.py`: T023 → T036
- `tests/integration/test_login_privacy.py`: T058 → T065
- `tests/unit/test_email.py`: T006 → T064
- `.github/workflows/checks.yml`: T045 → T069

### Parallel Opportunities

- **Phase 2**: T003, T004, T005, T006 (four test files); T009–T012 (four models); T015, T016, T017
  (three services); T019 alongside any of them
- **Phase 3**: T023 and T024; then T025, T028, T029
- **Phase 4**: T035, T036, T038 (T037 touches `test_home.py`, also parallel); T043 alongside the
  `auth.py` work
- **After US1**: US2, US3, US4 and US5 can proceed in parallel by different people, respecting the
  shared-file order above
- **Phase 8**: T064, T065, T066 together; T068 anytime
- **Phase 9**: T074 and T075 together

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Four unit-test files together:
Task: "Write tests/unit/test_auth_config.py — C1–C8, W1–W3, no values in messages"
Task: "Write tests/unit/test_security.py — hashing, signing, tokens, email rules, client_address"
Task: "Write tests/unit/test_safe_next.py — the open-redirect table"
Task: "Write tests/unit/test_email.py — message text, console format, memory outbox"

# Four models together:
Task: "Create app/models/user.py — User, Role(StrEnum) = {ADMIN}"
Task: "Create app/models/user_session.py — UserSession (table sessions)"
Task: "Create app/models/login_code.py — LoginCode"
Task: "Create app/models/rate_limit_hit.py — RateLimitHit + named composite index"
```

## Parallel Example: User Story 1

```bash
Task: "Create tests/integration/test_login_flow.py — end to end via outbox + US1 scenarios"
Task: "Create tests/integration/test_auth_services.py — L1, L2, L4, L6"

Task: "Create app/schemas/auth.py — EmailSubmission, CodeSubmission"
Task: "Create app/templates/pages/login.html — step 1"
Task: "Create app/templates/pages/login_code.html — step 2"
```

## Parallel Example: after US1

```bash
Developer A: US2 — PUBLIC_ROUTES + LoginRequired, route sweep, test_home → admin_client, pipeline
Developer B: US3 — reconcile deactivation + retry, test_admin_reconcile.py
Developer C: US4 — purge_expired, test_sessions.py
Developer D: US5 — rate_limits.py, test_login_privacy.py
```

---

## Implementation Strategy

### MVP First (Phases 1–3)

1. Phase 1: Setup (`python-multipart`)
2. Phase 2: Foundational (settings, security helpers, tables, email interface, sessions, resolver,
   fixtures)
3. Phase 3: User Story 1 (the two-step login and logout)
4. **STOP and VALIDATE**: the end-to-end test via the outbox, and a local sign-in via the console
   (T033)

### Incremental Delivery

1. Setup + Foundational → the app knows who is signed in, but still protects nothing
2. **+ US1 → administrators can sign in and out** (MVP)
3. + US2 → every page is private by default; CI and the release check it
4. + US3 → the administrator list in configuration is enforced on every start
5. + US4 → the session lifecycle is complete (expiry, deactivation, cleanup)
6. + US5 → the login flow resists guessing, flooding and account discovery
7. + US6 → production email through Resend and the production refusal rules
8. + Polish → README, scope and secret reviews
9. T071 (rollout gate) → merge → post-merge checks (V4–V10) → acceptance checklist

The milestone ships as **one** pull request (constitution *Branching*), so "incremental" here means
checkpoints on the branch. Each one leaves the suite green and the app runnable. Do **not** push a
state between US1 and US2 to a PR expecting a green `image` job: the milestone-3 image check still
reads `/` anonymously until T045.

---

## Notes

- **[MANUAL] tasks are not optional.** T071 is the rollout gate and must happen **before merge**.
  T034, T052, T063, T072 and T078 are the post-merge acceptance procedures that the plan's
  *Complexity Tracking* justifies as procedures rather than tests
- **Values that do not exist until generated**: the Alembic revision id (T014), the production
  `SECRET_KEY` and the Resend API key (T071). The secrets must never be written into any file,
  issue, commit, chat or log
- **No login bypass of any kind** (FR-034): the only shortcut is the `admin_client` fixture in
  `tests/conftest.py`
- `[P]` tasks touch different files and depend on nothing unfinished
- Commit after each task or logical group. Stop at any checkpoint to validate the story
  independently
