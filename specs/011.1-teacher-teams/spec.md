# Feature Specification: Teams (Teacher) (Milestone 11.1)

**Feature Branch**: `011.1-teacher-teams`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: milestone 11.1 of `docs/requirements/milestones.md` ("Teams
(teacher)"), with `product-requirements.md` (the new **Team** section and the team rules for teachers
and personal data), the milestone 7, 8, 9, 10, 10.1 and 11 specifications and
`docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 11.1 of the walking skeleton for the Student Competitions application. After milestone 11,
teachers manage classes and students of their institutions and read or change the question bank.
Students exist only as members of one class; there is no way to group students for a competition.

The product requirements now say that **teams, not single students or classes, are the participants
of competitions** (milestone 12). This milestone gives teachers those teams. Seven things become true
when this milestone is done:

1. **Teachers put students together into named teams.** A team belongs to one educational institution
   and holds students of that institution only, from any of its classes. Classes do not change. A
   student can be in several teams of their institution, but in each team only once.
2. **The teacher area gets a Teams tab.** It sits between **Students** and **Questions** and works
   like **Students**: three chained lists (**Region**, **Educational institution**, **Team**) choose a
   team, and its active members are listed below.
3. **Write access manages teams; Read access only sees them.** With Write access to the institution a
   teacher creates, renames and deletes teams and adds and removes members. With Read access they see
   the same teams and members with no actions. Administrators and students have no access.
4. **Team names are unique everywhere.** No two teams share a name, ignoring case, in any
   institution; the name of a deleted team is free again.
5. **Deleting a team only hides it.** A deleted team stays stored with all its memberships, so
   completed competitions can keep showing it (milestones 12–15), but it is never listed, changed or
   added to a new competition again. Its members are not affected.
6. **Team memberships are personal data.** The student's profile lists their teams; withdrawing
   consent, deleting the data or removing the student role erases them, in deleted teams too. The
   student consent text version 1 is rewritten in place to say so (a one-time exception, because no
   real users exist yet).
7. **An institution that has ever held a team cannot be deleted**, only deactivated.

The selected class on **Students** already has a section heading with actions, but it is hand-built
on that page. Following the project rules, it becomes a component in the library, the component
gallery (`/admin/components`) and the UI guidelines, and both **Students** and **Teams** use it;
**Students** looks and behaves exactly as before.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher creates a team and adds students to it (Priority: P1)

Olena is a teacher linked to "Kyiv Polytechnic Institute" (Kyiv) with **Write** access. She opens the
teacher area and chooses the **Teams** tab, then "Kyiv" in **Region** and "Kyiv Polytechnic Institute
(Write)" in **Educational institution**. The institution has no team yet, so the page shows "No teams
yet" with a hint to create the first team with **+ Add team**. She picks **+ Add team** in the
**Team** list, types "Rockets" and saves. She is back on the **Teams** tab with Kyiv and the
institution still selected and "Rockets" selected, which shows "No members in this team yet".

She presses **Add students** beside the team's name. A page for "Rockets" opens with a **Class** list.
She chooses "KN-21 (year 2)", sees its students by last name, and presses **Add** beside Taras
Shevchenko. She is back on the **Teams** tab with "Rockets" selected, a notice that Taras Shevchenko
was added, and Taras listed as a member with his class "KN-21 (year 2)". She opens **Add students**
again, chooses "KN-31 (year 3)" and adds Lesia Ukrainka. "Rockets" now lists both, by last name.

**Why this priority**: Teams are what milestone 12 assigns to competitions; without creating teams
and filling them there is nothing to assign.

**Independent Test**: Sign in as a teacher with Write access, create a team, add students from two
classes of the institution, and check the member list, the notice, the selection kept after every
step, and that the students' classes are unchanged.

**Acceptance Scenarios**:

1. **Given** a teacher opens the teacher area, **When** the tab row is shown, **Then** it holds four
   tabs in the order **Students**, **Teams**, **Questions**, **Competitions**, and **Teams** opens
   `/teacher/teams`.
2. **Given** the **Teams** tab is open, **When** the teacher looks at the lists, **Then** **Region**,
   **Educational institution** and **Team** stand in a row (stacked in that order on a narrow screen),
   each disabled until the one before it is selected, and **Region** and **Educational institution**
   offer exactly what they offer on **Students**, each institution marked "Read" or "Write".
3. **Given** Olena has Write access to the selected institution, **When** she opens the **Team** list,
   **Then** it offers the institution's teams that are not deleted, sorted by name ignoring case, and
   its last entry is **+ Add team**.
4. **Given** she picks **+ Add team**, **When** the form opens, **Then** it has one field, the name,
   and she can save or cancel, the way **+ Add class** works on **Students**.
5. **Given** she enters a valid, unused name, **When** she saves, **Then** the team is created in the
   selected institution and she returns to the **Teams** tab with the same region and institution and
   the new team selected.
6. **Given** a team with no members is selected, **When** the page is shown, **Then** it shows "No
   members in this team yet".
7. **Given** a team is selected, **When** Olena presses **Add students**, **Then** a page for that
   team opens with a back link to the team and a **Class** list of the institution's active classes,
   sorted by name ignoring case, each with its year of study, and the page shows "Select a class to
   see its students".
8. **Given** she chooses a class, **When** the page is shown, **Then** the class's students are listed
   by last name ignoring case, then first name, each with their name and **Add** beside it, and the
   chosen class is kept in the page address.
9. **Given** a student of the chosen class is already in the team, **When** the list is shown,
   **Then** that student shows "In this team" instead of **Add**.
10. **Given** she presses **Add** beside a student, **When** the student is added, **Then** she returns
    to the **Teams** tab with the same region, institution and team selected, a notice naming the
    added student, and the updated member list.
11. **Given** the team has members from two classes, **When** the member list is shown, **Then** it
    shows the active members by last name ignoring case, then first name, each with their name and
    their class with its year of study.
12. **Given** a student was added to a team, **When** anyone looks at the student's class on
    **Students**, **Then** the student is still in the same class, with the same role and enrolment.
13. **Given** the chosen class has no students, **When** the **Add students** page is shown, **Then**
    it shows "No students in this class yet".
14. **Given** a student is already in another team of the institution, **When** Olena adds them to
    "Rockets", **Then** they are added and stay in the other team too.

---

### User Story 2 - A teacher renames a team, removes a member and deletes a team (Priority: P1)

Olena renames "Rockets" to "Comets" with **Rename**, which opens the same form filled with the current
name. Later Taras moves to another school project, so she presses **Remove** beside him; a
confirmation names Taras and "Comets", and she confirms. Taras is no longer listed, but he keeps his
class, his student role and can still sign in. At the end of the year she presses **Delete** under the
team's name. The confirmation names "Comets", its institution and its 1 active member. After she
confirms, "Comets" is gone from the **Team** list, but the team and its memberships are still stored,
and Lesia is unchanged.

**Why this priority**: Teams change over a school year; renaming, removing and retiring them are part
of keeping them correct, and deletion must never lose what a past competition needs to show.

**Independent Test**: Rename a team, remove one member, delete the team, and check the selection
after every step, the confirmation texts, that the removed student is unaffected, and that the deleted
team stays stored with its memberships while no page lists it.

**Acceptance Scenarios**:

1. **Given** Olena has Write access and a team is selected, **When** the page is shown, **Then** the
   team's name is a section heading with **Add students** beside it and **Rename** and **Delete** as
   small buttons below it, and each member has **Remove**.
2. **Given** she presses **Rename**, **When** the form opens, **Then** it is the team form filled
   with the current name; **Given** she saves a valid, unused new name, **Then** she returns to the
   **Teams** tab with the same region, institution and team selected, showing the new name.
3. **Given** she presses **Remove** beside a member, **When** the confirmation opens, **Then** it names
   the student and the team; **When** she confirms, **Then** the student is taken out of the team
   only, and she returns to the **Teams** tab with the same team selected and the updated list.
4. **Given** a student was removed from a team, **When** anyone checks the student, **Then** they keep
   their student role, class and enrolment, their other teams, and are not signed out.
5. **Given** she presses **Delete**, **When** the confirmation opens, **Then** it names the team, its
   institution and the number of its active members, not counting blocked members.
6. **Given** she confirms the deletion, **When** it is done, **Then** she returns to the **Teams** tab
   with the same region and institution and no team selected, and the team is no longer in the
   **Team** list.
7. **Given** a team was deleted, **When** the stored data is checked, **Then** the team, its name, its
   institution and all its memberships are stored unchanged, and the team is marked as deleted.
8. **Given** a team was deleted, **When** anyone opens its address on the **Teams** tab, or any of its
   forms, confirmations or **Add students** page, or sends any action for it, **Then** they get
   "access denied" and nothing changes.
9. **Given** a team was deleted, **When** its former members are checked, **Then** each keeps their
   account, role, class, enrolment and other teams.
10. **Given** a deleted team was the institution's only team, **When** the **Teams** tab is shown for
    that institution, **Then** it shows "No teams yet" with its hint.
11. **Given** any form, confirmation or **Add students** page of the tab, **When** Olena presses
    **Cancel** or the back link, **Then** nothing changes and she returns to the **Teams** tab with the
    same region and institution, and the same team when the page belonged to one.

---

### User Story 3 - Team names are unique across all institutions (Priority: P1)

Olena tries to create a team "comets" while another teacher's institution in Lviv already has a team
"Comets". The form is shown again with her entry and the error "A team named “comets” already exists",
which does not say where. After the Lviv team is deleted, the name "Comets" can be used again.

**Why this priority**: Milestone 12 lets a teacher assign teams of several institutions to one
competition; names that repeat across institutions would make those lists and the results ambiguous.

**Independent Test**: Create teams with names that repeat an existing name in another institution and
in the same institution, in different case, before and after the existing team is deleted, and check
the errors and the entered values.

**Acceptance Scenarios**:

1. **Given** a team with the same name, ignoring case, exists in any institution and is not deleted,
   **When** a teacher creates or renames a team to that name, **Then** nothing is stored and the form
   is shown again with "A team named “…” already exists" (with the entered name) and the entered
   value; the message does not name any institution.
2. **Given** the only team with that name is deleted, **When** a teacher creates or renames a team to
   that name, **Then** it is accepted.
3. **Given** a name that is empty or only spaces, longer than 200 characters after trimming, or
   containing a control character, **When** the teacher saves, **Then** nothing is stored and the form
   is shown again with the error beside the field, in the error summary, and with the entered value.
4. **Given** the teacher typed spaces around the name, **When** they save, **Then** the stored name is
   trimmed.
5. **Given** the teacher renames a team to its own name in another case (for example "comets" to
   "Comets"), **When** they save, **Then** it is accepted.

---

### User Story 4 - Only the right people see and change teams (Priority: P1)

Mykola is linked to "Kyiv Polytechnic Institute" with **Read** access. On the **Teams** tab he sees
its teams and their members, with no **+ Add team**, **Add students**, **Rename**, **Delete** or
**Remove**. He types the address of the **Add students** page and sends a hand-made removal request:
both get "access denied". He changes the address to a team of an institution he is not linked to and
gets "access denied" again. An administrator and a student who type `/teacher/teams` get "access
denied".

**Why this priority**: Teams reveal which students belong together and will decide who takes part in
competitions; a missing check would leak personal data or let a teacher change another institution's
teams.

**Independent Test**: For every page and action of the tab, send requests as each role and as
teachers with Write, Read and no link to the team's institution, including typed-in addresses and
crafted form submissions for unknown, deleted and unreachable teams and students.

**Acceptance Scenarios**:

1. **Given** a person in the administrator or student role, **When** they open any page or send any
   action of the **Teams** tab, **Then** they get "access denied", naming their current role.
2. **Given** Mykola has Read access, **When** he selects a team, **Then** he sees its heading and its
   active members with no actions, and the **Team** list has no **+ Add team**; an institution with
   no team shows "No teams yet" with a hint that a teacher with Write access creates teams.
3. **Given** Mykola has Read access, **When** he opens through its address any form, confirmation or
   **Add students** page of the institution's teams, or submits any change, **Then** he gets "access
   denied" and nothing changes.
4. **Given** any teacher, **When** they name an unknown team, a deleted team or a team of an
   institution they are not linked to or that is not available, in an address or a submitted form,
   **Then** they get "access denied" and nothing changes.
5. **Given** a teacher with Write access, **When** a submitted form adds a student of another
   institution, a blocked student or an unknown student, or removes a blocked member, **Then** they
   get "access denied" and nothing changes.
6. **Given** a teacher opened a form, a confirmation or the **Add students** page, **When** their link
   is removed or lowered to Read, or the team is deleted, before they submit, **Then** submitting gets
   "access denied" and nothing changes.
7. **Given** the address names a region, institution and team that do not belong together, **When** it
   is opened, **Then** the teacher gets "access denied", as on **Students**.
8. **Given** a teacher with Write access, **When** they open **Add students** for a team of a Read
   institution through its address, **Then** they get "access denied".

---

### User Story 5 - Membership rules are enforced (Priority: P1)

A team never holds the same student twice, never holds more than 50 members, and holds only students
of its own institution. When a team already has 50 members, its **Add students** page says so and
offers no **Add**. A crafted request for a 51st member, a second membership of the same student or a
student of another institution is refused.

**Why this priority**: These rules keep competitions in milestones 12–15 well defined; the 50-member
limit protects validation, and the institution rule protects personal data.

**Independent Test**: Fill a team to 50 members, blocked ones included, and try to add one more
through the page and a crafted request; try adding an existing member twice and a student of another
institution.

**Acceptance Scenarios**:

1. **Given** a team has 50 members, blocked ones included, **When** the **Add students** page is
   shown, **Then** it says "This team already has 50 members" and shows no **Add** buttons.
2. **Given** a team has 50 members, **When** a submitted form adds another student, **Then** nothing
   changes and the teacher returns to the **Add students** page, which says "This team already has 50
   members".
3. **Given** a student is already in the team, **When** a submitted form adds them again (for example
   from two open tabs), **Then** no second membership is stored and the teacher returns to the
   **Teams** tab with the team selected and a notice that the student is already in this team.
4. **Given** a student moves to another class of the same institution, **When** their teams are
   checked, **Then** they keep every team.
5. **Given** two teams of the same institution, **When** the same student is added to both, **Then**
   both memberships are stored.

---

### User Story 6 - Deactivation hides and blocks members (Priority: P2)

The administrator deactivates class "KN-21", where Taras studies. Taras disappears from the member
list of "Comets" with no notice, the team's delete confirmation counts only its other active members,
and the **Add students** page no longer offers "KN-21". When the class is activated again, Taras shows
in "Comets" again.

**Why this priority**: It follows the milestone 9 deactivation chain, which already exists; the
milestone only extends it to team members.

**Independent Test**: Deactivate a member's class, institution and region in turn, check the member
list, the delete confirmation count and the **Add students** page, then activate again and check the
member is listed again and the membership never changed.

**Acceptance Scenarios**:

1. **Given** a member's class, institution or region is deactivated, **When** the team is shown,
   **Then** the member is not listed and no notice mentions them.
2. **Given** a team has blocked members, **When** the delete confirmation is shown, **Then** it counts
   only the active members.
3. **Given** a team has blocked members, **When** the 50-member limit is checked, **Then** the blocked
   members count.
4. **Given** everything above the member is active again, **When** the team is shown, **Then** the
   member is listed again, and the membership was never changed.
5. **Given** a class is deactivated, **When** the **Add students** page is shown, **Then** the class is
   not offered in the **Class** list.

---

### User Story 7 - Team memberships are personal data (Priority: P2)

Lesia opens her profile. It lists her teams, sorted by name, "Comets (deleted)" among them. She
withdraws consent. Her account data is erased as before, and so is every one of her team memberships,
including the one in the deleted "Comets". A new student who is invited reads a consent text that
names team memberships among the stored data, says the teachers of the institution see them, and says
withdrawal erases them too.

**Why this priority**: The product rules make team memberships personal data; storing them without
saying so in the consent text, or keeping them after withdrawal, would break the consent promise.

**Independent Test**: Add a student to several teams, delete one of them, check the profile, then
withdraw consent, delete the data without signing in and remove the student role in turn, and check
that no membership is left, in deleted teams too. Read the consent text shown on a student invitation.

**Acceptance Scenarios**:

1. **Given** a student belongs to teams, **When** they open their profile, **Then** it lists every
   team they belong to, sorted by name ignoring case, with deleted teams marked as deleted.
2. **Given** a student belongs to no team, **When** they open their profile, **Then** it says they
   belong to no team.
3. **Given** a student belongs to teams, deleted ones included, **When** they withdraw consent, delete
   their data without signing in, or a teacher removes their student role, **Then** every membership
   of theirs is erased, and the teams themselves are kept.
4. **Given** a student invitation is opened, **When** the consent text is shown, **Then** it is still
   version 1 and names team memberships among the stored data, says that the teachers linked to the
   student's institution see them, and says that withdrawal erases them too.
5. **Given** the upgrade runs on a database that holds the old version 1 text, **When** it is done,
   **Then** the stored version 1 text is the new wording, and the published-text check pins the new
   wording.
6. **Given** a student whose institution or class is blocked, **When** they open their profile,
   **Then** their teams are still listed.

---

### User Story 8 - An institution with teams can only be deactivated (Priority: P3)

The administrator tries to delete "Lviv Academy". It once had a team, which was deleted since. The
deletion is refused as "in use", with the usual suggestion to deactivate the institution instead.

**Why this priority**: It protects the record that milestones 12–15 will show, but no competition
exists yet, so the risk in this milestone is small.

**Independent Test**: Try to delete an institution with a team, an institution with only deleted
teams, and an institution that never had a team and has no other use.

**Acceptance Scenarios**:

1. **Given** an institution holds at least one team, deleted or not, **When** an administrator tries to
   delete it, **Then** the deletion is refused as "in use", suggesting deactivation, as for an
   institution with enrolled students.
2. **Given** an institution never held a team and has no other use, **When** an administrator deletes
   it, **Then** it is deleted as before.
3. **Given** a class of an institution that holds teams, **When** a teacher tries to delete it, **Then**
   the milestone 9 rule applies unchanged (a class with students cannot be deleted).

---

### User Story 9 - The teacher area shows its new work (Priority: P3)

A teacher opens the home page. The teacher area's card describes its work: students, teams, the
question bank and competitions. On a phone 360 px or 375 px wide, the four tabs wrap onto at most two
rows, and anything the page moves to (the skip link, the error summary, a focused field) still lands
below the pinned frame.

**Why this priority**: It keeps the entry points and the frame correct with the new tab, but carries
no new capability.

**Independent Test**: Inspect the home page as a teacher; measure the tab row at 360 px and 375 px
width and check the targets against the pinned-frame clearances.

**Acceptance Scenarios**:

1. **Given** a teacher opens the home page, **When** the teacher area's card is shown, **Then** it
   names students, teams, the question bank and competitions.
2. **Given** a screen 360 px or 375 px wide, **When** any teacher area page is shown, **Then** the tab
   row takes at most two rows and nothing scrolls sideways.
3. **Given** a screen 360 px or 375 px wide, **When** the page moves to the error summary, a skip-link
   target or a focused field, **Then** it lands below the pinned frame.

---

### Edge Cases

- **A teacher linked to no available institution**: the **Teams** tab shows "You are not linked to any
  educational institution" and disabled lists, as on **Students**.
- **An institution with only deleted teams**: shows "No teams yet" with the hint for the teacher's
  access level.
- **An institution switched from Write to Read while the teacher has the tab open**: the next page
  shows no actions, and any change sent from the old page gets "access denied".
- **A team renamed by another teacher meanwhile**: the page shows the current name after the next
  load; a rename to a name taken meanwhile gets the duplicate error.
- **Two teachers create teams with the same name at the same time**: only one is stored; the other
  gets the duplicate error.
- **Two teachers add the 50th and 51st member at the same time**: only one is stored; the other is
  refused as in User Story 5.
- **A student added while their class is being deactivated**: the check is made when the addition is
  submitted. If the class is already deactivated, the addition gets "access denied"; if it is
  deactivated just after, the membership is stored and hidden like any blocked member's.
- **The selected team is deleted by another teacher**: opening its address gets "access denied"; the
  teacher chooses another team.
- **A team whose only members are all blocked**: the member list shows "No members in this team yet";
  the delete confirmation names 0 active members; the 50-member limit still counts the blocked ones.
- **A student removed from their institution, with Remove on Students**: their student role is taken
  away (milestone 9) and their memberships are erased.
- **A student of the team's institution, in a class that is active, but whose institution or region is
  deactivated**: the **Teams** tab cannot reach that institution, so nothing about them is shown.
- **The class list on Add students without JavaScript**: shows the **Show** button, like every chained
  list (milestone 11).
- **An address naming a class of another institution on Add students**: "access denied".
- **Very long team names or student names**: wrap within the content width on every screen size, with
  no sideways page scroll.
- **Saving the same form twice (double press)**: the form cannot be sent again until the next page
  arrives (milestone 10.1); reloading the result page does not repeat the action.
- **A deleted team's name in the student's profile**: shown with its name at the time of deletion,
  marked as deleted.

## Requirements *(mandatory)*

### Functional Requirements

#### Teams and memberships

- **FR-001**: A **team** MUST belong to exactly one educational institution and MUST never move to
  another. It MUST have a name and nothing else that a teacher sets.
- **FR-002**: Team names MUST follow the subject-name rules (milestone 6): trimmed, 1–200 characters
  after trimming, no control characters. A name MUST be unique ignoring case among all teams that are
  not deleted, in every institution. A duplicate MUST be refused with "A team named “…” already
  exists", which MUST NOT name any institution. The name of a deleted team MUST be free to use again.
- **FR-003**: A **membership** links one student to one team. Only students enrolled in the team's
  institution MUST be able to become members. A student MAY belong to several teams of their
  institution, but MUST belong to each team at most once.
- **FR-004**: A team MUST hold at most 50 members, blocked members included. Adding a 51st member MUST
  be refused.
- **FR-005**: Adding a student to a team MUST NOT change their class, enrolment, role, other teams or
  sessions. Moving a student to another class of the same institution MUST keep their teams.
- **FR-006**: Removing a member MUST only take the student out of that team: the student MUST keep
  their role, class, enrolment and other teams and MUST NOT be signed out.

#### Deleting a team

- **FR-007**: Deleting a team MUST only mark it as deleted: the team and all its memberships MUST stay
  stored unchanged. There MUST be no way to restore it.
- **FR-008**: A deleted team MUST never be listed on the **Teams** tab, MUST NOT be renamed, changed,
  given or relieved of members, and MUST be marked so that milestone 12 can never add it to a new
  competition or list it when managing competitions.
- **FR-009**: Deleting a team MUST change nothing for its members: each MUST keep their account,
  role, class, enrolment and other teams.

#### Deactivation chain

- **FR-010**: A member whose class, institution or region is deactivated MUST be blocked, following the
  milestone 9 chain: they MUST be hidden from the team's member list with no notice, MUST NOT be
  counted in the delete confirmation, and MUST be listed again once everything above them is active.
  The membership MUST stay stored unchanged meanwhile.
- **FR-011**: A blocked student MUST NOT be added to a team or removed from it, including through a
  submitted form.

#### Personal data and consent

- **FR-012**: A student's team memberships MUST be treated as personal data, like their class.
- **FR-013**: The student's profile MUST list every team the student belongs to, sorted by name
  ignoring case, with deleted teams marked as deleted, including while the student is blocked. A
  student with no team MUST see that they belong to no team.
- **FR-014**: When the student role is removed, consent is withdrawn or the data is deleted
  (milestones 8 and 9), every membership of the student MUST be erased, in deleted teams too. The
  teams themselves MUST be kept.
- **FR-015**: The student consent text version 1 MUST be rewritten in place to also name team
  memberships among the stored data, say that the teachers linked to the student's institution see
  them, and say that withdrawal erases them too. It MUST stay version 1; no version 2 is published.
  A new upgrade step MUST update the stored text, and the pinned checksum of the published text MUST
  be updated with it. This is a one-time exception to the milestone 8 rule that a published consent
  text never changes, allowed only because no real users exist yet.
- **FR-016**: The milestone 8 logging rule MUST hold for every page and action of the tab: no log
  line contains an email address or a first or last name.

#### Institution in use

- **FR-017**: Every team, deleted ones included, MUST count as a use of its institution. An
  institution that holds any team MUST NOT be deletable (milestone 7); the refusal MUST say it is "in
  use" and suggest deactivation, as for an institution with enrolled students.
- **FR-018**: Deleting a class MUST be unaffected by teams (a class with students already cannot be
  deleted).

#### Access

- **FR-019**: The **Teams** tab and all its pages and actions MUST be open only to the teacher role.
  Administrators and students MUST get "access denied" on every page and action of it.
- **FR-020**: Every teacher MUST be able to see the teams and active members of the available
  institutions they are linked to, with Read or Write access.
- **FR-021**: Creating, renaming and deleting teams and adding and removing members MUST require Write
  access to the team's institution. A teacher with Read access MUST get "access denied" on every
  form, confirmation and **Add students** page opened through its address and on every change they
  submit.
- **FR-022**: An unknown team, a deleted team, a team of an institution the teacher is not linked to
  or that is not available, an unknown student, a student of another institution and a blocked
  student MUST all get "access denied", on every page and action, including typed-in addresses and
  submitted forms. A region, institution, team or class in an address that do not belong together
  MUST get "access denied".
- **FR-023**: Access MUST be checked on every request against the current links and access levels,
  before anything the request names, whatever the page showed.
- **FR-024**: Every page MUST show a teacher only the actions they may take: with Read access, no **+
  Add team**, **Add students**, **Rename**, **Delete** or **Remove**.

#### Teacher area: the Teams tab

- **FR-025**: The teacher area MUST gain a tab, **Teams**, at `/teacher/teams`. The tabs MUST be
  ordered **Students**, **Teams**, **Questions**, **Competitions**. `/teacher` MUST keep opening
  **Students**.
- **FR-026**: On small screens the tab row MAY wrap onto at most two rows. It MUST be measured again at
  360 px and 375 px width against the pinned-frame clearances of milestone 10.1; if it needs more
  room, the clearances MUST be raised. The UI guidelines MUST be updated to match, and the measurement
  MUST be recorded with the feature.
- **FR-027**: The teacher area's card on the home page MUST describe the teacher area with its work:
  students, teams, the question bank and competitions.

#### Choosing a team

- **FR-028**: The **Teams** tab MUST show three drop-down lists in a row: **Region**, **Educational
  institution** and **Team**, stacked in that order on narrow screens. Each MUST be disabled until the
  previous one is selected, and all MUST be sorted by name ignoring case. **Region** and **Educational
  institution** MUST offer exactly what they offer on **Students**, each institution marked "Read" or
  "Write". **Team** MUST list the selected institution's teams that are not deleted; with Write access
  its last entry MUST be **+ Add team**.
- **FR-029**: Until the chain is complete, the page MUST show "Select a region to continue", "Select an
  educational institution to continue" or "Select a team to see its members". An institution with no
  team that is not deleted MUST show "No teams yet" instead of the last message, with a hint: with
  Write access, to create the first team with **+ Add team**; with Read access, that a teacher with
  Write access creates teams. A teacher linked to no available institution MUST see "You are not
  linked to any educational institution" and disabled lists.
- **FR-030**: The selected region, institution and team MUST be kept in the page address, so they
  survive reloads and bookmarks.
- **FR-031**: The region and the institution MUST be sticky: every action of the tab (creating,
  renaming and deleting a team, adding and removing members), with its form, confirmation or **Add
  students** page, its **Cancel** and its back link, MUST return to the **Teams** tab with the same
  region and institution selected. After creating, the new team MUST be selected; after renaming,
  adding or removing a member, the same team; after deleting, no team. **Cancel** and the back link
  MUST return with the team selected when the page belonged to a team.

#### Creating and renaming a team

- **FR-032**: **+ Add team** MUST open a form page with one field, the name, the way **+ Add class**
  does on **Students**. **Rename** MUST open the same form filled with the current name.
- **FR-033**: An invalid or duplicate name MUST show the form again with the error beside the field
  and in the error summary, and with the entered value.

#### The selected team

- **FR-034**: The selected team MUST be shown under a section heading with its name. With Write
  access, **Add students** MUST stand beside the name, and **Rename** and **Delete** MUST be small
  buttons below it. With Read access, the heading MUST have no actions.
- **FR-035**: Below the heading, the team's active members MUST be listed by last name ignoring case,
  then first name, each with their name and their class with its year of study. An empty team (or one
  whose members are all blocked) MUST show "No members in this team yet". With Write access each
  member MUST have **Remove**; with Read access the list MUST have no actions.
- **FR-036**: **Remove** MUST ask for confirmation naming the student and the team.
- **FR-037**: **Delete** MUST ask for confirmation naming the team, its institution and the number of
  its active members (blocked members not counted), and saying that the team will be hidden and its
  members keep their accounts and classes.

#### Adding students

- **FR-038**: **Add students** MUST open its own page for the team, with a back link to the team. It
  MUST show one drop-down list, **Class**, with the active classes of the team's institution sorted by
  name ignoring case, each with its year of study. The chosen class MUST be kept in the page address.
  The list MUST work without JavaScript.
- **FR-039**: Until a class is chosen, the page MUST show "Select a class to see its students". Once
  chosen, the class's students MUST be listed by last name ignoring case, then first name, each with
  their name and an **Add** button beside it; a student already in the team MUST show "In this team"
  instead. An empty class MUST show "No students in this class yet".
- **FR-040**: **Add** MUST add that one student and return to the **Teams** tab with the same region,
  institution and team selected, showing the updated member list and a notice naming the added
  student.
- **FR-041**: When the team already has 50 members, the page MUST say "This team already has 50
  members" and show no **Add** buttons.
- **FR-042**: A submitted addition of a student who is already in the team MUST store nothing and
  return to the **Teams** tab with the team selected and a notice that the student is already in this
  team. A submitted addition beyond 50 members MUST store nothing and return to the **Add students**
  page with the same class, saying "This team already has 50 members".

#### Shared page and action behaviour

- **FR-043**: Every change MUST be a form submission that passes the existing cross-site request
  check. Opening a page or following a link MUST never change anything.
- **FR-044**: After a successful change, the teacher MUST be sent to a result page, so reloading does
  not repeat the change.
- **FR-045**: Every page of the tab MUST be built from the existing components (chained lists, data
  tables, status badges, notices, confirmations, empty states with a hint, back links) and follow the
  UI guidelines, including the loading feedback and busy button of milestone 10.1, and MUST work on a
  phone-width screen without sideways page scrolling.
- **FR-046**: The section heading with actions (a level-2 title, at most one primary button beside it,
  and a row of small secondary or destructive buttons below it) MUST become a component in the
  library, the component gallery (`/admin/components`) and the UI guidelines, first, and MUST then be
  used by **Teams** and **Students**. **Students** MUST look and behave exactly as before. Any other
  new pattern MUST be added to the library, the gallery and the guidelines first, and only then used.

#### Verification and scope

- **FR-047**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" line, including allowed and denied access per role and per access level,
  every "access denied" case through addresses and submitted forms, name validation and uniqueness
  across institutions and case, reuse of a deleted team's name, the membership rules (once per team,
  same institution only, 50-member limit with blocked members, blocked students), the sticky
  selection after every action and cancel, the soft deletion keeping the team and memberships,
  members unchanged by team deletion and member removal, the deactivation chain for members and the
  delete count, the profile list, the erasure of memberships on withdrawal, data deletion and role
  removal (deleted teams included), the rewritten consent text, the institution in-use rule, and
  **Students** unchanged with the new section heading component.
- **FR-048**: This milestone MUST NOT add competitions or the content of the **Competitions** tab
  (milestone 12 and later), using teams in competitions, moving a team to another institution,
  restoring a deleted team, adding several students in one action, bulk import or export of teams, a
  team description, captain or other attributes, a change history, or any access to teams for
  administrators or students beyond the student's own profile.

### Key Entities *(include if feature involves data)*

- **Team** (new): belongs to one educational institution, which never changes; has a name (1–200
  characters, unique ignoring case among teams that are not deleted, across all institutions) and a
  deleted mark. A deleted team stays stored with its name, institution and memberships. The team
  itself is not personal data; its memberships are.
- **Team membership** (new): links one student to one team, at most once per pair; at most 50 per
  team. Personal data of the student: erased with the student's role, consent or data, in deleted
  teams too. Kept unchanged when the team is deleted or the student is blocked.
- **Educational institution** (existing): its in-use check now counts every team, deleted ones
  included.
- **Student enrolment** (existing): unchanged; the team's institution must be the student's enrolled
  institution.
- **Student consent text** (existing, version 1): rewritten in place to cover team memberships; its
  pinned checksum is updated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A teacher with Write access can create a team and add five students from two classes in
  under 3 minutes.
- **SC-002**: In the automated access check, 100% of **Teams** pages and actions refuse the
  administrator and student roles, 100% of change pages and actions refuse teachers with Read access,
  and 100% of requests naming an unknown, deleted or unreachable team, or an unknown, blocked or
  other-institution student, get "access denied" with nothing changed.
- **SC-003**: After 100% of the actions, cancels and back links covered by the tests, the teacher lands
  on the **Teams** tab with the region, institution and team this specification names.
- **SC-004**: 0 teams ever hold the same student twice, more than 50 members, or a student of another
  institution, including through crafted requests and concurrent additions.
- **SC-005**: 0 pairs of teams that are not deleted share a name ignoring case, across all
  institutions.
- **SC-006**: 100% of deleted teams remain stored with all their memberships unchanged, 0 of them
  appear on the **Teams** tab, and 0 of their former members change in any way.
- **SC-007**: After a student's consent is withdrawn, their data deleted or their role removed, 0
  memberships of theirs remain, in deleted teams too.
- **SC-008**: 0 institutions that hold any team, deleted ones included, can be deleted.
- **SC-009**: The **Teams** tab and its pages are usable at 360 px width with no sideways page
  scrolling, and the four-tab row takes at most two rows and meets the pinned-frame clearances at
  360 px and 375 px.
- **SC-010**: Reloading the page after any successful change never repeats it.
- **SC-011**: All tests from milestones 1–11 still pass, apart from tests of the old student consent
  text checksum, the three-tab row and the old teacher card wording, which this milestone replaces.

## Assumptions

- **Removing a member erases the membership.** The milestone says removal "only takes them out of the
  team"; unlike team deletion, it does not need to keep a record, because which members took part in a
  competition is an open question for milestone 12. A removed student can be added again later.
- **Uniqueness is checked against teams that are not deleted.** Because the name of a deleted team is
  free again, a deleted team and a live team may share a name; the profile and later the competition
  record tell them apart by the deleted mark.
- **The member list shows only active members**, so a team whose members are all blocked shows "No
  members in this team yet"; the stored memberships are unaffected.
- **The Add students page lists only students who are not blocked**: it offers only active classes of
  an available institution, so every listed student is active.
- **"In this team"** is shown as plain text in the place of the **Add** button, not as a badge.
- **Notices** read "<First name> <Last name> was added to the team." after **Add** and "<First name>
  <Last name> is already in this team." after a repeated addition, in the notice component's success
  and information styles; the exact wording is fixed in the plan.
- **The delete confirmation** reads, for example, "Delete team “Comets” of Kyiv Polytechnic
  Institute? It has 3 members. The team will be hidden and can no longer join new competitions. Its
  members keep their accounts, classes and other teams." The exact wording is fixed in the plan.
- **The remove confirmation** reads, for example, "Remove Taras Shevchenko from team “Comets”? The
  student keeps their class and their account."
- **The "No teams yet" hints** read "Create the first team with + Add team." (Write) and "A teacher with
  Write access to this institution creates its teams." (Read).
- **The Add students page title** names the team, and its back link reads "Back to <team name>" and
  returns to the **Teams** tab with the team selected.
- **Who created a team** is not shown and, where it is not needed for anything else, not stored; teams
  belong to the institution.
- **The profile list** shows team names only, not their institution, since every team of a student
  belongs to the student's own institution.
- **The consent text rewrite** keeps version 1's publication date; it adds team memberships to the
  list of stored data, adds "the teachers linked to your institution see your teams" to who sees it,
  and adds team memberships to what withdrawal erases. Existing student consent records keep pointing
  at version 1.
- **The tab row**: if the current clearances (11 rem below 768 px) already cover two rows of tabs, they
  are kept; the measurement is recorded either way.
- **Concurrent changes** follow the milestone 9 pattern: the database keeps one membership per student
  and team and one live team per name, and the loser of a race gets the normal refusal.

## Dependencies

- **Milestone 5**: roles, the current role, "access denied" and the automated route check.
- **Milestone 6**: the subject-name rules reused for team names.
- **Milestone 7**: regions and educational institutions, and the institution in-use rule extended here.
- **Milestone 8**: the consent flow, the student consent text versioning and its pinned checksum, the
  profile, withdrawal, data deletion without signing in, and the logging rule.
- **Milestone 9**: the teacher area, the **Students** tab with its chained lists, Read and Write
  access, classes with their year of study, enrolments, role removal and the deactivation chain with
  blocked students.
- **Milestone 10**: the component library, the component gallery, the UI guidelines and the existing
  components; the section heading of the selected class, turned into a component here.
- **Milestone 10.1**: the loading bar, the busy button and the pinned frame with its clearances.
- **Milestone 11**: the **Questions** tab in the tab row and the **Show** button of chained lists
  without JavaScript.
- **Later milestones that depend on this one**: milestone 12 assigns teams to competitions and must
  refuse deleted teams and teams of institutions the teacher is not linked to; milestones 13–15 show
  competitions to the members of participating teams and keep showing deleted teams in completed
  competitions.

## Out of Scope

- Using teams in competitions, and the content of the **Competitions** tab: milestone 12 and later.
- Moving a team to another institution, restoring a deleted team, erasing a team for good.
- Adding or removing several students in one action, bulk import or export of teams.
- Team attributes beyond the name (description, captain, colour, size target).
- A change history, or showing who created or changed a team.
- Any access to teams for administrators, or for students beyond their own profile.
