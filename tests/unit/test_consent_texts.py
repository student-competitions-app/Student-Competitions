"""Published consent texts never change: each version's SHA-256 is pinned here.

See specs/008-teacher-management-consent/research.md#d7. The texts live in the migrations, as
`<ROLE>_CONSENT_TEXT_V<n>` constants, and the migrations are the single source of truth: this
test reads them from the revision modules rather than keeping a copy that could drift. Publishing
a new version means a new migration with a new constant, and a new pin below.

**Rewrites in place** (milestone 11.1 FR-015; milestone 12.5 FR-048, research R11): a later
migration may define `<ROLE>_CONSENT_TEXT_V<n>_REWRITE_<k>`, which replaces that version's wording
in place; the teams migration's unnumbered `…_REWRITE` is rewrite 1. The published text of a
version is its highest rewrite, pinned in `PUBLISHED`; every earlier wording is still pinned, in
`SUPERSEDED`, so no migration that holds one can change unnoticed. `REWRITES_ALLOWED` caps the
rewrites of each version: student version 1 twice (teams, then bilingual), teacher version 1 once
(bilingual), and no other version ever. Milestone 12.5's was the last rewrite in place (FR-051).
"""

import hashlib
import re
from types import ModuleType

from alembic.script import ScriptDirectory

from app.core.migrations import alembic_config

PUBLISHED = {
    ("teacher", 1): "64b785dce3356943b2e9c8fa2597fc1c3edc21d3414dc89fb87d0ae295477725",
    ("student", 1): "85fdcf5e8d6385651c49e22c08a8078a3fd45479987132677ad4df6a9ba5b56b",
}
"""`(role, version)` → SHA-256 of the published text: its highest rewrite where there is one."""

SUPERSEDED = {
    ("teacher", 1): ["e1f6621d7c569720cc1571325528eee4b755b36248e2b36621639311a79b9950"],
    ("student", 1): [
        "0a518ef06fe972985ec55b131ceac238cd61c755404f47a7acb6dab758f06040",
        "00701e781cb77a6930a13fe849cb127e3c6f91f02a87429a85403c9149626e5c",
    ],
}
"""`(role, version)` → SHA-256 of every earlier wording, oldest first: the original, then each
rewrite but the last."""

REWRITES_ALLOWED = {("student", 1): 2, ("teacher", 1): 1}
"""How many times each version may be rewritten in place; any other version, never."""

ORIGINAL = re.compile(r"^([A-Z]+)_CONSENT_TEXT_V([0-9]+)$")
REWRITE = re.compile(r"^([A-Z]+)_CONSENT_TEXT_V([0-9]+)_REWRITE(?:_([0-9]+))?$")

TEAMS_REVISION = "09cbcbe472be"
LOCALISATION_REVISION = "7110bec350d2"

PREVAILS_EN = "If the Ukrainian and English wordings differ, the Ukrainian wording prevails."
PREVAILS_UK = "Якщо українська та англійська редакції відрізняються, переважає українська редакція."

APPEND_ONLY = (
    "published consent texts are append-only; add a new version in a new migration "
    "(and pin it here)"
)
NO_MORE_REWRITES = (
    "a consent text may be rewritten in place only as REWRITES_ALLOWED says (milestone 12.5 "
    "FR-051: the bilingual rewrite was the last); publish a new version instead"
)


def _modules() -> list[ModuleType]:
    return [r.module for r in ScriptDirectory.from_config(alembic_config()).walk_revisions()]


def original_texts() -> dict[tuple[str, int], str]:
    found: dict[tuple[str, int], str] = {}
    for module in _modules():
        for name, value in vars(module).items():
            match = ORIGINAL.match(name)
            if match is not None and isinstance(value, str):
                key = (match.group(1).lower(), int(match.group(2)))
                assert key not in found, f"{name} is defined in two migrations"
                found[key] = value
    return found


def rewritten_texts() -> dict[tuple[str, int], dict[int, str]]:
    """`(role, version)` → rewrite number → text; an unnumbered rewrite is number 1."""
    found: dict[tuple[str, int], dict[int, str]] = {}
    for module in _modules():
        for name, value in vars(module).items():
            match = REWRITE.match(name)
            if match is not None and isinstance(value, str):
                key = (match.group(1).lower(), int(match.group(2)))
                number = int(match.group(3) or 1)
                assert number not in found.get(key, {}), f"{name}: rewrite {number} twice"
                found.setdefault(key, {})[number] = value
    return found


def published_texts() -> dict[tuple[str, int], str]:
    """Each version's text as published now: its highest rewrite, else its original."""
    texts = dict(original_texts())
    for key, rewrites in rewritten_texts().items():
        texts[key] = rewrites[max(rewrites)]
    return texts


def superseded_texts() -> dict[tuple[str, int], list[str]]:
    """Each rewritten version's earlier wordings, oldest first."""
    originals = original_texts()
    return {
        key: [originals[key], *(rewrites[n] for n in sorted(rewrites)[:-1])]
        for key, rewrites in rewritten_texts().items()
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_every_rewrite_is_of_a_published_version_and_allowed() -> None:
    originals, rewrites = original_texts(), rewritten_texts()
    for key, numbered in rewrites.items():
        assert key in originals, f"{key}: a rewrite of a version that was never published"
        assert sorted(numbered) == list(range(1, len(numbered) + 1)), f"{key}: rewrites skip"
        assert len(numbered) <= REWRITES_ALLOWED.get(key, 0), f"{key}: {NO_MORE_REWRITES}"
    assert {key: len(numbered) for key, numbered in rewrites.items()} == REWRITES_ALLOWED


def test_every_published_text_is_pinned_and_unchanged() -> None:
    texts = published_texts()
    assert set(texts) == set(PUBLISHED), APPEND_ONLY
    for key, text in texts.items():
        assert _sha256(text) == PUBLISHED[key], f"{key}: {APPEND_ONLY}"


def test_every_superseded_wording_is_still_pinned() -> None:
    """The milestone 8 and 9 migrations keep the originals, the teams migration the student's
    rewrite 1; none of them can change."""
    superseded = superseded_texts()
    assert set(superseded) == set(SUPERSEDED), NO_MORE_REWRITES
    for key, texts in superseded.items():
        assert [_sha256(text) for text in texts] == SUPERSEDED[key], f"{key}: {APPEND_ONLY}"


def _migration(revision_id: str) -> ModuleType:
    revision = ScriptDirectory.from_config(alembic_config()).get_revision(revision_id)
    assert revision is not None
    return revision.module


def test_the_downgrades_restore_exactly_the_earlier_wordings() -> None:
    """The private copies the migrations write back on downgrade are the superseded texts."""
    teams = _migration(TEAMS_REVISION)
    assert _sha256(teams._STUDENT_CONSENT_TEXT_V1_ORIGINAL) == SUPERSEDED[("student", 1)][0]
    localisation = _migration(LOCALISATION_REVISION)
    assert _sha256(localisation._TEACHER_CONSENT_TEXT_V1_ORIGINAL) == SUPERSEDED[("teacher", 1)][0]
    assert _sha256(localisation._STUDENT_CONSENT_TEXT_V1_REWRITE_1) == SUPERSEDED[("student", 1)][1]


def english_part(text: str) -> str:
    """The paragraphs after the paragraph `English` (data-model §4)."""
    paragraphs = text.split("\n\n")
    return "\n\n".join(paragraphs[paragraphs.index("English") + 1 :])


def ukrainian_part(text: str) -> str:
    paragraphs = text.split("\n\n")
    assert paragraphs[0] == "Українською"
    return "\n\n".join(paragraphs[1 : paragraphs.index("English")])


def test_every_published_text_is_ukrainian_then_english() -> None:
    """FR-044, FR-045: both parts, each ending with the sentence that the Ukrainian prevails;
    the English part is the earlier wording, word for word, then that sentence."""
    for key, text in published_texts().items():
        assert ukrainian_part(text).endswith(PREVAILS_UK), key
        assert english_part(text).endswith(PREVAILS_EN), key
        earlier = superseded_texts()[key][-1]
        assert english_part(text) == earlier + "\n\n" + PREVAILS_EN, key


def test_the_teacher_text_covers_every_required_topic() -> None:
    """FR-036: what is stored, why, who sees it, the email service, and how to withdraw."""
    text = english_part(published_texts()[("teacher", 1)])
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
    text = english_part(published_texts()[("student", 1)])
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
