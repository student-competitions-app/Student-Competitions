"""The teacher's role details, and the institution picker's form values. Pure, no I/O.

See specs/008-teacher-management-consent/research.md#d11 and contracts/services.md
§schemas/teachers. The picker submits two repeated fields: `institution` (`<id>` for each picked
row) and `access` (`<id>:read` or `<id>:write` for every row, picked or not, because every row's
select is always submitted). Both are read as strings, never as integers, so a bad value
re-renders the form with a message instead of FastAPI's 422 JSON.

Whether an institution may be picked (exists, active, active region) is not checked here: the
router and the services check that against the database.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.models.teacher import AccessLevel

NONE_PICKED = "Pick at least one educational institution."
NOT_SELECTABLE = "This educational institution cannot be selected."
PICKED_TWICE = "Each educational institution can be picked only once."
BAD_LEVEL = "Choose Read or Write access for each educational institution."

MAX_ID = 2**31 - 1
"""The largest `integer` key: a larger id cannot exist, and PostgreSQL would refuse to compare
it."""


@dataclass(frozen=True)
class TeacherDetails:
    """What a teacher invitation grants, besides the role: the links and the setting."""

    institutions: Mapping[int, AccessLevel]
    """Never empty: institution id → access level."""
    can_create_competitions: bool


class InvalidChoice(ValueError):
    """The picker's values break a rule; `message` is ready to show in the form."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _institution_id(raw: str) -> int:
    value = raw.strip()
    if not value.isascii() or not value.isdigit() or int(value) > MAX_ID:
        raise InvalidChoice(NOT_SELECTABLE)
    return int(value)


def parse_institution_choices(
    institution: Sequence[str],
    access: Sequence[str],
    keep_level_for: Mapping[int, AccessLevel] | None = None,
) -> dict[int, AccessLevel]:
    """The picked institutions with their levels, or `InvalidChoice` with the first rule broken.

    `access` entries for ids that were not picked are ignored. For the ids in `keep_level_for`
    (already linked, but no longer selectable, so their level cannot change), any submitted level
    is ignored and the kept level is used.
    """
    keep_level_for = keep_level_for or {}
    if not institution:
        raise InvalidChoice(NONE_PICKED)
    picked: list[int] = []
    for raw in institution:
        institution_id = _institution_id(raw)
        if institution_id in picked:
            raise InvalidChoice(PICKED_TWICE)
        picked.append(institution_id)

    submitted: dict[int, set[str]] = {}
    for entry in access:
        raw_id, separator, level = entry.partition(":")
        if not separator or not raw_id.strip().isascii() or not raw_id.strip().isdigit():
            continue
        submitted.setdefault(int(raw_id.strip()), set()).add(level.strip())

    choices: dict[int, AccessLevel] = {}
    for institution_id in picked:
        if institution_id in keep_level_for:
            choices[institution_id] = keep_level_for[institution_id]
            continue
        levels = submitted.get(institution_id, set())
        if len(levels) != 1:
            raise InvalidChoice(BAD_LEVEL)
        [level] = levels
        if level not in {member.value for member in AccessLevel}:
            raise InvalidChoice(BAD_LEVEL)
        choices[institution_id] = AccessLevel(level)
    return choices
