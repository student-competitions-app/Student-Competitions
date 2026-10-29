"""Published consent texts never change: each version's SHA-256 is pinned here.

See specs/008-teacher-management-consent/research.md#d7. The texts live in the migrations, as
`<ROLE>_CONSENT_TEXT_V<n>` constants, and the migrations are the single source of truth: this
test reads them from the revision modules rather than keeping a copy that could drift. Publishing
a new version means a new migration with a new constant, and a new pin below.

**The one rewrite** (milestone 11.1 FR-015, specs/011.1-teacher-teams/research.md R9): a later
migration may define `<ROLE>_CONSENT_TEXT_V<n>_REWRITE`, which replaces that version's wording in
place. The published text of a version is then its rewrite, pinned in `PUBLISHED`, and the
original is still pinned, in `SUPERSEDED`, so the migration that holds it cannot change unnoticed
either. Only the versions in `REWRITES_ALLOWED` may be rewritten: the exception was granted once,
for student version 1, because no real users existed yet.
"""

import hashlib
import re
from types import ModuleType

from alembic.script import ScriptDirectory

from app.core.migrations import alembic_config

PUBLISHED = {
    ("teacher", 1): "e1f6621d7c569720cc1571325528eee4b755b36248e2b36621639311a79b9950",
    ("student", 1): "00701e781cb77a6930a13fe849cb127e3c6f91f02a87429a85403c9149626e5c",
}
"""`(role, version)` → SHA-256 of the published text: the rewrite where there is one."""

SUPERSEDED = {
    ("student", 1): "0a518ef06fe972985ec55b131ceac238cd61c755404f47a7acb6dab758f06040",
}
"""`(role, version)` → SHA-256 of an original wording that a rewrite replaced."""

REWRITES_ALLOWED = {("student", 1)}
"""The only versions that may be rewritten in place (milestone 11.1 FR-015)."""

ORIGINAL = re.compile(r"^([A-Z]+)_CONSENT_TEXT_V([0-9]+)$")
REWRITE = re.compile(r"^([A-Z]+)_CONSENT_TEXT_V([0-9]+)_REWRITE$")

TEAMS_REVISION = "09cbcbe472be"

APPEND_ONLY = (
    "published consent texts are append-only; add a new version in a new migration "
    "(and pin it here)"
)
ONE_TIME = (
    "a consent text may be rewritten in place only once, for student version 1 "
    "(milestone 11.1 FR-015); publish a new version instead"
)


def _modules() -> list[ModuleType]:
    return [r.module for r in ScriptDirectory.from_config(alembic_config()).walk_revisions()]


def _collect(pattern: re.Pattern[str]) -> dict[tuple[str, int], str]:
    found: dict[tuple[str, int], str] = {}
    for module in _modules():
        for name, value in vars(module).items():
            match = pattern.match(name)
            if match is not None and isinstance(value, str):
                key = (match.group(1).lower(), int(match.group(2)))
                assert key not in found, f"{name} is defined in two migrations"
                found[key] = value
    return found


def original_texts() -> dict[tuple[str, int], str]:
    return _collect(ORIGINAL)


def rewritten_texts() -> dict[tuple[str, int], str]:
    return _collect(REWRITE)


def published_texts() -> dict[tuple[str, int], str]:
    """Each version's text as published now: its rewrite when there is one, else its original."""
    return {**original_texts(), **rewritten_texts()}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_every_rewrite_is_of_a_published_version_and_allowed() -> None:
    originals, rewrites = original_texts(), rewritten_texts()
    for key in rewrites:
        assert key in originals, f"{key}: a rewrite of a version that was never published"
        assert key in REWRITES_ALLOWED, f"{key}: {ONE_TIME}"


def test_every_published_text_is_pinned_and_unchanged() -> None:
    texts = published_texts()
    assert set(texts) == set(PUBLISHED), APPEND_ONLY
    for key, text in texts.items():
        assert _sha256(text) == PUBLISHED[key], f"{key}: {APPEND_ONLY}"


def test_every_superseded_original_is_still_pinned() -> None:
    """The milestone 9 migration keeps the original student wording; it still cannot change."""
    originals, rewrites = original_texts(), rewritten_texts()
    assert set(rewrites) == set(SUPERSEDED), ONE_TIME
    for key in SUPERSEDED:
        assert _sha256(originals[key]) == SUPERSEDED[key], f"{key}: {APPEND_ONLY}"


def _teams_migration() -> ModuleType:
    revision = ScriptDirectory.from_config(alembic_config()).get_revision(TEAMS_REVISION)
    assert revision is not None
    return revision.module


def test_the_downgrade_restores_exactly_the_original() -> None:
    """The private copy the teams migration writes back on downgrade is the superseded text."""
    copy = _teams_migration()._STUDENT_CONSENT_TEXT_V1_ORIGINAL
    assert _sha256(copy) == SUPERSEDED[("student", 1)]


def test_the_teacher_text_covers_every_required_topic() -> None:
    """FR-036: what is stored, why, who sees it, the email service, and how to withdraw."""
    text = published_texts()[("teacher", 1)]
    for topic in (
        "email address",
        "first and last name",
        "access level",
        "create competitions",
        "so that",
        "administrators",
        "Resend",
        "Withdraw consent",
        "Delete my data",
    ):
        assert topic in text


def test_the_student_text_covers_every_required_topic() -> None:
    """Milestone 9 FR-039, research D13: the class and the year of study are stored, who sees
    them, the email service, and how to withdraw; milestone 11.1 FR-015: the team memberships
    too, and that withdrawal erases them."""
    text = published_texts()[("student", 1)]
    for topic in (
        "email address",
        "first and last name",
        "class",
        "year of study",
        "educational institution",
        "so that",
        "teachers",
        "Resend",
        "Withdraw consent",
        "Delete my data",
        "team memberships",
        "teams",
        "erased",
    ):
        assert topic in text


def test_the_student_text_names_no_institution_or_class() -> None:
    """FR-039: a fixed text, the same for every institution and class, with no placeholder."""
    text = published_texts()[("student", 1)]
    assert "Kyiv" not in text
    assert "{" not in text
    assert "}" not in text
