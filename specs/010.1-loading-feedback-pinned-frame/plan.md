# Implementation Plan: Feedback While a Page Loads, and a Frame That Stays in View (Milestone 10.1)

**Branch**: `010.1-loading-feedback-pinned-frame` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010.1-loading-feedback-pinned-frame/spec.md`

## Summary

Two improvements to the milestone 10 page frame. Addresses, fields, messages, access and stored
data do not change (FR-022).

**Loading feedback** (research R1–R6):

- **The script**: one deferred script, `app/static/js/loading-feedback.js`, loaded by
  `layouts/base.html` on every page. It listens on `document` for link clicks and form submits.
  For a click it starts only on a same-site, same-window click that leaves the page.
- **After 200 ms**:
  - it reveals a **loading bar**, a primary-coloured, indeterminate line hanging under the frame,
    still under reduced motion;
  - it marks the submitting button `aria-busy="true"`, which gives the **busy button** with Pico's
    spinner, redrawn in the button's own colour.
- **No double posts**: a POST form that is already sending cancels any further `submit`. The script
  never uses `disabled`, so the role and theme switches still send their button's value.
- **Back and Forward**: `pageshow` with `persisted` clears everything.
- **The components**: both are components, `loading_bar()` and `button(…, busy=True)`, shown in a new
  gallery section and described in the UI guidelines first.

**Pinned frame** (R7–R10):

- **The wrapper**: `base.html` wraps the top bar, the area tabs and the loading bar in
  `<div class="frame">`.
- **Sticky only on tall screens**: inside `@media screen and (min-height: 600px)`, `body > .frame` is
  `position: sticky; top: 0`. The page keeps scrolling as a whole, and print and short screens keep
  today's flow.
- **Targets stay visible**: new clearance tokens drive `scroll-padding-top` (more on area pages,
  through `:has()`). Form controls get a `scroll-margin-top` for their label and error. With these,
  skip-link targets, error-summary targets and keyboard focus land below the frame, without
  JavaScript.
- **The user menu** scrolls inside itself.
- **The phone tabs** drop to the 44 px touch-target height, so the wrapped administrator tabs keep the
  frame under a quarter of a 375 × 667 screen (SC-007).

**Tests** (R11): pytest checks the markup on every kind of page, the gallery, the stylesheet rules
and the script's source. Browser behaviour is checked by hand from the quickstart, with network
throttling, in Chrome, Firefox, Safari and on a phone.

## Technical Context

**Language/Version**: Python 3.13, unchanged. The browser code is plain ES2020 JavaScript, with no
build step.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, Pico.css v2.1.1 (vendored, not edited).
- No new runtime or development dependency (FR-020).

**Storage**: none. No table, column, migration, cookie or setting
([data-model.md](./data-model.md)).

**Testing**:

- pytest on SQLite and PostgreSQL, as before.
- 2 new unit modules: `test_frame_stylesheet.py` and `test_loading_script.py`.
- 2 extended integration modules: `test_layout.py` and `test_component_gallery.py`.
- A manual browser checklist in [quickstart.md](./quickstart.md) §2–§4. Playwright stays out of the
  project until milestone 16 (milestone 10 research D1).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and mobile.
- **Features relied on**:
  - `position: sticky`;
  - `scroll-padding` and `scroll-margin`;
  - `:has()`;
  - `dvh`;
  - `prefers-reduced-motion`;
  - `SubmitEvent.submitter`;
  - `pageshow.persisted`.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- **No extra request cost**: one extra static request per page, a few kilobytes and cacheable,
  loaded with `defer`, so it never blocks rendering.
- **Cheap to run**: no work runs while scrolling, except one passive listener that runs only while
  the bar shows (research R5). Sticky positioning and a `transform` animation run on the browser's
  compositor.

**Constraints**:

- **Nothing changes in behaviour**: addresses, fields, messages, access and data (FR-022).
- **Without JavaScript**, everything works as today (FR-021).
- **The milestone 10 checks stay green** (FR-023): every class defined and used, no inline style, no
  literal colour or pixel length outside the tokens, nothing loaded from another site.
- **No change to `pico.min.css`.**

**Scale/Scope**:

- 1 new script.
- 1 new macro (`loading_bar`) and 1 new macro parameter (`busy`).
- 3 new tokens.
- 4 changed templates:
  - `layouts/base.html`;
  - `components/frame.html`;
  - `components/button.html`;
  - `pages/admin/components.html`.
- `app.css` extended.
- 2 new and 2 extended test modules.
- 2 documents updated: the UI guidelines and the README.
- No route, router, service or model changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 10 is merged into `main` (PR #39). This is the next step of the ladder (10.1 in `milestones.md`). It is one user-visible slice: every page gets the feedback and the pinned frame, end to end. It ends in a demonstrable result (quickstart §2–§3). Nothing from milestone 11 or later is built. The out-of-scope items (prefetching, transitions, hide-on-scroll) stay out (FR-024). | ✅ |
| II. Server-rendered simplicity | Pages stay server-rendered. The new script is about 80 lines of plain JavaScript, with no build step, no framework, no dependency and no HTMX. The pinned frame and the target clearance are CSS only. **UI guidelines** (required from milestone 11, applied now): both new patterns go into the component library (`loading_bar`, `button(busy=True)`), the gallery (`#loading`) and `ui-guidelines.md` before the layout uses them. Every value is a token, and no page builds anything by hand (FR-017–FR-019). | ✅ |
| III. Test-backed delivery | **Deviation, recorded in Complexity Tracking.** The server-side half of the milestone's _Test:_ line is automated: every page loads the script and has the one pinned block; the gallery shows both components; the token and component check passes. The real-browser half ("a slow page shows the bar…", "Back shows no leftover…", "the frame stays in view…") is **not** automated by pytest, which this principle requires. It is checked by hand from quickstart §2–§4 and recorded in `pr-notes.md` (research R11). Text checks on the script and the stylesheet guard what can be read without a browser. No route changes, so no new role-access tests are needed; the existing sweeps still run. The milestone 1–10 suite stays green on both engines. | ⚠️ justified |
| IV. Role-based access & data scoping | No route, no permission and no data change. The gallery section is inside the existing administrator-only, development-only `/admin/components`. | ✅ |
| V. Secure authentication & secrets | No change to sessions, CSRF or secrets. The script sends nothing, reads no cookie and stores nothing. It cannot bypass the cross-site check: it never re-sends a form, it only cancels a duplicate. Nothing new is logged. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | No schema change, no migration and no stored data. The double-post guard reduces accidental duplicate writes but is not relied on for integrity (research R3). | ✅ |
| Stack: Styling row | Pico is restyled only through `app.css`, using its own `--pico-icon-loading` for the spinner. There is no CSS build step and nothing from another site. | ✅ |
| Stack: component timing | No component is introduced early. Playwright is not added (milestone 16). | ✅ |
| Application Layout | `static/js/` gains one file; `templates/components/` keeps the macros; no router or service logic. | ✅ |
| Governance | No constitution amendment is needed (research R12). | ✅ |
| Workflow gates | The README and the UI guidelines are updated in this PR. `milestones.md` moves 10.1 to Delivered on delivery. No migration is needed. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅, except the recorded Principle III deviation.

- **Only the planned markup changes**: the contracts add one wrapper element, one macro and one
  macro parameter.
- **No forbidden values**: the 3 new tokens live in the token block, and the only new literal is the
  `(min-height: 600px)` media query, which the token check allows.
- **No forbidden script behaviour**: the script never sets `disabled` and never sends anything, and
  a unit test guards both.

## Project Structure

### Documentation (this feature)

```text
specs/010.1-loading-feedback-pinned-frame/
├── plan.md                    # This file
├── research.md                # Phase 0: decisions R1–R12, with measurements
├── data-model.md              # Phase 1: new tokens; client-side states (no stored data)
├── quickstart.md              # Phase 1: CI checks, manual browser checklist, measurements
├── contracts/
│   ├── components.md          # Phase 1: layout skeleton, loading_bar, button(busy), styles, gallery section
│   └── loading-script.md      # Phase 1: the script's events, conditions and states
├── checklists/requirements.md # From /speckit-specify
└── tasks.md                   # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
app/
├── static/
│   ├── js/
│   │   ├── auto-submit.js              # unchanged
│   │   └── loading-feedback.js         # NEW: loading bar + busy button + double-post guard + bfcache reset
│   └── css/
│       └── app.css                     # CHANGED: 3 clearance tokens; .frame (sticky ≥600 px tall), scroll padding/margin;
│                                       #   .loading-bar (+ reduced motion, print, detached); busy spinner in currentColor;
│                                       #   phone tab height; user menu max-height/overflow; body > header.top-bar rule removed
└── templates/
    ├── layouts/
    │   └── base.html                   # CHANGED: <script defer> in <head>; <div class="frame"> around top bar, tabs, loading bar
    ├── components/
    │   ├── frame.html                  # CHANGED: + loading_bar(active=False)
    │   └── button.html                 # CHANGED: button(..., busy=False) → aria-busy="true"
    └── pages/admin/
        └── components.html             # CHANGED: + section #loading after #frame

tests/
├── unit/
│   ├── test_frame_stylesheet.py        # NEW: sticky rule scope, clearance tokens, reduced motion, print, menu overflow, tab height
│   └── test_loading_script.py          # NEW: source checks (no imports/fetch/foreign URLs; click/submit/pageshow; never disabled)
└── integration/
    ├── test_layout.py                  # EXTENDED: script once + .frame structure on every kind of page
    └── test_component_gallery.py       # EXTENDED: "loading" section, active bar, three busy buttons

docs/requirements/ui-guidelines.md      # CHANGED: §2 exception, §3 tokens, §4 pinned frame + 600 px rule, §5/§6 components, §8 phone tabs, §10 checks
README.md                               # CHANGED: one bullet in "Design system and UI guidelines"
```

**Structure Decision**: this is the existing single FastAPI application. The change touches only
templates, static files, tests and documents, in the directories the constitution's Application
Layout defines.

## Complexity Tracking

The script is not a deviation: Principle II already allows minimal custom JavaScript with no
build step. One deviation is recorded:

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle III**: the real-browser half of the milestone's _Test:_ line is checked by hand (quickstart §2–§4, results in `pr-notes.md`), not by automated pytest tests. | The behaviour exists only in a browser: a delayed bar while the old page waits for a slow response, a busy button, the back/forward cache, sticky positioning, and scroll padding for focus. pytest with the `TestClient` has no browser. The automated part covers everything the server sends, plus text-level guards on the script and the stylesheet, including the one regression with a silent, serious effect (a `disabled` button dropping its value). | **Introducing Playwright now** (`tests/e2e/`, justified in this plan as the stack rules allow) was rejected for this milestone. The constitution and milestone 10 research D1 place it in milestone 16. It would add a development dependency, browser binaries in CI and a CI job for one small milestone. An ad hoc headless check also showed that a Playwright screenshot waits for the pending navigation to finish, so the in-between state needs extra tooling (research R11). **When milestone 16 adds Playwright**, quickstart §2–§3 should become its first end-to-end tests. |
