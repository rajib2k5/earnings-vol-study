"""Screenshots of every app page, and three still views of the 3D terrain, for the README and the report.

    uv run --frozen --with playwright==1.64.1 python tools/screenshots.py            # npm run build, then shoot
    uv run --frozen --with playwright==1.64.1 python tools/screenshots.py --no-build # reuse app/dist

What it does:

1. ``npm run build`` in ``app/`` (unless ``--no-build``): the production bundle in ``app/dist``.
2. ``npm run preview`` on 127.0.0.1 (``--port``, default 4183): Vite's static server for that bundle.
3. Headless Chromium (Playwright 1.64.1; the browser binary is ``$PLAYWRIGHT_CHROMIUM`` or
   ``~/.cache/ms-playwright/chromium-1234/chrome-linux/chrome``), with ``prefers-reduced-motion: reduce`` so the
   animated pages show one still frame and the 3D view does not turn by itself. WebGL runs on SwiftShader.
4. ``app-<page>.png``: one screenshot per page at desktop width (``DESKTOP``; the top ``MAX_HEIGHT`` pixels, so
   the Results, Drivers, Heatmap and Architecture pages, which run longer, are cut there; the run prints each
   page's full height), and ``app-about-phone.png``, the home
   page at phone width (``PHONE``, the top ``PHONE_MAX_HEIGHT`` CSS pixels).
5. ``terrain-<view>.png``: three stills of the 3D terrain canvas at ``TERRAIN_DPR``: the default camera, then
   orbited by dragging the canvas, each trimmed to the drawn surface (``trim``).
6. ``fig-<name>.png``: the report's figures, one part of a page each (``FIGURES``), at ``FIGURE_DPR``.
7. Each PNG is reduced to a 256-colour palette with Pillow (``compress``) and written to ``docs/images/``.

The screenshots show only what the app shows: the app draws the committed ``app/public/data/*.json`` and
nothing else (DATA.md). Nothing is sent anywhere: the server listens on 127.0.0.1 and the pages load only
local files.

Blender hero renders are not made here: Blender was unreachable on 2026-10-29 (``tools/blender/README.md``).
The three-dimensional stills ``terrain-*.png`` are three.js frames of the app's own 3D view instead.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app"
OUT = REPO / "docs" / "images"
DEFAULT_CHROME = Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux/chrome"

# The app's pages, in the order of its navigation bar (app/src/App.tsx), plus the shell's Metrics page.
PAGES: list[tuple[str, str]] = [
    ("about", "About"),
    ("sample", "Sample"),
    ("iv", "IV measures"),
    ("results", "Results"),
    ("drivers", "Drivers"),
    ("implied", "Implied vs realised"),
    ("paths", "Crush paths"),
    ("heatmap", "Heatmap"),
    ("architecture", "Architecture"),
    ("3d", "3D view"),
    ("metrics", "Metrics"),
]
DESKTOP = {"width": 1280, "height": 800}
PHONE = {"width": 390, "height": 844}
MAX_HEIGHT = 3000  # px of a desktop page kept (the top of the page); a few pages are much longer
PHONE_MAX_HEIGHT = 2400
# Drags on the 3D canvas, from its centre: (name, dx, dy) in CSS pixels.
TERRAIN_VIEWS: list[tuple[str, int, int]] = [("default", 0, 0), ("side", 260, 0), ("top", 0, 170)]
# Figures for the report: (file name, page, the start of the heading of the part shown). A heading inside a
# `.card` gives that card; otherwise the heading and its siblings up to the next heading (FIGURE_JS).
FIGURES: list[tuple[str, str, str]] = [
    ("fig-funnel", "sample", "Sample funnel"),
    ("fig-crush-histogram", "iv", "30-day IV crush"),
    ("fig-implied-move", "iv", "Implied move"),
    ("fig-mean-path", "paths", "Mean path with 95% band"),
    ("fig-implied-realised", "implied", "Expected against realised move"),
    ("fig-heatmap", "heatmap", "Abnormal log IV by company and event day"),
]
FIGURE_DPR = 2
FIGURE_PAD = 12  # CSS px around the part
FIGURE_JS = """(text) => {
  const h = [...document.querySelectorAll('main h2')].find((e) => e.textContent.trim().startsWith(text))
  if (!h) return null
  const card = h.closest('.card')
  const els = card ? [card] : [h]
  if (!card) {
    for (let n = h.nextElementSibling; n && n.tagName !== 'H2' && !n.querySelector('h2'); n = n.nextElementSibling) els.push(n)
  }
  const rs = els.map((e) => e.getBoundingClientRect())
  const x0 = Math.min(...rs.map((r) => r.left)), y0 = Math.min(...rs.map((r) => r.top))
  const x1 = Math.max(...rs.map((r) => r.right)), y1 = Math.max(...rs.map((r) => r.bottom))
  return { x: x0 + window.scrollX, y: y0 + window.scrollY, width: x1 - x0, height: y1 - y0 }
}"""
TERRAIN_DPR = 2  # the stills are rendered at twice the pixel density, then trimmed to the surface
TERRAIN_MARGIN = 40  # px of background kept around the surface


def compress(png: bytes, max_height: int | None = None) -> bytes:
    """Crop to ``max_height`` (from the top) and quantise to a 256-colour palette, PNG optimised."""
    from PIL import Image

    img = Image.open(io.BytesIO(png)).convert("RGB")
    print(f"  captured {img.width} x {img.height} px")
    if max_height is not None and img.height > max_height:
        img = img.crop((0, 0, img.width, max_height))
    pal = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    pal.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def trim(png: bytes, margin: int) -> bytes:
    """Cut a still down to the drawn surface: the box of pixels that differ from the corner (background) colour."""
    from PIL import Image, ImageChops

    img = Image.open(io.BytesIO(png)).convert("RGB")
    bg = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if box is None:
        raise RuntimeError("the 3D still is empty: nothing differs from the background")
    x0, y0, x1, y1 = box
    img = img.crop((max(0, x0 - margin), max(0, y0 - margin), min(img.width, x1 + margin), min(img.height, y1 + margin)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def wait_http(url: str, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 (a local URL we started)
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.3)
    raise TimeoutError(f"no answer from {url} after {timeout_s:.0f} s")


def settle(page) -> None:
    """Wait until no page shows a loading line, then a little longer for the charts to lay out."""
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        "() => ![...document.querySelectorAll('[role=status]')].some(e => /Loading/i.test(e.textContent || ''))",
        timeout=30_000,
    )
    page.wait_for_timeout(600)


def shoot(base: str, chrome: Path, out: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    written: list[Path] = []

    def save(name: str, png: bytes, max_height: int | None) -> None:
        path = out / f"{name}.png"
        path.write_bytes(compress(png, max_height))
        written.append(path)
        shown = path.relative_to(REPO) if path.is_relative_to(REPO) else path
        print(f"wrote {shown} ({path.stat().st_size:,} B)")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(chrome),
            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
        )
        ctx = browser.new_context(viewport=DESKTOP, device_scale_factor=1, reduced_motion="reduce")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for pid, label in PAGES:
            page.goto(f"{base}/#/{pid}")
            settle(page)
            page.get_by_role("link", name=label, exact=True).wait_for()
            if pid == "3d":
                page.locator(".terrain-canvas canvas").wait_for(timeout=30_000)
                page.wait_for_timeout(2500)  # the lazy chunk and the first WebGL frame
            save(f"app-{pid}", page.screenshot(full_page=True), MAX_HEIGHT)

        ctx.close()

        # Three stills of the terrain canvas: the default camera, then orbited by a drag. Rendered at
        # TERRAIN_DPR and trimmed to the surface, so the surface fills the picture.
        tctx = browser.new_context(viewport=DESKTOP, device_scale_factor=TERRAIN_DPR, reduced_motion="reduce")
        page = tctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/3d")
        settle(page)
        canvas = page.locator(".terrain-canvas canvas")
        canvas.wait_for(timeout=30_000)
        page.wait_for_timeout(2500)
        canvas.scroll_into_view_if_needed()
        box = canvas.bounding_box()
        if box is None:
            raise RuntimeError("the 3D canvas has no box")
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        for name, dx, dy in TERRAIN_VIEWS:
            if dx or dy:
                page.mouse.move(cx, cy)
                page.mouse.down()
                page.mouse.move(cx + dx, cy + dy, steps=12)
                page.mouse.up()
                page.wait_for_timeout(800)
            save(f"terrain-{name}", trim(canvas.screenshot(), TERRAIN_MARGIN), None)
        tctx.close()

        # The report's figures: one part of a page each, at FIGURE_DPR.
        fctx = browser.new_context(viewport=DESKTOP, device_scale_factor=FIGURE_DPR, reduced_motion="reduce")
        page = fctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        for name, pid, heading in FIGURES:
            page.goto(f"{base}/#/{pid}")
            settle(page)
            box = page.evaluate(FIGURE_JS, heading)
            if box is None:
                raise RuntimeError(f"no heading starting '{heading}' on #/{pid}")
            clip = {"x": max(0, box["x"] - FIGURE_PAD), "y": max(0, box["y"] - FIGURE_PAD),
                    "width": box["width"] + 2 * FIGURE_PAD, "height": box["height"] + 2 * FIGURE_PAD}
            save(name, page.screenshot(clip=clip, full_page=True), None)
        fctx.close()

        phone = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True,
                                    reduced_motion="reduce")
        p2 = phone.new_page()
        p2.on("pageerror", lambda e: errors.append(str(e)))
        p2.goto(f"{base}/#/about")
        settle(p2)
        save("app-about-phone", p2.screenshot(full_page=True), PHONE_MAX_HEIGHT * 2)
        phone.close()
        browser.close()
    if errors:
        raise RuntimeError(f"page errors while shooting: {errors}")
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-build", action="store_true", help="reuse app/dist instead of running npm run build")
    ap.add_argument("--port", type=int, default=4183)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    chrome = Path(os.environ.get("PLAYWRIGHT_CHROMIUM", DEFAULT_CHROME))
    if not chrome.exists():
        print(f"no Chromium at {chrome}; set PLAYWRIGHT_CHROMIUM", file=sys.stderr)
        return 2
    if not args.no_build:
        subprocess.run(["npm", "run", "build"], cwd=APP, check=True)
    args.out.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(
        ["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", str(args.port), "--strictPort"],
        cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True,
    )
    base = f"http://127.0.0.1:{args.port}"
    try:
        wait_http(base + "/")
        written = shoot(base, chrome, args.out)
    finally:
        os.killpg(server.pid, 15)
        server.wait(timeout=20)
    total = sum(p.stat().st_size for p in written)
    print(f"{len(written)} images, {total:,} B in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
