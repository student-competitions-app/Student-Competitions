# Data Model: Finishing a Competition and Grading Its Answers by Hand (Teacher) (Milestone 12.4)

Phase 1 of [plan.md](./plan.md). One column is added; finishing uses a column that already exists.
Decisions: [research.md](./research.md) R1, R2, R5.

## 1. Grade: column `team_answers.grade` (new)

| Column | Type | Null | Rule |
|---|---|---|---|
| `grade` | `SMALLINT` | yes | `NULL` = not graded; otherwise a whole number 0–10 |

- **Check constraint `grade_range`** (named through the project's convention, `ck_team_answers_grade_range`):
  `grade IS NULL OR (grade >= 0 AND grade <= 10)`.
- **No author, no time** (FR-028): who graded and when are not stored. Not personal data.
- **No index**: every read of grades already filters by `(competition_id, team_id)` or
  `competition_id`, the leading columns of the primary key.

**Model** (`app/models/competition.py`, `TeamAnswer`):

```text
grade: int | None = Field(default=None, sa_type=SmallInteger, nullable=True)
__table_args__ += CheckConstraint("grade IS NULL OR (grade >= 0 AND grade <= 10)", name="grade_range")
```

The docstring of `TeamAnswer` gains its new writer: `app.services.grades.save_grades` writes
`grade` only, only while the competition is **Finished**; `save_answers` writes `text` only, only
while it is **In progress**.

## 2. Unchanged: `competitions.stopped_at`

Exists since milestone 12.1 (`UTCDateTime`, nullable, with the `one_end` check constraint against
`cancelled_at`). Milestone 12.4 is its first writer: `competitions.finish_competition` sets it once,
to the moment of finishing, and never clears it. The docstrings of `Competition` and of the field
lose "a later 12.x milestone; in milestone 12.1 only tests set it".

## 3. State transitions of a competition

```text
            start passes (nobody acts)          Finish competition
Upcoming ──────────────────────────────▶ In progress ──────────────────▶ Finished
   │                                         │
   │ Cancel competition                      │ Cancel competition
   ▼                                         ▼
Cancelled ◀──────────────────────────────────┘
```

- **Finished** is final: never **In progress** again, never **Cancelled** (`one_end`, and the
  cancel service refuses it).
- **Finishing** is possible only from **In progress** (the conditional update requires
  `cancelled_at IS NULL AND stopped_at IS NULL AND starts_at <= :now`).

## 4. Invariants

| Invariant | Kept by |
|---|---|
| At most one grade per answer; no grade for an unanswered question | the column on the answer row; a row exists only for an answered question (12.3) |
| A grade is 0–10 | `grade_range`; `clean_grade` before it |
| Grades exist only on **Finished** competitions | `save_grades` checks **Finished** under the competition's share lock; nothing else writes `grade` |
| A finished competition's questions, teams and answers never change | 12.2 writers require **Upcoming**; `save_answers` requires **In progress** under the share lock; `delete_team` skips finished competitions |
| A competition is never both cancelled and finished | `one_end`; the conditional updates of cancel and finish under `FOR UPDATE` |
| A team's grades are those of one save | the competition team link `FOR UPDATE` in `save_grades` |

## 5. Derived values (never stored)

| Value | Definition |
|---|---|
| **Answered** of a team | rows of the team in the competition (12.3) |
| **Graded** of a team | rows with `grade IS NOT NULL` |
| **Score** of a team | `SUM(grade)` over its rows, 0 when none is graded |
| Team **fully graded** | Graded = Answered (so a team with no answers is) |
| **Overall progress** | fully graded teams / all the competition's teams |
| **Ungraded only** | teams with Graded < Answered |

## 6. Migration

One Alembic revision after `b709653d1111` (milestone 12.3), file
`migrations/versions/2026_11_<dd>_<rev>_answer_grades.py`:

- **Upgrade**: `batch_alter_table("team_answers")` adds `grade SMALLINT NULL` and the check
  constraint `ck_team_answers_grade_range` (`op.f(…)` naming). Batch mode copies the table on SQLite
  and is a plain `ALTER TABLE` on PostgreSQL.
- **No data step**: no grade exists yet; every existing answer is not graded.
- **Downgrade**: drops the constraint and the column; every grade is lost, nothing else changes.
- A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.

The stairway and drift tests in `tests/integration/test_migrations.py` cover it on both engines.
