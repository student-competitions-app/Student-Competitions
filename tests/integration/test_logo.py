"""The logo's files: the icons and the web manifest (specs/012.7-new-logo FR-013–FR-017;
contracts/static-assets.md).

Every icon, the Apple touch icon and the manifest are static files under `/static/img/logo/`,
written by `scripts/make_logo.py` and served to everyone, signed in or not, with their types. The
manifest opens the application in the browser. The folder holds exactly what the pages use
(FR-018, FR-019), the emblem's letters are solid while its ornament is engraved (FR-041, FR-043),
the icons show the letters ЯНМ alone, without the ornament (FR-044, FR-046), and nothing in the code or the tests still refers to the old mark (FR-028, FR-029). Every test that
takes a client runs once per database engine.
"""

import json
import struct
import zlib
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


def png_pixels(path: Path) -> list[bytes]:
    """The pixels of a PNG, one row of RGBA bytes per item, read with the standard library alone:
    CI installs no image library (research R14, R16). Only the type `make_logo.py` writes is
    accepted, 8-bit RGBA, not interlaced, so a change in how the images are written fails loudly."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    pos, header, compressed = 8, None, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed += body
        pos += 12 + length
    width, height, depth, colour, _, _, interlace = header
    assert (depth, colour, interlace) == (8, 6, 0), f"{path.name}: not 8-bit RGBA, not interlaced"
    raw, stride, bpp = zlib.decompress(compressed), width * 4, 4
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            up = previous[i]
            corner = previous[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[i] = (
                    line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)
                ) & 0xFF
            else:
                assert kind == 0, f"{path.name}: unknown row filter {kind}"
        rows.append(bytes(line))
        previous = line
    return rows


def png_alpha(path: Path) -> list[bytes]:
    """The alpha channel of a PNG, one row per item."""
    return [row[3::4] for row in png_pixels(path)]


# Sample points as fractions of the emblem image's side, picked on the reviewed option B and checked
# on an overlay (research R14): the middle of each letter's widest stroke, and ornament ink around.
LETTER_POINTS = {
    "Я's stem": (0.303, 0.546),
    "Н's left stem": (0.436, 0.569),
    "Н's right stem": (0.555, 0.569),
    "М's right stem": (0.853, 0.560),
}
ORNAMENT_POINTS = {
    "the loop above the letters": (0.303, 0.261),
    "the loop below the letters": (0.367, 0.679),
    "the fleur-de-lis between Я and Н": (0.367, 0.541),
    "the left flourish": (0.078, 0.495),
}
OPAQUE = 250
"""Opaque to the eye (98 %): the downscale leaves 1–2 % dips along the finest engraved lines."""
ENGRAVED = 240
"""The ornament's ink stays partly transparent, clearly below the letters."""


@pytest.mark.parametrize("name", ["logo-light-132.png", "logo-dark-192.png"])
def test_the_letters_are_solid_and_the_ornament_engraved(name: str) -> None:
    """FR-041, FR-043, SC-011: in both inks, every point inside the letters ЯНМ is opaque, with its
    neighbours, and every point in the ornament is inked but partly transparent."""
    alpha = png_alpha(APP / "static/img/logo" / name)
    side = len(alpha)

    def around(point: tuple[float, float]) -> list[int]:
        x, y = int(point[0] * side), int(point[1] * side)
        return [alpha[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]

    see_through = {k: min(around(p)) for k, p in LETTER_POINTS.items() if min(around(p)) < OPAQUE}
    assert see_through == {}, f"{name}: letters let the background through: {see_through}"
    solid = {k: max(around(p)) for k, p in ORNAMENT_POINTS.items() if max(around(p)) > ENGRAVED}
    assert solid == {}, f"{name}: ornament turned solid: {solid}"
    blank = {k: alpha[int(p[1] * side)][int(p[0] * side)] for k, p in ORNAMENT_POINTS.items()}
    assert all(value > 0 for value in blank.values()), (
        f"{name}: a point misses the ornament: {blank}"
    )


NAVY = (0x16, 0x33, 0x7A)
LIGHT_INK = (0xF4, 0xF5, 0xF8)
NEAR = 8
"""How far from the light ink a point inside the letters may be, per channel (resampling)."""
ICONS = {
    # The letters' widest strokes as fractions of the icon's side, and the letters' top and bottom
    # rows: picked on the reviewed option B and checked on an overlay (research R16). The two icons
    # differ in padding (6 % and 15 % a side).
    "icon-512.png": {
        "points": {
            "Я's stem": (0.295, 0.44),
            "Н's left stem": (0.441, 0.44),
            "Н's right stem": (0.545, 0.44),
            "М's right stem": (0.855, 0.44),
        },
        "letters": (0.31, 0.69),
    },
    "icon-maskable-512.png": {
        "points": {
            "Я's stem": (0.338, 0.453),
            "Н's left stem": (0.454, 0.453),
            "Н's right stem": (0.537, 0.453),
            "М's right stem": (0.783, 0.453),
        },
        "letters": (0.35, 0.65),
    },
}
MARGIN = 4
"""Rows next to the letters left out of the no-ornament check, for the resampling's spread."""


@pytest.mark.parametrize("name", sorted(ICONS))
def test_the_icons_show_the_letters_alone(name: str) -> None:
    """FR-044, FR-046, SC-012: the icons show the letters ЯНМ in light ink, and nothing of the
    ornament: the rows above and below the letters, where the emblem's loops and fleurs-de-lis are,
    hold only the deep blue."""
    rows = png_pixels(APP / "static/img/logo" / name)
    side = len(rows)

    def pixel(x: int, y: int) -> tuple[int, ...]:
        return tuple(rows[y][4 * x : 4 * x + 4])

    not_ink = {}
    for letter, (fx, fy) in ICONS[name]["points"].items():
        x, y = int(fx * side), int(fy * side)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                r, g, b, a = pixel(x + dx, y + dy)
                if a != 255 or max(abs(c - i) for c, i in zip((r, g, b), LIGHT_INK)) > NEAR:
                    not_ink[letter] = (r, g, b, a)
    assert not_ink == {}, f"{name}: the letters are not the light ink: {not_ink}"

    top, bottom = ICONS[name]["letters"]
    outside = [*range(int(top * side) - MARGIN), *range(int(bottom * side) + MARGIN + 1, side)]
    inked = [y for y in outside if rows[y] != bytes(NAVY + (255,)) * side]
    assert inked == [], f"{name}: ornament above or below the letters, in rows {inked[:5]}…"
