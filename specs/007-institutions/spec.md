# Feature Specification: Administrator Area — Educational Institutions (Milestone 7)

**Feature Branch**: `007-institutions`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Create a 007-institutions using product-requirements and technical-requirements"

## Overview

Milestone 7 of the walking skeleton for the Student Competitions application. Milestone 6 turned
the administrator page into an administrator area with three tabs: **Teachers**, **Educational
institutions** and **Subjects**. Only the Subjects tab has real features. The Educational
institutions tab is a placeholder page with one sentence.

This milestone turns the **Educational institutions** tab into the list of educational institutions
(for example universities, colleges and schools). Teachers and students are linked to these
institutions in later milestones. The tab works the same way as the **Subjects** tab. Three things
become true when this milestone is done:

1. **Administrators keep the list of educational institutions.** Administrators can see all
   institutions, and create, rename, deactivate, reactivate and delete them. Institution names are
   unique, ignoring case. Product rules make the administrator the only role that can edit this
   list.
2. **Institutions are ready for teachers and students.** Milestone 8 links each teacher to one or
   more institutions, and milestone 9 places each student in one. Those links refer to an
   institution by its identity, not its name, so renaming never breaks a link. An inactive
   institution is not offered or accepted for new links, but existing links stay.
3. **No link is ever left pointing at nothing.** An institution that anything refers to cannot be
   deleted. The administrator is told it is in use and can deactivate it instead.

The **Teachers** tab stays a placeholder page until milestone 8.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator builds the list of educational institutions (Priority: P1)

An administrator signs in, opens the administrator area and clicks the **Educational institutions**
tab. The first time, the list is empty and shows "No educational institutions yet", with a
**Create** button. The administrator clicks **Create**, types "Kyiv Polytechnic Institute" and
saves. They return to the Educational institutions tab, where the new institution is listed as
active. They add "Lviv Polytechnic" and "Kharkiv Lyceum No. 27" the same way. The list shows all
three, sorted by name.

The administrator then tries to add "lviv polytechnic" (lower case). The form shows again with the
entered value and an error saying an institution with that name already exists. They try to save
an empty name. The form shows again with an error saying the name is required.

**Why this priority**: The institution list is the only real data this milestone adds. Milestone 8
cannot link teachers to institutions until the list exists. This story alone delivers a usable
feature.

**Independent Test**: Sign in as an administrator (or create a session directly with the test
support), open the Educational institutions tab, create institutions and check the list. Submit
invalid and duplicate names and check that each one is refused with the right error and the
entered value kept.

**Acceptance Scenarios**:

1. **Given** no institutions exist, **When** an administrator opens the Educational institutions
   tab, **Then** the page shows "No educational institutions yet" and a **Create** button.
2. **Given** the Educational institutions tab is open, **When** the administrator clicks
   **Create**, enters "Kyiv Polytechnic Institute" and saves, **Then** they return to the
   Educational institutions tab and "Kyiv Polytechnic Institute" is listed as active.
3. **Given** institutions "Lviv Polytechnic", "alpha College" and "Kyiv Polytechnic Institute"
   exist, **When** the tab is opened, **Then** they are listed in alphabetical order ignoring case:
   alpha College, Kyiv Polytechnic Institute, Lviv Polytechnic.
4. **Given** "Lviv Polytechnic" exists, **When** the administrator creates "  LVIV POLYTECHNIC  ",
   **Then** the form shows again with a "name already exists" error and the entered value, and no
   institution is added.
5. **Given** the create form is open, **When** the administrator saves a name that is empty or only
   spaces, longer than 200 characters after trimming, or contains a control character, **Then** the
   form shows again with an error that explains the rule, the entered value is kept, and no
   institution is added.
6. **Given** the create form is open, **When** the administrator saves "  Odesa College  ",
   **Then** the institution is stored and shown as "Odesa College", with the outer spaces removed.

---

### User Story 2 - An administrator renames, deactivates, reactivates and deletes institutions (Priority: P2)

Each institution in the list has **Rename**, **Deactivate** and **Delete** buttons. The
administrator notices "Lviv Politechnic" is misspelled, clicks **Rename**, corrects it to "Lviv
Polytechnic" and saves. The list shows the new name.

A partner college stops taking part in competitions. The administrator clicks **Deactivate** on
it. It stays in the list, marked as inactive. From now on it will not be offered when inviting a
teacher or a student, or when adding an institution to an existing teacher or student
(milestones 8 and 9). Teachers and students already linked to it keep their links. Its
**Deactivate** button is replaced by **Activate**, which reverses the change.

The administrator created "Test School" by mistake. They click **Delete**, confirm, and the
institution is gone. If any teacher or student were already linked to an institution, its deletion
would be refused with a message saying the institution is in use and can be deactivated instead,
and the institution would stay unchanged.

**Why this priority**: Mistakes in a list happen, and the list changes over time. Without these
actions the only fix is a database edit. They come after creation because they need institutions
to exist.

**Independent Test**: With a few institutions in place, rename one (including to a duplicate name,
which must be refused), deactivate and reactivate one, and delete an unused one after confirming.
Check that an institution in use cannot be deleted.

**Acceptance Scenarios**:

1. **Given** "Lviv Politechnic" exists, **When** the administrator clicks **Rename**, **Then** a
   form opens with the current name filled in.
2. **Given** the rename form for "Lviv Politechnic" is open, **When** the administrator saves
   "Lviv Polytechnic", **Then** they return to the Educational institutions tab and the
   institution is listed as "Lviv Polytechnic".
3. **Given** "Lviv Polytechnic" and "Odesa College" exist, **When** the administrator renames
   "Odesa College" to "lviv polytechnic", **Then** the form shows again with a "name already
   exists" error and the entered value, and "Odesa College" is unchanged.
4. **Given** "odesa college" exists, **When** the administrator renames it to "Odesa College"
   (only the case changes), **Then** the rename succeeds.
5. **Given** an inactive institution, **When** the administrator renames it, **Then** the rename
   succeeds and the institution stays inactive.
6. **Given** an active institution, **When** the administrator clicks **Deactivate**, **Then** the
   institution stays in the list, marked as inactive, with an **Activate** button.
7. **Given** an inactive institution, **When** the administrator clicks **Activate**, **Then** the
   institution is marked as active again, with a **Deactivate** button.
8. **Given** an unused institution, **When** the administrator clicks **Delete**, **Then** a
   confirmation step names the institution and says the deletion cannot be undone. Nothing is
   deleted until the administrator confirms.
9. **Given** the confirmation step for an unused institution, **When** the administrator confirms,
   **Then** the institution is removed and no longer appears in the list. **When** the
   administrator cancels instead, **Then** they return to the list and the institution is
   unchanged.
10. **Given** an institution that is in use, **When** the administrator confirms its deletion,
    **Then** the deletion is refused with a message saying the institution is in use and can be
    deactivated instead, and the institution is unchanged.

---

### User Story 3 - Only administrators reach the Educational institutions tab (Priority: P3)

A teacher, a student, and a person who is both an administrator and a teacher but is using the
teacher role each try to open the Educational institutions tab and its forms by typing their
addresses. Each one sees the "access denied" page from milestone 5. An anonymous visitor is sent to
the sign-in page. None of them can create, rename, deactivate, reactivate or delete an institution
by sending a form directly.

**Why this priority**: Milestone 5 already makes access deny-by-default, and milestone 6 already
limits the administrator area to administrators. This story confirms that the new pages and actions
follow the same rules. It is essential but low-risk.

**Independent Test**: For each role and for an anonymous visitor, request every new page and send
every new form. Check that only an administrator using the administrator role succeeds and that
the institution list is unchanged after every refused request.

**Acceptance Scenarios**:

1. **Given** a person using the teacher or student role, **When** they open the Educational
   institutions tab or any institution form, **Then** they see "access denied".
2. **Given** a person using the teacher or student role, **When** they submit any institution
   action directly, **Then** they see "access denied" and no institution changes.
3. **Given** a person who holds the administrator and teacher roles but is using the teacher role,
   **When** they open `/admin/institutions`, **Then** they see "access denied". **When** they
   switch to the administrator role, **Then** the page opens.
4. **Given** an anonymous visitor, **When** they open any institution page, **Then** they are
   redirected to the sign-in page, and after signing in as an administrator they return to that
   page.

---

### Edge Cases

- **Name with letters outside English**: uniqueness ignores case for all letters, not only Latin
  ones. "Київський університет" and "КИЇВСЬКИЙ УНІВЕРСИТЕТ" are the same name.
- **Name only differs in inner spaces**: "Lviv Polytechnic" and "Lviv  Polytechnic" (two spaces)
  are different names. Only spaces at the start and end are removed.
- **Name exactly 200 characters after trimming**: accepted. 201 characters: refused.
- **Control characters**: a name containing a tab, a line break or any other control character is
  refused, even if it would otherwise be valid.
- **Duplicate of an inactive institution**: creating or renaming to a name already used by an
  inactive institution is refused. Uniqueness covers every institution, active or not.
- **Same name as a subject**: an institution may have the same name as a subject. The two lists are
  independent.
- **Rename to the same name**: saving the rename form without changes succeeds and changes nothing.
- **Repeated status change**: deactivating an already inactive institution, or activating an active
  one (for example from a stale page or a double click), changes nothing and is not an error.
- **Institution removed meanwhile**: if another administrator deletes an institution while it is
  being renamed, deactivated, activated or deleted, the action shows a friendly "institution not
  found" page with a link back to the Educational institutions tab. No error details are shown.
- **Two administrators create the same name at the same moment**: only one institution is stored.
  The other administrator sees the "name already exists" error.
- **Delete when nothing yet refers to institutions**: no teacher or student is linked to an
  institution in this milestone, so every institution can be deleted for now. The in-use check
  still runs, and milestones 8 and 9 extend it to cover their links.
- **Page reload after a form is saved**: reloading the list after creating, renaming, deactivating,
  activating or deleting does not repeat the action.

## Requirements *(mandatory)*

### Functional Requirements

#### Educational institutions tab

- **FR-001**: The **Educational institutions** tab at `/admin/institutions` MUST stop being a
  placeholder page and MUST list all educational institutions, active and inactive, sorted
  alphabetically by name ignoring case.
- **FR-002**: Each listed institution MUST show its name and whether it is active or inactive.
- **FR-003**: When no institutions exist, the tab MUST show "No educational institutions yet".
- **FR-004**: The tab MUST show a **Create** button. Each listed institution MUST offer **Rename**,
  **Delete**, and either **Deactivate** (when active) or **Activate** (when inactive).
- **FR-005**: The institution forms and the delete confirmation MUST show the administrator area
  tabs with **Educational institutions** highlighted, as milestone 6 requires for pages that belong
  to a tab.
- **FR-006**: The rest of the administrator area MUST stay as it is: the tabs, their order and
  addresses, the `/admin` redirect to the Teachers tab, the Teachers placeholder page and the
  Subjects tab.

#### Institution names

- **FR-007**: An institution's name MUST be trimmed of spaces at the start and end before it is
  checked and stored. Spaces inside the name MUST be kept as entered.
- **FR-008**: After trimming, a name MUST be 1 to 200 characters long and MUST NOT contain control
  characters (such as tab, line break or other non-printing characters).
- **FR-009**: Institution names MUST be unique across all institutions, active and inactive,
  ignoring case for all letters, including non-Latin ones.
- **FR-010**: Uniqueness MUST hold even when two administrators submit the same name at the same
  time. Only one institution is stored, and the other submission gets the "name already exists"
  error.

#### Creating an institution

- **FR-011**: **Create** MUST open a form with one field, the name.
- **FR-012**: Saving a valid, unique name MUST create an **active** institution and return the
  administrator to the Educational institutions tab, where the new institution is listed.
- **FR-013**: Saving an invalid or duplicate name MUST show the form again with an error message
  that explains the problem and the value the administrator entered. No institution is created.

#### Renaming an institution

- **FR-014**: **Rename** MUST open the same form as **Create**, filled in with the institution's
  current name.
- **FR-015**: A new name MUST follow the same rules as on creation (FR-007 to FR-010). The
  institution being renamed MUST NOT count as a duplicate of itself, so a change of case alone is
  allowed.
- **FR-016**: Saving a valid name MUST update the institution and return to the Educational
  institutions tab. Saving an invalid or duplicate name MUST show the form again with the error
  and the entered value, and the institution MUST stay unchanged.
- **FR-017**: Renaming MUST be allowed for active and inactive institutions and MUST NOT change the
  institution's status.
- **FR-018**: Everything that refers to an institution MUST refer to it by its identity, not by its
  name, so renaming an institution never breaks a link to it.

#### Deactivating and activating an institution

- **FR-019**: **Deactivate** MUST mark an active institution as inactive. The institution stays in
  the list, keeps its name and is marked as inactive.
- **FR-020**: **Activate** MUST mark an inactive institution as active again.
- **FR-021**: Deactivating an inactive institution or activating an active one MUST change nothing
  and MUST NOT show an error.
- **FR-022**: The status MUST be stored so later milestones can rely on it. From milestone 8 on, an
  inactive institution MUST NOT be offered or accepted for new links: inviting a teacher or a
  student, or adding an institution to a teacher or student when editing them. Existing links to an
  institution that was deactivated later MUST stay, and editing that teacher or student MUST keep
  them. This milestone stores and shows the status but has no links to restrict.

#### Deleting an institution

- **FR-023**: **Delete** MUST first show a confirmation step that names the institution and says
  that deletion cannot be undone. Only an explicit confirmation deletes the institution. Cancelling
  returns to the Educational institutions tab with nothing changed.
- **FR-024**: Before deleting, the system MUST check whether anything refers to the institution. If
  it is in use, the deletion MUST be refused with a message saying the institution is in use and
  can be deactivated instead. The institution MUST stay unchanged.
- **FR-025**: The in-use check MUST be the single place that decides whether an institution may be
  deleted, so later milestones extend it when they add records that refer to institutions (teacher
  links in milestone 8, student details in milestone 9). Whatever records exist, deleting an
  institution MUST NEVER leave a record pointing at an institution that no longer exists.
- **FR-026**: Deleting an unused institution MUST remove it permanently and return to the
  Educational institutions tab, where it no longer appears. Its name becomes free for a new
  institution.

#### Shared form and action behaviour

- **FR-027**: Every action that changes an institution (create, rename, deactivate, activate,
  delete) MUST be a form submission that changes data. Opening a page or following a link MUST
  NEVER change an institution.
- **FR-028**: After a successful action, the administrator MUST be sent back to the Educational
  institutions tab, so reloading the page does not repeat the action.
- **FR-029**: Every action that changes an institution MUST pass the existing cross-site request
  check. A cross-site submission MUST be refused and change nothing.
- **FR-030**: An action or page for an institution that does not exist MUST show a friendly "not
  found" page with a link back to the Educational institutions tab, without internal error details.

#### Access

- **FR-031**: The Educational institutions tab, its forms, the delete confirmation and every
  institution action MUST be open only to a person currently using the administrator role. Every
  other role MUST get the "access denied" page from milestone 5, and an anonymous visitor MUST be
  sent to sign in, as for every protected page.
- **FR-032**: Every new page and action MUST state which roles can open it, and MUST be covered by
  the existing automated check that every route declares its roles.

### Key Entities *(include if feature involves data)*

- **Educational institution**: a university, college, school or similar body that teachers and
  students belong to. Attributes: a name (1–200 characters, unique ignoring case across active and
  inactive institutions) and a status (active or inactive). A new institution is active. Other
  records refer to it by its identity, never by its name. From milestone 8 on, teachers are linked
  to one or more institutions, and from milestone 9 on, each student belongs to one. An institution
  that any record refers to cannot be deleted. Only administrators create or change institutions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can create a new institution, starting from the Educational
  institutions tab, in under 30 seconds and with no more than 2 clicks plus typing the name.
- **SC-002**: 100% of invalid or duplicate names are refused with a message, and the entered value
  is still in the form.
- **SC-003**: In the automated access check, 100% of institution pages and actions refuse every
  role except administrator, and refuse an administrator who is currently using another role.
- **SC-004**: No institution that is in use can be deleted, as shown by a test with a stand-in
  record that refers to an institution.
- **SC-005**: No two institutions can ever exist with names that differ only in case, including
  when two administrators submit at the same moment.
- **SC-006**: Reloading the page after any successful institution action never repeats the action.
- **SC-007**: Renaming an institution leaves every record that refers to it pointing at the same
  institution.
- **SC-008**: All tests from milestones 1–6 still pass unchanged, apart from tests of the old
  Educational institutions placeholder page, which this milestone replaces.

## Assumptions

- **The Subjects tab is the model.** The technical requirements say the tab "works the same way as
  the Subjects tab". Name rules, ordering, uniqueness, the confirmation step, the not-found page and
  the redirect after each action all match milestone 6.
- **Delete asks for confirmation**, as the requirements state, because deletion cannot be undone.
  Deactivate and activate are reversible and happen at once, with no confirmation.
- **Inactive institutions stay in the list**, marked as inactive and mixed in name order with active
  ones. There is no filter or separate section. The list is expected to stay short (tens of
  institutions).
- **Sorting** is alphabetical ignoring case. Language-specific ordering rules are not required.
- **No paging or search** on the tab, given the expected size of the list.
- **No starting institutions are created.** The list starts empty. Since no real users exist until
  all milestones are done (product requirements), no migration of existing data is needed.
- **Institution names are not personal data**, so the privacy rules on logging do not restrict
  them. No change history is kept for institutions.
- **The in-use check has nothing to find in this milestone.** No teacher or student refers to an
  institution yet. Milestones 8 and 9 add those references to the check, along with acceptance
  tests that an institution in use cannot be deleted. In this milestone, the refusal path is
  verified with a stand-in record that refers to an institution.
- **Institution and subject names are independent.** The same text may be both a subject name and
  an institution name.

## Dependencies

- **Milestone 6 (administrator area)**: the tab row, the `/admin/institutions` address, tab
  highlighting, and the Subjects tab whose behaviour this milestone mirrors.
- **Milestone 5 (roles and authorization)**: current role, the role-based access check, the
  "access denied" page, and the automated check that every route declares its roles.
- **Milestone 4 (authentication)**: sign-in, sessions, the redirect to sign in with a return
  address, and the cross-site request check for form submissions.
- **Milestone 3 (database and migrations)**: storing institutions with a schema change that runs on
  both the local and the production database.
- **Later milestones that depend on this one**:
  - Milestone 8 links teachers to institutions, offers only active institutions for new links, and
    extends the in-use check.
  - Milestone 9 places students in institutions, offers only active institutions for new
    placements, and extends the in-use check.

## Out of Scope

- Linking teachers or students to institutions: milestones 8 and 9.
- Any institution details besides the name and status (address, type, code, contact details).
- The **Teachers** tab, which stays a placeholder page until milestone 8.
- Changes to the **Subjects** tab.
- Bulk import or export of institutions.
- A change history for institutions.
