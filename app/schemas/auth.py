"""Sign-in form input: the validation boundary for the two login steps.

Handlers take plain `Form("")` strings and validate through these models, so a bad submission
re-renders the page with a friendly message instead of FastAPI's 422 JSON (research D11).
"""

from pydantic import BaseModel, field_validator

from app.core.security import is_valid_email, normalize_email


def _valid_address(value: str) -> str:
    address = normalize_email(value)
    if not is_valid_email(address):
        raise ValueError("not a valid email address")
    return address


class EmailSubmission(BaseModel):
    """Step 1: the address a code is requested for, normalised."""

    email: str
    next: str = "/"

    _email = field_validator("email")(_valid_address)


class CodeSubmission(BaseModel):
    """Step 2: the code entered for an address.

    The code is only stripped of surrounding whitespace, never rejected for its format: anything
    that is not the right code must still count as a wrong attempt against a live code (research
    D2).
    """

    email: str
    code: str
    next: str = "/"

    _email = field_validator("email")(_valid_address)

    @field_validator("code")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()
