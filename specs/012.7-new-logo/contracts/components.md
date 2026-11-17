# Contract: The Logo Mark, the Top Bar and the Gallery (Milestone 12.7)

No new component and no new UI pattern. `logo_mark` changes what it draws and gains two arguments.
The gallery's **Identity** section and the guidelines' **Icons and identity** section describe it
(research R4, R12).

## `components/icons.html`: `logo_mark(size="md", theme=none, top_bar=False)`

**Errors** (each a `template_error`, raised before any markup):

| Condition | Message |
|---|---|
| `size` not in `sm`, `md`, `lg` | `logo_mark: size must be sm, md or lg` (unchanged) |
| `top_bar` and `size != "md"` (the default) | `logo_mark: the top bar's mark takes no size` |
| not `top_bar` and `theme` not in `light`, `dark`, `device` | `logo_mark: theme must be light, dark or device` |

These messages are developer errors, not user-facing text, and are not translated, as today.

**Markup.** `B` stands for `/static/img/logo/`. Every `<img>` carries `alt=""`, `aria-hidden="true"`,
`width` and `height`.

Top bar (`logo_mark(top_bar=True)`), 44 px at every width (revised 2026-11-17, design review round 1):

```html
<img class="logo-mark logo-mark-top-bar" src="B/logo-light-44.png"
     srcset="B/logo-light-44.png 1x, B/logo-light-88.png 2x, B/logo-light-132.png 3x"
     width="44" height="44" alt="" aria-hidden="true">
```

Page background, `size` → 1× pixels `p` (sm 24, md 32, lg 64):

- `theme="light"`:
  `<img class="logo-mark logo-mark-{size}" src="B/logo-dark-{p}.png" srcset="B/logo-dark-{p}.png 1x,
  B/logo-dark-{2p}.png 2x, B/logo-dark-{3p}.png 3x" width="{p}" height="{p}" alt="" aria-hidden="true">`
- `theme="dark"`: the same with `logo-light-…`.
- `theme="device"`:

  ```html
  <picture>
    <source media="(prefers-color-scheme: dark)"
            srcset="B/logo-light-{p}.png 1x, B/logo-light-{2p}.png 2x, B/logo-light-{3p}.png 3x">
    <img class="logo-mark logo-mark-{size}" src="B/logo-dark-{p}.png" srcset="…dark 1x, 2x, 3x…"
         width="{p}" height="{p}" alt="" aria-hidden="true">
  </picture>
  ```

**Guarantees**:

- One image request per mark.
- No script.
- The space is reserved before the image loads.
- The mark is never announced by assistive technology.

## `components/frame.html`: `top_bar`

- `<a href="/" class="brand…">{{ logo_mark(top_bar=True) }}<span class="brand-name">{{ app_name }}</span></a>`.
- No other change. The link's accessible name is still `brand-name`'s text, in the page's language,
  hidden only visually when a role is shown below 768 px.

## `layouts/base.html`: the head

The three old icon links are replaced by the six links of
[static-assets.md](./static-assets.md) §2, in the same place, after the font preload.

## `pages/admin/components.html`: Identity

`{{ logo_mark("lg", theme) }}{{ logo_mark("md", theme) }}{{ logo_mark("sm", theme) }}` in the existing
`button-row`. The context's `theme` is passed explicitly. The palette swatches, including `--sc-accent`
and `--sc-on-accent`, are unchanged.

The **Frame** section's top bars show the top bar's mark, through `top_bar`, with no change of their own.

## `static/css/app.css`

| Rule | Before | After |
|---|---|---|
| `.logo-mark` | `display: block; flex: none` | unchanged |
| `.logo-mark-sm` / `-md` / `-lg` | 1.5rem / 2rem / 4rem | unchanged |
| `.logo-mark-top-bar` | (none) | `width` and `height: var(--sc-touch-target)`, at every width; no `@media` block changes them |
| `.logo-mark-tile`, `.logo-mark-spark` | tile and spark fills | **deleted** |
| `.brand-role` (top level) | `padding-left: calc(2rem + var(--sc-space-1))` | `calc(var(--sc-touch-target) + var(--sc-space-1))` |
| `.brand-with-role + .brand-role` (top level) | `margin: 0 0 0 calc(2rem + var(--sc-space-1))` | `margin: 0 0 0 calc(var(--sc-touch-target) + var(--sc-space-1))` |
| Icons comment | "tile and spark take the top bar's deep blue and the accent amber" | the mark is an image: light ink on the top bar, following the theme elsewhere; the line icons draw in the current text colour |

The `768px` reset rules for `.brand-role` are unchanged. No token is added, and the top bar container's
`min-height: 4rem` is unchanged.
