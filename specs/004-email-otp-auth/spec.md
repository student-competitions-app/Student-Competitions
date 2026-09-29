# Feature Specification: Email Code Authentication (Milestone 4)

**Feature Branch**: `004-email-otp-auth`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "use product-requirements.md and technical-requirements.md for refearence. Create a specification for the milestone 4"

## Overview

Milestone 4 of the walking skeleton for the Student Competitions application. Milestones 1–3 put
a page on the public internet, behind an automated check-and-publish pipeline, reading sample
questions and a database status line from a persistent database. Until now, anyone on the
internet can see everything, and the application has no idea who is looking.

This milestone gives the application a front door. People sign in by typing their email address
and then the one-time code that arrives in their inbox; there are no passwords. Four things become
true when this milestone is done:

1. **Only known, active users can get in.** There is no sign-up. In this milestone the only users
   are site administrators, and the list of administrators is owned by the operations team through
   deployment configuration — never through the website.
2. **Everything is private by default.** Every page, including the existing home page, requires a
   signed-in user. Only a short, explicit list of addresses is reachable anonymously: the login
   and logout steps, the liveness check and static assets.
3. **Sign-in resists abuse.** Codes are short-lived, single-use and stored only in protected form;
   guessing and email flooding are rate-limited; and nothing in the login flow reveals whether a
   given email address belongs to a user.
4. **Email delivery is swappable per environment.** Developers see the email on their own console
   with no mail account; the automated tests read codes from an in-memory outbox and run the real
   flow end to end; production sends real email through a transactional email provider. The
   production deployment refuses to start with an unsafe or incomplete configuration.

Roles and role-based access (student / teacher / administrator) are **not** part of this
milestone; milestone 5 builds them on top of this sign-in flow.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator signs in with a code sent by email (Priority: P1)

An administrator opens the site and lands on a login page. They enter their email address and
submit. The page tells them to check their inbox for a code. A few moments later an email arrives
containing a short code. They type the code into the second step of the login page and submit.
They are now signed in: they are taken to the page they originally wanted (or the home page), and
the header shows their email address and a **Log out** button. The home page looks exactly as it
did before this milestone.

**Why this priority**: This is the milestone's reason to exist and its end-to-end slice —
email in, code out, code back, session established. Every later milestone (roles, question bank,
users, competitions) depends on knowing who the current user is.

**Independent Test**: With an administrator email configured, run the full flow in the automated
tests using the in-memory outbox (request code → read code from the outbox → submit code → reach
the home page signed in). In production, the acceptance check is the same flow with a real inbox.

**Acceptance Scenarios**:

1. **Given** an active administrator, **When** they submit their email on the login page, **Then**
   they are shown the code-entry step with a "check your email" message, and an email containing
   a one-time code is sent to that address.
2. **Given** the administrator received a code, **When** they submit the correct code within its
   validity period, **Then** they are signed in, redirected to the page they originally requested
   (or to the home page if none), and the header shows their email address and a **Log out**
   button.
3. **Given** a signed-in administrator, **When** they open the home page, **Then** it shows the
   same content as before this milestone (introduction, sample questions, database status line).
4. **Given** the administrator typed their email with surrounding spaces or different letter case,
   **When** they submit it, **Then** it is treated as the same address as the configured one.
5. **Given** a code has been used successfully once, **When** it is submitted again, **Then** it is
   rejected.
6. **Given** a code older than its validity period, **When** it is submitted, **Then** it is
   rejected with a message suggesting the user request a new code.
7. **Given** a user is on the code-entry step, **When** they choose to start over or request a new
   code, **Then** they can do so without leaving the login page flow (subject to rate limits).

---

### User Story 2 - Every page is private unless explicitly public (Priority: P2)

An anonymous visitor who opens any page of the application — the home page included — is sent to
the login page instead. After signing in, they land on the page they originally asked for. Only
the login and logout steps, the liveness check used by the hosting platform, and static assets
(styles, images, scripts) remain reachable without signing in.

**Why this priority**: Protecting pages is the point of authentication. Making protection the
default — rather than something each new page must remember to add — means pages added in later
milestones are private automatically, and a forgotten check cannot leak data.

**Independent Test**: An automated test walks the application's full list of addresses and
asserts that every one not on the public allowlist turns an anonymous request away to the login
page; the same test fails if a new address is added without protection or allowlisting.

**Acceptance Scenarios**:

1. **Given** an anonymous visitor, **When** they request the home page or any other protected
   page, **Then** they are redirected to the login page, and the originally requested address is
   carried along so they can return to it after signing in.
2. **Given** an anonymous visitor, **When** they request the login page, the logout action, the
   liveness check or a static asset, **Then** the request is served without a redirect to login.
3. **Given** the login page is reached with a "return to" address that points to another site
   (absolute address, protocol-relative address or similar trick), **When** the user signs in,
   **Then** they are sent to the home page instead of the other site.
4. **Given** a new page is added to the application without being placed on the allowlist,
   **When** the automated checks run, **Then** that page is verified to reject anonymous requests.
5. **Given** a signed-in user, **When** they open the login page, **Then** they are sent on to the
   home page (or their "return to" address) rather than being asked to sign in again.

---

### User Story 3 - Operations controls who is an administrator through deployment configuration (Priority: P3)

The operations team (SRE) maintains the list of administrator email addresses as a deployment
setting. When the application starts, after the database is brought up to date, it makes the set
of active administrators match that list exactly: every listed address becomes an active
administrator; every administrator no longer on the list is deactivated and immediately loses all
of their sessions. Nobody can grant or revoke administrator rights through the website.

**Why this priority**: Without a user in the database, nobody can sign in, so this is what makes
story 1 usable in every environment. It ranks below the sign-in and protection stories because it
is the mechanism that feeds them rather than a flow people see.

**Independent Test**: Start the application with a list of two addresses and confirm both can
sign in; restart with the same list and confirm nothing changes; restart with one address removed
and confirm that person's sessions are gone and they can no longer obtain a code.

**Acceptance Scenarios**:

1. **Given** a configured administrator list, **When** the application starts, **Then** every
   listed address (trimmed and lowercased) exists as an active administrator.
2. **Given** the administrators already match the list, **When** the application starts again,
   **Then** no user record is created, changed or deactivated.
3. **Given** a signed-in administrator whose address is removed from the list, **When** the
   application restarts, **Then** that user is deactivated, all of their sessions are deleted, and
   their next request is treated as anonymous.
4. **Given** a deactivated administrator, **When** they request a login code, **Then** they see the
   same response as anyone else, but no code is issued or sent.
5. **Given** a previously deactivated administrator is added back to the list, **When** the
   application restarts, **Then** they are active again and can sign in.
6. **Given** the list is reconciled, **When** the result is logged, **Then** the log shows only
   counts (for example created / reactivated / deactivated / unchanged), never email addresses.
7. **Given** the production deployment, **When** the administrator list is empty or contains a
   malformed address, **Then** the application refuses to start and says which setting is wrong
   without echoing its contents.

---

### User Story 4 - Sessions end when they should (Priority: P4)

A signed-in administrator stays signed in across page loads and browser restarts for up to 14
days. They can end the session at any time with **Log out**, which invalidates it on the server,
not just in their browser. A session also stops working the moment its user is deactivated, and
expired sessions and codes are cleaned up automatically.

**Why this priority**: A sign-in that cannot be ended — by the user, by time, or by operations —
is a liability. This story completes the session lifecycle that story 1 starts.

**Independent Test**: Sign in, log out, and confirm that re-using the old session is treated as
anonymous; create a session older than 14 days and confirm it is rejected; deactivate a user and
confirm their existing session stops working on the next request.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they press **Log out**, **Then** their session is deleted
   on the server, their browser's session cookie is cleared, and they are taken to the login page.
2. **Given** a user has logged out, **When** a copy of their old session cookie is replayed,
   **Then** the request is treated as anonymous.
3. **Given** a session created more than 14 days ago, **When** it is used, **Then** it is rejected
   and the user is sent to the login page.
4. **Given** a signed-in user who has been deactivated, **When** they make their next request,
   **Then** it is treated as anonymous.
5. **Given** expired sessions and expired or used codes exist, **When** the automatic cleanup runs,
   **Then** they are removed; and regardless of cleanup timing, an expired session or code is
   never accepted.
6. **Given** a user signs in on two browsers, **When** they log out on one, **Then** only that
   browser's session ends.

---

### User Story 5 - Sign-in resists guessing, flooding and account discovery (Priority: P5)

An attacker cannot learn which email addresses belong to users by watching how the login page
responds, cannot guess a code by trying many values, and cannot use the login page to flood
someone's inbox. Legitimate users who mistype a code a few times can still recover by requesting
a new one.

**Why this priority**: The system will hold student personal data and competition results; the
login flow is its only gate. These protections are cheap now and hard to retrofit, but they
harden story 1 rather than add a new capability, so they follow it.

**Independent Test**: Automated tests submit a known and an unknown email and compare the
responses; exceed the attempt limit for one code and confirm even the correct code is then
rejected; exceed the request limit for one email and confirm no further emails are sent.

**Acceptance Scenarios**:

1. **Given** one registered and one unregistered email, **When** each is submitted on the login
   page, **Then** both receive the same page, the same message and the same status, with no
   systematic difference in response time.
2. **Given** a code has received the maximum number of wrong attempts, **When** any further code is
   submitted for it — including the correct one — **Then** it is rejected, and the user is told to
   request a new code.
3. **Given** an email has reached the maximum number of code requests in the time window, **When**
   another code is requested for it, **Then** no new code is issued or sent, and the response does
   not reveal whether the address is registered.
4. **Given** a single client submits code requests for many different addresses, **When** it
   exceeds the per-client limit, **Then** further requests from that client are refused for the
   rest of the window.
5. **Given** the application restarts, **When** rate-limit counters are checked, **Then** the
   counts from before the restart still apply.
6. **Given** a user requested a new code, **When** they submit an older code for the same email,
   **Then** the older code is rejected.
7. **Given** a wrong, expired, already-used or exhausted code, **When** it is submitted, **Then** the
   same generic "invalid or expired code" message is shown in every case.

---

### User Story 6 - Email delivery fits each environment, and production refuses an unsafe setup (Priority: P6)

A developer runs the application locally with no mail account: the full login email, code
included, is printed to their console. The automated tests use an in-memory outbox and read the
code from it, exercising the real flow with no shortcuts. Production sends real email through a
transactional email provider from a verified sending domain. The login flow itself does not know
or care which of these is in use. The production deployment refuses to start if it would print
emails to the console, if email is not configured, or if any required secret is missing.

**Why this priority**: This makes stories 1–5 practical to develop, test and operate — but it is
supporting infrastructure, so it ranks last. It is still required for the milestone to ship.

**Independent Test**: Start the application locally without email settings and confirm a login
email appears on the console; run the test suite and confirm it reads codes from the outbox and
makes no real network calls to an email provider; start with production-like settings but the
console delivery mode and confirm startup is refused.

**Acceptance Scenarios**:

1. **Given** a local start with no email settings, **When** a code is requested, **Then** the full
   email, including the code, is printed to the application console.
2. **Given** the test suite, **When** a code is requested, **Then** the message is captured in an
   in-memory outbox from which the test reads the code, and no real email is sent.
3. **Given** production, **When** a code is requested for an active user, **Then** a real email is
   delivered to that address from the verified sending domain.
4. **Given** the production deployment, **When** the delivery mode is console or in-memory, or any
   of the session secret, administrator list, email provider key or sender address is missing,
   **Then** the application refuses to start and names the missing or invalid setting without
   revealing any secret value.
5. **Given** any delivery mode other than console, **When** an email is sent or fails to send,
   **Then** neither the message body nor the code appears in logs.
6. **Given** the email provider is unavailable when a code is requested, **When** the request is
   submitted, **Then** the user sees the usual "check your email" response, the failure is logged
   without the code, and the user can request a new code later.

---

### Edge Cases

- **Empty or malformed email on step 1**: the login page shows a validation message and does not
  issue a code or count against rate limits for a real address.
- **Tampered hidden email on step 2**: the code is checked only against codes issued for the
  submitted address; a mismatched address simply yields the generic "invalid or expired code"
  message.
- **Code with surrounding spaces**: surrounding whitespace in the entered code is ignored.
- **Double submission of a correct code** (double click): the first submission signs the user in;
  the second is rejected as already used and must not create a second session or an error page.
- **User deactivated between requesting and submitting a code**: the code is rejected and no
  session is created.
- **Session cookie tampered with or signed with a different secret**: treated as anonymous; no
  error page.
- **Session secret rotated**: all existing sessions stop working and everyone must sign in again;
  outstanding codes are invalid. This is acceptable and documented.
- **"Return to" address pointing to the login or logout step**: after signing in the user goes to
  the home page, never into a loop.
- **"Return to" address that is a protected page with its own query string**: preserved exactly.
- **Logout requested by a plain link (not a form submission)**: logout happens only through a form
  submission; a plain visit does not log the user out.
- **Logout while already anonymous**: harmless; the visitor is taken to the login page.
- **Unknown email that is later added as an administrator**: it can sign in after the next start;
  no stale state from earlier attempts blocks it beyond the normal rate-limit window.
- **Two application instances starting at once during a redeploy**: reconciling the administrator
  list twice concurrently produces the same end state as running it once, with no duplicate users.
- **Administrator list with duplicates or different letter case of one address**: treated as a
  single administrator.
- **Database unavailable during login**: the login page shows a friendly "temporarily unavailable"
  message; no stack trace, no code sent, no session created.
- **Email clients that pre-fetch links**: the email contains only the code (no sign-in link), so
  link scanners cannot consume it.

## Requirements *(mandatory)*

### Functional Requirements

#### Users & administrators

- **FR-001**: The system MUST store users, each with a unique email address (stored trimmed and
  lowercased), a role, an active/inactive flag, and creation and last-modified times. In this
  milestone the only role that exists is administrator, but the role is stored so that milestone 5
  can add student and teacher without reshaping stored data.
- **FR-002**: There MUST be no self-registration. Only users that already exist and are active can
  obtain a code or a session.
- **FR-003**: The administrator list MUST come only from deployment configuration: a
  comma-separated list of email addresses held as a platform secret, never committed to the
  repository.
- **FR-004**: On every start, after bringing the database up to date and before counting the boot,
  the application MUST reconcile users with the administrator list: every listed address (trimmed,
  lowercased, de-duplicated) MUST exist as an active administrator; every active administrator not
  on the list MUST be deactivated and all of their sessions and outstanding codes deleted.
- **FR-005**: Reconciliation MUST be idempotent — running it again with the same list changes
  nothing — and MUST be safe when two instances run it at the same time.
- **FR-006**: Reconciliation MUST log only counts of users created, reactivated, deactivated and
  unchanged, never email addresses.
- **FR-007**: The website MUST NOT offer any way to grant, revoke or edit administrator rights.

#### Login flow

- **FR-008**: The login page MUST have two steps rendered as plain forms that redirect after
  submission: (1) enter email, (2) enter the code. Between the steps the email is carried in a
  hidden form field.
- **FR-009**: On step 1, for an active user, the system MUST issue a one-time code and send it to
  that address by email; for an unknown or inactive address it MUST issue and send nothing.
- **FR-010**: The response to step 1 MUST be identical for known, unknown and inactive addresses
  (same page, message and status), and sending the email MUST happen after the response is
  produced so that response time does not reveal whether an address is registered.
- **FR-011**: A code MUST be a 6-digit number, valid for 20 minutes, and usable at most once.
  Issuing a new code for an address MUST invalidate any earlier unused codes for that address.
- **FR-012**: On step 2, a correct, unexpired, unused code for an active user MUST mark the code as
  used, create a new session and redirect the user to their "return to" address or the home page.
- **FR-013**: A wrong, expired, used or exhausted code, or a code for an inactive or unknown user,
  MUST produce the same generic "invalid or expired code" message and MUST NOT create a session.
- **FR-014**: The code-entry step MUST let the user request a new code or start over with a
  different email, subject to the rate limits.
- **FR-015**: The login email MUST contain the code, how long it is valid, and a note that it can
  be ignored if the recipient did not request it. It MUST NOT contain a sign-in link.

#### Abuse protection

- **FR-016**: Each code MUST accept at most 5 wrong attempts; after that it MUST be invalidated,
  even for the correct value.
- **FR-017**: Code requests MUST be limited to 5 per email address per hour, counted for every
  submitted address whether or not it is registered, so hitting the limit reveals nothing.
- **FR-018**: Code requests MUST also be limited per client (originating network address) to 20
  per hour, to stop one client from flooding many inboxes.
- **FR-019**: Rate-limit counters MUST be stored in the application database, so they survive
  restarts and are shared between instances.
- **FR-020**: When a limit is reached, the user MUST see a friendly "too many attempts, try again
  later" message that is the same for registered and unregistered addresses.

#### Sessions

- **FR-021**: A session MUST be stored on the server and identified by a random token. The browser
  cookie MUST carry that token signed with the application's session secret; the database MUST
  store only a one-way hash of the token.
- **FR-022**: Every request MUST verify that the session exists, is unexpired and belongs to a user
  who is still active; otherwise the request is treated as anonymous.
- **FR-023**: A session MUST expire 14 days after it was created.
- **FR-024**: The session cookie MUST be inaccessible to page scripts, MUST be restricted to
  same-site requests for state-changing submissions, and MUST be sent only over encrypted
  connections in production.
- **FR-025**: **Log out** MUST be a form submission (not a plain link) that deletes the server-side
  session, clears the cookie and redirects to the login page.
- **FR-026**: Expired sessions and expired or used codes MUST be deleted automatically without
  manual action; an expired session or code MUST never be accepted even before cleanup runs.
- **FR-027**: Codes MUST be stored only as a keyed one-way hash using the application's session
  secret; the plain code MUST never be stored.

#### Access protection

- **FR-028**: Every address of the application MUST require a signed-in user by default. Only an
  explicit allowlist is public: the login steps, logout, the liveness check and static assets.
- **FR-029**: An anonymous request to a protected page MUST be redirected (as a "see other"
  redirect) to the login page with the requested address carried as a "return to" parameter.
- **FR-030**: The "return to" address MUST be accepted only if it is a relative path on this site;
  anything else (absolute addresses, protocol-relative addresses, backslash variants, the login or
  logout steps) MUST be replaced by the home page.
- **FR-031**: A signed-in user who opens the login page MUST be redirected onward instead of being
  shown the form again.
- **FR-032**: The header of every page for a signed-in user MUST show their email address and a
  **Log out** button. The home page content MUST otherwise be unchanged from milestone 3.
- **FR-033**: The login pages MUST use plain forms with full-page redirects; no partial-page
  interactivity is introduced in this milestone.
- **FR-034**: The application MUST contain no login bypass of any kind — no magic codes, no
  development-only sign-in addresses, no skip-email switch. Tests of protected pages MAY create a
  session directly through test-only support that is not reachable in a running application.

#### Email delivery

- **FR-035**: The login flow MUST send email only through a single email-sending interface and
  MUST NOT depend on how delivery happens.
- **FR-036**: The delivery mode MUST be selected by a deployment setting with three options:
  **console** (the local default: prints the full email to the application console), **memory**
  (for tests: keeps sent messages in an in-memory outbox readable by tests) and **provider**
  (production: sends through the transactional email provider's web API, not a mail-server
  connection, because free hosting tiers may block outbound mail ports).
- **FR-037**: Only the console mode MAY output an email's body or code. No other mode, and no log
  line, may contain a code, a session token, a secret or an email body.
- **FR-038**: The production sender address MUST belong to a sending domain verified with the
  provider through domain authentication records, so that login emails are not rejected as spam.
- **FR-039**: A failure to send an email MUST NOT change the user-visible response and MUST be
  logged without the code or message body.

#### Configuration & startup

- **FR-040**: The deployment MUST declare four new secrets by name only, with values entered in
  the hosting platform: the session secret, the administrator list, the email provider key and the
  sender address. None of their values may be committed to the repository.
- **FR-041**: On the production platform, the application MUST refuse to start if the delivery
  mode is console or memory (including when it is unset and would default to console), if any of
  the four secrets is missing, if the session secret is shorter than 32 characters, or if the
  administrator list is empty or contains a malformed address. The error MUST name the setting but
  not reveal its value — the same pattern already used for the database location.
- **FR-042**: Locally, the application MUST start with no new settings: email goes to the console,
  a development-only session secret is used with a visible warning, and an empty administrator
  list is allowed with a warning that nobody will be able to sign in.
- **FR-043**: The startup order MUST be: bring the database up to date, then reconcile
  administrators, then count the boot.
- **FR-044**: The README MUST document every new setting (purpose, allowed values, local default,
  production requirement) and how a developer signs in locally by reading the code from the
  console.

#### Verification & scope guard

- **FR-045**: The automated checks MUST include: an end-to-end login using the in-memory outbox; a
  test over the full list of application addresses asserting that every address outside the
  allowlist rejects anonymous requests; equal responses for known and unknown emails;
  reconciliation run twice changing nothing; and an address removed from the administrator list
  losing its sessions and its ability to sign in.
- **FR-046**: Existing page tests from earlier milestones MUST keep passing by signing in through
  the test-only session support rather than through the email step.
- **FR-047**: This milestone MUST NOT introduce student or teacher users, role-based access checks,
  profile pages, or any new data-changing feature beyond login and logout.

### Key Entities *(include if feature involves data)*

- **User**: A person allowed to sign in. Attributes: unique email address (normalized), role (only
  "administrator" in this milestone), active flag, creation time, last-modified time. Users are
  never hard-deleted by reconciliation — they are deactivated — so that later milestones can link
  historical records to them.
- **Login code**: A one-time code issued to a user's email. Attributes: the user or email it was
  issued for, a keyed hash of the code (never the code itself), issue time, expiry time, number of
  wrong attempts, and whether it has been used or invalidated.
- **Session**: A signed-in browser. Attributes: the user it belongs to, a hash of its random token,
  creation time and expiry time. Deleted on logout, on user deactivation and after expiry.
- **Rate-limit counter**: A count of recent code requests or attempts, keyed by email address or by
  client, with its time window. Stored in the database so it survives restarts and is shared
  between instances.
- **Administrator list (configuration)**: The deployment setting listing administrator email
  addresses. It is the only source of truth for who is an administrator; the database is made to
  match it on every start.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can go from opening the site to seeing the home page signed in in
  under 2 minutes, including waiting for the email.
- **SC-002**: In production, 95% of login emails arrive in the recipient's inbox (not the spam
  folder) within 1 minute of the request — verified with at least two different mail providers
  before the milestone is accepted.
- **SC-003**: 100% of application addresses outside the public allowlist turn away anonymous
  requests, as verified by the automated address-list test on every pull request.
- **SC-004**: Responses to known and unknown email addresses on the login page are identical in
  content and status, and their response times show no systematic difference greater than 100 ms
  across 50 attempts each.
- **SC-005**: A code cannot be guessed: no more than 5 attempts are possible per code and no more
  than 5 codes per email per hour — at most 600 guesses per address per day against a million
  possible codes, capping an attacker's chance of success below 0.1% per address per day.
- **SC-006**: Within one restart after an address is removed from the administrator list, that
  person has zero active sessions and cannot obtain a code.
- **SC-007**: Running the administrator reconciliation twice in a row changes zero user records on
  the second run.
- **SC-008**: The repository, the packaged application and a full set of production logs for the
  acceptance check contain zero login codes, session tokens, secrets or email bodies.
- **SC-009**: A developer with a clean checkout can sign in locally in under 15 minutes using only
  the README, with no mail account and no secrets.
- **SC-010**: A production start with any required secret missing, or with console delivery,
  fails 100% of the time and the previously published version keeps serving — verified once
  before the milestone is accepted.

## Assumptions

- **Milestones 1–3 are live** (`specs/001-hello-world-page/`, `specs/002-public-deploy-cicd/`,
  `specs/003-database-questions/`) and are reused unchanged except where this spec extends them.
- **The home page becomes private.** The milestone 3 check "anyone can watch the boot count go up
  across a redeploy" now requires signing in as an administrator. The liveness check stays public
  and database-independent.
- **Email provider**: the technical requirements name Resend, used through its web API, with the
  sending domain's authentication records added at the domain registrar (NIC.UA). This fills the
  constitution's open decision "email delivery service — decide in milestone 4"; `plan.md` records
  it.
- **Setting names** follow the technical requirements (`EMAIL_BACKEND` with values `console`,
  `memory`, `resend`; `SECRET_KEY`; `ADMIN_EMAILS`; `RESEND_API_KEY`; `EMAIL_FROM`). The spec
  refers to them by role; `plan.md` fixes the contract.
- **CSRF**: the technical requirements state that restricting the session cookie to same-site
  requests is sufficient against cross-site request forgery for this milestone, which has only
  login and logout as state-changing actions. This is taken as satisfying constitution Principle V
  for now. The residual risk of "login CSRF" (tricking a browser into signing in as the attacker)
  is accepted because there is nothing yet to leak into an attacker's account. Milestone 5, which
  introduces data-changing pages and HTMX submissions, must revisit this.
- **Per-client rate limit** (FR-018) is added beyond the technical requirements because
  constitution Principle V requires limits "per email and per client". The client is identified by
  its originating network address as reported by the hosting platform's proxy.
- **Numeric defaults** — 6-digit codes, 20-minute validity, 5 attempts per code, 5 code requests
  per email per hour, 20 per client per hour, 14-day absolute session lifetime, 32-character
  minimum session secret — are industry-typical values chosen within the technical requirements;
  `plan.md` may tune them within the same order of magnitude.
- **Session lifetime is absolute**, not sliding: activity does not extend it.
- **Newest code wins**: requesting a new code invalidates older unused ones, to keep only one live
  code per address.
- **Cleanup** runs automatically as part of normal application activity (for example on start and
  during login); no scheduler or new infrastructure is introduced, per the constitution.
- **Deactivation, not deletion**: removing an address from the administrator list deactivates the
  user rather than deleting them.
- **The session secret doubles as the code-hashing key**, as the technical requirements specify;
  rotating it signs everyone out and invalidates outstanding codes.
- **Email addresses are personal data** and are not written to logs by the login flow.

## Dependencies

- Milestones 1–3 merged, deployed and passing their acceptance tests — already satisfied.
- A transactional email provider account with an API key, and a verified sending domain.
- Access to the domain's DNS at the registrar (NIC.UA) to add the provider's domain-authentication
  records.
- **Rollout gate**: the DNS records are verified and all four production secrets are entered in the
  hosting platform **before** this milestone is merged to `main`; otherwise the first automatic
  publish will (correctly) refuse to start.

## Out of Scope

- Student and teacher users, roles and role-based page access (milestone 5)
- Adding, editing or deleting users through the website; profile pages (milestone 7)
- Passwords, "remember me" options, third-party sign-in, multi-factor beyond the emailed code
- Sign-in links in email ("magic links")
- Partial-page interactivity on the login pages
- Changes to home page content, the question list or the database status line
- Account lockout notifications, login history or security dashboards
