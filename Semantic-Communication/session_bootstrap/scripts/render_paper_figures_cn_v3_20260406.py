#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
OUT2 = FIG_DIR / "paper_fig2_e2e_payload_reconstruction_cn_20260406.png"
OUT3 = FIG_DIR / "paper_fig3_big_little_pipeline_cn_20260406.png"
OUT5 = FIG_DIR / "paper_fig_performance_ladder_cn_20260406.png"

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

ROUTE_LABELS = [
    "trusted current",
    "latest handwritten\nmean4 v7",
    "ACL integration line",
]
ROUTE_SHORT_LABELS = [
    "trusted current",
    "handwritten v7",
    "ACL line",
]
ROUTE_COLORS = [BASELINE, HAND, ACL]

PAYLOAD_MS = [244.617, 240.059, 248.156]
RECON_MS = [347.341, 345.609, 352.158]
SERIAL_MS = [347.341, 345.609, 352.158]
PIPELINE_MS = [257.388, 249.393, 262.922]
UPLIFT = [34.569, 38.706, 33.814]

TVM_MAINLINE = [
    ("旧端到端", 1850.0, BASELINE),
    ("TVM 直通", 230.3, HEAD),
    ("TVM 流水线", 134.6, HAND),
]


def load_font(size: int, zh: bool = True, bold: bool = False):
    path = FONT_ZH if zh else (FONT_EN_BOLD if bold else FONT_EN)
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = load_font(50)
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
    return GOOD if value <= baseline else BAD


def draw_route_legend_row(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int]):
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=14, fill="#F5F8FB", outline=FRAME, width=1)
    width = x1 - x0
    col_w = width / 3.0
    for i, (label, color) in enumerate(zip(ROUTE_LABELS, ROUTE_COLORS)):
        cx = x0 + col_w * (i + 0.5)
        box_x = cx - col_w * 0.42
        draw.rounded_rectangle((box_x, y0 + 23, box_x + 22, y0 + 45), radius=4, fill=color)
        draw_multiline_center(draw, cx + 42, y0 + 14, label, F_SMALL, INK)


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
    draw.text((x0 + 24, y0 + 54), "柱顶同时标注相对 trusted current 的变化幅度。", font=F_SMALL, fill=MUTED)
    draw.text((x0 + 24, y0 + 88), f"局部放大（非零起点），单位：{unit}", font=F_SMALL, fill=MUTED)

    left = x0 + 80
    top = y0 + 150
    right = x1 - 40
    bottom = y1 - 150
    vmin = min(values)
    vmax = max(values)
    span = max(vmax - vmin, 1.0)
    ymin = vmin - span * 0.48
    ymax = vmax + span * 0.40

    tick_count = 4
    tick_step = (ymax - ymin) / tick_count
    for i in range(tick_count + 1):
        tick = ymin + i * tick_step
        ty = map_linear(tick, ymin, ymax, bottom, top)
        draw.line((left, ty, right, ty), fill=GRID, width=1)
        draw.text((x0 + 18, ty - 10), f"{tick:.1f}", font=F_NUM, fill=MUTED)

    group_gap = (right - left) / 3.0
    bar_w = 112
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
        draw_multiline_center(draw, cx, bottom + 24, label, F_SMALL, INK)

    draw.line((left, bottom, right, bottom), fill=FRAME, width=2)
    draw.line((left, top, left, bottom), fill=FRAME, width=2)

    break_x = left - 12
    break_y = bottom + 6
    draw.line((break_x - 10, break_y, break_x, break_y + 12), fill=FRAME, width=3)
    draw.line((break_x, break_y, break_x + 10, break_y + 12), fill=FRAME, width=3)


def save_fig2():
    width, height = 2500, 1080
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 36), "OpenAMP 三核 same-day payload 与重建时间差异", font=F_TITLE, fill=HEAD)
    draw.text(
        (70, 104),
        "全部数据来自 2026-04-06 的 same-day follow-up。左图为 serial payload，右图为 serial reconstruction，均以 trusted current 为比较基线。",
        font=F_SUB,
        fill=MUTED,
    )
    draw_route_legend_row(draw, (70, 148, 2430, 224))

    left_rect = (70, 250, 1210, 980)
    right_rect = (1290, 250, 2430, 980)
    draw_zoom_panel(draw, left_rect, "纯推理时间（payload median）", PAYLOAD_MS, "ms")
    draw_zoom_panel(draw, right_rect, "端到端重建时间（serial reconstruction median）", RECON_MS, "ms/image")

    footer = "当前最新 handwritten mean4 v7 line 在 same-day payload 与 serial reconstruction 两个口径都直接领先 trusted current 与 ACL line。"
    draw.text((70, 1018), footer, font=F_SMALL, fill=MUTED)

    OUT2.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT2)


def save_fig3():
    width, height = 2600, 1140
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 36), "OpenAMP 三核 same-day 异构大小核流水线差异", font=F_TITLE, fill=HEAD)
    draw.text(
        (70, 104),
        "同日同板态下，左图给出 serial reconstruction，右图给出 big.LITTLE pipeline endpoint；底部补充各路线自身的 serial→pipeline 提升。",
        font=F_SUB,
        fill=MUTED,
    )
    draw_route_legend_row(draw, (70, 148, 2530, 224))

    left_rect = (70, 250, 1260, 980)
    right_rect = (1340, 250, 2530, 980)
    draw_zoom_panel(draw, left_rect, "串行执行时间（serial reconstruction median）", SERIAL_MS, "ms/image")
    draw_zoom_panel(draw, right_rect, "异构流水线时间（pipeline endpoint）", PIPELINE_MS, "ms/image")

    strip = (70, 1010, 2530, 1090)
    draw.rounded_rectangle(strip, radius=14, fill="#F4F7FA", outline=FRAME, width=1)
    draw.text((98, 1032), "各路线自身的 serial→pipeline 提升：", font=F_BODY, fill=HEAD)
    centers = [760, 1450, 2140]
    for (label, uplift, color), cx in zip(zip(ROUTE_SHORT_LABELS, UPLIFT, ROUTE_COLORS), centers):
        draw.rounded_rectangle((cx - 170, 1037, cx - 150, 1057), radius=4, fill=color)
        draw_multiline_center(draw, cx - 10, 1028, label, F_SMALL, INK)
        draw_multiline_center(draw, cx + 185, 1028, f"{uplift:.3f}%", F_NUM_BOLD, color)

    footer = "same-day big.LITTLE compare 下，latest handwritten mean4 v7 line 在 serial、pipeline endpoint 与 uplift 三项都领先另外两条路线。"
    draw.text((70, 1104), footer, font=F_SMALL, fill=MUTED)

    OUT3.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT3)


def draw_value_card(draw: ImageDraw.ImageDraw, rect, title: str, value: str, subtitle: str, color: str):
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=18, fill="#FFFFFF", outline=FRAME, width=2)
    draw.text((x0 + 24, y0 + 18), title, font=F_BODY, fill=color)
    draw.text((x0 + 24, y0 + 74), value, font=F_TITLE, fill=INK)
    draw.multiline_text((x0 + 24, y0 + 146), subtitle, font=F_SMALL, fill=MUTED, spacing=4)


def save_fig5():
    width, height = 2600, 1160
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 36), "系统关键性能跃迁与最新 OpenAMP 三核结果", font=F_TITLE, fill=HEAD)
    draw.text(
        (70, 104),
        "左侧保留固定形状 TVM 主线的长期收敛，右侧补充 2026-04-06 latest handwritten mean4 v7 在 OpenAMP 三核口径下的同日最新结论。",
        font=F_SUB,
        fill=MUTED,
    )

    left = (70, 180, 1280, 1080)
    right = (1340, 180, 2530, 1080)
    draw_box(draw, left)
    draw_box(draw, right)
    draw.text((96, 204), "固定形状 TVM 主线", font=F_BODY, fill=HEAD)
    draw.text((1366, 204), "OpenAMP 三核 latest handwritten 结果", font=F_BODY, fill=HEAD)

    # Left ladder
    lx0, ly0, lx1, ly1 = left
    points_y = [ly0 + 180, ly0 + 430, ly0 + 690]
    points_x = [lx0 + 960, lx0 + 500, lx0 + 280]
    for i in range(2):
        draw.line((points_x[i], points_y[i], points_x[i + 1], points_y[i + 1]), fill=GRID, width=8)
    for (label, value, color), x, y in zip(TVM_MAINLINE, points_x, points_y):
        draw.ellipse((x - 30, y - 30, x + 30, y + 30), fill=color, outline=BG, width=3)
        draw.rounded_rectangle((x - 170, y - 92, x + 170, y - 22), radius=16, fill="#FFFFFF", outline=color, width=2)
        draw_multiline_center(draw, x, y - 84, label, F_BODY, color)
        draw_multiline_center(draw, x, y + 46, f"{value:.1f} ms/image", F_NUM_BOLD, color)

    draw.text((lx0 + 88, ly1 - 100), "主线结论：4 核性能模式下，TVM 固定形状主路径已从 1850.0 ms/image 收敛到 230.3 ms/image，并在 big.LITTLE 流水线下进一步压到 134.6 ms/image。", font=F_SMALL, fill=MUTED)

    # Right highlight cards
    card_w = 520
    card_h = 240
    draw_value_card(
        draw,
        (1380, 300, 1380 + card_w, 300 + card_h),
        "same-day serial payload",
        "240.059 ms",
        "latest handwritten mean4 v7\ntrusted current 244.617 ms\nACL line 248.156 ms",
        HAND,
    )
    draw_value_card(
        draw,
        (1940, 300, 1940 + card_w, 300 + card_h),
        "same-day big.LITTLE endpoint",
        "249.393 ms/image",
        "latest handwritten mean4 v7\ntrusted current 257.388 ms/image\nACL line 262.922 ms/image",
        HAND,
    )
    draw_value_card(
        draw,
        (1380, 598, 1380 + card_w, 598 + card_h),
        "same-day throughput uplift",
        "38.706%",
        "latest handwritten mean4 v7\ntrusted current 34.569%\nACL line 33.814%",
        HAND,
    )
    draw_value_card(
        draw,
        (1940, 598, 1940 + card_w, 598 + card_h),
        "当前 strongest statement",
        "三项指标领先",
        "在 OpenAMP 三核 same-day compare 下，latest handwritten mean4 v7 line 已同时取得最低 serial reconstruction、最低 pipeline endpoint 与最高 uplift。",
        HEAD,
    )

    draw.text((1368, 930), "读图方式：左侧讲长期主线收敛，右侧讲 latest handwritten follow-up 的当前最好 OpenAMP 三核结论，两者分属不同时间口径。", font=F_SMALL, fill=MUTED)

    OUT5.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT5)


def main():
    save_fig2()
    save_fig3()
    save_fig5()
    print(OUT2)
    print(OUT3)
    print(OUT5)


if __name__ == "__main__":
    main()
