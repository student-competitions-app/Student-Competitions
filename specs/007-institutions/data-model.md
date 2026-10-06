# Data Model: Administrator Area — Educational Institutions (Milestone 7)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

The milestone makes one schema change: a new `institutions` table. Its shape is the same as the
`subjects` table from milestone 6
([specs/006-admin-area/data-model.md](../006-admin-area/data-model.md#1-subject--table-subjects-new)).

---

## 1. Institution — table `institutions` (new)

A university, college, school or similar body that teachers (milestone 8) and students
(milestone 9) belong to. Only administrators create or change institutions.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer, primary key | no | The identity other records refer to (FR-018). Never changes. |
| `name` | `String(200)` | no | As entered after trimming (FR-007). Shown everywhere. |
| `name_key` | `String(600)` | no | `name_key(name)` = `NFC(name).casefold()`. **Unique** (`uq_institutions_name_key`). Never shown. |
| `is_active` | boolean | no | `True` on creation (FR-012). `False` = deactivated (FR-019). |
| `created_at` | `UTCDateTime` | no | Set once. |
| `updated_at` | `UTCDateTime` | no | Set at creation. Reset by a rename or status change that actually changes something. |

**Model**: `app/models/institution.py`, `class Institution(SQLModel, table=True)`, exported from
`app/models/__init__.py` (the drift test needs that). The column lengths come from
`INSTITUTION_NAME_MAX_LENGTH` and `INSTITUTION_NAME_KEY_MAX_LENGTH` in
`app/schemas/institution.py`, which are aliases of the shared limits in `app/schemas/names.py`
(research D1).

**Indexes and constraints**:

- `pk_institutions` on `id`.
- `uq_institutions_name_key` on `name_key`. It enforces FR-009 and FR-010 on both engines and
  serves the duplicate lookup, so no extra index is needed.

### Validation rules (applied by `clean_name`, research D1)

The same rules and messages as subjects. Only the duplicate message names the entity.

| Rule | Check | Message shown in the form |
|---|---|---|
| No control characters | no character of the **submitted** value is in Unicode category `C*`, `Zl` or `Zp` | "The name cannot contain tabs, line breaks or other control characters." |
| Trim | `str.strip()` after the check above | — |
| Required | length after trimming ≥ 1 | "Enter a name." |
| Length | length after trimming ≤ 200 code points | "The name can be at most 200 characters." |
| Unique | no **other** institution has the same `name_key` (active or inactive) | "An educational institution named “{existing name}” already exists." |

The duplicate message shows the **stored** name of the existing institution. Uniqueness is checked
only among institutions: a subject with the same name does not count.

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
   └─ delete ──┴─ delete   (only when count_institution_uses = 0)
               │
               ▼
           (row removed)
```

- **create** → active.
- **deactivate**: active → inactive. On an inactive institution it changes nothing (FR-021).
- **activate**: inactive → active. On an active institution it changes nothing (FR-021).
- **rename**: allowed in either state and keeps the state and the `id` (FR-017, FR-018). Renaming
  to the same name changes nothing, so `updated_at` is unchanged. A change of case only is allowed,
  because the institution itself does not count as a duplicate (FR-015).
- **delete**: from either state, only when `count_institution_uses(institution) == 0` (FR-024).
  The row is removed permanently, and its name becomes free (FR-026).

### Relationships

None in this milestone. Later milestones add these, always by `institutions.id` (research D4):

- Milestone 8: a teacher–institution link (many to many), `→ institutions.id`. New links accept
  active institutions only. Existing links to an institution deactivated later stay.
- Milestone 9: a student's institution, `→ institutions.id` (required). New placements accept
  active institutions only. Existing placements stay.

Each of these milestones extends `count_institution_uses` (research D5).

## 2. Shared name rules — `app/schemas/names.py` (code, not data)

| Name | Value / behaviour |
|---|---|
| `NAME_MAX_LENGTH` | 200 |
| `NAME_KEY_MAX_LENGTH` | 600 (3 × 200, the most Unicode case folding can expand a string) |
| `NameRuleError` | `ValueError` with a `message` ready for the form |
| `clean_name(raw)` | Moved unchanged from `clean_subject_name` (milestone 6 research D2) |
| `name_key(name)` | Moved unchanged from `subject_name_key` (milestone 6 research D1) |

`app/schemas/subject.py` and `app/schemas/institution.py` re-export these under their own names.
The `subjects` table does not change.

## 3. Schema revision introduced by this milestone

One Alembic revision on top of `2a84d288f9e6` (create subjects):

- **Create institutions**
  - upgrade: `create_table("institutions", …)` with the columns and constraints in section 1.
    Names come from `op.f(...)` and the project naming convention.
  - downgrade: `drop_table("institutions")`.

It is written with plain SQLAlchemy constructs, as the earlier revisions are, so it stays valid
however the models change. It inserts no data: the institution list starts empty (spec
Assumptions).

## 4. Administrator tabs — unchanged

| Key | Label | Address | Page in this milestone |
|---|---|---|---|
| `teachers` | Teachers | `/admin/teachers` | Placeholder (until milestone 8) |
| `institutions` | Educational institutions | `/admin/institutions` | **The institution list (new)** |
| `subjects` | Subjects | `/admin/subjects` | The subject list |
