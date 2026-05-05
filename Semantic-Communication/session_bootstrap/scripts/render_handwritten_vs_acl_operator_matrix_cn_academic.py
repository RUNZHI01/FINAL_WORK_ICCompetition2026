#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "session_bootstrap" / "reports" / "figures" / "handwritten_vs_acl_operator_matrix_20260404_cn_academic.png"

WIDTH = 2400
HEIGHT = 2280
MARGIN = 80

FONT_ZH = Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf")
FONT_EN = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_EN_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

BG = "#FFFFFF"
INK = "#16263A"
MUTED = "#5C6B7A"
GRID = "#D5DDE5"
HEAD = "#183A5A"
BLUE_BG = "#EEF4FA"
TEAL = "#2F6F68"
TEAL_BG = "#EAF6F2"
RED = "#A04B3A"
RED_BG = "#FBEDEA"
AMBER = "#9A6A11"
AMBER_BG = "#FBF3E4"
ROW_BLUE = "#F6FAFD"
ROW_GREEN = "#F3FBF8"
ROW_RED = "#FEF6F4"
ROW_GRAY = "#FAFBFC"
ORANGE = "#D27B2C"


ROUTE_OK = [
    "fused_conv2d_transpose1_add9",
    "fused_conv2d_transpose_add6",
    "fused_conv2d_transpose2_add12",
]

ROUTE_MISSING = [
    "fused_variance3_add10_tir_sqrt3",
    "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
]

CAUSAL = [
    ("mean4", -6.530),
    ("variance3", -0.942),
    ("transpose_add6", -0.513),
    ("transpose1", -0.455),
    ("transpose2", 0.470),
]

ROWS = [
    (
        "fused_conv2d_transpose1_add9",
        "v7 promoted\n板级 payload 156.785 ms\n相对参考 -1.97%",
        "可信线 55.016 ms\nHandwritten 48.249 ms",
        "transpose1_asym\n26.611 ms\n仅 standalone",
        "ACL 可扩，但当前还没有 stock ACL 真正入图后的公平证据",
        ROW_BLUE,
    ),
    (
        "fused_conv2d_transpose_add6",
        "v1 accepted\n板级 payload 159.503 ms\n相对参考 -0.28%",
        "可信线 40.916 ms\nHandwritten 34.790 ms\n相对 ACL-line -0.513 ms",
        "transpose_add6_asym\n16.771 ms\n仅 standalone",
        "ACL 最值得继续追，但旧的 +33.9% 结论已失效",
        ROW_BLUE,
    ),
    (
        "fused_conv2d_transpose2_add12",
        "v1 accepted baseline\n板级 payload 161.416 ms\n相对参考 +0.92%",
        "可信线 43.912 ms\nHandwritten 39.143 ms",
        "transpose2_asym\n51.505 ms\n仅 standalone",
        "现有 ACL 信号偏负，三段 transpose 中优先级最低",
        ROW_BLUE,
    ),
    (
        "fused_variance4_add13_tir_sqrt4",
        "v18 frozen\n板级 payload 158.347 ms\n相对参考 -1.00%",
        "可信线约 7.045 ms",
        "无现成 stock ACL 路线",
        "手写小幅正收益，但 ACL 当前没有对应落地线",
        ROW_GREEN,
    ),
    (
        "fused_variance3_add10_tir_sqrt3",
        "v1.1 keep\n单算子 2771 us\n相对基线 -22.2%",
        "可信线 3.581 ms\nHandwritten final 2.736 ms",
        "无现成 stock ACL 路线",
        "这是 handwritten final 的关键收益点之一",
        ROW_GREEN,
    ),
    (
        "fused_variance1_add3_tir_sqrt1",
        "v1 Welford\n单算子 1315 us\n但 integrated A/B 回退",
        "整图相对可信线\n+9.459 ms",
        "无现成 stock ACL 路线",
        "典型反例：单算子很好看，但整图失败",
        ROW_RED,
    ),
    (
        "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
        "v4 keep\nmean4_only e2e 242.9 ms\n相对 trusted -3.26%",
        "Handwritten final 4.648 ms\n当前 ACL-line 11.178 ms",
        "无现成 stock ACL 路线",
        "当前 handwritten 相对 ACL-line 的最大领先来源",
        ROW_GREEN,
    ),
    (
        "fused_mean1_subtract1_divide1_multiply1_add4",
        "v1 仅已编译\n暂无正式板级性能",
        "可信线约 4.215 ms",
        "无现成 stock ACL 路线",
        "目前证据不足，不能下性能结论",
        ROW_GRAY,
    ),
    (
        "fused_conv2d3_add15",
        "v2 dropped\n板级 payload 161.999 ms\n相对基线 +0.62%",
        "可信线约 28.497 ms",
        "无现成 stock ACL 路线",
        "手写已证实当前无收益，ACL 也没有现成实验线",
        ROW_GRAY,
    ),
]


def load_font(size: int, zh: bool = True, bold: bool = False):
    path = FONT_ZH if zh else (FONT_EN_BOLD if bold else FONT_EN)
    if path.is_file():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


F_TITLE = load_font(68)
F_SUB = load_font(28)
F_PANEL = load_font(30)
F_BODY = load_font(22)
F_SMALL = load_font(18)
F_TABLE_HEAD = load_font(22)
F_OPERATOR = load_font(21, zh=False, bold=True)
F_TABLE = load_font(19)
F_BADGE = load_font(18)


def tsize(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    return x1 - x0, y1 - y0


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            trial = current + ch
            if current and draw.textlength(trial, font=font) > max_width:
                lines.append(current)
                current = ch
            else:
                current = trial
        lines.append(current)
    return "\n".join(lines)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=GRID, radius=18, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def badge(draw: ImageDraw.ImageDraw, box, text: str, fg: str, bg: str):
    draw.rounded_rectangle(box, radius=14, fill=bg)
    tw, th = tsize(draw, text, F_BADGE)
    x0, y0, x1, y1 = box
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + (y1 - y0 - th) / 2 - 1), text, font=F_BADGE, fill=fg)


def draw_box_title(draw: ImageDraw.ImageDraw, x: int, y: int, panel: str, title: str, subtitle: str):
    draw.text((x, y), panel, font=F_PANEL, fill=HEAD)
    draw.text((x + 46, y), title, font=F_PANEL, fill=INK)
    draw.text((x + 46, y + 38), subtitle, font=F_SMALL, fill=MUTED)


def render():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # header
    draw.rectangle((0, 0, WIDTH, 150), fill=BLUE_BG)
    draw.text((MARGIN, 34), "手写算子优化路线与 ACL 路线对比矩阵", font=F_TITLE, fill=HEAD)
    draw.text(
        (MARGIN, 108),
        "OpenAMP 三核板态，结合当前 JSCC 计算图；算子名保留英文，正文判断使用中文",
        font=F_SUB,
        fill=MUTED,
    )

    # Panel A
    ax0, ay0, ax1, ay1 = MARGIN, 188, WIDTH - MARGIN, 520
    rounded(draw, (ax0, ay0, ax1, ay1), "#FFFFFF")
    draw_box_title(draw, ax0 + 26, ay0 + 22, "A", "路线层判断", "ACL 可以扩成哪种多算子路线，以及当前还缺什么")

    left = (ax0 + 26, ay0 + 92, 1080, ay1 - 26)
    right = (1120, ay0 + 92, ax1 - 26, ay1 - 26)
    rounded(draw, left, TEAL_BG, outline="#CFE7DE")
    rounded(draw, right, AMBER_BG, outline="#F0DEC0")

    draw.text((left[0] + 20, left[1] + 18), "ACL 当前最现实的可扩展子集", font=F_PANEL, fill=TEAL)
    draw.text((right[0] + 20, right[1] + 18), "ACL 当前无法直接覆盖的真实收益点", font=F_PANEL, fill=AMBER)

    ly = left[1] + 70
    for item in ROUTE_OK:
        badge(draw, (left[0] + 20, ly, left[0] + 150, ly + 34), "可扩展", TEAL, "#DDF3EB")
        draw.text((left[0] + 170, ly + 2), item, font=F_OPERATOR, fill=INK)
        ly += 48

    ry = right[1] + 70
    for item in ROUTE_MISSING:
        badge(draw, (right[0] + 20, ry, right[0] + 166, ry + 34), "尚未覆盖", AMBER, "#F8EBCB")
        wrapped = wrap_text(draw, item, F_OPERATOR, right[2] - right[0] - 200)
        draw.multiline_text((right[0] + 186, ry + 2), wrapped, font=F_OPERATOR, fill=INK, spacing=2)
        ry += 64

    strip = (ax0 + 26, ay1 - 86, ax1 - 26, ay1 - 26)
    rounded(draw, strip, "#F7FAFC", outline=GRID)
    conclusion = (
        "结论：ACL 当前可以升级成“3 个 transpose 一起替换”的多算子路线；"
        "但不能直接等价替代 handwritten final，因为 handwritten 当前真正领先的部分还包含 variance3 与 mean4。"
    )
    draw.multiline_text((strip[0] + 20, strip[1] + 16), wrap_text(draw, conclusion, F_BODY, strip[2] - strip[0] - 40), font=F_BODY, fill=INK, spacing=4)

    # Panel B
    bx0, by0, bx1, by1 = MARGIN, 548, WIDTH - MARGIN, 818
    rounded(draw, (bx0, by0, bx1, by1), "#FFFFFF")
    draw_box_title(draw, bx0 + 26, by0 + 20, "B", "端到端方向反转的主要原因", "Handwritten final 相对当前 ACL 单点替换线的图内贡献项")

    chart_left = bx0 + 220
    chart_right = bx1 - 80
    chart_top = by0 + 108
    center = chart_left + 520
    draw.line((center, chart_top - 16, center, chart_top + 150), fill=GRID, width=3)
    max_abs = 7.0
    for i, (name, value) in enumerate(CAUSAL):
        y = chart_top + i * 34
        draw.text((bx0 + 42, y - 3), name, font=F_OPERATOR, fill=INK)
        length = int(abs(value) / max_abs * 370)
        if value < 0:
            x0, x1 = center - length, center
            fill = TEAL
        else:
            x0, x1 = center, center + length
            fill = ORANGE
        draw.rounded_rectangle((x0, y, x1, y + 18), radius=9, fill=fill)
        label = f"{value:+.3f} ms"
        tw, _ = tsize(draw, label, F_BODY)
        draw.text((chart_right - tw, y - 5), label, font=F_BODY, fill=fill)
    draw.text((bx0 + 42, by1 - 48), "负值表示 handwritten 更快；正值表示当前 ACL-line 更快。当前主要领先来源是 mean4 与 variance3。", font=F_SMALL, fill=MUTED)

    # Panel C
    cx0, cy0, cx1, cy1 = MARGIN, 846, WIDTH - MARGIN, HEIGHT - 70
    rounded(draw, (cx0, cy0, cx1, cy1), "#FFFFFF")
    draw_box_title(draw, cx0 + 26, cy0 + 20, "C", "算子级性能矩阵", "表中汇总当前所有 handwritten lane，以及 ACL 在 repo 内真正已有的证据")

    top = cy0 + 92
    left = cx0 + 20
    right = cx1 - 20
    cols = [
        ("算子", 430),
        ("手写最强证据", 520),
        ("OpenAMP 3 核图内", 360),
        ("ACL 当前证据", 300),
        ("当前判断", right - left - 430 - 520 - 360 - 300),
    ]

    x = left
    header_h = 48
    for title, width in cols:
        draw.rectangle((x, top, x + width - 8, top + header_h), fill=HEAD)
        draw.text((x + 12, top + 10), title, font=F_TABLE_HEAD, fill="#FFFFFF")
        x += width

    row_h = 96
    y = top + header_h + 10
    for operator, hand, graph, acl, judge, fill in ROWS:
        draw.rectangle((left, y, right - 8, y + row_h), fill=fill, outline=GRID)
        x = left
        cells = [
            (operator, F_OPERATOR, cols[0][1]),
            (hand, F_TABLE, cols[1][1]),
            (graph, F_TABLE, cols[2][1]),
            (acl, F_TABLE, cols[3][1]),
            (judge, F_TABLE, cols[4][1]),
        ]
        for text, font, width in cells:
            wrapped = wrap_text(draw, text, font, width - 24)
            draw.multiline_text((x + 12, y + 10), wrapped, font=font, fill=INK, spacing=4)
            x += width
        y += row_h + 8

    foot = (
        "注：当前 repo 内真正有 stock ACL 对位证据的只包括 transpose family；"
        "variance/mean 相关收益目前仍主要由 TVM/handwritten 路线提供。"
    )
    draw.multiline_text((cx0 + 26, cy1 - 56), wrap_text(draw, foot, F_SMALL, cx1 - cx0 - 52), font=F_SMALL, fill=MUTED, spacing=4)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT, format="PNG", optimize=True)
    print(OUTPUT)


if __name__ == "__main__":
    render()
