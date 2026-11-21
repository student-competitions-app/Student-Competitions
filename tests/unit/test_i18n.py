"""The i18n module: the language cookie, `Text`, and the default-language setting
(specs/012.5-ukrainian-localisation research R1–R7, R17, contracts/i18n.md).

Most cases run against a small Ukrainian catalogue built in memory, so they do not depend on the
wording of the real one; the cases at the end read the real catalogue (glossary terms, plurals).
"""

from collections.abc import Iterator
from io import BytesIO

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.support import Translations
from starlette.responses import Response

import app.core.config as config
from app.core import i18n
from app.core.i18n import (
    LANGUAGE_COOKIE_MAX_AGE,
    LANGUAGE_COOKIE_NAME,
    Language,
    Text,
    _,
    _n,
    _p,
    apply_language,
    current_language,
    parse_language,
    use_language,
)


def _catalogue() -> Translations:
    catalog = Catalog(locale="uk")
    catalog.add("Subject", "Предмет")
    catalog.add("Physics", "Фізика")
    catalog.add("Delete “%(name)s”?", "Видалити предмет «%(name)s»?")
    catalog.add("Status: %(status)s", "Стан: %(status)s")
    catalog.add("Upcoming", "Заплановано")
    catalog.add("Read", "Перегляд", context="access level")
    catalog.add("100%% done", "100%% готово")
    catalog.add(
        ("%(num)d team", "%(num)d teams"), ("%(num)d команда", "%(num)d команди", "%(num)d команд")
    )
    buffer = BytesIO()
    write_mo(buffer, catalog)
    buffer.seek(0)
    return Translations(fp=buffer)


@pytest.fixture
def ukrainian(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The in-memory Ukrainian catalogue in place of the real one, for one test."""
    monkeypatch.setitem(i18n._TRANSLATIONS, Language.UK, _catalogue())
    with use_language(Language.UK):
        yield


# ---------------------------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------------------------


def test_outside_a_request_a_text_is_its_english_identifier() -> None:
    assert str(_("Delete “%(name)s”?", name="Physics")) == "Delete “Physics”?"
    assert current_language() is Language.EN


def test_a_text_is_translated_when_rendered(ukrainian: None) -> None:
    assert str(_("Subject")) == "Предмет"
    assert str(_p("access level", "Read")) == "Перегляд"


def test_a_constant_made_before_the_language_is_set_is_translated_when_rendered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constant = _("Subject")
    monkeypatch.setitem(i18n._TRANSLATIONS, Language.UK, _catalogue())
    assert str(constant) == "Subject"
    with use_language(Language.UK):
        assert str(constant) == "Предмет"
    assert str(constant) == "Subject"


def test_a_user_value_equal_to_an_identifier_is_inserted_unchanged(ukrainian: None) -> None:
    assert str(_("Delete “%(name)s”?", name="Physics")) == "Видалити предмет «Physics»?"


def test_a_text_parameter_is_translated_in_the_same_language(ukrainian: None) -> None:
    assert str(_("Status: %(status)s", status=_("Upcoming"))) == "Стан: Заплановано"


def test_a_literal_percent_is_written_twice(ukrainian: None) -> None:
    assert str(_("100%% done")) == "100% готово"
    with use_language(Language.EN):
        assert str(_("100%% done")) == "100% done"


def test_equality_with_str_and_text_and_a_consistent_hash() -> None:
    message = _("Subject")
    assert message == "Subject"
    assert message == _("Subject")
    assert message != "Предмет"
    assert hash(message) == hash("Subject") == hash(_("Subject"))
    assert {message: 1}["Subject"] == 1
    assert (message == 3) is False


def test_a_text_in_an_f_string_and_an_exception() -> None:
    message = _("Delete “%(name)s”?", name="Physics")
    assert f"{message}" == "Delete “Physics”?"
    assert str(ValueError(message)) == "Delete “Physics”?"


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1 команда"),
        (2, "2 команди"),
        (5, "5 команд"),
        (11, "11 команд"),
        (21, "21 команда"),
        (22, "22 команди"),
        (25, "25 команд"),
    ],
)
def test_counted_messages_take_the_ukrainian_form(ukrainian: None, n: int, expected: str) -> None:
    assert str(_n("%(num)d team", "%(num)d teams", n)) == expected


@pytest.mark.parametrize(("n", "expected"), [(1, "1 team"), (2, "2 teams"), (0, "0 teams")])
def test_counted_messages_take_the_english_form(n: int, expected: str) -> None:
    assert str(_n("%(num)d team", "%(num)d teams", n)) == expected


# ---------------------------------------------------------------------------------------------
# The language and its cookie
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "language"), [("uk", Language.UK), ("en", Language.EN)])
def test_uk_and_en_are_read_exactly(value: str, language: Language) -> None:
    assert parse_language(value) is language


@pytest.mark.parametrize("value", ["ua", "UK", "en-GB", "", None, "x" * 5000, " uk", "En"])
def test_anything_else_is_no_choice(value: str | None) -> None:
    assert parse_language(value) is None


def test_use_language_restores_the_previous_language() -> None:
    with use_language(Language.UK):
        assert current_language() is Language.UK
        with use_language(Language.EN):
            assert current_language() is Language.EN
        assert current_language() is Language.UK
    assert current_language() is Language.EN


def test_use_language_restores_after_an_exception() -> None:
    with pytest.raises(RuntimeError), use_language(Language.UK):
        raise RuntimeError
    assert current_language() is Language.EN


def _set_cookie(response: Response) -> str:
    [header] = [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]
    return header


@pytest.mark.parametrize("secure", [True, False])
@pytest.mark.parametrize("language", [Language.UK, Language.EN])
def test_the_choice_is_stored_for_a_year(language: Language, secure: bool) -> None:
    response = Response()
    apply_language(response, language, secure=secure)
    header = _set_cookie(response)
    assert header.startswith(f"{LANGUAGE_COOKIE_NAME}={language.value};")
    assert f"Max-Age={LANGUAGE_COOKIE_MAX_AGE}" in header
    assert LANGUAGE_COOKIE_MAX_AGE == 31_536_000
    assert "Path=/" in header
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert ("Secure" in header) is secure


def test_the_texts_are_frozen() -> None:
    message = _("Subject")
    assert isinstance(message, Text)
    with pytest.raises(AttributeError):
        message.msgid = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------------------------
# The default-language setting (read through the module: `tests/unit/test_config.py` reloads it)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("environ", "language"),
    [
        ({}, Language.UK),
        ({"DEFAULT_LANGUAGE": ""}, Language.UK),
        ({"DEFAULT_LANGUAGE": "uk"}, Language.UK),
        ({"DEFAULT_LANGUAGE": "en"}, Language.EN),
    ],
)
def test_the_default_language_setting(environ: dict[str, str], language: Language) -> None:
    assert config.resolve_default_language(environ) is language


@pytest.mark.parametrize("value", ["fr", "UK", "ua", "en-GB", " en"])
def test_an_unknown_default_language_stops_the_start(value: str) -> None:
    with pytest.raises(config.LanguageConfigError) as raised:
        config.resolve_default_language({"DEFAULT_LANGUAGE": value})
    assert str(raised.value) == "DEFAULT_LANGUAGE must be uk or en"


# ---------------------------------------------------------------------------------------------
# The real catalogue (US3, research R14: the glossary)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "ukrainian", "english"),
    [
        (1, "1 команда", "1 team"),
        (2, "2 команди", "2 teams"),
        (5, "5 команд", "5 teams"),
        (11, "11 команд", "11 teams"),
        (21, "21 команда", "21 teams"),
        (22, "22 команди", "22 teams"),
        (25, "25 команд", "25 teams"),
    ],
)
def test_the_real_catalogue_counts_teams(n: int, ukrainian: str, english: str) -> None:
    message = _n("%(num)d team", "%(num)d teams", n)
    with use_language(Language.UK):
        assert str(message) == ukrainian
    with use_language(Language.EN):
        assert str(message) == english


def test_the_labels_are_the_glossary_terms() -> None:
    from app.models import AccessLevel, Role
    from app.services.competitions import CompetitionStatus

    with use_language(Language.UK):
        assert [str(s.label) for s in CompetitionStatus] == [
            "Заплановано",
            "Триває",
            "Завершено",
            "Опубліковано",
            "Скасовано",
        ]
        assert [str(a.label) for a in AccessLevel] == ["Перегляд", "Редагування"]
        assert [str(r.label) for r in Role] == ["Адміністратор", "Педагог", "Студент"]
        assert str(_p("tab", "Students")) == "Учасники"
        assert str(_("Student Competitions")) == "Студентські змагання"


@pytest.mark.parametrize(
    ("kind", "active"),
    [
        ("subject", "Активний"),
        ("region", "Активний"),
        ("institution", "Активний"),
        ("class", "Активна"),
    ],
)
def test_the_status_word_agrees_with_the_record(kind: str, active: str) -> None:
    with use_language(Language.UK):
        assert str(_p(kind, "Active")) == active
        assert str(_p(kind, "Deactivated")) == "Деактивовано"
