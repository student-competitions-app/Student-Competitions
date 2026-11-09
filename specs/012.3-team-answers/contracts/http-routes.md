# Contract: HTTP Routes of a Competition's Team Answers

Router `app/routers/teacher_team_answers.py`, prefix `/teacher/competitions/{competition_id:int}`,
included in `app/main.py`. Every page renders in the teacher frame with the **Competitions** tab
active (`render_teacher(…, "competitions")`). Every route is `@allow_roles(Role.TEACHER)`. Handlers
read every value as a plain string, so no input gets FastAPI's 422. See
[research.md](../research.md) R8–R14.

## Order of checks (every route)

1. **Role** (decorator): not a teacher → 403, the milestone 5 "access denied" page, before any id
   is read.
2. **Subject and competition**, as in 12.2 (`find_context`): `subject` not offered → 404 "Subject
   not found"; the competition unknown, of another subject, or hidden by a deactivated subject →
   404 "Competition not found". No `subject` → the 12.2 fallback.
3. **Status**: not **In progress** → 409, the refusal below.
4. **Team and questions** (sheet and save) → 404:
   - the team unknown, deleted, not in the competition, or of a deactivated institution or region →
     "Team not found";
   - the save names a question that is not one of the competition's, names one twice, or has an
     `answer-…` field whose suffix is not an id → "Question not found".
5. **Access to the team** (sheet and save): the teacher not linked to the team's institution, or
   linked with **Read** only → 403 "access denied".
6. **The answers** (save): any answer too long or holding a NUL character → 400, the sheet again
   (R13).
7. **The write** repeats steps 2–6 under lock (services contract); its refusals map to the same
   responses.

There is no **Can manage competitions** check on any route of this router.

**Path ids that are not numbers** match no route and get the application's plain 404 before step 1,
as in 12.1 and 12.2. Numeric ids of any length match; a `team_id` above `MAX_ID` is "Team not
found".

**Not-found page**: the 12.1 `pages/teacher/competition_not_found.html`, with these new headings and
texts:

- "Team not found" / "This team does not exist, or it is not in this competition."
- "Question not found" / "This question is not in this competition."

## Address parameters

| Name | Where | Values | Missing or invalid |
|---|---|---|---|
| `subject`, `status`, `page` | query, form | the competitions list the teacher came from (12.1) | as in 12.2: no `subject` → the competition's own, All, the page holding it; `subject` not offered → 404 |
| `p` | query (team answers page) | the page of the team answers page | `parse_page`: 1, clamped to the last page |
| `back` | query, form (sheet, save) | the page of the team answers page to return to | the page holding the team in the teacher's list (R10) |
| `notice` | query (sheet) | a sealed notice token (R12) | no notice |
| `answer-<id>` | form (save) | one per question: the text typed | see step 4 |

**Address builders** (from looked-up ids and parsed values only, through the 12.2 `_address`):

- `answers_path(competition_id, context, p=1, anchor=None)`:
  `/teacher/competitions/17/answers?subject=3&status=in_progress&page=2&p=3#team-31`.
- `sheet_path(competition_id, team_id, context, back, notice=None)`:
  `/teacher/competitions/17/answers/31?subject=3&back=3&notice=…`.

## Routes

### 1. `GET /answers`: the team answers page (every teacher)

Steps 1–3. Then `team_answers.answer_team_page(session, teacher, competition, parse_page(p))`.

- **Title** "Answers of “<name>”"; `back_link` "Back to the competitions" →
  `list_path(subject, status, page, anchor=competition)`; under the heading the `details_list`
  Subject, Start (`local_time`), Status (badge), as on the 12.2 pages. No heading action.
- **Empty states**, the first that applies (FR-012): `not listing.linked` → "You are not linked to
  any educational institution"; no listed team → "No teams from your educational institutions". No
  hint for either (spec Assumptions).
- **List**: page navigation "Teams" above and below (`answers_path` prefix); one `region_group` per
  region on the page (`heading_id` `region-<id>-p<page>`), each a `data_table` with the columns
  **Team**, **Educational institution**, **Active members**, **Answered**, **Actions**. Row
  `id="team-<id>"`; **Answered** "<answered> of <questions>"; the actions cell **Enter answers**
  (`link_button`, secondary outline small) → `sheet_path(…, back=current page)` when `can_write`,
  otherwise `row_note("Read access")`.
- No **Add team**, no **Remove**, for anyone (FR-011). Opening it changes nothing.

### 2. `GET /answers/{team_id:int}`: the answer sheet (Write)

Steps 1–5. Then `team_answers.answer_sheet(session, teacher, competition, team)`.

- **Title** "Answers of “<team>” in “<competition>”"; `back_link` "Back to the answers" →
  `answers_path(…, p=back, anchor=team)`; under the heading the team's institution
  (`details_list` "Educational institution").
- **Notice**: "Answers of “<team>” were saved" (success) for a valid token (R12).
- **No questions**: `empty_state("No questions in this competition")`, no form (FR-021).
- **Otherwise** the `answer_sheet` (components contract §1) posting to
  `/teacher/competitions/<id>/answers/<team>`, with the hidden `subject`, `status`, `page`, `back`;
  every question in the competition's order, "Question <n>", its copied text, the field
  `answer-<copy id>` "Answer to question <n>" with the saved answer or empty with "Not answered";
  no reference answer anywhere (FR-015, FR-016).

### 3. `POST /answers/{team_id:int}`: save (Write)

Form: `subject`, `status`, `page`, `back` (plain `Form` strings) and every `answer-…` field (the
`answer_fields` dependency, R9). Steps 1–4 (the questions parsed here), then
`team_answers.save_answers(…)`, which repeats the checks under lock.

| Outcome | Response |
|---|---|
| Saved (also with nothing changed) | 303 → `sheet_path(…, back, notice=<saved>)` |
| `CompetitionNotFound` | 404 "Competition not found" |
| `AnswersClosed(status)` | 409, the refusal |
| `TeamNotFound` | 404 "Team not found" |
| `QuestionNotFound` | 404 "Question not found" |
| `AnswersDenied` | 403 "access denied" |
| `InvalidAnswers(errors)` | 400, the sheet with every field as sent, each error at its field, the `error_summary` in question order |

Nothing is saved in any case but the first. Reloading the page after the 303 repeats nothing.

## Refusal (409)

`pages/teacher/competition_refused.html`, unchanged, with:

- question: "Enter answers for “<name>”?";
- reason by status:
  - Upcoming: "“<name>” has not started yet, so its answers cannot be entered yet.";
  - Cancelled: "“<name>” has been cancelled, so its answers can no longer be entered.";
  - Finished: "“<name>” has finished, so its answers can no longer be entered.";
- `back` → `list_path(subject, status, page, anchor=competition)`, with `back_text` **Back to
  competitions** and `back_link_text` "Back to the competitions", as the 12.1 edit refusal.

## Response summary

| Situation | Status |
|---|---|
| Page shown | 200 |
| Answers saved | 303 to the sheet |
| Answers too long | 400 |
| Not a teacher; no **Write** access to the team's institution | 403 |
| Subject, competition, team or question not found | 404 |
| Competition not **In progress** | 409 |
| Cross-site check failed | the existing 403 of the milestone 4 check, before the route |

## Changed routes and pages (outside the router)

| Where | Change |
|---|---|
| `app/routers/teacher_competition_entries.py` | `_found` → public `find_context`; `_render` → public `render_competition_page`; `_address` and `_page_prefix` public for the new builders |
| `pages/teacher/competitions.html` | **Answers** after **Teams**, before **Cancel competition**, on an **In progress** row, for every teacher (R16) |
| `app/main.py` | `include_router(teacher_team_answers.router)` |

The **Teams** page (12.2) does not change.

## Route table changes (tests)

- **`test_routes.py`**: the exact write list gains
  `POST /teacher/competitions/{competition_id:int}/answers/{team_id:int}`; the read set swept with
  the cast teacher allowed (`ENTRY_READ_PATHS`) gains `…/answers` and `…/answers/{team_id:int}` (id 1
  names no competition, so both answer 404, not 403).
- **`test_teacher_team_answers.py`** checks every route with teachers with **Write**, **Read**, mixed
  and no links, with and without the setting, an administrator and a student, through addresses
  and submitted forms.
