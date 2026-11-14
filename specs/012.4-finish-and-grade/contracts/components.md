# Contract: Components

Phase 1 of [plan.md](../plan.md). Decisions: [research.md](../research.md) R13. Each new pattern
is added to the component library, the gallery (`/admin/components`, `admin_components.py` sample
data and `pages/admin/components.html`) and `docs/requirements/ui-guidelines.md` before any page
uses it (FR-048).

## 1. Non-destructive confirmation (changed): `components/confirmation.html`

```text
confirmation(question, consequence, action, verb, cancel_href, hidden={}, back_label="Cancel",
             kind="destructive")
```

- `kind` is `"destructive"` (default, every existing call) or `"primary"`; it is passed to the
  `post_button`. Any other value is a template error.
- **Gallery**: a "Finish competition “Spring round”…?" sample with **Finish competition** (primary)
  and **Keep in progress**, next to the existing destructive sample.
- **UI guidelines**: the rule that every action that cannot be undone goes through a confirmation
  page; its button is destructive when the action removes, hides or calls off something
  (**Delete**, **Deactivate**, **Withdraw consent**, **Cancel competition**), primary when it is the
  normal next step of the work (**Finish competition**).

## 2. Grading sheet (new): `components/grading_sheet.html`

```text
grading_sheet(items, action, hidden, submit_label="Save grades")
answers_read_only(items, grades=True)
```

**Items** (mappings), in question order: `number`, `text`, `answer` (`None` = not answered), and:

- for `grading_sheet`: `reference_answer`, `field_id` (`grade-<copy id>`), `value` (the saved grade
  as text, or what was sent), `error` (or `None`);
- for `answers_read_only`: `grade` (`int` or `None`); no reference answer is ever read.

**`grading_sheet`**: an `<ol class="answer-sheet">` of `text_card("Question {n}")`, each with
`text_box("Question", text)`, `text_box("Reference answer", reference_answer)`, then either
`text_box("Answer to question {n}", answer)` and the grade field — `field(field_id, "Grade for
question {n}", value, error, hint="A whole number from 0 to 10.", placeholder="Not graded",
attrs={"inputmode": "numeric", "autocomplete": "off"})` — or the plain text "Not answered" and no
field. When at least one item is answered, the list is wrapped in `<form method="post">` with the
hidden fields and `form_actions(submit_label)` (one primary button, no Cancel); otherwise there is
no form and no button. An empty `items` is a template error (the page shows its own empty state).

**`answers_read_only`**: the same cards with the question and the answer (or "Not answered"); with
`grades`, under each answered question "Grade: {g} of 10" or "Not graded yet". No form, no field,
no button, never a reference answer.

**Phone layout**: the 12.3 `.answer-sheet` styles (cards full width, fields full width); no new CSS
beyond the grade line (`.grade-line`, tokens only).

**Gallery**: the grading sheet with an error, with an unanswered question, at phone width; the
read-only variant with grades and without.

**UI guidelines**: a "Grading sheet" entry: the answer sheet's counterpart, always showing the
reference answer; the answer labelled "Answer to question <n>" in both variants; the read-only
variant's rules.

## 3. Filter links (new): `components/filter.html`

```text
filter_links(links, label)        # links: [(text, href, current: bool)]
```

```html
<nav class="filter-links" aria-label="{label}">
  <ul>
    <li><a href="…" aria-current="true">All teams</a></li>
    <li><a href="…">Ungraded only</a></li>
  </ul>
</nav>
```

- Exactly one link is current (template error otherwise). `aria-current="true"`, not `"page"`.
- Styled with the page navigation's current-page tokens (`.filter-links a[aria-current="true"]`
  shares the `.pagination a[aria-current="page"]` rule); no JavaScript, no **Show** button.
- **Gallery**: two links, the first current. **UI guidelines**: a "Filter links" entry with the
  `aria-current` reasoning.

## 4. Existing components used, unchanged

`page_heading`, `back_link`, `details_list`, `notice`, `empty_state`, `error_summary`,
`page_navigation`, `region_group`, `data_table`, `cell`, `actions_cell`, `row_note`, `link_button`,
`text_card`, `text_box`, `field`, `form_actions`, `competition_status_badge`, `local_time`,
`actions_menu`, `menu_link`, `refusal`.

## 5. UI guidelines changes (`docs/requirements/ui-guidelines.md`, FR-047)

- **Actions menu**: the Competitions entries in the order **Edit**, **Questions**, **Teams**,
  **Answers**, **Grades**, **Finish competition**, **Cancel competition**; the example template
  shows **Answers** on in progress and finished, **Grades**, and a non-destructive **Finish
  competition**.
- **Confirmations**: the link back says what is kept whenever the verb ends something
  (**Keep competition**, **Keep in progress**); "Every destructive action goes through a
  confirmation page" (in **Forgiving** and under **Confirmations**) and the **destructive** row of
  the button kinds are replaced by the rule of §1.
- **Wording patterns**: a confirmation's consequence is one to three short sentences, the first
  saying what happens to the item; "Read access" leaves the row-note examples.
- New entries: the grading sheet (§2) and the filter links (§3).
