# Implementation Plan: Publishing a Competition's Results as PDF Files (Teacher) (Milestone 12.8)

**Branch**: `012.8-publishing-results` (local: `023.8_publishing_results`) | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.8-publishing-results/spec.md`

## Summary

A teacher with **Can manage competitions** publishes the results of a fully graded **Finished**
competition from a primary confirmation. Publishing is permanent:

- it sets the new status **Published**;
- it freezes the grades;
- in the same transaction, it stores two PDF files of the results, Ukrainian and English: a
  header with the logo, then every team by region, institution and team, with its score.

Every teacher then downloads the stored file of the current site language from the actions menu.

**Data** (research R3, [data-model.md](./data-model.md)): one migration adds
`competitions.published_at` (with `published_after_finish`) and a new table
`competition_results_files (competition_id, language, content)`. Its primary key is
`(competition_id, language)`, and the table is insert-only. The status stays derived: `status_of`
reads `published_at` after `cancelled_at`.

**Status** (R4): `CompetitionStatus.PUBLISHED`, placed after `FINISHED`, and
`CompetitionStatus.has_finished` (Finished or Published). Every "has ended" check moves to it, from
a named list of call sites. Visibility and team deletion read `stopped_at` and need no change.

**Publishing** (R5, [contracts/services.md](./contracts/services.md) §1), in
`app/services/results.py` (new): `publish_results` mirrors `finish_competition`, in this order:

1. the setting, under lock;
2. the competition `FOR UPDATE`;
3. **Finished**, read with a fresh clock;
4. every team fully graded (`grades.grading_progress`);
5. the snapshot (R7);
6. both files rendered;
7. a conditional update of `published_at`;
8. two inserts and one commit.

The grade save's `FOR SHARE` (12.4) and the publish's `FOR UPDATE` order every grade save and
publish, so the first wins and the files always match the grades.

**Files** (R1, R2, R8, [contracts/results-file.md](./contracts/results-file.md)):

- `app/services/results_pdf.py`: a pure `render_results_pdf(snapshot, language) -> bytes`.
- **Library and font**: fpdf2 with Open Sans Regular and Bold TTF, embedded as subsets.
- **Logo**: `logo-dark-192.png`.
- **Times**: Kyiv time, labelled through the 12.5 helpers.
- **Page numbers**: "Page n of N" via `{nb}`.
- The design is finalized in review rounds on samples from `scripts/make_results_samples.py` (R12).

**Routes** (R9, R10, [contracts/http-routes.md](./contracts/http-routes.md)):

- **Publish**: `GET`/`POST /teacher/competitions/{id}/publish` in `teacher_competitions.py`,
  beside finishing, with `PUBLISH_REFUSALS`, the blocked confirmation and the notice `published`.
- **Download**: `GET /teacher/competitions/{id}/results` in `teacher_results.py` (new). It is open
  to every teacher and returns the stored bytes with `Content-Disposition` (RFC 6266 name) and
  `Cache-Control: no-store`; anything not **Published** answers 404.
- **Grading**: the 12.4 grading routes open on **Published**; there the sheet is read-only with
  the note, and a save is refused with 409.

**Components first** (R11, [contracts/components.md](./contracts/components.md)), each added to the
library, the gallery and `ui-guidelines.md` before a page uses it:

- the **Published** badge (new kind `accent`, existing tokens);
- `menu_link(download=True)`;
- the blocked state of `confirmation`;
- the read-only `grading_sheet`.

**Documents**: the constitution v2.5.0 and the requirements already state the rules (FR-047). The
UI guidelines and the README are updated in this PR; `milestones.md` on delivery. This plan
records the open stack decision "PDF library and font" (R1, R2).

**Tests** (R14): three new modules, updates to eleven, plus a new development dependency, `pypdf`,
to read files back.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, SQLModel, Alembic, python-multipart, Babel, Pico.css v2.1.1.
- **New runtime dependency**: `fpdf2>=2.9`, which brings Pillow and fontTools (research R1;
  justification below, as Principle II requires).
- **New development dependency**: `pypdf`, test-only, to read text and images back from the files.
- New committed assets: `app/static/fonts/OpenSans-Regular.ttf` and `OpenSans-Bold.ttf`, under
  the existing `OFL.txt`.
- New script: `scripts/make_results_samples.py`, for the design review only.

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged.
- One new Alembic revision after `7110bec350d2` ([data-model.md](./data-model.md) §6): one column
  and one constraint on `competitions` (batch mode on SQLite), and one new table with a
  `LargeBinary` column (`BYTEA` / `BLOB`).

**Testing**:

- pytest on both engines, with the race cases (two sessions) on PostgreSQL only, as in 12.1–12.4.
- **New modules**:
  - `tests/unit/test_results_pdf.py`;
  - `tests/integration/test_results_service.py`;
  - `tests/integration/test_teacher_results.py`.
- **Updated modules**:
  - the teacher pages: `test_teacher_competitions`, `test_teacher_grades`,
    `test_teacher_team_answers`;
  - the services: `test_competition_service`, `test_grade_service`;
  - the cross-cutting checks: `test_routes`, `test_migrations`, `test_form_contract` (+
    `form_contract.json`), `test_component_gallery`, `test_page_patterns`, `test_templates`;
  - `tests/conftest.py`: a `publish` seeder.
- The design of the files is approved by hand (FR-049). Browser behaviour (the download with no
  loading bar, 360 px) is checked by hand or with an ad hoc Playwright run
  ([quickstart.md](./quickstart.md) §4).

**Target Platform**:

- **Server**: the Linux container on Render. The Dockerfile is unchanged: fpdf2, Pillow and
  fontTools install as wheels through `uv sync --locked`.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript. The download is a plain link.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **A publish of 500 teams in 10 regions**, files included, completes in under 5 s (SC-007). The
  work is one team query, one grouped grade count, then two renders in memory.
- **A download** reads one row by primary key and streams it; it starts within 1 s.
- **Lists stay cheap**: `select(Competition)` never reads a file (R3).

**Constraints**:

- **Check order** exactly as FR-034: the role; the setting (publish only) before any value is
  parsed; the subject and the competition; the status; the grading.
- **Under lock**: the publish re-checks the setting, the status and the grading inside its
  transaction; the 12.4 grade save keeps its share lock.
- **Files** are written once, in the publishing transaction, and never updated or deleted.
- **No JavaScript needed**: plain forms and links; the 10.1 busy button applies to **Publish
  results**.
- **Tokens only** in the stylesheet; the milestone 10 and 10.1 stylesheet checks stay green.
- **Both engines**: the same code and migration run on SQLite and PostgreSQL.
- **No log line** carries a name: publishing logs ids, team count and byte size.

**Scale/Scope**:

- **Schema**: 1 migration (1 column, 1 constraint, 1 table).
- **Services**: 2 new modules (`results`, `results_pdf`) and 2 changed (`competitions`, `grades`).
  The status call sites change in 3 routers.
- **Routers**: 1 new router with 1 endpoint; 2 new endpoints in `teacher_competitions`.
  `teacher_grades` and `teacher_team_answers` change.
- **Templates**:
  - 1 new page template (`competition_publish.html`);
  - 2 changed pages (`competitions.html`, `team_grading_sheet.html`) and
    `competition_answers.html` (status check);
  - 4 changed components (`badge`, `menu`, `confirmation`, `grading_sheet`) and their CSS and
    gallery sections.
- **Assets**: 2 committed fonts; 1 script; the review samples and `design-approval.md`.
- **Documents**: 2 updated (UI guidelines, README); `milestones.md` on delivery.

**New dependency justification** (constitution Principle II, "Results files" row):

- The milestone needs PDF output with embedded Cyrillic fonts, made on the server, with no
  external service.
- fpdf2 is the smallest library that does that in pure Python: no system libraries, no template
  engine, and "Page n of N" in one pass.
- ReportLab, WeasyPrint, xhtml2pdf and borb were weighed in research R1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.7 is merged (PR #60). 12.8 is one end-to-end slice: from the menu, through the confirmation and the publishing transaction, to the stored files and their download. Nothing from later milestones is built: no results page, places, winner or best answers (14); no student view (14); no LLM (13). | ✅ |
| II. Server-rendered simplicity | Jinja pages with plain `GET` and `POST`; the download is a plain link with `download`; no HTMX partial, no new script. One new runtime dependency (fpdf2), justified above and in R1. | ✅ |
| UI guidelines | Pages built from the component library with tokens only. The badge, the download entry, the blocked confirmation and the read-only grading sheet go into the library, the gallery and `ui-guidelines.md` before any page uses them (FR-041–FR-046; components.md). No new colour token: `accent` reuses `--sc-accent` / `--sc-on-accent`. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ list map to pytest cases on both engines (R14), with the 12.1 controlled clock and two-session race tests on PostgreSQL. Access tests cover the 3 new endpoints and the changed ones, allowed and denied, per role and setting. The files are read back with pypdf. No external service is called. The design approval is by hand, as the milestone says. | ✅ |
| IV. Role-based access & data scoping | Every route is `@allow_roles(Role.TEACHER)`. Publishing checks **Can manage competitions** first in the router and again under lock in the service, for every competition whatever the teacher's links. Only a fully graded **Finished** competition is published, permanently; every later grade save is refused server-side under the share lock. The download is open to every teacher (published results are open information) and holds only team, institution, region and score; answers and per-question grades keep their 12.4 scoping. Administrators and students get 403. | ✅ |
| V. Secure authentication & secrets | No change to sign-in or sessions. The publish `POST` passes the existing cross-site check, and the download is a safe `GET` that changes nothing. Notices use the existing sealing. Logs carry ids, counts and sizes only. | ✅ |
| VI. LLM evaluation | Not called. The constitution's rule that evaluation never runs on a published competition is served by `status_of` returning `PUBLISHED`, which milestone 13 will check. | n/a |
| VII. Data integrity & migrations | One Alembic revision, run on both engines, covered by the stairway and drift checks. The status stays derived, now from the stored publishing too. The files are stored in the database in the publishing transaction, made once, never updated or deleted, and served as stored; a lost race cannot store a second pair (primary key). Scores in the pages stay calculated from the frozen grades. Timestamps UTC. No `ON DELETE` cascades. `LargeBinary` maps to both engines with no engine-specific code. | ✅ |
| Stack | fpdf2 fills the "Results files" row, introduced in its listed milestone (12.8). The open stack decision "PDF library and the font" is recorded here: fpdf2 ≥ 2.9 with Open Sans (OFL). No other new technology. | ✅ |
| Application Layout | `models/` (column, table), `services/` (`results`, `results_pdf`), `routers/` (thin: `teacher_results`, publish routes), `templates/components/`, `templates/pages/teacher/`, `static/fonts/` (TTF beside the licence). | ✅ |
| Governance and workflow | The constitution amendment this milestone needs is already in `main` (v2.5.0, 2026-11-21), with the product and technical requirements. The UI guidelines and the README are updated in this PR; `milestones.md` on delivery. The schema change ships with its migration. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Access**: the contracts keep every check server-side, in the spec's order: the setting before
  any value on publish ([http-routes.md](./contracts/http-routes.md) §Order of checks), and again
  under lock ([services.md](./contracts/services.md) §1). The download needs only the teacher role
  and a **Published** competition.
- **Freeze**: the only writer of `grade` requires **Finished** under the share lock. The only
  writer of `published_at` requires **Finished** and full grading under `FOR UPDATE`, and inserts
  the files in the same transaction.
- **Snapshot**: the only writer of `competition_results_files` inserts; no path updates or deletes.
- **Components**: the four additions and the guideline changes are in
  [components.md](./contracts/components.md), with their gallery sections.
- **Data**: no personal data added; who published is not stored; nothing derived is stored except
  the snapshots the constitution requires.

## Project Structure

### Documentation (this feature)

```text
specs/012.8-publishing-results/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R15
├── data-model.md           # Phase 1: published_at, the files table, status, invariants, migration
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── http-routes.md      # publish, download, changed routes, checks, refusals, headers
│   ├── services.md         # results, results_pdf, grades and competitions changes
│   ├── components.md       # badge, download entry, blocked confirmation, read-only sheet
│   └── results-file.md     # what every file holds, and how it is checked
├── samples/                # the review samples (made by scripts/make_results_samples.py)
├── design-approval.md      # the review rounds (during implementation)
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── models/
│   ├── competition.py           # Competition.published_at + published_after_finish; CompetitionResultsFile
│   └── __init__.py              # export CompetitionResultsFile
├── services/
│   ├── results.py               # NEW: snapshot, publish_results, results_file, file names
│   ├── results_pdf.py           # NEW: render_results_pdf (fpdf2)
│   ├── competitions.py          # PUBLISHED, has_finished, status_of, cancel refuses Published
│   └── grades.py                # grading_progress; docstring (frozen grades)
├── routers/
│   ├── teacher_competitions.py  # GET/POST /{id}/publish, PUBLISH_REFUSALS, NOTICES["published"]; Published in the other refusal tables
│   ├── teacher_results.py       # NEW: GET /{id}/results (the download)
│   ├── teacher_grades.py        # pages on has_finished; read-only sheet and 409 on Published
│   ├── teacher_team_answers.py  # has_finished; Published refusal text
│   └── admin_components.py      # gallery samples: five statuses, download entry, blocked confirmation, read-only sheet
├── templates/
│   ├── components/
│   │   ├── badge.html           # "published" → accent
│   │   ├── menu.html            # menu_link(download=…)
│   │   ├── confirmation.html    # blocked, alternative
│   │   └── grading_sheet.html   # read_only, note
│   └── pages/
│       ├── admin/components.html                # gallery sections
│       └── teacher/
│           ├── competitions.html                # menu order and entries (R10)
│           ├── competition_publish.html         # NEW: the confirmation, ready and blocked
│           ├── competition_answers.html         # has_finished
│           └── team_grading_sheet.html          # read-only with the note
├── static/
│   ├── css/app.css              # .badge-accent
│   └── fonts/OpenSans-Regular.ttf, OpenSans-Bold.ttf   # NEW (OFL, beside OFL.txt)
├── locale/{uk,en}/LC_MESSAGES/messages.po      # the new messages
└── main.py                      # include teacher_results

migrations/versions/2026_11_<dd>_<rev>_published_results.py   # NEW

scripts/make_results_samples.py  # NEW: review samples in both languages

tests/
├── unit/test_results_pdf.py                       # NEW
├── integration/test_results_service.py            # NEW
├── integration/test_teacher_results.py            # NEW
└── (updated) test_teacher_competitions, test_teacher_grades, test_teacher_team_answers,
    test_competition_service, test_grade_service, test_routes, test_migrations,
    test_form_contract + form_contract.json, test_component_gallery, test_page_patterns,
    unit/test_templates, conftest.py

pyproject.toml, uv.lock              # fpdf2 (runtime), pypdf (dev)
docs/requirements/ui-guidelines.md   # statuses, menu, download entry, blocked confirmation, read-only sheet
README.md                            # publishing and downloading, fpdf2 and the fonts, the sample script
```

**Structure Decision**: the existing single FastAPI application layout.

- **Publishing** joins the 12.1 router beside cancelling and finishing, sharing their landing,
  notice and refusal code.
- **The files** are a new pair of services: a database-facing `results` and a pure renderer
  `results_pdf`, so the samples and the unit tests render without a database.
- **The download** is a separate small router: it has its own access rule (any teacher, no
  setting) and returns a file, not a page.

## Complexity Tracking

No constitution violations to justify.

- The one new runtime dependency (fpdf2) is required by the "Results files" row and justified above.
- The row locks that render nothing on SQLite follow the 12.1 pattern, and the files' primary key
  backs them up there.
- The development dependency `pypdf` is test-only and does not enter the image.
