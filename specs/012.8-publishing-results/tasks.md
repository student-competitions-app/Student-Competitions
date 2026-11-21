---

description: "Task list for milestone 12.8: publishing a competition's results as PDF files (teacher)"
---

# Tasks: Publishing a Competition's Results as PDF Files (Teacher) (Milestone 12.8)

**Input**: Design documents from `/specs/012.8-publishing-results/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[contracts/results-file.md](./contracts/results-file.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-048 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R14.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`. The two-session race tests run on PostgreSQL only (skip on SQLite), with the
  `threading.Barrier` pattern of `tests/integration/test_competition_service.py` (the 12.4 finish
  races) and `tests/integration/test_grade_service.py`.
- **Seeders** (existing): `make_teacher(engine, settings, email=..., institutions={}, can_manage=...)`,
  `make_subject`, `make_question`, `make_institution(..., region=..., region_active=...)`,
  `make_team(engine, institution_id, name, deleted=...)`, `make_competition(engine, subject_id, name,
  starts_at=..., cancelled=..., stopped=...)`, `add_competition_question`, `add_competition_team`,
  `save_team_answer`, `grade_answer`. **New** (T016): `make_competition(..., published=...)` and
  `store_results_files`.
- **The clock**: tests control "now" with
  `monkeypatch.setattr("app.services.competitions.utc_now", lambda: fixed)`.
  `app/services/results.py` reads the clock **through that module attribute**
  (`competitions.utc_now()`), as `grades.py` does, so the same patch moves it. No test sleeps.
- **Reading files back**: `pypdf.PdfReader(io.BytesIO(content))`, text through
  `page.extract_text()`, metadata through `reader.metadata`, images through `page.images`. A small
  helper `pdf_text(content: bytes) -> str` (all pages joined with `"\n"`) lives in `tests/pdf.py`
  (T003), beside `tests/html.py`.

**Organization**: tasks are grouped by user story (US1–US9 in spec.md).

- **Phase 1** is the dependencies, the fonts and the four component additions with the gallery and
  the guidelines, because the constitution puts the library, the gallery and the guidelines before
  any page (FR-041–FR-046). It delivers **US9**.
- **Phase 2** is the schema and migration, the **Published** status and its call sites, the
  grading progress, the snapshot and the renderer (the initial design of research R8), and the
  seeders. Every later story needs them.
- **US1** (publish), **US2** (only when fully graded) and **US7** (download) are the MVP: a graded
  competition is published and its file downloaded.
- **US3** (refusals and races), **US4** (the status and filter), **US5** (frozen grades) and
  **US6** (the files' content and permanence) complete the rules.
- **US8** (design approval) runs through the review rounds and closes the milestone.

**Reference implementation**: milestones 12.1–12.7 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**:
  - `app/services/competitions.py`: `finish_competition` step by step (`_require_manage`,
    `lock_competition`, `status_of` with a fresh clock, `_listed` before and after, the conditional
    `update(...)` with `rowcount`, `_reread_status`, `landing`, the log line); `_refuse`; the module
    docstring's "Contract for later milestones";
  - `app/services/grades.py`: `grade_counts`, `count_of`, `grade_team_page`'s `teams_graded`,
    `save_grades`'s lock order, `_rollback`;
  - `app/services/competition_entries.py`: `team_entries`, `TeamEntry`;
  - `app/core/i18n.py`: `use_language`, `Language`;
  - `app/core/time_zone.py`: `format_local_time(moment, None)`, `format_local_date`, `KYIV`;
  - `app/schemas/names.py`: `name_sort_key`.
- **Routers**:
  - `app/routers/teacher_competitions.py`: the finish pair `finish_competition_page` /
    `finish_competition_action`, `FINISH_REFUSALS`, `_finish_refused`, `_refused`, `NOTICES`,
    `_notice_token`, `require_manage`, `list_path`, `offered_subject`, `find_competition`,
    `not_found`, `redirect`, `SUBJECT_NOT_FOUND`, `COMPETITION_NOT_FOUND`;
  - `app/routers/teacher_grades.py`: `_open`, `grades_path`, `GRADE_REFUSALS`, `grades_refused`,
    `_render_sheet`, `save_grades_action`;
  - `app/routers/teacher_team_answers.py`: `_open`, `_PAGE_STATUSES`, `ANSWER_REFUSALS`.
- **Templates**:
  - pages: `pages/teacher/competition_finish.html`, `competition_refused.html`, `competitions.html`,
    `team_grading_sheet.html`;
  - components: `confirmation.html`, `badge.html`, `menu.html`, `grading_sheet.html`,
    `feedback.html`;
  - the gallery `app/templates/pages/admin/components.html` with `app/routers/admin_components.py`
    (`_samples`, `COMPETITION_STATUSES`); `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Migration**: `migrations/versions/2026_11_14_04d5b638615c_answer_grades.py` (frozen snapshot,
  `op.f` names, `batch_alter_table`); the head is `7110bec350d2`.
- **Scripts**: `scripts/make_logo.py` (a stand-alone script that writes committed files; its
  docstring style).
- **Tests**:
  - the 12.4 tests: `tests/integration/test_teacher_competitions.py` (the finish landings, menus,
    refusals), `test_teacher_grades.py`, `test_grade_service.py`, `test_competition_service.py`;
  - the cross-cutting checks: `test_routes.py`, `test_form_contract.py` with `form_contract.json`,
    `test_page_patterns.py`, `test_component_gallery.py`, `test_migrations.py`;
  - the helpers and unit tests: `tests/unit/test_templates.py`, `tests/html.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks, publishing** (FR-034):
  1. the role (`@allow_roles(Role.TEACHER)`): 403 before any id is read;
  2. the setting (`require_manage(request, session)`, the first statement of the handler): 403
     before any value is parsed, also for unknown ids;
  3. the subject (`offered_subject`, "Subject not found" 404), then the competition
     (`find_competition`, "Competition not found" 404);
  4. the status (`PUBLISH_REFUSALS`, 409);
  5. the grading (the blocked confirmation, 409 on `POST`);
  6. the service repeats 2–5 under lock.
- **Order of checks, download**: the role → the subject → the competition (any status but
  **Published** → "Competition not found" 404). **No setting check.**
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON. Ids go through `parse_id`, pages through `parse_page`,
  the status filter through `parse_status_filter`.
- **Redirects**: every change is a `POST` through the existing cross-site check, answering `303`, so
  a reload never repeats it (FR-035).
- **Notices** travel sealed, holding the competition id and the outcome only; the text is built
  when the list is shown.
- **Logging**: services log ids, counts and sizes only, exactly `Results published: id=%d teams=%d
  bytes=%d`. A refusal and a download log nothing. No name of any kind ever reaches a log line or an
  address.
- **Files**: `competition_results_files` rows are inserted only by `results.publish_results`. No
  code path issues an `UPDATE` or `DELETE` on that table (data-model.md §4).
- **Messages**: every new user-facing text goes through `_()` (Python) or `{{ _("…") }}`
  (templates) as one whole message (milestone 12.5 FR-021). It is extracted with
  `scripts/translations.sh update`, and the Ukrainian entry is translated in
  `app/locale/uk/LC_MESSAGES/messages.po` (guillemets « », impersonal status words), never left
  fuzzy.
- **Components first**: each addition is in the library, its CSS in the Components section of
  `app/static/css/app.css` (tokens only, no inline style, no literal colour, no new token), the
  gallery and `ui-guidelines.md` **before** a page uses it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US9)

---

## Phase 1: Setup (Dependencies, fonts, components and documents first)

**Purpose**: the two new dependencies and the fonts; the **Published** badge, the download entry,
the blocked confirmation and the read-only grading sheet, in the library, the gallery and the
guidelines (research R1, R2, R11, contracts/components.md §1–§4, §6). Nothing here touches the
database. Delivers **US9**.

- [X] T001 Add the dependencies in `pyproject.toml` and `uv.lock` per research R1, R14:
  - run `uv add "fpdf2>=2.9"` (runtime) and `uv add --dev pypdf` (development), then
    `uv lock --check`;
  - confirm that `uv sync --locked --no-dev` (the Dockerfile's command) installs fpdf2, Pillow and
    fontTools, and not pypdf;
  - the `logo` dependency group (`pillow`, `numpy`) stays as it is.
- [X] T002 [P] Commit the fonts `app/static/fonts/OpenSans-Regular.ttf` and `app/static/fonts/OpenSans-Bold.ttf` per research R2:
  - take the static TrueType instances from the upstream Open Sans release (googlefonts/opensans,
    `fonts/ttf/`); record the release tag and the two files' SHA-256 for the README (T066);
  - they are covered by the existing `app/static/fonts/OFL.txt`; add no other font file.
- [X] T003 [P] Create `tests/pdf.py` (depends on T001), a test helper beside `tests/html.py`:
  - `pdf_text(content: bytes) -> str`: every page's `extract_text()` joined with `"\n"`;
  - `pdf_pages(content: bytes) -> int`;
  - `pdf_metadata(content: bytes) -> dict[str, str]`;
  - `pdf_images(content: bytes, page: int = 0) -> int`: the number of images on that page;
  - `pdf_fonts_embedded(content: bytes) -> bool`: every font of every page has a `/FontFile2` in
    its descriptor.
  - A docstring: test-only, reads with pypdf, never imported by `app/`.
- [X] T004 [P] Add the `accent` badge and the **Published** status badge per contracts/components.md §1:
  - in `app/templates/components/badge.html`:
    - `badge`'s `badge_classes` gains `"accent": "badge badge-accent"`;
    - `competition_status_badge` gains `{%- elif value == "published" %}{{ badge(_("Published"), "accent") }}`
      between `finished` and `cancelled`;
    - update the header comment (five statuses);
  - in the badge section of `app/static/css/app.css`:
    `.badge-accent { background: var(--sc-accent); color: var(--sc-on-accent); }`.
- [X] T005 [P] Add the download entry to `app/templates/components/menu.html` per contracts/components.md §2:
  - the signature becomes `menu_link(label, href, destructive=False, download=False)`;
  - with `download=True`, the `<a>` gets the bare attribute `download`;
  - `destructive=True` together with `download=True` is `template_error("menu_link: a download is never destructive")`;
  - existing calls render byte-for-byte as before;
  - the header comment gains: "A download is an entry like any other, a link marked as a download:
    it opens no page, and the loading script of milestone 10.1 never starts for it (it skips
    `a[download]`)."
- [X] T006 [P] Add the blocked state to `confirmation` in `app/templates/components/confirmation.html` per contracts/components.md §3:
  - the signature becomes `confirmation(question, consequence, action, verb, cancel_href, hidden={}, back_label=None, kind="destructive", blocked=None, alternative=None)`;
  - with `blocked` (a reason):
    - no `post_button`; `notice(blocked, "info")` above `.form-actions`;
    - in `.form-actions`, the `alternative` link (`(label, href)`) when given, then the back link;
  - `blocked` together with `kind="destructive"` is
    `template_error("confirmation: only a primary confirmation can be blocked")`;
  - `alternative` without `blocked` is a template error;
  - without `blocked`, the markup is byte-for-byte the current one;
  - extend the header comment with the rule of contracts/components.md §3.
- [X] T007 [P] Add the read-only state to `grading_sheet` in `app/templates/components/grading_sheet.html` per contracts/components.md §4 and research R11:
  - the signature gains `read_only=False, note=None`; `note` is accepted only with `read_only`
    (template error otherwise);
  - read-only:
    - `notice(note, "info")` first when given;
    - the same `<ol class="answer-sheet">` of text cards with the question, "Reference answer" and
      "Answer to question <n>";
    - under each answered question, `<p class="grade-line">Grade: <g> of 10</p>`, or
      `<p class="grade-line">Not graded yet</p>` if `None`; "Not answered" as now;
    - no `<form>`, no field, no error, no button;
  - the editable state is byte-for-byte unchanged;
  - extend the header comment.
- [X] T008 Add the gallery entries (depends on T004–T007):
  - `app/routers/admin_components.py`:
    - `COMPETITION_STATUSES = ("upcoming", "in_progress", "finished", "published", "cancelled")`;
    - a read-only grading sample: the three items of the existing grading sample with grades
      `7`, `None` (unanswered) and `10`, plus the note "The results of “Spring round” are
      published, so its grades can no longer be changed.";
  - `app/templates/pages/admin/components.html`:
    - in the status badges sample, the five badges in the filter's order;
    - in `#actions-menu`, the full example menu becomes **Questions**, **Teams**, **Answers**,
      **Grades**, **Download results** (`download=True`), as a published competition shows it to a
      teacher with the setting; keep the existing destructive **Cancel competition** sample
      elsewhere in the section;
    - in `#confirmations`, two new samples:
      - the ready publish confirmation: `confirmation("Publish the results of “Spring round” of
        Chemistry, started 14 March 2027, 10:00?", "The results will be published for every
        teacher as PDF files in Ukrainian and English. Publishing is permanent: the results cannot
        be unpublished, and the grades can no longer be changed.", "#", "Publish results",
        "#confirmations", back_label="Keep unpublished", kind="primary")`, whose caller block holds
        the **Finished** badge and "Graded 52 of 52 teams";
      - the blocked one, the same with "Graded 37 of 52 teams", `blocked="Every team must be graded
        before the results can be published."` and `alternative=("Grade the remaining teams",
        "#confirmations")`;
    - in `#grading-sheet`, the read-only sample with its note.
- [X] T009 [P] Update `docs/requirements/ui-guidelines.md` per contracts/components.md §6 (depends on T004–T007):
  - **Statuses**: five statuses, **Published** ("a finished competition whose results are
    published") with the `accent` badge;
  - **Actions menu**: the Competitions entries in the order **Edit**, **Questions**, **Teams**,
    **Answers**, **Grades**, **Publish results**, **Download results**, **Finish competition**,
    **Cancel competition**; the example template for a published competition; the download rule
    of FR-042 ("a download is offered as a link marked as a download, never through a page in
    between, and it starts no loading feedback");
  - **Confirmations**: the blocked state of FR-046 (only a primary confirmation can be blocked; the
    reason in place of the button, a link to the work left, the link back); **Publish results** /
    **Keep unpublished** among the primary confirmations;
  - **Grading sheet**: the read-only state with its note;
  - **Wording patterns**: the notice "The results of “<name>” were published", the refusal reasons
    of contracts/http-routes.md §2;
  - gallery links for each.
- [X] T010 [P] Extend the component tests (depends on T008):
  - `tests/integration/test_component_gallery.py`:
    - the status badges sample shows five badges in order, **Published** with `badge-accent`;
    - `#actions-menu` holds an `a[download]` "Download results" that is not destructive;
    - `#confirmations` has the ready publish confirmation (a primary submit **Publish results**,
      the link **Keep unpublished**) and the blocked one (no submit, the explanation as a notice,
      the links **Grade the remaining teams** and **Keep unpublished** in that order);
    - `#grading-sheet` has a read-only sample with the note, "Reference answer", "Grade: 7 of 10",
      "Not answered" and "Grade: 10 of 10", and no `form`, `input` or button;
  - `tests/unit/test_templates.py`:
    - `menu_link` without `download` is unchanged, and with both flags is a template error;
    - `confirmation` without `blocked` is byte-for-byte as before; `blocked` with `destructive` and
      `alternative` without `blocked` are template errors;
    - `grading_sheet` editable is unchanged; `note` without `read_only` is a template error;
    - `competition_status_badge("published")` renders "Published" with `badge-accent`;
  - `tests/unit/test_stylesheet.py` stays green.

**Checkpoint**: dependencies installed, fonts committed, and the four additions are in the library,
the gallery and the guidelines; every existing page renders as before. US9 is done.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the column, the table and the migration; the **Published** status and every call site;
the grading progress; the snapshot and the renderer; the seeders (data-model.md, research R3–R8,
contracts/services.md §1–§5).

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end.

- [X] T011 Add the column and the table to `app/models/competition.py` per data-model.md §1–§2:
  - `Competition.published_at: datetime | None = Field(default=None, sa_type=UTCDateTime, nullable=True)`
    with the docstring "Set once by `app.services.results.publish_results` (milestone 12.8), only
    while the competition is Finished and fully graded; never cleared.";
  - `CheckConstraint("published_at IS NULL OR stopped_at IS NOT NULL", name="published_after_finish")`
    in `Competition.__table_args__`;
  - `class CompetitionResultsFile(SQLModel, table=True)`, `__tablename__ = "competition_results_files"`:
    - `competition_id: int = Field(foreign_key="competitions.id", primary_key=True)` (no `ON DELETE`);
    - `language: str = Field(sa_column=Column(String(2), primary_key=True))`;
    - `content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))`;
    - `CheckConstraint("language IN ('uk', 'en')", name="results_file_language")`;
    - `CheckConstraint("length(content) > 0", name="results_file_not_empty")`;
    - a class docstring: the stored snapshot, one row per language, inserted only by
      `publish_results`, never updated or deleted, not personal data;
  - export `CompetitionResultsFile` from `app/models/__init__.py`;
  - update the docstrings of `Competition` (the status now also derives **Published** from
    `published_at`) and `TeamAnswer` (a grade never changes once the competition is published), and
    the module docstring (cite specs/012.8-publishing-results/data-model.md §1–§2).
- [X] T012 Create the migration `migrations/versions/2026_11_<dd>_<rev>_published_results.py` (`down_revision = "7110bec350d2"`) per data-model.md §6 (depends on T011):
  - generate the id with `uv run alembic revision -m "published results"` and write the operations
    by hand as a frozen snapshot (plain SQLAlchemy types, nothing imported from `app`);
  - upgrade:
    - `with op.batch_alter_table("competitions") as batch:`
      `batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))`
      (the type `72e46cb10175` used for `stopped_at`) and
      `batch.create_check_constraint(op.f("ck_competitions_published_after_finish"),
      "published_at IS NULL OR stopped_at IS NOT NULL")`;
    - `op.create_table("competition_results_files", sa.Column("competition_id", sa.Integer(),
      nullable=False), sa.Column("language", sa.String(length=2), nullable=False),
      sa.Column("content", sa.LargeBinary(), nullable=False), …)` with the foreign key to
      `competitions.id`, the primary key `(competition_id, language)` and the two check
      constraints, all named through `op.f` as the naming convention does;
  - downgrade: drop the table, then the constraint and the column in a batch;
  - a module docstring in the style of `04d5b638615c`'s; run `uv run alembic upgrade head`
    locally.
- [X] T013 [P] Extend `tests/integration/test_migrations.py` (depends on T012):
  - the head is the new revision, and the stairway and drift checks cover it on both engines;
  - a finished competition inserted at `7110bec350d2` is kept with `published_at` `NULL`;
  - after upgrade:
    - setting `published_at` on a competition with `stopped_at` `NULL` fails with an integrity
      error;
    - a results file with `language` `'de'` or empty `content` fails;
    - a second row for the same `(competition_id, language)` fails;
  - downgrade to `7110bec350d2` drops the table and the column and keeps every competition.
- [X] T014 Add the status to `app/services/competitions.py` per contracts/services.md §4 and research R4 (depends on T011):
  - `CompetitionStatus.PUBLISHED = "published"`, declared between `FINISHED` and `CANCELLED`, and
    `_LABELS[PUBLISHED] = _("Published")`;
  - the property `has_finished` (`self in (FINISHED, PUBLISHED)`) with a docstring: "has ended";
    every Finished rule holds; only the grades differ;
  - `status_of`: after `cancelled_at`, `if row.published_at is not None: return PUBLISHED`, then
    `stopped_at`;
  - `cancel_competition` refuses `PUBLISHED` like `FINISHED` (`NotCancellable(current)`);
  - `update_competition` already refuses every non-Upcoming status; check it raises
    `NotEditable(PUBLISHED)`;
  - the module docstring: the status list; the "Contract for later milestones" gains
    "`published_at` is written once by `app.services.results.publish_results` (milestone 12.8);
    milestone 13 never evaluates or grades a Published competition; milestone 14 shows results only
    for Published competitions".
- [X] T015 Move every status call site to the new status per research R4's table (depends on T014):
  - **`app/routers/teacher_competitions.py`**:
    - `EDIT_REFUSALS`, `CANCEL_REFUSALS` and `FINISH_REFUSALS` gain `CompetitionStatus.PUBLISHED`
      mapped to the same text as `FINISHED` in each ("“%(name)s” has finished and can no longer be
      edited.", "… has finished and cannot be cancelled.", "… has already finished.");
    - `STATUS_OPTIONS` picks up **Published** from the enum order; check that `parse_status_filter`
      accepts `"published"`;
  - **`app/routers/teacher_team_answers.py`**:
    - `_PAGE_STATUSES = (IN_PROGRESS, FINISHED, PUBLISHED)`;
    - `ANSWER_REFUSALS[PUBLISHED]` = the `FINISHED` text;
    - both `finished = competition.status is CompetitionStatus.FINISHED` lines become
      `competition.status.has_finished`;
  - **`app/routers/teacher_grades.py`**:
    - `_open`: `if not competition.status.has_finished:` → the refusal (the read-only behaviour on
      Published is US5);
    - `GRADE_REFUSALS[PUBLISHED]` = `_("The results of “%(name)s” are published, so its grades can
      no longer be changed.", name=name)`, so the `GradingClosed(PUBLISHED)` that `save_grades`
      raises once publishing exists (T026) never meets a missing key. Until T038 a late save gets
      this text on the 12.4 refusal page; T038 replaces that with the read-only sheet and the same
      note, and removes the entry if nothing else reads it;
  - **`app/templates/pages/teacher/competitions.html`**:
    - **Answers** on `c.status in ("in_progress", "finished", "published")`;
    - **Grades** on `can_manage and c.status in ("finished", "published")`;
    - **Publish results** and **Download results** come in US1 and US7;
  - **`app/templates/pages/teacher/competition_answers.html`**: `finished` becomes
    `competition.status in ("finished", "published")`;
  - grep `app/` for `CompetitionStatus.FINISHED`, `"finished"` and `stopped_at` once more. Every
    remaining hit means either "grades may still change" (`grades.save_grades`, the `Grades` badge
    case) or reads `stopped_at` (visibility, `offered_subjects`, `teams.delete_team`) and stays.
- [X] T016 [P] Add the seeders to `tests/conftest.py` in a new "Milestone 12.8: published results" section (depends on T011):
  - `make_competition(..., published: bool = False)`: with `published=True` (which requires
    `stopped=True`, else an assertion), sets `published_at` to the same `now`;
  - `store_results_files(engine, competition_id, uk: bytes = b"%PDF-uk test", en: bytes = b"%PDF-en test") -> None`
    inserts the two rows; with `make_competition(..., published=True)` it gives a Published
    competition with known bytes. Docstring: "**Test-only**: it skips publishing, which
    `test_results_service.py` covers; real files come from `publish_results`."
- [X] T017 [P] Add the status tests to `tests/integration/test_competition_service.py` (depends on T014, T016):
  - the enum order is Upcoming, In progress, Finished, Published, Cancelled;
  - `has_finished` is true only for Finished and Published;
  - `status_of` gives **Published** for a row with `stopped_at` and `published_at`, and
    **Finished** with `stopped_at` only;
  - `cancel_competition` on a Published competition raises `NotCancellable(PUBLISHED)`, and
    `update_competition` raises `NotEditable(PUBLISHED)`; nothing changes;
  - a Published competition of a deactivated subject is visible (`get_competition` finds it, and
    `offered_subjects` offers the subject);
  - a new competition of the subject can take a Published one's name;
  - `competition_page(..., status=PUBLISHED)` lists only Published competitions, and
    `status=FINISHED` lists none of them.
- [X] T018 Add `grading_progress` to `app/services/grades.py` per contracts/services.md §1, §3 (depends on T014):
  - in `grades.py`: `@dataclass(frozen=True) class GradingProgress(graded: int, total: int)` with
    the property `complete` (`graded == total`, so 0 of 0 is complete); `results` imports it from
    `grades`, keeping the one-way import `results` → `grades`;
  - `grading_progress(session, competition_id) -> GradingProgress`: the competition's teams through
    the same `_listed(session, competition_id, GradeFilter.ALL)` entries, each counted fully graded
    through `count_of(counts, team.id).fully_graded`;
  - `grade_team_page` computes `teams_total` and `teams_graded` through it (no behaviour change);
  - the `save_grades` docstring states that a Published competition raises
    `GradingClosed(PUBLISHED)` under the share lock, which publishing's `FOR UPDATE` excludes;
  - update the module docstring's "Contract for later milestones".
- [X] T019 [P] Add the progress tests to `tests/integration/test_grade_service.py` (depends on T016, T018):
  - one fully graded, one partly graded and one unanswered team → `GradingProgress(2, 3)`, not
    complete;
  - a deleted team and a team of a deactivated institution count;
  - no teams → `(0, 0)`, complete;
  - `save_grades` on a Published competition raises `GradingClosed(PUBLISHED)`, and the grade is
    unchanged.
- [X] T020 Create `app/services/results.py` with its types, the snapshot and the file names per contracts/services.md §1 and research R7, R9 (depends on T014, T018):
  - a module docstring in the style of `grades.py`'s:
    - who publishes (a teacher with **Can manage competitions**, any competition) and only a fully
      graded **Finished** one;
    - the order of research R5;
    - the files: inserted once, never changed;
    - the clock: `competitions.utc_now`;
    - the one log line;
    - imports run one way: `results` → `results_pdf`, `grades`, `competitions`,
      `competition_entries`;
  - the frozen dataclasses `ResultLine(institution, team, score)`, `RegionResults(name, lines)`
    and `ResultsSnapshot(competition_name, subject_name, starts_at, finished_at, published_at,
    regions)`, exactly as contracts/services.md §1;
  - the errors `NotPublishable(ValueError)` carrying `status` and `NotFullyGraded(ValueError)`
    carrying `progress`;
  - `build_snapshot(session, competition, subject, published_at) -> ResultsSnapshot`:
    - `team_entries(session, competition.id)`, `grade_counts(session, competition.id)`;
    - group by region and institution, using the names as they are now;
    - sort regions by `(name_sort_key(region.name), region.id)`, institutions within a region by
      `(name_sort_key(institution.name), institution.id)`, and teams within an institution by
      `(name_sort_key(team.name), team.id)`;
    - each line `ResultLine(institution.name, team.name, count_of(counts, team.id).score)`;
    - deleted teams and deactivated institutions and regions are included, with no mark;
  - `results_file_name(name: str, starts_at: datetime) -> str`:
    - replace each of `/ \ : * ? " < > |` and each `unicodedata.category(c) == "Cc"` character with
      `_`;
    - strip spaces at both ends and trailing dots; `"results"` if empty;
    - append `f" {starts_at.astimezone(KYIV):%Y-%m-%d}.pdf"`;
  - `ascii_file_name(file_name: str) -> str`: NFKD, then keep ASCII letters, digits, space and
    `-_.()`; every other character becomes `_`, and runs of `_` collapse to one;
  - `results_file(session, competition_id, language: Language) -> bytes | None`:
    `session.get(CompetitionResultsFile, (competition_id, language.value))`, returning its
    `content`.
- [X] T021 Create `app/services/results_pdf.py` with `render_results_pdf(snapshot, language) -> bytes` per contracts/services.md §2, contracts/results-file.md and the initial design of research R8 (depends on T002, T020):
  - **Setup**:
    - a module docstring: pure, no session, the layout and why;
    - asset paths from `Path(__file__).resolve().parent.parent / "static"`: the two TTFs and
      `img/logo/logo-dark-192.png`;
    - the whole body inside `with use_language(language):`;
    - a subclass of `fpdf.FPDF` with `header()` (on pages after the first, the small running title)
      and `footer()` ("Page %(n)d of %(total)d" with `{nb}`, 9 pt, centred);
    - `alias_nb_pages()`; A4 portrait, 20 mm margins, `set_auto_page_break(True, margin=20)`;
    - `add_font("OpenSans", "", regular)` and `add_font("OpenSans", "B", bold)`;
  - **Page 1**:
    - the logo 18 mm high;
    - the title `_("Results of “%(name)s”", name=…)` in Bold 16 pt, through `multi_cell` so long
      names wrap;
    - the subject;
    - `_("Started: %(moment)s")` and `_("Finished: %(moment)s")` with
      `format_local_time(moment, None)`;
    - `_("Published: %(date)s")` with `format_local_date(published_at, None)`;
  - **Body**:
    - per region, a Bold 12 pt heading and a thin rule; before a heading, start a new page when
      less than the heading plus one line is left;
    - per line, `multi_cell` of `_("%(institution)s, %(team)s, %(score)d")` in 10.5 pt;
    - no regions → `_("No teams took part in this competition.")`;
  - **Metadata**: `set_title(<the title text>)`, `set_lang("uk-UA" | "en-GB")`,
    `set_creation_date(snapshot.published_at)`, `set_producer("Student Competitions")`; no author;
  - **Return**: `bytes(pdf.output())`.
  - Nothing reads the wall clock, so the same snapshot and language give the same bytes.
- [X] T022 [P] Create `tests/unit/test_results_pdf.py` with the renderer's base tests (depends on T003, T021):
  - **Fonts**: both cover every character of "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ", its lower case, A–Z,
    a–z, the apostrophes `'` `’` `ʼ`, “ ” « », `–` and `№` (read the `cmap` with
    `fontTools.ttLib.TTFont`);
  - **Fixed snapshot**: rendering two regions in each language gives a PDF (`%PDF-` prefix),
    `pdf_fonts_embedded`, one image on page 1, and the metadata title, language and creation
    date;
  - **Determinism**: the same snapshot rendered twice gives identical bytes;
  - **Wrapping**: a 200-character institution name renders without error.
- [X] T023 [P] Add the file name tests to `tests/unit/test_results_pdf.py` (depends on T020):
  - "Spring round" started 2027-03-14 08:00 UTC → "Spring round 2027-03-14.pdf";
  - a start at 23:30 UTC on 2027-03-13 → `2027-03-14` (Kyiv);
  - `A/B: final?` → `A_B_ final_ 2027-03-14.pdf`;
  - `"  name.. "` → `name 2027-03-14.pdf`;
  - `"..."` → `results 2027-03-14.pdf`;
  - a Cyrillic name is kept in `results_file_name` and becomes `_` runs in `ascii_file_name`;
  - a tab or NUL in the name becomes `_`.
- [X] T024 Extract and translate the messages of Phase 1 and 2 (depends on T004–T007, T014, T021):
  - run `scripts/translations.sh update`;
  - translate every new Ukrainian entry in `app/locale/uk/LC_MESSAGES/messages.po`:
    - "Published" → «Опубліковано»;
    - "Results of “%(name)s”" → «Результати «%(name)s»» (names in «…», as the catalogue's
      «Змагання «%(name)s» завершено»);
    - "Started: %(moment)s" → «Початок: %(moment)s»;
    - "Finished: %(moment)s" → «Завершено: %(moment)s»;
    - "Published: %(date)s" → «Опубліковано: %(date)s»;
    - "Page %(n)d of %(total)d" → «Сторінка %(n)d з %(total)d»;
    - "No teams took part in this competition." → «У цьому змаганні не брала участі жодна
      команда.»;
    - "%(institution)s, %(team)s, %(score)d" kept as is;
    - "Download results" → «Завантажити результати»;
  - run `scripts/translations.sh compile`; `tests/unit/test_catalogues.py` and
    `test_template_text.py` pass.

**Checkpoint**: the schema is on both engines; **Published** exists and every page treats it as
**Finished**; the grading progress, the snapshot and both files render; the whole existing suite
is green.

---

## Phase 3: User Story 1 - A teacher with the setting publishes the results of a graded competition (Priority: P1) 🎯 MVP

**Goal**: **Publish results** in the menu of a **Finished** competition, the ready confirmation,
publishing with the two stored files, the notice and the landing of the status filter.

**Independent Test**: as a teacher with the setting, publish a fully graded **Finished**
competition from the list under each status filter, and check the confirmation, **Keep
unpublished**, the notice, the landing, the new status and menu, and that exactly two files are
stored.

- [X] T025 [P] [US1] Add the `publish_results` service tests to `tests/integration/test_results_service.py` (new; depends on T016, T020):
  - **Success**: a fully graded **Finished** competition is published:
    - `published_at` = the patched now; `status_of` → **Published**;
    - only `published_at` changes on `competitions`;
    - exactly two `competition_results_files` rows, `uk` and `en`, each a PDF whose text holds the
      competition's name;
  - **Landing**: for the filter `None` and **Published**, the competition itself; for **Finished**,
    the row that took its place, the row before when it was last, the previous page's last row when
    its page empties (11 finished, the 11th published from page 2), `competition_id=None` when none
    is left;
  - **No setting**: `ManageRequired`, and nothing is stored;
  - **Log**: exactly one line `Results published: id=<id> teams=<n> bytes=<total>`, with no name in
    it;
  - **Render failure**: with `results_pdf.render_results_pdf` patched to raise, the call raises,
    `published_at` stays `NULL`, no file row exists, and the competition is still **Finished**
    (FR-009).
- [X] T026 [US1] Add `publish_results` to `app/services/results.py` per contracts/services.md §1 and research R5 (depends on T021, T025):
  - **Checks, each refusal rolling back first** (`competitions._refuse`-style):
    - `can_manage_competitions(session, teacher_id, lock=True)`, else `ManageRequired`;
    - `row, subject = competitions.lock_competition(session, competition_id, subject_id)`;
    - `now = competitions.utc_now()`; `current = competitions.status_of(row, now)`; not
      `FINISHED` → `NotPublishable(current)`;
    - `progress = grading_progress(...)`; not `complete` → `NotFullyGraded(progress)`;
  - **Render**:
    - `snapshot = build_snapshot(session, row, subject, now)`;
    - `files = {language: render_results_pdf(snapshot, language) for language in Language}`;
  - **Write**:
    - `before` and `old_index` as `finish_competition`;
    - `update(Competition).where(id == competition_id, stopped_at IS NOT NULL, cancelled_at IS
      NULL, published_at IS NULL).values(published_at=now)`; a row count of 0 →
      `NotPublishable(competitions._reread_status(...))`;
    - `session.add(CompetitionResultsFile(...))` for each language and `session.flush()`; an
      `IntegrityError` → rollback, `NotPublishable(PUBLISHED)`;
    - `after`; commit; the log line; `return competitions.landing(after, competition_id,
      old_index)`;
  - a docstring as `finish_competition`'s, naming the share lock of `save_grades`.
- [X] T027 [US1] Add the publish routes to `app/routers/teacher_competitions.py` and the template `app/templates/pages/teacher/competition_publish.html` per contracts/http-routes.md §1–§2 (depends on T006, T026):
  - **Refusal and notice**:
    - `PUBLISH_REFUSALS` with the four reasons of http-routes.md §2 verbatim;
    - `_publish_refused(...)` with the question "Publish the results of “<name>”?" through
      `_refused`;
    - `NOTICES["published"] = lambda name: _("The results of “%(name)s” were published", name=name)`;
  - **`GET /{competition_id:int}/publish`** (`publish_competition_page`), shaped like the finish
    pair:
    - `require_manage` first, then `offered_subject`, then `find_competition`;
    - `competition.status in PUBLISH_REFUSALS` → refusal;
    - `grading_progress(session, competition.id)`;
    - render the template with the competition, the subject, the progress, `back` and the hidden
      context;
  - **`POST /{competition_id:int}/publish`** (`publish_results_action`), the same checks, then
    `publish_results(...)`:
    - `ManageRequired` → `AccessDenied`;
    - `CompetitionNotFound` → 404;
    - `NotPublishable` → `_publish_refused` with its status;
    - `NotFullyGraded` → the template with the progress, status 409 (US2);
    - success → `redirect(list_path(selected.id, status_filter, landing.page,
      landing.competition_id, _notice_token(request, competition_id, "published")))`;
  - **The template**, as `competition_finish.html`:
    - the back link "Back to the competitions";
    - the question "Publish the results of “{{ competition.name }}” of {{ subject.name }}, started
      {{ local_time(competition.starts_at) }}?";
    - in the caller block, `competition_status_badge(competition.status)` and the progress through
      the existing 12.4 plural message `_n("Graded %(graded)d of %(num)d team", "Graded %(graded)d
      of %(num)d teams", progress.total, graded=progress.graded, num=progress.total)` (the same
      entry as the Grades page, so no new catalogue entry);
    - the consequence of FR-007 verbatim;
    - `confirmation(..., "Publish results", back, hidden={"subject", "status", "page"},
      back_label=_("Keep unpublished"), kind="primary")` when `progress.complete`; the blocked
      variant comes in US2;
    - a header comment citing contracts/http-routes.md §1;
  - update the module docstring: publishing joins finishing, and the manage routes.
- [X] T028 [US1] Add **Publish results** to the row menu in `app/templates/pages/teacher/competitions.html` per research R10 (depends on T027):
  - after **Grades**: `{%- if can_manage and c.status == "finished" %}{{ menu_link(_("Publish results"), "/teacher/competitions/" ~ c.id ~ "/publish?" ~ return_query) }}{% endif -%}`, not destructive;
  - update the template's header comment with the menu order of FR-004.
- [X] T029 [US1] Add the publishing route tests to `tests/integration/test_teacher_results.py` (new; depends on T028):
  - **The confirmation**: it names the competition, its subject and its start in the browser's
    zone, shows the **Finished** badge, "Graded 3 of 3 teams" and the consequence verbatim, with a
    primary (not destructive) submit **Publish results** and the link **Keep unpublished** to the
    list at the competition;
  - **Keep unpublished** changes nothing;
  - **Confirming under All and Published**: 303 to the same subject, filter and page, at
    `#competition-<id>`, with the notice "The results of “Spring round” were published" and the
    badge **Published**;
  - **Confirming under Finished**: the four landings of spec US1 scenario 4;
  - **Afterwards**: the menu has no **Publish results**; exactly two file rows; reloading the
    landing page sends nothing again;
  - **The menu**: a teacher with the setting sees **Publish results** after **Grades** on a
    **Finished** competition only; a teacher without the setting never sees it;
  - **The setting taken away** (FR-003, spec Edge Cases): Olena opens the confirmation, the
    administrator removes her **Can manage competitions**, she sends the publish → 403 "access
    denied", `published_at` stays `NULL` and no file row exists; her next `GET …/publish` is 403 too;
  - **No setting**: `GET` and `POST …/publish` with an unknown competition id answer 403, not 404
    (the setting is checked before any id).

**Checkpoint**: a fully graded competition can be published from the menu, with its confirmation,
notice, landing and two stored files. US1 is done.

---

## Phase 4: User Story 2 - Publishing waits until every team is graded (Priority: P1)

**Goal**: the blocked confirmation while a team is ungraded, its link to **Ungraded only**, the
refused publish, and publishing a competition with no teams.

**Independent Test**: as in spec US2, on partly graded, unanswered and team-less competitions.

- [X] T030 [P] [US2] Add the service tests to `tests/integration/test_results_service.py` (depends on T026):
  - one answer without a grade → `NotFullyGraded(GradingProgress(2, 3))`, and nothing is stored;
  - a team with no answers counts as graded;
  - a deleted team with an ungraded answer blocks publishing;
  - a competition with no teams is published, and both files contain "No teams took part in this
    competition." (and its Ukrainian translation in the `uk` file);
  - a competition with no questions (every team unanswered) is published with every score 0.
- [X] T031 [US2] Render the blocked state in `app/templates/pages/teacher/competition_publish.html` per contracts/http-routes.md §1 (depends on T027):
  - when `not progress.complete`, call `confirmation(...)` with
    `blocked=_("Every team must be graded before the results can be published.")` and
    `alternative=(_("Grade the remaining teams"), grade_remaining_href)`;
  - `grade_remaining_href` is built in `teacher_competitions.py` as
    `f"/teacher/competitions/{competition.id}/grades?{list_query(selected.id, status_filter, return_page)}&show=ungraded"`.
    **Do not import `teacher_grades` or `teacher_competition_entries` here**:
    `teacher_grades` → `teacher_competition_entries` → `teacher_competitions` already import one
    another in that direction, so the import would be circular. The parameters (`subject`,
    `status`, `page`, then `show`) are the ones `teacher_competition_entries.address` writes, so the
    Grades page reads the same list context and its back link returns to the same list page;
  - the same template answers the `NotFullyGraded` refusal of the `POST` with status 409.
- [X] T032 [US2] Add the route tests to `tests/integration/test_teacher_results.py` (depends on T031):
  - **The blocked confirmation**: "Graded 2 of 3 teams", the explanation verbatim, the link
    **Grade the remaining teams** (to `…/grades?subject=…&status=…&page=…&show=ungraded`) then
    **Keep unpublished**, and no submit;
  - following that link opens **Grades** under **Ungraded only**, whose back link leads to the
    original list page;
  - the link equals `teacher_grades.grades_path(competition_id, context, GradeFilter.UNGRADED)` for
    the same list context (the test imports both, so a change to `address` that breaks the
    hand-built link fails here);
  - a crafted `POST` → 409 with the blocked page and nothing stored;
  - after grading the last answer, the same `GET` shows the button;
  - a team-less competition shows "Graded 0 of 0 teams" with the button and publishes.

**Checkpoint**: an ungraded competition can never be published, and the page leads to the work
left. US2 is done.

---

## Phase 5: User Story 3 - Publishing is refused for the wrong status, and the first wins (Priority: P1)

**Goal**: the four status refusals, and exactly one outcome under every race.

**Independent Test**: as in spec US3: typed addresses and forms for each status; two publishes, a
publish and a grade save, and the same form twice at the same moment.

- [X] T033 [P] [US3] Add the refusal tests to `tests/integration/test_teacher_results.py` (depends on T027):
  - for an **Upcoming** (typed address), an **In progress**, a **Cancelled** and a **Published**
    competition, both `GET …/publish` and `POST …/publish` answer 409 with the question "Publish
    the results of “<name>”?", the reason verbatim and **Back to competitions** to the list at the
    competition; nothing changes;
  - the `POST` sent twice → the first 303, the second 409 "The results of “<name>” are already
    published.", with two files stored in all.
- [X] T034 [P] [US3] Add the PostgreSQL-only race tests to `tests/integration/test_results_service.py` (depends on T026):
  - **Two publishes**: two sessions behind a `threading.Barrier` → exactly one returns a `Landing`,
    the other raises `NotPublishable(PUBLISHED)`, and there are exactly two file rows;
  - **Grade save first**: a session holding `lock_competition(share=True)` (a grade save in
    progress) makes `publish_results` in a second session wait until it commits:
    - when that save emptied a grade, the publish raises `NotFullyGraded`;
    - when it changed a grade, the published file holds the new score;
  - **Publish first**: a `save_grades` started after the publish committed raises
    `GradingClosed(PUBLISHED)` and changes no grade;
  - **Publish and cancel**: impossible by status (a Finished competition cannot be cancelled); a
    cancel sent during a publish raises `NotCancellable` with `FINISHED` or `PUBLISHED`.
- [X] T035 [P] [US3] Add the primary-key guard test to `tests/integration/test_results_service.py` (depends on T026). It exercises the guard against a lost race on SQLite, where the row locks render nothing; the state it sets up (a file present while `published_at` is `NULL`) is not reachable through the application (data-model.md §4 invariant 1), so the test names that in its docstring. With a file row for `uk` inserted beforehand by `store_results_files` on a Finished competition whose `published_at` is `NULL` (a simulated lost race), `publish_results` raises `NotPublishable(PUBLISHED)`, leaves `published_at` `NULL` and keeps the existing row unchanged.

**Checkpoint**: publishing is refused where it must be and is applied exactly once. US3 is done.

---

## Phase 6: User Story 4 - The Published status is shown and filtered (Priority: P1)

**Goal**: the badge everywhere, the **Published** filter, **Finished** narrowed, the finished
pages offered on Published, and the deactivated-subject case.

**Independent Test**: as in spec US4: competitions of every status, one published; badges, filter
lists, pages and the deactivated subject.

- [X] T036 [P] [US4] Add the list tests to `tests/integration/test_teacher_competitions.py` (depends on T015, T016):
  - **The filter**: the **Status** list offers All, Upcoming, In progress, Finished, Published,
    Cancelled in that order; `?status=published` lists only the published competition with its
    **Published** badge; `?status=finished` no longer lists it; All lists both;
  - **The menu** on a published competition:
    - a teacher with the setting sees **Questions**, **Teams**, **Answers**, **Grades**,
      **Download results**;
    - a teacher without it sees **Questions**, **Teams**, **Answers**, **Download results**;
    - no **Edit**, **Publish results**, **Finish competition** or **Cancel competition**;
    - (**Download results** arrives in US7; assert it there if this task runs first);
  - **Refusals**: the edit, cancel and finish addresses of a published competition answer their
    finished refusals.
- [X] T037 [P] [US4] Add the page tests for a Published competition to `tests/integration/test_teacher_competition_entries.py` and `tests/integration/test_teacher_team_answers.py` (depends on T015, T016):
  - **Questions** and **Teams** open read-only, with the **Published** badge under the heading,
    and their add and remove addresses show the 12.2 finished refusals;
  - **Answers** opens with **Graded** and **Score** and **View answers**, and the read-only sheet
    shows grades and score;
  - an answer save gets "“<name>” has finished, so its answers can no longer be entered.";
  - with the subject deactivated, the list, the pages and the badge still work.

**Checkpoint**: Published is a first-class status on every page. US4 is done.

---

## Phase 7: User Story 5 - The grades of a published competition are frozen (Priority: P1)

**Goal**: the read-only grading sheet with its note, and a refused grade save.

**Independent Test**: as in spec US5: publish, open the Grades page and sheets, send saves.

- [X] T038 [US5] Make the grading sheet read-only on Published in `app/routers/teacher_grades.py` and `app/templates/pages/teacher/team_grading_sheet.html` per contracts/http-routes.md §4 and research R6 (depends on T007, T015):
  - `PUBLISHED_NOTE = lambda name: _("The results of “%(name)s” are published, so its grades can no longer be changed.", name=name)`;
  - `_render_sheet(..., read_only: bool, status_code=200)` passes `read_only=True` and
    `note=PUBLISHED_NOTE(competition.name)` to the template, which calls `grading_sheet(...,
    read_only=read_only, note=note)` and renders no error summary when read-only;
  - `GET /grades/{team_id}`: `read_only = competition.status is CompetitionStatus.PUBLISHED`;
  - `POST /grades/{team_id}`:
    - `competition.status is PUBLISHED` before the service → the read-only sheet with status 409
      and nothing parsed or stored;
    - `GradingClosed(PUBLISHED)` from the service (published meanwhile) → the same;
    - `GradingClosed` of other statuses keeps `grades_refused`;
  - the Grades page (`GET /grades`) is unchanged and keeps **Grade answers**.
- [X] T039 [US5] Add the route tests to `tests/integration/test_teacher_grades.py` (depends on T038, T016):
  - **The sheet on Published**: the note verbatim, "Reference answer" for each question,
    "Grade: 7 of 10" for each grade, and no `form`, `input` or **Save grades**;
  - **A save**: a crafted `POST` → 409 with the same sheet and note, and every grade is unchanged
    in the database; a save from a sheet rendered before publishing (the form captured, then
    publish, then submit) → the same;
  - **Unchanged pages**: the Grades page shows the same rows, **Graded**, **Score** and progress
    as before publishing;
  - **Finished**: the editable sheet and saves are unchanged.

**Checkpoint**: no grade of a published competition can change, and the sheet says why. US5 is
done.

---

## Phase 8: User Story 6 - The results files hold the official results (Priority: P1)

**Goal**: every rule of contracts/results-file.md is tested on real published files, and the files
never change.

**Independent Test**: as in spec US6: seed a multi-region competition with deleted, renamed and
deactivated cases, publish, read both files, change the data, and compare bytes.

- [X] T040 [P] [US6] Add the snapshot tests to `tests/integration/test_results_service.py` (depends on T020):
  - **Order**: three regions "Харківська", "Київська", "Lviv" (a Latin name sorts before Cyrillic
    under `name_sort_key`), institutions and teams named to exercise the Ukrainian order (Ґ after
    Г, Є after Е, І and Ї after И, apostrophes ignored);
  - **Ties**: equal names are ordered by id;
  - **Every team** exactly once, including a deleted team and a team of a deactivated institution
    and region, with no mark;
  - **Scores**: each the sum of its grades, 0 for a team with no answers;
  - two teams with the same name in different institutions are both listed.
- [X] T041 [P] [US6] Add the content tests to `tests/unit/test_results_pdf.py` (depends on T022):
  - **The English file's text** holds, in this order: "Results of “Spring round”", the subject,
    "Started: 14 March 2027, 10:00 (Kyiv time)", "Finished: …", "Published: …", each region name,
    and each line "School No. 5, Comets, 17";
  - **The Ukrainian file** holds the translated labels («Результати», «Сторінка 1 з 1», «за
    київським часом») and the same names, untranslated;
  - **Cyrillic names** (with ґ, є, ї and the apostrophe ʼ) extract exactly as given;
  - **Pages**: a snapshot of 120 lines runs over several pages, each page's text holds "Page n of
    N" with the right N, and no region heading is the last line of a page;
  - **Nothing extra**: none of the answer, reference answer, question text or member names known to
    the test appear (render a snapshot built through `build_snapshot` from a seeded competition
    whose answers and questions carry unique marker strings).
- [X] T042 [US6] Add the permanence tests to `tests/integration/test_results_service.py` (depends on T026):
  - publish, read both file rows' bytes, then:
    - rename the region, the institution, a team and the subject;
    - deactivate the institution and the subject;
    - delete a team;
  - both rows are byte-for-byte unchanged, still name the old names, and still hold two rows;
  - a scan of `app/` (a test that greps the source for `update(CompetitionResultsFile` and
    `delete(CompetitionResultsFile`) finds none.
- [X] T043 [US6] Add the timing test to `tests/integration/test_results_service.py` (depends on T026): a competition of 500 teams in 10 regions with 10 graded answers each publishes in under 5 seconds (SC-007), measured with `time.perf_counter` around `publish_results` only (not the seeding). It runs everywhere, CI and both engines included, and is never skipped. Name it `test_publishing_500_teams_takes_under_5_seconds`, and make the assertion message state the measured time. If CI cannot meet the bound, record that as a deviation in plan.md's Complexity Tracking and agree a new bound with the product owner; do not skip the test.

**Checkpoint**: the files hold exactly the official results, in both languages, and never change.
US6 is done.

---

## Phase 9: User Story 7 - Every teacher downloads the results (Priority: P1) 🎯 MVP

**Goal**: **Download results** for every teacher on a **Published** competition, handing out the
stored file of the current language.

**Independent Test**: as in spec US7: every kind of teacher, both languages, headers, file name,
404s, 403s.

- [X] T044 [US7] Create `app/routers/teacher_results.py` with the download per contracts/http-routes.md §3 and research R9, and include it in `app/main.py` next to `teacher_grades.router` (depends on T020):
  - a module docstring:
    - any teacher, no setting;
    - the published results are open information;
    - the order of checks;
    - the headers and why `no-store`;
    - nothing logged;
  - `router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")`;
  - `@router.get("/results")` `@allow_roles(Role.TEACHER)`
    `def download_results(request, session, competition_id, subject: str | None = Query(None)) -> Response`:
    - `offered_subject(offered_subjects(session), subject)`, else `not_found(request,
      SUBJECT_NOT_FOUND)`;
    - `find_competition(...)` with `status is not PUBLISHED`, else `not_found(request,
      COMPETITION_NOT_FOUND)`;
    - `content = results_file(session, competition.id, request.state.language)`; `None` →
      `COMPETITION_NOT_FOUND` (cannot happen, invariant 1);
    - `name = results_file_name(competition.name, competition.starts_at)`;
    - `Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{ascii_file_name(name)}"; filename*=UTF-8\'\'{quote(name, safe="")}', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})`.
- [X] T045 [US7] Add **Download results** to the row menu in `app/templates/pages/teacher/competitions.html` (depends on T005, T044):
  - after **Publish results**: `{%- if c.status == "published" %}{{ menu_link(_("Download results"), "/teacher/competitions/" ~ c.id ~ "/results?subject=" ~ selected.id, download=True) }}{% endif -%}`;
  - every teacher, whatever their setting and links;
  - check the full order against FR-004.
- [X] T046 [US7] Add the download tests to `tests/integration/test_teacher_results.py` (depends on T045, T016):
  - **Every teacher** gets 200 with the stored `uk` bytes exactly (`store_results_files` with known
    bytes) and the four headers: a teacher with **Read**, one with **Write**, one with the setting,
    and one linked to no institution of the competition's teams;
  - **Language**: with the language cookie `en`, the stored `en` bytes;
  - **File name**: `Content-Disposition` carries `filename*=UTF-8''Spring%20round%202027-03-14.pdf`
    and an ASCII `filename`; a Cyrillic name round-trips through `filename*`;
  - **The menu**: the entry is an `a[download]` with that address, on Published rows only, for
    every teacher;
  - **404 "Competition not found"**: an Upcoming, In progress, Finished and Cancelled competition,
    an unknown id, and a competition of another subject;
  - **404 "Subject not found"**: an unknown subject;
  - **403 before any id**: an administrator and a student, also with unknown ids;
  - **No change**: the download changes nothing (row counts before and after);
  - **End to end**: after a real `publish_results`, the download's bytes equal the stored row's.

**Checkpoint**: every teacher downloads the stored file of their language. US7 is done; with US1
and US2, the MVP is complete.

---

## Phase 10: User Story 8 - The product owner approves the design of the files (Priority: P2)

**Goal**: repeatable samples, the review rounds and the recorded approval.

**Independent Test**: run the sample script, review the samples, record each round.

- [X] T047 [US8] Create `scripts/make_results_samples.py` per research R12 (depends on T021, T024):
  - a module docstring in the style of `scripts/make_logo.py`'s (what it writes, that it takes no
    arguments, that the outputs are committed review evidence);
  - three `ResultsSnapshot`s built in memory, with fixed times (start 14 March 2027 10:00 Kyiv,
    finish 12:30, published 21 March 2027):
    1. `long-list`: seven Ukrainian regions, 60 teams in 20 institutions with realistic Cyrillic
       names (apostrophes, ґ, є, ї), several pages;
    2. `long-names`: one region with institution and team names of about 200 characters;
    3. `no-teams`;
  - each rendered with `render_results_pdf` for `Language.UK` and `Language.EN`, after
    `load_translations()`, to `specs/012.8-publishing-results/samples/<set>-<lang>.pdf`;
  - the outputs are deterministic, so a re-run without a design change leaves them unchanged.
- [X] T048 [US8] Make the first samples and open the review (depends on T047):
  - run `uv run python scripts/make_results_samples.py`;
  - commit the six PDFs;
  - create `specs/012.8-publishing-results/design-approval.md` in the format of
    `specs/012.7-new-logo/design-approval.md`: the round number, the date, the samples, what to
    look at (layout, fonts, logo size and place, header, spacing, wording), and the product owner's
    decision (pending).
- [X] T049 [US8] Apply each round's change requests in `app/services/results_pdf.py` (and, if a larger logo is needed, one dark-ink print size in `scripts/make_logo.py` and its committed image), regenerate the samples, re-run `tests/unit/test_results_pdf.py`, and record the round in `design-approval.md` (depends on T048; repeat until approved). Wording changes go through the catalogues (T024's workflow). Record each round's decisions in the spec's Clarifications if they change a rule.
  - **Round 1 (2026-11-21)**: changes requested and made: the maximum score under "Published"; a table per region (institution, team, score; the score column just wide enough). Recorded in the spec's Clarifications, FR-023, FR-025, contracts/results-file.md, research R8 and data-model §5. Round 2 approved by the product owner on 2026-11-21.
- [X] T050 [US8] Record the approval (depends on T049): the approved round, the date and the product owner's words in `design-approval.md`; the milestone is not done before this (FR-040).

**Checkpoint**: the design of both files is approved and recorded. US8 is done.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: the route sweep, the form contract, the page patterns, the documents, the catalogues,
and the whole suite on both engines.

- [X] T051 [P] Update `tests/integration/test_routes.py` (depends on T027, T044):
  - the write routes list gains `POST /teacher/competitions/{competition_id}/publish`;
  - the declared-GET sweep finds `GET …/publish` among the manage pages and `GET …/results` among
    the teacher pages;
  - every new route redirects anonymous requests and denies administrators and students.
- [X] T052 [P] Update `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json` (depends on T027): the publish form posts `subject`, `status`, `page` and the cross-site token, with no other field; a cross-site `POST` to `…/publish` is refused and nothing changes (as `test_cross_site.py` does for finishing).
- [X] T053 [P] Update `tests/integration/test_page_patterns.py` (depends on T027, T031, T038):
  - the publish confirmation (both states), the publish refusal and the read-only grading sheet
    follow the page patterns: one `h1`, the back link, no inline style, labelled landmarks;
  - at 360 px width (the existing pattern check) there is no element wider than the content.
- [X] T054 Extract and translate every message added since T024 (depends on T027–T045):
  - run `scripts/translations.sh update`;
  - translate the new Ukrainian entries in `app/locale/uk/LC_MESSAGES/messages.po`:
    - "Publish results" → «Опублікувати результати»;
    - "Keep unpublished" → «Не публікувати»;
    - "Publish the results of “%(name)s” of %(subject)s, started %(start)s?" and "Publish the
      results of “%(name)s”?" → «Опублікувати результати «…»…?»;
    - the consequence;
    - "Every team must be graded before the results can be published.";
    - "Grade the remaining teams";
    - the four `PUBLISH_REFUSALS`;
    - the notice;
    - the published grading note;
  - compile; the catalogue tests pass.
- [X] T055 [P] Update `README.md` per research R15 (depends on T044, T047):
  - in the feature overview: publishing and downloading results;
  - in the dependencies section: `fpdf2` (why: the "Results files" row) and `pypdf` (tests only);
  - a font note: Open Sans TTF from upstream release <tag>, SHA-256 of both files, OFL;
  - in the scripts section: `scripts/make_results_samples.py`.
- [X] T056 [P] Finish `docs/requirements/ui-guidelines.md` against the pages as built (depends on T009, T027, T038, T045): the examples match the final markup, and the actions menu example matches `competitions.html`.
- [X] T057 Run the whole suite on both engines (depends on everything above):
  - `uv run ruff check && uv run ruff format --check`;
  - `TEST_POSTGRES_URL=… uv run pytest`;
  - fix any failure. Then `docker build .` and the image's smoke run (the CI `image` job), to
    confirm fpdf2, Pillow and fontTools install from the lock and a publish works in the container.
- [X] T058 Walk through [quickstart.md](./quickstart.md) §2–§5 by hand:
  - the migration up and down on a copy of a 12.7 database;
  - the samples;
  - the full flow as Olena and Taras, including the language switch, the download with no loading
    bar, phone width and both themes;
  - fix what it finds.
- [ ] T059 On delivery (after T050 and the PR's merge): move 12.8 to **Delivered** in `docs/requirements/milestones.md` with the spec link and a one-paragraph summary in the style of 12.4's and 12.7's entries.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependency. T001 before T003; T004–T007 before T008–T010.
- **Phase 2 (Foundational)**: after T001, T002 (fonts) and T004–T007 (the templates T015 edits).
  - T011 → T012 → T013;
  - T011 → T014 → T015, T017, T018;
  - T018 → T019, T020;
  - T020 → T021 → T022, T024;
  - T016 is needed by every later test.
- **US1 (Phase 3)**: after Phase 2. T025 → T026 → T027 → T028 → T029.
- **US2 (Phase 4)**: after T027.
- **US3 (Phase 5)**: after T026 / T027.
- **US4 (Phase 6)**: after T015 and T016; independent of US1.
- **US5 (Phase 7)**: after T007 and T015; independent of US1 (seeded Published competitions).
- **US6 (Phase 8)**: T040 and T041 after Phase 2; T042 and T043 after T026.
- **US7 (Phase 9)**: after T005, T020 and T016; independent of US1 for its tests (seeded files),
  except the end-to-end case.
- **US8 (Phase 10)**: after T021 and T024; review rounds can start as soon as the renderer exists
  and run alongside the other stories.
- **Polish (Phase 11)**: after the stories it covers. T059 last, after merge.

### Within each story

- Service tests are written first and fail, then the service, then the routes and templates, then
  the route tests.
- A story's messages are extracted and translated before its route tests assert Ukrainian text.

### Parallel opportunities

- **Phase 1**: T002, T004, T005, T006, T007 together, after T001; then T009 and T010 alongside T008.
- **Phase 2**: T013, T016 and T017 alongside T014–T015; T022 and T023 together.
- **After Phase 2**: US4 (T036, T037), US5 (T038–T039), US6 (T040, T041), US7 (T044–T046) and US8
  (T047–T048) can all proceed while US1 is built, since each seeds its own Published competitions.
- **Polish**: T051, T052, T053, T055 and T056 together.

## Parallel Example: after Phase 2

```text
Developer A: T025 → T026 → T027 → T028 → T029   (US1: publishing)
Developer B: T044 → T045 → T046                 (US7: the download, on seeded files)
Developer C: T038 → T039                        (US5: frozen grades)
Developer D: T047 → T048                        (US8: samples, first review round)
Then:        T030–T032 (US2), T033–T035 (US3), T036–T037 (US4), T040–T043 (US6)
```

## Implementation Strategy

### MVP first (Phase 1 + Phase 2 + US1 + US2 + US7)

1. Components, dependencies and fonts (Phase 1), and the schema, status, snapshot and renderer
   (Phase 2).
2. US1: publish a fully graded competition.
3. US2: never publish an ungraded one.
4. US7: every teacher downloads the file.
5. **Stop and validate**: publish a seeded competition and download both languages; start the
   first design review round (US8) on these files.

### Incremental delivery

1. US3: refusals and races, so publishing is safe under real use.
2. US4: the status and filter everywhere.
3. US5: frozen grades.
4. US6: the file content and permanence tests.
5. US8: review rounds until approval.
6. Polish, the whole suite on both engines, the quickstart walk-through.
7. Merge after approval; T059 on delivery.
