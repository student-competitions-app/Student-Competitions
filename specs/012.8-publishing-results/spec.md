# Feature Specification: Publishing a Competition's Results as PDF Files (Teacher) (Milestone 12.8)

**Feature Branch**: `012.8-publishing-results`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "create specification for 12.8 publishing results": milestone 12.8 of
`docs/requirements/milestones.md` ("Publishing a competition's results as PDF files (teacher)"), the
last of the 12.x group "Competitions", with `product-requirements.md` (the "How a competition works",
"Teacher access rights", "Personal data", "Competition statuses" and "Published results" sections),
`technical-requirements.md` (the "Results files" row), the constitution v2.5.0 (Principles II, IV and
VII and the "Results files" row of the technology stack), the milestone 10, 10.1, 12.1, 12.2, 12.3,
12.4, 12.5 and 12.7 specifications and `docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 12.8 of the walking skeleton for the Student Competitions application, and the last of the
12.x milestones that build the teacher's side of competitions. After milestone 12.4, a teacher with
**Can manage competitions** finishes a competition and grades every team's answers, but the grades
can change at any time, nothing marks the end of grading, and nobody can hand the results to anyone.

This milestone lets a teacher with **Can manage competitions** **publish** the results of a fully
graded **Finished** competition. Publishing is permanent: it freezes the competition's grades, gives
it the new status **Published** and makes two PDF files of its results, one in Ukrainian and one in
English, which are stored with the competition as the official, unchangeable confirmation of its
results. From then on every teacher can download the file in the current site language from the
actions menu, since the published results are open information, like the results of a school
competition. Nine things become true when this milestone is done:

1. **The actions menu gains Publish results and Download results.** The entries read, in this order,
   **Edit**, **Questions**, **Teams**, **Answers**, **Grades**, **Publish results**, **Download
   results**, **Finish competition** and **Cancel competition**, each where it is available.
2. **A teacher with the setting publishes a fully graded finished competition** on a confirmation
   page with a primary, not destructive, **Publish results** button. A competition with an ungraded
   team cannot be published; the page then shows the progress and leads to the teams left to grade.
3. **Publishing is refused with a reason** for a competition that is not **Finished**, and when two
   requests meet, the first wins.
4. **The new status Published** is shown with its own badge and has its own status filter; **Finished**
   now lists only the finished competitions whose results are not published yet.
5. **The grades of a published competition are frozen**: every grading sheet becomes read-only, and a
   grade save is refused.
6. **Two results files are made and stored at publishing**: a header with the logo, then the teams by
   region, institution and team, each with its score, in Ukrainian and in English. They are never made
   again or changed.
7. **Every teacher downloads the stored file** of the current site language straight from the menu,
   named after the competition and its start date.
8. **The product owner approves the design of the files** in review rounds on sample files made from
   realistic data, as in milestone 12.7.
9. **The Published badge, the download entry of the actions menu, the read-only grading sheet and
   the blocked confirmation** are added to the component library, the component gallery
   (`/admin/components`) and the UI guidelines before any page uses them.

## Clarifications

### Session 2026-11-21 (design review round 1)

- Q: What should the header show besides the dates? → A: Under "Published", the maximum score a team
  could get: "Maximum score: 40" («Максимальний бал: 40»), 10 (the grade scale's maximum) for each of
  the competition's questions, so a reader can judge every score against it (FR-023).
- Q: How are a region's teams laid out? → A: As a table under the region's heading, with the columns
  "Educational institution", "Team" and "Score" («Заклад освіти», «Команда», «Бал»), one row per
  team. The score column is just wide enough to show the score (or its heading, if wider); the other
  two share the rest of the width, and long names wrap within their cell. A table that continues on
  a new page repeats its heading row (FR-025).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A teacher with the setting publishes the results of a graded competition (Priority: P1)

Olena has **Can manage competitions**. "Spring round" of "Chemistry" started on 14 March 2027 at 10:00,
was finished, and she has graded all its 52 teams. On the **Competitions** tab, with the status
**All**, she opens the **Actions** menu of "Spring round", which lists **Questions**, **Teams**,
**Answers**, **Grades** and **Publish results**, and chooses **Publish results**. The page asks
"Publish the results of “Spring round” of Chemistry, started 14 March 2027, 10:00?", shows the
**Finished** badge, "Graded 52 of 52 teams" and the consequence "The results will be published for
every teacher as PDF files in Ukrainian and English. Publishing is permanent: the results cannot be
unpublished, and the grades can no longer be changed.". She presses the primary button **Publish
results**. She is back on the same list page, at "Spring round", which now shows **Published**, with
the notice "The results of “Spring round” were published". Its menu now lists **Questions**,
**Teams**, **Answers**, **Grades** and **Download results**.

**Why this priority**: Publishing is the purpose of this milestone and the only way to the results
files; without it nothing else of this milestone can be reached.

**Independent Test**: As a teacher with the setting, publish a fully graded **Finished** competition
from the list under each status filter, and check the confirmation, **Keep unpublished**, the notice,
the landing row, the new status, the menu and that exactly two files are stored.

**Acceptance Scenarios**:

1. **Given** a fully graded **Finished** competition, **When** Olena chooses **Publish results**,
   **Then** the confirmation page asks "Publish the results of “Spring round” of Chemistry, started 14
   March 2027, 10:00?" (the start in her time zone), shows the **Finished** badge, the progress
   "Graded 52 of 52 teams" counted as on the **Grades** page, and the consequence "The results will be
   published for every teacher as PDF files in Ukrainian and English. Publishing is permanent: the
   results cannot be unpublished, and the grades can no longer be changed.", and has the primary (not
   destructive) button **Publish results** and the link **Keep unpublished**.
2. **Given** the confirmation, **When** she follows **Keep unpublished**, **Then** she returns to the
   list page she came from, at the competition, and nothing has changed.
3. **Given** she confirms under the status filter **All** or **Published**, **When** the list is shown
   again, **Then** it keeps the same subject, status filter and page, she lands at the competition,
   which now shows **Published**, and the notice reads "The results of “Spring round” were published".
4. **Given** she confirms under the status filter **Finished**, **When** the list is shown again,
   **Then** the competition is no longer listed, and she lands as after finishing a competition under
   **In progress** (milestone 12.4): at the row that took its place, at the row before it if none did,
   on the previous page at its last row if the page is now empty, or on the empty state if no row is
   left; the notice is shown as well.
5. **Given** the publish succeeded, **When** the stored data is inspected, **Then** the competition
   records the moment it was published and holds exactly two results files, one in Ukrainian and one in
   English, made in the same step as the status change.
6. **Given** a publish, **When** the page is reloaded, **Then** nothing is sent again.

---

### User Story 2 - Publishing waits until every team is graded (Priority: P1)

Olena opens **Publish results** on "Autumn round", which is finished but has 15 teams with ungraded
answers. The confirmation shows "Graded 37 of 52 teams", the explanation "Every team must be graded
before the results can be published.", the link **Grade the remaining teams** and the link **Keep
unpublished**, and no **Publish results** button. She follows **Grade the remaining teams**, which
opens **Grades** of "Autumn round" with **Ungraded only**, and grades the rest. When she opens the
confirmation again it shows "Graded 52 of 52 teams" and the **Publish results** button. "Winter round"
was finished with no teams; its confirmation shows "Graded 0 of 0 teams" and can be published.

**Why this priority**: Published results are final; publishing a competition with ungraded answers
would freeze wrong scores into the official files for good.

**Independent Test**: Seed finished competitions with partly graded teams, teams with no answers and
no teams; open the confirmation, follow its links, send a publish through a crafted form for a
competition with an ungraded team, and check the progress, the explanation, the missing button, the
refusal and that nothing is stored.

**Acceptance Scenarios**:

1. **Given** a **Finished** competition with at least one team that has an answer without a grade,
   **When** the confirmation is opened, **Then** it shows the progress ("Graded 37 of 52 teams"), the
   explanation "Every team must be graded before the results can be published.", the link **Grade the
   remaining teams** and the link **Keep unpublished**, and no **Publish results** button.
2. **Given** that page, **When** **Grade the remaining teams** is followed, **Then** it opens the
   **Grades** page of the competition with the filter **Ungraded only**, page 1, whose back link still
   leads to the list page the teacher came from, at the competition.
3. **Given** a competition with an ungraded team, **When** a publish is sent anyway (a crafted form, or
   a confirmation opened before a grade was emptied), **Then** the confirmation page is shown again
   with the progress and the explanation "Every team must be graded before the results can be
   published.", and nothing changes: no status, no files.
4. **Given** a team with no answers, **When** the progress is counted, **Then** it counts as fully
   graded (milestone 12.4).
5. **Given** a **Finished** competition with no teams, **When** the confirmation is opened, **Then** it
   shows "Graded 0 of 0 teams" and the **Publish results** button, and publishing it succeeds; its
   files say "No teams took part in this competition." under the header.

---

### User Story 3 - Publishing is refused for the wrong status, and the first wins (Priority: P1)

Olena types the publish address of the in-progress "Summer round" and sees "Publish the results of
“Summer round”?" with "“Summer round” is still in progress. Finish it and grade its answers before
publishing its results." and the link **Back to competitions**. Olena and her colleague Petro, both
with the setting, open the confirmation of "Spring round" at the same time; Olena confirms first, and
Petro's confirmation gets "The results of “Spring round” are already published.". Petro had also just
emptied a grade of "Comets" in another tab; because his save arrived first, Olena's publish was
refused as not fully graded.

**Why this priority**: Publishing is permanent; publishing the wrong competition, publishing twice or
freezing a grade that is being changed would leave official results that cannot be repaired.

**Independent Test**: Send the confirmation and the publish for an **Upcoming**, an **In progress**, a
**Cancelled** and a **Published** competition; send two publishes, a publish and a grade save, and the
same form twice, at the same moment; check the refusals, their reasons and links, and that exactly
one change and exactly two files were stored.

**Acceptance Scenarios**:

1. **Given** an **Upcoming** competition (typed address), **When** its publish confirmation is opened
   or a publish is sent, **Then** the refusal "Publish the results of “Autumn round”?" shows the reason
   "“Autumn round” has not started yet, so it has no results to publish." and the link **Back to
   competitions**, and nothing changes.
2. **Given** an **In progress** competition, **Then** the reason reads "“Summer round” is still in
   progress. Finish it and grade its answers before publishing its results."; **Given** a **Cancelled**
   one, **Then** "“Spring round” has been cancelled, so it has no results to publish."; **Given** a
   **Published** one, **Then** "The results of “Spring round” are already published.".
3. **Given** a refusal, **When** **Back to competitions** is followed, **Then** it leads to the list
   page the teacher came from, at the competition.
4. **Given** two teachers publish the same competition at the same time, **When** both are handled,
   **Then** exactly one succeeds and makes the files, and the other gets "The results of “Spring round”
   are already published."; the competition holds exactly two files.
5. **Given** a grade save and a publish of the same competition at the same time, **When** the grade
   save is handled first, **Then** the grade counts, and the publish succeeds with it in the files, or
   is refused as not fully graded when the save emptied a grade; **When** the publish is handled first,
   **Then** the grade save is refused with the note of User Story 5 and nothing changes.
6. **Given** the same publish form sent twice, **When** both requests are handled, **Then** the results
   are published once, and the second request gets "The results of “Spring round” are already
   published.".

---

### User Story 4 - The Published status is shown and filtered (Priority: P1)

On the **Competitions** tab "Spring round" now shows the new **Published** badge. The status filter
reads **All**, **Upcoming**, **In progress**, **Finished**, **Published** and **Cancelled**; under
**Finished** "Spring round" is no longer listed, and under **Published** it is. Its **Questions** and
**Teams** pages are read-only, its **Answers** pages show the teams' answers, grades and scores
read-only to the teachers of their institutions, and its **Grades** page still lists every team with
its score. When the administrator deactivates "Chemistry", "Spring round" stays listed and usable.

**Why this priority**: The status is how teachers tell published results from results that may still
change, and how they find the competitions they can download.

**Independent Test**: Seed competitions of every status, publish one, and check the badges on every
page that shows a status, the filter values and their lists, the pages offered on the published
competition, the finished-competition rules and the deactivated-subject case.

**Acceptance Scenarios**:

1. **Given** a published competition, **When** any page that shows a competition's status badge is
   shown, **Then** it shows the **Published** badge.
2. **Given** the status filter of the **Competitions** tab, **When** it is shown, **Then** it offers
   **Published** after **Finished**; **Published** lists only the published competitions, and
   **Finished** lists only the finished competitions whose results are not published yet; **All**
   lists both.
3. **Given** a published competition, **When** its menu is shown, **Then** it offers the pages offered
   on a **Finished** competition (the read-only **Questions** and **Teams**, **Answers** and, with the
   setting, **Grades**), and they open as on a **Finished** competition.
4. **Given** a published competition, **When** anyone tries to change its questions, teams or answers,
   cancel it, or edit it, **Then** it is refused as for a **Finished** competition; its deleted teams
   stay in it; its name stays free in its subject (milestone 12.1).
5. **Given** the subject of a published competition is deactivated, **When** the competitions list and
   its pages are opened, **Then** the competition stays available, as a finished one does, and its
   results can be downloaded.

---

### User Story 5 - The grades of a published competition are frozen (Priority: P1)

After "Spring round" is published, Olena opens **Grades** and then the grading sheet of "Comets". Under
the heading she sees "The results of “Spring round” are published, so its grades can no longer be
changed."; every grade is shown as text ("Grade: 7 of 10") instead of a field, and there is no **Save
grades** button. A save she sends from a sheet opened before publishing is refused with the same note,
and the grade stays as it was.

**Why this priority**: Results that change after they are announced would invite complaints from
participants and contradict the stored files.

**Independent Test**: Publish a graded competition, then open its Grades page and grading sheets, send
grade saves from a sheet opened before publishing and through a crafted form, and check the note, the
read-only grades, the missing button, the refusal and that no grade changed.

**Acceptance Scenarios**:

1. **Given** a **Published** competition, **When** a teacher with the setting opens a grading sheet,
   **Then** it shows the note "The results of “Spring round” are published, so its grades can no longer
   be changed.", each question with its reference answer, the team's answer and its grade as text, and
   no grade field and no **Save grades** button.
2. **Given** a **Published** competition, **When** a grade save is sent (from a sheet opened before
   publishing, or a crafted form), **Then** the sheet is shown read-only with the same note, and no
   grade is saved, changed or emptied.
3. **Given** a **Published** competition, **When** its **Grades** page and the read-only **Answers**
   pages are shown, **Then** they show the same teams, columns, grades and scores as before publishing.
4. **Given** a **Published** competition, **When** its menu is shown, **Then** it no longer offers
   **Publish results**; there is no way to unpublish it.

---

### User Story 6 - The results files hold the official results (Priority: P1)

The Ukrainian file of "Spring round" starts with the logo, the title "Results of “Spring round”" in
Ukrainian, "Chemistry", the start and the finish date and time in Kyiv time, labelled, the date of
publishing and "Maximum score: 40". Then come the regions in Ukrainian alphabetical order, each with a
heading over a table of its teams, ordered by institution and then by team, with the columns
"Educational institution", "Team" and "Score", such as the row "School No. 5 | Comets | 17". The
deleted team "Meteors" is listed with its score like every other team. The list runs over three pages,
each numbered ("Page 2 of 3"). The English file shows the same teams and scores with the English
labels. A month later the school is renamed and "Comets" is deleted; both files still show the row
"School No. 5 | Comets | 17".

**Why this priority**: The files are the official confirmation of the results; their content and
their permanence are what publishing is for.

**Independent Test**: Seed a fully graded competition with teams in several regions, of deactivated
and renamed institutions, a deleted team, Cyrillic and long names and enough teams to fill several
pages; publish it, read the text of both files, then rename, deactivate and delete regions,
institutions and teams, and compare the stored files with the ones read before.

**Acceptance Scenarios**:

1. **Given** a published competition, **When** either file is read, **Then** it starts with a header
   holding the logo of milestone 12.7, the title "Results of “<name>”", the subject, the start and
   finish date and time, the date of publishing, the times in Kyiv time and labelled as such, and the
   maximum score (10 for each of the competition's questions).
2. **Given** the header, **When** the teams follow, **Then** there is a heading for each region, and
   under it a table with the columns "Educational institution", "Team" and "Score" and one row per
   team, its score the sum of its grades ("School No. 5 | Comets | 17"); a team with no answers has
   the score 0. The score column is just wide enough for the score, and a table continued on a new
   page repeats its heading row.
3. **Given** teams of several regions and institutions, **When** they are listed, **Then** the regions,
   the institutions within a region and the teams within an institution are in alphabetical order by
   the Ukrainian alphabet rule of milestone 12.5, in both files.
4. **Given** a team deleted before publishing, or a team of an institution or region that was
   deactivated, **When** the files are made, **Then** the team is listed with its score like every other
   team.
5. **Given** the Ukrainian file, **When** it is read, **Then** every label is in Ukrainian; **Given**
   the English file, **Then** every label is in English; the names of the competition, subject, regions,
   institutions and teams are shown as entered in both, never translated, and Cyrillic letters render
   correctly.
6. **Given** the files, **When** their text is read, **Then** they hold only each team's region,
   institution, name and score, never an answer, a reference answer, a question, a grade per question
   or a team member.
7. **Given** a list longer than one page, **When** the file is read, **Then** the list continues across
   pages and every page is numbered "Page <n> of <total>".
8. **Given** the files were made, **When** a region, institution or team is later renamed, deactivated
   or deleted, or the subject is renamed or deactivated, **Then** the stored files are unchanged, byte
   for byte, and still show the names and scores as they were at publishing.

---

### User Story 7 - Every teacher downloads the results (Priority: P1)

Taras has no **Can manage competitions** and is linked only to School No. 5, which has no team in
"Spring round". Its menu lists **Questions**, **Teams**, **Answers** and **Download results**. He
chooses **Download results**: the browser saves "Spring round 2027-03-14.pdf" straight away, in
Ukrainian because the site is in Ukrainian, and he stays on the list. He switches the site to English
and downloads again: the file is the English one. The loading bar does not appear.

**Why this priority**: Handing the results to the teachers is the purpose of the files; the published
results are open information for every teacher.

**Independent Test**: As teachers with **Read** and **Write** access, with and without the setting,
linked and not linked to the teams' institutions, download the results in both languages and compare
the bytes with the stored files; check the menu on every status, the link's download marking, the file
name, the 404 for other statuses and the refusal for administrators and students.

**Acceptance Scenarios**:

1. **Given** a **Published** competition, **When** any teacher opens its menu, **Then** it offers
   **Download results**, with **Read** or **Write** access, with or without the setting, and whatever
   institutions the competition's teams belong to; **Given** a competition of any other status,
   **Then** it does not.
2. **Given** **Download results**, **When** it is chosen, **Then** the stored file of the current site
   language is downloaded at once, byte for byte as stored, with no page in between, and the teacher
   stays on the list.
3. **Given** the site language is switched, **When** **Download results** is chosen again, **Then** the
   file of the new language is downloaded.
4. **Given** **Download results**, **When** its link is inspected, **Then** it is a link marked as a
   download, and the loading bar of milestone 10.1 does not start for it and never stays on the screen.
5. **Given** a download, **When** the file is saved, **Then** it is named "<name> <YYYY-MM-DD>.pdf"
   after the competition's name and its start date in Kyiv time ("Spring round 2027-03-14.pdf");
   characters a file name cannot hold are replaced, and a Cyrillic name is kept.
6. **Given** a competition that is not **Published**, or an unknown one, **When** its download address
   is requested by a teacher, **Then** it answers 404 with the page "Competition not found" (milestone
   12.1).
7. **Given** an administrator or a student, **When** they request a download address, also with an
   unknown id, **Then** they get "access denied" before any id is read; neither role is ever offered
   the entry.

---

### User Story 8 - The product owner approves the design of the files (Priority: P2)

Before the milestone is done, the product owner reviews sample files in both languages made from
realistic data: several regions, long institution and team names, Cyrillic text, a list long enough to
continue across pages, and a competition with no teams. They ask for a larger logo and more space
between regions; the changes are made and the samples are made again for the next round, until they
approve the design.

**Why this priority**: The files are the face of the competition to schools and families; their look
is a product decision, but it adds no capability that teachers cannot test without it.

**Independent Test**: Make the sample files with the repeatable sample-making step, review them, record
each round and its decision in the design approval record of this milestone.

**Acceptance Scenarios**:

1. **Given** the implementation, **When** a review round starts, **Then** sample files in Ukrainian and
   English can be made again at any time from the same realistic data, covering several regions, long
   names, Cyrillic text, a multi-page list and a competition with no teams.
2. **Given** a round, **When** the product owner asks for changes to the layout, fonts, the size and
   place of the logo, the header, spacing or wording, **Then** they are made within this milestone and
   reviewed in a new round.
3. **Given** the rounds, **When** the milestone is closed, **Then** the design approval record names the
   approved round; the milestone is not done before it.

---

### User Story 9 - The new patterns are written first (Priority: P3)

A developer opens the component gallery and the UI guidelines. They show the **Published** status
badge next to the other status badges, the actions menu with a **Download results** entry marked as a
download, the read-only grading sheet of a published competition with its note, and the publish
confirmation both ready and blocked.

**Why this priority**: It follows the project rule that pages use only library components; it adds no
capability of its own.

**Independent Test**: Open the gallery and the UI guidelines and check each addition and change.

**Acceptance Scenarios**:

1. **Given** the gallery, **When** it is opened, **Then** it shows the **Published** badge with the
   other competition status badges, an actions menu with a download entry, the read-only grading
   sheet with the published note, and the publish confirmation ready (with **Publish results**) and
   blocked (with the reason, **Grade the remaining teams** and no button).
2. **Given** the UI guidelines, **When** they are read, **Then** they describe the **Published** status
   and badge, the download entry of the actions menu (a link marked as a download, no loading bar, no
   page in between), the blocked confirmation, the new menu order and the changes of FR-045.

---

### Edge Cases

- **A grade is emptied while the publish confirmation is open**: the publish is refused as not fully
  graded, the confirmation shows the new progress, and nothing is stored.
- **The competition is published while its confirmation is open in another tab**: the second publish
  gets "The results of “…” are already published.".
- **The competition is published while a grading sheet is open**: the next grade save is refused with
  the published note and saves nothing.
- **The setting is taken away while the publish confirmation is open**: the publish gets "access
  denied" and changes nothing.
- **A team is deleted, or its institution or region deactivated, after finishing and before
  publishing**: it is still a team of the competition; it counts in the progress and is listed in the
  files with its score.
- **A team is deleted, renamed or moved after publishing**: the files do not change; the **Grades** and
  **Answers** pages follow their 12.4 rules.
- **A competition with no questions**: every team has no answers, counts as fully graded and has the
  score 0; it can be published.
- **A team whose every answer was graded 0**: it is listed with the score 0.
- **Two teams with the same name in different institutions, or institutions with the same name in
  different regions**: each is listed under its own institution and region.
- **Names that differ only by letter case or by the apostrophe**: they are ordered by the Ukrainian
  alphabet rule of milestone 12.5, the same way in both files.
- **Very long competition, subject, region, institution or team names**: they wrap within the page of
  the file and are never cut off; on the web pages they wrap within the content width with no sideways
  page scroll, in the confirmation, the refusals and the notice.
- **A competition name with characters a file name cannot hold** ("A/B: final?"): those characters are
  replaced in the downloaded file's name; the name inside the file is shown as entered.
- **Two published competitions with the same name in the same subject** (possible, since a finished
  name is free again): their file names differ by the start date; two with the same name and the same
  start date get the same file name, and the browser keeps both as it does for any download.
- **The site language is switched between two downloads**: each download hands out the file of the
  language current at that moment.
- **The download address of a published competition of a deactivated subject**: it downloads, since a
  finished competition stays available.
- **The download address names a competition of another subject, or the subject is unknown**: 404, as
  any unknown competition.
- **Pressing Publish results twice (double press)**: the form cannot be sent again until the next page
  arrives (milestone 10.1); a second request arriving anyway gets "already published".
- **The competitions-list context in the address is missing or invalid**: the back links, **Keep
  unpublished**, the landing after publishing and **Grade the remaining teams** fall back as in
  milestones 12.2 and 12.4 (the competition's subject, the status **All** and the page holding the
  competition).
- **Competitions finished before this milestone is deployed**: they stay **Finished** with their grades,
  and can be published like any other.

## Requirements *(mandatory)*

### Functional Requirements

#### Who

- **FR-001**: Only a teacher with **Can manage competitions** MUST be able to publish results: of
  every competition, whoever created it, whatever institutions its teams belong to. There MUST be no
  rights per competition or per institution.
- **FR-002**: Every teacher, with **Read** or **Write** access to any institutions (or none), with or
  without the setting, MUST be able to download the results of every **Published** competition.
- **FR-003**: A teacher without the setting MUST get no **Publish results** entry and MUST get "access
  denied" on the publish confirmation and the publish. When the setting is taken away, they MUST get
  "access denied" at once. Administrators and students MUST get "access denied" on every page and
  action of this milestone, the download included, and MUST never be offered **Publish results** or
  **Download results**.

#### Row actions

- **FR-004**: The actions menu MUST list, in this order, **Edit**, **Questions**, **Teams**,
  **Answers**, **Grades**, **Publish results**, **Download results**, **Finish competition** and
  **Cancel competition**, each only where it is available.
- **FR-005**: **Publish results** MUST be offered only on a **Finished** competition, to a teacher with
  the setting, whether or not every team is graded. It MUST NOT be a destructive entry.
- **FR-006**: **Download results** MUST be offered only on a **Published** competition, to every
  teacher. The other entries keep their 12.1 to 12.4 rules, with a **Published** competition treated as
  a **Finished** one (FR-018).

#### Publishing

- **FR-007**: **Publish results** MUST open a confirmation page in the pattern of **Finish competition**
  (milestone 12.4), asking "Publish the results of “<name>” of <subject>, started <start>?" with the
  start in the teacher's time zone, and showing the competition's status badge, the progress "Graded
  <fully graded> of <all> teams" counted as on the **Grades** page (milestone 12.4), and the
  consequence "The results will be published for every teacher as PDF files in Ukrainian and English.
  Publishing is permanent: the results cannot be unpublished, and the grades can no longer be
  changed.".
- **FR-008**: The confirming button MUST be **Publish results**, of the primary kind, not destructive.
  The link back MUST be **Keep unpublished** and MUST return to the list page the teacher came from,
  at the competition, with nothing changed.
- **FR-009**: Confirming MUST, in one step, record the moment of publishing, which makes the
  competition **Published**, and store its two results files (FR-024). If the files cannot be made,
  nothing MUST be stored and the competition MUST stay **Finished**.
- **FR-010**: After publishing, the teacher MUST return to the list page they came from, with the same
  subject, status filter and page, and the notice "The results of “<name>” were published". Under
  **All** or **Published** they MUST land at the competition, which shows **Published**; under
  **Finished** they MUST land as after finishing a competition under **In progress** (milestone 12.4).

#### Only when fully graded

- **FR-011**: A competition MUST be publishable only when every one of its teams is fully graded in the
  milestone 12.4 sense: every one of its answers has a grade, so a team with no answers counts as
  graded. Every team of the competition MUST count, a deleted team and a team of a deactivated
  institution or region included.
- **FR-012**: Until then the confirmation page MUST show the progress, the explanation "Every team must
  be graded before the results can be published.", the link **Grade the remaining teams** to the
  **Grades** page with **Ungraded only** (page 1, carrying the list context), the link **Keep
  unpublished** and no **Publish results** button.
- **FR-013**: A publish sent while a team is not fully graded MUST be refused: the confirmation page
  MUST be shown again with the current progress and the explanation, and nothing MUST change.
- **FR-014**: A **Finished** competition with no teams MUST be publishable ("Graded 0 of 0 teams"); its
  files MUST say "No teams took part in this competition." where the teams would be.

#### Refusals and concurrency

- **FR-015**: Opening the confirmation of, or sending a publish for, a competition that is not
  **Finished** MUST show a refusal in the pattern of milestone 12.1, with the heading "Publish the
  results of “<name>”?", the reason for its status and the link **Back to competitions** to the list
  page the teacher came from, at the competition. The reasons MUST be "“<name>” has not started yet, so
  it has no results to publish." (**Upcoming**), "“<name>” is still in progress. Finish it and grade its
  answers before publishing its results." (**In progress**), "“<name>” has been cancelled, so it has no
  results to publish." (**Cancelled**) and "The results of “<name>” are already published."
  (**Published**). Nothing MUST change.
- **FR-016**: When two publishes of the same competition meet, exactly one MUST succeed and make the
  files; the other MUST get "The results of “<name>” are already published.". The same form sent twice
  MUST publish once.
- **FR-017**: When a grade save and a publish of the same competition meet, the first MUST win: a grade
  saved first counts, and the publish is then checked against it (refused as not fully graded if the
  save emptied a grade); a grade save handled after the publish MUST be refused (FR-021). A
  competition MUST never be published with grades that differ from those in its files.

#### The Published status

- **FR-018**: A competition whose results are published MUST have the status **Published**, derived
  from its stored moment of publishing. The statuses MUST be **Upcoming**, **In progress**,
  **Finished**, **Published** and **Cancelled**. Every rule of a finished competition MUST hold for a
  published one: its questions, teams and answers never change, it cannot be edited or cancelled, it
  keeps its deleted teams, it stays available when its subject is deactivated, and its name stays free
  in its subject; except that its grades can no longer be changed.
- **FR-019**: The pages that milestones 12.2 to 12.4 offer on a **Finished** competition (the read-only
  **Questions** and **Teams**, **Answers** and **Grades**) MUST be offered on a **Published** one as
  well, to the same teachers, and the refusals of those milestones that name a **Finished** competition
  (for example, answer saves after finishing) MUST apply to a **Published** one too.
- **FR-020**: The **Published** badge MUST be shown wherever a competition's status badge is shown. The
  status filter of the **Competitions** tab MUST offer **Published** after **Finished**; **Finished**
  MUST list only the finished competitions whose results are not published yet, and **Published** only
  the published ones.

#### Frozen grades

- **FR-021**: There MUST be no unpublish. On a **Published** competition every grading sheet MUST be
  read-only, with the note "The results of “<name>” are published, so its grades can no longer be
  changed.", each grade shown as text, and no grade field and no **Save grades** button. A grade save
  sent anyway MUST be refused with the same note, and nothing MUST change. This replaces the milestone
  12.4 rule that grades can be changed at any time ([12.4](../012.4-finish-and-grade/spec.md) FR-027).
- **FR-022**: The **Grades** page and the read-only **Answers** pages of a **Published** competition
  MUST stay as they are for a **Finished** one otherwise.

#### The results files

- **FR-023**: Each file MUST start with a header: the logo of milestone 12.7, the title "Results of
  “<name>”", the subject, the start and finish date and time, the date of publishing, and under it
  the maximum score, "Maximum score: <n>", where n is 10 (the grade scale's maximum) for each of the
  competition's questions. The start and finish times MUST be in Kyiv time, labelled as such, as in
  milestone 12.5; the date of publishing MUST be the date in Kyiv time.
- **FR-024**: Two files MUST be made at publishing, one with every label in Ukrainian and one with every
  label in English, and stored with the competition. Names (of the competition, subject, regions,
  institutions and teams) MUST be shown as entered, never translated, and Cyrillic letters MUST render
  correctly on any device, with no font needed on the reader's side.
- **FR-025**: Below the header each file MUST show a heading for each region, and under it a table
  with the columns "Educational institution", "Team" and "Score" and one row per team: the
  institution's name, the team's name and its score, the sum of its grades. The score column MUST be
  just wide enough to show the score (or its heading, if wider); long names MUST wrap within their
  cell; a table continued on a new page MUST repeat its heading row. Every team of the competition
  MUST be listed, a deleted team and a team of a deactivated institution or region included, like
  every other team.
- **FR-026**: Regions, the institutions within a region and the teams within an institution MUST be
  ordered alphabetically with the Ukrainian alphabet rule of milestone 12.5, the same in both files.
- **FR-027**: The files MUST hold only each team's region, institution, name and final score: never an
  answer, a reference answer, a question, a grade per question or a member of a team.
- **FR-028**: A long list MUST continue across pages, and every page MUST be numbered "Page <n> of
  <total>" in the file's language.
- **FR-029**: The files MUST be snapshots: they MUST never be made again or changed, whatever happens to
  the competition's subject, regions, institutions or teams later. They MUST keep the names and scores as
  they were at publishing.

#### Download

- **FR-030**: **Download results** MUST hand out the stored file of the current site language, byte for
  byte as stored, with nothing calculated again, straight away with no page in between; the teacher MUST
  stay on the list.
- **FR-031**: **Download results** MUST be a link marked as a download, so the loading bar of milestone
  10.1 does not start for it and never stays on the screen.
- **FR-032**: The downloaded file MUST be named "<name> <YYYY-MM-DD>.pdf" after the competition's name
  and its start date in Kyiv time; characters a file name cannot hold MUST be replaced, and other
  characters, Cyrillic included, MUST be kept.
- **FR-033**: The download MUST answer 404 with the page "Competition not found" (milestone 12.1) for
  an unknown competition, a competition of another subject, and a competition that is not
  **Published**; and 404 with the page "Subject not found" (milestone 12.1) for an unknown subject, as
  every competition route does.

#### Checks and shared behaviour

- **FR-034**: Every page and action of this milestone MUST check everything again when it is opened or
  sent, whatever the page showed, and again when the change is stored. The checks MUST run in this
  order, and the first failing one MUST decide the answer:
  1. the role: anyone who is not a teacher gets "access denied", before any id is read;
  2. the setting (confirmation and publish only): a teacher without **Can manage competitions** gets
     "access denied", before any id or subject is read;
  3. the subject and the competition: an unknown subject or competition, a competition of another
     subject, or a competition of a deactivated subject that is not **Finished** or **Published** shows
     "not found", as in milestone 12.1; for the download, any competition that is not **Published**
     answers 404 (FR-033);
  4. the status (confirmation and publish): the refusal of FR-015;
  5. the grading (publish): the refusal of FR-013.
- **FR-035**: Every publish MUST be a form submission that passes the existing cross-site request
  check. Opening a page or following a link, the download included, MUST never change anything, and
  reloading a page after a publish MUST never repeat it. No log line MUST contain an email address or a
  person's name.
- **FR-036**: Every page of this milestone MUST follow the UI guidelines, including the loading feedback
  and busy button of milestone 10.1, and MUST work on a phone-width screen without sideways page
  scrolling.

#### Languages

- **FR-037**: Every new text of the pages, notices, refusals and files MUST be in both message
  catalogues, Ukrainian and English, translated, with no unused or obsolete entries, as the milestone
  12.5 catalogue checks require. The texts quoted in this specification are the English ones.

#### Design approval

- **FR-038**: The design of the files (layout, fonts, the size and place of the logo, the header,
  spacing and wording) MUST be finalized in review rounds with the product owner, as in milestone 12.7,
  and each round and its decision MUST be recorded in this milestone's design approval record.
- **FR-039**: Sample files in both languages MUST be repeatable to make from realistic data: several
  regions, long institution and team names, Cyrillic text, a list long enough to continue across pages,
  and a competition with no teams.
- **FR-040**: The milestone MUST NOT be done until the product owner approves the design. Change
  requests to the design MUST be made within this milestone.

#### Components and UI guidelines

- **FR-041**: The **Published** status badge MUST be added to the component library, the component
  gallery and the UI guidelines before any page uses it, next to the other competition status badges.
- **FR-042**: The **download entry of the actions menu** (a link marked as a download that starts no
  loading feedback and opens no page) MUST be added to the component library, the component gallery and
  the UI guidelines before any page uses it. The UI guidelines MUST state the rule for every download:
  it is offered as a link marked as a download, never through a page in between, and it starts no
  loading feedback.
- **FR-043**: The **read-only state of the grading sheet** (the grading sheet with each grade as text,
  no field, no save button and a note under the heading) MUST be added to the component library and the
  component gallery before any page uses it.
- **FR-044**: Apart from these four (FR-041, FR-042, FR-043 and FR-046), the pages MUST be built from
  existing components: the confirmation and refusal pages, the non-destructive confirmation, the
  filter links, notices, back links, the local-time display and the competition status badges.
- **FR-045**: The documentation MUST be updated in the same change: the UI guidelines' actions menu
  order and example, the list of statuses and their badges, and the wording patterns for the new texts.
- **FR-046**: The **blocked state of the non-destructive confirmation** (the confirmation page of an
  action that cannot be taken yet because work is left: the reason in place of the confirming button,
  a link to the work left, and the link back) MUST be added to the component library, the component
  gallery and the UI guidelines before any page uses it. Only a primary confirmation can be blocked.

#### Rules already written down

- **FR-047**: The product requirements, the technical requirements and the constitution v2.5.0
  (Principles IV and VII and the "Results files" row) already state the rules of this milestone: only
  a teacher allowed to manage competitions publishes, only a fully graded finished competition, and
  permanently; grades never change after publishing; the published results are open to every teacher;
  the files are made once at publishing, as PDF with embedded fonts, one per language, stored in the
  database and handed out as stored. The implementation MUST NOT contradict them; no further amendment
  is needed.

#### Verification and scope

- **FR-048**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" list: the menu per status and setting; publishing, its landings, the
  fully-graded rule (with no teams included), every status refusal, the concurrent and repeated
  publishes and the grade-save-and-publish race; the **Published** badge and filter; the frozen
  grading sheets and the refused grade saves; exactly two stored files that do not change after a
  later rename or deletion; the content of each file (header, logo, region headings, order, every
  team's line with its score, a deleted team included, the language, Cyrillic text, no answer or grade
  per question, page numbers); the download for every kind of teacher, its download marking, the stored
  bytes, the file name, the 404 cases and the refusal of administrators and students; the check order;
  the cross-site request check; and the gallery.
- **FR-049**: The design approval of the files by the product owner is checked by hand and MUST NOT be
  automated.
- **FR-050**: This milestone MUST NOT add anything listed under **Out of Scope** below.

### Key Entities *(include if feature involves data)*

- **Competition** (existing, milestones 12.1–12.4): now also records the moment its results were
  published; its **Published** status is derived from that, as **Finished** is from its finishing. Only
  a finished competition can be published, and once published it never goes back. Who published is not
  stored.
- **Results file** (new): one stored PDF of a published competition's results in one language
  (Ukrainian or English), made at publishing. A published competition has exactly two, one per
  language; an unpublished one has none. A file never changes after it is stored and is never deleted
  while its competition exists. It holds no personal data: only team names, institutions, regions and
  scores.
- **Grade** (existing, milestone 12.4): can no longer be added, changed or removed once its competition
  is published.
- **Team score** (derived, not stored): the sum of a team's grades; once published, the score in the
  files is the official one, and it equals the score derived from the frozen grades.
- **Teacher's Can manage competitions setting** (existing, milestone 8): now also publishes results;
  read on every request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the competitions list, a teacher with the setting publishes a fully graded
  competition with three choices (**Actions**, **Publish results**, **Publish results**), and any
  teacher gets the results file with two (**Actions**, **Download results**), with no page in between.
- **SC-002**: In 100% of concurrent and repeated publishes, exactly one publish succeeds and the
  competition holds exactly two results files.
- **SC-003**: 0 grades are saved, changed or removed for a published competition, and 0 competitions
  are published with a team that is not fully graded.
- **SC-004**: 100% of downloads hand out a file identical, byte for byte, to the one stored at
  publishing, also after the competition's subject, regions, institutions or teams were renamed,
  deactivated or deleted.
- **SC-005**: In 100% of the tested files, the text read back from the file contains every team of the
  competition with the score derived from its grades, in the required order, with Cyrillic names
  exactly as entered, and contains no answer, reference answer, question text or grade per question.
- **SC-006**: In the automated access check, 100% of the pages and actions of this milestone refuse
  administrators and students before any id is read, publishing refuses teachers without the setting
  before any id is read, and the download answers 404 for 100% of competitions that are not
  **Published**, with nothing changed in every case.
- **SC-007**: Publishing a competition of 500 teams in 10 regions completes, files included, within 5
  seconds, and a download of its file starts within 1 second.
- **SC-008**: The product owner approves the design of both files after at most the review rounds the
  milestone needs, and the approval is recorded before the milestone is closed.

## Assumptions

- **The date of publishing is shown as a date** in Kyiv time (e.g. "21 November 2026"), while the start
  and finish are shown as date and time, as the local-time display of milestone 12.5 shows them; the
  exact formats are part of the design approval.
- **The moment of finishing appears for the first time** in the files (milestone 12.4 stored but never
  showed it); the moment of publishing is shown only in the files, not on the web pages.
- **A deleted team carries no "(deleted)" mark** in the files: it is listed like every other team, as
  the milestone says; likewise a deactivated institution or region carries no mark.
- **The line layout "Institution, Team, Score"** is fixed in its content and order; how it is set on
  the page (one line of text, or columns) is part of the design approval.
- **The region of a team** is the region of its institution at the moment of publishing.
- **Characters a file name cannot hold** are the path separators, `: * ? " < > |` and control
  characters; each is replaced with "_". Spaces at the ends and trailing dots are removed. The file name
  is the same in both languages, since names are never translated. A non-ASCII name is kept for browsers
  that support it, with a plain fallback for those that do not.
- **The download is always the file of the current site language**: Ukrainian unless the teacher
  switched to English (milestone 12.5); there is no choice of language on the menu and no download of
  both files at once.
- **The Grades page of a published competition keeps its Grade answers entry** ("stay as they are
  otherwise"); it opens the read-only grading sheet. The read-only grading sheet keeps the reference
  answers, since it is still the grader's view, and shows each grade as "Grade: 7 of 10", the wording of
  the 12.4 read-only sheet.
- **Every Published competition has both files**: they are stored in the same step as the status, so
  a published competition without files cannot exist; no repair path is needed.
- **Who published the results is not stored**, as who graded is not (milestone 12.4); the files are not
  personal data.
- **A published competition of a deactivated subject** stays listed and downloadable, as a finished
  one stays available (milestone 12.1 rules for finished competitions).
- **Students get no change in this milestone**: they see no results and get no files; their view of
  published results is milestone 14.
- **Competitions finished before this milestone is deployed** stay **Finished**; nothing is published
  automatically.
- **Sample files for the design review** are made by a repeatable step from seeded realistic data, in
  the way milestone 12.7 made its images; the step is not part of the running application.
- **Every quoted text above** is taken from the milestone where the milestone gives it; the texts it
  only implies (the page numbering in Ukrainian, the Kyiv time label) follow the existing patterns.

## Dependencies

- **Constitution v2.5.0** (amended on 2026-11-21): Principle II (component library first), Principle IV
  (who publishes, grades frozen after publishing, published results open to every teacher) and
  Principle VII (the status derived from the stored publishing; the results files stored once as
  snapshots and handed out as stored), and the "Results files" row of the technology stack (one
  server-side PDF library, chosen and justified in this milestone's plan, fonts embedded, no external
  service).
- **Product requirements** (updated with the milestone): the "How a competition works", "Teacher
  access rights", "Personal data", "Competition statuses" and "Published results" sections.
- **Technical requirements**: the "Results files" row.
- **Milestone 5**: roles, "access denied" and the automated route check.
- **Milestone 7**: regions and educational institutions, their deactivation and renaming.
- **Milestone 8**: teachers' links, **Read** and **Write** access, and **Can manage competitions**.
- **Milestones 10 and 10.1**: the component library, the gallery, the UI guidelines, the loading
  feedback and the busy button.
- **Milestone 11.1**: teams and their deletion.
- **Milestone 12.1**: competitions, statuses, the actions menu, the status filter, the refusal pattern,
  "Competition not found", the landing rules and the deactivated-subject rules.
- **Milestones 12.2 and 12.3**: a competition's teams, the **Teams**, **Questions** and **Answers**
  pages.
- **Milestone 12.4**: finishing, the non-destructive confirmation, the **Grades** page with **Ungraded
  only**, the grading sheet, "fully graded", the team score and the landing after finishing.
- **Milestone 12.5**: the two languages, the message catalogues, Kyiv time for unknown zones and the
  Ukrainian alphabet order.
- **Milestone 12.7**: the logo shown in the files, and its design review process.
- **Later milestones that depend on this one**: milestone 13 proposes grades by an LLM that a teacher
  can adjust only until the results are published, and never evaluates a published competition;
  milestone 14 shows best answers, scores, places and the winner only for **Published** competitions,
  agreeing with the stored files, and shows students their own teams' published results.

## Out of Scope

- Unpublishing, publishing again, or making the files again for any reason.
- A results page, places, a winner or best answers on the web pages (milestone 14).
- Students seeing results or getting the files (milestone 14).
- Answer evaluation by an LLM (milestone 13).
- Downloads for administrators or students, or for anyone not signed in.
- Results files in other formats (spreadsheet, CSV) or other languages, a combined bilingual file, or
  a download of both files at once.
- Answers, reference answers, questions, grades per question or team members in the files.
- Sending the files by email or to any external service.
- Publishing automatically, at a set time, or when the last team is graded.
- Publishing part of a competition, or with ungraded teams.
- Storing who published, or showing the moment of publishing on the web pages.
- Scores in the competitions list.
- Changing the **Grades** or **Answers** pages beyond the read-only grading sheet of a published
  competition.
