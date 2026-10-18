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

9. **User management with consent: classes and students.** The teacher page becomes a teacher area. Teachers keep the classes of the institutions where they have Write access (milestone 8) and add students to them. A student belongs to exactly one class in exactly one educational institution. The student role is added to the invitation and consent flow from milestone 8 as one more invitable role, so the flow itself does not change.
   _Teacher area:_
   - The teacher page becomes a teacher area with two tabs: **Students** and **Competitions**. Each tab is an ordinary link to its own page (`/teacher/students`, `/teacher/competitions`), so it can be bookmarked and reloaded. The current tab is highlighted. The area is open only to the teacher role, and it looks like the administrator area from milestone 6.
   - The **Competitions** tab is a placeholder; milestones 11 and 14 fill it.

   _Classes:_
   - A **class** is a named group of students inside one educational institution, such as "KN-21". A class is not personal data, so it is stored as soon as it is created.
   - Class names follow the same rules as subject names (milestone 6) and are unique within their institution ignoring case ("already exists in this institution"). The same name may exist in different institutions. There is no preset list; every institution starts with no classes.
   - A class is created in the selected institution, which must be selectable (it and its region are active), and can never move to another institution.
   - Only a teacher with Write access to the institution can create, rename, deactivate, activate or delete its classes. Administrators do not manage classes.
   - **Deactivate** keeps the class and its students, but the class accepts no new students. Its students stay fully manageable. Students in deactivated class can not participate in competitions. 
   - **Activate** reverses it.
   - **Delete** asks for confirmation, naming the class and its institution, and is refused while the class holds any student, suggesting deactivation instead. An institution that holds any class cannot be deleted (the milestone 7 rule).

   _Students, institutions and classes:_
   - A student belongs to exactly one educational institution and exactly one of its classes. This membership is the student's **enrolment**: the institution, the class, the year of study and the consent record. A student can never hold two enrolments or two classes at once, and the database enforces it.
   - Joining an institution always needs the student's consent for that institution, given by accepting an invitation. Moving to another class of the same institution needs no new consent.
   - A teacher sees the names, the email, the class and the year of study of the students of their institutions, and nothing about any institution a student belonged to before.

   _Students tab: choosing a class:_
   - Three drop-down lists sit in a row at the top of the page: **Region**, **Educational institution** and **Class**. On narrow screens they stack in that order.
   - **Region** offers the active regions that hold at least one active institution the teacher is linked to, with Read or Write access.
   - **Educational institution** offers the active institutions of the selected region that the teacher is linked to, each marked "Read" or "Write".
   - **Class** offers all classes of the selected institution, active and deactivated, with deactivated ones marked. Where the teacher has Write access, the last entry of the list is **+ Add class**, which opens a form with one field, the name. After creating, the new class is selected. With Read access there is no **+ Add class**.
   - All three lists are sorted by name ignoring case.
   - Until the chain is complete, the middle of the page shows one message instead of the student list:
     - no region selected: "Select a region to continue";
     - no institution selected: "Select an educational institution to continue";
     - no class selected: "Select a class to see its students".
     A teacher linked to no selectable institution sees "You are not linked to any educational institution" and disabled lists.
   - The selected region, institution and class are kept in the page address, so they survive reloads and bookmarks. After an action, the affected class stays selected. An address that names a region, institution or class the teacher may not see shows "access denied".
   - Students of a deactivated institution or region are kept but are not reachable until it is active again, because such an institution cannot be selected (milestone 7).

   _Students tab: the selected class:_
   - A bar above the student list shows the class name, marked if deactivated. Where the teacher has Write access, it offers **Rename**, **Deactivate** / **Activate**, **Delete** and **Add students**. **Rename** uses the same form as creating. **Add students** is offered only while the class is active.
   - Below the bar is the list of the class's students, sorted by last name ignoring case: name, email, year of study and the date of consent for this institution. An empty class shows "No students in this class yet".
   - Where the teacher has Write access, each student has **Edit** and **Remove**. With Read access, the bar and the list are shown without any actions, and the server answers such a request with "access denied".

   _Personal data:_ besides the email and names, a student's institution, class and year of study are personal data. The enrolment is stored only when the student accepts the invitation, like the rest.
   _Adding students:_
   - **Add students** opens a form for the selected class, which is shown at the top and cannot be changed in the form. The form starts with one student row: email, first name, last name and year of study.
   - **+ Add one more student** at the bottom of the form adds an empty row. Every row except the only one has a **Remove row** action. The form takes up to 20 rows, the per-inviter hourly limit from milestone 8.
   - Validation: the email and names as in milestone 8. The year of study is a whole number from 1 to 12. Two rows with the same email (ignoring case) are an error.
   - All rows are checked first. If any row is invalid, nothing is done, and the form shows again with every entered value and an error next to each wrong field. If the invitations would exceed a rate limit, nothing is done and the form says so.
   - When all rows are valid, each row is handled by its email:
     - **already in this class:** nothing changes; the row reports "already in this class".
     - **a student of this institution in another class:** nothing changes; the row reports "already in class <name>". The teacher moves the student with **Edit**.
     - **anyone else** (a new address, a user without the student role, or a student of another institution): an invitation is sent; the row reports "invitation sent". The report is the same whether or not the address belongs to a user or a student elsewhere.
     The teacher can already see every student of their institution, so the first two cases reveal nothing new. Only invitations count toward the rate limits.
   - Sending, the token, the email and the acceptance page work as in milestone 8. The token holds the class id and the year of study. After sending, the page lists the outcome of every row; if a send fails, it names the rows that were not sent so the teacher can send them again.
   - The server accepts the form only for an active class of an institution where the teacher has Write access.

   _Accepting:_
   - On top of the checks in milestone 8, the class must still exist and be active, its institution must be selectable, and the inviter must still be a teacher with Write access to that institution. Each refusal uses the neutral message from milestone 8.
   - A new person is created with the names from the invitation. An existing person's names are never changed by an invitation.
   - Accepting creates the enrolment in the class's institution, with the class, the year of study from the invitation and a consent record naming the institution. The person gains the student role if they did not hold it. Example: a teacher invited as a student gains the student role and keeps the teacher role.
   - If the person is a student of another institution, the consent page says, before **I agree**, that accepting moves them out of their current institution and class. Accepting deletes the old enrolment, keeps its consent record and creates the new one. The teachers of the old institution no longer see the student.
   - If the person became a student of the inviting institution after the invitation was sent, nothing changes and the page says "already a student of this institution".

   _Consent text:_ a student consent text, versioned like the teacher one and accepted on joining an institution. It names the institution and says that the class and year of study are stored, that the teachers of that institution can see them along with the email and names, that teachers of other institutions cannot, and that a student belongs to one institution at a time. Placeholder wording is fine until real users arrive, as in milestone 8.
   _Editing and removing students:_
   - **Edit** changes the student's names, year of study and class. The class list offers the active classes of the same institution; the student's current class stays selectable even if deactivated. Changing the class moves the student. The email cannot be edited, and a student cannot be moved to another institution this way.
   - **Remove** asks for confirmation, naming the student, the class and the institution, and takes the student out of the institution: the enrolment is deleted and its consent record is kept. The removal then works as in milestone 8: the student role is removed, the person is signed out everywhere, and they are deactivated if no role is left.

   _Profile and withdrawing consent:_
   - The profile also shows the student's enrolment: the institution with its region, the class and the year of study.
   - The enrolment has **Leave this institution**. It asks for confirmation, deletes the enrolment, keeps the consent record, removes the student role and signs the person out everywhere; if they hold no other role, it then works exactly as the full withdrawal from milestone 8.
   - The full **Withdraw consent** from milestone 8 also deletes the enrolment and removes the student role.
   - Corrections to a student's data go through a teacher with Write access to their institution.

   _Access:_ the teacher area: teachers only. Seeing classes and students: institutions the teacher is linked to. Managing classes and adding, editing and removing students: institutions with Write access.
   _Out of scope:_
   - importing students from a file
   - administrators seeing, inviting or removing students
   - parental consent for minors
   - the content of the **Competitions** tab

   _Test:_
   - `/teacher` opens the **Students** tab; both tabs open for the teacher role and show "access denied" for other roles. The **Competitions** tab is a placeholder.
   - The region list offers only active regions with an active institution the teacher is linked to; the institution list only the teacher's active institutions of that region; the class list all classes of that institution. Each list is disabled, and the matching message shows in the middle of the page, until the previous one is selected. The selection survives a reload.
   - Class names: validation, uniqueness within an institution, the same name in two institutions. Creating, renaming, deactivating, activating and deleting a class work with Write access and are refused with Read access. Deleting a class with students is refused. A deactivated class offers no **Add students** and refuses a submitted form. An institution with a class cannot be deleted.
   - End to end: a teacher adds two new students in one form, and both links are read from the `memory` outbox. The GET creates nothing. Each POST creates the user with the student role, the enrolment with its class and a consent record. A student then signs in and sees the institution and class on their profile.
   - A row with a student of the same institution, in this class or another one, changes nothing, sends no email and reports the student's class. A row with a student of another institution sends an invitation; the consent page warns about the move, and accepting deletes the old enrolment, keeps its consent record, creates the new enrolment and consent record and leaves the names unchanged. The old institution's teachers no longer see the student.
   - The database refuses a second enrolment or a second class for the same student.
   - **Edit** moves a student to another active class of the same institution and refuses a deactivated class or a class of another institution. The outcome reported for an address of an existing user outside the institution is the same as for a new address.
   - The form with an invalid row or a duplicate email does nothing and keeps every entered value. A form over the rate limit does nothing. A submission for a class of a Read-access or unlinked institution is refused.
   - The invitation is refused if, before acceptance, the inviter is removed, unlinked from the institution or lowered to Read access, or the class is deactivated or deleted.
   - Before acceptance, no table contains the invited email, names or details, and an existing student's data is unchanged.
   - A teacher sees only the classes and students of their own institutions and gets "access denied" for others by address. For a student who moved, a teacher of the new institution sees nothing about the old one. With Read access, a teacher sees the students but gets "access denied" when editing or removing them.
   - Removing a student deletes the enrolment, keeps the consent record and removes the student role; a person left with no role is deactivated.
   - **Leave this institution** deletes the enrolment and removes the student role. The full withdrawal deletes the enrolment.
   - A teacher invited as a student holds both roles.
   - Logs captured during all of the above contain no email, name or token.
   - The milestone 8 tests pass unchanged.

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
