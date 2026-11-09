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

12. **Competitions (12.x).** A group of milestones, not a milestone of its own: it has no spec and no test. Together the 12.x milestones build the teacher's side of competitions: creating, editing and cancelling them, choosing their questions and teams, entering the teams' answers, grading the answers by hand, and stopping them. Taking a competition (milestone 13), answer evaluation by an LLM (milestone 14) and results (milestone 15) come after.

12.3. **Entering a team's answers (teacher).** While a competition is **In progress**, a teacher enters the answers of the teams of the educational institutions they have **Write** access to, one text answer per question per team, and a teacher with **Read** access follows the answer progress of their institutions' teams. Answers belong to a team: a student has no answers of their own. The answers are saved for grading by hand, which comes in a later 12.x milestone; evaluation by an LLM comes in milestone 14.
    _Who:_ every teacher, with or without **Can manage competitions**, for the teams of every available educational institution (an active institution in an active region) they are linked to (milestone 8). With **Write** access the teacher sees each team's answer progress and enters its answers. With **Read** access the teacher sees each team's answer progress on the team answers page, but cannot open the team's answers, so never sees or changes the answers themselves. When a teacher is unlinked from an institution, its teams disappear from their team answers page at once; when their access is lowered to **Read**, its teams lose **Enter answers** at once. In both cases every page and action for those teams' answers gets "access denied"; the answers already saved stay.
    _Row actions:_ the actions menu of milestones 12.1 and 12.2 gains the entry **Answers**, offered only on an **In progress** competition, to every teacher. The menu lists, in this order, **Edit**, **Questions**, **Teams**, **Answers** and **Cancel competition**, each one where it is available. **Upcoming**, **Finished** and **Cancelled** competitions do not offer it.
    _Teams page (unchanged from milestone 12.2):_ every teacher opens a competition's **Teams** page and sees all its teams, from every institution. For a teacher without **Can manage competitions** it is read-only: no **Add team** and no **Remove**. The **Teams** page has no **Enter answers** button for anyone; teams' answers are entered only from the team answers page.
    _Team answers of a competition:_ **Answers** opens the page "Answers of “Spring round”". Under the heading it shows the competition's subject, its start in the teacher's time zone and its status badge, and it has a back link to the competitions list the teacher came from (same subject, status and page), as the pages of milestone 12.2.
    - The page looks and behaves like the **Teams** page of milestone 12.2, with the same layout, order, page navigation and phone layout, but it lists only the competition's teams whose institution the teacher is linked to, with **Read** or **Write** access. Teams of other institutions are not shown at all, not even greyed out. Teams of a deactivated institution or region are not listed either.
    - As on the Teams page, the teams are grouped in region boxes. The regions are sorted by name ignoring case, and the teams inside a region are sorted by name ignoring case. There are 10 teams per page with the page navigation ("Teams 1–10 of 12"), and a region whose teams continue on the next page shows its header again. The region header shows the region's name as it is stored and how many teams of that region the page lists across all its pages, counting only the listed teams ("Kyiv · 3 teams", "Kyiv · 1 team").
    - Each row shows the team's name, the team's educational institution and the number of the team's own active members (milestone 11.1), not of the institution, as on the Teams page, then the team's answer progress in an **Answered** column, and, in the actions cell, an **Enter answers** button for a team of an institution the teacher has **Write** access to, or the row note "Read access" (no button, UI guidelines) for a team of an institution the teacher has only **Read** access to. The progress is plain text, not part of the button's label (buttons are verbs, UI guidelines), so it is read as a column and on a phone as a labelled line of the card.
    - The progress reads "3 of 6": the number of the competition's questions that have a saved non-empty answer of the team, of the number of questions in the competition. A team with no answers reads "0 of 6", and a competition with no questions reads "0 of 0". The progress is counted when the page is shown and is not stored.
    - The page has no **Add team** and no **Remove**, also for a teacher with **Can manage competitions**.
    - Empty states, the first that applies: a teacher linked to no available institution sees "You are not linked to any educational institution" (as on the **Teams** tab, milestone 11.1); otherwise, when no team of their institutions is in the competition, "No teams from your educational institutions".
    _Entering answers:_ **Enter answers** opens the page "Answers of “Comets” in “Spring round”", with the team's institution under the heading and a back link to the team answers page at the page the teacher came from, at that team.
    - It shows every question of the competition on one page, in the competition's order (milestone 12.2), numbered 1, 2, 3, …, each with its copied text and an answer field below it, labelled "Answer to question 3". The reference answer is never shown. A question deleted from the question bank is shown like any other.
    - A question with no saved answer shows an empty field with the placeholder "Not answered". A saved answer is shown in its field and can be changed or emptied.
    - One **Save answers** button below the questions saves all the answers at once. An empty field means the question is not answered. Answers are trimmed, keep their line breaks and are limited to 2,000 characters, as in the question bank (milestone 11), with the error wording of milestone 11. If any answer is too long, nothing is saved and the page shows again with every entered text kept, the error at that answer and the error summary linking to it. After a save the teacher stays on the page with the notice "Answers of “Comets” were saved".
    - A competition with no questions shows "No questions in this competition" and no **Save answers** button.
    - Who saved an answer, or when, is not stored. A team's answers are not personal data, and no special logging rule applies to them.
    _New patterns:_ two, each added to the component library, the component gallery (`/admin/components`) and the UI guidelines before any page uses it:
    - the **answer sheet**: a numbered list of questions, each a text card with its answer field (`textarea_field`) under it, one error per answer, and one primary save button below the list, with labelled answers and the phone layout of the guidelines;
    - the **placeholder** of an empty field: it only says that the field is empty ("Not answered") and never replaces the field's label or hint; the UI guidelines gain this rule in their wording patterns.
    _Several teachers on one team:_ a team's answers are not reserved for a teacher. Usually one teacher is linked to an institution, so two teachers rarely enter the answers of the same team. When they do, each **Save answers** stores every answer of its page, and the last save wins: it replaces the answers an earlier save stored, emptied ones included, with no warning and no refusal.
    _Checks and refusals:_ every page and action checks everything again when it is opened or sent, whatever the page showed, from the top of the hierarchy down, with the access to the team last; the first failing check decides the answer:
    1. the role: anyone who is not a teacher gets "access denied", before any id is read;
    2. the subject and the competition: an unknown subject or competition, a competition of another subject, or a competition of a deactivated subject shows "not found", as in milestone 12.2;
    3. the status: a competition that is not **In progress** shows a refusal in the 12.1 pattern, "Enter answers for “Spring round”?", with the reason for its status, "“Spring round” has not started yet, so its answers cannot be entered yet." (**Upcoming**), "“Spring round” has been cancelled, so its answers can no longer be entered." (**Cancelled**) or "“Spring round” has finished, so its answers can no longer be entered." (**Finished**), and the link **Back to competitions** to the competitions list the teacher came from, at the competition (as the 12.1 edit refusal). A save sent then changes nothing;
    4. the team and the questions: an unknown or deleted team, a team that is not in the competition, or a team of a deactivated institution or region shows "not found"; so does a save that names a question that is not one of the competition's, and then nothing is saved;
    5. the access to the team: a team of an institution the teacher is not linked to gets "access denied" on the team's answers page and its save; a team of an institution the teacher has only **Read** access to gets "access denied" there too, because **Read** access shows only the progress on the team answers page.
    - Every save is a form submission that passes the existing cross-site request check; opening a page never changes anything, and reloading a page after a save never repeats it.
    _Deleting a team:_ deleting a team (milestone 11.1) takes it out of every competition that is not **Finished** (milestone 12.2) and deletes its answers in those competitions. A teacher who has its answers page open gets "not found" on the next save. A **Finished** competition keeps the deleted team and its answers.
    _Test:_
    1. Menu: **Answers** is offered on an **In progress** competition to teachers with and without **Can manage competitions**, in the order **Edit**, **Questions**, **Teams**, **Answers**, **Cancel competition** where each is available, and never on an **Upcoming**, **Finished** or **Cancelled** one.
    2. Teams page: a teacher without the setting opens it and sees every team of the competition, from every institution, with no **Add team**, no **Remove** and no **Enter answers**; a teacher with the setting sees **Add team** and **Remove** on an **Upcoming** competition and no **Enter answers** in any status.
    3. Listing: a teacher with **Write** access to one institution and **Read** access to another sees the teams of both, with their progress, **Enter answers** on the first one's teams and the row note "Read access" on the other's; a teacher with only **Read** access sees their institutions' teams with their progress and no **Enter answers**; teams of unlinked institutions and of a deactivated institution or region are not listed; lowering a link to **Read** replaces **Enter answers** with "Read access" on the next page load; with 12 listed teams in two regions there are 10 per page, the region spanning the page break shows its header again, and each header counts only the listed teams.
    4. Empty states: "You are not linked to any educational institution" for a teacher with no available link, and "No teams from your educational institutions" for a teacher with **Read** or **Write** access whose teams are not in the competition.
    5. Progress: "0 of 6" before any save, "3 of 6" after saving three answers, "2 of 6" after one is emptied, and "0 of 0" for a competition with no questions.
    6. Answer sheet: every question in the competition's order, numbered from 1, with its copied text (also after the bank question is edited or deleted), "Not answered" on unanswered questions, saved answers in their fields, and no reference answer anywhere on the page.
    7. Saving: one **Save answers** stores, changes and empties answers at once; answers are trimmed and keep their line breaks; the teacher stays on the page with the notice; reloading does not save again.
    8. Too long: an answer of 2,001 characters after trimming saves nothing, keeps every entered text and shows the error at that answer and in the error summary; exactly 2,000 characters is saved.
    9. No questions: "No questions in this competition" and no **Save answers**.
    10. Two teachers: when both save the same team, the later save replaces every answer of the earlier one, emptied ones included.
    11. Refusals: opening either page or sending a save on an **Upcoming** competition (typed address), on one cancelled while the page was open and on a **Finished** one (stored directly by the test) shows the refusal with the reason for its status and **Back to competitions**, and saves nothing; when the start passes, the **Upcoming** refusal turns into the page.
    12. Not found: unknown subject or competition, a competition of another subject or of a deactivated subject, an unknown or deleted team, a team not in the competition, a team of a deactivated institution or region, and a save naming a question of another competition; nothing is saved.
    13. Access denied: administrators and students on every page and save, before any id is read; a teacher not linked to the team's institution, and one with **Read** access to it, on the team's answers page (typed address) and on a save; a teacher unlinked or lowered to **Read** while the page is open gets "access denied" on the save, and the answers saved before stay.
    14. Check order: a cancelled competition with a team of an unlinked institution shows the refusal; a deleted team of a **Read**-access institution shows "not found"; a non-teacher sending unknown ids gets "access denied".
    15. Deleting a team: its answers are deleted in an **In progress** and a **Cancelled** competition, a **Finished** competition keeps the team and its answers, and a save from a page opened before the deletion gets "not found".
    16. Cross-site request: a save without a valid token is refused and saves nothing.
    17. Gallery: the answer sheet (with an error and at phone width) and the "Not answered" placeholder are shown at `/admin/components`.

13. **Taking a competition (student).** List of the competitions the student's teams take part in; a competition's questions open and its answers are accepted only while it is **In progress**, from its start until a teacher stops it, since a competition has no duration; the students of a team enter the team's text answers, one per question per team. These are the same answers a teacher enters in milestone 12.3: a student has no answers of their own, every member of the team sees the team's answers, and the last save wins. The student's lists of upcoming and past competitions show each competition's subject. A competition of a deactivated subject that is not finished is hidden from students and cannot be opened.
    _Test:_ a team's answers are saved and shown to every member of the team and to a teacher with Write access to its institution; the competition is not accessible before its start, after it is stopped or cancelled, or while its subject is deactivated.

14. **Answer evaluation via LLM.** Each team's answer receives a score of 1–10 that takes level of detail into account; results are saved to the database. How this score relates to the manual grade of the 12.x milestones is decided before this milestone.
    _Test:_ evaluation returns a structured result and it is persisted.

15. **Best answer selection + results.** For each question, the best answer is selected from the teams' answers; each team's total score and place are saved and displayed. The winner is the team with the highest total score.
    _Kept for the record:_ a completed competition keeps showing every one of its questions and its subject, even after the question was deleted from the question bank or the subject was deactivated (milestone 11), and every one of its teams with its answers, even after the team was deleted (milestone 11.1).
    _Who sees results:_ a teacher sees the results of the teams of their own institutions, with Read or Write access (milestone 8). Results of teams from other institutions are not shown to them. A student sees the results of their own teams.
    _Test:_ the best answer is determined, the results page works. The results still show a question deleted after the competition, a subject deactivated after it and a team deleted after it. A teacher with Read access sees the results of that institution's teams and none from institutions they are not linked to.

16. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)