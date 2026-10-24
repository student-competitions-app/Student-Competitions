---

description: "Task list for milestone 10.1: feedback while a page loads, and a frame that stays in view"
---

# Tasks: Feedback While a Page Loads, and a Frame That Stays in View (Milestone 10.1)

**Input**: Design documents from `/specs/010.1-loading-feedback-pinned-frame/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/components.md](./contracts/components.md),
[contracts/loading-script.md](./contracts/loading-script.md), [quickstart.md](./quickstart.md)

**Tests**: required. Constitution Principle III makes tests non-negotiable, and the plan names the
test modules (plan "Testing", quickstart §1).

- **Markup**: pages are queried through `tests/html.py`, never by literal markup.
- **The script and the stylesheet**: these are read as text, in the style of
  `tests/unit/test_stylesheet.py`.
- **Engines**: integration tests run on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL` is
  set (the local `sc-pg` container).
- **Browser behaviour**: checked by hand from [quickstart.md](./quickstart.md) §2–§4. Playwright is
  not added before milestone 16.

**Organization**: tasks are grouped by user story (US1–US5 in spec.md).

1. **Foundational first**: the two new components, their tokens, the gallery section and their
   guidelines entries come before the layout uses them (constitution Principle II, FR-017).
2. **US1 and US2** build the script.
3. **US3 and US4** pin the frame. US4 must ship with US3 (spec US4, "Why this priority").
4. **US5** completes the gallery tests and the guidelines.

**Reference implementation**: read these before starting, and match their style, naming and
comment density:

- `app/static/js/auto-submit.js`: a short leading comment and plain DOM code;
- `app/templates/components/frame.html` and `app/templates/components/button.html`: the macro
  docstrings and the `_attrs`/`attrs` handling;
- `app/static/css/app.css`: section comments naming the FR, tokens only;
- `tests/unit/test_stylesheet.py`, `tests/integration/test_layout.py` and
  `tests/integration/test_component_gallery.py`.

**Rules for every task** (plan Constraints, FR-020–FR-023):

- **No behaviour change**: addresses, methods, form field names, status codes, messages, access
  declarations and stored data stay exactly as they are.
- **Tokens only**: no literal colour or `px` length outside the token block in `app.css`. The only
  literal media queries are `768px`, `1024px` and the new `(min-height: 600px)`.
- **Classes**: no inline `style`. Every class used is defined, and every class defined is used.
- **Nothing from elsewhere**: no new dependency, nothing loaded from another site, and
  `pico.min.css` is never edited.
- **The script never sets `disabled`, `readonly` or `inert`** (FR-010).
- **Suite green**: after each task, `uv run pytest` passes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: the user story the task belongs to (US1–US5)

---

## Phase 1: Setup

**Purpose**: confirm the starting point.

- [ ] T001 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest` on branch `010.1-loading-feedback-pinned-frame` (with `TEST_POSTGRES_URL` set if the `sc-pg` container is running). Record in `specs/010.1-loading-feedback-pinned-frame/pr-notes.md` (new file, a heading "Baseline" and the pass counts) that the milestone 10 suite is green before any change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the two new components, their tokens, their gallery entries, their guidelines entries
and the frame wrapper. Principle II requires the library, the gallery and the guidelines before any
page uses a new pattern.

**⚠️ CRITICAL**: no user story work can begin until this phase is complete.

- [ ] T002 Add three tokens to the token block of `app/static/css/app.css` (between `/* == Tokens == */` and `/* == End of tokens == */`), per [data-model.md §1](./data-model.md#1-new-design-tokens-appstaticcssappcss-token-block):
  - **In the light `:root` block**, each defined once: `--sc-frame-clearance: 5.5rem;`, `--sc-frame-clearance-tabs: 11rem;` and `--sc-field-clearance: 5rem;`.
  - **In a `@media (min-width: 768px) { :root { … } }` block inside the token block**: `--sc-frame-clearance-tabs: 8rem;`. Reuse such a block if one exists; otherwise add one next to the existing `1024px` block.
  - **Comment**: a short note naming research R8 and saying that each value is the tallest measured frame at that breakpoint, with room to spare.
  - **Dark theme**: these tokens are lengths, so they need no dark values.
  - **Check**: `tests/unit/test_stylesheet.py::test_tokens_are_defined_once` stays green.
- [ ] T003 [P] Add the macro `loading_bar(active=False)` to `app/templates/components/frame.html`, per [contracts/components.md §2](./contracts/components.md#2-loading_baractivefalse-componentsframehtml-new):
  - **Output**: `<div class="loading-bar" aria-hidden="true" hidden></div>`. With `active=True`, the `hidden` attribute is left out.
  - **Docstring**: in the `{#- … -#}` style of the file. It says that the layout renders the bar as the frame's last child, that the gallery passes `active=True`, that only `loading-feedback.js` changes `hidden` and `data-detached`, and it names the source (milestone 10.1 FR-001–FR-006, research R5).
  - **Top-of-file comment**: extend it to mention 10.1.
- [ ] T004 [P] Add the parameter `busy=False` as the last parameter of `button(...)` in `app/templates/components/button.html`, per [contracts/components.md §3](./contracts/components.md#3-button-busyfalse-componentsbuttonhtml-new):
  - **Output**: with `busy=True` the button gets `aria-busy="true"`. Nothing else changes, and the button never gets `disabled`.
  - **Comment**: the attribute's comment says that pages never pass `busy`, that the script sets `aria-busy` in use, and that the parameter exists for the gallery (FR-008, FR-010).
- [ ] T005 Add the component styles to `app/static/css/app.css`, near the frame section, with comments naming milestone 10.1 FR-001–FR-008 and research R5 and R6. Use only tokens. Per [contracts/components.md §2–§3](./contracts/components.md):
  - **`.frame`**: `position: relative`.
  - **`.loading-bar`**: `position: absolute; inset-inline: 0; top: 100%; height: var(--sc-border-accent); overflow: hidden; pointer-events: none`.
  - **`.loading-bar::before`**: `content: ""`, a block with `background: var(--sc-primary)`, height 100% and width about a third, animated by a new `@keyframes loading-bar` that moves it only with `transform: translateX(…)` from fully left of the track to fully right. The loop takes `1.5s`, `ease-in-out`, `infinite`.
  - **`.loading-bar[data-detached]`**: `position: fixed; top: 0`.
  - **`@media (prefers-reduced-motion: reduce)`**: `.loading-bar::before { animation: none; width: 100%; transform: none; }` (FR-005).
  - **`@media print`**: `.loading-bar { display: none; }`.
  - **The busy spinner**: `:is(button, [type="submit"])[aria-busy="true"]::before { background-image: none; background-color: currentColor; -webkit-mask: var(--pico-icon-loading) center / 1em no-repeat; mask: var(--pico-icon-loading) center / 1em no-repeat; filter: none; }`. The selector must be at least as specific as Pico's `[aria-busy=true]:not(input,select,textarea):is(button,…):not(.outline)::before` rule. Increase specificity with `:not(.outline, .contrast)` or similar if needed, so the white `filter` never wins (research R6). Check it in light and dark on a primary, a secondary (`.secondary`) and a destructive (`.destructive`) button.
  - **Check**: `uv run pytest tests/unit/test_stylesheet.py` passes. `.frame` and `.loading-bar` must be used in a template by T006 and T007, so run it after them if `test_every_app_css_class_is_used` fails in between.
- [ ] T006 Add the gallery section to `app/templates/pages/admin/components.html`, per [contracts/components.md §5](./contracts/components.md#5-gallery-pagesadmincomponentshtml-new-section):
  - **Imports**: add `loading_bar` to the existing `components/frame.html` import.
  - **Placement**: insert `<section id="loading" aria-labelledby="loading-heading">` right after the `#frame` section, with `<h2 id="loading-heading">Loading feedback</h2>`.
  - **"Loading bar"**: `<h3>Loading bar</h3>`, then `<div class="frame">{{ top_bar(one_role_user, teacher_role, [teacher_role]) }}{{ loading_bar(active=True) }}</div>`.
  - **"Busy button"**: `<h3>Busy button</h3>`, then `<div class="button-row">` holding `button("Send invitation", busy=True)`, `button("Dark", kind="secondary", small=True, busy=True)` and `button("Delete", kind="destructive", busy=True)`. These are **not** inside any `<form>`.
  - **Section text**: one short sentence under the heading, in the plain style of the other sections: these appear only while the next page is on its way; pages never draw them.
- [ ] T007 Wrap the frame in `app/templates/layouts/base.html`, per [contracts/components.md §1](./contracts/components.md#1-layout-skeleton-layoutsbasehtml-replacing-milestone-10-12):
  - **Import**: change it to `{% from "components/frame.html" import top_bar, loading_bar with context -%}`.
  - **Wrapper**: replace the two lines `{{ top_bar() }}` and `{% block tabs %}{% endblock %}` with `<div class="frame">`, holding `{{ top_bar() }}`, `{% block tabs %}{% endblock %}` and `{{ loading_bar() }}`, then `</div>`.
  - **No script yet**: the `<script>` tag is added in T013.
  - **Remove** from `app/static/css/app.css` the rule `body > header.top-bar { padding-block: 0; }`. The top bar is no longer a child of `body`, so Pico's `body > header` padding no longer applies. Fix its comment block so that the following `.top-bar` rule keeps its FR-018 comment.
  - **Check**: `uv run pytest` passes. `tests/html.py` already finds the `header` and the `nav` at any depth.
- [ ] T008 [P] Add the two components to `docs/requirements/ui-guidelines.md`:
  - **In §5 "Frame (`components/frame.html`)"**: a bullet for **`loading_bar(active=False)`**. It is rendered by the layout as the frame's last child and never called by a page. It is a thin primary line hanging under the frame, shown by the script 200 ms after a link to another page or a form submit, and still under reduced motion. The gallery shows it active.
  - **In §5 "Buttons"**: a bullet for **`button(…, busy=True)`**. It renders `aria-busy="true"` and Pico's spinner, redrawn in the button's text colour. Pages never pass it; the script marks the button that sent a form. A busy button is never `disabled`, so its value is still sent.
  - **Gallery links**: link both entries to `/admin/components#loading`, in the style of the existing `_Gallery_:` lines.

**Checkpoint**: the gallery shows both components. Every page renders the `.frame` wrapper with a
hidden bar, and nothing behaves differently yet.

---

## Phase 3: User Story 1 - A person sees that a slow page is on its way (Priority: P1) 🎯 MVP

**Goal**: following a link to another page of the application or submitting a form shows the
loading bar after 200 ms, until the next page arrives. Excluded cases start nothing, reduced motion
shows the bar still, and Back and Forward never restore a leftover bar.

**Independent Test**: [quickstart.md §2](./quickstart.md#2-loading-bar-and-busy-button-us1-us2),
rows 2.1–2.5 and 2.8–2.11, plus the automated checks below.

### Tests for User Story 1

- [ ] T009 [P] [US1] Create `tests/unit/test_loading_script.py`:
  - **Docstring**: in the style of `tests/unit/test_stylesheet.py`, naming specs/010.1 FR-001–FR-011, FR-020 and research R1–R4. It says that the script is read as text, because the suite has no browser before milestone 16.
  - **`SCRIPT`**: `(APP / "static" / "js" / "loading-feedback.js").read_text()`.
  - **`test_it_is_a_plain_script`**: no `import ` or `export ` statement, and no `fetch(`, `XMLHttpRequest`, `sendBeacon`, `localStorage`, `sessionStorage` or `document.cookie`.
  - **`test_it_names_no_other_site`**: no `http://`, `https://` or `//` URL in a string literal.
  - **`test_it_listens_for_links_forms_and_restores`**: `addEventListener("click"`, `addEventListener("submit"` and `addEventListener("pageshow"` each appear, and `persisted` appears.
  - **`test_the_delay_is_200_ms`**: the source contains `200`.
  - **`test_it_never_disables_anything`**: there is no `disabled`, `readonly` or `inert` as an assignment target, a `setAttribute` argument or a `toggleAttribute` argument. Use a regex on `\.(disabled|readOnly|inert)\s*=` and `(set|toggle)Attribute\(\s*["'](disabled|readonly|inert)`.
  - **`test_it_stays_small`**: at most 120 non-blank lines (contract: about 80).
  - **Expect**: these fail until T012.
- [ ] T010 [P] [US1] Extend `tests/integration/test_layout.py` with page-frame tests. Update the module docstring to name specs/010.1 FR-001, FR-012, FR-019 and FR-020 and contracts/components.md §1.
  - **`PAGE_KINDS`**: a list of `(client fixture, path)` pairs:
    - anonymous `/login`;
    - anonymous `/no-such-page` (the 404);
    - anonymous `/data-deletion`;
    - administrator `/`;
    - administrator `/admin/subjects`;
    - administrator `/profile`;
    - a teacher (`client_as(TEACHER_EMAIL)`) on `/teacher/students`.
  - **`test_every_page_loads_the_script_once`**: for each kind, the `script` elements whose `src` is `/static/js/loading-feedback.js` are exactly one, with `defer` and inside `<head>`. Use `html.parse(body)`, find `head`, then `find_all("script")`. Also `client.get("/static/js/loading-feedback.js")` returns 200 with a JavaScript content type.
  - **`test_every_page_has_one_frame_with_a_hidden_bar`**: for each kind there is exactly one element with class `frame` that is a direct child of `body`. Its children, in order, are the `header` with class `top-bar`, then a `nav` with class `area-tabs` on `/admin/subjects` and `/teacher/students` only, then a `div` with class `loading-bar`. The bar has `hidden` and `aria-hidden="true"`.
  - **Expect**: the frame test passes after T007; the script test fails until T013.
- [ ] T011 [US1] Update `tests/integration/test_admin_area.py::test_tabs_are_plain_links`. Milestone 6 FR-003 asserted that the page has no script at all; milestone 10.1 adds the base layout's `loading-feedback.js` to every page (FR-020).
  - **Keep**: the tab row has no `form` and no `hx-*` attribute.
  - **Replace** `html.parse(body).find_all("script") == []` with: the page's only `script` is `{"src": "/static/js/loading-feedback.js", "defer": ""}`.
  - **Docstring**: add one line saying that the tabs still work without the script (FR-021).
  - **Search**: look in `tests/` for any other assertion of "no script" on a page (`find_all("script")`) and adapt it the same way, without weakening what it checks about HTMX or forms.

### Implementation for User Story 1

- [ ] T012 [US1] Create `app/static/js/loading-feedback.js`, per [contracts/loading-script.md](./contracts/loading-script.md) §1, §2, §4 and §5 (bar only; the form guard and the busy button come in T016). It is a plain script, with no module syntax:
  - **Leading comment**: a two-to-three-line comment in the style of `auto-submit.js`. It shows a thin bar under the frame when the next page takes longer than 200 ms, marks the button that sent a form as busy, and keeps a form from being sent twice. Without JavaScript, links and forms work as before.
  - **State**: `const DELAY = 200;`, and one `let pending = null;` holding `{ timer, form, button }`.
  - **`bar()`**: returns `document.querySelector("body > .frame > .loading-bar")`. It may be `null`; every use must tolerate that.
  - **`start(form, button)`**: clears any existing `pending.timer`, then sets `pending = { form, button, timer: setTimeout(show, DELAY) }`.
  - **`show()`**:
    - if the bar exists: if `document.querySelector("body > .frame").getBoundingClientRect().bottom <= 0`, set `data-detached`, otherwise remove it; then `bar.hidden = false`;
    - for the form case (T016): `if (pending.button) pending.button.setAttribute("aria-busy", "true")`.
  - **`click` listener on `document`**: start only when every condition of contract §2 holds:
    1. `!event.defaultPrevented`;
    2. `event.button === 0` and none of `ctrlKey`, `metaKey`, `shiftKey` or `altKey`;
    3. `const link = event.target.closest("a[href]")` exists, has no `download` attribute, and `!link.target || link.target === "_self"`;
    4. `const url = new URL(link.href)` has `url.origin === location.origin`;
    5. not (`url.hash && url.pathname === location.pathname && url.search === location.search`).

    Then call `start(null, null)`.
  - **`submit` listener on `document`**: for now, if `!event.defaultPrevented`, and the effective target (`event.submitter?.formTarget || event.target.target`) is empty or `_self`, call `start(event.target, null)`. T016 completes it.
  - **`pageshow` listener on `window`**: if `event.persisted`, clear `pending.timer` and set `pending = null`; then, if the bar exists, set `hidden = true` and remove `data-detached`. T016 adds the busy reset.
  - **Check**: T009's tests pass, except `test_it_never_disables_anything` and the others that must already pass.
- [ ] T013 [US1] In `app/templates/layouts/base.html`, add `<script src="/static/js/loading-feedback.js" defer></script>` inside `<head>`, after `<link rel="stylesheet" href="/static/css/app.css">` and before `{% block scripts %}{% endblock %}` (contract §1). The teacher students page's own `auto-submit.js` stays in its `scripts` block. Then T010 and T011 pass, and `tests/integration/test_teacher_classes.py::test_choosing_from_a_list_opens_the_selection_at_once` still passes, since it checks membership, not equality.
- [ ] T014 [US1] Check User Story 1 by hand from [quickstart.md §2](./quickstart.md#2-loading-bar-and-busy-button-us1-us2), rows 2.1, 2.2, 2.3, 2.4, 2.5 (no bar), 2.8, 2.9 (bar part), 2.10 and 2.11, in Chrome with DevTools throttling. Also confirm the R1 assumption: the old page keeps painting the moving bar until the next page arrives. Then repeat 2.1 and 2.9 in Firefox and Safari. Record the results, browser by browser, under a heading "US1 manual checks" in `specs/010.1-loading-feedback-pinned-frame/pr-notes.md`.

**Checkpoint**: on a slow page, every link and form shows the bar after 200 ms; fast pages and the
excluded cases show nothing.

---

## Phase 4: User Story 2 - A form is not sent twice (Priority: P1)

**Goal**: a POST form cannot be sent a second time while its next page is on its way. After
200 ms its button shows a spinner and is marked busy. The button's value is still sent, and Back
and Forward clear the busy state.

**Independent Test**: [quickstart.md §2](./quickstart.md#2-loading-bar-and-busy-button-us1-us2),
rows 2.6, 2.7, 2.8 and 2.9, plus `tests/unit/test_loading_script.py`.

### Tests for User Story 2

- [ ] T015 [P] [US2] Extend `tests/unit/test_loading_script.py`:
  - **`test_a_sending_post_form_cancels_a_second_submit`**: the source mentions `submitter`, `formMethod` and `preventDefault()`. This is a text-level guard of contract §3; the behaviour itself is checked by hand.
  - **`test_the_busy_state_is_aria_busy`**: the source contains `"aria-busy"` both in a `setAttribute` and in a `removeAttribute` (the reset).
  - **Existing test**: confirm that `test_it_never_disables_anything` from T009 covers the button-value guarantee (FR-010).
  - **Expect**: these fail until T016.

### Implementation for User Story 2

- [ ] T016 [US2] Complete `app/static/js/loading-feedback.js`, per [contracts/loading-script.md §3–§5](./contracts/loading-script.md#3-forms):
  - **Sending forms**: add `const sending = new WeakSet();` for the forms being sent.
  - **The `submit` listener**, in order:
    1. ignore the event if `event.defaultPrevented`, or if the effective target is set and is not `_self`;
    2. `const method = (event.submitter?.getAttribute("formmethod") || event.target.method).toLowerCase()`. Use `getAttribute`, because `submitter.formMethod` reflects the form's method when the attribute is absent, which also works; choose one and comment it;
    3. if `method === "post"` and `sending.has(form)`, call `event.preventDefault()` and return (FR-007);
    4. if `method === "post"`, call `sending.add(form)`;
    5. call `start(form, event.submitter)`. `event.submitter` is the default button when Enter was pressed, and `null` for `requestSubmit()` from `auto-submit.js`.
  - **GET forms are never added to `sending`**: a newer choice in a self-submitting list sends again (spec FR-007, research R3).
  - **`show()`**: sets `aria-busy="true"` on `pending.button` when there is one (FR-008).
  - **`pageshow` with `persisted`**: also `pending?.button?.removeAttribute("aria-busy")`, and forget the sending form (`if (pending?.form) sending.delete(pending.form)`). Read `pending` before resetting it to `null` (FR-011).
  - **Never** `disabled`, `readonly` or `inert` (FR-010).
  - **Comments**: one short comment on why `aria-busy` and not `disabled` (the form data is built after the `submit` event, and a disabled button's value would be left out). One on why GET forms may be sent again.
  - **Check**: `uv run pytest tests/unit/test_loading_script.py` passes.
- [ ] T017 [US2] Check User Story 2 by hand from [quickstart.md §2](./quickstart.md#2-loading-bar-and-busy-button-us1-us2), rows 2.6, 2.7, 2.8 and 2.9, in Chrome with throttling:
  - **2.6**: the uvicorn log shows exactly one `POST` for the invitation after 5 presses and an Enter.
  - **2.7**: the role switch and the theme switch apply the pressed value, and their secondary buttons show a visible spinner in Light and in Dark.
  - **2.8**: the newer list choice wins.
  - **2.9**: no busy button after Back or Forward.
  - **Other browsers**: repeat 2.6 and 2.7 in Firefox and Safari.
  - **Record**: the results go under "US2 manual checks" in `specs/010.1-loading-feedback-pinned-frame/pr-notes.md`.

**Checkpoint**: on slow pages, forms are sent once, the pressed button shows a busy spinner, and the
role and theme switches work as before.

---

## Phase 5: User Story 3 - Staff reach another tab without scrolling back up (Priority: P2)

**Goal**: on screens at least 600 px tall, the top bar and the area tabs stay at the top as one
block, while the page still scrolls as a whole. Shorter screens and print keep today's flow. The
user menu scrolls inside itself. The phone tabs are low enough to keep the frame under a quarter of
a 375 × 667 screen.

**Independent Test**: [quickstart.md §3](./quickstart.md#3-pinned-frame-us3-us4) rows 3.1–3.7 and
3.10, and [§4](./quickstart.md#4-measurements), plus `tests/unit/test_frame_stylesheet.py`.

**⚠️ Ship together with US4**: the pinned frame may not be merged without US4's target clearance
(spec US4).

### Tests for User Story 3

- [ ] T018 [P] [US3] Create `tests/unit/test_frame_stylesheet.py`:
  - **Docstring**: names specs/010.1 FR-005, FR-012–FR-016, SC-007 and research R5, R7, R9 and R10. **Helpers**: reuse `APP_CSS` and the helpers by importing them from `tests.unit.test_stylesheet`, or copy the small ones.
  - **A media-block helper**: `media_blocks(css, prelude)` returns the bodies of every `@media` block whose prelude equals `prelude` after collapsing whitespace. Brace-match; do not use a non-greedy regex.
  - **`test_only_the_page_frame_sticks_and_only_on_tall_screens`**:
    - `position: sticky` appears in `app.css` only inside `@media screen and (min-height: 600px)`;
    - there, the rule's selector is exactly `body > .frame`, with `top: 0` and a `z-index`;
    - no other rule in `app.css` sets `position: sticky` or `position: fixed`, except `.loading-bar[data-detached]`.
  - **`test_the_bar_is_still_under_reduced_motion_and_hidden_in_print`**:
    - a `@media (prefers-reduced-motion: reduce)` block sets `animation: none` on `.loading-bar::before`;
    - a `@media print` block sets `display: none` on `.loading-bar`.
  - **`test_the_user_menu_scrolls_inside_itself`**: the `.user-menu-panel` rule has `max-height` using `var(--sc-frame-clearance)` and `dvh`, plus `overflow-y: auto`.
  - **`test_phone_tabs_are_touch_target_high`**: the base `nav.area-tabs li a` rule has `min-height: var(--sc-touch-target)`, and a `@media (min-width: 768px)` block sets `min-height: 3rem` on it.
  - **Expect**: these fail until T019–T021.

### Implementation for User Story 3

- [ ] T019 [US3] In `app/static/css/app.css`, add the pinned frame (research R7, contract §1):
  - **The rule**: `@media screen and (min-height: 600px) { body > .frame { position: sticky; top: 0; z-index: 3; } }`.
  - **Comment**: it names FR-012–FR-014. The page still scrolls as a whole, and nothing here may add `overflow` or a fixed height. Below 600 px tall and in print the frame scrolls away as before. The skip link (`z-index: 10`) stays above it, and the user menu panel lives inside its stacking context.
  - **Check**: nothing between `body` and `.frame` sets `overflow`, which would stop the sticky rule from working.
- [ ] T020 [US3] In `app/static/css/app.css`, change the area tabs' height (research R9):
  - **`nav.area-tabs li a`**: `min-height: 3rem` becomes `min-height: var(--sc-touch-target)`.
  - **From 768 px**: `@media (min-width: 768px) { nav.area-tabs li a { min-height: 3rem; } }`. Reuse the existing `768px` block after `nav.area-tabs ul` if it fits.
  - **Comment**: wrapped phone tabs stay at the 44 px touch target, so the pinned frame fits within a quarter of a 375 × 667 screen (SC-007).
- [ ] T021 [US3] In `app/static/css/app.css`, let the user menu scroll inside itself (research R10, FR-016). Add `max-height: calc(100dvh - var(--sc-frame-clearance)); overflow-y: auto; overscroll-behavior: contain;` to `.user-menu-panel`, with a one-line comment.
- [ ] T022 [US3] Check User Story 3 by hand from [quickstart.md §3](./quickstart.md#3-pinned-frame-us3-us4) rows 3.1–3.7 and 3.10, at 1280 × 800 and 375 × 667, in Chrome and on a real phone, or Safari's responsive mode for 3.3:
  - **Long list**: add enough subjects locally to make `/admin/subjects` scroll.
  - **Measurements**: take [quickstart.md §4](./quickstart.md#4-measurements) with the DevTools computed height of `body > .frame` on `/admin/teachers` at 375 × 667 and 360 × 640, and on `/`. Expect at most 166 px (about 158.5 px) and below the clearance tokens.
  - **Record**: results and measurements go under "US3 manual checks" in `specs/010.1-loading-feedback-pinned-frame/pr-notes.md`.
  - **If a frame is taller than its token**: raise the token in T002's block and note why.

**Checkpoint**: on a tall screen the frame stays in view; on a short screen and in print it does
not.

---

## Phase 6: User Story 4 - The pinned frame never hides what the page moves to (Priority: P2)

**Goal**: the targets of the skip link and the error summary, and every element that receives
keyboard focus, land fully below the pinned frame, with the field's label and error. The skip link
shows above the frame. None of this depends on JavaScript.

**Independent Test**: [quickstart.md §3](./quickstart.md#3-pinned-frame-us3-us4) rows 3.8, 3.9 and
3.11, and [§2](./quickstart.md#2-loading-bar-and-busy-button-us1-us2) row 2.5, plus
`tests/unit/test_frame_stylesheet.py`.

### Tests for User Story 4

- [ ] T023 [P] [US4] Extend `tests/unit/test_frame_stylesheet.py`. Each test fails until T024.
  - **`test_targets_clear_the_frame`**: inside `@media screen and (min-height: 600px)`:
    - an `html` rule sets `scroll-padding-top: var(--sc-frame-clearance)`;
    - an `html:has(body > .frame .area-tabs)` rule sets `scroll-padding-top: var(--sc-frame-clearance-tabs)`.
  - **`test_fields_keep_their_label_in_view`**: a rule whose selector list contains `input`, `select` and `textarea` sets `scroll-margin-top: var(--sc-field-clearance)`.
  - **`test_the_skip_link_is_above_the_frame`**: the `.skip-link` rule's `z-index` is greater than the `body > .frame` rule's `z-index`. Parse both as integers.

### Implementation for User Story 4

- [ ] T024 [US4] In `app/static/css/app.css` (research R8, FR-015):
  - **The scroll padding**: inside the same `@media screen and (min-height: 600px)` block as T019, add `html { scroll-padding-top: var(--sc-frame-clearance); }` and `html:has(body > .frame .area-tabs) { scroll-padding-top: var(--sc-frame-clearance-tabs); }`.
  - **The field margin**: outside any media query, near the form styles, add `input, select, textarea { scroll-margin-top: var(--sc-field-clearance); }`.
  - **Comment**: it names WCAG 2.2 2.4.11 "Focus Not Obscured (Minimum)". It says that the browser keeps this space above every `#fragment` target and every element that receives focus, and that a form control also keeps its label and error message above it in view.
  - **Check**: `test_stylesheet.py` and `test_frame_stylesheet.py` pass.
- [ ] T025 [US4] Check User Story 4 by hand:
  - **Rows**: [quickstart.md §3](./quickstart.md#3-pinned-frame-us3-us4) rows 3.8 and 3.9, and [§2](./quickstart.md#2-loading-bar-and-busy-button-us1-us2) row 2.5. Use the teacher invitation form with two server-side errors on `/admin/teachers/invite`: follow each error-summary link.
  - **Sizes**: at 1280 × 800 and 375 × 667 (wrapped tabs) in Chrome, then row 3.11 in Firefox and Safari.
  - **Without JavaScript**: repeat 3.8 with JavaScript disabled.
  - **Record**: results go under "US4 manual checks" in `specs/010.1-loading-feedback-pinned-frame/pr-notes.md`.
  - **If a browser hides a target**: raise the relevant token, or add a `scroll-margin-top` where needed, and note why. Do not add script.

**Checkpoint**: the pinned frame is complete. US3 and US4 can be merged together.

---

## Phase 7: User Story 5 - A developer finds both new components in the gallery and the guidelines (Priority: P3)

**Goal**: the gallery's **Loading feedback** section is tested, and the UI guidelines describe the
pinned frame, the new tokens and breakpoint, the "Calm and focused" exception, the phone tabs and
the new checks.

**Independent Test**: `uv run pytest tests/integration/test_component_gallery.py`; reading
`docs/requirements/ui-guidelines.md`; [quickstart.md §5](./quickstart.md#5-gallery-and-documents-us5).

### Tests for User Story 5

- [ ] T026 [P] [US5] Extend `tests/integration/test_component_gallery.py`:
  - **`SECTIONS`**: insert `"loading": ["Loading bar", "Busy button", "Send invitation"]` right after `"frame"`. Dicts keep insertion order, so rebuild the literal in order. Update the docstring reference to name specs/010.1 contracts/components.md §5.
  - **`test_the_loading_section_shows_both_components_in_their_loading_state`**, signed in as an administrator, in `section#loading`:
    - exactly one element with class `loading-bar`, without `hidden`, with `aria-hidden="true"`, inside an element with class `frame`;
    - exactly three `button` elements with `aria-busy="true"`, none with `disabled`, and none inside a `form`.
  - **Expect**: these pass after T006. Run them now and fix T006 if needed.

### Implementation for User Story 5

- [ ] T027 [US5] Update `docs/requirements/ui-guidelines.md`:
  - **§2 "Calm and focused"**: after "Nothing moves or blinks", add the one exception. The loading bar moves while the next page is on its way, and stands still with reduced motion (milestone 10.1, FR-018).
  - **§3 Tokens, "Space and shape"**: add `--sc-frame-clearance`, `--sc-frame-clearance-tabs` (11 rem below 768 px, 8 rem from 768 px) and `--sc-field-clearance`, with what each is for.
  - **§4 Layout**:
    - item 2/3: the top bar, the area tabs and the loading bar sit in one `<div class="frame">`, pinned to the top on screens at least 600 px tall, scrolling away on shorter screens and in print; the page still scrolls as a whole;
    - add `(min-height: 600px)` to **Breakpoints**, which become three;
    - say that the script `loading-feedback.js` is loaded by the base layout on every page.
  - **§4, new paragraph "Keeping targets in view"**: scroll padding from the clearance tokens and the field margin keep skip-link targets, error-summary targets and focused elements below the frame (WCAG 2.2 2.4.11). A new tab, a longer tab label or a taller top bar must be re-measured at 360 px and 375 px width against the tokens (research R8).
  - **§8 Phone behaviour**: the area tabs are 44 px tall (the touch target) below 768 px and wrap; a phone held sideways (under 600 px tall) does not pin the frame.
  - **§10 Checks**: add `tests/unit/test_frame_stylesheet.py` and `tests/unit/test_loading_script.py`, and what each enforces.
  - **Style**: keep the document's existing tone and structure.

**Checkpoint**: the component library, the gallery and the guidelines are complete for later
milestones.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T028 [P] In `README.md`, section "Design system and UI guidelines", add one bullet after **Component gallery**:
  - **Loading feedback and pinned frame**: a thin bar under the top bar shows that a slow page is on its way, and the button that sent a form shows a spinner and cannot send it twice. Both come from `app/static/js/loading-feedback.js`, which the base layout loads on every page; without JavaScript, links and forms work as before.
  - The top bar and the area tabs stay at the top of the screen on screens at least 600 px tall.
  - Pages get all of this from the base layout.
- [ ] T029 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest`, then the same with `TEST_POSTGRES_URL` set. Everything must pass on both engines (FR-023, SC-010).
- [ ] T030 Take review screenshots with headless Playwright, following the memory recipe (`uv run --no-project --with playwright -- python -I <script>`, port 8765, a database copy). Never add Playwright to the project.
  - **Pages and sizes**: `/admin/teachers`, `/admin/subjects`, `/` and `/admin/components#loading`, at 1280 × 800 and 375 × 667, in Light and Dark.
  - **Scroll state**: on the list pages, scroll part-way so the pinned frame shows over the content.
  - **Where**: save to the git-ignored `screenshots/` folder.
  - **Review**: the frame, the hanging bar in the gallery, and the busy spinners on all three button kinds.
- [ ] T031 Go through every row of [quickstart.md](./quickstart.md) §2–§5 not already recorded by T014, T017, T022 and T025. Complete `specs/010.1-loading-feedback-pinned-frame/pr-notes.md` with a summary for the PR description:
  - what changed;
  - the manual check results by browser;
  - the measured frame heights;
  - the one visible change to the milestone 10 look (phone tab height, research R9);
  - the updated test `test_tabs_are_plain_links` (T011), with its reason.
- [ ] T032 On delivery, update `docs/requirements/milestones.md`:
  - move 10.1 from **Upcoming** to **Delivered**, as a short summary in the style of the other delivered milestones, with `_Spec:_ [010.1-loading-feedback-pinned-frame](../../specs/010.1-loading-feedback-pinned-frame/spec.md)`;
  - keep the delivered summary for milestone 10 unchanged, except for one added note that the frame is pinned and pages show loading feedback from 10.1, if the summary would otherwise be wrong.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup. It blocks every story.
  - T002 comes before T005.
  - T003 and T004 come before T005 and T006.
  - T006 and T007 come after T003 and T004.
  - T008 can run alongside T005–T007.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after US1. It completes the same script file (T016 extends T012).
- **US3 (Phase 5)**: after Foundational. It is independent of US1 and US2, which are script only,
  and can run in parallel with them.
- **US4 (Phase 6)**: after US3, in the same media block. It must be merged together with US3.
- **US5 (Phase 7)**: after Foundational. T027 describes US3 and US4, so finish its §4 and §8 text
  after them.
- **Polish (Phase 8)**: after every story.

### User Story Dependencies

- **US1 (P1)**: Foundational only.
- **US2 (P1)**: US1 (same file, `loading-feedback.js`).
- **US3 (P2)**: Foundational only.
- **US4 (P2)**: US3; they ship together.
- **US5 (P3)**: Foundational (the gallery); the guidelines text needs US3 and US4's final values.

### Within Each User Story

- Tests are written first and fail, except where a task says they pass already. Then comes the
  implementation, then the manual check.
- `app.css` edits in different stories touch different rules but the same file, so they are not
  marked [P] against each other.

### Parallel Opportunities

- **Phase 2**: T003, T004 and T008 touch different files.
- **Test modules**: T009 and T010 (US1), T015 (US2), T018 (US3), T023 (US4) and T026 (US5) are
  separate modules. T015 and T009 share a file, so write T015 after T009, and T023 after T018.
- **Two parallel streams**: after Foundational, US1→US2 (the script) and US3→US4 (the stylesheet)
  can run side by side, with US5's test (T026) alongside both.

---

## Parallel Example: after Foundational

```bash
# Stream A, the script (US1 → US2):
Task: "T009 Create tests/unit/test_loading_script.py"
Task: "T012 Create app/static/js/loading-feedback.js"

# Stream B, the stylesheet (US3 → US4):
Task: "T018 Create tests/unit/test_frame_stylesheet.py"
Task: "T019 Add the pinned frame rule to app/static/css/app.css"

# Stream C, the gallery test (US5):
Task: "T026 Extend tests/integration/test_component_gallery.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (T001) and Phase 2 (T002–T008): the components exist, are in the gallery and the
   guidelines, and the frame wrapper is in place.
2. Phase 3 (T009–T014): the loading bar on every page.
3. **Stop and validate**: quickstart §2 rows for US1. This alone removes "the link looks broken".

### Incremental Delivery

1. **+ US2**: no double posts, and a busy button.
2. **+ US3 and US4 together**: the pinned frame, which never hides targets.
3. **+ US5**: the gallery tests and the complete guidelines.
4. **Polish**: the README, both engines, screenshots, the PR notes, and `milestones.md` on delivery.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Commit after each task or logical group. Each story phase ends at a checkpoint that can be
  validated on its own.
- The manual checks (T014, T017, T022, T025, T031) are part of the milestone's _Test:_ line. They
  are not optional, because the suite has no browser before milestone 16.
