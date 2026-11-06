# Pipeline Contract: GitHub Actions workflows

**Feature**: `002-public-deploy-cicd` | **Date**: 2026-09-22 | **Plan**: [plan.md](../plan.md)

The verification and release surface: what runs, when, with what permissions, and what each
outcome means. Rationale: [research.md D9](../research.md#d9--pipeline-shape-one-reusable-checks-workflow-two-entry-points),
[D10](../research.md#d10--ordering-making-sure-the-newest-commit-wins),
[D12](../research.md#d12--secrets-and-untrusted-contributions),
[D15](../research.md#d15--proving-the-deploy-actually-landed).

## Files and triggers

| File | Trigger | Purpose |
|---|---|---|
| `.github/workflows/checks.yml` | `workflow_call` **only** | Defines the two verification jobs once. Never runs on its own. |
| `.github/workflows/ci.yml` | `pull_request` targeting `main` (opened, synchronize, reopened) | Calls `checks.yml`. This is the merge gate. |
| `.github/workflows/deploy.yml` | `push` to `main` (plus `workflow_dispatch` for a manual re-release) | Calls `checks.yml`, then deploys and verifies. |

Because both entry points call the same reusable workflow, the pull-request gate and the release
gate cannot drift apart.

## `checks.yml` — the verification jobs

| Job | Steps | Timeout | Requirement |
|---|---|---|---|
| `quality` | checkout → `astral-sh/setup-uv` (cache on) → `uv sync --locked` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run pytest` | 20 min (10 until milestone 12.2) | FR-013, FR-014, FR-018, FR-019 |
| `image` | checkout → `docker build --build-arg APP_COMMIT=${{ github.sha }} -t student-competitions:ci .` → run the container with a mapped port → assert `GET /healthz` is `200` with `status == "ok"` and `commit == github.sha` → assert `GET /` is `200` and contains the application name → stop the container | 15 min | FR-011, US4 |

Both jobs run on `ubuntu-latest`, in parallel, with workflow-level `permissions: contents: read`.
Neither references a secret or an environment, which is what makes fork pull requests safe
(FR-028).

**Failure output** (FR-017) comes from the tools themselves — ruff names file, line and rule;
pytest names the test and shows the assertion; the smoke test echoes the URL, the status it got
and an excerpt of the body. No custom reporting layer is added, because none is needed to act on a
failure without reproducing it locally.

## `ci.yml` — the merge gate

```yaml
on:
  pull_request:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  checks:
    uses: ./.github/workflows/checks.yml
```

| Requirement | How |
|---|---|
| FR-013/FR-014 — tests and style run on every PR | The `pull_request` trigger |
| FR-015 — re-runs when new commits are pushed | The `synchronize` event; `cancel-in-progress` supersedes the stale run |
| FR-016 — a failing outcome blocks the merge | Branch protection requires the `checks / quality` and `checks / image` contexts (see below) |
| FR-019 — bounded time | `timeout-minutes` on both jobs |
| SC-006 — under 5 minutes | Two parallel jobs, uv's cache, a small test suite and a layer-cached image build |

## `deploy.yml` — the release

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: deploy-production
  cancel-in-progress: true
jobs:
  checks:
    uses: ./.github/workflows/checks.yml
  deploy:
    needs: checks
    environment:
      name: production
      url: ${{ vars.PUBLIC_BASE_URL }}
    timeout-minutes: 20
    steps: …
```

The `deploy` job's steps:

1. **Trigger** — `scripts/render_deploy.sh "${{ github.sha }}"` with `RENDER_DEPLOY_HOOK_URL` from
   the environment secret. Accepts `200` (deploy started) and `202` (queued behind a running
   deploy); fails on `400`, `401`, `404` or any other status, printing the status and body but
   **never the URL** (FR-027).
2. **Verify** — `scripts/wait_for_release.sh "${{ vars.PUBLIC_BASE_URL }}" "${{ github.sha }}"`
   polls `/healthz` until `commit` matches, or fails after a 12-minute deadline, printing the last
   response it saw. A free instance may be cold-starting, so each request allows up to 60 s.

| Requirement | How |
|---|---|
| FR-020 — merging starts the publish, no manual step | The `push` trigger; nothing else is needed from a human |
| FR-021 — publish only if checks pass | `needs: checks` on the same commit |
| FR-022 — other branches publish nothing | `branches: [main]`, and Render's own auto-deploy is off |
| FR-023 — failures reported, previous version keeps serving | Any failing step fails the job (GitHub's existing notifications); Render leaves the old version in place |
| FR-024 — newest commit wins | `cancel-in-progress: true` on a single `deploy-production` group, `ref=<sha>` pinning, and step 2 refusing to pass on the wrong SHA |
| FR-025 — which commit is live, and when | The GitHub deployment record on the `production` environment, plus `/healthz` |
| SC-007 — live within 15 minutes, zero manual steps | Measured by the job's own duration on every release |

## Secrets, variables and permissions

| Name | Kind | Scope | Used by |
|---|---|---|---|
| `RENDER_DEPLOY_HOOK_URL` | **secret** | `production` environment | `deploy` job only |
| `PUBLIC_BASE_URL` | repository **variable** (not secret) | repository | `deploy` job, and the environment URL shown in GitHub |

- Workflow-level `permissions: contents: read` everywhere; nothing writes to the repository.
- The hook secret is an *environment* secret, so it is unreachable from `checks.yml`, from
  `ci.yml`, and from any fork pull request (FR-028).
- `pull_request_target` is **not** used anywhere, and must not be introduced.

## Branch protection (the gate itself)

Applied by `scripts/setup_branch_protection.sh` (idempotent `gh api` call), with the dashboard
equivalent written out in the quickstart:

| Setting | Value | Requirement |
|---|---|---|
| Required status checks | `checks / quality`, `checks / image` | FR-016 |
| Strict (branch must be up to date) | on | The "two green PRs that conflict once combined" edge case |
| Require a pull request before merging | on | Constitution, Development Workflow §2 |
| Required approvals | `0` | Single active contributor; one number to change when the team grows |
| Force pushes / deletions | blocked | Protects release history |

**External dependency**: branch protection and rulesets are free for **public** repositories;
a private repository on a free GitHub plan cannot enforce this, and FR-016 then cannot be
satisfied without changing visibility or plan. Called out in the quickstart because no amount of
implementation works around it.

## What a green pipeline means

| Signal | Meaning |
|---|---|
| Green `ci.yml` on a PR | The suite, the style rules and the container build all pass for that commit; the merge button is enabled |
| Green `deploy.yml` on `main` | The same checks passed **and** the public address is serving that exact commit — asserted, not assumed |
| Red `deploy.yml`, deploy step | Render rejected or failed the release; the previous version is still serving |
| Red `deploy.yml`, verify step | Render accepted the release but the public address did not report the SHA within the deadline; someone must look at Render's deploy log before merging anything else |
