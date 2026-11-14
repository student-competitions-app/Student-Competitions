# Quickstart: Finishing a Competition and Grading Its Answers by Hand (Teacher) (Milestone 12.4)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **The addresses, the page contents and the wording**:
  [contracts/http-routes.md](./contracts/http-routes.md).
- **The services**: [contracts/services.md](./contracts/services.md).
- **The three new patterns and the guideline changes**: [contracts/components.md](./contracts/components.md).
- **The column and the migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`.
- For the PostgreSQL cases, the local container (`sc-pg`) running and `TEST_POSTGRES_URL` set (see
  the README). The concurrency tests of research R1 and R3 run only on PostgreSQL.
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–12.3.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_grade_schemas.py
uv run pytest tests/integration/test_grade_service.py tests/integration/test_teacher_grades.py
uv run pytest tests/integration/test_teacher_competitions.py \
              tests/integration/test_teacher_team_answers.py \
              tests/integration/test_team_answer_service.py \
              tests/integration/test_competition_service.py tests/integration/test_migrations.py \
              tests/integration/test_routes.py tests/integration/test_form_contract.py \
              tests/integration/test_component_gallery.py tests/integration/test_page_patterns.py
uv run pytest                                   # the whole suite (SC-011)
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from spec scenarios and the milestone's _Test:_ items to tests is in
[research.md](./research.md) R15.

## 2. Upgrade a database from milestone 12.3

```bash
cp data/student_competitions.sqlite3 /tmp/before-m12-4.sqlite3   # a database at revision b709653d1111
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head
```

**Check**: `team_answers` has a nullable `grade` column with the `ck_team_answers_grade_range`
constraint; every existing answer is ungraded; no other table changed.

## 3. Walk through it by hand

Run the app (`uv run fastapi dev app/main.py`) with a database holding: a subject with an **In
progress** competition "Spring round" of 4 questions (start in the past) whose teams of three
institutions in two regions have answers, one team with none, one deleted team; an upcoming
competition; Taras with **Write** to one institution and **Read** to another, without **Can manage
competitions**; Olena with the setting and no links.

1. **Menu** (US9): as Olena, "Spring round" → **Questions**, **Teams**, **Answers**, **Finish
   competition** (not red), **Cancel competition**; as Taras, **Questions**, **Teams**, **Answers**.
2. **Read access while in progress** (US7): as Taras, **Answers** → his Write teams have **Enter
   answers**, his Read team **View answers**; the read-only sheet shows the notice, the answers,
   "Not answered", no reference answer, no grades, no field.
3. **Finish** (US1): as Olena, **Finish competition** → the question, the consequence, the blue
   **Finish competition** and **Keep in progress**. Confirm under the filter **In progress**: the row
   leaves the list, the notice shows. Switch to **All**: "Spring round" shows **Finished**; its menu
   has **Grades** and no **Finish** or **Cancel**.
4. **Finish refusal** (US2): type `/teacher/competitions/<upcoming id>/finish?subject=<id>` → "has
   not started yet and cannot be finished."
5. **Grades page** (US3, US6): **Grades** → "Graded 1 of N teams" (the team with no answers), every
   team incl. the deleted one marked "(deleted)", the three columns; **Ungraded only** lists only
   teams with answers and is marked current.
6. **Grading** (US4, US5): **Grade answers** → reference answers, the grade fields with "Not graded";
   type "7.5" and "11" → nothing saved, both errors, the summary, the values kept; type 7, 10, 0 →
   saved with the notice; the back link under **Ungraded only** lands without the team once it is
   fully graded.
7. **After finishing** (US8): as Taras, **Answers** → his teams with **Graded** and **Score**, all
   with **View answers**; the sheet shows "Score: …", "Graded … of … answers", "Grade: 7 of 10" and
   "Not graded yet"; no team of an unlinked institution.
8. **Access** (US11): as Taras, type the Grades address → "access denied".
9. **Deactivated subject** (US13): as an administrator, deactivate the subject; "Spring round" still
   lists with **Answers** and **Grades**, and grading still saves.
10. **Gallery** (US14): `/admin/components` → the non-destructive confirmation, the grading sheet
    (error, unanswered, narrow), the read-only variant with and without grades, the filter links.

## 4. Browser checks

At 360 px wide (the device toolbar, or the headless Playwright routine of the project memory): the
Grades table becomes cards with "Answered", "Graded" and "Score" lines; the grading sheet has no
sideways scroll with long texts; the grade field opens the digit keypad on a phone; the filter
links' current link looks like the current page in both themes; **Save grades** and **Finish
competition** show the busy state (milestone 10.1); everything works with JavaScript off.

## 5. Reload and repeat

Reload after a finish and after a grade save: nothing is sent again (303 and a GET). Send the finish
form twice (two tabs): the second shows "has already finished."
