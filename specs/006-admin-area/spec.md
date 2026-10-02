# Feature Specification: Administrator Area — Teachers, Educational Institutions, Subjects (Milestone 6)

**Feature Branch**: `006-admin-area`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "create specification for the milestone 6 from technical requirements. Use product-requirements.md for a context"

## Overview

Milestone 6 of the walking skeleton for the Student Competitions application. Milestone 5 added
the three roles (student, teacher, administrator) and gave each a placeholder page. The
administrator page is still a single sentence with nothing behind it.

This milestone turns the administrator page into a real **administrator area** with three tabs:
**Teachers**, **Educational institutions** and **Subjects**. Only the Subjects tab gets real
features now. Three things become true when this milestone is done:

1. **The administrator area has a stable shape.** A row of tabs sits at the top of every
   administrator page, below the header. Each tab is its own page with its own address, so it can
   be bookmarked, reloaded and opened directly. Milestones 7 and 8 fill the other two tabs without
   changing this structure.
2. **Administrators keep the list of subjects.** A subject is a knowledge area, such as mathematics
   or physics, in which competitions are held. Administrators can see all subjects, create, rename,
   deactivate, reactivate and delete them. Subject names are unique, ignoring case.
3. **Subjects are ready for questions and competitions.** Milestone 9 links every question to a
   subject, and milestone 10 links every competition to one. A deactivated subject will not be
   offered for new questions or competitions. A subject that is in use can never be deleted, so no
   question or competition is ever left pointing at nothing.

The **Teachers** and **Educational institutions** tabs are placeholder pages in this milestone.
Managing educational institutions and teachers arrives in later milestones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator manages the list of subjects (Priority: P1)

An administrator signs in and opens the administrator area, then clicks the **Subjects** tab. The
first time, the list is empty and shows "No subjects yet", with a **Create** button. The
administrator clicks **Create**, types "Mathematics" and saves. They return to the Subjects tab,
where "Mathematics" is listed. They add "Physics" and "Chemistry" the same way. The list shows all
three, sorted by name: Chemistry, Mathematics, Physics.

The administrator then tries to add "physics" (lower case). The form shows again with the entered
value and an error saying a subject with that name already exists. They try to save an empty name.
The form shows again with an error saying the name is required.

**Why this priority**: Subjects are the only real data this milestone adds. Milestones 9 and 10
cannot start without a list of subjects to choose from. This story alone delivers a usable feature.

**Independent Test**: Sign in as an administrator (or create a session directly with the test
support), open the Subjects tab, create subjects and check the list. Submit invalid and duplicate
names and check that each one is refused with the right error and the entered value kept.

**Acceptance Scenarios**:

1. **Given** no subjects exist, **When** an administrator opens the Subjects tab, **Then** the page
   shows "No subjects yet" and a **Create** button.
2. **Given** the Subjects tab is open, **When** the administrator clicks **Create**, enters
   "Mathematics" and saves, **Then** they return to the Subjects tab and "Mathematics" is listed as
   active.
3. **Given** subjects "Physics", "chemistry" and "Mathematics" exist, **When** the Subjects tab is
   opened, **Then** they are listed in alphabetical order ignoring case: chemistry, Mathematics,
   Physics.
4. **Given** "Physics" exists, **When** the administrator creates "  PHYSICS  ", **Then** the form
   shows again with a "name already exists" error and the entered value, and no subject is added.
5. **Given** the create form is open, **When** the administrator saves a name that is empty or only
   spaces, longer than 200 characters after trimming, or contains a control character, **Then** the
   form shows again with an error that explains the rule, the entered value is kept, and no subject
   is added.
6. **Given** the create form is open, **When** the administrator saves "  Computer Science  ",
   **Then** the subject is stored and shown as "Computer Science", with the outer spaces removed.

---

### User Story 2 - An administrator renames, deactivates and deletes subjects (Priority: P2)

Each subject in the list has **Rename**, **Deactivate** and **Delete** buttons. The administrator
notices "Mathmatics" is misspelled, clicks **Rename**, corrects it to "Mathematics" and saves. The
list shows the new name.

The school stops running chemistry competitions for a while. The administrator clicks
**Deactivate** on "Chemistry". It stays in the list, marked as inactive, and from now on it will
not be offered for new questions or competitions (milestones 9 and 10). Its **Deactivate** button
is replaced by **Activate**, which reverses the change.

The administrator created "Biology" by mistake. They click **Delete**, confirm, and the subject is
gone. If a subject were already used by a question or competition, the deletion would be refused
with a message explaining why, and the subject would stay unchanged. The administrator can
deactivate it instead.

**Why this priority**: Mistakes in a list happen, and the list changes over time. Without these
actions the only fix is a database edit. They come after creation because they need subjects to
exist.

**Independent Test**: With a few subjects in place, rename one (including to a duplicate name,
which must be refused), deactivate and reactivate one, and delete an unused one after confirming.
Check that a subject in use cannot be deleted.

**Acceptance Scenarios**:

1. **Given** "Mathmatics" exists, **When** the administrator clicks **Rename**, **Then** a form
   opens with the current name filled in.
2. **Given** the rename form for "Mathmatics" is open, **When** the administrator saves
   "Mathematics", **Then** they return to the Subjects tab and the subject is listed as
   "Mathematics".
3. **Given** "Physics" and "Chemistry" exist, **When** the administrator renames "Chemistry" to
   "physics", **Then** the form shows again with a "name already exists" error and the entered
   value, and "Chemistry" is unchanged.
4. **Given** "physics" exists, **When** the administrator renames it to "Physics" (only the case
   changes), **Then** the rename succeeds.
5. **Given** an active subject, **When** the administrator clicks **Deactivate**, **Then** the
   subject stays in the list, marked as inactive, with an **Activate** button.
6. **Given** an inactive subject, **When** the administrator clicks **Activate**, **Then** the
   subject is marked as active again.
7. **Given** an unused subject, **When** the administrator clicks **Delete**, **Then** a
   confirmation step names the subject and says the deletion cannot be undone. Nothing is deleted
   until the administrator confirms.
8. **Given** the confirmation step for an unused subject, **When** the administrator confirms,
   **Then** the subject is removed and no longer appears in the list. **When** the administrator
   cancels instead, **Then** they return to the list and the subject is unchanged.
9. **Given** a subject that is in use, **When** the administrator confirms its deletion, **Then**
   the deletion is refused with a message saying the subject is in use and can be deactivated
   instead, and the subject is unchanged.

---

### User Story 3 - The administrator area is a set of tabs with their own addresses (Priority: P3)

An administrator clicks the administrator area link on the home page. The address `/admin` takes
them to the **Teachers** tab. Below the header they see three tabs: **Teachers**, **Educational
institutions**, **Subjects**. The **Teachers** tab is highlighted. Clicking another tab opens that
tab's page at its own address, and that tab is highlighted. Reloading a tab, opening its address
directly or using the browser's back button shows the same tab.

The Teachers and Educational institutions tabs show a short note that their features arrive in a
later milestone. The Subjects tab holds the subject list from User Stories 1 and 2. The tabs also
appear on the subject forms and the delete confirmation, with **Subjects** highlighted.

**Why this priority**: The tab structure is what milestones 7 and 8 build on. Its value is
structural, so it ranks below the subject features, which deliver real data now.

**Independent Test**: As an administrator, request `/admin`, `/admin/teachers`,
`/admin/institutions` and `/admin/subjects`. Check the redirect, that each tab page shows all three
tabs, and that exactly the matching tab is highlighted.

**Acceptance Scenarios**:

1. **Given** a signed-in administrator, **When** they open `/admin`, **Then** they are redirected
   to `/admin/teachers`.
2. **Given** a signed-in administrator, **When** they open any of `/admin/teachers`,
   `/admin/institutions` or `/admin/subjects` directly, **Then** the page shows the three tabs in
   the order Teachers, Educational institutions, Subjects, and only the tab for that page is
   highlighted.
3. **Given** the Teachers tab is open, **When** the administrator clicks **Educational
   institutions**, **Then** the browser loads `/admin/institutions` as a normal page and the
   address bar shows that address.
4. **Given** the Teachers or Educational institutions tab is open, **Then** the page shows a short
   placeholder note and no actions.
5. **Given** a subject form or the delete confirmation is open, **Then** the tabs are shown and
   **Subjects** is highlighted.

---

### User Story 4 - Only administrators reach the administrator area (Priority: P4)

A teacher, a student, and a person who is both an administrator and a student but is using the
student role each try to open the administrator tabs and subject forms by typing their addresses.
Each one sees the "access denied" page from milestone 5. An anonymous visitor is sent to the
sign-in page. None of them can create, rename, deactivate, reactivate or delete a subject by
sending a form directly. No page outside the administrator area shows the tabs.

**Why this priority**: Milestone 5 already makes access deny-by-default, so this story mostly
confirms that the new pages follow the existing rules. It is essential but low-risk.

**Independent Test**: For each role and for an anonymous visitor, request every new page and send
every new form. Check that only an administrator using the administrator role succeeds and that
nothing changes in the subject list after a refused request.

**Acceptance Scenarios**:

1. **Given** a person using the teacher or student role, **When** they open any administrator tab
   or subject form, **Then** they see "access denied".
2. **Given** a person using the teacher or student role, **When** they submit any subject action
   directly, **Then** they see "access denied" and no subject changes.
3. **Given** a person who holds the administrator and student roles but is using the student role,
   **When** they open `/admin/subjects`, **Then** they see "access denied". **When** they switch to
   the administrator role, **Then** the page opens.
4. **Given** an anonymous visitor, **When** they open any administrator page, **Then** they are
   redirected to the sign-in page, and after signing in as an administrator they return to that
   page.
5. **Given** a teacher or student is signed in, **When** they open any page they may see, **Then**
   no administrator tabs are shown.

---

### Edge Cases

- **Name with letters outside English**: uniqueness ignores case for all letters, not only Latin
  ones. "Фізика" and "ФІЗИКА" are the same name.
- **Name only differs in inner spaces**: "Computer Science" and "Computer  Science" (two spaces)
  are different names. Only spaces at the start and end are removed.
- **Name exactly 200 characters after trimming**: accepted. 201 characters: refused.
- **Control characters**: a name containing a tab, a line break or any other control character is
  refused, even if it would otherwise be valid.
- **Duplicate of an inactive subject**: creating or renaming to a name already used by an inactive
  subject is refused. Uniqueness covers every subject, active or not.
- **Rename to the same name**: saving the rename form without changes succeeds and changes nothing.
- **Renaming or deactivating an inactive subject**: rename works whatever the status. Deactivating
  an already inactive subject, or activating an active one, changes nothing and is not an error.
- **Subject removed meanwhile**: if another administrator deletes a subject while it is being
  renamed, deactivated or deleted, the action shows a friendly "subject not found" page with a link
  back to the Subjects tab. No error details are shown.
- **Two administrators create the same name at the same moment**: only one subject is stored. The
  other administrator sees the "name already exists" error.
- **Unknown address under `/admin`**: an address such as `/admin/unknown` shows the usual "not
  found" page to administrators. It never shows a different role's page.
- **Delete when nothing yet uses subjects**: no question or competition refers to a subject in this
  milestone, so every subject can be deleted for now. The in-use check still runs, and milestones 9
  and 10 extend it to cover their records.
- **Page reload after a form is saved**: reloading the list after creating, renaming, deactivating
  or deleting does not repeat the action.

## Requirements *(mandatory)*

### Functional Requirements

#### Administrator area and tabs

- **FR-001**: The administrator page from milestone 5 MUST be replaced by an administrator area
  with three tabs, in this order: **Teachers**, **Educational institutions**, **Subjects**.
- **FR-002**: Each tab MUST be its own page with its own address: `/admin/teachers`,
  `/admin/institutions` and `/admin/subjects`. Each tab MUST open correctly when its address is
  entered directly, bookmarked or reloaded.
- **FR-003**: The tabs MUST be a row of ordinary links at the top of every administrator page,
  below the header. Clicking a tab MUST load that tab's page. There is no switching of tabs inside
  the page.
- **FR-004**: The tab for the current page MUST be highlighted, and MUST be marked as the current
  page for assistive technologies. Pages that belong to a tab (subject forms, delete confirmation)
  MUST highlight that tab.
- **FR-005**: Opening `/admin` MUST redirect to `/admin/teachers`.
- **FR-006**: The tabs MUST appear only on administrator-area pages and MUST NOT be shown on any
  page outside it.
- **FR-007**: The **Teachers** and **Educational institutions** tabs MUST be placeholder pages. Each
  shows its title and a short note that its features arrive in a later milestone. They MUST offer
  no actions.
- **FR-008**: The home page link to the administrator area from milestone 5 MUST keep working. It
  leads to the administrator area, which opens on the Teachers tab.

#### Subjects list

- **FR-009**: The **Subjects** tab MUST list all subjects, active and inactive, sorted
  alphabetically by name ignoring case.
- **FR-010**: Each listed subject MUST show its name and whether it is active or inactive.
- **FR-011**: When no subjects exist, the Subjects tab MUST show "No subjects yet".
- **FR-012**: The Subjects tab MUST show a **Create** button. Each listed subject MUST offer
  **Rename**, **Delete**, and either **Deactivate** (when active) or **Activate** (when inactive).

#### Subject names

- **FR-013**: A subject's name MUST be trimmed of spaces at the start and end before it is checked
  and stored. Spaces inside the name MUST be kept as entered.
- **FR-014**: After trimming, a name MUST be 1 to 200 characters long and MUST NOT contain control
  characters (such as tab, line break or other non-printing characters).
- **FR-015**: Subject names MUST be unique across all subjects, active and inactive, ignoring case
  for all letters, including non-Latin ones.
- **FR-016**: Uniqueness MUST hold even when two administrators submit the same name at the same
  time. Only one subject is stored, and the other submission gets the "name already exists" error.

#### Creating a subject

- **FR-017**: **Create** MUST open a form with one field, the name.
- **FR-018**: Saving a valid, unique name MUST create an active subject and return the administrator
  to the Subjects tab, where the new subject is listed.
- **FR-019**: Saving an invalid or duplicate name MUST show the form again with an error message
  that explains the problem and the value the administrator entered. No subject is created.

#### Renaming a subject

- **FR-020**: **Rename** MUST open a form with one field, the name, filled in with the subject's
  current name.
- **FR-021**: A new name MUST follow the same rules as on creation (FR-013 to FR-015). The subject
  being renamed MUST NOT count as a duplicate of itself, so a change of case alone is allowed.
- **FR-022**: Saving a valid name MUST update the subject and return to the Subjects tab. Saving an
  invalid or duplicate name MUST show the form again with the error and the entered value, and the
  subject MUST stay unchanged.
- **FR-023**: Renaming MUST be allowed for active and inactive subjects and MUST NOT change the
  subject's status.

#### Deactivating and activating a subject

- **FR-024**: **Deactivate** MUST mark an active subject as inactive. The subject stays in the list
  and keeps its name.
- **FR-025**: **Activate** MUST mark an inactive subject as active again.
- **FR-026**: Deactivating an inactive subject or activating an active one MUST change nothing and
  MUST NOT show an error.
- **FR-027**: The status MUST be stored so later milestones can rely on it. From milestone 9 on, an
  inactive subject MUST NOT be offered or accepted for new questions or new competitions. Questions
  and competitions that already use it MUST stay valid. This milestone stores and shows the status
  but has no questions or competitions to restrict.

#### Deleting a subject

- **FR-028**: **Delete** MUST first show a confirmation step that names the subject and says that
  deletion cannot be undone. Only an explicit confirmation deletes the subject. Cancelling returns
  to the Subjects tab with nothing changed.
- **FR-029**: Before deleting, the system MUST check whether anything uses the subject. If it is in
  use, the deletion MUST be refused with a message saying the subject is in use and can be
  deactivated instead. The subject MUST stay unchanged.
- **FR-030**: The in-use check MUST be the single place that decides whether a subject may be
  deleted, so later milestones extend it when they add records that use subjects (questions in
  milestone 9, competitions in milestone 10). Whatever records exist, deleting a subject MUST NEVER
  leave a record pointing at a subject that no longer exists.
- **FR-031**: Deleting an unused subject MUST remove it permanently and return to the Subjects tab,
  where it no longer appears. Its name becomes free for a new subject.

#### Shared form and action behaviour

- **FR-032**: Every action that changes a subject (create, rename, deactivate, activate, delete)
  MUST be a form submission that changes data. Opening a page or following a link MUST NEVER change
  a subject.
- **FR-033**: After a successful action, the administrator MUST be sent back to the Subjects tab,
  so reloading the page does not repeat the action.
- **FR-034**: Every action that changes a subject MUST pass the existing cross-site request check.
  A cross-site submission MUST be refused and change nothing.
- **FR-035**: An action or page for a subject that does not exist MUST show a friendly "not found"
  page with a link back to the Subjects tab, without internal error details.

#### Access

- **FR-036**: Every administrator page and every subject action MUST be open only to a person using
  the administrator role, following milestone 5: what counts is the current role, not every role
  the person holds.
- **FR-037**: A signed-in person using any other role MUST get the milestone 5 "access denied" page
  for every administrator page and subject action, and nothing changes.
- **FR-038**: An anonymous visitor MUST be redirected to sign in for every administrator page, and
  return to the requested page after signing in, as in milestone 4.
- **FR-039**: Every new page and action MUST declare which roles may open it, as milestone 5
  requires, so the existing automated check of all routes covers them.

#### Verification and scope

- **FR-040**: Automated tests MUST cover:
  - the `/admin` redirect
  - each tab page with exactly its own tab highlighted
  - creating, renaming, deactivating, activating and deleting a subject
  - every name rule, including the 200-character limit, control characters and duplicates that
    differ only in case, including non-Latin letters
  - refusal to delete a subject in use
  - "access denied" for the teacher and student roles, and for a person with the administrator
    role who is using another role
  - the redirect to sign in for anonymous visitors
- **FR-041**: This milestone MUST NOT add any feature to the Teachers or Educational institutions
  tabs beyond their placeholder pages, and MUST NOT change the teacher, student or staff pages from
  milestone 5.

### Key Entities *(include if feature involves data)*

- **Subject**: a knowledge area in which competitions are held, such as mathematics or physics.
  Attributes: a name (1–200 characters, unique ignoring case) and a status (active or inactive). A
  new subject is active. From milestone 9 on, questions belong to exactly one subject, and from
  milestone 10 on, competitions do. A subject that any record uses cannot be deleted. Only
  administrators create or change subjects.
- **Administrator area tab**: one of the three fixed sections of the administrator area (Teachers,
  Educational institutions, Subjects). Each has a title and an address. The list is fixed and is
  not stored as data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can create a new subject, starting from the Subjects tab, in under
  30 seconds and with no more than 2 clicks plus typing the name.
- **SC-002**: 100% of invalid or duplicate names are refused with a message, and the
  entered value is still in the form.
- **SC-003**: In the automated access check, 100% of administrator pages and subject
  actions refuse every role except administrator, and refuse an administrator who is currently
  using another role.
- **SC-004**: Each of the three tab addresses opens the correct tab when entered directly,
  bookmarked or reloaded, with exactly one highlighted tab.
- **SC-005**: No subject that is in use can be deleted.
- **SC-006**: No two subjects can ever exist with names that differ only in case, including when
  two administrators submit at the same moment.
- **SC-007**: Reloading the page after any successful subject action never repeats the action.
- **SC-008**: All tests from milestones 1–5 still pass unchanged, apart from tests of the old
  administrator placeholder page, which this milestone replaces.

## Assumptions

- **Reactivation is included.** The requirements name only **Deactivate**. The spec adds
  **Activate** so that a deactivation can be undone. Otherwise, a deactivated subject that is in
  use could never be offered again.
- **Delete asks for confirmation**, because deletion cannot be undone. Deactivate and activate are
  reversible and happen at once, with no confirmation.
- **Inactive subjects stay in the list**, marked as inactive and mixed in name order with active
  ones. There is no filter or separate section. The list is expected to stay short (tens of
  subjects).
- **Uniqueness covers inactive subjects too**, so reactivating a subject can never create a
  duplicate.
- **Sorting** is alphabetical ignoring case. Language-specific ordering rules are not required.
- **No paging or search** on the Subjects tab, given the expected size of the list.
- **No starting subjects are created.** The list starts empty. Since no real users exist until all
  milestones are done (product requirements), no migration of existing data is needed.
- **No change history** is kept for subjects. Subject names are not personal data, so the privacy
  rules on logging do not restrict them.
- **The in-use check has nothing to find in this milestone.** No questions or competitions
  reference subjects yet. Milestones 9 and 10 add those references to the check, along with
  acceptance tests that a subject in use cannot be deleted. In this milestone, the refusal path is
  verified with a stand-in record that uses a subject.
- **Placeholder pages** for Teachers and Educational institutions contain only a title and one
  sentence. That matches the milestone 5 placeholders.
- **The home page link** keeps the label from milestone 5 and points to `/admin`, which redirects
  to the Teachers tab.

## Dependencies

- **Milestone 5 (roles and authorization)**: current role, the role-based access check, the
  "access denied" page, the header with the role name, and the automated check that every route
  declares its roles.
- **Milestone 4 (authentication)**: sign-in, sessions, the redirect to sign in with a return
  address, and the cross-site request check for form submissions.
- **Milestone 3 (database and migrations)**: storing subjects with a schema change that runs on
  both the local and the production database.
- **Later milestones that depend on this one**:
  - Later milestones fill the Educational institutions and Teachers tabs.
  - Milestone 9 links questions to subjects and extends the in-use check.
  - Milestone 10 links competitions to subjects and extends the in-use check.

## Out of Scope

- Any feature on the **Teachers** tab (listing, inviting, editing or removing teachers): a later
  milestone.
- Any feature on the **Educational institutions** tab (listing, creating, renaming institutions):
  a later milestone.
- Questions, competitions and anything that uses subjects: milestones 9 and 10.
- Bulk import or export of subjects.
- Subject descriptions, codes, icons or any field other than the name and status.
- A change history for subjects.
- Changes to the teacher, student and staff placeholder pages from milestone 5.
