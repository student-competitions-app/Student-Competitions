# Implementation Plan: Entering a Team's Answers (Teacher) (Milestone 12.3)

**Branch**: `012.3-team-answers` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.3-team-answers/spec.md`

## Summary

While a competition is **In progress**, a teacher enters the answers of the teams of their
**Write** institutions, one text answer per question per team, on one answer sheet saved at once; a
**Read** institution's teams show only their progress. **Answers** joins the row menu of an **In
progress** competition for every teacher. The last save wins, and deleting a team deletes its
answers in every competition that has not finished.

**Data** (research R1, R2, [data-model.md](./data-model.md)):

- **One migration** creates `team_answers`: `(competition_id, team_id, competition_question_id)`
  primary key, `text` (1–2,000 characters, never empty). A row exists only for an answered question.
- **A composite foreign key to `competition_teams`** keeps every answer's team in the competition;
  a foreign key to `competition_questions` keys the answer by the competition's copy.
- **Nothing names a person or a time**: answers are not personal data (FR-023).

**The save** (R3–R5, [contracts/services.md](./contracts/services.md)):

- **`app/services/team_answers.py`** (new), `save_answers`: in the spec's order, under lock: the
  competition `FOR SHARE` (a new `share` flag on `competitions.lock_competition`), the status with a
  fresh clock, the team `FOR SHARE` and its link `FOR UPDATE`, the institution and region, the named
  questions, **Write** access (`teacher_access.reach_institution`), the texts; then one commit.
- **Last save wins, never a mix**: the link row lock queues two saves of one team; each save
  deletes emptied answers, writes changed ones and leaves unnamed questions alone.
- **`app/schemas/answer.py`** (new): the question bank's cleaning rules, with an empty answer
  allowed and "Answer to question 3 can be at most 2,000 characters.".
- **`teams.delete_team`** deletes the team's answers before its links in unfinished competitions.

**Reads** (R6, R11): the team answers page lists the competition's live teams whose institution is
in `teacher_access.list_reachable_institutions`, grouped by region with the 12.2 grouping (extracted
as `competition_entries.group_by_region`), with "<answered> of <questions>" counted in one query per
page. The sheet lists every copy in order with the team's saved answer, never the reference answer.

**Routes** (R8–R14, [contracts/http-routes.md](./contracts/http-routes.md)):

- **A new router, `app/routers/teacher_team_answers.py`**, three routes under
  `/teacher/competitions/{competition_id}`: `GET /answers`, `GET /answers/{team_id}`,
  `POST /answers/{team_id}`.
- **Order of checks**: role → subject and competition (404) → status (409) → team and questions
  (404) → **Write** access (403) → lengths (400); no **Can manage competitions** check.
- **The form**: one field per question, `answer-<copy id>`, read through a small async dependency;
  the context (`subject`, `status`, `page`, `back`) as in 12.2. A save redirects (303) to the sheet
  with a sealed notice.
- **The menu**: **Answers** after **Teams** on an **In progress** row, for every teacher. The
  **Teams** page does not change.

**Components first** (R15, [contracts/components.md](./contracts/components.md)): the **answer
sheet** (`components/answer_sheet.html`) and a `placeholder` argument on `field` and
`textarea_field` are added to the library, the gallery and `ui-guidelines.md` (with the
"Placeholders" wording pattern) before the sheet uses them.

**Documents**: the product requirements and the constitution (v2.2.0, PR #48) already state the
rules (FR-035); the UI guidelines and the README are updated in this PR, `milestones.md` on
delivery.

**Tests** (R17): one new unit module and two new integration modules; updates to the competitions,
entries, teams and competition-service tests, the route sweep, the migrations, the form contract,
the gallery and page patterns.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, Alembic, python-multipart, Pico.css v2.1.1 (vendored, not
  edited).
- No new runtime or development dependency, and no new script.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision after `59c636929942`: `team_answers` ([data-model.md](./data-model.md)
  §5).

**Testing**:

- pytest on both engines; the concurrency cases (two sessions) on PostgreSQL only, as in 11.1–12.2.
- New modules:
  - `tests/unit/test_answer_schemas.py`;
  - `tests/integration/test_team_answer_service.py`;
  - `tests/integration/test_teacher_team_answers.py`.
- Updated modules: `test_teacher_competitions`, `test_teacher_competition_entries`,
  `test_team_service`, `test_teacher_teams`, `test_competition_service`, `test_routes`,
  `test_migrations`, `test_form_contract` (+ `form_contract.json`), `test_component_gallery`,
  `test_page_patterns`, `conftest.py` (a `save_team_answer` seeder).
- Browser behaviour (the sheet on a phone, the busy button, the placeholder in both themes) is
  checked by hand or with an ad hoc Playwright run ([quickstart.md](./quickstart.md) §4).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **The team answers page**: the reachable institutions (one query), the competition's teams with
  their institutions and regions (one query, sorted in Python as in 12.2), then for the page's ten
  teams one grouped count of active members and one of answers, and the question count.
- **The sheet**: the team's checks, the copies in order, the team's answers: four short queries.
- **A save**: six short locked reads, one read of the stored answers, and a write per changed
  answer. Saves of different teams of one competition do not wait for each other (R3).

**Constraints**:

- **Check order** exactly as FR-025; access after "not found", lengths last.
- **In progress only, under lock**: the save re-checks the status inside its transaction (FR-026).
- **No JavaScript needed**: the sheet is a plain form; the busy button of 10.1 applies.
- **Stylesheet rules**: tokens only; the milestone 10 and 10.1 stylesheet checks stay green.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.

**Scale/Scope**:

- 1 migration, 1 new model, 1 new schema module, 1 new service module; 3 changed services
  (`competitions`, `competition_entries`, `teams`).
- 1 new router with 3 endpoints; the 12.2 router exposes its helpers.
- 2 new page templates (`competition_answers.html`, the team answers page;
  `team_answer_sheet.html`, the answer sheet); 1 changed
  (`competitions.html`).
- 1 new component file (`answer_sheet.html`), 1 changed (`form.html`), and their CSS; gallery
  sections.
- 2 documents updated (UI guidelines, README); `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.2 is merged and delivered. 12.3 is one end-to-end slice: the menu entry, the team answers page, the sheet and its save, and team deletion, from the menu down to the table. Nothing from later milestones is built: no grading, no stopping, no student view, no LLM, no results (FR-037). | ✅ |
| II. Server-rendered simplicity | Every page is rendered by Jinja on the server with plain `GET` and `POST`; no HTMX partial and no new script. The one async piece is a dependency that awaits the form body; the handlers stay synchronous. No new dependency. | ✅ |
| UI guidelines | Every page is built from the component library with design tokens only. The two new patterns, the answer sheet and the placeholder, are added to the library, the gallery and `ui-guidelines.md` before a page uses them, with the "Placeholders" wording rule (FR-034; R15). No new colour token. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ items 1–17 map to pytest cases on both engines (R17), with the 12.1 controlled clock, and two-session concurrency tests on PostgreSQL. Access tests cover all 3 routes, allowed and denied, per role and access level, through addresses and forms. The replaced 12.2 menu assertions are named (SC-011). No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`; administrators and students get 403 before any id is read. The sheet and the save need **Write** to the team's institution, checked by `teacher_access` in the router and again under lock in the service; **Read** sees only the progress, never an answer, as amended Principle IV (v2.2.0) requires. The team answers page lists only the teams of the teacher's reachable institutions. Competitions of a deactivated subject stay hidden. The one exception, deleting a team, deletes its answers only where Principle IV takes the team out (R7). | ✅ |
| V. Secure authentication & secrets | No change to sign-in, sessions or the cross-site check; every `POST` passes it. The notice uses the existing sealing with a purpose and a 10-minute lifetime (R12). Logs carry ids and counts only; answers are not under the logging ban (v2.2.0), and are not logged anyway. | ✅ |
| VI. LLM evaluation | Not called. Saving answers needs no LLM (Principle VI: "saving answers MUST succeed independently of the LLM"); the rows are what milestone 14 will score, against the copy (R2). | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines and covered by the stairway and drift checks. Answers are entered only while **In progress**, enforced on the server under the competition's share lock (R3). A finished competition keeps its teams' answers when a team is deleted, so no result is orphaned (R7). No `ON DELETE` cascades. The only engine-specific detail is the row locks that render nothing on SQLite, which serialises writers anyway (the 12.1 pattern). | ✅ |
| Stack | Only listed technologies. Pico is restyled only through `app.css`. | ✅ |
| Application Layout | `models/` (one table), `schemas/` (the answer rules), `services/` (business logic), `routers/` (thin), `templates/components/` (the answer sheet), `templates/pages/teacher/` (pages). | ✅ |
| Governance and workflow | The constitution amendment this milestone needs was merged in its own PR before this plan (v2.2.0, PR #48), and the product requirements were updated with the milestone. The UI guidelines and the README are updated in this PR, and `milestones.md` moves 12.3 to Delivered on delivery. The schema change ships with its migration. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: the contracts keep every check server-side, in the spec's order, with **Write** checked
  after "not found" and before the lengths ([http-routes.md](./contracts/http-routes.md) §Order of
  checks), and again under lock ([services.md](./contracts/services.md) §Write).
- **Status**: the only writer of answers checks **In progress** under the competition's share lock;
  the only other writer, `delete_team`, is the constitution's exception and touches only
  competitions that are not finished.
- **Components**: the answer sheet and the placeholder are in [components.md](./contracts/components.md)
  with their gallery sections and guideline changes.
- **Data**: no personal data added; no author or time stored.

## Project Structure

### Documentation (this feature)

```text
specs/012.3-team-answers/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R17
├── data-model.md           # Phase 1: the table, invariants, the migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # the 3 routes, checks, parameters, pages, refusal
│   ├── services.md         # team_answers, answer schema, and the changes to competitions, competition_entries, teams
│   └── components.md       # the answer sheet, the placeholder, guideline changes
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── competition.py           # + TeamAnswer; docstrings of CompetitionTeam, CompetitionQuestion
│   └── __init__.py              # + TeamAnswer
├── schemas/
│   └── answer.py                # NEW: clean_answer, InvalidAnswer, ANSWER_MAX_LENGTH
├── services/
│   ├── team_answers.py          # NEW: answer_team_page, team_page_of, answer_sheet, count_answered, save_answers
│   ├── competitions.py          # lock_competition(share=True); later-milestones docstring
│   ├── competition_entries.py   # team_entries (public), group_by_region, generic RegionGroup
│   └── teams.py                 # delete_team deletes answers in unfinished competitions
├── routers/
│   ├── teacher_team_answers.py  # NEW: 3 endpoints, answer_fields dependency, notice, refusal
│   ├── teacher_competition_entries.py  # find_context, render_competition_page, _address public
│   └── admin_components.py      # gallery sample data for the answer sheet
├── templates/
│   ├── components/
│   │   ├── answer_sheet.html    # NEW: answer_sheet
│   │   └── form.html            # field / textarea_field: placeholder
│   └── pages/
│       ├── admin/components.html                # answer sheet section; placeholder in forms
│       └── teacher/
│           ├── competitions.html                # Answers in the menu (In progress)
│           ├── competition_answers.html         # NEW: the team answers page
│           └── team_answer_sheet.html           # NEW: the answer sheet
├── static/css/app.css           # .answer-sheet
└── main.py                      # include the new router

migrations/versions/2026_11_<dd>_<rev>_team_answers.py   # NEW

tests/
├── unit/test_answer_schemas.py                    # NEW
├── integration/test_team_answer_service.py        # NEW
├── integration/test_teacher_team_answers.py       # NEW
└── (updated) test_teacher_competitions, test_teacher_competition_entries, test_team_service,
    test_teacher_teams, test_competition_service, test_routes, test_migrations,
    test_form_contract + form_contract.json, test_component_gallery, test_page_patterns,
    conftest.py

docs/requirements/ui-guidelines.md   # Answer sheet, placeholder, Placeholders wording, Read access row note
README.md                            # entering a team's answers
```

**Structure Decision**: the existing single FastAPI application layout. The pages belong to the
**Competitions** tab and reuse the 12.2 router's context, address builder, not-found and refusal
pages; the save follows the 12.1/12.2 write pattern (lock, status with a fresh clock, entry checks,
conditional change) with a share lock on the competition; the team answers page follows the 12.2
**Teams** page; the sheet follows the milestone 11 form pattern (values, errors, error summary).

## Complexity Tracking

No constitution violations to justify. The row locks that render nothing on SQLite follow the 12.1
pattern. The async form dependency (R9) is the smallest way to read one field per question while
keeping the handler synchronous.
