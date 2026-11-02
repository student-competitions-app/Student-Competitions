# Feature Specification: Creating, Editing and Cancelling Competitions (Teacher) (Milestone 12.1)

**Feature Branch**: `012.1-teacher-competitions`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: milestone 12.1 of `docs/requirements/milestones.md` ("Creating, editing
and cancelling competitions (teacher)"), part of the 12.x group "Competitions", with
`product-requirements.md` (the **Competition** section, "Competition statuses", "Teacher access
rights to competitions" and the **Subject** section), the milestone 6, 10, 10.1, 11 and 11.1
specifications and `docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 12.1 of the walking skeleton for the Student Competitions application, and the first of
the 12.x milestones that build the teacher's side of competitions. After milestone 11.1, teachers
manage students, teams and the question bank, but the **Competitions** tab of the teacher area is
still the placeholder of milestone 9.

This milestone fills that tab. A competition here has only a **subject**, a **name** and a **start**
(a date and a time to the minute); its questions, its teams and stopping it come in later 12.x
milestones. Eight things become true when this milestone is done:

1. **Every teacher sees the competitions of a subject.** The **Competitions** tab
   (`/teacher/competitions`) chooses a subject the way **Questions** does and lists its
   competitions, latest start first, 10 per page, with a status filter.
2. **A teacher with Can manage competitions creates, edits and cancels them.** Any such teacher acts
   on any competition, whoever created it; there are no rights per competition, and who created a
   competition is neither stored nor shown.
3. **A competition has a status that nobody has to set.** It is **Upcoming** until its start and
   **In progress** from then on, worked out by the server from the stored start whenever it is shown
   or checked. **Cancelled** is final. **Finished** is reached by stopping, which a later 12.x
   milestone adds, but the list, the filter and the deactivated-subject rules already handle it.
4. **Only an upcoming competition can be edited; any competition that is not finished can be
   cancelled.** Each attempt outside these rules shows a clear refusal and changes nothing.
5. **Names are unique only among live competitions.** Within a subject, no two upcoming or
   in-progress competitions share a name ignoring case; once finished or cancelled, a name is free
   again.
6. **Times are right in every time zone.** Starts are stored in UTC. The browser only reports its
   time zone; the server reads what the teacher typed in that zone, handles clock changes, and shows
   every start in that zone, or in UTC labelled "UTC" when no zone is known.
7. **Deactivating a subject hides its competitions that are not finished.** Its finished
   competitions stay available, read-only, under "Deactivated subjects", so their results can be
   reviewed in milestone 15. A subject used by any competition cannot be deleted.
8. **The component library grows first.** The actions menu, the date and time fields with their
   time-zone hint, the competition status badge, the local-time display, a back label for
   confirmations and option groups for the chained-list selector are added to the library, the
   component gallery (`/admin/components`) and the UI guidelines before any page uses them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher creates a competition (Priority: P1)

Olena is a teacher with **Can manage competitions**; her browser is in `Europe/Kyiv`. She opens the
teacher area and chooses the **Competitions** tab, then "Chemistry" in the subject list. The subject
has no competitions yet, so the page shows "No competitions yet" with the hint "Add the first
competition with Add competition.". She presses **Add competition** beside the page heading. The
page "Add competition" shows "Chemistry" as text and three fields, **Name**, **Start date** and
**Start time**, with "Time zone: Europe/Kyiv" under the time. She types "Spring round", 14 March 2027
and 10:00 and presses **Save competition**. She is back on the list of "Chemistry" with the status
**All**, at the new row, with the notice "Competition “Spring round” was added". The row shows "Spring
round", "14 March 2027, 10:00" and the badge **Upcoming**. The competition is stored as 08:00 UTC.

**Why this priority**: Creating competitions is the reason the tab exists; every later 12.x
milestone (questions, teams, stopping) builds on a stored competition.

**Independent Test**: Sign in as a teacher with the setting, with the browser time zone set to
`Europe/Kyiv`, create a competition, and check the landing page, the notice, the row, the displayed
time and the stored UTC moment.

**Acceptance Scenarios**:

1. **Given** a teacher opens the teacher area, **When** they choose **Competitions**, **Then**
   `/teacher/competitions` opens with a subject list, and the tab row is unchanged (**Students**,
   **Teams**, **Questions**, **Competitions**).
2. **Given** Olena has the setting and an active subject is chosen, **When** the list is shown,
   **Then** **Add competition** stands beside the page heading.
3. **Given** she presses **Add competition**, **When** the form opens, **Then** its title is "Add
   competition", it has a back link, shows the subject as text, and has the fields **Name**, **Start
   date** and **Start time** (the browser's own date and time fields), with "Time zone:
   Europe/Kyiv" under the time field.
4. **Given** a valid name and a start in the future, **When** she presses **Save competition**,
   **Then** the competition is created in the chosen subject, and she lands on its list with the
   status **All**, on the page that contains the new competition, at it, with the notice
   "Competition “Spring round” was added".
5. **Given** she entered 14 March 2027, 10:00 in `Europe/Kyiv`, **When** the competition is stored,
   **Then** its start is 14 March 2027, 08:00 UTC, and the list shows "14 March 2027, 10:00".
6. **Given** a competition was created, **When** it is listed, **Then** its status is **Upcoming**.
7. **Given** she presses **Cancel** on the form, **When** she returns, **Then** she is on the page
   she came from, at the same place, and nothing is stored.
8. **Given** the subject list offers only one subject, **When** the tab opens, **Then** that subject
   is chosen automatically.

---

### User Story 2 - The list of competitions (Priority: P1)

Mykola is a teacher without **Can manage competitions**. He opens **Competitions** and chooses
"Chemistry". It has 35 competitions; he sees the 10 with the latest start, "Competitions 1–10 of
35", and page navigation above and below. He chooses **Upcoming** in the **Status** list, and the
list shows only upcoming competitions, from the first page, with no button to press. He moves to the
second page; the status stays **Upcoming**. He sees no **Add competition** and no actions menus.

**Why this priority**: Every teacher needs to see what competitions exist, and the list is where
every action starts and returns.

**Independent Test**: Seed a subject with competitions of every status and with equal and different
starts, and check the order, the paging, the filter, the address and the empty states, as teachers
with and without the setting.

**Acceptance Scenarios**:

1. **Given** a subject is chosen, **When** the list is shown, **Then** its competitions are shown in
   a data table (labelled cards on a phone) with the name, the start and the status badge, and no
   column naming who created them.
2. **Given** competitions starting on 15 March, 1 March and 25 March, **When** they are listed,
   **Then** they appear as 25 March, 15 March, 1 March, whatever their status.
3. **Given** two competitions with the same start, **When** they are listed, **Then** they are
   ordered by name ignoring case.
4. **Given** a subject with 25 competitions, **When** the list is shown, **Then** it shows 10 per
   page with the page navigation of **Questions** above and below ("Competitions 11–20 of 25" on the
   second page).
5. **Given** the **Status** list above the table, **When** it is opened, **Then** it offers **All**
   (the default), **Upcoming**, **In progress**, **Finished** and **Cancelled**; **When** an item is
   chosen, **Then** it applies at once, with no button to press, and the first page opens.
6. **Given** a status is chosen, **When** the teacher moves between pages, **Then** only matching
   competitions are shown and the status is kept.
7. **Given** the subject, the status and the page, **When** the page is reloaded or bookmarked,
   **Then** they are kept in the page address and restored.
8. **Given** the teacher chooses another subject or another status, **When** the list is shown,
   **Then** the first page opens.
9. **Given** a subject has no competitions, **When** the list is shown, **Then** it shows "No
   competitions yet", with the hint "Add the first competition with Add competition." for a teacher
   with the setting and no hint for any other teacher.
10. **Given** a status matches nothing, **When** the list is shown, **Then** it shows "No
    competitions with this status" with the hint "Choose another status, or All.".
11. **Given** no subject is chosen, **When** the tab is shown, **Then** it shows "Select a subject"
    with the hint "Choose a subject in the list above to see its competitions.".
12. **Given** no subject is offered at all, **When** the tab is shown, **Then** it shows "No subjects
    yet" with the hint "Ask an administrator to add a subject.".
13. **Given** Mykola has no setting, **When** he views any list, **Then** he sees no **Add
    competition** and no actions menus.

---

### User Story 3 - A teacher edits an upcoming competition (Priority: P1)

Olena opens the **Actions** menu of "Spring round" ("Actions for “Spring round”") and chooses
**Edit**. The page "Edit competition “Spring round”" shows the subject, the name and 14 March 2027,
10:00 in her zone. She changes the name to "Spring final" and the start to 2 April 2027, 09:30, and
saves. She returns to the same subject and status, on the page that now holds the competition, at
it, with the notice "Competition “Spring final” was saved".

**Why this priority**: Plans change before a competition starts; without editing, a mistake could
only be fixed by cancelling and creating anew.

**Independent Test**: Edit the name and start of an upcoming competition so that it moves to another
page, and check the filled form, the landing page and position, the notice and the stored start.

**Acceptance Scenarios**:

1. **Given** an **Upcoming** competition and a teacher with the setting, **When** its row is shown,
   **Then** it has a button **Actions**, read as "Actions for “Spring round”", whose menu lists
   **Edit** and then **Cancel competition**.
2. **Given** she chooses **Edit**, **When** the form opens, **Then** its title is "Edit competition
   “Spring round”", it is filled with the current name, start date and start time in her time zone,
   and the subject is shown but cannot be changed.
3. **Given** she saves a valid name and a start in the future, **When** the change is stored,
   **Then** she returns to the list with the same subject and status, on the page that now contains
   the competition, at it, with the notice "Competition “…” was saved" naming the saved name.
4. **Given** she saves the competition with its own name, or with only its case changed, **When** the
   form is checked, **Then** the name is accepted.
5. **Given** she presses **Cancel** on the edit form, **When** she returns, **Then** she is on the
   page she came from, at the competition, and nothing changed.

---

### User Story 4 - Names, dates and times are validated (Priority: P1)

Olena types a name of 201 characters, leaves the date empty and types a time that is in the past.
The form comes back with each error beside its field and in the error summary, and with what she
typed. She then tries 28 March 2027, 03:30 in `Europe/Kyiv`, when the clocks go forward, and is told
there is no such time. She tries the name of another live competition of "Chemistry" in lower case
and is told it already exists; the same name is accepted in "Physics".

**Why this priority**: Wrong starts or ambiguous names would send students to the wrong
competition at the wrong time in milestone 13.

**Independent Test**: Submit the create and edit forms with every invalid input listed below and
check the errors, the kept values and that nothing is stored.

**Acceptance Scenarios**:

1. **Given** a name that is empty or only spaces, longer than 200 characters after trimming, or
   containing a control character, **When** the form is saved, **Then** nothing is stored and the
   form is shown again with the subject-name error beside the field and in the summary, and with the
   entered values.
2. **Given** spaces around the name, **When** it is saved, **Then** the stored name is trimmed.
3. **Given** an upcoming or in-progress competition of the same subject has the same name ignoring
   case, **When** the form is saved, **Then** it is refused with "A competition named “…” already
   exists in this subject." naming the entered name.
4. **Given** the only competitions with that name in the subject are finished or cancelled, **When**
   the form is saved, **Then** the name is accepted.
5. **Given** a live competition of another subject has the same name, **When** the form is saved,
   **Then** the name is accepted.
6. **Given** the start date is missing or not a real date, **When** the form is saved, **Then** it
   shows "Enter the start date." or "Enter a real start date.".
7. **Given** the start time is missing or not a real time, **When** the form is saved, **Then** it
   shows "Enter the start time." or "Enter a real start time.".
8. **Given** a start that is now or in the past, **When** the form is saved (creating or editing),
   **Then** it shows "The start must be in the future.".
9. **Given** 28 March 2027, 03:30 entered in `Europe/Kyiv`, **When** the form is saved, **Then** it
   shows "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward. Enter
   another time.".
10. **Given** a local time that happens twice because the clocks go back (for example 31 October
    2027, 03:30 in `Europe/Kyiv`), **When** the form is saved, **Then** the earlier of the two
    moments is stored.
11. **Given** two teachers save competitions with the same name in the same subject at the same
    time, **When** both are processed, **Then** only one is stored and the other gets the duplicate
    error.

---

### User Story 5 - A teacher cancels a competition (Priority: P1)

The "Spring final" competition will not take place. Olena opens its **Actions** menu and chooses
**Cancel competition**. The page asks "Cancel competition “Spring final” of Chemistry, starting 2
April 2027, 09:30?" and explains: "The competition will be marked Cancelled and stays in the list.
It cannot be edited, started or restored." She presses the destructive **Cancel competition**. She
returns to the page she came from, at the competition, which now shows **Cancelled** and has no
menu, with the notice "Competition “Spring final” was cancelled". A new competition named "Spring
final" can now be created in "Chemistry".

**Why this priority**: Competitions that will not happen must be taken out of play visibly and for
good, without losing the record.

**Independent Test**: Cancel an upcoming and an in-progress competition, use **Keep competition**,
cancel under a status filter that then hides the row, and repeat a cancellation; check the texts,
the landing position, the statuses and that cancelled competitions never change again.

**Acceptance Scenarios**:

1. **Given** an **Upcoming** or **In progress** competition and a teacher with the setting, **When**
   they choose **Cancel competition**, **Then** a confirmation page names the competition, its
   subject and its start in the teacher's time zone, says "The competition will be marked Cancelled
   and stays in the list. It cannot be edited, started or restored.", and offers the destructive
   **Cancel competition** and **Keep competition**.
2. **Given** they press **Keep competition**, **When** they return, **Then** they are on the page
   they came from, at the competition, and nothing changed.
3. **Given** they confirm, **When** they return, **Then** they are on the page they came from (same
   subject, status and page), at the competition, with the notice "Competition “…” was cancelled",
   and the row shows **Cancelled** and no menu.
4. **Given** the status filter no longer shows the cancelled competition (for example **Upcoming**),
   **When** they return, **Then** they land at the row that took its place; if none did, at the row
   before it on that page; if the page is now empty, on the previous page at its last row; if no row
   is left, on the empty state.
5. **Given** an upcoming competition whose start passes while the confirmation is open, **When** it
   is confirmed, **Then** it is cancelled.
6. **Given** a competition is cancelled, **When** its start passes, **Then** it stays **Cancelled**.
7. **Given** a cancelled competition, **When** anyone opens its cancel confirmation or sends it again
   (another teacher, or the same form twice, also at the same time), **Then** the refusal "Cancel
   competition “…”?" shows the reason "“…” is already cancelled." and the link **Back to
   competitions**, and nothing changes.
8. **Given** a finished competition, **When** anyone opens or sends its cancel confirmation, **Then**
   the refusal shows the reason "“…” has finished and cannot be cancelled.".
9. **Given** a cancelled competition, **When** a new competition of the same subject is created with
   its name, **Then** the name is accepted, and the cancelled one keeps its name.
10. **Given** the **Cancelled** status filter, **When** it is chosen, **Then** cancelled
    competitions are listed with no menus.

---

### User Story 6 - A competition starts on its own (Priority: P1)

At 10:00 Kyiv time on 14 March 2027, nobody does anything, yet "Spring round" now shows **In
progress**. Its menu offers only **Cancel competition**. Olena had its edit form open since 09:58;
when she saves at 10:01, she sees the refusal "Edit competition “Spring round”?" with the reason
"“Spring round” has already started and can no longer be edited." and **Back to competitions**.

**Why this priority**: The status rules decide what may be changed; a competition that silently
stays editable after its start would break milestone 13.

**Independent Test**: With the current time controlled by the test, let a start pass and check the
badge, the filter, the menu, the edit page and the edit action.

**Acceptance Scenarios**:

1. **Given** an upcoming competition whose start passes, **When** it is next shown or checked,
   **Then** it is **In progress**, with nobody acting and no background job, and the **In progress**
   filter lists it.
2. **Given** an **In progress** competition, **When** its menu is opened by a teacher with the
   setting, **Then** it lists only **Cancel competition**.
3. **Given** a competition that is no longer **Upcoming**, **When** its edit page is opened or its
   edit form is saved, **Then** the refusal "Edit competition “…”?" is shown with the reason for its
   status: "“…” has already started and can no longer be edited.", "“…” has been cancelled and can
   no longer be edited." or "“…” has finished and can no longer be edited.", with the link **Back to
   competitions** to the page the teacher came from, and nothing changes.
4. **Given** a **Finished** or **Cancelled** competition, **When** its row is shown, **Then** it has
   no actions menu, for every teacher.

---

### User Story 7 - Only teachers see competitions, and only managers change them (Priority: P1)

Mykola, without the setting, types the address of the create form, then of an edit form, and sends
a hand-made cancel request: each gets "access denied", before any subject or competition is read. An
administrator and a student who type `/teacher/competitions` get "access denied". Olena changes the
competition id in an edit address to one of another subject and gets "not found".

**Why this priority**: Competitions decide who answers what and when; a missing check would let
anyone change them.

**Independent Test**: For every page and action of the tab, send requests as each role and as
teachers with and without the setting, including typed-in addresses and crafted form submissions
for unknown, mismatched and hidden subjects and competitions, and check the result and the check
order.

**Acceptance Scenarios**:

1. **Given** a person in the administrator or student role, **When** they open any page or send any
   action of the tab, also through a typed address or a crafted form, **Then** they get "access
   denied", naming their current role.
2. **Given** a teacher without the setting, **When** they open the create, edit or cancel page or
   send any of those actions, **Then** they get "access denied" before any subject or competition id
   is read, even for unknown ids.
3. **Given** any teacher, **When** the address names an unknown subject, or a deactivated subject
   with no finished competition, **Then** the page shows "not found".
4. **Given** a teacher, **When** the address or form names an unknown competition, one of another
   subject than the one in the address, or one hidden because its subject is deactivated, **Then**
   they get "not found" and nothing changes.
5. **Given** checks fail at several levels, **When** a request is handled, **Then** the first failing
   check in the order role, setting, subject, competition, status decides the answer.
6. **Given** a teacher with the setting, **When** they act on a competition another teacher created,
   **Then** they can edit it while upcoming and cancel it while not finished, like their own.
7. **Given** any change, **When** it is sent without a valid cross-site request token, **Then** it is
   refused and nothing changes.

---

### User Story 8 - Times follow the teacher's time zone (Priority: P1)

Olena flies to Lisbon. Her browser now reports `Europe/Lisbon`; on the next page every start is
shown in Lisbon time, and the form says "Time zone: Europe/Lisbon". Her colleague's browser blocks
scripts; he sees "14 March 2027, 08:00 UTC" and "Time zone: UTC", and the times he enters are read
in UTC.

**Why this priority**: Teachers and students in different zones must agree on when a competition
starts; one wrong conversion moves a competition by hours.

**Independent Test**: Set the zone cookie to several valid and invalid values and none, and check
every place a start is shown and how a submitted start is read, including a cookie change between
opening and saving a form.

**Acceptance Scenarios**:

1. **Given** the browser runs the application's script, **When** a page loads, **Then** the browser's
   IANA time-zone name is stored in a cookie kept in that browser only, and updated when the zone
   changes.
2. **Given** a known zone, **When** any start is shown on the tab (list, forms, confirmation,
   refusals, notices), **Then** it reads like "14 March 2027, 10:00": the day without a leading
   zero, the month in full, a 24-hour clock, in that zone, inside a time element carrying the UTC
   moment.
3. **Given** no zone is known (no cookie, or a name the time-zone database does not know), **When**
   a start is shown, **Then** it is shown in UTC as "14 March 2027, 10:00 UTC", and the form hint
   reads "Time zone: UTC".
4. **Given** a form shown in `Europe/Kyiv`, **When** the cookie changes to another zone before it is
   saved, **Then** the entered date and time are still read in `Europe/Kyiv`, the zone the form was
   shown in.
5. **Given** a start entered in any zone, **When** it is stored, **Then** it is stored in UTC and
   compared with the current time in UTC.

---

### User Story 9 - Deactivated subjects keep only their finished competitions (Priority: P2)

An administrator deactivates "Chemistry". Its upcoming, in-progress and cancelled competitions
disappear from the tab, and their addresses show "not found". "Chemistry" has one finished
competition, so it is still offered, in a group "Deactivated subjects" below the active subjects,
and its list shows that competition read-only, with the status filter and page navigation, no **Add
competition** and no menus. An upcoming competition of "Chemistry" still turns **In progress** at its
start meanwhile. When "Chemistry" is activated again, everything shows as before.

**Why this priority**: It extends the milestone 6 and 11 deactivation rules to competitions; finished
competitions only exist once stopping arrives, so the risk now is small, but the rule must hold from
the first competition.

**Independent Test**: With a finished competition stored directly by the test, deactivate its
subject and check the subject list, the listed competitions, "not found" for the others, the absence
of actions, and the subject's delete refusal.

**Acceptance Scenarios**:

1. **Given** a subject is deactivated, **When** its competitions that are not finished are opened or
   acted on, **Then** they are not listed and every page and action for them shows "not found".
2. **Given** a deactivated subject with a finished competition, **When** the subject list is opened,
   **Then** it is offered below the active subjects in a group labelled "Deactivated subjects",
   sorted by name ignoring case.
3. **Given** a deactivated subject with no finished competition, **When** the subject list is opened,
   **Then** it is not offered, and its address shows "not found".
4. **Given** a deactivated subject is chosen, **When** its list is shown, **Then** it shows only its
   finished competitions, with the status filter and page navigation, with no **Add competition** and
   no menus.
5. **Given** an upcoming competition of a deactivated subject, **When** its start passes and the
   subject is activated again, **Then** it is listed as **In progress**.
6. **Given** a subject used by any competition, **When** an administrator tries to delete it,
   **Then** the deletion is refused as "in use", suggesting deactivation (milestone 6).

---

### User Story 10 - New and changed components are in the library first (Priority: P3)

An administrator opens `/admin/components` outside production and finds the actions menu, the date
and time fields with their zone hint, the four competition status badges, the local-time display
with and without a known zone, a confirmation with a custom back label, and a chained-list selector
with an option group. The UI guidelines describe each, and list the competition statuses in their
wording patterns.

**Why this priority**: It follows the project rule that pages use only library components; it adds
no capability of its own.

**Independent Test**: Open the gallery and the guidelines and check each new or changed component;
check that existing confirmations and chained lists render as before.

**Acceptance Scenarios**:

1. **Given** the gallery, **When** it is opened, **Then** every new or changed component is shown in
   every variant.
2. **Given** an existing confirmation that sets no back label, **When** it is shown, **Then** its way
   back still reads **Cancel**.
3. **Given** an existing chained list without option groups, **When** it is shown, **Then** it
   renders exactly as before.
4. **Given** the actions menu on a phone card or with the keyboard only, **When** it is opened,
   **Then** each entry is at least 44 px tall and reachable, and the menu opens without JavaScript.

---

### Edge Cases

- **A teacher loses the setting while a form is open**: saving gets "access denied" and nothing is
  stored.
- **The subject is deactivated while a form or confirmation is open**: saving or confirming gets
  "not found" for a competition that is not finished; nothing changes.
- **Another teacher edits the competition meanwhile**: the last save wins, as long as the
  competition is still upcoming and the name is still free.
- **Another teacher cancels the competition while its edit form is open**: saving shows the
  "has been cancelled" refusal.
- **A start in the current minute**: it is already in the past at saving time and is refused with
  "The start must be in the future.".
- **The form is saved just as the start passes during editing**: the competition is no longer
  upcoming, so the edit refusal is shown; the new values are not stored.
- **A start years ahead or a far-past year typed in the date field**: a real future date is accepted;
  a past one gets "The start must be in the future."; a date the calendar does not have (31 April)
  gets "Enter a real start date.".
- **A crafted form with a time-zone name the database does not know**: the entry is read in UTC, the
  same as when no zone is known.
- **A page or address naming a competition with a subject that differs from the address subject**:
  "not found".
- **A page number beyond the last page, or not a number**: the list opens on the nearest valid page,
  as on **Questions**.
- **A status in the address that is not one of the five**: the filter falls back to **All**.
- **A subject offered only through its finished competitions is activated again**: it moves to the
  active subjects and its hidden competitions are listed again.
- **The only offered subject is a deactivated one with a finished competition**: it is chosen
  automatically, like a single active subject.
- **Very long competition names**: wrap within the content width on every screen size, with no
  sideways page scroll, in the table, the cards, the menu label, the confirmation and the notices.
- **Saving the same form twice (double press)**: the form cannot be sent again until the next page
  arrives (milestone 10.1); reloading the result page does not repeat the change; a second create
  arriving anyway gets the duplicate-name error.
- **Script blocked or not yet run on the first page after sign-in**: times on that page are shown
  in UTC labelled "UTC"; the next page uses the reported zone.

## Requirements *(mandatory)*

### Functional Requirements

#### Competitions

- **FR-001**: A **competition** MUST belong to exactly one subject, which MUST never change. In this
  milestone it MUST have a name and a start and nothing else that a teacher sets. Who created it MUST
  NOT be stored or shown.
- **FR-002**: Competition names MUST follow the subject-name rules and messages (milestone 6):
  trimmed, 1–200 characters after trimming, no control characters.
- **FR-003**: A name MUST be unique ignoring case within its subject among the competitions that are
  **Upcoming** or **In progress**, under concurrency too. A duplicate MUST be refused with "A
  competition named “…” already exists in this subject.". The same name MAY be used in different
  subjects at the same time. A **Finished** or **Cancelled** competition MUST keep its name while
  that name is free to use again. Saving a competition with its own name, or with only its case
  changed, MUST be valid.
- **FR-004**: The start MUST be a date and a time to the minute and MUST be later than the moment the
  form is saved, both when creating and when editing. A competition MUST have no duration.

#### Statuses

- **FR-005**: A competition MUST be **Upcoming**, **In progress**, **Finished** or **Cancelled**
  (product requirements, "Competition statuses"), and each status MUST be shown as a badge.
- **FR-006**: The status MUST be worked out by the server from the stored start and the stored stop
  or cancellation whenever it is shown or checked: **Upcoming** before the start, **In progress**
  from the start, with nobody acting and no background job.
- **FR-007**: **Cancelled** MUST be final: a cancelled competition MUST never change again, MUST NOT
  be restored, and MUST stay **Cancelled** when its start passes.
- **FR-008**: **Finished** MUST be a stored state reached only by stopping (a later 12.x milestone);
  no page of this milestone reaches it, but the list, the status filter, the refusals and the
  deactivated-subject rules MUST handle it.

#### Choosing a subject

- **FR-009**: The tab MUST choose a subject with a drop-down list, as on **Questions** (milestone
  11): choosing opens its competitions at once with no button to press (and a **Show** button
  without JavaScript), and the subject MUST be kept in the page address.
- **FR-010**: The list MUST offer the active subjects sorted by name ignoring case, and below them,
  in a group labelled "Deactivated subjects", every deactivated subject that has a **Finished**
  competition, sorted the same way. When the list offers only one subject, it MUST be chosen
  automatically.
- **FR-011**: Until a subject is chosen the page MUST show "Select a subject" with the hint "Choose a
  subject in the list above to see its competitions."; when no subject is offered at all, it MUST
  show "No subjects yet" with the hint "Ask an administrator to add a subject.".
- **FR-012**: An unknown subject in the address, or a deactivated subject with no finished
  competition, MUST show "not found". Every page and action of the tab MUST work in the chosen
  subject.

#### List

- **FR-013**: The competitions of the chosen subject MUST be shown in a data table (labelled cards on
  a phone) with the name, the start and the status badge, and no column naming who created them.
- **FR-014**: The list MUST be ordered by start, latest first, whatever the status, then by name
  ignoring case for equal starts.
- **FR-015**: A **Status** drop-down list above the table MUST offer **All** (the default),
  **Upcoming**, **In progress**, **Finished** and **Cancelled**; choosing an item MUST apply it at
  once, with no button to press (and a **Show** button without JavaScript).
- **FR-016**: The list MUST show 10 competitions per page, with the page navigation of **Questions**
  above and below ("Competitions 11–20 of 35").
- **FR-017**: The subject, the status and the page MUST be kept in the page address. Choosing another
  subject or status MUST open the first page.
- **FR-018**: A subject with no listed competition MUST show "No competitions yet", with the hint
  "Add the first competition with Add competition." for a teacher with **Can manage competitions**
  and no hint for any other teacher. A status that matches nothing MUST show "No competitions with
  this status" with the hint "Choose another status, or All.".

#### Time zones

- **FR-019**: Every start MUST be stored in UTC. The server MUST do every conversion and format every
  time; the browser MUST only report its time zone.
- **FR-020**: A small script MUST report the browser's IANA time-zone name in a cookie kept in that
  browser only, like the theme (milestone 10), set on the first page after sign-in and updated when
  the browser's zone changes. The server MUST accept only a name its time-zone database knows and
  MUST ignore any other.
- **FR-021**: Every start on the tab (the list, the forms, the confirmation, the refusals and the
  notices) MUST be shown in the reported zone as "14 March 2027, 10:00" (day without a leading zero,
  month in full, 24-hour clock), inside a time element that carries the UTC moment. When no zone is
  known, it MUST be shown in UTC as "14 March 2027, 10:00 UTC".
- **FR-022**: The form MUST show the zone the start is entered in, with the hint "Time zone: <zone>"
  (or "Time zone: UTC") under the time field, and MUST carry that zone with the form. The server MUST
  read the entered date and time in the zone the form was shown in, even if the cookie changed
  meanwhile, convert the result to UTC and compare it with the current time in UTC.
- **FR-023**: A local time that does not exist because the clocks go forward MUST be refused with
  "There is no <time> on <date> in <zone> because the clocks go forward. Enter another time.". A
  local time that happens twice because the clocks go back MUST be taken as the earlier one.

#### Creating

- **FR-024**: With **Can manage competitions**, a chosen active subject MUST show **Add competition**
  beside the page heading. It MUST open the form page "Add competition" with a back link, the
  subject shown as text and the fields **Name**, **Start date** and **Start time** (the browser's
  own date and time fields), with the time-zone hint.
- **FR-025**: **Save competition** MUST create the competition in the chosen subject and open its
  list with the status **All**, on the page that contains the new competition and at it, with the
  notice "Competition “…” was added". **Cancel** MUST return to the page the teacher came from, at the
  same place.
- **FR-026**: An invalid name, a missing or invalid date or time, a start that is not in the future,
  or a local time that does not exist MUST show the form again with each error beside its field and
  in the error summary, and with the entered values. The date and time messages MUST be "Enter the
  start date.", "Enter a real start date.", "Enter the start time.", "Enter a real start time." and
  "The start must be in the future.".

#### Row actions

- **FR-027**: Each row MUST have an actions menu when at least one action is available: a button
  **Actions**, read as "Actions for “…”", that opens a short list of the actions for that
  competition. A row with no available action MUST show no menu button.
- **FR-028**: In this milestone the menu MUST offer, only to a teacher with **Can manage
  competitions**, **Edit** on **Upcoming** competitions and **Cancel competition** on **Upcoming** and
  **In progress** competitions, listed after **Edit**. Nobody MUST see a menu on a **Finished** or
  **Cancelled** competition.
- **FR-029**: The menu MUST be built so that later 12.x milestones can add actions without changing
  its look or behaviour.

#### Editing

- **FR-030**: **Edit** MUST open the form page "Edit competition “…”", filled with the current name,
  start date and start time in the teacher's zone; the subject MUST be shown and MUST NOT be
  changeable.
- **FR-031**: **Save competition** MUST keep the rules of creating, and MUST return to the list with
  the same subject and status, on the page that now contains the competition, at it, with the notice
  "Competition “…” was saved". **Cancel** MUST return to the page the teacher came from, at the
  competition, with nothing changed.
- **FR-032**: A competition that is not **Upcoming** MUST NOT be edited. Opening its edit page or
  saving it MUST show the refusal "Edit competition “…”?" with the reason "“…” has already started and
  can no longer be edited." (in progress), "“…” has been cancelled and can no longer be edited." or
  "“…” has finished and can no longer be edited.", and the link **Back to competitions** to the page
  the teacher came from.

#### Cancelling

- **FR-033**: **Cancel competition** MUST open a confirmation page that names the competition, its
  subject and its start in the teacher's zone, for example "Cancel competition “Spring round” of
  Chemistry, starting 14 March 2027, 10:00?", and says "The competition will be marked Cancelled and
  stays in the list. It cannot be edited, started or restored.". The destructive **Cancel
  competition** button MUST confirm it; **Keep competition** MUST return to the page the teacher came
  from, at the competition, with nothing changed.
- **FR-034**: After cancelling, the teacher MUST return to the page they came from (same subject,
  status and page) with the notice "Competition “…” was cancelled", at the competition. When the
  status filter no longer shows it, they MUST land at the row that took its place, as after deleting
  a question (milestone 11): at the row before it on that page if no row took its place, on the
  previous page at its last row if the page is now empty, and on the empty state if no row is left.
- **FR-035**: An upcoming competition whose start passes while the confirmation is open MUST still be
  cancelled.
- **FR-036**: For a competition that is already **Cancelled**, opening the confirmation or sending it
  MUST show the refusal "Cancel competition “…”?" with the reason "“…” is already cancelled." and the
  link **Back to competitions**, and MUST change nothing, under concurrency too. For a **Finished**
  competition the reason MUST be "“…” has finished and cannot be cancelled.".

#### Deactivated subjects

- **FR-037**: Deactivating a subject MUST hide every one of its competitions that is not
  **Finished**: until the subject is activated again they MUST NOT be listed, and every page and
  action for them MUST show "not found". An upcoming one MUST still become **In progress** at its
  start meanwhile.
- **FR-038**: The finished competitions of a deactivated subject MUST stay available, read-only: the
  subject MUST be offered under "Deactivated subjects", and its list MUST show them with the status
  filter and page navigation, with no **Add competition** and no menus. Creating a competition in a
  deactivated subject MUST be refused with "not found".
- **FR-039**: A subject used by any competition, in any status, MUST NOT be deletable (milestone 6).

#### Access

- **FR-040**: Every teacher MUST see the competitions of every subject the list offers, whoever
  created them. Creating, editing and cancelling MUST need **Can manage competitions**, and any
  teacher with it MUST be able to edit any upcoming competition and cancel any upcoming or
  in-progress one; there MUST be no rights per competition.
- **FR-041**: Administrators and students MUST get "access denied" on every page and action of the
  tab, also through the page address or a submitted form.
- **FR-042**: Checks MUST run in this order, and the first failing one MUST decide the answer:
  1. the role: anyone who is not a teacher gets "access denied";
  2. the setting, for the create, edit and cancel pages and actions: a teacher without **Can manage
     competitions** gets "access denied", before any id or subject is read;
  3. the subject: an unknown one, or a deactivated one with no finished competition, shows "not
     found";
  4. the competition: an unknown one, one of another subject than the one in the address, or one
     hidden because its subject is deactivated, shows "not found";
  5. the status: the refusals of FR-032 and FR-036.
- **FR-043**: Access MUST be checked on every request against the current role, setting, subject and
  competition, whatever the page showed, and again when the change is stored.

#### Shared page and action behaviour

- **FR-044**: Every change MUST be a form submission that passes the existing cross-site request
  check. Opening a page or following a link MUST never change anything.
- **FR-045**: After a successful change, the teacher MUST be sent to a result page, so reloading does
  not repeat the change.
- **FR-046**: No log line MUST contain an email address, a person's name or a competition name.
- **FR-047**: Every page of the tab MUST follow the UI guidelines, including the loading feedback and
  busy button of milestone 10.1, and MUST work on a phone-width screen without sideways page
  scrolling.

#### Components

- **FR-048**: The pages MUST be built from existing components (the chained-list selector for the
  subject and the status, data tables, page navigation, notices, empty states with a hint, form
  fields with an error summary, confirmations, refusals, back links and the status badge), plus the
  following new or changed ones, each added to the component library, the component gallery
  (`/admin/components`) and the UI guidelines first, and only then used:
  - the **actions menu**: opens without JavaScript, like the user menu, with entries at least 44 px
    tall that stay reachable on a phone card and by keyboard;
  - the **date and time fields** with their time-zone hint;
  - the **competition status badge**, one kind per status;
  - the **local-time display**: the time element with the server-formatted text, and the "UTC" label
    when no zone is known;
  - **confirmations** gain an optional label for their way back, **Cancel** by default, for when
    "Cancel" would read as the destructive verb (here **Keep competition**); existing confirmations
    MUST look the same;
  - the **chained-list selector** gains option groups (here "Deactivated subjects"); existing lists
    MUST look the same.
- **FR-049**: The UI guidelines MUST gain the competition statuses in their wording patterns, and
  their "one word each" rule for statuses MUST become "one short term each" (**In progress**). The
  time-zone script MUST be one new small file loaded by the base layout, with no build step and no
  new dependency; without it every page MUST still work, with times in UTC.

#### Verification and scope

- **FR-050**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" list: creating and editing with the zone `Europe/Kyiv` and with no zone;
  validation (past or present start, a skipped local time, empty and 201-character names, a duplicate
  in any case, the same name in another subject, a repeated local time stored as the earlier one);
  order and landing (start order, name order on equal starts, 10 per page with 25 competitions, the
  landing page after creating and after an edit that moves the competition); the start passing; the
  cancellation of an upcoming and an in-progress competition, **Keep competition**, a cancelled
  competition staying cancelled and freeing its name, and every refusal; the status filter across
  pages; access per role and per setting through addresses and submitted forms; and the
  deactivated-subject rules with a finished competition stored directly by the test, and the subject
  in-use rule.
- **FR-051**: This milestone MUST NOT add a duration, questions or teams in a competition, stopping a
  competition (reaching **Finished**), deleting or restoring a competition, a reason for cancelling,
  rights per competition, the student's view (milestone 13) or results (milestone 15).

### Key Entities *(include if feature involves data)*

- **Competition** (new): belongs to one subject, which never changes; has a name (1–200 characters,
  unique ignoring case within its subject among upcoming and in-progress competitions), a start (a
  moment in UTC, to the minute), and the stored facts that it was cancelled or stopped (stopping
  arrives in a later 12.x milestone). Its status is worked out from these whenever it is shown or
  checked. Its creator is not stored. It is not personal data.
- **Subject** (existing): now also used by competitions; any competition makes it undeletable.
  Deactivating it hides its competitions that are not finished.
- **Time-zone preference** (new, browser only): the browser's IANA time-zone name in a cookie, like
  the theme; never stored on the server.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A teacher with **Can manage competitions** can create a competition and find it in the
  list in under 1 minute.
- **SC-002**: 100% of starts entered in a known zone are stored as the correct UTC moment and shown
  back in that zone exactly as entered, including both sides of a clock change; 0 local times that do
  not exist are stored.
- **SC-003**: In the automated access check, 100% of pages and actions of the tab refuse the
  administrator and student roles, 100% of create, edit and cancel pages and actions refuse teachers
  without the setting, and 100% of requests naming an unknown, mismatched or hidden subject or
  competition get "not found" with nothing changed.
- **SC-004**: 0 pairs of upcoming or in-progress competitions of the same subject share a name
  ignoring case, including under concurrent saves.
- **SC-005**: 0 competitions are edited after leaving **Upcoming**, and 0 cancelled or finished
  competitions change in any way, including through repeated or concurrent requests.
- **SC-006**: 100% of competitions show **In progress** from the first request after their start,
  with no one acting.
- **SC-007**: After 100% of the creates, edits, cancellations, cancels and refusals covered by the
  tests, the teacher lands on the subject, status, page and row this specification names.
- **SC-008**: The tab and its pages are usable at 360 px width with no sideways page scrolling, and
  every actions menu entry is at least 44 px tall and reachable by keyboard.
- **SC-009**: Reloading the page after any successful change never repeats it.
- **SC-010**: All tests from milestones 1–11.1 still pass, apart from tests of the **Competitions**
  placeholder, which this milestone replaces.

## Assumptions

- **Finished competitions** cannot be reached through any page in this milestone; tests store them
  directly to check the list, the filter, the refusals and the deactivated-subject rules.
- **Tests control the current time**, so that a start can pass during a test without waiting.
- **"In the future"** means strictly later than the moment of saving; since starts are to the minute,
  a start in the current minute is refused.
- **An unknown time-zone name sent with a form** (only possible through a crafted request) is treated
  like an unknown zone: the entry is read in UTC.
- **Creating in a deactivated subject** that is still offered because of a finished competition is
  refused with "not found", the same answer as for a hidden competition; the page never offers it.
- **Edit and cancel on a finished competition of a deactivated subject** reach the status check and
  show the "has finished" refusals, because the competition itself is visible.
- **Concurrent edits** follow last-write-wins while the competition stays upcoming and the name stays
  free; the database keeps the live-name uniqueness and the final cancelled state, and the loser of a
  race gets the normal error or refusal.
- **Page numbers and statuses in the address** that are out of range or unknown fall back to the
  nearest valid page and to **All**, as on **Questions**.
- **The status filter in a deactivated subject** offers the same five items; every item except
  **All** and **Finished** shows "No competitions with this status".
- **The notice names the competition** with its saved name; the date and time are not part of the
  notices.
- **The tab row is unchanged**: the **Competitions** tab already exists (milestone 9) and was measured
  with four tabs in milestone 11.1, and the home page's teacher card already names competitions.
- **The refusal page** uses the existing refusal pattern (a title as a question, a reason, and a link
  back), as for questions and teams that can no longer be changed.

## Dependencies

- **Milestone 5**: roles, the current role, "access denied" and the automated route check.
- **Milestone 6**: subjects, their name rules reused for competition names, deactivation and the
  "in use" rule for deleting a subject.
- **Milestone 8**: the **Can create competitions** setting (renamed **Can manage competitions** in
  milestone 11) and the logging rule.
- **Milestone 9**: the teacher area and its **Competitions** placeholder tab.
- **Milestone 10**: the component library, the gallery, the UI guidelines, the theme cookie pattern
  and the existing components.
- **Milestone 10.1**: the loading bar, the busy button and the pinned frame.
- **Milestone 11**: the subject chooser of **Questions**, page navigation, the landing rules after
  a deletion and the **Show** button of chained lists without JavaScript.
- **Milestone 11.1**: the four-tab row and the confirmation pattern used for deleting teams.
- **Runtime**: the server needs the IANA time-zone database; the plan confirms that the deployed
  runtime carries it.
- **Later milestones that depend on this one**: the next 12.x milestones add questions, teams and
  stopping (reaching **Finished**) as further actions in the menu; milestone 13 opens a competition
  to students only while **In progress** and never while cancelled or hidden; milestone 15 shows the
  results of finished competitions, also in deactivated subjects.

## Out of Scope

- A duration: a competition runs until it is stopped.
- Questions and teams in a competition, and stopping a competition: later 12.x milestones.
- Deleting or restoring a competition, and a reason for cancelling.
- Rights per competition, or storing or showing who created a competition.
- The student's view of competitions (milestone 13) and results (milestone 15).
