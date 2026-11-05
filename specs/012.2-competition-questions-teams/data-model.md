# Data Model: Questions and Teams of a Competition (Teacher) (Milestone 12.2)

Phase 1 of [plan.md](./plan.md). Two new tables; one changed write on `teams`. No column of an
existing table changes. Decisions are in [research.md](./research.md).

## 1. Competition question: table `competition_questions` (new)

Model `CompetitionQuestion` in `app/models/competition.py`, exported from `app/models/__init__.py`.
A question as one competition holds it: a copy taken when it was added (R1, R3).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer, primary key, `AUTOINCREMENT` on SQLite | no | The order of adding: the list is sorted by it (FR-005). Never shown. |
| `competition_id` | integer, FK `competitions.id`, indexed | no | No `ON DELETE`: competitions are never deleted. |
| `question_id` | integer, FK `questions.id` | no | The bank question it was copied from: its number ("Question 12"), its "Deleted from the question bank" mark (`questions.deleted_at`) and the "Already in this competition" check. No `ON DELETE`: questions are only soft-deleted. |
| `text` | `String(QUESTION_FIELD_MAX_LENGTH)` | no | The bank's text at the moment of adding; never written again (FR-007). |
| `reference_answer` | `String(QUESTION_FIELD_MAX_LENGTH)` | no | The bank's reference answer at the moment of adding; never written again. Shown only in the teacher area. |
| `added_at` | `UTCDateTime` | no | When it was added. Never shown. |

**Constraints and indexes**

| Name | Definition | Why |
|---|---|---|
| `uq_competition_questions_competition_id_question_id` | unique `(competition_id, question_id)` | A bank question at most once per competition, under concurrency (FR-035). Its leading column serves the per-competition reads, so `competition_id` needs no separate index. |

**Writers**: `competition_entries.add_question` (insert) and `competition_entries.remove_question`
(delete), both only while the competition is **Upcoming** (R2). Nothing else writes the table:
editing or deleting the bank question leaves the copy alone (FR-039).

**Not personal data**: no column names a person.

## 2. Competition team: table `competition_teams` (new)

Model `CompetitionTeam` in `app/models/competition.py`, exported from `app/models/__init__.py`.
The fact that a team takes part in a competition (R1, R4).

| Column | Type | Null | Notes |
|---|---|---|---|
| `competition_id` | integer, FK `competitions.id`, primary key part | no | No `ON DELETE`. |
| `team_id` | integer, FK `teams.id`, primary key part, indexed | no | No `ON DELETE`: teams are only soft-deleted. Indexed for the deletion of R5. |
| `added_at` | `UTCDateTime` | no | When it was added. Never shown. |

**Constraints and indexes**

| Name | Definition | Why |
|---|---|---|
| `pk_competition_teams` | primary key `(competition_id, team_id)` | A team at most once per competition, under concurrency (FR-035). |
| `ix_competition_teams_team_id` | index on `team_id` | `delete_team` removes a team's links by team. |

**Writers**:

- `competition_entries.add_team` (insert) and `competition_entries.remove_team` (delete), only
  while the competition is **Upcoming** (R2);
- `teams.delete_team` (delete): every link of the team to a competition that is not finished
  (`stopped_at IS NULL`), in the deletion's own transaction (R5, FR-040).

**Read from the team, not copied**: the name, the institution, the region and the active-member
count are always the team's current ones (spec Assumptions).

**Not personal data**: it names a team, not its members. Data erasure (milestones 8–9) deletes
memberships, which changes only the member count shown.

## 3. Invariants

| Invariant | Held by |
|---|---|
| The questions and teams of a competition change only while it is **Upcoming** | every write locks the competition `FOR UPDATE` and checks `status_of` with a fresh clock (R2); cancelling takes the same lock |
| …except that deleting a team removes its links from every competition that is not **Finished** | `teams.delete_team` (R5); constitution v2.1.0, Principle IV |
| A deleted team is linked only to **Finished** competitions | the deletion removes the others; an addition reads the team `FOR SHARE` and refuses a deleted one, serialised with the deletion's `FOR UPDATE` (R5) |
| A competition's copy of a question never changes | no `UPDATE` of `competition_questions` exists |
| A question copied into a competition belongs to the competition's subject, and was live when added | `add_question` (R3) |
| A team linked to a competition was live, of an active institution in an active region, when added | `add_team` (R4) |
| Each question and team at most once per competition | the unique constraint and the primary key |

## 4. Derived values (never stored)

| Value | Derived by |
|---|---|
| A question's number | `competition_questions.question_id` |
| "Deleted from the question bank" | `questions.deleted_at IS NOT NULL` |
| "(deleted)" on a team | `teams.deleted_at IS NOT NULL` (only in a **Finished** competition) |
| A team's number of active members | `teams.count_active_members`: memberships whose class, institution and region are active (R13) |
| A region header's total | the competition's teams of that region, across all pages (R12) |

## 5. Migration

One Alembic revision after `72e46cb10175` (milestone 12.1), file
`migrations/versions/2026_11_<dd>_<rev>_competition_questions_and_teams.py`:

- **Upgrade**: creates `competition_questions` (with `sqlite_autoincrement=True`) and
  `competition_teams`, their foreign keys, the unique constraint and the `team_id` index, with the
  project's naming convention (`op.f(…)`).
- **No data step**: no competition holds a question or a team yet.
- **Downgrade**: drops both tables; every question and team of every competition is lost, nothing
  else changes.
- A frozen snapshot: plain SQLAlchemy types, nothing imported from `app`.

The stairway and drift tests in `tests/integration/test_migrations.py` cover it on both engines.
