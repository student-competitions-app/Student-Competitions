# Internal Interfaces Contract: roles, sessions, access declaration, cross-site check

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](../plan.md)

Signatures and behaviour of the functions this milestone adds or changes. They are internal (no
external caller), but the tests are written against them, so they are fixed here. Services are
plain functions taking a `sqlmodel.Session`. Nothing here logs an email address, a token or a
hash. Milestone 4's interfaces not listed below are unchanged
([specs/004-email-otp-auth/contracts/auth-services.md](../../004-email-otp-auth/contracts/auth-services.md)).

---

## `app/services/users.py`

```python
@dataclass(frozen=True)
class ReconcileResult:
    created: int
    reactivated: int
    deactivated: int
    roles_added: int
    roles_removed: int
    unchanged: int          # people whose active flag and role set did not change

def reconcile_users(
    session: Session,
    role_lists: Mapping[Role, Sequence[str]],
    now: datetime | None = None,
) -> ReconcileResult: ...

def get_roles(session: Session, user_id: int) -> tuple[Role, ...]:
    """The roles held, in the fixed order; () for none."""

def get_active_user_by_email(session: Session, email: str) -> User | None:  # unchanged
```

`reconcile_admins` is **removed**. `role_lists` holds addresses that are already normalised and
de-duplicated (by `resolve_auth_settings`). A role missing from the mapping counts as an empty
list. The function commits once. On `IntegrityError` the caller rolls back and calls it once more
([research D8](../research.md#d8--reconciliation-generalised-to-three-lists)).

**Behaviour matrix** (each case on SQLite and PostgreSQL; `A`/`T`/`S` = administrator, teacher
and student lists):

| # | Before | Lists | After | Counts |
|---|---|---|---|---|
| S1 | empty database | `A={a}`, `T={t}`, `S={a,s}` | `a` active {A,S}; `t` active {T}; `s` active {S} | created 3, roles_added 4 |
| S2 | state after S1 | same | nothing written; `updated_at` untouched; no session deleted | unchanged 3, all else 0 (FR-006, SC-007) |
| S3 | `a` {A,S} with 2 sessions | `A={a}`, `S={}` | `a` {A}; **both sessions deleted**; codes kept | roles_removed 1 (FR-005, US2-4) |
| S4 | `t` {T} with 1 session | `T={t}`, `S={t}` | `t` {T,S}; **session kept** | roles_added 1 (US2-6) |
| S5 | `s` {S} with session and code | `s` on no list | `s` inactive, no roles, no sessions, no codes, row still present | deactivated 1, roles_removed 1 (FR-005, FR-008, US2-5) |
| S6 | `s` inactive | `S={s}` | `s` active {S} | reactivated 1, roles_added 1 (US2-7) |
| S7 | — | `A={" X@Ex.com "}` vs `S={"x@ex.com"}` after normalisation | one user `x@ex.com` {A,S} | created 1, roles_added 2 (US2-2, edge case) |
| S8 | pre-milestone admin `a` (role row from the migration) | `A={a}` | unchanged | unchanged 1 |
| S9 | another instance inserts the same new user first | — | first call raises `IntegrityError`; the retry reaches the S1 end state | (retry's counts) |
| S10 | two instances start concurrently (PostgreSQL) | same lists | one user per address, one row per role, no error | — (edge case) |
| S11 | any | all three lists empty | every user inactive, no role rows | — |

The startup log line: `Users reconciled: <c> created, <r> reactivated, <d> deactivated, <ra> roles
added, <rr> roles removed, <u> unchanged`. It contains no address (FR-007, SC-008).

## `app/services/sessions.py`

```python
@dataclass(frozen=True)
class SessionIdentity:
    user: User
    roles: tuple[Role, ...]          # non-empty, fixed order
    current_role: Role | None

def create_session(
    session: Session, user: User, current_role: Role | None, now: datetime | None = None
) -> str:
    """Insert a session with this current role; return the plain token. Commits."""

def start_session(session: Session, user: User, now: datetime | None = None) -> tuple[str, Role | None]:
    """What the code check calls: the token and the initial current role, which is the single
    role held, or None when several roles are held (FR-012, FR-013)."""

def get_session_identity(
    session: Session, token: str, now: datetime | None = None
) -> SessionIdentity | None: ...

def set_current_role(session: Session, token: str, role: Role) -> None:
    """Make `role` current for this session only. The caller has already checked that the role
    is held. Commits."""

def delete_session(session: Session, token: str) -> None:  # unchanged
```

`get_session_user` is **replaced** by `get_session_identity`. It runs one query (`sessions` ⋈
`users` ⋈ `user_roles`, by token hash, unexpired, active user), then:

| # | Stored state | Result | Side effect |
|---|---|---|---|
| G1 | unknown or expired token, inactive user | `None` | — |
| G2 | active user holding no roles (invariant broken) | `None` | — |
| G3 | `current_role` NULL, one role held | identity with that role | **writes** `current_role` (pre-milestone upgrade, SC-010) |
| G4 | `current_role` NULL, several roles held | identity, `current_role=None` | — |
| G5 | `current_role` held | identity with it | — |
| G6 | `current_role` not held, or not a `Role` value | `None` | **deletes this session row** (FR-017) |

## `app/core/auth.py`

```python
PUBLIC_ROUTES: frozenset[tuple[str, str]]          # unchanged, five entries
ROLE_CHOICE_ROUTES: frozenset[tuple[str, str]] = frozenset({("GET", "/role"), ("POST", "/role")})

def allow_roles(*roles: Role) -> Callable[[F], F]:
    """Mark an endpoint with the non-empty set of roles that may open it. Raises ValueError when
    called with no roles. Returns the function unchanged, so it may sit above or below the route
    decorator."""

def declared_roles(endpoint: Callable[..., Any]) -> frozenset[Role] | None:
    """The marker, or None. Used by resolve_access and by the route sweep."""

def resolve_access(request: Request) -> None:
    """The decision order of contracts/http-routes.md#access-rule-applies-to-every-route."""

class LoginRequired(Exception): ...          # unchanged
class RoleChoiceRequired(Exception):         # 303 to `location` (/role?next=…)
    location: str
class AccessDenied(Exception):               # 403 access denied page
    current_role: Role
class CrossSiteRequest(Exception): ...       # 403 refused page

CurrentUser = Annotated[User | None, Depends(get_current_user)]          # unchanged
CurrentRole = Annotated[Role | None, Depends(get_current_role)]          # new
```

`app.main` registers one exception handler per exception. `RoleChoiceRequired` → 303. Both 403
exceptions → `pages/error.html`.

## `app/core/security.py`

```python
AUTH_PATHS = frozenset({"/login", "/login/code", "/logout", "/role"})   # + "/role"

def safe_next_path(value: str | None) -> str: ...      # unchanged rules; now also refuses /role

def is_cross_site(method: str, headers: Mapping[str, str]) -> bool:
    """True when an unsafe-method request must be refused (research D7). Header names are
    case-insensitive (Starlette `Headers`)."""
```

**`is_cross_site` table** (unit-tested):

| Method | `Sec-Fetch-Site` | `Origin` | `Host` | Result |
|---|---|---|---|---|
| `GET`/`HEAD`/`OPTIONS` | `cross-site` | `https://evil.example` | `app.test` | `False` |
| `POST` | `same-origin` | — | `app.test` | `False` |
| `POST` | `none` | — | `app.test` | `False` |
| `POST` | `same-site` | — | `app.test` | `True` |
| `POST` | `cross-site` | `https://app.test` | `app.test` | `True` (the header wins) |
| `POST` | — | `https://app.test` | `app.test` | `False` |
| `POST` | — | `http://app.test:8000` | `app.test:8000` | `False` |
| `POST` | — | `https://evil.example` | `app.test` | `True` |
| `POST` | — | `null` | `app.test` | `True` |
| `POST` | — | — | `app.test` | `False` |
| `PUT`/`PATCH`/`DELETE` | as `POST` | | | as `POST` |

## `app/routers/areas.py`

```python
@dataclass(frozen=True)
class Area:
    path: str
    title: str
    roles: frozenset[Role]

ADMIN_AREA = Area("/admin", "Administrator area", frozenset({Role.ADMIN}))
TEACHER_AREA = Area("/teacher", "Teacher area", frozenset({Role.TEACHER}))
STUDENT_AREA = Area("/student", "Student area", frozenset({Role.STUDENT}))
STAFF_AREA = Area("/staff", "Staff area", frozenset({Role.ADMIN, Role.TEACHER}))
AREAS = (ADMIN_AREA, TEACHER_AREA, STUDENT_AREA, STAFF_AREA)

def areas_for(role: Role) -> list[Area]:
    """The areas `role` may open, in AREAS order; used by the home page."""
```

Each handler is `@router.get(AREA.path)` + `@allow_roles(*AREA.roles)`.

## `app/routers/roles.py`

`GET /role` and `POST /role`, as in [http-routes.md](./http-routes.md). These are thin handlers
that read `request.state`, call `set_current_role`, and render or redirect.

## Test-only support (`tests/conftest.py`)

```python
AUTO = object()

def sign_in_directly(test_client, email: str, current_role: Role | None | object = AUTO) -> str:
    """Create a session for the active user `email` directly in the database and set the signed
    cookie. AUTO = start_session's rule; a Role or None overrides it. Test-only (FR-041)."""

@pytest.fixture
def client_as(client) -> Callable[..., TestClient]: ...   # factory: client_as(email, current_role=AUTO)

@pytest.fixture
def admin_client(client_as) -> TestClient: ...            # unchanged meaning
```
