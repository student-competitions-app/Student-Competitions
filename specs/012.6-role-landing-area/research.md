# Research: Each Role Lands in Its Own Area (Milestone 12.6)

Every decision below was checked against the code on `main` after the milestone 12.5 merge (`da141ce`).
The Technical Context has no open questions: the stack, storage and test tools are unchanged.

## R1. Where the landing redirect lives

**Decision**: The `home` handler (`GET /`, `app/routers/pages.py`) asks `landing_area(current_role)`
(R2). When it returns an area, the handler answers **303 See Other** to `area.path` (`/admin` or
`/teacher`) before it reads the database. Otherwise it renders the student's home page as today. The
`@allow_roles(*ALL_ROLES)` decorator stays, so a signed-out visitor still goes to
`/login?next=%2F`, and a person with several roles and no current role still goes to
`/role?next=%2F`. Both already happen before the handler runs.

**Rationale**: Every way in (sign-in, role choice, role switch, brand link, `/role` with one role)
already ends at `/` (`auth.py` default `next_path="/"`, `roles.py` `RedirectResponse(next_path or
"/")`, `frame.html` `href="/"`). One change at `/` covers all of them (FR-006), and no flow gains a
role-specific address.

**Alternatives considered**:
- *Redirect straight to the first tab* (`/admin/teachers`, `/teacher/students`). This saves one
  round trip but gives two owners to the question of which tab opens first. Today `ADMIN_TABS[0]` and
  `TEACHER_TABS[0]` own it (milestone 6 FR-005, milestone 9 FR-047, spec FR-002). Rejected.
- *Change each flow's return address to the role's area.* There are five call sites, and each would
  need the role. Spec FR-006 forbids it. Rejected.
- *Redirect in the access middleware.* That would mix access checks with navigation. Rejected.

## R2. The area declarations after the Staff area is gone

**Decision**: In `app/routers/areas.py`:

- **Delete** `STAFF_AREA` and the `staff_area` handler.
- `Area` keeps `path`, `title` and `roles`. `description` becomes optional (`Text | None = None`):
  only the student's area has a home page card now. A new optional `back_label` holds the "Back to …"
  label of an area that is a landing.
- `ADMIN_AREA` and `TEACHER_AREA` lose their card descriptions and gain their back labels. They keep
  their titles: the area's name, the same message as the tab row's accessible label.
- `AREAS = (ADMIN_AREA, TEACHER_AREA, STUDENT_AREA)`. `areas_for(role)` stays: the home page calls it,
  now only for the student, and the access tests still compare it with their own access table.
- New: `LANDINGS = {Role.ADMIN: ADMIN_AREA, Role.TEACHER: TEACHER_AREA}` and
  `landing_area(role) -> Area | None`.
- New: `BackLink(path, label)`, `HOME_BACK_LINK = BackLink("/", _("Back to the home page"))` and
  `back_link_for(role) -> BackLink`. It returns the landing's path and back label for an
  administrator or a teacher, and `HOME_BACK_LINK` for everyone else, including `None`.
- The module docstring is rewritten (R10).

**Rationale**: Each area is still declared once: its address, its roles, its name and the label that
leads back to it. The redirect (R1) and the back links (R3) read the same declaration, so they cannot
drift apart.

**Alternatives considered**:
- *Drop `ADMIN_AREA` and `TEACHER_AREA`, and put the addresses in `admin.py` and `teacher.py`.* That
  would scatter the landing mapping across three modules. Rejected.
- *Keep the card descriptions for "completeness".* FR-020 says unused messages go. Rejected.

## R3. How the back links know the role

**Decision**: `back_link_for(role)` (R2) is computed by the two renderers and passed as `back` in the
template context:

- `profile_page` (`app/routers/profile.py`) passes `back_link_for(current_role)`. The route needs a
  chosen role, so this is always the administrator, teacher or student link.
- `_error_page` (`app/main.py`) passes `back_link_for(getattr(request.state, "current_role", None))`.
  On an address no route matched, the access resolver never ran, so the role is missing and the link
  is the home link (spec FR-016, edge cases). The same happens for a refused cross-site request,
  which `resolve_access` raises before it reads the session, and when the session cannot be read. In
  practice only **Access denied** (403) shows an area link.

`profile.html` calls `back_link(back.path, back.label)`. `error.html` keeps its plain link and takes
its `href` and text from `back`. `data_erased.html` does not change (FR-017).

**Rationale**: Only two pages need it. Passing the value keeps the role-to-address rule in Python
(the constitution keeps logic out of templates) and needs no new global.

**Alternatives considered**:
- *A Jinja global or context processor.* `app/core/templates.py` cannot import `app.routers` without
  inverting the layers, and a global set at router import time is invisible coupling. Rejected.
- *A template macro that compares `current_role.value`.* That puts role logic in a template.
  Rejected.
- *Resolve the session for unknown addresses too.* That would add a database read to every 404 and
  change the 404 page that milestone 10 pinned as identical for everyone (the gallery test). The link
  still ends in the area through `/`. Rejected, and the spec was corrected to match.

## R4. Reading the database line from more than one page

**Decision**: Add `read_database_status_or_none(session) -> DatabaseStatus | None` to
`app/services/database_status.py`. It calls `read_database_status`. On `SQLAlchemyError` it logs
`"Database status unavailable: %s: %s"` (the type name and the message, as milestone 3 FR-026 does
today) and returns `None`. Both readers use it:

- `home` (student only) with its request session. `data_available` becomes `status is not None`, so
  the notice and the line behave exactly as today (FR-003).
- `render_admin` (`app/routers/admin.py`) opens a short read-only `Session(request.app.state.engine)`
  and adds `db_status` to the context of every administrator page. All 20 administrator renders go
  through it, including the component gallery and pages shown again with form errors (FR-010).
  `render_teacher` is untouched, so teacher pages never show the line (FR-011).

Tests make the read fail by patching `app.services.database_status.read_database_status`, a single
seam instead of today's `pages.read_database_status`.

**Rationale**: One function owns "read it, or log and give up", so the home page and the administrator
area cannot handle failure differently (FR-013). `render_admin` takes no session today, and adding a
parameter to 20 call sites only to pass it on is churn. A second short session costs one small read
per administrator page.

**Risk checked**: On SQLite the second connection reads while the handler's own session may hold an
uncommitted write. In SQLite's default journal mode a reader is blocked only while a writer holds
the PENDING or EXCLUSIVE lock during a commit, not by the RESERVED lock of an uncommitted write. The
services commit or roll back before they return (for example `grades._rollback`). On PostgreSQL the
read is independent. The suite runs on both engines (FR-026).

**Alternatives considered**:
- *A context processor reading the status for every page.* That adds a database read to every page,
  teacher pages included, and they must not show the line anyway. Rejected.
- *Pass the handler's session into `render_admin`.* This is correct too, but touches 20 call sites.
  Rejected for churn. It stays the fallback if the SQLite risk ever shows up.

## R5. Where the line's markup lives

**Decision**: Move the `<p data-engine=… data-revision=… data-boots=…>` line from `home.html`'s
`footer_extra` block into the footer of `layouts/base.html`, rendered when the context has a truthy
`db_status`. Delete the `footer_extra` block, which has no other user, and `home.html`'s override. The
markup, message and attributes are unchanged, so the pipeline and the tests read them as before.

**Rationale**: The footer belongs to the shared frame (UI guidelines §frame item 5). One place renders
it for whichever page supplies the status. No new UI pattern is introduced, so the gallery and the
guidelines need only the wording update (R9).

**Alternatives considered**:
- *A macro in `components/frame.html`, called from `home.html` and `layouts/admin.html` through
  `footer_extra`.* This works, but keeps a block whose only purpose is this line. Rejected as the
  larger result.

## R6. Messages

**Decision**: Run `scripts/translations.sh update`, translate the two new Ukrainian entries, then
`scripts/translations.sh compile`. The catalogue tests (`tests/unit/test_catalogues.py`) already fail
on any unused, obsolete or untranslated entry (FR-020, FR-021).

| Change | English | Ukrainian |
|---|---|---|
| removed | Staff area | Розділ працівників |
| removed | Pages shared by administrators and teachers. | Спільні сторінки адміністраторів і педагогів. |
| removed | Manage teachers, educational institutions and subjects. | (its translation) |
| removed | Manage your classes, students and teams, and work with the question bank and competitions. | (its translation) |
| added | Back to the administrator area | Назад до розділу адміністратора |
| added | Back to the teacher area | Назад до розділу педагога |
| kept | Administrator area, Teacher area, Student area, Your areas, Back to the home page, the database line, the unavailable notice | unchanged |

The Ukrainian follows the glossary's area names («Розділ адміністратора», «Розділ педагога») in the
genitive after «до», like the existing «Назад до регіону «Київ»» (UI guidelines §wording).

## R7. Tests

**Decision**: Tests are rewritten by kind, never skipped (FR-023):

1. **Landing** (new, `tests/integration/test_landing.py`): `/` for each single role (303 to `/admin`
   or `/teacher`, the student's home page); signed out (`/login?next=%2F`); several roles with no
   role (`/role?next=%2F`); several roles with each current role; sign-in without `next` for one role
   and through the role choice; the role switch both ways; the brand link; `/role` with one role.
2. **`/staff`** (in `test_access_control.py`): 404 **Page not found** for administrator, teacher,
   student and signed out, the same page as `/no-such-page`. `ACCESS_TABLE`, `TITLES`,
   `PLACEHOLDER_AREAS` and `HOME_LINKS` drop `/staff`. `/` moves to its own landing expectations, and
   the access-denied test now expects the role's back link.
3. **Database line**: on every administrator tab, a page inside a tab, a page shown again with form
   errors and the gallery; absent on teacher pages; when the read fails, an administrator page renders
   without it and the body holds no error detail. The student's home page keeps the milestone 3 and
   10 tests, now as a student.
4. **Back links** (`test_page_patterns.py`, `test_access_control.py`): the profile page per role, the
   **Access denied** page per role, and the home link on `/no-such-page` and on a refused cross-site
   request for a signed-in administrator. Both are answered before the session is read. No route raises an HTTP 404 into
   the error page: the areas render their own "not found" pages, which do not change.
5. **Probes that used `GET /` to mean "still signed in"** (`test_admin_teachers.py`,
   `test_sessions.py`, `test_profile.py`, `test_cross_site.py`, `test_self_invitation.py`,
   `test_user_reconcile.py`): after this milestone an administrator also gets a 303 from `/`.
   Signed-in probes switch to `GET /profile` (any role, 200 when signed in). Signed-out probes assert
   the `Location` starts with `/login`, as `test_user_reconcile.returns_to_login` already does.
6. **Tests that used `/` as a sample page** (`test_layout.py`, `test_form_contract.py`,
   `test_role_switch.py`, `test_login_flow.py`, `test_language.py`, `test_boot_counter.py`,
   `test_health.py`) switch to the page the person now sees: the administrator's or teacher's first
   tab, or the student's home page. `test_health.py` and `test_boot_counter.py` read the line on
   `/admin/teachers`, and patch the new seam (R4).
7. **Deleted**: the administrator and teacher home-card tests, including
   `test_the_teacher_card_names_…` and the `HOME_LINKS` rows for both staff roles, the `/staff`
   parameters of `test_admin_area.py`, and the `/staff` return addresses of `test_role_choice.py`,
   which now use another real page (`/teacher/teams`). A helper or fixture left without a user is
   deleted.

**Rationale**: Principle III wants allowed and denied access per role for every changed route, and
the existing probes would otherwise pass for the wrong reason: a 303 that now means "landed" instead
of "signed out".

## R8. The pipeline's smoke checks

**Decision**: `.github/workflows/checks.yml`, job `image`, step "Sign in, smoke test GET /, restart,
and again":

- `check_home` becomes `check_landing`. It checks that `GET /` answers 303 with `Location: /admin`,
  then runs today's checks on `GET /admin/teachers`: the application name, the signed-in address, the
  logout form, no unavailable notice, `data-engine="postgresql"`, the expected `data-boots`, and the
  **Administrator** role label.
- The area-links assertion (`href="/admin"` and `href="/staff"`, no `/student` or `/teacher`) becomes
  "no link to `/staff`, `/student` or `/teacher`".
- `check_page / 200 'class="brand-role"'` becomes `check_page /admin/teachers 200 'class="brand-role"'`.
- The anonymous and after-logout checks of `GET /` (303 to `/login?next=%2F`) do not change, and
  neither does `scripts/verify_private.sh`.
- The step name and the comments in `checks.yml` and `deploy.yml` that say the home page carries the
  boot count are reworded.

**Rationale**: The job is the only proof that data and sessions survive a restart (README "Service
status"). It must keep reading the line, now where an administrator sees it (spec FR-026).

## R9. Documentation

**Decision**:
- `README.md`: the access table drops the `/staff` row and describes `/` per role. The areas paragraph
  says administrators and teachers land in their area, the home page is the student's, and the
  database line is in the administrator area's footer. The role-switch bullet ("land on the home
  page") says they land in the new role's area. "Service status" says where the boot count is read.
  The source tree comments for `pages.py` and `areas.py` are updated.
- `docs/requirements/ui-guidelines.md`: frame item 1 (the wordmark leads to `/`, which opens the
  current role's area), frame item 5 (the database line is on the administrator area's pages and the
  student's home page), and the card section's "as on the home page" example, which stays true for
  students and is checked.
- `docs/requirements/milestones.md`, Delivered: milestone 3 ("The home page shows a database status
  line…") says administrators see it in their area's footer. Milestone 5 and the others are checked:
  no other summary describes the home page or the Staff area.
- `product-requirements.md` and `technical-requirements.md` were checked and mention neither, so
  nothing changes.
- Specs of delivered milestones are not edited (FR-024).

## R10. Comments and docstrings to correct (FR-022)

- `app/routers/areas.py`: the module docstring (the four areas, "the home page keeps its
  'Administrator area' link").
- `app/routers/admin.py`: "`GET /admin` keeps milestone 5's address (the home page links to it)".
- `app/routers/teacher.py`: "(the home page links to it through `areas.TEACHER_AREA`)".
- `app/routers/pages.py`: the module and `home` docstrings.
- `app/routers/roles.py`: `role_choice` ("goes to the home page") and `choose_role` ("go to … `/`").
- `app/static/css/app.css`: the footer comment ("and on the home page the database line").
- `tests/integration/test_routes.py` around line 408, and every other test docstring that names the
  Staff area or the staff home page.

A final `grep -rniE "staff|home page"` over `app/`, `tests/`, `README.md` and `docs/` checks the
result. The only allowed hits are milestone 12.6's text, the 404 test's `/staff`, the student's home
page and the general word "staff" in the UI guidelines' audience paragraph.
