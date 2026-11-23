"""The names of the files teachers download: the results file (milestone 12.8), a competition's
questions file and a subject's study materials (milestone 12.10).

See specs/012.8-publishing-results/research.md R9 and specs/012.10-questions-study-materials/
research.md R7. Every name is built from what people entered (a competition's or a subject's
name), so it is cleaned before it reaches the `Content-Disposition` header: a character a file
name cannot hold on the common systems becomes `_`, every other character, Cyrillic included, is
kept. The header also carries a plain ASCII fallback for browsers that do not read `filename*`.
"""

import unicodedata

_UNSAFE = frozenset('/\\:*?"<>|')
"""The characters a file name cannot hold on the common systems (milestone 12.8 research R9)."""


def clean_file_stem(text: str, fallback: str) -> str:
    """`text` as the start of a file name: each character a file name cannot hold (`/ \\ : * ? "
    < > |` and control characters) becomes `_`; spaces at the ends and trailing dots are removed;
    an empty result becomes `fallback`. Every other character, Cyrillic included, is kept."""
    cleaned = "".join(
        "_" if c in _UNSAFE or unicodedata.category(c) == "Cc" else c for c in text
    ).strip()
    return cleaned.rstrip(". ") or fallback


_ASCII_KEPT = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.()")


def ascii_file_name(file_name: str) -> str:
    """The plain fallback of the `Content-Disposition` header's `filename=` for browsers that do
    not read `filename*`: ASCII letters, digits, space and `-_.()` kept (accents dropped), every
    other character `_`, runs of `_` collapsed to one."""
    decomposed = unicodedata.normalize("NFKD", file_name)
    kept = "".join(
        c if c in _ASCII_KEPT else "_" for c in decomposed if not unicodedata.combining(c)
    )
    collapsed = []
    for c in kept:
        if c == "_" and collapsed and collapsed[-1] == "_":
            continue
        collapsed.append(c)
    return "".join(collapsed)
