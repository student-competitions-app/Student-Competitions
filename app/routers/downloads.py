"""The response of every download: the results file (milestone 12.8), a competition's questions
file and a subject's study materials (milestone 12.10), all PDF, and the question bank CSV file
(milestone 12.11), offered to administrators.

See specs/012.8-publishing-results/research.md R9 and specs/012.10-questions-study-materials/
contracts/http-routes.md §2. The response is the file itself, with no page in between, so the
teacher stays where they were:

- `Content-Disposition: attachment` names it, with an ASCII `filename=` and the full name in
  `filename*` (RFC 6266 / 5987), so a Cyrillic name is kept by every browser that can;
- `Cache-Control: no-store`, since the same address answers the Ukrainian or the English file by
  the language cookie, and a cached file must never answer after a switch;
- `X-Content-Type-Options: nosniff`.

Every page offers a download as a link marked as a download (`menu_link(..., download=True)`,
`link_button(..., download=True)`), which the loading script of milestone 10.1 skips. Opening one
changes nothing and logs nothing.
"""

from urllib.parse import quote

from fastapi.responses import Response

from app.services.file_names import ascii_file_name


def pdf_download(content: bytes, file_name: str) -> Response:
    """`content` as a PDF attachment named `file_name`."""
    return _attachment(content, file_name, "application/pdf")


def csv_download(content: bytes, file_name: str) -> Response:
    """`content` as a CSV attachment named `file_name`: a subject's question bank, exported by an
    administrator (milestone 12.11). The bytes carry their own byte-order mark."""
    return _attachment(content, file_name, "text/csv; charset=utf-8")


def _attachment(content: bytes, file_name: str, media_type: str) -> Response:
    disposition = (
        f'attachment; filename="{ascii_file_name(file_name)}"; '
        f"filename*=UTF-8''{quote(file_name, safe='')}"
    )
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
