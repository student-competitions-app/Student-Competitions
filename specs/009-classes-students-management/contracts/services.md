# Contract: Services — Availability, Teacher Access, Classes, Students (Milestone 9)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D2–D5, D8–D14

These are the signatures and behaviour the routers and tests rely on. Every function:

- takes an open `Session` first; the caller owns it;
- commits once per successful write and rolls back on refusal, so no lock outlives a refused
  change;
- logs ids and counts only (FR-057).

`now` parameters default to `utc_now()` and exist for tests.

**Import graph**, with no cycles:

```text
availability ──> models, users
teacher_access ──> availability, models
classes ──> teacher_access, availability, schemas.names, schemas.classes
students ──> teacher_access, classes, consent, invitations (protocol types), institutions
invitations ──(lazy)──> teachers, students            regions, institutions ──> availability
sessions ──> availability                               login ──> availability
```

---

## `app/schemas/classes.py` (NEW, pure)

```python
YEAR_MIN, YEAR_MAX = 1, 12
INVALID_YEAR = "Enter a year of study from 1 to 12."

class InvalidYear(ValueError):
    message: str

def parse_year_of_study(raw: str) -> int
```

The value is trimmed and must be ASCII digits with a value from 1 to 12, so `"02"` gives `2`.
Anything else raises `InvalidYear`, for example `""`, `"0"`, `"13"`, `"2.5"`, `"+2"`, `"two"` or
`"٢"`.

## `app/schemas/students.py` (NEW, pure)

```python
@dataclass(frozen=True)
class StudentDetails:
    institution_id: int
    class_id: int
```

---

## `app/services/availability.py` (NEW; research D2–D4)

```python
def is_student_blocked(session, user_id: int) -> bool
```

`True` ⇔ an enrolment exists and its class, the class's institution or its region is inactive.

```python
def usable_roles(session, user_id: int) -> tuple[Role, ...]
```

`get_roles` without `Role.STUDENT` while the person is blocked. The order is fixed.

```python
def get_signable_user_by_email(session, email: str) -> User | None
```

An active user with at least one usable role. Used only by sign-in.

```python
def class_is_available(session, class_id: int, lock: bool = False) -> bool
```

The class exists and the chain is active. With `lock`, the class, institution and region rows are
read `FOR SHARE`.

```python
def sign_out_students_below(
    session, *, region_id: int | None = None, institution_id: int | None = None,
    class_id: int | None = None,
) -> int
```

- Exactly one keyword must be given.
- It deletes every session of every person enrolled in a class below that object, and returns the
  number deleted.
- It does not commit.

---

## `app/services/sessions.py` (CHANGED; research D3)

- `get_session_identity`:
  - `roles` holds only usable roles; the query for the enrolment chain runs only when the student
    role is held;
  - a stored current role that is not usable deletes the session and returns `None`, as for a role
    not held;
  - no usable role at all returns `None`.
- `start_session`: the initial current role comes from `usable_roles`.

## `app/services/login.py` (CHANGED)

- `verify_code` and `deliver_login_code` look the person up with
  `availability.get_signable_user_by_email` instead of `users.get_active_user_by_email`.
- Nothing else changes: same timing, same messages, same logging.

## `app/services/rate_limits.py` (CHANGED)

```python
BUCKET_INVITE_STUDENT_INVITER = "invite_student_inviter"
STUDENT_INVITER_INVITE_LIMIT = 100
```

The docstring table gains the row. `invite_email` (5 per hour) is shared by both roles.

---

## `app/services/regions.py` and `app/services/institutions.py` (CHANGED)

- **`set_region_active(…, active=False)`** and **`set_institution_active(…, active=False)`**:
  when the status actually changes, they call `sign_out_students_below` in the same transaction
  (research D4). They log "Students signed out: region_id=… sessions=…".
- **`count_institution_uses`**: teacher links + enrolments whose class belongs to the
  institution.
- **`delete_institution`**:
  - refused (`InstitutionInUse`) while uses > 0;
  - otherwise it deletes the institution's classes, then the institution, in one transaction;
  - an `IntegrityError` at commit is reported as `InstitutionInUse` (research D14).

---

## `app/services/teacher_access.py` (NEW; research D5)

```python
class NotReachable(LookupError): ...
class WriteRequired(PermissionError): ...

@dataclass(frozen=True)
class ReachableInstitution:
    id: int
    name: str
    region_id: int
    region_name: str
    access_level: AccessLevel
    label: str                 # "Name — Read" / "Name — Write"
    @property
    def can_write(self) -> bool
```

```python
def list_reachable_institutions(session, teacher_id: int) -> list[ReachableInstitution]
```

- The teacher's linked institutions that are available: the institution and its region are
  active.
- Sorted by region `name_key`, then institution `name_key`, then id.
- Empty for a teacher with no links, which includes the test cast's directly seeded teacher.

```python
def reachable_regions(institutions: list[ReachableInstitution]) -> list[tuple[int, str]]
```

The distinct regions of those institutions, sorted ignoring case. Pure.

```python
def reach_institution(
    session, teacher_id: int, institution_id: int, *, region_id: int | None = None,
    write: bool = False, lock: bool = False,
) -> ReachableInstitution
```

- `NotReachable` if the institution is not linked, not available, or not in `region_id` when one
  is given.
- `WriteRequired` if `write` and the level is Read.
- With `lock`, the link, institution and region rows are read `FOR SHARE`.

```python
def reach_class(
    session, teacher_id: int, class_id: int, *, institution_id: int | None = None,
    write: bool = False, lock: bool = False,
) -> tuple[ReachableInstitution, SchoolClass]
```

- The class, active or deactivated, of a reachable institution.
- `NotReachable` if the class is unknown or not in `institution_id`.
- With `lock`, the class row is also locked: `FOR UPDATE`.

```python
def reach_student(
    session, teacher_id: int, user_id: int, *, write: bool = False, lock: bool = False,
) -> tuple[ReachableInstitution, SchoolClass, User]
```

- The person must hold the student role, have an enrolment, have an available class, and belong to
  a reachable institution. Otherwise `NotReachable`.
- With `lock`, the user row is locked `FOR UPDATE` before anything else is read.

Before raising, every function rolls back if it took a lock.

---

## `app/services/classes.py` (NEW; research D8)

```python
class DuplicateClassName(ValueError): message  # "A class named “…” already exists in this institution."
class ClassInUse(ValueError): school_class: SchoolClass; students: int

@dataclass(frozen=True)
class ClassView:
    id: int
    institution_id: int
    name: str
    year_of_study: int
    is_active: bool
    @property
    def label(self) -> str      # "KN-21 · year 2"
```

| Function | Behaviour |
|---|---|
| `list_classes(session, institution_id) -> list[ClassView]` | All classes of the institution, sorted by `name_key`, then id. It does not check reach: the router calls `reach_institution` first. |
| `count_institution_classes(session, institution_id) -> int` | For the administrator's delete confirmation (research D14). |
| `create_class(session, teacher_id, institution_id, raw_name, raw_year) -> ClassView` | `reach_institution(write=True, lock=True)`, then `clean_name` and `parse_year_of_study`, then the duplicate check, then insert and commit. An `IntegrityError` becomes `DuplicateClassName`. Raises `InvalidName`, `InvalidYear`, `DuplicateClassName`, `NotReachable` or `WriteRequired`. |
| `update_class(session, teacher_id, class_id, raw_name, raw_year) -> ClassView` | `reach_class(write=True, lock=True)`. The class itself never counts as a duplicate, so a change of case is valid. An unchanged form writes nothing. |
| `set_class_active(session, teacher_id, class_id, active: bool) -> ClassView` | `reach_class(write=True, lock=True)`. A no-op when unchanged. Deactivation calls `sign_out_students_below(class_id=…)` before the commit (FR-015). |
| `delete_class(session, teacher_id, class_id) -> None` | `reach_class(write=True, lock=True)`, then the enrolments are counted, blocked included. Any → `ClassInUse` (FR-006). Otherwise delete and commit. An `IntegrityError` becomes `ClassInUse`. |

---

## `app/services/students.py` (NEW; research D9, D12)

### `STUDENT_INVITATION` (the student's `InvitableRole`)

| Member | Contract |
|---|---|
| `role` | `Role.STUDENT` |
| `details_to_payload(d)` | `{"institution": d.institution_id, "class": d.class_id}` |
| `details_from_payload(raw)` | A dict with exactly those keys, each a non-boolean `int`. Otherwise `ValueError`. |
| `inviter_may_invite(session, inviter, d)` | `inviter.is_active`, holds `Role.TEACHER`, and has a `teacher_institutions` row for `d.institution_id` with `write`. |
| `details_acceptable(session, d, lock)` | The class exists, `class.institution_id == d.institution_id`, and `class_is_available(…, lock=lock)`. |
| `describe(session, d)` | `[DetailLine("Educational institution: Name (Region)"), DetailLine("Class: KN-21 · year 2")]` by current names. Missing rows give no line, though the checks refuse such links first. |
| `grant(session, user, d, now)` | Adds `UserRole(student)` and `Enrolment(user_id, class_id)`, then flushes. |
| `revoke(session, user_id)` | Deletes the enrolment and the student role row. |

`invitations.invitable_roles()` returns `{Role.TEACHER: TEACHER_INVITATION, Role.STUDENT:
STUDENT_INVITATION}`. It imports `teachers` and `students` lazily.

### Lookups and changes

```python
NOT_A_NEW_STUDENT = "This email already belongs to a student"
CLASS_DEACTIVATED = "This class is deactivated."


class ClassNotActive(ValueError):
    message


@dataclass(frozen=True)
class StudentRow:
    user_id: int
    first_name: str
    last_name: str
    email: str
    class_id: int


@dataclass(frozen=True)
class EnrolmentView:
    institution_label: str  # "Name (Region)"
    class_name: str
    year_of_study: int
    is_available: bool
```

| Function | Behaviour |
|---|---|
| `is_student_address(session, email) -> bool` | Someone with this address holds `Role.STUDENT`, blocked or not (FR-026). |
| `list_students(session, class_id) -> list[StudentRow]` | The class's enrolled people, sorted by last name, then first name (case-folded), then id. The router lists only for an active class of a reachable institution. |
| `get_student(session, teacher_id, user_id, *, write=False) -> tuple[ReachableInstitution, ClassView, StudentRow]` | Through `reach_student(write=write)`. Raises `NotReachable`, and `WriteRequired` when `write` is set and the access level is Read. The student pages (§2.4 of http-routes.md) call it with `write=True`. |
| `update_student(session, teacher_id, user_id, first_name, last_name, raw_class_id: str, now=None) -> int` | Returns the student's class id after the save. Names are already cleaned by the router. Steps: `reach_student(write=True, lock=True)`; parse `raw_class_id`, where a non-integer raises `NotReachable`; the target class must be in the same institution, else `NotReachable`; it must be active, else `ClassNotActive`; then the target class is read `FOR SHARE`. Only changed values are written. Sessions are untouched (FR-042). |
| `remove_student(session, settings, teacher_id, user_id, now=None) -> None` | `reach_student(write=True, lock=True)`, then `STUDENT_INVITATION.revoke`, then `set_cutoff(…, Role.STUDENT, now)`. The person is deactivated if no role is left. Then `end_all_sessions`, and commit (FR-043). |
| `get_enrolment_view(session, user_id) -> EnrolmentView \| None` | For the profile; `None` when there is no enrolment. |

---

## `app/services/invitations.py` (CHANGED; research D9, D10)

- The registry gains the student, as above.
- In `_accept_once`, the names from the link are written unless all of these hold:
  - `user` exists and is active;
  - `first_name is not None`;
  - `{Role.TEACHER, Role.STUDENT} & set(get_roles(session, user.id))` is non-empty.

  When they all hold, the names are kept (FR-036, FR-037).
- `issue_invitation`'s log line adds `class_id` when the details carry one.

## `app/services/consent.py` (no code change)

- `erase_personal_data` already revokes every invitable role held and raises every invitable
  role's cut-off. With the student registered, that covers the student role, the enrolment and the
  student cut-off (FR-044).
- `describe_erasure` lists "Student" among the roles to remove.

## `app/services/email.py` (no code change)

`invitation_message` takes the detail lines. For a student, the body reads:

```text
Olena Kovalenko (olena@example.org) invites you to Student Competitions as a student.

Role: Student
- Educational institution: Kyiv Polytechnic Institute (Kyiv)
- Class: KN-21 · year 2

Nothing about you is stored unless you accept. …
```

It also gives the link and its expiry, so the email covers every FR-029 item.
