# Quickstart: Publishing a Competition's Results as PDF Files (Milestone 12.8)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **Addresses, refusals, headers**: [contracts/http-routes.md](./contracts/http-routes.md).
- **Services**: [contracts/services.md](./contracts/services.md).
- **What a file holds**: [contracts/results-file.md](./contracts/results-file.md).
- **Badge, download entry, blocked confirmation, read-only sheet**:
  [contracts/components.md](./contracts/components.md).
- **Column, table, migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`, which now installs `fpdf2` (runtime) and `pypdf` (development).
- The fonts `app/static/fonts/OpenSans-Regular.ttf` and `OpenSans-Bold.ttf` are committed.
- For the PostgreSQL cases, the local container (`sc-pg`) running and `TEST_POSTGRES_URL` set (see
  the README). The race tests of research R5 run only on PostgreSQL.
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–12.4.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_results_pdf.py
uv run pytest tests/integration/test_results_service.py tests/integration/test_teacher_results.py
uv run pytest tests/integration/test_teacher_competitions.py tests/integration/test_teacher_grades.py \
              tests/integration/test_teacher_team_answers.py tests/integration/test_grade_service.py \
              tests/integration/test_competition_service.py tests/integration/test_migrations.py \
              tests/integration/test_routes.py tests/integration/test_form_contract.py \
              tests/integration/test_component_gallery.py tests/integration/test_page_patterns.py
uv run pytest                                   # the whole suite
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from scenarios to tests is in [research.md](./research.md) R14.

## 2. Upgrade a database from milestone 12.7

```bash
cp data/student_competitions.sqlite3 /tmp/before-m12-8.sqlite3   # at revision 7110bec350d2
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head
```

**Check**:

- `competitions` has a nullable `published_at` and the `published_after_finish` constraint;
- `competition_results_files` exists and is empty;
- every finished competition is still **Finished**.

## 3. Make the sample files (design review)

```bash
uv run python scripts/make_results_samples.py
open specs/012.8-publishing-results/samples/
```

**Check** six files, three sets × two languages (research R12):

- the logo and the header;
- the regions and the order;
- long names wrapping, never cut;
- Cyrillic text;
- "Page n of N" on every page of the long set;
- "No teams took part in this competition." in the empty set.

Record the round in `design-approval.md`.

## 4. Walk through it by hand

Run the app (`uv run fastapi dev app/main.py`) with a database holding:

- a subject "Chemistry" with a **Finished** competition "Spring round":
  - teams of three institutions in two regions, one of them deleted;
  - every answer graded except one;
- a **Finished** competition "Winter round" with no teams;
- Olena, with **Can manage competitions** and no links;
- Taras, without the setting, linked with **Read** to an institution with no team in "Spring
  round".

1. **Menu** (US1, US7):
   - as Olena, "Spring round" lists **Questions**, **Teams**, **Answers**, **Grades** and
     **Publish results** (not red);
   - as Taras, **Questions**, **Teams**, **Answers**, with no **Publish results** and no
     **Download results**.
2. **Blocked** (US2): **Publish results** shows "Graded N−1 of N teams", the explanation, **Grade
   the remaining teams** and **Keep unpublished**, and no button. **Grade the remaining teams**
   opens **Grades** under **Ungraded only**. Grade the last answer and go back.
3. **Publish** (US1): the button **Publish results** brings the list back at "Spring round", now
   **Published**, with the notice. Its menu now lists **Download results** and no **Publish
   results**.
4. **Frozen** (US5): **Grades** → **Grade answers** shows the note, grades as text and no **Save
   grades**. A save sent from a sheet opened in another tab before publishing gets the note and
   changes nothing.
5. **Filter** (US4): **Published** lists "Spring round"; **Finished** lists only "Winter round".
6. **Download** (US7): as Taras, **Download results** saves "Spring round <date>.pdf" at once, the
   loading bar never shows, and the file is Ukrainian. Switch to English and download again: the
   file is English. Open both, read the header and the lines (the deleted team is listed), and
   compare with the sample design.
7. **Refusals** (US3): the typed `…/publish` addresses of an upcoming, an in-progress, a cancelled
   and the published competition show each reason. `…/results` of a finished one answers
   "Competition not found".
8. **No teams** (US2): publish "Winter round" ("Graded 0 of 0 teams"). Its file says "No teams took
   part in this competition.".
9. **Later changes** (US6): rename the institution and delete a team, then download again: the
   bytes are the same as before.
10. **Phone width** (360 px): the confirmation, the blocked state, the refusals and the read-only
   sheet have no sideways scroll. For screenshots, use the headless Playwright recipe of the
   earlier milestones.

## 5. The gallery

`/admin/components` shows:

- the five status badges, **Published** included;
- the actions menu with **Download results** (a link with `download`);
- the publish confirmation, ready and blocked;
- the read-only grading sheet with the published note.

Check both themes.
