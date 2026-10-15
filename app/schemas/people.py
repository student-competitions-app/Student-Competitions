"""Person names and addresses: the validation boundary for invitations and teacher edits. Pure,
no I/O.

See specs/008-teacher-management-consent/research.md#d11 and data-model.md §1. Names follow the
milestone 6/7 rules with a shorter limit: control characters are refused on the value as
submitted, then the name is trimmed, and its length (1–100 code points) is checked. Inner spaces
are kept exactly. Addresses are normalised and checked exactly as at sign-in.
"""

from app.core.security import is_valid_email, normalize_email
from app.schemas.names import has_control_character

PERSON_NAME_MAX_LENGTH = 100
"""Also the length of `users.first_name` and `users.last_name`, so the rule and the columns cannot
drift."""

INVALID_EMAIL = "Enter a valid email address."
"""The sign-in wording."""


class InvalidPersonName(ValueError):
    """The name breaks a rule; `message` is ready to show in the form, and names the field."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidEmail(ValueError):
    """The address is not a valid email address; `message` is ready to show in the form."""

    def __init__(self, message: str = INVALID_EMAIL) -> None:
        super().__init__(message)
        self.message = message


def clean_person_name(raw: str, field_label: str) -> str:
    """The trimmed name, or `InvalidPersonName` with the first rule it breaks. `field_label` is
    "first name" or "last name"."""
    if has_control_character(raw):
        raise InvalidPersonName(
            f"The {field_label} cannot contain tabs, line breaks or other control characters."
        )
    name = raw.strip()
    if not name:
        raise InvalidPersonName(f"Enter a {field_label}.")
    if len(name) > PERSON_NAME_MAX_LENGTH:
        raise InvalidPersonName(
            f"The {field_label} can be at most {PERSON_NAME_MAX_LENGTH} characters."
        )
    return name


def clean_email(raw: str) -> str:
    """The normalised address, or `InvalidEmail`."""
    email = normalize_email(raw)
    if not is_valid_email(email):
        raise InvalidEmail()
    return email
