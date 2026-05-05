#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "session_bootstrap" / "reports" / "figures" / "paper_figure_handwritten_acl_routes_cn_20260404.png"

WIDTH = 2400
HEIGHT = 1800
MARGIN = 80

FONT_ZH = Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf")
FONT_EN = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_EN_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

BG = "#FFFFFF"
INK = "#102235"
MUTED = "#5F6F7F"
GRID = "#D8E0E7"
FRAME = "#B8C4CF"
TRUSTED = "#7F8C99"
HAND = "#1B9E77"
ACL = "#D95F02"
HEAD = "#173A5E"
LIGHT = "#F5F8FB"
HILITE = "#EEF8F4"

ROUTES = [
    ("Trusted current", TRUSTED),
    ("Handwritten final", HAND),
    ("ACL route", ACL),
]

PANEL_A = {
    "ops": [
        ("transpose1", 55.016, 48.249, 48.705),
        ("transpose2", 43.912, 39.143, 38.672),
        ("transpose_add6", 40.916, 34.790, 35.303),
        ("variance3", 3.581, 2.736, 3.678),
        ("mean4", 3.102, 4.648, 11.178),
    ],
    "max": 60.0,
}

PANEL_B = {
    "payload": [242.628, 242.044, 246.820],
    "recon": [350.059, 345.267, 353.408],
}

PANEL_C = {
    "routes": [
        ("Trusted current", 360.218, 251.913, 44.102, TRUSTED),
        ("Handwritten final", 342.927, 252.584, 35.489, HAND),
        ("ACL route", 349.374, 258.933, 34.705, ACL),
    ],
    "xmin": 240,
    "xmax": 380,
}


def font(size: int, zh: bool = True, bold: bool = False):
    path = FONT_ZH if zh else (FONT_EN_BOLD if bold else FONT_EN)
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = font(64)
F_SUB = font(26)
F_PANEL = font(30)
F_BODY = font(22)
F_SMALL = font(18)
F_AXIS = font(20)
F_OP = font(20, zh=False, bold=True)
F_LEG = font(20, zh=False)
F_NUM = font(18, zh=False)
F_PANEL_LABEL = font(32, zh=False, bold=True)


def tsize(draw: ImageDraw.ImageDraw, text: str, f) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=f)
    return x1 - x0, y1 - y0


def wrap(draw: ImageDraw.ImageDraw, text: str, f, max_w: int) -> str:
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            trial = cur + ch
            if cur and draw.textlength(trial, font=f) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur = trial
        lines.append(cur)
    return "\n".join(lines)


def box(draw: ImageDraw.ImageDraw, rect):
    draw.rectangle(rect, outline=FRAME, width=2, fill="#FFFFFF")


def draw_panel_header(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, title: str, subtitle: str):
    draw.text((x, y), label, font=F_PANEL_LABEL, fill=HEAD)
    draw.text((x + 44, y + 1), title, font=F_PANEL, fill=HEAD)
    draw.text((x + 44, y + 38), subtitle, font=F_SMALL, fill=MUTED)


def hbar(draw: ImageDraw.ImageDraw, rect, color):
    draw.rounded_rectangle(rect, radius=8, fill=color)


def vbar(draw: ImageDraw.ImageDraw, rect, color):
    draw.rounded_rectangle(rect, radius=10, fill=color)


def map_x(v: float, x0: int, x1: int, vmin: float, vmax: float) -> int:
    return int(x0 + (v - vmin) / (vmax - vmin) * (x1 - x0))


def panel_a(draw: ImageDraw.ImageDraw, rect):
    x0, y0, x1, y1 = rect
    box(draw, rect)
    draw_panel_header(draw, x0 + 24, y0 + 18, "A", "关键算子图内延迟对比", "OpenAMP 三核、当前计算图下的 runtime profiling（ms）")

    # legend
    lx = x1 - 530
    ly = y0 + 24
    for name, color in ROUTES:
        draw.rectangle((lx, ly + 8, lx + 22, ly + 30), fill=color)
        draw.text((lx + 34, ly + 3), name, font=F_LEG, fill=INK)
        lx += 170

    chart_x0 = x0 + 500
    chart_x1 = x1 - 80
    chart_y0 = y0 + 120
    chart_y1 = y1 - 90

    # grid and axis
    for tick in range(0, 61, 10):
        tx = map_x(tick, chart_x0, chart_x1, 0, PANEL_A["max"])
        draw.line((tx, chart_y0, tx, chart_y1), fill=GRID, width=1)
        label = f"{tick}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((tx - tw / 2, chart_y1 + 14), label, font=F_NUM, fill=MUTED)
    draw.text((chart_x1 - 8, chart_y1 + 38), "ms", font=F_AXIS, fill=MUTED)

    row_h = 100
    for i, (name, trusted, hand, acl) in enumerate(PANEL_A["ops"]):
        cy = chart_y0 + 28 + i * row_h
        draw.text((x0 + 36, cy - 8), name, font=F_OP, fill=INK)
        vals = [trusted, hand, acl]
        colors = [TRUSTED, HAND, ACL]
        offsets = [-18, 4, 26]
        for v, c, off in zip(vals, colors, offsets):
            hbar(draw, (chart_x0, cy + off, map_x(v, chart_x0, chart_x1, 0, PANEL_A["max"]), cy + off + 14), c)
            label = f"{v:.3f}"
            tw, _ = tsize(draw, label, F_NUM)
            tx = map_x(v, chart_x0, chart_x1, 0, PANEL_A["max"])
            draw.text((min(tx + 8, chart_x1 - tw), cy + off - 4), label, font=F_NUM, fill=c)

    # callout
    note = (
        "观察：三段 transpose 上 handwritten 与 ACL route 已非常接近；\n"
        "当前真正拉开系统差距的，是 variance3 与 mean4 两段。"
    )
    nx0, ny0, nx1, ny1 = x0 + 36, y1 - 84, 960, y1 - 26
    draw.rounded_rectangle((nx0, ny0, nx1, ny1), radius=14, fill=HILITE, outline="#C9E8DA")
    draw.multiline_text((nx0 + 16, ny0 + 11), note, font=F_SMALL, fill=INK, spacing=3)


def sub_bar_chart(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, title: str, values: list[float], ymax: float):
    draw.text((x0, y0), title, font=F_BODY, fill=HEAD)
    cy0 = y0 + 42
    cy1 = y1 - 40
    for t in range(0, int(ymax) + 1, int(ymax / 4)):
        ty = int(cy1 - (t / ymax) * (cy1 - cy0))
        draw.line((x0 + 46, ty, x1, ty), fill=GRID, width=1)
        label = f"{t}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((x0 + 38 - tw, ty - 10), label, font=F_NUM, fill=MUTED)
    draw.line((x0 + 46, cy0, x0 + 46, cy1), fill=FRAME, width=2)
    draw.line((x0 + 46, cy1, x1, cy1), fill=FRAME, width=2)
    centers = [x0 + 190, x0 + 470, x0 + 750]
    bw = 112
    for (name, color), value, cx in zip(ROUTES, values, centers):
        top = int(cy1 - (value / ymax) * (cy1 - cy0))
        vbar(draw, (cx - bw // 2, top, cx + bw // 2, cy1), color)
        label = f"{value:.3f}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((cx - tw / 2, top - 26), label, font=F_NUM, fill=color)
        name_w, _ = tsize(draw, name, F_LEG)
        draw.text((cx - name_w / 2, cy1 + 10), name, font=F_LEG, fill=INK)


def panel_b(draw: ImageDraw.ImageDraw, rect):
    x0, y0, x1, y1 = rect
    box(draw, rect)
    draw_panel_header(draw, x0 + 24, y0 + 18, "B", "三条路线的 current-only 结果", "上：payload median；下：reconstruction mean（OpenAMP 三核）")
    inner_x0 = x0 + 36
    inner_x1 = x1 - 36
    sub_bar_chart(draw, inner_x0, y0 + 92, inner_x1, y0 + 360, "Payload median（ms）", PANEL_B["payload"], 260)
    sub_bar_chart(draw, inner_x0, y0 + 430, inner_x1, y1 - 28, "Reconstruction mean（ms/image）", PANEL_B["recon"], 370)


def panel_c(draw: ImageDraw.ImageDraw, rect):
    x0, y0, x1, y1 = rect
    box(draw, rect)
    draw_panel_header(draw, x0 + 24, y0 + 18, "C", "异构大小核流水线收益", "Dumbbell plot：串行到 big.LITTLE pipeline 的变化（ms/image）")

    chart_x0 = x0 + 180
    chart_x1 = x1 - 60
    chart_y0 = y0 + 130
    chart_y1 = y1 - 90

    for tick in range(240, 381, 20):
        tx = map_x(tick, chart_x0, chart_x1, PANEL_C["xmin"], PANEL_C["xmax"])
        draw.line((tx, chart_y0, tx, chart_y1), fill=GRID, width=1)
        label = f"{tick}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((tx - tw / 2, chart_y1 + 14), label, font=F_NUM, fill=MUTED)
    draw.text((chart_x1 - 8, chart_y1 + 38), "ms/image", font=F_AXIS, fill=MUTED)

    ys = [chart_y0 + 70, chart_y0 + 220, chart_y0 + 370]
    for (name, serial, pipe, uplift, color), cy in zip(PANEL_C["routes"], ys):
        sx = map_x(serial, chart_x0, chart_x1, PANEL_C["xmin"], PANEL_C["xmax"])
        px = map_x(pipe, chart_x0, chart_x1, PANEL_C["xmin"], PANEL_C["xmax"])
        draw.text((x0 + 26, cy - 12), name, font=F_LEG, fill=INK)
        draw.line((px, cy, sx, cy), fill=color, width=6)
        draw.ellipse((sx - 10, cy - 10, sx + 10, cy + 10), outline=color, width=4, fill="#FFFFFF")
        draw.ellipse((px - 10, cy - 10, px + 10, cy + 10), outline=color, width=4, fill=color)
        s_txt = f"{serial:.3f}"
        p_txt = f"{pipe:.3f}"
        draw.text((sx + 12, cy - 24), s_txt, font=F_NUM, fill=color)
        draw.text((px - 72, cy - 24), p_txt, font=F_NUM, fill=color)
        u_txt = f"提升 {uplift:.3f}%"
        uw, _ = tsize(draw, u_txt, F_BODY)
        mid = (sx + px) / 2
        draw.rounded_rectangle((mid - uw / 2 - 12, cy + 18, mid + uw / 2 + 12, cy + 54), radius=10, fill=LIGHT, outline=GRID)
        draw.text((mid - uw / 2, cy + 23), u_txt, font=F_BODY, fill=INK)

    # legend
    draw.text((chart_x0, chart_y1 + 62), "空心点：串行", font=F_SMALL, fill=MUTED)
    draw.text((chart_x0 + 160, chart_y1 + 62), "实心点：big.LITTLE pipeline", font=F_SMALL, fill=MUTED)


def render():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    draw.text((MARGIN, 28), "手写优化路线与 ACL 路线的算子级和系统级比较", font=F_TITLE, fill=HEAD)
    draw.text(
        (MARGIN, 98),
        "A：关键算子图内延迟；B：三条路线的 payload / reconstruction；C：加入异构大小核后的收益",
        font=F_SUB,
        fill=MUTED,
    )

    rect_a = (MARGIN, 136, WIDTH - MARGIN, 792)
    rect_b = (MARGIN, 836, 1140, HEIGHT - 80)
    rect_c = (1180, 836, WIDTH - MARGIN, HEIGHT - 80)

    panel_a(draw, rect_a)
    panel_b(draw, rect_b)
    panel_c(draw, rect_c)

    foot = (
        "注：ACL route 表示当前项目已实现的 ACL 替换路线；"
        "Panel A/B 使用 OpenAMP 三核 current graph 数据，Panel C 使用三条路线的 big.LITTLE compare 数据。"
    )
    draw.text((MARGIN, HEIGHT - 42), foot, font=F_SMALL, fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    print(OUT)


if __name__ == "__main__":
    render()
