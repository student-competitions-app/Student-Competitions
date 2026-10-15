# Data Model: User Management with Consent — Teachers (Milestone 8)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md) | **Date**: 2026-10-15

All tables are SQLModel models in `app/models/`, created by Alembic migrations (research D18).
Timestamps use `UTCDateTime` from `app.core.db`. Constraint names follow the project naming
convention. Composite constraints are named explicitly, as in milestone 7.

```text
users ─┬─< user_roles                (existing; teacher rows now written only by acceptance)
       ├─1 teacher_profiles          (NEW: one per current teacher)
       ├─< teacher_institutions >─── institutions ─── regions   (NEW link; milestone 7 tables)
       ├─< consent_records >──────── consent_texts  (NEW)
       │        └── inviter_id ──> users
       └─< sessions, login_codes     (existing)

invitation_cutoffs   (NEW; keyed hash of an address, no foreign key)
```

Not stored: the **invitation** (only inside the sealed link) and the **data deletion link**
(sealed; only `users.data_erased_at` is used to refuse reuse).

---

## 1. User — table `users` (CHANGED)

| Column | Type | Rules |
|---|---|---|
| `id` | integer PK | unchanged |
| `email` | `String(254)` NOT NULL UNIQUE | unchanged. Normalised. Replaced by `erased-<id>` on erasure unless the user holds `admin` (research D8). |
| `is_active` | bool NOT NULL | unchanged. Invariant: active ⇔ holds at least one role. |
| `first_name` | `String(100)` NULL | **NEW**. Written only by acceptance and by an administrator's edit. `NULL` = no data stored on consent, or erased. |
| `last_name` | `String(100)` NULL | **NEW**. Same as `first_name`. Both are set together and cleared together. |
| `data_erased_at` | `UTCDateTime` NULL | **NEW**. The time of the latest erasure. Makes older deletion links "used" (research D10). Not personal data. |
| `created_at`, `updated_at` | `UTCDateTime` | unchanged. `updated_at` also moves on acceptance, name edits and erasure. |

**Derived**:

- `has_consent_data(user)` ⇔ `first_name IS NOT NULL` (research D8).
- **Display name**: `"<first> <last>"` when stored, otherwise the email.

**Validation** (`app/schemas/people.py`, research D11):

- Names: control characters are refused on the raw value. Then trim, and the length must be
  1–100 code points. Inner spaces are kept.
- Email: `normalize_email`, then `is_valid_email`, as at sign-in.

**State transitions**:

```text
                 accept (new address)
   (none) ───────────────────────────────▶ active, names set, role(s)
                                               │
          remove teacher (no role left)        │ withdraw / delete my data
   inactive, names kept ◀──────────────────────┤ (no admin role)
        │        ▲                             ▼
        │        │ accept newer invitation   inactive, names NULL, email = erased-<id>
        │        └─────────────────────────────── (terminal: no address left to match)
        │ delete my data
        └──────────────▶ inactive, names NULL, email = erased-<id>

   admin + consent data ──withdraw──▶ active admin, names NULL, email kept
```

---

## 2. UserRole — table `user_roles` (unchanged schema, changed writers)

The schema is unchanged: PK `(user_id, role)`, CHECK `role IN ('admin','teacher','student')`.

| Role | Granted by | Removed by |
|---|---|---|
| `admin` | `reconcile_users` from `ADMIN_EMAILS` only | `reconcile_users` |
| `teacher` | acceptance (`TEACHER_INVITATION.grant`) | remove teacher, withdrawal, data deletion |
| `student` | nobody until milestone 9 (the test cast seeds it directly) | — |

The `retire_role_lists` migration deletes every existing `teacher` and `student` row (research
D16).

---

## 3. TeacherProfile — table `teacher_profiles` (NEW, `app/models/teacher.py`)

| Column | Type | Rules |
|---|---|---|
| `user_id` | integer PK, FK → `users.id` | one row per current teacher |
| `can_create_competitions` | bool NOT NULL, default false | FR-007. Only stored and shown in this milestone (FR-013). |
| `created_at` | `UTCDateTime` NOT NULL | set by `grant` |
| `updated_at` | `UTCDateTime` NOT NULL | changed only when the setting changes |

**Invariant**: the row exists ⇔ the user holds `teacher` ⇔ the user has ≥ 1 `teacher_institutions`
row. `grant` and `revoke` maintain it in one transaction (research D9).

---

## 4. TeacherInstitution — table `teacher_institutions` (NEW, `app/models/teacher.py`)

| Column | Type | Rules |
|---|---|---|
| `user_id` | integer, FK → `users.id`, PK part | |
| `institution_id` | integer, FK → `institutions.id`, PK part | no cascade |
| `access_level` | `String(5)` NOT NULL | CHECK `access_level IN ('read','write')` (`ck_teacher_institutions_access_level`); `AccessLevel` StrEnum |
| `created_at` | `UTCDateTime` NOT NULL | |
| `updated_at` | `UTCDateTime` NOT NULL | changed only when this link's level changes (FR-040) |

- **Primary key** `(user_id, institution_id)`: the same institution cannot be linked twice
  (FR-010).
- **Index** `ix_teacher_institutions_institution_id`, for `count_institution_uses` (FR-012).
- **Adding a link**: the institution must exist, be active, and be in an active region. These rows
  are locked `FOR SHARE` (research D6, D9).
- **Keeping a link**: an existing link is kept even when its institution or region is no longer
  active (FR-011). It is shown as deactivated, and its level cannot be changed (research D9).
- **Deleting an institution** (milestone 7) is refused while any row refers to it. The PostgreSQL
  foreign key is the backstop.

`AccessLevel` labels: `read` → "Read", `write` → "Write". The default for a newly picked
institution is `read` (FR-006).

---

## 5. ConsentText — table `consent_texts` (NEW, `app/models/consent.py`)

| Column | Type | Rules |
|---|---|---|
| `id` | integer PK | what records and the acceptance form refer to |
| `role` | `String(20)` NOT NULL | CHECK `role IN ('teacher','student')` (`ck_consent_texts_role`): invitable roles only |
| `version` | integer NOT NULL | 1, 2, … per role |
| `text` | `Text` NOT NULL | the full wording, plain text with paragraphs |
| `published_at` | `UTCDateTime` NOT NULL | |

- **Unique** `(role, version)`, named `uq_consent_texts_role_version`.
- **Current text of a role**: the row with the highest `version`.
- **Append-only**: rows are inserted by migrations only, and nothing updates or deletes them. A
  test pins the SHA-256 of each published text (research D7).
- **Seed**: `teacher` v1, a placeholder covering what is stored (email, names, institutions with
  access levels, the competitions setting), why, who sees it (administrators; the teacher on
  their profile), that emails are delivered by Resend, and how to withdraw (profile → **Withdraw
  consent**, or **Delete my data** on the sign-in page).

---

## 6. ConsentRecord — table `consent_records` (NEW, `app/models/consent.py`)

| Column | Type | Rules |
|---|---|---|
| `id` | integer PK | |
| `user_id` | integer NOT NULL, FK → `users.id`, indexed | the person who agreed |
| `consent_text_id` | integer NOT NULL, FK → `consent_texts.id` | the exact version accepted. The role is `consent_text.role`. |
| `accepted_at` | `UTCDateTime` NOT NULL | the time **I agree** was processed |
| `inviter_id` | integer NOT NULL, FK → `users.id` | from the invitation. Equals `user_id` for a self-invitation (US6). |
| `invitation_issued_at` | `UTCDateTime` NOT NULL | the invitation's `at` |

- **Written** only by an acceptance that changes something (FR-030), in the same transaction as
  the role grant (FR-031).
- **Never updated or deleted**, including by withdrawal and data deletion: it is the proof of
  consent.
- **Teachers tab "date of consent"**: the latest `accepted_at` among the user's records whose text
  role is `teacher`.

---

## 7. InvitationCutoff — table `invitation_cutoffs` (NEW, `app/models/consent.py`)

| Column | Type | Rules |
|---|---|---|
| `email_hash` | `String(64)` PK part | `HMAC-SHA256(SECRET_KEY, "invitation-cutoff\0" + normalised email)`, hex |
| `role` | `String(20)` PK part | CHECK `role IN ('teacher','student')` (`ck_invitation_cutoffs_role`) |
| `cutoff_at` | `UTCDateTime` NOT NULL | the latest removal or withdrawal for this address and role. Only ever raised. |

- **Written** by:
  - remove teacher: role `teacher`;
  - erasure: every invitable role (research D5, D8).
- **Read** by acceptance: refused unless `invitation.at > cutoff_at`.
- **Holds no readable personal data** (FR-003, FR-034).

---

## 8. RateLimitHit — table `rate_limit_hits` (unchanged schema)

New bucket values (`String(32)`): `invite_inviter`, `invite_email`, `deletion_email` and
`deletion_client` (research D12). Keys are hashed with `hash_rate_limit_key`, as before.

---

## 9. Not stored

### Invitation (sealed link, purpose `invitation`, 7 days)

| Field | Meaning |
|---|---|
| `v` | payload version, `1` |
| `role` | `"teacher"` |
| `email` | normalised address |
| `first`, `last` | cleaned names |
| `details` | role-specific: `{"institutions": [[id, "read"\|"write"], …], "can_create_competitions": bool}` |
| `inviter` | inviter's user id |
| `at` | issue time, integer microseconds since the epoch (UTC) |

### Data deletion link (sealed, purpose `data-deletion`, 1 hour)

| Field | Meaning |
|---|---|
| `user` | user id |
| `at` | issue time, integer microseconds since the epoch |

It is usable while the user has consent data and `data_erased_at` is `NULL` or before `at`
(research D10).

### Short-lived notices (sealed, 10 minutes)

| Purpose | Payload | Used for |
|---|---|---|
| `invitation-sent` | `{"email"}` | the "Invitation sent to …" banner after the redirect |
| `login-prefill` | `{"email"}` | the sign-in field after a successful acceptance |

---

## 10. Migrations (research D18)

| Revision | Upgrade | Downgrade |
|---|---|---|
| `create_consent_and_teachers` (down: `b300a1055049`) | `users` + 3 columns (batch on SQLite). Create `teacher_profiles`, `teacher_institutions` (+ index), `consent_texts` (+ seed teacher v1), `consent_records` (+ index), `invitation_cutoffs`. | drop the five tables and the three columns |
| `retire_role_lists` (down: the above) | Delete the sessions of holders of `teacher`/`student`, and delete those role rows. Every user with no role: deactivated, `email = 'erased-' \|\| id`, `data_erased_at = now`, sessions and login codes deleted. | no-op (documented) |

`tests/integration/test_migrations.py`: `APPLICATION_TABLES` += `teacher_profiles`,
`teacher_institutions`, `consent_texts`, `consent_records`, `invitation_cutoffs`. A new test
checks the retirement against a database seeded at the previous revision.
