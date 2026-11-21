# Contract: Services (Milestone 12.8)

Every function takes an open session first; the caller owns it. Decisions:
[research.md](../research.md) R4–R9.

## 1. `app/services/results.py` (new)

The publishing of a competition's results, its snapshot and the stored files.

```python
@dataclass(frozen=True)
class ResultLine:
    institution: str
    team: str
    score: int

@dataclass(frozen=True)
class RegionResults:
    name: str
    lines: tuple[ResultLine, ...]

@dataclass(frozen=True)
class ResultsSnapshot:
    competition_name: str
    subject_name: str
    starts_at: datetime        # UTC
    finished_at: datetime      # UTC, competitions.stopped_at
    published_at: datetime     # UTC, the publishing moment
    regions: tuple[RegionResults, ...]

@dataclass(frozen=True)
class GradingProgress:
    graded: int                # fully graded teams
    total: int                 # all the competition's teams
    @property
    def complete(self) -> bool: ...   # graded == total (True for 0 of 0)

class NotPublishable(ValueError):     # .status: CompetitionStatus
class NotFullyGraded(ValueError):     # .progress: GradingProgress
```

| Function | Contract |
|---|---|
| `build_snapshot(session, competition: Competition, subject: Subject, published_at) -> ResultsSnapshot` | Every team of the competition (`competition_entries.team_entries`: deleted, deactivated included) with its institution, region and score (`grades.grade_counts`, 0 when absent). Regions, institutions and teams ordered by `name_sort_key`, ties by id. Reads nothing else. |
| `publish_results(session, teacher_id, competition_id, subject_id, status_filter) -> Landing` | Order: the setting with `lock=True` (`ManageRequired`) → `lock_competition` (`CompetitionNotFound`) → status with a fresh clock must be `FINISHED` (`NotPublishable(status)`) → `grades.grading_progress` must be complete (`NotFullyGraded`) → snapshot → `render_results_pdf` for `Language.UK` and `Language.EN` → the list before → conditional `UPDATE … SET published_at = now WHERE id AND stopped_at IS NOT NULL AND cancelled_at IS NULL AND published_at IS NULL` (row count 0 → `NotPublishable(reread)`) → two inserts (`IntegrityError` → rollback, `NotPublishable(PUBLISHED)`) → the list after → commit → log `Results published: id=%d teams=%d bytes=%d`. Every refusal rolls back first; nothing is stored then. Returns the landing as `finish_competition` does. |
| `results_file(session, competition_id, language: Language) -> bytes \| None` | The stored content of that row, or `None`. No status check: the caller has found a **Published** competition. |
| `results_file_name(name: str, starts_at: datetime) -> str` | `"<cleaned name> <YYYY-MM-DD>.pdf"`, the date in Kyiv time; cleaning per research R9. |
| `ascii_file_name(file_name: str) -> str` | The `filename=` fallback (research R9). |

**Clock**: `app.services.competitions.utc_now`, read through that module once per call, so the
12.1 test clock moves it.

**Imports run one way**: `results` → `results_pdf`, `grades`, `competitions`,
`competition_entries`. Nothing imports `results` except the routers and the sample script.

## 2. `app/services/results_pdf.py` (new)

```python
def render_results_pdf(snapshot: ResultsSnapshot, language: Language) -> bytes
```

- **Pure**: no session, no request. It is called inside `use_language(language)` by itself, so
  every label is translated, and times use `format_local_time(moment, None)` (Kyiv, labelled).
- **Assets**: `app/static/fonts/OpenSans-Regular.ttf`, `OpenSans-Bold.ttf` and
  `app/static/img/logo/logo-dark-192.png`, read from paths relative to the package. They are loaded
  once per call; fpdf2 caches nothing between calls.
- **Output**: a complete PDF, layout per research R8 and
  [results-file.md](./results-file.md). The output is deterministic for a given snapshot and
  language: the creation date is set to `published_at` and nothing reads the wall clock.

## 3. `app/services/grades.py` (changed)

| Change | Contract |
|---|---|
| `grading_progress(session, competition_id) -> GradingProgress` (new) | Fully graded teams of all the competition's teams, counted as the Grades page counts them. `grade_team_page` uses it for `teams_graded` / `teams_total`. |
| `save_grades` | Unchanged code; the docstring states that a `PUBLISHED` competition raises `GradingClosed(PUBLISHED)` under the share lock, which publishing's `FOR UPDATE` excludes. |

## 4. `app/services/competitions.py` (changed)

| Change | Contract |
|---|---|
| `CompetitionStatus.PUBLISHED` | Declared after `FINISHED`; label `_("Published")`. |
| `CompetitionStatus.has_finished` | `self in (FINISHED, PUBLISHED)`. |
| `status_of` | `published_at` checked after `cancelled_at`, before `stopped_at`. |
| `cancel_competition` | Refuses `PUBLISHED` with `NotCancellable(PUBLISHED)`. |
| Module docstring | The contract for later milestones gains publishing: `published_at` is written once by `results.publish_results`; milestone 13 must not grade a `PUBLISHED` competition; milestone 14 shows results only for `PUBLISHED`. |

**Call-site checklist** (research R4): every use of `CompetitionStatus.FINISHED` and `"finished"`
in `app/` is reviewed. Those meaning "has ended" switch to `has_finished`; those meaning "grades may
still change" stay. `tests/integration/test_competition_service.py` asserts the enum order, the
labels and `has_finished`.

## 5. `app/models/competition.py` (changed)

- `Competition.published_at: datetime | None` and the `published_after_finish` constraint.
- `CompetitionResultsFile` (new table), per [data-model.md](../data-model.md) §2.
- The docstrings of `Competition` and `TeamAnswer` name the new writer and the frozen grades.
