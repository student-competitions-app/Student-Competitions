# Components: Additional Questions (Milestone 12.9)

Two additions to the component library. Each is shown in the gallery (`/admin/components`) and is
described in `docs/requirements/ui-guidelines.md` (already updated in `3a4e5bb`) before any page
uses it (constitution Principle II; spec FR-028–FR-030). Decisions:
[research.md](../research.md) R7, R8.

## 1. `additional_badge()` (`components/badge.html`, new)

```jinja
{% macro additional_badge() -%}
{{ badge(pgettext("question", "Additional"), "info") }}
{%- endmacro %}
```

- **Word**: **Additional** / «Додаткове». The context `question` lets the Ukrainian agree with
  «питання».
- **Kind**: `info` (`--sc-primary-tint` / `--sc-primary`), the existing `.badge-info` rule. No new
  token or CSS.
- **Meaning**: the mark of a record, not a status (ui-guidelines §Badges). It is shown only to
  teachers with **Can manage competitions**; the pages decide that, the macro does not.
- **Gallery**: the badges section gains a third row, under the heading "Marks", with
  `additional_badge()`.

## 2. `text_card(heading, id=None, badge=None)` (`components/card.html`, changed)

```jinja
{% macro text_card(heading, id=None, badge=None) -%}
<article class="text-card"{% if id %} id="{{ id }}"{% endif %}>
  <h3>{{ heading }}{% if badge %} {{ badge }}{% endif %}</h3>
  {{ caller() }}
</article>
{%- endmacro %}
```

- **`badge`**: a rendered badge, for example `badge=additional_badge()`, which is already
  markup. With no badge the output is byte-for-byte what milestone 11 renders.
- **Layout**: the badge follows the heading's text after one space, inside the `h3`. It is read
  with the heading ("Question 57 Additional"). It stays on the heading's line where it fits and
  wraps below the text as one unit on a narrow screen (`.badge` is `inline-block` and `nowrap`).
  No sideways scrolling at 360 px.
- **Anchor**: `id` still targets the card (`#question-58`) and lands below the pinned frame
  (milestone 10.1).
- **CSS**: none expected. If the 360 px check shows the badge too close to the text, one token-only
  rule is allowed: `.text-card h3 .badge { margin-inline-start: var(--sc-space-1); }`, then the
  stylesheet checks (`test_stylesheet`, `test_frame_stylesheet`).
- **Gallery**: the "Text cards" list shows "Question 58" with `badge=additional_badge()`, keeping
  its long-word sample, so the badge is seen beside a heading over long text.

## 3. Pages that use them

| Page | Template | Badge shown when |
|---|---|---|
| **Questions** tab | `pages/teacher/questions.html` | `q.is_additional` (only teachers with the setting are given additional questions) |
| **Add questions** | `pages/teacher/competition_questions_add.html` | `q.is_additional` |
| A competition's **Questions** | `pages/teacher/competition_questions.html` | `q.is_additional` is true, which only happens with `with_bank_mark=True` |

Each passes `badge=additional_badge() if q.is_additional else none` to `text_card`.

## 4. The checkbox on the question form (existing component)

`pages/teacher/question_form.html` adds, after the reference answer field and before
`form_actions`:

```jinja
{{ checkbox_field("additional", _("Additional question"), checked=values.additional, value="1",
   hint=_("Additional questions and their answers are not given to participants before a competition.")) }}
```

`checkbox_field` already exists with `hint` and `aria-describedby` (milestone 10). Nothing changes
in the macro.

## 5. Checks

- `tests/unit/test_templates.py`: `additional_badge()` renders `<span class="badge badge-info">`
  with the word in each language; `text_card` without `badge` is unchanged, and with it holds the
  badge inside the `h3`.
- `tests/integration/test_component_gallery.py`: the badges section shows **Additional**, and the
  cards section shows a text card whose `h3` holds "Question 58" and the badge.
- By hand or with the ad hoc Playwright run ([quickstart.md](../quickstart.md) §4): 360 px and
  desktop width, light and dark, Ukrainian and English.
