# Contract: Services and Helpers

Python interfaces the routes and later milestones rely on. Every service function takes an open
session first; the caller owns it. Decisions are in [research.md](../research.md).

## `app/services/competitions.py` (new)

The clock is the module-level `utc_now` (imported from `app.core.db`), read once per call; tests
replace it with `monkeypatch.setattr("app.services.competitions.utc_now", …)`. Each successful
change logs one line with ids only: `Competition created: id=%d subject=%d`, `Competition updated:
id=%d`, `Competition cancelled: id=%d`. No name is ever logged (FR-046).

### Types

```python
class CompetitionStatus(StrEnum):
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str: ...  # "Upcoming", "In progress", "Finished", "Cancelled"


def parse_status_filter(raw: str | None) -> CompetitionStatus | None:
    """A status from the address; anything else is None, meaning All."""


@dataclass(frozen=True)
class CompetitionView:
    id: int
    subject_id: int
    name: str
    starts_at: datetime  # UTC
    status: CompetitionStatus


@dataclass(frozen=True)
class CompetitionPage:
    competitions: list[CompetitionView]  # one page, sorted
    paging: Paging
    subject_total: int  # visible competitions of the subject, any status


@dataclass(frozen=True)
class SubjectChoices:
    active: list[Subject]  # sorted by name_key, then id
    deactivated: list[Subject]  # deactivated, with a finished competition; same order

    def is_offered(self, subject_id: int) -> bool: ...
    def get(self, subject_id: int) -> Subject | None: ...
    @property
    def only(self) -> Subject | None: ...  # the single offered subject, if exactly one


@dataclass(frozen=True)
class Landing:
    page: int
    competition_id: int | None  # the row to show at its anchor; None for the empty state
```

### Errors

| Exception | Meaning | Route answer |
|---|---|---|
| `ManageRequired` | the teacher lacks **Can manage competitions** | 403 |
| `SubjectUnavailable` | the subject is not offered, or not active where a new competition is made | 404 "Subject not found" |
| `CompetitionNotFound` | unknown, of another subject, or invisible | 404 "Competition not found" |
| `NotEditable(status)` | the competition is not Upcoming | 409, the edit refusal for `status` |
| `NotCancellable(status)` | already Cancelled, or Finished | 409, the cancel refusal for `status` |
| `StartNotInFuture` | the start is not later than now | 400, "The start must be in the future." |
| `InvalidName` (from `app.schemas.names`) | the name breaks a rule | 400, its message |
| `DuplicateCompetitionName(entered)` | a live competition of the subject has the name | 400, "A competition named “…” already exists in this subject." |

### Pure functions

```python
def status_of(row: Competition, now: datetime) -> CompetitionStatus
def sort_key(view: CompetitionView) -> tuple   # (-starts_at timestamp, name_key, id)
def landing(rows: Sequence[CompetitionView], competition_id: int, old_index: int | None) -> Landing
```

`landing`: if `competition_id` is in `rows`, its index; else the row at `old_index`, else the row
at `old_index - 1`, else `Landing(1, None)`. The page is `index // PAGE_SIZE + 1`.

### Reads (no setting needed: every teacher reads)

```python
def offered_subjects(session) -> SubjectChoices
def competition_page(session, subject: Subject, status: CompetitionStatus | None, page: int) -> CompetitionPage
def get_competition(session, competition_id: int, subject_id: int) -> CompetitionView
def locate(session, subject: Subject, status: CompetitionStatus | None, competition_id: int, old_index: int | None = None) -> Landing
```

- `competition_page` lists the subject's visible competitions (all of them for an active subject,
  only finished ones for a deactivated subject), derives each status with one `now`, keeps those
  matching `status`, sorts with `sort_key` and slices with `Paging.build(page, total)`.
- `get_competition` raises `CompetitionNotFound` for an unknown id, a competition of another
  subject or an invisible one; it never says which.
- `locate` gives the landing for the list after a change.

### Writes

```python
def create_competition(session, teacher_id: int, subject_id: int, raw_name: str, starts_at: datetime) -> CompetitionView
def update_competition(session, teacher_id: int, competition_id: int, subject_id: int, raw_name: str, starts_at: datetime) -> CompetitionView
def cancel_competition(session, teacher_id: int, competition_id: int, subject_id: int, status: CompetitionStatus | None) -> Landing
```

Each, in order (research R8): the setting with `lock=True`; the subject `FOR SHARE` (create: must
be active); the row `FOR UPDATE` (update, cancel: must belong to `subject_id` and be visible); the
status with a fresh `now`; then the change. Every refusal rolls back first.

- **create**: `StartNotInFuture` unless `starts_at > now`; the name cleaned and looked up among
  live competitions of the subject; insert; an `IntegrityError` on commit is
  `DuplicateCompetitionName`.
- **update**: `NotEditable(status)` unless Upcoming; `StartNotInFuture`; the name looked up,
  ignoring the competition itself; nothing changed → no write; else a conditional `UPDATE … WHERE
  id = :id AND cancelled_at IS NULL AND stopped_at IS NULL AND starts_at > :now`. A row count of 0
  re-reads the row and raises `NotEditable` with its current status. An `IntegrityError` is
  `DuplicateCompetitionName`.
- **cancel**: `NotCancellable(status)` for Cancelled or Finished. Under the lock it takes the
  competition's index in the list filtered by `status` (the request's filter) before the change,
  makes the conditional `UPDATE … SET cancelled_at = :now WHERE id = :id AND cancelled_at IS NULL
  AND stopped_at IS NULL`, and returns `landing(<the filtered list after the change>,
  competition_id, old_index)` (research R13), as `delete_question` returns its landing. A row count
  of 0 re-reads the row and raises `NotCancellable` with its current status.

After a create or an update, the router calls `locate(session, subject, status, competition_id)`
for the landing (status **All** after a create).

### Contract for later milestones

- **Stopping** (a later 12.x) writes `stopped_at` with a conditional update on
  `cancelled_at IS NULL AND stopped_at IS NULL AND starts_at <= :now`, and adds **Stop
  competition** to the actions menu.
- **Questions and teams of a competition** (later 12.x) may be changed only while `status_of` is
  Upcoming, with the same lock and conditional-update pattern.
- **Students** (milestone 13) may read questions and answer only while `status_of` is In progress
  and the competition is visible.

## `app/schemas/competition.py` (new, pure)

```python
@dataclass(frozen=True)
class StartErrors:
    date: str | None
    time: str | None

def parse_start(raw_date: str, raw_time: str, zone: ZoneInfo) -> datetime | StartErrors
def local_parts(moment: datetime, zone: ZoneInfo) -> tuple[str, str]   # ("2027-03-14", "10:00") for the edit form
def gap_message(local: datetime, zone_name: str) -> str
```

Rules and messages: [data-model.md](../data-model.md) §6, research R6.

## `app/core/time_zone.py` (new)

```python
TIME_ZONE_COOKIE_NAME = "sc_time_zone"
TIME_ZONE_MAX_LENGTH = 64
UTC_ZONE: ZoneInfo        # ZoneInfo("UTC")

def parse_time_zone(value: str | None) -> ZoneInfo | None   # only names in available_timezones()
def read_time_zone(request: Request) -> ZoneInfo | None     # never raises
def zone_name(zone: ZoneInfo | None) -> str                 # the key, or "UTC"
def format_local_time(moment: datetime, zone: ZoneInfo | None) -> str
    # "14 March 2027, 10:00"; with None: "14 March 2027, 08:00 UTC"
def utc_iso(moment: datetime) -> str                        # "2027-03-14T08:00Z"
```

`format_local_time` and `utc_iso` are registered as Jinja globals; a context processor adds
`time_zone` (`read_time_zone(request)`) to every template.

## `app/services/subjects.py` (changed)

`count_subject_uses` adds `SELECT count(*) FROM competitions WHERE subject_id = :id` to the question
count. The docstring's "competitions add theirs in milestone 12" becomes a statement.

## Notices (in the router)

```python
COMPETITION_NOTICE_PURPOSE = "competition-notice"
COMPETITION_NOTICE_TTL = timedelta(minutes=10)
# payload: {"competition": <id>, "outcome": "added" | "saved" | "cancelled"}
```

`seal` and `unseal` come from `app.core.sealing`. A token that is tampered with, expired, of an
unknown outcome, or for a competition that is not visible in the listed subject shows no notice and
is not an error. The texts are "Competition “<name>” was added", "… was saved", "… was cancelled",
with the name read when the list is shown.

## `app/models/__init__.py` (changed)

Exports `Competition`, so `SQLModel.metadata` is complete for Alembic and the drift test.
