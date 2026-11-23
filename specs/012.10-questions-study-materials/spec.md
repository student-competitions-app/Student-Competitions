# Feature Specification: A Competition's Questions Only After It Starts, and Study Materials (Teacher) (Milestone 12.10)

**Feature Branch**: `012.10_questions_study_materials`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: milestone 12.10 of `docs/requirements/milestones.md` ("A competition's
questions only after it starts, and study materials (teacher)"), as refined on 2026-11-23, with
`product-requirements.md` (the "Teacher responsibilities", "Teacher access rights to competitions"
and "Additional questions" sections), `technical-requirements.md` (the "PDF files" row), the
constitution v2.7.1 (Principles II, III, IV and VII and the "PDF files" row of the technology stack),
`docs/requirements/ui-guidelines.md` (the actions menu and its download entry), and the milestone 5,
8, 10, 10.1, 11, 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 12.8 and 12.9 specifications as reference.

## Overview

Milestone 12.10 of the walking skeleton for the Student Competitions application. After milestone
12.2, every teacher reads a competition's questions, with their reference answers, on its
**Questions** page in every status, an **Upcoming** one included. A teacher could therefore pass a
competition's questions to their teams before it starts, and the additional questions of milestone
12.9 stop being kept back as soon as they are added to a competition (the gap 012.9 FR-027 accepted
until this milestone). At the same time, nothing yet hands the teams their questions once the
competition begins, and nothing gives students the question bank to prepare with.

This milestone keeps a competition's questions with the teachers who choose them, hands their texts
to the teams once the competition starts, and gives every teacher the rest of the bank as study
materials. A bank holds a hundred questions or more per subject and a competition uses about ten of
them, so the students learn the whole bank and answer a small part of it. Eight things become true
when this milestone is done:

1. **A competition's Questions page is only for teachers with Can manage competitions**, in every
   status. Every other teacher no longer has **Questions** in the actions menu, and the page and
   every page under it answer "access denied", the same for every competition and for one that does
   not exist. **Teams** stays offered to every teacher.
2. **Every teacher downloads the questions of a started competition** with **Download questions** in
   the actions menu, on an **In progress**, **Finished** or **Published** competition, as a PDF file
   to hand to the teams.
3. **The questions file holds the question texts only**: every question of the competition in its
   order, numbered from 1, additional ones included, never a reference answer, a bank number or the
   **Additional** mark. It is made at every download and never stored.
4. **Every teacher downloads a subject's study materials** with the link **Download study materials**
   beside the subject list of the **Competitions** tab, once an active subject is chosen.
5. **The study materials file holds the bank to learn**: every question of the subject with its
   reference answer, oldest first, numbered from 1, without the additional and deleted questions and
   without bank numbers, whoever downloads it.
6. **The study materials are kept in memory but never stale**: the last file per subject and language
   is given again only while nothing it shows has changed, and is made again otherwise.
7. **Both files follow the design of the results file** of milestone 12.8, in the current site
   language, and the product owner approves both files and the look and place of the link in review
   rounds before the milestone is done.
8. **The actions menu order becomes** Edit, Questions, Teams, Answers, Download questions, Grades,
   Publish results, Download results, Finish competition, Cancel competition, each only where it is
   available, and the UI guidelines say so.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Only teachers with the setting see a competition's questions (Priority: P1)

Olena has **Can manage competitions**. On the **Competitions** tab, the menu of the **Upcoming**
"Spring round" of "Chemistry" still offers **Questions**, and its page lists the six questions Olena
chose, with their reference answers and the **Additional** badge on two of them, exactly as before.
Petro has **Write** access to School No. 5 and no setting. The menu of "Spring round" now offers him
only **Teams**. Petro types the address of its **Questions** page and gets the "access denied" page;
he gets the same page for the address of a competition that does not exist, and for **Add
questions**. After "Spring round" starts, finishes and is published, Petro still has no **Questions**
entry and still gets "access denied" for the page.

**Why this priority**: Keeping a competition's questions from the teachers who could pass them to
their teams before the start is the reason for the milestone, and it closes the gap left open by
milestone 12.9.

**Independent Test**: As a teacher with the setting and as teachers without it, with **Read** and
with **Write** access, open the actions menu and the **Questions** page, **Add questions** and every
action under them, for a competition in every status and for a missing one, and compare the menus
and the responses.

**Acceptance Scenarios**:

1. **Given** a teacher with **Can manage competitions**, **When** they open the actions menu of a
   competition in any status (**Upcoming**, **In progress**, **Finished**, **Published**,
   **Cancelled**, and a finished competition of a deactivated subject), **Then** it offers
   **Questions**, and the **Questions** page, **Add questions** and removing a question behave
   exactly as in milestones 12.2 and 12.9.
2. **Given** a teacher without the setting, with **Read** or **Write** access, **When** they open the
   actions menu of a competition in any status, **Then** it offers no **Questions** entry, and still
   offers **Teams**.
3. **Given** a teacher without the setting, **When** they open the **Questions** page of a
   competition in any status by a typed-in address, **Then** they get the "access denied" page
   (milestone 5), and the response holds no question text, reference answer, bank number or badge.
4. **Given** the same teacher, **When** they request the **Questions** page of a competition that
   does not exist, or of an unknown subject, **Then** they get the same "access denied" page as for
   an existing competition.
5. **Given** the same teacher, **When** they open **Add questions**, send an add, open a removal or
   send it, for any competition or a missing one, **Then** they get the same "access denied" page,
   and nothing changes.
6. **Given** a teacher who loses the setting, **When** they open the next page, **Then** **Questions**
   is gone from the menu and the page refuses them; **given** a teacher who gets it, **then** the
   entry and the page are there on the next page.
7. **Given** an administrator or a student, **When** they request the **Questions** page or any page
   under it, **Then** they get "access denied", as before.

---

### User Story 2 - Every teacher downloads the questions of a started competition (Priority: P1)

"Spring round" has started. Petro, without the setting and linked to an institution with no team in
it, opens its menu: it offers **Teams**, **Answers** and **Download questions**. Petro chooses
**Download questions**, the browser saves "Spring round 2026-11-21 питання.pdf" in Ukrainian straight
away, and Petro stays on the list; the loading bar does not appear. Petro hands the printed file to
the team. On the **Upcoming** "Autumn round" the menu has no **Download questions**, and its download
address, typed in, answers "Competition not found".

**Why this priority**: The teams need the questions to answer once the competition begins, and after
User Story 1 this file is how every teacher other than the managers gets them.

**Independent Test**: As teachers with **Read** and **Write** access, with and without the setting,
linked and not linked to the teams' institutions, check the menu of a competition in every status,
download the file in both languages, check the link's download marking and the file name, and
request the download of competitions in every status, of a deactivated subject and of a missing
one.

**Acceptance Scenarios**:

1. **Given** an **In progress**, **Finished** or **Published** competition, **When** any teacher opens
   its menu, with **Read** or **Write** access, with or without the setting, and whatever
   institutions its teams belong to, **Then** it offers **Download questions**.
2. **Given** an **Upcoming** or **Cancelled** competition, **When** any teacher opens its menu,
   **Then** it does not offer **Download questions**, and its download address answers 404 with the
   page "Competition not found" (milestone 12.1).
3. **Given** **Download questions**, **When** it is chosen, **Then** the file of the current site
   language is downloaded at once, with no page in between, and the teacher stays on the list with
   the same subject, status filter and page.
4. **Given** the site language is switched, **When** **Download questions** is chosen again, **Then**
   the file is in the new language.
5. **Given** **Download questions**, **When** its link is inspected, **Then** it is a link marked as a
   download, the download entry of the actions menu (milestone 12.8), and the loading bar of
   milestone 10.1 does not start for it.
6. **Given** a deactivated subject, **When** a teacher opens the menu of its **Finished** or
   **Published** competition, **Then** it offers **Download questions** and the download gives its
   file; **when** the download address of one of its **In progress** competitions is requested,
   **then** it answers 404 with "Competition not found".
7. **Given** an unknown subject, or a deactivated subject with no finished competition, **When** a
   download address under it is requested, **Then** it answers 404 with "Subject not found"; **given**
   an unknown competition, or a competition of another subject, **then** it answers 404 with
   "Competition not found".
8. **Given** an **In progress** competition, **When** it is cancelled and its download address is
   requested again, **Then** it answers 404 with "Competition not found" at once.
9. **Given** an administrator or a student, **When** they request a download address, also with an
   unknown id, **Then** they get "access denied" before any id is read; neither role is ever offered
   the entry.
10. **Given** a menu where every entry is available, **When** it is opened, **Then** its entries read
    Edit, Questions, Teams, Answers, Download questions, Grades, Publish results, Download results,
    Finish competition, Cancel competition, in that order, each only where it is available.

---

### User Story 3 - The questions file holds the question texts only (Priority: P1)

Petro opens the downloaded file of "Spring round". Below the logo, the header reads "Questions of
“Spring round”", "Chemistry" and "Started: 21 November 2026, 10:00 (Kyiv time)", and nothing else.
Below it come the six questions, numbered 1 to 6 in the competition's order, each with its text as
entered. There is no reference answer, no bank number such as "Question 58" and no sign of which two
questions are additional. A week later "Chemistry" is renamed "Chemistry and Biology"; the next
download shows the new name in the header and the same six questions.

**Why this priority**: The file is handed to the teams; anything beyond the question texts would give
away the answers or the additional questions.

**Independent Test**: Make the file of competitions with mixed, additional, deleted and no questions,
with long Cyrillic texts and enough questions to fill several pages, in both languages; read the text
back and compare it with the competition's copies of the questions.

**Acceptance Scenarios**:

1. **Given** a started competition, **When** its file is made, **Then** its header holds the logo of
   milestone 12.7 at the size of the results file, the title "Questions of “<name>”", the subject and
   the start date and time in Kyiv time, labelled as in the results file ("Started: …"), and no other
   line: no finish, no date of publishing, no maximum score.
2. **Given** the competition holds questions, **When** the file is made, **Then** below the header it
   lists every one of them in the competition's order (milestone 12.2), numbered from 1 by their place
   in the competition, additional questions and questions deleted from the bank included.
3. **Given** the file, **When** its text is read back, **Then** it holds each question's text as the
   competition copied it (milestone 12.2), and no reference answer, no bank number and no
   **Additional** mark.
4. **Given** a question whose bank question was edited after the competition copied it, **When** the
   file is made, **Then** it shows the competition's copy, not the bank's new text.
5. **Given** a competition with no questions, **When** its file is made, **Then** below the header it
   says "This competition has no questions.".
6. **Given** the subject is renamed after the competition started, **When** the file is downloaded
   again, **Then** its header shows the new name; otherwise every download gives the same content.
7. **Given** the site language, **When** the file is made, **Then** every label is in that language,
   and question texts, the competition's name and the subject are shown as entered, never translated,
   with Cyrillic letters rendered correctly.
8. **Given** a file is downloaded, **When** it is saved, **Then** it is named "<name> <YYYY-MM-DD>
   questions.pdf" after the competition's name and its start date in Kyiv time, with the word
   "questions" in the file's language ("Spring round 2026-11-21 questions.pdf").

---

### User Story 4 - Every teacher downloads a subject's study materials (Priority: P1)

Before the spring competitions, Petro opens the **Competitions** tab and chooses "History" in the
subject list. Beside the list the link **Download study materials** appears. Petro chooses it: the
browser saves "History 2026-11-23 навчальні матеріали.pdf" straight away, and Petro stays on the tab
with "History", the same status filter and the same page. Before a subject is chosen, and for a
subject of the **Deactivated subjects** group, the link is not shown.

**Why this priority**: The study materials are what the students learn from; without them the bank
cannot be given to participants at all.

**Independent Test**: As teachers with **Read** and **Write** access, with and without the setting,
open the **Competitions** tab before and after choosing an active subject, a subject with no
competitions and a deactivated subject, download the file in both languages, check the link's
download marking, and request the download of an unknown and a deactivated subject; repeat on a
phone-width screen and without JavaScript.

**Acceptance Scenarios**:

1. **Given** the **Competitions** tab, **When** an active subject is chosen in the subject list,
   **Then** the link **Download study materials** is shown beside the list, whether or not the subject
   has competitions, to every teacher, with **Read** or **Write** access, with or without the
   setting.
2. **Given** the tab before a subject is chosen, or with no subjects at all, **When** it is shown,
   **Then** the link is not shown.
3. **Given** a subject of the **Deactivated subjects** group is chosen, **When** the tab is shown,
   **Then** the link is not shown.
4. **Given** the link, **When** it is chosen, **Then** the file of the chosen subject in the current
   site language is downloaded at once, with no page in between, the teacher stays on the tab with
   the same subject, status filter and page, and the loading bar does not start.
5. **Given** the link, **When** it is inspected, **Then** it is a link marked as a download, and it
   works without JavaScript.
6. **Given** an unknown subject, or a deactivated one, **When** its study materials address is
   requested, **Then** it answers 404 with the page "Subject not found", as the **Questions** tab does.
7. **Given** an administrator or a student, **When** they request a study materials address, also
   with an unknown id, **Then** they get "access denied" before any id is read; neither role is ever
   shown the link.
8. **Given** a phone-width screen, where the subject list and the status filter stack, **When** a
   subject is chosen, **Then** the link is shown with the subject list and the page does not scroll
   sideways, in both languages and both themes.

---

### User Story 5 - The study materials hold the bank to learn, and nothing more (Priority: P1)

"History" has 158 questions that are not deleted, 8 of them additional, and 4 deleted ones. Olena,
who has the setting, downloads the study materials. Below the logo the header reads "Study
materials", "History" and "Downloaded: 23 November 2026", and nothing else. Below it come 150
questions, oldest first, numbered 1 to 150, each with its text and, below it, "Answer: …" with its
reference answer. None of the 8 additional or 4 deleted questions is there, and no bank number is
shown, so nobody can tell that any were left out. The file runs over several numbered pages.

**Why this priority**: The study materials go to students; an additional question in them would end
its value, and a bank number would show where the gaps are.

**Independent Test**: Make the file of a subject that mixes ordinary, additional and deleted
questions, of a subject with none left, and of a subject of 150 questions, as a teacher with and
without the setting and in both languages; read the text back and compare it with the bank.

**Acceptance Scenarios**:

1. **Given** an active subject, **When** its file is made, **Then** its header holds the logo at the
   size of the results file, the title "Study materials", the subject and the date of the download in
   Kyiv time, labelled ("Downloaded: …"), and no other line.
2. **Given** the subject's bank, **When** the file is made, **Then** it lists every question of the
   subject that is neither additional nor deleted, oldest first, numbered from 1 by their place in the
   list, each with its text and, below it, its reference answer labelled ("Answer: …").
3. **Given** a teacher with **Can manage competitions**, **When** they download the file, **Then** it
   is the same as for any other teacher: no additional question is in it.
4. **Given** the file, **When** its text is read back, **Then** it holds no bank number, no
   **Additional** mark and no text or reference answer of an additional or deleted question.
5. **Given** a subject with no such questions (none at all, or only additional or deleted ones),
   **When** its file is made, **Then** below the header it says "This subject has no questions yet.".
6. **Given** a subject of 150 questions, **When** its file is made, **Then** it continues across
   several pages, each numbered.
7. **Given** a file is downloaded, **When** it is saved, **Then** it is named "<subject> <YYYY-MM-DD>
   study materials.pdf" after the subject's name and the date of the download in Kyiv time, with the
   words "study materials" in the file's language ("History 2026-11-23 study materials.pdf").

---

### User Story 6 - The study materials are kept but never out of date (Priority: P2)

Making the study materials of a large bank takes seconds on the hosting plan's single slow processor,
and slows every other page while it runs. Petro downloads the materials of "History"; a minute later
Taras downloads them too and gets the same file at once, without it being made again. Olena then
fixes a typo in a reference answer; Taras's next download shows the fix. A database fix applied by a
script, outside the application, shows in the next download as well, and so does the date the next
day.

**Why this priority**: It protects the speed of the whole application for every user, but the
materials can be downloaded correctly without it.

**Independent Test**: Download the same materials twice and check that the second download does not
make the file; then make each kind of change in turn (in the application, straight in the database,
in the other language, on the next day in Kyiv time) and check that the next download makes a new
file that shows it; overlap a download with a change; deactivate the subject; download twice at once;
restart the application.

**Acceptance Scenarios**:

1. **Given** a file was made for a subject and language, **When** the same file is downloaded again
   and nothing it shows has changed, **Then** the kept file is given without being made again.
2. **Given** a kept file, **When** a question of the subject is added, edited or deleted, marked or
   unmarked as additional, or the subject is renamed, **Then** the next download makes a new file that
   shows the change.
3. **Given** a kept file, **When** a question's text or reference answer is changed straight in the
   database, without the application, **Then** the next download makes a new file that shows the
   change.
4. **Given** a kept file in one language, **When** the file is downloaded in the other language,
   **Then** a file in that language is made; the file of each language is kept on its own.
5. **Given** a kept file, **When** it is downloaded on the next day in Kyiv time, **Then** a new file
   with the new date is made.
6. **Given** a change to the bank lands while a file is being made, **When** the next download comes
   after the change, **Then** the file made during the change is not given; a file is given only when
   what it was made from matches what is read at the download.
7. **Given** a kept file, **When** the subject is deactivated and the file is requested, **Then** the
   answer is 404 with "Subject not found", whatever is kept.
8. **Given** several teachers download the same subject's file in the same language at the same time,
   **When** no file is kept for it, **Then** the file is made once and they all get it.
9. **Given** the application restarts, is deployed again or wakes from sleep, **When** the study
   materials are downloaded, **Then** the file is made again, with the current release's labels and
   design.

---

### User Story 7 - The product owner approves both files and the link (Priority: P2)

Before the milestone is done, the product owner reviews sample files in both languages made from
realistic data, and screenshots of the **Competitions** tab with the new link, on a wide screen and
on a phone, in both languages and both themes. They ask for more space between the questions and for
the answer label in bold; the changes are made and a new round is held, until they approve both
files and the link.

**Why this priority**: The files go to students and teams and the link is new on a page every teacher
uses; their look is a product decision, but it adds no capability that cannot be tested without it.

**Independent Test**: Make the sample files and screenshots with the repeatable step, review them,
and record each round and its decision in the design approval record of this milestone.

**Acceptance Scenarios**:

1. **Given** the implementation, **When** a review round starts, **Then** sample files in Ukrainian
   and English can be made again at any time from the same realistic data: long Ukrainian questions
   and answers, a competition list long enough to continue across pages, study materials of about 150
   questions, a competition with no questions and a subject with no questions.
2. **Given** a round, **When** the product owner reviews the link, **Then** screenshots of the
   **Competitions** tab with a subject chosen are available on a wide screen and on a phone, in both
   languages and both themes.
3. **Given** a round, **When** the product owner asks for changes, **Then** they are made within this
   milestone and reviewed in a new round.
4. **Given** the rounds, **When** the milestone is closed, **Then** the design approval record names
   the approved round for the two files and for the link; the milestone is not done before it.

---

### User Story 8 - A new pattern is written first, if one is needed (Priority: P3)

If no component of the library fits the link beside the subject list, a developer finds the new
pattern in the component gallery and its rules in the UI guidelines before the **Competitions** tab
uses it. The UI guidelines show the new order of the actions menu with **Download questions**.

**Why this priority**: It follows the project rule that pages use only library components; it gives
teachers nothing on its own.

**Independent Test**: Open the component gallery and the UI guidelines and check the link's pattern
(new or existing) on a wide screen and at 360 px, in both themes, and the actions menu order.

**Acceptance Scenarios**:

1. **Given** an existing component fits the link beside the subject list on a wide screen and on a
   phone, **When** the tab is built, **Then** it uses that component and no new pattern is added.
2. **Given** none fits, **When** the tab is built, **Then** the new pattern is first added to the
   component library, the component gallery and the UI guidelines, and only then used on the tab.
3. **Given** the UI guidelines, **When** they are read, **Then** they give the actions menu order of
   this milestone, with **Download questions** as a download entry.

---

### Edge Cases

- **A teacher without the setting with a link to a competition's Questions page** (from before this
  milestone, or shared by a colleague) gets "access denied", the same as for a missing competition.
- **The setting is taken away while the Questions page is open**: the next request under it, a
  removal or an add, is refused with "access denied"; nothing changes.
- **A competition that starts while its menu is open**: the menu on the screen still lacks **Download
  questions** until the list is opened again; the download address works from the start, since the
  status is checked at every download.
- **A competition cancelled while In progress**: the next questions download answers 404 at once.
- **Every question of a competition is additional**: the questions file lists them all, like any other
  questions, with no mark.
- **A question deleted from the bank after a competition took it**: the competition's copy is in the
  questions file like every other question; it is never in the study materials.
- **A question of the bank edited after a competition took it**: the questions file shows the
  competition's copy; the study materials show the bank's current text.
- **A competition or subject name with characters a file name cannot hold** (`/`, `:`, `?` and the
  like): those characters are replaced in the file name, as in milestone 12.8; Cyrillic is kept.
- **A subject whose only questions are additional or deleted**: the link is shown, and the file says
  "This subject has no questions yet.".
- **A question or answer longer than a page** is split across pages; a shorter one, and in the study
  materials a question with its answer, starts on a new page rather than being split.
- **A download just before and just after midnight in Kyiv** gives two files with different dates in
  the header and the name; the second is made again.
- **The subject is renamed between two downloads of a competition's questions**: the second file's
  header shows the new name; the file name uses the competition's name and does not change.
- **A teacher with Read access only, or linked to no institution**, gets both downloads like every
  other teacher.
- **A deactivated subject with no finished competition** is not in the subject list, and every address
  under it answers "Subject not found".
- **A subject is activated again**: the link is shown for it once more, and its file is made from the
  bank as it is.

## Requirements *(mandatory)*

### Functional Requirements

#### A competition's Questions page

- **FR-001**: The **Questions** entry of the actions menu and a competition's **Questions** page
  (milestone 12.2) MUST be offered only to teachers with **Can manage competitions**, in every status
  of the competition and for a finished competition of a deactivated subject too. For them the page,
  **Add questions** and removing a question MUST stay as milestones 12.2 and 12.9 left them, the
  **Additional** badge and the bank numbers included.
- **FR-002**: Every other teacher, with **Read** or **Write** access or with no linked institution,
  MUST have no **Questions** entry in the menu, and MUST get the "access denied" page (milestone 5)
  from the **Questions** page and from every page and action under it (**Add questions** and its add,
  removing a question and its confirmation), opened by a typed-in address or sent as a crafted form.
  Nothing MUST change, and no question text, reference answer, bank number or badge MUST be in the
  response.
- **FR-003**: The setting MUST be checked before the subject and the competition are looked up, so the
  refusal is the same for every competition, in every status, for an unknown competition and for an
  unknown subject.
- **FR-004**: FR-001 to FR-003 replace the milestone 12.2 rule that every teacher reads a
  competition's questions ([012.2](../012.2-competition-questions-teams/spec.md) FR-002) and close the
  gap milestone 12.9 accepted ([012.9](../012.9-additional-questions/spec.md) FR-027). **Teams** MUST
  keep the 12.2 rule and stay offered to every teacher in every status.
- **FR-005**: The setting MUST be checked on every request: a teacher who gets it MUST see **Questions**
  and its page on the next page they open, and a teacher who loses it MUST be refused on the next
  request.

#### Download questions

- **FR-006**: **Download questions** MUST be offered in the actions menu on an **In progress**,
  **Finished** or **Published** competition to every teacher, with **Read** or **Write** access, with
  or without **Can manage competitions**, whatever institutions the competition's teams belong to.
- **FR-007**: It MUST NOT be offered on an **Upcoming** or **Cancelled** competition, and its download
  MUST answer 404 with the page "Competition not found" (milestone 12.1) for those, for an unknown
  competition and for a competition of another subject, in the pattern of **Download results**
  (milestone 12.8).
- **FR-008**: For a deactivated subject, its **Finished** and **Published** competitions MUST offer
  **Download questions** and give their file; its **In progress** competitions, which are hidden
  (milestone 12.1), MUST answer 404 with "Competition not found". An unknown subject, or a deactivated
  subject with no finished competition, MUST answer 404 with "Subject not found". The subject MUST be
  checked first, then the competition, as for **Download results**.
- **FR-009**: **Download questions** MUST use the download entry of the actions menu (milestone 12.8): a
  link marked as a download that gives the file of the current site language straight away, with no
  page in between; the teacher MUST stay on the list with the same subject, status filter and page,
  and the loading bar of milestone 10.1 MUST NOT start for it.
- **FR-010**: The actions menu MUST list, in this order, **Edit**, **Questions**, **Teams**, **Answers**,
  **Download questions**, **Grades**, **Publish results**, **Download results**, **Finish
  competition** and **Cancel competition**, each only where it is available.
- **FR-011**: Administrators and students MUST get "access denied" from the download before any id is
  read, and MUST never be offered the entry.

#### The questions file

- **FR-012**: The questions file MUST follow the design of the results file of milestone 12.8, with
  the logo of milestone 12.7 at the same size.
- **FR-013**: Its header MUST hold only the title "Questions of “<name>”", the subject and the start
  date and time in Kyiv time, labelled as in the results file ("Started: …"). It MUST NOT hold a
  finish, a date of publishing, a maximum score or any other line.
- **FR-014**: Below the header it MUST list every question the competition holds, additional questions
  and questions deleted from the bank included, in the competition's order (milestone 12.2), numbered
  from 1 by their place in the competition.
- **FR-015**: It MUST hold the question texts only: never a reference answer, never the number a
  question has in the bank, and never the mark of milestone 12.9, so the teams cannot tell the
  additional questions from the others.
- **FR-016**: The texts MUST be the competition's copies of the questions (milestone 12.2), so a later
  change in the bank does not change them.
- **FR-017**: A competition with no questions MUST get a file that says "This competition has no
  questions." below the header.
- **FR-018**: The file MUST be made at each download and MUST NOT be stored or kept in memory. The
  competition's status MUST be checked at every download, so a competition cancelled while **In
  progress** answers 404 at once, and the subject in the header MUST follow a later rename of the
  subject. Apart from such a rename, every download of a started competition MUST give the same
  content.
- **FR-019**: The file MUST be named "<name> <YYYY-MM-DD> questions.pdf" after the competition's name
  and its start date in Kyiv time, with the word "questions" in the file's language.

#### Download study materials

- **FR-020**: On the **Competitions** tab, once a subject is chosen in the subject list, the link
  **Download study materials** MUST be shown beside the list for an active subject, whether or not it
  has competitions. It MUST NOT be shown before a subject is chosen, when there are no subjects, or for
  a subject of the **Deactivated subjects** group.
- **FR-021**: Every teacher MUST be shown the link, with **Read** or **Write** access, with or without
  **Can manage competitions**. Administrators and students MUST get "access denied" from the download
  before any id is read, and MUST never be shown the link.
- **FR-022**: The link MUST be marked as a download and give the file of the chosen subject in the
  current site language straight away; the teacher MUST stay on the tab with the same subject, status
  filter and page; the loading bar MUST NOT start; and it MUST work without JavaScript.
- **FR-023**: An unknown subject, or a deactivated one, MUST answer 404 with the page "Subject not
  found", as the **Questions** tab does.
- **FR-024**: The link MUST use an existing component of the library if one fits beside the subject
  list, on a wide screen and on a phone, where the lists stack; otherwise a new pattern MUST first be
  added to the component library, the component gallery and the UI guidelines, and only then used on
  the tab (constitution Principle II).

#### The study materials file

- **FR-025**: The study materials file MUST follow the same design, with the logo at the same size.
- **FR-026**: Its header MUST hold only the title "Study materials", the subject and the date of the
  download in Kyiv time, labelled ("Downloaded: …").
- **FR-027**: Below the header it MUST list every question of the subject's bank, oldest first,
  numbered from 1 by their place in the list, each with its text and, below it, its reference answer,
  labelled ("Answer: …").
- **FR-028**: The list MUST leave out the additional questions (milestone 12.9) and the deleted
  questions (milestone 11), whoever downloads it, a teacher with **Can manage competitions** included,
  and MUST NOT show the number a question has in the bank, so the gaps left by the questions it leaves
  out cannot be seen.
- **FR-029**: The file MUST show the bank as it is at the download, so a change in the bank shows in
  the next download.
- **FR-030**: A subject with no such questions MUST get a file that says "This subject has no questions
  yet." below the header.
- **FR-031**: The file MUST NOT be stored in the database. It MUST be named "<subject> <YYYY-MM-DD>
  study materials.pdf" after the subject's name and the date of the download in Kyiv time, with the
  words "study materials" in the file's language.

#### Keeping the study materials in memory

- **FR-032**: The application MUST keep the last study materials file it made for each subject and
  language in memory, together with exactly what it was made from: the subject's name, the text and
  reference answer of every question it holds in their order, the language and the date of the
  download in Kyiv time. Only the newest file per subject and language MUST be kept.
- **FR-033**: Every download MUST first check that the subject exists and is active (otherwise 404,
  whatever is kept), then read what the file would show. It MUST give the kept file only when what it
  has read, the language and the date in Kyiv time are all the same as what the kept file was made
  from; otherwise it MUST make a new file from what it has just read, and the new file MUST replace the
  kept one.
- **FR-034**: Nothing MUST have to remove a kept file when the bank changes: adding, editing or deleting
  a question, marking or unmarking it as additional, renaming the subject, a change made outside the
  application and a new day MUST each give a new file at the next download through FR-033 alone.
- **FR-035**: A file made while the bank was changing MUST never be given after the change: it is kept
  with what it was made from, and that no longer matches.
- **FR-036**: When several teachers download the same subject's file in the same language at once and
  no matching file is kept, the file MUST be made once and they MUST all get it.
- **FR-037**: The memory MUST be emptied whenever the application starts (a restart, a new deployment
  with its migrations, a wake from sleep on the hosting plan), so the first download after it makes the
  file with the current release's labels and design.

#### Both files

- **FR-038**: Question texts, reference answers, the competition's name and the subject MUST be shown
  as entered, never translated, and Cyrillic letters MUST render correctly with no font needed on the
  reader's side. Every label MUST be in the file's language, which is the current site language.
- **FR-039**: A long list MUST continue across pages, with a running title on every page after the
  first, as in the results file: "Questions of “<name>”" for the questions file and "Study materials:
  <subject>" for the study materials. Every page MUST be numbered "Page <n> of <total>" in the file's
  language.
- **FR-040**: A question, and in the study materials a question with its answer, MUST NOT be split
  across two pages unless it is longer than a page.
- **FR-041**: Characters a file name cannot hold MUST be replaced, and other characters, Cyrillic
  included, kept, as in milestone 12.8.

#### Checks and shared behaviour

- **FR-042**: Every page and action of this milestone MUST check everything again when it is opened or
  sent, and the checks MUST run in this order, the first failing one deciding the answer:
  1. the role: anyone who is not a teacher gets "access denied", before any id is read;
  2. the setting (a competition's **Questions** page and every page and action under it): a teacher
     without **Can manage competitions** gets "access denied", before any subject or competition is
     looked up;
  3. the subject: an unknown subject, or a deactivated one where the page does not allow it, answers
     "Subject not found";
  4. the competition (**Download questions** and the **Questions** pages): an unknown competition, one
     of another subject, or one the page does not allow answers "Competition not found" (for **Download
     questions**, any **Upcoming** or **Cancelled** competition, and an **In progress** one of a
     deactivated subject).
- **FR-043**: Following a download link or opening a download address MUST never change anything
  stored. No log line MUST contain an email address or a person's name.
- **FR-044**: Every changed page MUST be built from the component library with design tokens only,
  MUST follow the UI guidelines, MUST work without JavaScript, and MUST be usable at 360 px width with
  no sideways scrolling, in both themes and both languages.

#### Languages

- **FR-045**: Every new text of the menu, the link, the files and the file names MUST be in both message
  catalogues, Ukrainian and English, translated, with no unused or obsolete entries, as the milestone
  12.5 catalogue checks require. The texts quoted in this specification are the English ones.

#### Design approval

- **FR-046**: The layout of both files (fonts, spacing, the header, the numbering, the answer label and
  wording) MUST be finalized in review rounds with the product owner, as in milestone 12.8, and each
  round and its decision MUST be recorded in this milestone's design approval record.
- **FR-047**: Sample files in both languages MUST be repeatable to make from realistic data: long
  Ukrainian questions and answers, a competition list long enough to continue across pages, study
  materials of about 150 questions, a competition with no questions and a subject with no questions.
- **FR-048**: The look and place of the **Download study materials** link MUST be approved the same
  way, from screenshots of the **Competitions** tab on a wide screen and on a phone, in both languages
  and both themes.
- **FR-049**: The approval MUST be a manual step of the implementation, a task of its own in the task
  list; the milestone MUST NOT be delivered until the product owner has approved both files and the
  link.

#### Documents

- **FR-050**: The product requirements, the technical requirements and the constitution v2.7.1 already
  state the rules of this milestone; the implementation MUST NOT contradict them. The UI guidelines
  MUST give the new actions menu order and its example, and, if FR-024 adds one, the link's pattern.
  When the milestone is delivered, its summary in `milestones.md` MUST say who sees a competition's
  questions and who downloads the two files; the summary of milestone 12.9 MUST no longer say that
  every teacher reads a competition's **Questions** page until milestone 12.10; and the README MUST
  no longer say that every teacher reads a competition's questions.

#### Verification and scope

- **FR-051**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" line: the **Questions** entry, page and every page under it for every kind of
  teacher, in every status and for a missing competition; **Teams** for every teacher; **Download
  questions** per status, per kind of teacher, for a deactivated subject, its download marking, the 404
  cases and the refusal of administrators and students; the content of the questions file (header,
  order, numbering, every question including additional ones, the language, Cyrillic text, no reference
  answer, bank number or mark, the empty sentence, the rename, the cancel); the **Download study
  materials** link per subject and per role, the 404 cases; the content of the study materials file
  (header, order, numbering, answers, no additional or deleted questions even for a teacher with the
  setting, no bank numbers, the empty sentence, several pages for 150 questions); the kept file given
  without being made again, and every kind of change in FR-034, the overlapping change, the deactivated
  subject and the simultaneous downloads; both file names; and the menu order.
- **FR-052**: The design approval of the files and of the link is checked by hand and MUST NOT be
  automated.
- **FR-053**: This milestone MUST NOT add anything listed under **Out of Scope** below.

### Key Entities *(include if feature involves data)*

- **A competition's question (copy)** (existing, milestone 12.2): its text, in the competition's order,
  is what the questions file shows; its reference answer is never in that file. Now read, on its page,
  only by teachers with **Can manage competitions**.
- **Question (of the bank)** (existing, milestones 11 and 12.9): its text and reference answer are what
  the study materials show, unless it is additional or deleted. Its bank number is shown on neither
  file.
- **Subject** (existing): its name heads both files; only an active subject has study materials.
- **Questions file** (new, not stored): a PDF of a started competition's question texts in one
  language, made at every download.
- **Study materials file** (new, not stored in the database): a PDF of a subject's questions with
  their reference answers in one language, kept in the application's memory, newest per subject and
  language, together with exactly what it was made from, and given again only while that still
  matches the bank, the language and the date.
- **Teacher's setting Can manage competitions** (existing, milestone 8): now also decides who sees a
  competition's questions; read on every request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the automated access check, 0 responses to a teacher without the setting, from a
  competition's **Questions** page and every page under it, in every status, hold a question text,
  reference answer, bank number or badge, and 100% of them are the same refusal, a missing competition
  included.
- **SC-002**: Any teacher gets the questions file of a started competition with two choices
  (**Actions**, **Download questions**), and the study materials with one choice once a subject is
  chosen, with no page in between.
- **SC-003**: In 100% of the tested questions files, the text read back holds every question of the
  competition in its order, numbered from 1, and 0 reference answers, bank numbers or **Additional**
  marks.
- **SC-004**: In 100% of the tested study materials, the text read back holds every question of the
  subject that is neither additional nor deleted, with its reference answer, oldest first, and 0
  additional or deleted questions and 0 bank numbers, also when a teacher with the setting downloads
  it.
- **SC-005**: A second download of unchanged study materials of a subject of 150 questions starts within
  1 second and does not make the file again.
- **SC-006**: After each kind of change in FR-034, 100% of the next downloads show the change, and 0
  downloads give a file that differs from what the bank, the language and the date would make at that
  moment.
- **SC-007**: Two simultaneous downloads of the same study materials make the file once in 100% of the
  checks.
- **SC-008**: The download of a questions file of a competition of 10 questions starts within 1 second.
- **SC-009**: The **Competitions** tab with the link is usable at 360 px width in both languages and
  both themes, with no sideways scrolling.
- **SC-010**: The product owner approves both files and the link, and the approval is recorded before
  the milestone is closed.

## Assumptions

- **The Ukrainian texts** follow the glossary and the results file: **Download questions**
  «Завантажити питання», **Download study materials** «Завантажити навчальні матеріали», "Questions of
  “<name>”" «Питання «<name>»», "Study materials" «Навчальні матеріали», "Study materials: <subject>"
  «Навчальні матеріали: <subject>», "Downloaded: …" «Завантажено: …», "Answer: …" «Відповідь: …»,
  "This competition has no questions." «У цьому змаганні немає питань.», "This subject has no
  questions yet." «З цього предмета ще немає питань.», and the file name words «питання» and
  «навчальні матеріали». "Started: …" keeps the results file's «Початок: …».
- **The file names differ by language**, unlike the results file, since each carries its word in the
  file's language; the names of the competition and subject are never translated.
- **"Oldest first"** is the order in which the questions were added to the bank.
- **Line breaks** in question texts and reference answers are kept in both files, as the pages show
  them.
- **The date of the download** is shown as a date in the format of the results file's date of
  publishing (e.g. "23 November 2026"); the start, as a date and time with the Kyiv time label of the
  results file. The exact formats are part of the design approval.
- **The Answers pages stay as they are** (milestones 12.3 and 12.4): once a competition starts, they
  show the teachers of a team's institution the question texts, never the reference answers. The
  constitution v2.7.1 (Principle IV) names these answer sheets as the one other place, besides the
  questions file, where other teachers see a started competition's questions. The **Grades** page and
  the grading sheets stay with the teachers with the setting.
- **The Questions page of a teacher with the setting is unchanged**, bank numbers included: the
  numbering by place is for the file the teams get.
- **The memory holds at most one file per active subject and language**: with tens of subjects and two
  languages this is a small, bounded amount; no other limit or expiry is needed.
- **The hosting plan runs the application as one process**; if it ever runs more, each keeps its own
  files, which stays correct under FR-033 and only makes a file more than once.
- **There is no download for administrators or students** and no link for anyone not signed in.
- **No data change is needed**: nothing new is stored in the database.
- **Every quoted text above** is taken from the milestone where the milestone gives it.

## Dependencies

- **Constitution v2.7.1** (amended on 2026-11-23; v2.7.1 clarifies the Principle IV wording on the
  answer sheets): Principle II (component library first), Principle III (allowed and denied access
  tested on every route), Principle IV (a competition's questions kept back from everyone but the
  teachers allowed to manage competitions, their texts given out after the start in the questions
  file and, for the teachers of the teams' institutions, on the answer sheets; the study materials open to every teacher, never with additional or deleted questions or bank
  numbers) and Principle VII (the status derived on the server and checked on every read of
  questions), and the "PDF files" row of the technology stack (made at download, not stored; the study
  materials may be kept in memory but never served stale).
- **Product requirements** (updated with the milestone): the "Teacher responsibilities", "Teacher
  access rights to competitions" ("Read") and "Additional questions" sections.
- **Technical requirements**: the "PDF files" row.
- **Milestone 5**: roles, "access denied" and the automated route check.
- **Milestone 8**: **Can manage competitions** and the teachers' **Read** and **Write** links.
- **Milestones 10 and 10.1**: the component library, the gallery, the UI guidelines and the loading
  feedback.
- **Milestone 11**: the question bank, soft deletion and "Subject not found" on the **Questions** tab.
- **Milestone 12.1**: competitions, statuses, the actions menu, the subject list with its
  **Deactivated subjects** group, "Competition not found" and the deactivated-subject rules.
- **Milestone 12.2**: a competition's **Questions** page, **Add questions**, the copies of questions and
  their order.
- **Milestones 12.3 and 12.4**: the **Answers** pages, which stay unchanged.
- **Milestone 12.5**: the two languages, the message catalogues and Kyiv time.
- **Milestone 12.7**: the logo.
- **Milestone 12.8**: the results file's design, the PDF library and font, the download entry of the
  actions menu, the file name rule and the design review process.
- **Milestone 12.9**: the additional questions, which the questions file holds without the mark and the
  study materials leave out.
- **Later milestones that depend on this one**: milestone 14 shows the published results to students;
  no later milestone is needed for the study materials, which teachers hand to students themselves.

## Out of Scope

- Giving either file to students or administrators in the application, or to anyone not signed in.
- Sending the files by email or to any external service.
- A questions file of an **Upcoming** or **Cancelled** competition, or a questions file with reference
  answers.
- Study materials with the additional or deleted questions, of a deactivated subject, of several
  subjects at once, or with a choice of questions.
- Storing either file in the database, or keeping the questions file in memory.
- Other formats (spreadsheet, document, plain text), other languages, a combined bilingual file or a
  download of both languages at once.
- Changing the **Answers**, **Grades** or **Teams** pages, or the **Questions** page for teachers with
  the setting.
- Changing the question bank's **Questions** tab, or showing the study materials on a page.
- Answer evaluation by an LLM (milestone 13) and results on the web pages (milestone 14).
