# Quickstart: Question Bank (Teacher) (Milestone 11)

How to check, end to end, that the milestone works. What should happen is defined in
[spec.md](./spec.md), the addresses and page contents in
[contracts/http-routes.md](./contracts/http-routes.md), and the components in
[contracts/components.md](./contracts/components.md). This guide only says how to run and what to
look for.

## 0. Prerequisites

- `uv sync`.
- For the PostgreSQL cases, the local container (`sc-pg`) running, and `TEST_POSTGRES_URL` set (see
  the README).
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–9.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_paging.py tests/unit/test_question_schemas.py
uv run pytest tests/integration/test_question_service.py tests/integration/test_teacher_questions.py
uv run pytest tests/integration/test_migrations.py tests/integration/test_admin_subjects.py \
              tests/integration/test_home.py tests/integration/test_routes.py
uv run pytest                                   # the whole suite (SC-010)
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from spec scenarios to tests is in [research.md](./research.md) R15.

## 2. Upgrade a database that holds the sample questions

```bash
cp data/app.db /tmp/before-m11.db          # or any database at revision 596ead9f1205
uv run alembic upgrade head
```

**Check**:

- **The sample questions are gone**: `SELECT count(*) FROM questions` is `0` (SC-007).
- **Each teacher keeps their value** under the new name: `SELECT user_id, can_manage_competitions
  FROM teacher_profiles` gives the values `can_create_competitions` had before (SC-006).
- **The home page** shows no questions and still has the database line in the footer (US8-2).
- **The teacher card** says "… and see the question bank." (US8-4).

## 3. Run the application and walk through the tab

```bash
uv run uvicorn app.main:app --reload
```

**As an administrator**:

- create the subjects "Mathematics", "Physics" and "Chemistry";
- invite a teacher **with** **Can manage competitions**, and one without;
- accept both invitations from the emails in the log;
- check that the **Teachers** tab, the forms, the acceptance page and the profile say **Can manage
  competitions** (US6-2).

**As the teacher with the setting** (US1, US3, US4):

1. Open `/teacher`: the tabs read **Students · Questions · Competitions**, and **Students** opens.
2. **Questions**: "Select a subject". Choose "Physics": the address becomes `?subject=<id>`, and the
   page says "No questions yet".
3. **Add question**: the form shows "Subject: Physics". Save with both fields empty: two field
   errors, in the summary too. Fill in and press **Save and add one more question**: an empty form
   with "The question was saved.". Fill in again and press **Save question**: page 1, with the
   newest question first.
4. **Paging**: add questions until there are more than 20 (a short loop through the service in a
   Python shell is fine). Check "Questions 1–10 of N", **Previous** and **Next**, the gaps, and
   `&page=0`, `&page=abc` and `&page=999`.
5. **Edit** a question on page 2: the form is filled in. Save: page 2, scrolled to that question,
   below the pinned tabs. Cancel does the same.
6. **Delete** a question in the middle of page 2: "Delete question <n>?" with the exact consequence
   text. Confirm: still page 2, at the question that took its place. Then delete:
   - the last question of the whole list, which lands on the previous question;
   - the only question on the last page, which lands on the previous page, at its last question.
7. Reload after any save or delete: nothing happens twice (SC-009).

**As the teacher without the setting** (US2, US5):

- the same list, with no **Add question**, **Edit** or **Delete**;
- typing `/teacher/questions/new?subject=<id>` or `/teacher/questions/<id>/edit` gives **403**.

**As the administrator again** (US5-4, US7):

- deactivate "Physics": the teacher's bookmark `?subject=<physics>` behaves as no selection, and
  `/teacher/questions/<physics question>/edit` gives **404**;
- try to delete "Physics" (or a subject whose questions were all deleted): refused, with
  "deactivate instead";
- activate it again: its questions are back, unchanged.

**As an administrator or a student**: `/teacher/questions` gives **403**.

## 4. Without JavaScript

Turn JavaScript off in the browser's developer tools and repeat step 3.2–3.4:

- each subject list shows a **Show** button that opens the subject;
- the page navigation and both save buttons work (US2-14).

The Students tab's lists show **Show** too.

## 5. Phone width and themes

At 360 px and 375 px width (device emulation), in Light and Dark:

- **The list**, the forms, the confirmation and the page navigation: no sideways scroll, and the
  page navigation wraps (SC-008).
- **A question** with a 300-character word and many line breaks wraps inside its boxes.

## 6. The three-tab row against the clearances (FR-011)

Measure the frame's height on `/teacher/questions` at 360 × 640 and 375 × 667, with the **Questions**
and the **Competitions** tab current: the frame's `getBoundingClientRect().bottom`, the tab row's
row count, and whether the row wraps. Use DevTools, or the ad hoc Playwright recipe (`uv run --with
playwright`, a copy of the database, port 8765; see the project's screenshot notes).

**Expected** (research R14):

- one row: the frame is about 114 px, under `--sc-frame-clearance-tabs` (176 px below 768 px);
- if it wraps, two rows, still under 176 px and under a quarter of the screen height.

Record the numbers in `pr-notes.md`. Then follow an `#question-<id>` link and a field error link,
and check that the target sits below the frame.

## 7. The component gallery

Open `/admin/components` outside production:

- `#pagination` shows the three variants;
- `#forms` shows the textarea variants and the two-button actions;
- `#cards` shows the text card with a long word;
- `#selectors` is unchanged, and shows **Show** with JavaScript off.

Check that each is described in `docs/requirements/ui-guidelines.md`.
