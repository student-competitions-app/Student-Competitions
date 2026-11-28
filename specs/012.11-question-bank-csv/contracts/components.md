# Contract: Components (Milestone 12.11)

Constitution Principle II says every pattern below goes into `app/templates/components/`, the
gallery (`/admin/components`) and `docs/requirements/ui-guidelines.md` *before* the import page
uses it.

## 1. `confirmation` with a form (`components/confirmation.html`)

```jinja
confirmation(question, consequence, action, verb, cancel_href, hidden={}, back_label=None,
             kind="destructive", blocked=None, alternative=None,
             form_content=False, sends_file=False, summary=None)
```

- **`summary`**: rendered markup (an `error_summary(...)` call), placed right after the `h1` and
  before the consequence. `None` renders nothing.
- **`form_content=True`**: the caller's block and the `form-actions` are wrapped in one
  `<form method="post" action="{{ action }}">`. The hidden fields go first, and the confirming
  button is `button(verb, kind=kind)`, a submit button. Without it, the caller's block stays
  outside any form and the button is a `post_button`, exactly as today.
- **`sends_file=True`**: adds `enctype="multipart/form-data"` to that form. It is a template
  error without `form_content`.
- **`blocked` with `form_content`**: a template error, since a blocked confirmation has no
  button.
- **Unchanged without the new arguments**: every existing confirmation renders byte for byte as
  before, and the gallery test compares one.

## 2. `file_field` (`components/form.html`)

```jinja
file_field(id, label, error=None, hint=None, accept=None, name=None, attrs={})
```

```html
<label for="file">CSV file</label>
<small id="file-hint" class="field-hint">A CSV file in the format described in the README, at most 2 MB</small>
<small id="file-error" class="field-error">…</small>              <!-- only with an error -->
<input type="file" id="file" name="file" accept=".csv,text/csv"
       aria-describedby="file-hint file-error" aria-invalid="true">
```

- It never renders a `value`, so the field is always empty, after an error as well.
- It uses the same `_messages` and `_described` helpers as `field`.
- **CSS**: the field's existing spacing, border and focus tokens. The browser's own button and
  file name stay native. It fits 360 px without sideways scrolling.

## 3. `error_summary` with row errors (`components/form.html`)

```jinja
error_summary(errors, form_error=None, order=None, row_errors=(), more=0)
```

- **Order**: the linked field errors first (as today), then each of `row_errors` as a plain
  `<li>` with no link, then `form_error`.
- **`more > 0`**: after the `<ul>`, `<p class="error-summary-more">` with
  `ngettext("And %(num)d more error.", "And %(num)d more errors.", more)`.
- **Without the new arguments** the output is unchanged.
- **The import page** passes `errors={"file": file_error}` when there is a whole-file error, so it
  links to the file field, and passes the row errors unlinked.

## 4. Subjects tab (`pages/admin/subjects.html`)

- **Table**: `data_table([_("Name"), _("Status"), _("Questions"), _("Actions")])`. The
  **Questions** cell is the number, labelled on a phone card like every cell.
- **Actions**: the cell holds `actions_menu(s.name)` with the five entries in the order of
  [http-routes.md](./http-routes.md) §1. **Export questions** is `download=True`; **Import
  questions**, **Deactivate** and **Delete** are `destructive=True`.

## 5. Gallery and guidelines

- **The gallery** (`pages/admin/components.html`):
  - **"Confirmation with a form"** (`#confirmation-with-form`): the import page's shape, with a
    file field, once clean and once with a summary of one file error, three row errors and "And 5
    more errors.";
  - **"File field"** (`#file-field`): plain, with a hint, and with an error;
  - **the Forms section** (`#forms`) also shows `error_summary` with row errors.
- **`ui-guidelines.md`**:
  - Confirmations: `form_content`, `sends_file` and `summary`, and when to use them (a
    confirmation whose action needs input, such as a file).
  - Forms:
    - `file_field`, which is never refilled; after an error, the person chooses the file again;
    - the row-error variant of the error summary, and when an error is linked (it is about a
      field) or unlinked (it is about a row of a file);
    - the 20-error limit.
  - Actions menu: the **Subjects** tab's entries and their order.
  - Wording: "Row N: <field message>", "And N more errors.", and the glossary entries for
    **Export questions**, **Import questions**, **Replace questions** and **CSV file** in both
    languages.
