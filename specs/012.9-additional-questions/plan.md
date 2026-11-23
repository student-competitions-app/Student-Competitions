# Implementation Plan: Additional Questions in the Question Bank (Teacher) (Milestone 12.9)

**Branch**: `012.9-additional-questions` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.9-additional-questions/spec.md`

## Summary

A question of the bank can be marked as an **additional question**: before a competition that
holds it starts, only teachers with **Can manage competitions** see it.

- **The checkbox**: such a teacher sets and clears the mark with the checkbox **Additional
  question** on the add and edit form.
- **The badge**: they see the mark as the badge **Additional** beside the question's number on the
  **Questions** tab, on a competition's **Add questions** page and on a competition's **Questions**
  page.
- **The bank for everyone else**: every other teacher gets the bank without the additional
  questions. They are not listed, counted or paged, and they are left out of what the server reads.
- **Competitions**: their copies are untouched.

**Data** (research R1, R2, [data-model.md](./data-model.md)): one migration adds
`questions.is_additional BOOLEAN NOT NULL DEFAULT false`, in a batch block that keeps the table's
SQLite `AUTOINCREMENT`. `competition_questions` is unchanged: a copy holds no mark.

**Reading** (R3, R6, [contracts/services.md](./contracts/services.md)):

- `questions.question_page` gains a required keyword, `include_additional`. Without it, the
  condition `NOT is_additional` goes into both the count and the rows.
  - The **Questions** tab passes the teacher's setting.
  - **Add questions** passes `True`, since it is manage-only already.
- `competition_entries.question_page` gains a required keyword, `with_bank_mark`. With it, the
  query also selects the bank's current `is_additional` through its existing join; without it, the
  column is never read (`None`).

**Writing** (R5): the routers read the checkbox `additional` as a plain string (non-empty =
marked). `create_question` takes `is_additional=False` by default; `update_question` takes it as a
required keyword and counts it in `changed`. The edit form opens with the stored mark, and an
invalid form keeps what was sent.

**Access** (R4, [contracts/http-routes.md](./contracts/http-routes.md)): no route is added. Every
single-question route and **Add questions** already check the setting before any lookup, so a
teacher without it gets the same 403 for an additional, ordinary, deleted or missing question. The
tests gain the `additional` target.

**Components first** (R7, [contracts/components.md](./contracts/components.md)), each in the library
and the gallery before a page uses it; the guidelines are already updated:

- `additional_badge()`, giving `pgettext("question", "Additional")` with the `info` kind;
- `text_card(..., badge=None)`, which puts the badge inside the heading.

**Texts** (R8): three messages, «Додаткове питання», the hint and «Додаткове».

**Documents** (R10): the README's **Questions** paragraph in this PR; `milestones.md` (the 12.9 and
11 summaries) on delivery. The constitution v2.6.0, the product requirements and the UI guidelines
are already in `main`.

**Tests** (R9): no new module. Updates to twelve modules plus the form contract:
- ten that gain tests;
- two whose existing calls of `update_question` gain the now-required argument.

A thirteenth, `test_page_patterns`, is updated only if it sweeps the question pages.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**: unchanged. FastAPI 0.141, Jinja2, SQLModel, Alembic,
python-multipart, Babel, Pico.css v2.1.1, and fpdf2 (results files, not touched). No new runtime or
development dependency.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision after `c730fd883079` ([data-model.md](./data-model.md) §4): one column
  on `questions`, with a server default. Batch mode with `sqlite_autoincrement`; no data step, no
  index.

**Testing**:

- pytest on both engines, with no new module:
  - **The bank**: `test_question_service`, `test_teacher_questions`.
  - **Competitions**: `test_competition_entries_service`, `test_teacher_competition_entries`,
    `test_teacher_team_answers`, `test_teacher_grades`.
  - **Cross-cutting**: `test_migrations`, `test_form_contract` (+ `form_contract.json`, five
    `teacher-question-*` cases regenerated), `test_component_gallery`, `unit/test_templates`.
  - **Existing calls only**: `test_grade_service` and `test_team_answer_service`. Their calls of
    `update_question` gain `is_additional=False`, since the argument becomes required.
  - `tests/conftest.py`: `make_question(..., additional=False)`.
- `test_routes` and the catalogue tests stay green with no new entry. `test_page_patterns` gains a
  case only if it sweeps the question pages (tasks T034).
- Browser checks (360 px, both themes) by hand or with the ad hoc Playwright recipe
  ([quickstart.md](./quickstart.md) §3–4).

**Target Platform**:

- **Server**: the Linux container on Render; the Dockerfile is unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript. The checkbox is a plain form field.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**: nothing measurable changes.

- The list adds one boolean predicate to two queries that already filter by `subject_id` (indexed)
  and `deleted_at`.
- A competition's **Questions** page selects one more column through the join it already makes.
- The setting is read once per request, as it already is for the page's actions.

**Constraints**:

- **Check order** unchanged ([http-routes.md](./contracts/http-routes.md) §Order of checks): the
  role, then the setting before any id on a manage route.
- **Left out, not hidden**: for a teacher without the setting, additional questions and the mark
  are never read into a view (constitution IV).
- **No 422**: every new form value is read as a string.
- **No JavaScript needed**; the 10.1 busy button and loading bar are unchanged.
- **Tokens only** in the stylesheet; ideally no CSS change at all.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.
- **Logs** carry ids only, as before.

**Scale/Scope**:

- **Schema**: 1 migration, 1 column.
- **Services**: 2 changed (`questions`, `competition_entries`).
- **Routers**: 2 changed (`teacher_questions`, `teacher_competition_entries`); no new endpoint.
- **Templates**: 4 pages changed (`questions.html`, `question_form.html`,
  `competition_questions_add.html`, `competition_questions.html`), 2 components (`badge.html`,
  `card.html`) and the gallery page.
- **Catalogues**: 3 messages in `uk` and `en`.
- **Documents**: README.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | 12.8 is merged and delivered (PR #61, #62). 12.9 is one end-to-end slice: from the checkbox on the form, through the stored mark, to what each teacher's pages show and what the server reads for them. Nothing from 12.10 is built (the competition's **Questions** page stays open to every teacher; no questions file), and nothing is given to participants (not yet scheduled). | ✅ |
| II. Server-rendered simplicity | Jinja pages, plain `GET` and `POST`, no HTMX partial, no script, no new dependency. | ✅ |
| UI guidelines | Pages built from the component library with tokens only. `additional_badge()` and `text_card`'s `badge` go into the library and the gallery before any page uses them; `ui-guidelines.md` already describes both (v2.6.0 change, `3a4e5bb`) and is checked against the build. The checkbox is the existing `checkbox_field`. No new token or colour: `info` reuses `.badge-info`. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ line map to pytest cases on both engines (R9). Every changed route is tested allowed and denied per role and setting, with the new `additional` target. The response bodies are searched for additional questions' texts, numbers and the badge. No external service is called. | ✅ |
| IV. Role-based access & data scoping | Every route stays `@allow_roles(Role.TEACHER)`; administrators and students get 403. **Additional questions kept back**: for a teacher without the setting, the bank query leaves them out of the count and rows, and the competition page never reads the mark (R3, R6). Manage routes check the setting before any lookup and again under lock in the service. **The recorded exception**: every teacher still reads a competition's **Questions** page until 12.10 (spec FR-027; constitution IV). This plan does not widen it: the bank numbers stay as 12.2 shows them, and the badge is left out for other teachers. | ✅ |
| V. Secure authentication & secrets | No change to sign-in or sessions. The changed `POST`s keep the existing cross-site check. Logs carry ids only. | ✅ |
| VI. LLM evaluation | Not touched. The mark does not change grading or scoring. | n/a |
| VII. Data integrity & migrations | One Alembic revision on both engines, covered by the stairway and drift checks. The server default fills existing rows; the downgrade keeps SQLite `AUTOINCREMENT`. Competition copies, answers, grades and results files never change with the mark (FR-023; checked in R9). No cascade, no derived value stored. | ✅ |
| Stack | No new technology or dependency. | ✅ |
| Application Layout | `models/` (the column), `services/` (`questions`, `competition_entries`), `routers/` (thin: they parse the checkbox and pass the setting), `templates/components/` (`badge`, `card`), `templates/pages/teacher/`, `migrations/`. | ✅ |
| Governance and workflow | The constitution amendment this milestone needs (v2.6.0, 2026-11-23) and the product requirements and UI guidelines are in `main` (`3a4e5bb`). The README is updated in this PR; `milestones.md` on delivery. The schema change ships with its migration. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: no caller of `questions.question_page` or `competition_entries.question_page` can
  omit the visibility decision (required keywords). The only callers that pass `True` sit behind
  `require_manage` or pass the setting itself ([services.md](./contracts/services.md)).
- **Integrity**: the only writers of `is_additional` are `create_question` and `update_question`,
  both under the setting lock. `update_question` refuses deleted questions and those of deactivated
  subjects before writing. No writer touches `competition_questions` for the mark.
- **Components**: the two additions, their gallery entries and the page uses are in
  [components.md](./contracts/components.md).
- **Data**: no personal data added; who set the mark is not stored.

## Project Structure

### Documentation (this feature)

```text
specs/012.9-additional-questions/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R10
├── data-model.md           # Phase 1: the column, the views, who reads what, the migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # changed routes, fields, refusals, pages that never show the mark
│   ├── services.md         # questions and competition_entries changes, seeders
│   └── components.md       # additional_badge, text_card badge, the checkbox on the form
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   └── question.py                  # Question.is_additional (server default false)
├── services/
│   ├── questions.py                 # QuestionView.is_additional; question_page(include_additional=…); create/update take the mark
│   └── competition_entries.py       # CompetitionQuestionView.is_additional; question_page(with_bank_mark=…)
├── routers/
│   ├── teacher_questions.py         # read `additional`; pass the setting to question_page; values for the form
│   ├── teacher_competition_entries.py  # with_bank_mark=can_manage; include_additional=True on Add questions
│   └── admin_components.py          # (only if the gallery needs new sample data; likely none)
├── templates/
│   ├── components/
│   │   ├── badge.html               # additional_badge()
│   │   └── card.html                # text_card(..., badge=None)
│   └── pages/
│       ├── admin/components.html    # badges "Marks" row; text card with the badge
│       └── teacher/
│           ├── question_form.html               # the checkbox after the reference answer
│           ├── questions.html                   # badge on additional questions
│           ├── competition_questions_add.html   # badge on additional questions
│           └── competition_questions.html       # badge when q.is_additional
├── static/css/app.css               # only if the 360 px check needs the one spacing rule (R7)
└── locale/{uk,en}/LC_MESSAGES/messages.po   # 3 messages

migrations/versions/2026_11_<dd>_<rev>_additional_questions.py   # NEW

tests/
├── conftest.py                                  # make_question(additional=…)
├── unit/test_templates.py
└── integration/
    ├── test_question_service.py, test_teacher_questions.py
    ├── test_competition_entries_service.py, test_teacher_competition_entries.py
    ├── test_teacher_team_answers.py, test_teacher_grades.py
    ├── test_grade_service.py, test_team_answer_service.py   # existing update_question calls only
    ├── test_migrations.py, test_component_gallery.py
    └── test_form_contract.py + form_contract.json   # five teacher-question-* cases regenerated

README.md                            # the Questions paragraph
```

**Structure Decision**: the existing single FastAPI application layout. The mark lives on the bank
row. The visibility decision is a required argument of the two services that read questions for
pages, so routers stay thin: they read the setting and pass it on. There is no new router, service
or page.

## Complexity Tracking

No constitution violations to justify.

- The accepted gap (every teacher reads a competition's **Questions** page until 12.10) is the
  exception the constitution v2.6.0 records itself in Principle IV, not a deviation of this plan.
