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
   - **Deactivate** keeps the subject but stops offering it for new questions (milestone 11) and new competitions (milestone 12). Questions and competitions that already use it stay valid. **Activate** reverses it.
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

9. **User management with consent: classes and students.** _Spec:_ [009-classes-students-management](../../specs/009-classes-students-management/spec.md)
   - The teacher page is a teacher area like the administrator area, with two tabs: **Students** (opened by `/teacher`) and **Competitions**, a placeholder for milestones 12 and 15.
   - On **Students**, three lists in a row (**Region**, **Educational institution**, **Class**; stacked on narrow screens) choose a class among the available institutions the teacher is linked to, each marked "Read" or "Write". The selection is kept in the page address, and a message says what to choose next.
   - A class belongs to one institution and has a name (unique ignoring case within the institution) and a year of study from 1 to 12. With Write access a teacher creates, edits, deactivates (after a confirmation), activates and deletes classes; a class with a student cannot be deleted.
   - Teachers with Write access invite students one by one into an active class, through the milestone 8 consent flow. Nothing is stored until the student presses **I agree**; only then are the student role and the enrolment (institution and class) stored. An address that already belongs to a student is refused without naming their class, and student invitations are limited to 100 per teacher per hour.
   - A student acceptance is refused when the inviter no longer has Write access to the institution or the class is no longer available, besides the milestone 8 checks. A person who already is a teacher or a student keeps their names when accepting any invitation, teacher invitations included.
   - A class lists its students by last name. **Edit** changes the names or moves the student to another active class of the same institution, with no new consent; **Remove** takes the student role away, signs the student out everywhere and deactivates them if no role is left. Read access shows the same classes and students with no actions, and anything out of reach shows "access denied", also through the page address.
   - Regions, institutions and classes form a chain. Deactivating any of them signs out and hides every student below it until it is activated again, without changing any other status; a blocked student cannot sign in with the student role but can still delete their data. The administrator confirms deactivating a region or an institution.
   - An institution with an enrolled student cannot be deleted; its empty classes are deleted with it. A student's profile shows the institution, the class and the year of study; withdrawal and **Delete my data** erase the enrolment with the rest.

## Upcoming

10. **Professional design system and UI guidelines.** The application looks and works like a professionally designed educational website: calm, readable, consistent and trustworthy for students, teachers and administrators. It gets a visual identity, a library of shared page components and written UI guidelines that follow established practice for educational and public-service websites. Every existing page moves onto them with no change in behaviour, and every later milestone builds its pages from them.
    _Audience:_ students from school to university (years of study 1–12), teachers and administrators. Students mostly use phones and many have no laptop; young readers scan rather than read, skip long instructions, and rely on an in-page back link rather than the browser's. Teachers and administrators mostly work on desktops with lists and forms. Every page works for the youngest student who can take a written competition and stays efficient for staff.
    _Design principles_ (each one explained, with sources, in the guidelines):
    - **Calm and focused.** Content comes first, with no decoration that competes with it. No moving or blinking content; transitions are subtle. No advertising or promotional content.
    - **Clear and consistent.** One navigation per page. The same component looks and behaves the same everywhere and sits in the same place. Every page below an area's main page has a visible back link.
    - **Readable.** Body text at least 16 px on phones and 18 px on desktops, line height at least 1.5, lines no longer than about 70 characters, left-aligned, never justified. Emphasis uses bold, not italics, underlining or capitals. The font is **Open Sans** (open licence, Latin and Cyrillic letters) in regular 400, semibold 600 and bold 700, served from the application itself, never from a third-party font service, with the system font stack as a fallback.
    - **Plain language.** Short sentences and words students know. Buttons are verbs ("Save", "Invite student"). Abbreviations are spelled out. Instructions are a sentence or two, placed where they are needed.
    - **Forgiving.** Every form error is shown next to its field, and also in an error summary at the top of the page (heading "There is a problem", one link per error that moves to its field). Entered values are kept. Destructive actions always ask for confirmation and say what will happen.
    _Visual identity:_ a wordmark for "Student Competitions" with a simple logo mark, also used as the favicon; the **Classroom blue** palette; neutral surfaces with content grouped on cards against a slightly tinted page background; an 8 px spacing grid; one corner radius (8 px for controls, 12 px for cards); a type scale with clear heading levels. All of these are design tokens defined once at the top of `app.css`, and the rest of the CSS uses the tokens instead of literal values.
    _Classroom blue:_ a deep blue top bar, a bright blue for primary actions, links and the current tab, and amber as the accent (the logo mark, highlights). Success is green and destructive actions are red. The main tokens, light / dark:

    | Token | Light | Dark |
    |---|---|---|
    | Page background | `#f4f6fb` | `#0d1424` |
    | Surface (cards, tables) | `#ffffff` | `#151f35` |
    | Text | `#172033` | `#e6eaf2` |
    | Muted text | `#556070` | `#9aa6bd` |
    | Border | `#dde3ee` | `#26324d` |
    | Top bar | `#16337a` | `#111a2e` |
    | Primary (buttons, current tab) | `#1f56d6` | `#6c9cff` |
    | Text on primary | `#ffffff` | `#0d1424` |
    | Primary tint (selection, icons) | `#e7eefc` | `#1d2c4f` |
    | Accent | `#f2a516` | `#f5b83d` |
    | Success / its tint | `#17803d` / `#e5f5ea` | `#5fcf86` / `#13291c` |
    | Danger / its tint | `#c0392b` / `#fdf0ee` | `#ff8a7a` / `#341b19` |

    _Light and dark themes:_ both themes are complete, and a theme switch with three choices (**Light**, **Dark**, **Device**) sits in the user menu and on the sign-in page. **Device**, the default, follows the device's setting. The choice is kept in a cookie in that browser, so the server renders every page in the chosen theme with no flash on load and no JavaScript; it is not stored in the database and does not follow the person to another browser.
    _Stack:_ still Jinja2, HTMX and Pico.css v2, with no build step and no new runtime frontend dependency. The look comes from overriding Pico's CSS variables; Pico's own stylesheet is not edited. The font files (`woff2`) are kept in `static/`.
    _Page layout:_ a top bar with the logo, the product name and the current role; the email, the role switch, the theme switch and **Log out** in a user menu that opens without JavaScript and folds into the top bar on a phone; the area tabs below it; one content width on every page; a quiet footer with the version.
    _Components:_ Jinja macros in `templates/components/`, each with one purpose:
    - **Top bar and user menu**, **area tabs**, **back link**, and **page heading** with the page's primary action.
    - **Button** in three kinds: *primary* (at most one per page or section), *secondary*, and *destructive* (Delete, Remove, Deactivate, Withdraw consent). The kind decides the look, not whether the HTML is a link or a form: a link that opens a form or a confirmation page looks like the action it leads to.
    - **Card**, for grouping content and for the entries on the home page.
    - **Data table** with row actions: all actions in a row look the same and sit together. Long values wrap. At phone width (below 768 px) each row becomes a card of labelled values, so the page never scrolls sideways.
    - **Status badge** (Active / Deactivated, Read / Write), always with text.
    - **Empty state**: the existing messages ("No subjects yet", "Select a region", …) with a short hint about what to do next.
    - **Notice** in three kinds (success, error, information).
    - **Form field** (label, optional hint, error, entered value kept), **error summary**, and the form's actions (the primary button first, then **Cancel** as a link).
    - **Confirmation page**: the question names the item ("Delete “Physics”?"), the consequence is stated, the destructive button repeats the verb, then **Cancel**. Its refusal variant explains why ("is in use") and offers the alternative (deactivate).
    - **Details list**: label and value pairs, as on the profile and invitation pages.
    - **Selectors**: the list-and-detail pair (regions → institutions) and the chained lists (region → institution → class), ready for reuse in milestones 11 and 12.
    _Home page:_ a start page for the current role: a greeting and a card for each area the role can open, with a one-line description of what is done there. The database status line moves to the footer in muted text. The sample questions keep their place until milestone 11 removes them.
    _Guidelines:_ `docs/requirements/ui-guidelines.md` sets out the principles with their sources; the tokens; when to use each component and each kind of button; wording (the patterns for buttons, confirmations, errors and empty states); and behaviour at phone width. It also records the research for later screens, so they start from it: for taking a competition (milestone 13), a visible countdown with warnings before the end, a "saved" status for answers, and a clear final submit. The constitution's styling rule points to the guidelines, so every later spec and plan is checked against them. A new pattern is first added to the component library and the guidelines, never hand-built on a single page.
    _Design approval:_ the font (Open Sans) and the palette (Classroom blue) were chosen from mockups of several candidates. Before the pages are rebuilt, a mockup of the visual identity and of key pages (sign-in, home, a list, a form with errors, a confirmation) at phone and desktop width, in light and dark mode, is reviewed and approved.
    _Gallery:_ `/admin/components`, open only to administrators and not linked from the tabs, shows every component in every variant with sample data.
    _Existing pages:_ every page (sign-in, role choice, home, profile, consent and data deletion, the administrator and teacher areas, confirmations, error pages) is built from the components. Addresses, fields, texts, messages, the order of steps and access rules stay the same; only wording that breaks the plain-language rules may change. Page-specific CSS classes (`subjects-table`, `teachers-table`, `subjects-empty`, …) are removed; `app.css` holds only the tokens, the page layout and the components.
    _Out of scope:_ accessibility work (conformance to WCAG, screen reader and keyboard-only testing). Pages keep the accessibility features they already have.
    _Test:_ all existing tests pass; only tests that check markup rather than behaviour may change. A test checks that every CSS class used in a template is defined in Pico.css or `app.css`, that every class in `app.css` is used, and that no template has an inline `style`. No page loads anything from another site. Choosing **Light** or **Dark** renders every following page, the sign-in page included, in that theme; **Device** and a missing or unknown cookie value follow the device. Teachers and students get "access denied" on the gallery. Screenshots of every page at phone (375 px) and desktop (1280 px) width, in light and dark mode, are reviewed before merge.

11. **Question bank (teacher).** Uploading a list of questions, viewing, editing, reference answers for questions.
    _Subjects:_ every question belongs to exactly one subject. The teacher selects it from the list kept on the **Subjects** tab (milestone 6), with no free-text entry, and the server accepts only a subject that exists. Teachers can filter the question bank by subject. The sample questions seeded in milestone 3 have no subject, and the migration deletes them, since no real data exists yet.
    _Test:_ question CRUD works and is visible only to teachers. A question without a subject or with an unknown subject is refused. Filtering by subject shows only that subject's questions.

12. **Creating a competition (teacher).** A competition with a subject, a start time, duration, assignment to a class/students, a set of questions from the bank and reference answers.
    _Who can create:_ only a teacher with **Can create competitions** (milestone 8) can create or change competitions. A teacher without it sees no create action, and the server answers with "access denied". The setting covers all the teacher's institutions, so participants can be students of any of them, with Read or Write access. Students of other institutions cannot be assigned.
    _Subjects:_ the teacher selects the competition's subject first, from the list kept on the **Subjects** tab. The question picker then offers only questions of that subject, and the server refuses a competition that includes a question of another subject. Changing the subject of an upcoming competition is refused while it still holds questions of the old subject.
    _Test:_ a competition is created and correctly linked to its subject, questions and participants. A competition with a question from another subject is refused. A teacher without **Can create competitions** gets "access denied". A teacher with it can assign students of a Read-access institution, but not students of an institution they are not linked to.

13. **Taking a competition (student).** List of assigned competitions, enforcement of the time window and duration, entering and submitting text answers. The student's lists of upcoming and past competitions show each competition's subject.
    _Test:_ answers are saved; the competition is not accessible outside its time window.

14. **Answer evaluation via LLM.** Each answer receives a score of 1–10 that takes level of detail into account; results are saved to the database.
    _Test:_ evaluation returns a structured result and it is persisted.

15. **Best answer selection + results.** For each question, the best answer is selected from the group's answers; competition results are saved and displayed.
    _Who sees results:_ a teacher sees the results of the students of their own institutions, with Read or Write access (milestone 8). Results of students from other institutions are not shown to them.
    _Test:_ the best answer is determined, the results page works. A teacher with Read access sees the results of that institution's students and none from institutions they are not linked to.

16. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)
