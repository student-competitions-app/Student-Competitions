# Research: Administrator Area — Regions and Educational Institutions (Milestone 7)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-10

The Technical Context has no open questions. The stack, layout and access model are fixed by the
constitution and milestones 1–6, and milestone 6's Subjects tab already settled most patterns:
name rules, case-insensitive keys, Python sorting, Post/Redirect/Get and the in-use hook
(specs/006-admin-area/research.md D1–D5). This file records only what milestone 7 adds or
changes. Each decision is stated as Decision / Rationale / Alternatives considered.

---

## D1. One set of name rules, shared by subjects, regions and institutions

**Decision**: move the body of `app/schemas/subject.py` into a new `app/schemas/names.py`:

- `NAME_MAX_LENGTH = 200`, `NAME_KEY_MAX_LENGTH = 600`;
- `class InvalidName(ValueError)` with `.message`;
- `clean_name(raw) -> str` and `name_key(name) -> str`.

The rules, their order and the messages are unchanged (milestone 6 research D1–D2).
`app/schemas/subject.py` keeps its public names as aliases of the shared ones
(`SubjectNameError = InvalidName`, `clean_subject_name = clean_name`, and so on). The subject
model, service, router and tests therefore do not change. Regions and institutions import from
`app/schemas/names.py` directly.

**Rationale**: the spec says region and institution names follow exactly the subject rules
(FR-016, FR-017, and technical requirements "validated as for regions"). With three users, one
function is the simplest way to keep the rules from drifting (Principle II: an abstraction with a
present need). The aliases keep FR-049 ("Subjects tab unchanged") literally true: no subject
behaviour, message or import changes.

**Alternatives considered**:

- *Import `clean_subject_name` from `app/schemas/subject.py` for regions*: rejected, because a
  region rule that lives in the subject module is misleading, and the error class name
  (`SubjectNameError`) would show up in region code.
- *Copy the module per entity*: rejected, because three copies of the same rules drift.
- *Rename the subject functions everywhere*: rejected for this milestone, because it touches
  milestone 6 code and tests for no behaviour gain.

## D2. Region uniqueness: a unique `name_key`, as for subjects

**Decision**: `regions.name_key` = `name_key(name)`, with a unique constraint
`uq_regions_name_key`. The service checks first, for a friendly error. The constraint is the
guarantee under concurrency, and an `IntegrityError` on commit becomes the same duplicate error
(FR-018, FR-020).

**Rationale and alternatives**: as in milestone 6 research D1. This gives Unicode-correct case
folding that behaves the same on SQLite and PostgreSQL ("Київ" = "КИЇВ").

## D3. Institution uniqueness: a composite unique constraint `(region_id, name_key)`

**Decision**: `institutions` has `UNIQUE (region_id, name_key)`, named explicitly
`uq_institutions_region_id_name_key`. The duplicate pre-check looks only inside the region. An
`IntegrityError` on commit becomes `DuplicateInstitutionName` (FR-019, FR-020).

The name is given explicitly because the project's naming convention for unique constraints
(`uq_%(table_name)s_%(column_0_name)s`) uses only the first column. That would produce the
misleading name `uq_institutions_region_id`. An explicit name is used as it is, on both engines,
and is what autogenerate and the drift test compare.

The constraint's leading column is `region_id`, so the same index also serves the per-region list
query and the "does this region hold institutions" count. No separate index on `region_id` is
needed.

**Rationale**: "unique within a region, ignoring case" is exactly a two-column key. It needs no
engine-specific SQL.

**Alternatives considered**:

- *A single `name_key` that includes the region id (for example `"5:kyiv polytechnic"`)*:
  rejected, because it hides the rule inside a string and must be recomputed if a region could
  ever change. It cannot, but the composite constraint says what it means.
- *Changing the global naming convention to `column_0N_name`*: rejected, because it is a global
  change for one constraint. It would keep the existing single-column names, but it would need
  its own review.

## D4. Institutions refer to regions by a foreign key, and the service is the real guard

**Decision**: `institutions.region_id` is `NOT NULL` with a foreign key to `regions.id`
(`fk_institutions_region_id_regions`, the default `NO ACTION`, so no cascade). The service also
enforces every rule itself:

- `delete_region` counts the region's institutions (active and deactivated) and refuses with
  `RegionNotEmpty` if there are any (FR-036). An `IntegrityError` raised by the delete (the
  PostgreSQL foreign key, in a race) also becomes `RegionNotEmpty`.
- `create_institution` loads the region with `SELECT … FOR UPDATE` (see D5). It refuses with
  `RegionNotFound` or `RegionInactive` (FR-024).

**Rationale**:

- SQLite does not enforce foreign keys in this application: there is no `PRAGMA foreign_keys=ON`
  (milestone 6 research D4). On SQLite the service check is the only guard, so it must exist.
- On PostgreSQL the foreign key is a real backstop. A region delete racing an institution insert
  can never leave an institution pointing at nothing (FR-038).
- No `ON DELETE CASCADE`: deleting a region must never take institutions with it.

**Alternatives considered**:

- *Turn on `PRAGMA foreign_keys=ON` for SQLite*: rejected for this milestone. It changes how
  every existing SQLite batch migration behaves. For example, the milestone 6 `users` batch
  recreate would run with enforced references from `user_roles` and `sessions`. That deserves its
  own change, not one smuggled into a feature (Principle I).
- *`ON DELETE CASCADE`*: rejected, because the spec forbids deleting a region that holds
  institutions.

## D5. Creating an institution locks its region row

**Decision**: `create_institution` reads the region with
`session.get(Region, region_id, with_for_update=True)`. It then checks that the region is
active, checks for a duplicate, inserts and commits.

**Rationale**: SC-007 says no institution can be created in a deactivated region. Without a lock,
PostgreSQL under READ COMMITTED allows this order: the create reads "active", a deactivation
commits, then the insert commits. With `FOR UPDATE`, the create waits for any concurrent
deactivation, rename or deletion of the region to commit, and then reads the region's new
state. A concurrent `delete_region` either waits for the insert (and then finds an institution
and refuses), or deletes first (and the create then finds no region).

`with_for_update` is portable SQLAlchemy. On SQLite it renders nothing, and SQLite already
serialises writers. The lock lasts only for one short transaction.

**Alternatives considered**: *rely on the check alone*: rejected, because the race is narrow but
real, and the success criterion is absolute. *A `CHECK` or trigger*: rejected, because it is
engine-specific.

## D6. Sorting in Python by `(name_key, id)` for both lists

**Decision**: `list_regions` and `list_institutions(region_id)` sort in Python with
`key=(name_key, id)`, as subjects do.

**Rationale and alternatives**: milestone 6 research D3. This gives the same order on both
engines. The lists are short (spec Assumptions: tens of items).

## D7. The selected region is part of the path

**Decision**: the tab with no region selected is `/admin/institutions`. With a region selected,
the address is `/admin/institutions/regions/{region_id}`. Clicking a region in the left list is
an ordinary link to that address. Every region and institution page or action lives under that
address, so the region is always in the path:

- `/admin/institutions/regions/{region_id}/rename`
- `/admin/institutions/regions/{region_id}/institutions/new`
- `/admin/institutions/regions/{region_id}/institutions/{institution_id}/rename`
- and so on.

The complete table is in [contracts/http-routes.md](./contracts/http-routes.md).

**Rationale**:

- FR-003 asks for selection that survives reloads, bookmarks, direct links and the back button.
  A path does all of that with no script (Principle II), and selection stays navigation, not a
  change (FR-040).
- The integer converter (`{region_id:int}`) makes a non-integer id the application's ordinary
  404. An unknown integer id gets the friendly "Region not found" page inside the area (FR-043).
  A query parameter (`?region=abc`) would need its own parsing to avoid FastAPI's JSON `422`.
- Milestone 4's sign-in redirect already carries the full path in `next` (and the query, see
  `app/core/auth.py::_return_target`), so FR-046 holds with nothing added.
- Nesting institution routes under their region gives every institution page its "back" target
  and its redirect target without another lookup. It also makes the "wrong region" case
  explicit: the service compares `institution.region_id` with the region in the path and answers
  "not found" on a mismatch (spec edge case). An institution can never be moved this way
  (FR-030).

**Alternatives considered**:

- *`/admin/institutions?region=5`*: workable, but needs manual integer parsing, and mixes a query
  parameter into an otherwise path-based admin area.
- *Flat institution routes (`/admin/institutions/items/{id}/rename`)*: rejected, because every
  redirect would need an extra lookup to find the region, and a region selection would be lost if
  the institution was deleted meanwhile.
- *HTMX swap of the right-hand list*: rejected, because it adds partials and still needs the URL
  updated for FR-003. Plain links already meet every requirement.

## D8. Redirect targets after each action (Post/Redirect/Get)

**Decision**:

| Action | Success redirect (`303`) |
|---|---|
| Create region | `/admin/institutions/regions/{new id}` (the new region selected, FR-022) |
| Rename, deactivate or activate a region | `/admin/institutions/regions/{id}` |
| Delete a region | `/admin/institutions` (no region selected, FR-039) |
| Any institution action, including delete | `/admin/institutions/regions/{region_id}` |

Errors re-render instead of redirecting:

- `400`: an invalid or duplicate name (the form again, with the entered value);
- `409`: a refused state change (a region that holds institutions, an institution in use, or
  creating in a deactivated region);
- `404`: the "Region not found" or "Educational institution not found" page.

**Rationale**: these are the spec's Assumptions ("after an action, the relevant region stays
selected"). The status codes are the ones milestone 6 already uses (milestone 6 research D5).

## D9. The in-use check for institutions: one function that returns 0 for now

**Decision**: `count_institution_uses(session, institution_id) -> int` in
`app/services/institutions.py` returns `0` in this milestone. Its docstring names milestone 8
(teacher links) and milestone 9 (students) as the places that add their counts. `delete_institution`
calls it and raises `InstitutionInUse` if the count is above zero. An `IntegrityError` from the
delete itself (a future foreign key) is also turned into `InstitutionInUse`. Tests prove the
refusal by monkeypatching the function to return `1` (the spec's "stand-in record").

**Rationale and alternatives**: the same reasoning as `count_subject_uses` (milestone 6 research
D4), FR-037 and FR-038. A region's emptiness, by contrast, is a real query today
(`count_region_institutions`), because institutions exist now.

## D10. A region and its institutions have independent statuses

**Decision**: `set_region_active` changes only `regions.is_active`. It never touches
`institutions.is_active` (FR-033). Whether an institution is *available for selection* (active
and in an active region, FR-034) is not stored and has no function yet. Milestone 8 adds the
first query that needs it (the teacher institution picker), and it will combine both flags in
that query.

**Rationale**:

- Cascading the status would lose each institution's own status, which the spec forbids
  ("exactly as they were").
- A derived `is_available` column would have to be updated on every region change.
- A helper with no caller would be a speculative abstraction (Principle II). The rule is
  recorded in [data-model.md](./data-model.md) so milestone 8 implements it as written.

**Alternatives considered**: *an `available_institutions()` service function now*: rejected
(YAGNI). Nothing in this milestone picks institutions.

## D11. Region selection is marked with `aria-current="true"`

**Decision**: the selected region's link carries `aria-current="true"` and a CSS highlight
(FR-002). The tab row keeps `aria-current="page"` on the current tab.

**Rationale**: `aria-current="page"` already marks the current tab, and the milestone 6 tests
assert it appears exactly once per page. `aria-current="true"` is the WAI-ARIA value for "the
current item in a set" (here, the set of regions). It keeps the two meanings apart for assistive
technologies and for the tests.

## D12. Layout: a two-column grid that stacks on narrow screens

**Decision**: the tab content is a `<div class="institutions-layout">` with two `<section>`s:
regions, then institutions. Custom CSS in `app/static/css/app.css` places them in two columns
(`grid-template-columns: minmax(14rem, 1fr) 2fr`) from 768 px wide. Below that, it uses one column
with regions first (FR-006). The left list is a `<ul>`. The right list is a table like the
subjects table.

**Rationale**: Pico.css's own `.grid` gives equal columns, which wastes space on the short region
names. A few lines of override CSS are allowed (constitution, Styling). There is no script.

## D13. Deleting the Educational institutions placeholder

**Decision**: the `admin_institutions` placeholder handler is removed from `app/routers/admin.py`.
`GET /admin/institutions` is served by the new `app/routers/admin_institutions.py`. `ADMIN_TABS`
is unchanged. `pages/admin/placeholder.html` stays, because the Teachers tab still uses it.

**Rationale**: milestone 6 research D6 planned for this. A tab gets its features by replacing one
handler, and the shell does not change.

## D14. One migration revision for both tables

**Decision**: one Alembic revision, `create_regions_and_institutions`, on top of `2a84d288f9e6`
(create subjects). The upgrade creates `regions`, then `institutions`. The downgrade drops them
in reverse order. No data is inserted.

**Rationale**: the two tables are one feature, and neither is useful alone (spec US1/US2 share P1).
The stairway test still checks that the revision is reversible. Plain SQLAlchemy constructs are
used, as in earlier revisions.

**Alternatives considered**: *two revisions*: allowed, but it adds a revision whose intermediate
state (regions without institutions) is never deployed.
