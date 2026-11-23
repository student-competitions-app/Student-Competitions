# Feature Specification: Additional Questions in the Question Bank (Teacher) (Milestone 12.9)

**Feature Branch**: `012.9-additional-questions`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: milestone 12.9 of `docs/requirements/milestones.md` ("Additional
questions in the question bank (teacher)"), as refined on 2026-11-23, with `product-requirements.md`
(the "Teacher responsibilities", "Teacher access rights to competitions", "Administrator", "Question"
and "Additional questions" sections), the constitution v2.6.0 (Principles II, III and IV),
`docs/requirements/ui-guidelines.md` (Badges, Cards, Wording, Glossary), and the milestone 5, 8, 10,
10.1, 11, 12.2, 12.5 and 12.8 specifications as reference.

## Overview

Milestone 12.9 of the walking skeleton for the Student Competitions application. After milestone 11,
every teacher reads every question of the question bank with its reference answer, and after
milestone 12.2 a teacher with **Can manage competitions** chooses a competition's questions from it.
A later milestone, not yet scheduled, will give participants the question bank of a subject before a
competition, so students can learn the subject. A competition then needs questions that test
knowledge beyond what participants could study in advance, and those questions are worth something
only while nobody who could pass them on has seen them.

This milestone introduces the **additional question**: a question of the bank that nobody but the
teachers with **Can manage competitions** sees before a competition that holds it starts. Seven
things become true when this milestone is done:

1. **The question form gains the checkbox Additional question.** A teacher with **Can manage
   competitions** marks a question as additional when adding or editing it, and clears the mark the
   same way. Every question already in the bank starts as not additional.
2. **Teachers with the setting see the mark** as the badge **Additional** beside the question's
   number: on the **Questions** tab, on a competition's **Add questions** page and on a competition's
   **Questions** page.
3. **Every other teacher no longer gets the additional questions from the question bank.** For them
   the **Questions** tab lists, counts and pages only the other questions, so nothing on it shows that
   additional questions exist.
4. **The server enforces the rule on every request**: the additional questions are left out of what
   it reads for a teacher without the setting, and every endpoint that names a single bank question
   refuses such a teacher the same way, whether the question is additional, ordinary or missing.
5. **Competitions keep their copies unchanged.** A competition's copy of a question takes no copy of
   the mark, and changing the mark changes nothing stored in any competition.
6. **One gap stays open until milestone 12.10**: every teacher still reads a competition's
   **Questions** page in every status, an **Upcoming** one included. It is recorded and accepted,
   since no real users are involved until every milestone is delivered.
7. **The Additional badge and the text card's badge** are added to the component library and the
   component gallery (`/admin/components`), following the UI guidelines, before any page uses them.

## Clarifications

### Session 2026-11-23 (milestone review)

- Q: Can the mark of a question that cannot be edited be changed? → A: No. The mark is part of the
  question: a deleted question and a question of a deactivated subject keep the mark they have, and
  their edit form and its save answer "Question not found", as in milestone 11 (FR-005).
- Q: How does the edit form show the mark? → A: The checkbox opens checked when the question is
  already additional, and cleared when it is not (FR-008).
- Q: Should a competition's **Questions** page show which of its questions are additional? → A: Yes,
  to teachers with **Can manage competitions** only, as the same **Additional** badge, so they can
  review the mix they chose (FR-025).
- Q: A teacher without the setting can still read a competition's **Questions** page, and can tell
  additional questions from the bank numbers shown there. Is that resolved here? → A: No. It is an
  accepted gap, closed by milestone 12.10 (FR-027).
- Q: Does the invitation explanation of **Can manage competitions** ("You will not be able to manage
  competitions or change the question bank.") need to mention additional questions? → A: No. Not
  being able to manage the bank already covers not managing its additional questions (Assumptions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher with the setting marks a question as additional (Priority: P1)

Olena has **Can manage competitions**. On the **Questions** tab, with the subject "Chemistry"
selected, Olena chooses **Add question**. Below the question text and the reference answer, the form
now has the checkbox **Additional question**, cleared, with the hint "Additional questions and their
answers are not given to participants before a competition.". Olena types a hard question, checks the
box and presses **Save and add one more question**. The next empty form opens with the notice that
the question was saved and the checkbox cleared. Olena adds an ordinary question with **Save
question** and lands on the first page of the list, where both new questions are first; the hard one
shows "Question 58 **Additional**" in its heading, the ordinary one "Question 59" with no badge. Later
Olena opens **Edit** on question 58: the checkbox is checked. Olena clears it and saves, and question
58 is listed with no badge.

**Why this priority**: The mark is the whole point of the milestone; nothing else can be shown or
kept back without it.

**Independent Test**: As a teacher with the setting, add questions with and without the checkbox,
edit one to set and to clear the mark, send an invalid form with the checkbox checked, and check what
is stored and how the list shows each question.

**Acceptance Scenarios**:

1. **Given** the add form, **When** it opens, **Then** it shows the checkbox **Additional question**
   below the reference answer, cleared, with the hint "Additional questions and their answers are not
   given to participants before a competition.".
2. **Given** the add form with the checkbox checked, **When** Olena saves it with **Save question**
   or **Save and add one more question**, **Then** the new question is stored as additional.
3. **Given** the add form with the checkbox cleared, **When** it is saved, **Then** the new question
   is stored as not additional.
4. **Given** Olena used **Save and add one more question** with the checkbox checked, **When** the
   next empty form opens, **Then** its checkbox is cleared.
5. **Given** an additional question, **When** Olena opens **Edit**, **Then** the checkbox is checked;
   for a question that is not additional it is cleared.
6. **Given** the edit form, **When** Olena checks the box and saves, **Then** the question is stored
   as additional; **when** Olena clears the box and saves, **then** it is stored as not additional.
7. **Given** a form (add or edit) with an empty question text and the checkbox checked, **When** it
   is sent, **Then** it is shown again with the field error and the checkbox still checked, and
   nothing is stored; with the checkbox cleared, it is shown again cleared.
8. **Given** an additional question in the list, **When** Olena looks at it, **Then** its card
   heading reads "Question 58" followed by the badge **Additional**; a question that is not additional
   shows no badge.
9. **Given** the application is upgraded to this milestone, **When** the bank is inspected, **Then**
   every question already stored, deleted ones included, is not additional.
10. **Given** a deleted question, or a question of a deactivated subject, additional or not, **When**
    Olena opens its edit form or sends its save with the checkbox changed, **Then** the answer is
    "Question not found", and its mark is unchanged.

---

### User Story 2 - Every other teacher does not get the additional questions (Priority: P1)

Petro is a teacher with **Write** access to an institution and without **Can manage competitions**.
"Chemistry" has 23 questions that are not deleted, 3 of them additional. On the **Questions** tab
Petro sees "Questions 1–10 of 20", two pages and no sign of the other three: no badge, no gap note, no
count of them. "Astronomy" has only additional questions, and Petro sees "No questions yet" for it.
Nothing on the page, and nothing in the page's code, holds an additional question.

**Why this priority**: Keeping the additional questions from everyone who could pass them on is what
gives them their value; a leak in the bank defeats the milestone.

**Independent Test**: As a teacher without the setting, with Read and with Write access, open every
page of a subject that mixes additional and other questions, and of a subject with only additional
questions, and check the responses, the counts and the page navigation.

**Acceptance Scenarios**:

1. **Given** a subject with 20 questions that are not additional and 3 that are, **When** Petro opens
   it, **Then** the list shows only the 20, newest first, 10 per page, and the page navigation reads
   "Questions 1–10 of 20" with two pages.
2. **Given** any page of that subject, **When** its response is inspected, **Then** it holds no text,
   reference answer, number, badge or hidden element of an additional question.
3. **Given** a subject whose listed questions are all additional, **When** Petro opens it, **Then**
   the page shows "No questions yet", with no hint, and no page navigation.
4. **Given** a page number past the last page of the questions Petro may see, **When** it is opened,
   **Then** the last of those pages opens, as in milestone 11.
5. **Given** a teacher with **Read** access only, or with no linked institution, without the setting,
   **When** they open the **Questions** tab, **Then** they get the same list as Petro.
6. **Given** Olena, with the setting, **When** Olena opens the same subject, **Then** Olena sees all 23
   questions and "Questions 1–10 of 23", the three additional ones with the badge.

---

### User Story 3 - A crafted request shows nothing about additional questions (Priority: P1)

Petro types the address of the edit form of question 58, which is additional, then of question 59,
which is not, then of question 9999, which does not exist. Each time Petro gets the same "access
denied" page. A crafted edit, delete or add form gets the same page for each, and nothing changes.

**Why this priority**: Enforcing the rule only on the page would leave the additional questions one
typed-in address away.

**Independent Test**: As a teacher without the setting, send every single-question request of the
bank and every request of a competition's **Add questions** page for an additional question, an
ordinary one, a deleted one and a missing number, and compare the responses.

**Acceptance Scenarios**:

1. **Given** a teacher without the setting, **When** they open the edit form, send its save, open
   the delete confirmation or send the delete, for an additional question, an ordinary question and
   a number that does not exist, **Then** every response is the same "access denied" page (milestone
   5), and nothing is stored or changed.
2. **Given** the same teacher, **When** they open a competition's **Add questions** page or send its
   add for an additional question, an ordinary one or a missing number, **Then** every response is
   the same "access denied" page, and the competition does not change.
3. **Given** the same teacher, **When** they send an add form for a new question with the checkbox
   checked, **Then** they get "access denied" and nothing is stored.
4. **Given** an administrator or a student, **When** they request any page or action of the question
   bank, **Then** they get "access denied", as in milestone 11.

---

### User Story 4 - A teacher with the setting chooses and reviews a mix for a competition (Priority: P2)

Olena opens **Questions** of the **Upcoming** competition "Spring round" of "Chemistry", then **Add
question**. The **Add questions** page lists every question of the subject, the additional ones with
the badge, so Olena adds two additional questions and four ordinary ones. Back on the competition's
**Questions** page, Olena sees the six questions, the two additional ones with the **Additional**
badge beside their bank numbers. Petro opens the same page and sees the six questions without any
badge. After the competition starts, Olena clears the mark of one of the two in the bank: on the
competition's **Questions** page that question no longer shows the badge, and the competition's
stored questions are unchanged.

**Why this priority**: Choosing a mix of questions is why a teacher marks them; it relies on the mark
of User Story 1.

**Independent Test**: As a teacher with the setting, add additional and other questions to an
**Upcoming** competition, then view its **Questions** page with and without the setting in every
status, change a mark in the bank, and compare the page and the stored copies.

**Acceptance Scenarios**:

1. **Given** the **Add questions** page of an **Upcoming** competition, **When** Olena opens it,
   **Then** it lists every question of the subject that the bank lists, additional ones included,
   each additional one with the badge, and each with **Add** or "Already in this competition" as in
   milestone 12.2.
2. **Given** an additional question, **When** Olena adds it, **Then** it is copied to the competition
   like every other question, with the notice "Question 58 was added to “Spring round”".
3. **Given** a competition holding questions whose bank questions are additional, **When** Olena
   opens its **Questions** page in any status (**Upcoming**, **In progress**, **Finished**,
   **Published**, **Cancelled**, and a finished competition of a deactivated subject), **Then** each
   such question shows the badge **Additional** beside its number.
4. **Given** the same page, **When** Petro opens it, **Then** it shows the same questions without any
   badge, and the response holds no badge.
5. **Given** a question deleted from the bank whose bank question is additional, **When** Olena opens
   the competition's **Questions** page, **Then** it shows both the badge and the note "Deleted from
   the question bank".
6. **Given** a question in a competition, **When** its mark is set or cleared in the bank, **Then**
   the badge on the competition's **Questions** page follows the bank's mark, and nothing stored in
   the competition (its questions, their texts, reference answers and order, its teams, answers and
   grades, and its results files) changes.
7. **Given** a competition's **Answers** and **Grades** pages, the answer and grading sheets, the
   **Teams** pages, the confirmations and the results files, **When** any teacher opens them, **Then**
   none shows the mark.

---

### User Story 5 - Changing the setting changes what a teacher sees (Priority: P2)

An administrator gives Petro **Can manage competitions**. The next page Petro opens on the
**Questions** tab lists the additional questions too, with the badge. When the setting is taken away
again, the next page no longer lists them.

**Why this priority**: The setting is the only key to the additional questions; it must take effect
at once in both directions.

**Independent Test**: Give a teacher the setting and take it away between two requests, and check
the **Questions** tab and a competition's **Questions** page after each change.

**Acceptance Scenarios**:

1. **Given** a teacher without the setting, **When** an administrator gives it and the teacher opens
   the next page, **Then** the **Questions** tab lists the additional questions with the badge, and a
   competition's **Questions** page shows the badge.
2. **Given** a teacher with the setting, **When** it is taken away and the teacher opens the next
   page, **Then** the additional questions are no longer listed or counted, the badge is gone from the
   competition's **Questions** page, and an edit form opened earlier is refused when sent.

---

### User Story 6 - The new patterns are written first (Priority: P3)

Before any page shows the mark, a developer finds the **Additional** badge and a text card with a
badge beside its heading in the component gallery, and their rules in the UI guidelines.

**Why this priority**: The constitution requires every new pattern to be in the library, the gallery
and the guidelines first; it shapes how the other stories are built but gives teachers nothing on its
own.

**Independent Test**: Open the component gallery and check the badge and the text card with a badge,
in both themes, at 360 px and at desktop width, and compare them with the guidelines.

**Acceptance Scenarios**:

1. **Given** the component gallery, **When** it is opened, **Then** its badges section shows
   **Additional** and its cards section shows a text card whose heading "Question 57" is followed by
   the badge.
2. **Given** a 360 px wide screen, **When** a text card's heading and badge do not fit on one line,
   **Then** the badge wraps below the heading's text, and the page does not scroll sideways.

---

### Edge Cases

- **A question already in a competition** can be marked and unmarked at any time, whatever the
  competition's status; the competition's copy never changes (FR-004, FR-023).
- **A deleted question** keeps its mark, cannot be marked or unmarked, and is never listed in the
  bank, for anyone; in a competition that holds it, a teacher with the setting sees the badge and
  "Deleted from the question bank" together (FR-005, FR-025).
- **A question of a deactivated subject** keeps its mark and cannot be edited; when the subject is
  activated again, its questions are listed with the marks they had.
- **An additional question in a competition that has started or finished** stays kept back in the
  bank, since it can be added to later competitions (FR-016).
- **Gaps in the numbers**: bank numbers are global across subjects and deleted questions leave gaps,
  so a teacher without the setting seeing "Question 57" then "Question 59" cannot tell whether 58 is
  in another subject, deleted or additional.
- **A link to an additional question** (`/teacher/questions?subject=3&page=2#question-58`) opened by
  a teacher without the setting shows the page of questions they may see; the anchor leads nowhere.
- **The setting changes between opening a form and sending it**: the send is checked again and
  refused as in milestone 11; nothing is stored.
- **Two teachers with the setting edit the same question**, one changing the mark: the last save
  wins, as for the text and the reference answer.
- **A subject with only additional questions**: a teacher with the setting sees them, every other
  teacher sees "No questions yet"; the subject is still offered in the subject list to both.
- **The subject list** offers the same active subjects to every teacher, whatever their questions.
- **Every question in a competition was additional**: the competition behaves as any other; teachers
  without the setting read it on its **Questions** page until milestone 12.10 (FR-027).
- **The checkbox sent with an unexpected value**, or sent twice: any value sent for the checkbox
  marks the question; no value clears it.

## Requirements *(mandatory)*

### Functional Requirements

#### The mark

- **FR-001**: Every question of the bank MUST hold a yes/no mark, **additional question**. A new
  question MUST NOT be additional unless the teacher marks it.
- **FR-002**: On the upgrade to this milestone, every question already stored, deleted ones included,
  MUST become not additional.
- **FR-003**: The mark MUST be set and cleared only on the form for adding and editing a question
  (milestone 11), by a teacher with **Can manage competitions**, and MUST be saved together with the
  question's text and reference answer.
- **FR-004**: The mark MUST be changeable on every question that can be edited, also on one that is
  already in a competition, whatever that competition's status.
- **FR-005**: A question that cannot be edited MUST NOT have its mark changed: a deleted question
  and a question of a deactivated subject MUST keep the mark they have, and their edit form and its
  save MUST answer "Question not found", as in milestone 11 (011 FR-004, FR-038). Deleting a question
  MUST leave its mark unchanged.

#### The checkbox

- **FR-006**: The form for adding and editing a question MUST gain the checkbox **Additional
  question** below the reference answer field and above the save buttons, with the hint "Additional
  questions and their answers are not given to participants before a competition.". It MUST be the
  existing checkbox field of the component library.
- **FR-007**: The add form MUST open with the checkbox cleared.
- **FR-008**: The edit form MUST open with the checkbox checked when the question is additional, and
  cleared when it is not.
- **FR-009**: Saving a form with the checkbox checked MUST store the question as additional; saving
  it with the checkbox cleared MUST store it as not additional. This MUST hold for **Save question**,
  **Save and add one more question** and the save of the edit form alike.
- **FR-010**: **Save and add one more question** MUST open the next empty form with the checkbox
  cleared, whatever the saved question's mark.
- **FR-011**: An invalid form MUST be shown again with the checkbox as it was sent, together with the
  other values and the errors (011 FR-029), and nothing MUST be stored. **Cancel** MUST store nothing
  (011 FR-028).
- **FR-012**: Like the rest of the form, the checkbox MUST be open only to teachers with **Can manage
  competitions**. A form sent by anyone else MUST be refused with "access denied", as in milestone 11
  (011 FR-007), and nothing MUST change.

#### Who sees additional questions in the question bank

- **FR-013**: A teacher with **Can manage competitions** MUST see every listed question on the
  **Questions** tab, as in milestone 11, each additional question with the badge **Additional** beside
  its number in its card heading.
- **FR-014**: Every other teacher, with **Read** or **Write** access or with no linked institution,
  MUST get only the questions that are not additional on the **Questions** tab. The count, the page
  navigation ("Questions 31–40 of 200"), the number of pages and the page a number past the end
  opens MUST count only those questions. A subject whose listed questions are all additional MUST show
  "No questions yet", with no hint. Nothing on the tab, no badge, note, count or hidden element, MUST
  show that additional questions exist. This replaces the milestone 11 rule that every teacher reads
  the whole question bank (011 FR-006).
- **FR-015**: The milestone 11 pages that a teacher with the setting opens for one question (the edit
  form and the delete confirmation) MUST stay as they are apart from the checkbox; the delete
  confirmation MUST still name the question by its number only (011 FR-033), with no badge.
- **FR-016**: The question bank MUST keep an additional question back for good, also after a
  competition that holds it has started, finished, been published or been cancelled, since it can be
  added to later competitions.
- **FR-017**: The setting MUST be checked on every request: a teacher who gets it MUST see the
  additional questions on the next page they open, and a teacher who loses it MUST no longer see them
  on the next page.
- **FR-018**: Administrators and students MUST keep getting "access denied" from every page and
  action of the question bank (011 FR-005).

#### Checked by the server

- **FR-019**: The rule MUST be enforced on every endpoint, never only on the page. For a teacher
  without the setting, the questions of the **Questions** tab MUST be read without the additional
  questions, so no additional question reaches the response, not even hidden.
- **FR-020**: Every endpoint that opens or changes a single question of the bank by its number (the
  edit form and its save, the delete confirmation and the delete), the add form and its save, and a
  competition's **Add questions** page and its add MUST stay open only to teachers with the setting
  (milestones 11 and 12.2), and MUST check the setting before looking up any subject, competition or
  question. Every other teacher MUST get the same "access denied" page (milestone 5) for an additional
  question, an ordinary one, a deleted one and a number that does not exist, so a typed-in address or
  a crafted form does not show whether an additional question exists.
- **FR-021**: Every page and action this milestone changes MUST have automated tests proving both the
  allowed and the denied access, for a teacher with the setting, a teacher without it with Read and
  with Write access, an administrator and a student.

#### Competitions

- **FR-022**: A competition's copy of a question (milestone 12.2) MUST NOT take a copy of the mark:
  the mark belongs to the question of the bank.
- **FR-023**: Changing a question's mark MUST change nothing stored in any competition: not its
  questions, their texts, reference answers or order, not its teams, answers or grades, and not its
  results files.
- **FR-024**: The **Add questions** page of a competition (milestone 12.2) MUST list the additional
  questions of the subject together with the others, newest first as before, each additional one with
  the badge **Additional** beside its number, and each with **Add** or "Already in this competition"
  as in milestone 12.2. An additional question MUST be added like every other question (012.2
  FR-018).
- **FR-025**: On a competition's **Questions** page (milestone 12.2), in every status and for a
  finished competition of a deactivated subject too, a teacher with **Can manage competitions** MUST
  see the badge **Additional** beside the number of each question whose question in the bank is
  additional at that moment, read from the bank as the note "Deleted from the question bank" is
  (012.2 FR-008). A question MAY show both the badge and that note.
- **FR-026**: Every other teacher MUST see a competition's **Questions** page without the badge, and
  the badge MUST NOT be in their response. No other page of a competition (its **Teams**, **Answers**
  and **Grades** pages, the answer and grading sheets, its confirmations and refusals) and no results
  file (milestone 12.8) MUST show the mark, to anyone.
- **FR-027**: Accepted gap: until milestone 12.10, every teacher MUST still be able to read a
  competition's **Questions** page in every status, an **Upcoming** one included (012.2 FR-002), with
  the bank numbers of its questions (012.2 FR-006). A teacher without the setting can therefore read
  the additional questions of a competition before it starts, and tell which of them are additional
  from those numbers and the bank they see. This milestone MUST NOT change that page for them beyond
  FR-026; the gap is the one exception the constitution records (Principle IV) and milestone 12.10
  closes it.

#### Components and UI guidelines

- **FR-028**: The badge **Additional** MUST be added to the component library as its own badge (the
  UI guidelines name it `additional_badge()`), with the `info` kind. It is the mark of a record, not a
  status, and MUST be shown with its word, never colour alone.
- **FR-029**: The text card MUST gain an optional badge beside its heading: the badge follows the
  heading's text inside the heading, on the same line where it fits and wrapping below it on a narrow
  screen, so it is read together with the heading ("Question 57 Additional").
- **FR-030**: Both MUST be shown in the component gallery (`/admin/components`), in its badges and
  cards sections, and MUST follow the rules the UI guidelines already give for them (Badges, Cards,
  Wording), before any page uses them.
- **FR-031**: Every changed page MUST be built from the component library with design tokens only,
  MUST work without JavaScript, and MUST be usable at 360 px width with no sideways scrolling, in both
  themes and both languages.

#### Languages

- **FR-032**: The checkbox label, its hint and the badge MUST be in Ukrainian and English (milestone
  12.5), through the message catalogues: **Additional question** is «Додаткове питання», and the badge
  **Additional** is «Додаткове», agreeing with «питання». The hint follows the glossary («учасники»,
  «змагання»).
- **FR-033**: Question texts and reference answers MUST be shown as entered, never translated, as
  before.

#### Documents

- **FR-034**: The product requirements, the constitution (v2.6.0) and the UI guidelines already
  describe additional questions; the change MUST keep them in agreement with this specification. When
  the milestone is delivered, its summary in `milestones.md` MUST say who sees the additional
  questions; the summary of milestone 11 MUST no longer say that every teacher browses "the shared
  question bank"; and the README's paragraph on the **Questions** tab MUST no longer say that every
  teacher reads the whole bank. In these documents "shared" means given to participants, never that
  the bank is common to all teachers.

#### Verification and scope

- **FR-035**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" line.
- **FR-036**: This milestone MUST NOT give participants anything (the bank is given to them in a
  later milestone, not yet scheduled), MUST NOT change who reads a competition's **Questions** page
  (milestone 12.10), and MUST NOT change any student or administrator page.

### Key Entities *(include if feature involves data)*

- **Question (of the bank)** — milestone 11's question, gaining the mark **additional question**
  (yes or no, no by default). The mark is part of the question: it changes only through the
  question's edit, and a deleted question, or one of a deactivated subject, keeps it. Not personal
  data; who set the mark, and when, is not stored.
- **A competition's question (copy)** — milestone 12.2's copy of a bank question's text and reference
  answer. It holds no mark; a teacher with the setting sees the mark of the bank question it was
  copied from on the competition's **Questions** page.
- **Teacher's setting Can manage competitions** — milestone 8's setting; it now also decides who sees
  the additional questions. It is read on every request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the automated checks, 0 responses of the **Questions** tab to a teacher without the
  setting, on every page of a subject that mixes additional and other questions, hold any part of an
  additional question, and the count shown equals the number of other questions listed.
- **SC-002**: For a teacher without the setting, 100% of the single-question requests of the bank and
  of a competition's **Add questions** page give the same response for an additional question, an
  ordinary one, a deleted one and a missing number.
- **SC-003**: A teacher with the setting marks a new question as additional with one action more than
  adding an ordinary question, and sees it with the badge at the top of the list right after saving.
- **SC-004**: After the upgrade, 0 questions are additional.
- **SC-005**: Setting and clearing marks of questions held by competitions in every status changes 0
  stored values of those competitions.
- **SC-006**: After the setting is given or taken away, the very next page the teacher opens shows,
  or leaves out, the additional questions in 100% of the checks.
- **SC-007**: On a competition's **Questions** page, the badge is shown to a teacher with the setting
  on 100% of the questions whose bank question is additional, and to a teacher without it on 0.
- **SC-008**: The **Questions** tab, the question form, the **Add questions** page and a
  competition's **Questions** page with badges are usable at 360 px width in both languages and both
  themes, with no sideways scrolling.

## Assumptions

- **The badge is `info`**, as the milestone states: a mild highlight that a teacher choosing a mix can
  spot. Every badge kind is already used by some competition status, so any choice repeats a colour
  seen elsewhere; the word is what tells them apart.
- **The Ukrainian hint** reads «Додаткові питання та відповіді на них не надаються учасникам до
  змагання.», using the glossary terms; it is confirmed in review with the other new texts.
- **The invitation explanation of the setting stays as it is** ("You will not be able to manage
  competitions or change the question bank."): not managing the bank covers its additional questions.
- **There is no filter "Additional only"**, on the **Questions** tab or on the **Add questions** page,
  and no count of additional questions on any page; the badge on each card is the only sign.
- **Who set the mark, and when, is not stored**, as who added or changed a question is not
  (milestone 11).
- **The mark carries no other meaning**: an additional question is graded on the same 0–10 scale as
  every other question, counts the same in a team's score and in the maximum score of the results
  files (milestone 12.8), and is ordered in a competition like any other.
- **The edit form does not show the badge**: the checkbox shows the mark there.
- **The bank numbers on a competition's Questions page stay** as milestone 12.2 shows them; showing a
  competition's own position instead is left to milestone 12.10, which hides the page from other
  teachers anyway.
- **No data migration beyond the default** is needed: no real users are involved until every
  milestone is delivered (product requirements, "Production usage").
- **Every quoted text above** is taken from the milestone where the milestone gives it.

## Dependencies

- **Constitution v2.6.0** (amended on 2026-11-23): Principle II (component library first; new
  patterns in the gallery and the guidelines), Principle III (allowed and denied access tested on
  every route) and Principle IV (additional questions kept back from everyone but teachers allowed to
  manage competitions until a competition that holds them starts, left out of what the server reads;
  the milestone 12.9 gap as the one accepted exception).
- **Product requirements** (updated with the milestone): the "Teacher responsibilities", "Teacher
  access rights to competitions", "Administrator", "Question" and "Additional questions" sections.
- **UI guidelines** (updated with the milestone): `additional_badge()`, the text card's `badge`, and
  the row-note rule that the **Additional** mark takes a badge.
- **Milestone 5**: roles, "access denied" and the automated route check.
- **Milestone 8**: **Can manage competitions** and the teachers' **Read** and **Write** links.
- **Milestones 10 and 10.1**: the component library, the gallery, the UI guidelines, the checkbox
  field, the badges, the text card and the loading feedback.
- **Milestone 11**: the question bank, the **Questions** tab, the question form with its two save
  buttons, soft deletion, the page navigation, the order of checks and "Question not found".
- **Milestone 12.2**: a competition's **Questions** page, the **Add questions** page, the copies of
  questions and the note "Deleted from the question bank".
- **Milestone 12.5**: the two languages, the message catalogues and the glossary.
- **Later milestones that depend on this one**: milestone 12.10 keeps a competition's questions from
  teachers without the setting and hands the teams a questions file without the mark; the
  not-yet-scheduled milestone that gives participants the question bank leaves the additional
  questions out.

## Out of Scope

- Giving the question bank, or any question, to participants or students.
- Changing who reads a competition's **Questions** page, or what it shows other teachers (milestone
  12.10).
- A questions file of a competition (milestone 12.10).
- A filter, a count or a sort by the mark, and marking several questions at once.
- Showing the mark anywhere but the **Questions** tab, the **Add questions** page and a competition's
  **Questions** page, or to anyone but teachers with **Can manage competitions**.
- Different grades, weights or scoring for additional questions.
- Changing the invitation, the profile or the administrator's **Teachers** tab.
- Restoring deleted questions, or changing the mark of a deleted question or of a question of a
  deactivated subject.
