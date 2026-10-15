---

description: "Task list for milestone 8: user management with consent — teachers"
---

# Tasks: User Management with Consent — Teachers (Milestone 8)

**Input**: Design documents from `/specs/008-teacher-management-consent/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-routes.md](./contracts/http-routes.md),
[contracts/services.md](./contracts/services.md),
[contracts/configuration.md](./contracts/configuration.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-067 lists the behaviour the automated tests must cover, and Constitution
Principle III makes tests non-negotiable. Every database test runs on SQLite, and also on
PostgreSQL when `TEST_POSTGRES_URL` is set, through the existing `database_url` / `engine` /
`session` / `client` fixtures in `tests/conftest.py`. Signed-in clients come from `admin_client`
and `client_as`. Emails are read from the `outbox` fixture (the `memory` backend).

**Organization**: tasks are grouped by user story. The shared primitives, the role-list
retirement, the tables and the generic invitation/consent services come first (Phases 1–2),
because every story needs them. Routes, pages and story tests follow in priority order.

**Reference implementation**: milestones 4–7 set every pattern used here. Read these before
starting, and match their docstring style, naming, comment density and error handling:

- `app/core/security.py` (`_hmac_hex`, `hash_rate_limit_key`), `app/core/config.py`
  (`resolve_auth_settings`, `AuthSettings.__repr__`), `app/core/auth.py` (`PUBLIC_ROUTES`,
  `allow_roles`);
- `app/services/rate_limits.py`, `app/services/login.py` (`deliver_login_code`, the background
  pattern), `app/services/users.py` (`reconcile_users`), `app/services/institutions.py`
  (`count_institution_uses`, `with_for_update`);
- `app/routers/admin.py` (`render_admin`, the Teachers placeholder), `app/routers/admin_institutions.py`,
  `app/routers/auth.py`;
- `migrations/versions/2026_10_10_b300a1055049_create_regions_and_institutions.py` and
  `2026_09_25_bba0b3665864_seed_sample_questions.py` (a constant inside a migration);
- `tests/conftest.py`, `tests/integration/test_admin_institutions.py`, `test_routes.py`,
  `test_access_control.py`, `test_migrations.py` (`test_upgrade_keeps_the_active_administrators`).

**Rules for every task** (plan Constraints, FR-004):

- Services log ids, roles and counts only — never an email, a name, a token or a URL.
- Every change is a `POST` through the existing cross-site check, answering `303` on success.
- No engine-specific SQL: keys and sorting in Python, `with_for_update` (no-op on SQLite),
  SQLAlchemy Core for string concatenation.
- No JavaScript, no HTMX.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US8)

---

## Phase 1: Setup (Pure primitives)

**Purpose**: the new dependency and the pure building blocks (plan Implementation Order step 1).
None of them touches the database.

- [X] T001 Add `cryptography` to `[project].dependencies` in `pyproject.toml` and run `uv lock` / `uv sync` to update `uv.lock`. Add a one-line comment or README note only where other dependencies carry one (research D1).
- [X] T002 [P] Create `app/core/sealing.py` per contracts/services.md §`app/core/sealing.py` and research D1:
  - `SEAL_VERSION = 1`; `class SealInvalid(ValueError)`; `class SealExpired(ValueError)`;
  - `_key(secret_key)`: HKDF-SHA256, length 32, `salt=None`, `info=b"student-competitions/sealed/v1"`, cached per key (`functools.lru_cache`);
  - `seal(secret_key, purpose, payload, now=None) -> str`: compact JSON (`separators=(",", ":")`) of `payload` plus `"at"` = integer microseconds since the epoch of `now or utc_now()`; AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`) with a random 12-byte nonce (`os.urandom`); AAD `bytes([SEAL_VERSION]) + purpose.encode()`; token `base64.urlsafe_b64encode(bytes([SEAL_VERSION]) + nonce + ciphertext_and_tag)` with `=` padding stripped;
  - `unseal(secret_key, purpose, token, max_age, now=None) -> dict`: validation order 1) base64 decodes (re-pad), 2) version byte known and length ≥ 1+12+16, 3) tag verifies (`InvalidTag` → `SealInvalid`), 4) JSON parses to a `dict` whose `"at"` is an `int` (not `bool`). Any failure raises `SealInvalid`. Only then `now − at ≥ max_age` raises `SealExpired`. Exception messages never contain the token or the payload. No logging.
  - Module docstring lists the four purposes and lifetimes (`invitation` 7 days, `data-deletion` 1 hour, `invitation-sent` and `login-prefill` 10 minutes) and states that the constants live beside their users.
- [X] T003 [P] Create `tests/unit/test_sealing.py`: round trip returns the payload plus `"at"`; the token is URL-safe (`[A-Za-z0-9_-]+`) and contains no plaintext (seal `{"email": "olena@example.org", "first": "Olena"}` and assert neither substring nor its base64 appears); flipping any single byte of the decoded token (loop over every position) → `SealInvalid`; truncated, empty, non-base64 and unknown-version tokens → `SealInvalid`; a different purpose or a different secret key → `SealInvalid`; a JSON payload without integer `"at"` (forge with the real key via the private helpers) → `SealInvalid`; age exactly `max_age` → `SealExpired`, one microsecond less → valid; an expired *tampered* token → `SealInvalid`, not `SealExpired`; two seals of the same payload differ (random nonce); a worst-case invitation payload (254-char address, two 100-character Cyrillic names, 40 institutions) yields a token under 2,000 characters (depends on T002).
- [X] T004 [P] Add `hash_invitation_cutoff_key(secret_key: str, email: str) -> str` to `app/core/security.py` beside `hash_rate_limit_key`: `_hmac_hex(secret_key, "invitation-cutoff\0" + email)`; docstring says the caller normalises the email, cites research D5, and says it is the one keyed hash FR-003 allows for cut-offs. Extend `tests/unit/test_security.py`: deterministic, 64 hex characters, differs for a different key, differs from `hash_rate_limit_key(secret, bucket, email)` for every existing bucket name, and does not contain the address.
- [X] T005 [P] Create `app/core/log_redaction.py` with `class AccessLogRedactor(logging.Filter)` per contracts/services.md and research D14: `filter(record)` always returns `True`; when `record.args` is a 5-tuple `(client, method, full_path, http_version, status)` it rewrites `full_path` (index 2): the path segment after `/invitations/` → `***`, the segment after `/data-deletion/confirm/` → `***`, and the values of the `sent` and `prefill` query parameters → `***` (other parameters untouched). Rebuild `record.args` as a new tuple. Any other record passes unchanged. Use compiled regexes; no logging inside the filter.
- [X] T006 [P] Create `tests/unit/test_log_redaction.py`: build `logging.LogRecord`s shaped like uvicorn's access record (`msg='%s - "%s %s HTTP/%s" %d'`, `args=("1.2.3.4:5", "GET", path, "1.1", 200)`) and assert `record.getMessage()` after filtering for: `/invitations/<token>` → `/invitations/***`; `/invitations/<token>?x=1` keeps `?x=1`; `/data-deletion/confirm/<token>` → `/data-deletion/confirm/***`; `/admin/teachers?sent=<v>` → `?sent=***`; `/login?prefill=<v>&next=/x` → `?prefill=***&next=/x`; `/admin/teachers` and `/login?next=/x` unchanged; a record with non-tuple or 3-tuple `args` unchanged; `filter` returns `True` every time (depends on T005).
- [X] T007 [P] In `app/schemas/names.py`, rename `_is_control` usage into a public `has_control_character(raw: str) -> bool` (true when any character is in a `C*` category, `Zl` or `Zp`) and make `clean_name` call it. No behaviour change: `tests/unit/test_name_schemas.py` and `tests/unit/test_subject_schemas.py` pass unchanged.
- [X] T008 Create `app/schemas/people.py` per research D11 and data-model.md §1 (depends on T007):
  - `PERSON_NAME_MAX_LENGTH = 100`;
  - `class InvalidPersonName(ValueError)` and `class InvalidEmail(ValueError)`, each with `.message`;
  - `clean_person_name(raw: str, field_label: str) -> str`: refuse control characters on the raw value first ("The {field_label} cannot contain tabs, line breaks or other control characters."), then `strip()`, then "Enter a {field_label}." when empty, then "The {field_label} can be at most 100 characters." when over 100 code points; inner spaces kept. `field_label` is "first name" or "last name";
  - `clean_email(raw: str) -> str`: `normalize_email` then `is_valid_email` from `app.core.security`; refuse with "Enter a valid email address." (the sign-in wording).
- [X] T009 [P] Create `tests/unit/test_person_schemas.py`: exactly 100 characters after trimming accepted, 101 refused; "  Olena  " → "Olena"; "Anna  Maria" keeps both inner spaces; "\tOlena", "Ole\nna", "Olena " refused with the control-character message; empty and whitespace-only refused with "Enter a first name."; the field label appears in each message; Cyrillic names accepted; `clean_email("  Olena@Example.org ") == "olena@example.org"`; "not-an-email", "erased-12" and a 255-character address refused (depends on T008).

**Checkpoint**: `uv run pytest tests/unit` is green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: retire the role lists (the test cast changes for every existing test), add the
tables, and build the generic invitation, consent and erasure services that every story uses
(plan Implementation Order steps 2–3).

**⚠️ CRITICAL**: no user story can start until this phase is complete.

### 2a. Configuration and the role-list retirement (the whole existing suite must be green again)

- [X] T010 Change `app/core/config.py` per contracts/configuration.md and research D15, D16:
  - `AuthSettings` loses `teacher_emails` and `student_emails` and gains `public_base_url: str | None = None`; `__repr__` drops the two list counts and shows `public_base_url` as is (not a secret);
  - `resolve_auth_settings` stops reading `TEACHER_EMAILS` and `STUDENT_EMAILS` (leftover values are ignored); C9 and C10 are removed; W4 ("No role lists are set") is removed; W3 becomes "ADMIN_EMAILS is empty; nobody will be able to sign in as an administrator.";
  - reads `PUBLIC_BASE_URL` (blank = unset) and adds C11 "PUBLIC_BASE_URL is required when running on Render.", C12 "PUBLIC_BASE_URL must be an absolute URL with no path, query or fragment." (scheme `http`/`https`, a host, path empty or `/`, no query, no fragment; a trailing `/` is removed), C13 "PUBLIC_BASE_URL must use https when running on Render.". Errors name the setting, never the value; all violations still reported together in the order C1…C8, C11…C13 in one `AuthConfigError`;
  - update the docstrings that mention C1–C10/W1–W4 and the role lists to point at specs/008-teacher-management-consent/contracts/configuration.md.
- [X] T011 Rewrite `reconcile_users` in `app/services/users.py` as `reconcile_users(session, admin_emails: Sequence[str], now=None) -> ReconcileResult` per contracts/services.md and research D16: it reads and writes only `admin` role rows; creates a listed address with no user; reactivates an inactive listed user; adds and removes `admin`; deactivates a user only when no role at all remains; deletes the sessions of everyone who lost `admin`; keeps the final sweep of sessions and login codes of inactive users; `ReconcileResult` keeps its fields. Never reads or writes `teacher`/`student` rows (FR-057). In the same file add `get_user_by_email(session, email) -> User | None` (active or not), `end_all_sessions(session, user_id) -> None` (deletes every `UserSession` of the user, no commit) and `display_name(user) -> str` (`"<first> <last>"` when `first_name` is stored, otherwise the email) (depends on T010 only for the call site).
- [X] T012 Update `app/main.py`: `reconcile_users_with_retry(engine, admin_emails: Sequence[str])` passes `settings.admin_emails` only; update the start-up order docstring to contracts/configuration.md §Start-up order (the redactor line is added in T085). Update the docstring of `app/models/user.py` (role sources: admin from `ADMIN_EMAILS`, teacher from accepted invitations, student nobody until milestone 9) and `app/models/user_role.py` (writers per data-model.md §2) (depends on T010, T011).
- [X] T013 Change `tests/conftest.py` per plan §Changes to existing tests and research D16 (depends on T012):
  - `client` sets only `DATABASE_URL` and `ADMIN_EMAILS`; drop `TEACHER_EMAILS`/`STUDENT_EMAILS` from `AUTH_VARIABLES` handling only if they are no longer needed for isolation (keep them in `_isolate_environment` so a developer's shell value cannot leak in);
  - add test-only `seed_roles_directly(engine, roles_by_email: Mapping[str, Iterable[Role]]) -> None`: for each address, get or create the user (active) and insert the missing `UserRole` rows; docstring says it is test-only like `sign_in_directly`, and that no route or setting can do this;
  - after the `TestClient` starts, call it with the cast's teacher and student roles (`TEACHER_EMAIL`, `TEACHER_STUDENT_EMAIL` → teacher; `STUDENT_EMAIL`, `ADMIN_STUDENT_EMAIL`, `TEACHER_STUDENT_EMAIL` → student), built from the existing `CAST_TEACHER_EMAILS` / `CAST_STUDENT_EMAILS` constants so the cast keeps its five people;
  - update the `client` docstring.
- [X] T014 [P] Rewrite `tests/integration/test_user_reconcile.py` for `reconcile_users(session, admin_emails)`: creates a missing admin; reactivates an inactive listed user; removes `admin` from an unlisted user and deletes their sessions; a user holding only `teacher` (seeded directly) and not listed is untouched — role and `is_active` unchanged; a user holding `admin` + `teacher` who is unlisted loses `admin`, stays active, and loses every session; a user left with no role is deactivated; counts in `ReconcileResult`; no `student`/`teacher` row is ever written (depends on T011).
- [X] T015 [P] Update `tests/integration/test_startup.py`: cases that started with teacher or student lists now assert the lists are ignored (a `TEACHER_EMAILS` value creates no user and no role); the reconcile log line still carries counts and no addresses (depends on T012, T013).
- [X] T016 [P] Update `tests/unit/test_auth_config.py`: remove the C9, C10 and W4 cases; reword W3; add C11 (Render without `PUBLIC_BASE_URL`), C12 (`ftp://x`, `https://x/path`, `https://x?q=1`, `https://x#f`, `example.org` refused; `https://x/` → `https://x`), C13 (`http://` on Render refused, allowed locally); C11–C13 reported in order after C1–C8 in one error; no message contains the value; `repr` shows `public_base_url` and no list counts; a leftover `TEACHER_EMAILS` value is ignored (depends on T010).
- [X] T017 [P] Update `render.yaml` per contracts/configuration.md §`render.yaml`: remove the `TEACHER_EMAILS` and `STUDENT_EMAILS` entries and their comment; add `- key: PUBLIC_BASE_URL` / `value: https://brainring.org.ua`; header comment "Five secrets are declared below by key only".
- [X] T018 Run `uv run pytest` and fix every failure caused by T010–T013 (for example tests reading `settings.teacher_emails` or relying on list-reconciled teachers) without changing what they prove; grep `tests/` and `app/` for `TEACHER_EMAILS`, `STUDENT_EMAILS`, `teacher_emails`, `student_emails` and `role_lists` and remove remaining uses outside `tests/conftest.py` constants (depends on T013–T016).

### 2b. Tables and the schema migration

- [X] T019 [P] Add to `app/models/user.py`: `first_name: str | None` and `last_name: str | None` (`Column(String(PERSON_NAME_MAX_LENGTH), nullable=True)`, "Written only by acceptance and by an administrator's edit. `NULL` = no data stored on consent, or erased."; both set and cleared together) and `data_erased_at: datetime | None` (`sa_type=UTCDateTime`, nullable, "The time of the latest erasure. Makes older deletion links used (research D10)."). Docstring: `email` is replaced by `erased-<id>` on erasure unless the user holds `admin`; invariant active ⇔ at least one role (data-model.md §1).
- [X] T020 [P] Create `app/models/teacher.py` per data-model.md §3–§4:
  - `class AccessLevel(StrEnum)`: `READ = "read"`, `WRITE = "write"`, with a `label` property ("Read"/"Write");
  - `class TeacherProfile(SQLModel, table=True)`, `__tablename__ = "teacher_profiles"`: `user_id` integer PK + FK → `users.id`; `can_create_competitions: bool` NOT NULL default `False` ("FR-007. Only stored and shown in this milestone (FR-013)."); `created_at`, `updated_at` (`UTCDateTime`, NOT NULL, `default_factory=utc_now`; `updated_at` "changed only when the setting changes");
  - `class TeacherInstitution(SQLModel, table=True)`, `__tablename__ = "teacher_institutions"`: `user_id` FK → `users.id` PK part; `institution_id` FK → `institutions.id` PK part, no cascade, indexed as `ix_teacher_institutions_institution_id`; `access_level` `String(5)` NOT NULL with `CheckConstraint("access_level IN ('read','write')", name="ck_teacher_institutions_access_level")`; `created_at`, `updated_at` NOT NULL (`updated_at` "changed only when this link's level changes (FR-040)").
  - Module docstring: invariant "profile row exists ⇔ holds `teacher` ⇔ ≥ 1 link", maintained by `grant`/`revoke` (research D9).
- [X] T021 [P] Create `app/models/consent.py` per data-model.md §5–§7:
  - `class ConsentText`, `__tablename__ = "consent_texts"`: `id` PK; `role` `String(20)` NOT NULL with `CheckConstraint("role IN ('teacher','student')", name="ck_consent_texts_role")`; `version: int` NOT NULL; `text` `Text` NOT NULL; `published_at` `UTCDateTime` NOT NULL; `UniqueConstraint("role", "version", name="uq_consent_texts_role_version")`. Docstring: append-only, inserted by migrations only; current text = highest `version`;
  - `class ConsentRecord`, `__tablename__ = "consent_records"`: `id` PK; `user_id` NOT NULL FK → `users.id`, indexed; `consent_text_id` NOT NULL FK → `consent_texts.id`; `accepted_at` `UTCDateTime` NOT NULL; `inviter_id` NOT NULL FK → `users.id`; `invitation_issued_at` `UTCDateTime` NOT NULL. Docstring: never updated or deleted, including by withdrawal and data deletion;
  - `class InvitationCutoff`, `__tablename__ = "invitation_cutoffs"`: `email_hash` `String(64)` PK part; `role` `String(20)` PK part with `CheckConstraint("role IN ('teacher','student')", name="ck_invitation_cutoffs_role")`; `cutoff_at` `UTCDateTime` NOT NULL ("only ever raised"). No foreign key; holds no readable personal data (FR-003, FR-034).
- [X] T022 Export `AccessLevel`, `TeacherProfile`, `TeacherInstitution`, `ConsentText`, `ConsentRecord`, `InvitationCutoff` from `app/models/__init__.py` so Alembic metadata and drift tests see them (depends on T020, T021).
- [X] T023 Generate and hand-edit `migrations/versions/2026_10_xx_<rev>_create_consent_and_teachers.py` (down revision `b300a1055049`) per data-model.md §10 and research D18: `users` + `first_name`, `last_name` (`String(100)`, nullable) and `data_erased_at` (`UTCDateTime`, nullable) inside `op.batch_alter_table("users")`; create `teacher_profiles`, `teacher_institutions` (+ `ix_teacher_institutions_institution_id`), `consent_texts`, `consent_records` (+ index on `user_id`), `invitation_cutoffs` with the exact constraint names from T020/T021; define a module constant `TEACHER_CONSENT_TEXT_V1` (placeholder wording covering FR-036: what is stored — email, first and last name, institutions with access levels, the competitions setting; why; who sees it — administrators, and the teacher on their profile; that emails are delivered by Resend; how to withdraw — profile → **Withdraw consent**, or **Delete my data** on the sign-in page; plain text, paragraphs separated by blank lines) and insert `("teacher", 1, TEACHER_CONSENT_TEXT_V1, <fixed published_at>)` with `op.bulk_insert`. Downgrade drops the five tables and the three columns (batch on SQLite) (depends on T019–T022).
- [X] T024 Update `tests/integration/test_migrations.py`: `APPLICATION_TABLES` += `teacher_profiles`, `teacher_institutions`, `consent_texts`, `consent_records`, `invitation_cutoffs`; empty → head, head → head, stairway, single head and model/schema drift stay green on both engines (depends on T023).
- [X] T025 [P] Create `tests/unit/test_consent_texts.py`: load every revision module via `ScriptDirectory.walk_revisions()` (as the `sample_questions` fixture does), collect constants named `*_CONSENT_TEXT_V*`, and assert a pinned SHA-256 for each published `(role, version)` (`PUBLISHED = {("teacher", 1): "<sha256>"}`); a new constant without a pin, or a changed text, fails with a message saying "published consent texts are append-only; add a new version in a new migration" (research D7) (depends on T023).

### 2c. The one-time retirement migration

- [X] T026 Create `migrations/versions/2026_10_xx_<rev>_retire_role_lists.py` (down revision: T023's) per data-model.md §10 and research D16, using SQLAlchemy Core table stubs (no models): 1) delete the sessions of users holding `teacher` or `student`; 2) delete every `teacher` and `student` row of `user_roles`; 3) for every user with no remaining role row: `is_active = false`, `email = literal("erased-") + cast(id, String)` (Core concatenation, portable), `data_erased_at = now`, `updated_at = now`, and delete their sessions and login codes. Downgrade is a documented no-op ("the removed grants came from configuration that no longer exists"). Writes no cut-off (research D5) (depends on T023).
- [X] T027 Add a retirement test to `tests/integration/test_migrations.py`, modelled on `test_upgrade_keeps_the_active_administrators`: migrate to T023's revision, seed an admin-only user, an admin+teacher user, a teacher-only user, a student-only user, a teacher+student user and an already inactive user with no role, each with a session (and login codes for one); upgrade to head; assert `teacher`/`student` rows are gone; admins stay active with their emails and sessions dropped only for those who held teacher/student; people left with no role are inactive with `email == f"erased-{id}"`, `data_erased_at` set, no sessions, no login codes; no `invitation_cutoffs` rows; downgrade one step changes nothing (depends on T026).

### 2d. Shared services

- [X] T028 [P] Generalise `app/services/rate_limits.py` per contracts/services.md §rate_limits and research D12: add `@dataclass(frozen=True) class LimitCheck(bucket: str, key: str, limit: int)` (key is plain; hashed with `hash_rate_limit_key` before any query or insert) and `allow(session, secret_key, checks: Sequence[LimitCheck], now=None) -> bool` — if any bucket already has `limit` or more hits since `now − WINDOW`, return `False` and record nothing; otherwise record one hit per check, commit, return `True`. Rewrite `allow_code_request` as a thin wrapper (behaviour and its tests unchanged). Add constants `BUCKET_INVITE_INVITER = "invite_inviter"`, `BUCKET_INVITE_EMAIL = "invite_email"`, `BUCKET_DELETION_EMAIL = "deletion_email"`, `BUCKET_DELETION_CLIENT = "deletion_client"`, `INVITER_INVITE_LIMIT = 20`, `EMAIL_INVITE_LIMIT = 5`, `EMAIL_DELETION_LIMIT = 5`, `CLIENT_DELETION_LIMIT = 20`. Bucket names fit `rate_limit_hits.bucket` `String(32)`.
- [X] T029 [P] Add to `app/services/institutions.py` per contracts/services.md §institutions: `@dataclass(frozen=True) class SelectableInstitution(id: int, label: str, is_selectable: bool)` with `label = "Name (Region)"` and `is_selectable = institution.is_active and region.is_active`; `list_selectable_institutions(session)` — active institutions in active regions, sorted in Python by `(label.casefold(), id)` (FR-009); `describe_institutions(session, ids, lock=False) -> dict[int, SelectableInstitution]` — found ids only, current names, and with `lock=True` reads the institution and region rows `with_for_update(read=True)` (research D6). Change `count_institution_uses` to count `TeacherInstitution` rows for the institution and update its docstring (FR-012; milestone 9 adds students here) (depends on T022).
- [X] T030 [P] Extend `tests/integration/test_institution_service.py`: `list_selectable_institutions` omits a deactivated institution and an active institution in a deactivated region, labels "Name (Region)", sorts ignoring case; `describe_institutions` omits unknown ids and reports `is_selectable=False` for the two unavailable cases; a real `TeacherInstitution` row makes `count_institution_uses` 1 and `delete_institution` raises `InstitutionInUse`. Keep the existing monkeypatched-count test (depends on T029).
- [X] T031 [P] Add `invitation_message(to, inviter_display, inviter_email, role_label, detail_lines, link, expires_at) -> EmailMessage` and `deletion_message(to, link, expires_at) -> EmailMessage` to `app/services/email.py` per contracts/services.md §email. Invitation subject "You are invited to Student Competitions as a teacher" (built from `role_label`, never names); body: "<inviter_display> (<inviter_email>) invites you…", the role, each detail line (institutions with access levels and the "You will / will not be able to create competitions." line), "Nothing about you is stored unless you accept.", the link on its own line, "This invitation expires on <YYYY-MM-DD HH:MM> UTC.". Deletion subject "Delete your Student Competitions data"; body: what the link does (erases the names and the address, removes the roles granted by consent), that it works once, within one hour, until <UTC time>, the link, "If you did not ask for this, you can ignore this email." Plain text only, links as given.
- [X] T032 [P] Extend `tests/unit/test_email.py`: both messages are plain text (`EmailMessage.text`, no HTML), contain every required statement, the link verbatim and the UTC expiry; the invitation subject contains no first or last name; the deletion message contains the "ignore" sentence (depends on T031).
- [X] T033 [P] Add a `utc` Jinja filter in `app/core/templates.py` (research D19): `value|utc` → `"2026-10-22 14:05 UTC"`, `value|utc("date")` → `"2026-10-15"`; `None` → `""`. Add a unit test case to an existing unit module for the filter (or a new `tests/unit/test_templates.py`).
- [X] T034 Create `app/schemas/teachers.py` per contracts/services.md §schemas/teachers and research D11 (depends on T022): `@dataclass(frozen=True) class TeacherDetails(institutions: Mapping[int, AccessLevel], can_create_competitions: bool)`; `class InvalidChoice(ValueError)` with `.message`; `parse_institution_choices(institution: Sequence[str], access: Sequence[str], keep_level_for: Mapping[int, AccessLevel] = {}) -> dict[int, AccessLevel]`. `access` entries are `"<id>:read"` / `"<id>:write"`; entries for unpicked ids are ignored. Refuse: empty pick → "Pick at least one educational institution."; non-integer id → "This educational institution cannot be selected."; duplicate id → "Each educational institution can be picked only once."; missing, unknown or conflicting level for a picked id → "Choose Read or Write access for each educational institution.". For ids in `keep_level_for` the submitted level is ignored and the kept level is used. Selectability is not checked here.
- [X] T035 [P] Create `tests/unit/test_teacher_schemas.py`: none picked, `"abc"`, duplicate `"12","12"`, missing level, `"12:admin"`, conflicting `"12:read","12:write"` each refused with the exact message; `["12","15"]` with `["12:write","15:read","99:write"]` → `{12: WRITE, 15: READ}` (unpicked 99 ignored); a kept id with a submitted `write` keeps its stored `read`; a kept id with no access entry is accepted (depends on T034).
- [X] T036 Create `app/services/invitations.py` per contracts/services.md §invitations and research D2–D6 (depends on T002, T008, T028, T031):
  - `INVITATION_PURPOSE = "invitation"`, `INVITATION_TTL = timedelta(days=7)`;
  - `@dataclass(frozen=True) class DetailLine` (text) used by `describe`;
  - `class InvitableRole(Protocol)` with `role`, `details_to_payload`, `details_from_payload` (raises `ValueError`), `inviter_may_invite`, `details_acceptable(session, details, lock)`, `describe`, `grant` (no commit), `revoke` (no commit);
  - `invitable_role(role) -> InvitableRole` and `invitable_roles() -> dict[Role, InvitableRole]`, which import `app.services.teachers` lazily (no import cycle) and return `{Role.TEACHER: TEACHER_INVITATION}`; document `INVITABLE_ROLES` as this registry;
  - `@dataclass(frozen=True) class Invitation(role, email, first_name, last_name, details, inviter_id, issued_at)` with `expires_at` = `issued_at + INVITATION_TTL`;
  - outcomes `Invalid`, `Expired`, `Refused` (no payload), `AlreadyHeld(invitation)`, `Acceptable(invitation)`, `Accepted(user_id, email)`, `ConsentChanged(invitation)`;
  - `issue_invitation(session, settings, sender, base_url, inviter, role, email, first_name, last_name, details, now=None) -> None`: re-check `inviter_may_invite` and `details_acceptable(lock=False)` → raise `InvalidChoice("This educational institution cannot be selected.")`; seal `{"v": 1, "role", "email", "first", "last", "details": role_def.details_to_payload(details), "inviter"}` (data-model.md §9); send `invitation_message` with `f"{base_url}/invitations/{token}"`, the inviter's `display_name` and email, the role label, `describe` lines and `expires_at`. Writes nothing to the database. `EmailDeliveryError` propagates. Logs "Invitation sent: inviter_id=%s role=%s institutions=%s";
  - `_read(settings, token, now) -> Invalid | Expired | Invitation`: `unseal`, then re-validate the payload as untrusted (`v == 1`, known invitable role, `clean_email`, `clean_person_name` ×2, `details_from_payload`, integer `inviter`) — any failure → `Invalid`;
  - `evaluate_invitation(session, settings, token, now=None, lock=False)` with the D4 order: unseal/re-validate → inviter active admin (`inviter_may_invite` with the inviter `User`, missing inviter = `Refused`) → `details_acceptable(lock)` → cut-off (`get_cutoff`; refused unless `issued_at > cutoff_at`, strictly) → `AlreadyHeld` if a user with the email holds the role → `Acceptable`;
  - `accept_invitation(session, settings, token, consent_text_id, now=None)` per research D6: lock the user by email (`with_for_update`); evaluate with `lock=True`; if `consent_text_id != current_consent_text(role).id` → `ConsentChanged`; apply FR-028 (create active user / add role / reactivate inactive), set names and `updated_at`, `role_def.grant(...)`, insert `ConsentRecord(user_id, consent_text_id, accepted_at=now, inviter_id, invitation_issued_at)`; commit; on `IntegrityError` roll back and run once more (the second run's `AlreadyHeld` is the answer). Never touches sessions. Logs "Invitation accepted: user_id=%s role=%s %s" with `created|added|reactivated`.
- [X] T037 Create `app/services/consent.py` per contracts/services.md §consent and research D5, D7, D8 (depends on T004, T011, T021, T036):
  - `current_consent_text(session, role) -> ConsentText` (highest `version`);
  - `@dataclass(frozen=True) class ConsentRecordView(accepted_at, role, version, text, inviter_id)`; `list_consent_records(session, user_id)` newest first; `latest_consent_at(session, user_id, role)`;
  - `has_consent_data(user) -> bool` = `user.first_name is not None`;
  - `get_cutoff(session, secret_key, email, role)` and `set_cutoff(session, secret_key, email, role, now)` (read, then update only if `now` is later, or insert; no commit) keyed by `hash_invitation_cutoff_key`;
  - `@dataclass(frozen=True) class ErasureResult(roles_removed: tuple[Role, ...], email_kept: bool, deactivated: bool)`; `erase_personal_data(session, settings, user_id, now=None)`: lock the user; `revoke` every invitable role held; `set_cutoff` for **every** invitable role with the current email; clear `first_name`/`last_name`, set `data_erased_at = now` and `updated_at`; replace the email with `f"erased-{user.id}"` unless the user holds `admin`; deactivate if no role left; delete all sessions and login codes; commit. Consent records untouched. Logs "Personal data erased: user_id=%s roles_removed=%s email_kept=%s";
  - `@dataclass(frozen=True) class ErasurePlan(first_name, last_name, email, roles_to_remove, email_kept, will_deactivate)`; `describe_erasure(session, user) -> ErasurePlan`.
- [X] T038 Create `app/services/teachers.py` with the role definition and the shared write helpers per contracts/services.md §teachers and research D3, D9 (depends on T029, T034, T036, T037):
  - `class _TeacherInvitation` implementing `InvitableRole` and `TEACHER_INVITATION = _TeacherInvitation()`: `role = Role.TEACHER`; `details_to_payload` → `{"institutions": [[id, level], …] (sorted by id), "can_create_competitions": bool}`; `details_from_payload` validates types, levels and non-empty unique ids, else `ValueError`; `inviter_may_invite` → inviter active and holds `admin`; `details_acceptable` → every id found by `describe_institutions(..., lock=lock)` with `is_selectable`; `describe` → one `DetailLine` per institution "Name (Region) — Read/Write" (current names, sorted by label casefold) plus "Can create competitions: Yes/No"; `grant` → add the `UserRole`, the `TeacherProfile` and the `TeacherInstitution` rows (no commit); `revoke` → delete the links, the profile and the role row, only those present (no commit);
  - `grant_teacher(session, user, details, now)` = `TEACHER_INVITATION.grant` (used by tests and US3);
  - `class TeacherNotFound(LookupError)`; `class InstitutionNotSelectable(ValueError)` with `.message`;
  - `remove_teacher(session, settings, user_id, now=None) -> None`: lock the user; require a current teacher (holds `teacher` and has a profile row) else `TeacherNotFound`; `revoke`; `set_cutoff(email, teacher)`; deactivate if no role left; `end_all_sessions`; commit. Email, names and consent records stay. Logs "Teacher removed: user_id=%s deactivated=%s".
- [X] T039 Create `tests/integration/test_consent_service.py` (service level, both engines) (depends on T037, T038):
  - `set_cutoff` only raises (an earlier `now` leaves the stored time), stores the keyed hash and never the address (scan the row);
  - `erase_personal_data` on a teacher with no other role: teacher role, profile and links gone; names `NULL`; email `erased-<id>`; `data_erased_at` set; inactive; no sessions or login codes; consent records unchanged; cut-off set for every invitable role;
  - on an admin + teacher: admin role and email kept, active, names cleared, sessions gone, `email_kept=True`;
  - on a removed teacher who is still admin (names stored, no teacher role): names cleared, `roles_removed == ()`;
  - `describe_erasure` reports roles, `email_kept` and `will_deactivate` for both cases and writes nothing;
  - `remove_teacher` on a teacher-only user: deactivated, signed out, names and records kept, cut-off set; on an admin + teacher: stays active; unknown id and a cast teacher without profile → `TeacherNotFound`;
  - `current_consent_text(Role.TEACHER).version == 1`.
- [X] T040 Add test helpers to `tests/conftest.py` (depends on T036, T038): `make_institution(engine, name, region="Kyiv", active=True, region_active=True) -> int` through the milestone 7 services; `invite_and_accept(engine, settings, *, email, first="Olena", last="Kovalenko", institutions={id: AccessLevel.READ}, can_create=False, inviter_email=ADMIN_EMAIL, now=None) -> int` that calls `issue_invitation` with a local `MemoryEmailSender`, extracts the token from the message, and calls `accept_invitation` with the current consent text id, returning the user id; and `token_from(message) -> str` that extracts the `/invitations/<token>` or `/data-deletion/confirm/<token>` segment from an `EmailMessage`.

**Checkpoint**: `uv run pytest` is fully green on SQLite (and PostgreSQL when configured), with the
lists retired, the cast seeded directly, both migrations applied and the services tested.

---

## Phase 3: User Story 1 — An administrator invites a teacher, who accepts (Priority: P1) 🎯 MVP

**Goal**: an administrator sends an invitation from the Teachers tab; the invited person opens
the emailed link, sees exactly what will be stored, presses **I agree**, and lands on a prefilled
sign-in page.

**Independent Test**: as `admin_client`, post the invitation form, read the link from `outbox`,
`GET` it and assert no table holds the email or names, `POST` **I agree**, then assert the user,
role, both links, the setting and the consent record, follow the redirect to the prefilled
sign-in page and sign in with the emailed code.

### Tests for User Story 1

> Write these first and see them fail before implementing.

- [X] T041 [P] [US1] Create `tests/integration/test_teacher_invitation.py` covering US1 scenarios 1–9: the invite form has `email`, `first_name`, `last_name`, picker rows and an unchecked `can_create_competitions`; the picker offers only active institutions in active regions as "Name (Region)", each with Read preselected (seed a deactivated institution and an institution in a deactivated region); a valid post with Kyiv=Write, Lviv=Read and the setting → `303` to `/admin/teachers?sent=…`, the followed page shows "Invitation sent to olena@example.org", the `Location` header contains no `@` and no "olena"; one email in `outbox` with every FR-021 statement; after `GET /invitations/<token>` (twice) the `users` table has no such email and the page shows inviter, role, email, names, both institutions with levels, "Can create competitions: Yes", the expiry in UTC, the consent text, the hidden `consent_text_id`, **I agree**, the "If any detail is wrong…" note, and no `<input>` other than the hidden field and the button; `POST` → `303` to `/login?prefill=…`; the user is active with `teacher`, names, two `TeacherInstitution` rows with the right levels, `can_create_competitions=True`, and one `ConsentRecord` (text v1, inviter = admin id, `invitation_issued_at` = sealed `at`); the sign-in page has the email field prefilled and "Your account is ready. Send yourself a sign-in code to continue."; the anonymous client has no session cookie; signing in through `POST /login` + the emailed code works; an invalid or stale `prefill` is ignored; invalid invite forms (bad email, 101-character name, control character, no institution, duplicate id, bad level, deactivated id) → `400` with the errors and every entered value, and no email.

### Implementation for User Story 1

- [X] T042 [P] [US1] Create `app/templates/pages/admin/_institution_picker.html` (research D11): a table of rows, each with a checkbox `name="institution" value="<id>"` (checked when picked), the label "Name (Region)", and a `<select name="access">` with `<id>:read` (selected by default) and `<id>:write`; an optional set of extra "kept" rows (checked checkbox, level as text, "deactivated" mark, no select) for the edit page; pre-fills picked ids and levels from the submitted values on re-render. Accessible labels per row.
- [X] T043 [P] [US1] Create `app/templates/pages/admin/teacher_invite.html` extending the admin layout: heading "Invite teacher", fields `email`, `first_name`, `last_name` with per-field errors and kept values, the picker include, the `can_create_competitions` checkbox (unchecked by default, kept on re-render), a form-level error area (rate limit, send failure, picker error), and **Send invitation** posting to `/admin/teachers/invite`.
- [X] T044 [P] [US1] Create `app/templates/pages/admin/teachers.html` (minimal for US1): the "Invitation sent to <email>" banner when given, the **Invite teacher** link, "No teachers yet" when the list is empty, and a placeholder block for the table that US3 fills.
- [X] T045 [US1] Create `app/routers/admin_teachers.py` (all handlers `@allow_roles(Role.ADMIN)`, rendered through `render_admin` with the Teachers tab current) with: `INVITATION_SENT_PURPOSE = "invitation-sent"`, `NOTICE_TTL = timedelta(minutes=10)`; `GET /admin/teachers` (unseal `sent`; show the banner only when it unseals; empty list until US3); `GET /admin/teachers/invite` (picker from `list_selectable_institutions`); `POST /admin/teachers/invite` with `email`, `first_name`, `last_name`, `institution: list[str] = Form([])`, `access: list[str] = Form([])`, `can_create_competitions: str | None = Form(None)` — validation order email → names → picker (`parse_institution_choices`, then every id must be in `describe_institutions` and selectable, else "This educational institution cannot be selected."), collecting all errors → `400`; then `rate_limits.allow` with `LimitCheck(BUCKET_INVITE_INVITER, str(inviter.id), 20)` and `LimitCheck(BUCKET_INVITE_EMAIL, email, 5)` → `429` "Too many invitations. Please try again later." with values; then `issue_invitation` with `base_url = settings.public_base_url or str(request.base_url).rstrip("/")` — `InvalidChoice` → `400`, `EmailDeliveryError` → `503` "The invitation email could not be sent. Please try again." with values (the hit still counts); success → `303` to `/admin/teachers?sent=<seal(INVITATION_SENT_PURPOSE, {"email": email})>`. Remove the `/admin/teachers` placeholder handler from `app/routers/admin.py` and update its module docstring; include the new router in `app/main.py` (depends on T042–T044).
- [X] T046 [P] [US1] Create `app/templates/pages/invitation.html` (public layout, no admin tabs, nothing about the signed-in session) per contracts/http-routes.md §2: heading "Invitation to Student Competitions"; "<inviter display name> (<inviter email>) invites you to join as a teacher."; a read-only definition list (email, first name, last name, each institution "Name (Region)" — Read/Write by **current** names, Can create competitions Yes/No); "This invitation expires on <…|utc>."; the consent text split into paragraphs; an optional notice slot (used by US2's consent-changed case); `<form method="post">` with hidden `consent_text_id` and **I agree**; under it "If any detail is wrong, ask the person who invited you for a new invitation, or accept and ask them to correct it."
- [X] T047 [P] [US1] Create `app/templates/pages/invitation_status.html`: one template for the non-acceptance outcomes, given a heading, a message and an optional link — used here for "You are already a teacher." with a **Sign in** link to `/login`, and in US2 for expired and neutral messages.
- [X] T048 [US1] Create `app/routers/invitations.py` (public) with `GET /invitations/{token}` and `POST /invitations/{token}` (depends on T046, T047): `GET` calls `evaluate_invitation(lock=False)` — `Acceptable` → `200` `invitation.html` with `describe` lines, inviter (`display_name`, email), `current_consent_text`; `AlreadyHeld` → `200` "You are already a teacher." — never writes. `POST` reads only `consent_text_id: str = Form("")` (non-integer → treat as stale, i.e. not the current id), ignores every other field (FR-029), calls `accept_invitation`; `Accepted` → `303` to `/login?prefill=<seal("login-prefill", {"email": email})>`; `AlreadyHeld` → `303` to `/invitations/{token}`. Leave a clearly marked branch for `Invalid`/`Refused`/`Expired`/`ConsentChanged` that US2 completes (for now a neutral `400`). Add `("GET", "/invitations/{token}")` and `("POST", "/invitations/{token}")` to `PUBLIC_ROUTES` in `app/core/auth.py`; include the router in `app/main.py`.
- [X] T049 [US1] Change `GET /login` in `app/routers/auth.py` and `app/templates/pages/login.html` (contracts/http-routes.md §3): optional `prefill` query parameter; when it unseals with purpose `login-prefill` and max age 10 minutes, fill the email input and show "Your account is ready. Send yourself a sign-in code to continue."; otherwise ignore it. Keep the existing redirect for a signed-in visitor unchanged.
- [X] T050 [US1] Update `tests/integration/test_admin_area.py`: remove `/admin/teachers` from `PLACEHOLDERS`; add `test_the_teachers_tab_is_no_longer_a_placeholder` (shows "No teachers yet" and **Invite teacher**, not the placeholder note) and parametrise "every teachers page marks the Teachers tab" over `/admin/teachers` and `/admin/teachers/invite` (US3 adds more). Update `test_admin_opens_the_teachers_tab` accordingly.
- [X] T051 [US1] Update `tests/integration/test_routes.py`: `test_the_write_routes_are_exact` += `POST /admin/teachers/invite`, `POST /invitations/{token}`; `test_the_allowlist_is_exact` += `GET /invitations/{token}`, `POST /invitations/{token}`. Run the whole suite and `tests/integration/test_teacher_invitation.py` green.

**Checkpoint**: the invite → accept → sign in path works end to end. MVP demonstrable.

---

## Phase 4: User Story 2 — Acceptance is refused when the invitation is no longer valid (Priority: P1)

**Goal**: tampered, expired, outdated or otherwise invalid invitations are refused with the right
message and store nothing; a removal or withdrawal always beats an older invitation.

**Independent Test**: build links that are tampered, expired, from a removed inviter, for a
deleted/deactivated institution or deactivated region, and older than a removal or withdrawal;
each is refused and stores nothing; a newer invitation succeeds.

### Tests for User Story 2

- [X] T052 [P] [US2] Create `tests/integration/test_invitation_refusals.py` (US2 scenarios 1–5, 9; FR-033, FR-035): a token with one changed character → `GET` and `POST` `400` with "This invitation cannot be accepted. Ask the person who invited you to send a new one." and no user created; an invitation issued with `now = utc_now() − 8 days` (via `issue_invitation(now=…)`) → `410` "This invitation has expired; ask for a new one." on `GET` and `POST`; the inviter removed from `ADMIN_EMAILS` (reconcile with an empty list, or a second admin who is reconciled away) → `GET` and `POST` `400` with the same neutral message and status; an invited institution deleted, deactivated, or its region deactivated after issue → `400` neutral; an institution renamed after issue → the page shows the new name and `POST` succeeds; a `POST` with extra fields (`email=evil@example.org`, `first_name=X`, `institution=99`, `access=99:write`, `can_create_competitions=on`) stores exactly what the link holds; a stale `consent_text_id` (insert a v2 consent text in the test DB directly) → `409` acceptance page showing the v2 text and "The consent text has changed since you opened this page. Please read it again.", nothing stored, then a `POST` with the v2 id succeeds; the expired and neutral responses never reveal which check failed (identical body for tampered, refused-inviter and refused-institution).
- [X] T053 [P] [US2] Create `tests/integration/test_invitation_cutoff.py` (US2 scenarios 6–8; FR-027, FR-034, FR-048), using `invite_and_accept`, `issue_invitation` with explicit `now` values and `remove_teacher`/`erase_personal_data` with explicit `now`: an invitation issued before `remove_teacher` is refused for a now-deactivated teacher; for an admin + teacher who lost only the teacher role and stayed active; for a person who withdrew (`erase_personal_data`) — note the email changed, the cut-off still matches; for a person removed, re-invited (link B issued), and then deleting their data — link B is refused; an invitation issued strictly after the removal or withdrawal succeeds (and reactivates the inactive user with the invited names and details); an invitation issued at exactly the same microsecond as the removal is refused ("the removal wins").
- [X] T054 [P] [US2] Create `tests/integration/test_invitation_edge_cases.py` (spec Edge Cases): an invitation to an existing teacher is sent; `GET` shows "You are already a teacher."; `POST` → `303` back to the link, no new consent record; pressing **I agree** twice → one user, one role row, one consent record; two invitations for the same person → the first accepted wins, the second shows "already a teacher"; an inactive user removed earlier accepts a newer invitation → reactivated with the teacher role and the new names; the 21st invitation by one inviter within an hour → `429` with values and no email; the 6th invitation to one address within an hour → `429`; with the sender patched to raise `EmailDeliveryError` → `503` with values, nothing stored, and the attempt counted (the next five to that address include it); `"  Olena@Example.org "` invites `olena@example.org`; a signed-in teacher opening someone else's invitation sees the invited person's data and their own session is unchanged after accepting it.

### Implementation for User Story 2

- [X] T055 [US2] Complete the outcome mapping in `app/routers/invitations.py` per contracts/http-routes.md §2: `Expired` → `410` `invitation_status.html` "This invitation has expired; ask for a new one."; `Invalid` and `Refused` → `400` with the single neutral message (same template, same status, same body); `ConsentChanged` → `409` `invitation.html` re-rendered with the new current text, its id in the hidden field, and the notice "The consent text has changed since you opened this page. Please read it again." Define the messages as module constants shared with the tests.
- [X] T056 [US2] Review `evaluate_invitation` and `accept_invitation` in `app/services/invitations.py` against T052–T054 and fix any gap (for example the cut-off comparison must be strictly `issued_at > cutoff_at`, the re-validation must reject a payload whose `role` is not invitable, and the `IntegrityError` retry must return `AlreadyHeld`). Run the three US2 modules green.

**Checkpoint**: US1 and US2 together are the minimum safe invitation flow.

---

## Phase 5: User Story 3 — An administrator manages teachers (Priority: P1)

**Goal**: the Teachers tab lists current teachers; each has a page to edit names, links, levels
and the setting; **Remove** takes the teacher role away.

**Independent Test**: with teachers created through `invite_and_accept`, check the list order and
columns, edit one link's level and the setting while another link stays byte-for-byte the same,
see refusals for invalid edits, and remove a teacher.

### Tests for User Story 3

- [X] T057 [P] [US3] Create `tests/integration/test_admin_teachers.py` covering US3 scenarios 1–10 and the edge cases: empty tab → "No teachers yet" + **Invite teacher** (the cast's directly seeded teachers do not appear); three teachers ("kovalenko", "Antonenko", "bondar") listed by last name ignoring case, then first name; each row shows name (link to `/admin/teachers/<id>`), email, "Name (Region) — Read/Write", "(deactivated)" on an unavailable link, Yes/No and the consent date `YYYY-MM-DD`; on the teacher page the email is shown but is not an input; changing Kyiv Write→Read and unchecking the setting changes those, and the Lviv link's `access_level`, `created_at` and `updated_at` are unchanged; adding a third institution adds one row; a link whose institution was later deactivated is shown as deactivated with the level as text, is kept when other changes are saved (even if a different level is submitted for it), can be unchecked and removed, and is then not offered again; adding a deactivated institution, an institution in a deactivated region or an unknown id → `400` "This educational institution cannot be selected." and nothing changes; no institutions, `access=12:admin`, an empty or 101-character name → `400` with the errors and entered values, nothing changes; editing does not end the teacher's session (their `client_as` still opens `/`); the remove confirmation shows the FR-042 text; removing a teacher-only user → gone from the list, inactive, no sessions, names and consent records kept; removing an admin + teacher → stays active as admin, signed out everywhere; `GET`/`POST` for an unknown id, a non-teacher and a removed teacher → `404` "Teacher not found"; saving after the teacher was removed in another request → `404`; reloading after each `303` does not repeat the action.
- [X] T058 [P] [US3] Extend `tests/integration/test_admin_area.py`: every teacher page (`/admin/teachers/<id>`, `/admin/teachers/<id>/remove`, the not-found page) marks the Teachers tab. Extend `tests/integration/test_admin_institutions.py` (or `test_institution_service.py` if T030 already covers HTTP): deleting an institution linked to a teacher through the UI is refused as "in use" (FR-012, US3-8).

### Implementation for User Story 3

- [X] T059 [US3] Add to `app/services/teachers.py` per contracts/services.md §teachers (depends on T038): `@dataclass(frozen=True) class TeacherLink(institution_id, label, access_level, is_selectable)`; `@dataclass(frozen=True) class TeacherView(user_id, email, first_name, last_name, links, can_create_competitions, consented_at)` with links sorted by `label.casefold()`; `list_teachers(session)` — current teachers (role + profile row) sorted by `(last_name.casefold(), first_name.casefold(), id)` in Python, `consented_at = latest_consent_at(..., Role.TEACHER)`; `get_teacher(session, user_id)` → `TeacherNotFound`; `update_teacher(session, user_id, first_name, last_name, institutions, can_create_competitions, now=None)`: lock the user and re-check current teacher; compute added/removed/changed against the stored links; lock the added institutions `FOR SHARE` via `describe_institutions(lock=True)` and raise `InstitutionNotSelectable("This educational institution cannot be selected.")` if any is missing or unselectable (nothing changes); a kept unselectable link keeps its stored level; write only the differences, bumping `updated_at` only on changed rows and on the profile only when the setting changes, and on the user only when the names change; never touches sessions; commit; log "Teacher updated: user_id=%s added=%s removed=%s changed=%s".
- [X] T060 [P] [US3] Fill the table in `app/templates/pages/admin/teachers.html` per contracts/http-routes.md §1 "The list": columns name (link), email, institutions (one per line, "(deactivated)" mark), Can create competitions (Yes/No), date of consent (`|utc("date")`).
- [X] T061 [P] [US3] Create `app/templates/pages/admin/teacher_form.html`: the email as read-only text, `first_name`/`last_name` inputs with errors and kept values, the picker include with the teacher's links checked at their levels plus kept "deactivated" rows, the `can_create_competitions` checkbox, **Save** posting to `/admin/teachers/<id>`, and a **Remove teacher** link to `/admin/teachers/<id>/remove`.
- [X] T062 [P] [US3] Create `app/templates/pages/admin/teacher_remove.html` (the confirmation text from contracts/http-routes.md §1 "Remove", with the teacher's display name; **Remove** posts to `/admin/teachers/<id>/remove`; **Cancel** links back) and `app/templates/pages/admin/teacher_not_found.html` ("Teacher not found" with a link to the Teachers tab).
- [X] T063 [US3] Add the routes to `app/routers/admin_teachers.py` (all `@allow_roles(Role.ADMIN)`) (depends on T059–T062): `GET /admin/teachers` renders `list_teachers`; `GET /admin/teachers/{user_id:int}` (picker = selectable institutions ∪ kept unselectable links); `POST /admin/teachers/{user_id:int}` — clean names, `parse_institution_choices(..., keep_level_for={id: level for unselectable stored links})`, then `update_teacher`; errors → `400` re-render with entered values; `InstitutionNotSelectable` → `400`; `TeacherNotFound` → `404`; success → `303` to `/admin/teachers`; `GET /admin/teachers/{user_id:int}/remove` → confirmation or `404`; `POST /admin/teachers/{user_id:int}/remove` → `remove_teacher` → `303` to `/admin/teachers`, or `404`.
- [X] T064 [US3] Update `tests/integration/test_routes.py`: `test_the_write_routes_are_exact` += `POST /admin/teachers/{user_id:int}` and `POST /admin/teachers/{user_id:int}/remove`; confirm the declared-page sweep treats `/admin/teachers/1` as `404` for the administrator (≠ 403) and `403` for others. Run the suite green.

**Checkpoint**: all P1 stories work; teachers can be invited, accepted, managed and removed.

---

## Phase 6: User Story 4 — A person sees their profile and withdraws consent (Priority: P2)

**Goal**: every signed-in person has a read-only profile; anyone with consent data can withdraw
it, which erases their data and signs them out everywhere.

**Independent Test**: open `/profile` as each kind of person; as a teacher withdraw and check the
erasure, the sign-out and that sign-in no longer sends a code; as an admin + teacher withdraw and
check the admin role and email stay.

### Tests for User Story 4

- [X] T065 [P] [US4] Create `tests/integration/test_profile.py` covering US4 scenarios 1–8: a teacher's profile shows email, names, "Teacher", both institutions "Name (Region) — Read/Write" (deactivated marked), "Can create competitions: Yes" and the consent record (UTC time, role, version, full text); a cast admin without consent data sees only the email and "Administrator", no names, no records, no **Withdraw consent**; a cast student and a cast teacher (no consent data) can open it; the page has no form other than the withdraw link and says "Corrections to teacher data are made by an administrator."; `GET /profile/withdraw` lists what will be erased and the roles, and changes nothing; with no consent data `GET`/`POST /profile/withdraw` → `409` "There is no data stored on your consent to withdraw."; teacher-only `POST` → `303` to `/data-erased`, the cookie is cleared, all sessions of the user are gone (a second `client_as` session too), names `NULL`, email `erased-<id>`, records kept, inactive; then `POST /login` with the old address sends no email; admin + teacher (seed via `invite_and_accept` for a cast admin address) withdraws → keeps admin and email, loses teacher and names, gone from the Teachers tab, signed out; a removed teacher who is still admin sees **Withdraw consent**; reloading `/data-erased` repeats nothing.
- [X] T066 [P] [US4] Extend `tests/integration/test_teacher_invitation.py` with US1 scenario 10: after accepting and signing in, the teacher's `/profile` shows email, names, Teacher, both institutions with levels, Can create competitions and the consent record with the accepted text. Add a header test (here or in `test_home.py`): the signed-in email in the header links to `/profile` on every page.

### Implementation for User Story 4

- [X] T067 [P] [US4] Create `app/templates/pages/profile.html` per contracts/http-routes.md §4: email; first and last name when stored; roles in the fixed order with labels; for a current teacher the institutions (deactivated marked) and Can create competitions; consent records newest first (accepted `|utc`, role label, version, full text in paragraphs); the note "Corrections to teacher data are made by an administrator."; **Withdraw consent** link to `/profile/withdraw` only when `has_consent_data`.
- [X] T068 [P] [US4] Create `app/templates/pages/profile_withdraw.html` (confirmation per contracts/http-routes.md §4 "The confirmation": what will be erased, roles removed, "Your administrator role and email stay: they come from the deployment configuration." when `email_kept`, "You will be signed out everywhere.", "You will no longer be able to sign in." when `will_deactivate`; **Withdraw consent** POST and **Cancel** link to `/profile`; also renders the `409` "There is no data stored on your consent to withdraw." variant) and `app/templates/pages/data_erased.html` ("Your data has been erased.", consent records are kept as proof, any session was ended; a link to the home/sign-in page).
- [X] T069 [US4] Create `app/routers/profile.py` (every handler `@allow_roles(*ALL_ROLES)`, acting only on `request.state.user`) (depends on T067, T068): `GET /profile` (roles, `get_teacher` when a current teacher, `list_consent_records`); `GET /profile/withdraw` (`describe_erasure`, or `409`); `POST /profile/withdraw` → `erase_personal_data` → `303` to `/data-erased` with the session cookie deleted, or `409`. Create `app/routers/data_deletion.py` with only `GET /data-erased` (public, renders `data_erased.html`) — US5 adds the rest — and add `("GET", "/data-erased")` to `PUBLIC_ROUTES`. Include both routers in `app/main.py`.
- [X] T070 [US4] Change `app/templates/layouts/base.html`: the signed-in email in the header becomes a link to `/profile` on every page.
- [X] T071 [US4] Update `tests/integration/test_routes.py`: `test_the_write_routes_are_exact` += `POST /profile/withdraw`; `test_the_allowlist_is_exact` += `GET /data-erased`; the declared-page sweep admits `/profile` for all three roles. Run the suite green.

**Checkpoint**: people can see and withdraw their consent.

---

## Phase 7: User Story 5 — A person deletes their data without signing in (Priority: P2)

**Goal**: from the sign-in page, anyone can request a one-hour, one-use deletion link by email
and erase their data without signing in.

**Independent Test**: request deletion for a known, an unknown and an erased address — same
answer, only the known one gets an email; open the link (nothing changes), press the button
(erasure), and check used and expired links are refused.

### Tests for User Story 5

- [X] T072 [P] [US5] Create `tests/integration/test_data_deletion.py` covering US5 scenarios 1–7 and the edge cases: the sign-in page shows a **Delete my data** link to `/data-deletion` for an anonymous visitor; `POST /data-deletion` with a known consented address, an unknown address, an erased address and a cast admin without consent data all → `303` to `/data-deletion/requested` with identical bodies ("If this email is registered, we have sent you a link."), and only the known address gets an email (subject, statements, link, expiry); a malformed address → `400` "Enter a valid email address."; the 6th request for one address within an hour still → `303` and sends no email; `GET /data-deletion/confirm/<token>` changes nothing and shows the email, names and roles to remove, plus "Your administrator role and email stay." for an admin + teacher; `POST` erases as withdrawal does → `303` to `/data-erased`; opening or posting the link again → `410` "This link has expired; request a new one." with a link to `/data-deletion`; a link issued with `now − 61 minutes` → `410`; a tampered link → `400` "This link cannot be used. Request a new one."; two links requested, one used → the other is `410`; a removed teacher (inactive) can delete their data; a signed-in browser whose own user is erased gets its cookie cleared, while a signed-in browser of another user posting someone's link keeps its session and the link acts only on the person in it (FR-055); a link issued before erasure stays used even after the person is re-invited and accepts within the hour.
- [X] T073 [P] [US5] Update `tests/integration/test_login_flow.py`: teacher and student sign-in cases use the directly seeded cast (they still sign in); add the **Delete my data** link case and the prefill case if not already covered by T041.

### Implementation for User Story 5

- [X] T074 [US5] Create `app/services/data_deletion.py` per contracts/services.md §data_deletion and research D10 (depends on T037): `DELETION_PURPOSE = "data-deletion"`, `DELETION_TTL = timedelta(hours=1)`; outcomes `LinkInvalid`, `LinkExpired`; `deliver_deletion_link(engine, sender, settings, base_url, email) -> None` — background task: user by email (active or not) with `has_consent_data` → seal `{"user": id}` → `deletion_message(email, f"{base_url}/data-deletion/confirm/{token}", expires_at)`; otherwise nothing; every exception caught and logged by type only (as `deliver_login_code`); `read_deletion_link(session, settings, token, now=None, lock=False) -> LinkInvalid | LinkExpired | User` — unseal (`SealInvalid` → `LinkInvalid`, `SealExpired` → `LinkExpired`), then usable only while the user exists, `has_consent_data(user)` and `data_erased_at is None or data_erased_at < at`, else `LinkExpired`; `confirm_deletion(session, settings, token, now=None) -> LinkInvalid | LinkExpired | ErasureResult` — re-read with the user locked, then `erase_personal_data`. Logs ids only.
- [X] T075 [P] [US5] Create `app/templates/pages/data_deletion_request.html` (one `email` field, **Send link**, explanation that the link erases data stored on consent, error slot), `data_deletion_requested.html` ("If this email is registered, we have sent you a link."), `data_deletion_confirm.html` (email and names shown, roles to remove, "Your administrator role and email stay." when the user holds admin, **Delete my data** POST) and `link_status.html` (expired with a link to `/data-deletion`, or neutral) in `app/templates/pages/`.
- [X] T076 [US5] Add the public routes to `app/routers/data_deletion.py` per contracts/http-routes.md §5 (depends on T074, T075): `GET /data-deletion`; `POST /data-deletion` — `clean_email` or `400`; `rate_limits.allow` with `LimitCheck(BUCKET_DELETION_EMAIL, email, 5)` and `LimitCheck(BUCKET_DELETION_CLIENT, client_address(request, settings.trust_forwarded…), 20)` (use the same client-address call as `POST /login`); only when allowed, `BackgroundTasks.add_task(deliver_deletion_link, engine, sender, settings, base_url, email)` with `base_url = settings.public_base_url or request base`; always `303` to `/data-deletion/requested`; `GET /data-deletion/requested`; `GET /data-deletion/confirm/{token}` → `200` / `410` / `400`, never writes; `POST /data-deletion/confirm/{token}` → `303` to `/data-erased`, clearing the cookie only when the browser's session belongs to the erased user, else `410` / `400`. Add the six entries (`GET`/`POST /data-deletion`, `GET /data-deletion/requested`, `GET`/`POST /data-deletion/confirm/{token}`) to `PUBLIC_ROUTES`.
- [X] T077 [US5] Add the **Delete my data** link to `/data-deletion` in `app/templates/pages/login.html`, shown to everyone (FR-049).
- [X] T078 [US5] Update `tests/integration/test_routes.py`: `test_the_write_routes_are_exact` += `POST /data-deletion`, `POST /data-deletion/confirm/{token}`; `test_the_allowlist_is_exact` += the six data-deletion entries. Run the suite green.

**Checkpoint**: the consent promise is complete — see, withdraw, delete without signing in.

---

## Phase 8: User Story 7 — The teacher and student role lists are retired (Priority: P2)

**Goal**: confirm the retirement and the admin-only reconcile (built in Phase 2) cover every
scenario, with real consent teachers.

**Independent Test**: start the application with users holding roles from the old lists and
with consent teachers; check the migration result and that the administrator list never touches
the teacher role.

- [X] T079 [US7] Extend `tests/integration/test_user_reconcile.py` with real consent teachers (`invite_and_accept`): US7-2 a teacher not on the administrator list keeps the role and `is_active` across a reconcile; US7-3 an admin + consent teacher removed from `ADMIN_EMAILS` loses admin, stays active as a teacher, still appears on the Teachers tab, and is signed out everywhere; a reconcile never creates a `student` row.
- [X] T080 [US7] Extend `tests/integration/test_startup.py` (US7-4): a start with `TEACHER_EMAILS` and `STUDENT_EMAILS` set grants nothing; after start no user holds `student` except those seeded directly by the test helper (assert on a client started without `seed_roles_directly`, or query before seeding); review T027 against US7-1 and add any missing assertion (everyone affected signed out).

---

## Phase 9: User Story 6 — An administrator who also teaches invites themselves (Priority: P3)

**Goal**: self-invitation goes through the same steps as anyone else, with no shortcut.

**Independent Test**: as an administrator, invite your own address, accept in the same browser,
check both roles, the names and the consent record's inviter; withdraw and check the result.

- [X] T081 [US6] Create `tests/integration/test_self_invitation.py` (US6 scenarios 1–3): `admin_client` invites `ADMIN_EMAIL`; the same client opens and accepts the link → the user holds `admin` and `teacher`, carries the invited names, the consent record's `inviter_id == user_id`; the current session still works (no sign-out, `GET /login` redirects as for a signed-in visitor) and the role switch now offers Teacher; the user appears on the Teachers tab; after withdrawal they keep admin and email, lose teacher and names, disappear from the Teachers tab, and are signed out. If any assertion fails, fix the service rather than adding a special case for administrators.

---

## Phase 10: User Story 8 — Only the right people reach each page (Priority: P3)

**Goal**: every new page and action follows the milestone 5 access rules.

**Independent Test**: for each role and an anonymous visitor, request every new page and send
every new form, and check the outcome and that nothing changed.

- [X] T082 [P] [US8] Extend `tests/integration/test_access_control.py`: `ADMIN_PAGES` += `/admin/teachers`, `/admin/teachers/invite`, `/admin/teachers/<id>`, `/admin/teachers/<id>/remove`; `ADMIN_ACTIONS` += the three teacher `POST`s with valid bodies; for teacher, student and an administrator using another role → `403` "Access denied", and users, roles, links, profiles, consent records and `outbox` length compared before and after are unchanged; anonymous `GET` → `303 /login?next=…`, anonymous `POST` → `303 /login`; `/profile` and `/profile/withdraw` (`GET`) open to every role and show only the signed-in user's data; anonymous → sign in; a signed-in person with no current role is sent to `/role` for profile and teacher pages but served the public link pages; invitation and deletion pages opened by an admin, a teacher and an anonymous visitor act only on the person in the link (US8-4).
- [X] T083 [P] [US8] Extend `tests/integration/test_cross_site.py`: a cross-site `POST /admin/teachers/invite`, `POST /invitations/<token>`, `POST /profile/withdraw` and `POST /data-deletion/confirm/<token>` are refused (`403`), no email is sent, and nothing changes.
- [X] T084 [US8] Final check of `tests/integration/test_routes.py`: the write set grew by exactly the seven routes of contracts/http-routes.md and the allowlist by exactly its eight entries; `test_every_route_is_public_role_choice_or_declared` and `test_every_declared_page_admits_exactly_its_roles` are green with the new routes.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: privacy guarantees across all flows, headers, documentation and the final checks.

- [X] T085 Install the redactor in the `lifespan` of `app/main.py`: add one `AccessLogRedactor` to `logging.getLogger("uvicorn.access")` only if none is installed yet (idempotent across test restarts); update the start-up order docstring (contracts/configuration.md). Add a test in `tests/integration/test_startup.py` that after start the `uvicorn.access` logger has exactly one `AccessLogRedactor`, also after a second start.
- [X] T086 Add `Referrer-Policy: no-referrer` and `Cache-Control: no-store` to every response (every status) of `/invitations/{token}` and `/data-deletion/confirm/{token}` (a small shared helper used by both routers in `app/routers/invitations.py` and `app/routers/data_deletion.py`) (FR-061). Add assertions for `200`, `400`, `409`, `410` and the `303` responses to `tests/integration/test_invitation_refusals.py` and `tests/integration/test_data_deletion.py`.
- [X] T087 Create `tests/integration/test_consent_privacy.py` (SC-002, SC-007): (1) after sending an invitation and opening its link (twice), scan every column of every table (`inspect(engine).get_table_names()` → `SELECT *`) and assert no value contains the invited email, its local part, the first name or the last name; (2) run every flow of this milestone — invite (success, invalid, rate-limited, send failure), open, accept, already-a-teacher, refusals, edit, remove, profile, withdraw, deletion request (known/unknown), deletion confirm — with `caplog.set_level(logging.DEBUG)` on the root logger, and assert the captured text contains none of the invited addresses, names, issued tokens or sealed `sent`/`prefill` values; (3) after withdrawal and after data deletion, scan every table again and assert no value contains the names, and the email remains only for an admin (SC-005).
- [X] T088 [P] Update `README.md`: roles and configuration (`ADMIN_EMAILS` only; `TEACHER_EMAILS`/`STUDENT_EMAILS` retired; teachers come from invitations), `PUBLIC_BASE_URL` (required on Render, optional locally), the effects of rotating `SECRET_KEY` (outstanding links invalid, hash-based limits and cut-offs reset), local sign-in as a teacher (invite yourself through the console backend), and the project layout (new modules and templates).
- [X] T089 [P] Review every new module for log lines and confirm they carry ids, roles and counts only (FR-004): `app/services/invitations.py`, `teachers.py`, `consent.py`, `data_deletion.py`, and the four routers. Confirm no handler echoes a token or an address into an error message or a log.
- [X] T090 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` (and with `TEST_POSTGRES_URL` set when available); fix every finding.
- [X] T091 Walk through [quickstart.md](./quickstart.md) §2 manually (local start with two administrators, steps 1–10) and fix anything that does not match.
- [X] T092 On delivery, move milestone 8 to "Delivered" in `docs/requirements/milestones.md`, following how milestones 1–7 were recorded.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002–T009 are pure and mostly parallel.
- **Foundational (Phase 2)**: depends on Phase 1. 2a (T010–T018) must finish first, because the
  test cast changes for every existing test. 2b (T019–T025) and 2c (T026–T027) follow. 2d
  (T028–T040) needs the models (T022). **Blocks every user story.**
- **US1 (Phase 3)**: after Phase 2.
- **US2 (Phase 4)**: after US1 (it completes the invitations router created in T048 and uses the
  invite route to issue links).
- **US3 (Phase 5)**: after Phase 2; touches `admin_teachers.py` and `teachers.html` created in US1,
  so run after US1.
- **US4 (Phase 6)**: after Phase 2; T066 extends US1's test module.
- **US5 (Phase 7)**: after US4 (it extends `app/routers/data_deletion.py`, created in T069 for
  `/data-erased`).
- **US7 (Phase 8)**: after Phase 2 and US3 (the Teachers tab assertion).
- **US6 (Phase 9)**: after US1 and US4.
- **US8 (Phase 10)**: after US1, US3, US4 and US5 (every route exists).
- **Polish (Phase 11)**: after all stories.

### Story completion order

US1 → US2 → US3 → US4 → US5 → US7 → US6 → US8, which is priority order (P1, P1, P1, P2, P2, P2,
P3, P3).

### Within each story

- Tests first, failing before the implementation.
- Templates before the router that renders them.
- Services before routes.
- Each story ends by updating the pinned route sets in `test_routes.py` and running the full suite.

### Parallel Opportunities

- Phase 1: T002/T003, T004, T005/T006 and T007→T008/T009 are independent groups.
- Phase 2a: T014, T015, T016, T017 in parallel after T013.
- Phase 2b: T019, T020, T021 in parallel; T025 in parallel with T024.
- Phase 2d: T028, T029, T031, T033 in parallel; their tests T030, T032 in parallel.
- US1: T041, T042, T043, T044, T046, T047 in parallel.
- US2: T052, T053, T054 in parallel.
- US3: T057, T058, T060, T061, T062 in parallel.
- US4: T065, T066, T067, T068 in parallel.
- US5: T072, T073, T075 in parallel.
- US8: T082, T083 in parallel.
- Polish: T088, T089 in parallel.

---

## Parallel Example: User Story 1

```bash
# Tests and templates for User Story 1 together:
Task: "T041 Create tests/integration/test_teacher_invitation.py"
Task: "T042 Create app/templates/pages/admin/_institution_picker.html"
Task: "T043 Create app/templates/pages/admin/teacher_invite.html"
Task: "T044 Create app/templates/pages/admin/teachers.html"
Task: "T046 Create app/templates/pages/invitation.html"
Task: "T047 Create app/templates/pages/invitation_status.html"

# Then the routers, in order:
Task: "T045 Create app/routers/admin_teachers.py (invite)"
Task: "T048 Create app/routers/invitations.py"
Task: "T049 Sign-in prefill in app/routers/auth.py"
```

## Parallel Example: Phase 2 models

```bash
Task: "T019 Add first_name, last_name, data_erased_at to app/models/user.py"
Task: "T020 Create app/models/teacher.py"
Task: "T021 Create app/models/consent.py"
# Then T022 (exports) → T023 (migration) → T024 / T025
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1: Setup.
2. Phase 2: Foundational — retire the lists and get the existing suite green before adding
   tables; then the migrations and services.
3. Phase 3: US1 — invite, accept, prefilled sign-in.
4. Phase 4: US2 — the refusals and the cut-off. Without them US1 is not safe to deploy.
5. **STOP and VALIDATE**: quickstart §2 steps 1–4 and 7.

### Incremental Delivery

1. Setup + Foundational → the lists are retired, nothing visible changes yet.
2. US1 + US2 → teachers can be invited safely (MVP).
3. US3 → teachers can be managed and removed.
4. US4 + US5 → people see, withdraw and delete their data.
5. US7, US6, US8 → verification stories (mostly tests).
6. Polish → privacy scans, headers, README, manual walk-through.

---

## Notes

- [P] tasks = different files, no dependency on an unfinished task.
- The `[Story]` label maps a task to its user story for traceability.
- Keep services free of route authorization; routers declare roles or use `PUBLIC_ROUTES`.
- Never put an email, a name or a token in a log line, an exception message or a plain URL.
- Commit after each task or logical group; stop at any checkpoint to validate the story alone.
