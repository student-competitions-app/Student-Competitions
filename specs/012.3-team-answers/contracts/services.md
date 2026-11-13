# Contract: Services and Helpers

Every function takes an open session first; the caller owns it. See [research.md](../research.md)
R3–R7, R11.

## `app/schemas/answer.py` (new, pure)

```python
ANSWER_MAX_LENGTH = QUESTION_FIELD_MAX_LENGTH  # 2000; also the column length

class InvalidAnswer(ValueError):
    message: str  # ready to show beside the field

def clean_answer(raw: str, number: int) -> str:
    """Line endings → "\n"; a NUL → InvalidAnswer("Answer to question <number> cannot contain a
    null character."); trimmed; "" means not answered; more than 2,000 code points →
    InvalidAnswer("Answer to question <number> can be at most 2,000 characters.")."""
```

## `app/services/team_answers.py` (new)

Reading needs only the teacher role (the routes check it) and a competition already found with
`competitions.get_competition` (its subject and visibility checked). The clock is
`app.services.competitions.utc_now`, read through that module, so tests that move the 12.1 clock
move this one too.

### Types

```python
@dataclass(frozen=True)
class AnswerTeamRow:
    team_id: int
    name: str
    institution_name: str
    active_members: int
    answered: int        # the team's answers in the competition
    questions: int       # the competition's questions
    can_write: bool      # Write access to the team's institution

@dataclass(frozen=True)
class AnswerTeamPage:
    groups: list[RegionGroup[AnswerTeamRow]]   # this page: regions, then teams, by name ignoring case
    paging: Paging                             # counts the listed teams
    linked: bool                               # the teacher has at least one reachable institution

@dataclass(frozen=True)
class SheetQuestion:
    competition_question_id: int   # the field: answer-<id>
    number: int                    # 1, 2, 3, … in the order of adding
    text: str                      # the copy; never the reference answer
    answer: str                    # the saved answer, "" when not answered

@dataclass(frozen=True)
class AnswerSheet:
    team_id: int
    team_name: str
    institution_name: str
    questions: list[SheetQuestion]
```

### Errors

| Error | Meaning | Route answer |
|---|---|---|
| `competitions.CompetitionNotFound` | re-used | 404 |
| `AnswersClosed(status)` | the competition is not **In progress** | 409 |
| `TeamNotFound` | unknown, deleted, not in the competition, or of a deactivated institution or region | 404 |
| `QuestionNotFound` | a named question is not one of the competition's | 404 |
| `AnswersDenied` | not linked to the team's institution, or **Read** only | 403 |
| `InvalidAnswers(errors: dict[int, str])` | by `competition_question_id`, in question order | 400 |

### Reads

- `answer_team_page(session, teacher_id, competition_id, p) -> AnswerTeamPage`: the competition's
  live teams whose institution the teacher reaches (`teacher_access.list_reachable_institutions`),
  grouped by region with `competition_entries.group_by_region`, the totals counting only those
  teams; ten per page, clamped; active members and answered counts for the page's teams in one
  query each (R11).
- `team_page_of(session, teacher_id, competition_id, team_id) -> int`: the page of that listing
  holding the team, 1 if it is not listed; for the sheet's back link fallback (R10).
- `answer_sheet(session, teacher_id, competition_id, team_id) -> AnswerSheet`: checks R3 steps 3
  and 5 without locks (`TeamNotFound`, then `AnswersDenied`), then every copy in the order of adding
  with the team's saved answer.
- `count_answered(session, competition_id, team_ids) -> dict[int, int]`: one grouped count.

### Write

- `save_answers(session, teacher_id, competition_id, subject_id, team_id, raw_answers: Mapping[int,
  str]) -> SaveResult(answered: int, changed: int)`: R3 steps 1–7 in one transaction, then one
  commit; each refusal rolls back before it raises; nothing is stored then. Applies R4: for each
  named question, an empty cleaned text deletes the row, an equal text writes nothing, any other
  inserts or updates it; unnamed questions keep their rows. Logs one line, ids and counts only:
  `Team answers saved: competition=%d team=%d answered=%d changed=%d`.

## `app/services/competitions.py` (changed)

- `lock_competition(session, competition_id, subject_id, *, share=False)`: with `share`, the
  competition is read `FOR SHARE` instead of `FOR UPDATE`; the subject stays `FOR SHARE`; both
  refreshed; `CompetitionNotFound` after a rollback otherwise (R3).
- The module's "Contract for later milestones" names the answers: entered only while **In
  progress**, under the competition's share lock.

## `app/services/competition_entries.py` (changed)

- `_team_entries` → public `team_entries(session, competition_id)`.
- New `group_by_region(entries, p, make_rows) -> (list[RegionGroup[Row]], Paging)`: the 12.2
  grouping and per-region totals, extracted. `make_rows(shown)` is called **once** with the page's
  `(team, institution, region)` entries and returns their rows in the same order, so a caller
  counts members (and answers) for the whole page in one query each; `team_page` calls it with a
  `make_rows` built on `count_active_members` and `_team_row`.
- `RegionGroup` becomes generic in its row type (`RegionGroup[TeamRow]` for 12.2).
- The docstring's "Contract for later milestones" points to `team_answers` for the answers.

## `app/services/teams.py` (changed)

- `delete_team`: before deleting the team's links to competitions with `stopped_at IS NULL`, deletes
  the team's `team_answers` in those competitions, in the same transaction; logs
  `Team deleted: id=%d members=%d competitions=%d answers=%d` (R7). Docstring updated.

## `app/services/teacher_access.py` (unchanged)

`list_reachable_institutions` and `reach_institution(write=True, lock=…)` are used as they are.

## Notices (in the router)

```python
# purpose "team-answers-notice", lifetime 10 minutes
# payload: {"competition": <id>, "team": <id>, "outcome": "saved"}
# text: "Answers of “{team}” were saved" (success), the team named as stored when shown
```

## `app/models/__init__.py` (changed)

Exports `TeamAnswer`.

## Contract for later milestones

- **A later 12.x (grading by hand)** grades the rows of `team_answers`; a question with no row has
  no answer to grade.
- **Milestone 13 (students)** saves through `save_answers`' steps 1–4 and 6–7, with step 5 replaced
  by "the student is a member of the team", into the same rows: the last save wins, whoever made
  it.
- **Milestone 14 (LLM)** scores each row against its copy's text and reference answer; a changed row
  (R4) needs scoring again. The evaluation status it needs is a new column or table then.
- **Milestone 15 (results)** reads the answers of every team, deleted ones included, of a
  **Finished** competition.
