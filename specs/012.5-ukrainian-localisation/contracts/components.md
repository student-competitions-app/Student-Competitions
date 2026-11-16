# Contract: components (Milestone 12.5)

Each new or changed macro goes into the component library, the gallery (`/admin/components`) and
`ui-guidelines.md` before a page uses it (constitution Principle II).

## 1. `language_switch(current, return_to)` — new, `components/frame.html`

Called by `top_bar()` only; never by a page. `current` is the request's language code; `return_to`
the page's `return_path`.

```html
<details class="language-switch">
  <summary>
    <img src="/static/img/flag-ua.svg" alt="" class="flag">
    <span class="visually-hidden">{{ _("Language") }}</span>
    <span class="language-switch-name" lang="uk">Українська</span>
  </summary>
  <form method="post" action="/language" class="language-switch-panel">
    <input type="hidden" name="next" value="{{ return_to }}">
    <button type="submit" name="language" value="uk" lang="uk" aria-current="true">
      <img src="/static/img/flag-ua.svg" alt="" class="flag">Українська</button>
    <button type="submit" name="language" value="en" lang="en">
      <img src="/static/img/flag-gb.svg" alt="" class="flag">English</button>
  </form>
</details>
```

- The language names are not translated: each is written in its own language (FR-007).
- Below 768 px, `.language-switch-name` in the summary is visually hidden (still read).
- Each button is at least `--sc-touch-target` tall and wide.
- Styles: Components section of `app.css`, tokens only; one new size token, `--sc-flag-height`
  (a length, so it needs no dark-theme entries).
- Gallery section `#language`: the switch closed, and open (`<details open>`), in both states of
  `current`.

## 2. `top_bar()` — changed, `components/frame.html`

Order: brand (logo, wordmark), role label (signed in with a role), **language switch**, user menu
(signed in). Signed out: brand, language switch. Below 768 px the wordmark may be visually hidden
when a role is shown, if the frame measurement requires it (research R15); the logo link then
carries the application's name as its accessible name.

## 3. `theme_switch(current, return_to, standalone=False)` — texts only

Options **Light**, **Dark**, **Device** and its label become messages. Placement unchanged.

## 4. `local_time(moment, zone=time_zone)` and new `local_date(moment, zone=time_zone)` — `components/time.html`

`local_time` keeps its markup (`<time datetime="…Z">`) and calls the new `format_local_time` (Kyiv
fallback, labelled). `local_date` emits `<time datetime="YYYY-MM-DD">15 October 2026</time>` in the
same zone rules, no label. The `utc` filter is removed.

## 5. Date-time field — changed, `components/form.html`

The macro takes `date_label` and `time_label` as whole messages instead of building
`legend ~ " date"` / `legend ~ " time"`; the hint is `_("Time zone: %(zone)s", zone=zone_label)`.

## 6. Region group — changed, `components/group.html`

The header count is `ngettext("%(num)d team", "%(num)d teams", total)`.

## 6a. `status_badge(is_active, kind)` — changed, `components/badge.html`

Takes the kind of record (`subject`, `region`, `institution`, `class`; anything else →
`template_error`), so the Ukrainian word agrees with the record's noun: `pgettext(kind, "Active")`
is «Активний» for предмет, регіон, заклад освіти and «Активна» for група; `pgettext(kind,
"Deactivated")` is «Деактивовано» for all. Every caller passes its kind; the gallery shows each.

## 7. Consent text — new partial use in `pages/invitation.html` and `pages/profile.html`

```html
<section class="consent-text">
  <div lang="uk"><h3>Українською</h3>{% for p in parts.ukrainian %}<p>{{ p }}</p>{% endfor %}</div>
  <div lang="en"><h3>English</h3>{% for p in parts.english %}<p>{{ p }}</p>{% endfor %}</div>
</section>
```

The headings come from the stored text (they are part of the consented wording), not from the
catalogue.

## 8. Every component's own text

`Actions`, `Actions for “%(item)s”`, `There is a problem`, `Previous`, `Next`, `Skip to main
content`, `Account menu`, `Switch to`, `Log out`, badges and notices become messages. The page
navigation range is `_("%(noun)s %(first)d–%(last)d of %(total)d")`: the noun is the list's
standalone plural label («Питання», «Команди»), which never changes form in this position, so it may
be a `Text` parameter (contracts/i18n.md, rule 2).
