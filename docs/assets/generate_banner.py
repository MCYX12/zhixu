#!/usr/bin/env python3
"""Bespoke README banners, one composition per project."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2400, 640
CJK_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_DIR = Path("/usr/share/matplotlib/mpl-data/fonts/ttf")
WHITE = (248, 250, 252)


def f_cjk(size, bold=True):
    return ImageFont.truetype(CJK_B if bold else CJK_R, size, index=2)


def f_sans(size):
    return ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), size)


def f_mono(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ("DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf")), size)


def use_cjk(text):
    return any(ord(ch) > 0x2E80 for ch in text)


CONFIGS = {
    "zhixu": dict(
        kicker="ZHIXU  //  LOCAL-FIRST AI WORKBENCH",
        lines=[("知序", 116), ("本地知识工作台", 54)],
        subtitle="文档知识库  ·  流式问答  ·  成员权限  ·  推理全程不出本机",
        metrics=[("5.68", "GB MODEL"), ("4", "ANSWER MODES"), ("3", "LOCAL PORTS"), ("0", "CLOUD CALLS")],
        accent=(129, 140, 248), text_y=136, subtitle_y=404, metrics_y=480,
    ),
}


def base():
    t = np.linspace(0, 1, H)[:, None, None]
    img = np.repeat(np.array((5, 9, 17))[None, None, :] * (1 - t)
                    + np.array((11, 22, 38))[None, None, :] * t, W, axis=1)
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    img[((xs % 48) < 1) | ((ys % 48) < 1)] += 9.0
    return img


def vignette(canvas):
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    vx = (xs - W / 2) / (W / 2)
    vy = (ys - H / 2) / (H / 2)
    vig = 1.0 - 0.20 * np.clip(vx ** 2 + vy ** 2, 0, 1) ** 1.5
    arr = np.asarray(canvas.convert("RGB"), dtype=float) * vig[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def halo(img, cx, cy, accent, radius=600, strength=0.20):
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    d = np.hypot(xs - cx, ys - cy) / radius
    img += (np.clip(1 - d, 0, 1) ** 2 * strength)[..., None] * np.array(accent) * 0.6


def draw_text(canvas, cfg):
    d = ImageDraw.Draw(canvas)
    accent = cfg["accent"]
    left, y = 140, cfg["text_y"]
    d.rectangle((96, cfg["text_y"] - 6, 104, cfg["metrics_y"] + 46), fill=accent + (190,))
    d.text((left, y - 14), cfg["kicker"], font=f_mono(26), fill=accent + (255,))
    y += 34
    for i, (text, size) in enumerate(cfg["lines"]):
        f = f_cjk(size) if use_cjk(text) else f_sans(size)
        d.text((left - 4, y), text, font=f, fill=(WHITE if i == 0 else accent) + (255,))
        y += int(size * 1.14) + 4
    d.text((left, cfg["subtitle_y"]), cfg["subtitle"], font=f_cjk(27, bold=False), fill=(148, 163, 184, 255))
    x = left
    for value, label in cfg["metrics"]:
        d.text((x, cfg["metrics_y"]), value, font=f_mono(30, True), fill=WHITE + (255,))
        wv = d.textlength(value, font=f_mono(30, True))
        d.text((x + wv + 10, cfg["metrics_y"] + 10), label, font=f_mono(19), fill=(100, 116, 139, 255))
        x += wv + 10 + d.textlength(label, font=f_mono(19)) + 42


# ---------------------------------------------------------------- motifs

def motif_window(ov, accent):
    d = ImageDraw.Draw(ov)
    x0, y0, x1, y1 = 1470, 108, 2270, 546
    d.rounded_rectangle([x0, y0, x1, y1], radius=20, fill=accent + (10,), outline=accent + (95,), width=2)
    d.line([x0, y0 + 46, x1, y0 + 46], fill=accent + (70,), width=1)
    for i in range(3):
        cx = x0 + 28 + i * 22
        d.ellipse([cx - 5, y0 + 18, cx + 5, y0 + 28], fill=accent + (150,))
    d.line([x0 + 150, y0 + 46, x0 + 150, y1], fill=accent + (55,), width=1)
    for i in range(4):
        yy = y0 + 86 + i * 56
        d.rounded_rectangle([x0 + 26, yy, x0 + 120, yy + 30], radius=6, fill=accent + (18 if i else 42,))
        d.rounded_rectangle([x0 + 26, yy + 8, x0 + 92, yy + 21], radius=4, fill=(209, 213, 255, 70 if i else 120))
    bubbles = [(x0 + 190, y0 + 90, 330, (209, 213, 255, 55)),
               (x0 + 330, y0 + 170, 240, (209, 213, 255, 55)),
               (x0 + 190, y0 + 250, 330, (209, 213, 255, 70)),
               (x0 + 300, y0 + 340, 240, accent + (95,))]
    for bx, by, w, c in bubbles:
        d.rounded_rectangle([bx, by, bx + w, by + 58], radius=12, fill=c)
    cx0, cx1 = x0 + 560, x1 - 24
    d.rounded_rectangle([cx0, y0 + 86, cx1, y0 + 300], radius=12,
                        outline=accent + (70,), width=1, fill=accent + (8,))
    for i in range(6):
        width = (cx1 - cx0 - 26) if i % 3 else (cx1 - cx0 - 90)
        d.rounded_rectangle([cx0 + 13, y0 + 116 + i * 26,
                             cx0 + 13 + width, y0 + 126 + i * 26],
                            radius=4, fill=(203, 213, 225, 60))
    d.line([x0 + 170, y1 - 40, x1 - 20, y1 - 40], fill=accent + (45,), width=1)
    d.ellipse([x0 + 170, y1 - 27, x0 + 182, y1 - 15], fill=(74, 222, 128, 220))


def render(out):
    cfg = CONFIGS["zhixu"]
    accent = cfg["accent"]
    img = base()
    halo(img, 1900, 320, accent, 620, 0.20)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    motif_window(ov, accent)

    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    canvas = Image.alpha_composite(canvas, ov.filter(ImageFilter.GaussianBlur(7)))
    canvas = Image.alpha_composite(canvas, ov.filter(ImageFilter.GaussianBlur(0.4)))
    canvas = vignette(canvas)
    draw_text(canvas, cfg)
    canvas.convert("RGB").save(out, optimize=True)
    print(f"wrote {out} ({Path(out).stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else "banner.png")
