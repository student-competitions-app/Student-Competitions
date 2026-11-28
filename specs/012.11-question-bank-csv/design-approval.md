# Design Approval: Milestone 12.11

The product owner's check of the look of the file field and the **Import questions** page
(spec FR-062, User Story 9 scenario 5; tasks T046, T047), and of an export opened in Excel
(task T050, research R4). The milestone was not to be delivered before this approval.

## Screenshots (T046)

Taken on 2026-11-28 with headless Playwright (Chromium) against a seeded scratch database: History
with 124 questions (every ninth additional), Chemistry with none, and a deactivated Latin. They are in
`specs/012.11-question-bank-csv/screenshots/`, which is git-ignored like every screenshot folder
(milestone 10 research D1), so they are not committed; retake them as below.

Each view is in Ukrainian and English, light and dark, at 1280 px and 360 px (`<view>-<lang>-<theme>-<width>.png`):

| View | File prefix |
|---|---|
| The **Subjects** tab, first row's menu open | `subjects-menu` |
| **Import questions**, clean | `import` |
| **Import questions** after a file with 25 bad rows (20 listed, "And 5 more errors.") | `import-rows` |
| **Import questions** after a file with a wrong header (the error on the field) | `import-file-error` |
| **Deactivate** confirmation | `deactivate` |
| **Activate** confirmation | `activate` |
| Gallery: **File field** | `gallery-file-field` |
| Gallery: **Confirmation with a form** | `gallery-confirmation-with-form` |

No view scrolls sideways at 360 px (checked by the script for every page view).

**Notes for the review:**

- **The file control's own labels** ("Choose File", "No file chosen") come from the browser and
  follow its language, not the site's: the headless browser was English. A Ukrainian browser shows
  its Ukrainian labels.
- **The gallery captures of single sections** show the pinned top bar over the section's top
  edge. That is how an element screenshot meets the pinned frame, not how the page looks.
- **One fix was made during the shots**: with an error, Pico gave the file control the padding and
  icon of an invalid text field, which floated beside the button. A file control has no box, so
  `app.css` drops both for `input[type="file"][aria-invalid]`; the message above the field marks
  the error.

**To retake**: migrate a scratch SQLite database, seed it (subjects, an import of 124 questions,
an administrator session made with `create_session`), start `uvicorn app.main:app --port 8765`
on it, and run a Playwright script with the `sc_session`, `sc_lang` and `sc_theme` cookies
(`uv run --no-project --with playwright -- python -I <script>`).

## Decisions

| Round | Date | What | Decision |
|---|---|---|---|
| 1 | 2026-11-28 | The screenshots above (T047) | **Approved** by the product owner, as shown; no changes asked |
| 2 | 2026-11-28 | An export opened in Excel (T050) | **Confirmed** by the product owner: the exported CSV file was imported into Excel successfully. The separator stays a comma (spec FR-019); the accepted risk in research R4 stands for a double-click open under a Ukrainian regional setting |
