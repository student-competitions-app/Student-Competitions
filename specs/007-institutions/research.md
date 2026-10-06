# Research: Administrator Area — Educational Institutions (Milestone 7)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-06

The Technical Context has no open questions. The stack, layout and access model are fixed by the
constitution and milestones 1–6. The technical requirements say the tab "works the same way as the
**Subjects** tab", so most decisions repeat milestone 6's
([specs/006-admin-area/research.md](../006-admin-area/research.md)). This file records only what
is new or different. Each decision is stated as Decision / Rationale / Alternatives considered.

---

## D1. Share the name rules between subjects and institutions

**Decision**: move the pure name rules from `app/schemas/subject.py` into a new
`app/schemas/names.py`:

```text
NAME_MAX_LENGTH = 200
NAME_KEY_MAX_LENGTH = 600
class NameRuleError(ValueError)        # .message, ready for the form
def clean_name(raw: str) -> str        # control characters → trim → empty → length
def name_key(name: str) -> str         # NFC, then casefold
```

`app/schemas/subject.py` keeps its public names as aliases of these (`SUBJECT_NAME_MAX_LENGTH`,
`SubjectNameError`, `clean_subject_name`, `subject_name_key`), so no milestone 6 code or test
changes. The new `app/schemas/institution.py` does the same with institution names.

**Rationale**:

- The spec (FR-007 to FR-009) and the technical requirements give institution names exactly the
  subject rules: 1–200 characters after trimming, no control characters, unique ignoring case.
  Two copies of the control-character and case-folding logic could drift apart. The second user
  is a present need, so the shared module passes Principle II's "at least one concrete present
  need".
- The messages ("Enter a name.", "The name can be at most 200 characters.", the control-character
  message) do not name the entity, so they can be shared as they are.
- Keeping the subject aliases means SC-008 ("milestones 1–6 tests pass unchanged") holds for the
  subject tests, and the subject service and router do not change.
- Aliases are the same objects, not subclasses. A router that catches `SubjectNameError` would also
  catch an institution name error. That is harmless, because each router calls only its own
  service.

**Alternatives considered**:

- *Copy `app/schemas/subject.py` as `institution.py`*: rejected, because the most subtle code in
  milestone 6 (Unicode categories, case folding, the order of checks) would exist twice.
- *Make institutions import from `app.schemas.subject`*: rejected, because an institution module
  would depend on a subject module for no domain reason.
- *Rename the subject functions and update every subject caller and test*: rejected, because it
  churns milestone 6 code and tests for no behaviour change.

## D2. Separate model, service, router and templates for institutions

**Decision**: institutions get their own `Institution` model, `app/services/institutions.py`,
`app/routers/admin_institutions.py` and four templates under `templates/pages/admin/`. They copy
the subject design one for one: same functions, same exceptions, same routes, same statuses (see
[contracts/](./contracts/)). Only the names and texts change.

**Rationale**:

- Milestone 6 split the area shell from the Subjects tab precisely so that "milestone 7 can add
  `admin_institutions.py` beside them without editing the subject code" (006 plan, Structure
  Decision).
- The two lists will diverge soon. Milestone 8 adds teacher links to institutions, an
  "active institutions for a form" query and its own in-use count. Milestones 10 and 11 do the same
  for subjects with questions and competitions. Separate services keep each set of rules in one
  file.
- The routers are thin. Each handler is a few lines that call the service and map its exceptions.
  A generic router factory would save little code and make every route harder to read and to find
  in the route-table tests.

**Alternatives considered**:

- *A generic "named catalog" service and router, parameterized by model and texts*: rejected for
  now. It would be an abstraction with two users whose futures differ, and it would require
  rewriting the subject code that milestone 6 just shipped. If a third list of the same shape
  appears, revisit.
- *Generic templates (`catalog_list.html`, `catalog_form.html`, …) shared by both tabs*: rejected
  for the same reason. They would replace the subject templates, whose texts the milestone 6 tests
  pin. Four small institution templates are cheaper than a shared template full of variables.

## D3. Table `institutions` with a unique `name_key`, the same as `subjects`

**Decision**: a new table `institutions` with `id`, `name` (`String(200)`), `name_key`
(`String(600)`, unique as `uq_institutions_name_key`), `is_active`, `created_at`, `updated_at`.
`name_key` is `name_key(name)` from D1. One Alembic revision, `create_institutions`, on top of
`2a84d288f9e6` (create subjects).

**Rationale**: the same reasons as milestone 6 research D1. Unicode-correct uniqueness that ignores
case ("Київський університет" = "КИЇВСЬКИЙ УНІВЕРСИТЕТ", FR-009), identical on SQLite and
PostgreSQL, and enforced by a constraint when two administrators submit at once (FR-010).

Institutions and subjects are separate tables with separate constraints, so an institution and a
subject may share a name (spec edge case "Same name as a subject").

**Alternatives considered**: *one shared `catalog_items` table with a `kind` column*: rejected,
because later milestones need real foreign keys to each list (`teacher_institutions.institution_id`,
`questions.subject_id`), and a shared table would let a question point at an institution.

## D4. Identity, not name, is what other records will refer to

**Decision**: other records refer to an institution only by `institutions.id`. In this milestone
nothing refers to institutions yet. The rule is recorded in the model docstring and in
[data-model.md](./data-model.md#relationships) for milestones 8 and 9, and the service tests check
that a rename keeps the same `id` (SC-007).

**Rationale**: FR-018 and the technical requirements ("Everything that refers to an institution
refers to it by id, so renaming never breaks a link"). Milestone 8's invitation token also carries
institution ids, not names.

**Alternatives considered**: none. A name-based reference would break on every rename.

## D5. The in-use check: `count_institution_uses`, returning 0 for now

**Decision**: `count_institution_uses(session, institution_id) -> int` in
`app/services/institutions.py`. In this milestone it returns `0`. Its docstring names milestone 8
(teacher links) and milestone 9 (student details) as the places that must add their counts.
`delete_institution` raises `InstitutionInUse` when the count is above zero. An `IntegrityError` on
the delete itself (a future foreign key) is also turned into `InstitutionInUse`.

Tests prove the refusal path by monkeypatching `count_institution_uses` to return `1`. This is the
"stand-in record" in the spec's Assumptions and SC-004.

**Rationale**: the same as milestone 6 research D4. FR-025 asks for one place that decides.

**Note for milestones 8 and 9**: SQLite does not enforce foreign keys in this application. On
SQLite the service check is the only guard, so those milestones **must** extend
`count_institution_uses`, not rely on a foreign key alone.

**Alternatives considered**: the same as milestone 6 research D4 (a registry of checks, a test-only
table, soft delete), rejected for the same reasons.

## D6. The inactive status is stored and shown, but restricts nothing yet

**Decision**: this milestone adds no "active institutions only" query. Milestone 8 adds one when it
builds the first form that offers institutions (FR-022).

**Rationale**: nothing in this milestone offers institutions for a link, so such a query would have
no caller (YAGNI). The status column and the list display are enough for milestone 8 to build on.

**Alternatives considered**: *add `list_active_institutions` now*: rejected, because it would be
untested by any real use and milestone 8 may need a different shape (for example, active ones plus
those already linked to the teacher being edited).

## D7. The Institutions tab moves out of `admin.py`

**Decision**: remove the `GET /admin/institutions` placeholder handler from `app/routers/admin.py`
and serve the address from the new `app/routers/admin_institutions.py` (prefix
`/admin/institutions`). `ADMIN_TABS`, the tab order, the `/admin` redirect and the Teachers
placeholder stay as they are (FR-006). The module docstring of `admin.py` is updated to say only
Teachers is a placeholder, until milestone 8.

**Rationale**: the same split as the Subjects tab. Two handlers for one address would make the
route that wins depend on router order.

**Alternatives considered**: none worth recording.

## D8. Texts

**Decision**: the institution pages use these texts. They mirror the subject texts, with
"educational institution" as the noun.

| Place | Text |
|---|---|
| Tab list heading | "Educational institutions" |
| Empty list | "No educational institutions yet" (FR-003) |
| Create form heading | "New educational institution" |
| Rename form heading | "Rename educational institution" |
| Duplicate name | "An educational institution named “{existing name}” already exists." |
| Delete confirmation | heading "Delete “{name}”?", text "Deleting an educational institution cannot be undone." |
| Delete refused (in use) | "“{name}” is in use and cannot be deleted. You can deactivate it instead." |
| Not found | heading "Educational institution not found", text "This educational institution does not exist. It may have been deleted." |
| Back link | "Back to the educational institutions" |

**Rationale**: the spec and technical requirements fix "No educational institutions yet" and the
gist of the in-use message. The rest follows the subject pages, so both tabs read alike.

## D9. CSS: reuse the subject list styles

**Decision**: the institution list uses the same table layout as the subject list. The existing
selectors in `static/css/app.css` (`.subjects-table`, `.subjects-actions`, `.subjects-empty`) are
extended to also match `.institutions-table`, `.institutions-actions` and `.institutions-empty`, by
adding them to the same rules.

**Rationale**: no new styling is needed, and the subject templates and tests stay unchanged.

**Alternatives considered**: *rename the classes to a neutral `.catalog-*` and update both
templates*: rejected, because it changes milestone 6 templates for no visible difference.

## D10. Existing tests that change

**Decision**: the following milestone 6 tests change, because the Institutions tab stops being a
placeholder and the write surface grows. Everything else passes unchanged (SC-008).

| Test | Change |
|---|---|
| `test_admin_area.py` | Remove `/admin/institutions` from `PLACEHOLDERS`. Add a check that every institution page (list, new, rename, delete, not found) marks the **Educational institutions** tab as current. |
| `test_routes.py::test_the_write_routes_are_exactly_…` | Add the five `POST /admin/institutions…` routes. |
| `test_access_control.py` | Add the institution pages and actions to the role × route matrix, with an institution fixture and "rows unchanged" assertions. |
| `test_cross_site.py` | Add a cross-site institution action that changes nothing. |
| `test_migrations.py` | Add `institutions` to `APPLICATION_TABLES`. |

**Rationale**: the spec allows exactly this in SC-008: tests of the old placeholder page change.
The route and access sweeps must list the new routes to stay exact.
