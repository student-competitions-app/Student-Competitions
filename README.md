# Student Competitions

A web application for running online knowledge competitions among students. Teachers manage students, a question bank and competitions; students answer questions in writing; answers are scored by an LLM..

> **Status:** milestone 4 in progress — the application has a front door: administrators sign in with a 6-digit code sent by email, and every page is private unless explicitly public. Behind it is milestone 3's home page: sample questions stored by a migration, and a status line showing the engine, the schema revision and how many times the application has started. Locally it uses a SQLite file and prints login emails to the console; in production, PostgreSQL on Neon and email through Resend. Implementation is driven by [GitHub Spec Kit](https://github.com/github/spec-kit).

**Public address:** <https://brainring.org.ua> — served from Render, HTTPS only (`www.brainring.org.ua` redirects there; the Render address <https://student-competitions.onrender.com> still works as a fallback). `GET /healthz` there reports the commit currently live.

## Getting started

### Prerequisites

[`uv`](https://docs.astral.sh/uv/) — and nothing else. **No system Python is required:** `uv` reads `.python-version` and provisions Python 3.13 itself. There is no database server to install, no `.env` file and no API keys: locally the application uses a SQLite file that the first migration creates.

Docker is needed only to build and run the packaged application ([below](#run-the-packaged-application)) and, optionally, to run the PostgreSQL half of the test suite ([below](#test)); it is not needed for development.

### Setup

```bash
git clone <repository-url>
cd Student-Competitions
uv sync
```

### Run

```bash
uv run alembic upgrade head          # creates data/student_competitions.sqlite3 at the newest schema
uv run uvicorn app.main:app --reload
```

Run `uv run alembic upgrade head` again after pulling a change that adds a migration. If you forget, the application refuses to start and prints that command. To start over from nothing, stop the application, delete `data/student_competitions.sqlite3` and migrate again.

The startup output ends with the address it is serving on:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Open <http://127.0.0.1:8000>. If port 8000 is already taken, pass `--port 8001`.

### Signing in locally as each role

Every page is private, so you sign in first, as one of the three roles: administrator, teacher or student. Who holds which role comes from three comma-separated lists, `ADMIN_EMAILS`, `TEACHER_EMAILS` and `STUDENT_EMAILS`. Locally any address works, because the code is printed to the terminal. Start the application with one person per role and one with two roles:

```bash
ADMIN_EMAILS=admin@example.com \
TEACHER_EMAILS=teacher@example.com,multi@example.com \
STUDENT_EMAILS=student@example.com,multi@example.com \
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>, which sends you to the login page, and enter one of those addresses. Nothing is sent: with no `EMAIL_BACKEND` set, the email is printed to the terminal running uvicorn:

```text
======== EMAIL (console backend: not sent) ========
To: you@example.com
Subject: Your Student Competitions sign-in code

Your Student Competitions sign-in code is: 042917
...
======== END EMAIL ========
```

Type the code into the second step. Someone with one role, such as `teacher@example.com`, lands straight on the page they asked for, with `Student Competitions · Teacher`, their address and **Log out** in the header. Someone with several roles, such as `multi@example.com`, first sees **Choose a role**, then lands on that page; the header then also offers **Switch to** the other role. To see another role's view, log out and sign in with another address, or open a private window. Sessions last 14 days and survive `--reload`, because the local signing key is a fixed development constant. The startup log warns about each sign-in setting left at its local default; that is expected locally and refused on Render ([settings](#environment-variables)).

Only addresses on at least one list can sign in. The lists are applied on every start: removing an address from **any** list and restarting logs that person out everywhere, and removing it from every list also stops them obtaining a code. Any other address gets the same "we have sent a code" page, and nothing is sent.

### Roles and access

Every page states which roles may open it, and access is judged by the role the session is **currently** using, never by every role the person holds:

| Page | Administrator | Teacher | Student |
|---|---|---|---|
| `/` home page | ✅ | ✅ | ✅ |
| `/admin` Administrator area | ✅ | ❌ | ❌ |
| `/teacher` Teacher area | ❌ | ✅ | ❌ |
| `/student` Student area | ❌ | ❌ | ✅ |
| `/staff` Staff area | ✅ | ✅ | ❌ |

The four areas are placeholders that later milestones fill. The home page links exactly the areas the current role may open. A page the current role may not open answers **403 Access denied**, naming the current role; the application never switches role for you.

- **Current role.** Each browser has its own. Someone with one role is always in it. Someone with several chooses one at `GET /role` right after the code, and every other page sends them there until they do.
- **Switching.** The header's **Switch to** buttons post to `/role` and land on the home page. Switching in one browser leaves the others as they are.
- **Cross-site requests.** Every request that is not `GET`, `HEAD` or `OPTIONS` is refused with 403 when the browser says it came from another site (`Sec-Fetch-Site`, or else an `Origin` that does not match `Host`), before any session is read. This covers signing in and out, choosing a role, and every future write, with no per-form token. Requests that carry neither header, like `curl`'s, are allowed.

### Test

```bash
uv run pytest
```

Every test that touches the database runs twice, as `[sqlite]` and `[postgresql]`. Without further setup the SQLite cases run and the PostgreSQL ones are skipped with a reason. To run both engines the way CI does, start a password-less PostgreSQL 17 and point `TEST_POSTGRES_URL` at it:

```bash
docker run -d --name sc-pg -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:17
TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest
docker rm -f sc-pg                   # when done
```

The suite creates and drops its own uniquely named databases on that server, and never touches `data/` or whatever `DATABASE_URL` points to. In CI (`CI=true`) a missing `TEST_POSTGRES_URL` fails the run at start, so the PostgreSQL half can never be skipped silently.

No test sends an email: the suite always runs with `EMAIL_BACKEND=memory`. Every application fixture starts with the same cast: `admin@example.com`, `teacher@example.com` and `student@example.com` (one role each), `admin.student@example.com` and `teacher.student@example.com` (two roles each). For page tests, [`tests/conftest.py`](tests/conftest.py) provides:

- `client`: the running application, **anonymous**;
- `client_as(email, current_role=AUTO)`: a further client **signed in** as one of the cast through a session created directly in the database. `AUTO` starts it the way a real sign-in would (one role: that role; several: none chosen yet), and a `Role` or `None` overrides it. This is the only sign-in shortcut, and it exists only in `tests/`;
- `admin_client`: `client_as("admin@example.com")`;
- `outbox`: every email the application has sent, for tests that walk through the real login and read the code.

### Adding a page

Access is **denied by default**. An application-wide dependency in [`app/core/auth.py`](app/core/auth.py) sends an anonymous visitor of any route to `/login?next=…`, and then admits a signed-in person only if the route declares their current role. Declare it next to the handler:

```python
@router.get("/teacher/questions", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def question_bank(request: Request) -> HTMLResponse: ...
```

A route without `@allow_roles(...)` answers 403 to everyone. Test each role on it with `client_as(...)`: allowed roles get 200, the others 403, and `client` is redirected to sign in.

Making a route public is a deliberate, one-line change to `PUBLIC_ROUTES` in the same file. Today the list is `GET`/`POST /login`, `POST /login/code`, `POST /logout` and `GET /healthz`; `GET`/`POST /role` (`ROLE_CHOICE_ROUTES`) are open to anyone signed in. The route-table sweep in [`tests/integration/test_routes.py`](tests/integration/test_routes.py) walks every route and fails the build, naming the route, if one is neither public, nor the role choice, nor declared; if a declared page admits a role it should not; if one outside the list answers an anonymous request; or if a list names a route that does not exist.

### Adding a migration

Every change to the database structure is an Alembic migration in `migrations/versions/`; nothing creates tables any other way.

```bash
# 1. change or add a model in app/models/ (and import it in app/models/__init__.py)
uv run alembic revision --autogenerate -m "short description"
# 2. read the generated file and fix what autogenerate got wrong
uv run alembic upgrade head
uv run pytest                        # the drift, single-head and stairway tests guard the history
```

Rules that keep releases safe:

- **Keep the previous release working.** During a deploy the old and the new version run side by side for a moment, both against the new schema. Add first (a new column, a new table) and remove in a later release, never both in one.
- **Data migrations use a frozen table.** Describe the table with `sa.table(...)` inside the migration; never import from `app`, whose models will change later.
- **Migrations run themselves on release.** The container runs `alembic upgrade head` before starting the application; there is no manual production command. On PostgreSQL the whole upgrade is one transaction behind an advisory lock, so a failure changes nothing and two starting instances cannot both apply it.
- **SQLite is not transactional for schema changes.** A failed local migration may leave `data/student_competitions.sqlite3` half-migrated: fix the migration and run it again, or delete the file and migrate from scratch.

### Lint & format

```bash
uv run ruff check .
uv run ruff format --check .
```

## Run the packaged application

The same image the platform runs. Build and start it from a clean checkout with Docker installed, and nothing else:

```bash
docker build --build-arg APP_COMMIT="$(git rev-parse HEAD)" -t student-competitions .
docker run --rm -p 8000:8000 student-competitions
```

Open <http://localhost:8000>. `APP_COMMIT` is optional — it stamps the commit that `/healthz` reports; without it the endpoint reports `"unknown"`.

The container migrates its database before the application starts. With no `DATABASE_URL` it uses a throw-away SQLite file inside the container; to use a PostgreSQL database instead, pass `-e DATABASE_URL=postgresql://…`.

To sign in to the container, give it an administrator with `-e ADMIN_EMAILS=you@example.com` (and, to try the other roles, `-e TEACHER_EMAILS=…` and `-e STUDENT_EMAILS=…`), and read the code from its output (`docker logs <container>` if it runs detached). The CI `image` job signs in exactly this way.

The port is configuration, not code. To listen somewhere else, with no rebuild:

```bash
docker run --rm -e PORT=9000 -p 9000:9000 student-competitions
```

On macOS, if the build fails with `docker-credential-desktop: executable file not found in $PATH`,
Docker Desktop's credential helper is not on your `PATH`. Add it:

```bash
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
```

### Service status

`GET /healthz` reports what is live, as JSON:

```json
{"status": "ok", "version": "0.1.0", "commit": "9f2c1ab3e4d5678901234567890abcdef1234567"}
```

Render uses it as the service's health check, and the deploy pipeline polls it to prove a release actually landed.

Every page also carries the same release identity in its footer — `v<version>` and the short commit, with the full SHA on hover — so which release is serving is visible without leaving the page.

### Environment variables

The complete configuration surface. Locally every one is optional — the application starts on the defaults below with nothing supplied. On Render, `DATABASE_URL` and the five milestone 4 sign-in settings are required, and the application refuses to start without them; `TEACHER_EMAILS` and `STUDENT_EMAILS` may be empty. The refusal names every missing or invalid setting and never shows a value.

| Variable | Read by | Default | Purpose |
|---|---|---|---|
| `PORT` | the container entrypoint (`uvicorn --port`) | `8000` | The port to listen on. Render sets it automatically. |
| `HOST` | the container entrypoint (`uvicorn --host`) | `0.0.0.0` | The interface to bind. Set explicitly in `render.yaml`. |
| `APP_COMMIT` | `app/core/config.py` | *(empty)* | Stamps the commit for a local or CI build. Empty falls through to `RENDER_GIT_COMMIT`. |
| `RENDER_GIT_COMMIT` | `app/core/config.py` | *(unset off-Render)* | Set automatically by Render for every deploy; what makes `/healthz` truthful in production. |
| `PYTHONUNBUFFERED` | Python | `1` (set in the image) | Logs reach the platform's stream immediately instead of sitting in a buffer. |
| `DATABASE_URL` | `app/core/config.py` and `migrations/env.py` | `sqlite:///<repository>/data/student_competitions.sqlite3`, **only when not on Render** | Where the database is. `sqlite:///…` or `postgresql://…` (also `postgres://`; normalised to the psycopg driver). **A secret in production**: Neon's connection string, set only in Render's dashboard and never committed, pasted or logged. |
| `RENDER` | `app/core/config.py` | *(unset)* | Set to `true` by Render. Turns a missing `DATABASE_URL` into a refusal to start instead of a silent fallback to SQLite, applies the production rules for the settings below, marks the session cookie `Secure`, and makes the per-client rate limit read `X-Forwarded-For`. Do not set it locally. |
| `EMAIL_BACKEND` | `app/core/config.py` | `console` (with a warning) | How login emails are delivered: `console` prints them to the application's output, `memory` keeps them in memory (tests only), `resend` sends them through Resend. **Must be `resend` on Render**; declared with that value in `render.yaml`. Not a secret. |
| `SECRET_KEY` | `app/core/config.py` | a fixed, insecure development key (with a warning) | Signs session cookies and keys the stored code and rate-limit hashes. At least 32 characters, everywhere. **A secret; required on Render.** Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Changing it signs everyone out. |
| `ADMIN_EMAILS` | `app/core/config.py` | empty (with a warning: nobody can sign in as an administrator; if all three lists are empty, nobody can sign in at all) | Comma-separated administrator addresses, e.g. `a@example.com, b@example.com`. Trimmed, lowercased and de-duplicated; a malformed entry is refused by position, never echoed. Applied on every start, with the two lists below: listed addresses become active people holding the roles of the lists they are on, anyone who loses a role is logged out everywhere, and anyone on no list is deactivated. **A secret; required and non-empty on Render.** |
| `TEACHER_EMAILS` | `app/core/config.py` | empty: nobody is a teacher | Comma-separated teacher addresses, parsed exactly like `ADMIN_EMAILS`. An address on several lists is one person with several roles. **Temporary**: milestone 7 replaces it with teacher management in the application. **A secret; optional and may be empty on Render, but every entry must be well-formed.** Removing an address logs that person out everywhere at the restart. |
| `STUDENT_EMAILS` | `app/core/config.py` | empty: nobody is a student | Comma-separated student addresses, exactly as `TEACHER_EMAILS`, and temporary in the same way. **A secret; optional and may be empty on Render, but every entry must be well-formed.** |
| `RESEND_API_KEY` | `app/core/config.py` | *(unset)* | Resend API key, sending-only and restricted to the domain. **A secret; required for `resend` and on Render.** |
| `EMAIL_FROM` | `app/core/config.py` | *(unset)* | The sender, `addr@domain` or `Display Name <addr@domain>`, on the verified domain (`Student Competitions <login@brainring.org.ua>`). **Required for `resend` and on Render**; kept in Render's environment like the secrets. |
| `TEST_POSTGRES_URL` | `tests/conftest.py` only | *(unset: PostgreSQL tests skipped)* | **Tests only** — never read by the application. A PostgreSQL server where the tests may create databases. Not a secret (a disposable, password-less server). |

The application reads seven secrets in production: `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAILS`, `TEACHER_EMAILS`, `STUDENT_EMAILS`, `RESEND_API_KEY` and `EMAIL_FROM`. They live in Render's service environment and nowhere else: not in this repository, not in the image and not in GitHub. `render.yaml` declares them by name only (`sync: false`). The application never logs a login code, a session token, a key or an address; only the local `console` backend prints an email.

## Deployment

Hosted on [Render](https://render.com) (free instance type, Frankfurt), configured by [`render.yaml`](render.yaml). Render's own auto-deploy is **off**: the pipeline is the only thing that releases.

### Domain

`brainring.org.ua` is registered at [NIC.UA](https://nic.ua), which also hosts its DNS: an `A` record for the root pointing to Render's load balancer (`216.24.57.1`) and a `CNAME` for `www` pointing to `student-competitions.onrender.com.`. Render learns the domain from the `domains:` list in `render.yaml` and issues and renews the TLS certificate itself. The domain and the NIC.UA name-server service are separate orders, each renewed automatically. The GitHub repository variable `PUBLIC_BASE_URL` holds this address, so the deploy job checks releases through it.

### Releasing

Merge to `main`. That is the whole procedure — no commands, no dashboard.

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) then runs the same checks a pull request runs, calls Render's deploy hook pinned to the merged commit, and polls the public `/healthz` until it reports that commit. The workflow only reports success once the public address is actually serving the merged commit; the GitHub **Environments → production** view records which commit went live and when.

Each release runs `alembic upgrade head` before the new version serves: the container's entrypoint migrates, then starts the application. A failed migration, or missing sign-in settings, stops the container before it opens its port, so Render keeps the previous release serving. After the release, the deploy job runs [`scripts/verify_private.sh`](scripts/verify_private.sh): the home page must send an anonymous visitor to `/login?next=%2F`, the login page must serve its form, and the Administrator area must send an anonymous visitor to `/login?next=%2Fadmin`. That proves the site and its role pages are private.

The home page's status line (schema revision and boot count) now requires signing in, so the release no longer reads it. "Data survives a restart" is checked on every pull request instead, by the `image` job, which signs in to the real container and restarts it. To watch the boot count rise across a production redeploy, sign in and compare the status line before and after.

### Production email

Login emails are sent through [Resend](https://resend.com)'s HTTP API from the verified domain `brainring.org.ua`. DKIM, SPF and DMARC are published at NIC.UA. The one-time bootstrap (verify the domain, create a sending-only key, enter the four sign-in secrets in Render) is described in [`specs/004-email-otp-auth/quickstart.md`](specs/004-email-otp-auth/quickstart.md#one-time-bootstrap-production-do-this-before-merging-to-main). It must be done **before** the first release that needs it; otherwise that release refuses to start, by design, and the previous one keeps serving.

To change who can sign in, and as what, edit `ADMIN_EMAILS`, `TEACHER_EMAILS` or `STUDENT_EMAILS` in Render → service → Environment and save; the restart applies the lists. Check every entry for typos: a malformed one refuses the start (the previous release keeps serving), and a well-formed misspelling silently signs nobody in. Removing an address from any list logs that person out everywhere. To rotate `SECRET_KEY` or `RESEND_API_KEY`, replace the value there the same way. A new `SECRET_KEY` signs everyone out.

**Delivery to Outlook.** Gmail and Outlook/Hotmail both deliver the codes to the inbox (checked 2026-10-01). Earlier, Outlook put them in Junk although SPF, DKIM and DMARC all passed: Microsoft's filter rated the then-new sending domain on reputation (spam confidence level 5), not on authentication. That has since stopped as the domain built up a sending history. If codes start landing in Junk again, the cause is most likely reputation rather than configuration: check Junk and mark the message *Not junk*. The original finding is recorded under T072 in [`specs/004-email-otp-auth/tasks.md`](specs/004-email-otp-auth/tasks.md).

### Production database

PostgreSQL 17 on Neon's free plan (project `student-competitions`, AWS Europe Central 1 / Frankfurt), next to the Render service. Render reads its **direct** (non-pooled) connection string from the `DATABASE_URL` environment variable, declared in `render.yaml` without a value and entered once in the dashboard. The one-time bootstrap is described in [`specs/003-database-questions/quickstart.md`](specs/003-database-questions/quickstart.md#one-time-bootstrap-production-database).

To rotate the credential: in Neon, reset the role's password and copy the new connection string; in Render → service → Environment, replace `DATABASE_URL` and choose **Save, rebuild, and deploy**.

### Rolling back

If a release is bad, get the public address healthy first, then fix `main`:

1. **Render dashboard → Deploys → Rollback** on the last successful deploy. Fastest, because nothing is rebuilt, and available to anyone with dashboard access.
2. **Or re-deploy the last good commit** from a terminal:

   ```bash
   export RENDER_DEPLOY_HOOK_URL='<the service deploy hook URL>'
   ./scripts/render_deploy.sh <previous-good-sha>
   ./scripts/wait_for_release.sh https://brainring.org.ua <previous-good-sha>
   ```

Then **revert the bad commit on `main`** and let the pipeline publish the revert, so the repository and the public address agree again. Until that happens, the next merge re-publishes the broken version.

A failed release leaves the previous version serving: Render switches traffic only after a new instance passes its health check.

### Continuous integration

| Workflow | Runs on | Does |
|---|---|---|
| [`checks.yml`](.github/workflows/checks.yml) | called by the two below | `quality` (tests on SQLite and on a PostgreSQL service, `ruff check`, `ruff format --check`) and `image` (builds the Dockerfile; checks it refuses to start on Render without a database, without sign-in settings, or with the console email backend; then signs in to the container with the code from its console output and smoke-tests it against PostgreSQL across a restart and a logout) |
| [`ci.yml`](.github/workflows/ci.yml) | every pull request against `main` | Calls `checks.yml`. Branch protection requires both jobs, so a failing check blocks the merge. |
| [`deploy.yml`](.github/workflows/deploy.yml) | every push to `main` | Calls `checks.yml`, then deploys and verifies the release. |

Apply the branch protection rule with [`scripts/setup_branch_protection.sh`](scripts/setup_branch_protection.sh) (needs the `gh` CLI, authenticated with admin rights).

## Requirements

- Product requirements: [`docs/requirements/product-requirements.md`](docs/requirements/product-requirements.md)
- Technical requirements & milestones: [`docs/requirements/technical-requirements.md`](docs/requirements/technical-requirements.md)

## Tech stack

| Area | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-side rendering: Jinja2 + HTMX + Pico.css |
| Database | SQLModel + Alembic migrations, psycopg 3; SQLite locally and in tests, PostgreSQL 17 on Neon's free plan in production (and in CI) |
| Authentication | Email OTP + server-side sessions in a signed cookie |
| Answer evaluation | LLM API (Claude or OpenAI) with structured output |
| Containerization | Docker (two-stage build, non-root, uv-locked dependencies) |
| Hosting | Render, configured as code by `render.yaml` |
| CI/CD | GitHub Actions: checks on every pull request, auto-deploy on merge to `main` |
| Tooling | uv, ruff, pytest, Playwright (later) |

## Repository layout

```text
.
├── .claude/skills/          # Spec Kit skills for Claude Code (/speckit-*)
├── .specify/                # Spec Kit: constitution, templates, scripts, workflows
│   └── memory/constitution.md
├── .github/workflows/       # CI/CD
│   ├── checks.yml           # Reusable: quality + image jobs
│   ├── ci.yml               # Pull requests → checks (the merge gate)
│   └── deploy.yml           # Push to main → checks, deploy, verify
├── docs/requirements/       # Source product & technical requirements
├── specs/                   # Feature specs created by /speckit-specify (NNN-feature-name/)
├── Dockerfile               # Two-stage image: uv builder → python:3.13-slim runtime; migrates, then serves
├── .dockerignore            # Build context: keeps tests, specs, .git, env files and local databases out
├── render.yaml              # Render Blueprint: the service, as code
├── alembic.ini              # Alembic: script location, file naming, ruff hooks (no database URL)
├── pyproject.toml           # Project metadata, dependencies, ruff & pytest config
├── uv.lock                  # Committed lockfile
├── .python-version          # 3.13
├── app/                     # FastAPI application
│   ├── main.py              # App construction: startup (settings, database guard, user reconcile, boot count), access dependency, routers, error handlers
│   ├── core/                # Settings, security, access control, DB engine
│   │   ├── config.py        # App constants, COMMIT_SHA, resolve_database_url, resolve_auth_settings
│   │   ├── security.py      # Pure helpers: email rules, codes, tokens, cookie signing, safe return paths, the cross-site rule
│   │   ├── auth.py          # PUBLIC_ROUTES, ROLE_CHOICE_ROUTES, @allow_roles, the access dependency, CurrentUser/CurrentRole, the session cookie
│   │   ├── db.py            # Engine, per-request session, UTC timestamp column type
│   │   ├── migrations.py    # Expected (head) and current schema revision; startup guard
│   │   └── templates.py     # Shared Jinja2Templates instance (+ `current_user`, `current_role`, `user_roles` for every page)
│   ├── models/              # SQLModel tables: Question, BootCounter, User, UserRole, UserSession, LoginCode, RateLimitHit
│   ├── schemas/             # Validation and view schemas: questions, login form input
│   ├── routers/             # Route handlers grouped by area/role
│   │   ├── pages.py         # GET / → home page with the question list and status line
│   │   ├── auth.py          # GET/POST /login, POST /login/code, POST /logout
│   │   ├── roles.py         # GET/POST /role → choose or switch the current role
│   │   ├── areas.py         # /admin, /teacher, /student, /staff placeholders (AREAS also drives the home links)
│   │   └── health.py        # GET /healthz → status, version, commit
│   ├── services/            # Business logic: questions, database_status, users, sessions, login, rate_limits, email
│   ├── templates/           # Jinja2: layouts/, partials/ (HTMX fragments), pages/
│   │   ├── layouts/base.html  # Header with the current role, the signed-in address, the role switch and Log out
│   │   └── pages/           # home.html, login.html, login_code.html, role_choice.html, area.html, error.html
│   └── static/              # css/ (vendored pico.min.css + app.css), js/, img/
├── migrations/              # Alembic migrations
│   ├── env.py               # Uses resolve_database_url; one locked transaction on PostgreSQL
│   └── versions/            # Revisions: tables + boot counter, the sample questions, the sign-in tables, user roles
├── data/                    # Local SQLite database (git-ignored, created by the first migration)
├── tests/                   # unit/, integration/, e2e/ (Playwright)
│   ├── conftest.py          # Both-engine database fixtures (template + clone), the cast, `client`, `client_as`, `admin_client`, `outbox`
│   ├── unit/                # config, database and auth settings, security helpers, safe return paths, the cross-site rule, email, schemas
│   └── integration/         # access control, role choice and switch, cross-site, login flow and privacy, sessions, user reconcile, auth services, home, health, routes, startup, migrations, boot counter, question service
└── scripts/                 # Developer & ops helper scripts
    ├── render_deploy.sh            # Trigger a Render deploy of one commit
    ├── wait_for_release.sh         # Poll /healthz until that commit is serving
    ├── verify_private.sh           # After a release: / and /admin redirect anonymous visitors to /login, which serves its form
    └── setup_branch_protection.sh  # Apply the main branch protection rule
```

The internal layout of `app/` is a starting point; the implementation plan (`/speckit-plan`) may refine it.

## Spec-driven workflow

Requires [Claude Code](https://claude.com/claude-code) and [uv](https://docs.astral.sh/uv/).

1. `/speckit-constitution` — define project principles (fill `.specify/memory/constitution.md`)
2. `/speckit-specify` — describe a milestone / feature → `specs/NNN-feature/spec.md`
3. `/speckit-clarify` *(optional)* — resolve ambiguities
4. `/speckit-plan` — technical plan for the feature
5. `/speckit-tasks` — break the plan into tasks
6. `/speckit-analyze` *(optional)* — cross-artifact consistency check
7. `/speckit-implement` — implement the tasks

Work one milestone at a time on a feature branch (`NNN-feature-name`) and merge via pull request.

To upgrade Spec Kit files later:

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init --here --force --integration claude --script sh
```
