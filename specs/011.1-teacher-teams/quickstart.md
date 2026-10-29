# Quickstart: Teams (Teacher) (Milestone 11.1)

How to check, end to end, that the milestone works.

- **What should happen**: [spec.md](./spec.md).
- **The addresses, the page contents and the wording**:
  [contracts/http-routes.md](./contracts/http-routes.md).
- **The services**: [contracts/services.md](./contracts/services.md).
- **The components**: [contracts/components.md](./contracts/components.md).
- **The tables and the migration**: [data-model.md](./data-model.md).

This guide only says how to run and what to look for.

## 0. Prerequisites

- `uv sync`.
- For the PostgreSQL cases, the local container (`sc-pg`) running and `TEST_POSTGRES_URL` set (see
  the README).
- A local `.env` with the cast emails and the `memory` email sender, as in milestones 8–11.

## 1. Automated checks (both engines)

```bash
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_consent_texts.py
uv run pytest tests/integration/test_team_service.py tests/integration/test_teacher_teams.py
uv run pytest tests/integration/test_migrations.py tests/integration/test_routes.py \
              tests/integration/test_teacher_access.py tests/integration/test_teacher_students.py \
              tests/integration/test_profile.py tests/integration/test_consent_privacy.py \
              tests/integration/test_data_deletion.py tests/integration/test_admin_institutions.py \
              tests/integration/test_component_gallery.py tests/integration/test_home.py
uv run pytest                                   # the whole suite (SC-011)
```

**Expected**: everything green on SQLite, and on PostgreSQL when `TEST_POSTGRES_URL` is set. The
mapping from spec scenarios to tests is in [research.md](./research.md) R17.

## 2. Upgrade a database from milestone 11

```bash
cp data/app.db /tmp/before-m11-1.db        # or any database at revision 3e32707ed794
uv run alembic upgrade head
```

**Check**:

- **The new tables**: `teams` and `team_memberships` exist and are empty.
- **The consent text is rewritten in place**:
  `SELECT version, published_at, text FROM consent_texts WHERE role = 'student'` gives one row,
  still version 1 and still published 2026-10-19. Its text names team memberships (US7-5).
- **The way back**: `uv run alembic downgrade 3e32707ed794` restores the old wording, and
  `upgrade head` brings the new one back.

## 3. Run the application and walk through the tab

```bash
uv run uvicorn app.main:app --reload
```

**As an administrator**:

- create the regions "Kyiv" and "Lviv", the institution "Kyiv Polytechnic Institute" in Kyiv, and
  "Lviv Academy" in Lviv;
- invite teacher A with **Write** on both institutions, and teacher B with **Read** on Kyiv
  Polytechnic Institute;
- accept both invitations.

**As teacher A** (US1, US2, US3, US5):

1. **The tab row**: Students, Teams, Questions, Competitions; **Teams** is `/teacher/teams`.
2. **On Students**: create the classes "KN-21" (year 2) and "KN-31" (year 3), and invite and accept
   two students in each. The class heading looks and works exactly as before (FR-046).
3. **The empty institution**: on **Teams**, choose Kyiv and then the institution. It shows "No teams
   yet" with "Create the first team with + Add team."
4. **Create**: choose **+ Add team**, enter "  Rockets  " and save. You are back on the tab with
   "Rockets" selected (trimmed), showing "No members in this team yet".
5. **Add students**: open **Add students** and choose KN-21. Its students are listed by last name.
   Press **Add** beside one. You are back on the tab with "Rockets" selected, the success notice,
   and the student listed with "KN-21 · year 2".
6. **A second class**: add a KN-31 student the same way. The list now holds both, by last name, each
   with their class. On **Students**, both are still in their own classes.
7. **"In this team"**: open **Add students** for KN-21 again. The student you added shows "In this
   team" instead of **Add**.
8. **A repeated addition**: open the **Add students** page in two browser tabs and press **Add**
   for the same student in both. The second gives the "already in this team" notice, and the
   student is listed once.
9. **Unique names**: in "Lviv Academy", try to create "rockets". You get "A team named “rockets”
   already exists.", and the message names no institution.
10. **Rename** "Rockets" to "Comets", then to "comets": both are accepted.
11. **Remove** one member. The confirmation names the student and "comets". After you confirm, the
    student is gone from the team but can still sign in, and keeps their class.
12. **Delete** the team. The confirmation names the team, the institution and "Members: 1". After you
    confirm, the institution is selected with no team, and "No teams yet" is shown.
13. **After the deletion**:
    - typing the old address `/teacher/teams?region=…&institution=…&team=<id>` gives "Access
      denied";
    - so do `/teacher/teams/<id>/rename` and `/teacher/teams/<id>/add`;
    - creating "comets" in "Lviv Academy" now works.

**As teacher B (Read)** (US4):

- **The page**: the same teams and members, with no **+ Add team**, **Add students**, **Rename**,
  **Delete** or **Remove**; an empty institution shows the Read hint.
- **Typed addresses**: `/teacher/teams/<id>/add`, `/teacher/teams/<id>/rename` and
  `/teacher/teams/<id>/members/<user>/remove` all give "Access denied".

**As the administrator and as a student**: `/teacher/teams` gives "Access denied", naming the role.

**The deactivation chain** (US6):

1. As teacher A, deactivate KN-21 on **Students**.
2. Its member disappears from the team with no notice, the delete confirmation's count drops, and
   **Add students** no longer offers KN-21.
3. Activate KN-21 again: the member is back.

**Personal data** (US7):

1. As a student in two teams, one of them deleted, open the profile. **Teams** lists both by name,
   with the deleted one as "<name> (deleted)".
2. Withdraw consent.
3. The database holds no `team_memberships` row of theirs, and the teams are still there.
4. A new student invitation shows the consent text with team memberships.

**The institution in-use rule** (US8): as the administrator, try to delete "Lviv Academy", which
holds only a deleted team. It is refused as "in use", with the deactivation suggestion.

## 4. Without JavaScript

Turn JavaScript off.

- **The tab**: the three lists show **Show** buttons and work one step at a time.
- **Add students**: the **Class** list shows **Show**.
- **Forms and confirmations**: every one still works, and every redirect lands as above.

## 5. Phone width and themes

At 360 px and 375 px width (device emulation), in Light and Dark:

- **The tab and every page**: the lists stack in the order Region, Educational institution, Team.
  The member table becomes cards, and "In this team" sits where **Add** would be.
- **Long names**: a 200-character team name and long student names wrap, with no sideways scroll
  (SC-009).

## 6. The four-tab row against the clearances (FR-026)

Measure the frame on `/teacher/teams` at 360 × 640 and 375 × 667, with **Teams** and with
**Competitions** current. Record:

- the frame's `getBoundingClientRect().bottom`;
- the number of tab rows;
- whether the page scrolls sideways.

Use DevTools, or the ad hoc Playwright recipe (`uv run --with playwright`, a copy of the database,
port 8765; see the project's screenshot notes).

**Expected** (research R15): two rows, a frame of about 158.5 px, under
`--sc-frame-clearance-tabs` (176 px below 768 px). Then:

- follow the skip link: `<main>` lands below the frame;
- submit an empty team name and follow the error summary link: the field's label lands below the
  frame;
- tab to a field: it lands below the frame (US9-3).

Record the numbers in `pr-notes.md` and in the guidelines' clearance note. Raise the token only if a
measurement exceeds it.

## 7. The component gallery

Open `/admin/components` outside production:

- `#section-heading` shows its four variants, including the wrapped 200-character title;
- `#table` shows the row with **Add** and the row with "In this team".

Check that both are described in `docs/requirements/ui-guidelines.md` (FR-046).
