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

## Gate (T089)

To be recorded.

## Behaviour audit (T061)

To be recorded.

## Walk-through (T088)

To be recorded.
