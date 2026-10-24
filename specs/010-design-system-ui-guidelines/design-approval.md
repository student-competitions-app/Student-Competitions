# Design Approval: Milestone 10

**Feature**: [spec.md](./spec.md) (User Story 1, FR-046) | **Research**: [research.md](./research.md) D1

- **Approver**: the product owner.
- **Mockup**: [mockup/index.html](./mockup/index.html). Open it directly in a browser; it needs no
  server and loads nothing from another site.
- **The gate**: no commit on this branch changes `app/templates/` or `app/static/css/app.css`
  before the commit that records the approving round below (quickstart §2).
- **A later deviation** from the approved look is a new round in this log, approved again (US1-3).

## Review log

| Date | Round | Mockup commit | Changes requested | Changes made | Status |
|---|---|---|---|---|---|
| 2026-10-24 | 1 | `1f26f60` | | | Awaiting review |

## Questions for round 1

The mockup takes these choices. Each is easy to change before the rebuild starts.

1. **The logo mark**: an amber spark on a deep-blue tile. In the top bar the tile is the bar's own
   colour, so only the spark shows there. The favicon shows the full tile.
2. **The role label**: below the product name on a phone, and as an outlined label beside it on a
   desktop.
3. **The sign-in page**: a narrow centred column on the page background, with the theme switch
   under the form.
4. **Row actions**: outlined buttons. **Rename** and **Activate** are secondary; **Deactivate** and
   **Delete** are red.
5. **The error summary**: a red-bordered box with a tinted background. The message is repeated in
   red, bold, above the field.
