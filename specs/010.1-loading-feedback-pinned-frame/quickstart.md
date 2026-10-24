# Quickstart: Validating Milestone 10.1 (Loading Feedback and Pinned Frame)

**Feature**: [spec.md](./spec.md) | **Contracts**: [components.md](./contracts/components.md),
[loading-script.md](./contracts/loading-script.md) | **Research**: [research.md](./research.md)

This is a validation guide, not an implementation. §1 runs in CI. §2–§4 are checked by hand before
merge, because the suite has no browser until milestone 16 (research R11).

---

## 0. Prerequisites

- The project set up as in the README (`uv sync`), with the local database migrated.
- For both engines: the `sc-pg` container running and `TEST_POSTGRES_URL` set.
- Current Chrome, Firefox and Safari, plus one real phone, or the browsers' device emulation for
  sizes.
- A local run: `uv run uvicorn app.main:app --reload`, signed in as an administrator, then as a
  teacher (README "Signing in locally as each role").

## 1. Automated checks (CI)

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

**Expected**: everything passes on SQLite and PostgreSQL. In particular:

| Check | Covers |
|---|---|
| `tests/unit/test_stylesheet.py`, unchanged | no undefined or unused class, no inline style, no literal colour or pixel length outside the tokens, nothing loaded from another site (FR-023) |
| `tests/unit/test_frame_stylesheet.py`, new | the sticky rule only in `@media screen and (min-height: 600px)`; the scroll padding and field margin from the clearance tokens; the bar's reduced-motion and print rules; the user menu's `max-height` and `overflow-y`; the phone tab height (FR-005, FR-012–FR-016) |
| `tests/unit/test_loading_script.py`, new | the script exists, imports and fetches nothing, names no other site, listens to `click`, `submit` and `pageshow`, and never sets `disabled`, `readonly` or `inert` (FR-010, FR-020) |
| `tests/integration/test_layout.py`, extended | the sign-in page, the home page, an administrator page, a teacher page, a public consent or link-status page, and "not found" each load the script once with `defer`. Each has one `.frame` holding the top bar, the area tabs on area pages, and a hidden, `aria-hidden` loading bar (FR-012, FR-019, FR-020) |
| `tests/integration/test_component_gallery.py`, extended | the `loading` section after `frame`, with an active bar and three busy buttons (FR-017) |

## 2. Loading bar and busy button (US1, US2)

Open DevTools → Network → throttling **Slow 3G** (or a custom profile with 2,000 ms latency). In
Safari, use the Network Link Conditioner, or test against the deployed site after an idle period.

| # | Do | Expect |
|---|---|---|
| 2.1 | With throttling, click the **Subjects** tab | after about 0.2 s, a thin moving bar hangs under the tabs until **Subjects** appears (SC-001) |
| 2.2 | Without throttling, click between tabs quickly | no bar at any moment (SC-001) |
| 2.3 | With throttling, Ctrl-click, Cmd-click, Shift-click and middle-click a tab | each opens a new tab or window; the current page shows no bar (SC-003) |
| 2.4 | Submit a subject form with an empty name (the browser refuses the empty required field) | no bar; the button stays normal (SC-003) |
| 2.5 | Submit a form with a server-side error (a duplicate subject); click a link in "There is a problem" | the field, its label and its error are fully below the frame; no bar (SC-003, SC-008) |
| 2.6 | With throttling, invite a teacher: press **Send invitation** 5 times, then press Enter in the email field | from about 0.2 s the button shows a spinner; the server log shows **one** `POST` (SC-002) |
| 2.7 | With throttling, switch role from the user menu, then switch theme | the busy spinner shows on the pressed button, visible in both themes; the role and the theme that were pressed are applied (SC-004) |
| 2.8 | With throttling, in the teacher **Students** tab, pick a region, then quickly another | the bar shows; the page that arrives reflects the **last** choice |
| 2.9 | With throttling, open a page, then press Back while the bar shows; press Forward | neither page shows a leftover bar or busy button (SC-005) |
| 2.10 | Turn on reduced motion in the OS; repeat 2.1 | the bar shows as a still, full-width line (FR-005) |
| 2.11 | Disable JavaScript; follow links and submit forms, the role and theme switches included | everything works as before, with no bar and no spinner (SC-011) |

## 3. Pinned frame (US3, US4)

Use an administrator list long enough to scroll (add subjects locally if needed) and the teacher
**Students** tab.

| # | Do | Expect |
|---|---|---|
| 3.1 | At 1280 × 800 and 375 × 667, scroll to the bottom of a long list | the top bar and the tabs stay at the top as one block; another tab opens with one press (SC-006) |
| 3.2 | On the home page and the profile | the top bar alone stays at the top |
| 3.3 | On a real phone, scroll down, then pull down at the top | the address bar hides; pull-to-refresh reloads (FR-013) |
| 3.4 | Scroll halfway, open an item, press Back | the list returns to the same place (FR-013) |
| 3.5 | Press Space and Page Down | the page scrolls (FR-013) |
| 3.6 | Print preview a long list | the whole content prints; the frame appears once at the top (SC-009) |
| 3.7 | At 667 × 375 (phone held sideways), or a desktop window under 600 px tall, or a page zoomed until under 600 px | the frame scrolls away; a slow page still shows the bar at the top edge of the screen (FR-006, FR-014, SC-009) |
| 3.8 | Tab from the address bar | the skip link appears above the frame; using it shows the start of the main content below the frame (US4-2, US4-4) |
| 3.9 | Tab through a long table of actions | every focused control is fully below the frame (SC-008) |
| 3.10 | Open the user menu at a window height of 600–700 px, for a person with several roles | the menu scrolls inside itself; **Log out** can be reached (FR-016) |
| 3.11 | Repeat 3.1, 3.8 and 3.9 in Firefox and Safari | same results (research R8) |

## 4. Measurements

In DevTools at 375 × 667 and 360 × 640, on `/admin/teachers` (the tabs wrap there), measure the
height of `body > .frame`.

**Expected**:

- at most 166 px at 375 × 667, so at most a quarter of the screen (SC-007), and about 158.5 px
  (research R9);
- smaller than `--sc-frame-clearance-tabs` (176 px) at both sizes;
- on `/`, smaller than `--sc-frame-clearance` (88 px).

Re-measure whenever the top bar or the tabs change.

## 5. Gallery and documents (US5)

- **The gallery**: `/admin/components` → **Loading feedback** shows the moving bar under a sample
  top bar, and three busy buttons (primary, secondary, destructive) with visible spinners in Light
  and Dark. Pressing a sample button does nothing.
- **The guidelines**: `docs/requirements/ui-guidelines.md` describes the loading bar, the busy
  button, the pinned frame, the 600 px rule, the clearance tokens, the "Calm and focused" exception
  and the phone tab height.
- **The README**: its design section mentions all three.
- **On delivery**: `milestones.md` moves 10.1 to **Delivered**.
