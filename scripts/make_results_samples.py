"""Make the sample results files for the design review of milestone 12.8.

    uv run python scripts/make_results_samples.py

It takes no arguments. It builds three results snapshots from realistic data held below, in
memory, with no database, and renders each in Ukrainian and in English with the application's own
renderer (`app.services.results_pdf.render_results_pdf`), so the samples are exactly what
publishing would store. It writes six files to `specs/012.8-publishing-results/samples/`
(milestone 12.8 research R12, FR-039):

- `long-list-{uk,en}.pdf`: seven regions, sixty teams in twenty institutions, Cyrillic names with
  the apostrophe and the letters ґ, є, ї, enough to continue across pages (4 questions, so a
  maximum score of 40);
- `long-names-{uk,en}.pdf`: one region with institution and team names of about two hundred
  characters, so the wrapping can be judged;
- `no-teams-{uk,en}.pdf`: a competition with no teams.

The times are fixed and the renderer reads no clock, so running it again without a change to the
design leaves the files byte for byte as they were. They are committed as the evidence of each
review round, recorded in `specs/012.8-publishing-results/design-approval.md`: to change the
design, change the renderer, run this script and commit the samples with the new round.

Nothing here is personal data: the names are invented, and results files hold only team,
institution and region names and scores.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.i18n import Language, load_translations  # noqa: E402
from app.services.results import RegionResults, ResultLine, ResultsSnapshot  # noqa: E402
from app.services.results_pdf import render_results_pdf  # noqa: E402

OUT = ROOT / "specs/012.8-publishing-results/samples"

STARTED = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
"""14 March 2027, 10:00 in Kyiv."""
FINISHED = datetime(2027, 3, 14, 10, 30, tzinfo=UTC)
PUBLISHED = datetime(2027, 3, 21, 9, 0, tzinfo=UTC)

REGIONS = {
    "Вінницька": ["Вінницький ліцей №7", "Гімназія «Ґрунт»", "Барський ліцей"],
    "Житомирська": ["Житомирський академічний ліцей №1", "Бердичівська гімназія №3"],
    "Київ": [
        "Ліцей «Інтелект»",
        "Природничо-математичний ліцей №145",
        "Гімназія №153 імені О. С. Пушкіна",
        "Український гуманітарний ліцей",
    ],
    "Львівська": ["Львівський фізико-математичний ліцей", "Академічна гімназія Львова"],
    "Одеська": ["Рішельєвський ліцей", "Одеська гімназія №2", "Ізмаїльський ліцей №1"],
    "Харківська": [
        "Харківський фізико-математичний ліцей №27",
        "Ліцей «Слобожанський»",
        "Чугуївська гімназія",
    ],
    "Чернігівська": ["Чернігівський ліцей №32", "Ніжинська гімназія «Їжак»", "Прилуцький ліцей"],
}
TEAMS = [
    "Зорі",
    "Кометиʼ",
    "Ґрафіт",
    "Єдність",
    "Їжаки",
    "Атоми",
    "Квант",
    "Мар’яна та друзі",
    "Іскра",
    "Сузір’я",
]


def long_list() -> ResultsSnapshot:
    regions = []
    n = 0
    for region, institutions in sorted(REGIONS.items()):
        lines = []
        for institution in institutions:
            for _ in range(3):
                lines.append(ResultLine(institution, TEAMS[n % len(TEAMS)], (n * 7) % 41))
                n += 1
        regions.append(RegionResults(region, tuple(lines)))
    return ResultsSnapshot(
        competition_name="Весняний тур олімпіади з хімії",
        subject_name="Хімія",
        starts_at=STARTED,
        finished_at=FINISHED,
        published_at=PUBLISHED,
        max_score=40,
        regions=tuple(regions),
    )


def long_names() -> ResultsSnapshot:
    institution = (
        "Комунальний заклад «Харківський навчально-виховний комплекс — спеціалізована "
        "загальноосвітня школа І–ІІІ ступенів з поглибленим вивченням природничо-математичних "
        "дисциплін імені академіка Василя Івановича Вернадського» Харківської міської ради"
    )
    team = (
        "Об’єднана команда юних дослідників, винахідників і майбутніх лауреатів міжнародних "
        "олімпіад з хімії, фізики та біології «Ґрунтовні знання — їхня найбільша сила»"
    )
    return ResultsSnapshot(
        competition_name=(
            "Відкрита регіональна олімпіада для учнів старших класів і студентів перших курсів "
            "закладів фахової передвищої освіти з хімії та суміжних природничих наук"
        ),
        subject_name="Хімія",
        starts_at=STARTED,
        finished_at=FINISHED,
        published_at=PUBLISHED,
        max_score=50,
        regions=(
            RegionResults(
                "Харківська",
                (ResultLine(institution, team, 38), ResultLine(institution, team + " 2", 9)),
            ),
        ),
    )


def no_teams() -> ResultsSnapshot:
    return ResultsSnapshot(
        competition_name="Осінній тур",
        subject_name="Хімія",
        starts_at=STARTED,
        finished_at=FINISHED,
        published_at=PUBLISHED,
        max_score=30,
        regions=(),
    )


def main() -> None:
    load_translations()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, snapshot in (
        ("long-list", long_list()),
        ("long-names", long_names()),
        ("no-teams", no_teams()),
    ):
        for language in Language:
            path = OUT / f"{name}-{language.value}.pdf"
            path.write_bytes(render_results_pdf(snapshot, language))
            print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
