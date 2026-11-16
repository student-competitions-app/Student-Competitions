"""The logo's files: the icons and the web manifest (specs/012.7-new-logo FR-013–FR-017;
contracts/static-assets.md).

Every icon, the Apple touch icon and the manifest are static files under `/static/img/logo/`,
written by `scripts/make_logo.py` and served to everyone, signed in or not, with their types. The
manifest opens the application in the browser. Every test runs once per database engine.
"""

import json

import pytest
from fastapi.testclient import TestClient

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
