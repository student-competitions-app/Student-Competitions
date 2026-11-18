# Data Model: The New Logo (Milestone 12.7)

**No stored data changes.** No table, column, migration, route or catalogue message is added or
changed. The "entities" of this milestone are static files and one component's inputs. They are listed
here so that the tests, the script and the documentation share one definition.

## 1. Emblem image

A square, transparent PNG of the emblem in one ink, filling the square edge to edge. Its letters ЯНМ
are fully opaque; its ornament is engraved, with partly transparent shading (research R13). Its path is
`/static/img/logo/logo-{ink}-{px}.png`.

| Field | Values | Rule |
|---|---|---|
| `ink` | `light` (`#f4f5f8`), `dark` (`#1c1c22`) | Light ink on dark backgrounds, dark ink on light ones |
| `px` | light: 24, 32, 44, 48, 64, 72, 88, 96, 128, 132, 192; dark: 24, 32, 48, 64, 72, 96, 128, 192 | 1×/2×/3× of the displayed sizes (research R1); 44, 88 and 132 exist only in light ink |

That makes 19 files. Every file is used by at least one `srcset`; none is used by nothing.

## 2. Displayed mark (`logo_mark`)

| Input | Values | Rule |
|---|---|---|
| `size` | `sm` (1.5rem), `md` (2rem), `lg` (4rem) | Anything else is a template error |
| `top_bar` | `false` (default), `true` | `true` takes no size: `size` stays at its default, and `sm` or `lg` is a template error |
| `theme` | `light`, `dark`, `device` | Required when `top_bar` is false; ignored when it is true; missing or unknown is a template error |

The rendered ink and density candidates follow from the inputs:

| Case | Element | Ink | Candidates |
|---|---|---|---|
| `top_bar=true` | `<img>` | light | `{1×,2×,3×}` of 44 px, at every width |
| `theme=light` | `<img>` | dark | `{1×,2×,3×}` of the size |
| `theme=dark` | `<img>` | light | `{1×,2×,3×}` of the size |
| `theme=device` | `<picture>`: `<source media="(prefers-color-scheme: dark)">` + `<img>` | source light, img dark | `{1×,2×,3×}` of the size, each |

Every case renders `alt=""`, `aria-hidden="true"`, and `width` and `height` equal to the 1× size (32
for the top bar). See [contracts/components.md](./contracts/components.md).

## 3. Icon

The letters ЯНМ alone, without the ornament, in light ink on `#16337a` (research R15). They are as solid
as in the emblem image. Padding a side: 4 % on the favicons' tile, 8 % on the Apple touch icon, 6 % on
the 192 px and 512 px icons, 15 % on the maskable icon.

| File | Size | Shape | Type |
|---|---|---|---|
| `favicon.ico` | 16, 32, 48 | rounded tile | `image/x-icon` or `image/vnd.microsoft.icon` |
| `favicon-16.png`, `favicon-32.png`, `favicon-48.png` | 16, 32, 48 | rounded tile | `image/png` |
| `apple-touch-icon.png` | 180 | full-bleed square, opaque | `image/png` |
| `icon-192.png`, `icon-512.png` | 192, 512 | full-bleed square | `image/png` |
| `icon-maskable-512.png` | 512 | full-bleed square, letters within the 80 % safe zone | `image/png` |

That makes 8 files.

## 4. Web manifest

`site.webmanifest`, served as `application/manifest+json`:

| Field | Value |
|---|---|
| `name` | «Студентські змагання» |
| `start_url` | `/` |
| `display` | `browser` |
| `theme_color`, `background_color` | `#16337a` |
| `icons` | `icon-192.png` (192x192), `icon-512.png` (512x512), `icon-maskable-512.png` (512x512, `purpose: maskable`) |

## 5. The image folder

`app/static/img/logo/` holds exactly the 19 emblem images, the 8 icons and the manifest: 28 files.
It is the output of `scripts/make_logo.py`, which deletes any other file in it
([contracts/logo-script.md](./contracts/logo-script.md)). The set of files equals the set of
`/static/img/logo/` URLs that the pages, the gallery in both themes and the manifest refer to (research
R9).

## 6. Design approval

`specs/012.7-new-logo/design-approval.md` is a review log. Each row has a date, a round, a commit, the
changes requested, the changes made, and a status (`Changes requested` or `Approved`). It also holds the
16 screenshots in `screenshots/` (research R10). The milestone merges only after an `Approved` row.
