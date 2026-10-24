# Student Competitions Constitution

## Core Principles

### I. Walking Skeleton & Vertical Slices

The product is built as a "walking skeleton" that grows by vertical slices, following the
milestone ladder in `docs/requirements/milestones.md`.

- Milestones MUST be delivered in order; a milestone MUST NOT start until the previous one is
  merged, deployed and its acceptance test passes.
- Each milestone is one Spec Kit feature (`specs/NNN-feature-name/`) on its own branch and MUST
  end in a working, testable, user-meaningful result — never a horizontal layer
  (e.g. "all models first") without a usable path through the UI.
- The `main` branch MUST always be deployable; from milestone 2 onward every merge to `main`
  auto-deploys to production.
- Work beyond the current milestone's scope MUST be deferred to a later spec, not smuggled in.

**Rationale**: Shipping an end-to-end path early exposes integration, deployment and hosting
problems while they are cheap to fix, and keeps every step demonstrable.

### II. Server-Rendered Simplicity

The UI is server-rendered with Jinja2, made interactive with HTMX and styled with Pico.css.

- Pages MUST be rendered on the server; interactivity MUST use HTMX partials
  (`app/templates/partials/`) returning HTML fragments, not JSON consumed by client code.
- Custom JavaScript MUST be minimal and MUST NOT require a build step (no bundlers, no SPA
  framework). The optional React migration in milestone 16 requires a constitution amendment.
- Every feature MUST use the stack defined in Technology & Architecture Constraints →
  Technology Stack. Adding a new runtime dependency MUST be justified in the feature's `plan.md`.
- Prefer the simplest design that satisfies the spec (YAGNI); abstractions MUST have at least
  one concrete present need.
- Every page MUST be built from the component library in `app/templates/components/` and MUST
  follow the UI guidelines in `docs/requirements/ui-guidelines.md` (design tokens only, the
  shared page frame, the button kinds, the wording patterns). A new UI pattern MUST first be
  added to the component library, the component gallery (`/admin/components`) and the
  guidelines, and only then used; it MUST NOT be hand-built on a single page.

**Rationale**: A small team and a small user base (competitions of ~10 students) do not justify
SPA complexity; SSR + HTMX keeps one language, one codebase and one deployment unit. One
component library and one set of guidelines keep every page calm, readable and consistent for
students from year 1 to university, and stop each milestone from inventing its own look.

### III. Test-Backed Delivery (NON-NEGOTIABLE)

- Every feature MUST ship with automated pytest tests that verify the milestone's stated
  acceptance criterion ("_Test:_" line in the milestones document) and the spec's
  acceptance scenarios.
- Tests live in `tests/unit/` (pure logic, services), `tests/integration/` (HTTP routes via
  the FastAPI test client, database, auth flows) and `tests/e2e/` (Playwright, from
  milestone 16).
- Every protected route MUST have tests proving both allowed and denied access per role.
- Tests MUST NOT call real external services: the LLM provider and the email sender MUST be
  replaced by fakes/stubs in the test suite.
- A bug fix MUST include a regression test that fails before the fix.
- CI (tests + `ruff check` + `ruff format --check`) MUST be green before a PR is merged.

**Rationale**: Each milestone is defined by a test; automated verification is what makes
continuous deployment of `main` safe.

### IV. Role-Based Access & Data Scoping (NON-NEGOTIABLE)

The application has three roles — student, teacher, administrator — with rights defined in
`docs/requirements/product-requirements.md`.

- Authorization MUST be enforced server-side on every route and every service operation
  (reusable FastAPI dependencies); hiding a link in a template is never sufficient.
- Access MUST be deny-by-default: a route without an explicit role requirement is a defect.
- Teachers MUST only see and manage students of the educational institutions they are linked
  to; only administrators can link teachers to institutions and edit the institution list.
- Competition rights MUST follow the product rules: every teacher can read all competitions;
  only the creator (and teachers the creator grants edit rights) can edit one; only upcoming
  competitions are editable.
- Students MUST only access their own profile (read-only), their own answers and results,
  and competitions they are assigned to.
- The administrator list MUST come from deployment configuration, not from the UI.

**Rationale**: The system holds personal data of students and competition results; a single
missing check leaks data or allows score tampering.

### V. Secure Authentication & Secrets

- Login is by email one-time code (OTP) only; no passwords are stored.
- OTP codes MUST be single-use, short-lived, stored hashed, and rate-limited per email and
  per client to prevent brute force and email flooding.
- Sessions MUST be server-side, referenced by a signed cookie that is `HttpOnly`, `Secure`
  in production, and `SameSite=Lax` or stricter; logout MUST invalidate the server session.
- State-changing requests (including HTMX requests) MUST be protected against CSRF.
- Secrets (session key, database URL, LLM and email API keys, admin list) MUST come from
  environment variables and MUST NOT be committed to the repository.
- Logs MUST NOT contain OTP codes, session identifiers, API keys or full student answers.

**Rationale**: Email OTP moves the security boundary to code handling and session management;
these rules close the common gaps.

### VI. Trustworthy LLM Evaluation

- The LLM provider (Claude or OpenAI) MUST be accessed only through a single service in
  `app/services/` behind a provider-agnostic interface, so the provider can be switched by
  configuration.
- Evaluation MUST use structured output validated against a Pydantic schema in
  `app/schemas/`; the score MUST be an integer from 1 to 10 and MUST account for the level
  of detail, with the question text and the teacher's reference answer as inputs.
- Student answers MUST be treated as untrusted input: clearly delimited in the prompt and
  never able to alter scoring instructions (prompt-injection resistance).
- Evaluation failures (timeouts, invalid output, provider errors) MUST NOT lose or corrupt a
  submitted answer; the answer stays persisted with an explicit pending/failed status and can
  be re-evaluated.
- Each stored evaluation MUST record the score, the model's justification and the model
  identifier used, so results are auditable.
- LLM calls MUST NOT run inside the request that saves a student's answer; answer submission
  MUST succeed independently of the LLM being available.

**Rationale**: Scores decide winners; they must be reproducible, explainable and resilient to
provider outages and manipulation.

### VII. Data Integrity & Migrations

- All tables are defined with SQLModel in `app/models/`; every schema change MUST be an
  Alembic migration in `migrations/` — no `create_all()` in production paths.
- Code and migrations MUST run on both SQLite (local/tests) and PostgreSQL (production);
  database-specific features require justification in `plan.md`.
- All timestamps MUST be stored timezone-aware in UTC and converted only for display.
- Competition time windows (start time + duration) MUST be enforced server-side on every
  read of questions and every answer submission.
- Results (scores, totals, places, best answers) MUST be persisted, and deletions MUST NOT
  silently orphan or destroy historical competition results.

**Rationale**: Competition results are the product's core record; they must survive restarts,
deployments and database engine changes.

## Technology & Architecture Constraints

### Technology Stack

The stack is taken from the "Technology Stack" table in
`docs/requirements/technical-requirements.md` and the milestone ladder in
`docs/requirements/milestones.md`, and is binding for every spec and plan. The "Milestone"
column shows when each component enters the codebase.

| Area | Technology | Binding rules | Milestone |
|---|---|---|---|
| Language & web framework | Python + FastAPI | One FastAPI application serves all pages and HTMX fragments. | 1 |
| Templating | Jinja2 | Every page is rendered on the server (Principle II). | 1 |
| Interactivity | HTMX | Partial updates return HTML fragments from `templates/partials/`, never JSON for the UI. | 1+ (as needed) |
| Styling | Pico.css v2 | Restyled only by overriding its CSS variables with the design tokens in `static/css/app.css`; Pico's own stylesheet is not edited; no CSS build step; fonts self-hosted in `static/fonts/`; nothing loaded from another site. Pages follow `docs/requirements/ui-guidelines.md` (Principle II). | 1 (tokens and components from 10) |
| Dependency & environment management | uv | `pyproject.toml` + committed `uv.lock`; no pip/poetry/requirements files. | 1 |
| Lint & format | ruff | `ruff check` and `ruff format` are the only linter/formatter; enforced in CI from milestone 2. | 1 |
| Unit & integration tests | pytest | Every milestone's "_Test:_" criterion is an automated pytest test (Principle III). | 1 |
| Containerization | Docker | One image for the whole application, configured only via environment variables. | 2 |
| Hosting | Render (default); Railway or Fly.io are approved alternatives | The chosen host is recorded in milestone 2's `plan.md`; switching between listed hosts needs no amendment. | 2 |
| CI/CD | GitHub Actions | Tests + lint run on every pull request; every push to `main` auto-deploys. | 2 |
| ORM / models | SQLModel | All tables are SQLModel models in `app/models/` (Principle VII). | 3 |
| Migrations | Alembic | Every schema change is an Alembic migration in `migrations/`. | 3 |
| Database | SQLite (local development, tests) → PostgreSQL (production) | The same code and migrations run on both engines. | 3 |
| Authentication | Email one-time code (OTP) + server-side sessions in a signed cookie | No passwords, no third-party identity provider (Principle V). | 4 |
| Authorization | Roles: student / teacher / administrator; administrator list from deploy-time configuration | Enforced server-side, deny-by-default (Principle IV). | 5 |
| Answer evaluation | LLM API (Claude or OpenAI) with structured output | Behind one provider-agnostic service; provider chosen by configuration (Principle VI). | 14 |
| End-to-end tests | Playwright | Added "later", as part of polish and hardening; lives in `tests/e2e/`. | 16 |
| Development process | GitHub Spec Kit | Every feature goes through the Spec Kit flow (see Development Workflow). | all |

**Stack rules**:

- A component MUST be introduced in the milestone listed above, or later. Introducing it
  earlier MUST be justified in that feature's `plan.md` (Principle I).
- Background work, such as LLM evaluation (Principle VI), MUST use what the stack already
  provides: FastAPI background tasks, or pending records in the database processed by the
  application. External brokers or workers (e.g. Redis, Celery) are not part of the stack.
- Server-side session and OTP state MUST be stored in the application database, not in new
  infrastructure.
- The milestone-16 stretch goal of moving part of the UI to React is **not** approved. Adopting
  it requires a constitution amendment (Principle II).
- Choosing between alternatives the table already lists (Render / Railway / Fly.io;
  Claude / OpenAI) needs no amendment, but the choice MUST be recorded in the relevant
  `plan.md`. Replacing a listed technology or adding a new stack category is an amendment
  (see Governance).

**Open stack decisions**: the technical requirements do not settle these. Each MUST be
decided and recorded in the `plan.md` of the named milestone, within the rules above:

| Decision | Decide in milestone |
|---|---|
| Python version (pinned via `.python-version` / `requires-python`) | 1 |
| Hosting provider (Render unless justified) and managed PostgreSQL offering | 2 |
| Email delivery service (SMTP or transactional-email API) for sending OTP codes | 4 |
| LLM provider and model for answer evaluation | 14 |

### Application Layout

The `app/` layout below MAY be refined by `/speckit-plan` but MUST NOT be bypassed:

- `core/` — settings (loaded from environment), security, sessions, database engine.
- `models/` — SQLModel tables only.
- `schemas/` — request/response models and LLM structured-output schemas.
- `routers/` — thin HTTP handlers grouped by area/role: parse input, check authorization,
  call a service, render a template. Business logic MUST NOT live in routers or templates.
- `services/` — business logic (competitions, scoring, users, email, LLM); independently
  unit-testable.
- `templates/` — `components/` (the component library: Jinja macros shared by every page),
  `layouts/`, `pages/`, `partials/` (HTMX fragments).
- `static/` — `css/`, `fonts/` (self-hosted fonts and their licence), `js/`, `img/`.

### Operational Constraints

- The application MUST run from a single Docker image configured solely via environment
  variables; migrations MUST be applied as part of deployment.
- User-facing errors MUST render a friendly page or HTMX fragment; stack traces MUST NOT be
  shown to users in production.

## Development Workflow & Quality Gates

1. **Spec Kit flow**: `/speckit-specify` → (`/speckit-clarify`) → `/speckit-plan` →
   `/speckit-tasks` → (`/speckit-analyze`) → `/speckit-implement`. Specs describe what and why;
   plans describe how and MUST pass the Constitution Check gate.
2. **Branching**: one feature branch per spec, named `NNN-feature-name`, merged into `main`
   only via pull request.
3. **Pull request gates** — a PR MUST NOT be merged unless:
   - CI is green: `ruff check`, `ruff format --check`, full pytest suite;
   - new or changed routes include role-access tests (Principle IV);
   - schema changes include an Alembic migration (Principle VII);
   - the milestone's acceptance test is automated and passing (Principle III);
   - no secrets or credentials are included in the diff (Principle V).
4. **Deployment**: merges to `main` auto-deploy via GitHub Actions (from milestone 2). A failed
   deployment MUST be fixed or reverted before new feature work merges.
5. **Documentation**: README and requirements docs MUST be updated in the same PR when a
   feature changes setup steps, configuration variables or documented behavior.

## Governance

- This constitution supersedes other project practices and conventions. Where a spec, plan or
  task conflicts with it, the constitution wins until it is amended.
- **Amendments** are made via `/speckit-constitution` in a dedicated pull request that states
  the change, its rationale and any migration impact on existing specs or code.
- **Versioning** follows semantic versioning:
  - MAJOR — removal or backward-incompatible redefinition of a principle, or replacement of
    a technology in the stack (e.g. another web framework, ORM, production database or
    frontend framework);
  - MINOR — a new principle or section, a new stack category, or materially expanded
    guidance;
  - PATCH — clarifications, wording and typo fixes.
- **Compliance**: every `plan.md` MUST include a Constitution Check; any deviation MUST be
  recorded in its Complexity Tracking table with justification and the simpler alternative
  rejected. From milestone 11 the Constitution Check MUST include a **UI guidelines** row: the
  feature's pages are built from the component library, use design tokens only, follow
  `docs/requirements/ui-guidelines.md`, and any new pattern is added to the library, the
  gallery and the guidelines first. Reviewers MUST verify PRs against the Quality Gates above.
- Runtime development guidance lives in `README.md` and `docs/requirements/`; those documents
  MUST NOT contradict this constitution.

**Version**: 1.1.0 | **Ratified**: 2026-09-18 | **Last Amended**: 2026-10-24
