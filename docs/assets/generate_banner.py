#!/usr/bin/env python3
"""README banner generator (shared style, per-project config).

Usage: python3 generate_banner.py [output]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2400, 640
CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_DIR = Path("/usr/share/matplotlib/mpl-data/fonts/ttf")
MONO = FONT_DIR / "DejaVuSansMono.ttf"
MONO_B = FONT_DIR / "DejaVuSansMono-Bold.ttf"


def font(path, size, index=0):
    return ImageFont.truetype(str(path), size, index=index)


def cjk(size, bold=True):
    return font(CJK if bold else CJK_R, size, index=2)


CONFIGS = {
    "zhixu": dict(
        kicker="ZHIXU  //  LOCAL-FIRST AI WORKBENCH",
        lines=[("知序", 120, "white"), ("本地知识工作台", 56, "accent")],
        subtitle="文档知识库  ·  流式问答  ·  成员权限  ·  推理全程不出本机",
        metrics=[("5.68", "GB MODEL"), ("4", "ANSWER MODES"), ("3", "LOCAL PORTS"), ("0", "CLOUD CALLS")],
        accent=(129, 140, 248),
        motif="network",
        seed=23,
    ),
}


def gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    return np.repeat(np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t, W, axis=1)


def base():
    img = gradient((5, 9, 17), (11, 22, 38))
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    img[((xs % 48) < 1) | ((ys % 48) < 1)] += 9.0
    return img


def soft_ring(img, cx, cy, radius, accent, strength=0.22):
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    r = np.hypot(xs - cx, ys - cy)
    ring = np.abs(r - radius) < 1.1
    img += ring[..., None] * np.array(accent) * strength


def motif_network(ov, d, accent, seed, cx=1900, cy=330, radius=255):
    rng = np.random.default_rng(seed)
    pts = []
    while len(pts) < 22:
        x, y = rng.uniform(-1, 1, 2)
        if x * x + y * y <= 1.0:
            pts.append((cx + x * radius, cy + y * radius))
    for i, p in enumerate(pts):
        near = sorted(((np.hypot(p[0] - q[0], p[1] - q[1]), j) for j, q in enumerate(pts) if j != i))[:2]
        for _, j in near:
            d.line([p, pts[j]], fill=accent + (34,), width=1)
    for ring in (250, 300):
        d.ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=accent + (12,), width=1)
    for i, p in enumerate(pts):
        rr = 4.4 if i % 4 == 0 else 2.4
        color = (248, 250, 252, 235) if i % 4 == 0 else accent + (205,)
        d.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=color)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=accent + (240,))


def motif_wave(d, accent, cx=1890, cy=330):
    rng = np.random.default_rng(5)
    n = 64
    span = 780
    bw = 7
    gap = (span - n * bw) / (n - 1)
    for i in range(n):
        x = cx - span / 2 + i * (bw + gap)
        env = np.exp(-((i - n / 2) / (n / 2.6)) ** 2)
        h = 30 + 250 * env * (0.25 + 0.75 * abs(np.sin(i * 0.55 + rng.normal(0, 0.15))))
        alpha = int(40 + 150 * env)
        d.rounded_rectangle([x, cy - h, x + bw, cy + h], radius=bw / 2, fill=accent + (alpha,))
    d.line([cx - span / 2 - 20, cy, cx + span / 2 + 20, cy], fill=accent + (40,), width=1)


def motif_grid(d, accent, cx=1900, cy=330):
    cols, rows, cell, gap = 7, 5, 74, 14
    x0 = cx - (cols * cell + (cols - 1) * gap) / 2
    y0 = cy - (rows * cell + (rows - 1) * gap) / 2
    hot = {(1, 1), (3, 2), (5, 1), (2, 3), (4, 0)}
    for r in range(rows):
        for c in range(cols):
            x = x0 + c * (cell + gap)
            y = y0 + r * (cell + gap)
            if (c, r) in hot:
                d.rounded_rectangle([x, y, x + cell, y + cell], radius=10, fill=accent + (70,), outline=accent + (200,), width=2)
                d.ellipse([x + cell / 2 - 7, y + cell / 2 - 7, x + cell / 2 + 7, y + cell / 2 + 7], fill=accent + (230,))
            else:
                d.rounded_rectangle([x, y, x + cell, y + cell], radius=10, outline=accent + (34,), width=1)


def render(name, out):
    cfg = CONFIGS[name]
    accent = cfg["accent"]
    img = base()

    # soft halo behind the motif
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    d2 = np.hypot(xs - 1900, ys - 330) / 520.0
    halo = np.clip(1 - d2, 0, 1) ** 2 * 0.16
    img += halo[..., None] * np.array(accent) * 0.55

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if cfg["motif"] == "network":
        motif_network(ov, d, accent, cfg["seed"])
    elif cfg["motif"] == "wave":
        motif_wave(d, accent)
    else:
        motif_grid(d, accent)

    glow = ov.filter(ImageFilter.GaussianBlur(9))
    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    canvas = Image.alpha_composite(canvas, glow)
    canvas = Image.alpha_composite(canvas, ov.filter(ImageFilter.GaussianBlur(0.4)))

    # vignette before text
    vx = (xs - W / 2) / (W / 2)
    vy = (ys - H / 2) / (H / 2)
    vig = 1.0 - 0.22 * np.clip(vx ** 2 + vy ** 2, 0, 1) ** 1.4
    arr = np.asarray(canvas.convert("RGB"), dtype=float) * vig[..., None]
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    d = ImageDraw.Draw(canvas)
    d.rectangle((96, 142, 104, 552), fill=accent + (190,))
    left = 140
    d.text((left, 136), cfg["kicker"], font=font(MONO, 26), fill=accent + (255,))

    y = 168
    for text, size, color in cfg["lines"]:
        f = cjk(size) if any(ord(ch) > 0x2E80 for ch in text) else font(FONT_DIR / "DejaVuSans-Bold.ttf", size)
        d.text((left - 4, y), text, font=f, fill=(248, 250, 252, 255) if color == "white" else accent + (255,))
        y += int(size * 1.16) + 6

    d.text((left, 430), cfg["subtitle"], font=cjk(28, bold=False), fill=(148, 163, 184, 255))

    x = left
    for value, label in cfg["metrics"]:
        if not value:
            continue
        d.text((x, 498), value, font=font(MONO_B, 30), fill=(248, 250, 252, 255))
        wv = d.textlength(value, font=font(MONO_B, 30))
        d.text((x + wv + 10, 508), label, font=font(MONO, 19), fill=(100, 116, 139, 255))
        x += wv + 10 + d.textlength(label, font=font(MONO, 19)) + 42

    canvas.convert("RGB").save(out, optimize=True)
    print(f"wrote {out} ({Path(out).stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    render("zhixu", sys.argv[1] if len(sys.argv) > 1 else "banner.png")
