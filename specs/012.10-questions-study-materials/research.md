# Research: A Competition's Questions Only After It Starts, and Study Materials (Milestone 12.10)

Each decision below was taken against the code on `main` after milestone 12.9 and the
constitution v2.7.0. The spec had no `[NEEDS CLARIFICATION]` markers. The open points listed in
its checklist (the Ukrainian texts, the Answers pages, line breaks, date formats) take the spec's
documented assumptions, and the design rounds can change them (R11).

## R1. Closing the Questions page to teachers without the setting

**Decision**: `competition_questions_page` (`app/routers/teacher_competition_entries.py`) calls
`require_manage(request, session)` first in the handler, before `find_context`. That is the same
call every *manage* route under it already makes first (`add_questions_page`,
`add_question_action`, `remove_question_page`, `remove_question_action`). The page then always
reads the bank's mark (`with_bank_mark=True`), because only teachers with the setting reach it.
The **Questions** entry in `competitions.html` gets the guard `can_manage`.

**Rationale**: `require_manage` raises the milestone 5 `AccessDenied` before any subject or
competition is looked up. The refusal is therefore the same 403 page for every competition, for a
missing one and for an unknown subject (FR-002, FR-003). Each request reads the setting through
`can_manage_competitions` (FR-005). With this one call the whole `/questions` subtree is a manage
subtree. The teams routes keep their 12.2 split: every teacher reads, only managers change.

**Alternatives considered**:

- *Keep the page open but hide the questions from other teachers*: rejected. The spec wants the
  same refusal for every competition, and an empty page would still show that the competition
  exists and how it is laid out.
- *A 404 for teachers without the setting*: rejected. Milestone 12.9 already answers "access
  denied" for every manage route, and the spec asks for the same.

## R2. The two download addresses and their router

**Decision**: one new thin router, `app/routers/teacher_question_files.py`, with two `GET`
routes, both `@allow_roles(Role.TEACHER)`:

- `GET /teacher/competitions/{competition_id:int}/questions-file?subject=<id>`: the questions
  file. It does not sit under `/questions`, which is now the managers' subtree (R1), so every
  teacher's download never has to make an exception inside it.
- `GET /teacher/competitions/study-materials?subject=<id>`: the study materials of the subject the
  Competitions tab has chosen. `{competition_id:int}` only matches digits, so this path cannot
  collide with a competition's routes, nor with `/teacher/competitions/new`.

Both answer with the bytes and the same headers as **Download results**. Those are a
`Content-Disposition: attachment` with an ASCII `filename=` and the full name in `filename*`,
`Cache-Control: no-store` (the language cookie picks the file) and `X-Content-Type-Options:
nosniff`. That response is built in one place: a `pdf_download(content, file_name)` helper moves
out of `teacher_results.py` into `app/routers/downloads.py`, and all three downloads use it.

**Order of checks**:

- **Questions file**:
  1. the role;
  2. the subject, through `offered_subject(offered_subjects(session), subject)`, else "Subject
     not found" (the 12.1 text and page);
  3. the competition, through `find_competition`, which must be **In progress**, **Finished** or
     **Published** (`CompetitionStatus`), else "Competition not found".

  A deactivated subject's **In progress** competitions are hidden, so `find_competition` gives
  `None` for them, as milestone 12.1 does for every competition route (FR-008).
- **Study materials**:
  1. the role;
  2. the subject must exist and be active (`questions.get_active_subject`). Otherwise the answer is
     404 with the Questions tab's text "This subject does not exist or is deactivated.", shown on
     the Competitions tab's not-found page (FR-023).

The setting is never read: every teacher downloads (FR-006, FR-021).

**Rationale**: these are the patterns of `teacher_results.download_results`, so the 404 pages and
headers are the same. Every id comes from a parsed number or a row that was looked up.

**Alternatives considered**:

- *Adding the routes to `teacher_results.py`*: rejected. That module is about the stored results
  snapshot, and these files are made on demand.
- *`/teacher/subjects/{id}/study-materials`*: rejected. There is no teacher **Subjects** area,
  and the link lives on the Competitions tab with the `subject=` parameter that tab already uses.

## R3. Sharing the results file's design

**Decision**: the drawing code that `results_pdf.py` shares goes into
`app/services/pdf_layout.py`:

- the constants: fonts, sizes, colours, margins, the logo path;
- the A4 document class with its running title and its "Page n of N" footer;
- `open_document(title, language, created_at)`;
- `draw_header(document, title, subject, meta_lines)`.

`results_pdf.render_results_pdf` calls these functions. The new renderers sit in
`app/services/question_files_pdf.py`:

- `render_questions_pdf(sheet, language)`;
- `render_study_materials_pdf(materials, language)`.

Both are pure: no session, no request, no clock.

**The refactor must not change the results file**: `scripts/make_results_samples.py` writes the
12.8 samples byte for byte from fixed data. After the refactor it must leave
`specs/012.8-publishing-results/samples/` unchanged in `git status`, and `test_results_pdf.py`
must stay green.

**Rationale**: FR-012 and FR-025 ask for "the design of the results file, with the logo at the
same size". Shared code keeps the three files alike as the design rounds change them. Being pure
keeps the renderers testable and lets the sample script call them without a database, as in 12.8.

**Alternatives considered**:

- *Copying `_ResultsDocument` and the header code*: rejected. The three files would drift apart
  through the design rounds.
- *Generalising `render_results_pdf` with flags*: rejected. The bodies differ entirely (a table
  per region against a numbered list).

## R4. Laying out the numbered list

**Decision**:

- **Numbering**: each entry draws its number ("12.") in a fixed column, as wide as the widest
  number of the file in bold. Its text goes in a `multi_cell` to the right of the number, so
  wrapped lines align under the text.
- **Answers**: in the study materials, the reference answer follows below the question, indented
  like the text. The label "Answer:" is drawn in bold with `write()` and the answer in regular
  type, with the left margin set to the indent while it is written, so wrapped lines align.
- **No markdown**: user text is never passed to fpdf2's markdown mode, so `**` in a question stays
  as typed.
- **Line breaks** in texts and answers are kept: `multi_cell` and `write` honour `\n`.
- **Keeping an entry together** (FR-040):
  1. Before an entry is drawn, its height is measured with a dry run (`multi_cell(...,
     dry_run=True, output="HEIGHT")` for each part, plus the gaps).
  2. If the entry fits on an empty page but not on the rest of this one
     (`document.will_page_break(height)`), a page is added first.
  3. An entry taller than a page is drawn as it comes, and the automatic page break splits it.
- **Empty files**: the questions file says "This competition has no questions." and the study
  materials say "This subject has no questions yet.", in the place where the results file says
  "No teams took part in this competition.".

**Rationale**: these are the same building blocks the results file uses (`will_page_break`,
`multi_cell`) and need no new library. The exact spacing, sizes and label style are the starting
point of the design rounds (FR-046).

**Alternatives considered**:

- *`unbreakable()`*: rejected. Its behaviour for blocks taller than a page is not what FR-040
  asks for: those must split.
- *A two-column `table()`*: rejected. A table row cannot hold a label and its text in two styles
  without markdown.

## R5. What each file is made from

**Decision**: two frozen dataclasses in `app/services/question_files.py`. They are the renderers'
only inputs, and in the study materials they are also the key the kept file is compared with.

- **`QuestionsSheet`** holds `competition_name`, `subject_name`, `starts_at` and `texts:
  tuple[str, ...]`. The texts are `competition_entries.question_copies(session, id)` in their
  order, each the copy's `text`. Additional questions and copies of deleted bank questions are
  included (FR-014, FR-016). `subject_name` is read from the `subjects` row at the download, so a
  rename shows (FR-018).
- **`StudyMaterials`** holds `subject_name`, `downloaded_on` (a `date`, the Kyiv day) and
  `entries: tuple[tuple[str, str], ...]` (text, reference answer). The entries come from one
  query:

  ```
  select(Question.text, Question.reference_answer)
  .where(subject_id == s, deleted_at IS NULL, is_additional IS FALSE)
  .order_by(Question.id)
  ```

  The id is given in creation order and never reused, so `id` ascending is "oldest first"
  (FR-027, FR-028). Bank numbers are never read into the sheet, so they cannot be drawn.
- **The PDF creation date** is the competition's start for the questions file, and the Kyiv
  midnight of `downloaded_on` for the study materials. Every byte of a file then follows from
  its inputs and the language, which makes the samples repeatable and lets tests compare bytes.
- **The clock** is read through `app.services.competitions.utc_now`, as 12.8 does, so tests that
  move the 12.1 clock move this one.

**Rationale**: a file that depends only on these values makes "nothing it shows has changed" an
equality test on a value object (R6). Leaving the bank number out of the sheet makes FR-015 and
FR-028 hold by construction.

## R6. Keeping the study materials in memory, never stale

**Decision**: a small class `StudyMaterialsCache` in `app/services/question_files.py`, one
instance per running application. `lifespan` creates it in `app.state.study_materials`, so it is
empty at every start: a restart, a deployment or a wake from sleep (FR-037). Each `TestClient`
gets a fresh one.

- **What it keeps**: `dict[(subject_id, language), Kept]`, where `Kept` is the `StudyMaterials` the
  file was made from plus the file's bytes. That is at most one entry per subject and language
  (FR-032).
- **How a download is served**:
  1. The router checks the subject (R2).
  2. It builds `StudyMaterials` from the database (one quick query, R5) with today's Kyiv date.
  3. It calls `cache.file_for(subject_id, language, materials, render)`.
- **Inside `file_for`**, under a per-key `threading.Lock`:
  1. If a file is kept for the key and its `materials` equal the ones just read, the kept bytes
     are returned.
  2. Otherwise the file is rendered from the materials just read, stored in place of the old one
     and returned.
- **No invalidation**: no other module knows about the cache (FR-034). Every kind of change shows
  as a difference in the values read: a question added, edited, deleted or (un)marked; a rename;
  a change made straight in the database; the other language (another key); a new Kyiv day.
- **A change during rendering** (FR-035): a file is stored only with the materials it was made
  from. A download after the change reads the new values, which do not match, so it makes the
  file again.

  The subject's name and the questions are read in two statements, so on PostgreSQL READ
  COMMITTED a rename between them can give materials that mix two moments. The file then shows
  exactly those values, and the next download reads values that no longer match, so it is made
  again. No file is ever given for values older than those its own request read.
- **Simultaneous downloads** (FR-036): requests for the same key queue on the key's lock. The
  first renders. The others find the kept file matching their own materials and take it. Requests
  whose materials differ (one read before a change, one after) each render in turn, which is
  correct. A global lock guards only the creation of the per-key locks.
- **Concurrency model**: the server runs one uvicorn process (`Dockerfile` `CMD`), and the
  handlers are synchronous, so they run in its thread pool. Process memory and `threading` locks
  are therefore enough. If the hosting plan ever ran more processes, each would keep its own
  files: still correct, only made more often (spec Assumptions).
- **Logging**: nothing is logged on a download, as for **Download results**.

**Rationale**: comparing what was read with what the file was made from is the only approach the
milestone allows ("without any of them having to know about the kept file"). It is correct even
for changes made outside the application. Reading the inputs is cheap (one indexed query of
about 150 short rows), while rendering is the slow part. The constitution's "PDF files" row
allows memory, which is no new infrastructure.

**Alternatives considered**:

- *Invalidating on writes in `questions` and `subjects`*: rejected. It misses changes made
  outside the application, and the milestone forbids it.
- *A version counter or `updated_at` maximum*: rejected. Deleting a question does not change
  `updated_at` (milestone 11), and a change made straight in the database may not either.
- *A hash of the inputs instead of the inputs*: no gain. The inputs are a few tens of kilobytes,
  and equality on them cannot collide.
- *Storing the file in the database*: forbidden by FR-031.
- *`functools.lru_cache`*: it has no single-flight and no "replace on mismatch" for a key.

## R7. File names

**Decision**: a new `app/services/file_names.py` takes the 12.8 cleaning out of `results.py`:

- `_UNSAFE`, control characters and trailing dots, as `clean_file_stem(text, fallback)`;
- `ascii_file_name`, moved unchanged.

`results_file_name` keeps its output and uses them. The new names are whole messages in the file's
language, made under `use_language(language)`:

- `_("%(name)s %(date)s questions", ...)`, with the competition's name and its start date in Kyiv
  time;
- `_("%(subject)s %(date)s study materials", ...)`, with the subject's name and the Kyiv date of
  the download.

The cleaned stem gets `.pdf`. In Ukrainian they are «%(name)s %(date)s питання» and «%(subject)s
%(date)s навчальні матеріали». The name is cleaned before it is put into the message.

**Rationale**: whole messages, as milestone 12.5 requires (no gluing of translated pieces). The
file-name rule is the one from 12.8 (FR-041).

## R8. The Download study materials link beside the subject list

**Decision**:

- **Two additions to existing components**. They are added to the library, the gallery
  (`/admin/components`, its selectors and buttons sections) and the UI guidelines before the
  Competitions tab uses them (FR-024):
  1. `chained_lists(levels, action, aside=None)`: when `aside` is given, its HTML is rendered as
     one more cell of the selectors' grid, after the levels, bottom-aligned with the selects.
     Wide screens already give the chained lists three columns, and the tab uses two (subject,
     status), so the link takes the third. On a phone the grid is one column, so the link stacks
     under the lists.
  2. `link_button(..., download=False)`: a `download` attribute, as `menu_link` got in 12.8.
     The loading script already skips `a[download]`.
- **On the tab**, the aside is `link_button(_("Download study materials"),
  "/teacher/competitions/study-materials?subject=<id>", kind="secondary", outline=True,
  small=True, download=True)`. It is given only when a subject is chosen and `selected.is_active`
  (FR-020). The page shows it to every teacher (FR-021).
- **Without JavaScript** it is a plain link (FR-022).

**Rationale**: no existing component puts a link beside the chained lists. A free-standing
`link_button` under the lists would fail "beside the list" on a wide screen. The variant is the
smallest change that is still a library pattern and not built on one page. Its look and place are
then approved in the design rounds (FR-048).

**Alternatives considered**:

- *An action in `page_heading`*: rejected. That place belongs to the primary **Add competition**,
  and the link would sit far from the subject it downloads.
- *A plain text link*: possible. The secondary outline small button is the starting point, and
  the product owner may choose otherwise in the rounds.

## R9. The actions menu

**Decision**: `competitions.html` lists **Questions** under `can_manage`. **Download questions**
comes after **Answers**, under `c.status in ("in_progress", "finished", "published")`, as
`menu_link(_("Download questions"), "/teacher/competitions/<id>/questions-file?subject=<selected.id>",
download=True)`. The resulting order is that of FR-010. A deactivated subject's list shows only
its finished and published competitions (12.1), so the entry there follows FR-008 with no extra
condition. The template's header comment and the UI guidelines' menu order and example are
updated.

## R10. Tests

**Decision**: pytest on both engines, as every milestone does.

- **New modules**:
  - `tests/unit/test_question_files_pdf.py`: the renderers on in-memory sheets:
    - header lines, and no others;
    - numbering, order, texts and answers;
    - no bank numbers or marks;
    - the empty sentences;
    - both languages and Cyrillic text;
    - several pages for 150 entries, with the running title and "Page n of N";
    - an entry not split unless taller than a page;
    - the same input giving the same bytes.
  - `tests/unit/test_study_materials_cache.py`: a kept file returned when the materials are equal
    and made again when not; replacement; separate keys per language; single-flight with two
    threads and a barrier (one render).
  - `tests/integration/test_teacher_question_files.py`: the two routes through `TestClient`:
    - access per role and setting (managers, Read and Write teachers, linked or not; 403 for
      administrators and students before any id is read);
    - every status, the deactivated subject cases and the 404 pages;
    - headers and file names in both languages;
    - content read back with `tests/pdf.py`: additional questions included in the questions file
      and left out of the study materials (also for a manager); deleted questions; copies against
      later bank edits; a subject rename; cancelling while In progress;
    - the kept file through the route, by counting calls to the renderer (monkeypatched at
      `question_files_pdf.render_study_materials_pdf`), after each change in FR-034:
      - add, edit, delete, mark and unmark a question, and rename the subject;
      - change a question's text or reference answer with a raw SQL `UPDATE` on the engine;
      - download in the other language, and on the next day by moving the clock;
    - a change that overlaps a render: the counting wrapper commits a change while rendering,
      and the next download makes the file again and shows the change;
    - deactivating the subject after a file was kept: 404;
    - a fresh application (new `TestClient`) making the file again.
- **Updated modules**:
  - `test_teacher_competition_entries.py`: the Questions page and the pages under it refuse
    Read and Write teachers without the setting in every status and for missing ids. Its
    existing "every teacher reads" cases become managers-only. Teams stays open to all.
  - `test_teacher_competitions.py`: the menu per status and setting, and its order.
  - `test_routes.py` and `test_access_control.py`: the route registry and its role sweep.
  - `test_component_gallery.py`: the aside and the download `link_button`.
  - `test_results_pdf.py`: unchanged; it must stay green after R3.
  - `test_catalogues.py`: unchanged; it checks the new messages.
- **The manual design approval** (FR-049) and the 360 px look are checked by hand, with
  screenshots made by an ad hoc Playwright run (see quickstart).

## R11. Samples and the design approval record

**Decision**: `scripts/make_question_file_samples.py`, in the manner of `make_results_samples.py`.
It builds sheets in memory from invented realistic data and writes these files to
`specs/012.10-questions-study-materials/samples/`:

- `questions-long-{uk,en}.pdf`: long Ukrainian questions, enough to continue across pages, with
  the apostrophe and the letters ґ, є, ї;
- `questions-empty-{uk,en}.pdf`;
- `study-materials-150-{uk,en}.pdf`;
- `study-materials-empty-{uk,en}.pdf`.

The output is byte-stable (R5). The screenshots of the Competitions tab (wide and 360 px, both
languages and both themes) are made against a copy of the development database, following the
project's browser-screenshot routine. Rounds and decisions are recorded in
`specs/012.10-questions-study-materials/design-approval.md`. The approval is its own task, and the
milestone is not delivered before it (FR-049).

## R12. Performance

**Decision**:

- **Questions file**: about ten entries, rendered at every download; well under a second
  (SC-008).
- **Study materials of 150 questions**: rendered once per change, then served from memory. The
  target for a kept file is a response within 1 s (SC-005). It needs one indexed query
  (`ix_questions_subject_id`) and a tuple comparison.
- **Measurement**: the first render's time is measured on the samples script, and noted in
  `design-approval.md` for the record. No target is set for it beyond the spec's.
