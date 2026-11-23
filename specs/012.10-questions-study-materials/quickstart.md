# Quickstart: Milestone 12.10

How to see and check the milestone once it is implemented. The details live in
[contracts/](./contracts/) and [data-model.md](./data-model.md); this guide only runs them.

## 1. Prerequisites

- `uv sync` (no new dependency).
- The catalogues compiled: `scripts/translations.sh compile` (the tests compile them
  themselves).
- For both engines, the local PostgreSQL container running and `TEST_POSTGRES_URL` set (see the
  README's testing section).

## 2. Automated checks

```sh
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_question_files_pdf.py tests/unit/test_study_materials_cache.py
uv run pytest tests/integration/test_teacher_question_files.py \
              tests/integration/test_teacher_competition_entries.py \
              tests/integration/test_teacher_competitions.py \
              tests/integration/test_routes.py tests/integration/test_component_gallery.py
uv run pytest            # the whole suite, both engines when TEST_POSTGRES_URL is set
```

Expected: all green. The new modules cover the scenarios of User Stories 1–6. The milestone's
_Test:_ line is mapped in research R10.

**The 12.8 results file is unchanged by the refactor**:

```sh
uv run python scripts/make_results_samples.py
git status --short specs/012.8-publishing-results/samples/   # expected: no output
```

## 3. By hand in the running application

Run `uv run uvicorn app.main:app --reload`, then sign in as a teacher with **Can manage
competitions** and as one without it. You need a subject with:

- ordinary, additional and deleted questions;
- an **Upcoming**, an **In progress** and a **Published** competition.

| Step | Expected |
|---|---|
| Open the actions menu of each competition as each teacher | **Questions** only for the manager; **Download questions** on **In progress** and **Published** only, for both; the order of FR-010 |
| As the teacher without the setting, type `/teacher/competitions/<id>/questions` for any id, and for `999999` | the same "access denied" page every time |
| Choose **Download questions** | the browser saves "<name> <date> questions.pdf" (or «… питання.pdf»); no loading bar; the list stays as it was |
| Open the file | the header holds only the title, the subject and "Started: … (Kyiv time)"; the questions are numbered from 1; there are no answers, no "Question 58" and no mark |
| Type the download address of the **Upcoming** competition | 404 "Competition not found" |
| Choose a subject on the Competitions tab | **Download study materials** appears beside the lists; it is not shown before a choice or for a deactivated subject |
| Download the study materials as the manager | no additional or deleted question in the file, and no bank numbers; "Answer: …" under each question |
| Download again, then edit a reference answer and download again | the second download is instant; the third shows the edit |
| Switch the language and download both files | the labels and the file names are in Ukrainian or English; the texts are unchanged |
| Repeat on a phone-width window (360 px), with JavaScript off | the link stacks under the lists, with no sideways scrolling; the downloads still work |

## 4. Design review material

```sh
uv run python scripts/make_question_file_samples.py   # writes specs/012.10-…/samples/*.pdf
```

For the screenshots of the link, use the project's headless Playwright routine against a copy of
the development database: `uv run --with playwright`, port 8765. Take the Competitions tab with a
subject chosen, at desktop width and at 360 px, in Ukrainian and English, light and dark.

Record each round, its samples and screenshots, the decision and the measured render time of the
150-question sample in `design-approval.md`. The milestone is delivered only after the product
owner approves both files and the link (FR-049).
