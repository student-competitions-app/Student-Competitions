# Milestones

The milestone ladder for the product described in [product-requirements.md](product-requirements.md), built with the stack in [technical-requirements.md](technical-requirements.md). Each milestone is delivered as one Spec Kit feature.

The ladder follows a "walking skeleton" approach: first ship an empty skeleton to the internet, then grow it with vertical slices. Each step ends with a working, testable and meaningful result.

**Delivered milestones** are short summaries of what the product does after them. Their specification in [`specs/`](../../specs/) is the source of truth for details, and the summary is updated only if the product behaviour changes. **Upcoming milestones** hold the full scope, refined until every detail is clear, and are the input for `speckit-specify`.

## Delivered

1. **Hello World locally.** _Spec:_ [001-hello-world-page](../../specs/001-hello-world-page/spec.md)
   - A server-rendered home page that runs on a developer's machine, with a README for setup, running and testing.

2. **Deploy Hello World to the internet + CI/CD.** _Spec:_ [002-public-deploy-cicd](../../specs/002-public-deploy-cicd/spec.md)
   - The application is public over HTTPS. Pull requests are gated by tests and style checks, every merge to `main` is deployed automatically, and a status address reports health and version.

3. **Database + first entity.** _Spec:_ [003-database-questions](../../specs/003-database-questions/spec.md)
   - A persistent database with the first entity, the question (text and reference answer). The home page shows a database status line and stays up when the database is unreachable.

4. **Email code authentication.** _Spec:_ [004-email-otp-auth](../../specs/004-email-otp-auth/spec.md)
   - Passwordless sign-in with a one-time emailed code, only for users already known to the application, with rate limits, no account enumeration and 14-day sessions. Every page except sign-in, status and static files requires sign-in.

5. **Roles and authorization.** _Spec:_ [005-roles-authorization](../../specs/005-roles-authorization/spec.md)
   - Administrator, teacher and student roles. A person with several roles chooses one and can switch from the header; access follows the current role only and is denied by default.

6. **Administrator area and subjects.** _Spec:_ [006-admin-area](../../specs/006-admin-area/spec.md)
   - A tabbed administrator area. Administrators create, rename, deactivate, activate and delete (while unused) subjects.

7. **Administrator area: educational institutions.** _Spec:_ [007-region-and-institutions-management](../../specs/007-region-and-institutions-management/spec.md)
   - Administrators manage regions and the educational institutions in them with the same actions as subjects. Only an active institution in an active region can be selected.

8. **User management with consent: teachers.** _Spec:_ [008-teacher-management-consent](../../specs/008-teacher-management-consent/spec.md)
   - Administrators invite teachers by email; nothing is stored until the teacher accepts the versioned consent text. Teachers are linked to institutions with **Read** or **Write** access and have a competition-management setting. Every user has a profile with **Withdraw consent**, and **Delete my data** works without signing in.

9. **User management with consent: classes and students.** _Spec:_ [009-classes-students-management](../../specs/009-classes-students-management/spec.md)
   - A teacher area with a **Students** tab. Teachers with Write access manage classes and invite, edit, move and remove students through the same consent flow; Read access is view-only. Deactivating a region, institution or class blocks the students below it.

10. **Professional design system and UI guidelines.** _Spec:_ [010-design-system-ui-guidelines](../../specs/010-design-system-ui-guidelines/spec.md)
    - A visual identity, one shared page frame, a component library used by every page, and **Light** / **Dark** / **Device** themes. The binding UI guidelines are in [ui-guidelines.md](ui-guidelines.md), with a component gallery at `/admin/components` and an automated check.

10.1. **Feedback while a page loads, and a frame that stays in view.** _Spec:_ [010.1-loading-feedback-pinned-frame](../../specs/010.1-loading-feedback-pinned-frame/spec.md)
   - A loading bar for slow navigations, a busy state on the button that sent a form, and a top bar and area tabs pinned on tall screens. Everything works without JavaScript.

11. **Question bank (teacher).** _Spec:_ [011-question-bank](../../specs/011-question-bank/spec.md)
    - A **Questions** tab where every teacher browses the shared question bank by subject, paginated. Teachers with **Can manage competitions** add, edit and soft-delete questions.

11.1. **Teams (teacher).** _Spec:_ [011.1-teacher-teams](../../specs/011.1-teacher-teams/spec.md)
   - A **Teams** tab. Teachers with Write access create, rename and soft-delete teams of an institution and add and remove its students as members. Memberships are personal data, shown on the profile and erased with the student's data.

12.1. **Creating, editing and cancelling competitions (teacher).** _Spec:_ [012.1-teacher-competitions](../../specs/012.1-teacher-competitions/spec.md)
   - A **Competitions** tab listing competitions by subject and status, paginated. Teachers with **Can manage competitions** add competitions, edit upcoming ones and cancel upcoming or in-progress ones. The status (**Upcoming**, **In progress**, **Finished**, **Cancelled**) is derived; times are stored in UTC and shown in the browser's time zone.

12.2. **Questions and teams of a competition (teacher).** _Spec:_ [012.2-competition-questions-teams](../../specs/012.2-competition-questions-teams/spec.md)
   - Every competition row has an actions menu with **Questions** and **Teams**, which every teacher reads. Teachers with **Can manage competitions** add questions (copied from the bank when added) and teams of any institution, one region at a time, to an **Upcoming** competition, and remove them. Teams are listed in region boxes. Deleting a team takes it out of every competition that has not finished.

## Upcoming

12. **Competitions (12.x).** A group of milestones, not a milestone of its own: it has no spec and no test. Together the 12.x milestones build the teacher's side of competitions: creating, editing and cancelling them, choosing their questions and teams, and stopping them. Taking a competition (milestone 13), answer evaluation (milestone 14) and results (milestone 15) come after.

13. **Taking a competition (student).** List of the competitions the student's teams take part in; a competition's questions open and its answers are accepted only while it is **In progress**, from its start until a teacher stops it, since a competition has no duration; entering and submitting text answers. The student's lists of upcoming and past competitions show each competition's subject. A competition of a deactivated subject that is not finished is hidden from students and cannot be opened.
    _Test:_ answers are saved; the competition is not accessible before its start, after it is stopped or cancelled, or while its subject is deactivated.

14. **Answer evaluation via LLM.** Each answer receives a score of 1–10 that takes level of detail into account; results are saved to the database.
    _Test:_ evaluation returns a structured result and it is persisted.

15. **Best answer selection + results.** For each question, the best answer is selected from the group's answers; competition results are saved and displayed.
    _Kept for the record:_ a completed competition keeps showing every one of its questions and its subject, even after the question was deleted from the question bank or the subject was deactivated (milestone 11), and every one of its teams, even after the team was deleted (milestone 11.1).
    _Who sees results:_ a teacher sees the results of the students of their own institutions, with Read or Write access (milestone 8). Results of students from other institutions are not shown to them.
    _Test:_ the best answer is determined, the results page works. The results still show a question deleted after the competition, a subject deactivated after it and a team deleted after it. A teacher with Read access sees the results of that institution's students and none from institutions they are not linked to.

16. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)
