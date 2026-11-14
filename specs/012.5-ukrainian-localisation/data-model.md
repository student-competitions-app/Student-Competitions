# Data Model: Ukrainian Localisation (Milestone 12.5)

No table and no column is added or removed (spec FR-046, FR-053). One Alembic revision changes data
only: the consent texts' wordings and the stored duplicate keys of six tables (research R11, R12).

## 1. Language choice (browser only, new)

| Item | Value |
|---|---|
| Cookie | `sc_lang` |
| Values | `uk` or `en`, exactly; anything else, or no cookie, means the default language |
| Attributes | `Path=/`, `Max-Age=31536000`, `HttpOnly`, `SameSite=Lax`, `Secure` in production |
| Written by | `POST /language` only; always set, never deleted (FR-015) |
| Read by | `LanguageMiddleware`, once per request |
| Personal data | No: not linked to an account or a session, not in the database, never logged (FR-016) |

## 2. Default language (deployment setting, new)

| Item | Value |
|---|---|
| Variable | `DEFAULT_LANGUAGE` |
| Values | `uk` or `en`; unset or empty → `uk`; anything else stops the start (`LanguageConfigError`) |
| Stored | `app.state.default_language` (a `Language`) |
| Tests | `tests/conftest.py` sets `en`; the default's tests set `uk` |

## 3. Message catalogues (repository files, new)

| File | Committed | Content |
|---|---|---|
| `babel.cfg` | yes | extraction mapping; the gallery's template and router ignored |
| `app/locale/messages.pot` | yes | every message identifier, with its source locations |
| `app/locale/uk/LC_MESSAGES/messages.po` | yes | Ukrainian translations; `Plural-Forms: nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 \|\| n%100>=20) ? 1 : 2);` |
| `app/locale/en/LC_MESSAGES/messages.po` | yes | English translations, filled from the identifiers; `nplurals=2; plural=(n != 1);` |
| `app/locale/*/LC_MESSAGES/messages.mo` | no (git-ignored) | compiled at image build and test start |

Rules (research R4, R17): every identifier is the English wording; placeholders are named
(`%(name)s`, `%(num)d`); a literal `%` is `%%`; every message in use is translated in both files,
not fuzzy, with the same placeholders; no obsolete entries.

## 4. Consent texts (existing table `consent_texts`, data change)

Rows `(role='teacher', version=1)` and `(role='student', version=1)` keep their `id`, `version` and
`published_at`; only `text` changes.

| Wording | Teacher v1 | Student v1 |
|---|---|---|
| Original (milestone 8 / 9) | superseded | superseded |
| Rewrite 1 (milestone 11.1, teams) | — | superseded |
| Rewrite (milestone 12.5) | **published**, `TEACHER_CONSENT_TEXT_V1_REWRITE_1` | **published**, `STUDENT_CONSENT_TEXT_V1_REWRITE_2` |

**Shape of a bilingual text** (plain text, paragraphs separated by one blank line):

```text
Українською

<Ukrainian paragraph 1>

…

<the sentence: the Ukrainian wording prevails>

English

<today's English paragraph 1>

…

If the Ukrainian and English wordings differ, the Ukrainian wording prevails.
```

`consent_parts(text)` splits it at the paragraph that is exactly `English` (research R11). The
`consent_records` table is unchanged: its rows point to version 1, now bilingual.

**Pins** (`tests/unit/test_consent_texts.py`): `PUBLISHED` holds the two new hashes (set after the
product owner's approval); `SUPERSEDED` lists, per version, every earlier wording's hash (teacher:
1, student: 2); `REWRITES_ALLOWED = {("student", 1): 2, ("teacher", 1): 1}`.

## 5. Name duplicate keys (existing columns, recomputed)

| Table | Column | Uniqueness scope (unchanged) |
|---|---|---|
| `subjects` | `name_key` | all subjects |
| `regions` | `name_key` | all regions |
| `institutions` | `name_key` | within `region_id` |
| `classes` | `name_key` | within `institution_id` |
| `teams` | `name_key` | live teams (`deleted_at IS NULL`) |
| `competitions` | `name_key` | live competitions (not cancelled, not stopped) of a `subject_id` |

**Key, before**: `NFC(name).casefold()`.
**Key, after**: `NFC(name).casefold()` with `'` `’` `ʼ` `‘` `` ` `` each replaced by `ʼ` (U+02BC).
Length unchanged (one code point for one), so the 600-character columns still fit.

**Upgrade**: compute every new key; if two rows in the same scope get the same key, stop before any
write with `RuntimeError("… <table> ids <a> and <b> (“<name a>”, “<name b>”) now have the same name;
rename one and upgrade again")`; else update the keys that changed. **Downgrade**: recompute the old
key (cannot clash).

## 6. Name order (computed, never stored)

`name_sort_key(name)`: over `NFC(name).casefold()` with the five apostrophes removed, each character
mapped to `(group, order)`: `(0, code point)` not a letter; `(1, code point)` Latin letter;
`(2, rank)` Ukrainian letter, ranks 0–32 in the order а б в г ґ д е є ж з и і ї й к л м н о п р с т у
ф х ц ч ш щ ь ю я; `(3, code point)` any other letter. Lists add the record's id as the last
tie-break, as today. People: `(name_sort_key(last_name), name_sort_key(first_name), id)`.

## 7. Times (display only)

Storage is unchanged (UTC, Principle VII). Display: the browser's zone when known, no label;
otherwise `Europe/Kyiv`, labelled. Emails: always `Europe/Kyiv`, labelled. Formats in
[contracts/i18n.md](./contracts/i18n.md) §Times.
