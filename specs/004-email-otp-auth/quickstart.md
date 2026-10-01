# Quickstart & Validation: Email Code Authentication (Milestone 4)

**Feature**: `004-email-otp-auth` | **Date**: 2026-09-29 | **Plan**: [plan.md](./plan.md)

This guide covers three things: the one-time production setup (email domain and secrets), how a
developer signs in locally, and how to prove the milestone is done. Every validation scenario maps
to acceptance scenarios or success criteria in [spec.md](./spec.md). The run-and-configure parts
also go into the README (FR-044).

The milestone's stated criterion is: **"A user can log in end to end, reading the code from the
`memory` outbox. A route-table test asserts that every route outside the allowlist rejects
anonymous requests. Existing page tests use a fixture that creates a session directly. Unknown and
known emails get the same response. Running the reconcile twice changes nothing. An email removed
from `ADMIN_EMAILS` can no longer log in and loses its sessions."**

## Prerequisites

| Need | For |
|---|---|
| [`uv`](https://docs.astral.sh/uv/), Docker | unchanged from milestone 3 |
| A [Resend](https://resend.com) account | production email (B1) |
| Access to the DNS of `brainring.org.ua` at NIC.UA | domain verification records (B1) |
| Access to the Render service's *Environment* settings | the four secrets (B3) |
| Two real inboxes at different providers (for example Gmail and Outlook/ukr.net) | SC-002 (V7) |

Locally, nothing needs configuring (FR-042, SC-009).

---

## One-time bootstrap (production). Do this before merging to `main`.

If you skip it, the first release refuses to start (by design, FR-041). The deploy fails and
milestone 3's release keeps serving.

### B1: Verify the sending domain in Resend

1. In Resend → *Domains* → *Add domain*, enter `brainring.org.ua` and choose the EU region if
   offered. *Re-check the free plan's current limits (domains, daily/monthly sends) on the pricing
   page.*
2. Resend shows the DNS records to create: a DKIM `TXT` at `resend._domainkey`, and an `MX` plus an
   SPF `TXT` on its bounce subdomain (usually `send`). Add each one exactly as shown in the NIC.UA
   DNS editor for `brainring.org.ua`. Do not touch the existing `A @` and `CNAME www` records.
3. Add `TXT _dmarc` → `v=DMARC1; p=none;` if no DMARC record exists yet.
4. Wait until Resend shows **Verified** for the domain. This takes minutes to a few hours,
   depending on DNS propagation.

### B2: Create the API key

In Resend → *API Keys* → *Create*, choose permission **Sending access**, restricted to
`brainring.org.ua`. Copy it once. It goes only into Render (B3), never into a file, chat or
GitHub.

### B3: Give the secrets to Render

In Render → service `student-competitions` → *Environment*, set:

| Key | Value |
|---|---|
| `SECRET_KEY` | output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_EMAILS` | the real administrator addresses, comma-separated |
| `RESEND_API_KEY` | the key from B2 |
| `EMAIL_FROM` | `Student Competitions <login@brainring.org.ua>` |

`EMAIL_BACKEND=resend` comes from `render.yaml` after the merge. Saving environment changes
restarts the currently deployed milestone-3 release. It ignores the new variables, which is
harmless.

---

## Running locally: sign in with the code from the console

```bash
uv sync
uv run alembic upgrade head
ADMIN_EMAILS=you@example.com uv run uvicorn app.main:app --reload
```

The startup output warns that `SECRET_KEY` and `EMAIL_BACKEND` are not set (expected locally) and
reports `Administrators reconciled: 1 created, …`. Open <http://127.0.0.1:8000>, which redirects
to the login page. Enter `you@example.com`. The terminal prints the email:

```text
======== EMAIL (console backend: not sent) ========
To: you@example.com
Subject: Your Student Competitions sign-in code

Your Student Competitions sign-in code is: 042917
…
```

Type the code. You land on the home page, with your address and **Log out** in the header.

## Running the suite

Unchanged: `uv run pytest`, and add `TEST_POSTGRES_URL=…` for the PostgreSQL half (milestone 3
README). The fixtures set `EMAIL_BACKEND=memory`, and no test makes a network call.

---

## Validation scenarios

### V1: A developer signs in locally from a clean checkout (US1-1/2/3, US6-1; FR-042, FR-044; SC-001, SC-009)

Follow *Running locally* from a fresh clone, timing from `git clone`, using only the README.

**Expected**: the console email appears after step 1; sign-in succeeds; the home page is exactly
milestone 3's page plus the header. The whole thing takes under 15 minutes (SC-009), and
under 2 minutes from opening the site (SC-001). Starting **without** `ADMIN_EMAILS` shows the
"nobody will be able to sign in" warning, and the login page still behaves identically.

### V2: The automated suite proves the flow, the protection and the rules (all user stories; FR-045, FR-046; SC-003, SC-004, SC-005, SC-007)

Run the suite with `TEST_POSTGRES_URL` set.

**Expected**: all green, with every database test run as `[sqlite]` and `[postgresql]`. In
particular:

- the end-to-end login via the memory outbox (`test_login_flow.py`);
- the route-table sweep (`test_routes.py`, SC-003);
- known, unknown and inactive addresses give identical responses, with timing medians < 100 ms
  apart (`test_login_privacy.py`, SC-004);
- the attempt and request limits, including across a restart (SC-005);
- reconcile run twice changes nothing (S2, SC-007);
- an address removed from the list loses its sessions and can no longer obtain a code (S3 plus an
  HTTP test);
- every milestone-3 page test passing through `admin_client` (FR-046).

The full matrix is in [auth-services.md](./contracts/auth-services.md#behaviour-matrix-each-row-is-a-test-on-sqlite-and-postgresql)
and [http-routes.md](./contracts/http-routes.md#verification).

### V3: The packaged image signs in for real and refuses unsafe production configs (US6-4; FR-041; SC-010) *(automated on every PR)*

Open the `checks / image` job of the pull request.

**Expected**: green, with the log showing:

- anonymous `/` → 303;
- the code read from `docker logs`;
- signed in, boot #1;
- restart, still signed in with the same cookie, boot #2;
- logout → anonymous again;
- both `RENDER=true` refusals, naming the settings without echoing the dummy values.

See [pipeline.md](./contracts/pipeline.md#checksyml--image).

### V4: The release proves production is private (US2-1/2; FR-028) *(automated on every release)*

After merging, open the `Deploy` run.

**Expected**: *Verify the public address is serving this commit* and *Verify access control* are
green. `curl -s -o /dev/null -D - https://brainring.org.ua/` (a GET; `curl -I` sends HEAD, which FastAPI answers with `405`) shows `303` and `location: /login?next=%2F`.
`/healthz` answers without a cookie.

### V5: An administrator signs in on production with a real inbox (US1; FR-009, FR-012, FR-032, FR-038; SC-001) *(manual, required once)*

From a device outside the team's network, open `https://brainring.org.ua/`, enter an address from
`ADMIN_EMAILS`, and sign in with the emailed code.

**Expected**: the email arrives from `login@brainring.org.ua` with the code and no link. Sign-in
lands on the home page, and the header shows the address. The cookie in the browser's dev tools is
`HttpOnly`, `Secure` and `SameSite=Lax`. Log out: you are back on `/login`, and pressing *Back*
then reloading gives the login page again.

### V6: Removing an administrator ends their access within one restart (US3-3/4/5; FR-004; SC-006) *(manual, required once)*

1. Add a second address you control to `ADMIN_EMAILS` in Render (which restarts the service), and
   sign in with it in a separate browser.
2. Remove that address from `ADMIN_EMAILS` (another restart).
3. Reload the page in that browser. Then request a code for that address.

**Expected**: after the restart the Render log shows `… 0 created, 0 reactivated, 1 deactivated,
…` and no email address. The reload lands on `/login`. The code request shows the usual "check
your email" page, and no email arrives. Add the address back, restart, and it can sign in again.

### V7: Login emails reach the inbox, not spam (FR-038; SC-002) *(manual, required once)*

Request 10 codes spread over two inboxes at different providers, staying within the rate limits
(for example 5 per address).

**Expected**: at least 95% land in the inbox (not spam) within 1 minute. The message headers show
`dkim=pass` and `spf=pass` for `brainring.org.ua` (and `dmarc=pass`). Record the results in the
PR.

### V8: The boot count still rises across a redeploy, seen signed in (milestone 3 SC-002, spec assumption) *(manual witness, required once)*

Signed in on production, note `boot #N`. Merge any small change (or re-run the deploy workflow),
then reload.

**Expected**: `boot #N+1` or higher, the same revision line format, and the questions intact. Every
PR checks the same property automatically in the `image` job (V3).

### V9: Rate limits and the per-client key in production (US5-3/4; FR-017, FR-018; research D8) *(manual, required once)*

1. Request codes for one of **your own** addresses 6 times within an hour. Expected: the 6th
   attempt shows "Too many attempts", and exactly 5 emails arrived.
2. From one machine, send 21 step-1 requests for 21 different made-up addresses at
   `example.invalid`, **each with a different fake** `X-Forwarded-For` header
   (`curl -H "X-Forwarded-For: 203.0.113.<n>" -d email=u<n>@example.invalid …/login`).
   Record whether the 21st is refused.
   - **Refused**: Render overrides the header, and the per-client limit holds.
   - **Accepted**: the residual risk in plan Complexity Tracking is confirmed. Record it in the PR.
     No change is required for acceptance, because the per-email and per-code limits still bound
     SC-005.

### V10: No codes, tokens, secrets or email bodies anywhere (FR-037, FR-040; SC-008) *(manual, required once)*

- `git grep -nE 're_[A-Za-z0-9]{8,}'` and a review of the diff: no secret. `render.yaml` holds
  keys only, except `EMAIL_BACKEND: resend`.
- Download the Render logs covering V5–V9: no 6-digit code next to "code", no `sc_session`, no
  address from `ADMIN_EMAILS`, no email body. Only the reconciliation counts and the uvicorn
  access lines are present. The access lines contain paths such as `/login?next=%2F`, never an
  email address.
- `docker run --rm --entrypoint sh student-competitions:ci -c 'env; ls -a /app'` (from a local
  build): no auth variable is set, and no `.env` file exists.

---

## Milestone acceptance checklist

- [ ] B1–B3 done before the merge; the Resend domain is *Verified*; the four secrets exist only in
      Render
- [ ] V1: clean checkout → local sign-in via the console email in under 15 minutes
- [ ] V2: full suite green on both engines
- [ ] V3: `image` job green (real sign-in, restart keeps the session, refusals)
- [ ] V4: deploy job's *Verify access control* green; production `/` → 303
- [ ] V5: real sign-in on production; cookie flags confirmed
- [X] V6: removed administrator loses access within one restart; re-adding restores it
- [ ] V7: ≥ 95% inbox placement within 1 minute across two providers; DKIM/SPF/DMARC pass
- [ ] V8: boot count witnessed rising across a redeploy while signed in
- [X] V9: per-email limit confirmed; per-client spoofing result recorded
- [ ] V10: no code, token, secret or body in the diff, the logs or the image
- [ ] README updated: every new setting (purpose, values, local default, production requirement),
      local sign-in via the console, and the private-by-default rule for new pages

## Reference

- Design: [plan.md](./plan.md) · [research.md](./research.md) · [data-model.md](./data-model.md)
- Contracts: [http-routes.md](./contracts/http-routes.md) ·
  [auth-services.md](./contracts/auth-services.md) ·
  [email-sender.md](./contracts/email-sender.md) ·
  [configuration.md](./contracts/configuration.md) · [pipeline.md](./contracts/pipeline.md)
