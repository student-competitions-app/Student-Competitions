# Data Model: Teams (Teacher) (Milestone 11.1)

Phase 1 of [plan.md](./plan.md). The decisions are in [research.md](./research.md) R1–R3 and
R5–R9.

## 1. Team: table `teams` (new)

| Column | Type | Null | Rules |
|---|---|---|---|
| `id` | `INTEGER` primary key | no | Never reused in practice: teams are never hard-deleted (R1). |
| `institution_id` | `INTEGER`, FK → `institutions.id` (no `ON DELETE`), index `ix_teams_institution_id` | no | Set at creation and never changed: no function writes it after the insert (FR-001). The index serves the **Team** list and the institution's in-use count (R8). |
| `name` | `VARCHAR(200)` (`NAME_MAX_LENGTH`) | no | As entered after `clean_name`: trimmed, 1–200 code points, no control characters (FR-002). Shown everywhere. |
| `name_key` | `VARCHAR(600)` (`NAME_KEY_MAX_LENGTH`) | no | `name_key(name)`: NFC, then case-folded. Never shown. Unique among live teams (below). |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no | Set once at creation (UTC). |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no | Set at creation, and reset by a rename that changes something. A deletion leaves it alone. |
| `deleted_at` | `TIMESTAMP WITH TIME ZONE` | yes | `NULL` while live; set once by a deletion and never cleared (FR-007, R1). |

**Indexes**:

- `ix_teams_institution_id` on `institution_id`.
- `uq_teams_name_key_live`: `UNIQUE (name_key) WHERE deleted_at IS NULL`. It is declared on the model
  as
  `Index("uq_teams_name_key_live", "name_key", unique=True, sqlite_where=…, postgresql_where=…)`,
  both with `deleted_at IS NULL` (R2). It applies across all institutions.

**Model** (`app/models/team.py`, class `Team`, exported from `app.models`). Its docstring states:

- the live rule, and that milestone 12 may add only live teams;
- that the team is not personal data, while its memberships are;
- that every team counts as a use of its institution.

**Derived states**:

| State | Condition | On the Teams tab | Rename, delete, add or remove members | Milestone 12 may add it |
|---|---|---|---|---|
| Live | `deleted_at IS NULL` and its institution and region active | listed | yes (Write) | yes |
| Out of reach | `deleted_at IS NULL`, institution or region deactivated | the institution is not offered | no: "access denied" | not offered |
| Deleted | `deleted_at IS NOT NULL` | never | no: "access denied" (FR-008) | **never** |

**Transitions**:

```text
(none) --create--> Live --delete--> Deleted   (terminal; no restore, FR-007)
Live <--institution or region deactivated / activated--> Out of reach
```

- **A rename** keeps a team Live and changes `name`, `name_key` and `updated_at`.
- **The institution** never changes.

**Not stored**: who created or changed a team (spec Assumptions). Teams hold no personal data and
are untouched by data erasure.

## 2. Team membership: table `team_memberships` (new)

| Column | Type | Null | Rules |
|---|---|---|---|
| `team_id` | `INTEGER`, FK → `teams.id` (no `ON DELETE`), primary key part 1 | no | The team. A deleted team keeps its rows (FR-007). |
| `user_id` | `INTEGER`, FK → `users.id` (no `ON DELETE`), primary key part 2, index `ix_team_memberships_user_id` | no | The student. At most once per team, by the primary key (FR-003). The index serves the profile and the erasure delete. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no | When the student was added (UTC). Never shown. |

**Model** (`app/models/team.py`, class `TeamMembership`, exported from `app.models`). Its
docstring states:

- that it is personal data of the student;
- that its only writers are `teams.add_member` (insert) and `teams.remove_member` and
  `STUDENT_INVITATION.revoke` (delete);
- that a membership's team belongs to the student's enrolled institution.

**Rules**:

| Rule | Where it is enforced |
|---|---|
| Once per team | the primary key; an `IntegrityError` in a race becomes "already in this team" (R3) |
| Same institution only | `add_member`: the student's class must be in the team's institution (R4) |
| At most 50 per team, blocked members included | `add_member`, counting under the team row's `FOR UPDATE` (R5) |
| A blocked student cannot be added or removed | `reach_student` refuses a student whose class is deactivated (R4) |
| Kept when the team is deleted or the student is blocked | nothing writes them then (FR-007, FR-010) |
| Erased with the student role, consent or data, in deleted teams too | `STUDENT_INVITATION.revoke` (R7) |

**Queries** (`app.services.teams`, R6):

- **Active members of a team**:
  - `team_memberships` joined to `users`, `enrolments`, `classes`, `institutions` and `regions`;
  - `WHERE team_id = :t` and the class, the institution and the region all active;
  - sorted in Python by last name, then first name (case-folded), ties by `user_id`.
- **All members of a team** (the limit): `SELECT count(*) FROM team_memberships WHERE team_id = :t`.
- **Member ids of a team** (for "In this team"): `SELECT user_id … WHERE team_id = :t`.
- **A student's teams** (the profile): `team_memberships` joined to `teams`, `WHERE user_id = :u`,
  deleted teams included, sorted by `name_key`, ties by id.
- **Erasure**: `DELETE FROM team_memberships WHERE user_id = :u`.

## 3. Educational institution: table `institutions` (unchanged schema)

- **In use** (`count_institution_uses`) now also counts every team of the institution, deleted ones
  included (FR-017, R8). An institution with any team is refused deletion with the existing "in
  use" page.

## 4. Student enrolment: table `enrolments` (unchanged)

- **The team's institution** must be the student's enrolled institution, through the class
  (FR-003).
- **Moving to another class** of the same institution does not touch memberships (FR-005).

## 5. Consent text: table `consent_texts` (unchanged schema; one row rewritten)

The row `role = 'student', version = 1` gets a new `text`. Its `id`, `version` and `published_at`
(2026-10-19) are unchanged, and every consent record keeps pointing at it (FR-015, R9).

**The new text** (`STUDENT_CONSENT_TEXT_V1_REWRITE`), paragraphs separated by blank lines. The
fourth paragraph is unchanged.

> By pressing "I agree" you consent to Student Competitions storing the following data about you
> as a student: your email address, your first and last name, your class, which also records your
> educational institution and your year of study, and your team memberships: the teams of your
> educational institution that you belong to. The application also records when you agreed, to
> which version of this text, and who invited you.
>
> We store this data so that you can sign in as a student and take part, as a member of your
> teams, in the competitions of your educational institution. Nothing about you was stored before
> you agreed.
>
> Your data, including your teams, is seen by the teachers linked to your educational institution,
> and by you on your profile page. It is not shared with anyone else.
>
> Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email
> delivery service, which receives your email address and the content of each message for that
> purpose only.
>
> You can withdraw your consent at any time: open your profile and press "Withdraw consent", or,
> without signing in, use "Delete my data" on the sign-in page. Your names, your email address,
> your class and your team memberships are then erased and your student role is removed. The
> record that you agreed to this text is kept as proof of your consent.

It still covers every milestone 9 topic ("email address", "first and last name", "class", "year of
study", "educational institution", "so that", "teachers", "Resend", "Withdraw consent", "Delete my
data"). It adds "team memberships", "teams" and "erased" (FR-015), and names no institution and
holds no placeholder.

**`ConsentText`'s docstring**: "Append-only" gains the one exception, student version 1 rewritten
by the teams migration (milestone 11.1 FR-015).

## 6. Validation rules (from the spec)

| Rule | Where | Refusal |
|---|---|---|
| Team name: trimmed, 1–200, no control characters | `app.schemas.names.clean_name` (router for the form, service again) | 400, the form again with the error and the value (FR-033) |
| Team name unique ignoring case among live teams, everywhere | service lookup, then `uq_teams_name_key_live` | 400, "A team named “<entered>” already exists." (FR-002) |
| Teacher role | `@allow_roles(Role.TEACHER)` | 403 (FR-019) |
| Reachable live team; Write for changes | `teacher_access.reach_team` (router, then service under lock) | 403 (FR-021, FR-022) |
| Reachable, unblocked student of the team's institution | `teacher_access.reach_student` and an institution check in the service | 403 (FR-011, FR-022) |
| Active class of the team's institution (Add students) | `teacher_access.reach_class` with `institution_id`, then `is_active` | 403 (FR-038, spec Edge Cases) |
| Not already a member | primary key; service lookup first | 303 to the tab with the "already" notice (FR-042) |
| At most 50 members | service count under the team lock | 303 to the Add students page, which says the team is full (FR-042) |
| An institution with any team cannot be deleted | `institutions.count_institution_uses` | 409, "in use", deactivate instead (FR-017) |

## 7. Migration `teams` (revision after `3e32707ed794`)

File `migrations/versions/2026_10_29_<rev>_teams.py`: a frozen snapshot with plain SQLAlchemy
types, no imports from `app`, and constraint names following the project's naming convention.

**Upgrade**:

1. `create_table("teams", …)`:
   - the columns of §1;
   - `pk_teams`;
   - `fk_teams_institution_id_institutions`;
   - then `ix_teams_institution_id`;
   - then `uq_teams_name_key_live` with `sqlite_where` and `postgresql_where` set to
     `deleted_at IS NULL`.
2. `create_table("team_memberships", …)`:
   - the columns of §2;
   - `pk_team_memberships` on `(team_id, user_id)`;
   - `fk_team_memberships_team_id_teams`;
   - `fk_team_memberships_user_id_users`;
   - then `ix_team_memberships_user_id`.
3. `UPDATE consent_texts SET text = STUDENT_CONSENT_TEXT_V1_REWRITE WHERE role = 'student' AND
   version = 1`.

**Downgrade** (lossy by design: teams are dropped):

1. Write `_STUDENT_CONSENT_TEXT_V1_ORIGINAL`, a private copy of the milestone 9 wording, back into
   the same row.
2. Drop `team_memberships`, then `teams`, with their indexes.

**Tests** (`test_migrations.py`):

- **At head**: both tables, their indexes, and the student text equal to the rewrite, still
  version 1, published 2026-10-19.
- **An upgrade from `3e32707ed794`** with a student consent record: the text is rewritten, and the
  record's `consent_text_id` is unchanged.
- **A downgrade back to `3e32707ed794`**: the original wording is restored, byte for byte.
- **The stairway and the drift check**, on both engines.
