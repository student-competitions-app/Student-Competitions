# Research: Administrator Area — Teachers, Educational Institutions, Subjects (Milestone 6)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-02

The Technical Context has no open questions: the stack, layout and access model are fixed by the
constitution and milestones 1–5. This file records the design decisions the spec leaves to the
plan. Each one is stated as Decision / Rationale / Alternatives considered.

---

## D1. Case-insensitive uniqueness: a stored `name_key` column with a unique constraint

**Decision**: store a second column, `subjects.name_key`, computed in Python as
`unicodedata.normalize("NFC", name).casefold()`. The column has a unique constraint
(`uq_subjects_name_key`). The service checks for a duplicate before writing, to produce a
friendly error. The constraint is the real guarantee: an `IntegrityError` on commit is turned
into the same "name already exists" error (FR-016, edge case "two administrators at the same
moment").

**Rationale**:

- FR-015 and the spec's edge case require "Фізика" = "ФІЗИКА". SQLite's `lower()` and `NOCASE`
  collation fold only ASCII letters. PostgreSQL's `lower()` depends on the database collation
  and provider: under the `C` locale, it also folds only ASCII. A database-side
  `UNIQUE (lower(name))` would therefore behave differently on the two engines (Principle VII).
- Python's `str.casefold()` is the full Unicode case folding, identical on every platform and
  engine. It is stronger than `lower()` (for example, it folds "ß" and "SS" together).
- NFC normalisation first means a name typed with a precomposed "é" and one with "e" plus a
  combining accent count as the same name. The stored `name` itself is kept as entered.
- A plain unique constraint on an ordinary column is portable and needs no engine-specific SQL.
  Autogenerate and the drift test understand it.

**Alternatives considered**:

- *Functional unique index on `lower(name)`*: rejected, because ASCII-only on SQLite and
  locale-dependent on PostgreSQL.
- *PostgreSQL `citext` or an ICU nondeterministic collation*: rejected, because engine-specific
  and not available on SQLite.
- *Check in the service only, no constraint*: rejected, because two simultaneous submissions
  could both pass the check.

## D2. Name rules: control characters are checked before trimming

**Decision**: one pure function, `clean_subject_name(raw: str) -> str` in
`app/schemas/subject.py`, applied in this order:

1. Refuse if **any** character of the submitted value is in Unicode category `C*` (control,
   format, surrogate, private use, unassigned) or is a line or paragraph separator (`Zl`, `Zp`).
   This is checked on the raw value, so a leading tab or a trailing line break is refused rather
   than silently trimmed away.
2. Trim whitespace at both ends (`str.strip()`). Inner spaces are kept exactly.
3. Refuse if empty ("Enter a name.").
4. Refuse if longer than 200 characters, counted in Unicode code points.

Each refusal raises `SubjectNameError` with a message written for the form (see
[contracts/subject-service.md](./contracts/subject-service.md)). The service functions call it
themselves, so no caller can store a name that skipped validation.

**Rationale**: the spec's edge case says a name *containing* a tab or line break is refused. If
trimming came first, `"\tMath"` would be quietly accepted as `"Math"`. A single-line `<input>`
never submits a line break, so checking first costs nothing for real users. Category `C*`
also covers invisible format characters (such as bidirectional overrides) that could make two
names look the same.

**Alternatives considered**:

- *Pydantic `StringConstraints(strip_whitespace=True, ...)`, as in `app/schemas/question.py`*:
  rejected for this field. Its error messages are generic ("String should have at least 1
  character"). It also trims before any custom check runs, which would accept `"\tMath"`.
- *`str.isprintable()`*: rejected, because it also refuses non-breaking spaces and every
  separator except U+0020, which is broader than "control characters".

## D3. Sorting is done in Python, by `name_key`, then `id`

**Decision**: `list_subjects` loads every subject and sorts with
`key=lambda s: (s.name_key, s.id)`.

**Rationale**: `ORDER BY` on text follows the database collation, which differs between SQLite
(binary) and PostgreSQL (the database's locale). Sorting in Python gives the same order on both
engines and in the tests. The list holds tens of subjects (spec Assumptions), so loading all rows
is free. Code-point order of the case-folded key satisfies "alphabetical, ignoring case" for
names in one script, and the spec says language-specific ordering rules are not required.

**Alternatives considered**: `ORDER BY name_key COLLATE "C"`: rejected, because the collation
name differs between the engines. `ORDER BY lower(name)`: rejected, because of the ASCII-only
folding on SQLite.

## D4. The in-use check is one function that returns 0 for now

**Decision**: `count_subject_uses(session, subject_id) -> int` in `app/services/subjects.py`. In
this milestone it returns `0`, with a docstring naming milestones 9 (questions) and 10
(competitions) as the places that must add their counts. `delete_subject` calls it and raises
`SubjectInUse` when the count is above zero. As a backstop, an `IntegrityError` raised by the
delete itself (a future foreign key) is also turned into `SubjectInUse`.

Tests prove the refusal path by monkeypatching `count_subject_uses` to return `1`. This is the
"stand-in record" in the spec's Assumptions.

**Rationale**: FR-029 and FR-030 ask for one place that decides. A single function is the
simplest form of that. Nothing refers to subjects yet, so a list of registered checks would be an
abstraction with no present use (Principle II, YAGNI).

**Note for milestones 9 and 10**: SQLite does not enforce foreign keys in this application (no
`PRAGMA foreign_keys=ON`). On SQLite the service check is the only guard, so these milestones
**must** extend `count_subject_uses`, not rely on a foreign key alone.

**Alternatives considered**:

- *A registry of usage checks*: rejected for now (YAGNI). Later milestones can introduce it if
  more than two kinds of record refer to subjects.
- *A temporary test-only table with a foreign key to `subjects`*: rejected, because it adds
  schema only for tests.
- *Soft delete*: rejected, because the spec asks for permanent deletion of unused subjects
  (FR-031) and deactivation already covers "retire".

## D5. Routes: plain links and forms, Post/Redirect/Get, no HTMX

**Decision**: every tab is a `GET` page, and every change is an HTML `<form method="post">` to a
path ending in a verb (`/rename`, `/deactivate`, `/activate`, `/delete`). Success answers
`303 See Other` to `/admin/subjects`. A validation or duplicate error re-renders the form with
`400`. A refused deletion re-renders the confirmation page with `409`. A missing subject renders
a "Subject not found" page inside the administrator area with `404`. The full table is in
[contracts/http-routes.md](./contracts/http-routes.md).

**Rationale**:

- FR-003 requires tabs to be ordinary links with no client-side switching.
- FR-032 says only form submissions may change data.
- FR-033 requires that a reload never repeats an action, which is Post/Redirect/Get.
- HTML forms can only send `GET` and `POST`, so the action goes in the path. This is the same
  style as milestone 4's `/login/code` and milestone 5's `/role`.
- HTMX would add nothing the spec asks for. Principle II allows it only "as needed".
- The status codes follow `POST /role` (400 for bad input). A 409 marks a valid request refused
  because of the current state.

**Alternatives considered**:

- *One `POST /admin/subjects/{id}` with an `action` field*: rejected, because separate paths are
  easier to test and to sweep in `test_routes.py`.
- *HTMX inline rename*: rejected, because it is not required and adds partials and tests.

## D6. Tab structure: declarations in one module, a shared admin layout

**Decision**:

- `app/routers/admin.py` declares the tabs once:
  `ADMIN_TABS = (AdminTab("teachers", "Teachers", "/admin/teachers"), …)`, in the order Teachers,
  Educational institutions, Subjects. This mirrors `AREAS` in `app/routers/areas.py`.
- The same module serves `GET /admin` (a 303 to `/admin/teachers`) and the two placeholder tabs.
- The subject pages and forms live in `app/routers/admin_subjects.py`.
- Every administrator page extends a new `templates/layouts/admin.html`. That layout extends
  `layouts/base.html` and renders the tab row from `ADMIN_TABS`. Each handler passes
  `active_tab`. The tab whose key matches is rendered with `aria-current="page"` and a visual
  highlight (FR-004).
- `ADMIN_AREA` stays in `AREAS`, so the home page link is unchanged (FR-008). Its placeholder
  handler is removed from `areas.py`, and `GET /admin` is now the redirect in `admin.py`,
  declared with `ADMIN_AREA.roles`.

**Rationale**:

- Only templates that extend `layouts/admin.html` can show the tabs, so FR-006 holds by
  construction.
- One declaration feeds both the routes and the tab row, so the two cannot drift apart. This is
  the same reasoning as milestone 5's `AREAS`.
- Milestone 7 adds its features to the Teachers and Institutions tabs by replacing two handlers.
  The shell does not change.

**Alternatives considered**: *one template with `{% if %}` per tab*: rejected, because it grows
with every milestone. *Tabs in `base.html` behind a flag*: rejected, because that risks showing
them outside the area.

## D7. Redirect `/admin` with 303

**Decision**: `GET /admin` answers `303 See Other`, `Location: /admin/teachers`.

**Rationale**: this matches every other redirect in the application. It is not permanent (301 or
308): milestone 7 may change the default tab, and browsers cache permanent redirects.

## D8. Drop the legacy `users.role` column in this milestone's first migration

**Decision**: the milestone has two Alembic revisions:

1. `drop_legacy_user_role`: drops `users.role` (with `batch_alter_table` for SQLite). The
   downgrade adds it back as a nullable `String(20)`, and milestone 5's downgrade fills it.
2. `create_subjects`: creates the `subjects` table.

`User.legacy_role` is removed from the model. Tests that wrote the column at head are updated
(see the plan's test changes).

**Rationale**: milestone 5 used "expand now, contract later". Its migration, its research D2 and
the `User` model docstring commit milestone 6's first migration to dropping the column. Leaving it
would keep a dead column and break the documented promise. Two revisions keep each change
separately reversible in the stairway test.

**Alternatives considered**: *one revision doing both*: workable, but it mixes an unrelated
contraction with the new feature table. *Postpone again*: rejected, because no real users exist
(product requirements), so there is no overlap risk worth keeping it for.

## D9. Existing access tests change where `/admin` stops being a page

**Decision**:

- `test_routes.py::test_every_declared_page_admits_exactly_its_roles` currently expects `200` for
  allowed roles. It changes to "allowed roles are **not** denied (status ≠ 403), and every other
  role gets 403". This is needed because `/admin` now answers 303, and
  `/admin/subjects/1/rename` answers 404 when subject 1 does not exist. Both are correct
  behaviour for an allowed role.
- `test_routes.py::test_the_write_routes_are_exactly_…` lists the six new `POST` routes.
- `test_access_control.py` replaces `/admin` in its access table with `/admin/teachers`, and adds a
  check that `/admin` redirects. The home page links keep `/admin`.

**Rationale**: the sweeps must stay meaningful. Accepting any non-403 status for allowed roles
still proves access is granted. Denial is still exact. A separate, explicit test checks each
page's real status (FR-040).

## D10. No success message after an action

**Decision**: after a successful action, the administrator lands on the Subjects list, where the
result is visible (the new name, the status, the missing row). No one-time "Subject created"
message is shown.

**Rationale**: the spec does not ask for one. A one-time message across a redirect needs either
session storage (a new column or table) or a query parameter that would show again on reload.
Neither is justified yet (YAGNI).
