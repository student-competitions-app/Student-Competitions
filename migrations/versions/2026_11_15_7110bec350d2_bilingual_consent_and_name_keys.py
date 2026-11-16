"""bilingual consent and name keys

Revision ID: 7110bec350d2
Revises: 04d5b638615c
Create Date: 2026-11-15 15:10:21.255209+00:00

Milestone 12.5 (specs/012.5-ukrainian-localisation data-model §4–§5, research R11, R12). Data
only: no table, column or index changes.

1. **Name keys recomputed.** The duplicate key of a name now treats the five apostrophes
   (`'` `’` `ʼ` `‘` `` ` ``) as one, so «Мар'яна» and «Марʼяна» are the same name. The stored
   `name_key` of subjects, regions, institutions, classes, teams and competitions is recomputed.
   Before any write the new keys are checked within each uniqueness scope; two existing names
   that now collide stop the upgrade with a message naming both records, so the administrator
   can rename one and upgrade again.
2. **The consent texts become bilingual.** Version 1 of the teacher's and the student's text is
   rewritten in place as «Українською» then "English", keeping its `id`, `version` and
   `published_at`, so every consent record keeps pointing at it. This is the last in-place rewrite
   of a published consent text (FR-051): from now on a wording change is a new version.
   `tests/unit/test_consent_texts.py` pins every wording.

The downgrade writes the previous wordings back from private copies (one revision cannot import
another) and restores the previous keys.

A frozen snapshot: plain SQLAlchemy constructs, nothing imported from `app`.
"""

import unicodedata
from collections.abc import Callable, Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7110bec350d2"
down_revision: str | Sequence[str] | None = "04d5b638615c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------------------------
# The consent texts (data-model §4, research R11)
# ---------------------------------------------------------------------------------------------

TEACHER_CONSENT_TEXT_V1_REWRITE_1 = """\
Українською

Натискаючи «Я погоджуюся», ви даєте згоду на те, щоб застосунок «Студентські змагання» зберігав \
такі дані про вас як педагога: вашу адресу електронної пошти, ваші імʼя та прізвище, заклади \
освіти, з якими вас повʼязано, разом із рівнем доступу до кожного з них («Перегляд» або \
«Редагування»), а також те, чи можете ви створювати змагання. Застосунок також фіксує, коли ви \
надали згоду, на яку версію цього тексту та від кого ви отримали запрошення.

Ми зберігаємо ці дані, щоб ви могли входити як педагог і щоб адміністратори могли визначати, з \
якими закладами освіти ви працюєте. До надання вами згоди жодних даних про вас не зберігалося.

Ваші дані бачать адміністратори застосунку «Студентські змагання», а також ви — на сторінці свого \
профілю. Іншим особам вони не передаються.

Листи від застосунку «Студентські змагання», як-от коди для входу, доставляє Resend — сервіс \
доставки електронної пошти, який отримує вашу адресу електронної пошти та вміст кожного листа \
лише для цієї мети.

Ви можете будь-коли відкликати згоду: відкрийте свій профіль і натисніть «Відкликати згоду» або, \
не входячи, скористайтеся посиланням «Видалити мої дані» на сторінці входу. Після цього ваші \
імʼя, прізвище та адресу електронної пошти буде стерто, а вашу роль педагога — вилучено. Запис \
про те, що ви погодилися з цим текстом, зберігається як підтвердження вашої згоди.

Якщо українська та англійська редакції відрізняються, переважає українська редакція.

English

By pressing "I agree" you consent to Student Competitions storing the following data about you as \
a teacher: your email address, your first and last name, the educational institutions you are \
linked to with your access level for each (Read or Write), and whether you may create \
competitions. The application also records when you agreed, to which version of this text, and \
who invited you.

We store this data so that you can sign in as a teacher and so that administrators can manage \
which educational institutions you work with. Nothing about you was stored before you agreed.

Your data is seen by the administrators of Student Competitions, and by you on your profile page. \
It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names and your email address \
are then erased and your teacher role is removed. The record that you agreed to this text is kept \
as proof of your consent.

If the Ukrainian and English wordings differ, the Ukrainian wording prevails."""
"""The teacher's consent text, version 1, bilingual: Ukrainian, then English (milestone 12.5
FR-044). Published; never edit it again (FR-051)."""

STUDENT_CONSENT_TEXT_V1_REWRITE_2 = """\
Українською

Натискаючи «Я погоджуюся», ви даєте згоду на те, щоб застосунок «Студентські змагання» зберігав \
такі дані про вас як студента: вашу адресу електронної пошти, ваші імʼя та прізвище, вашу групу, \
яка також визначає ваш заклад освіти та рік навчання, і ваше членство в командах: команди вашого \
закладу освіти, до яких ви входите. Застосунок також фіксує, коли ви надали згоду, на яку версію \
цього тексту та від кого ви отримали запрошення.

Ми зберігаємо ці дані, щоб ви могли входити як студент і брати участь у змаганнях вашого закладу \
освіти у складі своїх команд. До надання вами згоди жодних даних про вас не зберігалося.

Ваші дані, зокрема ваші команди, бачать педагоги, повʼязані з вашим закладом освіти, а також ви — \
на сторінці свого профілю. Іншим особам вони не передаються.

Листи від застосунку «Студентські змагання», як-от коди для входу, доставляє Resend — сервіс \
доставки електронної пошти, який отримує вашу адресу електронної пошти та вміст кожного листа \
лише для цієї мети.

Ви можете будь-коли відкликати згоду: відкрийте свій профіль і натисніть «Відкликати згоду» або, \
не входячи, скористайтеся посиланням «Видалити мої дані» на сторінці входу. Після цього ваші \
імʼя, прізвище, адресу електронної пошти, групу та членство в командах буде стерто, а вашу роль \
студента — вилучено. Запис про те, що ви погодилися з цим текстом, зберігається як підтвердження \
вашої згоди.

Якщо українська та англійська редакції відрізняються, переважає українська редакція.

English

By pressing "I agree" you consent to Student Competitions storing the following data about you as \
a student: your email address, your first and last name, your class, which also records your \
educational institution and your year of study, and your team memberships: the teams of your \
educational institution that you belong to. The application also records when you agreed, to \
which version of this text, and who invited you.

We store this data so that you can sign in as a student and take part, as a member of your teams, \
in the competitions of your educational institution. Nothing about you was stored before you \
agreed.

Your data, including your teams, is seen by the teachers linked to your educational institution, \
and by you on your profile page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names, your email address, \
your class and your team memberships are then erased and your student role is removed. The record \
that you agreed to this text is kept as proof of your consent.

If the Ukrainian and English wordings differ, the Ukrainian wording prevails."""
"""The student's consent text, version 1, bilingual: Ukrainian, then English (milestone 12.5
FR-044). Published; never edit it again (FR-051)."""

_TEACHER_CONSENT_TEXT_V1_ORIGINAL = """\
By pressing "I agree" you consent to Student Competitions storing the following data about you as \
a teacher: your email address, your first and last name, the educational institutions you are \
linked to with your access level for each (Read or Write), and whether you may create \
competitions. The application also records when you agreed, to which version of this text, and \
who invited you.

We store this data so that you can sign in as a teacher and so that administrators can manage \
which educational institutions you work with. Nothing about you was stored before you agreed.

Your data is seen by the administrators of Student Competitions, and by you on your profile page. \
It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names and your email address \
are then erased and your teacher role is removed. The record that you agreed to this text is kept \
as proof of your consent."""
"""A byte-for-byte copy of `TEACHER_CONSENT_TEXT_V1` of revision `f3bd41a67737`, for the
downgrade. Its SHA-256 is pinned as superseded in `tests/unit/test_consent_texts.py`."""

_STUDENT_CONSENT_TEXT_V1_REWRITE_1 = """\
By pressing "I agree" you consent to Student Competitions storing the following data about you as \
a student: your email address, your first and last name, your class, which also records your \
educational institution and your year of study, and your team memberships: the teams of your \
educational institution that you belong to. The application also records when you agreed, to \
which version of this text, and who invited you.

We store this data so that you can sign in as a student and take part, as a member of your teams, \
in the competitions of your educational institution. Nothing about you was stored before you \
agreed.

Your data, including your teams, is seen by the teachers linked to your educational institution, \
and by you on your profile page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email \
delivery service, which receives your email address and the content of each message for that \
purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, \
without signing in, use "Delete my data" on the sign-in page. Your names, your email address, \
your class and your team memberships are then erased and your student role is removed. The record \
that you agreed to this text is kept as proof of your consent."""
"""A byte-for-byte copy of `STUDENT_CONSENT_TEXT_V1_REWRITE` of revision `09cbcbe472be`, for
the downgrade. Its SHA-256 is pinned as superseded in `tests/unit/test_consent_texts.py`."""


def _write_consent_text_v1(role: str, text: str) -> None:
    """Rewrite the text of `role`'s version 1 in place; its `id`, `version` and `published_at`
    stay, so no consent record changes (FR-046)."""
    consent_texts = sa.table(
        "consent_texts",
        sa.column("role", sa.String),
        sa.column("version", sa.Integer),
        sa.column("text", sa.Text),
    )
    op.execute(
        consent_texts.update()
        .where(consent_texts.c.role == role, consent_texts.c.version == 1)
        .values(text=text)
    )


# ---------------------------------------------------------------------------------------------
# The name keys (data-model §5, research R12; FR-054, FR-055)
# ---------------------------------------------------------------------------------------------

_APOSTROPHES = frozenset("'’ʼ‘`")


def _old_name_key(name: str) -> str:
    """The key before this revision: NFC, then case-folded. A private copy: a revision never
    imports `app`."""
    return unicodedata.normalize("NFC", name).casefold()


def _new_name_key(name: str) -> str:
    """The key from this revision: the old key with every apostrophe as ʼ (U+02BC). A private
    copy of `app.schemas.names.name_key`; `tests/unit/test_name_order.py` checks they agree."""
    return "".join("ʼ" if c in _APOSTROPHES else c for c in _old_name_key(name))


_NAMED_TABLES: tuple[tuple[str, str | None, str | None], ...] = (
    ("subjects", None, None),
    ("regions", None, None),
    ("institutions", "region_id", None),
    ("classes", "institution_id", None),
    ("teams", None, "deleted_at IS NULL"),
    ("competitions", "subject_id", "cancelled_at IS NULL AND stopped_at IS NULL"),
)
"""Each table with a `name_key`: the column its names are unique within (none: the whole
table), and which rows the uniqueness covers (none: every row), as the unique indexes say."""


def _rows(table: str, scope: str | None, live: str | None) -> list[tuple[int, str, object, bool]]:
    """`(id, name, scope value, live)` of every row of `table`."""
    scope_sql = scope or "NULL"
    live_sql = f"CASE WHEN {live} THEN 1 ELSE 0 END" if live else "1"
    result = op.get_bind().execute(
        sa.text(f"SELECT id, name, {scope_sql}, {live_sql} FROM {table} ORDER BY id")
    )
    return [(row[0], row[1], row[2], bool(row[3])) for row in result]


def _refuse_clashes() -> None:
    """Stop before any write when two names in one scope would get the same new key, naming both
    records, so the administrator can rename one and upgrade again (FR-055)."""
    for table, scope, live in _NAMED_TABLES:
        seen: dict[tuple[object, str], tuple[int, str]] = {}
        for row_id, name, scope_value, is_live in _rows(table, scope, live):
            if not is_live:
                continue
            key = (scope_value, _new_name_key(name))
            if key in seen:
                other_id, other_name = seen[key]
                raise RuntimeError(
                    f"{table} ids {other_id} and {row_id} (“{other_name}”, “{name}”) now have the "
                    "same name; rename one and upgrade again"
                )
            seen[key] = (row_id, name)


def _write_name_keys(compute: Callable[[str], str]) -> None:
    """Store `compute(name)` as the key of every row whose key changes; other rows are left
    alone."""
    for table, _scope, _live in _NAMED_TABLES:
        named = sa.table(
            table,
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("name_key", sa.String),
        )
        rows = op.get_bind().execute(sa.select(named.c.id, named.c.name, named.c.name_key)).all()
        for row_id, name, stored in rows:
            key = compute(name)
            if key != stored:
                op.execute(named.update().where(named.c.id == row_id).values(name_key=key))


def upgrade() -> None:
    """Upgrade data: the name keys (after checking that none clash), then the consent texts."""
    _refuse_clashes()
    _write_name_keys(_new_name_key)
    _write_consent_text_v1("teacher", TEACHER_CONSENT_TEXT_V1_REWRITE_1)
    _write_consent_text_v1("student", STUDENT_CONSENT_TEXT_V1_REWRITE_2)


def downgrade() -> None:
    """Downgrade data: the consent texts, then the name keys."""
    _write_consent_text_v1("teacher", _TEACHER_CONSENT_TEXT_V1_ORIGINAL)
    _write_consent_text_v1("student", _STUDENT_CONSENT_TEXT_V1_REWRITE_1)
    _write_name_keys(_old_name_key)
