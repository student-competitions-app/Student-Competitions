# Services: Milestone 12.10

The imports run one way:

```text
routers.teacher_question_files → services.question_files → services.question_files_pdf → services.pdf_layout
                                                          → services.file_names
services.results → services.results_pdf → services.pdf_layout
                 → services.file_names
```

## 1. `app/services/pdf_layout.py` (new; taken from `results_pdf.py`)

This module holds the design shared by the three PDF files. It has no database, no request and no
clock.

- **Constants**: the fonts and family, the logo, `MARGIN`, `LOGO_HEIGHT`, the colours (`INK`,
  `MUTED`, `RULE`, `HEADING_FILL`), the sizes and leadings, `PRODUCER`, `PDF_LANGUAGE`.
- **`class PdfDocument(FPDF)`**: A4, a running title on every page after the first, and "Page n
  of N" in the footer. This is the 12.8 `_ResultsDocument` renamed.
- **`open_document(title: str, language: Language, created_at: datetime) -> PdfDocument`**: sets
  the margins, the auto page break, the fonts, `alias_nb_pages`, the metadata, and adds the first
  page. It is called inside `use_language(language)`.
- **`draw_header(document, title: str, subject: str, meta: Sequence[str]) -> None`**: draws the
  logo, the title, the subject and the muted meta lines, exactly as 12.8 does.

**Contract**: `render_results_pdf` refactored onto these functions gives byte-identical output.
Running `scripts/make_results_samples.py` leaves `specs/012.8-publishing-results/samples/`
unchanged.

## 2. `app/services/question_files_pdf.py` (new)

```python
def render_questions_pdf(sheet: QuestionsSheet, language: Language) -> bytes: ...
def render_study_materials_pdf(materials: StudyMaterials, language: Language) -> bytes: ...
```

- **Pure functions**: the same input and language always give the same bytes.
- **Content**: as specified in [files.md](./files.md).
- **Only inputs**: the dataclasses of [data-model.md](../data-model.md) §3–§4.

## 3. `app/services/question_files.py` (new)

### Reading

```python
def questions_sheet(session: Session, competition: CompetitionView, subject: Subject) -> QuestionsSheet
def study_materials(session: Session, subject: Subject) -> StudyMaterials
```

- **`questions_sheet`**: the competition's copies (`competition_entries.question_copies`), every
  one, in order, texts only, and the subject's current name. The caller has already checked the
  status.
- **`study_materials`**: one query (data-model §2) and the Kyiv date of
  `competitions.utc_now()`. The caller has already checked that the subject is active.

### File names

```python
def questions_file_name(sheet: QuestionsSheet, language: Language) -> str
def study_materials_file_name(materials: StudyMaterials, language: Language) -> str
```

Each is a whole message in `language` (research R7), built on `file_names.clean_file_stem`, plus
`.pdf`.

### `StudyMaterialsCache`

```python
class StudyMaterialsCache:
    def file_for(self, subject_id: int, language: Language, materials: StudyMaterials) -> bytes: ...
```

Under the lock of `(subject_id, language)`:

1. If an entry is kept and `entry.materials == materials`, return `entry.content`.
2. Otherwise call `question_files_pdf.render_study_materials_pdf(materials, language)`, looked up
   through the module so tests can count the calls. Store `Kept(materials, content)` in place of
   any entry, and return `content`.

**Guarantees** (data-model §5):

- **Never stale**: the bytes returned always render exactly the `materials` passed in.
- **Single-flight**: concurrent calls with equal materials render once.
- **Bounded**: one entry per key.
- **Thread-safe**: for the uvicorn thread pool.
- **Quiet**: no logging.

`lifespan` (`app/main.py`) sets `app.state.study_materials = StudyMaterialsCache()` before
`yield`.

## 4. `app/services/file_names.py` (new; taken from `results.py`)

```python
def clean_file_stem(text: str, fallback: str) -> str   # the 12.8 rule: / \ : * ? " < > | and control chars → "_", ends stripped, trailing dots removed; empty → fallback
def ascii_file_name(file_name: str) -> str              # moved unchanged
```

`results_file_name` keeps its output and uses `clean_file_stem(name, "results")`.

## 5. `app/routers/downloads.py` (new; taken from `teacher_results.py`)

```python
def pdf_download(content: bytes, file_name: str) -> Response
```

It returns the response with the headers of [http-routes.md](./http-routes.md) §2. **Download
results**, **Download questions** and **Download study materials** all use it.

## 6. `app/routers/teacher_question_files.py` (new)

Thin handlers, each following the order of checks in [http-routes.md](./http-routes.md) §2 and
§3.

- **`download_questions`**: looks up the subject and the competition and checks the status. It
  then calls `questions_sheet`, renders the file in `request.state.language` and returns
  `pdf_download`.
- **`download_study_materials`**: parses the subject id and calls `questions.get_active_subject`;
  on `SubjectUnavailable` it answers 404. It then reads `study_materials` and calls
  `request.app.state.study_materials.file_for(...)`, then `pdf_download`.

## 7. Changed: `teacher_competition_entries.competition_questions_page`

`require_manage(request, session)` becomes the first statement, and `with_bank_mark=True`. The
module docstring's "Every teacher reads both lists" changes to "every teacher reads the teams; only
a teacher with the setting opens the questions (milestone 12.10)".
