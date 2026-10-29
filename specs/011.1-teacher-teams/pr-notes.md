# PR notes: Teams (teacher), milestone 11.1

For the PR description. The spec, plan and contracts are in this folder.

## What changed

- **A Teams tab** (`/teacher/teams`), second in the teacher area: Students, Teams, Questions,
  Competitions. It works like Students:
  - three chained lists (Region, Educational institution, Team), with the selection in the
    address;
  - the selected team lists its active members.
- **Write access manages teams; Read access only sees them.**
  - With Write: **+ Add team** (a one-field form), **Rename**, **Delete** (soft, after a
    confirmation), **Add students** (a page with a Class list; each student shows **Add** or
    "In this team"), and **Remove** (after a confirmation).
  - Every action returns to the tab with the region and the institution still selected. A sealed,
    10-minute notice names the added student; it carries ids only.
- **The rules**:
  - team names are unique ignoring case among live teams across all institutions (a partial
    unique index);
  - a student may be in several teams of their own institution, each once;
  - a team holds at most 50 members, blocked ones included, counted under the team row's lock.
- **Access**: 11 endpoints, all `@allow_roles(Role.TEACHER)`, through the new
  `teacher_access.reach_team`.
  - The team is reached, with Write on every management route, before any student, class or name
    is read.
  - Every service write repeats the checks under lock, in the order team → user → class →
    institution.
- **One migration** (`09cbcbe472be`):
  - `teams` (with `deleted_at` and the partial index `uq_teams_name_key_live`) and
    `team_memberships`;
  - the student consent text version 1 rewritten in place (below).
- **Personal data**:
  - `STUDENT_INVITATION.revoke` deletes the student's memberships first, so removal, withdrawal
    and data deletion all erase them, in deleted teams too;
  - the profile lists the student's teams, a deleted one as "(deleted)".
- **An institution with any team, deleted ones included, cannot be deleted**
  (`count_institution_uses`).
- **The home page's teacher card** reads "Manage your classes, students and teams, and work with
  the question bank and competitions."
- **Components**, each in the library, the gallery and `ui-guidelines.md` before any page uses it:
  - `section_heading` (`components/frame.html`): the selected item's `h2`, one primary button
    beside it, and a row of small buttons below, left out when empty;
  - `row_note` (`components/table.html`, `.row-note`): the muted "In this team".
- **A table refinement**: below 768 px an actions cell with nothing in it is hidden
  (`td.row-actions:empty`). Without it, a row on a full team's Add students page showed an empty
  actions strip under a rule. The gallery's table shows such a row, and the guidelines' phone
  section says so.

## Students: the heading refactor (FR-046)

The selected class's heading on **Students** now comes from `section_heading`. Its markup is
pinned before and after the change by `test_the_class_heading_markup_is_pinned_with_write` and
`..._with_read`, in four states:

- Write with an active class;
- Write with a deactivated class;
- Read with an active class;
- Read with a deactivated class.

The fragment is compared literally, with only the white space between tags normalised. Nothing
else on the page changed.

## The consent text rewrite (FR-015, R9)

The teams migration updates the stored `consent_texts` row for student version 1 in place. Its
id, version and `published_at` (2026-10-19) stay the same, so every consent record still points
at it. The new wording, `STUDENT_CONSENT_TEXT_V1_REWRITE`, names team memberships, says who sees
them, and says withdrawal erases them.

This is a deliberate, one-time exception to milestone 8's append-only rule. It is fenced in
`tests/unit/test_consent_texts.py`:

- `PUBLISHED` pins the rewrite;
- `SUPERSEDED` still pins the original, so the milestone 9 migration cannot change unnoticed;
- `REWRITES_ALLOWED = {("student", 1)}` fails the build for any other rewrite;
- a test checks that the migration's private copy of the original hashes to the superseded pin.

`ConsentText`'s docstring records the exception.

## The downgrade is lossy by design

The downgrade writes the original wording back, byte for byte, then drops `team_memberships` and
`teams`: every team and membership is lost.

Checked by hand on a copy of `data/student_competitions.sqlite3` (it was at `50f17535d874`):

- after `upgrade head`, the student text is the rewrite: row id 2, version 1, published
  2026-10-19;
- after `downgrade 3e32707ed794`, the original 1,182-character text is back and the team tables
  are gone;
- `upgrade head` again brings the rewrite back.

`test_migrations.py` covers the same upgrade, with a consent record, on both engines.

## The four-tab row (FR-026, R15)

Measured with ad hoc Playwright (Chromium) against a seeded scratch database, with Teams current
(`/teacher/teams`) and with Competitions current (`/teacher/competitions`):

| Viewport | Tab rows | Frame bottom | Sideways scroll |
|---|---|---|---|
| 360 × 640 | 2 | 158.5 px | no |
| 375 × 667 | 2 | 158.5 px | no |

The frame stays under `--sc-frame-clearance-tabs` (176 px below 768 px), so the token is
unchanged. From the bottom of a long page:

- **the skip link** puts `<main>` at 158.5 px, right below the frame;
- **the error summary link** of an empty team name puts the field's label at 194 px;
- **tabbing to the field** leaves its label at 364 px (360 wide) and 377 px (375 wide).

The guidelines' clearance note records the measurement.

## Screenshots

The screenshots are in the git-ignored `screenshots/011.1/`, at 1280 × 800 and 360 × 640, in
Light and Dark. They show:

- the tab in each state, with Write and with Read;
- the new-team form with an error;
- **Add students** with "In this team", with no class chosen, and full;
- both confirmations;
- a 200-character team name, and long student names;
- the profile's Teams row;
- the gallery's `#section-heading` and `#table`;
- **Students** with a class selected.

The tab and **Add students** were also taken without JavaScript, showing the **Show** buttons. No
page scrolls sideways.

## Replaced and updated tests (SC-011)

- **The student consent checksum**: `PUBLISHED[("student", 1)]` is the rewrite's. The old
  checksum moved to `SUPERSEDED`.
- **Three assertions quoting the old student wording**, "and your class, which also records", now
  quote the rewritten text. They are in `test_profile.py` (one) and `test_student_invitation.py`
  (two).
- **The three-tab row**: the assertions in `test_teacher_classes.py` and
  `test_teacher_questions.py` now expect four tabs.
- **The teacher card**: `test_home.py` pins the new wording.
- **The route sweeps**:
  - `test_the_write_routes_are_exact` gains the 5 team POST routes;
  - `TEACHER_SCOPED_PATHS` takes the `/teacher/teams/` paths with an id;
  - `test_teacher_access.py` expects 13 teacher POST routes, and its scene has a real team, a
    deleted team and another institution's team.
- **The form contract**: the 8 `teacher-team*` cases were generated once, for those cases only.
  No existing entry changed.

New modules:

- `test_team_service.py`: the service, including the index and primary-key races, and the 50th
  and 51st member added at once on PostgreSQL;
- `test_teacher_teams.py`: the tab end to end.

`ruff check`, `ruff format --check` and `pytest` pass on SQLite and PostgreSQL: 3,725 passed, and
6 skipped for engine-specific cases. `ruff format` also re-spaced the Python blocks in
`contracts/http-routes.md` and `contracts/services.md` (blank lines only), so the
repository-wide format check passes.

## Things to know

- **"(deleted)" on the profile is plain text, not a badge.** The guidelines prefer badges for
  statuses, but the spec fixes this wording (research R14). No new badge word was added.
- **US8-3** (deleting a class of an institution with teams) is tested in `test_teacher_teams.py`,
  because class deletion is a teacher action.
- **Milestone 12** must add only teams that `reach_team` returns: live teams of a linked
  institution. The services module docstring says so.
