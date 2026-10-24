# Data Model: Professional Design System and UI Guidelines (Milestone 10)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This milestone stores **nothing new in the database**:

- no table, no column, no migration;
- `tests/integration/test_migrations.py` is unchanged.

The "entities" below are a browser cookie, the design tokens, the component inventory and two small
changes to in-memory declarations that the templates read.

---

## 1. Theme choice (cookie, not stored on the server)

| Attribute | Value |
|---|---|
| Name | `sc_theme` |
| Values | `light`, `dark` |
| Absent, empty or any other value | **Device** (follow `prefers-color-scheme`) |
| Path | `/` |
| Max-Age | `31536000` (one year) |
| SameSite | `Lax` |
| HttpOnly | yes |
| Secure | in production (`settings.production`), like the session cookie |
| Set by | `POST /theme` with `theme=light` or `theme=dark` |
| Deleted by | `POST /theme` with `theme=device`, or with any unknown value |
| Read by | the `_theme` context processor, through `app.core.theme.read_theme(request)` |

**Python shape** (`app/core/theme.py`):

- `class Theme(StrEnum)` with `LIGHT = "light"`, `DARK = "dark"` and `DEVICE = "device"`.
- `THEME_COOKIE_NAME = "sc_theme"`.
- `read_theme(request) -> Theme`: never raises. Anything unexpected is `Theme.DEVICE`.
- `parse_theme(value: str | None) -> Theme`: the same rule, for the form field.
- `apply_theme(response, theme, *, secure: bool) -> None`:
  - for Light and Dark, sets the cookie;
  - for Device, deletes it, with the same path and flags.

**Rules**:

- **Not personal data**: it is not linked to a user or a session. Signing in, signing out and
  switching role neither read nor change it (FR-015, US5-4).
- **No consent needed**: as a preference cookie that holds only the choice, it needs no consent of
  its own (spec assumption).
- **No logging**: no log line ever names it.

**Template context** (added for every template by `_theme`):

| Name | Type | Meaning |
|---|---|---|
| `theme` | `"light"`, `"dark"` or `"device"` | The current choice. `base.html` renders `data-theme` for the first two and nothing for `device`. |
| `theme_return` | `str` | The address the switch returns to: the path and query string for `GET`/`HEAD`, otherwise the path only (research D6). The handler checks it again. |

---

## 2. Design tokens

All tokens are defined once, at the top of `app/static/css/app.css`, between the markers
`/* == Tokens == */` and `/* == End of tokens == */`. The dark values apply under
`[data-theme="dark"]`, and under `:root:not([data-theme="light"])` inside
`@media (prefers-color-scheme: dark)` (research D2).

### 2.1 Colour: given by the spec (FR-010)

| Token | Role | Light | Dark |
|---|---|---|---|
| `--sc-page` | Page background | `#f4f6fb` | `#0d1424` |
| `--sc-surface` | Cards, tables, menus | `#ffffff` | `#151f35` |
| `--sc-text` | Text | `#172033` | `#e6eaf2` |
| `--sc-muted` | Muted text | `#556070` | `#9aa6bd` |
| `--sc-border` | Borders, dividers | `#dde3ee` | `#26324d` |
| `--sc-top-bar` | Top bar background | `#16337a` | `#111a2e` |
| `--sc-primary` | Primary buttons, links, current tab | `#1f56d6` | `#6c9cff` |
| `--sc-on-primary` | Text on primary | `#ffffff` | `#0d1424` |
| `--sc-primary-tint` | Selection, icons, Write badge | `#e7eefc` | `#1d2c4f` |
| `--sc-accent` | Logo mark, highlights | `#f2a516` | `#f5b83d` |
| `--sc-success` | Success text, Active badge | `#17803d` | `#5fcf86` |
| `--sc-success-tint` | Success notice, Active badge background | `#e5f5ea` | `#13291c` |
| `--sc-danger` | Destructive buttons, errors | `#c0392b` | `#ff8a7a` |
| `--sc-danger-tint` | Error notice, error summary background | `#fdf0ee` | `#341b19` |

### 2.2 Colour: derived in this plan (spec assumption "tokens not listed")

| Token | Role | Light | Dark | Derivation |
|---|---|---|---|---|
| `--sc-primary-hover` | Hover and active on primary | `#1a47b3` | `#8fb3ff` | Primary darkened about 15 % in light, lightened about 15 % in dark. |
| `--sc-focus-ring` | Focus outline | `rgb(31 86 214 / 0.4)` | `rgb(108 156 255 / 0.45)` | Primary at about 40 % opacity. |
| `--sc-danger-hover` | Hover on destructive | `#a02f23` | `#ffa597` | As for primary. |
| `--sc-on-danger` | Text on destructive | `#ffffff` | `#0d1424` | As for text on primary. |
| `--sc-on-success` | Text on a solid success fill | `#ffffff` | `#0d1424` | As for text on primary. |
| `--sc-on-accent` | Text on accent | `#172033` | `#0d1424` | Dark text: amber is too light for white. |
| `--sc-on-top-bar` | Wordmark and menu text in the top bar | `#ffffff` | `#e6eaf2` | Text on the deep blue. |
| `--sc-on-top-bar-muted` | Role label in the top bar | `#c3cfee` | `#9aa6bd` | Muted text on the deep blue. |
| `--sc-neutral-tint` | Deactivated and Read badges, table header row | `#eef1f6` | `#1b253b` | Between page and border. |
| `--sc-shadow-card` | Card shadow | `0 1px 2px rgb(23 32 51 / 0.06)` | `none` | Calm: barely visible in light, and borders only in dark. |

### 2.3 Typography

| Token | Value | Notes |
|---|---|---|
| `--sc-font-family` | `"Open Sans", system-ui, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial, sans-serif` | Self-hosted `woff2`, variable, four subsets (research D4). |
| `--sc-weight-regular` / `-semibold` / `-bold` | `400` / `600` / `700` | FR-005. |
| `--sc-text-body` | `1rem` (16 px); `1.125rem` (18 px) from `1024px` | FR-004, SC-008. The root stays at 16 px (research D3). |
| `--sc-text-small` | `0.875rem` | Footer, hints, badges. Never used for running text. |
| `--sc-line-height` | `1.5` | Body text (FR-004). |
| `--sc-line-height-heading` | `1.25` | |
| `--sc-text-h1` | `1.75rem` (28 px); `2rem` (32 px) from `768px` | Bold 700. |
| `--sc-text-h2` | `1.375rem` (22 px); `1.5rem` (24 px) from `768px` | Bold 700. |
| `--sc-text-h3` | `1.25rem` (20 px) | Semibold 600. |
| `--sc-text-h4` | `1.125rem` (18 px) | Semibold 600. |
| `--sc-measure` | `70ch` | Maximum line length of running text (FR-004). |

### 2.4 Spacing, radii, sizes, breakpoints

| Token | Value | Notes |
|---|---|---|
| `--sc-space-1` … `--sc-space-6` | `0.5rem`, `1rem`, `1.5rem`, `2rem`, `3rem`, `4rem` (8, 16, 24, 32, 48 and 64 px) | 8 px grid (FR-011). |
| `--sc-radius-control` | `0.5rem` (8 px) | Buttons, inputs, badges, notices (FR-011). |
| `--sc-radius-card` | `0.75rem` (12 px) | Cards, table-as-card rows, the user menu panel (FR-011). |
| `--sc-content-width` | `72rem` | The one content width (FR-021). |
| `--sc-touch-target` | `2.75rem` (44 px) | The minimum height of buttons and menu entries. |
| Breakpoints | `768px` (tables, user menu, selectors, headings), `1024px` (body text) | Media queries cannot read custom properties, so they are written as literals. They are the only `px` values outside the token block (research D2). |

### 2.5 Mapping onto Pico (research D2)

The mapping block follows the tokens. Its pairs, with the Pico variable on the left and the token
on the right:

- **Page and text**:
  - `--pico-background-color` ← `--sc-page`
  - `--pico-color` ← `--sc-text`
  - `--pico-muted-color` ← `--sc-muted`
  - `--pico-muted-border-color` ← `--sc-border`
- **Primary**:
  - `--pico-primary` ← `--sc-primary`
  - `--pico-primary-background` ← `--sc-primary`
  - `--pico-primary-border` ← `--sc-primary`
  - `--pico-primary-hover` ← `--sc-primary-hover`
  - `--pico-primary-hover-background` ← `--sc-primary-hover`
  - `--pico-primary-hover-border` ← `--sc-primary-hover`
  - `--pico-primary-inverse` ← `--sc-on-primary`
  - `--pico-primary-focus` ← `--sc-focus-ring`
- **Secondary** (`--pico-secondary*`): the text colour on a surface-coloured button with a border,
  so a secondary button is calm, not grey.
- **Cards**:
  - `--pico-card-background-color` ← `--sc-surface`
  - `--pico-card-sectioning-background-color` ← `--sc-neutral-tint`
- **Form controls**:
  - `--pico-form-element-background-color` ← `--sc-surface`
  - `--pico-form-element-border-color` ← `--sc-border`
  - `--pico-form-element-focus-color` ← `--sc-focus-ring`
  - `--pico-form-element-invalid-border-color` ← `--sc-danger`
- **Status colours**:
  - `--pico-del-color` ← `--sc-danger`
  - `--pico-ins-color` ← `--sc-success`
- **Shape and type**:
  - `--pico-border-radius` ← `--sc-radius-control`
  - `--pico-font-family` ← `--sc-font-family`
  - `--pico-font-size` ← `100%` at every breakpoint
  - `--pico-line-height` ← `--sc-line-height`
  - `--pico-spacing` ← `--sc-space-2`
  - `--pico-typography-spacing-vertical` ← `--sc-space-3`

---

## 3. Components (not data)

Every component is a Jinja macro in `app/templates/components/`. It has one purpose, documented
variants and its own CSS classes. The full contract (names, parameters, variants, emitted markup
and classes) is in [contracts/components.md](./contracts/components.md).

| Family (file) | Macros | Spec |
|---|---|---|
| `frame.html` | `top_bar`, `user_menu`, `theme_switch`, `area_tabs`, `back_link`, `page_heading` | FR-018–FR-021, FR-024 |
| `button.html` | `button`, `link_button`, `post_button` | FR-025 |
| `card.html` | `card` | FR-026 |
| `table.html` | `data_table`, `cell`, `actions_cell` | FR-027 |
| `badge.html` | `badge`, `status_badge`, `access_badge` | FR-028 |
| `feedback.html` | `notice`, `empty_state` | FR-029, FR-030 |
| `form.html` | `field`, `select_field`, `checkbox_field`, `error_summary`, `form_actions` | FR-031 |
| `confirmation.html` | `confirmation`, `refusal` | FR-032 |
| `details.html` | `details_list` | FR-033 |
| `selectors.html` | `list_detail`, `chained_lists` | FR-034 |
| `icons.html` | `logo_mark`, `icon` | FR-008 |

---

## 4. Changed in-memory declarations

### 4.1 `Area` (`app/routers/areas.py`)

The class gains `description: str`, a one-line description for the home-page card (FR-035). The
paths, titles and roles are unchanged.

| Area | Path | Roles | Description (new) |
|---|---|---|---|
| Administrator area | `/admin` | administrator | Manage teachers, educational institutions and subjects. |
| Teacher area | `/teacher` | teacher | Manage your classes and invite your students. |
| Student area | `/student` | student | Take part in competitions and see your results. |
| Staff area | `/staff` | administrator, teacher | Pages shared by administrators and teachers. |

### 4.2 Form page context (every page with a form)

| Key | Type | Meaning |
|---|---|---|
| `values` | `dict[str, str]` | What was entered, keyed by field id. Re-rendered as is (FR-031). |
| `errors` | `dict[str, str]` | Field id → message. One summary link and one field error per entry. |
| `form_error` | `str \| None` | A message that belongs to no single field: summary text, no link. |

Four handlers change from a single `error` or `message` to this shape:

- `admin_subjects._form`;
- `admin_institutions` (the region form and the institution form);
- `auth._page` (sign-in and code entry).

The messages, their conditions and their status codes are unchanged (research D10). The mapping per
form is in [contracts/pages.md §3](./contracts/pages.md#3-form-error-mapping).

### 4.3 Gallery sample data (`app/routers/admin_components.py`)

Module-level frozen dataclasses and tuples: sample subjects, regions, institutions, classes,
students, a details list, field errors, and the confirmation and refusal texts. They are built at
import time and never read from or written to the database. The handler takes no session (FR-037).

---

## 5. Not changed

- **Data**: database tables, migrations, services, and the stored data of every entity.
- **Routes**: every existing route's address, method, form field names, status codes and access
  declaration (FR-040, SC-011). The only additions are `POST /theme` and `GET /admin/components`
  ([contracts/http-routes.md](./contracts/http-routes.md)).
- **Emails**: their templates and texts (spec assumption).
