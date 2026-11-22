#!/usr/bin/env python3
"""Generate the PNG assets for the arch-sky Plymouth theme.

Everything is generated procedurally so the theme stays reproducible and
license-clean (apart from the Arch logo, which is taken from the system).
"""

from __future__ import annotations

import math
import random
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
THEME = HERE.parent
ASSETS = THEME / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
WORKSPACE = THEME.parent

ARCH_LOGO = Path("/usr/share/pixmaps/archlinux-logo.png")
ARCH_LOGO_SVG = Path("/usr/share/pixmaps/archlinux-logo.svg")
FONT_REGULAR = Path("/usr/share/fonts/noto/NotoSans-Regular.ttf")
FONT_LIGHT = Path("/usr/share/fonts/noto/NotoSans-Light.ttf")

W, H = 1280, 720


def _radial(size: int, color: tuple[int, int, int], power: float = 2.2) -> Image.Image:
    """A soft round glow with the given colour and a transparent edge."""
    y, x = np.mgrid[0:size, 0:size]
    cx = cy = (size - 1) / 2
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / (size / 2)
    r = np.clip(r, 0, 1)
    alpha = np.clip(1 - r, 0, 1) ** power
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[..., 0] = color[0]
    rgba[..., 1] = color[1]
    rgba[..., 2] = color[2]
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def make_background() -> None:
    rng = np.random.default_rng(20261121)

    yy = np.linspace(0.0, 1.0, H)[:, None, None]
    top = np.array([10, 16, 38], dtype=np.float64)
    bottom = np.array([3, 4, 10], dtype=np.float64)
    img = top * (1 - yy) + bottom * yy
    img = np.repeat(img, W, axis=1)

    def add_blob(cx: float, cy: float, radius: float,
                 colour: tuple[int, int, int], strength: float) -> None:
        nonlocal img
        y, x = np.mgrid[0:H, 0:W]
        d = np.sqrt(((x - cx) / radius) ** 2 + ((y - cy) / radius) ** 2)
        falloff = np.clip(1 - d, 0, 1) ** 2.1
        img += falloff[..., None] * np.array(colour) * strength

    add_blob(W * 0.22, H * 0.20, W * 0.62, (18, 170, 205), 0.30)
    add_blob(W * 0.80, H * 0.72, W * 0.58, (96, 58, 210), 0.26)
    add_blob(W * 0.62, H * 0.30, W * 0.34, (40, 120, 190), 0.12)

    # A couple of very soft aurora bands.
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    for (base_y, amp, freq, phase, width, colour, strength) in [
        (H * 0.31, 70, 0.0035, 0.0, 95, (40, 220, 210), 0.055),
        (H * 0.47, 55, 0.0048, 2.1, 70, (110, 80, 240), 0.045),
    ]:
        centre = base_y + amp * np.sin(x * freq + phase)
        band = np.exp(-((y - centre) / width) ** 2)
        img += band[..., None] * np.array(colour) * strength

    # Vignette.
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    nx = (x - W / 2) / (W / 2)
    ny = (y - H / 2) / (H / 2)
    vignette = 1.0 - 0.34 * np.clip(nx * nx * 0.55 + ny * ny * 0.75, 0, 1)
    img *= vignette[..., None]

    # Fine grain keeps large gradients from banding on 8-bit displays.
    img += rng.normal(0.0, 1.4, img.shape)

    img = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # Stars.
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(240):
        sx = rng.uniform(0, W)
        sy = rng.uniform(0, H * 0.92)
        brightness = rng.uniform(22, 95)
        radius = rng.uniform(0.35, 1.1)
        draw.ellipse(
            (sx - radius, sy - radius, sx + radius, sy + radius),
            fill=(210, 240, 255, int(brightness)),
        )
    for _ in range(9):
        sx = rng.uniform(0, W)
        sy = rng.uniform(0, H * 0.9)
        glow = _radial(int(rng.uniform(8, 16)), (150, 230, 255))
        glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.18)))
        img.alpha_composite(glow, (int(sx), int(sy)))

    # Keep the initramfs payload small: 256 colours are plenty for a soft
    # gradient and cut the file roughly in half.
    img.convert("RGB").quantize(
        colors=256, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG
    ).convert("RGB").save(ASSETS / "background.png", optimize=True)


def make_halos() -> None:
    for name, colour in [
        ("halo.png", (130, 240, 255)),
        ("halo-green.png", (120, 255, 190)),
        ("halo-red.png", (255, 110, 120)),
        ("halo-violet.png", (150, 110, 255)),
    ]:
        _radial(512, colour, power=2.4).save(ASSETS / name, optimize=True)


def rounded_gradient(size: tuple[int, int], top: tuple[int, int, int, int],
                     bottom: tuple[int, int, int, int], radius: int) -> Image.Image:
    w, h = size
    grad = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(grad)
    for y in range(h):
        t = y / max(1, h - 1)
        colour = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(4))
        d.line((0, y, w, y), fill=colour)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    grad.putalpha(mask)
    return grad


def make_panel() -> None:
    s = 8
    w, h = 780, 160
    panel = rounded_gradient((w * s, h * s), (13, 22, 42, 214), (5, 8, 18, 234), 32 * s)

    d = ImageDraw.Draw(panel, "RGBA")
    d.rounded_rectangle(
        (s, s, w * s - s - 1, h * s - s - 1),
        radius=31 * s,
        outline=(120, 232, 255, 150),
        width=max(1, int(1.6 * s)),
    )
    d.rounded_rectangle(
        (3 * s, 3 * s, w * s - 3 * s - 1, h * s - 3 * s - 1),
        radius=29 * s,
        outline=(190, 245, 255, 24),
        width=max(1, int(1.0 * s)),
    )
    # Top highlight.
    d.line(
        (34 * s, 2 * s, (w - 34) * s, 2 * s),
        fill=(205, 248, 255, 90),
        width=max(1, int(1.2 * s)),
    )
    # Faint divider between prompt and the passphrase row.
    d.line(
        (128 * s, 62 * s, (w - 44) * s, 62 * s),
        fill=(120, 210, 240, 26),
        width=max(1, int(1.0 * s)),
    )
    panel.resize((w * 2, h * 2), Image.LANCZOS).save(ASSETS / "panel.png", optimize=True)


def make_lock() -> None:
    s = 8
    w, h = 72, 80
    img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")

    # Shackle.
    d.arc(
        (20 * s, 8 * s, 52 * s, 52 * s),
        start=180,
        end=360,
        fill=(165, 244, 255, 255),
        width=7 * s,
    )
    d.arc(
        (20 * s, 8 * s, 52 * s, 52 * s),
        start=180,
        end=360,
        fill=(235, 253, 255, 150),
        width=2 * s,
    )

    # Body.
    body_mask = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(body_mask).rounded_rectangle(
        (11 * s, 32 * s, 61 * s, 73 * s), radius=11 * s, fill=255
    )
    body = rounded_gradient((w * s, h * s), (60, 210, 240, 255), (22, 92, 210, 255), 10 * s)
    body.putalpha(body_mask)
    img.alpha_composite(body)
    d.rounded_rectangle(
        (11 * s, 32 * s, 61 * s, 73 * s),
        radius=11 * s,
        outline=(190, 250, 255, 190),
        width=max(1, int(1.2 * s)),
    )

    # Keyhole.
    d.ellipse((32 * s, 43 * s, 40 * s, 51 * s), fill=(5, 12, 26, 230))
    d.rounded_rectangle((34 * s, 48 * s, 38 * s, 60 * s), radius=2 * s, fill=(5, 12, 26, 230))
    d.ellipse((33 * s, 44 * s, 36 * s, 47 * s), fill=(210, 250, 255, 120))

    img.resize((w * 2, h * 2), Image.LANCZOS).save(ASSETS / "lock.png", optimize=True)


def make_dot_and_caret() -> None:
    s = 4
    size = 30
    img = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    glow = _radial(size * s, (90, 225, 255), power=2.6)
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img, "RGBA")
    c = size * s / 2
    d.ellipse((c - 7 * s, c - 7 * s, c + 7 * s, c + 7 * s), fill=(105, 235, 255, 255))
    d.ellipse((c - 4 * s, c - 4 * s, c + 4 * s, c + 4 * s), fill=(225, 253, 255, 255))
    img.resize((size * 2, size * 2), Image.LANCZOS).save(ASSETS / "dot.png", optimize=True)

    # A small orbit particle.
    img2 = _radial(28, (160, 245, 255), power=2.0)
    d2 = ImageDraw.Draw(img2, "RGBA")
    d2.ellipse((8, 8, 20, 20), fill=(235, 254, 255, 255))
    img2.save(ASSETS / "orbit-dot.png", optimize=True)

    # Blinking caret.
    cs = 4
    caret = Image.new("RGBA", (4 * cs, 30 * cs), (0, 0, 0, 0))
    ImageDraw.Draw(caret).rounded_rectangle(
        (0, 0, 4 * cs - 1, 30 * cs - 1), radius=2 * cs, fill=(120, 238, 255, 255)
    )
    caret.resize((8, 60), Image.LANCZOS).save(ASSETS / "caret.png", optimize=True)


def make_progress() -> None:
    s = 4
    w, h = 800, 10

    track = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(track, "RGBA")
    d.rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1),
        radius=h * s // 2,
        fill=(255, 255, 255, 22),
        outline=(125, 220, 245, 34),
        width=s,
    )
    track.resize((w * 2, h * 2), Image.LANCZOS).save(ASSETS / "progress-track.png", optimize=True)

    fill = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (w * s, h * s))
    gd = ImageDraw.Draw(grad)
    for x in range(w * s):
        t = x / max(1, w * s - 1)
        r = int(46 * (1 - t) + 139 * t)
        g = int(232 * (1 - t) + 92 * t)
        b = int(255 * (1 - t) + 246 * t)
        gd.line((x, 0, x, h * s), fill=(r, g, b, 255))
    mask = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w * s - 1, h * s - 1), radius=h * s // 2, fill=255
    )
    fill = Image.composite(grad, Image.new("RGBA", grad.size, (0, 0, 0, 0)), mask)
    fd = ImageDraw.Draw(fill, "RGBA")
    fd.line((h * s, s, (w - h) * s, s), fill=(235, 255, 255, 120), width=s)
    fill.resize((w * 2, h * 2), Image.LANCZOS).save(ASSETS / "progress-fill.png", optimize=True)

    glow = fill.resize((w * 2, h * 2), Image.LANCZOS)
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.55)))
    glow.save(ASSETS / "progress-glow.png", optimize=True)


def _largest_alpha_component(img: Image.Image) -> Image.Image:
    """Drop the tiny trademark glyph that ships with the Arch logo."""
    alpha = np.array(img.getchannel("A"))
    mask = alpha > 8
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            pixels: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                pixels.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(pixels) > len(best):
                best = pixels
    keep = np.zeros_like(mask, dtype=np.uint8) * 255
    for y, x in best:
        keep[y, x] = 255
    out = img.copy()
    out.putalpha(Image.fromarray(keep, "L"))
    return out


def make_logo() -> None:
    logo = None
    if ARCH_LOGO_SVG.exists():
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "logo.png"
                subprocess.run(
                    ["rsvg-convert", "-w", "1024", "-h", "1024", str(ARCH_LOGO_SVG), "-o", str(out)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                logo = Image.open(out).convert("RGBA").copy()
        except Exception:
            logo = None
    if logo is None and ARCH_LOGO.exists():
        logo = Image.open(ARCH_LOGO).convert("RGBA")
    if logo is None:
        return
    logo = _largest_alpha_component(logo)
    w, h = logo.size
    grad = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(grad)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(238 * (1 - t) + 64 * t)
        g = int(252 * (1 - t) + 206 * t)
        b = int(255 * (1 - t) + 255 * t)
        d.line((0, y, w, y), fill=(r, g, b, 255))
    tinted = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tinted.paste(grad, (0, 0), logo.getchannel("A"))
    tinted.save(ASSETS / "logo.png", optimize=True)


def make_preview() -> None:
    pw, ph = 1920, 1080
    canvas = Image.open(ASSETS / "background.png").convert("RGBA").resize((pw, ph), Image.LANCZOS)
    cx, cy = pw // 2, int(ph * 0.46)
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((230, 230), Image.LANCZOS)
    halo = Image.open(ASSETS / "halo.png").convert("RGBA").resize((600, 600), Image.LANCZOS)
    halo.putalpha(halo.getchannel("A").point(lambda a: int(a * 0.55)))
    canvas.alpha_composite(halo, (cx - 300, cy - 300))
    canvas.alpha_composite(logo, (cx - 115, cy - 115))

    # The progress line is intentionally hidden while the passphrase is up.
    # Password panel.
    panel = Image.open(ASSETS / "panel.png").convert("RGBA").resize((780, 160), Image.LANCZOS)
    px, py = cx - 390, int(ph * 0.66)
    canvas.alpha_composite(panel, (px, py))
    lock = Image.open(ASSETS / "lock.png").convert("RGBA").resize((64, 71), Image.LANCZOS)
    canvas.alpha_composite(lock, (px + 36, py + 44))

    font = ImageFont.truetype(str(FONT_LIGHT), 26)
    small = ImageFont.truetype(str(FONT_REGULAR), 15)
    d = ImageDraw.Draw(canvas)
    d.text((px + 130, py + 24), "Enter passphrase", font=font, fill=(214, 243, 255, 255))
    d.text((px + 130, py + 124), "press enter to unlock", font=small, fill=(95, 140, 175, 210))

    dot = Image.open(ASSETS / "dot.png").convert("RGBA").resize((24, 24), Image.LANCZOS)
    for i in range(3):
        canvas.alpha_composite(dot, (px + 130 + i * 30, py + 92))
    caret = Image.open(ASSETS / "caret.png").convert("RGBA").resize((3, 28), Image.LANCZOS)
    canvas.alpha_composite(caret, (px + 130 + 3 * 30 + 4, py + 92))

    canvas.convert("RGB").save(WORKSPACE / "preview.png", optimize=True)

    # A second mock-up of the normal boot state: centred logo, status line,
    # and the progress line without the passphrase panel.
    boot = Image.open(ASSETS / "background.png").convert("RGBA").resize((pw, ph), Image.LANCZOS)
    boot.alpha_composite(halo, (cx - 300, cy - 300))
    boot.alpha_composite(logo, (cx - 115, cy - 115))
    bd = ImageDraw.Draw(boot)
    status = ImageFont.truetype(str(FONT_REGULAR), 17)
    text = "Started Journal Service"
    tw = bd.textlength(text, font=status)
    bd.text((cx - tw / 2, cy + 150), text, font=status, fill=(140, 175, 205, 150))
    btrack = Image.open(ASSETS / "progress-track.png").convert("RGBA").resize((900, 11), Image.LANCZOS)
    boot.alpha_composite(btrack, (cx - 450, int(ph * 0.935) - 5))
    bfill = Image.open(ASSETS / "progress-fill.png").convert("RGBA").resize((414, 11), Image.LANCZOS)
    boot.alpha_composite(bfill, (cx - 450, int(ph * 0.935) - 5))
    boot.convert("RGB").save(WORKSPACE / "preview-boot.png", optimize=True)


def main() -> None:
    make_background()
    make_halos()
    make_panel()
    make_lock()
    make_dot_and_caret()
    make_progress()
    make_logo()
    make_preview()
    print(f"assets written to {ASSETS}")


if __name__ == "__main__":
    main()
