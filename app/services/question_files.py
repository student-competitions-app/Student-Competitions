"""A competition's questions file and a subject's study materials: what each is made from, their
names, and the study materials kept in memory (milestone 12.10).

See specs/012.10-questions-study-materials/data-model.md, contracts/services.md §3 and research
R5–R7.

- **The questions file** (FR-012–FR-019) holds the question texts of a started competition, in its
  order, for the teams. It is made at every download and never stored or kept: it holds about ten
  questions and is made in a moment, and the router checks the competition's status at every
  download. `QuestionsSheet` has no field for a reference answer, a bank number or the additional
  mark, so none of them can reach the file (constitution IV).
- **The study materials** (FR-025–FR-031) hold every question of a subject's bank with its
  reference answer, oldest first, for the students to learn. The additional and the deleted
  questions are left out in the query itself, for every teacher, a teacher with Can manage
  competitions included, and the bank number is never read, so the gaps cannot be seen.
- **Kept in memory, never stale** (FR-032–FR-037, research R6): `StudyMaterialsCache` keeps the last
  file per subject and language together with the `StudyMaterials` it was made from, and gives it
  again only when what a download has just read equals them. Nothing else knows about it: every
  change, made by the application or straight in the database, shows as a difference in what is
  read.
- **The clock** is `app.services.competitions.utc_now`, read through that module, so tests that
  move the 12.1 clock move this one too.

The imports run one way: `question_files` → `question_files_pdf`, `file_names`,
`competition_entries`, `competitions`. Only the routers and the sample script import this module.
Nothing here logs.
"""

import threading
from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, col, select

from app.core.i18n import Language, _, use_language
from app.core.time_zone import KYIV
from app.models import Question, Subject
from app.services import competitions, question_files_pdf
from app.services.competition_entries import question_copies
from app.services.competitions import CompetitionView
from app.services.file_names import clean_file_stem

# ---------------------------------------------------------------------------------------------
# What the files are made from (data-model.md §3, §4)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionsSheet:
    """What a competition's questions file shows. It has no field for a bank number, a mark or a
    reference answer, so none can reach the file (FR-015)."""

    competition_name: str
    subject_name: str
    """The subject's name at the download, so a rename shows (FR-018)."""
    starts_at: datetime
    """Aware, UTC; shown in Kyiv time, labelled; also the PDF creation date."""
    texts: tuple[str, ...]
    """The competition's copies' texts in the competition's order; may be empty."""


@dataclass(frozen=True)
class StudyMaterials:
    """What a subject's study materials show. Two values are equal exactly when the file they make
    would show the same things, so a kept file is given again only for an equal value (research
    R6). The language is not a field: it is part of the key and an argument of the renderer."""

    subject_name: str
    downloaded_on: date
    """Today in Kyiv; shown as "Downloaded: …"; its Kyiv midnight is the PDF creation date."""
    entries: tuple[tuple[str, str], ...]
    """`(text, reference_answer)` per question that is neither additional nor deleted, oldest
    first; may be empty."""


def questions_sheet(
    session: Session, competition: CompetitionView, subject: Subject
) -> QuestionsSheet:
    """The questions file's content: every copy the competition holds, additional ones and copies
    of questions deleted from the bank included, in its order (FR-014, FR-016). The caller has
    checked that the competition has started and is not cancelled."""
    return QuestionsSheet(
        competition_name=competition.name,
        subject_name=subject.name,
        starts_at=competition.starts_at,
        texts=tuple(copy.text for copy in question_copies(session, competition.id)),
    )


def study_materials(session: Session, subject: Subject) -> StudyMaterials:
    """The study materials' content, read now: one query over the subject's bank, leaving out the
    additional and the deleted questions, oldest first, never selecting the bank number (FR-027,
    FR-028). The caller has checked that the subject is active."""
    rows = session.exec(
        select(Question.text, Question.reference_answer)
        .where(
            Question.subject_id == subject.id,
            col(Question.deleted_at).is_(None),
            col(Question.is_additional).is_(False),
        )
        .order_by(col(Question.id))
    ).all()
    return StudyMaterials(
        subject_name=subject.name,
        downloaded_on=competitions.utc_now().astimezone(KYIV).date(),
        entries=tuple((text, answer) for text, answer in rows),
    )


# ---------------------------------------------------------------------------------------------
# File names (research R7)
# ---------------------------------------------------------------------------------------------


def questions_file_name(sheet: QuestionsSheet, language: Language) -> str:
    """ "<name> <YYYY-MM-DD> questions.pdf" in `language` («… питання.pdf»): the competition's
    name and its start date in Kyiv time (FR-019)."""
    with use_language(language):
        stem = _(
            "%(name)s %(date)s questions",
            name=clean_file_stem(sheet.competition_name, "questions"),
            date=f"{sheet.starts_at.astimezone(KYIV):%Y-%m-%d}",
        )
        return f"{clean_file_stem(str(stem), 'questions')}.pdf"


def study_materials_file_name(materials: StudyMaterials, language: Language) -> str:
    """ "<subject> <YYYY-MM-DD> study materials.pdf" in `language` («… навчальні
    матеріали.pdf»): the subject's name and the date of the download in Kyiv time (FR-031)."""
    with use_language(language):
        stem = _(
            "%(subject)s %(date)s study materials",
            subject=clean_file_stem(materials.subject_name, "study materials"),
            date=f"{materials.downloaded_on:%Y-%m-%d}",
        )
        return f"{clean_file_stem(str(stem), 'study materials')}.pdf"


# ---------------------------------------------------------------------------------------------
# The study materials kept in memory (data-model.md §5, research R6)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Kept:
    materials: StudyMaterials
    """Exactly what `content` was made from."""
    content: bytes


class StudyMaterialsCache:
    """The last study materials file made for each subject and language, kept with exactly what it
    was made from (FR-032–FR-037).

    **Never stale**: `file_for` gives the kept bytes only when the materials the request has just
    read equal those the file was made from; otherwise it makes the file from what was just read
    and keeps it in place of the old one. Nothing removes a kept file when the bank changes, and
    nothing else knows about it: a question added, edited, deleted, marked or unmarked, a renamed
    subject, a change made straight in the database and a new day each show as a difference in
    what is read. A file made while the bank was changing is kept with what it was made from, so
    it is never given after the change.

    **Once for simultaneous downloads**: each (subject, language) has its own lock. The first
    request makes the file; the others wait, then find it kept and matching. Requests whose
    materials differ each make their own file in turn, which is correct.

    **Bounded and fresh at every start**: one entry per subject and language, and one instance per
    running application, made in `lifespan`, so a restart, a deployment or a wake from sleep starts
    empty and the first download makes the file with the current release's labels and design.
    The server runs one process with a thread pool (research R6): process memory and `threading`
    locks are enough, and more processes would each keep their own files, still correct.

    Nothing here logs.
    """

    def __init__(self) -> None:
        self._kept: dict[tuple[int, Language], _Kept] = {}
        self._locks: dict[tuple[int, Language], threading.Lock] = {}
        self._guard = threading.Lock()

    def file_for(self, subject_id: int, language: Language, materials: StudyMaterials) -> bytes:
        """The study materials of `materials` in `language`: kept if they match, made otherwise.
        The caller has checked that the subject is active and read `materials` just now."""
        key = (subject_id, language)
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            kept = self._kept.get(key)
            if kept is not None and kept.materials == materials:
                return kept.content
            # Through the module, so the tests can count the files made.
            content = question_files_pdf.render_study_materials_pdf(materials, language)
            self._kept[key] = _Kept(materials, content)
            return content
