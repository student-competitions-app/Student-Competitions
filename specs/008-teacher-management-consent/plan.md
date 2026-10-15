# Implementation Plan: User Management with Consent — Teachers (Milestone 8)

**Branch**: `008-teacher-management-consent` | **Date**: 2026-10-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-teacher-management-consent/spec.md`

## Summary

Administrators invite teachers by email. Nothing about the invited person is stored until they
press **I agree**. Administrators then manage teachers' institution links, access levels and the
**Can create competitions** setting. Everyone can see their own profile and withdraw consent, or,
without signing in, delete their data through an emailed link. The teacher and student lists in
the deployment configuration are retired.

**The invitation exists only in the link** (research D1, D2):

- The whole invitation is sealed with AES-256-GCM (new dependency `cryptography`). The key is
  derived from `SECRET_KEY`, and a purpose label is bound as associated data.
- The link `/invitations/<token>` is valid for 7 days, computed from the issue time inside it.
- The same sealing serves the one-hour data-deletion link and two 10-minute notices. These carry
  an address through a redirect without putting it in a URL (D13).

**One generic flow, one role definition** (D3–D6):

- `app/services/invitations.py` issues, evaluates and accepts invitations for any role in
  `INVITABLE_ROLES`.
- `app/services/teachers.py` registers the teacher definition (inviter check, institution check,
  description, grant, revoke), and holds list, get, edit and remove.
- **Acceptance**:
  - Re-checks, in this order: the inviter is still an administrator, the institutions are still
    selectable, the invitation is newer than the address's **invitation cut-off** (a keyed hash
    of the address, a role and a time), and the role is not already held.
  - Locks the user row and the institution rows.
  - Writes the user, role, details and a **consent record** referring to a versioned **consent
    text**, in one transaction. A second press ends as "already a teacher".

**Erasure** (D8). One function serves both withdrawal and data deletion:

- It removes every consent-granted role, sets the cut-offs, and clears the names.
- It replaces the email with `erased-<id>`, unless the person holds the administrator role.
- It keeps the consent records, deactivates a person left with no role, and ends every session.

"Has consent data" means the names are stored.

**Data**: one schema revision and one data revision (D18).

- `users` gains `first_name`, `last_name` and `data_erased_at`.
- New tables: `teacher_profiles`, `teacher_institutions`, `consent_texts` (seeded with teacher
  v1, append-only), `consent_records` and `invitation_cutoffs`.
- `retire_role_lists` removes every teacher and student role granted by the old lists. People left
  with no role are deactivated and their emails replaced.

**Configuration** (D15, D16):

- `TEACHER_EMAILS` and `STUDENT_EMAILS` are no longer read.
- `reconcile_users` manages only the administrator role.
- The new `PUBLIC_BASE_URL` (required on Render) is the origin of emailed links, which prevents
  host-header poisoning of the anonymous deletion request.

**Routes** (D17):

- `admin_teachers.py` (administrator) replaces the Teachers placeholder.
- `profile.py` is open to every role.
- `invitations.py` and `data_deletion.py` are public. Their routes are added to `PUBLIC_ROUTES`.
- The header email links to the profile, and the sign-in page gets **Delete my data** and the
  prefill notice.

**Privacy** (D14):

- Services log ids only.
- An access-log filter redacts tokens and sealed values from uvicorn's request lines.
- Link pages send `Referrer-Policy: no-referrer`.
- A test scans every table before acceptance and every captured log line.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`)

**Primary Dependencies**:

- Already in `pyproject.toml`: FastAPI, Jinja2, Pico.css, SQLModel, Alembic, psycopg 3,
  python-multipart.
- **New**: `cryptography`, for AES-256-GCM and HKDF (research D1; justified under Complexity
  Tracking).

**Storage**: SQLite (local, tests) and PostgreSQL (production, Neon via Render). Two new Alembic
revisions on top of `b300a1055049`: `create_consent_and_teachers` (schema and seed) and
`retire_role_lists` (one-time data step).

**Testing**:

- pytest with the FastAPI `TestClient`, on both engines through the `database_url` fixture.
- The `memory` email backend's outbox supplies invitation and deletion links.
- `client_as` and `admin_client` provide signed-in clients. The cast's teacher and student roles
  are now seeded directly by a test-only helper (research D16).

**Target Platform**: Linux container on Render. Any modern browser, including phone width.

**Project Type**: Server-rendered web application (a single FastAPI application).

**Performance Goals**: none beyond the defaults. There are tens of institutions and teachers, and
each page makes a handful of queries. The tokens are short enough for any URL limit, under about
2,000 characters at the worst case.

**Constraints**:

- **Nothing personal before acceptance** (FR-001–FR-003). The only exceptions are keyed hashes,
  for rate limits and cut-offs.
- **No email, name or link in any log line** (FR-004).
- **The same behaviour on SQLite and PostgreSQL** (Principle VII):
  - keys and sorting are computed in Python;
  - `with_for_update` is a no-op on SQLite;
  - string concatenation goes through SQLAlchemy Core.
- **Every action** is a `POST` through the cross-site check, followed by a 303. No JavaScript.

**Scale/Scope**:

- 11 new `GET` routes: teachers list, invite, teacher page, remove confirmation, invitation,
  profile, withdraw confirmation, deletion request, requested, deletion confirmation, and data
  erased. The existing sign-in page also gains the prefill.
- 7 new `POST` routes.
- 5 new tables and 3 new `users` columns.
- 1 placeholder removed.
- 2 settings retired and 1 added.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 7 is merged into `main` (its regions and institutions code and migrations are this branch's base). This is one vertical slice: tables → services → routes → pages → tests, ending in a demonstrable invite → accept → manage → withdraw path. Nothing from milestone 9 is built. The student role gets no flow, form or page, and `INVITABLE_ROLES` holds only the teacher. Access levels and the setting are stored and shown, not enforced (FR-013, FR-068). | ✅ |
| II. Server-rendered simplicity | Jinja2 pages, plain links and forms, and the picker as a table of checkboxes and selects (research D11). No HTMX and no script. **One new runtime dependency** (`cryptography`), justified below. The one new abstraction (`InvitableRole`) is required by FR-005 and has its second user in the next milestone (Complexity Tracking). | ✅ (justified) |
| III. Test-backed delivery | Every milestone 8 _Test:_ item maps to a test module ([quickstart.md](./quickstart.md) §1). Unit tests cover sealing, schemas, redaction, configuration and emails. Service and HTTP tests run on both engines. Allowed and denied access per role for every new route. Migration stairway, drift and the retirement are tested. The email sender is the `memory` fake, with no real external service. | ✅ |
| IV. Role-based access | Teacher management is `@allow_roles(Role.ADMIN)`. The profile is `ALL_ROLES` and acts only on `request.state.user`. Invitation and deletion pages are added to the reviewed, test-pinned `PUBLIC_ROUTES`: they carry their own authority (the sealed token) and act only on the person it names (FR-055, FR-065). Only administrators link teachers to institutions and set levels (FR-008). The administrator list still comes only from configuration, and the reconcile now manages only it. | ✅ |
| V. Secure authentication & secrets | Sign-in is unchanged. New keyed values use `SECRET_KEY`, with purpose labels (HKDF info and AAD for seals, an HMAC label for cut-offs). Logs carry no emails, names, tokens or URLs with tokens (FR-004, access-log redaction). Every new write is a `POST` behind the cross-site check. Anonymous email-sending forms are rate-limited per address and per client. Emailed links use the configured origin, not the `Host` header. `PUBLIC_BASE_URL` is not a secret. | ✅ |
| VI. LLM evaluation | Not touched. | n/a |
| VII. Data integrity & migrations | Five SQLModel models and two Alembic revisions. Portable SQL only. Timestamps use `UTCDateTime`. Users are never hard-deleted. Consent records and consent texts are append-only. An institution with teacher links cannot be deleted (in-use count and foreign-key backstop). The data revision's downgrade is a documented no-op (Complexity Tracking). | ✅ |
| Workflow gates | The plan lists the role-access tests, both migrations, and the README, `render.yaml` and requirements updates for the configuration change. | ✅ |

**Post-design re-check (after Phase 1)**: still all ✅.

- The only dependency added is `cryptography`, justified below.
- No engine-specific SQL. `FOR SHARE` (`with_for_update(read=True)`) and `FOR UPDATE` are
  SQLAlchemy constructs that are omitted on SQLite, where writers are already serialised.
- `PUBLIC_ROUTES` grows by exactly the eight entries in
  [contracts/http-routes.md](./contracts/http-routes.md), and each one is a page whose access is
  carried by a sealed token or that changes nothing.
- No route outside those reads or acts on anyone but the signed-in user, except teacher
  management, which is administrator-only.

## Project Structure

### Documentation (this feature)

```text
specs/008-teacher-management-consent/
├── plan.md                         # This file
├── research.md                     # Phase 0: decisions D1–D19
├── data-model.md                   # Phase 1: users changes, 5 new tables, sealed payloads, migrations
├── quickstart.md                   # Phase 1: automated and manual validation, post-deploy check
├── contracts/
│   ├── http-routes.md              # Phase 1: every route, status and page
│   ├── services.md                 # Phase 1: sealing, invitations, teachers, consent, deletion, reconcile
│   └── configuration.md            # Phase 1: lists retired, PUBLIC_BASE_URL, start-up
├── checklists/requirements.md      # From /speckit-specify
└── tasks.md                        # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
pyproject.toml / uv.lock               # CHANGED: + cryptography

app/
├── core/
│   ├── sealing.py                     # NEW: seal/unseal (AES-256-GCM, HKDF, purpose as AAD)
│   ├── log_redaction.py               # NEW: AccessLogRedactor for uvicorn.access
│   ├── security.py                    # CHANGED: + hash_invitation_cutoff_key
│   ├── config.py                      # CHANGED: lists retired; + PUBLIC_BASE_URL (C11–C13)
│   ├── auth.py                        # CHANGED: PUBLIC_ROUTES += 8 entries
│   └── templates.py                   # CHANGED: + `utc` filter
├── models/
│   ├── __init__.py                    # CHANGED: export the new models and AccessLevel
│   ├── user.py                        # CHANGED: + first_name, last_name, data_erased_at; docstring
│   ├── user_role.py                   # CHANGED: docstring (writers)
│   ├── teacher.py                     # NEW: AccessLevel, TeacherProfile, TeacherInstitution
│   └── consent.py                     # NEW: ConsentText, ConsentRecord, InvitationCutoff
├── schemas/
│   ├── names.py                       # CHANGED: has_control_character made public (no behaviour change)
│   ├── people.py                      # NEW: clean_person_name, clean_email
│   └── teachers.py                    # NEW: TeacherDetails, parse_institution_choices
├── services/
│   ├── rate_limits.py                 # CHANGED: generic allow(); allow_code_request wraps it
│   ├── users.py                       # CHANGED: reconcile admin only; get_user_by_email, end_all_sessions, display_name
│   ├── institutions.py                # CHANGED: list_selectable_institutions, describe_institutions; count uses
│   ├── email.py                       # CHANGED: invitation_message, deletion_message
│   ├── invitations.py                 # NEW: InvitableRole, registry, issue/evaluate/accept
│   ├── teachers.py                    # NEW: TEACHER_INVITATION; list/get/update/remove
│   ├── consent.py                     # NEW: texts, records, cut-offs, erasure
│   └── data_deletion.py               # NEW: deliver link (background), read, confirm
├── routers/
│   ├── admin.py                       # CHANGED: Teachers placeholder handler removed
│   ├── admin_teachers.py              # NEW: /admin/teachers…
│   ├── invitations.py                 # NEW: /invitations/{token}
│   ├── profile.py                     # NEW: /profile, /profile/withdraw
│   ├── data_deletion.py               # NEW: /data-deletion…, /data-erased
│   └── auth.py                        # CHANGED: GET /login reads `prefill`
├── main.py                            # CHANGED: include 4 routers; reconcile(admin_emails); install redactor
└── templates/
    ├── layouts/base.html              # CHANGED: header email → /profile
    ├── pages/login.html               # CHANGED: prefill notice; "Delete my data" link
    ├── pages/admin/
    │   ├── teachers.html              # NEW: list, empty state, "Invitation sent" banner
    │   ├── teacher_invite.html        # NEW: invitation form
    │   ├── teacher_form.html          # NEW: teacher page (edit)
    │   ├── teacher_remove.html        # NEW: confirmation
    │   ├── teacher_not_found.html     # NEW
    │   ├── _institution_picker.html   # NEW: included by invite and edit forms
    │   └── placeholder.html           # unchanged (no tab uses it now; kept for later tabs)
    └── pages/
        ├── invitation.html            # NEW: acceptance page (+ consent-changed note)
        ├── invitation_status.html     # NEW: expired / neutral / already a teacher
        ├── profile.html               # NEW
        ├── profile_withdraw.html      # NEW: confirmation (also the 409 "nothing to withdraw")
        ├── data_deletion_request.html # NEW
        ├── data_deletion_requested.html  # NEW
        ├── data_deletion_confirm.html # NEW
        ├── link_status.html           # NEW: deletion link expired / neutral
        └── data_erased.html           # NEW

migrations/versions/
├── 2026_10_xx_<rev>_create_consent_and_teachers.py   # NEW: schema + teacher consent text v1
└── 2026_10_xx_<rev>_retire_role_lists.py             # NEW: one-time data step

tests/
├── conftest.py                        # CHANGED: ADMIN_EMAILS only; seed_roles_directly for the cast;
│                                      #   helpers: invite_and_accept, make_institution
├── unit/
│   ├── test_sealing.py                # NEW
│   ├── test_person_schemas.py         # NEW
│   ├── test_teacher_schemas.py        # NEW
│   ├── test_log_redaction.py          # NEW
│   ├── test_consent_texts.py          # NEW: pinned SHA-256 per published version
│   ├── test_auth_config.py            # CHANGED
│   ├── test_email.py                  # CHANGED: + invitation and deletion messages
│   └── test_security.py               # CHANGED: + cut-off hash (keyed, purpose-separated)
└── integration/
    ├── test_teacher_invitation.py     # NEW (US1, end to end)
    ├── test_invitation_refusals.py    # NEW (US2)
    ├── test_invitation_cutoff.py      # NEW (US2-6..8)
    ├── test_invitation_edge_cases.py  # NEW
    ├── test_admin_teachers.py         # NEW (US3)
    ├── test_profile.py                # NEW (US4)
    ├── test_data_deletion.py          # NEW (US5)
    ├── test_self_invitation.py        # NEW (US6)
    ├── test_consent_privacy.py        # NEW (SC-002, SC-007)
    ├── test_user_reconcile.py         # REWRITTEN (US7)
    ├── test_startup.py                # CHANGED: lists no longer read
    ├── test_login_flow.py             # CHANGED: cast via seeding; prefill; "Delete my data" link
    ├── test_institution_service.py    # CHANGED: linked institution is in use
    ├── test_admin_area.py             # CHANGED
    ├── test_routes.py                 # CHANGED
    ├── test_access_control.py         # CHANGED (US8)
    ├── test_cross_site.py             # CHANGED
    └── test_migrations.py             # CHANGED

README.md                              # CHANGED: roles/config, PUBLIC_BASE_URL, local sign-in, layout
render.yaml                            # CHANGED: lists removed, PUBLIC_BASE_URL added
docs/requirements/milestones.md        # CHANGED on delivery: milestone 8 moves to "Delivered"
```

**Structure Decision**: the existing single-application layout from the constitution, with no
new top-level directories.

- **One router module per area**, as in milestones 6 and 7.
- **The generic flow** (`invitations.py`, `consent.py`) **and the role** (`teachers.py`) are
  separate service modules. `teachers.py` imports the protocol types from `invitations.py`.
  `invitations.py` reads the registry through a function, `invitable_role(role)`, that imports
  `teachers` lazily, so there is no import cycle. `consent.py` imports the registry the same way.
- **Pure primitives** (`sealing.py`, `log_redaction.py`) live in `core/`, beside `security.py`.

### Changes to existing tests (why they change)

| Test | Change | Reason |
|---|---|---|
| `tests/conftest.py` | `client` sets only `ADMIN_EMAILS`. After start-up, `seed_roles_directly` inserts the cast's teacher and student roles (test-only, like `sign_in_directly`). New helpers create institutions and accept invitations through the real services. | Lists retired (FR-056). The cast must survive for milestone 5–7 tests (research D16). |
| `test_user_reconcile.py` | Rewritten for `reconcile_users(session, admin_emails)`. | FR-057. |
| `test_startup.py` | Cases that started with teacher or student lists now assert the lists are ignored. | FR-056. SC-010 allows replacing tests of the retired lists. |
| `test_auth_config.py` | C9, C10 and W4 cases removed. W3 reworded. C11–C13 added. | [contracts/configuration.md](./contracts/configuration.md). |
| `test_login_flow.py` | Teacher and student sign-in cases use the seeded cast. Prefill and **Delete my data** link cases added. | Lists retired. FR-032, FR-049. |
| `test_admin_area.py` | `PLACEHOLDERS` loses `/admin/teachers`. Every page of this feature marks the Teachers tab. | The placeholder is replaced (SC-010). |
| `test_routes.py` | `test_the_write_routes_are_exact` += 7. `test_the_allowlist_is_exact` += 8. The declared-page sweep is unchanged: `/admin/teachers/1` is a `404` for the administrator (≠ 403) and a `403` for others. `/profile` is allowed for all three roles. | The write and public surfaces grow on purpose, and are still pinned exactly. |
| `test_access_control.py` | New `ADMIN_PAGES` and `ADMIN_ACTIONS` rows for teacher management, with users, roles, links and profiles compared before and after each refusal. Profile rows for every role. | US8, FR-063, FR-064. |
| `test_cross_site.py` | A cross-site invite, an acceptance and a deletion confirmation are refused, and nothing changes. | FR-059. |
| `test_institution_service.py` | The monkeypatched-count test stays. Added: a real teacher link makes the institution in use. | FR-012. |
| `test_migrations.py` | `APPLICATION_TABLES` += 5. Added: a retirement test, seeded at the previous revision. | Research D18. |

## Implementation Order (for /speckit-tasks)

1. **Primitives**: add `cryptography`. Then `core/sealing.py`, the cut-off hash in `security.py`,
   `core/log_redaction.py`, `schemas/people.py` and `schemas/teachers.py`, each with its unit
   tests.
2. **Configuration and retirement** (blocks every story, because the cast changes):
   - `config.py` (lists retired, `PUBLIC_BASE_URL`);
   - `reconcile_users` (admin only) and `main.py`;
   - `conftest.py` seeding;
   - rewritten reconcile, start-up and config tests;
   - `render.yaml`.

   The whole existing suite must be green again.
3. **Foundation**:
   - the models and the `create_consent_and_teachers` migration (drift and stairway green);
   - the `retire_role_lists` migration and its test;
   - the generic `rate_limits.allow`;
   - `institutions.py` additions (selectable list, describe, count uses);
   - `consent.py` (texts, records, cut-offs, erasure) with service tests;
   - `invitations.py` with the registry and `teachers.TEACHER_INVITATION`;
   - email messages.
4. **US1 + US2** (P1):
   - the invite form and `POST`;
   - the Teachers list (minimal);
   - `/invitations/{token}` `GET` and `POST`;
   - the sign-in prefill;
   - the end-to-end, refusal and cut-off tests.
5. **US3** (P1): the full list, the teacher page, edit, remove, the in-use test, and the tab
   tests.
6. **US4** (P2): the profile, the header link, withdrawal, and the profile tests.
7. **US5** (P2): the data deletion pages, the background delivery, the link checks, and the tests.
8. **US6** (P3): the self-invitation tests. No new code is expected.
9. **US7** (P2): verify that the retirement and the admin-only reconcile are covered (done in
   steps 2–3), and add any missing scenario.
10. **US8** (P3): the role × route matrix, cross-site tests, and route-table updates.
11. **Privacy and polish**:
    - `test_consent_privacy.py` (table scan, log scan) and the access-log redactor wiring;
    - `Referrer-Policy` and `Cache-Control` headers;
    - README updates;
    - `ruff`;
    - the manual walk-through ([quickstart.md](./quickstart.md)).

## Complexity Tracking

> Choices that add a dependency or look like extra complexity, each justified.

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| New runtime dependency `cryptography` (AES-256-GCM, HKDF) | FR-020 requires the link to be encrypted *and* tamper-proof, and the standard library has no cipher (research D1). | Signed-only tokens (`itsdangerous`, HMAC) leave the email and names readable in the URL. A home-made HMAC stream cipher is unreviewed cryptography. Storing pending invitations is forbidden (FR-002). |
| `InvitableRole` protocol and registry with one implementation | FR-005 requires the flow to be identical for every invitable role. Milestone 9 adds the student definition and must not change the flow ("milestone 8 tests pass unchanged"). | Hard-coding the teacher flow means rewriting invitation, acceptance and withdrawal in milestone 9. |
| `invitation_cutoffs` table keyed by an HMAC of the address | FR-027 and FR-034: a removal or withdrawal must beat older invitations even after the email has been replaced (research D5). | A column on the user or role row is lost when the email is replaced or the role row is deleted. An unkeyed hash is reversible by guessing (FR-003). |
| Row locks (`FOR UPDATE` on the user, `FOR SHARE` on institutions and regions) during acceptance and edits | FR-031 (one grant, one record) and FR-026 or FR-009 under concurrent deactivation or removal (research D6, D9). | Without locks, PostgreSQL lets a concurrent removal or deactivation slip between the check and the write. |
| Sealed query values for "Invitation sent to …" and the sign-in prefill | FR-060 needs a redirect, and FR-004 (milestone 4 research D11) keeps addresses out of URLs (research D13). | A plain address in the query reaches the access log. A flash cookie means more state and more flags. Rendering on `POST` breaks reload safety. |
| `AccessLogRedactor` on `uvicorn.access` | Uvicorn's access log prints request paths, which contain the tokens (FR-004, research D14). | `--no-access-log` throws away all request observability. |
| `PUBLIC_BASE_URL`, required on Render | Links in the anonymous deletion email must not come from the `Host` header (host-header poisoning), and Render's proxy hides the `https` scheme (research D15). | Building links from the request is unsafe in production. |
| `retire_role_lists` data migration with a no-op downgrade | The grants from the retired lists must be removed exactly once, before code that can no longer tell them from consent grants starts (research D16). | Doing it in the reconcile at every start would remove consented teachers. A real downgrade cannot restore grants whose source configuration no longer exists. |
| Per-client limit on deletion requests (beyond the spec's per-address limit) | An anonymous form that sends email follows milestone 4's two-bucket pattern (spec Assumptions; research D12). | A per-address limit alone lets one client make the application email every consented address. |
