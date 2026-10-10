# Data Model: Administrator Area — Regions and Educational Institutions (Milestone 7)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

The milestone adds two tables, `regions` and `institutions`, in one Alembic revision (research
D14). It also moves the name rules into one shared module, with no change to any rule (research
D1).

---

## 1. Region — table `regions` (new)

A geographic grouping of educational institutions, created by administrators. There is no preset
list.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer, primary key | no | |
| `name` | `String(200)` | no | As entered after trimming (FR-016). Shown everywhere. |
| `name_key` | `String(600)` | no | `name_key(name)` = `NFC(name).casefold()`. **Unique** (`uq_regions_name_key`). Never shown. |
| `is_active` | boolean | no | `True` on creation. `False` = deactivated (FR-031). |
| `created_at` | `UTCDateTime` | no | Set once. |
| `updated_at` | `UTCDateTime` | no | Set at creation. Reset by a rename or status change that actually changes something. |

**Model**: `app/models/region.py`, `class Region(SQLModel, table=True)`, exported from
`app/models/__init__.py`.

**Constraints**: `pk_regions` on `id`; `uq_regions_name_key` on `name_key` (FR-018, FR-020).

## 2. Educational institution — table `institutions` (new)

A school, college or university. Teachers (milestone 8) and students (milestone 9) are linked to
it. It belongs to exactly one region, for its whole life.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer, primary key | no | |
| `region_id` | integer, foreign key → `regions.id` | no | Set at creation and **never changed** (FR-030). No service function writes it after the insert. `fk_institutions_region_id_regions`, no cascade (research D4). |
| `name` | `String(200)` | no | As entered after trimming. |
| `name_key` | `String(600)` | no | `name_key(name)`. Never shown. |
| `is_active` | boolean | no | `True` on creation. Independent of the region's status (FR-033). |
| `created_at` | `UTCDateTime` | no | Set once. |
| `updated_at` | `UTCDateTime` | no | As for regions. |

**Model**: `app/models/institution.py`, `class Institution(SQLModel, table=True)`, exported from
`app/models/__init__.py`. There is no ORM `Relationship`: the services query by `region_id`
(Principle II).

**Constraints**:

- `pk_institutions` on `id`.
- `uq_institutions_region_id_name_key` on `(region_id, name_key)`. The name is given explicitly
  (research D3). It enforces FR-019 and FR-020, and its leading `region_id` column also serves the
  per-region list and count queries.
- `fk_institutions_region_id_regions` on `region_id` → `regions.id`.

## 3. Name rules — shared by subjects, regions and institutions

Applied by `clean_name` in `app/schemas/names.py` (research D1). They are the rules from
milestone 6, unchanged:

| Rule | Check | Message shown in the form |
|---|---|---|
| No control characters | no character of the **submitted** value is in Unicode category `C*`, `Zl` or `Zp` | "The name cannot contain tabs, line breaks or other control characters." |
| Trim | `str.strip()`, after the check above. Inner spaces are kept. | — |
| Required | length after trimming ≥ 1 | "Enter a name." |
| Length | length after trimming ≤ 200 code points | "The name can be at most 200 characters." |

Uniqueness (checked by the services, guaranteed by the constraints):

| Entity | Scope | Message (shows the **stored** name of the existing item) |
|---|---|---|
| Region | every other region, active or deactivated | "A region named “{existing name}” already exists." |
| Institution | every other institution **of the same region**, active or deactivated | "An educational institution named “{existing name}” already exists in this region." |

The messages tell the two scopes apart (FR-021).

## 4. States and transitions

Regions and institutions have the same life cycle. Only the delete guard and the create
precondition differ.

```text
             create
               │
               ▼
   ┌──────── active ◄──── activate ────┐
   │           │                       │
   │       deactivate                  │
   │           ▼                       │
   │      deactivated ─────────────────┘
   │           │
   └─ delete ──┴─ delete   (region: holds no institution; institution: count_institution_uses = 0)
               │
               ▼
           (row removed)
```

| Transition | Region | Institution |
|---|---|---|
| **create** | → active. | → active. **Only** if its region exists and is active (FR-024), checked with the region row locked (research D5). |
| **rename** | Either state, keeps the state (FR-029). An unchanged name writes nothing. A change of case only is allowed (FR-027). | The same. Never changes `region_id` (FR-030). Allowed whatever the region's status (FR-015, US4-9). |
| **deactivate / activate** | Sets `is_active`. Repeating it changes nothing (FR-032). Never changes the institutions' `is_active` (FR-033). | Sets `is_active`. Repeating it changes nothing. Allowed whatever the region's status. |
| **delete** | Only when `count_region_institutions = 0`, counting active and deactivated institutions (FR-036). | Only when `count_institution_uses = 0` (FR-037). Allowed whatever the region's status. |

## 5. Derived rule: availability for selection (used from milestone 8)

An institution is **available for selection** when `institutions.is_active` **and**
`regions.is_active` are both true (FR-034). It is not stored. In this milestone nothing reads
it: the only restriction today is FR-024, refusing to create an institution in a deactivated
region. Milestone 8's institution picker and its server-side check must compute exactly this
rule (research D10). Existing links to an institution that later becomes unavailable stay valid.

## 6. Relationships

```text
regions 1 ──── 0..* institutions
   (delete refused while any exist)
```

Milestones that add references to `institutions` (spec Dependencies):

- Milestone 8: teacher ↔ institution links. These are uses.
- Milestone 9: student → institution. These are uses.

Each of these milestones must extend `count_institution_uses` (research D9). Do not rely on the
foreign key alone, because SQLite does not enforce foreign keys in this application.

## 7. Schema revision introduced by this milestone

One Alembic revision on top of `2a84d288f9e6` (create subjects):

- **upgrade**: `create_table("regions", …)`, then `create_table("institutions", …)`, with the
  columns and constraints in sections 1 and 2.
- **downgrade**: `drop_table("institutions")`, then `drop_table("regions")`.

Plain SQLAlchemy types, as in earlier revisions. No data is inserted: both lists start empty
(spec Assumptions).
