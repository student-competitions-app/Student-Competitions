# UI Guidelines

These guidelines are binding for every page of Student Competitions. Every later milestone builds
its pages from the component library in `app/templates/components/` and follows the rules below;
its spec and plan are checked against them. A new pattern is first added to the library, the
gallery and this document, and only then used on a page. It is never hand-built on a single page.

They were introduced in milestone 10 ([spec](../../specs/010-design-system-ui-guidelines/spec.md)).
The approved look is the mockup in
[`specs/010-design-system-ui-guidelines/mockup/`](../../specs/010-design-system-ui-guidelines/mockup/index.html).
The component gallery at `/admin/components` (outside production only, for administrators) shows
every component in every variant; the section names below link to its parts.

## 1. Audience

- **Students** from school to university, years of study 1 to 12. Most use phones, and many have
  no laptop. Young readers scan rather than read, skip long instructions, and rely on an in-page
  back link rather than the browser's.
- **Teachers and administrators** mostly work on desktops, with lists and forms.

Every page works for the youngest student who can take a written competition, and stays efficient
for staff.

## 2. Principles

Each principle is followed by its rules and the sources it rests on.

### Calm and focused

- Content comes first. No decoration competes with it, and there is no advertising or promotion.
- Nothing moves or blinks. Transitions, where there are any, are subtle. The one exception is the
  loading bar: it moves while the next page is on its way, so a slow page never looks broken, and
  it stands still when the device asks for reduced motion (milestone 10.1).
- One primary action per page or section, so the next step is obvious.

_Sources_: Nielsen Norman Group on visual hierarchy and on how children use websites (they are
easily distracted by moving and promotional content); the W3C/WAI *Making Content Usable for
People with Cognitive and Learning Disabilities*, objective 4 (help users focus).

### Clear and consistent

- One navigation per page: the area tabs. The same component looks and behaves the same
  everywhere and sits in the same place.
- Every page below an area's main page starts with a back link to a fixed address.
- A status is always a word in a badge, never colour alone.

_Sources_: the GOV.UK Design System (consistent patterns, the back link); W3C/WAI *Making Content
Usable*, objective 3 (make it easy to find what you need, with consistent navigation).

### Readable

- Body text is at least 16 px on a phone and 18 px from 1024 px, with a line height of at least
  1.5. Running text is held to about 70 characters per line.
- Text is left-aligned, never justified. Emphasis is **bold**: never italics, underlining or
  capitals.
- The font is Open Sans (SIL Open Font License, Latin and Cyrillic), in regular 400, semibold 600
  and bold 700, served from `app/static/fonts/`, never from a font service. The system font stack
  is the fallback.

_Sources_: the British Dyslexia Association *Dyslexia Style Guide* (16–19 px text, line spacing
1.5, no italics, underlining or justified text, sans-serif fonts); Nielsen Norman Group on line
length and on reading on screens.

### Plain language

- Short sentences and words students know. Instructions are a sentence or two, where they are
  needed.
- Buttons are verbs that say what happens: **Save**, **Invite teacher**, **Create subject**.
- Abbreviations are spelled out: "educational institution", not "institution" alone or an acronym.

_Sources_: the GOV.UK content design guidance (plain English, writing for the reading age of the
youngest user); W3C/WAI *Making Content Usable*, objective 3 (use clear words).

### Forgiving

- Every form error is shown next to its field and in an error summary at the top of the page,
  headed "There is a problem", with one link per error that moves to its field. What the person
  entered is kept.
- Every destructive action asks for confirmation on its own page, names the item and says what
  will happen.

_Sources_: the GOV.UK Design System error summary, error message and confirmation patterns;
W3C/WAI *Making Content Usable*, objective 6 (help users avoid mistakes and know how to correct
them). Touch targets follow Material Design and the Apple Human Interface Guidelines: at least 44
by 44 px.

## 3. Tokens

**Use a token; never a literal.** Every colour, size and length is a `--sc-*` custom property,
defined once between `/* == Tokens == */` and `/* == End of tokens == */` at the top of
`app/static/css/app.css`. The rest of the stylesheet uses `var(--sc-*)` (or a Pico variable that
the mapping sets from a token). The only literal `px` values outside the token block are the
`768px` and `1024px` breakpoints, because media queries cannot read custom properties.
`tests/unit/test_stylesheet.py` fails on any other literal colour or pixel length.

### Colour

| Token | Role | Light | Dark |
|---|---|---|---|
| `--sc-page` | Page background | `#f4f6fb` | `#0d1424` |
| `--sc-surface` | Cards, tables, menus | `#ffffff` | `#151f35` |
| `--sc-text` | Text | `#172033` | `#e6eaf2` |
| `--sc-muted` | Muted text | `#556070` | `#9aa6bd` |
| `--sc-border` | Borders, dividers | `#dde3ee` | `#26324d` |
| `--sc-top-bar` | Top bar background | `#16337a` | `#111a2e` |
| `--sc-primary` | Primary buttons, links, current tab | `#1f56d6` | `#6c9cff` |
| `--sc-on-primary` | Text on primary | `#ffffff` | `#0d1424` |
| `--sc-primary-tint` | Selection, Write badge, pressed choice | `#e7eefc` | `#1d2c4f` |
| `--sc-accent` | Logo mark, highlights | `#f2a516` | `#f5b83d` |
| `--sc-success` / `--sc-success-tint` | Success, Active badge | `#17803d` / `#e5f5ea` | `#5fcf86` / `#13291c` |
| `--sc-danger` / `--sc-danger-tint` | Destructive actions, errors | `#c0392b` / `#fdf0ee` | `#ff8a7a` / `#341b19` |
| `--sc-primary-hover`, `--sc-danger-hover` | Hover and active | `#1a47b3`, `#a02f23` | `#8fb3ff`, `#ffa597` |
| `--sc-focus-ring` | Focus outline | `rgb(31 86 214 / 0.4)` | `rgb(108 156 255 / 0.45)` |
| `--sc-on-danger`, `--sc-on-success`, `--sc-on-accent` | Text on those fills | `#ffffff`, `#ffffff`, `#172033` | `#0d1424` |
| `--sc-on-top-bar`, `--sc-on-top-bar-muted` | Text in the top bar | `#ffffff`, `#c3cfee` | `#e6eaf2`, `#9aa6bd` |
| `--sc-neutral-tint` | Deactivated and Read badges, table header | `#eef1f6` | `#1b253b` |
| `--sc-shadow-card`, `--sc-shadow-menu` | Card and menu shadows | barely visible | none, and a deeper menu shadow |

### Type

| Token | Value |
|---|---|
| `--sc-font-family` | `"Open Sans"`, then the system font stack |
| `--sc-weight-regular` / `-semibold` / `-bold` | 400 / 600 / 700 |
| `--sc-text-body` | 1 rem (16 px); 1.125 rem (18 px) from 1024 px |
| `--sc-text-small` | 0.875 rem: footer, hints and badges only, never running text |
| `--sc-line-height` / `--sc-line-height-heading` | 1.5 / 1.25 |
| `--sc-text-h1` … `--sc-text-h4` | 28, 22, 20 and 18 px; h1 and h2 are 32 and 24 px from 768 px |
| `--sc-measure` | 70 ch, the longest line of running text |

### Space and shape

| Token | Value |
|---|---|
| `--sc-space-1` … `--sc-space-6` | 8, 16, 24, 32, 48 and 64 px: the 8 px grid |
| `--sc-radius-control` / `--sc-radius-card` | 8 px for buttons, fields, badges and notices; 12 px for cards, table cards and the menu |
| `--sc-content-width` | 72 rem, the one content width |
| `--sc-form-width` | 30 rem, the widest a field grows, and the narrow column of one-form pages |
| `--sc-touch-target` | 44 px, the minimum height of a button or menu entry |
| `--sc-action-width` | 7.5 rem, the minimum width of a row action |
| `--sc-border-width` / `-strong` / `-accent` | 1 px, 2 px and 4 px borders |
| `--sc-frame-clearance` | 5.5 rem, the room kept above a scroll or focus target on a page without area tabs, so the pinned frame never covers it |
| `--sc-frame-clearance-tabs` | the same on an area page: 11 rem below 768 px (the tabs may wrap), 8 rem from 768 px |
| `--sc-field-clearance` | 5 rem kept above a form control, so its label and error stay in view too |

The root font size stays at 16 px at every width, so every `rem` stays on the grid; only the body
text grows from 1024 px.

## 4. Layout

Every page renders the same frame from `layouts/base.html`:

1. a **skip link**, "Skip to main content", visible when it has focus, shown above the frame;
2. the **frame**, `<div class="frame">`, which holds:
   1. the **top bar** ([gallery: frame](/admin/components#frame)): the logo mark and the wordmark
      linking home, the current role's label, and the **user menu**;
   2. the **area tabs** of the administrator or teacher area, if the page is in one;
   3. the **loading bar**, hidden until a page load is pending;
4. `<main>`, at the one content width;
5. the **footer**: the version and build, and on the home page the database line.

The user menu is a native `<details>`, so it opens without JavaScript. It holds, in order, the
email linking to the profile, the role switch (for a person with several roles), the theme switch
and **Log out**. When it is taller than the space below the top bar, it scrolls inside itself.

**The pinned frame** (milestone 10.1): on a screen at least 600 px tall, the frame stays at the top
while the page scrolls, so the tabs and the user menu are always in reach. The page still scrolls
as a whole: nothing gets its own scroll area, so the address bar hides on a phone, pull-to-refresh
works, Back returns to the same place, the keyboard scrolls the page and printing shows everything.
On a shorter screen (a phone held sideways, or a page zoomed in far) and in print, the frame
scrolls away with the page.

**Keeping targets in view**: the pinned frame never covers what the page moves to. The page keeps
`--sc-frame-clearance` (or `--sc-frame-clearance-tabs` on an area page) above every target of a
`#` link, such as the skip link and the error summary, and above every element that gets keyboard
focus; a form control keeps `--sc-field-clearance`, so its label and error stay in view (WCAG 2.2,
2.4.11). The clearances are the tallest frames measured, plus room to spare: a new tab, a longer
tab label or a taller top bar must be measured again at 360 px and 375 px width against them.
Last measured in milestone 11.1, with the teacher area's four tabs (Students, Teams, Questions,
Competitions): they wrap onto two rows at 360 × 640 and 375 × 667, and the frame ends at 158.5 px,
the same as the administrator area's, under the 176 px of `--sc-frame-clearance-tabs`.

**The loading feedback**: the base layout loads one script, `loading-feedback.js`, on every page.
It shows the loading bar and the busy button (section 5) while the next page is on its way. Pages
add nothing; without JavaScript, links and forms work as before.

**Inside `<main>`**, in order: the back link (on every page below an area's main page), the page
heading, the error summary or a notice, then the content. A page has one `h1`; sections are `h2`.
One-form public pages (sign-in, code entry, role choice, data deletion) use the `.narrow` centred
column.

**Breakpoints**: three, written as literals. Below `768px`: tables become cards, the user menu
folds to its icon, the selectors stack, the area tabs drop to the touch-target height, and h1 and
h2 step down a size. From `1024px`: body text is 18 px. From a height of `600px` (on screen, not in
print): the frame is pinned.

## 5. Components

Every component is a Jinja macro. Import what the page uses, for example
`{% from "components/button.html" import link_button, post_button %}`. Text parameters are plain
strings, escaped by autoescape. Rich content goes through `{% call %}`, never as an HTML string.
The full contract, with parameters and emitted markup, is
[contracts/components.md](../../specs/010-design-system-ui-guidelines/contracts/components.md).

### Frame (`components/frame.html`)

- **`top_bar()`**, **`user_menu()`**: rendered by the layout; never called by a page.
- **`theme_switch(current, return_to, standalone=False)`**: in the user menu, and standalone under
  the sign-in form. No other page shows it.
- **`area_tabs(tabs, active, label)`**: rendered by `layouts/admin.html` and `layouts/teacher.html`.
  A new tab is added to `ADMIN_TABS` or `TEACHER_TABS`, never drawn by a page.
- **`back_link(href, text)`**: first in `<main>` on every page below an area's main page. The
  target is a fixed address that keeps the page's selection, never the browser's history. The text
  is "Back to {parent}": "Back to the subjects", "Back to “Kyiv”".
- **`page_heading(title, action=None)`**: the page's `h1`, with at most one primary link button
  beside it, for example `page_heading("Subjects", ("Create subject", "/admin/subjects/new"))`.
- **`section_heading(title, heading_id, action=None, deactivated=False)`**: the `h2` of a section
  that is one selected item, such as the selected class on **Students** or the selected team on
  **Teams**. At most one primary link button beside the title, and the item's other actions as
  small outline buttons in a row below it (through `{% call %}`; the row is left out when it is
  empty). The page wraps the heading and its content in `<section aria-labelledby="…">`.

  ```jinja
  <section aria-labelledby="team-heading">
    {% call section_heading(team.name, "team-heading", ("Add students", add_href) if can_write else None) %}
    {%- if can_write -%}
    {{- link_button("Rename", rename_href, kind="secondary", outline=True, small=True) -}}
    {{- link_button("Delete", delete_href, kind="destructive", outline=True, small=True) -}}
    {%- endif -%}
    {% endcall %}
    …the section's content…
  </section>
  ```
- **`loading_bar(active=False)`**: rendered by the layout as the frame's last child; never called
  by a page. A thin primary line hanging just under the frame. `loading-feedback.js` shows it when
  a link to another page of the application is followed or a form is sent, and the next page has
  not arrived within 200 ms. It starts for nothing else: not for a link opened in a new tab, a link
  to another site, a `#` link or a form the browser refuses. With reduced motion it stands still.

_Gallery_: [frame](/admin/components#frame), [section heading](/admin/components#section-heading),
[loading feedback](/admin/components#loading).

### Buttons (`components/button.html`)

- **`button(label, kind, …)`**: a submit button inside a form.
- **`link_button(label, href, kind, …)`**: a link that opens a form or a confirmation page. It
  looks like the action it leads to.
- **`post_button(action, label, kind, hidden={}, …)`**: a one-button `POST` form, such as
  **Activate** in a row or the destructive button of a confirmation.

`outline=True` and `small=True` give the row-action look. See section 6 for the kinds.
_Gallery_: [buttons](/admin/components#buttons).

**Busy button**: `button(…, busy=True)` renders `aria-busy="true"`, which shows Pico's spinner,
redrawn in the button's own text colour. Pages never pass it: `loading-feedback.js` marks the
button that sent a form once the next page has taken 200 ms, and a form that changes something
cannot be sent again until that page arrives. A busy button is never `disabled`, so its value is
still sent (the role switch and the theme switch rely on it).
_Gallery_: [loading feedback](/admin/components#loading).

### Card (`components/card.html`)

**`card(title, href=None, description=None)`** groups related content on a surface. With `href`
the whole card is the link, as on the home page. Use it for entries the person chooses between, or
to frame one block (a consent record). Do not use it for a list of records: that is a data table.
_Gallery_: [cards](/admin/components#cards).

**`text_card(heading, id=None)`** with **`text_box(label, text)`** holds long entered texts, such
as a question with its reference answer (milestone 11). The card is one surface with a heading
("Question 57"); its body, through `{% call %}`, is one or more boxes, each a quieter tint with a
small label, stacked at full width on every screen, then any `row-actions`. The texts keep their
line breaks, and a long word wraps inside its box. With `id` the card is the target of a `#` link
(`#question-57`), which lands below the pinned frame. Several text cards go in
`<ol class="text-card-list">`. Use it, not a data table or a details list, when the values are
paragraphs rather than short facts. _Gallery_: [cards](/admin/components#cards).

### Data table (`components/table.html`)

**`data_table(columns)`** with `cell(label, value)` and `actions_cell()` is every list of records.
Rows are plain `<tr>`s in the `{% call %}` block. Every cell gets its column's label, so below
768 px each row becomes a card of labelled values with the actions last. Long values wrap; a table
never scrolls sideways. An empty list renders `empty_state` instead of a table.

```jinja
{% call data_table(["Name", "Status", "Actions"]) %}
<tr>
  {{ cell("Name", s.name) }}
  {% call cell("Status") %}{{ status_badge(s.is_active) }}{% endcall %}
  {% call actions_cell() %}{{ link_button("Rename", path, kind="secondary", outline=True, small=True) }}{% endcall %}
</tr>
{% endcall %}
```

**`row_note(text)`** stands in the actions cell where a row's action is not available, as "In this
team"; muted text, never a disabled button.

_Gallery_: [table](/admin/components#table).

### Badges (`components/badge.html`)

**`status_badge(is_active)`** gives **Active** or **Deactivated**; **`access_badge(level)`**
gives **Read** or **Write**. **`badge(text, kind)`** is for a new status with its own word; an
empty text is refused. Use a badge for every status, never coloured text or "(deactivated)".
_Gallery_: [badges](/admin/components#badges).

### Feedback (`components/feedback.html`)

- **`notice(text, kind)`**: `success` after an action ("Invitation sent to …"), `error` for a
  refusal that is not about a form field (an expired link), `info` for a state the person should
  know about (a deactivated region, data temporarily unavailable). An error notice is an alert;
  the others are a status.
- **`empty_state(message, hint)`**: in place of an empty list or an unmade choice. The hint is one
  line saying what to do next.

_Gallery_: [notices](/admin/components#notices), [empty states](/admin/components#empty-states).

### Forms (`components/form.html`)

Every form page passes `values` (what was entered, by field id), `errors` (field id → message) and
`form_error` (a message about the whole submission). Then:

- **`error_summary(errors, form_error, order)`** sits under the `h1`. It renders nothing without
  errors.
- **`field`**, **`select_field`** and **`checkbox_field`** give each field its label, optional
  hint, its error and the entered value.
- **`textarea_field`** is the multi-line twin of `field`, for text that may run over several lines
  (a question, a reference answer). It keeps the value exactly, line breaks included, is wider than
  a single-line field (the reading measure) and resizes only downwards.
- **`form_actions(label, cancel_href)`**: the primary button first, then **Cancel** as a link.
  `name` and `value` go on the primary button. `secondary` (`{"label", "name", "value"}`) adds one
  secondary save right after it, for "save and continue with another": **Save question** then
  **Save and add one more question**. There is at most one secondary save; the primary one comes
  first, so Enter submits it, and it leads back to the list.

A message about one field's value (an invalid address, a duplicate name, a wrong code) is a field
error. A limit, an outage or a message about the whole submission is the form error.
_Gallery_: [forms](/admin/components#forms).

### Confirmations (`components/confirmation.html`)

- **`confirmation(question, consequence, action, verb, cancel_href)`**: the question names the
  item ("Delete “Physics”?"), the consequence says what happens, the destructive button repeats
  the verb, then **Cancel**.
- **`refusal(question, reason, back_href, back_text)`**: when the action cannot be done, with the
  reason ("is in use") and the alternative, through `{% call %}` (**Deactivate**).

Every destructive action goes through a confirmation page. _Gallery_:
[confirmations](/admin/components#confirmations).

### Details list (`components/details.html`)

**`details_list(items)`**: label and value pairs, such as a profile or what an invitation will
store. A `None` value is left out; a rich value (a list, a badge) comes through
`{% call(label) %}`. _Gallery_: [details](/admin/components#details).

### Selectors (`components/selectors.html`)

- **`list_detail(...)`**: a list of items beside the selected item's detail, as regions beside
  their educational institutions.
- **`chained_lists(levels, action)`**: lists that narrow each other, each a `GET` form that submits
  itself on change (`auto-submit.js`) and still works without JavaScript, as region → educational
  institution → class. Without JavaScript, each list shows a **Show** button (inside `<noscript>`,
  so it never appears when the script runs).

Reuse these for the subject and class choices of milestones 11 and 12. _Gallery_:
[selectors](/admin/components#selectors).

### Page navigation (`components/pagination.html`)

**`page_navigation(paging, href, noun, label)`** moves through a long list one page at a time
(milestone 11; the paging itself is `app/services/paging.py`). Put it both above and below the
list, labelled "Pages, top" and "Pages, bottom", so the two landmarks can be told apart.

- **The range** comes first, on its own line: "Questions 31–40 of 200".
- **Previous** and **Next** are links; on the first or last page each is plain muted text, never a
  disabled link.
- **The pages**: always the first, the last, the current one and one on each side. A hidden run of
  two or more pages becomes one `…`; a single hidden page is shown, since a gap would take the same
  room. At most seven entries.
- **The current page** is a link marked `aria-current="page"`, bold, with the primary underline of
  the area tabs.
- Every entry keeps the touch target, and it is all plain links: no JavaScript. With no item it
  renders nothing. _Gallery_: [pagination](/admin/components#pagination).

### Icons and identity (`components/icons.html`, `components/palette.html`)

**`logo_mark(size)`** and **`icon(name)`** (`account`, `arrow-left`) are inline SVG, hidden from
assistive technology. **`swatch(token)`** draws a palette chip for the gallery. There is no icon
font or icon library. _Gallery_: [identity](/admin/components#identity).

## 6. Buttons

| Kind | Looks | Use for |
|---|---|---|
| **primary** | solid primary blue | the main action of a page or section: **Save**, **Send code**, **Create subject**. At most one per page or section. |
| **secondary** | surface with a border | other actions: **Cancel** as a button, **Rename**, **Edit**, **Activate**, the role and theme choices |
| **destructive** | red | actions that remove or hide: **Delete**, **Remove**, **Deactivate**, **Withdraw consent** |

- **The kind follows the action, not the element.** A link to a form or a confirmation page is a
  `link_button` of the kind of the action it leads to: **Create subject** is primary, **Delete** in
  a row is destructive.
- **Row actions** are `outline` and `small`, all the same width and gap, together at the end of
  the row.
- **Equal choices** (choosing a role) are all secondary: none is primary.

## 7. Wording patterns

- **Buttons** are verbs, and say what will happen: **Create subject**, **Invite teacher**, **Send
  invitation**, **Add student**. Not "Create", not "OK", not "Submit".
- **Confirmations** ask a question that names the item: "Delete “Physics”?", "Remove Olena
  Kovalenko as a teacher?". The consequence is one plain sentence: "Deleting a subject cannot be
  undone." The button repeats the verb: **Delete**, **Remove**.
- **Refusals** say why, then what to do instead: "“Physics” is in use and cannot be deleted. You
  can deactivate it instead."
- **Errors** say what is wrong and how to fix it, in one sentence: "Enter a valid email address.",
  "A subject named “Physics” already exists.". The summary heading is always "There is a problem".
- **Empty states** say what is missing, then what to do: "No subjects yet" / "Create the first
  subject with Create subject."; "Select a region" / "Choose a region from the list to see its
  educational institutions."
- **Notices** state the outcome: "Invitation sent to olena@example.org".
- **Statuses** use one word each, everywhere: **Active** or **Deactivated**; **Read** or
  **Write**.
- **Row notes** are a short plain phrase, with no full stop: "In this team".
- **Page navigation** says where you are as "<Noun> 31–40 of 200" (an en dash, no spaces), and
  moves with **Previous** and **Next**.

## 8. Phone behaviour

Below 768 px:

- **Tables become cards**: each row a card of labelled values, the actions last, in equal parts
  of the card's width. A row note sits in the card's actions part, where a button would be; a row
  with no action at all has no actions part.
- **The user menu folds** to its account icon, read as "Account menu"; the product name and the
  role stay in the top bar.
- **The selectors stack**: the list above its detail, the chained lists one under another.
- **Everything wraps**: long names, tabs and buttons wrap rather than push the page wider. No page
  scrolls sideways at 375 px. The page navigation wraps onto more rows, each entry keeping its
  touch target, and a long word in a text box wraps inside the box. Two save buttons wrap, each
  with its full label.
- **The area tabs are 44 px tall** (the touch target) and may wrap onto two rows, which keeps the
  pinned frame under a quarter of a 375 × 667 screen.
- **Held sideways**, under 600 px tall, a phone does not pin the frame: it scrolls away, so the
  content keeps the small screen.

Check every new page at 375 px.

## 9. Themes

Light and dark are both complete; **Device**, the default, follows the operating system.

- **How a token gets its dark value**: each colour token is set on `:root` (light) and again under
  `[data-theme="dark"]` and, for a browser that follows its device, under
  `:root:not([data-theme="light"])` inside `@media (prefers-color-scheme: dark)`. A new colour
  token gets all three.
- **How the theme reaches the page**: the server reads the `sc_theme` cookie and renders
  `data-theme` on `<html>`, so there is no flash and no script. The cookie is set by `POST /theme`
  from the theme switch.
- **Check both themes**: open every new page in Light and in Dark (with the switch, or by
  emulating the colour scheme in the browser's developer tools).

## 10. Checks

`tests/unit/test_stylesheet.py` runs in CI and enforces, for every template and `app.css`:

- every class used in a template is defined in `pico.min.css` or `app.css`, and every class in
  `app.css` is used. A class may be built dynamically only inside `components/`, from the literal
  strings of a `{% set …_class = … %}` statement;
- no inline `style`;
- nothing loaded from another site: no absolute `src`, `href` or `action`, no `@import`, and
  `url()` only under `/static/`;
- no literal colour or pixel length outside the token block, apart from the breakpoints;
- body text and line-height tokens at the minimums of section 2;
- emphasis in bold only: no `<i>` or `<u>`, no italic, capitalised or justified text;
- no page-specific class from the milestone 9 stylesheet;
- the busy spinner drawn in the button's own colour, with Pico's white filter cancelled.

`tests/unit/test_frame_stylesheet.py` enforces the pinned frame: `body > .frame` is the only sticky
element, and only on a screen at least 600 px tall; the scroll padding and the field margin come
from the clearance tokens; the skip link stays above the frame; the loading bar stands still under
reduced motion and is hidden in print; the user menu scrolls inside itself; the phone tabs keep the
touch-target height.

`tests/unit/test_loading_script.py` reads `loading-feedback.js` as text. It checks that the script
imports, fetches and stores nothing and names no other site; that it listens for links, forms and
Back or Forward restores, with a 200 ms delay; that it never disables a control (a disabled button
would drop its value from the form); and that it stays small. `tests/integration/test_layout.py`
checks that every kind of page loads it once and has the one frame block with a hidden bar. How the
bar, the busy button and the pinned frame behave in a browser is checked by hand from the
milestone 10.1 quickstart, until end-to-end tests arrive in milestone 16.

`tests/integration/test_page_patterns.py` checks the patterns page by page (error summaries,
confirmations, back links, badges, link buttons), and `tests/html.py` lets tests query pages by
meaning, so a restyle does not break them.

**Adding a pattern**: (1) add the macro to the component library, with its CSS in the Components
section of `app.css`; (2) add it, with every variant, to the gallery
(`pages/admin/components.html`); (3) describe it here; (4) then use it on the page.

## 11. Research for later screens

### Taking a competition (milestone 13)

A student takes a timed, written competition, mostly on a phone. Build it from these findings:

- **A visible countdown.** The remaining time is always visible, in the top part of the screen, in
  minutes and seconds, without scrolling. It warns before the end, for example at 5 minutes and at
  1 minute, with a notice that is announced, not only a colour change.
- **A "Saved" status per answer.** Each answer shows that it is saved ("Saved", with the time) or
  that it is not yet saved, so a student never wonders whether a lost connection lost their work.
- **A clear final Submit.** One primary **Submit** button at the end, and a confirmation page that
  says what cannot be changed afterwards ("You cannot change your answers after you submit.") and
  how many questions are unanswered. Leaving the page is not submitting.
- **One question at a time on a phone**, with a back link to the list of questions, and the
  question text kept with its line breaks.

_Sources_: the GOV.UK Design System guidance on timeouts (warn before the time runs out) and on
"check answers" pages; Nielsen Norman Group on system status visibility (the first usability
heuristic); W3C/WAI *Making Content Usable*, objective 6 (help users avoid mistakes).
