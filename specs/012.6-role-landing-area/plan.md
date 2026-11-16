# Implementation Plan: Each Role Lands in Its Own Area (Milestone 12.6)

**Branch**: `012.6-role-landing-area` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.6-role-landing-area/spec.md`

## Summary

Administrators and teachers stop seeing the home page and the empty Staff area. `/` redirects them to
their own area. The database line moves to the administrator area's footer, and the profile and error
pages' back links name the person's area. Students see no change. Everything the change leaves unused
is removed.

**Landing** (research R1, R2; [contracts/http-routes.md](./contracts/http-routes.md)):
- `home` asks `landing_area(current_role)`. For an administrator or a teacher it answers 303 to
  `/admin` or `/teacher` before any database read.
- The area addresses keep opening their first tabs.
- Sign-in, the role choice, the role switch, the brand link and `/role` with one role all still end
  at `/`, so they now land in the area with no change of their own.

**Staff area** (R2): `STAFF_AREA` and its handler are deleted, so `/staff` is an unknown address
(404 for everyone, signed out included). `Area.description` becomes optional (only the student's card
has one), and `Area` gains `back_label`.

**Database line** (R4, R5):
- `read_database_status_or_none(session)` in `app/services/database_status.py` reads the line, or
  logs and returns `None`.
- `home` (student) and `render_admin` (every administrator page, through a short read-only session)
  both use it.
- The markup moves unchanged from `home.html` into the footer of `layouts/base.html`, shown when
  `db_status` is set. The `footer_extra` block goes.

**Back links** (R3):
- `back_link_for(role)` returns `/admin` "Back to the administrator area", `/teacher` "Back to the
  teacher area", or `/` "Back to the home page".
- `profile_page` and `_error_page` pass it as `back`.
- On an unknown address or a cross-site refusal the session is never read, so the link stays home.

**Messages** (R6): four messages are removed and two added (Ukrainian «Назад до розділу
адміністратора», «Назад до розділу педагога»). The catalogue tests enforce the rest.

**Tests** (R7):
- A new `test_landing.py`.
- `/staff` 404 for all four kinds of visitor.
- Database-line, back-link and per-role access tests.
- About 15 tests used `GET /` as a "still signed in" probe or as a sample page. They move to
  `/profile`, to a `Location` assertion, or to the page the person now lands on.
- The tests of the staff home cards are deleted.

**Pipeline** (R8; [contracts/pipeline.md](./contracts/pipeline.md)): the `image` job's smoke check now
expects `/` → `/admin`, and reads the boot count and the other checks on `/admin/teachers`.

**Documentation** (R9, R10):
- The README and the UI guidelines are updated.
- The milestone 3 summary in Delivered is updated.
- Code comments and docstrings that name the staff home page are corrected.
- Specs of delivered milestones are not touched.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**: unchanged: FastAPI, Jinja2 (`jinja2.ext.i18n`), SQLModel, Alembic, Babel,
Pico.css v2 (vendored, not edited). No new dependency.

**Storage**: SQLite (local, tests) and PostgreSQL (production), unchanged. No schema change and no
migration ([data-model.md](./data-model.md)).

**Testing**: pytest on both engines (`TEST_POSTGRES_URL`), ruff, the catalogue tests, and the `image`
job of `checks.yml`.

**Target Platform**: one Docker image on Render, unchanged.

**Project Type**: server-rendered web application (one FastAPI app).

**Performance Goals**: no new goal.
- Administrators and teachers lose one full page render on every landing, in exchange for one extra
  redirect.
- Every administrator page gains one small read-only database read: the boot counter row and the
  Alembic revision.

**Constraints**:
- The redirect must not read the database.
- A failed status read must never fail an administrator page.
- Teacher pages must not read the status at all.
- Everything must work without JavaScript, as today.

**Scale/Scope**:
- About 10 application files: `areas.py`, `pages.py`, `admin.py`, `profile.py`, `main.py`,
  `database_status.py`, `base.html`, `home.html`, `profile.html`, `error.html`.
- Comments in `teacher.py`, `roles.py` and `app.css`.
- Both catalogues.
- About 20 test files.
- `checks.yml`, `deploy.yml`, `README.md`, `ui-guidelines.md` and `milestones.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | Status | How |
|---|---|---|
| I. Walking skeleton | ✅ | 12.5 is merged (`da141ce`), and a merge to `main` deploys automatically. Its deployment should be confirmed green before implementation starts. One feature, one branch named `012.6-role-landing-area`. The scope is the milestone's, and the student's landing is deferred to milestone 13+ |
| II. Server-rendered simplicity | ✅ | Server redirects and templates only, no JavaScript. No new dependency. The role-to-address rule stays in Python, not in templates (R3) |
| II. UI guidelines (required from milestone 11) | ✅ | No new component or pattern. Back links use the existing `back_link` component and the "Back to {parent}" wording. The footer line keeps its markup. The guidelines' frame wording is updated in the same PR (R9) |
| III. Test-backed delivery | ✅ | The milestone's _Test:_ line maps to `test_landing.py`, the `/staff` 404 tests, the database-line and back-link tests and the catalogue tests. Allowed and denied access is tested per role for `/` and `/staff`. Fakes are unchanged. CI is green on both engines, with ruff and the `image` job (R7, R8) |
| IV. Role-based access | ✅ | `/` stays `allow_roles(ALL_ROLES)` and deny-by-default. The redirect grants nothing, because each area runs its own check. Removing `/staff` removes a route rather than adding one. The database line is shown only where `render_admin` runs, behind the administrator check |
| V. Secure authentication | ✅ | Sessions, cookies, CSRF and sign-in are untouched. The status-read log keeps the milestone 3 rule: type and message, never the database address. No secrets |
| VI. LLM evaluation | n/a | — |
| VII. Data integrity & migrations | ✅ | No schema or data change. The extra read session is read-only and is checked on both engines (R4 risk note) |
| Application layout | ✅ | The read-or-log helper is in `services/`. Routers stay thin: `home` redirects or renders, and `render_admin` asks the service |
| Operational | ✅ | One image, no new environment variable. Error pages stay friendly |
| Documentation gate | ✅ | README, UI guidelines and milestones Delivered are updated in the same PR (R9) |

No violations, so Complexity Tracking is empty.

**Post-design re-check** (after Phase 1): unchanged, all ✅. Two items were considered and resolved
inside the rules:
- The second database session in `render_admin` (R4, a documented risk, verified on both engines).
- Not resolving the session on unknown addresses (R3), which keeps the milestone 10 404 page
  identical for everyone. The spec's edge cases were corrected to match.

## Project Structure

### Documentation (this feature)

```text
specs/012.6-role-landing-area/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R10
├── data-model.md        # Phase 1: no stored data; Area, landings, BackLink, the status reader
├── quickstart.md        # Phase 1: automated, leftover-search and by-hand validation
├── contracts/
│   ├── http-routes.md   # /, /staff, the flows ending at /, admin footer, back links
│   ├── templates.md     # base footer, home, profile, error; messages
│   └── pipeline.md      # checks.yml image job, deploy.yml comment
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
app/
├── main.py                          # _error_page passes back_link_for(...)
├── routers/
│   ├── areas.py                     # −STAFF_AREA/handler; Area.description optional, +back_label;
│   │                                #   +LANDINGS, landing_area, BackLink, back_link_for; docstring
│   ├── pages.py                     # home: redirect for staff roles; status via the service helper
│   ├── admin.py                     # render_admin adds db_status; docstring
│   ├── profile.py                   # profile_page passes back
│   ├── teacher.py, roles.py         # docstrings only
├── services/
│   └── database_status.py           # +read_database_status_or_none
├── templates/
│   ├── layouts/base.html            # footer renders the line from db_status; −footer_extra
│   └── pages/
│       ├── home.html                # −footer_extra override
│       ├── profile.html, error.html # back link from `back`
├── static/css/app.css               # footer comment only
└── locale/                          # messages.pot, uk/en messages.po (−4, +2)

tests/
├── integration/
│   ├── test_landing.py              # new: R7 item 1
│   ├── test_access_control.py       # /staff 404; tables without /staff; denied-page back link
│   ├── test_home.py                 # student-only home; staff card tests deleted
│   ├── test_layout.py, test_boot_counter.py, test_health.py   # database line on /admin/teachers
│   ├── test_page_patterns.py        # profile back link per role
│   ├── test_admin_area.py, test_role_choice.py, test_role_switch.py, test_login_flow.py,
│   │   test_form_contract.py, test_language.py                # sample pages and /staff params
│   └── test_admin_teachers.py, test_sessions.py, test_profile.py, test_cross_site.py,
│       test_self_invitation.py, test_user_reconcile.py         # "signed in" probes
└── unit/
    └── test_areas.py                # new: landing/back-link invariants (data-model §2–3)

.github/workflows/checks.yml, deploy.yml
README.md, docs/requirements/ui-guidelines.md, docs/requirements/milestones.md
```

**Structure Decision**: The existing single FastAPI application. The change stays inside the modules
that already own areas (`routers/areas.py`), the home page (`routers/pages.py`), the administrator
shell (`routers/admin.py`), the error page (`main.py`) and the status line
(`services/database_status.py`). No new module, apart from the new test file(s).

## Complexity Tracking

No constitution violations to justify.
