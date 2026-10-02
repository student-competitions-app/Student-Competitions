# Data Model: Administrator Area — Teachers, Educational Institutions, Subjects (Milestone 6)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

The milestone makes two schema changes: a new `subjects` table, and dropping the unused
`users.role` column (research D8). The administrator tabs are code, not data.

---

## 1. Subject — table `subjects` (new)

A knowledge area in which competitions are held, such as mathematics or physics. Only
administrators create or change subjects.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer, primary key | no | |
| `name` | `String(200)` | no | As entered after trimming (FR-013). Shown everywhere. |
| `name_key` | `String(600)` | no | `NFC(name).casefold()`. **Unique** (`uq_subjects_name_key`). Never shown. 600 = 3 × 200, the most Unicode case folding can expand a string. |
| `is_active` | boolean | no | `True` on creation. `False` = deactivated (FR-024). |
| `created_at` | `UTCDateTime` | no | Set once. |
| `updated_at` | `UTCDateTime` | no | Set at creation. Reset by a rename or status change that actually changes something. |

**Model**: `app/models/subject.py`, `class Subject(SQLModel, table=True)`, exported from
`app/models/__init__.py` (the drift test needs that). `SUBJECT_NAME_MAX_LENGTH = 200` and
`SUBJECT_NAME_KEY_MAX_LENGTH = 600` live in `app/schemas/subject.py` and are imported by the
model, as `app/models/question.py` does for its limits.

**Indexes and constraints**:

- `pk_subjects` on `id`.
- `uq_subjects_name_key` on `name_key`. It enforces FR-015 and FR-016 on both engines. It also
  serves the duplicate lookup, so no extra index is needed.

### Validation rules (applied by `clean_subject_name`, research D2)

| Rule | Check | Message shown in the form |
|---|---|---|
| No control characters | no character of the **submitted** value is in Unicode category `C*`, `Zl` or `Zp` | "The name cannot contain tabs, line breaks or other control characters." |
| Trim | `str.strip()` after the check above | — |
| Required | length after trimming ≥ 1 | "Enter a name." |
| Length | length after trimming ≤ 200 code points | "The name can be at most 200 characters." |
| Unique | no **other** subject has the same `name_key` (active or inactive) | "A subject named “{existing name}” already exists." |

The duplicate message shows the **stored** name of the existing subject. For example, entering
"physics" says "A subject named “Physics” already exists."

### States and transitions

```text
             create
               │
               ▼
   ┌──────── active ◄──── activate ────┐
   │           │                       │
   │       deactivate                  │
   │           ▼                       │
   │        inactive ──────────────────┘
   │           │
   └─ delete ──┴─ delete   (only when count_subject_uses = 0)
               │
               ▼
           (row removed)
```

- **create** → active.
- **deactivate**: active → inactive. On an inactive subject it changes nothing (FR-026).
- **activate**: inactive → active. On an active subject it changes nothing (FR-026).
- **rename**: allowed in either state and keeps the state (FR-023). Renaming to the same name
  changes nothing, so `updated_at` is unchanged. A change of case only is allowed, because the
  subject itself does not count as a duplicate (FR-021).
- **delete**: from either state, only when `count_subject_uses(subject) == 0` (FR-029). The row
  is removed permanently, and its name becomes free (FR-031).

### Relationships

None in this milestone. Later milestones add these (spec Dependencies):

- Milestone 9: `questions.subject_id → subjects.id` (required). New questions accept active
  subjects only.
- Milestone 10: `competitions.subject_id → subjects.id` (required). New competitions accept active
  subjects only.

Each of these milestones extends `count_subject_uses` (research D4).

## 2. User — table `users` (changed)

| Change | Detail |
|---|---|
| Column `role` dropped | Unused since milestone 5 (always `NULL` on new rows, never read). The `User.legacy_role` field is removed from the model. |

Nothing else about users changes. Rows are still written only by `reconcile_users`.

## 3. Schema revisions introduced by this milestone

Two Alembic revisions on top of `50f17535d874` (add user roles), in this order:

1. **Drop legacy user role**
   - upgrade: `batch_alter_table("users")` → `drop_column("role")`.
   - downgrade: add `role String(20) NULL` back. Milestone 5's downgrade then fills it.
2. **Create subjects**
   - upgrade: `create_table("subjects", …)` with the columns and constraints in section 1. Names
     come from `op.f(...)` and the project naming convention.
   - downgrade: `drop_table("subjects")`.

Both are written with plain SQLAlchemy constructs, as the earlier revisions are, so they stay
valid however the models change. They insert no data: the subject list starts empty (spec
Assumptions).

## 4. Administrator tabs — code, not data

| Key | Label | Address | Page in this milestone |
|---|---|---|---|
| `teachers` | Teachers | `/admin/teachers` | Placeholder |
| `institutions` | Educational institutions | `/admin/institutions` | Placeholder |
| `subjects` | Subjects | `/admin/subjects` | The subject list |

Declared once as `ADMIN_TABS` in `app/routers/admin.py` (research D6), in this order.
