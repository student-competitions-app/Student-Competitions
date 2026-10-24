# Contract: Frame and Component Changes (Milestone 10.1)

**Feature**: [../spec.md](../spec.md) | **Research**: [../research.md](../research.md) R3, R5–R10 |
**Base contract**: [milestone 10 components.md](../../010-design-system-ui-guidelines/contracts/components.md)

Everything not listed here keeps the milestone 10 contract. All milestone 10 rules still apply:
text is escaped, every class is defined and used, there is no inline `style`, and every macro and
variant is in the gallery and the guidelines in the same change.

---

## 1. Layout skeleton (`layouts/base.html`), replacing milestone 10 §1.2

The layout renders, in order:

1. in `<head>`, after the stylesheets and before `{% block scripts %}`:
   `<script src="/static/js/loading-feedback.js" defer></script>`, exactly once on every page;
2. `<a href="#main" class="skip-link">Skip to main content</a>`, unchanged;
3. **new** `<div class="frame">`, holding in order:
   1. `top_bar()`, unchanged: `<header class="top-bar">…</header>`;
   2. `{% block tabs %}{% endblock %}`, unchanged: area pages render `area_tabs(...)` here;
   3. `loading_bar()`;
4. `<main id="main" class="container">{% block content %}{% endblock %}</main>`, unchanged;
5. `<footer class="site-footer container">…</footer>`, unchanged.

`layouts/admin.html` and `layouts/teacher.html` are unchanged. Pages change nothing (FR-019).

**Styles** (`app.css`):

| Selector | Rule | Where |
|---|---|---|
| `.frame` | `position: relative` (the bar's anchor) | always |
| `body > .frame` | `position: sticky; top: 0; z-index: 3` | `@media screen and (min-height: 600px)` only |
| `html` | `scroll-padding-top: var(--sc-frame-clearance)` | same media query |
| `html:has(body > .frame .area-tabs)` | `scroll-padding-top: var(--sc-frame-clearance-tabs)` | same media query |
| `input, select, textarea` | `scroll-margin-top: var(--sc-field-clearance)` | always |
| `body > header.top-bar` | **removed**: the top bar is no longer a child of `body` | n/a |

---

## 2. `loading_bar(active=False)` (`components/frame.html`), new

| Parameter | Meaning |
|---|---|
| `active` | `False`, the default, renders the bar hidden, as every page does. `True` renders it shown; only the gallery uses it. |

**Emits**: `<div class="loading-bar" aria-hidden="true" hidden></div>`. With `active=True`, the
`hidden` attribute is left out.

**Styles**:

| Selector | Rule |
|---|---|
| `.loading-bar` | `position: absolute; inset-inline: 0; top: 100%; height: var(--sc-border-accent); overflow: hidden; pointer-events: none` |
| `.loading-bar::before` | a `--sc-primary` segment about a third of the width, moving left to right on a 1.5 s infinite loop (`transform` only) |
| `.loading-bar[data-detached]` | `position: fixed; top: 0` |
| `@media (prefers-reduced-motion: reduce)` `.loading-bar::before` | `animation: none`, filling the whole width (FR-005) |
| `@media print` `.loading-bar` | `display: none` |

**Rules**:

- **Placement**: it is rendered only by the layout, as the frame's last child. A page never calls
  it; the gallery does, to show it.
- **Who changes it**: only the script changes `hidden` and `data-detached`
  ([loading-script.md](./loading-script.md)).

---

## 3. `button(…, busy=False)` (`components/button.html`), new parameter

`button(label, kind="primary", name=None, value=None, outline=False, small=False, attrs={},
busy=False)`. With `busy=True`, it adds `aria-busy="true"`. Nothing else changes.

**Rules**:

- **Who sets it**: pages never set `busy`. In use, the script sets `aria-busy` on the button that
  sent the form ([loading-script.md §3](./loading-script.md#3-forms)). The parameter exists so the
  gallery can show the busy state.
- **No `disabled`**: a busy button is never `disabled`, so its `name` and `value` are still sent
  (FR-010).

**Styles**:

| Selector | Rule |
|---|---|
| `:is(button, [type="submit"])[aria-busy="true"]::before` | Pico's spinner redrawn as a `mask` (`var(--pico-icon-loading)`) over `background-color: currentColor`, with `filter: none`, so it takes each kind's text colour in both themes (research R6). The spinner keeps turning under reduced motion, as Pico intends for busy controls. |

Pico already supplies `pointer-events: none` and the spacing for `[aria-busy=true]` buttons.

---

## 4. Frame component styles, changed

| Selector | Change | Source |
|---|---|---|
| `nav.area-tabs li a` | `min-height: var(--sc-touch-target)` below 768 px; `3rem` from 768 px (was `3rem` everywhere) | research R9 |
| `.user-menu-panel` | `+ max-height: calc(100dvh - var(--sc-frame-clearance)); overflow-y: auto; overscroll-behavior: contain` | research R10, FR-016 |

---

## 5. Gallery (`pages/admin/components.html`), new section

A new `<section id="loading" aria-labelledby="loading-heading">`, placed right after `#frame`,
headed **Loading feedback**, with:

1. **"Loading bar"** (`h3`): a sample `<div class="frame">` holding `top_bar(one_role_user,
   teacher_role, [teacher_role])` and `loading_bar(active=True)`. It is shown in its loading state
   and never starts a page load. It is not `body > .frame`, so it does not stick.
2. **"Busy button"** (`h3`): `button("Send invitation", busy=True)`,
   `button("Dark", kind="secondary", small=True, busy=True)` and
   `button("Delete", kind="destructive", busy=True)`, inside a `<div class="button-row">` and
   **not** inside any `<form>`. A submit button with no form does nothing when pressed, and Pico's
   `pointer-events: none` already ignores clicks. They are shown in both themes through the
   gallery's theme switch.

**Gallery test coverage** (`tests/integration/test_component_gallery.py`, `SECTIONS`): the key
`"loading"`, after `"frame"`, with the texts `["Loading bar", "Busy button", "Send invitation"]`.
Further checks: the section holds one `.loading-bar` without `hidden`, and three buttons with
`aria-busy="true"`.
