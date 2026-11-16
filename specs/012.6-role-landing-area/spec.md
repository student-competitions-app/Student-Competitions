# Feature Specification: Each Role Lands in Its Own Area (Milestone 12.6)

**Feature Branch**: `012.6-role-landing-area`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "create specification for the 12.6 milestone": milestone 12.6 of
`docs/requirements/milestones.md` ("Each role lands in its own area"), placed in the 12.x group after
milestone 12.5, with `product-requirements.md`, `technical-requirements.md`, the constitution v2.4.0
(Principles I, II, III, IV and the Documentation quality gate), the milestone 3, 5, 6, 9, 10 and 12.5
specifications and `docs/requirements/ui-guidelines.md` as reference.

## Overview

Milestone 12.6 of the walking skeleton for the Student Competitions application. Like milestone 12.5, it
is not about competitions: it takes administrators and teachers straight to their own area.

Today an administrator or a teacher who signs in first lands on the home page (`/`). For them the page
only shows cards for the areas they may open: their own area and the **Staff area** (`/staff`). The
Staff area is a placeholder that milestone 5 created for pages shared by administrators and teachers. No
milestone ever filled it, and none plans to. So staff click through a page that offers one real choice,
and that choice sits next to an empty one. Six things become true when this milestone is done:

1. **An administrator lands in the administrator area, and a teacher in the teacher area.** `/` sends
   each of them to the area of their current role. Every way into the application that ends at `/`
   ends there: signing in, choosing a role, switching role, the brand link in the top bar.
2. **The Staff area is gone.** `/staff` is an unknown address for everyone, and nothing links to it or
   says its name in either language.
3. **Administrators still see the database line.** The line ("Database: … · schema revision … · boot
   #…") moves from the home page footer to the footer of every administrator area page.
4. **Links back lead to the area.** On the profile page and the error page, an administrator's or a
   teacher's back link names their area and leads straight to it.
5. **Nothing changes for a student.** `/` still shows a student the home page with its single
   **Student area** card and the database line.
6. **Nothing is left behind.** The staff area and the parts of the home page that only staff used are
   removed from the code, the messages in both languages, the tests and the documentation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator or a teacher lands in their own area (Priority: P1)

An administrator signs in and goes straight to the administrator area, on its first tab, **Teachers**. A
teacher signs in and goes straight to the teacher area, on its first tab, **Students**. Neither sees the
home page on the way. The brand link in the top bar takes them to the same place from any page.

**Why this priority**: This is the milestone. Staff open the application many times a day, and the home
page gives them one click and nothing else.

**Independent Test**: Sign in as an administrator, then as a teacher, each with one role. Check where
each one lands after the code and after following the brand link.

**Acceptance Scenarios**:

1. **Given** a signed-in administrator, **When** they open `/`, **Then** they are redirected (303) to
   `/admin`, which opens the **Teachers** tab.
2. **Given** a signed-in teacher, **When** they open `/`, **Then** they are redirected (303) to
   `/teacher`, which opens the **Students** tab.
3. **Given** an administrator with only that role, **When** they sign in without a return address,
   **Then** they arrive at the **Teachers** tab without seeing the home page.
4. **Given** a teacher with only that role, **When** they sign in without a return address, **Then** they
   arrive at the **Students** tab without seeing the home page.
5. **Given** an administrator or a teacher on any page, **When** they follow the brand link in the top
   bar, **Then** they arrive in their own area.
6. **Given** a person with one role, **When** they open the role choice (`/role`), **Then** they are
   sent to `/` as today, and from there to their area.
7. **Given** a sign-in with a return address (for example `/teacher/competitions`), **When** the code is
   accepted, **Then** the person goes to that address, as today.

---

### User Story 2 - A person with several roles lands in the area of the role they chose (Priority: P1)

A person who is both an administrator and a teacher signs in, chooses a role, and lands in that role's
area. When they switch role from the user menu, they land in the area of the new role.

**Why this priority**: People with both staff roles are the ones who switch most often, and the switch
must never leave them in the area they just left.

**Independent Test**: Sign in as a person with both staff roles, choose one, then switch to the other from
the user menu. Check where each step lands.

**Acceptance Scenarios**:

1. **Given** a person with several roles who signs in without a return address, **When** the code is
   accepted, **Then** they see the role choice first, as today (`/role?next=%2F`).
2. **Given** the role choice, **When** they choose **Administrator**, **Then** they land on the
   **Teachers** tab of the administrator area. **When** they choose **Teacher** instead, **Then** they
   land on the **Students** tab of the teacher area.
3. **Given** a person working as a teacher, **When** they switch to **Administrator** from the user menu,
   **Then** they land in the administrator area, and the other way round in the teacher area.
4. **Given** a person with several roles who has not chosen one yet, **When** they open `/` or follow
   the brand link, **Then** they get the role choice, as today.
5. **Given** a person who is a teacher and a student, **When** their current role is **Student**,
   **Then** `/` shows them the student's home page. **When** they switch to **Teacher**, **Then** they
   land in the teacher area.

---

### User Story 3 - The empty Staff area is gone (Priority: P2)

Nobody is shown the Staff area again. Its address answers like any address the application does not have,
and its name appears nowhere in either language.

**Why this priority**: The empty page is the reason the home page offered staff a choice at all. Leaving
it reachable would keep a dead end in the application.

**Independent Test**: Open `/staff` as each role and signed out, and look for any link to it or any
mention of its name in both languages.

**Acceptance Scenarios**:

1. **Given** an administrator, a teacher, a student or a signed-out visitor, **When** they open `/staff`,
   **Then** they get **404 Page not found**, exactly as for any other unknown address.
2. **Given** any page of the application, in Ukrainian or in English, **When** it is shown to anyone,
   **Then** it has no link to `/staff` and no mention of the Staff area: neither "Staff area" nor
   «Розділ працівників».
3. **Given** a sign-in whose return address is `/staff` (an old bookmark), **When** the code is accepted,
   **Then** the person gets the **Page not found** page. An unknown address never reads the session, so
   its back link is "Back to the home page" (User Story 5, FR-016). It leads to `/`, and from there to
   the person's area.

---

### User Story 4 - Administrators still see the database line (Priority: P2)

The footer of every administrator area page shows the database line that the home page footer shows today:
the database engine, the schema revision and the boot count. A teacher never sees it. A student still
sees it on the home page.

**Why this priority**: The line tells an administrator which database and schema revision are live.
Without this story they would lose it when the home page goes away.

**Independent Test**: Open pages of the administrator area and of the teacher area, and the student's
home page, and check their footers. Then make reading the line fail and open an administrator area page.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they open any page of the administrator area (every tab, every
   page inside a tab, and the component gallery where it is served), **Then** its footer shows the
   database line, with the same content and look as on the home page today.
2. **Given** a teacher, **When** they open any page of the teacher area, **Then** its footer has no
   database line.
3. **Given** a student, **When** they open `/`, **Then** the home page footer shows the database line, as
   today.
4. **Given** reading the database line fails, **When** an administrator opens an administrator area
   page, **Then** the page renders without the line, and the error is logged by type and message only,
   never with the database address.

---

### User Story 5 - Back links lead to the person's area (Priority: P3)

On the profile page and the error page, the back link today reads "Back to the home page" and leads to
`/`. For an administrator it now reads "Back to the administrator area" and leads to `/admin`. For a
teacher it reads "Back to the teacher area" and leads to `/teacher`. Everyone else keeps the link to the
home page.

**Why this priority**: Without it, the link would still name a home page that staff never see. Staff
would still arrive in the right place, so this is wording, not a broken path.

**Independent Test**: Open the profile page and an error page as an administrator, a teacher, a student
and a person with several roles who has not chosen one, and read the back link.

**Acceptance Scenarios**:

1. **Given** the current role is **Administrator**, **When** the profile page or the error page is
   shown, **Then** the back link reads "Back to the administrator area" («Назад до розділу
   адміністратора») and leads to `/admin`.
2. **Given** the current role is **Teacher**, **When** the profile page or the error page is shown,
   **Then** the back link reads "Back to the teacher area" («Назад до розділу педагога») and leads to
   `/teacher`.
3. **Given** the current role is **Student**, **When** the profile page or the error page is shown,
   **Then** the back link reads "Back to the home page" and leads to `/`, as today.
4. **Given** a signed-out visitor, a person with several roles who has not chosen one, or a person whose
   current role is not read (as on any unknown address), **When** the error page is shown, **Then** the
   back link reads "Back to the home page" and leads to `/`, as today. The profile page needs a chosen
   role, so it is never shown without one.
5. **Given** the "data erased" page, which is shown to a signed-out person, **When** it is shown, **Then**
   its link does not change.
6. **Given** a teacher who opens an administrator page, **When** they get **403 Access denied**, **Then**
   its back link reads "Back to the teacher area".

---

### User Story 6 - Nothing is left of what was removed (Priority: P3)

A developer or a reviewer who reads the code, the message catalogues, the tests or the documentation finds
nothing that serves, renders, translates, tests or describes the Staff area, or the home page as a page
for administrators and teachers.

**Why this priority**: Leftovers mislead the next milestone. Unused messages cost translation work, and
tests of removed behaviour hide what the application really does.

**Independent Test**: Search the application, the tests, the README and the requirement documents for the
Staff area and for the staff home page, and run the catalogue checks and the full test suite.

**Acceptance Scenarios**:

1. **Given** the application code, **When** it is searched, **Then** it holds no declaration, handler,
   helper, template block, page value or style rule that only the Staff area or the staff home page used.
   The home page and the area placeholder page stay, because the student still uses them.
2. **Given** the message catalogues, **When** the messages are extracted again, **Then** both catalogues
   match the code exactly: no unused, obsolete or untranslated entries. The Staff area's title and
   description and the administrator and teacher area card descriptions are gone. The two new back-link
   labels are there, in both languages.
3. **Given** the tests, **When** they are read, **Then** no test checks the Staff area or the
   administrator's and teacher's home page cards. These tests are deleted or rewritten for the new
   behaviour, never skipped. Only the test that `/staff` answers 404 mentions `/staff`. No test helper or
   fixture is left without a user.
4. **Given** the comments and docstrings, **When** they are read, **Then** none says that the home page
   links to the administrator, teacher or staff area, or that `/` shows a home page to every role.
5. **Given** the README, the UI guidelines, the product and technical requirements and the Delivered
   section of the milestones document, **When** they are read, **Then** they describe the new
   behaviour. The specifications of delivered milestones are not edited.

---

### Edge Cases

- **Several roles, current role chosen.** `/` follows the current role only, never another role the
  person holds. A person whose current role is **Administrator** goes to `/admin` even if they are also a
  teacher.
- **No current role yet.** A person with several roles who has not chosen one gets the role choice,
  whatever address they open, as today. After choosing, they land in the chosen role's area.
- **The redirect grants nothing.** The area applies its own access check, as it does today when its
  address is opened directly. A person whose role changed since they opened `/` gets what the area
  answers to that role.
- **The database is unreachable while opening `/`.** The current role cannot be read. The application
  answers exactly as it does today when a signed-in page cannot read the session.
- **Signed out.** `/` still sends a signed-out visitor to sign in, with `/` as the return address, as
  today. After signing in they land in their area.
- **An old `/staff` bookmark.** A signed-out visitor opening `/staff` gets **Page not found**, not the
  sign-in page, the same as any unknown address. A sign-in with `/staff` as its return address ends on
  **Page not found**.
- **The language and theme switches.** They keep returning the reader to the page they were on. Used on
  an area page, they stay on that page and never pass through `/`.
- **The component gallery.** It is part of the administrator area where it is served, so it shows the
  database line. In production it stays an unknown address, as today.
- **Reading the database line fails on an administrator page.** Only the line is left out. The rest of the
  page is unaffected, and the page does not fail because of the line.
- **A student's home page.** It stays exactly as today: the greeting, the single **Student area** card,
  the "data unavailable" notice when the database cannot be read, and the database line in the footer.
- **A 403 or 404 for a person with several roles and no chosen role.** The error page's back link stays
  "Back to the home page", which leads to the role choice.
- **An unknown address for a signed-in administrator or teacher.** An address the application does not
  have never reads the session, so its page looks the same for everyone. Its back link is "Back to the
  home page", and following it lands an administrator or a teacher in their area through `/`. **Access denied** reads the
  session, so its back link names the person's area. A refused cross-site request is turned away before
  the session is read, so its back link is "Back to the home page". The areas' own "not found"
  pages (an unknown subject, region or competition) keep their own back links and do not change.

## Requirements *(mandatory)*

### Functional Requirements

**Landing**

- **FR-001**: When the current role is **Administrator**, `/` MUST redirect with 303 See Other to
  `/admin`. When it is **Teacher**, `/` MUST redirect with 303 See Other to `/teacher`. Neither may show
  the home page.
- **FR-002**: `/admin` and `/teacher` MUST keep opening their first tabs, **Teachers** and **Students**,
  as milestones 6 and 9 define.
- **FR-003**: When the current role is **Student**, `/` MUST show the home page exactly as today: the
  greeting, the single **Student area** card, the notice when the data is unavailable, and the database
  line in the footer.
- **FR-004**: `/` MUST stay open to every role and to a signed-in person only. A signed-out visitor is
  sent to sign in, and a person with several roles and no current role gets the role choice, both as
  today.
- **FR-005**: The redirect MUST follow the current role only, never the set of roles a person holds.
- **FR-006**: Signing in, the role choice after sign-in, switching role from the user menu, the brand link
  in the top bar and the role choice opened by a person with one role MUST keep sending the person to `/`
  when no return address is given. By FR-001 they then land in the area. None of these flows may gain a
  role-specific address of its own.
- **FR-007**: A sign-in or role choice with a return address MUST keep going to that address, as today.

**The Staff area**

- **FR-008**: `/staff` MUST no longer be served. It MUST answer **404 Page not found** to every role and to
  a signed-out visitor, with the same page as any other unknown address.
- **FR-009**: No page may link to `/staff` or name the Staff area, in either language.

**The database line**

- **FR-010**: The footer of every page of the administrator area MUST show the database line, with the
  content and look the home page footer has today. This covers every tab, every page reached from a tab,
  pages shown again with form errors, and the component gallery wherever it is served.
- **FR-011**: The footer of the teacher area pages MUST NOT show the database line.
- **FR-012**: The student's home page MUST keep its database line (FR-003).
- **FR-013**: If reading the database line fails on an administrator area page, the page MUST render
  without the line. The error MUST be logged by type and message only, never with the database address,
  as on the home page today. The line MUST NOT fail the page.

**Links back**

- **FR-014**: On the profile page and the error page, when the current role is **Administrator**, the
  back link MUST read "Back to the administrator area" («Назад до розділу адміністратора») and lead to
  `/admin`.
- **FR-015**: On the same pages, when the current role is **Teacher**, the back link MUST read "Back to the
  teacher area" («Назад до розділу педагога») and lead to `/teacher`.
- **FR-016**: In every other case the back link MUST stay "Back to the home page", leading to `/`. That
  covers a student, a person with several roles and no current role, a signed-out visitor, and a person
  whose current role is not read: an unknown address, or a session that cannot be read.
- **FR-017**: The link on the "data erased" page MUST NOT change.
- **FR-018**: The new labels MUST follow the UI guidelines' "Back to {parent}" pattern and the Ukrainian
  glossary's area names («Розділ адміністратора», «Розділ педагога»), in the existing back-link
  components.

**Cleanup**

- **FR-019**: The Staff area's declaration and handler MUST be removed. So MUST every helper, template
  block, page value and style rule left with no use once administrators and teachers no longer see the
  home page. The home page and the area placeholder page MUST stay, because the student uses them.
- **FR-020**: Every message no longer used MUST be removed from the message template and from both the
  Ukrainian and English catalogues, which are then compiled again. This covers the Staff area's title
  ("Staff area") and description ("Pages shared by administrators and teachers.") and the administrator
  and teacher area card descriptions. The catalogues MUST keep no unused or obsolete entries, as the
  milestone 12.5 catalogue checks require.
- **FR-021**: The two new back-link labels MUST be in both catalogues, translated.
- **FR-022**: Every comment and docstring that says the home page links to the administrator, teacher or
  staff area, or that `/` shows a home page to every role, MUST be corrected.
- **FR-023**: Tests of `/staff` and of the administrator's and teacher's home page cards MUST be deleted or
  rewritten for the new behaviour. None may be skipped or left behind. The access tables of the
  access-control tests MUST drop `/staff`. Every test helper or fixture left without a user MUST be
  deleted. Only the test that `/staff` answers 404 may mention `/staff`.
- **FR-024**: Nothing under the application, the README or the documentation MUST mention `/staff` or the
  Staff area, except the milestones document's description of this milestone. Specifications of
  delivered milestones are records of their time and MUST NOT be edited.

**Tests and documentation**

- **FR-025**: Every changed route MUST have tests of allowed and denied access per role, as the
  constitution requires (Principle III). For `/` that means the redirect for an administrator and a
  teacher, the home page for a student, and sign-in for a signed-out visitor. For `/staff` it means 404
  for every role and for a signed-out visitor.
- **FR-026**: The whole test suite MUST pass on both database engines, and the style checks MUST pass.
  The pipeline's smoke checks of the built image, which sign in as an administrator and read the
  database line, MUST follow the new landing and keep passing.
- **FR-027**: The README MUST describe the new behaviour: where administrators and teachers land, the
  home page as the student's page, the database line, and the areas paragraph without the Staff area.
- **FR-028**: The UI guidelines MUST describe the new behaviour: the top bar (the brand link leads to `/`,
  which opens the current role's area), the footer rule (where the database line appears), and every
  example that names the home page or the Staff area.
- **FR-029**: The product and technical requirements MUST be checked for mentions of the home page or the
  Staff area and updated if they have any.
- **FR-030**: In the Delivered section of the milestones document, every summary whose behaviour this
  milestone changes MUST be updated. This includes milestone 3's database line on the home page.
  Milestone 12.6 itself moves to Delivered once it ships, compacted like the others.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator or a teacher with one role reaches the first tab of their area after
  signing in with zero intermediate pages, down from one today.
- **SC-002**: All five ways into the application that end at `/` (sign-in, role choice, role switch, brand
  link, role choice with one role) take an administrator or a teacher to their own area in 100% of
  cases.
- **SC-003**: `/staff` answers **Page not found** for all four kinds of visitor (administrator, teacher,
  student, signed out), and 0 pages link to it.
- **SC-004**: The Staff area's name appears 0 times on any page in either language, and the message
  catalogues hold 0 unused, obsolete or untranslated entries.
- **SC-005**: The database line is on 100% of administrator area pages and 0% of teacher area pages, and
  an administrator area page renders in 100% of cases when only reading the line fails.
- **SC-006**: A student sees the same home page as before the milestone, with no visible difference.
- **SC-007**: The back link on the profile and error pages names the right destination for each of the
  four cases (administrator, teacher, student, no chosen role), in both languages.
- **SC-008**: The full test suite passes on both database engines, with 0 tests skipped because of this
  milestone.

## Assumptions

- **No real users yet.** The product requirements say no real users take part until every milestone is
  done. So `/staff` simply becomes unknown, with no redirect for old bookmarks.
- **Students are out of scope.** Where a student lands is decided when the student's side is built
  (milestone 13 or later). This milestone leaves the student's home page as it is.
- **The home page's wording for students stays.** That includes the "data unavailable" notice, whose text
  still mentions question data although the home page has shown no questions since milestone 11.
- **One redirect to the first tab is acceptable.** `/` redirects to the area's address, and the area's
  address redirects to its first tab, as it does today. Whether `/` may go straight to the first tab is
  left to the plan, provided the person lands on the same tab.
- **The administrator area layout is the one place for the line.** Every administrator area page,
  including the component gallery, shares that layout, so the line appears on all of them together.
- **No data changes.** No table, column or migration is added or changed.

## Dependencies

- **Milestone 12.5** (merged): every new or changed message goes through the catalogues in both languages,
  and the catalogue checks fail on unused or untranslated entries.
- **Milestone 5**: the current role, the role choice and the role switch, whose return address stays `/`.
- **Milestones 6 and 9**: `/admin` and `/teacher` open their first tabs.
- **Milestones 3 and 10**: the database line, its failure handling and its place in the footer.

## Out of Scope

- The student's landing page and the student area (milestone 13 or later).
- Any new shared page for administrators and teachers.
- Rewording the student's home page, including its "data unavailable" notice.
- Editing the specifications of delivered milestones.
- Any change to sign-in, sessions, roles or access rules beyond where `/` leads.
