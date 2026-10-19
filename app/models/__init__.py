"""Every table model, imported here so that importing `app.models` makes `SQLModel.metadata`
complete. Alembic's `env.py` and the drift test rely on that; a new model must be added here."""

from app.models.boot_counter import BootCounter
from app.models.consent import ConsentRecord, ConsentText, InvitationCutoff
from app.models.enrolment import Enrolment
from app.models.institution import Institution
from app.models.login_code import LoginCode
from app.models.question import Question
from app.models.rate_limit_hit import RateLimitHit
from app.models.region import Region
from app.models.school_class import SchoolClass
from app.models.subject import Subject
from app.models.teacher import AccessLevel, TeacherInstitution, TeacherProfile
from app.models.user import ALL_ROLES, Role, User
from app.models.user_role import UserRole
from app.models.user_session import UserSession

__all__ = [
    "ALL_ROLES",
    "AccessLevel",
    "BootCounter",
    "ConsentRecord",
    "ConsentText",
    "Enrolment",
    "Institution",
    "InvitationCutoff",
    "LoginCode",
    "Question",
    "RateLimitHit",
    "Region",
    "Role",
    "SchoolClass",
    "Subject",
    "TeacherInstitution",
    "TeacherProfile",
    "User",
    "UserRole",
    "UserSession",
]
