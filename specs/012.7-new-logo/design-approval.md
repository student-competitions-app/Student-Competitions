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
| Browser tab (by hand) | checked by hand | checked by hand | checked by hand | [tab-1280-dark](./screenshots/tab-1280-dark.png) |

Headless browsers draw no tab, so the four tab images are taken by hand: a desktop browser in its
light and dark appearance at 1280 px, and a phone's tab overview for 375 px. Each is cropped to the
application's tabs. `tab-1280-dark` is Chrome on macOS in its dark appearance, taken by the product
owner on 2026-11-18 on the deployed branch; the page's own theme does not change the tab. The other
three were not taken: the product owner's check of the real tab and home screen on the same day stands
in for them, and [round-4-icons](./screenshots/round-4-icons.png) records the icons in a drawn tab and
home screen, in light and dark (spec Clarifications, round 4).

**Proposals reviewed in round 2**: [round-2-letters-options](./screenshots/round-2-letters-options.png)
shows three versions of the emblem in the real top bar (1280 px and 375 px, Light and Dark, 2×) and
large on both backgrounds: **A** as merged, **B** with the letters fully opaque, **C** with the
letters opaque but engraved. The product owner chose **B**. It is a proposal made outside the script,
kept as the record of the choice; the round's review screenshots are taken again once the script
makes **B** (research R13).

**Proposals reviewed in round 3**: [round-3-small-icons-options](./screenshots/round-3-small-icons-options.png)
shows the icons in a drawn browser tab (light and dark, on a 2× and a 1× screen), on a drawn phone home
screen (iOS and Android) and pixel for pixel: **A** the whole emblem, as in round 3, and **B** the letters
ЯНМ alone, cut out of the same source ([round-3-letters-cut](./screenshots/round-3-letters-cut.png)).
The product owner chose **B** for the icons; the emblem stays at the sizes the pages show. It is a
proposal made outside the script, kept as the record of the choice (research R15).

## Review log

| Date | Round | Commit | Changes requested | Changes made | Status |
|---|---|---|---|---|---|
| 2026-11-16 | 1 | `b15286f` | Top bar, seen on the deployed branch at desktop width: the emblem is barely visible at 2rem (32 px). Make it as tall as the language switch beside it, at every width. | The top bar's mark is the touch-target size (44 px), the language switch's height, at every width; it was 2rem from 768 px. It loads the 44, 88 or 132 px light ink. The bar is still one 64 px row at 360, 375, 768 and 1280 px, signed out and with a role, in both languages. Only the four 1280 px top bar screenshots change. | Changes requested |
| 2026-11-17 | 2 | `28a2a99` | The size is right ("much better" on the deployed site). The emblem still lets the background through everywhere: make the letters ЯНМ fully opaque and keep the ornament as it is, option B of [round-2-letters-options](./screenshots/round-2-letters-options.png). | `scripts/make_logo.py` holds the letter area as data in the source's pixels (research R13) and lifts the ink inside it to full; the ornament is unchanged. Every image and icon is regenerated; the output is pixel-identical to option B. A test reads two committed PNGs and checks points in the letters (opaque) and in the ornament (engraved). All 12 screenshots change. | Changes requested |
| 2026-11-18 | 3 | `1e73c51` | The solid letters are right: the top bar looks fine on a laptop and on a phone, in Light and Dark. But on small images, the browser tab and the phone's home screen, the emblem looks like a hexagon with blurred edges. Show the ornament at large sizes and the three letters ЯНМ alone at small ones: option B of [round-3-small-icons-options](./screenshots/round-3-small-icons-options.png). | `scripts/make_logo.py` cuts the letters ЯНМ out of the source by a rule it holds with its data (research R15: the letters are the heaviest ink of their row) and draws all 8 icons from them, without the ornament; the favicons' padding is 4 % a side. Only the 8 icons are regenerated, pixel-identical to option B; the emblem images, so the 12 screenshots, do not change. A test reads the two 512 px icons and checks the letters (light ink) and the rows above and below them (deep blue only). | Changes requested |
| 2026-11-18 | 4 | `d165b33` | None: the product owner approved round 4 as it stands. | | **Approved** (2026-11-18) |

The approval takes the open questions below as answered by the implementation as it stands: the
gallery's `sm` mark keeps the whole emblem, the icons keep the letters alone with their padding (4 % on
the favicons, 15 % on the maskable icon), the marks off the top bar keep the near-black ink in Light,
and the small sizes keep their lift. Any of these can still change in a later milestone; each is a
parameter of `scripts/make_logo.py` or a rule in `app.css`.

On the same day the product owner checked by hand, on the deployed branch, the browser tab in a desktop
browser and the home-screen icon on their phone (the letters ЯНМ alone): both look fine (quickstart
§3.6 and §3.7, task T019).

## Questions for round 4

Review [round-4-icons](./screenshots/round-4-icons.png), drawn from the committed icons, and the real
browser tab and home screen on the deployed branch. A phone that already has the old home-screen icon
may keep it until it is removed and added again.

1. **The gallery's `sm` mark** (24 px, its 2× file 48 px) has the same blurred-hexagon look as the old
   favicons. Keep the whole emblem there, as now, or show the letters alone too?
2. **The letters alone in the tab and on the home screen**: legible at 32 px, told apart at 16 px,
   and filling the tile well enough (4 % padding a side on the favicons)?
3. Round 3's question 2 and round 1's questions 3, 4 and 5 are still open. Round 1's question 4 (the
   maskable icon's padding) is now about the letters inside the circle.

## Questions for round 3

1. **The solid letters**: in every screenshot the letters ЯНМ are solid and the ornament engraved.
   Is this option B as you chose it?
   *Answered on 2026-11-17, on the deployed branch: the logo looks fine on a laptop browser in Light
   and Dark, and on a phone in Light and Dark. This covers the top bar at both widths; the gallery's
   Identity, the browser tab and the home screen are not covered yet.*
2. **Where letters and ornament meet**: the loops crossing Н count as letter inside the letters' row,
   and a few hairline curls touching М may read as solid at large sizes. Acceptable?
3. **Small sizes**: at 48 px and below (the gallery's `sm`, the favicons) all of the emblem is lifted
   so it does not wash out, so there the ornament looks nearly as solid as the letters. Keep it?
   *Answered on 2026-11-17, on the deployed branch: the browser tab icon looks good. On a second look
   (2026-11-18) the browser tab and the home screen showed a hexagon with blurred edges, which gave
   round 3's change: the icons show the letters alone. That also replaces round 1 question 1 (the
   favicon's legibility on its tile), which round 4 reviews again with the letters. Whether the
   gallery's `sm` mark looks too heavy beside `md` (round 1 question 5) is still open.*
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
