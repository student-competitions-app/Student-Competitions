# Milestones

The milestone ladder for the product described in [product-requirements.md](product-requirements.md), built with the stack in [technical-requirements.md](technical-requirements.md). Each milestone is delivered as one Spec Kit feature.

The ladder follows a "walking skeleton" approach: first ship an empty skeleton to the internet, then grow it with vertical slices. Each step ends with a working, testable and meaningful result.

**Delivered milestones** are short summaries of what the product does after them. Their specification in [`specs/`](../../specs/) is the source of truth for details, and the summary is updated only if the product behaviour changes. **Upcoming milestones** hold the full scope, refined until every detail is clear, and are the input for `speckit-specify`.

## Delivered

1. **Hello World locally.** _Spec:_ [001-hello-world-page](../../specs/001-hello-world-page/spec.md)
   - The application runs on a developer's machine and serves one server-rendered home page with the application name and a short description of its purpose.
   - The page is readable on desktop and phone-width screens. Unknown addresses show a friendly "not found" page.
   - A developer can set up, run and test the application by following the README.

2. **Deploy Hello World to the internet + CI/CD.** _Spec:_ [002-public-deploy-cicd](../../specs/002-public-deploy-cicd/spec.md)
   - The home page from milestone 1, unchanged, is available to anyone at a public HTTPS address.
   - Every pull request is checked automatically (tests, code style, formatting) and cannot be merged while a check fails.
   - Every merge to `main` is published automatically with no manual steps. A failed publish leaves the previous version serving visitors.
   - A public status address reports that the service is alive and which version is running.

3. **Database + first entity.** _Spec:_ [003-database-questions](../../specs/003-database-questions/spec.md)
   - The application keeps its data in a database that survives restarts and redeploys.
   - The first product entity is the **question**: question text (up to 1,000 characters) and a reference answer (up to 5,000 characters), both required. Questions can be created, read, updated and deleted inside the application, but not yet through the website.
   - The home page lists at least five sample questions, read-only. Reference answers are never shown publicly.
   - The home page shows a database status line: the database kind, the schema version and a boot count that goes up with every application start, which proves that data persists.
   - If the database is briefly unreachable, the home page still opens and shows "data temporarily unavailable".

4. **Email code authentication.** _Spec:_ [004-email-otp-auth](../../specs/004-email-otp-auth/spec.md)
   - People sign in with their email address and a one-time code sent to it. There are no passwords, no sign-in links and no sign-up: only active users already known to the application can sign in.
   - In this milestone the only users are site administrators. Operations owns their list in the deployment configuration; the website can never grant or revoke administrator rights. An address removed from the list is deactivated and signed out everywhere. Users are never deleted.
   - A code has 6 digits, is valid for 20 minutes and works once. A new code replaces the previous one. A code allows 5 wrong attempts, and code requests are limited to 5 per email address and 20 per client per hour.
   - Sign-in behaves the same for registered and unregistered addresses, so it never reveals whether an address belongs to a user. Email addresses are not written to logs.
   - Every page, including the home page, requires sign-in. Only the sign-in and sign-out steps, the status address and static files are public. An anonymous visitor is sent to sign in and then returned to the page they asked for.
   - A session lasts 14 days from sign-in; activity does not extend it. The header shows the signed-in email and a **Log out** button.
   - There is no way to bypass the emailed code.

5. **Roles and authorization.** _Spec:_ [005-roles-authorization](../../specs/005-roles-authorization/spec.md)
   - Three roles: administrator, teacher and student. Operations sets three lists of email addresses in the deployment configuration, one per role. One person can be on several lists and so hold several roles. A person on no list cannot sign in. The teacher and student lists are temporary; milestones 8 and 9 replace them with management in the application.
   - Removing any role from a person signs them out everywhere; adding a role does not.
   - A signed-in person always acts in one role. A person with one role gets it right after sign-in. A person with several roles chooses one (in the order administrator, teacher, student) and then lands on the page they originally asked for; until then no other page opens.
   - A person with several roles can switch role from the header at any time without signing out, and lands on the home page.
   - Access follows the current role only: someone who is both an administrator and a student cannot open administrator pages while using the student role. A page the current role may not open shows "access denied", naming the current role; the role is never switched automatically.
   - Every page states which roles may open it, and access is denied by default.
   - Pages: the home page for all roles, with links to only the pages the current role can open; placeholder **Administrator area**, **Teacher area** and **Student area** pages, each for its own role; a placeholder **Staff area** for administrators and teachers.
   - The header shows "Student Competitions · <Role>" in the top left corner, and the email, the role switch (for several roles) and **Log out** on the right.

6. **Administrator area and subjects.** _Spec:_ [006-admin-area](../../specs/006-admin-area/spec.md)
   - The administrator page becomes an administrator area with three tabs: **Teachers**, **Educational institutions** and **Subjects**. Each tab is an ordinary link to its own page (`/admin/teachers`, `/admin/institutions`, `/admin/subjects`), so it can be bookmarked and reloaded. The current tab is highlighted, and `/admin` opens the **Teachers** tab. The area is open only to the administrator role.
   - The **Teachers** and **Educational institutions** tabs are placeholders in this milestone.
   - A **subject** is a knowledge area in which competitions are held, such as mathematics or physics. The **Subjects** tab lists all subjects, active and deactivated, sorted by name ignoring case, with deactivated ones marked. An empty list shows "No subjects yet". The list starts empty.
   - **Create** and **Rename** use a form with one field, the name: trimmed, 1–200 characters, no control characters, and unique ignoring case, including deactivated subjects and non-Latin letters. An invalid or duplicate name shows the form again with the error and the entered value. A change of case alone is a valid rename.
   - **Deactivate** keeps the subject but stops offering it for new questions (milestone 10) and new competitions (milestone 11). Questions and competitions that already use it stay valid. **Activate** reverses it.
   - **Delete** asks for confirmation and is refused while anything uses the subject, suggesting deactivation instead.

7. **Administrator area: educational institutions.** _Spec:_ [007-region-and-institutions-management](../../specs/007-region-and-institutions-management/spec.md)
   - The **Educational institutions** tab shows two lists side by side: regions on the left and the educational institutions of the selected region on the right. On narrow screens they stack, regions first.
   - The selected region is highlighted and kept in the page address, so it survives reloads and bookmarks. With no region selected, the right side shows "Select a region". After an action, the affected region stays selected.
   - Both lists show active and deactivated items, sorted by name ignoring case, with deactivated items marked. Empty lists show "No regions yet" and "No educational institutions yet". There is no preset list; both start empty.
   - Names of regions and institutions follow the same rules as subject names. Region names are unique. Institution names are unique within their region ("already exists in this region"); the same name may exist in different regions.
   - **Regions** offer **Create**, **Rename**, **Deactivate** / **Activate** and **Delete**. Delete asks for confirmation and is refused while the region holds any institution. A deactivated region accepts no new institutions, and none of its institutions can be selected anywhere; the institutions' own statuses do not change, and they stay fully manageable.
   - **Educational institutions** offer the same actions. An institution is created in the selected region, which must be active, and can never move to another region. Delete asks for confirmation, naming the institution and its region, and is refused while anything uses the institution (teacher links from milestone 8, students from milestone 9), suggesting deactivation instead.
   - An institution can be selected (when inviting or editing teachers in milestone 8 and students in milestone 9) only when it and its region are both active. Existing links to an institution that later becomes unavailable stay valid.

8. **User management with consent: teachers.** _Spec:_ [008-teacher-management-consent](../../specs/008-teacher-management-consent/spec.md)
   - Administrators invite teachers by email. Nothing about an invited person is stored until they press **I agree** on the consent page: the whole invitation travels encrypted and tamper-proof inside the emailed link, valid for 7 days. Invitations are rate-limited per inviter and per address. Accepting creates, extends or reactivates the person, stores the names and teacher details and a consent record (role, consent text version, time, inviter), and leads to the sign-in page with the email filled in.
   - An invitation is refused when it was tampered with, expired, its inviter is no longer an administrator, one of its institutions is no longer selectable, or the teacher role was removed or consent withdrawn after it was issued. Expiry has its own message; every other refusal shares one neutral message.
   - Each teacher is linked to one or more educational institutions with **Read** or **Write** access and has one **Can create competitions** setting. Only administrators set them; they are stored and shown, and later milestones enforce them. Only active institutions in active regions can be picked; a link to an institution deactivated later is kept and shown as deactivated. An institution linked to a teacher cannot be deleted.
   - The **Teachers** tab lists current teachers sorted by last name, with email, institutions and access levels, the setting and the date of consent. Each teacher's page edits the names, institutions, levels and setting, or removes the teacher, which signs them out everywhere and deactivates them if no role is left. The email cannot be edited.
   - Every signed-in person has a read-only profile (the header email links to it) with their data, roles, teacher details and the consent texts they accepted. **Withdraw consent** erases the names, replaces the email (administrators keep theirs), removes the teacher role and signs the person out everywhere; consent records are kept.
   - **Delete my data** on the sign-in page emails a one-hour, one-use link that erases the same way, without signing in. Every address gets the same answer.
   - Consent texts are versioned per invitable role and never change once published. The invitation, acceptance, profile and withdrawal flow is shared by every invitable role, so milestone 9 adds students without changing it.
   - `TEACHER_EMAILS` and `STUDENT_EMAILS` are retired: roles they granted were removed once, at deploy. `ADMIN_EMAILS` manages only the administrator role. Emailed links use `PUBLIC_BASE_URL`. No log line contains an email, a name or a link token.

## Upcoming

9. **User management with consent: classes and students.** Teachers keep the classes of the institutions where they have Write access (milestone 8) and invite students into them. The student role joins the milestone 8 invitation and consent flow as one more invitable role. The flow changes only where this milestone says so: the names of a person who already is a teacher or a student are kept on acceptance (for teacher invitations too), the student invitation form checks for an existing student, student invitations have their own limit per inviter, and the inviter and institution checks at acceptance are different for students.

   **Functional requirements**

   _Classes:_
   - A **class** is a named group of students inside one educational institution, such as "KN-21", with a required **year of study**: a whole number from 1 to 12. Several classes of one institution may share a year. Every institution starts with no classes.
   - Class names follow the subject-name rules (milestone 6) and are unique within their institution ignoring case ("already exists in this institution"); the same name may exist in different institutions.
   - A class is created in an available institution (see _Deactivation_) and never moves to another institution. A class is not personal data, so it is stored as soon as it is created.
   - Classes can be created, edited (name and year of study), deactivated, activated and deleted. A deactivated class accepts no new students. Delete is refused while the class holds any student.
   - Deleting an educational institution (milestone 7) is still refused while any teacher is linked to it or any student is enrolled in it. Classes without students do not prevent the deletion and are deleted together with the institution; the confirmation says so.

   _Enrolment:_
   - A student belongs to exactly one educational institution and exactly one of its classes. This is the student's **enrolment**: the institution and the class.
   - The student's institution and class are personal data. The enrolment is stored only when the student accepts an invitation.
   - Moving to another class needs no new consent.

   _Deactivation:_
   - Regions, educational institutions, classes and students form a chain: a region holds institutions, an institution holds classes, a class holds students. An object is **available** when it and every object above it in the chain are active. Deactivating an object makes everything below it unavailable without changing their own statuses; once the object is active again, everything below it whose own status is active is available again.
   - An unavailable object, and everything below it, is not shown and cannot be selected, opened or used anywhere: in lists, drop-down lists, page addresses, submitted forms, invitations and later in competitions. The only exception is the place where the deactivated object itself is managed, where it stays visible and marked as deactivated so it can be activated again: regions and institutions in the administrator area (milestone 7), teacher links on the administrator's teacher page (milestone 8), and classes on the **Students** tab. The objects below it stay hidden even there.
   - A student whose class is unavailable is **blocked**. A blocked student keeps all their data, but:
     - when the deactivation happens, they are signed out everywhere, as when a role is removed (milestone 5);
     - a person with no other role is treated at sign-in as a removed person (milestone 8): sign-in behaves as for an unknown address. A person with other roles is not offered the student role;
     - they can still delete their data through **Delete my data** on the sign-in page (milestone 8);
     - they cannot take part in competitions;
     - teachers do not see them and cannot edit or remove them.
   - Once the class is available again, the student can sign in with the student role again and teachers see them again. Nothing else changes.

   _Access:_
   - The teacher area: the teacher role only.
   - Seeing classes and students: available institutions the teacher is linked to, with Read or Write access. A teacher sees the names, email and class of the students of the available classes of these institutions.
   - Managing classes and adding, editing and removing students: institutions with Write access. Administrators do not manage classes or students.
   - A teacher can reach only the available institutions they are linked to, all their classes (deactivated ones included), and the students of their available classes, also through the page address. Anything else, in the page address or in a submitted form, shows "access denied". A management action on an institution with Read access also shows "access denied".

   _Inviting students:_
   - A teacher invites students into the selected class one by one, entering the email, first name and last name (validated as in milestone 8).
   - On submission, the email must not belong to anyone who holds the student role, in any institution. Otherwise the form shows again with "This email already belongs to a student" and the entered values, and no invitation is sent. The message never names the institution or the class. This is an intended exception to the milestone 8 rule that the invitation form does not check existing roles: a teacher may learn that an address is used by a student of an institution they are not linked to, but nothing more about that student.
   - Student invitations are limited to 100 per inviter per hour (teacher invitations stay at 20, milestone 8). The limit per invited address stays at 5 per hour.
   - Otherwise, the invitation, its email and its link work as in milestone 8.

   _Accepting:_
   - The milestone 8 checks apply unchanged: a tampered link is refused, an expired one has its own message, an invitation issued before the person lost the student role or withdrew consent is refused, and a changed consent text shows the page again.
   - The milestone 8 inviter and institution checks are replaced for students. The invitation is refused, with the neutral message from milestone 8, when:
     - the inviter is no longer an active user holding the teacher role with Write access to the invited institution;
     - the invited class is no longer available: it was deleted, or it, its institution or its region was deactivated.
   - Names, for both invitable roles: when the person already holds the teacher or the student role, their current names are kept and the names from the invitation are not used. This changes milestone 8, where a teacher invitation always stored the invited names. In every other case (a new person, an inactive person, or an administrator without these roles) the names from the invitation are stored. The acceptance page of both roles says "If you are already a teacher or a student, your current names are kept."
   - Accepting creates the enrolment and a consent record (as in milestone 8) and grants the student role; for example, a teacher keeps the teacher role and gains the student role.
   - If the person became a student after the invitation was sent, accepting changes nothing and the page says they are already a student (the milestone 8 rule for a role already held).

   _Consent text:_ a student consent text, versioned like the teacher one: a fixed text that never names a particular institution or class. The invited institution and class are shown on the acceptance page as the data to be stored, not in the consent text, and the consent record does not store them. The text says that the class, and with it the year of study, is stored along with the email and names, and who can see them. Placeholder wording is fine until real users arrive, as in milestone 8.

   _Editing and removing students:_
   - **Edit** changes the student's names and class. The new class must be an active class of the same institution. The email, the institution and the year of study (on its own) cannot be edited.
   - **Remove** takes the student out of the institution: the enrolment is deleted and the consent records are kept, then it works as in milestone 8: the student role is removed, the person is signed out everywhere, and is deactivated if no role is left.

   _Withdrawing consent:_
   - Withdrawing consent works the same way as in milestone 8.

   _Profile:_
   - The profile (milestone 8) of a student also shows the enrolment: the institution with its region, the class and the year of study, next to the student role and the student consent records. While the student is blocked, the enrolment is still shown, marked as deactivated.
   - For a student, the profile says that corrections to student data go through a teacher of their institution (for teacher data it still says an administrator, milestone 8).

   **User interface**

   _Teacher area:_
   - The teacher page becomes a teacher area that looks like the administrator area (milestone 6), with two tabs: **Students** (`/teacher/students`, opened by `/teacher`) and **Competitions** (`/teacher/competitions`). Each tab is an ordinary link, so it can be bookmarked and reloaded; the current tab is highlighted.
   - **Competitions** is a placeholder; milestones 11 and 14 fill it.

   _Students tab: choosing a class:_
   - Three drop-down lists sit in a row at the top: **Region**, **Educational institution** and **Class**, stacked in that order on narrow screens. Each is disabled until the previous one is selected. All are sorted by name ignoring case.
     - **Region**: active regions that hold at least one active institution the teacher is linked to.
     - **Educational institution**: the teacher's active institutions of the selected region, each marked "Read" or "Write".
     - **Class**: all classes of the selected institution, each with its year of study, deactivated ones marked. With Write access, the last entry is **+ Add class**, which opens a form with the name and the year of study; the new class is then selected.
   - Until the chain is complete, the middle of the page shows one message instead of the student list: "Select a region to continue", "Select an educational institution to continue" or "Select a class to see its students". A teacher linked to no available institution sees "You are not linked to any educational institution" and disabled lists.
   - The selected region, institution and class are kept in the page address, so they survive reloads and bookmarks. After an action, the affected class stays selected.

   _Students tab: the selected class:_
   - A bar shows the class name and year of study, marked if deactivated. With Write access, it offers **Edit** (the same form as creating), **Deactivate** / **Activate**, **Delete** and, while the class is active, **Add student**. **Deactivate** asks for confirmation, saying that the class's students will be signed out and hidden until the class is activated again. **Delete** asks for confirmation, naming the class and its institution; a refusal suggests deactivation instead, but only if the institution isn't deactivated already.
   - Below it, the students of an active class are listed by last name ignoring case: name, email. An empty class shows "No students in this class yet". A deactivated class shows "This class is deactivated; its students are hidden until it is activated again". With Write access, each student has **Edit** and **Remove**; with Read access, the bar and the list have no actions.
   - **Edit** offers the active classes of the institution.
   - **Remove** asks for confirmation, naming the student, the class and the institution, and then works as described in _Editing and removing students_.

   _Out of scope:_
   - the content of the **Competitions** tab

  10. **Question bank (teacher).** Uploading a list of questions, viewing, editing, reference answers for questions.
    _Subjects:_ every question belongs to exactly one subject. The teacher selects it from the list kept on the **Subjects** tab (milestone 6), with no free-text entry, and the server accepts only a subject that exists. Teachers can filter the question bank by subject. The sample questions seeded in milestone 3 have no subject, and the migration deletes them, since no real data exists yet.
    _Test:_ question CRUD works and is visible only to teachers. A question without a subject or with an unknown subject is refused. Filtering by subject shows only that subject's questions.

11. **Creating a competition (teacher).** A competition with a subject, a start time, duration, assignment to a class/students, a set of questions from the bank and reference answers.
    _Who can create:_ only a teacher with **Can create competitions** (milestone 8) can create or change competitions. A teacher without it sees no create action, and the server answers with "access denied". The setting covers all the teacher's institutions, so participants can be students of any of them, with Read or Write access. Students of other institutions cannot be assigned.
    _Subjects:_ the teacher selects the competition's subject first, from the list kept on the **Subjects** tab. The question picker then offers only questions of that subject, and the server refuses a competition that includes a question of another subject. Changing the subject of an upcoming competition is refused while it still holds questions of the old subject.
    _Test:_ a competition is created and correctly linked to its subject, questions and participants. A competition with a question from another subject is refused. A teacher without **Can create competitions** gets "access denied". A teacher with it can assign students of a Read-access institution, but not students of an institution they are not linked to.

12. **Taking a competition (student).** List of assigned competitions, enforcement of the time window and duration, entering and submitting text answers. The student's lists of upcoming and past competitions show each competition's subject.
    _Test:_ answers are saved; the competition is not accessible outside its time window.

13. **Answer evaluation via LLM.** Each answer receives a score of 1–10 that takes level of detail into account; results are saved to the database.
    _Test:_ evaluation returns a structured result and it is persisted.

14. **Best answer selection + results.** For each question, the best answer is selected from the group's answers; competition results are saved and displayed.
    _Who sees results:_ a teacher sees the results of the students of their own institutions, with Read or Write access (milestone 8). Results of students from other institutions are not shown to them.
    _Test:_ the best answer is determined, the results page works. A teacher with Read access sees the results of that institution's students and none from institutions they are not linked to.

15. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)
