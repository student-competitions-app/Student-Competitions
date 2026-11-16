"""Make every logo image and the web manifest from the emblem's source image.

    uv run --group logo scripts/make_logo.py

It takes no arguments. It reads `docs/brand/logo-source.png` and writes exactly the files the
application uses to `app/static/img/logo/` (milestone 12.7 data-model.md §1, §3 and §4):

- the emblem in light ink (`#f4f5f8`) and dark ink (`#1c1c22`), `logo-{ink}-{px}.png`, at every
  displayed size at 1x, 2x and 3x;
- the favicons, the Apple touch icon and the manifest icons, the emblem on `#16337a`;
- `site.webmanifest`.

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
from PIL import Image, ImageDraw

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


def coverage_master() -> np.ndarray:
    """The emblem's ink coverage (0 paper, 1 full ink) on a large square, centred."""
    src = Image.open(SRC).convert("RGBA")
    # The source has stray transparent pixels with black RGB: flatten it onto white first.
    flat = Image.alpha_composite(Image.new("RGBA", src.size, (255, 255, 255, 255)), src)
    lum = np.asarray(flat.convert("L"), dtype=np.float32)

    ys, xs = np.where(lum < 240)
    x0, x1 = max(int(xs.min()) - 3, 0), min(int(xs.max()) + 4, lum.shape[1])
    y0, y1 = max(int(ys.min()) - 3, 0), min(int(ys.max()) + 4, lum.shape[0])
    hi = lum[y0:y1, x0:x1]
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

    h, w = coverage.shape
    side = max(h, w)
    square = np.zeros((side, side), np.float32)
    top, left = (side - h) // 2, (side - w) // 2
    square[top : top + h, left : left + w] = coverage
    print(f"master {side}x{side}")
    return square


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
    """The emblem on an opaque navy square, with rounded corners when `radius` is set."""
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
    coverage = coverage_master()
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

    # Favicons: a rounded navy tile with minimal padding, so the emblem is as large as possible.
    light = masters["light"]
    favicons = {
        s: tile(light, s, 0.02, 0.22, sharpen=1.0 if s <= 32 else 0.4) for s in (16, 32, 48)
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
    # icon keeps the emblem inside the central 80 % safe-zone circle.
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
