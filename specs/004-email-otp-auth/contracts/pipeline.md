# Pipeline Contract: deltas to the container, Render, CI and release

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](../plan.md)

This is what changes in the delivery pipeline because the home page becomes private and four
secrets appear. Everything not mentioned is unchanged from
[milestone 3's pipeline contract](../../003-database-questions/contracts/pipeline.md). Rationale:
[research D14](../research.md#d14--pipeline-the-public-page-is-private-now-so-the-checks-sign-in-or-check-privacy).

---

## Container (`Dockerfile`, `.dockerignore`)

**Unchanged.** The entrypoint is still `alembic upgrade head && exec uvicorn …`. The new
dependency is installed by `uv sync --locked` from the updated `uv.lock`. No secret is baked in.
Authentication settings are read only from the environment at start.

## Render service (`render.yaml`)

It adds five `envVars`: `EMAIL_BACKEND` with the value `resend`, and `SECRET_KEY`, `ADMIN_EMAILS`,
`RESEND_API_KEY` and `EMAIL_FROM` with `sync: false`
([configuration.md](./configuration.md#render-renderyaml)). The header comment is updated from
"one secret" to "five secrets". **Rollout gate**: all four secret values are entered in the
dashboard and the Resend domain shows *Verified* before the merge to `main` (quickstart B1–B3).
Otherwise the first release refuses to start (by design) and the previous one keeps serving.

## `checks.yml` → `quality`

Unchanged steps. The suite now includes the new test modules. `EMAIL_BACKEND=memory` is set by
the test fixtures, not by the workflow. No secret is added: this workflow still references none
(fork PRs stay safe).

## `checks.yml` → `image`

The steps, in order (new or changed ones marked):

1. Build the image. *(unchanged)*
2. Refuse to start on Render without a database. *(unchanged)*
3. **NEW: Refuse to start on Render without auth settings.** Runs
   `docker run --rm --network host -e RENDER=true -e DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres …`.
   Expects a non-zero exit, and output containing each of `EMAIL_BACKEND`, `SECRET_KEY`,
   `ADMIN_EMAILS`, `RESEND_API_KEY` and `EMAIL_FROM`.
4. **NEW: Refuse the console backend on Render.** The same, plus `EMAIL_BACKEND=console`,
   `SECRET_KEY=ci-dummy-not-a-secret-0123456789abcdef`, `ADMIN_EMAILS=ci-admin@example.com`,
   `RESEND_API_KEY=ci-dummy-key` and `EMAIL_FROM=ci@example.com`. Expects a non-zero exit, output
   containing `EMAIL_BACKEND`, and output **not** containing `ci-dummy-not-a-secret` or
   `ci-dummy-key` (the no-echo rule, FR-041). The values are deliberately fake and labelled, so
   the workflow still holds no credential.
5. **CHANGED: Start the container.** Adds `-e ADMIN_EMAILS=ci-admin@example.com`. There is no
   `EMAIL_BACKEND` (the local default is `console`) and no `SECRET_KEY` (the fixed development key,
   the same across the restart below).
6. Wait for the container to answer `/healthz`. *(unchanged)*
7. Smoke test `GET /healthz`. *(unchanged: three keys, commit)*
8. **REPLACED: Sign in, smoke test `GET /`, restart, and again.**
   - Anonymous `curl -s -o /dev/null -w '%{http_code} %{redirect_url}' /` → `303` and
     `…/login?next=%2F`.
   - `curl -c jar -d email=ci-admin@example.com /login` → 200.
   - Poll `docker logs smoke` for up to 10 s for the line `Your Student Competitions sign-in code
     is: <6 digits>`, and extract the last one.
   - `curl -b jar -c jar -d email=… -d code=… /login/code` → `303`, and the jar now holds
     `sc_session`.
   - `check_home 1`: milestone 3's checks, made with `-b jar`: the app name, the first sample
     question, no unavailable notice, `data-engine="postgresql"`, `data-boots="1"`, 6 items, and
     additionally `ci-admin@example.com` and `action="/logout"` in the header.
   - `docker restart smoke`, wait for `/healthz`.
   - `check_home 2` **with the same jar**, without signing in again. This proves the server-side
     session and the data survived the restart.
   - `curl -b jar -c jar -X POST /logout` → 303. Then `GET /` with the jar → 303 to login. This
     proves logout invalidates the server session.
   - On any failure, print the URL, the status, an excerpt of the body and `docker logs smoke`.
     The logs contain the code by design here: it is the console backend, and the code belongs to
     a throw-away CI container.
9. Stop the container. *(unchanged)*

## `deploy.yml` → `deploy`

| Step | Change |
|---|---|
| Install uv, Install dependencies | **removed**: they were needed only for *Expected revision* |
| Expected revision | **removed** (the single-head check remains in `test_migrations.py`, which the `checks` job runs for this commit) |
| Previous boot count | **removed**: the anonymous page no longer shows it |
| Trigger the Render deploy | unchanged |
| Verify the public address is serving this commit | unchanged (`wait_for_release.sh` reads the public `/healthz`) |
| Verify data | **replaced by** *Verify access control*: `./scripts/verify_private.sh "${{ vars.PUBLIC_BASE_URL }}"` |

### `scripts/verify_private.sh` (new; replaces `scripts/database_status.sh`, which is deleted)

Usage: `./scripts/verify_private.sh <base-url>`. It reads only public responses, needs no
credential and prints none. It retries for up to 60 s (a cold instance) and then asserts:

1. `GET <base>/` without a cookie → status `303`, and `Location` ends with `/login?next=%2F`.
2. `GET <base>/login` → `200`, and the body contains `name="email"` and `action="/login"`.
3. `GET <base>/healthz` → `200` (already covered by `wait_for_release.sh`; repeated here cheaply,
   so the script is self-sufficient when a person runs it).

On failure it prints the URL, the status, the `Location` header and a 500-byte body excerpt, then
exits 1. It uses `curl` only (no `-L`, so redirects are observed rather than followed).

## Secrets surface after this milestone

| Secret | Lives in | Never in |
|---|---|---|
| `DATABASE_URL` | Render environment | unchanged from milestone 3 |
| `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`, `EMAIL_FROM` | Render environment only | the repository, `render.yaml` values, the image, GitHub secrets or variables, CI logs, application logs |
| `RENDER_DEPLOY_HOOK_URL` | GitHub `production` environment | unchanged |

GitHub gains **no** secret in this milestone. The CI dummy values in `image` step 4 are labelled
fakes and unlock nothing.
