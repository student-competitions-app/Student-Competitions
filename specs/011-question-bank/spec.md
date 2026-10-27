# Feature Specification: Question Bank (Teacher) (Milestone 11)

**Feature Branch**: `011-question-bank`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: milestone 11 of `docs/requirements/milestones.md` ("Question bank
(teacher)"), with `product-requirements.md`, the milestone 3, 6, 8, 9, 10 and 10.1 specifications
and `docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 11 of the walking skeleton for the Student Competitions application. After milestone 10.1,
teachers manage classes and students, administrators keep the list of subjects, and the only
questions in the application are the sample questions from milestone 3, which have no subject and
can be changed only inside the application, not through the website.

This milestone gives teachers the **question bank** that competitions will be built from
(milestone 12). Six things become true when this milestone is done:

1. **Every question belongs to one subject** and has two parts: the question text and its reference
   answer. During a competition, participants' answers will be assessed against the reference answer
   by an LLM (milestone 14).
2. **Teachers see the question bank.** The teacher area gets a **Questions** tab. A teacher picks a
   subject and reads its questions, newest first, ten per page, each in full with its number and its
   reference answer.
3. **Only teachers allowed to manage competitions change it.** The milestone 8 setting **Can create
   competitions** becomes **Can manage competitions** and now also covers the question bank. A
   teacher with the setting adds, edits and deletes any question, whoever added it; every other
   teacher sees the bank read-only. Administrators and students have no access to it.
4. **Deleting a question only hides it.** A deleted question stays stored unchanged, so completed
   competitions can keep showing it (milestone 15), but it is never listed, edited or added to a new
   competition again.
5. **A subject that has ever had a question cannot be deleted**, only deactivated, for the same
   reason.
6. **The sample questions are gone.** The home page no longer lists questions; it keeps its database
   line and its message when the database is briefly unreachable.

Two new interface patterns are needed: **page navigation** for long lists, and a **form with two save
buttons**. Following the project rules, each is first added to the component library, the component
gallery (`/admin/components`) and the UI guidelines, and only then used on the **Questions** tab.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher adds questions to a subject (Priority: P1)

Olena is a teacher with **Can manage competitions**. The administrator keeps three active subjects:
"Mathematics", "Physics" and "Chemistry". Olena opens the **Questions** tab of the teacher area,
chooses "Physics" in the subject list and presses **Add question**. She types a question text and a
reference answer and presses **Save and add one more question**, because she has a few more to enter.
The form opens again, empty, for "Physics", with a notice that the question was saved. She enters a
second question and presses **Save question**. The list of "Physics" questions opens at the top of
its first page, with her second question shown first and her first question below it.

**Why this priority**: Without a way to add questions there is no question bank, and milestone 12
cannot build competitions.

**Independent Test**: Sign in as a teacher with the setting, select a subject, add two questions with
the two save buttons, and check where each save leads and what the list shows.

**Acceptance Scenarios**:

1. **Given** Olena has the setting and "Physics" is selected, **When** she presses **Add question**,
   **Then** a form opens for a new question in "Physics", with the subject shown and two empty
   fields: the question text and the reference answer.
2. **Given** the form is filled in validly, **When** she presses **Save question**, **Then** the
   question is stored in "Physics", and the list opens at the top of its first page with "Physics"
   still selected and the new question shown first.
3. **Given** the form is filled in validly, **When** she presses **Save and add one more question**,
   **Then** the question is stored, and an empty form for "Physics" opens with a notice that the
   question was saved.
4. **Given** she leaves the question text or the reference answer empty, or only spaces, **When** she
   saves with either button, **Then** nothing is stored and the form is shown again with the error
   beside the field, in the error summary, and with the values she entered.
5. **Given** she enters a question text or a reference answer longer than 2,000 characters after
   trimming, **When** she saves, **Then** nothing is stored and the form is shown again with a field
   error and the values she entered.
6. **Given** a question with exactly the same text already exists, **When** she saves a new question
   with that text, **Then** it is accepted and both questions are listed.
7. **Given** she typed spaces or line breaks around the text, **When** she saves, **Then** the stored
   text and reference answer are trimmed.
8. **Given** she opened **Add question** from page 3 of the list, **When** she presses **Cancel**,
   **Then** she returns to page 3 of the same subject and nothing is stored.

---

### User Story 2 - A teacher reads the question bank of a subject (Priority: P1)

Taras is a teacher without **Can manage competitions**. He opens the **Questions** tab, chooses
"Mathematics" and reads its questions: newest first, ten per page, each shown in full as one large box
holding the question text and, below it, the reference answer, together with the question's number.
He moves between pages with the page navigation above and below the list, which tells him, for
example, "Questions 31–40 of 200". He bookmarks page 4 and later opens it again at the same subject
and page. He sees no **Add question**, **Edit** or **Delete**.

**Why this priority**: Reading the bank is the base for every other action, and every teacher, with
or without the setting, needs it to know which questions exist.

**Independent Test**: With a subject holding 25 questions, open the tab as a teacher without the
setting, select the subject, walk through the pages and check the order, the content and the page
navigation, then reload and bookmark addresses with different `subject` and `page` values.

**Acceptance Scenarios**:

1. **Given** a teacher opens the teacher area, **When** the tab row is shown, **Then** it holds three
   tabs in the order **Students**, **Questions**, **Competitions**, and **Questions** opens
   `/teacher/questions`.
2. **Given** several active and some deactivated subjects, **When** the teacher opens the subject
   list, **Then** it offers only the active subjects.
3. **Given** exactly one active subject, **When** the teacher opens the **Questions** tab without a
   subject in the address, **Then** that subject is selected automatically and its list is shown.
4. **Given** two or more active subjects and no subject in the address, **When** the teacher opens the
   tab, **Then** the page shows "Select a subject" with a hint.
5. **Given** no active subject at all, **When** the teacher opens the tab, **Then** the page shows
   "No subjects yet" with a hint to ask an administrator.
6. **Given** the address names an unknown subject or a deactivated subject, **When** the teacher opens
   it, **Then** the page behaves as with no subject selected (including the automatic selection of a
   single active subject).
7. **Given** a selected subject without questions, or with only deleted questions, **When** the list
   is shown, **Then** it shows "No questions yet".
8. **Given** "Mathematics" holds 25 questions and "Physics" holds 3, **When** "Mathematics" is
   selected, **Then** only its 25 questions are listed, newest first, 10 on the first page, 10 on the
   second and 5 on the third.
9. **Given** a question is listed, **When** the teacher looks at it, **Then** it shows its number, its
   full question text and, below it, its full reference answer, in two boxes inside one larger box.
10. **Given** a subject with 200 questions and page 4 open, **When** the teacher looks at the page
    navigation above or below the list, **Then** it says "Questions 31–40 of 200" and offers
    **Previous**, **Next** and the page numbers, with gaps when there are many pages.
11. **Given** the address has no page number, a page number that is not a whole number, or a number
    below 1, **When** it is opened, **Then** the first page is shown; **Given** a page number past the
    last page, **Then** the last page is shown.
12. **Given** the teacher is on page 3 of "Mathematics", **When** they choose "Physics" in the subject
    list, **Then** the first page of "Physics" opens.
13. **Given** the selected subject and page are in the address, **When** the teacher reloads or opens
    a bookmark of it, **Then** the same subject and page are shown.
14. **Given** JavaScript is turned off in the browser, **When** the teacher chooses a subject and
    moves between pages, **Then** everything works as with JavaScript.
15. **Given** a teacher without the setting, **When** they view any page of the tab, **Then** no
    **Add question**, **Edit** or **Delete** is shown; **Given** a teacher with the setting, **Then**
    **Add question** is shown above the list and **Edit** and **Delete** on each question.

---

### User Story 3 - A teacher edits a question (Priority: P1)

Olena notices a mistake in the reference answer of question 57 on page 2 of "Physics", which another
teacher added. She presses **Edit** on it. The form opens filled in with the question text and the
reference answer; the subject is shown but cannot be changed. She corrects the answer and saves. She
returns to page 2 of "Physics", at question 57, which now shows the corrected answer and keeps its
number.

**Why this priority**: Reference answers decide scores in milestone 14; a mistake must be correctable
by any teacher allowed to manage competitions, not only by the one who added the question.

**Independent Test**: As a teacher with the setting, edit a question added by another teacher from a
page other than the first, and check the stored values, the number and where saving and **Cancel**
lead.

**Acceptance Scenarios**:

1. **Given** Olena has the setting, **When** she presses **Edit** on any question, whoever added it,
   **Then** the form opens with the current question text and reference answer, and the subject
   shown but not editable.
2. **Given** she changes the fields validly, **When** she saves, **Then** the question is updated,
   keeps its number and its subject, and she returns to the page she came from, at that question.
3. **Given** she opened the form from page 2, **When** she presses **Cancel**, **Then** nothing
   changes and she returns to page 2, at that question.
4. **Given** she empties a field or makes it longer than 2,000 characters, **When** she saves,
   **Then** nothing changes and the form is shown again with the field error and her entered values.
5. **Given** a crafted request sends a different subject with the edit, **When** it is saved, **Then**
   the sent subject is ignored and the question stays in its own subject.

---

### User Story 4 - A teacher deletes a question (Priority: P2)

Olena decides that question 12 of "Chemistry" should no longer be used. She presses **Delete** on it.
A confirmation page asks "Delete question 12?" and explains: "The question will be hidden from this
list and can no longer be added to new competitions. It is not erased, but it cannot be restored." She
presses the destructive **Delete**. She returns to the same page, at the question that took question
12's place. Question 12 is no longer listed anywhere in the bank, but it is still stored, unchanged.

**Why this priority**: Teachers need to retire questions, but the bank works without deletion, and
the soft-delete rule matters mostly once competitions exist.

**Independent Test**: Delete questions in each position (middle of a page, last of the whole list,
only question on the last page) and check the confirmation text, where the teacher lands, that the
question is not listed, and that it is still stored unchanged.

**Acceptance Scenarios**:

1. **Given** Olena has the setting, **When** she presses **Delete** on question 12, **Then** a
   confirmation page asks "Delete question 12?" and says "The question will be hidden from this list
   and can no longer be added to new competitions. It is not erased, but it cannot be restored."
2. **Given** the confirmation page, **When** she presses **Cancel**, **Then** nothing changes and she
   returns to the page she came from, at question 12.
3. **Given** she confirms, **When** the deletion is done, **Then** the question stays stored with its
   text, reference answer, subject and number unchanged, and it is never listed again.
4. **Given** the deleted question was followed by another question in the list (on the same page or
   moved up from the next page), **When** she returns, **Then** she is on the same page at the
   question that now holds the deleted one's position.
5. **Given** the deleted question was the last question of the whole list and its page still holds
   other questions, **When** she returns, **Then** she is on the same page at the question before it.
6. **Given** the deleted question was the only question on the last page, **When** she returns,
   **Then** she is on the previous page, at its last question.
7. **Given** the deleted question was the only question of the subject, **When** she returns, **Then**
   the subject's list shows "No questions yet".
8. **Given** a question was deleted, **When** anyone opens its edit or delete address, **Then** they
   get "not found".

---

### User Story 5 - Only the right people reach the question bank (Priority: P1)

The server checks every request, whatever the page showed. Taras, without **Can manage
competitions**, types the address of the add form and sends a hand-made deletion request: both get
"access denied". Olena, with the setting, opens an old bookmark of a question whose subject the
administrator has since deactivated: she gets "not found". An administrator and a student who type
`/teacher/questions` get "access denied".

**Why this priority**: The bank holds the reference answers that decide scores. A missing check would
let a teacher who is not trusted with competitions change them, or leak them to students.

**Independent Test**: For every page and action of the tab, send requests as each role and as a
teacher with and without the setting, including typed-in addresses and crafted form submissions for
unknown, deleted and deactivated-subject questions.

**Acceptance Scenarios**:

1. **Given** a person in the administrator or student role, **When** they open any page or send any
   action of the question bank, **Then** they get "access denied", naming their current role.
2. **Given** a teacher without the setting, **When** they open the add, edit or delete page, or send
   an add, edit or delete request, **Then** they get "access denied" and nothing changes.
3. **Given** a teacher with the setting, **When** they add to an unknown or deactivated subject,
   **Then** they get "not found" and nothing is stored.
4. **Given** a teacher with the setting, **When** they open, edit or delete an unknown question, a
   deleted question or a question of a deactivated subject, **Then** they get "not found" and nothing
   changes.
5. **Given** a teacher opened the edit form, **When** the question is deleted or its subject
   deactivated by someone else before they save, **Then** saving gets "not found" and nothing changes.
6. **Given** a teacher opened the edit form, **When** an administrator removes their **Can manage
   competitions** before they save, **Then** saving gets "access denied" and nothing changes.

---

### User Story 6 - The setting becomes "Can manage competitions" (Priority: P2)

An administrator opens the **Teachers** tab. The column that said **Can create competitions** now says
**Can manage competitions**, and so do the checkbox on the invitation and edit forms, the teacher's
details on the invitation acceptance page, and the teacher's profile. Every teacher keeps the value
they had.

**Why this priority**: The setting now governs the question bank too; its name must say so, but the
rename itself carries no new behaviour beyond User Story 5.

**Independent Test**: Before and after the upgrade, compare every teacher's value; then check every
place where the setting is shown or set for the new name.

**Acceptance Scenarios**:

1. **Given** teachers with and without the setting before this milestone, **When** the milestone is
   deployed, **Then** each keeps their value.
2. **Given** the **Teachers** tab, the teacher invitation form, the teacher edit form, the invitation
   acceptance page and the profile, **When** they are shown, **Then** the setting is called **Can
   manage competitions** in each, and the explanation on the acceptance page says it covers managing
   competitions and the question bank.
3. **Given** a teacher invitation issued before the deployment and still valid, **When** it is
   accepted, **Then** the setting value it carries is stored as **Can manage competitions**.

---

### User Story 7 - A subject with questions can only be deactivated (Priority: P3)

The administrator tries to delete "Chemistry". It once had questions, all of them deleted since. The
deletion is refused with the usual suggestion to deactivate the subject instead.

**Why this priority**: It protects the record that milestone 15 will show, but no competition exists
yet, so the risk in this milestone is small.

**Independent Test**: Try to delete a subject with active questions, a subject with only deleted
questions, and a subject that never had a question.

**Acceptance Scenarios**:

1. **Given** a subject with at least one question, deleted or not, **When** an administrator tries to
   delete it, **Then** the deletion is refused, suggesting deactivation, as for any other use.
2. **Given** a subject that never had a question and has no other use, **When** an administrator
   deletes it, **Then** it is deleted as before.
3. **Given** a subject is deactivated, **When** it is activated again, **Then** its questions that were
   not deleted are listed again, unchanged.

---

### User Story 8 - The sample questions are removed (Priority: P3)

After the deployment, the home page no longer lists sample questions. It still shows the database
line in its footer, and the message when the database is briefly unreachable. The teacher area's card
on the home page mentions the question bank.

**Why this priority**: Cleanup that removes a milestone 3 stand-in; it is visible but carries no new
capability.

**Independent Test**: Deploy on a database that holds the sample questions; check they are gone and
inspect the home page for each role, with the database reachable and unreachable.

**Acceptance Scenarios**:

1. **Given** a database with the milestone 3 sample questions, **When** the upgrade runs, **Then** the
   sample questions are deleted.
2. **Given** any role, **When** the home page is shown, **Then** it lists no questions and still shows
   the database line in its footer.
3. **Given** the database is briefly unreachable, **When** the home page is opened, **Then** it still
   opens and shows its existing message.
4. **Given** a teacher opens the home page, **When** the teacher area's card is shown, **Then** it
   mentions the question bank.

---

### Edge Cases

- **A single active subject that is then deactivated**: the tab shows "No subjects yet" if no other
  subject is active; bookmarks naming it are treated as no selection.
- **Two teachers change the bank at the same time**: the teacher returns to the same page number even
  though its questions may have shifted; the anchored question may then be on another page. This is
  accepted.
- **The return page in the address is missing, not a whole number, below 1 or past the end**: it is
  treated like any page number in the list address (first or last page), never as an error.
- **The return target is anything other than a page number** (for example an address): it is ignored;
  the page the teacher came from is never taken from an address in the request.
- **Saving the same form twice** (double press): the form cannot be sent again until the next page
  arrives (milestone 10.1); reloading the page after a save does not save again.
- **A deleted question's number** is never reused or shown for another question.
- **Very long single words or long lines** in a question or reference answer: the boxes wrap them
  inside the content width on every screen size, with no sideways page scroll.
- **Line breaks inside the text**: kept and shown as typed.
- **A subject renamed by the administrator**: the bank shows the new name; its questions are
  unaffected.
- **A teacher without any linked institution**: the question bank is not scoped to institutions, so
  they read it (and change it, with the setting) like any other teacher.
- **The question text equals the reference answer**, or two questions are identical: accepted.
- **Pinned frame and anchors**: returning "at a question" lands it below the pinned top bar and tabs
  (milestone 10.1), on every screen size.

## Requirements *(mandatory)*

### Functional Requirements

#### Questions

- **FR-001**: Every question MUST belong to exactly one subject and MUST hold a question text and a
  reference answer. Its subject MUST never change after creation.
- **FR-002**: The question text and the reference answer MUST each be required, trimmed, and at most
  2,000 characters after trimming. Line breaks inside them MUST be kept. The same text MAY appear in
  more than one question.
- **FR-003**: Every question MUST get a number when it is created. The number MUST never change, MUST
  never be reused, and MUST never pass to another question, including after deletion.
- **FR-004**: Deleting a question MUST only hide it: the question MUST stay stored with its text,
  reference answer, subject and number unchanged, MUST never be listed again, MUST NOT be editable or
  deletable again, and MUST be marked so that milestone 12 can never add it to a new competition.
  There MUST be no way to restore it.

#### Access and the setting

- **FR-005**: The question bank MUST be open only to the teacher role. Administrators and students
  MUST get "access denied" on every page and action of it.
- **FR-006**: Every teacher MUST be able to read the question bank, reference answers included.
- **FR-007**: Only a teacher with **Can manage competitions** MUST be able to open the add, edit and
  delete pages and send add, edit and delete requests; every other teacher MUST get "access denied"
  from each of them. A teacher with the setting MUST be able to edit and delete any question, whoever
  added it.
- **FR-008**: Every page MUST show a teacher only the actions they may take: **Add question**,
  **Edit** and **Delete** MUST appear only for teachers with the setting.
- **FR-009**: The milestone 8 setting **Can create competitions** MUST be renamed **Can manage
  competitions** everywhere it is shown or set (the **Teachers** tab, the teacher invitation and edit
  forms, the invitation acceptance page and the profile). Its meaning MUST cover the question bank as
  well as competitions (milestone 12), and the explanation on the acceptance page MUST say so. Every
  teacher MUST keep their current value, and teacher invitations issued before the change MUST keep
  working with the value they carry.

#### Teacher area: the Questions tab

- **FR-010**: The teacher area MUST gain a third tab, **Questions**, at `/teacher/questions`. The tabs
  MUST be ordered **Students**, **Questions**, **Competitions**. `/teacher` MUST keep opening
  **Students**.
- **FR-011**: With the third tab, the tab row MUST be measured again at 360 px and 375 px screen width
  against the pinned-frame clearances of milestone 10.1, and MUST meet them; the measurement MUST be
  recorded with the feature.

#### Choosing a subject

- **FR-012**: The top of the **Questions** tab MUST hold a subject list that selects the subject the
  list, additions, edits and deletions apply to. It MUST be the existing self-submitting selector
  with one level, MUST offer only active subjects, and MUST work without JavaScript.
- **FR-013**: The selected subject MUST be kept in the page address (`?subject=<id>`), so it survives
  reloads and bookmarks, and MUST stay selected after every addition, edit, deletion and cancel.
- **FR-014**: When exactly one subject is active and no valid subject is in the address, it MUST be
  selected automatically.
- **FR-015**: An unknown or deactivated subject in the address MUST be treated as no selection.
- **FR-016**: With no subject selected, the page MUST show "Select a subject" with a hint. With no
  active subject at all, it MUST show "No subjects yet" with a hint to ask an administrator.
- **FR-017**: Changing the subject MUST open the first page of the new subject's list.

#### The list

- **FR-018**: The list MUST show only the questions of the selected subject that are not deleted,
  newest first, 10 per page.
- **FR-019**: Each question MUST be shown in full as one large box holding two smaller boxes: the
  question text and, below it, its reference answer. Each question MUST show its number.
- **FR-020**: A subject with no listed question MUST show "No questions yet".
- **FR-021**: For a teacher with the setting, **Add question** MUST be shown above the list and
  **Edit** and **Delete** on each question.

#### Page navigation

- **FR-022**: The page number MUST be kept in the address (`?subject=<id>&page=<n>`).
- **FR-023**: Above and below the list, a page navigation MUST show which questions are on the page
  (for example "Questions 31–40 of 200"), **Previous** and **Next**, and the page numbers, with gaps
  when there are many pages. It MUST work without JavaScript.
- **FR-024**: A missing or invalid page number MUST open the first page, and a number past the end
  MUST open the last page.
- **FR-025**: Page navigation is a new pattern: it MUST first be added to the component library, the
  component gallery (`/admin/components`) and the UI guidelines, and only then used on the
  **Questions** tab.

#### Adding a question

- **FR-026**: **Add question** MUST open a form for a new question in the selected subject, showing
  that subject, with the question text and the reference answer fields.
- **FR-027**: The form MUST have two save buttons. **Save question** (primary) MUST save and return to
  the top of the first page with the same subject selected, where the new question is shown first.
  **Save and add one more question** (secondary) MUST save and open an empty form for the same
  subject, with a notice that the question was saved.
- **FR-028**: **Cancel** MUST return to the page the teacher came from, with nothing stored.
- **FR-029**: An invalid form MUST be shown again with each error beside its field and in the error
  summary, and with the entered values.
- **FR-030**: A form with two save buttons is a new pattern: it MUST first be added to the component
  library (the form actions component), the component gallery and the UI guidelines, and only then
  used.

#### Editing a question

- **FR-031**: **Edit** MUST open the same form filled in with the current question text and reference
  answer. The subject MUST be shown and MUST NOT be changeable; a subject sent with an edit MUST be
  ignored.
- **FR-032**: Saving and **Cancel** MUST both return to the page the teacher came from, at the edited
  question. An invalid edit MUST be handled as in FR-029.

#### Deleting a question

- **FR-033**: **Delete** MUST open a confirmation page that names the question by its number, for
  example "Delete question 12?", and says: "The question will be hidden from this list and can no
  longer be added to new competitions. It is not erased, but it cannot be restored." The destructive
  **Delete** MUST confirm it; **Cancel** MUST return to the page the teacher came from, at that
  question.
- **FR-034**: After a deletion, the list MUST return to the same page at the question that now holds
  the deleted one's position; if no question holds it (the deleted question was the last of the whole
  list), at the question before it on that page; and if that page is now empty, to the previous page,
  at its last question. If the subject has no listed question left, the list MUST show "No questions
  yet".

#### Returning to the list

- **FR-035**: The page the teacher came from MUST travel in the address as a page number only, never
  as an address. Returning MUST go to that page number of the same subject, even if other teachers'
  changes have shifted its questions meanwhile. An invalid return page MUST be handled as in FR-024.
- **FR-036**: Returning "at a question" MUST bring that question into view below the pinned frame.

#### Server checks

- **FR-037**: The server MUST check every request, whatever the page showed. Access MUST be checked
  before anything else, so a person without access gets "access denied" whatever the request names.
- **FR-038**: An unknown subject, a deactivated subject, an unknown question, a deleted question and a
  question of a deactivated subject MUST all get "not found", on the add, edit and delete pages and
  on add, edit and delete requests, including typed-in addresses and crafted requests.
- **FR-039**: An empty or too long question text or reference answer MUST be a field error, never a
  page-level error.

#### Subject in use

- **FR-040**: Every question, deleted questions included, MUST count as a use of its subject. A
  subject that has ever had a question MUST NOT be deletable (milestone 6), only deactivatable; the
  refusal MUST suggest deactivation as for any other use.
- **FR-041**: Activating a subject again MUST list its questions that were not deleted, unchanged.

#### Sample questions and the home page

- **FR-042**: The upgrade MUST delete the milestone 3 sample questions.
- **FR-043**: The home page MUST no longer list questions. It MUST keep the database line in its
  footer and its message when the database is briefly unreachable.
- **FR-044**: The teacher area's card on the home page MUST mention the question bank.

#### Shared page and action behaviour

- **FR-045**: Every add, edit and delete MUST be a form submission that passes the existing
  cross-site request check. Opening a page or following a link MUST never change anything.
- **FR-046**: After a successful add, edit or delete, the teacher MUST be sent to a result page, so
  reloading does not repeat the action.
- **FR-047**: Every page of the tab MUST be built from the component library and follow the UI
  guidelines, including the loading feedback and busy button of milestone 10.1, and MUST work on a
  phone-width screen without sideways page scrolling.

#### Verification and scope

- **FR-048**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" line, including allowed and denied access per role and per setting value,
  every "not found" case, field validation with entered values kept, the order and paging of the
  list, every return position after add, edit, cancel and delete, the soft deletion staying stored
  unchanged, the subject-in-use rule for deleted questions, the removal of the sample questions and
  the renamed setting.
- **FR-049**: This milestone MUST NOT add competitions or the content of the **Competitions** tab
  (milestone 12), search or filtering of questions beyond the subject, moving a question to another
  subject, restoring a deleted question, bulk import or export of questions, a history of changes,
  showing who added or last changed a question, or any access to the question bank for
  administrators or students.

### Key Entities *(include if feature involves data)*

- **Question** (existing, changed): now belongs to one subject and has a number, a question text and a
  reference answer (each up to 2,000 characters), and a deleted mark. The subject and the number
  never change. A deleted question stays stored unchanged. Not personal data.
- **Subject** (existing): its in-use check now counts every question, deleted ones included.
  Deactivating it hides its questions from the bank; activating it shows them again.
- **Teacher details** (existing): the **Can create competitions** setting is renamed **Can manage
  competitions**, keeping every value.
- **Teacher invitation** (not stored, existing): carries the renamed setting; invitations issued
  before the change keep their value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A teacher with the setting can select a subject and add five questions in a row, using
  **Save and add one more question**, in under 3 minutes (excluding typing time).
- **SC-002**: In the automated access check, 100% of question bank pages and actions refuse the
  administrator and student roles, 100% of add, edit and delete pages and actions refuse teachers
  without the setting, and 100% of requests naming an unknown subject, a deactivated subject, an
  unknown question, a deleted question or a question of a deactivated subject get "not found".
- **SC-003**: 100% of deleted questions remain stored with unchanged text, reference answer, subject
  and number, and 0 of them appear in the list.
- **SC-004**: 0 subjects that have ever had a question can be deleted.
- **SC-005**: After every add, edit, cancel and delete covered by the tests, the teacher lands on the
  page and question this specification names in 100% of cases.
- **SC-006**: Every teacher's **Can manage competitions** value after the upgrade equals their **Can
  create competitions** value before it, and 0 places in the application still show the old name.
- **SC-007**: After the upgrade, 0 sample questions remain and the home page lists 0 questions.
- **SC-008**: The **Questions** tab, the forms and the page navigation are usable at 360 px width
  with no sideways page scrolling, and the three-tab row meets the pinned-frame clearances at 360 px
  and 375 px.
- **SC-009**: Reloading the page after any successful add, edit or delete never repeats it.
- **SC-010**: All tests from milestones 1–10.1 still pass, apart from tests of the sample questions on
  the home page and of the old setting name, which this milestone replaces.

## Assumptions

- **Question numbers are global** across the whole bank, not per subject: a question's number is
  given once, in creation order, and is unique among all questions, including deleted ones. The
  milestone only says the number never changes or passes to another question; one global sequence is
  the simplest reading that satisfies it.
- **"Newest first"** means by creation time; editing a question does not move it in the list.
- **The page gaps** follow the usual pattern: the first and last page, the current page and its
  neighbours are always shown, and a gap mark replaces each longer run of skipped page numbers. The
  exact rule is fixed when the component is added to the library.
- **With only one page**, the page navigation still shows the range ("Questions 1–5 of 5") and shows
  **Previous** and **Next** as unavailable; with no listed question it is not shown.
- **"The page teacher came from" for the add form** is the list page from which **Add question** was
  pressed; **Save and add one more question** keeps it, so **Cancel** on the next empty form still
  returns there.
- **The notice after "Save and add one more question"** reads "The question was saved." in the
  notice component's success style.
- **The add, edit and delete pages** count as changes for the access rule: a teacher without the
  setting gets "access denied" on them, not only on the submitted requests.
- **Access before existence**: a teacher without the setting who names an unknown question gets
  "access denied", not "not found", so the response reveals nothing.
- **The 2,000-character limit** is counted in characters after trimming, line breaks included; no
  further character rules apply, unlike names.
- **The sample questions** are all the questions present before this milestone: questions could not
  be added through the website before it, and no real users exist yet, so the upgrade deletes every
  existing question.
- **The hint for "Select a subject"** tells the teacher to choose a subject in the list above.
- **Who added a question** is not shown and, where it is not needed for anything else, not required;
  the bank is shared.

## Dependencies

- **Milestone 3**: the question entity and the sample questions, both replaced here; the home page
  database line and its unavailable message.
- **Milestone 5**: roles, the current role, "access denied" and the automated route check.
- **Milestone 6**: subjects, their active and deactivated status and the subject in-use rule.
- **Milestone 8**: the **Can create competitions** setting, renamed here, and the teacher
  invitation flow that carries it.
- **Milestone 9**: the teacher area, its tabs and the self-submitting selector (`chained_lists`).
- **Milestone 10**: the component library, the component gallery, the UI guidelines, the form actions
  component and the empty-state, notice, confirmation and error summary components.
- **Milestone 10.1**: the loading bar, the busy button and the pinned frame with its clearances.
- **Later milestones that depend on this one**: milestone 12 picks questions of the competition's
  subject from the bank and must refuse deleted questions; milestone 14 assesses answers against the
  reference answer; milestone 15 keeps showing deleted questions and deactivated subjects in completed
  competitions.

## Out of Scope

- Competitions and the content of the **Competitions** tab: milestone 12.
- Searching or filtering questions other than by subject; sorting other than newest first.
- Moving a question to another subject, restoring a deleted question, erasing a question for good.
- Bulk import or export of questions, attachments, images or formatted text in questions.
- A change history, or showing who added or last changed a question.
- Any access to the question bank for administrators or students.
