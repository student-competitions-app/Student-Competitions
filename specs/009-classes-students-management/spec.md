# Feature Specification: User Management with Consent — Classes and Students (Milestone 9)

**Feature Branch**: `009-classes-students-management`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: milestone 9 of `docs/requirements/milestones.md` ("User management with
consent: classes and students"), with `product-requirements.md` and the milestone 8 specification
(`specs/008-teacher-management-consent/spec.md`) as reference.

## Overview

Milestone 9 of the walking skeleton for the Student Competitions application. After milestone 8,
administrators invite teachers and link them to educational institutions with **Read** or **Write**
access, but those access levels are only stored. Nobody holds the student role, and the teacher page
is still a placeholder.

This milestone brings students in, under the same rule as milestone 8: **no personal data about a
person is stored until that person agrees to it.** Six things become true when this milestone is
done:

1. **Teachers keep the classes of their institutions.** A class is a named group of students inside
   one institution, with a year of study. Teachers with Write access create, edit, deactivate,
   activate and delete classes.
2. **Teachers invite students into classes.** The student role joins the milestone 8 invitation and
   consent flow as one more invitable role. A student's institution and class are stored only when
   the student presses **I agree**.
3. **Teachers manage their students.** With Write access, a teacher edits a student's names, moves
   them to another class of the same institution, or removes them. With Read access, a teacher only
   sees the classes and students.
4. **Access levels from milestone 8 are enforced.** A teacher reaches only the available
   institutions they are linked to, and changes data only where they have Write access.
5. **Deactivation works as a chain.** Regions hold institutions, institutions hold classes, classes
   hold students. Deactivating any of them hides everything below it, and the students below are
   blocked until it is activated again.
6. **Names already held are kept.** When a person who already is a teacher or a student accepts any
   invitation, their current names stay. This changes milestone 8 for teacher invitations too.

Everything else in the invitation, acceptance, profile, withdrawal and data deletion flow works as in
milestone 8.

## Clarifications

### Session 2026-10-19

- Q: In the administrator area, should objects below a deactivated object be hidden too (FR-014)?
  → A: No. Hiding applies to classes and students only; milestones 7 and 8 stay unchanged in the
  administrator area.
- Q: Deactivating a region or an institution now signs out and hides every student below it.
  Should those actions get a confirmation (FR-017)? → A: Yes, the same wording as the class
  confirmation: "its students will be signed out and hidden until it is activated again".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher chooses a class and manages classes (Priority: P1)

Olena is a teacher linked to "Kyiv Polytechnic Institute" (Kyiv) with **Write** access and to "Lviv
Academy" (Lviv) with **Read** access. She opens the teacher area and lands on the **Students** tab.
Three drop-down lists sit in a row: **Region**, **Educational institution** and **Class**. Only
**Region** is enabled, and the page says "Select a region to continue". She picks "Kyiv", then "Kyiv
Polytechnic Institute — Write". The institution has no classes yet, so the **Class** list offers
only **+ Add class**. She adds "KN-21" with year of study 2; the new class is selected straight
away, and the page says "No students in this class yet".

Later she renames the class to "KN-22" and changes its year to 3. At the end of the year she
deactivates a graduated class. The confirmation says that its students will be signed out and hidden
until the class is activated again. In "Lviv Academy", where she has Read access, she sees the
classes and their students but has no actions at all.

**Why this priority**: Classes are where students live. Without choosing an institution and a class,
no student can be invited, seen or managed.

**Independent Test**: As a teacher with one Write and one Read institution, walk the three lists,
check every message, create, edit, deactivate, activate and delete classes in the Write
institution, check every validation error, reload and bookmark the page, and check that the Read
institution shows no actions.

**Acceptance Scenarios**:

1. **Given** a teacher, **When** they open `/teacher`, **Then** the **Students** tab
   (`/teacher/students`) opens, highlighted, next to the **Competitions** tab
   (`/teacher/competitions`), which is a placeholder.
2. **Given** the **Students** tab with nothing selected, **Then** **Region** is enabled,
   **Educational institution** and **Class** are disabled, and the page says "Select a region to
   continue".
3. **Given** the teacher's links, **Then** **Region** offers only active regions that hold at least
   one active institution the teacher is linked to, sorted by name ignoring case.
4. **Given** a selected region, **Then** **Educational institution** offers the teacher's active
   institutions of that region, sorted by name ignoring case, each marked "Read" or "Write", and the
   page says "Select an educational institution to continue".
5. **Given** a selected institution, **Then** **Class** offers all its classes, active and
   deactivated, sorted by name ignoring case, each with its year of study and deactivated ones
   marked, and the page says "Select a class to see its students". With Write access, the last entry
   is **+ Add class**; with Read access, there is no such entry.
6. **Given** Write access, **When** the teacher chooses **+ Add class** and submits the name "KN-21"
   and year 2, **Then** the class is created in the selected institution and selected.
7. **Given** the class form, **When** the name is empty, longer than 200 characters after trimming,
   contains a control character, or matches another class of the same institution ignoring case
   (active or deactivated), or the year of study is not a whole number from 1 to 12, **Then** the form
   shows again with the error (for a duplicate, "already exists in this institution") and the
   entered values, and nothing is stored.
8. **Given** a class "KN-21" in one institution, **When** a class "KN-21" is created in another
   institution, **Then** it is accepted.
9. **Given** a selected class with Write access, **When** the teacher uses **Edit** and changes the
   name and the year of study, **Then** both change. A change of case alone is a valid rename.
10. **Given** an active class with Write access, **When** the teacher chooses **Deactivate**,
    **Then** a confirmation says that the class's students will be signed out and hidden until the
    class is activated again. Nothing changes until the teacher confirms.
11. **Given** a deactivated class, **Then** the bar shows it marked as deactivated with
    **Activate**, no **Add student**, and the list area says "This class is deactivated; its students
    are hidden until it is activated again".
12. **Given** a class with no students, **When** the teacher chooses **Delete** and confirms,
    **Then** the class is deleted. The confirmation names the class and its institution.
13. **Given** a class with at least one student, **When** the teacher confirms its deletion, **Then**
    it is refused. The refusal suggests deactivation instead, unless the class is already
    deactivated.
14. **Given** a selected region, institution and class, **When** the page is reloaded or opened from
    a bookmark, **Then** the same selection is shown. After any class action, the affected class stays
    selected.
15. **Given** a teacher not linked to any available institution, **When** they open the
    **Students** tab, **Then** all three lists are disabled and the page says "You are not linked to
    any educational institution".
16. **Given** Read access to the selected institution, **Then** the class bar and the student list
    have no actions.

---

### User Story 2 - A teacher invites a student, who accepts (Priority: P1)

Olena selects "KN-21" and presses **Add student**. She enters `taras@example.org`, "Taras" and
"Shevchenko" and presses **Send invitation**. Nothing about Taras is stored. Taras receives a
plain-text email: who invites him, that the role is student, the institution with its region, the
class with its year of study, that nothing is stored unless he accepts, the link and when it
expires. On the acceptance page he sees the same data, the student consent text, the note "If you
are already a teacher or a student, your current names are kept." and **I agree**. He agrees, lands
on the sign-in page with his email filled in, signs in, and his profile shows the institution, the
class and the year of study.

**Why this priority**: This is the heart of the milestone: it is the only way a student can exist,
and it shows that the milestone 8 flow takes a second role without being rebuilt.

**Independent Test**: As a Write teacher, invite a student into an active class, read the link from
the in-memory outbox, check that no stored data contains the email, the names or the enrolment, open
the link, press **I agree**, then check the user, the student role, the enrolment and the consent
record. Sign in as the student and open the profile.

**Acceptance Scenarios**:

1. **Given** an active class selected with Write access, **When** the teacher presses **Add
   student**, **Then** a form opens with email, first name and last name for that class.
2. **Given** a valid form, **When** it is submitted, **Then** an invitation email is sent, the page
   confirms it, and no stored data contains the invited email, names, institution or class.
3. **Given** the form, **When** the email or a name is invalid (milestone 8 rules), **Then** the form
   shows again with the error and the entered values, and no email is sent.
4. **Given** an email that belongs to a person holding the student role, in any institution,
   **When** the form is submitted, **Then** it shows again with "This email already belongs to a
   student" and the entered values, and no email is sent. The message never names the institution
   or the class.
5. **Given** an email that belongs to a teacher, an administrator, or an inactive person who no
   longer holds the student role, **When** the form is submitted, **Then** the invitation is sent.
6. **Given** a teacher has sent 100 student invitations within the last hour, **When** they submit
   another, **Then** the form shows again with an error saying to try again later, and no email is
   sent. **Given** an address has received 5 invitations within the last hour, **Then** the same
   applies.
7. **Given** the invitation email, **Then** it is plain text and states the inviter, the student
   role, the institution with its region, the class with its year of study, that nothing is stored
   unless the person accepts, the link and its expiry.
8. **Given** a valid student invitation link, **When** it is opened, **Then** nothing changes, and the
   page shows the inviter, the role, the email, the names, the institution with its region, the class
   and its year of study by their current values, the current student consent text, "If you are
   already a teacher or a student, your current names are kept." and **I agree**.
9. **Given** the acceptance page for an email that belongs to no user, **When** **I agree** is
   pressed, **Then** an active user is created with the invited names, the student role, the
   enrolment in the invited institution and class, and a consent record. The person lands on the
   sign-in page with the email filled in.
10. **Given** the student signs in, **Then** they use the student role, and their profile shows
    their email, names, the student role, the institution with its region, the class, the year of
    study and the student consent record with its text.
11. **Given** the student consent text, **Then** it never names an institution or a class, and the
    consent record does not store them.

---

### User Story 3 - A student acceptance is refused when the invitation is no longer valid (Priority: P1)

Taras's classmate has a link from a teacher whose access to the institution was lowered to Read; **I
agree** is refused with the neutral message. Another invitation is for a class that was deactivated
after it was sent, and a third is for a class in an institution that the administrator deactivated;
both are refused the same way. A fourth was sent before the student was removed from the class; it
is refused too. A link whose class was only renamed still works and shows the new name.

**Why this priority**: Without these checks an old or forged link could put a student into a class
their inviter no longer manages, or undo a removal or a withdrawal.

**Independent Test**: Create student invitation links, then change the inviter or the class in each
of the ways below, and check that **I agree** is refused with the right message and stores nothing.
Check the cases that must still succeed.

**Acceptance Scenarios**:

1. **Given** a link changed in any way, **Then** the neutral message from milestone 8 is shown and
   nothing is stored. **Given** a link older than 7 days, **Then** the page shows "This invitation
   has expired; ask for a new one."
2. **Given** the inviter is no longer active, no longer holds the teacher role, is no longer linked to
   the invited institution, or now has only Read access to it, **When** **I agree** is pressed,
   **Then** the neutral message is shown and nothing is stored.
3. **Given** the invited class was deleted, or the class, its institution or its region was
   deactivated, after the invitation was sent, **When** **I agree** is pressed, **Then** the neutral
   message is shown and nothing is stored.
4. **Given** the class was renamed or its year of study changed after the invitation was sent,
   **When** the link is opened, **Then** the page shows the current values, and **I agree** succeeds.
5. **Given** an invitation issued before the person lost the student role or withdrew consent,
   **When** **I agree** is pressed, **Then** it is refused, whether or not the person is still active.
   An invitation issued after that succeeds.
6. **Given** the person became a student after the invitation was sent, **When** **I agree** is
   pressed, **Then** nothing changes, no consent record is stored, and the page says they are already
   a student.
7. **Given** the student consent text changed between opening the page and pressing **I agree**,
   **Then** nothing is stored and the page shows again with the new text, saying it changed.
8. **Given** an acceptance request with extra or changed form fields, **Then** exactly what the link
   holds is used and the extra fields are ignored.
9. **Given** a student invitation, **Then** the milestone 8 checks for teacher invitations (inviter
   is an active administrator, invited institutions are selectable) are not applied to it.

---

### User Story 4 - A teacher edits and removes students (Priority: P1)

The class "KN-21" lists its students by last name, each with name and email. Olena opens Taras's
**Edit**, corrects a typo in his first name and moves him to "KN-22", an active class of the same
institution; no new consent is asked. Another student has left the institution. Olena presses
**Remove**; the confirmation names the student, the class and the institution. After she confirms,
the student is gone from the list, loses the student role, is signed out everywhere and, having no
other role, is deactivated.

**Why this priority**: Keeping the class lists correct is the everyday job of a teacher, and removal
is the only way to end a student's access.

**Independent Test**: With accepted students in place, check the list contents and order, edit
names and class, check refused edits, remove a student, and check the stored result.

**Acceptance Scenarios**:

1. **Given** an active class with students, **Then** they are listed sorted by last name ignoring
   case, each with name and email. **Given** an active class without students, **Then** it shows "No
   students in this class yet".
2. **Given** Write access, **Then** each student has **Edit** and **Remove**. **Given** Read access,
   **Then** neither is shown.
3. **Given** a student's **Edit**, **Then** it offers first name, last name and a class chosen from
   the active classes of the same institution. The email and the institution are shown and cannot be
   edited.
4. **Given** **Edit**, **When** the teacher saves new names and another active class, **Then** both
   change, the student stays signed in, and no new consent is asked.
5. **Given** **Edit**, **When** an invalid name, a deactivated class or a class of another
   institution is submitted, **Then** the edit is refused and nothing changes.
6. **Given** a student who holds no other role, **When** the teacher removes them and confirms,
   **Then** the enrolment is deleted, the student role is removed, the invitation cut-off is
   updated, the person is deactivated and signed out everywhere, and their email, names and consent
   records stay.
7. **Given** a student who is also a teacher, **When** they are removed as a student, **Then** they
   keep the teacher role, stay active and are signed out everywhere.
8. **Given** a removed student, **When** an invitation issued after the removal is accepted, **Then**
   the person becomes a student again, with a new enrolment and a new consent record.

---

### User Story 5 - Deactivation blocks the students below it (Priority: P2)

The administrator deactivates the region "Odesa". Every student of every class in every institution
of that region is blocked: they are signed out everywhere, teachers no longer see them, and a
blocked student who has no other role cannot sign in, as if their address were unknown. A blocked
student can still delete their data through **Delete my data** on the sign-in page. Nothing about
the students, classes or institutions themselves changes. When the region is activated again,
everything below it whose own status is active is available again, and the students can sign in and
are seen by their teachers.

**Why this priority**: The chain rule decides who can sign in and what teachers see, but it builds on
classes and students already existing (stories 1–4).

**Independent Test**: With students in classes of several institutions and regions, deactivate a
class, an institution and a region in turn, and check sign-out, sign-in, the teacher's view, the
profile, data deletion and the effect of reactivation.

**Acceptance Scenarios**:

1. **Given** a class, its institution or its region is deactivated, **Then** every student of the
   affected classes is signed out everywhere at that moment.
2. **Given** a blocked student with no other role, **When** they try to sign in, **Then** sign-in
   behaves exactly as for an unknown address.
3. **Given** a blocked student who also holds another role, **When** they sign in, **Then** they are
   not offered the student role, and their profile shows the enrolment marked as deactivated.
4. **Given** a blocked student, **When** they request **Delete my data**, **Then** they receive the
   link and can erase their data as in milestone 8.
5. **Given** a teacher, **Then** an unavailable institution and everything below it is not shown or
   offered on the **Students** tab, and opening it through the page address shows "access denied".
6. **Given** a deactivated class in an available institution, **Then** the class is still listed and
   marked, so it can be activated again, but its students are not shown and cannot be opened, edited
   or removed, also through the page address.
7. **Given** the deactivated object is activated again, **Then** every object below it whose own
   status is active is available again: its students can sign in with the student role and teachers
   see them. No status or other data changed while it was deactivated.
8. **Given** a class that becomes unavailable, **Then** no new student can be invited into it, moved
   into it or accept an invitation into it.

---

### User Story 6 - Names already held are kept on acceptance (Priority: P2)

Olena, a teacher, is also invited as a student in an evening course under the name "O. Kovalenko".
On acceptance she keeps her current names, gains the student role and keeps the teacher role. The
other way round, a student invited as a teacher by an administrator also keeps their names. A new
person, an inactive person and an administrator without these roles get the names from the
invitation, as before.

**Why this priority**: It prevents one person's names from flipping with every invitation, but it
only matters for people who hold both roles.

**Independent Test**: Accept student and teacher invitations for each kind of person and check
which names are stored and which roles result.

**Acceptance Scenarios**:

1. **Given** a teacher accepts a student invitation, **Then** their names stay as they were, they
   keep the teacher role and gain the student role and the enrolment.
2. **Given** a student accepts a teacher invitation, **Then** their names stay as they were, they
   keep the student role and gain the teacher role and its details.
3. **Given** a new person, an inactive person, or an administrator who holds neither the teacher nor
   the student role accepts an invitation of either role, **Then** the names from the invitation are
   stored.
4. **Given** the acceptance page of either role, **Then** it says "If you are already a teacher or a
   student, your current names are kept."

---

### User Story 7 - A student sees their profile and withdraws consent (Priority: P2)

Taras opens his profile from the header. It shows his email and names, the student role, the
institution with its region, the class and its year of study, and his student consent record. It
says that corrections to his student data go through a teacher of his institution. He presses
**Withdraw consent**; as in milestone 8, his names are erased, his email is replaced, his student
role and enrolment are removed, his consent records stay and he is signed out everywhere.

**Why this priority**: The milestone 8 rights apply to students unchanged; this story checks that the
enrolment is shown and erased with the rest.

**Independent Test**: Sign in as a student, open the profile, withdraw, and check the result.
Repeat through **Delete my data** without signing in.

**Acceptance Scenarios**:

1. **Given** a signed-in student, **When** they open the profile, **Then** it shows their email,
   names, roles, the institution with its region, the class, the year of study and the student
   consent records with their texts.
2. **Given** a student's profile, **Then** it says that corrections to student data go through a
   teacher of their institution. **Given** a person who is also a teacher, **Then** it still says that
   corrections to teacher data go through an administrator.
3. **Given** a student withdraws consent or deletes their data through the emailed link, **Then** the
   enrolment is deleted together with the milestone 8 erasure, and they disappear from every
   teacher's view.
4. **Given** a person who is both a teacher and a student withdraws, **Then** both roles and their
   details are removed, as in milestone 8.

---

### User Story 8 - An administrator deletes an institution that holds classes (Priority: P3)

An institution was created by mistake, and a teacher already added two empty classes to it. The
administrator removes the teacher's link and deletes the institution. The confirmation says that its
classes will be deleted too. Another institution has an enrolled student; its deletion is refused.

**Why this priority**: Rare, but it changes the milestone 7 in-use check.

**Independent Test**: Delete institutions with no classes, with empty classes, with an enrolled
student and with a teacher link, and check each outcome.

**Acceptance Scenarios**:

1. **Given** an institution with classes but no enrolled students and no teacher links, **When** the
   administrator deletes it, **Then** the confirmation says that its classes will be deleted too, and
   after confirmation the institution and its classes are gone.
2. **Given** an institution with at least one enrolled student, blocked or not, **When** the
   administrator confirms its deletion, **Then** it is refused as "in use", suggesting deactivation
   instead.
3. **Given** an institution linked to a teacher, **Then** its deletion is still refused (milestone 8).

---

### User Story 9 - Only the right people reach each page (Priority: P3)

A teacher with Read access to "Lviv Academy" types the address of an **Edit** for one of its
students and gets "access denied". She changes the address to a class of an institution she is not
linked to, and again gets "access denied". An administrator, a student and an anonymous visitor
cannot open the teacher area at all.

**Why this priority**: Milestone 5 already makes access deny-by-default; this story proves that the
new pages and the new Read/Write rules follow it, including through hand-made addresses and forms.

**Independent Test**: For each role, an anonymous visitor, and teachers with Write, Read and no link
to an institution, request every new page and submit every new form, including hand-made addresses
and form values, and check the outcome.

**Acceptance Scenarios**:

1. **Given** a person using the administrator or student role, **When** they open or submit any
   teacher area page or action, **Then** they see "access denied" and nothing changes. **Given** an
   anonymous visitor, **Then** they are sent to sign in.
2. **Given** a teacher, **When** the page address or a submitted form names a region, institution,
   class or student they cannot reach (not linked, unavailable, unknown, or a student of a
   deactivated class), **Then** they see "access denied" and nothing changes.
3. **Given** a teacher with Read access, **When** they submit any class or student management
   action for that institution, **Then** they see "access denied" and nothing changes.
4. **Given** a teacher whose access was lowered from Write to Read, or whose link was removed,
   while they had a form open, **When** they submit it, **Then** they see "access denied".
5. **Given** an administrator, **Then** the administrator area offers no way to manage classes or
   students.

---

### Edge Cases

- **Year of study**: 1 and 12 are accepted; 0, 13, a decimal, text or an empty value are refused.
  Several classes of one institution may share a year.
- **Class name rules**: the subject-name rules from milestone 6 apply: trimmed, 1–200 characters,
  no control characters, unique within the institution ignoring case, including deactivated classes
  and non-Latin letters.
- **Changing the year of a class** changes the year of study of all its students at once; their
  profiles show the new year.
- **A student is never in two places**: one person holds at most one enrolment. Two invitations into
  different classes are each valid on their own; the first accepted wins and the second shows
  "already a student".
- **Blocked student invited elsewhere**: a blocked student still holds the student role, so the
  invitation form refuses their email with "This email already belongs to a student". They can be
  invited elsewhere only after their class is available again and a teacher removes them, or after
  they delete their data.
- **Moving to another institution** is a removal followed by a new invitation, which asks for consent
  again (product rule: a student agrees again each time they join an institution).
- **A teacher invites their own address as a student**: allowed, with the same steps as anyone else.
  On acceptance they keep their names and gain the student role. They then appear in the class list
  and can be edited or removed like any student.
- **Class deactivated while a student is signed in**: the student is signed out everywhere at once;
  their next request asks them to sign in.
- **Class deactivated and activated again quickly**: the students were signed out and simply sign in
  again; nothing else changes.
- **Institution or region reactivated while its class stays deactivated**: the class's students stay
  blocked.
- **Deleting a class at the same moment a student accepts into it**: either the deletion is refused
  because the class now holds a student, or the acceptance is refused because the class is gone;
  never a student without a class.
- **I agree pressed twice**: at most one enrolment, one role grant and one consent record.
- **Class selected in the address does not belong to the institution in the address**, or the
  institution does not belong to the region: "access denied".
- **Deleting the selected class**: afterwards the institution stays selected and no class is
  selected.
- **Editing a student while they are signed in**, including moving them to another class: they stay
  signed in.
- **Student removed while the teacher has their Edit open**: a later save shows "access denied",
  because the student is no longer reachable.
- **Teacher linked only to institutions that are deactivated or in deactivated regions**: sees "You
  are not linked to any educational institution" with disabled lists.
- **Rate limits across roles**: a person who is both an administrator and a teacher has 20 teacher
  invitations and 100 student invitations per hour, counted separately.
- **Invitation email fails to send**: as in milestone 8, the form shows an error with the entered
  values, nothing is stored and the attempt counts toward the limits.
- **Page reload after a successful action** (create, edit, deactivate, activate or delete a class;
  invite, edit or remove a student; accept): does not repeat the action.

## Requirements *(mandatory)*

### Functional Requirements

#### Classes

- **FR-001**: A **class** MUST belong to exactly one educational institution and MUST have a name
  and a year of study. The year of study MUST be a whole number from 1 to 12. Several classes of one
  institution MAY share a year. Every institution MUST start with no classes.
- **FR-002**: Class names MUST follow the subject-name rules (milestone 6): trimmed, 1–200
  characters, no control characters. They MUST be unique within their institution ignoring case,
  including deactivated classes ("already exists in this institution"). The same name MAY exist in
  different institutions. A change of case alone MUST be a valid rename.
- **FR-003**: A class MUST be created only in an available institution and MUST never move to
  another institution. A class is not personal data and MUST be stored as soon as it is created.
- **FR-004**: A teacher with Write access MUST be able to create, edit (name and year of study),
  deactivate, activate and delete the classes of that institution. An invalid form MUST show again
  with the errors and the entered values, and nothing changes.
- **FR-005**: A deactivated class MUST accept no new students: no invitation into it, no student
  moved into it, and no acceptance into it.
- **FR-006**: Deleting a class MUST be refused while it holds any student, blocked or not.
- **FR-007**: Deleting an educational institution (milestone 7) MUST be refused while any teacher is
  linked to it or any student is enrolled in it. Classes without students MUST NOT prevent the
  deletion and MUST be deleted together with the institution. When the institution has classes, the
  confirmation MUST say that they will be deleted too.

#### Enrolment

- **FR-008**: A student MUST belong to exactly one educational institution and exactly one of its
  classes: the student's **enrolment**.
- **FR-009**: The enrolment MUST be treated as personal data (it reveals the institution, the class
  and the year of study). It MUST be stored only when the student accepts an invitation and MUST be
  deleted on removal, withdrawal and data deletion.
- **FR-010**: Moving a student to another class of the same institution MUST NOT require new
  consent.

#### Deactivation chain

- **FR-011**: Regions, educational institutions, classes and students MUST form a chain: a region
  holds institutions, an institution holds classes, a class holds students. An object MUST be
  **available** only when it and every object above it in the chain are active.
- **FR-012**: Deactivating an object MUST make everything below it unavailable without changing
  their own statuses. Activating it again MUST make available again everything below it whose own
  status is active.
- **FR-013**: An unavailable object, and everything below it, MUST NOT be shown, selected, opened or
  used anywhere: lists, drop-down lists, page addresses, submitted forms, invitations and, in later
  milestones, competitions.
- **FR-014**: The only exception MUST be the place where the deactivated object itself is managed,
  where it stays visible and marked as deactivated so it can be activated again: regions and
  institutions in the administrator area (milestone 7), teacher links on the administrator's teacher
  page (milestone 8), and classes on the **Students** tab. The objects below it MUST stay hidden even
  there. This hiding applies to classes and students only: the administrator area keeps
  milestones 7 and 8 unchanged, so the institutions of a deactivated region stay listed and
  manageable there, and a teacher link to such an institution stays shown as deactivated.
- **FR-015**: A student whose class is unavailable MUST be **blocked**. A blocked student MUST keep
  all their data, and:
  - MUST be signed out everywhere at the moment of the deactivation that blocks them, as when a role
    is removed (milestone 5);
  - with no other role, MUST be treated at sign-in as a removed person: sign-in behaves as for an
    unknown address;
  - with other roles, MUST NOT be offered the student role;
  - MUST still be able to delete their data through **Delete my data** (milestone 8);
  - MUST NOT be able to take part in competitions (enforced from milestone 11 on);
  - MUST NOT be shown to teachers, who cannot open, edit or remove them.
- **FR-016**: Once the class is available again, the student MUST be able to sign in with the student
  role again and teachers MUST see them again. Nothing else changes.
- **FR-017**: Deactivating a class, an institution or a region MUST NOT change any enrolment.
  Deactivating a region or an institution in the administrator area MUST ask for confirmation,
  saying that its students will be signed out and hidden until it is activated again, as the class
  confirmation does. Activating needs no confirmation.

#### Access

- **FR-018**: The teacher area and all its pages and actions MUST be open only to a person using the
  teacher role (milestone 5 rules).
- **FR-019**: A teacher MUST be able to see the classes and students of the available institutions
  they are linked to, with Read or Write access: all classes of these institutions (deactivated ones
  included), and the names, email and class of the students of their available classes.
- **FR-020**: Managing classes and adding, editing and removing students MUST require Write access to
  the institution. Administrators MUST NOT manage classes or students.
- **FR-021**: A teacher MUST be able to reach only the available institutions they are linked to,
  all classes of these institutions, and the students of their available classes, also through the
  page address. Anything else in the page address or in a submitted form, including an unknown
  object, MUST show "access denied". A management action on an institution with Read access MUST
  show "access denied".
- **FR-022**: Access MUST be checked on every request against the current links and access levels,
  so a change made by an administrator takes effect on the teacher's next request.
- **FR-023**: Every new page and action MUST declare which roles may open it, so the existing
  automated check of all routes covers them.

#### Inviting students

- **FR-024**: The student role MUST join the milestone 8 flow as one more invitable role. The flow
  MUST change only where this specification says so.
- **FR-025**: A teacher with Write access MUST be able to invite students one by one into the
  selected active class, entering email, first name and last name, validated as in milestone 8.
- **FR-026**: On submission, the email MUST NOT belong to anyone who holds the student role, in any
  institution, blocked students included. Otherwise the form MUST show again with "This email already
  belongs to a student" and the entered values, and no invitation is sent. The message MUST NOT name
  the institution or the class. This is an intended exception to the milestone 8 rule that the
  invitation form does not check existing roles.
- **FR-027**: Student invitations MUST be limited to 100 per inviter per hour. Teacher invitations
  MUST stay at 20 per inviter per hour. The limit per invited address MUST stay at 5 per hour.
- **FR-028**: The student invitation link MUST carry the role, the email, the names, the invited
  institution and class, the inviter and the issue time, and MUST be encrypted, tamper-proof and
  valid for 7 days, as in milestone 8. Nothing from the form MUST be stored.
- **FR-029**: The student invitation email MUST be plain text and MUST state: who invites, the
  student role, the institution with its region, the class with its year of study, that nothing is
  stored unless the person accepts, the link and its expiry.

#### Accepting a student invitation

- **FR-030**: The milestone 8 checks MUST apply unchanged: a tampered link is refused, an expired one
  has its own message, an invitation issued at or before the moment the person lost the student role
  or withdrew consent is refused, and a changed consent text shows the page again.
- **FR-031**: The acceptance page MUST show the inviter, the role, the email, the names, the
  institution with its region, the class and its year of study by their current values, the current
  student consent text and **I agree**, as data to be stored. Nothing on it MUST be editable.
- **FR-032**: For a student invitation, the milestone 8 inviter and institution checks MUST be
  replaced. **I agree** MUST be refused with the neutral message from milestone 8 when:
  - the inviter is no longer an active user holding the teacher role with Write access to the invited
    institution;
  - the invited class is no longer available: it was deleted, or it, its institution or its region
    was deactivated.
- **FR-033**: Otherwise, acceptance MUST create the enrolment and a consent record (as in milestone
  8) and grant the student role, creating, extending or reactivating the person as in milestone 8.
  Other roles MUST be kept.
- **FR-034**: If the person already holds the student role, accepting MUST change nothing, store no
  consent record, and say on the page that they are already a student.
- **FR-035**: Acceptance MUST be safe against double submission and against a concurrent class
  deletion: at most one enrolment, one role grant and one consent record, and never a student without
  a class.

#### Names on acceptance (both invitable roles)

- **FR-036**: When the accepting person already holds the teacher or the student role, their current
  names MUST be kept and the names from the invitation MUST NOT be used. This MUST apply to teacher
  and student invitations alike, changing milestone 8 for teacher invitations.
- **FR-037**: In every other case (a new person, an inactive person, or an administrator without
  these roles) the names from the invitation MUST be stored.
- **FR-038**: The acceptance page of both roles MUST say "If you are already a teacher or a student,
  your current names are kept."

#### Consent text

- **FR-039**: The student role MUST have its own consent text, versioned like the teacher one. It
  MUST be a fixed text that never names a particular institution or class. It MUST say that the
  class, and with it the year of study, is stored along with the email and names, and who can see
  them. Placeholder wording is acceptable, as in milestone 8.
- **FR-040**: The consent record MUST NOT store the invited institution or class.

#### Editing and removing students

- **FR-041**: **Edit** MUST change the student's first name, last name and class. The new class MUST
  be an active class of the same institution. The email, the institution and the year of study (on
  its own) MUST NOT be editable. Names MUST be validated as in milestone 8. An invalid edit MUST show
  the form again with the errors and the entered values, and nothing changes.
- **FR-042**: Editing a student MUST NOT sign them out.
- **FR-043**: **Remove** MUST ask for confirmation, naming the student, the class and the
  institution. Removing MUST delete the enrolment, keep the consent records, and then work as in
  milestone 8: the student role is removed, the invitation cut-off is updated, the person is signed
  out everywhere and deactivated if no role is left. Email and names MUST stay until the person
  deletes their data.

#### Withdrawing consent and profile

- **FR-044**: Withdrawing consent and deleting data without signing in MUST work as in milestone 8,
  with the student role and its enrolment among the roles and details removed.
- **FR-045**: The profile of a student MUST also show the enrolment: the institution with its
  region, the class and the year of study, next to the student role and the student consent records.
  While the student is blocked, the enrolment MUST still be shown, marked as deactivated.
- **FR-046**: For a student, the profile MUST say that corrections to student data go through a
  teacher of their institution. For teacher data it MUST still say an administrator.

#### Teacher area

- **FR-047**: The teacher page MUST become a teacher area that looks like the administrator area
  (milestone 6), with two tabs: **Students** (`/teacher/students`, opened by `/teacher`) and
  **Competitions** (`/teacher/competitions`). Each tab MUST be an ordinary link that can be
  bookmarked and reloaded, and the current tab MUST be highlighted. **Competitions** MUST be a
  placeholder.

#### Students tab: choosing a class

- **FR-048**: The **Students** tab MUST show three drop-down lists in a row: **Region**,
  **Educational institution** and **Class**, stacked in that order on narrow screens. Each MUST be
  disabled until the previous one is selected. All MUST be sorted by name ignoring case. Choosing an
  entry MUST open it at once, with no **Show** button.
  - **Region**: active regions that hold at least one active institution the teacher is linked to.
  - **Educational institution**: the teacher's active institutions of the selected region, each
    marked "Read" or "Write".
  - **Class**: all classes of the selected institution, each with its year of study, deactivated
    ones marked. With Write access, the last entry MUST be **+ Add class**, which opens a form with
    the name and the year of study; the new class is then selected.
- **FR-049**: Until the chain is complete, the middle of the page MUST show one message instead of the
  student list: "Select a region to continue", "Select an educational institution to continue" or
  "Select a class to see its students". A teacher linked to no available institution MUST see "You
  are not linked to any educational institution" and disabled lists.
- **FR-050**: The selected region, institution and class MUST be kept in the page address, so they
  survive reloads and bookmarks. After an action, the affected class MUST stay selected.

#### Students tab: the selected class

- **FR-051**: A bar MUST show the class name and year of study, marked if deactivated. With Write
  access it MUST offer **Edit** (the same form as creating), **Deactivate** / **Activate**,
  **Delete** and, while the class is active, **Add student**.
- **FR-052**: **Deactivate** MUST ask for confirmation, saying that the class's students will be
  signed out and hidden until the class is activated again.
- **FR-053**: **Delete** MUST ask for confirmation, naming the class and its institution. A refusal
  MUST suggest deactivation instead, but only if the class is not deactivated already.
- **FR-054**: Below the bar, the students of an active class MUST be listed by last name ignoring
  case, then first name, each with name and email. An empty class MUST show "No students in this class
  yet". A deactivated class MUST show "This class is deactivated; its students are hidden until it is
  activated again". With Write access, each student MUST have **Edit** and **Remove**; with Read
  access, the bar and the list MUST have no actions.

#### Shared page and action behaviour

- **FR-055**: Every action that changes data (class create, edit, deactivate, activate, delete;
  student invite, edit, remove) MUST be a form submission that passes the existing cross-site request
  check. Opening a page or following a link MUST never change anything.
- **FR-056**: After a successful action, the person MUST be sent to a result page, so reloading does
  not repeat the action.
- **FR-057**: The milestone 8 logging rule MUST hold: no log line contains an email address, a first
  or last name, or an invitation or deletion link.

#### Verification and scope

- **FR-058**: Automated tests MUST cover the acceptance scenarios of this specification, including
  the end-to-end student invitation through the in-memory outbox, the absence of personal data and
  enrolment before acceptance, every refusal at acceptance, the names rule for both roles, the
  existing-student check, the separate rate limits, the deactivation chain at every level, blocked
  students at sign-in, and Read versus Write access through page addresses and submitted forms.
- **FR-059**: This milestone MUST NOT add the content of the **Competitions** tab (milestones 11 and
  14), bulk upload of students, a list of pending invitations, cancelling an invitation, changing a
  person's email, moving a student to another institution in one step, or any way for administrators
  to manage students.

### Key Entities *(include if feature involves data)*

- **Class** (new): an educational institution, a name, a year of study (1–12) and an active or
  deactivated status. Not personal data. Never moves to another institution. Cannot be deleted while
  it holds a student; deleted together with its institution when it holds none.
- **Enrolment** (new): a student, their educational institution and their class. At most one per
  person. Personal data: stored only on acceptance, deleted on removal, withdrawal and data deletion.
- **Role assignment** (existing): the student role now comes only from an accepted invitation.
- **Invitation** (not stored, existing): for a student, carries the role, email, names, the invited
  institution and class, the inviter and the issue time.
- **Consent text version** (existing): gains the student role's texts.
- **Consent record** (existing): unchanged; for a student it does not store the institution or class.
- **Invitation cut-off** (existing): now also kept for the student role.
- **Educational institution** (existing): now also holds classes. The in-use check counts enrolled
  students.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A teacher can create a class and send a student invitation in under 2 minutes, and the
  invited student can accept it in under 1 minute.
- **SC-002**: Before acceptance, 0 stored records contain the invited student's email, names,
  institution or class.
- **SC-003**: 100% of student invitations whose inviter lost Write access, whose class became
  unavailable, or that were issued before a removal or withdrawal are refused and store nothing.
- **SC-004**: In the automated access check, 100% of teacher area pages and actions refuse every
  role except teacher, 100% of hand-made addresses and form values naming an unreachable object show
  "access denied", and 100% of management actions with Read access show "access denied".
- **SC-005**: After a class, institution or region is deactivated, 100% of the students below it are
  signed out, cannot sign in with the student role, and are not shown to any teacher; after it is
  activated again, 100% of them can sign in again.
- **SC-006**: 0 people hold more than one enrolment, and 0 classes are deleted while holding a
  student.
- **SC-007**: When a person who already holds the teacher or the student role accepts any invitation,
  their names are unchanged in 100% of cases.
- **SC-008**: 0 log lines captured during the test suite contain an email address, a name or an
  invitation or deletion link.
- **SC-009**: Reloading the page after any successful action never repeats it.
- **SC-010**: All tests from milestones 1–8 still pass, apart from tests of the old teacher area
  placeholder, which this milestone replaces.

## Assumptions

- **Delete refusal wording**: the milestone says the refusal suggests deactivation "only if the
  institution isn't deactivated already". A teacher can never reach a class of a deactivated
  institution, so this is read as the class: the suggestion is shown only while the class is active.
- **The per-address limit** of 5 invitations per hour is shared by teacher and student invitations,
  so an address is protected from flooding whatever the role. The per-inviter limits are counted
  separately for each role.
- **Invitation into or move to a deactivated class** (reachable but deactivated) is refused with an
  error saying the class is deactivated, not "access denied", because the class itself is reachable.
- **Students are sorted** by last name ignoring case, then first name, as teachers are in milestone
  8.
- **After deleting a class**, the institution stays selected and no class is selected.
- **Who invites is shown as** the inviter's name and email, as in milestone 8.
- **Who can see a student's data**, for the consent text: the teachers linked to the student's
  institution, with Read or Write access, and the student. No page of this milestone shows students
  to administrators.
- **Year of study is shown** next to the class name wherever a class is shown, for example "KN-21 ·
  year 2".
- **No real users exist** until all milestones are done, so no migration of existing students is
  needed: nobody holds the student role after milestone 8.
- **Placeholder consent text** is used until the product owner supplies the final wording.

## Dependencies

- **Milestone 8**: the invitation, acceptance, consent record, invitation cut-off, profile,
  withdrawal and data deletion flow; teacher institution links with Read and Write access; the
  in-memory outbox; rate limits.
- **Milestone 7**: regions, educational institutions, their statuses and the institution in-use
  check.
- **Milestone 6**: the look of the administrator area, reused by the teacher area; the subject-name
  rules reused for class names.
- **Milestone 5**: roles, the current role, role switching, "access denied", ending sessions on role
  removal and the automated route check.
- **Milestone 4**: sign-in, email validation, sessions and the cross-site request check.
- **Later milestones that depend on this one**: milestone 11 assigns students and classes to
  competitions and must exclude blocked students; milestones 11 and 14 fill the **Competitions**
  tab; milestone 14 shows results to teachers by institution access.

## Out of Scope

- The content of the **Competitions** tab: milestones 11 and 14.
- Bulk upload of students; students are invited one by one.
- Moving a student to another institution in one step; this is a removal and a new invitation.
- Administrators managing or seeing classes and students.
- A list of pending invitations, cancelling an invitation, changing a person's email, self sign-up
  (unchanged from milestone 8).
- Final consent wording.
