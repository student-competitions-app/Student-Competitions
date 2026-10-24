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

Every page is private, so you sign in first, as one of the three roles: administrator, teacher or student. Administrators come from one comma-separated list, `ADMIN_EMAILS`. Teachers come from **invitations**: an administrator invites them, and they become teachers only when they accept (milestone 8). Students come only from a teacher's invitation into a class, in the same way (milestone 9). Locally any address works, because every email is printed to the terminal. Start the application with an administrator:

```bash
ADMIN_EMAILS=admin@example.com uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>, which sends you to the login page, and enter that address. Nothing is sent: with no `EMAIL_BACKEND` set, the email is printed to the terminal running uvicorn:

```text
======== EMAIL (console backend: not sent) ========
To: you@example.com
Subject: Your Student Competitions sign-in code

Your Student Competitions sign-in code is: 042917
...
======== END EMAIL ========
```

Type the code into the second step. Someone with one role lands straight on the page they asked for, with `Student Competitions · Administrator`, their address (a link to their profile) and **Log out** in the header.

**To sign in as a teacher**, invite yourself: create a region and an educational institution on the **Educational institutions** tab, then **Teachers → Invite teacher** with your own address (or any other). The invitation email is printed to the terminal; open its link (`/invitations/…`), press **I agree**, and you are a teacher too. Someone with several roles, like a self-invited administrator, first sees **Choose a role** at the next sign-in, and the header then offers **Switch to** the other role. **To sign in as a student**, sign in as that teacher, open **Teacher area → Students**, choose the region, the institution and **+ Add class**, create a class, press **Add student** and invite another address; accept its printed link the same way. To see another role's view, log out and sign in with another address, or open a private window. Sessions last 14 days and survive `--reload`, because the local signing key is a fixed development constant. The startup log warns about each sign-in setting left at its local default; that is expected locally and refused on Render ([settings](#environment-variables)).

Only people holding a role can sign in. `ADMIN_EMAILS` is applied on every start: removing an address and restarting takes the administrator role away and logs that person out everywhere; a person left with no role can no longer obtain a code. It never touches the teacher role: removing a teacher is done on the **Teachers** tab. Any other address gets the same "we have sent a code" page, and nothing is sent. `TEACHER_EMAILS` and `STUDENT_EMAILS` are retired and ignored.

### Roles and access

Every page states which roles may open it, and access is judged by the role the session is **currently** using, never by every role the person holds:

| Page | Administrator | Teacher | Student |
|---|---|---|---|
| `/` home page | ✅ | ✅ | ✅ |
| `/admin` Administrator area (redirects to `/admin/teachers`) | ✅ | ❌ | ❌ |
| `/admin/teachers`, `/admin/institutions`, `/admin/subjects` (and every page and action under it) | ✅ | ❌ | ❌ |
| `/profile` own profile, and withdrawing consent | ✅ | ✅ | ✅ |
| `/teacher` Teacher area (redirects to `/teacher/students`), and every page and action under it | ❌ | ✅ | ❌ |
| `/student` Student area | ❌ | ❌ | ✅ |
| `/staff` Staff area | ✅ | ✅ | ❌ |

The student and staff areas are placeholders that later milestones fill. The administrator area has three tabs, each with its own address. **Teachers** lists the current teachers (sorted by last name) with their institutions and access levels (Read or Write), the **Can create competitions** setting and the date of consent; **Invite teacher** emails an invitation, and each teacher's page edits names, institutions, levels and the setting, or removes the teacher. Nothing about an invited person is stored until they press **I agree**: the whole invitation travels encrypted in the emailed link (`/invitations/…`, valid for seven days). **Educational institutions** shows regions on the left and the institutions of the selected region on the right; the selected region is part of the address (`/admin/institutions/regions/{id}`), so it survives a reload or a bookmark. Administrators create, rename, deactivate/activate and delete both. Region names are unique ignoring case, and institution names are unique ignoring case within their region (the same name may exist in another region). A deactivated region accepts no new institutions, but its institutions keep their own statuses and stay manageable. Deactivating a region or an institution asks for confirmation first, because it signs out and hides the students below it. A region that still holds institutions, or an institution in use (linked to a teacher, or with an enrolled student), cannot be deleted; its empty classes are deleted with it. **Subjects** lets administrators create, rename, deactivate/activate and delete subjects. Subject names are unique ignoring case (in every alphabet), and a subject in use cannot be deleted, only deactivated. The home page links exactly the areas the current role may open. A page the current role may not open answers **403 Access denied**, naming the current role; the application never switches role for you.

- **Current role.** Each browser has its own. Someone with one role is always in it. Someone with several chooses one at `GET /role` right after the code, and every other page sends them there until they do.
- **Switching.** The header's **Switch to** buttons post to `/role` and land on the home page. Switching in one browser leaves the others as they are.
- **Consent pages.** The invitation link, **Delete my data** (`/data-deletion`, linked from the sign-in page; it emails a one-hour, one-use link) and `/data-erased` are public: the sealed token in the link is their authority, and they act only on the person it names. Everyone signed in can open `/profile`, see what is stored about them and the consent text they accepted, and **Withdraw consent**, which erases their names (and email, unless they are an administrator), removes the teacher and student roles (and a student's class) and signs them out everywhere.
- **Cross-site requests.** Every request that is not `GET`, `HEAD` or `OPTIONS` is refused with 403 when the browser says it came from another site (`Sec-Fetch-Site`, or else an `Origin` that does not match `Host`), before any session is read. This covers signing in and out, choosing a role, the administrator's subject actions, and every future write, with no per-form token. Requests that carry neither header, like `curl`'s, are allowed.

### Teacher area

`/teacher` opens the **Students** tab (`/teacher/students`); **Competitions** is a placeholder. A teacher sees only the available educational institutions they are linked to, and each one's access level:

- **Choosing a class.** Three lists in a row (Region, Educational institution, Class), each opening its choice at once (one small script submits the list's form on change); they stack on a phone. The selection lives in the address (`?region=…&institution=…&class=…`), so it survives a reload or a bookmark. Anything in the address the teacher cannot reach answers **403 Access denied**, unknown ids included.
- **Classes.** A class belongs to one institution and has a name (unique ignoring case within the institution) and a year of study from 1 to 12. With **Write** access a teacher creates (**+ Add class**), edits, deactivates (after a confirmation), activates and deletes classes; a class with a student cannot be deleted.
- **Students.** With Write access a teacher invites students one by one into an active class (**Add student**: email, first and last name). Nothing is stored until the student presses **I agree**; only then are the student role and the enrolment written. An address that already belongs to a student is refused, and a teacher may send 100 student invitations an hour. The class lists its students by last name; **Edit** changes the names or moves the student to another active class of the same institution, and **Remove** takes the student role away.
- **Read access** shows the same classes and students with no actions at all.

**The deactivation chain.** Regions hold institutions, institutions hold classes, classes hold students. A class is available only while it, its institution and its region are all active. Deactivating any of them signs out every student below it at once; those students cannot sign in with the student role (with no other role, sign-in treats them as an unknown address) and teachers no longer see them, but they can still use **Delete my data**. Nothing below changes its own status, so activating the object again restores exactly what was there.

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

Making a route public is a deliberate, one-line change to `PUBLIC_ROUTES` in the same file. Today the list is `GET`/`POST /login`, `POST /login/code`, `POST /logout`, `GET /healthz`, the emailed-link pages (invitations and data deletion) and `POST /theme`; `GET`/`POST /role` (`ROLE_CHOICE_ROUTES`) are open to anyone signed in. The route-table sweep in [`tests/integration/test_routes.py`](tests/integration/test_routes.py) walks every route and fails the build, naming the route, if one is neither public, nor the role choice, nor declared; if a declared page admits a role it should not; if one outside the list answers an anonymous request; or if a list names a route that does not exist.

### Design system and UI guidelines

Every page is built from the component library in [`app/templates/components/`](app/templates/components/) and follows [`docs/requirements/ui-guidelines.md`](docs/requirements/ui-guidelines.md): the principles, the design tokens, when to use each component, the wording patterns and the phone behaviour. Colours and sizes are the `--sc-*` tokens at the top of [`app/static/css/app.css`](app/static/css/app.css), mapped onto Pico's own variables; Pico's stylesheet is never edited. A new pattern goes into the library, the gallery and the guidelines first, then onto a page. [`tests/unit/test_stylesheet.py`](tests/unit/test_stylesheet.py) fails the build on an undefined or unused class, an inline `style`, a literal colour or pixel length outside the tokens, or anything loaded from another site.

- **Component gallery**: [`/admin/components`](http://127.0.0.1:8000/admin/components) shows every component in every variant, with sample data. It is for administrators, not linked from the tabs, and exists only outside production: with `RENDER` set it is the same "not found" page as any unknown address.
- **Light, Dark, Device**: the theme switch in the user menu and on the sign-in page keeps the choice in the browser's `sc_theme` cookie (`light` or `dark`; **Device**, the default, deletes it and follows the operating system). The server renders the chosen theme, so there is no flash and no script. The cookie holds only the choice, is not linked to the account and follows no one to another browser.
- **Fonts**: Open Sans is self-hosted in [`app/static/fonts/`](app/static/fonts/) as four variable `woff2` subsets (Latin, Latin Extended, Cyrillic, Cyrillic Extended), under the SIL Open Font License ([`OFL.txt`](app/static/fonts/OFL.txt)). No page loads a font, a script or a stylesheet from another site.

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

To sign in to the container, give it an administrator with `-e ADMIN_EMAILS=you@example.com` (to try the teacher role, invite yourself as described in [Signing in locally](#signing-in-locally-as-each-role)), and read the code from its output (`docker logs <container>` if it runs detached). The CI `image` job signs in exactly this way.

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

The complete configuration surface. Locally every one is optional — the application starts on the defaults below with nothing supplied. On Render, `DATABASE_URL`, the five milestone 4 sign-in settings and `PUBLIC_BASE_URL` are required, and the application refuses to start without them. `TEACHER_EMAILS` and `STUDENT_EMAILS` are **retired** (milestone 8): they are no longer read, and a leftover value is ignored. The refusal names every missing or invalid setting and never shows a value.

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
| `SECRET_KEY` | `app/core/config.py` | a fixed, insecure development key (with a warning) | Signs session cookies, keys the stored code, rate-limit and invitation cut-off hashes, and encrypts invitation and data-deletion links. At least 32 characters, everywhere. **A secret; required on Render.** Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Changing it signs everyone out, makes every outstanding invitation and data-deletion link invalid, and resets the rate limits and the invitation cut-offs (harmless: every invitation issued before the change is invalid too). |
| `ADMIN_EMAILS` | `app/core/config.py` | empty (with a warning: nobody can sign in as an administrator) | Comma-separated administrator addresses, e.g. `a@example.com, b@example.com`. Trimmed, lowercased and de-duplicated; a malformed entry is refused by position, never echoed. Applied on every start, to the administrator role only: listed addresses become active administrators, an unlisted administrator loses the role and is logged out everywhere, and is deactivated only when no other role (such as teacher) is left. **A secret; required and non-empty on Render.** |
| `PUBLIC_BASE_URL` | `app/core/config.py` | *(unset: links use the request's address)* | The origin of every emailed link, e.g. `https://brainring.org.ua`: an absolute `http`/`https` URL with no path, query or fragment (a trailing `/` is removed). **Required on Render, and must be `https` there**, so a link is never built from a forged `Host` header. Not a secret; set as a plain value in `render.yaml`. |
| `RESEND_API_KEY` | `app/core/config.py` | *(unset)* | Resend API key, sending-only and restricted to the domain. **A secret; required for `resend` and on Render.** |
| `EMAIL_FROM` | `app/core/config.py` | *(unset)* | The sender, `addr@domain` or `Display Name <addr@domain>`, on the verified domain (`Student Competitions <login@brainring.org.ua>`). **Required for `resend` and on Render**; kept in Render's environment like the secrets. |
| `TEST_POSTGRES_URL` | `tests/conftest.py` only | *(unset: PostgreSQL tests skipped)* | **Tests only** — never read by the application. A PostgreSQL server where the tests may create databases. Not a secret (a disposable, password-less server). |

The application reads five secrets in production: `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY` and `EMAIL_FROM`. They live in Render's service environment and nowhere else: not in this repository, not in the image and not in GitHub. `render.yaml` declares them by name only (`sync: false`). The application never logs a login code, a session token, a key, an address, a name or a link token (the access log replaces invitation and deletion tokens with `***`); only the local `console` backend prints an email.

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

To change who is an administrator, edit `ADMIN_EMAILS` in Render → service → Environment and save; the restart applies the list. Check every entry for typos: a malformed one refuses the start (the previous release keeps serving), and a well-formed misspelling silently signs nobody in. Removing an address logs that person out everywhere. Teachers are invited and removed on the **Teachers** tab. After the milestone 8 release, delete the retired `TEACHER_EMAILS` and `STUDENT_EMAILS` from the dashboard: they are ignored, but keeping them is misleading. To rotate `SECRET_KEY` or `RESEND_API_KEY`, replace the value there the same way. A new `SECRET_KEY` signs everyone out.

**Known issue: Outlook puts the codes in Junk.** Gmail delivers them to the inbox. Outlook/Hotmail addresses currently receive them in the Junk folder, although SPF, DKIM and DMARC all pass there too: Microsoft's filter rates the new sending domain on reputation (spam confidence level 5), not on authentication. Someone signing in with an Outlook address should check Junk and mark the message *Not junk*. This must be solved before teachers and students sign in; see the result recorded under T072 in [`specs/004-email-otp-auth/tasks.md`](specs/004-email-otp-auth/tasks.md).

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
- Technical requirements: [`docs/requirements/technical-requirements.md`](docs/requirements/technical-requirements.md)
- Milestones: [`docs/requirements/milestones.md`](docs/requirements/milestones.md)
- UI guidelines: [`docs/requirements/ui-guidelines.md`](docs/requirements/ui-guidelines.md)

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
├── docs/requirements/       # Product & technical requirements, milestones
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
│   │   ├── security.py      # Pure helpers: email rules, codes, tokens, cookie signing, keyed hashes, safe return paths, the cross-site rule
│   │   ├── sealing.py       # seal/unseal: AES-256-GCM sealed links and notices (invitation, data deletion)
│   │   ├── log_redaction.py # AccessLogRedactor: link tokens and sealed values out of uvicorn's access log
│   │   ├── auth.py          # PUBLIC_ROUTES, ROLE_CHOICE_ROUTES, @allow_roles, the access dependency, CurrentUser/CurrentRole, the session cookie
│   │   ├── db.py            # Engine, per-request session, UTC timestamp column type
│   │   ├── migrations.py    # Expected (head) and current schema revision; startup guard
│   │   ├── theme.py         # The theme choice: Theme, the sc_theme cookie, read_theme, apply_theme
│   │   └── templates.py     # Shared Jinja2Templates instance (+ `current_user`, `current_role`, `user_roles`, `theme`, `theme_return` for every page, the `utc` filter, `template_error`)
│   ├── models/              # SQLModel tables: Question, BootCounter, User, UserRole, UserSession, LoginCode, RateLimitHit, Subject, Region, Institution, TeacherProfile and TeacherInstitution (teacher.py), ConsentText, ConsentRecord and InvitationCutoff (consent.py), SchoolClass (school_class.py, table `classes`), Enrolment
│   ├── schemas/             # Validation and view schemas: questions, login form input, names.py (shared name rules), people.py (person names, addresses), teachers.py (role details, the institution picker), classes.py (year of study), students.py (role details)
│   ├── routers/             # Route handlers grouped by area/role
│   │   ├── pages.py         # GET / → home page with the question list and status line
│   │   ├── auth.py          # GET/POST /login, POST /login/code, POST /logout
│   │   ├── roles.py         # GET/POST /role → choose or switch the current role
│   │   ├── areas.py         # /student, /staff placeholders (AREAS, /admin and /teacher included, drives the home links)
│   │   ├── teacher.py       # Teacher area shell: TEACHER_TABS, GET /teacher → Students, the Competitions placeholder
│   │   ├── teacher_students.py  # /teacher/students: the three lists, classes, inviting students, student edit and remove
│   │   ├── admin.py         # Administrator area shell: ADMIN_TABS, GET /admin → first tab
│   │   ├── admin_teachers.py  # /admin/teachers: list, invite, teacher page (edit), remove
│   │   ├── invitations.py   # /invitations/{token}: the acceptance page and I agree (public)
│   │   ├── profile.py       # /profile and /profile/withdraw (every role)
│   │   ├── data_deletion.py # /data-deletion…, /data-erased (public)
│   │   ├── admin_institutions.py  # /admin/institutions: regions and the selected region's institutions; create, rename, deactivate/activate, delete
│   │   ├── admin_subjects.py  # /admin/subjects: list, create, rename, deactivate/activate, delete
│   │   ├── admin_components.py  # GET /admin/components: the component gallery, outside production only (DevelopmentOnlyRoute)
│   │   ├── theme.py         # POST /theme: choose Light, Dark or Device (public)
│   │   └── health.py        # GET /healthz → status, version, commit
│   ├── services/            # Business logic: questions, subjects, regions, institutions, database_status, users, sessions, login, rate_limits, email; invitations (the generic invite/accept flow and the role registry), teachers, students (the student role, edit, move, remove), consent (texts, records, cut-offs, erasure), data_deletion; availability (the deactivation chain and usable roles), teacher_access (what a teacher may reach, Read or Write), classes
│   ├── templates/           # Jinja2: components/, layouts/, partials/ (HTMX fragments), pages/
│   │   ├── components/      # The component library: frame, button, card, table, badge, feedback, form, confirmation, details, selectors, icons, palette
│   │   ├── layouts/base.html  # The frame: skip link, top bar with the user menu (profile link, role switch, theme switch, Log out), main, footer
│   │   ├── layouts/admin.html # The administrator area's tab row, current tab marked
│   │   ├── layouts/teacher.html # The teacher area's tab row, current tab marked
│   │   └── pages/           # home, login, login_code, role_choice, area, error; invitation and invitation_status; profile, profile_withdraw; data_deletion_request, _requested, _confirm, link_status, data_erased; admin/ (placeholder; subjects; institutions and regions; teachers, teacher_invite, teacher_form, teacher_remove, teacher_not_found, _institution_picker, _person_names; region and institution deactivation confirmations); teacher/ (students, class_form, class_deactivate, class_delete, student_invite, student_form, student_remove, placeholder)
│   └── static/              # css/ (vendored pico.min.css + app.css: tokens, Pico mapping, components), fonts/ (Open Sans, OFL), js/, img/ (favicons)
├── migrations/              # Alembic migrations
│   ├── env.py               # Uses resolve_database_url; one locked transaction on PostgreSQL
│   └── versions/            # Revisions: tables + boot counter, the sample questions, the sign-in tables, user roles, drop the unused users.role, subjects, regions and institutions, consent and teachers (+ the teacher consent text v1), the one-time retirement of the role lists, classes and enrolments (+ the student consent text v1)
├── data/                    # Local SQLite database (git-ignored, created by the first migration)
├── tests/                   # unit/, integration/, e2e/ (Playwright); html.py queries rendered pages by meaning
│   ├── conftest.py          # Both-engine database fixtures (template + clone), the cast (`seed_roles_directly`), `client`, `client_as`, `admin_client`, `outbox`; `make_institution`, `invite`, `invite_and_accept`, `make_teacher`, `token_from`; `make_class`, `invite_student`, `enrol_student`
│   ├── unit/                # config, database and auth settings, security helpers, sealing, log redaction, safe return paths, the cross-site rule, email, templates, schemas (names, people, teachers, classes), pinned consent texts
│   └── integration/         # teacher area classes and students, student invitation and refusals, names on acceptance, availability (chain and service), teacher access (service and route sweeps), classes service, teacher invitation, refusals, cut-offs and edge cases, admin teachers, profile, data deletion, self-invitation, consent privacy and service, admin area, subjects and institutions, subject, region and institution services, access control, role choice and switch, cross-site, login flow and privacy, sessions, user reconcile, auth services, home, health, routes, startup, migrations, boot counter, question service
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
