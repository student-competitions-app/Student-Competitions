# Components: Milestone 12.10

Constitution Principle II: each addition goes into the component library, the component gallery
(`/admin/components`) and `docs/requirements/ui-guidelines.md` **before** a page uses it.

## 1. `chained_lists(levels, action, aside=None)` (changed, `components/selectors.html`)

- **`aside`**: optional ready HTML, usually a `link_button`. It is rendered as one more cell of
  the `.selectors-chained` grid, after the levels, in a `<div class="selectors-aside">`.
- **Wide screens (≥ 768 px)**: the grid has three columns. The aside takes the next free cell,
  the third when there are two levels, and aligns with the bottom of the selects (`align-self:
  end`). Its own bottom margin is 0, so it lines up with the select.
- **Phones**: one column, so the aside comes after the levels, left-aligned. No sideways
  scrolling at 360 px.
- **Without `aside`**: the output is unchanged. Every existing use keeps its markup.
- **CSS**: `.selectors-aside` uses tokens only (`--sc-space-*`). The stylesheet checks of
  milestones 10 and 10.1 stay green.

**Gallery**: the selectors section shows the chained lists with two levels and an aside download
link.

**Guidelines** (Selectors): "A chained list may carry one aside: a link about the chosen value,
such as a download. It sits beside the lists on a wide screen and below them on a phone. It is
never a primary action."

## 2. `link_button(label, href, kind, outline, small, download=False)` (changed, `components/button.html`)

- **`download=True`** adds the HTML `download` attribute. The loading script of milestone 10.1
  already skips `a[download]`, so no loading feedback starts.
- **A download is never `destructive`**: `template_error` refuses the combination, as `menu_link`
  does.

**Gallery**: the buttons section shows a secondary outline small download link button.

**Guidelines** (Buttons and the download rule of 12.8): "A download outside a menu is a
`link_button(download=True)`, of the secondary kind. It opens no page and starts no loading
feedback."

## 3. The actions menu order (guidelines only)

The order becomes **Edit**, **Questions**, **Teams**, **Answers**, **Download questions**,
**Grades**, **Publish results**, **Download results**, **Finish competition**, **Cancel
competition**. The guidelines' example of `competitions.html` shows the **Download questions**
entry with `download=True`, and **Questions** under the setting.

## 4. Use on the Competitions tab

```jinja
{% set aside = link_button(_("Download study materials"),
     "/teacher/competitions/study-materials?subject=" ~ selected.id,
     kind="secondary", outline=True, small=True, download=True)
   if selected and selected.is_active else none %}
{{ chained_lists([subject_level, status_level], "/teacher/competitions", aside=aside) }}
```

Its look and place are approved by the product owner from screenshots (FR-048). A different
kind, size or wording decided in the rounds changes only this call and, if needed, §1–§2.
