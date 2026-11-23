# Implementation Plan: A Competition's Questions Only After It Starts, and Study Materials (Milestone 12.10)

**Branch**: `012.10_questions_study_materials` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.10-questions-study-materials/spec.md`

## Summary

This milestone makes three changes.

1. **A competition's questions are kept back.** Its **Questions** page is for teachers with
   **Can manage competitions** only.
2. **Download questions.** Every teacher downloads a started competition's question texts as a
   PDF for the teams.
3. **Download study materials.** Every teacher downloads a subject's bank, with reference answers
   and without additional or deleted questions, as a PDF for the students.

No schema change.

**Access** ([research R1](./research.md)): `competition_questions_page` calls `require_manage`
first, before any lookup, as every route under it already does. The whole `/questions` subtree
now refuses other teachers with the same 403. The **Questions** menu entry gets the guard
`can_manage`. **Teams** is unchanged.

**Downloads** (R2, [contracts/http-routes.md](./contracts/http-routes.md)): a new router,
`app/routers/teacher_question_files.py`, with two routes for every teacher. The response
headers of **Download results** move into a shared helper, `app/routers/downloads.py`.

- `GET /teacher/competitions/{id}/questions-file?subject=` answers for **In progress**,
  **Finished** and **Published** competitions, and 404 for anything else, with the 12.1 subject
  and competition rules.
- `GET /teacher/competitions/study-materials?subject=` needs an active subject, and answers 404
  otherwise.

**Files** (R3–R5, [contracts/files.md](./contracts/files.md)):

- `app/services/pdf_layout.py` takes the shared design out of `results_pdf.py`. The 12.8 samples
  must stay byte-identical.
- `app/services/question_files_pdf.py` holds two pure renderers:
  - `render_questions_pdf(QuestionsSheet, language)`;
  - `render_study_materials_pdf(StudyMaterials, language)`.

  Each draws a numbered list, and an entry is never split unless it is taller than a page.
- `app/services/question_files.py` reads the inputs:
  - the competition's copies, every one, with no bank number or mark;
  - the subject's questions that are neither additional nor deleted, `id` ascending.

**Kept in memory, never stale** (R6, [contracts/services.md](./contracts/services.md) §3):

- `StudyMaterialsCache` lives on `app.state`, created in `lifespan`, so it is empty at every start.
- It keeps one file per (subject, language), together with the `StudyMaterials` it was made from.
- Every download reads the materials, a cheap query. It gives the kept bytes only when they are
  equal to what was just read, else it renders and replaces.
- A per-key lock makes simultaneous downloads render once.
- Nothing else in the code knows about the cache.

**Components first** (R8, R9, [contracts/components.md](./contracts/components.md)):

- `chained_lists` gains an optional `aside` cell, and `link_button` gains `download=True`. Both
  go into the library, the gallery and `ui-guidelines.md` before the Competitions tab uses them.
- The actions menu order becomes Edit, Questions, Teams, Answers, Download questions, Grades,
  Publish results, Download results, Finish competition, Cancel competition.

**Design approval** (R11): `scripts/make_question_file_samples.py` writes byte-stable samples.
Screenshots of the link come from an ad hoc Playwright run. Rounds are recorded in
`design-approval.md`, and approval is a manual task of its own.

**Tests** (R10): three new modules, and updates to the Questions-page, competitions-list, routes
and gallery tests. pypdf, already a development dependency, reads the files back.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**: unchanged: FastAPI, Jinja2, SQLModel, Alembic, Babel, Pico.css v2,
fpdf2 (12.8) with the embedded Open Sans. No new runtime or development dependency: pypdf is
already a development dependency.

**Storage**: SQLite (local, tests) and PostgreSQL (production). No migration. Nothing new is
stored. The study materials are kept only in the process's memory (R6).

**Testing**: pytest on both engines.

- **New modules**:
  - `tests/unit/test_question_files_pdf.py`;
  - `tests/unit/test_study_materials_cache.py`;
  - `tests/integration/test_teacher_question_files.py`.
- **Updated modules**:
  - `test_teacher_competition_entries.py`;
  - `test_teacher_competitions.py`;
  - `test_routes.py` and `test_access_control.py`;
  - `test_component_gallery.py`.
- **Kept green**: `test_results_pdf.py` (the refactor), `test_catalogues.py`.
- **By hand**: the design approval and the 360 px look.

**Target Platform**: the Linux container on Render: one uvicorn process, synchronous handlers in
its thread pool. Current desktop and phone browsers, with and without JavaScript; both downloads
are plain links.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- A questions file of 10 questions starts downloading within 1 s (SC-008).
- A kept study materials file of 150 questions is given within 1 s without rendering (SC-005).
- The first render of 150 questions is measured and recorded (R12).

**Constraints**:

- **Check order** as FR-042.
- **The setting before any lookup** on the Questions subtree.
- **The questions file** is made at every download, and never stored or kept.
- **The study materials** are never stored in the database and never given stale.
- **No markdown interpretation** of user text in the files.
- **Tokens only** in CSS.
- **No log line** on a download.
- **Both engines.**

**Scale/Scope**:

- **Routers**: 1 new router with 2 endpoints. 1 changed handler (`competition_questions_page`).
  `teacher_results.py` uses the shared download helper.
- **Services**: 3 new modules (`pdf_layout`, `question_files`, `question_files_pdf`) and 1 helper
  module (`file_names`). `results_pdf` and `results` are refactored with no change in output.
- **`app/main.py`**: one line in `lifespan`.
- **Templates**:
  - 1 changed page (`competitions.html`);
  - 2 changed components (`selectors.html`, `button.html`), with their CSS and gallery sections.
- **Catalogues**: about 12 new messages in each language.
- **Assets**: 1 script, samples, `design-approval.md`.
- **Documents**: UI guidelines and README in this PR; `milestones.md` on delivery.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.9 is merged (PR #64). 12.10 is one end-to-end slice: the menu and the tab link, through the routes, to the files. Nothing from later milestones is built: no student view, no LLM, no results page. | ✅ |
| II. Server-rendered simplicity | Plain `GET` links with `download`; no HTMX, no new script, no new dependency. | ✅ |
| UI guidelines | The Competitions tab is built from the library. The `chained_lists` aside and the `link_button` download variant are added to the library, the gallery and `ui-guidelines.md` first (FR-024). The menu entry reuses `menu_link(download=True)`. Tokens only. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ line map to pytest cases on both engines (R10). That covers allowed and denied access on the 2 new routes and the changed Questions subtree, per role, setting and access level, and the files read back with pypdf. The kept-file behaviour is tested by counting renders. Design approval by hand, as the milestone says. | ✅ |
| IV. Role-based access & data scoping | Enforced server-side. The Questions subtree checks the setting before any lookup, so other teachers learn nothing about which competitions exist or what they hold. The questions file exists only from the start (status checked at every download) and holds texts only: no reference answer, bank number or mark (by construction: R5). The study materials leave out additional and deleted questions in the query itself, for every teacher, managers included, and hold no bank numbers. Administrators and students get 403 before any id is read. The answer sheets of milestones 12.3 and 12.4 keep showing a started competition's texts, never the reference answers, to the teachers of the teams' institutions, which v2.7.1 names as the one other place besides the questions file. | ✅ |
| V. Secure authentication & secrets | No change to sign-in or sessions. Both routes are safe `GET`s that change nothing. Nothing is logged on a download. | ✅ |
| VI. LLM evaluation | Not involved. | n/a |
| VII. Data integrity & migrations | No schema change. The status is derived on the server at every download (Principle VII, "on every read of questions"). The results snapshots are untouched, and the refactor is checked byte for byte against the 12.8 samples. | ✅ |
| Stack | The "PDF files" row is followed: fpdf2 and Open Sans. Both files are made at download and not stored. The study materials are kept in process memory, which is no new infrastructure, and are compared with freshly read inputs at every download, so they are never stale. | ✅ |
| Application Layout | `routers/` stays thin (`teacher_question_files`, `downloads`). The logic and the cache are in `services/` (`question_files`, `question_files_pdf`, `pdf_layout`, `file_names`). `templates/components/` and `templates/pages/teacher/` are changed. | ✅ |
| Governance and workflow | The amendment this milestone needs is already on the branch (constitution v2.7.1, with the product and technical requirements). The UI guidelines and the README are updated in this PR; `milestones.md` (12.10 and the 12.9 summary) on delivery. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: [http-routes.md](./contracts/http-routes.md) gives each route's checks in FR-042
  order. The Questions subtree raises 403 before `find_context`. The two downloads read no
  setting.
- **Content**: `QuestionsSheet` and `StudyMaterials` ([data-model.md](./data-model.md)) have no
  field for a bank number, a mark or (in the sheet) a reference answer, so the renderers cannot
  draw one. The study materials query filters `is_additional` and `deleted_at` in SQL.
- **Freshness**: the cache's only path to returning bytes is equality with the materials read
  in the same request ([services.md](./contracts/services.md) §3).
- **Components**: [components.md](./contracts/components.md) lists the two additions and their
  gallery sections.

## Project Structure

### Documentation (this feature)

```text
specs/012.10-questions-study-materials/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R12
├── data-model.md        # Phase 1: the sheets, the cache, the reads (no schema change)
├── quickstart.md        # Phase 1: how to see and check the milestone
├── contracts/
│   ├── http-routes.md   # the Questions subtree, the two downloads, the menu
│   ├── files.md         # the two PDF files
│   ├── services.md      # question_files, question_files_pdf, pdf_layout, file_names
│   └── components.md    # chained_lists aside, link_button download, menu order
├── checklists/requirements.md
├── design-approval.md   # created during implementation (rounds and decisions)
├── samples/             # created during implementation (review samples)
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── main.py                                  # lifespan: app.state.study_materials = StudyMaterialsCache();
│                                            # include_router(teacher_question_files.router)
├── routers/
│   ├── downloads.py                         # new: pdf_download(content, file_name)
│   ├── teacher_question_files.py            # new: questions-file, study-materials
│   ├── teacher_results.py                   # uses downloads.pdf_download
│   └── teacher_competition_entries.py       # competition_questions_page: require_manage first
├── services/
│   ├── file_names.py                        # new: clean_file_stem, ascii_file_name (moved)
│   ├── pdf_layout.py                        # new: the shared document, header, constants
│   ├── question_files.py                    # new: sheets, reads, file names, StudyMaterialsCache
│   ├── question_files_pdf.py                # new: render_questions_pdf, render_study_materials_pdf
│   ├── results_pdf.py                       # uses pdf_layout (output unchanged)
│   └── results.py                           # uses file_names (output unchanged)
├── templates/
│   ├── components/selectors.html            # chained_lists(..., aside=None)
│   ├── components/button.html               # link_button(..., download=False)
│   ├── pages/teacher/competitions.html      # menu guard and entry; the aside link
│   └── pages/admin/components.html          # gallery: the aside, the download link button
├── static/css/app.css                       # .selectors-aside (tokens only)
└── locale/{uk,en}/LC_MESSAGES/messages.po   # new messages

scripts/make_question_file_samples.py        # new: review samples

tests/
├── unit/test_question_files_pdf.py          # new
├── unit/test_study_materials_cache.py       # new
├── integration/test_teacher_question_files.py  # new
└── integration/…                            # updated, as in Technical Context

docs/requirements/ui-guidelines.md           # menu order, aside, download link button
README.md                                    # Competitions tab: Questions, the two downloads
```

**Structure Decision**: the existing single FastAPI application and its `app/` layout
(constitution, Application Layout). The new code follows the 12.8 split:

- a thin router;
- a service that reads the inputs and keeps the files;
- a pure renderer;
- one shared layout module, so the three PDF files keep one design.

## Complexity Tracking

No constitution violations to justify.
