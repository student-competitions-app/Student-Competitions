"""Subject name rules: the shared rules of `app.schemas.names`, under subject names.

See specs/006-admin-area/research.md D1–D2 and specs/007-institutions/research.md D1. These are
the very same objects, so subjects and institutions cannot drift apart.
"""

from app.schemas.names import (
    NAME_KEY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NameRuleError,
    clean_name,
    name_key,
)

SUBJECT_NAME_MAX_LENGTH = NAME_MAX_LENGTH
SUBJECT_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH
SubjectNameError = NameRuleError
clean_subject_name = clean_name
subject_name_key = name_key
