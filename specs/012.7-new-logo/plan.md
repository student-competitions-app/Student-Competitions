# Implementation Plan: The New Logo (Milestone 12.7)

**Branch**: `012.7-new-logo` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.7-new-logo/spec.md`

## Summary

The amber spark on a deep-blue tile is replaced everywhere by the engraved emblem. The new mark is
an image, not inline SVG. Nothing else in the UI changes.

**Images** (research R1, R7, R8; [contracts/logo-script.md](./contracts/logo-script.md)):

- `scripts/make_logo.py` is rewritten with Pillow and numpy only. OpenCV goes.
- It takes no arguments: it reads `docs/brand/logo-source.png` and writes exactly the 28 files that
  the application uses to `app/static/img/logo/`, then deletes any other file there:
  - 19 emblem images, `logo-{light,dark}-{px}.png`;
  - 8 icons on `#16337a`;
  - `site.webmanifest`.
- Its libraries are the `logo` dependency group, locked in `uv.lock`. Neither CI nor the image
  installs the group.
- **Solid letters** (R13, added 2026-11-17 after the design review's round 2): the script holds the
  letter area of ЯНМ as data in the source's pixels and lifts the coverage inside it, so the letters
  are fully opaque in every image, icons included; the ornament is unchanged. No template, CSS or file
  name changes; every image in the folder is regenerated.
- **The letters alone on the icons** (R15, added 2026-11-18 after the design review's round 3): the
  script cuts the letters ЯНМ out of the source by a rule it holds with its data (heavy ink, small
  pieces dropped, grown back to the letters' edge) into a second master, and draws all 8 icons from it,
  without the ornament. The favicons' padding becomes 4 %. The emblem images keep the whole emblem. No
  template, CSS, link or file name changes; only the 8 icons are regenerated.

**The mark** (R2–R5; [contracts/components.md](./contracts/components.md)):

- The signature becomes `logo_mark(size="md", theme=none, top_bar=False)`. It keeps `sm`, `md` and
  `lg` and the size error.
- **Top bar**: light ink in one `<img>`, 44 px at every width, with density candidates (44, 88 and
  132 px). CSS sizes it by `--sc-touch-target`, the language switch's height, and the role label's
  offset follows. The bar stays one 64 px row. (Revised 2026-11-17 after the design review's round 1:
  the mark was 2rem from 768 px, with width-described candidates.)
- **Page background** (the gallery): it follows the `theme` the server already renders. **Light**
  gives dark ink, **Dark** gives light ink, and **Device** gives a `<picture>` whose
  `prefers-color-scheme: dark` source holds the light ink. There is no script, and each mark loads one
  file.
- Every variant is `alt=""` and `aria-hidden="true"`, with `width` and `height` set.

**Icons** (R6; [contracts/static-assets.md](./contracts/static-assets.md)):

- `base.html` links four favicons (ICO and 16/32/48 PNG), the 180 px Apple touch icon and the
  manifest.
- The manifest names «Студентські змагання», with `start_url` `/`, `display` `browser` and `#16337a`
  colours.
- The types come from Python's `mimetypes`, with no registration.

**Cleanup** (R12):

- The three old files in `app/static/img/` and their links go.
- So do the inline SVG, `.logo-mark-tile` and `.logo-mark-spark`, and the comments about the spark.
- `--sc-accent` stays, with its swatch, and its role becomes "Highlights".

**Tests** (R9):

- The identity tests in `test_layout.py` are rewritten.
- A new `test_logo.py` covers the files, types and manifest, "only what is used" and the leftover
  search.
- The macro's markup and errors are tested in `tests/unit/test_templates.py`.
- New gallery-ink tests in `test_component_gallery.py`.
- New stylesheet tests in `test_frame_stylesheet.py`.
- A solid-letters test in `test_logo.py` reads two committed PNGs with the standard library alone
  and checks sample points: letters fully opaque, ornament not (R14).
- An icons test in `test_logo.py` reads the two 512 px icons the same way: points in the letters are
  the light ink, and the rows above and below the letters are only the deep blue (R16).

**Approval and checks by hand** (R10, R11; [quickstart.md](./quickstart.md)):

- 16 screenshots are committed in `screenshots/`, and the product owner's approval goes in this
  folder's `design-approval.md` before merge.
- The frame is measured again, for "Last measured in milestone 12.7".

**Documentation** (R12): the UI guidelines, the README tree and a logo paragraph, and milestones
Delivered.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:
- The application's are unchanged: FastAPI, Jinja2 (`jinja2.ext.i18n`), SQLModel, Alembic, Babel,
  Pico.css v2 (vendored).
- Pillow and numpy are added as the non-default `logo` dependency group, used by the development
  script only. They are not a runtime dependency (R8).

**Storage**: SQLite and PostgreSQL, unchanged. No schema change and no migration
([data-model.md](./data-model.md)). The new assets are static files under `app/static/img/logo/`.

**Testing**: pytest on both engines (`TEST_POSTGRES_URL`), ruff (the script included), and the
existing stylesheet and template checks. The by-hand checks and the screenshots are made with
Playwright, run ad hoc (not a dependency, milestone 10 D1).

**Target Platform**: one Docker image on Render, unchanged. `scripts/` and `docs/` stay out of the
build context.

**Project Type**: server-rendered web application (one FastAPI app), plus one development script.

**Performance Goals**:
- Each page downloads one emblem file in the top bar, sized for its slot and density, instead of an
  inline SVG. It is a few kilobytes at most (an estimate, not a measured goal), and the browser caches
  it.
- The favicons are fetched once per browser.
- No server-side cost.

**Constraints**:
- Everything works without JavaScript.
- The mark is decorative.
- The images are never edited by hand.
- No pixel literal or custom property outside the token block (`test_stylesheet.py`).
- The top bar stays one 64 px row.
- No new route, environment variable or runtime dependency.

**Scale/Scope**:
- Application, 5 files: `components/icons.html`, `components/frame.html`, `layouts/base.html`,
  `pages/admin/components.html`, `static/css/app.css`.
- Images: 3 files deleted from `app/static/img/`, and `app/static/img/logo/` regenerated.
- Script and dependencies: `scripts/make_logo.py`, `pyproject.toml`, `uv.lock`.
- Tests, 5 files: `test_layout.py`, the new `test_logo.py`, `test_component_gallery.py`,
  `test_frame_stylesheet.py`, `test_templates.py`.
- Documentation: `README.md`, `ui-guidelines.md`, `milestones.md`.
- This folder: `design-approval.md` and `screenshots/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | Status | How |
|---|---|---|
| I. Walking skeleton | ✅ | 12.6 is merged to `main` (`cb0e188`) and deployed, as the product owner confirmed on 2026-11-16. One feature on its own branch, `012.7-new-logo`, which follows the `NNN-feature-name` convention, like the spec folder. The scope is the milestone's: link previews, root `/favicon.ico` and an SVG emblem are deferred |
| II. Server-rendered simplicity | ✅ | Server-rendered `<img>` and `<picture>`, theme chosen on the server, no JavaScript. No new runtime dependency. Pillow and numpy are a development-only group, so the "justify a new runtime dependency" rule is not triggered, and R8 records them anyway |
| II. UI guidelines (required from milestone 11) | ✅ | No new pattern. `logo_mark` stays the library's identity component, shown in the gallery's **Identity** in every theme. CSS uses tokens only (`--sc-touch-target`, `--sc-space-1`) and rem sizes. The guidelines are updated in the same PR (R12) |
| III. Test-backed delivery | ✅ | Every clause of the milestone's _Test:_ line maps to an automated test (R9). No route is added or changed, so there are no new role-access tests. Static files stay public by design, and that is tested for a signed-out visitor. CI is green on both engines, with ruff. What tests cannot see is checked by hand (R11), as in milestone 10.1, until milestone 16 |
| IV. Role-based access | ✅ | No route, no data and no access rule changes. `/static` was already public and serves only images and a manifest. The gallery stays administrator-only and outside production |
| V. Secure authentication | ✅ | Untouched. No secret is involved; the manifest holds the name and colours only |
| VI. LLM evaluation | n/a | — |
| VII. Data integrity & migrations | ✅ | No schema or data change |
| Technology stack (uv) | ✅ | The `logo` group is in `pyproject.toml` and locked in `uv.lock`; no requirements file and no `--with` for the script (R8). Pillow and numpy are not a new stack category: they are a development tool's libraries, like `pytest` in `dev` |
| Application layout | ✅ | The component stays in `templates/components/`. The images are under `static/img/`, as the layout lists. The script is in `scripts/`, outside `app/` |
| Operational | ✅ | One image, unchanged contents apart from `app/static/img/`. No new environment variable |
| Documentation gate | ✅ | README, UI guidelines and milestones are updated in the same PR (R12). The specs of delivered milestones are not edited |

No violations, so Complexity Tracking is empty.

**Post-design re-check** (after Phase 1): unchanged, all ✅. Three points were weighed and resolved
within the rules:
- **The explicit `theme` argument (R4).** It is a required input, not a hidden context dependency.
- **Theme selection on the server, plus `<picture>` for Device (R3).** This keeps "no script" and
  "one file per mark" together.
- **No per-breakpoint custom property (R5).** It respects the stylesheet's token rules.

## Project Structure

### Documentation (this feature)

```text
specs/012.7-new-logo/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R12; R13–R14 (round 2), R15–R16 (round 3)
├── data-model.md        # Phase 1: no stored data; emblem images, logo_mark inputs, icons, manifest, folder
├── quickstart.md        # Phase 1: automated, leftovers, by hand, approval, regeneration, documentation
├── contracts/
│   ├── components.md    # logo_mark, top_bar, base head, gallery Identity, app.css rules
│   ├── static-assets.md # served files and types, head links, manifest, the folder
│   └── logo-script.md   # the command, behaviour, libraries, dependency group, style
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit-specify)
├── design-approval.md   # implementation: the review log (R10)
├── screenshots/         # implementation: 16 review images (R10)
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
app/
├── templates/
│   ├── components/icons.html        # logo_mark(size, theme, top_bar): emblem <img>/<picture>; header comment
│   ├── components/frame.html        # top_bar: logo_mark(top_bar=True)
│   ├── layouts/base.html            # six icon/manifest links replace the three old ones
│   └── pages/admin/components.html  # Identity: logo_mark(size, theme)
└── static/
    ├── css/app.css                  # +.logo-mark-top-bar; role offsets by --sc-touch-target;
    │                                #   −.logo-mark-tile, −.logo-mark-spark; icons comment
    └── img/
        ├── favicon.svg, favicon-32.png, apple-touch-icon.png   # deleted
        └── logo/                    # regenerated: 19 emblem images, 8 icons, site.webmanifest

scripts/make_logo.py                 # rewritten: no args, Pillow + numpy, owns img/logo/
pyproject.toml, uv.lock              # + dependency group `logo`

tests/
├── integration/
│   ├── test_layout.py               # identity tests: the image mark, both languages, new links
│   ├── test_logo.py                 # new: files and types, manifest, only-what-is-used, leftovers
│   └── test_component_gallery.py    # Identity inks per theme
└── unit/
    ├── test_frame_stylesheet.py     # top bar mark sizes and role offset
    └── test_templates.py            # logo_mark markup per variant and its errors

README.md, docs/requirements/ui-guidelines.md, docs/requirements/milestones.md
```

**Structure Decision**: The existing single FastAPI application. The change stays inside the identity
component (`components/icons.html`), its two callers, the base layout's head and the stylesheet. No
new module apart from the new test file. The generator stays a standalone development script in
`scripts/`, and its dependencies are kept apart in their own group.

## Complexity Tracking

No constitution violations to justify.
