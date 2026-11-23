"""Downloading a competition's published results (milestone 12.8).

See specs/012.8-publishing-results/contracts/http-routes.md §3 and research R9. One thin handler:
it finds the competition and hands out the stored results file of the current site language,
exactly as it was made at publishing, so nothing is calculated again (constitution Principle VII).

**Every teacher downloads**: the published results are open information, like the results of a
school competition (FR-002), so the route needs the teacher role only: no **Can manage
competitions**, and no link to the teams' institutions. Administrators and students get "access
denied" before any id is read.

**Order of checks**: the role (`@allow_roles`); the subject ("Subject not found", 404); the
competition, which must be **Published** ("Competition not found", 404, for an unknown
competition, one of another subject, and one in any other status, FR-033).

**The response** is the file itself, with no page in between, so the teacher stays on the list;
its headers are built by `app.routers.downloads.pdf_download`, shared with the questions file and
the study materials (milestone 12.10).

The menu offers it as a link marked as a download (`menu_link(..., download=True)`), which the
loading script of milestone 10.1 skips. Opening it changes nothing and logs nothing.
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.core.auth import allow_roles
from app.core.db import SessionDep
from app.core.i18n import Language
from app.models import Role
from app.routers.downloads import pdf_download
from app.routers.teacher_competitions import (
    COMPETITION_NOT_FOUND,
    SUBJECT_NOT_FOUND,
    find_competition,
    not_found,
    offered_subject,
)
from app.services.competitions import CompetitionStatus, offered_subjects
from app.services.results import results_file, results_file_name

router = APIRouter(prefix="/teacher/competitions/{competition_id:int}")


@router.get("/results", response_class=Response)
@allow_roles(Role.TEACHER)
def download_results(
    request: Request,
    session: SessionDep,
    competition_id: int,
    subject: str | None = Query(None),
) -> Response:
    """The stored results file of the published competition in the current site language."""
    selected = offered_subject(offered_subjects(session), subject)
    if selected is None:
        return not_found(request, SUBJECT_NOT_FOUND)
    competition = find_competition(session, competition_id, selected)
    if competition is None or competition.status is not CompetitionStatus.PUBLISHED:
        return not_found(request, COMPETITION_NOT_FOUND)
    language: Language = request.state.language
    content = results_file(session, competition.id, language)
    if content is None:  # never: a Published competition has both files (data-model.md §4)
        return not_found(request, COMPETITION_NOT_FOUND)
    return pdf_download(content, results_file_name(competition.name, competition.starts_at))
