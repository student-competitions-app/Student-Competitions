# Contract: Component Library (Milestone 10)

**Feature**: [../spec.md](../spec.md) | **Research**: [../research.md](../research.md) D7–D13 | **Tokens**: [../data-model.md §2](../data-model.md#2-design-tokens)

**Where the components live**: every component is a Jinja macro in `app/templates/components/`.
Pages import what they use, for example:

```jinja
{% from "components/button.html" import link_button, post_button %}
```

**Rules for every macro**:

- **Escaping**: text parameters are plain strings, escaped by autoescape. Rich content is passed
  through `{% call %}` and `caller()`, never as an HTML string.
- **Classes**: every class a macro emits is defined in `pico.min.css` or `app.css`. A class is only
  built dynamically inside a macro, from the literal strings of a `{% set …_class = … %}` statement
  (research D16).
- **No inline `style`**: no `style=` attribute anywhere.
- **The gallery**: every macro and every variant below appears in `/admin/components` (FR-037,
  SC-009). A new macro or variant is added there and to `docs/requirements/ui-guidelines.md` in the
  same change (FR-045).

The **Emits** column gives the essential markup and classes, which the tests and the stylesheet
check rely on. Attribute order and whitespace are not part of the contract.

---

## 1. Frame (`components/frame.html`), FR-018–FR-021, FR-024

| Macro | Parameters | Emits |
|---|---|---|
| `top_bar()` | none; reads `app_name`, `current_user`, `current_role`, `user_roles`, `theme` and `theme_return` from the context | `<header class="top-bar">`, holding `<a href="/" class="brand">`, then `logo_mark()`, then `<span class="brand-name">Student Competitions</span>`. When signed in it adds `<span class="brand-role">{role label}</span>` and `user_menu()`. |
| `user_menu()` | none (context as above) | `<details class="user-menu">` with `<summary>`, which holds `icon("account")`, then `<span class="user-menu-email">{email}</span>`, visually hidden below 768 px, where "Account menu" is read instead. Its panel holds, in order: `<a href="/profile">{email}</a>`; the role switch (§1.1); `theme_switch()`; `<form method="post" action="/logout"><button type="submit" class="secondary">Log out</button></form>`. |
| `theme_switch(current, return_to)` | `current`: `"light"`, `"dark"` or `"device"`; `return_to`: `str` | `<form method="post" action="/theme" class="theme-switch">` with a `<fieldset>` and the legend "Theme", `<input type="hidden" name="next" value="{return_to}">`, and three `<button type="submit" name="theme" value="light\|dark\|device">` labelled **Light**, **Dark** and **Device**. The current one has `aria-pressed="true"`, the others `"false"`. |
| `area_tabs(tabs, active, label)` | `tabs`: objects with `key`, `label` and `path`; `active`: `str \| None`; `label`: `str`, the nav's accessible name | `<nav class="area-tabs" aria-label="{label}"><ul>`, then one `<li><a href="{path}">` per tab. The active one adds `aria-current="page"`. |
| `back_link(href, text)` | `href`: a local path; `text`: `str` | `<a href="{href}" class="back-link">← {text}</a>`. It is the first element in `<main>`. |
| `page_heading(title, action=None)` | `title`: `str`; `action`: optional `(label, href)`, rendered as a primary `link_button` | `<div class="page-heading"><h1>{title}</h1> [action]</div>` |

### 1.1 Role switch (inside `user_menu`)

This is the existing form, moved into the menu, and rendered only when `user_roles | length > 1`.
It is `<form method="post" action="/role">` with "Switch to" and one
`<button type="submit" name="role" value="{role}" class="secondary">` per other role. The field
names and values are unchanged (US2-3).

### 1.2 Layout skeleton (`layouts/base.html`)

The layout renders, in order:

1. `<a href="#main" class="skip-link">Skip to main content</a>`;
2. `top_bar()`;
3. `{% block tabs %}{% endblock %}`;
4. `<main id="main" class="container">{% block content %}{% endblock %}</main>`;
5. `<footer class="site-footer container">`, with the version and build, then
   `{% block footer_extra %}{% endblock %}`.

`layouts/admin.html` and `layouts/teacher.html` fill `tabs` with `area_tabs(...)`, labelled
"Administrator area" and "Teacher area".

---

## 2. Buttons (`components/button.html`), FR-025

| Macro | Parameters | Emits |
|---|---|---|
| `button(label, kind="primary", name=None, value=None, outline=False, small=False)` | `kind`: `"primary"`, `"secondary"` or `"destructive"` | `<button type="submit" class="{kind class}[ outline][ small]">{label}</button>` |
| `link_button(label, href, kind="primary", outline=False, small=False)` | as above | `<a href="{href}" role="button" class="{kind class}[ outline][ small]">{label}</a>` |
| `post_button(action, label, kind="primary", hidden={}, outline=False, small=False)` | `hidden`: a mapping rendered as hidden inputs | `<form method="post" action="{action}" class="inline-form">`, then the hidden inputs and `button(...)` |

**Kind to class**: `primary` adds no class (Pico's default button), `secondary` adds `secondary`
(Pico), and `destructive` adds `destructive` (`app.css`). `outline` is Pico's. `small` is
`app.css`.

**Rules**:

- **One primary per page or section**: at most one primary button or link button.
- **Destructive actions** use `destructive`: Delete, Remove, Deactivate and Withdraw consent.
- **Links that open a form or a confirmation** use `link_button` with the kind of the action they
  lead to (US3-7).

---

## 3. Card (`components/card.html`), FR-026

| Macro | Parameters | Emits |
|---|---|---|
| `card(title, href=None, description=None)` | the body is optional, via `caller()` | `<article class="card">`. With `href`, the title is `<h3><a href="{href}" class="card-link">{title}</a></h3>`, and the link's hit area covers the whole card through CSS. Then `<p class="card-description">{description}</p>`, then the body. |

The home page uses one card per area (FR-035). The gallery shows a card with a link, one without,
and one with a body.

---

## 4. Data table (`components/table.html`), FR-027

| Macro | Parameters | Emits |
|---|---|---|
| `data_table(columns, caption=None)` | `columns`: a list of header labels; rows come from `caller()` | `<table class="data-table">`, with an optional `<caption>`, `<thead><tr>` holding one `<th scope="col">` per column, and `<tbody>{caller()}</tbody>` |
| `cell(label, value=None)` | `label`: the column header; `value`, or the content via `caller()` | `<td data-label="{label}">…</td>` |
| `actions_cell()` | the content via `caller()`, as `link_button` or `post_button` with `small=True` | `<td class="row-actions" data-label="">…</td>` |

**Rows** are plain `<tr>` elements written by the page inside the `call` block.

**Below 768 px** each row is a card of labelled values, with the actions last. Long values wrap
everywhere. There is no horizontal scroll wrapper.

**An empty list** renders `empty_state` instead of the table.

---

## 5. Badges (`components/badge.html`), FR-028

| Macro | Parameters | Emits |
|---|---|---|
| `badge(text, kind="neutral")` | `kind`: `"success"`, `"muted"`, `"neutral"` or `"info"`; `text` is required, and an empty value raises a template error | `<span class="badge badge-{kind}">{text}</span>` |
| `status_badge(is_active)` | `bool` | **Active** (`success`) or **Deactivated** (`muted`) |
| `access_badge(level)` | an `AccessLevel` | **Read** (`neutral`) or **Write** (`info`) |

---

## 6. Feedback (`components/feedback.html`), FR-029, FR-030

| Macro | Parameters | Emits |
|---|---|---|
| `notice(text, kind="info")` | `kind`: `"success"`, `"error"` or `"info"`; the body may come from `caller()` | `<div class="notice notice-{kind}" role="status\|alert">`. The role is `alert` for `error` and `status` otherwise. Then `<p>{text}</p>`. |
| `empty_state(message, hint=None)` | the body may come from `caller()`, for a link or action | `<div class="empty-state"><p class="empty-state-message">{message}</p>[<p class="empty-state-hint">{hint}</p>]</div>` |

---

## 7. Forms (`components/form.html`), FR-031

| Macro | Parameters | Emits |
|---|---|---|
| `error_summary(errors, form_error=None, order=None)` | `errors`: `dict[str, str]`; `order`: field ids in page order (it defaults to the dict's order) | Nothing when there are no errors. Otherwise `<div class="error-summary" role="alert" aria-labelledby="error-summary-title" tabindex="-1">`, holding `<h2 id="error-summary-title">There is a problem</h2>` and `<ul>`. The list has one `<li><a href="#{field_id}">{message}</a></li>` per field error, plus `<li>{form_error}</li>`, with no link, when it is set. |
| `field(id, label, value="", error=None, hint=None, type="text", name=None, attrs={})` | `attrs`: extra input attributes such as `required`, `maxlength`, `autocomplete`, `inputmode` and `pattern` | `<label for="{id}">{label}</label>`, then `[<small id="{id}-hint" class="field-hint">]`, `[<small id="{id}-error" class="field-error">{error}</small>]` and `<input id="{id}" name="{name or id}" value="{value}" …>`. With an error, the input has `aria-invalid="true"`. `aria-describedby` lists the hint and the error. |
| `select_field(id, label, options, selected=None, error=None, hint=None, name=None, attrs={})` | `options`: `(value, label)` pairs | As `field`, with a `<select>` |
| `checkbox_field(id, label, checked=False, name=None, value=None, hint=None)` | | `<label for="{id}"><input type="checkbox" …> {label}</label>`, then the hint |
| `form_actions(submit_label, cancel_href=None, kind="primary")` | | `<div class="form-actions">`, holding `button(submit_label, kind)` and `[<a href="{cancel_href}">Cancel</a>]` |

**How a form page uses them**:

1. `error_summary` sits directly under the `h1`, above the form.
2. Each field gets its message from `errors[field_id]`.
3. Values come from `values` (see [data-model.md §4.2](../data-model.md#42-form-page-context-every-page-with-a-form)).

**The institution picker** (`_institution_picker.html`) keeps its `<fieldset>` and its field names.
It is rebuilt from `data_table` and `checkbox_field`, and its error is the field error for
`picker`, whose summary link goes to `#picker`.

---

## 8. Confirmations (`components/confirmation.html`), FR-032

| Macro | Parameters | Emits |
|---|---|---|
| `confirmation(question, consequence, action, verb, cancel_href, hidden={})` | the consequence may also come from `caller()`, for lists such as "classes will be deleted too" | `<section class="confirmation">`, holding `<h1>{question}</h1>`, `<p>{consequence}</p>` and a `<div class="form-actions">` with `post_button(action, verb, kind="destructive", hidden=hidden)` and `<a href="{cancel_href}">Cancel</a>` |
| `refusal(question, reason, back_href, back_text)` | an optional alternative action via `caller()`, for example `link_button("Deactivate", …, kind="destructive")` or `post_button(…)` exactly as the current page has it | `<section class="confirmation confirmation-refused">`, holding `<h1>{question}</h1>`, `notice(reason, "info")`, the alternative action and `<a href="{back_href}">{back_text}</a>` |

**Which pages use them**: `subject_delete`, `region_delete`, `region_deactivate`,
`institution_delete`, `institution_deactivate`, `teacher_remove`, `class_delete`,
`class_deactivate`, `student_remove`, `profile_withdraw` and `data_deletion_confirm`. Each keeps its
current texts (FR-040).

---

## 9. Details list (`components/details.html`), FR-033

| Macro | Parameters | Emits |
|---|---|---|
| `details_list(items)` | `items`: `(label, value)` pairs, where a value of `None` skips the row; rich values come through `caller(label)` | `<dl class="details-list">`, with `<dt>` and `<dd>` pairs. Two columns from 768 px, stacked below. |

**Which pages use it**: the profile, the invitation and the data-deletion confirmation.

---

## 10. Selectors (`components/selectors.html`), FR-034

| Macro | Parameters | Emits |
|---|---|---|
| `list_detail(list_label, items, selected_id, item_href)` | `items`: objects with `id`, `name` and `is_active`; `item_href(item)`: a callable or a path prefix. The detail panel comes from `caller()`. | `<div class="selectors selectors-list-detail">`. The left panel is `<section aria-labelledby=…><h2>{list_label}</h2><ul class="select-list">`, with one `<li>` per item holding `<a href=…>`. The selected item has `aria-current="true"` and `class="selected"`, and a deactivated item adds `status_badge`. The right panel is `caller()`. Side by side from 768 px, stacked below. |
| `chained_lists(levels, action)` | `levels`: three objects, each with `id`, `name`, `label`, `placeholder`, `options`, `selected`, `disabled`, `carry` (the hidden `name`/`value` pairs) and `extra_options` | `<div class="selectors selectors-chained">`, then one `<form method="get" action="{action}">` per level. Each form holds the hidden carry inputs and `select_field(…, attrs={"data-auto-submit": True})`. In a row from 768 px, stacked below. |

**Behaviour stays where it is**: the existing `GET` parameters, the `data-auto-submit` script and
the "+ Add class" option are unchanged. The **Educational institutions** tab uses `list_detail`.
The **Students** tab uses `chained_lists`.

---

## 11. Icons (`components/icons.html`), FR-008

| Macro | Parameters | Emits |
|---|---|---|
| `logo_mark(size="md")` | `"sm"`, `"md"` or `"lg"` | An inline `<svg class="logo-mark logo-mark-{size}" viewBox="0 0 32 32" aria-hidden="true" focusable="false">`. Its fills come from classes, not inline styles. |
| `icon(name)` | `"account"` or `"arrow-left"` | An inline `<svg class="icon" aria-hidden="true" focusable="false">` |

`app/static/img/favicon.svg` is the same mark, drawn with fixed colours.

---

## 12. Gallery coverage checklist (SC-009)

The `/admin/components` page has one section per row below, in this order. The integration test
asserts each section's `id` and the presence of each variant's text.

| Section id | Must show |
|---|---|
| `identity` | wordmark, logo mark at three sizes, the palette swatches for every colour token, the type scale (h1–h4, body, small) |
| `frame` | top bar (signed out and signed in), user menu (one role, several roles), theme switch (each current value), area tabs, back link, page heading with and without an action |
| `buttons` | primary, secondary and destructive, each as `button`, `link_button` and `post_button`, plus outline and small |
| `cards` | with a link, without one, with a body |
| `table` | a data table with three rows, a long value that wraps, status badges and row actions; an empty state in place of a table. The phone layout is seen by narrowing the window below 768 px, because it is a media query, not a container query. |
| `badges` | Active, Deactivated, Read, Write |
| `empty-states` | "No subjects yet" with its hint; "Select a region" with its hint |
| `notices` | success, error, info |
| `forms` | a field with a hint, a field with an error and its kept value, a select, a checkbox, an error summary with two field errors and one form error, form actions |
| `confirmations` | a confirmation; the refusal variant with the "Deactivate" alternative |
| `details` | a details list |
| `selectors` | list and detail (regions → institutions); chained lists (region → institution → class) |
