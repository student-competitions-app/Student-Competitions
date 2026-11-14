# Implementation Plan: Finishing a Competition and Grading Its Answers by Hand (Teacher) (Milestone 12.4)

**Branch**: `012.4-finish-and-grade` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.4-finish-and-grade/spec.md`

## Summary

A teacher with **Can manage competitions** finishes an **In progress** competition (a primary,
not destructive, confirmation), then grades every team's answers by hand, one whole number 0–10 per
answer, on one grading sheet per team, from a Grades page that lists every team with **Answered**,
**Graded** and **Score** and can show only the teams still to grade. On the **Competitions** tab,
**Read** access now reads a team's answers; after finishing, the Answers pages are read-only and
show each team's grades and score to the teachers of its institution.

**Data** (research R1, R2, [data-model.md](./data-model.md)):

- **Finishing needs no schema change**: `competitions.stopped_at` and the `one_end` constraint exist
  since 12.1, and `status_of` already derives **Finished**.
- **One migration** adds `team_answers.grade` (`SMALLINT NULL`, check 0–10). `NULL` = not graded.
  No author, no time.

**Finishing** (R1, [contracts/services.md](./contracts/services.md) §`competitions`):
`competitions.finish_competition` mirrors `cancel_competition`: the setting under lock, the
competition `FOR UPDATE`, **In progress** with a fresh clock, a conditional update of `stopped_at`
(the condition the 12.1 contract promised), the 12.1 landing. The 12.3 answer saves hold the
competition `FOR SHARE`, so a finish waits for them and every later save sees **Finished**.

**Grading** (R3–R6, §`grades`):

- **`app/services/grades.py`** (new): `grade_counts` (one grouped query: answered, graded, score per
  team), `grade_team_page` (every team, the 12.2 `team_entries` and `group_by_region`, the
  **Ungraded only** filter), `grading_sheet`, `is_listed`, and `save_grades`: the setting → the
  competition `FOR SHARE` → **Finished** → the team and its link `FOR UPDATE` (deleted and
  deactivated teams found) → each named copy answered by the team → `clean_grade` → one commit.
  Last save wins, never a mix.
- **`app/schemas/grade.py`** (new): digits only, trimmed, 0–10, empty = not graded; "Enter a whole
  number from 0 to 10.". The field is `type="text"` with `inputmode="numeric"` (R4).

**Read access and the Answers pages** (R7): the 12.3 sheet address renders the answer sheet for
**Write** while **In progress**, else the read-only sheet (Read while **In progress** with the access
notice; any reachable team when **Finished**, with grades and score). `answer_sheet` no longer
refuses **Read**; the save still does. The Answers page opens on **Finished**, gets **Graded** and
**Score**, and **View answers** replaces the "Read access" note.

**Routes** (R8, [contracts/http-routes.md](./contracts/http-routes.md)):

- `teacher_competitions.py`: `GET`/`POST /{id}/finish`, as the cancel pair; notice `finished`.
- **`app/routers/teacher_grades.py`** (new): `GET /grades`, `GET /grades/{team_id}`,
  `POST /grades/{team_id}`, each `require_manage` first, then `find_context`, the status (409), the
  team and questions (404), the grades (400). Address parameter `show=ungraded`.
- `teacher_team_answers.py`: `_open` lets **Finished** through for the pages; the sheet route
  chooses the rendering; the form dependency becomes `prefixed_fields` (R9), shared with grades.
- **The menu** (R12): **Edit**, **Questions**, **Teams**, **Answers** (in progress, finished),
  **Grades** (`can_manage`, finished), **Finish competition** (`can_manage`, in progress, not
  destructive), **Cancel competition**.

**Components first** (R13, [contracts/components.md](./contracts/components.md)): `confirmation`
gains `kind="primary"`; `components/grading_sheet.html` (`grading_sheet`, `answers_read_only`);
`components/filter.html` (`filter_links`, `aria-current="true"`). Each goes into the library, the
gallery and `ui-guidelines.md` before a page uses it, with the guideline changes of FR-047.

**Documents**: the constitution v2.3.0 and the product requirements already state the rules
(FR-050); the UI guidelines and the README are updated in this PR, `milestones.md` on delivery.

**Tests** (R15): one new unit module and two new integration modules; updates to the competitions,
team-answers, competition-service and team-answer-service tests, the route sweep, the migrations,
the form contract, the gallery and page patterns, and a `grade_answer` seeder.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, Alembic, python-multipart, Pico.css v2.1.1 (vendored, not
  edited).
- No new runtime or development dependency, and no new script.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision after `b709653d1111`: `team_answers.grade` ([data-model.md](./data-model.md)
  §6), through batch mode on SQLite.

**Testing**:

- pytest on both engines; the concurrency cases (two sessions) on PostgreSQL only, as in 11.1–12.3.
- New modules:
  - `tests/unit/test_grade_schemas.py`;
  - `tests/integration/test_grade_service.py`;
  - `tests/integration/test_teacher_grades.py`.
- Updated modules: `test_teacher_competitions`, `test_teacher_team_answers`,
  `test_team_answer_service`, `test_competition_service`, `test_routes`, `test_migrations`,
  `test_form_contract` (+ `form_contract.json`), `test_component_gallery`, `test_page_patterns`,
  `tests/conftest.py` (a `grade_answer` seeder).
- Browser behaviour (the sheet at 360 px, the digit keypad, the filter links in both themes, the busy
  button) is checked by hand or with an ad hoc Playwright run ([quickstart.md](./quickstart.md) §4).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **The Grades page**: the competition's teams with institutions and regions (one query), the grade
  counts of all its teams (one grouped query), then for the page's ten teams one grouped count of
  active members, and the question count.
- **The grading sheet**: the team and link, the copies in order, the team's answers: three short
  queries.
- **A grade save**: the setting, the competition, the subject, the team and its link (locked
  reads), the copies, the team's rows, and an update per changed grade. Saves of different teams do
  not wait for each other.
- **A finish**: as a 12.1 cancel (two list reads for the landing, one conditional update).

**Constraints**:

- **Check order** exactly as FR-043 (finishing and grading) and FR-041 (Answers pages): the setting
  before any id; access after "not found"; grades last.
- **Status under lock**: the finish and the grade save re-check the status inside their
  transaction; the 12.3 answer save keeps its share lock.
- **No JavaScript needed**: plain forms and links; the busy button of 10.1 applies.
- **Stylesheet rules**: tokens only; the milestone 10 and 10.1 stylesheet checks stay green.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.

**Scale/Scope**:

- 1 migration (1 column, 1 check constraint); 1 new schema module, 1 new service module; 2 changed
  services (`competitions`, `team_answers`).
- 1 new router with 3 endpoints; 2 new endpoints in `teacher_competitions`; `teacher_team_answers`
  changed.
- 4 new page templates (`competition_finish.html`, `competition_grades.html`,
  `team_grading_sheet.html`, `team_answers_read_only.html`); 2 changed (`competitions.html`,
  `competition_answers.html`).
- 2 new component files (`grading_sheet.html`, `filter.html`), 1 changed (`confirmation.html`), and
  their CSS; gallery sections.
- 2 documents updated (UI guidelines, README); `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.3 is merged (PR #50). 12.4 is one end-to-end slice: finishing, the Grades page, the grading sheet and its save, the read-only Answers pages, from the menu down to the table. Nothing from later milestones is built: no student view, no LLM evaluation, no best answers, places or results page (FR-052). | ✅ |
| II. Server-rendered simplicity | Jinja pages with plain `GET` and `POST`; no HTMX partial and no new script. The filter is a pair of links. No new dependency. | ✅ |
| UI guidelines | Pages built from the component library with tokens only. The three new patterns (non-destructive confirmation, grading sheet with its read-only variant, filter links) go into the library, the gallery and `ui-guidelines.md` before a page uses them, and the guideline rules this milestone changes are updated in the same PR (FR-047, FR-048; R13). No new colour token. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ items 1–17 map to pytest cases on both engines (R15), with the 12.1 controlled clock, and two-session concurrency tests on PostgreSQL. Access tests cover the 5 new routes and the changed ones, allowed and denied, per role, setting and access level. The replaced 12.3 assertions are named (SC-011). No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`. Finishing and grading check **Can manage competitions** first in the router and again under lock in the service, for every competition and every team whatever the teacher's links, as amended Principle IV (v2.3.0) says. Grading adds or changes grades only: `save_grades` writes `grade` and nothing else. The Answers pages follow the teacher's links only (Read and Write see the same, only Write enters answers); the setting gives nothing there. Finished competitions of a deactivated subject stay gradable; others stay hidden. | ✅ |
| V. Secure authentication & secrets | No change to sign-in, sessions or the cross-site check; every `POST` passes it. Notices use the existing sealing with a purpose and a 10-minute lifetime. Logs carry ids and counts only; grades and answers are not personal data and are not logged. | ✅ |
| VI. LLM evaluation | Not called. The grade column is the stored grade milestone 14 will propose into and teachers will adjust (R2). | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines, covered by the stairway and drift checks. The status stays derived from the stored start and the stored stop or cancel; finishing writes `stopped_at` once under lock with a conditional update. Grades are persisted; scores and progress are calculated from them and never stored. Answers are entered only while **In progress** and graded only once **Finished**, both enforced under the competition's lock. No `ON DELETE` cascades. The only engine-specific detail is the row locks that render nothing on SQLite (the 12.1 pattern). | ✅ |
| Stack | Only listed technologies. Pico is restyled only through `app.css`. | ✅ |
| Application Layout | `models/` (one column), `schemas/` (the grade rule), `services/` (business logic), `routers/` (thin), `templates/components/` (the new patterns), `templates/pages/teacher/` (pages). | ✅ |
| Governance and workflow | The constitution amendment this milestone needs is already in `main` (v2.3.0, 2026-11-14), and the product requirements were updated with the milestone. The UI guidelines and the README are updated in this PR; `milestones.md` moves 12.4 to Delivered on delivery. The schema change ships with its migration. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: the contracts keep every check server-side, in the spec's order, with the setting
  before any id on every finishing and grading route ([http-routes.md](./contracts/http-routes.md)
  §Order of checks), and again under lock ([services.md](./contracts/services.md) §Write). The
  Answers pages keep `reach_institution` as their only access step.
- **Status**: the only writer of `stopped_at` requires **In progress** under `FOR UPDATE`; the only
  writer of `grade` requires **Finished** under the share lock; the 12.3 writer of `text` keeps
  **In progress** under the share lock, so a finish and a save never interleave.
- **Components**: the three patterns and the guideline changes are in
  [components.md](./contracts/components.md) with their gallery sections.
- **Data**: no personal data added; no author or time stored; nothing derived is stored.

## Project Structure

### Documentation (this feature)

```text
specs/012.4-finish-and-grade/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R15
├── data-model.md           # Phase 1: the grade column, transitions, invariants, the migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # finish, grades, the changed answers routes, checks, refusals
│   ├── services.md         # grade schema, grades service, competitions and team_answers changes
│   └── components.md       # non-destructive confirmation, grading sheet, filter links, guidelines
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   └── competition.py           # TeamAnswer.grade + grade_range; docstrings of Competition, TeamAnswer
├── schemas/
│   └── grade.py                 # NEW: clean_grade, InvalidGrade, GRADE_ERROR
├── services/
│   ├── grades.py                # NEW: grade_counts, grade_team_page, is_listed, grading_sheet, save_grades
│   ├── competitions.py          # finish_competition, NotFinishable; docstring
│   └── team_answers.py          # answer_team_page / answer_sheet: Read access, finished, grades
├── routers/
│   ├── teacher_grades.py        # NEW: 3 endpoints, notice, refusal, addresses
│   ├── teacher_competitions.py  # GET/POST /{id}/finish, FINISH_REFUSALS, NOTICES["finished"]
│   ├── teacher_team_answers.py  # _open lets Finished through; read-only sheet; prefixed_fields
│   ├── teacher_competition_entries.py  # address(show=…)
│   └── admin_components.py      # gallery sample data for the new patterns
├── templates/
│   ├── components/
│   │   ├── confirmation.html    # kind="primary"
│   │   ├── grading_sheet.html   # NEW: grading_sheet, answers_read_only
│   │   └── filter.html          # NEW: filter_links
│   └── pages/
│       ├── admin/components.html                # sections for the three patterns
│       └── teacher/
│           ├── competitions.html                # the menu (R12)
│           ├── competition_finish.html          # NEW: the finish confirmation
│           ├── competition_grades.html          # NEW: the Grades page
│           ├── team_grading_sheet.html          # NEW: the grading sheet
│           ├── team_answers_read_only.html      # NEW: the read-only answer sheet
│           └── competition_answers.html         # View answers, Graded, Score
├── static/css/app.css           # .filter-links, .grade-line
└── main.py                      # include the new router

migrations/versions/2026_11_<dd>_<rev>_answer_grades.py   # NEW

tests/
├── unit/test_grade_schemas.py                     # NEW
├── integration/test_grade_service.py              # NEW
├── integration/test_teacher_grades.py             # NEW
└── (updated) test_teacher_competitions, test_teacher_team_answers, test_team_answer_service,
    test_competition_service, test_routes, test_migrations, test_form_contract +
    form_contract.json, test_component_gallery, test_page_patterns, conftest.py

docs/requirements/ui-guidelines.md   # three patterns; menu, confirmations, wording changes (FR-047)
README.md                            # finishing and grading
```

**Structure Decision**: the existing single FastAPI application layout. Finishing joins the 12.1
router and service beside cancelling, sharing their notice, landing and refusal code. Grading is a
new router and service under the competition, reusing the 12.2 context, addresses, grouping and
not-found page, and the 12.3 form-field reading. The read-only answer sheet stays on the 12.3
address, so every Answers link keeps working.

## Complexity Tracking

No constitution violations to justify. The row locks that render nothing on SQLite follow the 12.1
pattern. The one shared change across routers, `prefixed_fields` (R9), replaces a 12.3 function
rather than copying it.
