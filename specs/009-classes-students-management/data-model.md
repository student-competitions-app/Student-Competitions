# Data Model: Classes and Students (Milestone 9)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md) D1, D2, D9, D13, D14, D18

Two new tables: `classes` and `enrolments`. One new consent text row. Every other table keeps its
schema; some get new writers or new rules, listed below. All timestamps use `UTCDateTime`
(Principle VII). Keys and sorting are computed in Python, so SQLite and PostgreSQL agree.

```text
regions 1───* institutions 1───* classes 1───* enrolments *───1 users
                    │                                             │
                    └───────* teacher_institutions *──────────────┘
```

---

## 1. SchoolClass — table `classes` (NEW, `app/models/school_class.py`)

| Column | Type | Rules |
|---|---|---|
| `id` | integer, PK | |
| `institution_id` | integer, FK `institutions.id`, NOT NULL | Set at creation, never changed (FR-003). |
| `name` | `String(200)`, NOT NULL | As entered after `clean_name` (trimmed, 1–200, no control characters; FR-002). |
| `name_key` | `String(600)`, NOT NULL | `name_key(name)`, never shown. |
| `year_of_study` | integer, NOT NULL | 1–12 (FR-001). `CHECK (year_of_study BETWEEN 1 AND 12)`, named `ck_classes_year_of_study`. |
| `is_active` | boolean, NOT NULL, default true | The class's own status (FR-012). |
| `created_at` | `UTCDateTime`, NOT NULL | |
| `updated_at` | `UTCDateTime`, NOT NULL | Reset only by a change that actually changes something. |

**Constraints**:

- `UNIQUE (institution_id, name_key)`, named `uq_classes_institution_id_name_key`. It makes names
  unique within an institution, ignoring case, deactivated classes included. The same name may
  exist in another institution. Its leading column serves the per-institution list.

**Rules**:

- **Not personal data**: stored on creation (FR-003).
- **Created** only in an available institution, by a teacher with Write access (FR-004, D5).
- **Available** ⇔ `classes.is_active` ∧ `institutions.is_active` ∧ `regions.is_active` (FR-011).
  Computed by `app.services.availability`, never stored (D2).
- **Deleted**:
  - only while no enrolment refers to it (FR-006);
  - or together with its institution when it holds none (FR-007, D14).
- **Sort order**: by `name_key`, then `id`.
- **Display**: "KN-21 · year 2" wherever a class is listed (spec Assumptions).

**State transitions**: `active ⇄ deactivated` (teacher with Write access). Deactivating signs out
every student of the class (D4). Activating writes only the status.

---

## 2. Enrolment — table `enrolments` (NEW, `app/models/enrolment.py`)

| Column | Type | Rules |
|---|---|---|
| `user_id` | integer, PK, FK `users.id` | At most one enrolment per person (FR-008, SC-006). |
| `class_id` | integer, FK `classes.id`, NOT NULL, indexed | The student's class. Its institution is the student's institution (D1). |
| `created_at` | `UTCDateTime`, NOT NULL | The acceptance time. |
| `updated_at` | `UTCDateTime`, NOT NULL | Changed by a move only. |

**Rules**:

- **Personal data** (FR-009):
  - written only by `STUDENT_INVITATION.grant`, in the acceptance transaction;
  - deleted only by `STUDENT_INVITATION.revoke`, which is called by removal, withdrawal and data
    deletion.
- **Invariant**: the person holds the `student` role ⇔ an enrolment row exists. `grant` and `revoke`
  write both together.
  - The only exception is the test cast's directly seeded student roles, which have no row and
    count as usable (research D2).
- **Moves**: `class_id` changes only to an active, available class of the same institution
  (FR-041). A class never moves, so the institution of an enrolment never changes.
- **Blocked** ⇔ the row exists and its class is not available (FR-015). Computed, never stored.
- **Foreign key**: `class_id` has no cascade. A class with an enrolment cannot be deleted: the
  service counts first, and on PostgreSQL the foreign key is the backstop.

---

## 3. ConsentText — table `consent_texts` (unchanged schema, one new row)

| `role` | `version` | `text` | `published_at` |
|---|---|---|---|
| `student` | 1 | `STUDENT_CONSENT_TEXT_V1` (research D13) | 2026-10-19T00:00Z |

- The text never names an institution or a class (FR-039).
- `tests/unit/test_consent_texts.py` pins its SHA-256.
- The existing `CHECK (role IN ('teacher', 'student'))` already admits the row.

---

## 4. Existing tables: changed rules and writers

| Table | Change |
|---|---|
| `users` | No schema change. `first_name` and `last_name` are now also written by a teacher's student edit (FR-041). Acceptance keeps the current names of a person who already holds the teacher or student role (FR-036, research D10). The docstring's role-source list adds the student. |
| `user_roles` | `student` is now granted only by `STUDENT_INVITATION.grant`. It is removed by student removal, withdrawal and data deletion (docstring). |
| `consent_records` | No change. A student record stores no institution or class (FR-040). |
| `invitation_cutoffs` | Now also written for `role = 'student'` by student removal, and by erasure, which already covers every registered role. |
| `rate_limit_hits` | New bucket value `invite_student_inviter` (research D11). |
| `sessions` | Deleted for every student below a deactivated region, institution or class (research D4). Deleted on lookup when the current role is `student` and the person is blocked (research D3). |
| `institutions` | The in-use count adds the enrolments of its classes. Deletion deletes its classes first (FR-007, research D14). |
| `regions` | No change. Deactivation now signs out the students below (research D4). |

---

## 5. Derived views (not stored)

| View | Fields | Built by |
|---|---|---|
| `ReachableInstitution` | `id`, `name`, `region_id`, `region_name`, `access_level`, `label` ("Name — Write") | `teacher_access.list_reachable_institutions` |
| `ClassView` | `id`, `institution_id`, `name`, `year_of_study`, `is_active`, `label` ("KN-21 · year 2") | `classes.list_classes`, `classes.get_class` |
| `StudentRow` | `user_id`, `first_name`, `last_name`, `email`, `class_id` | `students.list_students` |
| `StudentView` | a `StudentRow` with `institution` (`ReachableInstitution`) and `school_class` (`ClassView`) | `students.get_student` |
| `EnrolmentView` | `institution_label` ("Name (Region)"), `class_name`, `year_of_study`, `is_available` | `students.get_enrolment_view` (profile) |

The exact signatures are in [contracts/services.md](./contracts/services.md).

---

## 6. Not stored: the student invitation (sealed link, purpose `invitation`, 7 days)

The milestone 8 payload, with student details:

```json
{
  "v": 1,
  "role": "student",
  "email": "taras@example.org",
  "first": "Taras",
  "last": "Shevchenko",
  "details": {"institution": 12, "class": 34},
  "inviter": 7,
  "at": 1760832000000000
}
```

- `inviter` is the teacher's user id. `at` is the issue time in microseconds, added by `seal`.
- `details` must have exactly these two keys, each a non-boolean integer. Otherwise the link is
  invalid and gets the neutral message.
- The payload version stays `1`, because the teacher payload is unchanged.
- Nothing from the form is stored (FR-028, SC-002).
- The `invitation-sent` notice (10 minutes, `{"email": …}`) is reused for the teacher's
  "Invitation sent to …" banner.

---

## 7. Migration (research D18)

`migrations/versions/2026_10_xx_<rev>_create_classes_and_enrolments.py`, with `down_revision =
"f13dab4dd8ba"`.

**Upgrade**:

1. create `classes`, with its unique constraint, its check constraint and its FK to
   `institutions`;
2. create `enrolments`, with its FK to `users` and `classes`, and the index on `class_id`;
3. insert student consent text v1.

**Downgrade**: delete student consent text v1, then drop `enrolments` and `classes`.

- Constraint names follow the metadata naming convention (`app.core.db`), so they are the same on
  both engines and the drift test passes.
- There is no data step: no person holds the student role after milestone 8.
