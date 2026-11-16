# Contract: Static Assets — Icons, Manifest and the Image Folder (Milestone 12.7)

All files are served by the existing `/static` mount, to everyone, signed in or not. No route is added.

## 1. Served files

| URL | Status | `Content-Type` |
|---|---|---|
| `/static/img/logo/favicon.ico` | 200 | `image/x-icon` or `image/vnd.microsoft.icon` |
| `/static/img/logo/favicon-16.png`, `-32.png`, `-48.png` | 200 | `image/png` |
| `/static/img/logo/apple-touch-icon.png` | 200 | `image/png` |
| `/static/img/logo/icon-192.png`, `icon-512.png`, `icon-maskable-512.png` | 200 | `image/png` |
| `/static/img/logo/site.webmanifest` | 200 | `application/manifest+json` |
| `/static/img/logo/logo-{ink}-{px}.png` ([data-model.md](../data-model.md) §1) | 200 | `image/png` |
| `/static/img/favicon.svg`, `/static/img/favicon-32.png`, `/static/img/apple-touch-icon.png` | 404 | — (deleted) |
| `/static/img/logo/og-image.png`, `logo-{dark,light}-{256,512,1024}.png`, `logo-header-{32,64,96}.png` | 404 | — (deleted) |

`/favicon.ico` at the site root is not added and answers as it does today (out of scope).

## 2. Links on every page (`layouts/base.html`)

```html
<link rel="icon" href="/static/img/logo/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="icon" href="/static/img/logo/favicon-16.png" sizes="16x16" type="image/png">
<link rel="icon" href="/static/img/logo/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/static/img/logo/favicon-48.png" sizes="48x48" type="image/png">
<link rel="apple-touch-icon" href="/static/img/logo/apple-touch-icon.png">
<link rel="manifest" href="/static/img/logo/site.webmanifest">
```

Every page extends `base.html` (sign-in, area pages, profile, error and refusal pages), so every page
carries them.

## 3. The manifest

```json
{
  "name": "Студентські змагання",
  "start_url": "/",
  "display": "browser",
  "theme_color": "#16337a",
  "background_color": "#16337a",
  "icons": [
    {"src": "/static/img/logo/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/img/logo/icon-512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "/static/img/logo/icon-maskable-512.png", "sizes": "512x512", "type": "image/png",
     "purpose": "maskable"}
  ]
}
```

The file is written by the script in UTF-8, with the Cyrillic name not escaped, indented by two
spaces, and ending with a newline. The order of the keys is not part of the contract; their values
are.

## 4. The folder

`app/static/img/logo/` holds exactly the 28 files of [data-model.md](../data-model.md) §5. The set of
`/static/img/logo/…` URLs referred to by the sign-in page, the gallery in **Light** and in **Dark**,
and the manifest equals the folder's listing.

`app/static/img/` keeps `flag-gb.svg` and `flag-ua.svg` and the `logo/` folder, and nothing else.
