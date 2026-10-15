# Contract: Services — Sealing, Invitations, Teachers, Consent, Data Deletion (Milestone 8)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) | **Data model**: [data-model.md](../data-model.md)

**Conventions**, as in milestones 4–7:

- Services take a `sqlmodel.Session` and, where time matters, `now: datetime | None = None`
  (defaulting to `utc_now()`).
- They raise typed exceptions or return typed outcomes.
- They commit their own transaction.
- They enforce no route authorization: routers do, through `@allow_roles` or `PUBLIC_ROUTES`.
- They log ids, roles and counts only, never an email, a name, a token or a URL (FR-004).

---

## `app/core/sealing.py` (NEW, pure; research D1)

```python
SEAL_VERSION = 1

class SealInvalid(ValueError): ...        # tampered, malformed, wrong purpose, unknown version
class SealExpired(ValueError): ...        # authentic, but older than max_age

def seal(secret_key: str, purpose: str, payload: Mapping[str, Any], now: datetime | None = None) -> str
def unseal(secret_key: str, purpose: str, token: str, max_age: timedelta,
           now: datetime | None = None) -> dict[str, Any]
```

**`seal`**:

- The plaintext is compact JSON of `payload`, plus `"at"`: microseconds since the epoch of `now`.
- It is encrypted with AES-256-GCM. The key is HKDF-SHA256(`secret_key`), cached per key. The
  nonce is 12 random bytes. The AAD is `bytes([SEAL_VERSION]) + purpose.encode()`.
- The token is `base64url(version ‖ nonce ‖ ciphertext‖tag)`, without padding.

**`unseal`**:

- It checks the format, the version, the tag, the JSON, and that `"at"` is an integer. Any failure
  raises `SealInvalid`.
- Then `now − at ≥ max_age` raises `SealExpired`.
- It never logs, and its exception messages never contain the token or the payload.

**Purposes and lifetimes**:

| Purpose | Lifetime |
|---|---|
| `invitation` | 7 days |
| `data-deletion` | 1 hour |
| `invitation-sent` | 10 minutes |
| `login-prefill` | 10 minutes |

These are constants, defined beside their users.

---

## `app/core/security.py` (CHANGED)

```python
def hash_invitation_cutoff_key(secret_key: str, email: str) -> str
    # HMAC-SHA256 hex over "invitation-cutoff\0" + email (normalised by the caller); research D5
```

## `app/core/log_redaction.py` (NEW; research D14)

```python
class AccessLogRedactor(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool   # always True; rewrites record.args[2]
```

- It applies to records whose `args` is uvicorn's 5-tuple
  `(client, method, full_path, http_version, status)`.
- It replaces the segment after `/invitations/` and after `/data-deletion/confirm/` with `***`.
- It replaces the values of the `sent` and `prefill` query parameters with `***`.
- Other records pass unchanged.
- The `lifespan` installs it once on `logging.getLogger("uvicorn.access")`.

## `app/core/config.py` (CHANGED; research D15, D16; [configuration.md](./configuration.md))

`AuthSettings`:

- loses `teacher_emails` and `student_emails`;
- gains `public_base_url: str | None`.

`resolve_auth_settings`:

- stops reading `TEACHER_EMAILS` and `STUDENT_EMAILS`;
- validates `PUBLIC_BASE_URL`.

---

## `app/schemas/people.py` (NEW; research D11)

```python
PERSON_NAME_MAX_LENGTH = 100

def clean_person_name(raw: str, field_label: str) -> str     # raises InvalidName(.message)
def clean_email(raw: str) -> str                             # normalize_email + is_valid_email;
                                                             # raises InvalidEmail(.message)
```

`app/schemas/names.py` exposes `has_control_character(raw) -> bool`, the existing rule made
public. Its behaviour is unchanged.

## `app/schemas/teachers.py` (NEW)

```python
@dataclass(frozen=True)
class TeacherDetails:
    institutions: Mapping[int, AccessLevel]          # non-empty
    can_create_competitions: bool

class InvalidChoice(ValueError): message: str

def parse_institution_choices(institution: Sequence[str], access: Sequence[str],
                              keep_level_for: Mapping[int, AccessLevel] = {}) -> dict[int, AccessLevel]
```

`parse_institution_choices` refuses:

- an empty pick: "Pick at least one educational institution.";
- a non-integer id: "This educational institution cannot be selected.";
- a duplicate id: "Each educational institution can be picked only once.";
- a missing level, an unknown level, or conflicting levels for a picked id: "Choose Read or Write
  access for each educational institution."

For ids in `keep_level_for` (linked but no longer selectable), the submitted level is ignored and
the kept level is used. Selectability is checked by the service, not here.

---

## `app/services/rate_limits.py` (CHANGED; research D12)

```python
@dataclass(frozen=True)
class LimitCheck:
    bucket: str
    key: str          # plain; hashed with hash_rate_limit_key before any query or insert
    limit: int

def allow(session, secret_key, checks: Sequence[LimitCheck], now=None) -> bool
def allow_code_request(session, secret_key, email, client, now=None) -> bool   # unchanged behaviour
```

`allow` works as follows:

- If any bucket already has `limit` or more hits in the last hour, it returns `False` and records
  nothing.
- Otherwise it records one hit per check, commits, and returns `True`.

New constants:

| Constant | Value |
|---|---|
| `BUCKET_INVITE_INVITER` | `invite_inviter` |
| `BUCKET_INVITE_EMAIL` | `invite_email` |
| `BUCKET_DELETION_EMAIL` | `deletion_email` |
| `BUCKET_DELETION_CLIENT` | `deletion_client` |
| `INVITER_INVITE_LIMIT` | 20 |
| `EMAIL_INVITE_LIMIT` | 5 |
| `EMAIL_DELETION_LIMIT` | 5 |
| `CLIENT_DELETION_LIMIT` | 20 |

---

## `app/services/institutions.py` (CHANGED)

```python
@dataclass(frozen=True)
class SelectableInstitution:
    id: int
    label: str                 # "Name (Region)"
    is_selectable: bool        # institution.is_active and region.is_active

def list_selectable_institutions(session) -> list[SelectableInstitution]
    # active institutions in active regions, sorted by label casefold, then id (FR-009)
def describe_institutions(session, ids: Iterable[int], lock: bool = False) -> dict[int, SelectableInstitution]
    # the found ids only (unknown ids are absent), with current names and selectability;
    # lock=True reads the institution and region rows FOR SHARE (research D6)
def count_institution_uses(session, institution_id) -> int
    # NOW: the number of teacher_institutions rows for the institution (FR-012)
```

---

## `app/services/users.py` (CHANGED; research D16)

```python
def reconcile_users(session, admin_emails: Sequence[str], now=None) -> ReconcileResult
def get_user_by_email(session, email) -> User | None          # active or not
def end_all_sessions(session, user_id) -> None                # deletes sessions; no commit
def display_name(user) -> str                                 # "First Last" or the email
```

`reconcile_users` reads and writes only `admin` role rows:

- It creates a listed address that has no user.
- It reactivates an inactive listed user.
- It adds and removes the `admin` role.
- It deactivates a user only when no role at all remains.
- It deletes the sessions of everyone who lost `admin`.

`ReconcileResult` keeps its fields. The `lifespan` passes `settings.admin_emails`.

---

## `app/services/invitations.py` (NEW; research D2–D6)

```python
INVITATION_PURPOSE = "invitation"
INVITATION_TTL = timedelta(days=7)

class InvitableRole(Protocol):
    role: Role
    def details_to_payload(self, details: Any) -> dict[str, Any]: ...
    def details_from_payload(self, raw: Any) -> Any: ...                 # raises ValueError
    def inviter_may_invite(self, session, inviter: User, details: Any) -> bool: ...
    def details_acceptable(self, session, details: Any, lock: bool) -> bool: ...
    def describe(self, session, details: Any) -> list[DetailLine]: ...
    def grant(self, session, user: User, details: Any, now: datetime) -> None: ...   # no commit
    def revoke(self, session, user_id: int) -> None: ...                              # no commit

INVITABLE_ROLES: dict[Role, InvitableRole]          # {Role.TEACHER: TEACHER_INVITATION}

@dataclass(frozen=True)
class Invitation:
    role: Role; email: str; first_name: str; last_name: str
    details: Any; inviter_id: int; issued_at: datetime
    @property
    def expires_at(self) -> datetime                 # issued_at + 7 days

# Outcomes
class Invalid, Expired, Refused                       # no payload
@dataclass class AlreadyHeld:  invitation: Invitation
@dataclass class Acceptable:   invitation: Invitation
@dataclass class Accepted:     user_id: int; email: str
@dataclass class ConsentChanged: invitation: Invitation

def issue_invitation(session, settings, sender, base_url, inviter: User, role: Role,
                     email, first_name, last_name, details, now=None) -> None
def evaluate_invitation(session, settings, token, now=None, lock=False)
        -> Invalid | Expired | Refused | AlreadyHeld | Acceptable
def accept_invitation(session, settings, token, consent_text_id: int, now=None)
        -> Invalid | Expired | Refused | AlreadyHeld | ConsentChanged | Accepted
```

### `issue_invitation`

The router has already validated the form and checked the rate limits (FR-018).

1. Re-check `inviter_may_invite`, and check that every institution is selectable now. On failure,
   raise `InvalidChoice` (the router answers `400`).
2. Seal the payload (data-model §9).
3. Build `invitation_message(...)` with the absolute link `<base_url>/invitations/<token>`.
4. `sender.send(...)`. `EmailDeliveryError` propagates (the router answers `503`).

It writes nothing to the database. It logs "Invitation sent: inviter_id=… role=…
institutions=<n>".

### `evaluate_invitation`

The check order is research D4. `lock=False` reads only.

### `accept_invitation`

The transaction is research D6:

1. Lock the user by email.
2. Evaluate with `lock=True`.
3. If `consent_text_id` is not the current text of the role, return `ConsentChanged`.
4. Apply FR-028: create, add the role, or reactivate. Set the names and `updated_at`, call
   `role_def.grant`, and insert a `ConsentRecord`. Commit.
5. On `IntegrityError`: roll back and run once more. The second run's `AlreadyHeld` is the answer.

It never touches sessions. It logs "Invitation accepted: user_id=… role=… created|added|
reactivated".

---

## `app/services/teachers.py` (NEW; research D3, D9)

```python
TEACHER_INVITATION: InvitableRole          # registered in INVITABLE_ROLES

@dataclass(frozen=True)
class TeacherLink:
    institution_id: int; label: str; access_level: AccessLevel; is_selectable: bool

@dataclass(frozen=True)
class TeacherView:
    user_id: int; email: str; first_name: str; last_name: str
    links: list[TeacherLink]               # sorted by label casefold
    can_create_competitions: bool
    consented_at: datetime | None          # latest teacher consent record

class TeacherNotFound(LookupError): ...
class InstitutionNotSelectable(ValueError): message: str

def list_teachers(session) -> list[TeacherView]               # FR-038 order
def get_teacher(session, user_id) -> TeacherView              # raises TeacherNotFound
def update_teacher(session, user_id, first_name, last_name,
                   institutions: Mapping[int, AccessLevel], can_create_competitions: bool,
                   now=None) -> TeacherView
def remove_teacher(session, settings, user_id, now=None) -> None
def grant_teacher(session, user, details: TeacherDetails, now) -> None    # = TEACHER_INVITATION.grant
```

### "Current teacher"

The user holds `teacher` **and** has a `teacher_profiles` row (research D9). Anyone else, or an
unknown id, is `TeacherNotFound`.

### `update_teacher`

1. Lock the user and re-check that they are a current teacher.
2. Lock the newly added institutions `FOR SHARE`. Any of them that is not selectable or does not
   exist raises `InstitutionNotSelectable`, and nothing changes.
3. Write only the differences:
   - insert the added links;
   - delete the removed links;
   - update the level of changed links, and their `updated_at`;
   - update the setting and the names when they changed.

   Commit.

It never deletes sessions (FR-041). It logs "Teacher updated: user_id=… added=… removed=…
changed=…".

### `remove_teacher`

1. Lock the user and call `revoke`.
2. `set_cutoff(email, teacher)`.
3. Deactivate the user if no role is left.
4. `end_all_sessions`. Commit.

It logs "Teacher removed: user_id=… deactivated=…".

### `TEACHER_INVITATION`

| Member | Teacher implementation |
|---|---|
| `inviter_may_invite` | the inviter is active and holds `admin` |
| `details_acceptable` | every id is found by `describe_institutions` with `is_selectable` |
| `describe` | one line per institution, "Name (Region) — Read/Write", plus "Can create competitions: Yes/No" |
| `grant` | add the role row, the profile and the links |
| `revoke` | delete the links, the profile and the role row (only those present) |

---

## `app/services/consent.py` (NEW; research D5, D7, D8)

```python
def current_consent_text(session, role: Role) -> ConsentText            # highest version
def list_consent_records(session, user_id) -> list[ConsentRecordView]   # newest first, with text
def latest_consent_at(session, user_id, role) -> datetime | None
def has_consent_data(user: User) -> bool                                # first_name is not None
def get_cutoff(session, secret_key, email, role) -> datetime | None
def set_cutoff(session, secret_key, email, role, now) -> None           # raise-only upsert; no commit
def erase_personal_data(session, settings, user_id, now=None) -> ErasureResult
```

`ErasureResult` holds `roles_removed: tuple[Role, ...]`, `email_kept: bool` and
`deactivated: bool`.

### `erase_personal_data`

The steps are research D8, in one transaction:

1. Lock the user.
2. Call `revoke` for each invitable role held.
3. `set_cutoff` for every invitable role.
4. Clear the names and set `data_erased_at`.
5. Replace the email with `erased-<id>`, unless the user holds `admin`.
6. Deactivate the user if no role is left.
7. Delete all sessions and login codes. Commit.

Consent records are untouched. It logs "Personal data erased: user_id=… roles_removed=…
email_kept=…".

### Planning a withdrawal

```python
def describe_erasure(session, user) -> ErasurePlan
```

`ErasurePlan` holds the names, the email, the roles to remove, `email_kept` and
`will_deactivate`. The withdrawal and deletion confirmation pages use it.

---

## `app/services/data_deletion.py` (NEW; research D10)

```python
DELETION_PURPOSE = "data-deletion"
DELETION_TTL = timedelta(hours=1)

class LinkInvalid, LinkExpired                        # outcomes

def deliver_deletion_link(engine, sender, settings, base_url, email) -> None
    # background task: user by email with consent data → seal {"user": id} → deletion_message.
    # Otherwise nothing. Every exception is caught and logged by type only (as deliver_login_code).
def read_deletion_link(session, settings, token, now=None, lock=False)
        -> LinkInvalid | LinkExpired | User
def confirm_deletion(session, settings, token, now=None) -> LinkInvalid | LinkExpired | ErasureResult
```

A link is usable while all of these hold:

- the user exists;
- `has_consent_data(user)`;
- `data_erased_at is None or data_erased_at < at`.

Anything else is `LinkExpired` (a used link). A link that does not unseal is `LinkInvalid`.

---

## `app/services/email.py` (CHANGED)

```python
def invitation_message(to, inviter_display, inviter_email, role_label, detail_lines,
                       link, expires_at) -> EmailMessage
def deletion_message(to, link, expires_at) -> EmailMessage
```

Both are plain text. Links appear as given, with no tracking. The application keeps no copy: the
`memory` backend's outbox exists only in tests.

### Invitation email

- **Subject**: "You are invited to Student Competitions as a teacher". It contains no names.
- **Body**:
  - who invites: "<display name> (<email>)";
  - the role;
  - each institution with its access level;
  - "You will be able to create competitions." or "You will not be able to create
    competitions.";
  - "Nothing about you is stored unless you accept.";
  - the link;
  - "This invitation expires on <UTC time>.".

### Deletion email

- **Subject**: "Delete your Student Competitions data".
- **Body**:
  - what the link does: it erases the names and the address, and removes the roles granted by
    consent;
  - that it works once, within one hour, until <UTC time>;
  - the link;
  - "If you did not ask for this, you can ignore this email."
