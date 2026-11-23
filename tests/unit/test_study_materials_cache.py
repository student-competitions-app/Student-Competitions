"""The study materials kept in memory: given again only for equal materials, made once for
simultaneous requests, one entry per subject and language (milestone 12.10).

See specs/012.10-questions-study-materials/data-model.md §5, contracts/services.md §3 and research
R6. The renderer is replaced by a fake that counts its calls, so these cases need no database and
no PDF.
"""

import threading
import time
from datetime import date

import pytest

from app.core.i18n import Language
from app.services import question_files_pdf
from app.services.question_files import StudyMaterials, StudyMaterialsCache

TODAY = date(2026, 11, 23)


def materials(*entries: tuple[str, str], name: str = "History") -> StudyMaterials:
    return StudyMaterials(subject_name=name, downloaded_on=TODAY, entries=entries)


@pytest.fixture
def made(monkeypatch: pytest.MonkeyPatch) -> list[tuple[StudyMaterials, Language]]:
    """Every file made, as `(materials, language)`; the fake file names what it was made from."""
    calls: list[tuple[StudyMaterials, Language]] = []

    def fake(value: StudyMaterials, language: Language) -> bytes:
        calls.append((value, language))
        return f"{len(calls)}:{value.entries!r}:{language.value}".encode()

    monkeypatch.setattr(question_files_pdf, "render_study_materials_pdf", fake)
    return calls


def test_equal_materials_give_the_kept_file(made: list[object]) -> None:
    """FR-033: a fresh but equal value is enough; nothing is made again."""
    cache = StudyMaterialsCache()
    first = cache.file_for(1, Language.UK, materials(("Q?", "A.")))
    second = cache.file_for(1, Language.UK, materials(("Q?", "A.")))
    assert first == second
    assert len(made) == 1


def test_different_materials_make_a_new_file_that_replaces_the_old(made: list[object]) -> None:
    """FR-032, FR-033: only the newest file per subject and language is kept."""
    cache = StudyMaterialsCache()
    old, new = materials(("Q?", "A.")), materials(("Q?", "B."))
    cache.file_for(1, Language.UK, old)
    assert cache.file_for(1, Language.UK, new) != cache.file_for(1, Language.UK, old)
    assert len(made) == 3


BASE = materials(("Q?", "A."), ("R?", "B."))


@pytest.mark.parametrize(
    "changed",
    [
        materials(("Q?", "A."), ("R?", "B."), ("S?", "C.")),
        materials(("Q?", "A.")),
        materials(("Q?", "A."), ("R?", "Better.")),
        materials(("R?", "B."), ("Q?", "A.")),
        materials(("Q?", "A."), ("R?", "B."), name="World history"),
        StudyMaterials("History", date(2026, 11, 24), (("Q?", "A."), ("R?", "B."))),
    ],
    ids=["added", "removed", "edited", "reordered", "renamed", "next-day"],
)
def test_any_difference_is_a_different_value(changed: StudyMaterials) -> None:
    """Research R6: every change a download can read makes the value unequal; an equal one is
    equal."""
    assert changed != BASE
    assert materials(("Q?", "A."), ("R?", "B.")) == BASE


def test_each_language_and_subject_is_kept_on_its_own(made: list[object]) -> None:
    cache = StudyMaterialsCache()
    value = materials(("Q?", "A."))
    for key in ((1, Language.UK), (1, Language.EN), (2, Language.UK)):
        cache.file_for(*key, value)
    for key in ((1, Language.UK), (1, Language.EN), (2, Language.UK)):
        cache.file_for(*key, value)
    assert len(made) == 3


def test_two_requests_at_once_make_the_file_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-036: the second request waits on the key's lock, then takes the kept file. The fake
    waits on an event the test sets once the second thread is queued; a two-party barrier would
    deadlock, since the second thread never enters the renderer."""
    calls: list[StudyMaterials] = []
    entered, release = threading.Event(), threading.Event()

    def slow(value: StudyMaterials, language: Language) -> bytes:
        calls.append(value)
        entered.set()
        assert release.wait(10)
        return b"file"

    monkeypatch.setattr(question_files_pdf, "render_study_materials_pdf", slow)
    cache = StudyMaterialsCache()
    value = materials(("Q?", "A."))
    results: list[bytes] = []
    threads = [
        threading.Thread(target=lambda: results.append(cache.file_for(1, Language.UK, value)))
        for _ in range(2)
    ]
    threads[0].start()
    assert entered.wait(10)
    threads[1].start()
    time.sleep(0.2)
    release.set()
    for thread in threads:
        thread.join(10)
    assert len(calls) == 1
    assert results == [b"file", b"file"]


def test_other_keys_are_not_blocked_by_a_file_being_made(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each (subject, language) has its own lock: one subject's slow file holds no other."""
    entered, release = threading.Event(), threading.Event()

    def render(value: StudyMaterials, language: Language) -> bytes:
        if value.subject_name == "Slow":
            entered.set()
            assert release.wait(10)
        return value.subject_name.encode()

    monkeypatch.setattr(question_files_pdf, "render_study_materials_pdf", render)
    cache = StudyMaterialsCache()
    slow = threading.Thread(target=lambda: cache.file_for(1, Language.UK, materials(name="Slow")))
    slow.start()
    assert entered.wait(10)
    assert cache.file_for(2, Language.UK, materials(name="Quick")) == b"Quick"
    release.set()
    slow.join(10)
