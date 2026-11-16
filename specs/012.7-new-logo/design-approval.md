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

## Review log

| Date | Round | Commit | Changes requested | Changes made | Status |
|---|---|---|---|---|---|
| 2026-11-16 | 1 | `b15286f` | | | Awaiting review |

## Questions for round 1

The implementation takes these choices. Each is a parameter of `scripts/make_logo.py` or a rule in
`app.css`, so each is easy to change and regenerate.

1. **The favicons**: the emblem fills a rounded deep-blue tile with almost no padding (2 % a side,
   corner radius 22 %), so it is as large as a tab allows. Is it legible at 16 px, or should the
   tile have more padding?
2. **The 44 px mark on phones**: below 768 px the top bar's mark is the touch-target size, larger
   than the 2rem (32 px) it has from 768 px, with the role label beside it. Is the size right?
3. **The dark ink on the light gallery background**: in **Light**, the marks off the top bar are
   near-black (`#1c1c22`) on the page background. Does the engraving read well there?
4. **The maskable icon's padding**: on Android, the home-screen icon keeps the emblem within the
   central safe zone (15 % padding a side), so a round mask never cuts it. Is it too small inside
   the circle?
5. **The small sizes' weight**: images of 48 px and below get their strokes lifted so the fine
   engraving does not wash out. That makes the `sm` mark (24 px, whose 2× file is 48 px) look a
   little heavier than `md` in the Identity screenshots. Keep the lift, soften it, or apply it only
   below 48 px?
