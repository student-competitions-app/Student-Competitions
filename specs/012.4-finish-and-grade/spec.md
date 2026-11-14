# Feature Specification: Finishing a Competition and Grading Its Answers by Hand (Teacher) (Milestone 12.4)

**Feature Branch**: `012.4-finish-and-grade`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "create specification for the 12.4 milestone": milestone 12.4 of
`docs/requirements/milestones.md` ("Finishing a competition and grading its answers by hand
(teacher)"), part of the 12.x group "Competitions", with `product-requirements.md` (the "Teacher access
rights", "Personal data", "How a competition works", "Competition statuses", **Team** and **Subject**
sections), the constitution v2.3.0 (Principles IV and VII), the milestone 8, 10, 10.1, 11, 11.1, 12.1,
12.2 and 12.3 specifications and `docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 12.4 of the walking skeleton for the Student Competitions application, and the last of the
12.x milestones that build the teacher's side of competitions. After milestone 12.3, teachers enter
the teams' answers of a competition that is **In progress**, but nobody can stop the competition, and
its answers cannot be graded. A teacher with only **Read** access to an institution sees only how many
questions its teams answered.

This milestone lets a teacher with **Can manage competitions** **finish** a competition and then
**grade** every team's answers by hand, one whole-number grade from 0 to 10 per answer; a team's
**score** is the sum of its grades. It also lets the teachers of a team's institution read the team's
answers, with **Read** or **Write** access, and, after finishing, its grades and score. Nine things
become true when this milestone is done:

1. **The actions menu gains Grades and Finish competition.** The entries read, in this order,
   **Edit**, **Questions**, **Teams**, **Answers**, **Grades**, **Finish competition** and **Cancel
   competition**, each where it is available. **Answers** is now offered on **In progress** and
   **Finished** competitions, to every teacher.
2. **A teacher with the setting finishes a competition in progress.** A confirmation page with a
   primary, not destructive, **Finish competition** button marks it **Finished**. Finishing is final:
   its questions, teams and answers never change again.
3. **The Grades page lists every team of a finished competition** with its **Answered**, **Graded**
   and **Score** columns and the overall progress "Graded 37 of 52 teams", and lets the teacher show
   only the teams that still need grading.
4. **One grading sheet grades a whole team.** "Grade answers of “Comets” in “Spring round”" shows
   every question with its reference answer and the team's answer, a grade field under each answered
   question, and one **Save grades** button. Grades can be changed at any time; the last save wins.
5. **Read access reads answers.** On the **Competitions** tab a teacher with **Read** access sees what
   a teacher with **Write** access sees; only **Write** access enters and changes answers. While a
   competition is **In progress**, a **Read**-access team has **View answers**, which opens its answers
   read-only.
6. **After finishing, the Answers pages are read-only** and show each team's grades and score to the
   teachers of its institution, with **Read** or **Write** access.
7. **A finished competition of a deactivated subject stays usable**: its **Answers** pages open and its
   answers can still be graded.
8. **Three new patterns**, the **non-destructive confirmation**, the **grading sheet** (with its
   read-only variant) and the **filter links**, are added to the component library, the component
   gallery (`/admin/components`) and the UI guidelines before any page uses them.
9. **The UI guidelines are updated** for the actions menu, the confirmations and the wording patterns
   that this milestone changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher with the setting finishes a competition (Priority: P1)

Olena has **Can manage competitions**. "Spring round" of "Chemistry" started on 14 March 2027 at 10:00
and its teams have entered their answers. On the **Competitions** tab, with the status **All**, she
opens the **Actions** menu of "Spring round", which lists **Questions**, **Teams**, **Answers**,
**Finish competition** and **Cancel competition**, and chooses **Finish competition**. The page asks
"Finish competition “Spring round” of Chemistry, started 14 March 2027, 10:00?" and says "The
competition will be marked Finished. Its answers can no longer be entered or changed, and it cannot be
cancelled or restarted. Its answers can then be graded.". She presses the primary button **Finish
competition**. She is back on the same list page, at "Spring round", which now shows **Finished**, with
the notice "Competition “Spring round” was finished". Its menu now lists **Questions**, **Teams**,
**Answers** and **Grades**.

**Why this priority**: Finishing is the only way a competition ends and the condition for grading;
without it nothing of this milestone can be reached.

**Independent Test**: As a teacher with the setting, finish an **In progress** competition from the
list under each status filter, and check the confirmation, **Keep in progress**, the notice, the
landing row, the new status, the menu and that the competition can no longer change.

**Acceptance Scenarios**:

1. **Given** an **In progress** competition, **When** Olena chooses **Finish competition**, **Then**
   the confirmation page asks "Finish competition “Spring round” of Chemistry, started 14 March 2027,
   10:00?" (the start in her time zone), shows the consequence "The competition will be marked
   Finished. Its answers can no longer be entered or changed, and it cannot be cancelled or restarted.
   Its answers can then be graded.", and has the primary (not destructive) button **Finish
   competition** and the link **Keep in progress**.
2. **Given** the confirmation, **When** she follows **Keep in progress**, **Then** she returns to the
   list page she came from, at the competition, and nothing has changed.
3. **Given** she confirms under the status filter **All** or **Finished**, **When** the list is shown
   again, **Then** it keeps the same subject, status filter and page, she lands at the competition,
   which now shows **Finished**, and the notice reads "Competition “Spring round” was finished".
4. **Given** she confirms under the status filter **In progress**, **When** the list is shown again,
   **Then** the competition is no longer listed, and she lands as after cancelling (milestone 12.1): at
   the row that took its place, at the row before it if none did, on the previous page at its last row
   if the page is now empty, or on the empty state if no row is left.
5. **Given** a finished competition, **When** its menu is shown, **Then** it no longer offers **Finish
   competition** or **Cancel competition**, it cannot be cancelled or edited, and it is never **In
   progress** again.
6. **Given** a finished competition named "Spring round", **When** a new competition of the same subject
   is saved with that name, **Then** the name is accepted (milestone 12.1).
7. **Given** a competition is finished, **When** its **Questions** and **Teams** pages are opened,
   **Then** they are read-only for everyone, and its questions, teams and answers never change again;
   only the grades of this milestone are added to its answers.
8. **Given** a finish, **When** the page is reloaded, **Then** nothing is sent again.

---

### User Story 2 - Finishing is refused for the wrong status, and happens once (Priority: P1)

Olena types the finish address of the upcoming "Autumn round" and sees "Finish competition “Autumn
round”?" with "“Autumn round” has not started yet and cannot be finished." and the link **Back to
competitions**. Once its start passes, the same address shows the confirmation. Olena and her colleague
Petro, both with the setting, open the confirmation of "Spring round" at the same time; Olena confirms
first, and Petro's confirmation shows "“Spring round” has already finished.". When Petro had chosen
**Cancel competition** instead and confirmed at the same moment as Olena, exactly one of the two
changes was made, and the other teacher saw the refusal for the new status.

**Why this priority**: Finishing is final; finishing the wrong competition, or finishing and
cancelling the same one, would leave a record that cannot be repaired.

**Independent Test**: With the current time controlled by the test, send the confirmation and the
finish for an **Upcoming**, a **Cancelled** and a **Finished** competition; let the start of the
upcoming one pass; send two finishes, a finish and a cancel, and the same form twice, at the same
moment; check the refusals, their reasons and links, and that exactly one change was stored.

**Acceptance Scenarios**:

1. **Given** an **Upcoming** competition (typed address), **When** its finish confirmation is opened or
   a finish is sent, **Then** the refusal "Finish competition “Autumn round”?" shows the reason "“Autumn
   round” has not started yet and cannot be finished." and the link **Back to competitions**, and
   nothing changes.
2. **Given** a **Cancelled** competition, **When** the same is tried, **Then** the reason reads "“Spring
   round” has been cancelled and cannot be finished."; **Given** a **Finished** one, **Then** it reads
   "“Spring round” has already finished.".
3. **Given** a refusal, **When** **Back to competitions** is followed, **Then** it leads to the list page
   the teacher came from, at the competition.
4. **Given** an **Upcoming** competition whose start passes while its refusal is shown, **When** the
   teacher tries again, **Then** the confirmation is shown and the competition can be finished.
5. **Given** two teachers finish the same competition at the same time, **When** both finishes are
   handled, **Then** exactly one succeeds and the other gets "“Spring round” has already finished.".
6. **Given** one teacher finishes and another cancels the same competition at the same time, **When**
   both are handled, **Then** exactly one succeeds and the other gets the refusal for the new status
   (the finishing refusal for **Cancelled**, or the cancelling refusal of milestone 12.1 for
   **Finished**).
7. **Given** the same finish form sent twice, **When** both requests are handled, **Then** the
   competition is finished once, and the second request gets "“Spring round” has already finished.".

---

### User Story 3 - The Grades page lists every team with its progress (Priority: P1)

"Spring round" is finished and holds 52 teams from seven regions, of institutions Olena is not linked
to as well. She chooses **Grades** in its menu. "Grades of “Spring round”" shows "Chemistry", the start
and the **Finished** badge under the heading, and "Graded 37 of 52 teams". Below the filter links
**All teams** and **Ungraded only** it lists "Teams 1–10 of 52" in region boxes, as on the **Teams**
page. The row of "Comets" reads "School No. 5", "4" members, **Answered** "4 of 10", **Graded** "3 of
4", **Score** "17", and has **Grade answers**. A deleted team is listed as "Meteors (deleted)", and a
team of a deactivated institution is listed too.

**Why this priority**: The Grades page is the only way to the grading sheets and the grader's overview
of what is left to grade.

**Independent Test**: Seed a finished competition with teams of linked, unlinked, deactivated and
deleted institutions and teams in several regions, with answers and grades in every combination, and
check the listing, the paging, the region headers, the three columns, the overall progress and the
empty state.

**Acceptance Scenarios**:

1. **Given** a **Finished** competition, **When** a teacher with the setting chooses **Grades**,
   **Then** the page "Grades of “Spring round”" opens, showing under the heading the competition's
   subject, its start in the teacher's time zone, its status badge and the overall progress "Graded 37
   of 52 teams", with a back link to the competitions list the teacher came from (same subject, status
   and page), at the competition, as the pages of milestone 12.2.
2. **Given** the competition's teams, **When** the page lists them, **Then** it lists every team of the
   competition, whether or not the teacher is linked to its institution, including the teams of a
   deactivated institution or region and deleted teams, marked "(deleted)".
3. **Given** teams of several regions, **When** they are listed, **Then** they are grouped in region
   boxes with the order, region headers and counts of the **Teams** page (milestone 12.2), 10 teams per
   page with the page navigation ("Teams 1–10 of 52") and the page number kept in the address.
4. **Given** a team row, **When** it is shown, **Then** it shows the team's name, its educational
   institution and its number of active members, as on the **Teams** page, then **Answered** ("4 of
   10", as in milestone 12.3), **Graded** ("3 of 4") and **Score** ("17"), as plain text, then **Grade
   answers** in the actions cell; on a phone the three values are labelled lines of the card.
5. **Given** a team with no answers, **When** its row is shown, **Then** **Graded** reads "0 of 0" and
   **Score** "0"; **Given** a team with answers but no grades, **Then** **Score** reads "0".
6. **Given** the overall progress, **When** it is counted, **Then** it counts the fully graded teams (a
   team every one of whose answers has a grade, so a team with no answers counts) of all the
   competition's teams, on all pages, whatever the filter.
7. **Given** a competition with no teams, **When** the page is shown, **Then** it shows "No teams in
   this competition" and "Graded 0 of 0 teams", whatever the filter.

---

### User Story 4 - A teacher grades a team's answers on one sheet (Priority: P1)

Olena presses **Grade answers** on the row of "Comets". "Grade answers of “Comets” in “Spring round”"
shows "School No. 5" under the heading, then questions 1 to 10. Each shows its copied text, the copied
reference answer labelled "Reference answer" and the team's answer labelled "Answer to question 1",
with its line breaks kept. Under each of the four answered questions is a field "Grade for question 1"
with the hint "A whole number from 0 to 10." and the placeholder "Not graded"; three already hold the
grades 5, 7 and 5. The six unanswered questions show "Not answered" and no field. She types 4 in the
fourth field, changes the 7 to 8 and presses **Save grades**. She stays on the page with the notice
"Grades of “Comets” were saved". On the Grades page, "Comets" now reads **Graded** "4 of 4" and
**Score** "22".

**Why this priority**: Grading the answers is the purpose of this milestone; the scores of milestones
14 and 15 are built on these grades.

**Independent Test**: As a teacher with the setting, open the grading sheet of a team with answered and
unanswered questions, save, change and empty grades in one save, and check the fields, the notice, the
stored grades, the Grades page and the team's read-only answer sheet.

**Acceptance Scenarios**:

1. **Given** the Grades page, **When** **Grade answers** is pressed, **Then** the page "Grade answers
   of “Comets” in “Spring round”" opens, with the team's institution under the heading ("(deleted)" for
   a deleted team) and a back link to the Grades page at the page and filter the teacher came from, at
   that team.
2. **Given** the competition holds 10 questions, **When** the sheet is shown, **Then** it lists all 10 on
   one page, in the competition's order (milestone 12.2), numbered 1 to 10, each with its copied text,
   its copied reference answer labelled "Reference answer" and the team's answer labelled "Answer to
   question <n>", read-only with its line breaks kept; a question deleted from the question bank, or
   edited there after it was copied, is shown with its copied texts like any other.
3. **Given** an answered question, **When** the sheet is shown, **Then** a field labelled "Grade for
   question <n>" with the hint "A whole number from 0 to 10." stands under the answer; it shows the
   saved grade, or is empty with the placeholder "Not graded".
4. **Given** a question the team did not answer, **When** the sheet is shown, **Then** it shows "Not
   answered" where the answer would be, and no grade field.
5. **Given** grades typed, changed and emptied, **When** **Save grades** is pressed, **Then** all of
   them are stored by that one save, an emptied field leaves its answer not graded, and the teacher
   stays on the page with the notice "Grades of “Comets” were saved" and the saved grades in their
   fields.
6. **Given** a grade with spaces around it (" 7 "), "0" or "10", **When** it is saved, **Then** it is
   accepted and stored as 7, 0 or 10.
7. **Given** a save, **When** the Grades page, the Answers page of a teacher of the team's institution
   or the team's read-only answer sheet is shown next, **Then** they show the new **Graded**, **Score**
   and grades.
8. **Given** a save, **When** the page is reloaded, **Then** the save is not repeated.
9. **Given** a team with no answers, **When** its sheet is shown, **Then** every question shows "Not
   answered", the text "“Comets” gave no answers, so there is nothing to grade" is shown, and there is
   no **Save grades** button; **Given** a competition with no questions, **Then** the sheet shows "No
   questions in this competition" and no **Save grades** button.

---

### User Story 5 - Invalid grades save nothing (Priority: P1)

Olena types "7.5" for question 2, "11" for question 3 and changes question 1 from 5 to 6, then presses
**Save grades**. Nothing is saved: the page shows again with "6", "7.5" and "11" still in their fields,
the error "Enter a whole number from 0 to 10." at questions 2 and 3, and the error summary "There is a
problem" linking to both. She corrects them to 7 and 10 and saves all three grades.

**Why this priority**: A save stores the whole sheet, so it must never store part of it; and a grader
who loses their entries must type them again.

**Independent Test**: Save a sheet with each invalid value among valid changes, and check that nothing
is stored, the kept values, the errors and the summary; then save valid values.

**Acceptance Scenarios**:

1. **Given** a grade "7.5", "-1", "11" or "seven", **When** the sheet is saved, **Then** nothing is
   saved, no other grade included, and the page shows again with every entered value kept.
2. **Given** that refused save, **When** the page is shown again, **Then** the error "Enter a whole
   number from 0 to 10." stands at that grade and the error summary under the heading links to it.
3. **Given** several invalid grades, **When** the sheet is saved, **Then** each shows its error and the
   summary lists them all, in the order of the questions.

---

### User Story 6 - A grader shows only the teams that still need grading (Priority: P2)

On "Grades of “Spring round”" Olena follows **Ungraded only**. The page shows "Teams 1–10 of 14": only
the teams with at least one ungraded answer, with region headers counting only those, while the overall
progress still reads "Graded 38 of 52 teams". She grades the last ungraded answer of "Comets" and
follows the back link: she lands on the same page of **Ungraded only**, now without "Comets". When she
has graded every team, **Ungraded only** shows "All teams are graded".

**Why this priority**: It saves time on large competitions but adds no capability; the full list
reaches every team too.

**Independent Test**: Seed a finished competition with fully graded, partly graded and unanswered
teams over several pages; switch the filter on different pages, grade the last answer of a team, and
check the listing, the counts, the address, the current link and every landing of the back link.

**Acceptance Scenarios**:

1. **Given** the Grades page opened from the menu, **When** it is shown, **Then** **All teams** is the
   current filter, marked as current and drawn as the current page of the page navigation.
2. **Given** any page of either filter, **When** a filter link is followed, **Then** page 1 of that
   filter is shown.
3. **Given** **Ungraded only**, **When** the list is shown, **Then** it lists only the teams with at
   least one answer that has no grade (so not a team with no answers), the page navigation ("Teams 1–10
   of 14") and the region header counts count only the listed teams, and the overall progress still
   counts all the competition's teams.
4. **Given** a filter, **When** the page is reloaded, the page navigation is followed or a grading sheet's
   back link is followed, **Then** the filter is kept in the page address.
5. **Given** **Ungraded only** and no team needing grading, **When** the page is shown, **Then** it
   shows "All teams are graded".
6. **Given** a grading sheet opened from **Ungraded only** and the team is now fully graded, **When** its
   back link is followed, **Then** it leads to the same page without the team, to the last page if that
   page no longer exists, or to "All teams are graded" if no team is left.

---

### User Story 7 - Read access opens a team's answers while the competition is in progress (Priority: P1)

Taras has **Write** access to School No. 5 and **Read** access to Lyceum No. 2. On "Answers of “Spring
round”", in progress, the school's teams have **Enter answers** and the lyceum's team "Stars" has
**View answers**, where the row note "Read access" used to be. **View answers** opens "Answers of
“Stars” in “Spring round”" with the notice "You have Read access to “Lyceum No. 2”, so you cannot change
these answers.", every question with the team's answer or "Not answered", no grades, no score, no
reference answer, no field and no save button. His colleague Iryna, with only **Read** access to the
lyceum, sees the same.

**Why this priority**: The milestone changes what **Read** access means on the **Competitions** tab; the
teachers of an institution must see their teams' answers to discuss them, and must still not change
them.

**Independent Test**: As teachers with **Read**, **Write** and mixed access, open the Answers page and
the sheets of an **In progress** competition; save answers from another session and open the sheet
again; try a save for a **Read**-access team through a crafted form and from a sheet opened before the
access was lowered; raise the access to **Write**; unlink the teacher.

**Acceptance Scenarios**:

1. **Given** an **In progress** competition, **When** the Answers page is shown, **Then** a team of a
   **Write**-access institution has **Enter answers** and a team of a **Read**-access institution has
   **View answers**; no row shows the row note "Read access".
2. **Given** **View answers**, **When** it is pressed, **Then** the read-only sheet "Answers of “Stars”
   in “Spring round”" opens, with the team's institution and the notice "You have Read access to
   “Lyceum No. 2”, so you cannot change these answers." under the heading, and a back link to the
   Answers page at the page the teacher came from, at that team.
3. **Given** the read-only sheet of an **In progress** competition, **When** it is shown, **Then** it
   shows every question in the competition's order, numbered from 1, with its copied text and the
   team's answer labelled "Answer to question <n>" with its line breaks kept, or "Not answered"; and no
   grade, no score, no reference answer, no field and no save button.
4. **Given** answers are saved by another teacher after the sheet was opened, **When** it is opened
   again, **Then** it shows them; it is not refreshed on its own.
5. **Given** a team of a **Read**-access institution, **When** a save is sent for it, typed or from an
   answer sheet opened before the access was lowered to **Read**, **Then** it gets "access denied",
   nothing is saved, and the answers saved before stay.
6. **Given** the access is raised to **Write**, **When** the Answers page is shown next, **Then** the
   team has **Enter answers**.
7. **Given** a teacher unlinked from the institution, **When** the Answers page or the team's sheet is
   requested next, **Then** its teams are no longer listed and the sheet gets "access denied".
8. **Given** a competition with no questions, **When** the read-only sheet is shown, **Then** it shows
   "No questions in this competition".

---

### User Story 8 - After finishing, a team's teachers see its answers, grades and score (Priority: P1)

"Spring round" is finished and Olena has graded "Comets". Taras, without the setting, opens **Answers**
in its menu. "Answers of “Spring round”" lists his institutions' teams, each with **Answered**,
**Graded** and **Score** and **View answers**, for School No. 5 (**Write**) and Lyceum No. 2 (**Read**)
alike. The read-only sheet of "Comets" shows "Score: 17" with "Graded 3 of 4 answers", every question
with the team's answer and "Grade: 7 of 10" or "Not graded yet" under it, or "Not answered". He talks
the results through with the team. A minute after Olena saves the last grade, opening the sheet again
shows "Score: 22" and "Graded 4 of 4 answers".

**Why this priority**: Grades are given so that the team's performance can be discussed with its
members, and the teachers of the team's institution are the ones who do it.

**Independent Test**: On a finished competition with graded, partly graded and unanswered teams, as
teachers with **Write**, **Read** and mixed access, with and without the setting, open the Answers page
and the read-only sheets; save grades on a grading sheet and open the read-only sheet again; send an
answer save from a sheet opened before finishing and through a crafted form.

**Acceptance Scenarios**:

1. **Given** a **Finished** competition, **When** any teacher chooses **Answers**, **Then** the page
   "Answers of “Spring round”" opens as in milestone 12.3: only the teams of the teacher's own
   institutions, the same region boxes, order, paging, **Answered** column and empty states; deleted
   teams and teams of a deactivated institution or region are not listed.
2. **Given** that page, **When** a row is shown, **Then** after **Answered** it shows the **Graded**
   ("3 of 4") and **Score** ("17") columns, counted as on the Grades page, and **View answers**, with
   **Read** or **Write** access.
3. **Given** **View answers** on a **Finished** competition, **When** the sheet opens, **Then** it shows
   the team's institution under the heading, the score "Score: 17" (the sum of its saved grades, "Score:
   0" when none is graded) with "Graded 3 of 4 answers", and every question with its answer and
   "Grade: 7 of 10" once the answer is graded or "Not graded yet" until then, or "Not answered"; no
   reference answer, no field and no save button.
4. **Given** a team with no answers, **When** its read-only sheet is shown, **Then** every question
   shows "Not answered", with "Score: 0".
5. **Given** a grade saved on the grading sheet, **When** the read-only sheet is opened next, **Then**
   it shows the grade and the new score.
6. **Given** a teacher with the setting, **When** they open the Answers page, **Then** they see only the
   teams of their own institutions, and the read-only sheet of a team of an institution they are not
   linked to gets "access denied".
7. **Given** a deleted team or a team of a deactivated institution or region, **When** its read-only
   sheet is requested, **Then** it shows "not found".
8. **Given** an answer sheet opened before the competition finished, or a typed save afterwards, **When**
   the save is sent, **Then** it gets the 12.3 refusal "“Spring round” has finished, so its answers can
   no longer be entered." and nothing changes; the answers saved before finishing stay.
9. **Given** an **Upcoming** or **Cancelled** competition, **When** an Answers page or save is
   requested, **Then** it keeps the 12.3 refusals.

---

### User Story 9 - The menu offers the right entries per status and setting (Priority: P1)

Olena, with the setting, opens **Competitions** with the status **All**. The in-progress "Spring round"
lists **Questions**, **Teams**, **Answers**, **Finish competition** and **Cancel competition**; the
finished "Summer round" lists **Questions**, **Teams**, **Answers** and **Grades**. Taras, without the
setting, sees **Questions**, **Teams** and **Answers** on both, and **Finish competition** or **Grades**
nowhere.

**Why this priority**: The menu is the only way into the new pages and actions.

**Independent Test**: List competitions of every status as teachers with and without the setting and
check each menu's entries and their order.

**Acceptance Scenarios**:

1. **Given** a teacher with the setting, **When** the menu of an **In progress** competition opens,
   **Then** it lists **Questions**, **Teams**, **Answers**, **Finish competition** and **Cancel
   competition**, in this order; **Given** a **Finished** one, **Then** it lists **Questions**,
   **Teams**, **Answers** and **Grades**.
2. **Given** a teacher without the setting, **When** the menu of an **In progress** or **Finished**
   competition opens, **Then** it lists **Questions**, **Teams** and **Answers**; in no status does it
   offer **Finish competition** or **Grades**.
3. **Given** an **Upcoming** or **Cancelled** competition, **When** its menu opens, **Then** it offers
   neither **Answers**, **Grades** nor **Finish competition**, and the other entries keep their 12.1 and
   12.2 rules.
4. **Given** **Finish competition**, **When** the menu is shown, **Then** it is not in the danger colour
   of a destructive entry.
5. **Given** **Grades** or **Finish competition** is chosen, **When** the page opens, **Then** the
   competitions list's subject, status and page are kept for the way back.

---

### User Story 10 - Grading is possible only on a finished competition (Priority: P1)

Olena types the Grades address of "Spring round" while it is still in progress and sees "Grade answers
of “Spring round”?" with "“Spring round” is still in progress, so its answers cannot be graded until it
is finished." and **Back to competitions**. A grading save crafted for the upcoming "Autumn round" shows
"“Autumn round” has not started yet, so its answers cannot be graded." and saves nothing.

**Why this priority**: Answers are graded only once the competition is finished (Principle VII);
grading answers that can still change would give a false score.

**Independent Test**: Open the Grades page and a grading sheet, and send a grading save, for an
**Upcoming**, an **In progress** and a **Cancelled** competition; check the refusals, their reasons and
links, and that nothing is saved.

**Acceptance Scenarios**:

1. **Given** a competition that is not **Finished**, **When** its Grades page or a grading sheet is
   opened or a grading save is sent, **Then** the refusal "Grade answers of “Spring round”?" shows the
   reason for its status, "“…” has not started yet, so its answers cannot be graded." (**Upcoming**),
   "“…” is still in progress, so its answers cannot be graded until it is finished." (**In progress**)
   or "“…” has been cancelled, so its answers cannot be graded." (**Cancelled**), with the link **Back to
   competitions**.
2. **Given** such a refusal for a save, **When** it is shown, **Then** nothing has been saved.

---

### User Story 11 - Only the right teacher reaches finishing and grading (Priority: P1)

An administrator and a student who type the address of a Grades page get "access denied", before any id
is read. Taras, without the setting, gets "access denied" on the finish confirmation, the finish, the
Grades page, a grading sheet and a grading save, also with unknown ids. While Olena has a grading sheet
open, an administrator takes away her setting: her save gets "access denied", and the grades she saved
before stay. A crafted grading save that names a question the team did not answer gets "not found" and
saves nothing.

**Why this priority**: A team's grades decide its result; a missing check would let anyone change them.

**Independent Test**: For every page and action of finishing and grading, send requests as each role
and as teachers with and without the setting, including typed addresses and crafted forms for unknown,
mismatched and hidden subjects, competitions, teams and questions, and the setting taken away while a
page is open; check the result, the check order and that nothing changes.

**Acceptance Scenarios**:

1. **Given** a person in the administrator or student role, **When** they open any page or send any
   action of this milestone, also with unknown ids, **Then** they get "access denied" before any id is
   read.
2. **Given** a teacher without **Can manage competitions**, **When** they open the finish confirmation,
   send a finish, open the Grades page or a grading sheet or send a grading save, also with unknown ids,
   **Then** they get "access denied" before any id or subject is read.
3. **Given** a teacher whose setting is taken away, **When** their next request of finishing or grading
   arrives, also from a page opened before, **Then** it gets "access denied", and the grades saved
   before stay.
4. **Given** a teacher with the setting, **When** the address names an unknown subject or competition, a
   competition of another subject, or a competition of a deactivated subject that is not **Finished**,
   **Then** they get "not found".
5. **Given** a **Finished** competition, **When** a grading sheet or save names an unknown team or a team
   that is not in the competition, **Then** it shows "not found" and nothing is saved; a deleted team,
   or one of a deactivated institution or region, is found and graded normally.
6. **Given** a grading save, **When** it names a question that is not one of the competition's, or one
   the team did not answer, **Then** it shows "not found" and nothing is saved.
7. **Given** a teacher with the setting who is not linked to a team's institution, **When** they grade
   it, **Then** the grading sheet opens and saves as for any team.
8. **Given** checks fail at several levels, **When** a request is handled, **Then** the first failing
   check in the order role, setting, subject and competition, status, team and questions, grades decides
   the answer: a teacher without the setting sending unknown ids gets "access denied", and an unknown
   team in an **In progress** competition shows the grading refusal.
9. **Given** a finish or a grading save, **When** the existing cross-site request check judges it sent
   from another site, **Then** it is refused and nothing changes.

---

### User Story 12 - Two teachers grade the same team (Priority: P2)

"Comets" has the grade 5 on question 1. Olena and Petro open its grading sheet at the same time. Petro
grades question 2 with 8 and saves. Olena, whose page does not show his grade, empties question 1,
grades question 3 with 6 and saves a minute later. The team's grades are now exactly those of Olena's
page: question 1 and question 2 are not graded, and question 3 has 6. Neither is warned.

**Why this priority**: The milestone accepts this on purpose, as with answers (milestone 12.3); the
behaviour must still be predictable.

**Independent Test**: Open the same team's grading sheet twice, save different grades from each,
including an emptied one, and check that the stored grades are exactly those of the later save.

**Acceptance Scenarios**:

1. **Given** two teachers save the same team's grading sheet one after the other, **When** the second
   save is stored, **Then** it replaces every grade of the first, emptied ones included, with no warning
   and no refusal.
2. **Given** two saves of the same team at the same moment, **When** both are stored, **Then** the
   team's grades are exactly those of one of the two saves, never a mix of both.

---

### User Story 13 - A finished competition of a deactivated subject stays usable (Priority: P2)

An administrator deactivates "Chemistry". The finished "Summer round" of Chemistry is still listed,
with **Answers** and **Grades** in its menu. Olena grades its remaining answers, and Taras opens its
Answers page and the read-only sheets of his teams. The in-progress "Spring round" of Chemistry is
hidden and gets "not found", as in milestone 12.1.

**Why this priority**: A deactivated subject must not stop a finished competition from being graded
or reviewed (constitution, Principle IV); the case is rare.

**Independent Test**: Deactivate the subject of a finished and of an in-progress competition, and open
the menus, the Answers pages, the Grades page, the grading sheets and a save of each.

**Acceptance Scenarios**:

1. **Given** a finished competition of a deactivated subject, **When** it is listed, **Then** its menu
   offers **Answers** to every teacher and **Grades** to a teacher with the setting.
2. **Given** that competition, **When** its Grades page, a grading sheet or a grading save is used,
   **Then** they work as on any finished competition, and grading changes nothing else about it.
3. **Given** that competition, **When** its Answers page and read-only sheets are opened, **Then** they
   open as on any finished competition.
4. **Given** a competition of a deactivated subject that is not **Finished**, **When** any page or
   action of this milestone is requested, **Then** it shows "not found".

---

### User Story 14 - The new patterns and guideline updates are written first (Priority: P3)

An administrator opens `/admin/components` outside production and finds the non-destructive
confirmation, with a primary confirming button; the grading sheet, with an error, with an unanswered
question and at phone width; its read-only variant with and without grades; and a row of filter links
with the current one marked. The UI guidelines describe them, and their actions menu, confirmations and
wording patterns are updated.

**Why this priority**: It follows the project rule that pages use only library components; it adds no
capability of its own.

**Independent Test**: Open the gallery and the UI guidelines and check each addition and change.

**Acceptance Scenarios**:

1. **Given** the gallery, **When** it is opened, **Then** it shows the non-destructive confirmation; the
   grading sheet with an error, with an unanswered question and at phone width; the read-only variant
   with grades and without them; and the filter links, the current one marked as current.
2. **Given** the UI guidelines, **When** they are read, **Then** they describe the three patterns, state
   that every action that cannot be undone goes through a confirmation page, and say when its button is
   destructive and when it is primary.
3. **Given** the UI guidelines, **When** their actions menu, confirmations and wording patterns are
   read, **Then** they carry the changes of FR-047.

---

### Edge Cases

- **The competition is finished while an answer sheet is open**: the next answer save gets the 12.3
  "has finished" refusal and saves nothing; the answers saved before stay.
- **The competition is finished while its finish confirmation is open in another tab**: the second
  confirmation gets "“…” has already finished." and nothing changes.
- **The competition is cancelled while its finish confirmation is open**: the finish gets "“…” has been
  cancelled and cannot be finished.".
- **Finishing a competition with no teams or no questions**: allowed; its Grades page shows "No teams
  in this competition" with "Graded 0 of 0 teams", or every team "0 of 0" and graded.
- **The setting is taken away while a grading sheet or a finish confirmation is open**: the next save or
  finish gets "access denied" and changes nothing; the grades saved before stay.
- **The setting is given to a teacher**: **Finish competition** and **Grades** appear in their menu on
  the next page shown.
- **A team is deleted after the competition finished**: it stays in the competition with its answers
  and grades, is listed on the Grades page marked "(deleted)" and can still be graded; it is no longer
  listed on the Answers pages, and its read-only sheet shows "not found".
- **A team's institution or region is deactivated after finishing**: the Grades page still lists the
  team and it can be graded; the Answers pages no longer list it and its read-only sheet shows "not
  found"; when it is activated again, the team is listed again with its answers and grades.
- **The subject is deactivated while a grading sheet is open**: the competition is **Finished**, so the
  save is stored.
- **A grade typed with a leading zero ("07") or with a plus sign ("+7")**: see Assumptions.
- **A grade field emptied that was never graded**: nothing changes for that answer.
- **Saving grades with nothing changed**: the save is accepted and shows the notice.
- **Pressing Save grades or Finish competition twice (double press)**: the form cannot be sent again
  until the next page arrives (milestone 10.1); a second grading request arriving anyway stores the same
  grades again, and a second finish gets "“…” has already finished.".
- **A competition with many questions**: all are shown on the one grading sheet, with no page
  navigation.
- **The last answer of the last team on a page of Ungraded only is graded**: the back link leads to the
  previous page's last position, or to "All teams are graded" if no team is left.
- **A page number beyond the last page, or not a number**, on the Grades page: it opens on the nearest
  valid page, as on **Teams**; **an unknown filter value**: it is taken as **All teams**.
- **The competitions-list context, the Grades page's page or filter, or the Answers page's page in the
  address is missing or invalid**: the back links fall back as in milestones 12.2 and 12.3 (the
  competition's subject, the status **All** and the page holding the competition; the page of the list
  holding the team, under **All teams**).
- **A teacher with mixed access and the setting**: the Answers pages show only their own institutions'
  teams, with **Enter answers** or **View answers** by access while **In progress**; the Grades page
  shows every team.
- **A team with answers to every question and every one graded 0**: it is fully graded with "Score: 0".
- **Very long competition, team, institution or region names, long question texts, reference answers
  and answers**: they wrap within the content width on every screen size, with no sideways page
  scroll, in the headings, region headers, rows, cards, fields, refusals, confirmations and notices.

## Requirements *(mandatory)*

### Functional Requirements

#### Who

- **FR-001**: Only a teacher with **Can manage competitions** MUST be able to finish competitions and
  grade answers: of every competition, whoever created it, and of every team in it, whether or not they
  are linked to the team's institution. There MUST be no rights per competition or per institution.
- **FR-002**: A teacher without the setting MUST get no **Finish competition** or **Grades** entry, and
  MUST get "access denied" on the finish confirmation, the finish, the Grades page, the grading sheets
  and their saves. When the setting is taken away from a teacher, those pages and actions MUST get
  "access denied" for them at once; the grades already saved MUST stay.
- **FR-003**: The **Answers** pages MUST follow the teacher's links to institutions, with or without the
  setting (FR-031 to FR-041); **Can manage competitions** MUST give no access there.

#### Row actions

- **FR-004**: The actions menu MUST list, in this order, **Edit**, **Questions**, **Teams**,
  **Answers**, **Grades**, **Finish competition** and **Cancel competition**, each only where it is
  available.
- **FR-005**: **Finish competition** MUST be offered only on an **In progress** competition, and
  **Grades** only on a **Finished** one, both only to a teacher with the setting. **Finish competition**
  MUST NOT be a destructive entry.
- **FR-006**: **Answers** MUST be offered on every **In progress** and **Finished** competition the list
  shows, to every teacher, and on no **Upcoming** or **Cancelled** one. Once a competition is finished,
  **Finish competition** and **Cancel competition** MUST no longer be offered on it. The other entries
  keep their 12.1 and 12.2 rules.

#### Finishing

- **FR-007**: **Finish competition** MUST open a confirmation page in the 12.1 cancel pattern, asking
  "Finish competition “<name>” of <subject>, started <start>?" with the start in the teacher's time
  zone, and the consequence "The competition will be marked Finished. Its answers can no longer be
  entered or changed, and it cannot be cancelled or restarted. Its answers can then be graded.".
- **FR-008**: The confirming button MUST be **Finish competition**, of the primary kind, not
  destructive. The link back MUST be **Keep in progress** and MUST return to the list page the teacher
  came from, at the competition, with nothing changed.
- **FR-009**: Confirming MUST mark the competition **Finished** at that moment, and MUST return the
  teacher to the list page they came from, with the same subject, status filter and page, and the
  notice "Competition “<name>” was finished". The status filter MUST keep its value: under **All** or
  **Finished** the teacher lands at the competition, which shows **Finished**; under **In progress** they
  land as after cancelling (milestone 12.1): at the row that took its place, at the row before it if
  none did, on the previous page at its last row if the page is now empty, and on the empty state if no
  row is left.
- **FR-010**: Finishing MUST be final: a finished competition MUST never be **In progress** again and
  MUST NOT be cancelled or edited. Its name MUST be free again in its subject (milestone 12.1).
- **FR-011**: The status MUST change for everyone at once. After finishing, the competition's
  questions, teams and answers MUST never change; only the grades of this milestone are added to its
  answers. Answers saved before the competition finished MUST stay.
- **FR-012**: Finishing a competition that is not **In progress** MUST show a refusal in the 12.1
  pattern, "Finish competition “<name>”?", with the reason for its status: "“…” has not started yet and
  cannot be finished." (**Upcoming**), "“…” has been cancelled and cannot be finished." (**Cancelled**)
  or "“…” has already finished." (**Finished**), and the link **Back to competitions** to the list page
  the teacher came from, at the competition. Nothing MUST change. An upcoming competition whose start
  passes while its refusal is shown MUST be finishable on the next try.
- **FR-013**: When two teachers finish the same competition at the same time, or one finishes and another
  cancels it at the same time, exactly one MUST succeed, and the other MUST get the refusal for the new
  status. The same form sent twice MUST finish the competition once.

#### The Grades page

- **FR-014**: **Grades** MUST open the page "Grades of “<name>”". Under the heading it MUST show the
  competition's subject, its start in the teacher's time zone, its status badge and the overall
  progress "Graded <fully graded> of <all> teams". It MUST have a back link to the competitions list
  the teacher came from (same subject, status and page), at the competition, as the pages of milestone
  12.2, and that context MUST be carried through every page and save of grading.
- **FR-015**: A team MUST count as fully graded when every one of its answers has a grade; a team with
  no answers MUST count as fully graded. The overall progress MUST count all the competition's teams on
  all pages, whatever the filter.
- **FR-016**: The page MUST list every team of the competition, with the region boxes, order, region
  headers and counts, paging (10 teams per page, "Teams 1–10 of 25", page number kept in the address)
  and phone layout of the **Teams** page (milestone 12.2). A team of a deactivated institution or region
  MUST be listed, and a deleted team MUST be listed and marked "(deleted)".
- **FR-017**: Above the list MUST be two filter links, **All teams** and **Ungraded only**. The current
  one MUST be marked as the current filter and drawn as the current page of the page navigation; **All
  teams** MUST be current when the page opens from the menu. **Ungraded only** MUST list only the teams
  with at least one answer that has no grade. The filter MUST be kept in the page address together with
  the page number, and the page navigation and every back link to the Grades page MUST keep it.
  Following either link MUST go to page 1. Under **Ungraded only** the page navigation and the region
  header counts MUST count only the listed teams.
- **FR-018**: Each row MUST show the team's name, its educational institution and its number of active
  members, as on the **Teams** page, then three plain-text columns: **Answered** ("4 of 10", as in
  milestone 12.3), **Graded** (the team's answers that have a grade, of the team's answers: "3 of 4";
  "0 of 0" for a team with no answers) and **Score** (the sum of the team's saved grades: "17"; "0" when
  none of its answers is graded or it has no answers), then **Grade answers** in the actions cell. All
  three MUST be counted when the page is shown and MUST NOT be stored; on a phone they MUST be labelled
  lines of the card.
- **FR-019**: A competition with no teams MUST show "No teams in this competition" and "Graded 0 of 0
  teams", whatever the filter. When **Ungraded only** is current and no team needs grading, the page
  MUST show "All teams are graded".

#### The grading sheet

- **FR-020**: **Grade answers** MUST open the page "Grade answers of “<team>” in “<competition>”", with
  the team's educational institution under the heading ("(deleted)" for a deleted team) and a back link
  to the Grades page at the page and filter the teacher came from, at that team. When that page no
  longer lists the team (**Ungraded only** and the team is now fully graded), the back link MUST lead to
  the same page without the team, or to the last page if that page no longer exists, or to "All teams
  are graded".
- **FR-021**: The sheet MUST show every question of the competition on one page, in the competition's
  order (milestone 12.2), numbered 1, 2, 3, …, each with its copied text, its copied reference answer
  labelled "Reference answer" and the team's answer labelled "Answer to question <n>", read-only with
  its line breaks kept. A question deleted from the question bank MUST be shown like any other.
- **FR-022**: Under each answered question MUST be its grade field, labelled "Grade for question <n>",
  with the hint "A whole number from 0 to 10." and the placeholder "Not graded" when it has no grade. A
  saved grade MUST be shown in its field and MUST be changeable and removable by emptying the field; an
  empty field MUST mean that the answer is not graded.
- **FR-023**: A question the team did not answer MUST show "Not answered" where the answer would be and
  MUST have no grade field; it MUST have no grade and add nothing to the team's score.
- **FR-024**: One **Save grades** button below the questions MUST save all the grades of the page at
  once. After a save the teacher MUST stay on the page with the saved grades in their fields and the
  notice "Grades of “<team>” were saved".
- **FR-025**: A grade MUST be trimmed of spaces, entered as digits only, and be a whole number from 0
  to 10 ("0", "7", "10"). Anything else ("7.5", "-1", "11", "seven") MUST get the error "Enter a whole
  number from 0 to 10.". If any grade is invalid, nothing MUST be saved, and the page MUST show again
  with every entered value kept, the error at each invalid grade and the error summary linking to them,
  in the order of the questions. The server MUST check every grade on every save, whatever the browser
  did.
- **FR-026**: A team with no answers MUST show every question with "Not answered", the text "“<team>”
  gave no answers, so there is nothing to grade" and no **Save grades** button. A competition with no
  questions MUST show "No questions in this competition" and no **Save grades** button.
- **FR-027**: Grades MUST be changeable at any time while the competition is **Finished**; there MUST be
  no step that closes grading. A saved grade MUST be shown on the team's read-only answer sheet at once.

#### Grades and scores

- **FR-028**: A grade MUST belong to one team's answer: at most one whole-number grade from 0 to 10 per
  answer. A question the team did not answer MUST have no grade. Who graded an answer, or when, MUST NOT
  be stored; a grade is not personal data.
- **FR-029**: A team's score MUST be the sum of its saved grades, calculated from them whenever it is
  shown and never stored apart from them (constitution, Principle VII). Ungraded answers MUST add
  nothing.
- **FR-030**: Grades MUST NOT be reserved for a teacher. Each **Save grades** MUST store every grade of
  its page, and the last save MUST win: it replaces the grades an earlier save stored, emptied ones
  included, with no warning and no refusal. A save MUST be stored as a whole, so the team's grades are
  always those of one save, also when two saves arrive at the same moment.

#### Read access to answers

- **FR-031**: On the **Competitions** tab, a teacher with **Read** access to an institution MUST see
  everything a teacher with **Write** access sees; only **Write** access MUST enter and change answers.
  **Read** access on the other tabs (**Students**, **Teams**) MUST stay as it is.
- **FR-032**: On the Answers page of an **In progress** competition, a team of a **Write**-access
  institution MUST keep **Enter answers**, and a team of a **Read**-access institution MUST have **View
  answers** in place of the row note "Read access".
- **FR-033**: **View answers** on an **In progress** competition MUST open the read-only answer sheet
  with the notice "You have Read access to “<institution>”, so you cannot change these answers." under
  the heading. It MUST show the answers as they are stored when it is opened, with no grades and no
  score, and MUST NOT refresh on its own.
- **FR-034**: An answer save for a team of a **Read**-access institution, typed or from an answer sheet
  opened before the teacher's access was lowered to **Read**, MUST get "access denied" and change
  nothing; the answers saved before MUST stay. When the access is raised to **Write**, the team MUST
  have **Enter answers** on the next page shown.
- **FR-035**: The teacher's links MUST be read on every request, as in milestone 12.3: an unlinked
  institution's teams MUST leave the page at once, and their sheets MUST get "access denied".

#### Answers after finishing

- **FR-036**: On a **Finished** competition the Answers pages of milestone 12.3 MUST be read-only. The
  page "Answers of “<name>”" MUST be the 12.3 page, with the same teams (only those of the teacher's
  own institutions; deleted teams and teams of a deactivated institution or region not listed), region
  boxes, order, paging, **Answered** column and empty states. A deactivated institution or region MUST
  give no access to its teams' answers, grades or scores; its teams MUST be listed again when it is
  activated again.
- **FR-037**: After **Answered**, the page of a finished competition MUST show the **Graded** and
  **Score** columns of the Grades page, counted the same way, for every listed team, and every listed
  team MUST have **View answers**, with **Read** or **Write** access.
- **FR-038**: **View answers** MUST open the read-only sheet "Answers of “<team>” in “<competition>”",
  with the team's institution under the heading and a back link to the Answers page at the page the
  teacher came from, at that team. It MUST show every question in the competition's order, numbered from
  1, each with its copied text and the team's answer labelled "Answer to question <n>", read-only with
  its line breaks kept, or "Not answered". It MUST never show the reference answer, and MUST have no
  fields and no save button. A competition with no questions MUST show "No questions in this
  competition".
- **FR-039**: On a **Finished** competition the read-only sheet MUST also show the team's score "Score:
  <sum>" ("Score: 0" when none is graded or the team has no answers) with "Graded <graded> of <answers>
  answers", and under each answered question "Grade: <grade> of 10" once it is graded and "Not graded
  yet" until then.
- **FR-040**: An answer save sent to a finished competition, from a sheet opened before it finished or
  typed, MUST get the 12.3 refusal "“<name>” has finished, so its answers can no longer be entered." and
  change nothing. An **Upcoming** or **Cancelled** competition MUST keep the 12.3 refusals on every
  Answers page and save.
- **FR-041**: The Answers pages MUST keep the checks of milestone 12.3 in the same order: the role; the
  subject and the competition (a competition of a deactivated subject is "not found" only when it is not
  **Finished**); the status (an **In progress** competition opens the pages and accepts a save; a
  **Finished** one opens the read-only pages and refuses a save; an **Upcoming** or **Cancelled** one
  shows the 12.3 refusal); the team ("not found" for an unknown or deleted team, a team not in the
  competition, or a team of a deactivated institution or region); the access to the team (a team of an
  institution the teacher is not linked to gets "access denied" on its sheet and its save; with **Read**
  access the sheet opens read-only and a save gets "access denied"; with **Write** access the sheet of an
  **In progress** competition is the answer sheet).

#### Deactivated subjects

- **FR-042**: A finished competition of a deactivated subject MUST stay listed and available (milestone
  12.1), with **Answers** and **Grades** in its menu where FR-005 and FR-006 offer them; its Answers
  pages MUST open as on any finished competition, and its answers MUST still be gradable. Grading MUST
  change nothing else about it. A competition of a deactivated subject that is not **Finished** MUST
  stay hidden and "not found".

#### Checks and refusals

- **FR-043**: Every page and action of finishing and grading MUST check everything again when it is
  opened or sent, whatever the page showed, and again when a change is stored. The checks MUST run in
  this order, and the first failing one MUST decide the answer:
  1. the role: anyone who is not a teacher gets "access denied", before any id is read;
  2. the setting: a teacher without **Can manage competitions** gets "access denied", before any id or
     subject is read;
  3. the subject and the competition: an unknown subject or competition, a competition of another
     subject, or a competition of a deactivated subject that is not **Finished** shows "not found", as in
     milestone 12.1;
  4. the status: finishing a competition that is not **In progress** shows the refusal of FR-012;
     opening the Grades page or a grading sheet, or sending a grading save, on a competition that is not
     **Finished** shows the refusal of FR-044;
  5. the team and the questions (grading sheet and save): an unknown team or a team that is not in the
     competition shows "not found"; so does a save that names a question that is not one of the
     competition's, or one the team did not answer, and then nothing is saved. A deleted team, or one of
     a deactivated institution or region, is found;
  6. the grades (save): the error of FR-025.
- **FR-044**: For a competition that is not **Finished**, the Grades page, the grading sheet and the
  grading save MUST show the refusal "Grade answers of “<name>”?" with the reason for its status: "“…”
  has not started yet, so its answers cannot be graded." (**Upcoming**), "“…” is still in progress, so
  its answers cannot be graded until it is finished." (**In progress**) or "“…” has been cancelled, so
  its answers cannot be graded." (**Cancelled**), and the link **Back to competitions** to the list page
  the teacher came from, at the competition. A save sent then MUST change nothing.

#### Shared page and action behaviour

- **FR-045**: Every finish and every save MUST be a form submission that passes the existing cross-site
  request check. Opening a page or following a link MUST never change anything, and reloading a page
  after a finish or a save MUST never repeat it. No log line MUST contain an email address or a
  person's name; answers and grades are not personal data and are under no special logging rule.
- **FR-046**: Every page of this milestone MUST follow the UI guidelines, including the loading feedback
  and busy button of milestone 10.1, and MUST work on a phone-width screen without sideways page
  scrolling.

#### Components and UI guidelines

- **FR-047**: The UI guidelines MUST be updated in the same change for the rules this milestone changes:
  - **Actions menu**: the entries on the **Competitions** tab are, in this order, **Edit**,
    **Questions**, **Teams**, **Answers**, **Grades**, **Finish competition** and **Cancel competition**,
    and the example shows **Answers** on **In progress** and **Finished** competitions, **Grades** and a
    **Finish competition** entry that is not destructive;
  - **Confirmations**: the link back says what is kept whenever the verb ends something, not only when
    it is "Cancel …" (**Cancel competition** / **Keep competition**, **Finish competition** / **Keep in
    progress**); "Every destructive action goes through a confirmation page" (in **Forgiving** and under
    **Confirmations**) and the **destructive** row of the button kinds are replaced by the rule of the
    non-destructive confirmation (FR-048);
  - **Wording patterns**: the consequence of a confirmation says plainly what will happen in one to
    three short sentences, the first one saying what happens to the item, instead of "one plain
    sentence"; the row note "Read access" leaves the examples of row notes.
- **FR-048**: Three patterns MUST be new, each added to the component library, the component gallery
  (`/admin/components`) and the UI guidelines before any page uses it:
  - the **confirmation of an action that cannot be undone but is not destructive**: the 12.1
    confirmation with a primary confirming button instead of a destructive one. The UI guidelines MUST
    gain the rule that every action that cannot be undone goes through a confirmation page. Its button
    is destructive when the action has a high impact that cannot be reverted and that the person may
    regret: it removes, hides or calls off something (**Delete**, **Deactivate**, **Withdraw consent**,
    **Cancel competition**). An action that cannot be undone but is the normal next step of the work,
    such as **Finish competition**, has a primary button;
  - the **grading sheet**: a numbered list of questions, each a text card with the question's text, the
    reference answer and the participant's answer as labelled read-only texts, and its grade field
    under them (or "Not answered" and no field), one error per grade, and one primary save button below
    the list, with labelled grades and the phone layout of the guidelines. The answer is labelled
    "Answer to question <n>". Its **read-only variant** shows the grade as text ("Grade: 7 of 10", "Not
    graded yet") instead of the field, has no save button and leaves the reference answer out; for a
    competition still **In progress** it also leaves the grades out;
  - the **filter links**: a row of plain links above a list, each one a filter of it, the current one
    marked `aria-current="true"` (not `"page"`) and drawn as the current page of the page navigation;
    following a link goes to page 1 of the filtered list. They need no JavaScript and no **Show**
    button.
- **FR-049**: Apart from these, the pages MUST be built from existing components: the section heading,
  the region group, data tables, page navigation, text cards, the error summary, notices, empty states,
  the confirmation and refusal pages, back links, the local-time display and the competition status
  badge.

#### Rules already written down

- **FR-050**: The product requirements and the constitution v2.3.0 (Principles IV and VII) already state
  the rules of this milestone: only a teacher allowed to manage competitions stops and grades, only once
  the competition is finished, and the answers of every team in it; grading adds or changes grades
  only; **Read** and **Write** access see the same in competitions and only **Write** enters answers; a
  team's score is the sum of its stored grades and is not stored apart from them; finished competitions
  of a deactivated subject can still be graded. The implementation MUST NOT contradict them; no further
  amendment is needed.

#### Verification and scope

- **FR-051**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" list (items 1–17): the menu per status and setting; finishing, its landings,
  its refusals, the start passing and the concurrent and repeated finishes; answer saves refused after
  finishing; the read-only Answers pages after finishing and while **In progress** for **Read**,
  **Write** and mixed access, with and without the setting; the Grades page, its columns, overall
  progress and empty state; the filter links and every back-link landing; the grading sheet; saving,
  changing and emptying grades; every invalid grade; two teachers grading the same team; the grading
  refusals; every "not found" and "access denied" case and the check order; the deactivated-subject
  cases; the cross-site request check; and the gallery.
- **FR-052**: This milestone MUST NOT add anything listed under **Out of Scope** below.

### Key Entities *(include if feature involves data)*

- **Grade** (new): the grade of one team's answer to one question of one finished competition, a whole
  number from 0 to 10. It belongs to exactly one team answer, and an answer has at most one grade; an
  unanswered question has none. It stores neither who graded nor when, and is not personal data. It is
  kept with its answer: a finished competition keeps its teams and answers, deleted teams included.
- **Team score** (derived, not stored): the sum of a team's saved grades in one competition; 0 when none
  is graded.
- **Competition** (existing, milestones 12.1–12.3): now records the moment a teacher finished it; its
  **Finished** status is derived from that, as **Cancelled** is from its cancellation. Finishing and
  cancelling exclude each other.
- **Team answer** (existing, milestone 12.3): never changes after its competition finished; now may
  carry a grade.
- **Teacher's link to an institution** (existing, milestone 8): on the **Competitions** tab, **Read**
  now reads a team's answers, grades and score; **Write** also enters answers. Read on every request.
- **Teacher's Can manage competitions setting** (existing, milestone 8): now also finishes competitions
  and grades answers; read on every request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the competitions list, a teacher with the setting finishes a competition with three
  choices (**Actions**, **Finish competition**, **Finish competition**), and reaches a team's grading
  sheet with three (**Actions**, **Grades**, **Grade answers**), grading all its answers with one press
  of **Save grades**.
- **SC-002**: In the automated access check, 100% of pages and actions of finishing and grading refuse
  the administrator and student roles, and teachers without the setting, before any id is read; 100% of
  read-only answer sheets of a team of an unlinked institution get "access denied"; and 100% of requests
  naming an unknown, mismatched or hidden subject, competition, team or question get "not found", with
  nothing changed in every case.
- **SC-003**: 0 grades are saved, changed or removed for a competition that is not **Finished**, and 0
  answers are saved, changed or removed for a competition after it finished.
- **SC-004**: In 100% of concurrent and repeated finishes, and finish-and-cancel pairs, exactly one
  change is stored.
- **SC-005**: 0 reference answers appear on any Answers page, and 0 answers, grades or scores of a team
  of an institution the teacher is not linked to appear on the Answers pages.
- **SC-006**: 100% of refused grading saves (an invalid grade, a refusal, "not found", "access denied")
  store nothing, and 100% of saves with an invalid grade show the page again with every entered value
  kept.
- **SC-007**: The **Graded**, **Score** and overall progress values on the Grades and Answers pages, and
  the score on the read-only sheet, equal the values counted from the stored grades in 100% of the
  tested cases.
- **SC-008**: After two grading saves of the same team, also at the same moment, the stored grades are
  exactly those of one save in 100% of the tested cases.
- **SC-009**: Every page of this milestone is usable at 360 px width with no sideways page scrolling.
- **SC-010**: Reloading the page after a finish or a save never repeats it.
- **SC-011**: All tests from milestones 1–12.3 still pass, apart from those of the rules this milestone
  changes: the actions menu of **In progress** and **Finished** competitions; the 12.3 row note "Read
  access" and "access denied" on the answer sheet of a **Read**-access team; the 12.3 refusal on the
  Answers pages of a **Finished** competition, which now open read-only; "not found" for the Answers
  pages of a finished competition of a deactivated subject; and the UI guideline examples changed by
  FR-047.

## Assumptions

- **The Read access notice appears only while the competition is In progress.** The milestone gives it
  under "Read access to answers", where it explains why the sheet cannot be changed; once finished,
  nobody can change the answers, so the read-only sheet has no access notice for either access level.
- **Counts follow the number's noun**: "Graded 1 of 1 team" and "Graded 1 of 1 answer", as the region
  headers say "1 team". A team with no answers reads "Score: 0" with "Graded 0 of 0 answers".
- **A grade is the digits 0–9 only, after trimming spaces, with a value from 0 to 10**: "07" is
  accepted as 7; "+7", "7.0", "1e1" and digits of other scripts get the error "Enter a whole number from
  0 to 10."; a value made only of spaces is trimmed to empty, so the answer is not graded. The browser
  may offer a numeric keypad, but the field accepts whatever is typed and the server decides.
- **A grading save that does not name an answered question** (only a crafted form can omit one) leaves
  that answer's grade as it is.
- **A save with nothing changed** is accepted and shows the notice.
- **The phone card's lines carry the column labels**: "Answered 4 of 10", "Graded 3 of 4", "Score 17".
- **The moment of finishing is stored but not shown** anywhere in this milestone; the competitions list
  keeps showing the start.
- **An unknown filter value on the Grades page** is taken as **All teams**; a page number beyond the
  last page, or not a number, opens the nearest valid page.
- **The back links of the sheets** carry the list page's page number (and, for the Grades page, its
  filter); when missing or invalid they lead to the page holding the team under **All teams**.
- **The read-only answer sheet is reached by its own entry, View answers**; opening the answer sheet's
  address of a **Finished** competition, or of a **Read**-access team while **In progress**, shows the
  read-only sheet, as the milestone's checks say ("opens the read-only pages").
- **The empty states have no hint**, as in milestone 12.3.
- **Tests control the current time**, so that a start can pass while a refusal is shown.
- **Every quoted text above** is taken from the milestone where the milestone gives it; the texts it only
  implies (the count nouns, the phone lines) follow the existing patterns.

## Dependencies

- **Constitution v2.3.0** (amended on 2026-11-14): Principle IV (who stops and grades, grading adds or
  changes grades only, **Read** access sees answers, grades and scores read-only, finished competitions
  of a deactivated subject can be graded) and Principle VII (the status derived from the stored start
  and the stored stop or cancel; grades persisted; scores calculated from them).
- **Product requirements** (updated with the milestone): the "Teacher access rights", "Personal data",
  "How a competition works", "Competition statuses", **Team** and **Subject** sections.
- **Milestone 5**: roles, "access denied" and the automated route check.
- **Milestone 7**: regions and educational institutions and their deactivation.
- **Milestone 8**: teachers' links, **Read** and **Write** access, and **Can manage competitions**.
- **Milestone 10 and 10.1**: the component library, the gallery, the UI guidelines, the loading feedback
  and the busy button.
- **Milestone 11**: text cards, read-only texts with line breaks, the error summary.
- **Milestone 11.1**: teams, their active members and their deletion.
- **Milestone 12.1**: competitions, statuses, the actions menu, the cancel confirmation and its landing
  rules, the refusal pattern, live-name uniqueness and the deactivated-subject rules.
- **Milestone 12.2**: a competition's copied questions and reference answers, its teams, the **Teams**
  page and the region group.
- **Milestone 12.3**: the team answers, the Answers page, the answer sheet and its refusals.
- **Later milestones that depend on this one**: milestone 13 lets students enter answers while a
  competition is **In progress** and see their own teams' results; milestone 14 proposes grades on the
  same 0–10 scale that a teacher with the setting can adjust; milestone 15 shows best answers, scores
  and places from the stored grades. Milestones 14 and 15 are refined after this milestone is shown to
  the product owner.

## Out of Scope

- Evaluation of answers by an LLM, proposed grades or their justification (milestone 14).
- Best answers, places, a winner or a results page (milestone 15).
- Students entering answers or seeing their grades (milestone 13).
- A step that closes grading, or locking grades.
- Grading per question across all teams, or grading from the Answers pages.
- Storing who graded an answer or when, keeping earlier grades, or comments on a grade.
- Reserving a team's grading sheet for a teacher, warning about another teacher's save, or refusing a
  save made over it.
- Restarting, reopening or un-finishing a competition, and finishing a competition on its own at a set
  time.
- Showing the moment a competition finished.
- Grades or scores in the competitions list or on the **Teams** page.
- Page navigation on the grading sheet or the read-only sheet.
- Showing the reference answer on the Answers pages.
- Changing **Read** access on the **Students** or **Teams** tabs.
