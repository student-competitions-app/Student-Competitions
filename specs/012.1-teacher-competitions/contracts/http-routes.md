# Contract: HTTP Routes of the Competitions Tab

Router `app/routers/teacher_competitions.py`, prefix `/teacher/competitions`, included in
`app/main.py`. It replaces the placeholder handler in `app/routers/teacher.py`; the **Competitions**
entry of `TEACHER_TABS` keeps its key, label and path. Every route is
`@allow_roles(Role.TEACHER)`. Handlers read every value as a plain string, so no input gets
FastAPI's 422. See [research.md](../research.md) R9–R13.

## Order of checks (every route)

1. **Role** (decorator): not a teacher → 403, the milestone 5 "access denied" page naming the
   current role.
2. **Setting** (manage routes, first line of the handler, before any value is parsed):
   `can_manage_competitions` false → 403, for unknown ids too.
3. **Subject**: `subject` from the query or form, parsed as an ASCII integer up to `MAX_ID`. Not
   offered (unknown, non-numeric, or deactivated with no finished competition) → 404 "Subject not
   found". On the create page and action, also a deactivated subject → 404.
4. **Competition**: unknown, of another subject than step 3's, or invisible → 404 "Competition not
   found".
5. **Status**: the refusals below → 409.
6. **Fields** (create and edit): errors → 400, the form again with every error and every value as
   typed.
7. **The write** repeats steps 2–5 under lock (services contract); its refusals map to the same
   responses.

**Not-found page**: `pages/teacher/competition_not_found.html`, in the teacher frame, with the back
link "Back to the competitions" to `/teacher/competitions` (no subject: the subject may be the
missing thing). Headings and texts:

- "Subject not found" / "This subject does not exist, or it is deactivated and has no finished
  competitions."
- "Competition not found" / "This competition does not exist, or its subject is deactivated."

## Address parameters

| Name | Where | Values | Missing or invalid |
|---|---|---|---|
| `subject` | query, form | a subject id | missing or empty on the list: no subject chosen; anything else not offered: 404 |
| `status` | query, form | `upcoming`, `in_progress`, `finished`, `cancelled` | **All** |
| `page` | query, form | a page number | `paging.parse_page`: 1, clamped to the last page |
| `notice` | query (list only) | a sealed notice token | no notice |

**`list_path(subject_id, status=None, page=1, anchor=None, notice=None)`** builds every return
address: `/teacher/competitions?subject=3&status=upcoming&page=2&notice=…#competition-17`, leaving
out `status` for **All**, `page` for 1, and `notice` and the anchor when not given. It takes only
looked-up ids and parsed values.

## Routes

### 1. `GET /teacher/competitions`: the tab (read)

Query: `subject`, `status`, `page`, `notice`.

- **Subject list**: `chained_lists` with one level, `subject`, label "Subject", placeholder
  "Choose a subject", options the active subjects, and the group "Deactivated subjects" with the
  offered deactivated ones. Disabled when nothing is offered. When exactly one subject is offered
  and none is in the address, it is chosen.
- **Heading**: `page_heading("Competitions")`, with the action **Add competition** →
  `/teacher/competitions/new?subject=<id>&status=<s>&page=<n>` only for a teacher with the setting
  and a chosen **active** subject.
- **Exactly one of**:
  - nothing offered: `empty_state("No subjects yet", "Ask an administrator to add a subject.")`;
  - no subject chosen: `empty_state("Select a subject", "Choose a subject in the list above to see
    its competitions.")`;
  - the subject's list (below).
- **The subject's list**, for a chosen subject:
  - the **Status** list: a second `chained_lists` level, label "Status", options **All** (value
    empty), **Upcoming**, **In progress**, **Finished**, **Cancelled**, carrying `subject` as a
    hidden field and no page, so choosing opens the first page;
  - the notice, if the `notice` token is valid (services contract §Notices);
  - no competition at all in the subject (visible ones): `empty_state("No competitions yet", "Add
    the first competition with Add competition.")`, the hint only with the setting and an active
    subject;
  - competitions, none matching the status: `empty_state("No competitions with this status",
    "Choose another status, or All.")`;
  - otherwise `page_navigation(paging, href, "Competitions", "Pages, top")`, the table, and the
    same navigation labelled "Pages, bottom". `href` keeps `subject` and `status`.
- **The table**: `data_table(["Name", "Start", "Status", "Actions"])`, one row per competition with
  `id="competition-<id>"`: the name, `local_time(starts_at)`, `competition_status_badge(status)`,
  and in the actions cell the `actions_menu` with **Edit** (Upcoming) and **Cancel competition**
  (Upcoming, In progress), only with the setting and an active subject. A row with no entry has an
  empty actions cell, which the phone card hides.
- Opening it changes nothing. 200; 404 for a subject that is not offered.

### 2. `GET /teacher/competitions/new`: the add form (manage)

Query: `subject`, `status`, `page`. Checks 1–3 (an active subject only). 200.

- `back_link(<return>, "Back to the competitions")`, `page_heading("Add competition")`, the error
  summary, "Subject: <name>" as text.
- `<form method="post" action="/teacher/competitions">` with hidden `subject`, `status`, `page`;
  `field("name", "Name", required, maxlength 200)`; `date_time_fields("start", "Start", …)` with
  the hidden `time_zone` (the zone the form is shown in, or `UTC`) and the hint "Time zone:
  <zone>"; `form_actions("Save competition", cancel_href=<return>)`.
- `<return>` is `list_path(subject, status, page)`: the page the teacher came from.

### 3. `POST /teacher/competitions`: create (manage)

Form: `subject`, `status`, `page`, `name`, `start_date`, `start_time`, `time_zone`.

- Checks 1–3; the start parsed in `time_zone` (R6); name checked by the service.
- Errors → 400, the form again with the entered values and the same `time_zone`.
- Success → 303 to `list_path(subject, None, <page of the new competition>, anchor=<id>,
  notice=<added>)`: status **All**, at the competition, with "Competition “…” was added".

### 4. `GET /teacher/competitions/{competition_id:int}/edit`: the edit form (manage)

Query: `subject`, `status`, `page`. Checks 1–5.

- **Upcoming** → 200: `back_link`, `page_heading("Edit competition “<name>”")`, "Subject: <name>",
  the form posting to the same path with hidden `subject`, `status`, `page`, filled with the name
  and the start in the teacher's zone; `form_actions("Save competition", cancel_href=<return at
  the competition>)`.
- **Not Upcoming** → 409 refusal page (`pages/teacher/competition_refused.html`):
  `refusal("Edit competition “<name>”?", <reason>, <return at the competition>, "Back to
  competitions")` with the reason:
  - In progress: "“<name>” has already started and can no longer be edited."
  - Cancelled: "“<name>” has been cancelled and can no longer be edited."
  - Finished: "“<name>” has finished and can no longer be edited."

### 5. `POST /teacher/competitions/{competition_id:int}/edit`: save (manage)

Form: `subject`, `status`, `page`, `name`, `start_date`, `start_time`, `time_zone`. Only these are
read; a different subject in the form fails check 4, so a competition never changes subject.

- Checks 1–5 (the refusal as in §4, 409), fields (400), then the service.
- Success → 303 to `list_path(subject, status, <page that now holds it>, anchor=<id>,
  notice=<saved>)`, "Competition “…” was saved". If the status filter no longer shows it, the
  landing rule of §7 applies.

### 6. `GET /teacher/competitions/{competition_id:int}/cancel`: the confirmation (manage)

Query: `subject`, `status`, `page`. Checks 1–5.

- **Upcoming or In progress** → 200: `back_link(<return at the competition>, "Back to the
  competitions")`, then `confirmation(question, consequence, action, "Cancel competition",
  <return at the competition>, hidden={subject, status, page}, back_label="Keep competition")`:
  - question: "Cancel competition “<name>” of <subject name>, starting <local_time>?";
  - consequence: "The competition will be marked Cancelled and stays in the list. It cannot be
    edited, started or restored.".
- **Cancelled** → 409 refusal "Cancel competition “<name>”?" with "“<name>” is already
  cancelled." and **Back to competitions**.
- **Finished** → 409 refusal with "“<name>” has finished and cannot be cancelled.".

### 7. `POST /teacher/competitions/{competition_id:int}/cancel`: cancel (manage)

Form: `subject`, `status`, `page`. Checks 1–5 (refusals as in §6, 409), then the service.

- Success → 303 to the landing (research R13): `list_path(subject, status, <landing page>,
  anchor=<landing row>, notice=<cancelled>)`, "Competition “…” was cancelled". With the filter
  still showing it, the anchor is the competition; otherwise the row that took its place, else the
  row before it, else the empty state.
- An upcoming competition whose start passed meanwhile is cancelled (FR-035).
- A second cancel, also a simultaneous one, gets the "already cancelled" refusal and changes
  nothing.

## Response summary

| Situation | Status |
|---|---|
| Page shown, form or confirmation opened | 200 |
| Change done | 303 to a `GET` page |
| Form shown again with errors | 400 |
| Not a teacher; manage route without the setting | 403 |
| Subject or competition not found | 404 |
| Edit or cancel refused by the status | 409 |
| Cross-site check failed | the existing 403 of the milestone 4 check |

## Changed routes and pages (outside the router)

| Where | Change |
|---|---|
| `app/routers/teacher.py` | the placeholder `competitions_page` is removed; the docstring names the new router |
| `app/main.py` | `include_router(teacher_competitions.router)` |
| `app/services/subjects.py` | `count_subject_uses` counts competitions (FR-039) |
| `/admin/subjects/{id}/delete` | unchanged page; "in use" now also covers competitions |
| `layouts/base.html` | loads `/static/js/time-zone.js` with `defer`, after `loading-feedback.js` |
| `app/core/templates.py` | the `time_zone` context processor; `format_local_time` and `utc_iso` globals |
| `app/routers/admin_components.py`, `pages/admin/components.html` | sample data and sections for the new and changed components |
| `pages/teacher/placeholder.html` | removed: the **Competitions** placeholder was its only user |

## Route table changes (tests)

- **`test_routes.py`**:
  - the exact write list gains `POST /teacher/competitions`,
    `POST /teacher/competitions/{competition_id:int}/edit` and
    `POST /teacher/competitions/{competition_id:int}/cancel`;
  - `MANAGE_PATHS` gains `/teacher/competitions/new` and the edit and cancel paths, which the cast
    teacher (no profile, so no setting) is refused, so the sweep checks the denied roles only;
  - `/teacher/competitions` is swept with the cast teacher allowed.
- **`test_teacher_competitions.py`** checks every route with a real teacher who has the setting,
  one who has not, an administrator and a student, through addresses and submitted forms.
