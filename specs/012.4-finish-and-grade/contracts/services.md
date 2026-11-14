# Contract: Services and Helpers

Phase 1 of [plan.md](../plan.md). Signatures and behaviour only; bodies are the implementation's.
Decisions: [research.md](../research.md).

## `app/schemas/grade.py` (new, pure)

```text
GRADE_ERROR = "Enter a whole number from 0 to 10."
GRADE_MAX = 10

class InvalidGrade(ValueError):
    message: str                       # GRADE_ERROR

def clean_grade(raw: str) -> int | None
    # strip(); "" → None (not graded)
    # not (isascii() and isdigit()) → InvalidGrade
    # significant = value.lstrip("0") or "0"        (leading zeros ignored, however many)
    # len(significant) ≤ 2 and int(significant) ≤ 10 → int; else InvalidGrade
```

A grade is an integer from 0 to 10. "07", "0007" → 7; "0010" → 10; "000" → 0; "7.5", "-1", "11",
"011", "seven", "+7", "7.0", "1e1", "٧" → `InvalidGrade` (research R4).

## `app/services/competitions.py` (changed)

```text
class NotFinishable(ValueError):
    status: CompetitionStatus          # Upcoming, Cancelled or Finished (409)

def finish_competition(session, teacher_id, competition_id, subject_id,
                       status: CompetitionStatus | None) -> Landing
```

- **Order**: `_require_manage` (`ManageRequired`) → `lock_competition` FOR UPDATE
  (`CompetitionNotFound`) → status with a fresh clock, not **In progress** → `NotFinishable` →
  the filtered list before (old index) → conditional update setting `stopped_at = now` where
  `cancelled_at IS NULL AND stopped_at IS NULL AND starts_at <= now`; no row → `NotFinishable`
  with the re-read status → the filtered list after → commit → log `Competition finished: id=%d` →
  `landing(after, competition_id, old_index)`.
- Every refusal rolls back first. Nothing else in the module changes; the module docstring's
  "Contract for later milestones" now records that stopping exists.

## `app/services/grades.py` (new)

### Types

```text
@dataclass(frozen=True)
class GradeCount:
    answered: int
    graded: int
    score: int
    fully_graded: bool                 # property: graded == answered

class GradeFilter(StrEnum):
    ALL = "all"
    UNGRADED = "ungraded"              # the address value of show=

def parse_grade_filter(raw: str | None) -> GradeFilter   # "ungraded" → UNGRADED; anything else → ALL

@dataclass(frozen=True)
class GradeTeamRow:
    team_id: int
    name: str
    institution_name: str
    active_members: int
    is_deleted: bool
    answered: int
    questions: int
    graded: int
    score: int

@dataclass(frozen=True)
class GradeTeamPage:
    groups: list[RegionGroup[GradeTeamRow]]
    paging: Paging                     # counts the listed teams under the filter
    teams_total: int                   # all the competition's teams
    teams_graded: int                  # fully graded, of all

@dataclass(frozen=True)
class GradingQuestion:
    competition_question_id: int       # the grade field is grade-<id>
    number: int
    text: str
    reference_answer: str
    answer: str | None                 # None: not answered (no field)
    grade: int | None

@dataclass(frozen=True)
class GradingSheet:
    team_id: int
    team_name: str
    institution_name: str
    is_deleted: bool
    questions: list[GradingQuestion]
    count: GradeCount

@dataclass(frozen=True)
class GradeSaveResult:
    graded: int
    changed: int
```

### Errors

```text
class GradingClosed(ValueError): status: CompetitionStatus   # not Finished (409)
class GradedTeamNotFound(LookupError)                        # unknown, or not in the competition (404)
class GradedQuestionNotFound(LookupError)                    # not the competition's, or not answered (404)
class InvalidGrades(ValueError): errors: dict[int, str]      # by copy id, in question order (400)
```

`ManageRequired` and `CompetitionNotFound` are the 12.1 errors of `competitions`. The two
not-found errors are named apart from `team_answers.TeamNotFound` and `QuestionNotFound` because
their rules differ: grading finds a deleted team, or one of a deactivated institution or region
(a finished competition keeps every team, and every one is graded), and refuses a question the team
did not answer (it has no answer to grade). Both map to the same "Team not found" and "Question
not found" pages.

### Reads

```text
def grade_counts(session, competition_id) -> dict[int, GradeCount]
    # one grouped query over team_answers of the competition; a team with no row is absent
    # (read it as GradeCount(0, 0, 0))

def grade_team_page(session, competition_id, show: GradeFilter, p: int) -> GradeTeamPage
    # team_entries (unfiltered), grade_counts, the filter, group_by_region; active members and
    # the question count for the page; the overall progress over all entries

def is_listed(session, competition_id, team_id, show: GradeFilter) -> bool
    # the team is in the competition and, under UNGRADED, still has an ungraded answer

def team_page_of(session, competition_id, team_id, show: GradeFilter) -> int
    # the page of the Grades page under `show` that holds the team, 1 if it is not listed:
    # the grading sheet's way back when its address carries no valid `back` (as 12.3's
    # team_answers.team_page_of). Shares one private "listed entries" helper with the two above.

def grading_sheet(session, competition_id, team_id) -> GradingSheet
    # GradedTeamNotFound for an unknown team or one not in the competition; deleted teams and
    # deactivated institutions and regions are found. Every copy in order, with its reference
    # answer, the team's answer and grade. No access check: the caller holds the setting and
    # has checked the competition and its status.
```

### Write

```text
def save_grades(session, teacher_id, competition_id, subject_id, team_id,
                raw_grades: Mapping[int, str]) -> GradeSaveResult
```

In this order, each refusal after a rollback (research R3): the setting `FOR SHARE`
(`ManageRequired`) → `competitions.lock_competition(share=True)` (`CompetitionNotFound`) → status
with a fresh clock, not **Finished** → `GradingClosed` → the team (`GradedTeamNotFound`) and its
link `FOR UPDATE` (`GradedTeamNotFound`) → every named id is a copy of the competition with an
answer of the team (`GradedQuestionNotFound`) → `clean_grade` on each, in question order (`InvalidGrades`) → the
team's rows re-read (`populate_existing`), each named row's `grade` set where it differs → commit →
log `Grades saved: competition=%d team=%d graded=%d changed=%d`. A row the save does not name keeps
its grade. Never touches `text`.

## `app/services/team_answers.py` (changed)

- **`AnswerTeamRow`** gains `graded: int | None` and `score: int | None` (set only on a **Finished**
  competition); `can_write` stays and now chooses **Enter answers** or **View answers** (research
  R7).
- **`answer_team_page(session, teacher_id, competition_id, p, *, finished: bool)`**: with
  `finished`, the counts come from `grades.grade_counts` for the listed teams.
- **`SheetQuestion`** gains `grade: int | None`.
- **`AnswerSheet`** gains `can_write: bool`, `institution_id` (for the notice) and
  `count: GradeCount | None` (on a **Finished** competition).
- **`answer_sheet(session, teacher_id, competition_id, team_id, *, finished: bool)`**: the same
  team checks; `NotReachable` → `AnswersDenied`; **Read** access no longer raises (it sets
  `can_write=False`); with `finished`, the grades and the count are filled. Never the reference
  answer.
- **`save_answers`**: unchanged (it still refuses **Read** and every status but **In progress**).
- The module docstring's "Contract for later milestones" names `app.services.grades` as the grader
  of these rows.

## `app/services/competition_entries.py` (changed)

```text
def question_copies(session, competition_id) -> list[CompetitionQuestion]
    # the competition's copies in the order of adding (CompetitionQuestion.id): moved here from
    # team_answers._question_copies, unchanged
```

Both `team_answers` and `grades` import it from here. **The imports run one way only**:
`team_answers` → `grades` (for `grade_counts` and `GradeCount`) → `competition_entries`;
`grades` never imports `team_answers`, so the two services form no import cycle. `team_entries`
and `group_by_region` are reused as they are.

## `app/services/teams.py` (unchanged)

`count_active_members` is reused as it is. `delete_team` already skips finished competitions, so
it never meets a grade.

## Notices (in the routers)

```text
# competitions list (12.1): NOTICES["finished"] = "Competition “{name}” was finished"
# grading sheet: purpose "grades-notice", lifetime 10 minutes
# payload: {"competition": <id>, "team": <id>, "outcome": "saved"}
# text: "Grades of “{team}” were saved", the team named as stored when shown
```

## `app/models/__init__.py`

Unchanged: `TeamAnswer` is already exported.

## Contract for later milestones

- **Milestone 13** (students): `save_answers` with the access step replaced by membership; a
  finished competition refuses as it does now.
- **Milestone 14** (LLM): proposes a grade per row of a **Finished** competition; the stored
  `team_answers.grade`, proposed or adjusted through `save_grades`, is the one that counts.
- **Milestone 15** (results): a team's score is `grade_counts(…)[team].score`; places are worked out
  from it, never stored apart from the grades.
