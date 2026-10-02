# Quickstart: Validate the Administrator Area (Milestone 6)

**Feature**: [spec.md](./spec.md) | **Routes**: [contracts/http-routes.md](./contracts/http-routes.md) |
**Service**: [contracts/subject-service.md](./contracts/subject-service.md)

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

Expected: all green. The suite runs every database test on SQLite, and on PostgreSQL when
`TEST_POSTGRES_URL` is set. The tests that cover this milestone:

| Test module | Proves |
|---|---|
| `tests/unit/test_subject_schemas.py` | Name rules and the case-insensitive key: Cyrillic, "ß", NFC/NFD, 200/201 characters, control characters ([data-model.md](./data-model.md#validation-rules-applied-by-clean_subject_name-research-d2)) |
| `tests/integration/test_subject_service.py` | Create, rename, activate, deactivate, delete; no-op writes; the unique constraint; refusal of a subject in use |
| `tests/integration/test_admin_area.py` | The `/admin` redirect, three tabs on each page, exactly one current tab, placeholder pages, no tabs outside the area (US3) |
| `tests/integration/test_admin_subjects.py` | US1, US2 end to end over HTTP: forms, `400` and `409` re-renders with the entered value kept, `404` "Subject not found", Post/Redirect/Get, reload safety |
| `tests/integration/test_routes.py` | Every new route declares `Role.ADMIN`, and the write-route list includes the six subject `POST`s (US4) |
| `tests/integration/test_access_control.py` | Teacher, student and administrator-using-student get `403` on every administrator page and action, and nothing changes (US4) |
| `tests/integration/test_cross_site.py` | A cross-site `POST` to a subject action is refused and nothing changes |
| `tests/integration/test_migrations.py` | Empty → head, stairway, drift: the `subjects` table exists and `users.role` is gone |

## 2. Manual walk-through

Start the application locally with one person per role, plus one person who is both an
administrator and a student (README, "Signing in locally as each role"):

```bash
uv run alembic upgrade head
ADMIN_EMAILS=admin@example.com,both@example.com \
TEACHER_EMAILS=teacher@example.com \
STUDENT_EMAILS=student@example.com,both@example.com \
uv run uvicorn app.main:app --reload
```

Sign-in codes are printed to the terminal.

### Tabs (US3)

1. Sign in as `admin@example.com`. On the home page, click **Administrator area**.
   → The address becomes `/admin/teachers`. Three tabs are shown, and **Teachers** is highlighted.
2. Click **Educational institutions**, then **Subjects**. → Each one loads a new page at its own
   address, with that tab highlighted.
3. Reload each tab, and open `/admin/subjects` in a new browser tab. → The same tab is shown.
4. Teachers and Educational institutions show only a placeholder sentence.

### Subjects (US1, US2)

1. **Subjects** shows "No subjects yet" and **Create**.
2. Create "Mathmatics", "Physics" and "chemistry". → The list shows chemistry, Mathmatics,
   Physics, all Active.
3. Create "  PHYSICS  ". → The form returns with "A subject named “Physics” already exists." and
   your input.
4. Create an empty name, then a name of 201 characters. → Each one is refused with its message
   and your input kept.
5. Rename "Mathmatics" to "Mathematics". Then rename "chemistry" to "Chemistry" (case only).
   → Both succeed.
6. Rename "Chemistry" to "physics". → Refused as a duplicate. "Chemistry" is unchanged.
7. Deactivate "Chemistry". → It shows Inactive, with an **Activate** button. Activate it again.
8. Create "Biology". Click **Delete**. → A confirmation page names it. Click **Cancel**: nothing
   changed. Click **Delete** again and confirm. → "Biology" is gone.
9. After any action, reload the list. → The action is not repeated.
10. Open `/admin/subjects/999/rename`. → "Subject not found", with a link back to the list.

### Access (US4)

1. Sign in as `teacher@example.com`, then as `student@example.com`. Open `/admin`,
   `/admin/subjects` and `/admin/subjects/new`. → "Access denied" each time. No page shows the tabs.
2. Sign in as `both@example.com` and choose **Student**. Open `/admin/subjects`. → "Access denied".
   Switch to **Administrator** from the header. → The page opens.
3. Sign out, then open `/admin/subjects`. → You are sent to sign in. After signing in as
   `admin@example.com`, you land on `/admin/subjects`.

## 3. After deployment

On the production URL, sign in as an administrator from `ADMIN_EMAILS` and repeat "Tabs" and
steps 1–2 and 8 of "Subjects". Production starts with an empty subject list. The migrations run
from the container entrypoint, so nothing needs to be run by hand.
