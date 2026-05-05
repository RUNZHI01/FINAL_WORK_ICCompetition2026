#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "session_bootstrap" / "reports" / "figures" / "paper_triptych_cn_20260404.png"

FONT_ZH = Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf")
FONT_EN = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_EN_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

W = 3000
H = 1120
M = 70

BG = "#FFFFFF"
INK = "#0F2235"
MUTED = "#617285"
GRID = "#D7E0E8"
FRAME = "#9FB0BF"
HEAD = "#163A5F"
TRUSTED = "#7A8794"
HAND = "#1B9E77"
ACL = "#D95F02"
ZERO = "#98A6B3"


def load_font(size: int, zh: bool = True, bold: bool = False):
    path = FONT_ZH if zh else (FONT_EN_BOLD if bold else FONT_EN)
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = load_font(52)
F_SUB = load_font(24)
F_PANEL = load_font(26)
F_AXIS = load_font(18)
F_BODY = load_font(20)
F_SMALL = load_font(17)
F_EN = load_font(18, zh=False)
F_EN_BOLD = load_font(18, zh=False, bold=True)
F_LEG = load_font(19, zh=False)


# Panel A: operator-level relative delta vs trusted current (%), lower is better.
OPS = ["transpose1", "transpose2", "transpose_add6", "variance3", "mean4"]
HAND_DELTA_PCT = [-12.707, -11.867, -14.526, -23.376, 46.602]
ACL_DELTA_PCT = [-13.011, -12.100, -13.355, 5.167, 262.758]

# Panel B: current-only, normalized latency to trusted current.
PAYLOAD_NORM = [1.000, 242.044 / 242.628, 246.820 / 242.628]
RECON_NORM = [1.000, 345.267 / 350.059, 353.408 / 350.059]

# Panel C: big.LITTLE throughput uplift (%)
UPLIFT = [44.102, 35.489, 34.705]
SERIAL_TO_PIPE = [
    "360.218→251.913",
    "342.927→252.584",
    "349.374→258.933",
]

ROUTES = ["Trusted current", "Handwritten final", "ACL route"]
ROUTE_COLORS = [TRUSTED, HAND, ACL]


def tsize(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    return x1 - x0, y1 - y0


def draw_text_center(draw: ImageDraw.ImageDraw, cx: int, cy: int, text: str, font, fill: str):
    w, h = tsize(draw, text, font)
    draw.text((cx - w / 2, cy - h / 2), text, font=font, fill=fill)


def panel_header(draw: ImageDraw.ImageDraw, x: int, y: int, tag: str, title: str, subtitle: str):
    draw.text((x, y), f"({tag})", font=F_EN_BOLD, fill=HEAD)
    draw.text((x + 58, y - 2), title, font=F_PANEL, fill=HEAD)
    draw.text((x + 58, y + 32), subtitle, font=F_SMALL, fill=MUTED)


def box(draw: ImageDraw.ImageDraw, rect):
    draw.rectangle(rect, outline=FRAME, width=2)


def map_linear(v: float, a0: float, a1: float, b0: float, b1: float) -> float:
    return b0 + (v - a0) * (b1 - b0) / (a1 - a0)


def draw_panel_a(draw: ImageDraw.ImageDraw, rect):
    x0, y0, x1, y1 = rect
    box(draw, rect)
    panel_header(
        draw,
        x0 + 24,
        y0 + 16,
        "a",
        "关键算子延迟差异（相对 Trusted current）",
        "OpenAMP 三核，当前计算图内 profiling；横轴为相对变化（%），负值更好",
    )

    chart_x0 = x0 + 180
    chart_x1 = x1 - 60
    chart_y0 = y0 + 120
    chart_y1 = y1 - 70

    xmin, xmax = -40, 280
    zero_x = map_linear(0, xmin, xmax, chart_x0, chart_x1)

    for tick in range(-40, 281, 40):
        tx = map_linear(tick, xmin, xmax, chart_x0, chart_x1)
        draw.line((tx, chart_y0, tx, chart_y1), fill=GRID, width=1)
        label = f"{tick}"
        draw_text_center(draw, int(tx), chart_y1 + 18, label, F_AXIS, MUTED)

    draw.line((zero_x, chart_y0, zero_x, chart_y1), fill=ZERO, width=3)
    draw.text((chart_x1 - 20, chart_y1 + 40), "%", font=F_AXIS, fill=MUTED)

    row_gap = 74
    base_y = chart_y0 + 34
    for i, op in enumerate(OPS):
        cy = base_y + i * row_gap
        draw.text((x0 + 30, cy - 10), op, font=F_EN_BOLD, fill=INK)

        vals = [HAND_DELTA_PCT[i], ACL_DELTA_PCT[i]]
        colors = [HAND, ACL]
        offsets = [-14, 12]
        for v, c, dy in zip(vals, colors, offsets):
            sx = zero_x
            ex = map_linear(v, xmin, xmax, chart_x0, chart_x1)
            yb0 = cy + dy
            yb1 = yb0 + 14
            if ex >= sx:
                draw.rounded_rectangle((sx, yb0, ex, yb1), radius=6, fill=c)
                tx = min(ex + 10, chart_x1 - 40)
            else:
                draw.rounded_rectangle((ex, yb0, sx, yb1), radius=6, fill=c)
                tx = ex - 70
            draw.text((tx, yb0 - 4), f"{v:+.1f}", font=F_AXIS, fill=c)

    note = "mean4 与 variance3 才是 handwritten 相对当前 ACL route 的主要领先来源。"
    draw.text((x0 + 28, y1 - 34), note, font=F_SMALL, fill=MUTED)


def draw_panel_b(draw: ImageDraw.ImageDraw, rect):
    x0, y0, x1, y1 = rect
    box(draw, rect)
    panel_header(
        draw,
        x0 + 24,
        y0 + 16,
        "b",
        "三条路线的 current-only 结果（归一化）",
        "以 Trusted current = 1.0 归一化；数值越低越好，从而放大原始绝对值中的小差异",
    )

    chart_x0 = x0 + 80
    chart_x1 = x1 - 40
    chart_y0 = y0 + 120
    chart_y1 = y1 - 86
    ymin, ymax = 0.98, 1.02

    for tick in [0.98, 0.99, 1.00, 1.01, 1.02]:
        ty = map_linear(tick, ymin, ymax, chart_y1, chart_y0)
        draw.line((chart_x0, ty, chart_x1, ty), fill=GRID, width=1)
        draw.text((chart_x0 - 48, ty - 9), f"{tick:.2f}", font=F_AXIS, fill=MUTED)

    group_centers = [chart_x0 + 240, chart_x0 + 650]
    group_names = ["Payload", "Reconstruction"]
    group_vals = [PAYLOAD_NORM, RECON_NORM]
    bar_w = 68

    for gc, gname, vals in zip(group_centers, group_names, group_vals):
        for j, (name, color, value) in enumerate(zip(ROUTES, ROUTE_COLORS, vals)):
            cx = gc + (j - 1) * 95
            yv = map_linear(value, ymin, ymax, chart_y1, chart_y0)
            draw.rounded_rectangle((cx - bar_w / 2, yv, cx + bar_w / 2, chart_y1), radius=8, fill=color)
            draw_text_center(draw, int(cx), int(yv - 22), f"{value:.3f}", F_AXIS, color)
            draw_text_center(draw, int(cx), chart_y1 + 28, ["Trusted", "Hand", "ACL"][j], F_LEG, INK)
        draw_text_center(draw, int(gc), chart_y0 - 26, gname, F_BODY, HEAD)

    draw.text((chart_x0, chart_y1 + 60), "注：该面板直接展示“接近但不完全相同”的 current-only 差异。", font=F_SMALL, fill=MUTED)


def draw_panel_c(draw: ImageDraw.ImageDraw, rect):
    x0, y0, x1, y1 = rect
    box(draw, rect)
    panel_header(
        draw,
        x0 + 24,
        y0 + 16,
        "c",
        "加入异构大小核后的收益",
        "big.LITTLE throughput uplift（%）；柱顶为提升比例，柱下标注 serial→pipeline 的绝对延迟",
    )

    chart_x0 = x0 + 70
    chart_x1 = x1 - 40
    chart_y0 = y0 + 120
    chart_y1 = y1 - 110
    ymax = 50.0

    for tick in range(0, 51, 10):
        ty = map_linear(tick, 0, ymax, chart_y1, chart_y0)
        draw.line((chart_x0, ty, chart_x1, ty), fill=GRID, width=1)
        draw.text((chart_x0 - 36, ty - 9), f"{tick}", font=F_AXIS, fill=MUTED)

    centers = [chart_x0 + 190, chart_x0 + 470, chart_x0 + 750]
    bw = 110
    for cx, uplift, label, name, color in zip(centers, UPLIFT, SERIAL_TO_PIPE, ROUTES, ROUTE_COLORS):
        yv = map_linear(uplift, 0, ymax, chart_y1, chart_y0)
        draw.rounded_rectangle((cx - bw / 2, yv, cx + bw / 2, chart_y1), radius=10, fill=color)
        draw_text_center(draw, int(cx), int(yv - 24), f"{uplift:.1f}%", F_AXIS, color)
        draw_text_center(draw, int(cx), chart_y1 + 26, name, F_LEG, INK)
        draw_text_center(draw, int(cx), chart_y1 + 52, label, F_AXIS, MUTED)

    draw.text((chart_x1 - 20, chart_y0 - 12), "%", font=F_AXIS, fill=MUTED)


def draw_legend(draw: ImageDraw.ImageDraw, x: int, y: int):
    entries = [(TRUSTED, "Trusted current"), (HAND, "Handwritten final"), (ACL, "ACL route")]
    cur_x = x
    for color, label in entries:
        draw.rectangle((cur_x, y + 6, cur_x + 24, y + 30), fill=color)
        draw.text((cur_x + 36, y), label, font=F_LEG, fill=INK)
        cur_x += 250


def render():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((M, 26), "手写算子优化路线与 ACL 路线的三联图比较", font=F_TITLE, fill=HEAD)
    draw.text(
        (M, 90),
        "图中避免直接使用原始绝对量级，而优先采用相对变化或归一化结果，以放大三条路线之间的真实差异。",
        font=F_SUB,
        fill=MUTED,
    )
    draw_legend(draw, W - 860, 34)

    gap = 28
    pw = (W - 2 * M - 2 * gap) // 3
    rects = [
        (M, 150, M + pw, H - 70),
        (M + pw + gap, 150, M + 2 * pw + gap, H - 70),
        (M + 2 * (pw + gap), 150, W - M, H - 70),
    ]

    draw_panel_a(draw, rects[0])
    draw_panel_b(draw, rects[1])
    draw_panel_c(draw, rects[2])

    footer = (
        "数据来源：OpenAMP 三核 current graph profiling、三条路线 current-only 复测、以及 big.LITTLE compare。"
    )
    draw.text((M, H - 38), footer, font=F_SMALL, fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(OUT)


if __name__ == "__main__":
    render()
