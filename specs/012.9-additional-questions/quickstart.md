# Quickstart: Additional Questions in the Question Bank (Milestone 12.9)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **Addresses, fields, refusals**: [contracts/http-routes.md](./contracts/http-routes.md).
- **Services**: [contracts/services.md](./contracts/services.md).
- **Badge, text card, checkbox**: [contracts/components.md](./contracts/components.md).
- **Column, views, migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`. No new dependency.
- For the PostgreSQL cases: the local container `sc-pg` running and `TEST_POSTGRES_URL` set (see
  the README).
- A local `.env` with the cast emails and the `memory` email sender, as in the earlier milestones.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/integration/test_question_service.py tests/integration/test_teacher_questions.py
uv run pytest tests/integration/test_competition_entries_service.py \
              tests/integration/test_teacher_competition_entries.py \
              tests/integration/test_teacher_team_answers.py tests/integration/test_teacher_grades.py
uv run pytest tests/integration/test_migrations.py tests/integration/test_form_contract.py \
              tests/integration/test_component_gallery.py tests/integration/test_routes.py \
              tests/unit/test_templates.py tests/unit/test_catalogues.py
TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest   # the whole suite
```

**Expected**: everything green on SQLite and on PostgreSQL. The mapping from scenarios to tests is
in [research.md](./research.md) R9.

## 2. Upgrade a database from milestone 12.8

```bash
cp data/student_competitions.sqlite3 <scratchpad>/before-m12-9.sqlite3   # at revision c730fd883079
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head
```

**Check**:

- `questions` has `is_additional` (not null, default false);
- `SELECT count(*) FROM questions WHERE is_additional` is 0, deleted questions included;
- on SQLite, `SELECT sql FROM sqlite_master WHERE name = 'questions'` still holds `AUTOINCREMENT`
  after the downgrade and the upgrade again.

## 3. Walk through it by hand

Run the app (`uv run fastapi dev app/main.py`) with a database holding:

- **Chemistry**, with 23 listed questions (3 to be marked additional) and one deleted question;
- **Astronomy**, with 2 questions (both to be marked additional);
- an **Upcoming** competition "Spring round" of Chemistry;
- **Olena**, with **Can manage competitions**;
- **Petro**, without the setting, with **Write** access;
- **Taras**, without the setting, with **Read** access.

1. **Marking** (US1), as Olena:
   - **Add question** shows the checkbox **Additional question**, unchecked, with its hint, under
     the reference answer.
   - Check it and use **Save and add one more question**: the next form is unchecked.
   - **Save question** lands on page 1, where the marked question's heading reads "Question N
     **Additional**".
   - **Edit** it: the box is checked. Clear it and save: no badge.
   - Send the form with an empty question and the box checked: the error, and the box still
     checked.
2. **The bank without the setting** (US2), as Petro and as Taras:
   - Chemistry shows "Questions 1–10 of 20" and two pages; nowhere a badge or a hint of the other
     three.
   - Astronomy shows "No questions yet" with no hint.
   - View the page source: no additional question's text or number.
   - `?page=9` opens page 2.
3. **Crafted requests** (US3), as Petro: type `/teacher/questions/<additional id>/edit`, then an
   ordinary id, then `999999`. Every time the same "access denied" page. The same for
   `/teacher/competitions/<id>/questions/add`.
4. **A mix for a competition** (US4):
   - As Olena, **Questions** → **Add question** on "Spring round": the additional questions carry
     the badge. Add two of them and four others.
   - Back on the competition's **Questions** page: the two show the badge beside their bank numbers.
   - As Petro, the same page shows six questions and no badge (the accepted gap: Petro can still
     read them until milestone 12.10).
   - As Olena, delete one of the two in the bank: the competition page shows the badge **and**
     "Deleted from the question bank".
   - Clear the other's mark in the bank: its badge disappears, and the copy's text is unchanged.
5. **Later statuses** (US4): with the start moved into the past (or the 12.1 test clock), the page
   still shows the badges to Olena while **In progress**; after **Finish competition**, the
   **Answers** and **Grades** sheets show no badge.
6. **The setting** (US5): as an administrator, give Petro **Can manage competitions**. Petro's next
   page lists 23 questions with the badges. Take it away: back to 20.
7. **Languages**: switch to Ukrainian. The checkbox reads «Додаткове питання» with its hint, and
   the badge reads «Додаткове».
8. **Phone width** (360 px): the question form, the list, **Add questions** and the competition's
   **Questions** page have no sideways scroll, and a badge that does not fit wraps under the
   heading. For screenshots, use the headless Playwright recipe of the earlier milestones (ad hoc,
   not a project dependency).

## 4. The gallery

`/admin/components` shows:

- in **Badges**, the row "Marks" with **Additional**;
- in **Cards** → "Text cards", "Question 58" with the badge in its heading.

Check both in light and dark, at 360 px and desktop width.

## 5. Documents in the pull request

- The README's **Questions** paragraph says who sees additional questions.
- `docs/requirements/ui-guidelines.md` matches what was built (`additional_badge()`, `text_card`'s
  `badge`).
- On delivery: the 12.9 summary in `milestones.md`, and the milestone 11 summary without "the shared
  question bank".
