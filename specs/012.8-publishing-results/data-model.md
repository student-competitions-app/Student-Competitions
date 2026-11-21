# Data Model: Publishing a Competition's Results (Milestone 12.8)

Phase 1 of [plan.md](./plan.md). Decisions: [research.md](./research.md) R3–R7.

## 1. `competitions` (changed)

One new column and one new check constraint.

| Column | Type | Null | Rule |
|---|---|---|---|
| `published_at` | `UTCDateTime` | yes | The publishing moment, UTC. Written once by `app.services.results.publish_results`, only while the competition is **Finished**, with a conditional update; never cleared. |

| Constraint | Definition | Meaning |
|---|---|---|
| `published_after_finish` | `published_at IS NULL OR stopped_at IS NOT NULL` | Only a finished competition is published. With `one_end` (`cancelled_at IS NULL OR stopped_at IS NULL`), a cancelled one never is. |

The partial unique index `uq_competitions_subject_name_live` is unchanged. A published competition
has `stopped_at` set, so it is not live and its name stays free (FR-018).

## 2. `competition_results_files` (new)

The stored snapshot of a published competition's results, one row per language.

| Column | Type | Null | Rule |
|---|---|---|---|
| `competition_id` | integer, FK `competitions.id` | no | No `ON DELETE`: competitions are never deleted. |
| `language` | `String(2)` | no | `'uk'` or `'en'` (`app.core.i18n.Language`); check constraint `results_file_language`. |
| `content` | `LargeBinary` (`BYTEA` / `BLOB`) | no | The PDF as rendered at publishing; check constraint `results_file_not_empty` (`length(content) > 0`). Never updated. |

- **Primary key**: `(competition_id, language)`, so there is at most one file per language. Its
  leading column serves the lookup by competition, so it needs no other index.
- **Writers**: `app.services.results.publish_results` only, with two inserts in the publishing
  transaction. No code path updates or deletes a row.
- **Readers**: `app.services.results.results_file`, which reads one row by its primary key for the
  download. `select(Competition)` never touches the table, so lists read no blob.
- **Personal data**: none. It holds team, institution and region names and scores (product
  requirements, "Personal data").

SQLModel: `class CompetitionResultsFile(SQLModel, table=True)` in `app/models/competition.py`,
exported from `app.models`.

## 3. The status (derived, never stored)

`app.services.competitions.status_of(row, now)`:

```text
cancelled_at set          → Cancelled
published_at set          → Published
stopped_at set            → Finished
now < starts_at           → Upcoming
otherwise                 → In progress
```

`CompetitionStatus` order: `UPCOMING`, `IN_PROGRESS`, `FINISHED`, `PUBLISHED`, `CANCELLED` (the
status filter's order). `CompetitionStatus.has_finished` is true for `FINISHED` and `PUBLISHED`.

### Transitions

```text
Upcoming ──start passes──▶ In progress ──finish──▶ Finished ──publish──▶ Published
    │                           │
    └──────────cancel───────────┴──▶ Cancelled
```

- **publish**: only from **Finished**; only when every team is fully graded; never undone.
- **Published** has no outgoing transition: no unpublish, no cancel, no edit.

## 4. Invariants

1. A competition has two results files if and only if it is **Published**. Both rows are inserted
   in the transaction that sets `published_at`, so neither exists without the other.
2. A results file never changes: no `UPDATE` or `DELETE` statement targets the table, and
   `tests/integration/test_results_service.py` checks the bytes after renames, deactivations and
   deletions.
3. On a **Published** competition no `team_answers.grade` changes. `grades.save_grades` (the only
   writer of `grade`) requires **Finished** under the competition's share lock, and publishing takes
   the competition `FOR UPDATE`.
4. A **Published** competition was fully graded when it was published, and its grades are frozen,
   so the scores derived from `team_answers.grade` equal the scores in its files.
5. Visibility is unchanged: a published competition has `stopped_at`, so it is visible when its
   subject is deactivated, and `teams.delete_team` leaves it alone.

## 5. The snapshot (in memory, not stored)

`app.services.results.ResultsSnapshot`, a frozen dataclass handed to the renderer:

| Field | Type | Source |
|---|---|---|
| `competition_name` | `str` | `competitions.name` |
| `subject_name` | `str` | `subjects.name` |
| `starts_at`, `finished_at`, `published_at` | aware `datetime` (UTC) | `starts_at`, `stopped_at`, the publishing moment |
| `regions` | `tuple[RegionResults, ...]` | ordered by `name_sort_key`, then id |
| `RegionResults.name` | `str` | `regions.name` |
| `RegionResults.lines` | `tuple[ResultLine, ...]` | institutions by `name_sort_key`, then id; within one, teams by `name_sort_key`, then id |
| `ResultLine` | `institution: str`, `team: str`, `score: int` | `institutions.name`, `teams.name`, `grade_counts(...)[team].score` or 0 |

Every team of the competition is included: deleted teams, and teams of deactivated institutions or
regions. Nothing else about a team (members, answers, grades per question) is read.

## 6. The migration

One Alembic revision after `7110bec350d2` (`2026_11_<dd>_<rev>_published_results.py`):

- `upgrade`:
  - `batch_alter_table("competitions")`: add `published_at` and create the check constraint
    `published_after_finish`; batch mode is needed for SQLite;
  - create `competition_results_files` with its primary key, foreign key and two check constraints.
- `downgrade`: drop the table, then the constraint and the column (batch mode).
- No data step: no competition is published before this revision.
- Covered by the existing drift, single-head and stairway tests on both engines.
