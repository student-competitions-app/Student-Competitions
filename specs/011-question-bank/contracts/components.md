# Contract: components (Milestone 11)

**The order of work**, from the guidelines' "Adding a pattern", for each item below:

1. the macro, with its CSS in the Components section of `app.css` (tokens only);
2. the gallery (`pages/admin/components.html`, sample data in `app/routers/admin_components.py`),
   every variant;
3. `docs/requirements/ui-guidelines.md` §5 (and §7 or §8 where noted);
4. only then the **Questions** tab.

The stylesheet checks (`test_stylesheet.py`, `test_frame_stylesheet.py`) cover the new classes:
every class defined and used, no inline style, no literal colours or pixel lengths.

Decisions: [research.md](../research.md) R9–R11.

## 1. `page_navigation` (new): `components/pagination.html`

```jinja
{% macro page_navigation(paging, href, noun, label) %}
```

**Parameters**:

- `paging`: a `paging.Paging`.
- `href`: the address prefix that a page number completes, e.g.
  `/teacher/questions?subject=3&page=`.
- `noun`: the plural shown in the range ("Questions").
- `label`: the landmark's name ("Pages, top" or "Pages, bottom").

**Emits** nothing when `paging.total == 0`. Otherwise:

```html
<nav class="pagination" aria-label="{label}">
  <p class="pagination-range">{noun} {first_item}–{last_item} of {total}</p>
  <ul>
    <li><a href="{href}{previous}" rel="prev">Previous</a></li>   <!-- or: -->
    <li><span class="pagination-off">Previous</span></li>          <!-- on page 1 -->
    <li><a href="{href}1">1</a></li>
    <li><span class="pagination-gap" aria-hidden="true">…</span></li>
    <li><a href="{href}9">9</a></li>
    <li><a href="{href}10" aria-current="page">10</a></li>
    …
    <li><a href="{href}{next}" rel="next">Next</a></li>            <!-- or the off span -->
  </ul>
</nav>
```

**Rules**:

- **The range** uses an en dash and no spaces ("Questions 31–40 of 200"). With one item it reads
  "Questions 1–1 of 1".
- **The current page** is a link with `aria-current="page"`, styled bold, with the primary underline
  of the area tabs. It is a link, so keyboard users land on it too.
- **Unavailable Previous or Next** is text with `.pagination-off` in the muted colour, never a
  disabled link.
- **Touch targets**: every link and span is at least `--sc-touch-target` high and wide.
- **On a phone** the list wraps (`flex-wrap`) and never scrolls sideways at 360 px. The range sits
  on its own line above.
- **No JavaScript**: plain links.

**Gallery** `#pagination`, with three variants built from `Paging.build`:

- page 1 of 1 (5 items);
- page 4 of 20 (200 items);
- page 20 of 20.

**Guidelines**:

- **§5 Components**: a new "Page navigation" entry.
- **§7 Wording**: "<Noun> 31–40 of 200", **Previous** and **Next**.
- **§8 Phone behaviour**: it wraps.

## 2. `form_actions`: a second save button (extended), `components/form.html`

```jinja
{% macro form_actions(submit_label, cancel_href=None, kind="primary", name=None, value=None, secondary=None) %}
```

**New parameters**:

- `name` and `value`: given to the main button.
- `secondary`: a mapping `{"label", "name", "value"}`, rendered as a `secondary` button right after
  the main one.

The existing calls are unchanged.

```html
<div class="form-actions">
  <button type="submit" name="then" value="list">Save question</button>
  <button type="submit" class="secondary" name="then" value="another">Save and add one more question</button>
  <a href="…">Cancel</a>
</div>
```

**Rules**:

- **One primary per form**, and it comes first, so implicit submission (Enter) uses it.
- **Both buttons send their value** with or without JavaScript. The busy-button script never
  disables them (milestone 10.1).
- **On a phone**, the buttons wrap. Each keeps its full label.

**Gallery** `#forms`: a second form shows the two-button variant.

**Guidelines** §5 Forms:

- **When to use it**: the second button is for "save and continue with another"; there is at most
  one secondary save.
- **Where the main button leads**: back to the list.

## 3. `textarea_field` (new macro), `components/form.html`

```jinja
{% macro textarea_field(id, label, value="", error=None, hint=None, name=None, rows=6, attrs={}) %}
```

**Emits** the same label, hint and error as `field`, then:

```html
<textarea id="{id}" name="{name or id}" rows="{rows}" aria-describedby="…" aria-invalid="true"…>{value}</textarea>
```

**Rules**:

- **The value** is escaped and kept exactly, line breaks included. There is no whitespace between
  the tags and the value, because a leading newline inside `<textarea>` is dropped by HTML parsing.
  The macro emits `"\n" ~ value` when the value starts with a newline.
- **Width**: a textarea's `max-width` becomes `var(--sc-measure)` instead of `--sc-form-width`, so
  long texts are comfortable. No textarea exists yet, so nothing else changes, and no page-specific
  class is needed.
- **Resizing**: vertical only.

**Gallery** `#forms`: empty with a hint, filled with line breaks, and with an error.

**Guidelines** §5 Forms: use it for multi-line text. It keeps line breaks.

## 4. `text_card` and `text_box` (new macros), `components/card.html`

```jinja
{% macro text_card(heading, id=None) %}   {# body through {% call %} #}
{% macro text_box(label, text) %}
```

```html
<article class="text-card" id="question-57">
  <h3>Question 57</h3>
  <section class="text-box">
    <h4 class="text-box-label">Question</h4>
    <p class="keep-lines">…</p>
  </section>
  <section class="text-box">
    <h4 class="text-box-label">Reference answer</h4>
    <p class="keep-lines">…</p>
  </section>
  <div class="row-actions">…</div>          <!-- from the caller -->
</article>
```

**Rules**:

- **The outer card** is a surface with the card radius and border.
- **The inner boxes**:
  - each has a quieter tint (`--sc-neutral-tint`), the control radius, and a small, semibold,
    muted label;
  - they stack, the reference answer below the question, at full width on every screen;
  - their text wraps long words (`.keep-lines`: `white-space: pre-line; overflow-wrap: anywhere`).
- **The anchor**: `id` makes the card a target (`#question-57`). The pinned-frame scroll padding of
  milestone 10.1 keeps it below the frame.

**Gallery** `#cards`:

- a text card with two boxes and row actions;
- one with a very long unbroken word and several lines.

**Guidelines** §5 Card: a text card holds long entered texts, such as a question with its reference
answer.

## 5. `chained_lists`: a no-script Show button (extended), `components/selectors.html`

Inside each level's `<form>`, after the select:

```html
<noscript><button type="submit" class="secondary small">Show</button></noscript>
```

The button is rendered through `button("Show", kind="secondary", small=True)`.

**Rules**:

- **With JavaScript**: nothing visible changes.
- **Without JavaScript**: each list can be sent (FR-012, US2-14). This also restores the Students
  tab without JavaScript (research R11).
- **A disabled level** keeps its `disabled` select. Its button submits nothing useful but is
  harmless, as before milestone 9's change.

**Gallery** `#selectors`: unchanged markup. The gallery note says the button shows without
JavaScript.

**Guidelines** §5 Selectors: "Without JavaScript, each list shows a **Show** button."

**Form contract**: the noscript button has no `name`, so `form_contract.json` changes only through
the new forms.
