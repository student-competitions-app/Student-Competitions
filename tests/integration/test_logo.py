"""The logo's files: the icons and the web manifest (specs/012.7-new-logo FR-013–FR-017;
contracts/static-assets.md).

Every icon, the Apple touch icon and the manifest are static files under `/static/img/logo/`,
written by `scripts/make_logo.py` and served to everyone, signed in or not, with their types. The
manifest opens the application in the browser. The folder holds exactly what the pages use
(FR-018, FR-019), and nothing in the code or the tests still refers to the old mark (FR-028,
FR-029). Every test runs once per database engine.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests import html

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

LOGO = "/static/img/logo/"

ICON_LINKS = [
    ("icon", f"{LOGO}favicon.ico"),
    ("icon", f"{LOGO}favicon-16.png"),
    ("icon", f"{LOGO}favicon-32.png"),
    ("icon", f"{LOGO}favicon-48.png"),
    ("apple-touch-icon", f"{LOGO}apple-touch-icon.png"),
    ("manifest", f"{LOGO}site.webmanifest"),
]
"""The six links on every page (contracts/static-assets.md §2)."""

MANIFEST_ICONS = [
    {"src": f"{LOGO}icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": f"{LOGO}icon-512.png", "sizes": "512x512", "type": "image/png"},
    {
        "src": f"{LOGO}icon-maskable-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable",
    },
]
"""The manifest's icons (contracts/static-assets.md §3)."""

ICON_URLS = list(
    dict.fromkeys([href for _, href in ICON_LINKS] + [i["src"] for i in MANIFEST_ICONS])
)


def media_type(content_type: str) -> str:
    return content_type.split(";")[0].strip()


@pytest.mark.parametrize("url", ICON_URLS)
def test_every_icon_and_the_manifest_answer_to_a_signed_out_visitor(
    client: TestClient, url: str
) -> None:
    """FR-016, FR-017: each file answers a visitor who is not signed in, with its type; a
    system's table may name the ICO either way."""
    response = client.get(url)
    assert response.status_code == 200
    kind = media_type(response.headers["content-type"])
    if url.endswith(".png"):
        assert kind == "image/png"
    elif url.endswith(".ico"):
        assert kind in ("image/x-icon", "image/vnd.microsoft.icon")
    else:
        assert response.headers["content-type"].startswith("application/manifest+json")


def test_the_manifest_opens_the_application_in_the_browser(client: TestClient) -> None:
    """FR-014, FR-016: the manifest names the application, opens `/` in the browser with its
    address bar, and lists the three icons, each served as a PNG."""
    manifest = json.loads(client.get(f"{LOGO}site.webmanifest").content.decode("utf-8"))
    assert manifest["name"] == "Студентські змагання"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "browser"
    assert manifest["theme_color"] == manifest["background_color"] == "#16337a"
    assert manifest["icons"] == MANIFEST_ICONS
    for icon in manifest["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200
        assert media_type(response.headers["content-type"]) == "image/png"


def logo_urls(body: str) -> set[str]:
    """Every `/static/img/logo/` URL in a page's `src`, `srcset` and `href` attributes."""
    urls = set()
    for element in html.parse(body).iter():
        candidates = [element.attrs.get("src", ""), element.attrs.get("href", "")]
        candidates += [
            c.split()[0] for c in element.attrs.get("srcset", "").split(",") if c.strip()
        ]
        urls |= {url for url in candidates if url.startswith(LOGO)}
    return urls


def test_the_logo_folder_holds_only_what_is_used(
    client: TestClient, admin_client: TestClient
) -> None:
    """FR-018, FR-019, SC-006: the sign-in page, the gallery in Light and in Dark and the manifest
    refer to exactly the files of the folder: none is missing, none is unused."""
    used = logo_urls(client.get("/login").text)
    for theme in ("light", "dark"):
        admin_client.cookies.set("sc_theme", theme)
        used |= logo_urls(admin_client.get("/admin/components").text)
    manifest = json.loads(client.get(f"{LOGO}site.webmanifest").content.decode("utf-8"))
    used |= {icon["src"] for icon in manifest["icons"]} | {f"{LOGO}site.webmanifest"}

    used_names = {url.removeprefix(LOGO) for url in used}
    folder = {path.name for path in (APP / "static/img/logo").iterdir()}
    assert used_names == folder, (
        f"unused in the folder: {sorted(folder - used_names)}; "
        f"missing from the folder: {sorted(used_names - folder)}"
    )


# Built from parts, so this file does not match itself.
OLD_MARK = [
    "/static/img/" + "favicon.svg",
    "/static/img/" + "favicon-32.png",
    "/static/img/" + "apple-touch-icon.png",
    "logo-mark-" + "tile",
    "logo-mark-" + "spark",
]


def text_files(*folders: Path) -> list[Path]:
    found = []
    for folder in folders:
        for path in folder.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".mo":
                continue
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            found.append(path)
    return found


def test_nothing_refers_to_the_old_mark(client: TestClient) -> None:
    """FR-028, FR-029, FR-036, SC-008: no code or test serves, draws or links the spark, its tile
    or the old favicons, and the old favicon is gone."""
    files = text_files(APP, ROOT / "tests")
    assert files
    offending = sorted(
        f"{path.relative_to(ROOT)}: {old}"
        for path in files
        for old in OLD_MARK
        if old in path.read_text(encoding="utf-8")
    )
    assert offending == []
    assert client.get("/static/img/" + "favicon.svg").status_code == 404
