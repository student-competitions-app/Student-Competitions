# Contract: Services (Milestone 11.1)

Decisions: [research.md](../research.md) R2–R9, R11, R14.

**Conventions**, unchanged from milestones 7 and 9 (`regions`, `classes`):

- **Values** are passed as submitted, and the services clean them.
- **Uniqueness** is guaranteed by the database constraint, not by the lookup before a write.
- **One commit** per successful change, and a rollback on every refusal, so no lock outlives it.
- **Logging**: one log line per successful change, with ids and counts only; a no-op logs nothing.
- **Reach**: every function that acts for a teacher checks the teacher's reach in its own
  transaction, with `lock=True` for a change.

## `app/services/teacher_access.py` (added)

```python
def reach_team(
    session: Session,
    teacher_id: int,
    team_id: int,
    *,
    institution_id: int | None = None,
    write: bool = False,
    lock: bool = False,
) -> tuple[ReachableInstitution, Team]:
    """The live team, if its institution is reachable and, when given, is `institution_id`.

    `NotReachable` for an unknown team, a deleted team (`deleted_at` set), a team of another
    institution than `institution_id`, or an institution the teacher may not reach.
    `WriteRequired` when `write` is set and the level is Read.

    With `lock`, the team row is read `FOR UPDATE` (refreshed) first, then the link, institution
    and region `FOR SHARE` through `reach_institution`. That is the first lock of every team
    change (research R5). Rolls back before raising when it took a lock.
    """
```

The module docstring gains a fourth definition: **reachable team** means a live team of a reachable
institution.

## `app/services/teams.py` (new)

```python
MAX_MEMBERS = 50

class DuplicateTeamName(ValueError):
    """A live team in any institution already has this name, ignoring case."""
    # message = f"A team named “{entered_name}” already exists."  (the entered name, R2)

class AlreadyMember(ValueError):
    """The student is already in the team; nothing was stored."""
    # carries team_id, user_id

class TeamFull(ValueError):
    """The team already holds MAX_MEMBERS memberships, blocked ones included; nothing was stored."""

@dataclass(frozen=True)
class TeamView:
    id: int
    institution_id: int
    name: str

@dataclass(frozen=True)
class MemberRow:
    user_id: int
    first_name: str
    last_name: str
    class_label: str        # ClassView.label: "KN-21 · year 2"

@dataclass(frozen=True)
class StudentTeam:
    name: str
    is_deleted: bool
```

### Lookups (no reach check: the router checks it first)

| Function | Returns |
|---|---|
| `list_teams(session, institution_id) -> list[TeamView]` | the institution's **live** teams, sorted by `name_key`, ties by id (FR-028) |
| `list_active_members(session, team_id) -> list[MemberRow]` | the members whose class, institution and region are active, by last name, then first name, case-folded, ties by id (FR-035, FR-010, R6) |
| `count_members(session, team_id) -> int` | all memberships, blocked included: the limit (FR-004) |
| `member_ids(session, team_id) -> set[int]` | every member's user id, blocked included: "In this team" (FR-039) |
| `is_full(session, team_id) -> bool` | `count_members(...) >= MAX_MEMBERS` (FR-041) |
| `list_student_teams(session, user_id) -> list[StudentTeam]` | every team the person belongs to, deleted included, by `name_key`, ties by id (FR-013, R14) |

### Changes

```python
def create_team(session, teacher_id: int, institution_id: int, raw_name: str) -> TeamView:
```

1. `reach_institution(..., write=True, lock=True)`.
2. `clean_name`, rolling back and re-raising `InvalidName` on a refusal.
3. A live team with the same `name_key` anywhere gives `DuplicateTeamName(cleaned)`.
4. Insert and commit. An `IntegrityError` (the partial index, in a race) is rolled back and gives
   `DuplicateTeamName(cleaned)`.

It logs `Team created: id=%d institution_id=%d`. Raises `NotReachable`, `WriteRequired`,
`InvalidName` or `DuplicateTeamName`.

```python
def rename_team(session, teacher_id: int, team_id: int, raw_name: str) -> TeamView:
```

1. `reach_team(..., write=True, lock=True)`, then `clean_name`.
2. **Duplicate**: another live team with the key gives `DuplicateTeamName`; the team itself does not
   count (US3-5).
3. **Unchanged**: if the name and key are unchanged, it rolls back and returns, writing nothing.
4. **Otherwise**: it sets `name`, `name_key` and `updated_at`, and commits. An `IntegrityError` is
   handled as in `create_team`.

It logs `Team renamed: id=%d`.

```python
def delete_team(session, teacher_id: int, team_id: int) -> TeamView:
```

`reach_team(..., write=True, lock=True)`, then sets `deleted_at = utc_now()` and commits.

- **Unchanged**: the name, the institution, `updated_at` and every membership (FR-007, FR-009).
- **A second deletion** is `NotReachable`: a deleted team is not reachable.

It logs `Team deleted: id=%d members=%d`, counting every membership row. It returns the view for the
redirect.

```python
def add_member(session, teacher_id: int, team_id: int, raw_user_id: str) -> MemberRow:
```

Locks in the order of research R5.

1. `reach_team(..., write=True, lock=True)`: the team row `FOR UPDATE`.
2. **The id**: `raw_user_id` must be ASCII digits ≤ `MAX_ID`, else `NotReachable`.
3. `reach_student(..., write=True, lock=True)`: the user `FOR UPDATE`, then the class and the
   institution rows `FOR SHARE`. This refuses a person without the student role, a person without
   an enrolment, and a blocked student (FR-011).
4. **The institution**: the student's class must be in `team.institution_id`, else `NotReachable`
   (FR-003).
5. **An existing membership** gives `AlreadyMember`.
6. **The limit**: `count_members(...) >= MAX_MEMBERS` gives `TeamFull`, blocked members included
   (FR-004).
7. **Insert** `TeamMembership(created_at=utc_now())` and commit. An `IntegrityError` (the primary
   key, in a race) is rolled back and gives `AlreadyMember`.

It logs `Team member added: team_id=%d user_id=%d`. It returns the member's row for the notice.
Nothing else about the student is written: class, enrolment, role, other teams and sessions are
unchanged (FR-005).

```python
def get_member(session, teacher_id: int, team_id: int, user_id: int) -> tuple[ReachableInstitution, TeamView, MemberRow]:
```

The remove confirmation's lookup, with no lock: steps 1, 3 and 4 of `add_member` with
`write=True`, and the membership must exist. Raises `NotReachable` or `WriteRequired`.

```python
def remove_member(session, teacher_id: int, team_id: int, user_id: int) -> None:
```

1. `reach_team(..., write=True, lock=True)`, then `reach_student(..., write=True, lock=True)`.
2. **The institution** check, as in `add_member`.
3. **The membership** must exist, else `NotReachable`.
4. Delete that one row and commit.

It logs `Team member removed: team_id=%d user_id=%d`. The student keeps their role, class,
enrolment, other teams and sessions (FR-006).

**For milestone 12** (stated in the module docstring): only a team that `reach_team` returns, that
is a live team, may be added to a competition. Its institution must be one the teacher is linked
to, with Read or Write, and the reach check already enforces that.

## `app/services/students.py` (changed)

`_StudentInvitation.revoke(session, user_id)` first deletes every `TeamMembership` of the user, then
the enrolment and the role, as today (research R7). This erases the memberships on removal,
withdrawal and data deletion, in deleted teams too, and keeps the teams (FR-014). The module
docstring and the `TeamMembership` docstring name this.

## `app/services/institutions.py` (changed)

`count_institution_uses` adds the count of `teams` rows with this `institution_id`, deleted ones
included (FR-017, research R8). It queries the `Team` model directly and does not import
`app.services.teams`. The docstring names teams among the uses. `delete_institution` is
unchanged: an `IntegrityError` is already reported as "in use".

## `app/routers/teacher_teams.py`: the notice helpers

```python
def seal_member_notice(settings: AuthSettings, team_id: int, user_id: int, outcome: str) -> str: ...
def member_notice(
    session: Session, settings: AuthSettings, token: str | None, team_id: int,
) -> tuple[str, str] | None:
    """(text, kind) for a valid, fresh token of this team whose student is a listed member;
    None for anything else (research R11)."""
```

## `app/routers/profile.py` (changed)

When the person holds the student role (`get_roles`, blocked or not), the context gains
`teams = list_student_teams(session, person.id)` (FR-013).

## `app/models/__init__.py` (changed)

It exports `Team` and `TeamMembership`, so `SQLModel.metadata` is complete for Alembic and the drift
test.
