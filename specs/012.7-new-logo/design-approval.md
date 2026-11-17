# Design Approval: Milestone 12.7

**Feature**: [spec.md](./spec.md) (User Story 4, FR-025, FR-026) | **Research**: [research.md](./research.md) R10

- **Approver**: the product owner.
- **What is reviewed**: the real pages, in the screenshots below. There is no mockup: the change is
  one image swap, and the source emblem is already the product owner's choice.
- **The gate**: the milestone does not merge before a round below with status **Approved** and its
  date.
- **The deviation**: this replaces the logo mark of milestone 10's approved look (milestone 10
  [design-approval.md](../010-design-system-ui-guidelines/design-approval.md), its User Story 1
  scenario 3: a later deviation is reviewed and approved again). The amber spark on a deep-blue tile
  becomes the engraved emblem: light ink on the top bar, following the theme elsewhere, and on a
  deep-blue tile in the browser tab and on the home screen. Nothing else in the look changes.

## Screenshots

In [screenshots/](./screenshots/), named `{view}-{width}-{theme}.png`. The top bar views are the
frame (top bar and area tabs) of the page; the identity views are the gallery's **Identity** section
down to the wordmark line. Headless Chromium at 2× density, in Ukrainian, signed in as a teacher
(`area`) and an administrator (`identity`).

| View | 375 px, Light | 375 px, Dark | 1280 px, Light | 1280 px, Dark |
|---|---|---|---|---|
| Sign-in page, top bar (`/login`) | [sign-in-375-light](./screenshots/sign-in-375-light.png) | [sign-in-375-dark](./screenshots/sign-in-375-dark.png) | [sign-in-1280-light](./screenshots/sign-in-1280-light.png) | [sign-in-1280-dark](./screenshots/sign-in-1280-dark.png) |
| Area page, top bar with the role (`/teacher/students`) | [area-375-light](./screenshots/area-375-light.png) | [area-375-dark](./screenshots/area-375-dark.png) | [area-1280-light](./screenshots/area-1280-light.png) | [area-1280-dark](./screenshots/area-1280-dark.png) |
| Gallery, Identity (`/admin/components#identity`) | [identity-375-light](./screenshots/identity-375-light.png) | [identity-375-dark](./screenshots/identity-375-dark.png) | [identity-1280-light](./screenshots/identity-1280-light.png) | [identity-1280-dark](./screenshots/identity-1280-dark.png) |
| Browser tab (by hand) | `tab-375-light.png` (to add) | `tab-375-dark.png` (to add) | `tab-1280-light.png` (to add) | `tab-1280-dark.png` (to add) |

Headless browsers draw no tab, so the four tab images are taken by hand: a desktop browser in its
light and dark appearance at 1280 px, and a phone's tab overview for 375 px.

**Proposals reviewed in round 2**: [round-2-letters-options](./screenshots/round-2-letters-options.png)
shows three versions of the emblem in the real top bar (1280 px and 375 px, Light and Dark, 2×) and
large on both backgrounds: **A** as merged, **B** with the letters fully opaque, **C** with the
letters opaque but engraved. The product owner chose **B**. It is a proposal made outside the script,
kept as the record of the choice; the round's review screenshots are taken again once the script
makes **B** (research R13).

## Review log

| Date | Round | Commit | Changes requested | Changes made | Status |
|---|---|---|---|---|---|
| 2026-11-16 | 1 | `b15286f` | Top bar, seen on the deployed branch at desktop width: the emblem is barely visible at 2rem (32 px). Make it as tall as the language switch beside it, at every width. | The top bar's mark is the touch-target size (44 px), the language switch's height, at every width; it was 2rem from 768 px. It loads the 44, 88 or 132 px light ink. The bar is still one 64 px row at 360, 375, 768 and 1280 px, signed out and with a role, in both languages. Only the four 1280 px top bar screenshots change. | Changes requested |
| 2026-11-17 | 2 | `28a2a99` | The size is right ("much better" on the deployed site). The emblem still lets the background through everywhere: make the letters ЯНМ fully opaque and keep the ornament as it is, option B of [round-2-letters-options](./screenshots/round-2-letters-options.png). | `scripts/make_logo.py` holds the letter area as data in the source's pixels (research R13) and lifts the ink inside it to full; the ornament is unchanged. Every image and icon is regenerated; the output is pixel-identical to option B. A test reads two committed PNGs and checks points in the letters (opaque) and in the ornament (engraved). All 12 screenshots change. | Changes requested |
| 2026-11-17 | 3 | `1e73c51` | | | Awaiting review |

## Questions for round 3

1. **The solid letters**: in every screenshot the letters ЯНМ are solid and the ornament engraved.
   Is this option B as you chose it?
2. **Where letters and ornament meet**: the loops crossing Н count as letter inside the letters' row,
   and a few hairline curls touching М may read as solid at large sizes. Acceptable?
3. **Small sizes**: at 48 px and below (the gallery's `sm`, the favicons) all of the emblem is lifted
   so it does not wash out, so there the ornament looks nearly as solid as the letters. Keep it?
4. Questions 1, 3, 4 and 5 of round 1 are still open.

## Questions for round 2

Round 1 answered question 2 below. Questions 1, 3, 4 and 5 are still open; the answer to each is
needed before approval. In round 2, also check the four 1280 px top bar screenshots: the emblem beside
the wordmark, at the language switch's height.

## Questions for round 1

The implementation takes these choices. Each is a parameter of `scripts/make_logo.py` or a rule in
`app.css`, so each is easy to change and regenerate.

1. **The favicons**: the emblem fills a rounded deep-blue tile with almost no padding (2 % a side,
   corner radius 22 %), so it is as large as a tab allows. Is it legible at 16 px, or should the
   tile have more padding?
2. **The 44 px mark on phones**: below 768 px the top bar's mark is the touch-target size, larger
   than the 2rem (32 px) it has from 768 px, with the role label beside it. Is the size right?
   *Answered in round 1: the mark is the touch-target size (44 px), the language switch's height, at
   every width (spec Clarifications, session 2026-11-17).*
3. **The dark ink on the light gallery background**: in **Light**, the marks off the top bar are
   near-black (`#1c1c22`) on the page background. Does the engraving read well there?
4. **The maskable icon's padding**: on Android, the home-screen icon keeps the emblem within the
   central safe zone (15 % padding a side), so a round mask never cuts it. Is it too small inside
   the circle?
5. **The small sizes' weight**: images of 48 px and below get their strokes lifted so the fine
   engraving does not wash out. That makes the `sm` mark (24 px, whose 2× file is 48 px) look a
   little heavier than `md` in the Identity screenshots. Keep the lift, soften it, or apply it only
   below 48 px?
