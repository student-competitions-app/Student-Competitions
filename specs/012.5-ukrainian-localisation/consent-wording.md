# Bilingual consent texts — approved

**Status**: approved by the product owner on 2026-11-16 (FR-045, FR-050). The migration
`7110bec350d2` carries these wordings byte for byte, and `tests/unit/test_consent_texts.py`
pins their SHA-256 in `PUBLISHED`. This file is the record of the review; the migration is the
source of truth.

**What was reviewed**: the Ukrainian paragraphs. The English paragraphs are today's published wording,
word for word, plus the closing "prevails" sentence. If the review changes the meaning of a
Ukrainian sentence, the English wording is changed to match.

**Conventions used**: the glossary of research R14 (педагог, студент, заклад освіти, група, команда,
«Перегляд» / «Редагування», «Відкликати згоду», «Видалити мої дані»); quotation marks «…»; the
apostrophe ʼ; the reader addressed as «ви»; no word that agrees with the inviter's gender («від кого
ви отримали запрошення» instead of «хто вас запросив»). The button is quoted as «Я погоджуюся», the
Ukrainian label of **I agree** in the catalogue.

Each text is stored as plain text, paragraphs separated by one blank line, exactly as below
(data-model §4).

## Teacher, version 1 (`TEACHER_CONSENT_TEXT_V1_REWRITE_1`)

```text
Українською

Натискаючи «Я погоджуюся», ви даєте згоду на те, щоб застосунок «Студентські змагання» зберігав такі дані про вас як педагога: вашу адресу електронної пошти, ваші імʼя та прізвище, заклади освіти, з якими вас повʼязано, разом із рівнем доступу до кожного з них («Перегляд» або «Редагування»), а також те, чи можете ви створювати змагання. Застосунок також фіксує, коли ви надали згоду, на яку версію цього тексту та від кого ви отримали запрошення.

Ми зберігаємо ці дані, щоб ви могли входити як педагог і щоб адміністратори могли визначати, з якими закладами освіти ви працюєте. До надання вами згоди жодних даних про вас не зберігалося.

Ваші дані бачать адміністратори застосунку «Студентські змагання», а також ви — на сторінці свого профілю. Іншим особам вони не передаються.

Листи від застосунку «Студентські змагання», як-от коди для входу, доставляє Resend — сервіс доставки електронної пошти, який отримує вашу адресу електронної пошти та вміст кожного листа лише для цієї мети.

Ви можете будь-коли відкликати згоду: відкрийте свій профіль і натисніть «Відкликати згоду» або, не входячи, скористайтеся посиланням «Видалити мої дані» на сторінці входу. Після цього ваші імʼя, прізвище та адресу електронної пошти буде стерто, а вашу роль педагога — вилучено. Запис про те, що ви погодилися з цим текстом, зберігається як підтвердження вашої згоди.

Якщо українська та англійська редакції відрізняються, переважає українська редакція.

English

By pressing "I agree" you consent to Student Competitions storing the following data about you as a teacher: your email address, your first and last name, the educational institutions you are linked to with your access level for each (Read or Write), and whether you may create competitions. The application also records when you agreed, to which version of this text, and who invited you.

We store this data so that you can sign in as a teacher and so that administrators can manage which educational institutions you work with. Nothing about you was stored before you agreed.

Your data is seen by the administrators of Student Competitions, and by you on your profile page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email delivery service, which receives your email address and the content of each message for that purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, without signing in, use "Delete my data" on the sign-in page. Your names and your email address are then erased and your teacher role is removed. The record that you agreed to this text is kept as proof of your consent.

If the Ukrainian and English wordings differ, the Ukrainian wording prevails.
```

## Student, version 1 (`STUDENT_CONSENT_TEXT_V1_REWRITE_2`)

```text
Українською

Натискаючи «Я погоджуюся», ви даєте згоду на те, щоб застосунок «Студентські змагання» зберігав такі дані про вас як студента: вашу адресу електронної пошти, ваші імʼя та прізвище, вашу групу, яка також визначає ваш заклад освіти та рік навчання, і ваше членство в командах: команди вашого закладу освіти, до яких ви входите. Застосунок також фіксує, коли ви надали згоду, на яку версію цього тексту та від кого ви отримали запрошення.

Ми зберігаємо ці дані, щоб ви могли входити як студент і брати участь у змаганнях вашого закладу освіти у складі своїх команд. До надання вами згоди жодних даних про вас не зберігалося.

Ваші дані, зокрема ваші команди, бачать педагоги, повʼязані з вашим закладом освіти, а також ви — на сторінці свого профілю. Іншим особам вони не передаються.

Листи від застосунку «Студентські змагання», як-от коди для входу, доставляє Resend — сервіс доставки електронної пошти, який отримує вашу адресу електронної пошти та вміст кожного листа лише для цієї мети.

Ви можете будь-коли відкликати згоду: відкрийте свій профіль і натисніть «Відкликати згоду» або, не входячи, скористайтеся посиланням «Видалити мої дані» на сторінці входу. Після цього ваші імʼя, прізвище, адресу електронної пошти, групу та членство в командах буде стерто, а вашу роль студента — вилучено. Запис про те, що ви погодилися з цим текстом, зберігається як підтвердження вашої згоди.

Якщо українська та англійська редакції відрізняються, переважає українська редакція.

English

By pressing "I agree" you consent to Student Competitions storing the following data about you as a student: your email address, your first and last name, your class, which also records your educational institution and your year of study, and your team memberships: the teams of your educational institution that you belong to. The application also records when you agreed, to which version of this text, and who invited you.

We store this data so that you can sign in as a student and take part, as a member of your teams, in the competitions of your educational institution. Nothing about you was stored before you agreed.

Your data, including your teams, is seen by the teachers linked to your educational institution, and by you on your profile page. It is not shared with anyone else.

Emails from Student Competitions, such as sign-in codes, are delivered by Resend, an email delivery service, which receives your email address and the content of each message for that purpose only.

You can withdraw your consent at any time: open your profile and press "Withdraw consent", or, without signing in, use "Delete my data" on the sign-in page. Your names, your email address, your class and your team memberships are then erased and your student role is removed. The record that you agreed to this text is kept as proof of your consent.

If the Ukrainian and English wordings differ, the Ukrainian wording prevails.
```
