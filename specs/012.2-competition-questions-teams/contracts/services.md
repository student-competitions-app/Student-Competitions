# Contract: Services and Helpers

Python interfaces the routes and later milestones rely on. Every service function takes an open
session first; the caller owns it. Decisions are in [research.md](../research.md).

## `app/services/competition_entries.py` (new)

The questions and teams of a competition. The clock is `app.services.competitions.utc_now` (the
12.1 module's), read once per call, so tests that move the 12.1 clock move this one too. Each
successful change logs one line with ids only: `Competition question added: competition=%d
question=%d`, `… removed …`, `Competition team added: competition=%d team=%d`, `… removed …`.
No name or text is ever logged (FR-048). A no-op ("already", "absent") and a refusal log nothing.

### Types

```python
EntryKind = Literal["question", "team"]


@dataclass(frozen=True)
class CompetitionQuestionView:
    question_id: int  # the number shown: "Question 12"
    text: str  # the copy
    reference_answer: str  # the copy
    deleted_from_bank: bool


@dataclass(frozen=True)
class CompetitionQuestionPage:
    questions: list[CompetitionQuestionView]  # order of adding
    paging: Paging


@dataclass(frozen=True)
class TeamRow:
    team_id: int
    name: str
    institution_name: str
    active_members: int
    is_deleted: bool  # only in a Finished competition


@dataclass(frozen=True)
class RegionGroup:
    region_id: int
    region_name: str  # as stored
    total: int  # the region's teams in the competition, across all pages
    rows: list[TeamRow]  # this page's rows of the region


@dataclass(frozen=True)
class CompetitionTeamPage:
    groups: list[RegionGroup]  # this page, regions then teams by name ignoring case
    paging: Paging  # counts teams, not regions


@dataclass(frozen=True)
class AddableTeam:
    team_id: int
    name: str
    institution_name: str
    active_members: int


@dataclass(frozen=True)
class AddableTeamPage:
    teams: list[AddableTeam]  # by name ignoring case
    paging: Paging
```

### Errors

| Exception | Meaning | Route answer |
|---|---|---|
| `competitions.ManageRequired` | no **Can manage competitions** | 403 |
| `competitions.CompetitionNotFound` | unknown, of another subject, or hidden | 404 "Competition not found" |
| `NotChangeable(status)` | the competition is not **Upcoming** | 409, the refusal for `status` |
| `EntryNotFound(kind)` | the question or team cannot be added (R3, R4), or names nothing at all on removal | 404 "Question not found" / "Team not found" |
| `AlreadyIn(kind, entry_id)` | adding one that is already in | 303, `already` notice |
| `NotIn(kind, entry_id)` | removing a known one that is not in | 303, `absent` notice |

### Reads (no setting needed: every teacher reads)

```python
def question_page(session, competition_id: int, p: int) -> CompetitionQuestionPage
def question_ids(session, competition_id: int) -> set[int]          # for "Already in this competition"
def get_competition_question(session, competition_id: int, question_id: int) -> CompetitionQuestionView
    # EntryNotFound("question") for an unknown question; NotIn for a known one not in the competition

def team_page(session, competition_id: int, p: int) -> CompetitionTeamPage
def team_ids(session, competition_id: int) -> set[int]
def get_competition_team(session, competition_id: int, team_id: int) -> tuple[TeamRow, str]
    # the row and the region's name; EntryNotFound("team") / NotIn as above

def addable_teams(session, region_id: int, p: int) -> AddableTeamPage
    # live teams of the region's active institutions; the caller checked the region is active
```

The caller has already found the competition with `competitions.get_competition` (12.1), which
checks its subject and visibility. `team_page` and `addable_teams` count active members through
`teams.count_active_members` (R13).

### Writes

```python
def add_question(session, teacher_id: int, competition_id: int, subject_id: int, question_id: int) -> None
def remove_question(session, teacher_id: int, competition_id: int, subject_id: int, question_id: int) -> Landing
def add_team(session, teacher_id: int, competition_id: int, subject_id: int, region_id: int, team_id: int) -> None
def remove_team(session, teacher_id: int, competition_id: int, subject_id: int, team_id: int) -> Landing
```

Each, in order (research R2): the setting with `lock=True` (`ManageRequired`); the competition
`FOR UPDATE` and its subject `FOR SHARE` through `competitions.lock_competition`
(`CompetitionNotFound`); the status with a fresh clock (`NotChangeable`); then:

- **`add_question`**: the question `FOR SHARE`, refreshed; unknown, deleted or of another subject →
  `EntryNotFound("question")`; already copied → `AlreadyIn`; insert the copy of `text` and
  `reference_answer` as read; an `IntegrityError` on commit → `AlreadyIn`.
- **`add_team`**: the team, its institution and its region `FOR SHARE`, refreshed; unknown,
  deleted, of another region than `region_id`, or institution or region deactivated →
  `EntryNotFound("team")`; already linked → `AlreadyIn`; insert the link; an `IntegrityError` →
  `AlreadyIn`.
- **`remove_question`** / **`remove_team`**: the entry must name a known question (team), else
  `EntryNotFound`; not in the competition → `NotIn`. Under the lock, take the entry's index in the
  ordered list (R11, R12), delete the row, and return `Landing` from
  `paging.landing_index(<ids after>, old_index)`.

Every refusal rolls back before it raises.

```python
@dataclass(frozen=True)
class Landing:
    p: int
    entry_id: int | None  # the row to show at its anchor; None for the empty state
```

## `app/services/competitions.py` (changed)

```python
def lock_competition(session, competition_id: int, subject_id: int) -> tuple[Competition, Subject]
```

The 12.1 `_find(…, lock=True)` under a public name: the competition `FOR UPDATE`, then its subject
`FOR SHARE`, both refreshed; `CompetitionNotFound` (after a rollback) for an unknown, mismatched or
invisible one. `update_competition` and `cancel_competition` call it too. The 12.1 `landing` is
re-expressed through `paging.landing_index`. The module docstring's "Contract for later milestones"
names `competition_entries` as the first user of the Upcoming-only rule.

## `app/services/paging.py` (changed)

```python
def landing_index(ids: Sequence[int], kept_id: int | None, old_index: int | None) -> tuple[int, int | None]
```

`(page, id)`: `kept_id` if it is still in `ids`; else the id at `old_index`, else the one before
it; else `(1, None)`. The page is `index // PAGE_SIZE + 1`. Pure; shared by the 12.1 cancellation
landing and the removals here.

## `app/services/teams.py` (changed)

```python
def count_active_members(session, team_ids: Collection[int]) -> dict[int, int]
```

One grouped query over memberships whose class, institution and region are active (the
`list_active_members` chain); a team with none is absent from the result and reads as 0.

`delete_team`: after the reach check and before the commit, deletes the team's
`competition_teams` rows whose competition has `stopped_at IS NULL` (research R5); logs `Team
deleted: id=%d members=%d competitions=%d`. The module docstring's "For milestone 12" paragraph is
replaced: any live team of an active institution in an active region may be added to a competition
by a teacher with **Can manage competitions**, linked to it or not; deleting a team takes it out
of every competition that is not finished.

## `app/services/regions.py` (changed)

```python
def list_active_regions(session) -> list[Region]  # active only, sorted by name_key, then id
```

## `app/services/questions.py` (docstring only)

"Contract for milestone 12" becomes a statement: a competition copies a question when it is added
and keeps the copy whatever happens to the bank row; a deleted question can no longer be added.

## Notices (in the router)

```python
ENTRY_NOTICE_PURPOSE = "competition-entry-notice"
ENTRY_NOTICE_TTL = timedelta(minutes=10)
# payload: {"competition": <id>, "question" | "team": <id>, "outcome": "added" | "already" | "removed" | "absent"}
```

Texts and styles: research R9. A token for another competition, of an unknown outcome, tampered
with or expired shows no notice.

## `app/models/__init__.py` (changed)

Exports `CompetitionQuestion` and `CompetitionTeam`, so `SQLModel.metadata` is complete for Alembic
and the drift test.

## Contract for later milestones

- **Stopping** (a later 12.x): sets `stopped_at`; from then on the competition's questions and teams
  are frozen for good, deleted teams included.
- **Milestone 13**: a student sees a competition when one of their teams is linked to it; the
  questions shown are the copies in `competition_questions`, in their order, never the bank's.
- **Milestones 14–15**: scoring uses the copy's `text` and `reference_answer`; results list every
  linked team, deleted ones marked.
