"""Subject name rules: the milestone 6 names for the rules now shared in `app.schemas.names`.

See specs/007-region-and-institutions-management/research.md D1. Subjects, regions and
institutions follow exactly the same rules, so they live in one place. These aliases are the very
same objects, kept so that the subject code and tests need no change.
"""

from app.schemas.names import (
    NAME_KEY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    InvalidName,
    clean_name,
    name_key,
)

SUBJECT_NAME_MAX_LENGTH = NAME_MAX_LENGTH
SUBJECT_NAME_KEY_MAX_LENGTH = NAME_KEY_MAX_LENGTH
SubjectNameError = InvalidName
clean_subject_name = clean_name
subject_name_key = name_key
