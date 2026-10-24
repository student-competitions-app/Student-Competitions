# PR Description Draft: Milestone 10

The evidence that tasks.md asks to record for the pull request description. It is filled in as
the tasks run.

## Baseline (T001)

Run on `010-design-system-ui-guidelines` at `cd8633b`, before any change, on 2026-10-24:

- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check .`: 267 files already formatted.
- `TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest`: **2215 passed,
  3 skipped** (SQLite and PostgreSQL).

Every later checkpoint compares against this count (SC-002).

## Test harness checkpoint (T014)

After the markup assertions moved to `tests/html.py` and the form contract was added, before any
look change: ruff clean; **2328 passed, 3 skipped** on both engines, which is the 2215 baseline
plus the 113 form-contract tests (56 cases × 2 engines, and the stale-case check). The contract
file `tests/integration/form_contract.json` was generated once, from the milestone 9 templates.
The signed-in 404 page is not a case: it shows no form today, because the error handlers render
without the session (T077 checks the frame there).

## Error pages (T077)

No handler needed a change: the 404, the "Access denied" 403 and the "Request refused" 403 render
`pages/error.html` through `base.html` with the full frame, the favicons and the footer. The
`_current_user` and `_theme` context processors default safely when `resolve_access` has not
run, and `app_name` is now a template global. `test_layout.py` checks the identity on each of
these pages.

## Screenshots (T086)

A throw-away Playwright script (`uv run --with playwright`, kept out of the repository) captured
56 pages for four people (signed out, an administrator, a teacher, a student), at 375 and 1280 px,
light and dark, set by the `sc_theme` cookie: 224 screenshots in the git-ignored `screenshots/`,
with `screenshots/index.html` as the contact sheet. The report found **0 problems**: no page wider
than 375 px at phone width, body text 16 px at 375 px and 18 px at 1280 px, line height 1.5, and
every page rendered the chosen theme. The only non-200 statuses are the intended error states
(400 link pages, 404 not-found pages, 403 access denied, 409 refusals).

## Gate (T089)

Checked by commit order on this branch with the quickstart §2 script: the first commit adding
`| Approved |` to `design-approval.md` is `47d6a71`, the first commit changing `app/templates/`
or `app/static/css/app.css` is `12f4a72`, and `47d6a71` is an ancestor of `12f4a72`. **Gate
kept.**

## Behaviour audit (T061)

Run on 2026-10-24, after US5 and US7.

- **Routes**: the sorted `(method, path)` list of the application, `main` (76 entries) against
  this branch (78), differs by exactly `GET /admin/components` and `POST /theme`.
- **Fields**: `tests/integration/form_contract.json` has one commit, `71750e6`, the one that
  generated it from the milestone 9 templates before any template changed. `test_form_contract.py`
  (56 cases) is green on both engines, so every form on every page keeps its method, action and
  field names.
- **Tests**: `git diff main -- tests/integration tests/unit` replaces literal-markup assertions with
  `tests/html.py` queries, applies the wording changes of contracts/pages.md §4, and adds the new
  modules (`test_layout`, `test_page_patterns`, `test_form_contract`, `test_theme`,
  `test_component_gallery`, `tests/unit/test_theme`, `test_stylesheet`). No milestone 1–9 test is
  removed; one is renamed because its subject moved: `test_status_line_sits_between_the_questions_and_the_footer`
  became `test_status_line_is_in_the_footer` (the database line is in the footer, pages.md §4.1).
  No access or behaviour assertion is dropped or loosened; status codes, addresses and texts are
  still asserted exactly.

## Walk-through (T088)

- **Phone, student** (375 px): sign-in with **Dark** chosen first, then home with one card
  (**Student area**), the user menu and the profile with its back link, all checked in the
  screenshots and in a browser with JavaScript disabled: the theme switch works on the sign-in
  page, the choice survives signing in, the menu opens and closes, and **Device** removes the
  choice. The SC-010 timing (under two minutes) was not measured by a person.
- **Desktop, administrator** (1280 px): the subjects list, the duplicate-name form, the in-use and
  the plain delete confirmations, the cards below 768 px and the gallery, in the screenshots and in
  `test_page_patterns.py`.
- **Teacher**: the Students tab's three lists, badges and table; the lists keep milestone 9's
  auto-submit, unchanged.
- **Themes**: Light, Dark and Device from the user menu and the sign-in page; `test_theme.py`.
- **Production guard**: checked by `test_component_gallery.py` with `settings.production` on (every
  visitor gets the same 404 as an unknown address), not by starting the server with `RENDER=true`.

## Constitution (T083) and final run (T091)

The constitution amendment to v1.1.0 merged first, as PR #38. This branch then merged
`origin/main` (PR #37, PR #38) and takes its constitution unchanged. After the merge: ruff clean;
**2572 passed, 3 skipped** on SQLite and PostgreSQL; the gate check against `origin/main` still
passes (`47d6a71` before `12f4a72`).

