# Contract: HTTP Routes — Administrator Area (Milestone 6)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D5–D7

## Access (all routes below)

Every route below is declared `@allow_roles(Role.ADMIN)` and goes through milestone 5's
`resolve_access`. No route is added to `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES`.

| Who | `GET` | `POST` |
|---|---|---|
| Anonymous | `303` → `/login?next=<path>` (FR-038) | `303` → `/login` |
| Signed in, no current role yet | `303` → `/role?next=<path>` | `303` → `/role` |
| Current role teacher or student (including an administrator using another role) | `403` "Access denied" (FR-037) | `403` "Access denied"; nothing changes |
| Current role administrator | as described below | as described below |
| Any `POST` from another site | — | `403` "Request refused" (FR-034), before any database access |

`{id}` is declared in routes as `{subject_id:int}` (Starlette's integer converter). A non-integer
path such as `/admin/subjects/abc/rename` then matches no route, and gets the application's
existing friendly `404` page. Without the converter, FastAPI's parameter validation would answer
a JSON `422`, which the application's error handlers do not cover.

## Area shell — `app/routers/admin.py`

### `GET /admin`

`303 See Other`, `Location: /admin/teachers` (FR-005). The home page's "Administrator area" link
still points here (FR-008).

### `GET /admin/teachers`

`200`. The admin layout with the **Teachers** tab current. Content: the heading "Teachers" and one
sentence saying that teacher management arrives in a later milestone. No forms, no buttons
(FR-007).

### `GET /admin/institutions`

`200`. The same placeholder, with the heading "Educational institutions" and the
**Educational institutions** tab current.

## Subjects — `app/routers/admin_subjects.py` (prefix `/admin/subjects`)

Every page below uses the admin layout with the **Subjects** tab current (FR-004).

### `GET /admin/subjects` — the list

`200`. Content:

- a **Create** link to `/admin/subjects/new`;
- with no subjects: the text "No subjects yet" (FR-011);
- otherwise, a table with one row per subject, sorted by `name_key`, then `id` (research D3).
  Each row shows:
  - the name;
  - the status, "Active" or "Inactive" (FR-010);
  - a **Rename** link to `/admin/subjects/{id}/rename`;
  - **Deactivate** (when active) or **Activate** (when inactive): a one-button
    `<form method="post">` to `/admin/subjects/{id}/deactivate` or `/activate`;
  - a **Delete** link to `/admin/subjects/{id}/delete` (the confirmation page).

### `GET /admin/subjects/new` — create form

`200`. A form `POST /admin/subjects` with one field, `name` (text input, `maxlength="200"`,
`required`), a **Save** button and a **Cancel** link back to `/admin/subjects`.

### `POST /admin/subjects` — create

Form field: `name`. A missing field is treated as an empty string.

| Outcome | Response |
|---|---|
| Valid and unique | Create an active subject. `303` → `/admin/subjects` (FR-018, FR-033). |
| Invalid (research D2) | `400`. The create form again, with the message and the submitted value exactly as typed (FR-019). |
| Duplicate, including a concurrent insert caught by the unique constraint | `400`. The create form again, with "A subject named “…” already exists." and the submitted value. |

### `GET /admin/subjects/{id}/rename` — rename form

`200`. A form `POST /admin/subjects/{id}/rename` with one field, `name`, pre-filled with the
current name (FR-020), plus **Save** and **Cancel**. `404` "Subject not found" if the subject does
not exist.

### `POST /admin/subjects/{id}/rename` — rename

Form field: `name`.

| Outcome | Response |
|---|---|
| Valid and unique (own name and change of case included) | Update, or do nothing if the name is unchanged. `303` → `/admin/subjects`. |
| Invalid or duplicate | `400`. The rename form again, with the message and the submitted value. The subject is unchanged (FR-022). |
| Subject does not exist | `404` "Subject not found". |

### `POST /admin/subjects/{id}/deactivate` and `POST /admin/subjects/{id}/activate`

No form fields. Set the status. If the subject already has that status, nothing changes and there
is no error (FR-026). `303` → `/admin/subjects`. `404` "Subject not found" if the subject does not
exist.

### `GET /admin/subjects/{id}/delete` — confirmation

`200`. Content:

- the subject's name;
- the sentence "Deleting a subject cannot be undone.";
- a form `POST /admin/subjects/{id}/delete` with a **Delete** button;
- a **Cancel** link to `/admin/subjects` (FR-028).

`404` "Subject not found" if the subject does not exist. Opening this page changes nothing.

### `POST /admin/subjects/{id}/delete` — delete

| Outcome | Response |
|---|---|
| Unused | Delete the row. `303` → `/admin/subjects` (FR-031). |
| In use (`count_subject_uses` > 0, or a foreign-key `IntegrityError`) | `409`. The confirmation page again, without the **Delete** button, with the message "“{name}” is in use and cannot be deleted. You can deactivate it instead." and, if the subject is active, a **Deactivate** form (FR-029). Nothing changes. |
| Subject does not exist | `404` "Subject not found". |

## "Subject not found" page

Status `404`, rendered in the admin layout with **Subjects** current. Content: the heading
"Subject not found", the sentence "This subject does not exist. It may have been deleted.", and a
link back to `/admin/subjects` (FR-035). There are no internal details.

## Unknown paths under `/admin`

For example, `/admin/unknown`. No route matches, so the application's existing friendly `404`
page is shown (spec edge case). Nothing changes here.

## Admin layout — `templates/layouts/admin.html`

Extends `layouts/base.html`. Directly inside `<main>`, before the page content:

```html
<nav class="admin-tabs" aria-label="Administrator area">
  <ul>
    <li><a href="/admin/teachers" aria-current="page">Teachers</a></li>   <!-- only on the current tab -->
    <li><a href="/admin/institutions">Educational institutions</a></li>
    <li><a href="/admin/subjects">Subjects</a></li>
  </ul>
</nav>
```

- Exactly one link carries `aria-current="page"`. CSS in `static/css/app.css` highlights it
  (FR-004).
- Tabs are ordinary `<a href>` links with no script (FR-003).
- No template outside `templates/pages/admin/` extends this layout (FR-006).

## Changes to existing routes

| Route | Before | After |
|---|---|---|
| `GET /admin` | `200` placeholder page from `areas.py` | `303` → `/admin/teachers`, served by `admin.py` |
| `GET /teacher`, `/student`, `/staff`, `/` | unchanged | unchanged (FR-041) |

## Logging

One `INFO` line per successful change, with the subject id and the action only. For example:
`Subject created: id=7` or `Subject deleted: id=7`. Subject names are not personal data, but
there is no need to log them. Access denials keep milestone 5's existing log line.
