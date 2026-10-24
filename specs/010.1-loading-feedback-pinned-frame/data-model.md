# Data Model: Feedback While a Page Loads, and a Frame That Stays in View (Milestone 10.1)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

**Stored data: none.** No table, column, migration, cookie or setting is added or changed
(FR-022). This document lists the design tokens the milestone adds and the client-side states the
script moves through.

---

## 1. New design tokens (`app/static/css/app.css`, token block)

The tokens are defined once in the light `:root` block. The breakpoint values go in the token
block's existing media blocks, as milestone 10 does for the body text size.

| Token | Below 768 px | From 768 px | Used by | Source |
|---|---|---|---|---|
| `--sc-frame-clearance` | `5.5rem` | `5.5rem` | `scroll-padding-top` on pages without area tabs; the user menu's `max-height` | research R8, R10 |
| `--sc-frame-clearance-tabs` | `11rem` | `8rem` | `scroll-padding-top` on area pages | research R8 |
| `--sc-field-clearance` | `5rem` | `5rem` | `scroll-margin-top` on `input`, `select`, `textarea` | research R8 |

**Reused tokens**:

- `--sc-primary`: the bar's colour;
- `--sc-border-accent`: the bar's thickness;
- `--sc-touch-target`: the area tabs' height below 768 px (research R9).

**New breakpoint**: `(min-height: 600px)`, combined with `screen`, pins the frame. It joins
`768px` and `1024px` as a literal in media queries, which the token check already allows.

**Validation**: each clearance must be at least the tallest frame it covers, measured at 360 px and
375 px width (research R8 table). A change to the top bar or the tabs is re-measured
([quickstart.md §4](./quickstart.md#4-measurements)).

---

## 2. Client-side states (in the page, never sent or stored)

### 2.1 The pending page load (one per page)

| State | Entered when | Visible effect | Left when |
|---|---|---|---|
| **Idle** | page load; Back or Forward restore (`pageshow`, `persisted`) | none | a qualifying link click or form submit (contract §2) |
| **Waiting** | a qualifying link click or form submit; a POST form is marked *sending* at once | none (the 200 ms timer runs); a second submit of a *sending* form is cancelled | 200 ms pass → **Showing**; the next page arrives → page discarded; another qualifying click or submit → **Waiting** again, with the timer restarted |
| **Showing** | the timer fires | the bar shows (detached to the screen's top edge if the frame is out of view); the form's submitter gets `aria-busy="true"` | the next page arrives → page discarded; another qualifying click or submit → **Waiting**, and the bar stays until that load shows or arrives; Back or Forward restore → **Idle** |

There is no time-out (FR-009). A stopped load (the Stop button or Esc) stays in **Showing** until
the next page or a reload (spec assumption).

### 2.2 The loading bar element

| Attribute | Meaning |
|---|---|
| `hidden` present | not shown (default render) |
| `hidden` absent | shown; the gallery renders it so (`loading_bar(active=True)`) |
| `data-detached` present | fixed to the top edge of the screen, because the frame was out of view when it appeared |

### 2.3 A form

| Marker | Set | Effect | Cleared |
|---|---|---|---|
| *sending* (held by the script, not in the markup) | on submit of a POST form | later `submit` events for that form are cancelled | the next page; Back or Forward restore |
| `aria-busy="true"` on the submitter | when **Showing** begins | Pico's spinner (redrawn in `currentColor`) and `pointer-events: none`; announced as busy | the next page; Back or Forward restore |

GET forms are never *sending*: a newer choice sends again (spec FR-007).
