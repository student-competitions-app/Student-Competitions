# Contract: services and core modules (Milestone 12.5)

Only what changes. Every service message that reaches a person becomes a `Text`
([i18n.md](./i18n.md)); signatures otherwise stay.

## `app/core/config.py`

```python
class LanguageConfigError(RuntimeError): ...
def resolve_default_language(environ: Mapping[str, str] = os.environ) -> Language
    # unset/empty → UK; "uk"/"en" → that; else LanguageConfigError("DEFAULT_LANGUAGE must be uk or en")
```

`APP_NAME`, `APP_TAGLINE`, `APP_DESCRIPTION` become `Text` values (the Ukrainian name «Студентські
змагання»).

## `app/main.py`

- Lifespan: `resolve_default_language()` beside `resolve_auth_settings()`, before the database;
  `load_translations()`; `app.state.default_language`.
- `app.add_middleware(LanguageMiddleware)` at **module level**, right after `app = FastAPI(...)`,
  never inside the lifespan: Starlette refuses middleware once the app has started (its first call is
  the startup event). It then wraps routing and the exception handlers.
- `app.include_router(language.router)`.
- Error handlers: messages as `Text` (research R16).

## `app/core/templates.py`

- `templates.env.add_extension("jinja2.ext.i18n")`; `install_gettext_callables(gettext, ngettext,
  newstyle=True, pgettext=pgettext, npgettext=npgettext)`.
- Context processor `_page_context`: `theme`, `language`, `return_path` (replaces `theme_return`).
- Globals: `format_local_time`, `format_local_date`, `utc_iso`, `app_name`; the `utc` filter removed.

## `app/core/return_path.py` (new)

```python
def resolve_return(request: Request, raw: str) -> str
    # safe_return_path(raw), then a full GET route match; else "/" signed in, "/login" signed out
```

Moved from `app/routers/theme.py` (`_has_get_page` and its fallback), unchanged.

## `app/core/time_zone.py`

`KYIV`; `format_local_time(moment, zone)` (Kyiv fallback, labelled); `format_local_date(moment,
zone)`; `zone_name(None) == "Europe/Kyiv"`; `MONTHS` replaced by twelve `_p("genitive month", …)`
messages. See [i18n.md](./i18n.md) §Times.

## `app/schemas/names.py`

```python
APOSTROPHES = frozenset("'’ʼ‘`")
def name_key(name: str) -> str        # NFC → casefold → each apostrophe → "ʼ"
def name_sort_key(name: str) -> tuple[tuple[int, int], ...]   # data-model §6
def person_sort_key(last: str, first: str) -> tuple[...]
```

`InvalidName.message` is a `Text`.

## `app/schemas/people.py`

`clean_person_name(raw, field)` takes a field key (`"first_name"` / `"last_name"`) and picks whole
messages per field instead of inserting the field's name into a sentence.

## Sorting (research R13)

Every listed site sorts by `(name_sort_key(...), id)` or `person_sort_key`; nothing sorts by
`.casefold()` or by a translated label.

## `app/services/email.py`

```python
def login_code_message(email: str, code: str, minutes: int) -> EmailMessage
    # subject and text in current_language()
def deletion_message(to: str, link: str, expires_at: datetime) -> EmailMessage
    # current_language(); expiry via format_local_time(expires_at, None)
def invitation_message(to, inviter_display, inviter_email, role: Role,
                       detail_lines: Sequence[Text], link, expires_at) -> EmailMessage
    # subject = f"{uk} / {en}"; text = uk body + "\n\n———\n\n" + en body,
    # each rendered under use_language(...)
```

`format_utc` is removed. `services/invitations.py` passes `role` and `Text` detail lines.

## `app/services/consent.py`

```python
@dataclass(frozen=True)
class ConsentParts:
    ukrainian: tuple[str, ...]   # paragraphs after «Українською», before "English"
    english: tuple[str, ...]     # paragraphs after "English"
def consent_parts(text: str) -> ConsentParts | None   # None when no "English" paragraph
```

## Enums with labels

`Role.label`, `AccessLevel.label` (`models/teacher.py`), `CompetitionStatus.label`, the class label
(`services/classes.py`) return `Text`. Nothing calls `.lower()` on a label.

## Migration `<rev>_bilingual_consent_and_name_keys.py` (after `04d5b638615c`)

- `TEACHER_CONSENT_TEXT_V1_REWRITE_1`, `STUDENT_CONSENT_TEXT_V1_REWRITE_2`; private copies of the
  wordings to restore.
- `_new_name_key`, `_old_name_key`: private copies.
- `upgrade`: name keys (clash check first, data-model §5), then the two consent rows.
- `downgrade`: the consent rows restored, then the old keys.
