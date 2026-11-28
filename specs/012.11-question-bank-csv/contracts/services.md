# Contract: Services (Milestone 12.11)

The imports run one way: the router imports `question_bank_files`, `question_csv`, `uploads`
and `downloads`; `question_bank_files` imports `question_csv`, `file_names`, `competitions`
(for the clock) and `subjects`; `question_csv` imports only `app.schemas.question` and
`app.core.i18n`.

## 1. `app/services/question_csv.py` (pure)

```python
HEADER: tuple[str, str, str]          # ("question", "answer", "additional")
MAX_FILE_BYTES: int                   # 2 * 1024 * 1024
MAX_QUESTIONS: int                    # 1000
ERRORS_SHOWN: int                     # 20

@dataclass(frozen=True)
class QuestionRow: text: str; reference_answer: str; is_additional: bool

@dataclass(frozen=True)
class QuestionFileError: row: int | None; message: Text

@dataclass(frozen=True)
class QuestionFileCheck:
    rows: tuple[QuestionRow, ...]
    errors: tuple[QuestionFileError, ...]
    ok, file_error, row_errors, more    # properties, data-model.md §2

class UnclosedQuote(ValueError): row: int

def write_question_csv(rows: Iterable[QuestionRow]) -> bytes
def parse_records(text: str, separator: str) -> Iterator[tuple[int, list[str]]]   # raises UnclosedQuote
def check_question_file(data: bytes | None, *, too_large: bool = False) -> QuestionFileCheck
```

- `check_question_file` runs the checks of [csv-format.md](./csv-format.md) §3 in order.
  `too_large=True`, from the upload, is check 2 without the bytes.
- It never raises for any input, and its messages are lazy `Text`, translated when rendered.
- Nothing in this module logs.

## 2. `app/services/question_bank_files.py`

```python
@dataclass(frozen=True)
class Replaced: deleted: int; added: int

def question_counts(session) -> dict[int, int]
    # subject_id -> listed questions (deleted_at IS NULL), additional included; one GROUP BY

def export_rows(session, subject_id: int) -> list[QuestionRow]
    # listed questions of the subject, id ascending; the caller has found the subject

def export_file_name(subject_name: str, today: date) -> str
    # "<clean stem> <YYYY-MM-DD> <_('question bank')>.csv"; fallback stem _("Subject")

def today_in_kyiv() -> date
    # competitions.utc_now() in KYIV

def lock_question_bank(session) -> None
    # PostgreSQL: LOCK TABLE questions IN EXCLUSIVE MODE; SQLite: nothing (research R6)

def replace_questions(session, subject_id: int, rows: Sequence[QuestionRow]) -> Replaced
    # research R5: subject FOR SHARE (SubjectNotFound after rollback), lock, soft-delete UPDATE,
    # one INSERT in file order, commit, one log line. `rows` is 1..MAX_QUESTIONS long (asserted).
```

- **Authorization**: none here, as in `subjects.py`. The router is `@allow_roles(Role.ADMIN)`,
  and a later caller must put its own role check in front.
- **The log line**: `Questions imported: subject=%d deleted=%d added=%d`, the only one this
  milestone adds. It has no text, email or name.

## 3. `app/routers/uploads.py`

```python
@dataclass(frozen=True)
class Upload: data: bytes | None; too_large: bool

def uploaded_file(field: str = "file", max_bytes: int = MAX_FILE_BYTES)
    -> Callable[[Request], Coroutine[Any, Any, Upload]]
UploadedCsv = Annotated[Upload, Depends(uploaded_file())]
```

This is research R7. It is never used as a `File(...)` parameter, so it is solved after
`resolve_access`.

## 4. `app/routers/downloads.py`

```python
def csv_download(content: bytes, file_name: str) -> Response   # text/csv; charset=utf-8
def pdf_download(content: bytes, file_name: str) -> Response   # unchanged behaviour
```

Both share one private `_attachment`, and the PDF headers stay exactly as they are (the 12.8 and
12.10 tests).

## 5. Unchanged services

`questions.py` (the teacher's writes now wait for an import on PostgreSQL, with no code change),
`question_files.py` (the study materials cache sees the new bank by comparison), `subjects.py`
and `competition_entries.py`.
