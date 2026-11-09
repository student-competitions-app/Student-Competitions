# Research: Entering a Team's Answers (Teacher) (Milestone 12.3)

Phase 0 of [plan.md](./plan.md). The spec has no open clarifications; its Assumptions section
settles the points the milestone left open. Each entry below records a design decision, the reason
for it and the alternatives considered.

---

## R1. One table, `team_answers`: a row only for an answered question

**Decision** ([data-model.md](./data-model.md) §1):

- **`team_answers`**: `competition_id`, `team_id`, `competition_question_id`, `text`. Primary key
  `(competition_id, team_id, competition_question_id)`.
- **A composite foreign key** `(competition_id, team_id)` → `competition_teams`, and a foreign key
  `competition_question_id` → `competition_questions.id`, none with `ON DELETE`.
- **A check constraint** `text <> ''`: a row exists only for an answered question.
- **An index** on `competition_question_id`, for the foreign-key check when a competition's
  question is removed (12.2).
- **No author and no time** columns (FR-023).

**Rationale**:

- **A row means "answered"** (FR-016, FR-017): emptying a field deletes the row, so the progress
  (FR-009) is a plain count of rows, and milestone 14 scores exactly the rows that exist.
- **The composite foreign key to `competition_teams`** makes "an answer of a team that is not in
  the competition" impossible in the database, on both engines. It also stops `delete_team` or the
  12.2 `remove_team` from silently orphaning answers: they must delete the answers first (R7).
- **The primary key** is one answer per question per team (FR-022), under concurrency too. Its
  leading columns serve the reads: one team's sheet (`competition_id, team_id`) and the progress
  of a page of teams (`competition_id`, `team_id IN …`).
- **Nothing names a person and nothing is timed** (FR-023): the answers are the team's, not
  personal data, so data erasure (milestones 8–9) has nothing to erase here.

**Alternatives considered**:

- **A row per question with an empty text for "not answered"**: every save would have to create
  the missing rows, and "answered" would be a condition, not a count.
- **A composite foreign key `(competition_id, competition_question_id)` →
  `competition_questions(competition_id, id)`**, so the database also checks that the question is
  the competition's: it needs a new unique constraint on `competition_questions`, which SQLite can
  only add by rebuilding the table. The save checks it under lock (R3), and the questions of an
  **In progress** competition cannot change (12.2), so the service guarantee is enough.
- **`saved_at` / `saved_by`**: the milestone forbids both (FR-023).

---

## R2. An answer is keyed by the competition's copy of the question

**Decision**: `team_answers.competition_question_id` refers to `competition_questions.id`, the
copy made when the question was added (12.2), not to the bank's `questions.id`.

**Rationale**: the team answers the text it is shown (FR-015), which is the copy; milestone 14
scores against the copy's text and reference answer. The copy's `id` is also the order of the
sheet (12.2 R1), and it identifies the answer field in the form (R9).

**Alternatives considered**: the bank `question_id`, unique per competition too. It would tie the
answer to a bank row that may be edited or deleted, and the answer could not join to the copy
without the competition.

---

## R3. The save: one service write, every check under lock, in the spec's order

**Decision**: `team_answers.save_answers(session, teacher_id, competition_id, subject_id, team_id,
raw_answers)` runs, in one transaction:

1. the competition `FOR SHARE` and its subject `FOR SHARE`, both refreshed
   (`competitions.lock_competition(…, share=True)`), else `CompetitionNotFound`;
2. the status with a fresh clock: not **In progress** → `AnswersClosed(status)`;
3. the team `FOR SHARE`, then its link to the competition (`competition_teams`) `FOR UPDATE`, then
   its institution and region `FOR SHARE`: unknown, deleted, not in the competition, or of a
   deactivated institution or region → `TeamNotFound`;
4. the questions: every id in `raw_answers` must be one of the competition's copies, else
   `QuestionNotFound`;
5. the teacher's access: `teacher_access.reach_institution(…, write=True, lock=True)`;
   `NotReachable` or `WriteRequired` → `AnswersDenied`;
6. the texts (R5): any invalid → `InvalidAnswers(errors)`;
7. the change (R4), then one commit.

Each refusal rolls back first, so no lock outlives it. The router checks steps 1–2 and the role
before calling, as every 12.x router does, and maps each error to its page (R8).

**Rationale**:

- **The order is the spec's** (FR-025): role (the router), subject and competition, status, team
  and questions, access, and only then the lengths. A deleted team of a **Read**-access institution
  is "not found"; a cancelled competition with a team of an unlinked institution is the refusal.
- **The competition is read `FOR SHARE`, not `FOR UPDATE`**: cancelling (12.1) and stopping (a
  later 12.x) take it `FOR UPDATE`, so a save and a cancellation are serialised and the save sees
  the status as it is when it stores (FR-026); but saves of different teams of one competition do
  not wait for each other, which matters once students save in milestone 13.
- **The team before its link, both before the institution**: `delete_team` (11.1, 12.2) locks the
  team `FOR UPDATE` first, then deletes its links. Taking the team first here, `FOR SHARE`, means a
  deletion and a save never hold each other's next lock: whichever comes first finishes, and the
  other sees it (FR-028).
- **The link `FOR UPDATE`** serialises two saves of the same team (R4).
- **The institution and region before the teacher's link**: "not found" for a deactivated one must
  win over "access denied" (FR-025 step 4 before step 5); `reach_institution` would answer
  `NotReachable` for both.

**Alternatives considered**:

- **`lock_competition` as it is (`FOR UPDATE`)**: simplest, but it would make every save in a
  competition wait for every other.
- **Checks in the router only**: a cancellation, a deletion or a lowered link committed between the
  check and the write would go unseen.

---

## R4. Last save wins: the save replaces the named answers, as one change

**Decision**: under the link's `FOR UPDATE` (R3 step 3), the save reads the team's stored answers in
the competition and, for each question it names:

- an empty text (after cleaning): the row is deleted if there is one;
- a text equal to the stored one: nothing;
- any other text: the row is inserted or updated.

A question the save does not name keeps its row (spec Assumptions). A save that changes nothing
writes nothing, and the teacher still gets the notice. The service returns how many questions are
answered and how many changed; one log line carries them with the ids.

**Rationale**:

- **Last save wins** (FR-024): a save stores every answer of its page, emptied ones included, with
  no version check, no warning and no refusal.
- **Never a mix** (FR-024, SC-006): two saves of the same team queue on the link row, and the
  second reads the answers the first committed (PostgreSQL's read committed takes a new snapshot
  per statement), so the result is exactly the second save's.
- **Writing only what changed** keeps the rows of unchanged answers as they are, which milestone 14
  can rely on when it decides what to score again.

**Alternatives considered**:

- **Delete every answer of the team, then insert**: simpler, but it rewrites every row on every
  save, and an omitted question would lose its answer.
- **An optimistic version check that refuses a stale save**: the milestone asks for no refusal.

---

## R5. Cleaning an answer: the question bank's rules, an empty answer allowed

**Decision**: a new pure module `app/schemas/answer.py`:

- `ANSWER_MAX_LENGTH = QUESTION_FIELD_MAX_LENGTH` (2,000);
- `clean_answer(raw, number) -> str`: line endings become `\n`, a NUL character is refused, the
  text is trimmed; an empty result is `""` (not answered); more than 2,000 code points is refused;
- the messages, with the field's label as their subject: "Answer to question 3 can be at most 2,000
  characters." and "Answer to question 3 cannot contain a null character.".
- `InvalidAnswer(message)`.

**Rationale**: FR-018 asks for the question bank's rules and error wording (milestone 11 R4, the
`clean_question_field` order: line endings, NUL, trim, length). The only difference is that an
empty answer is valid. The NUL rule is not in the milestone, but PostgreSQL cannot store the
character, so the bank's refusal is kept, with the same wording pattern. The messages follow the
bank's "The question text can be at most 2,000 characters." (spec Assumptions).

**Alternatives considered**: reusing `clean_question_field` with a new field name: its messages
are a fixed table, and an empty value is an error there.

---

## R6. Write access to the team's institution, read on every request

**Decision**:

- **The sheet and the save** need **Write** to the team's institution, through
  `teacher_access.reach_institution(…, write=True)` (with `lock=True` in the save). A teacher who
  is not linked, or only with **Read**, gets 403, the milestone 5 "access denied" page, raised as
  `AccessDenied(Role.TEACHER)` by the router.
- **The team answers page** lists the competition's teams whose institution is in
  `teacher_access.list_reachable_institutions(session, teacher_id)`: linked, with an active
  institution in an active region. Each row's level comes from that list: **Write** →
  **Enter answers**, **Read** → the row note "Read access".
- **No Can manage competitions check** anywhere: every teacher may enter the answers of their
  **Write** institutions (FR-002).

**Rationale**: `teacher_access` is the one authority for a teacher's reach (milestone 9 D5), and
both functions read the link and the statuses on every call, so unlinking or lowering takes effect
on the next request (FR-013, FR-027). Using the reachable list for the page drops the teams of
deactivated institutions and regions with no extra condition (FR-005).

**Alternatives considered**: a new `reach_competition_team` in `teacher_access`. Its only caller
would be this service, and it would have to return "not found" and "access denied" separately, so
it would split back into the two checks above.

---

## R7. Deleting a team deletes its answers in every competition that has not finished

**Decision**: `teams.delete_team` keeps its checks and lock order and, before it deletes the team's
links to competitions with `stopped_at IS NULL`, deletes the team's `team_answers` in those same
competitions. Its log line gains the number of answers deleted (`answers=%d`). The 12.2
`competition_entries.remove_team` and `remove_question` are unchanged: they act only on
**Upcoming** competitions, which have no answers (answers are entered only while **In progress**,
and a competition never becomes **Upcoming** again); the foreign keys would refuse the removal if
one ever had.

**Rationale**: FR-028 and the product requirements' **Team** section. The composite foreign key
(R1) makes the order compulsory. A save waiting on the team's share lock (R3) sees the deletion
and answers "not found"; a save that came first is deleted with the rest. **Finished**
competitions keep the team and its answers for the results of milestone 15.

**Alternatives considered**: `ON DELETE CASCADE` from `competition_teams`: the project uses no
cascades (12.2 R1), and a cascade would also fire for a finished competition if anything ever
deleted its link.

---

## R8. The pages: a new router under the competition, reusing the 12.2 helpers

**Decision**: a new router `app/routers/teacher_team_answers.py`, prefix
`/teacher/competitions/{competition_id:int}`, three routes ([contracts/http-routes.md](./contracts/http-routes.md)):

- `GET /answers`: the team answers page (every teacher);
- `GET /answers/{team_id:int}`: the answer sheet (Write);
- `POST /answers/{team_id:int}`: the save (Write).

From `teacher_competition_entries` it imports `ListContext` and two helpers made public:
`find_context` (today `_found`: the context and the competition, or the not-found page) and
`render_competition_page` (today `_render`). From `teacher_competitions` it imports the helpers
12.2 already uses (`not_found`, `redirect`, `teacher_id`, `settings_of`, `parse_id`, the texts).

Responses: 200 for a page; 303 after a save; 403 for the role and for access; 404 for the subject,
the competition, the team or a question; 409 for the status; 400 for answers that are too long.

**Rationale**: the pages belong to the **Competitions** tab and use the same competitions-list
context, back links, not-found page and refusal page as 12.2. A separate router keeps the 948-line
12.2 router from growing, as 12.2 did for 12.1.

**Alternatives considered**: adding the routes to `teacher_competition_entries.py`; a top-level
`/teacher/answers/…` address without the competition: the competition is the page's context and
the first thing checked.

---

## R9. The sheet's form: one field per question, `answer-<copy id>`

**Decision**:

- **Each answer field** is a `textarea` with `id` and `name` `answer-<competition_question_id>`
  (`answer-41`). The error summary links to the same id.
- **The save** reads the context fields (`subject`, `status`, `page`, `back`) as `Form` strings, as
  in 12.2, and the answers through a small async dependency, `answer_fields(request)`, which awaits
  `request.form()` (Starlette caches it, so the body is parsed once) and returns every field whose
  name starts with `answer-`. The handler itself stays a plain `def`, so its database calls run in
  the thread pool like every other route's.
- **Parsing**: `answer-` followed by an id (`parse_id`) → that question; any other `answer-…` name,
  or the same question twice, is "Question not found" (404), and nothing is saved (FR-025 step 4).

**Rationale**: a name per question ties each text to its question without relying on the order of
the fields, and a crafted form naming another competition's question is caught by the id (FR-025).
The cross-site check is the existing header rule (`Sec-Fetch-Site`, then `Origin`, milestone 5
D7), which runs before any route; the spec's "valid token" means that check.

**Alternatives considered**:

- **Two parallel lists, `question` and `answer`**: plain `Form` lists with no dependency, but the
  pairing depends on the order of the fields and needs a rule for unequal lengths.
- **An `async def` handler**: the synchronous session would then block the event loop.

---

## R10. Addresses: the list context, the list's page, the way back

**Decision**: as in 12.2 (R8 there):

- `subject`, `status`, `page`: the competitions list the teacher came from, carried through every
  page, form, refusal and redirect of this milestone (FR-004); missing → the 12.2 fallback.
- `p`: the page of the team answers page.
- `back`: on the sheet and in its form, the page of the team answers page to return to. Missing or
  not a number: the page that holds the team in the teacher's list, found with the same listing
  (spec Assumptions).
- `notice`: the sealed notice after a save (R12).

The team answers page's rows are anchored `team-<id>`; the sheet's back link is
`…/answers?<context>&p=<back>#team-<id>`. **Enter answers** links to
`…/answers/<team>?<context>&back=<current page>`.

**Rationale**: the same shapes as 12.2, built by the same `_address` helper, from looked-up ids and
parsed values only.

**Alternatives considered**: always computing the team's page instead of carrying `back`: it would
not be "the page the teacher came from" if the list changed meanwhile.

---

## R11. The team answers page: the reachable teams, grouped by region, with their progress

**Decision**: `team_answers.answer_team_page(session, teacher_id, competition_id, p)`:

1. the teacher's reachable institutions (R6), as `{institution_id: AccessLevel}`;
2. the competition's live teams whose institution is in that map, from the 12.2 `_team_entries`
   (made public as `competition_entries.team_entries`), sorted by region, then team, ignoring case;
3. per-region totals over those teams only (FR-007), the page sliced and grouped by region with the
   12.2 grouping, extracted as `competition_entries.group_by_region(entries, p, make_row)`, which
   `team_page` then calls too;
4. the active members of the page's teams (`teams.count_active_members`), and their answered counts
   in one grouped query (`team_answers.count_answered`), and the competition's question count.

Each row is an `AnswerTeamRow`: the team's id, name, institution, active members, `answered`,
`questions` and `can_write`. The page reports `linked` (the reachable list is not empty), so the
template picks the empty state (FR-012).

**Rationale**: one query for the entries, as in 12.2; the filter is a set lookup in Python, so the
order and the totals are the 12.2 ones restricted to the listed teams. The progress is counted when
the page is shown (FR-009), in one query for the page.

**Alternatives considered**: filtering in SQL with a join on `teacher_institutions`: the access
level and the "linked to nothing" case would need a second query anyway, and the sorting is in
Python already.

---

## R12. The notice after a save travels sealed; the sheet is shown again by a redirect

**Decision**: after a save, a 303 to the sheet (`…/answers/<team>?<context>&back=<back>&notice=…`)
with a sealed token, purpose `team-answers-notice`, 10-minute lifetime, payload
`{"competition": <id>, "team": <id>, "outcome": "saved"}`. The sheet shows "Answers of “<team>”
were saved" (success) when the token is valid, fresh and of this competition and team, with the
team's name read then. A save with nothing changed shows the same notice.

**Rationale**: Post/Redirect/Get, so a reload never repeats the save (FR-030); the notice texts are
built when the page is shown, as in 12.1 and 12.2, so no name reaches an address or a log line.

**Alternatives considered**: rendering the sheet straight from the `POST` with a 200: a reload
would send the save again.

---

## R13. Answers that are too long: the sheet again, with what was typed

**Decision**: on `InvalidAnswers`, the router renders the sheet with 400: every field holds the text
as it was sent (not cleaned), each invalid one its message, and the error summary under the heading
lists them in the order of the questions, each linking to `#answer-<id>`. Nothing is saved
(FR-019). The questions are read again for this page, after the service's rollback.

**Rationale**: the milestone 11 and 12.1 form pattern (`values`, `errors`, `error_summary` with an
`order`), and 400 as for any invalid form in this project.

**Alternatives considered**: keeping the cleaned texts: trimming what the teacher typed would be a
surprise on a page that saved nothing.

---

## R14. The refusal for a competition that is not In progress

**Decision**: the 12.1 refusal page (`pages/teacher/competition_refused.html`), 409, with:

- the question "Enter answers for “<name>”?";
- the reason by status: **Upcoming** "“<name>” has not started yet, so its answers cannot be entered
  yet.", **Cancelled** "“<name>” has been cancelled, so its answers can no longer be entered.",
  **Finished** "“<name>” has finished, so its answers can no longer be entered.";
- the link **Back to competitions** to the competitions list the teacher came from, at the
  competition, and the back link "Back to the competitions", as the 12.1 edit refusal.

The team answers page, the sheet and the save all show it (FR-026).

**Rationale**: the milestone's texts and the 12.1 pattern; the page already takes both link texts
from the route (12.2).

---

## R15. Two new patterns: the answer sheet and the placeholder

**Decision** ([contracts/components.md](./contracts/components.md)):

- **The answer sheet**, `components/answer_sheet.html`, macro `answer_sheet(items, action, hidden,
  submit_label="Save answers")`: a `<form method="post">` with the hidden fields, an
  `<ol class="answer-sheet">` of text cards ("Question 3", the question's text in a `text_box`, then
  the `textarea_field` "Answer to question 3" with the hint "Up to 2,000 characters.", the
  placeholder "Not answered", `maxlength="2000"` and its error), and one primary **Save answers**
  button below the list (`form_actions`). The page puts the `error_summary` under its heading.
- **The placeholder**: `field` and `textarea_field` gain a `placeholder` argument. The guidelines'
  wording patterns gain "Placeholders": only to say that a field is empty ("Not answered"), never
  in place of the label or the hint.
- **CSS**: `.answer-sheet` in `app.css`, tokens only: the list without markers, the cards spaced as
  `.text-card-list`, the field at full width inside the card on every screen.
- **Gallery** (`#answer-sheet`): a sheet of three questions (answered, empty with the placeholder,
  and one with an error), and in `#forms` an empty field with its placeholder, label and hint.
- **Guidelines**: an "Answer sheet" section, the `placeholder` argument under Forms, the
  "Placeholders" wording pattern, "Read access" among the row-note examples, and the sheet's phone
  behaviour.

**Rationale**: FR-034 and Principle II: a new pattern goes into the library, the gallery and the
guidelines before a page uses it. Milestone 13 will give students the same sheet. `maxlength`
follows the question form (milestone 11); the server check is the guarantee, and both count a line
break as one character.

**Alternatives considered**: building the sheet in the page template: forbidden by Principle II.
Passing the placeholder through `attrs`: it works today, but the rule needs a named argument to
document.

---

## R16. The menu entry

**Decision**: in `pages/teacher/competitions.html`, `menu_link("Answers", …/answers?<return_query>)`
after **Teams** and before **Cancel competition**, when `c.status == "in_progress"`, for every
teacher (FR-001, FR-002). The router passes nothing new.

**Rationale**: the menu is the only way in; the status on each row is already derived for the list.

---

## R17. Test plan

New modules:

- `tests/unit/test_answer_schemas.py`: `clean_answer`: line endings, NUL, trimming, empty, 2,000 and
  2,001 code points (also with a trailing space and a Cyrillic text), the messages.
- `tests/integration/test_team_answer_service.py`: the service on both engines: the listing (which
  teams, the order, the per-region totals counting only listed teams, `linked`, the levels, the
  progress, deactivated institutions and regions, a link lowered or removed); the sheet; saving,
  changing, emptying and leaving out questions; trimming and line breaks; too long; every refusal in
  the spec's order with the controlled clock; `delete_team` across **In progress**, **Cancelled**
  and **Finished**; two saves of one team, a save racing a cancellation, a deletion, a lowered link
  and a deactivation (two sessions, PostgreSQL).
- `tests/integration/test_teacher_team_answers.py`: every route end to end, per the user stories
  and the milestone's _Test:_ items 1–16: texts, empty states, notices, back links, anchors, the
  address fallbacks, the phone labels, access per role and level through addresses and forms, the
  check order, reloads and the cross-site check.

Updated modules:

- `test_teacher_competitions.py`: **Answers** in the menu per status and setting, and in order
  (item 1).
- `test_teacher_competition_entries.py`: the **Teams** page shows no **Enter answers** in any status,
  with and without the setting (item 2).
- `test_team_service.py`, `test_teacher_teams.py`: `delete_team` deletes answers in unfinished
  competitions and keeps them in finished ones (item 15).
- `test_competition_service.py`: `lock_competition(share=True)`.
- `test_routes.py`: the save in the exact write list; the two read paths swept with the cast
  teacher allowed (id 1 is "not found", not "access denied").
- `test_migrations.py`: the new revision, stairway and drift, both engines.
- `test_form_contract.py` + `form_contract.json`: the sheet's form (`teacher-team-answers*` cases,
  generated once with `UPDATE_FORM_CONTRACT=1` for those cases only).
- `test_component_gallery.py`, `test_page_patterns.py`: the answer sheet, the placeholder (item 17).
- `tests/conftest.py`: a `save_team_answer` seeder, the only way to give a **Finished** or
  **Cancelled** competition answers.

Browser behaviour (the sheet on a phone, the busy **Save answers** button, the placeholder in both
themes) is checked by hand or with an ad hoc Playwright run ([quickstart.md](./quickstart.md) §4).
