# Implementation Plan: Professional Design System and UI Guidelines (Milestone 10)

**Branch**: `010-design-system-ui-guidelines` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-design-system-ui-guidelines/spec.md`

## Summary

The application keeps everything it does and changes how it looks and reads. Behaviour,
addresses, form fields, messages and access rules stay the same (FR-040).

**Gate first** (research D1):

- A static mockup of the identity and five key pages, at 375 and 1280 px, light and dark, is
  approved by the product owner.
- The approval is recorded in `design-approval.md` before any page template changes.

**Tokens** (D2–D4):

- **One token block** at the top of `app/static/css/app.css` defines everything once, as `--sc-*`
  custom properties: the Classroom blue palette, light and dark; Open Sans; the 8 px spacing grid;
  8 and 12 px radii; the type scale; and the 72 rem content width.
- **Mapping onto Pico**: a mapping block sets Pico v2's own variables from the tokens, with Pico's
  selectors, so Pico restyles itself. `pico.min.css` is untouched.
- **The font**: Open Sans is self-hosted as four variable `woff2` subsets.

**Theme** (D5, D6):

- **The cookie**: `sc_theme` is `light` or `dark`; no cookie means Device. It is read by a context
  processor.
- **Rendering**: it is rendered as `data-theme` on `<html>` by the server, so there is no flash and
  no script.
- **The switch**: `POST /theme`, a new public route behind the existing cross-site check, sets the
  cookie and returns to a checked local address.

**Components** (D7–D13): Jinja macros in `app/templates/components/`.

- frame: top bar, a `<details>` user menu, theme switch, area tabs, back link, page heading;
- buttons in three kinds, with links styled as the action they lead to;
- card;
- a data table that becomes labelled cards below 768 px;
- badges;
- notice and empty state;
- form field and error summary;
- confirmation and refusal;
- details list;
- the two selectors;
- icons.

**Pages** (D10, D12, D14, D17, D18):

- **All 43 existing templates are rebuilt** from the components.
- **Form errors**: four handlers move to the shared `errors` / `form_error` shape, so every form
  gets an error summary.
- **The home page** becomes a start page with one card per area. `Area` gains `description`.
- **Wording**: the only changes are in [contracts/pages.md §4](./contracts/pages.md#4-wording-changes-fr-040).
- **Old classes**: the page-specific classes are deleted.

**Gallery** (D15): `GET /admin/components` is administrator-only and is served by a
`DevelopmentOnlyRoute`. It matches no request when `settings.production` is true, so in production
it is an unknown address for everyone.

**Governance** (D16, D19, D20):

- **The guidelines**: `docs/requirements/ui-guidelines.md` is written.
- **The constitution**: it gains a pointer to the guidelines, through `/speckit-constitution` in a
  dedicated PR.
- **The checks**: `tests/unit/test_stylesheet.py` enforces the class, inline-style, token and
  off-site rules in CI from now on.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2, Pico.css v2.1.1 (vendored), SQLModel, Alembic, psycopg 3,
  python-multipart and `cryptography`.
- **No new runtime dependency** (FR-047). The new assets are not dependencies:
  - the Open Sans font files, under the SIL OFL;
  - three favicon files.
- No HTMX (none is needed), no build step, and no new script.

**Storage**: unchanged. No table, no column and no migration. The theme choice is a browser cookie
([data-model.md §1](./data-model.md#1-theme-choice-cookie-not-stored-on-the-server)).

**Testing**:

- pytest with the FastAPI `TestClient`, on SQLite and PostgreSQL, as before.
- New: `tests/html.py`, a stdlib `html.parser` helper that queries pages by meaning (research D17).
- New: `tests/unit/test_stylesheet.py`, the static checks (research D16).
- New integration modules:
  - `test_theme.py`;
  - `test_component_gallery.py`;
  - `test_layout.py`;
  - `test_page_patterns.py`.
- Screenshots: Playwright, through `uv run --with playwright`, is a one-off review aid and not part
  of the suite (research D1).

**Target Platform**:

- **Server**: a Linux container on Render, unchanged.
- **Browsers**: current major desktop and mobile browsers, from 375 px wide.
- **Features relied on**:
  - `prefers-color-scheme`;
  - `<details>`;
  - CSS custom properties;
  - `woff2` variable fonts;
  - SVG favicons, with a PNG fallback.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**: none beyond the defaults.

- The first paint needs `pico.min.css`, `app.css` and the latin font subset, which is preloaded.
- Fonts use `font-display: swap`.
- The theme adds one cookie read per request, with no database access.

**Constraints**:

- **No behaviour change** (FR-040, FR-050, SC-011): addresses, field names, statuses, messages and
  access rules.
- **Nothing from another site** (FR-048).
- **No inline `style`, and every class defined and used** (FR-049).
- **No sideways scroll at 375 px** (FR-022).
- **Body text sizes** (FR-004): body text is at least 16 px on a phone and at least 18 px from
  1024 px, with line height at least 1.5.
- **Both themes are complete** (FR-013).
- **No JavaScript** is needed for the menu, the theme switch, the tabs or the confirmations.

**Scale/Scope**:

- 2 new routes: `POST /theme`, which is public, and `GET /admin/components`, for administrators
  outside production.
- 2 new router modules.
- 1 new core module, `theme.py`.
- 11 component files.
- 43 templates rebuilt, plus 1 new (the gallery).
- `app.css` rewritten.
- 4 font files, 3 favicon files, 1 guidelines document, 1 mockup and 1 approval record.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 9 is merged into `main` (PR #32). A later ad-hoc styling pass (PR #33) was reverted in PR #36 (`8be231a`), so this branch starts from the milestone 9 templates as delivered. The milestone is one user-visible slice: every page restyled end to end, the theme switch, the home cards and the gallery. It ends in a demonstrable result: the approved look on every page in both themes. Nothing from milestones 11–13 is built. The guidelines only record research for milestone 13 (FR-044, FR-050). | ✅ |
| II. Server-rendered simplicity | Jinja2 pages and Pico.css only. The theme is rendered by the server from a cookie, and the menu is a native `<details>`, so no script is added. The existing `auto-submit.js` is unchanged. There is no build step and no new dependency (FR-047). The new abstractions each have a present need: the components serve 43 templates, and the theme module serves every page. `DevelopmentOnlyRoute` serves exactly one route, but it is the only mechanism that satisfies FR-038a (see Complexity Tracking). HTMX partials are not needed. | ✅ |
| III. Test-backed delivery | Every story maps to a test module ([quickstart.md §1](./quickstart.md#1-automated-checks-ci)). The milestone _Test:_ line is covered: the stylesheet checks, the theme from the server, both themes, every page rebuilt, and the gallery's access. The two new routes have allowed and denied tests: `POST /theme` for anonymous visitors, every role and cross-site posts; `GET /admin/components` per role and in production. The milestone 1–9 suite stays green on both engines. Its markup assertions move to meaning-based queries, and no behaviour assertion is removed (research D17). | ✅ |
| IV. Role-based access & data scoping | `POST /theme` is added to `PUBLIC_ROUTES` in a reviewed change. It reads and writes no data and acts only on the requesting browser. The gallery is `@allow_roles(Role.ADMIN)`, and the existing route-table sweep covers it. In production it matches no route, which is stricter than deny-by-default. No existing declaration changes. Hiding the gallery from the tabs is presentation only; the server enforces access. | ✅ |
| V. Secure authentication & secrets | No change to sign-in, sessions, OTP or secrets. `POST /theme` goes through the cross-site check. The theme cookie is HttpOnly, `SameSite=Lax`, `Secure` in production, and holds no identifier. The return target is checked against open redirects with the `safe_next_path` rules, plus a route-table check (research D6). Nothing new is logged. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | No schema change, no migration and no stored data. | ✅ |
| Stack: Styling row | Pico.css is restyled only by overriding its variables. Custom CSS lives only in `static/css/app.css`. There is no CSS build step. Pico's own stylesheet is not edited. The fonts are self-hosted static files. | ✅ |
| Stack: component timing | No stack component is introduced early. Playwright is used once, through `uv run --with`, to capture review screenshots. It is not added to the project or the test suite, which keeps it in milestone 12 (see Complexity Tracking). | ✅ |
| Application Layout | It is refined, not bypassed, with `templates/components/` and `static/fonts/`. The amendment (research D19) records both. Routers stay thin: the gallery's sample data is presentation, not business logic. | ✅ |
| Governance | The styling-rule pointer to the guidelines (FR-045) is a constitution amendment. It goes through `/speckit-constitution` in a dedicated PR, as version 1.1.0 (MINOR), merged before this feature (research D19). | ✅ |
| Workflow gates | The plan lists the role-access tests for both new routes and the README update (theme, gallery, fonts). It also lists the guidelines document and the `milestones.md` update on delivery. No migration is needed. | ✅ |

**Post-design re-check (after Phase 1)**: still all ✅.

- **Allowlist**: `PUBLIC_ROUTES` and the write set each grow by exactly `("POST", "/theme")`
  ([contracts/http-routes.md](./contracts/http-routes.md)).
- **No change to existing routes**: no existing route changes its address, method, fields or
  declaration.
- **No new dependency**: none is added to `pyproject.toml` or `uv.lock`.
- **No inline styles, no foreign loads**: there are no inline styles, and nothing is loaded from
  another site. `test_stylesheet.py` enforces both from this milestone on.

## Project Structure

### Documentation (this feature)

```text
specs/010-design-system-ui-guidelines/
├── plan.md                   # This file
├── research.md               # Phase 0: decisions D1–D20
├── data-model.md             # Phase 1: theme cookie, design tokens, component inventory, changed declarations
├── quickstart.md             # Phase 1: automated checks, approval, manual walk-through, screenshot review
├── contracts/
│   ├── http-routes.md        # Phase 1: POST /theme, GET /admin/components, theme on every page
│   ├── components.md         # Phase 1: every macro, its parameters, variants and emitted classes; gallery checklist
│   └── pages.md              # Phase 1: page inventory, back links, form error mapping, wording changes
├── mockup/index.html         # Before rebuild: the static mockup for approval (research D1)
├── design-approval.md        # Before rebuild: approval record and change log (FR-046)
├── checklists/requirements.md  # From /speckit-specify
└── tasks.md                  # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
app/
├── core/
│   ├── theme.py                       # NEW: Theme, THEME_COOKIE_NAME, read_theme, parse_theme, apply_theme
│   ├── security.py                    # CHANGED: + safe_return_path (safe_next_path rules; allows /login and /role)
│   ├── auth.py                        # CHANGED: PUBLIC_ROUTES += ("POST", "/theme")
│   └── templates.py                   # CHANGED: + _theme context processor (theme, theme_return)
├── routers/
│   ├── theme.py                       # NEW: POST /theme
│   ├── admin_components.py            # NEW: DevelopmentOnlyRoute, GET /admin/components, sample data
│   ├── areas.py                       # CHANGED: Area.description
│   ├── admin_subjects.py              # CHANGED: form context → errors/values (same messages)
│   ├── admin_institutions.py          # CHANGED: region and institution form context → errors/values
│   └── auth.py                        # CHANGED: page context → errors/form_error (same messages)
├── main.py                            # CHANGED: include theme and admin_components routers
├── static/
│   ├── css/app.css                    # REWRITTEN: tokens → Pico mapping → base → layout → components
│   ├── fonts/                         # NEW: open-sans-{latin,latin-ext,cyrillic,cyrillic-ext}.woff2, OFL.txt
│   └── img/                           # NEW: favicon.svg, favicon-32.png, apple-touch-icon.png
└── templates/
    ├── components/                    # NEW: frame, button, card, table, badge, feedback, form,
    │                                  #      confirmation, details, selectors, icons (.html)
    ├── layouts/base.html              # CHANGED: data-theme, color-scheme, font preload, favicons, frame
    ├── layouts/admin.html             # CHANGED: area_tabs
    ├── layouts/teacher.html           # CHANGED: area_tabs
    └── pages/**                       # CHANGED: all 43 templates rebuilt (contracts/pages.md §1)
        └── admin/components.html      # NEW: the gallery

tests/
├── html.py                            # NEW: meaning-based HTML queries (research D17)
├── unit/
│   ├── test_stylesheet.py             # NEW: classes, inline style, tokens, off-site, text sizes
│   ├── test_theme.py                  # NEW: parse_theme, read_theme, apply_theme
│   └── test_safe_next.py              # CHANGED: + safe_return_path cases
└── integration/
    ├── test_theme.py                  # NEW: US5
    ├── test_component_gallery.py      # NEW: US7
    ├── test_layout.py                 # NEW: US2, US6 (frame, menu, favicon, footer)
    ├── test_page_patterns.py          # NEW: US3 (error summary, confirmations, back links, badges, link buttons)
    └── (milestone 1–9 modules)        # CHANGED: markup assertions → tests/html.py (see below)

docs/requirements/ui-guidelines.md     # NEW: the binding guidelines (research D20)
.specify/memory/constitution.md        # CHANGED in a dedicated PR via /speckit-constitution (research D19)
README.md                              # CHANGED: theme switch, gallery (local only), fonts and licence
docs/requirements/milestones.md        # CHANGED on delivery: milestone 10 → "Delivered"
.gitignore                             # CHANGED: + screenshots/
```

**Structure Decision**: the existing single-application layout from the constitution, refined with
two new directories, `templates/components/` and `static/fonts/`.

- **The components** are templates, not Python, so they sit beside `layouts/` and `pages/`.
- **The theme** is request plumbing like the session cookie, so it lives in `core/`.
- **The gallery** has its own router because it has its own route class.
- **No service module is added**, since there is no business logic.

### Changes to existing tests (why they change)

Every template is rebuilt, so tests that matched literal markup fail for reasons that are not
regressions. Each change below replaces a markup match with a query from `tests/html.py`. The
address, method, text, status and role are still asserted exactly (research D17, SC-002).

| Test | Change | Reason |
|---|---|---|
| `test_home.py` | The header title, role and logout: queried from `header`, not `<span class="site-title">`. The `h1` comes from `h1()`, and it still contains `APP_NAME`. The unavailable notice is found by text and `role="status"`. The question list is found by its section. The footer release checks are unchanged. | FR-018, FR-019; wording [pages.md §4](./contracts/pages.md#4-wording-changes-fr-040) (greeting) |
| `test_admin_area.py`, `test_admin_subjects.py`, `test_admin_institutions.py`, `test_access_control.py` | The tabs come from `nav("Administrator area")` instead of `<nav class="admin-tabs"`. Row names come from `table_rows()`, not `td class=`. Links and forms come from `links()` and `forms()`. "Create" becomes "Create subject", "Create region" or "Create educational institution". The status "Inactive" becomes "Deactivated". The selected region is found by `aria-current="true"`, not `class="selected"`. | FR-041; wording §4 |
| `test_admin_teachers.py`, `test_profile.py`, `test_teacher_students.py`, `test_teacher_classes.py`, `test_availability.py` | `<small class="status-deactivated">(deactivated)</small>` becomes the **Deactivated** badge, from `badges()`. Field-error ids become `{field}-error`. | FR-028; pages.md §1.4 |
| `test_role_choice.py`, `test_role_switch.py` | The role-switch form is found inside the user menu (`<details>`), not in the header row. The role-choice sentence uses its new wording. | FR-019; wording §4 |
| `test_login_flow.py`, `test_data_deletion.py`, `test_invitation_*.py`, `test_student_invitation*.py`, `test_teacher_invitation.py`, `test_names_on_acceptance.py` | Messages are found in the error summary and beside the field (or in a notice), not as `auth-message`. The texts and status codes are unchanged. | FR-031; research D10 |
| `test_routes.py` | `test_the_allowlist_is_exact` and `test_the_write_routes_are_exact` each gain `("POST", "/theme")`. | contracts/http-routes.md §1 |
| `test_cross_site.py` | A `POST /theme` case is added. | Constitution V |

## Implementation Order (for /speckit-tasks)

1. **Approval gate** (US1, blocks every page change):
   - the Open Sans files and the draft tokens;
   - `mockup/index.html`;
   - the logo mark and favicon;
   - product-owner review rounds, logged in `design-approval.md`, ending in "Approved".
2. **Test harness**:
   - `tests/html.py`;
   - rewrite the markup assertions of the milestone 1–9 tests to use it, against the **current**
     templates. The suite must stay green, which proves the rewrite kept every assertion's meaning
     before any page changes.
3. **Foundation**:
   - the token block and Pico mapping in `app.css`;
   - `@font-face`;
   - `core/theme.py` and the `_theme` context processor;
   - `safe_return_path`;
   - `POST /theme` and its `PUBLIC_ROUTES` entry;
   - `base.html` with `data-theme`, `color-scheme`, favicons and the frame;
   - `components/frame.html` and `icons.html`;
   - `test_theme.py` (unit and integration), `test_layout.py` and the `test_routes.py` update.
4. **Component library**:
   - every macro in [contracts/components.md](./contracts/components.md), with its CSS;
   - `admin_components.py` with `DevelopmentOnlyRoute` and the gallery page;
   - `test_component_gallery.py`.
5. **Stylesheet checks**: `tests/unit/test_stylesheet.py`. It goes red, listing the page-specific
   classes still in use, and goes green as step 6 removes them.
6. **Pages**, in this order, the suite green after each group:
   1. the frame layouts (`admin.html`, `teacher.html`);
   2. sign-in, code and role choice;
   3. home (`Area.description`, cards, footer line);
   4. profile and withdrawal;
   5. invitation and data deletion pages;
   6. error pages;
   7. the administrator tabs and their forms and confirmations (the form context change in
      `admin_subjects` and `admin_institutions`);
   8. the teacher area.

   Then `test_page_patterns.py`.
7. **Clean-up**:
   - delete every page-specific class;
   - `test_stylesheet.py` green;
   - `ruff`.
8. **Documents**:
   - `docs/requirements/ui-guidelines.md`;
   - the constitution amendment PR via `/speckit-constitution`;
   - the README.
9. **Review**:
   - the screenshot capture and report (0 sideways scroll, text sizes);
   - product-owner review logged;
   - the manual walk-through ([quickstart.md §3](./quickstart.md#3-manual-walk-through-local));
   - the wording list in [contracts/pages.md §4](./contracts/pages.md#4-wording-changes-fr-040)
     completed.

## Complexity Tracking

> There are no constitution violations. The choices below look like extra complexity, so each one
> is justified.

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| `DevelopmentOnlyRoute`, an `APIRoute` subclass whose `matches()` is off in production | FR-038a: in production the gallery must be "not found" to everyone, including anonymous visitors, exactly like an unknown address. Only route matching runs before `resolve_access` (research D15). | A check in the handler or in `resolve_access` sends anonymous visitors to sign in (303) and teachers to 403, which reveals the address. Registering the router conditionally at import reads the environment outside `config.py`, and is testable only by reloading `app.main`. |
| A `--sc-*` token layer mapped onto Pico's variables, rather than setting Pico's variables directly | The top bar, accent, badges, danger and tints have no Pico variable. Product-named tokens are what the guidelines document and later milestones use (research D2). | Writing Pico variables directly still needs new names for half the palette, and ties the guidelines to Pico's naming. |
| `POST /theme` checks the return target against the route table | A page shown after a failed `POST` may have no `GET` counterpart. Returning there would land on a 405, which breaks FR-017 (research D6). | Trusting the path alone gives a broken page in that case. The `Referer` header is unreliable. |
| Playwright through `uv run --with playwright` for review screenshots, before milestone 12 | SC-001 needs every page captured at two widths in two themes, with a sideways-scroll and text-size report (research D1). | Manual screenshots for about 40 pages × 4 combinations are slow and miss sideways scroll. Adding Playwright to the project or the test suite brings a stack component in early. |
| `tests/html.py`, a meaning-based query helper, and rewriting the markup assertions before the rebuild | Every template changes. The tests must keep asserting behaviour without pinning markup (SC-002, research D17). | Keeping the old classes to satisfy the tests contradicts FR-041. Deleting the assertions loses coverage. BeautifulSoup is a new dependency. |
