# Research: Questions and Teams of a Competition (Teacher) (Milestone 12.2)

Phase 0 of [plan.md](./plan.md). The spec has no open clarifications; its Assumptions section
settles the points the milestone left open. Each entry below records a design decision, the reason
for it and the alternatives considered.

---

## R1. Two tables: `competition_questions` holds copies, `competition_teams` holds links

**Decision** ([data-model.md](./data-model.md) §1–§2):

- **`competition_questions`**: `id` (primary key, `AUTOINCREMENT` on SQLite), `competition_id`,
  `question_id` (both foreign keys, no `ON DELETE`), `text` and `reference_answer` (the copies,
  `String(QUESTION_FIELD_MAX_LENGTH)`), `added_at`. A unique constraint on
  `(competition_id, question_id)`.
- **`competition_teams`**: primary key `(competition_id, team_id)`, both foreign keys with no
  `ON DELETE`, `added_at`, and an index on `team_id` for the deletion of R7.

**Rationale**:

- **Questions are copied** (FR-007): the competition must keep the text it was built with, and
  milestones 14–15 score answers against that exact text and reference answer. The `question_id`
  stays, because the number shown is the bank id, the "Deleted from the question bank" mark reads
  the bank row's `deleted_at`, and "Already in this competition" compares ids.
- **Teams are not copied** (spec Assumptions): a team is a group of people, not text to answer;
  its current name, institution and member count are what a teacher needs. Deleted teams are kept
  stored (milestone 11.1), so a finished competition can always show them.
- **The order of adding is the `id`** (FR-005): a removed and re-added question gets a new, larger
  id and goes to the end. `AUTOINCREMENT` on SQLite and the sequence on PostgreSQL never hand out a
  smaller id again, as for `questions`.
- **The unique constraint and the primary key** are what stop a second copy or a second link under
  concurrency (FR-035), on both engines.
- **Removing deletes the row**: a removed question or team leaves no trace, because only an
  upcoming competition can lose one, and an upcoming competition has no answers or results to
  keep.

**Alternatives considered**:

- **A `position` column**: needed only for reordering, which is out of scope (FR-053).
- **Linking to the bank without a copy**: a bank edit would change a competition, against FR-007.
- **A soft "removed" flag**: nothing ever reads a removed entry.
- **Copying the team name and institution**: they would go stale after a rename, and the milestone
  does not ask for it.

---

## R2. Every change locks the competition, then checks the status under the lock

**Decision**: the four writes (`add_question`, `remove_question`, `add_team`, `remove_team`) follow
the milestone 12.1 write pattern, in this order:

1. the setting with `lock=True` (`teacher_access.can_manage_competitions`), else `ManageRequired`;
2. the competition `FOR UPDATE` and its subject `FOR SHARE`, both refreshed (the 12.1 `_find`, made
   public as `competitions.lock_competition`), else `CompetitionNotFound`;
3. the status with a fresh clock: not **Upcoming** → `NotChangeable(status)`;
4. the question or the team, under lock (R3, R4), else `EntryNotFound`;
5. the change, then one commit.

Each refusal rolls back first, so no lock outlives it.

**Rationale**: cancelling (12.1) also takes the competition `FOR UPDATE`, so a change and a
cancellation are serialised: whichever commits first is seen by the other. The start is checked
with the clock read under the lock, so an add page opened before the start and sent after it gets
the refusal (FR-034). An insert cannot be made conditional the way 12.1's `UPDATE`s are; the row
lock does the same job. On SQLite the locks render nothing and writers are serialised anyway.

**Alternatives considered**:

- **`INSERT … SELECT … WHERE starts_at > :now`**: conditional, but the "already in" and "not
  found" cases would need extra reads to explain an empty result, and the code would differ from
  every other service.
- **No competition lock**: a cancellation committing between the status check and the insert
  would leave a cancelled competition with a new question.

---

## R3. Adding a question copies the bank row read under lock

**Decision**: after R2 steps 1–3, the question is read `FOR SHARE` and refreshed. It must exist,
not be deleted, and belong to the competition's subject; otherwise `EntryNotFound` (FR-045 step 5).
If a copy already exists, `AlreadyIn`. Otherwise one row is inserted with the bank's `text` and
`reference_answer` as read; an `IntegrityError` on the commit is `AlreadyIn` too.

**Rationale**: `delete_question` and `update_question` (milestone 11) take the question
`FOR UPDATE`, so an edit or a deletion at the same moment either commits first, and the copy holds
the new text or the addition gets "not found", or waits until the addition commits (spec
Assumptions, Edge Cases). The subject needs no check of its own: the competition's subject was
already checked under lock in R2, and a question of that subject is visible with it.

**Alternatives considered**: reusing `questions.get_question`. It checks the subject again under
another lock, in another order, and raises `QuestionNotFound` for a deactivated subject, which R2
already rules out. A small private lookup is clearer.

---

## R4. Adding a team: live, of the region in the address, institution and region active

**Decision**: after R2 steps 1–3, the team, then its institution, then its region are read
`FOR SHARE` and refreshed. The team must exist, be live (`deleted_at IS NULL`) and belong to an
institution of the region named in the form, and that institution and region must be active;
otherwise `EntryNotFound`. Then `AlreadyIn` if linked, else one link is inserted; an
`IntegrityError` is `AlreadyIn`.

A deactivation (an `UPDATE` of the institution or region row) at the same moment either commits
first and is seen, or waits for the addition to commit, as for `teams.create_team`.

**No link check**: the teacher does not have to be linked to the team's institution (FR-023). The
milestone 11.1 docstring in `app/services/teams.py`, "only a team that `reach_team` returns … may be
added to a competition", is replaced by this rule, and `reach_team` is not used.

**Rationale**: competitions are managed across all institutions (Principle IV: "each of them can
manage every competition"), while teams are managed per institution. A competition gathers teams
from everywhere; the institution link governs who edits a team, not who invites it.

**Alternatives considered**: requiring a link. The milestone says the opposite, and a teacher in
Kyiv could then never organise a national round.

---

## R5. Deleting a team takes it out of every competition that is not finished

**Decision**: `teams.delete_team` keeps its checks and its lock order (`reach_team` with Write
takes the team row `FOR UPDATE` first) and, in the same transaction, runs

```sql
DELETE FROM competition_teams
WHERE team_id = :team_id
  AND competition_id IN (SELECT id FROM competitions WHERE stopped_at IS NULL)
```

before it commits. The log line becomes `Team deleted: id=%d members=%d competitions=%d`, the last
number being the rows removed. Finished competitions keep their link; their teams page shows the
team marked "(deleted)" (FR-040).

**Concurrency** (FR-037): an addition reads the team `FOR SHARE` (R4) and the deletion holds it
`FOR UPDATE`, so they are serialised:

- the addition commits first: the deletion then removes the new link;
- the deletion commits first: the addition sees `deleted_at` and gets "not found".

No deadlock: the addition takes the competition, then the team; the deletion takes the team and
never a competition row. Deleting `competition_teams` rows takes no lock on the referenced
`competitions` rows on PostgreSQL.

**Who may**: the teacher with Write access who deletes the team, with or without **Can manage
competitions** (FR-040). This is the one exception to "only upcoming competitions are editable" and
"a cancelled competition never changes again", as the constitution (v2.1.0, Principle IV) now says.

**Alternatives considered**:

- **Keeping the link and hiding deleted teams on read**: every reader (here, milestones 13–15)
  would need the filter, and a cancelled competition's list would still "contain" the team.
- **Removing the link from finished competitions too**: their record must stay complete
  (milestone 15).
- **A database trigger**: engine-specific, and invisible in the service.

---

## R6. Deleting or editing a question, and deactivating, change nothing

**Decision**: `questions.delete_question`, `questions.update_question`,
`institutions.set_institution_active` and `regions.set_region_active` are not changed (FR-039,
FR-042). The milestone 11 delete confirmation keeps its wording. Only the docstring of
`app/services/questions.py` gains a line: a competition keeps its copy.

**Rationale**: copies (R1) make the bank independent of competitions; deactivation only hides
things in pickers, and milestone 13 decides what a deactivated team's students may do.

---

## R7. The pages: one router for both lists, under the competition

**Decision**: a new router `app/routers/teacher_competition_entries.py` with prefix
`/teacher/competitions/{competition_id}`. Ten routes ([contracts/http-routes.md](./contracts/http-routes.md)):

| | Questions | Teams |
|---|---|---|
| List (read) | `GET …/questions` | `GET …/teams` |
| Add page | `GET …/questions/add` | `GET …/teams/add` |
| Add | `POST …/questions` | `POST …/teams` |
| Remove confirmation | `GET …/questions/{question_id}/remove` | `GET …/teams/{team_id}/remove` |
| Remove | `POST …/questions/{question_id}/remove` | `POST …/teams/{team_id}/remove` |

All are `@allow_roles(Role.TEACHER)`; the add and remove routes (eight) are *manage* routes. The
helpers they share with the 12.1 router (`list_path`, `_query`, `_parse_id`, `_offered`,
`_competition`, the not-found page) become public names in `app/routers/teacher_competitions.py`
and are imported, so both routers build the same addresses.

**Rationale**: the two lists share their context, their refusals, their notices and their access
order; one module keeps them side by side without growing the 12.1 router past 1,000 lines. Both
pages belong to the **Competitions** tab, so they render with `render_teacher(…, "competitions")`.

**Alternatives considered**: adding the routes to `teacher_competitions.py` (too large), or one
router per list (half of each would be the same helpers).

---

## R8. Address parameters: the list context, the list's own page, the way back

**Decision**: three kinds of values travel in every address and form of this milestone:

| Name | Meaning | Missing or invalid |
|---|---|---|
| `subject`, `status`, `page` | the competitions list the teacher came from, exactly as in 12.1 (the menu links already append them) | `subject` not offered → 404; `status` → All; `page` → `parse_page` |
| `p` | the page of the list the page itself shows: the competition's questions or teams, "Add questions", "Add teams" | `parse_page`, clamped to the last page |
| `back` | on the add pages and remove confirmations: the page of the competition's list to return to | `parse_page` |
| `region` | on "Add teams" | missing: none chosen (or the only region); unknown or deactivated → 404 |

**`entries_path(kind, competition_id, context, p=1, anchor=None, notice=None)`** and
**`add_path(…)`** build every return address from looked-up and parsed values only, as 12.1's
`list_path` does. Anchors are `#question-<id>` and `#team-<id>`.

**Rationale**: keeping `subject`, `status` and `page` with their 12.1 meaning means the actions
menu needs no change in how it builds links, and every back link to the competitions list reuses
`list_path` (FR-004). `p` keeps each page bookmarkable; `back` implements the spec's assumption
that the add pages lead back to the page of the competition's list the teacher came from.

**Alternatives considered**: a sealed "return" token (opaque, unbookmarkable); renaming the
context to `list_page` (would change 12.1's addresses).

---

## R9. Notices after a change travel sealed, as in 12.1

**Decision**: one purpose, `competition-entry-notice`, 10-minute lifetime, payload
`{"competition": <id>, "question" | "team": <id>, "outcome": "added" | "already" | "removed" |
"absent"}`. The texts are built when the page is shown:

| Outcome | Question | Team | Style |
|---|---|---|---|
| `added` | "Question 12 was added to “Spring round”" | "Team “Comets” was added to “Spring round”" | success |
| `already` | "Question 12 is already in “Spring round”" | "Team “Comets” is already in “Spring round”" | info |
| `removed` | "Question 12 was removed from “Spring round”" | "Team “Comets” was removed from “Spring round”" | success |
| `absent` | "Question 12 is not in “Spring round”" | "Team “Comets” is not in “Spring round”" | info |

The question's number is its id; the team's name is read from the `teams` row, deleted or not. A
token that is tampered with, expired, of another competition or of an unknown outcome shows no
notice and is not an error.

**Rationale**: no competition or team name enters an address or a log (FR-048), and the pattern is
the one 12.1 and 11.1 already use.

---

## R10. "Is not in" on removal, "not found" for unknown ids

**Decision**: on the remove confirmation and the remove action, after the access checks:

- an id that names no bank question (or no team) at all → 404 "Question not found" ("Team not
  found");
- a known question or team that is not in the competition → 303 to the competition's list with the
  `absent` notice (FR-036). The `GET` changes nothing; it only redirects;
- otherwise the confirmation (200) or the removal (303 with `removed`).

A question deleted from the bank, or a deleted team, that is still in the competition can be
removed (FR-045 step 5).

**Rationale**: FR-036 asks for the notice on a repeated removal; a stale confirmation link opened
after another teacher removed the entry deserves the same answer, not a confusing 404.

---

## R11. The competition's questions list

**Decision**: `competition_entries.question_page(session, competition, p)` returns one page of
`competition_questions` rows ordered by `id`, with each row's bank `deleted_at` (one join), 10 per
page through `Paging.build`. Each question is a `text_card("Question 12", id="question-12")` with
the copied text and reference answer in two `text_box`es; a deleted one has
`row_note("Deleted from the question bank")` in its `row-actions`, before **Remove** when shown.

**Landing after a removal**: the index the question had in the ordered list before the change;
after it, the row now at that index, else the one before it, else the empty state. The page is
`index // PAGE_SIZE + 1`, so a page that empties leads to the previous one (FR-032). This is 12.1's
`landing` with a list of ids; it moves to `app/services/paging.py` as `landing_index` so both
services share it.

---

## R12. The competition's teams list, grouped by region

**Decision**: `competition_entries.team_page(session, competition, p)`:

1. one query: the competition's links joined with `teams`, `institutions` and `regions`;
2. sorted in Python by `(region.name_key, region.id, team.name_key, team.id)`, as every list of the
   project is sorted, so both engines agree;
3. the per-region totals counted over the whole list;
4. sliced to the page; consecutive rows of the same region on the page form one `RegionGroup`
   (`region_name`, `total`, `rows`);
5. the active members of the page's teams counted in one grouped query (R13).

The page renders one `region_group` per group (R15), so a region that continues from the previous
page shows its header again with the same total (FR-011). A deleted team's row has
`row_note("(deleted)")` in its actions cell.

**Alternatives considered**: sorting with `ORDER BY` (each engine's collation differs; the project
sorts names in Python), and paging regions instead of teams (the milestone pages teams).

---

## R13. "Number of active members", counted in one query

**Decision**: a new `teams.count_active_members(session, team_ids) -> dict[int, int]`: memberships
joined through enrolment, class, institution and region, all active, grouped by team. It is the
same chain `list_active_members` uses (milestone 11.1 research R6), so a team shows the number its
own page lists. A team with none counts 0 and can be added (FR-027).

**Rationale**: one query for a page of ten teams, not ten.

---

## R14. "Add teams": every active region, then its addable teams

**Decision**:

- **The Region list**: `regions.list_active_regions(session)` (new: active regions, sorted by
  `name_key`, then id), through `chained_lists` with one level, label "Region", placeholder
  "Choose a region", carrying the context and `back` as hidden fields and no `p`, so choosing a
  region opens the first page (FR-024). The only region is chosen when exactly one is offered.
- **The list**: `competition_entries.addable_teams(session, region_id, p)`: live teams of the region's active
  institutions, sorted by `(name_key, id)`, 10 per page, each with its institution's name and its
  active-member count; the competition's linked team ids mark "Already in this competition".
- **Empty states**: no region offered → "No teams yet"; none chosen → "Select a region" with "Choose
  a region in the list above to see its teams."; no team to list → "No teams in this region yet"
  with "Choose another region.".

"Add questions" reuses `questions.question_page(session, subject_id, p)` (milestone 11: listed
questions, newest first) and the competition's question ids.

---

## R15. One new component, the region group; the menu wording changes

**Decision** ([contracts/components.md](./contracts/components.md)):

- **`region_group(name, total, heading_id)`** in a new `components/group.html`: a bordered box
  with an `h2` header "Kyiv · 14 teams" ("1 team" for one) over the `data_table` the page writes
  inside the `{% call %}`. On a phone the table's rows become labelled cards inside the box, as
  everywhere. The section is labelled by its header.
- **The actions menu** is unchanged as a component. The competitions list now gives every row a
  menu: **Questions** and **Teams** for every teacher on every listed competition; **Edit** and
  **Cancel competition** keep their 12.1 rules (setting, status, active subject). Entry order:
  **Edit**, **Questions**, **Teams**, **Cancel competition**.
- **The refusal page** `competition_refused.html` takes its link text from the route, so the new
  refusals read **Back to the competition**.
- **UI guidelines**: the "Menus" wording pattern changes as FR-051 says; the region group gets its
  section; the row-note examples gain "Already in this competition", "Deleted from the question
  bank" and "(deleted)".

**"(deleted)" and the badge rule**: the guidelines say "never … '(deactivated)'" for a *status*.
The milestone names "(deleted)" as a mark shown through `row_note`, which is the guidelines' tool
for "this row's action is not available"; a deleted team in a finished competition is exactly
that. The guidelines' row-note section says so, so the two rules do not read as a conflict.

---

## R16. Test plan

New modules:

- `tests/integration/test_competition_entries_service.py`: the service on both engines: copies
  and their independence from bank edits and deletions; order of adding; re-adding; the teams
  ordering, grouping and per-region totals across a page break; active-member counts; every
  refusal (setting, competition, status, entry); "already" and "absent"; the controlled clock
  passing the start; concurrent additions and removals, an addition racing a cancellation, and a
  bank deletion or edit racing a question's addition (two sessions, PostgreSQL).
- `tests/integration/test_teacher_competition_entries.py`: every route, end to end, per the spec's
  user stories: pages, texts, empty states, notices, landing, anchors and addresses; access per
  role and setting through addresses and forms; the check order; deactivated subjects; reloads.

Updated modules:

- `test_teacher_competitions.py`: menus on every row, entry order per status and setting, finished
  competitions of a deactivated subject (SC-009 names the replaced 12.1 assertions).
- `test_teacher_teams.py`, `test_team_service.py`: the delete confirmation text; `delete_team`
  removing links from upcoming, in-progress and cancelled competitions and keeping finished ones,
  and a deletion racing a team's addition (two sessions, PostgreSQL); `count_active_members`.
- `test_region_service.py`: `list_active_regions`.
- `test_routes.py`: the four new writes; the eight manage paths in `MANAGE_PATHS`; the two read
  paths swept with the cast teacher allowed.
- `test_migrations.py`: the new revision on both engines, stairway and drift.
- `test_form_contract.py` + `form_contract.json`: the new forms.
- `test_component_gallery.py`, `test_page_patterns.py`: the region group; the refusal link text.
- `tests/conftest.py`: `add_competition_question` and `add_competition_team` seeders, and
  `make_competition` with `stopped_at` already supported.

Browser behaviour (the region list without JavaScript, the region group on a phone) is checked by
hand or with an ad hoc Playwright run ([quickstart.md](./quickstart.md) §4).
