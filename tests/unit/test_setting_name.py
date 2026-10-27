"""The setting is called "Can manage competitions" everywhere it is shown or set.

See specs/011-question-bank/spec.md US6, FR-009 and SC-006. The old name may survive only as the
legacy key of invitations sealed before milestone 11 (`LEGACY_SETTING_KEY` in
`app/services/teachers.py`, research R12). Migrations are frozen snapshots and out of scope; the
published consent text v1 lives in a migration too, so it is untouched (append-only).
"""

from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
OLD_NAMES = ("Can create competitions", "can_create_competitions")
LEGACY_KEY_LINE = 'LEGACY_SETTING_KEY = "can_create_competitions"'


def test_the_old_name_is_gone_from_the_application() -> None:
    offenders = []
    for path in sorted(APP.rglob("*")):
        if path.suffix not in (".py", ".html") or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.strip() == LEGACY_KEY_LINE:
                continue
            if any(name in line for name in OLD_NAMES):
                offenders.append(f"{path.relative_to(APP)}:{number}: {line.strip()}")
    assert not offenders, offenders


def test_the_legacy_key_is_declared_once() -> None:
    teachers = (APP / "services" / "teachers.py").read_text()
    assert teachers.count(LEGACY_KEY_LINE) == 1
