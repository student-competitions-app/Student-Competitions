# Product Requirements

## Context

A web application for running online competitions among students, testing their knowledge in a specific subject area.

## Roles

### Student

- Takes part in competitions against other students by answering questions in writing.
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
   - group code (text) within the educational institution
   - the student's year of study at the educational institution
2. **Managing the question bank.** Edit the global list of questions used in competitions. Questions can be reused across different competitions. Each question belongs to one subject, selected from the list of subjects. For each question, the teacher adds the correct answer as text.
3. **Running a competition.** The teacher selects:
   - the subject of the competition; only questions of that subject can be added to it
   - the start time and duration of the competition (usually 1 hour)
   - the list of questions
   - the list of participants (usually up to 10 people)
4. **Viewing competitions.** The teacher can view the list of all competitions, both past and planned. For upcoming competitions, the teacher can edit the list of participants, the title and the list of questions, according to their access rights.

#### Teacher access rights to competitions

- **Edit** — a teacher can edit all competitions they created. A teacher can edit access rights of other teachers for their own competitions.
- **Read** — every teacher has read access to all competitions.

#### Teacher access to students

- A teacher is linked to one or more educational institutions.
- A teacher only has access to the list of students from their own educational institutions.
- Only an administrator can link a teacher to an educational institution.

### Administrator

- Adds and deletes teachers in the application.
- Links a teacher to one or more educational institutions, selecting them from the list of institutions.
- Is the only role that can edit the list of educational institutions.
- Is the only role that can edit the list of subjects.

## Personal data

- Email, first name and last name are personal data for every role. A student's educational institution, group code and year of study are personal data too.
- Personal data is stored only after the person has agreed to it. An administrator or teacher who adds someone sends an invitation. The person's data is saved only when that person opens the invitation and accepts the consent text. Until then, nothing about them is kept.
- Every person can see the personal data stored about them and can withdraw consent at any time. Withdrawing erases their personal data and ends their access.

## Competition

### How a competition works

- A teacher organizes a competition in one subject for a specific date and time with a specific duration (usually one hour).
- Students answer the given questions in writing (text).
- Answers are evaluated using AI. The input for evaluation is the question text and the correct answer prepared in advance by the teacher. Each answer is assigned a score.
- The winner is the student with the highest total score, calculated as the sum of scores across all questions in the competition.

### Question

A question in a competition is usually 1–3 lines of text and expects a text answer. Every question belongs to one subject.

### Subject

A subject is a knowledge area, such as mathematics or physics, that competitions test. Administrators keep the list of subjects. Every question and every competition belongs to exactly one subject, and a competition contains only questions of its own subject.

## Production usage

IMPORTANT!!! No real users will be involved untill all milestones are executed. So there are no reasons to add complexity to the system to smmothly go from one milestone to another without any end-users disruptions.