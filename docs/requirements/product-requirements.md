# Product Requirements

## Context

A web application for running online competitions among students, testing their knowledge in a specific subject area.

## Roles

### Student

- Takes part in competitions as a member of a team, by answering questions in writing.
- Cannot edit their own profile.
- Can view the list of competitions they have taken part in, with results:
  - title
  - subject
  - date
  - start time
  - final score
  - place
- Can view the list of upcoming competitions they are scheduled to take part in:
  - title
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
   - the start time and duration of the competition (usually 1 hour)
   - the list of questions
   - the participating teams (a team usually has fewer than 10 members, at most 50)
5. **Viewing competitions.** The teacher can view the list of all competitions, both past and planned. For upcoming competitions, the teacher can edit the participating teams, the title and the list of questions, according to their access rights.

#### Teacher access rights to competitions

- **Edit** — a teacher can edit all competitions they created. A teacher can edit access rights of other teachers for their own competitions.
- **Read** — every teacher has read access to all competitions.

#### Teacher access to students

- A teacher is linked to one or more educational institutions.
- A teacher only has access to the list of students from their own educational institutions.
- Each link has an access level: **Read** (see the institution's students, its teams and the students' results) or **Write** (also add, edit and delete the students, and manage the teams).
- The students of an educational institution are divided into classes (for example "KN-21"). Each class has a year of study, shared by all its students. A student belongs to exactly one educational institution and exactly one class in it. A teacher with Write access keeps the list of classes of that institution.
- A teacher sees a student's data only for their own institutions, never anything about an institution the student belonged to before.
- Only an administrator can link a teacher to an educational institution and set the access level.
- Only a teacher whom an administrator allowed to manage competitions can create competitions and change the question bank.

### Administrator

- Adds and deletes teachers in the application.
- Links a teacher to one or more educational institutions, selecting them from the list of institutions, with Read or Write access to each.
- Decides whether a teacher can manage competitions: create competitions and change the question bank.
- Is the only role that can edit the list of educational institutions.
- Is the only role that can edit the list of subjects.

## Personal data

- Email, first name and last name are personal data for every role. A student's educational institution, class (and so their year of study) and the teams they belong to are personal data too. A student agrees again each time they join an educational institution.
- Personal data is stored only after the person has agreed to it. An administrator or teacher who adds someone sends an invitation. The person's data is saved only when that person opens the invitation and accepts the consent text. Until then, nothing about them is kept.
- Every person can see the personal data stored about them and can withdraw consent at any time, even after being removed. Withdrawing erases their personal data and ends their access.
- Administrators are the exception: they are set by deployment configuration, not invited. Withdrawing consent does not remove an administrator's role or email.

## Competition

### How a competition works

- A teacher organizes a competition in one subject for a specific date and time with a specific duration (usually one hour).
- Teams take part in a competition: the students of the participating teams answer the given questions in writing (text).
- Answers are evaluated using AI. The input for evaluation is the question text and the correct answer prepared in advance by the teacher. Each answer is assigned a score.
- The winner is the student with the highest total score, calculated as the sum of scores across all questions in the competition.

### Question

A question in a competition is usually 1–3 lines of text and expects a text answer. Every question belongs to one subject. A deleted question is only hidden: it stays stored, but it is no longer shown in the question bank and can no longer be added to new competitions. Completed competitions keep showing it.

### Team

A team is a named group of students of one educational institution, put together by a teacher without changing their classes. Teams are the participants of competitions. A team belongs to one institution and never moves to another. Its name is unique across all institutions. A student can belong to several teams of their institution, but to each team only once. A team has at most 50 members. A deleted team is only hidden: it stays stored with all its members, but it is no longer shown when managing teams or competitions and can no longer join new competitions. Completed competitions keep showing it. An institution that holds any team, even a deleted one, cannot be deleted.

### Subject

A subject is a knowledge area, such as mathematics or physics, that competitions test. Administrators keep the list of subjects. Every question and every competition belongs to exactly one subject, and a competition contains only questions of its own subject. A subject used by any question, even a deleted one, or by any competition can only be deactivated, never deleted, so completed competitions keep showing it.

## Production usage

IMPORTANT!!! No real users will be involved until all milestones are executed. So there are no reasons to add complexity to the system to smoothly go from one milestone to another without any end-users disruptions.