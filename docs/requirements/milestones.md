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

## Upcoming

8. **User management with consent: teachers.** Administrators invite and manage teachers. No personal data about a person is stored until that person agrees to it. Milestone 9 reuses this flow for students. The teacher and student lists from milestone 5 are retired; administrators stay in `ADMIN_EMAILS`.
   _Personal data and consent:_ a person's email, first name and last name are personal data. They are stored only after the person agrees to a consent text on this site. Until then, the invitation exists only inside the emailed link. The only exception is a keyed one-way hash of an email address, which cannot be turned back into the address and is kept only for rate limits and to stop outdated invitations (see _Accepting_).
   _Built for reuse:_ the invitation, acceptance, consent record, profile and withdrawal work the same for every invitable role. Each role defines its invitation form and validation, who may invite it and for which institutions, its extra checks at acceptance, the details stored on acceptance and its consent text. This milestone defines the teacher role; milestone 9 adds students without changing the flow.
   _Teacher details:_
   - Each teacher is linked to one or more educational institutions (milestone 7). Each link has an access level: **Read** lets the teacher see the institution's students and their results; **Write** also lets them invite, edit and remove those students. A new link starts at Read.
   - Each teacher has one **Can create competitions** setting covering all their institutions, unchecked by default.
   - Only an administrator sets these, when inviting and from the teacher's page. Institutions are picked from a list, at least one, each shown as "Name (Region)". The list offers only active institutions in active regions, and the server accepts nothing else. A link to an institution deactivated later is kept and shown as deactivated; it can be removed but not added again.
   - An institution linked to a teacher cannot be deleted. In this milestone, access levels and the setting are only stored and shown; milestones 9, 11 and 14 enforce them.

   _Inviting a teacher:_
   - An administrator enters the email, first name and last name, picks institutions with access levels and sets **Can create competitions**. The email is validated as at sign-in. Names are 1–100 characters after trimming, with no control characters.
   - Submitting sends the invitation email and shows "Invitation sent to …". If sending fails, the form shows an error with the entered values. Nothing from the form is kept and there is no list of pending invitations. Each invitation is valid on its own for 7 days; to resend, the administrator fills in the form again.
   - Invitations are rate-limited per inviter and per invited address.
   - The link carries the whole invitation, encrypted and tamper-proof: its contents cannot be read from the URL, and any change makes it invalid.
   - The email is plain text: who invites, the role, the institutions with access levels, whether it includes creating competitions, that nothing is stored unless the person accepts, the link and its expiry. Links are not click-tracked, and the application keeps no copy of the email.
   - An administrator who also works as a teacher invites their own address and goes through the same steps.

   _Accepting:_
   - Opening the link changes nothing, because mail scanners open links automatically. The page shows the inviter, the role, exactly the data that will be stored (institutions by their current names), the consent text and an **I agree** button. Nothing can be edited there. Under the button, the page says that a wrong detail is fixed by asking the inviter for a new invitation, or by accepting and asking the inviter to correct it.
   - **I agree** is refused if:
     - the inviter is no longer an active administrator
     - any invited institution was deleted or deactivated, or its region was deactivated
     - after the invitation was issued, the person lost the teacher role or withdrew consent, whether or not they are still active. A removal or withdrawal always wins over an older invitation.
   - Otherwise, the names and teacher details from the invitation are stored, and:
     - no user has the email: an active user is created with the teacher role
     - an active user without the teacher role (for example an administrator): gains the role
     - an inactive user: is reactivated with the role
     - a user who already holds the role: nothing changes, and the page says so. A second press ends here too.
   - Every acceptance that changes something stores a consent record: the user, the role, the consent text version, when it was accepted, the inviter and when the invitation was issued. This record is the proof of consent.
   - Accepting never signs anyone in. The person lands on the sign-in page with their email filled in.
   - An expired link shows "This invitation has expired; ask for a new one." Any other failure shows one neutral message that does not say which check failed.
   - The invitation pages act on the person named in the link, never on the signed-in session.

   _Consent text:_ each invitable role has its own versioned consent text: what is stored, why, who can see it, which external service delivers the emails, and how to withdraw. Any wording change is a new version. Earlier versions are kept, and each record keeps the version that was accepted. Placeholder wording is fine until the product owner supplies the final text before real users arrive.
   _Managing teachers:_ the **Teachers** tab (milestone 6) lists current teachers sorted by last name: name, email, institutions with access levels, **Can create competitions** and date of consent. An empty list shows "No teachers yet". Each teacher has a page where an administrator can:
   - edit the names (validated as on the invitation), institutions, access levels and **Can create competitions**
   - remove the teacher, after confirmation. This takes away the teacher role and details. A person left with no roles is deactivated, and the person is logged out everywhere. Their email, names and consent records stay until they delete their data. Users are never hard-deleted.

   An email cannot be edited: remove the teacher and invite the new address.
   _Profile:_ every signed-in person can open their own read-only profile: their personal data, roles, for a teacher the institutions with access levels and **Can create competitions**, and their consent records with each accepted text. Corrections to teacher data go through an administrator.
   _Withdrawing consent:_ anyone whose data was stored on consent and not yet erased, including a removed teacher who is still an administrator, sees **Withdraw consent** on the profile, with a confirmation step. Withdrawing:
   - removes every role granted by consent (here, teacher) and its details
   - erases the names and replaces the email, so the account identifies no one while later records, such as results, can still refer to it
   - keeps the consent records
   - deactivates a person left with no roles, logs the person out everywhere and shows a confirmation page

   An administrator from `ADMIN_EMAILS` keeps that role and address, because they come from deployment configuration, not from consent. A person who withdrew can be invited again with an invitation issued after the withdrawal.
   _Deleting data without signing in:_ the sign-in page has a **Delete my data** link, also for people who can no longer sign in, such as removed teachers.
   - The person enters an email and always sees "If this email is registered, we have sent you a link." Requests are rate-limited per address.
   - The email is sent only if the address has data stored on consent and not yet erased. It says what the link does and when it expires. No copy is kept.
   - The link works once, within one hour. Opening it changes nothing. The page shows the data to be erased, the roles to be removed, for an administrator from `ADMIN_EMAILS` that this role and address stay, and a **Delete my data** button. The button works like **Withdraw consent**, then confirms the deletion.
   - An expired or used link shows "This link has expired; request a new one." Any other failure shows one neutral message.
   - These pages act on the person the link was sent to, never on the signed-in session.

   _Retiring the role lists:_ `TEACHER_EMAILS` and `STUDENT_EMAILS` are removed. `ADMIN_EMAILS` grants and removes only the administrator role, and deactivates a person only when no role is left. Teacher and student roles granted by the old lists are removed; users left with no role are deactivated and their emails replaced as on withdrawal. Until milestone 9, nobody holds the student role.
   _Access:_ teacher management: administrators. Profile: every role. Invitation and data deletion pages: public.
   _Privacy:_ no log line contains an email, a name, or an invitation or deletion link.
   _Out of scope:_ anything about students (milestone 9); a list of pending invitations or cancelling one (known limitation: an invitation sent by mistake stays valid for 7 days; if it is accepted, remove the person); changing a person's email; self sign-up.
   _Test:_
   - End to end: an administrator invites a teacher to two institutions, one Write and one Read, with **Can create competitions** checked. Opening the link from the `memory` outbox creates nothing. **I agree** creates the user with the role, both links, the setting and a consent record. The teacher signs in and sees all of it on the profile.
   - Before acceptance, no table contains the invited email or names.
   - The forms offer only active institutions in active regions. No institution, an unknown or deactivated institution, an institution in a deactivated region, or an access level other than Read or Write is refused. A link to an institution deactivated later survives an edit.
   - Changing one link's access level and the setting leaves the other link unchanged. A linked institution cannot be deleted.
   - An institution renamed before acceptance shows its new name. One deleted or deactivated before acceptance makes the acceptance fail.
   - A tampered or expired link is refused. Exactly what the link holds is stored; extra or changed form fields are ignored.
   - Acceptance is refused if the inviter lost the administrator role.
   - An invitation issued before the teacher role was removed or consent was withdrawn cannot bring it back: for a deactivated teacher, a teacher whose data was deleted, and an administrator who lost the teacher role but stayed active. A newer invitation can.
   - An administrator invites their own address: they gain the teacher role and the invitation's names, keep the administrator role, and are their own inviter. After withdrawing, they keep the administrator role and address and leave the **Teachers** tab.
   - Withdrawing erases the personal data and logs the person out; a person without the administrator role can no longer sign in.
   - A removed teacher can delete their data: from the profile if still an administrator, otherwise through **Delete my data**.
   - Delete my data: known, unknown and already erased addresses get the same answer, and only the known one receives an email. Opening the link changes nothing. The button erases as withdrawing does. A used or an expired link is refused.
   - Logs contain no email, name or link.
   - The reconcile manages only the administrator role.

9. **User management with consent: students.** Teachers invite students to the institutions where they have Write access (milestone 8). The student role is added to the invitation and consent flow from milestone 8 as one more invitable role, so the flow itself does not change.
   _Personal data:_ besides the email and names, a student's educational institution, group code and year of study are personal data. They are stored only on acceptance, like the rest.
   _Inviting a student:_
   - A teacher fills in the email, first name, last name, group code and year of study, and selects one of their own institutions from a list. The list offers only institutions where the teacher has Write access, and the server accepts only such an institution.
   - Validation: the email and names as in milestone 8. The group code is 1–20 characters. The year of study is a whole number from 1 to 12.
   - Sending, rate limits, the token, the email and the acceptance page work as in milestone 8. The token holds the institution id, the group code and the year of study.

   _Accepting:_ on top of the checks in milestone 8, the inviter must still be a teacher with Write access to the student's institution. The cases for an email that already belongs to a user apply unchanged. Example: a teacher invited as a student gains the student role and keeps the teacher role.
   _Consent text:_ a student consent text, versioned like the teacher one. It also says that the institution, group code and year of study are stored, and that the teachers of that institution can see them. Placeholder wording is fine until real users arrive, as in milestone 8.
   _Managing students:_
   - A teacher can see the students of all their own institutions, with Read or Write access: name, email, institution, group, year. Students of other institutions are neither listed nor reachable: opening one by address shows "access denied".
   - For a student of an institution where the teacher has Write access, the teacher can edit the student's names, institution, group and year, and remove the student. A student can be moved only to another institution where the teacher has Write access.
   - Where the teacher has only Read access, the students are shown without edit or remove actions, and the server answers such a request with "access denied".
   - An administrator can see all students and remove any of them.
   - An email cannot be edited, and removing works as in milestone 8.

   _Profile and withdrawing consent:_ the profile also shows the student details. Withdrawing also removes the student role and deletes the student details. Corrections to a student's data go through a teacher with Write access to their institution.
   _Access:_ student management: teachers (seeing students: own institutions; inviting, editing and removing: institutions with Write access) and administrators.
   _Out of scope:_
   - bulk import of students
   - administrators inviting students
   - parental consent for minors

   _Test:_
   - End to end: a teacher invites a student, and the link is read from the `memory` outbox. The GET creates nothing. The POST creates the user with the student role, the details and a consent record. The student then signs in.
   - The invitation form offers only the teacher's institutions with Write access. A submission with a Read-access institution or another teacher's institution is refused.
   - The invitation is refused if, before acceptance, the inviter is removed, unlinked from the institution, or lowered to Read access for it.
   - Before acceptance, no table contains the invited email, names or details.
   - A teacher sees and edits only the students of their own institutions, and gets "access denied" for the others. With Read access to an institution, a teacher sees its students but gets "access denied" when editing or removing them. A teacher cannot move a student to an institution where they have Read access. An administrator sees all students and can remove any of them.
   - Withdrawing consent as a student erases the student details too.
   - A teacher invited as a student holds both roles.
   - Logs captured during all of the above contain no email, name or token.
   - The milestone 8 tests pass unchanged.

10. **Question bank (teacher).** Uploading a list of questions, viewing, editing, reference answers for questions.
    _Subjects:_ every question belongs to exactly one subject. The teacher selects it from the list kept on the **Subjects** tab (milestone 6), with no free-text entry, and the server accepts only a subject that exists. Teachers can filter the question bank by subject. The sample questions seeded in milestone 3 have no subject, and the migration deletes them, since no real data exists yet.
    _Test:_ question CRUD works and is visible only to teachers. A question without a subject or with an unknown subject is refused. Filtering by subject shows only that subject's questions.

11. **Creating a competition (teacher).** A competition with a subject, a start time, duration, assignment to a group/students, a set of questions from the bank and reference answers.
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
