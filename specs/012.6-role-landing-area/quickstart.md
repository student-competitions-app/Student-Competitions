# Quickstart: Validate Milestone 12.6

Run from the repository root. Routes and expected answers: [contracts/http-routes.md](./contracts/http-routes.md).

## 1. Automated checks

```bash
scripts/translations.sh compile
uv run pytest                                   # SQLite
TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest   # both engines
uv run ruff check . && uv run ruff format --check .
scripts/translations.sh check                   # catalogues: nothing unused, nothing untranslated
```

Expected: everything passes, and no test is skipped because of this milestone.

## 2. Leftover search

```bash
grep -rniE "/staff|staff area|Розділ працівників" app tests README.md docs
```

Expected hits, and only these: the `/staff` 404 test, and milestone 12.6's own text in
`docs/requirements/milestones.md`.

```bash
grep -rniE "home page" app README.md docs/requirements/ui-guidelines.md
```

Each remaining hit is about the student's home page, the "Back to the home page" / "Go to the home
page" links, or the signed-out redirect. None says administrators or teachers see the home page.

## 3. By hand

```bash
uv run alembic upgrade head
ADMIN_EMAILS=admin@example.com uv run uvicorn app.main:app --reload
```

The sign-in code is printed in the console. Invite a teacher and a student as in the README if they
don't exist yet.

| Step | Expected |
|---|---|
| Sign in as `admin@example.com` | You land on **Teachers** of the administrator area, with no home page in between |
| Look at the footer | "Database: SQLite · schema revision … · boot #…" |
| Open **Educational institutions**, **Subjects**, `/admin/components` | the same line on each |
| Click the brand (logo) | back on **Teachers** |
| Open `/profile` | "Back to the administrator area" → `/admin` |
| Open `/student` | **Access denied**, with "Back to the administrator area" |
| Open `/staff` | **Page not found**, with "Back to the home page", which leads to **Teachers** |
| Switch the language to Ukrainian | «Назад до розділу адміністратора» on the profile; «Розділ працівників» nowhere |
| Sign in as a teacher | You land on **Students** of the teacher area. No database line in the footer |
| As a teacher with several roles, switch role from the user menu | You land in the new role's area (or the student's home page) |
| Sign in as a student | The home page with one **Student area** card and the database line, as before |

## 4. Pipeline

Push the branch. The `image` job of `checks.yml` must pass with its new landing check
([contracts/pipeline.md](./contracts/pipeline.md)).
