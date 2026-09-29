# Auth Services Contract: internal interfaces and behaviour matrix

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](../plan.md)

Business logic lives in `app/services/`, and pure helpers live in `app/core/security.py`. Routers
only parse form fields, call these functions, and render. Every function that takes a `Session`
is unit-testable against the both-engines `session` fixture. Clock-dependent functions take `now`
explicitly (default `utc_now()`), so tests move time without patching.

---

## Conventions

- Addresses passed in are already normalised (`normalize_email`). Functions never log addresses,
  codes, tokens or hashes.
- Functions **commit their own unit of work** unless stated otherwise, as milestone 3's services
  do.
- No function here performs authorization. Access is decided before a handler runs, by
  `resolve_access` (see [http-routes.md](./http-routes.md#access-rule-applies-to-every-route)).
  Milestone 5 adds role dependencies in front of routes. Nothing here changes for that.

## `app/core/security.py` (pure, no I/O)

| Function | Contract |
|---|---|
| `normalize_email(raw: str) -> str` | `raw.strip().lower()` |
| `is_valid_email(value: str) -> bool` | the structural rule in [data-model §1](../data-model.md#1-user--table-users-appmodelsuserpy) |
| `generate_code() -> str` | 6 decimal digits from `secrets` |
| `hash_code(secret_key, email, code) -> str` | 64-char hex HMAC (research D2) |
| `new_session_token() -> str` | `secrets.token_urlsafe(32)` |
| `hash_token(token) -> str` | 64-char hex SHA-256 |
| `sign_cookie_value(secret_key, token) -> str` / `unsign_cookie_value(secret_key, value) -> str \| None` | `token.signature`; `None` on any malformation or mismatch (constant-time compare) |
| `hash_rate_limit_key(secret_key, bucket, key) -> str` | 64-char hex HMAC (research D5) |
| `safe_next_path(value: str \| None) -> str` | research D12 |
| `client_address(request, trust_forwarded: bool) -> str` | research D8 |

## `app/services/users.py`

| Function | Contract |
|---|---|
| `get_active_user_by_email(session, email) -> User \| None` | |
| `reconcile_admins(session, emails, now=…) -> ReconcileResult` | research D13; commits; a caller that catches `IntegrityError` rolls back and calls it once more |

## `app/services/sessions.py`

| Function | Contract |
|---|---|
| `create_session(session, user, now=…) -> str` | inserts a row with `expires_at = now + 14 d`; commits; returns the **plain token**. It is the one place a token is created; `admin_client` in tests uses it directly |
| `get_session_user(session, token, now=…) -> User \| None` | one query: token hash, unexpired, active user |
| `delete_session(session, token) -> None` | deletes by token hash if present; commits; idempotent |

## `app/services/rate_limits.py`

| Function | Contract |
|---|---|
| `allow_code_request(session, secret_key, email, client, now=…) -> bool` | counts hits in `(now − 1 h, now]` for both buckets; if either is at its limit, returns `False` and writes nothing; otherwise inserts both hits, commits, and returns `True` |

## `app/services/login.py`

| Function | Contract |
|---|---|
| `issue_code(session, secret_key, user, now=…) -> str` | deletes the user's unused codes, inserts a new one (`expires_at = now + 20 min`), commits, returns the **plain code** (only for the email) |
| `verify_code(session, secret_key, email, code, now=…) -> User \| None` | returns the user when the code is correct and the consume `UPDATE` touched one row; otherwise `None`, after incrementing `attempts` if a live code existed and the code was wrong. Commits |
| `deliver_login_code(engine, sender, settings, email) -> None` | the background task (research D10): its own `Session(engine)`; `issue_code` + `sender.send(login_code_message(…))` for an active user; then `purge_expired`; catches and logs every exception by type |
| `purge_expired(session, now=…) -> None` | research D9; commits |

## Behaviour matrix (each row is a test on SQLite and PostgreSQL)

| # | Given | When | Then |
|---|---|---|---|
| S1 | empty users, list `[a, b]` | `reconcile_admins` | both active admins; result `(2, 0, 0, 0)` |
| S2 | S1 done | `reconcile_admins([a, b])` again | result `(0, 0, 0, 2)`; no `updated_at` changed (SC-007) |
| S3 | `a` has 2 sessions + 1 code | `reconcile_admins([b])` | `a` inactive, 0 sessions, 0 codes; result `(0, 0, 1, 1)` |
| S4 | `a` inactive | `reconcile_admins([a, b])` | `a` active again; result `(0, 1, 0, 1)` |
| S5 | list `[" A@X.org ", "a@x.org"]` via settings | reconcile | one user `a@x.org` |
| S6 | two engines' sessions reconcile the same new list concurrently (PostgreSQL: two connections; SQLite: sequential simulation of the conflict path) | both finish, with one retrying on `IntegrityError` | same end state as one run; no duplicate |
| L1 | active user | `issue_code` twice | only the second code verifies (newest wins) |
| L2 | live code | `verify_code` with the correct code | user returned; `used_at` set; a second call returns `None` |
| L3 | live code | 5 wrong codes, then the correct one | all `None`; `attempts == 5` (FR-016) |
| L4 | code issued at `t` | `verify_code(now = t + 20 min)` | `None` (expiry inclusive) |
| L5 | user deactivated after issue | `verify_code` correct | `None` (code deleted by reconcile) |
| L6 | code for `a` | `verify_code(email=b, code=a's)` | `None` |
| L7 | live code | the correct code with surrounding spaces, via the route | success |
| R1 | 5 hits for email `e` in the last hour | `allow_code_request(e, …)` | `False`; still 5 hits |
| R2 | 20 hits for client `c` across 20 emails | 21st email from `c` | `False` |
| R3 | 5 hits at `t` | `allow_code_request(now = t + 61 min)` | `True` (sliding window) |
| R4 | limit reached | app restarted (new `TestClient` on the same database) | still refused (FR-019, US5-5) |
| P1 | expired session, expired code, used code, 2 h old hit, live ones of each | `purge_expired` | only the live ones remain |
| P2 | expired session **not yet purged** | `get_session_user` | `None` (FR-026) |
| X1 | session for an inactive user (created before deactivation, row somehow left) | `get_session_user` | `None` |
