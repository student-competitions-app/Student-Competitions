# Configuration Contract: the teacher and student lists, and the startup order

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](../plan.md)

Extends milestone 4's authentication settings
([specs/004-email-otp-auth/contracts/configuration.md](../../004-email-otp-auth/contracts/configuration.md)).
Rules C1–C8 and W1–W2 are unchanged. Rationale:
[research D11](../research.md#d11--settings-teacher_emails-and-student_emails-parsed-like-admin_emails).

---

## Inputs (new rows)

| Variable | Meaning | Local default (no `RENDER`) | On Render | Secret? |
|---|---|---|---|---|
| `TEACHER_EMAILS` | comma-separated teacher addresses. **Temporary**: milestone 7 replaces it with teacher management in the application | empty: nobody is a teacher, no warning | optional, may be empty; every entry well-formed | yes (`sync: false`) |
| `STUDENT_EMAILS` | comma-separated student addresses. **Temporary**, as above | empty: nobody is a student, no warning | optional, may be empty; every entry well-formed | yes (`sync: false`) |

The parsing is the same as `ADMIN_EMAILS` for all three lists (one helper). Empty string = unset.
Entries are trimmed and lowercased, empty entries are ignored, duplicates within a list collapse,
and the result is sorted. An address on several lists is one person with several roles. That
merge happens in reconciliation, not here.

## Rules (changes)

| # | Condition | Where | Result |
|---|---|---|---|
| C5 | `ADMIN_EMAILS` empty after parsing | on Render | **unchanged** error (FR-036) |
| C6 | an `ADMIN_EMAILS` entry is malformed | everywhere | unchanged: `ADMIN_EMAILS entry 3 is not a valid email address.` |
| **C9** | a `TEACHER_EMAILS` entry is malformed | everywhere | error: `TEACHER_EMAILS entry <n> is not a valid email address.` (position only, 1-based, one line per bad entry, FR-035) |
| **C10** | a `STUDENT_EMAILS` entry is malformed | everywhere | error: `STUDENT_EMAILS entry <n> is not a valid email address.` |
| W3 | `ADMIN_EMAILS` empty, but another list is not | locally | warning (reworded): `ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator.` |
| **W4** | all three lists empty | locally | warning: `No role lists are set; nobody will be able to sign in.` (replaces W3 in this case) |

All violations are still reported together, in the order C1…C10, in one `AuthConfigError`. **No
message contains a value.** Planting a recognisable address in each list must not make it appear
in any message.

## Outputs

`AuthSettings` gains `teacher_emails: tuple[str, ...]` and `student_emails: tuple[str, ...]`.
`repr` shows `<n addresses>` for all three lists.

## Startup order (FR-038)

```text
resolve_database_url → resolve_auth_settings → create engine → ensure_at_head
  → reconcile_users (one retry; log counts) → purge_expired → record_boot → serve
```

`app.main` builds the mapping
`{Role.ADMIN: settings.admin_emails, Role.TEACHER: settings.teacher_emails, Role.STUDENT:
settings.student_emails}` and passes it to `reconcile_users_with_retry`. A refused start (C9, C10)
happens before any database connection and is never counted, as for the other rules.

## Render (`render.yaml`, added under `envVars`)

```yaml
      # Temporary until milestone 7: comma-separated teacher and student addresses, reconciled on
      # every start like ADMIN_EMAILS. May be left empty. Removing an address logs that person
      # out everywhere at the restart this change triggers.
      - key: TEACHER_EMAILS
        sync: false
      - key: STUDENT_EMAILS
        sync: false
```

**Rollout gate** (spec Dependencies): if real teachers or students should sign in on release day,
enter both values in Render → service → *Environment* before merging to `main`. Leaving them unset
is safe: only administrators can sign in.

## Local sign-in as each role (README, FR-039, SC-009)

With the console email backend (the local default), any address works, because the code is printed
to the terminal:

```bash
ADMIN_EMAILS=admin@example.com \
TEACHER_EMAILS=teacher@example.com,multi@example.com \
STUDENT_EMAILS=student@example.com,multi@example.com \
uv run uvicorn app.main:app --reload
```

Sign in as `teacher@example.com` to see the teacher view, or as `multi@example.com` to see the
role choice and the switch.

## Verification

| Test | Covers |
|---|---|
| `tests/unit/test_auth_config.py` | C9, C10, W3 (reworded), W4; positions; all lists in one message; no value in any message; both lists optional on Render; `repr` counts |
| `tests/integration/test_startup.py` | a malformed `TEACHER_EMAILS` refuses the start before any database access, and the start is not counted |
