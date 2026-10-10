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

8. **User management with consent: teachers.** Administrators keep the list of educational institutions and invite teachers. No personal data about a person is stored until that person agrees to it. This milestone builds the invitation and consent flow, and milestone 9 reuses it for students. The teacher and student lists from milestone 5 are retired. Administrators stay in `ADMIN_EMAILS`.
   _Personal data and consent:_ a person's email, first name and last name are personal data. The application stores them only after the person agrees, on a page of this site, to a consent text. The text says what is stored, why, who can see it and how to withdraw consent. The form an inviter fills in is not saved anywhere. Its contents travel only inside the invitation link, and until the person accepts, nothing about them exists in the database.
   _Built for reuse:_ the invitation, the acceptance, the consent record, the profile and the withdrawal are written once and do not depend on a particular role. Each role that can be invited supplies:
   - the fields of its invitation form and their validation
   - which role may invite it
   - its extra checks at acceptance
   - the details stored on acceptance and erased on withdrawal
   - its consent text

   This milestone defines the teacher role. Milestone 9 adds the student role the same way, without changing the flow.
   _Educational institutions:_ administrators keep the regions and institutions created in milestone 7. Institution names are unique only within a region, so every institution picker shows each one as "Name (Region)". Each teacher is linked to one or more institutions. Only an administrator sets these links, when inviting the teacher and later from the teacher's page. On both forms the administrator selects the institutions from the list, at least one. The list offers only active institutions in active regions. There is no free-text entry, so an institution is added to the list before a teacher can be linked to it. The server accepts only institutions that exist, are active and are in an active region. A teacher link is a use of the institution, so an institution linked to a teacher cannot be deleted.
   _Inviting a teacher:_
   - An administrator fills in the email, first name and last name, and selects one or more institutions.
   - Submitting the form sends the invitation email and shows "Invitation sent to …". Nothing from the form is kept, and there is no list of pending invitations. To resend, the inviter fills in the form again. Every invitation sent is valid on its own until it expires.
   - Validation: the email is checked as at sign-in. Names are 1–100 characters after trimming, with no control characters.
   - Invitations are rate-limited per inviter and per invited address, using the existing rate-limit counters.

   _The invitation link:_ the link carries one opaque token, and the token is the whole invitation. It holds:
   - the role
   - the person's details
   - the institutions, by id, so renaming an institution before acceptance does not break the invitation
   - the inviter's user id
   - the time of issue
   - a purpose label

   The token is encrypted and authenticated (for example Fernet or AES-GCM) with a key derived from `SECRET_KEY` for invitations only. So the personal data cannot be read from the URL, wherever the URL ends up: server request logs, browser history, mail scanners. Any change to the token makes it invalid. A token is valid for 7 days from issue. Rotating `SECRET_KEY` invalidates every invitation not yet accepted, and inviters then send new ones.
   _The invitation email:_ plain text, sent through the existing email sender. Its content:
   - who sent the invitation
   - the role and the institutions it is for
   - that nothing is stored unless the person accepts
   - the link, and when it expires

   Click tracking stays off in Resend, because it would store the link. The application keeps no copy of the email: no BCC and no archive mailbox.
   _Accepting:_
   - Opening the link (GET) changes nothing. Mail security scanners open links automatically, so only the person's own button press may create anything. The page shows:
     - the data that will be stored, with the current names of the institutions
     - the consent text
     - the inviter and the role
     - an **I agree** button
   - Nothing can be changed on that page: the data stored is exactly the data in the token. Under the button, the page says that if any detail is wrong, the person can either ask the inviter for a corrected invitation, or accept and ask the inviter to correct it afterwards. Letting the person edit their own name would let them take on someone else's name.
   - **I agree** submits a POST with the token in a hidden field, under the existing cross-site check. The server checks the token again. Then it checks that the inviter is still active and still holds the role that allows the invitation (for a teacher, administrator), and runs the invited role's own checks.
   - What happens next depends on whether the email already belongs to a user:
     - No user has the email: an active user is created with the names, role and details.
     - An active user without this role: the role and details are added, and their names stay unchanged. Example: an administrator invited as a teacher.
     - An active user who already holds the role: nothing changes, and the page says so. A second press of the button ends here too.
     - An inactive user deactivated *after* the invitation was issued: refused. A removal always wins over an older invitation.
     - An inactive user deactivated *before* the invitation was issued: reactivated with the role and details from the invitation.
   - Every acceptance that changes something stores a consent record:
     - the user
     - the role granted
     - the consent text version
     - when it was accepted
     - the inviter
     - when the invitation was issued

     This record, not any email, is the proof of consent.
   - After accepting, the person lands on the sign-in page with their email filled in and signs in with a code as usual. Accepting never signs anyone in.
   - An expired link shows "This invitation has expired; ask for a new one." Any other failure shows one neutral message without saying which check failed: a tampered or unreadable token, an inviter who no longer qualifies, or a refused acceptance.
   - The two invitation routes are added to the public allowlist. They act on the person named in the token, never on the signed-in session.

   _Consent text:_ each invitable role has its own versioned template in the repository, because each role stores different data. Any change to its wording is a new version, and each existing record keeps the version that was accepted. Placeholder wording is fine until real users arrive. The product owner supplies the final wording before then.
   _Managing teachers:_ on the **Teachers** tab from milestone 6, which now lists invited teachers instead of `TEACHER_EMAILS`.
   - An administrator can:
     - see all teachers: name, email, institutions, date of consent
     - edit a teacher's names and institutions, selecting the institutions from the list, at least one
     - remove a teacher
   - An email cannot be edited. To change one, remove the person and invite the new address.
   - Removing a person takes away that role and its details. A person left with no roles is deactivated. As in milestone 5, they are logged out everywhere. Users are never hard-deleted.

   _Profile:_ every signed-in person can open their own profile. It shows the personal data stored about them, their roles, and their consent records with the text of each accepted version. The profile is read-only. Corrections go through an administrator.
   _Withdrawing consent:_ a person holding a role granted by consent sees **Withdraw consent** on the profile, with a confirmation step. Withdrawing:
   - removes the roles granted by consent (in this milestone, teacher)
   - clears the names
   - deletes the role's details (for a teacher, the institution links)
   - replaces the email with an anonymous placeholder, so later records such as competition results can still refer to the user row without identifying anyone
   - keeps only the dates and versions in the consent records
   - logs the person out everywhere

   An administrator from `ADMIN_EMAILS` keeps that role and that address, because that role comes from deployment configuration, not from consent. A person who withdrew can be invited again like anyone new.
   _Retiring the role lists:_ `TEACHER_EMAILS` and `STUDENT_EMAILS` are removed from the configuration and from `render.yaml`. The startup reconcile manages only the administrator role. It removes that role from addresses no longer listed, and deactivates a user only when no role is left. The migration deletes the teacher and student roles granted by the old lists. Until milestone 9, nobody holds the student role.
   _Access:_ each new page states its roles, as milestone 5 requires:
   - institutions and teacher management: administrators
   - profile: every role
   - the invitation pages: public

   _Privacy:_ no log line contains an email, a name or a decrypted token. The console email backend remains the only code path that prints a message body.
   _Out of scope:_
   - anything about students: inviting, managing, their details and consent text (milestone 9)
   - a list of pending invitations, or cancelling one. Known limitation: an invitation sent by mistake stays valid for 7 days. If the person accepts, remove them.
   - changing a person's email
   - self sign-up

   _Test:_
   - End to end: an administrator adds two institutions and invites a teacher with both selected, and the link is read from the `memory` outbox. The GET creates nothing. The POST creates the user with the role, both institutions and a consent record. The teacher then signs in and sees their profile.
   - The invitation and teacher edit forms offer only active institutions in active regions. A submission with no institution, an unknown institution id, a deactivated institution or an institution in a deactivated region is refused.
   - An institution linked to a teacher cannot be deleted.
   - An institution renamed between invitation and acceptance is still linked, and the acceptance page shows its new name.
   - Before acceptance, no table contains the invited email or names.
   - A tampered token, an expired token and a token with the wrong purpose label are each refused. The POST stores only what the token holds: any extra or changed form field is ignored.
   - The invitation is refused if the inviter loses the administrator role before acceptance.
   - A person removed after an invitation was issued cannot be brought back by it. A newer invitation can bring them back.
   - An administrator invited as a teacher gains the teacher role and keeps the administrator role.
   - Withdrawing consent erases the personal data and logs the person out, and that person can no longer sign in. An administrator who withdraws keeps the administrator role and address.
   - Logs captured during all of the above contain no email, name or token.
   - The reconcile manages only the administrator role.

9. **User management with consent: students.** Teachers invite students. The student role is added to the invitation and consent flow from milestone 8 as one more invitable role, so the flow itself does not change.
   _Personal data:_ besides the email and names, a student's educational institution, group code and year of study are personal data. They are stored only on acceptance, like the rest.
   _Inviting a student:_
   - A teacher fills in the email, first name, last name, group code and year of study, and selects one of their own institutions from a list. The server accepts only an institution the teacher is linked to.
   - Validation: the email and names as in milestone 8. The group code is 1–20 characters. The year of study is a whole number from 1 to 12.
   - Sending, rate limits, the token, the email and the acceptance page work as in milestone 8. The token holds the institution id, the group code and the year of study.

   _Accepting:_ on top of the checks in milestone 8, the inviter must still be a teacher linked to the student's institution. The cases for an email that already belongs to a user apply unchanged. Example: a teacher invited as a student gains the student role and keeps the teacher role.
   _Consent text:_ a student consent text, versioned like the teacher one. It also says that the institution, group code and year of study are stored, and that the teachers of that institution can see them. Placeholder wording is fine until real users arrive, as in milestone 8.
   _Managing students:_
   - A teacher can see the students of their own institutions: name, email, institution, group, year. They can edit a student's names, institution (selected among their own), group and year, and remove a student. Students of other institutions are neither listed nor reachable: opening one by address shows "access denied".
   - An administrator can see all students and remove any of them.
   - An email cannot be edited, and removing works as in milestone 8.

   _Profile and withdrawing consent:_ the profile also shows the student details. Withdrawing also removes the student role and deletes the student details. Corrections to a student's data go through a teacher of their institution.
   _Access:_ student management: teachers (own institutions only) and administrators.
   _Out of scope:_
   - bulk import of students
   - administrators inviting students
   - parental consent for minors

   _Test:_
   - End to end: a teacher invites a student, and the link is read from the `memory` outbox. The GET creates nothing. The POST creates the user with the student role, the details and a consent record. The student then signs in.
   - The invitation form offers only the teacher's own institutions. A submission with another institution is refused.
   - The invitation is refused if, before acceptance, the inviter is removed or unlinked from the institution.
   - Before acceptance, no table contains the invited email, names or details.
   - A teacher sees and edits only the students of their own institutions, and gets "access denied" for the others. An administrator sees all students and can remove any of them.
   - Withdrawing consent as a student erases the student details too.
   - A teacher invited as a student holds both roles.
   - Logs captured during all of the above contain no email, name or token.
   - The milestone 8 tests pass unchanged.

10. **Question bank (teacher).** Uploading a list of questions, viewing, editing, reference answers for questions.
    _Subjects:_ every question belongs to exactly one subject. The teacher selects it from the list kept on the **Subjects** tab (milestone 6), with no free-text entry, and the server accepts only a subject that exists. Teachers can filter the question bank by subject. The sample questions seeded in milestone 3 have no subject, and the migration deletes them, since no real data exists yet.
    _Test:_ question CRUD works and is visible only to teachers. A question without a subject or with an unknown subject is refused. Filtering by subject shows only that subject's questions.

11. **Creating a competition (teacher).** A competition with a subject, a start time, duration, assignment to a group/students, a set of questions from the bank and reference answers.
    _Subjects:_ the teacher selects the competition's subject first, from the list kept on the **Subjects** tab. The question picker then offers only questions of that subject, and the server refuses a competition that includes a question of another subject. Changing the subject of an upcoming competition is refused while it still holds questions of the old subject.
    _Test:_ a competition is created and correctly linked to its subject, questions and participants. A competition with a question from another subject is refused.

12. **Taking a competition (student).** List of assigned competitions, enforcement of the time window and duration, entering and submitting text answers. The student's lists of upcoming and past competitions show each competition's subject.
    _Test:_ answers are saved; the competition is not accessible outside its time window.

13. **Answer evaluation via LLM.** Each answer receives a score of 1–10 that takes level of detail into account; results are saved to the database.
    _Test:_ evaluation returns a structured result and it is persisted.

14. **Best answer selection + results.** For each question, the best answer is selected from the group's answers; competition results are saved and displayed.
    _Test:_ the best answer is determined, the results page works.

15. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)
