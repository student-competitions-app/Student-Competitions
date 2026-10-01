# Data Model: Roles and Authorization (Milestone 5)

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](./plan.md)

This milestone changes two milestone 4 tables, adds one, and adds one Alembic revision. The tables
`login_codes` and `rate_limit_hits` are unchanged. Rationale:
[research D1–D3](./research.md#d1--role-storage-a-user_roles-table-one-row-per-role-held),
[D8](./research.md#d8--reconciliation-generalised-to-three-lists),
[D9](./research.md#d9--session-resolution-one-query-the-role-check-and-the-pre-milestone-upgrade).
Milestone 4's model is in
[specs/004-email-otp-auth/data-model.md](../004-email-otp-auth/data-model.md).

All timestamps are `UTCDateTime` (timezone-aware UTC on both engines). Constraint names come from
the metadata naming convention in `app/core/db.py`, so they are identical on SQLite and
PostgreSQL.

---

## 1. `Role` — in-code enum (`app/models/user.py`)

| Member | Stored value | Label | Order |
|---|---|---|---|
| `ADMIN` | `admin` | Administrator | 1 |
| `TEACHER` | `teacher` | Teacher | 2 |
| `STUDENT` | `student` | Student | 3 |

- `admin` is the value milestone 4 already stores, so existing data needs no translation.
- The **order** is the one used by the role choice (FR-015), the header switch and
  `SessionIdentity.roles`. It is the enum's definition order.
- `ALL_ROLES = frozenset(Role)` is a convenience for pages open to everyone, such as `/`.

## 2. `User` — table `users` (CHANGED)

| Column | Type | Constraints | Change |
|---|---|---|---|
| `id` | `Integer` | PK | unchanged |
| `email` | `String(254)` | NOT NULL, unique (`uq_users_email`) | unchanged (normalised, FR-002) |
| `role` → Python attribute `legacy_role` | `String(20)` | **now NULL-able** | **Unused** from this milestone on. Never read, never written, `NULL` on new rows. Kept so that the previous release keeps working during a deploy overlap. Dropped by milestone 6's first migration ([research D2](./research.md#d2--migration-expand-now-contract-later-the-old-usersrole-column-stays-nullable)). |
| `is_active` | `Boolean` | NOT NULL | unchanged |
| `created_at` | `UTCDateTime` | NOT NULL | unchanged |
| `updated_at` | `UTCDateTime` | NOT NULL | Now also changes when the person's **role set** changes. It is still untouched by a no-op reconciliation (SC-007). |

**Invariant** (maintained by `reconcile_users` in one transaction): **active ⇔ holds at least one
role**. An inactive user has no `user_roles` rows, no sessions and no login codes. That is why
milestone 4's "active user" checks in `get_active_user_by_email` and `verify_code` already
implement FR-010 unchanged.

**Lifecycle** (driven only by reconciliation at start, FR-009):

```text
                 (on ≥1 list)                         (on no list)
  [none] ─────────────────────────▶ ACTIVE ──────────────────────────────▶ INACTIVE
                                    │  ▲                                     │
               (role set changes:   │  │      (on ≥1 list again)             │
                rows added/removed) └──┘ ◀───────────────────────────────────┘
```

| Transition | Role rows | Sessions | Login codes |
|---|---|---|---|
| created / reactivated | rows for each list the address is on | none exist | none exist |
| active → active, roles only **added** | inserted | **kept** (US2-6) | kept |
| active → active, any role **removed** | inserted/deleted | **all deleted** (FR-005, US2-4) | kept |
| active → inactive | all deleted | all deleted | all deleted (FR-005) |

Users are never hard-deleted (FR-008).

## 3. `UserRole` — table `user_roles` (NEW, `app/models/user_role.py`)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `user_id` | `Integer` | PK (part 1), FK → `users.id` (`fk_user_roles_user_id_users`) | |
| `role` | `String(20)` | PK (part 2), NOT NULL, CHECK `role IN ('admin', 'teacher', 'student')` (`ck_user_roles_role`) | a `Role` value |
| `created_at` | `UTCDateTime` | NOT NULL | when the assignment first appeared |

- Primary key `pk_user_roles` = `(user_id, role)`: a person holds each role at most once (Key
  Entities). This is also the constraint that rejects a duplicate insert from a concurrently
  starting instance, which triggers the one retry (FR-006, research D8).
- The composite primary key's index leads with `user_id`, so it serves the per-request join and
  the reconciliation's per-user lookups. No extra index is needed.
- The CHECK constraint is safe here: the product has exactly three roles (FR-001), and a fourth
  would be a spec change with its own migration.
- Rows are written **only** by `reconcile_users` (FR-003, FR-009). Milestone 7 will write them
  from the application.

## 4. `UserSession` — table `sessions` (CHANGED)

| Column | Type | Constraints | Change |
|---|---|---|---|
| `id`, `user_id`, `token_hash`, `created_at`, `expires_at` | | | unchanged |
| `current_role` | `String(20)` | **NULL-able**, no CHECK | **new**: the role this browser is using; `NULL` = signed in, no role chosen yet (FR-011, FR-013) |

There is no CHECK constraint on purpose. The resolver checks the value against the person's
current roles on every request, and anything else, including an unknown string, ends the session
(FR-017). One rule covers both "no longer held" and "never valid".

**States of one session**:

```text
                     code check, 1 role          choose / switch (role held)
   (sign-in) ──────────────────────────▶ ROLE=r ◀──────────────────────────┐
       │                                   │  └────────────────────────────┘
       │ code check, ≥2 roles              │ r no longer held (FR-017), any role removed
       ▼                                   │ by reconciliation, deactivation, expiry, logout
   NO ROLE ──── choose (role held) ───▶ ROLE=r        ▼
       │                                         [deleted]
       │ (pre-milestone session, 1 role:
       │  set automatically on next request, D9)
       └──── logout, expiry, reconciliation ────▶ [deleted]
```

## 5. Configuration read from the environment (not stored)

| Variable | Meaning | Local default | On Render |
|---|---|---|---|
| `ADMIN_EMAILS` | administrators (unchanged) | empty (warning) | required, non-empty |
| `TEACHER_EMAILS` | teachers (**new**, temporary until milestone 7) | empty: nobody is a teacher | optional, may be empty |
| `STUDENT_EMAILS` | students (**new**, temporary until milestone 7) | empty: nobody is a student | optional, may be empty |

Each list is comma-separated. Entries are trimmed, lowercased and de-duplicated, and blank entries
are ignored. A malformed entry refuses the start in every environment
([contracts/configuration.md](./contracts/configuration.md)). The same address on several lists
is one person with several roles.

## 6. In-memory values (not stored)

| Value | Where | Shape |
|---|---|---|
| `SessionIdentity` | `app/services/sessions.py` | frozen: `user: User`, `roles: tuple[Role, ...]` (fixed order, non-empty), `current_role: Role \| None` |
| `request.state.user` / `.roles` / `.current_role` | set by `resolve_access` | from `SessionIdentity`, or `None` / `()` / `None` when anonymous |
| `allowed_roles` | attribute on each declared endpoint, set by `@allow_roles` | non-empty `frozenset[Role]` |
| `Area` / `AREAS` | `app/routers/areas.py` | frozen: `path`, `title`, `roles: frozenset[Role]`; the four placeholders |
| `ReconcileResult` | `app/services/users.py` | `created`, `reactivated`, `deactivated`, `roles_added`, `roles_removed`, `unchanged` (counts only) |
| `AuthSettings.teacher_emails`, `.student_emails` | `app/core/config.py` | sorted, de-duplicated tuples; `repr` shows counts only |

## 7. Schema revision introduced by this milestone

One revision, `add_user_roles`, `down_revision = "a35580dee830"` (milestone 4's auth tables).
Written with plain SQLAlchemy types and table constructs, like its predecessors.

**Upgrade**, in this order:

1. create `user_roles` (composite PK, FK, CHECK);
2. insert one `('admin')` row per **active** user whose `role = 'admin'`, with `created_at` = the
   migration's UTC time. Inactive users get no rows (invariant);
3. add `sessions.current_role` `VARCHAR(20) NULL`. Existing sessions keep `NULL` and are upgraded
   on their next request (D9);
4. alter `users.role` to NULL-able (batch mode on SQLite).

**Downgrade**, in this order:

1. `users.role = 'admin'` for every holder of the administrator role;
2. for every user without the administrator role: `users.role` = their first remaining role (or
   `'admin'` if none), `is_active = false`, and their sessions and login codes are deleted.
   Milestone 4 treats every active user as an administrator, so they must not stay active;
3. drop `sessions.current_role`, drop `user_roles`, and make `users.role` NOT NULL again.

**Compatibility with the previous release** (deploy overlap, refused start): every change is
additive or relaxes a constraint. Milestone 4 code reads `users.role` (still present) and writes
it (still accepted). It ignores `user_roles` and `sessions.current_role`. A milestone 4 session
row remains valid for milestone 5 (D9). The milestone 3 drift, stairway, single-head and
concurrent-upgrade tests cover the revision on both engines.

## 8. Requirement → data traceability

| Requirement | Where it lives |
|---|---|
| FR-001 three roles | `Role` enum; `ck_user_roles_role` |
| FR-002 any non-empty combination, one person | `uq_users_email`; `pk_user_roles`; active ⇔ ≥1 role |
| FR-003 roles only from configuration | `TEACHER_EMAILS`, `STUDENT_EMAILS`, `ADMIN_EMAILS`; only `reconcile_users` writes `user_roles` |
| FR-004–FR-008 reconciliation | `reconcile_users` transitions (§2), `ReconcileResult` |
| FR-010 only active people with a role sign in | invariant (§2) + milestone 4's active checks |
| FR-011 one current role per session | `sessions.current_role` |
| FR-012, FR-013 initial current role | §4 state diagram |
| FR-017 current role still held | resolver check against `user_roles` (§4) |
| FR-022 declared roles per page | `allowed_roles` marker (code, not stored) |
| Key Entities: page access rule is code | `@allow_roles`, `AREAS` |
| SC-010 pre-milestone sessions keep working | `current_role` NULL + automatic upgrade (§4) |
