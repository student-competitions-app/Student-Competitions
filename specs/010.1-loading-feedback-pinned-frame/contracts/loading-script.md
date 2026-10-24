# Contract: `loading-feedback.js` (Milestone 10.1)

**Feature**: [../spec.md](../spec.md) FR-001–FR-011, FR-019–FR-021 | **Research**:
[../research.md](../research.md) R1–R5 | **States**: [../data-model.md §2](../data-model.md#2-client-side-states-in-the-page-never-sent-or-stored)

**The file**: `app/static/js/loading-feedback.js`, served from `/static/js/`. It is loaded by
`layouts/base.html` with `defer` on every page.

- **Plain script**: a plain script (not a module), with no imports.
- **Nothing outside the page**: no network requests, no storage, no cookies, nothing loaded from
  another site.
- **Small**: about 80 lines, commented the way `auto-submit.js` is.

Without JavaScript, or if the file fails to load, nothing in this contract happens, and links and
forms work as before (FR-021).

---

## 1. Constants and state

| Name | Value |
|---|---|
| Delay | `200` ms (FR-002) |
| Pending state | the timer, the `<form>` being sent (POST only) and the button to mark busy, for the latest page load |
| `sending` | a `WeakSet` of every POST form sent from this page and not yet followed by a new page. A restore replaces it. |
| `busy` | a `Set` of every button the script marked `aria-busy`, so a restore can clear them all |

---

## 2. Links (`click` on `document`, bubbling)

A pending load starts (or restarts the timer) when **all** of these hold (research R2):

| # | Condition | Excludes |
|---|---|---|
| 1 | `!event.defaultPrevented` | clicks another script cancelled |
| 2 | `event.button === 0` and no `ctrlKey`, `metaKey`, `shiftKey` or `altKey` | new tab or window, downloads (FR-003). A middle click never fires `click`. |
| 3 | the closest `a[href]` exists, has no `download` attribute, and its `target` is empty or `_self` | non-links, downloads, other windows |
| 4 | `new URL(link.href).origin === location.origin` | another site, `mailto:`, `tel:` (FR-003) |
| 5 | not (`hash !== ""` and `pathname` and `search` equal the current page's) | in-page links: the skip link and the error-summary links (FR-003) |

A link to the current page without a fragment **does** start a load: it reloads the page.

---

## 3. Forms (`submit` on `document`, bubbling)

| Step | Behaviour |
|---|---|
| 1 | Ignore the event if `event.defaultPrevented`, or if the effective target (`submitter.formTarget` or `form.target`) is set and is not `_self`. |
| 2 | Effective method: `submitter.formMethod` or `form.method`. |
| 3 | **POST** and the form is already *sending*: `event.preventDefault()` and stop. Nothing else changes (FR-007). |
| 4 | **POST**: mark the form *sending*. |
| 5 | Start the pending load, as for a link, remembering `event.submitter` (it may be `null`: a list sent through `requestSubmit()`). |

When the timer fires (§4), the remembered submitter, if any, gets `aria-busy="true"` (FR-008).

The script **never** sets `disabled`, `readonly` or `inert` on anything (FR-010). A unit test
checks the source for it.

A form the browser refuses as invalid fires no `submit` event, so nothing starts (FR-003).

---

## 4. Showing (the timer fires)

1. **Place the bar** (`place()`): measure the frame (`body > .frame`). If its
   `getBoundingClientRect().bottom` is at most `0`, set `data-detached` on the bar; otherwise remove
   it (FR-006).
2. Remove `hidden` from the bar (`body > .frame > .loading-bar`) (FR-001).
3. **Follow scrolling**: add `place` as a passive `scroll` listener on `window`, so the bar stays
   visible if the person scrolls while it shows (FR-006). This matters only on screens under 600 px
   tall, where the frame can scroll away; on taller screens the frame is pinned and `place()` never
   detaches it. Nothing runs on scroll before the bar shows.
4. Set `aria-busy="true"` on the remembered submitter (§3) and add it to `busy`.

This happens at most once per pending load. A newer pending load restarts the timer. If the bar is
already shown, it stays shown.

---

## 5. Back and Forward (`pageshow` on `window`)

When `event.persisted` is true, `reset()` runs (FR-011):

- clear the timer and the pending state;
- remove the `scroll` listener;
- set `hidden` on the bar and remove `data-detached`;
- remove `aria-busy` from **every** button in `busy`, then clear `busy`;
- replace `sending` with a new, empty `WeakSet`.

**Why everything is cleared**: a person can send a POST form, then follow a link before the form's
page arrives. The link replaces the pending state. Clearing only the current form and button would
leave the first form blocked and its button busy after Back.

A page that is not restored from the cache was loaded fresh, so the script does nothing.

---

## 6. What the script does not do

- It does not touch the pinned frame. That is CSS only (research R7, R8).
- It does not intercept, delay or re-send any navigation. The browser loads the page as before.
- It has no time-out (FR-009). It does not watch the Stop button or Esc (spec assumption).
- It does not use any HTMX or partial-update event. There are none yet; a later milestone that adds
  them decides their feedback.
