# Contract: HTTP Routes of a Competition's Questions and Teams

Router `app/routers/teacher_competition_entries.py`, prefix
`/teacher/competitions/{competition_id:int}`, included in `app/main.py`. Every page renders in the
teacher frame with the **Competitions** tab active (`render_teacher(…, "competitions")`). Every
route is `@allow_roles(Role.TEACHER)`. Handlers read every value as a plain string, so no input
gets FastAPI's 422. See [research.md](../research.md) R7–R10.

## Order of checks (every route)

1. **Role** (decorator): not a teacher → 403, the milestone 5 "access denied" page.
2. **Setting** (the eight add and remove routes, first line of the handler, before any value is
   parsed): no **Can manage competitions** → 403, for unknown ids too.
3. **Subject and competition**, as in 12.1: `subject` not offered → 404 "Subject not found"; the
   competition unknown, of another subject, or hidden by a deactivated subject → 404 "Competition
   not found".
4. **Status** (add and remove routes): not **Upcoming** → 409, the refusal below.
5. **Region, question or team** → 404:
   - "Add teams": `region` unknown or deactivated → "Region not found";
   - adding a question: unknown, of another subject, deleted from the bank → "Question not found";
   - adding a team: unknown, deleted, of another region than `region`, or of a deactivated
     institution or region → "Team not found";
   - removing: an id that names no question (team) at all → "Question not found" ("Team not
     found"); a known one that is not in the competition → 303 with the `absent` notice (R10).
6. **The write** repeats steps 2–5 under lock (services contract); its refusals map to the same
   responses.

**Not-found page**: the 12.1 `pages/teacher/competition_not_found.html`, with these new headings
and texts:

- "Region not found" / "This region does not exist, or it is deactivated."
- "Question not found" / "This question does not exist, or it cannot be added to this competition."
- "Team not found" / "This team does not exist, or it cannot be added to this competition."

## Address parameters

| Name | Where | Values | Missing or invalid |
|---|---|---|---|
| `subject`, `status`, `page` | query, form | the competitions list the teacher came from (12.1) | as in 12.1: `subject` not offered → 404; `status` → All; `page` → 1, clamped |
| `p` | query, form | the page of the list this page shows | `parse_page`: 1, clamped to the last page |
| `back` | query, form (add pages, confirmations) | the page of the competition's list to return to | `parse_page` |
| `region` | query, form ("Add teams") | a region id | missing or empty: none chosen, or the only one offered; other → 404 |
| `question`, `team` | form (add) | the id to add | not an id → 404 |
| `notice` | query (the lists and the add pages) | a sealed notice token (R9) | no notice |

**Address builders** (all from looked-up ids and parsed values only):

- `list_path(subject, status, page, anchor=competition_id)`: the competitions list (12.1), the
  back link of both lists.
- `entries_path(kind, competition_id, context, p=1, anchor=None, notice=None)`:
  `/teacher/competitions/17/questions?subject=3&status=upcoming&page=2&p=3&notice=…#question-12`,
  leaving out `status` for All, `page` and `p` when 1, the notice and the anchor when not given.
  `kind` is `questions` or `teams`; the anchor is `question-<id>` or `team-<id>`.
- `add_page_path(kind, competition_id, context, back, p=1, region=None, anchor=None, notice=None)`.

## Routes

### 1. `GET /questions`: the competition's questions (read)

Query: `subject`, `status`, `page`, `p`, `notice`. Checks 1, 3. 200.

- `back_link(list_path(…, anchor=competition), "Back to the competitions")`.
- `page_heading("Questions of “<name>”", action=("Add question", <add page, back=p>))`, the action
  only for a teacher who can make changes (setting and **Upcoming**).
- `details_list`: **Subject** <name>; **Start** `local_time(starts_at)`; **Status**
  `competition_status_badge(status)`.
- The notice, if the token is valid.
- No questions: `empty_state("No questions in this competition yet", "Add questions with Add
  question." | none)`.
- Otherwise `page_navigation(paging, href, "Questions", "Pages, top")`, an
  `<ol class="text-card-list">` of `text_card("Question <id>", id="question-<id>")` with
  `text_box("Question", text)` and `text_box("Reference answer", reference_answer)`, then a
  `row-actions` with `row_note("Deleted from the question bank")` for a deleted one and, for a
  teacher who can make changes, the destructive outline **Remove** link to the confirmation
  (`back=p`); then the bottom navigation.

### 2. `GET /questions/add`: "Add questions" (manage)

Query: `subject`, `status`, `page`, `back`, `p`, `notice`. Checks 1–4. 200.

- `back_link(entries_path("questions", …, p=back), "Back to the questions")`.
- `page_heading("Add questions to “<name>”")`, the notice.
- No listed question in the subject: `empty_state("No questions in this subject yet")`.
- Otherwise the navigation, the subject's listed questions newest first
  (`questions.question_page`), each a text card with its number, and in its `row-actions` either
  `row_note("Already in this competition")` or the secondary outline `post_button` **Add** to
  `POST /questions` with hidden `subject`, `status`, `page`, `back`, `p`, `question`; the bottom
  navigation.

### 3. `POST /questions`: add a question (manage)

Form: `subject`, `status`, `page`, `back`, `p`, `question`. Checks 1–5, then
`competition_entries.add_question`.

- Added → 303 to `add_page_path("questions", …, back, p, anchor=question, notice=added)`.
- Already in → 303 to the same address with `notice=already`.
- Refusals: 403, 404, 409 as above.

### 4. `GET /questions/{question_id:int}/remove`: the confirmation (manage)

Query: `subject`, `status`, `page`, `back`. Checks 1–5. 200:

- `back_link(<the competition's questions at back, at the question>, "Back to the questions")`;
- `confirmation("Remove question <id> from “<name>”?", <consequence>, <POST path>, "Remove",
  <same return>, hidden={subject, status, page, back})`, the consequence "The question stays in
  the question bank and can be added again." or, for a question deleted from the bank, "The
  question was deleted from the question bank and cannot be added again.".

### 5. `POST /questions/{question_id:int}/remove`: remove (manage)

Form: `subject`, `status`, `page`, `back`. Checks 1–5, then `competition_entries.remove_question`.

- Removed → 303 to `entries_path("questions", …, p=<landing page>, anchor=<landing row>,
  notice=removed)` (R11).
- Not in the competition → 303 to `entries_path("questions", …, p=back, notice=absent)`.

### 6. `GET /teams`: the competition's teams (read)

Query: `subject`, `status`, `page`, `p`, `notice`. Checks 1, 3. 200.

- The back link, `page_heading("Teams of “<name>”", action=("Add team", <add page, back=p>))` (the
  action as in §1), the details list and the notice, as in §1.
- No teams: `empty_state("No teams in this competition yet", "Add teams with Add team." | none)`.
- Otherwise the navigation ("Teams 1–10 of 14"), then for each region group on the page a
  `region_group(region_name, total, "region-<id>-p<p>")` holding `data_table(["Team",
  "Educational institution", "Active members", "Actions"])` (the last column only when an action
  or a mark is possible), one row per team with `id="team-<id>"`: the name, the institution, the
  count, and in the actions cell `row_note("(deleted)")` for a deleted team, or the destructive
  outline **Remove** link for a teacher who can make changes. Then the bottom navigation.

### 7. `GET /teams/add`: "Add teams" (manage)

Query: `subject`, `status`, `page`, `back`, `region`, `p`, `notice`. Checks 1–5. 200.

- `back_link(entries_path("teams", …, p=back), "Back to the teams")`,
  `page_heading("Add teams to “<name>”")`, the notice.
- `chained_lists` with one level: `region`, label "Region", placeholder "Choose a region", the
  active regions; carries `subject`, `status`, `page`, `back`; disabled when none is offered.
- Exactly one of:
  - no region offered: `empty_state("No teams yet")`;
  - none chosen: `empty_state("Select a region", "Choose a region in the list above to see its
    teams.")`;
  - no team to list: `empty_state("No teams in this region yet", "Choose another region.")`;
  - the navigation, `data_table(["Team", "Educational institution", "Active members",
    "Actions"])`, rows `id="team-<id>"` with `row_note("Already in this competition")` or the
    **Add** `post_button` to `POST /teams` with hidden `subject`, `status`, `page`, `back`,
    `region`, `p`, `team`; the bottom navigation.

### 8. `POST /teams`: add a team (manage)

Form: `subject`, `status`, `page`, `back`, `region`, `p`, `team`. Checks 1–5, then
`competition_entries.add_team`.

- Added → 303 to `add_page_path("teams", …, back, p, region, anchor=team, notice=added)`.
- Already in → the same with `notice=already`.

### 9. `GET /teams/{team_id:int}/remove`: the confirmation (manage)

Query: `subject`, `status`, `page`, `back`. Checks 1–5. 200: `back_link(…, "Back to the teams")`,
`confirmation("Remove team “<team>” of <institution>, <region> from “<name>”?", "The team and its
members are not changed, and the team can be added again.", <POST path>, "Remove", <return at the
team>, hidden={…})`.

### 10. `POST /teams/{team_id:int}/remove`: remove (manage)

As §5, with `removed` / `absent` notices for the team and the landing of R12.

## Refusal (409)

`pages/teacher/competition_refused.html`, which now takes the link text from the route:

- question: "Change the questions of “<name>”?" or "Change the teams of “<name>”?";
- reason by status:
  - In progress: "“<name>” has already started and its questions (teams) can no longer be
    changed.";
  - Cancelled: "“<name>” has been cancelled and its questions (teams) can no longer be changed.";
  - Finished: "“<name>” has finished and its questions (teams) can no longer be changed.";
- link **Back to the competition** → the competition's questions or teams page at `back`.

The 12.1 refusals keep **Back to competitions**.

## Response summary

| Situation | Status |
|---|---|
| Page shown, add page or confirmation opened | 200 |
| Change done, "already", "absent" | 303 to a `GET` page |
| Not a teacher; manage route without the setting | 403 |
| Subject, competition, region, question or team not found | 404 |
| Change refused by the status | 409 |
| Cross-site check failed | the existing 403 of the milestone 4 check |

## Changed routes and pages (outside the router)

| Where | Change |
|---|---|
| `app/routers/teacher_competitions.py` | the shared helpers become public (`list_path` already is; `parse_id`, `offered_subject`, `find_competition`, `not_found`, the `SUBJECT_NOT_FOUND` and `COMPETITION_NOT_FOUND` texts); `_refused` passes the link text |
| `pages/teacher/competitions.html` | every row has the actions menu: **Edit** (setting, Upcoming, active subject), **Questions**, **Teams**, **Cancel competition** (setting, Upcoming or In progress, active subject), in this order |
| `pages/teacher/competition_refused.html` | the link text is a context value |
| `pages/teacher/team_delete.html` | "The team will be hidden and taken out of every competition that has not finished. It can no longer join new competitions." replaces the first sentence |
| `app/main.py` | `include_router(teacher_competition_entries.router)` |

## Route table changes (tests)

- **`test_routes.py`**: the exact write list gains `POST …/questions`, `POST …/questions/{question_id:int}/remove`,
  `POST …/teams`, `POST …/teams/{team_id:int}/remove`; `MANAGE_PATHS` gains the eight add and
  remove paths; the two list paths are swept with the cast teacher allowed.
- **`test_teacher_competition_entries.py`** checks every route with a teacher who has the setting,
  one who has not, an administrator and a student, through addresses and submitted forms.
