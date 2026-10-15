# Contract: Configuration — Role Lists Retired, Public Base URL (Milestone 8)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D1, D15, D16

This contract changes [specs/005-roles-authorization/contracts/configuration.md](../../005-roles-authorization/contracts/configuration.md)
and [specs/004-email-otp-auth/contracts/configuration.md](../../004-email-otp-auth/contracts/configuration.md).
Everything not listed here is unchanged.

## Variables

| Variable | Before | Now |
|---|---|---|
| `ADMIN_EMAILS` | grants the administrator role; reconciled at each start | **Unchanged meaning, narrower effect**: it grants and removes only the administrator role. A person is deactivated only when no role is left (FR-057). |
| `TEACHER_EMAILS` | grants the teacher role | **Retired.** No longer read. A leftover value is ignored (FR-056). |
| `STUDENT_EMAILS` | grants the student role | **Retired.** As above. |
| `PUBLIC_BASE_URL` | — | **NEW.** The origin used in emailed links, for example `https://brainring.org.ua`. See the rules below. |
| `SECRET_KEY` | session cookies, code hashes, rate-limit hashes | **Also**: the AES-GCM key for sealed links (through HKDF) and the invitation cut-off hashes. |

## Rules for `PUBLIC_BASE_URL`

| # | Rule | Error (names the setting, never the value) |
|---|---|---|
| C11 | On Render it is required. | `PUBLIC_BASE_URL is required when running on Render.` |
| C12 | When set, it is an absolute `http` or `https` URL with a host and no path other than `/`, no query and no fragment. A trailing `/` is removed. | `PUBLIC_BASE_URL must be an absolute URL with no path, query or fragment.` |
| C13 | On Render it must be `https`. | `PUBLIC_BASE_URL must use https when running on Render.` |

- **Unset locally**: links are built from the request's base URL. That is safe on a developer
  machine, and the tests take the link's path from the outbox.
- **`AuthSettings.__repr__`** shows `public_base_url` as is, because it is not a secret.

## Removed rules, changed warnings

- **C9 and C10** (a malformed `TEACHER_EMAILS` or `STUDENT_EMAILS` entry) are **removed**: the
  lists are no longer read.
- **W3** (local) becomes: `ADMIN_EMAILS` is empty → "ADMIN_EMAILS is empty; nobody will be able
  to sign in as an administrator."
- **W4** ("No role lists are set") is **removed**.
- All violations are still reported together, in the order C1…C8, C11…C13, in one
  `AuthConfigError`.

## Effects of rotating `SECRET_KEY` (documented in the README)

Rotating it, in addition to what milestone 4 lists (everyone signed out, codes invalid):

- makes every outstanding invitation and data-deletion link invalid;
- resets the hash-based rate limits;
- resets the invitation cut-offs. This is harmless, because all invitations issued before the
  rotation are invalid too.

## `render.yaml`

- Remove the `TEACHER_EMAILS` and `STUDENT_EMAILS` entries and their comment.
- Add the URL as a plain value. It is not a secret:

  ```yaml
  - key: PUBLIC_BASE_URL
    value: https://brainring.org.ua
  ```
- Update the header comment: "Five secrets are declared below by key only".

**Operations step** (quickstart): after deploy, delete `TEACHER_EMAILS` and `STUDENT_EMAILS`
from the Render dashboard. They are ignored, but keeping them is misleading.

## Start-up order

Unchanged except for the reconcile's input and one filter:

```text
resolve_database_url → resolve_auth_settings → create engine → ensure_at_head
  → reconcile_users(admin_emails only, one retry) → purge_expired → record_boot
  → install AccessLogRedactor on "uvicorn.access"
```

The `retire_role_lists` migration runs earlier, in `alembic upgrade head`, in the container
entrypoint, before the application starts.
