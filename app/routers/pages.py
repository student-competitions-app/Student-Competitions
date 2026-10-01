"""Server-rendered pages. Thin handlers only — application wiring lives in `app.main`.

The role areas have their own router (`app.routers.areas`); this one serves the home page, which
every role may open."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import CurrentRole, allow_roles
from app.core.config import APP_DESCRIPTION, APP_NAME, APP_TAGLINE
from app.core.db import SessionDep
from app.core.templates import templates
from app.models import ALL_ROLES
from app.routers.areas import areas_for
from app.schemas.question import QuestionPublic
from app.services.database_status import read_database_status
from app.services.questions import list_questions

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
@allow_roles(*ALL_ROLES)
def home(request: Request, session: SessionDep, current_role: CurrentRole) -> HTMLResponse:
    """Render the home page: the introduction, links to the areas the current role may open
    (FR-027), the stored questions, and the database status.

    Sync rather than async: the database calls block, so FastAPI runs this in its thread pool.

    A database error while reading degrades the page rather than failing it: the page still
    renders with a notice in place of the data, and the error is logged by type and message only,
    never with the database URL (FR-026). Any other exception is a bug and still reaches the
    default 500 handling.
    """
    context: dict[str, object] = {
        "app_name": APP_NAME,
        "app_tagline": APP_TAGLINE,
        "app_description": APP_DESCRIPTION,
        "areas": areas_for(current_role),
    }
    try:
        questions = [
            QuestionPublic.model_validate(question, from_attributes=True)
            for question in list_questions(session)
        ]
        db_status = read_database_status(session)
    except SQLAlchemyError as exc:
        logger.error("Question data unavailable: %s: %s", type(exc).__name__, exc)
        context["data_available"] = False
    else:
        context["data_available"] = True
        context["questions"] = questions
        context["db_status"] = db_status
    return templates.TemplateResponse(request, "pages/home.html", context)
