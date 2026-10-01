# Pipeline Contract: changes to Render, CI and release

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](../plan.md)

Changes to milestone 4's pipeline
([specs/004-email-otp-auth/contracts/pipeline.md](../../004-email-otp-auth/contracts/pipeline.md)).
Everything not listed is unchanged. Rationale:
[research D13](../research.md#d13--pipeline-the-packaged-image-proves-one-role-boundary-the-release-proves-a-role-page-is-private).

---

## Container (`Dockerfile`, `.dockerignore`)

Unchanged. The entrypoint still runs `alembic upgrade head` before uvicorn, which applies this
milestone's revision.

## Render service (`render.yaml`)

Two keys are added under `envVars`, after `ADMIN_EMAILS`, with a comment (exact text in
[configuration.md](./configuration.md#render-renderyaml-added-under-envvars)):

- `TEACHER_EMAILS` (`sync: false`);
- `STUDENT_EMAILS` (`sync: false`).

The header comment's count of declared secrets goes from five to seven. Nothing else changes.

## `checks.yml` → `quality`

Unchanged. `ruff check`, `ruff format --check` and the full pytest suite on both engines now
include this milestone's tests.

## `checks.yml` → `image`

Steps 1–7 are unchanged. The refusal checks (steps 3–4) are unchanged too, because neither new
list is required on Render.

Step 8, *Sign in, smoke test `GET /`, restart, and again*, is **extended**. The CI administrator
`ci-admin@example.com` holds one role, so the sign-in itself is unchanged: `POST /login/code` still
answers 303 to `/` (SC-003). Added checks:

1. In `check_home`: the header contains `class="site-role"` and `Administrator`, and the body
   contains `href="/admin"` and `href="/staff"` but not `href="/student"` or `href="/teacher"`.
2. After the first `check_home 1`:
   - `curl -b jar /admin` → `200`, and the body contains `Administrator area`.
   - `curl -b jar /student` → `403`, and the body contains `Access denied`.
   - A **cross-site** logout attempt: `curl -b jar -X POST -H 'Origin: https://evil.example'
     /logout` → `403`. Then `curl -b jar /` → `200`. This proves the session survived (FR-021,
     research D7).
3. The existing restart, `check_home 2` and logout checks follow, unchanged. The legitimate
   logout `curl` sends no `Origin` header and is still accepted.

The step's comment gains one sentence naming the role checks and linking here.

## `deploy.yml` → `deploy`

Unchanged. *Verify access control* still runs `scripts/verify_private.sh`, which gains one check
(below).

### `scripts/verify_private.sh` (changed)

A fourth assertion, inside the same retry loop:

4. `GET <base>/admin` without a cookie → status `303`, and `Location` ends with
   `/login?next=%2Fadmin`. This proves that a role page is private on production, without any
   credential.

The script's header comment names the new check. Output and failure format are unchanged.

## Secrets surface after this milestone

| Secret | Lives in | Never in |
|---|---|---|
| `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY`, `EMAIL_FROM` | Render environment | unchanged from milestone 4 |
| `TEACHER_EMAILS`, `STUDENT_EMAILS` | Render environment only | the repository, `render.yaml` values, the image, GitHub secrets or variables, CI logs, application logs |
| `RENDER_DEPLOY_HOOK_URL` | GitHub `production` environment | unchanged |

CI adds no secret and no variable. The only addresses in the workflow remain the labelled fake
`ci-admin@example.com`.
