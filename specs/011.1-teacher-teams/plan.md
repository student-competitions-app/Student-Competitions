# Implementation Plan: Teams (Teacher) (Milestone 11.1)

**Branch**: `011.1-teacher-teams` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011.1-teacher-teams/spec.md`

## Summary

Teachers put students of one institution together into named teams on a new **Teams** tab, which
works like **Students**. With Write access they create, rename and soft-delete teams and add and
remove members; with Read access they only see them. Memberships are personal data: the profile
lists them, and every path out of the student role erases them. The student consent text version 1
is rewritten in place to say so.

**Data** (research R1–R3, R9, [data-model.md](./data-model.md)):

- **One migration** after `3e32707ed794`:
  - it creates `teams`: an institution, a name and its `name_key`, and a nullable `deleted_at`;
  - it creates `team_memberships`, keyed by `(team_id, user_id)`;
  - it rewrites the stored student consent text version 1, keeping its version and date.
- **Names are unique among live teams, across all institutions**, through a partial unique index on
  `name_key WHERE deleted_at IS NULL`. It is declared for both engines and probed on both with no
  schema drift (R2).
- **Deleting a team sets `deleted_at`** and changes nothing else; its memberships stay.
- **Removing a member deletes the row.**

**Services** (R4–R8, R14, [contracts/services.md](./contracts/services.md)):

- **`teacher_access.reach_team`**: a live team of a reachable institution, with Write when asked,
  and the team row locked first for a change.
- **A new `app/services/teams.py`**:
  - the lookups: the live teams of an institution, the active members (the milestone 9 chain
    filter), the counts, the member ids and a student's teams;
  - the changes: create, rename, soft delete, add and remove.

  Each change reaches the team, and the student where needed, under lock in its own transaction.
  The lock order is team, then user, then class and institution. Adding counts under the team lock,
  so the 50-member limit holds under concurrency.
- **`STUDENT_INVITATION.revoke`** also deletes the student's memberships. Removal, withdrawal and
  data deletion all go through it (R7).
- **`count_institution_uses`** counts every team, deleted ones included (R8).

**Routes** (R10, R11, [contracts/http-routes.md](./contracts/http-routes.md)):

- **A new router, `app/routers/teacher_teams.py`**, serves 11 endpoints under `/teacher/teams`, 5 of
  them POST, all `@allow_roles(Role.TEACHER)`.
- **The selection** lives in the address (`?region=&institution=&team=`), validated as on
  **Students**. `team=new` opens the form.
- **Every change** is a POST followed by a 303 back to the tab:
  - after create, the new team is selected;
  - after rename, add or remove, the same team;
  - after delete, no team.
  An addition beyond 50 returns to **Add students** with the same class.
- **After an addition**, a sealed, 10-minute `notice` token carries ids only, so no name ever reaches
  an address or a log line.
- **Refusals**: unknown, deleted and unreachable teams, Read access on management pages, and
  blocked or other-institution students are all "access denied" (403).

**Components first** (R12, R13, [contracts/components.md](./contracts/components.md)). Each is added
to the library, the gallery and `ui-guidelines.md` before any page uses it:

- **`section_heading`** (new, `components/frame.html`): the hand-built class heading of **Students**,
  as a component. It emits the same markup and leaves out the row of small buttons when it is empty.
  **Students** switches to it first, with its markup pinned by a test in four states; then **Teams**
  uses it.
- **`row_note`** (new, `components/table.html`): the muted "In this team" in place of **Add**.

**Other changes**:

- **The tab row**: `TEACHER_TABS` gains **Teams** second (R15).
- **The home page's teacher card**: it names students, teams, the question bank and competitions
  (R16).
- **The profile** gains a **Teams** row (R14).
- **`test_consent_texts.py`** learns a one-time rewrite rule: the new pin, the superseded original
  still pinned, and only student version 1 allowed (R9).

**Tests** (R17):

- new modules for the service and the tab;
- updates to the route sweeps, the form contract, the gallery, migrations, the profile, consent and
  data deletion, the institution in-use rule, the home page, the tab row and the Students heading.

The four-tab row is measured at 360 px and 375 px with an ad hoc Playwright run and recorded. It is
expected to take two rows, a 158.5 px frame, under the 176 px clearance (R15).

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, SQLAlchemy 2.0.54, Alembic 1.20.0, Pico.css v2.1.1
  (vendored, not edited).
- No new runtime or development dependency.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision: two tables, one partial unique index, and one `UPDATE` of a consent
  text ([data-model.md](./data-model.md) §7).

**Testing**:

- pytest on both engines.
- New modules:
  - `tests/integration/test_team_service.py`;
  - `tests/integration/test_teacher_teams.py`.
- Changed rule: `tests/unit/test_consent_texts.py` (the rewrite rule and the new pin).
- Updated modules:
  - routes, teacher access, cross-site, form contract, gallery, page patterns, templates and
    stylesheet;
  - Students (the heading pin, and a removal erasing memberships), layout and classes (four tabs);
  - home, migrations, admin institutions and the institution service;
  - profile, consent privacy, data deletion and the student invitation;
  - `conftest.py`.
- The tab-row measurement is an ad hoc Playwright step, as in milestones 10.1 and 11
  ([quickstart.md](./quickstart.md) §6).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **The tab** runs a handful of indexed queries per page: the reachable institutions, the live teams
  of one institution (`ix_teams_institution_id`), and one join for at most 50 members (on the
  primary key).
- **The profile** adds one query on `ix_team_memberships_user_id`.

**Constraints**:

- **Access before anything named** (FR-023): the team is reached, with Write for changes, before any
  student, class or name is read. Each change checks again under lock.
- **No JavaScript needed**: every page works without it, with the **Show** buttons of
  `chained_lists`.
- **No names in logs or addresses** (FR-016): services log ids only, and notices travel as sealed ids.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL; the partial index is
  supported and drift-free on both (R2).
- **Students unchanged**: the heading's markup is pinned by a test (FR-046).

**Scale/Scope**:

- **Data and services**: 1 migration, 2 new models, 1 new service module, 3 changed service modules
  (`teacher_access`, `students`, `institutions`), and 5 changed router or app modules (`teacher`,
  `areas`, `profile`, `admin_components`, `main`).
- **Routes and pages**: 1 new router with 11 endpoints, and 5 new page templates.
- **Components**: 2 new component macros and 1 CSS rule.
- **Changed templates and modules**: about 5 (Students, profile, gallery, tabs, teacher card).
- **Documents**: 2 updated (UI guidelines, README), and `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 11 is merged (PR #42). Milestone 11.1 is the next rung and one end-to-end slice: the tab, the forms and pages, the services and the tables, plus the profile and consent. Nothing from milestone 12 is built: no competitions, no use of teams in competitions, and no change to the **Competitions** placeholder (FR-048). | ✅ |
| II. Server-rendered simplicity | All pages are rendered by Jinja on the server with plain `GET` and `POST`, and there are no HTMX partials (none needed). No JavaScript is added: the lists reuse `auto-submit.js` and `loading-feedback.js`. No new dependency. | ✅ |
| UI guidelines | Every page is built from the component library, uses design tokens only, and follows `docs/requirements/ui-guidelines.md`. The two new patterns, `section_heading` (the hand-built Students heading, FR-046) and `row_note` ("In this team"), are added to the library, the gallery (`/admin/components`) and the guidelines before **Teams** or **Students** use them (research R12, R13). **Students** keeps its markup exactly, pinned by a test. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ line map to pytest cases on both engines (research R17). Access tests cover every new route, allowed and denied, per role, per access level and for unknown, deleted and unreachable ids. Tests of the old consent checksum, the three-tab row and the old card text are replaced, not deleted silently (SC-011). The tab measurement (FR-026) is recorded, not an acceptance test. No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`. Teams are scoped to the institutions the teacher is linked to, through `teacher_access`, the only authority for scope (`reach_team`, `reach_student`). Write is checked in the router and again in the service transaction under lock (research R4, R5). Students see only their own teams on their profile; administrators get no team access (FR-019, FR-048). | ✅ |
| V. Secure authentication & secrets | No change to sign-in or sessions. Every POST passes the existing cross-site check (FR-043). The notice token is sealed with the existing key and holds ids only; no name or email reaches an address or a log line (FR-016, research R11). | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines and covered by the stairway and drift checks. Timestamps are UTC-aware. Deletion is soft, so milestones 12–15 can still show a deleted team with its memberships (FR-007). An institution with any team cannot be deleted (FR-017). One engine-specific feature is justified in R2: a partial unique index, declared for SQLite and PostgreSQL and verified on both. The consent text rewrite is a deliberate, one-time exception to milestone 8's append-only rule, required by FR-015; it is fenced by the test (R9). The downgrade drops teams; this is recorded in data-model §7. | ✅ |
| Stack | Only listed technologies. Pico is restyled only through `app.css`. | ✅ |
| Application Layout | `models/` (tables), `services/` (all rules: `teams`, `teacher_access`), `routers/` (thin), `templates/components/` (new macros first), `templates/pages/teacher/` (pages). | ✅ |
| Governance and workflow | README and `ui-guidelines.md` are updated in the PR, and `milestones.md` moves 11.1 to Delivered on delivery. The schema change ships with its migration. No constitution amendment is needed. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: every check is server-side, team before student, and again under lock
  ([http-routes.md](./contracts/http-routes.md) §Order of checks,
  [services.md](./contracts/services.md)).
- **Components**: both new components are in [components.md](./contracts/components.md) with their
  gallery variants and guidelines text, ordered before their use.
- **Data**: memberships are the only new personal data. They are erased on every path out of the
  student role through the one `revoke` (R7). Teams store no creator, so erasure leaves them intact.
- **Consent**: the rewrite keeps version 1, and its pin and the superseded original are both
  enforced (R9).

## Project Structure

### Documentation (this feature)

```text
specs/011.1-teacher-teams/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R17
├── data-model.md           # Phase 1: tables, rules, the consent text, migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # the /teacher/teams routes, statuses, redirects, page contents, wording
│   ├── services.md         # teams, teacher_access.reach_team, students.revoke, institutions
│   └── components.md       # section_heading, row_note
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── team.py                  # NEW: Team (partial unique index), TeamMembership
│   ├── consent.py               # docstring: the one-time rewrite exception
│   └── __init__.py              # export Team, TeamMembership
├── services/
│   ├── teams.py                 # NEW: lookups, create, rename, soft delete, add, remove, student's teams
│   ├── teacher_access.py        # + reach_team
│   ├── students.py              # revoke also deletes memberships
│   └── institutions.py          # count_institution_uses counts teams
├── routers/
│   ├── teacher_teams.py         # NEW: the Teams tab (11 endpoints), notice token
│   ├── teacher.py               # TEACHER_TABS gains Teams (second)
│   ├── areas.py                 # teacher card description
│   ├── profile.py               # teams for a student
│   └── admin_components.py      # gallery sample data for the new components
├── templates/
│   ├── components/
│   │   ├── frame.html           # + section_heading
│   │   └── table.html           # + row_note
│   └── pages/
│       ├── profile.html         # Teams row
│       ├── admin/components.html # #section-heading section, row_note in #table
│       └── teacher/
│           ├── students.html             # heading → section_heading (same markup)
│           ├── teams.html                # NEW: the lists, states, selected team, members
│           ├── team_form.html            # NEW: new and rename
│           ├── team_delete.html          # NEW: confirmation
│           ├── team_add_students.html    # NEW: class list, students, Add / In this team
│           └── team_member_remove.html   # NEW: confirmation
├── static/css/app.css           # .row-note
└── main.py                      # include teacher_teams router

migrations/versions/2026_10_29_<rev>_teams.py   # NEW

tests/
├── integration/test_team_service.py     # NEW
├── integration/test_teacher_teams.py    # NEW: the tab, end to end
├── unit/test_consent_texts.py           # rewrite rule, new pin, SUPERSEDED
└── (updated) test_routes, test_teacher_access, test_cross_site, test_form_contract +
    form_contract.json, test_component_gallery, test_page_patterns, test_templates,
    test_stylesheet, test_teacher_students, test_layout, test_teacher_classes, test_home,
    test_migrations, test_admin_institutions, test_institution_service, test_profile,
    test_consent_privacy, test_data_deletion, test_student_invitation, conftest.py

docs/requirements/ui-guidelines.md   # section_heading, row_note, clearance note (measured)
README.md                            # the Teams tab
```

**Structure Decision**: the existing single FastAPI application layout. The tab follows the
milestone 9 Students tab:

- a router per tab, and `render_teacher` for the tab row;
- the selection in the address, built by one path helper;
- services that take the teacher id and check reach inside their own transaction, under lock.

## Complexity Tracking

No constitution violations to justify. Two deliberate choices are recorded in research:

- **The partial unique index** (R2): an engine-specific feature, supported and drift-free on both
  engines.
- **The in-place rewrite of student consent text version 1** (R9): a one-time exception the spec
  requires (FR-015), fenced by `REWRITES_ALLOWED` in the published-text test.
