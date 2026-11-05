# Feature Specification: Questions and Teams of a Competition (Teacher) (Milestone 12.2)

**Feature Branch**: `012.2-competition-questions-teams`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: milestone 12.2 of `docs/requirements/milestones.md` ("Questions and
teams of a competition (teacher)"), part of the 12.x group "Competitions", with
`product-requirements.md` (the **Competition**, "Competition statuses", **Question**, **Team** and
**Subject** sections), the milestone 7, 10, 10.1, 11, 11.1 and 12.1 specifications and
`docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 12.2 of the walking skeleton for the Student Competitions application, and the second of
the 12.x milestones that build the teacher's side of competitions. After milestone 12.1, a
competition has a subject, a name and a start, and teachers with **Can manage competitions** create,
edit and cancel it, but it holds neither questions nor teams.

This milestone gives every competition two lists of its own: its **questions** and its **teams**.
Nine things become true when this milestone is done:

1. **Every row of the competitions list has an actions menu.** The menu of milestone 12.1 gains
   **Questions** and **Teams**, offered to every teacher on every listed competition in every status.
   The entries read, in this order, **Edit**, **Questions**, **Teams** and **Cancel competition**,
   each where it is available.
2. **Every teacher reads a competition's questions and teams.** Each opens on a page of its own,
   "Questions of “Spring round”" and "Teams of “Spring round”", with the competition's subject, start
   and status, and a back link to the exact competitions list the teacher came from.
3. **A competition holds copies of its questions.** A question is copied from the bank when it is
   added; editing or deleting it in the bank afterwards changes nothing in the competition. A copy
   whose bank question was deleted is marked "Deleted from the question bank".
4. **Teams are listed by region.** The competition's teams are grouped in region boxes, regions and
   teams sorted by name ignoring case, 10 teams per page, each region header naming the full number
   of its teams in the competition.
5. **Only a teacher with Can manage competitions changes the lists, and only while the competition is
   Upcoming.** They add questions of the competition's subject from "Add questions", add teams one
   region at a time from "Add teams", and remove either after a confirmation.
6. **Every change re-checks the status and is safe to repeat.** A change sent after the competition
   started, was cancelled or finished is refused; adding twice stores once, removing twice changes
   nothing, and reloading never repeats a change.
7. **Deleting a team takes it out of every competition that has not finished.** Only **Finished**
   competitions keep a deleted team, marked "(deleted)". Deleting a question from the bank never
   changes a competition, and deactivating an institution or a region takes no team out.
8. **The rules are written down.** The constitution, the product requirements and the UI guidelines
   are updated for the exception that deleting a team makes, the copied questions and the naming of
   menu entries.
9. **One new component, the region group**, is added to the component library, the component
   gallery (`/admin/components`) and the UI guidelines before any page uses it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher adds questions to an upcoming competition (Priority: P1)

Olena is a teacher with **Can manage competitions**. On the **Competitions** tab she opens the
**Actions** menu of the upcoming "Spring round" of "Chemistry" and chooses **Questions**. The page
"Questions of “Spring round”" shows "Chemistry", "14 March 2027, 10:00" and the badge **Upcoming**,
then "No questions in this competition yet" with the hint "Add questions with Add question.". She
presses **Add question**. The page "Add questions to “Spring round”" lists the questions of
"Chemistry" newest first, each in full with its number. She presses **Add** on question 12. She stays
on the same page, at question 12, which now shows "Already in this competition" with no **Add**
button, and the notice "Question 12 was added to “Spring round”". She adds questions 9 and 15 the same
way and follows the back link: the competition lists questions 12, 9 and 15, in the order she added
them.

**Why this priority**: A competition without questions cannot be taken in milestone 13; choosing
them is the core of this milestone.

**Independent Test**: As a teacher with the setting, add three questions to an upcoming competition
and check the add page, the notices, the "Already in this competition" marks and the order of the
competition's list.

**Acceptance Scenarios**:

1. **Given** Olena has the setting and the competition is **Upcoming**, **When** she opens its
   questions, **Then** **Add question** stands beside the page heading.
2. **Given** she presses **Add question**, **When** the page opens, **Then** its title is "Add
   questions to “Spring round”", it has a back link to the competition's questions, and it lists
   every question of the competition's subject that the question bank shows, with deleted questions
   left out, newest first, 10 per page, with the page navigation of **Questions** above and below,
   each question in full with its number.
3. **Given** a question is not yet in the competition, **When** it is listed, **Then** it has an
   **Add** button; **Given** it is already in the competition, **Then** it shows "Already in this
   competition" and no **Add** button.
4. **Given** she presses **Add** on question 12, **When** the question is added, **Then** its text
   and reference answer, as the bank shows them at that moment, are copied to the end of the
   competition's list, and she stays on the same page of "Add questions", at question 12, which shows
   "Already in this competition", with the notice "Question 12 was added to “Spring round”".
5. **Given** the page number of "Add questions", **When** the page is reloaded or bookmarked,
   **Then** it is kept in the page address and restored.
6. **Given** the subject's bank has no questions, **When** "Add questions" opens, **Then** it shows
   "No questions in this subject yet".

---

### User Story 2 - A teacher adds teams of a region (Priority: P1)

Olena opens **Teams** for "Spring round" and presses **Add team**. The page "Add teams to “Spring
round”" shows a **Region** list and "Select a region" with the hint "Choose a region in the list above
to see its teams.". She chooses "Kyiv"; its teams appear at once, sorted by name, "Teams 1–10 of 14",
from every institution in Kyiv, also those she is not linked to. Each row shows the team's name, its
institution and its number of active members. She presses **Add** on "Comets" of School No. 5. She
stays on "Kyiv", on the same page, at "Comets", which now shows "Already in this competition", with
the notice "Team “Comets” was added to “Spring round”". She also adds "Novas", which has no members
yet.

**Why this priority**: Teams are the participants of a competition; without them nobody can take it
in milestone 13.

**Independent Test**: As a teacher with the setting, add teams of two institutions the teacher is not
linked to, including one with no members, and check the region list, the team list, its order and
paging, the address, the notice and the marks.

**Acceptance Scenarios**:

1. **Given** Olena has the setting and the competition is **Upcoming**, **When** she opens its
   teams, **Then** **Add team** stands beside the page heading.
2. **Given** she presses **Add team**, **When** the page opens, **Then** its title is "Add teams to
   “Spring round”", it has a back link to the competition's teams, and a **Region** drop-down list
   above the list offers every active region, sorted by name ignoring case, with no "all regions"
   choice.
3. **Given** no region is chosen, **When** the page is shown, **Then** it shows "Select a region" with
   the hint "Choose a region in the list above to see its teams.".
4. **Given** she chooses a region, **When** it is chosen, **Then** its teams are shown at once with no
   button to press (and a **Show** button without JavaScript), and the first page opens.
5. **Given** a region is chosen, **When** its teams are listed, **Then** the list holds every team of
   that region that is not deleted and whose institution is active, from every institution of the
   region, whether or not she is linked to it, sorted by name ignoring case, 10 per page, with the
   page navigation ("Teams 1–10 of 14").
6. **Given** a listed team, **When** its row is shown, **Then** it shows the team's name, its
   institution, its number of active members, and either an **Add** button or "Already in this
   competition" with no **Add** button; the region is not repeated in the row.
7. **Given** she presses **Add** on "Comets", **When** the team is added, **Then** she stays on the
   same region and page, at "Comets", which shows "Already in this competition", with the notice
   "Team “Comets” was added to “Spring round”".
8. **Given** the region and the page, **When** the page is reloaded or bookmarked, **Then** they are
   kept in the page address and restored.
9. **Given** only one region is offered, **When** the page opens, **Then** it is chosen
   automatically; **Given** no region is offered, **Then** the page shows "No teams yet".
10. **Given** a chosen region has no team to list, **When** it is shown, **Then** the page shows "No
    teams in this region yet" with the hint "Choose another region.".
11. **Given** a team with no active members, or a team that shares a member with a team already in
    the competition, **When** she presses **Add**, **Then** it is added.

---

### User Story 3 - Every teacher reads a competition's questions (Priority: P1)

Mykola is a teacher without **Can manage competitions**. He opens the **Actions** menu of "Spring
round", which lists only **Questions** and **Teams**, and chooses **Questions**. The competition has 23
questions; he sees the first 10 in the order they were added, "Questions 1–10 of 23", each in full
with its bank number, text and reference answer, and moves to the second page. Since Olena added
question 12, another teacher changed its text in the bank, but the competition still shows the text
it was added with. He sees no **Add question** and no **Remove**. The back link takes him to the
competitions list he came from, at "Spring round".

**Why this priority**: Every teacher may read every competition (Principle IV), and the list is
where adding and removing start and return.

**Independent Test**: Seed a competition with 23 questions, edit and delete some of them in the bank,
and check the order, the paging, the copied texts, the marks and the back link, as teachers with and
without the setting.

**Acceptance Scenarios**:

1. **Given** a competition, **When** its **Questions** page opens, **Then** its title is "Questions
   of “Spring round”", and under the heading it shows the competition's subject, its start in the
   teacher's time zone (as in milestone 12.1) and its status badge.
2. **Given** a competition with 23 questions, **When** they are listed, **Then** they appear in the
   order they were added, the first added first, 10 per page, with the page navigation above and
   below ("Questions 11–20 of 23" on the second page), and the page number is kept in the address.
3. **Given** a listed question, **When** it is shown, **Then** it is shown in full, as in the question
   bank (milestone 11): its number in the bank, and its text and reference answer as they were copied
   when it was added.
4. **Given** a question was edited in the bank after it was added, **When** the competition's list is
   shown, **Then** it still shows the copied text and reference answer.
5. **Given** a question was deleted from the bank after it was added, **When** the list is shown in
   any status, **Then** the question is still listed, marked "Deleted from the question bank".
6. **Given** a competition with no questions, **When** the list is shown, **Then** it shows "No
   questions in this competition yet", with the hint "Add questions with Add question." for a teacher
   who can make changes and no hint for anyone else.
7. **Given** the back link, **When** it is followed, **Then** it leads to the competitions list the
   teacher came from (same subject, status and page), at the competition.

---

### User Story 4 - Every teacher reads a competition's teams, grouped by region (Priority: P1)

"Spring round" has 25 teams from three regions: "Dnipro" (4), "Kyiv" (14) and "Lviv" (7). On the
first page Mykola sees a box "Dnipro · 4 teams" with its 4 teams and a box "Kyiv · 14 teams" with the
first 6 Kyiv teams. The second page starts with "Kyiv · 14 teams" again and its next 8 teams, followed
by "Lviv · 7 teams" with its first 2. Each row shows the team's name, its institution and its number
of active members; no member names are shown.

**Why this priority**: Teachers need to see who takes part, and with hundreds of teams the region
grouping keeps the list readable.

**Independent Test**: Seed a competition with 25 teams from three regions, one region spanning a page
break, and check the grouping, the order, the headers and counts on both pages, the rows, and the
phone layout.

**Acceptance Scenarios**:

1. **Given** a competition, **When** its **Teams** page opens, **Then** its title is "Teams of
   “Spring round”", with the subject, start and status badge under the heading, and the same back
   link as the questions page.
2. **Given** teams of several regions, **When** they are listed, **Then** the regions are sorted by
   name ignoring case, and within each region its teams are sorted by name ignoring case.
3. **Given** 25 teams, **When** they are listed, **Then** the list shows 10 teams per page with the
   page navigation ("Teams 1–10 of 25"), and a page may hold teams of several regions.
4. **Given** a region on a page, **When** it is shown, **Then** it is a box with a header and a data
   table of its teams on that page (labelled cards on a phone). The header shows the region's name as
   it is stored, with no word added, and how many of its teams the competition holds across all
   pages ("Kyiv · 14 teams", "Kyiv · 1 team" for one).
5. **Given** a region whose teams continue from the previous page, **When** the later page is shown,
   **Then** it shows the same header again, with the same count.
6. **Given** a team row, **When** it is shown, **Then** it shows the team's name, its educational
   institution and its number of active members (milestone 11.1); the region is shown only in the
   header, and members' names are not shown.
7. **Given** a team whose institution or region was deactivated, **When** the list is shown, **Then**
   the team is still listed.
8. **Given** a **Finished** competition holding a deleted team, **When** its list is shown, **Then**
   the team is listed and marked "(deleted)".
9. **Given** a competition with no teams, **When** the list is shown, **Then** it shows "No teams in
   this competition yet", with the hint "Add teams with Add team." for a teacher who can make changes
   and no hint for anyone else.

---

### User Story 5 - A teacher removes a question or a team (Priority: P1)

Olena opens **Remove** on question 12 of "Spring round". The page asks "Remove question 12 from
“Spring round”?" and explains "The question stays in the question bank and can be added again." She
presses the destructive **Remove**. She is back on the same page of the competition's questions, at
the question that took its place, with the notice "Question 12 was removed from “Spring round”".
Later she removes "Comets": "Remove team “Comets” of School No. 5, Kyiv from “Spring round”? The team
and its members are not changed, and the team can be added again."

**Why this priority**: Plans change before a competition starts; a wrong question or team must be
taken out as easily as it was put in.

**Independent Test**: Remove a question, a question deleted from the bank and a team after the
confirmation, use **Cancel**, and remove the last item of a page; check the texts, the notices, the
landing position and that the bank, the team and its members are unchanged.

**Acceptance Scenarios**:

1. **Given** a teacher who can make changes, **When** the competition's lists are shown, **Then**
   every question and every team has **Remove**.
2. **Given** **Remove** on question 12, **When** the confirmation opens, **Then** it reads "Remove
   question 12 from “Spring round”?" and "The question stays in the question bank and can be added
   again.".
3. **Given** **Remove** on a question deleted from the bank, **When** the confirmation opens, **Then**
   the second sentence reads "The question was deleted from the question bank and cannot be added
   again.".
4. **Given** **Remove** on "Comets", **When** the confirmation opens, **Then** it reads "Remove team
   “Comets” of School No. 5, Kyiv from “Spring round”?" (the institution, then the region's name as it
   is stored) and "The team and its members are not changed, and the team can be added again.".
5. **Given** the confirmation, **When** **Cancel** is pressed, **Then** the teacher returns to the
   page they came from, at that question or team, with nothing changed.
6. **Given** the destructive **Remove** is pressed, **When** the removal is stored, **Then** the
   teacher returns to the same page of the competition's list with the notice "Question 12 was
   removed from “Spring round”" (or "Team “Comets” was removed from “Spring round”"), at the row that
   took its place, or on the previous page if that page is now empty, as after deleting a question
   (milestone 11).
7. **Given** a question was removed, **When** the bank is shown, **Then** it is still there,
   unchanged; **Given** a team was removed, **Then** the team and its members are unchanged.
8. **Given** a question deleted from the bank was removed, **When** "Add questions" is shown, **Then**
   it is not offered, so it cannot be added again.
9. **Given** a removed question that is still in the bank is added again, **When** the competition's
   list is shown, **Then** it is at the end, with the bank's current text.

---

### User Story 6 - Every row has a menu with the competition's lists (Priority: P1)

Mykola, without the setting, opens **Competitions** and chooses the status **All**: every row now has
an **Actions** menu, each with only **Questions** and **Teams**. Olena, with the setting, sees
**Edit**, **Questions**, **Teams** and **Cancel competition** on an upcoming competition, **Questions**,
**Teams** and **Cancel competition** on one in progress, and only **Questions** and **Teams** on a
finished or cancelled one.

**Why this priority**: The menu is the only way into the new pages; it also replaces a 12.1 rule.

**Independent Test**: List competitions of every status, including a finished one of a deactivated
subject, as teachers with and without the setting, and check each menu's entries and their order.

**Acceptance Scenarios**:

1. **Given** a teacher with the setting, **When** an **Upcoming** competition's menu opens, **Then** it
   lists **Edit**, **Questions**, **Teams** and **Cancel competition**, in this order.
2. **Given** a teacher with the setting, **When** an **In progress** competition's menu opens,
   **Then** it lists **Questions**, **Teams** and **Cancel competition**.
3. **Given** any teacher, **When** the menu of a **Finished** or **Cancelled** competition opens,
   **Then** it lists only **Questions** and **Teams**.
4. **Given** a teacher without the setting, **When** any competition's menu opens, **Then** it lists
   only **Questions** and **Teams**.
5. **Given** a finished competition of a deactivated subject, **When** its row is shown, **Then** it
   has a menu with only **Questions** and **Teams**.
6. **Given** **Questions** or **Teams** is chosen, **When** the page opens, **Then** it is the
   competition's questions or teams page, and the competitions list's subject, status and page are
   kept for the way back.

---

### User Story 7 - Changes stop when the competition leaves Upcoming (Priority: P1)

At 09:58 Olena opens "Add questions" for "Spring round", which starts at 10:00. At 10:01 she presses
**Add**: nothing is stored, and the page "Change the questions of “Spring round”?" says "“Spring
round” has already started and its questions can no longer be changed." with the link **Back to the
competition**, which leads to its questions. From now on its lists are read-only for every teacher.
Meanwhile two teachers press **Add** on "Comets" for another competition at the same moment; the team
is stored once, and one of them sees "Team “Comets” is already in “Autumn round”".

**Why this priority**: Questions and teams decide what students answer and who answers in milestone
13; changes after the start would break the competition.

**Independent Test**: With the current time controlled by the test, let a start pass while add and
remove pages are open, cancel a competition, store a finished one directly, and send repeated and
concurrent additions and removals; check the refusals, the notices and that nothing else changes.

**Acceptance Scenarios**:

1. **Given** a competition that is **In progress**, **Finished** or **Cancelled**, **When** any
   teacher views its lists, **Then** they show no **Add question**, **Add team** or **Remove**.
2. **Given** a competition that is no longer **Upcoming**, **When** "Add questions", "Add teams" or a
   remove confirmation is opened, or an addition or a removal is sent, **Then** nothing changes and
   the refusal "Change the questions of “Spring round”?" (or "Change the teams of “Spring round”?")
   is shown with the reason "“Spring round” has already started and its questions can no longer be
   changed." (or "… its teams can no longer be changed."), and the link **Back to the competition**
   to its questions or teams page.
3. **Given** a cancelled or finished competition, **When** the same is tried, **Then** the reason
   reads "“Spring round” has been cancelled and its questions (teams) can no longer be changed." or
   "“Spring round” has finished and its questions (teams) can no longer be changed.".
4. **Given** a question or team already in the competition, **When** it is added again (by sending
   the form twice, or by two teachers at once), **Then** it is stored once and the teacher returns
   with the notice "Question 12 is already in “Spring round”" (or "Team “Comets” is already in
   “Spring round”").
5. **Given** a question or team no longer in the competition, **When** its removal is sent (again, or
   by two teachers at once), **Then** nothing changes and the teacher returns with the notice
   "Question 12 is not in “Spring round”" (or "Team “Comets” is not in “Spring round”").
6. **Given** any successful change, **When** the result page is reloaded, **Then** the change is not
   repeated.

---

### User Story 8 - Deleting a team or a question elsewhere (Priority: P1)

Taras, a teacher with **Write** access but without **Can manage competitions**, deletes the team
"Comets" on the **Teams** tab. The confirmation now reads "… The team will be hidden and taken out of
every competition that has not finished. It can no longer join new competitions. …". After he
confirms, "Comets" is gone from the upcoming "Spring round", the in-progress "Winter round" and the
cancelled "Autumn round", but the finished "Summer round" still lists it, marked "(deleted)". Olena
deletes question 12 from the bank: "Spring round" keeps its copy, marked "Deleted from the question
bank".

**Why this priority**: Deleted teams must not take part in a competition, while finished competitions
must keep their complete record for the results of milestone 15.

**Independent Test**: Put a team in an upcoming, an in-progress, a cancelled and a finished
competition (the last two stored directly by the test), delete it, and check each competition; delete
a question that is in a competition and check the copy and the add page; deactivate an institution and
a region and check that their teams stay.

**Acceptance Scenarios**:

1. **Given** a team in an **Upcoming**, an **In progress** and a **Cancelled** competition, **When** a
   teacher with **Write** access deletes it (milestone 11.1), with or without **Can manage
   competitions**, **Then** it is taken out of all three as part of the deletion.
2. **Given** a team in a **Finished** competition, **When** it is deleted, **Then** the finished
   competition keeps it, marked "(deleted)".
3. **Given** the team delete confirmation of milestone 11.1, **When** it is shown, **Then** "The team
   will be hidden and can no longer join new competitions." reads "The team will be hidden and taken
   out of every competition that has not finished. It can no longer join new competitions.", with the
   rest unchanged.
4. **Given** a deleted team, **When** "Add teams" is shown, **Then** it is not listed, and adding it
   through a crafted form shows "not found".
5. **Given** a question in a competition, **When** it is deleted from the bank, **Then** the
   competition keeps its copy, marked "Deleted from the question bank", the question is no longer
   offered on "Add questions" of any competition, and the milestone 11 delete confirmation keeps its
   wording ("can no longer be added to new competitions").
6. **Given** a team in a competition, **When** its institution or its region is deactivated, **Then**
   the team stays in the competition.
7. **Given** a team is deleted while it is being added to a competition, **When** both are processed,
   **Then** the team does not end up in any competition that is not **Finished**.

---

### User Story 9 - Only teachers read, and only managers change (Priority: P1)

Mykola, without the setting, types the address of "Add questions" and sends a hand-made removal: each
gets "access denied", before any competition, question or team id is read. An administrator and a
student who type the address of a competition's questions get "access denied". Olena changes the team
id in an addition to a team of another region than the one in the address and gets "not found".

**Why this priority**: Questions and teams decide what students answer and who answers; a missing
check would let anyone change a competition.

**Independent Test**: For every page and action of this milestone, send requests as each role and as
teachers with and without the setting, including typed-in addresses and crafted forms for unknown,
mismatched and hidden competitions, regions, questions and teams, and check the result and the check
order.

**Acceptance Scenarios**:

1. **Given** a person in the administrator or student role, **When** they open any page or send any
   action of this milestone, also through a typed address or a crafted form, **Then** they get
   "access denied".
2. **Given** a teacher without the setting, **When** they open an add page or a remove confirmation,
   or send an addition or a removal, **Then** they get "access denied" before any id is read, even
   for unknown ids.
3. **Given** any teacher, **When** the address names an unknown subject or competition, a competition
   of another subject, or one hidden because its subject is deactivated, **Then** they get "not
   found".
4. **Given** "Add teams", **When** the address names an unknown or deactivated region, **Then** the
   page shows "not found".
5. **Given** an addition, **When** it names an unknown question, one of another subject, or one
   deleted from the bank or hidden, **Then** it shows "not found" and nothing changes.
6. **Given** an addition, **When** it names an unknown or deleted team, one of another region than
   the one in the address, or one whose institution or region is deactivated, **Then** it shows "not
   found" and nothing changes.
7. **Given** a removal, **When** it names a question or a team that is in the competition, **Then** it
   passes this check, even for a question deleted from the bank.
8. **Given** checks fail at several levels, **When** a request is handled, **Then** the first failing
   check in the order role, setting, subject and competition, status, region / question / team decides
   the answer.
9. **Given** any change, **When** it is sent without a valid cross-site request token, **Then** it is
   refused and nothing changes.

---

### User Story 10 - Deactivated subjects (Priority: P2)

An administrator deactivates "Chemistry". The questions and teams pages of its upcoming "Spring
round", and every add and remove page and action for it, now show "not found". Its finished "Summer
round" is still listed (milestone 12.1); its menu offers **Questions** and **Teams**, and both lists
are shown read-only, including questions the bank now hides because "Chemistry" is deactivated.

**Why this priority**: It extends the 12.1 deactivation rules to the new pages; the risk is small,
but the rule must hold from the first question added.

**Independent Test**: With a finished competition stored directly by the test, deactivate its subject
and check both lists of the finished competition and "not found" on every page and action of an
upcoming one.

**Acceptance Scenarios**:

1. **Given** a competition of a deactivated subject that is not **Finished**, **When** its questions
   or teams page, or any add or remove page or action for it, is opened or sent, **Then** it shows
   "not found".
2. **Given** a finished competition of a deactivated subject, **When** its questions and teams are
   opened, **Then** they are shown read-only, including questions the bank hides because their
   subject is deactivated.

---

### User Story 11 - The region group and the changed rules are written first (Priority: P3)

An administrator opens `/admin/components` outside production and finds the region group: a box with a
region header ("Kyiv · 14 teams") over a data table, also with a "1 team" header and as cards on a
phone. The UI guidelines describe it, and their "Menus" wording pattern now says how entries are
named. The constitution and the product requirements describe the team-deletion exception and the
copied questions.

**Why this priority**: It follows the project rule that pages use only library components and that
documents match the product; it adds no capability of its own.

**Independent Test**: Open the gallery, the guidelines, the product requirements and the constitution
and check each change.

**Acceptance Scenarios**:

1. **Given** the gallery, **When** it is opened, **Then** the region group is shown with a plural
   count, a "1 team" count and a long region name, and as labelled cards at phone width.
2. **Given** the UI guidelines' "Menus" wording pattern, **When** it is read, **Then** it says that an
   entry that does something is a verb (**Edit**, **Cancel competition**), an entry that only opens a
   page is named by that page (**Questions**, **Teams**), and a destructive entry is always a verb.
3. **Given** the product requirements and the constitution, **When** they are read, **Then** they
   state the rules listed under FR-051.

---

### Edge Cases

- **The competition starts while "Add questions" is open**: the next **Add** shows the "has already
  started" refusal and stores nothing; reopening the questions page shows it read-only.
- **The competition is cancelled while a remove confirmation is open**: confirming shows the "has
  been cancelled" refusal and changes nothing.
- **A teacher loses Can manage competitions while an add page is open**: the next **Add** gets "access
  denied" and stores nothing.
- **The subject is deactivated while an add page is open**: the next **Add** for a competition that is
  not finished gets "not found".
- **A question is edited in the bank while "Add questions" is open**: **Add** copies the text the bank
  holds at the moment the addition is stored, not the text shown on the open page.
- **A question is deleted from the bank while "Add questions" is open**: a later **Add** of it gets
  "not found"; if the addition was stored first, the competition keeps the copy, marked "Deleted from
  the question bank".
- **A team's institution or region is deactivated while "Add teams" is open**: a later **Add** of it
  gets "not found"; a deactivated region in the address shows "not found" on reload.
- **A team is renamed or moves members after it was added**: the competition shows the team's current
  name and its current number of active members; only questions are copied.
- **A team is deleted while "Add teams" shows it**: a later **Add** of it gets "not found".
- **Removing the only question or team of the last page**: the teacher lands on the previous page at
  its last row; removing the very last one shows the empty state with its hint.
- **A region spans a page break and a team is removed from it**: the header on both pages shows the
  new count.
- **A page number beyond the last page, or not a number**, on any list of this milestone: the list
  opens on the nearest valid page, as on **Questions**.
- **The competitions-list context in the address is missing or invalid**: the back link leads to the
  competitions list with the competition's subject, the status **All** and the page holding the
  competition.
- **Very long competition, team, institution or region names, and long question texts**: they wrap
  within the content width on every screen size, with no sideways page scroll, in the headings,
  region headers, rows, cards, confirmations, refusals and notices.
- **Pressing Add twice (double press)**: the form cannot be sent again until the next page arrives
  (milestone 10.1); a second request arriving anyway stores nothing and shows the "already in"
  notice.
- **A finished competition with only deleted teams**: its teams page lists them, all marked
  "(deleted)", grouped by region as usual.

## Requirements *(mandatory)*

### Functional Requirements

#### Row actions

- **FR-001**: The actions menu of milestone 12.1 MUST gain the entries **Questions** and **Teams**.
  The menu MUST list, in this order, **Edit**, **Questions**, **Teams** and **Cancel competition**,
  each only where it is available.
- **FR-002**: **Questions** and **Teams** MUST be offered to every teacher, with or without **Can
  manage competitions**, on every competition the list shows, in every status, including the finished
  competitions of a deactivated subject. Every row MUST therefore have a menu. This replaces the 12.1
  rule that **Finished** and **Cancelled** competitions, and the finished competitions of a
  deactivated subject, show no menu; **Edit** and **Cancel competition** keep their 12.1 rules.

#### The competition's pages

- **FR-003**: **Questions** and **Teams** MUST each open a page of their own, titled "Questions of
  “…”" and "Teams of “…”" with the competition's name. Under the heading each page MUST show the
  competition's subject, its start in the teacher's time zone (as in milestone 12.1) and its status
  badge.
- **FR-004**: Each page MUST have a back link to the competitions list the teacher came from (same
  subject, status and page), at the competition. That subject, status and page MUST be carried through
  every page and action of this milestone (the add pages, the confirmations, the refusals and the
  notices), so the back link always leads to the same list. The page number of every list of this
  milestone MUST be kept in the page address.

#### Questions of a competition

- **FR-005**: A competition's questions MUST be listed in the order they were added, the first added
  first, 10 per page, with the page navigation of **Questions** above and below ("Questions 11–20 of
  23").
- **FR-006**: Each question MUST be shown in full, as in the question bank (milestone 11): its number
  in the bank, and its text and reference answer as they were copied when it was added.
- **FR-007**: Adding a question MUST copy its text and reference answer into the competition. Editing
  the question in the bank afterwards MUST change nothing in the competition; a teacher who wants the
  new text removes the question and adds it again.
- **FR-008**: A question deleted from the bank after it was added MUST stay in the competition, in
  every status, and MUST be marked "Deleted from the question bank".
- **FR-009**: A competition with no questions MUST show "No questions in this competition yet", with
  the hint "Add questions with Add question." for a teacher who can make changes (FR-015) and no hint
  for anyone else.

#### Teams of a competition

- **FR-010**: A competition's teams MUST be grouped by region: the regions sorted by name ignoring
  case, and within each region its teams sorted by name ignoring case. The list MUST show 10 teams per
  page with the same page navigation ("Teams 1–10 of 14"), and a page MAY hold teams of several
  regions.
- **FR-011**: Each region on a page MUST be a box with a header and a data table of its teams on that
  page (labelled cards on a phone). The header MUST show the region's name as it is stored, with no
  word added, and how many of its teams the competition holds across all pages ("Kyiv · 14 teams";
  "1 team" for one). A region whose teams continue from the previous page MUST show the same header
  again, with the same count.
- **FR-012**: Each row MUST show the team's name, its educational institution and its number of
  active members (milestone 11.1). The region MUST be shown only in the header. Members' names MUST
  NOT be shown.
- **FR-013**: A team MUST stay in a competition when its institution or region is deactivated. Only a
  **Finished** competition can hold a deleted team (FR-040), and there the team MUST be marked
  "(deleted)".
- **FR-014**: A competition with no teams MUST show "No teams in this competition yet", with the hint
  "Add teams with Add team." for a teacher who can make changes and no hint for anyone else.

#### Who can make changes

- **FR-015**: Only a teacher with **Can manage competitions** MUST be able to change a competition's
  questions and teams, and only while the competition is **Upcoming**. For such a teacher the
  questions page MUST show **Add question** beside the page heading and **Remove** on every question,
  and the teams page MUST show **Add team** beside the heading and **Remove** on every team. Every
  other teacher, and every teacher looking at an **In progress**, **Finished** or **Cancelled**
  competition, MUST see the same lists with no **Add question**, **Add team** or **Remove**.

#### Adding questions

- **FR-016**: **Add question** MUST open the page "Add questions to “…”", with a back link to the
  competition's questions. It MUST list every question of the competition's subject that the question
  bank shows (deleted questions left out), newest first, as in the bank, 10 per page with the same
  page navigation, each shown in full with its number.
- **FR-017**: Each question not yet in the competition MUST have an **Add** button. A question already
  in the competition MUST show "Already in this competition" instead, with no **Add** button.
- **FR-018**: **Add** MUST copy that one question, with its text and reference answer as the bank
  holds them at that moment, to the end of the competition's list. The teacher MUST stay on the same
  page of "Add questions", at that question, which now shows "Already in this competition", with the
  notice "Question 12 was added to “…”".
- **FR-019**: A subject whose bank has no questions MUST show "No questions in this subject yet".

#### Adding teams

- **FR-020**: **Add team** MUST open the page "Add teams to “…”", with a back link to the
  competition's teams. The teacher MUST choose one region and add its teams one at a time.
- **FR-021**: A **Region** drop-down list above the list (the chained-list selector, as for the
  subject on **Competitions**) MUST offer every active region, sorted by name ignoring case, with no
  "all regions" choice. Choosing a region MUST show its teams at once, with no button to press (and a
  **Show** button without JavaScript).
- **FR-022**: Until a region is chosen, the page MUST show "Select a region" with the hint "Choose a
  region in the list above to see its teams.". When only one region is offered it MUST be chosen
  automatically. When no region is offered the page MUST show "No teams yet".
- **FR-023**: The list MUST hold every team of the chosen region that is not deleted and whose
  educational institution is active, from every institution of that region, whether or not the
  teacher is linked to it, sorted by name ignoring case, 10 per page, with the same page navigation. A
  region with no team to list MUST show "No teams in this region yet" with the hint "Choose another
  region.".
- **FR-024**: The region and the page MUST be kept in the page address. Choosing another region MUST
  open the first page. An unknown or deactivated region in the address MUST show "not found".
- **FR-025**: Each row MUST show the team's name, its institution, its number of active members, and
  either an **Add** button or "Already in this competition" with no **Add** button. The region MUST
  NOT be repeated in the rows.
- **FR-026**: **Add** MUST add that one team. The teacher MUST stay on the same region and page of
  "Add teams", at that team, which now shows "Already in this competition", with the notice "Team
  “Comets” was added to “…”".
- **FR-027**: A team with no active members MUST be addable. A student MAY be a member of several
  teams in the same competition; nothing MUST check this.
- **FR-028**: Every notice of this milestone MUST identify a team by its name alone, which is unique
  among the teams that are not deleted (milestone 11.1).

#### Removing

- **FR-029**: **Remove** MUST open a confirmation page, like cancelling a competition (milestone
  12.1). For a question it MUST read "Remove question 12 from “…”?" and then "The question stays in
  the question bank and can be added again."; for a question deleted from the bank the second sentence
  MUST be "The question was deleted from the question bank and cannot be added again.".
- **FR-030**: For a team it MUST read "Remove team “Comets” of School No. 5, Kyiv from “…”?" (the
  institution, then the region's name as it is stored) and then "The team and its members are not
  changed, and the team can be added again.".
- **FR-031**: The destructive **Remove** button MUST confirm the removal. **Cancel** MUST return to
  the page the teacher came from, at that question or team, with nothing changed.
- **FR-032**: After removing, the teacher MUST return to the same page of the competition's list with
  the notice "Question 12 was removed from “…”" (or "Team “Comets” was removed from “…”"), at the row
  that took its place, or on the previous page if that page is now empty, as after deleting a question
  (milestone 11): at the row before it on that page if no row took its place, and on the empty state
  if no row is left.
- **FR-033**: Removing a question MUST leave it in the bank, and removing a team MUST leave the team
  and its members unchanged. A question deleted from the bank MUST be removable like any other, and
  once removed it cannot be added again, because it is no longer offered.

#### Refusals and concurrency

- **FR-034**: Every add and remove page and action MUST check the status again when it is opened or
  sent. When the competition is no longer **Upcoming**, it MUST change nothing and show a refusal in
  the 12.1 pattern: "Change the questions of “…”?" (or "Change the teams of “…”?") with the reason
  "“…” has already started and its questions can no longer be changed." (or "… its teams can no longer
  be changed."), and variants for a cancelled competition ("has been cancelled") and a finished one
  ("has finished"). The link **Back to the competition** MUST lead to its questions or teams page.
- **FR-035**: Adding a question or team that is already in the competition, also by sending the form
  twice or by two teachers at once, MUST store it once and return with the notice "Question 12 is
  already in “…”" (or "Team “Comets” is already in “…”").
- **FR-036**: Removing a question or team that is no longer in the competition, also under
  concurrency, MUST change nothing and return with the notice "Question 12 is not in “…”" (or "Team
  “Comets” is not in “…”").
- **FR-037**: A team that is deleted while it is being added to a competition MUST never end up in a
  competition that is not **Finished**.
- **FR-038**: Reloading a page after any change MUST never repeat it.

#### Deleting and deactivating elsewhere

- **FR-039**: Deleting a question from the bank (milestone 11) MUST never change a competition: the
  competition keeps its copy, marked as in FR-008, and the question can no longer be added to any
  competition. The wording of the milestone 11 delete confirmation ("can no longer be added to new
  competitions") MUST stay as it is.
- **FR-040**: Deleting a team (milestone 11.1) MUST take it out of every competition that is not
  **Finished** (**Upcoming**, **In progress** and **Cancelled**), as part of the deletion done by the
  teacher with **Write** access who deletes the team, whether or not they have **Can manage
  competitions**. A deleted team MUST NOT take part in any competition or be added to one.
  **Finished** competitions MUST keep it, marked "(deleted)", so their record stays complete.
- **FR-041**: The 11.1 team delete confirmation MUST change "The team will be hidden and can no longer
  join new competitions." to "The team will be hidden and taken out of every competition that has not
  finished. It can no longer join new competitions.", with the rest unchanged.
- **FR-042**: Deactivating an institution or a region MUST never take its teams out of competitions.

#### Deactivated subjects

- **FR-043**: For a competition of a deactivated subject that is not **Finished**, the questions and
  teams pages and every add and remove page and action MUST show "not found". The finished
  competitions of a deactivated subject MUST show their questions and teams read-only, including
  questions the bank now hides because their subject is deactivated.

#### Access

- **FR-044**: Administrators and students MUST get "access denied" on every page and action of this
  milestone, also through the page address or a submitted form.
- **FR-045**: Checks MUST run in this order, and the first failing one MUST decide the answer:
  1. the role: anyone who is not a teacher gets "access denied";
  2. the setting, for the add and remove pages and actions: a teacher without **Can manage
     competitions** gets "access denied", before any id is read;
  3. the subject and the competition, as in milestone 12.1: an unknown one, a mismatched one, or one
     hidden because its subject is deactivated, shows "not found";
  4. the status, for the add and remove pages and actions: the refusals of FR-034;
  5. the region, the question or the team, which show "not found": on "Add teams", an unknown or
     deactivated region in the address; when being added, an unknown question, one of another
     subject, or one deleted from the bank or hidden, and an unknown or deleted team, one of another
     region than the one in the address, or one whose institution or region is deactivated. When
     being removed, a question or team only has to be in the competition, so a question deleted from
     the bank can still be removed.
- **FR-046**: Access MUST be checked on every request against the current role, setting, subject,
  competition and status, whatever the page showed, and again when the change is stored.

#### Shared page and action behaviour

- **FR-047**: Every change MUST be a form submission that passes the existing cross-site request
  check. Opening a page or following a link MUST never change anything.
- **FR-048**: No log line MUST contain an email address, a person's name, a competition name, a team
  name or question text.
- **FR-049**: Every page of this milestone MUST follow the UI guidelines, including the loading
  feedback and busy button of milestone 10.1, and MUST work on a phone-width screen without sideways
  page scrolling.

#### Components

- **FR-050**: The pages MUST be built from existing components: the section heading with actions,
  text cards for questions, data tables, page navigation, the chained-list selector (for the region
  on "Add teams"), `row_note` (for "Already in this competition" and the deleted marks), notices,
  empty states with a hint, confirmations, refusals, back links, the local-time display, the
  competition status badge and the actions menu. One component MUST be new: the **region group**, a
  box with the region header over a data table. Any new component or variant MUST be added to the
  component library, the component gallery (`/admin/components`) and the UI guidelines first, and
  only then used.

#### Rules this milestone changes

- **FR-051**: These documents MUST be updated to match:
  - the constitution (Principle IV) and the product requirements ("Competition statuses", "Team"):
    deleting a team is the one exception to "only an upcoming competition can be edited" and "a
    cancelled competition never changes again", because it takes the team out of every competition
    that is not finished; a deleted team stays only in finished competitions. The constitution
    amendment MUST be made with `/speckit-constitution` in its own pull request before this
    milestone's plan;
  - the product requirements ("Question"): a competition holds a copy of each of its questions, taken
    when the question is added, so editing or deleting the question in the bank does not change the
    competition;
  - the UI guidelines ("Menus" in the wording patterns): "the entries are verbs, as buttons are"
    becomes "an entry that does something is a verb (**Edit**, **Cancel competition**); an entry that
    only opens a page is named by that page (**Questions**, **Teams**); a destructive entry is always
    a verb".

#### Verification and scope

- **FR-052**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" list: the menu entries and their order per status and setting; adding three
  questions, their order, the marks on "Add questions", 10 per page with 25 questions, the copy
  surviving a bank edit, removing and adding again, removing and **Cancel**; adding teams of two
  unlinked institutions including one with no members, the **Region** list and its order, nothing
  listed before a region is chosen, the region and page in the address, deleted teams and teams of
  deactivated institutions not listed, a deactivated region not offered, 25 teams from three regions
  with one spanning a page break and its repeated header count, removing a team, a team sharing a
  member; read-only lists and "access denied" for a teacher without the setting; the start passing
  with an open add page or remove confirmation, and cancelled and finished competitions (the latter
  stored directly by the test); a question deleted from the bank, team deletion across the four
  statuses and its confirmation text, deactivated institutions and regions, and both kinds of
  competition of a deactivated subject; repeated and concurrent additions and removals, a team deleted
  while being added, and reloads; and access per role, setting and id.
- **FR-053**: This milestone MUST NOT add changing the order of a competition's questions, updating a
  competition's copy of a question when the bank changes, limits on the number of questions or teams
  in a competition, checking that a student is in only one team of a competition, question or team
  counts in the competitions list, filtering "Add questions", searching "Add questions" or "Add
  teams", an "all regions" choice on "Add teams", stopping a competition, the student's view
  (milestone 13) or results (milestone 15).

### Key Entities *(include if feature involves data)*

- **Competition question** (new): a question as one competition holds it. It belongs to one
  competition and refers to the bank question it was copied from (for its number, the "Deleted from
  the question bank" mark and the "Already in this competition" check). It holds the text and
  reference answer copied when it was added, and its place in the order of adding. A competition holds
  each bank question at most once. It is not personal data.
- **Competition team** (new): the fact that a team takes part in a competition. It belongs to one
  competition and one team; a competition holds each team at most once. The team's name, institution,
  region and member count are read from the team, not copied. It names a team, not its members, and is
  not personal data.
- **Competition** (existing, milestone 12.1): now has its questions and its teams, changeable only
  while **Upcoming**, except that deleting a team takes it out of every competition that is not
  **Finished**.
- **Question** (existing, milestone 11): editing or deleting it never changes a competition's copy; a
  deleted question can no longer be added.
- **Team** (existing, milestone 11.1): deleting it now also takes it out of every competition that is
  not **Finished**.
- **Region** and **Educational institution** (existing, milestone 7): group the teams of a competition
  and of "Add teams"; deactivating them takes no team out of a competition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A teacher with **Can manage competitions** can add 5 questions and 3 teams of one region
  to a new competition in under 3 minutes.
- **SC-002**: 100% of a competition's questions show the text and reference answer they were added
  with, after any number of edits or a deletion in the bank.
- **SC-003**: In the automated access check, 100% of pages and actions of this milestone refuse the
  administrator and student roles, 100% of add and remove pages and actions refuse teachers without
  the setting before any id is read, and 100% of requests naming an unknown, mismatched or hidden
  competition, region, question or team get "not found" with nothing changed.
- **SC-004**: 0 competitions hold the same question or team twice, and 0 questions or teams change in
  a competition that is not **Upcoming** through this milestone's pages, including under repeated and
  concurrent requests.
- **SC-005**: After a team is deleted, 0 competitions that are not **Finished** hold it, including when
  the deletion and an addition happen at once, and 100% of **Finished** competitions that held it
  still list it, marked "(deleted)".
- **SC-006**: After 100% of the additions, removals, uses of **Cancel**, refusals and back links
  covered by the tests, the teacher lands on the competition, list, region, page and row this
  specification names, and the way back leads to the competitions list they came from.
- **SC-007**: Every page of this milestone is usable at 360 px width with no sideways page scrolling.
- **SC-008**: Reloading the page after any successful change never repeats it.
- **SC-009**: All tests from milestones 1–12.1 still pass, apart from those of the two rules this
  milestone changes: rows of finished and cancelled competitions with no menu (milestone 12.1) and the
  wording of the team delete confirmation (milestone 11.1).

## Assumptions

- **The back link of "Add questions" and "Add teams"** leads to the competition's questions or teams
  page the teacher came from (its page number carried along, as the competitions-list context is),
  rather than always to the first page. The milestone says only "a back link to the competition's
  questions" (or teams).
- **Teams are not copied**: the competition's teams list shows each team's current name,
  institution, region and number of active members; the milestone copies only questions.
- **"Number of active members"** is the count defined in milestone 11.1, not counting blocked members.
- **A question deleted from the bank at the same moment it is added** ends in one of two consistent
  states: the addition is stored first and the competition keeps a copy marked "Deleted from the
  question bank", or the deletion is first and the addition gets "not found".
- **Finished competitions** cannot be reached through any page yet (stopping comes in a later 12.x
  milestone); tests store them directly, with their questions and teams.
- **Tests control the current time**, so that a start can pass while an add page is open.
- **Page numbers out of range or not a number** on any list of this milestone fall back to the nearest
  valid page, as on **Questions**.
- **A missing or invalid competitions-list context** in the address falls back to the competition's
  subject, the status **All** and the page that holds the competition.
- **The refusal page** uses the existing 12.1 refusal pattern (a title as a question, a reason and a
  link back), with the link reading **Back to the competition**.
- **The "already in" and "is not in" notices** use the notice component's information style; the
  "was added" and "was removed" notices its success style, as in milestone 11.1.
- **Every quoted text above** is taken from the milestone where the milestone gives it; the texts
  the milestone only implies (the cancelled and finished refusal reasons for teams, the region header
  with one team) follow the same patterns.
- **Answers already given by a deleted team's members in an In progress competition** do not exist
  yet; what happens to them is decided in milestone 13.

## Dependencies

- **Constitution amendment**: Principle IV MUST be amended with `/speckit-constitution`, in its own
  pull request, before this milestone's plan, so that the plan's Constitution Check passes (FR-051).
- **Milestone 5**: roles, the current role, "access denied" and the automated route check.
- **Milestone 7**: regions and educational institutions, their names and their deactivation.
- **Milestone 8**: the **Can manage competitions** setting and the logging rule.
- **Milestone 10 and 10.1**: the component library, the gallery, the UI guidelines, the loading
  feedback and the busy button.
- **Milestone 11**: the question bank, its question numbers, text cards, page navigation, the
  landing rules after a deletion and the delete confirmation.
- **Milestone 11.1**: teams, their unique names, active members, deletion and its confirmation.
- **Milestone 12.1**: competitions, their statuses, the actions menu, the local-time display, the
  status badge, the chained-list selector, the confirmation and refusal patterns and the
  deactivated-subject rules.
- **Later milestones that depend on this one**: a later 12.x milestone adds stopping (reaching
  **Finished**); milestone 13 shows students the questions of the competitions their teams take part
  in, and decides what happens to answers of a deleted team and of teams whose institution or region
  is deactivated; milestone 15 shows results with every question and team, deleted ones included.

## Out of Scope

- Changing the order of a competition's questions.
- Updating a competition's copy of a question when the bank changes (the teacher removes it and adds
  it again).
- Limits on the number of questions or teams in a competition.
- Checking that a student is in only one team of a competition.
- Question or team counts in the competitions list.
- Filtering "Add questions", and searching "Add questions" or "Add teams".
- An "all regions" choice on "Add teams".
- Stopping a competition (a later 12.x milestone), the student's view (milestone 13) and results
  (milestone 15).
