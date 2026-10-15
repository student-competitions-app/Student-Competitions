# Research: User Management with Consent — Teachers (Milestone 8)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-15

The Technical Context has no open questions. The stack, layout and access model are fixed by the
constitution and milestones 1–7. Milestones 4–7 already settled most patterns: keyed hashes,
sliding-window rate limits in the database, background email delivery, Post/Redirect/Get,
row locks with `with_for_update`, the in-use hook and the route-table sweeps. This file records
only what milestone 8 adds or changes. Each decision is stated as Decision / Rationale /
Alternatives considered.

---

## D1. Sealed links: AES-256-GCM from `cryptography` (one new dependency)

**Decision**: add `cryptography` to `pyproject.toml`. A new pure module `app/core/sealing.py`
offers two functions:

- `seal(secret_key, purpose, payload: dict) -> str`
- `unseal(secret_key, purpose, token, max_age, now) -> dict`, which raises `SealInvalid` or
  `SealExpired`.

The construction:

- **Key**: HKDF-SHA256 over `SECRET_KEY`, 32 bytes, `info = b"student-competitions/sealed/v1"`.
  It is derived once per key and cached.
- **Cipher**: AES-256-GCM with a random 96-bit nonce per token.
- **Associated data**: the version byte plus the purpose label (`invitation`, `data-deletion`,
  `invitation-sent`, `login-prefill`). A token sealed for one purpose cannot be opened as another.
- **Plaintext**: compact JSON. It always holds `"at"`, the issue time in integer microseconds
  since the epoch (UTC).
- **Token**: `base64url(0x01 ‖ nonce ‖ ciphertext‖tag)`, without padding. It is URL-safe and
  needs no escaping in a path segment.
- **Validation order** in `unseal`:
  1. base64 decodes;
  2. the version byte is known;
  3. the tag verifies;
  4. the JSON parses to an object with an integer `"at"`.

  Any failure raises `SealInvalid`. Only after that is the age checked
  (`now − at ≥ max_age` raises `SealExpired`). Expiry is therefore reported only for a token this
  server really issued.

**Rationale**: FR-020 requires the link to be *encrypted* (its contents cannot be read from the
address) and *tamper-proof* (any change makes it invalid). That is authenticated encryption. The
standard library has HMAC but no cipher. `cryptography` is the de-facto standard Python crypto
library, ships binary wheels for the Docker image's platform, and is maintained by the PyCA. AES-GCM
binds the purpose through the associated data, and adds only 28 bytes (nonce and tag), so a
worst-case invitation (two 100-character Cyrillic names, a 254-character address, tens of
institutions) stays well under 2,000 URL characters. Random 96-bit nonces are safe far beyond this
application's volume. The constitution allows a new runtime dependency when `plan.md` justifies it
(Principle II). See Complexity Tracking.

**Alternatives considered**:

- *Fernet* (also from `cryptography`): rejected. It uses AES-128-CBC with HMAC and a fixed 57+
  byte overhead, and has no associated data, so purposes would need separate keys. GCM is shorter
  and binds the purpose directly. Both would be acceptable.
- *`itsdangerous` / HMAC-signed JSON*: rejected. It is tamper-proof but readable: the email and
  names would be base64 in the URL, which breaks FR-020.
- *A home-made stream cipher from HMAC-SHA256 in counter mode, plus a MAC*: rejected. It is
  probably sound, but it is home-made cryptography in a codebase whose reviewers are not
  cryptographers.
- *Store pending invitations server-side and email a random id*: forbidden by FR-002.

---

## D2. The invitation payload and its validity

**Decision**: the sealed invitation (`purpose = "invitation"`, `max_age = 7 days`) holds:

```json
{"v": 1, "role": "teacher", "email": "olena@example.org", "first": "Olena", "last": "Kovalenko",
 "details": {"institutions": [[12, "write"], [15, "read"]], "can_create_competitions": true},
 "inviter": 3, "at": 1760527200123456}
```

- `email` is normalised, and the names are cleaned (D11) before sealing.
- `details` belongs to the role: the role definition (D3) builds it and reads it back.
- `inviter` is the inviter's user id. The page and the email show the inviter's *current* name and
  address (spec Assumptions).
- The expiry is `at + 7 days`. It is not a separate field, so it cannot disagree with the issue
  time.
- After `unseal`, the payload is validated again as if it were untrusted: known role, valid
  email, valid names, and role details that parse. A payload that fails is `SealInvalid`. In
  practice this only guards against this server's own older payload versions.

**Rationale**: FR-020 requires that the link carry the whole invitation. Issue time in
microseconds makes "issued strictly after the latest removal" (D5) precise. A removal and an
invitation in the same second are still ordered correctly. Times come from `utc_now()`, so tests
control them through the services' `now` parameter.

**Alternatives considered**:

- *An explicit `expires` field*: redundant with `at`.
- *Institution names in the payload*: rejected. The acceptance page must show *current* names
  (US2-5), and the ids are what get stored.

---

## D3. Built for reuse: an `InvitableRole` definition per role, and one generic flow

**Decision**: `app/services/invitations.py` holds the generic flow:

- seal and email an invitation;
- read and evaluate a token;
- accept it;
- write the consent record.

It knows roles only through a small protocol, `InvitableRole`, and a registry `INVITABLE_ROLES:
dict[Role, InvitableRole]`. This milestone registers one implementation, `TEACHER_INVITATION`, in
`app/services/teachers.py`. The protocol, which is FR-005's list:

| Member | Teacher implementation |
|---|---|
| `role` | `Role.TEACHER` |
| `details_to_payload(details)` / `details_from_payload(raw)` | links as `[[id, level], …]`, the setting as a bool |
| `inviter_may_invite(session, inviter, details)` | the inviter is active and holds `Role.ADMIN` (any institution) |
| `details_acceptable(session, details, lock)` | every institution exists, is active, and is in an active region; rows locked `FOR SHARE` when `lock` |
| `describe(session, details)` | lines for the email and the page: "Name (Region) — Write", "Can create competitions: yes" |
| `grant(session, user, details, now)` | add the role row, the `teacher_profiles` row and the links |
| `revoke(session, user_id)` | delete the links, the profile and the role row |

The invitation form and its validation stay in the teacher router and schema (D11), because the
form differs per role.

**Rationale**: FR-005 requires the flow to be identical for every invitable role, and milestone 9
adds students as "one more invitable role without changing the flow". With the protocol,
milestone 9 adds `STUDENT_INVITATION` and its form, and nothing in invitations, consent, profile
or withdrawal changes. Withdrawal (D8) iterates the registry to remove "every role granted by
consent". This is the one abstraction with a single implementation. It is justified by FR-005
and the next milestone (Complexity Tracking).

**Alternatives considered**:

- *Write the teacher flow directly and generalise in milestone 9*: rejected. FR-005 is a
  requirement of this milestone, and milestone 9's own test says "the milestone 8 tests pass
  unchanged", so the flow must not need to change later.
- *An abstract base class hierarchy*: rejected. A `Protocol` and a dict are smaller and enough.

---

## D4. Where the acceptance checks run, and the order

**Decision**: one function, `evaluate_invitation(session, settings, token, now, lock=False)`,
returns one of these outcomes:

- `Invalid`
- `Expired`
- `Refused`
- `AlreadyHeld(invitation)`
- `Acceptable(invitation)`

It is used by both `GET` (read-only, `lock=False`) and `POST` (`lock=True`, inside the acceptance
transaction). The checks run in this order, and the first failure wins:

1. `unseal`. Tampered or malformed → `Invalid`. Older than 7 days → `Expired`.
2. Payload re-validation (D2) → `Invalid`.
3. The inviter is active and holds the administrator role (`inviter_may_invite`) → otherwise
   `Refused`.
4. Every invited institution is still selectable (`details_acceptable`) → otherwise `Refused`.
5. The invitation cut-off (D5): `at` must be strictly after the stored cut-off for
   `(hash(email), role)` → otherwise `Refused`.
6. A user with this email already holds the role → `AlreadyHeld`.
7. Otherwise → `Acceptable`.

Pages:

- `Invalid` and `Refused` show the same neutral message with the same status (`400`), so the
  response does not reveal which check failed (FR-033).
- `Expired` shows "This invitation has expired; ask for a new one." (`410`).
- `AlreadyHeld` shows "You are already a teacher." with a sign-in link.

**Rationale**:

- Running the same checks on `GET` means a person is never shown an **I agree** button that will
  certainly fail. The spec's refusals are stated "when I agree is pressed", and they still hold
  there because `POST` re-evaluates under locks.
- Steps 3–5 come before 6, as the milestone text orders them ("refused if … Otherwise … a user
  who already holds the role").
- One status for all neutral failures avoids a status-code oracle.

**Alternatives considered**:

- *Check only on `POST`*: rejected. It shows a page that cannot succeed.
- *Different statuses for tampered (400) and refused (409)*: rejected. The status would reveal
  which check failed.

---

## D5. The invitation cut-off: a keyed hash, a role and a time

**Decision**: a table `invitation_cutoffs(email_hash, role, cutoff_at)` with primary key
`(email_hash, role)`.

- `email_hash = HMAC-SHA256(SECRET_KEY, "invitation-cutoff\0" + email)`, added to
  `app/core/security.py` beside `hash_rate_limit_key`, with its own purpose label.
- `set_cutoff(session, secret_key, email, role, now)` raises the stored time to `now`. It reads
  the row, then updates or inserts it, inside the caller's transaction. The callers hold the
  user's row lock, so two writers for one address are already serialised. A lost insert race
  still ends in `IntegrityError`, and the caller retries once.
- It is written by:
  - removing a teacher (role `teacher`);
  - withdrawal and data deletion (D8), for **every** invitable role, held or not.
- Acceptance is refused unless `invitation.at > cutoff_at` (strictly, so "at the same instant,
  the removal wins").

**Rationale**:

- FR-027 and FR-034 must hold even after the email has been replaced. The user row can then no
  longer be found by address, so the cut-off cannot live on the user.
- A keyed hash is the one exception FR-003 allows.
- Writing the cut-off for every invitable role on erasure covers US2-7: a person removed earlier,
  re-invited, and then deleting their data cannot have the in-between invitation accepted
  afterwards.
- The role-list retirement (D16) writes no cut-off. No invitation can predate the migration,
  because invitations are created only by this milestone's code, which starts after the
  migration.

**Alternatives considered**:

- *A `removed_at` column on `user_roles` or `users`*: rejected. It is lost when the email is
  replaced, and the role row is deleted on removal.
- *Plain SHA-256 of the email*: rejected. Unkeyed, it can be reversed by hashing candidate
  addresses (FR-003 says "keyed").

**Secret rotation**: rotating `SECRET_KEY` changes every hash, so old cut-offs stop matching.
Rotation also invalidates every outstanding invitation (D1), so no old invitation can use the
reset. This is acceptable and documented (spec Assumptions).

---

## D6. Accepting safely under concurrency

**Decision**: `accept_invitation(session, settings, token, consent_text_id, now)` runs in one
transaction:

1. Load the user by email with `with_for_update()` (`FOR UPDATE` on PostgreSQL, nothing on
   SQLite).
2. `evaluate_invitation(..., lock=True)`. Its institution check reads the institution and region
   rows `with_for_update(read=True)` (`FOR SHARE`). This blocks a concurrent deactivation
   (`FOR NO KEY UPDATE`) and deletion until commit, but not another transaction's foreign-key
   check (`FOR KEY SHARE`).
3. If `consent_text_id` is not the role's current text, return `ConsentChanged`. Nothing is
   stored (FR-035).
4. Apply FR-028:
   - create the user (`is_active=True`), or
   - add the role to an active user, or
   - reactivate an inactive user.

   Then set the names, call `grant`, and insert the consent record. Commit.
5. On `IntegrityError` (two first acceptances for a new address: the unique `users.email`; or a
   duplicate `user_roles` primary key): roll back and re-run once. The second run finds the role
   held and returns `AlreadyHeld`.

Acceptance never touches `sessions`, so it signs nobody in and nobody out (FR-032).

**Rationale**:

- FR-031: at most one role grant and one consent record. The consent record is written only in
  the transaction that grants the role. A second press either waits on the user lock and then
  sees the role, or loses the unique-constraint race and retries into `AlreadyHeld`.
- Locking the user row also orders acceptance against a concurrent removal or withdrawal of the
  same person, which take the same lock (D8). The cut-off they write is then seen.
- This is the pattern milestone 7 used for institutions (`with_for_update`, research D5 there).
  It is correct on SQLite because SQLite serialises writers.

**Alternatives considered**:

- *An idempotency key in the form*: rejected. The token already identifies the invitation, and
  the role row and the unique email decide.
- *A unique constraint on consent records per invitation*: rejected. Two different invitations
  could share an issue time and a person, and the role row already guards.

---

## D7. Consent texts: an append-only table seeded by migrations

**Decision**: a table `consent_texts(id, role, version, text, published_at)` with
`UNIQUE(role, version)`. The current text of a role is the row with the highest `version`.

- The milestone 8 schema migration inserts `teacher` version 1, a placeholder wording that covers
  every FR-036 topic: what is stored, why, who can see it, that Resend delivers the emails, and
  how to withdraw. The wording lives in the migration module as a constant, like
  `SAMPLE_QUESTIONS`.
- A wording change is a **new migration that inserts version n+1**. No code path updates or
  deletes a consent text.
- `consent_records.consent_text_id` is a foreign key, so the profile shows the exact accepted
  text (FR-043).
- A test pins the SHA-256 of every published version. Editing a published text in place fails
  the build.
- The acceptance form carries the `consent_text_id` it showed, as a hidden field (FR-035).

**Rationale**: FR-037 requires that earlier versions are kept and that each record refers to its
version. A table with a foreign key makes "refers to" a database fact on PostgreSQL. A migration
is the reviewed, ordered, deploy-time way to publish a new version, and it runs on both engines.
The pinned hashes make "never changed once published" testable.

**Alternatives considered**:

- *Texts as Python constants keyed by version*: rejected. A deleted or edited constant would
  silently break old records' references. Nothing in the database would stop it.
- *Copy the full text into each consent record*: rejected. It duplicates the text per person,
  and the spec models the version as its own entity.

---

## D8. Erasure: one function behind withdrawal, data deletion and the list retirement's rules

**Decision**: `erase_personal_data(session, settings, user_id, now)` in `app/services/consent.py`:

1. Lock the user row (`with_for_update`).
2. For every role in `INVITABLE_ROLES` that the user holds, call `revoke`. Then call `set_cutoff`
   for **every** invitable role (D5), using the current email.
3. Set `first_name = last_name = NULL` and `data_erased_at = now`.
4. If the user does **not** hold `Role.ADMIN`, replace the email with `erased-<id>`. Otherwise
   keep it (FR-046, FR-047).
5. With no role left, set `is_active = False`.
6. Delete every session and every login code of the user (signed out everywhere). Commit.

Consent records are never touched.

- **"Has data stored on consent and not yet erased"** is `first_name IS NOT NULL`. Names are
  required on every invitation and are written only by acceptance, so they are present exactly
  between an acceptance and an erasure. This decides:
  - whether the profile shows **Withdraw consent** (FR-045);
  - whether a deletion email is sent (FR-051);
  - whether a deletion link is still usable (D10).
- **The replacement email** `erased-<id>` contains no `@`. It is unique per user, keeps
  `users.email NOT NULL UNIQUE`, and can never pass `is_valid_email`. So nobody can request a
  sign-in code for it, invite it, or match it from `ADMIN_EMAILS`.
- **The administrator role** "from the deployment configuration" is simply `Role.ADMIN`. Since
  this milestone, only `ADMIN_EMAILS` grants it (D16).

**Rationale**:

- Withdrawal (FR-046), data deletion (FR-053: "erase as Withdraw consent does") and the
  spec's "emails replaced as on withdrawal" for the retired lists share one rule. One function
  keeps them identical.
- `data_erased_at` is the only extra column. It records the erasure time, which is not personal
  data, and is what makes old deletion links "used" (D10).

**Alternatives considered**:

- *A separate `has_consent_data` flag*: rejected. It is redundant with the names and can drift.
- *Replace the email with `erased-<id>@invalid.example`*: rejected. It is a syntactically valid
  address, so an administrator could invite it and reactivate the erased account.
- *Hard-delete the user*: forbidden. Users are never hard-deleted, and later records refer to
  them.

---

## D9. Teacher data: the role row, a profile row and the links, always together

**Decision**: a teacher has three things, written by `grant` and deleted by `revoke` in the same
transaction:

- the `user_roles` row `(user_id, 'teacher')`;
- one `teacher_profiles` row with `can_create_competitions`;
- one or more `teacher_institutions` rows `(user_id, institution_id, access_level)`.

`access_level` is `'read'` or `'write'`, with a CHECK constraint and an `AccessLevel` StrEnum.
"Current teacher" for the tab and the teacher page means: holds the role **and** has a profile
row. In production the two always coincide.

- **Editing** (`update_teacher`):
  - locks the user row;
  - re-reads the current links;
  - computes the added, removed and changed links;
  - writes only those, and bumps `updated_at` only on the rows it changes (FR-040).

  A link whose institution is no longer selectable is kept with its level, unless it is unpicked
  (FR-011). Its level cannot be changed. The form shows it as text, and a submitted level for it
  is ignored.
- **Adding** an institution requires it to be selectable now. Its rows are locked `FOR SHARE`, as
  in D6.
- `count_institution_uses` (milestone 7's hook) now counts `teacher_institutions` rows (FR-012).
  A link insert racing an institution delete ends in milestone 7's foreign-key backstop
  (`IntegrityError` → "in use").
- **Removing** (`remove_teacher`):
  - locks the user row;
  - calls `revoke`;
  - sets the `teacher` cut-off;
  - deactivates the user if no role is left;
  - deletes all their sessions (FR-042).

  The email, names and consent records stay.

**Rationale**: FR-006 and FR-007 give per-link levels and one setting per teacher. A profile row
gives the setting a home that milestones 11 and 14 can read. Using the profile row as part of
"current teacher" also keeps the test cast (D16), whose teacher role is seeded directly, out of
the Teachers tab, so "No teachers yet" stays testable with the cast present.

**Alternatives considered**:

- *`can_create_competitions` as a column on `users`*: rejected. It is meaningless for
  non-teachers, and milestone 9 would add student columns there too.
- *Replace all links on every save*: rejected. It changes untouched links' timestamps, against
  FR-040.

---

## D10. Data deletion links: sealed, one hour, "used" through the erasure time

**Decision**:

- `POST /data-deletion` validates the address and applies the limits (D12). It then always
  answers with a 303 to `/data-deletion/requested`, which shows "If this email is registered, we
  have sent you a link." (FR-050).
- When the request was within the limits, a background task (milestone 4's pattern, research D10
  there) looks up the user by email, active or not, with `first_name IS NOT NULL`. If one is
  found, it seals `{"user": id, "at": now}` (`purpose = "data-deletion"`, `max_age = 1 hour`) and
  sends the deletion email. Otherwise it does nothing. Response and timing are the same for every
  address.
- A link is **usable** when:
  1. it unseals (else neutral `400`);
  2. it is younger than one hour (else "expired", `410`);
  3. the user still has consent data and `data_erased_at` is `NULL` or earlier than `at` (else
     "expired": the data was erased after the link was issued, so the link counts as used).
- `GET` shows what will be erased and changes nothing. `POST` re-checks under the user lock and
  calls `erase_personal_data`. If the browser's own session belongs to that user, the response
  also clears the cookie. Either way it redirects with a 303 to `/data-erased`.

**Rationale**:

- "Works once": after the erasure, every link for that user fails check 3. This holds even if the
  person is re-invited and accepts within the hour, because `data_erased_at` is then later than
  the old link's `at`.
- "Mostly not stored": the only state is `users.data_erased_at` (FR, Key Entities: "only what is
  needed to refuse reuse").
- The background task gives identical answers and timing for known, unknown and erased addresses
  (SC-006).

**Alternatives considered**:

- *A table of used deletion-link ids*: rejected. It stores more than needed, and still needs the
  erasure check for the re-invitation case.
- *An HMAC-signed, unencrypted link*: rejected. One codec for every link is simpler, and the user
  id would otherwise be readable.

---

## D11. Person names, invitation and edit forms, and the institution picker without JavaScript

**Decision**:

- **Person names**: `app/schemas/people.py` adds `PERSON_NAME_MAX_LENGTH = 100` and
  `clean_person_name(raw, field)`.
  - Control characters are refused first, on the raw value, with the milestone 6/7 control-
    character rule exposed from `app/schemas/names.py` as `has_control_character`.
  - Then the name is trimmed, and its length must be 1–100 code points. Inner spaces are kept.
  - Messages name the field: "Enter a first name.", "The last name can be at most 100
    characters."
- **Email**: validated and normalised exactly as at sign-in (`normalize_email`,
  `is_valid_email`).
- **Picker**: a table of the selectable institutions, sorted by `"Name (Region)"` ignoring case
  (Python sort, as in milestone 7). Each row has:
  - a checkbox `institution` with `value = <id>`;
  - a select `access` with options `<id>:read` (selected by default) and `<id>:write`.

  On the edit page, linked institutions that are no longer selectable appear as extra rows: a
  checked checkbox, the level as text, and a "deactivated" mark.
- **Parsing**: `institution: list[str] = Form([])` and `access: list[str] = Form([])`, parsed by
  `parse_institution_choices(institution, access)` into `{id: AccessLevel}`. It refuses:
  - a non-integer id;
  - the same id twice;
  - a picked id whose access entry is missing, or is not `read`/`write`, unless it is an
    already-linked unselectable institution, whose level is kept;
  - an empty pick ("Pick at least one educational institution.").

  Access entries for unpicked ids are ignored, because every row's select is always submitted.

**Rationale**:

- Two plain repeated fields keep the handlers sync and simple (`Form` lists of strings, never
  `int`, so a bad value re-renders the form instead of FastAPI's 422 JSON, as in milestone 4
  research D11).
- No JavaScript (Principle II).
- The default selected option makes "a newly picked institution defaults to Read" literal
  (FR-006).

**Alternatives considered**:

- *Dynamic field names (`access_12`)*: rejected. It needs `await request.form()`, so async
  handlers.
- *One select per row with "Not linked / Read / Write"*: rejected. It has no explicit "pick", and
  FR-006's default-on-pick reads less directly.
- *HTMX add-row widget*: rejected. Tens of institutions fit a table, and no script is needed.

---

## D12. Rate limits: one generic check, five buckets

**Decision**: `app/services/rate_limits.py` gains
`allow(session, secret_key, checks: Sequence[LimitCheck], now) -> bool`, which is the body of
`allow_code_request` generalised. `allow_code_request` becomes a thin wrapper, so its behaviour
and tests do not change. The buckets are:

| Bucket | Key (hashed) | Limit / hour | Used by |
|---|---|---|---|
| `code_email`, `code_client` | unchanged | 5, 20 | sign-in (milestone 4) |
| `invite_inviter` | inviter's user id | 20 | `POST /admin/teachers/invite` |
| `invite_email` | invited address | 5 | `POST /admin/teachers/invite` |
| `deletion_email` | address | 5 | `POST /data-deletion` |
| `deletion_client` | client address (milestone 4's `client_address`) | 20 | `POST /data-deletion` |

A hit is recorded **before** the email is sent, so a send failure still counts (spec Edge
Cases). A refused request records nothing. Hits live one hour and are purged by the existing
`purge_expired`.

**Rationale**: FR-018 and FR-050 give the per-inviter and per-address limits. The deletion form
is the second anonymous form that sends email. Milestone 4's per-client limit protects it from
being used to flood many addresses, and the spec's Assumptions say limits "follow the milestone 4
pattern", which has both buckets. The per-client bucket is additive: it never lets more through
than the spec allows.

**Alternatives considered**:

- *Copy `allow_code_request` per form*: rejected. Three copies of the sliding-window logic would
  drift.
- *Only the per-address limit on deletion requests*: rejected. One client could make the
  application send deletion emails to every consented address in turn.

---

## D13. Post/Redirect/Get without putting an address in a URL

**Decision**: two results must show an address after a redirect:

- "Invitation sent to …";
- the sign-in page with the email filled in.

The address travels **sealed** in the query string, with a 10-minute TTL:

- `POST /admin/teachers/invite` → `303 /admin/teachers?sent=<seal("invitation-sent",
  {"email"})>`. The tab shows the banner when `sent` unseals, and ignores it otherwise.
- `POST /invitations/{token}` (success) → `303 /login?prefill=<seal("login-prefill",
  {"email"})>`. The sign-in page fills the field and says the account is ready. An invalid or
  stale `prefill` is ignored. A signed-in visitor (US6, self-invitation) is sent on as today, and
  their session is untouched.
- "Already a teacher" → `303` back to `GET /invitations/{token}`, which shows that outcome
  (D4 step 6).

**Rationale**: FR-060 requires a redirect after every successful action. FR-004 and milestone 4
research D11 keep addresses out of URLs, because access logs record URLs. A sealed value is
unreadable, needs no server or cookie state, and survives a reload within its TTL.

**Alternatives considered**:

- *The address in plain text in the query*: rejected (access logs).
- *A flash cookie*: rejected. It is more moving parts (set, read, clear, flags), and it stores the
  address in the browser's cookie jar.
- *Rendering the result directly from the `POST`*: rejected (FR-060: a reload would offer to
  resend the invitation).

---

## D14. Logs: services log ids only, and the access log is redacted

**Decision**:

- Every new service logs at most ids, roles and counts. Examples: "Teacher invited:
  inviter_id=3 institutions=2", "Invitation accepted: user_id=9 role=teacher", "Consent
  withdrawn: user_id=9". Nothing logs an email, a name, a token or a URL.
- `app/core/log_redaction.py` adds `AccessLogRedactor(logging.Filter)`. The `lifespan` installs it
  on the `uvicorn.access` logger. It rewrites the path argument of uvicorn's access record:
  - `/invitations/<token>` becomes `/invitations/***`;
  - `/data-deletion/confirm/<token>` becomes `/data-deletion/confirm/***`;
  - the values of `sent` and `prefill` become `***`.
- Tests:
  - a unit test feeds the filter records shaped like uvicorn's `(client, method, path, version,
    status)`;
  - an integration test (`test_consent_privacy.py`) runs every flow of this milestone with
    `caplog` at `DEBUG` on the root logger, and asserts that the captured text contains none of
    the invited addresses, names or issued tokens (SC-007).
- Pages opened from a link send `Referrer-Policy: no-referrer` and `Cache-Control: no-store`
  (FR-061). The `console` email backend still prints bodies, including links. It is a local
  development aid and is refused on Render (milestone 4), so it is not a log.

**Rationale**: the uvicorn access log is the one place that prints URLs. `TestClient` does not
run uvicorn, so the filter needs its own unit test. Render's own edge request logs are outside the
application. The tokens there are encrypted, so they hold no readable personal data, and this is
recorded as a residual risk.

**Alternatives considered**:

- *`--no-access-log` in the Dockerfile*: rejected. It loses all request observability to hide two
  path shapes.
- *Tokens in the URL fragment*: rejected. The fragment never reaches the server without
  JavaScript.

---

## D15. Absolute links in emails: `PUBLIC_BASE_URL`

**Decision**: a new setting `PUBLIC_BASE_URL`, for example `https://brainring.org.ua`.

- On Render it is **required** and must be `https://` with no path, query or fragment.
- Locally it is optional. When it is unset, links are built from the request's base URL.
- It is read by `resolve_auth_settings` into `AuthSettings.public_base_url`, and validated with
  the other settings. The error names the setting, never its value.
- `render.yaml` sets it as a plain value: it is not a secret.

**Rationale**: the deletion request is anonymous. Building its link from the request's `Host`
header would allow host-header poisoning: an attacker posts the victim's address with a forged
`Host`, and the victim receives a genuine token on the attacker's domain. Behind Render's proxy,
the request scheme is also `http`, so links built from the request would not be `https`. A
configured origin removes both problems.

**Alternatives considered**:

- *Trust `Host` / `X-Forwarded-*`*: rejected (poisoning).
- *Hard-code the domain*: rejected. Local, CI and any future host need different values.

---

## D16. Retiring the teacher and student lists

**Decision**:

- **Settings**: `resolve_auth_settings` stops reading `TEACHER_EMAILS` and `STUDENT_EMAILS`.
  `AuthSettings` loses `teacher_emails` and `student_emails`. A leftover value in an environment
  is ignored (FR-056). The local warning becomes "ADMIN_EMAILS is empty; nobody will be able to
  sign in as an administrator."
- **Reconcile**: `reconcile_users(session, admin_emails, now)` manages **only** `Role.ADMIN`:
  - a listed address with no user is created;
  - an inactive listed user is reactivated;
  - the admin role is added or removed;
  - a user is deactivated only when no role at all is left;
  - every session of anyone who lost the admin role is deleted.

  Teacher and student rows are never read or written (FR-057). The final sweep of sessions and
  codes of inactive users stays. `reconcile_users_with_retry` and `ReconcileResult` keep their
  shapes.
- **One data migration** (`retire_role_lists`) runs once, at deploy (FR-058):
  1. delete the sessions of users holding `teacher` or `student`;
  2. delete all `teacher` and `student` role rows;
  3. for every user left with no role: `is_active = false`, `email = 'erased-' || id`,
     `data_erased_at = now`, `updated_at = now`, and delete their sessions and login codes.

  It uses SQLAlchemy Core expressions, which render `||` on both engines. Downgrade is a no-op:
  the removed grants came from configuration that no longer exists.
- **Tests**: the cast (milestone 5 research D12) keeps its five people. `client` sets only
  `ADMIN_EMAILS`. A test-only helper `seed_roles_directly(engine, {email: roles})` in
  `tests/conftest.py`, run after start-up, inserts the cast's teacher and student role rows
  directly, like `sign_in_directly`. No route or setting of the application can do this. Cast
  teachers have no profile row, so they are not "current teachers" for the tab (D9). Tests that
  need a real teacher create one through the invitation flow or the `grant_teacher` service
  helper.

**Rationale**:

- Before this milestone, every teacher and student role came from the lists. After it, the
  reconcile can no longer tell list grants from consent grants. So the cleanup must happen exactly
  once, in a migration, before the new code starts.
- Users already inactive from earlier list removals have no role either. Replacing their emails
  too means no address that never consented remains (spec Assumptions: no real users yet).

**Alternatives considered**:

- *Clean up in the reconcile at every start*: rejected. It would remove consented teachers.
- *A `source` column on `user_roles`*: rejected. The source is fixed per role (administrator:
  configuration; teacher and student: consent).

---

## D17. Pages, routes and access

**Decision**: four router modules (contracts in [contracts/http-routes.md](./contracts/http-routes.md)):

- `admin_teachers.py`: the Teachers tab, invite, the teacher page, and remove. All are
  `@allow_roles(Role.ADMIN)`. It replaces the placeholder handler in `admin.py`.
- `profile.py`: `/profile` and withdrawal, `@allow_roles(*ALL_ROLES)`.
- `invitations.py`: `/invitations/{token}`, `GET` and `POST`. Both are added to `PUBLIC_ROUTES`.
- `data_deletion.py`: `/data-deletion`, `/data-deletion/requested`,
  `/data-deletion/confirm/{token}` and `/data-erased`. All are added to `PUBLIC_ROUTES`.

Further decisions:

- The header's email becomes a link to `/profile` (spec Assumption).
- The sign-in page gains a **Delete my data** link (FR-049).
- Every change is a `POST` through the application-wide cross-site check (FR-059), and every
  success is a 303 (FR-060).

**Rationale**:

- One router per area follows milestones 6 and 7.
- The public pages carry their own authority (the sealed token), so they must work for anonymous
  visitors and for anyone signed in, whatever their role. `PUBLIC_ROUTES` is exactly that, and the
  allowlist is a reviewed, test-pinned set.
- `ALL_ROLES` on the profile still requires a chosen role, which the role choice provides.

**Alternatives considered**:

- *Make the invitation pages role-protected*: rejected. The invited person usually has no account
  yet (FR-065).

---

## D18. Migrations

**Decision**: two Alembic revisions on top of `b300a1055049`.

1. **`create_consent_and_teachers`** (schema):
   - `users`: add `first_name`, `last_name` (`String(100)`, nullable) and `data_erased_at`
     (`UTCDateTime`, nullable), with `batch_alter_table` for SQLite.
   - Create `teacher_profiles`, `teacher_institutions`, `consent_texts`, `consent_records` and
     `invitation_cutoffs`.
   - Insert `consent_texts` (`teacher`, version 1).
   - The downgrade drops all of these.
2. **`retire_role_lists`** (data, D16). The downgrade is a no-op.

**Rationale**: the schema and the one-time data step are reviewed and reverted separately, as in
milestone 3 (`create_questions…` then `seed_sample_questions`). Both run on SQLite and PostgreSQL,
and the stairway and drift tests cover them.

---

## D19. Times shown to people

**Decision**: stored times stay UTC (`UTCDateTime`). The invitation expiry in the email and on the
page, the consent times on the profile, and the consent date on the Teachers tab are shown in UTC
with an explicit "UTC" suffix: `2026-10-22 14:05 UTC`, and for the tab date `2026-10-15`. One
Jinja filter, `utc`, formats them.

**Rationale**: the application has no per-user time zone yet. Labelling UTC is unambiguous
(Principle VII: convert only for display).
