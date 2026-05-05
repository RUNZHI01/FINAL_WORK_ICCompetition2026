#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import fill

import fitz
import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import seaborn as sns
import scienceplots  # noqa: F401
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
TIKZ_DIR = ROOT / "paper" / "tikz_figures_enhanced"


@dataclass(frozen=True)
class PdfAsset:
    source: Path
    target: Path
    scale: float = 2.8


PDF_ASSETS = [
    PdfAsset(
        source=TIKZ_DIR / "fig_system_arch_CLEAN.pdf",
        target=FIG_DIR / "paper_fig_system_arch_cn_20260405.png",
        scale=3.0,
    ),
    PdfAsset(
        source=TIKZ_DIR / "fig_gan_jscc_enhanced.pdf",
        target=FIG_DIR / "paper_fig_gan_jscc_cn_20260405.png",
        scale=3.0,
    ),
    PdfAsset(
        source=TIKZ_DIR / "fig_openamp_state_machine_enhanced.pdf",
        target=FIG_DIR / "paper_fig_openamp_state_machine_cn_20260405.png",
        scale=3.0,
    ),
    PdfAsset(
        source=TIKZ_DIR / "fig_tvm_opt_flow_enhanced.pdf",
        target=FIG_DIR / "paper_fig_tvm_opt_flow_cn_20260405.png",
        scale=3.0,
    ),
]

PROJECT_TIMELINE = [
    ("03-01", "基础打通", "飞腾派 TVM 推理首次成功"),
    ("03-08~10", "运行时重建", "TVM 0.24 安全运行时与 A72 目标收敛"),
    ("03-11~13", "性能突破", "端到端 1850 ms 降至 230 ms"),
    ("03-14~15", "控制面闭环", "OpenAMP 五类消息 + 三项 FIT 收证"),
    ("03-18", "异构加速", "big.LITTLE 流水线吞吐提升 56.1%"),
    ("03-17~30", "演示集成", "current live 300/300 与界面收口"),
]

PERFORMANCE_LADDER = [
    {
        "title": "初始端到端",
        "value": "1850.0",
        "unit": "ms/image",
        "note": "旧执行链路 / 4-core Linux",
        "color": "#7A8794",
    },
    {
        "title": "TVM 主线优化后",
        "value": "230.3",
        "unit": "ms/image",
        "note": "固定形状端到端",
        "color": "#2D6A4F",
    },
    {
        "title": "big.LITTLE 流水线",
        "value": "134.6",
        "unit": "ms/image",
        "note": "4-core 吞吐主口径",
        "color": "#1B9E77",
    },
]

TVM_RESULT_SUMMARY = [
    ("端到端直通", "230.3", "ms/image", "4-core Linux / 固定形状"),
    ("异构流水线", "134.6", "ms/image", "big.LITTLE 吞吐主口径"),
    ("Throughput Uplift", "+56.1%", "", "vs serial current"),
    ("Quality", "35.66 / 0.9728", "PSNR / SSIM", "优化未牺牲重建质量"),
    ("Integrity", "300 / 300", "PNG outputs", "完整真实重建链路"),
    ("Footprint", "1.57 MiB", "artifact size", "min free mem 88,340 KB"),
]

EVIDENCE_BUNDLE_CARDS = [
    {
        "title": "总判定 / 覆盖矩阵",
        "color": "#335C81",
        "lines": [
            "summary_report.md",
            "coverage_matrix.md",
            "P0 / P1 闭环与边界总入口",
        ],
    },
    {
        "title": "live 状态收口",
        "color": "#1B9E77",
        "lines": [
            "openamp_demo_live_dualpath_status_20260317.md",
            "current 300/300 / valid instance 8115",
            "TC-002 live reconstruction 证据",
        ],
    },
    {
        "title": "FIT 安全验证",
        "color": "#D95F02",
        "lines": [
            "FIT-01 wrong SHA",
            "FIT-02 input contract",
            "FIT-03 heartbeat timeout / watchdog",
        ],
    },
    {
        "title": "性能与质量",
        "color": "#6A4C93",
        "lines": [
            "230.339 / 134.617 / 327.3 ms",
            "PSNR 35.66 / SSIM 0.9728",
            "resource profile / compare reports",
        ],
    },
    {
        "title": "演示与话术",
        "color": "#1F7A8C",
        "lines": [
            "operator runbook / rehearsal result",
            "mode boundary / defense talk track",
            "证据驱动，不做现场临时排障",
        ],
    },
]


OPENAMP_STATES = {
    "READY": (0.15, 0.72),
    "CHECKING": (0.42, 0.72),
    "RUNNING": (0.72, 0.72),
    "SAFE_STOP": (0.72, 0.30),
    "FAULT": (0.42, 0.30),
}

OPENAMP_LABELS = {
    "READY": "READY\n空闲待命",
    "CHECKING": "CHECKING\n工件/参数校验",
    "RUNNING": "RUNNING\n心跳监护激活",
    "SAFE_STOP": "SAFE_STOP\n安全停机与收敛",
    "FAULT": "FAULT\n故障留痕",
}

OPENAMP_COLORS = {
    "READY": "#1F7A8C",
    "CHECKING": "#6A4C93",
    "RUNNING": "#1B9E77",
    "SAFE_STOP": "#D95F02",
    "FAULT": "#C1121F",
}

MNN_BENCHMARK = {
    "基线\n1I/1T/FP32": 140.7,
    "正式最优\n2I/1T/FP32": 98.2,
    "低精度\n2I/1T/low": 99.1,
    "多线程\n2I/2T/FP32": 101.3,
}

FRAMEWORK_POSITIONING = [
    {
        "label": "TVM big.LITTLE",
        "value": 134.6,
        "color": "#1B9E77",
        "tag": "4-core / 固定形状 / 吞吐",
    },
    {
        "label": "TVM serial",
        "value": 230.3,
        "color": "#2D6A4F",
        "tag": "4-core / 固定形状 / 端到端",
    },
    {
        "label": "MNN dynamic",
        "value": 327.3,
        "color": "#335C81",
        "tag": "混合尺寸 / 无需预缩放 / 灵活部署",
    },
    {
        "label": "PyTorch ref",
        "value": 484.2,
        "color": "#7A8794",
        "tag": "reference baseline",
    },
]

PERF_QUALITY_POINTS = [
    {
        "label": "初始版本",
        "latency": 1850.0,
        "psnr": 34.42,
        "color": "#7A8794",
        "note": "旧执行链路 / 4-core Linux",
    },
    {
        "label": "TVM direct",
        "latency": 230.3,
        "psnr": 35.66,
        "color": "#2D6A4F",
        "note": "固定形状端到端",
    },
    {
        "label": "TVM pipeline",
        "latency": 134.6,
        "psnr": 35.66,
        "color": "#1B9E77",
        "note": "big.LITTLE 吞吐主口径",
    },
]

SNR_POINTS = np.array([1, 4, 7, 10, 13], dtype=float)
SNR_LAT_MS = np.array([228.223, 228.595, 233.509, 231.893, 234.018], dtype=float)
SNR_PSNR = np.array([29.1452, 31.8047, 34.0185, 35.6644, 36.8695], dtype=float)
SNR_SSIM = np.array([0.900039, 0.939559, 0.961243, 0.972735, 0.978757], dtype=float)

QUALITY_ROOT = ROOT / "session_bootstrap" / "tmp" / "quality_metrics_inputs_20260312" / "reference" / "reconstructions"
SNR_ROOT = ROOT / "session_bootstrap" / "tmp" / "snr_sweep_current_chunk4_20260330_152054"
RECON_SAMPLES = [
    "Places365_val_00000317_recon.png",
    "Places365_val_00000437_recon.png",
]


def choose_font() -> fm.FontProperties:
    candidates = [
        Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return fm.FontProperties(fname=str(path))
    return fm.FontProperties()


FONT_PROP = choose_font()


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_pil_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[Path] = []
    if bold:
        candidates.extend(
            [
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
                Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"),
                Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
            ]
        )
    candidates.extend(
        [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
            Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def wrap_mixed_text(text: str, max_units: int) -> str:
    lines: list[str] = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        current = ""
        current_units = 0
        for ch in raw:
            units = 1 if (ch.isascii() and ch not in "MW@#%") else 2
            if current and current_units + units > max_units:
                lines.append(current.rstrip())
                current = ch
                current_units = units
            else:
                current += ch
                current_units += units
        if current:
            lines.append(current.rstrip())
    return "\n".join(lines)


def pil_text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, spacing: int = 6) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def pil_shadow(canvas: Image.Image, box: tuple[int, int, int, int], radius: int = 28, alpha: int = 48, y_shift: int = 14) -> None:
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x0, y0 + y_shift, x1, y1 + y_shift), radius=radius, fill=(15, 31, 49, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(20))
    canvas.alpha_composite(layer)


def pil_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str = "#FFFFFF",
    outline: str = "#D4DEEA",
    radius: int = 30,
    width: int = 2,
    shadow: bool = True,
) -> None:
    if shadow:
        pil_shadow(canvas, box, radius=radius)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pil_badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fill: str,
    *,
    font: ImageFont.ImageFont,
    text_fill: str = "#FFFFFF",
    pad_x: int = 18,
    pad_y: int = 10,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    box = (x, y, x + (right - left) + pad_x * 2, y + (bottom - top) + pad_y * 2)
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    draw.text((x + pad_x, y + pad_y - 2), text, fill=text_fill, font=font)
    return box


def pil_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 6) -> None:
    draw.line([start, end], fill=color, width=width)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    head = 18
    wing = 10
    p1 = (end[0], end[1])
    p2 = (int(end[0] - ux * head + px * wing), int(end[1] - uy * head + py * wing))
    p3 = (int(end[0] - ux * head - px * wing), int(end[1] - uy * head - py * wing))
    draw.polygon([p1, p2, p3], fill=color)


def pil_poly_arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, width: int = 6) -> None:
    if len(points) < 2:
        return
    draw.line(points, fill=color, width=width)
    pil_arrow(draw, points[-2], points[-1], color, width=width)


def pil_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    *,
    dash: int = 20,
    gap: int = 12,
    width: int = 3,
) -> None:
    x0, y0 = start
    x1, y1 = end
    total = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if total == 0:
        return
    dx = (x1 - x0) / total
    dy = (y1 - y0) / total
    drawn = 0.0
    while drawn < total:
        seg = min(dash, total - drawn)
        sx = x0 + dx * drawn
        sy = y0 + dy * drawn
        ex = x0 + dx * (drawn + seg)
        ey = y0 + dy * (drawn + seg)
        draw.line((sx, sy, ex, ey), fill=color, width=width)
        drawn += dash + gap


def pil_header(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    title: str,
    subtitle: str,
    title_font: ImageFont.ImageFont,
    subtitle_font: ImageFont.ImageFont,
    subtitle_width: int = 86,
) -> int:
    draw.text((x, y), title, fill="#173A5E", font=title_font)
    _, title_h = pil_text_size(draw, title, title_font)
    wrapped = wrap_mixed_text(subtitle, subtitle_width)
    subtitle_y = y + title_h + 18
    draw.multiline_text((x, subtitle_y), wrapped, fill="#5B6D80", font=subtitle_font, spacing=10)
    _, subtitle_h = pil_text_size(draw, wrapped, subtitle_font, spacing=10)
    return subtitle_y + subtitle_h


def render_pdf(asset: PdfAsset) -> None:
    ensure_dir(asset.target)
    doc = fitz.open(asset.source)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(asset.scale, asset.scale), alpha=False)
    pix.save(asset.target)
    doc.close()


def apply_plot_style() -> None:
    plt.style.use(["science", "no-latex", "grid"])
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.family"] = FONT_PROP.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "#FFFFFF"
    plt.rcParams["axes.facecolor"] = "#FFFFFF"
    plt.rcParams["grid.color"] = "#D9E1E8"
    plt.rcParams["axes.edgecolor"] = "#AAB8C4"
    plt.rcParams["axes.labelcolor"] = "#173A5E"
    plt.rcParams["text.color"] = "#13263A"
    plt.rcParams["xtick.color"] = "#13263A"
    plt.rcParams["ytick.color"] = "#13263A"


def add_rounded_box(
    ax: plt.Axes,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    color: str,
    text: str,
) -> None:
    box = patches.FancyBboxPatch(
        (center_x - width / 2.0, center_y - height / 2.0),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        linewidth=2.0,
        edgecolor=color,
        facecolor="#F8FBFD",
    )
    ax.add_patch(box)
    ax.text(
        center_x,
        center_y,
        text,
        ha="center",
        va="center",
        fontsize=15,
        fontproperties=FONT_PROP,
        color="#13263A",
        linespacing=1.5,
        weight="bold",
    )


def add_arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    label: str,
    color: str = "#5B6D80",
    curve: float = 0.0,
    text_offset: tuple[float, float] = (0.0, 0.0),
) -> None:
    arrow = patches.FancyArrowPatch(
        start,
        end,
        connectionstyle=f"arc3,rad={curve}",
        arrowstyle="-|>",
        mutation_scale=18,
        linewidth=2.0,
        color=color,
    )
    ax.add_patch(arrow)
    mid_x = (start[0] + end[0]) / 2.0 + text_offset[0]
    mid_y = (start[1] + end[1]) / 2.0 + text_offset[1]
    ax.text(
        mid_x,
        mid_y,
        label,
        ha="center",
        va="center",
        fontsize=12,
        fontproperties=FONT_PROP,
        color=color,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor="none", alpha=0.92),
    )


def render_gan_jscc(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2200, 1200), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(52, bold=True)
    f_sub = load_pil_font(28)
    f_section = load_pil_font(30, bold=True)
    f_block = load_pil_font(30, bold=True)
    f_text = load_pil_font(24)
    f_small = load_pil_font(22)
    header_bottom = pil_header(
        draw,
        x=86,
        y=54,
        title="GAN-based JSCC 系统结构图",
        subtitle="上层只保留部署阶段真正使用的编码-信道-生成主链；训练期才启用的 Discriminator 与损失函数被单独下沉到第二层，避免压住主路径。",
        title_font=f_title,
        subtitle_font=f_sub,
    )

    top_box = (80, header_bottom + 44, 2120, 630)
    train_box = (80, 710, 2120, 1080)
    pil_panel(canvas, draw, top_box, fill="#F8FBFF", outline="#D3E2F1", radius=34)
    pil_panel(canvas, draw, train_box, fill="#FFF9F4", outline="#F0D8BC", radius=34)
    pil_badge(draw, 110, top_box[1] + 22, "部署主链", "#2C6BFF", font=load_pil_font(22, bold=True))
    pil_badge(draw, 110, train_box[1] + 22, "训练期附加模块", "#E17A21", font=load_pil_font(22, bold=True))
    draw.text((128, top_box[1] + 84), "发送端", fill="#173A5E", font=f_section)
    draw.text((1752, top_box[1] + 84), "接收端", fill="#173A5E", font=f_section)

    blocks = [
        ((180, 360, 470, 500), "#EAF4FF", "#BFD6F4", "Encoder", "输入图像 x -> latent y"),
        ((560, 360, 850, 500), "#EDF6FF", "#C6D9EE", "功率控制", "归一化并匹配发送功率"),
        ((950, 360, 1240, 500), "#F0FAF3", "#BFDCC7", "AWGN", "弱网信道噪声 n"),
        ((1340, 360, 1650, 500), "#F5F0FA", "#D5C8E6", "Generator", "y_hat -> 重建图像"),
        ((1760, 360, 2040, 500), "#FFFFFF", "#BFCBDA", "x_hat", "部署阶段输出"),
    ]
    for box, fill_color, outline_color, title, detail in blocks:
        pil_panel(canvas, draw, box, fill=fill_color, outline=outline_color, radius=28, shadow=False)
        draw.text((box[0] + 34, box[1] + 34), title, fill="#13263A", font=f_block)
        wrapped = wrap_mixed_text(detail, 18)
        draw.multiline_text((box[0] + 34, box[1] + 84), wrapped, fill="#5B6D80", font=f_text, spacing=8)

    pil_arrow(draw, (470, 430), (560, 430), "#4F647A")
    pil_arrow(draw, (850, 430), (950, 430), "#4F647A")
    pil_arrow(draw, (1240, 430), (1340, 430), "#4F647A")
    pil_arrow(draw, (1650, 430), (1760, 430), "#4F647A")
    pil_badge(draw, 492, 384, "y ∈ R^{1×32³}", "#335C81", font=load_pil_font(18, bold=True), pad_x=12, pad_y=6)
    pil_badge(draw, 890, 384, "√P·y", "#1F7A8C", font=load_pil_font(18, bold=True), pad_x=12, pad_y=6)
    pil_badge(draw, 1276, 384, "y_hat = √P·y + n", "#1B9E77", font=load_pil_font(18, bold=True), pad_x=12, pad_y=6)
    pil_badge(draw, 1686, 384, "1×3×256×256", "#6A4C93", font=load_pil_font(18, bold=True), pad_x=12, pad_y=6)

    draw.text((206, 548), "Conv -> BN -> ReLU -> Res×2", fill="#5B6D80", font=f_small)
    draw.text((1368, 548), "Deconv -> BN -> ReLU -> Res×2", fill="#5B6D80", font=f_small)

    loss_box = (126, 800, 720, 1010)
    disc_box = (930, 820, 1280, 980)
    train_note_box = (1470, 800, 2044, 1010)
    pil_panel(canvas, draw, loss_box, fill="#FFFFFF", outline="#D6E0EA", radius=28, shadow=False)
    pil_panel(canvas, draw, disc_box, fill="#FFF1F4", outline="#F0C7D0", radius=28, shadow=False)
    pil_panel(canvas, draw, train_note_box, fill="#FFFFFF", outline="#D6E0EA", radius=28, shadow=False)
    draw.text((158, 840), "训练损失", fill="#173A5E", font=f_block)
    loss_text = wrap_mixed_text("L_t = λ_G + α·L_MSE + β·L_LPIPS\nL_G / L_D 只在训练期参与对抗学习。", 28)
    draw.multiline_text((158, 894), loss_text, fill="#5B6D80", font=f_text, spacing=8)
    draw.text((992, 866), "Discriminator", fill="#13263A", font=f_block)
    draw.text((992, 918), "接收 ground truth x\n与重建 x_hat 做对抗判别", fill="#5B6D80", font=f_text, spacing=8)
    draw.text((1504, 840), "部署说明", fill="#173A5E", font=f_block)
    deploy_note = wrap_mixed_text("部署阶段只保留 Encoder / AWGN 模拟 / Generator 主链；Discriminator 与损失项不会进入飞腾端运行时。", 30)
    draw.multiline_text((1504, 894), deploy_note, fill="#5B6D80", font=f_text, spacing=8)

    pil_poly_arrow(draw, [(188, 500), (188, 760), (930, 760), (930, 870)], "#B48A43", width=5)
    pil_poly_arrow(draw, [(1900, 500), (1900, 760), (1280, 760), (1280, 870)], "#D04F6B", width=5)
    pil_badge(draw, 404, 734, "ground truth x", "#B48A43", font=load_pil_font(18, bold=True), pad_x=12, pad_y=6)
    pil_badge(draw, 1508, 734, "reconstructed x_hat", "#D04F6B", font=load_pil_font(18, bold=True), pad_x=12, pad_y=6)

    footer = (80, 1110, 2120, 1168)
    draw.rounded_rectangle(footer, radius=22, fill="#EAF2F8", outline="#D3DFEA", width=2)
    footer_text = "读图方式：上层只看部署主链，下层只看训练附加模块。这样能同时解释 GAN-based JSCC 的来源与飞腾端实际部署边界。"
    draw.text((112, 1126), footer_text, fill="#42586E", font=f_small)
    canvas.convert("RGB").save(target)


def render_tvm_opt_flow(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2100, 1460), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(52, bold=True)
    f_sub = load_pil_font(28)
    f_stage = load_pil_font(30, bold=True)
    f_text = load_pil_font(24)
    f_small = load_pil_font(22)
    header_bottom = pil_header(
        draw,
        x=86,
        y=54,
        title="TVM 编译优化流程图",
        subtitle="按“能不能跑 -> 跑在哪个 target -> 如何缩短时间 -> 如何归因验证”的顺序重排，避免把 baseline/current、流程节点和结论说明压在同一层。",
        title_font=f_title,
        subtitle_font=f_sub,
    )

    stage_specs = [
        ("1", "运行时重建", "剥离 torch 依赖，恢复 safe runtime 的最小可执行链路。", "结果：current 路线可加载"),
        ("2", "target 收敛", "将目标收敛到 cortex-a72 + neon，并确认 artifact 可在飞腾派稳定运行。", "结果：从 generic 迁到 A72"),
        ("3", "增量调优", "以 rebuild-only / payload-only 为过渡口径，逐步把调优预算押到真实瓶颈上。", "结果：500 trials 收敛到 152 ms"),
        ("4", "真实重建评测", "回到 300 张图像的真实端到端链路，确认收益不是只存在于 micro benchmark。", "结果：端到端 230.3 ms/image"),
        ("5", "Profiling 与手写算子", "按热点算子证据链补手写 TIR/NEON，保留正收益 lane，放弃负收益方向。", "结果：big.LITTLE 134.6 ms/image"),
    ]
    accent = ["#335C81", "#6A4C93", "#1B9E77", "#1F7A8C", "#D95F02"]
    top_y = header_bottom + 54
    box_h = 170
    gap = 34
    for idx, ((num, title, body, outcome), color) in enumerate(zip(stage_specs, accent)):
        y0 = top_y + idx * (box_h + gap)
        box = (180, y0, 1980, y0 + box_h)
        pil_panel(canvas, draw, box, fill="#FFFFFF", outline="#D4DEEA", radius=30)
        circle = (104, y0 + 38, 158, y0 + 92)
        draw.ellipse(circle, fill=color, outline="#FFFFFF", width=4)
        draw.text((121, y0 + 49), num, fill="#FFFFFF", font=load_pil_font(24, bold=True))
        pil_badge(draw, 220, y0 + 24, title, color, font=load_pil_font(22, bold=True), pad_x=16, pad_y=8)
        draw.text((220, y0 + 86), wrap_mixed_text(body, 58), fill="#173A5E", font=f_stage)
        note_box = (1320, y0 + 34, 1928, y0 + 134)
        draw.rounded_rectangle(note_box, radius=24, fill="#F7FAFD", outline="#D6E0EA", width=2)
        draw.text((1350, y0 + 58), "关键收口", fill=color, font=load_pil_font(22, bold=True))
        draw.multiline_text((1350, y0 + 92), wrap_mixed_text(outcome, 24), fill="#5B6D80", font=f_text, spacing=8)
        if idx < len(stage_specs) - 1:
            pil_arrow(draw, (1060, y0 + box_h), (1060, y0 + box_h + gap - 6), "#B8C7D6", width=5)

    footer = (86, 1360, 2010, 1420)
    draw.rounded_rectangle(footer, radius=22, fill="#EAF2F8", outline="#D3DFEA", width=2)
    footer_text = "这张图只讲主线证据链，不再把旧 baseline/current 两条路线压成同一层流程图。"
    draw.text((118, 1377), footer_text, fill="#42586E", font=f_small)
    canvas.convert("RGB").save(target)


def render_mnn_arch(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2200, 1280), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(50, bold=True)
    f_sub = load_pil_font(28)
    f_block = load_pil_font(30, bold=True)
    f_text = load_pil_font(24)
    f_small = load_pil_font(21)
    header_bottom = pil_header(
        draw,
        x=86,
        y=54,
        title="MNN 架构示意图",
        subtitle="主执行链只保留“模型导入 -> 解析优化 -> Interpreter/Session -> Backend”；动态尺寸、搜索和 NEON 则下沉到能力层，避免所有模块挤在同一平面。",
        title_font=f_title,
        subtitle_font=f_sub,
    )

    main_band = (80, header_bottom + 42, 2120, 640)
    capability_band = (80, 720, 2120, 1130)
    pil_panel(canvas, draw, main_band, fill="#F8FBFF", outline="#D3E2F1", radius=34)
    pil_panel(canvas, draw, capability_band, fill="#FFF9F4", outline="#F0D8BC", radius=34)
    pil_badge(draw, 112, main_band[1] + 22, "主执行链", "#2C6BFF", font=load_pil_font(22, bold=True))
    pil_badge(draw, 112, capability_band[1] + 22, "优化与部署能力", "#E17A21", font=load_pil_font(22, bold=True))

    op_box = (122, 282, 640, 520)
    pil_panel(canvas, draw, op_box, fill="#FFFFFF", outline="#D6E0EA", radius=28, shadow=False)
    draw.text((154, 318), "算子分类与预处理", fill="#173A5E", font=f_block)
    op_text = wrap_mixed_text("原子算子 61 / 转换算子 45 / 复合算子 16 / 控制流 2\n几何计算次数 O(1954) -> O(1055)，约减少 46%。", 34)
    draw.multiline_text((154, 372), op_text, fill="#5B6D80", font=f_text, spacing=8)

    chain_blocks = [
        ((760, 300, 1050, 460), "#EFF6FF", "#CFE0FF", "Model Import", "TensorFlow / TFLite / Caffe / ONNX"),
        ((1120, 300, 1410, 460), "#F0F7FF", "#D3E2F1", "Frontend", "格式解析与图级预处理"),
        ((1480, 300, 1770, 460), "#F5F0FA", "#D8CDE8", "Interpreter", "图调度与 Session 管理"),
        ((1840, 300, 2110, 460), "#F0FAF3", "#C7DFCF", "Backend", "CPU / GPU / NPU 执行后端"),
    ]
    for box, fill_color, outline_color, title, detail in chain_blocks:
        pil_panel(canvas, draw, box, fill=fill_color, outline=outline_color, radius=28, shadow=False)
        draw.text((box[0] + 26, box[1] + 32), title, fill="#13263A", font=f_block)
        draw.multiline_text((box[0] + 26, box[1] + 88), wrap_mixed_text(detail, 22), fill="#5B6D80", font=f_text, spacing=8)
    pil_arrow(draw, (1050, 380), (1120, 380), "#5B6D80")
    pil_arrow(draw, (1410, 380), (1480, 380), "#5B6D80")
    pil_arrow(draw, (1770, 380), (1840, 380), "#5B6D80")

    capability_blocks = [
        ((150, 820, 590, 980), "#F3FBF7", "#C7DFCF", "动态尺寸路径", "resizeTensor + resizeSession\n支持 B×3×H×W"),
        ((660, 820, 1100, 980), "#FFFCEF", "#EFD999", "Session 复用", "bucketed shape reuse\n减少频繁重建"),
        ((1170, 820, 1610, 980), "#F8F4FF", "#D6C8F0", "半自动搜索", "对解释器/线程/precision 做 sweep"),
        ((1680, 820, 2060, 980), "#FFF3F4", "#E7C8D1", "NEON / 汇编", "仅保留有正收益的 lane"),
    ]
    for box, fill_color, outline_color, title, detail in capability_blocks:
        pil_panel(canvas, draw, box, fill=fill_color, outline=outline_color, radius=28, shadow=False)
        draw.text((box[0] + 26, box[1] + 28), title, fill="#173A5E", font=f_block)
        draw.multiline_text((box[0] + 26, box[1] + 84), wrap_mixed_text(detail, 22), fill="#5B6D80", font=f_text, spacing=8)
    pil_poly_arrow(draw, [(1620, 460), (1620, 700), (370, 700), (370, 820)], "#1B9E77", width=5)
    pil_poly_arrow(draw, [(1620, 460), (1620, 700), (880, 700), (880, 820)], "#C4A640", width=5)
    pil_poly_arrow(draw, [(1620, 460), (1620, 700), (1390, 700), (1390, 820)], "#7C63BE", width=5)
    pil_poly_arrow(draw, [(1910, 460), (1910, 700), (1870, 700), (1870, 820)], "#C65A74", width=5)

    footer = (80, 1160, 2120, 1220)
    draw.rounded_rectangle(footer, radius=22, fill="#EAF2F8", outline="#D3DFEA", width=2)
    footer_text = "读图方式：上层回答 MNN 如何执行，下层回答它为什么适合动态尺寸与运行时扫参。"
    draw.text((114, 1177), footer_text, fill="#42586E", font=f_small)
    canvas.convert("RGB").save(target)


def render_openamp_state_machine(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)
    fig, ax = plt.subplots(figsize=(11.5, 7.2), dpi=220)
    ax.set_xlim(0.02, 0.98)
    ax.set_ylim(0.06, 0.94)
    ax.axis("off")

    for name, (x, y) in OPENAMP_STATES.items():
        add_rounded_box(ax, x, y, 0.18, 0.14, OPENAMP_COLORS[name], OPENAMP_LABELS[name])

    add_arrow(ax, (0.24, 0.72), (0.33, 0.72), "JOB_REQ", curve=0.0, text_offset=(0.0, 0.04))
    add_arrow(ax, (0.51, 0.72), (0.63, 0.72), "JOB_ACK(ALLOW)", curve=0.0, text_offset=(0.0, 0.04))
    add_arrow(ax, (0.42, 0.65), (0.23, 0.65), "JOB_ACK(DENY)\nSHA/参数非法", curve=0.15, text_offset=(0.0, 0.05))
    add_arrow(ax, (0.72, 0.65), (0.72, 0.39), "SAFE_STOP / 心跳超时", curve=0.0, text_offset=(0.08, 0.0))
    add_arrow(ax, (0.66, 0.72), (0.23, 0.74), "JOB_DONE(success)", curve=-0.16, text_offset=(0.0, 0.08))
    add_arrow(ax, (0.63, 0.30), (0.51, 0.30), "STATUS_REQ\n仅查询", curve=0.0, text_offset=(0.0, 0.05))
    add_arrow(ax, (0.42, 0.37), (0.15, 0.65), "故障记录落盘后\n回到 READY", curve=-0.25, text_offset=(-0.03, 0.02))

    ax.text(
        0.03,
        0.93,
        "OpenAMP 控制状态机与消息转移",
        fontsize=22,
        fontproperties=FONT_PROP,
        weight="bold",
        color="#173A5E",
        va="top",
    )
    ax.text(
        0.03,
        0.87,
        "RTOS 从核用五状态有限状态机约束 JOB_REQ、HEARTBEAT、SAFE_STOP 与 JOB_DONE 的合法转移。",
        fontsize=13,
        fontproperties=FONT_PROP,
        color="#5B6D80",
        va="top",
    )
    ax.text(
        0.03,
        0.11,
        "说明：SAFE_STOP 与 FAULT 在论文中都被设计成“可观测安全态”，Linux 侧可通过 STATUS_REQ 查询最后一次 fault_code 与 heartbeat 状态。",
        fontsize=11.5,
        fontproperties=FONT_PROP,
        color="#5B6D80",
        va="bottom",
    )
    fig.tight_layout(pad=1.1)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def render_control_message_sequence(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2360, 1320), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(52, bold=True)
    f_sub = load_pil_font(28)
    f_lane = load_pil_font(28, bold=True)
    f_text = load_pil_font(24)
    f_small = load_pil_font(22)
    header_bottom = pil_header(
        draw,
        x=86,
        y=54,
        title="控制协议与消息时序",
        subtitle="用 4 条泳道把“谁发起、经过哪条轻载通道、谁裁决、最后观测到什么”拆开，避免把多组消息和条件说明压在同一根线上。",
        title_font=f_title,
        subtitle_font=f_sub,
    )

    lane_x = [360, 930, 1500, 2070]
    lane_titles = ["Linux 主核", "OpenAMP 控制通道", "RTOS 从核", "可观测结果"]
    lane_colors = ["#335C81", "#6A4C93", "#1B9E77", "#D95F02"]
    top_y = header_bottom + 106
    bottom_y = 1118
    main_box = (120, top_y - 72, 2240, 1136)
    pil_panel(canvas, draw, main_box, fill="#FFFFFF", outline="#D8E2EC", radius=34)
    for x, title, color in zip(lane_x, lane_titles, lane_colors):
        badge = pil_badge(draw, x - 118, top_y - 54, title, color, font=load_pil_font(22, bold=True), pad_x=18, pad_y=8)
        draw.rounded_rectangle((badge[0] - 12, badge[1] - 10, badge[2] + 12, badge[3] + 10), radius=26, outline="#E3EBF3", width=2)
        pil_dashed_line(draw, (x, top_y), (x, bottom_y), "#B8C7D6", dash=18, gap=12, width=3)

    section_specs = [
        ("状态查询", "#335C81", 360, ("STATUS_REQ", "RPMsg 查询", "STATUS_RESP", "READY / last_fault_code")),
        ("作业准入", "#6A4C93", 520, ("JOB_REQ", "artifact_hash +\nparam_digest", "JOB_ACK", "ALLOW / DENY")),
        ("运行监护", "#1B9E77", 680, ("HEARTBEAT", "周期上报", "RUNNING", "继续执行 / 监护")),
        ("结束收敛", "#D95F02", 840, ("SAFE_STOP / JOB_DONE", "SAFE_STOP 或\ntimeout", "SAFE_STOP / FAULT", "可观测收敛态")),
    ]
    section_x = 146
    for label, color, y, row in section_specs:
        pil_badge(draw, section_x, y - 36, label, color, font=load_pil_font(20, bold=True), pad_x=14, pad_y=6)
        box_width = 270
        for idx, text in enumerate(row):
            x_center = lane_x[idx]
            box = (x_center - box_width // 2, y - 50, x_center + box_width // 2, y + 50)
            fill_color = "#FFFFFF" if idx < 3 else "#F8FBFD"
            outline_color = color if idx == 0 else "#D6E0EA"
            pil_panel(canvas, draw, box, fill=fill_color, outline=outline_color, radius=24, shadow=False)
            wrapped = wrap_mixed_text(text, 18)
            tw, th = pil_text_size(draw, wrapped, f_text, spacing=8)
            draw.multiline_text((x_center - tw / 2, y - th / 2), wrapped, fill="#173A5E" if idx < 3 else color, font=f_text, spacing=8)
        for idx in range(3):
            pil_arrow(draw, (lane_x[idx] + box_width // 2, y), (lane_x[idx + 1] - box_width // 2, y), color, width=5)

    note_left = (168, 982, 1128, 1066)
    note_right = (1234, 982, 2194, 1066)
    draw.rounded_rectangle(note_left, radius=22, fill="#EEF8F4", outline="#CFE5DA", width=2)
    draw.rounded_rectangle(note_right, radius=22, fill="#FFF4ED", outline="#F0D6C3", width=2)
    draw.text((178, 1002), "ALLOW 后才进入推理执行与 heartbeat 监护。", fill="#1B9E77", font=f_small)
    draw.text((1266, 1002), "若 heartbeat 丢失，则控制面转入 SAFE_STOP / FAULT 并保留最后一次 fault_code。", fill="#D95F02", font=f_small)

    footer = (120, 1170, 2240, 1236)
    draw.rounded_rectangle(footer, radius=22, fill="#EAF2F8", outline="#D3DFEA", width=2)
    draw.text((154, 1188), "说明：大体量图像数据不经过该通道；控制面只传作业状态、校验摘要与故障码，因此可保持轻载和可审计。", fill="#42586E", font=f_small)
    canvas.convert("RGB").save(target)


def render_project_timeline(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)
    fig, ax = plt.subplots(figsize=(12.8, 4.6), dpi=220)
    ax.set_xlim(-0.3, len(PROJECT_TIMELINE) - 0.7)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.plot([0, len(PROJECT_TIMELINE) - 1], [0.5, 0.5], color="#9FB3C8", linewidth=3.0, zorder=1)
    colors = ["#335C81", "#6A4C93", "#1B9E77", "#D95F02", "#1F7A8C", "#C1121F"]

    for idx, ((date_label, title, desc), color) in enumerate(zip(PROJECT_TIMELINE, colors)):
        y = 0.68 if idx % 2 == 0 else 0.32
        ax.plot([idx, idx], [0.5, y], color="#C6D3E0", linewidth=2.0, zorder=1)
        ax.scatter([idx], [0.5], s=170, color=color, zorder=3, edgecolors="#FFFFFF", linewidths=2.2)
        box = patches.FancyBboxPatch(
            (idx - 0.5, y - 0.12),
            1.0,
            0.22,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            linewidth=1.2,
            edgecolor="#D6E0EA",
            facecolor="#FFFFFF",
            zorder=2,
        )
        ax.add_patch(box)
        ax.text(idx - 0.42, y + 0.05, date_label, fontproperties=FONT_PROP, fontsize=10.5, color=color, weight="bold", zorder=4)
        ax.text(idx - 0.42, y + 0.0, title, fontproperties=FONT_PROP, fontsize=12.2, color="#173A5E", weight="bold", zorder=4)
        ax.text(idx - 0.42, y - 0.055, desc, fontproperties=FONT_PROP, fontsize=10.1, color="#5B6D80", zorder=4)

    fig.suptitle("项目开发时间线与关键收口节点", fontproperties=FONT_PROP, fontsize=20, color="#173A5E", y=0.98)
    fig.text(
        0.08,
        0.9,
        "从首次飞腾端推理成功到 OpenAMP 控制面闭环、big.LITTLE 提速与演示集成，项目在 2026 年 3 月完成了由点到面的系统收口。",
        ha="left",
        va="center",
        fontsize=11.8,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )
    fig.subplots_adjust(top=0.82, bottom=0.1, left=0.04, right=0.98)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def render_mnn_benchmark(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)
    labels = list(MNN_BENCHMARK.keys())
    values = list(MNN_BENCHMARK.values())
    palette = ["#7A8794", "#1B9E77", "#D95F02", "#6A4C93"]

    fig, ax = plt.subplots(figsize=(10.8, 6.2), dpi=220)
    bars = ax.bar(labels, values, color=palette, width=0.62)
    fig.suptitle("MNN 动态尺寸路线关键配置对比", fontproperties=FONT_PROP, fontsize=21, color="#173A5E", y=0.98)
    fig.text(
        0.08,
        0.915,
        "300 张不同尺寸图像，单位为总耗时（秒）。当前正式最优仍为 2 interpreters + 1 thread/session + FP32(normal)。",
        ha="left",
        va="center",
        fontsize=12.2,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )
    ax.set_ylabel("300 张总耗时（s）", fontproperties=FONT_PROP, fontsize=13)
    ax.set_ylim(0, 165)
    for tick in ax.get_xticklabels():
        tick.set_fontproperties(FONT_PROP)
        tick.set_fontsize(12)
    for tick in ax.get_yticklabels():
        tick.set_fontproperties(FONT_PROP)
        tick.set_fontsize(11)

    best_value = min(values)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            value + 2.6,
            f"{value:.1f}s",
            ha="center",
            va="bottom",
            fontsize=12,
            fontproperties=FONT_PROP,
            color="#13263A",
            weight="bold",
        )
        if value == best_value:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                value / 2.0,
                "正式最优",
                ha="center",
                va="center",
                fontsize=12.5,
                fontproperties=FONT_PROP,
                color="#FFFFFF",
                weight="bold",
            )

    baseline = MNN_BENCHMARK["基线\n1I/1T/FP32"]
    best = MNN_BENCHMARK["正式最优\n2I/1T/FP32"]
    uplift = baseline / best
    ax.text(
        0.98,
        0.94,
        f"基线→正式最优：{uplift:.2f}x",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=13,
        fontproperties=FONT_PROP,
        color="#1B9E77",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#F0F8F3", edgecolor="#1B9E77", linewidth=1.2),
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.subplots_adjust(top=0.88, bottom=0.16, left=0.08, right=0.98)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def render_performance_ladder(target: Path) -> None:
    ensure_dir(target)
    from PIL import ImageDraw, ImageFont

    canvas_w, canvas_h = 2300, 1180
    bg = Image.new("RGB", (canvas_w, canvas_h), "#F5F8FC")
    draw = ImageDraw.Draw(bg)

    def load_font_local(size: int, bold: bool = False):
        candidates = [
            Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for p in candidates:
            if p.is_file():
                return ImageFont.truetype(str(p), size)
        return ImageFont.load_default()

    f_title = load_font_local(60, bold=True)
    f_sub = load_font_local(26)
    f_card_title = load_font_local(32, bold=True)
    f_value = load_font_local(58, bold=True)
    f_unit = load_font_local(24)
    f_note = load_font_local(24)
    f_badge = load_font_local(24, bold=True)

    for y in range(200):
        alpha = int(255 * (1 - y / 200) * 0.16)
        band = Image.new("RGBA", (canvas_w, 1), (24, 65, 118, alpha))
        bg.paste(band, (0, y), band)

    draw.text((90, 48), "系统关键性能跃迁", fill="#173A5E", font=f_title)
    draw.text(
        (90, 128),
        "主线结果并不是单点 benchmark，而是从旧端到端链路到 TVM 主线再到 big.LITTLE 流水线的连续收口。MNN 动态尺寸路线作为旁路负责混合尺寸部署。",
        fill="#5B6D80",
        font=f_sub,
    )

    card_w, card_h = 560, 420
    top_y = 260
    xs = [90, 735, 1380]
    arrow_texts = ["8.0x 更快", "1.71x 更快"]

    for idx, item in enumerate(PERFORMANCE_LADDER):
        x = xs[idx]
        shadow = Image.new("RGBA", (card_w + 28, card_h + 28), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((14, 14, card_w + 14, card_h + 14), radius=30, fill=(12, 23, 38, 58))
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        bg.paste(shadow, (x - 8, top_y - 4), shadow)

        card = Image.new("RGB", (card_w, card_h), "#FFFFFF")
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=30, fill="#FFFFFF", outline="#D4DEEA", width=2)
        cd.rounded_rectangle((28, 24, 180, 72), radius=24, fill=item["color"])
        cd.text((52, 36), "主结果", fill="#FFFFFF", font=f_badge)
        cd.text((28, 110), item["title"], fill="#173A5E", font=f_card_title)
        cd.text((28, 196), item["value"], fill=item["color"], font=f_value)
        cd.text((300, 220), item["unit"], fill="#5B6D80", font=f_unit)
        cd.rounded_rectangle((28, 288, card_w - 28, 368), radius=22, fill="#F3F8FC", outline="#E2EAF2", width=1)
        cd.text((48, 315), item["note"], fill="#5B6D80", font=f_note)
        bg.paste(card, (x, top_y))

        if idx < len(PERFORMANCE_LADDER) - 1:
            arrow_x0 = x + card_w + 24
            arrow_x1 = xs[idx + 1] - 28
            arrow_y = top_y + 195
            draw.line((arrow_x0, arrow_y, arrow_x1, arrow_y), fill="#6A7F94", width=7)
            draw.polygon([(arrow_x1, arrow_y), (arrow_x1 - 26, arrow_y - 14), (arrow_x1 - 26, arrow_y + 14)], fill="#6A7F94")
            text_w = draw.textbbox((0, 0), arrow_texts[idx], font=f_badge)[2]
            draw.rounded_rectangle((arrow_x0 + 24, arrow_y - 54, arrow_x0 + 24 + text_w + 34, arrow_y - 14), radius=20, fill="#EAF2F8")
            draw.text((arrow_x0 + 41, arrow_y - 47), arrow_texts[idx], fill="#42586E", font=f_badge)

    # MNN side panel
    side_x, side_y, side_w, side_h = 1720, 720, 490, 320
    shadow = Image.new("RGBA", (side_w + 28, side_h + 28), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((14, 14, side_w + 14, side_h + 14), radius=28, fill=(12, 23, 38, 52))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    bg.paste(shadow, (side_x - 8, side_y - 4), shadow)
    card = Image.new("RGB", (side_w, side_h), "#FFFFFF")
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, side_w - 1, side_h - 1), radius=28, fill="#FFFFFF", outline="#D4DEEA", width=2)
    cd.rounded_rectangle((24, 22, 196, 68), radius=22, fill="#335C81")
    cd.text((48, 34), "动态尺寸旁路", fill="#FFFFFF", font=f_badge)
    cd.text((24, 96), "MNN dynamic", fill="#173A5E", font=f_card_title)
    cd.text((24, 164), "327.3", fill="#335C81", font=f_value)
    cd.text((250, 188), "ms/image", fill="#5B6D80", font=f_unit)
    cd.text((24, 248), "混合尺寸 / 无需预缩放 / 300 张 98.2 s", fill="#5B6D80", font=f_note)
    bg.paste(card, (side_x, side_y))

    footer_y = 1068
    draw.rounded_rectangle((90, footer_y - 8, canvas_w - 90, canvas_h - 50), radius=24, fill="#EAF2F8", outline="#D3DFEA", width=2)
    draw.text((118, footer_y + 8), "读图方式：固定形状主线看左到右三张卡；混合尺寸部署看右下角 MNN 旁路。", fill="#42586E", font=f_sub)
    bg.save(target)


def render_tvm_result_summary(target: Path) -> None:
    ensure_dir(target)
    from PIL import ImageDraw, ImageFont

    canvas_w, canvas_h = 2260, 1240
    bg = Image.new("RGB", (canvas_w, canvas_h), "#F5F8FC")
    draw = ImageDraw.Draw(bg)

    def load_font_local(size: int, bold: bool = False):
        candidates = [
            Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for p in candidates:
            if p.is_file():
                return ImageFont.truetype(str(p), size)
        return ImageFont.load_default()

    f_title = load_font_local(58, bold=True)
    f_sub = load_font_local(26)
    f_label = load_font_local(26, bold=True)
    f_value = load_font_local(46, bold=True)
    f_unit = load_font_local(22)
    f_note = load_font_local(22)
    f_badge = load_font_local(24, bold=True)

    for y in range(190):
        alpha = int(255 * (1 - y / 190) * 0.15)
        band = Image.new("RGBA", (canvas_w, 1), (24, 65, 118, alpha))
        bg.paste(band, (0, y), band)

    draw.text((86, 44), "TVM 主线结果总览", fill="#173A5E", font=f_title)
    draw.text(
        (86, 120),
        "该页汇总 4-core Linux performance mode 下最应被引用的 TVM 主线结论：时间、吞吐、质量、完整性与资源占用。",
        fill="#5B6D80",
        font=f_sub,
    )

    card_w, card_h = 650, 240
    x_positions = [86, 804, 1522]
    y_positions = [250, 540]
    accents = ["#2D6A4F", "#1B9E77", "#335C81", "#D95F02", "#6A4C93", "#1F7A8C"]

    for idx, ((label, value, unit, note), accent) in enumerate(zip(TVM_RESULT_SUMMARY, accents)):
        row, col = divmod(idx, 3)
        x = x_positions[col]
        y = y_positions[row]
        shadow = Image.new("RGBA", (card_w + 28, card_h + 28), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((14, 14, card_w + 14, card_h + 14), radius=28, fill=(12, 23, 38, 54))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        bg.paste(shadow, (x - 8, y - 4), shadow)

        card = Image.new("RGB", (card_w, card_h), "#FFFFFF")
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=28, fill="#FFFFFF", outline="#D4DEEA", width=2)
        cd.rounded_rectangle((24, 22, 170, 66), radius=22, fill=accent)
        cd.text((48, 34), "TVM 主线", fill="#FFFFFF", font=f_badge)
        cd.text((24, 92), label, fill="#173A5E", font=f_label)
        cd.text((24, 146), value, fill=accent, font=f_value)
        if unit:
            cd.text((360, 164), unit, fill="#5B6D80", font=f_unit)
        cd.text((24, 202), note, fill="#5B6D80", font=f_note)
        bg.paste(card, (x, y))

    footer_y = 960
    draw.rounded_rectangle((86, footer_y, canvas_w - 86, 1145), radius=26, fill="#EAF2F8", outline="#D3DFEA", width=2)
    draw.text((116, footer_y + 26), "引用边界", fill="#173A5E", font=f_label)
    draw.text(
        (116, footer_y + 84),
        "本图只汇总 4-core Linux performance mode 的 TVM 主线结论。OpenAMP 三核演示模式的公平比较、控制面闭环和 FIT 结果应继续引用第 3 章与第 4.1.3 节对应证据，不与本图混写。",
        fill="#42586E",
        font=f_sub,
    )
    bg.save(target)


def render_evidence_bundle_map(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2300, 1360), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(56, bold=True)
    f_sub = load_pil_font(24)
    f_center = load_pil_font(34, bold=True)
    f_card_title = load_pil_font(28, bold=True)
    f_card_body = load_pil_font(20)
    f_badge = load_pil_font(23, bold=True)
    draw.text((86, 46), "答辩证据包结构图", fill="#173A5E", font=f_title)
    draw.text((86, 118), "将面向评审的材料按“总判定、live 状态、安全验证、性能质量、演示与话术”五类组织，并通过中心枢纽统一进入。", fill="#5B6D80", font=f_sub)

    center_box = (930, 480, 1370, 820)
    pil_panel(canvas, draw, center_box, fill="#13263F", outline="#1F3A5A", radius=42)
    draw.text((1038, 560), "Evidence Bundle", fill="#FFFFFF", font=f_center)
    draw.text((1008, 628), "Judge-facing 入口", fill="#86C5FF", font=f_badge)
    draw.multiline_text((1016, 680), "文档优先 / 证据驱动 /\n操作员在环", fill="#DCE7F3", font=f_sub, spacing=10)

    left_cards = [(130, 250), (130, 620), (130, 990)]
    right_cards = [(1610, 360), (1610, 850)]
    positions = left_cards + right_cards
    for card, (x, y) in zip(EVIDENCE_BUNDLE_CARDS, positions):
        box = (x, y, x + 560, y + 240)
        pil_panel(canvas, draw, box, fill="#FFFFFF", outline="#D4DEEA", radius=28)
        pil_badge(draw, x + 26, y + 22, "证据入口", card["color"], font=f_badge, pad_x=16, pad_y=8)
        draw.text((x + 26, y + 98), card["title"], fill="#173A5E", font=f_card_title)
        cursor_y = y + 144
        for line in card["lines"]:
            wrapped = wrap_mixed_text(line, 26)
            draw.multiline_text((x + 26, cursor_y), wrapped, fill="#5B6D80", font=f_card_body, spacing=5)
            _, text_h = pil_text_size(draw, wrapped, f_card_body, spacing=5)
            cursor_y += text_h + 8

        if x < center_box[0]:
            anchor_x = box[2]
            trunk_x = 790
            draw.line((anchor_x, y + 110, trunk_x, y + 110), fill="#B7C7D8", width=5)
            draw.line((trunk_x, y + 110, trunk_x, 650), fill="#B7C7D8", width=5)
            pil_arrow(draw, (trunk_x, 650), (center_box[0], 650), "#B7C7D8", width=5)
        else:
            anchor_x = box[0]
            trunk_x = 1510
            draw.line((anchor_x, y + 110, trunk_x, y + 110), fill="#B7C7D8", width=5)
            draw.line((trunk_x, y + 110, trunk_x, 650), fill="#B7C7D8", width=5)
            pil_arrow(draw, (trunk_x, 650), (center_box[2], 650), "#B7C7D8", width=5)

    footer = (86, 1240, 2214, 1304)
    draw.rounded_rectangle(footer, radius=24, fill="#EAF2F8", outline="#D3DFEA", width=2)
    draw.text((116, 1258), "用途：评委追问时先选证据卡，再进入对应文档；连接线只表达“进入中心枢纽”，不再穿过正文。", fill="#42586E", font=f_sub)
    canvas.convert("RGB").save(target)


def render_framework_positioning(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)

    labels = [item["label"] for item in FRAMEWORK_POSITIONING][::-1]
    values = [item["value"] for item in FRAMEWORK_POSITIONING][::-1]
    colors = [item["color"] for item in FRAMEWORK_POSITIONING][::-1]
    tags = [item["tag"] for item in FRAMEWORK_POSITIONING][::-1]

    fig, ax = plt.subplots(figsize=(12.2, 6.6), dpi=220)
    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=colors, height=0.62)

    fig.suptitle("双引擎部署定位与端侧性能关系", fontproperties=FONT_PROP, fontsize=21, color="#173A5E", y=0.985)
    fig.text(
        0.08,
        0.92,
        "TVM 负责固定形状极致性能，MNN 负责动态尺寸灵活部署；OpenAMP 演示模式的控制/安全结论不与本图 latency 混写。",
        ha="left",
        va="center",
        fontsize=12.2,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )

    ax.set_xlabel("端到端时间（ms/image，越低越好）", fontproperties=FONT_PROP, fontsize=12.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 560)
    for tick in ax.get_xticklabels():
        tick.set_fontproperties(FONT_PROP)
        tick.set_fontsize(11)
    for tick in ax.get_yticklabels():
        tick.set_fontproperties(FONT_PROP)
        tick.set_fontsize(13)

    for bar, value, tag in zip(bars, values, tags):
        y_mid = bar.get_y() + bar.get_height() / 2.0
        ax.text(
            max(value - 8, 18),
            y_mid,
            f"{value:.1f} ms",
            ha="right",
            va="center",
            fontsize=12.5,
            fontproperties=FONT_PROP,
            color="#FFFFFF",
            weight="bold",
        )
        tag_x = value + 10
        tag_ha = "left"
        if tag_x > 545:
            tag_x = 545
            tag_ha = "right"
        ax.text(
            tag_x,
            y_mid,
            tag,
            ha=tag_ha,
            va="center",
            fontsize=10.8,
            fontproperties=FONT_PROP,
            color="#FFFFFF",
            bbox=dict(boxstyle="round,pad=0.28", facecolor=bar.get_facecolor(), edgecolor="none"),
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.text(
        0.08,
        0.08,
        "注：MNN 值来自 300 张混合尺寸真机 benchmark；TVM 值来自 256×256 固定形状性能主口径。",
        ha="left",
        va="center",
        fontsize=10.8,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )
    fig.text(
        0.97,
        0.08,
        "结论：固定形状优先 TVM；动态尺寸优先 MNN。",
        ha="right",
        va="center",
        fontsize=12.3,
        fontproperties=FONT_PROP,
        color="#1B9E77",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#F0F8F3", edgecolor="#1B9E77", linewidth=1.1),
    )
    fig.subplots_adjust(top=0.84, bottom=0.2, left=0.17, right=0.97)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def render_perf_quality_tradeoff(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)

    fig = plt.figure(figsize=(12.6, 6.4), dpi=220)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 0.95])
    ax = fig.add_subplot(gs[0, 0])
    panel = fig.add_subplot(gs[0, 1])
    panel.axis("off")

    x_vals = [item["latency"] for item in PERF_QUALITY_POINTS]
    y_vals = [item["psnr"] for item in PERF_QUALITY_POINTS]
    ax.plot(x_vals, y_vals, linestyle="--", linewidth=2.0, color="#A9B8C8", zorder=1)

    for item in PERF_QUALITY_POINTS:
        ax.scatter(
            item["latency"],
            item["psnr"],
            s=260,
            color=item["color"],
            edgecolor="white",
            linewidth=1.8,
            zorder=3,
        )
        offset = (10, 12)
        if item["label"] == "初始版本":
            offset = (-70, -5)
        elif item["label"] == "TVM pipeline":
            offset = (10, -28)
        ax.annotate(
            f"{item['label']}\n{item['latency']:.1f} ms / {item['psnr']:.2f} dB",
            xy=(item["latency"], item["psnr"]),
            xytext=offset,
            textcoords="offset points",
            ha="left" if offset[0] >= 0 else "right",
            va="bottom",
            fontsize=10.8,
            fontproperties=FONT_PROP,
            color="#173A5E",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor="#D4DFEA", linewidth=1.0, alpha=0.95),
        )

    ax.annotate(
        "",
        xy=(230.3, 35.66),
        xytext=(1850.0, 34.42),
        arrowprops=dict(arrowstyle="-|>", lw=2.0, color="#2D6A4F"),
    )
    ax.annotate(
        "",
        xy=(134.6, 35.66),
        xytext=(230.3, 35.66),
        arrowprops=dict(arrowstyle="-|>", lw=2.0, color="#1B9E77"),
    )

    ax.text(
        0.03,
        0.95,
        "更快且未牺牲质量",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=12.2,
        fontproperties=FONT_PROP,
        color="#1B9E77",
        bbox=dict(boxstyle="round,pad=0.32", facecolor="#EEF8F2", edgecolor="#1B9E77", linewidth=1.0),
    )
    ax.text(
        0.03,
        0.07,
        "左图只比较同口径 TVM 主线\nMNN 不与该 PSNR 散点直接混写",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10.0,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )

    ax.set_xscale("log")
    ax.set_xlim(110, 2400)
    ax.set_ylim(34.1, 36.1)
    ax.set_xticks([125, 250, 500, 1000, 2000])
    ax.set_xticklabels(["125", "250", "500", "1000", "2000"])
    ax.set_xlabel("端到端时间（ms/image，对数坐标，越低越好）", fontproperties=FONT_PROP, fontsize=12.5)
    ax.set_ylabel("PSNR (dB，越高越好)", fontproperties=FONT_PROP, fontsize=12.5)
    ax.grid(alpha=0.18, linestyle="--")
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontproperties(FONT_PROP)
        tick.set_fontsize(10.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.suptitle("性能-质量-部署灵活性权衡图", fontproperties=FONT_PROP, fontsize=21, color="#173A5E", y=0.985)
    fig.text(
        0.08,
        0.92,
        "TVM 主线证明“更快不等于更差”；MNN 作为混合尺寸部署旁路保留，不与左图的同尺寸质量口径混写。",
        ha="left",
        va="center",
        fontsize=12.0,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )

    def add_card(x: float, y: float, w: float, h: float, title: str, color: str, lines: list[str]) -> None:
        rect = patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.018,rounding_size=0.03",
            facecolor="white",
            edgecolor="#D4DFEA",
            linewidth=1.1,
        )
        panel.add_patch(rect)
        tag = patches.FancyBboxPatch(
            (x + 0.03, y + h - 0.12),
            0.24,
            0.08,
            boxstyle="round,pad=0.01,rounding_size=0.04",
            facecolor=color,
            edgecolor="none",
        )
        panel.add_patch(tag)
        panel.text(x + 0.15, y + h - 0.08, "部署卡片", ha="center", va="center", fontsize=10.5, fontproperties=FONT_PROP, color="white", weight="bold")
        panel.text(x + 0.03, y + h - 0.14, title, ha="left", va="top", fontsize=14.2, fontproperties=FONT_PROP, color="#173A5E", weight="bold")
        for idx, line in enumerate(lines):
            panel.text(
                x + 0.03,
                y + h - 0.21 - idx * 0.07,
                line,
                ha="left",
                va="top",
                fontsize=10.8,
                fontproperties=FONT_PROP,
                color="#5B6D80",
            )

    add_card(
        0.04,
        0.56,
        0.9,
        0.29,
        "固定形状 TVM 主线",
        "#2D6A4F",
        [
            "230.3 ms/image 端到端 / 134.6 ms/image big.LITTLE",
            "PSNR 35.66 / SSIM 0.9728 / 性能主口径",
        ],
    )
    add_card(
        0.04,
        0.22,
        0.9,
        0.29,
        "动态尺寸 MNN 旁路",
        "#335C81",
        [
            "327.3 ms/image / 300 张混合尺寸",
            "无需预缩放 / 保留部署灵活性",
        ],
    )
    panel.text(
        0.04,
        0.10,
        "结论：固定形状优先追 TVM 主线；动态尺寸场景保留 MNN。",
        ha="left",
        va="center",
        fontsize=11.6,
        fontproperties=FONT_PROP,
        color="#173A5E",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#F7FAFD", edgecolor="#C8D6E5", linewidth=1.0),
    )
    panel.text(
        0.04,
        0.04,
        "注：MNN 保留部署灵活性，不与左图的同尺寸 PSNR 散点直接混写。",
        ha="left",
        va="center",
        fontsize=9.8,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )

    fig.subplots_adjust(top=0.84, bottom=0.14, left=0.08, right=0.97, wspace=0.12)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def render_semantic_vs_traditional(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2200, 1280), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(56, bold=True)
    f_sub = load_pil_font(28)
    f_block = load_pil_font(34, bold=True)
    f_text = load_pil_font(24)
    f_small = load_pil_font(22)
    header_bottom = pil_header(
        draw,
        x=86,
        y=50,
        title="传统压缩与语义通信的弱网对比",
        subtitle="这张图同时回答“传什么”和“在极端弱网下会怎样”。主对照区只保留两栏结论；大小对照被独立下沉到底部，不再与正文挤在同一块。",
        title_font=f_title,
        subtitle_font=f_sub,
    )

    left_box = (120, header_bottom + 54, 980, 760)
    right_box = (1220, header_bottom + 54, 2080, 760)
    pil_panel(canvas, draw, left_box, fill="#FFF9F2", outline="#F2C38B", radius=34)
    pil_panel(canvas, draw, right_box, fill="#F3FBF7", outline="#9BCBB3", radius=34)
    pil_badge(draw, 180, left_box[1] + 24, "传统压缩", "#D95F02", font=load_pil_font(24, bold=True))
    pil_badge(draw, 1280, right_box[1] + 24, "语义通信", "#1B9E77", font=load_pil_font(24, bold=True))
    draw.text((182, left_box[1] + 106), "传输对象：像素级信息", fill="#173A5E", font=f_block)
    draw.text((1282, right_box[1] + 106), "传输对象：latent 语义特征", fill="#173A5E", font=f_block)

    left_lines = [
        "JPEG / H.265 仍围绕像素保真展开",
        "链路变差时需要更强的冗余与纠错开销",
        "极低 SNR 下容易出现明显失真甚至不可用",
    ]
    right_lines = [
        "Encoder 先提取紧凑语义表征再入信道",
        "本系统 32×32×32 latent 约 128 KB (FP32)",
        "文献[6]：SNR=1 dB 时 GAN-based JSCC 仍可达 29 dB+",
    ]
    for idx, line in enumerate(left_lines):
        draw.text((196, left_box[1] + 206 + idx * 106), f"- {line}", fill="#5B6D80", font=f_text)
    for idx, line in enumerate(right_lines):
        draw.text((1296, right_box[1] + 206 + idx * 106), f"- {line}", fill="#5B6D80", font=f_text)

    pil_badge(draw, 1020, 420, "弱网巡检场景", "#879AAF", font=load_pil_font(20, bold=True), pad_x=16, pad_y=6)
    pil_arrow(draw, (1000, 520), (1200, 520), "#A9B8C8", width=10)
    draw.text((1030, 568), "更关注“能否传回有效语义”", fill="#5B6D80", font=f_small)

    compare_box = (120, 860, 2080, 1130)
    pil_panel(canvas, draw, compare_box, fill="#FFFFFF", outline="#D4DEEA", radius=30)
    draw.text((164, 900), "本系统输入与 latent 大小对照", fill="#173A5E", font=f_block)
    draw.text((164, 982), "256×256 RGB 原图", fill="#5B6D80", font=f_text)
    draw.text((164, 1052), "Encoder latent", fill="#5B6D80", font=f_text)
    raw_bar = (520, 974, 1570, 1024)
    latent_bar = (520, 1044, 1220, 1094)
    draw.rounded_rectangle(raw_bar, radius=24, fill="#DADFE6")
    draw.rounded_rectangle(latent_bar, radius=24, fill="#1B9E77")
    draw.text((1500, 982), "≈192 KB", fill="#173A5E", font=load_pil_font(24, bold=True))
    draw.text((1028, 1052), "≈128 KB", fill="#FFFFFF", font=load_pil_font(24, bold=True))
    footer_text = "注：大小对照来自本系统 256×256 RGB 输入与 32×32×32 latent（FP32）；弱网鲁棒性结论引自文献[6]。"
    draw.text((164, 1110), footer_text, fill="#5B6D80", font=f_small)
    canvas.convert("RGB").save(target)


def render_system_closure_overview(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2200, 1320), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    f_title = load_pil_font(56, bold=True)
    f_sub = load_pil_font(28)
    f_section = load_pil_font(32, bold=True)
    f_text = load_pil_font(24)
    f_small = load_pil_font(22)
    header_bottom = pil_header(
        draw,
        x=86,
        y=48,
        title="弱网安全语义回传系统闭环总览图",
        subtitle="这张总览图改成三层：上层讲输入链路，中层拆数据面与控制面，下层落到性能结果与答辩入口。连接只表达关系，不再穿正文。",
        title_font=f_title,
        subtitle_font=f_sub,
    )

    top_box = (120, header_bottom + 42, 2080, 330)
    mid_left = (120, 390, 1040, 760)
    mid_right = (1160, 390, 2080, 760)
    bottom_left = (120, 840, 1040, 1140)
    bottom_right = (1160, 840, 2080, 1140)
    for box in (top_box, mid_left, mid_right, bottom_left, bottom_right):
        pil_panel(canvas, draw, box, fill="#FFFFFF", outline="#D4DEEA", radius=32)

    pil_badge(draw, 156, top_box[1] + 22, "输入链路", "#335C81", font=load_pil_font(22, bold=True))
    draw.text((168, top_box[1] + 92), "Host 图像输入 -> Encoder -> latent -> 飞腾 Linux 主核", fill="#173A5E", font=f_section)
    draw.text((168, top_box[1] + 156), "这条链路回答“传得回”：先压成紧凑语义特征，再在端侧完成重建。", fill="#5B6D80", font=f_text)
    pil_arrow(draw, (680, top_box[3]), (680, mid_left[1]), "#335C81", width=5)
    pil_arrow(draw, (1520, top_box[3]), (1520, mid_right[1]), "#335C81", width=5)

    pil_badge(draw, 156, mid_left[1] + 22, "数据面", "#1B9E77", font=load_pil_font(22, bold=True))
    draw.text((168, mid_left[1] + 92), "TVM 固定形状 / MNN 动态尺寸双引擎", fill="#173A5E", font=f_section)
    draw.multiline_text((168, mid_left[1] + 158), "300 / 300 真机重建与 PNG 落盘\n固定形状看 TVM 主线，混合尺寸看 MNN 旁路", fill="#5B6D80", font=f_text, spacing=10)

    pil_badge(draw, 1196, mid_right[1] + 22, "控制面", "#D95F02", font=load_pil_font(22, bold=True))
    draw.text((1208, mid_right[1] + 92), "RTOS 从核 + OpenAMP 五类消息", fill="#173A5E", font=f_section)
    draw.multiline_text((1208, mid_right[1] + 158), "READY / CHECKING / RUNNING / SAFE_STOP / FAULT\n3 项 FIT 真机通过，SAFE_STOP 可观测收敛", fill="#5B6D80", font=f_text, spacing=10)

    pil_arrow(draw, (580, mid_left[3]), (580, bottom_left[1]), "#1B9E77", width=5)
    pil_arrow(draw, (1620, mid_right[3]), (1620, bottom_right[1]), "#D95F02", width=5)

    pil_badge(draw, 156, bottom_left[1] + 22, "性能结果", "#2D6A4F", font=load_pil_font(22, bold=True))
    draw.text((168, bottom_left[1] + 92), "TVM direct 230.3 ms/image", fill="#173A5E", font=f_section)
    draw.multiline_text((168, bottom_left[1] + 156), "big.LITTLE 134.6 ms/image / +56.1%\nMNN dynamic 327.3 ms/image", fill="#5B6D80", font=f_text, spacing=10)

    pil_badge(draw, 1196, bottom_right[1] + 22, "答辩入口", "#1F7A8C", font=load_pil_font(22, bold=True))
    draw.text((1208, bottom_right[1] + 92), "dashboard + evidence bundle + compare drawer", fill="#173A5E", font=load_pil_font(29, bold=True))
    draw.multiline_text((1208, bottom_right[1] + 156), "面向评审的五类材料入口\n操作员在环，不靠现场翻日志", fill="#5B6D80", font=f_text, spacing=10)

    footer = (86, 1210, 2110, 1272)
    draw.rounded_rectangle(footer, radius=22, fill="#13263F", outline="#1F3A5A", width=2)
    draw.text((118, 1228), "结论：弱网语义回传不是单点 benchmark，而是一套数据面、控制面、证据入口都闭环的系统。", fill="#FFFFFF", font=f_small)
    canvas.convert("RGB").save(target)


def render_cover_summary(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)

    fig, ax = plt.subplots(figsize=(13.2, 7.2), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    bg = patches.FancyBboxPatch(
        (0.02, 0.04),
        0.96,
        0.90,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        facecolor="#F7FAFD",
        edgecolor="#D8E6F3",
        linewidth=1.0,
    )
    ax.add_patch(bg)

    fig.suptitle("飞腾多核异构安全语义回传系统摘要图", fontproperties=FONT_PROP, fontsize=23, color="#173A5E", y=0.985)
    fig.text(
        0.08,
        0.925,
        "一张图同时概括链路、角色分工和关键结果，适合作为论文首页与答辩首页的摘要图。",
        ha="left",
        va="center",
        fontsize=12.1,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )

    step_specs = [
        (0.07, "弱网图像输入", "#335C81", ["原始图像", "巡检/应急场景"]),
        (0.29, "Host Encoder + AWGN", "#6A4C93", ["语义编码", "latent 扰动模拟"]),
        (0.51, "飞腾 Linux + RTOS", "#1B9E77", ["TVM/MNN 重建", "OpenAMP 安全控制"]),
        (0.73, "Dashboard / Evidence", "#2D6A4F", ["重建显示与存储", "面向评审的证据入口"]),
    ]

    centers = []
    for x, title, color, lines in step_specs:
        rect = patches.FancyBboxPatch(
            (x, 0.58),
            0.18,
            0.18,
            boxstyle="round,pad=0.018,rounding_size=0.03",
            facecolor="white",
            edgecolor="#D4DFEA",
            linewidth=1.2,
        )
        ax.add_patch(rect)
        chip = patches.FancyBboxPatch(
            (x + 0.02, 0.70),
            0.14,
            0.045,
            boxstyle="round,pad=0.01,rounding_size=0.02",
            facecolor=color,
            edgecolor="none",
        )
        ax.add_patch(chip)
        ax.text(x + 0.09, 0.722, "阶段", ha="center", va="center", fontsize=10.0, fontproperties=FONT_PROP, color="white", weight="bold")
        ax.text(x + 0.02, 0.66, title, ha="left", va="top", fontsize=14.0, fontproperties=FONT_PROP, color="#173A5E", weight="bold")
        for idx, line in enumerate(lines):
            ax.text(x + 0.02, 0.60 - idx * 0.05, line, ha="left", va="top", fontsize=10.6, fontproperties=FONT_PROP, color="#5B6D80")
        centers.append((x + 0.09, 0.67))

    for start, end in zip(centers[:-1], centers[1:]):
        arrow = patches.FancyArrowPatch(
            (start[0] + 0.10, start[1]),
            (end[0] - 0.10, end[1]),
            arrowstyle="simple",
            mutation_scale=22,
            linewidth=0,
            color="#B7C7D8",
            alpha=0.95,
        )
        ax.add_patch(arrow)

    metric_specs = [
        (0.07, "性能主口径", "#1B9E77", "230.3 / 134.6 ms", "TVM 端到端 / big.LITTLE"),
        (0.38, "安全闭环", "#D95F02", "5 类消息 + 3 FIT", "SAFE_STOP 可观测收敛"),
        (0.69, "动态部署", "#335C81", "327.3 ms/image", "MNN 混合尺寸 / 无需预缩放"),
    ]
    for x, title, color, value, note in metric_specs:
        card = patches.FancyBboxPatch(
            (x, 0.24),
            0.24,
            0.20,
            boxstyle="round,pad=0.018,rounding_size=0.03",
            facecolor="white",
            edgecolor="#D4DFEA",
            linewidth=1.2,
        )
        ax.add_patch(card)
        ax.text(x + 0.02, 0.40, title, ha="left", va="top", fontsize=13.5, fontproperties=FONT_PROP, color=color, weight="bold")
        ax.text(x + 0.02, 0.335, value, ha="left", va="top", fontsize=18.0, fontproperties=FONT_PROP, color="#173A5E", weight="bold")
        ax.text(x + 0.02, 0.275, note, ha="left", va="top", fontsize=10.6, fontproperties=FONT_PROP, color="#5B6D80")

    ribbon = patches.FancyBboxPatch(
        (0.18, 0.10),
        0.64,
        0.07,
        boxstyle="round,pad=0.012,rounding_size=0.03",
        facecolor="#13263F",
        edgecolor="none",
    )
    ax.add_patch(ribbon)
    ax.text(0.50, 0.135, "传得回  |  跑得快  |  用得稳", ha="center", va="center", fontsize=16.0, fontproperties=FONT_PROP, color="white", weight="bold")

    ax.text(0.07, 0.05, "注：性能主口径与混合尺寸结果分别对应固定形状 TVM 与动态尺寸 MNN；控制面结论来自 3 核 Linux + RTOS 演示模式。", ha="left", va="center", fontsize=10.0, fontproperties=FONT_PROP, color="#5B6D80")

    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def render_snr_curve(target: Path) -> None:
    apply_plot_style()
    ensure_dir(target)
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.9), dpi=220)

    ax0, ax1 = axes
    ax0.plot(SNR_POINTS, SNR_LAT_MS, color="#1B9E77", marker="o", linewidth=2.5, markersize=6.5)
    ax0.fill_between(SNR_POINTS, SNR_LAT_MS.min(), SNR_LAT_MS, color="#1B9E77", alpha=0.08)
    ax0.set_title("时延对 SNR 变化不敏感", fontproperties=FONT_PROP, fontsize=16, color="#173A5E", pad=10)
    ax0.set_xlabel("SNR (dB)", fontproperties=FONT_PROP, fontsize=12)
    ax0.set_ylabel("重建时间 (ms/image)", fontproperties=FONT_PROP, fontsize=12)
    ax0.set_xticks(SNR_POINTS)
    ax0.set_ylim(226.5, 235.5)
    for x, y in zip(SNR_POINTS, SNR_LAT_MS):
        ax0.text(x, y + 0.35, f"{y:.1f}", ha="center", va="bottom", fontsize=10.5, fontproperties=FONT_PROP, color="#1B9E77")

    ax1.plot(SNR_POINTS, SNR_PSNR, color="#335C81", marker="o", linewidth=2.5, markersize=6.5, label="PSNR")
    ax1.plot(SNR_POINTS, SNR_SSIM * 40.0, color="#D95F02", marker="s", linewidth=2.1, markersize=5.8, label="SSIM × 40")
    ax1.set_title("质量随信道条件改善而提升", fontproperties=FONT_PROP, fontsize=16, color="#173A5E", pad=10)
    ax1.set_xlabel("SNR (dB)", fontproperties=FONT_PROP, fontsize=12)
    ax1.set_ylabel("PSNR (dB) / SSIM × 40", fontproperties=FONT_PROP, fontsize=12)
    ax1.set_xticks(SNR_POINTS)
    ax1.set_ylim(28, 40)
    ax1.legend(prop=FONT_PROP, frameon=True, loc="upper left")
    for x, y in zip(SNR_POINTS, SNR_PSNR):
        ax1.text(x, y + 0.35, f"{y:.1f}", ha="center", va="bottom", fontsize=10.2, fontproperties=FONT_PROP, color="#335C81")

    fig.suptitle("TVM trusted current 的多 SNR 鲁棒性", fontproperties=FONT_PROP, fontsize=20, color="#173A5E", y=0.99)
    fig.text(
        0.08,
        0.92,
        "基于 300 张图像的真机复测：SNR=1~13 dB 范围内时延稳定在 228~234 ms/image，质量指标单调提升。",
        ha="left",
        va="center",
        fontsize=11.8,
        fontproperties=FONT_PROP,
        color="#5B6D80",
    )
    fig.subplots_adjust(top=0.82, bottom=0.17, left=0.08, right=0.98, wspace=0.2)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)


def load_labeled_image(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)


def render_reconstruction_grid(target: Path) -> None:
    ensure_dir(target)
    canvas_w, canvas_h = 1980, 1100
    pad_x, pad_y = 84, 52
    title_h = 118
    label_h = 44
    row_gap = 48
    col_gap = 26
    img_w, img_h = 380, 280
    bg = Image.new("RGB", (canvas_w, canvas_h), "#FFFFFF")
    draw = ImageDraw = None

    from PIL import ImageDraw, ImageFont

    def load_font_local(size: int, bold: bool = False):
        candidates = [
            Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for p in candidates:
            if p.is_file():
                return ImageFont.truetype(str(p), size)
        return ImageFont.load_default()

    f_title = load_font_local(42, bold=True)
    f_sub = load_font_local(22)
    f_label = load_font_local(26, bold=True)
    f_row = load_font_local(24, bold=True)

    draw = ImageDraw.Draw(bg)
    draw.text((pad_x, 24), "重建效果对比：PyTorch reference vs TVM current", fill="#173A5E", font=f_title)
    draw.text(
        (pad_x, 78),
        "相同样本在不同 SNR 下的重建结果。列方向展示信道条件变化，行方向展示不同场景样本。",
        fill="#5B6D80",
        font=f_sub,
    )

    column_defs = [
        ("PyTorch ref", None),
        ("SNR=1 dB", "snr1"),
        ("SNR=7 dB", "snr7"),
        ("SNR=13 dB", "snr13"),
    ]

    for col_idx, (label, _) in enumerate(column_defs):
        x = pad_x + col_idx * (img_w + col_gap)
        draw.text((x + 96, title_h + 6), label, fill="#173A5E", font=f_label)

    for row_idx, sample_name in enumerate(RECON_SAMPLES):
        y = title_h + label_h + row_idx * (img_h + row_gap)
        stem = sample_name.replace("_recon.png", "")
        draw.text((24, y + img_h // 2 - 18), f"#{stem.split('_')[-1][-5:]}", fill="#13263A", font=f_row)

        ref_path = QUALITY_ROOT / sample_name
        image_paths = [
            ref_path,
            SNR_ROOT / "snr_current_chunk4_snr1_20260330_152054_current" / "reconstructions" / sample_name,
            SNR_ROOT / "snr_current_chunk4_snr7_20260330_152054_current" / "reconstructions" / sample_name,
            SNR_ROOT / "snr_current_chunk4_snr13_20260330_152054_current" / "reconstructions" / sample_name,
        ]
        for col_idx, image_path in enumerate(image_paths):
            x = pad_x + col_idx * (img_w + col_gap)
            tile = load_labeled_image(image_path, (img_w, img_h))
            bg.paste(tile, (x, y))
            draw.rounded_rectangle((x, y, x + img_w, y + img_h), radius=14, outline="#AAB8C4", width=2)

    draw.text(
        (pad_x, canvas_h - 38),
        "说明：参考列为本地归档的 PyTorch reference 重建；其余列为 TVM trusted current 在不同 SNR 下的真机输出。",
        fill="#5B6D80",
        font=f_sub,
    )
    bg.save(target)


def main() -> None:
    for asset in PDF_ASSETS:
        render_pdf(asset)
    render_project_timeline(FIG_DIR / "paper_fig_project_timeline_cn_20260405.png")
    render_control_message_sequence(FIG_DIR / "paper_fig_control_message_sequence_cn_20260405.png")
    render_mnn_arch(FIG_DIR / "paper_fig_mnn_arch_cn_20260405.png")
    render_evidence_bundle_map(FIG_DIR / "paper_fig_evidence_bundle_cn_20260405.png")
    render_semantic_vs_traditional(FIG_DIR / "paper_fig_semantic_vs_traditional_cn_20260405.png")
    render_system_closure_overview(FIG_DIR / "paper_fig_system_closure_overview_cn_20260405.png")
    render_cover_summary(FIG_DIR / "paper_fig_cover_summary_cn_20260405.png")
    render_reconstruction_grid(FIG_DIR / "paper_fig_reconstruction_gallery_cn_20260405.png")
    for asset in PDF_ASSETS:
        print(asset.target)
    print(FIG_DIR / "paper_fig_project_timeline_cn_20260405.png")
    print(FIG_DIR / "paper_fig_control_message_sequence_cn_20260405.png")
    print(FIG_DIR / "paper_fig_mnn_arch_cn_20260405.png")
    print(FIG_DIR / "paper_fig_evidence_bundle_cn_20260405.png")
    print(FIG_DIR / "paper_fig_semantic_vs_traditional_cn_20260405.png")
    print(FIG_DIR / "paper_fig_system_closure_overview_cn_20260405.png")
    print(FIG_DIR / "paper_fig_cover_summary_cn_20260405.png")
    print(FIG_DIR / "paper_fig_reconstruction_gallery_cn_20260405.png")


if __name__ == "__main__":
    main()
