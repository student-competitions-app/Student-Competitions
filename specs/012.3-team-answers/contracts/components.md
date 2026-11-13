# Contract: Components

Two new patterns, the answer sheet and the placeholder; wording additions in the UI guidelines.
Each is added to the library, the gallery (`/admin/components`) and
`docs/requirements/ui-guidelines.md` before a page uses it (FR-034). See
[research.md](../research.md) R15.

## 1. Answer sheet (new): `components/answer_sheet.html`

```jinja
{% from "components/answer_sheet.html" import answer_sheet %}
{{ error_summary(errors, order=field_order) }}
{{ answer_sheet(items, "/teacher/competitions/17/answers/31", hidden) }}
```

- **`items`**: one per question, in order, each a mapping with `number` (1, 2, 3, …), `field_id`
  (`answer-41`), `text` (the question), `value` (the answer, `""` when none) and `error` (or
  `None`). At least one item: the page shows its empty state instead (refused with
  `template_error` otherwise).
- **`action`**, **`hidden`** (name → value, rendered as hidden inputs), **`submit_label`** (default
  "Save answers").
- **Markup**: `<form method="post" action="…">`, the hidden inputs, then
  `<ol class="answer-sheet">`, each `<li>` a `text_card("Question <n>")` holding
  `text_box("Question", text)` and, under it, `textarea_field(field_id, "Answer to question <n>",
  value=value, error=error, hint="Up to 2,000 characters.", placeholder="Not answered",
  attrs={"maxlength": "2000"})`; then `form_actions(submit_label)`, one primary button, no
  **Cancel**.
- **Look**: tokens only, no new token. The list has no markers (the card heading carries the
  number); cards are spaced as `.text-card-list`; the field takes the card's full width.
- **Phone**: below 768 px nothing changes but the widths: one column, the field full width, the
  button wrapping with its full label; no sideways scroll.
- **Errors**: each field shows its own message (`field-error`, `aria-invalid`); the page's
  `error_summary` links to `#answer-<id>`.

**Gallery** (`#answer-sheet`): a sheet of three questions: one answered (with a line break), one
empty showing "Not answered", one with "Answer to question 3 can be at most 2,000 characters.",
shown in the error summary above it too; the gallery's narrow view, if any, or a check by hand at
375 px.

**Guidelines**: an "Answer sheet (`components/answer_sheet.html`)" section after "Forms": when to use
it (every answer of one participant to a list of questions, saved at once), the numbering, the
labels, one save below the list, no reference answer.

## 2. Placeholder (new argument): `field` and `textarea_field`

```jinja
{{ textarea_field("answer-41", "Answer to question 3", hint="Up to 2,000 characters.", placeholder="Not answered") }}
```

- `placeholder=None`; when given, the control gets `placeholder="…"`. The label and the hint are
  rendered as before.

**Gallery** (`#forms`): an empty `textarea_field` with a label, a hint and the placeholder "Not
answered".

**Guidelines**: under Forms, the argument; under "Wording patterns", a new bullet:

> **Placeholders** only say that a field is empty: "Not answered". A placeholder never replaces the
> field's label or hint, and never holds an example, an instruction or a value.

## 3. Existing components used, unchanged

`page_heading`, `back_link`, `details_list`, `region_group`, `data_table`, `cell`, `actions_cell`,
`row_note`, `link_button`, `page_navigation`, `text_card`, `text_box`, `textarea_field`,
`error_summary`, `form_actions`, `notice`, `empty_state`, `refusal`, `local_time`,
`competition_status_badge`, `actions_menu`, `menu_link`.

## 4. Other UI guidelines changes (`docs/requirements/ui-guidelines.md`)

- **Wording patterns → Row notes**: the examples gain "Read access".
- **Phone behaviour**: "The answer sheet stays one column: each question card with its answer field
  under the text, the save button below the list."
- **Actions menu**: the example lists **Edit**, **Questions**, **Teams**, **Answers**, **Cancel
  competition**.
