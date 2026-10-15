# Feature Specification: User Management with Consent — Teachers (Milestone 8)

**Feature Branch**: `008-teacher-management-consent`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "create specification for the milestone 8 from docs/requirements/milestones.md file. Use also product-requirements.md and technical-requirements.md for refearence."

## Overview

Milestone 8 of the walking skeleton for the Student Competitions application. Until now, operations
grants every role through three lists of email addresses in the deployment configuration
(milestone 5). The **Teachers** tab of the administrator area (milestone 6) is still a placeholder,
and the educational institutions from milestone 7 are not linked to anyone.

This milestone lets administrators invite and manage teachers inside the application, under one
rule: **no personal data about a person is stored until that person agrees to it.** Five things
become true when this milestone is done:

1. **Administrators invite teachers by email.** The invitation lives only inside an encrypted,
   tamper-proof link in the email. The application keeps nothing from the invitation form.
2. **A teacher's data is stored only when they press I agree.** The acceptance page shows exactly
   what will be stored and the consent text. Agreeing stores the data and a consent record that
   proves the agreement.
3. **Administrators manage teachers.** The **Teachers** tab lists current teachers. Each teacher
   is linked to one or more educational institutions with a Read or Write access level and has a
   **Can create competitions** setting. Administrators edit these details and remove teachers.
4. **Every person controls their own data.** Everyone can see their own profile. Anyone whose data
   was stored on consent can withdraw consent from the profile, or, without signing in, delete
   their data through an emailed link.
5. **The teacher and student role lists are retired.** Only the administrator list remains in the
   deployment configuration. Teachers come only from accepted invitations.

The flow is built so that milestone 9 adds students as one more invitable role without changing
the invitation, acceptance, consent record, profile or withdrawal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator invites a teacher, who accepts (Priority: P1)

An administrator opens the **Teachers** tab and clicks **Invite teacher**. They enter the email
`olena@example.org`, the first name "Olena" and the last name "Kovalenko". From the list of
institutions, each shown as "Name (Region)", they pick "Kyiv Polytechnic Institute (Kyiv)" with
**Write** access and "Lviv Academy (Lviv)" with **Read** access, and check **Can create
competitions**. They press **Send invitation** and see "Invitation sent to olena@example.org". The
application has stored nothing about Olena.

Olena receives a plain-text email. It says who invites her, that the role is teacher, which
institutions with which access levels, that she will be able to create competitions, that nothing
is stored unless she accepts, the link and when it expires. She opens the link. The page shows the
inviter, the role, her email, her names, the two institutions with their access levels, the
competitions setting, the consent text and an **I agree** button. Opening the page changed
nothing. She presses **I agree**. Her account is created with the teacher role, both institution
links, the setting and a consent record. She lands on the sign-in page with her email already
filled in, signs in with an emailed code, and sees all of it on her profile.

**Why this priority**: This is the heart of the milestone. Without it, no teacher can exist once
the teacher list is retired, and the consent rule cannot be demonstrated.

**Independent Test**: As an administrator, submit the invitation form, read the link from the
in-memory outbox, open it, check that no stored data contains the invited email or names, press
**I agree**, then check the stored user, role, links, setting and consent record. Sign in as the
teacher and open the profile.

**Acceptance Scenarios**:

1. **Given** an administrator on the **Teachers** tab, **When** they click **Invite teacher**,
   **Then** a form opens with email, first name, last name, an institution picker with an access
   level per picked institution, and an unchecked **Can create competitions** box.
2. **Given** active institutions in active regions, a deactivated institution, and an active
   institution in a deactivated region, **When** the invitation form opens, **Then** the picker
   offers only the active institutions in active regions, each shown as "Name (Region)".
3. **Given** a valid form with two institutions (Write and Read) and the setting checked, **When**
   the administrator submits it, **Then** an invitation email is sent and the page shows
   "Invitation sent to <email>".
4. **Given** an invitation was just sent, **Then** no stored data contains the invited email, first
   name or last name, and there is no list of pending invitations.
5. **Given** the invitation email, **Then** it is plain text and states the inviter, the role, each
   institution with its access level, whether it includes creating competitions, that nothing is
   stored unless the person accepts, the link and its expiry date and time.
6. **Given** a valid invitation link, **When** it is opened (as a mail scanner would), **Then**
   nothing is stored or changed, and the page shows the inviter, the role, the email, the names, the
   institutions with access levels by their current names, the competitions setting, the consent
   text and **I agree**. Nothing on the page can be edited.
7. **Given** the acceptance page, **Then** under **I agree** it says that a wrong detail is fixed by
   asking the inviter for a new invitation, or by accepting and asking the inviter to correct it.
8. **Given** the acceptance page for an email that belongs to no user, **When** the person presses
   **I agree**, **Then** an active user is created with the teacher role, the invited names, both
   institution links with their access levels, the setting, and a consent record.
9. **Given** a successful acceptance, **Then** the person is not signed in and lands on the sign-in
   page with their email filled in.
10. **Given** the new teacher signs in, **When** they open their profile, **Then** it shows their
    email and names, the teacher role, both institutions with access levels, **Can create
    competitions** and the consent record with the accepted text.

---

### User Story 2 - Acceptance is refused when the invitation is no longer valid (Priority: P1)

Some invitations must not succeed. Olena's link was edited by hand: the page says the invitation
cannot be accepted. A second link is 8 days old: the page says "This invitation has expired; ask
for a new one." For a third, the administrator who sent it has since been removed from the
administrator list, so **I agree** is refused with the same neutral message, which does not say
which check failed. A fourth names an institution that was deactivated after the invitation was
sent, and is refused the same way.

Most importantly, a removal always wins over an older invitation. Petro was a teacher; an
administrator removed him. Petro still has an invitation that was sent before the removal. **I
agree** on that old link is refused. An invitation sent after the removal works.

**Why this priority**: Without these checks, an old or forged link could grant the teacher role or
undo a removal or a withdrawal of consent. They are part of the minimum safe flow.

**Independent Test**: Create links that are tampered, expired, from a removed inviter, for a
deleted or deactivated institution, for an institution in a deactivated region, and older than a
removal or withdrawal. Check that each is refused with the right message and stores nothing. Check
that a newer invitation succeeds.

**Acceptance Scenarios**:

1. **Given** a link whose content was changed in any way, **When** it is opened or accepted,
   **Then** the neutral failure message is shown and nothing is stored.
2. **Given** a link older than 7 days, **When** it is opened or accepted, **Then** the page shows
   "This invitation has expired; ask for a new one." and nothing is stored.
3. **Given** the inviter is no longer an active administrator, **When** **I agree** is pressed,
   **Then** the neutral failure message is shown and nothing is stored.
4. **Given** any invited institution was deleted or deactivated, or its region was deactivated,
   after the invitation was sent, **When** **I agree** is pressed, **Then** the neutral failure
   message is shown and nothing is stored.
5. **Given** an invited institution was renamed after the invitation was sent, **When** the link
   is opened, **Then** the page shows the new name, and **I agree** succeeds.
6. **Given** an invitation issued before the person's teacher role was removed, **When** **I
   agree** is pressed, **Then** it is refused, whether the person is now deactivated or still active
   with another role.
7. **Given** an invitation issued before the person withdrew consent or deleted their data,
   **When** **I agree** is pressed, **Then** it is refused.
8. **Given** an invitation issued after the removal or withdrawal, **When** **I agree** is pressed,
   **Then** it succeeds.
9. **Given** an acceptance request that carries extra or changed form fields besides the link,
   **When** it is processed, **Then** exactly what the link holds is stored and the extra fields are
   ignored.

---

### User Story 3 - An administrator manages teachers (Priority: P1)

The **Teachers** tab lists current teachers sorted by last name: name, email, institutions with
access levels, **Can create competitions** and the date of consent. The administrator opens Olena's
page and lowers her access to "Kyiv Polytechnic Institute" from Write to Read, unchecks **Can
create competitions** and adds a third institution. The Lviv link is unchanged. Later, "Lviv
Academy" is deactivated; Olena's page still shows the link, marked as deactivated. The
administrator can remove it but cannot add it again.

Another teacher has left. The administrator presses **Remove**, confirms, and the teacher is gone
from the list. The person loses the teacher role and its details. Having no other role, they are
deactivated and signed out everywhere. Their email, names and consent records stay until they
delete their data.

**Why this priority**: Institution links, access levels and the competitions setting are what
milestones 9, 11 and 14 rely on, and removing a teacher is the only way to end access now that the
role list is gone.

**Independent Test**: With accepted teachers in place, check the list contents and order, edit
names, links, access levels and the setting, check that an unchanged link stays unchanged, check
the refusal of invalid edits, and remove a teacher.

**Acceptance Scenarios**:

1. **Given** no teachers, **When** the administrator opens the **Teachers** tab, **Then** it shows
   "No teachers yet" and **Invite teacher**.
2. **Given** several teachers, **When** the tab opens, **Then** they are listed sorted by last name
   ignoring case, each with name, email, institutions with access levels, **Can create
   competitions** and the date of consent.
3. **Given** a teacher's page, **When** the administrator changes one link's access level and the
   setting and saves, **Then** those change and every other link stays exactly as it was.
4. **Given** a teacher linked to an institution that was deactivated later, **When** the page
   opens, **Then** that link is shown as deactivated, can be removed, and saving other changes keeps
   it.
5. **Given** a teacher's page, **When** the administrator submits an edit that adds a deactivated
   institution, an institution in a deactivated region, or an unknown institution, **Then** the edit
   is refused with an error and nothing changes.
6. **Given** a teacher's page, **When** the administrator submits an edit with no institutions, an
   access level other than Read or Write, or an invalid name, **Then** the form shows again with the
   error and the entered values, and nothing changes.
7. **Given** a teacher's page, **Then** the email is shown but cannot be edited.
8. **Given** an institution linked to a teacher, **When** the administrator tries to delete it
   (milestone 7), **Then** the deletion is refused as "in use".
9. **Given** a teacher with no other role, **When** the administrator removes them and confirms,
   **Then** the teacher role, institution links and setting are removed, the person is deactivated
   and signed out everywhere, and they disappear from the list. Their email, names and consent
   records stay.
10. **Given** a teacher who is also an administrator, **When** they are removed as a teacher,
    **Then** they lose the teacher role and its details, stay active as an administrator, and are
    signed out everywhere.

---

### User Story 4 - A person sees their profile and withdraws consent (Priority: P2)

Any signed-in person can open their own read-only profile. Olena's profile shows her email and
names, her roles, her institutions with access levels, **Can create competitions**, and her consent
records, each with the text she accepted. An administrator from the deployment configuration who
never accepted an invitation sees only their email and the administrator role.

Olena decides to leave. She presses **Withdraw consent** and confirms. Her teacher role and details
are removed, her names are erased and her email is replaced, so the account no longer identifies
anyone. Her consent records stay. She is deactivated, signed out everywhere and sees a confirmation
page. She can no longer sign in.

**Why this priority**: The right to see and withdraw is part of the consent promise, but it only
matters once data exists (stories 1–3).

**Independent Test**: Sign in as each kind of person and open the profile. As a teacher, withdraw
consent and check the erasure, the sign-out and that sign-in no longer works. As an administrator
who also accepted a teacher invitation, withdraw and check that the administrator role and email
stay.

**Acceptance Scenarios**:

1. **Given** a signed-in person in any role, **When** they open their profile, **Then** it shows
   their email, names (if stored), roles, for a teacher the institutions with access levels and
   **Can create competitions**, and each consent record with the text of the version accepted.
2. **Given** the profile, **Then** nothing on it can be edited, and it says that corrections to
   teacher data go through an administrator.
3. **Given** a person with data stored on consent and not yet erased, **Then** the profile shows
   **Withdraw consent**. **Given** a person without such data, **Then** it is not shown.
4. **Given** **Withdraw consent**, **When** it is pressed, **Then** a confirmation step says what
   will be erased and which roles removed. Nothing changes until the person confirms.
5. **Given** a teacher with no other role confirms withdrawal, **Then** the teacher role and
   details are removed, names erased, email replaced, consent records kept, the person is
   deactivated and signed out everywhere, and a confirmation page is shown.
6. **Given** the person withdrew, **When** they try to sign in with their old email, **Then** they
   cannot sign in (the usual sign-in behaviour for an unknown address).
7. **Given** an administrator from the deployment configuration who also holds the teacher role
   through consent, **When** they withdraw, **Then** they keep the administrator role and their
   email, lose the teacher role and their names, leave the **Teachers** tab and are signed out
   everywhere.
8. **Given** a removed teacher who is still an administrator, **When** they open their profile,
   **Then** **Withdraw consent** is shown, because their names are still stored.

---

### User Story 5 - A person deletes their data without signing in (Priority: P2)

Petro was removed as a teacher and cannot sign in any more. On the sign-in page he clicks **Delete
my data**, enters his email and sees "If this email is registered, we have sent you a link." He
receives an email that explains what the link does and that it expires in one hour. Opening the
link changes nothing: the page shows the data to be erased, the roles to be removed and a
**Delete my data** button. He presses it. His data is erased exactly as on withdrawal, and the page
confirms the deletion. Opening the link again shows "This link has expired; request a new one."

**Why this priority**: People who can no longer sign in, such as removed teachers, still have the
right to erase their data. This completes the consent promise.

**Independent Test**: Request deletion for a known address, an unknown address and an already
erased address, and check that all three get the same answer and only the known one gets an email.
Open the link, check that nothing changed, press the button, check the erasure. Check that a used
and an expired link are refused.

**Acceptance Scenarios**:

1. **Given** the sign-in page, **Then** it shows a **Delete my data** link, also to anonymous
   visitors.
2. **Given** the deletion request form, **When** any email is submitted, **Then** the page always
   shows "If this email is registered, we have sent you a link."
3. **Given** an address with data stored on consent and not yet erased, **When** deletion is
   requested, **Then** an email is sent that says what the link does and when it expires.
   **Given** an unknown address, an already erased address, or an administrator without consent
   data, **Then** no email is sent.
4. **Given** a valid deletion link, **When** it is opened, **Then** nothing changes, and the page
   shows the data to be erased, the roles to be removed and **Delete my data**. For an administrator
   from the deployment configuration, it also says that the administrator role and email stay.
5. **Given** the deletion page, **When** **Delete my data** is pressed, **Then** the data is erased
   as on withdrawal and a confirmation page is shown.
6. **Given** a link that was already used, or is older than one hour, **When** it is opened or
   submitted, **Then** the page shows "This link has expired; request a new one." Any other failure
   shows one neutral message.
7. **Given** more deletion requests for one address than the limit allows, **Then** the page still
   shows the same answer and no further email is sent.

---

### User Story 6 - An administrator who also teaches invites themselves (Priority: P3)

An administrator who also teaches enters their own address on the invitation form and goes through
the same steps as anyone else. After **I agree** they hold both roles, carry the names from the
invitation, and are their own inviter in the consent record. Later they withdraw consent: they keep
the administrator role and their email and leave the **Teachers** tab.

**Why this priority**: An uncommon but expected case that shows the flow has no shortcuts for
administrators.

**Independent Test**: As an administrator, invite your own address, accept, check both roles, the
names and the consent record's inviter, then withdraw and check the result.

**Acceptance Scenarios**:

1. **Given** an administrator invites their own address, **When** they accept, **Then** they gain
   the teacher role and the invited names, keep the administrator role, and the consent record names
   them as the inviter.
2. **Given** the acceptance, **Then** their current session is not ended, and the teacher role is
   now offered in the role switch.
3. **Given** they then withdraw consent, **Then** they keep the administrator role and email, lose
   the teacher role and names, and no longer appear on the **Teachers** tab.

---

### User Story 7 - The teacher and student role lists are retired (Priority: P2)

Operations removes the teacher and student lists from the deployment configuration. On the next
start, teacher and student roles that came from those lists are removed. People left with no role
are deactivated and their emails replaced, as on withdrawal. From now on, the administrator list
only grants and removes the administrator role, and deactivates a person only when no role is left.

**Why this priority**: Required for the consent rule to hold (no one gains a role without consent
except administrators), but mechanical once the flow exists.

**Independent Test**: Start the application with users that hold roles from the old lists, check
the result, and check that the administrator list neither touches the teacher role nor deactivates a
person who still holds it.

**Acceptance Scenarios**:

1. **Given** people who held the teacher or student role from the old lists, **When** this
   milestone is deployed, **Then** those roles are removed, people left with no role are deactivated
   and their emails replaced, and everyone affected is signed out.
2. **Given** a teacher who accepted an invitation and is not on the administrator list, **When**
   the administrator list is reconciled, **Then** their teacher role and active status are untouched.
3. **Given** an administrator who is also a teacher, **When** their address is removed from the
   administrator list, **Then** they lose the administrator role, stay active as a teacher, and are
   signed out everywhere.
4. **Given** the deployment configuration, **Then** the teacher and student lists are no longer
   read, and no one holds the student role.

---

### User Story 8 - Only the right people reach each page (Priority: P3)

A teacher, a student and an administrator using another role each try to open the **Teachers** tab,
the invitation form and a teacher's page; each sees "access denied". An anonymous visitor is sent
to sign in. Everyone, in any role, can open their own profile. The invitation and data deletion
pages are public.

**Why this priority**: Milestone 5 already makes access deny-by-default, so this story confirms
that the new pages follow the rules.

**Independent Test**: For each role and an anonymous visitor, request every new page and send every
new form, and check the outcome.

**Acceptance Scenarios**:

1. **Given** a person using the teacher or student role, **When** they open or submit any teacher
   management page or action, **Then** they see "access denied" and nothing changes.
2. **Given** a person using any role, **When** they open their profile, **Then** it shows their own
   data only.
3. **Given** an anonymous visitor, **When** they open the profile or any teacher management page,
   **Then** they are sent to sign in.
4. **Given** an anonymous visitor or any signed-in person, **When** they open an invitation or data
   deletion link, **Then** the page acts on the person named in the link, never on the signed-in
   session.

---

### Edge Cases

- **Email normalization**: the invited email is trimmed and lowercased as at sign-in, so an
  invitation to "  Olena@Example.org " matches the user `olena@example.org`.
- **Name exactly 100 characters after trimming**: accepted. 101: refused. A name with a tab, line
  break or other control character is refused. Spaces at the start and end are removed; inner
  spaces are kept.
- **Same institution picked twice** in one form: refused, nothing is sent or changed.
- **Invitation to someone who already holds the teacher role**: the email is sent. **I agree**
  changes nothing, stores no consent record, and the page says the person is already a teacher.
- **I agree pressed twice**, or two tabs submitting at the same moment: only one user, one role and
  one consent record result. The second press sees "already a teacher".
- **Two invitations for the same person**: each is valid on its own. The first accepted one wins;
  the second then sees "already a teacher". A later invitation never cancels an earlier one.
- **Invitation accepted by an inactive user** who was removed earlier: allowed only if the
  invitation was issued after the removal. The user is reactivated with the teacher role and the
  invited names and details.
- **Removal and invitation at the same instant**: the removal wins. An invitation is accepted only
  if it was issued strictly after the latest removal or withdrawal.
- **Consent text changed between opening the link and pressing I agree**: the acceptance is not
  stored. The page is shown again with the new text, saying the text has changed.
- **Invitation email fails to send**: the form shows an error with the entered values, nothing is
  stored, and the attempt still counts toward the rate limit.
- **Rate limit reached for an inviter or an invited address**: the form shows an error saying to
  try again later, with the entered values. No email is sent.
- **Signed-in person opens someone else's invitation**: the page shows the invited person's data
  and acts only on them. The signed-in session is unchanged.
- **Signed-in person withdraws or deletes via link**: their sessions are ended, including the one
  in the current browser.
- **Teacher edited while signed in**: changing names, links, access levels or the setting does not
  sign the teacher out.
- **Teacher removed while editing**: a later save shows a friendly "teacher not found" page.
- **Teacher page for an unknown person, or for a user who is not a current teacher**: friendly
  "teacher not found" page.
- **Edit leaves the teacher with no institutions**: refused; at least one link is required.
- **Deactivated institution link and re-adding**: a link to an institution that became
  unavailable is kept on save and shown as deactivated. Once removed, it cannot be added back until
  the institution and its region are active again.
- **Withdrawal when the email is also on the administrator list**: the administrator role and email
  stay; names are erased; the person stays active.
- **Address re-added to the administrator list after its owner withdrew**: the withdrawn account
  no longer carries the address, so a new administrator user is created.
- **Deletion link requested twice**: each link is valid on its own until it expires or until the
  data is erased; after erasure, every remaining link shows "This link has expired; request a new
  one."
- **Deletion requested for an address whose data was already erased**: same answer, no email.
- **Profile of an administrator with no consent data**: shows the email and the administrator role,
  no names, no consent records and no **Withdraw consent**.
- **Page reload after a successful action** (invite, edit, remove, accept, withdraw, delete): does
  not repeat the action.

## Requirements *(mandatory)*

### Functional Requirements

#### Personal data and the consent rule

- **FR-001**: A person's email, first name and last name MUST be treated as personal data. For
  invited roles, they MUST be stored only after the person presses **I agree** on the acceptance
  page.
- **FR-002**: Before acceptance, the system MUST NOT store any part of the invitation: no email,
  no names, no institution choices, no setting, and no record of a pending invitation.
- **FR-003**: The only exception is a keyed one-way hash of an email address, which cannot be
  turned back into the address without a server-side secret. It MAY be stored only for rate limits
  and for the invitation cut-off (FR-034).
- **FR-004**: No log line MUST contain an email address, a first or last name, or an invitation or
  deletion link.

#### Built for reuse

- **FR-005**: The invitation, acceptance, consent record, profile, withdrawal and data deletion MUST
  work the same for every invitable role. Each invitable role MUST define: its invitation form and
  validation, who may invite it and for which institutions, its extra checks at acceptance, the
  details stored on acceptance, and its consent text. This milestone defines only the teacher role.

#### Teacher details

- **FR-006**: Each teacher MUST be linked to one or more educational institutions. Each link MUST
  have an access level, **Read** or **Write**. A newly picked institution MUST default to **Read**.
- **FR-007**: Each teacher MUST have one **Can create competitions** setting, unchecked by default,
  covering all their institutions.
- **FR-008**: Only an administrator MUST be able to set the institution links, access levels and
  setting, when inviting and from the teacher's page.
- **FR-009**: Institution pickers MUST show each institution as "Name (Region)" and MUST offer only
  active institutions in active regions. The system MUST refuse any other institution, including an
  unknown one, a deactivated one, or one in a deactivated region, when submitted directly.
- **FR-010**: An access level other than Read or Write, no institution, or the same institution
  twice MUST be refused.
- **FR-011**: A link to an institution that became unavailable after it was added MUST be kept,
  shown as deactivated, and kept when other changes are saved. It MAY be removed but MUST NOT be
  added again while the institution or its region is deactivated.
- **FR-012**: An institution linked to a teacher MUST NOT be deletable. The milestone 7 in-use
  check MUST count teacher links.
- **FR-013**: In this milestone, access levels and the setting are only stored and shown. Their
  enforcement belongs to milestones 9, 11 and 14.

#### Inviting a teacher

- **FR-014**: The **Teachers** tab MUST offer **Invite teacher**, which opens a form with: email,
  first name, last name, institutions with an access level each, and **Can create competitions**.
- **FR-015**: The email MUST be validated and normalized as at sign-in. First and last names MUST
  be trimmed, 1–100 characters, and free of control characters.
- **FR-016**: Submitting a valid form MUST send the invitation email and show "Invitation sent to
  <email>". An invalid form MUST show again with the errors and the entered values, and no email is
  sent.
- **FR-017**: If sending fails, the form MUST show an error with the entered values. Nothing from
  the form is kept.
- **FR-018**: Invitations MUST be rate-limited per inviter (20 per hour) and per invited address
  (5 per hour). A refused submission MUST show the form again with an error and the entered values,
  and MUST NOT send an email.
- **FR-019**: Each invitation MUST be valid on its own for 7 days from issue. Issuing a new
  invitation MUST NOT affect earlier ones. There is no list of pending invitations and no way to
  cancel one.
- **FR-020**: The invitation link MUST carry the whole invitation: role, email, names, institutions
  with access levels, the setting, the inviter and the issue time. It MUST be encrypted, so its
  contents cannot be read from the address, and tamper-proof, so any change makes it invalid.
- **FR-021**: The invitation email MUST be plain text and MUST state: who invites, the role, the
  institutions with access levels, whether it includes creating competitions, that nothing is
  stored unless the person accepts, the link and its expiry. Links MUST NOT be click-tracked, and
  the system MUST keep no copy of the email.
- **FR-022**: An administrator MAY invite their own address and MUST go through the same steps as
  anyone else.

#### Accepting

- **FR-023**: Opening an invitation link MUST change nothing.
- **FR-024**: The acceptance page MUST show the inviter, the role, exactly the data that will be
  stored (institutions by their current names), the current consent text for the role and an
  **I agree** button. Nothing on it MUST be editable. Under the button it MUST say that a wrong
  detail is fixed by asking the inviter for a new invitation, or by accepting and asking the inviter
  to correct it.
- **FR-025**: **I agree** MUST be refused if the inviter is no longer an active administrator.
- **FR-026**: **I agree** MUST be refused if any invited institution was deleted or deactivated, or
  its region was deactivated.
- **FR-027**: **I agree** MUST be refused if, at or after the moment the invitation was issued, the
  person lost the teacher role or withdrew consent (including deleting their data), whether or not
  they are still active.
- **FR-028**: Otherwise, acceptance MUST store the names and teacher details from the link, and:
  - when no user has the email: create an active user with the teacher role
  - when an active user without the teacher role has the email: add the role
  - when an inactive user has the email: reactivate them with the role
  - when the user already holds the teacher role: change nothing, store no consent record, and say
    so on the page
- **FR-029**: Exactly what the link holds MUST be stored. Any other submitted field MUST be ignored.
- **FR-030**: Every acceptance that changes something MUST store a consent record: the user, the
  role, the consent text version, the time of acceptance, the inviter and the invitation's issue
  time.
- **FR-031**: Acceptance MUST be safe against double submission: concurrent or repeated presses
  produce at most one role grant and one consent record.
- **FR-032**: Acceptance MUST NOT sign anyone in and MUST NOT end any session. It MUST lead to the
  sign-in page with the email filled in.
- **FR-033**: An expired link MUST show "This invitation has expired; ask for a new one." Any other
  failure MUST show one neutral message that does not say which check failed.
- **FR-034**: To enforce FR-027 after the person's data may have been erased, the system MUST keep,
  per keyed hash of an email address and per role, the time of the latest role removal or
  withdrawal (the invitation cut-off). It MUST NOT keep the email itself for this purpose.
- **FR-035**: If the consent text of the role changed between opening the page and pressing **I
  agree**, the acceptance MUST NOT be stored, and the page MUST show again with the new text and a
  note that it changed.

#### Consent text

- **FR-036**: Each invitable role MUST have its own versioned consent text stating what is stored,
  why, who can see it, which external service delivers the emails, and how to withdraw.
- **FR-037**: Any wording change MUST create a new version. Earlier versions MUST be kept, and each
  consent record MUST refer to the version accepted. Placeholder wording is acceptable in this
  milestone.

#### Managing teachers

- **FR-038**: The **Teachers** tab (`/admin/teachers`) MUST replace its placeholder with the list of
  current teachers, sorted by last name ignoring case, then first name. Each row MUST show name,
  email, institutions with access levels (deactivated ones marked), **Can create competitions** and
  the date of consent. An empty list MUST show "No teachers yet".
- **FR-039**: Each teacher MUST have a page where an administrator edits the names (validated as in
  FR-015), institutions, access levels and **Can create competitions**. The email MUST be shown and
  MUST NOT be editable.
- **FR-040**: Saving an edit MUST change only what was changed. Links that were not changed MUST
  stay exactly as they were. An invalid edit MUST show the form again with the errors and the
  entered values, and nothing changes.
- **FR-041**: Editing a teacher MUST NOT sign them out.
- **FR-042**: **Remove** MUST ask for confirmation. Removing MUST take away the teacher role, the
  institution links and the setting, update the invitation cut-off, deactivate the person if no role
  is left, and sign the person out everywhere. Email, names and consent records MUST stay until the
  person deletes their data. Users MUST never be hard-deleted.

#### Profile

- **FR-043**: Every signed-in person MUST be able to open their own read-only profile from the
  header. It MUST show their email, names (if stored), roles, for a teacher the institutions with
  access levels and **Can create competitions**, and each consent record with the time accepted, the
  role and the full text of the version accepted.
- **FR-044**: The profile MUST say that corrections to teacher data go through an administrator.

#### Withdrawing consent

- **FR-045**: The profile MUST show **Withdraw consent**, with a confirmation step, to every person
  whose data was stored on consent and not yet erased, including a removed teacher who is still an
  administrator.
- **FR-046**: Withdrawing MUST:
  - remove every role granted by consent (here, teacher) and its details
  - update the invitation cut-off for each such role
  - erase the first and last names
  - replace the email with a value that identifies no one, unless the person holds the
    administrator role from the deployment configuration, in which case the email stays
  - keep the consent records
  - deactivate a person left with no role
  - sign the person out everywhere and show a confirmation page
- **FR-047**: The administrator role from the deployment configuration MUST NOT be affected by
  withdrawal.
- **FR-048**: A person who withdrew MAY be invited again; only an invitation issued after the
  withdrawal can be accepted.

#### Deleting data without signing in

- **FR-049**: The sign-in page MUST show a **Delete my data** link, open to anyone.
- **FR-050**: The deletion request form MUST always answer "If this email is registered, we have
  sent you a link.", whatever the address. Requests MUST be rate-limited per address (5 per hour).
- **FR-051**: The deletion email MUST be sent only when the address has data stored on consent and
  not yet erased. It MUST say what the link does and when it expires. No copy MUST be kept.
- **FR-052**: The deletion link MUST work once and only within one hour of its issue. Opening it
  MUST change nothing.
- **FR-053**: The deletion page MUST show the data to be erased, the roles to be removed, for an
  administrator from the deployment configuration that this role and address stay, and a **Delete
  my data** button. Pressing it MUST erase as **Withdraw consent** does and then confirm the
  deletion.
- **FR-054**: An expired or used deletion link MUST show "This link has expired; request a new
  one." Any other failure MUST show one neutral message.
- **FR-055**: Invitation and deletion pages MUST act on the person named in the link, never on the
  signed-in session.

#### Retiring the role lists

- **FR-056**: The teacher and student lists MUST be removed from the deployment configuration and
  MUST no longer be read.
- **FR-057**: The administrator list MUST grant and remove only the administrator role. It MUST
  deactivate a person only when no role is left, and MUST NOT touch the teacher role.
- **FR-058**: On deployment of this milestone, teacher and student roles granted by the old lists
  MUST be removed. People left with no role MUST be deactivated and their emails replaced as on
  withdrawal. All affected people MUST be signed out. After this, nobody holds the student role
  until milestone 9.

#### Shared page and action behaviour

- **FR-059**: Every action that changes data (invite, edit, remove, accept, withdraw, request and
  confirm deletion) MUST be a form submission that passes the existing cross-site request check.
  Opening a page or following a link MUST NEVER change anything.
- **FR-060**: After a successful action, the person MUST be sent to a result page, so reloading does
  not repeat the action.
- **FR-061**: Pages opened from an invitation or deletion link MUST NOT pass the link to other
  sites, such as through the referring-page address.
- **FR-062**: Rate-limit and send failures MUST show friendly messages without internal error
  details.

#### Access

- **FR-063**: The **Teachers** tab, the invitation form and every teacher page and action MUST be
  open only to a person using the administrator role (milestone 5 rules).
- **FR-064**: The profile and withdrawal MUST be open to every signed-in person, in any role, and
  MUST act only on that person.
- **FR-065**: The invitation pages and the data deletion pages MUST be public.
- **FR-066**: Every new page and action MUST declare which roles may open it, so the existing
  automated check of all routes covers them.

#### Verification and scope

- **FR-067**: Automated tests MUST cover every item of the milestone 8 _Test:_ list in
  `docs/requirements/milestones.md`, including the end-to-end invitation through the in-memory
  outbox, the absence of personal data before acceptance, every refusal at acceptance, the
  invitation cut-off, self-invitation, withdrawal, data deletion, the reconcile of the
  administrator list only, and logs free of emails, names and links.
- **FR-068**: This milestone MUST NOT add any student feature (milestone 9), a list of pending
  invitations, cancelling an invitation, changing a person's email, or self sign-up.

### Key Entities *(include if feature involves data)*

- **User** (existing): a person who can sign in. Gains first and last name, stored only on
  consent. The email may be replaced on withdrawal. Never hard-deleted.
- **Role assignment** (existing): a role held by a user. The administrator role comes from the
  deployment configuration; the teacher role comes only from an accepted invitation.
- **Teacher details**: per teacher, the **Can create competitions** setting.
- **Teacher institution link**: a teacher, an educational institution and an access level (Read
  or Write). Removed with the teacher role. Prevents deletion of the institution.
- **Invitation** (not stored): role, email, names, role details, inviter, issue time. Exists only
  inside the encrypted link.
- **Consent text version**: a role, a version identifier and the full text. Never changed once
  published.
- **Consent record**: user, role, consent text version, time accepted, inviter, invitation issue
  time. Kept after withdrawal and data deletion as proof of consent.
- **Invitation cut-off**: a keyed hash of an email address, a role and the time of the latest
  removal or withdrawal. Contains no readable personal data.
- **Data deletion link** (mostly not stored): issued for one user, valid for one hour, usable once.
  Only what is needed to refuse reuse is stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can send a teacher invitation in under 2 minutes, and the invited
  person can accept it in under 1 minute.
- **SC-002**: Before acceptance, 0 stored records contain the invited email, first name or last
  name.
- **SC-003**: 100% of tampered, expired, outdated or otherwise invalid invitations are refused and
  store nothing.
- **SC-004**: 100% of invitations issued before a role removal or withdrawal are refused, and an
  invitation issued after it succeeds.
- **SC-005**: After withdrawal or data deletion, 0 stored records contain the person's names, and
  their email remains only when it comes from the administrator list.
- **SC-006**: Known, unknown and already erased addresses get identical answers on the data
  deletion form, and only the known address receives an email.
- **SC-007**: 0 log lines captured during the test suite contain an email address, a name or an
  invitation or deletion link.
- **SC-008**: In the automated access check, 100% of teacher management pages and actions refuse
  every role except administrator, and refuse an administrator who is using another role.
- **SC-009**: Reloading the page after any successful action never repeats it.
- **SC-010**: All tests from milestones 1–7 still pass, apart from tests of the old **Teachers**
  placeholder and of the retired teacher and student lists, which this milestone replaces.

## Assumptions

- **Who invites is shown as** the inviter's name and email when names are stored, otherwise the
  email alone, so the invited person knows whom to contact.
- **Rate limits** follow the milestone 4 pattern: 20 invitations per inviter per hour, 5 per
  invited address per hour, and 5 deletion requests per address per hour. Per-address limits use
  the keyed hash, never the address itself.
- **The invitation form does not check** whether the address already belongs to a teacher. The
  acceptance page handles that case.
- **The deletion email states** that it can be ignored if the person did not ask for it.
- **The profile is reached from the header**, through the signed-in email.
- **The consent date on the Teachers tab** is the time of the latest teacher consent record.
- **The email replacement value** on withdrawal is unique per user, so later records (such as
  results) can still refer to the account.
- **No real users exist** until all milestones are done (product requirements). Retiring the role
  lists needs no gentle transition; tests of the old lists may be replaced.
- **Rotating the server-side secret** makes outstanding invitation and deletion links invalid and
  resets the hash-based limits and cut-offs. This is acceptable and documented, as for sessions in
  milestone 4.
- **Placeholder consent text** is used until the product owner supplies the final wording before
  real users arrive.

## Dependencies

- **Milestone 7**: educational institutions, regions, their statuses, availability for selection
  and the institution in-use check.
- **Milestone 6**: the administrator area and the **Teachers** tab address.
- **Milestone 5**: roles, the current role, role switching, "access denied", ending sessions on
  role removal and the automated route check.
- **Milestone 4**: email delivery (including the in-memory outbox for tests), sign-in, email
  validation, sessions, rate limits and the cross-site request check.
- **Later milestones that depend on this one**: milestone 9 adds students to the same flow;
  milestones 9, 11 and 14 enforce access levels and **Can create competitions**.

## Out of Scope

- Anything about students: milestone 9.
- A list of pending invitations or cancelling an invitation. Known limitation: an invitation sent by
  mistake stays valid for 7 days; if it is accepted, the administrator removes the person.
- Changing a person's email.
- Self sign-up.
- Enforcing access levels and **Can create competitions**: milestones 9, 11 and 14.
- Final consent wording.
