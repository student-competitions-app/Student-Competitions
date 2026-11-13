# Quickstart: Entering a Team's Answers (Teacher) (Milestone 12.3)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **The addresses, the page contents and the wording**:
  [contracts/http-routes.md](./contracts/http-routes.md).
- **The services**: [contracts/services.md](./contracts/services.md).
- **The answer sheet and the placeholder**: [contracts/components.md](./contracts/components.md).
- **The table and the migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`.
- For the PostgreSQL cases, the local container (`sc-pg`) running and `TEST_POSTGRES_URL` set (see
  the README). The concurrency tests of research R3, R4 and R7 run only on PostgreSQL.
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–12.2.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_answer_schemas.py
uv run pytest tests/integration/test_team_answer_service.py \
              tests/integration/test_teacher_team_answers.py
uv run pytest tests/integration/test_teacher_competitions.py \
              tests/integration/test_teacher_competition_entries.py \
              tests/integration/test_team_service.py tests/integration/test_teacher_teams.py \
              tests/integration/test_competition_service.py tests/integration/test_migrations.py \
              tests/integration/test_routes.py tests/integration/test_form_contract.py \
              tests/integration/test_component_gallery.py tests/integration/test_page_patterns.py
uv run pytest                                   # the whole suite (SC-011)
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from spec scenarios to tests is in [research.md](./research.md) R17.

## 2. Upgrade a database from milestone 12.2

```bash
cp data/student_competitions.sqlite3 /tmp/before-m12-3.sqlite3   # a database at revision 59c636929942
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head
```

**Check**: `team_answers` exists and is empty, with its primary key, the two foreign keys, the
check constraint and the `competition_question_id` index; no other table changed.

## 3. Walk through it by hand

Run the app (`uv run fastapi dev app/main.py`) with a database holding: a subject with an **In
progress** competition "Spring round" of 6 questions (set the start in the past) and an upcoming
one; teams of three institutions in two regions in "Spring round"; a teacher Taras with **Write**
to one institution and **Read** to another, without **Can manage competitions**; Olena with the
setting; a teacher linked only to a deactivated institution.

1. **Menu** (US4): as Taras, "Spring round" → **Actions** lists **Questions**, **Teams**, **Answers**;
   the upcoming one has no **Answers**. As Olena, **Questions**, **Teams**, **Answers**, **Cancel
   competition**.
2. **Teams page** (US5): **Teams** lists every team of every institution, no **Enter answers**.
3. **Team answers page** (US2, US3): **Answers** → only Taras's institutions' teams, in region
   boxes, each "0 of 6"; **Enter answers** on the **Write** institution's teams, "Read access" on the
   other's; no **Add team** or **Remove**.
4. **Answer sheet** (US1): **Enter answers** → six numbered questions, "Not answered" in each field,
   no reference answer. Answer three, **Save answers**: the notice, the answers in their fields.
   Back: "3 of 6". Empty one, save: "2 of 6".
5. **Too long** (US6): paste 2,001 characters into one answer and change another, save: nothing
   saved, every text kept, the error at the field and in the summary.
6. **Status** (US7): open a sheet, cancel the competition as Olena in another window, save: "Enter
   answers for “Spring round”?" with the reason and **Back to competitions**. Type the address of the
   upcoming competition's answers page: the "has not started yet" refusal.
7. **Access** (US8): as Taras, type the sheet address of a team of his **Read** institution, and of
   an institution he is not linked to: "access denied".
   As an administrator or a student, type the answers page address: "access denied". Lower Taras to
   **Read** while his sheet is open, save: "access denied", the answers saved before stay.
8. **Two teachers** (US10): open the same sheet in two windows, save different answers, empty one in
   the second: the second save's answers are the team's.
9. **Deleting a team** (US11): delete a team with answers on the **Teams** tab; open a sheet of it
   saved before: "Team not found".
10. **Empty states** (US9): as the teacher of the deactivated institution, "You are not linked to any
    educational institution"; a competition with no questions shows "No questions in this
    competition" on the sheet and "0 of 0".

## 4. Browser checks

At 360 px width the team answers page shows labelled cards with "Answered 3 of 6", and the sheet
stays one column with full-width fields; long names and long answers wrap; nothing scrolls sideways
(SC-009). **Save answers** turns busy while the next page loads (milestone 10.1). The placeholder
reads "Not answered" in the light and dark themes, under the field's label and hint. An ad hoc
Playwright run, as in milestone 10.1, may take the screenshots.

## 5. Reload and repeat

After a save, reload the sheet: nothing is sent again (SC-010). Send the same save twice (copy it
with the browser's developer tools): the answers are stored once, and the notice shows again.
