# Research: The New Logo (Milestone 12.7)

Every decision below was checked against branch `012.7-new-logo` at `0f0839e` (milestone 12.6 merged in
`cb0e188`). The Technical Context has no open questions: the stack, storage and test tools are
unchanged. The only new libraries, Pillow and numpy, belong to a development script and never reach the
application or its image (R8).

What the code holds today:

- `components/icons.html`: `logo_mark(size)` draws an inline SVG with a `logo-mark-tile` rect and two
  `logo-mark-spark` paths.
- `layouts/base.html`: links `/static/img/favicon.svg`, `/static/img/favicon-32.png` and
  `/static/img/apple-touch-icon.png`.
- `components/frame.html`: `top_bar` calls `logo_mark()` (md) inside the brand link.
- `pages/admin/components.html`: the gallery's **Identity** shows `logo_mark("lg")`, `("md")` and
  `("sm")`.
- `app/static/img/logo/` holds the first prepared set (19 files). Of these, `logo-header-32/64/96.png`
  (light ink), the favicons, the touch and manifest icons and `site.webmanifest` are close to what is
  needed. `logo-{dark,light}-{256,512,1024}.png` and `og-image.png` are not used.
- `scripts/make_logo.py` takes `SRC OUT_DIR WORK_DIR`, imports `cv2`, writes a debug master into
  `WORK_DIR`, and fails `ruff format --check`.

## R1. The emblem images: which sizes, which inks, which names

**Decision**: The mark is shown at four CSS sizes: `sm` 1.5rem (24 px), `md` 2rem (32 px), `lg` 4rem
(64 px), and the top bar's size 2.75rem (44 px), at every width (revised 2026-11-17 after the design
review's round 1; until then the top bar's mark was `md` from 768 px). Each is needed at 1×, 2× and 3×
density.

| Shown as | 1× | 2× | 3× | Inks |
|---|---|---|---|---|
| `sm` | 24 | 48 | 72 | dark, light |
| `md` (on a page) | 32 | 64 | 96 | dark, light |
| `lg` | 64 | 128 | 192 | dark, light |
| top bar, every width | 44 | 88 | 132 | light |

The pixel sizes are deduplicated per ink (64 serves `md` 2× and `lg` 1×), giving:

- **Light ink**, 11 files: `logo-light-{24,32,44,48,64,72,88,96,128,132,192}.png`.
- **Dark ink**, 8 files: `logo-dark-{24,32,48,64,72,96,128,192}.png`.

Each is a square, transparent PNG with the emblem filling it edge to edge, as the first set's
`logo-header-*` and `logo-*-256` were. One naming scheme, `logo-{ink}-{px}.png`, replaces
`logo-header-*`: the top bar's mark is simply the light ink.

The revision changes no file: light ink at 32, 64 and 96 px still serves `md` in **Dark**, and 44, 88
and 132 px already existed for the phone.

The light ink is only used on dark backgrounds (the top bar, and the page in **Dark**). The dark ink is
only used on light backgrounds (the page in **Light**). The top bar's 44 px sizes exist only in light
ink, because the bar is dark in both themes.

**Rationale**: Spec FR-009 and FR-018 ask for every displayed size at 1×, 2× and 3×, in both inks
wherever the mark can appear in both, and nothing else. Exact pixel sizes let the browser draw without
resampling, which matters for a fine engraving at 24–44 px. The CSS sizes assume 1rem = 16 px: the
stylesheet sets Pico's `--pico-font-size: 100%`. Body text grows to 18 px from 1024 px, but that does
not change `rem` units.

**Alternatives considered**:
- *One large image per ink, scaled by the browser.* Browsers downscale an engraving poorly, and every
  page would download a large file. This is what milestone FR-009 rules out. Rejected.
- *Keep the `logo-header-*` names for the top bar.* That gives two names for the same light-ink
  images. Rejected.
- *Add 4× images.* No common screen needs them; 3× is the milestone's limit. Rejected.
- *The top bar's mark at `md` (2rem) from 768 px.* The first decision. The product owner's review,
  round 1, found the engraving barely visible at 32 px beside the 44 px language switch. Rejected
  2026-11-17.

## R2. How the browser picks the file it needs

**Decision**:

- **A mark on a page background** (`sm`, `md`, `lg`): `<img>` with **density descriptors**, for
  example `src="logo-dark-24.png" srcset="logo-dark-24.png 1x, logo-dark-48.png 2x,
  logo-dark-72.png 3x"`. Its `width` and `height` attributes are the 1× size.
- **The top bar's mark**: one `<img>` with **density descriptors** over the light-ink files
  `logo-light-44.png 1x, logo-light-88.png 2x, logo-light-132.png 3x`, `src` `logo-light-44.png` and
  `width`/`height` 44. CSS sets the same size, `var(--sc-touch-target)` (R5). The attributes give the
  aspect ratio and reserve the space before the image loads. (Revised 2026-11-17: the mark was 2rem
  from 768 px, so it had width descriptors `32w … 132w` and `sizes="(min-width: 768px) 2rem,
  2.75rem"`.)

The browser downloads only the one candidate that matches the slot's size times the screen's density.

**Rationale**: Spec FR-009 and FR-010. Density descriptors are the simplest fit for a fixed-size image,
and since the revision every mark, the top bar's included, has one size at every width.

**Alternatives considered**:
- *Keep the width descriptors with `sizes="2.75rem"`.* It works, but says in two attributes what one
  density list says. Rejected.
- *CSS `image-set()` backgrounds.* The mark would no longer be an image element with set dimensions
  (FR-008, FR-010). Rejected.

## R3. How a mark on the page follows the theme without JavaScript

**Decision**: The server already knows the theme: `theme` (light, dark or device) is read from the
`sc_theme` cookie and given to every template (milestone 10). The component renders by it:

- **Light**: a plain `<img>` with the dark-ink files.
- **Dark**: a plain `<img>` with the light-ink files.
- **Device**: `<picture>` with `<source media="(prefers-color-scheme: dark)" srcset="…light-ink…">`
  around the dark-ink `<img>`.

The browser re-evaluates a `<source>`'s media query when the device's colour scheme changes, so the
mark switches live, also when the scheme is emulated in the developer tools. The top bar's mark is
always light ink, whatever the theme.

**Rationale**: This is the same rule as the colour tokens (an explicit choice wins, and **Device**
follows the system: ui-guidelines §9), with no script and no flash (FR-011). It loads exactly one file,
because only the chosen candidate is fetched (FR-009).

**Alternatives considered**:
- *Two `<img>` elements, one hidden by the theme CSS.* Browsers download hidden images too (unless
  lazy, and lazy loading would delay a visible mark). This breaks "only the file it needs". Rejected.
- *`<picture>` with `prefers-color-scheme` alone.* It ignores an explicit **Light** or **Dark** that
  differs from the device's setting. Rejected.
- *A CSS filter that inverts one ink.* It changes the engraved shading and the silver tone, and would be
  an unreviewed rendering. Rejected.

## R4. The `logo_mark` component's interface

**Decision**: `logo_mark(size="md", theme=none, top_bar=False)` in `components/icons.html`:

- `size` must be `sm`, `md` or `lg`. Any other value is a `template_error`, as today (FR-007).
- `top_bar=True` draws the top bar's mark (R2): light ink, 44 px, class
  `logo-mark logo-mark-top-bar`. It takes no size: `size` stays at its default, and `sm` or `lg` is a
  `template_error`. `theme` is not read. (Revised 2026-11-17: it took `size="md"`, the size it had from
  768 px.)
- Otherwise `theme` must be `light`, `dark` or `device` (R3); a missing or unknown theme is a
  `template_error`. The class is `logo-mark logo-mark-{size}`.
- Every variant renders `alt=""` and `aria-hidden="true"` on the `<img>`. That makes it decorative
  (FR-005): the brand link's name stays the wordmark text, which is hidden only visually below 768 px.
- Paths come from one place in the macro: `/static/img/logo/logo-{ink}-{px}.png`, with the pixel
  sizes of R1.

Callers:

- `frame.html` `top_bar`: `logo_mark(top_bar=True)`.
- The gallery: `logo_mark("lg", theme)`, `logo_mark("md", theme)` and `logo_mark("sm", theme)`. It
  passes the context's `theme` explicitly, because `icons.html` is imported without context.

**Rationale**: The milestone keeps three sizes and the error for any other size, so the top bar's phone
size cannot become a fourth size of the component. A flag that only the top bar sets keeps the two uses apart. Making
`theme` required off the top bar means that a future page cannot silently get the wrong ink.

**Alternatives considered**:
- *Read `theme` from the template context.* `icons.html` is imported without context, in `frame.html`
  and in the gallery. Changing every import to `with context` hides a dependency that an explicit
  argument shows. Rejected.
- *A separate `top_bar_mark()` macro.* That gives two components for one mark, and the milestone names
  `logo_mark` as the top bar's mark too. Rejected.
- *A default `theme="device"`.* It is wrong whenever an explicit theme differs from the device's.
  Rejected.

## R5. The top bar's mark in the stylesheet

**Decision**: In `app.css`, delete `.logo-mark-tile` and `.logo-mark-spark`. The other rules:

- `.logo-mark` stays `display: block; flex: none`. `.logo-mark-sm`, `-md` and `-lg` keep 1.5rem, 2rem
  and 4rem (width and height).
- New `.logo-mark-top-bar` is `width/height: var(--sc-touch-target)`, at every width; no media query
  changes it (revised 2026-11-17: it was `2rem` from 768 px).
- Below 768 px, the role label's offset beside the mark follows the same width:
  - `.brand-with-role + .brand-role` gets `margin: 0 0 0 calc(var(--sc-touch-target) + var(--sc-space-1))`.
  - The base `.brand-role` gets `padding-left: calc(var(--sc-touch-target) + var(--sc-space-1))`.
    Today that rule is always overridden, because a role label is always preceded by
    `.brand-with-role`, but it still states the old width. From 768 px both offsets are reset, as
    today, because the label follows the wordmark in the flex row.
- No other offset in `app.css` assumes the mark's width: the search for `2rem` finds only these two and
  `.logo-mark-md`.
- The top bar's container keeps `min-height: 4rem` and `padding-block: var(--sc-space-1)`. A 44 px mark
  in the 44 px `.brand` (`min-height: var(--sc-touch-target)`) plus 2 × 8 px padding is 60 px, so the
  bar stays one 64 px row (FR-003). From 768 px the mark is 12 px wider than before, beside the wordmark,
  the role label, the language switch and the user menu: that the row does not wrap at 768 px is
  checked by hand (R11).
- The icons comment is rewritten: the logo mark is an image in light ink on the top bar, and follows the
  theme elsewhere.

**Rationale**: FR-002 and FR-004. `test_stylesheet.py` forbids `--sc-*` properties outside the token
block and pixel literals outside it. A per-breakpoint custom property on `.top-bar` would break the
first rule; the mark has one size, so the token is used directly.

**Alternatives considered**:
- *A new token `--sc-brand-mark`, redefined in a media query.* Tokens are defined once, in the token
  block. Rejected.
- *Size the mark with `width/height` attributes alone.* Every other mark is sized by its class, and the
  stylesheet test reads the class. Rejected.

## R6. Icons, links and the manifest

**Decision**:

- **Files** (written by the script, R7): `favicon.ico` (16, 32, 48 px), `favicon-16.png`,
  `favicon-32.png`, `favicon-48.png`, `apple-touch-icon.png` (180 px, opaque RGB), `icon-192.png`,
  `icon-512.png`, `icon-maskable-512.png` and `site.webmanifest`. All are under
  `/static/img/logo/`.
- **Appearance**:
  - The favicons are a rounded `#16337a` tile with the light-ink emblem and minimal padding.
  - The Apple touch icon and the manifest icons are full-bleed `#16337a` squares.
  - The maskable icon keeps the emblem within the central 80 % safe-zone circle (padding 15 % a side).

  These are the first script's parameters, which the approval round judges.

  *Changed after round 3 (R15):* every icon shows the letters ЯНМ alone, without the ornament, and the
  favicons' padding is 4 % a side; the other paddings stay.
- **Links** in `layouts/base.html`, replacing the three old ones:

  ```html
  <link rel="icon" href="/static/img/logo/favicon.ico" sizes="16x16 32x32 48x48">
  <link rel="icon" href="/static/img/logo/favicon-16.png" sizes="16x16" type="image/png">
  <link rel="icon" href="/static/img/logo/favicon-32.png" sizes="32x32" type="image/png">
  <link rel="icon" href="/static/img/logo/favicon-48.png" sizes="48x48" type="image/png">
  <link rel="apple-touch-icon" href="/static/img/logo/apple-touch-icon.png">
  <link rel="manifest" href="/static/img/logo/site.webmanifest">
  ```

- **Manifest** (UTF-8, `ensure_ascii=False`):
  - `name`: «Студентські змагання»
  - `start_url`: `/`
  - `display`: `browser`
  - `theme_color` and `background_color`: `#16337a`
  - `icons`: the three manifest icons, the maskable one with `"purpose": "maskable"`

  There is no `short_name`: the name is short enough, and a second name would be another string to
  keep in step. There is no `id` or `scope`: `start_url` `/` gives both their defaults.
- **Types**: `StaticFiles` takes types from Python's `mimetypes`. Python 3.13's built-in table maps
  `.webmanifest` to `application/manifest+json`, `.ico` to `image/x-icon` and `.png` to `image/png`. A
  system `mime.types` may map `.ico` to `image/vnd.microsoft.icon` instead (Debian and Ubuntu do), which
  is why both are accepted (FR-017). No registration in `main.py` is needed. The test runs on macOS and
  on the Ubuntu CI runner and guards it there.

  The runtime image (`python:3.13-slim-bookworm`) is not covered by the test suite. The accepted risk
  is that its system table maps `.webmanifest` differently. That is unlikely: Debian's table, where
  installed, agrees with Python's. A one-off check by hand covers it: build the image and request the
  manifest from the running container (quickstart §3.9). Adding this check to the CI `image` job would
  go beyond the milestone, so it is not done.
- **Public**: `/static` is a mount, not a route, and is served to everyone (`core/auth.py`), so a
  visitor who is not signed in gets every file, and so does the browser's credential-less manifest
  fetch.

**Rationale**: FR-013–FR-017. Listing each favicon with its exact `sizes` lets a browser choose the
nearest size. The ICO covers browsers and tools that ask for an ICO.

**Alternatives considered**:
- *`sizes="any"` on the ICO.* That value is meant for a scalable icon, and there is none (no SVG, by
  the milestone). Rejected.
- *Generate the manifest from a route, to translate its name.* The manifest is read once, when the icon
  is added, and every page opens in Ukrainian. A route would also have to be public and declared.
  Rejected.
- *Register `.webmanifest` in `main.py`.* Python already maps it, so registering it would be dead code.
  Rejected; the test would catch a platform where it is missing.

## R7. The script without OpenCV

**Decision**: Rewrite `scripts/make_logo.py` as a small module with a `main()` and
`if __name__ == "__main__"`, which:

1. **Takes no arguments.** It finds the repository root from its own path, reads
   `docs/brand/logo-source.png` and writes to `app/static/img/logo/`. It writes no work files: the
   first version's `WORK_DIR` debug master is dropped.
2. **Keeps the first version's steps and parameters, but with Pillow and numpy:**
   - It flattens the source onto white, then crops to the ink (`L < 240`) plus 3 px.
   - It upscales ×2 three times. Each step is a Pillow `resize(LANCZOS)` of the float (`F` mode) image,
     followed by an unsharp mask (amount 0.6, σ 1.2).
   - It smooths with an edge-preserving filter (window 7, colour σ 18, space σ 5), then applies a final
     unsharp mask (0.8, σ 2.0).
   - It applies levels (25–232, γ 0.9) and pads the result to a square master.
   - It makes the letters ЯНМ solid inside the letter area (R13, added after the design review's
     round 2), before any image is resized from the master.
3. **Replaces the OpenCV operations with:**
   - **Resizing**: Pillow `Image.resize` on `F` images, which supports Lanczos. This was checked with
     Pillow 11.1 and numpy 2.1.
   - **Gaussian blur**: a separable numpy convolution with a normalised 1-D kernel (radius ⌈3σ⌉) and
     edge padding. Pillow's `GaussianBlur` rejects `F` images, and blurring 8-bit data would lose the
     precision the sharpening relies on.
   - **Bilateral smoothing**: numpy over the 7 × 7 window's 49 shifted copies of the padded image. Each
     copy is weighted by a spatial Gaussian and by a range Gaussian of its difference from the centre,
     then normalised. On a ~1,700 px master this takes seconds.
4. **Writes exactly the files of R1 and R6,** no more. Emblem images at 48 px and below get the first
   version's alpha sharpening for small sizes. The favicons get it as before.
5. **Owns its folder.** After writing, it deletes any file in `app/static/img/logo/` that it did not
   write. That removes `og-image.png`, `logo-{dark,light}-{256,512,1024}.png` and `logo-header-*` in
   this milestone, and keeps the folder exact afterwards (FR-019, FR-020).
6. **Prints** the crop and the list of files written, and passes `ruff check` and
   `ruff format --check`.

The script's output is committed. A second run on the same machine leaves `git status` clean for
`app/static/img/logo/` (quickstart §5).

**Rationale**: FR-020–FR-024. Without arguments, the milestone's command
(`uv run --group logo scripts/make_logo.py`) is the whole interface. Owning the folder makes "only what
is used" hold by construction, not by memory.

**Risks**:
- The Pillow and numpy filters are not bit-identical to OpenCV's (Lanczos kernels and border handling
  differ slightly). The images will look the same but differ in bytes from the first set. The approval
  round (R10) reviews the regenerated set, not the first one.
- Float results may differ in the last bit between machines. Reproducibility is therefore checked on the
  machine that generated the committed set (quickstart §5), not in CI, which does not install the
  group (R8).

**Alternatives considered**:
- *Keep OpenCV.* The milestone removes it: it is a large binary dependency for three filters. Rejected.
- *SciPy's `ndimage` for the filters.* That would be a third library; the milestone allows Pillow and
  numpy only. Rejected.
- *Clear the folder before writing.* A failed run would leave the folder empty. Deleting strays after a
  successful write is safer. Rejected.

## R8. The `logo` dependency group

**Decision**: In `pyproject.toml`, add `logo = ["numpy>=2.1", "pillow>=11.1"]` under
`[dependency-groups]`, next to `dev`, and run `uv lock`. `[tool.uv] default-groups` is not set, so the
defaults stay `["dev"]`:

- CI's `uv sync --locked` installs the project and `dev`;
- the image's `uv sync --locked --no-dev` installs the project alone;
- neither installs `logo`.

`uv run --group logo scripts/make_logo.py` adds the group for that run. OpenCV was never in the lock
file: the first version ran with ad-hoc packages, so nothing needs to be removed from it.

To verify, after `uv sync --locked`, `uv run python -c "import PIL"` fails. `uv lock --check` passes
(quickstart §5).

**Rationale**: FR-023 and the constitution's uv rule: one manifest and one lock file, no
requirements files. The application gains no runtime dependency, so Principle II's justification rule
does not apply.

**Alternatives considered**:
- *Put Pillow and numpy in `dev`.* CI would install them for nothing. Rejected.
- *`uv run --with pillow --with numpy`.* The versions would be unlocked, against the uv rule and the
  milestone. Rejected.

## R9. Tests

**Decision**:

- **`tests/integration/test_logo.py`, the solid letters** (added after round 2): R14.
- **`tests/integration/test_layout.py`, the identity tests** (rewritten, same four pages: sign-in,
  signed-in pages, 404, refusals):
  - `assert_identity` finds exactly one `img.logo-mark` in the brand link, with `alt=""` and
    `aria-hidden="true"`, `logo-mark-top-bar`, and its `src` and `srcset` under `/static/img/logo/` in
    light ink only.
  - The link's text is the application's name in the page's language. The test checks it in Ukrainian
    («Студентські змагання», with the `sc_lang=uk` cookie) and in English ("Student Competitions",
    the test suite's default since milestone 12.5), signed out and signed in.
  - The page links the six icon and manifest URLs of R6.
- **A new `tests/integration/test_logo.py`**:
  - Each icon URL and the manifest answer 200 to a signed-out client, with the types of FR-017 (ICO:
    either type).
  - The manifest's JSON has `name` «Студентські змагання», `start_url` `/`, `display` `browser`, both
    colours `#16337a`, and three icons that each answer 200 as `image/png`.
  - Only what is used: render the sign-in page and the gallery in **Light** and in **Dark**, read the
    manifest, and collect every `/static/img/logo/…` URL. That set must equal the folder's listing
    (FR-018, FR-019). This test catches a stray file and a missing one.
  - No leftovers: no file under `app/` or `tests/` contains the three old paths, `logo-mark-tile` or
    `logo-mark-spark`. The test builds those strings from parts, so it does not match itself.
- **`tests/unit/test_templates.py`**, beside the other components' refusals (its `render` helper and
  `TemplateRuntimeError`): `logo_mark` raises the template error for an unknown size, for
  `top_bar=True` with a size other than `md`, and for a missing or unknown theme off the top bar. The
  same file checks each variant's markup (contracts/components.md).
- **`tests/integration/test_component_gallery.py`**: the **Identity** section has three marks with
  classes `logo-mark-lg`, `-md` and `-sm`:
  - **Light**: dark-ink files only, plain `<img>`.
  - **Dark**: light-ink files only.
  - **Device**: a `<picture>` whose `<source media="(prefers-color-scheme: dark)">` holds light ink and
    whose `<img>` holds dark ink.

  The section's existing text check keeps `--sc-accent`.
- **`tests/unit/test_frame_stylesheet.py`** (new tests, using its block helpers):
  - At the top level, `.logo-mark-top-bar` is sized by `var(--sc-touch-target)`.
  - No `@media` block changes its `width` or `height` (revised 2026-11-17: it was `2rem` from 768 px).
  - The top-level `.brand-with-role + .brand-role` margin and `.brand-role` padding-left use
    `calc(var(--sc-touch-target) + var(--sc-space-1))`.
  - No `2rem` offset remains in either.
- **Existing stylesheet checks** cover the rest unchanged: every class used is defined and every
  defined class is used, so `logo-mark-tile` and `-spark` must leave both. No literal colour or pixel
  value is outside the tokens. Nothing is loaded from another site.

The whole suite runs on both engines with `TEST_POSTGRES_URL` set. Ruff covers the script.

**Rationale**: FR-031–FR-037 map one to one onto the milestone's _Test:_ line. The "only what is used"
comparison is the automated half of SC-006. The other half, reproducibility, needs the `logo` group and
stays a by-hand check (R7).

**Alternatives considered**:
- *Test the script in CI.* CI would have to install the group, against FR-023. Rejected.
- *Hard-code the expected file list in the test.* That would be a second copy of R1 to keep in step.
  Deriving the list from the rendered pages tests what is actually linked. Rejected.

## R10. The design approval

**Decision**:

- **Screenshots.** Taken after the implementation and the regenerated images are committed, with
  headless Playwright run ad hoc (`uv run --no-project --with playwright`, not a dependency; milestone
  10 D1). They are viewport crops, to keep them small:
  - the top bar on `/login` and on `/teacher/students`;
  - the gallery's **Identity** section on `/admin/components#identity`;
  - each at 375 px and 1280 px, in **Light** and **Dark**.

  That is 12 PNGs.
- **The browser tab.** Headless browsers draw no tab, so the tab screenshots are taken by hand in a
  desktop browser in its light and dark appearance at 1280 px. At 375 px, a phone's (or phone
  simulator's) tab overview stands in. That is 4 more images.
- **Storage.** All 16 images are committed in `specs/012.7-new-logo/screenshots/`, named
  `{view}-{width}-{theme}.png`.
- **The record.** `specs/012.7-new-logo/design-approval.md` follows milestone 10's form: approver,
  screenshots, the gate ("no merge before an approving round"), and a review log with date, round,
  commit, changes requested, changes made and status. Changes asked for are made in a new commit and
  give a new round with new screenshots.
- **A proposal sheet.** When a requested change has more than one reasonable answer, the options may
  be shown on one sheet before the script makes them, as in round 2:
  `screenshots/round-2-letters-options.png`, with the real top bar served with each option's images.
  The sheet records the choice; the next round's 12 screenshots show the script's output. Round 3's
  sheet, `screenshots/round-3-small-icons-options.png`, shows the icons in a drawn browser tab (light
  and dark, at 2× and 1×), on a drawn phone home screen (iOS and Android) and pixel for pixel; it is made
  from the icon files themselves, since a headless browser draws no tab.
- Milestone 10's `design-approval.md` is not edited.

**Rationale**: FR-025 and FR-026, and milestone 10 user story 1 scenario 3. Unlike milestone 10, there
is no mockup: the change is small, and the real pages are the most faithful thing to approve.
Committing the images makes the approval checkable later.

**Alternatives considered**:
- *Keep the screenshots in the git-ignored `screenshots/` folder.* The approval would then point at
  nothing. Rejected.
- *A mockup before implementation.* That doubles the work for one image swap, and the source emblem is
  already the product owner's choice. Rejected.

## R11. What is checked by hand

**Decision**: [quickstart.md](./quickstart.md) §3 lists the by-hand checks of FR-027, in the manner of
milestone 10.1:

- the emblem is sharp in the bar and the gallery (the screenshots);
- the bar is one 64 px row at 360 px, 375 px, 768 px and 1280 px, with a role and signed out, in
  Ukrainian and English (16 combinations, measured with Playwright's bounding box);
- the frame's bottom on an area page, measured again at 360 × 640 and 375 × 667 for the teacher and
  the administrator in both languages. It must stay under 176 px (`--sc-frame-clearance-tabs`), and the
  numbers go into ui-guidelines §4 ("Last measured in milestone 12.7");
- **Device** in the gallery, switched in the developer tools' "Emulate prefers-color-scheme";
- the browser tab and a phone's home screen: add to home screen, open it, and see the address bar.

The bar's height cannot change (R5), so the frame should measure as in milestone 12.5 (153 px and
109 px). If a number changes, the guidelines take the new one.

## R12. Cleanup and documentation

**Decision**:

- **Delete** `app/static/img/favicon.svg`, `favicon-32.png` and `apple-touch-icon.png`, with their
  links. The flags stay in `app/static/img/`.
- **Rewrite** the comment at the top of `components/icons.html`: the logo mark is the emblem image (this
  milestone's contracts), and it no longer mentions `favicon.svg`. Also rewrite the icons comment in
  `app.css` (R5).
- **`--sc-accent` and `--sc-on-accent`** stay, with their gallery swatches. The guidelines' palette row
  changes from "Logo mark, highlights" to "Highlights".
- **`docs/requirements/ui-guidelines.md`**:
  - The introduction adds a sentence that the logo mark was replaced in milestone 12.7, with a link to
    `specs/012.7-new-logo/design-approval.md`.
  - §4 adds a top bar item: the mark is 44 px (the touch target) at every width. The "Last measured" paragraph
    is replaced by milestone 12.7's numbers.
  - The **Icons and identity** section says that `logo_mark(size, theme, top_bar)` shows the emblem
    image, light ink on the top bar, and that elsewhere it follows the theme (picture for **Device**,
    no script); and that the emblem's letters are solid while its ornament is engraved (R13).
  - §3 changes the palette role of `--sc-accent`. §8's "beside the logo" wording stays true.
- **`README.md`**:
  - The tree's `static/` line names `img/` (flags) and `img/logo/` (the emblem images, icons and web
    manifest, generated).
  - The `scripts/` list gains `make_logo.py` (the logo images from `docs/brand/logo-source.png`).
  - A `docs/brand/` entry is added (the emblem's source image).
  - A short "Logo images" paragraph gives `uv run --group logo scripts/make_logo.py` and says that its
    output is committed and never edited by hand, and that the letter area in the script belongs to the
    current source image: a new source means drawing it again (R13).
- **`docs/requirements/milestones.md`**: 12.7 moves to Delivered, compacted, when it ships. The
  Delivered milestone 10 summary is checked for the spark: it has none today.
- **No catalogue change**: no user-facing message changes. The application's name is already in both
  catalogues, and the manifest's name is a static file.

**Rationale**: FR-028–FR-030 and FR-038–FR-040, and the constitution's documentation gate.

## R13. Solid letters (design review, round 2)

Added on 2026-11-17, after the product owner chose option **B** of
[round-2-letters-options](./screenshots/round-2-letters-options.png) (spec Clarifications, round 2;
FR-041, FR-042).

**Decision**: The script makes the letters ЯНМ solid with a **letter area** held as data and a
**lift** of the coverage inside it. The values below are the ones the reviewed sheet was made with.

- **Letter area, in the source's pixels** (`docs/brand/logo-source.png`, 311 × 311):
  - **Band**: the rectangle `(58, 116)–(248, 192)` (x0, y0, x1, y1), the row of letters.
  - **Ink**: inside the band, the source's ink (`L < 215` on the white-flattened source), closed with a
    3 × 3 maximum then minimum filter so the light inline inside each stroke is not a gap.
  - **Less the ornament inside the band**, as polygons (filled with 0):
    - left side flourish `(48,141) (79,141) (79,165) (48,165)`;
    - right side flourish `(239,141) (265,141) (265,165) (239,165)`;
    - fleur and dots between Я and Н `(121,121) (131,121) (131,189) (121,189)`;
    - dots inside Н above the bar `(149,122) (158,122) (158,146) (149,146)`;
    - dots inside Н below the bar `(149,159) (158,159) (158,190) (149,190)`;
    - fleur and dots between Н and М `(173,121) (187,121) (187,189) (173,189)`;
    - fleur between М's peaks `(203,110) (221,110) (214,149) (209,149)`.

  The boxes sit 2 px inside the panels between the stems, so the stems keep their dark outline. They
  were checked on 11× gridded overlays of the source. The horizontal rod through the panels is
  ornament; Н's own crossbar, between its stems, is letter.
- **Into the master**: the area goes through the same crop as the coverage (the ink plus 3 px), is
  scaled ×8 with bilinear resampling, blurred with the script's Gaussian (σ 3 master px) to a soft
  0–1 mask `L`, and placed in the square master as the coverage is.
- **The lift**: with coverage `c` (0 paper, 1 full ink), the master becomes
  `L · min(c / 0.45, 1) + (1 − L) · c`. Inside the letters, any ink at or above 45 % coverage is full
  ink, so the engraved shading stops letting the background through, while their outline and inline
  (no ink) keep their shape. Outside, nothing changes.
- **Everything follows**: the emblem images in both inks and the icons are all made from this master,
  so every file changes and the folder keeps the same 28 names. The small-size sharpening (48 px and
  below) still applies after.

**Rationale**: The source has one layer: the letters and the ornament share its strokes, its width
of stroke and its shading, so they cannot be told apart by measurement. A stroke-width filter (a
morphological opening at 5, 7 and 9 px) kept the loops and the fleurs-de-lis as well as the letters
and ate the letters' serifs. A fixed area, drawn once for this source, is exact and reviewable. The
lift, rather than filling the area with ink, keeps each letter's drawn outline: a flat fill of the
area made rough-edged white blocks (tried first, rejected on sight).

**Alternatives considered**:
- *Option A, as merged.* Rejected in round 2: the background shows through the letters.
- *Option C, letters opaque but engraved* (a silver-grey backing under the engraving). At 44 px it
  looks almost as merged. Rejected in round 2.
- *A separate letters layer in the source.* Better, but it needs the emblem redrawn; out of scope.

## R14. Testing the solid letters without an image library

**Decision**: `tests/integration/test_logo.py` gains a test that reads committed PNGs with the
standard library: `zlib` to inflate the `IDAT` chunks and the five PNG row filters undone by hand
(about 30 lines, 8-bit RGBA, non-interlaced, which is what Pillow writes). It reads
`logo-light-132.png` and `logo-dark-192.png`, sizes above 48 px, so the small-size sharpening does not
blur the line between letter and ornament. Sample points are given as fractions of the image's side, so
one list serves every size:

- **Letters**: one point in the middle of each letter's widest stroke (Я's stem, Н's two stems, М's
  right stem): alpha must be 250 or more at the point and its 8 neighbours. Not 255: the Lanczos
  downscale leaves 1–2 % dips (252–254) along the finest engraved lines inside the strokes, invisible
  but present at most points (measured on option B, 2026-11-17).
- **Ornament**: points in the loops above and below the letters, in a fleur-de-lis between them and in
  a side flourish: alpha must be 240 or less at the point and its neighbours (the engraving's shading),
  and above 0 at the point, so that it lies on the ornament's ink and not on paper.

The exact points are picked when the script is changed, on its output, at least 2 px from any edge at
the checked size, and each is shown on an overlay before it is kept, so that it lies clearly inside a
letter or the ornament. The reader refuses any other PNG type with a clear
error, so a change in how Pillow writes the files fails loudly.

**Rationale**: FR-043. CI installs neither Pillow nor numpy (R8), and the application must gain no
runtime dependency; a reader of the one PNG type the script writes is small and has no dependency.

**Alternatives considered**:
- *Add Pillow to `dev`.* CI would install an image library for one test; R8 rejects it.
- *Test only the script's constants.* That checks the data, not the committed images. Rejected.

## R15. The letters alone, for the icons (design review, round 3)

Added on 2026-11-18, after the product owner chose option **B** of
[round-3-small-icons-options](./screenshots/round-3-small-icons-options.png) (spec Clarifications,
round 3; FR-044, FR-045).

**Decision**: The script makes a second master, the **letters alone**, and draws every icon from it.
The emblem images keep the emblem's master (R13). The values below are the ones the reviewed sheet was
made with.

- **The cut, in the source's pixels** (`docs/brand/logo-source.png`, 311 × 311, flattened onto white,
  `L` its luminance):
  1. **Band**: rows 118–191 and columns 58–248, the row of letters; less rows 141–163 of columns
     240–248, where the right flourish's stem meets М.
  2. **Heavy ink**: `L < 120` inside the band, closed with a 3 × 3 maximum then minimum filter (the
     engraved inline), then opened with a 3 × 3 minimum then maximum filter (the horizontal rod and
     the hairlines, 1–2 px thick).
  3. **Small pieces dropped**: 4-connected pieces of 120 px or fewer go (dots, curls, the tips of the
     fleurs-de-lis that pass the threshold). The letters are one piece of several thousand pixels.
  4. **Grown back**: two steps of a 3 × 3 maximum filter, each kept inside `L < 215` and the band,
     so the letters reach their own drawn edge again (the threshold of step 2 lies inside it) and
     nothing further.
  5. **Holes filled**: holes of fewer than 40 px left inside the letters (the engraved inline) are
     filled; Я's bowl and the panels between the stems are larger and stay open.
- **Into the master**: as the letter area (R13): the same crop, ×8 bilinear, the Gaussian of σ 3
  master px, giving a soft mask `K`. The letters-alone coverage is `K · min(c / 0.45, 1)`: the same
  solid letters as in the emblem, and nothing outside them. It is cropped to its ink (coverage above
  0.02) and centred in a square.
- **The icons**: drawn from this master by the same `tile` as before, the light ink on `#16337a`, with
  the same sharpening at 32 px and below. The favicons' padding becomes 4 % a side (it was 2 %, which
  suited the emblem's diamond with its empty corners; the letters fill the tile's width). The Apple touch
  icon keeps 8 %, the 192 px and 512 px icons 6 %, and the maskable icon 15 %, so all three letters
  stay inside its safe zone.
- **Checked on**: [round-3-letters-cut](./screenshots/round-3-letters-cut.png), the source at 5× with
  the final cut in red. It was chosen on the same overlays for thresholds 120, 150 and 180, without and
  with the opening: at 150 the fleurs-de-lis between the stems join the letters, at 180 the dots and
  curls do too, and without the opening the horizontal rod stays across the panels.

**Rationale**: At 16–48 px, and at a home screen's 60 pt, the ornament's fine engraving blurs into a
shape around the letters, and the letters, a third of the emblem's height, are too small to read. The
letters alone fill the width of the icon and stay legible down to 32 px. The cut is a rule, not a hand
drawing, because the letters are the heaviest ink in their row: the R13 letter area could not be used,
since it counts the panels between the stems and the loops crossing Н as letter, which cut out alone
shows as stripes beside Н (tried first, rejected on sight). The rule's numbers belong to this source,
like the letter area.

**Alternatives considered**:
- *Option A, the whole emblem, as today.* Rejected in round 3: a blurred hexagon in the tab and on the
  home screen.
- *Option C, the letters as flat silhouettes* (the cut itself, without the engraved inline). The edges
  came out ragged from the source's pixels, and at 16 and 32 px it looked the same as B. Dropped
  before the review.
- *The letters typeset in a font.* Crisp, but no longer the emblem's own letters. Not proposed.
- *The letters alone for the gallery's `sm` mark too.* Asked in round 4; until then the emblem images
  keep the whole emblem (FR-044).

## R16. Testing the icons without an image library

**Decision**: `tests/integration/test_logo.py` gains a test on `icon-512.png` and
`icon-maskable-512.png`, read with the standard-library reader of R14 (extended to return the four
channels, not only the alpha; both files are 8-bit RGBA):

- **Letters**: one point in the middle of each letter's widest stroke, as fractions of the side, picked
  on the script's output and shown on an overlay before they are kept: the point and its 8 neighbours
  are the light ink `#f4f5f8`, each channel within 8 of it.
- **No ornament**: every pixel of the rows above the letters' top and below their bottom, less a
  margin of 4 px for the resampling, is exactly `#16337a`, opaque. In the emblem these rows hold the
  loops and the fleurs-de-lis, so one stray piece of ornament fails the test.

**Rationale**: FR-046, for the same reasons as R14. The 512 px icons are the largest, so the points and
the margin are the least sensitive to resampling; the maskable one also checks the larger padding. The
favicons are made by the same code from the same master.

**Alternatives considered**:
- *Compare the icons with the emblem images.* Says nothing about the ornament being gone. Rejected.
- *Check the favicons as well.* At 16–48 px a test point is one or two pixels; the 512 px icons cover
  the same master. Not done.
