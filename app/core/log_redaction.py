"""Keeping sealed links out of the access log.

See specs/008-teacher-management-consent/research.md#d14. Uvicorn's access log prints every
request's path and query, and two kinds of address carry a sealed value: the invitation and
data-deletion links (`/invitations/<token>`, `/data-deletion/confirm/<token>`), and the two
sealed notices after a redirect (`?sent=…`, `?prefill=…`). The values are encrypted, but they are
still the keys to an invitation or an erasure, so they are replaced with `***` before the line is
written. The `lifespan` installs one `AccessLogRedactor` on the `uvicorn.access` logger.

Pure, and it logs nothing itself.
"""

import logging
import re

_TOKEN_SEGMENT = re.compile(r"(/invitations/|/data-deletion/confirm/)[^/?#]+")
_SEALED_PARAMETER = re.compile(r"([?&](?:sent|prefill)=)[^&#]*")

_ACCESS_ARGS_LENGTH = 5
"""Uvicorn's access record: `(client, method, full_path, http_version, status)`."""
_PATH_INDEX = 2

REDACTED = "***"


def redact_path(full_path: str) -> str:
    """`full_path` with the sealed tokens and the sealed query values replaced by `***`."""
    path = _TOKEN_SEGMENT.sub(rf"\g<1>{REDACTED}", full_path)
    return _SEALED_PARAMETER.sub(rf"\g<1>{REDACTED}", path)


class AccessLogRedactor(logging.Filter):
    """Rewrites the path of uvicorn's access records; any other record passes unchanged."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == _ACCESS_ARGS_LENGTH:
            path = args[_PATH_INDEX]
            if isinstance(path, str):
                record.args = (*args[:_PATH_INDEX], redact_path(path), *args[_PATH_INDEX + 1 :])
        return True
