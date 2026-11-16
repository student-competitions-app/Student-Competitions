"""Fill the English catalogue from its message identifiers (milestone 12.5 research R5).

Every identifier is the English wording (FR-023), so English needs no hand translation: for each
entry of `app/locale/en/LC_MESSAGES/messages.po` whose translation is empty or marked fuzzy, the
translation becomes the identifier (for a counted message, form 0 the singular identifier and
form 1 the plural one), and the fuzzy flag is cleared. A translation that is filled in and not
fuzzy is a deliberate English wording and is kept.

Run by `scripts/translations.sh update`, after `pybabel update`; development only, not in the
image.
"""

from pathlib import Path

from babel.messages.pofile import read_po, write_po

ENGLISH_CATALOGUE = (
    Path(__file__).resolve().parent.parent / "app" / "locale" / "en" / "LC_MESSAGES" / "messages.po"
)

LINE_WIDTH = 76
"""The width `pybabel update` writes, so a fill leaves no line-wrapping noise in the diff."""


def _is_empty(value: str | tuple[str, ...] | None) -> bool:
    if isinstance(value, tuple):
        return not all(value)
    return not value


def main() -> None:
    with ENGLISH_CATALOGUE.open("rb") as handle:
        catalogue = read_po(handle, locale="en")
    filled = 0
    for message in catalogue:
        if not message.id:
            continue  # the header
        if not (message.fuzzy or _is_empty(message.string)):
            continue
        if isinstance(message.id, tuple | list):
            singular, plural = message.id[0], message.id[1]
            message.string = (singular, plural)
        else:
            message.string = message.id
        message.flags.discard("fuzzy")
        filled += 1
    with ENGLISH_CATALOGUE.open("wb") as handle:
        write_po(handle, catalogue, width=LINE_WIDTH, ignore_obsolete=True)
    print(f"English catalogue: {filled} entries filled from their identifiers")


if __name__ == "__main__":
    main()
