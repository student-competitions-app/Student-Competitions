# Contract: HTTP Routes of Finishing and Grading

Phase 1 of [plan.md](../plan.md). Decisions: [research.md](../research.md) R7, R8, R11, R12.

Every route is `@allow_roles(Role.TEACHER)`, reads its values as plain strings (no FastAPI 422),
and on success redirects with a 303, so a reload never repeats a change. Every `POST` passes the
existing cross-site request check.

## Order of checks: finishing and grading (FR-043)

1. **Role** (decorator): not a teacher → 403, before any id is read.
2. **Setting**: `require_manage`, first thing in the handler → 403 for a teacher without **Can
   manage competitions**, also for unknown ids.
3. **Subject and competition** → 404: finishing as the 12.1 cancel routes (`offered_subject`,
   `find_competition`); grading through the 12.2 `find_context` (with its no-`subject` fallback).
   A finished competition of a deactivated subject is found; any other competition of one is not.
4. **Status** → 409: finishing needs **In progress** (the finish refusal); grading needs **Finished**
   (the grading refusal).
5. **Team and questions** (grading sheet and save) → 404 "Team not found" for an unknown team or one
   not in the competition (a `team_id` above `MAX_ID` too); "Question not found" for a save naming a
   copy that is not the competition's, one the team did not answer, the same copy twice, or a
   `grade-…` suffix that is not an id. Deleted teams and teams of a deactivated institution or
   region are found.
6. **Grades** (save) → 400, the sheet again with every value as sent and the errors.
7. **The write** repeats 2–6 under lock; its refusals map to the same responses.

## Order of checks: the Answers pages (FR-041, changed from 12.3)

1. Role → 403. 2. Subject and competition → 404 (`find_context`). 3. Status: **Upcoming** or
**Cancelled** → the 12.3 refusal (409) on every page and save; **In progress** → the pages open and
a save is accepted; **Finished** → the pages open read-only, and a save gets the 12.3 refusal "has
finished" (409). 4. Team → 404 (unknown, deleted, not in the competition, deactivated institution or
region). 5. Access: not linked → 403; **Read** → the read-only sheet, a save 403; **Write** → the
answer sheet while **In progress**, the read-only sheet when **Finished**. No setting check.

## Address parameters

| Name | Where | Values | Missing or invalid |
|---|---|---|---|
| `subject`, `status`, `page` | query, form | the competitions list the teacher came from (12.1) | as in 12.2 |
| `p` | query (Grades page) | the page of the Grades page | `parse_page`: 1, clamped to the last |
| `show` | query, form (Grades page, grading sheet, save) | `ungraded` for **Ungraded only** | **All teams** |
| `back` | query, form (grading sheet, save) | the Grades page's page to return to | the page holding the team under the current filter (`grades.team_page_of`), 1 if it is not listed |
| `notice` | query (grading sheet) | a sealed `grades-notice` token | no notice |
| `grade-<copy id>` | form (save) | one per answered question: the grade typed | see step 5 |

**Address builders** (from looked-up ids and parsed values only, through the 12.2 `address`):

- `grades_path(competition_id, context, show, p=1, anchor=None)`:
  `/teacher/competitions/17/grades?subject=3&status=finished&page=2&show=ungraded&p=2#team-31`.
- `grading_sheet_path(competition_id, team_id, context, show, back, notice=None)`:
  `/teacher/competitions/17/grades/31?subject=3&show=ungraded&back=2&notice=…`.
- `filter_href(competition_id, context, show)`: `grades_path(…, p=1)`.
- The 12.2 `address` gains an optional `show` argument, left out at **All teams**.

## Routes

### 1. `GET /teacher/competitions/{competition_id}/grades`: the Grades page (setting)

Template `pages/teacher/competition_grades.html`. Heading "Grades of “{name}”"; details list:
Subject, Start (local time), Status (badge); then the line "Graded {n} of {total} teams" (counted
noun per spec Assumptions). Then the filter links **All teams** / **Ungraded only** (label "Show"),
the page navigation ("Teams 1–10 of 25", "Pages, top" and "Pages, bottom"), the region groups with
the table: **Team**, **Educational institution**, **Active members**, **Answered** ("4 of 10"),
**Graded** ("3 of 4"), **Score** ("17"), **Actions**: the row note "(deleted)" for a deleted team,
in the actions cell as on the Teams page, then **Grade answers** (secondary outline small, to
`grading_sheet_path(…, back=current page)`). Rows have `id="team-<id>"`. Empty states: no team in
the competition → "No teams in this competition" (whatever the filter); **Ungraded only** with no
team listed → "All teams are graded". Back link "Back to the competitions" to the list at the
competition. Opening it changes nothing.

### 2. `GET /teacher/competitions/{competition_id}/grades/{team_id}`: the grading sheet (setting)

Template `pages/teacher/team_grading_sheet.html`. Heading "Grade answers of “{team}” in “{name}”";
under it the details list with the Educational institution, followed by the row note "(deleted)"
for a deleted team. Then the error summary (after a refused save), the notice (after a save), and:

- a competition with no questions → "No questions in this competition", no form;
- a team with no answers → "“{team}” gave no answers, so there is nothing to grade", then the
  questions read-only (`grading_sheet` renders no form when nothing is answered);
- otherwise the `grading_sheet`: every question with "Reference answer" and "Answer to question
  {n}", a field "Grade for question {n}" under each answered one, "Not answered" under the others,
  and **Save grades**.

Back link "Back to the grades" to `grades_path(…, show, p=back, anchor=team if is_listed)`.
Opening it changes nothing.

### 3. `POST /teacher/competitions/{competition_id}/grades/{team_id}`: save (setting)

Form: the context (`subject`, `status`, `page`), `show`, `back`, and `grade-<copy id>` per answered
question. Calls `grades.save_grades`; success → 303 to `grading_sheet_path(…, notice=token)` with
"Grades of “{team}” were saved", also when nothing changed. Invalid grades → 400, the sheet with
every value as sent, the error "Enter a whole number from 0 to 10." at each and the summary in
question order. `ManageRequired` → 403; the other errors as in the order of checks.

### 4. `GET /teacher/competitions/{competition_id}/answers` (changed, 12.3)

- Opens on **In progress** and **Finished** (`_open` refuses only **Upcoming** and **Cancelled**).
- Every row has an action: **Enter answers** (Write, **In progress**) or **View answers**
  (otherwise), both to the 12.3 `sheet_path`. The "Read access" row note is gone.
- On **Finished**, the table gains **Graded** and **Score** after **Answered**, from `grade_counts`.

### 5. `GET /teacher/competitions/{competition_id}/answers/{team_id}` (changed, 12.3)

- **Write** and **In progress** → the 12.3 answer sheet, unchanged.
- **Read** and **In progress** → `pages/teacher/team_answers_read_only.html`: heading "Answers of
  “{team}” in “{name}”", the institution, the info notice "You have Read access to “{institution}”,
  so you cannot change these answers.", then `answers_read_only(items, grades=False)`.
- **Finished** (Read or Write) → the same template, no access notice, "Score: {score}" and "Graded
  {graded} of {answered} answers" under the institution, then `answers_read_only(items,
  grades=True)`.
- A competition with no questions → "No questions in this competition".
- Back link "Back to the answers" as in 12.3.

### 6. `POST /teacher/competitions/{competition_id}/answers/{team_id}` (unchanged, 12.3)

A **Finished** competition keeps the 12.3 refusal (409) before the team is read; **Read** access →
403. Its form dependency is now `prefixed_fields("answer-")` (research R9), same behaviour.

### 7. `GET /teacher/competitions/{competition_id}/finish`: the confirmation (setting)

Template `pages/teacher/competition_finish.html`, the 12.1 cancel pattern with
`confirmation(…, kind="primary")`: question "Finish competition “{name}” of {subject}, started
{local start}?", consequence "The competition will be marked Finished. Its answers can no longer be
entered or changed, and it cannot be cancelled or restarted. Its answers can then be graded.",
button **Finish competition**, link **Keep in progress** to the list at the competition. Hidden
fields: `subject`, `status`, `page`. Not **In progress** → the finish refusal.

### 8. `POST /teacher/competitions/{competition_id}/finish`: finish (setting)

As the cancel action: the checks, then `competitions.finish_competition(…, status_filter)`;
success → 303 to `list_path(subject, status_filter, landing.page, landing.competition_id,
notice)` with "Competition “{name}” was finished". `NotFinishable` → the finish refusal for the
status it carries; `ManageRequired` → 403; `CompetitionNotFound` → 404.

## Refusals (409)

`pages/teacher/competition_refused.html`, back link "Back to the competitions", link **Back to
competitions** to the list at the competition:

| Action | Question | Upcoming | In progress | Cancelled | Finished |
|---|---|---|---|---|---|
| Finish | Finish competition “{name}”? | “{name}” has not started yet and cannot be finished. | — | “{name}” has been cancelled and cannot be finished. | “{name}” has already finished. |
| Grade | Grade answers of “{name}”? | “{name}” has not started yet, so its answers cannot be graded. | “{name}” is still in progress, so its answers cannot be graded until it is finished. | “{name}” has been cancelled, so its answers cannot be graded. | — |

The 12.3 answer refusals are unchanged.

## Response summary

| Route | 200/303 | 400 | 403 | 404 | 409 |
|---|---|---|---|---|---|
| `GET …/finish` | confirmation | — | not teacher, no setting | subject, competition | not In progress |
| `POST …/finish` | 303 list | — | not teacher, no setting | subject, competition | not In progress |
| `GET …/grades` | page | — | not teacher, no setting | subject, competition | not Finished |
| `GET …/grades/{team}` | sheet | — | not teacher, no setting | + team | not Finished |
| `POST …/grades/{team}` | 303 sheet | invalid grade | not teacher, no setting | + team, question | not Finished |
| `GET …/answers` | page | — | not teacher | subject, competition | Upcoming, Cancelled |
| `GET …/answers/{team}` | sheet or read-only | — | not teacher, not linked | + team | Upcoming, Cancelled |
| `POST …/answers/{team}` | 303 sheet | too long | not teacher, Read, not linked | + team, question | not In progress |

## Changed pages outside the routers

- `pages/teacher/competitions.html`: the menu of research R12; `NOTICES` gains `finished`.
- `pages/teacher/competition_answers.html`: research R7 (§4 above).

## Route table changes (tests)

- `test_routes.py`: the write routes gain `("POST", "/teacher/competitions/{competition_id:int}/finish")`
  and `("POST", "/teacher/competitions/{competition_id:int}/grades/{team_id:int}")`; the teacher read
  sweeps gain `…/finish`, `…/grades` and `…/grades/{team_id:int}` (403 for administrators and
  students; for a teacher without the setting, 403 before any id is read).
- `app/main.py` includes `teacher_grades.router` next to `teacher_team_answers.router`.
