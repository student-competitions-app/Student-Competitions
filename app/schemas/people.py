"""Person names and addresses: the validation boundary for invitations, teacher edits and
student edits. Pure, no I/O.

See specs/008-teacher-management-consent/research.md#d11 and data-model.md §1. Names follow the
milestone 6/7 rules with a shorter limit: control characters are refused on the value as
submitted, then the name is trimmed, and its length (1–100 code points) is checked. Inner spaces
are kept exactly. Addresses are normalised and checked exactly as at sign-in.
"""

from typing import Literal

from app.core.i18n import Text, _
from app.core.security import is_valid_email, normalize_email
from app.schemas.names import has_control_character

PERSON_NAME_MAX_LENGTH = 100
"""Also the length of `users.first_name` and `users.last_name`, so the rule and the columns cannot
drift."""

INVALID_EMAIL = _("Enter a valid email address.")
"""The sign-in wording."""


class InvalidPersonName(ValueError):
    """The name breaks a rule; `message` is ready to show in the form, and names the field."""

    def __init__(self, message: Text) -> None:
        super().__init__(message)
        self.message = message


class InvalidEmail(ValueError):
    """The address is not a valid email address; `message` is ready to show in the form."""

    def __init__(self, message: Text = INVALID_EMAIL) -> None:
        super().__init__(message)
        self.message = message


PersonNameField = Literal["first_name", "last_name"]

_MESSAGES: dict[PersonNameField, tuple[Text, Text, Text]] = {
    "first_name": (
        _("The first name cannot contain tabs, line breaks or other control characters."),
        _("Enter a first name."),
        _("The first name can be at most %(max)d characters.", max=PERSON_NAME_MAX_LENGTH),
    ),
    "last_name": (
        _("The last name cannot contain tabs, line breaks or other control characters."),
        _("Enter a last name."),
        _("The last name can be at most %(max)d characters.", max=PERSON_NAME_MAX_LENGTH),
    ),
}
"""Whole messages per field (milestone 12.5 FR-021): the field's name is never inserted into a
sentence, since Ukrainian declines it."""


def clean_person_name(raw: str, field: PersonNameField) -> str:
    """The trimmed name, or `InvalidPersonName` with the first rule it breaks. `field` is
    `"first_name"` or `"last_name"`."""
    control, empty, too_long = _MESSAGES[field]
    if has_control_character(raw):
        raise InvalidPersonName(control)
    name = raw.strip()
    if not name:
        raise InvalidPersonName(empty)
    if len(name) > PERSON_NAME_MAX_LENGTH:
        raise InvalidPersonName(too_long)
    return name


def clean_person_names(first_name: str, last_name: str, errors: dict[str, Text]) -> tuple[str, str]:
    """Both names cleaned; a refused one is `""`, with its message recorded in `errors` under
    `first_name` or `last_name`, so a form can show every error at once."""
    cleaned = []
    fields: tuple[tuple[PersonNameField, str], ...] = (
        ("first_name", first_name),
        ("last_name", last_name),
    )
    for field, raw in fields:
        try:
            cleaned.append(clean_person_name(raw, field))
        except InvalidPersonName as refused:
            errors[field] = refused.message
            cleaned.append("")
    return cleaned[0], cleaned[1]


def clean_email(raw: str) -> str:
    """The normalised address, or `InvalidEmail`."""
    email = normalize_email(raw)
    if not is_valid_email(email):
        raise InvalidEmail()
    return email
