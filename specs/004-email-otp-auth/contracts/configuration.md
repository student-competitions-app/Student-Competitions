# Configuration Contract: authentication settings, and when to refuse to start

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](../plan.md)

One function, `resolve_auth_settings(environ: Mapping[str, str] = os.environ) -> AuthSettings` in
`app/core/config.py`, reads and validates every authentication setting. `lifespan` calls it right
after milestone 3's `resolve_database_url` and before any database connection. Rationale:
[research D7](../research.md#d7--configuration-one-validated-settings-object-all-problems-reported-at-once).

---

## Inputs

| Variable | Meaning | Local default (no `RENDER`) | On Render (`RENDER` set) | Secret? |
|---|---|---|---|---|
| `EMAIL_BACKEND` | `console`, `memory` or `resend` | `console`, with a warning | **must be `resend`** | no; declared with a value in `render.yaml` |
| `SECRET_KEY` | signs session cookies; keys the code and rate-limit hashes | a fixed development constant, with a warning | **required**, ≥ 32 characters | yes (`sync: false`) |
| `ADMIN_EMAILS` | comma-separated administrator addresses | empty, with a warning that nobody can sign in | **required**, non-empty, every entry well-formed | yes (`sync: false`) |
| `RESEND_API_KEY` | Resend API key | none | **required** | yes (`sync: false`) |
| `EMAIL_FROM` | sender, `addr@domain` or `Display Name <addr@domain>`, on the verified domain | none | **required** | yes (`sync: false`) |
| `RENDER` | presence means production (unchanged from milestone 3) | unset | set by Render | no |

Empty strings count as unset. In `ADMIN_EMAILS`, entries are trimmed and lowercased, empty entries
(for example from a trailing comma) are ignored, duplicates collapse, and the result is sorted.

## Rules

Every rule is checked, and all violations are reported together.

| # | Condition | Where | Result |
|---|---|---|---|
| C1 | `EMAIL_BACKEND` set to something other than `console`/`memory`/`resend` | everywhere | error: `EMAIL_BACKEND must be one of console, memory, resend.` |
| C2 | `EMAIL_BACKEND` unset, `console` or `memory` | on Render | error: `EMAIL_BACKEND must be 'resend' when running on Render.` |
| C3 | `SECRET_KEY` unset | on Render | error: `SECRET_KEY is required when running on Render.` |
| C4 | `SECRET_KEY` set and shorter than 32 characters | everywhere | error: `SECRET_KEY must be at least 32 characters long.` |
| C5 | `ADMIN_EMAILS` empty after parsing | on Render | error: `ADMIN_EMAILS must list at least one address when running on Render.` |
| C6 | an `ADMIN_EMAILS` entry is malformed | everywhere | error: `ADMIN_EMAILS entry 3 is not a valid email address.` (position only, 1-based, one line per bad entry) |
| C7 | backend is `resend` (or on Render) and `RESEND_API_KEY` is unset | everywhere | error: `RESEND_API_KEY is required for the resend email backend.` |
| C8 | backend is `resend` (or on Render) and `EMAIL_FROM` is unset or its address part is malformed | everywhere | error: `EMAIL_FROM is required for the resend email backend and must be a valid sender address.` |
| W1 | `SECRET_KEY` unset | locally | warning: `SECRET_KEY is not set; using an insecure development key. Never do this in production.` |
| W2 | `EMAIL_BACKEND` unset | locally | warning: `EMAIL_BACKEND is not set; login emails will be printed to this console.` |
| W3 | `ADMIN_EMAILS` empty | locally | warning: `ADMIN_EMAILS is empty; nobody will be able to sign in.` |

## Errors

`AuthConfigError` subclasses `RuntimeError`. Its message starts with
`Invalid authentication configuration:` followed by one line per violation, in the order C1…C8.
**No message ever contains a setting's value** or any part of it (no key, no secret, no address).
Malformed admin entries are identified by position only (FR-041, SC-008). Warnings go to the
`uvicorn.error` logger at WARNING and name settings only.

**Where an error surfaces** (same as milestone 3's `DatabaseConfigError`):

| Process | Effect |
|---|---|
| uvicorn `lifespan` | the application does not start; uvicorn exits non-zero; the boot is not counted, and nothing has touched the database |
| On Render | the new instance never passes `/healthz`; the deploy fails; the previous release keeps serving (SC-010). The migration step may already have run; the new tables are additive and harmless to the old release. |
| `alembic upgrade head` | unaffected: migrations do not read authentication settings |

## Outputs

`AuthSettings` (frozen dataclass): `production: bool`, `email_backend`, `secret_key`,
`admin_emails: tuple[str, ...]`, `resend_api_key: str | None`, `email_from: str | None`. Its
`repr` masks `secret_key` and `resend_api_key`. It is stored as `app.state.settings`.

Derived constants (in `app/core/security.py` / `app/services/login.py`, **not** configurable in
this milestone): `CODE_TTL = 20 min`, `CODE_MAX_ATTEMPTS = 5`, `SESSION_TTL = 14 days`,
`EMAIL_CODE_LIMIT = 5/h`, `CLIENT_CODE_LIMIT = 20/h`, `MIN_SECRET_KEY_LENGTH = 32`.

## Startup order (FR-043)

```text
resolve_database_url → resolve_auth_settings → create engine → ensure_at_head
  → reconcile_admins (log counts) → purge_expired → record_boot (log boot line) → serve
```

## Render (`render.yaml`)

```yaml
      - key: EMAIL_BACKEND
        value: resend
      - key: SECRET_KEY
        sync: false
      - key: ADMIN_EMAILS
        sync: false
      - key: RESEND_API_KEY
        sync: false
      - key: EMAIL_FROM
        sync: false
```

Values are entered once in Render → service → *Environment* (quickstart B3). Generate
`SECRET_KEY` with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Changing
`ADMIN_EMAILS` in the dashboard triggers a restart, and the restart reconciles the list (US3).

## Verification

| Test | Covers |
|---|---|
| `tests/unit/test_auth_config.py` | every row C1–C8 and W1–W3 with a dict `environ`; all violations in one message; no value appears in any message (asserted by planting a recognisable value in every variable); normalisation, de-duplication and positions of `ADMIN_EMAILS`; `repr` masking |
| `tests/integration/test_startup.py` | `RENDER=true` + valid `DATABASE_URL` + no auth settings → refused and not counted; milestone-3 refusal tests unchanged |
| `checks.yml` `image` job | the same two refusals in the real container (see [pipeline.md](./pipeline.md)) |
