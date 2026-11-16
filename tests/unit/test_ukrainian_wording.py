"""The Ukrainian catalogue's wording (specs/012.5-ukrainian-localisation US8, FR-030–FR-034;
research R14, the glossary).

- The apostrophe is ʼ (U+02BC), never `'`, `’`, `‘` or `` ` ``.
- Quotation marks are «…», with „…“ inside; never `"` or `”`.
- A name quoted “%(x)s” in English stands in «%(x)s» (or „%(x)s“ inside «…») in Ukrainian.
- Nothing agrees with another person's gender (no gendered past forms about them), and the reader
  is «ви», never «ти».
- Every glossary term used as a whole message has the glossary's translation.
"""

import re
from pathlib import Path

import pytest
from babel.messages.catalog import Message
from babel.messages.pofile import read_po

CATALOGUE = (
    Path(__file__).resolve().parents[2] / "app" / "locale" / "uk" / "LC_MESSAGES" / "messages.po"
)


def _messages() -> list[Message]:
    with CATALOGUE.open("rb") as handle:
        return [m for m in read_po(handle, locale="uk") if m.id]


MESSAGES = _messages()


def _translations(message: Message) -> list[str]:
    return list(message.string) if isinstance(message.string, tuple) else [message.string]


def _identifier(message: Message) -> str:
    return message.id[0] if isinstance(message.id, tuple | list) else message.id


def _all() -> list[tuple[str, str]]:
    return [(_identifier(m), t) for m in MESSAGES for t in _translations(m)]


def test_the_apostrophe_is_the_letter_apostrophe() -> None:
    offenders = [t for _, t in _all() if re.search(r"['’‘`]", t)]
    assert offenders == []


def test_quotation_marks_are_ukrainian() -> None:
    offenders = []
    for _, translation in _all():
        if '"' in translation or "”" in translation:
            offenders.append(translation)
        if translation.count("„") != translation.count("“"):
            offenders.append(translation)
        if translation.count("«") != translation.count("»"):
            offenders.append(translation)
    assert offenders == []


def test_a_quoted_name_stays_quoted() -> None:
    offenders = []
    for identifier, translation in _all():
        for placeholder in re.findall(r"“(%\(\w+\)s)”", identifier):
            if f"«{placeholder}»" not in translation and f"„{placeholder}“" not in translation:
                offenders.append((identifier, translation))
    assert offenders == []


GENDERED = (
    "запросив",
    "запросила",
    "запрошений",
    "запрошена",
    "додав",
    "додала",
    "створив",
    "створила",
    "видалив",
    "видалила",
    "змінив",
    "змінила",
    "вилучив",
    "вилучила",
)
FAMILIAR = ("ти", "твій", "твоя", "твої", "тебе", "тобі")


@pytest.mark.parametrize("word", GENDERED + FAMILIAR)
def test_no_gendered_or_familiar_word(word: str) -> None:
    pattern = re.compile(rf"(?<![\wʼ]){word}(?![\wʼ])", re.IGNORECASE)
    assert [t for _, t in _all() if pattern.search(t)] == []


GLOSSARY = {
    ("tab", "Teachers"): "Педагоги",
    ("tab", "Educational institutions"): "Заклади освіти",
    ("tab", "Subjects"): "Предмети",
    ("tab", "Students"): "Учасники",
    ("tab", "Teams"): "Команди",
    ("tab", "Questions"): "Питання",
    ("tab", "Competitions"): "Змагання",
    (None, "Student Competitions"): "Студентські змагання",
    (None, "Administrator"): "Адміністратор",
    (None, "Teacher"): "Педагог",
    (None, "Student"): "Студент",
    (None, "Upcoming"): "Заплановано",
    (None, "In progress"): "Триває",
    (None, "Finished"): "Завершено",
    (None, "Cancelled"): "Скасовано",
    ("access level", "Read"): "Перегляд",
    ("access level", "Write"): "Редагування",
    (None, "Can manage competitions"): "Може керувати змаганнями",
    (None, "Grades"): "Оцінки",
    (None, "Score"): "Бал",
    (None, "Sign in"): "Увійти",
    (None, "Log out"): "Вийти",
    (None, "Withdraw consent"): "Відкликати згоду",
    (None, "Delete my data"): "Видалити мої дані",
    (None, "Reference answer"): "Еталонна відповідь",
    (None, "Educational institution"): "Заклад освіти",
    (None, "Class"): "Група",
    (None, "Region"): "Регіон",
    (None, "Subject"): "Предмет",
    (None, "Team"): "Команда",
    ("subject", "Active"): "Активний",
    ("region", "Active"): "Активний",
    ("institution", "Active"): "Активний",
    ("class", "Active"): "Активна",
    ("subject", "Deactivated"): "Деактивовано",
    ("class", "Deactivated"): "Деактивовано",
}


def test_the_glossary_terms() -> None:
    found = {(m.context, _identifier(m)): _translations(m)[0] for m in MESSAGES}
    assert {key: found.get(key) for key in GLOSSARY} == GLOSSARY


def test_the_kyiv_label() -> None:
    found = {_identifier(m): _translations(m)[0] for m in MESSAGES}
    assert found["%(moment)s (Kyiv time)"] == "%(moment)s (за київським часом)"
