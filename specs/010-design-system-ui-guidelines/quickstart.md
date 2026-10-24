# Quickstart: Validating Milestone 10 (Design System and UI Guidelines)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/](./contracts/)

This guide proves that the feature works. It does not describe how to build it. Run it from the
repository root.

## 0. Prerequisites

- `uv sync`, as in the README.
- For the PostgreSQL half of the suite: the local `sc-pg` container, with `TEST_POSTGRES_URL` set
  (see README §Tests).
- For screenshots only: Chromium for Playwright, run on demand through `uv run --with playwright`.
  Nothing is added to `pyproject.toml` (research D1).
- `ADMIN_EMAILS` set to your own address for the manual walk-through.

---

## 1. Automated checks (CI)

```bash
uv run ruff check . && uv run ruff format --check .
TEST_POSTGRES_URL=postgresql://… uv run pytest
```

**Expected**: green on both engines. The tests map to the stories as follows.

| Story / requirement | Test module | What it proves |
|---|---|---|
| US4, SC-002, SC-011 | the whole milestone 1–9 suite | Behaviour, addresses, access and messages are unchanged. Only markup assertions moved to `tests/html.py` queries (plan, "Changes to existing tests"). |
| US4, FR-040, SC-011 | `tests/integration/test_form_contract.py` (new) | Every page state that shows a form, including those reached only by `POST`, renders the same forms as before the rebuild: the same method, action (ids as `{id}`), field names and named-button values as `form_contract.json`, generated once from the milestone 9 templates. Only the new theme-switch forms are left out. |
| US8, FR-012, FR-041, FR-048, FR-049, SC-003, SC-004, SC-008 | `tests/unit/test_stylesheet.py` (new) | Every used class is defined, and every `app.css` class is used. No inline `style`, no page-specific classes, no literal colours or pixel lengths outside the token block, no off-site resources. The body-text and line-height tokens meet the minimums. |
| US5, FR-014–FR-017, SC-005 | `tests/integration/test_theme.py` (new) | `POST /theme` sets or deletes `sc_theme` and returns to a safe target. `data-theme` and `color-scheme` match the cookie on the sign-in page, on a signed-in page and on an error page. Missing or unknown values follow the device. Cross-site posts are refused. The theme survives sign-in, role switch and logout. Unsafe and `POST`-only targets fall back. |
| US7, FR-037–FR-038a, SC-009 | `tests/integration/test_component_gallery.py` (new) | The administrator gets 200 with every section and variant in [components.md §12](./contracts/components.md#12-gallery-coverage-checklist-sc-009). Teachers, students and an administrator acting as either get 403 naming the role. Anonymous visitors are sent to sign in. No tab links to it. With production on, everyone gets the same 404 as an unknown address. No database query runs: the engine is patched to fail. |
| US2, US6, FR-018–FR-021, FR-035, FR-036 | `tests/integration/test_layout.py` (new) and the updated `test_home.py` | Top bar with the logo mark, the name and the role. The user menu is a `<details>` holding the email link, the role switch only with several roles, the theme switch and **Log out**. Favicon links. Footer version. Home cards exactly match `areas_for(role)` with their descriptions. The database line is in the footer on `/` only. The unavailable notice keeps its text. |
| US3, FR-003, FR-025–FR-032, SC-006, SC-007 | `tests/integration/test_page_patterns.py` (new) | For every form in [pages.md §3](./contracts/pages.md#3-form-error-mapping), an invalid submission shows the summary "There is a problem". It has one link per field error to `#field`, the same message beside the field, the form error as text and every value kept. Every destructive action's `GET` page has a question naming the item, a consequence, a destructive button repeating the verb, and **Cancel**. Every page below an area's main page has a back link to the target in [pages.md §1](./contracts/pages.md#1-page-inventory). Statuses are badges with text. Link actions to forms and confirmations carry `role="button"`. |
| Route table | `tests/integration/test_routes.py` (updated) | The allowlist and the write routes each gain exactly `("POST", "/theme")`. The access sweep covers `/admin/components`. |

---

## 2. Design approval (before any page is rebuilt), User Story 1

1. Open `specs/010-design-system-ui-guidelines/mockup/index.html` directly in a browser. It needs
   no server.
2. **Check**: the wordmark, the logo mark, the favicon at 16 and 32 px, the palette in both themes
   and the type scale. Then the five pages (sign-in, home, **Subjects**, **Create subject** with an
   error, **Delete “Physics”?** and its refusal), each at 375 px and 1280 px, light and dark.
3. **Check** with the browser's network panel: no request leaves `file://`.
4. **Expected**: `design-approval.md` has an "Approved" entry dated before the first commit that
   changes `app/templates/pages/`:

   ```bash
   git log --format='%ad %s' --date=short -- app/templates/pages | tail -1
   ```

---

## 3. Manual walk-through (local)

Start the application as in the README, then open it at <http://localhost:8000>.

### 3.1 Phone, as a student (US2, SC-010)

Use the browser's device mode at 375 × 812.

1. **On `/login`**, set the theme switch to **Dark**.
   - **Expected**: the sign-in page comes back dark with no white flash.
2. **Sign in** with a student account; the code is in the console.
   - **Expected**: the home page shows the greeting and one card, **Student area**, with its
     description.
   - **Expected**: no sideways scroll, and body text at 16 px.
3. **Open the user menu** with one tap.
   - **Expected**: the email (a link to the profile), the theme switch and **Log out**.
   - **Expected**: with JavaScript disabled in DevTools, the menu still opens and closes.
4. **Open the profile.**
   - **Expected**: label and value pairs, stacked.
   - **Expected**: "← Back to the home page" at the top, which returns home.
   - Time steps 2–4 (SC-010: under 2 minutes, not counting the email wait).

### 3.2 Desktop, as an administrator (US3)

Use a window 1280 px wide.

1. **On `/admin/subjects`**:
   - **Expected**: the heading with **Create subject** as the one primary button;
   - **Expected**: **Active** and **Deactivated** badges;
   - **Expected**: row actions of the same size, together at the end of each row.
2. **Create a subject with an existing name.**
   - **Expected**: the summary "There is a problem" with one link that moves focus to the field.
   - **Expected**: the same message under the field, and the value kept.
3. **Choose Delete on a subject in use.**
   - **Expected**: "Delete “Physics”?", the "is in use" reason, and the **Deactivate** alternative.
4. **Choose Delete on an unused subject.**
   - **Expected**: the consequence, a red **Delete** button, then **Cancel**.
5. **Narrow the window below 768 px.**
   - **Expected**: each table row becomes a card of labelled values, with the actions last.
6. **Open `/admin/components`.**
   - **Expected**: every section in [components.md §12](./contracts/components.md#12-gallery-coverage-checklist-sc-009),
     in the current theme.
   - **Expected**: no tab is marked current, and no tab links here.

### 3.3 Teacher (US3)

1. **On `/teacher/students`**, choose a region, an institution and a class.
   - **Expected**: each list submits on change, as before.
   - **Expected**: Read and Write appear as badges; students are in a data table.
   - **Expected**: **Add student** is a primary button.
2. **Disable JavaScript.**
   - **Expected**: the existing fallback still works, and the user menu and theme switch still work.

### 3.4 Themes (US5)

1. **From the user menu**, choose **Light**, then **Dark**, then **Device**.
   - **Expected**: each choice returns to the same page.
   - **Expected**: with **Device**, switching the OS appearance changes the open page.
2. **Sign out, then sign in again.**
   - **Expected**: the choice is kept in this browser.
3. **Open a private window.**
   - **Expected**: **Device** applies.

### 3.5 Production guard (US7, FR-038a)

1. **Start the application with production on.** Run it locally with `RENDER=true` and the
   production settings it requires (see README §Configuration).
2. **Open `/admin/components`**, signed out and then as an administrator.
   - **Expected**: both get the friendly "not found" page with status 404, identical to
     `/no-such-page`.

---

## 4. Screenshot review before merge (SC-001)

1. **Capture**: run the throw-away capture script from research D1 against a local server on
   port 8765.
2. **Coverage**: it visits every `GET` page of the inventory ([pages.md §1](./contracts/pages.md#1-page-inventory))
   for each role that can open it, at 375 and 1280 px, light and dark.
3. **Output**: it writes the PNGs and `screenshots/index.html` to the git-ignored `screenshots/`
   folder.
4. **Expected**:
   - the script's report lists **0** pages with `scrollWidth > 375` at phone width;
   - body font size is at least 16 px at phone width and at least 18 px at desktop width, with line
     height at least 1.5 (SC-008);
   - the product owner's review is logged in `design-approval.md`.

---

## 5. Documents

- `docs/requirements/ui-guidelines.md` has the sections listed in research D20, including the
  milestone 13 research (US8-1).
- The constitution amendment PR (research D19) is merged. `.specify/memory/constitution.md`
  Principle II and the Styling row point to the guidelines (US8-2).
- The README describes the theme switch, the gallery (local only) and the fonts' licence.
- `docs/requirements/milestones.md` marks milestone 10 delivered.
