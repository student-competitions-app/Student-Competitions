# Feature Specification: Administrator Area — Regions and Educational Institutions (Milestone 7)

**Feature Branch**: `007-region-and-institutions-management`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Using product-requirements.md and technical-requirements.md create a 007 feature called 007-region-and-institutions-management."

## Overview

Milestone 7 of the walking skeleton for the Student Competitions application. Milestone 6 turned
the administrator page into a tabbed area. Its **Subjects** tab works, but its **Educational
institutions** tab is still a placeholder.

This milestone replaces that placeholder with a page that shows two lists side by side: **regions**
on the left and the **educational institutions** of the selected region on the right. Three things
become true when this milestone is done:

1. **Administrators keep a list of regions.** There is no preset list. Administrators create,
   rename, deactivate, reactivate and delete regions themselves. Region names are unique, ignoring
   case.
2. **Administrators keep the educational institutions of each region.** Every institution belongs
   to exactly one region and never moves to another. Institution names are unique within a region,
   ignoring case. The same name may exist in different regions.
3. **The lists are ready for teachers and students.** Milestone 8 links teachers to institutions,
   and milestone 9 links students to them. A deactivated institution, or any institution in a
   deactivated region, will not be offered there. An institution that is in use can never be
   deleted, and a region that still holds institutions can never be deleted, so nothing is ever
   left pointing at a record that no longer exists.

The **Teachers** tab stays a placeholder in this milestone. The **Subjects** tab is unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator builds the list of regions (Priority: P1)

An administrator opens the administrator area and clicks the **Educational institutions** tab. The
first time, the left side shows "No regions yet" and a **Create** button, and the right side shows
"Select a region". The administrator clicks **Create**, types "Kyiv" and saves. They return to the
tab, where "Kyiv" is listed. They add "Lviv" and "Odesa" the same way. The list shows all three,
sorted by name.

The administrator then tries to add "kyiv" (lower case). The form shows again with the entered
value and an error saying a region with that name already exists. They try to save an empty name,
and the form shows again with an error saying the name is required.

**Why this priority**: Every institution belongs to a region, so nothing else in this milestone
works without regions. This story alone delivers a usable list.

**Independent Test**: Sign in as an administrator (or create a session directly with the test
support), open the Educational institutions tab, create regions and check the list. Submit invalid
and duplicate names and check that each one is refused with the right error and the entered value
kept.

**Acceptance Scenarios**:

1. **Given** no regions exist, **When** an administrator opens the Educational institutions tab,
   **Then** the left side shows "No regions yet" and a **Create** button, and the right side shows
   "Select a region".
2. **Given** the tab is open, **When** the administrator creates the region "Kyiv", **Then** they
   return to the tab and "Kyiv" is listed as active.
3. **Given** regions "Odesa", "kyiv" and "Lviv" exist, **When** the tab is opened, **Then** they are
   listed in alphabetical order ignoring case: kyiv, Lviv, Odesa.
4. **Given** "Kyiv" exists, **When** the administrator creates "  KYIV  ", **Then** the form shows
   again with a "name already exists" error and the entered value, and no region is added.
5. **Given** the create form is open, **When** the administrator saves a name that is empty or only
   spaces, longer than 200 characters after trimming, or contains a control character, **Then** the
   form shows again with an error that explains the rule, the entered value is kept, and no region
   is added.
6. **Given** the create form is open, **When** the administrator saves "  Kharkiv Region  ",
   **Then** the region is stored and shown as "Kharkiv Region", with the outer spaces removed.

---

### User Story 2 - An administrator adds educational institutions to a region (Priority: P1)

The administrator clicks "Kyiv" in the region list. "Kyiv" is highlighted, and the right side shows
"No educational institutions yet" and a **Create** button. The administrator clicks **Create**,
types "Kyiv Polytechnic Institute" and saves. They return to the tab with "Kyiv" still selected, and
the new institution is listed on the right. They add a second institution the same way.

The administrator then selects "Lviv" and creates an institution there called "Kyiv Polytechnic
Institute" too. This works, because the same name may exist in different regions. Adding "kyiv
polytechnic institute" to "Kyiv" a second time is refused with a "name already exists in this
region" error.

**Why this priority**: Institutions are what milestones 8 and 9 actually need. Regions exist only
to group them. This story shares the top priority with regions because neither is useful alone.

**Independent Test**: With at least two regions in place, select a region, create institutions and
check that they appear only under that region. Check that the same name is accepted in a different
region and refused in the same one. Check that **Create** is not offered when no region is
selected.

**Acceptance Scenarios**:

1. **Given** regions exist and none is selected, **When** the administrator opens the tab, **Then**
   the right side shows "Select a region" and no **Create** button for institutions.
2. **Given** the administrator clicks the region "Kyiv", **Then** "Kyiv" is highlighted in the left
   list and the right side shows the institutions of Kyiv, or "No educational institutions yet" if
   it has none, with a **Create** button.
3. **Given** "Kyiv" is selected, **When** the administrator creates the institution "Kyiv
   Polytechnic Institute", **Then** they return to the tab with "Kyiv" still selected and the new
   institution listed as active.
4. **Given** "Kyiv" holds "Kyiv Polytechnic Institute", **When** the administrator selects "Lviv"
   and creates an institution with the same name, **Then** it is created in Lviv, and each region
   shows only its own institution.
5. **Given** "Kyiv" holds "Kyiv Polytechnic Institute", **When** the administrator creates "  KYIV
   POLYTECHNIC INSTITUTE  " in Kyiv, **Then** the form shows again with a "name already exists in
   this region" error and the entered value, and no institution is added.
6. **Given** the institution create form is open, **When** the administrator saves an invalid name
   (empty, longer than 200 characters after trimming, or with a control character), **Then** the
   form shows again with the error and the entered value, and no institution is added.
7. **Given** a region holds institutions "Zaporizhzhia College", "art school" and "Academy",
   **When** that region is selected, **Then** the institutions are listed alphabetically ignoring
   case: Academy, art school, Zaporizhzhia College.
8. **Given** a region is selected, **When** the administrator reloads the page or opens its address
   from a bookmark, **Then** the same region is still selected.

---

### User Story 3 - An administrator renames, deactivates and deletes regions (Priority: P2)

Each region in the list has **Rename**, **Deactivate** and **Delete** buttons. The administrator
notices "Lvov" is misspelled, clicks **Rename**, corrects it to "Lviv" and saves.

The region "Odesa" will not run competitions for a while. The administrator clicks **Deactivate**
on it. "Odesa" stays in the list, marked as deactivated, and its **Deactivate** button is replaced
by **Activate**. When "Odesa" is selected, its institutions are still listed, but no new
institution can be created there, and its institutions will not be offered when inviting or
editing teachers (milestone 8) or students (milestone 9). **Activate** reverses this.

The administrator created the region "Test" by mistake and it holds no institutions. They click
**Delete**, confirm, and the region is gone. They then try to delete "Kyiv", which holds
institutions. The deletion is refused with a message saying the region still holds educational
institutions, and "Kyiv" stays unchanged.

**Why this priority**: Mistakes in a list happen, and regions change over time. These actions come
after creation because they need regions to exist.

**Independent Test**: With a few regions in place, rename one (including to a duplicate name,
which must be refused), deactivate and reactivate one, delete an empty one after confirming, and
check that a region with an active or a deactivated institution cannot be deleted.

**Acceptance Scenarios**:

1. **Given** the region "Lvov" exists, **When** the administrator clicks **Rename**, **Then** a form
   opens with the current name filled in.
2. **Given** the rename form for "Lvov" is open, **When** the administrator saves "Lviv", **Then**
   they return to the tab and the region is listed as "Lviv".
3. **Given** "Kyiv" and "Lviv" exist, **When** the administrator renames "Lviv" to "KYIV", **Then**
   the form shows again with a "name already exists" error and the entered value, and "Lviv" is
   unchanged.
4. **Given** "kyiv" exists, **When** the administrator renames it to "Kyiv" (only the case
   changes), **Then** the rename succeeds.
5. **Given** an active region, **When** the administrator clicks **Deactivate**, **Then** the region
   stays in the list, marked as deactivated, with an **Activate** button.
6. **Given** a deactivated region is selected, **Then** its institutions are still listed, the
   **Create** button for institutions is not offered, and the page says that new institutions
   cannot be added to a deactivated region.
7. **Given** a deactivated region, **When** an institution creation for that region is submitted
   directly, **Then** it is refused and no institution is added.
8. **Given** a deactivated region, **When** the administrator clicks **Activate**, **Then** the
   region is marked as active again and **Create** is offered for its institutions.
9. **Given** a region with no institutions, **When** the administrator clicks **Delete**, **Then** a
   confirmation step names the region and says that deletion cannot be undone. Nothing is deleted
   until the administrator confirms. Cancelling returns to the tab with nothing changed.
10. **Given** the confirmation step for a region with no institutions, **When** the administrator
    confirms, **Then** the region is removed and no longer appears in the list.
11. **Given** a region that holds at least one institution, active or deactivated, **When** the
    administrator confirms its deletion, **Then** the deletion is refused with a message saying the
    region still holds educational institutions, and the region is unchanged.

---

### User Story 4 - An administrator renames, deactivates and deletes institutions (Priority: P2)

Each institution in the right-hand list has **Rename**, **Deactivate** and **Delete** buttons. The
administrator fixes a typo with **Rename**. The rename form has only the name: an institution
cannot be moved to another region.

An institution has closed. The administrator clicks **Deactivate**. It stays in the list, marked as
deactivated, and from milestone 8 on it will not be offered when inviting or editing teachers or
students. **Activate** reverses this.

An institution was created by mistake. The administrator clicks **Delete**, confirms, and the
institution is gone. Nothing uses institutions in this milestone, so deletion always succeeds now.
From milestone 8 on, a linked teacher or student will make the deletion be refused.

**Why this priority**: Same reasons as for regions: lists need correcting and change over time.

**Independent Test**: With a region holding a few institutions, rename one (including to a name
already used in the same region, which must be refused, and to a name used in another region,
which must succeed), deactivate and reactivate one, and delete one after confirming.

**Acceptance Scenarios**:

1. **Given** an institution, **When** the administrator clicks **Rename**, **Then** a form opens with
   the current name filled in and no way to choose a region.
2. **Given** the rename form is open, **When** the administrator saves a valid new name, **Then**
   they return to the tab with the institution's region selected and the new name listed.
3. **Given** a region holds "Academy" and "College", **When** the administrator renames "College" to
   "academy", **Then** the form shows again with a "name already exists in this region" error and
   the entered value, and "College" is unchanged.
4. **Given** "Academy" exists in Kyiv, **When** the administrator renames an institution in Lviv to
   "Academy", **Then** the rename succeeds.
5. **Given** an active institution, **When** the administrator clicks **Deactivate**, **Then** it
   stays in the list, marked as deactivated, with an **Activate** button. **When** they click
   **Activate**, **Then** it is marked as active again.
6. **Given** an institution, **When** the administrator clicks **Delete**, **Then** a confirmation
   step names the institution and its region and says that deletion cannot be undone. Cancelling
   returns to the tab with that region selected and nothing changed.
7. **Given** the confirmation step for an unused institution, **When** the administrator confirms,
   **Then** the institution is removed and the tab shows its region with the institution gone.
8. **Given** an institution that is in use, **When** the administrator confirms its deletion,
   **Then** the deletion is refused with a message saying the institution is in use and can be
   deactivated instead, and the institution is unchanged.
9. **Given** an institution in a deactivated region, **Then** it can still be renamed, deactivated,
   activated and deleted.

---

### User Story 5 - Only administrators manage regions and institutions (Priority: P3)

A teacher, a student, and a person who is both an administrator and a teacher but is using the
teacher role each try to open the Educational institutions tab and its forms by typing their
addresses. Each one sees the "access denied" page from milestone 5. An anonymous visitor is sent to
the sign-in page. None of them can change a region or an institution by sending a form directly.

**Why this priority**: Milestone 5 already makes access deny-by-default, so this story mostly
confirms that the new pages follow the existing rules. It is essential but low-risk.

**Independent Test**: For each role and for an anonymous visitor, request every new page and send
every new form. Check that only an administrator using the administrator role succeeds and that no
region or institution changes after a refused request.

**Acceptance Scenarios**:

1. **Given** a person using the teacher or student role, **When** they open the Educational
   institutions tab or any region or institution form, **Then** they see "access denied".
2. **Given** a person using the teacher or student role, **When** they submit any region or
   institution action directly, **Then** they see "access denied" and nothing changes.
3. **Given** a person who holds the administrator and teacher roles but is using the teacher role,
   **When** they open the Educational institutions tab, **Then** they see "access denied". **When**
   they switch to the administrator role, **Then** the page opens.
4. **Given** an anonymous visitor, **When** they open the Educational institutions tab with a region
   selected, **Then** they are redirected to the sign-in page, and after signing in as an
   administrator they return to that page with the same region selected.

---

### Edge Cases

- **Names with letters outside English**: uniqueness ignores case for all letters, not only Latin
  ones. "Київ" and "КИЇВ" are the same region name.
- **Names that differ only in inner spaces**: "Kyiv Region" and "Kyiv  Region" (two spaces) are
  different names. Only spaces at the start and end are removed.
- **Name exactly 200 characters after trimming**: accepted. 201 characters: refused.
- **Control characters**: a name containing a tab, a line break or any other control character is
  refused, even if it would otherwise be valid.
- **Duplicate of a deactivated item**: creating or renaming to a name already used by a deactivated
  region (or, within the same region, a deactivated institution) is refused. Uniqueness covers
  every item, active or not.
- **Rename to the same name**: saving a rename form without changes succeeds and changes nothing.
- **Repeated status changes**: deactivating an already deactivated region or institution, or
  activating an active one, changes nothing and is not an error.
- **Deactivating a region does not change its institutions**: each institution keeps its own
  status. When the region is activated again, its institutions are exactly as they were. An
  institution counts as available for selection (milestones 8 and 9) only when both it and its
  region are active.
- **Deactivated institution in an active region, and active institution in a deactivated region**:
  both are listed. The first is marked as deactivated. The second keeps its own status, and the
  selected region is marked as deactivated.
- **Region with only deactivated institutions**: still cannot be deleted. The administrator must
  delete its institutions first.
- **Region removed meanwhile**: if another administrator deletes a region while it is selected or
  being renamed, deactivated or deleted, or while an institution is being created in it, the action
  shows a friendly "region not found" page with a link back to the tab. No error details are shown.
- **Institution removed meanwhile**: the same, with an "educational institution not found" page.
- **Region selected by an address that does not exist**: shows the same friendly "region not found"
  page.
- **Institution acted on through the wrong region**: an action that names an institution together
  with a region it does not belong to is refused as "not found" and changes nothing. An institution
  can never be moved between regions this way.
- **Two administrators create the same name at the same moment**: only one item is stored. The
  other administrator sees the "name already exists" error. The same holds for two institutions
  with the same name in the same region.
- **Last institution deleted**: the region stays selected and shows "No educational institutions
  yet".
- **Delete when nothing yet uses institutions**: no teacher or student refers to an institution in
  this milestone, so every institution can be deleted for now. The in-use check still runs, and
  milestones 8 and 9 extend it to cover their records.
- **Page reload after a form is saved**: reloading the tab after creating, renaming, deactivating,
  activating or deleting does not repeat the action.

## Requirements *(mandatory)*

### Functional Requirements

#### Page layout

- **FR-001**: The **Educational institutions** tab (`/admin/institutions`) MUST replace its
  milestone 6 placeholder with two lists side by side: regions on the left and the educational
  institutions of the selected region on the right.
- **FR-002**: Clicking a region MUST select it. The selected region MUST be highlighted and MUST be
  marked as the current item for assistive technologies.
- **FR-003**: The selected region MUST be part of the page address, so the page opens with the same
  region selected when it is reloaded, bookmarked, opened directly or reached with the browser's
  back button.
- **FR-004**: With no region selected, the right side MUST show "Select a region" and no
  institution actions.
- **FR-005**: The milestone 6 tabs MUST keep working unchanged. Every page of this feature (the
  tab, its forms and its confirmation steps) MUST show the tabs with **Educational institutions**
  highlighted.
- **FR-006**: On narrow screens the two lists MAY be shown one above the other, regions first,
  as long as both stay usable.

#### Regions list

- **FR-007**: The region list MUST show all regions, active and deactivated, sorted alphabetically
  by name ignoring case.
- **FR-008**: Each listed region MUST show its name and, when deactivated, a mark saying it is
  deactivated.
- **FR-009**: When no regions exist, the region list MUST show "No regions yet".
- **FR-010**: The region list MUST show a **Create** button. Each listed region MUST offer
  **Rename**, **Delete**, and either **Deactivate** (when active) or **Activate** (when
  deactivated).

#### Institutions list

- **FR-011**: The institution list MUST show all institutions of the selected region, active and
  deactivated, sorted alphabetically by name ignoring case. It MUST NOT show institutions of other
  regions.
- **FR-012**: Each listed institution MUST show its name and, when deactivated, a mark saying it is
  deactivated.
- **FR-013**: When the selected region has no institutions, the list MUST show "No educational
  institutions yet".
- **FR-014**: The institution list MUST show a **Create** button only when the selected region is
  active. When the selected region is deactivated, the list MUST say that new institutions cannot
  be added to a deactivated region.
- **FR-015**: Each listed institution MUST offer **Rename**, **Delete**, and either **Deactivate**
  (when active) or **Activate** (when deactivated), whatever the status of its region.

#### Names

- **FR-016**: A region or institution name MUST be trimmed of spaces at the start and end before it
  is checked and stored. Spaces inside the name MUST be kept as entered.
- **FR-017**: After trimming, a name MUST be 1 to 200 characters long and MUST NOT contain control
  characters (such as tab, line break or other non-printing characters).
- **FR-018**: Region names MUST be unique across all regions, active and deactivated, ignoring case
  for all letters, including non-Latin ones.
- **FR-019**: Institution names MUST be unique within their region, across its active and
  deactivated institutions, ignoring case in the same way. The same name MAY exist in different
  regions.
- **FR-020**: Uniqueness MUST hold even when two administrators submit the same name at the same
  time. Only one item is stored, and the other submission gets the "name already exists" error.
- **FR-021**: The error messages MUST tell the two uniqueness rules apart: a region name "already
  exists", and an institution name "already exists in this region".

#### Creating

- **FR-022**: **Create** for regions MUST open a form with one field, the name. Saving a valid,
  unique name MUST create an active region and return to the tab with the new region selected.
- **FR-023**: **Create** for institutions MUST open a form with one field, the name, for the
  selected region. The form MUST show which region the institution is being added to. Saving a
  valid name that is unique within the region MUST create an active institution in that region and
  return to the tab with that region selected.
- **FR-024**: Creating an institution MUST be refused when the region does not exist or is
  deactivated, including when the request is sent directly without the button. No institution is
  created.
- **FR-025**: Saving an invalid or duplicate name on either form MUST show the form again with an
  error message that explains the problem and the value the administrator entered. Nothing is
  created.

#### Renaming

- **FR-026**: **Rename** for a region or an institution MUST open a form with one field, the name,
  filled in with the current name.
- **FR-027**: A new name MUST follow the same rules as on creation (FR-016 to FR-019). The item
  being renamed MUST NOT count as a duplicate of itself, so a change of case alone is allowed.
- **FR-028**: Saving a valid name MUST update the item and return to the tab with the relevant
  region selected. Saving an invalid or duplicate name MUST show the form again with the error and
  the entered value, and the item MUST stay unchanged.
- **FR-029**: Renaming MUST be allowed for active and deactivated items and MUST NOT change their
  status.
- **FR-030**: An institution MUST NOT be movable to another region, by the rename form or by any
  other action.

#### Deactivating and activating

- **FR-031**: **Deactivate** MUST mark an active region or institution as deactivated. It stays in
  its list and keeps its name. **Activate** MUST mark it as active again.
- **FR-032**: Deactivating a deactivated item, or activating an active one, MUST change nothing and
  MUST NOT show an error.
- **FR-033**: Deactivating or activating a region MUST NOT change the status of its institutions.
- **FR-034**: The statuses MUST be stored so later milestones can rely on them. An institution is
  available for selection only when it is active and its region is active. From milestone 8 on,
  only available institutions MUST be offered or accepted when inviting or editing teachers, and
  from milestone 9 on, students. Existing links to an institution that later becomes unavailable
  MUST stay valid. This milestone stores and shows the statuses but has nothing to restrict yet
  beyond FR-024.

#### Deleting

- **FR-035**: **Delete** for a region or an institution MUST first show a confirmation step that
  names the item (for an institution, also its region) and says that deletion cannot be undone.
  Only an explicit confirmation deletes it. Cancelling returns to the tab with nothing changed.
- **FR-036**: Deleting a region MUST be refused while it holds any institution, active or
  deactivated, with a message saying the region still holds educational institutions. The region
  MUST stay unchanged.
- **FR-037**: Before deleting an institution, the system MUST check whether anything uses it. If it
  is in use, the deletion MUST be refused with a message saying the institution is in use and can
  be deactivated instead. The institution MUST stay unchanged.
- **FR-038**: The institution in-use check MUST be the single place that decides whether an
  institution may be deleted, so later milestones extend it when they add records that use
  institutions (teacher links in milestone 8, students in milestone 9). Whatever records exist,
  deleting a region or an institution MUST NEVER leave a record pointing at something that no
  longer exists.
- **FR-039**: Deleting an empty region MUST remove it permanently and return to the tab with no
  region selected. Deleting an unused institution MUST remove it permanently and return to the tab
  with its region selected. The deleted item's name becomes free for a new item.

#### Shared form and action behaviour

- **FR-040**: Every action that changes a region or an institution (create, rename, deactivate,
  activate, delete) MUST be a form submission that changes data. Opening a page, selecting a region
  or following a link MUST NEVER change anything.
- **FR-041**: After a successful action, the administrator MUST be sent back to the tab, so
  reloading the page does not repeat the action.
- **FR-042**: Every action that changes a region or an institution MUST pass the existing
  cross-site request check. A cross-site submission MUST be refused and change nothing.
- **FR-043**: A page or action for a region or institution that does not exist, or for an
  institution named together with a region it does not belong to, MUST show a friendly "not found"
  page with a link back to the tab, without internal error details.

#### Access

- **FR-044**: The Educational institutions tab and every region and institution page and action
  MUST be open only to a person using the administrator role, following milestone 5: what counts
  is the current role, not every role the person holds.
- **FR-045**: A signed-in person using any other role MUST get the milestone 5 "access denied" page
  for every such page and action, and nothing changes.
- **FR-046**: An anonymous visitor MUST be redirected to sign in for every such page, and return to
  the requested page, including the selected region, after signing in, as in milestone 4.
- **FR-047**: Every new page and action MUST declare which roles may open it, as milestone 5
  requires, so the existing automated check of all routes covers them.

#### Verification and scope

- **FR-048**: Automated tests MUST cover:
  - the two-list layout, "Select a region", "No regions yet" and "No educational institutions yet"
  - the selected region kept in the page address and highlighted
  - creating, renaming, deactivating, activating and deleting regions and institutions
  - every name rule, including the 200-character limit, control characters, and duplicates that
    differ only in case, including non-Latin letters
  - institution names unique within a region and allowed again in another region
  - refusal to create an institution with no region, in an unknown region or in a deactivated
    region, including direct submissions
  - refusal to delete a region holding active or deactivated institutions
  - refusal to delete an institution in use
  - deactivating a region leaving its institutions' statuses unchanged
  - "access denied" for the teacher and student roles, and for a person with the administrator
    role who is using another role
  - the redirect to sign in for anonymous visitors
- **FR-049**: This milestone MUST NOT add any feature to the **Teachers** tab beyond its
  placeholder page, MUST NOT change the **Subjects** tab, and MUST NOT change the teacher, student
  and staff pages from milestone 5.

### Key Entities *(include if feature involves data)*

- **Region**: a geographic grouping of educational institutions, created by administrators.
  Attributes: a name (1–200 characters, unique ignoring case) and a status (active or deactivated).
  A new region is active. A region holds zero or more institutions and cannot be deleted while it
  holds any. While deactivated, no institution can be added to it and none of its institutions is
  available for selection.
- **Educational institution**: a school, college or university to which teachers (milestone 8)
  and students (milestone 9) are linked. Attributes: a name (1–200 characters, unique ignoring
  case within its region), a status (active or deactivated) and the region it belongs to, which
  never changes. A new institution is active. It is available for selection only when it and its
  region are both active. An institution that any record uses cannot be deleted. Only
  administrators create or change institutions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting from an empty tab, an administrator can create a region and add an
  institution to it in under 1 minute.
- **SC-002**: 100% of invalid or duplicate names, for regions and institutions, are refused with a
  message, and the entered value is still in the form.
- **SC-003**: In the automated access check, 100% of the new pages and actions refuse every role
  except administrator, and refuse an administrator who is currently using another role.
- **SC-004**: Reloading or bookmarking the tab with a region selected opens it with the same region
  selected every time.
- **SC-005**: No region that holds an institution, and no institution that is in use, can be
  deleted.
- **SC-006**: No two regions, and no two institutions in the same region, can ever exist with names
  that differ only in case, including when two administrators submit at the same moment.
- **SC-007**: No institution can be created in a deactivated region, whether through the page or by
  sending the form directly.
- **SC-008**: Reloading the page after any successful action never repeats the action.
- **SC-009**: All tests from milestones 1–6 still pass unchanged, apart from tests of the old
  Educational institutions placeholder page, which this milestone replaces.

## Assumptions

- **Selecting a region is navigation, not a change.** It updates the page address, the same way the
  milestone 6 tabs do, so the selection survives reloads and bookmarks.
- **After an action, the relevant region stays selected**: the new region after creating one, and
  the institution's region after any institution action. Deleting a region returns to the tab with
  no region selected.
- **Delete asks for confirmation**, for regions and institutions, matching the subject deletion in
  milestone 6. Deactivate and activate are reversible and happen at once, with no confirmation.
- **Deactivated items stay in their lists**, marked as deactivated and mixed in name order with
  active ones. There is no filter or separate section.
- **Uniqueness covers deactivated items too**, so activating an item can never create a duplicate.
- **Deactivating a region does not cascade.** Institution statuses are independent of the region's.
  Availability for selection combines both, as the technical requirements describe.
- **Institutions in a deactivated region stay fully manageable** (rename, deactivate, activate,
  delete). The requirements only block creating new institutions there.
- **Sorting** is alphabetical ignoring case. Language-specific ordering rules are not required.
- **No paging or search** in either list. Both are expected to stay short (tens of regions,
  tens of institutions per region).
- **No starting regions or institutions are created.** Both lists start empty. Since no real users
  exist until all milestones are done (product requirements), no migration of existing data is
  needed.
- **No change history** is kept for regions or institutions. Their names are not personal data, so
  the privacy rules on logging do not restrict them.
- **The institution in-use check has nothing to find in this milestone.** No teacher or student
  refers to an institution yet. Milestones 8 and 9 add those references to the check, along with
  acceptance tests. In this milestone, the refusal path is verified with a stand-in record that
  uses an institution, as was done for subjects in milestone 6.
- **Showing an institution as "Name (Region)"** in pickers belongs to milestone 8, where the first
  picker appears. This milestone always shows institutions under their region.

## Dependencies

- **Milestone 6 (administrator area)**: the tab row, the Educational institutions tab address, the
  tab highlighting, and the name rules and page patterns established for subjects.
- **Milestone 5 (roles and authorization)**: current role, the role-based access check, the
  "access denied" page, the header with the role name, and the automated check that every route
  declares its roles.
- **Milestone 4 (authentication)**: sign-in, sessions, the redirect to sign in with a return
  address, and the cross-site request check for form submissions.
- **Milestone 3 (database and migrations)**: storing regions and institutions with a schema change
  that runs on both the local and the production database.
- **Later milestones that depend on this one**:
  - Milestone 8 links teachers to institutions, offers only available institutions shown as
    "Name (Region)", and extends the institution in-use check.
  - Milestone 9 links students to institutions and extends the in-use check again.

## Out of Scope

- Any feature on the **Teachers** tab: milestone 8.
- Linking teachers or students to institutions, and institution pickers: milestones 8 and 9.
- Moving an institution to another region.
- A preset list of regions, or importing regions or institutions in bulk.
- Region or institution fields other than the name, status and (for institutions) region, such as
  addresses, codes or contact details.
- A change history for regions or institutions.
- Changes to the **Subjects** tab or to the teacher, student and staff placeholder pages.
