# Feature Specification: Feedback While a Page Loads, and a Frame That Stays in View (Milestone 10.1)

**Feature Branch**: `010.1-loading-feedback-pinned-frame`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: milestone 10.1 of `docs/requirements/milestones.md` ("Feedback while a
page loads, and a frame that stays in view"), with the specification of milestone 10
(`specs/010-design-system-ui-guidelines/spec.md`, FR-018–FR-021) as reference for the page frame.

## Overview

Milestone 10.1 makes two small improvements to the page frame that milestone 10 introduced. It
changes how the application **responds while it works** and **what stays on screen**, not what it
**does**: addresses, fields, messages, access rules and stored data stay the same.

1. **Feedback while a page loads.** After a link or a button is pressed, the old page stays on screen
   with no sign that anything is happening until the server answers. That can take seconds, longer
   when the hosting has been idle, so people take the link for broken and press it again. After this
   milestone, a thin **loading bar** shows that the next page is on its way, and the button that sent
   a form becomes a **busy button** that cannot send it twice. Fast pages show neither.
2. **A frame that stays in view.** On long pages, the top bar and the area tabs scroll away, so
   reaching another tab means scrolling back up first. After this milestone, they stay at the top of
   the screen while the page scrolls, without changing how the browser scrolls, prints or goes back,
   and without ever hiding what the page moves to.

Both new patterns go into the component library, the component gallery and the UI guidelines before
any page uses them (constitution, Principle II).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A person sees that a slow page is on its way (Priority: P1)

Olena, a teacher, opens the application in the morning, when the hosting has been idle. She presses
the **Students** tab. The server takes four seconds to answer. A fifth of a second after her press, a
thin bar in the primary colour starts running along the bottom edge of the top bar and the tabs, and
it keeps running until the **Students** page appears. She waits instead of pressing the tab again.
Later in the day pages open at once, and she sees no bar at all.

**Why this priority**: People who see no response think the application is broken. This is the most
visible problem the milestone solves and helps every role on every page.

**Independent Test**: With the server slowed down, follow a link and submit a form; check that the bar
appears after about 200 ms and stays until the next page arrives. With the server at normal speed,
check that no bar appears. Check that a Ctrl-click, a middle click, a link to another site, a `#` link
and a form with an empty required field start nothing.

**Acceptance Scenarios**:

1. **Given** the next page takes longer than 200 ms to arrive, **When** a person follows a link to
   another page of the application, **Then** the loading bar appears 200 ms after the press and stays
   until the next page arrives.
2. **Given** the next page takes longer than 200 ms to arrive, **When** a person submits a form,
   **Then** the loading bar appears in the same way.
3. **Given** the next page arrives within 200 ms, **When** a person follows a link or submits a form,
   **Then** no loading bar appears at any moment.
4. **Given** a link to another page of the application, **When** it is opened in a new tab or window
   (Ctrl, Cmd or Shift click, middle click), **Then** the current page shows no loading bar.
5. **Given** a link to another site, or a link within the same page (such as the skip link or a link
   of the error summary), **When** it is followed, **Then** no loading bar appears.
6. **Given** a form with an empty required field, **When** the person presses its button and the
   browser refuses the form, **Then** no loading bar appears and the button stays usable.
7. **Given** one of the cascading lists that submits itself on change (region, institution, class),
   **When** the person picks another value and the next page is slow, **Then** the loading bar appears
   as for any other form.
8. **Given** reduced motion is turned on in the device settings, **When** the loading bar appears,
   **Then** it is shown without moving.
9. **Given** a person left a page while the bar was showing, **When** they come back to it with the
   browser's Back or Forward button, **Then** the page shows no loading bar.

---

### User Story 2 - A form is not sent twice (Priority: P1)

Mykola, an administrator, invites a teacher. The server is slow, and he presses **Send invitation**
again, then presses Enter in the email field. Nothing happens a second time: from his first press,
the button shows a spinner and cannot be pressed, and the form is sent once. When the next page
arrives, it shows the result of one invitation. He then switches role and theme from the user menu,
and both work as before.

**Why this priority**: A form sent twice can create two invitations, two records or two emails, and
counts twice against rate limits. Preventing it protects the data and the person's trust.

**Independent Test**: With the server slowed down, press a form's button several times and press
Enter in one of its fields; check that the server receives the form exactly once, that the button
shows a spinner after about 200 ms, and that it stays so until the next page arrives. Check that the
role switch and the theme switch still reach the role or theme that was pressed.

**Acceptance Scenarios**:

1. **Given** a form whose next page is slow, **When** the person presses its button, **Then** from
   that moment the form cannot be sent again, by that button, by another button of the same form or by
   pressing Enter in one of its fields.
2. **Given** the form was sent and the next page has not arrived within 200 ms, **When** the person
   looks at the button they pressed, **Then** it shows a spinner and is marked busy.
3. **Given** the next page arrives within 200 ms, **When** the form is sent, **Then** the button never
   shows a spinner.
4. **Given** a slow server, **When** the button is busy, **Then** it stays busy until the next page
   arrives, however long that takes; there is no time-out.
5. **Given** a form whose buttons each send their own value (the role switch, the theme switch),
   **When** a person presses one of them, **Then** the value of that button is sent, and the role or
   theme changes exactly as before this milestone.
6. **Given** a form that the server returns with errors, **When** the page with the errors arrives,
   **Then** its button is usable again.
7. **Given** a person left a page while a button was busy, **When** they come back to it with the
   browser's Back or Forward button, **Then** no button on the page is busy and every form can be sent.

---

### User Story 3 - Staff reach another tab without scrolling back up (Priority: P2)

Iryna, an administrator, scrolls to the bottom of a long list of teachers. She wants to open the
**Subjects** tab. The top bar and the area tabs are still at the top of the screen, so she presses
**Subjects** at once. On her phone, the same frame stays in view, the address bar still hides while
she scrolls, pull-to-refresh still works, and Back returns her to the same place in the list. When
she holds the phone sideways, the frame scrolls away as before, so the content keeps the small
screen.

**Why this priority**: It saves a scroll on every long page for staff and keeps the user menu always
in reach. It is valuable but not as urgent as the feedback that stops people pressing twice.

**Independent Test**: On a long administrator list at phone and desktop widths, scroll to the bottom
and check that the top bar and the area tabs are visible and work; check that the page scrolls as a
whole, that Back returns to the same scroll position and that printing shows the whole page. On a
screen less than 600 px tall, check that the frame scrolls away.

**Acceptance Scenarios**:

1. **Given** an area page longer than the screen, **When** the person scrolls down, **Then** the top
   bar and, below it, the area tabs stay at the top of the screen as one block.
2. **Given** a page outside an area (for example the home page or the profile), **When** the person
   scrolls down, **Then** the top bar stays at the top of the screen.
3. **Given** a pinned frame, **When** the person scrolls, **Then** the whole page scrolls, with no
   separate scroll area for the content: the keyboard scrolls the page, the address bar hides on a
   phone and pull-to-refresh works as before.
4. **Given** a person scrolled down a long list and opened another page, **When** they press the
   browser's Back button, **Then** they return to the same place in the list.
5. **Given** a long page, **When** it is printed, **Then** the print shows the whole content, with the
   frame once at the top and not repeated over the content.
6. **Given** a screen less than 600 px tall (such as a phone held sideways), **When** the person
   scrolls, **Then** the frame scrolls away with the page as before this milestone.
7. **Given** the user menu is opened from the pinned top bar, **When** the menu is taller than the
   space below the bar, **Then** the menu scrolls inside itself so that every item, **Log out**
   included, can be reached.

---

### User Story 4 - The pinned frame never hides what the page moves to (Priority: P2)

Andrii, a keyboard user, submits a teacher form with two errors. He follows the second link of the
error summary; the page moves to the field, and the field, its label and its error are fully visible
below the pinned frame. He presses Tab through a long table of actions, and every focused button
appears below the frame, never under it. On another page he uses the skip link, and the start of the
main content appears below the frame.

**Why this priority**: A pinned frame that covers the focused element makes the page unusable for
keyboard users and breaks the error summary of milestone 10. Pinning the frame may only ship together
with this guarantee.

**Independent Test**: On a form with errors, at phone and desktop widths, follow each link of the
error summary, use the skip link, and move focus with the keyboard through a long page; check that the
target is fully visible below the frame every time.

**Acceptance Scenarios**:

1. **Given** a form shown with errors, **When** a person follows a link of the error summary, **Then**
   the field it leads to is fully visible below the frame, with its label.
2. **Given** any page, **When** a person uses the skip link, **Then** the start of the main content is
   fully visible below the frame.
3. **Given** a long page, **When** a person moves focus with the keyboard to an element further down,
   **Then** the page scrolls so that the focused element is fully visible below the frame (WCAG 2.2,
   success criterion 2.4.11 "Focus Not Obscured (Minimum)").
4. **Given** the skip link has focus, **When** it becomes visible, **Then** it is shown above the
   frame, not under it.

---

### User Story 5 - A developer finds both new components in the gallery and the guidelines (Priority: P3)

A developer building milestone 11 opens `/admin/components` on a local run and finds the loading bar
and the busy button, each shown in its loading state, next to the other components. The UI guidelines
say when each appears, that pages get them from the base layout without doing anything, and that the
loading bar is the one moving element the calm design allows.

**Why this priority**: It keeps the component library and the guidelines complete for later
milestones, as the constitution requires, but people using the application do not see it.

**Independent Test**: Open the gallery on a local run and check that both components are shown in
their loading state; read the guidelines and check that both are described; run the automated token
and component check and check that it passes.

**Acceptance Scenarios**:

1. **Given** a local run, **When** an administrator opens the component gallery, **Then** it shows the
   loading bar and the busy button, each in its loading state, without starting any page load.
2. **Given** the UI guidelines, **When** a developer reads them, **Then** they describe the loading
   bar, the busy button and the pinned frame: when each applies, what starts nothing, and that pages
   get them from the base layout.
3. **Given** the templates and the stylesheet, **When** the automated token and component check runs,
   **Then** it passes.

---

### Edge Cases

- **The frame is out of view when the bar starts** (a screen less than 600 px tall, scrolled down):
  the loading bar is still visible, at the top edge of the screen.
- **A page without area tabs**: the loading bar runs along the bottom edge of the top bar.
- **The area tabs wrap onto a second line** on a narrow phone: the pinned block grows with them, and
  targets the page moves to are still fully visible below it.
- **The screen is rotated or the window is resized** across the 600 px height: the frame pins or
  stops being pinned to match, without a reload.
- **The page is zoomed in** so far that less than 600 px of height is left: the frame scrolls away
  with the page, so the content keeps the screen.
- **The user menu is open** while the page scrolls: it stays attached to the pinned top bar.
- **Enter is pressed in a field** of a form whose next page is slow: the default button of that form
  becomes the busy button.
- **A list that submits itself on change** has no button: only the loading bar shows. Changing the
  list again before the next page arrives starts another page load, which the browser handles as
  today.
- **Several forms on one page**: only the button of the form that was sent becomes busy; pressing a
  button of another form (for example **Log out**) still works and leads to its own page.
- **A link to the current page's own address** (for example the current tab) reloads the page and
  shows the loading bar like any other page load.
- **The server answers with an error page** ("access denied", "not found", a server error): that page
  is the next page, so the loading bar and the busy button end when it arrives.
- **The network fails**: the browser shows its own error page, so nothing of the old page stays.
- **The person stops the page load** with the browser's Stop button or Esc: the bar and the busy
  button may stay until the page is reloaded or another page is opened (see Assumptions).
- **A submission is cancelled before it is sent** (the browser refuses an invalid field): nothing
  starts, and the button stays usable.
- **JavaScript is off or the script fails to load**: links and forms work exactly as today, without
  the loading bar and the busy button. The pinned frame does not depend on JavaScript.
- **Light and dark theme**: the loading bar and the busy button are visible in both.

## Requirements *(mandatory)*

### Functional Requirements

#### Loading bar

- **FR-001**: When a person follows a link to another page of the application or submits a form, a
  thin loading bar in the primary colour MUST run along the bottom edge of the frame (the top bar, and
  the area tabs where the page has them) until the next page arrives.
- **FR-002**: The loading bar MUST appear only when the next page has not arrived within 200 ms of the
  link being followed or the form being sent. When the next page arrives within 200 ms, nothing MUST
  be shown.
- **FR-003**: The loading bar MUST NOT start for a link opened in a new tab or window (Ctrl, Cmd or
  Shift click, middle click), for a link that leaves the application (another site, an email link),
  for a link that only moves within the current page (`#…`, such as the skip link and the links of the
  error summary), or for a form the browser refuses because a field is invalid.
- **FR-004**: Lists that submit themselves on change MUST start the loading bar like any other form.
- **FR-005**: With reduced motion turned on in the device settings, the loading bar MUST be shown
  without moving.
- **FR-006**: The loading bar MUST be visible whenever it shows, in both themes: at the bottom edge of
  the frame, or at the top edge of the screen when the frame has scrolled out of view.

#### Busy button

- **FR-007**: From the moment a form that changes something is sent, the form MUST NOT be sent again,
  neither by the button that sent it, by another button of the same form, nor by pressing Enter in
  one of its fields. A list that submits itself on change only chooses what to show, like a link, so
  choosing again sends the newer choice.
- **FR-008**: When the next page has not arrived within 200 ms, the button that sent the form MUST
  show a spinner and be marked busy, so assistive technology announces it as busy. When pressing Enter
  sent the form, the button is the form's default button. A form sent with no button (a list that
  submits itself) MUST show only the loading bar.
- **FR-009**: The busy button MUST stay so until the next page arrives, with no time-out.
- **FR-010**: The value of the button that sent the form MUST still be sent with it, so the role switch,
  the theme switch and every other form behave exactly as before this milestone.

#### Back and Forward

- **FR-011**: A page restored with the browser's Back or Forward button MUST NOT show a loading bar or
  a busy button left over from before, and every form on it MUST be usable.

#### Frame in view

- **FR-012**: The top bar and, on area pages, the area tabs below it MUST stay at the top of the screen
  as one block while the page scrolls. This extends FR-018 and FR-020 of milestone 10.
- **FR-013**: The page MUST still scroll as a whole, with no separate scroll area for the content, so
  the browser behaves as before: the address bar hides on a phone, pull-to-refresh works, Back returns
  to the same place, the keyboard scrolls the page and printing shows the whole content.
- **FR-014**: On a screen less than 600 px tall, the frame MUST scroll away with the page as before
  this milestone. In print, the frame MUST NOT stay over the content.
- **FR-015**: The pinned frame MUST NEVER cover what the page moves to: after the skip link, a link of
  the error summary or moving focus with the keyboard, the target MUST be fully visible below the frame
  (WCAG 2.2, success criterion 2.4.11). The skip link, when it has focus, MUST be shown above the
  frame.
- **FR-016**: The user menu opened from the pinned top bar MUST scroll inside itself when it is taller
  than the space below the bar, so every item can be reached.

#### Components and guidelines

- **FR-017**: The loading bar and the busy button MUST be added to the component library, to the
  component gallery (`/admin/components`), each shown in its loading state, and to the UI guidelines,
  before any page uses them (constitution, Principle II).
- **FR-018**: The UI guidelines MUST describe the pinned frame (what is pinned, the 600 px rule, that
  targets stay visible below it) and MUST record the loading bar as the one moving element allowed by
  the "Calm and focused" principle (milestone 10, FR-002), shown only while a page loads and still
  with reduced motion.
- **FR-019**: Every page MUST get the loading bar, the busy button and the pinned frame from the base
  layout; no page MUST build them by hand or need any change of its own to use them.
- **FR-020**: The loading bar and the busy button MUST come from one small script loaded by the base
  layout on every page, with no build step and no new dependency.
- **FR-021**: Without JavaScript, links and forms MUST work exactly as today, only without the loading
  bar and the busy button.

#### Constraints and scope

- **FR-022**: Addresses, form fields, messages, access rules and stored data MUST NOT change.
- **FR-023**: The automated token and component check of milestone 10 MUST pass, and every test of
  milestones 1–10 MUST keep passing.
- **FR-024**: Making pages load faster (prefetching, boosted links, keeping the hosting awake),
  animated page transitions and hiding the frame while scrolling down MUST NOT be part of this
  milestone.

### Key Entities

No data is stored or changed. The milestone adds two components and changes the page frame:

- **Loading bar**: a thin bar in the primary colour along the bottom edge of the frame, shown while
  the next page is on its way and it takes longer than 200 ms.
- **Busy button**: the state of the button that sent a form, with a spinner and no further presses,
  until the next page arrives.
- **Pinned frame**: the top bar and, on area pages, the area tabs, kept together at the top of the
  screen on screens at least 600 px tall.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a real browser at phone and desktop widths, 100% of page loads that take longer than
  200 ms show the loading bar from about 200 ms after the press until the next page arrives, and 0
  page loads that finish within 200 ms show the bar or a spinner.
- **SC-002**: When a form's button is pressed 5 times and Enter is pressed in one of its fields while
  the next page is slow, the server receives the form exactly once.
- **SC-003**: 0 of these start the loading bar or a busy button: a Ctrl or Cmd click, a Shift click, a
  middle click, a link to another site, a `#` link, a form with an empty required field.
- **SC-004**: 100% of uses of the role switch and of the theme switch reach the role or theme that was
  pressed, as before this milestone.
- **SC-005**: 100% of pages restored with Back or Forward show no loading bar and no busy button.
- **SC-006**: On a long administrator list at 375 × 667 px and 1280 × 800 px, the top bar and the area
  tabs are visible at every scroll position, and another tab opens with one press from the bottom of
  the list, with no scrolling.
- **SC-007**: At 375 × 667 px, the pinned frame takes no more than a quarter of the screen height on
  every page.
- **SC-008**: 100% of targets of the skip link and of the error-summary links, and 100% of elements
  reached by moving focus with the keyboard, are fully visible below the frame.
- **SC-009**: On a screen less than 600 px tall, the frame scrolls away on 100% of pages; printing
  shows the whole content of 100% of pages.
- **SC-010**: 100% of pages load the script and have the top bar and the area tabs in one pinned
  block; the gallery shows both new components; the automated token and component check passes.
- **SC-011**: With JavaScript off, 100% of links and forms work as before this milestone; 0 addresses,
  form fields, messages or access rules change.

## Assumptions

- **"The next page arrives"** means the browser leaves the current page for the next one. Until then
  the current page stays on screen, as browsers do today.
- **The 200 ms delay** applies to both the loading bar and the spinner of the busy button, so a fast
  page shows nothing; blocking a second send starts at once, without the delay.
- **The spinner** is the busy indicator that the existing stylesheet (Pico.css) already provides for
  controls marked busy; no new spinner is drawn.
- **The loading bar is not announced** by screen readers, so a page load does not add noise; the busy
  button is announced as busy, and the browser's own page-load signals stay.
- **A stopped page load** (the browser's Stop button or Esc) is rare and has no reliable signal in
  every supported browser, so the bar and the busy button may stay until the page is reloaded or
  another page is opened. This follows from the milestone's "no time-out" rule.
- **No link or form leads to a download** or to a response that keeps the current page; if a later
  milestone adds one, that milestone decides how it opts out of the loading bar.
- **No part of a page is updated without loading a new page** today; such partial updates, when a
  later milestone adds them, are not page loads and are outside this milestone.
- **The 600 px height rule** uses the visible height of the browser window in CSS pixels, so zooming in
  far enough also lets the frame scroll away.
- **The loading bar's motion** is subtle and only shown while a page loads; it is the one exception to
  milestone 10's "nothing moves" rule, and the guidelines record it as such.
- **Supported browsers** are current versions of the major desktop and mobile browsers, as in
  milestone 10.

## Dependencies

- **Milestone 10**: the page frame (top bar, user menu, area tabs; FR-018–FR-021), the skip link, the
  error summary, the role and theme switches, the component library, the gallery, the UI guidelines
  and the automated token and component check that this milestone extends.
- **Milestone 9**: the cascading lists that submit themselves on change.
- **Milestones 5 and 10**: the role switch and the theme switch, whose behaviour must stay the same.
- **Later milestones**: every later page gets the loading bar, the busy button and the pinned frame
  from the base layout without any work of its own.

## Out of Scope

- Making pages load faster: prefetching, boosted links, keeping the hosting awake.
- Animated page transitions.
- Hiding the frame while scrolling down and showing it while scrolling up.
- A time-out or an error message for a page load that never finishes.
- Any change in addresses, fields, messages, access rules or stored data.
- A frontend build step or a new runtime dependency.
