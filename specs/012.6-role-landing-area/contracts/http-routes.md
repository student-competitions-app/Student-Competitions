# Contract: HTTP Routes (Milestone 12.6)

Only the routes whose answer changes are listed. Every other route answers as before.

## `GET /`

`@allow_roles(ADMIN, TEACHER, STUDENT)`, unchanged.

| Visitor | Before | After |
|---|---|---|
| signed out | 303 → `/login?next=%2F` | unchanged |
| several roles, none chosen | 303 → `/role?next=%2F` | unchanged |
| current role **Administrator** | 200, home page (cards `/admin`, `/staff`; database line) | **303 → `/admin`** (then 303 → `/admin/teachers`) |
| current role **Teacher** | 200, home page (cards `/teacher`, `/staff`; database line) | **303 → `/teacher`** (then 303 → `/teacher/students`) |
| current role **Student** | 200, home page (card `/student`; database line) | unchanged |

The redirect is answered before the database status is read. `HEAD /` is not served (405), as
today: the route is `GET` only, and this milestone does not change that.

## `GET /staff`

| Visitor | Before | After |
|---|---|---|
| Administrator, Teacher | 200, placeholder "Staff area" | **404 "Page not found"**, identical to `/no-such-page` |
| Student | 403 Access denied | **404**, identical to `/no-such-page` |
| signed out | 303 → `/login?next=%2Fstaff` | **404**, identical to `/no-such-page` |

The route is deleted, so the address is unknown like any other. Nothing renders a link to it.

## Flows that end at `/` (unchanged addresses, new final destination)

| Flow | Answer (unchanged) | Where an administrator / teacher now lands |
|---|---|---|
| `POST /login/code`, one role, no `next` | 303 → `/` | `/admin/teachers` / `/teacher/students` |
| `POST /login/code`, several roles | 303 → `/role?next=%2F` | after choosing: the chosen role's first tab |
| `POST /role` without `next` (user menu switch) | 303 → `/` | the new role's first tab |
| `GET /role`, one role | 303 → `/` | their first tab |
| brand link `href="/"` | — | the current role's first tab |

A `next` given to `POST /login/code` or `POST /role` is still followed as is (spec FR-007).

## Every administrator area page (`render_admin`)

The footer gains the database line (`<p data-engine data-revision data-boots>`, same message as the
home page). If reading it fails, the line is left out, the page answers with its usual status, and the
log has `Database status unavailable: <type>: <message>`. Teacher area pages are unchanged and have
no line.

## `GET /profile` and every error page (`pages/error.html`)

The back link follows `back_link_for(current role)`; see [data-model.md §3](../data-model.md).

| Page | Administrator | Teacher | Student | role not read |
|---|---|---|---|---|
| `/profile` | "Back to the administrator area" → `/admin` | "Back to the teacher area" → `/teacher` | "Back to the home page" → `/` | (needs a role) |
| 403 Access denied | same as above | same as above | same as above | — |
| 404 unknown address, 403 cross-site refusal, 405 | "Back to the home page" → `/` | same | same | same |

`/data-erased` keeps "Go to the home page" → `/`.
