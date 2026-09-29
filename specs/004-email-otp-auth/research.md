# Research & Decisions: Email Code Authentication (Milestone 4)

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](./plan.md)

Every unknown in the plan's Technical Context is resolved here. Each entry records the decision,
why it was made, and what was rejected. Platform facts are those documented by Render and Resend
at the time of writing; the ones that could drift (free-plan limits, proxy behaviour) are flagged
for a re-check in [quickstart.md](./quickstart.md).

---

## D1 — Email delivery service: Resend, through its HTTP API, called with the standard library

**Decision**: production sends login emails through **Resend**'s REST API
(`POST https://api.resend.com/emails`, `Authorization: Bearer <RESEND_API_KEY>`, JSON body
`{from, to, subject, text}`). The call is made with the standard library's `urllib.request`, with a
10-second timeout and an explicit `User-Agent: student-competitions/<APP_VERSION>`. The sending
domain `brainring.org.ua` is verified in Resend with the DKIM and SPF records Resend generates,
added at NIC.UA, plus a `_dmarc` TXT record (`v=DMARC1; p=none`). The sender is
`EMAIL_FROM`, for example `Student Competitions <login@brainring.org.ua>`. This closes the
constitution's open stack decision "email delivery service — decide in milestone 4".

**Rationale**:

- **The technical requirements name Resend and its HTTP API.** Free hosting tiers may block
  outbound SMTP ports; an HTTPS call on port 443 is never blocked.
- **No new dependency.** One JSON `POST` per login does not justify the `resend` SDK (which pulls
  in `requests`) or promoting `httpx` to a runtime dependency. `urllib.request` is enough, and
  tests replace the transport function instead of patching a library (see
  [contracts/email-sender.md](./contracts/email-sender.md)).
- **Explicit `User-Agent`.** Some Cloudflare-fronted APIs reject the default `Python-urllib/3.x`
  agent. Setting our own costs one header and removes that failure mode.
- **Deliverability (SC-002).** DKIM and SPF are what Resend's domain verification requires. A DMARC
  record is what Gmail and Yahoo now expect from senders, and `p=none` cannot cause a rejection.
  The email is short plain text with no link (FR-015), which also helps spam scoring.
- **Free plan fits.** Resend's free plan allows one verified domain and a daily and monthly send
  allowance (currently 100/day and 3,000/month) that is orders of magnitude above what a handful
  of administrators need. *Re-check the current limits when creating the account.*

**Alternatives considered**:

- *SMTP (Resend SMTP, Gmail SMTP, Mailgun SMTP)*: rejected. Outbound SMTP may be blocked on free
  tiers, and the technical requirements rule it out.
- *The `resend` Python SDK*: rejected. It is one more runtime dependency (plus `requests`) for a
  single HTTP call.
- *`httpx` as a runtime dependency*: rejected for the same reason. It is currently a test-only
  package.
- *Other providers (Postmark, SendGrid, Mailgun, Amazon SES)*: not needed. The requirements name
  Resend, and it has a free plan with a domain-based sender. Switching later means writing one more
  `EmailSender` implementation (D6).

---

## D2 — Codes: 6 digits from `secrets`, keyed hash bound to the address, newest code wins

**Decision**:

- A code is `f"{secrets.randbelow(1_000_000):06d}"`: 6 digits, leading zeros allowed.
- Stored as `HMAC-SHA256(SECRET_KEY, "login-code\x00" + email + "\x00" + code)`, hex-encoded
  (64 characters). The plain code is never stored and never logged (FR-027).
- Valid for **20 minutes** from issue (FR-011). At most **5 wrong attempts** per code (FR-016).
- Issuing a code **deletes** every earlier unused code of that user, so at most one live code
  exists per user (FR-011, US5-6).
- Verification takes the user's single live code, compares hashes with `hmac.compare_digest`, and
  either:
  - increments `attempts` with one conditional `UPDATE … SET attempts = attempts + 1 WHERE id = ?
    AND attempts < 5`, or
  - consumes it with one conditional `UPDATE … SET used_at = now WHERE id = ? AND used_at IS NULL
    AND attempts < 5 AND expires_at > now`. Only the request whose `UPDATE` touches one row
    creates a session, so a double-clicked submit cannot create two sessions (edge case).
- Surrounding whitespace in the entered code is stripped. Anything that is not exactly 6 digits
  counts as a wrong attempt against the live code, if there is one, and gets the same generic
  message.

**Rationale**:

- **Binding the email into the hash** means a hash row can only ever match its own address. A
  tampered hidden email field (edge case) cannot verify against another user's code.
- **Domain separation.** The same `SECRET_KEY` also signs cookies (D4). The `"login-code\x00"`
  prefix makes a code hash and a cookie signature unusable as one another.
- **The numbers meet SC-005.** 5 codes per email per hour × 5 attempts = 25 guesses per hour, at
  most 600 per day, against 10⁶ values. That is a success chance below 0.06% per address per day.
- **Delete, not flag, superseded codes.** "Invalidated" needs no column when the row is gone. Used
  codes keep `used_at` until cleanup, so the spec's entity attributes remain visible to tests.

**Alternatives considered**:

- *bcrypt/argon2 for codes*: rejected. A slow hash protects low-entropy secrets against offline
  cracking. Here the key is secret (HMAC), so an attacker with the database but not `SECRET_KEY`
  cannot even test guesses. Brute force online is capped by D5. A slow hash would add a dependency
  and latency for no gain.
- *8-digit or alphanumeric codes*: rejected. 6 digits is the industry norm, easy to type from a
  phone, and already meets SC-005.
- *Magic links*: out of scope (spec). Link scanners in mail clients would consume them.

---

## D3 — Sessions: random token, SHA-256 in the database, HMAC-signed cookie

**Decision**:

- Token: `secrets.token_urlsafe(32)` (256 bits).
- Database: table `sessions` stores `sha256(token)` hex (64 characters, unique). The plain token
  exists only in the cookie (FR-021).
- Cookie `sc_session`, value `<token>.<signature>`, where the signature is
  `base64url(HMAC-SHA256(SECRET_KEY, "session\x00" + token))`. Attributes: `HttpOnly`,
  `SameSite=Lax`, `Path=/`, `Max-Age=1209600` (14 days), and `Secure` when running on Render
  (FR-024).
- Absolute lifetime of **14 days** from creation. Activity does not extend it (spec assumption).
- On every request the app first checks the signature. A bad signature means anonymous, with no
  database query. It then runs one indexed query: session by token hash, `expires_at > now`, joined
  to a user with `is_active = true` (FR-022).
- Logout deletes the row by token hash and clears the cookie with the same attributes (FR-025).
  Other sessions of the same user are untouched (US4-6).

**Rationale**:

- **The token is already high-entropy**, so a plain SHA-256 is a sufficient one-way hash. A keyed
  or slow hash adds nothing: a database leak cannot be reversed into cookies either way.
- **Signing the cookie**, as the requirements specify, rejects forged or tampered cookies before
  any database access. It also means rotating `SECRET_KEY` signs everyone out, which is the
  documented edge case.
- **Standard library only.** `hmac`, `hashlib`, `secrets` and `base64` implement this in a few
  lines. No `itsdangerous` is needed. It is not installed, and it would be a dependency for one
  function.
- **`Secure` keyed on `RENDER`**, the same production switch as `DATABASE_URL`. Locally the app is
  served over plain `http://127.0.0.1`, where a `Secure` cookie would never be sent back.

**Alternatives considered**:

- *Starlette `SessionMiddleware` (client-side signed session data)*: rejected. It is not
  server-side, so logout could not invalidate a copied cookie (US4-2), and deactivation could not
  end sessions. It also needs `itsdangerous`.
- *JWT*: rejected for the same reason: it cannot be revoked without a server-side store, at which
  point it is a session with extra steps.
- *Sliding expiry*: rejected by the spec (absolute lifetime).
- *`__Host-` cookie prefix*: rejected. It requires `Secure`, which breaks local `http`. It would add
  a second cookie name per environment for a marginal gain on a single-host application.

---

## D4 — Deny-by-default access: one application-level dependency and an explicit allowlist

**Decision**: `app/core/auth.py` defines:

- `PUBLIC_ROUTES`: a frozen set of `(method, path)` pairs: `GET /login`, `POST /login`,
  `POST /login/code`, `POST /logout` and `GET /healthz`. The `/static` mount is public by being a
  mount, not a route.
- `resolve_access(request, session)`, registered as an **application-wide dependency**
  (`FastAPI(dependencies=[Depends(resolve_access)])`). FastAPI prepends it to every route the
  application has or will ever include.
  - `GET /healthz`: returns immediately (no cookie parsing, no database; the milestone-2
    contract stays intact).
  - Otherwise it resolves the current user from the cookie (D3) into `request.state.user`.
  - If there is no user and the matched route is not in `PUBLIC_ROUTES`, it raises `LoginRequired`.
- An exception handler turns `LoginRequired` into **303 See Other** to
  `/login?next=<percent-encoded path and query>`. `next` is carried only for `GET`/`HEAD`; any
  other method gets plain `/login` (FR-029).
- `CurrentUser`: an `Annotated` dependency that returns `request.state.user` for handlers that need
  it. Milestone 5 builds its role dependencies on it.
- A Jinja context processor exposes `current_user` to every template, so the layout header (email
  and **Log out**) is rendered without every handler passing it (FR-032).

**Rationale**:

- **Protection is structural.** A route added later in any router is protected unless someone adds
  it to `PUBLIC_ROUTES`, which is a visible one-line diff in a security module. That is what
  Principle IV's "deny-by-default" asks for, and it satisfies FR-028's "a forgotten check cannot
  leak data".
- **The route-table test (FR-045, SC-003)** iterates over `app.routes`. It asserts that every route
  outside the allowlist answers an anonymous request with 303 to `/login`, that every allowlist
  entry exists, and that the allowlist is exactly the five entries above. A new unprotected route
  and a stale allowlist entry both fail the build.
- **A dependency, not middleware.** The constitution calls for reusable FastAPI dependencies. A
  sync dependency runs in the thread pool, so the blocking database lookup never stalls the event
  loop. That is not true of an `@app.middleware("http")` function.
- **Unknown paths** match no route, so no dependency runs, and anonymous visitors get the ordinary
  friendly 404 page. It reveals nothing: there is no data behind it, and every real page redirects.

**Alternatives considered**:

- *Per-router `dependencies=[…]`*: rejected. A new router that forgets it is unprotected, which is
  opt-in security.
- *HTTP middleware with a path-prefix allowlist*: rejected. It is harder to test per route,
  duplicates routing logic with string prefixes, and runs sync I/O on the event loop unless wrapped.
- *Redirect with 302/307*: rejected. 303 guarantees the browser follows with `GET`, which the spec
  names.

---

## D5 — Rate limits: an append-only hit log in the database, sliding one-hour window

**Decision**: table `rate_limit_hits (id, bucket, key_hash, created_at)` with an index on
`(bucket, key_hash, created_at)`.

- A code request (step 1 with a well-formed email, including "request a new code") first counts
  hits in the last hour for two keys:
  - `bucket="code_email"`, limit **5**, key = the normalised email (FR-017);
  - `bucket="code_client"`, limit **20**, key = the client address (FR-018, D8).
- If either count is at its limit, the request is refused with the "too many attempts" page
  (HTTP 429, identical for registered and unregistered addresses; FR-020), and nothing is
  recorded or sent.
- Otherwise one hit is inserted for each key, in the same transaction, and the request proceeds.
- `key_hash = HMAC-SHA256(SECRET_KEY, "rate-limit\x00" + bucket + "\x00" + key)`. Addresses and
  client IPs are never stored in plain form. Unregistered addresses someone typed are personal data
  too.
- Wrong code attempts are limited on the code row itself (D2), not here.
- Hits older than one hour are deleted by cleanup (D9).

**Rationale**:

- **Survives restarts and is shared between instances (FR-019)** because it lives in the
  application database. The constitution forbids new infrastructure such as Redis for this.
- **Portable.** Inserts and a `COUNT(*)` run identically on SQLite and PostgreSQL. No dialect-
  specific upsert (`ON CONFLICT`) is needed, unlike a fixed-window counter row.
- **Counting every submitted address (FR-017)**, registered or not, is what makes hitting the limit
  reveal nothing.
- **The one known imprecision is harmless.** Two truly simultaneous requests at count 4 can both
  pass, allowing 6 in an hour. The bound is off by the concurrency degree, which is negligible for
  SC-005's arithmetic.

**Alternatives considered**:

- *Fixed-window counter row with upsert*: rejected. It needs dialect-specific SQL and allows 2×
  bursts at window edges.
- *In-memory limiter (e.g. `slowapi`)*: rejected. It is lost on restart (violates FR-019, US5-5),
  not shared between instances, and a new dependency.
- *Counting refused requests too*: rejected. A client stuck at its limit would extend its own
  lock-out indefinitely, which is unfriendly to a user retrying.

---

## D6 — Email sending: one small protocol, three implementations, chosen at startup

**Decision**: `app/services/email.py` defines:

- `EmailMessage(to: str, subject: str, text: str)`: a frozen dataclass.
- `EmailSender`: a `Protocol` with `send(message) -> None`, which raises `EmailDeliveryError` on
  failure.
- `ConsoleEmailSender`: prints the whole message (headers and body) to stdout between clear markers.
  This is the only implementation that ever outputs a body (FR-037).
- `MemoryEmailSender`: appends to `self.outbox: list[EmailMessage]`. Tests read the code from the
  last message (FR-036).
- `ResendEmailSender(api_key, sender, post=_urllib_post)`: D1. On a non-2xx status or a network
  error, it raises `EmailDeliveryError` carrying only the HTTP status or the exception type.
- `build_email_sender(settings) -> EmailSender`, called once in `lifespan`. The result is stored on
  `app.state.email_sender`.
- `login_code_message(email, code, minutes) -> EmailMessage`, which holds the text: the code, the
  validity, and "ignore this email if you did not request it" (FR-015). Subject:
  "Your Student Competitions sign-in code". **The code is not in the subject**, so it does not
  appear in lock-screen previews or in a provider's subject-line logs.

**Rationale**:

- **The login flow depends only on the protocol (FR-035).** The backend is picked by
  `EMAIL_BACKEND` and never inspected by the flow.
- **Principle II's "an abstraction must have one concrete present need"** is met three times over.
  There are three environments with different delivery, all required now.
- **`print`, not `logging`, for the console backend.** The application's own module loggers have
  no handler under uvicorn's default logging configuration (only `uvicorn.*` loggers do), so INFO
  records from them are dropped. `print(…, flush=True)` always reaches the developer's terminal
  and `docker logs`, which the CI image job relies on (D11).
- **Plain text only.** A 3-line message needs no HTML. The Resend API accepts `text` alone.

**Alternatives considered**:

- *A base class with inheritance*: rejected. A `Protocol` lets the memory and console senders be
  trivial and keeps tests free to pass any object with `send`.
- *Selecting the backend per request*: rejected. It is chosen once and validated at startup (D7).

---

## D7 — Configuration: one validated settings object, all problems reported at once

**Decision**: `app/core/config.py` gains `AuthSettings` (a frozen dataclass) and
`resolve_auth_settings(environ) -> AuthSettings`, which raises `AuthConfigError` (a `RuntimeError`,
like `DatabaseConfigError`). It reads `EMAIL_BACKEND`, `SECRET_KEY`, `ADMIN_EMAILS`,
`RESEND_API_KEY` and `EMAIL_FROM`. "Production" means `RENDER` is set, the same switch
milestone 3 uses. The full rule table is in
[contracts/configuration.md](./contracts/configuration.md). The main rules:

- On Render: `EMAIL_BACKEND` must be `resend`; unset, `console` and `memory` are refused. All four
  secrets must be present. `SECRET_KEY` must have ≥ 32 characters. `ADMIN_EMAILS` must be non-empty
  and every entry well-formed (FR-041).
- Locally: every setting is optional (FR-042). The defaults are `console` and a fixed,
  development-only `SECRET_KEY`, with a startup warning for each. An empty `ADMIN_EMAILS` gives a
  warning that nobody can sign in. Values that are **present but invalid** are refused everywhere
  (a short `SECRET_KEY`, an unknown `EMAIL_BACKEND`, a malformed admin address, `resend` without
  its key or sender), because a typo should fail fast rather than silently fall back.
- Every problem is collected, and one error lists **every** offending setting by name. Malformed
  admin entries are reported by position ("entry 3"), never by value. No message contains a value
  (FR-041, SC-008).
- The development `SECRET_KEY` is a constant, so local sessions survive `--reload` and container
  restarts (D11 relies on that). It can never be used in production, because production requires
  the variable to be set.

`lifespan` order: `resolve_database_url` → `resolve_auth_settings` → engine → `ensure_at_head` →
`reconcile_admins` → `purge_expired` → `record_boot` (FR-043). Settings are validated before any
database connection, so a refused start is never counted and never touches data. The database-URL
check stays first, so milestone 3's refusal tests and messages are unchanged.

**Rationale**:

- It follows the established pattern: a function over a `Mapping`, easily unit-tested with a dict,
  with errors that name the setting and never the value.
- **Reporting all problems at once** saves an operator a redeploy per missing secret on the first
  production start.

**Alternatives considered**:

- *`pydantic-settings`*: rejected, as in milestone 3. It is a new dependency for five variables,
  and its validation errors echo input values by default, which is a secret leak risk.
- *Validating lazily on first login*: rejected. It violates FR-041's "refuse to start".

---

## D8 — The client address for the per-client limit

**Decision**: `client_address(request, trust_forwarded)` returns:

- on Render (`trust_forwarded=True`): the **first** entry of `X-Forwarded-For`, trimmed, falling
  back to the socket peer if the header is absent or empty;
- elsewhere: the socket peer (`request.client.host`), or `"unknown"`.

The value is used only as a rate-limit key, hashed (D5). It is never logged or stored in plain form.

**Rationale**:

- Behind Render's proxy the socket peer is the proxy, so every visitor would share one bucket and
  one client could lock everyone out.
- Render staff state that Render puts the real client IP **first** in `X-Forwarded-For`.
  Uvicorn's `--forwarded-allow-ips='*'` would do the same thing less visibly, and would also
  rewrite the scheme and host for the whole app. An explicit function keeps the rule in one
  tested place.

**Residual risk (recorded in plan Complexity Tracking)**: Render **appends** to a client-supplied
`X-Forwarded-For` rather than replacing it, so the first entry can be spoofed. A determined
attacker can then rotate fake addresses and bypass the **per-client** limit. The **per-email**
limit (FR-017) and the per-code attempt limit (FR-016), which alone bound guessing (SC-005) and
flooding any single inbox, do not depend on the client address. The per-client limit is defence in
depth against casual spraying. Quickstart V9 checks the real behaviour once in production, and the
result is recorded there. If Render documents a trustworthy header (for example `True-Client-IP`)
later, only `client_address` changes.

**Alternatives considered**:

- *Last `X-Forwarded-For` entry*: rejected. Render sits behind Cloudflare, so the last hop is an
  edge address shared by many clients.
- *`CF-Connecting-IP` / `True-Client-IP`*: not guaranteed by Render's documentation, and if a
  header is not set by the platform, a client can set it.

---

## D9 — Cleanup without a scheduler

**Decision**: `purge_expired(session, now)` in `app/services/login.py` deletes:

- sessions with `expires_at <= now`;
- login codes that are expired or used;
- rate-limit hits older than one hour.

It runs once at startup (after reconciliation) and at the end of every code-issuing background
task (D10). Every read path also checks expiry itself, so correctness never depends on cleanup
timing (FR-026, US4-5).

**Rationale**: the constitution forbids new infrastructure (no cron, no worker). The three
`DELETE`s are indexed and touch a handful of rows. Login activity is exactly when rows accumulate,
so cleaning up there keeps the tables small without a timer.

**Alternatives considered**: *APScheduler or a background thread*: rejected. That is a new
dependency or a hand-rolled scheduler. On Render's free tier the instance sleeps when idle, so a
timer would not fire reliably anyway.

---

## D10 — Step 1 does identical work for every address; the email is issued and sent after the response

**Decision**: `POST /login` with a well-formed address, for **every** address, does the same work:

1. Checks and records the two rate-limit hits (D5) and commits.
2. Schedules a FastAPI **background task**, `deliver_login_code(engine, sender, settings, email)`.
3. Renders the step-2 page with "If this address belongs to an account, a code is on its way…"
   (HTTP 200).

The background task, which runs after the response is sent, opens its own database session. It
looks up an **active** user by email. If there is one, it deletes their older codes, issues a new
code, commits, and sends the email. If there is none, it does nothing. It then runs
`purge_expired`. It catches every exception and logs only the exception type and, for delivery
failures, the HTTP status. It never logs the address, the code or the body (FR-039).

**Rationale**:

- **The response is identical by construction (FR-010, SC-004).** The known-vs-unknown difference
  (a user lookup, a code insert, an HTTP call to Resend) all happens after the response. The
  in-request work is byte-for-byte the same queries for every address, so there is no timing
  signal to measure. That is stronger than the requirements' "send in a background task", which
  would still leave the lookup and insert in the request.
- **Provider outages are invisible to the user (US6-6).** The response is already sent. The user
  can request a new code later, within limits.
- **Tests see the result immediately.** Starlette's `TestClient` runs background tasks before
  `client.post` returns, so the memory outbox is already populated when the test reads it.

**Alternatives considered**:

- *Issue the code in the request and only send in the background*: rejected. It leaves a
  measurable timing difference (user lookup plus insert only for known addresses) and branches the
  request path.
- *Artificial delays to equalise timing*: rejected. That is fragile, slows every login, and is
  unnecessary once the branch leaves the request.

---

## D11 — Plain forms, no redirect between the steps; the email travels in a hidden field

**Decision**:

- `GET /login` renders step 1 (the email form). `POST /login` **renders step 2 directly** (HTTP 200,
  not a redirect), with the email in a hidden field, as the requirements specify.
- `POST /login/code` redirects with **303** on success. On failure it re-renders step 2 with the
  generic message (HTTP 400).
- `POST /logout` always redirects with 303.
- Form fields are declared as plain `str = Form("")` parameters. Validation is done in the handler
  through the `app/schemas/auth.py` models, so an invalid submission re-renders the page with a
  friendly message instead of FastAPI's 422 JSON.
- Step 2 offers **"Send a new code"** (a small form posting the hidden email back to `POST /login`,
  rate-limited like any request) and **"Use a different email"** (a link to `GET /login`, keeping
  `next`) (FR-014, US1-7).

**Rationale**:

- **Keeps the email out of URLs.** Redirecting from step 1 to a `GET` step 2 would need the email
  in the query string, and uvicorn's access log prints every request line: personal data in logs
  (Principle V). The only alternative is a pending-login cookie, which contradicts the specified
  hidden field.
- **FR-008's "redirect after submission"** is honoured where it matters. The two submissions that
  change state visible to the browser (sign-in, sign-out) redirect, so a refresh never re-submits
  them. Refreshing step 2 re-posts step 1, which the browser warns about, and it is harmless: at
  most one more rate-limited code request.
- **Requires `python-multipart`**, the package FastAPI and Starlette use to parse any form body
  (`Form(...)` or `request.form()`). It is not installed yet, so it is the milestone's one new
  runtime dependency (justified in the plan).

**Alternatives considered**:

- *POST-redirect-GET with the email in the query string*: rejected (personal data in access logs).
- *Parsing `application/x-www-form-urlencoded` by hand with `urllib.parse`*: rejected. It
  reimplements a well-tested parser to save one small, standard, pure-Python dependency.
- *HTMX-driven steps*: excluded by FR-033.

---

## D12 — Safe "return to" addresses

**Decision**: `safe_next_path(value) -> str` returns `value` unchanged only if **all** hold:

- it is at most 2,048 characters;
- it starts with a single `/`, not `//`, and contains no `\`, no control characters and no
  whitespace;
- `urllib.parse.urlsplit` gives an empty scheme and netloc;
- its path is not `/login`, `/login/code` or `/logout`.

Otherwise it returns `/`. It is applied when a login page is rendered (to the hidden field), when
a signed-in user opens `/login` (FR-031), and on successful sign-in (FR-030). A protected page's
own query string is preserved exactly (edge case).

**Rationale**: these are the standard open-redirect tricks: absolute URLs, `//evil.example`,
`/\evil.example` (browsers treat `\` as `/`), and `javascript:`. Rejecting the auth pages prevents
loops. Returning `/` rather than an error keeps the flow friendly.

**Alternatives considered**: *An allowlist of known paths*: rejected. It would need an update with
every new page, and the check above is already safe.

---

## D13 — Administrator reconciliation: idempotent, concurrency-safe, counts only

**Decision**: `reconcile_admins(session, emails) -> ReconcileResult(created, reactivated,
deactivated, unchanged)` in `app/services/users.py`, run in one transaction:

1. For each listed address (already normalised and de-duplicated by the settings loader):
   - if it is missing, insert an active `admin` user (**created**);
   - if it exists but is inactive, activate it (**reactivated**);
   - if it is already an active admin, leave it (**unchanged**).
2. Deactivate every active admin not in the list (**deactivated**), with one `UPDATE`.
3. Delete the sessions and login codes of **every** inactive user, with two `DELETE … WHERE user_id
   IN (SELECT id FROM users WHERE is_active = false)`. This is idempotent and also cleans up after
   any earlier partial run.
4. Commit and return the counts.

`updated_at` changes only on rows that actually changed, so a second run writes nothing (SC-007).
If the commit fails with an `IntegrityError`, the caller rolls back and runs it **once more**.
The only conflict possible is a concurrent instance inserting the same new address; the retry sees
that row and counts it as unchanged, which gives the same end state (FR-005, edge case).

`lifespan` logs `Administrators reconciled: 1 created, 0 reactivated, 0 deactivated, 2 unchanged`
on the `uvicorn.error` logger, with counts only and no addresses (FR-006).

**Rationale**:

- It is portable (no dialect-specific upsert), obviously idempotent, and it never hard-deletes
  users (spec: later milestones link records to them).
- **A retry instead of an advisory lock.** Milestone 3 already justified one PostgreSQL-only lock
  for migrations. Reconciliation doesn't need one: the unique constraint on `email` already
  serialises the only conflicting operation.

**Alternatives considered**:

- *Deleting unlisted admins*: rejected by the spec.
- *Running reconciliation inside the Alembic migration*: rejected. Migrations are frozen snapshots
  and must not read runtime configuration, and the list changes without a new migration.

---

## D14 — Pipeline: the public page is private now, so the checks sign in or check privacy

**Decision**:

- **`checks.yml` → `image` job** (every PR and every release): the container starts with
  `ADMIN_EMAILS=ci-admin@example.com` and the default `console` backend. The job:
  - checks that anonymous `GET /` → 303 to `/login?next=%2F`;
  - posts the email to `/login`;
  - **reads the code from `docker logs`** (the console backend's output);
  - posts it to `/login/code` with a cookie jar, and expects 303 and a `Set-Cookie`;
  - checks the milestone-3 home page (samples, `data-engine="postgresql"`, `data-boots="1"`);
  - **restarts the container** and checks the same cookie jar still works: the server-side session
    survived the restart, and `data-boots="2"`.

  It also adds two refusal checks with `RENDER=true`:
  - no auth settings → non-zero exit, output names all five settings;
  - a full set with `EMAIL_BACKEND=console` → refused naming `EMAIL_BACKEND`, and the dummy
    `SECRET_KEY` value does **not** appear in the output.
- **`deploy.yml`** (after each release): the *Verify data* step (boot count on the anonymous home
  page) cannot work any more and is replaced by *Verify access control*, done by the new
  `scripts/verify_private.sh <base-url>`:
  - `GET /` → 303 with `Location: /login?next=%2F`;
  - `GET /login` → 200 with the email form;
  - `GET /healthz` still answers without a cookie.

  The *Expected revision* and *Previous boot count* steps and `scripts/database_status.sh` are
  removed. The single-head check stays in the test suite (`test_migrations.py`).
- **`/healthz` is unchanged**: exactly three keys, no I/O. The boot count is **not** moved there.

**Rationale**:

- The image job's sign-in is the **real flow**: the real packaged image, PostgreSQL, the console
  backend, and a code read from where a developer would read it. There is no bypass (FR-034).
  It keeps milestone 3's "boot count rises across a restart, data intact" check on every PR, and
  adds "sessions survive a restart".
- A production release cannot sign in without a real inbox, and putting a production session
  cookie in GitHub would be a standing credential. What a release *can* prove anonymously is that
  the new commit is serving (`wait_for_release.sh`, unchanged) and that it is private. The startup
  guard already proves the database is reachable and at head, because the instance would not
  answer otherwise. The spec anticipates that the boot-count check "now requires signing in"; it
  becomes a once-before-acceptance witness (quickstart V8), recorded in Complexity Tracking.
- The existing `test_health.py` deliberately limits `/healthz` to three keys, so that an
  unauthenticated endpoint exposes no infrastructure detail. Adding the boot count there would
  undo that decision to preserve a check.

**Alternatives considered**:

- *Adding `schema_revision` and `boots` to `/healthz`*: rejected, as above.
- *A public `/status` page*: rejected. It is a new public address outside FR-028's allowlist.
- *A CI-only login bypass or magic code for the pipeline*: forbidden by FR-034.

---

## D15 — Tests: an anonymous `client`, an `admin_client` with a directly created session

**Decision**:

- `tests/conftest.py` sets `EMAIL_BACKEND=memory` for every test (autouse), clears the other auth
  variables, and sets `ADMIN_EMAILS=admin@example.com` for the application fixtures.
- `client` stays anonymous (what it truthfully is).
- A new `admin_client` fixture creates the session **directly** through
  `app.services.sessions.create_session` on the test's database and sets the signed cookie on the
  `TestClient`. This is test-only support. The function exists in the app, but no route or
  configuration exposes session creation without a verified code (FR-034, FR-046).
- A new `outbox` fixture returns `app.state.email_sender.outbox`.
- Existing page tests in `test_home.py` switch from `client` to `admin_client`. `test_home_has_no_
  write_affordance` narrows to "no form or button other than the header's logout form". The
  database-failure test in `test_health.py` does the same.
- `test_routes.py` changes from "every route is read-only" to "the only routes accepting a write
  method are exactly `POST /login`, `POST /login/code` and `POST /logout`" (FR-047 guard). It gains
  the anonymous-access sweep over the whole route table (D4).
- Every new database test runs on both engines through the existing `database_url`
  parametrisation. Pure logic (hashing, `safe_next_path`, email normalisation, settings rules,
  message text, the Resend sender with a fake `post`) goes in `tests/unit/`.
- The timing test (SC-004) runs 50 known and 50 unknown submissions, interleaved, and asserts that
  the medians differ by less than 100 ms. It lives in `tests/integration/test_login_privacy.py`,
  with a generous threshold so it does not flake in CI.

**Rationale**: it keeps existing tests meaningful with minimal churn, keeps the email step real in
the end-to-end tests, and makes the "no bypass" rule checkable, because the only shortcut lives
in `tests/`.

**Alternatives considered**: *Making `client` signed in by default*: rejected. Anonymous is the
case the spec cares most about, and a misleading fixture name invites mistakes.

---

## Summary of resolved unknowns

| Technical Context item | Resolved by |
|---|---|
| Email delivery service (constitution open decision) | D1: Resend HTTP API via `urllib.request`; DKIM/SPF/DMARC at NIC.UA |
| Code format, storage, lifetime, attempts | D2 |
| Session storage, cookie format and signing library | D3: standard library HMAC; no `itsdangerous` |
| How deny-by-default is enforced and tested | D4 |
| Rate-limit storage and algorithm | D5 |
| Email backend abstraction and test outbox | D6 |
| Settings validation and startup order | D7 |
| Client identification behind Render's proxy | D8 (residual risk recorded) |
| Cleanup without a scheduler | D9 |
| Equal responses and timing for known/unknown emails | D10 |
| Form handling, step transitions, new dependency | D11: `python-multipart` |
| Open-redirect protection | D12 |
| Reconciliation idempotency and concurrency | D13 |
| Pipeline checks once `/` is private | D14 |
| Test fixtures without a login bypass | D15 |
