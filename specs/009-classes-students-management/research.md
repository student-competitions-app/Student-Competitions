# Research: User Management with Consent — Classes and Students (Milestone 9)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Phase 0 of `/speckit-plan`. The spec has no open clarifications: FR-014 and FR-017 were settled on
2026-10-19 (spec §Clarifications). The stack is fixed by the constitution, and this milestone adds
no dependency. Each decision below records what was chosen, why, and what was rejected.

The milestone 8 design is the base: sealed invitations, the `InvitableRole` registry, consent
texts and records, cut-offs, erasure, and Post/Redirect/Get with sealed notices
(specs/008-teacher-management-consent/research.md D1–D19). This milestone adds the second
invitable role. It changes the generic flow in one place only, the names rule (D10).

---

## D1. Two new tables: `classes` and `enrolments`

**Decision**:

- **`classes`** (`app/models/school_class.py`, model `SchoolClass`): `id`, `institution_id`,
  `name`, `name_key`, `year_of_study`, `is_active`, `created_at` and `updated_at`.
  - Unique `(institution_id, name_key)`, as institutions are unique within their region. The
    leading `institution_id` also serves the per-institution list, so there is no separate index.
  - `CHECK (year_of_study BETWEEN 1 AND 12)`.
- **`enrolments`** (`app/models/enrolment.py`): `user_id` (primary key, FK `users.id`), `class_id`
  (FK `classes.id`, indexed), `created_at`, and `updated_at`, which changes on a move.
  - The primary key on `user_id` is what makes "at most one enrolment per person" hold under any
    concurrency (FR-008, SC-006).
- The enrolment stores **only the class**. The institution is the class's institution. A class
  never moves (FR-003), and a move is checked to stay in the same institution (FR-041), so the
  institution of an enrolment can never change.

**Rationale**:

- The model is named `SchoolClass` because `class` is a Python keyword. The table and every
  user-facing word stay "class".
- Storing the institution a second time would need a composite foreign key to keep the two in
  step. It would add an invariant and buy nothing: every query that needs the institution already
  joins the class.

**Alternatives rejected**:

- `enrolments.institution_id` beside `class_id`: redundant, as above.
- The class as a column on `users`: it would mix personal data into the user row and need its own
  rules for erasure.
- A surrogate `id` on enrolments: nothing refers to an enrolment, and the person is its natural
  key.

---

## D2. The deactivation chain is computed on read, never stored

**Decision**: one small module, `app/services/availability.py`, is the only place that decides
availability (FR-011–FR-016).

- **Available class**: the class, its institution and its region are all active.
- **Blocked student**: the person **has an enrolment** whose class is not available.
- Statuses are never cascaded. Deactivating an object writes only its own `is_active`, so
  activating it again gives back exactly the statuses below it (FR-012, FR-017).
- A student role **without** an enrolment counts as usable.
  - In the application this state cannot occur: the student role and the enrolment are granted
    and revoked together (D9), and nobody holds the student role after milestone 8's
    `retire_role_lists`.
  - It occurs only for the test cast, whose student roles are seeded directly (milestone 8 research
    D16). Treating them as usable keeps every milestone 5–8 test unchanged (SC-010).

**Rationale**: the rule is about who may sign in and what teachers see, so it must hold on every
read. A computed rule cannot drift from the statuses it is computed from.

**Alternatives rejected**:

- A stored `blocked` flag or cascaded statuses: they must be rewritten on every activation and
  deactivation, they lose each object's own status (forbidden by FR-012), and they can drift.
- Fail-closed "no enrolment ⇒ blocked": in production it equals the chosen rule, but it would
  change the milestone 5–8 test cast. Giving the cast enrolments would create regions and
  institutions, which breaks the milestone 7 tests that start from an empty list.

---

## D3. Usable roles: sessions, sign-in and the role choice

**Decision**: `availability.usable_roles(session, user_id)` returns the roles held, without the
student role while the person is blocked. It replaces the roles held in exactly three places.

1. **`sessions.get_session_identity`** (every request):
   - When the existing query finds the student role, one extra query checks the enrolment chain.
   - A session whose current role is `student` while the person is blocked is deleted, and the
     request is treated as anonymous. This is the milestone 5 rule for a role no longer held, and it
     is what FR-015 calls "as when a role is removed".
   - If no usable role is left at all, the request is anonymous as well.
   - `SessionIdentity.roles` holds only usable roles. The header switch, the role choice and the
     access rule therefore never offer the student role to a blocked person (FR-015).
2. **`sessions.start_session`**: the initial current role is chosen from the usable roles.
3. **Sign-in** (`login.deliver_login_code` and `login.verify_code`): the new
   `availability.get_signable_user_by_email` replaces `users.get_active_user_by_email` there. It
   finds an active user with at least one usable role.
   - A blocked student with no other role gets no code and cannot use an old one. That is exactly
     the unknown-address behaviour (US5-2), with no new message and no timing difference: the code
     is still issued after the response.

`users.get_roles` keeps its meaning: the roles **held**. Everything that is about holding the role
keeps using it: "already a student" at acceptance and on the invitation form (FR-026, FR-034), the
roles erasure removes, and "no role left" on removal.

**Alternatives rejected**:

- Deactivating blocked users (`is_active = False`): it breaks the invariant "active ⇔ holds a
  role", hides the person from **Delete my data**, and would have to be undone by activation.
- Checking the chain only in the route dependencies: sign-in would still issue codes to blocked
  students.

---

## D4. Signing out at the moment of deactivation

**Decision**: `availability.sign_out_students_below(session, *, region_id | institution_id |
class_id)` deletes every session of every person enrolled in a class below the object. It does not
commit.

- It is called inside the same transaction as the status change by `regions.set_region_active`,
  `institutions.set_institution_active` and `classes.set_class_active`, only when the status
  actually changes to deactivated (FR-015).
- It signs out every such person, including those who also hold another role. "Signed out
  everywhere" is the milestone 5 rule for a role removal. Their other roles are still usable at the
  next sign-in.
- D3 makes this belt and braces rather than the only guard. A request that races the deactivation
  is refused at the very next session lookup anyway.

**Import graph**: `availability.py` imports only `app.models` and `app.services.users`, so
`regions.py` and `institutions.py` can call it without a cycle.

**Alternatives rejected**: relying on D3 alone. It is correct for access, but sessions would linger
in the table and in the header until the next request, and FR-015 asks for a sign-out "at the
moment".

---

## D5. Teacher reach and access levels are checked inside the services

**Decision**: `app/services/teacher_access.py` answers one question for every teacher page and
action: what may this teacher reach, and at which level?

- **Reachable institution**: a `teacher_institutions` row for (teacher, institution), and the
  institution is available (it and its region are active).
- **Reachable class**: any class, active or deactivated, of a reachable institution.
- **Reachable student**: an enrolment whose class is available and whose institution is
  reachable.
- **Errors**: anything else raises `NotReachable`, including unknown ids, a class that is not in
  the named institution, and an institution that is not in the named region. A management action
  without Write raises `WriteRequired`.
- **Where it is checked**: the class and student services take the acting `teacher_id` and run the
  check **in their own transaction**.
  - Writes read the teacher's link row, the institution row and the region row `FOR SHARE`. An
    administrator who lowers the access level or deactivates the institution at the same moment
    waits until the write commits, or commits first and is seen (FR-022).
  - Reads run the same check without locks.
- **The router** maps both errors to the milestone 5 "Access denied" page (`AccessDenied`, 403),
  so unknown, unlinked, unavailable and read-only all look the same. Nothing reveals whether an
  object exists.

**Rationale**:

- Constitution IV requires authorization "on every route and every service operation" and data
  scoping for teachers. Putting the scope check in the service operation means no caller can
  forget it, and the check and the write see the same rows.
- `@allow_roles(Role.TEACHER)` remains the route-level declaration (FR-023).

**Alternatives rejected**:

- A FastAPI dependency that resolves path ids to objects: it runs before the handler's
  transaction, so a write would need a second check under lock anyway.
- 404 for unknown objects, as milestones 7 and 8 do: the spec requires "access denied" for unknown
  objects too (FR-021). A different status would also let a teacher probe which ids exist.

---

## D6. The teacher area: a tab shell like the administrator area

**Decision**: a new `app/routers/teacher.py`, modelled on `app/routers/admin.py`.

- `TEACHER_TABS = (Students /teacher/students, Competitions /teacher/competitions)` and
  `render_teacher(request, template, active_tab, context, status_code)`.
- `GET /teacher` answers `303 /teacher/students`. **Competitions** renders
  `pages/teacher/placeholder.html`.
- `layouts/teacher.html` mirrors `layouts/admin.html`. The tab CSS gets a shared `.area-tabs`
  class, used by both layouts.
- `areas.py` keeps the `TEACHER_AREA` declaration, so the home page still links to `/teacher`, but
  its placeholder handler is removed. This is the same move milestone 6 made for `/admin`.

**Rationale**: FR-047 asks for the administrator area's look and its tab behaviour: ordinary links,
bookmarkable, with the current tab highlighted.

---

## D7. The three lists, without JavaScript, with the selection in the address

**Decision**: the canonical address of the tab is
`/teacher/students?region=<id>&institution=<id>&class=<id>` (FR-050).

- **Three small `GET` forms in a row**, each with its own **Show** button. CSS stacks them on
  narrow screens.
  - The Region form submits `region`.
  - The Institution form submits a hidden `region` and `institution`.
  - The Class form submits hidden `region` and `institution`, and `class`.
  - Changing a higher list therefore never submits a stale lower one.
- A list that is not yet enabled is rendered `disabled` with its **Show** button disabled.
- **No script.** Milestones 6–8 have none, and an auto-submit `onchange` handler would be the first
  inline script, with no CSP in place to review it against. Principle II allows minimal JavaScript,
  but nothing here needs it.
- **Reading the address**:
  - The parameters are read as strings, so a bad value never produces FastAPI's 422 JSON.
  - An empty value counts as absent.
  - `institution` without `region`, or `class` without `institution`, is "access denied". So is a
    value that is not an ASCII integer, unknown, or unreachable, and so is a child that does not
    belong to its parent (FR-021, Edge Cases).
  - `class=new` is the **+ Add class** entry. With Write access it answers
    `303 /teacher/students/institutions/{id}/classes/new`; with Read access it is "access denied".
- **The page in each state** (FR-049):

  | State | Message |
  |---|---|
  | No reachable institution | "You are not linked to any educational institution", all lists disabled |
  | Nothing selected | "Select a region to continue" |
  | Region only | "Select an educational institution to continue" |
  | Institution | "Select a class to see its students" |
  | Active class | the student list, or "No students in this class yet" |
  | Deactivated class | "This class is deactivated; its students are hidden until it is activated again" |

- After every successful class or student action, the browser is sent back to this address with
  the affected class selected.
  - After a delete, the class is no longer selected.
  - After a student is moved, the class the teacher was viewing stays selected ("the affected
    class stays selected", FR-050).

**Alternatives rejected**:

- One form with all three lists: changing the region would submit the old institution, and the
  page would answer "access denied".
- Path segments (`/teacher/students/regions/{r}/institutions/{i}/classes/{c}`), as milestone 7
  does: a `GET` form can only produce a query string, so every **Show** would need a redirect.
- HTMX partials: the full page is small, and HTMX is not yet in the codebase. It can arrive when a
  feature needs it.

---

## D8. Class rules and operations (`app/services/classes.py`)

**Decision**:

- **Names**: `app.schemas.names.clean_name` and `name_key`, the milestone 6 and 7 rules (FR-002).
  The duplicate message is "A class named “…” already exists in this institution."
- **Year of study**: `app.schemas.classes.parse_year_of_study(raw: str) -> int`, pure.
  - The value is trimmed and must be ASCII digits with a value from 1 to 12, so `02` is 2.
  - Empty, `0`, `13`, `2.5`, `+2`, `two` and non-ASCII digits are refused with "Enter a year of
    study from 1 to 12."
  - The form uses `<input type="number" min="1" max="12" step="1">`, and the server is the
    authority.
- **Create**: in a reachable institution with Write access. The institution and region rows are
  read `FOR SHARE`, the link `FOR SHARE` (D5). The unique constraint settles a simultaneous
  duplicate, reported as the duplicate message.
- **Edit**: the name and the year. A change of case alone is a valid rename, and an unchanged
  form writes nothing. Changing the year changes every student's year at once, because the year
  is read from the class (Edge Cases).
- **Deactivate and activate**: no-ops when nothing changes. Deactivating signs the class's
  students out in the same transaction (D4).
- **Delete**:
  - The class row is locked `FOR UPDATE`, then its enrolments are counted, blocked students
    included. Any enrolment means `ClassInUse` (FR-006).
  - The foreign key from `enrolments` is the PostgreSQL backstop. An `IntegrityError` at commit is
    reported as `ClassInUse` too.
- **Against acceptance** (FR-035): acceptance reads the class `FOR SHARE` (D9). Either the
  deletion commits first and acceptance finds the class gone, or acceptance commits first and the
  deletion finds a student. There is never a student without a class.

**Refusals** (FR-053): the refusal page suggests deactivation, with a **Deactivate** link to the
confirmation, only while the class is active.

---

## D9. The student as an invitable role (`app/services/students.py`)

**Decision**: `STUDENT_INVITATION`, the second `InvitableRole`, registered in
`invitations.invitable_roles()` beside the teacher. Its details are
`StudentDetails(institution_id, class_id)` (`app/schemas/students.py`).

| Protocol member | Student behaviour |
|---|---|
| `details_to_payload` | `{"institution": I, "class": C}` |
| `details_from_payload` | exactly these two keys, both non-boolean integers; else `ValueError` → the link is invalid |
| `inviter_may_invite` | the inviter is active, holds the teacher role, and has a **Write** link to `institution` (FR-032). Administrator status plays no part (US3-9). |
| `details_acceptable(lock)` | the class exists, belongs to `institution`, and is available (D2); with `lock`, the class, institution and region rows are read `FOR SHARE` |
| `describe` | "Educational institution: Name (Region)" and "Class: KN-21 · year 2", by current names (FR-031, US3-4). The invitation email uses the same lines (FR-029), so `email.invitation_message` is unchanged. |
| `grant` | `user_roles (user, student)` and `enrolments (user, class)` |
| `revoke` | deletes the enrolment and the student role row |

Everything else comes from the milestone 8 flow unchanged:

- tamper and expiry checks, and the cut-off, keyed per role, so a removal or withdrawal beats older
  student invitations (FR-030);
- the consent-text check and "already a student" (FR-034, where the generic `AlreadyHeld` wording
  is "You are already a student.");
- the user row lock and the retry on `IntegrityError` (FR-035);
- erasure, which already loops over the registry, so the student role, the enrolment and the
  student cut-off are handled with no change to `consent.py` (FR-044).

The inviter check takes no lock: the protocol has no lock parameter for it, and a Write-to-Read
change racing an acceptance at the same instant may go either way, like any two simultaneous
events. Every later acceptance sees the change.

**Alternatives rejected**: a separate student flow. FR-024 requires the milestone 8 flow to take
the second role "without being rebuilt", and `InvitableRole` was introduced for exactly this
(milestone 8 Complexity Tracking).

---

## D10. Names on acceptance (FR-036–FR-038)

**Decision**: in `invitations._accept_once`, the names from the link are written **unless** the
person is active, holds the teacher or the student role, and has names stored. In that case the
names are left as they are.

- A new person, an inactive person, and an administrator with neither role get the invited names
  (FR-037).
- The guard "has names stored" covers only the test cast's directly seeded roles, which have no
  names. In the application, holding the teacher or student role implies stored names.
- The acceptance page (`pages/invitation.html`) shows "If you are already a teacher or a student,
  your current names are kept." for both roles (FR-038).

This is the only change to the generic flow, and it changes milestone 8's behaviour for teacher
invitations on purpose (spec Overview §6). No milestone 8 test has to change, because none of them
covers the changed case:

- the names-related tests accept as a new person or as a removed (inactive) teacher, and both still
  get the invited names;
- before this milestone, no real student existed to accept a teacher invitation.

New tests cover the changed case (US6).

---

## D11. The student invitation form: validation order and limits

**Decision**: `POST /teacher/students/classes/{class_id}/invite` runs these steps; the first failure
answers.

1. **Reach and level**: the class is reachable, with Write access (403 otherwise).
2. **The class is active**: if not, 409 with "This class is deactivated. Students cannot be added
   to it." (spec Assumptions).
3. **The fields**: email and names with the milestone 8 rules (`clean_email`,
   `clean_person_name`). On failure, 400 with every error and every value as typed.
4. **The limits** (FR-027). On failure, 429 "Too many invitations. Please try again later."
   - `invite_student_inviter`: 100 per teacher per hour (new bucket).
   - `invite_email`: 5 per address per hour, **shared** with teacher invitations (spec
     Assumptions).
5. **Not a student already** (FR-026): if the address belongs to a person who holds the student
   role, 400 "This email already belongs to a student", with no institution or class named.
6. **Issue** through `issue_invitation`.
   - `EmailDeliveryError` gives 503 "The invitation email could not be sent. Please try again.",
     and the attempt has already counted (Edge Cases).
   - `InvalidChoice` means a race lost to a deactivation or a change of access; it gives 403.

The limits run **before** the student check on purpose. The check reveals whether an address is a
student anywhere, which FR-026 accepts. Counting every attempt bounds that probe at 100 per
teacher and 5 per address per hour.

**After success**: `303 /teacher/students?region=…&institution=…&class=…&sent=<sealed>`. The
milestone 8 `invitation-sent` notice (10 minutes) shows "Invitation sent to …" above the list. The
address never appears in plain form in a URL or a log.

---

## D12. Editing, moving and removing students

**Decision** (`students.update_student`, `students.remove_student`):

- **Edit**:
  - The student's user row is locked `FOR UPDATE`, then reach and Write are checked (D5).
  - The target class must be **active**, available, and in the **same institution**.
    - A deactivated class of the same institution gives 400, "This class is deactivated."
    - A class of another institution, or an unknown class, is "access denied", because it is not a
      class of this student's institution.
  - Names use the milestone 8 rules.
  - Only what changed is written: the names (and `users.updated_at`), and the enrolment's
    `class_id` (and its `updated_at`).
  - Sessions are never touched (FR-042). There is no new consent and no cut-off (FR-010).
- **Remove** (FR-043), the same steps as `teachers.remove_teacher`:
  1. lock the user row and check reach and Write;
  2. `STUDENT_INVITATION.revoke` (the enrolment and the role);
  3. `set_cutoff(…, Role.STUDENT, now)`;
  4. deactivate the person if no role is left;
  5. `end_all_sessions`;
  6. commit.

  Email, names and consent records stay.
- **Concurrency**: "Student removed while the teacher has their Edit open" works through the lock.
  A later save finds no reachable student and answers 403 (Edge Cases).

---

## D13. The student consent text, version 1

**Decision**: seeded by this milestone's migration as `consent_texts (role='student', version=1)`.
It is placeholder wording, like teacher v1, and `tests/unit/test_consent_texts.py` pins its
SHA-256. It covers every FR-039 topic and never names an institution or a class:

- what is stored: the email, the first and last name, the class and with it the educational
  institution and the year of study; and when the person agreed, to which version, and who invited
  them;
- why: to sign in as a student and to take part in competitions of the institution;
- who sees it: the teachers linked to the student's institution, and the student on their
  profile (spec Assumptions);
- the email delivery service, as in teacher v1;
- how to withdraw, and what withdrawal erases.

`consent_texts` and `invitation_cutoffs` already accept `role = 'student'` (milestone 8 CHECK
constraints), so no constraint changes. The consent record stores no institution or class
(FR-040), because the record's columns are unchanged.

---

## D14. Deleting an institution that holds classes (FR-007)

**Decision**:

- **`count_institution_uses`** counts teacher links **plus enrolments in the institution's
  classes**. It is still the one place that decides whether an institution may be deleted.
- **`delete_institution`** deletes the institution's classes and then the institution in one
  transaction. Classes without students never block the deletion.
  - On PostgreSQL the foreign keys (`enrolments.class_id`, `teacher_institutions.institution_id`)
    are the backstop. An enrolment or link created at the same moment makes the commit fail, and
    the failure is reported as "in use".
  - On SQLite, writers are serialised.
- **The confirmation page** (`institution_delete.html`) says "Its N classes will be deleted too."
  when the institution has classes. The new `classes.count_institution_classes` supplies N.

---

## D15. Confirmation before deactivating a region or an institution (FR-017)

**Decision**:

- Two new `GET` confirmation pages: `/admin/institutions/regions/{r}/deactivate` and
  `…/institutions/{i}/deactivate`.
  - Each names the object and says "Its students will be signed out and hidden until it is
    activated again."
  - A **Deactivate** button posts to the existing `POST` route, which is unchanged.
- In the lists, **Deactivate** becomes a link to the confirmation. **Activate** stays a direct
  form button.
- The "in use" refusal on the institution delete page links to the confirmation instead of
  posting directly.

The milestone 7 tests that look for the direct `<form … /deactivate>` in the list are updated (plan,
"Changes to existing tests"). The `POST` behaviour they test is unchanged.

---

## D16. The profile

**Decision**:

- `profile_page` loads `students.get_enrolment_view(session, user_id)` when the person **holds**
  the student role, blocked or not. The view has:
  - "Educational institution": "Name (Region)";
  - "Class": "KN-21";
  - "Year of study": "2";
  - marked "(deactivated)" when the class is not available (FR-045).
- The "Roles" line keeps showing `request.state.roles`, the usable roles (D3). A blocked student
  who is also a teacher sees "Teacher", with the enrolment shown and marked deactivated (US5-3).
- The correction notes are per role held (FR-046):
  - "Corrections to student data are made by a teacher of your educational institution."
  - "Corrections to teacher data are made by an administrator." (unchanged)
- The consent records list already shows every role's records.

---

## D17. Access tests: object-level denial is a 403 too

**Decision**:

- "Access denied" for an unreachable object uses the same 403 page as a role denial. The spec asks
  for the same words, and D5 keeps unknown and unreachable indistinguishable.
- The milestone 5 sweep `test_every_declared_page_admits_exactly_its_roles` requests every
  declared page with each id set to `1`. For a teacher, that answers 403 on any page that names an
  object. So:
  - The sweep keeps its denied-role assertion (403) for **every** page.
  - For allowed roles, it skips only the teacher pages whose path names an object
    (`TEACHER_SCOPED_PATHS`, computed from the route table: `/teacher/students/…{…}`).
  - A new sweep, `test_every_teacher_page_admits_a_write_teacher`
    (`tests/integration/test_teacher_access.py`), fills each path parameter (`institution_id`,
    `class_id`, `user_id`) with a real, reachable object, and asserts not-403 for a Write teacher.
    It also asserts 403 for a Read teacher on every management page, and for an unlinked teacher on
    every page.
- Because the second sweep is built from the route table, a teacher route added later is covered
  automatically.

---

## D18. One migration

**Decision**: one Alembic revision, `create_classes_and_enrolments`, on top of `f13dab4dd8ba`
(`retire_role_lists`):

- creates `classes` and `enrolments`;
- inserts student consent text v1 (D13);
- downgrade drops both tables and deletes the student consent text v1 row. Downgrade is only
  possible before any student consent record refers to it; that is the same limit as milestone 8's
  teacher text.

No data step: nobody holds the student role after milestone 8 (spec Assumptions). The migration
test adds both tables to `APPLICATION_TABLES`, and the stairway and drift tests cover the rest.

---

## D19. Logging

**Decision**: the milestone 8 rule (FR-057). Every new service logs one line per change, with ids
and counts only:

- "Class created: id=… institution_id=…";
- "Student moved: user_id=… class_id=…";
- "Students signed out: class_id=… sessions=…".

There is no address, no name and no link. The student invitation log line reuses
`issue_invitation`'s line. `test_consent_privacy.py`'s log scan runs over the new flows too
(SC-008).
