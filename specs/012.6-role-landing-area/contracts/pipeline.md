# Contract: Pipeline (Milestone 12.6)

## `.github/workflows/checks.yml`, job `image`

Step "Sign in, smoke test GET /, restart, and again" is renamed "Sign in, smoke test the landing,
restart, and again".

| Check | Before | After |
|---|---|---|
| anonymous `GET /` | 303 → `/login?next=%2F` | unchanged |
| `/login` opens in Ukrainian; language switch to English | as is | unchanged |
| signed-in landing | `GET /` → 200 | `GET /` → **303, `Location: /admin`** |
| page carrying the status | `/` | **`/admin/teachers`** → 200 |
| on that page: app name, signed-in address, logout form, no unavailable notice, `data-engine="postgresql"`, `data-boots` = expected | on `/` | same checks on `/admin/teachers` |
| role label "Administrator" | on `/` | on `/admin/teachers` |
| area links | `href="/admin"` and `href="/staff"`, no `/student`, `/teacher` | **no** `href="/staff"`, `href="/student"`, `href="/teacher"` |
| `GET /admin` → 303 `/admin/teachers`; `/admin/teachers` 200; `/student` 403 | as is | unchanged |
| cross-site logout refused, then `check_page / 200 'class="brand-role"'` | `/` | `check_page /admin/teachers 200 'class="brand-role"'` |
| after restart: boot count +1, same session | read on `/` | read on `/admin/teachers` |
| after logout `GET /` | 303 → `/login?next=%2F` | unchanged |

The step's leading comment is reworded: the status line is read on the administrator area's first tab.

## `.github/workflows/deploy.yml`

Comment only: "the page carrying it" means the administrator area. No behaviour change.

## `scripts/verify_private.sh`

Unchanged: it checks anonymous `/` → `/login?next=%2F` and anonymous `/admin` → `/login?next=%2Fadmin`.
