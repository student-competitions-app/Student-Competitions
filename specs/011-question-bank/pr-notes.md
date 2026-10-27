# PR notes: Question bank (teacher), milestone 11

For the PR description. The spec, plan and contracts are in this folder.

## What changed

- **A Questions tab** (`/teacher/questions`) between Students and Competitions: a list of active
  subjects, then the subject's questions, newest first, 10 per page, with page navigation above
  and below. Subject and page are in the address.
- **Adding, editing and soft deletion**, only for teachers with **Can manage competitions**:
  - **Save question** returns to page 1;
  - **Save and add one more question** opens an empty form with a notice;
  - edit, Cancel and delete return to the page the teacher came from, at the question
    (`#question-<id>`);
  - deletion sets `deleted_at` and nothing else.
- **Access**: every route is teacher-only. On the 6 management endpoints the setting is checked
  before any id is looked up, and again inside the write transaction, under lock. An unknown or
  deactivated subject, and an unknown, deleted or hidden question, get a 404 page in the teacher
  frame.
- **One migration** (`3e32707ed794`):
  - deletes the milestone 3 sample questions;
  - adds `questions.subject_id` (FK, indexed) and `deleted_at`, with both texts at 2,000
    characters and SQLite `AUTOINCREMENT`;
  - renames `teacher_profiles.can_create_competitions` to `can_manage_competitions`.
- **The setting is shown as "Can manage competitions"** on the Teachers tab, both teacher forms,
  the acceptance page, the invitation email and the profile.
- **A subject with any question, deleted ones included, cannot be deleted** (`count_subject_uses`).
- **The home page** lists no questions. Its database line and unavailable message stay, and the
  teacher card now says "Manage your classes and students, and see the question bank."
- **New and extended components**, each in the library, the gallery and `ui-guidelines.md` first:
  - `page_navigation` (`components/pagination.html`; logic in `app/services/paging.py`);
  - a second save button in `form_actions`;
  - `textarea_field`;
  - `text_card` and `text_box`, with `.text-card-list`. The plan's `.question-list` is banned by
    the page-specific class check, so the list class belongs to the component instead.

## The no-script Show button

The `chained_lists` selector has had no submit button since milestone 9 (commit `f866721`), so it
did not work without JavaScript. Each level's form now has a nameless **Show** button inside
`<noscript>`. With JavaScript nothing changes. Without it the subject list works, and **the
Students tab's three lists work again too**. The form contract is unchanged: the button has no
`name`.

## The three-tab row (FR-011, R14)

Measured with ad hoc Playwright (Chromium) on `/teacher/questions` against a seeded copy of the
local database, with Questions current and with Competitions current:

| Viewport | Tab rows | Frame bottom | Sideways scroll |
|---|---|---|---|
| 360 × 640 | 1 | 114.5 px | no |
| 375 × 667 | 1 | 114.5 px | no |

The frame stays under `--sc-frame-clearance-tabs` (176 px below 768 px). A `#question-<id>` link
puts its card at 175.5 px, below the frame. A field-error link puts the field's label at 165 px
and the field at 256 px. The clearance note in the guidelines is unchanged.

Screenshots of these pages are in the git-ignored `screenshots/011/`, at 1280 × 800 and
360 × 640, in Light and Dark:

- the list with page navigation;
- the add form with errors and with the saved notice;
- the edit form and the delete confirmation;
- a question with a 300-character word;
- the gallery's pagination, forms and cards sections;
- the Questions and Students tabs without JavaScript.

No page scrolls sideways.

## Replaced tests (SC-010)

- **Sample questions**:
  - the home page list tests and the `sample_questions` fixture are retired;
  - `test_migrations` now expects no questions at head, and checks a real upgrade from
    `596ead9f1205` (samples gone, setting values kept), the new columns, SQLite `AUTOINCREMENT`
    and PostgreSQL's preserved id sequence;
  - `test_home` gained the US8 cases.
- **The milestone 3 question service and schema tests** are rewritten for the bank
  (`test_question_service.py`, `test_question_schemas.py`).
- **The old setting name**: every test that named it now uses the new name.
  - The form contract records the renamed checkbox, a deliberate change noted in
    `test_form_contract.py`.
  - The new cases cover a legacy sealed invitation, the sealed key set, and a guard that the old
    name is gone from `app/` (`tests/unit/test_setting_name.py`).
- **The Show button**: `test_teacher_classes` asserted that there was no Show button. It now
  asserts that Show is only inside `<noscript>`.
- **Generic sweeps**:
  - `test_teacher_access.py` leaves the Questions tab out;
  - `test_routes.py` skips the allowed-teacher check for the three management pages, with a guard
    (`MANAGE_PATHS`);
  - `test_teacher_questions.py` sweeps all 7 endpoints with real ids, per role and per setting
    value, including race cases.

`ruff check`, `ruff format --check` and `pytest` pass on SQLite and PostgreSQL: 3,329 passed, and
5 skipped for engine-specific cases. `ruff format` also reformatted the Python block in
`contracts/services.md`, whitespace only, so the repository-wide format check passes.

## Things to know

- **The downgrade is lossy by design (R3)**: it deletes every question and does not restore the
  samples. Questions with a subject and 2,000-character answers do not fit the old shape.
- **The legacy invitation key**: invitations sealed before this deployment carry
  `can_create_competitions`. `details_from_payload` still reads it (`LEGACY_SETTING_KEY` in
  `app/services/teachers.py`). It and its tests can go 7 days after the deployment, when every such
  invitation has expired; the steps are in `docs/issues-to-fix.md` §2.
- **The real upgrade was checked by hand** on a copy of `data/student_competitions.sqlite3`:
  - the copy was taken to `596ead9f1205` (6 samples), and two teacher profiles were added with
    `true` and `false`;
  - after `alembic upgrade head`: 0 questions, and both values kept under
    `can_manage_competitions`.
- **The published teacher consent text v1** still says "create competitions". It is append-only
  and describes the stored data in prose (R12).
