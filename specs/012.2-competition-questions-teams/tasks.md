---

description: "Task list for milestone 12.2: the questions and teams of a competition (teacher)"
---

# Tasks: Questions and Teams of a Competition (Teacher) (Milestone 12.2)

**Input**: Design documents from `/specs/012.2-competition-questions-teams/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md), [contracts/components.md](./contracts/components.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-052 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. The mapping from scenarios to modules is research R16.

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set, through the existing `database_url` / `engine` / `session` / `client` fixtures in
  `tests/conftest.py`. The two-session concurrency tests run on PostgreSQL only (skip on SQLite),
  with the `threading.Barrier` pattern of `tests/integration/test_team_service.py` (around line 730).
- **Seeders**: `make_teacher(engine, settings, email=..., institutions={}, can_manage=True | False)`,
  `make_subject`, `make_question`, `make_institution(..., region="Kyiv", region_active=...)`,
  `make_class`, `make_team(engine, institution_id, name, deleted=...)`, `make_member`,
  `make_competition(engine, subject_id, name, starts_at=..., cancelled=..., stopped=...)`, and the
  new `add_competition_question` / `add_competition_team` (T015).
- **The clock**: tests control "now" with
  `monkeypatch.setattr("app.services.competitions.utc_now", lambda: fixed)`, as
  `tests/integration/test_competition_service.py` does. The new service reads the clock **through
  that module attribute** (`competitions.utc_now()`), never through its own import, so the same
  patch moves it (contracts/services.md). No test sleeps.
- **Finished competitions** are stored directly with `make_competition(..., stopped=True)`; stopping
  does not exist yet (spec Assumptions).

**Organization**: tasks are grouped by user story (US1–US11 in spec.md).

- **Phase 1 is the region group, the refusal link text and the documents**, because the
  constitution puts the library, the gallery and the guidelines before any page (FR-050, FR-051).
  It delivers **US11**.
- **Phase 2** is the two tables, the migration, the shared helpers (`landing_index`,
  `lock_competition`, `count_active_members`), the service and router skeletons and the seeders.
- **US1** builds the competition's questions list and "Add questions": the MVP. **US3** completes
  the questions list (marks, hints, the address fallback). **US4** builds the teams list and
  **US2** "Add teams" on top of it, so US4 comes before US2 although both are P1. **US6** puts the
  menu on every row once both lists exist. **US5** adds removing.
- **US7** (status and concurrency), **US9** (access) and **US10** (deactivated subjects) are
  enforced inside every route and service as they are built (the rules below); their own phases
  are the cross-cutting tests, after the last route (US5). **US8** changes the team deletion.

**Reference implementation**: milestones 11–12.1 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- **Services**: `app/services/competitions.py` (`_find`, `_refuse`, `_require_manage`, `status_of`,
  `landing`, `cancel_competition`'s lock-then-check order), `app/services/questions.py`
  (`question_page`, `_listed`, `with_for_update`, `populate_existing`), `app/services/teams.py`
  (`list_active_members`' join chain, `delete_team`, the `IntegrityError` branch of
  `create_team`), `app/services/regions.py` (`list_regions`), `app/services/paging.py`
  (`parse_page`, `Paging.build`, `PAGE_SIZE`), `app/services/teacher_access.py::can_manage_competitions`.
- **Routers**: `app/routers/teacher_competitions.py` (thin handlers, `_require_manage` first,
  `list_path`, `_query`, `_parse_id`, `_offered`, `_competition`, `_not_found`, `_refused`, the
  sealed notice), `app/routers/teacher_teams.py` (`seal_member_notice` / the reading side: a
  notice with its kind), `app/routers/teacher.py::render_teacher`.
- **Templates**: `app/templates/pages/teacher/competitions.html`, `competition_cancel.html`,
  `competition_refused.html`, `competition_not_found.html`, `questions.html` (the text-card list),
  `team_add_students.html` (a chained list over a table with **Add** or a row note); components
  `frame.html` (`page_heading`, `back_link`, `section_heading`), `card.html` (`text_card`,
  `text_box`), `table.html` (`data_table`, `cell`, `actions_cell`, `row_note`), `selectors.html`
  (`chained_lists`), `menu.html`, `details.html`, `feedback.html`, `pagination.html`,
  `confirmation.html`, `button.html` (`post_button`, `link_button`), `time.html`; the gallery
  `app/templates/pages/admin/components.html` with `app/routers/admin_components.py`;
  `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Migration**: `migrations/versions/2026_11_02_72e46cb10175_competitions.py` (frozen snapshot,
  `op.f` names).
- **Tests**: `tests/integration/test_teacher_competitions.py` (its `Scene`, `rows()` parser and
  `listed()` helper), `test_competition_service.py`, `test_teacher_teams.py`, `test_team_service.py`,
  `test_routes.py` (`test_the_write_routes_are_exact`, `MANAGE_PATHS`,
  `test_the_manage_pages_are_found`), `test_form_contract.py` with `form_contract.json`,
  `test_page_patterns.py`, `test_component_gallery.py`, `test_migrations.py`, `tests/html.py`.

**Rules for every task** (plan Constraints; http-routes.md §Order of checks):

- **Order of checks** in every handler: role (`@allow_roles(Role.TEACHER)`, 403 for administrator
  and student) → on a *manage* route (the eight add and remove routes), `require_manage` as the
  **first line**, before any value is parsed (403 `AccessDenied(Role.TEACHER)`, unknown ids too) →
  the subject (404 "Subject not found") → the competition (404 "Competition not found") → on a
  manage route, the status (409 refusal) → the region, question or team (404) → the service write,
  which repeats the setting, competition, status and entry checks under lock and raises the same
  outcomes.
- **Values**: query and form values are read as plain strings (`Query(None)`, `Form("")`), so no
  input ever produces FastAPI's 422 JSON. Ids go through `parse_id` (ASCII digits ≤ `MAX_ID`), else
  "not found"; page numbers through `parse_page`.
- **Addresses**: `subject`, `status`, `page` keep their 12.1 meaning (the competitions list the
  teacher came from) and are carried through every page, form, refusal and redirect; `p` is the
  page's own list page; `back` is the page of the competition's list the add pages and
  confirmations return to; `region` on "Add teams" (research R8). Every address is built by
  `list_path`, `entries_path` or `add_page_path` from looked-up ids and parsed values only.
- **Redirects**: every change is a `POST` through the existing cross-site check, answering `303`
  to a `GET` page, so a reload never repeats it (FR-038, FR-047).
- **Notices** travel sealed (`ENTRY_NOTICE_PURPOSE = "competition-entry-notice"`, 10 minutes),
  holding ids and the outcome only; the texts are built when the page is shown (research R9).
- **Logging**: services log ids only, exactly: `Competition question added: competition=%d
  question=%d`, `Competition question removed: competition=%d question=%d`, `Competition team
  added: competition=%d team=%d`, `Competition team removed: competition=%d team=%d`, and
  `Team deleted: id=%d members=%d competitions=%d`. A no-op ("already", "absent") and a refusal log
  nothing. No email, person's name, competition name, team name or question text ever reaches a log
  line or an address (FR-048).
- **Components first**: the new macro is in the library, its CSS in the Components section of
  `app/static/css/app.css` (tokens only, no inline style, no literal colour or pixel length, no new
  token), the gallery and `ui-guidelines.md` **before** a page uses it (FR-050).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US11)

---

## Phase 1: Setup (Components and documents first)

**Purpose**: the region group in the library, the gallery and the guidelines; the refusal page's
link text; the guidelines' wording changes; the product requirements (FR-050, FR-051, research
R15, contracts/components.md §1–§5). Nothing here touches the database. Delivers **US11**.

- [X] T001 Create `app/templates/components/group.html` with `region_group(name, total, heading_id)` per contracts/components.md §1 and research R15, and its CSS:
  - a header comment in the style of `table.html`'s (what it is, when to use it, that the page writes a `data_table` inside the `{% call %}`, that a region continuing on the next page repeats its header with the same total and gets another `heading_id`);
  - an empty `name` is `template_error("region_group: the name is required")`, as `row_note` refuses; a `total` below 1 is `template_error("region_group: the total must be at least 1")`;
  - markup: `<section class="region-group" aria-labelledby="{{ heading_id }}"><h2 class="region-group-header" id="{{ heading_id }}">{{ name }} · {{ total }} {{ "team" if total == 1 else "teams" }}</h2>{{ caller() }}</section>` → "Kyiv · 14 teams", "Lviv · 1 team"; no other word is added to the name;
  - CSS in the Components section of `app/static/css/app.css`, tokens only: `.region-group` with `border: var(--sc-border-width) solid var(--sc-border)`, `border-radius: var(--sc-radius-card)`, `background: var(--sc-surface)`, and the standard vertical gap between consecutive groups (`.region-group + .region-group`); `.region-group-header` with the card padding, the type size `section_heading` uses for `h2`, `margin: 0`, `overflow-wrap: anywhere`; the `.data-table` inside a `.region-group` loses its own outer border and radius (no double border) and keeps its look otherwise; below 768 px the rows stay labelled cards inside the box with no sideways scroll.
- [X] T002 [P] Make the refusal page's link texts context values: in `app/templates/pages/teacher/competition_refused.html` render `back_link(back, back_link_text)` and `refusal(question, reason, back, back_text)`, and update its header comment (it now also serves milestone 12.2's refusals). In `app/routers/teacher_competitions.py::_refused` pass `"back_link_text": "Back to the competitions"` and `"back_text": "Back to competitions"`, so every 12.1 refusal renders byte-for-byte as before (contracts/components.md §3).
- [X] T003 Add the gallery entries (depends on T001):
  - `app/routers/admin_components.py` (`_samples`): sample region groups — "Kyiv" with total 14 and three team rows (name, institution, active members), "Lviv" with total 1 and one row, a 200-character region name with total 3, and one row of a deleted team;
  - `app/templates/pages/admin/components.html`: a new `<section id="region-group" aria-labelledby="region-group-heading">` right after `#table`, with the three groups each holding a `data_table(["Team", "Educational institution", "Active members", "Actions"])`, one row whose actions cell holds `row_note("(deleted)")` and one with `row_note("Already in this competition")`; import `components/group.html`;
  - `#actions-menu` gains the full four-entry menu (**Edit**, **Questions**, **Teams**, the destructive **Cancel competition**, shown open) and the two-entry read-only menu (**Questions**, **Teams**);
  - add `#region-group` to the gallery's table of contents if it has one.
- [X] T004 [P] Update `docs/requirements/ui-guidelines.md` per contracts/components.md §5 (depends on T001):
  - §5 a new "Region group (`components/group.html`)" subsection right after "Data table": when to use it (one list grouped by a parent and paged across groups), the header format "<name> · <n> teams" / "1 team" with the name as stored, the repeated header with the same total on the next page, a unique `heading_id` per page, "never a table caption for this", the phone behaviour, and the gallery link `/admin/components#region-group`;
  - §5 "Actions menu": "an empty menu is no menu" stays; the example shows the four entries **Edit**, **Questions**, **Teams**, **Cancel competition**;
  - §7 **Menus**: "the entries are verbs, as buttons are: **Edit**, **Cancel competition**" becomes "an entry that does something is a verb (**Edit**, **Cancel competition**); an entry that only opens a page is named by that page (**Questions**, **Teams**); a destructive entry is always a verb" (FR-051);
  - §7 **Row notes**: the examples gain "Already in this competition", "Deleted from the question bank" and "(deleted)", with the sentence that a row note may also mark a record the row can no longer act on, while a *status* still takes a badge (research R15).
- [X] T005 [P] Update `docs/requirements/product-requirements.md` per FR-051: "Competition statuses" — deleting a team is the one exception to "only an upcoming competition can be edited" and "a cancelled competition never changes again": it takes the team out of every competition that is not finished; "Team" — a deleted team stays only in finished competitions, marked deleted; any live team of an active institution in an active region can be added by a teacher with **Can manage competitions**, linked to its institution or not; "Question" — a competition holds a copy of each of its questions, taken when it is added, so editing or deleting the question in the bank does not change the competition, and a deleted question can no longer be added. Confirm (read only) that `.specify/memory/constitution.md` v2.1.0 Principle IV already states the team-deletion exception; do not edit the constitution here.
- [X] T006 [P] Extend the component tests (depends on T003): `tests/integration/test_component_gallery.py` — `#region-group` has `section.region-group` elements labelled by their `h2` (`aria-labelledby` equals the header's `id`), the headers "Kyiv · 14 teams" and "Lviv · 1 team", the long name, a `data_table` inside each, the "(deleted)" and "Already in this competition" row notes; `#actions-menu` has the four-entry menu in the order **Edit**, **Questions**, **Teams**, **Cancel competition** (the last destructive) and the two-entry menu; `tests/unit/test_templates.py` — `region_group` singular and plural headers, a template error for an empty name and for a total of 0; `tests/unit/test_stylesheet.py` stays green (every new class defined and used, no literal colour or pixel length). `test_page_patterns.py` and `test_form_contract.py` stay green unchanged (T002 renders the 12.1 refusals as before).

**Checkpoint**: the region group is in the library, the gallery and the guidelines; the documents
state the new rules; every existing page renders as before. US11 is done.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the two tables and their migration, the shared helpers, the service and router
skeletons, and the seeders (data-model.md, research R1, R2, R8, R9, R11, R13,
contracts/services.md, contracts/http-routes.md §Order of checks, §Address parameters).

**⚠️ CRITICAL**: no user story work can begin until this phase is complete, and the whole existing
suite must be green at its end.

- [X] T007 Add the models to `app/models/competition.py` per data-model.md §1–§2 and research R1, and export both from `app/models/__init__.py` (and its `__all__`):
  - `class CompetitionQuestion(SQLModel, table=True)`, `__tablename__ = "competition_questions"`, a class docstring (a copy taken when the question was added; never written again; the `id` is the order of adding; not personal data), `__table_args__ = (UniqueConstraint("competition_id", "question_id", name="uq_competition_questions_competition_id_question_id"), {"sqlite_autoincrement": True})`; columns: `id: int | None` primary key ("The order of adding: the list is sorted by it (FR-005). Never shown."); `competition_id: int = Field(foreign_key="competitions.id", nullable=False)` ("No `ON DELETE`: competitions are never deleted."; no separate index, the unique constraint's leading column serves it); `question_id: int = Field(foreign_key="questions.id", nullable=False)` ("The bank question it was copied from … No `ON DELETE`: questions are only soft-deleted."); `text: str` and `reference_answer: str` as `String(QUESTION_FIELD_MAX_LENGTH)`, not null ("The bank's text at the moment of adding; never written again (FR-007)."; the reference answer "Shown only in the teacher area."); `added_at: datetime` `UTCDateTime`, not null ("When it was added. Never shown.");
  - `class CompetitionTeam(SQLModel, table=True)`, `__tablename__ = "competition_teams"`, a class docstring (the fact that a team takes part; name, institution, region and member count are read from the team, not copied; not personal data; its writers are `competition_entries` while Upcoming and `teams.delete_team`); columns: `competition_id: int = Field(foreign_key="competitions.id", primary_key=True)` ("No `ON DELETE`."); `team_id: int = Field(foreign_key="teams.id", primary_key=True, index=True)` ("No `ON DELETE`: teams are only soft-deleted. Indexed for the deletion of R5."); `added_at: datetime` `UTCDateTime`, not null. The primary key is named `pk_competition_teams` by the naming convention and the index `ix_competition_teams_team_id`.
- [X] T008 Create the migration `migrations/versions/2026_11_<dd>_<rev>_competition_questions_and_teams.py` (`down_revision = "72e46cb10175"`) per data-model.md §5, following `2026_11_02_72e46cb10175_competitions.py` (depends on T007): generate the revision id with `uv run alembic revision -m "competition questions and teams"` and write the operations by hand as a frozen snapshot (plain SQLAlchemy types, nothing imported from `app`); upgrade creates `competition_questions` (`sqlite_autoincrement=True`, both foreign keys with no `ON DELETE`, `String(<QUESTION_FIELD_MAX_LENGTH value>)` for `text` and `reference_answer`, the unique constraint `uq_competition_questions_competition_id_question_id`) and `competition_teams` (the composite primary key, both foreign keys, `op.f("ix_competition_teams_team_id")`), all names through `op.f`; no data step; downgrade drops the index and both tables. Run `uv run alembic upgrade head` locally.
- [X] T009 [P] Extend `tests/integration/test_migrations.py` (depends on T008): the head is the new revision; the stairway and drift checks cover it on both engines; after upgrade, a second `competition_questions` row with the same `(competition_id, question_id)` fails, the same question in another competition succeeds; a second `competition_teams` row with the same pair fails; the `team_id` index exists; downgrade to `72e46cb10175` drops both tables and leaves `competitions`, `questions` and `teams` unchanged.
- [X] T010 [P] Add `landing_index(ids: Sequence[int], kept_id: int | None, old_index: int | None) -> tuple[int, int | None]` to `app/services/paging.py` per contracts/services.md §`app/services/paging.py` and research R11: `kept_id` if it is in `ids`; else the id at `min(old_index, len(ids) - 1)`; else `(1, None)` (no `old_index` or an empty list); the page is `index // PAGE_SIZE + 1`. Pure, with a docstring. Re-express `app/services/competitions.py::landing` through it (same behaviour, same `Landing`), and update the paging module docstring's "milestones 12 and 15" sentence to name the landing.
- [X] T011 [P] Extend `tests/unit/test_paging.py` (depends on T010): `landing_index` — the kept id on its page; the row that took the removed one's place; the row before it when it was last; the previous page when a page empties (11 ids, the one at index 10 removed → page 1 at the id now at index 9); the empty list → `(1, None)`; `old_index=None` and `kept_id` absent → `(1, None)`. `tests/integration/test_competition_service.py`'s landing tests stay green unchanged.
- [X] T012 Make the competition lock public in `app/services/competitions.py` per contracts/services.md §`app/services/competitions.py`: `lock_competition(session, competition_id, subject_id) -> tuple[Competition, Subject]` is `_find(..., lock=True)` (the competition `FOR UPDATE`, then its subject `FOR SHARE`, both refreshed; `CompetitionNotFound` after a rollback for an unknown, mismatched or invisible one); `update_competition` and `cancel_competition` call it. Update the module docstring's "Contract for later milestones" to name `app.services.competition_entries` as the first user of the Upcoming-only rule and of `lock_competition`.
- [X] T013 [P] Add `count_active_members(session, team_ids: Collection[int]) -> dict[int, int]` to `app/services/teams.py` per contracts/services.md and research R13: one grouped query (`select(TeamMembership.team_id, func.count())`) over the same join chain as `list_active_members` (enrolment, class, institution, region, each active), `where(col(TeamMembership.team_id).in_(team_ids))`, `group_by(TeamMembership.team_id)`; an empty `team_ids` returns `{}` without a query; a team with no active member is absent from the result and the caller reads it as 0. Docstring: the number a team's own page lists (milestone 11.1).
- [X] T014 [P] Add the `count_active_members` tests to `tests/integration/test_team_service.py` (depends on T013): two teams with 3 and 0 members, one member in a deactivated class, one in a deactivated institution and one in a deactivated region not counted; `{}` for no ids; each count equals `len(list_active_members(...))`.
- [X] T015 Add the seeders to `tests/conftest.py` in a new "Milestone 12.2: a competition's questions and teams" section after the 12.1 helpers (depends on T007): `add_competition_question(engine, competition_id, question_id, *, text=None, reference_answer=None) -> int` inserts a copy, taking `text` and `reference_answer` from the bank row unless given, `added_at = utc_now()`, and returns the row id; `add_competition_team(engine, competition_id, team_id) -> None` inserts the link. Docstrings: "**Test-only**, but harmless: no personal data; it skips the setting, status and entry checks that `test_competition_entries_service.py` covers, and is the only way to give a **Finished** or **Cancelled** competition questions and teams."
- [X] T016 Create `app/services/competition_entries.py` with its skeleton per contracts/services.md §Types, §Errors and research R2 (depends on T010, T012): a module docstring in the style of `competitions.py`'s (what the module holds; the clock is `competitions.utc_now`, read once per call; the write order setting → competition `FOR UPDATE` → status with a fresh clock → entry under lock → change; every refusal rolls back; no link check for teams; the log lines; the contract for later milestones of contracts/services.md); `from app.services import competitions` and every clock read as `competitions.utc_now()`; `EntryKind = Literal["question", "team"]`; the frozen dataclasses `CompetitionQuestionView`, `CompetitionQuestionPage`, `TeamRow`, `RegionGroup`, `CompetitionTeamPage`, `AddableTeam`, `AddableTeamPage`, `Landing(p, entry_id)` exactly as contracts/services.md §Types; the errors `NotChangeable(status)` (carrying a `CompetitionStatus`), `EntryNotFound(kind)`, `AlreadyIn(kind, entry_id)`, `NotIn(kind, entry_id)` (re-using `competitions.ManageRequired` and `competitions.CompetitionNotFound`); a private `_upcoming(session, teacher_id, competition_id, subject_id) -> tuple[Competition, Subject]` doing steps 1–3: `can_manage_competitions(session, teacher_id, lock=True)` else roll back and `ManageRequired`; `competitions.lock_competition(...)`; `status_of(row, competitions.utc_now())` not `UPCOMING` → roll back and `NotChangeable(status)`.
- [X] T017 Make the 12.1 router's shared helpers public in `app/routers/teacher_competitions.py` per contracts/http-routes.md §Changed routes (research R7): rename `_parse_id` → `parse_id`, `_offered` → `offered_subject`, `_competition` → `find_competition`, `_not_found` → `not_found`, `_require_manage` → `require_manage`, `_teacher` → `teacher_id`, `_can_manage` → `can_manage`, `_redirect` → `redirect`, `_query` → `list_query`, `_settings` → `settings_of`, and update every caller; `SUBJECT_NOT_FOUND`, `COMPETITION_NOT_FOUND`, `TAB` and `list_path` are already public. Update the module docstring to say milestone 12.2's router (`teacher_competition_entries`) imports these, so both build the same addresses. No behaviour change; the 12.1 suite stays green.
- [X] T018 Create `app/routers/teacher_competition_entries.py` with its skeleton and include it in `app/main.py` next to `teacher_competitions.router` (depends on T016, T017), per contracts/http-routes.md §Order of checks, §Address parameters, §Refusal and research R7–R9:
  - module docstring in the style of `teacher_competitions.py`'s (the two lists, who reads and who changes, the order of checks, the addresses `subject`/`status`/`page`/`p`/`back`/`region`, the sealed notices, nothing logged here);
  - `router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")`; every page renders with `render_teacher(request, template, TAB, context)` (the **Competitions** tab);
  - not-found pages (rendered with `not_found` and `competition_not_found.html`): `REGION_NOT_FOUND = ("Region not found", "This region does not exist, or it is deactivated.")`, `QUESTION_NOT_FOUND = ("Question not found", "This question does not exist, or it cannot be added to this competition.")`, `TEAM_NOT_FOUND = ("Team not found", "This team does not exist, or it cannot be added to this competition.")`;
  - `@dataclass(frozen=True) class ListContext(subject: Subject, status: CompetitionStatus | None, page: int)` and `read_context(session, raw_subject, raw_status, raw_page) -> ListContext | None` (`offered_subject(offered_subjects(session), raw)`, `None` → the caller answers 404 `SUBJECT_NOT_FOUND`; `parse_status_filter`; `parse_page`); a helper that then calls `find_competition` → 404 `COMPETITION_NOT_FOUND`; `hidden(context)` → `{"subject": id, "status": value or "", "page": page}` for forms;
  - `entries_path(kind, competition_id, context, p=1, anchor=None, notice=None)` → `/teacher/competitions/17/questions?subject=3&status=upcoming&page=2&p=3&notice=…#question-12`, leaving out `status` for All, `page` and `p` when 1, the notice and the anchor when not given; `kind` is `"questions"` or `"teams"`, the anchor `question-<id>` or `team-<id>`; `add_page_path(kind, competition_id, context, back, p=1, region=None, anchor=None, notice=None)` → `…/questions/add?…&back=2&p=3[&region=7]…`, leaving out `back` and `p` when 1; `remove_path(kind, competition_id, entry_id, context, back)`; all built from `list_query` plus parsed values only;
  - the notice: `ENTRY_NOTICE_PURPOSE = "competition-entry-notice"`, `ENTRY_NOTICE_TTL = timedelta(minutes=10)`, `entry_notice_token(request, competition_id, kind, entry_id, outcome)` sealing `{"competition": id, "question" | "team": id, "outcome": "added" | "already" | "removed" | "absent"}`, and `read_entry_notice(request, session, token, competition) -> tuple[str, str] | None` returning `(text, kind)` — the texts and styles of research R9 ("Question 12 was added to “Spring round”" success, "Question 12 is already in “Spring round”" info, "Question 12 was removed from “Spring round”" success, "Question 12 is not in “Spring round”" info, and "Team “Comets” …" likewise, the team's name read from its `teams` row, deleted or not) — `None` for a missing, tampered, expired token, another competition's, an unknown outcome or a non-integer id;
  - `entries_refused(request, kind, competition, status, context, back)` → 409 `pages/teacher/competition_refused.html` with question "Change the questions of “<name>”?" / "Change the teams of “<name>”?", the reason by status from `ENTRY_REFUSALS` (In progress "“<name>” has already started and its questions can no longer be changed.", Cancelled "“<name>” has been cancelled and its questions can no longer be changed.", Finished "“<name>” has finished and its questions can no longer be changed.", and "teams" in place of "questions"), `back = entries_path(kind, …, p=back)`, `back_text = "Back to the competition"`, `back_link_text = "Back to the questions"` / `"Back to the teams"`;
  - `header_context(competition, subject)` for the two lists: the subject's name, `starts_at` and the status for the `details_list`.

**Checkpoint**: both tables exist on both engines, the helpers are shared, the skeletons import
cleanly, and the whole existing suite is green.

---

## Phase 3: User Story 1 - A teacher adds questions to an upcoming competition (Priority: P1) 🎯 MVP

**Goal**: the competition's questions list and "Add questions": copy a question in, stay on the
page at it with the notice and "Already in this competition" (FR-003–FR-007, FR-015–FR-019).

**Independent Test**: as a teacher with the setting, add questions 12, 9 and 15 to an upcoming
competition and check the add page, the notices, the marks and the order of the competition's
list.

### Implementation for User Story 1

- [X] T019 [US1] Add the question reads to `app/services/competition_entries.py` per contracts/services.md §Reads and research R11 (depends on T016): `question_page(session, competition_id, p) -> CompetitionQuestionPage` — the count of the competition's rows, `Paging.build(p, total)`, then one query `select(CompetitionQuestion, Question.deleted_at)` joined on `Question.id == CompetitionQuestion.question_id`, ordered by `CompetitionQuestion.id`, limited and offset by the paging; each a `CompetitionQuestionView(question_id, text, reference_answer, deleted_from_bank=deleted_at is not None)` from the **copy**, never the bank's text; `question_ids(session, competition_id) -> set[int]`.
- [X] T020 [US1] Add `add_question(session, teacher_id, competition_id, subject_id, question_id) -> None` per contracts/services.md §Writes and research R2, R3 (depends on T019): `_upcoming(...)`; the question `session.get(Question, question_id, with_for_update={"read": True}, populate_existing=True)`; `None`, `deleted_at` set, or `subject_id` not the competition's → roll back, `EntryNotFound("question")`; a copy already there → roll back, `AlreadyIn("question", question_id)`; insert `CompetitionQuestion(competition_id, question_id, text=question.text, reference_answer=question.reference_answer, added_at=now)` with the text as read under lock; commit; an `IntegrityError` → roll back, `AlreadyIn`; log `Competition question added: competition=%d question=%d`.
- [X] T021 [US1] Add the question routes to `app/routers/teacher_competition_entries.py` per contracts/http-routes.md §1–§3 (depends on T018, T020):
  - `GET /questions` (read; checks 1, 3): query `subject`, `status`, `page`, `p`, `notice`; `question_page(session, id, parse_page(p))`; `can_change = can_manage(...) and competition.status is UPCOMING`; context: the competition, `header_context`, `listing`, `can_change`, the notice, `back = list_path(subject.id, status, page, anchor=competition.id)`, `add_href = add_page_path("questions", …, back=paging.number)`, `page_href` (keeps the context, varies `p`);
  - `GET /questions/add` (manage; checks 1–4): `require_manage` first; context; competition; not Upcoming → `entries_refused`; `questions.question_page(session, subject.id, parse_page(p))`, `question_ids(...)`, the notice; `back_href = entries_path("questions", …, p=parse_page(back))`;
  - `POST /questions` (manage; checks 1–5): form `subject`, `status`, `page`, `back`, `p`, `question`; `require_manage` first; context and competition (404); status (409); `parse_id(question)` `None` → 404 `QUESTION_NOT_FOUND`; `add_question(...)`, mapping `ManageRequired` → `AccessDenied(Role.TEACHER)`, `CompetitionNotFound` → 404, `NotChangeable` → 409 refusal, `EntryNotFound` → 404 `QUESTION_NOT_FOUND`, `AlreadyIn` → 303 with `already`; success → 303 to `add_page_path("questions", …, back, p, anchor=question_id, notice=entry_notice_token(..., "added"))`.
- [X] T022 [P] [US1] Create `app/templates/pages/teacher/competition_questions.html` per contracts/http-routes.md §1 (depends on T001, T018): extends `layouts/teacher.html`; header comment; `{% block title %}Questions of “{{ competition.name }}” — {{ app_name }}{% endblock %}`; `back_link(back, "Back to the competitions")`; `page_heading("Questions of “" ~ competition.name ~ "”", action=("Add question", add_href) if can_change else none)`; `details_list([("Subject", subject.name), ("Start", <local_time captured with {% set %}>), ("Status", <competition_status_badge captured>)])` (import `time.html` `with context`); the notice (`notice(text, kind)`); `empty_state("No questions in this competition yet", "Add questions with Add question." if can_change else none)`; otherwise `page_navigation(listing.paging, page_href, "Questions", "Pages, top")`, `<ol class="text-card-list">` of `text_card("Question " ~ q.question_id, id="question-" ~ q.question_id)` each with `text_box("Question", q.text)` and `text_box("Reference answer", q.reference_answer)`, then `page_navigation(…, "Pages, bottom")`. (US3 adds the deleted mark; US5 the **Remove** links.)
- [X] T023 [P] [US1] Create `app/templates/pages/teacher/competition_questions_add.html` per contracts/http-routes.md §2 (depends on T018): `back_link(back_href, "Back to the questions")`; `page_heading("Add questions to “" ~ competition.name ~ "”")`; the notice; `empty_state("No questions in this subject yet")` when the subject has none; otherwise the top navigation ("Questions"), the `text-card-list` of the subject's questions newest first, each `text_card("Question " ~ q.id, id="question-" ~ q.id)` with its text and reference answer and a `row-actions` holding `row_note("Already in this competition")` when `q.id in in_competition`, else `post_button("/teacher/competitions/" ~ competition.id ~ "/questions", "Add", kind="secondary", outline=True, small=True, hidden={…context, "back": back, "p": paging.number, "question": q.id})`; the bottom navigation. `page_href` keeps the context and `back`.
- [X] T024 [US1] Keep the route-table tests green (depends on T021): in `tests/integration/test_routes.py` add `("POST", "/teacher/competitions/{competition_id:int}/questions")` to `test_the_write_routes_are_exact` (and its docstring: "…and a competition's questions and teams (milestone 12.2)"); add `"/teacher/competitions/{competition_id:int}/questions/add"` to `MANAGE_PATHS` (extend its docstring); add `ENTRY_READ_PATHS = frozenset({"/teacher/competitions/{competition_id:int}/questions", "/teacher/competitions/{competition_id:int}/teams"})` with a docstring (every teacher reads them; swept with the cast teacher allowed, since id 1 answers 404, not 403) and change `test_the_manage_pages_are_found` to compare against `MANAGE_PATHS` after removing `ENTRY_READ_PATHS` (only the questions path exists until T032 adds `GET /teams` — use `& declared`).
- [X] T025 [P] [US1] Create `tests/integration/test_competition_entries_service.py` with its setup and the US1 service tests (depends on T015, T020): a module docstring (research R16); a `clock` fixture patching `app.services.competitions.utc_now` (fixed at 2027-03-01 09:00 UTC); seeds of a subject "Chemistry", another subject, a manager and a teacher without the setting, an upcoming competition; tests: `add_question` copies `text` and `reference_answer` as the bank holds them; three additions are listed by `question_page` in the order of adding (12, 9, 15), not by id; `question_ids`; a question of another subject, a deleted one and an unknown id → `EntryNotFound("question")` and nothing stored; a second addition → `AlreadyIn` and one row; 25 copies page 10/10/5 and a page past the end clamps to the last; the session is usable after every refusal.
- [X] T026 [US1] Create `tests/integration/test_teacher_competition_entries.py` with its setup and the US1 route tests (depends on T021–T024): a module docstring; a `Scene` fixture (a manager Olena, a teacher Mykola without the setting, subjects "Chemistry" and "Physics", questions, the `clock` fixture and `client.cookies.set("sc_time_zone", "Europe/Kyiv")`, an upcoming "Spring round" starting 14 March 2027 10:00 Kyiv); parsing helpers on `tests/html.py` for the text cards (number, text, reference answer, row note, buttons); tests for US1-1 to US1-6: **Add question** beside the heading for Olena; the questions page title, the subject, "14 March 2027, 10:00" in a `<time>` and **Upcoming** under the heading; "No questions in this competition yet" with "Add questions with Add question."; the add page title "Add questions to “Spring round”", its back link to the questions, the subject's questions newest first with deleted ones left out, 10 per page with the navigation above and below; **Add** on question 12 → 303 to `/teacher/competitions/<id>/questions/add?subject=…&notice=…#question-12`, the page then shows "Question 12 was added to “Spring round”" (success style) and "Already in this competition" with no **Add** on question 12; adding 9 and 15 lists 12, 9, 15 on the questions page; the add page's `p` kept in the address and restored on reload (25 bank questions, add from page 2 → back on page 2); "No questions in this subject yet"; no competition name, question text or team name in any redirect address.

**Checkpoint**: a teacher with the setting can choose a competition's questions and see them in
order (MVP).

---

## Phase 4: User Story 3 - Every teacher reads a competition's questions (Priority: P1)

**Goal**: the read-only questions list for every teacher: the copies, the "Deleted from the
question bank" mark, the hints, the paging and the back link with its fallback (FR-003–FR-009).

**Independent Test**: seed 23 copies, edit and delete some bank questions, and check the order,
paging, texts, marks and back link as teachers with and without the setting.

### Implementation for User Story 3

- [X] T027 [US3] Add the deleted mark to `app/templates/pages/teacher/competition_questions.html` (depends on T022): after the two `text_box`es, a `row-actions` holding `row_note("Deleted from the question bank")` when `q.deleted_from_bank` (US5 adds **Remove** after it); the page shows no `row-actions` at all when it would be empty.
- [X] T028 [US3] Add the competitions-list fallback (spec Edge Cases, Assumptions) (depends on T018): `app/services/competitions.py::subject_id_of(session, competition_id) -> int | None` (the competition's `subject_id`, or `None` for an unknown id; docstring: only for the fallback of an address without a subject); in `read_context` of `app/routers/teacher_competition_entries.py`, a **missing or empty** `subject` falls back to the competition's own subject, the status All and the page that holds the competition (`competitions.locate(session, subject, None, competition_id).page`), so the back link leads to that list at the competition; a `subject` that is present but not offered stays 404 "Subject not found", and one that is not the competition's stays 404 "Competition not found" (FR-045 step 3); an invalid `status` reads as All and an invalid `page` through `parse_page`, as in 12.1.
- [X] T029 [P] [US3] Add the US3 service tests to `tests/integration/test_competition_entries_service.py` (depends on T019): after `update_question` changes the bank text, `question_page` still shows the copy; after `delete_question`, the copy is listed with `deleted_from_bank=True`; 23 copies → "11–20 of 23" on page 2 in the order of adding; a removed-then-re-added question (rows inserted with `add_competition_question`) sorts by its new id.
- [X] T030 [US3] Add the US3 route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T027, T028): US3-1 to US3-7 — Mykola sees the same page as Olena with no **Add question** and no **Remove**; 23 questions: "Questions 1–10 of 23", page 2 "Questions 11–20 of 23", the navigation above and below, `p` in the address and restored; each card shows "Question <bank id>", the copied text and reference answer; a bank edit after adding leaves the page unchanged; a deleted bank question shows "Deleted from the question bank"; "No questions in this competition yet" with the hint for Olena and without it for Mykola and for Olena on an In progress competition; the back link is `list_path(subject, status, page, anchor=competition)` for the context in the address; with no `subject` the back link falls back to the competition's subject, All and the page holding it (a competition on page 2 of 15); `subject=<other offered subject>` → 404 "Competition not found"; `subject=abc` → 404 "Subject not found"; `p=99` and `p=x` open the nearest valid page.

**Checkpoint**: every teacher reads a competition's questions, whatever happened in the bank.

---

## Phase 5: User Story 4 - Every teacher reads a competition's teams, grouped by region (Priority: P1)

**Goal**: the teams list in region boxes, 10 teams per page, headers repeated with the full count
(FR-010–FR-014).

**Independent Test**: seed 25 teams from three regions with one region spanning the page break and
check the grouping, order, headers, counts, rows and phone layout.

### Implementation for User Story 4

- [X] T031 [US4] Add the team reads to `app/services/competition_entries.py` per contracts/services.md §Reads and research R12 (depends on T013, T016): `team_page(session, competition_id, p) -> CompetitionTeamPage` — one query `select(Team, Institution, Region)` over `CompetitionTeam` joined to `Team`, `Institution` and `Region` for the competition (deleted teams and deactivated institutions and regions included); sorted in Python by `(region.name_key, region.id, team.name_key, team.id)`; per-region totals counted over the whole list; `Paging.build(p, len(rows))`; the page's slice grouped into consecutive `RegionGroup(region_id, region_name, total, rows)`; the page's active members through `teams.count_active_members` (0 when absent); each `TeamRow(team_id, name, institution_name, active_members, is_deleted=team.deleted_at is not None)`; `team_ids(session, competition_id) -> set[int]`.
- [X] T032 [US4] Add `GET /teams` (read; checks 1, 3) to `app/routers/teacher_competition_entries.py` per contracts/http-routes.md §6 (depends on T018, T031): as `GET /questions`, with `team_page(...)`, `add_href = add_page_path("teams", …, back=paging.number)`, and `show_actions = can_change or any(row.is_deleted for group in groups for row in group.rows)`. In `tests/integration/test_routes.py`, `ENTRY_READ_PATHS` (T024) now matches both declared paths.
- [X] T033 [P] [US4] Create `app/templates/pages/teacher/competition_teams.html` per contracts/http-routes.md §6 (depends on T001, T032): back link, `page_heading("Teams of “…”", action=("Add team", add_href) if can_change)`, the `details_list` and notice as in `competition_questions.html`; `empty_state("No teams in this competition yet", "Add teams with Add team." if can_change else none)`; otherwise `page_navigation(listing.paging, page_href, "Teams", "Pages, top")`, then for each group `{% call region_group(g.region_name, g.total, "region-" ~ g.region_id ~ "-p" ~ listing.paging.number) %}` holding `data_table(["Team", "Educational institution", "Active members"] + (["Actions"] if show_actions else []))`, rows `<tr id="team-{{ row.team_id }}">` with `cell("Team", row.name)`, `cell("Educational institution", row.institution_name)`, `cell("Active members", row.active_members)` and, when `show_actions`, an `actions_cell()` holding `row_note("(deleted)")` for a deleted team (US5 adds **Remove**); the bottom navigation. No member name and no region in the rows.
- [X] T034 [P] [US4] Add the US4 service tests to `tests/integration/test_competition_entries_service.py` (depends on T015, T031): 25 teams — "Dnipro" 4, "Kyiv" 14, "Lviv" 7 — page 1 holds the Dnipro group (total 4, 4 rows) and the Kyiv group (total 14, 6 rows), page 2 Kyiv (total 14, 8 rows) then Lviv (total 7, 2 rows), page 3 Lviv (total 7, 5 rows); regions and teams sorted by name ignoring case on both engines ("ärger" / "Apple" style names), ties by id; active members counted per team (0 for a team without members); a team of a deactivated institution or region still listed; a deleted team in a finished competition has `is_deleted`.
- [X] T035 [US4] Add the US4 route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T032, T033): US4-1 to US4-9 — the title "Teams of “Spring round”", the subject, start and badge, the back link as on the questions page; the 25-team layout above through the HTML (`section.region-group` headers "Dnipro · 4 teams", "Kyiv · 14 teams" on both pages, "Lviv · 7 teams"; "Teams 1–10 of 25"; unique `aria-labelledby` ids); "Kyiv · 1 team" for one team; the columns Team, Educational institution, Active members and no member names; a team whose institution or region was deactivated is listed; a team renamed after it was added, and one whose members moved to another team, show the current name and the current number of active members (spec Edge Cases: only questions are copied); a finished competition holding a deleted team shows it with "(deleted)", also when all its teams are deleted; "No teams in this competition yet" with the hint for Olena only; Mykola sees no **Add team**; `p` kept in the address.

**Checkpoint**: every teacher reads a competition's teams, grouped by region.

---

## Phase 6: User Story 2 - A teacher adds teams of a region (Priority: P1)

**Goal**: "Add teams": the **Region** list, the region's addable teams from every institution, and
adding one at a time (FR-020–FR-028).

**Independent Test**: as a teacher with the setting, add teams of two institutions the teacher is
not linked to, including one with no members, and check the region list, the team list, its order
and paging, the address, the notice and the marks.

### Implementation for User Story 2

- [X] T036 [P] [US2] Add `list_active_regions(session) -> list[Region]` to `app/services/regions.py` (active only, sorted in Python by `(name_key, id)`, as `list_regions` sorts) and its tests to `tests/integration/test_region_service.py` (a deactivated region left out; the order ignoring case).
- [X] T037 [US2] Add `addable_teams(session, region_id, p) -> AddableTeamPage` to `app/services/competition_entries.py` per contracts/services.md §Reads and research R14 (depends on T013, T016): live teams (`deleted_at IS NULL`) of the region's active institutions, from every institution whether or not any teacher is linked, sorted in Python by `(team.name_key, team.id)`, `Paging.build(p, total)`, the page's slice with each institution's name and `count_active_members` (0 when absent). The caller has checked the region is active.
- [X] T038 [US2] Add `add_team(session, teacher_id, competition_id, subject_id, region_id, team_id) -> None` per contracts/services.md §Writes and research R2, R4 (depends on T037): `_upcoming(...)`; the team, then its institution, then its region, each `with_for_update={"read": True}, populate_existing=True`; the team unknown or `deleted_at` set, its institution inactive, its region inactive, or its region not `region_id` → roll back, `EntryNotFound("team")`; already linked → roll back, `AlreadyIn("team", team_id)`; insert `CompetitionTeam(competition_id, team_id, added_at=now)`; commit; an `IntegrityError` → roll back, `AlreadyIn`; log `Competition team added: competition=%d team=%d`. No link check, no member check, no `reach_team` (FR-023, FR-027). In `app/services/teams.py`, replace the module docstring's "**For milestone 12**" paragraph with: any live team of an active institution in an active region may be added to a competition by a teacher with **Can manage competitions**, linked to its institution or not (`app.services.competition_entries`).
- [X] T039 [US2] Add the team-adding routes to `app/routers/teacher_competition_entries.py` per contracts/http-routes.md §7–§8 (depends on T032, T036, T038):
  - `GET /teams/add` (manage; checks 1–5): `require_manage` first; context; competition; status (409); `regions = list_active_regions(session)`; `region` missing or empty → the only region when exactly one is offered (no redirect: the address stays as it is, and every **Add** form and page-navigation link carries that region's id, so the next address holds it), else none chosen; otherwise `parse_id` and membership in `regions`, else 404 `REGION_NOT_FOUND`; with a region: `addable_teams(session, region.id, parse_page(p))` and `team_ids(...)`; context for the template: `regions` as `(id, name)` pairs, `selected`, `listing`, `in_competition`, the notice, `back_href = entries_path("teams", …, p=parse_page(back))`, `page_href` (keeps the context, `back`, `region`);
  - `POST /teams` (manage; checks 1–5): form `subject`, `status`, `page`, `back`, `region`, `p`, `team`; `require_manage` first; context and competition (404); status (409); `region` not an active region → 404 `REGION_NOT_FOUND`; `parse_id(team)` `None` → 404 `TEAM_NOT_FOUND`; `add_team(...)` with the mappings of T021 (`EntryNotFound` → 404 `TEAM_NOT_FOUND`); success or `AlreadyIn` → 303 to `add_page_path("teams", …, back, p, region, anchor=team_id, notice=…)` with `added` / `already`.
- [X] T040 [P] [US2] Create `app/templates/pages/teacher/competition_teams_add.html` per contracts/http-routes.md §7 (depends on T018): `auto-submit.js` in `{% block scripts %}`; `back_link(back_href, "Back to the teams")`; `page_heading("Add teams to “" ~ competition.name ~ "”")`; the notice; `chained_lists` with one level `{"id": "region", "name": "region", "label": "Region", "placeholder": "Choose a region", "options": regions, "selected": selected.id if selected else none, "disabled": not regions, "carry": [("subject", …), ("status", …), ("page", …), ("back", back)]}` and no `p`, so choosing a region opens page 1; then exactly one of `empty_state("No teams yet")` (no region offered), `empty_state("Select a region", "Choose a region in the list above to see its teams.")`, `empty_state("No teams in this region yet", "Choose another region.")`, or the navigation ("Teams"), `data_table(["Team", "Educational institution", "Active members", "Actions"])` with rows `id="team-<id>"` holding `row_note("Already in this competition")` or `post_button(".../teams", "Add", kind="secondary", outline=True, small=True, hidden={…context, "back", "region", "p", "team"})`, and the bottom navigation. The region is never repeated in the rows.
- [X] T041 [US2] Keep the route-table tests green (depends on T039): add `("POST", "/teacher/competitions/{competition_id:int}/teams")` to `test_the_write_routes_are_exact` and `"/teacher/competitions/{competition_id:int}/teams/add"` to `MANAGE_PATHS` in `tests/integration/test_routes.py`.
- [X] T042 [P] [US2] Add the US2 service tests to `tests/integration/test_competition_entries_service.py` (depends on T038): `addable_teams` lists teams of two institutions of the region, none linked to the manager, sorted ignoring case, 14 teams → 10/4; a deleted team and a team of a deactivated institution are not listed; `add_team` adds a team with no members and a team sharing a member with a team already in the competition; `EntryNotFound("team")` for an unknown team, a deleted one, one of another region than `region_id`, one of a deactivated institution and one of a deactivated region, nothing stored; `AlreadyIn` on a second addition, one row.
- [X] T043 [US2] Add the US2 route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T039–T041): US2-1 to US2-11 — **Add team** beside the teams heading for Olena; the add page title and back link to the teams; the **Region** list offers every active region sorted ignoring case, no "all regions" option, a deactivated region not offered; "Select a region" with its hint before a choice; the `<noscript>` **Show** button; choosing "Kyiv" lists "Teams 1–10 of 14" from every Kyiv institution including ones Olena is not linked to, each row with name, institution and active members and no region; **Add** on "Comets" → 303 back to the same region and page at `#team-<id>` with "Team “Comets” was added to “Spring round”" and "Already in this competition" on its row; "Novas" with no members is added; `region` and `p` kept in the address and restored; a single active region chosen automatically with no `region` in the address, its **Add** forms and page links carrying the region's id; no region at all → "No teams yet"; a region whose teams are all deleted or of deactivated institutions → "No teams in this region yet" with "Choose another region."; `region=<deactivated>` and `region=abc` → 404 "Region not found".

**Checkpoint**: a teacher with the setting fills a competition with teams from any institution.

---

## Phase 7: User Story 6 - Every row has a menu with the competition's lists (Priority: P1)

**Goal**: **Questions** and **Teams** on every row for every teacher, in the order **Edit**,
**Questions**, **Teams**, **Cancel competition** (FR-001, FR-002).

**Independent Test**: list competitions of every status, including a finished one of a deactivated
subject, as teachers with and without the setting, and check each menu's entries and order.

### Implementation for User Story 6

- [X] T044 [US6] Put a menu on every row of `app/templates/pages/teacher/competitions.html` per contracts/components.md §2 (depends on T021, T032): drop the `{% if can_add %}` around `actions_menu`; inside it, in this order, **Edit** when `can_add and c.status == "upcoming"`, `menu_link("Questions", "/teacher/competitions/" ~ c.id ~ "/questions?" ~ return_query)`, `menu_link("Teams", "/teacher/competitions/" ~ c.id ~ "/teams?" ~ return_query)`, and **Cancel competition** (destructive) when `can_add and c.status in ("upcoming", "in_progress")`. Update the template's header comment and the 12.1 router docstring sentence "The list shows **Add competition** and the row menus only with the setting and an active subject" (the menus are now on every row; **Edit** and **Cancel competition** keep that rule).
- [X] T045 [US6] Update `tests/integration/test_teacher_competitions.py` for the replaced 12.1 rule (SC-009) and add the US6 tests (depends on T044): rewrite the assertions that expect no menu — `test_without_the_setting_no_add_and_no_menus` (rename to `…_no_add_and_read_only_menus`), the cancelled row (`row.menu == []` around line 1044), the cancelled filter (around line 1132), the In progress menu (around line 1148), the finished and cancelled rows (around line 1195) and the deactivated-subject list (around line 1585) — naming each in a comment as replaced by milestone 12.2 FR-002; then US6-1 to US6-6: with the setting, Upcoming lists **Edit**, **Questions**, **Teams**, **Cancel competition**; In progress **Questions**, **Teams**, **Cancel competition**; Finished and Cancelled **Questions**, **Teams**; without the setting every row **Questions**, **Teams**; a finished competition of a deactivated subject **Questions**, **Teams**; each **Questions** / **Teams** href is `/teacher/competitions/<id>/questions?subject=…&status=…&page=…` with the list's context, and following it opens the page whose back link returns to that list at `#competition-<id>`.

**Checkpoint**: both lists are reachable from every row.

---

## Phase 8: User Story 5 - A teacher removes a question or a team (Priority: P1)

**Goal**: **Remove** with a confirmation, the landing after removing, and the unchanged bank and
team (FR-029–FR-033).

**Independent Test**: remove a question, a question deleted from the bank and a team after the
confirmation, use **Cancel**, and remove the last item of a page; check texts, notices, landing and
that the bank, the team and its members are unchanged.

### Implementation for User Story 5

- [X] T046 [US5] Add the entry lookups to `app/services/competition_entries.py` per contracts/services.md §Reads and research R10 (depends on T019, T031): `get_competition_question(session, competition_id, question_id) -> CompetitionQuestionView` (no bank question with that id at all → `EntryNotFound("question")`; a known one not in the competition → `NotIn("question", question_id)`); `get_competition_team(session, competition_id, team_id) -> tuple[TeamRow, str]` (the row and the region's name as stored; `EntryNotFound("team")` / `NotIn` likewise; a deleted team that is still linked is found).
- [X] T047 [US5] Add `remove_question(...) -> Landing` and `remove_team(...) -> Landing` per contracts/services.md §Writes and research R11, R12 (depends on T046): `_upcoming(...)`; the id names no bank question (team) → roll back, `EntryNotFound`; not in the competition → roll back, `NotIn`; under the lock, the ordered ids before the change (questions by `CompetitionQuestion.id`; teams in `team_page`'s order — factor the sort into a private helper shared with T031), the entry's `old_index`, delete the row, the ordered ids after; commit; log `Competition question removed: competition=%d question=%d` / `Competition team removed: competition=%d team=%d`; return `Landing(*paging.landing_index(after, None, old_index))`. A question deleted from the bank and a deleted team can be removed (FR-045 step 5).
- [X] T048 [US5] Add the four remove routes to `app/routers/teacher_competition_entries.py` per contracts/http-routes.md §4, §5, §9, §10 and research R10 (depends on T039, T047):
  - `GET /questions/{question_id:int}/remove` and `GET /teams/{team_id:int}/remove` (manage; checks 1–5): `require_manage` first; context (with `back`); competition; status (409); `get_competition_question` / `get_competition_team`: `EntryNotFound` → 404 `QUESTION_NOT_FOUND` / `TEAM_NOT_FOUND` (an id above `MAX_ID` too), `NotIn` → 303 to `entries_path(kind, …, p=back, notice=absent)` (the `GET` changes nothing); else 200 `pages/teacher/competition_entry_remove.html` with the question "Remove question 12 from “Spring round”?" and the consequence "The question stays in the question bank and can be added again." (or, for a question deleted from the bank, "The question was deleted from the question bank and cannot be added again."), or "Remove team “Comets” of School No. 5, Kyiv from “Spring round”?" and "The team and its members are not changed, and the team can be added again.", the `POST` path, `cancel_href = entries_path(kind, …, p=back, anchor=entry_id)`, the hidden context and `back`;
  - `POST /questions/{question_id:int}/remove` and `POST /teams/{team_id:int}/remove` (manage; checks 1–5): form `subject`, `status`, `page`, `back`; `require_manage` first; context; competition; status; `remove_question` / `remove_team` with the mappings of T021, `NotIn` → 303 with `absent` at `p=back`; success → 303 to `entries_path(kind, …, p=landing.p, anchor=landing.entry_id, notice=removed)`.
- [X] T049 [P] [US5] Create `app/templates/pages/teacher/competition_entry_remove.html` (depends on T018): a header comment (both confirmations); `{% block title %}{{ question }} — {{ app_name }}{% endblock %}`; `back_link(cancel_href, back_link_text)` ("Back to the questions" / "Back to the teams"); `confirmation(question, consequence, action, "Remove", cancel_href, hidden=hidden)` with the default **Cancel** label and the destructive button.
- [X] T050 [US5] Add **Remove** to both lists (depends on T027, T033, T048): in `competition_questions.html`, when `can_change`, `link_button("Remove", remove_href(q.question_id), kind="danger", outline=True, small=True)` in each card's `row-actions`, after the deleted mark; in `competition_teams.html`, when `can_change`, the same link in the row's `actions_cell()`; each link is `remove_path(kind, competition.id, id, context, back=paging.number)`, passed as a template helper or precomputed per row in `GET /questions` and `GET /teams`.
- [X] T051 [US5] Keep the route-table tests green (depends on T048): add `("POST", "/teacher/competitions/{competition_id:int}/questions/{question_id:int}/remove")` and `("POST", "/teacher/competitions/{competition_id:int}/teams/{team_id:int}/remove")` to `test_the_write_routes_are_exact`, and both `GET …/remove` paths to `MANAGE_PATHS`, in `tests/integration/test_routes.py`; `test_the_manage_pages_are_found` now matches the eight manage paths (four `GET` pages here: two add pages and two confirmations).
- [X] T052 [P] [US5] Add the US5 service tests to `tests/integration/test_competition_entries_service.py` (depends on T047): `remove_question` leaves the bank row unchanged; `remove_team` leaves the team and its memberships unchanged; a question deleted from the bank and removed is no longer offered (`question_ids` and the bank's `question_page` both lack it); a removed question re-added goes to the end with the bank's current text; the `Landing` cases: the row that took its place, the row before it when it was last, the previous page's last row when a page empties, `(1, None)` when none is left; for teams, removing a team of a region spanning a page break changes that region's total on both pages; `get_competition_question` / `get_competition_team` → `EntryNotFound` for unknown ids and `NotIn` for known ones not in the competition.
- [X] T053 [US5] Add the US5 route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T048–T051): US5-1 to US5-9 — **Remove** on every question and team for Olena; the confirmation texts for question 12, a question deleted from the bank and "Comets" of "School No. 5", "Kyiv"; **Cancel** returns to the page it came from at `#question-12` / `#team-<id>` and nothing changed; **Remove** → 303 to the same page with "Question 12 was removed from “Spring round”" (success) at the row that took its place; removing the only item of the last page lands on the previous page at its last row; removing the last one shows the empty state with its hint; the bank still lists question 12 unchanged; the team page and member count unchanged; a question deleted from the bank and removed is not offered on "Add questions"; re-adding a removed question shows it at the end with the bank's current text; a stale confirmation for an entry another teacher removed → 303 with "Question 12 is not in “Spring round”" (info).

**Checkpoint**: questions and teams come and go while the competition is upcoming.

---

## Phase 9: User Story 7 - Changes stop when the competition leaves Upcoming (Priority: P1)

**Goal**: every change re-checks the status under lock and is safe to repeat (FR-034–FR-038).

**Independent Test**: with the clock controlled, let a start pass while add and remove pages are
open, cancel a competition, store a finished one directly, and send repeated and concurrent
additions and removals.

### Tests for User Story 7

- [X] T054 [P] [US7] Add the US7 service tests to `tests/integration/test_competition_entries_service.py` (depends on T047): each of the four writes on an In progress (clock past the start), a Cancelled and a Finished competition → `NotChangeable(status)` with the right status and nothing changed; the start minute itself is In progress; `ManageRequired` for a teacher without the setting, before any entry is read (an unknown question id still gives `ManageRequired`); `CompetitionNotFound` for another subject's id and a hidden competition; the setting check comes before the competition and the status (a teacher without the setting on a cancelled competition → `ManageRequired`); on PostgreSQL only: two sessions adding the same question (and the same team) at once with a `threading.Barrier` → one row, one `AlreadyIn`; two sessions removing the same entry → one `Landing`, one `NotIn`; an addition racing `cancel_competition` → either the addition commits first and the competition is then cancelled with the entry kept, or the cancellation commits first and the addition gets `NotChangeable(CANCELLED)` — never a cancelled competition that gains an entry after its cancellation; `add_question` racing `questions.delete_question` for the same question → either the addition commits first and the copy is listed with `deleted_from_bank=True`, or the deletion commits first and the addition gets `EntryNotFound("question")` with nothing stored; `add_question` racing `questions.update_question` → the copy holds either the old text and reference answer or the new ones, never a mix (spec Assumptions, Edge Cases; research R3).
- [X] T055 [US7] Add the US7 route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T048): US7-1 to US7-6 — on In progress, Finished and Cancelled competitions both lists show no **Add question**, **Add team** or **Remove**, for every teacher; with the clock moved past the start after opening "Add questions", **Add** → 409 "Change the questions of “Spring round”?" with "“Spring round” has already started and its questions can no longer be changed." and **Back to the competition** to the questions page at `back`, and the back link "Back to the questions"; the same for "Add teams", both remove confirmations and both remove actions, with "teams" in the texts; the cancelled ("has been cancelled …") and finished ("has finished …") reasons; a competition cancelled while a remove confirmation is open → the cancelled refusal on confirming; sending the same **Add** form twice → one row, then "Question 12 is already in “Spring round”" / "Team “Comets” is already in “Spring round”" (info); sending the same removal twice → "… is not in “Spring round”" (info); reloading every 303 target after a change changes nothing (row counts unchanged).

**Checkpoint**: nothing changes outside Upcoming, and nothing is stored twice.

---

## Phase 10: User Story 8 - Deleting a team or a question elsewhere (Priority: P1)

**Goal**: deleting a team takes it out of every competition that has not finished; deleting a
question or deactivating an institution or region changes no competition (FR-039–FR-042).

**Independent Test**: put a team in an upcoming, an in-progress, a cancelled and a finished
competition, delete it, and check each; delete a question that is in a competition; deactivate an
institution and a region.

### Implementation for User Story 8

- [X] T056 [US8] Change `delete_team` in `app/services/teams.py` per contracts/services.md §`app/services/teams.py` and research R5 (depends on T007): after `reach_team(..., write=True, lock=True)` and before the commit, `session.execute(delete(CompetitionTeam).where(col(CompetitionTeam.team_id) == team_id, col(CompetitionTeam.competition_id).in_(select(Competition.id).where(col(Competition.stopped_at).is_(None)))))`; keep its row count; log `Team deleted: id=%d members=%d competitions=%d`. Update the docstring (deleting also takes the team out of every competition that is not finished; finished ones keep it) and append to the module docstring's milestone-12 paragraph (T038) that deleting a team takes it out of every competition that is not finished, the exception constitution v2.1.0 Principle IV allows.
- [X] T057 [P] [US8] In `app/templates/pages/teacher/team_delete.html` replace "The team will be hidden and can no longer join new competitions." with "The team will be hidden and taken out of every competition that has not finished. It can no longer join new competitions.", the rest of the paragraph unchanged (FR-041).
- [X] T058 [P] [US8] In `app/services/questions.py` rewrite the "**Contract for milestone 12** (enforced there)" paragraph as a statement (research R6): a competition copies a question when it is added (`app.services.competition_entries`) and keeps the copy whatever happens to the bank row; a deleted question, or one of another subject, can no longer be added. No code change; `question_delete.html` keeps "can no longer be added to new competitions" (FR-039).
- [X] T059 [US8] Add the deletion tests to `tests/integration/test_team_service.py` (depends on T015, T056): a team linked to an upcoming, an in-progress (clock past the start), a cancelled and a finished competition → after `delete_team`, linked only to the finished one; the log line reads `Team deleted: id=<id> members=<n> competitions=3` and holds no name; a teacher with Write but without **Can manage competitions** deletes it the same way; another team's links are untouched; on PostgreSQL only, `delete_team` racing `competition_entries.add_team` for the same team and an upcoming competition with a `threading.Barrier` → afterwards the team is in no competition that is not finished (either the addition was stored first and removed by the deletion, or it got `EntryNotFound("team")`) (FR-037, SC-005).
- [X] T060 [US8] Update `tests/integration/test_teacher_teams.py` and add the US8 route tests to `tests/integration/test_teacher_competition_entries.py` (depends on T056–T058): replace the assertion at `test_teacher_teams.py` around line 654 with the new sentence (SC-009, named in a comment); US8-1 to US8-7 — after deleting "Comets" on the **Teams** tab, the upcoming, in-progress and cancelled competitions' team pages no longer list it and the finished one lists it with "(deleted)"; "Add teams" no longer lists it and a crafted `POST /teams` with its id → 404 "Team not found"; deleting question 12 in the bank leaves the competition's copy with "Deleted from the question bank", it is not offered on "Add questions" of any competition, and a crafted addition → 404 "Question not found"; the milestone 11 delete confirmation still reads "can no longer be added to new competitions"; deactivating the team's institution, then its region, leaves it on the competition's teams page.

**Checkpoint**: deleted teams leave every competition that has not finished; finished ones keep
their record.

---

## Phase 11: User Story 9 - Only teachers read, and only managers change (Priority: P1)

**Goal**: the access rules on all ten routes, in the spec's order (FR-044–FR-047).

**Independent Test**: every route as each role and as teachers with and without the setting,
through addresses and submitted forms, including unknown, mismatched and hidden ids.

### Tests for User Story 9

- [X] T061 [US9] Add the access sweep to `tests/integration/test_teacher_competition_entries.py` (depends on T048): every `GET` and `POST` of the router (built from `ALL_ROUTES` filtered on `/teacher/competitions/{competition_id:int}/`, so a later route is covered) → 403 naming the role for the administrator and the student, through typed addresses and submitted forms, with a snapshot of `competition_questions` and `competition_teams` unchanged; every manage route → 403 for Mykola, also with unknown competition, subject, region, question and team ids (the setting is checked before any id is read); the two lists → 200 for Mykola; for Olena: 404 "Subject not found" for an unknown subject, 404 "Competition not found" for an unknown competition and one of another subject, each before a status refusal; a competition hidden by a deactivated subject → 404 before a status refusal (a hidden cancelled competition → 404, not 409), seeded both ways because `competitions.offered_subjects` keeps a deactivated subject only while it has a finished competition: with a finished competition of the same subject (seeded with `make_competition(..., stopped=True)`) the subject is offered and the answer is "Competition not found"; without one the subject is not offered and the answer is "Subject not found"; the status refusal before an unknown question, region or team id (a cancelled competition with `question=999999` → 409); 404 "Team not found" for a team of another region than the one in the form, a deleted team and a team of a deactivated institution or region; 404 "Question not found" for another subject's question, a deleted one and `question=abc`; a removal of a question deleted from the bank that is in the competition passes; a `POST` without the cross-site token is refused and changes nothing; the setting removed (with `update_teacher`) between opening "Add questions" and pressing **Add** → 403 and nothing stored; no route answers with FastAPI's JSON errors for odd values (`subject=1e9999`, `p=-1`, `back=%00`, `region=٣`, a 30-digit id); a path id that is not a number (`/teacher/competitions/abc/questions`, `…/questions/abc/remove`, `…/teams/abc/remove`) matches no route and answers 404 for every role, without "Competition not found", as 12.1's `test_a_path_id_that_is_not_a_number_matches_no_route` accepts (contracts/http-routes.md §Order of checks).

**Checkpoint**: every page and action is refused to everyone it must be.

---

## Phase 12: User Story 10 - Deactivated subjects (Priority: P2)

**Goal**: the 12.1 deactivation rules extend to both lists (FR-043).

**Independent Test**: with a finished competition stored directly, deactivate its subject and check
both lists read-only, and "not found" on every page and action of an upcoming one.

### Tests for User Story 10

- [X] T062 [US10] Add the US10 tests to `tests/integration/test_teacher_competition_entries.py` (depends on T048): with a finished competition of the subject seeded first (so `offered_subjects` still offers the deactivated subject; see T061), after `set_subject_active(…, False)`, every page and action of this milestone for an upcoming, an in-progress and a cancelled competition of the subject → 404 "Competition not found" (forms opened before the deactivation and sent after it included), nothing changed; a finished competition of the subject (with copies and links seeded by T015) shows both lists read-only, the menu on its row offers **Questions** and **Teams**, and its questions page lists the copies, including questions the bank now hides because the subject is deactivated; its add pages and remove confirmations → 409 "has finished …" (the competition is found, its status refuses).

**Checkpoint**: finished competitions keep their lists after their subject's deactivation;
everything else is hidden.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: contracts, logging, documents, the manual browser checks and delivery.

- [X] T063 [P] Extend `tests/integration/test_form_contract.py` and `tests/integration/form_contract.json`: new cases `teacher-competition-questions`, `teacher-competition-questions-add`, `teacher-competition-teams`, `teacher-competition-teams-add` (with a chosen region, so the **Add** forms and the region `GET` form are captured), `teacher-competition-entry-remove` (question and team) and `teacher-competition-entry-refused`, generated once with `UPDATE_FORM_CONTRACT=1` for those cases only; update `teacher-competitions` for the new menu entries (links, not forms, so only if the case records them); add a "**Milestone 12.2**: a competition's questions and teams (`teacher-competition-questions*`, `-teams*`, `-entry-*` cases) are new, generated once …" line to the module docstring; every other case unchanged.
- [X] T064 [P] Extend `tests/integration/test_page_patterns.py` with this milestone's pages: both lists have a back link, a `page_heading`, the details list and badges for statuses; the add pages have a back link and either the empty state or the list between two page navigations; the remove page is a confirmation with a destructive **Remove** and **Cancel**; the refusal uses `refusal` with **Back to the competition**, while the 12.1 refusals keep **Back to competitions**; the teams list uses `region_group`, never a table caption; every **Add** and **Remove** on these pages is a `<button type="submit">` inside a `POST` form (from `post_button` or `confirmation`), never `disabled` and with no inline script, so the milestone 10.1 `loading-feedback.js` that every page loads (`tests/integration/test_layout.py`) marks it busy and keeps the form from being sent twice (FR-049, spec Edge Cases "Pressing Add twice"; the second request that arrives anyway is T055's "already in" case).
- [X] T065 [P] Add the logging tests (FR-048) to `tests/integration/test_competition_entries_service.py`, with `caplog` on `uvicorn.error` as `test_competition_service.py` does: `add_question`, `remove_question`, `add_team` and `remove_team` each log exactly one of the four lines with ids only; no record contains the competition name, the team name, the institution name or the question text; "already", "absent" and every refusal log nothing.
- [X] T066 [P] Update `README.md`: a competition's questions and teams (who reads them, who adds and removes them and while it is Upcoming, that questions are copied, teams added from any institution, and that deleting a team takes it out of every competition that has not finished).
- [X] T067 Run the manual and ad hoc browser checks of [quickstart.md](./quickstart.md) §2–§5 (the upgrade and downgrade of a 12.1 database; the walk-through; the **Region** list without JavaScript; the region boxes at 360 px and 375 px as labelled cards with long names wrapping and no sideways scroll; both lists, the add pages, the confirmation and the refusal in Light and Dark; the menu entries by keyboard; the gallery's `#region-group`; reload and repeat) with an ad hoc Playwright run (`uv run --with playwright`, a copy of the database, port 8765) as in milestones 10.1 and 12.1, and record the results, with any deviation, in `specs/012.2-competition-questions-teams/pr-notes.md`.
- [X] T068 Run `uv run ruff check`, `uv run ruff format --check` and the whole suite on SQLite and on PostgreSQL (`TEST_POSTGRES_URL`); fix anything red (SC-009: only the 12.1 no-menu assertions and the 11.1 confirmation wording were changed, each named). On delivery, move milestone 12.2 to **Delivered** in `docs/requirements/milestones.md` with a short summary and its spec link, as the other delivered milestones have.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. T001 → T003 → T006; T002, T004, T005 in parallel with
  T001 (T004 after T001's markup is settled).
- **Phase 2 (Foundational)**: after Phase 1. T007 → T008 → T009; T007 → T015; T010 → T011;
  T010, T012 → T016; T013 → T014; T017; T016, T017 → T018. Blocks every story.
- **US1 (Phase 3)**: after Phase 2. T019 → T020 → T021 → T024; T022, T023 in parallel with T021;
  T025 after T020; T026 last.
- **US3 (Phase 4)**: after US1 (it completes the questions list).
- **US4 (Phase 5)**: after Phase 2; independent of US1 except for sharing the router file
  (T032 after T021 when one person edits the router).
- **US2 (Phase 6)**: after US4 (the "Add team" action and the back link land on the teams list).
- **US6 (Phase 7)**: after US1 and US4 (the menu links to both lists).
- **US5 (Phase 8)**: after US3 and US2 (it adds **Remove** to both lists and the router).
- **US7 (Phase 9)**, **US9 (Phase 11)**, **US10 (Phase 12)**: after US5, the last route.
- **US8 (Phase 10)**: T056–T058 can start any time after T007 and T038; T059, T060 after US4 and
  US2.
- **US11**: delivered by Phase 1.
- **Polish (Phase 13)**: after every story.

### Within each story

- The service read or write before the routes that call it; templates in parallel with the
  routes; the route-table test updates in the same phase as the routes they cover, so the suite
  stays green; the story's tests last.

### Parallel opportunities

- Phase 1: T002, T004, T005 alongside T001; T006 after T003.
- Phase 2: T009, T011, T013/T014 and T017 alongside each other once T007 and T010 are done.
- US1: T022, T023 while T021 is written; T025 alongside T026's setup.
- US4: T033 and T034 together.
- US2: T036 any time after Phase 2; T040 and T042 together.
- US5: T049 alongside T048; T052 alongside T053.
- US8: T057, T058 alongside T056.
- Polish: T063–T066 together.

## Parallel Example: User Story 1

```bash
# After T020 (add_question) is done, in parallel:
Task: "T021 Add GET /questions, GET /questions/add, POST /questions to app/routers/teacher_competition_entries.py"
Task: "T022 Create app/templates/pages/teacher/competition_questions.html"
Task: "T023 Create app/templates/pages/teacher/competition_questions_add.html"
Task: "T025 Create tests/integration/test_competition_entries_service.py (US1 service tests)"
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1: the region group, the refusal link text and the documents.
2. Phase 2: the tables, the migration, the shared helpers, the skeletons, the seeders.
3. Phase 3: the questions list and "Add questions". **Stop and validate**: add three questions to
   an upcoming competition and find them in order, with the copies in the database.

### Incremental delivery

1. US3 (the read-only questions list) → US4 (the teams list) → US2 (adding teams) → US6 (the menu
   on every row) → US5 (removing) → US7 (status and concurrency proof) → US8 (team deletion) → US9
   (access sweep) → US10 (deactivated subjects).
2. Each story ends with its tests green on both engines and the whole suite green.
3. Polish: contracts, logging, README, the manual browser run, delivery.
