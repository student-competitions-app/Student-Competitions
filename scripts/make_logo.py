"""Make every logo image and the web manifest from the emblem's source image.

    uv run --group logo scripts/make_logo.py

It takes no arguments. It reads `docs/brand/logo-source.png` and writes exactly the files the
application uses to `app/static/img/logo/` (milestone 12.7 data-model.md §1, §3 and §4):

- the emblem in light ink (`#f4f5f8`) and dark ink (`#1c1c22`), `logo-{ink}-{px}.png`, at every
  displayed size at 1x, 2x and 3x, with the letters ЯНМ solid and the ornament engraved;
- the favicons, the Apple touch icon and the manifest icons: the letters ЯНМ alone, without the
  ornament, on `#16337a`, because at a tab's or a home screen's size the whole emblem blurs;
- `site.webmanifest`.

The letters are solid because the source has one layer for letters and ornament alike: the script
holds the letter area as data, in the source's pixels (`LETTER_BAND` less `NOT_LETTERS`), and lifts
the ink inside it to full (milestone 12.7 research R13). The area belongs to this source image: a
new source means drawing it again.

The icons' letters are cut out of the source by a rule held with the data (`CUT_*`, research R15):
the letters are the heaviest ink of their row, the ornament there is lighter or thinner. Its numbers
belong to this source too.

Then it deletes every other file in that folder, so the folder holds only what is used. The images
are always this script's output and are never edited by hand: to change one, change this script or
the source, run it and commit the folder as it left it.

Pillow and numpy are the `logo` dependency group, which neither CI nor the image installs
(milestone 12.7 contracts/logo-script.md, research R7 and R8).
"""

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/brand/logo-source.png"
OUT = ROOT / "app/static/img/logo"

NAVY = (0x16, 0x33, 0x7A)
INKS = {"light": (0xF4, 0xF5, 0xF8), "dark": (0x1C, 0x1C, 0x22)}

# The 1x, 2x and 3x of every displayed size (research R1): sm 24, md 32, lg 64 in both inks, and
# the top bar's 44 on a phone in light ink only, because the bar is dark in both themes.
SIZES = {
    "light": (24, 32, 44, 48, 64, 72, 88, 96, 128, 132, 192),
    "dark": (24, 32, 48, 64, 72, 96, 128, 192),
}
# Sizes at and below this get their alpha sharpened, so thin engraved strokes do not wash out.
SMALL = 48

# The letters ЯНМ in the source's pixels (311 x 311), checked on gridded overlays of the source
# (research R13): the row of letters, less the ornament inside it. The boxes between the stems sit
# 2 px inside the panels, so the stems keep their dark outline.
LETTER_BAND = (58, 116, 248, 192)  # x0, y0, x1, y1
NOT_LETTERS = (
    ((48, 141), (79, 141), (79, 165), (48, 165)),  # the left side flourish
    ((239, 141), (265, 141), (265, 165), (239, 165)),  # the right side flourish
    ((121, 121), (131, 121), (131, 189), (121, 189)),  # the fleur and dots between Я and Н
    ((149, 122), (158, 122), (158, 146), (149, 146)),  # the dots inside Н, above its bar
    ((149, 159), (158, 159), (158, 190), (149, 190)),  # the dots inside Н, below its bar
    ((173, 121), (187, 121), (187, 189), (173, 189)),  # the fleur and dots between Н and М
    ((203, 110), (221, 110), (214, 149), (209, 149)),  # the fleur between М's peaks
)
# Inside the letters, ink at this coverage or more becomes full ink: the shading stops letting the
# background through, while each letter's outline and inline (no ink) keep their shape.
LETTER_LIFT = 0.45

# The letters alone, for the icons (research R15), in the source's pixels: the row of letters as
# rows and columns (end exclusive), less where the right flourish's stem meets М.
CUT_BAND = (118, 192, 58, 249)  # y0, y1, x0, x1
CUT_NOT_LETTERS = ((141, 164, 240, 249),)  # y0, y1, x0, x1
# The letters' heavy ink: the fleurs-de-lis, dots, curls and rod are lighter than this.
CUT_HEAVY = 120
# Pieces of this many pixels or fewer are ornament that passed the threshold.
CUT_SMALLEST_PIECE = 120
# Grown back this many pixels, inside the source's ink, to the letters' own edge.
CUT_GROW = 2
# Holes smaller than this, inside the letters, are their engraved inline.
CUT_LARGEST_HOLE = 40

MANIFEST = {
    "name": "Студентські змагання",
    "start_url": "/",
    "display": "browser",
    "theme_color": "#16337a",
    "background_color": "#16337a",
    "icons": [
        {"src": "/static/img/logo/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/img/logo/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {
            "src": "/static/img/logo/icon-maskable-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
    ],
}


def gaussian_blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Blur a float image with a separable, normalised Gaussian kernel and edge padding."""
    r = math.ceil(3 * sigma)
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x**2) / (2 * sigma**2))
    k /= k.sum()
    h, w = a.shape
    p = np.pad(a, ((r, r), (0, 0)), mode="edge")
    a = sum(k[i] * p[i : i + h] for i in range(2 * r + 1))
    p = np.pad(a, ((0, 0), (r, r)), mode="edge")
    return sum(k[i] * p[:, i : i + w] for i in range(2 * r + 1))


def unsharp(a: np.ndarray, amount: float, sigma: float) -> np.ndarray:
    return np.clip(a + amount * (a - gaussian_blur(a, sigma)), 0, 255)


def bilateral(a: np.ndarray, size: int = 7, sigma_range: float = 18, sigma_space: float = 5):
    """Edge-preserving smoothing: each pixel becomes the mean of its window, weighted by distance
    and by how close each neighbour's value is to its own."""
    r = size // 2
    h, w = a.shape
    p = np.pad(a, r, mode="edge")
    total = np.zeros_like(a)
    weights = np.zeros_like(a)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            shifted = p[r + dy : r + dy + h, r + dx : r + dx + w]
            weight = np.exp(-(dx * dx + dy * dy) / (2 * sigma_space**2)) * np.exp(
                -((shifted - a) ** 2) / (2 * sigma_range**2)
            )
            total += weight * shifted
            weights += weight
    return total / weights


def up2(a: np.ndarray) -> np.ndarray:
    """Double the size with Lanczos, then sharpen lightly: crisper than one large jump."""
    h, w = a.shape
    big = Image.fromarray(a.astype(np.float32), "F").resize((w * 2, h * 2), Image.LANCZOS)
    return unsharp(np.asarray(big, dtype=np.float32), 0.6, 1.2)


def letter_area(lum: np.ndarray) -> np.ndarray:
    """The letters ЯНМ of the source as a boolean mask in its pixels: the ink inside the band,
    closed so the light inline of each stroke is no gap, less the ornament's polygons."""
    ink = Image.fromarray(((lum < 215) * 255).astype(np.uint8), "L")
    ink = ink.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    keep = Image.new("L", ink.size, 0)
    draw = ImageDraw.Draw(keep)
    draw.rectangle(LETTER_BAND, fill=255)
    for polygon in NOT_LETTERS:
        draw.polygon(polygon, fill=0)
    return (np.asarray(ink) > 0) & (np.asarray(keep) > 0)


def filtered(mask: np.ndarray, *filters: ImageFilter.Filter) -> np.ndarray:
    img = Image.fromarray((mask * 255).astype(np.uint8), "L")
    for f in filters:
        img = img.filter(f)
    return np.asarray(img) > 0


def pieces(mask: np.ndarray) -> tuple[np.ndarray, dict[int, int]]:
    """The 4-connected pieces of a mask: a label per pixel (0 outside) and each label's size."""
    labels = np.zeros(mask.shape, np.int32)
    sizes: dict[int, int] = {}
    h, w = mask.shape
    for y, x in zip(*np.nonzero(mask), strict=True):
        if labels[y, x]:
            continue
        label = len(sizes) + 1
        labels[y, x], stack, size = label, [(y, x)], 0
        while stack:
            a, b = stack.pop()
            size += 1
            for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= c < h and 0 <= d < w and mask[c, d] and not labels[c, d]:
                    labels[c, d] = label
                    stack.append((c, d))
        sizes[label] = size
    return labels, sizes


def letters_alone(lum: np.ndarray) -> np.ndarray:
    """The letters ЯНМ without any of the ornament, as a boolean mask in the source's pixels."""
    band = np.zeros(lum.shape, bool)
    y0, y1, x0, x1 = CUT_BAND
    band[y0:y1, x0:x1] = True
    for y0, y1, x0, x1 in CUT_NOT_LETTERS:
        band[y0:y1, x0:x1] = False
    # The heavy ink, its inline closed, then opened so the rod and the hairlines go.
    heavy = filtered(lum < CUT_HEAVY, ImageFilter.MaxFilter(3), ImageFilter.MinFilter(3))
    heavy = filtered(heavy, ImageFilter.MinFilter(3), ImageFilter.MaxFilter(3)) & band
    labels, sizes = pieces(heavy)
    letters = np.isin(labels, [k for k, n in sizes.items() if n > CUT_SMALLEST_PIECE])
    for _ in range(CUT_GROW):
        letters = filtered(letters, ImageFilter.MaxFilter(3)) & (lum < 215) & band
    labels, sizes = pieces(~letters)
    return letters | np.isin(labels, [k for k, n in sizes.items() if n < CUT_LARGEST_HOLE])


def soft_mask(mask: np.ndarray) -> np.ndarray:
    """A mask in the source's pixels at the master's scale (×8), softened by about half a source
    pixel, from 0 to 1."""
    h, w = mask.shape
    big = Image.fromarray(mask.astype(np.float32) * 255, "F").resize((w * 8, h * 8), Image.BILINEAR)
    return np.clip(gaussian_blur(np.asarray(big, dtype=np.float32), 3.0) / 255.0, 0, 1)


def squared(coverage: np.ndarray) -> np.ndarray:
    """The coverage centred on a square of its larger side."""
    h, w = coverage.shape
    side = max(h, w)
    square = np.zeros((side, side), np.float32)
    top, left = (side - h) // 2, (side - w) // 2
    square[top : top + h, left : left + w] = coverage
    return square


def coverage_masters() -> tuple[np.ndarray, np.ndarray]:
    """The ink coverage (0 paper, 1 full ink) on large squares: the emblem, centred, with the
    letters' ink lifted to full; and the letters alone, the same lifted letters cropped to their
    ink, for the icons."""
    src = Image.open(SRC).convert("RGBA")
    # The source has stray transparent pixels with black RGB: flatten it onto white first.
    flat = Image.alpha_composite(Image.new("RGBA", src.size, (255, 255, 255, 255)), src)
    lum = np.asarray(flat.convert("L"), dtype=np.float32)

    ys, xs = np.where(lum < 240)
    x0, x1 = max(int(xs.min()) - 3, 0), min(int(xs.max()) + 4, lum.shape[1])
    y0, y1 = max(int(ys.min()) - 3, 0), min(int(ys.max()) + 4, lum.shape[0])
    hi = lum[y0:y1, x0:x1]
    letters = letter_area(lum)[y0:y1, x0:x1]
    alone = letters_alone(lum)[y0:y1, x0:x1]
    print(f"crop {(x0, y0, x1, y1)} -> {hi.shape[1]}x{hi.shape[0]}")

    for _ in range(3):
        hi = up2(hi)
    # Calm the ringing the sharpening adds, then sharpen once more, finer.
    hi = unsharp(bilateral(hi), 0.8, 2.0)

    # Levels: anything lighter than 232 is paper, the blacks deepen, and a slight gamma brings the
    # engraved mid-tones forward.
    n = np.clip((hi - 25.0) / (232.0 - 25.0), 0, 1) ** (1 / 0.9)
    coverage = 1.0 - n
    coverage[coverage < 0.02] = 0

    lifted = np.clip(coverage / LETTER_LIFT, 0, 1)
    soft = soft_mask(letters)
    emblem = squared(soft * lifted + (1 - soft) * coverage)
    only = soft_mask(alone) * lifted
    ys, xs = np.nonzero(only > 0.02)
    only = squared(only[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1])
    print(f"master {emblem.shape[0]} px, letters alone {only.shape[0]} px")
    return emblem, only


def ink_image(coverage: np.ndarray, ink: tuple[int, int, int]) -> Image.Image:
    alpha = (coverage * 255).round().astype(np.uint8)
    rgb = np.empty(coverage.shape + (3,), np.uint8)
    rgb[...] = ink
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def resized(img: Image.Image, size: int) -> Image.Image:
    # Pillow resizes RGBA premultiplied, so the alpha edge gets no dark or light fringe.
    return img.resize((size, size), Image.LANCZOS, reducing_gap=3.0)


def small_sharpen(img: Image.Image, amount: float) -> Image.Image:
    """Extra crispness for tiny sizes, applied to the alpha only."""
    a = np.asarray(img.getchannel("A"), np.float32)
    # Sharpen, then lift the alpha so thin engraved strokes do not wash out.
    a = np.clip((a + amount * (a - gaussian_blur(a, 0.6))) * 1.35, 0, 255).astype(np.uint8)
    out = img.copy()
    out.putalpha(Image.fromarray(a, "L"))
    return out


def tile(mark: Image.Image, size: int, pad: float, radius: float, sharpen: float = 0.0):
    """A mark on an opaque navy square, with rounded corners when `radius` is set."""
    if radius:
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, size * 4 - 1, size * 4 - 1), radius=int(size * 4 * radius), fill=255
        )
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(
            Image.new("RGBA", (size, size), NAVY + (255,)),
            (0, 0),
            mask.resize((size, size), Image.LANCZOS),
        )
    else:
        canvas = Image.new("RGBA", (size, size), NAVY + (255,))
    inner = round(size * (1 - 2 * pad))
    emblem = resized(mark, inner)
    if sharpen:
        emblem = small_sharpen(emblem, sharpen)
    offset = (size - inner) // 2
    canvas.alpha_composite(emblem, (offset, offset))
    return canvas


def main() -> None:
    coverage, letters = coverage_masters()
    masters = {ink: ink_image(coverage, rgb) for ink, rgb in INKS.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def save(img: Image.Image, name: str, **params) -> None:
        img.save(OUT / name, optimize=True, **params)
        written.append(name)

    # The emblem, transparent, filling its square edge to edge.
    for ink, sizes in SIZES.items():
        for size in sizes:
            img = resized(masters[ink], size)
            if size <= SMALL:
                img = small_sharpen(img, 0.8)
            save(img, f"logo-{ink}-{size}.png")

    # The icons show the letters alone. Favicons: a rounded navy tile with little padding, so the
    # letters are as large as a tab allows.
    light = ink_image(letters, INKS["light"])
    favicons = {
        s: tile(light, s, 0.04, 0.22, sharpen=1.0 if s <= 32 else 0.4) for s in (16, 32, 48)
    }
    for size, img in favicons.items():
        save(img, f"favicon-{size}.png")
    favicons[48].save(
        OUT / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[favicons[16], favicons[32]],
    )
    written.append("favicon.ico")

    # Platform icons: full-bleed squares, because the system applies its own mask. The maskable
    # icon keeps the letters inside the central 80 % safe-zone circle.
    save(tile(light, 180, 0.08, 0).convert("RGB"), "apple-touch-icon.png")
    save(tile(light, 192, 0.06, 0), "icon-192.png")
    save(tile(light, 512, 0.06, 0), "icon-512.png")
    save(tile(light, 512, 0.15, 0), "icon-maskable-512.png")

    (OUT / "site.webmanifest").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    written.append("site.webmanifest")

    for name in written:
        print(f"wrote {name}")
    # Only after every write has succeeded: the folder holds exactly what this run wrote.
    for path in sorted(OUT.iterdir()):
        if path.name not in written:
            path.unlink()
            print(f"removed {path.name}")


if __name__ == "__main__":
    main()
