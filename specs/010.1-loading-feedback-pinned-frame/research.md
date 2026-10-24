# Research: Feedback While a Page Loads, and a Frame That Stays in View (Milestone 10.1)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

The spec left no `NEEDS CLARIFICATION`. The decisions below settle how to build it inside the
constitution (Principle II: minimal script, no build step, no new dependency; components, gallery
and guidelines first) and the milestone 10 checks (`tests/unit/test_stylesheet.py`).

Measurements were taken on 2026-10-24 in Chromium (Playwright, ad hoc) against a local run of
`main` at `5ab91a3`.

---

## R1. One deferred script with three document-level listeners

**Decision**: one new file, `app/static/js/loading-feedback.js`, loaded by `layouts/base.html` as
`<script src="/static/js/loading-feedback.js" defer></script>` in the `<head>`, outside the
`scripts` block, so every page gets it, including the sign-in page and error pages. It listens on
`document` for `click` (links), `submit` (forms) and `pageshow` (Back and Forward). It holds one
piece of state: the pending page load (its timer, and the form and button it concerns). It has no
imports, makes no requests and uses no library.

**Rationale**: event delegation on `document` covers every link and form, now and in later
milestones, with no markup on the pages (FR-019). `click` on a link fires for the mouse, touch and
the Enter key. `submit` fires for a button, for Enter in a field, and for `requestSubmit()` from
`auto-submit.js`. It does **not** fire when the browser refuses an invalid form, so FR-003's last
case needs no code. In the HTML navigation model, the old document stays active while a page load
is pending: its timers run and it keeps painting until the next page's response arrives. That is
what makes a delayed bar possible without a single-page architecture. The quickstart (§3) checks
this in each browser, because headless Playwright cannot capture it (R11).

**Alternatives considered**:

- **`beforeunload` / `pagehide`**: these fire too late (only after the browser has the response) or
  for the wrong reasons (reloads, typed addresses). A `beforeunload` listener also keeps a page out
  of the back/forward cache in some browsers, which would break FR-011's restore.
- **The Navigation API (`navigate` event)**: it would catch every navigation in one place, but it is
  not in every supported browser yet.
- **HTMX boosted links**: out of scope (spec FR-024), and they change how pages load.
- **Merging `auto-submit.js` into the new script**: rejected. It is a different behaviour, loaded
  only by the page that needs it. The milestone asks for one script for the bar and the busy
  button, not for a single script overall.

---

## R2. Which link clicks start a page load

**Decision**: a `click` starts the pending state only when **all** of these hold:

1. the event was not already cancelled (`defaultPrevented` is false);
2. it is a primary-button click with no modifier key: `button === 0` and no `ctrlKey`, `metaKey`,
   `shiftKey` or `altKey`. A middle click fires `auxclick`, not `click`, so it never arrives here;
3. the target is inside an `<a href>` with no `download` attribute and no `target` other than
   `_self`;
4. the link's URL has the same origin as the page, so another site, `mailto:` and `tel:` start
   nothing;
5. it is not an in-page move: a URL with a `#fragment` whose path and query equal the current
   page's starts nothing. A link to the current page **without** a fragment reloads it, so it does
   start (spec edge case).

**Rationale**: this is the milestone's exclusion list (spec FR-003), turned into checks the
browser already exposes. Links styled as buttons (`link_button`, `role="button"`) are `<a>`
elements, so they are covered.

---

## R3. Forms: block a second send without `disabled`; mark the button with `aria-busy`

**Decision**:

- **Which forms**: on `submit` (not cancelled, and not aimed at another window through `target` or
  `formtarget`), the script reads the method, the submitter's `formmethod` first.
  - **POST forms** (every form that changes something) are marked as sending. Any later `submit`
    event for the same form is cancelled with `preventDefault()` until the next page arrives. That
    covers the same button, another button of the form, and Enter in a field (FR-007).
  - **GET forms** (today only the self-submitting lists of `chained_lists`) behave like links. A
    newer choice sends again, and the browser drops the older load (spec FR-007, second sentence).
- **The busy button**: after 200 ms, the submitter (`event.submitter`, which is the form's default
  button when Enter was pressed) gets `aria-busy="true"`. A form sent with no submitter (a list)
  shows only the bar (FR-008).
- **Never `disabled`**: the browser builds the form data right *after* the `submit` event. A
  `disabled` button drops out of it, which would break the role switch (`name="role"`) and the theme
  switch (`name="theme"`) (FR-010). `aria-busy` leaves the value in. Pico already gives
  `[aria-busy=true]` buttons `pointer-events: none` and the spinner, and the `preventDefault()`
  guard covers the keyboard.

**Rationale**: `aria-busy` is only an attribute, so it has no effect on the form data. `disabled`
does: a disabled control is left out of it. The quickstart checks the role switch and the theme
switch in a real browser. The guard sits on the form, so it does not depend on which control the
person uses.

**Alternatives considered**:

- **Setting `disabled` in a `setTimeout(0)`**: it works, but a double click can land before it runs,
  and a test would need a real browser to prove it does not drop the value.
- **Disabling every button on the page**: it would block **Log out** and the user menu while a slow
  form is pending, which the spec keeps working (edge case "several forms").
- **A server-side idempotency token**: it would protect against double posts from any client, but
  it is a change in fields and stored data, which the milestone excludes (FR-022).

---

## R4. The 200 ms delay, and the reset on Back and Forward

**Decision**: one `setTimeout(show, 200)` starts the pending state. `show` reveals the bar and, for
a form, sets `aria-busy` on its submitter. If the next page arrives first, the old document is
discarded with the timer still pending, so nothing is ever shown (FR-002, SC-001). A new link or
form while one is pending restarts the timer: the latest load is the one shown.

On `pageshow` with `event.persisted` (the page came back from the back/forward cache), the script
clears the timer, hides the bar, removes `aria-busy` from the button it marked, and forgets the
sending form (FR-011). A page that comes back *without* the cache is loaded fresh, so it is clean
already.

**Rationale**: the back/forward cache restores a page exactly as it was frozen, bar and busy
button included. `pageshow` with `persisted` is the one event every supported browser fires for
that.

**Alternative considered**: hiding everything on `pagehide`. It is rejected because some browsers
take the cache snapshot after `pagehide` and some before, while `pageshow` is reliable.

---

## R5. The loading bar: hanging under the frame, indeterminate, still under reduced motion

**Decision**:

- **The component**: `loading_bar(active=False)` in `components/frame.html` emits
  `<div class="loading-bar" aria-hidden="true" hidden></div>`. `active=True`, used only by the
  gallery, leaves out `hidden`. The script toggles `hidden`. No state class is added at run time, so
  the "every class is used" check stays meaningful.
- **Position**: the bar is the last child of the frame (R7). It is positioned absolutely at
  `top: 100%`, so it hangs **just under** the frame's bottom edge across the full width:
  - it does not hide the current tab's underline, which is the same primary colour and thickness;
  - against the page background it has a strong contrast (light `#1f56d6` on `#f4f6fb`, dark
    `#6c9cff` on `#0d1424`). The light primary on the deep blue top bar (`#16337a`) would not.
- **Thickness**: `--sc-border-accent` (0.25 rem), the same as the tab underline. There is no new
  colour or size.
- **Motion**: a primary segment, about a third of the width, moves left to right on a 1.5 s loop.
  That is an indeterminate bar, because the application does not know how long the server will take.
  Under `prefers-reduced-motion: reduce`, the whole track is shown filled and still (FR-005). Pico's
  own reduced-motion rule is not relied on: it shortens animations instead of stopping them.
- **Frame out of view** (a screen less than 600 px tall, scrolled down; FR-006): when `show` runs and
  the frame's bottom edge is above the screen, the script sets `data-detached` on the bar. CSS then
  fixes it to the top edge of the screen. If the person scrolls during the wait, the bar does not
  follow; the wait is short.
- **Assistive technology**: it is `aria-hidden`, as the spec assumes; the busy button carries the
  state.

**Rationale**: these are the smallest markup and the fewest tokens that meet FR-001–FR-006. The guidelines record
the bar as the one moving element allowed by "Calm and focused" (FR-018).

**Alternatives considered**:

- **A bar fixed at the top edge of the screen**: this is the usual pattern, but it covers the top
  bar's edge and contradicts "along the bottom edge of the frame".
- **A determinate bar with fake progress**: it suggests knowledge the application does not have.

---

## R6. The busy spinner in the button's own colour

**Decision**: `app.css` redraws Pico's busy spinner for buttons as a `mask` of Pico's own
`--pico-icon-loading` filled with `currentColor`, and sets `filter: none`.

**Rationale**: Pico colours the spinner with `filter: brightness(0) invert(1)` on every non-outline
button, which makes it white. The application's secondary buttons (the theme switch, the role
switch, **Log out**, **Cancel**-style actions) use a white surface background in the light theme,
so a white spinner would be invisible there. In the dark theme, the primary button's text is dark
(`--sc-on-primary` `#0d1424`), and a white spinner would clash with it. `currentColor` follows each
button kind in both themes. No new colour is needed, and `pico.min.css` is not edited.

**Alternative considered**: one `filter` per button kind and theme. That is six rules that drift
from the tokens.

---

## R7. The pinned frame: one sticky wrapper, only on screens at least 600 px tall

**Decision**:

- **The wrapper**: `layouts/base.html` wraps the top bar, the `tabs` block and the loading bar in
  `<div class="frame">`. The `<header class="top-bar">` stays the banner landmark: a `<header>`
  that is not inside `main`, `nav`, `section`, `article` or `aside` is still the page banner.
- **The sticky rule**: `position: sticky; top: 0` applies to `body > .frame` only, inside
  `@media screen and (min-height: 600px)`.
  - The gallery's sample frames (inside `main`) never stick.
  - Print (not `screen`) and short screens (FR-014) keep today's flow.
- **The page still scrolls as a whole** (FR-013): the document stays the only scroll container.
  `body` keeps its flex column; a sticky flex item sticks against the viewport. Nothing gets
  `overflow` or a fixed height, so the address bar still hides on a phone, pull-to-refresh, scroll
  restoration on Back, keyboard scrolling and printing are untouched.
- **Stacking**: `z-index: 3` on the frame, above the cards' stretched links and the tables. The
  user menu panel (`z-index: 5`) lives inside the frame's stacking context. The skip link
  (`z-index: 10`, outside the frame) stays above it (US4-4).
- **Old selector**: `body > header.top-bar { padding-block: 0 }` existed only to cancel Pico's
  `body > header` padding. The top bar is no longer a child of `body`, so Pico's rule stops
  matching and that override is removed (the "every class is used" check is unaffected).

**Rationale**: sticky positioning is the only way to pin the frame without a separate scroll area or
a script, and it falls back to normal flow wherever it does not apply. The 600 px threshold is a
media query on the viewport's height in CSS pixels, so zooming in also unpins the frame (spec
assumption, WCAG reflow).

**Alternatives considered**:

- **`position: fixed` with a spacer**: it needs the frame's height, and it breaks print.
- **A scrolling `<main>`**: it breaks everything FR-013 keeps.
- **Hiding the frame on scroll down**: out of scope.

---

## R8. Targets never hidden: scroll padding from tokens, without a script

**Decision**:

- **Scroll padding**: inside the same media query,
  `html { scroll-padding-top: var(--sc-frame-clearance) }`, and
  `html:has(body > .frame .area-tabs) { scroll-padding-top: var(--sc-frame-clearance-tabs) }`.
  The browser keeps that much space above every target it scrolls to: a `#fragment` (the skip link,
  the error-summary links) and an element that receives keyboard focus (FR-015, WCAG 2.2 2.4.11).
- **The tokens**: they are defined in the token block. Each is the tallest measured frame at that
  breakpoint, rounded up with room to spare:

  | Frame | Measured (375 px) | Measured (≥ 768 px) | Token value |
  |---|---|---|---|
  | Top bar only | 69.5 px | 64 px | `--sc-frame-clearance: 5.5rem` (88 px) |
  | Top bar + tabs, tabs wrapped on a phone (after R9) | 158.5 px | n/a | `--sc-frame-clearance-tabs: 11rem` (176 px) below 768 px |
  | Top bar + tabs, one row | 118 px (414 px wide) | 113 px | `--sc-frame-clearance-tabs: 8rem` (128 px) from 768 px |

- **Labels above fields**: an error-summary link targets the field itself, but its label and error
  message sit above it. Form controls (`input`, `select`, `textarea`) get
  `scroll-margin-top: var(--sc-field-clearance)` (5 rem). The label and a two-line error stay below
  the frame too (US4-1).
- **Verified**: in Chromium with a 120 px sticky header and a 130 px padding, the topmost focused
  element after 30 Tab presses sat at 200 px, and `focus()` from a script also respected the
  padding. Firefox and Safari also apply scroll padding to focus and fragment scrolling, but this
  was not measured here; the quickstart checks both by hand.

**Rationale**: these are CSS only, so they work without JavaScript, matching the spec's "the pinned
frame does not depend on JavaScript". `:has()` is in every current browser, as the spec's supported
browsers require. A few spare pixels above a target cost nothing. A target under the frame fails the
spec.

**Alternatives considered**:

- **The script measures the frame** with a `ResizeObserver` and sets the padding exactly. This is
  more precise, but it adds a second mechanism and fails without JavaScript.
- **One fixed padding for all pages**: up to 100 px of empty space above targets on pages without
  tabs.

**Guard for later milestones**: the guidelines will say that a new tab, a longer tab label or a
taller top bar must be checked against these tokens at 360 px width.

---

## R9. Area tabs at the touch-target height on a phone

**Decision**: below 768 px, the area tab links' `min-height` drops from 3 rem to
`--sc-touch-target` (2.75 rem). From 768 px it stays 3 rem.

**Rationale**: at 375 px the administrator tabs ("Teachers" 72 px, "Educational institutions" 183
px, "Subjects" 65 px, plus two 24 px gaps, 368 px in total) do not fit the 343 px content width, so
they wrap onto two rows. They do not fit even with 16 px gaps (352 px). The pinned frame then
measured 166.5 px, 24.96 % of a 667 px screen. That meets SC-007 by a quarter of a pixel, and a
browser's font rendering could tip it over. At the touch-target height it measures 158.5 px
(23.8 %). The tabs keep the 44 px minimum touch target from milestone 10, and the labels do not
change. The screenshot review shows the change, and the guidelines record it.

**Alternatives considered**:

- **Tabs that scroll sideways on a phone**: milestone 10 chose wrapping, so that nothing scrolls
  sideways.
- **Shorter tab labels**: that is a change in messages (FR-022).
- **Unpinning the tabs on a phone**: that contradicts FR-012.

---

## R10. The user menu scrolls inside itself

**Decision**: `.user-menu-panel` gets
`max-height: calc(100dvh - var(--sc-frame-clearance))`, `overflow-y: auto` and
`overscroll-behavior: contain` (FR-016).

**Rationale**: the panel opens just below the 44 px summary inside the top bar. The top bar's
clearance token bounds the space above the panel, so the panel always ends on screen. `dvh` follows
the phone's changing address bar. `contain` stops a scroll at the menu's end from scrolling the page
under it. The rule applies whether the frame is pinned or not: when the menu is opened at the top of
the page, the geometry is the same.

---

## R11. Testing without a browser in the suite

**Decision**:

- **pytest checks what the server sends and what the stylesheet and script say**:
  - every kind of page loads the script once, `defer`, from `/static/`, and has the frame wrapper
    with the top bar, the tabs on area pages and a hidden, `aria-hidden` loading bar;
  - the gallery shows both components in their loading state;
  - the stylesheet keeps the sticky rule inside `@media screen and (min-height: 600px)`, the scroll
    padding and field margin from tokens, the reduced-motion rule and the menu's `overflow`;
  - the script exists, imports nothing, loads nothing, listens to `click`, `submit` and `pageshow`,
    and never sets `disabled`, which guards FR-010.
- **Behaviour in a real browser** is checked by hand from the quickstart, at phone and desktop
  widths, with DevTools network throttling to make pages slow. The checks run in Chrome, Firefox and
  Safari, plus one real phone.

**Rationale**: Playwright stays out of the project until milestone 16 (milestone 10 research D1).
An ad hoc Playwright run cannot stand in for the manual check either. Its screenshot waits for the
pending navigation to finish, so it cannot capture the in-between state that this milestone is
about. The static script checks are cheap regex checks. They guard the one regression with a
silent, serious effect (a dropped button value), not the whole behaviour.

---

## R12. Documents and governance

**Decision**:

- `docs/requirements/ui-guidelines.md` gains:
  - the loading bar and the busy button (§5 Frame, §6 Buttons);
  - the exception in §2 "Calm and focused";
  - the pinned frame, the height breakpoint and the clearance tokens (§4 Layout, §3 Tokens);
  - the phone tab height (§8);
  - the new checks (§10).
- The README's design section gains one bullet: the loading bar, the busy button and the pinned
  frame, and that pages get them from the base layout.
- `milestones.md` moves 10.1 to **Delivered** on delivery.
- No constitution amendment: Principle II already allows minimal JavaScript without a build step,
  and the components go through the library, the gallery and the guidelines first.

**Rationale**: these are the constitution's documentation gate and Principle II's
"library, gallery and guidelines first", applied to the two new components.
