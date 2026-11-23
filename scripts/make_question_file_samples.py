"""Make the sample questions files and study materials for the design review of milestone 12.10.

    uv run python scripts/make_question_file_samples.py

It takes no arguments. It builds the files' content from realistic invented data held below, in
memory, with no database, and renders each in Ukrainian and in English with the application's own
renderers (`app.services.question_files_pdf`), so the samples are exactly what a download gives.
It writes eight files to `specs/012.10-questions-study-materials/samples/` (research R11, FR-047):

- `questions-long-{uk,en}.pdf`: a competition of 24 long Ukrainian questions, some with line
  breaks, the apostrophe and the letters ґ, є, ї, enough to continue across pages;
- `questions-empty-{uk,en}.pdf`: a competition with no questions;
- `study-materials-150-{uk,en}.pdf`: «Історія України», 150 questions with answers of varied
  length, a few of them longer than half a page;
- `study-materials-empty-{uk,en}.pdf`: a subject with no questions.

The dates are fixed and the renderers read no clock, so running it again without a change to the
design leaves the files byte for byte as they were. It prints the time the 150-question file took
to make, for the record in `design-approval.md`. The files are committed as the evidence of each
review round: to change the design, change the renderers or `app.services.pdf_layout`, run this
script and commit the samples with the new round.

Nothing here is personal data: questions, answers, and competition and subject names only.
"""

import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.i18n import Language, load_translations  # noqa: E402
from app.services.question_files import QuestionsSheet, StudyMaterials  # noqa: E402
from app.services.question_files_pdf import (  # noqa: E402
    render_questions_pdf,
    render_study_materials_pdf,
)

OUT = ROOT / "specs/012.10-questions-study-materials/samples"

STARTED = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
"""21 November 2026, 10:00 in Kyiv."""
DOWNLOADED = date(2026, 11, 23)

LONG_QUESTIONS = (
    "Поясніть, чому ґрунти лісостепової зони України вважаються одними з найродючіших у світі, "
    "і назвіть щонайменше три чинники, що впливають на їхню родючість.",
    "Що таке ковалентний зв’язок? Наведіть приклад речовини з полярним і неполярним ковалентним "
    "зв’язком та поясніть різницю між ними.",
    "Розгляньте реакцію:\n2H₂ + O₂ → 2H₂O\nСкільки молів води утвориться з 3 молів водню, якщо "
    "кисню достатньо? Відповідь обґрунтуйте.",
    "Чому їжак не замерзає взимку? Опишіть фізіологічні зміни в організмі тварини під час "
    "зимової сплячки.",
    "Яку роль відіграє ємність конденсатора в коливальному контурі? Як зміниться період "
    "коливань, якщо ємність збільшити вчетверо?",
    "Назвіть три основні етапи фотосинтезу та укажіть, де саме в клітині відбувається кожен "
    "із них.",
    "Поясніть, як працює принцип Ле Шательє, на прикладі синтезу аміаку. Які умови зміщують "
    "рівновагу праворуч?",
    "Що спільного й відмінного між мітозом і мейозом? Відповідь подайте у вигляді порівняння "
    "щонайменше за чотирма ознаками.",
    "Обчисліть масову частку Оксигену в сульфатній кислоті H₂SO₄. Запишіть хід розв’язання.",
    "Чим відрізняється хімічна реакція від фізичного явища? Наведіть по два приклади кожного.",
    "Опишіть будову атома Карбону: кількість протонів, нейтронів, електронів і розподіл "
    "електронів за енергетичними рівнями.",
    "Чому мідь добре проводить електричний струм, а скло — ні? Поясніть з погляду будови речовини.",
    "Що таке каталізатор? Наведіть приклад промислового процесу, у якому без каталізатора не "
    "обійтися, і поясніть його роль.",
    "Поясніть явище осмосу. Чому морква, покладена в солону воду, стає м’якою?",
    "Що таке pH розчину? Як зміниться pH, якщо до води додати кілька крапель оцтової кислоти?",
    "Назвіть інертні гази та поясніть, чому вони майже не вступають у хімічні реакції.",
    "Опишіть кругообіг Нітрогену в природі та роль бактерій у ньому.",
    "Яка різниця між екзотермічними та ендотермічними реакціями? Наведіть приклади з "
    "повсякденного життя.",
    "Як визначити, чи є речовина кислотою, за допомогою індикатора? Які індикатори ви знаєте?",
    "Поясніть, чому залізо іржавіє, а алюміній — ні, хоча алюміній активніший метал.",
    "Що таке ізотопи? Наведіть приклад ізотопів Гідрогену та поясніть, чим вони відрізняються.",
    "Опишіть будову молекули ДНК і поясніть принцип комплементарності.",
    "Як змінюється розчинність газів у воді з підвищенням температури? Чому риби в теплій "
    "воді можуть задихатися?",
    "Розв’яжіть задачу: яку масу солі потрібно розчинити в 200 г води, щоб отримати розчин з "
    "масовою часткою солі 20 %?",
)

TOPICS = (
    "Київської Русі",
    "Галицько-Волинської держави",
    "Запорозької Січі",
    "Гетьманщини",
    "Української революції 1917–1921 років",
    "Другої світової війни на території України",
    "відновлення незалежності України",
    "культури доби Відродження в Україні",
    "козацьких повстань",
    "Литовсько-Руської держави",
)
FORMS = (
    "Які основні події {topic}?",
    "Назвіть визначних діячів {topic} та їхній внесок.",
    "Які причини та наслідки {topic} для подальшої історії України?",
    "Як змінилося суспільне життя внаслідок {topic}?",
    "Які джерела дають змогу вивчати історію {topic}?",
)
SENTENCES = (
    "Історики виокремлюють кілька етапів цього періоду, кожен з яких мав власні особливості.",
    "Важливу роль відіграли міжнародні відносини та торговельні шляхи.",
    "Ґрунтовні дослідження останніх десятиліть уточнили хронологію подій.",
    "Суспільство пережило глибокі зміни в господарстві, праві та культурі.",
    "Значну частину відомостей збережено в літописах, грамотах і листуванні.",
    "Події цього часу вплинули на формування національної самосвідомості українців.",
)


def history_entries() -> tuple[tuple[str, str], ...]:
    """150 questions of «Історія України», oldest first, with answers of one sentence up to well
    over half a page."""
    entries = []
    for n in range(150):
        topic = TOPICS[n % len(TOPICS)]
        question = FORMS[n % len(FORMS)].format(topic=topic)
        if n % 7 == 0:
            question += " Відповідь обґрунтуйте, спираючись на щонайменше два історичні джерела."
        length = 1 + (n * 5) % 9
        if n % 37 == 0:
            length = 40
        answer = " ".join(SENTENCES[(n + i) % len(SENTENCES)] for i in range(length))
        if n % 11 == 0:
            answer = answer.replace(". ", ".\n", 2)
        entries.append((question, answer))
    return tuple(entries)


def main() -> None:
    load_translations()
    OUT.mkdir(parents=True, exist_ok=True)
    long = QuestionsSheet("Весняний тур з природничих наук", "Хімія", STARTED, LONG_QUESTIONS)
    empty = QuestionsSheet("Осінній тур", "Хімія", STARTED, ())
    history = StudyMaterials("Історія України", DOWNLOADED, history_entries())
    nothing = StudyMaterials("Астрономія", DOWNLOADED, ())
    for language in Language:
        for name, content in (
            ("questions-long", render_questions_pdf(long, language)),
            ("questions-empty", render_questions_pdf(empty, language)),
            ("study-materials-empty", render_study_materials_pdf(nothing, language)),
        ):
            path = OUT / f"{name}-{language.value}.pdf"
            path.write_bytes(content)
            print(path.relative_to(ROOT))
        started = time.perf_counter()
        content = render_study_materials_pdf(history, language)
        elapsed = time.perf_counter() - started
        path = OUT / f"study-materials-150-{language.value}.pdf"
        path.write_bytes(content)
        print(f"{path.relative_to(ROOT)} (made in {elapsed:.2f} s)")


if __name__ == "__main__":
    main()
