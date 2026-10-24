# PR Notes: Milestone 10.1

## Summary for the PR description

**Feedback while a page loads, and a frame that stays in view.** Addresses, fields, messages,
access and stored data are unchanged.

- **Loading bar**: when a link to another page of the application is followed or a form is sent,
  and the next page has not arrived within 200 ms, a thin primary bar runs just under the frame
  until it does.
  - It starts for nothing else: not for new tabs (Ctrl, Cmd, Shift, middle click), other sites,
    `#` links or forms the browser refuses.
  - It stands still with reduced motion.
  - On a short screen it moves to the screen's top edge once the frame has scrolled away.
- **Busy button**: after the same 200 ms, the button that sent the form shows Pico's spinner,
  redrawn in the button's own colour.
  - A form that changes something (POST) cannot be sent again until the next page arrives.
  - Self-submitting lists (GET) may send a newer choice.
  - The button is never `disabled`, so the role and theme switches still send their value.
- **Back and Forward**: a page restored from the back/forward cache starts clean, with every busy
  button cleared and every form usable again.
- **Pinned frame**: on screens at least 600 px tall, the top bar and the area tabs stay at the top
  as one block.
  - The page still scrolls as a whole; short screens and print keep today's flow.
  - Scroll padding from new clearance tokens, and a margin on form controls, keep skip-link
    targets, error-summary targets and keyboard focus below the frame (WCAG 2.2, 2.4.11),
    without JavaScript.
  - The user menu scrolls inside itself.
- **Components first**: `loading_bar()`, `button(…, busy=True)`, the gallery section
  `#loading` and the UI guidelines (§2 exception, §3 tokens, §4 frame, §5 components, §8 phone,
  §10 checks) came before the layout used them (Principle II).
- **Code**: one new script, `app/static/js/loading-feedback.js` (85 non-blank lines), loaded by the
  base layout. No new dependency, no build step, and `pico.min.css` is untouched.

**One visible change to the milestone 10 look**: below 768 px, the area tabs are 44 px tall (the
touch-target token) instead of 48 px. The wrapped administrator tabs then keep the pinned frame
at 158.5 px, 23.8 % of a 375 × 667 screen (SC-007; at 48 px it was 24.96 %). See research R9.

**One changed earlier test**: `tests/integration/test_admin_area.py::test_tabs_are_plain_links`
asserted that an administrator page has no script at all. It now accepts exactly the base layout's
`loading-feedback.js`, and keeps its checks that the tabs are plain links with no forms and no
`hx-*` attributes. This is the one exception spec FR-023 allows.

**Tests**:

- **New**:
  - `tests/unit/test_loading_script.py` (9);
  - `tests/unit/test_frame_stylesheet.py` (7);
  - in `tests/unit/test_stylesheet.py`, the spinner-colour test;
  - in `tests/integration/test_layout.py`, the script and frame tests on 7 kinds of page;
  - in `tests/integration/test_component_gallery.py`, the loading section.
- **Whole suite**: 2,621 passed and 3 skipped on SQLite and PostgreSQL; the baseline was 2,572.

**Principle III deviation, recorded in plan.md Complexity Tracking**: the browser half of the
_Test:_ line is not in the pytest suite. It was checked with ad hoc headless Playwright in
Chromium, Firefox and WebKit (below). The items Playwright cannot reach are listed for the
reviewer.

**For the reviewer to check by hand before merge**:

- a real back/forward cache restore after a slow form (quickstart 2.9, 2.9a);
- real Safari and a real phone: 2.1, 2.6, 2.7, 2.9, plus the address bar hiding, pull-to-refresh
  and Back keeping the scroll position (3.3, 3.4);
- Tab and Shift-Tab in Safari with "Press Tab to highlight each item" on (3.9);
- 2.8, the teacher's self-submitting lists, with a teacher linked to institutions;
- print preview by eye (3.6).

**Screenshots**: `screenshots/010.1/` (git-ignored) holds the teachers, subjects, home and gallery
pages, at 1280 × 800 and 375 × 667, in Light and Dark.

## Baseline

Before any change, on branch `010.1-loading-feedback-pinned-frame` at `5ab91a3` (2026-10-24):
`ruff check` and `ruff format --check` were clean, and
`TEST_POSTGRES_URL=… uv run pytest` gave 2,572 passed and 3 skipped, on SQLite and PostgreSQL.

## US1 and US2 checks (loading bar, busy button)

Run on 2026-10-24 against a local run, with headless Playwright run ad hoc (not a project
dependency). Slow pages were made by holding the matching responses for 2 s in a Playwright route.
Playwright waits for a pending page load before it reads a page, so the page reported its own bar
and busy-button changes to the test as they happened.

**Real page loads** (quickstart §2):

| Row | Chromium | Firefox | WebKit |
|---|---|---|---|
| 2.1 bar shows on the old page, after 200 ms, until the next page | ✅ 246–248 ms | ✅ 204 ms | ✅ |
| 2.2 a fast page never shows the bar | ✅ | ✅ | ✅ |
| 2.3 Ctrl, Cmd, Shift and middle click start nothing | ✅ | ✅ | ✅ |
| 2.4 a form refused for an empty required field starts nothing | ✅ | ✅ | ✅ |
| 2.5 the skip link (`#main`) starts nothing | ✅ | ✅ | ✅ |
| 2.6 5 presses + Enter on a slow form: one `POST`, and the "Save" button busy | ✅ | ✅ | ✅ |
| 2.7 the theme switch is busy while slow and applies the pressed value | ✅ | ✅ | ✅ |
| 2.9 Back shows no leftover bar or busy button | ✅ | ✅ | ✅ |
| 2.9a form, then a link, then Back: no busy button; the form sends again | ✅ | harness error ¹ | ✅ |
| 2.9b short screen: the bar moves to the screen's top edge when scrolled | ✅ | not reached ¹ | ✗ ² |
| 2.10 reduced motion: the bar does not move | ✅ | not reached ¹ | ✅ |
| 2.11 without JavaScript: tabs and the theme switch work | ✅ | not reached ¹ | ✅ |

¹ Firefox: Playwright reports the deliberately cancelled form load as an error and stops. The
engine-independent checks below cover these rows in Firefox.
² Headless WebKit does not scroll while a page load is pending, so the case never arises there.
The engine-independent check below shows the script handles it in WebKit.

**Engine-independent checks**: a listener added after the script cancels the navigation, so the
page stays while the script believes a load is pending; the test then scrolls, resends and fires a
synthetic `pageshow` with `persisted`.

| Check | Chromium | Firefox | WebKit |
|---|---|---|---|
| FR-006: the bar shows under the frame, moves to the screen's top edge when scrolled, and comes back | ✅ | ✅ | ✅ |
| FR-008: the pressed button is busy after 200 ms | ✅ | ✅ | ✅ |
| FR-007: a second press and an Enter are cancelled | ✅ | ✅ | ✅ |
| FR-011: a restore after form → link clears the bar and the busy button, and the form sends again | ✅ | ✅ | ✅ |
| FR-007: a GET form (self-submitting list) may be sent again | ✅ | ✅ | ✅ |

**Still to check by hand before merge**:

- **A real back/forward cache restore** (2.9, 2.9a). Playwright disables the cache in every engine
  (no `persisted` restore was seen), so the real restore path was covered only by the synthetic
  event.
- **Real Safari and a real phone**: 2.1, 2.6, 2.7 and 2.9.
- **2.8, the teacher's self-submitting lists**: it needs a teacher linked to institutions. The
  logic is covered by the GET-form check above.

## US3 checks (pinned frame)

Run on 2026-10-24 with headless Playwright in Chromium, Firefox and WebKit: 13 of 13 passed in each.

- **§4 measurements** (`body > .frame`, the same in all three engines):

  | Size | With area tabs (`/admin/teachers`) | Without tabs (`/`) |
  |---|---|---|
  | 375 × 667 | 158.5 px, 23.8 % of the screen | 69.5 px |
  | 360 × 640 | 158.5 px, 24.8 % of the screen | 69.5 px |

  The administrator tabs wrap onto two rows at both widths. Every height is below its token:
  `--sc-frame-clearance-tabs` (176 px) and `--sc-frame-clearance` (88 px). SC-007 holds.
- **3.1, 3.2**: at 1280 × 800 and 375 × 667, after scrolling a long page, the frame is at the top
  of the screen, with and without tabs. Another tab opens with one press from the bottom.
- **3.3, 3.5**: the document is the only scroll container, and Page Down scrolls it.
- **3.6**: in print media the frame is not sticky and the loading bar is hidden.
- **3.7**: at 667 × 375 the frame scrolls away. Resized to 700 px tall, it pins again without a
  reload (analysis G1).
- **3.10**: at 1280 × 600 the open user menu ends on screen, and **Log out** can be reached.

**Still to check by hand before merge**: on a real phone, the address bar hiding, pull-to-refresh
(3.3) and Back returning to the same scroll position (3.4); print preview by eye (3.6).

## US4 checks (targets never hidden)

Run on 2026-10-24 with headless Playwright at 1280 × 800 and 375 × 667 (the tabs wrap), with and
without JavaScript: 14 of 14 passed in Chromium, Firefox and WebKit.

- **3.8 the skip link**: when focused it shows above the frame, and `<main>` then starts exactly at
  the frame's bottom edge (113 px desktop, 158 px phone).
- **2.5 an error-summary link**: the field was pushed 2,500 px down the page (JavaScript runs) or
  left in place (no JavaScript). After following the link, the label, the error message and the
  field are all below the frame. For example, at 375 × 667: frame 158 px, label 327 px, error
  357 px.
- **3.9 keyboard focus**: 35 controls down and 35 back up a long page; the closest any focused
  control came to the frame was 11–29 px below it.
  - **WebKit**: headless WebKit, like Safari's default setting, only Tabs between the page body and
    the account menu, so there focus was moved control by control from the page. The browser still
    scrolls each one into view past the frame.

**Still to check by hand before merge**: Tab and Shift-Tab in real Safari with "Press Tab to
highlight each item" turned on.

## Delivery

Merged in PR #40 and deployed. The product owner confirmed by hand that the loading bar and the
pinned frame behave as expected. `milestones.md` moves 10.1 to **Delivered** (T033).
