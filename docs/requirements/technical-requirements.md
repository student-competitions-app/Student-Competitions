# Technical Requirements

## Technology Stack

| Area | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-side rendering: Jinja2 + HTMX + Pico.css |
| Database | SQLite locally, PostgreSQL in production, via SQLModel + Alembic |
| Authentication | Email code (OTP) + server-side sessions in a signed cookie |
| Answer evaluation | LLM API call (Claude or OpenAI) with structured output |
| Infrastructure & deployment | Docker + Render (or Railway / Fly.io) |
| Tooling & tests | uv, ruff, pytest, later Playwright |
| Development process | GitHub Spec Kit |

## Milestones

The ladder follows a "walking skeleton" approach: first ship an empty skeleton to the internet, then grow it with vertical slices. Each step ends with a working, testable and meaningful result.

1. **Hello World locally.** FastAPI serves a single HTML page via Jinja2.
   _Test:_ the application starts, the page opens, there is a first pytest test for the endpoint.

2. **Deploy Hello World to the internet + CI/CD.** Dockerfile, deployment to Render, public URL. GitHub Actions runs tests and linting on PRs, auto-deploy on push to `main`.
   _Test:_ the page is accessible from outside, the pipeline is green.

3. **Database + first entity.** Connect the database (SQLite locally, Postgres in production) with Alembic migrations. Create the "Question" model with a CRUD layer covered by tests (no write endpoints, since there is no authentication yet). The public page shows a read-only list of seeded sample questions and a database status line (database type, migration revision, boot count).
   _Test:_ CRUD tests pass on SQLite and Postgres in CI; in production, the sample questions are visible and the boot count increases across a redeploy.

4. **Email code authentication.** Email input form → code sent to email → code verification → session.
   _Email delivery:_ the auth flow sends email through a small email-sender interface and never knows how the message is delivered. The backend is selected by the `EMAIL_BACKEND` environment variable:
   - `console` (local default): prints the full email, including the code, to the server console. No mail provider account or keys are needed for local development.
   - `memory` (tests): keeps sent messages in an in-memory outbox, so tests read the code from it and run the real flow end to end.
   - `resend` (production): the Resend HTTP API, not SMTP, since free hosting tiers may block outbound SMTP. The sending domain is verified with SPF/DKIM records.

   On Render, the application refuses to start with the `console` backend, following the same pattern as `DATABASE_URL`. There are no login bypasses (magic codes, dev-only login URLs). Only the console backend may output the message body. Tests of role-protected pages in later milestones use a fixture that creates a session directly and skip the email step.
   _Site administrators:_ there is no sign-up. Only active users already in the database can log in, and an unknown email receives no code. SRE manages administrators through the `ADMIN_EMAILS` environment variable: a comma-separated list, declared in `render.yaml` with `sync: false`. On startup, after migrations, the application reconciles the users table with this list. Every listed email (trimmed and lowercased) gets an active administrator user. Administrators missing from the list are deactivated and their sessions deleted. The step is idempotent and logs only counts. On Render, the application refuses to start if `ADMIN_EMAILS` is empty or contains a malformed email. The UI cannot grant or revoke administrator rights. This milestone has no role-based checks; milestone 5 adds them on top of this flow.
   _Access:_ every page is protected by default, including the existing home page. Routes are public only if they are on an explicit allowlist: login, logout, `/healthz` and `/static`. An anonymous request to a protected page redirects (303) to `/login?next=…`, and `next` is accepted only as a relative path.
   _UI (minimal):_ a two-step login page (email, then code) using plain forms that redirect after submit, with no HTMX. The header shows the signed-in email and a **Log out** button that submits a POST form. The home page content is unchanged.
   _Sessions:_ stored server-side in a `sessions` table. The cookie carries a random token signed with `SECRET_KEY`, and the database stores only the token's hash. Every request checks that the session is unexpired and the user is still active. Sessions expire after 14 days, and expired sessions and codes are cleaned up.
   _Security:_ codes are hashed with HMAC keyed by `SECRET_KEY`, single-use, and expire after about 20 minutes. Attempts per code and code requests per email are rate-limited, with counters stored in the database. Between the two steps, the email travels in a hidden form field. Known and unknown emails get the same response, and the email is sent in a background task so response timing does not reveal which emails are registered. The session cookie is `HttpOnly`, `SameSite=Lax` (sufficient against CSRF for this milestone), and `Secure` in production.
   _Configuration:_ `SECRET_KEY`, `ADMIN_EMAILS`, `RESEND_API_KEY` and `EMAIL_FROM` are declared in `render.yaml` with `sync: false`. On Render, the application refuses to start if any of them is missing. Startup order: migration check, then admin reconcile, then boot count. The `users` table has a `role` column (only `admin` for now); milestone 5 may change how roles are stored.
   _Rollout:_ the Resend domain's DNS records at NIC.UA and the Render secrets are in place before merging to `main`.
   _Test:_ a user can log in end to end, reading the code from the `memory` outbox. A route-table test asserts that every route outside the allowlist rejects anonymous requests. Existing page tests use a fixture that creates a session directly. Unknown and known emails get the same response. Running the reconcile twice changes nothing. An email removed from `ADMIN_EMAILS` can no longer log in and loses its sessions.

5. **Roles and authorization.** Three roles: student, teacher and administrator. Each page is open only to the roles allowed to see it. The aim is the complete role flow, kept simple: the role pages are placeholders with no features behind them.
   _Who has which role:_ the lists of administrators, teachers and students are all set via configuration at deploy time, the same way administrators are set today. One person can be on several lists and so have several roles. A person on no list cannot log in. Removing a person from a list takes effect at once: they are logged out everywhere. The teacher and student lists are temporary; milestones 8 and 9 replace them with managing teachers and students in the application.
   _Choosing a role:_ a person with one role gets it right after login. A person with several roles chooses one after login, and then lands on the page they originally asked for. Until a role is chosen, no other page opens. A person with several roles can switch role at any time from the header without logging out.
   _Access:_ what a person can open depends on the role they are currently using, not on all the roles they have. For example, someone who is both an administrator and a student cannot open administrator pages while using the student role. Opening a page the current role is not allowed to see shows an "access denied" page. Every new page must state which roles can open it.
   _Pages:_
   - The home page is open to all roles. Its content is unchanged, plus links to only the pages the current role can open.
   - One placeholder page per role (administrator, teacher, student), each open only to that role.
   - One placeholder page for staff, open to administrators and teachers but not to students.
   - Every page shown after a role is chosen displays the current role in the header, next to the application name in the top left corner.

   _Out of scope:_ managing users, educational institutions or profiles in the application, and any real functionality for a role beyond its placeholder page.
   _Test:_
   - Each role can open exactly the pages it is allowed to and sees "access denied" on the others.
   - The home page shows each role only its own links.
   - A person with several roles is asked to choose one after login, and a person with one role is not.
   - Someone who is both an administrator and a student, using the student role, cannot open the administrator page.
   - A person removed from a list is logged out, and a person removed from every list can no longer log in.

6. **Administrator area: teachers, educational institutions, subjects.** The administrator page from milestone 5 stops being a placeholder and becomes a tabbed area with three tabs at the top: **Teachers**, **Educational institutions**, **Subjects**.
   _Tabs:_
   - The tabs are a row of links at the top of every administrator page, below the header. Each tab is its own page with its own address: `/admin/teachers`, `/admin/institutions`, `/admin/subjects`. Clicking a tab is an ordinary link to that page, with no client-side tab switching, so every tab can be bookmarked, reloaded and opened directly.
   - The current tab is highlighted. `/admin` redirects to the **Teachers** tab.
   - The tabs exist only in the administrator area and are not shown to any other role.

   _Teachers tab:_ dummy page at this milestone
   _Educational institutions tab:_ dummy page at this milestone
  
   _Subjects tab:_ the list of subject areas in which competitions are held (for example mathematics, physics). It shows all subjects, sorted by name, and a **Create** button. 
   - **Create** opens a form with one field, the name. The name is 1–200 characters after trimming, with no control characters. Names are unique, ignoring case. A duplicate or invalid name shows the form again with the error and the entered value. An empty list shows "No subjects yet".
   _Access:_ all three tabs and their forms: administrators. Every other role gets "access denied", as in milestone 5.
    - The tab contains the **Rename** and **Delete**,  **Deactivate** buttons. Deletion should check any usage of the subject and deline the operation to avoid broken references. The deactivated status restricts creation on any new questions for the subject and any new competitions (will be covered in future milestones)

   Out of Scope: this milestone does not add any operations an UI ourside of dummy pages for teachers and Educational institutions tabs.
   

7. **Administrator area: educational institutions.** The **Educational institutions** tab from milestone 6 stops being a placeholder and becomes a page with two lists side by side: regions on the left, and the educational institutions of the selected region on the right.
   _Layout:_
   - The selected region is highlighted. With no region selected, the right side shows "Select a region".
   - Both lists are sorted by name and show active and deactivated items. Deactivated items are marked as deactivated.

   _Regions:_ administrators create the regions themselves; there is no preset list.
   - **Create** opens a form with one field, the name. The name is 1–200 characters after trimming, with no control characters. Region names are unique, ignoring case. A duplicate or invalid name shows the form again with the error and the entered value. An empty list shows "No regions yet".
   - **Rename** uses the same form and the same validation as **Create**.
   - **Delete** is refused while the region holds any educational institution, active or deactivated.
   - **Deactivate** blocks creating new educational institutions in the region, and its institutions can no longer be selected anywhere an institution is picked (milestones 8 and 9). **Activate** reverses it. 

   _Educational institutions:_
   - **Create** adds an institution to the selected region. It is unavailable when no region is selected or the selected region is deactivated. It opens a form with one field, the name, validated as for regions. Names are unique within a region, ignoring case; the same name may exist in different regions. An empty list shows "No educational institutions yet".
   - **Rename** uses the same form and the same validation as **Create**. An institution cannot be moved to another region.
   - **Delete** is refused while anything uses the institution. Nothing does in this milestone, so deletion always succeeds; milestone 8 adds teacher links and milestone 9 adds students as uses.
   - **Deactivate** means the institution can no longer be selected when inviting or editing teachers (milestone 8) or students (milestone 9). **Activate** reverses it.

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
