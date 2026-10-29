# Research: Teams (Teacher) (Milestone 11.1)

Phase 0 of [plan.md](./plan.md). The spec has no open clarifications, so each entry below records a
design decision, the reason for it and the alternatives considered.

---

## R1. Two tables, and soft deletion with `deleted_at`

**Decision**: two new tables ([data-model.md](./data-model.md)).

- **`teams`**: `id`, `institution_id`, `name`, `name_key`, `created_at`, `updated_at` and a
  nullable, UTC-aware `deleted_at`.
- **`team_memberships`**: one row per (team, student), with the composite primary key
  `(team_id, user_id)` and `created_at`.

**Deleting a team** sets `deleted_at` and changes nothing else: the name, the institution,
`updated_at` and every membership row stay as they were (FR-007, SC-006). A **live** team is one
with `deleted_at IS NULL`. Milestone 12 may add a team to a competition only if it is live; the
services contract states this rule.

- **No restore**: nothing ever clears `deleted_at` (FR-007).
- **No `created_by`**: who created a team is not stored (spec Assumptions), so teams hold no
  personal data and data erasure leaves them alone (FR-014).

**Rationale**: it is the milestone 11 question pattern (011 research R2): one column marks the
state and records when it changed, and both the check and the listing are a plain `IS NULL`.

**Alternatives considered**:

- **An `is_deleted` boolean**: the same check, but it loses the time.
- **Moving deleted teams to another table**: milestone 15 would then need a union to show a
  competition's teams.
- **Hard deletion**: forbidden by FR-007.

---

## R2. Team names: unique among live teams, across all institutions

**Decision**: names follow the subject-name rules through the existing `app.schemas.names`
(`clean_name`, `name_key`), and uniqueness is a **partial unique index** on `teams.name_key`
where `deleted_at IS NULL` (`uq_teams_name_key_live`).

- **Across institutions**: the index has no `institution_id`, unlike classes (FR-002).
- **A deleted team's name is free again**: deleted rows are outside the index, so any number of
  deleted teams may share a name with each other and with one live team (spec Assumptions).
- **Renaming to the team's own name in another case is valid**: the service ignores the team
  itself in the lookup, as `update_class` does.
- **The message** is "A team named “<entered name>” already exists." with the name as the teacher
  entered it (after trimming), never the stored name and never the institution, so nothing about
  another institution leaks (FR-002, US3-1).
- **Races**: the service looks the name up first, for the friendly message, but the index is the
  guarantee. A commit the index refuses (`IntegrityError`) is rolled back and reported as the same
  duplicate error (spec Edge Cases).

**Engine-specific feature, justified (Constitution VII)**: partial indexes exist on both engines
(SQLite since 3.8, PostgreSQL always), and SQLAlchemy declares them with `sqlite_where` and
`postgresql_where` on the same `Index`. A probe on this machine (SQLAlchemy 2.0.54, Alembic 1.20.0)
created the index on SQLite and PostgreSQL 17: a second live row with the same key was refused, any
number of deleted rows were accepted, and `compare_metadata` reported no drift on either engine, so
the project's drift test stays green.

**Alternatives considered**:

- **A plain unique index on `name_key`**: a deleted team would keep its name for ever, against
  FR-002.
- **Renaming a team on deletion** (for example adding a suffix): the stored name would change,
  against FR-007, and the profile and milestone 15 would show the altered name.
- **A lookup without an index**: two simultaneous creates could both pass, against SC-005.

---

## R3. Memberships

**Decision**:

- **At most once per team**: the composite primary key `(team_id, user_id)` (FR-003, SC-004). A
  second insert in a race fails with `IntegrityError` and is reported as "already in this team".
- **Same institution only**: checked when a member is added. The student must be reachable by the
  teacher (R4) and their class must belong to the team's institution (FR-003).
- **The invariant holds afterwards** without a check, because a student's institution never
  changes while they hold the role. A move to another class stays inside the institution
  (milestone 9 `update_student`), and the only way to another institution is removal or withdrawal
  and a new invitation, which erase the memberships first (R7). Moving keeps the teams (FR-005).
- **Removing a member deletes the row** (spec Assumptions). No record is kept, and the student can
  be added again later.
- **No `updated_at`**: a membership is never changed, only inserted and deleted. No "added by":
  not needed, and it would be more personal data.
- **An index on `user_id`** serves the profile list and the erasure delete. The primary key's
  leading `team_id` serves the member list and the counts.

**Alternatives considered**:

- **A surrogate `id` with a unique constraint**: one more column and index, for no use.
- **Keeping removed memberships with a `removed_at`**: whether competitions record their members is
  an open question for milestone 12; this milestone does not need it.

---

## R4. Access: `reach_team`, and the order of checks

**Decision**: `app.services.teacher_access`, the only authority for a teacher's scope, gains
`reach_team(session, teacher_id, team_id, *, institution_id=None, write=False, lock=False)`.

- **A reachable team** is a live team of a reachable institution (an available institution the
  teacher is linked to).
- **`NotReachable`** covers an unknown team, a deleted team, a team of an institution that is not
  linked or not available, and a team that is not in `institution_id` when one is given.
- **`WriteRequired`**: when `write` is set and the level is Read.

The router turns both into the milestone 5 "Access denied" page (403). Unknown, deleted and
unreachable cannot be told apart (FR-022).

**Students** are checked with the existing `reach_student`. It already refuses a person without
the student role, without an enrolment, or in a deactivated class (blocked), and checks the
institution. The team services then require the student's class to be in the team's institution,
so a student of another institution the teacher also reaches is still "access denied" (US4-5).

**Order of checks**, on every route:

1. **The role**: `@allow_roles(Role.TEACHER)`; administrators and students get 403 (FR-019).
2. **The ids** in the address and the form are parsed. Anything that is not an ASCII integer up to
   `MAX_ID` is "access denied", as on **Students**.
3. **The team** (or the institution for **+ Add team**) is reached, with Write for every
   management page and action (FR-021). Read access stops here, before any student id, class id or
   name is looked at (FR-023).
4. **The student** or **the class** named is reached and checked against the team's institution.
5. **Then the rules**: the name, already a member, 50 members.

Every change repeats steps 3 and 4 inside its own transaction, under lock (R5). A link removed or
lowered, or a team deleted, after the page was shown is then seen (US4-6).

**Alternatives considered**: checking teams in the router only. Constitution IV and the milestone 9
pattern (009 research D5) put the check in the service transaction, where it cannot race.

---

## R5. Concurrency: locks inside each write

**Decision**: every team change runs in one transaction that takes its locks in a fixed order:
**team → user → class → institution and region**.

- **`reach_team(..., lock=True)`** reads the team row `FOR UPDATE`, then the link, institution and
  region `FOR SHARE` (through `reach_institution`).
- **`reach_student(..., lock=True)`**, used by add and remove, reads the user row `FOR UPDATE`,
  then the class and the institution rows `FOR SHARE`, as today.

What each race gives:

- **The 50-member limit** (spec Edge Cases, SC-004): `add_member` counts the team's memberships
  while it holds the team row `FOR UPDATE`. Two additions to one team are serialised, so the 51st
  waits, then counts 50 and is refused.
- **Two creates with one name**: the partial unique index refuses the second (R2).
- **Rename or delete against add or remove**: all take the team row first, so they are serialised.
  An addition that waits for a deletion then finds the team deleted and gets "access denied".
- **A class deactivated during an addition**: `set_class_active` locks the class `FOR UPDATE`;
  `reach_student` holds it `FOR SHARE`. Whichever commits first wins: a deactivated class is
  "access denied", and a membership stored just before is hidden like any blocked member's (spec
  Edge Cases).
- **Removal of the student role or erasure during an addition**: both lock the user row first and
  delete the memberships (R7). The addition either commits first, and its row is then deleted, or
  waits and then finds no student role ("access denied").
- **A link lowered to Read, or an institution deactivated**: `FOR SHARE` on the link and the
  institution rows, as for classes.
- **Deleting the institution during a create**: the share lock on the institution makes the
  deletion wait; it then counts the new team and refuses (R8). On PostgreSQL the foreign key is
  the backstop as well.

**No deadlock**: no other code path locks a team row, and the paths that lock a user row (student
removal, erasure, student edit) never lock a team row, so no cycle can form. On SQLite the locks
render nothing, and SQLite already serialises writers, as in milestone 9.

**Alternatives considered**:

- **A `member_count` column**: a second copy of a fact that can drift; the count under the team
  lock is enough for at most 50 rows.
- **A database trigger or check for the limit**: engine-specific, and not needed with the lock.

---

## R6. Blocked members, the member list and the counts

**Decision**: three readings of a team's memberships, each one query.

- **The member list** (FR-035, FR-010): memberships joined to the user, the enrolment, the class,
  the institution and the region, keeping only rows where the class, the institution and the region
  are all active. This is the milestone 9 chain rule (`availability`). The list is sorted in Python
  by last name, then first name, ignoring case, ties by id, like `list_students`. Each row has the
  name and the class label ("KN-21 · year 2").
- **The delete confirmation's count**: the length of the same list. Blocked members are not
  counted (FR-037, US6-2).
- **The limit**: `count(*)` of all the team's memberships, blocked ones included (FR-004, US6-3).

Membership rows never change when a class, institution or region is deactivated (FR-010), so
activating again lists the member again (US6-4). On **Teams**, a team's institution is always
available, so in practice only the class can block a member. The query still checks all three, so
it is right wherever milestone 12 reuses it.

**The Add students page** offers only the active classes of the team's institution (FR-038), so
every student it lists is active (spec Assumptions). Members of the class show "In this team"
(R13).

**Alternatives considered**: showing blocked members with a badge. The spec wants them hidden with
no notice, as on **Students**.

---

## R7. Erasing memberships with the student's data

**Decision**: `STUDENT_INVITATION.revoke` (in `app.services.students`) also deletes every
`team_memberships` row of the user, in deleted teams too, in the same transaction.

`revoke` is already the one place every path out of the student role goes through:

- **Removal** on **Students**: `remove_student`;
- **Withdrawal** on the profile: `erase_personal_data`;
- **Data deletion** without signing in: `erase_personal_data`.

So all three erase the memberships (FR-014, SC-007) with no new call site. The teams themselves are
kept. `revoke` deletes the memberships before the enrolment and the role, so a reader under the
same lock never sees a membership of a student without an enrolment.

**Alternatives considered**: deleting memberships in each of the three callers. That is three
places to keep in step, and a fourth path added later could forget it.

---

## R8. The institution in-use rule

**Decision**: `app.services.institutions.count_institution_uses` adds
`SELECT count(*) FROM teams WHERE institution_id = :id`, deleted teams included (FR-017, SC-008).

- **The refusal is unchanged**: `InstitutionInUse` and the existing 409 page ("“…” is in use and
  cannot be deleted. You can deactivate it instead.").
- **The count is the rule; the foreign key is the backstop**: `teams.institution_id` has no
  `ON DELETE`, so on PostgreSQL a team inserted at the same moment makes the deletion's commit fail,
  which `delete_institution` already reports as "in use". Foreign keys are not enforced on SQLite
  in this application, which is why the count decides.
- **Queried directly** on the `Team` model, as the enrolment count is. `institutions` does not
  import `app.services.teams`, which sits above it (it imports `teacher_access` and `classes`), so
  no import cycle can appear.
- **Deleting a class is unchanged** (FR-018): a class with students cannot be deleted anyway, and
  memberships refer to students, not classes.

---

## R9. Rewriting the student consent text version 1 in place

**Decision**: the new migration updates the stored text in place, and the published-text test
learns a one-off rewrite rule.

**The migration**:

- **Upgrade**: `UPDATE consent_texts SET text = :rewrite WHERE role = 'student' AND version = 1`.
  `published_at` and `version` are unchanged (FR-015, spec Assumptions).
- **Existing consent records** keep pointing at the same row, so they show the new wording (no real
  users exist yet).
- **Downgrade**: writes the original wording back. The migration carries a private copy of it,
  `_STUDENT_CONSENT_TEXT_V1_ORIGINAL`, because one revision module cannot import another.

**Constant names**:

- **The new wording** is `STUDENT_CONSENT_TEXT_V1_REWRITE`.
- **The milestone 9 migration** keeps `STUDENT_CONSENT_TEXT_V1` unchanged: an applied migration
  is never edited, and the stairway test replays it.

**`tests/unit/test_consent_texts.py`**:

- **Collected**: originals (`^([A-Z]+)_CONSENT_TEXT_V([0-9]+)$`) and rewrites
  (`^([A-Z]+)_CONSENT_TEXT_V([0-9]+)_REWRITE$`), each defined in at most one migration.
- **The rewrite must be of a published version**: a rewrite of an unknown version fails.
- **The published text** of a version is its rewrite when one exists, otherwise its original.
  `PUBLISHED` pins that text: `("student", 1)` gets the new SHA-256.
- **A new `SUPERSEDED`** pins the original student version 1 (`0a518ef0…`), so the milestone 9
  migration still cannot be edited unnoticed.
- **`REWRITES_ALLOWED = {("student", 1)}`**: any other rewrite fails the build. The one-time
  exception stays one-time.
- **The topic test** checks the published text, so it now reads the rewrite. It gains "team
  memberships", "teams" and "erased".
- **The private copy** in the new migration must hash to the `SUPERSEDED` pin, so the downgrade
  restores exactly the original.

**`ConsentText`'s docstring** ("append-only… nothing updates") records the one exception and points
here.

**The withdrawal confirmation** is unchanged: it lists the names and the email, as today, and the
consent text itself already says that the class and the team memberships are erased. Listing them
there too was considered, but it is not required and would change a milestone 8 page.

**Alternatives considered**:

- **Publishing version 2**: the spec forbids it (FR-015). Every existing student would then also
  need to agree again.
- **Editing the milestone 9 migration's constant**: databases that already ran it would never get
  the new text, and the stairway would hide that.

---

## R10. Addresses, the selection and where every action returns

**Decision**: the selection lives in the address, as on **Students** (009 research D7):
`/teacher/teams?region=<id>&institution=<id>&team=<id>`, built by one helper,
`selection_path(region_id, institution_id, team_id=None)`.

- **The chain is validated as on Students**: an institution without a region, a team without an
  institution, a region the teacher does not reach, an institution outside the region, or a team
  outside the institution are all "access denied" (FR-022, US4-7).
- **`team=new`** is the **+ Add team** entry. It redirects to the form with Write access and is
  "access denied" with Read.
- **Sticky region and institution** (FR-031): every team belongs to one institution, and a
  `ReachableInstitution` carries its region, so each redirect is built from the team's institution.
  No selection has to be carried through a form, unlike the student pages of milestone 9.

| After | Returns to |
|---|---|
| create | the tab with the new team selected |
| rename, add a member, a repeated addition, remove a member | the tab with the same team |
| delete | the tab with the institution selected and no team |
| Cancel or back link on the new-team form | the tab with the institution selected |
| Cancel or back link on any page of a team | the tab with that team selected |
| an addition beyond 50 | the **Add students** page with the same class |

The routes are in [contracts/http-routes.md](./contracts/http-routes.md). The new-team form posts
to its own address (`…/institutions/{id}/new`), like the rename and delete pages, so every page of
a team and its action share one address.

**The Add students page** keeps its class in the address: `/teacher/teams/<id>/add?class=<id>`
(FR-038). An addition posts `student` and `class`. The class is used only to return to the same
class after a refusal, and is dropped if it is no longer an active class of the institution.

**Alternatives considered**: an HTMX member picker on the tab itself. No page needs a partial,
and a separate page keeps the no-JavaScript path identical (Constitution II).

---

## R11. The notices after Add

**Decision**: the redirect after an addition carries `notice=<sealed token>`.

- **The token**: purpose `team-member-notice`, 10 minutes, payload
  `{"team": <id>, "user": <id>, "outcome": "added" | "already"}`. It is built with
  `app.core.sealing` like the milestone 8 `sent` banner.
- **The tab shows the notice** only if the token is valid and fresh, its team is the selected team,
  and the student is still a listed member. The name is read from the database at that moment:
  - "Taras Shevchenko was added to the team." (success);
  - "Taras Shevchenko is already in this team." (information).
- **Otherwise** the tab shows no notice and the page is unchanged.

**Rationale**:

- **No names in addresses**: query strings appear in access logs, so names there would break FR-016.
- **No misleading notices**: a hand-made address cannot show a notice for a student the teacher did
  not add.
- **Reloads**: reloading within 10 minutes shows the same notice and repeats nothing (SC-010).

**Alternatives considered**:

- **A plain `added=<user id>`**: it can be crafted into a misleading notice.
- **A flash message in the server session**: there is no flash mechanism today, and the sealed
  parameter is the existing pattern.

---

## R12. The section heading becomes a component

**Decision**: a new macro, `section_heading(title, heading_id, action=None, deactivated=False)`, in
`components/frame.html`, next to `page_heading`. The small buttons below the heading come through
`{% call %}`.

```jinja
{% call section_heading(team.name, "team-heading", ("Add students", add_href)) %}
  {{ link_button("Rename", …, kind="secondary", outline=True, small=True) }}
  {{ link_button("Delete", …, kind="destructive", outline=True, small=True) }}
{% endcall %}
```

**Markup**: it emits exactly the markup **Students** hand-builds today:

- `<div class="page-heading">` holding `<h2 id="…">`, which carries the title and, with
  `deactivated`, the **Deactivated** status badge;
- at most one primary `link_button` beside the title;
- then `<div class="row-actions">` with the call block's content.

**Empty actions**: the macro renders the call block first and leaves out the `row-actions` div when
the result is only white space. A page can then always use `{% call %}` and wrap its buttons in
`{% if can_write %}`. Read access then gets no empty row, exactly as today.

**Students looks and behaves exactly as before** (FR-046): only the template changes. A test pins
the heading's markup on **Students** in four states: Write with an active class, Write with a
deactivated class, Read with an active class, and Read with a deactivated class. The section
wrapper `<section aria-labelledby>` stays on the page, because it also holds the content below the
heading.

**The library first**: the macro, its gallery section (four variants: action and row actions,
deactivated badge with row actions, no actions, and a 200-character title that wraps) and its
guidelines entry come before **Teams** or **Students** use it. No new CSS is needed:
`.page-heading` and `div.row-actions` already style it.

**Alternatives considered**:

- **A `{% call(part) %}` macro wrapping the whole section** (the `list_detail` style): it would
  also own the content, which differs on every page.
- **Actions passed as data**: **Students** mixes link buttons and a `post_button` (**Activate**),
  so data would need its own mini-language.

---

## R13. "In this team": a row note

**Decision**: a new macro in `components/table.html`, `row_note(text)`: muted text in the actions
cell, where an action is not available, as in "In this team" (spec Assumptions: plain text, not a
badge).

- **Markup**: `<span class="row-note">`, with one stylesheet rule using the `--sc-muted` token.
- **On a phone**: the note sits in the actions part of the card like a button would.
- **The library first**: it is added to the library, the gallery (a row with **Add** and a row with
  the note) and the guidelines before the **Add students** page uses it.

**Alternatives considered**:

- **A badge**: a badge is a status of the row, and the spec chose plain text.
- **A disabled button**: the guidelines never use disabled buttons for unavailable actions.

---

## R14. The profile lists the student's teams

**Decision**: `app.services.teams.list_student_teams(session, user_id)` returns the student's teams
as `(name, is_deleted)`, sorted by `name_key`, ties by id, deleted teams included (FR-013).

- **Where**: the profile loads it whenever the person holds the student role, blocked or not
  (US7-6), as it loads the enrolment.
- **How it shows**: a **Teams** row in the details list, holding a plain list. A deleted team reads
  "Comets (deleted)" (spec Edge Cases). The words follow the spec, and no new badge word is added.
- **No team**: the row reads "You are not in any team." (US7-2).
- **No institution**: teams are listed by name only, since they all belong to the student's
  institution (spec Assumptions).

---

## R15. The four-tab row against the pinned-frame clearances

**Decision**: the teacher tabs become **Students**, **Teams**, **Questions**, **Competitions**
(`TEACHER_TABS`). They are measured at 360 px and 375 px in Chromium with an ad hoc Playwright run,
as in milestones 10.1 and 11. The result is recorded in `specs/011.1-teacher-teams/pr-notes.md`
and in the guidelines' clearance note (FR-026, SC-009).

**Estimate** (Open Sans 16 px, from the milestone 10.1 and 11 measurements):

- **The labels**: "Students" 72 px, "Teams" about 50 px, "Questions" 81 px, "Competitions" 106 px.
- **The row**: about 309 px of labels plus three 24 px gaps, about 381 px in all. That is wider
  than the content width at 360 px (328 px) and at 375 px (343 px).
- **So the row wraps onto two rows**, the case already measured for the administrator tabs: a
  158.5 px frame.
- **The clearance holds**: 158.5 px is under the 176 px `--sc-frame-clearance-tabs` (11 rem below
  768 px) and under a quarter of a 667 px screen.

The clearances are therefore expected to stay. If the measurement shows three rows, or a frame
taller than 176 px, the token is raised and the guidelines are changed in the same PR. The
measurement also checks that a skip-link target, the error summary and a focused field land below
the frame (US9-3).

**Alternative considered**: a shorter label. "Teams" is already the shortest.

---

## R16. The home page's teacher card

**Decision**: `TEACHER_AREA.description` becomes "Manage your classes, students and teams, and work
with the question bank and competitions." It names students, teams, the question bank and
competitions (FR-027, US9-1). "Work with" covers both reading and changing the bank, which depends
on the **Can manage competitions** setting. `test_home.py` pins the new text.

---

## R17. Tests

**Decision**: the coverage maps onto modules as below. Every integration case runs on SQLite and
PostgreSQL.

- **`tests/integration/test_team_service.py`** (new):
  - create, rename and soft-delete: trimming, every name error, duplicates across institutions and
    in any case, a deleted team's name reused, a case-only rename, an unchanged rename writing
    nothing;
  - the partial index refusing a second live name when the lookup is bypassed (the race);
  - members: added, already a member (and the `IntegrityError` path), the 50-member limit with
    blocked members included, another institution's student, a blocked student, an unknown id;
  - removal, and the other memberships kept;
  - the member list's order and its chain filter, the active count;
  - `list_student_teams`;
  - `count_institution_uses` counting deleted teams;
  - every `NotReachable` and `WriteRequired` refusal, with nothing changed.
- **`tests/integration/test_teacher_teams.py`** (new): the tab end to end through the test client.
  - **Roles**: the administrator and the student get 403 on all 11 endpoints. Read access gets 403
    on the 9 management endpoints, with real, unknown and deleted ids. Write access is allowed
    (SC-002).
  - **The page**: every state message and hint, the tab order, the chain in the address, a broken
    chain, `team=new`.
  - **The forms**: create and rename with errors and values kept, Cancel and back-link targets.
  - **Add students**: class list, empty states, "In this team", the 50-member page, a class of
    another institution or a deactivated class in the address.
  - **Additions and removals**: the notices (and a stale, foreign or tampered token showing none),
    the redirects (SC-003), crafted submissions.
  - **Deletion**: the confirmation text and count, then 403 on every address of the deleted team.
  - **Access changes** between the page and the submit.
  - **Reloads**: a reload after each redirect repeats nothing (SC-010).
  - **Logging**: no email or name in any log line (FR-016).
- **`tests/unit/test_consent_texts.py`**: the rewrite rule, the new pin and `SUPERSEDED` (R9).
- **Updated**:
  - **`test_routes.py`**: the exact write list gains 5 POST routes. `TEACHER_SCOPED_PATHS` also
    takes `/teacher/teams/` paths with an id; the declared-page sweep then checks only the denied
    roles for them, as for `/teacher/students/`.
  - **`test_teacher_access.py`**: its sweeps gain the team routes, with a real team.
  - **`test_form_contract.py` and `form_contract.json`**: new `teacher-team*` cases, generated once
    for those cases only, and recorded in the module docstring.
  - **The gallery and the guidelines**: `test_component_gallery.py` gains `section_heading` and
    `row_note`, `test_page_patterns.py` the new pages, and `test_stylesheet.py` the `.row-note`
    rule.
  - **`test_teacher_students.py`**: the Students heading markup pinned in four states (R12). A
    removal on **Students** erases the student's memberships.
  - **`test_layout.py` and `test_teacher_classes.py`**: four tabs in order.
  - **`test_home.py`**: the new teacher card text.
  - **`test_migrations.py`**: the tables at head; an upgrade from `3e32707ed794` rewrites the
    student text and keeps its version and date; a downgrade restores the original; drift and
    stairway.
  - **`test_admin_institutions.py` and `test_institution_service.py`**: an institution with a team,
    or only a deleted team, is "in use" (US8).
  - **`test_profile.py`**: the teams row, "(deleted)", no team, and a blocked student (US7).
  - **`test_consent_privacy.py` and `test_data_deletion.py`**: withdrawal and data deletion erase
    memberships, in deleted teams too, and keep the teams (SC-007).
  - **`conftest.py`**: `make_team` and `add_member` helpers.

**Rationale**: it follows the module split of milestones 9 and 11 (service, HTTP, sweeps). Every
FR-047 item maps onto one of these cases.
