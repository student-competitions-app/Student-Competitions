# Contract: HTTP routes (Milestone 11.1)

The router is `app/routers/teacher_teams.py`, with `prefix="/teacher/teams"`, included in
`app/main.py`.

- **Every route** is `@allow_roles(Role.TEACHER)`, acts as `request.state.user`, and renders
  through `render_teacher(..., active_tab="teams")`.
- **Thin handlers**: they read every value as a plain string, call `app.services.teacher_access` and
  `app.services.teams`, map the outcomes to a status and a page, and redirect with 303 after a change
  (FR-043, FR-044).
- **Logging**: nothing is logged except by the services, with ids only (FR-016).

Decisions: [research.md](../research.md) R4, R10–R13.

## Tabs

`app/routers/teacher.py`:

```python
TEACHER_TABS = (
    TeacherTab("students", "Students", "/teacher/students"),
    TeacherTab("teams", "Teams", "/teacher/teams"),
    TeacherTab("questions", "Questions", "/teacher/questions"),
    TeacherTab("competitions", "Competitions", "/teacher/competitions"),
)
```

`GET /teacher` still answers `303 /teacher/students` (FR-025). The module docstring names the new
router.

## Order of checks (every route)

1. **Role**: an administrator or a student gets **403** (the milestone 5 page, naming the current
   role; FR-019).
2. **Ids**: a query or form id that is not ASCII digits ≤ `MAX_ID` is **403**
   (`AccessDenied(Role.TEACHER)`). A path id that is not an integer matches no route and gets the
   application's 404 for everyone.
3. **The team** (`reach_team`) or, for the new-team form, **the institution** (`reach_institution`),
   with `write=True` on every route marked *manage*: an unknown, deleted or unreachable team, Read
   access, or a broken chain gives **403**. Nothing named by a later step has been read yet (FR-023).
4. **The student or the class** named, through `reach_student` and `reach_class`, and checked
   against the team's institution: **403** otherwise (FR-022).
5. **Fields and rules**: name errors give **400**. "Already a member" and "full" are redirects.
6. **The service write** repeats steps 3 and 4 under lock (research R5). A refusal there is **403**.

## Helpers

```python
def selection_path(region_id: int, institution_id: int, team_id: int | None = None) -> str:
    """/teacher/teams?region=<r>&institution=<i>[&team=<t>]"""

def team_path(institution: ReachableInstitution, team_id: int) -> str:
    """selection_path(institution.region_id, institution.id, team_id)"""
```

Every redirect, Cancel and back link to the tab is built by these helpers, from the team's own
institution (research R10).

## Routes

| # | Method and path | Kind | Purpose |
|---|---|---|---|
| 1 | `GET /teacher/teams` | all teachers | the tab |
| 2 | `GET /teacher/teams/institutions/{institution_id:int}/new` | *manage* | the new-team form |
| 3 | `POST /teacher/teams/institutions/{institution_id:int}/new` | *manage* | create |
| 4 | `GET /teacher/teams/{team_id:int}/rename` | *manage* | the rename form |
| 5 | `POST /teacher/teams/{team_id:int}/rename` | *manage* | rename |
| 6 | `GET /teacher/teams/{team_id:int}/delete` | *manage* | the delete confirmation |
| 7 | `POST /teacher/teams/{team_id:int}/delete` | *manage* | delete (soft) |
| 8 | `GET /teacher/teams/{team_id:int}/add` | *manage* | the Add students page |
| 9 | `POST /teacher/teams/{team_id:int}/members` | *manage* | add one student |
| 10 | `GET /teacher/teams/{team_id:int}/members/{user_id:int}/remove` | *manage* | the remove confirmation |
| 11 | `POST /teacher/teams/{team_id:int}/members/{user_id:int}/remove` | *manage* | remove one member |

### 1. `GET /teacher/teams`: the tab

**Query** (all optional strings, so no input ever gets a 422): `region`, `institution`, `team`
(an id or `new`), `notice` (a sealed token).

**Selection**, validated as on **Students** (FR-022, US4-7):

- `institution` without `region`, or `team` without `institution`: 403.
- `region` not among the teacher's reachable regions: 403.
- `institution` not reachable, or not in `region`: 403.
- `team=new`: Write gives `303 /teacher/teams/institutions/<id>/new`; Read gives 403.
- `team` not a live team of the institution (`reach_team(..., institution_id=…)`): 403.

**The page, top to bottom**:

1. `page_heading("Teams")`.
2. **The notice** (research R11), if `notice` is valid, fresh, for the selected team, and its student
   is a listed member:
   - added: `notice("<First> <Last> was added to the team.", "success")`;
   - already a member: `notice("<First> <Last> is already in this team.", "info")`.
3. **`chained_lists`**, with three levels and `auto-submit.js`:

   | Level | `name` | Label | Placeholder | Options | Extra |
   |---|---|---|---|---|---|
   | 1 | `region` | Region | Select a region | `reachable_regions(...)` | |
   | 2 | `institution` | Educational institution | Select an educational institution | the region's reachable institutions, labelled "Name — Read" or "Name — Write" | |
   | 3 | `team` | Team | Select a team | `list_teams(institution)` | `("new", "+ Add team")` with Write |

   Each level is disabled until the one before it is selected, and every level is disabled when the
   teacher has no link (FR-028).
4. **One of the following**, as `empty_state(message, hint)`:

   | State | Message | Hint |
   |---|---|---|
   | No reachable institution | You are not linked to any educational institution | Ask an administrator to link you to an educational institution. |
   | No region | Select a region to continue | Choose a region in the first list. |
   | No institution | Select an educational institution to continue | Choose an educational institution in the second list. |
   | Institution with no live team | No teams yet | Write: "Create the first team with + Add team." Read: "A teacher with Write access to this institution creates its teams." |
   | Teams, none selected | Select a team to see its members | Choose a team in the third list. |

5. **The selected team**, inside `<section aria-labelledby="team-heading">`:
   - **The heading**: `section_heading(team.name, "team-heading", action)`.
     - With Write, `action` is `("Add students", "/teacher/teams/<id>/add")`, and the call block
       holds `link_button("Rename", "/teacher/teams/<id>/rename", kind="secondary",
       outline=True, small=True)` and `link_button("Delete", "/teacher/teams/<id>/delete",
       kind="destructive", outline=True, small=True)`.
     - With Read: no action and no row (FR-034).
   - **No active member**: `empty_state("No members in this team yet", hint)`. The hint is "Add the
     first student with Add students." with Write; with Read there is no hint.
   - **Otherwise**: `data_table(["Name", "Class", "Actions"])`, or `["Name", "Class"]` with Read,
     one row per active member in the service's order (FR-035):
     - `cell("Name", "<Last> <First>")`, as on **Students**;
     - `cell("Class", class_label)`, for example "KN-21 · year 2";
     - with Write, `actions_cell()` holding
       `link_button("Remove", "/teacher/teams/<id>/members/<user_id>/remove",
       kind="destructive", outline=True, small=True)`.

**Status**: 200. Opening the page changes nothing.

### 2. `GET /teacher/teams/institutions/{institution_id:int}/new`: the new-team form (*manage*)

- **The institution**: `reach_institution(..., write=True)`, else 403.
- **The page** (`pages/teacher/team_form.html`):
  - `back_link(selection_path(region, institution), "Back to Teams")`;
  - `page_heading("New team in “<institution>”")`;
  - `error_summary(errors, order=["name"])`;
  - "Educational institution: <name> (<region>)" as text;
  - a form posting to the same address with
    `field("name", "Name", attrs={"maxlength": "200", "required": True})`;
  - `form_actions("Save", cancel_href=selection_path(region, institution))` (FR-032).
- **Status**: 200.

### 3. `POST /teacher/teams/institutions/{institution_id:int}/new`: create (*manage*)

**Form**: `name`. Any other field, such as an institution, is ignored (FR-001).

| Case | Response |
|---|---|
| No Write reach (also when lost before the save) | 403; nothing stored |
| Name error | 400, the form again with the error beside the field, in the summary, and the value as typed (FR-033) |
| Duplicate among live teams, in any institution | 400, the same, with "A team named “<entered name>” already exists." (FR-002) |
| Created | 303 → `selection_path(region, institution, new_team_id)` (FR-031) |

### 4. `GET /teacher/teams/{team_id:int}/rename`: the rename form (*manage*)

The same template and layout as route 2:

- the heading "Rename team “<name>”";
- the back link `team_path(...)` "Back to “<name>”";
- the field filled with the current name;
- the form posting to the same address;
- Cancel to `team_path(...)` (FR-032).

**Status**: 200.

### 5. `POST /teacher/teams/{team_id:int}/rename`: rename (*manage*)

| Case | Response |
|---|---|
| No Write reach, or the team deleted meanwhile | 403; nothing changed |
| Name error or duplicate | 400, as for route 3. The team itself never counts as a duplicate, so a change of case is valid (US3-5). |
| Saved, or unchanged | 303 → `team_path(...)` (FR-031) |

### 6. `GET /teacher/teams/{team_id:int}/delete`: the delete confirmation (*manage*)

`pages/teacher/team_delete.html`:

- `back_link(team_path(...), "Back to “<name>”")`;
- `confirmation("Delete team “<name>”?", none, "/teacher/teams/<id>/delete", "Delete",
  team_path(...))`, with:
  - `details_list([("Educational institution", "<name> (<region>)"), ("Members", "<n>")])`. `n` is
    the number of active members; blocked members are not counted (FR-037, US6-2);
  - "The team will be hidden and can no longer join new competitions. Its members keep their
    accounts, classes and other teams. A deleted team cannot be restored."

**Status**: 200. Opening it changes nothing.

### 7. `POST /teacher/teams/{team_id:int}/delete`: delete (*manage*)

| Case | Response |
|---|---|
| No Write reach, or already deleted | 403; nothing changed (US2-8) |
| Deleted | 303 → `selection_path(region, institution)`, with no team selected (FR-031, US2-6) |

### 8. `GET /teacher/teams/{team_id:int}/add`: the Add students page (*manage*)

**Query**: `class`, an optional id.

**Checks**:

1. **The team**: `reach_team(..., write=True)`, else 403 (US4-8).
2. **The class**, when given: `reach_class(..., institution_id=team.institution_id)` and active, else
   403. A class of another institution and a deactivated class in the address are both refused (spec
   Edge Cases).

**The page** (`pages/teacher/team_add_students.html`), top to bottom:

1. `back_link(team_path(...), "Back to “<team>”")` (FR-038).
2. `page_heading("Add students to “<team>”")`.
3. **The team is full** (50 members, blocked ones included): `notice("This team already has 50
   members", "info")` (FR-041).
4. **`chained_lists`** with one level:
   - `name="class"`, label "Class", placeholder "Select a class";
   - the active classes of the team's institution, sorted by name ignoring case, labelled "KN-21 ·
     year 2";
   - the form action is the page's own address, and nothing is carried.

   It works without JavaScript through the **Show** button (FR-038).
5. **One of the following**:
   - **No class chosen**: `empty_state("Select a class to see its students", "Choose a class in the
     list.")`.
   - **The class has no student**: `empty_state("No students in this class yet")`.
   - **Otherwise**: `data_table(["Name", "Actions"])`, one row per student of the class, by last
     name, then first name, ignoring case (`students.list_students`):
     - `cell("Name", "<Last> <First>")`;
     - `actions_cell()` holding one of:
       - for a member, `row_note("In this team")`;
       - otherwise, when the team is not full, `post_button("/teacher/teams/<id>/members",
         "Add", kind="secondary", outline=True, small=True, hidden={"student": <user_id>,
         "class": <class_id>})`;
       - otherwise nothing (FR-039, FR-041).

**Status**: 200.

### 9. `POST /teacher/teams/{team_id:int}/members`: add one student (*manage*)

**Form**: `student` (required id) and `class` (optional id, used only for the return address).

| Case | Response |
|---|---|
| No Write reach, or the team deleted (also when lost before the save) | 403; nothing stored |
| `student` missing or not an id, an unknown person, not a student, blocked, or enrolled in another institution | 403; nothing stored (US4-5) |
| Already a member, including a lost race | 303 → `team_path(...)&notice=<sealed already>`; nothing stored (FR-042, US5-3) |
| The team holds 50 members | 303 → `/teacher/teams/<id>/add?class=<class>`, or without `class` when it is missing or no longer an active class of the institution; nothing stored. That page shows the full notice (FR-042, US5-2). |
| Added | 303 → `team_path(...)&notice=<sealed added>` (FR-040) |

"Already a member" is checked before the limit, so re-adding a member of a full team gives the
"already" notice.

### 10. `GET /teacher/teams/{team_id:int}/members/{user_id:int}/remove`: the remove confirmation (*manage*)

**Checks**: the team with Write, then the student (`reach_student`), who must be enrolled in the
team's institution and be a member. Otherwise 403: a blocked member, a non-member, or an unknown
person (FR-011).

**The page** (`pages/teacher/team_member_remove.html`):

- `back_link(team_path(...), "Back to “<team>”")`;
- `confirmation("Remove <First> <Last> from team “<team>”?", none,
  "/teacher/teams/<id>/members/<user_id>/remove", "Remove", team_path(...))`, with:
  - `details_list([("Class", class_label)])`;
  - "They stay in their class and keep their account and their other teams." (FR-036).

**Status**: 200. Opening it changes nothing.

### 11. `POST /teacher/teams/{team_id:int}/members/{user_id:int}/remove`: remove one member (*manage*)

| Case | Response |
|---|---|
| No Write reach, the team deleted, the student blocked, out of reach or not a member (also when that changes before the save) | 403; nothing changed |
| Removed | 303 → `team_path(...)` (FR-031). The student keeps their role, class, enrolment, other teams and sessions (FR-006). |

## The notice token

```python
TEAM_NOTICE_PURPOSE = "team-member-notice"
TEAM_NOTICE_TTL = timedelta(minutes=10)
# payload: {"team": <team id>, "user": <user id>, "outcome": "added" | "already"}
```

`seal` and `unseal` come from `app.core.sealing`. A token that is tampered with, expired, for
another team, of an unknown outcome, or for a student who is no longer a listed member shows no
notice and is not an error (research R11).

## Changed routes and pages (outside the router)

| Where | Change |
|---|---|
| `app/routers/teacher.py` | `TEACHER_TABS` gains **Teams** second (FR-025) |
| `app/routers/areas.py` | `TEACHER_AREA.description` = "Manage your classes, students and teams, and work with the question bank and competitions." (FR-027) |
| `pages/teacher/students.html` | the hand-built heading becomes `section_heading`, with the same markup (FR-046, research R12) |
| `app/routers/profile.py`, `pages/profile.html` | a **Teams** row for a person holding the student role (FR-013, research R14) |
| `app/routers/admin_components.py`, `pages/admin/components.html` | sample data and sections for `section_heading` and `row_note` |
| `/admin/institutions/.../delete` | unchanged page; "in use" now also covers teams (FR-017) |

**The profile's Teams row**:

- `details_list` row "Teams", given when the person holds the student role, blocked or not;
- with teams, a `<ul>` of names sorted ignoring case, a deleted team as "<name> (deleted)";
- without teams, "You are not in any team.".

## Route table changes (tests)

- **`test_routes.py`**:
  - the exact write list gains the 5 POST routes of the table above;
  - `TEACHER_SCOPED_PATHS` also takes every `/teacher/teams/` path with a `{`. The declared-page
    sweep checks only the denied roles for them, because id `1` is out of reach for the cast
    teacher;
  - `/teacher/teams` itself is swept with the cast teacher allowed.
- **`test_teacher_access.py`**: the scene gains a live team, a deleted team and a member. Every team
  page admits a Write teacher, and every team action is refused to Read, unlinked and unknown-id
  teachers and to the other roles.
