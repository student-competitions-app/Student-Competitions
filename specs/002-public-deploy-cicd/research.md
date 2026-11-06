# Research & Decisions: Public Deployment & CI/CD (Milestone 2)

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](./plan.md)

Every decision this milestone needs, with the alternative that was rejected and why. Three
decisions were fixed by the user's instruction to `/speckit-plan` and are recorded here as
constraints rather than open choices: **Render's free plan** as the host (D1), **a deploy hook**
rather than Render's repository auto-deploy (D2), and **infrastructure as code wherever the
platform allows it** (D3).

Render behaviour below was checked against Render's documentation on 2026-09-22; the source page
is named in each *Evidence* line. Where the documentation does not settle a point, it says so.

---

## D1 — Hosting platform and plan

**Decision**: Render, **free instance type**, one `web` service, region `frankfurt`, built from
the repository's `Dockerfile`. The public address is the service's automatic
`https://<service-name>.onrender.com` subdomain; no custom domain.

**Rationale**:

- The constitution's stack table names Render as the default host and requires only that the
  choice be recorded in this plan; Railway and Fly.io were the approved alternatives.
- The free instance type covers this milestone's payload completely: one stateless HTTP service,
  512 MB RAM and 0.1 CPU, no persistent disk (milestone 2 has no database — FR-030), managed TLS
  on the `onrender.com` subdomain (FR-003), and automatic restarts (FR-006).
- `frankfurt` is the closest of Render's five regions (`oregon`, `ohio`, `virginia`, `frankfurt`,
  `singapore`) to the team, which matters for SC-002's 3-second warm page load. The region is one
  line in `render.yaml` and is set at creation time — Render cannot move a service between regions
  afterwards, so it is worth getting right once.

**Consequences accepted** (all of them already allowed by the spec's *Assumptions*):

| Free-plan property | Effect on this milestone |
|---|---|
| Spins down after 15 minutes without inbound traffic; ~1 minute to spin back up | The first request after idling is slow. The spec excludes this from SC-002 explicitly ("measures a warm request") and the edge-case list accepts it. |
| 750 free instance-hours per workspace per month | One always-idling service is far inside the budget. |
| Single instance, no scaling | Nothing in this milestone needs more; SC-003's 99% target is about the service being up, not about capacity. |
| Ephemeral filesystem | Nothing is written at runtime. It becomes a real constraint in milestone 3, which is why the database is managed Postgres, not a file. |
| No shell/SSH access on free instances | Debugging is by logs and by `/healthz`. This is the reason `/healthz` reports the commit (D7) rather than relying on an interactive check. |

**Zero-downtime deploys — what is and is not guaranteed**: Render's deploy documentation
describes the general sequence — build, start a new instance while the old one keeps serving
traffic, switch over only once the new instance passes its health check, then `SIGTERM` the old
one — and states that a failed build "cancels immediately" with "your original service instance
continues running without interruption". It does **not** state whether the free instance type gets
the same overlap, and free services are explicitly single-instance. So:

- **SC-008 (a broken publish leaves the previous version serving) is satisfied regardless**: a
  failed build, a failed image start or a health check that never passes all end with the deploy
  marked failed and the old version still in place.
- **A *successful* free-tier deploy may involve a brief restart window** rather than a true
  hand-off. At a milestone whose audience is "the team and reviewers" (spec *Assumptions*) and
  whose service idles anyway, a few seconds of unavailability on a deliberate release is
  acceptable and is not asserted anywhere in the success criteria. If it ever matters, the fix is
  a paid instance type — a one-line `plan:` change in `render.yaml`, no code change.

**Alternatives considered**:

- **Railway / Fly.io** — both approved by the constitution. Rejected: Render is the stated
  default, and neither offers an advantage for a single free stateless container. Fly.io's model
  (its own `fly.toml`, `flyctl` in CI, machine-level control) is a better fit for later scaling
  but adds a CLI and an auth token to the pipeline now.
- **A paid Render instance** (no spin-down, guaranteed zero-downtime). Rejected: the user
  specified the free plan, and the spin-down cost is explicitly accepted by the spec.
- **A custom domain**. Rejected: the spec puts it out of scope and marks the platform address
  sufficient.

**Evidence**: Render docs — *Free instance types*, *Compute plans*, *Blueprint YAML reference*
(`region` allowed values), *Deploys* (zero-downtime sequence, failed-build behaviour).

---

## D2 — What triggers a deploy: GitHub Actions calling a Render deploy hook

**Decision**: Render's own auto-deploy is **off** (`autoDeployTrigger: "off"` in `render.yaml`).
The only thing that deploys the service is the `deploy` job of `.github/workflows/deploy.yml`,
which runs after the checks pass on `main` and sends a request to the service's **deploy hook**
URL with the exact commit pinned:

```text
POST ${RENDER_DEPLOY_HOOK_URL}&ref=<full 40-character commit SHA>
```

The hook URL already carries a `key=` query parameter, so the `ref` is appended with `&`, not `?`.
It is held in the repository secret `RENDER_DEPLOY_HOOK_URL` (D12).

**Rationale**:

- It is what the user asked for, and it is also the only arrangement that can satisfy **FR-021**
  ("publishing MUST only proceed if the automated tests and style checks pass for the commit being
  published"). With Render's plain repo auto-deploy, Render sees the push and starts building
  immediately, in parallel with CI — a commit that fails its tests would still reach the public
  address. Render's `autoDeployTrigger: "checksPass"` is the platform's answer to that, but it
  makes the release condition a setting in Render's UI/YAML interpreted against GitHub's check
  API, instead of an explicit, reviewable step in a workflow file. The deploy hook keeps the whole
  release rule in the repository: *tests → lint → image smoke test → deploy → verify*.
- `ref=<sha>` makes the release **commit-addressed**. Without it, the hook deploys "whatever the
  branch points at now", which is a race: two merges in quick succession could both resolve to the
  same (or the wrong) tree. Pinning the SHA is what makes FR-024's "the newest commit wins"
  checkable — the deployed commit is reported back by `/healthz` (D7) and compared against
  `github.sha` before the job is allowed to succeed (D15).
- The hook is credential-scoped to exactly one action on one service. It cannot read the repo,
  cannot change service configuration and cannot reach any other resource in the Render workspace
  — a much smaller blast radius than a Render API key (FR-027).

**What "no repo integration" does and does not mean here**: Render still needs read access to the
GitHub repository, because Render is the thing that runs `docker build` (D4) and because the
Blueprint is read from `render.yaml` in the repo (D3). What is switched off is Render's
*automatic deploy on push*. Render never decides on its own when to release; it only responds to
the pipeline's hook call.

**Response codes the pipeline must handle** (from Render's deploy-hook documentation):
`200` deploy started, `202` another deploy is in progress and this one is queued, `401` bad or
missing key, `404` service or commit SHA not found, `400` invalid parameters. Only `200` and `202`
are success; everything else fails the job loudly (FR-027's "fails loudly" edge case, FR-023).

**Alternatives considered**:

- **Render repo auto-deploy on push to `main`** (`autoDeployTrigger: "commit"`). Rejected: cannot
  gate on tests, as above. This is the arrangement the user explicitly asked to avoid.
- **`autoDeployTrigger: "checksPass"`**. Rejected: it does gate on checks, but it moves the
  release decision out of the repository, gives no place to verify the result afterwards, and is
  not a deploy hook.
- **Render REST API (`POST /v1/services/{id}/deploys`) with an API key**. Rejected: a workspace-
  wide API key is a far broader secret than a per-service hook, for no benefit — the hook already
  accepts the commit SHA. Revisit only if the pipeline ever needs to *read* deploy status
  programmatically, which D15 avoids by polling the application itself.
- **`render deploy` via Render's CLI in the workflow**. Rejected: another tool and another
  workspace-scoped token in CI, same outcome.

**Evidence**: Render docs — *Deploy hooks* (GET/POST, `ref` parameter, response codes),
*Blueprint YAML reference* (`autoDeployTrigger` replaces the deprecated `autoDeploy`; values
`commit`, `checksPass`, `off`).

---

## D3 — Infrastructure as code: `render.yaml` Blueprint

**Decision**: the Render service is declared in a committed **`render.yaml` Blueprint** at the
repository root and created in Render as a Blueprint instance. Everything Render lets a Blueprint
express lives there: service type, name, runtime, plan, region, branch, Dockerfile path, health
check path, deploy trigger, and non-secret environment variables. Blueprint **Auto-Sync stays on**,
so a merged change to `render.yaml` becomes the live configuration without anyone touching the
dashboard.

Three things are, by the platform's design, **not** expressible in the Blueprint and are therefore
done once by hand and documented in [quickstart.md](./quickstart.md):

| Manual step | Why it cannot be code | Where it is recorded |
|---|---|---|
| Creating the Render account/workspace and connecting the GitHub repository | Requires an interactive OAuth grant | quickstart §Setup |
| Creating the Blueprint instance the first time ("New → Blueprint") | Bootstrap: Render has to be told which repo/branch/file to read | quickstart §Setup |
| Copying the generated deploy hook URL into the GitHub secret | The URL only exists after the service exists | quickstart §Setup |

Everything after that bootstrap is repository state.

**Rationale**: the point of the Blueprint is not to save clicks once, it is that the service's
configuration is reviewed in a pull request, versioned with the code it configures, and restorable
— a deleted service can be recreated from `render.yaml` in minutes. It also makes the health check
path, the region and the free plan visible to the next reader instead of hidden in a dashboard.

**Two traps, both already handled in the design**:

1. **`autoDeployTrigger: "off"` must be quoted.** YAML 1.1 parses a bare `off` as the boolean
   `false`; Render expects the string. The file uses `"off"`.
2. **A Blueprint sync redeploys affected services.** Render's documentation states it
   "automatically redeploys any affected services to apply the new configuration" when the
   Blueprint changes. That is a deploy this pipeline did not trigger — acceptable, because it only
   happens for a commit already merged to `main` (i.e. already checked), and the deploy workflow
   runs for that same commit anyway. It is noted in the quickstart so a doubled deploy after a
   `render.yaml` change is not mistaken for a fault.

**Also as code, outside Render**: the two GitHub Actions workflow files and the reusable checks
workflow (D9), the `Dockerfile` and `.dockerignore` (D5), and the two pipeline shell scripts
(`scripts/render_deploy.sh`, `scripts/wait_for_release.sh`) that the workflow calls, so that every
release action can also be run by hand from a terminal — which is exactly what makes the rollback
procedure a one-liner (D11).

**Alternatives considered**:

- **Terraform / OpenTofu with the Render provider**. Rejected: it would introduce a new stack
  category (the constitution's Governance section calls that an amendment), a state file to store,
  and a second source of truth for the same service — for one free web service. `render.yaml` is
  Render's own native IaC and costs nothing.
- **Configuring the service by hand in the dashboard**. Rejected: no review, no history, no
  restore, and the user asked for IaC.
- **Blueprint Auto-Sync off, with manual syncs.** Rejected: it would make the committed file a
  document rather than the configuration, which defeats the purpose. Auto-Sync applies only to
  *configuration*; code deploys stay off (D2).

**Evidence**: Render docs — *Infrastructure as code (Blueprints)* (creation flow, auto-sync,
redeploy on sync, Auto-Sync setting), *Blueprint YAML reference*.

---

## D4 — Where the image is built: on Render, from the repository

**Decision**: Render builds the Docker image itself from the `Dockerfile` at the commit named by
`ref`. CI **also** builds the image, but as a verification step (and to smoke-test it), not to
publish an artifact. No container registry is involved.

**Rationale**:

- No registry account, no registry credentials on Render, no image retention policy, no extra
  secret — at a milestone whose stated scope guard is "no external service integration" (FR-030).
- Reproducibility comes from the inputs being pinned, not from the bytes being copied: the same
  commit, the same `uv.lock` (installed with `uv sync --locked`), the same pinned base images. CI
  building the image from the same `Dockerfile` on every pull request means a Dockerfile that
  cannot build never reaches `main`, so "it built in CI but not on Render" is a near-empty case.
- Render's free build minutes are generous and the image is small (D5).

**The honest trade-off**: FR-011 says "the same package is what gets published". With this
decision the *recipe* and the *inputs* are identical and CI proves the recipe works, but the bytes
Render runs were produced by a second build. A bit-identical guarantee needs D4's alternative:

- **Alternative — build in CI, push to GHCR, point Render at the image** (`runtime: image` plus
  `imgURL=` on the deploy hook). Rejected for now: it adds a registry, registry credentials stored
  in Render, image visibility/retention decisions and a second place where the release can fail —
  all to close a gap that pinned inputs already make very small. It is the natural upgrade if the
  build ever becomes slow or non-deterministic; the deploy hook supports it with a query parameter,
  so the pipeline shape would not change.
- **Alternative — Render's native Python runtime instead of Docker**. Rejected: the constitution
  puts Docker in the stack at milestone 2 and requires "a single Docker image for the whole
  application", and FR-008/FR-011 want one self-contained unit that runs the same locally and in
  production. Render's buildpack cannot be run on a developer's machine.

**Evidence**: Render docs — *Deploy hooks* (`imgURL` for image-backed services), *Blueprint YAML
reference* (`runtime: docker`, `dockerfilePath`, `dockerContext`).

---

## D5 — Image design

**Decision**: a two-stage `Dockerfile`.

- **Builder**: `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` — uv's own image, so uv does not
  have to be installed or downloaded. It copies only `pyproject.toml` and `uv.lock`, then runs
  `uv sync --locked --no-dev --no-install-project` to build `/app/.venv` in a cache-friendly
  layer, with `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy` and `UV_PYTHON_DOWNLOADS=never`.
- **Runtime**: `python:3.13-slim-bookworm` — same Python minor version, same Debian release as the
  builder, so the copied virtualenv is valid. It receives `/app/.venv` and `app/`, nothing else:
  no uv, no compiler, no tests, no `.git`.
- Runs as a **non-root** user; `PATH` puts the venv first; `PYTHONUNBUFFERED=1` so Render's log
  stream is live.
- `ARG APP_COMMIT=""` → `ENV APP_COMMIT=$APP_COMMIT` lets a local or CI build stamp the commit
  (D7). An empty value is falsy, so on Render the `RENDER_GIT_COMMIT` fallback still wins.
- **Entrypoint**:
  ```dockerfile
  CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
  ```
  `sh -c` because the exec form does not expand `${PORT}`, and **`exec`** because without it the
  shell stays PID 1, does not forward `SIGTERM`, and every deploy ends with uvicorn being
  `SIGKILL`ed after Render's grace period instead of shutting down cleanly.
- A `HEALTHCHECK` using `python -c` against `/healthz` (no `curl` in the image). Render does not
  use Docker's healthcheck — it uses `healthCheckPath` (D7) — but it makes `docker run` locally
  behave like production and gives the CI smoke test something to wait on.

**Rationale**: FR-008 asks for "a single self-contained, reproducible unit". Pinned base images
plus `--locked` give reproducibility; two stages keep the published image small and free of build
tooling; non-root and a minimal surface are the cheap security defaults that cost nothing to adopt
now and are awkward to retrofit once the image does real work.

**`.dockerignore`** excludes `.git/`, `.venv/`, `tests/`, `specs/`, `docs/`, `.github/`,
`__pycache__/`, caches and editor files — smaller context, faster builds, and no chance of a local
`.env` or virtualenv being baked into a published image (FR-027).

**Alternatives considered**:

- **Single-stage build on `python:3.13-slim` with `pip install`**. Rejected: no lockfile
  enforcement (the constitution bans pip/requirements files), and it ships build tooling to
  production.
- **Pinning base images by digest** (`python:3.13-slim-bookworm@sha256:…`). Rejected for now:
  stronger reproducibility, but it freezes out security patches until someone updates the digest
  by hand, and there is no automation (Renovate/Dependabot) in this milestone to do it. Tag
  pinning to the exact minor version plus the Debian release is the right point on that curve
  today; revisit alongside dependency automation.
- **Alpine base**. Rejected: musl wheels and source builds for later dependencies (psycopg,
  cryptography) are a known source of slow, surprising builds; `slim` is the boring choice.

---

## D6 — Runtime configuration

**Decision**: configuration is read from the process environment, with the split below.

| Value | Read by | Default | Set where |
|---|---|---|---|
| `PORT` | the entrypoint, passed to `uvicorn --port` | `8000` | Render sets it automatically (Render's documented default port is `10000`) |
| `HOST` | the entrypoint, passed to `uvicorn --host` | `0.0.0.0` | `render.yaml` (explicit, so the value is visible) |
| `APP_COMMIT` | `app/core/config.py` | *(empty)* | Docker build arg for local/CI builds |
| `RENDER_GIT_COMMIT` | `app/core/config.py` (fallback) | *(unset locally)* | Render, automatically |

The application module itself reads **no** server-binding configuration: the address and port stay
a concern of the entrypoint, exactly as they are today when a developer types
`uv run uvicorn app.main:app --port 8001`. What `app/core/config.py` gains is the commit/version
pair that `/healthz` reports (D7), read with plain `os.environ` calls behind module constants.

**Rationale**:

- FR-009/FR-010: nothing environment-specific is hard-coded, the packaged app listens where its
  environment tells it to, and it starts with documented defaults when nothing is supplied
  (`docker run -p 8000:8000 student-competitions` must just work — US4 scenario 3).
- `os.environ` rather than a settings library: the entire configuration surface at this milestone
  is one optional string. `pydantic-settings` is a new runtime dependency and the constitution
  requires justifying those; "we will need it in milestone 3" is not a present need (Principle II,
  YAGNI). Milestone 3 introduces `DATABASE_URL`, milestone 4 a session secret and mail
  credentials — that is the point at which a typed `Settings` object earns its place, and moving
  two constants into it is a small, contained change.

**Alternatives considered**:

- **`pydantic-settings` now**. Rejected as above.
- **A committed `.env` / `.env.example`**. Rejected: nothing is required to run the app, so an
  example file would list one optional variable and invite the habit of keeping environment files
  next to the code (FR-027). The README's variable table (FR-012) is the documentation.
- **Reading `PORT` inside `app/main.py` and calling `uvicorn.run()`**. Rejected: it hard-wires the
  server into the app module, breaks `--reload` ergonomics and duplicates what the CLI already
  does well.

**Evidence**: Render docs — *Environment variables* (`PORT`, and the automatically set `RENDER`,
`RENDER_GIT_COMMIT`, `RENDER_GIT_BRANCH`, `RENDER_EXTERNAL_URL`, …).

---

## D7 — Health and version endpoint: `GET /healthz`

**Decision**: one new route, `GET /healthz`, returning `200` and a small JSON body:

```json
{"status": "ok", "version": "0.1.0", "commit": "<40-char sha or 'unknown'>"}
```

`commit` is `APP_COMMIT`, else `RENDER_GIT_COMMIT`, else the literal `"unknown"`. `render.yaml`
sets `healthCheckPath: /healthz`. Full contract: [contracts/http-routes.md](./contracts/http-routes.md).

**Rationale**:

- **FR-005** asks for one address that reports both liveness *and* the running version, usable by
  automated monitoring and for confirming a deployment took effect. One endpoint answers both.
- **FR-025** ("the team can see which commit the published version was built from") is then true
  for anyone with a browser, not only for someone with Render dashboard access — which matters
  because free instances have no shell.
- **D15** uses it as the release gate: the deploy job polls the public URL until `commit` equals
  the SHA it just deployed. That turns "the hook returned 200" into "the new version is actually
  serving", and it is what makes FR-024 (newest commit wins) observable.
- Render's health check needs a 2xx/3xx within **five seconds**; this handler touches nothing and
  allocates a three-key dict.

**Why JSON does not conflict with Principle II** ("interactivity MUST use HTMX partials … not JSON
consumed by client code"): that principle governs the *user interface*. `/healthz` is a
machine-to-machine endpoint with no UI, no template and no client-side code — the audience is
Render's health checker and the deploy workflow. Rendering it as HTML would force both to scrape
markup. The route is listed in `contracts/http-routes.md` as deliberately outside the page surface.

**Naming**: `/healthz` over `/health` or `/status` — the `z` suffix is the widespread convention
for infrastructure endpoints precisely because it is unlikely to collide with a future user-facing
page called "health" or "status".

**Not included**: no readiness/liveness split (one instance, nothing to warm up), no dependency
checks (there are no dependencies — FR-030), no uptime or build-time field (the GitHub deployment
record and Render's deploy list both carry timestamps already). Milestone 3 adds a database and
with it the first real reason for the endpoint to report on something other than itself.

---

## D8 — HTTPS

**Decision**: rely on Render's edge. No HTTPS middleware in the application.

**Rationale**: Render's documentation states it issues free managed TLS certificates for the
`onrender.com` subdomain and "automatically redirects all `HTTP` requests to `HTTPS`". That is
exactly FR-003, delivered by the platform, and it happens *before* the request reaches the
container.

Adding Starlette's `HTTPSRedirectMiddleware` on top would be actively harmful here: TLS is
terminated at Render's edge, so the app sees plain HTTP and would redirect in a loop unless
proxy headers are trusted; and Render's internal health check would hit the same redirect and
could mark a healthy instance unhealthy. Verified manually per quickstart V3 (`curl -I` against
`http://`, expecting a 301/308 to `https://`).

**Alternatives considered**: application-level redirect middleware (rejected, above); HSTS headers
(deferred — worth adding in milestone 12's hardening pass, not needed for a page with no cookies,
no login and no data).

**Evidence**: Render docs — *TLS certificates*.

---

## D9 — Pipeline shape: one reusable checks workflow, two entry points

**Decision**: three workflow files under `.github/workflows/`.

| File | Trigger | Contains |
|---|---|---|
| `checks.yml` | `workflow_call` only | The two verification jobs: `quality` (ruff check, ruff format --check, pytest) and `image` (docker build + container smoke test) |
| `ci.yml` | `pull_request` → `main` | Calls `checks.yml`. This is what the branch protection rule requires. |
| `deploy.yml` | `push` → `main` | Calls `checks.yml`, then a `deploy` job with `needs: checks` |

Both entry points therefore run the **same** job definitions; there is no way for the pull-request
gate and the release gate to drift apart, and no copy-pasted YAML.

Shared properties, each tied to a requirement:

- `uv` is installed with `astral-sh/setup-uv` (cache enabled) and dependencies with
  **`uv sync --locked`**, which fails if `uv.lock` does not match `pyproject.toml` — FR-018's
  "exact dependency versions the repository pins", enforced rather than assumed.
- **`timeout-minutes`** on every job (10 for `quality`, 15 for `image`, 20 for `deploy`) — FR-019
  and the "checks time out or hang" edge case. The run ends reported, not hung. _Updated
  2026-11-06_: `quality` is now 20, since the suite, run on both engines, passed 10 minutes in
  milestone 12.2; the bound, not its value, is what FR-019 asks for.
- `permissions: contents: read` at workflow level — least privilege; nothing in this pipeline
  writes to the repository.
- `concurrency` on `ci.yml` keyed by ref with `cancel-in-progress: true`: a new push to a pull
  request supersedes the previous run (FR-015 — re-verification on every update — without paying
  for stale runs).
- The `image` job runs `docker build` then starts the container with a mapped port and asserts
  `GET /healthz` returns `200` with the expected commit and `GET /` returns `200` with the
  application name. That is US4/FR-011 ("runs identically everywhere") verified automatically on
  every change, and it is the reason a Dockerfile regression cannot reach `main`.
- Failure output: ruff prints file, line and rule; pytest prints the failing test and assertion;
  the smoke test echoes the failing URL, status and body excerpt — FR-017 satisfied by the tools'
  own output, with no custom reporting layer.

**Required status checks** on `main` are the *job* names surfaced by `ci.yml`
(`checks / quality`, `checks / image`), so a red check blocks the merge button (FR-016).

**Alternatives considered**:

- **One workflow with a `deploy` job guarded by `if: github.ref == 'refs/heads/main'`**. Rejected:
  the pull-request run then contains a permanently skipped deploy job, and the release path shares
  a `concurrency` group with pull-request runs, which is how a cancelled PR run ends up cancelling
  a release.
- **`workflow_run:` — deploy triggered by CI completing successfully**. Rejected: `workflow_run`
  runs in a detached context, reports on the wrong commit in the UI, and is notoriously awkward to
  reason about. `needs:` inside one workflow is explicit and reviewable.
- **Duplicating the check steps in both workflows**. Rejected: guaranteed drift.
- **A pre-commit framework / separate lint action**. Rejected: `ruff` is already the project's one
  linter and formatter; a second tool to configure adds nothing.

---

## D10 — Ordering: making sure the newest commit wins

**Decision**: `deploy.yml` declares

```yaml
concurrency:
  group: deploy-production
  cancel-in-progress: true
```

and every hook call pins `ref=<sha>` (D2), with the post-deploy check (D15) asserting the live
`/healthz` commit equals the SHA that job deployed.

**How the three layers combine for FR-024** (the "two merges in quick succession" edge case):

1. **GitHub side** — only one release job exists at a time per repository; a newer push cancels an
   older job that has not finished. An older, superseded job cannot call the hook after a newer one
   has.
2. **Render side** — the hook returns `202` when a deploy is already running, queueing the new one;
   Render's overlapping-deploy policy (either "wait" or "override", depending on workspace age)
   resolves the order. Either way the **last deploy started is the last to finish**, and that is
   the newer commit.
3. **Verification** — the newer job only succeeds once `/healthz` reports *its* SHA. If an older
   deploy somehow landed last, the job fails loudly instead of reporting a false success.

The residual case — a newer job cancelled by GitHub mid-wait while its Render deploy is still
running — ends with the newest commit live and no job reporting it. That is a visible, benign
outcome (the deploy shows in Render and in the next `/healthz` read), not a wrong version served.

**Alternatives considered**: `cancel-in-progress: false` (a strict queue) — rejected, because it
means the older deploy runs to completion first and briefly publishes a superseded commit, which
is precisely what FR-024 forbids. Serialising with an external lock — rejected as
over-engineering for a repository with this merge rate.

**Evidence**: Render docs — *Deploys* (overlapping-deploy policies "wait" and "override"),
*Deploy hooks* (`202` when a deploy is in progress).

---

## D11 — Rollback (FR-026)

**Decision**: the documented procedure is a **single command**, the same mechanism a release uses:

```bash
RENDER_DEPLOY_HOOK_URL='…' ./scripts/render_deploy.sh <previous-good-sha>
./scripts/wait_for_release.sh https://<service>.onrender.com <previous-good-sha>
```

with Render's dashboard *Rollback* button on the previous successful deploy documented as the
no-terminal fallback (it redeploys a previous build without rebuilding, so it is faster).

**Rationale**: FR-026 asks only for a documented procedure, and the cheapest reliable procedure is
the release path run backwards — same script, same hook, same verification, nothing that only
works on a good day. Because the pipeline is commit-addressed (D2), "roll back" is literally
"deploy the previous SHA". Reverting the commit on `main` and letting the pipeline publish the
revert is the *preferred* long-term fix and is documented as such; the hook call is the fast path
for when the public address needs to be good in two minutes rather than ten.

**Alternatives considered**: a bespoke rollback mechanism, e.g. keeping the last-known-good image
tagged in a registry — rejected, the spec explicitly says the platform's own facility plus a
documented procedure is enough, and there is no registry (D4).

---

## D12 — Secrets and untrusted contributions

**Decision**:

| Value | Kind | Stored as |
|---|---|---|
| `RENDER_DEPLOY_HOOK_URL` (contains the hook `key`) | secret | GitHub **environment** secret on the `production` environment |
| `PUBLIC_BASE_URL` | not secret | GitHub repository **variable** |
| Render account credentials | secret | Render only; never in GitHub |

The `deploy` job declares `environment: production`, so the hook secret is reachable only from
that job, in that environment, on `push` to `main` — and GitHub records a deployment with its URL,
which doubles as FR-025's "when it was published".

**Fork safety (FR-028)**: pull requests from forks run `ci.yml`, which calls only `checks.yml`.
That workflow has no `environment:`, references no secret, and runs with `contents: read`. GitHub
additionally does not expose repository or environment secrets to `pull_request` runs from forks.
Untrusted code is therefore built and tested, and can reach no credential — which is exactly what
the requirement asks and why the deploy job lives on the `push` trigger rather than behind an `if`
in the shared workflow (D9).

**Nothing secret in the image or the logs (FR-027)**: the image contains no credential (D5's
`.dockerignore` keeps `.env`-style files and the local virtualenv out); the hook URL is passed to
`curl` through an environment variable, never interpolated into a logged command line, and GitHub
masks registered secrets in log output. `scripts/render_deploy.sh` prints the response *status*,
not the URL it called.

**SC-009 (zero secrets in the repository)** is verified by review of the milestone's full diff, as
the spec specifies. Enabling GitHub's secret scanning with push protection on the repository is
documented in the quickstart as a recommended one-time setting — free for public repositories and
a standing safety net rather than a one-off check.

**Alternatives considered**: a Render API key in CI (rejected, D2 — broader scope); committing the
public URL into the workflow instead of a variable (rejected — the URL is not secret, but it *is*
environment-specific, and FR-009 keeps environment-specific values out of committed files);
`pull_request_target` to give fork PRs access to secrets (rejected outright — it is the exact
anti-pattern FR-028 exists to prevent).

---

## D13 — Merge protection on `main`

**Decision**: protect `main` with a **repository ruleset / branch protection rule** requiring the
`quality` and `image` checks to pass and a pull request to merge, applied by a committed,
idempotent script — `scripts/setup_branch_protection.sh`, a thin wrapper over
`gh api --method PUT repos/{owner}/{repo}/branches/main/protection` — with the equivalent
dashboard steps written out in the quickstart for anyone without the `gh` CLI (it is not installed
on the current machine).

**Rationale**: FR-016 requires a failing check to *prevent* a merge, and a check that only reports
is not a gate. Branch protection is configured outside the repository, so the closest thing to IaC
the platform allows is a committed script that reproduces the setting exactly — reviewable,
re-runnable, and self-documenting about which contexts are required.

**Settings and why each one**: required status checks `quality` and `image`, *strict* (branch must
be up to date before merging — this is what catches the spec's "two independently green pull
requests that conflict once combined"); required pull request before merging; no force pushes; no
deletions. Required approvals are left at `0`: the project currently has a single active
contributor, and a rule nobody can satisfy gets switched off rather than followed. It is one
number in the script when the team grows.

**Known constraint**: classic branch protection and rulesets are available on free GitHub plans for
**public** repositories; private repositories need a paid plan. If this repository is private and
on the free plan, the gate must be achieved by making it public or upgrading — this is called out
in the quickstart because it is a hard external dependency of FR-016, not something the
implementation can work around.

**Alternatives considered**: relying on contributor discipline (rejected — FR-016 says "prevent");
a merge-queue (rejected — needs a paid plan for private repos and is meaningless at this merge
rate); Terraform's GitHub provider (rejected for the same reason as D3's Terraform option).

---

## D14 — Templates and static files anchored to the package

**Decision**: change `Jinja2Templates(directory="app/templates")` and
`StaticFiles(directory="app/static")` to paths derived from `__file__`
(`Path(__file__).resolve().parent`), instead of paths relative to the current working directory.

**Rationale**: both current paths silently assume the process was started from the repository
root. That assumption holds for `uv run uvicorn` in a checkout and would hold in the container as
long as `WORKDIR` is `/app` — until the day something runs the app from elsewhere, and then the
failure is a 500 on every page or a `RuntimeError: Directory 'app/static' does not exist` at
import time. FR-011 ("runs identically on a developer machine and on the hosting platform") is
exactly the requirement that makes this worth fixing now, while the app has two directories and
five minutes of work, rather than at milestone 6 with a bug report from production.

**Alternatives considered**: relying on `WORKDIR /app` alone (rejected — it makes a correctness
property of the app a property of the Dockerfile, in a file nobody reads when debugging a 500);
`importlib.resources` (rejected — the right tool for a *distributed* package's data files, and
noise for a directory sitting next to the module).

---

## D15 — Proving the deploy actually landed

**Decision**: after the hook call returns, `scripts/wait_for_release.sh` polls
`${PUBLIC_BASE_URL}/healthz` until the reported `commit` equals the deployed SHA, or a **12-minute**
deadline passes; it then fails the job. Each poll uses `curl --max-time 60` (a free instance may be
spinning up from cold), backing off between attempts, and the script prints the last response it
saw before failing.

**Rationale**:

- Without it, the workflow's success means only "Render accepted the request". FR-023 wants a
  *failed publish* reported to the team; a hook call that returns `200` before a build that fails
  four minutes later would otherwise be a green workflow over a stale site.
- It is the only automated evidence for **SC-007** ("visible at the public address within 15
  minutes, zero manual steps"): the job's own duration measures it on every release.
- Polling the application rather than Render's API keeps the pipeline free of a workspace-scoped
  API key (D2) and checks the thing that actually matters — what a visitor gets — rather than what
  the control plane believes.
- The deadline sits inside SC-007's 15 minutes and outside the realistic worst case (a cold
  multi-minute image build plus a ~1-minute free-instance start).

**Alternatives considered**: polling Render's `GET /v1/deploys/{id}` (rejected — needs an API key,
and reports the control plane's view, not the public address); a fixed `sleep` (rejected — either
too short to be true or too long to be useful); no verification at all (rejected — FR-023).

---

## Summary of resolved unknowns

| Question | Resolution |
|---|---|
| Hosting provider, plan, region | Render, free instance type, `frankfurt` (D1) |
| What triggers a release | GitHub Actions → Render deploy hook, `ref` pinned to the commit (D2) |
| How much is infrastructure as code | `render.yaml` Blueprint + workflows + Dockerfile + scripts; three documented bootstrap clicks (D3) |
| Who builds the image | Render, from the repo; CI builds and smoke-tests it too (D4) |
| Base images, entrypoint | uv builder + `python:3.13-slim-bookworm`, non-root, `exec uvicorn` with `${PORT:-8000}` (D5) |
| Configuration mechanism | `os.environ` behind constants; no settings library yet (D6) |
| Liveness/version address | `GET /healthz` → `{status, version, commit}` (D7) |
| HTTPS redirect | Render's edge; no app middleware (D8) |
| Pipeline layout | Reusable `checks.yml`, called by `ci.yml` (PRs) and `deploy.yml` (main) (D9) |
| Newest-commit-wins | `concurrency` + pinned `ref` + post-deploy verification (D10) |
| Rollback | Re-run the deploy script with the previous SHA; dashboard rollback as fallback (D11) |
| Secret storage & fork safety | `production` environment secret; fork PRs touch no secret (D12) |
| Merge protection | Scripted branch protection requiring both checks (D13) |
| Path resolution | Anchored to the package directory (D14) |
| Deploy verification | Poll public `/healthz` for the SHA, 12-minute deadline (D15) |

**No `NEEDS CLARIFICATION` items remain.** Two values exist only after the one-time bootstrap and
are filled in then, not decided here: the service's generated `onrender.com` hostname (recorded in
the README per FR-007 and in the `PUBLIC_BASE_URL` repository variable) and the deploy hook URL
(stored as a secret per D12).
