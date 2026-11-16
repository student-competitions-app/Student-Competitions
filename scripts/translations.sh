#!/usr/bin/env bash
# The message catalogue workflow (milestone 12.5 research R5; README "Translations").
#
#   scripts/translations.sh update    extract every message into app/locale/messages.pot, merge it
#                                     into the uk and en catalogues, fill English from the
#                                     identifiers; then translate the new Ukrainian entries in
#                                     app/locale/uk/LC_MESSAGES/messages.po and clear "fuzzy"
#   scripts/translations.sh compile   compile both catalogues (.po → .mo)
#   scripts/translations.sh check     run the catalogue completeness test alone
#
# Run from the repository root. Everything goes through `uv run`, so the locked Babel is used.
set -euo pipefail

# The extraction keywords, defined once here. tests/unit/test_catalogues.py mirrors this list:
# change both together.
KEYWORDS=(
  -k _ -k _n:1,2 -k _p:1c,2
  -k gettext -k ngettext:1,2 -k pgettext:1c,2 -k npgettext:1c,2,3
)

cd "$(dirname "$0")/.."

case "${1:-}" in
  update)
    uv run pybabel extract -F babel.cfg --no-default-keywords "${KEYWORDS[@]}" \
      --project student-competitions --sort-by-file -o app/locale/messages.pot .
    uv run pybabel update -i app/locale/messages.pot -d app/locale -D messages --ignore-obsolete --no-fuzzy-matching
    uv run python scripts/fill_english_catalogue.py
    ;;
  compile)
    uv run pybabel compile -d app/locale -D messages --statistics
    ;;
  check)
    uv run pytest tests/unit/test_catalogues.py
    ;;
  *)
    echo "usage: scripts/translations.sh update|compile|check" >&2
    exit 2
    ;;
esac
