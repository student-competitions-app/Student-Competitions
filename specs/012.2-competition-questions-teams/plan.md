# Implementation Plan: Questions and Teams of a Competition (Teacher) (Milestone 12.2)

**Branch**: `012.2-competition-questions-teams` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.2-competition-questions-teams/spec.md`

## Summary

Every competition gets two lists of its own, its questions and its teams, opened from the row's
actions menu, which every teacher now sees on every row. A teacher with **Can manage competitions**
adds and removes questions and teams while the competition is **Upcoming**. Questions are copied
when added; deleting a team takes it out of every competition that has not finished.

**Data** (research R1, [data-model.md](./data-model.md)):

- **One migration** creates `competition_questions` (a copy of `text` and `reference_answer`, the
  bank `question_id`, `added_at`; the `id` is the order of adding) and `competition_teams`
  (`(competition_id, team_id)` primary key, `added_at`, a `team_id` index).
- **A unique constraint and a primary key** stop a second copy or link under concurrency.
- **Teams are linked, not copied**: their current name, institution and member count are shown.

**Writes** (R2–R5, [contracts/services.md](./contracts/services.md)):

- **`app/services/competition_entries.py`** (new): four writes in the 12.1 order: the setting
  under lock, the competition `FOR UPDATE` (the 12.1 `_find`, now `lock_competition`), the status
  with a fresh clock, the question or team `FOR SHARE`, then the insert or delete. Cancelling takes
  the same competition lock, so a change and a cancellation never interleave.
- **`teams.delete_team`** also deletes the team's links to competitions with `stopped_at IS NULL`,
  in its own transaction. Its `FOR UPDATE` on the team and the addition's `FOR SHARE` serialise a
  deletion racing an addition (FR-037). This is the exception constitution v2.1.0 allows.
- **No link check for teams**: any live team of an active institution in an active region can be
  added (R4); the 11.1 docstring that said otherwise is replaced.

**Reads** (R11–R14): the questions page in the order of adding, with the bank's `deleted_at` for
the mark; the teams page sorted in Python by region, then team, sliced into `RegionGroup`s with
per-region totals; active members counted for a page in one grouped query
(`teams.count_active_members`); "Add questions" reuses `questions.question_page`; "Add teams" lists
`regions.list_active_regions` and a region's addable teams.

**Routes** (R7–R10, [contracts/http-routes.md](./contracts/http-routes.md)):

- **A new router, `app/routers/teacher_competition_entries.py`**, 10 routes under
  `/teacher/competitions/{competition_id}`: two lists (read), and for each kind an add page, an
  add, a remove confirmation and a remove (manage).
- **Order of checks**: role → setting (before any value is read) → subject and competition (404) →
  status (409) → region, question or team (404).
- **Addresses**: `subject`, `status`, `page` keep their 12.1 meaning (the competitions list); `p`
  is the page's own list page; `back` is the page of the competition's list the add pages and
  confirmations return to; `region` on "Add teams". Notices travel sealed (R9).
- **The competitions list**: every row gets the menu (**Edit**, **Questions**, **Teams**,
  **Cancel competition**); the 12.1 helpers the new router needs become public.

**Components first** (R15, [contracts/components.md](./contracts/components.md)): the **region
group** (`components/group.html`) is added to the library, the gallery and `ui-guidelines.md`; the
guidelines' "Menus" and "Row notes" wording changes. The refusal page takes its link text from the
route.

**Documents** (FR-051): the product requirements ("Competition statuses", "Team", "Question") and
the UI guidelines are updated in this PR; the constitution was amended beforehand (v2.1.0, PR #46).
The 11.1 team delete confirmation gets its new sentence.

**Tests** (R16): two new integration modules (service, routes); updates to the competitions and
teams tests, the route sweep, the migrations, the form contract, the gallery and page patterns.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, Alembic, Pico.css v2.1.1 (vendored, not edited).
- No new runtime or development dependency, and no new script.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision after `72e46cb10175`: `competition_questions` and `competition_teams`
  ([data-model.md](./data-model.md) §5).

**Testing**:

- pytest on both engines; the concurrency cases (two sessions) on PostgreSQL only, as in 11.1 and
  12.1.
- New modules:
  - `tests/integration/test_competition_entries_service.py`;
  - `tests/integration/test_teacher_competition_entries.py`.
- Updated modules: `test_teacher_competitions`, `test_teacher_teams`, `test_team_service`,
  `test_region_service`, `test_paging` (unit), `test_templates` (unit), `test_routes`,
  `test_migrations`, `test_form_contract` (+ `form_contract.json`), `test_component_gallery`,
  `test_page_patterns`, `conftest.py` (seeders for a competition's questions and teams).
  `test_competition_service` stays green unchanged (the landing now goes through
  `paging.landing_index`).
- Browser behaviour (the region list without JavaScript, the region group on a phone) is checked by
  hand or with an ad hoc Playwright run ([quickstart.md](./quickstart.md) §4).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **The teams list**: one query for the competition's links with their teams, institutions and
  regions, sorted and sliced in Python, then one grouped count for the page's ten teams. A
  competition holds tens of teams; hundreds stay fast.
- **"Add teams"**: one query for the region's live teams of active institutions, one grouped count
  for the page, one query for the competition's team ids.
- **A write**: four short locked reads and one insert or delete.

**Constraints**:

- **Access before existence**: the setting is checked before any id is read (FR-045).
- **Upcoming only, under lock**: every add and remove re-checks the status inside its transaction
  (FR-034).
- **No JavaScript needed**: the region list has its **Show** button; every action is a form.
- **Stylesheet rules**: tokens only; the milestone 10 and 10.1 stylesheet checks stay green.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.

**Scale/Scope**:

- 1 migration, 2 new models, 1 new service module; 4 changed services (`competitions`, `teams`,
  `regions`, `paging`) and 1 docstring (`questions`).
- 1 new router with 10 endpoints; the 12.1 router exposes its helpers.
- 5 new page templates (the two lists, the two add pages, one remove confirmation); 3 changed
  (`competitions.html`, `competition_refused.html`, `team_delete.html`).
- 1 new component file (`group.html`) and its CSS; gallery sections.
- 3 documents updated (product requirements, UI guidelines, README); `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.1 is merged and delivered. 12.2 is one end-to-end slice: the menu entries, both lists, adding and removing, and the team-deletion rule, from the menu down to the tables. Nothing from later milestones is built: no stopping, no ordering of questions, no student view, no results (FR-053). | ✅ |
| II. Server-rendered simplicity | Every page is rendered by Jinja on the server with plain `GET` and `POST`; no HTMX partial and no new script (the existing `auto-submit.js` drives the region list). No new dependency. | ✅ |
| UI guidelines | Every page is built from the component library with design tokens only. The one new pattern, the region group, is added to the library, the gallery and `ui-guidelines.md` before a page uses it; the "Menus" and "Row notes" wording is updated in the guidelines (FR-050, FR-051; R15). No new colour token. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ list map to pytest cases on both engines (R16), with the 12.1 controlled clock, and two-session concurrency tests on PostgreSQL. Access tests cover all 10 routes, allowed and denied, per role and setting, through addresses and forms. The replaced 12.1 and 11.1 assertions are named (SC-009). No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`; administrators and students get 403. Every teacher reads both lists; adding and removing need **Can manage competitions**, checked first in the router and again under lock in the service, with no per-competition rights. Only an upcoming competition's questions and teams change (R2). The one exception, deleting a team, follows the amended Principle IV (v2.1.0): the teacher with Write access who deletes it takes it out of every competition that is not finished, and finished ones keep it (R5). Competitions of a deactivated subject stay hidden unless finished; finished ones show both lists read-only. Teams of any institution can be added, whether or not the teacher is linked to it, as the milestone asks (R4). This does not widen access to students: the lists show a team's name, institution and member count, never a member's name. | ✅ |
| V. Secure authentication & secrets | No change to sign-in, sessions or the cross-site check; every `POST` passes it. Notices use the existing sealing with a purpose and a 10-minute lifetime (R9). Logs carry ids and counts only, never a competition name, team name or question text (FR-048). | ✅ |
| VI. LLM evaluation | Not touched. The copies are what milestone 14 will score against, as Principle VI's "question text and the teacher's reference answer as inputs" requires. | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines and covered by the stairway and drift checks. Questions are copied, so a competition's record never changes when the bank does; deleted teams stay linked to finished competitions, so "deletions MUST NOT silently orphan or destroy historical competition results" holds (R1, R5). No `ON DELETE` cascades. The only engine-specific detail is the row locks that render nothing on SQLite, which serialises writers anyway (R2, the 12.1 pattern). | ✅ |
| Stack | Only listed technologies. Pico is restyled only through `app.css`. | ✅ |
| Application Layout | `models/` (two tables), `services/` (business logic), `routers/` (thin), `templates/components/` (the region group), `templates/pages/teacher/` (pages). | ✅ |
| Governance and workflow | The constitution amendment this milestone needs was merged in its own PR before this plan (v2.1.0). The product requirements, the UI guidelines and the README are updated in this PR, and `milestones.md` moves 12.2 to Delivered on delivery. The schema change ships with its migration. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: the contracts keep every check server-side, in the spec's order, with the setting
  before ids ([http-routes.md](./contracts/http-routes.md) §Order of checks), and again under lock
  ([services.md](./contracts/services.md) §Writes).
- **Status**: every write checks **Upcoming** under the competition lock; the only other writer of
  `competition_teams`, `delete_team`, is the constitution's exception and touches only
  competitions that are not finished.
- **Components**: the region group is in [components.md](./contracts/components.md) with its
  gallery section and guidelines change.
- **Data**: no personal data added; the links name teams, not members.

## Project Structure

### Documentation (this feature)

```text
specs/012.2-competition-questions-teams/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R16
├── data-model.md           # Phase 1: the two tables, invariants, the migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # the 10 routes, checks, parameters, pages, refusals
│   ├── services.md         # competition_entries, and the changes to competitions, teams, regions, paging
│   └── components.md       # the region group, the menu on every row, guideline changes
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── competition.py           # + CompetitionQuestion, CompetitionTeam
│   └── __init__.py              # + both exports
├── services/
│   ├── competition_entries.py   # NEW: lists, add/remove questions and teams, landing
│   ├── competitions.py          # lock_competition (public _find); landing via paging
│   ├── teams.py                 # count_active_members; delete_team withdraws links; docstring
│   ├── regions.py               # list_active_regions
│   ├── paging.py                # landing_index
│   └── questions.py             # docstring only
├── routers/
│   ├── teacher_competition_entries.py  # NEW: 10 endpoints, notices, refusals
│   ├── teacher_competitions.py  # shared helpers public; refusal link text
│   └── admin_components.py      # gallery sample data for the region group and the menus
├── templates/
│   ├── components/
│   │   └── group.html           # NEW: region_group
│   └── pages/
│       ├── admin/components.html                   # region group section; menu variants
│       └── teacher/
│           ├── competitions.html                   # a menu on every row
│           ├── competition_questions.html          # NEW
│           ├── competition_questions_add.html      # NEW
│           ├── competition_teams.html              # NEW
│           ├── competition_teams_add.html          # NEW
│           ├── competition_entry_remove.html       # NEW: both confirmations
│           ├── competition_refused.html            # link text from the route
│           └── team_delete.html                    # the new sentence
├── static/css/app.css           # .region-group
└── main.py                      # include the new router

migrations/versions/2026_11_<dd>_<rev>_competition_questions_and_teams.py   # NEW

tests/
├── integration/test_competition_entries_service.py   # NEW
├── integration/test_teacher_competition_entries.py   # NEW
└── (updated) test_teacher_competitions, test_teacher_teams, test_team_service,
    test_region_service, unit/test_paging, unit/test_templates, test_routes, test_migrations,
    test_form_contract + form_contract.json, test_component_gallery, test_page_patterns,
    conftest.py

docs/requirements/product-requirements.md   # statuses, Team, Question (FR-051)
docs/requirements/ui-guidelines.md          # Menus, Row notes, Region group
README.md                                   # the competition's questions and teams
```

**Structure Decision**: the existing single FastAPI application layout. The pages belong to the
**Competitions** tab and reuse the 12.1 router's address helpers, refusals and not-found page; the
service follows the 12.1 write pattern (setting, lock, status, conditional change); the add pages
follow milestone 11.1's "Add students" (a chained list, a table, **Add** or a row note on each
row).

## Complexity Tracking

No constitution violations to justify. The row locks that render nothing on SQLite follow the 12.1
pattern (R2). The team-deletion exception to the Upcoming-only rule is allowed by the amended
constitution (v2.1.0), not a deviation.
