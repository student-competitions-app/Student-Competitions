"""Downloading a started competition's questions and a subject's study materials (milestone 12.10).

See specs/012.10-questions-study-materials/contracts/http-routes.md §2–§3 and research R2, R6. Two
thin handlers: each looks up what the file shows, makes it (or takes it from memory) and hands it
out with `app.routers.downloads.pdf_download`, so the teacher stays on the Competitions tab.

**Every teacher downloads**, with Read or Write access, with or without **Can manage
competitions**, whatever institutions the teams belong to (FR-006, FR-021). The setting is never
read. Administrators and students get "access denied" before any id is read (`@allow_roles`).

**Download questions** (`/teacher/competitions/{id}/questions-file?subject=`): a started
competition's question texts for the teams. It is not under `/questions`, which only teachers with
the setting open (research R1, R2). The order of checks follows **Download results**: the role; the
subject, an offered one ("Subject not found", 404); the competition, visible in that subject and
**In progress**, **Finished** or **Published** ("Competition not found", 404, for an Upcoming or
Cancelled one too, and for an In progress one of a deactivated subject, which is hidden). The
file is made at every download and never stored or kept (FR-018), so a competition cancelled
while In progress answers 404 at once and a renamed subject shows.

**Download study materials** (`/teacher/competitions/study-materials?subject=`): the subject's bank
for the students. The order of checks: the role; the subject, which must exist and be active, else
404 with the Questions tab's "Subject not found" text, on the Competitions tab's page (FR-023),
whatever the memory holds. The file comes from the application's `StudyMaterialsCache`, which gives
the kept file only while what it shows has not changed (FR-032–FR-037).

Opening either changes nothing and logs nothing.
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.core.auth import allow_roles
from app.core.db import SessionDep
from app.core.i18n import Language
from app.models import Role
from app.routers import teacher_questions
from app.routers.downloads import pdf_download
from app.routers.teacher_competitions import (
    COMPETITION_NOT_FOUND,
    SUBJECT_NOT_FOUND,
    find_competition,
    not_found,
    offered_subject,
    parse_id,
)
from app.services import question_files_pdf
from app.services.competitions import CompetitionStatus, offered_subjects
from app.services.question_files import (
    StudyMaterialsCache,
    questions_file_name,
    questions_sheet,
    study_materials,
    study_materials_file_name,
)
from app.services.questions import SubjectUnavailable, get_active_subject

router = APIRouter(prefix="/teacher/competitions")

STARTED = frozenset(
    {CompetitionStatus.IN_PROGRESS, CompetitionStatus.FINISHED, CompetitionStatus.PUBLISHED}
)
"""The statuses whose questions every teacher downloads (FR-006, FR-007)."""


@router.get("/{competition_id:int}/questions-file", response_class=Response)
@allow_roles(Role.TEACHER)
def download_questions(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
) -> Response:
    """The question texts of a started competition in the current site language, made now."""
    selected = offered_subject(offered_subjects(session), subject)
    if selected is None:
        return not_found(request, SUBJECT_NOT_FOUND)
    competition = find_competition(session, competition_id, selected)
    if competition is None or competition.status not in STARTED:
        return not_found(request, COMPETITION_NOT_FOUND)
    language: Language = request.state.language
    sheet = questions_sheet(session, competition, selected)
    content = question_files_pdf.render_questions_pdf(sheet, language)
    return pdf_download(content, questions_file_name(sheet, language))


@router.get("/study-materials", response_class=Response)
@allow_roles(Role.TEACHER)
def download_study_materials(
    request: Request,
    session: SessionDep,
    subject: str | None = Query(None),
) -> Response:
    """The study materials of an active subject in the current site language: the kept file while
    nothing it shows has changed, a new one otherwise."""
    subject_id = parse_id(subject)
    if subject_id is None:
        return not_found(request, teacher_questions.SUBJECT_NOT_FOUND)
    try:
        found = get_active_subject(session, subject_id)
    except SubjectUnavailable:
        return not_found(request, teacher_questions.SUBJECT_NOT_FOUND)
    assert found.id is not None
    language: Language = request.state.language
    materials = study_materials(session, found)
    kept: StudyMaterialsCache = request.app.state.study_materials
    content = kept.file_for(found.id, language, materials)
    return pdf_download(content, study_materials_file_name(materials, language))
