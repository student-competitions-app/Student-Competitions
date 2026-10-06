# Contract: HTTP Routes — Educational Institutions Tab (Milestone 7)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D2, D7, D8

The routes mirror the Subjects tab from milestone 6
([specs/006-admin-area/contracts/http-routes.md](../../006-admin-area/contracts/http-routes.md)):
the same methods, paths under their own prefix, statuses and Post/Redirect/Get behaviour.

## Access (all routes below)

Every route below is declared `@allow_roles(Role.ADMIN)` and goes through milestone 5's
`resolve_access`. No route is added to `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES` (FR-031, FR-032).

| Who | `GET` | `POST` |
|---|---|---|
| Anonymous | `303` → `/login?next=<path>` | `303` → `/login` |
| Signed in, no current role yet | `303` → `/role?next=<path>` | `303` → `/role` |
| Current role teacher or student (including an administrator using another role) | `403` "Access denied" | `403` "Access denied"; nothing changes |
| Current role administrator | as described below | as described below |
| Any `POST` from another site | — | `403` "Request refused" (FR-029), before any database access |

`{id}` is declared in routes as `{institution_id:int}`, so a non-integer path such as
`/admin/institutions/abc/rename` matches no route and gets the application's existing friendly
`404` page.

## Institutions — `app/routers/admin_institutions.py` (prefix `/admin/institutions`)

Every page below uses the admin layout with the **Educational institutions** tab current (FR-005).

### `GET /admin/institutions` — the list

`200`. Replaces milestone 6's placeholder (FR-001). Content:

- the heading "Educational institutions";
- a **Create** link to `/admin/institutions/new`;
- with no institutions: the text "No educational institutions yet" (FR-003);
- otherwise, a table with one row per institution, sorted by `name_key`, then `id`. Each row shows:
  - the name;
  - the status, "Active" or "Inactive" (FR-002);
  - a **Rename** link to `/admin/institutions/{id}/rename`;
  - **Deactivate** (when active) or **Activate** (when inactive): a one-button
    `<form method="post">` to `/admin/institutions/{id}/deactivate` or `/activate`;
  - a **Delete** link to `/admin/institutions/{id}/delete` (the confirmation page).

### `GET /admin/institutions/new` — create form

`200`. Heading "New educational institution". A form `POST /admin/institutions` with one field,
`name` (text input, `maxlength="200"`, `required`), a **Save** button and a **Cancel** link back to
`/admin/institutions` (FR-011).

### `POST /admin/institutions` — create

Form field: `name`. A missing field is treated as an empty string.

| Outcome | Response |
|---|---|
| Valid and unique | Create an active institution. `303` → `/admin/institutions` (FR-012, FR-028). |
| Invalid | `400`. The create form again, with the message and the submitted value exactly as typed (FR-013). |
| Duplicate, including a concurrent insert caught by the unique constraint | `400`. The create form again, with "An educational institution named “…” already exists." and the submitted value. |

### `GET /admin/institutions/{id}/rename` — rename form

`200`. Heading "Rename educational institution". The same form as create, posting to
`/admin/institutions/{id}/rename`, with `name` pre-filled with the current name (FR-014). `404`
"Educational institution not found" if it does not exist.

### `POST /admin/institutions/{id}/rename` — rename

Form field: `name`.

| Outcome | Response |
|---|---|
| Valid and unique (own name and change of case included), active or inactive | Update, or do nothing if the name is unchanged. Status and `id` are kept. `303` → `/admin/institutions` (FR-016, FR-017). |
| Invalid or duplicate | `400`. The rename form again, with the message and the submitted value. The institution is unchanged. |
| Institution does not exist | `404` "Educational institution not found". |

### `POST /admin/institutions/{id}/deactivate` and `POST /admin/institutions/{id}/activate`

No form fields. Set the status. If the institution already has that status, nothing changes and
there is no error (FR-021). `303` → `/admin/institutions`. `404` "Educational institution not
found" if it does not exist.

### `GET /admin/institutions/{id}/delete` — confirmation

`200`. Content:

- the heading "Delete “{name}”?";
- the sentence "Deleting an educational institution cannot be undone.";
- a form `POST /admin/institutions/{id}/delete` with a **Delete** button;
- a **Cancel** link to `/admin/institutions` (FR-023).

`404` "Educational institution not found" if it does not exist. Opening this page changes nothing.

### `POST /admin/institutions/{id}/delete` — delete

| Outcome | Response |
|---|---|
| Unused | Delete the row. `303` → `/admin/institutions` (FR-026). |
| In use (`count_institution_uses` > 0, or a foreign-key `IntegrityError`) | `409`. The confirmation page again, without the **Delete** button, with the message "“{name}” is in use and cannot be deleted. You can deactivate it instead." and, if the institution is active, a **Deactivate** form (FR-024). Nothing changes. |
| Institution does not exist | `404` "Educational institution not found". |

## "Educational institution not found" page

Status `404`, rendered in the admin layout with **Educational institutions** current. Content: the
heading "Educational institution not found", the sentence "This educational institution does not
exist. It may have been deleted.", and a link "Back to the educational institutions" to
`/admin/institutions` (FR-030). There are no internal details.

## Changes to existing routes

| Route | Before | After |
|---|---|---|
| `GET /admin/institutions` | `200` placeholder from `admin.py` | `200` institution list from `admin_institutions.py` |
| `GET /admin`, `/admin/teachers`, `/admin/subjects…` | unchanged | unchanged (FR-006) |

## New write routes

The application's write surface (pinned by `test_routes.py`) grows by exactly these five:

```text
POST /admin/institutions
POST /admin/institutions/{institution_id:int}/rename
POST /admin/institutions/{institution_id:int}/deactivate
POST /admin/institutions/{institution_id:int}/activate
POST /admin/institutions/{institution_id:int}/delete
```

## Logging

One `INFO` line per successful change, with the institution id and the action only, for example
`Institution renamed: id=3`. Institution names are not personal data, but there is no need to log
them. Access denials keep milestone 5's existing log line.
