# Product Requirements

## Context

A web application for running online competitions among students, testing their knowledge in a specific subject area.

## Roles

### Student

- Takes part in competitions as a member of a team. The team answers the questions in writing, one answer per question; a student has no answers of their own.
- Cannot edit their own profile.
- Can view the list of competitions they have taken part in, with results:
  - name
  - subject
  - date
  - start time
  - the team's final score
  - the team's place
- Can view the list of upcoming competitions they are scheduled to take part in:
  - name
  - subject
  - date and time

### Teacher

#### Teacher responsibilities

1. **Managing students.** Add, delete and edit students in the application. To add a student, the teacher needs:
   - the student's work email
   - first name
   - last name
   - educational institution
   - the class within the educational institution; the student's year of study is the year of their class
2. **Managing teams.** Put students of one educational institution together into named teams (see [Team](#team)). A teacher with Write access to the institution creates, renames and deletes its teams and adds and removes their members.
3. **Managing the question bank.** Edit the global list of questions used in competitions. Questions can be reused across different competitions. Each question belongs to one subject, selected from the list of subjects. For each question, the teacher adds the correct answer as text. Only teachers allowed to manage competitions change the question bank; every other teacher can read it.
4. **Running a competition.** The teacher selects:
   - the subject of the competition; only questions of that subject can be added to it
   - the name and the start date and time of the competition; a competition has no duration and runs until a teacher stops it
   - the list of questions
   - the participating teams (a team usually has fewer than 10 members, at most 50)
5. **Entering team answers.** While a competition is in progress, a teacher with Write access to an educational institution enters the answers of its teams, one text answer per question per team. A teacher with Read access sees only how many questions each team has answered, not the answers. After the competition has finished, the answers can no longer be changed: a teacher with Write access sees them read-only, with their grades and the team's score, to discuss them with the team.
6. **Viewing competitions.** The teacher can view the list of all competitions, both past and planned. A teacher allowed to manage competitions can edit the name, the start, the participating teams and the list of questions of any upcoming competition, stop (finish) any competition in progress, and cancel any competition that is not finished (see [Competition statuses](#competition-statuses)).
7. **Grading answers.** After a competition has finished, a teacher allowed to manage competitions grades its teams' answers by hand: each answer gets a whole-number grade from 0 to 10. They grade the answers of every team in the competition, whatever its educational institution, and can change a grade at any time. A team's score is the sum of its grades.

#### Teacher access rights to competitions

- **Read** — every teacher has read access to all competitions.
- **Manage** — a teacher whom an administrator allowed to manage competitions creates, edits, stops, cancels and grades any competition, whoever created it. There are no access rights per competition.

#### Teacher access to students

- A teacher is linked to one or more educational institutions.
- A teacher only has access to the list of students from their own educational institutions.
- Each link has an access level: **Read** (see the institution's students, its teams, how many questions its teams have answered in a competition in progress, and the teams' results) or **Write** (also add, edit and delete the students, manage the teams and enter the teams' answers).
- The students of an educational institution are divided into classes (for example "KN-21"). Each class has a year of study, shared by all its students. A student belongs to exactly one educational institution and exactly one class in it. A teacher with Write access keeps the list of classes of that institution.
- A teacher sees a student's data only for their own institutions, never anything about an institution the student belonged to before.
- Only an administrator can link a teacher to an educational institution and set the access level.
- Only a teacher whom an administrator allowed to manage competitions can create and manage competitions and change the question bank.

### Administrator

- Adds and deletes teachers in the application.
- Links a teacher to one or more educational institutions, selecting them from the list of institutions, with Read or Write access to each.
- Decides whether a teacher can manage competitions: create, edit, stop, cancel and grade any competition, and change the question bank.
- Is the only role that can edit the list of educational institutions.
- Is the only role that can edit the list of subjects.

## Personal data

- Email, first name and last name are personal data for every role. A student's educational institution, class (and so their year of study) and the teams they belong to are personal data too. A student agrees again each time they join an educational institution.
- A team's answers are not personal data: they belong to the team, and who entered them is not stored.
- Personal data is stored only after the person has agreed to it. An administrator or teacher who adds someone sends an invitation. The person's data is saved only when that person opens the invitation and accepts the consent text. Until then, nothing about them is kept.
- Every person can see the personal data stored about them and can withdraw consent at any time, even after being removed. Withdrawing erases their personal data and ends their access.
- Administrators are the exception: they are set by deployment configuration, not invited. Withdrawing consent does not remove an administrator's role or email.

## Competition

### How a competition works

- A teacher organizes a competition in one subject for a specific date and time. A competition has no duration: it starts on its own at its start time and runs until a teacher stops it.
- Teams take part in a competition: each participating team gives one written (text) answer to each question. The answers belong to the team, not to its students: the team's members, or a teacher with Write access to its educational institution, enter them, and the last save wins. A student has no answers of their own.
- After the competition has finished, a teacher allowed to manage competitions grades the answers by hand, a whole number from 0 to 10 per answer. A question a team did not answer has no grade. Who graded an answer, or when, is not stored.
- Answers are evaluated using AI. The input for evaluation is the question text and the correct answer prepared in advance by the teacher. Each answer is assigned a score.
- The winner is the team with the highest total score, calculated as the sum of its scores across all questions in the competition.

### Competition statuses

- **Upcoming** — before its start. Only an upcoming competition can be edited.
- **In progress** — from its start, reached on its own with nobody acting, until a teacher stops it. A team's answers are entered only while its competition is in progress.
- **Finished** — after a teacher allowed to manage competitions stops it (the action **Finish competition**). A finished competition cannot be cancelled, and its questions, teams and answers never change again; its answers are graded, and its results can always be reviewed.
- **Cancelled** — after a teacher allowed to manage competitions cancels it, which is possible in any status except **Finished**. Cancelling is final: a cancelled competition never changes again and cannot be restored.

Deleting a team is the one exception to "only an upcoming competition can be edited" and "a cancelled competition never changes again": it takes the team out of every competition that is not finished (upcoming, in progress and cancelled). A deleted team stays only in finished competitions, so their record stays complete.

### Question

A question in a competition is usually 1–3 lines of text and expects a text answer. Every question belongs to one subject. A competition holds a copy of each of its questions, taken when the question is added, so editing or deleting the question in the bank afterwards does not change the competition. A deleted question is only hidden: it stays stored, but it is no longer shown in the question bank and can no longer be added to new competitions. Competitions that hold it keep their copy.

### Team

A team is a named group of students of one educational institution, put together by a teacher without changing their classes. Teams are the participants of competitions. A team belongs to one institution and never moves to another. Its name is unique across all institutions. A student can belong to several teams of their institution, but to each team only once. A team has at most 50 members. Any team that is not deleted, of an active institution in an active region, can be added to a competition by a teacher allowed to manage competitions, whether or not the teacher is linked to its institution. A deleted team is only hidden: it stays stored with all its members, but it is no longer shown when managing teams or competitions and can no longer join new competitions. Deleting a team takes it out of every competition that is not finished and deletes its answers in them; finished competitions keep it with its answers, marked deleted. An institution that holds any team, even a deleted one, cannot be deleted.

### Subject

A subject is a knowledge area, such as mathematics or physics, that competitions test. Administrators keep the list of subjects. Every question and every competition belongs to exactly one subject, and a competition contains only questions of its own subject. A subject used by any question, even a deleted one, or by any competition can only be deactivated, never deleted, so completed competitions keep showing it. Deactivating a subject hides its questions and every one of its competitions that is not finished, and they cannot be opened until it is activated again; its finished competitions stay available, so their answers can still be graded and their results reviewed; nothing else about them changes.

## Production usage

IMPORTANT!!! No real users will be involved until all milestones are executed. So there are no reasons to add complexity to the system to smoothly go from one milestone to another without any end-users disruptions.