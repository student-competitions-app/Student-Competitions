# Contract: The Logo Script and Its Dependency Group (Milestone 12.7)

## Command

```sh
uv run --group logo scripts/make_logo.py
```

- **No arguments.** It reads `docs/brand/logo-source.png` and writes `app/static/img/logo/`, with both
  paths resolved from the script's own location, so it runs from any working directory.
- **Exit 0** after writing every file. On failure (a missing source, a write error), it exits non-zero
  through the uncaught exception, and the folder's existing files are kept: the stray-file cleanup runs
  only after every write succeeded.
- **Output** on stdout: the crop box and master size, then one line per file written, then the files
  removed.

## Behaviour

1. Flattens the source onto white and crops to the ink plus a 3 px margin.
2. Upscales ×2 three times (Lanczos, then an unsharp mask after each step). Applies edge-preserving
   smoothing and a final unsharp mask. Applies levels, so the paper becomes transparent (coverage →
   alpha). Pads the result to a square master.
   Then makes the letters ЯНМ solid: inside the letter area (research R13), held in the script as data
   in the source's pixels, the coverage is lifted, `min(c / 0.45, 1)`; outside it, the ornament is
   unchanged.
3. Writes the 19 emblem images (light ink `#f4f5f8`, dark ink `#1c1c22`), sharpening the alpha of
   sizes of 48 px and below.
4. Writes the 8 icons on `#16337a` and `site.webmanifest`
   ([static-assets.md](./static-assets.md) §3).
5. Deletes every other file in `app/static/img/logo/`.

The letter area belongs to the current `docs/brand/logo-source.png`. If the source changes, the area
is drawn again, and the opacity test (research R14) shows whether it still fits.

The images are always this script's output. A committed image is never edited by hand. To change one,
change the script or the source, run the script and commit its output.

## Libraries

- `PIL` (Pillow) and `numpy` only, plus the standard library. No `cv2`.
- The resizing is Pillow `Image.resize(…, Image.LANCZOS)`, on float (`F`) images for the master and on
  RGBA for the outputs.
- The Gaussian blur and the bilateral filter are numpy (research R7).

## `pyproject.toml` and `uv.lock`

```toml
[dependency-groups]
dev = ["pytest", "httpx2", "ruff"]
logo = ["numpy>=2.1", "pillow>=11.1"]
```

- `uv lock` records the group in `uv.lock`, and `uv lock --check` passes.
- `default-groups` is not set, so:
  - `uv sync --locked` (CI) installs the project and `dev` only;
  - `uv sync --locked --no-dev` (the image) installs the project only.
- `scripts/` and `docs/` are already excluded from the image's build context (`.dockerignore`).

## Style

`ruff check .` and `ruff format --check .` pass with the script included (CI runs both over the whole
repository).
