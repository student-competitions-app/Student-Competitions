# Technical Requirements

## Technology Stack

| Area | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-side rendering: Jinja2 + HTMX + Pico.css |
| Database | SQLite locally, PostgreSQL in production, via SQLModel + Alembic |
| Authentication | Email code (OTP) + server-side sessions in a signed cookie |
| Answer evaluation | LLM API call (Claude or OpenAI) with structured output |
| Infrastructure & deployment | Docker + Render (or Railway / Fly.io) |
| Tooling & tests | uv, ruff, pytest, later Playwright |
| Development process | GitHub Spec Kit |

## Milestones

The ladder follows a "walking skeleton" approach: first ship an empty skeleton to the internet, then grow it with vertical slices. Each step ends with a working, testable and meaningful result.

1. **Hello World locally.** FastAPI serves a single HTML page via Jinja2.
   _Test:_ the application starts, the page opens, there is a first pytest test for the endpoint.

2. **Deploy Hello World to the internet + CI/CD.** Dockerfile, deployment to Render, public URL. GitHub Actions runs tests and linting on PRs, auto-deploy on push to `main`.
   _Test:_ the page is accessible from outside, the pipeline is green.

3. **Database + first entity.** Connect the database (SQLite locally, Postgres in production) with Alembic migrations. Create the "Question" model with a CRUD layer covered by tests (no write endpoints, since there is no authentication yet). The public page shows a read-only list of seeded sample questions and a database status line (database type, migration revision, boot count).
   _Test:_ CRUD tests pass on SQLite and Postgres in CI; in production, the sample questions are visible and the boot count increases across a redeploy.

4. **Email code authentication.** Email input form → code sent to email → code verification → session.
   _Email delivery:_ the auth flow sends email through a small email-sender interface and never knows how the message is delivered. The backend is selected by the `EMAIL_BACKEND` environment variable:
   - `console` (local default): prints the full email, including the code, to the server console. No mail provider account or keys are needed for local development.
   - `memory` (tests): keeps sent messages in an in-memory outbox, so tests read the code from it and run the real flow end to end.
   - `resend` (production): the Resend HTTP API, not SMTP, since free hosting tiers may block outbound SMTP. The sending domain is verified with SPF/DKIM records.

   On Render, the application refuses to start with the `console` backend, following the same pattern as `DATABASE_URL`. There are no login bypasses (magic codes, dev-only login URLs). Only the console backend may output the message body. Tests of role-protected pages in later milestones use a fixture that creates a session directly and skip the email step.
   _Site administrators:_ there is no sign-up. Only active users already in the database can log in, and an unknown email receives no code. SRE manages administrators through the `ADMIN_EMAILS` environment variable: a comma-separated list, declared in `render.yaml` with `sync: false`. On startup, after migrations, the application reconciles the users table with this list. Every listed email (trimmed and lowercased) gets an active administrator user. Administrators missing from the list are deactivated and their sessions deleted. The step is idempotent and logs only counts. On Render, the application refuses to start if `ADMIN_EMAILS` is empty or contains a malformed email. The UI cannot grant or revoke administrator rights. This milestone has no role-based checks; milestone 5 adds them on top of this flow.
   _Access:_ every page is protected by default, including the existing home page. Routes are public only if they are on an explicit allowlist: login, logout, `/healthz` and `/static`. An anonymous request to a protected page redirects (303) to `/login?next=…`, and `next` is accepted only as a relative path.
   _UI (minimal):_ a two-step login page (email, then code) using plain forms that redirect after submit, with no HTMX. The header shows the signed-in email and a **Log out** button that submits a POST form. The home page content is unchanged.
   _Sessions:_ stored server-side in a `sessions` table. The cookie carries a random token signed with `SECRET_KEY`, and the database stores only the token's hash. Every request checks that the session is unexpired and the user is still active. Sessions expire after 14 days, and expired sessions and codes are cleaned up.
   _Security:_ codes are hashed with HMAC keyed by `SECRET_KEY`, single-use, and expire after about 20 minutes. Attempts per code and code requests per email are rate-limited, with counters stored in the database. Between the two steps, the email travels in a hidden form field. Known and unknown emails get the same response, and the email is sent in a background task so response timing does not reveal which emails are registered. The session cookie is `HttpOnly`, `SameSite=Lax` (sufficient against CSRF for this milestone), and `Secure` in production.
   _Configuration:_ `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY` and `EMAIL_FROM` are declared in `render.yaml` with `sync: false`. On Render, the application refuses to start if any of them is missing. Startup order: migration check, then admin reconcile, then boot count. The `users` table has a `role` column (only `admin` for now); milestone 5 may change how roles are stored.
   _Rollout:_ the Resend domain's DNS records at NIC.UA and the Render secrets are in place before merging to `main`.
   _Test:_ a user can log in end to end, reading the code from the `memory` outbox. A route-table test asserts that every route outside the allowlist rejects anonymous requests. Existing page tests use a fixture that creates a session directly. Unknown and known emails get the same response. Running the reconcile twice changes nothing. An email removed from `ADMIN_EMAILS` can no longer log in and loses its sessions.

5. **Roles and authorization.** Three roles: student, teacher and administrator. Each page is open only to the roles allowed to see it. The aim is the complete role flow, kept simple: the role pages are placeholders with no features behind them.
   _Who has which role:_ the lists of administrators, teachers and students are all set via configuration at deploy time, the same way administrators are set today. One person can be on several lists and so have several roles. A person on no list cannot log in. Removing a person from a list takes effect at once: they are logged out everywhere. The teacher and student lists are temporary; milestone 7 replaces them with managing teachers and students in the application.
   _Choosing a role:_ a person with one role gets it right after login. A person with several roles chooses one after login, and then lands on the page they originally asked for. Until a role is chosen, no other page opens. A person with several roles can switch role at any time from the header without logging out.
   _Access:_ what a person can open depends on the role they are currently using, not on all the roles they have. For example, someone who is both an administrator and a student cannot open administrator pages while using the student role. Opening a page the current role is not allowed to see shows an "access denied" page. Every new page must state which roles can open it.
   _Pages:_
   - The home page is open to all roles. Its content is unchanged, plus links to only the pages the current role can open.
   - One placeholder page per role (administrator, teacher, student), each open only to that role.
   - One placeholder page for staff, open to administrators and teachers but not to students.
   - Every page shown after a role is chosen displays the current role in the header, next to the application name in the top left corner.

   _Out of scope:_ managing users, educational institutions or profiles in the application, and any real functionality for a role beyond its placeholder page.
   _Test:_
   - Each role can open exactly the pages it is allowed to and sees "access denied" on the others.
   - The home page shows each role only its own links.
   - A person with several roles is asked to choose one after login, and a person with one role is not.
   - Someone who is both an administrator and a student, using the student role, cannot open the administrator page.
   - A person removed from a list is logged out, and a person removed from every list can no longer log in.

6. **Question bank (teacher).** Uploading a list of questions, viewing, editing, reference answers for questions.
   _Test:_ question CRUD works and is visible only to teachers.

7. **User management.** A teacher adds students (email, first name, last name, educational institution, year, group). An administrator manages teachers and students. Profiles for all roles.
   _Test:_ users are created, profiles are edited.

8. **Creating a competition (teacher).** A competition with a start time, duration, assignment to a group/students, a set of questions from the bank and reference answers.
   _Test:_ a competition is created and correctly linked to questions and participants.

9. **Taking a competition (student).** List of assigned competitions, enforcement of the time window and duration, entering and submitting text answers.
   _Test:_ answers are saved; the competition is not accessible outside its time window.

10. **Answer evaluation via LLM.** Each answer receives a score of 1–10 that takes level of detail into account; results are saved to the database.
    _Test:_ evaluation returns a structured result and it is persisted.

11. **Best answer selection + results.** For each question, the best answer is selected from the group's answers; competition results are saved and displayed.
    _Test:_ the best answer is determined, the results page works.

12. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)
