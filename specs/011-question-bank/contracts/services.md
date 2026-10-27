# Contract: services and schemas (Milestone 11)

**Conventions**, as in milestones 6–9:

- **Sessions**: every function takes an open `Session` first, and the caller owns it.
- **Writes**: each write is one committed unit of work, rolled back on refusal before the error is
  raised.
- **Logging**: one log line per successful change, ids only.

Decisions: [research.md](../research.md) R1, R2, R4, R5, R7–R9, R12, R16.

## `app/schemas/question.py` (rewritten)

```python
QUESTION_FIELD_MAX_LENGTH = 2000  # also both column lengths


class InvalidQuestionField(ValueError):
    message: str  # ready to show beside the field


def clean_question_field(raw: str, field: Literal["text", "reference_answer"]) -> str:
    """CR/CRLF → LF; NUL refused; strip; 1..2000 code points. Returns the clean value."""


def question_field_errors(text: str, reference_answer: str) -> tuple[dict[str, str], str, str]:
    """Both fields checked: (errors by field id, clean text, clean answer)."""
```

**Messages**:

| Field | Empty or only whitespace | Too long | NUL |
|---|---|---|---|
| `text` | Enter the question text. | The question text can be at most 2,000 characters. | The question text cannot contain a null character. |
| `reference_answer` | Enter the reference answer. | The reference answer can be at most 2,000 characters. | The reference answer cannot contain a null character. |

**Removed**: `QuestionCreate`, `QuestionUpdate`, `QuestionPublic`, `QUESTION_TEXT_MAX_LENGTH` and
`REFERENCE_ANSWER_MAX_LENGTH`.

## `app/services/paging.py` (new, pure)

```python
PAGE_SIZE = 10
MAX_PAGE = 999_999_999


def parse_page(raw: str | None) -> int:
    """1 for missing, empty, non-ASCII-digit or 0; MAX_PAGE for more than 9 digits; else int."""


@dataclass(frozen=True)
class PageLink:
    number: int | None  # None = a gap
    current: bool


@dataclass(frozen=True)
class Paging:
    number: int  # the current page, 1..last
    last: int  # >= 1
    total: int  # items in the whole list
    size: int
    first_item: int  # 1-based; 0 when total == 0
    last_item: int
    previous: int | None
    next: int | None
    links: tuple[PageLink, ...]  # first, last, current ±1, gaps for runs of >= 2 (R9)
    offset: int  # (number - 1) * size

    @classmethod
    def build(cls, page: int, total: int, size: int = PAGE_SIZE) -> "Paging": ...
```

## `app/services/teacher_access.py` (added)

```python
def can_manage_competitions(session: Session, teacher_id: int, *, lock: bool = False) -> bool:
    """True only if the teacher has a profile row with `can_manage_competitions`. With `lock`,
    the row is read FOR SHARE with populate_existing (R5, R7)."""
```

## `app/services/subjects.py` (changed)

```python
def list_active_subjects(session: Session) -> list[Subject]:
    """Active subjects, sorted like list_subjects (name_key, then id)."""


def count_subject_uses(session: Session, subject_id: int) -> int:
    """Number of question rows of the subject, deleted ones included (FR-040)."""
```

The module docstring's note "milestones 9 and 10 add references" is updated: questions now count,
and competitions will add theirs in milestone 12.

## `app/services/questions.py` (rewritten)

```python
class SubjectUnavailable(LookupError):
    """Unknown or deactivated subject: "Subject not found" (404)."""


class QuestionNotFound(LookupError):
    """Unknown, deleted, or of a deactivated subject: "Question not found" (404)."""


class ManageRequired(PermissionError):
    """The teacher lacks Can manage competitions (403)."""


@dataclass(frozen=True)
class QuestionView:
    id: int  # also the number shown
    subject_id: int
    text: str
    reference_answer: str


@dataclass(frozen=True)
class QuestionPage:
    questions: list[QuestionView]  # newest first (id DESC), at most PAGE_SIZE
    paging: Paging


@dataclass(frozen=True)
class Landing:
    page: int
    question_id: int | None  # None: the subject has no listed question left


def get_active_subject(session: Session, subject_id: int, *, lock: bool = False) -> Subject:
    """The subject if it exists and is active; SubjectUnavailable otherwise."""


def question_page(session: Session, subject_id: int, page: int) -> QuestionPage:
    """One page of the subject's listed questions (deleted_at IS NULL), page clamped to 1..last.
    The caller has already checked that the subject is active."""


def get_question(
    session: Session, question_id: int, *, lock: bool = False
) -> tuple[QuestionView, Subject]:
    """A question that exists, is not deleted, and whose subject is active; QuestionNotFound
    otherwise. With `lock`, the question row is read FOR UPDATE and the subject FOR SHARE."""


def create_question(
    session: Session, teacher_id: int, subject_id: int, text: str, reference_answer: str
) -> QuestionView:
    """Values already cleaned. In one transaction: setting (lock) → ManageRequired; subject active
    (lock) → SubjectUnavailable; insert with created_at = updated_at = now."""


def update_question(
    session: Session, teacher_id: int, question_id: int, text: str, reference_answer: str
) -> QuestionView:
    """Values already cleaned. Setting (lock); question (lock) → QuestionNotFound; set both fields;
    updated_at = now only if something changed. Subject never touched."""


def delete_question(session: Session, teacher_id: int, question_id: int) -> Landing:
    """Setting (lock); question (lock) → QuestionNotFound; compute index i among listed questions
    of its subject; set deleted_at = now (nothing else); then the landing: the next question
    (largest listed id < q.id), else the previous one (smallest listed id > q.id), else none;
    page = target_index // PAGE_SIZE + 1 (R8)."""
```

**Retired**: the milestone 3 functions `list_questions` (all questions, for the home page) and the
unscoped `create_question`, `update_question` and `delete_question`. The hard delete goes too.

**Contract for milestone 12** (recorded here, enforced there): a question may be added to a new
competition only if `deleted_at IS NULL` and it belongs to the competition's subject. `get_question`
already gives the first rule.

**Logging**: `Question created: id=%d subject=%d`, `Question updated: id=%d` and
`Question deleted: id=%d`.

## `app/services/teachers.py` and `app/schemas/teachers.py` (renamed setting)

- **The setting is renamed**:
  - `TeacherDetails.can_create_competitions` becomes `can_manage_competitions`;
  - `TeacherView`'s field and the `update_teacher(..., can_manage_competitions)` parameter follow.
- **`_TeacherInvitation.details_to_payload`** writes the key `can_manage_competitions`.
- **`_TeacherInvitation.details_from_payload`** accepts exactly one of these key sets:
  - `{"institutions", "can_manage_competitions"}`;
  - `{"institutions", "can_create_competitions"}`, the legacy set from milestone 8 (R12).

  Any other set raises `ValueError`, as today.
- **`describe`** gives the detail lines:
  - "Can manage competitions: Yes", explained as "You will be able to manage competitions and change
    the question bank.";
  - "Can manage competitions: No", explained as "You will not be able to manage competitions or
    change the question bank.".

## `app/routers/pages.py`

`home` no longer imports `list_questions` or `QuestionPublic`. The `try` block reads
`read_database_status` only. The error branch, its log line and its notice are unchanged.
