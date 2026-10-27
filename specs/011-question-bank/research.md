# Research: Question Bank (Teacher) (Milestone 11)

Phase 0 of [plan.md](./plan.md). The spec has no open clarifications, so each entry below records a
design decision, the reason for it and the alternatives considered.

---

## R1. A question's number is its id

**Decision**: the number shown ("Question 57", "Delete question 57?") is `questions.id`. It is
global across the bank (spec Assumptions) and given once, in creation order.

- **No reuse on PostgreSQL**: the id sequence never goes back.
- **No reuse on SQLite**: the table gets `AUTOINCREMENT` (`sqlite_autoincrement=True` on the model,
  and `table_kwargs` in the batch rebuild), so a rowid is never handed out twice, even if the
  highest row were ever removed.
- **Never hard-deleted**: after this milestone nothing deletes a question row: deletion is soft (R2),
  questions do not refer to people (R12), and data erasure does not touch them. The number of a
  deleted question can therefore never pass to another question (FR-003).

**Order**: newest first is `ORDER BY id DESC`.

- **Same as creation order**: ids are given in creation order, so this is "by creation time" (spec
  Assumptions).
- **Cheap**: the order uses the primary key.
- **Easy to read**: numbers fall steadily down the page.
- **Edits do not move a question**: editing changes neither the id nor the order.

**Rationale**: one column already has every required property, so a second counter would add a
table or a sequence, a unique constraint and a race, for no visible gain.

**Alternatives considered**:

- **A separate `number` column from its own counter**: more code and a concurrency rule, with
  nothing gained.
- **A number per subject** ("Physics question 3"): the spec settles on global numbers, and per-subject
  numbers need a locked counter row per subject.
- **Ordering by `created_at`**: two questions saved in the same microsecond would need `id` to break
  the tie anyway.

---

## R2. Soft deletion with `deleted_at`

**Decision**: a nullable, UTC-aware `deleted_at` column.

- **Deleting** sets it to the current time and changes nothing else: text, reference answer,
  subject, number and `updated_at` stay as they were (FR-004, SC-003).
- **A listed question** is one with `deleted_at IS NULL`.
- **For milestone 12**: a question can be added to a new competition only if `deleted_at IS NULL`.
  The services contract states this rule.

**Rationale**: one column marks the state and records when it changed, and makes both the check
("is it deleted?") and the query ("listed questions") a plain `IS NULL`.

**Alternatives considered**:

- **An `is_deleted` boolean**: the same check, but it loses the time.
- **Moving deleted questions to another table**: milestone 15 would then need a union to show a
  competition's questions.
- **Hard deletion**: forbidden by FR-004.

---

## R3. One migration, with the sample questions deleted first

**Decision**: one revision, `question_bank`, after `596ead9f1205`. It runs in this order:

1. **Delete every row of `questions`.** These are the milestone 3 sample questions: before this
   milestone, nothing could add a question through the website (spec Assumptions, FR-042).
2. **Rebuild `questions`** in batch mode, so it works on SQLite:
   - add `subject_id INTEGER NOT NULL`, a foreign key to `subjects.id`, indexed as
     `ix_questions_subject_id`;
   - add `deleted_at TIMESTAMP WITH TIME ZONE NULL`;
   - change `text` from `VARCHAR(1000)` to `VARCHAR(2000)`;
   - change `reference_answer` from `VARCHAR(5000)` to `VARCHAR(2000)`;
   - turn on SQLite `AUTOINCREMENT`.

   The table is empty, so the new required column needs no default, and the shorter
   `reference_answer` cannot cut any value short.
3. **Rename `teacher_profiles.can_create_competitions`** to `can_manage_competitions` in batch mode,
   keeping every value (FR-009, SC-006).

**Downgrade**:

- **The setting**: the column is renamed back.
- **The questions**: every question is deleted and the old column shapes come back.
- **Lossy on purpose**: questions with subjects and up to 2,000 characters of answer do not fit the
  old shape. The downgrade does not restore the sample questions. This matches the milestone 5
  precedent: its role-list downgrade deactivates people. Downgrades are a development tool here.
  The stairway test still passes, since it checks revisions and tables, and at head `questions`
  starts empty.

**The seed migration `bba0b3665864` stays frozen**: applied migrations are never edited. A fresh
database still runs it, and the new revision then deletes its rows.

- **Retired fixture**: the `sample_questions` fixture and `SAMPLE_QUESTIONS` lookups in the tests go
  away.
- **New expectations**: `test_migrations` expects `questions` to be empty at head, and adds a case
  that upgrades a database holding the samples and profiles with both setting values.

**Rationale**: one revision keeps the milestone's schema change atomic and reviewable. Deleting
before rebuilding avoids defaults for a required foreign key, and avoids a narrowing cast on
PostgreSQL.

**Alternatives considered**:

- **Giving the sample questions a placeholder subject**: it invents data, and it makes some subject
  undeletable for ever.
- **Deleting the samples by their text**, as the seed's downgrade does: any other row would then
  block the required column. There are no other rows, so "every row" is both simpler and exact.
- **Two revisions** (rename, then questions): no benefit, and two heads to keep in order.

---

## R4. Text rules for the question text and the reference answer

**Decision**: `app/schemas/question.py` keeps the field rules. One pure function,
`clean_question_field(raw, field)`, returns the clean value or raises `InvalidQuestionField` with a
ready message. In this order:

1. **Normalise line endings**: `\r\n` and lone `\r` become `\n`. Browsers send a textarea's line
   breaks as CRLF, so without this every line break would count as 2 characters, and the stored
   text would depend on the browser.
2. **Refuse NUL** (`\x00`): "The question text cannot contain a null character." (or "The reference
   answer …"). PostgreSQL cannot store NUL in text, so without this a crafted request would end in a
   500. A browser cannot send it from typing, so in practice only crafted requests meet it.
   Everything else is kept: tabs, line breaks, any script, `<`, `&` (spec Assumptions: no further
   character rules).
3. **Trim** surrounding whitespace (`str.strip()`). Empty: "Enter the question text." / "Enter the
   reference answer."
4. **Length** in Unicode code points, at most 2,000 (`QUESTION_FIELD_MAX_LENGTH`): "The question
   text can be at most 2,000 characters." / "The reference answer can be at most 2,000 characters."
   This follows the milestone 6 wording for names.

**Errors**: both fields are checked on every submission, and each error is a field error, shown
beside its field and in the summary (FR-029, FR-039). The textareas carry `required` and
`maxlength="2000"`, as the existing name fields do. The server stays the authority.

**Removed**: the milestone 3 pydantic types (`QuestionCreate`, `QuestionUpdate`, `QuestionPublic`)
are removed. They served the home page list and the internal service, and both are gone. Both
columns use `QUESTION_FIELD_MAX_LENGTH`, so the rule and the column cannot drift.

**Alternatives considered**:

- **Keeping pydantic `StringConstraints`**: it cannot normalise line endings before counting, and its
  messages are not the project's wording. The milestone 6–9 forms all use small clean functions with
  ready messages.
- **Silently removing NUL**: changing what the teacher sent without saying so.

---

## R5. Access: the setting, and the order of checks

**Decision**: `app/services/teacher_access.py` gains
`can_manage_competitions(session, teacher_id, *, lock=False) -> bool`.

- **The rule**: it is true only if the teacher has a `teacher_profiles` row and that row's
  `can_manage_competitions` is true.
- **No profile means no setting**: a teacher without a profile row has no setting. This covers the
  test cast's directly seeded teachers.
- **Locking**: with `lock`, it reads the row `FOR SHARE` and refreshes it (`populate_existing`).
- **One authority**: this module already decides every teacher-scope question (milestone 9 D5).

**Order of checks** on every request (FR-037, spec Assumptions "Access before existence"):

1. **Role**: `@allow_roles(Role.TEACHER)`. An administrator or a student gets the milestone 5 403
   page, which names their current role.
2. **Setting**: on the add, edit and delete pages and actions. Without it, the teacher gets the same
   403 page (`AccessDenied(Role.TEACHER)`), before any id or form value is read.
3. **Ids**: a `subject` value that is not an ASCII integer up to `MAX_ID`, an unknown subject, a
   deactivated subject, an unknown question, a deleted question, or a question of a deactivated
   subject. Each gets "not found" (R6).
4. **Fields**: field errors (400).
5. **The write**: the service checks steps 2 and 3 again inside its transaction (R7).

A path id that is not an integer (`/teacher/questions/abc/edit`) matches no route, so it gets the
application's 404 for everyone, as in milestones 6–9. No route exists there, so the 404 reveals
nothing.

**On the list page**, the setting decides only what is shown: **Add question**, **Edit** and
**Delete** (FR-008, FR-021).

**Rationale**: checking the setting first means a teacher without it learns nothing about which
questions exist. Checking it again inside the transaction covers a setting removed between the page
and the save (US5-6).

**Alternatives considered**:

- **A FastAPI dependency for the setting**: the routers would still need the in-transaction check,
  and the ordering against id parsing is clearer in the handler. Milestone 9 checks access the same
  way.
- **"Not found" for a teacher without the setting**: rejected by the spec (US5-2).

---

## R6. "Not found"

**Decision**: one template, `pages/teacher/question_not_found.html`, in the teacher frame with the
**Questions** tab current, returned with status 404. It has two headings:

- **"Subject not found"**, for the add page and action: "This subject does not exist or is
  deactivated."
- **"Question not found"**, for the edit and delete pages and actions: "This question does not
  exist, was deleted, or its subject is deactivated."

The back link goes to the **Questions** tab (`/teacher/questions`), with no subject in the address.
The subject may be the missing thing, so the link does not name it.

**Rationale**: the spec makes these cases "not found" rather than "access denied", because the
teacher may reach the bank and the thing is simply not there. One template keeps every case alike.
The milestone 6 admin pages work the same way (`subject_not_found.html`).

**Alternative considered**: raising `HTTPException(404)` for the generic error page. That page has
no teacher tabs and no back link to the bank.

---

## R7. Concurrency: locks inside each write

**Decision**: each write runs as one transaction in the service. It reads, in this order:

1. **The teacher's profile row**, `FOR SHARE`: an administrator removing the setting waits, or wins
   first and is seen (US5-6).
2. **The subject row**, `FOR SHARE`: an administrator deactivating the subject waits, or wins first
   and is seen (US5-5).
3. **For an edit or a delete, the question row**, `FOR UPDATE`, read before the subject, since the
   subject comes from the question. Two teachers deleting or editing the same question take turns;
   the second sees `deleted_at` set and gets "not found".

Every read uses `populate_existing=True`, so the check sees the committed state, not an earlier
read in the same request. A refusal rolls back before it raises, so no lock outlives it. This is the
milestone 9 pattern (`teacher_access._refuse`). On SQLite the locks render nothing, and SQLite
already serialises writers.

**Subject deletion against a new question**:

- **PostgreSQL**: `delete_subject` counts uses, then deletes. A concurrent add holds `FOR SHARE` on
  the subject, so the delete waits, then fails the foreign key. The existing `IntegrityError` branch
  turns that into `SubjectInUse`.
- **SQLite**: the engine serialises the two writers, so the count sees the committed question.

**Alternatives considered**:

- **No locks**, accepting rare races: the spec makes the race outcomes acceptance scenarios
  (US5-5, US5-6).
- **`SERIALIZABLE` isolation**: it changes the whole session and needs retries.

---

## R8. Addresses, return positions and anchors

**Decision**: the addresses are below. The full contract is in
[http-routes.md](./contracts/http-routes.md).

| Purpose | Address |
|---|---|
| The list | `GET /teacher/questions?subject=<id>&page=<n>` |
| The add form | `GET /teacher/questions/new?subject=<id>&page=<n>[&saved=1]` |
| Add | `POST /teacher/questions` (`subject`, `page`, `text`, `reference_answer`, `then`) |
| The edit form | `GET /teacher/questions/<id>/edit?page=<n>` |
| Edit | `POST /teacher/questions/<id>/edit` (`page`, `text`, `reference_answer`; anything else ignored) |
| The delete confirmation | `GET /teacher/questions/<id>/delete?page=<n>` |
| Delete | `POST /teacher/questions/<id>/delete` |

- **The return page**: `page` on the form and confirmation pages is the list page the teacher came
  from. It travels as a number only, and it is parsed like the list's own `page` (R9). The return
  address is always built on the server by one helper, `list_path(subject_id, page, anchor)`, so it
  can never be an address taken from the request (FR-035, spec Edge Cases).
- **Save question** (`then=list`, or `then` missing or unknown): 303 to
  `/teacher/questions?subject=<id>`, the top of the first page, where the new question is first
  (FR-027).
- **Save and add one more question** (`then=another`): 303 to
  `/teacher/questions/new?subject=<id>&page=<n>&saved=1`. The empty form shows the success notice
  "The question was saved." and keeps the return page, so **Cancel** still leads back (spec
  Assumptions). Reloading it shows the notice again but stores nothing. `saved` carries no data, so
  it does not need sealing, unlike the milestone 9 `sent` notice, which names an email address.
- **Edit save, Cancel, and Cancel on the delete confirmation**: 303 or a link to
  `/teacher/questions?subject=<id>&page=<n>#question-<id>` (FR-032, FR-033).
- **Delete**: the landing is worked out from the question's position at the moment it is deleted
  (FR-034). Let `i` be its 0-based index in the subject's listed questions, newest first.
  - **The next question** is the one that now holds index `i`. If it exists, land on it.
  - **Otherwise, the previous question**, the one at `i − 1`. If it exists, land on it.
  - **Otherwise**, the subject is now empty: land on `/teacher/questions?subject=<id>`, which shows
    "No questions yet".

  The page is `target_index // 10 + 1`. One rule gives all three cases:
  - the next question, from the same page or moved up from the next page;
  - the question before, on the same page;
  - the last question of the previous page, when the page became empty.

  **When nobody else changed the list**, this is exactly the page the teacher came from. **When
  someone did**, the landing follows the deleted question's real position, so the anchor always
  exists. The delete action therefore does not need a `page` field.
- **The anchor**: each question's box has `id="question-<id>"`. The milestone 10.1 rule
  `scroll-padding-top: var(--sc-frame-clearance-tabs)` already keeps every `#` target below the
  pinned frame and tabs, without JavaScript (FR-036). No new CSS or script is needed.

**Alternatives considered**:

- **The subject in the path** (`/teacher/questions/subjects/<id>/new`): this is the milestone 9 style
  for classes. A query value keeps the list and the add form on one parameter name, and makes "a
  subject in the address" mean the same thing everywhere.
- **Storing the return position in the session**: the spec requires the address (FR-035).
- **Landing after a deletion on the `page` that was sent**: under concurrent changes the anchor may
  then point to a question that is not on that page. Using the position is exact, and without
  concurrent changes it gives the same page.

---

## R9. Paging

**Decision**: a pure module, `app/services/paging.py`.

- **Page size**: `PAGE_SIZE = 10`.
- **`parse_page(raw: str | None) -> int`**:
  - missing, empty, not ASCII digits, or `0` gives `1`;
  - more than 9 digits gives `MAX_PAGE` (999,999,999), which is then clamped to the last page. This
    also avoids Python's limit on very long integer strings.
- **`Paging.build(page, total, size=PAGE_SIZE)`**:
  - `last = max(1, ceil(total / size))`, and `number = min(max(page, 1), last)`;
  - `first_item` and `last_item` give the range ("Questions 31–40 of 200");
  - `previous` and `next` are `None` at the ends;
  - `items` is the page links with gaps.
- **The gap rule**: always show the first page, the last page, the current page and one page on each
  side of it. A run of two or more hidden pages becomes one gap mark (`…`). A run of exactly one is
  shown as its number, since a gap mark would take the same room and hide it.
  - Page 10 of 20: `1 … 9 10 11 … 20`.
  - Page 3 of 20: `1 2 3 4 … 20`.
  - Page 1 of 4: `1 2 3 4`.

  This gives at most 7 entries, so the navigation stays short on a phone.
- **Past the end**: the list renders the last page directly, without a redirect. The address keeps
  what was typed, the navigation marks the real page, and no extra request is made (FR-024).
- **With one page**: the navigation still shows the range, with **Previous** and **Next**
  unavailable. With no listed question it is not shown (spec Assumptions).

**Rationale**: the logic is the same for every future paged list (competitions in milestone 12,
results in 15), and pure code is unit-tested exhaustively without HTTP. It belongs to the component,
not to questions.

**Alternatives considered**:

- **A redirect to the clamped page**: one more round trip, for a nicer address only.
- **Building the gaps in Jinja**: hard to test, and hard to read.
- **Keyset paging**: page numbers in the address (FR-022) need offsets, and offsets of a few hundred
  are cheap here.

---

## R10. Components added before use

**Decision**: four additions to the component library, each first shown in the gallery and
described in `ui-guidelines.md`. The full contracts are in
[components.md](./contracts/components.md).

1. **`page_navigation(paging, href, noun, label)`**, in a new file `components/pagination.html`:
   - a `<nav>` with its own label, so the two copies on a page can be told apart ("Pages, top" and
     "Pages, bottom");
   - the range as text ("Questions 31–40 of 200");
   - **Previous**, the page numbers and **Next**, as links;
   - the current page as `aria-current="page"`;
   - an unavailable **Previous** or **Next** as text, not a link;
   - gaps as a hidden `…`.

   It wraps on a phone, and every link keeps the 44 px touch target. It needs no JavaScript
   (FR-023, FR-025).
2. **`form_actions` with a second save button**: new optional `name` and `value` for the primary
   button, and `secondary`, a mapping (`label`, `name`, `value`) for a secondary button after it.
   The order is primary, secondary, then **Cancel** as a link.
   - **Enter in a single-line field** submits with the first button, the primary one.
   - **No JavaScript needed**: both buttons send their value without JavaScript.
   - **The busy-button script** (10.1) never disables a button, so the value survives (FR-030).
3. **`textarea_field(id, label, value, error, hint, name, rows, attrs)`**, in `form.html`: the
   multi-line twin of `field`, with the same label, hint, error and `aria-describedby` wiring, and
   the value kept exactly as entered.
   - **No such field exists yet**: no form has had multi-line input before.
   - **Why a component**: building one by hand on the page would break Principle II.
4. **`text_card(heading, id)` and `text_box(label, text)`**, in `card.html`. A `text_card` is one
   large box with a heading ("Question 57") and an optional anchor id. Its body comes from
   `{% call %}`: one or more `text_box` sections, each a smaller bordered box with a small label
   ("Question", "Reference answer") and the text with `.keep-lines`. The actions come after, in the
   existing `row-actions` row (FR-019).
   - **Wrapping**: very long words wrap inside the box (`overflow-wrap: anywhere`, already in
     `.keep-lines`).
   - **Reuse**: milestones 12, 13 and 15 show questions, answers and reference answers in the same
     way.

**Rationale**: the constitution and the guidelines' "Adding a pattern" steps require every new
markup pattern to be in the library first.

- **Two of these are named by the spec**: page navigation and the two-button form.
- **Two more are needed by the pages**: the multi-line field and the question box. Building either
  by hand on the page would break FR-047.

**Alternatives considered**:

- **Reusing `card()`**: it is an `h3` link card with a description, made for the home page areas.
  Overloading it with nested boxes would change its contract for every caller.
- **Reusing `details_list`** for the question and answer: it is a label/value grid that becomes two
  columns from 768 px. Long texts need full width.

---

## R11. The subject list

**Decision**: `chained_lists` with one level:

- `id="subject"`, `name="subject"`, label **Subject**, placeholder "Choose a subject";
- the options are `list_active_subjects`, the active subjects sorted like `list_subjects` (by name,
  ignoring case, then id), so both engines give the same order;
- no `carry` values, so changing the subject drops `page` and opens the first page (FR-017).

It submits itself through `auto-submit.js`.

**Without JavaScript the existing selector does not work today.** Milestone 9 removed the **Show**
buttons (commit `f866721`), so a `<select>` alone cannot send its form, while FR-012 and US2-14
require the subject list to work without JavaScript.

- **The fix**: `chained_lists` gains a **Show** button inside `<noscript>` in each level's form: a
  secondary, small button.
  - **With JavaScript**: nothing changes, and the page looks exactly as it does today.
  - **Without JavaScript**: the button appears and submits the level's form.
- **Where it applies**: the change is inside the component, so the Students tab's three lists gain
  the same fallback.
- **What else changes**: the gallery shows it, the guidelines describe it, and the form contract
  records the button.
- **The stylesheet check**: `<noscript>` needs no class, and the button uses existing classes.

**Alternatives considered**:

- **A visible Show button again**: this reverses a deliberate milestone 9 choice.
- **A list of subject links** instead of a selector: the milestone names `chained_lists`.

**Selection** (FR-013–FR-016):

- **The address** is parsed like any id: an ASCII integer up to `MAX_ID`.
- **No selection**: a value that is not an id, an unknown subject or a deactivated subject counts as
  no selection, and is never an error on the list page.
- **Automatic selection**: with no valid selection and exactly one active subject, that subject is
  selected. The page renders directly, without a redirect, and its links all carry `subject=<id>`.
- **The empty states**:
  - with no active subject: "No subjects yet", hint "Ask an administrator to add a subject.";
  - with two or more active subjects and no selection: "Select a subject", hint "Choose a subject in
    the list above to see its questions.".

**Alternative considered**: `list_detail` with subjects on the left. It takes width from long
question texts, and the milestone names `chained_lists`.

---

## R12. Renaming the setting

**Decision**:

- **Storage**: the column is renamed (R3), and so are the model field and `TeacherDetails`.
- **The admin forms**: the field is renamed to `can_manage_competitions`, and the form contract
  records it.
- **Shown everywhere as "Can manage competitions"**:
  - the **Teachers** tab column;
  - the invitation and edit checkboxes;
  - the profile line;
  - the acceptance page detail line;
  - the invitation email line.
- **The explanation** on the acceptance page and in the email (FR-009):
  - "You will be able to manage competitions and change the question bank.";
  - "You will not be able to manage competitions or change the question bank.".
- **Sealed teacher invitations**: they are written with the key `can_manage_competitions`.
  - **Old invitations are still read**: `details_from_payload` also accepts the old key set
    `{"institutions", "can_create_competitions"}` and reads its value as the new setting. An
    invitation sealed before the deployment and still valid (at most 7 days) is accepted with its
    value (US6-3).
  - **Removing the old key**: it can go in any milestone after 2026-11-03, with its test.
- **The published teacher consent text v1 is not changed**:
  - **Append-only**: published consent texts are pinned by hash (milestone 8 D7).
  - **Not the label**: the text says "whether you may create competitions", which describes the
    stored data in prose and does not name the setting.
  - **No new consent needed**: the stored data does not change, so there is nothing new to agree
    to. A new consent version would ask every new teacher to agree again for a wording change only.
  - **Not covered by SC-006**: SC-006 concerns the setting's name where it is shown or set, and the
    places FR-009 lists.

**Rationale**: the values move with the column, so nothing can drift. Reading both keys is the
smallest way to keep issued links working.

**Alternatives considered**:

- **Keeping `can_create_competitions` as the stored and sealed name**: the old name would stay in the
  code for ever.
- **Invalidating old invitations**: this breaks US6-3.

---

## R13. The home page and the teacher card

**Decision**:

- **The handler**: `pages.home` no longer lists questions. Its `try` block reads only
  `read_database_status`.
- **Unchanged**: the `SQLAlchemyError` branch, its log line and its notice ("Question data is
  temporarily unavailable. Please try again in a moment.") stay exactly as they are (FR-043, US8-3).
  The spec says the page keeps "its existing message", and `test_health` pins it. Rewording it would
  be a separate change.
- **Removed**: the `#questions` section and `list_questions`.
- **The teacher card** (`areas.TEACHER_AREA.description`): "Manage your classes and students, and
  see the question bank." (FR-044). It names the bank without promising changes, which suits
  teachers without the setting.

**Alternative considered**: a count of the bank's questions on the card. It is not asked for, and it
is one more query on every home page.

---

## R14. The three-tab row against the pinned-frame clearances

**Decision**: the teacher tabs become **Students**, **Questions**, **Competitions**. They are
measured at 360 px and 375 px width in Chromium with an ad hoc Playwright run, as in milestone 10.1
(the screenshot recipe in the project memory). The result is recorded in
`specs/011-question-bank/pr-notes.md`, and in the guidelines' clearance note if it changes anything
(FR-011, SC-008).

**Estimate**:

- **The labels**, with Open Sans at 16 px, using the 10.1 measurements of "Teachers" (72 px) and
  "Subjects" (65 px):
  - "Students" about 72 px;
  - "Questions" about 81 px;
  - "Competitions" about 106 px;
  - with two 24 px gaps, about 307 px in all, or about 315 px with the current tab in bold.
- **At 360 px**: the content width is 328 px (360 − 2 × 16), so the row should fit on one line. The
  frame is then about 114 px, well under the 176 px clearance.
- **If a browser wraps it**: it becomes two rows, the same case as the administrator tabs, measured
  at 158.5 px, which is still under the 176 px clearance and under a quarter of a 667 px screen.

Either way the clearances hold. The measurement confirms which case applies.

**Alternative considered**: shorter labels. These are the spec's names.

---

## R15. Tests

**Decision**: the coverage maps onto modules as below. Every integration case runs on SQLite and
PostgreSQL.

- **`tests/unit/test_paging.py`**:
  - `parse_page` for missing, empty, `abc`, `-1`, `0`, `1`, `٣` (non-ASCII digit), 10+ digits;
  - `Paging` ranges, ends, clamping and the gap table for page counts 1–12 and 200 (SC-005,
    US2-10, US2-11).
- **`tests/unit/test_question_schemas.py`**, rewritten:
  - trim, CRLF and CR normalisation, NUL, empty, only spaces, exactly 2,000 and 2,001 characters
    (code points, Cyrillic, a line break), duplicates allowed.
- **`tests/integration/test_question_service.py`**, rewritten:
  - create, update, soft delete;
  - numbering, never reused;
  - order and paging;
  - a deleted question stored unchanged (SC-003);
  - every "not found" and "setting required" refusal, with nothing changed;
  - the deletion landing in each position (US4-4 to US4-7);
  - `count_subject_uses` with deleted questions (SC-004).
- **`tests/integration/test_teacher_questions.py`**, new: the tab end to end, through the test
  client.
  - **Roles**: administrator and student get 403 on all 7 endpoints. A teacher without the setting
    gets 403 on the 5 management endpoints, with an unknown or deleted id too (access before
    existence). A teacher with the setting is allowed (SC-002).
  - **The list**: the subject list and both empty states, automatic selection, an unknown or
    deactivated subject in the address. Paging addresses: missing, invalid, too high. Order,
    content, numbers, page navigation text. Actions shown only with the setting.
  - **Add**: both buttons, the notice, Cancel's target, field errors with values kept (empty, spaces,
    too long), trimming, duplicates.
  - **Edit**: values filled in, subject ignored, return page and anchor, Cancel.
  - **Delete**: confirmation text, Cancel's anchor, each landing, then "not found" for the deleted
    question.
  - **Not found** cases on every page and action.
  - **Concurrency**: the setting is removed, or the subject deactivated, between the form and the
    save.
  - **Reloads**: reloading after a redirect repeats nothing (SC-009).
  - **The tab row**: three tabs in order, `/teacher` still opens **Students**.
- **Updated**:
  - **`test_routes.py`**: the exact write list gains the 3 POST routes. The declared-page sweep
    skips the allowed-teacher check for the management pages, which need the setting. The cast
    teacher has no profile, so they get 403 there, as `TEACHER_SCOPED_PATHS` already does for
    milestone 9 and with the same guard test. `test_teacher_access.py`, or the new module, sweeps
    them with a real teacher who has the setting.
  - **`form_contract.json`**: the new forms and the renamed checkbox.
  - **The gallery and the guidelines**: `test_component_gallery.py` and `test_page_patterns.py` cover
    the new sections, confirmations and back links. `test_stylesheet.py` covers the new classes.
  - **`test_migrations.py`**:
    - empty `questions` at head;
    - an upgrade from `596ead9f1205` deletes the samples and keeps each teacher's setting value
      (US6-1, SC-006, SC-007);
    - drift and stairway checks.
  - **`test_admin_subjects.py`**: a subject whose only questions are deleted cannot be deleted
    (US7-1). Activating a subject again lists its questions (US7-3).
  - **`test_home.py`**: no questions, the database line, the teacher card text (US8).
  - **`test_health.py`** keeps its unavailable-message case.
  - **The setting**: every test that names the old setting (teachers, invitation, refusals, profile,
    email, sealing) is renamed. The sealing and invitation tests add a case for a legacy payload
    (US6-3). A guard test greps templates and app code for "Can create competitions" (SC-006).

**Rationale**: it follows the module split milestone 9 used (service, HTTP, sweeps). The spec's
FR-048 list maps one to one onto these cases.

---

## R16. The subject in-use rule

**Decision**: `count_subject_uses` returns `SELECT count(*) FROM questions WHERE subject_id = :id`,
counting deleted questions too (FR-040).

- **The refusal is unchanged**: `delete_subject` keeps its refusal (`SubjectInUse` and the 409 page:
  "“Chemistry” is in use and cannot be deleted. You can deactivate it instead.").
- **The foreign key is a backstop**: it has no `ON DELETE` action, so PostgreSQL refuses an orphan
  even under a race (R7). On SQLite, foreign keys are not enforced in this application, which is why
  the count is the rule.
- **Deactivating and activating a subject** do not touch its questions: the bank simply stops
  listing a deactivated subject, and lists it again when the subject is active (FR-041).

**Alternative considered**: counting only questions that are not deleted. FR-040 forbids it.
