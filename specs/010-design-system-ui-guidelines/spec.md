# Feature Specification: Professional Design System and UI Guidelines (Milestone 10)

**Feature Branch**: `010-design-system-ui-guidelines`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: milestone 10 of `docs/requirements/milestones.md` ("Professional design
system and UI guidelines"), with the specifications of milestones 1–9 (`specs/001-…` to `specs/009-…`)
as reference for the existing pages.

## Overview

Milestone 10 of the walking skeleton for the Student Competitions application. After milestone 9, the
application does everything its first nine milestones promised, but it looks like a developer's
prototype: Pico.css defaults, page-specific CSS written page by page, and no shared rules for how a
list, a form, an error or a confirmation should look and read.

This milestone changes how the application **looks and reads**, not what it **does**. Six things
become true when it is done:

1. **The application has a visual identity.** A wordmark and logo mark (also the favicon), the
   **Classroom blue** palette, the **Open Sans** font, an 8 px spacing grid, one corner radius and a
   clear type scale, all defined once as design tokens.
2. **Every page has the same frame.** A top bar with the logo, the product name and the current role;
   a user menu with the email, the role switch, the theme switch and **Log out**; the area tabs; one
   content width; a quiet footer with the version.
3. **Pages are built from a component library.** Buttons, cards, data tables, badges, empty states,
   notices, form fields, error summaries, confirmation pages, details lists and selectors each exist
   once and look and behave the same everywhere.
4. **People choose a light or a dark theme.** **Light**, **Dark** or **Device** (the default), kept in
   that browser and rendered by the server with no flash on load.
5. **Written UI guidelines** in `docs/requirements/ui-guidelines.md` set out the principles with their
   sources, the tokens, when to use each component, the wording patterns and phone behaviour, and the
   constitution points to them, so every later milestone builds from them.
6. **Every existing page moves onto the new system with no change in behaviour.** Addresses, fields,
   texts, messages, the order of steps and access rules stay the same. Only wording that breaks the
   plain-language rules may change.

The audience drives the design: students from year 1 to university, mostly on phones, who scan
rather than read and rely on an in-page back link; and teachers and administrators, mostly on
desktops, working with lists and forms. Every page must work for the youngest student who can take a
written competition and stay efficient for staff.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The product owner approves the look before the pages are rebuilt (Priority: P1)

The font (Open Sans) and the palette (Classroom blue) have already been chosen from mockups of several
candidates. Before any existing page is rebuilt, the product owner reviews a mockup of the visual
identity (wordmark, logo mark, palette, type scale) and of five key pages: sign-in, home, a list, a
form with errors and a confirmation. Each is shown at phone and desktop width, in the light and the
dark theme. The product owner approves it or asks for changes; the pages are rebuilt only after
approval.

**Why this priority**: Rebuilding every page on a look nobody approved wastes the whole milestone. The
approval is the gate for the rest of the work.

**Independent Test**: The mockup exists with the feature's documents, covers the identity and the five
key pages in all four width/theme combinations, and carries a recorded approval dated before the first
page is rebuilt.

**Acceptance Scenarios**:

1. **Given** the mockup is ready, **When** the product owner reviews it, **Then** they see the
   wordmark, the logo mark, the palette in both themes, the type scale and the five key pages at
   375 px and 1280 px width, each in light and dark.
2. **Given** the product owner asks for changes, **When** the mockup is updated, **Then** it is
   reviewed again and no existing page is rebuilt until it is approved.
3. **Given** the mockup is approved, **When** the pages are rebuilt, **Then** they follow the approved
   look; a later deviation is recorded and approved again.

---

### User Story 2 - A young student uses the application on a phone (Priority: P1)

Taras is in year 5 and has only a phone. He opens the application, signs in with the code from his
email, and lands on the home page: a greeting and one card per area he can open, each with a one-line
description. The text is large enough to read without zooming, lines are short, and nothing makes the
page scroll sideways. The top bar shows the logo, "Student Competitions" and "Student"; his email,
the theme switch and **Log out** are folded into a user menu he opens with one tap. He opens his
profile, reads his details as label and value pairs, and returns with the back link at the top of the
page rather than the browser's back button.

**Why this priority**: Students are the largest group and mostly use phones. If the youngest student
cannot read and move around the application on a phone, the design has failed.

**Independent Test**: Sign in as a student at 375 px width; check that body text is at least 16 px
with line height at least 1.5, that no page scrolls sideways, that the user menu opens and closes
without JavaScript, and that every page below an area's main page has a back link.

**Acceptance Scenarios**:

1. **Given** a student signs in on a 375 px wide screen, **When** the home page opens, **Then** it
   shows a greeting and one card per area the student role can open, each with a one-line description,
   and the page does not scroll sideways.
2. **Given** the student is on any page at phone width, **When** they open the user menu, **Then** it
   shows their email (linking to the profile), the theme switch and **Log out**, and it opens without
   JavaScript.
3. **Given** a student holds several roles, **When** they open the user menu on a phone, **Then** the
   role switch is in it, and switching works as in milestone 5.
4. **Given** the student opens a page below an area's main page, **When** the page loads, **Then** a
   visible back link at the top leads to the page one level up.
5. **Given** any page, **When** it is shown at phone width, **Then** body text is at least 16 px, line
   height is at least 1.5, text is left-aligned and never justified, and emphasis uses bold.

---

### User Story 3 - Staff work with lists and forms on a desktop (Priority: P1)

Iryna is an administrator working on a 1280 px screen. On the **Subjects** tab she sees a page heading
with its one primary action, **Create subject**, and a data table of subjects with a status badge
("Active" or "Deactivated") on each row and the row's actions together at the end of the row, all
looking the same. She creates a subject with a name that already exists: the form comes back with an
error summary at the top ("There is a problem", one link per error that moves to its field), the same
error next to the field, and her entered value kept. She fixes it and saves. Later she deletes a
subject: the confirmation page asks "Delete “Physics”?", says what will happen, offers a destructive
**Delete** button and **Cancel**. When the subject is in use, the confirmation explains why it cannot
be deleted and offers **Deactivate** instead.

Mykola, a teacher, sees the same patterns on the **Students** tab: the chained lists (region →
institution → class), the class's students in a data table, "Read" and "Write" badges, and the same
forms and confirmations.

**Why this priority**: Staff spend their time in lists and forms. Consistent tables, forms, errors and
confirmations are what make the application feel professional and keep mistakes rare.

**Independent Test**: In the administrator and teacher areas, submit each form with invalid values and
open each destructive action; check the error summary, field errors, kept values, confirmation wording
and button kinds against the guidelines.

**Acceptance Scenarios**:

1. **Given** any list page, **When** it opens, **Then** it shows a page heading with at most one
   primary action, and its items in a data table whose row actions look the same and sit together.
2. **Given** a list is empty, **When** it opens, **Then** it shows the existing empty message ("No
   subjects yet", "Select a region", …) with a short hint about what to do next.
3. **Given** a form is submitted with one or more errors, **When** it is shown again, **Then** an
   error summary headed "There is a problem" is at the top with one link per field error that moves to
   its field, each error is also shown next to its field, and every entered value is kept.
4. **Given** a destructive action (Delete, Remove, Deactivate, Withdraw consent), **When** it is
   chosen, **Then** a confirmation page names the item in its question, states the consequence, offers
   a destructive button that repeats the verb, then **Cancel**. The one exemption is **Deactivate**
   on the **Subjects** list, which stays direct (FR-032a).
5. **Given** a deletion is refused because the item is in use, **When** the confirmation opens,
   **Then** it explains why and offers the alternative (deactivate) where the existing behaviour offers
   it.
6. **Given** a status is shown (Active / Deactivated, Read / Write), **When** the page renders,
   **Then** it is a status badge that always contains text.
7. **Given** a link that opens a form or a confirmation page, **When** it is shown, **Then** it looks
   like the action it leads to (primary, secondary or destructive), not like a plain link.

---

### User Story 4 - Every existing page keeps its behaviour (Priority: P1)

Every page delivered in milestones 1–9 (sign-in and code entry, role choice, home, profile and
withdrawal, invitation and consent, data deletion, the administrator area, the teacher area,
confirmations, "access denied", "not found" and other error pages) is rebuilt from the components.
A person who knew the application before this milestone finds the same addresses, the same fields,
the same texts and messages and the same steps in the same order, and is allowed and denied exactly
what they were before.

**Why this priority**: This milestone must not break anything. A redesign that changes behaviour
silently is a regression, not a feature.

**Independent Test**: The full test suite of milestones 1–9 passes; only tests that check markup
rather than behaviour are changed, and every changed message is listed and justified by a
plain-language rule.

**Acceptance Scenarios**:

1. **Given** the tests of milestones 1–9, **When** they run after the rebuild, **Then** they all pass,
   and the only changed tests are those that checked markup rather than behaviour.
2. **Given** any page, **When** it is opened, **Then** its address, its fields and their names, its
   messages and the order of its steps are the same as before, except wording changed to follow the
   plain-language rules.
3. **Given** any page and any role, **When** it is opened, **Then** access is allowed or denied as
   before.
4. **Given** the page-specific CSS classes (`subjects-table`, `teachers-table`, `subjects-empty`, …),
   **When** the rebuild is done, **Then** none of them remain, and the stylesheet holds only the
   tokens, the page layout and the components.

---

### User Story 5 - A person chooses a light or a dark theme (Priority: P2)

Sofia studies in the evening and prefers dark pages. On the sign-in page, before she signs in, she
sets the theme switch to **Dark**; the sign-in page and every following page render dark, with no
flash of light on load. On her school's shared computer she never changed it, so the application
follows that device's setting (**Device**). Her choice is kept only in the browser where she made it;
it is not stored with her account and does not follow her to another browser.

**Why this priority**: Both themes must be complete, and the choice must work everywhere, but the
application is usable in the device's theme without it.

**Independent Test**: Choose **Light**, then **Dark**, then **Device** from the user menu and from the
sign-in page; check that each following page, the sign-in page included, renders in that theme from
the server, and that a missing or unknown stored value follows the device.

**Acceptance Scenarios**:

1. **Given** a visitor on the sign-in page, **When** they choose **Dark**, **Then** they return to the
   sign-in page, it renders dark, and every following page renders dark.
2. **Given** a signed-in person, **When** they choose **Light** from the user menu, **Then** they
   return to the same page in the light theme, and every following page renders light.
3. **Given** the choice is **Device**, or no choice was made, or the stored value is unknown, **When**
   a page renders, **Then** it follows the device's light or dark setting.
4. **Given** a person chose **Dark** in one browser, **When** they sign in from another browser,
   **Then** that browser uses its own choice (**Device** by default).
5. **Given** any page in the chosen theme, **When** it loads, **Then** it is rendered in that theme by
   the server, with no flash of the other theme and without JavaScript.

---

### User Story 6 - A visitor recognises the application and finds their way from the home page (Priority: P2)

A teacher opening the application for the first time sees the logo mark and the "Student
Competitions" wordmark in the top bar and on the browser tab (favicon). The home page is a start page
for the current role: a greeting and a card for each area the role can open, with a one-line
description of what is done there. The database status line, which proves that data persists, is in
the footer in muted text. The sample questions keep their place on the home page until milestone 11
removes them.

**Why this priority**: Identity and a clear start page make the application look trustworthy and
show each role where to go, but the existing home page already links to the areas.

**Independent Test**: Sign in with each role; check the wordmark, the favicon, one card per allowed
area with its description, the sample questions, and the database status line in the footer.

**Acceptance Scenarios**:

1. **Given** any page, **When** it opens, **Then** the top bar shows the logo mark, the product name
   and, when signed in, the current role, and the browser tab shows the logo mark as the favicon.
2. **Given** a signed-in person in any role, **When** the home page opens, **Then** it shows a
   greeting and one card per area that role can open, each linking to the area with a one-line
   description, and no card for an area the role cannot open.
3. **Given** the database is reachable, **When** the home page opens, **Then** the sample questions
   are listed as before and the database status line is in the footer in muted text.
4. **Given** the database is briefly unreachable, **When** the home page opens, **Then** it still
   opens and shows "data temporarily unavailable" as an information notice, as in milestone 3.

---

### User Story 7 - An administrator reviews every component in the gallery during development (Priority: P3)

The gallery is a development tool: it exists only when the application runs locally, never in the
production deployment. On a local run, an administrator opens `/admin/components`, which is not
linked from the tabs. It shows every component in every variant with sample data: the three button
kinds, cards, a data table (with wide and phone layouts), badges, empty states, the three notice
kinds, form fields with hints and errors, an error summary, a confirmation and its refusal variant, a
details list and both selectors. Teachers and students who open the address get "access denied". In
production, the address does not exist and everyone gets "not found".

**Why this priority**: The gallery makes review and later reuse easy, but no user task depends on it,
so it has no place in the production deployment.

**Independent Test**: On a local run, open the gallery as an administrator and check that every
component and variant listed in the requirements appears; open it as a teacher and as a student and
check "access denied". With the application configured as production, open the address as an
administrator and check "not found".

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they open `/admin/components`, **Then** every component in
   every variant is shown with sample data, in the current theme.
2. **Given** the administrator area tabs, **When** they are shown, **Then** none of them links to the
   gallery.
3. **Given** a person in the teacher or the student role, **When** they open `/admin/components`,
   **Then** they get "access denied" naming their current role.
4. **Given** the gallery's sample data, **When** the gallery is shown, **Then** nothing is read from
   or written to the database for it.
5. **Given** the production deployment, **When** anyone, an administrator included, opens
   `/admin/components`, **Then** they get "not found", the same as for any other unknown address.

---

### User Story 8 - A developer builds a later milestone from the guidelines (Priority: P3)

A developer starting milestone 11 reads `docs/requirements/ui-guidelines.md`. It explains each design
principle with its sources, lists the tokens, says when to use each component and each button kind,
gives the wording patterns for buttons, confirmations, errors and empty states, and describes
behaviour at phone width. It also records research for later screens: for taking a competition
(milestone 13), a visible countdown with warnings before the end, a "saved" status for answers and a
clear final submit. The constitution's styling rule points to the guidelines, so the new spec and plan
are checked against them. When the developer needs a pattern that does not exist, they add it to the
component library and the guidelines first.

**Why this priority**: The guidelines pay off in later milestones; this milestone only has to write
them and make them binding.

**Independent Test**: Review the guidelines for the required sections; check that the constitution's
styling rule references them; run the automated stylesheet checks.

**Acceptance Scenarios**:

1. **Given** the guidelines, **When** they are read, **Then** they cover the principles with sources,
   the tokens, every component and button kind with when to use it, the wording patterns, phone
   behaviour and the research for the competition-taking screens.
2. **Given** the constitution, **When** its styling rule is read, **Then** it points to the guidelines
   and requires new patterns to be added to the component library and the guidelines first.
3. **Given** the templates and the stylesheet, **When** the automated checks run, **Then** every CSS
   class used in a template is defined in Pico.css or `app.css`, every class in `app.css` is used, and
   no template has an inline `style`.

---

### Edge Cases

- **Long values** (a long email in the user menu, long names or institution names in a table cell, a
  long subject name in a confirmation question) wrap; no page ever scrolls sideways at 375 px.
- **A data table at phone width** (below 768 px) shows each row as a card of labelled values, with the
  row's actions together at the end of the card.
- **An empty list** shows the empty state instead of an empty table with headers.
- **A form error that belongs to no single field** (for example a rate limit) is shown in the error
  summary as text without a link, and not next to any field.
- **A form with exactly one error** still shows the error summary.
- **The theme switch** returns the person to the page they used it on; only addresses inside the
  application are accepted as the return target, and anything else returns to the home page (or, when
  signed out, the sign-in page).
- **A stored theme value that is missing, empty or unknown** is treated as **Device**.
- **The device switches between light and dark** while the choice is **Device**: the next page, and
  the open page where the device allows it, follows the new setting.
- **Public pages other than sign-in** (consent, data deletion, invitation and link status pages, "not
  found") render in the chosen theme but show no theme switch.
- **The font files fail to load**: pages fall back to the system font stack and stay readable.
- **JavaScript is off**: the user menu, the theme switch, the tabs and the confirmation flows still
  work; pages keep any existing no-JavaScript fallback they already had.
- **A person holding several roles** at phone width finds the role switch inside the user menu; a
  person with one role sees no role switch.
- **"Access denied", "not found" and other error pages** use the same layout and components, and keep
  their texts and status codes.
- **Very wide screens** keep the one content width; content does not stretch across the screen.
- **The gallery** opened by someone who is an administrator but currently acting as a teacher or
  student shows "access denied" naming the current role, as for any administrator page (milestone 5).
  In production the gallery does not exist, so every person, signed in or not and in any role, gets
  "not found"; the response does not reveal that the address exists elsewhere.
- **Deactivating a subject** from the **Subjects** list happens at once, without a confirmation page,
  as today (FR-032a); the button is destructive, and **Activate** on the same row undoes it.
- **A page that shows the same status for many rows** (for example many "Deactivated" badges) uses the
  same badge on every row; colour is never the only signal.

## Requirements *(mandatory)*

### Functional Requirements

#### Design principles

- **FR-001**: Every page MUST follow five design principles, each explained with its sources in the
  guidelines: **calm and focused**, **clear and consistent**, **readable**, **plain language** and
  **forgiving**.
- **FR-002**: **Calm and focused**: content MUST come first, with no decoration that competes with
  it. Pages MUST have no moving or blinking content; transitions MUST be subtle. Pages MUST show no
  advertising or promotional content.
- **FR-003**: **Clear and consistent**: each page MUST have one navigation. The same component MUST
  look and behave the same everywhere and sit in the same place. Every page below an area's main page
  MUST have a visible back link to the page one level up.
- **FR-004**: **Readable**: body text MUST be at least 16 px on phones and at least 18 px on desktops,
  with line height at least 1.5 and lines no longer than about 70 characters. Text MUST be
  left-aligned and never justified. Emphasis MUST use bold, not italics, underlining or capitals.
- **FR-005**: The font MUST be **Open Sans** (open licence, Latin and Cyrillic letters) in regular
  400, semibold 600 and bold 700, served by the application itself, never from a third-party font
  service, with the system font stack as a fallback.
- **FR-006**: **Plain language**: texts MUST use short sentences and words students know. Buttons MUST
  be verbs ("Save", "Invite student"). Abbreviations MUST be spelled out. Instructions MUST be a
  sentence or two, placed where they are needed.
- **FR-007**: **Forgiving**: every form error MUST be shown next to its field and in an error summary
  at the top of the page; entered values MUST be kept; destructive actions MUST always ask for
  confirmation and say what will happen, with the one exemption of FR-032a.

#### Visual identity and tokens

- **FR-008**: The application MUST have a wordmark for "Student Competitions" with a simple logo mark.
  The logo mark MUST also be the favicon.
- **FR-009**: The application MUST use the **Classroom blue** palette: a deep blue top bar; a bright
  blue for primary actions, links and the current tab; amber as the accent (the logo mark,
  highlights); green for success; red for destructive actions.
- **FR-010**: The main tokens MUST have these values in the light and the dark theme:

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

- **FR-011**: Surfaces MUST be neutral, with content grouped on cards against a slightly tinted page
  background. Spacing MUST follow an 8 px grid. Controls MUST use an 8 px corner radius and cards a
  12 px corner radius. A type scale MUST give clear heading levels.
- **FR-012**: All tokens (colours, font, spacing, radii, type scale) MUST be defined once at the top of
  `app.css`. The rest of the stylesheet MUST use the tokens instead of literal values.

#### Light and dark themes

- **FR-013**: Both themes MUST be complete: every page and every component MUST be fully styled in
  each.
- **FR-014**: A theme switch with three choices, **Light**, **Dark** and **Device**, MUST be in the
  user menu and on the sign-in page. **Device** MUST be the default and MUST follow the device's
  setting.
- **FR-015**: The choice MUST be kept in a cookie in that browser and MUST NOT be stored in the
  database; it MUST NOT follow the person to another browser. The cookie MUST hold only the choice.
- **FR-016**: The server MUST render every page, the sign-in page included, in the chosen theme, with
  no flash of the other theme on load and without JavaScript. A missing or unknown cookie value MUST
  be treated as **Device**.
- **FR-017**: Using the theme switch MUST return the person to the page they used it on. Only
  addresses inside the application MUST be accepted as the return target.

#### Page layout

- **FR-018**: Every page MUST have a top bar with the logo mark, the product name and, when signed in,
  the current role.
- **FR-019**: When signed in, the email (linking to the profile), the role switch (for people with
  several roles), the theme switch and **Log out** MUST be in a user menu that opens without
  JavaScript and folds into the top bar on a phone.
- **FR-020**: Area pages MUST show the area tabs below the top bar, with the current tab highlighted
  in the primary colour.
- **FR-021**: Every page MUST use one content width, and MUST end with a quiet footer that shows the
  version.
- **FR-022**: No page MUST scroll sideways at 375 px width.

#### Components

- **FR-023**: Every component MUST exist once in the component library (Jinja macros in
  `templates/components/`), each with one purpose, and pages MUST use the components instead of
  building the same pattern by hand.
- **FR-024**: **Top bar and user menu**, **area tabs**, **back link** and **page heading** (with the
  page's primary action) MUST be components.
- **FR-025**: **Button** MUST come in three kinds: *primary* (at most one per page or section),
  *secondary* and *destructive* (Delete, Remove, Deactivate, Withdraw consent). The kind MUST decide
  the look, whether the button is a link or a form button: a link that opens a form or a confirmation
  page MUST look like the action it leads to.
- **FR-026**: **Card** MUST group content, and MUST be used for the entries on the home page.
- **FR-027**: **Data table** MUST show row actions that all look the same and sit together. Long
  values MUST wrap. Below 768 px each row MUST become a card of labelled values, so the page never
  scrolls sideways.
- **FR-028**: **Status badge** (Active / Deactivated, Read / Write) MUST always contain text.
- **FR-029**: **Empty state** MUST show the existing empty message ("No subjects yet", "Select a
  region", …) with a short hint about what to do next.
- **FR-030**: **Notice** MUST come in three kinds: success, error and information.
- **FR-031**: **Form field** MUST show the label, an optional hint, the error when there is one, and
  the entered value kept. **Error summary** MUST be headed "There is a problem" and list one link per
  field error that moves to its field; an error that belongs to no single field MUST be listed as text.
  The form's actions MUST show the primary button first, then **Cancel** as a link.
- **FR-032**: **Confirmation page** MUST name the item in its question ("Delete “Physics”?"), state the
  consequence, offer a destructive button that repeats the verb, then **Cancel**. Its refusal variant
  MUST explain why the action is refused ("is in use") and offer the alternative (deactivate) where the
  existing behaviour offers it.
- **FR-032a** (exemption): **Deactivate** on the **Subjects** list stays a direct action with no
  confirmation page, as it works today. A confirmation would need a new page and route, which this
  look-only milestone rules out (FR-040, FR-050), and the action is reversible with **Activate** on
  the same row. It MUST still be shown as a destructive button. Adding the confirmation is recorded
  in `docs/issues-to-fix.md` for a later milestone.
- **FR-033**: **Details list** MUST show label and value pairs, as on the profile and invitation pages.
- **FR-034**: **Selectors** MUST include the list-and-detail pair (regions → institutions) and the
  chained lists (region → institution → class), ready for reuse in milestones 11 and 12.

#### Home page

- **FR-035**: The home page MUST be a start page for the current role: a greeting and a card for each
  area the role can open, each with a one-line description of what is done there.
- **FR-036**: The database status line MUST move to the footer of the home page, in muted text. The
  sample questions MUST keep their place on the home page until milestone 11 removes them, and the
  "data temporarily unavailable" behaviour of milestone 3 MUST be kept.

#### Component gallery

- **FR-037**: `/admin/components` MUST show every component in every variant with sample data that is
  neither read from nor written to the database.
- **FR-038**: The gallery MUST be open only to the administrator role and MUST NOT be linked from the
  area tabs. Every other role MUST get "access denied".
- **FR-038a**: The gallery MUST exist only when the application runs outside production. On the
  production platform, detected the same way as the production guards of milestones 3 and 4,
  `/admin/components` MUST respond with "not found" to everyone, exactly as an unknown address does.

#### Existing pages

- **FR-039**: Every existing page (sign-in and code entry, role choice, home, profile and withdrawal,
  invitation and consent, data deletion, the administrator and teacher areas, confirmations, error
  pages) MUST be built from the components.
- **FR-040**: Addresses, fields, texts, messages, the order of steps and access rules MUST stay the
  same. Only wording that breaks the plain-language rules MAY change, and every such change MUST be
  listed with the rule it follows.
- **FR-041**: Page-specific CSS classes (`subjects-table`, `teachers-table`, `subjects-empty`, …) MUST
  be removed. `app.css` MUST hold only the tokens, the page layout and the components.
- **FR-042**: Pages MUST keep the accessibility features they already have (labels, error
  associations, the current-tab marker, landmarks and similar).

#### UI guidelines and governance

- **FR-043**: `docs/requirements/ui-guidelines.md` MUST set out the design principles with their
  sources; the tokens; when to use each component and each kind of button; the wording patterns for
  buttons, confirmations, errors and empty states; and behaviour at phone width.
- **FR-044**: The guidelines MUST record the research for later screens, so they start from it: for
  taking a competition (milestone 13), a visible countdown with warnings before the end, a "saved"
  status for answers, and a clear final submit.
- **FR-045**: The constitution's styling rule MUST point to the guidelines, so every later spec and
  plan is checked against them. A new pattern MUST first be added to the component library and the
  guidelines, never hand-built on a single page.

#### Design approval

- **FR-046**: Before the existing pages are rebuilt, a mockup of the visual identity and of key pages
  (sign-in, home, a list, a form with errors, a confirmation) at phone and desktop width, in the light
  and the dark theme, MUST be reviewed and approved by the product owner. The approval MUST be
  recorded with the feature's documents.

#### Constraints

- **FR-047**: The stack MUST stay Jinja2, HTMX and Pico.css v2, with no build step and no new runtime
  frontend dependency. The look MUST come from overriding Pico's CSS variables; Pico's own stylesheet
  MUST NOT be edited. The font files (`woff2`) MUST be kept in `static/`.
- **FR-048**: No page MUST load anything (fonts, styles, scripts, images) from another site.
- **FR-049**: Every CSS class used in a template MUST be defined in Pico.css or `app.css`; every class
  defined in `app.css` MUST be used in a template; no template MUST have an inline `style`.

#### Scope

- **FR-050**: This milestone MUST NOT change any product behaviour beyond the look, the theme switch,
  the home page cards and the gallery. It MUST NOT add accessibility conformance work (WCAG
  conformance, screen-reader or keyboard-only testing), new pages other than the gallery, or new data
  stored in the database. The production deployment MUST gain no new page: the gallery is local only
  (FR-038a).

### Key Entities *(include if feature involves data)*

- **Theme choice** (new, not stored in the database): **Light**, **Dark** or **Device**, kept in a
  cookie in one browser. Not personal data and not linked to an account. Missing or unknown means
  **Device**.
- **Design token** (new, not data): a named value (colour, font, spacing, radius, type size) defined
  once, with a light and a dark value where it differs.
- **Component** (new, not data): a reusable page building block with one purpose and documented
  variants, shown in the gallery and described in the guidelines.
- **UI guidelines** (new document): the binding description of principles, tokens, components,
  wording and phone behaviour for this and every later milestone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pages, at 375 px and 1280 px width, in the light and the dark theme, are captured
  in screenshots and reviewed by the product owner before merge; 0 of them scroll sideways at 375 px.
- **SC-002**: 100% of the tests of milestones 1–9 pass; the only changed tests check markup rather than
  behaviour.
- **SC-003**: 0 pages load any resource from another site.
- **SC-004**: 100% of CSS classes used in templates are defined, 100% of classes in `app.css` are used,
  and 0 templates have an inline `style`; 0 page-specific classes remain.
- **SC-005**: After choosing **Light** or **Dark**, 100% of following pages, the sign-in page included,
  render in that theme from the server; with **Device**, no cookie or an unknown value, 100% of pages
  follow the device.
- **SC-006**: 100% of forms shown with errors display each field error both next to its field and in
  the error summary, and keep 100% of the entered values.
- **SC-007**: 100% of destructive actions, except the subject **Deactivate** exemption (FR-032a), go
  through a confirmation page that names the item, states the consequence and repeats the verb on the
  destructive button.
- **SC-008**: On every page, body text is at least 16 px at phone width and at least 18 px at desktop
  width, with line height at least 1.5.
- **SC-009**: On a local run, the gallery shows 100% of the components and variants listed in FR-024
  to FR-034, and 100% of attempts by the teacher and student roles get "access denied"; in production,
  100% of requests to `/admin/components` get "not found".
- **SC-010**: A year-5 student can sign in, open their profile and return to the home page on a phone
  in under 2 minutes, not counting the wait for the emailed code, without using the browser's back
  button.
- **SC-011**: 0 page addresses, form field names or access rules change; every changed message is
  listed with the plain-language rule it follows.

## Assumptions

- **The product owner** is the person who refined the milestone; they approve the mockup and the
  screenshots. The mockup and the record of approval are kept with the feature's documents.
- **The gallery is a development tool**: it is used by developers and by the product owner on a
  local run, to review the components and to reuse them in later milestones. Production users have
  no task that needs it, so it is left out of the production deployment; the product owner's
  approval of the look is based on the mockup (User Story 1) and the screenshots, not on a deployed
  gallery.
- **The mockup covers** the identity and the five key pages named in the milestone; other pages follow
  the approved patterns and are checked in the screenshot review before merge.
- **The theme cookie** holds only the choice, has no identifier, and lasts one year. As a preference
  cookie it needs no consent of its own.
- **The theme switch** is a small form that sets the choice and returns to the same page; on a page
  shown after a failed form submission, it returns to that page's address, and unsaved entries in
  another form on the page are not kept.
- **Public pages other than sign-in** render in the chosen theme but do not show the switch, because
  the milestone places it only in the user menu and on the sign-in page.
- **The back link** leads to a fixed page one level up (for example from a subject form to the
  **Subjects** tab, keeping the selection in the page address where the page has one), not to the
  browser's history.
- **The database status line** is shown in the footer of the home page only, as it was shown only on
  the home page before; other pages' footers show the version only.
- **Form-level errors** (not tied to one field, such as a rate limit) appear in the error summary as
  text without a link.
- **Success notices** are used only where a page already shows a message after an action; no new
  messages are added.
- **The 768 px breakpoint** is used for both the data table's card layout and the folded user menu.
- **Tokens not listed in the milestone** (hover and focus shades, text on success and danger, the
  heading sizes) are derived from the palette in the plan and documented in the guidelines.
- **Icons**, if any, are drawn within the application; no icon library or icon font is added.
- **Supported browsers** are current versions of the major desktop and mobile browsers.
- **The interface language** stays English; the font's Cyrillic letters are for names and later
  content.
- **Emails** sent by the application (codes, invitations, deletion links) keep their current content
  and format.

## Dependencies

- **Milestones 1–9**: every page, message and access rule that this milestone rebuilds without
  changing: the home page and its database status (1, 3), sign-in and sessions (4), roles, role
  switching and "access denied" (5), the administrator area (6, 7, 8), invitations, consent, profile
  and data deletion (8), and the teacher area with its chained lists (9).
- **Constitution amendment**: the styling rule's pointer to the guidelines is a constitution change,
  made with `/speckit-constitution` as the governance section requires.
- **Later milestones that depend on this one**: milestone 11 (question bank) and 12 (creating a
  competition) build their pages from the components and reuse the selectors; milestone 13 (taking a
  competition) starts from the research recorded in the guidelines; every later spec and plan is
  checked against the guidelines.

## Out of Scope

- Accessibility conformance work: WCAG conformance, screen-reader and keyboard-only testing. Pages keep
  the accessibility features they already have.
- Any change in product behaviour: addresses, fields, steps, access rules and stored data stay the
  same.
- Storing the theme choice with the account or carrying it across browsers.
- A frontend build step, a new runtime frontend dependency, a move to React, or editing Pico's own
  stylesheet.
- Translating the interface into other languages.
- Redesigning the emails the application sends.
- Advertising, promotional or marketing pages.
- The screens of later milestones (question bank, competitions, results); the guidelines only record
  research for them.
