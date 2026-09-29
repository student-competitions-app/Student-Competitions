# HTTP Routes Contract: login, logout, and private-by-default pages

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](../plan.md)

Every page is server-rendered HTML (Jinja2 + Pico.css). Forms are plain
`application/x-www-form-urlencoded` posts with full-page responses, with no HTMX and no JavaScript
(FR-033). Rationale: [research D4](../research.md#d4--deny-by-default-access-one-application-level-dependency-and-an-explicit-allowlist),
[D10](../research.md#d10--step-1-does-identical-work-for-every-address-the-email-is-issued-and-sent-after-the-response),
[D11](../research.md#d11--plain-forms-no-redirect-between-the-steps-the-email-travels-in-a-hidden-field),
[D12](../research.md#d12--safe-return-to-addresses).

---

## Access rule (applies to every route)

| Request | Result |
|---|---|
| Route in `PUBLIC_ROUTES` (table below) | served, signed in or not |
| Any other route, valid session | served; `request.state.user` is the user |
| Any other route, no valid session, method `GET`/`HEAD` | **303** `Location: /login?next=<percent-encoded path?query>` |
| Any other route, no valid session, other method | **303** `Location: /login` |
| No route matches | the friendly 404 page (unchanged); no redirect |
| `/static/…` | served by the static mount; never redirected |

"No valid session" covers: no cookie, a malformed cookie, a bad signature (including one made with
a rotated `SECRET_KEY`), an unknown token, an expired session, and an inactive user. It never
produces an error page (edge cases, FR-022).

**`PUBLIC_ROUTES`** (`app/core/auth.py`), the complete allowlist (FR-028):

| Method | Path | Why public |
|---|---|---|
| `GET` | `/login` | step 1 |
| `POST` | `/login` | request a code |
| `POST` | `/login/code` | verify a code |
| `POST` | `/logout` | harmless when anonymous (edge case) |
| `GET` | `/healthz` | Render's health check; also skips the session lookup entirely, so it stays free of I/O |

`HEAD` is accepted wherever `GET` is, as FastAPI already does.

## Session cookie

`Set-Cookie: sc_session=<token>.<signature>; Max-Age=1209600; Path=/; HttpOnly; SameSite=Lax`,
plus `; Secure` when `RENDER` is set (FR-024). The cookie is cleared with the same name, path and
flags and `Max-Age=0`. Its value is never logged.

## Layout header (every page)

- **Signed in**: the application name, the user's email, and a
  `<form method="post" action="/logout"><button type="submit">Log out</button></form>` (FR-032).
- **Anonymous**: the application name only.

The home page body and footer are unchanged from milestone 3.

---

## `GET /login` — step 1

| Case | Response |
|---|---|
| Signed in | **303** `Location: <safe_next_path(next)>` (FR-031) |
| Anonymous | **200** HTML: heading "Sign in", a form `POST /login` with `<input type="email" name="email" required autocomplete="email">`, hidden `next`, and a submit button "Send code" |

`next` (query, optional) is passed through `safe_next_path` before it is written into the hidden
field, so an unsafe value is replaced by `/` already at this point.

## `POST /login` — request a code (also "Send a new code")

Form fields: `email` (string), `next` (string, optional).

| Case | Status | Body | Side effects |
|---|---|---|---|
| `email` empty or malformed after trimming | **400** | step 1 re-rendered with "Enter a valid email address.", the typed value kept | none; nothing is counted (edge case) |
| Rate limit reached for this email **or** this client | **429** | step 1 with "Too many attempts. Please try again later." | none |
| Well-formed email, any other case (active, inactive or unknown user) | **200** | step 2 (below) with "If this address belongs to an account, we have sent a code to it. The code is valid for 20 minutes." | two rate-limit hits committed; background task scheduled (research D10) |
| Database unavailable | **503** | step 1 with "Sign-in is temporarily unavailable. Please try again in a moment." | none; nothing sent, no stack trace (edge case) |

**Identical-response guarantee** (FR-010, SC-004): for any two well-formed addresses under their
limits, the status code and the body are identical except for the echoed email in the hidden field
and the text. The in-request work is the same queries in the same order. Everything that differs
happens in the background task after the response.

**Background task** (`deliver_login_code`): for an active user it deletes older codes, issues a new
one, and sends `login_code_message` through `app.state.email_sender`. For anyone else it does
nothing. It then runs `purge_expired`. Exceptions are caught and logged by type (and HTTP status)
only (FR-039).

**Step 2 page** (rendered by this route, never reachable by `GET`):

- a form `POST /login/code` with hidden `email` and `next`, and
  `<input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]*"
  maxlength="6" required>`;
- a form `POST /login` with hidden `email` and `next` and a button "Send a new code" (FR-014);
- a link "Use a different email" → `/login?next=<next>` (FR-014, US1-7).

## `POST /login/code` — verify a code

Form fields: `email`, `code`, `next` (all strings; `next` optional).

| Case | Status | Body / headers | Side effects |
|---|---|---|---|
| Live code for this normalised email, matching code (whitespace stripped), user active, consume wins | **303** | `Location: <safe_next_path(next)>`, `Set-Cookie: sc_session=…` | code `used_at` set; one `sessions` row created (FR-012) |
| Wrong code, and a live code exists | **400** | step 2 with "Invalid or expired code. Request a new code if needed." | `attempts + 1` (FR-016) |
| No live code (none issued, expired, used, exhausted, superseded), unknown or inactive email, malformed email or code, consume lost a race (double submit) | **400** | same page, same message | none; no session (FR-013, US5-7, edge cases) |
| Database unavailable | **503** | step 2 with the "temporarily unavailable" message | none |

A signed-in user posting here is treated like anyone else. A success replaces their cookie with
the new session.

## `POST /logout`

| Case | Response | Side effects |
|---|---|---|
| Valid session | **303** `Location: /login`, cookie cleared | that session's row deleted (FR-025, US4-1, US4-6) |
| No or invalid session | **303** `Location: /login`, cookie cleared | none (edge case) |

`GET /logout` has no route and answers **405** with the friendly error page. A plain link can never
sign anyone out (edge case).

## `GET /` — home page (changed: now protected)

| Case | Response |
|---|---|
| Anonymous | **303** `Location: /login?next=%2F` (US2-1) |
| Signed in | **200**: exactly milestone 3's page (hero, sample questions, status line, or the unavailable notice) plus the signed-in header (US1-3, FR-032) |

## `GET /healthz` — unchanged

`{"status": "ok", "version": …, "commit": …}` with exactly three keys and no I/O, whether a cookie
is sent or not.

## Routes deliberately absent (FR-007, FR-034, FR-047)

No sign-up, no user or administrator management, no profile, no `GET /logout`, no "resend without
limits", no development or test sign-in route, no magic code. `tests/integration/test_routes.py`
asserts that the only routes accepting a write method are exactly `POST /login`,
`POST /login/code` and `POST /logout`.

## Verification

| Test module | Covers |
|---|---|
| `tests/integration/test_routes.py` | the full route-table sweep: every non-allowlisted route → 303 to `/login` when anonymous; the allowlist is exact and every entry exists; the write-route set is exact (SC-003) |
| `tests/integration/test_login_flow.py` | end to end with the memory outbox; `next` round trip; signed-in `GET /login`; code reuse; expiry (clock moved forward); newest code wins; whitespace; double submit; step-2 controls |
| `tests/integration/test_login_privacy.py` | known vs. unknown vs. inactive: identical status and body; timing medians (SC-004); rate limits per email and per client, persisting across an app restart; generic messages |
| `tests/integration/test_sessions.py` | logout deletes only that session; replayed cookie is anonymous; 14-day expiry; deactivated user; tampered and foreign-key cookies; cookie flags (with and without `RENDER`) |
| `tests/unit/test_safe_next.py` | the open-redirect table from research D12 |
| `tests/integration/test_home.py` | milestone-3 assertions, now through `admin_client`; the header shows the email and the logout form |
