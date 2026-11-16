# Data Model: Each Role Lands in Its Own Area (Milestone 12.6)

**No stored data changes.** No table, column, constraint or Alembic revision is added, changed or
removed. Sessions keep their `current_role` as milestone 5 defined it. The boot counter and the schema
revision are read as milestone 3 defined them.

The milestone changes three in-memory declarations and one view value. They are listed here because
the redirect, the back links and the tests all depend on them.

## 1. `Area` (`app/routers/areas.py`): one area of the application

| Field | Type | Before | After |
|---|---|---|---|
| `path` | `str` | the area's address | unchanged |
| `title` | `Text` | the area's name | unchanged |
| `roles` | `frozenset[Role]` | the roles that may open it | unchanged |
| `description` | `Text` → `Text \| None` | the home page card's sentence, on every area | only the student's area has one (`None` for the administrator and teacher areas) |
| `back_label` | — → `Text \| None` | — | "Back to the … area" for an area that is a landing, otherwise `None` |

| Declaration | `path` | `roles` | `description` | `back_label` |
|---|---|---|---|---|
| `ADMIN_AREA` | `/admin` | {ADMIN} | `None` (was "Manage teachers, educational institutions and subjects.") | "Back to the administrator area" |
| `TEACHER_AREA` | `/teacher` | {TEACHER} | `None` (was "Manage your classes, students and teams, …") | "Back to the teacher area" |
| `STUDENT_AREA` | `/student` | {STUDENT} | "Take part in competitions and see your results." (unchanged) | `None` |
| ~~`STAFF_AREA`~~ | ~~`/staff`~~ | ~~{ADMIN, TEACHER}~~ | deleted | deleted |

`AREAS = (ADMIN_AREA, TEACHER_AREA, STUDENT_AREA)`. `areas_for(role)` returns the areas in `AREAS`
whose `roles` hold `role`, in that order. The home page shows it to the student only.

## 2. Landings (`app/routers/areas.py`): where `/` sends a role

`LANDINGS: dict[Role, Area] = {Role.ADMIN: ADMIN_AREA, Role.TEACHER: TEACHER_AREA}`

`landing_area(role: Role | None) -> Area | None`: `LANDINGS.get(role)`. For `None` and for
`Role.STUDENT` it returns `None`, which means "show the home page".

Invariant: every landing's `roles` holds the role that maps to it, and every landing has a
`back_label`. A unit test checks both.

## 3. `BackLink` (`app/routers/areas.py`): the "Back to …" link of the profile and error pages

| Field | Type | Meaning |
|---|---|---|
| `path` | `str` | where the link leads |
| `label` | `Text` | its text, translated when rendered |

`HOME_BACK_LINK = BackLink("/", _("Back to the home page"))`

`back_link_for(role: Role | None) -> BackLink`:

| `role` | Result |
|---|---|
| `Role.ADMIN` | `BackLink("/admin", "Back to the administrator area")` |
| `Role.TEACHER` | `BackLink("/teacher", "Back to the teacher area")` |
| `Role.STUDENT`, `None` | `HOME_BACK_LINK` |

`None` covers a signed-out visitor, a person with several roles who has not chosen one, an unknown
address, a refused cross-site request, and a session that could not be read.

## 4. `DatabaseStatus` (`app/services/database_status.py`): the footer line

Unchanged: `engine`, `revision`, `boots`, `display_name`. New reader:

`read_database_status_or_none(session) -> DatabaseStatus | None`: `read_database_status(session)`, or
`None` after logging `"Database status unavailable: <type>: <message>"` when it raises
`SQLAlchemyError`.

| Template context value | Set by | Meaning |
|---|---|---|
| `db_status` | `home` (student), `render_admin` (every administrator page) | the line to show, or `None` to leave it out |
| `data_available` | `home` only | `db_status is not None`. It shows the unavailable notice, as today |
