# Quickstart: Validate the Educational Institutions Tab (Milestone 7)

**Feature**: [spec.md](./spec.md) | **Routes**: [contracts/http-routes.md](./contracts/http-routes.md) |
**Service**: [contracts/institution-service.md](./contracts/institution-service.md)

This guide proves the milestone works, first with the automated suite and then by hand in a
browser.

## Prerequisites

- The repository set up as in the README ("Getting started"): `uv sync`.
- Optional, to run the PostgreSQL half of the suite: a local PostgreSQL server and
  `TEST_POSTGRES_URL` (README, "Test").

## 1. Automated checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Expected: all green. Every database test runs on SQLite, and on PostgreSQL when
`TEST_POSTGRES_URL` is set. The tests that cover this milestone:

| Test module | Proves |
|---|---|
| `tests/unit/test_name_rules.py` | Subjects and institutions use the same shared name rules and limits |
| `tests/unit/test_subject_schemas.py` (unchanged) | The shared rules themselves: Cyrillic, "ß", NFC/NFD, 200/201 characters, control characters |
| `tests/integration/test_institution_service.py` | Create, rename, activate, deactivate, delete; no-op writes; rename keeps `id` and status; the unique constraint and a simulated race; an institution in use is refused |
| `tests/integration/test_admin_institutions.py` | US1, US2 end to end over HTTP: the list and empty state, forms, `400` and `409` re-renders with the entered value kept, `404` "Educational institution not found", Post/Redirect/Get, reload safety |
| `tests/integration/test_admin_area.py` | Teachers is still a placeholder; every institution page marks the **Educational institutions** tab |
| `tests/integration/test_routes.py` | Every new route declares `Role.ADMIN`; the write-route list includes the five institution `POST`s (US3) |
| `tests/integration/test_access_control.py` | Teacher, student and administrator-using-teacher get `403` on every institution page and action, and nothing changes (US3) |
| `tests/integration/test_cross_site.py` | A cross-site `POST` to an institution action is refused and nothing changes |
| `tests/integration/test_migrations.py` | Empty → head, stairway, drift: the `institutions` table exists |

## 2. Manual walk-through

Start the application locally with one person per role, plus one person who is both an
administrator and a teacher (README, "Signing in locally as each role"):

```bash
uv run alembic upgrade head
ADMIN_EMAILS=admin@example.com,both@example.com \
TEACHER_EMAILS=teacher@example.com,both@example.com \
STUDENT_EMAILS=student@example.com \
uv run uvicorn app.main:app --reload
```

Sign-in codes are printed to the terminal.

### Institutions list (US1)

1. Sign in as `admin@example.com`, open **Administrator area**, then the **Educational
   institutions** tab. → "No educational institutions yet" and **Create**. The tab is highlighted.
2. Create "Kyiv Polytechnic Institute", "Lviv Politechnic" and "alpha College". → The list shows
   alpha College, Kyiv Polytechnic Institute, Lviv Politechnic, all Active.
3. Create "  KYIV POLYTECHNIC INSTITUTE  ". → The form returns with "An educational institution
   named “Kyiv Polytechnic Institute” already exists." and your input.
4. Create an empty name, then a name of 201 characters. → Each one is refused with its message and
   your input kept.
5. Create "Київський університет", then "КИЇВСЬКИЙ УНІВЕРСИТЕТ". → The second is refused as a
   duplicate.
6. On the **Subjects** tab, create "Physics". Back on **Educational institutions**, create
   "Physics". → Allowed: the two lists are independent.

### Rename, deactivate, delete (US2)

1. Rename "Lviv Politechnic" to "Lviv Polytechnic". Rename "alpha College" to "Alpha College"
   (case only). → Both succeed.
2. Rename "Alpha College" to "lviv polytechnic". → Refused as a duplicate. "Alpha College" is
   unchanged.
3. Deactivate "Alpha College". → It shows Inactive, with an **Activate** button. Rename it while
   inactive. → It stays Inactive. Activate it again.
4. Create "Test School". Click **Delete**. → A confirmation page names it. Click **Cancel**:
   nothing changed. Click **Delete** again and confirm. → "Test School" is gone.
5. After any action, reload the list. → The action is not repeated.
6. Open `/admin/institutions/999/rename`. → "Educational institution not found", with a link back
   to the list.

### Access (US3)

1. Sign in as `teacher@example.com`, then as `student@example.com`. Open `/admin/institutions` and
   `/admin/institutions/new`. → "Access denied" each time.
2. Sign in as `both@example.com` and choose **Teacher**. Open `/admin/institutions`. → "Access
   denied". Switch to **Administrator** from the header. → The page opens.
3. Sign out, then open `/admin/institutions`. → You are sent to sign in. After signing in as
   `admin@example.com`, you land on `/admin/institutions`.

## 3. After deployment

On the production URL, sign in as an administrator from `ADMIN_EMAILS` and repeat steps 1–2 of
"Institutions list" and step 4 of "Rename, deactivate, delete". Production starts with an empty
institution list. The migration runs from the container entrypoint, so nothing needs to be run by
hand.
