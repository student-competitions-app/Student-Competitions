"""Turn the 311px monogram into a set of logo assets.

usage: make_logo.py SRC OUT_DIR WORK_DIR
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SRC, OUT, WORK = (Path(p) for p in sys.argv[1:4])
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

NAVY = (0x16, 0x33, 0x7A)
DARK_INK = (0x1C, 0x1C, 0x22)
LIGHT_INK = (0xF4, 0xF5, 0xF8)

# 1. Flatten onto white (the source has stray transparent pixels with black RGB).
src = Image.open(SRC).convert("RGBA")
flat = Image.alpha_composite(Image.new("RGBA", src.size, (255, 255, 255, 255)), src)
L = np.asarray(flat.convert("L"), dtype=np.float32)

# 2. Tight crop around the ink (L < 240), with a 3px margin.
ys, xs = np.where(L < 240)
x0, x1 = max(xs.min() - 3, 0), min(xs.max() + 4, L.shape[1])
y0, y1 = max(ys.min() - 3, 0), min(ys.max() + 4, L.shape[0])
L = L[y0:y1, x0:x1]
print("crop", (x0, y0, x1, y1), "->", L.shape[::-1])

# 3. Staged 2x upscales with a light unsharp mask after each step: keeps
#    edges crisper than one big Lanczos jump.
def up2(img):
    h, w = img.shape
    big = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(big, (0, 0), 1.2)
    return np.clip(big + 0.6 * (big - blur), 0, 255)

hi = L.copy()
for _ in range(3):  # ~212px -> ~1700px
    hi = up2(hi)
# Edge-preserving smoothing to calm the ringing/noise the sharpening adds,
# then a final, finer sharpen.
hi = cv2.bilateralFilter(hi.astype(np.float32), 7, 18, 5)
blur = cv2.GaussianBlur(hi, (0, 0), 2.0)
hi = np.clip(hi + 0.8 * (hi - blur), 0, 255)

# 4. Levels: anything lighter than 232 is paper (-> white), deepen the blacks,
#    slight gamma to bring the engraved mid-tones forward.
lo_pt, hi_pt, gamma = 25.0, 232.0, 0.9
n = np.clip((hi - lo_pt) / (hi_pt - lo_pt), 0, 1) ** (1 / gamma)
coverage = 1.0 - n  # 0 = paper, 1 = full ink
coverage[coverage < 0.02] = 0

# Pad to a square master so every derived size keeps the emblem centred.
h, w = coverage.shape
side = max(h, w)
sq = np.zeros((side, side), np.float32)
sq[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = coverage
coverage = sq
print("master", coverage.shape)


def ink_rgba(cov, ink):
    a = (cov * 255).round().astype(np.uint8)
    rgb = np.empty(cov.shape + (3,), np.uint8)
    rgb[...] = ink
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


def resized(img, size):
    # Resize premultiplied to avoid dark/light fringes on the alpha edge.
    return img.resize((size, size), Image.LANCZOS, reducing_gap=3.0)


def small_sharpen(img, amount):
    """Extra crispness for tiny sizes (favicons), applied to alpha only."""
    a = np.asarray(img.getchannel("A"), np.float32)
    blur = cv2.GaussianBlur(a, (0, 0), 0.6)
    # Sharpen, then lift the alpha so thin engraved strokes don't wash out.
    a = np.clip((a + amount * (a - blur)) * 1.35, 0, 255).astype(np.uint8)
    out = img.copy()
    out.putalpha(Image.fromarray(a))
    return out


master_dark = ink_rgba(coverage, DARK_INK)
master_light = ink_rgba(coverage, LIGHT_INK)
master_dark.save(WORK / "master-dark.png")

# 5. Transparent logos (square canvas, emblem fills it edge to edge).
for size in (1024, 512, 256):
    resized(master_dark, size).save(OUT / f"logo-dark-{size}.png", optimize=True)
    resized(master_light, size).save(OUT / f"logo-light-{size}.png", optimize=True)

# Header mark (top bar is navy -> light ink), 1x/2x/3x of the 32px slot.
for size in (32, 64, 96):
    im = resized(master_light, size)
    if size == 32:
        im = small_sharpen(im, 0.8)
    im.save(OUT / f"logo-header-{size}.png", optimize=True)


def tile(size, pad_frac, radius_frac, bg=NAVY, ink=master_light, sharpen=0.0):
    """Emblem on an opaque rounded (or square) navy tile."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if radius_frac:
        mask = Image.new("L", (size * 4, size * 4), 0)
        from PIL import ImageDraw
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, size * 4 - 1, size * 4 - 1), radius=int(size * 4 * radius_frac), fill=255
        )
        mask = mask.resize((size, size), Image.LANCZOS)
        canvas.paste(Image.new("RGBA", (size, size), bg + (255,)), (0, 0), mask)
    else:
        canvas = Image.new("RGBA", (size, size), bg + (255,))
    inner = round(size * (1 - 2 * pad_frac))
    mark = resized(ink, inner)
    if sharpen:
        mark = small_sharpen(mark, sharpen)
    off = (size - inner) // 2
    canvas.alpha_composite(mark, (off, off))
    return canvas


# 6. Favicons: rounded navy tile like the current favicon.svg, minimal padding
#    so the emblem is as large as possible.
fav = {s: tile(s, 0.02, 0.22, sharpen=1.0 if s <= 32 else 0.4) for s in (16, 32, 48)}
fav[32].save(OUT / "favicon-32.png", optimize=True)
fav[16].save(OUT / "favicon-16.png", optimize=True)
fav[48].save(OUT / "favicon-48.png", optimize=True)
fav[48].save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
             append_images=[fav[16], fav[32]])

# 7. Platform icons: full-bleed square (OSes apply their own mask).
tile(180, 0.08, 0).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)
tile(192, 0.06, 0).save(OUT / "icon-192.png", optimize=True)
tile(512, 0.06, 0).save(OUT / "icon-512.png", optimize=True)
# Maskable: emblem within the 80% safe-zone circle -> diamond fits at ~70%.
tile(512, 0.15, 0).save(OUT / "icon-maskable-512.png", optimize=True)

# 8. Social preview 1200x630: navy, emblem centred.
og = Image.new("RGBA", (1200, 630), NAVY + (255,))
mark = resized(master_light, 500)
og.alpha_composite(mark, ((1200 - 500) // 2, (630 - 500) // 2))
og.convert("RGB").save(OUT / "og-image.png", optimize=True)

(OUT / "site.webmanifest").write_text(json.dumps({
    "icons": [
        {"src": "/static/img/logo/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/img/logo/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/static/img/logo/icon-maskable-512.png", "sizes": "512x512",
         "type": "image/png", "purpose": "maskable"},
    ],
    "theme_color": "#16337a",
    "background_color": "#16337a",
    "display": "standalone",
}, indent=2) + "\n")

print("done")
