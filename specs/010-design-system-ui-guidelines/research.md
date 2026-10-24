# Research: Professional Design System and UI Guidelines (Milestone 10)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

The spec leaves no `[NEEDS CLARIFICATION]` markers. The decisions below settle the "how" questions
the spec hands to the plan: where the tokens live and how they reach Pico, how the theme is chosen
and rendered with no flash, how the gallery disappears in production, how the components are
shaped, how 375 px is guaranteed, and how the tests survive a rebuild of every template.

Each decision has the same three parts: **Decision**, **Rationale** and **Alternatives
considered**.

---

## D1. Mockup first, approval recorded, screenshots before merge

**Decision**:

- **The mockup** is one static, self-contained HTML page, `specs/010-design-system-ui-guidelines/mockup/index.html`.
  It holds a draft of the token block and the component CSS inline, and loads the Open Sans files
  from `app/static/fonts/` by a relative path. Nothing loads from another site (FR-048).
- **It shows**:
  - the wordmark, the logo mark, the favicon at 16 and 32 px, the palette in both themes and the type
    scale;
  - the five key pages: sign-in, home, a list (the **Subjects** tab), a form with errors (**Create
    subject** with a duplicate name) and a confirmation (**Delete “Physics”?**, and its refusal);
  - each page in four frames: 375 px and 1280 px wide, light and dark. Frames are fixed-width
    `<div>`s with a `data-theme` attribute, so all sixteen are on one page with no script.
- **Approval** is recorded in `specs/010-design-system-ui-guidelines/design-approval.md`: the date,
  the approver, the mockup's commit, and a log of the changes requested and made. No template under
  `app/templates/pages/` changes before the "Approved" line is committed (FR-046, User Story 1).
- **A later deviation** is a new entry in the same log, approved again (US1-3).
- **Screenshots before merge** (SC-001): a throw-away script captures every page at 375 px and
  1280 px, light and dark, and also reports `scrollWidth > 375` and the body's computed font size
  and line height. It runs Playwright through `uv run --with playwright`, so nothing is added to
  `pyproject.toml` or `uv.lock`. The local recipe is the one already used for this project:
  a copy of the database, port 8765, and the sign-in code read from the uvicorn log.
- **Where the screenshots go**: a git-ignored `screenshots/` folder with an `index.html` contact
  sheet. The product owner reviews it, and the review is logged in `design-approval.md`.

**Rationale**: The spec makes approval the gate for the whole milestone. A static page is the
cheapest thing to change between review rounds and needs no server. Keeping the screenshots out of
git avoids roughly 170 PNGs that would be out of date after the next milestone. The script is a
review aid, not a test: Playwright as a test framework still arrives in milestone 12 (Constitution,
Technology Stack).

**Alternatives considered**:

- **A design tool (Figma)**: not in the repository, and it cannot use the real font files and
  tokens.
- **The gallery as the mockup**: it needs the components built first, which is the work the
  approval is meant to gate.
- **Committing the screenshots**: bloats the repository with images nobody reads after the merge.
- **Adding Playwright to the dev dependencies now**: introduces a stack component before its
  milestone, for a one-off review.

---

## D2. Tokens: one block at the top of `app.css`, mapped onto Pico's variables

**Decision**:

- **Where they live**: `app/static/css/app.css` opens with a token block between the markers
  `/* == Tokens == */` and `/* == End of tokens == */`.
  - Light values sit on `:root`.
  - Dark values are given twice, with the same declarations: under `[data-theme="dark"]`, and under
    `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }`.
- **Naming**: every token is named `--sc-*`. The values are in [data-model.md §2](./data-model.md#2-design-tokens).
- **Mapping onto Pico**: right after the tokens, one mapping block sets Pico's own variables from
  the tokens. Examples: `--pico-background-color`, `--pico-color`, `--pico-muted-color`,
  `--pico-muted-border-color`, `--pico-primary*`, `--pico-secondary*`,
  `--pico-card-background-color`, `--pico-form-element-*`, `--pico-border-radius`,
  `--pico-font-family`, `--pico-spacing` and `--pico-typography-spacing-vertical`.
- **Selectors**: the mapping uses the selectors Pico v2.1.1 itself uses for its light scheme
  (`:root:not([data-theme=dark]), [data-theme=light]`) and its dark scheme (`[data-theme=dark]` and
  `:root:not([data-theme])` inside the media query). It loads after `pico.min.css`, so the same
  specificity and the later position make it win.
  - This is why the mapping repeats per scheme even though it only reads tokens: Pico re-declares
    its colour variables in each scheme block.
- **Pico itself** is never edited (FR-047).
- **The rest of `app.css`**, which is the page layout and the components, uses only `var(--sc-*)`
  and `var(--pico-*)`. A unit test fails on any hex colour, `rgb(`/`hsl(` value or `px` length
  outside the token block. The only exceptions are `0`, `1px` borders and the `768px`/`1024px`
  media queries (FR-012).

**Rationale**: Pico already themes every element it styles from its variables. Overriding them is
the documented way to restyle Pico, and the spec requires it (FR-047). A second, product-named set
of tokens (`--sc-*`) gives the guidelines stable names that do not depend on Pico's naming. It also
covers what Pico has no variable for: the top bar, the accent, the badges and the danger colours.

**Alternatives considered**:

- **Tokens written directly into Pico's variables, with no `--sc-*` layer**: the top bar, accent,
  badge and danger colours have no Pico variable, so half the tokens would still need new names.
- **Pico's colour themes (`pico.blue.min.css`)**: a different stylesheet with its own palette,
  which still needs overriding to reach the Classroom blue values.
- **Sass**: a build step (FR-047).

---

## D3. Type, spacing and widths

**Decision**:

- **Root font size**: fixed at 16 px. Pico's responsive root scaling (`--pico-font-size` from
  100 % up to 131.25 %) is switched off by setting `--pico-font-size: 100%` at every breakpoint.
- **Body text**: `--sc-text-body`, which is `1rem` (16 px) below 1024 px and `1.125rem` (18 px) from
  1024 px. It is applied to `body`, with `line-height: var(--sc-line-height)` (1.5) (FR-004,
  SC-008).
- **Spacing**: in multiples of `0.5rem` (8 px), so the 8 px grid is exact at every width (FR-011).
- **Content width**: `--sc-content-width: 72rem` (1152 px) for the page frame (`.container`).
  - Running text is held to `--sc-measure: 70ch` by the text components: paragraph blocks, notices,
    empty states, the details list and the confirmation body (FR-004).
  - Tables and the selectors use the full content width.
- **Breakpoints**: two. `768px` for the data table's card layout, the folded user menu and the
  selectors' stacking (spec assumption). `1024px` for the desktop text size.
- **Heading scale**: in [data-model.md §2](./data-model.md#2-design-tokens). On a phone, `h1` and
  `h2` step down one size.

**Rationale**: If the root size changes, every `rem` changes with it, which breaks the 8 px grid at
desktop width. Fixing the root and scaling only the body text keeps both rules exact. 72 rem fits a
four-column data table at 1280 px with room on both sides. The 70 ch measure keeps prose readable
on the same page.

**Alternatives considered**:

- **Keeping Pico's root scaling**: desktop text becomes 20 px at 1280 px, and spacing drifts off
  the grid.
- **A narrower content width (for example 60 rem)**: data tables with actions wrap too much at
  desktop width.

---

## D4. The font: Open Sans, self-hosted, variable

**Decision**:

- **Files**: Open Sans as a variable font (weight axis), in four `woff2` subsets: latin, latin-ext,
  cyrillic and cyrillic-ext.
  - They go in `app/static/fonts/`, with the SIL Open Font License as `OFL.txt` beside them.
  - They are downloaded once, during implementation, from the project's open-source release
    (Google Fonts' `opensans` repository), and committed.
- **Declaration**: one `@font-face` per subset in the token block, with
  `font-weight: 300 800`, `font-display: swap` and the subset's `unicode-range`.
- **Weights used**: 400, 600 and 700, through tokens (`--sc-weight-regular/semibold/bold`) (FR-005).
- **Fallback**: `--sc-font-family` is `"Open Sans"` followed by the system font stack Pico already
  uses (`system-ui, "Segoe UI", Roboto, …`).
- **Preload**: only the latin subset, with `<link rel="preload" … crossorigin>` in the base layout.

**Rationale**:

- **Fewer files**: one variable file per subset covers all three weights, so there are 4 files
  instead of 12 static ones.
- **Only what is needed**: `unicode-range` means an English page downloads only the latin file,
  and a Cyrillic name pulls in the cyrillic file when it appears.
- **Readable without the font**: `swap` keeps pages readable at once on the fallback font, which
  is also the edge case of font files failing to load.

**Alternatives considered**:

- **Static instances for 400, 600 and 700**: three times the files, for no visible difference.
- **Google Fonts' CSS API**: a third-party font service (FR-005, FR-048).
- **One file with every subset combined**: every page pays for Cyrillic glyphs it does not show.

---

## D5. The theme choice: a cookie read on the server

**Decision**:

- **Cookie**: `sc_theme`, with the value `light` or `dark`. Choosing **Device** deletes the cookie.
  A missing, empty or unknown value is **Device** (FR-015, FR-016, spec edge cases).
  - Attributes: `Path=/`, `Max-Age=31536000` (one year, spec assumption), `SameSite=Lax`,
    `HttpOnly`, and `Secure` in production (the same flag as the session cookie).
  - It holds only the choice: no identifier, and nothing in the database.
- **Reading it**: a new Jinja context processor, `_theme` in `app/core/templates.py`, beside
  `_current_user`. It reads the cookie through `app/core/theme.py` and gives every template:
  - `theme`: `"light"`, `"dark"` or `"device"`;
  - `theme_return`: the address the switch returns to (D6).
- **Rendering**: `layouts/base.html` renders `<html lang="en" data-theme="{{ theme }}">` for Light
  and Dark, and no `data-theme` attribute for Device.
  - The token block decides colours from that attribute, or from `prefers-color-scheme` when it is
    absent. The first paint is already in the right theme, with no script (FR-016, US5-5).
  - `<meta name="color-scheme">` is `light`, `dark` or `light dark` to match, so form controls and
    scrollbars follow too.
- **The device changes while the choice is Device**: the media query re-evaluates in the open page,
  and the next page follows it (spec edge case).
- **No user data**: the theme is not linked to the account or the session. Signing in, switching
  role and signing out leave it untouched, and it does not follow the person to another browser
  (US5-4).

**Rationale**: Only a value the server knows before it renders the first byte can avoid a flash
without JavaScript. Because the cookie is HttpOnly, no script can read it, and no script needs to.
Deleting the cookie for Device keeps the rule "no cookie means Device" true in exactly one place.

**Alternatives considered**:

- **`localStorage` and a script in `<head>`**: needs JavaScript, and flashes when the script is
  late.
- **Storing the choice with the account**: forbidden by FR-015.
- **Storing `device` explicitly**: a third state, with the same behaviour as no cookie.

---

## D6. The theme switch: `POST /theme`, a small form, a safe return

**Decision**:

- **The control**: `theme_switch()` is a component (contracts/components.md). It is one
  `<form method="post" action="/theme">` with three submit buttons, `name="theme"` and the values
  `light`, `dark` and `device`.
  - The current choice carries `aria-pressed="true"`.
  - A hidden field, `next`, holds `theme_return`.
- **Where it appears**: in the user menu, and on the sign-in page (`login.html`) only (FR-014). The
  other public pages render in the chosen theme but show no switch (spec assumption).
- **The route**: `POST /theme` lives in a new router, `app/routers/theme.py`.
  - It is added to `PUBLIC_ROUTES`, because it must work signed out on the sign-in page and for
    every signed-in role.
  - It goes through the application-wide cross-site check like every other `POST` (Constitution V).
  - It never reads or writes the database.
  - It answers 303 to the return target.
- **The return target**:
  - **Computed in `_theme`**: the current path and query string for a `GET` request. For a page
    rendered by another method (a form shown again after an error) it is the path alone, because
    that page's query belonged to the `POST`.
  - **Checked in the handler**: `safe_return_path` in `app/core/security.py` applies the
    `safe_next_path` rules. It refuses absolute and protocol-relative URLs, backslashes, control
    characters and values over 2,048 characters. Unlike `safe_next_path`, it allows `/login` and
    `/role`; it refuses `/login/code`, `/logout` and `/theme`.
  - **A GET page must exist**: the handler also requires that the path matches a `GET` route in the
    application's route table. A page that was only ever rendered by a `POST` has no `GET`
    counterpart, and returning there would give a 405.
  - **Fallback**: anything refused returns to `/` when signed in and to `/login` when signed out
    (FR-017, spec edge case).
- **An unknown `theme` value** is treated as **Device**: the cookie is deleted, and the response is
  still the 303. The switch never shows an error.

**Rationale**:

- **No JavaScript**: a form post is the only way to change a server-read cookie without
  JavaScript.
- **Same-site**: going through the existing cross-site check keeps the rule "every state change is
  a same-site `POST`".
- **Safe return**: checking the target against the route table removes the one way the switch
  could land on an error page.

**Alternatives considered**:

- **`GET /theme?set=dark`**: a state change on `GET`, and a link that crawlers and prefetchers
  would follow.
- **Returning by the `Referer` header**: often stripped, and not under the application's control.
- **Reusing `safe_next_path` unchanged**: it sends `/login` to `/`, which breaks the switch on the
  sign-in page.

---

## D7. The page frame: top bar, user menu, tabs, footer

**Decision**:

- **`layouts/base.html` renders the frame** from components (FR-018–FR-021):
  - a skip link;
  - the top bar, `top_bar()`, with the logo mark, the wordmark "Student Competitions" and, when
    signed in, the current role as a label, plus the user menu;
  - the `<main class="container">`;
  - a footer with the version and build, and an optional `{% block footer_extra %}` that the home
    page uses for the database status line (FR-036).
- **The user menu**, `user_menu()`, is a `<details class="user-menu">` with a `<summary>`. It
  works without JavaScript at every width (FR-019, US2-2). It holds, in order:
  1. the email, linking to `/profile`;
  2. the role switch, the existing `POST /role` form, only for people with several roles (US2-3);
  3. the theme switch;
  4. **Log out**, the existing `POST /logout` form.
- **Folding on a phone**: from 768 px the summary shows the email beside an account icon. Below
  768 px it shows only the icon and the visually hidden text "Account menu", so the top bar keeps
  the logo, the product name and the role on one row.
- **The area tabs**, `area_tabs(tabs, active, label)`, replace the two hand-built `<nav>`s in
  `layouts/admin.html` and `layouts/teacher.html`.
  - They keep the `<nav aria-label="Administrator area">` / `"Teacher area"` labels and the
    `aria-current="page"` marker (FR-042).
  - The current tab is underlined in `--sc-primary` (FR-020).
  - On a phone the row wraps, as it does today.
- **The skip link** is "Skip to main content", visually hidden until it has focus. It is the one
  addition to the frame's accessibility features, and it costs nothing.

**Rationale**: A `<details>` element opens and closes natively, so it meets "opens without
JavaScript" with no fallback to maintain. Using one menu at every width, rather than an inline row
on desktop and a menu on a phone, means one piece of markup and one test.

**Alternatives considered**:

- **A CSS-only checkbox toggle**: an invisible form control, worse than `<details>` for the same
  result.
- **An inline header on desktop with a separate menu on a phone**: two copies of the role switch,
  the theme switch and **Log out** in every page, kept in sync by hand.

---

## D8. The component library: Jinja macros in `app/templates/components/`

**Decision**:

- **One file per component family**, each a set of macros with one purpose:
  - `frame.html`: top bar, user menu, theme switch, area tabs, back link, page heading;
  - `button.html`;
  - `card.html`;
  - `table.html`;
  - `badge.html`;
  - `feedback.html`: notice and empty state;
  - `form.html`: field, select, checkbox, error summary, form actions;
  - `confirmation.html`;
  - `details.html`;
  - `selectors.html`;
  - `icons.html`: logo mark and the few icons.
- **How pages use them**: they import what they need, for example
  `{% from "components/button.html" import button, link_button, post_button %}`.
- **Slots**: macros that wrap content use Jinja's `caller()`, through `{% call %}`.
- **The contract**: names, parameters, variants and emitted classes are in
  [contracts/components.md](./contracts/components.md).
- **Class names**: they belong to the components, never to pages. For example `.data-table`,
  `.badge`, `.badge-success`, `.notice-error`, `.empty-state`, `.error-summary`, `.destructive`,
  `.row-actions` and `.selectors`.
  - The old page-specific classes (`subjects-table`, `teachers-table`, `institutions-table`,
    `students-table`, `subjects-empty`, `subjects-actions`, `list-empty`, `questions-empty`,
    `class-picker`, `class-bar`, `institutions-layout`, `regions-list`, `picker-table`,
    `auth-message`, `hero`, `site-*`, `admin-tabs`, …) are removed (FR-041, US4-4).
- **Escaping**: macros render text through Jinja autoescape. No macro takes HTML as a string; rich
  content goes through `caller()`.

**Rationale**:

- **No new code**: macros are the reuse mechanism Jinja already provides, with no new dependency
  (FR-023, FR-047).
- **No new HTML**: `caller()` keeps markup in templates rather than in Python strings, so
  autoescaping still protects every value.

**Alternatives considered**:

- **`{% include %}` with context variables**: no parameters, so every call site leaks variables
  into the next.
- **Python-side HTML helpers (`Markup`)**: markup in Python, which is harder to review and easy to
  get wrong on escaping.
- **A component library package (for example JinjaX)**: a new runtime dependency (FR-047).

---

## D9. Buttons: three kinds, the same look for links and form buttons

**Decision**:

- **Kind to class**:
  - *primary*: Pico's default button, no class;
  - *secondary*: Pico's `.secondary`;
  - *destructive*: `.destructive`, defined in `app.css` from `--sc-danger` and
    `--sc-on-danger`.
- **A link that opens a form or a confirmation page** (FR-025, US3-7) is
  `<a href="…" role="button" class="…">`, which Pico styles exactly like a button. Examples are
  **Create subject**, **Invite teacher**, **Add student**, and **Delete** or **Deactivate** in a row.
- **A one-button form** (Activate, Deactivate or Delete on a confirmation page) is `post_button()`.
  It renders `<form method="post" action="…">` holding one `<button>`, with the same kind classes.
- **Row actions** (FR-027) all use the compact size, `.row-actions` sets the padding.
  - Plain actions (Rename, Edit, Activate) are *secondary outline*.
  - Destructive actions (Deactivate, Delete, Remove) are *destructive outline*.
  - They are the same shape and size and sit together at the end of the row.
- **At most one primary button** per page or section, by convention (FR-025). The guidelines state
  it, and the gallery shows it.

**Rationale**: Pico already gives `<a role="button">` and `<button>` the same box. Mapping kinds to
classes in one macro means a page cannot pick a colour by hand.

**Alternatives considered**:

- **Converting every link action into a `POST` form**: changes behaviour, and confirmation pages
  must stay `GET` pages (FR-040).
- **A fourth "link" kind for row actions**: FR-025 names exactly three kinds.

---

## D10. Forms: errors next to fields and in a summary, from one shape

**Decision**:

- **One context shape for every form page**: `values: dict[str, str]`,
  `errors: dict[str, str]` (field id → message) and `form_error: str | None`.
  - Most forms already pass `errors` and `form_error`: the teacher, student and class forms.
  - Four handlers still pass a single `error` or `message`, and change to this shape: the subject
    form, the region form, the institution form and the sign-in pair.
  - The messages and status codes stay the same (FR-040).
- **`error_summary(errors, form_error, order)`** renders the summary (FR-031, SC-006):
  - `<div class="error-summary" role="alert" aria-labelledby="error-summary-title">`, headed
    "There is a problem";
  - one `<a href="#field-id">` per field error, in field order;
  - `form_error` as plain text with no link (spec edge case);
  - shown whenever there is at least one error, even exactly one.
- **`field()`, `select_field()` and `checkbox_field()`** render:
  - the label;
  - an optional hint (`id="…-hint"`);
  - the error (`<small id="…-error" class="field-error">`);
  - the control, with `aria-invalid="true"` and `aria-describedby` listing hint and error.
  - The value is always the one entered (FR-031, FR-042).
- **Classifying messages**: a message about one field's value is a field error, and that includes
  "Invalid or expired code" on the code field. Rate limits, "temporarily unavailable" and messages
  about the whole submission are form errors. The table per form is in
  [contracts/pages.md §3](./contracts/pages.md#3-form-error-mapping).
- **`form_actions(submit_label, cancel_href)`**: the primary button first, then **Cancel** as a
  plain link (FR-031).

**Rationale**: One shape means one macro and one test helper for every form. The four forms with a
single value change only how the router hands the message over, not when it appears or what it
says.

**Alternatives considered**:

- **Building the summary in each template from whatever the router passes**: the same pattern
  rebuilt per page, which FR-023 forbids.
- **Moving focus to the summary with a script**: JavaScript, and accessibility work beyond scope
  (FR-050).

---

## D11. Data table: a real table that becomes cards below 768 px

**Decision**:

- **`data_table(columns, caption=None)`** renders a `<table class="data-table">` with a header
  row. The rows come from `caller()`, each cell through `cell(label)`, which emits
  `<td data-label="Name">`. The actions cell is `actions_cell()`, which emits
  `<td class="row-actions" data-label="">`.
- **Phone layout**: below 768 px, CSS sets the table, `tbody`, `tr` and `td` to `display: block`.
  - The `thead` is visually hidden, not removed.
  - Each row becomes a card (`--sc-surface`, `--sc-radius-card`).
  - Each cell shows its label from `attr(data-label)` in muted semibold.
  - The actions cell sits last, its buttons wrapping together (FR-027, spec edge case).
- **Long values** wrap with `overflow-wrap: anywhere` at every width. There is no `.overflow-auto`
  wrapper any more, so a table never scrolls sideways (FR-022).
- **An empty list** renders `empty_state()` instead of the table (spec edge case).
- **The institution picker** inside the teacher forms is a data table too, with checkbox and
  select cells.

**Rationale**: The labelled-card pattern keeps one markup for both widths, which is pure CSS and
works without JavaScript.

**Alternatives considered**:

- **Horizontal scrolling (`overflow-auto`)**: forbidden by FR-022 and FR-027.
- **Separate card markup for phones**: every row twice in the page.

---

## D12. Confirmations, back links and the remaining components

**Decision**:

- **`confirmation(question, consequence, action, verb, cancel_href)`** (FR-032):
  - `h1` = the question naming the item, for example "Delete “Physics”?";
  - the consequence in a paragraph;
  - `post_button(action, verb, kind="destructive")`, then **Cancel** as a link.
- **`refusal(question, reason, alternative=None, back_href, back_text)`**: same heading, the reason
  ("is in use"), the alternative action where today's page offers one (Deactivate, as a link or a
  `POST` exactly as now), and the existing "Back to …" link.
  - Texts are taken from the current templates unchanged.
- **`back_link(href, text)`** sits at the top of every page below an area's main page (FR-003,
  US2-4). It is rendered as `← {text}`.
  - The targets are fixed, not taken from browser history, and keep the selection in the address
    where the page has one (spec assumption).
  - Where a page already has a "Back to …" link with its own text, that text is reused.
  - Otherwise the text is "Back to {parent title}".
  - The list is in [contracts/pages.md §1](./contracts/pages.md#1-page-inventory).
- **`page_heading(title, action=None)`**: the `h1`, plus at most one primary link button beside it
  (FR-024, US3-1).
- **`badge(text, kind)`** (FR-028):
  - kinds `success` (Active), `muted` (Deactivated), `neutral` (Read) and `info` (Write);
  - text is required, and the macro refuses an empty one with a Jinja error, so colour is never
    the only signal.
- **`notice(text, kind)`** (FR-030):
  - `success` (role `status`), `error` (role `alert`), `info` (role `status`);
  - "Invitation sent to …" is a success notice; "Question data is temporarily unavailable…" is an
    info notice; sign-in failures are error notices or summary entries.
- **`empty_state(message, hint=None)`** (FR-029): the existing message ("No subjects yet", "Select
  a region", …), then the hint. Hints are new text, listed in [contracts/pages.md
  §4](./contracts/pages.md#4-wording-changes-fr-040).
- **`card(title, href=None, description=None)`**: a home-page card is a whole-card link with the
  area title and its one-line description (FR-026, FR-035).
- **`details_list(items)`**: the existing `<dl>` grid, stacked to one column below 768 px (FR-033).
- **Selectors** (FR-034):
  - `list_detail()` is the regions list beside the institutions table, as on the **Educational
    institutions** tab.
  - `chained_lists()` is the region → institution → class row of three `GET` forms, each
    auto-submitted by the existing `auto-submit.js`, as on the **Students** tab.
  - Both keep their field names, addresses and no-JavaScript behaviour exactly.

**Rationale**: Each of these is a pattern that already exists, built by hand on one or more pages.
The macros fix one look for each and leave behaviour where it is.

**Alternatives considered**:

- **A JavaScript modal for confirmations**: needs JavaScript, and changes the addresses
  (FR-040).

---

## D13. Identity: wordmark, logo mark, favicon

**Decision**:

- **The logo mark**: a simple inline SVG drawn for the application. The proposal for the mockup is
  a rounded square in `--sc-primary` with an amber (`--sc-accent`) star-burst, read as a "spark of
  knowledge" or a medal.
  - It uses `fill="currentColor"` and token-driven classes, so it follows the theme.
  - It lives once, as the `logo_mark()` macro in `components/icons.html`.
- **The wordmark**: "Student Competitions", set in Open Sans 700 beside the mark. It is text, not
  an image.
- **The favicon**:
  - `app/static/img/favicon.svg` is the same mark with fixed colours (a favicon cannot read page
    tokens);
  - `favicon-32.png` and `apple-touch-icon.png` (180 px) are rendered from it once and committed;
  - all three are linked from `layouts/base.html` (FR-008).
- **Other icons**: the account icon and the back arrow are inline SVG macros or a text arrow
  (`←`). There is no icon font and no icon library (spec assumption).
- **Approval**: the final mark is whatever the product owner approves in the mockup (D1). This
  decision fixes only the format.

**Rationale**: Inline SVG costs no request and follows the theme. A text wordmark stays sharp and
selectable.

**Alternatives considered**:

- **A raster logo**: blurry at high density, and it cannot follow the theme.
- **An icon font**: a new asset family for two icons.

---

## D14. The home page: a start page for the current role

**Decision**:

- **`Area` gains a field**: `description: str`, a one-line description used by the home page cards
  (FR-035):
  - **Administrator area**: "Manage teachers, educational institutions and subjects."
  - **Teacher area**: "Manage your classes and invite your students."
  - **Student area**: "Take part in competitions and see your results."
  - **Staff area**: "Pages shared by administrators and teachers."
- **The page**:
  - **Greeting**: `h1` "Welcome to Student Competitions", followed by the tagline. The `h1` still
    contains the application name, so `test_home_headline_is_the_application_name` keeps its
    meaning.
  - **Cards**: then one `card()` per area in `areas_for(current_role)`, under the heading "Your
    areas".
  - **Sample questions**: then the sample questions, unchanged in content and order (FR-036).
- **The database status line** moves into `{% block footer_extra %}`, so it appears in the footer
  of the home page only, in muted text (FR-036, spec assumption).
- **"Data temporarily unavailable"** is an info `notice()` with the same text and role (US6-4).
- **The description paragraph** (`APP_DESCRIPTION`) stays as the page's `<meta name="description">`
  only. It is no longer repeated in the body, because the cards now say what each area is for.
  This is listed in [contracts/pages.md §4](./contracts/pages.md#4-wording-changes-fr-040).

**Rationale**: The links and roles come from the same `AREAS` declaration as before, so what a role
is shown and what it may open still cannot drift apart.

**Alternatives considered**:

- **A personal greeting ("Hello, Taras")**: administrators have no stored names, so the greeting
  would differ by role for no benefit.

---

## D15. The gallery exists only outside production

**Decision**:

- **Where it is served**: `GET /admin/components` lives in a new router,
  `app/routers/admin_components.py`. The router is created with
  `APIRouter(route_class=DevelopmentOnlyRoute)`.
- **`DevelopmentOnlyRoute`** is defined in the same module and subclasses `APIRoute`. It overrides
  `matches(scope)` to return `(Match.NONE, {})` when `scope["app"].state.settings.production` is
  true. It also returns no match when `settings` is missing, which fails closed.
- **In production**, the address therefore matches no route. Starlette answers it like any unknown
  address, with the friendly 404 page, before `resolve_access` runs. The response is the same for
  an anonymous visitor, any role and an administrator (FR-038a, SC-009, spec edge case).
- **Production detection** is `settings.production`. It is the same flag, read from `RENDER`, that
  the milestone 3 and 4 guards use (FR-038a).
- **Outside production**, the route is an ordinary administrator page:
  - `@allow_roles(Role.ADMIN)`, so other current roles get "Access denied" naming their role
    (FR-038, US7-3);
  - rendered through `render_admin` with no tab marked current;
  - not in `ADMIN_TABS` (US7-2).
- **Sample data**: frozen dataclasses and tuples declared in the router module. There is no session
  dependency, so the handler cannot touch the database (FR-037, US7-4).
- **The page** shows every component and variant listed in contracts/components.md, in the current
  theme.

**Rationale**:

- **Before authentication**: route matching runs before every dependency. Hiding the route there
  is the only place where "not found for everyone, signed in or not" holds. A check inside the
  handler or in `resolve_access` would send anonymous visitors to sign in, and that reveals the
  address exists.
- **Decided per request**: the decision reads the running app's settings, so tests can switch it
  with `app.state.settings = replace(settings, production=True)`. No module reload or second
  application instance is needed.

**Alternatives considered**:

- **Including the router only when `RENDER` is unset, at import time**: it reads the environment
  outside `config.py`, and it is testable only by reloading `app.main`.
- **Raising 404 in the handler**: anonymous visitors get a 303 to sign in, and teachers get a 403,
  so the address's existence leaks.
- **A middleware that answers 404 for the path**: a second mechanism for one route, and it would
  have to render the friendly 404 page itself, outside the exception handlers.

---

## D16. Automated stylesheet and resource checks

**Decision**: one new unit-test module, `tests/unit/test_stylesheet.py`, with no new dependency.

- **Class usage** (FR-049, SC-004):
  - It collects the class names used in `app/templates/**/*.html`. Each `class="…"` attribute is
    read with every `{{ … }}` and `{% … %}` stripped out. It also reads the string literals of
    `{% set …_class(es) = … %}` statements in `components/`, which is the only place a class may be
    built dynamically.
  - It collects the classes defined in `pico.min.css` and in `app.css` with a selector regex.
  - It asserts that every used class is defined, and that every class in `app.css` is used.
- **No inline style**: no template contains ` style=` (FR-049).
- **No page-specific classes**: a denylist of every class listed in D8 asserts that none remains
  (FR-041).
- **Tokens only**: colours and pixel lengths appear only inside the token block (FR-012, D2).
- **No other site** (FR-048, SC-003):
  - no `src=`, `href=` or `action=` in a template starts with `http:`, `https:` or `//`;
  - `app.css` has no `@import` and no `url(` outside `/static/`.
  - Emails are not templates under `app/templates/`, so their absolute links are untouched.
- **Readable text sizes** (SC-008): the token values are asserted directly. `--sc-text-body` is at
  least `1rem`, or `1.125rem` inside the `1024px` query, and `--sc-line-height` is at least 1.5.

**Rationale**: These rules are cheap to break by accident and cheap to check statically. One test
module keeps them in CI for every later milestone, which is what makes the guidelines binding
(FR-045).

**Alternatives considered**:

- **A CSS linter (stylelint)**: a Node toolchain.
- **Checking only by review**: the rules decay in the first milestone without a check.

---

## D17. Keeping the milestone 1–9 tests meaningful through a full rebuild

**Decision**:

- **A shared helper**: `tests/html.py` is a small stdlib `html.parser` wrapper. It answers questions
  by meaning, not by markup:
  - `h1(body)`;
  - `links(body, within=None)`, as `(href, text, attrs)`;
  - `forms(body)`, as `(method, action, buttons)`;
  - `nav(body, label)`;
  - `region(body, "header" | "main" | "footer")`;
  - `badges(body)`;
  - `error_summary(body)`, as `(heading, [(href, text)])`;
  - `field_error(body, field_id)`;
  - `table_rows(body)`, as a list of `{label: text}`.
- **What changes in the tests**: assertions that match literal markup are rewritten to use the
  helper. Examples are `'<a href="/admin/subjects/new" role="button">Create</a>'`,
  `'<nav class="admin-tabs"'`, `'<td class="subject-name">'` and `'<span class="site-title">'`.
- **What stays**:
  - the address, the method, the text, the status code and the role are still asserted exactly;
  - no assertion about behaviour or access is removed or loosened (SC-002).
- **The changed modules** are listed in [plan.md](./plan.md#changes-to-existing-tests-why-they-change).
  Each change is a markup change, or a wording change listed in contracts/pages.md §4.

**Rationale**: Every template changes, so tests that pin markup would all fail for reasons that are
not regressions. Asserting by meaning keeps them strict about behaviour and lets later milestones
restyle without touching them again.

**Alternatives considered**:

- **Keeping the old markup and classes so the tests pass**: contradicts FR-041.
- **Adding BeautifulSoup**: a new test dependency, for queries the stdlib parser handles.

---

## D18. Wording: only plain-language fixes, each listed

**Decision**:

- **The rule**: texts, messages and headings are copied from the current templates. A text changes
  only where it breaks a plain-language rule in FR-006, or where FR-028, FR-029 or FR-031 require
  new text.
- **New text** covers the empty-state hints, "There is a problem", the area descriptions, the theme
  switch labels and the skip link.
- **The list**: every change, with its rule, is in [contracts/pages.md
  §4](./contracts/pages.md#4-wording-changes-fr-040). Any further change found during
  implementation is added there before merge (SC-011).
- **What the list already includes**:
  - "Create" becomes "Create subject", "Create region" or "Create educational institution"
    (buttons name the action);
  - "Inactive" becomes "Deactivated" on the subject list (one word for one status, FR-028);
  - "switch at any time from the header" becomes "from the menu at the top" (the role switch moved,
    FR-019).

**Rationale**: FR-040 allows exactly these changes and requires the list. Keeping it as a contract
file makes the review mechanical.

---

## D19. The constitution amendment

**Decision**:

- **How**: the constitution is amended by `/speckit-constitution`, in a dedicated pull request as
  Governance requires. The version goes from 1.0.1 to 1.1.0, a MINOR change for materially expanded
  guidance.
- **What changes**:
  - **Principle II** gains a bullet. Every page MUST be built from the component library in
    `app/templates/components/` and follow `docs/requirements/ui-guidelines.md`. A new pattern MUST
    be added to the library, the gallery and the guidelines first (FR-045).
  - **The Styling row** of the Technology Stack table reads: Pico.css v2, restyled only through
    overriding its CSS variables with the tokens in `static/css/app.css`; no CSS build step; fonts
    self-hosted in `static/fonts/`; nothing loaded from another site.
  - **Application Layout** adds `templates/components/` and `static/fonts/`.
  - **The Constitution Check** of every later `plan.md` gains a row for the guidelines.
- **Order**: the amendment PR is opened as soon as the guidelines document exists in draft, and it
  merges before this feature's PR. The rest of this plan does not depend on its wording.

**Rationale**: The spec's dependency section requires the governance route. A dedicated PR keeps
the amendment reviewable on its own.

**Alternatives considered**:

- **Editing `constitution.md` inside this feature's PR**: contradicts Governance ("a dedicated pull
  request").

---

## D20. The UI guidelines document

**Decision**: `docs/requirements/ui-guidelines.md` has these sections, in order (FR-043, FR-044):

1. **Audience**: students from year 1 to university, mostly on phones; teachers and administrators,
   mostly on desktops.
2. **Principles**: calm and focused, clear and consistent, readable, plain language, forgiving.
   Each has its rules and sources:
   - the GOV.UK Design System (error summary, confirmation and button patterns, plain-language
     guidance);
   - the W3C/WAI *Cognitive Accessibility* guidance (*Making Content Usable*);
   - Nielsen Norman Group research on scanning, line length and children's web use;
   - the British Dyslexia Association *Style Guide* (sizes, line height, no italics or
     justification);
   - Material and Apple HIG for touch-target size.
3. **Tokens**: the table from [data-model.md §2](./data-model.md#2-design-tokens), with the rule
   "use a token; never a literal".
4. **Layout**: the frame, the content width, the breakpoints and phone behaviour.
5. **Components**: one entry per macro, with its purpose, when to use it and when not, its variants,
   a call example, and a link to its place in the gallery.
6. **Buttons**: the three kinds, "one primary per page or section", and links that look like the
   action they lead to.
7. **Wording patterns**: buttons, confirmations, errors, empty states and notices, with examples
   from the application.
8. **Phone behaviour**: tables as cards, the folded user menu, the stacked selectors and wrapping.
9. **Themes**: how a token gets its dark value, and checking both themes.
10. **Checks**: what `test_stylesheet.py` enforces, and how to add a pattern (library, then gallery,
    then guidelines, then use).
11. **Research for later screens**: for milestone 13, taking a competition. A visible countdown with
    warnings before the end, a "Saved" status per answer, and a clear final **Submit** with a
    confirmation that says what cannot be changed afterwards.

**Rationale**: The section list mirrors FR-043 and FR-044 one-to-one, so the review in User Story 8
is a checklist.
