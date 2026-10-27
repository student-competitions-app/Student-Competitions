# Implementation Plan: Question Bank (Teacher) (Milestone 11)

**Branch**: `011-question-bank` | **Date**: 2026-10-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-question-bank/spec.md`

## Summary

Teachers get a shared question bank, one subject at a time, on a new **Questions** tab. Teachers
with the renamed **Can manage competitions** setting add, edit and soft-delete questions; every
other teacher reads it. The milestone 3 sample questions and the home page list go away.

**Data** (research R1–R3, [data-model.md](./data-model.md)):

- **One migration** reshapes `questions`:
  - it deletes every existing row (the sample questions);
  - it adds `subject_id` (required, indexed, a foreign key to `subjects`) and `deleted_at`
    (nullable, UTC);
  - it sets both text columns to 2,000 characters;
  - it turns on SQLite `AUTOINCREMENT`.
- **The same migration renames the setting**: `teacher_profiles.can_create_competitions` becomes
  `can_manage_competitions`, and every value is kept.
- **A question's number is its id**: global, assigned once, never reused. The list is newest first
  by id.
- **Deleting a question sets `deleted_at`** and changes nothing else.

**Services** (R4–R8, [contracts/services.md](./contracts/services.md)):

- **`app/services/questions.py` is rewritten** around the bank:
  - list one page of a subject's questions;
  - create, update and soft-delete, each checking the setting and the subject inside its own
    transaction, with row locks;
  - work out where the list lands after a deletion.
- **`teacher_access.can_manage_competitions`** is the one authority for the setting.
- **`subjects.list_active_subjects`** gives the subject list.
- **`count_subject_uses` now counts every question**, deleted ones included.
- **A new pure module, `app/services/paging.py`**, parses and clamps the page number and builds the
  page navigation model, gaps included.

**Routes** (R5, R6, R8, [contracts/http-routes.md](./contracts/http-routes.md)):

- **A new router, `app/routers/teacher_questions.py`**, serves 7 endpoints under
  `/teacher/questions`, all `@allow_roles(Role.TEACHER)`.
- **Order of checks**: the setting is checked before any id is read. "Not found" (404) covers an
  unknown subject, a deactivated subject, an unknown question, a deleted question and a question
  of a deactivated subject.
- **Every change** is a POST followed by a 303 redirect.
- **The page the teacher came from** travels as `page=<n>` only. Returning "at a question" uses
  the `#question-<id>` anchor, which the milestone 10.1 scroll padding already keeps below the
  pinned frame.

**Components first** (R10, [contracts/components.md](./contracts/components.md)). Each is added to
the library, the gallery and `ui-guidelines.md` before the tab uses it:

- **New**:
  - `page_navigation` (new file `components/pagination.html`).
- **Extended**:
  - `form_actions` gets a second, secondary save button;
  - `form.html` gets `textarea_field`;
  - `card.html` gets `text_card` and `text_box`, the question's box holding two boxes;
  - `chained_lists` gets a `<noscript>` **Show** button (R11).
- **Why the `chained_lists` change**: the existing selector has had no submit button since
  milestone 9 (commit `f866721`), so today it does not work without JavaScript, which FR-012 and
  US2-14 require. The button appears only without JavaScript. It also restores the Students tab
  without JavaScript.

**Rename and cleanup** (R12, R13):

- **The new label**: **Can manage competitions** on the **Teachers** tab, both teacher forms, the
  acceptance page, the invitation email and the profile.
- **Old invitations still work**: sealed invitations carrying the old payload key are still
  accepted.
- **The home page** loses its question list but keeps the database line and its unavailable
  message, and the teacher card mentions the question bank.

**Tests** (R15): new unit and integration modules for paging, schemas, the service and the tab, plus
updates to the route sweeps, the form contract, the gallery, the migrations, the home page and
every test that names the old setting. The three-tab row is measured at 360 px and 375 px with an
ad hoc Playwright run and recorded (R14).

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, Alembic, Pico.css v2.1.1 (vendored, not edited).
- No new runtime or development dependency.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision. It changes `questions` and `teacher_profiles` and deletes the sample
  questions ([data-model.md](./data-model.md)).

**Testing**:

- pytest on both engines.
- New modules:
  - `tests/unit/test_paging.py`;
  - `tests/integration/test_teacher_questions.py`.
- Rewritten modules:
  - `tests/unit/test_question_schemas.py`;
  - `tests/integration/test_question_service.py`.
- Updated modules:
  - routes, access, form contract, gallery, page patterns, layout, home and health;
  - migrations, admin subjects and admin teachers;
  - invitations, profile, sealing and email.
- The tab-row measurement is a manual or ad hoc Playwright step, as in milestone 10.1
  ([quickstart.md](./quickstart.md) §6).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **The list**: one count and one page query, each on the `subject_id` index, so a page of 10
  stays cheap however large a subject grows.
- **A deletion** adds two small queries to find where the list lands.

**Constraints**:

- **Access before existence**: access is decided before any id or form value is read (FR-037).
- **No JavaScript needed**: every page works without it (FR-012, FR-023).
- **Stylesheet rules**: tokens only, and the milestone 10 and 10.1 stylesheet checks stay green.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.
- **Sealed invitations**: an invitation sealed before the deployment still works (FR-009).

**Scale/Scope**:

- 1 migration, 2 changed models and 1 rewritten service module.
- 1 new pure module and 1 new router with 7 endpoints.
- 4 new page templates.
- Components: 1 new component file and 4 extended component macros or files.
- About 12 changed templates (rename, home, gallery, layout tabs).
- 2 documents updated (UI guidelines, README); `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 10.1 is merged and delivered (PR #41). Milestone 11 is the next rung. It is one end-to-end slice: the subject list, the list, add, edit and delete, from the tab down to the table. Nothing from milestone 12 is built: no competitions, no question picker, and no change to the **Competitions** placeholder (FR-049). | ✅ |
| II. Server-rendered simplicity | All pages are rendered by Jinja on the server with plain `GET` and `POST`, and there are no HTMX partials (none needed). No JavaScript is added: the subject list reuses `auto-submit.js`, and paging and anchors are plain links. No new dependency. | ✅ |
| UI guidelines | Every page is built from the component library. Every value is a design token, and the pages follow `docs/requirements/ui-guidelines.md`. The new and extended patterns (`page_navigation`, two-button `form_actions`, `textarea_field`, `text_card`/`text_box`, and the `chained_lists` no-script **Show** button) are each added to the library, the gallery (`/admin/components`) and `ui-guidelines.md` before the **Questions** tab uses them (FR-025, FR-030, FR-047; research R10). | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ line map to pytest cases on both engines (research R15). Access tests cover every new route, allowed and denied, per role and per setting value. Old tests of the sample questions and the old setting name are replaced, not deleted silently (SC-010). The three-tab measurement (FR-011) is a recorded measurement, not an acceptance test; it is done with ad hoc Playwright as in milestone 10.1. No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`, so administrators and students get 403. Every add, edit and delete page and action also requires **Can manage competitions**. The router checks it first; the service checks it again inside the write transaction, with the teacher's profile row locked (R5, R7). The bank is deliberately not scoped to institutions (spec Edge Cases; product requirements: "every teacher can read the question bank"). Students never reach reference answers. | ✅ |
| V. Secure authentication & secrets | No change to sign-in, sessions or the cross-site check; every POST passes it (FR-045). The sealed teacher invitation format gains a new key name, and the old one is still read (R12). Nothing new is logged beyond ids. | ✅ |
| VI. LLM evaluation | Not touched. The reference answer is stored for milestone 14. | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines and covered by the stairway and drift checks. Timestamps (`deleted_at`) are UTC-aware. Deletion is soft, so milestone 15's history cannot be orphaned. A subject with any question, deleted ones included, can never be deleted (FR-040). Two engine-specific details are justified in R1 and R7: SQLite `AUTOINCREMENT`, a dialect option that PostgreSQL ignores, and row locks, which render nothing on SQLite, as in milestone 9. The downgrade deletes all questions; this is recorded in R3. | ✅ |
| Stack | Only listed technologies. Pico is restyled only through `app.css`. | ✅ |
| Application Layout | `models/`, `schemas/`, `services/` (business logic and paging), `routers/` (thin), `templates/components/` (new macros), `templates/pages/teacher/` (pages). | ✅ |
| Governance and workflow | README and `ui-guidelines.md` are updated in the PR, and `milestones.md` moves 11 to Delivered on delivery. The schema change ships with its migration. No constitution amendment is needed. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: the contracts keep every check server-side, with the setting before ids
  ([http-routes.md](./contracts/http-routes.md) §Order of checks).
- **Components**: every component is in [components.md](./contracts/components.md) with its gallery
  section.
- **Data**: the data model adds no personal data. `created_by` is deliberately not stored (spec
  Assumptions), so data erasure is unaffected.

## Project Structure

### Documentation (this feature)

```text
specs/011-question-bank/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R16
├── data-model.md           # Phase 1: tables, rules, migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # the /teacher/questions routes, statuses, redirects, page contents
│   ├── services.md         # questions, paging, teacher_access, subjects, teachers changes
│   └── components.md       # page_navigation, form_actions, textarea_field, text_card/text_box
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── question.py              # subject_id, deleted_at, 2,000-character columns, AUTOINCREMENT
│   └── teacher.py               # can_manage_competitions
├── schemas/
│   ├── question.py              # clean_question_text / clean_reference_answer, limits; QuestionPublic removed
│   └── teachers.py              # TeacherDetails.can_manage_competitions
├── services/
│   ├── questions.py             # rewritten: page, create, update, soft delete, landing
│   ├── paging.py                # NEW: parse_page, Paging (range, gaps)
│   ├── teacher_access.py        # + can_manage_competitions
│   ├── subjects.py              # + list_active_subjects; count_subject_uses counts questions
│   ├── teachers.py              # renamed setting; legacy invitation key read
│   └── …                        # invitations/email lines renamed
├── routers/
│   ├── teacher.py               # TEACHER_TABS gains Questions (middle)
│   ├── teacher_questions.py     # NEW: the Questions tab
│   ├── areas.py                 # teacher card description
│   ├── pages.py                 # home page without questions
│   ├── admin_teachers.py        # form field can_manage_competitions
│   └── admin_components.py      # gallery sample data for the new components
├── templates/
│   ├── components/
│   │   ├── pagination.html      # NEW: page_navigation
│   │   ├── form.html            # + textarea_field; form_actions second button
│   │   ├── card.html            # + text_card, text_box
│   │   └── selectors.html       # chained_lists: <noscript> Show button
│   └── pages/
│       ├── home.html            # question section removed
│       ├── profile.html, admin/teachers.html, admin/teacher_form.html, admin/teacher_invite.html
│       ├── admin/components.html # new gallery sections/variants
│       └── teacher/
│           ├── questions.html          # NEW: subject list, page navigation, the list
│           ├── question_form.html      # NEW: add and edit
│           ├── question_delete.html    # NEW: confirmation
│           └── question_not_found.html # NEW: 404 in the teacher frame
├── static/css/app.css           # pagination, text card/box, textarea height
└── main.py                      # include teacher_questions router

migrations/versions/2026_10_27_<rev>_question_bank.py   # NEW

tests/
├── unit/test_paging.py                      # NEW
├── unit/test_question_schemas.py            # rewritten
├── integration/test_question_service.py     # rewritten
├── integration/test_teacher_questions.py    # NEW: the tab, end to end
└── (updated) test_routes, test_teacher_access, test_form_contract + form_contract.json,
    test_component_gallery, test_page_patterns, test_layout, test_home, test_health,
    test_migrations, test_admin_subjects, test_admin_teachers, test_teacher_invitation,
    test_invitation_refusals, test_profile, test_sealing, test_email, conftest.py

docs/requirements/ui-guidelines.md   # the new components, wording, phone behaviour
README.md                            # the Questions tab, the renamed setting
```

**Structure Decision**: the existing single FastAPI application layout. The tab follows the
milestone 9 Students tab: a router per tab, `render_teacher` for the tab row, services that take
the teacher id and check access inside their own transaction, and redirects built by one path
helper.

## Complexity Tracking

No constitution violations to justify. The two engine-specific details are justified in research:
SQLite `AUTOINCREMENT` (R1) and row locks that render nothing on SQLite (R7).
