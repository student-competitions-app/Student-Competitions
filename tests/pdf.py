"""Read a results file back, so the tests check what a teacher would see in it.

See specs/012.8-publishing-results/research.md R14 and contracts/results-file.md.

**Test-only**: built on pypdf, a development dependency that never reaches the image, and never
imported by `app/`. Every function takes the file's bytes as stored or downloaded.
"""

import io

from pypdf import PdfReader
from pypdf.generic import DictionaryObject


def _reader(content: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(content))


def pdf_text(content: bytes) -> str:
    """The text of every page, in page order, the pages joined with a line break."""
    return "\n".join(page.extract_text() for page in _reader(content).pages)


def pdf_page_texts(content: bytes) -> list[str]:
    """The text of each page on its own, for the checks of the page numbering."""
    return [page.extract_text() for page in _reader(content).pages]


def pdf_pages(content: bytes) -> int:
    """The number of pages."""
    return len(_reader(content).pages)


def pdf_metadata(content: bytes) -> dict[str, str]:
    """The document information (`/Title`, `/Producer`, `/CreationDate`, …) and the catalogue's
    `/Lang`, as plain strings."""
    reader = _reader(content)
    info = {str(key): str(value) for key, value in (reader.metadata or {}).items()}
    lang = reader.trailer["/Root"].get("/Lang")
    if lang is not None:
        info["/Lang"] = str(lang)
    return info


def pdf_images(content: bytes, page: int = 0) -> int:
    """The number of images drawn on the page (0-based)."""
    return len(_reader(content).pages[page].images)


def pdf_fonts_embedded(content: bytes) -> bool:
    """Whether every font used on every page carries its own font program, so the file renders
    the same everywhere with no font installed on the reader's side."""
    reader = _reader(content)
    found = False
    for page in reader.pages:
        resources = page.get("/Resources")
        if resources is None:
            continue
        fonts = resources.get_object().get("/Font")
        if fonts is None:
            continue
        for ref in fonts.get_object().values():
            font = ref.get_object()
            found = True
            if not _has_font_file(font):
                return False
    return found


def _has_font_file(font: DictionaryObject) -> bool:
    descriptor = font.get("/FontDescriptor")
    if descriptor is None:
        descendants = font.get("/DescendantFonts")
        if not descendants:
            return False
        return _has_font_file(descendants.get_object()[0].get_object())
    descriptor = descriptor.get_object()
    return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
