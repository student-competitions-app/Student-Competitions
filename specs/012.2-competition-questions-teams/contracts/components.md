# Contract: Components

One new component; one changed page pattern; wording changes in the UI guidelines. Each is added
to the library, the gallery (`/admin/components`) and `docs/requirements/ui-guidelines.md` before a
page uses it (FR-050). See [research.md](../research.md) R15.

## 1. Region group (new): `components/group.html`

```jinja
{% from "components/group.html" import region_group %}
{% call region_group("Kyiv", 14, "region-7-p2") %}
  {% call data_table(["Team", "Educational institution", "Active members", "Actions"]) %}
    <tr id="team-31">…</tr>
  {% endcall %}
{% endcall %}
```

- **Markup**: `<section class="region-group" aria-labelledby="{heading_id}">` with
  `<h2 class="region-group-header" id="{heading_id}">Kyiv · 14 teams</h2>` and the caller's body.
- **The header**: the region's name as stored, " · ", and the total: "1 team", otherwise
  "<n> teams". No other word is added. A long name wraps.
- **Arguments**: `name` (required, refused when empty, as `row_note` refuses), `total` (an integer
  ≥ 1), `heading_id` (unique on the page: a region repeated on the next page gets another page
  suffix).
- **Look**: a box with `--sc-radius-card`, the `--sc-surface` background and a border token, the
  header in the section-heading type size with the card padding; the table inside keeps its own
  look, without a second border. Tokens only; no new token.
- **Phone**: below 768 px the table rows become labelled cards inside the box (the data-table rule),
  with no sideways scroll.
- **Several groups** follow each other with the standard vertical gap.

**Gallery** (`#region-group`): a group of 3 rows with "Kyiv · 14 teams"; a group with "Lviv · 1
team"; a group with a very long region name; a row with `row_note("(deleted)")`; the same section
shown at phone width by the gallery's existing narrow frame, if any, or checked by hand.

**Guidelines**: a "Region group (`components/group.html`)" section after "Data table": when to use
it (one list grouped by a parent, paged across groups), the header format, the repeat on the next
page, "never a table caption for this".

## 2. Actions menu on every row (changed use, unchanged component)

The competitions list passes every row an `actions_menu`:

```jinja
{% call actions_menu(c.name) %}
  {% if can_add and c.status == "upcoming" %}{{ menu_link("Edit", edit_href) }}{% endif %}
  {{ menu_link("Questions", questions_href) }}
  {{ menu_link("Teams", teams_href) }}
  {% if can_add and c.status in ("upcoming", "in_progress") %}{{ menu_link("Cancel competition", cancel_href, destructive=True) }}{% endif %}
{% endcall %}
```

The gallery's actions-menu section gains the full four-entry menu and the two-entry read-only
menu.

## 3. Refusal link text (changed page)

`pages/teacher/competition_refused.html` renders `refusal(question, reason, back, back_text)` and
`back_link(back, back_link_text)` from context values; 12.1 routes pass "Back to competitions" and
"Back to the competitions", the new routes "Back to the competition" and "Back to the questions" /
"Back to the teams". No component changes.

## 4. Existing components used, unchanged

`page_heading` with an action, `details_list` (subject, start, status under the heading),
`text_card` and `text_box`, `data_table`, `cell`, `actions_cell`, `row_note`, `page_navigation`,
`chained_lists` (the **Region** level), `notice`, `empty_state`, `confirmation`, `refusal`,
`back_link`, `local_time`, `competition_status_badge`, `link_button`, `post_button`,
`actions_menu`, `menu_link`.

## 5. UI guidelines changes (`docs/requirements/ui-guidelines.md`)

- **Wording patterns → Menus**: "the entries are verbs, as buttons are: **Edit**, **Cancel
  competition**" becomes "an entry that does something is a verb (**Edit**, **Cancel
  competition**); an entry that only opens a page is named by that page (**Questions**,
  **Teams**); a destructive entry is always a verb".
- **Wording patterns → Row notes**: examples gain "Already in this competition", "Deleted from the
  question bank" and "(deleted)", with the note that a row note may mark a record the row can no
  longer act on; a *status* still takes a badge.
- **Actions menu**: "an empty menu is no menu" stays; the example shows the four entries.
- **Region group**: the new section (§1).
