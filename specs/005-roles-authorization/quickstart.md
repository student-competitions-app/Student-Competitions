# Quickstart & Validation: Roles and Authorization (Milestone 5)

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](./plan.md)

How to run the milestone and prove it works, from a laptop and on production. This is a run and
validation guide. The rules themselves are in the [contracts](./contracts/) and the
[data model](./data-model.md).

Scenarios marked *(automated)* run in CI on every pull request or release. Scenarios marked
*(manual, required once)* are done once before the milestone is accepted, and the result is
recorded in the PR description.

---

## Prerequisites

- Milestone 4 merged, deployed and passing (spec Dependencies).
- A local checkout on branch `005-roles-authorization`, `uv sync` done.
- Optional, for the PostgreSQL half of the suite: `TEST_POSTGRES_URL` as in the README.
- For the production checks: two real inboxes you control, besides an administrator inbox already
  in `ADMIN_EMAILS`.

## Rollout gate (production). Before merging to `main`

Only needed if real teachers or students should sign in on release day. Leaving both lists unset
is safe: the application starts, and only administrators can sign in.

### R1: Enter the lists in Render

Render → `student-competitions` → *Environment*:

- `TEACHER_EMAILS` = comma-separated teacher addresses;
- `STUDENT_EMAILS` = comma-separated student addresses.

Saving restarts the **current** release, which ignores these keys. That is harmless. The release
of this milestone reconciles them at its first start. Check every entry for typos: a malformed
entry makes the new release refuse to start (the previous one keeps serving), and the deploy log
names the list and the position.

## Running locally: sign in as each role

```bash
ADMIN_EMAILS=admin@example.com \
TEACHER_EMAILS=teacher@example.com,multi@example.com \
STUDENT_EMAILS=student@example.com,multi@example.com \
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/>, sign in with any of the addresses, and read the 6-digit code from
the terminal (console backend). The startup log shows
`Users reconciled: 4 created, … 5 roles added, …`, with counts only.

## Running the suite

```bash
uv run ruff check && uv run ruff format --check && uv run pytest
```

---

## Validation scenarios

### V1: A developer signs in locally as every role (FR-039; SC-009)

1. Start as above. Sign in as `teacher@example.com`. You land on `/` with no extra step. The header
   reads `Student Competitions · Teacher`, and the home page lists *Teacher area* and *Staff
   area*.
2. Open `/teacher` and `/staff`: both show their placeholder. Open `/admin` and `/student`: both
   show **Access denied**, naming *Teacher*, with a link home.
3. Log out and repeat as `admin@example.com` (Administrator area, Staff area) and as
   `student@example.com` (Student area only).
4. **Expected**: the access table in [contracts/http-routes.md](./contracts/http-routes.md#access-rule-applies-to-every-route)
   holds for all three, all within 15 minutes using only the README.

### V2: A multi-role person chooses, then switches (US3, US4; SC-004, SC-005)

1. Logged out, open `/teacher`. You are sent to login. Sign in as `multi@example.com`.
2. **Expected**: the role choice appears, offering exactly *Teacher* and *Student*, in that order,
   with your email and **Log out** in the header but no role. Opening `/` in another tab sends you
   back to the role choice.
3. Choose *Teacher*. **Expected**: you land on `/teacher`, and the header reads `· Teacher` with a
   *Switch to Student* button.
4. Press *Switch to Student*. **Expected**: you land on `/`, the header reads `· Student`, the home
   page lists only *Student area*, and `/teacher` now shows **Access denied**. You were not asked
   to sign in again.
5. In a private window, sign in as the same person and choose *Student*. Switch the first window
   to *Teacher*. **Expected**: the private window is still *Student* after a reload (US4-5).

### V3: The automated suite proves the flow, the boundaries and the rules (all stories; FR-040, FR-041; SC-001, SC-002, SC-007, SC-008) *(automated)*

`uv run pytest` passes on SQLite, and on PostgreSQL in CI. The milestone's `_Test:_` line maps to:

| `_Test:_` clause | Test module |
|---|---|
| each role opens exactly its pages, "access denied" elsewhere | `tests/integration/test_access_control.py` (15-case matrix) |
| the home page shows each role only its own links | `tests/integration/test_access_control.py` |
| multi-role asked to choose; single-role not | `tests/integration/test_role_choice.py` (full flow through the `memory` outbox) |
| admin + student using student cannot open the administrator page | `tests/integration/test_role_switch.py` |
| removed from one list → logged out; from every list → cannot sign in | `tests/integration/test_user_reconcile.py` (restart-based), `tests/integration/test_login_flow.py` |
| every route declares roles or is allowlisted; an undeclared one fails | `tests/integration/test_routes.py` |

Also covered: reconciliation S1–S11, session resolution G1–G6, the cross-site table, configuration
C9/C10/W3/W4, the migration (upgrade, downgrade, drift, stairway) and the pre-milestone session
upgrade ([contracts/auth-services.md](./contracts/auth-services.md)).

### V4: The packaged image enforces a role boundary and refuses a cross-site post (FR-021, FR-023) *(automated on every PR)*

The `checks.yml` `image` job signs in as the CI administrator. `/admin` must answer 200, `/student`
must answer 403, the header must show `Administrator`, and a cross-site `POST /logout` must answer
403 and leave the session alive ([contracts/pipeline.md](./contracts/pipeline.md#checksyml--image)).

### V5: The release proves a role page is private (FR-023) *(automated on every release)*

`scripts/verify_private.sh` asserts that an anonymous `GET /admin` on the public address answers 303
to `/login?next=%2Fadmin`, besides milestone 4's checks.

### V6: An administrator signed in before the release keeps working (SC-010) *(manual, required once)*

1. Before merging, sign in on production as an administrator, in a browser you keep open.
2. After the release is live, reload `/`. **Expected**: no sign-in and no role choice. The header
   reads `· Administrator`, and *Administrator area* and *Staff area* are listed.

### V7: Real teachers and students sign in on production (US1, US2) *(manual, required once)*

1. With R1 done (one test address on `TEACHER_EMAILS`, one on both `TEACHER_EMAILS` and
   `STUDENT_EMAILS`), sign in with each from a real inbox.
2. **Expected**: the single-role address lands directly with `· Teacher`. The two-role address sees
   the role choice and can switch, as in V2.

### V8: Removing a role on production logs the person out everywhere (US2-4, US2-5; SC-006) *(manual, required once)*

1. Sign the two-role test address in on two browsers.
2. In Render, remove it from `STUDENT_EMAILS` only, and save (the service restarts).
3. **Expected**: after the restart, both browsers are sent to login on their next request. Signing
   in again gives `· Teacher` with no role choice and no switch.
4. Remove it from `TEACHER_EMAILS` too. **Expected**: its session ends, and requesting a code shows
   the usual step 2, but no email arrives.
5. The deploy log shows only the `Users reconciled: …` counts, with no address.

### V9: No addresses in logs (FR-007; SC-008) *(manual, required once)*

Search the Render log for the release window, covering V6–V8, for `@`. **Expected**: no email
address appears in any line written by the application, including the reconciliation, the role
choice and switch, and `Access denied:` lines.

---

## Milestone acceptance checklist

- [x] V3 green in CI on both engines; `ruff check` and `ruff format --check` clean
- [x] V4 green in the `image` job
- [x] V5 green in the release
- [x] V1 and V2 done locally
- [x] V6, V7, V8 and V9 done on production, with results noted in the PR
- [x] README documents `TEACHER_EMAILS` and `STUDENT_EMAILS` (purpose, format, local default,
      production rule, temporary until milestone 7) and local sign-in as each role (FR-039)
- [x] `render.yaml` declares both keys with `sync: false` (FR-034)

## Reference

- Spec: [spec.md](./spec.md). Plan: [plan.md](./plan.md). Decisions: [research.md](./research.md).
- Routes: [contracts/http-routes.md](./contracts/http-routes.md). Services:
  [contracts/auth-services.md](./contracts/auth-services.md). Settings:
  [contracts/configuration.md](./contracts/configuration.md). Pipeline:
  [contracts/pipeline.md](./contracts/pipeline.md).
