# Feature Specification: Roles and Authorization (Milestone 5)

**Feature Branch**: `005-roles-authorization`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "using product-requirements.md and technical-requirements.md create specification for milestone 5."

## Overview

Milestone 5 of the walking skeleton for the Student Competitions application. Milestones 1–4 put
a private page on the public internet. Only administrators can sign in, using a one-time code sent
by email, and every page is closed to anonymous visitors. The application knows *who* is signed
in, but not *what they are allowed to do*: every signed-in person can open every page.

This milestone adds the three roles from the product requirements: **student**, **teacher** and
**administrator**. Each page is opened only to the roles allowed to see it. The aim is the complete
role flow, kept simple: the role pages are placeholders with no features behind them. Five things
become true when this milestone is done:

1. **Operations decides who has which role.** Three lists of email addresses (administrators,
   teachers, students) are set in the deployment configuration, the same way administrators are set
   today. One person can be on several lists and so have several roles. A person on no list cannot
   sign in. Removing a person from a list logs them out everywhere.
2. **A signed-in person always acts in exactly one role.** A person with one role gets it right
   after signing in. A person with several roles picks one after signing in and then lands on the
   page they originally asked for. Until a role is chosen, no other page opens.
3. **Access follows the current role, not every role the person has.** Someone who is both an
   administrator and a student cannot open administrator pages while using the student role.
   Opening a page the current role may not see shows an "access denied" page.
4. **People with several roles can switch.** They change role from the header at any time, without
   signing out. The header always shows the current role next to the application name.
5. **Every page states which roles may open it.** Access is denied by default. A page that does not
   declare its roles is a defect, and the automated checks catch it before it can ship.

Managing users, educational institutions or profiles in the application, and any real feature
behind a role page, are **not** part of this milestone. The teacher and student lists in
configuration are temporary; milestone 7 replaces them with managing teachers and students in the
application.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each role opens exactly its own pages (Priority: P1)

A teacher signs in with the usual email-and-code flow. They hold only the teacher role, so no
extra step appears: they land on the page they asked for (or the home page). The header reads
"Student Competitions · Teacher". The home page shows its usual content, plus links to the two
pages a teacher may open: the teacher area and the staff area. Both open. When the teacher types
the address of the administrator area or the student area, they see an "access denied" page
instead. A student and an administrator have the same experience with their own pages.

**Why this priority**: This is the milestone's reason to exist. Every later milestone (question
bank for teachers, user management for administrators, competitions for students) puts real
features behind these role boundaries. If the boundaries are wrong, those features leak.

**Independent Test**: Configure one person per role. For each person, sign in (or create a session
directly with the test-only support) and request every page in the access table below. Confirm
that each allowed page opens, each other page shows "access denied", and the home page lists
exactly the allowed links.

**Access table** (the contract for this milestone):

| Page | Administrator | Teacher | Student |
|---|---|---|---|
| Home page | ✅ | ✅ | ✅ |
| Administrator area (placeholder) | ✅ | ❌ | ❌ |
| Teacher area (placeholder) | ❌ | ✅ | ❌ |
| Student area (placeholder) | ❌ | ❌ | ✅ |
| Staff area (placeholder) | ✅ | ✅ | ❌ |

**Acceptance Scenarios**:

1. **Given** a person who holds exactly one role, **When** they sign in, **Then** that role becomes
   their current role at once, with no role-choice step, and they land on the page they originally
   requested (or the home page).
2. **Given** a signed-in person using any role, **When** they open a page marked ✅ for that role
   in the access table, **Then** the page opens.
3. **Given** a signed-in person using any role, **When** they open a page marked ❌ for that role,
   **Then** they see an "access denied" page that names their current role and links back to the
   home page. The page does not reveal anything about the content they could not open.
4. **Given** a signed-in person using any role, **When** they open the home page, **Then** it shows
   the same content as in milestone 4, plus links to exactly the role pages their current role may
   open, and no links to any other role page.
5. **Given** a signed-in person on any page after their role has been chosen, **When** the page is
   shown, **Then** the header shows the current role next to the application name in the top left
   corner, as well as their email address and the **Log out** button.
6. **Given** an anonymous visitor, **When** they request any role page, **Then** they are sent to
   the login page (as in milestone 4), not to the "access denied" page.

---

### User Story 2 - Operations assigns roles through deployment configuration (Priority: P2)

The operations team (SRE) maintains three lists of email addresses as deployment settings: one for
administrators (it already exists), one for teachers and one for students. When the application
starts, the stored users are made to match these lists exactly. Everyone on at least one list can
sign in and holds every role whose list they are on. Everyone on no list cannot sign in. Anyone who
loses a role is logged out everywhere. Nobody can grant or revoke a role through the website.

**Why this priority**: Story 1 can only be tried by real teachers and students once they exist.
This story is the mechanism that feeds the role flow, not a flow people see, so it ranks just
below it. It extends the milestone 4 administrator list to all three roles.

**Independent Test**: Start the application with lists that put one address on the administrator
and student lists, one on the teacher list only and one on the student list only. Confirm each can
sign in with the expected roles. Restart with the same lists and confirm nothing changes. Remove
the first address from the student list and confirm that person's sessions are gone and that, after
signing in again, they hold only the administrator role. Remove an address from every list and
confirm that person cannot sign in.

**Acceptance Scenarios**:

1. **Given** the three configured lists, **When** the application starts, **Then** every listed
   address (trimmed and lowercased) exists as an active user who holds exactly the roles whose lists
   contain that address.
2. **Given** an address that appears on two or three lists, **When** the application starts,
   **Then** it is a single person holding two or three roles, not several people.
3. **Given** stored users that already match the lists, **When** the application starts again,
   **Then** no user, role or session is created, changed or deleted.
4. **Given** a signed-in person who is removed from one list but stays on another, **When** the
   changed configuration takes effect, **Then** all of that person's sessions, on every browser,
   are ended. They can sign in again and then hold only their remaining roles.
5. **Given** a signed-in person who is removed from every list, **When** the changed configuration
   takes effect, **Then** all of their sessions are ended, and when they next request a code they
   see the same response as anyone else but receive no code.
6. **Given** a person who is added to an additional list, **When** the changed configuration takes
   effect, **Then** their existing sessions continue, and the new role becomes available to them
   (for example, in the role switcher) on their next page load.
7. **Given** a person who was previously removed from every list, **When** they are added back to
   any list, **Then** they can sign in again with the roles they now hold.
8. **Given** the lists are reconciled, **When** the result is logged, **Then** the log shows only
   counts (for example, people created, reactivated, deactivated, roles added, roles removed,
   unchanged), never email addresses.
9. **Given** any environment, **When** the teacher or student list contains a malformed address,
   **Then** the application refuses to start and names the list and the position of the bad entry
   without echoing its contents, exactly as it already does for the administrator list.

---

### User Story 3 - A person with several roles chooses one after signing in (Priority: P3)

A person who is both a teacher and a student signs in with their code. Instead of landing on the
home page, they are asked which role to use now. The question offers only the roles they hold.
They pick "Teacher" and land on the page they originally asked for, with "Teacher" in the header.
Until they pick, every other page sends them back to the role choice.

**Why this priority**: Without this step, a multi-role person has no current role and cannot
open anything. It is needed for the cases where one person really does hold several roles, such as
an administrator who also teaches. These cases are less common than single-role people (story 1),
so the story ranks below it.

**Independent Test**: Configure one address on the teacher and student lists. Sign in through the
full flow with the in-memory outbox, starting from a request for the teacher area. Confirm that the
role choice appears, offers exactly "Teacher" and "Student", and that choosing "Teacher" lands on
the teacher area. Repeat with a single-role address and confirm no role choice appears.

**Acceptance Scenarios**:

1. **Given** a person who holds two or more roles, **When** they complete sign-in, **Then** they are
   shown the role choice, which offers exactly the roles they hold, in a fixed order
   (administrator, teacher, student).
2. **Given** the person originally requested a specific page before signing in, **When** they choose
   a role, **Then** they land on that page (or the home page if none was requested).
3. **Given** a signed-in person who has not chosen a role yet, **When** they request any page other
   than the role choice or logout, **Then** they are sent to the role choice instead, and the page
   they requested is kept as the place to land after choosing.
4. **Given** the role choice is shown, **When** the person logs out instead of choosing, **Then**
   they are logged out as usual.
5. **Given** a submitted role choice that names a role the person does not hold (a tampered form),
   **When** it is processed, **Then** it is rejected, no role becomes current, and the role choice
   is shown again.
6. **Given** a person who holds exactly one role, **When** they open the role choice page directly,
   **Then** they are sent on to the home page instead.

---

### User Story 4 - A person with several roles switches role from the header (Priority: P4)

An administrator who also takes part in competitions as a student is working in the administrator
role. From the header they switch to "Student" without signing out. The header now reads
"Student Competitions · Student". The home page now shows only the student area link. When they
try the administrator area address, they get "access denied", because what they can open depends
on the role they are using now. They switch back to "Administrator", and the administrator area
opens again.

**Why this priority**: This completes the multi-role experience that story 3 starts. It also
proves the key rule of this milestone: access depends on the current role, not on all roles held.
It is only useful to multi-role people, so it ranks after the role choice.

**Independent Test**: Configure one address on the administrator and student lists. Sign in as
administrator, switch to student from the header and confirm that the administrator area now shows
"access denied" and the home page shows only the student link. Switch back and confirm the
administrator area opens.

**Acceptance Scenarios**:

1. **Given** a signed-in person with several roles, **When** they look at the header on any page
   after a role is chosen, **Then** it offers a way to switch to each of their other roles.
2. **Given** a signed-in person with exactly one role, **When** they look at the header, **Then** it
   shows their role but offers no role switch.
3. **Given** a person switches role from the header, **When** the switch completes, **Then** their
   new role is current, they are still signed in with the same session, they land on the home page,
   and the header shows the new role.
4. **Given** a person who is both administrator and student is using the student role, **When** they
   open the administrator area, **Then** they see "access denied".
5. **Given** a person is signed in on two browsers, **When** they switch role on one, **Then** the
   other browser keeps its own current role.
6. **Given** a switch request that names a role the person does not hold, or that comes from
   another site, **When** it is processed, **Then** it is rejected and the current role is unchanged.

---

### User Story 5 - Every page declares who may open it, and access is denied by default (Priority: P5)

A developer adds a new page in a later milestone. To make it reachable, they must state which roles
may open it, or put it on the short public allowlist from milestone 4. If they forget, the page is
closed to everyone, and the automated checks fail the build and name the page. The same checks
prove, for every page, that each allowed role gets in and every other role gets "access denied".

**Why this priority**: This keeps stories 1–4 true as the application grows. It protects future
milestones rather than adding something people see, so it ranks last, but it is required for the
milestone to ship (constitution Principle IV: "a route without an explicit role requirement is a
defect").

**Independent Test**: An automated test walks the application's full list of pages. It asserts
that every page is either on the public allowlist or declares a non-empty set of roles. For each
declared page it checks that every allowed role gets in and every other role is denied. A
deliberately undeclared test page makes the check fail.

**Acceptance Scenarios**:

1. **Given** the full list of application pages, **When** the automated checks run, **Then** every
   page is either on the public allowlist or declares which roles may open it.
2. **Given** a page that declares its roles, **When** the automated checks run, **Then** each
   declared role is let in and each undeclared role sees "access denied".
3. **Given** a new page is added without declaring roles and without being allowlisted, **When**
   the automated checks run, **Then** they fail and name that page.
4. **Given** a page without a role declaration somehow reaches a running application, **When** any
   signed-in person opens it, **Then** access is denied (deny by default), never granted.
5. **Given** a role page is protected, **When** access is checked, **Then** the check happens on the
   server for every request. Hiding the link on the home page is not what keeps the page closed.

---

### Edge Cases

- **Session from before this milestone** (an administrator signed in on milestone 4, with no
  current role): on the next request it is treated as a person who has signed in but not yet
  chosen a role. A single-role person gets their role automatically. A multi-role person is sent
  to the role choice. Nobody has to sign in again.
- **Current role no longer held** (for example, a request arrives in the moment between the
  configuration change and the session clean-up): every request checks that the person still holds
  their current role. If they don't, the session is ended and the request is treated as anonymous.
- **Same address on several lists with different letter case or spaces**: treated as one person
  with several roles.
- **Duplicate address within one list**: treated as one entry.
- **Address on the teacher or student list only, with an empty administrator list locally**:
  allowed locally (with the existing warning about the administrator list). On the production host
  the administrator list must still be non-empty, as in milestone 4.
- **Empty teacher or student list**: valid in every environment; it simply means nobody holds that
  role.
- **"Return to" address that the chosen role may not open**: after choosing a role, the person
  lands on it and sees "access denied", with the header and role switch available. The role is
  never switched automatically.
- **"Return to" address that points to the role choice, the login or the logout step**: the person
  lands on the home page instead, never in a loop.
- **Opening the role choice page after a role is already chosen** (multi-role person): it is shown
  again, and choosing a role there works exactly like switching from the header.
- **Switching to the role already in use**: harmless; the person lands on the home page with the
  same role.
- **Switch or role choice attempted by a plain link visit rather than a form submission**: nothing
  changes. Choosing and switching roles happen only through form submissions.
- **Page that does not exist**: a signed-in person sees the usual "not found" response, not "access
  denied". An anonymous visitor's experience is unchanged from milestone 4.
- **Access denied for an anonymous visitor**: never shown. Anonymous visitors are sent to the login
  page first; authorization is only checked for signed-in people.
- **Two application instances starting at once during a redeploy**: reconciling the lists twice
  concurrently produces the same end state as running it once, with no duplicate people or roles.
- **A person removed from a list while the previous version of the application is still serving
  during a redeploy**: their sessions are ended when the new version starts. From then on, requests
  served by either version are treated as anonymous, because both read the same sessions.

## Requirements *(mandatory)*

### Functional Requirements

#### Roles & role lists

- **FR-001**: The system MUST support exactly three roles: administrator, teacher and student.
- **FR-002**: A person MUST be able to hold any non-empty combination of the three roles. A person
  is stored once, identified by their normalised email address, whatever the number of their
  roles.
- **FR-003**: The roles a person holds MUST come only from deployment configuration: three
  comma-separated lists of email addresses (administrators, teachers, students), each held as a
  platform secret and never committed to the repository. The administrator list is the one that
  already exists.
- **FR-004**: On every start, after bringing the database up to date and before counting the boot,
  the application MUST reconcile stored people and roles with the three lists. Every listed address
  (trimmed, lowercased, de-duplicated) MUST exist as an active person holding exactly the roles
  whose lists contain it. Every person on no list MUST be deactivated.
- **FR-005**: When reconciliation removes any role from a person, or deactivates them, all of that
  person's sessions MUST be ended, and any outstanding login codes of a deactivated person MUST be
  deleted. When reconciliation only adds roles, existing sessions MUST be kept.
- **FR-006**: Reconciliation MUST be idempotent: running it again with the same lists changes
  nothing. It MUST also be safe when two instances run it at the same time.
- **FR-007**: Reconciliation MUST log only counts, never email addresses.
- **FR-008**: People MUST never be hard-deleted by reconciliation; a person on no list is
  deactivated, so that later milestones can link historical records to them.
- **FR-009**: The website MUST NOT offer any way to grant, revoke or edit any role.
- **FR-010**: Only active people who hold at least one role MAY obtain a login code or a session.
  The login responses for everyone else stay exactly as in milestone 4.

#### Current role

- **FR-011**: Each session MUST carry at most one current role, which belongs to that session only.
  Different browsers of the same person can use different roles.
- **FR-012**: After a successful code check, if the person holds exactly one role, the session MUST
  start with that role as current, and the person MUST be redirected as in milestone 4.
- **FR-013**: After a successful code check, if the person holds several roles, the session MUST
  start with no current role, and the person MUST be redirected to the role choice. The originally
  requested address MUST be kept as the "return to" address.
- **FR-014**: While a session has no current role, every page except the role choice, logout and the
  public allowlist MUST redirect to the role choice, keeping the requested address as the "return
  to" address.
- **FR-015**: The role choice MUST offer exactly the roles the person holds, in the order
  administrator, teacher, student. Choosing one MUST make it current and redirect to the "return
  to" address (or the home page), using the milestone 4 rules for safe "return to" addresses. The
  role choice, login and logout addresses MUST also be replaced by the home page.
- **FR-016**: A person holding exactly one role who opens the role choice MUST be redirected to the
  home page.
- **FR-017**: Every request MUST check that the session's current role is still among the person's
  roles. If it is not, the session MUST be ended and the request treated as anonymous.

#### Switching role

- **FR-018**: For a person holding several roles, the header of every page shown after a role is
  chosen MUST offer a switch to each of their other roles. For a person holding one role, no switch
  is offered.
- **FR-019**: Switching role MUST keep the same session, make the selected role current and
  redirect to the home page. It MUST NOT require signing in again.
- **FR-020**: Choosing and switching roles MUST be form submissions, never plain link visits. A
  submission naming a role the person does not hold MUST be rejected without changing the current
  role.
- **FR-021**: Choosing and switching roles MUST be protected against cross-site request forgery: a
  submission that originates from another site MUST NOT change the current role.

#### Access control

- **FR-022**: Every page outside the milestone 4 public allowlist and the role choice MUST declare
  the non-empty set of roles that may open it. Access MUST be decided only by the session's current
  role, never by the other roles the person holds.
- **FR-023**: Access MUST be checked on the server for every request, after the milestone 4 sign-in
  check. Anonymous requests keep the milestone 4 behaviour (redirect to login). Only signed-in
  people can be denied by role.
- **FR-024**: A page that declares no roles MUST be denied to every signed-in person (deny by
  default).
- **FR-025**: A signed-in person whose current role may not open a page MUST see an "access denied"
  page with a "forbidden" status. The page names the current role, links to the home page, and
  reveals nothing about the denied page's content.
- **FR-026**: The "access denied" page MUST NOT switch role automatically, even when the person
  holds another role that could open the page.

#### Pages

- **FR-027**: The home page MUST be open to all three roles. Its content MUST be unchanged from
  milestone 4, plus a list of links to exactly the role pages the current role may open, according
  to the access table in User Story 1.
- **FR-028**: There MUST be one placeholder page per role (administrator area, teacher area, student
  area), each open only to that role.
- **FR-029**: There MUST be one placeholder staff area page, open to administrators and teachers and
  not to students.
- **FR-030**: Each placeholder page MUST show a title naming the area and one sentence saying that
  its features will arrive in a later milestone. It MUST contain no other features and no personal
  data beyond what the header already shows.
- **FR-031**: Every page shown after a role is chosen MUST display the current role in the header,
  next to the application name in the top left corner. The milestone 4 email address and **Log
  out** button stay in the header.
- **FR-032**: The role choice page MUST show the person's email address and the **Log out** button
  in the header, but no current role, because none has been chosen yet.
- **FR-033**: The new pages MUST use plain forms with full-page redirects. This milestone introduces
  no partial-page interactivity.

#### Configuration & startup

- **FR-034**: The deployment MUST declare two new secrets by name only, the teacher list and the
  student list, with values entered in the hosting platform.
- **FR-035**: In every environment, the application MUST refuse to start if the teacher or student
  list contains a malformed address. The error MUST name the list and the entry's position, but not
  its value, following the existing pattern for the administrator list.
- **FR-036**: The teacher and student lists MAY be empty in every environment. The production rule
  that the administrator list must be non-empty is unchanged.
- **FR-037**: Locally, the application MUST start with no new settings. Unset teacher and student
  lists mean nobody holds those roles.
- **FR-038**: The startup order MUST stay: bring the database up to date, then reconcile people
  and roles, then count the boot.
- **FR-039**: The README MUST document the two new settings (purpose, format, local default,
  production requirement), state that they are temporary until milestone 7, and explain how a
  developer signs in locally as each role.

#### Verification & scope guard

- **FR-040**: The automated checks MUST include:
  - for each role, every page in the access table opens or shows "access denied" as the table says;
  - the home page shows each role only its own links;
  - a multi-role person is asked to choose a role after signing in, and a single-role person is not;
  - a person who is both administrator and student, using the student role, cannot open the
    administrator area;
  - a person removed from one list is logged out everywhere, and a person removed from every list
    can no longer sign in;
  - a sweep over the full list of pages asserting that every page is either publicly allowlisted or
    declares its roles.
- **FR-041**: Tests of role-protected pages MUST be able to create a session with a given current
  role directly, through test-only support that cannot be reached in a running application. Existing
  page tests MUST keep passing.
- **FR-042**: This milestone MUST NOT introduce any feature behind the role pages, nor managing
  users, educational institutions or profiles. It MUST NOT change the login or code rules from
  milestone 4, except for adding the role step after a successful code check.

### Key Entities *(include if feature involves data)*

- **Person (user)**: someone allowed to sign in. Attributes from milestone 4 (unique normalised
  email address, active flag, creation and last-modified times) remain. The single role attribute
  is replaced by the set of roles the person holds. An active person holds at least one role.
- **Role assignment**: the fact that a person holds a given role (administrator, teacher or
  student). It is derived only from the configuration lists. A person has at most one assignment
  per role.
- **Session**: a signed-in browser, as in milestone 4 (person, token hash, creation and expiry
  time), now also carrying the **current role**. The current role is empty until a role is chosen,
  and is always one of the person's roles once set.
- **Role lists (configuration)**: the three deployment settings (administrators, teachers,
  students). Together they are the only source of truth for who holds which role. The stored people
  and roles are made to match them on every start.
- **Page access rule**: the set of roles each page declares it may be opened by. It is part of the
  application itself, not of stored data. The access table in User Story 1 lists the rules for this
  milestone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 15 role-and-page combinations in the access table behave as specified
  (open or "access denied"), as verified by automated checks on every pull request.
- **SC-002**: 100% of application pages are either on the public allowlist or declare their roles.
  A page added without either is caught by the automated checks before merge, every time.
- **SC-003**: A single-role person goes from entering their code to their requested page with zero
  extra steps compared with milestone 4.
- **SC-004**: A multi-role person goes from entering their code to their originally requested page
  in exactly one extra step (choosing a role).
- **SC-005**: A multi-role person can switch role from any page after a role is chosen in a single
  action, without signing in again, and sees the new role in the header right away.
- **SC-006**: Once a configuration change that removes a role is live, the affected person has zero
  active sessions. If they were removed from every list, they cannot obtain a login code.
- **SC-007**: Running the reconciliation twice in a row changes zero people, roles or sessions on
  the second run.
- **SC-008**: Logs from reconciliation and from role choice, switching and denial contain zero email
  addresses.
- **SC-009**: A developer with a clean checkout can sign in locally as each of the three roles in
  under 15 minutes, using only the README.
- **SC-010**: Administrators signed in before this milestone ships keep working after it ships,
  without being asked to sign in again (single-role administrators see no new step).

## Assumptions

- **Milestones 1–4 are live** (`specs/001-hello-world-page/` to `specs/004-email-otp-auth/`). They
  are reused unchanged except where this spec extends them: the email-code sign-in, sessions, the
  public allowlist, the "return to" rules and the administrator reconciliation.
- **Setting names**: the new lists follow the existing `ADMIN_EMAILS` pattern and are expected to
  be `TEACHER_EMAILS` and `STUDENT_EMAILS`, declared in the deployment blueprint without values
  (`sync: false`). The spec refers to them by role; `plan.md` fixes the contract.
- **"Takes effect at once"**: role lists are deployment configuration, so a change becomes live when
  the hosting platform restarts the application with the new values. Reconciliation runs at that
  start, before the new version serves traffic, and ends the affected sessions in the shared
  database. No separate polling or live re-reading of configuration is introduced.
- **Any role removal logs out everywhere**: the technical requirements say that removing a person
  from a list logs them out everywhere. This applies even when the person keeps other roles and
  even when the removed role was not current in a given session. Adding a role does not log anyone
  out.
- **How roles are stored** may change, as milestone 4 allowed ("milestone 5 may change how roles are
  stored"). The single role column becomes a set of roles per person. `plan.md` chooses the shape
  and the migration, which must keep existing administrators.
- **Landing page after a switch** is the home page, because the page the person was on may not be
  open to the new role. **Landing page after the role choice** is the originally requested page, as
  the technical requirements say.
- **Cross-site forgery**: the milestone 4 spec asked milestone 5 to revisit CSRF. Choosing and
  switching roles are the only new state-changing submissions, and they change only which of the
  person's own roles is active. The session cookie is already restricted to same-site requests.
  FR-021 adds that a cross-site submission must not change the role. `plan.md` picks the mechanism
  (for example, checking the request's origin, or a per-session form token) and records it in the
  Constitution Check against Principle V. Milestone 6, which adds the first data-changing pages,
  must apply the same protection to them.
- **"Access denied"** uses the standard "forbidden" response status and the existing friendly error
  page style. It is shown only to signed-in people.
- **Display names**: roles are shown as "Administrator", "Teacher" and "Student". Placeholder pages
  are named "Administrator area", "Teacher area", "Student area" and "Staff area". Page addresses
  are fixed in `plan.md`.
- **Header format**: "Student Competitions · <Role>" in the top left corner. The email address,
  the role switch (if any) and **Log out** are on the right.
- **Sessions from milestone 4** have no current role. They are upgraded on their next request
  rather than ended, so administrators are not signed out by this deployment.
- **Email addresses are personal data**, and the role flow keeps them out of logs, as in milestone 4.

## Dependencies

- Milestone 4 merged, deployed and passing its acceptance tests. This is already satisfied.
- **Rollout gate**: if real teachers or students should be able to sign in right after the release,
  the teacher and student lists are entered in the hosting platform before this milestone is merged
  to `main`. Leaving them empty is safe: the application starts, and only administrators can sign
  in.

## Out of Scope

- Managing users, teachers, students or educational institutions through the website (milestone 7)
- Profile pages for any role (milestone 7)
- Linking teachers to educational institutions and scoping students by institution (milestone 7)
- Any real feature behind the role pages: question bank (milestone 6), competitions (milestones
  8–11)
- Per-competition access rights for teachers (milestone 8)
- Granting or revoking any role through the website in this milestone. Administrator rights stay
  configuration-only permanently (constitution Principle IV).
- Remembering a person's last-used role between sign-ins
- Partial-page interactivity on any page
- Changes to the email-code sign-in rules, rate limits or session lifetime from milestone 4
