# Quickstart: Questions and Teams of a Competition (Teacher) (Milestone 12.2)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **The addresses, the page contents and the wording**:
  [contracts/http-routes.md](./contracts/http-routes.md).
- **The services**: [contracts/services.md](./contracts/services.md).
- **The region group and the guideline changes**: [contracts/components.md](./contracts/components.md).
- **The tables and the migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`.
- For the PostgreSQL cases, the local container (`sc-pg`) running and `TEST_POSTGRES_URL` set (see
  the README). The concurrency tests of research R5 run only on PostgreSQL.
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–12.1.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_paging.py
uv run pytest tests/integration/test_competition_entries_service.py \
              tests/integration/test_teacher_competition_entries.py
uv run pytest tests/integration/test_teacher_competitions.py tests/integration/test_teacher_teams.py \
              tests/integration/test_team_service.py tests/integration/test_competition_service.py \
              tests/integration/test_migrations.py tests/integration/test_routes.py \
              tests/integration/test_form_contract.py tests/integration/test_component_gallery.py \
              tests/integration/test_page_patterns.py
uv run pytest                                   # the whole suite (SC-009)
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from spec scenarios to tests is in [research.md](./research.md) R16.

## 2. Upgrade a database from milestone 12.1

```bash
cp data/app.db /tmp/before-m12-2.db        # or any database at revision 72e46cb10175
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head
```

**Check**: `competition_questions` and `competition_teams` exist and are empty, with the unique
constraint, the primary key and the `team_id` index; no other table changed.

## 3. Walk through it by hand

Run the app (`uv run fastapi dev app/main.py`) with a database holding two subjects, three regions
with institutions and teams (one with no members, one deleted, one in a deactivated institution),
a teacher with **Can manage competitions** (Olena) and one without (Mykola), and an upcoming
competition "Spring round".

1. **Menu** (US6): as Olena, **Competitions** → "Spring round" → **Actions** lists **Edit**,
   **Questions**, **Teams**, **Cancel competition**. As Mykola, every row has a menu with only
   **Questions** and **Teams**.
2. **Questions** (US1, US3, US5): **Questions** → "No questions in this competition yet" with the
   hint → **Add question** → **Add** on three questions: each stays on the page with "Already in this
   competition" and the notice. Back: the order of adding. Edit one in the **Questions** tab: the
   competition still shows the old text. **Remove** it, **Cancel**, then **Remove** for real: the
   notice, the landing, the question still in the bank. Add it again: at the end, new text.
3. **Teams** (US2, US4): **Add team** → "Select a region" → choose a region: its teams, sorted,
   none deleted and none of a deactivated institution, including teams of institutions Olena is not
   linked to; the address holds `region` and `p`. **Add** two, including the one with no members.
   Back: region boxes with "<Region> · <n> teams"; with more than 10 teams, a region spanning the
   page break shows its header again with the same total.
4. **Status** (US7): open "Add questions", let the start pass (or edit the start in the database),
   press **Add**: the refusal "Change the questions of “Spring round”?" with **Back to the
   competition**. The lists show no **Add** or **Remove** any more.
5. **Deleting a team** (US8): as a teacher with Write access to its institution, **Teams** tab →
   delete a team that is in an upcoming, a cancelled and a finished competition (set `stopped_at`
   directly). The confirmation says it is taken out of every competition that has not finished;
   afterwards only the finished one lists it, marked "(deleted)".
6. **Access** (US9): as Mykola, type an "Add questions" address: "access denied". As an
   administrator or a student, type a competition's questions address: "access denied".
7. **Deactivated subject** (US10): deactivate the subject: the upcoming competition's pages show
   "not found"; a finished one shows both lists read-only.

## 4. Browser checks

With the browser's script disabled, the **Region** list on "Add teams" shows **Show** and works. At
360 px width, the region boxes hold labelled cards, long names wrap, and nothing scrolls sideways
(SC-007). An ad hoc Playwright run, as in milestone 10.1, may take screenshots of both lists in the
light and dark themes.

## 5. Reload and repeat

After any add or remove, reload the result page: nothing changes again (SC-008). Send the same
**Add** form twice (copy it with the browser's developer tools): one copy, and the "is already in"
notice.
