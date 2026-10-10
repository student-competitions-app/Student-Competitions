# Quickstart: Validate Regions and Educational Institutions (Milestone 7)

**Feature**: [spec.md](./spec.md) | **Routes**: [contracts/http-routes.md](./contracts/http-routes.md) |
**Services**: [contracts/institution-service.md](./contracts/institution-service.md)

This guide proves the milestone works, first with the automated suite and then by hand in a
browser.

## Prerequisites

- The repository set up as in the README ("Getting started"): `uv sync`.
- Optional, to run the PostgreSQL half of the suite: a local PostgreSQL server and
  `TEST_POSTGRES_URL` (README, "Test"). The row-lock behaviour (research D5) and the foreign-key
  backstop (research D4) matter only on PostgreSQL.

## 1. Automated checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Expected: all green, on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL` is set. The tests
for this milestone:

| Test module | Proves |
|---|---|
| `tests/unit/test_name_schemas.py` | One set of name rules, and the subject names are aliases of it (research D1) |
| `tests/unit/test_subject_schemas.py` | **Unchanged** and still green: the move changed no rule |
| `tests/integration/test_region_service.py` | Region create, rename, status, delete; uniqueness ignoring case (Cyrillic too); refusal while holding active or deactivated institutions; no cascade of status |
| `tests/integration/test_institution_service.py` | Uniqueness per region; refusal in a missing or deactivated region; wrong-region ids are "not found"; `region_id` never changes; in-use refusal via a monkeypatched count |
| `tests/integration/test_admin_institutions.py` | US1–US4 over HTTP: the two lists, "Select a region", "No regions yet", "No educational institutions yet"; selection in the address and `aria-current="true"`; every form with `400`/`409`/`404`; redirects to the right region; reload safety |
| `tests/integration/test_admin_area.py` | The Educational institutions tab is no longer a placeholder; every page of this feature marks that tab |
| `tests/integration/test_routes.py` | The 10 new `POST` routes are in the exact write list, and every new route declares `Role.ADMIN` |
| `tests/integration/test_access_control.py` | Teacher, student and administrator-using-another-role get `403` on every new page and action, and nothing changes; anonymous visitors are sent to sign in and come back with the region still selected (US5) |
| `tests/integration/test_cross_site.py` | A cross-site region or institution `POST` is refused and changes nothing |
| `tests/integration/test_migrations.py` | Empty → head, stairway and drift include `regions` and `institutions` |

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

### Regions (US1)

1. Sign in as `admin@example.com` and open **Administrator area** → **Educational institutions**.
   → The left side shows "No regions yet" and **Create**. The right side shows "Select a region".
2. Create "Kyiv". → The address becomes `/admin/institutions/regions/<id>`, and "Kyiv" is listed
   and highlighted.
3. Create "Odesa", "lviv" and "  Kharkiv Region  ". → The list is in this order: Kharkiv Region,
   Kyiv, lviv, Odesa. "Kharkiv Region" has no outer spaces.
4. Create "  KYIV  ", an empty name, and a name of 201 characters. → Each one is refused with its
   message, and your input is kept.

### Institutions (US2)

1. Click **Kyiv**. → The right side shows "No educational institutions yet" and **Create**.
2. Create "Kyiv Polytechnic Institute", then "Academy". → You are back on Kyiv, and both are
   listed: Academy, Kyiv Polytechnic Institute.
3. Create "kyiv polytechnic institute" in Kyiv. → Refused with "…already exists in this region."
4. Select **lviv** and create "Kyiv Polytechnic Institute". → Accepted. Each region lists only its
   own institutions.
5. Reload the page, copy the address into a new browser tab, and use the back button. → The same
   region stays selected each time.

### Changing regions (US3)

1. Rename "lviv" to "Lviv" (case only). → Accepted. Rename "Lviv" to "KYIV". → Refused, and "Lviv"
   is unchanged.
2. Deactivate **Odesa** and select it. → "Deactivated" is shown, there is no **Create**, and the
   page says new institutions cannot be added.
3. Open `/admin/institutions/regions/<Odesa id>/institutions/new` directly. → A refusal page, and
   nothing is created.
4. Activate **Odesa**. → **Create** is offered again.
5. Create "Test", click **Delete**, then **Cancel**. → Nothing changed. Delete it and confirm.
   → It is gone, and no region is selected.
6. Try to delete **Kyiv**. → Refused: it still holds educational institutions.

### Changing institutions (US4)

1. In Kyiv, rename "Academy" to "kyiv polytechnic institute". → Refused. Rename it to "Academy of
   Arts". → Accepted, and Kyiv stays selected.
2. Deactivate "Academy of Arts". → It shows "Deactivated" with **Activate**. Activate it again.
3. Deactivate **Kyiv**. → Its institutions keep their own statuses. Rename, deactivate and delete
   still work there. Activate Kyiv again. → The statuses are exactly as before.
4. Delete "Academy of Arts". → The confirmation names the institution and "Region: Kyiv". Confirm.
   → It is gone, and Kyiv stays selected.
5. After any action, reload. → The action is not repeated.
6. Open `/admin/institutions/regions/999` and
   `/admin/institutions/regions/<Lviv id>/institutions/<a Kyiv institution id>/rename`. → "Region
   not found" and "Educational institution not found", each with a link back.

### Access (US5)

1. Sign in as `teacher@example.com`, then as `student@example.com`. Open `/admin/institutions` and
   `/admin/institutions/regions/new`. → "Access denied" each time.
2. Sign in as `both@example.com` and choose **Teacher**. Open `/admin/institutions`. → "Access
   denied". Switch to **Administrator** in the header. → The page opens.
3. Sign out, then open `/admin/institutions/regions/<Kyiv id>`. → You are sent to sign in. After
   signing in as `admin@example.com`, you land on the same address with Kyiv selected.

## 3. After deployment

On the production URL, sign in as an administrator from `ADMIN_EMAILS` and repeat "Regions" steps
1–2 and "Institutions" steps 1–2. Production starts with empty lists. The migration runs from the
container entrypoint, so nothing needs to be run by hand.
