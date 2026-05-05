#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "session_bootstrap" / "reports" / "figures" / "paper_fig_serial_reconstruction_handwritten_hotspots_cn_20260428.png"

WIDTH = 2600
HEIGHT = 1680
MARGIN = 76

FONT_ZH = Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf")
FONT_EN = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_EN_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

BG = "#FFFFFF"
INK = "#12243A"
MUTED = "#5D6B7A"
GRID = "#D6DEE7"
FRAME = "#AEBCC9"
HEAD = "#14365A"
BASE = "#7F8C99"
HAND = "#1B9E77"
ACL = "#D95F02"
BAD = "#B84A3A"
NA_BG = "#EEF2F6"


ROUTE_SERIAL = [
    ("TVM MetaSchedule\nTrusted Current", 347.341, BASE),
    ("Handwritten\nmean4 v7", 345.609, HAND),
    ("ACL integration\nline", 352.158, ACL),
]

HOTSPOT_ROWS = [
    ("transpose1", "ref", 159.943, "v7", 156.785, "-1.97%", HAND),
    ("transpose_add6", "ref", 159.943, "v1", 159.503, "-0.28%", HAND),
    ("transpose2", "ref", 159.943, "v1", 161.416, "+0.92%", BAD),
    ("conv2d3_add15", "ref", 159.943, "v2", 161.999, "+1.29%", BAD),
    ("variance4", "ref", 159.943, "v18", 158.347, "-1.00%", HAND),
    ("mean4", "control", 243.460, "v7", 238.602, "-2.00%", HAND),
]

STATUS_ROWS = [
    ("variance3", "standalone only", "3.562 -> 2.736 ms"),
    ("mean3", "no formal serial", "shortlist only"),
]


def font(size: int, zh: bool = True, bold: bool = False):
    path = FONT_ZH if zh else (FONT_EN_BOLD if bold else FONT_EN)
    if path.is_file():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


F_TITLE = font(58)
F_SUB = font(25)
F_PANEL = font(31)
F_BODY = font(22)
F_SMALL = font(18)
F_NUM = font(20, zh=False, bold=True)
F_LABEL = font(20, zh=False, bold=True)
F_ROUTE = font(20, zh=False)


def tsize(draw: ImageDraw.ImageDraw, text: str, f) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=f)
    return x1 - x0, y1 - y0


def wrap(draw: ImageDraw.ImageDraw, text: str, f, max_width: int) -> str:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            trial = current + ch
            if current and draw.textlength(trial, font=f) > max_width:
                lines.append(current)
                current = ch
            else:
                current = trial
        lines.append(current)
    return "\n".join(lines)


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=18, fill="#FFFFFF", outline=FRAME, width=2)


def draw_panel_title(draw: ImageDraw.ImageDraw, x: int, y: int, title: str, subtitle: str) -> None:
    draw.text((x, y), title, font=F_PANEL, fill=HEAD)
    draw.text((x, y + 42), subtitle, font=F_SMALL, fill=MUTED)


def map_y(value: float, y_bottom: int, y_top: int, vmin: float, vmax: float) -> int:
    return int(y_bottom - (value - vmin) / (vmax - vmin) * (y_bottom - y_top))


def panel_routes(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    card(draw, box)
    draw_panel_title(draw, x0 + 28, y0 + 24, "三条路线 Serial Reconstruction Median", "单位：ms/image；越低越好")

    chart_x0 = x0 + 110
    chart_x1 = x1 - 70
    chart_y0 = y0 + 140
    chart_y1 = y1 - 118
    vmin, vmax = 342.0, 354.5

    for tick in [342, 345, 348, 351, 354]:
        ty = map_y(tick, chart_y1, chart_y0, vmin, vmax)
        draw.line((chart_x0, ty, chart_x1, ty), fill=GRID, width=1)
        label = f"{tick}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((chart_x0 - tw - 14, ty - 11), label, font=F_NUM, fill=MUTED)
    draw.line((chart_x0, chart_y0, chart_x0, chart_y1), fill=FRAME, width=2)
    draw.line((chart_x0, chart_y1, chart_x1, chart_y1), fill=FRAME, width=2)

    centers = [chart_x0 + 210, (chart_x0 + chart_x1) // 2, chart_x1 - 210]
    bw = 132
    for (name, value, color), cx in zip(ROUTE_SERIAL, centers):
        top = map_y(value, chart_y1, chart_y0, vmin, vmax)
        draw.rounded_rectangle((cx - bw // 2, top, cx + bw // 2, chart_y1), radius=14, fill=color)
        label = f"{value:.3f}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((cx - tw / 2, top - 30), label, font=F_NUM, fill=color)
        wrapped = wrap(draw, name, F_ROUTE, 210)
        text_w = max(draw.textlength(line, font=F_ROUTE) for line in wrapped.split("\n"))
        draw.multiline_text((cx - text_w / 2, chart_y1 + 22), wrapped, font=F_ROUTE, fill=INK, spacing=4)


def panel_hotspots(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    card(draw, box)
    draw_panel_title(draw, x0 + 28, y0 + 24, "Handwritten 热点候选 Serial/Payload Median", "每组灰色为该轮 reference/control，彩色为该热点候选；单位：ms")

    chart_x0 = x0 + 92
    chart_x1 = x1 - 380
    chart_y0 = y0 + 132
    chart_y1 = y1 - 120
    vmin, vmax = 150.0, 250.0

    for tick in [150, 170, 190, 210, 230, 250]:
        ty = map_y(tick, chart_y1, chart_y0, vmin, vmax)
        draw.line((chart_x0, ty, chart_x1, ty), fill=GRID, width=1)
        label = f"{tick}"
        tw, _ = tsize(draw, label, F_NUM)
        draw.text((chart_x0 - tw - 14, ty - 11), label, font=F_NUM, fill=MUTED)
    draw.line((chart_x0, chart_y0, chart_x0, chart_y1), fill=FRAME, width=2)
    draw.line((chart_x0, chart_y1, chart_x1, chart_y1), fill=FRAME, width=2)

    group_w = (chart_x1 - chart_x0) / len(HOTSPOT_ROWS)
    bw = 46
    for i, (op, base_label, base_value, cand_label, cand_value, delta, color) in enumerate(HOTSPOT_ROWS):
        cx = int(chart_x0 + group_w * (i + 0.5))
        for value, bar_color, xoff, label in [
            (base_value, BASE, -32, base_label),
            (cand_value, color, 32, cand_label),
        ]:
            top = map_y(value, chart_y1, chart_y0, vmin, vmax)
            draw.rounded_rectangle((cx + xoff - bw // 2, top, cx + xoff + bw // 2, chart_y1), radius=9, fill=bar_color)
            val = f"{value:.1f}"
            tw, _ = tsize(draw, val, F_NUM)
            draw.text((cx + xoff - tw / 2, top - 24), val, font=F_NUM, fill=bar_color)
            lw, _ = tsize(draw, label, F_SMALL)
            draw.text((cx + xoff - lw / 2, chart_y1 + 10), label, font=F_SMALL, fill=MUTED)
        dcolor = HAND if delta.startswith("-") else BAD
        dw, _ = tsize(draw, delta, F_NUM)
        draw.text((cx - dw / 2, chart_y1 + 38), delta, font=F_NUM, fill=dcolor)
        wrapped = wrap(draw, op, F_LABEL, 180)
        text_w = max(draw.textlength(line, font=F_LABEL) for line in wrapped.split("\n"))
        draw.multiline_text((cx - text_w / 2, chart_y1 + 68), wrapped, font=F_LABEL, fill=INK, spacing=3)

    legend_x = chart_x1 + 36
    legend_y = chart_y0 + 10
    draw.rectangle((legend_x, legend_y, legend_x + 24, legend_y + 24), fill=BASE)
    draw.text((legend_x + 36, legend_y - 1), "reference / control", font=F_SMALL, fill=INK)
    draw.rectangle((legend_x, legend_y + 42, legend_x + 24, legend_y + 66), fill=HAND)
    draw.text((legend_x + 36, legend_y + 41), "candidate faster", font=F_SMALL, fill=INK)
    draw.rectangle((legend_x, legend_y + 84, legend_x + 24, legend_y + 108), fill=BAD)
    draw.text((legend_x + 36, legend_y + 83), "candidate slower", font=F_SMALL, fill=INK)

    status_y = legend_y + 150
    draw.text((legend_x, status_y), "仅有非 serial 证据", font=F_BODY, fill=HEAD)
    for j, (op, status, value) in enumerate(STATUS_ROWS):
        sy = status_y + 48 + j * 78
        draw.rounded_rectangle((legend_x, sy, x1 - 32, sy + 58), radius=12, fill=NA_BG, outline=GRID, width=1)
        draw.text((legend_x + 14, sy + 8), op, font=F_LABEL, fill=INK)
        draw.text((legend_x + 14, sy + 32), f"{status}: {value}", font=F_SMALL, fill=MUTED)


def render() -> Path:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    draw.text((MARGIN, 42), "三条路线与 Handwritten 全热点候选对比", font=F_TITLE, fill=HEAD)
    draw.text((MARGIN, 112), "只展示 serial / payload median；不混入 pipeline 指标", font=F_SUB, fill=MUTED)

    panel_routes(draw, (MARGIN, 170, WIDTH - MARGIN, 720))
    panel_hotspots(draw, (MARGIN, 760, WIDTH - MARGIN, HEIGHT - 70))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    return OUT


if __name__ == "__main__":
    print(render())
