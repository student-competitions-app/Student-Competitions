# Contract: Components and the Time-Zone Script

Every item here is added to the component library, the gallery (`/admin/components`) and
`docs/requirements/ui-guidelines.md` **before** the **Competitions** tab uses it (FR-048,
Constitution II). Existing callers render exactly as before. Decisions are in
[research.md](../research.md) R5, R10, R14, R15.

---

## 1. `actions_menu` and `menu_link` (new): `components/menu.html`

```jinja
{% from "components/menu.html" import actions_menu, menu_link %}
{% call actions_menu("Spring round") %}
  {{ menu_link("Edit", edit_href) }}
  {{ menu_link("Cancel competition", cancel_href, destructive=True) }}
{% endcall %}
```

**Emitted markup** (white space trimmed):

```html
<details class="actions-menu" name="row-actions">
  <summary>Actions<span class="visually-hidden"> for “Spring round”</span></summary>
  <ul class="actions-menu-panel">
    <li><a href="…" class="actions-menu-link">Edit</a></li>
    <li><a href="…" class="actions-menu-link actions-menu-link-destructive">Cancel competition</a></li>
  </ul>
</details>
```

- `actions_menu(item_name, label="Actions")`: `item_name` is required (a template error
  otherwise); the accessible name is "<label> for “<item_name>”". When the call block renders only
  white space, nothing is emitted.
- `menu_link(label, href, destructive=False)`: a link; the destructive one is in the danger colour.
  Entries are always links to a page (a form or a confirmation), never a `POST`.
- **Look**: the summary is a small outline secondary button with a down chevron; the panel is a
  surface card with the menu shadow, `--sc-radius-card`, positioned under the summary and aligned to
  its right edge, `z-index` as the user menu's. Each entry and the summary are at least
  `--sc-touch-target` tall, full width of the panel, with the focus ring.
- **Phone**: in a table card the menu sits in the actions part; the panel stays within the
  card's width and wraps long labels.
- **Table**: `.data-table` from 768 px no longer uses `overflow: hidden`; its corner cells carry the
  card radius instead, so an open panel is never clipped.
- **Gallery**: section `#actions-menu`, with a closed menu, an open one (`open` attribute) with a
  plain and a destructive entry, and the menu inside a data-table row.

## 2. `date_time_fields` (new): `components/form.html`

```jinja
{{ date_time_fields("start", "Start", values, errors, zone_label) }}
```

```html
<fieldset class="date-time-fields">
  <legend>Start</legend>
  <label for="start_date">Start date</label>
  <input type="date" id="start_date" name="start_date" value="2027-03-14" required …>
  <label for="start_time">Start time</label>
  <small id="start_time-hint" class="field-hint">Time zone: Europe/Kyiv</small>
  <input type="time" id="start_time" name="start_time" value="10:00" required aria-describedby="start_time-hint" …>
  <input type="hidden" name="time_zone" value="Europe/Kyiv">
</fieldset>
```

- The labels are "<legend> date" and "<legend> time"; each field shows its own error and keeps the
  value as typed, through the existing `field` macro (`type="date"`, `type="time"`).
- `zone_label` is the IANA name or `UTC`; it is both the hint text and the hidden value.
- On wide screens the two fields stand side by side; below 768 px they stack.
- **Gallery**: section `#forms` gains an empty pair, a filled pair with a zone, and a pair with a
  date error and the gap error.

## 3. `competition_status_badge` (new): `components/badge.html`

```jinja
{{ competition_status_badge(c.status) }}
```

| Status value | Word | Kind |
|---|---|---|
| `upcoming` | Upcoming | `info` |
| `in_progress` | In progress | `success` |
| `finished` | Finished | `neutral` |
| `cancelled` | Cancelled | `muted` |

An unknown value is a template error. **Gallery**: section `#badges` gains the four.

## 4. `local_time` (new): `components/time.html`

```jinja
{% from "components/time.html" import local_time with context %}
{{ local_time(c.starts_at) }}                 {# the request's zone #}
{{ local_time(sample, zone=none) }}           {# the gallery: no zone known #}
```

```html
<time datetime="2027-03-14T08:00Z">14 March 2027, 10:00</time>
<time datetime="2027-03-14T08:00Z">14 March 2027, 08:00 UTC</time>
```

- `zone` defaults to the context's `time_zone` (set for every request from the cookie).
- The text comes from `format_local_time`, the attribute from `utc_iso` (services contract).
- **In a heading**: capture the heading with `{% set question %}…{{ local_time(…) }}…{% endset %}`
  and pass it to `confirmation` or `refusal`; never build it as a string in Python.
- **Gallery**: section `#time`, the same moment with a zone and without.

## 5. `confirmation(..., back_label="Cancel")` (changed): `components/confirmation.html`

```jinja
{{ confirmation(question, consequence, action, "Cancel competition", back_href, hidden=…, back_label="Keep competition") }}
```

The link back reads `back_label`. Every existing call passes nothing and keeps **Cancel**.
**Gallery**: section `#confirmations` gains a confirmation with a custom back label.

## 6. `chained_lists` option groups (changed): `components/selectors.html` and `select_field`

A level may carry `groups`: a list of `(label, options)` pairs. `select_field(..., groups=())`
renders, after the plain options and before `extra_options`:

```html
<optgroup label="Deactivated subjects">
  <option value="7">Astronomy</option>
</optgroup>
```

A selected value inside a group is marked `selected` as in the plain options. A level without
`groups` renders exactly as before. **Gallery**: section `#selectors` gains a list with a group.

## 7. The time-zone script (new): `app/static/js/time-zone.js`

Loaded by `layouts/base.html` on every page: `<script src="/static/js/time-zone.js" defer></script>`
after `loading-feedback.js`.

Behaviour (research R5):

1. `const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;`
2. stop unless `zone` is a string of at most 64 characters matching
   `^[A-Za-z0-9_+\-]+(?:/[A-Za-z0-9_+\-]+)*$`;
3. read `sc_time_zone` from `document.cookie`; stop if it equals `zone`;
4. `document.cookie = "sc_time_zone=" + zone + "; Path=/; Max-Age=31536000; SameSite=Lax" +
   (location.protocol === "https:" ? "; Secure" : "");`

It makes no request, uses no other storage, reloads nothing, names no other site, and changes no
element of the page. Without it, every time is shown in UTC, labelled "UTC".

**Static checks** (`tests/unit/test_time_zone_script.py`, read as text): a plain script (no
`import`/`export`); no `fetch(`, `XMLHttpRequest`, `sendBeacon`, `localStorage`, `sessionStorage`;
no URL to another site; `document.cookie` written only with `sc_time_zone=` and with `Path=/`,
`SameSite=Lax` and `Max-Age=`; the name check present; at most 30 non-empty lines.
`tests/integration/test_layout.py` checks every kind of page loads it once, deferred, in the head.

## 8. UI guidelines changes (`docs/requirements/ui-guidelines.md`)

- **§5 Components**: the actions menu (new subsection, `components/menu.html`), the date and time
  fields under Forms, the competition status badge under Badges, local time (new subsection,
  `components/time.html`), the back label under Confirmations, option groups under Selectors.
- **§4 Layout**: the base layout loads two scripts, `loading-feedback.js` and `time-zone.js`.
- **§7 Wording patterns**: "Statuses use one short term each, everywhere: **Active** or
  **Deactivated**; **Read** or **Write**; **Upcoming**, **In progress**, **Finished** or
  **Cancelled**." A new **Times** pattern: "14 March 2027, 10:00" in the person's zone; "14 March
  2027, 10:00 UTC" when the zone is not known; a form names its zone under the time field, "Time
  zone: Europe/Kyiv". A **Menus** pattern: the button reads "Actions" and is announced "Actions for
  “<item>”"; entries are verbs.
- **§8 Phone behaviour**: the actions menu in a table card, its 44 px entries.
- **§10 Checks**: the time-zone script's static checks.
