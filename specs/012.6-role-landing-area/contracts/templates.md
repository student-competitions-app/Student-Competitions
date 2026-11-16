# Contract: Templates and Messages (Milestone 12.6)

No new component and no new UI pattern. The component gallery and the component list in the UI
guidelines do not change; only the guidelines' wording about the frame changes (research R9).

## `layouts/base.html`: the footer

- The footer renders the database line **when the context has a truthy `db_status`**:
  `<p data-engine="{{ db_status.engine }}" data-revision="{{ db_status.revision }}"
  data-boots="{{ db_status.boots }}">{{ _("Database: %(engine)s · schema revision %(revision)s · boot
  #%(boots)d", …) }}</p>`, moved unchanged from `pages/home.html`.
- The `footer_extra` block is deleted; it had no other user.

## `pages/home.html` (student only)

- The `footer_extra` override is deleted. The line now comes from the layout.
- Unchanged: the heading, the tagline, "Your areas" with one card per `areas_for(role)`, and the
  unavailable notice when `not data_available`.

## `layouts/admin.html`

Unchanged markup. Every render passes `db_status` through `render_admin`.

## `pages/profile.html`

`{{ back_link(back.path, back.label) }}` replaces `{{ back_link("/", _("Back to the home page")) }}`.

## `pages/error.html`

`<p><a href="{{ back.path }}">{{ back.label }}</a></p>` replaces the fixed link to `/`.

## Deleted

- The Staff area's placeholder render (the `pages/area.html` template stays, because `/student`
  uses it).

## Messages (both catalogues, research R6)

| | msgid | uk |
|---|---|---|
| − | Staff area | Розділ працівників |
| − | Pages shared by administrators and teachers. | Спільні сторінки адміністраторів і педагогів. |
| − | Manage teachers, educational institutions and subjects. | — |
| − | Manage your classes, students and teams, and work with the question bank and competitions. | — |
| + | Back to the administrator area | Назад до розділу адміністратора |
| + | Back to the teacher area | Назад до розділу педагога |

After `scripts/translations.sh update` + `compile`, `tests/unit/test_catalogues.py` passes: every
message is in both catalogues and nothing else, every entry is translated, and English equals the
identifiers.
