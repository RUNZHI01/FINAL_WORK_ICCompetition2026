#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
OUT1 = FIG_DIR / "paper_fig1_operator_performance_cn_20260404.png"
OUT2 = FIG_DIR / "paper_fig2_e2e_payload_reconstruction_cn_20260404.png"
OUT3 = FIG_DIR / "paper_fig3_big_little_pipeline_cn_20260404.png"

FONT_ZH = Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf")
FONT_EN = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_EN_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

BG = "#FFFFFF"
INK = "#13263A"
MUTED = "#5B6D80"
GRID = "#D9E1E8"
FRAME = "#AAB8C4"
HEAD = "#173A5E"
BASELINE = "#7A8794"
HAND = "#1B9E77"
ACL = "#D95F02"
GOOD = "#157347"
BAD = "#B02A37"
PIE_COLORS = ["#335C81", "#4F709C", "#6E90BA", "#8CAED4", "#B2C6E2", "#D7E1EC"]

ROUTE_LABELS = [
    "metaschedule优化",
    "metaschedule+\n手写算子优化",
    "metaschedule+关键算子acl库\n（arm neon官方算子库）替换",
]
ROUTE_SHORT_LABELS = [
    "metaschedule优化",
    "手写优化",
    "ACL替换",
]
ROUTE_COLORS = [BASELINE, HAND, ACL]

OPS = ["transpose1", "transpose2", "transpose_add6", "variance3", "mean4"]
OP_TIMES = {
    "metaschedule优化": [55.016, 43.912, 40.916, 3.581, 3.102],
    "metaschedule+手写算子优化": [48.025, 38.701, 34.973, 2.744, 4.548],
    "metaschedule+关键算子acl库（arm neon官方算子库）替换": [47.858, 38.599, 35.452, 3.766, 11.254],
}
OP_TOTAL = 358.450

E2E_PAYLOAD = [242.628, 242.044, 246.820]
E2E_RECON = [350.059, 345.267, 353.408]

SERIAL_MS = [360.218, 342.927, 349.374]
PIPELINE_MS = [251.913, 252.584, 258.933]
UPLIFT = [44.102, 35.489, 34.705]


def load_font(size: int, zh: bool = True, bold: bool = False):
    path = FONT_ZH if zh else (FONT_EN_BOLD if bold else FONT_EN)
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = load_font(52)
F_SUB = load_font(24)
F_BODY = load_font(22)
F_SMALL = load_font(18)
F_AXIS = load_font(17)
F_NUM = load_font(18, zh=False)
F_NUM_BOLD = load_font(20, zh=False, bold=True)
F_EN = load_font(18, zh=False)
F_EN_BOLD = load_font(20, zh=False, bold=True)


def tsize(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, align="left")
    return x1 - x0, y1 - y0


def draw_multiline_center(draw: ImageDraw.ImageDraw, cx: float, y: float, text: str, font, fill: str):
    w, _ = tsize(draw, text, font)
    draw.multiline_text((cx - w / 2, y), text, font=font, fill=fill, spacing=4, align="center")


def draw_legend(draw: ImageDraw.ImageDraw, x: int, y: int):
    cur_y = y
    labels = [
        ("metaschedule优化", BASELINE),
        ("metaschedule+\n手写算子优化", HAND),
        ("metaschedule+关键算子acl库\n（arm neon官方算子库）替换", ACL),
    ]
    for label, color in labels:
        draw.rounded_rectangle((x, cur_y + 4, x + 28, cur_y + 32), radius=4, fill=color)
        draw.multiline_text((x + 42, cur_y), label, font=F_SMALL, fill=INK, spacing=4)
        _, h = tsize(draw, label, F_SMALL)
        cur_y += h + 24


def draw_route_legend_row(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int]):
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=14, fill="#F5F8FB", outline=FRAME, width=1)
    width = x1 - x0
    col_w = width / 3.0
    for i, (label, color) in enumerate(zip(ROUTE_LABELS, ROUTE_COLORS)):
        cx = x0 + col_w * (i + 0.5)
        box_x = cx - col_w * 0.42
        draw.rounded_rectangle((box_x, y0 + 23, box_x + 22, y0 + 45), radius=4, fill=color)
        draw_multiline_center(draw, cx + 54, y0 + 14, label, F_SMALL, INK)


def draw_box(draw: ImageDraw.ImageDraw, rect):
    draw.rounded_rectangle(rect, radius=16, outline=FRAME, width=2)


def map_linear(v: float, a0: float, a1: float, b0: float, b1: float) -> float:
    return b0 + (v - a0) * (b1 - b0) / (a1 - a0)


def delta_text(value: float, baseline: float) -> str:
    if baseline == 0:
        return "NA"
    pct = (value / baseline - 1.0) * 100.0
    return f"{pct:+.2f}%"


def delta_color(value: float, baseline: float) -> str:
    if value <= baseline:
        return GOOD
    return BAD


def draw_axis_label(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, font, fill: str):
    w, _ = tsize(draw, text, font)
    draw.text((x - w / 2, y), text, font=font, fill=fill)


def save_fig1():
    width, height = 2700, 1320
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 36), "关键算子图内性能差异与热点占比", font=F_TITLE, fill=HEAD)
    draw.text(
        (70, 104),
        "OpenAMP 三核、当前计算图 profiling。左图给出绝对时间，中图按 metaschedule优化 归一化，右图展示 metaschedule优化 的总时长占比。",
        font=F_SUB,
        fill=MUTED,
    )
    draw_route_legend_row(draw, (70, 148, 2630, 224))

    abs_rect = (70, 250, 1520, 1220)
    norm_rect = (1560, 250, 2630, 720)
    pie_rect = (1560, 760, 2630, 1220)
    draw_box(draw, abs_rect)
    draw_box(draw, norm_rect)
    draw_box(draw, pie_rect)

    draw.text((96, 272), "绝对时间（ms）", font=F_BODY, fill=HEAD)
    draw.text((1588, 272), "相对 metaschedule优化 的归一化结果", font=F_BODY, fill=HEAD)
    draw.text((1588, 304), "仅展示手写路线与 ACL 路线的归一化倍数；1.0x 表示与基线持平。", font=F_SMALL, fill=MUTED)
    draw.text((1588, 784), "metaschedule优化 路线中的热点占比", font=F_BODY, fill=HEAD)

    ax0, ay0, ax1, ay1 = 120, 350, 1480, 1140
    ymin, ymax = 0.0, 60.0
    for tick in range(0, 61, 10):
        ty = map_linear(tick, ymin, ymax, ay1, ay0)
        draw.line((ax0, ty, ax1, ty), fill=GRID, width=1)
        draw.text((84, ty - 10), f"{tick}", font=F_NUM, fill=MUTED)
    draw.text((120, 314), "ms", font=F_AXIS, fill=MUTED)

    group_centers = [ax0 + 130 + i * 250 for i in range(len(OPS))]
    bar_w = 42
    offsets = [-56, 0, 56]
    route_names = list(OP_TIMES.keys())
    for gc, op in zip(group_centers, OPS):
        for idx, (route, color, off) in enumerate(zip(route_names, ROUTE_COLORS, offsets)):
            value = OP_TIMES[route][OPS.index(op)]
            top = map_linear(value, ymin, ymax, ay1, ay0)
            left = gc + off - bar_w / 2
            right = gc + off + bar_w / 2
            draw.rounded_rectangle((left, top, right, ay1), radius=8, fill=color)
            label_y = max(top - 46, ay0 + 8)
            draw_multiline_center(draw, gc + off, label_y, f"{value:.3f}\nms", F_AXIS, color)
        draw_axis_label(draw, gc, ay1 + 28, op, F_EN_BOLD, INK)

    nx0, ny0, nx1, ny1 = 1608, 342, 2590, 620
    ymin_norm, ymax_norm = 0.0, 4.0
    for tick in [0.0, 1.0, 2.0, 3.0, 4.0]:
        ty = map_linear(tick, ymin_norm, ymax_norm, ny1, ny0)
        draw.line((nx0, ty, nx1, ty), fill=GRID, width=1)
        draw.text((1576, ty - 10), f"{tick:.1f}x", font=F_NUM, fill=MUTED)
    baseline_y = map_linear(1.0, ymin_norm, ymax_norm, ny1, ny0)
    draw.line((nx0, baseline_y, nx1, baseline_y), fill="#8798A9", width=3)
    draw.text((2500, baseline_y - 26), "1.0x 基线", font=F_SMALL, fill=MUTED)

    norm_hand = [OP_TIMES[route_names[1]][i] / OP_TIMES[route_names[0]][i] for i in range(len(OPS))]
    norm_acl = [OP_TIMES[route_names[2]][i] / OP_TIMES[route_names[0]][i] for i in range(len(OPS))]
    group_centers = [nx0 + 95 + i * 182 for i in range(len(OPS))]
    nbar_w = 34
    noffsets = [-26, 26]
    for i, (gc, op) in enumerate(zip(group_centers, OPS)):
        for ratio, color, off in [(norm_hand[i], HAND, noffsets[0]), (norm_acl[i], ACL, noffsets[1])]:
            top = map_linear(ratio, ymin_norm, ymax_norm, ny1, ny0)
            draw.rounded_rectangle((gc + off - nbar_w / 2, top, gc + off + nbar_w / 2, ny1), radius=7, fill=color)
            label_y = max(top - 24, ny0 + 6)
            draw_multiline_center(draw, gc + off, label_y, f"{ratio:.2f}x", F_NUM_BOLD, color)
        draw_axis_label(draw, gc, ny1 + 18, op, F_EN_BOLD, INK)

    px0, py0, px1, py1 = pie_rect
    cx = (px0 + px1) // 2 - 80
    cy = (py0 + py1) // 2 + 18
    radius = 155
    values = OP_TIMES[route_names[0]] + [OP_TOTAL - sum(OP_TIMES[route_names[0]])]
    labels = OPS + ["other ops"]
    total = sum(values)
    start = -90.0
    for value, color in zip(values, PIE_COLORS):
        end = start + value / total * 360.0
        draw.pieslice((cx - radius, cy - radius, cx + radius, cy + radius), start=start, end=end, fill=color, outline=BG)
        start = end
    draw.ellipse((cx - 72, cy - 72, cx + 72, cy + 72), fill=BG)
    draw_multiline_center(draw, cx, cy - 20, "总时长\n358.450 ms", F_BODY, HEAD)

    legend_x = 2210
    legend_y = 850
    for label, value, color in zip(labels, values, PIE_COLORS):
        pct = value / total * 100.0
        draw.rounded_rectangle((legend_x, legend_y + 4, legend_x + 22, legend_y + 26), radius=4, fill=color)
        draw.text((legend_x + 34, legend_y), label, font=F_EN if label == "other ops" else F_EN_BOLD, fill=INK)
        draw.text((legend_x + 240, legend_y), f"{pct:.1f}%", font=F_NUM_BOLD, fill=HEAD)
        legend_y += 48

    footer = "第一张图同时保留绝对时间与相对归一化，避免只看其中一种口径。"
    draw.text((70, 1260), footer, font=F_SMALL, fill=MUTED)

    OUT1.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT1)


def draw_zoom_panel(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    subtitle: str,
    values: list[float],
    unit: str,
):
    x0, y0, x1, y1 = rect
    draw_box(draw, rect)
    draw.text((x0 + 24, y0 + 18), subtitle, font=F_BODY, fill=HEAD)
    draw.text((x0 + 24, y0 + 54), "绝对时间柱状图，柱顶同时标注相对 metaschedule优化 的变化幅度。", font=F_SMALL, fill=MUTED)
    draw.text((x0 + 28, y0 + 88), f"局部放大（非零起点），单位：{unit}", font=F_SMALL, fill=MUTED)

    left = x0 + 80
    top = y0 + 150
    right = x1 - 40
    bottom = y1 - 170
    vmin = min(values)
    vmax = max(values)
    span = max(vmax - vmin, 1.0)
    ymin = vmin - span * 0.45
    ymax = vmax + span * 0.38

    tick_count = 4
    tick_step = (ymax - ymin) / tick_count
    for i in range(tick_count + 1):
        tick = ymin + i * tick_step
        ty = map_linear(tick, ymin, ymax, bottom, top)
        draw.line((left, ty, right, ty), fill=GRID, width=1)
        draw.text((x0 + 16, ty - 10), f"{tick:.1f}", font=F_NUM, fill=MUTED)

    group_gap = (right - left) / 3.0
    bar_w = 110
    for i, (label, color, value) in enumerate(zip(ROUTE_SHORT_LABELS, ROUTE_COLORS, values)):
        cx = left + group_gap * (i + 0.5)
        top_y = map_linear(value, ymin, ymax, bottom, top)
        draw.rounded_rectangle((cx - bar_w / 2, top_y, cx + bar_w / 2, bottom), radius=10, fill=color)
        draw_multiline_center(draw, cx, top_y - 64, f"{value:.3f} {unit}", F_NUM_BOLD, color)
        if i == 0:
            delta = "基线"
            delta_fill = HEAD
            delta_font = F_SMALL
        else:
            delta = delta_text(value, values[0])
            delta_fill = delta_color(value, values[0])
            delta_font = F_NUM_BOLD
        draw_multiline_center(draw, cx, top_y - 34, delta, delta_font, delta_fill)
        draw_multiline_center(draw, cx, bottom + 26, label, F_SMALL, INK)

    draw.line((left, bottom, right, bottom), fill=FRAME, width=2)
    draw.line((left, top, left, bottom), fill=FRAME, width=2)

    # axis break mark
    break_x = left - 12
    break_y = bottom + 6
    draw.line((break_x - 10, break_y, break_x, break_y + 12), fill=FRAME, width=3)
    draw.line((break_x, break_y, break_x + 10, break_y + 12), fill=FRAME, width=3)


def save_fig2():
    width, height = 2500, 1080
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 36), "端到端重建与纯推理时间差异", font=F_TITLE, fill=HEAD)
    draw.text(
        (70, 104),
        "三条路线均使用绝对时间；由于差异仅为毫秒级，纵轴采用局部放大，并在柱顶附上相对 metaschedule优化 的变化幅度。",
        font=F_SUB,
        fill=MUTED,
    )
    draw_route_legend_row(draw, (70, 148, 2430, 224))

    left_rect = (70, 250, 1210, 980)
    right_rect = (1290, 250, 2430, 980)
    draw_zoom_panel(draw, left_rect, "纯推理时间（payload median）", E2E_PAYLOAD, "ms")
    draw_zoom_panel(draw, right_rect, "端到端重建时间（reconstruction mean）", E2E_RECON, "ms/image")

    footer = "同一 OpenAMP 三核板态下，metaschedule+手写算子优化 在 payload 与 reconstruction 两个口径都略优于 metaschedule优化。"
    draw.text((70, 1018), footer, font=F_SMALL, fill=MUTED)

    OUT2.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT2)


def save_fig3():
    width, height = 2600, 1140
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 36), "加入异构大小核流水线性能差异", font=F_TITLE, fill=HEAD)
    draw.text(
        (70, 104),
        "左右分别给出串行与异构大小核流水线的绝对时间；柱顶同时标出相对 metaschedule优化 的变化。底部补充各路线自身的 serial→pipeline 提升比例。",
        font=F_SUB,
        fill=MUTED,
    )
    draw_route_legend_row(draw, (70, 148, 2530, 224))

    left_rect = (70, 250, 1260, 980)
    right_rect = (1340, 250, 2530, 980)
    draw_zoom_panel(draw, left_rect, "串行执行时间（serial median）", SERIAL_MS, "ms")
    draw_zoom_panel(draw, right_rect, "异构流水线时间（pipeline）", PIPELINE_MS, "ms/image")

    strip = (70, 1010, 2530, 1090)
    draw.rounded_rectangle(strip, radius=14, fill="#F4F7FA", outline=FRAME, width=1)
    draw.text((98, 1032), "各路线自身的 serial→pipeline 提升：", font=F_BODY, fill=HEAD)

    entries = [
        ("metaschedule优化", UPLIFT[0], BASELINE),
        ("手写优化", UPLIFT[1], HAND),
        ("ACL替换", UPLIFT[2], ACL),
    ]
    centers = [760, 1450, 2100]
    for (label, uplift, color), cx in zip(entries, centers):
        draw.rounded_rectangle((cx - 170, 1037, cx - 150, 1057), radius=4, fill=color)
        draw_multiline_center(draw, cx - 22, 1028, label, F_SMALL, INK)
        draw_multiline_center(draw, cx + 160, 1028, f"{uplift:.2f}%", F_NUM_BOLD, color)

    OUT3.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT3)


def main():
    save_fig1()
    save_fig2()
    save_fig3()
    print(OUT1)
    print(OUT2)
    print(OUT3)


if __name__ == "__main__":
    main()
