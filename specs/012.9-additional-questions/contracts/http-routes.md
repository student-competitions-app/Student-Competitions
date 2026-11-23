# HTTP Routes: Additional Questions (Milestone 12.9)

No route is added or removed. This contract lists the routes whose behaviour changes and the ones
whose behaviour is now checked for additional questions. Every route stays
`@allow_roles(Role.TEACHER)`; administrators and students get the milestone 5 "access denied" page
(403) from each, as before (FR-018).

## Order of checks (unchanged)

The checks run in the 011 / 012.2 order:

1. the role (`@allow_roles`);
2. on a manage route, **Can manage competitions**, first thing in the handler, before any id is
   parsed or looked up;
3. the subject, competition and question ids ("not found", 404);
4. the competition's status, where it matters (012.2);
5. the fields (400);
6. the service write, which checks the setting and the ids again under lock.

A teacher without the setting therefore gets the same 403 page for an additional question, an
ordinary one, a deleted one, a question of a deactivated subject and a number that does not exist
(FR-020).

## The question bank (`app/routers/teacher_questions.py`)

### `GET /teacher/questions?subject=<id>&page=<n>`: the list (changed)

- **With the setting**: every listed question of the subject, as in milestone 11. Each additional
  question's card heading reads "Question 58" followed by the badge **Additional**
  (`text_card(..., badge=additional_badge())`).
- **Without it**: `question_page(..., include_additional=False)`. The rows, the total in "Questions
  1–10 of 20", the number of pages, and the clamping of a page past the end count only the questions
  that are not additional.
  - A subject with listed questions that are all additional shows the empty state "No questions
    yet" with no hint.
  - The response body holds no text, reference answer, number, badge or element of an additional
    question.
- 200, as before. Opening it changes nothing.

### `GET /teacher/questions/new?subject=<id>&page=<n>[&saved=1]`: the add form (changed)

- **Setting**: required, checked first.
- **Form**: below the reference answer, the checkbox
  `<input type="checkbox" id="additional" name="additional" value="1">` labelled **Additional
  question**, with the hint "Additional questions and their answers are not given to participants
  before a competition." (`aria-describedby`). It opens **unchecked**, also with `saved=1`.

### `POST /teacher/questions`: add (changed)

- **Fields read**: `subject`, `page`, `text`, `reference_answer`, `then`, and **`additional`** (new;
  a plain string, `None` when absent).
- **Marked**: when `additional` is a non-empty string. An absent or empty value means not
  additional. No value ever produces a 422.
- **Invalid fields (400)**: the form again with the errors, the values as typed, and the checkbox
  **as sent**. Nothing is stored.
- **Success**: `create_question(..., is_additional=<marked>)`, then the 303 of milestone 11:
  - `then=another` → `/teacher/questions/new?subject=…&page=…&saved=1`, whose form opens unchecked;
  - otherwise → the subject's first page.
- **Without the setting**: 403 before anything else, and nothing is stored.

### `GET /teacher/questions/{id}/edit?page=<n>`: the edit form (changed)

- **Setting** first, then "Question not found" (404) for an unknown or deleted question, or one of
  a deactivated subject.
- **Form**: the same checkbox, **checked when the stored question is additional**, unchecked
  otherwise. No badge on the page.

### `POST /teacher/questions/{id}/edit`: save (changed)

- **Fields read**: `page`, `text`, `reference_answer` and **`additional`** (as on add). A `subject`
  field is still ignored.
- **Invalid fields (400)**: the form again with the checkbox as sent. Nothing changes.
- **Success**: `update_question(..., is_additional=<marked>)`. Unchecking stores "not additional".
  Then the 303 back to the page and question, as before.
- **A deleted question, or one of a deactivated subject**: "Question not found" (404). Its mark is
  unchanged (FR-005).
- **Without the setting**: 403 first, and nothing changes.

### `GET` / `POST /teacher/questions/{id}/delete` (unchanged)

The confirmation still names the question by its number only, with no badge (FR-015). Deleting
leaves the mark unchanged. Without the setting: 403 first, for every target.

## A competition's questions (`app/routers/teacher_competition_entries.py`)

### `GET /teacher/competitions/{cid}/questions?…`: the competition's questions (changed)

- **Who**: every teacher, in every status, as in milestone 12.2; this is the gap accepted until
  milestone 12.10 (FR-027).
- **With the setting**: `question_page(..., with_bank_mark=True)`. Each question whose bank question
  is additional now shows the badge **Additional** in its card heading, beside the bank number, in
  every status and for a finished competition of a deactivated subject. "Deleted from the question
  bank" is shown as before, possibly together with the badge.
- **Without the setting**: `with_bank_mark=False`. The mark is not read, and the response holds no
  badge. Otherwise the page is unchanged.

### `GET /teacher/competitions/{cid}/questions/add?…`: Add questions (changed)

- **Setting** first (403 for every competition and target), then the 012.2 checks.
- **Listing**: `question_bank.question_page(..., include_additional=True)`. Each additional
  question's card heading shows the badge, with **Add** or "Already in this competition" as before.

### `POST /teacher/competitions/{cid}/questions`: add a question (unchanged)

An additional question is copied like any other. The notice "Question 58 was added to “…”" is
unchanged. Without the setting: 403 first, for an additional, ordinary, deleted or missing question.

### Remove confirmation and remove (unchanged)

The confirmation shows no badge (`get_competition_question` fills `is_additional=None`).

## Pages that never show the mark (unchanged, now asserted)

These show no **Additional** badge or word for a competition holding an additional question, to
any teacher:

- `/teacher/competitions/{cid}/teams…`
- `/teacher/competitions/{cid}/answers…` (the answer sheets, editable and read-only)
- `/teacher/competitions/{cid}/grades…` (the grading sheets, editable and read-only)
- the publish confirmation
- the results download

## Form contract

The `additional` field joins the recorded forms of `teacher-question-new`,
`teacher-question-new-invalid`, `teacher-question-new-saved`, `teacher-question-edit` and
`teacher-question-edit-invalid` in `tests/integration/form_contract.json`. These cases are
regenerated with `UPDATE_FORM_CONTRACT=1`, those cases only, and recorded as a deliberate change
(milestone 12.9) in the docstring of `test_form_contract.py`.
