# Quickstart: Validating the New Logo (Milestone 12.7)

Run from the repository root on branch `012.7_new_logo`. The sections are in order: automated checks
first, then searches for leftovers, the checks by hand, the approval, and the image set.

## 1. Automated checks

```sh
uv sync --locked
uv run ruff check . && uv run ruff format --check .
uv run pytest                                              # SQLite
TEST_POSTGRES_URL=postgresql+psycopg://… uv run pytest     # both engines (sc-pg container)
```

Expected: everything passes, with no test skipped because of this milestone. The tests of
[research.md](./research.md) R9 cover:

- the brand link's single, hidden mark and its name in both languages;
- the six icon and manifest links on every kind of page;
- each file's status and type for a signed-out visitor;
- the manifest's fields and icons;
- `logo_mark`'s errors;
- the stylesheet sizes and offsets;
- the gallery's inks per theme;
- the folder against the URLs in use;
- the absence of the old paths and classes.

## 2. Leftovers

```sh
grep -rnE "favicon\.svg|img/favicon-32|img/apple-touch-icon|logo-mark-(tile|spark)" app tests   # nothing
ls app/static/img          # flag-gb.svg  flag-ua.svg  logo
ls app/static/img/logo | wc -l                                   # 28
grep -n "cv2\|opencv" -ri scripts pyproject.toml uv.lock         # nothing
uv run python -c "import PIL" 2>&1 | tail -1                     # ModuleNotFoundError: the group is not installed
```

## 3. Checks by hand

Start the application locally (README "Run"). Sign in as an administrator, and as a teacher with an
accepted invitation (README "Signing in locally as each role"). For the headless measurements, use the Playwright recipe the project uses
for screenshots: `uv run --no-project --with playwright`, not a dependency.

1. **Sharp emblem.** Look at the top bar at 1280 px and 375 px, on a 1× and a 2× or 3× screen (or with
   the device pixel ratio emulated), and at the gallery's **Identity**. The emblem has crisp strokes and
   no halo, in **Light** and in **Dark**.
2. **One row.** At 360 px and 375 px width: signed out, and signed in with a role shown (teacher area),
   in Ukrainian and in English. That is 8 combinations. Each time the top bar is 64 px tall, the mark is
   44 × 44, the role label sits beside it without overlap, and nothing wraps.
3. **The frame.** At 360 × 640 and 375 × 667, in both languages, measure the bottom of `.frame` on
   `/teacher/students` and on `/admin/teachers`. It must be under 176 px
   (`--sc-frame-clearance-tabs`). Write the four largest numbers into ui-guidelines §4 under "Last
   measured in milestone 12.7". Milestone 12.5 measured 153 px and 109 px, and the bar's height has not
   changed.
4. **Device.** Choose **Device** in the theme switch. Open `/admin/components#identity` with JavaScript
   disabled. In the developer tools, switch "Emulate CSS prefers-color-scheme" between light and dark:
   the three marks switch between dark and light ink. The top bar's mark stays light ink.
5. **One file per mark.** In the Network panel of the gallery page, each mark loads exactly one
   `logo-*.png`. The top bar loads `logo-light-44.png` (or 88/132) below 768 px and `logo-light-32.png`
   (or 64/96) from 768 px.
6. **Browser tab.** The tab shows the emblem on a rounded deep-blue tile, in the browser's light and dark
   appearance.
7. **Home screen.** On a phone (iOS Safari: Share → Add to Home Screen; Android Chrome: Add to Home
   screen):
   - The icon is the emblem on a deep-blue square.
   - Opening it shows the application in the browser, with the address bar, and Back and reload work.
   - On Android, a round or squircle mask leaves the whole emblem visible.
8. **Accessibility.** With VoiceOver or NVDA, the brand link reads «Студентські змагання» (or "Student
   Competitions" in English) at both widths, and the image is not announced.

## 4. Design approval

1. Take the 12 headless screenshots of [research.md](./research.md) R10:
   - the top bar on `/login` and on `/teacher/students`;
   - `/admin/components#identity`;
   - each at 375 px and 1280 px, in **Light** and **Dark**.

   Take the 4 browser-tab images by hand. Save all 16 in `specs/012.7-new-logo/screenshots/` as
   `{view}-{width}-{theme}.png`.
2. Commit them, and open a review round in `design-approval.md` with the commit.
3. The product owner approves, or asks for changes. For changes, make them, take new screenshots, and
   open the next round.
4. Merge only after a row with status **Approved** and its date.

## 5. Regenerating the images

```sh
uv run --group logo scripts/make_logo.py
git status --porcelain app/static/img/logo     # empty: the committed set is the script's output
uv lock --check                                # the lock file is up to date
```

Run this on the machine that produced the committed set (see research R7 on float differences between
machines). When the source or the script changes, run it, review the images, and commit the folder as
it is.

## 6. Documentation

- `docs/requirements/ui-guidelines.md`:
  - the introduction names the 12.7 replacement and links the design approval;
  - §3's accent role is "Highlights";
  - §4 has the mark's two sizes and "Last measured in milestone 12.7";
  - **Icons and identity** describes the image and how it follows the theme.
- `README.md`:
  - the tree names `img/logo/`, `scripts/make_logo.py` and `docs/brand/`;
  - the logo paragraph gives `uv run --group logo …` and says that the output is committed.
- `docs/requirements/milestones.md`: 12.7 is in Delivered, compacted.
- `specs/010-design-system-ui-guidelines/` is unchanged: `git diff main -- specs/010-*` shows nothing.
