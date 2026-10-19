"""Published consent texts never change: each version's SHA-256 is pinned here.

See specs/008-teacher-management-consent/research.md#d7. The texts live in the migrations, as
`<ROLE>_CONSENT_TEXT_V<n>` constants, and the migrations are the single source of truth: this
test reads them from the revision modules, as the `sample_questions` fixture does. Publishing a
new version means a new migration with a new constant, and a new pin below.
"""

import hashlib
import re

from alembic.script import ScriptDirectory

from app.core.migrations import alembic_config

PUBLISHED = {
    ("teacher", 1): "e1f6621d7c569720cc1571325528eee4b755b36248e2b36621639311a79b9950",
    ("student", 1): "0a518ef06fe972985ec55b131ceac238cd61c755404f47a7acb6dab758f06040",
}
"""`(role, version)` → SHA-256 of the published text."""

CONSTANT = re.compile(r"^([A-Z]+)_CONSENT_TEXT_V([0-9]+)$")

APPEND_ONLY = (
    "published consent texts are append-only; add a new version in a new migration "
    "(and pin it here)"
)


def published_texts() -> dict[tuple[str, int], str]:
    found: dict[tuple[str, int], str] = {}
    for revision in ScriptDirectory.from_config(alembic_config()).walk_revisions():
        for name, value in vars(revision.module).items():
            match = CONSTANT.match(name)
            if match is not None and isinstance(value, str):
                key = (match.group(1).lower(), int(match.group(2)))
                assert key not in found, f"{name} is defined in two migrations"
                found[key] = value
    return found


def test_every_published_text_is_pinned_and_unchanged() -> None:
    texts = published_texts()
    assert set(texts) == set(PUBLISHED), APPEND_ONLY
    for key, text in texts.items():
        assert hashlib.sha256(text.encode()).hexdigest() == PUBLISHED[key], f"{key}: {APPEND_ONLY}"


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
    them, the email service, and how to withdraw."""
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
    ):
        assert topic in text


def test_the_student_text_names_no_institution_or_class() -> None:
    """FR-039: a fixed text, the same for every institution and class, with no placeholder."""
    text = published_texts()[("student", 1)]
    assert "Kyiv" not in text
    assert "{" not in text
    assert "}" not in text
