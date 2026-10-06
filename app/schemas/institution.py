"""Educational institution name rules: the shared rules of `app.schemas.names`, under
institution names.

See specs/007-institutions/research.md D1 and data-model.md "Validation rules". These are the very
same objects as the subject rules, so the two lists cannot drift apart.
"""

from app.schemas.names import (
    NAME_KEY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NameRuleError,
    clean_name,
    name_key,
)

INSTITUTION_NAME_MAX_LENGTH = NAME_MAX_LENGTH
INSTITUTION_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH
InstitutionNameError = NameRuleError
clean_institution_name = clean_name
institution_name_key = name_key
