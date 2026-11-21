# Contract: Components and UI Guidelines (Milestone 12.8)

Each addition goes into the component library (`app/templates/components/`), the component gallery
(`/admin/components`, `app/templates/pages/admin/components.html` with sample data in
`app/routers/admin_components.py`) and `docs/requirements/ui-guidelines.md` before any page uses it
(constitution Principle II). Tokens only; no new colour token.

## 1. The Published badge (`components/badge.html`)

- `competition_status_badge("published")` → `badge(_("Published"), "accent")`.
- `badge` gains the kind `accent`: `.badge-accent { background: var(--sc-accent); color:
  var(--sc-on-accent); }` in `app.css`, checked in both themes by the existing stylesheet tests.
- Gallery: the five status badges in a row, in the filter's order.
- Guidelines: the statuses list gains **Published** ("a finished competition whose results are
  published"), with its badge.

## 2. The download entry of the actions menu (`components/menu.html`)

- `menu_link(label, href, destructive=False, download=False)`. With `download=True` the link
  carries the bare `download` attribute, so the browser saves the file under the server's name. It
  is never destructive.
- `loading-feedback.js` already skips links with `download` (milestone 10.1), so the loading bar
  never starts for it; the gallery test asserts the attribute.
- Gallery: the open actions menu sample gains a **Download results** entry.
- Guidelines (actions menu): "A download is a menu entry like any other, a link marked as a
  download: it opens no page, starts no loading bar, and the teacher stays where they were."

## 3. The blocked confirmation (`components/confirmation.html`)

- `confirmation(..., blocked=None, alternative=None)`:
  - `blocked`: a reason. When given, the post button is not rendered, and the reason is shown as
    an `info` notice above the actions.
  - `alternative`: an `(label, href)` pair, rendered as a link before the back link.
- Without `blocked`, the confirmation is unchanged. A `blocked` confirmation with `kind=
  "destructive"` is refused (`template_error`): only a primary confirmation can wait for work to be
  done.
- Gallery: the publish confirmation in both states (ready, blocked).
- Guidelines (confirmations): "When an action cannot be taken yet because work is left to do, its
  confirmation page says what is left and links to it, and has no confirming button."

## 4. The read-only grading sheet (`components/grading_sheet.html`)

- `grading_sheet(..., read_only=False, note=None)`. Read-only:
  - each answered question shows "Grade: <g> of 10" as text in place of the field;
  - the reference answers stay;
  - there is no field, no error and no **Save grades**;
  - `note` is a notice under the heading.
- Gallery: the read-only sheet with the published note.
- Guidelines (grading sheet): "Once the results are published, the grading sheet is read-only,
  with a note saying why."

## 5. Pages built from these

| Page | Template | Built from |
|---|---|---|
| Publish confirmation | `pages/teacher/competition_publish.html` (new) | `confirmation(kind="primary", blocked=…, alternative=…)`, `competition_status_badge`, `local_time` |
| Publish refusal | `pages/teacher/competition_refused.html` (existing) | `refusal` |
| Competitions list | `pages/teacher/competitions.html` | `actions_menu`, `menu_link(download=True)`, `competition_status_badge` |
| Grading sheet | `pages/teacher/team_grading_sheet.html` | `grading_sheet(read_only=…, note=…)` |

## 6. UI guidelines changes (FR-045, FR-046)

- **Actions menu**: the order **Edit**, **Questions**, **Teams**, **Answers**, **Grades**,
  **Publish results**, **Download results**, **Finish competition**, **Cancel competition**; the
  example shows a published competition; the download entry rule (§2).
- **Statuses**: five statuses and badges.
- **Confirmations**: the blocked state (§3); **Publish results** / **Keep unpublished** joins the
  examples of a primary confirmation whose back link says what is kept.
- **Wording patterns**: the notice "The results of “<name>” were published"; the refusal reasons.
