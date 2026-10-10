# Contract: HTTP Routes — Educational Institutions Tab (Milestone 7)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D7, D8, D11, D12

All routes below are served by `app/routers/admin_institutions.py`, with the prefix
`/admin/institutions`. Every page uses the admin layout from milestone 6 with the **Educational
institutions** tab current (FR-005).

## Access (all routes below)

Every route is declared `@allow_roles(Role.ADMIN)` and goes through milestone 5's
`resolve_access`. No route is added to `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES` (FR-044–FR-047).

| Who | `GET` | `POST` |
|---|---|---|
| Anonymous | `303` → `/login?next=<path>`. The path includes the selected region (FR-046). | `303` → `/login` |
| Signed in, no current role yet | `303` → `/role?next=<path>` | `303` → `/role` |
| Current role teacher or student (including an administrator using another role) | `403` "Access denied" | `403` "Access denied"; nothing changes (FR-045) |
| Current role administrator | as described below | as described below |
| Any `POST` from another site | — | `403` "Request refused", before any database access (FR-042) |

Ids are declared `{region_id:int}` and `{institution_id:int}`. A non-integer id matches no route
and gets the application's ordinary friendly `404` (milestone 6 contract, same reason).

Below, `R` is `/admin/institutions/regions/{region_id}` and `I` is
`R/institutions/{institution_id}`.

## Route table

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/admin/institutions` | The tab, no region selected | `200` |
| GET | `/admin/institutions/regions/new` | Create-region form | `200` |
| POST | `/admin/institutions/regions` | Create a region | `303` → `/admin/institutions/regions/{new id}` |
| GET | `R` | The tab with the region selected | `200` |
| GET | `R/rename` | Rename-region form | `200` |
| POST | `R/rename` | Rename the region | `303` → `R` |
| POST | `R/deactivate` | Deactivate the region | `303` → `R` |
| POST | `R/activate` | Activate the region | `303` → `R` |
| GET | `R/delete` | Delete-region confirmation | `200` |
| POST | `R/delete` | Delete the region | `303` → `/admin/institutions` |
| GET | `R/institutions/new` | Create-institution form | `200` |
| POST | `R/institutions` | Create an institution in the region | `303` → `R` |
| GET | `I/rename` | Rename-institution form | `200` |
| POST | `I/rename` | Rename the institution | `303` → `R` |
| POST | `I/deactivate` | Deactivate the institution | `303` → `R` |
| POST | `I/activate` | Activate the institution | `303` → `R` |
| GET | `I/delete` | Delete-institution confirmation | `200` |
| POST | `I/delete` | Delete the institution | `303` → `R` |

That is 8 `GET` and 10 `POST` routes. The `POST` routes are added to
`tests/integration/test_routes.py::test_the_write_routes_are_exact`.

**Lookup order on every route with ids**: the region first, then the institution. A missing region
is "Region not found" (`404`), even if an institution id is also given. An institution that does
not exist, or that belongs to another region, is "Educational institution not found" (`404`).
Nothing changes in either case (FR-043, spec edge cases).

## The tab — `GET /admin/institutions` and `GET R`

`200`. Content, inside `<div class="institutions-layout">` (research D12):

**Left: `<section aria-labelledby="regions-heading">`**

- the heading "Regions";
- a **Create** link to `/admin/institutions/regions/new`;
- with no regions: "No regions yet" (FR-009);
- otherwise a `<ul class="regions-list">`, sorted by `(name_key, id)` (FR-007). Each item has:
  - the name as a link to `/admin/institutions/regions/{id}`. On the selected region, the link
    carries `aria-current="true"` and the item is highlighted (FR-002, research D11);
  - when deactivated, the mark "Deactivated" (FR-008);
  - a **Rename** link to `R/rename`;
  - **Deactivate** (when active) or **Activate** (when deactivated): a one-button
    `<form method="post">` to `R/deactivate` or `R/activate`;
  - a **Delete** link to `R/delete` (FR-010).

**Right: `<section aria-labelledby="institutions-heading">`**

- With no region selected (`/admin/institutions`): the heading "Educational institutions" and the
  text "Select a region". There is no **Create**, and no institution actions (FR-004).
- With a region selected (`R`):
  - the heading "Educational institutions in “{region name}”", plus "Deactivated" if the region is
    deactivated;
  - if the region is active, a **Create** link to `R/institutions/new` (FR-014);
  - if the region is deactivated, no **Create**, and instead the text "This region is deactivated.
    New educational institutions cannot be added to it." (FR-014, US3-6);
  - with no institutions: "No educational institutions yet" (FR-013);
  - otherwise a table of the region's institutions only, sorted by `(name_key, id)` (FR-011).
    Columns:
    - Name;
    - Status: "Active" or "Deactivated" (FR-012);
    - Actions: **Rename** link to `I/rename`; **Deactivate** or **Activate** one-button form to
      `I/deactivate` or `I/activate`; **Delete** link to `I/delete`. All three are offered whatever
      the region's status (FR-015).

`GET R` for a region that does not exist: `404` "Region not found" (spec edge case).

Opening either page changes nothing (FR-040).

## Region forms

### `GET /admin/institutions/regions/new` and `POST /admin/institutions/regions`

The form has the heading "New region", one field `name` (text input, `maxlength="200"`,
`required`), a **Save** button, and a **Cancel** link to `/admin/institutions`. A missing field is
treated as an empty string.

| Outcome of the `POST` | Response |
|---|---|
| Valid and unique | Create an active region. `303` → `/admin/institutions/regions/{new id}` (FR-022). |
| Invalid (name rules) | `400`. The form again, with the message and the submitted value exactly as typed (FR-025). |
| Duplicate, including a concurrent insert caught by the constraint | `400`. "A region named “…” already exists." and the submitted value. |

### `GET R/rename` and `POST R/rename`

The form has the heading "Rename region", the field pre-filled with the current name (FR-026),
**Save**, and **Cancel** to `R`.

| Outcome of the `POST` | Response |
|---|---|
| Valid and unique (own name and a change of case included) | Update, or do nothing if unchanged. `303` → `R`. |
| Invalid or duplicate | `400`. The form again, with the message and the submitted value. The region is unchanged (FR-028). |
| Region does not exist | `404` "Region not found". |

### `POST R/deactivate` and `POST R/activate`

No fields. They set the region's status. A repeat changes nothing and is not an error (FR-032).
The institutions' statuses are untouched (FR-033). `303` → `R`. `404` "Region not found" if the
region does not exist.

### `GET R/delete` — confirmation

`200`. Content:

- the heading "Delete region “{name}”?";
- the sentence "Deleting a region cannot be undone.";
- a form `POST R/delete` with a **Delete** button;
- **Cancel** to `R` (FR-035).

`404` if the region does not exist. Opening the page changes nothing.

### `POST R/delete`

| Outcome | Response |
|---|---|
| The region holds no institution | Delete it. `303` → `/admin/institutions` (FR-039). |
| The region holds at least one institution, active or deactivated (or the foreign key refuses, in a race) | `409`. The confirmation page again, without the **Delete** button, with "“{name}” still holds educational institutions and cannot be deleted. Delete its institutions first." and a link back to `R`. Nothing changes (FR-036). |
| Region does not exist | `404` "Region not found". |

## Institution forms

### `GET R/institutions/new` and `POST R/institutions`

The form has the heading "New educational institution in “{region name}”" (FR-023), one field
`name`, **Save**, and **Cancel** to `R`.

| Outcome | Response |
|---|---|
| Region does not exist | `404` "Region not found". Nothing is created (FR-024). |
| Region deactivated (`GET` or `POST`) | `409`. The same page with no form, the text "This region is deactivated. New educational institutions cannot be added to it.", and a link back to `R`. Nothing is created (FR-024, US3-7). |
| `POST`, valid and unique within the region | Create an active institution in the region. `303` → `R` (FR-023). |
| `POST`, invalid | `400`. The form again, with the message and the submitted value. |
| `POST`, duplicate within the region (including a concurrent insert) | `400`. "An educational institution named “…” already exists in this region." and the submitted value (FR-021). |

### `GET I/rename` and `POST I/rename`

The form has the heading "Rename educational institution", a line naming its region, the field
pre-filled, **Save**, and **Cancel** to `R`. There is **no** region field (FR-030, US4-1). The
`POST` reads only `name`. Any other submitted field is ignored.

| Outcome of the `POST` | Response |
|---|---|
| Valid and unique within the region | Update, or do nothing if unchanged. `303` → `R`. |
| Invalid or duplicate | `400`. The form again, with the message and the submitted value. Unchanged. |
| Region missing | `404` "Region not found". |
| Institution missing or in another region | `404` "Educational institution not found". |

### `POST I/deactivate` and `POST I/activate`

No fields. They set the institution's status, whatever the region's status. A repeat changes
nothing. `303` → `R`. `404` as above.

### `GET I/delete` — confirmation

`200`. Content:

- the heading "Delete educational institution “{name}”?";
- the line "Region: {region name}";
- the sentence "Deleting an educational institution cannot be undone.";
- a form `POST I/delete` with a **Delete** button;
- **Cancel** to `R` (FR-035).

`404` as above.

### `POST I/delete`

| Outcome | Response |
|---|---|
| Unused (`count_institution_uses` = 0) | Delete it. `303` → `R` (FR-039). |
| In use (count > 0, or a foreign-key `IntegrityError`) | `409`. The confirmation page again, without **Delete**, with "“{name}” is in use and cannot be deleted. You can deactivate it instead." If the institution is active, a **Deactivate** form to `I/deactivate` is shown. Nothing changes (FR-037). |
| Region or institution missing, or the institution is in another region | `404`, as above. |

## Not-found pages

Both have status `404`, are rendered in the admin layout with **Educational institutions** current,
show no internal details, and link back to `/admin/institutions` (FR-043):

| Page | Heading | Sentence |
|---|---|---|
| Region | "Region not found" | "This region does not exist. It may have been deleted." |
| Institution | "Educational institution not found" | "This educational institution does not exist in this region. It may have been deleted." |

## Changes to existing routes

| Route | Before | After |
|---|---|---|
| `GET /admin/institutions` | `200` placeholder in `app/routers/admin.py` | `200` the two lists, served by `app/routers/admin_institutions.py` (research D13) |
| `/admin`, `/admin/teachers`, `/admin/subjects/**` | — | unchanged (FR-049) |

## Logging

One `INFO` line per successful change, with ids and the action only. Examples:

- `Region created: id=3`
- `Region deactivated: id=3`
- `Institution created: id=12 region_id=3`
- `Institution deleted: id=12 region_id=3`

A no-op logs nothing. Access denials keep milestone 5's log line.
