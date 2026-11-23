# Services: Additional Questions (Milestone 12.9)

Changed signatures and behaviour. Every function keeps taking an open session first; the caller
owns it. Decisions: [research.md](../research.md) R3, R5, R6.

## `app/services/questions.py`

### `QuestionView` (changed)

Gains `is_additional: bool` (see [data-model.md](../data-model.md) §2). `_view` fills it from the
row.

### `question_page(session, subject_id, page, *, include_additional: bool) -> QuestionPage` (changed)

- `include_additional` is **required, keyword-only, and has no default**.
- With `True`, the result is exactly as in milestone 11: the subject's listed questions (not
  deleted), newest first, `PAGE_SIZE` per page, the page clamped to 1..last.
- With `False`, the condition `col(Question.is_additional).is_(False)` is added to the count *and*
  the page query. The total, the clamping and the rows then cover only the questions that are not
  additional; an all-additional subject gives an empty page with `total == 0`.
- Callers:
  - `teacher_questions.questions_page`: `include_additional=_can_manage(request, session)`;
  - `teacher_competition_entries.add_questions_page`: `include_additional=True` (after
    `require_manage`).

### `create_question(session, teacher_id, subject_id, text, reference_answer, *, is_additional: bool = False) -> QuestionView` (changed)

Stores the mark with the question. The checks are unchanged: the setting under lock, then the
subject `FOR SHARE`, so `ManageRequired` or `SubjectUnavailable` stores nothing. The log line is
unchanged and carries ids only.

### `update_question(session, teacher_id, question_id, text, reference_answer, *, is_additional: bool) -> QuestionView` (changed)

- `is_additional` is **required, keyword-only**, so an edit never clears the mark by omission.
- The checks are unchanged: the setting under lock, then the question `FOR UPDATE` and its subject
  `FOR SHARE`. A deleted question, or one of a deactivated subject, raises `QuestionNotFound`, and
  the mark is not written (FR-005).
- `changed` compares `(text, reference_answer, is_additional)`. When anything differs, all three are
  written and `updated_at` is reset; "Question updated: id=%d" is logged as before.

### `get_question`, `get_active_subject`, `delete_question` (unchanged)

`get_question` returns the view with the mark, for the edit form; only teachers with the setting
reach it. `delete_question` sets `deleted_at` only. The deletion landing (011 R8) counts every
listed question, additional ones included: only teachers with the setting delete, and they see all
of them.

## `app/services/competition_entries.py`

### `CompetitionQuestionView` (changed)

Gains `is_additional: bool | None`: the bank's current mark, or `None` when it was not read.

### `question_page(session, competition_id, p, *, with_bank_mark: bool) -> CompetitionQuestionPage` (changed)

- `with_bank_mark` is **required, keyword-only**.
- With `True`, the statement selects `CompetitionQuestion, Question.deleted_at,
  Question.is_additional` through the existing join, and `is_additional` is filled.
- With `False`, it selects `CompetitionQuestion, Question.deleted_at` as in 12.2, and
  `is_additional` is `None`.
- The order, the paging and the copies' texts are unchanged.
- Caller: `teacher_competition_entries.competition_questions_page`, with
  `with_bank_mark=can_manage(request, session)`.

### `get_competition_question` (changed, trivially)

Fills `is_additional=None`; the remove confirmation shows no mark.

### `add_question`, `remove_question`, `question_copies`, `question_ids` (unchanged)

`add_question` copies text and reference answer only. No copy of the mark is taken (FR-022), so
changing a mark later changes nothing in any competition (FR-023).

## `app/routers/teacher_questions.py` (thin, changed)

- `create_question_action` and `update_question_action` gain `additional: str | None = Form(None)`
  and compute `marked = bool(additional)`.
- On a 400, they put `"additional": marked` into `values`.
- `new_question_page` puts `"additional": False`, and `edit_question_page` puts
  `"additional": question.is_additional`.
- `_form` passes the values unchanged to `question_form.html`, which renders
  `checkbox_field("additional", _("Additional question"), checked=values.additional, value="1",
  hint=…)` after the reference answer.
- The module docstring changes: "Every teacher reads the bank" becomes "every teacher reads the
  questions that are not additional; only a teacher with the setting sees the additional ones and
  changes the bank".

## `app/routers/teacher_competition_entries.py` (thin, changed)

- `competition_questions_page` passes `with_bank_mark=can_manage(request, session)`. `can_manage`
  is already computed for `can_change`, so it is read once and reused.
- `add_questions_page` passes `include_additional=True`.

## Seeders (`tests/conftest.py`)

`make_question(engine, subject_id, text=…, reference_answer=…, *, deleted=False, additional=False)`
stores `is_additional=additional`.
