#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "session_bootstrap" / "reports" / "figures" / "handwritten_vs_acl_operator_matrix_20260404.png"

WIDTH = 2200
HEIGHT = 1720
MARGIN = 84

BG_TOP = "#F6F1E8"
BG_BOTTOM = "#EEF3F7"
CARD = "#FFFDFC"
CARD_ALT = "#F8FAFC"
INK = "#132033"
MUTED = "#5D6B7B"
GRID = "#D9E1E8"
HEADER = "#11243D"
GREEN = "#2E9B6F"
GREEN_BG = "#E6F7EF"
RED = "#C8574B"
RED_BG = "#FCEAE6"
AMBER = "#B87816"
AMBER_BG = "#FFF1D9"
BLUE = "#2474A6"
BLUE_BG = "#E8F4FB"
PURPLE = "#7A53A3"
PURPLE_BG = "#F1E9FB"
ORANGE = "#D97C2B"


TOP_FACTS = [
    ("YES", GREEN, GREEN_BG, "ACL can scale into one multi-op route for transpose1 + transpose_add6 + transpose2."),
    ("NOT YET", RED, RED_BG, "It still does not replace the full handwritten final route end-to-end."),
    ("WHY", AMBER, AMBER_BG, "The current handwritten edge comes mainly from mean4 (-6.530 ms) and variance3 (-0.942 ms)."),
]

CAUSAL_BARS = [
    ("mean4", -6.530),
    ("variance3", -0.942),
    ("transpose_add6", -0.513),
    ("transpose1", -0.455),
    ("transpose2", 0.470),
]

ROWS = [
    {
        "operator": "fused_conv2d_transpose1_add9",
        "hand": "v7 promoted\nBoard payload: 156.785 ms\nvs ref: -1.97%",
        "graph": "HW 48.249 ms\nACL-line 48.705 ms\nDelta: -0.455 ms",
        "acl": "ACL asym standalone\n26.611 ms",
        "takeaway": "ACL-expandable, but no stock ACL in-graph proof yet.",
        "accent": BLUE_BG,
    },
    {
        "operator": "fused_conv2d_transpose_add6",
        "hand": "v1 accepted, v2 dropped\nBoard payload: 159.503 ms\nvs ref: -0.28%",
        "graph": "HW 34.790 ms\nACL-line 35.303 ms\nDelta: -0.513 ms",
        "acl": "ACL asym standalone\n16.771 ms",
        "takeaway": "Best ACL seam, but the old '+33.9%' claim is retired.",
        "accent": BLUE_BG,
    },
    {
        "operator": "fused_conv2d_transpose2_add12",
        "hand": "v1 accepted baseline\nBoard payload: 161.416 ms\nvs ref: +0.92%",
        "graph": "HW 39.143 ms\nACL-line 38.672 ms\nDelta: +0.470 ms",
        "acl": "ACL asym standalone\n51.505 ms",
        "takeaway": "Current ACL signal is weak. Lowest priority among the three.",
        "accent": BLUE_BG,
    },
    {
        "operator": "fused_variance4_add13_tir_sqrt4",
        "hand": "v18 frozen\nBoard payload: 158.347 ms\nvs ref: -1.00%",
        "graph": "Trusted graph:\n~7.045 ms",
        "acl": "No stock ACL path\nin repo",
        "takeaway": "Small but real handwritten win.",
        "accent": PURPLE_BG,
    },
    {
        "operator": "fused_variance3_add10_tir_sqrt3",
        "hand": "v1.1 keep\nStandalone: 2771 us\nvs baseline: -22.2%",
        "graph": "Trusted 3.581 ms\nHW final 2.736 ms\nDelta: -0.942 ms",
        "acl": "No stock ACL path\nin repo",
        "takeaway": "Key handwritten gain source outside the ACL coverage set.",
        "accent": GREEN_BG,
    },
    {
        "operator": "fused_variance1_add3_tir_sqrt1",
        "hand": "v1 Welford\nStandalone: 1315 us\nbut integrated A/B regressed",
        "graph": "Integrated delta vs\ntrusted: +9.459 ms",
        "acl": "No stock ACL path\nin repo",
        "takeaway": "Classic warning: isolated win, full-model loss.",
        "accent": RED_BG,
    },
    {
        "operator": "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
        "hand": "v4 keep\nmean4_only e2e: 242.9 ms\nvs trusted: -3.26%",
        "graph": "HW final 4.648 ms\nACL-line 11.178 ms\nDelta: -6.530 ms",
        "acl": "No stock ACL path\nin repo",
        "takeaway": "Largest handwritten edge in the current graph.",
        "accent": GREEN_BG,
    },
    {
        "operator": "fused_mean1_subtract1_divide1_multiply1_add4",
        "hand": "v1 compiled only\nNo formal board perf yet",
        "graph": "Trusted graph:\n~4.215 ms",
        "acl": "No stock ACL path\nin repo",
        "takeaway": "Still missing real perf evidence.",
        "accent": CARD_ALT,
    },
    {
        "operator": "fused_conv2d3_add15",
        "hand": "v2 dropped\nBoard payload: 161.999 ms\nvs baseline: +0.62%",
        "graph": "Trusted graph:\n~28.497 ms",
        "acl": "No stock ACL path\nin repo",
        "takeaway": "No current handwritten gain and no ACL experiment line.",
        "accent": CARD_ALT,
    },
]


def hex_to_rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(color)
    return (r, g, b, alpha)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            ]
        )
    for path in candidates:
        p = Path(path)
        if p.is_file():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


FONT_TITLE = load_font(60, bold=True)
FONT_SUB = load_font(24)
FONT_CARD_TITLE = load_font(28, bold=True)
FONT_CARD = load_font(24)
FONT_SMALL = load_font(20)
FONT_TABLE_HEAD = load_font(22, bold=True)
FONT_TABLE = load_font(20)
FONT_PILL = load_font(18, bold=True)
FONT_FOOT = load_font(18)


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    r1, g1, b1 = ImageColor.getrgb(top)
    r2, g2, b2 = ImageColor.getrgb(bottom)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line((0, y, width, y), fill=(r, g, b, 255))
    return image


def draw_shadow_card(base: Image.Image, box: tuple[int, int, int, int], fill: str, radius: int = 26) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    x0, y0, x1, y1 = box
    shadow_box = (x0 + 10, y0 + 14, x1 + 10, y1 + 14)
    odraw.rounded_rectangle(shadow_box, radius=radius, fill=hex_to_rgba("#192534", 34))
    overlay = overlay.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=hex_to_rgba("#FFFFFF", 120), width=2)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    return x1 - x0, y1 - y0


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    paragraphs = text.split("\n")
    wrapped: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split(" ")
        if not words:
            wrapped.append("")
            continue
        line = words[0]
        for word in words[1:]:
            trial = f"{line} {word}"
            if draw.textlength(trial, font=font) <= max_width:
                line = trial
            else:
                wrapped.append(line)
                line = word
        wrapped.append(line)
    return "\n".join(wrapped)


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    spacing: int = 6,
) -> None:
    draw.multiline_text(xy, text, font=font, fill=fill, spacing=spacing)


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], label: str, color: str, bg: str) -> None:
    draw.rounded_rectangle(xy, radius=16, fill=bg)
    w, h = text_size(draw, label, FONT_PILL)
    x0, y0, x1, y1 = xy
    draw.text((x0 + (x1 - x0 - w) / 2, y0 + (y1 - y0 - h) / 2 - 1), label, font=FONT_PILL, fill=color)


def section_title(draw: ImageDraw.ImageDraw, x: int, y: int, title: str, subtitle: str) -> int:
    draw.text((x, y), title, font=FONT_CARD_TITLE, fill=INK)
    draw.text((x, y + 36), subtitle, font=FONT_SMALL, fill=MUTED)
    return y + 74


def render() -> Path:
    base = vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(base)

    # Decorative glow
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((1500, -180, 2200, 520), fill=hex_to_rgba("#9FD7FF", 68))
    gdraw.ellipse((-120, 1050, 560, 1680), fill=hex_to_rgba("#B6F0D4", 58))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    base.alpha_composite(glow)
    draw = ImageDraw.Draw(base)

    # Header
    draw.text((MARGIN, 52), "Handwritten vs ACL Routes", font=FONT_TITLE, fill=HEADER)
    draw.text((MARGIN, 126), "OpenAMP 3-core | Current JSCC graph | 2026-04-04", font=FONT_SUB, fill=MUTED)
    draw.text(
        (MARGIN, 160),
        "At a glance: ACL can grow into a 3-transpose route, but it still does not cover the real handwritten win sources.",
        font=FONT_SMALL,
        fill=INK,
    )

    left_box = (MARGIN, 210, 1080, 560)
    right_box = (1120, 210, WIDTH - MARGIN, 560)
    mid_box = (MARGIN, 590, WIDTH - MARGIN, 720)
    table_box = (MARGIN, 748, WIDTH - MARGIN, HEIGHT - 66)

    draw_shadow_card(base, left_box, CARD)
    draw_shadow_card(base, right_box, CARD)
    draw_shadow_card(base, mid_box, CARD_ALT)
    draw_shadow_card(base, table_box, CARD)
    draw = ImageDraw.Draw(base)

    # Left card
    y = section_title(draw, left_box[0] + 28, left_box[1] + 24, "Can ACL become a multi-op route?", "Short answer")
    fact_y = y
    for label, color, bg, text in TOP_FACTS:
        pill(draw, (left_box[0] + 28, fact_y, left_box[0] + 168, fact_y + 38), label, color, bg)
        wrapped = wrap_text(draw, text, FONT_CARD, 820)
        draw_multiline(draw, (left_box[0] + 190, fact_y - 2), wrapped, FONT_CARD, INK, spacing=5)
        fact_y += 86

    # Right card: causal bars
    y = section_title(draw, right_box[0] + 28, right_box[1] + 24, "Why does end-to-end flip?", "Handwritten final vs current ACL line")
    chart_left = right_box[0] + 28
    chart_top = y + 8
    chart_right = right_box[1] - 28
    center_x = chart_left + 430
    draw.line((center_x, chart_top, center_x, chart_top + 230), fill=GRID, width=3)
    max_abs = 7.0
    row_h = 42
    for idx, (label, value) in enumerate(CAUSAL_BARS):
        cy = chart_top + 10 + idx * row_h
        draw.text((chart_left, cy - 6), label, font=FONT_CARD, fill=INK)
        half = 250
        length = int(abs(value) / max_abs * half)
        if value < 0:
            x0, x1 = center_x - length, center_x
            fill = GREEN
        else:
            x0, x1 = center_x, center_x + length
            fill = ORANGE
        draw.rounded_rectangle((x0, cy, x1, cy + 20), radius=10, fill=fill)
        delta_txt = f"{value:+.3f} ms"
        tw, _ = text_size(draw, delta_txt, FONT_SMALL)
        draw.text((chart_right - tw, cy - 3), delta_txt, font=FONT_SMALL, fill=fill)
    draw.text((chart_left, chart_top + 228), "Negative = handwritten faster. Positive = ACL line faster.", font=FONT_SMALL, fill=MUTED)

    # Mid band
    band_x = mid_box[0] + 28
    band_y = section_title(draw, band_x, mid_box[1] + 20, "Fair evidence rules", "What to trust when you write the conclusion")
    rules = [
        ("USE", GREEN, GREEN_BG, "Graph-real profiling under OpenAMP 3-core"),
        ("DO NOT USE", RED, RED_BG, "Old transpose_add6 standalone ACL +33.9%"),
        ("BOUNDARY", AMBER, AMBER_BG, "Current 'ACL line' is packed-call + TVM proxy, not stock ACL fully in-graph"),
    ]
    rx = band_x
    widths = [350, 390, 860]
    for (label, color, bg, text), width in zip(rules, widths):
        pill(draw, (rx, band_y, rx + 126, band_y + 36), label, color, bg)
        wrapped = wrap_text(draw, text, FONT_SMALL, width - 140)
        draw_multiline(draw, (rx + 144, band_y - 1), wrapped, FONT_SMALL, INK, spacing=4)
        rx += width

    # Table
    tx0, ty0, tx1, ty1 = table_box
    title_y = section_title(draw, tx0 + 28, ty0 + 20, "Operator matrix", "All current handwritten lanes, plus the ACL evidence that actually exists")
    table_top = title_y + 8
    table_left = tx0 + 20
    table_right = tx1 - 20
    cols = [
        ("Operator", 360),
        ("Handwritten evidence", 520),
        ("3-core graph view", 350),
        ("ACL evidence", 270),
        ("Takeaway", table_right - table_left - 360 - 520 - 350 - 270),
    ]
    header_h = 48
    row_h = 91
    x = table_left
    for title, width in cols:
        draw.rounded_rectangle((x, table_top, x + width - 8, table_top + header_h), radius=14, fill=HEADER)
        tw, th = text_size(draw, title, FONT_TABLE_HEAD)
        draw.text((x + 16, table_top + (header_h - th) / 2 - 2), title, font=FONT_TABLE_HEAD, fill="#FFFFFF")
        x += width

    y = table_top + header_h + 10
    for idx, row in enumerate(ROWS):
        x = table_left
        fill = row["accent"] if idx % 2 == 0 else CARD
        draw.rounded_rectangle((table_left, y, table_right - 8, y + row_h), radius=18, fill=fill, outline=GRID)
        cell_texts = [
            row["operator"],
            row["hand"],
            row["graph"],
            row["acl"],
            row["takeaway"],
        ]
        cell_fonts = [FONT_TABLE_HEAD, FONT_TABLE, FONT_TABLE, FONT_TABLE, FONT_TABLE]
        for (col_title, width), text, font in zip(cols, cell_texts, cell_fonts):
            del col_title
            wrapped = wrap_text(draw, text, font, width - 30)
            draw_multiline(draw, (x + 14, y + 12), wrapped, font, INK, spacing=4)
            x += width
        y += row_h + 10

    footnote = (
        "Read this image in two layers: ACL is expandable across the three transpose hotspots, "
        "but the current handwritten route still wins because it also captures mean4 + variance3."
    )
    draw.text((MARGIN, HEIGHT - 46), footnote, font=FONT_FOOT, fill=MUTED)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(OUTPUT, format="PNG", optimize=True)
    return OUTPUT


if __name__ == "__main__":
    path = render()
    print(path)
