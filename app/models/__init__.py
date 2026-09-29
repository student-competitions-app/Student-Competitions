"""Every table model, imported here so that importing `app.models` makes `SQLModel.metadata`
complete. Alembic's `env.py` and the drift test rely on that; a new model must be added here."""

from app.models.boot_counter import BootCounter
from app.models.login_code import LoginCode
from app.models.question import Question
from app.models.rate_limit_hit import RateLimitHit
from app.models.user import Role, User
from app.models.user_session import UserSession

__all__ = ["BootCounter", "LoginCode", "Question", "RateLimitHit", "Role", "User", "UserSession"]
