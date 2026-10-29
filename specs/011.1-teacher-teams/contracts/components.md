# Contract: components (Milestone 11.1)

**The order of work**, from the guidelines' "Adding a pattern", for each item below:

1. the macro, with any CSS in the Components section of `app.css` (tokens only);
2. the gallery (`pages/admin/components.html`, with sample data in
   `app/routers/admin_components.py`), every variant;
3. `docs/requirements/ui-guidelines.md` §5 (and §7 where noted);
4. only then the pages: **Students** first for `section_heading` (FR-046), then **Teams**.

The stylesheet checks (`test_stylesheet.py`, `test_frame_stylesheet.py`) cover the new class: every
class defined and used, no inline style, no literal colours or pixel lengths.

Every other part of the **Teams** pages reuses existing components unchanged: `chained_lists`,
`data_table`/`cell`/`actions_cell`, `notice`, `empty_state`, `confirmation`, `details_list`,
`back_link`, `page_heading`, `field`/`error_summary`/`form_actions`, `link_button` and
`post_button` (FR-045).

Decisions: [research.md](../research.md) R12, R13.

## 1. `section_heading` (new): `components/frame.html`

```jinja
{% macro section_heading(title, heading_id, action=None, deactivated=False) %}
```

**Parameters**:

- `title`: the section's name, plain text (escaped).
- `heading_id`: the `h2`'s id, named by the page's `<section aria-labelledby="…">`.
- `action`: `(label, href)` for at most one primary `link_button` beside the title, or `None`.
- `deactivated`: `True` adds the **Deactivated** status badge after the title, inside the `h2`.
- **The call block** (optional): the small secondary or destructive buttons below the heading.

**Emits**, exactly the markup of the milestone 9 Students heading:

```html
<div class="page-heading">
  <h2 id="{heading_id}">{title}[ <span class="badge badge-muted">Deactivated</span>]</h2>
  [<a href="{href}" role="button" …>{label}</a>]          <!-- link_button(label, href) -->
</div>
[<div class="row-actions">{call block}</div>]             <!-- only when the block is not blank -->
```

**Rules**:

- **The row** is left out when there is no call block or its output is only white space, so a page
  can always write `{% call %}` with its buttons inside `{% if can_write %}` (research R12).
- **At most one primary button**, beside the title. The row holds `outline=True, small=True`
  buttons of kind secondary or destructive, links or `post_button`s (guidelines §6).
- **A long title wraps** inside the content width, and the button wraps below it on a phone. This is
  the existing `.page-heading` behaviour, so no new CSS is needed.
- **The page owns the `<section>`**: the component draws only the heading, because the content
  below it differs on every page.

**Used by**:

- **Students**: `section_heading(selected_class.label, "class-heading", ("Add student", …) if
  can_write and active, deactivated=not active)`, with Edit, Deactivate or Activate, and Delete in
  the call block under `{% if can_write %}`. The rendered markup is unchanged (test-pinned in four
  states).
- **Teams**: `section_heading(team.name, "team-heading", ("Add students", …) if can_write)`, with
  Rename and Delete under `{% if can_write %}`.

**Gallery** `#section-heading`, a new section after `#frame`, with four variants:

- an action and two row buttons (**Add student**; **Edit**, **Delete**);
- deactivated, with a row of **Edit**, **Activate** (a `post_button`) and **Delete**;
- no action and no row (Read access);
- a 200-character title with an action, to show the wrapping.

**Guidelines**: §5 Frame gains:

> **`section_heading(title, heading_id, action=None, deactivated=False)`**: the `h2` of a section
> that is one selected item, such as the selected class on **Students** or the selected team on
> **Teams**. At most one primary link button beside the title, and the item's other actions as
> small outline buttons in a row below it (through `{% call %}`; the row is left out when it is
> empty). The page wraps the heading and its content in `<section aria-labelledby="…">`.

## 2. `row_note` (new): `components/table.html`

```jinja
{% macro row_note(text) %}
```

**Emits**: `<span class="row-note">{text}</span>`.

**Rules**:

- **Where**: only inside `actions_cell()`, in place of an action that is not available for that row,
  as in "In this team" on **Add students**. It is not a status badge and not a disabled button
  (research R13).
- **The CSS**: one new rule in `app.css`, `.row-note { color: var(--sc-muted); }`. The note keeps
  the row's text size and lines up with the buttons of the other rows. Below 768 px it sits in the
  card's actions part like a button.
- **The text** is required: an empty text calls `template_error`, as `badge` does.

**Gallery**: the `#table` section gains a small second table, "Students of KN-21 · year 2", with one
row that has an **Add** `post_button` and one row with `row_note("In this team")`.

**Guidelines**:

- **§5 Data table**: "**`row_note(text)`** stands in the actions cell where a row's action is not
  available, as "In this team"; muted text, never a disabled button."
- **§7 Wording**: a row note is a short plain phrase, with no full stop.
