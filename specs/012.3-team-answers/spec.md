# Feature Specification: Entering a Team's Answers (Teacher) (Milestone 12.3)

**Feature Branch**: `012.3-team-answers`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: milestone 12.3 of `docs/requirements/milestones.md` ("Entering a team's
answers (teacher)"), part of the 12.x group "Competitions", with `product-requirements.md` (the
"Teacher access rights", "Personal data", "How a competition works", "Competition statuses" and
**Team** sections), the constitution v2.2.0 (Principles IV–VII), the milestone 8, 10, 10.1, 11,
11.1, 12.1 and 12.2 specifications and `docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 12.3 of the walking skeleton for the Student Competitions application, and the third of the
12.x milestones that build the teacher's side of competitions. After milestone 12.2, a competition
holds its questions (copied from the question bank) and its teams, and every teacher can read both
lists, but nobody can give an answer yet.

This milestone lets teachers enter the **teams' answers** of a competition that is **In progress**.
An answer belongs to a team, never to a student: one text answer per question per team. Eight things
become true when this milestone is done:

1. **The actions menu gains Answers.** On an **In progress** competition every teacher, with or
   without **Can manage competitions**, finds **Answers** in the row's menu. The entries read, in this
   order, **Edit**, **Questions**, **Teams**, **Answers** and **Cancel competition**, each where it is
   available.
2. **A teacher sees the answer progress of their own institutions' teams.** "Answers of “Spring
   round”" lists, grouped by region like the **Teams** page, only the competition's teams whose
   institution the teacher is linked to, each with an **Answered** column ("3 of 6").
3. **Write access enters answers, Read access only follows the progress.** A team of an institution
   the teacher has **Write** access to has **Enter answers**; a team of a **Read**-access institution
   has the row note "Read access", and its answers can never be opened by that teacher.
4. **One page holds the whole answer sheet.** "Answers of “Comets” in “Spring round”" shows every
   question of the competition, numbered, each with its answer field, and one **Save answers** button
   saves them all at once. The reference answer is never shown.
5. **The last save wins.** Who saved an answer, or when, is not stored. When two teachers save the
   same team, the later save replaces every answer of the earlier one, emptied ones included.
6. **Answers are entered only while the competition is In progress.** Every page and save re-checks
   the status, the team and the teacher's access; an **Upcoming**, **Cancelled** or **Finished**
   competition shows a refusal and nothing is saved.
7. **Deleting a team deletes its answers in every competition that has not finished.** A **Finished**
   competition keeps the deleted team and its answers.
8. **Two new patterns**, the **answer sheet** and the **placeholder** of an empty field, are added to
   the component library, the component gallery (`/admin/components`) and the UI guidelines before any
   page uses them.

The **Teams** page of milestone 12.2 is unchanged: every teacher still sees all the competition's
teams there, and it has no **Enter answers** button for anyone.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher with Write access enters a team's answers (Priority: P1)

Taras is a teacher without **Can manage competitions**. He has **Write** access to School No. 5 in
Kyiv. "Spring round" of "Chemistry" started at 10:00 and holds 6 questions. On the **Competitions** tab
he opens the **Actions** menu of "Spring round", which lists **Questions**, **Teams** and **Answers**,
and chooses **Answers**. The page "Answers of “Spring round”" lists his school's team "Comets" with
"0 of 6" in the **Answered** column and an **Enter answers** button. He presses it. The page "Answers
of “Comets” in “Spring round”" shows "School No. 5" under the heading, then questions 1 to 6, each with
its text and an empty field labelled "Answer to question 1" (and so on) showing "Not answered". He
types the team's answers to questions 1, 2 and 3 and presses **Save answers**. He stays on the page,
with the notice "Answers of “Comets” were saved" and the three answers in their fields. He follows the
back link: "Comets" now reads "3 of 6".

**Why this priority**: Entering the teams' answers is the purpose of this milestone; without it no
competition has anything to grade.

**Independent Test**: As a teacher with **Write** access to one institution, open the answer sheet of
one of its teams in an **In progress** competition, save, change and empty answers, and check the
fields, the notice, the stored answers, the progress and the back link.

**Acceptance Scenarios**:

1. **Given** Taras has **Write** access to the team's institution, **When** he presses **Enter
   answers**, **Then** the page "Answers of “Comets” in “Spring round”" opens, with the team's
   institution under the heading and a back link to the team answers page at the page he came from,
   at "Comets".
2. **Given** the competition holds 6 questions, **When** the answer sheet is shown, **Then** it lists
   all 6 on one page, in the competition's order (milestone 12.2), numbered 1 to 6, each with its
   copied text and an answer field below it labelled "Answer to question 1", "Answer to question 2"
   and so on.
3. **Given** a question with no saved answer, **When** the sheet is shown, **Then** its field is empty
   with the placeholder "Not answered"; **Given** a saved answer, **Then** it is shown in its field and
   can be changed or emptied.
4. **Given** the sheet, **When** it is shown, **Then** no reference answer appears anywhere on the
   page, and a question deleted from the question bank is shown like any other, with no mark.
5. **Given** he types answers to questions 1, 2 and 3, **When** he presses **Save answers**, **Then**
   all three are saved at once, he stays on the page with the notice "Answers of “Comets” were saved",
   and the saved answers are shown in their fields.
6. **Given** saved answers, **When** he changes one, empties another and fills a new one, and saves,
   **Then** all three changes are stored by that one save, and the emptied question is no longer
   answered.
7. **Given** an answer with spaces or line breaks around it and line breaks inside it, **When** it is
   saved, **Then** it is stored trimmed, with its inner line breaks kept, and shown that way.
8. **Given** an answer made only of spaces or line breaks, **When** it is saved, **Then** the question
   counts as not answered.
9. **Given** a save, **When** the page is reloaded, **Then** the save is not repeated.

---

### User Story 2 - A teacher sees their institutions' teams with their progress (Priority: P1)

"Spring round" holds 30 teams from five regions. Taras has **Write** access to School No. 5 (Kyiv) and
to Gymnasium No. 1 (Kyiv), and **Read** access to Lyceum No. 2 (Lviv); 12 of the competition's teams
belong to these three institutions. On "Answers of “Spring round”" he sees "Teams 1–10 of 12": a box
"Kyiv · 9 teams" with its 9 teams and a box "Lviv · 3 teams" with the first one. The second page starts
with "Lviv · 3 teams" again and its other 2 teams. Teams of the other institutions in the competition
are not shown at all. Each row shows the team's name, its institution, its number of active members
and its progress.

**Why this priority**: The team answers page is the only way to the answer sheets, and for a teacher
with **Read** access it is the only view of the answers' progress.

**Independent Test**: Seed a competition with teams of linked and unlinked institutions in several
regions, 12 of them listable, and check which teams are listed, the grouping, the order, the paging,
the headers and their counts, the rows, the progress and the phone layout.

**Acceptance Scenarios**:

1. **Given** an **In progress** competition, **When** **Answers** is chosen, **Then** the page
   "Answers of “Spring round”" opens, showing under the heading the competition's subject, its start
   in the teacher's time zone and its status badge, with a back link to the competitions list the
   teacher came from (same subject, status and page), at the competition, as the pages of milestone
   12.2.
2. **Given** the competition's teams, **When** the page lists them, **Then** it lists only the teams
   whose institution the teacher is linked to, with **Read** or **Write** access; teams of other
   institutions are not shown at all, not even greyed out, and teams of a deactivated institution or
   region are not listed either.
3. **Given** listed teams of several regions, **When** they are shown, **Then** they are grouped in
   region boxes as on the **Teams** page: the regions sorted by name ignoring case, the teams inside a
   region sorted by name ignoring case, 10 teams per page with the page navigation ("Teams 1–10 of
   12"), and a region whose teams continue on the next page shows its header again.
4. **Given** a region box, **When** its header is shown, **Then** it shows the region's name as it is
   stored and how many teams of that region the page lists across all its pages, counting only the
   listed teams ("Kyiv · 9 teams", "Kyiv · 1 team").
5. **Given** a team row, **When** it is shown, **Then** it shows the team's name, its educational
   institution and the number of the team's own active members (milestone 11.1), then its progress in
   an **Answered** column, then the actions cell.
6. **Given** a team that has saved non-empty answers to 3 of the competition's 6 questions, **When**
   its row is shown, **Then** the progress reads "3 of 6"; a team with no answers reads "0 of 6", and
   every team of a competition with no questions reads "0 of 0".
7. **Given** the progress, **When** it is shown, **Then** it is plain text, not part of a button's
   label, read as a column on a wide screen and as a labelled line of the card on a phone.
8. **Given** any teacher, also one with **Can manage competitions**, **When** the page is shown,
   **Then** it has no **Add team** and no **Remove**.
9. **Given** the page number, **When** the page is reloaded or bookmarked, **Then** it is kept in the
   page address and restored.

---

### User Story 3 - A teacher with Read access follows the progress only (Priority: P1)

Taras's colleague Iryna has only **Read** access to Lyceum No. 2. On "Answers of “Spring round”" she
sees the lyceum's three teams, each with its progress, and the row note "Read access" where **Enter
answers** would be. She types the address of the answer sheet of one of them and gets "access denied":
she never sees or changes the answers themselves. Taras has **Write** access to School No. 5 and
**Read** access to Lyceum No. 2, so his page shows **Enter answers** on the school's teams and "Read
access" on the lyceum's.

**Why this priority**: **Read** access shows how many questions a team has answered, never the
answers (Principle IV); a missing check would leak them.

**Independent Test**: As teachers with only **Read** access and with mixed access, check the actions
cell of every row, and try the answer sheet and a save of a **Read**-access team through a typed
address and a crafted form.

**Acceptance Scenarios**:

1. **Given** a team of an institution the teacher has **Write** access to, **When** its row is shown,
   **Then** the actions cell holds **Enter answers**.
2. **Given** a team of an institution the teacher has only **Read** access to, **When** its row is
   shown, **Then** the actions cell holds the row note "Read access", with no button.
3. **Given** a teacher with only **Read** access, **When** the page is shown, **Then** they see their
   institutions' teams with their progress and no **Enter answers**.
4. **Given** a team of a **Read**-access institution, **When** the teacher opens its answer sheet
   through a typed address or sends a save for it, **Then** they get "access denied" and nothing is
   saved.

---

### User Story 4 - The menu offers Answers on a competition in progress (Priority: P1)

Mykola, without **Can manage competitions**, opens **Competitions** with the status **All**. The menu
of the in-progress "Spring round" lists **Questions**, **Teams** and **Answers**; the menus of upcoming,
finished and cancelled competitions list only **Questions** and **Teams**. Olena, with the setting,
sees **Questions**, **Teams**, **Answers** and **Cancel competition** on "Spring round", and **Edit**,
**Questions**, **Teams** and **Cancel competition** on an upcoming competition.

**Why this priority**: The menu is the only way into the new pages.

**Independent Test**: List competitions of every status as teachers with and without the setting and
check each menu's entries and their order.

**Acceptance Scenarios**:

1. **Given** any teacher, **When** the menu of an **In progress** competition opens, **Then** it
   offers **Answers**.
2. **Given** a teacher with the setting, **When** an **In progress** competition's menu opens,
   **Then** it lists **Questions**, **Teams**, **Answers** and **Cancel competition**, in this order;
   **Given** a teacher without the setting, **Then** it lists **Questions**, **Teams** and **Answers**.
3. **Given** any teacher, **When** the menu of an **Upcoming**, **Finished** or **Cancelled**
   competition opens, **Then** it does not offer **Answers**, and the other entries keep their 12.2
   rules and order.
4. **Given** **Answers** is chosen, **When** the page opens, **Then** the competitions list's subject,
   status and page are kept for the way back.

---

### User Story 5 - The Teams page stays as it is (Priority: P1)

Mykola opens the **Teams** page of "Spring round": he sees every team of the competition, from every
institution, read-only, with no **Add team**, no **Remove** and no **Enter answers**. Olena, with the
setting, sees **Add team** and **Remove** on an upcoming competition and, in no status, **Enter
answers**.

**Why this priority**: The milestone keeps the two views apart: all teams on **Teams**, and only the
teacher's own on **Answers**, the only place answers are entered from.

**Independent Test**: Open the **Teams** page of competitions of every status as teachers with and
without the setting and with and without links, and check the teams and the buttons.

**Acceptance Scenarios**:

1. **Given** a teacher without the setting, **When** they open a competition's **Teams** page,
   **Then** they see all its teams, from every institution, with no **Add team**, no **Remove** and no
   **Enter answers**.
2. **Given** a teacher with the setting, **When** they open the **Teams** page of an **Upcoming**
   competition, **Then** they see **Add team** and **Remove** (milestone 12.2), and in no status do
   they see **Enter answers**.

---

### User Story 6 - Answers that are too long save nothing (Priority: P1)

Taras pastes a long text into the answer to question 4, 2,001 characters after trimming, and also
changes the answers to questions 1 and 5. He presses **Save answers**. Nothing is saved: the page
shows again with every text he entered kept, the error at question 4 and the error summary "There is a
problem" linking to it. He shortens the answer to exactly 2,000 characters and saves: all the answers
are saved.

**Why this priority**: A save stores the whole sheet, so it must never store part of it; and a lost
long answer would cost the teacher their typing.

**Independent Test**: Save a sheet with one answer of 2,001 characters after trimming among other
changes, and then with exactly 2,000; check that nothing, then everything, is stored, and the kept
texts, the error and the summary.

**Acceptance Scenarios**:

1. **Given** an answer longer than 2,000 characters after trimming, **When** the sheet is saved,
   **Then** nothing is saved, no other answer included, and the page shows again with every entered
   text kept.
2. **Given** that refused save, **When** the page is shown again, **Then** the error stands at that
   answer, with the wording of milestone 11, and the error summary under the heading links to it.
3. **Given** several answers are too long, **When** the sheet is saved, **Then** each of them shows its
   error and the summary lists them all, in the order of the questions.
4. **Given** an answer of exactly 2,000 characters after trimming, **When** the sheet is saved,
   **Then** it is saved.

---

### User Story 7 - Answers are entered only while the competition is In progress (Priority: P1)

Taras has the answer sheet of "Comets" open when Olena cancels "Spring round". He presses **Save
answers**: nothing is saved, and the page "Enter answers for “Spring round”?" says "“Spring round” has
been cancelled, so its answers can no longer be entered." with the link **Back to competitions**. He
types the address of the team answers page of the upcoming "Autumn round" and sees the refusal "“Autumn
round” has not started yet, so its answers cannot be entered yet."; once its start has passed, the same
address shows the page.

**Why this priority**: Answers are entered only while a competition is **In progress** (Principle
VII); answers changed after it was cancelled or finished would falsify its record.

**Independent Test**: With the current time controlled by the test, open both pages and send saves for
an **Upcoming** competition, one cancelled while the sheet is open and a **Finished** one (stored
directly by the test); check the refusals, their reasons and links, that nothing is saved, and that
the **Upcoming** refusal turns into the page when the start passes.

**Acceptance Scenarios**:

1. **Given** an **Upcoming** competition, **When** its team answers page or an answer sheet is opened
   (typed address) or a save is sent, **Then** the refusal "Enter answers for “Autumn round”?" is
   shown with the reason "“Autumn round” has not started yet, so its answers cannot be entered yet."
   and nothing is saved.
2. **Given** a **Cancelled** competition, **When** the same is tried, **Then** the reason reads "“Spring
   round” has been cancelled, so its answers can no longer be entered."; **Given** a **Finished** one,
   **Then** it reads "“Spring round” has finished, so its answers can no longer be entered.".
3. **Given** a refusal, **When** **Back to competitions** is followed, **Then** it leads to the
   competitions list the teacher came from, at the competition, as the 12.1 edit refusal.
4. **Given** a competition cancelled while its answer sheet is open, **When** the save is sent,
   **Then** the refusal is shown and nothing is saved.
5. **Given** an **Upcoming** competition whose start then passes, **When** the same address is opened
   again, **Then** the page is shown.

---

### User Story 8 - Only the right teacher reaches the right team (Priority: P1)

An administrator and a student who type the address of a team answers page get "access denied",
before any id is read. Taras types the answer sheet address of a team of an institution he is not
linked to and gets "access denied". He changes the team id to one that is not in the competition, and
then to a deleted team, and gets "not found". A hand-made save that names a question of another
competition gets "not found" and saves nothing. While Taras has a sheet open, an administrator lowers
his access to School No. 5 to **Read**: his save gets "access denied", and the answers saved before
stay.

**Why this priority**: A team's answers decide its result; a missing check would let anyone change
them.

**Independent Test**: For every page and save of this milestone, send requests as each role and as
teachers with **Write**, **Read** and no link, including typed addresses and crafted forms for unknown,
mismatched and hidden subjects, competitions, teams and questions, and links changed while a page is
open; check the result, the check order and that nothing is saved.

**Acceptance Scenarios**:

1. **Given** a person in the administrator or student role, **When** they open any page or send any
   save of this milestone, also with unknown ids, **Then** they get "access denied" before any id is
   read.
2. **Given** any teacher, **When** the address names an unknown subject or competition, a competition
   of another subject or a competition of a deactivated subject, **Then** they get "not found", as in
   milestone 12.2.
3. **Given** an **In progress** competition, **When** the answer sheet or a save names an unknown or
   deleted team, a team that is not in the competition, or a team of a deactivated institution or
   region, **Then** it shows "not found" and nothing is saved.
4. **Given** a save, **When** it names a question that is not one of the competition's, **Then** it
   shows "not found" and nothing is saved.
5. **Given** a team of an institution the teacher is not linked to, **When** they open its answer sheet
   or send a save for it, **Then** they get "access denied" and nothing is saved.
6. **Given** a teacher who is unlinked from the team's institution, or lowered to **Read** access,
   while the sheet is open, **When** they save, **Then** they get "access denied", nothing is saved,
   and the answers saved before stay.
7. **Given** a teacher is unlinked from an institution, **When** the team answers page is loaded next,
   **Then** its teams are no longer listed; **Given** their access is lowered to **Read**, **Then** its
   teams show "Read access" instead of **Enter answers**.
8. **Given** checks fail at several levels, **When** a request is handled, **Then** the first failing
   check in the order role, subject and competition, status, team and questions, access to the team
   decides the answer: a cancelled competition with a team of an unlinked institution shows the
   refusal, a deleted team of a **Read**-access institution shows "not found", and a non-teacher
   sending unknown ids gets "access denied".
9. **Given** any save, **When** the existing cross-site request check judges it sent from another
   site, **Then** it is refused and nothing is saved.

---

### User Story 9 - The empty states (Priority: P2)

Nadiia is a teacher whose only link is to an institution that was deactivated: "Answers of “Spring
round”" shows "You are not linked to any educational institution". Bohdan has **Write** access to a
school none of whose teams is in "Spring round": he sees "No teams from your educational institutions".
"Winter round" holds no questions: its answer sheets show "No questions in this competition" and no
**Save answers**, and its teams read "0 of 0".

**Why this priority**: Every teacher gets **Answers**, so the page must say clearly why there is
nothing to do; the cases are rare but must not look broken.

**Independent Test**: Open the team answers page as a teacher with no available link and as one whose
institutions have no team in the competition, and open the answer sheet of a competition with no
questions.

**Acceptance Scenarios**:

1. **Given** a teacher linked to no available institution (an active institution in an active
   region), **When** the team answers page is shown, **Then** it shows "You are not linked to any
   educational institution", as on the **Teams** tab (milestone 11.1).
2. **Given** a teacher linked to available institutions, none of whose teams is in the competition,
   **When** the page is shown, **Then** it shows "No teams from your educational institutions".
3. **Given** a competition with no questions, **When** an answer sheet is shown, **Then** it shows "No
   questions in this competition" and no **Save answers** button, and the team answers page shows
   "0 of 0" for every team.

---

### User Story 10 - Two teachers save the same team (Priority: P2)

"Comets" has an answer to question 1. Taras and his colleague Oksana both have **Write** access to
School No. 5 and open the answer sheet of "Comets" at the same time. Oksana answers question 2 and
saves. Taras, whose page does not show her answer, empties question 1, answers question 3 and saves a
minute later. The team's answers are now exactly those of Taras's page: question 1 is not answered,
question 2 is not answered either (Oksana's answer is replaced by the empty field Taras's page sent),
and question 3 is answered. Neither is warned.

**Why this priority**: The milestone accepts this on purpose: usually one teacher is linked to an
institution, and a team's answers are not reserved for a teacher. The behaviour must still be
predictable.

**Independent Test**: Open the same team's sheet twice, save different answers from each, including an
emptied one, and check that the stored answers are exactly those of the later save.

**Acceptance Scenarios**:

1. **Given** two teachers save the same team's sheet one after the other, **When** the second save is
   stored, **Then** it replaces every answer of the first, emptied ones included, with no warning and
   no refusal.
2. **Given** two saves of the same team at the same moment, **When** both are stored, **Then** the
   team's answers are exactly those of one of the two saves, never a mix of both.

---

### User Story 11 - Deleting a team deletes its answers in unfinished competitions (Priority: P2)

"Comets" has answers in the in-progress "Spring round", the cancelled "Autumn round" and the finished
"Summer round". Taras deletes "Comets" on the **Teams** tab (milestone 11.1). It is taken out of
"Spring round" and "Autumn round" with its answers there (milestone 12.2); "Summer round" keeps it,
marked "(deleted)", with its answers. Oksana, who had the answer sheet of "Comets" in "Spring round"
open, presses **Save answers** and gets "not found".

**Why this priority**: A deleted team takes no part in a competition, while a finished competition
keeps its complete record for the results of milestone 15.

**Independent Test**: Give a team answers in an **In progress**, a **Cancelled** and a **Finished**
competition (the last two stored directly by the test), delete it, and check the stored answers in
each; send a save from a sheet opened before the deletion.

**Acceptance Scenarios**:

1. **Given** a team with answers in an **In progress** and a **Cancelled** competition, **When** it is
   deleted, **Then** its answers in both are deleted, as part of the deletion that takes it out of
   them.
2. **Given** a team with answers in a **Finished** competition, **When** it is deleted, **Then** the
   competition keeps the team and its answers.
3. **Given** an answer sheet opened before the team was deleted, **When** it is saved, **Then** it
   shows "not found" and nothing is saved.

---

### User Story 12 - The new patterns are written first (Priority: P3)

An administrator opens `/admin/components` outside production and finds the answer sheet: numbered
questions, each a text card with its answer field under it, one with an error, one primary save button
below, also at phone width; and an empty answer field showing the placeholder "Not answered" under its
label. The UI guidelines describe the answer sheet, and their wording patterns gain the placeholder
rule.

**Why this priority**: It follows the project rule that pages use only library components; it adds no
capability of its own.

**Independent Test**: Open the gallery and the UI guidelines and check each addition.

**Acceptance Scenarios**:

1. **Given** the gallery, **When** it is opened, **Then** it shows the answer sheet, with an error and
   at phone width, and the "Not answered" placeholder.
2. **Given** the UI guidelines, **When** they are read, **Then** they describe the answer sheet, and
   their wording patterns say that a placeholder only says that the field is empty ("Not answered")
   and never replaces the field's label or hint.

---

### Edge Cases

- **The competition is cancelled while the sheet is open**: the save shows the "has been cancelled"
  refusal and saves nothing; the answers saved before stay.
- **The competition is stopped (stored as Finished by the test) while the sheet is open**: the save
  shows the "has finished" refusal and saves nothing.
- **The subject is deactivated while the sheet is open**: the next save gets "not found" and saves
  nothing; the answers saved before stay.
- **The team's institution or region is deactivated while the sheet is open**: the next save gets "not
  found"; the team disappears from the team answers page; its answers stay stored.
- **The teacher's link is removed or lowered to Read while the sheet is open**: the next save gets
  "access denied"; the answers saved before stay.
- **The team is deleted while the sheet is open**: the next save gets "not found"; its answers in the
  competition are already deleted.
- **A team is renamed, or its members change, while the pages are open**: the next page shows the
  current name and number of active members; the answers stay with the team.
- **A question deleted from the question bank**: shown on the sheet like any other question, with its
  copied text and no mark, and answered like any other.
- **An answer made only of spaces and line breaks**: trimmed to nothing, so the question is not
  answered and does not count in the progress.
- **An answer of 2,001 characters before trimming but 2,000 or fewer after**: it is saved.
- **Saving with nothing changed**: the save is accepted and shows the notice; the stored answers stay
  the same.
- **Pressing Save answers twice (double press)**: the form cannot be sent again until the next page
  arrives (milestone 10.1); a second request arriving anyway stores the same answers again.
- **A competition with many questions**: all are shown on the one sheet, with no page navigation.
- **A page number beyond the last page, or not a number**, on the team answers page: it opens on the
  nearest valid page, as on **Teams**.
- **The competitions-list context or the team answers page in the address is missing or invalid**:
  the back links fall back as in milestone 12.2 (the competition's subject, the status **All** and the
  page holding the competition; the page of the team answers list holding the team).
- **A teacher linked to an institution whose teams are all deleted**: if no other team of their
  institutions is in the competition, "No teams from your educational institutions".
- **A team whose institution was deactivated and reactivated**: it is listed again, with the answers
  it had.
- **Very long competition, team, institution or region names, long question texts and long
  answers**: they wrap within the content width on every screen size, with no sideways page scroll, in
  the headings, region headers, rows, cards, fields, refusals and notices.

## Requirements *(mandatory)*

### Functional Requirements

#### Row actions

- **FR-001**: The actions menu of milestones 12.1 and 12.2 MUST gain the entry **Answers**. The menu
  MUST list, in this order, **Edit**, **Questions**, **Teams**, **Answers** and **Cancel competition**,
  each only where it is available.
- **FR-002**: **Answers** MUST be offered on every **In progress** competition the list shows, to every
  teacher, with or without **Can manage competitions** and whatever their links. It MUST NOT be offered
  on an **Upcoming**, **Finished** or **Cancelled** competition. The other entries keep their 12.1 and
  12.2 rules.

#### The Teams page

- **FR-003**: The **Teams** page of milestone 12.2 MUST stay unchanged: every teacher sees all the
  competition's teams, from every institution; it is read-only for a teacher without **Can manage
  competitions**; and it has no **Enter answers** button for anyone. A team's answers MUST be entered
  only from the team answers page.

#### The team answers page

- **FR-004**: **Answers** MUST open the page "Answers of “…”" with the competition's name. Under the
  heading it MUST show the competition's subject, its start in the teacher's time zone and its status
  badge, and it MUST have a back link to the competitions list the teacher came from (same subject,
  status and page), at the competition, as the pages of milestone 12.2. That context MUST be carried
  through every page and save of this milestone, so the back links always lead to the same list.
- **FR-005**: The page MUST list only the competition's teams whose institution the teacher is linked
  to, with **Read** or **Write** access. Teams of other institutions MUST NOT be shown at all, not even
  greyed out. Teams of a deactivated institution or of an institution in a deactivated region MUST NOT
  be listed.
- **FR-006**: The page MUST look and behave like the **Teams** page of milestone 12.2: the listed teams
  grouped in region boxes, the regions sorted by name ignoring case and the teams inside a region
  sorted by name ignoring case; 10 teams per page with the page navigation ("Teams 1–10 of 12"); a
  region whose teams continue on the next page showing its header again; the same phone layout. The
  page number MUST be kept in the page address.
- **FR-007**: A region header MUST show the region's name as it is stored and how many teams of that
  region the page lists across all its pages, counting only the listed teams ("Kyiv · 3 teams", "Kyiv ·
  1 team").
- **FR-008**: Each row MUST show the team's name, its educational institution and the number of the
  team's own active members (milestone 11.1), then the team's answer progress in an **Answered**
  column, then the actions cell. The progress MUST be plain text, not part of a button's label, read
  as a column on a wide screen and as a labelled line of the card on a phone.
- **FR-009**: The progress MUST read "<answered> of <questions>": the number of the competition's
  questions that have a saved non-empty answer of the team, of the number of questions in the
  competition ("3 of 6"; "0 of 6" for a team with no answers; "0 of 0" for a competition with no
  questions). It MUST be counted when the page is shown and MUST NOT be stored.
- **FR-010**: The actions cell MUST hold an **Enter answers** button for a team of an institution the
  teacher has **Write** access to, and the row note "Read access" (no button, UI guidelines) for a team
  of an institution the teacher has only **Read** access to.
- **FR-011**: The page MUST have no **Add team** and no **Remove**, also for a teacher with **Can
  manage competitions**.
- **FR-012**: Empty states, the first that applies: a teacher linked to no available institution (an
  active institution in an active region) MUST see "You are not linked to any educational
  institution", as on the **Teams** tab (milestone 11.1); otherwise, when no team of their
  institutions is listed, "No teams from your educational institutions".
- **FR-013**: The teacher's links MUST be read on every request: when a teacher is unlinked from an
  institution, its teams MUST disappear from their team answers page at once; when their access is
  lowered to **Read**, its teams MUST lose **Enter answers** at once.

#### The answer sheet

- **FR-014**: **Enter answers** MUST open the page "Answers of “<team>” in “<competition>”", with the
  team's educational institution under the heading and a back link to the team answers page at the
  page the teacher came from, at that team.
- **FR-015**: The sheet MUST show every question of the competition on one page, in the competition's
  order (milestone 12.2), numbered 1, 2, 3, …, each with its copied text and an answer field below it,
  labelled "Answer to question <n>". The reference answer MUST never be shown. A question deleted from
  the question bank MUST be shown like any other.
- **FR-016**: A question with no saved answer MUST show an empty field with the placeholder "Not
  answered". A saved answer MUST be shown in its field and MUST be changeable and removable by
  emptying the field.
- **FR-017**: One **Save answers** button below the questions MUST save all the answers of the sheet
  at once. An empty field MUST mean that the question is not answered.
- **FR-018**: Answers MUST be trimmed, MUST keep their inner line breaks, and MUST be at most 2,000
  characters after trimming, as in the question bank (milestone 11), with the error wording of
  milestone 11.
- **FR-019**: If any answer is too long, nothing MUST be saved, and the page MUST show again with every
  entered text kept, the error at each answer that is too long and the error summary linking to them.
- **FR-020**: After a save the teacher MUST stay on the sheet, with the saved answers in their fields
  and the notice "Answers of “<team>” were saved".
- **FR-021**: A competition with no questions MUST show "No questions in this competition" on the
  sheet, and no **Save answers** button.

#### The team's answers

- **FR-022**: An answer MUST belong to a team: at most one text answer per question of the competition
  per team. A student MUST have no answers of their own.
- **FR-023**: Who saved an answer, or when, MUST NOT be stored. A team's answers are not personal data,
  and no special logging rule applies to them.
- **FR-024**: A team's answers MUST NOT be reserved for a teacher. Each **Save answers** MUST store
  every answer of its page, and the last save MUST win: it replaces the answers an earlier save stored,
  emptied ones included, with no warning and no refusal. A save MUST be stored as a whole, so the
  team's answers are always those of one save, also when two saves arrive at the same moment.

#### Checks and refusals

- **FR-025**: Every page and save of this milestone MUST check everything again when it is opened or
  sent, whatever the page showed, and again when a save is stored. The checks MUST run in this order,
  and the first failing one MUST decide the answer:
  1. the role: anyone who is not a teacher gets "access denied", before any id is read;
  2. the subject and the competition: an unknown subject or competition, a competition of another
     subject, or a competition of a deactivated subject shows "not found", as in milestone 12.2;
  3. the status: a competition that is not **In progress** shows the refusal of FR-026;
  4. the team and the questions (answer sheet and save): an unknown or deleted team, a team that is
     not in the competition, or a team of a deactivated institution or region shows "not found"; so
     does a save that names a question that is not one of the competition's, and then nothing is
     saved;
  5. the access to the team (answer sheet and save): a team of an institution the teacher is not
     linked to, or has only **Read** access to, gets "access denied".
  Only then MUST the answers' length be checked (FR-019).
- **FR-026**: For a competition that is not **In progress**, both pages and the save MUST show a
  refusal in the 12.1 pattern, "Enter answers for “…”?", with the reason for its status: "“…” has not
  started yet, so its answers cannot be entered yet." (**Upcoming**), "“…” has been cancelled, so its
  answers can no longer be entered." (**Cancelled**) or "“…” has finished, so its answers can no longer
  be entered." (**Finished**), and the link **Back to competitions** to the competitions list the
  teacher came from, at the competition, as the 12.1 edit refusal. A save sent then MUST change
  nothing.
- **FR-027**: When an access check refuses a save (unlinked, or lowered to **Read**), the answers saved
  before MUST stay.

#### Deleting and deactivating elsewhere

- **FR-028**: Deleting a team (milestone 11.1) MUST delete its answers in every competition that is
  not **Finished**, as part of the deletion that takes it out of those competitions (milestone 12.2).
  A **Finished** competition MUST keep the deleted team and its answers. A save from an answer sheet
  opened before the deletion MUST get "not found".
- **FR-029**: Deactivating an institution or a region MUST keep its teams' answers stored; while
  deactivated, those teams are not listed (FR-005) and their sheets and saves show "not found"
  (FR-025).

#### Shared page and action behaviour

- **FR-030**: Every save MUST be a form submission that passes the existing cross-site request check.
  Opening a page or following a link MUST never change anything, and reloading a page after a save
  MUST never repeat it.
- **FR-031**: No log line MUST contain an email address or a person's name. Answers are not personal
  data and are under no special logging rule (constitution v2.2.0, Principle V).
- **FR-032**: Every page of this milestone MUST follow the UI guidelines, including the loading
  feedback and busy button of milestone 10.1, and MUST work on a phone-width screen without sideways
  page scrolling.

#### Components

- **FR-033**: The pages MUST be built from existing components: the section heading, the region group,
  data tables, page navigation, `row_note`, text cards, `textarea_field`, the error summary, notices,
  empty states, refusals, back links, the local-time display and the competition status badge.
- **FR-034**: Two patterns MUST be new, each added to the component library, the component gallery
  (`/admin/components`) and the UI guidelines before any page uses it:
  - the **answer sheet**: a numbered list of questions, each a text card with its answer field
    (`textarea_field`) under it, one error per answer, and one primary save button below the list,
    with labelled answers and the phone layout of the guidelines;
  - the **placeholder** of an empty field: it only says that the field is empty ("Not answered") and
    never replaces the field's label or hint; the UI guidelines MUST gain this rule in their wording
    patterns.

#### Rules already written down

- **FR-035**: The product requirements (updated with the milestone) and the constitution v2.2.0
  (Principles IV–VII) already state the rules of this milestone: answers belong to a team; a teacher
  enters them only with **Write** access and with **Read** access sees only the progress; answers are
  not personal data; answers are entered only while the competition is **In progress**; deleting a team
  deletes its answers in every competition that has not finished. The implementation MUST NOT
  contradict them; no further amendment is needed.

#### Verification and scope

- **FR-036**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" list: the menu entries and their order per status and setting; the **Teams**
  page with and without the setting and with no **Enter answers**; the listing for **Write**, **Read**
  and mixed access, unlinked and deactivated institutions and regions, lowering a link to **Read**, and
  12 listed teams in two regions with one spanning a page break and its header counts; both empty
  states; the progress at "0 of 6", "3 of 6", "2 of 6" and "0 of 0"; the answer sheet's order,
  numbering, copied texts (after the bank question is edited or deleted), placeholder and saved
  answers, with no reference answer; saving, changing and emptying at once, trimming and line breaks,
  the notice and reloads; 2,001 and 2,000 characters; no questions; two teachers saving the same team;
  the refusals for **Upcoming** (typed address), cancelled while open and **Finished** (stored directly
  by the test), and the start passing; every "not found" and "access denied" case and the check order;
  deleting a team in an **In progress**, a **Cancelled** and a **Finished** competition and a save from
  a page opened before; the cross-site request check; and the gallery.
- **FR-037**: This milestone MUST NOT add anything listed under **Out of Scope** below.

### Key Entities *(include if feature involves data)*

- **Team answer** (new): one team's text answer to one question of one competition. It belongs to one
  competition team and one competition question; a team holds at most one answer per question. It
  holds the trimmed text, 1 to 2,000 characters; a question with no answer, or an emptied one, is not
  answered. It stores neither who saved it nor when. It is not personal data. It is deleted with the
  team's place in a competition that is not **Finished** when the team is deleted, and kept in a
  **Finished** one.
- **Competition team** (existing, milestone 12.2): now has its answers.
- **Competition question** (existing, milestone 12.2): the question an answer answers; its copied text
  is shown on the sheet, its reference answer never.
- **Competition** (existing, milestones 12.1 and 12.2): its answers are entered only while it is **In
  progress**.
- **Teacher's link to an institution** (existing, milestone 8): **Write** enters a team's answers,
  **Read** sees only the progress; read on every request.
- **Team** (existing, milestone 11.1): deleting it now also deletes its answers in every competition
  that is not **Finished**.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the competitions list, a teacher with **Write** access reaches a team's answer
  sheet with three choices (**Actions**, **Answers**, **Enter answers**) and saves the answers to every
  question with one press of **Save answers**.
- **SC-002**: In the automated access check, 100% of pages and saves of this milestone refuse the
  administrator and student roles before any id is read; 100% of answer sheets and saves for a team of
  an unlinked or **Read**-access institution get "access denied"; and 100% of requests naming an
  unknown, mismatched or hidden subject, competition, team or question get "not found", with nothing
  saved in every case.
- **SC-003**: 0 answers are saved, changed or deleted through this milestone's pages for a competition
  that is not **In progress**.
- **SC-004**: 0 reference answers, and 0 answers of a team the teacher has only **Read** access to, or
  no link to, appear on any page of this milestone.
- **SC-005**: 100% of refused saves (an answer too long, a refusal, "not found", "access denied")
  store nothing, and 100% of saves too long for one answer show the page again with every entered text
  kept.
- **SC-006**: After two saves of the same team, also at the same moment, the stored answers are
  exactly those of one save in 100% of the tested cases.
- **SC-007**: The progress on the team answers page equals the number of saved non-empty answers in
  100% of the tested cases.
- **SC-008**: After a team is deleted, 0 answers of it remain in competitions that are not
  **Finished**, and 100% of its answers in **Finished** competitions remain.
- **SC-009**: Every page of this milestone is usable at 360 px width with no sideways page scrolling.
- **SC-010**: Reloading the page after a save never repeats it.
- **SC-011**: All tests from milestones 1–12.2 still pass, apart from those of the rule this milestone
  changes: the entries of the actions menu of an **In progress** competition (milestone 12.2).

## Assumptions

- **The error wording of milestone 11** for a too-long answer reads "Answer to question <n> can be at
  most 2,000 characters.", following "The question text can be at most 2,000 characters." with the
  answer field's label as its subject.
- **Each answer field has the hint "Up to 2,000 characters."**, as the question form of milestone 11;
  the placeholder "Not answered" never replaces it. The milestone does not name a hint.
- **A save that does not name a question of the competition** (only a crafted form can omit one, since
  a competition's questions cannot change while it is **In progress**) leaves that question's stored
  answer as it is.
- **A save with nothing changed** is accepted and shows the notice.
- **The empty states have no hint**: the milestone gives none, and the teacher cannot fix either case
  from this page.
- **The phone card's progress line** carries the column's label: "Answered 3 of 6".
- **The back link of the answer sheet** carries the team answers page's page number, as the add pages
  of milestone 12.2 carry the list's page; when it is missing or invalid it leads to the page holding
  the team.
- **The team delete confirmation of milestones 11.1 and 12.2** keeps its wording ("The team will be
  hidden and taken out of every competition that has not finished. …"); the milestone does not ask to
  mention the answers.
- **Finished competitions** cannot be reached through any page yet (stopping comes in a later 12.x
  milestone); tests store them directly, with their teams and answers.
- **Tests control the current time**, so that a start can pass while a page is open.
- **Every quoted text above** is taken from the milestone where the milestone gives it; the texts it
  only implies (the error wording, the hint, the phone progress line) follow the existing patterns.

## Dependencies

- **Constitution v2.2.0** (merged in pull request #48): Principles IV–VII state that answers belong to
  a team, that **Write** access enters them and **Read** access sees only the progress, that answers are
  not under the logging ban, and that answers are entered only while the competition is **In
  progress**.
- **Product requirements** (updated with the milestone): the "Teacher access rights", "Personal data",
  "How a competition works", "Competition statuses" and **Team** sections.
- **Milestone 5**: roles, the current role, "access denied" and the automated route check.
- **Milestone 7**: regions and educational institutions and their deactivation.
- **Milestone 8**: teachers' links to institutions, **Read** and **Write** access, and **Can manage
  competitions**.
- **Milestone 10 and 10.1**: the component library, the gallery, the UI guidelines, the loading
  feedback and the busy button.
- **Milestone 11**: the 2,000-character limit, trimming, line breaks and the error wording; text cards
  and `textarea_field`.
- **Milestone 11.1**: teams, their active members, their deletion, and the "You are not linked to any
  educational institution" empty state.
- **Milestone 12.1**: competitions, their statuses, the actions menu, the local-time display, the
  status badge, the refusal pattern and the deactivated-subject rules.
- **Milestone 12.2**: a competition's questions (copied, in order) and teams, the **Teams** page and the
  region group, and taking a deleted team out of every competition that is not **Finished**.
- **Later milestones that depend on this one**: a later 12.x milestone adds grading the answers by hand
  and stopping a competition; milestone 13 lets a team's students enter the same answers; milestone 14
  evaluates them with an LLM; milestone 15 shows results with every team and its answers, deleted teams
  included.

## Out of Scope

- Grading answers by hand (a later 12.x milestone) and evaluation by an LLM (milestone 14).
- Stopping a competition (a later 12.x milestone).
- Students entering their team's answers (milestone 13).
- Results, best answers and places (milestone 15).
- Showing a team's answers to a teacher with **Read** access, or to a teacher not linked to its
  institution.
- Showing the reference answer on the answer sheet.
- Entering answers from the **Teams** page, or for a competition that is not **In progress**.
- Saving one answer at a time, saving automatically, or a "Saved" status per answer.
- Reserving a team's answers for a teacher, warning about another teacher's save, or refusing a save
  made over it.
- Storing who saved an answer or when, and keeping earlier versions of an answer.
- Page navigation on the answer sheet.
- Answer progress in the competitions list or on the **Teams** page.
