# Data Model: Email Code Authentication (Milestone 4)

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](./plan.md)

Four new tables, all SQLModel models in `app/models/`, and all created by **one** new Alembic
revision. Every timestamp uses `app.core.db.UTCDateTime` and is written from `utc_now()`
(Principle VII). Constraint and index names come from the naming convention in `app/core/db.py`,
so they are identical on SQLite and PostgreSQL. Milestone 3's `questions` and `boot_counter`
tables are unchanged.

```text
users 1 ──< sessions          (user_id → users.id)
users 1 ──< login_codes       (user_id → users.id)
rate_limit_hits               (no relation: keyed by a hash of an email or a client address)
```

---

## 1. `User` — table `users` (`app/models/user.py`)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `email` | `String(254)` | NOT NULL, **unique** (`uq_users_email`) | Always stored normalised: trimmed, lowercased (FR-001). 254 is the maximum length of a deliverable address. |
| `role` | `String(20)` | NOT NULL | Values from `Role(StrEnum)`; this milestone defines only `Role.ADMIN = "admin"`. There is **no** CHECK constraint, so milestone 5 adds `teacher` and `student` to the enum without a migration (FR-001). |
| `is_active` | `Boolean` | NOT NULL | Only active users can obtain a code or keep a session (FR-002, FR-022). |
| `created_at` | `UTCDateTime` | NOT NULL | |
| `updated_at` | `UTCDateTime` | NOT NULL | Changed only when a field actually changes, so a no-op reconciliation writes nothing (SC-007). |

**Validation rules** (in `app/core/security.py`, used both by the settings loader and by the login
form):

- `normalize_email(raw) = raw.strip().lower()`.
- `is_valid_email(value)`: 3 to 254 characters, exactly one `@`, a non-empty local part of at
  most 64 characters, and a domain containing at least one `.` whose labels are non-empty. No
  whitespace and no control characters. This is a structural check, not RFC 5322 in full, and it
  makes no DNS lookup.

**Lifecycle**:

```text
          (listed in ADMIN_EMAILS at start)          (removed from ADMIN_EMAILS at start)
 [none] ───────────────────────────────▶ ACTIVE ─────────────────────────────────▶ INACTIVE
                                           ▲                                          │
                                           └───────── (listed again at start) ────────┘
```

- Rows are **never hard-deleted** (spec, Key Entities).
- A transition to INACTIVE deletes all of the user's sessions and login codes in the same
  transaction (FR-004).
- Only `reconcile_admins` changes users. No route does (FR-007).

## 2. `UserSession` — table `sessions` (`app/models/user_session.py`)

Named `UserSession` in Python to avoid colliding with `sqlmodel.Session`. The table name `sessions`
follows the technical requirements.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `user_id` | `Integer` | NOT NULL, FK → `users.id`, indexed | |
| `token_hash` | `String(64)` | NOT NULL, **unique** | Hex SHA-256 of the random token. The token itself exists only in the signed cookie (FR-021). |
| `created_at` | `UTCDateTime` | NOT NULL | |
| `expires_at` | `UTCDateTime` | NOT NULL, indexed | `created_at + 14 days`, absolute (FR-023). Indexed for cleanup. |

**Validity rule** (checked on every request, before and regardless of cleanup): a row matches the
cookie's token hash, `expires_at > now`, and its user has `is_active = true`. Anything else means
the request is anonymous (FR-022, FR-026).

**Lifecycle**: created on successful code verification. Deleted on logout (only that row, US4-6),
on user deactivation (all rows of the user), or by cleanup once expired.

## 3. `LoginCode` — table `login_codes` (`app/models/login_code.py`)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `user_id` | `Integer` | NOT NULL, FK → `users.id`, indexed | Codes are issued only to existing active users (FR-009). |
| `code_hash` | `String(64)` | NOT NULL | Hex `HMAC-SHA256(SECRET_KEY, "login-code\0" + email + "\0" + code)`. The plain code is never stored (FR-027, research D2). |
| `created_at` | `UTCDateTime` | NOT NULL | |
| `expires_at` | `UTCDateTime` | NOT NULL, indexed | `created_at + 20 minutes` (FR-011). |
| `attempts` | `Integer` | NOT NULL, default 0 | Wrong submissions so far; the code is dead at 5 (FR-016). |
| `used_at` | `UTCDateTime` | NULL | Set once, atomically, on successful verification (FR-011). |

**Live code** means `used_at IS NULL AND attempts < 5 AND expires_at > now`. Issuing a code deletes
the user's other unused codes first, so each user has **at most one** code row that could be live
(newest code wins, FR-011, US5-6).

**State transitions**:

```text
                 wrong code (attempts+1 < 5)
                 ┌──────────┐
                 ▼          │
 [issued] ──▶ LIVE ─────────┘
               │  ├── correct code, conditional UPDATE wins ──▶ USED       (session created)
               │  ├── 5th wrong code ─────────────────────────▶ EXHAUSTED  (rejected even if correct)
               │  ├── now ≥ expires_at ───────────────────────▶ EXPIRED
               │  ├── new code issued for the same user ──────▶ (row deleted)
               │  └── user deactivated ───────────────────────▶ (row deleted)
 USED / EXPIRED / EXHAUSTED ──── cleanup ────▶ (row deleted)
```

USED, EXHAUSTED and EXPIRED all produce the same generic "invalid or expired code" message, as do
an unknown address, an inactive user and no code at all (FR-013, US5-7).

## 4. `RateLimitHit` — table `rate_limit_hits` (`app/models/rate_limit_hit.py`)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `bucket` | `String(32)` | NOT NULL | `code_email` or `code_client` (the values are constants in `app/services/rate_limits.py`). |
| `key_hash` | `String(64)` | NOT NULL | Hex `HMAC-SHA256(SECRET_KEY, "rate-limit\0" + bucket + "\0" + key)`. The key is the normalised email or the client address, never stored in plain form (research D5). |
| `created_at` | `UTCDateTime` | NOT NULL | |

A composite index `ix_rate_limit_hits_bucket_key_hash_created_at` on
`(bucket, key_hash, created_at)` serves the one count query. It is declared explicitly by name in
the model and the migration, because the naming convention's `ix` pattern covers only the first
column.

**Rules** (research D5):

| Bucket | Key | Limit | Window | Counted when |
|---|---|---|---|---|
| `code_email` | normalised email | 5 | sliding 1 h | a well-formed email is submitted to `POST /login`, registered or not, and neither limit is already reached (FR-017) |
| `code_client` | client address (research D8) | 20 | sliding 1 h | same moment (FR-018) |

Refused requests are not recorded. Rows older than one hour are deleted by cleanup (FR-019,
research D9).

## 5. Configuration read from the environment (not stored)

The full contract is in [contracts/configuration.md](./contracts/configuration.md).

| Variable | Parsed into | Consumer |
|---|---|---|
| `EMAIL_BACKEND` | `AuthSettings.email_backend: Literal["console", "memory", "resend"]` | `build_email_sender` |
| `SECRET_KEY` | `AuthSettings.secret_key: str` (≥ 32 characters) | code hashing, rate-limit key hashing, cookie signing |
| `ADMIN_EMAILS` | `AuthSettings.admin_emails: tuple[str, ...]`, normalised, de-duplicated and sorted | `reconcile_admins` |
| `RESEND_API_KEY` | `AuthSettings.resend_api_key: str \| None` | `ResendEmailSender` |
| `EMAIL_FROM` | `AuthSettings.email_from: str \| None` | `ResendEmailSender` |
| `RENDER` | `AuthSettings.production: bool` | the refusal rules, the cookie `Secure` flag, `client_address` trusting `X-Forwarded-For` |

`AuthSettings.__repr__` masks `secret_key` and `resend_api_key`, so an accidental log line or
traceback cannot print them (SC-008).

## 6. In-memory values (not stored)

| Name | Where | Shape |
|---|---|---|
| `EmailMessage` | `app/services/email.py` | frozen dataclass `(to, subject, text)` |
| `ReconcileResult` | `app/services/users.py` | frozen dataclass `(created, reactivated, deactivated, unchanged)`, all `int` |
| `request.state.user` | set by `resolve_access` | `User \| None` for the current request |
| `app.state.settings` / `app.state.email_sender` | set by `lifespan` | `AuthSettings` / `EmailSender` |

## 7. Schema version introduced by this milestone

| Order | Revision (file under `migrations/versions/`) | Change |
|---|---|---|
| 3 | `YYYY_MM_DD_<rev>_create_auth_tables.py` (down-revision `bba0b3665864`) | Creates `users`, `sessions`, `login_codes`, `rate_limit_hits` with their constraints and indexes. Data-free: no user is seeded, because administrators come from `ADMIN_EMAILS` at startup (D13). `downgrade()` drops the four tables in reverse dependency order. |

**Backward compatibility during deploy overlap**: the revision only **adds** tables. Milestone 3's
code, which may briefly run against the new schema while the new release starts (or keeps serving
if the new release refuses to start over missing secrets), never touches them. The existing drift,
single-head and stairway tests in `tests/integration/test_migrations.py` cover the new revision
automatically.

## 8. Requirement → data traceability

| Requirement | Enforced by |
|---|---|
| FR-001 normalised unique email, stored role | `users.email` unique + `normalize_email`; `users.role` |
| FR-004/005 reconcile, idempotent, concurrency-safe | `reconcile_admins` + `uq_users_email` + one retry (research D13) |
| FR-011 6 digits, 20 min, single use, newest wins | `login_codes.expires_at`, `used_at` conditional update, delete-older-on-issue |
| FR-016 5 attempts | `login_codes.attempts` conditional increment |
| FR-017/018/019 limits in the database | `rate_limit_hits` |
| FR-021 token hash only | `sessions.token_hash` |
| FR-022/023 active user, 14 days | session validity rule (§2) |
| FR-026 automatic cleanup, never accept expired | `purge_expired` + expiry predicates on every read |
| FR-027 keyed code hash | `login_codes.code_hash` |
