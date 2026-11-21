# Research: Publishing a Competition's Results as PDF Files (Milestone 12.8)

Phase 0 of [plan.md](./plan.md). Each decision resolves an unknown of the Technical Context or
records a choice the spec leaves to the plan. The spec has no `[NEEDS CLARIFICATION]` marker.

## R1. The PDF library: fpdf2

**Decision**: `fpdf2>=2.9` (2.9.0, released 2026-10-29), a runtime dependency. Its own
dependencies are Pillow and fontTools, both pure wheels for the `python:3.13-slim-bookworm` image
and macOS. This settles the constitution's open stack decision "PDF library" (milestone 12.8).

**Rationale**:

- **Pure Python, no system libraries**: nothing to add to the Dockerfile and nothing to install on
  a developer's machine besides `uv sync`. Both engines' test runs, CI and the image stay as they
  are.
- **Fonts**: `add_font()` embeds a TrueType font as a subset with a `ToUnicode` map, so Cyrillic
  renders everywhere and the text can be read back by the tests (R14).
- **Layout the files need, built in**: automatic page breaks, `header()`/`footer()` hooks, the
  `{nb}` alias for the total page count ("Page 2 of 3" in one pass), `multi_cell` for long names
  that wrap, PNG images with transparency (the logo), and document metadata (title, language,
  creation date).
- **Small surface**: the renderer is one module that draws text and one image; no template engine
  is needed.
- **Licence**: LGPL-3.0, used unmodified as an installed library, which the LGPL allows in an
  application of any licence.

**Alternatives considered**:

- **ReportLab** (BSD): mature, but "Page n of N" needs a second pass through a custom canvas, its
  Platypus layer is a larger API than the files need, and it pulls in `charset-normalizer`.
  Rejected as more machinery for the same output.
- **WeasyPrint** (HTML and CSS to PDF): the files could reuse Jinja templates, but it needs Pango,
  cairo and HarfBuzz system libraries in the image and on every developer's machine. Rejected for
  the system dependencies (constitution Principle II, simplest design).
- **xhtml2pdf**: ReportLab underneath with partial CSS support; rejected for the same reasons.
- **borb**: AGPL; rejected for the licence.

## R2. The font: Open Sans, static TrueType, Regular and Bold

**Decision**: commit `OpenSans-Regular.ttf` and `OpenSans-Bold.ttf` (the static instances of the
upstream Open Sans release, the same family the pages use) to `app/static/fonts/`, beside the
existing `OFL.txt`, which already covers them. The README's font note names the source and version.
The renderer registers both under one family name.

**Rationale**: the pages use Open Sans (self-hosted `woff2` subsets), so the files match the site.
fpdf2 reads TrueType, not `woff2`, and the `woff2` files are split into script subsets. The static
instances cover the full Ukrainian alphabet (А–Я with Ґ, Є, І, Ї), the three apostrophes of
milestone 12.5 (`'` U+0027, `’` U+2019, `ʼ` U+02BC), the typographic quotes “ ” « », the en dash
and `№`. fpdf2 embeds only the glyphs used, so each file carries a small subset.

**Checked by a test** (`tests/unit/test_results_pdf.py`): every character of the Ukrainian and
English alphabets, the apostrophes and the punctuation above is in both fonts' character maps. A
character the fonts lack (an emoji typed into a team name) is drawn as the font's missing-glyph box.
Names are never refused for it, since milestone 7 and 11.1 rules accept them.

**Alternatives considered**: DejaVu Sans (wider coverage, different look from the site); fpdf2's
core fonts (no Cyrillic); a variable font (one file, but static instances are what fpdf2 handles
best and are easy to check).

## R3. Storage: `competitions.published_at` and a table of results files

**Decision**:

- `competitions.published_at` (UTC, nullable): set once by publishing, never cleared. Check
  constraint `published_after_finish`: `published_at IS NULL OR stopped_at IS NOT NULL`.
- A new table `competition_results_files`: `competition_id` (foreign key, no `ON DELETE`),
  `language` (`'uk'` or `'en'`, check constraint), `content` (`LargeBinary`: `BYTEA` on PostgreSQL,
  `BLOB` on SQLite, not empty), primary key `(competition_id, language)`.

**Rationale**:

- The constitution (Principle VII) requires the files in the database, in the publishing
  transaction. Render's disk is not persistent anyway.
- **A separate table** keeps the files out of `select(Competition)`, which every competitions list
  runs over every competition of a subject. A column on `competitions` would read both files on
  every list.
- **The primary key** allows at most one file per language per competition, so even a lost race
  can never store four files.
- **Nothing ever updates or deletes a row**: the only writer is `results.publish_results` (insert).
  No `ON DELETE` cascades (competitions are never deleted).
- **The status stays derived** from the stored moments (Principle VII): `published_at` is the
  "stored publishing". Who published is not stored (spec Assumptions).

**Alternatives considered**: a `status` column (the status is derived, never stored); files on disk
or in object storage (constitution); one row with two blob columns (a lost race is harder to guard,
and a third language would need a migration).

## R4. The Published status

**Decision**:

- `CompetitionStatus.PUBLISHED = "published"`, declared between `FINISHED` and `CANCELLED`, so
  `STATUS_OPTIONS` (built from the enum's order) lists it after **Finished**. Its label is
  `_("Published")`, which the Ukrainian catalogue renders «Опубліковано», impersonal like the others.
- `status_of` checks `cancelled_at`, then `published_at`, then `stopped_at`, then the start.
- A new property, `CompetitionStatus.has_finished`, is true for `FINISHED` and `PUBLISHED`. Every
  check whose meaning is "the competition has ended" uses it. A check whose meaning is "grades may
  still change" stays `is FINISHED`.

**Call sites** (the whole list; [contracts/services.md](./contracts/services.md) §4 is the
checklist):

| Where | Today | After |
|---|---|---|
| `competitions.cancel_competition` | refuses `CANCELLED`, `FINISHED` | also `PUBLISHED` |
| `teacher_competitions` `EDIT_REFUSALS`, `CANCEL_REFUSALS`, `FINISH_REFUSALS` | keyed by status | `PUBLISHED` gets the `FINISHED` text (FR-018) |
| `teacher_competition_entries._entry_refusal` | falls through to "has finished" | unchanged (falls through) |
| `teacher_team_answers` `_PAGE_STATUSES`, `ANSWER_REFUSALS`, `finished = …` | `FINISHED` | `has_finished`; `PUBLISHED` refusal = finished text |
| `team_answers.answer_team_page(finished=…)` | caller passes `is FINISHED` | caller passes `has_finished` |
| `teacher_grades._open` | pages need `FINISHED` | pages open on `has_finished` |
| `grades.save_grades` | needs `FINISHED` | unchanged: `PUBLISHED` → `GradingClosed(PUBLISHED)` |
| `competitions._is_visible`, `_visible`, `offered_subjects`, `teams.delete_team` | `stopped_at` | unchanged: a published competition has `stopped_at` |
| `competitions.html` menu, `competition_answers.html` | `"finished"` | `has_finished` passed from the router / `PUBLISHED` cases |
| `badge.html`, `admin_components.COMPETITION_STATUSES` | four statuses | five |

**Rationale**: the spec says every finished rule holds for a published competition except the
grades. The visibility and deletion rules already read `stopped_at`, so they hold without a change.
The status checks are few and named, so a property keeps them from drifting.

## R5. The publish transaction and its races

**Decision**: `app.services.results.publish_results(session, teacher_id, competition_id,
subject_id, status_filter) -> Landing`, mirroring `finish_competition`:

1. the setting, read with `lock=True` (`ManageRequired`);
2. `competitions.lock_competition(...)`: the competition `FOR UPDATE`, its subject `FOR SHARE`,
   both refreshed (`CompetitionNotFound`);
3. the status with a fresh clock: must be `FINISHED` (`NotPublishable(status)`);
4. the grading progress under the lock: every team fully graded (`NotFullyGraded(progress)`);
5. the snapshot (R7) and both files rendered (R8), in memory;
6. the list before the change, for the landing (as finishing does);
7. a conditional `UPDATE competitions SET published_at = :now WHERE id = :id AND stopped_at IS NOT
   NULL AND cancelled_at IS NULL AND published_at IS NULL`; a row count of 0 →
   `NotPublishable(reread status)`;
8. two `INSERT`s into `competition_results_files`; an `IntegrityError` (a lost race on SQLite) →
   rollback and `NotPublishable(PUBLISHED)`;
9. the list after the change, one commit, one log line `Results published: id=%d teams=%d bytes=%d`
   (ids and sizes only).

A refusal rolls back first, so no lock outlives it. If rendering raises, the transaction rolls back
and the error page of milestone 2 is shown: nothing is stored and the competition stays
**Finished** (FR-009).

**The races** (FR-016, FR-017):

- **Two publishes**: on PostgreSQL the second waits on `FOR UPDATE`, then reads **Published** at
  step 3. The conditional update and the primary key guard it on SQLite, where the locks render
  nothing.
- **A grade save and a publish**: `save_grades` holds the competition `FOR SHARE` (milestone 12.4).
  A publish that comes first waits for the save to commit and then reads its grade at step 4. A
  save that comes after the publish waits for the publish's `FOR UPDATE` and then reads
  **Published** under its share lock, so `GradingClosed(PUBLISHED)` is raised. The files and the
  grades can never disagree.
- **The same form twice**: the second request reads **Published** at step 3.

**Time under lock**: rendering 500 teams takes well under a second with fpdf2 (checked in
`test_results_service.py` with a generous bound, SC-007). Grade saves of that competition wait that
long; nothing else waits.

**Alternatives considered**: rendering after the commit or in a background task (the constitution
wants the files in the publishing transaction, and a published competition must never lack files);
taking the lock only for the update (a grade save could then slip between the snapshot and the
update).

## R6. The frozen grades

**Decision**:

- `grades.save_grades` keeps "must be `FINISHED`". A `PUBLISHED` competition raises
  `GradingClosed(PUBLISHED)` under the share lock.
- `teacher_grades`:
  - the Grades page and the grading sheet open on `has_finished`;
  - on a `PUBLISHED` competition the sheet renders read-only (the note, grades as text, no field,
    no button) with status 200;
  - a save sent to a published competition renders the same read-only sheet with status 409 and
    stores nothing;
  - the other statuses keep their `GRADE_REFUSALS`.
- The Grades page keeps its **Grade answers** entry and its columns (spec Assumptions).

**Rationale**: the spec makes the grading sheet itself read-only, not a refusal page, and the
refusal of a late save is the same note on the same sheet (FR-021).

## R7. The snapshot

**Decision**: `results.build_snapshot(session, competition, subject) -> ResultsSnapshot`, read
under the publish lock:

- the competition's name, the subject's name, `starts_at`, `stopped_at`, and the publishing moment
  `now`;
- every team of the competition from `competition_entries.team_entries`: deleted teams and teams of
  deactivated institutions and regions included, as each is now (its name, its institution's name,
  that institution's region's name);
- the score from `grades.grade_counts` (0 for a team with no answers);
- regions, then institutions within a region, then teams within an institution, each by
  `name_sort_key`, ties by id. This is the same order in both files, since names are not translated.

The snapshot is a frozen dataclass of plain strings and ints. The renderer never touches the
database, so the sample script (R12) builds snapshots from data in memory.

**Rationale**: one read path for the files and the samples, and the order is tested on the snapshot
without parsing a PDF.

## R8. The renderer and the initial design

**Decision**: `app/services/results_pdf.py`, `render_results_pdf(snapshot, language) -> bytes`,
pure. It is called inside `use_language(language)`, so every label goes through the catalogues, and
times go through `format_local_time(moment, None)`. With no zone known, that gives Kyiv time
labelled "(Kyiv time)" / «(за київським часом)», as on the pages (milestone 12.5).

The **initial design**, the starting point of the review rounds (FR-038):

- **Page**: A4 portrait, 20 mm margins, Open Sans.
- **Header on page 1**:
  - the dark-ink emblem `logo-dark-192.png` (dark ink on white paper; milestone 12.7), 18 mm high,
    about 270 dpi;
  - the title "Results of “<name>”" (Bold 16 pt), with long names wrapping;
  - the subject;
  - "Started: <start>", "Finished: <finish>", "Published: <date>" and "Maximum score: <n>" (10 × the
    competition's questions; design review round 1) (10 pt).
- **Body** (design review round 1): per region, a heading (Bold 12 pt), then a table (fpdf2's
  `table()`): the heading row "Educational institution | Team | Score" (bold, light fill, repeated on
  every page the table continues onto), one row per team, horizontal rules only, 10.5 pt, long names
  wrapping within their cell. The score column is just wide enough for its heading or the widest
  score; the institution takes 56% of the rest, the team the remainder. A region heading is kept
  with its table's heading row and first team.
- **Footer on every page**: "Page <n> of <total>" (9 pt, centred), through fpdf2's `{nb}` alias. On
  pages after the first, a small running title with the competition's name.
- **No teams**: "No teams took part in this competition." in place of the regions.
- **Metadata**: the title, the language (`uk-UA` / `en-GB`), the creation date (the publishing
  moment), and the producer "Student Competitions". No author: the file is not personal data.

If the review needs a larger logo than 192 px gives at print quality, `scripts/make_logo.py` gains
one dark-ink print size. It is a change to the committed images only (milestone 12.7's script).

**Rationale**: a plain, printable list. The spec fixes the content and order, while the look is
settled with the product owner.

## R9. The download

**Decision**: `GET /teacher/competitions/{competition_id}/results?subject=<id>`.

- **Access**: any teacher (`@allow_roles(Role.TEACHER)`), no setting.
- **Lookup**: the subject and the competition as for every competition route. A competition that is
  not **Published** answers the 12.1 page "Competition not found" (404); an unknown subject answers
  "Subject not found" (404), as the other routes do.
- **The file**: it reads the one stored row of `request.state.language` and returns it unchanged:
  - `Content-Type: application/pdf`;
  - `Content-Disposition: attachment; filename="<ASCII fallback>"; filename*=UTF-8''<percent-encoded
    name>` (RFC 6266 / 5987);
  - `Cache-Control: no-store`, since the body depends on the language cookie and a cached English
    file must not answer after a switch to Ukrainian;
  - `X-Content-Type-Options: nosniff`.
- **The menu link**: it carries the HTML `download` attribute. The milestone 10.1 script already
  ignores links with `download` (`loading-feedback.js`), so no script changes.

**File name** (`results.results_file_name(name, starts_at)`): `"<name> <YYYY-MM-DD>.pdf"`, the
date in Kyiv time.

- In the name, `/ \ : * ? " < > |` and control characters become `_`, and spaces at the ends and
  trailing dots are removed. An empty result becomes `results`.
- The ASCII fallback keeps ASCII letters, digits, spaces and `-_.()`, turns every other character
  into `_`, and collapses runs of `_`.

**Rationale**: it is the same address shape as the competition's other pages, and the existing 404
page applies. Reading one row by its primary key serves the stored bytes without calculating
anything (Principle VII).

## R10. The menu and the publish confirmation

**Decision**:

- **The menu** (`competitions.html`) builds the entries in the order of FR-004:
  - **Publish results** for `can_manage` on `finished`, not destructive;
  - **Download results** for every teacher on `published`, via `menu_link(…, download=True)`;
  - **Answers** and **Grades** on `has_finished`;
  - **Finish competition** and **Cancel competition** unchanged.
- **The confirmation page** `competition_publish.html` is built on the 12.4 non-destructive
  `confirmation(kind="primary")`:
  - it shows the status badge and the progress "Graded 37 of 52 teams" through the `caller()`
    block;
  - while a team is ungraded it uses a new `blocked` state of `confirmation`, which shows the
    explanation as a notice in place of the button and offers an alternative link (**Grade the
    remaining teams**) beside **Keep unpublished**. It is added to the library and the gallery first
    ([contracts/components.md](./contracts/components.md) §3).
- **Routes**: `GET`/`POST /teacher/competitions/{id}/publish`, in `teacher_competitions.py` beside
  finishing, with `PUBLISH_REFUSALS` and the notice `published`. A publish refused as not fully
  graded renders the blocked confirmation with status 409.
- **The progress** comes from `grades.grading_progress(session, competition_id) -> (graded,
  total)`, extracted from `grade_team_page`, which keeps using it.

## R11. The Published badge and the read-only grading sheet

**Decision**:

- **The badge**: `competition_status_badge("published")` renders "Published" with a new badge kind
  `accent`. It is built from existing tokens only (`--sc-accent` background, `--sc-on-accent` text),
  so no new colour token. It stands apart from **Finished** (neutral) and **In progress** (success),
  and the word is always shown (milestone 10 FR-028).
- **The grading sheet**: `grading_sheet` gains `read_only=False` and `note=None`. Read-only, it
  keeps the question, the reference answer and the answer, shows each grade as "Grade: 7 of 10" (the
  12.4 read-only wording), and renders no field and no save button. The note is a notice under the
  heading. This differs from 12.4's `answers_read_only`, which leaves out the reference answers.

Both go into the library, the gallery and `ui-guidelines.md` before a page uses them (Principle II).

## R12. The samples and the design review

**Decision**:

- **The sample script**: `scripts/make_results_samples.py` (stdlib and the application's own
  modules, run with `uv run python scripts/make_results_samples.py`). It builds three snapshots in
  memory:
  1. seven regions and 60 teams, long and Cyrillic names, so the list runs over several pages;
  2. one region with very long institution and team names;
  3. no teams.
- **Output**: it writes each in Ukrainian and English to
  `specs/012.8-publishing-results/samples/<set>-<lang>.pdf`, which are committed as the review
  evidence.
- **The record**: `specs/012.8-publishing-results/design-approval.md` records each round, the
  product owner's requests and the approved round, as in milestone 12.7. The PR is not merged
  before approval (FR-040).

**Rationale**: the samples come from the same renderer as production. Since the renderer is pure,
no database or seed data is needed.

## R13. Languages

**Decision**:

- **Catalogues**: every new text goes into both catalogues and is extracted by the existing
  `scripts/translations.sh`:
  - the menu entries, the confirmation, the explanations and refusals, the notice, the grading note;
  - the file labels: the title, "Started", "Finished", "Published", "Page %(n)d of %(total)d", the
    no-teams line, the team line.
- **The file texts** live in `results_pdf.py` as `_()` messages, so Babel's Python extractor finds
  them.
- **Ukrainian wording** follows the existing catalogue (the guillemets « » of milestone 12.5).
- **The 12.5 catalogue checks** (`test_catalogues.py`, `test_template_text.py`) cover them.

## R14. Tests

**Decision**:

- **New modules**:
  - `tests/unit/test_results_pdf.py`: font coverage; the file name rule; the rendered text of each
    language read back with pypdf (header, labels, region headings, lines, order, page numbers, the
    no-teams line, no answer text); the logo image present; the metadata;
  - `tests/integration/test_results_service.py`:
    - publishing: success, every refusal, not fully graded, no teams;
    - the snapshot: the order, deleted teams, deactivated institutions;
    - the files: exactly two, unchanged after renames, deactivations and deletions;
    - grades frozen; the timing bound;
    - two-session races on PostgreSQL (two publishes; a publish and a grade save in both orders);
  - `tests/integration/test_teacher_results.py`:
    - the confirmation in both states, the landings under each filter, the refusals and the check
      order;
    - the download for every kind of teacher, in both languages, its headers and file name, 404s,
      403 for administrators and students, the cross-site check.
- **Updated modules**:
  - `test_teacher_competitions`: the menu per status and setting, the Published filter and badge;
  - `test_teacher_grades`: the read-only sheet, the refused save;
  - `test_teacher_team_answers`: the pages on Published;
  - `test_competition_service`: `status_of`, `has_finished`, cancel on Published;
  - `test_grade_service`: `GradingClosed(PUBLISHED)`, `grading_progress`;
  - `test_routes`: the two new routes in the sweep;
  - `test_migrations`: the new revision, drift, the stairway;
  - `test_form_contract` and `form_contract.json`: the publish form;
  - `test_component_gallery`, `test_page_patterns`, `test_templates`: the badge, the download entry,
    the blocked confirmation, the read-only grading sheet;
  - `tests/conftest.py`: a `publish` seeder.
- **New development dependency**: `pypdf` (pure Python, BSD), to read text and images back from the
  files. The tests compare bytes for "as stored".

**Rationale**: Principle III; the concurrency cases follow the 12.1–12.4 pattern (PostgreSQL only).

## R15. Documents

**Decision**:

- `docs/requirements/ui-guidelines.md`:
  - the statuses list and the Published badge;
  - the actions menu order and example, and the download entry rule (FR-042);
  - the blocked confirmation;
  - the read-only grading sheet.
- `README.md`:
  - publishing and downloading results;
  - the `fpdf2` dependency and the fonts (source and version);
  - the sample script.
- `docs/requirements/technical-requirements.md` and the constitution already state the rules; this
  plan records the open stack decision (fpdf2, Open Sans). No amendment.
- `milestones.md` moves 12.8 to **Delivered** on delivery.
