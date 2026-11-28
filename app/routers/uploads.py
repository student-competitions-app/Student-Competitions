"""Reading one uploaded file: the question bank CSV file an administrator imports (milestone 12.11).

See specs/012.11-question-bank-csv/research.md R7 and contracts/services.md §3.

**A dependency, never a `File(...)` or `Form(...)` parameter.** FastAPI reads a route's form body
before it solves the route's dependencies, so a `File(...)` parameter would read a refused user's
upload before `resolve_access` (the cross-site check and the role, milestone 5) has run. As a
dependency of the handler, listed after the application-wide `resolve_access`, the body is read
only once the request is allowed.

**At most `max_bytes` is kept.** A request whose `Content-Length` is larger than the file could be
(plus the multipart overhead) is drained and discarded, up to `_DRAIN_LIMIT`, never stored, so the
browser receives the page with its error rather than a reset connection. Otherwise the form is
parsed (Starlette spools a large part to a temporary file, removed when the form is closed), and at
most `max_bytes + 1` bytes of the file are read. A file field left empty is "no file": a browser
sends it as a part with an empty file name and no content. A body that is not a valid multipart
form is read as no file too. The file's extension is not checked: its content decides.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from app.services.question_csv import MAX_FILE_BYTES

_MULTIPART_OVERHEAD = 16 * 1024
"""Room for the multipart boundaries and part headers around the file."""

_DRAIN_LIMIT = 16 * 1024 * 1024
"""How much of a refused body is read and discarded before the page is answered anyway."""


@dataclass(frozen=True)
class Upload:
    """The file as sent: `data is None and not too_large` means that no file was chosen; with
    `too_large`, `data` is `None` and the body was never kept."""

    data: bytes | None
    too_large: bool


async def _drain(request: Request) -> None:
    read = 0
    async for chunk in request.stream():
        read += len(chunk)
        if read > _DRAIN_LIMIT:
            return


def uploaded_file(
    field: str = "file", max_bytes: int = MAX_FILE_BYTES
) -> Callable[[Request], Coroutine[Any, Any, Upload]]:
    """A dependency reading the one file sent as `field`, at most `max_bytes` of it."""

    async def read(request: Request) -> Upload:
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > max_bytes + _MULTIPART_OVERHEAD:
            await _drain(request)
            return Upload(data=None, too_large=True)
        try:
            form = await request.form(max_files=1, max_fields=2)
        except (MultiPartException, HTTPException):
            return Upload(data=None, too_large=False)
        try:
            value = form.get(field)
            if not isinstance(value, UploadFile):
                return Upload(data=None, too_large=False)
            data = await value.read(max_bytes + 1)
            if value.filename == "" and not data:
                return Upload(data=None, too_large=False)
            if len(data) > max_bytes:
                return Upload(data=None, too_large=True)
            return Upload(data=data, too_large=False)
        finally:
            await form.close()

    return read


UploadedCsv = Annotated[Upload, Depends(uploaded_file())]
"""The question bank CSV file of the import form, for a handler's signature."""
