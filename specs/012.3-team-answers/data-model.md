# Data Model: Entering a Team's Answers (Teacher) (Milestone 12.3)

Phase 1 of [plan.md](./plan.md). One new table; one changed write on `teams`. No column of an
existing table changes. Decisions are in [research.md](./research.md).

## 1. Team answer: table `team_answers` (new)

Model `TeamAnswer` in `app/models/competition.py`, exported from `app/models/__init__.py`. One
team's text answer to one question of one competition (R1, R2). A row exists only for an answered
question.

| Column | Type | Null | Notes |
|---|---|---|---|
| `competition_id` | integer, primary key part | no | With `team_id`, a foreign key to `competition_teams`. |
| `team_id` | integer, primary key part | no | With `competition_id`, a foreign key to `competition_teams`: the team is in the competition. |
| `competition_question_id` | integer, FK `competition_questions.id`, primary key part, indexed | no | The competition's copy of the question (R2). No `ON DELETE`. |
| `text` | `String(ANSWER_MAX_LENGTH)` (2,000) | no | Trimmed, line breaks as `\n`, 1–2,000 code points, no NUL (R5). Never empty: an emptied answer deletes the row. |

**Constraints and indexes**

| Name | Definition | Why |
|---|---|---|
| `pk_team_answers` | primary key `(competition_id, team_id, competition_question_id)` | One answer per question per team (FR-022). Its leading columns serve the sheet (one team) and the progress (a page of teams). |
| `fk_team_answers_competition_id_competition_teams` (the convention names a composite key by its first column) | `(competition_id, team_id)` → `competition_teams (competition_id, team_id)`, no `ON DELETE` | An answer's team is in the competition; deleting the link first requires deleting its answers (R7). |
| `fk_team_answers_competition_question_id_competition_questions` | `competition_question_id` → `competition_questions.id`, no `ON DELETE` | An answer's question exists. |
| `ix_team_answers_competition_question_id` | index on `competition_question_id` | The foreign-key check when a competition's question is removed (12.2). |
| `ck_team_answers_answered` | `text <> ''` | A row means "answered" (FR-009, FR-016). |

**Not stored** (FR-023): who saved an answer, and when.

**Writers**:

- `team_answers.save_answers` (insert, update, delete): only while the competition is **In
  progress**, by a teacher with **Write** access to the team's institution (R3, R4);
- `teams.delete_team` (delete): every answer of the team in a competition that is not finished
  (`stopped_at IS NULL`), in the deletion's own transaction, before its links (R7).

**Not personal data**: answers belong to the team, and no column names a person (constitution
v2.2.0, Principle V; product requirements "Personal data"). Data erasure does not touch the table.

## 2. Changed: `competition_teams` and `competition_questions`

No column changes. Both are now referenced by `team_answers`, so:

- **`competition_teams`**: `teams.delete_team` deletes the team's answers before its links;
  `competition_entries.remove_team` (Upcoming only) never meets an answer.
- **`competition_questions`**: `competition_entries.remove_question` (Upcoming only) never meets an
  answer.

The model docstrings name the new referencing table.

## 3. Invariants

| Invariant | Held by |
|---|---|
| Answers change only while the competition is **In progress** | `save_answers` reads the competition `FOR SHARE` and checks `status_of` with a fresh clock (R3); cancelling and stopping take it `FOR UPDATE` |
| …except that deleting a team deletes its answers in every competition that is not **Finished** | `teams.delete_team` (R7); constitution v2.2.0, Principle IV |
| An answer's team is in the competition | the composite foreign key; `delete_team` deletes answers before links |
| An answer's question is one of the competition's | `save_answers` checks every named id against the competition's copies (R3 step 4); the questions of an **In progress** competition cannot change (12.2) |
| An answer is saved only by a teacher with **Write** access to the team's institution | `save_answers` step 5, under lock (R3, R6) |
| At most one answer per question per team | the primary key |
| A stored answer is non-empty, trimmed and at most 2,000 code points | `clean_answer` (R5) and the check constraint |
| The team's stored answers are always those of one whole save | the link row `FOR UPDATE` and one commit per save (R4) |
| A deleted team keeps its answers only in **Finished** competitions | `delete_team` (R7) |

## 4. Derived values (never stored)

| Value | Derived by |
|---|---|
| A team's progress "3 of 6" | the team's `team_answers` rows in the competition, of the competition's `competition_questions` (FR-009) |
| A question's number on the sheet | its position in the order of adding (`competition_questions.id`) |
| "Enter answers" or "Read access" | the teacher's `teacher_institutions.access_level` for the team's institution, read on every request |
| Whether a team is listed for a teacher | the team is live, in the competition, and its institution is reachable (linked, active, in an active region) |
| A region header's total | the listed teams of that region, across all pages (FR-007) |

## 5. Migration

One Alembic revision after `59c636929942` (milestone 12.2), file
`migrations/versions/2026_11_<dd>_<rev>_team_answers.py`:

- **Upgrade**: creates `team_answers` with its primary key, the two foreign keys, the check
  constraint and the `competition_question_id` index, with the project's naming convention
  (`op.f(…)`).
- **No data step**: no answer exists yet.
- **Downgrade**: drops the table; every answer is lost, nothing else changes.
- A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`; the length is a frozen
  constant, as in the 12.2 revision.

The stairway and drift tests in `tests/integration/test_migrations.py` cover it on both engines.
