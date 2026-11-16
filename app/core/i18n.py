"""Languages: Ukrainian by default, English on request (specs/012.5-ukrainian-localisation research
R1–R7, contracts/i18n.md).

**The choice** lives in one browser cookie, `sc_lang`, holding `uk` or `en` exactly; anything else,
or no cookie, means the deployment's default language (`DEFAULT_LANGUAGE`, Ukrainian when unset).
Like the theme cookie (`app.core.theme`) it holds only the choice: no identifier, nothing linked to
an account or a session, nothing in the database, so it is not personal data. It is `HttpOnly`,
since only the server reads it, and no log line ever names it. The browser's `Accept-Language`
is never read: a first visit is in the default language whatever the browser prefers.

**One decision per request**: `LanguageMiddleware`, a pure ASGI middleware around routing and the
exception handlers, reads the cookie once and sets a `ContextVar` holding that language's
compiled catalogue. Everything that translates (templates, `Text`, email builders, error pages)
reads that `ContextVar`. Sync endpoints run in a thread pool that copies the context, so they see
it too. Outside any request the `ContextVar` holds an empty catalogue: the English identifiers,
with the English plural rule.

**Messages in Python code** are `Text` values made by `_`, `_n` and `_p`, which are also the
extraction keywords. A `Text` is translated when it is turned into a string, in the language of
that moment, so a module constant, an exception's message or an enum's label is never fixed when
its module is imported. The identifier is the English wording; parameters are named and inserted
after translation, a `Text` parameter translated in the same language, any other value (what
people entered) unchanged.

**Messages in templates** go through `jinja2.ext.i18n` with new-style callables
(`app.core.templates`): `{{ _("Delete “%(name)s”?", name=subject.name) }}`. The four callables
below are plain lookups; Jinja formats and escapes.

The catalogues are compiled from `app/locale/{uk,en}/LC_MESSAGES/messages.po`
(`scripts/translations.sh compile`, the image build, the test session) and loaded once at start-up;
a missing compiled catalogue stops the start rather than showing identifiers.
"""

import gettext as _gettext
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from babel.support import Translations
from starlette.requests import cookie_parser
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

LANGUAGE_COOKIE_NAME = "sc_lang"
LANGUAGE_COOKIE_MAX_AGE = 31_536_000
"""One year, in seconds, as for the theme cookie."""

LOCALE_DIR = Path(__file__).resolve().parent.parent / "locale"
"""`app/locale`: the catalogues ship inside the `app/` copy of the image."""

DOMAIN = "messages"


class Language(StrEnum):
    """The interface languages, by their ISO 639-1 language codes (Ukrainian is `uk`; the
    country code of Ukraine names only the flag's file)."""

    UK = "uk"
    EN = "en"


def parse_language(value: str | None) -> Language | None:
    """`uk` or `en`, exactly, gives that language; anything else (missing, empty, unknown, another
    case, a regional variant) is `None`. Never raises."""
    if value == Language.UK.value:
        return Language.UK
    if value == Language.EN.value:
        return Language.EN
    return None


def apply_language(response: Response, language: Language, *, secure: bool) -> None:
    """Keep the choice in `response`. The cookie is always set, the default language too, so a
    later change of the deployment's default never changes a choice already made; it is never
    deleted. `secure` is the production flag, as for the session cookie."""
    response.set_cookie(
        LANGUAGE_COOKIE_NAME,
        language.value,
        max_age=LANGUAGE_COOKIE_MAX_AGE,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )


# ---------------------------------------------------------------------------------------------
# Catalogues and the current language
# ---------------------------------------------------------------------------------------------


class TranslationsNotCompiled(RuntimeError):
    """A compiled catalogue is missing, so the application must not start."""


_TRANSLATIONS: dict[Language, _gettext.NullTranslations] = {}
"""The loaded catalogue of each language, filled once by `load_translations`."""

_CURRENT: ContextVar[tuple[Language, _gettext.NullTranslations]] = ContextVar(
    "sc_language", default=(Language.EN, _gettext.NullTranslations())
)
"""The language of the current request (or `use_language` block) and its catalogue. Outside any
request: English, with an empty catalogue that returns the identifiers."""


def load_translations() -> None:
    """Load each language's compiled catalogue once; a second call loads only what is missing.
    Raises `TranslationsNotCompiled` when a `.mo` file is absent: Babel would otherwise fall back
    silently to the identifiers."""
    for language in Language:
        if language in _TRANSLATIONS:
            continue
        compiled = LOCALE_DIR / language.value / "LC_MESSAGES" / f"{DOMAIN}.mo"
        if not compiled.is_file():
            raise TranslationsNotCompiled(
                "Translations are not compiled: run scripts/translations.sh compile"
            )
        _TRANSLATIONS[language] = Translations.load(LOCALE_DIR, [language.value], DOMAIN)


def _translations_for(language: Language) -> _gettext.NullTranslations:
    if language not in _TRANSLATIONS:
        load_translations()
    return _TRANSLATIONS[language]


def current_language() -> Language:
    """The language of the current request; English outside any request."""
    return _CURRENT.get()[0]


@contextmanager
def use_language(language: Language) -> Iterator[None]:
    """Translate in `language` for the duration of the block, then restore the previous language:
    the invitation email is written once in each language, and tests check either."""
    token = _CURRENT.set((language, _translations_for(language)))
    try:
        yield
    finally:
        _CURRENT.reset(token)


class LanguageMiddleware:
    """Decide each HTTP request's language once, before routing: the `sc_lang` cookie when it is
    `uk` or `en`, else the deployment's default (`app.state.default_language`). The code goes to
    `request.state.language` and the catalogue to the `ContextVar` for the whole call, the
    exception handlers included. Other scopes (lifespan, websockets) pass through untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        language = parse_language(_cookie_value(scope)) or getattr(
            scope["app"].state, "default_language", Language.UK
        )
        scope.setdefault("state", {})["language"] = language
        token = _CURRENT.set((language, _translations_for(language)))
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT.reset(token)


def _cookie_value(scope: Scope) -> str | None:
    """The `sc_lang` value of the request's `Cookie` header, if any. Never raises."""
    for name, value in scope.get("headers", ()):
        if name == b"cookie":
            return cookie_parser(value.decode("latin-1")).get(LANGUAGE_COOKIE_NAME)
    return None


# ---------------------------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Text:
    """A message, translated when it is turned into a string (`str(text)`), in the current
    language. Made by `_`, `_n` and `_p`; never built directly.

    Equality and hashing use the current rendering, so `Text` compares equal to its English
    wording outside a request, and existing code that compares messages keeps working.
    """

    msgid: str
    plural: str | None = None
    n: int | None = None
    context: str | None = None
    params: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    def __str__(self) -> str:
        translations = _CURRENT.get()[1]
        if self.plural is None:
            template = (
                translations.pgettext(self.context, self.msgid)
                if self.context is not None
                else translations.gettext(self.msgid)
            )
        else:
            assert self.n is not None
            template = (
                translations.npgettext(self.context, self.msgid, self.plural, self.n)
                if self.context is not None
                else translations.ngettext(self.msgid, self.plural, self.n)
            )
        values: dict[str, Any] = {
            name: str(value) if isinstance(value, Text) else value
            for name, value in self.params.items()
        }
        if self.n is not None:
            values.setdefault("num", self.n)
        return template % values

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Text | str):
            return str(self) == str(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))


def _(msgid: str, /, **params: object) -> Text:
    """A message: `_("Enter a name.")`, `_("Delete “%(name)s”?", name=subject.name)`."""
    return Text(msgid, params=MappingProxyType(params))


def _n(singular: str, plural: str, n: int, /, **params: object) -> Text:
    """A counted message, its form chosen by the language's plural rule; `n` is also available as
    `%(num)d`: `_n("%(num)d team", "%(num)d teams", total)`."""
    return Text(singular, plural=plural, n=n, params=MappingProxyType(params))


def _p(context: str, msgid: str, /, **params: object) -> Text:
    """A message with a context, for an English wording that needs two Ukrainian ones:
    `_p("access level", "Read")`."""
    return Text(msgid, context=context, params=MappingProxyType(params))


# The template callables, installed in the shared Jinja environment with `newstyle=True`
# (`app.core.templates`). Plain lookups in the current language: Jinja's new-style wrapper applies
# `%` with the template's named parameters and escapes them, so formatting here would format twice.


def gettext(msgid: str) -> str:
    return _CURRENT.get()[1].gettext(msgid)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _CURRENT.get()[1].ngettext(singular, plural, n)


def pgettext(context: str, msgid: str) -> str:
    return _CURRENT.get()[1].pgettext(context, msgid)


def npgettext(context: str, singular: str, plural: str, n: int) -> str:
    return _CURRENT.get()[1].npgettext(context, singular, plural, n)
