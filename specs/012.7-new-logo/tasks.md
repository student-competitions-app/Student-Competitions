---

description: "Task list for milestone 12.7: the new logo"
---

# Tasks: The New Logo (Milestone 12.7)

**Input**: Design documents from `/specs/012.7-new-logo/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/components.md](./contracts/components.md),
[contracts/static-assets.md](./contracts/static-assets.md),
[contracts/logo-script.md](./contracts/logo-script.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III, spec FR-031–FR-037. Research R9 maps the tests to
modules.

- **Engines**: every database test runs on SQLite, and on PostgreSQL too when `TEST_POSTGRES_URL` is
  set (the `sc-pg` container), through the fixtures in `tests/conftest.py` (`client`, `client_as`,
  `admin_client`). This milestone touches no data, but the whole suite still runs on both engines.
- **The suite runs in English** (milestone 12.5 FR-067). A test that needs Ukrainian sets the cookie
  `sc_lang=uk` on its client. A test of a theme sets the cookie `sc_theme=light` or `sc_theme=dark`;
  without it, the theme is `device`.
- **HTML helpers**: `tests/html.py` (`parse`, `find_all`, `attrs`, `classes()`, `text`, `role_label`).
- **Component tests**: `tests/unit/test_templates.py` renders a macro with
  `render(source, **context)` and expects `jinja2.TemplateRuntimeError` from `template_error`.
- **Stylesheet tests**: `tests/unit/test_frame_stylesheet.py` has `top_level_rules()`,
  `media_blocks(prelude)`, `rules(css)` and `rule(selector, rules)`. `tests/unit/test_stylesheet.py`
  enforces, unchanged, that:
  - every used class is defined, and every defined class is used;
  - no `--sc-*` property is set outside the token block;
  - no pixel literal appears outside it.
- **The images are never edited by hand.** Only T003 (and a rerun in T033) writes
  `app/static/img/logo/`, by running the script.

**Organization**: tasks are grouped by user story (US1–US6 in spec.md).

- **Phase 2** builds what every story shows:
  - the script and its regenerated image set;
  - the image-based `logo_mark` with both callers;
  - the stylesheet rules that keep the class checks green.

  After Phase 2 the emblem is in the top bar at 2rem at every width, and in the gallery.
- **US1** (P1) makes the top bar's mark 44 px on phones and moves the role label beside it.
- **US2** (P1) adds the favicons, the touch icon and the manifest, and removes the old icon links and
  files.
- **US3** (P2) proves the gallery's inks per theme. Its code is in Phase 2.
- **US4** (P2) is the product owner's approval, on screenshots of US1–US3.
- **US5** (P3) proves the image set is exact and reproducible, and documents the script.
- **US6** (P3) removes every trace of the old mark and updates the documentation.

**Reference implementation**: match the docstring style, naming and comment density of:

- `app/templates/components/icons.html` (the current `logo_mark` and `icon`, their header comment)
  and `app/templates/components/frame.html` (`top_bar`, its header comment).
- `tests/integration/test_layout.py` (`brand`, `assert_identity`, the identity tests) and
  `tests/integration/test_component_gallery.py` (`SECTIONS`, the per-variant tests).
- `tests/unit/test_frame_stylesheet.py` (`test_the_wordmark_gives_way_on_a_phone_when_a_role_is_shown`)
  and `tests/unit/test_templates.py` (`test_competition_status_badge_refuses_an_unknown_status`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: The script's libraries, locked but never installed by CI or the image.

- [X] T001 Add the non-default dependency group `logo = ["numpy>=2.1", "pillow>=11.1"]` under
  `[dependency-groups]` in `pyproject.toml`, next to `dev`. Do not set `[tool.uv] default-groups`.
  Run `uv lock` to record the group in `uv.lock`, then confirm:
  - `uv lock --check` passes;
  - after `uv sync --locked`, `uv run python -c "import PIL"` fails with `ModuleNotFoundError`.

  (contracts/logo-script.md, research R8, FR-023)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The image set, the image-based logo mark and the stylesheet rules every story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Rewrite `scripts/make_logo.py` per contracts/logo-script.md and research R7.
  - **Structure**: a module docstring with the command `uv run --group logo scripts/make_logo.py`,
    and a `main()` behind `if __name__ == "__main__"`.
  - **Arguments and paths**: no arguments. `ROOT = Path(__file__).resolve().parents[1]`,
    `SRC = ROOT / "docs/brand/logo-source.png"`, `OUT = ROOT / "app/static/img/logo"`. No work
    directory and no debug master.
  - **Imports**: `numpy` and `PIL` (Pillow) only; delete every use of `cv2`.
  - **Steps**: keep the first version's steps and parameters, porting each OpenCV call:
    - Flatten onto white and crop to `L < 240` plus 3 px.
    - Upscale three times by 2 with `Image.fromarray(a, "F").resize(…, Image.LANCZOS)`, each step
      followed by an unsharp mask (amount 0.6, σ 1.2).
    - A numpy bilateral filter: a 7 × 7 window over 49 shifted copies of the edge-padded image,
      spatial σ 5, range σ 18, normalised.
    - A final unsharp mask (0.8, σ 2.0).
    - Levels 25–232, γ 0.9; coverage below 0.02 becomes 0.
    - Pad to a square master.
  - **Gaussian blur**: a separable numpy convolution with a normalised 1-D kernel of radius
    `ceil(3σ)` and edge padding.
  - **Emblem images** (data-model.md §1): light ink `#f4f5f8` at 24, 32, 44, 48, 64, 72, 88, 96,
    128, 132, 192 px, and dark ink `#1c1c22` at 24, 32, 48, 64, 72, 96, 128, 192 px, written as
    `logo-{ink}-{px}.png`. Apply the alpha sharpening for small sizes at 48 px and below.
  - **Icons** (data-model.md §3), with the first version's `tile()` parameters, on `#16337a`:
    - `favicon-16.png`, `favicon-32.png`, `favicon-48.png` and `favicon.ico` (16/32/48): rounded
      tile, padding 0.02, radius 0.22;
    - `apple-touch-icon.png`: 180 px, padding 0.08, saved as opaque RGB;
    - `icon-192.png` and `icon-512.png`: padding 0.06;
    - `icon-maskable-512.png`: padding 0.15.
  - **Manifest**: `site.webmanifest` exactly as contracts/static-assets.md §3, with
    `json.dumps(…, ensure_ascii=False, indent=2) + "\n"`, written in UTF-8.
  - **No link preview**: do not write `og-image.png`.
  - **Cleanup**: only after every write has succeeded, delete every file in `OUT` that this run did
    not write, and print the crop, the files written and the files removed.
  - **Style**: `uv run ruff check scripts/make_logo.py` and `uv run ruff format --check
    scripts/make_logo.py` pass.

  (FR-020–FR-024)
- [X] T003 Run `uv run --group logo scripts/make_logo.py` and check its result:
  - `app/static/img/logo/` holds exactly 28 files: 19 `logo-*.png`, the 8 icons and
    `site.webmanifest`;
  - `og-image.png`, `logo-{dark,light}-{256,512,1024}.png` and `logo-header-{32,64,96}.png` are
    gone;
  - running the script a second time leaves `git status --porcelain app/static/img/logo` unchanged.

  Open `logo-light-44.png`, `logo-dark-64.png` and `favicon-32.png` to check them by eye. Commit the
  folder as the script left it. (FR-018–FR-020, depends on T001, T002)
- [X] T004 Rewrite `logo_mark` in `app/templates/components/icons.html` as
  `logo_mark(size="md", theme=none, top_bar=False)`, exactly per contracts/components.md.
  - **Errors** (`template_error`, before any markup):
    - an unknown size: "logo_mark: size must be sm, md or lg" (unchanged);
    - `top_bar` with a size other than `md`: "logo_mark: the top bar's mark is md";
    - no `top_bar` and a theme other than light, dark or device: "logo_mark: theme must be light,
      dark or device".
  - **Top bar**: one `<img class="logo-mark logo-mark-top-bar">` with `src` `logo-light-32.png`,
    `srcset` `32w 44w 64w 88w 96w 132w` over the light ink,
    `sizes="(min-width: 768px) 2rem, 2.75rem"`, and `width="32" height="32"`.
  - **On a page**:
    - **Light**: `<img class="logo-mark logo-mark-{size}">` with dark ink, `srcset` 1x/2x/3x of the
      size's pixels (sm 24, md 32, lg 64), and `width` and `height` the 1× size.
    - **Dark**: the same with light ink.
    - **Device**: `<picture>` with `<source media="(prefers-color-scheme: dark)" srcset="…light
      1x, 2x, 3x…">` around the dark-ink `<img>`.
  - **Every `<img>`**: `alt=""` and `aria-hidden="true"`; paths under `/static/img/logo/`, built in
    one place in the macro.
  - **Class literals**: keep them literal strings, as today, so `test_stylesheet.py`'s used-class
    scan sees `logo-mark-top-bar`, `logo-mark-sm`, `logo-mark-md` and `logo-mark-lg`.
  - **Header comment**: the logo mark is the emblem image (milestone 12.7 contracts/components.md,
    research R2–R4), light ink on the top bar, following the theme elsewhere with no script. It no
    longer mentions inline SVG or `favicon.svg`.

  (FR-005, FR-007–FR-011)
- [X] T005 [P] In `app/templates/components/frame.html`, `top_bar` calls
  `logo_mark("md", top_bar=True)` inside the brand link. Nothing else changes: the wordmark span, the
  `brand-with-role` class and the role label stay. Update the header comment's mention of "the logo"
  only if it describes the SVG. (FR-001, FR-006, depends on T004)
- [X] T006 [P] In `app/templates/pages/admin/components.html`, the **Identity** row becomes
  `{{ logo_mark("lg", theme) }}{{ logo_mark("md", theme) }}{{ logo_mark("sm", theme) }}`, passing the
  context's `theme` explicitly. The swatches, including `--sc-accent` and `--sc-on-accent`, are
  unchanged. (FR-012, FR-030, depends on T004)
- [X] T007 In `app/static/css/app.css`, icons section:
  - Delete `.logo-mark-tile` and `.logo-mark-spark`.
  - Add `.logo-mark-top-bar { width: 2rem; height: 2rem; }`. This is the size the top bar's mark has
    from 768 px, and US1 (T011) adds the phone size.
  - Rewrite the icons comment: the logo mark is an image, light ink on the top bar and following the
    theme elsewhere, and the line icons draw in the current text colour.
  - Keep `.logo-mark` and `.logo-mark-sm/-md/-lg`.

  Run `uv run pytest tests/unit/test_stylesheet.py tests/unit/test_frame_stylesheet.py` and check it
  passes. (FR-029, depends on T004)
- [X] T008 Run `uv run pytest tests/integration/test_layout.py tests/integration/test_component_gallery.py`.
  Only the identity tests that look for the inline `<svg class="logo-mark">` and the old favicons may
  fail; US1 and US2 rewrite them. Every other test passes. (depends on T005–T007)

**Checkpoint**: the emblem shows in the top bar (2rem at every width) and in the gallery, following
the theme. The image folder is the script's exact output.

---

## Phase 3: User Story 1 - A visitor recognises the application by its emblem in the top bar (Priority: P1) 🎯 MVP

**Goal**: The top bar shows the emblem in light ink, 2rem from 768 px and 44 px below. It stays one
64 px row with the role label beside the mark. The link still reads as the application's name.

**Independent Test**: Open the sign-in page and an area page at 375 px and 1280 px, in Light and Dark.
Check the ink, the size, the sharpness, the bar's height and the brand link's announced name
(quickstart §3.1, §3.2, §3.8).

### Tests for User Story 1 ⚠️

> Write these tests first and check that they fail before T011 and T012.

- [X] T009 [P] [US1] In `tests/integration/test_layout.py`, rewrite `assert_identity` for the image
  mark (keep `FAVICONS` for US2 to replace in T015). The brand link (`brand(body)`) holds exactly one
  element with class `logo-mark`. That element:
  - is an `<img>` with class `logo-mark-top-bar`, `alt=""` and `aria-hidden="true"`;
  - has `width="32"` and `height="32"`;
  - has a `src` and every `srcset` URL under `/static/img/logo/logo-light-`, and its `sizes` is
    `(min-width: 768px) 2rem, 2.75rem`.

  The page has no `<svg>` with class `logo-mark`. Keep the four identity tests (sign-in, signed-in
  pages, not-found pages, refusal pages). Add
  `test_the_brand_link_is_named_in_the_pages_language`, parametrised over signed out (`client`) and
  signed in (`admin_client`): with `sc_lang=uk`, the brand link's text is «Студентські змагання» and
  the mark contributes no text; without the cookie it is "Student Competitions". (FR-001, FR-005,
  FR-031)
- [X] T010 [P] [US1] In `tests/unit/test_frame_stylesheet.py`, add
  `test_the_top_bar_mark_is_a_touch_target_on_a_phone`:
  - top level, `rule(".logo-mark-top-bar", top_level_rules())` sets `width` and `height` to
    `var(--sc-touch-target)`;
  - exactly one `@media (min-width: 768px)` block sets `.logo-mark-top-bar` `width` and `height` to
    `2rem`.

  Add `test_the_role_label_follows_the_mark_width`:
  - top level, `.brand-with-role + .brand-role` has
    `margin: 0 0 0 calc(var(--sc-touch-target) + var(--sc-space-1))`;
  - `.brand-role` has `padding-left: calc(var(--sc-touch-target) + var(--sc-space-1))`;
  - neither top-level body contains `2rem`.

  Each test gets a docstring citing milestone 12.7 FR-002 and FR-004. (FR-034)

### Implementation for User Story 1

- [X] T011 [US1] In `app/static/css/app.css`:
  - Change `.logo-mark-top-bar` to `width: var(--sc-touch-target); height: var(--sc-touch-target);`.
  - In the existing `@media (min-width: 768px)` block nearest the icons section, or a new one right
    after the rule, set `.logo-mark-top-bar { width: 2rem; height: 2rem; }`.
  - Change `.brand-role`'s `padding-left` to `calc(var(--sc-touch-target) + var(--sc-space-1))`.
  - Change `.brand-with-role + .brand-role`'s `margin` to
    `0 0 0 calc(var(--sc-touch-target) + var(--sc-space-1))`.
  - Leave the `768px` resets of both unchanged, and leave `.top-bar > .container`'s
    `min-height: 4rem` unchanged.
  - Update the top bar comment ("The top bar (FR-018): the mark and the name…") to say that the mark
    is 44 px below 768 px and 2rem from it (milestone 12.7).

  Search `app.css` for any other `2rem` that assumes the mark's width; research R5 found none.
  (FR-002–FR-004, depends on T010)
- [X] T012 [US1] Run `uv run pytest tests/integration/test_layout.py tests/unit/test_frame_stylesheet.py
  tests/unit/test_stylesheet.py`. Everything passes except the favicon assertion of `assert_identity`,
  which T015 changes. (depends on T009–T011)
- [X] T013 [US1] Check by hand per quickstart §3.2 and §3.8, with the application running locally and
  Playwright run ad hoc (`uv run --no-project --with playwright`):
  - at 360 px and 375 px, signed out and with a teacher's role shown, in Ukrainian and English (8
    combinations), the top bar is 64 px tall, the mark is 44 × 44 and the role label does not overlap
    it;
  - with a screen reader, the brand link reads the application's name.

  Then quickstart §3.3: measure the bottom of `.frame` on `/teacher/students` and `/admin/teachers` at
  360 × 640 and 375 × 667 in both languages. Record all eight numbers in the **Measurements** table of
  `specs/012.7-new-logo/quickstart.md` §3, and tick its one-row confirmation. Commit it, so T031 can
  read the numbers in any later session. If a check fails, fix `app.css` and repeat T012. (FR-003,
  SC-002)

**Checkpoint**: US1 is complete. The emblem identifies the application in the top bar at every width.

---

## Phase 4: User Story 2 - The browser tab and the phone's home screen show the emblem (Priority: P1)

**Goal**: Every page links the new favicons, the Apple touch icon and the manifest; each is served
publicly with its type. The manifest opens the application in the browser.

**Independent Test**: Request each icon and the manifest signed out; read the manifest; see the browser
tab; add to a phone's home screen (quickstart §3.6, §3.7).

### Tests for User Story 2 ⚠️

> Write these tests first and check that they fail before T016.

- [X] T014 [P] [US2] Create `tests/integration/test_logo.py`, with a module docstring citing milestone
  12.7 spec FR-013–FR-017 and contracts/static-assets.md. Add:
  - `ICON_LINKS`: the six `(rel, href)` pairs of contracts/static-assets.md §2.
  - `test_every_icon_and_the_manifest_answer_to_a_signed_out_visitor`, parametrised over the nine
    URLs (four favicons, the touch icon, the manifest and its three icons, without duplicates). Each
    answers 200 to `client`. The type is `image/png` for PNGs; for `favicon.ico` it is
    `image/x-icon` or `image/vnd.microsoft.icon`, compared on the type before any `;`. The manifest's
    type starts with `application/manifest+json`.
  - `test_the_manifest_opens_the_application_in_the_browser`: the JSON has `name` ==
    "Студентські змагання", `start_url` == "/", `display` == "browser", and `theme_color` ==
    `background_color` == "#16337a". Its `icons` are exactly the three of §3, the maskable one with
    `purpose` "maskable", and each `src` answers 200 as `image/png`.
- [X] T015 [P] [US2] In `tests/integration/test_layout.py`, replace `FAVICONS` with the six links of
  contracts/static-assets.md §2. `assert_identity` checks that the page's `<link>` elements include
  each of them, with their `rel`, `href`, `sizes` and `type` where given. The identity tests already
  run on the sign-in page, signed-in pages, not-found and refusal pages, so every kind of page is
  covered. (FR-015, FR-032)

### Implementation for User Story 2

- [X] T016 [US2] In `app/templates/layouts/base.html`, replace the three old icon links
  (`/static/img/favicon.svg`, `/static/img/favicon-32.png`, `/static/img/apple-touch-icon.png`) with
  the six links of contracts/static-assets.md §2, in the same place after the font preload.
  (FR-015, depends on T003)
- [X] T017 [US2] Delete `app/static/img/favicon.svg`, `app/static/img/favicon-32.png` and
  `app/static/img/apple-touch-icon.png` (`git rm`). `app/static/img/` keeps `flag-gb.svg`,
  `flag-ua.svg` and `logo/`. (FR-028, depends on T016)
- [X] T018 [US2] Run `uv run pytest tests/integration/test_logo.py tests/integration/test_layout.py`;
  everything passes. If a type differs on this machine (for example `.webmanifest`), stop and revisit
  research R6 rather than loosen the test. (depends on T014–T017)
- [ ] T019 [US2] Check by hand per quickstart §3.6 and §3.7:
  - the browser tab shows the emblem on a rounded deep-blue tile, in the browser's light and dark
    appearance;
  - on a phone, Add to Home Screen gives the emblem on a deep-blue square, and opening it shows the
    application in the browser, with the address bar, and Back and reload working;
  - on Android, a round mask keeps the whole emblem.

  The phone check may need the product owner's device; record who checked it for T024. (FR-013,
  FR-014, FR-016, SC-005)

**Checkpoint**: US1 and US2 are complete. The new identity is in the bar, the tab and the home screen.

---

## Phase 5: User Story 3 - The logo mark component shows the emblem and follows the theme (Priority: P2)

**Goal**: Off the top bar, the mark follows Light, Dark and Device without JavaScript, at its three
sizes. The code is in Phase 2 (T004, T006); this phase proves it.

**Independent Test**: Open the gallery in each theme. Switch the device's colour scheme in the developer
tools with JavaScript off. Render the component with an unknown size (quickstart §3.4, §3.5).

### Tests for User Story 3 ⚠️

- [ ] T020 [P] [US3] In `tests/unit/test_templates.py`, after the existing refusals, add:
  - `test_logo_mark_refuses_an_unknown_size`, parametrised over `"xl"` and `""`, and
    `test_logo_mark_refuses_a_top_bar_size_other_than_md`, parametrised over `sm` and `lg`;
  - `test_logo_mark_needs_a_theme_off_the_top_bar`: no theme, and `"sepia"`.

  Each renders `{% from "components/icons.html" import logo_mark %}{{ logo_mark(…) }}` and expects
  `TemplateRuntimeError` matching the messages of contracts/components.md.

  Add `test_logo_mark_in_each_theme`, parametrised over the sizes `sm`/24, `md`/32 and `lg`/64:
  - `light`: one `<img>`, dark ink, `srcset` `…-{p}.png 1x, …-{2p}.png 2x, …-{3p}.png 3x`, and
    `width` = `height` = `p`;
  - `dark`: the same with light ink;
  - `device`: a `<picture>` whose single `<source>` has `media="(prefers-color-scheme: dark)"` and
    the light-ink srcset, and whose `<img>` has the dark-ink one.

  Every `<img>` has `alt=""` and `aria-hidden="true"`. (FR-007–FR-011, FR-033)
- [ ] T021 [P] [US3] In `tests/integration/test_component_gallery.py`, add
  `test_the_identity_marks_follow_the_theme`, parametrised over `light`, `dark` and `device` (the
  `sc_theme` cookie on `admin_client`; for `device`, no cookie). The `#identity` section holds three
  logo marks with classes `logo-mark-lg`, `logo-mark-md` and `logo-mark-sm`, in that order:
  - `light`: every `src`/`srcset` URL in the section is `logo-dark-*`, and there is no `<picture>`;
  - `dark`: every URL is `logo-light-*`;
  - `device`: three `<picture>` elements, each with a light-ink `<source>` for
    `(prefers-color-scheme: dark)` and a dark-ink `<img>`.

  The existing `SECTIONS["identity"]` text check (including `--sc-accent`) stays. (FR-011, FR-012,
  FR-035)

### Implementation for User Story 3

- [ ] T022 [US3] Run `uv run pytest tests/unit/test_templates.py
  tests/integration/test_component_gallery.py`. If a test fails, fix `components/icons.html` (T004) or
  `pages/admin/components.html` (T006) to match contracts/components.md, never the test.
  (depends on T020, T021)
- [ ] T023 [US3] Check by hand per quickstart §3.4 and §3.5, with JavaScript disabled:
  - with **Device** chosen, `/admin/components#identity` switches between dark and light ink when
    "Emulate CSS prefers-color-scheme" is switched, and the top bar's mark stays light ink;
  - the Network panel shows one `logo-*.png` per mark: `logo-light-44.png` (or 88/132) below 768 px
    and `logo-light-32.png` (or 64/96) from 768 px for the top bar.

  (FR-009, FR-011, SC-003)

**Checkpoint**: US1–US3 are complete. Every visible change is in place for review.

---

## Phase 6: User Story 4 - The product owner approves the new look (Priority: P2)

**Goal**: The deviation from milestone 10's approved look is reviewed on screenshots and recorded with
its date in this milestone's own design approval.

**Independent Test**: `specs/012.7-new-logo/design-approval.md` lists the 16 screenshots and has a dated
**Approved** round before merge.

- [ ] T024 [US4] Take the 12 headless screenshots of research R10 with a Playwright script in the
  scratchpad:
  - the top bar (viewport clip of the frame) on `/login` and on `/teacher/students`;
  - the `#identity` section of `/admin/components`;
  - each at 375 px and 1280 px, in Light and Dark (the `sc_theme` cookie).

  Sign in with the project's recipe: a database copy, `uvicorn` on port 8765, a session cookie or the
  console code. Ask the product owner for the 4 browser-tab images (desktop browser in light and dark
  appearance at 1280 px; a phone's tab view for 375 px), or take them by hand. Save all 16 in
  `specs/012.7-new-logo/screenshots/` as `{view}-{width}-{theme}.png`, with `view` one of `sign-in`,
  `area`, `identity`, `tab`. (FR-025, depends on T013 and T023; the phone check T019 does not block the
  screenshots)
- [ ] T025 [US4] Create `specs/012.7-new-logo/design-approval.md` in the form of
  `specs/010-design-system-ui-guidelines/design-approval.md`:
  - **Approver**: the product owner.
  - **Feature**: a link to spec.md (User Story 4, FR-025, FR-026).
  - **Screenshots**: a table of the 16 files.
  - **The gate**: the milestone does not merge before a round with status Approved.
  - **The deviation**: from milestone 10's approved look (its US1 scenario 3).
  - **Review log**: columns Date, Round, Commit, Changes requested, Changes made, Status. Round 1
    carries the commit that holds the screenshots and status "Awaiting review".
  - **Questions for round 1**:
    - the emblem's size and padding in the favicons;
    - the 44 px mark on phones;
    - the dark ink on the light gallery background;
    - the maskable icon's padding.

  Commit the screenshots and this file. (FR-026, depends on T024)
- [ ] T026 [US4] Ask the product owner to review round 1, and record the answer with its date.
  - **Changes requested**: make them in the script (then T003 again) or in T004/T007/T011, take new
    screenshots (T024) and add round 2. Repeat until approved.
  - **Approved**: set the status to Approved, with the date.

  Do not edit `specs/010-design-system-ui-guidelines/design-approval.md`. (FR-026, SC-009)

**Checkpoint**: The new look is approved and recorded.

---

## Phase 7: User Story 5 - A maintainer regenerates the images from the source (Priority: P3)

**Goal**: One command writes exactly the images the application uses. CI and the image never install
its libraries. The README says how to run it.

**Independent Test**: Compare the folder with the URLs in use. Rerun the script and see no change. Sync
as CI does and see that Pillow is absent (quickstart §2, §5).

### Tests for User Story 5 ⚠️

- [ ] T027 [P] [US5] In `tests/integration/test_logo.py`, add
  `test_the_logo_folder_holds_only_what_is_used`. It collects every `/static/img/logo/…` URL from:
  - `src`, `srcset` and `href` on `client.get("/login")`;
  - `admin_client.get("/admin/components")` with `sc_theme=light` and with `sc_theme=dark`;
  - the manifest's icons and the manifest's own URL.

  It parses `srcset` candidates by splitting on commas and taking the first token of each, and
  asserts that the set of file names equals `{p.name for p in (APP / "static/img/logo").iterdir()}`.
  The failure message names the stray and the missing files. (FR-018, FR-019, SC-006)

### Implementation for User Story 5

- [ ] T028 [US5] In `README.md`:
  - Add a short "Logo images" paragraph near the other developer tasks (for example after
    "Translations"):
    - the emblem's source is `docs/brand/logo-source.png`;
    - `uv run --group logo scripts/make_logo.py` writes every image and the web manifest in
      `app/static/img/logo/` and removes any other file there;
    - its output is committed and never edited by hand;
    - its libraries (Pillow, numpy) are the `logo` dependency group, which neither CI nor the image
      installs.
  - In the project tree, add under `scripts/`:
    `make_logo.py   # The logo images and web manifest from docs/brand/logo-source.png (uv run --group logo)`.

  (FR-039, depends on T003)
- [ ] T029 [US5] Run quickstart §5:
  - `uv run --group logo scripts/make_logo.py` leaves `git status --porcelain app/static/img/logo`
    empty;
  - `uv lock --check` passes;
  - after `uv sync --locked`, `import PIL` fails.

  Run `uv run pytest tests/integration/test_logo.py`. (FR-020, FR-023, SC-006, SC-007, depends on
  T027, T028)

**Checkpoint**: The image set is reproducible, exact and documented.

---

## Phase 8: User Story 6 - Nothing of the old mark is left (Priority: P3)

**Goal**: No code, test or document serves, draws, links or describes the spark, its tile or the old
favicons, and the guidelines describe the new mark.

**Independent Test**: The leftover search in quickstart §2 finds nothing. The guidelines and README
read correctly (quickstart §6).

### Tests for User Story 6 ⚠️

- [ ] T030 [P] [US6] In `tests/integration/test_logo.py`, add `test_nothing_refers_to_the_old_mark`.
  - Build the five forbidden strings from parts, so the test does not match itself: `"/static/img/"
    + "favicon.svg"`, `"/static/img/" + "favicon-32.png"`, `"/static/img/" +
    "apple-touch-icon.png"`, `"logo-mark-" + "tile"` and `"logo-mark-" + "spark"`.
  - Scan every text file under `app/` and `tests/`: skip binary files, `__pycache__` and compiled
    `.mo` catalogues.
  - Assert that no file contains any of them, naming each offending path.

  Also check that `/static/img/favicon.svg` answers 404 to `client`. (FR-028, FR-029, FR-036, SC-008)

### Implementation for User Story 6

- [ ] T031 [US6] In `docs/requirements/ui-guidelines.md`:
  - **Introduction**: after the sentence naming milestone 10's mockup as the approved look, add that
    the logo mark was replaced in milestone 12.7, linking
    [`specs/012.7-new-logo/design-approval.md`](../../specs/012.7-new-logo/design-approval.md).
  - **§3 Colour**: `--sc-accent`'s role changes from "Logo mark, highlights" to "Highlights".
  - **§4 Layout**:
    - The top bar item says that the logo mark (the emblem, in light ink) is 2rem from 768 px and the
      touch-target size (44 px) below.
    - Replace the "Last measured in milestone 12.5…" paragraph with "Last measured in milestone
      12.7…": the 44 px mark keeps the top bar one 64 px row at 360 px and 375 px, signed out and with
      a role shown, in Ukrainian and English. Give the frame's bottom on the teacher and administrator
      area pages, taken from the **Measurements** table in `specs/012.7-new-logo/quickstart.md` §3
      (filled in by T013), against the 176 px of `--sc-frame-clearance-tabs` and a quarter of a
      375 × 667 screen.
  - **§5 Icons and identity**:
    - `logo_mark(size, theme, top_bar)` shows the emblem as an image (`app/static/img/logo/`, made by
      `scripts/make_logo.py`), no longer inline SVG.
    - On the top bar it is always light ink, 2rem from 768 px and 44 px below.
    - Elsewhere it follows the theme: dark ink in Light, light ink in Dark, and a `<picture>` for
      Device, with no script.
    - Each size is sharp at 1×–3× density.
    - `icon(name)` stays inline SVG.
  - Check §8 and §9 for wording that names the spark or the tile (none today).

  (FR-038, depends on T013, T025)
- [ ] T032 [P] [US6] In `README.md`'s project tree:
  - the `static/` line's `img/` reads `img/ (flags; logo/: the emblem images, favicons, touch and
    manifest icons and the web manifest, generated by scripts/make_logo.py)`;
  - add a `docs/brand/` line next to `├── docs/requirements/`: `├── docs/brand/   # logo-source.png:
    the emblem's source image, read by scripts/make_logo.py`.

  Search `README.md` for "favicon" and "spark" and correct anything stale. (FR-039, depends on T028)
- [ ] T033 [US6] Run the leftover searches of quickstart §2 and `uv run pytest
  tests/integration/test_logo.py`. Then confirm with `git diff main -- specs/010-design-system-ui-guidelines
  specs/010.1-loading-feedback-pinned-frame specs/012.5-ukrainian-localisation` that no delivered
  milestone's spec changed. (FR-040, depends on T030–T032)

**Checkpoint**: All six stories are complete.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: The whole suite, style, the milestones document and the final quickstart pass.

- [ ] T034 Run `uv run ruff check .` and `uv run ruff format --check .` (the script included), then
  `uv run pytest` and `TEST_POSTGRES_URL=… uv run pytest` (the `sc-pg` container). Everything passes,
  with no test skipped because of this milestone. (FR-037, SC-010)
- [ ] T035 In `docs/requirements/milestones.md`, once the approval (T026) is recorded and the PR is
  ready:
  - move 12.7 from Upcoming to Delivered, compacted like 12.5 and 12.6. Its `_Spec:_` link is
    `specs/012.7-new-logo/spec.md`, and its summary is a few sentences: the emblem in the top bar
    (44 px on phones), the theme-following mark, the icons and the manifest opening in the browser, the
    script and its `logo` group, the approval;
  - update the 12.x group paragraph if it describes 12.7 as upcoming.

  (FR-040)
- [ ] T036 Run [quickstart.md](./quickstart.md) §1–§6 end to end and tick each item. This includes
  §3.9: build and run the Docker image and check the manifest's and the ICO's `content-type` from the
  container (research R6). Leave the branch ready for a pull request.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: depends on Setup. T002 → T003. T004 → T005, T006 and T007 → T008.
  T002/T003 and T004–T008 can proceed side by side, but T008's pages only show the images once T003
  has run.
- **US1 (Phase 3)** and **US2 (Phase 4)**: depend on Phase 2. They are independent of each other,
  except that both edit `tests/integration/test_layout.py` (T009 and T015), so run those two tasks
  one after the other.
- **US3 (Phase 5)**: depends on Phase 2 only.
- **US4 (Phase 6)**: depends on US1–US3, because the screenshots show their result. Within those
  stories, it waits for the automated tests and the checks T013 and T023, but not for the phone check
  T019.
- **US5 (Phase 7)**: depends on Phase 2. T027 shares `test_logo.py` with T014 and T030, so it runs
  after T014.
- **US6 (Phase 8)**: T030 depends on T017 (the old files deleted) and T007 (the old classes deleted).
  T031 needs T013's measurements (in quickstart.md's **Measurements** table) and T025's approval
  file. T032 follows T028 (same file).
- **Polish (Phase 9)**: after all stories. T035 after T026.

### Within Each User Story

- Tests are written first and must fail before the implementation task.
- Tests that share a file run one after the other: `test_layout.py` (T009, T015); `test_logo.py`
  (T014, T027, T030); `README.md` (T028, T032).
- Checks by hand come after the automated tests of the same story pass.

### Parallel Opportunities

- **Phase 2**: T005, T006 and T007 after T004 (different files).
- **US1**: T009 ∥ T010.
- **US2**: T014 ∥ T015 (T015 after T009).
- **US3**: T020 ∥ T021.
- US1, US2, US3 and US5's test tasks can be spread across developers once Phase 2 is done, as long
  as tasks in the same file are serialised.

## Parallel Example: User Story 1

```text
Task: "T009 [US1] Rewrite assert_identity for the image mark in tests/integration/test_layout.py"
Task: "T010 [US1] Add the top bar mark and role offset tests in tests/unit/test_frame_stylesheet.py"
```

## Parallel Example: User Story 3

```text
Task: "T020 [US3] logo_mark markup and refusals in tests/unit/test_templates.py"
Task: "T021 [US3] Identity inks per theme in tests/integration/test_component_gallery.py"
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (T001) and Phase 2 (T002–T008): the images and the image-based mark.
2. Phase 3 (T009–T013): the top bar at both sizes, measured by hand.
3. **Stop and validate**: the emblem identifies the application in the top bar.

### Incremental Delivery

1. + US2 (T014–T019): the tab and home-screen icons; the old icons are gone.
2. + US3 (T020–T023): the gallery's theme-following marks are proven.
3. + US4 (T024–T026): screenshots and the product owner's approval. **The merge gate.**
4. + US5 (T027–T029) and US6 (T030–T033): exactness, reproducibility, cleanup and documentation.
5. Polish (T034–T036), then the pull request.

## Notes

- [P] tasks touch different files and have no dependency on incomplete tasks.
- Commit after each task or logical group. The image folder is committed only as the script's output
  (T003, or after a change requested in T026).
- No catalogue change: no user-facing message is added or changed (research R12).
- Specs of delivered milestones are records of their time and are not edited.
