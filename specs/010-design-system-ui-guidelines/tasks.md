---

description: "Task list for milestone 10: professional design system and UI guidelines"
---

# Tasks: Professional Design System and UI Guidelines (Milestone 10)

**Input**: Design documents from `/specs/010-design-system-ui-guidelines/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/components.md](./contracts/components.md), [contracts/pages.md](./contracts/pages.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle III makes tests non-negotiable, and the plan names every
new test module (plan "Testing", quickstart §1).

- **Engines**: every database test runs on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL`
  is set (the local `sc-pg` container), through the existing fixtures in `tests/conftest.py`.
- **Signed-in clients**: `admin_client` and `client_as`, and the cast helpers in `tests/conftest.py`
  (`make_institution`, `make_teacher`, `invite_and_accept`, the student helpers).
- **Markup in tests**: new and rewritten assertions query pages through `tests/html.py` (research
  D17), never by literal markup or class name.

**Organization**: tasks are grouped by user story (US1–US8 in spec.md). The order follows the plan's
"Implementation Order":

1. **US1, the approval gate**, comes before Foundational: no look change is made until the mockup is
   approved (FR-046). The test-harness half of Foundational (3a) changes no look, so it may run
   alongside the gate.
2. **Foundational** builds the tokens, the component library and the frame, which every story uses.
3. **US2–US4** rebuild every existing page. US4 ends with the removal of the page-specific CSS.
4. **US5–US8** add the theme choice, verify the identity, add the gallery and write the guidelines.

**Reference implementation**: read these before starting, and match their docstring style, naming,
comment density and error handling:

- `app/core/templates.py` (context processor, globals), `app/core/security.py` (`safe_next_path`),
  `app/core/auth.py` (`PUBLIC_ROUTES`, `resolve_access`, the session cookie flags);
- `app/routers/admin.py` (`ADMIN_TABS`, `render_admin`), `app/routers/admin_teachers.py` (the
  `values` / `errors` / `form_error` shape already used there), `app/routers/teacher_students.py`;
- `tests/integration/test_routes.py`, `test_access_control.py`, `test_cross_site.py`.

**Rules for every task** (plan Constraints, FR-040, FR-047–FR-050):

- **No behaviour change**: addresses, methods, form field names, status codes, redirects, messages
  and `@allow_roles` declarations stay exactly as they are. A text changes only as listed in
  [contracts/pages.md §4](./contracts/pages.md#4-wording-changes-fr-040); any other change found is
  added to that list, with its rule, in the same task.
- **No inline `style`**, and every class used in a template is defined in `pico.min.css` or
  `app.css` (FR-049). Classes belong to components, never to pages.
- **Tokens only**: colours and lengths in `app.css` come from the `--sc-*` tokens. The only literal
  `px` values outside the token block are the `768px` and `1024px` media queries (research D2).
- **Nothing from another site** (FR-048): only `/static/…` resources. `pico.min.css` is never
  edited.
- **No script**: no JavaScript and no HTMX are added. `app/static/js/auto-submit.js` is unchanged.
- **No new dependency** in `pyproject.toml` or `uv.lock`. One-off tools (Playwright, fonttools) run
  through `uv run --with …` and are never added.
- **Escaping**: macros take plain strings; rich content goes through `{% call %}` / `caller()`.
- **Suite green**: after each page task, `uv run pytest` passes. A test changes only where it pinned
  markup or a wording change listed in pages.md §4 (SC-002). `tests/integration/form_contract.json`
  never changes after T092: a failing form contract means a field was renamed or lost, so the
  template is fixed, not the file.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US8)

---

## Phase 1: Setup

**Purpose**: the baseline and the static assets the mockup needs.

- [X] T001 Record the baseline: run `uv run ruff check .`, `uv run ruff format --check .` and `TEST_POSTGRES_URL=postgresql://… uv run pytest` on this branch before any change, and note the passing test count in the PR description draft. Every later checkpoint compares against it (SC-002).
- [X] T002 [P] Add Open Sans to `app/static/fonts/` per research D4:
  - four variable-weight (`wght` axis) `woff2` subsets, named exactly `open-sans-latin.woff2`, `open-sans-latin-ext.woff2`, `open-sans-cyrillic.woff2` and `open-sans-cyrillic-ext.woff2`;
  - taken from the open-source release (the `googlefonts/opensans` repository). If the release has no subset `woff2` files, subset the variable font once with `uv run --with 'fonttools[woff]' pyftsubset … --flavor=woff2`, using the `unicode-range` Google Fonts publishes for each subset, and keep those ranges for the `@font-face` rules in T015;
  - `app/static/fonts/OFL.txt`, the SIL Open Font License text from the same release;
  - record the source URL and commit in the commit message. Nothing is added to the project.
- [X] T003 [P] Add `screenshots/` to `.gitignore` (research D1).

---

## Phase 2: User Story 1 — The product owner approves the look before the pages are rebuilt (Priority: P1) 🎯 Gate

**Goal**: an approved, recorded mockup of the identity and five key pages, before any look change.

**Independent Test**: `mockup/index.html` opens from `file://` with no outside request, shows the
identity and the five pages in all four width/theme frames, and `design-approval.md` has an
"Approved" entry committed before the first commit that changes `app/templates/` or `app.css`
(quickstart §2).

- [X] T004 [P] [US1] Draw the logo mark (FR-008, research D13): a simple mark in `--sc-accent` amber on the deep blue of `--sc-top-bar`, legible at 16 px.
  - `app/static/img/favicon.svg`: `viewBox="0 0 32 32"`, fixed colours (no `currentColor`, no CSS);
  - `app/static/img/favicon-32.png` (32 × 32) and `app/static/img/apple-touch-icon.png` (180 × 180), rendered from the SVG once (for example with Playwright through `uv run --with playwright`, or `rsvg-convert` if installed). Nothing is added to the project.
- [X] T005 [US1] Create `specs/010-design-system-ui-guidelines/mockup/index.html`, one static self-contained page per research D1:
  - **Inline CSS** holding a draft of the full token block with the exact values of [data-model.md §2.1–§2.4](./data-model.md#2-design-tokens) (the given and the derived colours, type, spacing, radii, content width), the `@font-face` rules loading `../../../app/static/fonts/open-sans-*.woff2` by relative path, and draft CSS for every component the five pages use;
  - **Identity**: the wordmark "Student Competitions" beside the logo mark (inline SVG, the same drawing as T004), the favicon at 16 and 32 px, swatches of every colour token in light and dark, and the type scale (h1–h4, body, small);
  - **Five pages**, each in four frames (375 px light, 375 px dark, 1280 px light, 1280 px dark), as fixed-width `<div data-theme="light|dark">` frames on one page: sign-in (with the theme switch), home (greeting and one card per area), the **Subjects** list (heading with **Create subject**, data table with **Active** / **Deactivated** badges and row actions; the 375 px frame shows rows as cards), **Create subject** with the duplicate-name error (error summary "There is a problem", field error, kept value), and **Delete “Physics”?** with its "is in use" refusal offering **Deactivate**;
  - every frame shows the top bar, the user menu (open in one frame), the tabs where the page has them and the footer;
  - no `<script>`, and no `http:`, `https:` or `//` URL anywhere.
- [ ] T006 [US1] Create `specs/010-design-system-ui-guidelines/design-approval.md`: the approver (the product owner), the mockup path, and a log table with the columns *Date*, *Round*, *Mockup commit*, *Changes requested*, *Changes made*, *Status*. The *Status* cell is `Changes requested` for a review round and exactly `Approved` for the approving round, written as the table cell `| Approved |`; that cell appears nowhere else in the file, so the gate check (T089, quickstart §2) finds the approving commit. Commit the mockup and the record, then **STOP and ask the product owner** to review `mockup/index.html` in a browser (quickstart §2). Log the round.
- [ ] T007 [US1] Apply each requested change to `mockup/index.html` (and `favicon.*` if the mark changes), commit, log the round in `design-approval.md`, and ask again, until the product owner approves. Commit the "Approved" entry with its date and the approved mockup commit. **GATE**: T015 and every later task that changes `app/static/css/app.css` or `app/templates/` start only after this commit. A later deviation from the approved look is a new log entry, approved again (US1-3).

**Checkpoint**: the look is approved and recorded; the rebuild may start.

---

## Phase 3: Foundational (Blocking Prerequisites)

**Purpose**: the meaning-based test harness, the tokens, the component library and the page frame.

**⚠️ CRITICAL**: no page task (Phase 4 onwards) starts until this phase is complete.

### 3a. Test harness (may run alongside Phase 2: it changes no look)

- [ ] T008 Create `tests/html.py`, a stdlib `html.parser` helper that queries pages by meaning (research D17). Whitespace in returned text is collapsed and stripped. Functions, each taking the response body as `str`:
  - `h1(body) -> str`: the text of the page's only `h1` (asserts there is exactly one);
  - `links(body, within=None) -> list[Link]`, with `Link(href, text, attrs)`; `within` is a tag name (`"header"`, `"main"`, `"footer"`, `"details"`, `"nav"`) limiting the search to that element;
  - `forms(body, within=None) -> list[Form]`, with `Form(method, action, buttons, inputs)`; `buttons` as `(name, value, text, attrs)`, `inputs` as `(name, type, value)`, where `inputs` also holds every `<select>` (type `"select"`) and `<textarea>` (type `"textarea"`) inside the form; `method` is lowercased and defaults to `"get"`;
  - `nav(body, label) -> list[Link]`: the links inside `<nav aria-label="{label}">`;
  - `region(body, tag) -> str`: the inner HTML of the first `header`, `main` or `footer`;
  - `badges(body) -> list[str]`: the texts of elements whose classes include `badge`;
  - `notices(body) -> list[tuple[str, str]]`: `(role, text)` for every element with `role="status"` or `role="alert"`;
  - `error_summary(body) -> Summary | None`, with `Summary(heading, items)` and items as `(href or None, text)`;
  - `field_error(body, field_id) -> str | None`: the text of the element with `id="{field_id}-error"`;
  - `table_rows(body) -> list[dict[str, str]]`: one dict per `<tbody>` row, keyed by each cell's `data-label`, falling back to the matching `<th>` text by column index (so it reads the current templates too);
  - `html_attrs(body) -> dict[str, str]` (the `<html>` element) and `meta(body, name) -> str | None`.

  A module docstring says why it exists (tests assert behaviour, not markup) and that it has no dependency.
- [ ] T009 [P] Rewrite the markup assertions of `tests/integration/test_home.py` with `tests/html.py`, against the **current** templates (plan "Changes to existing tests"): the title, role and logout from `region(body, "header")` instead of `<span class="site-title">`; the `h1` from `h1()` (still containing `APP_NAME`); the unavailable notice from `notices()`; the question list by its section. The footer release checks stay unchanged. Texts, statuses and addresses are still asserted exactly.
- [ ] T010 [P] Rewrite the markup assertions of `tests/integration/test_admin_area.py`, `test_admin_subjects.py`, `test_admin_institutions.py` and `test_access_control.py` against the current templates: tabs from `nav(body, "Administrator area")` instead of `<nav class="admin-tabs"`, row names from `table_rows()` instead of `td class=…`, links and forms from `links()` and `forms()`. Assertions on "Create", "Inactive" and `class="selected"` stay as they are now; they change in the US3 task that rebuilds the page.
- [ ] T011 [P] Rewrite the markup assertions of `tests/integration/test_admin_teachers.py`, `test_profile.py`, `test_teacher_students.py`, `test_teacher_classes.py` and `test_availability.py` against the current templates, as in T010. Assertions on `(deactivated)` and on `first-name-error`-style ids stay; they change with the page rebuild (US2, US3).
- [ ] T012 [P] Rewrite the markup assertions of `tests/integration/test_role_choice.py` and `test_role_switch.py`: find the role-switch form with `forms(body, within="header")` (it moves into the user menu, still inside the header), and its buttons by `name="role"` and value. The role-choice sentence assertion stays until T037.
- [ ] T013 [P] Rewrite the markup assertions of `tests/integration/test_login_flow.py`, `test_data_deletion.py`, `test_invitation_cutoff.py`, `test_invitation_edge_cases.py`, `test_invitation_refusals.py`, `test_student_invitation.py`, `test_student_invitation_refusals.py`, `test_teacher_invitation.py` and `test_names_on_acceptance.py`: messages are found by their text in `region(body, "main")` (they move from `auth-message` to the error summary, a field error or a notice), never by class. Texts and status codes stay exact.
- [ ] T092 [P] Create the form contract (FR-040, SC-011, research D17), against the **current** templates, so it proves every form keeps its field names through the rebuild:
  - `tests/integration/test_form_contract.py` with a table of named cases, one per state that shows a form, each giving the client (anonymous, `admin_client`, `client_as(...)` with the cast helpers) and the request that produces the page. The cases cover every template with a form in [pages.md §1](./contracts/pages.md#1-page-inventory), including the states reached only by `POST`: sign-in step one and step two, a step-one error, role choice for a person with several roles, withdraw consent, a teacher and a student invitation, the data-deletion request and confirmation; every administrator page with a form (the subjects list with an active and a deactivated subject, subject new/rename/delete in use and not in use, the region and institution forms, deactivate and delete pages, teacher invite/edit/remove); every teacher page with a form (the Students tab with region, institution and class selected, class new/edit/deactivate/delete, student invite/edit/remove); and the frame forms (role switch, **Log out**) on `/` for a person with several roles;
  - for each case, the page's forms from `forms()` as records of `method`, `action` (empty means the request path; numeric path segments become `{id}` and invitation and deletion tokens `{token}`, so the record does not depend on database ids), the sorted, de-duplicated field names of its inputs, selects, textareas and named buttons, and the sorted `(name, value)` pairs of its named buttons (for example `role=teacher`). The records of a case are compared as a sorted list, so moving a form on the page (the role switch into the user menu) is not a change;
  - forms whose action is `/theme` are left out (they arrive with US5);
  - the expected records live in `tests/integration/form_contract.json`, keyed by case name. Running the module with `UPDATE_FORM_CONTRACT=1` rewrites the file; it is generated **once** here, from the current templates, reviewed and committed, and never regenerated in this milestone. A mismatch fails with the case name and the differing records;
  - a module docstring says why it exists: the milestone 1–9 tests post to the server by field name and never read the names from the page, so only this test catches a renamed or lost field in a template.
- [ ] T014 Run the whole suite on both engines: it must be green with the T001 count plus T092's cases, proving the rewrites kept every assertion's meaning and the form contract matches the current templates before any page changes (plan step 2). Depends on T008–T013 and T092.

### 3b. Tokens, components and frame (after T007)

- [ ] T015 Restructure `app/static/css/app.css` into marked sections, in this order (research D2, D3, D4; data-model §2):
  1. `/* == Tokens == */` … `/* == End of tokens == */`: the four `@font-face` rules (`font-family: "Open Sans"`, `src: url("/static/fonts/open-sans-<subset>.woff2") format("woff2")`, `font-weight: 300 800`, `font-display: swap`, the subset's `unicode-range`); then every `--sc-*` token with the exact light values of data-model §2.1–§2.4 on `:root`; the dark values under `[data-theme="dark"]` and under `:root:not([data-theme="light"])` inside `@media (prefers-color-scheme: dark)`; `--sc-text-body: 1.125rem` inside `@media (min-width: 1024px)`, and `--sc-text-h1: 2rem`, `--sc-text-h2: 1.5rem` inside `@media (min-width: 768px)`. Copy the values from the approved mockup (T007);
  2. `/* == Pico mapping == */`: every pair of data-model §2.5, written with the same selectors Pico uses for its own variables (read them from `pico.min.css`) so the mapping wins by order, and `--pico-font-size: 100%` repeated inside each of Pico's own breakpoint media queries;
  3. `/* == Base == */`: `body` background, colour, font and `font-size: var(--sc-text-body)`; `h1`–`h4` sizes, weights and line height from the tokens; `max-width: var(--sc-measure)` for running text (`p`, `li` inside `main`); `text-align: left`; emphasis as bold only (FR-004): `em, i { font-style: normal; font-weight: var(--sc-weight-bold) }`, and `strong, b` at `--sc-weight-bold`; a `.visually-hidden` utility;
  4. `/* == Layout == */`: `.container` capped at `--sc-content-width`, `.skip-link`, `.top-bar`, `.brand`, `.brand-name`, `.brand-role`, `.user-menu` (folded below 768 px: email hidden, icon and "Account menu" shown), `.area-tabs` (current tab underlined in `--sc-primary`, wrapping on a phone), `.site-footer` (muted, `--sc-text-small`);
  5. `/* == Components == */`: left empty here, filled by T027;
  6. `/* == Legacy page styles == */`: the current rules, moved unchanged. Each page task deletes the legacy rules its page no longer uses; T060 deletes the section.
- [ ] T016 [P] Create `app/templates/components/icons.html` per contracts/components.md §11: `logo_mark(size="md")` emitting `<svg class="logo-mark logo-mark-{size}" viewBox="0 0 32 32" aria-hidden="true" focusable="false">` with the approved mark, its fills from classes (no inline style); `icon(name)` for `"account"` and `"arrow-left"`, emitting `<svg class="icon" aria-hidden="true" focusable="false">`. Build the size class with `{% set logo_class = … %}` from literal strings (research D16).
- [ ] T017 [P] Create `app/templates/components/frame.html` per contracts/components.md §1, with `top_bar()`, `user_menu()`, `area_tabs(tabs, active, label)`, `back_link(href, text)` and `page_heading(title, action=None)`. `user_menu()` holds, in order: the email linking to `/profile`; the role switch of §1.1, unchanged (`<form method="post" action="/role">`, "Switch to", one `<button type="submit" name="role" value="{role.value}" class="secondary">{role.label}</button>` per other role, only when `current_role and user_roles | length > 1`, exactly the condition of today's `base.html`, so the switch never shows on the role-choice page before a role is chosen); then the logout form. The theme switch is added between them by T073. `<summary>` holds `icon("account")`, `<span class="user-menu-email">{email}</span>` and `<span class="visually-hidden">Account menu</span>`.
- [ ] T018 [P] Create `app/templates/components/button.html` per contracts/components.md §2: `button`, `link_button` (with `role="button"`), `post_button` (`<form method="post" action=… class="inline-form">` with the `hidden` mapping as hidden inputs). Kind to class: `primary` none, `secondary` → `secondary`, `destructive` → `destructive`; `outline` and `small` add those classes. An unknown kind is a template error.
- [ ] T019 [P] Create `app/templates/components/card.html` per contracts/components.md §3: `card(title, href=None, description=None)` with the optional `caller()` body; with `href`, `<h3><a href="{href}" class="card-link">{title}</a></h3>`; then `<p class="card-description">`.
- [ ] T020 [P] Create `app/templates/components/table.html` per contracts/components.md §4: `data_table(columns, caption=None)`, `cell(label, value=None)` emitting `<td data-label="{label}">`, and `actions_cell()` emitting `<td class="row-actions" data-label="">`.
- [ ] T021 [P] Create `app/templates/components/badge.html` per contracts/components.md §5: `badge(text, kind="neutral")` (kinds `success`, `muted`, `neutral`, `info`), `status_badge(is_active)` → **Active** (`success`) / **Deactivated** (`muted`), `access_badge(level)` → **Read** (`neutral`) / **Write** (`info`) from `AccessLevel`. An empty `text` is a template error: register a `template_error(message)` global in `app/core/templates.py` that raises `jinja2.TemplateRuntimeError`, and call it from the macro.
- [ ] T022 [P] Create `app/templates/components/feedback.html` per contracts/components.md §6: `notice(text, kind="info")` with `role="alert"` for `error` and `role="status"` otherwise; `empty_state(message, hint=None)` with `.empty-state-message` and `.empty-state-hint`.
- [ ] T023 [P] Create `app/templates/components/form.html` per contracts/components.md §7: `error_summary(errors, form_error=None, order=None)` (renders nothing without errors; heading exactly "There is a problem"; one `<li><a href="#{field_id}">` per field error in `order`; `form_error` as an `<li>` without a link), `field`, `select_field`, `checkbox_field` (ids `{id}-hint` and `{id}-error`, `aria-invalid="true"` with an error, `aria-describedby` listing hint and error) and `form_actions(submit_label, cancel_href=None, kind="primary")` (button first, then the **Cancel** link).
- [ ] T024 [P] Create `app/templates/components/confirmation.html` per contracts/components.md §8: `confirmation(question, consequence, action, verb, cancel_href, hidden={})` (consequence also via `caller()`), and `refusal(question, reason, back_href, back_text)` with `notice(reason, "info")` and the alternative action via `caller()`. Imports `post_button` and `notice`.
- [ ] T025 [P] Create `app/templates/components/details.html` per contracts/components.md §9: `details_list(items)` emitting `<dl class="details-list">`, skipping a `None` value, rich values through `caller(label)`.
- [ ] T026 [P] Create `app/templates/components/selectors.html` per contracts/components.md §10: `list_detail(list_label, items, selected_id, item_href)` (selected item `aria-current="true"` and `class="selected"`, `status_badge(False)` on a deactivated item, the detail panel via `caller()`), and `chained_lists(levels, action)` (one `<form method="get" action="{action}">` per level with its hidden carry inputs and `select_field(…, attrs={"data-auto-submit": True})`, honouring `disabled`, `placeholder` and `extra_options`).
- [ ] T027 Fill the `/* == Components == */` section of `app/static/css/app.css` for every class T016–T026 emit, ported from the approved mockup, tokens only: `.logo-mark*`, `.icon`, `.page-heading`, `.back-link`, `.destructive` (and its hover, `outline` variant), `.small` (still at least `--sc-touch-target` high), `.inline-form`, `.card`, `.card-link` (hit area over the whole card), `.card-description`, `.data-table` (long values wrap; below 768 px each row a card of labelled values from `td::before { content: attr(data-label) }`, `.row-actions` last and together), `.badge` and `.badge-{success,muted,neutral,info}`, `.notice` and `.notice-{success,error,info}`, `.empty-state*`, `.error-summary`, `.field-hint`, `.field-error`, `.form-actions`, `.confirmation`, `.confirmation-refused`, `.details-list` (two columns from 768 px), `.selectors`, `.selectors-list-detail`, `.selectors-chained`, `.select-list`, `.selected`. Depends on T016–T026.
- [ ] T028 Rebuild `app/templates/layouts/base.html` per contracts/components.md §1.2 and http-routes §3: keep `lang="en"`, the charset, viewport, `<meta name="description">` and `{% block title %}`; add `<meta name="color-scheme" content="light dark">` (made theme-aware by T072), `<link rel="preload" href="/static/fonts/open-sans-latin.woff2" as="font" type="font/woff2" crossorigin>`, the favicon links (`/static/img/favicon.svg` as `image/svg+xml`, `favicon-32.png`, `apple-touch-icon.png`), then `pico.min.css`, `app.css` and `{% block scripts %}`. The body renders the skip link (`href="#main"`, "Skip to main content"), `top_bar()`, `{% block tabs %}{% endblock %}`, `<main id="main" class="container">{% block content %}{% endblock %}</main>` and `<footer class="site-footer container">` with the current release text and `title="{{ commit_sha }}"` unchanged, then `{% block footer_extra %}{% endblock %}`. Delete the legacy `site-*` and `release*` rules from `app.css`. Depends on T017, T027.
- [ ] T029 Rebuild `app/templates/layouts/admin.html` and `app/templates/layouts/teacher.html`: fill `{% block tabs %}` with `area_tabs(admin_tabs, active_tab, "Administrator area")` and `area_tabs(teacher_tabs, active_tab, "Teacher area")`; keep `{% block admin_content %}` and `{% block teacher_content %}` inside `content`. The router context is unchanged. Delete the `admin-tabs` and `area-tabs` rules in the `/* == Legacy page styles == */` section only: the new `.area-tabs` rules in the Layout section (T015) stay, because the component uses that class. Depends on T017, T028.
- [ ] T030 Create `tests/unit/test_stylesheet.py` per research D16, no new dependency:
  - collect the classes used in `app/templates/**/*.html` (each `class="…"` with `{{ … }}` and `{% … %}` stripped, plus the string literals of `{% set …_class(es) = … %}` in `components/`), the classes defined in `pico.min.css` and in `app.css` (selector regex);
  - `test_every_used_class_is_defined`, `test_every_app_css_class_is_used`, `test_no_inline_style` (no ` style=` in any template), `test_nothing_loads_from_another_site` (no `src=`, `href=` or `action=` starting with `http:`, `https:` or `//`; no `@import` and no `url(` outside `/static/` in `app.css`), `test_readable_text_tokens` (`--sc-text-body` ≥ `1rem`, `1.125rem` inside the `1024px` query, `--sc-line-height` ≥ 1.5), `test_tokens_are_defined_once` (each `--sc-*` light value appears once on `:root`), `test_emphasis_is_bold_and_text_left_aligned` (FR-004: no `<i>` or `<u>` element in any template; in `app.css` no `font-style: italic`, no `text-transform: uppercase` or `capitalize`, no `text-align: justify`, and the Base section's `em, i` rule sets `font-style: normal`);
  - `test_no_page_specific_classes_remain` with the denylist of research D8 (`subjects-table`, `teachers-table`, `institutions-table`, `students-table`, `subjects-empty`, `subjects-actions`, `list-empty`, `questions-empty`, `class-picker`, `class-bar`, `institutions-layout`, `regions-list`, `picker-table`, `auth-message`, `hero`, `admin-tabs`, every `site-*` class, plus any other page-only class found in the current `app.css`), and `test_only_tokens_hold_literal_values` (no hex colour, `rgb(`, or `px` length outside the token block, except the `768px` / `1024px` queries). Mark these two `@pytest.mark.xfail(strict=True, reason="legacy section removed in T060")`.
- [ ] T031 Run the whole suite on both engines and `uv run ruff check .`: green, with the frame on every page. Open `/`, `/login` and `/admin/subjects` locally once to confirm the frame renders. Depends on T014–T030.

**Checkpoint**: the tokens, every component and the frame exist; pages can now be rebuilt.

---

## Phase 4: User Story 2 — A young student uses the application on a phone (Priority: P1) 🎯 MVP

**Goal**: sign-in, code entry, role choice, home, profile and withdrawal rebuilt; the user menu works
without JavaScript; every lower page has a back link.

**Independent Test**: as a student at 375 px: body text ≥ 16 px with line height ≥ 1.5, no sideways
scroll, the user menu opens without JavaScript, home shows one card per allowed area, and the profile
has a back link to `/` (quickstart §3.1).

### Tests for User Story 2

- [ ] T032 [P] [US2] Create `tests/integration/test_layout.py` with the user-menu tests (FR-019, US2-2, US2-3): signed in, the header holds a `<details class="user-menu">` with a `<summary>`, and inside it, in order, a link to `/profile` with the email, the role switch only for a person with several roles (form `POST /role`, buttons `name="role"` with the other roles' values), and the `POST /logout` form with **Log out**; a person with one role has no role-switch form; a person with several roles who has not chosen one yet (`GET /role`) has no role-switch form either (today's `current_role` condition); signed out there is no user menu. Use `links(…, within="details")` and `forms(…, within="details")`.
- [ ] T033 [P] [US2] Create `tests/integration/test_page_patterns.py` with the US2 cases (FR-003, FR-031, SC-006, SC-007): an invalid email on `POST /login` shows the summary "There is a problem" with one link `#email`, the same message from `field_error(body, "email")` and the email kept; a wrong code on step two links `#code`; a rate-limit refusal (patch as the existing login tests do) appears in the summary as text without a link and beside no field; `POST /role` with an invalid role shows "Choose one of your roles." as summary text; `GET /profile` has a back link to `/` "Back to the home page" first in `main`; `GET /profile/withdraw` has a back link to `/profile`, a question, a consequence, a destructive button **Withdraw consent** and **Cancel**. Write a reusable `assert_form_errors(body, errors, form_error, values)` and `assert_confirmation(body, question, verb, cancel_href)` for US3 and US4.

### Implementation for User Story 2

- [ ] T034 [US2] Change `_page` in `app/routers/auth.py` to the shared form shape (data-model §4.2, pages.md §3): replace `message` with `errors: dict[str, str]` and `form_error: str | None`, and pass `values={"email": email}` (step one) or keep `email` for step two's hidden field. Map each call: `INVALID_EMAIL` → `errors={"email": …}`; `INVALID_CODE` → `errors={"code": …}`; `TOO_MANY` and `UNAVAILABLE` → `form_error` (including the logout 503 path). `notice` (ACCOUNT_READY), every message text and every status code are unchanged.
- [ ] T035 [US2] Rebuild `app/templates/pages/login.html` (pages.md §1.1): `page_heading`; `notice(notice, "info")` when set; `error_summary(errors, form_error, order=["email"])`; `field("email", …)` keeping `name="email"`, `type="email"`, its current attributes (`autocomplete`, `required`, `autofocus`) and the value; the hidden `next` field unchanged; `form_actions("Send code")`; the "Delete my data" link unchanged. Delete the legacy rules it no longer uses (`auth-message`, …).
- [ ] T036 [US2] Rebuild `app/templates/pages/login_code.html`: `page_heading`; the "code sent" info notice; `error_summary(errors, form_error, order=["code"])`; `field("code", …)` keeping `name`, `inputmode`, `pattern`, `autocomplete`; the hidden fields unchanged; `form_actions("Sign in")`; `post_button(…, "Send a new code", kind="secondary")` with its current action and hidden fields; the "Use a different email" link. Update the assertions in `tests/integration/test_login_flow.py` only where they pinned markup.
- [ ] T037 [US2] Rebuild `app/templates/pages/role_choice.html`: `page_heading`; `error_summary({}, form_error=message)` (the router key `message` stays); one `button(role.label, kind="secondary", name="role", value=role.value)` per role in the existing `POST /role` form (secondary, because the choices are equal and FR-025 allows at most one primary per page; the page has no primary button); the sentence changed to "You can switch at any time from the menu at the top of the page." (pages.md §4.1). Update that assertion in `tests/integration/test_role_choice.py`.
- [ ] T038 [US2] Add `description: str` to `Area` in `app/routers/areas.py` with the four texts of data-model §4.1 verbatim ("Manage teachers, educational institutions and subjects.", "Manage your classes and invite your students.", "Take part in competitions and see your results.", "Pages shared by administrators and teachers."). Paths, titles and roles are unchanged; update the class docstring.
- [ ] T039 [US2] Rebuild `app/templates/pages/home.html` per research D14 and pages.md §1.1: `h1` "Welcome to Student Competitions" (built from `app_name`), then the tagline; drop the `app_description` paragraph from the body (it stays the `<meta name="description">`); the "Your areas" section (`id="areas"`, `h2 id="areas-heading"`) with one `card(area.title, href=area.path, description=area.description)` per area; the sample questions section unchanged in content and order, with `empty_state("No questions yet.")`; `notice("Question data is temporarily unavailable. Please try again in a moment.", "info")` when data is unavailable; move the database line into `{% block footer_extra %}` (only when data is available), keeping its text, its `<code>` and its `data-engine`, `data-revision` and `data-boots` attributes, without the `db-status` class. Delete the legacy `hero`, `tagline`, `question-list`, `questions-empty`, `db-status`, `data-unavailable` rules. Update `tests/integration/test_home.py` for the greeting `h1` and the footer location, per pages.md §4.1.
- [ ] T040 [US2] Rebuild `app/templates/pages/profile.html`: `back_link("/", "Back to the home page")`; `page_heading`; `details_list` for the label and value pairs; `status_badge(False)` in place of every "(deactivated)" small text; each consent record as a `card`; `link_button("Withdraw consent", "/profile/withdraw", kind="destructive")`. Update the `(deactivated)` assertions in `tests/integration/test_profile.py` to `badges()` containing "Deactivated" (pages.md §4.1). Delete the legacy profile rules.
- [ ] T041 [US2] Rebuild `app/templates/pages/profile_withdraw.html`: `back_link("/profile", "Back to your profile")`; `error_summary({}, form_error=…)` from the key the profile router passes today for "There is no data stored on your consent to withdraw."; `confirmation(…, verb="Withdraw consent", cancel_href="/profile")` with the current question and consequence texts and the current `POST` action.

**Checkpoint**: the student journey is complete on the new system; T032 and T033 pass; the suite is
green.

---

## Phase 5: User Story 3 — Staff work with lists and forms on a desktop (Priority: P1)

**Goal**: every administrator and teacher page rebuilt from tables, badges, forms, error summaries
and confirmations.

**Independent Test**: in both areas, submit each form invalid and open each destructive action;
check the summary, field errors, kept values, confirmation wording and button kinds
(quickstart §3.2, §3.3).

### Tests for User Story 3

- [ ] T042 [P] [US3] Extend `tests/integration/test_page_patterns.py` with the administrator and teacher cases (US3-1 to US3-7), using T033's helpers:
  - **Forms** (pages.md §3): subject (duplicate name → `#name`), region, institution, invite teacher (`email`, `first_name`, `last_name`, `picker`, and its `form_error`), edit teacher, class (`name`, `year_of_study`), invite student (fields and `form_error`), edit student (`first_name`, `last_name`, `class_id`): the summary, one link per field error, the message beside the field, the values kept;
  - **Confirmations** (components.md §8): `subject_delete`, `region_delete`, `region_deactivate`, `institution_delete`, `institution_deactivate`, `teacher_remove`, `class_delete`, `class_deactivate`, `student_remove`: the question names the item ("Delete “Physics”?"), a consequence, a destructive button repeating the verb, then **Cancel**; the refusal variants for an in-use subject, region and institution offer **Deactivate**;
  - **Back links**: every page of pages.md §1.2–§1.3 with a back link has it first in `main`, with the listed target and text;
  - **Badges**: Active/Deactivated and Read/Write are `badges()` texts; **Lists**: each list page has one `h1` and at most one primary action; empty lists show the empty message and its hint instead of a table;
  - **Link buttons**: links to a form or a confirmation carry `role="button"`.

### Implementation for User Story 3

- [ ] T043 [US3] Change `_form` in `app/routers/admin_subjects.py` to the shared shape: `values={"name": value}`, `errors={"name": error}` when there is an error, else `{}`. Messages, conditions and status codes (400) are unchanged; update the docstring.
- [ ] T044 [US3] Change the region form and the institution form contexts in `app/routers/admin_institutions.py` (the `_form` near line 145 and the institution form near line 314) the same way: `values={"name": …}`, `errors={"name": …}`; `cancel` and every other key stay.
- [ ] T045 [US3] Rebuild `app/templates/pages/admin/subjects.html`: `page_heading("Subjects", ("Create subject", "/admin/subjects/new"))`; the "Invitation sent"-style notices as `notice(…, "success")` where the page shows one; `data_table(["Name", "Status", "Actions"])` with `cell`, `status_badge(subject.is_active)` (the word "Inactive" becomes "Deactivated") and `actions_cell()` holding each current action with `small=True` (rename as a secondary `link_button`, delete as a destructive `link_button` to its confirmation page, **Deactivate** as a destructive `post_button` to the existing direct `POST /admin/subjects/{id}/deactivate` (no confirmation page, spec FR-032a), **Activate** as a secondary `post_button`); `empty_state("No subjects yet", "Create the first subject with Create subject.")`. Update the "Create" and "Inactive" assertions in `tests/integration/test_admin_subjects.py`. Delete the legacy `subjects-*` rules.
- [ ] T046 [US3] Rebuild `app/templates/pages/admin/subject_form.html` (`back_link("/admin/subjects", "Back to the subjects")`, `page_heading(heading)`, `error_summary(errors, order=["name"])`, `field("name", …)` with its current attributes, `form_actions("Save", cancel_href="/admin/subjects")`), `subject_delete.html` (`confirmation` with verb **Delete**, or `refusal` with the **Deactivate** `post_button` exactly as the page has it today) and `subject_not_found.html` (`back_link`, `page_heading`), all in `app/templates/pages/admin/`.
- [ ] T047 [US3] Rebuild `app/templates/pages/admin/institutions.html`: `page_heading`; `list_detail("Regions", regions, selected_id, …)` with **Create region** and the region row actions on the left; on the right, the selected region's data table of institutions with **Create educational institution**, `status_badge`, row actions, and the empty states ("No regions yet", "No educational institutions yet", "Select a region") with their hints from pages.md §4.3. Update the "Create" and `class="selected"` assertions in `tests/integration/test_admin_institutions.py` (`aria-current="true"`). Delete the legacy `institutions-*`, `regions-list` rules.
- [ ] T048 [US3] Rebuild `app/templates/pages/admin/region_form.html`, `region_deactivate.html` and `region_delete.html` per pages.md §1.2: the back links ("Back to “{region}”", or "Back to the educational institutions" when no region is selected), `error_summary` + `field("name")` + `form_actions("Save", cancel_href=cancel)`, `confirmation` (verbs **Deactivate**, **Delete**) and `refusal` with the **Deactivate** alternative.
- [ ] T049 [US3] Rebuild `app/templates/pages/admin/institution_form.html` (with the deactivated-region refusal as an info `notice`), `institution_deactivate.html`, `institution_delete.html` (the "classes will be deleted too" consequence via `caller()`, or `refusal` with **Deactivate**) and `institutions_not_found.html` per pages.md §1.2.
- [ ] T050 [US3] Rebuild the partials `app/templates/pages/admin/_person_names.html` (`field("first_name", …)`, `field("last_name", …)`, error ids now `first_name-error` / `last_name-error`) and `app/templates/pages/admin/_institution_picker.html` (keep its `<fieldset id="picker">` and every field name; rows from `data_table` and `checkbox_field`; its error as the field error for `picker`, linked from the summary as `#picker`). Update the field-error id assertions in `tests/integration/test_admin_teachers.py` and `test_teacher_students.py`. Delete the legacy `picker-table` rules.
- [ ] T051 [US3] Rebuild `app/templates/pages/admin/teachers.html` (`page_heading` with **Invite teacher**, the "Invitation sent…" success notice, data table of name, email, institutions with `access_badge`, status badge, row actions, the empty state "No teachers yet" with its hint if the page has one), `teacher_invite.html` and `teacher_form.html` (`error_summary(errors, form_error, order=[…])`, the partials, the checkbox, `form_actions`, and **Remove** as a destructive `link_button` on the edit form), `teacher_remove.html` (`confirmation` verb **Remove**, back link "Back to {name}") and `teacher_not_found.html`. Replace "(deactivated)" with `status_badge(False)`. Update the matching assertions in `tests/integration/test_admin_teachers.py`. Delete the legacy `teachers-*` rules.
- [ ] T052 [US3] Rebuild `app/templates/pages/admin/placeholder.html`: `page_heading` and `empty_state` with the current "… will arrive in a later milestone." text and no hint.
- [ ] T053 [US3] Rebuild `app/templates/pages/teacher/students.html` per pages.md §1.3 and components.md §10: keep `{% block scripts %}` with `auto-submit.js`; `page_heading`; the "Invitation sent…" success notice; `chained_lists(levels, "/teacher/students")` with the existing `region`, `institution` and `class` ids, names, placeholders, `disabled` conditions, carried hidden values and the "+ Add class" option; the selected class's heading with `status_badge`; its row actions (**Edit** secondary, **Deactivate** destructive link to its confirmation, **Activate** as it is today, **Delete** destructive link); **Add student** as the primary `link_button`; the students' `data_table` with Read/Write `access_badge`s where shown; every empty message with a one-line hint, each added to pages.md §4.3. Update the assertions in `tests/integration/test_teacher_students.py` and `test_teacher_classes.py` that pinned markup. Delete the legacy `class-picker`, `class-bar`, `students-table` rules.
- [ ] T054 [US3] Rebuild `app/templates/pages/teacher/class_form.html` (`error_summary(errors, order=["name", "year_of_study"])`, both fields, `form_actions("Save", cancel_href=cancel)`, back link "Back to “{class}”" when editing, "Back to Students" when creating), `class_deactivate.html` (verb **Deactivate**) and `class_delete.html` (verb **Delete**, or `refusal`).
- [ ] T055 [US3] Rebuild `app/templates/pages/teacher/student_invite.html` (fields, `form_error`, the deactivated-class refusal as an info `notice`, **Send invitation**), `student_form.html` (name fields, `select_field("class_id", …)`, **Save**, **Remove** as a destructive `link_button`), `student_remove.html` (verb **Remove**) and `teacher/placeholder.html` (empty state), each with its pages.md §1.3 back link.

**Checkpoint**: every administrator and teacher page is on the new system; T042 passes; the suite is
green.

---

## Phase 6: User Story 4 — Every existing page keeps its behaviour (Priority: P1)

**Goal**: the remaining public pages rebuilt, every page-specific class gone, and the behaviour
proven unchanged.

**Independent Test**: the full milestone 1–9 suite passes; only markup assertions changed; every
changed message is listed with its rule; `test_stylesheet.py` passes with no `xfail`.

### Tests for User Story 4

- [ ] T056 [P] [US4] Extend `tests/integration/test_page_patterns.py` with the remaining pages: invitation acceptance (name fields as field errors; the changed-consent message as summary text without a link, from today's `notice`), the data-deletion request (`#email`), `data_deletion_confirm` (a confirmation with the verb **Delete my data**, a details list and **Cancel** to `/`), and the back links of `data_deletion_request` and `data_deletion_requested` to `/login` ("Back to sign in").

### Implementation for User Story 4

- [ ] T057 [US4] Rebuild `app/templates/pages/invitation.html` (`page_heading`; `details_list`; the consent text in a `card`; `error_summary(errors, form_error=notice)`, mapping today's `notice` key in the template; the name fields via `_person_names.html`; `form_actions("I agree")`) and `invitation_status.html` (`page_heading`; `notice(message, "info" or "error")` as the state requires, the link unchanged).
- [ ] T058 [US4] Rebuild `app/templates/pages/data_deletion_request.html` (`back_link("/login", "Back to sign in")`, `error_summary({"email": message} if message else {}, order=["email"])` mapped in the template, `field("email", …)`, `form_actions("Send link")`), `data_deletion_requested.html` (back link, success notice) and `data_deletion_confirm.html` (`confirmation` verb **Delete my data**, `cancel_href="/"`, the consequence as a `details_list` of what will be deleted via `caller()`). The page has no **Cancel** today; the new link goes to `/`, which shows the home page to a signed-in person and sends a signed-out visitor to sign in by the existing rule, so it needs no condition in the template. The new link is listed in pages.md §4.2.
- [ ] T059 [US4] Rebuild `app/templates/pages/link_status.html` (error notice), `data_erased.html` (success notice), `error.html` (`page_heading`, the paragraph and the "Back to the home page" link unchanged; every status code and text unchanged) and `area.html` (`page_heading`, `empty_state("The features of this area will arrive in a later milestone.")`).
- [ ] T060 [US4] Clean up `app/static/css/app.css` (FR-041, US4-4): delete the `/* == Legacy page styles == */` section and any rule left in it; search `app/templates/` for every denylisted class and remove what remains; remove both `xfail` markers from `tests/unit/test_stylesheet.py`. `uv run pytest tests/unit/test_stylesheet.py` passes in full. Depends on T035–T059.
- [ ] T061 [US4] Audit that behaviour is unchanged (FR-040, SC-011), recording the results in the PR description draft:
  - **Routes**: the sorted `(methods, path)` list of `app.main.app.routes` on `main` and on this branch differs only by `POST /theme` and `GET /admin/components` (run after US5 and US7 are merged into the branch, or re-run then);
  - **Fields**: `tests/integration/test_form_contract.py` (T092) is green and `git diff main -- tests/integration/form_contract.json` shows only the file being added, never a changed record: every form on every page keeps its method, action and field names;
  - **Tests**: `git diff main -- tests/integration tests/unit` shows only markup-query rewrites, the wording changes of pages.md §4 and new tests; no behaviour or access assertion removed or loosened (SC-002).
- [ ] T062 [US4] Complete [contracts/pages.md §4](./contracts/pages.md#4-wording-changes-fr-040): every text change made in Phases 4–6 is listed with its rule, including every Students-tab hint added by T053 in §4.3.

**Checkpoint**: every page is on the new system with its behaviour intact (US2–US4 together are the
shippable rebuild).

---

## Phase 7: User Story 5 — A person chooses a light or a dark theme (Priority: P2)

**Goal**: the **Light** / **Dark** / **Device** switch in the user menu and on the sign-in page, kept
in a cookie and rendered by the server.

**Independent Test**: choose each value from the user menu and from `/login`; each following page,
the sign-in page included, carries the matching `data-theme` and `color-scheme` from the server; a
missing or unknown cookie follows the device (quickstart §3.4).

### Tests for User Story 5

- [ ] T063 [P] [US5] Create `tests/unit/test_theme.py`: `parse_theme` gives `LIGHT` for `"light"`, `DARK` for `"dark"`, and `DEVICE` for `"device"`, `None`, `""`, `"purple"` and `"Dark"` (exact lowercase only); `read_theme` reads `sc_theme` from a request's cookies with the same rule and never raises; `apply_theme(response, LIGHT|DARK, secure=…)` sets `sc_theme` with `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, `HttpOnly`, and `Secure` only when `secure=True`; `apply_theme(response, DEVICE, …)` deletes it with the same path and flags.
- [ ] T064 [P] [US5] Extend `tests/unit/test_safe_next.py` with `safe_return_path` cases (research D6): allowed `/login`, `/login?next=%2Fprofile`, `/role`, `/admin/subjects?x=1`; refused (returns `None`) empty, `None`, over 2,048 characters, `admin`, `//evil.example`, `https://evil.example/`, `/\evil`, a path with a space or a control character, `/login/code`, `/logout`, `/theme`.
- [ ] T065 [P] [US5] Create `tests/integration/test_theme.py` covering every row of [contracts/http-routes.md §1](./contracts/http-routes.md#1-post-theme-choose-the-theme) and §3:
  - `POST /theme` answers 303 to `next` and sets, or deletes, `sc_theme`; unknown values delete it; unsafe, `/login/code`, `/logout` and `POST`-only targets (`/admin/subjects/7/deactivate`) fall back to `/` signed in and `/login` signed out; the database is not touched;
  - a cross-site `POST /theme` gets the 403 "Request refused" page and no `Set-Cookie`;
  - with `sc_theme=dark` or `light`, `/login`, a signed-in page and the 404 page render `<html data-theme=…>` and the matching `<meta name="color-scheme">`; with no, empty or unknown cookie there is no `data-theme` and `color-scheme` is `light dark`;
  - the switch is on `/login` with `next` equal to `/login` plus its query, and inside the user menu between the role switch and **Log out**, with `aria-pressed="true"` on the current choice only; it is absent from the invitation, data-deletion and 404 pages;
  - a page shown after a failed `POST` (the subject form with a duplicate name) carries `next` with the path only;
  - signing in, switching role and logging out neither read nor change `sc_theme` (US5-4).
- [ ] T066 [P] [US5] Update `tests/integration/test_routes.py` (`test_the_allowlist_is_exact` and `test_the_write_routes_are_exact` each gain `("POST", "/theme")`) and add a `POST /theme` case to `tests/integration/test_cross_site.py`.

### Implementation for User Story 5

- [ ] T067 [US5] Create `app/core/theme.py` per data-model §1: `class Theme(StrEnum)` with `LIGHT = "light"`, `DARK = "dark"`, `DEVICE = "device"`; `THEME_COOKIE_NAME = "sc_theme"`; `THEME_COOKIE_MAX_AGE = 31_536_000`; `parse_theme(value: str | None) -> Theme`; `read_theme(request) -> Theme` (never raises); `apply_theme(response, theme, *, secure: bool) -> None` (sets for Light/Dark, deletes for Device, `path="/"`, `samesite="lax"`, `httponly=True`, `secure=secure`). The docstring says the cookie holds only the choice, is not personal data, is never logged, and needs no consent.
- [ ] T068 [US5] Add `safe_return_path(value: str | None) -> str | None` to `app/core/security.py` (research D6): the `safe_next_path` rules (shared, not copied: factor the common checks into one private helper), but `/login` and `/role` are allowed, and `/login/code`, `/logout` and `/theme` are refused; `None` when refused. `safe_next_path` keeps its exact behaviour (its existing tests stay green).
- [ ] T069 [US5] Create `app/routers/theme.py` with `POST /theme` per contracts/http-routes.md §1: `theme: str = Form("")`, `next: str = Form("")`; `target = safe_return_path(next)`; refuse a target whose path (without query) matches no `GET` `APIRoute` in `request.app.routes` (test with each route's `path_regex`); fallback `/` when `request.state.user` is set, else `/login`; `RedirectResponse(target, status_code=303)`; `apply_theme(response, parse_theme(theme), secure=<the auth settings' production flag>)`. No session dependency. Module docstring per research D6.
- [ ] T070 [US5] Add `("POST", "/theme")` to `PUBLIC_ROUTES` in `app/core/auth.py` (with a comment: it reads and writes no data and acts only on the requesting browser) and include `theme.router` in `app/main.py` (import in the `app.routers` list, `app.include_router(theme.router)`).
- [ ] T071 [US5] Add a `_theme(request)` context processor to `app/core/templates.py` returning `theme` (`read_theme(request).value`) and `theme_return` (path plus `?query` for `GET`/`HEAD`, path only otherwise), registered beside `_current_user`; extend the module docstring.
- [ ] T072 [US5] Make `app/templates/layouts/base.html` theme-aware per http-routes §3: `<html lang="en"{% if theme != "device" %} data-theme="{{ theme }}"{% endif %}>` and `<meta name="color-scheme" content="{{ 'light dark' if theme == 'device' else theme }}">`.
- [ ] T073 [US5] Add `theme_switch(current, return_to)` to `app/templates/components/frame.html` per contracts/components.md §1 (`<form method="post" action="/theme" class="theme-switch">`, `<fieldset>` with legend "Theme", hidden `next`, three `secondary` buttons `name="theme"` **Light** / **Dark** / **Device** with `aria-pressed`; never primary, FR-025), call it in `user_menu()` between the role switch and **Log out** with `theme` and `theme_return`, and add the `.theme-switch` styles to the Components section of `app/static/css/app.css` (tokens only; the pressed button, selected by `.theme-switch [aria-pressed="true"]`, gets the primary tint, a primary border and bold text, so it is not marked by colour alone).
- [ ] T074 [US5] Add `theme_switch(theme, theme_return)` to `app/templates/pages/login.html`, below the sign-in form (FR-014). No other public page gets it.

**Checkpoint**: both themes are selectable everywhere they should be; T063–T066 pass.

---

## Phase 8: User Story 6 — A visitor recognises the application and finds their way from the home page (Priority: P2)

**Goal**: the identity (top bar, favicon) and the start page verified for every role and on every
kind of page, including the error pages rendered by exception handlers.

**Independent Test**: sign in with each role; check the wordmark, the favicon, one card per allowed
area with its description, the sample questions and the database line in the footer (quickstart
§1, US6 row).

### Tests for User Story 6

- [ ] T075 [P] [US6] Extend `tests/integration/test_layout.py` with the identity tests (FR-008, FR-018, FR-021): on `/login`, `/`, `/admin/subjects` and the 404 page, the header has a link to `/` holding the `logo-mark` SVG and "Student Competitions"; signed in, the current role's label is in the top bar, and absent signed out; the head links `/static/img/favicon.svg`, `/static/img/favicon-32.png` and `/static/img/apple-touch-icon.png`; the footer shows the version on every page; the database status line is in the footer of `/` only.
- [ ] T076 [P] [US6] Extend `tests/integration/test_home.py` (US6-2 to US6-4): for an administrator, a teacher, a student and a person holding administrator and teacher acting as each, the card links on `/` equal `areas_for(role)` in order, each with its description from `app/routers/areas.py`, and no other area; the sample questions are listed as before; with the database unavailable (the existing milestone 3 patch) the page answers 200 with the info notice's unchanged text and no database line.

### Implementation for User Story 6

- [ ] T077 [US6] Check the exception handlers in `app/main.py` (unmatched 404, `AccessDenied` 403, cross-site 403, 5xx/503): each renders `pages/error.html` through `base.html` with the full frame, the favicons and the footer, although `resolve_access` may not have run; fix any handler context that lacks a value the frame reads (the `_current_user` and `_theme` processors already default safely). T075 passes.

**Checkpoint**: the identity and start page hold for every role and every kind of page.

---

## Phase 9: User Story 7 — An administrator reviews every component in the gallery during development (Priority: P3)

**Goal**: `GET /admin/components` shows every component and variant to administrators outside
production, and does not exist in production.

**Independent Test**: locally as an administrator, every section of components.md §12 is present;
teachers and students get "access denied"; with production on, everyone gets the same 404 as an
unknown address (quickstart §3.2 step 6, §3.5).

### Tests for User Story 7

- [ ] T078 [P] [US7] Create `tests/integration/test_component_gallery.py` per contracts/http-routes.md §2 and quickstart §1:
  - an administrator gets 200 with a section for every `id` of [components.md §12](./contracts/components.md#12-gallery-coverage-checklist-sc-009), in order, each with its variants' texts (for example **Active**, **Deactivated**, **Read**, **Write**, "There is a problem", "No subjects yet", **Light**, **Dark**, **Device**);
  - no tab in `nav(body, "Administrator area")` links to `/admin/components` and none carries `aria-current`;
  - a teacher, a student, and an administrator acting as teacher or student get 403 "Access denied" naming the current role; anonymous visitors get 303 to `/login?next=%2Fadmin%2Fcomponents`;
  - no database query runs: patch the engine's `connect` to fail for the request;
  - with `app.state.settings = dataclasses.replace(settings, production=True)`, anonymous visitors and every role get 404, and the body equals the body of `GET /no-such-page` apart from the requested path; restore the settings afterwards.

### Implementation for User Story 7

- [ ] T079 [US7] Change `render_admin` in `app/routers/admin.py` to accept `active_tab: str | None` (no tab marked current when `None`); the docstring says so. Existing callers are unchanged.
- [ ] T080 [US7] Create `app/routers/admin_components.py` per research D15: `class DevelopmentOnlyRoute(APIRoute)` overriding `matches(scope)` to return `(Match.NONE, {})` when `scope["app"].state` has no `settings` or `settings.production` is true; `router = APIRouter(route_class=DevelopmentOnlyRoute)`; module-level frozen dataclasses and tuples of sample data (subjects with a long name, regions, institutions, classes, students, a details list, field errors and a form error, confirmation and refusal texts), never from the database; `GET /admin/components` with `@allow_roles(Role.ADMIN)`, no session dependency, rendered by `render_admin(request, "pages/admin/components.html", None, {...})`. Include the router in `app/main.py`. The route-table sweep in `test_routes.py` covers it automatically; check it does.
- [ ] T081 [US7] Create `app/templates/pages/admin/components.html` (extends `layouts/admin.html`): `page_heading("Components")`, then one `<section id="…" aria-labelledby="…">` with an `h2` per row of components.md §12, in that order, rendering every macro and variant listed there from the sample data, with the palette swatches built from component classes only (no inline style; add a `.swatch` component class to `app.css` and to the guidelines if needed). `test_stylesheet.py` stays green.

**Checkpoint**: the gallery covers every component; T078 passes.

---

## Phase 10: User Story 8 — A developer builds a later milestone from the guidelines (Priority: P3)

**Goal**: the binding UI guidelines, and the constitution pointing to them.

**Independent Test**: the guidelines have every section of research D20; the constitution's styling
rule references them; `tests/unit/test_stylesheet.py` passes (quickstart §5).

- [ ] T082 [P] [US8] Write `docs/requirements/ui-guidelines.md` with the eleven sections of research D20, in order: audience; the five principles, each with its rules and sources (GOV.UK Design System, W3C/WAI *Making Content Usable*, Nielsen Norman Group, British Dyslexia Association *Style Guide*, Material and Apple HIG); the token tables of data-model §2 with the rule "use a token; never a literal"; layout (frame, content width, `768px` and `1024px`); one entry per macro of components.md (purpose, when to use and when not, variants, a call example, a link to its gallery section `id`); buttons (three kinds, one primary per page or section, links that look like their action); wording patterns with examples from the application (buttons, confirmations, errors, empty states, notices); phone behaviour; themes (how a token gets its dark value, checking both); checks (what `test_stylesheet.py` enforces; adding a pattern: library, gallery, guidelines, then use); research for milestone 13 (a visible countdown with warnings before the end, a "Saved" status per answer, a clear final **Submit** with a confirmation saying what cannot be changed afterwards).
- [ ] T083 [US8] Amend the constitution in a dedicated PR per research D19: **ask the user before creating the branch or pushing**; on a branch from `main`, run `/speckit-constitution` with the D19 changes (version 1.0.2 → 1.1.0; Principle II bullet requiring the component library and `docs/requirements/ui-guidelines.md`, new patterns added to the library, gallery and guidelines first; the Styling row; `templates/components/` and `static/fonts/` in Application Layout; a guidelines row in every later plan's Constitution Check), and open the PR. It merges before this feature's PR. Depends on a draft of T082.
- [ ] T084 [P] [US8] Update `README.md`: the theme switch (cookie `sc_theme`, Device by default), the gallery at `/admin/components` (local only, not in production), and the self-hosted Open Sans fonts under the SIL OFL (`app/static/fonts/OFL.txt`).

**Checkpoint**: the guidelines exist and are binding once the constitution PR merges.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: the review evidence required before merge.

- [ ] T085 Run `uv run ruff check .` and `uv run ruff format --check .`, and fix any finding.
- [ ] T086 Capture the review screenshots (SC-001, SC-008, research D1) with a throw-away script kept in the scratchpad, never committed: a copy of the local database, the app on port 8765, sign-in codes read from the uvicorn log; Playwright through `uv run --with playwright`; every `GET` page of pages.md §1 for each role that can open it, at 375 and 1280 px, light and dark (set by the `sc_theme` cookie), written to `screenshots/` with an `index.html` contact sheet. The report lists `scrollWidth > 375` (must be 0 pages) and the body's computed font size (≥ 16 px at 375, ≥ 18 px at 1280) and line height (≥ 1.5). Fix every failure in the components or tokens, then capture again.
- [ ] T087 **STOP and ask the product owner** to review `screenshots/index.html`; log the review, any requested change and its fix in `specs/010-design-system-ui-guidelines/design-approval.md`.
- [ ] T088 Walk through [quickstart.md §3](./quickstart.md#3-manual-walk-through-local) locally (phone student with SC-010 timing, desktop administrator, teacher with JavaScript off, themes, production guard with `RENDER=true`), and note the results in the PR description draft.
- [ ] T089 Confirm the gate (FR-046, quickstart §2) by commit order on this branch, not by date. Run the check of quickstart §2: it finds the first commit in `main..HEAD` that added "Approved" to `design-approval.md`, and the first commit in `main..HEAD` that changed `app/templates/` or `app/static/css/app.css` (the whole gate of T007, not only `pages/`), and passes only when they are different commits and `git merge-base --is-ancestor` puts the approval first. Record the two commit hashes and the result in the PR description draft. A failure is reported to the product owner, not hidden.
- [ ] T090 Mark milestone 10 "Delivered" in `docs/requirements/milestones.md`.
- [ ] T091 Run the whole suite on both engines a final time (`TEST_POSTGRES_URL=… uv run pytest`): green, with the T001 count plus the new tests (SC-002).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **US1 approval gate (Phase 2)**: depends on T002 (the mockup loads the fonts). **Blocks** every
  task that changes `app/static/css/app.css` or `app/templates/`.
- **Foundational (Phase 3)**: 3a (T008–T014 and T092) needs only Phase 1 and may run alongside Phase 2; 3b
  (T015–T031) starts after T007. Blocks every story phase below.
- **US2 (Phase 4)**, **US3 (Phase 5)**: after Foundational; independent of each other.
- **US4 (Phase 6)**: T056–T059 after Foundational; T060 (legacy CSS removal) after US2, US3 and
  T057–T059; T061's route check is re-run after US5 and US7.
- **US5 (Phase 7)**: after Foundational. T074 edits `login.html`, so it follows T035.
- **US6 (Phase 8)**: after US2 (home page, T038–T039).
- **US7 (Phase 9)**: after Foundational; its gallery shows the theme switch, so T081 follows T073.
- **US8 (Phase 10)**: T082 any time after Foundational, finished after US7 (it links gallery
  sections); T083 after a draft of T082; T084 after US5 and US7.
- **Polish (Phase 11)**: after every story.

### User Story Dependencies

- **US1 (P1)**: none; gates the rest.
- **US2 (P1)**: Foundational only.
- **US3 (P1)**: Foundational only.
- **US4 (P1)**: its clean-up closes after US2 and US3.
- **US5 (P2)**: Foundational; the sign-in switch after US2's `login.html`.
- **US6 (P2)**: US2's home page.
- **US7 (P3)**: Foundational; theme-switch variants after US5.
- **US8 (P3)**: US7 for gallery links; the constitution PR is separate and merges first.

### Within Each User Story

- Tests first; they fail before the implementation and pass after it.
- Router context changes (T034, T043, T044) before the templates that read them.
- After each page task: delete the legacy CSS rules it freed, update only the markup assertions it
  changed, run the suite.

### Parallel Opportunities

- T002 and T003; T004 alongside T002.
- T009–T013 and T092 (different test modules, after T008), and all of 3a alongside Phase 2.
- T016–T026: eleven component files, all independent.
- Test tasks marked [P] at the start of each story.
- US2 and US3 page tasks touch different templates and can be split between people; they share
  `app.css` only when deleting legacy rules, so merge those edits carefully.
- T082 and T084 alongside story work.

---

## Parallel Example: Foundational component library

```bash
# After T015, build every component family at once:
Task: "Create app/templates/components/icons.html (T016)"
Task: "Create app/templates/components/frame.html (T017)"
Task: "Create app/templates/components/button.html (T018)"
Task: "Create app/templates/components/table.html (T020)"
Task: "Create app/templates/components/form.html (T023)"
Task: "Create app/templates/components/selectors.html (T026)"
# Then T027 writes their CSS in one pass.
```

## Parallel Example: User Story 5

```bash
Task: "Create tests/unit/test_theme.py (T063)"
Task: "Extend tests/unit/test_safe_next.py (T064)"
Task: "Create tests/integration/test_theme.py (T065)"
Task: "Update test_routes.py and test_cross_site.py (T066)"
```

---

## Implementation Strategy

### MVP First

1. Phase 1, then the US1 gate (with Foundational 3a alongside).
2. Foundational 3b.
3. US2: the student journey on the new system.
4. **STOP and VALIDATE**: the US2 independent test at 375 px, in the device theme.

### Incremental Delivery

1. Gate + Foundational → the frame and components on every page.
2. US2 → the student pages.
3. US3 → the staff pages.
4. US4 → the remaining pages, the old CSS gone, behaviour audited: the rebuild is complete.
5. US5 → the theme choice.
6. US6 → the identity verified everywhere.
7. US7 → the gallery.
8. US8 → the guidelines and the constitution PR.
9. Polish → screenshots, product-owner review, walk-through, delivery.

---

## Notes

- [P] tasks touch different files and have no dependency on an unfinished task.
- The two **STOP** tasks (T006–T007, T087) wait for the product owner; T083 waits for the user's
  go-ahead to branch and push.
- Commit after each task or logical group; never commit `screenshots/` or the capture script.
- A wording change not yet in pages.md §4 is added there in the task that makes it.
