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

## Gate (T089)

To be recorded.

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

To be recorded.
