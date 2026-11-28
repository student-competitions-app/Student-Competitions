# UI Guidelines

These guidelines are binding for every page of Student Competitions. Every later milestone builds
its pages from the component library in `app/templates/components/` and follows the rules below;
its spec and plan are checked against them. A new pattern is first added to the library, the
gallery and this document, and only then used on a page. It is never hand-built on a single page.

They were introduced in milestone 10 ([spec](../../specs/010-design-system-ui-guidelines/spec.md)).
The approved look is the mockup in
[`specs/010-design-system-ui-guidelines/mockup/`](../../specs/010-design-system-ui-guidelines/mockup/index.html).
Its logo mark, an amber spark on a deep-blue tile, was replaced in milestone 12.7 by the engraved
emblem; its review and approval are recorded in
[`specs/012.7-new-logo/design-approval.md`](../../specs/012.7-new-logo/design-approval.md).
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
- Every action that cannot be undone asks for confirmation on its own page, names the item and
  says what will happen.

_Sources_: the GOV.UK Design System error summary, error message and confirmation patterns;
W3C/WAI *Making Content Usable*, objective 6 (help users avoid mistakes and know how to correct
them). Touch targets follow Material Design and the Apple Human Interface Guidelines: at least 44
by 44 px.

### Works before the script runs

- Every page is complete as server-rendered HTML: links, forms and `<details>` menus do the work,
  so reading, navigating and submitting never depend on JavaScript. Our tests check this baseline
  without a browser.
- JavaScript only enhances: it saves a click, shows progress or converts a value for display. A
  script must not be the only way to reach a page, send a form or see a value.
- When the script does not run, the page must stay usable, not polished: a plain **Show** button,
  a time shown in UTC and labelled "UTC", a full page load instead of a partial update.
- This rule applies to every page, so a milestone does not repeat it. It describes what happens
  without the script only where the baseline is not obvious from this rule and the component
  used.

_Sources_: the GOV.UK Service Manual on progressive enhancement (about 1 in 100 visits run no
JavaScript, mostly because a script failed to load, not because it was turned off); school
networks and filters that block scripts, and weak phone connections.

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
| `--sc-accent` | Highlights | `#f2a516` | `#f5b83d` |
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
      linking to `/`, which opens the current role's area (the student's home page for a
      student; milestone 12.6), the current role's label, the **language switch**
      ([gallery: language](/admin/components#language)) and the **user menu**; signed out, the
      brand and the language switch only. The logo mark is the emblem in light ink, the
      touch-target size (44 px) at every width, as tall as the language switch (milestone 12.7);
   2. the **area tabs** of the administrator or teacher area, if the page is in one;
   3. the **loading bar**, hidden until a page load is pending;
4. `<main>`, at the one content width;
5. the **footer**: the version and build, and on the administrator area's pages and the student's
   home page the database line.

The user menu is a native `<details>`, so it opens without JavaScript. It holds, in order, the
email linking to the profile, the role switch (for a person with several roles), the theme switch
and **Log out**. When it is taller than the space below the top bar, it scrolls inside itself.

The language switch (milestone 12.5) is on every page, signed in or out, error pages included,
always just before the user menu, or last when there is none. It is a native `<details>` too.

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
Last measured in milestone 12.7, with the 44 px logo mark: at 360 px, 375 px, 768 px and 1280 px,
signed out and with a role shown, in Ukrainian and in English, the top bar stays one 64 px row. Below 768 px, when
a role is shown, the wordmark is hidden visually (the logo link still reads as the application's
name) and the role label sits beside the mark (milestone 12.5 research R15). The teacher area's
tabs («Учасники · Команди · Питання · Змагання») and the administrator area's («Педагоги · Заклади
освіти · Предмети») wrap onto two rows at 360 × 640 and 375 × 667, and the frame ends at 153 px
(the administrator's at 375 × 667 in Ukrainian, on one row of tabs, at 109 px): under the 176 px of
`--sc-frame-clearance-tabs` and a quarter of a 375 × 667 screen (166.75 px). Without the fallback
the wordmark wrapped onto two lines under the role. At 768 × 1024 and 1280 × 800 the tabs fit on one
row and both areas' frames end at 113 px, under the 128 px it has from 768 px.

**The scripts**: the base layout loads two scripts on every page, each with `defer`, and pages add
nothing; without JavaScript, links and forms work as before.

- **`loading-feedback.js`** shows the loading bar and the busy button (section 5) while the next
  page is on its way.
- **`time-zone.js`** (milestone 12.1) writes the browser's time zone, such as `Europe/Kyiv`, to the
  `sc_time_zone` cookie, so the server shows times in it (see **Local time** in section 5). It sends
  nothing and reloads nothing; without it, times are shown in Kyiv time, labelled "(Kyiv time)"
  (milestone 12.5).

**Inside `<main>`**, in order: the back link (on every page below an area's main page), the page
heading, the error summary or a notice, then the content. A page has one `h1`; sections are `h2`.
One-form public pages (sign-in, code entry, role choice, data deletion) use the `.narrow` centred
column.

**Breakpoints**: three, written as literals. Below `768px`: tables become cards, the user menu
folds to its icon, the language switch folds to its flag, the selectors stack, the area tabs drop to the touch-target height, and h1 and
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
- **`language_switch(current, return_to)`** (milestone 12.5): rendered by `top_bar()` on every page;
  never called by a page. A native `<details>` drawn like a select: the current language's flag and
  name, a border and a chevron. Its panel is one form posting to `POST /language`, with the page's
  return address and two buttons, **Українська** then **English**, each with its flag. No
  JavaScript. The rules:
  - the flags are the SVG files `/static/img/flag-ua.svg` and `flag-gb.svg` (named by country),
    with `alt=""`, sized by `--sc-flag-height`; never emoji;
  - each language is named in its own language and never translated: «Українська» stays Ukrainian
    and "English" stays English on a Ukrainian page; each name carries its own `lang`;
  - the current language is marked with `aria-current="true"`;
  - below 768 px the summary shows the flag alone, the name hidden visually but still read; each
    option is a 44 px touch target.
- **`area_tabs(tabs, active, label)`**: rendered by `layouts/admin.html` and `layouts/teacher.html`.
  A new tab is added to `ADMIN_TABS` or `TEACHER_TABS`, never drawn by a page.
- **`back_link(href, text)`**: first in `<main>` on every page below an area's main page. The
  target is a fixed address that keeps the page's selection, never the browser's history. The text
  is "Back to {parent}": "Back to the subjects", "Back to “Kyiv”". The profile page and the error
  page lead back to the current role's area, "Back to the administrator area" or "Back to the
  teacher area", and to the home page for a student or when the role is not known (milestone 12.6).
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

_Gallery_: [frame](/admin/components#frame), [language switch](/admin/components#language),
[section heading](/admin/components#section-heading), [loading feedback](/admin/components#loading).

### Buttons (`components/button.html`)

- **`button(label, kind, …)`**: a submit button inside a form.
- **`link_button(label, href, kind, …)`**: a link that opens a form or a confirmation page. It
  looks like the action it leads to.
- **`link_button(..., download=True)`** (milestone 12.10): a download outside a menu, such as
  **Download study materials** beside the subject list. It follows the download rule of the actions
  menu: a link marked as a download, never through a page in between, no loading feedback. It is of
  the secondary kind (outline and small beside a list), never primary and never destructive.
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
the whole card is the link, as on the student's home page. Use it for entries the person chooses between, or
to frame one block (a consent record). Do not use it for a list of records: that is a data table.
_Gallery_: [cards](/admin/components#cards).

**`text_card(heading, id=None, badge=None)`** with **`text_box(label, text)`** holds long entered
texts, such as a question with its reference answer (milestone 11). The card is one surface with a
heading ("Question 57"); with `badge` (milestone 12.9), a rendered badge such as `additional_badge()`,
the badge follows the heading's text inside the heading, on the same line where it fits and wrapping
below it on a narrow screen, so it is read with the heading ("Question 57 Additional"). A page passes
`badge=additional_badge() if q.is_additional else none`, and only a teacher with **Can manage
competitions** is ever given a question that is additional. Its body, through `{% call %}`, is one or
more boxes, each a quieter tint with a small label, stacked at full width on every screen, then any `row-actions`. The texts keep their
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

**`cell(label, value, nowrap=True)`** (milestone 12.3) keeps a short value that must not break on
one line beside long names, such as a team's progress "3 of 6"; on a phone it is a labelled line of
the card as any other. Never for a name or a text.

**`row_note(text)`** stands in the actions cell where a row's action is not available, as "In this
team"; muted text, never a disabled button.

From 768 px the table's corner cells carry the card's radius; the table itself does not clip its
content (`overflow: hidden`), so an open actions menu is never cut off.

_Gallery_: [table](/admin/components#table).

### Region group (`components/group.html`)

**`region_group(name, total, heading_id)`** is one list grouped by a parent and paged across the
groups, such as a competition's teams by region (milestone 12.2). Each group on the page is a box
with a header over the `data_table` of its rows on that page, written in the `{% call %}` block.

```jinja
{% call region_group("Kyiv", 14, "region-7-p2") %}
  {% call data_table(["Team", "Educational institution", "Active members", "Actions"]) %}
    <tr id="team-31">…</tr>
  {% endcall %}
{% endcall %}
```

- **The header** reads "<name> · <n> teams", or "<name> · 1 team" for one: the name as it is
  stored, with no word added, and the group's total across all pages, not the rows on this page.
  It is the section's `h2`, which labels it (`heading_id`); a long name wraps.
- **The next page**: a group that continues there shows its header again, with the same total.
  Every `heading_id` is unique on the page, so a group repeated on another page gets another one
  (`region-7-p2`).
- **Never a table caption for this**: the header is the group's heading, and the table inside keeps
  its own look, without a second border.
- **On a phone** the table's rows become labelled cards inside the box, with no sideways scroll.

The name is required and the total is at least 1. _Gallery_: [region group](/admin/components#region-group).

### Actions menu (`components/menu.html`)

**`actions_menu(item_name, label="Actions")`** with **`menu_link(label, href, destructive=False,
download=False)`** puts a row's actions behind one button, in the row's actions cell, when the row
has more actions than fit a phone card (the **Competitions** tab, milestone 12.1). It is a native
`<details>`, like the user menu, so it opens and closes without JavaScript.

```jinja
{% call actions_cell() %}
{%- call actions_menu(c.name) -%}
{% if can_add and c.status == "upcoming" %}{{ menu_link("Edit", edit_href) }}{% endif %}
{% if can_manage %}{{ menu_link("Questions", questions_href) }}{% endif %}
{{ menu_link("Teams", teams_href) }}
{% if c.status in ("in_progress", "finished", "published") %}{{ menu_link("Answers", answers_href) }}{% endif %}
{% if c.status in ("in_progress", "finished", "published") %}{{ menu_link("Download questions", questions_file_href, download=True) }}{% endif %}
{% if can_manage and c.status in ("finished", "published") %}{{ menu_link("Grades", grades_href) }}{% endif %}
{% if can_manage and c.status == "finished" %}{{ menu_link("Publish results", publish_href) }}{% endif %}
{% if c.status == "published" %}{{ menu_link("Download results", results_href, download=True) }}{% endif %}
{% if can_manage and c.status == "in_progress" %}{{ menu_link("Finish competition", finish_href) }}{% endif %}
{% if can_add and c.status in ("upcoming", "in_progress") %}{{ menu_link("Cancel competition", cancel_href, destructive=True) }}{% endif %}
{%- endcall -%}
{% endcall %}
```

- **The button** reads "Actions" and is announced "Actions for “Spring round”"; the item name is
  required. It is a small outline secondary button with a chevron, a full touch target.
- **The entries** come in a fixed order, each where it is available: on the **Competitions** tab
  **Edit**, **Questions**, **Teams**, **Answers**, **Download questions**, **Grades**, **Publish
  results**, **Download results**, **Finish competition**, **Cancel competition** (milestones
  12.2–12.4, 12.8 and 12.10). **Questions** is only for teachers with **Can manage competitions**
  (milestone 12.10); **Download questions** is for every teacher once a competition has started.
  **Finish competition** and **Publish results** are not destructive: they cannot be undone, but
  each is the normal next step of the work. On the administrator's **Subjects** tab (milestone
  12.11): **Rename**, **Export questions** (a download), **Import questions** (destructive),
  **Deactivate** (destructive) or **Activate**, **Delete** (destructive). **Deactivate** and
  **Activate** open their confirmation pages, like every entry that changes something.
- **A download** (milestone 12.8) is an entry like any other, a link marked as a download
  (`download=True`, the HTML `download` attribute). It is offered this way, never through a page in
  between: the browser saves the file at once and the person stays where they were. It starts no
  loading feedback (the loading script skips `a[download]`), and it is never destructive.
- **Every entry** is a link to a page (a list, a form or a confirmation), never a `POST`, so every destructive
  action still goes through its confirmation. A destructive entry is in the danger colour. Each
  entry is 44 px tall and as wide as the panel; a long label wraps.
- **The panel** opens under the button, aligned to its right edge, over the rows below and under the
  pinned frame. The menus of a page are one group (`name="row-actions"`): where the browser supports
  it, opening one closes the others.
- **An empty menu is no menu**: when the call block renders only white space, nothing is emitted,
  so a row with no action has an empty actions cell, which a phone card hides.

_Gallery_: [actions menu](/admin/components#actions-menu).

### Badges (`components/badge.html`)

**`status_badge(is_active)`** gives **Active** or **Deactivated**; **`access_badge(level)`**
gives **Read** or **Write**; **`competition_status_badge(status)`** (milestone 12.1) gives
**Upcoming** (`info`), **In progress** (`success`), **Finished** (`neutral`), **Published**
(`accent`, milestone 12.8: a finished competition whose results are published) or **Cancelled**
(`muted`), in the order of the status filter, and refuses any other value. **`additional_badge()`**
(milestone 12.9) gives **Additional** (`info`), the mark of an additional question, which only teachers
allowed to manage competitions see: it is the mark of a record, not a status, and goes in the heading
of the question's text card (see Cards). **`badge(text, kind)`** is for a new status, or a new mark of
a record, with its own word; an empty text is refused. Use a badge for every status and every such
mark, never coloured text or "(deactivated)".
_Gallery_: [badges](/admin/components#badges).

### Feedback (`components/feedback.html`)

- **`notice(text, kind)`**: `success` after an action ("Invitation sent to …"), `error` for a
  refusal that is not about a form field (an expired link), `info` for a state the person should
  know about (a deactivated region, data temporarily unavailable). An error notice is an alert;
  the others are a status.
- **`empty_state(message, hint)`**: in place of an empty list or an unmade choice. The hint is one
  line saying what to do next.

_Gallery_: [notices](/admin/components#notices), [empty states](/admin/components#empty-states).

### Local time (`components/time.html`)

**`local_time(moment, zone=time_zone)`** (milestone 12.1) shows a stored time in the person's time
zone, in the page's language: `<time datetime="2027-03-14T08:00Z">14 March 2027, 10:00</time>`,
«14 березня 2027, 10:00». The zone comes from the `sc_time_zone` cookie, which `time-zone.js`
writes; when no zone is known (milestone 12.5), the time is shown in Kyiv time, labelled: "14 March
2027, 10:00 (Kyiv time)", «14 березня 2027, 10:00 (за київським часом)». Import it `with context`.
Every stored time is UTC and every conversion is on the server; the browser only says which zone it
is in. The `datetime` attribute is always UTC.

**`local_date(moment, zone=time_zone)`** (milestone 12.5) shows the date alone, with no label, in
the same zone (Kyiv when unknown): `<time datetime="2026-10-15">15 October 2026</time>`, «15 жовтня
2026». Use it where only the day matters, such as a date of consent.

**Emails** always use Kyiv time, labelled in the email's language.

The day has no leading zero, the month is written out (in Ukrainian in the genitive: «березня»), the
clock is 24-hour. Month names come from the catalogue, never from the process locale. No page shows
"UTC" or a `2026-10-22` style date.

**A time inside a heading** (a confirmation's question): capture the heading with
`{% set question %}Cancel competition “{{ c.name }}”, starting {{ local_time(c.starts_at) }}?{% endset %}`
and pass `question` on. It is still template content, escaped by autoescape; never build it as a
string in Python. The page's `<title>` leaves the time out.

_Gallery_: [time](/admin/components#time) (both macros).

### Forms (`components/form.html`)

Every form page passes `values` (what was entered, by field id), `errors` (field id → message) and
`form_error` (a message about the whole submission). Then:

- **`error_summary(errors, form_error, order)`** sits under the `h1`. It renders nothing without
  errors.
- **`field`**, **`select_field`** and **`checkbox_field`** give each field its label, optional
  hint, its error and the entered value.
- **`select_field(..., groups=())`** also takes option groups, `(label, options)` pairs, each an
  `<optgroup>` after the plain options, as "Deactivated subjects" on **Competitions**.
- **`date_time_fields(prefix, legend, values, errors, zone_label)`** (milestone 12.1) is a date and
  a time entered as a pair, in a `<fieldset>` with the legend ("Start"): "Start date"
  (`type="date"`, `<prefix>_date`) and "Start time" (`type="time"`, `<prefix>_time`), each with its
  own error. The hint under the time names the zone the entry is read in, "Time zone:
  Europe/Kyiv", and a hidden `time_zone` field carries it, so the server reads the entry in the
  zone the form was shown in. Side by side from 768 px, stacked below. The browser's own pickers do
  the rest.
- **`textarea_field`** is the multi-line twin of `field`, for text that may run over several lines
  (a question, a reference answer). It keeps the value exactly, line breaks included, is wider than
  a single-line field (the reading measure) and resizes only downwards.
- **`placeholder`** (milestone 12.3), an argument of `field` and `textarea_field`, only says that
  the field is empty: "Not answered". The label and the hint are rendered as without it; see
  **Placeholders** under Wording patterns.
- **`form_actions(label, cancel_href)`**: the primary button first, then **Cancel** as a link.
  `name` and `value` go on the primary button. `secondary` (`{"label", "name", "value"}`) adds one
  secondary save right after it, for "save and continue with another": **Save question** then
  **Save and add one more question**. There is at most one secondary save; the primary one comes
  first, so Enter submits it, and it leads back to the list.
- **`file_field(id, label, error, hint, accept)`** (milestone 12.11) is the browser's own file
  control with its label, hint and error, as wide as a single-line field. It is never refilled: a
  browser cannot set a file field's value, so after an error the person chooses the file again,
  and the page says nothing more about it. Its form is `multipart/form-data`. _Gallery_: [file
  field](/admin/components#file-field).
- **Row errors** (milestone 12.11): `error_summary(errors, row_errors=[…], more=n)` also lists
  errors about the rows of an uploaded file. An error about a field (no file chosen, the file is
  too large) is a field error, linked to the field; an error about a row names its row as a
  spreadsheet shows it, "Row 7: Enter the reference answer.", and is not linked, since no field
  holds it. At most 20 errors are listed in all, in row order and, within a row, in column order;
  `more` is how many were left out, said after the list: "And 5 more errors.".

A message about one field's value (an invalid address, a duplicate name, a wrong code) is a field
error. A limit, an outage or a message about the whole submission is the form error.
_Gallery_: [forms](/admin/components#forms).

### Answer sheet (`components/answer_sheet.html`)

**`answer_sheet(items, action, hidden, submit_label="Save answers")`** shows every answer of one
participant to a list of questions, saved at once: a team's answers in a competition (milestone
12.3; the students' own sheet in milestone 13 is the same).

```jinja
{{ error_summary(errors, order=field_order) }}
{{ answer_sheet(items, "/teacher/competitions/17/answers/31", hidden) }}
```

- **Each question** is a numbered text card, "Question 3", holding the question's text and, under
  it, its answer field "Answer to question 3" with the hint "Up to 2,000 characters.", the
  placeholder "Not answered" and the 2,000-character limit (the server checks it again).
- **One primary save button** below the list, **Save answers**, and no **Cancel**: the back link
  above the page leads away. Every question is on the one page, with no page navigation.
- **Errors**: each field shows its own message, and the page's `error_summary` under its heading
  links to each field, in the order of the questions. A refused save shows every text as it was
  sent.
- **Never a reference answer** on a sheet.
- **No question**: the page shows its empty state instead; an empty list is refused.

_Gallery_: [answer sheet](/admin/components#answer-sheet).

### Grading sheet (`components/grading_sheet.html`)

**`grading_sheet(items, action, hidden, submit_label="Save grades")`** is the answer sheet's
counterpart for the person who grades: every question of one participant's answers with its
reference answer, and a grade under each answer, saved at once (a team's answers in a finished
competition, milestone 12.4). **`answers_read_only(items, grades=True)`** shows the same answers
to someone who may only read them.

```jinja
{{ error_summary(errors, order=field_order) }}
{{ grading_sheet(items, "/teacher/competitions/17/grades/31", hidden) }}
```

- **Each question** is a numbered text card, "Question 3", holding the question's text, its
  **Reference answer** (always shown on the grading sheet), then the answer, "Answer to question 3",
  and under it the field "Grade for question 3" with the hint "A whole number from 0 to 10." and
  the placeholder "Not graded".
- **A question with no answer** shows the plain text "Not answered" and no field: there is nothing
  to grade. When no question is answered there is no form and no button.
- **The grade field** is a text field with `inputmode="numeric"`, not a number field: the phone
  opens the digit keypad, and a typed "7.5" or "seven" reaches the server and gets its error
  instead of being dropped by the browser. The server checks the value: "Enter a whole number from
  0 to 10.".
- **One primary save button** below the list, **Save grades**, and no **Cancel**. Errors as on the
  answer sheet: each field shows its own message, the summary links to each, in question order,
  and a refused save shows every value as it was sent.
- **The read-only variant** shows the question and "Answer to question 3" (or "Not answered"); with
  `grades`, under each answered question "Grade: 7 of 10" or "Not graded yet". Never a reference
  answer, no form, no field, no button.
- **Once the results are published** (milestone 12.8), the grading sheet itself is read-only:
  `grading_sheet(..., read_only=True, note=…)`. The note says why ("The results of “Spring round”
  are published, so its grades can no longer be changed."), the reference answers stay (it is still
  the grader's view), each grade is text ("Grade: 7 of 10"), and there is no field, no error and no
  button.
- **On a phone** the cards are one column and each grade field takes the card's full width; on a
  wide screen it is a short field.

_Gallery_: [grading sheet](/admin/components#grading-sheet).

### Confirmations (`components/confirmation.html`)

- **`confirmation(question, consequence, action, verb, cancel_href, back_label="Cancel",
  kind="destructive", blocked=None, alternative=None)`**: the question names the item ("Delete
  “Physics”?"), the consequence says what happens, the button repeats the verb, then **Cancel**.
  Whenever the verb ends something, the link back says what is kept instead: **Cancel
  competition** and **Keep competition**, **Finish competition** and **Keep in progress**,
  **Publish results** and **Keep unpublished** (`back_label`).
- **`kind`**: the button is destructive (the default) when the action removes, hides or calls off
  something (**Delete**, **Deactivate**, **Withdraw consent**, **Cancel competition**), and primary
  (`kind="primary"`) when it is the normal next step of the work (**Finish competition**,
  **Publish results**).
- **Blocked** (milestone 12.8): when an action cannot be taken yet because work is left to do, its
  confirmation page says what is left and links to it, and has no confirming button. `blocked` is
  the reason, shown as a notice in place of the button ("Every team must be graded before the
  results can be published."); `alternative` is the link to the work left (**Grade the remaining
  teams**), shown before the link back. Only a primary confirmation can be blocked: a destructive
  action is never waiting for work.
- **With a form** (milestone 12.11): a confirmation whose action needs input, such as a file,
  holds the input inside its own form. `form_content=True` puts the `{% call %}` block (the
  explanation and the fields) and the buttons in one `<form method="post">`, between the
  consequence and the buttons; `sends_file=True` makes it `multipart/form-data`; `summary` is the
  page's `error_summary(...)`, placed right under the question as on every form page. The button
  still repeats the verb (**Replace questions**), and **Cancel** still leads back. A blocked
  confirmation has no form. Used by **Import questions** on the **Subjects** tab. _Gallery_:
  [confirmation with a form](/admin/components#confirmation-with-form).
- **`refusal(question, reason, back_href, back_text)`**: when the action cannot be done, with the
  reason ("is in use") and the alternative, through `{% call %}` (**Deactivate**).

Every action that cannot be undone goes through a confirmation page. _Gallery_:
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
  so it never appears when the script runs). A level may carry `groups`, `(label, options)` pairs
  shown as option groups after its plain options (milestone 12.1).
- **`chained_lists(levels, action, aside=...)`** (milestone 12.10): a chained list may carry one
  aside, a link about the chosen value such as a download (`link_button(..., download=True)`). It is
  one more cell of the lists' grid: beside the lists on a wide screen, level with the bottom of the
  selects, and below them on a phone. It is never a primary action, and a page gives it only when
  the chosen value allows it (on the **Competitions** tab, an active subject).

Reuse these for the subject and class choices of milestones 11 and 12. _Gallery_:
[selectors](/admin/components#selectors).

### Filter links (`components/filter.html`)

**`filter_links(links, label)`** is a short row of links above a list, each one a filter of the
list below, such as **All teams** and **Ungraded only** on a competition's Grades page (milestone
12.4). `links` is a list of `(text, href, current)`, exactly one current; `label` names the
landmark ("Show").

- **Following a link** goes to page 1 of that filter; the filter travels in the address, so the
  page navigation and the links back keep it.
- **The current filter** is marked `aria-current="true"`, not `"page"`: on page 3 of a filter its
  link leads to page 1, so it is not the current page, and the page navigation already marks the
  current page. It is drawn like the current page: bold, with the primary underline.
- Plain links with the touch target: no JavaScript and no **Show** button.

_Gallery_: [filter links](/admin/components#filter-links).

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

**`logo_mark(size, theme, top_bar)`** shows the emblem as an image, from
`app/static/img/logo/`, which `scripts/make_logo.py` writes; it is no longer inline SVG. The
emblem's letters ЯНМ are solid ink and its ornament is engraved, partly transparent, in both inks.
The browser and device icons (the favicons, the Apple touch icon and the manifest's icons) show the
letters ЯНМ alone, without the ornament, in light ink on deep blue: at a tab's or a home screen's
size the whole emblem blurs into a shape. The marks in the pages always show the whole emblem. On the
top bar (`top_bar=True`, no size) the mark is always light ink, 44 px (the touch
target) at every width. Elsewhere it follows the `theme` it is given, with no script: dark ink in **Light**, light ink in **Dark**,
and for **Device** a `<picture>` whose `prefers-color-scheme: dark` source holds the light ink. Each
of its sizes (`sm` 1.5rem, `md` 2rem, `lg` 4rem) is sharp at 1×–3× density, and each mark loads one
file. **`icon(name)`** (`account`, `arrow-left`) stays inline SVG and draws in the current text
colour. Both are hidden from assistive technology. **`swatch(token)`** draws a palette chip for the
gallery. There is no icon font or icon library. _Gallery_: [identity](/admin/components#identity).

## 6. Buttons

| Kind | Looks | Use for |
|---|---|---|
| **primary** | solid primary blue | the main action of a page or section: **Save**, **Send code**, **Create subject**. At most one per page or section. |
| **secondary** | surface with a border | other actions: **Cancel** as a button, **Rename**, **Edit**, **Activate**, the role and theme choices |
| **destructive** | red | actions with a high impact that cannot be reverted and that the person may regret: they remove, hide or call off something (**Delete**, **Remove**, **Deactivate**, **Withdraw consent**, **Cancel competition**) |

- **The kind follows the action, not the element.** A link to a form or a confirmation page is a
  `link_button` of the kind of the action it leads to: **Create subject** is primary, **Delete** in
  a row is destructive.
- **An action that cannot be undone but is the normal next step of the work** (**Finish
  competition**) is primary, not destructive; its confirmation page still asks first.
- **Row actions** are `outline` and `small`, all the same width and gap, together at the end of
  the row.
- **Equal choices** (choosing a role) are all secondary: none is primary.

## 7. Wording patterns

- **Buttons** are verbs, and say what will happen: **Create subject**, **Invite teacher**, **Send
  invitation**, **Add student**. Not "Create", not "OK", not "Submit".
- **Confirmations** ask a question that names the item: "Delete “Physics”?", "Remove Olena
  Kovalenko as a teacher?". The consequence says plainly what will happen in one to three short
  sentences, the first saying what happens to the item: "Deleting a subject cannot be undone." The
  button repeats the verb: **Delete**, **Remove**.
- **Refusals** say why, then what to do instead: "“Physics” is in use and cannot be deleted. You
  can deactivate it instead."
- **Errors** say what is wrong and how to fix it, in one sentence: "Enter a valid email address.",
  "A subject named “Physics” already exists.". The summary heading is always "There is a problem".
- **Empty states** say what is missing, then what to do: "No subjects yet" / "Create the first
  subject with Create subject."; "Select a region" / "Choose a region from the list to see its
  educational institutions."
- **Notices** state the outcome: "Invitation sent to olena@example.org", "The results of “Spring
  round” were published".
- **Statuses** use one short term each, everywhere: **Active** or **Deactivated**; **Read** or
  **Write**; **Upcoming**, **In progress**, **Finished**, **Published** or **Cancelled**.
- **A refusal for the status** gives the reason for that status, in one sentence: "“Spring round”
  has not started yet, so it has no results to publish.", "The results of “Spring round” are already
  published.".
- **Times** read "14 March 2027, 10:00" in the person's zone (the day without a leading zero, the
  month in full, a 24-hour clock), and "14 March 2027, 10:00 (Kyiv time)" when the zone is not
  known. A form names its zone under the time field: "Time zone: Europe/Kyiv".
- **Menus**: the button reads "Actions" and is announced "Actions for “<item>”"; an entry that does
  something is a verb (**Edit**, **Cancel competition**); an entry that only opens a page is named
  by that page (**Questions**, **Teams**); a destructive entry is always a verb.
- **Row notes** are a short plain phrase, with no full stop: "In this team", "Already in this
  competition", "Deleted from the question bank", "(deleted)". A row note may also mark a record
  the row can no longer act on, such as a deleted team in a finished competition; a *status*
  (Active, Upcoming…) still takes a badge, and so does the **Additional** mark of a question.
- **Page navigation** says where you are as "<Noun> 31–40 of 200" (an en dash, no spaces), and
  moves with **Previous** and **Next**.
- **Placeholders** only say that a field is empty: "Not answered". A placeholder never replaces the
  field's label or hint, and never holds an example, an instruction or a value.

### In Ukrainian (milestone 12.5)

Ukrainian is the default language; every pattern above has its Ukrainian form, written with the
glossary below and these rules (FR-030–FR-034):

- **Typography**: quotation marks «…», with „…“ inside them; the apostrophe is ʼ (U+02BC), never
  `'` or `’`.
- **Names stay as entered**, in the nominative. A name follows a noun in the case the sentence
  needs, in quotation marks: «Видалити предмет «Фізика»?», «Назад до регіону «Київ»». A person's
  name follows a colon: «Вилучити зі списку: Олена Коваленко?».
- **No guessed gender**: nothing agrees with another person's gender. The inviter is named in the
  present tense: «Олена Коваленко запрошує вас». Statuses are impersonal forms (Заплановано,
  Триває, Деактивовано) or agree with the record's noun, never with a person.
- **The reader is «ви»**, always: never «ти».
- **Counts** use the three Ukrainian forms: «1 команда», «2 команди», «5 команд»; never a form
  chosen by comparing with 1.

| Pattern | English | Ukrainian |
|---|---|---|
| Button | **Create subject** | **Створити предмет** |
| Confirmation | "Delete “Physics”?" | «Видалити предмет «Фізика»?» |
| Refusal | "“Physics” is in use and cannot be deleted." | «Предмет «Фізика» використовується, тому його не можна видалити.» |
| Error | "Enter a valid email address." | «Введіть дійсну адресу електронної пошти.» |
| Error summary | "There is a problem" | «Виникла проблема» |
| Empty state | "No subjects yet" | «Предметів ще немає» |
| Notice | "Invitation sent to olena@example.org" | «Запрошення надіслано на адресу olena@example.org» |
| Back link | "Back to “Kyiv”" | «Назад до регіону «Київ»» |
| Time | "14 March 2027, 10:00 (Kyiv time)" | «14 березня 2027, 10:00 (за київським часом)» |
| Page navigation | "Teams 31–40 of 200" | «Команди 31–40 із 200» |
| Menu | "Actions for “Spring final”" | «Дії для «Spring final»» |

### Glossary

Approved by the product owner on 2026-11-15. Every Ukrainian text uses these terms.

| English | Ukrainian |
|---|---|
| Student Competitions | Студентські змагання |
| Administrator | Адміністратор |
| Teacher (role) | Педагог |
| Student (role) | Студент |
| educational institution | заклад освіти |
| region | регіон |
| subject | предмет |
| class | група |
| team | команда |
| question bank | банк питань |
| reference answer | еталонна відповідь |
| competition | змагання |
| Upcoming / In progress / Finished / Published / Cancelled | Заплановано / Триває / Завершено / Опубліковано / Скасовано |
| results (published, milestone 12.8) | результати |
| Active / Deactivated (per kind of record, `pgettext(kind, …)`) | Активний (предмет, регіон, заклад освіти), Активна (група) / Деактивовано |
| Read / Write (access) | Перегляд / Редагування |
| Can manage competitions | Може керувати змаганнями |
| Students / Teams / Questions / Competitions (tabs) | Учасники / Команди / Питання / Змагання |
| Teachers / Educational institutions / Subjects (tabs) | Педагоги / Заклади освіти / Предмети |
| Grades, Score | Оцінки, Бал |
| Sign in / Log out | Увійти / Вийти |
| Profile | Профіль |
| Withdraw consent / Delete my data | Відкликати згоду / Видалити мої дані |
| Kyiv time | за київським часом |
| Export questions / Import questions / Replace questions (milestone 12.11) | Експортувати питання / Імпортувати питання / Замінити питання |
| CSV file | файл CSV |
| Row N: … (an error in a row of a file) | Рядок N: … |

The tab "Students" is «Учасники» on purpose: it lists every participant a teacher manages and is
short; the role itself is «Студент».

## 8. Phone behaviour

Below 768 px:

- **Tables become cards**: each row a card of labelled values, the actions last, in equal parts
  of the card's width. A row note sits in the card's actions part, where a button would be; a row
  with no action at all has no actions part. An actions menu takes the whole actions part, and its
  panel opens within the card, each entry 44 px tall.
- **The user menu folds** to its account icon, read as "Account menu"; the role stays in the top
  bar, beside the logo. With a role shown, the wordmark is hidden visually (the logo link still
  reads as the product name), so the top bar keeps one row (milestone 12.5); signed out, the
  wordmark shows.
- **The language switch folds** to its flag; the language's name is hidden visually and still
  read, and each of its two options is a 44 px row. The theme switch stays in the user menu and
  under the sign-in form.
- **The selectors stack**: the list above its detail, the chained lists one under another.
- **Everything wraps**: long names, tabs and buttons wrap rather than push the page wider. No page
  scrolls sideways at 375 px. The page navigation wraps onto more rows, each entry keeping its
  touch target, and a long word in a text box wraps inside the box. Two save buttons wrap, each
  with its full label.
- **The answer sheet stays one column**: each question card with its answer field under the text,
  the save button below the list.
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

## 10. Languages

The application speaks Ukrainian by default and English on request (milestone 12.5). Every page and
email is written in the browser's chosen language; what people enter is shown as entered, never
translated.

**Message rules** (binding for every milestone):

1. **The identifier is the English wording**, exactly as shown in English.
2. **Whole messages only**: never join translated pieces, never insert a translated word into
   another message to make a sentence. A parameter may be a translated value only when it stands
   on its own (a status, a role, an access level).
3. **Named placeholders**: `%(name)s`; counts with `ngettext` / `_n` and `%(num)d`; a literal `%`
   is `%%`.
4. **User content is a parameter**, never translated, inserted unchanged. In Ukrainian it follows a
   noun in the needed case, in «…», or a colon for a person.
5. **Contexts** (`pgettext`, `_p`) when one English wording needs two Ukrainian ones: an access
   level **Read** and another "Read", month names, "Delete “%(name)s”?" for each kind of record.
6. **Developer-only text stays plain English** and is not marked: component contract errors, log
   lines, `/healthz`.
7. **No gendered word about another person** in Ukrainian; the reader is «ви».
8. **The gallery's content is not marked**: `pages/admin/components.html` and its router stay
   English, while its frame follows the language.

**In a template**: `{{ _("Delete “%(name)s”?", name=subject.name) }}`,
`{{ ngettext("%(num)d team", "%(num)d teams", total) }}`, `{{ pgettext("class", "Active") }}`.
**In Python**: `_`, `_n` and `_p` from `app.core.i18n` give a `Text`, translated when the page is
rendered or the email written; never `str()` it earlier.

**The catalogue workflow** (README "Translations"): `scripts/translations.sh update`, translate the
new entries of `app/locale/uk/LC_MESSAGES/messages.po` with the glossary (section 7) and clear
"fuzzy", `scripts/translations.sh compile`, run the tests. English is filled from the identifiers.

**Check every page in both languages**: switch with the language switch, or send `sc_lang=uk` /
`sc_lang=en`.

## 11. Checks

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
milestone 10.1 quickstart, until end-to-end tests arrive in milestone 15.

`tests/unit/test_time_zone_script.py` reads `time-zone.js` as text (milestone 12.1). It checks that
the script imports, fetches and stores nothing but the one cookie and names no other site; that it
writes only `sc_time_zone`, with `Path=/`, `SameSite=Lax`, a one-year `Max-Age` and `Secure` over
HTTPS; that it checks the zone name before writing it; and that it stays small.
`tests/integration/test_layout.py` checks that every kind of page loads it once, after
`loading-feedback.js`.

**Languages** (milestone 12.5):

- `tests/unit/test_catalogues.py`: every marked message is in both catalogues, translated in every
  plural form, not fuzzy, with the same placeholders as its identifier; nothing obsolete; nothing
  from the gallery.
- `tests/unit/test_template_text.py`: no English letters left in a template's text or in its
  `aria-label`, `title`, `alt` and `placeholder` values, outside a marked message (the gallery
  aside); no `ua` used as a language code.
- `tests/unit/test_ukrainian_wording.py`: the Ukrainian catalogue uses ʼ and «…», no gendered past
  form about another person, no «ти», and the glossary's terms.
- The sort-key guard in `tests/unit/test_name_order.py`: no list is ordered by `.casefold()` or by
  the stored duplicate key; names sort in the Ukrainian alphabet.

`tests/integration/test_page_patterns.py` checks the patterns page by page (error summaries,
confirmations, back links, badges, link buttons), and `tests/html.py` lets tests query pages by
meaning, so a restyle does not break them.

**Adding a pattern**: (1) add the macro to the component library, with its CSS in the Components
section of `app.css`; (2) add it, with every variant, to the gallery
(`pages/admin/components.html`); (3) describe it here; (4) then use it on the page.

## 12. Research for later screens

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
