"""The response of every PDF download: the results file (milestone 12.8), a competition's questions
file and a subject's study materials (milestone 12.10).

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
    disposition = (
        f'attachment; filename="{ascii_file_name(file_name)}"; '
        f"filename*=UTF-8''{quote(file_name, safe='')}"
    )
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
