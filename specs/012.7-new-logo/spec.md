# Feature Specification: The New Logo (Milestone 12.7)

**Feature Branch**: `012.7-new-logo`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "create specification for the 12.7 milestone": milestone 12.7 of
`docs/requirements/milestones.md` ("The new logo"), placed in the 12.x group after milestone 12.6, with
the constitution v2.4.0 (the uv rule, Principle III and the Documentation quality gate), the milestone 10,
10.1, 12.5 and 12.6 specifications, milestone 10's design approval, `docs/requirements/ui-guidelines.md`,
the source image `docs/brand/logo-source.png`, the first image set in `app/static/img/logo/` and
`scripts/make_logo.py` as reference.

## Overview

Milestone 12.7 of the walking skeleton for the Student Competitions application. Like milestones 12.5 and
12.6, it is not about competitions: it replaces the logo.

Since milestone 10 the application's mark has been an amber spark on a deep-blue tile, drawn as inline
SVG in the top bar and the component gallery, with three old favicon files beside it. The product now has
its own emblem: an engraved monogram in a diamond of flourishes, in one colour with engraved shading; its
letters ЯНМ are solid ink, and the flourishes keep their engraving. A
first set of images was prepared from the source image by a script, but it does not hold every size the
application needs, it holds files nothing uses, and the script depends on a library (OpenCV) the project
does not want. Seven things become true when this milestone is done:

1. **The emblem is the mark in the top bar.** The brand link shows the emblem in light ink straight on the
   dark bar, in both themes, at the touch-target size (44 px), as tall as the language switch, at every
   width; below 768 px it is often the only identity in the bar. The bar stays one 64 px row.
2. **The logo mark component shows the emblem.** It keeps its three sizes and its error for any other
   size. Every size is sharp on ordinary and high-density screens, and off the top bar it follows the
   theme without JavaScript.
3. **The browser tab and the phone's home screen show the emblem.** Favicons, an Apple touch icon and a
   web manifest are linked from every page. An icon added to a home screen opens the application in the
   browser, like a bookmark.
4. **The images come from one script, and only the used ones are kept.** The script uses Pillow and numpy
   only, lives in its own dependency group that neither CI nor the image installs, and writes exactly the
   files the application links or shows. It makes the letters ЯНМ solid from a letter area it holds as
   data, and leaves the ornament as engraved.
5. **The product owner approves the new look.** The change to milestone 10's approved look is reviewed on
   screenshots and recorded in this milestone's own design approval.
6. **What tests cannot see is checked by hand**, from this milestone's quickstart.
7. **Nothing of the old mark is left.** No code serves, draws, links or tests the spark, its tile or the
   old favicons, and the documentation describes the new mark.

## Clarifications

### Session 2026-11-17

- Q: The product owner's review, round 1 (design-approval.md), found the top bar's emblem barely visible
  at 2rem (32 px) on a desktop. What size should it be? → A: The touch-target size
  (`--sc-touch-target`, 2.75rem, 44 px), as tall as the language switch beside it, at every width, not
  only below 768 px. FR-002, FR-034, User Story 1, the edge cases, SC-002 and the assumptions follow.
  The component's `sm`, `md` and `lg` sizes do not change, and no emblem image is added or removed: the
  44, 88 and 132 px light-ink images already exist.

### Session 2026-11-17 (design review round 2)

- Q: In round 2 the product owner found the size right, but the whole emblem lets the background show
  through its engraving. What should change? → A: The letters ЯНМ become fully opaque, in both inks;
  the ornament stays as it is, engraved and partly transparent. This is option **B** of the reviewed
  sheet [round-2-letters-options](./screenshots/round-2-letters-options.png). The letters keep their own
  outline and inline (where the source has no ink); only the engraved shading inside them becomes full
  ink. FR-041–FR-043, User Stories 1, 3 and 5, the edge cases, the entities, SC-011 and the assumptions
  follow.
- Q: The favicons, the Apple touch icon and the manifest's icons are made from the same emblem. Do they
  get the solid letters too? → A: Yes. Every image the script writes shows the same mark, and the solid
  letters help most at the icons' small sizes.
- Q: CI does not install Pillow, so how is the solid-letters rule tested? → A: A test reads the committed
  PNGs with the standard library alone (`zlib`, no image library) and checks points inside the letters
  are fully opaque and points in the ornament are not, in both inks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A visitor recognises the application by its emblem in the top bar (Priority: P1)

Olena, a teacher, opens the application on her laptop. In the top bar, before the product name, she sees
the silver diamond of the new emblem on the deep-blue bar, the size of a button, as tall as the language
switch, and she can read its letters. Later she opens it on her phone, where the wordmark is hidden beside
her role and the emblem, at the same size, is the only identity in the bar. In both places it is the link
to her area, as it was before.

**Why this priority**: The top bar is on every page; the mark there is the application's identity. This is
what the milestone is for.

**Independent Test**: Open the sign-in page and an area page at 375 px and 1280 px, in **Light** and
**Dark**. Check the emblem's ink, size and sharpness, the bar's height and what a screen reader announces
for the brand link.

**Acceptance Scenarios**:

1. **Given** any page at 768 px or wider, in **Light** or **Dark**, **When** it is shown, **Then** the
   brand link holds the emblem in light ink, the touch-target size (44 px) square, as tall as the
   language switch, straight on the bar with no tile around it, followed by the wordmark. The top bar is
   still one 64 px row.
2. **Given** any page narrower than 768 px, signed in with a role shown or signed out, **When** it is
   shown, **Then** the emblem is the same touch-target size (44 px) and the top bar is still one 64 px
   row.
3. **Given** a signed-in teacher at 360 px or 375 px, in Ukrainian or English, **When** the area page is
   shown, **Then** the role label sits beside the 44 px mark at an offset that follows the mark's new
   width, without overlapping it or wrapping the bar onto a second row.
4. **Given** a screen with 1×, 2× or 3× pixel density, **When** the top bar is shown at any width,
   **Then** the emblem is sharp, and the browser downloads only the one image file it needs.
5. **Given** a screen reader user on any page, **When** they reach the brand link, **Then** it is announced
   by the application's name in the page's language, the emblem itself is not announced, and this holds
   below 768 px where the wordmark is hidden visually.
6. **Given** a slow connection, **When** a page loads, **Then** the space for the emblem is reserved from
   the start and nothing in the bar shifts when the image arrives.
7. **Given** any page, **When** the brand link is followed, **Then** it leads where it led before
   (milestone 12.6); the wordmark and the role label are unchanged.
8. **Given** any page in **Light** or **Dark**, **When** the top bar is shown, **Then** the letters ЯНМ of
   the emblem are solid light ink, with none of the bar's colour showing through them, and the ornament
   around them keeps its engraved shading (Clarifications, round 2).

---

### User Story 2 - The browser tab and the phone's home screen show the emblem (Priority: P1)

Olena keeps the application open in a tab next to others; the tab shows the emblem on a small deep-blue
tile. On her phone she adds the application to the home screen; the icon is the emblem on a deep-blue
square, and tapping it opens the application in her browser, with its address bar and Back button.

**Why this priority**: The tab and the home-screen icon are where people find the application among
others; the old spark still showing there would undo the change of identity.

**Independent Test**: Request every icon and the manifest, signed in and signed out, and check their
answers and types; read the manifest's fields; open a page and look at the browser tab; add the page to a
phone's home screen and open it from there.

**Acceptance Scenarios**:

1. **Given** any page, signed in or not, **When** its head is read, **Then** it links the favicons (an ICO
   holding 16, 32 and 48 px, and PNGs of the same three sizes), the 180 px Apple touch icon and the web
   manifest.
2. **Given** a visitor who is not signed in, **When** they request each linked icon and the manifest,
   **Then** each answers 200 with its type: `image/png` for the PNGs, `image/x-icon` or
   `image/vnd.microsoft.icon` for the ICO, and `application/manifest+json` for the manifest.
3. **Given** the manifest, **When** it is read, **Then** it names the application «Студентські змагання»,
   has `start_url` `/`, `display` `browser`, the deep blue `#16337a` as its theme and background colour,
   and lists a 192 px icon, a 512 px icon and a 512 px maskable icon, each of which answers 200.
4. **Given** the browser tab, **When** a page is open, **Then** it shows the emblem in light ink on a
   rounded deep-blue tile.
5. **Given** a phone, **When** the application is added to the home screen and opened from there, **Then**
   the icon is the emblem on a full-bleed deep-blue square rounded by the device, and the application
   opens in the browser, not as a standalone app.
6. **Given** a launcher that crops icons to a circle or another shape, **When** it uses the maskable icon,
   **Then** the whole emblem stays visible, inside the safe zone.

---

### User Story 3 - The logo mark component shows the emblem and follows the theme (Priority: P2)

A developer uses the logo mark component on a page background. In the component gallery's **Identity**
section the administrator sees the emblem at its three sizes: dark ink in **Light**, light ink in **Dark**,
and in **Device** whichever the device's colour scheme asks for.

**Why this priority**: The component is how every page shows the mark; the top bar depends on it. It is
P2 because today only the gallery shows it off the top bar.

**Independent Test**: Open the gallery in each theme, switch the device's colour scheme in the browser's
developer tools with JavaScript off, and check the ink and size of each mark; render the component with an
unknown size.

**Acceptance Scenarios**:

1. **Given** the gallery in **Light**, **When** the **Identity** section is shown, **Then** it shows the
   emblem at `sm` (1.5rem), `md` (2rem) and `lg` (4rem), each in dark ink.
2. **Given** the gallery in **Dark**, **When** the **Identity** section is shown, **Then** the same three
   marks are in light ink.
3. **Given** the gallery in **Device** and JavaScript turned off, **When** the device's colour scheme is
   switched between light and dark, **Then** the marks switch between dark and light ink.
4. **Given** a template that asks for the logo mark with any size other than `sm`, `md` or `lg`, **When**
   it is rendered, **Then** rendering fails with a template error, as today.
5. **Given** any of the three sizes at 1×, 2× or 3× density, **When** it is shown, **Then** it is sharp,
   its width and height are set, and the browser loads only the file it needs.
6. **Given** the gallery in **Light** or **Dark**, **When** the **Identity** section is shown, **Then** in
   each mark the letters ЯНМ are solid ink and the ornament is engraved, in dark ink and in light ink
   alike.

---

### User Story 4 - The product owner approves the new look (Priority: P2)

The new mark changes the look the product owner approved in milestone 10. Before merge, they review
screenshots and approve it, or ask for changes that are made and reviewed again.

**Why this priority**: Milestone 10's spec asks for any later deviation from the approved look to be
recorded and approved again; the milestone cannot merge without it.

**Independent Test**: The design approval file exists in this milestone's spec folder, lists the reviewed
screenshots and records a dated approving round before merge.

**Acceptance Scenarios**:

1. **Given** the change is ready, **When** the product owner reviews it, **Then** they see screenshots of
   the top bar on the sign-in page and on an area page, of the gallery's **Identity** section and of the
   browser tab, at 375 px and 1280 px, each in **Light** and **Dark**.
2. **Given** the product owner asks for changes, **When** they are made, **Then** a new round is reviewed
   and recorded, and the milestone does not merge until a round is approved.
3. **Given** the approval, **When** it is recorded, **Then** it is in this milestone's design approval
   file with its date, and milestone 10's design approval is not edited.

---

### User Story 5 - A maintainer regenerates the images from the source (Priority: P3)

A maintainer changes how the emblem is rendered, or the source image changes. They run one command, the
script writes the complete set of images the application uses, and they commit its output.

**Why this priority**: The images are made once per change of the mark; this keeps them reproducible and
keeps unused files and dependencies out of the application, but users do not see it directly.

**Independent Test**: On a clean checkout, sync the project as CI and the image do and confirm the script's
libraries are not installed; run the script with its group; compare its output with the committed folder.

**Acceptance Scenarios**:

1. **Given** a checkout, **When** the maintainer runs `uv run --group logo scripts/make_logo.py`, **Then**
   the script writes exactly the files the application links or shows, no more and no fewer.
2. **Given** the committed image folder, **When** it is compared with a fresh run of the script on the
   same source, **Then** it holds the same files; no committed image was edited by hand.
3. **Given** CI (`uv sync --locked`) or the image (`uv sync --locked --no-dev`), **When** dependencies are
   installed, **Then** Pillow and numpy for the script are not installed by them, and the application has
   no new runtime dependency.
4. **Given** the script, **When** its imports are read, **Then** it uses Pillow and numpy only; OpenCV is
   gone from it and from the lock file.
5. **Given** the source image, **When** the script runs, **Then** it crops the white margin, upscales in
   steps with sharpening, makes the paper transparent, and writes the emblem in dark ink (for light
   backgrounds) and light ink (for dark ones) wherever the mark can appear in both.
6. **Given** the source image, **When** the script runs, **Then** inside the letter area it holds as data
   the letters ЯНМ become fully opaque, and outside it the ornament is rendered as before, in every image
   it writes, the icons included.

---

### User Story 6 - Nothing of the old mark is left (Priority: P3)

After the milestone, a developer searching the code, the tests and the documentation finds the new mark
described everywhere and no trace of the spark, its tile or the old favicons.

**Why this priority**: Left-over files and rules mislead the next person who changes the identity, and
the old favicons would still be served to anyone who knew their addresses.

**Independent Test**: Search `app/` and `tests/` for the old paths and classes; request the old favicon
addresses; read the UI guidelines and the README.

**Acceptance Scenarios**:

1. **Given** the code and tests, **When** they are searched, **Then** nothing under `app/` or `tests/`
   refers to `/static/img/favicon.svg`, `/static/img/favicon-32.png`, `/static/img/apple-touch-icon.png`,
   `logo-mark-tile` or `logo-mark-spark`.
2. **Given** the old favicon addresses, **When** they are requested, **Then** they are not found, because
   the files are deleted.
3. **Given** the palette, **When** it is read, **Then** `--sc-accent` and `--sc-on-accent` remain, with
   their gallery swatches, and the UI guidelines name the accent's role "Highlights".
4. **Given** the UI guidelines and the README, **When** they are read, **Then** they describe the new mark,
   its sizes, how it follows the theme, the image folder, the script and how to run it.

### Edge Cases

- **The emblem image fails to load.** The brand link is still named by the application's name and still
  leads to the same place; the bar keeps its height, because the image's size is set.
- **A long role label on a narrow phone.** At 360 px, with the English role label beside the 44 px mark,
  the top bar is still one 64 px row (checked by hand in both languages).
- **The frame under a taller top bar.** The bar's height does not change, but section 4 of the UI
  guidelines asks for the frame to be measured again whenever the top bar changes; the frame must still
  end under `--sc-frame-clearance-tabs` on an area page.
- **Device theme without JavaScript.** The gallery's mark follows the device's colour scheme through the
  page alone; no script decides which ink to show.
- **High-density screens.** A 3× phone showing the 44 px mark needs a 132 px image; every displayed size
  has an image at 1×, 2× and 3×, so nothing is upscaled by the browser.
- **Very small sizes.** At 16 px the emblem reads as a texture, and at 32 px its letters are hard to read;
  both are accepted in the browser tab and in the gallery's `sm` and `md` marks, because there the mark is
  recognised by its shape, a silver diamond on deep blue. The top bar's mark is never smaller than 44 px,
  where the letters are readable (Clarifications, 2026-11-17).
- **A request to `/favicon.ico` at the site root.** It is not served by this milestone and answers as it
  does today: 404, the **Page not found** page (checked on 2026-11-16). Browsers use the linked icons
  instead.
- **An old bookmark or a cached page linking the old favicons.** The old files no longer exist; the browser
  falls back to the new linked icons on the next page load.
- **An unknown logo size in a template.** Rendering fails with a template error, so the mistake is found
  in development and in the tests.
- **Where the letters and the ornament meet.** The source has no separate letters layer: the letter area
  is drawn by hand in the source's pixels, around the letters and clear of the fleurs-de-lis, the dots
  and curls, the horizontal rod and the side flourishes. Where a flourish crosses a letter (the loops
  through Н), the crossing inside the letters' band counts as letter. A few hairline curls touching a
  letter may come out solid; that is accepted if the review does not object.
- **A new source image.** The letter area belongs to `docs/brand/logo-source.png` as it is. If the source
  changes, the area must be drawn again; the opacity test fails if its sample points no longer fall on
  the letters and the ornament.

## Requirements *(mandatory)*

### Functional Requirements

**The top bar**

- **FR-001**: The brand link in the top bar MUST show the emblem in light ink straight on the bar, with no
  tile, in both themes.
- **FR-002**: At every width, signed in or out, the top bar's mark MUST be the touch-target size
  (`--sc-touch-target`, 2.75rem, 44 px) square, the height of the language switch beside it.
- **FR-003**: The top bar MUST stay one 64 px row at every width, including at 360 px, 375 px, 768 px and
  1280 px with a role shown and signed out, in Ukrainian and in English.
- **FR-004**: Every offset that assumes the old 2rem mark width, such as the role label's left margin
  beside the mark, MUST follow the mark's 44 px width wherever it applies.
- **FR-005**: The mark MUST stay decorative: hidden from assistive technology. The brand link's accessible
  name MUST remain the application's name in the page's language, also below 768 px where the wordmark is
  hidden visually.
- **FR-006**: The wordmark, the role label and the brand link's destination (milestone 12.6) MUST NOT
  change.

**The logo mark component**

- **FR-007**: The logo mark component MUST keep its three sizes, `sm` (1.5rem), `md` (2rem) and `lg`
  (4rem), and MUST keep failing with a template error for any other size.
- **FR-008**: The component MUST show the emblem image instead of inline SVG.
- **FR-009**: Each size, and the top bar's 44 px size, MUST be sharp at 1×, 2× and 3× pixel
  density, and the browser MUST load only the one file it needs for the screen.
- **FR-010**: The image MUST have its width and height set, so nothing shifts while it loads.
- **FR-011**: In the top bar the mark MUST always be in light ink. Anywhere else (today only the gallery) it
  MUST follow the theme: dark ink in **Light**, light ink in **Dark**, and in **Device** whichever the
  device's colour scheme asks for. This MUST work without JavaScript.
- **FR-012**: The gallery's **Identity** section MUST show the mark at its three sizes.

**Browser and device icons**

- **FR-013**: The favicons MUST show the emblem in light ink on a rounded deep-blue tile (`#16337a`, the
  light theme's top bar colour): an ICO holding 16, 32 and 48 px, and PNGs of the same three sizes.
- **FR-014**: The Apple touch icon (180 px) and the manifest's icons (192 px, 512 px, and a 512 px
  maskable icon with the emblem inside the safe zone) MUST be full-bleed deep-blue squares with the
  emblem in light ink.
- **FR-015**: Every page MUST link the favicons, the Apple touch icon and the manifest from the base
  layout.
- **FR-016**: The manifest MUST be served as `application/manifest+json`, name the application
  «Студентські змагання», have `#16337a` as its theme and background colour, `start_url` `/` and
  `display` `browser`.
- **FR-017**: The icons and the manifest MUST be reachable by a visitor who is not signed in, each
  answering 200 with its type.

**The image set and the script**

- **FR-018**: The image folder (`app/static/img/logo/`) MUST hold only the files the application links or
  shows: the emblem images for the component's sizes and the top bar's size at 1×, 2× and 3×, in
  both inks wherever the mark can appear in both; the favicons; the Apple touch icon; the manifest's icons;
  and the manifest.
- **FR-019**: The prepared link-preview image (`og-image.png`) and the 512 px and 1024 px transparent
  logos MUST be removed, as must any other file in the folder that nothing links or shows.
- **FR-020**: Every committed image MUST be the script's output, never edited by hand; the script MUST
  write exactly the files of FR-018.
- **FR-021**: The script MUST crop the source's white margin, upscale in steps with sharpening, make the
  paper transparent so the shading survives on any background, and write the emblem in dark ink and in
  light ink.
- **FR-022**: The script MUST use Pillow and numpy only. OpenCV MUST be removed; its resizing, blurring and
  smoothing MUST be done with Pillow and numpy.
- **FR-023**: The script's libraries MUST be a non-default dependency group, `logo`, in the project
  file, locked in the lock file with everything else. Neither CI's install nor the image's install MUST
  install the group, and the application MUST gain no runtime dependency.
- **FR-024**: The script MUST run with `uv run --group logo scripts/make_logo.py` and MUST pass the style
  checks.
- **FR-041**: In every image the script writes, in both inks and in the icons, the letters ЯНМ MUST be
  fully opaque wherever the source has ink in them, keeping their own outline and inline. The ornament
  MUST stay as it is: engraved, its shading partly transparent.
- **FR-042**: The script MUST find the letters by a letter area it holds as data, in the source image's
  pixels (the letters' band, less the ornament inside it), not by guessing from the image. The area MUST
  be documented with the picture it was checked against.

**Approval and manual checks**

- **FR-025**: Before merge, the product owner MUST review screenshots of the top bar on the sign-in page
  and on an area page, of the gallery's **Identity** section and of the browser tab, at 375 px and
  1280 px, in **Light** and **Dark**.
- **FR-026**: The approval, or the changes asked for and the round that approves them, MUST be recorded
  with its date in a design approval file in this milestone's spec folder. Milestone 10's design approval
  MUST NOT be edited.
- **FR-027**: This milestone's quickstart MUST list the checks a test cannot make, as in milestone 10.1:
  the emblem is sharp in the bar and the gallery; the bar is one 64 px row at 360 px, 375 px, 768 px and
  1280 px with a role shown and signed out, in Ukrainian and English; the frame still ends under
  `--sc-frame-clearance-tabs` on an area page; in **Device** the gallery's mark follows the device's colour
  scheme when it is switched in the developer tools; the browser tab and a phone's home screen show the
  new icons.

**Cleanup**

- **FR-028**: The old `favicon.svg`, `favicon-32.png` and `apple-touch-icon.png` in `app/static/img/` MUST
  be deleted, with their links.
- **FR-029**: The component's inline SVG, the `logo-mark-tile` and `logo-mark-spark` style rules, and the
  comments that describe the spark and the tile (in the icons component and the stylesheet's icons
  comment) MUST be deleted or corrected.
- **FR-030**: `--sc-accent` and `--sc-on-accent` MUST stay in the palette for highlights, and the gallery
  MUST keep their swatches.

**Tests**

- **FR-031**: Tests MUST check, on the sign-in page and on signed-in pages, that the brand link holds
  exactly one logo mark, hidden from assistive technology, and that the link's name is the application's
  name in the page's language.
- **FR-032**: Tests MUST check that every page links the favicons, the Apple touch icon and the manifest,
  that each answers 200 with its type (FR-017, accepting both ICO types) to a visitor who is not signed in,
  that the manifest has `start_url` `/` and `display` `browser`, and that its icons exist and answer 200.
- **FR-033**: A test MUST check that the logo mark with an unknown size is a template error.
- **FR-034**: A stylesheet test, in the manner of the existing frame stylesheet test, MUST check that the
  top bar's mark is sized by `--sc-touch-target` at every width, with no other size from 768 px, and that
  the role label's offset beside the mark follows the same width.
- **FR-035**: Tests MUST check that the gallery's **Identity** section shows the mark at its three sizes,
  in dark ink in **Light** and in light ink in **Dark**.
- **FR-036**: A test MUST check that nothing under `app/` or `tests/` refers to the old favicon paths or to
  the `logo-mark-tile` and `logo-mark-spark` classes.
- **FR-037**: Existing tests of the old mark (the identity test in the layout tests among them) MUST be
  rewritten for the new behaviour, never skipped or left behind. The whole suite MUST pass on both database
  engines, and the style checks MUST pass, the script included.
- **FR-043**: A test MUST read committed emblem images in light ink and in dark ink with the standard
  library alone (CI has no image library) and check that sample points inside the letters are opaque
  (alpha 250 or more, 98 %: the downscale leaves 1–2 % dips along the finest engraved lines) and
  sample points in the ornament are inked but partly transparent (alpha above 0 and 240 or less).

**Documentation**

- **FR-038**: The UI guidelines MUST describe the new mark: the introduction adds that the logo mark was
  replaced in milestone 12.7 and links this milestone's design approval; section 4 gives the top bar mark's
  two sizes and the new frame measurement ("Last measured in milestone 12.7"), replacing milestone 12.5's;
  the **Icons and identity** section says the mark is an image, no longer inline SVG, with solid letters
  and an engraved ornament, and how it follows the theme; and `--sc-accent`'s palette role becomes
  "Highlights".
- **FR-039**: The README's project tree MUST name `img/logo/` under `static/`, `scripts/make_logo.py` and
  `docs/brand/` with what they are for, and the README MUST say how to run the script (`uv run --group
  logo …`), that its output is committed, and that its letter area belongs to the current source image.
- **FR-040**: In the milestones document, milestone 12.7 MUST move to Delivered once it ships, compacted
  like the others. The specifications of delivered milestones, milestone 10's design approval included,
  MUST NOT be edited.

### Key Entities

- **Emblem**: the application's mark, an engraved monogram in a diamond of flourishes, in one colour with
  engraved shading. Its source is `docs/brand/logo-source.png` (311 × 311 px, the emblem about 212 px of
  it). It exists in two inks: dark, for light backgrounds, and light, for dark ones. Its letters ЯНМ are
  solid ink; the ornament around them keeps its engraved shading.
- **Letter area**: the part of the source image that is the letters ЯНМ, held by the script as data in
  the source's pixels: the letters' band, less boxes around the ornament inside it.
- **Emblem image**: one rendering of the emblem in one ink at one pixel size, on a transparent background.
  The displayed sizes are `sm` (24 px), `md` (32 px), `lg` (64 px) and the top bar's size (44 px),
  each needed at 1×, 2× and 3× density. `sm`, `md` and `lg` exist in both inks; the 44 px size, shown only
  in the top bar, in light ink.
- **Icon**: the emblem in light ink on deep blue (`#16337a`) for browsers and devices: favicons on a
  rounded tile (16, 32 and 48 px, as an ICO and as PNGs); the Apple touch icon (180 px) and the manifest's
  icons (192 px, 512 px, 512 px maskable) as full-bleed squares.
- **Web manifest**: the application's description for devices: name «Студентські змагання», theme and
  background colour `#16337a`, `start_url` `/`, `display` `browser`, and its three icons.
- **Logo script**: the development tool that turns the source into the image set. Not part of the
  application or its image; its libraries are the `logo` dependency group.
- **Design approval**: the dated record of the product owner's review rounds for the new mark, in this
  milestone's spec folder.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The new emblem appears in 100% of top bars, in both themes and at every width, and the old
  spark appears on 0 pages, in 0 browser tabs and on 0 home-screen icons.
- **SC-002**: The top bar is one 64 px row in all 16 hand-checked combinations (360 px, 375 px, 768 px
  and 1280 px, role shown and signed out, Ukrainian and English).
- **SC-003**: The emblem is sharp at all 4 displayed sizes on 1×, 2× and 3× screens, with no image
  enlarged by the browser, and each page downloads exactly one emblem file per mark shown.
- **SC-004**: All 9 files (the 5 icons each page links, the manifest and the manifest's 3 icons) answer
  200 with the right type to a visitor who is not signed in.
- **SC-005**: A phone home-screen icon opens the application in the browser with its address bar in 100%
  of tries.
- **SC-006**: The image folder holds 0 files that the application does not link or show, and a fresh run
  of the script reproduces every committed image.
- **SC-007**: CI and the image install 0 new packages; the application gains 0 runtime dependencies.
- **SC-008**: 0 references to the old favicon paths or the old mark classes remain under `app/` and
  `tests/`.
- **SC-009**: The product owner's approval is recorded with its date before merge, covering all 16
  screenshots (4 views × 2 widths × 2 themes).
- **SC-010**: The full test suite passes on both database engines with 0 tests skipped because of this
  milestone, and the style checks pass.
- **SC-011**: In 100% of the checked emblem images, in both inks, every sample point inside the letters
  is opaque (alpha ≥ 250) and every sample point in the ornament is partly transparent (alpha ≤ 240).

## Assumptions

- **Pixel sizes follow the default text size.** 1rem is 16 px, so `sm`, `md` and `lg` are 24, 32 and
  64 px and the touch target is 44 px. The exact file names in the image folder are left to the plan.
- **Which files the script writes is decided by FR-018.** The first prepared set (light ink at 32, 64 and
  96 px; both inks at 256, 512 and 1024 px; `og-image.png`) is replaced by the script's new output, and
  whatever it no longer writes is removed.
- **The manifest needs no short name or other fields** beyond those of FR-016 and its icons; adding a short
  name equal to the name is left to the plan.
- **The manifest's name stays Ukrainian in both languages.** Every page opens in Ukrainian, and a manifest
  is read once, when the icon is added.
- **The 32 px mark stays hard to read where it remains.** In the browser tab and the gallery's `md` mark
  the emblem is recognised by its shape; making it legible at 32 px is not a goal. The top bar's mark is
  44 px at every width, where it is legible (Clarifications, 2026-11-17).
- **The reviewed sheet is a proposal, not the output.** Option **B** was made outside the script, from
  the same pipeline with a hand-drawn letter area and a lift of 0.45 (research R13). The script's output
  is reviewed again in the next round's screenshots.
- **No data changes.** No table, column, route or migration is added or changed; the icons are static
  files.
- **The hand checks stay manual** until end-to-end tests arrive in milestone 16.

## Dependencies

- **Milestone 10**: the design system, the logo mark component, the gallery, the top bar and the approved
  look whose deviation this milestone records.
- **Milestone 10.1**: the pinned frame, `--sc-frame-clearance-tabs` and the pattern of hand checks in the
  quickstart.
- **Milestone 12.5**: the application's name in both languages and the language switch in the top bar.
- **Milestone 12.6**: where the brand link leads.
- **The constitution's uv rule**: dependencies only through `pyproject.toml` and the committed `uv.lock`.

## Out of Scope

- Link previews (`og:image`), which would need the site's public address and lead to the sign-in page
  anyway.
- Serving `/favicon.ico` at the site root.
- A vector (SVG) version of the emblem, which automatic tracing could not make faithfully and which would
  have to be redrawn by hand.
- Installing the application as an app (a standalone display mode, offline use).
- Any change to the wordmark, the role label, the palette other than the accent's documented role, or the
  brand link's destination.
- Editing the specifications of delivered milestones, milestone 10's design approval included.
