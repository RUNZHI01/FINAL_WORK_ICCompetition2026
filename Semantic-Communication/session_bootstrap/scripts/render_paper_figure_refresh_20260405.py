#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
SCREEN_DIR = ROOT / "output" / "playwright"

RUNNING_SCREEN = SCREEN_DIR / "cockpit_dashboard_running.png"
FAULT_SCREEN = SCREEN_DIR / "cockpit_dashboard_faults.png"

BG = "#F4F7FB"
CARD = "#FFFFFF"
INK = "#10243E"
MUTED = "#5D728A"
LINE = "#D7E2EE"
BLUE = "#2C6BFF"
TEAL = "#159D90"
GREEN = "#24A06B"
ORANGE = "#E17A21"
RED = "#D9425F"
PURPLE = "#7461D9"
CYAN = "#2A8FB4"


@dataclass(frozen=True)
class Callout:
    idx: int
    anchor: tuple[float, float]
    title: str
    detail: str
    color: str


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
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


def rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(hex_color)
    return (r, g, b, alpha)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    lines: list[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current.rstrip())
            current = ""
            continue
        trial = current + ch
        width = draw.textbbox((0, 0), trial, font=font)[2]
        if current and width > max_width:
            lines.append(current.rstrip())
            current = ch
        else:
            current = trial
    if current:
        lines.append(current.rstrip())
    return "\n".join(lines)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, spacing: int = 6) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_header_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    title: str,
    subtitle: str,
    *,
    title_font: ImageFont.ImageFont,
    subtitle_font: ImageFont.ImageFont,
    max_width: int,
    title_fill: str = INK,
    subtitle_fill: str = MUTED,
    subtitle_spacing: int = 8,
) -> int:
    draw.text((x, y), title, fill=title_fill, font=title_font)
    _, title_h = text_size(draw, title, title_font)
    wrapped = wrap_text(draw, subtitle, subtitle_font, max_width)
    subtitle_y = y + title_h + 18
    draw.multiline_text((x, subtitle_y), wrapped, fill=subtitle_fill, font=subtitle_font, spacing=subtitle_spacing)
    _, subtitle_h = text_size(draw, wrapped, subtitle_font, spacing=subtitle_spacing)
    return subtitle_y + subtitle_h


def rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None, radius: int = 30, width: int = 2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def shadow(canvas: Image.Image, box: tuple[int, int, int, int], radius: int = 28, alpha: int = 50, y_shift: int = 16) -> None:
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x0, y0 + y_shift, x1, y1 + y_shift), radius=radius, fill=(17, 35, 59, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(24))
    canvas.alpha_composite(layer)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fill: str, text_fill: str = "#FFFFFF", h_pad: int = 18, v_pad: int = 10, font: ImageFont.ImageFont | None = None) -> tuple[int, int, int, int]:
    font = font or load_font(28, bold=True)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    width = right - left + h_pad * 2
    height = bottom - top + v_pad * 2
    box = (x, y, x + width, y + height)
    draw.rounded_rectangle(box, radius=height // 2, fill=fill)
    draw.text((x + h_pad, y + v_pad - 2), text, fill=text_fill, font=font)
    return box


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 6) -> None:
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


def poly_arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, width: int = 6) -> None:
    if len(points) < 2:
        return
    draw.line(points, fill=color, width=width)
    start = points[-2]
    end = points[-1]
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


def draw_footer_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: str = "#EDF4FB",
    outline: str = "#D4E1EE",
    text_fill: str = MUTED,
    padding_x: int = 28,
    padding_y: int = 20,
) -> None:
    rounded_panel(draw, box, fill, outline, radius=24)
    wrapped = wrap_text(draw, text, font, box[2] - box[0] - padding_x * 2)
    draw.multiline_text((box[0] + padding_x, box[1] + padding_y), wrapped, fill=text_fill, font=font, spacing=8)


def paste_image_card(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int], radius: int = 34, border: str = LINE) -> None:
    x0, y0, x1, y1 = box
    shadow(canvas, box, radius=radius, alpha=55, y_shift=18)
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0, y1 - y0), radius=radius, fill=255)
    framed = ImageOps.fit(source, (x1 - x0, y1 - y0), method=Image.Resampling.LANCZOS)
    canvas.paste(framed.convert("RGBA"), (x0, y0), mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, outline=border, width=2)


def paste_contained_card(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int], radius: int = 34, border: str = LINE, fill: str = "#F8FBFF") -> None:
    x0, y0, x1, y1 = box
    shadow(canvas, box, radius=radius, alpha=55, y_shift=18)
    panel = Image.new("RGBA", (x1 - x0, y1 - y0), fill)
    contained = ImageOps.contain(source, (x1 - x0 - 28, y1 - y0 - 28), method=Image.Resampling.LANCZOS)
    px = (panel.width - contained.width) // 2
    py = (panel.height - contained.height) // 2
    panel.paste(contained.convert("RGBA"), (px, py))
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0, y1 - y0), radius=radius, fill=255)
    canvas.paste(panel, (x0, y0), mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, outline=border, width=2)


def place_callout_marker(draw: ImageDraw.ImageDraw, x: int, y: int, idx: int, color: str, radius: int = 28) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline="#FFFFFF", width=4)
    text = str(idx)
    font = load_font(28, bold=True)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((x - (right - left) / 2, y - (bottom - top) / 2 - 2), text, fill="#FFFFFF", font=font)


def load_screen(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Missing screenshot: {path}\nRun capture_cockpit_paper_screens_20260405.js first.")
    return Image.open(path).convert("RGBA")


def has_demo_screens() -> bool:
    return RUNNING_SCREEN.is_file() and FAULT_SCREEN.is_file()


def render_system_arch(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2160, 1320), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(42, bold=True)
    f_text = load_font(28)
    f_small = load_font(24)
    f_bold = load_font(30, bold=True)
    header_bottom = draw_header_block(
        draw,
        96,
        72,
        "系统总体架构",
        "把上位机编码、飞腾 Linux 数据面与 RTOS 控制面拆开，是为了同时满足“传得回、跑得快、用得稳”的现场要求。",
        title_font=f_title,
        subtitle_font=f_text,
        max_width=1720,
    )
    pill(draw, 96, header_bottom + 26, "Data Plane", BLUE, font=load_font(22, bold=True))
    pill(draw, 258, header_bottom + 26, "Control Plane", ORANGE, font=load_font(22, bold=True))

    host_box = (80, 320, 600, 1060)
    transport_box = (760, 440, 1160, 650)
    control_box = (860, 780, 1260, 980)
    linux_box = (1320, 280, 2070, 680)
    rtos_box = (1320, 780, 2070, 1090)

    for box in (host_box, transport_box, control_box, linux_box, rtos_box):
        shadow(canvas, box)
    rounded_panel(draw, host_box, CARD, LINE)
    rounded_panel(draw, transport_box, "#F0F7FF", "#CFE0FF")
    rounded_panel(draw, control_box, "#FFF7F0", "#FFD8B3")
    rounded_panel(draw, linux_box, "#F8FBFF", "#CFE0FF")
    rounded_panel(draw, rtos_box, "#FFF8F1", "#FFD8B3")

    draw.text((124, 372), "上位机 / 发送端", fill=INK, font=f_bold)
    draw.text((124, 430), "RTX 4060 + i7-13700H", fill=MUTED, font=f_small)
    rounded_panel(draw, (124, 520, 554, 674), "#EFF6FF", "#CFE0FF", radius=28)
    draw.text((164, 560), "Encoder 语义编码", fill=INK, font=f_bold)
    draw.text((164, 608), "输入图像 -> latent 张量", fill=MUTED, font=f_small)
    rounded_panel(draw, (124, 736, 554, 900), "#F8FAFD", "#DDE7F0", radius=28)
    draw.text((164, 778), "量化 + AWGN 扰动", fill=INK, font=f_bold)
    host_detail = wrap_text(draw, "将 256×256 图像压缩为可远端传输的紧凑表征。", f_small, 340)
    draw.multiline_text((164, 826), host_detail, fill=MUTED, font=f_small, spacing=8)

    draw.text((804, 490), "安全传输", fill=INK, font=f_bold)
    draw.text((804, 548), "OpenSSH / AES-128-CTR", fill=BLUE, font=load_font(26, bold=True))
    transport_text = wrap_text(draw, "弱网条件下优先传语义特征，不回传大体量原图。", f_small, 286)
    draw.multiline_text((804, 594), transport_text, fill=MUTED, font=f_small, spacing=8)

    draw.text((900, 830), "OpenAMP / RPMsg", fill=INK, font=f_bold)
    control_text = wrap_text(draw, "小消息控制链路，只传作业、状态与 fault_code，不承载大数据。", f_small, 306)
    draw.multiline_text((900, 884), control_text, fill=MUTED, font=f_small, spacing=8)

    draw.text((1362, 334), "飞腾 Linux 数据面", fill=INK, font=f_bold)
    draw.text((1362, 392), "TVM 固定形状主线 + MNN 动态尺寸旁路", fill=MUTED, font=f_small)
    rounded_panel(draw, (1362, 474, 1676, 624), "#EFF6FF", "#CFE0FF", radius=28)
    rounded_panel(draw, (1716, 474, 2028, 624), "#F2FCFA", "#CDEDE5", radius=28)
    draw.multiline_text((1410, 520), "TVM\n静态极致性能", fill=INK, font=load_font(32, bold=True), spacing=4)
    draw.multiline_text((1762, 520), "MNN\n动态尺寸适配", fill=INK, font=load_font(32, bold=True), spacing=4)
    linux_out = wrap_text(draw, "输出：重建图像、性能日志与证据归档。", f_small, 620)
    draw.multiline_text((1362, 640), linux_out, fill=MUTED, font=f_small, spacing=8)

    draw.text((1362, 836), "RTOS / Bare Metal 控制面", fill=INK, font=f_bold)
    draw.text((1362, 894), "负责准入判定、心跳监护与安全停机。", fill=MUTED, font=f_small)
    rounded_panel(draw, (1362, 962, 2014, 1044), "#FFFDF8", "#FFE2BC", radius=24)
    job_text = wrap_text(draw, "JOB_REQ / HEARTBEAT / SAFE_STOP / STATUS_REQ", load_font(24, bold=True), 600)
    draw.multiline_text((1392, 986), job_text, fill=ORANGE, font=load_font(24, bold=True), spacing=6)

    poly_arrow(draw, [(554, 598), (760, 546)], BLUE)
    poly_arrow(draw, [(1160, 546), (1320, 546)], BLUE)
    poly_arrow(draw, [(1620, 680), (1620, 730), (1160, 730), (1160, 780)], ORANGE)
    poly_arrow(draw, [(1260, 880), (1320, 880)], ORANGE)

    pill(draw, 836, 386, "数据传输", BLUE, font=load_font(20, bold=True), h_pad=14, v_pad=7)
    pill(draw, 1300, 724, "控制消息", ORANGE, font=load_font(20, bold=True), h_pad=14, v_pad=7)

    note_box = (80, 1160, 2070, 1246)
    draw_footer_panel(
        draw,
        note_box,
        "正式性能数字只引用 Linux 数据面；OpenAMP 与 FIT 结论只引用 RTOS 控制面，避免双模式口径混写。",
        font=f_text,
    )
    canvas.convert("RGB").save(target)


def render_project_timeline(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2140, 1120), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(42, bold=True)
    f_sub = load_font(28)
    f_card_title = load_font(28, bold=True)
    f_card_body = load_font(22)
    header_bottom = draw_header_block(
        draw,
        96,
        72,
        "项目开发时间线",
        "从首次推理成功到 OpenAMP 闭环、big.LITTLE 加速与 Electron 演示收口，项目在 2026 年 3 月完成系统级成形。",
        title_font=f_title,
        subtitle_font=f_sub,
        max_width=1780,
    )

    milestones = [
        ("03-01", "基础打通", "飞腾派 TVM 推理首次成功"),
        ("03-08~10", "运行时重建", "TVM 0.24 安全运行时与\nA72 目标收敛"),
        ("03-11~13", "性能突破", "端到端 1850 ms\n降至 230 ms"),
        ("03-14~15", "控制面闭环", "OpenAMP 五类消息 + 三项\nFIT 收证"),
        ("03-18", "异构加速", "big.LITTLE 流水线\n吞吐提升 56.1%"),
        ("03-17~30", "演示集成", "current live 300/300 与\nElectron 界面收口"),
    ]
    colors = [CYAN, PURPLE, GREEN, ORANGE, TEAL, RED]
    base_y = 640
    draw.line((140, base_y, 1980, base_y), fill="#B6C7D9", width=8)

    xs = [220, 560, 900, 1240, 1580, 1920]
    for idx, ((date_text, title, body), color) in enumerate(zip(milestones, colors)):
        y = 370 if idx % 2 == 0 else 860
        draw.line((xs[idx], base_y, xs[idx], y), fill="#C8D6E4", width=4)
        draw.ellipse((xs[idx] - 20, base_y - 20, xs[idx] + 20, base_y + 20), fill=color, outline="#FFFFFF", width=4)
        box = (xs[idx] - 184, y - 104, xs[idx] + 184, y + 104)
        shadow(canvas, box, radius=28, alpha=45, y_shift=10)
        rounded_panel(draw, box, CARD, LINE, radius=28)
        pill(draw, box[0] + 18, box[1] + 16, date_text, color, font=load_font(22, bold=True), h_pad=14, v_pad=8)
        draw.text((box[0] + 18, box[1] + 62), title, fill=INK, font=f_card_title)
        wrapped = wrap_text(draw, body, f_card_body, 304)
        draw.multiline_text((box[0] + 18, box[1] + 104), wrapped, fill=MUTED, font=f_card_body, spacing=8)

    note_box = (96, 1000, 2040, 1086)
    draw_footer_panel(
        draw,
        note_box,
        "时间线只保留六个系统收口节点，不把零碎试验记录全部塞入同一页，以保证阅读路径从左到右稳定可跟踪。",
        font=f_sub,
    )
    canvas.convert("RGB").save(target)


def render_openamp_state_machine(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (2080, 1280), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(42, bold=True)
    f_body = load_font(28)
    f_state_sub = load_font(24)
    header_bottom = draw_header_block(
        draw,
        96,
        72,
        "OpenAMP 控制状态机",
        "RTOS 从核用确定性五状态约束 JOB_REQ、HEARTBEAT、SAFE_STOP 与 JOB_DONE 的合法转移。",
        title_font=f_title,
        subtitle_font=f_body,
        max_width=1760,
    )

    states = {
        "READY": ((120, 340, 500, 520), CYAN, "空闲待命"),
        "CHECKING": ((700, 340, 1120, 520), PURPLE, "工件 / 参数校验"),
        "RUNNING": ((1360, 340, 1760, 520), GREEN, "心跳监护激活"),
        "FAULT": ((500, 780, 920, 960), RED, "故障留痕"),
        "SAFE_STOP": ((1260, 780, 1720, 960), ORANGE, "安全停机与收敛"),
    }
    for name, (box, color, sub) in states.items():
        shadow(canvas, box, radius=36, alpha=48, y_shift=12)
        rounded_panel(draw, box, CARD, color, radius=36, width=5)
        pill(draw, box[0] + 22, box[1] + 20, name, color, font=load_font(24, bold=True))
        draw.text((box[0] + 34, box[1] + 90), sub, fill=MUTED, font=f_state_sub)

    label_font = load_font(24, bold=True)
    poly_arrow(draw, [(500, 430), (700, 430)], BLUE)
    poly_arrow(draw, [(1120, 430), (1360, 430)], GREEN)
    poly_arrow(draw, [(960, 340), (960, 290), (320, 290), (320, 340)], PURPLE)
    poly_arrow(draw, [(1460, 520), (1460, 780)], ORANGE)
    poly_arrow(draw, [(660, 780), (660, 690), (300, 690), (300, 520)], CYAN)

    labels = [
        ((560, 378), "JOB_REQ", BLUE),
        ((1190, 378), "JOB_ACK(ALLOW)", GREEN),
        ((770, 218), "JOB_ACK(DENY): SHA / 参数非法", PURPLE),
        ((1510, 630), "SAFE_STOP / heartbeat timeout", ORANGE),
        ((340, 650), "故障留痕后返回 READY", CYAN),
    ]
    for (x, y), text, color in labels:
        bbox = draw.textbbox((0, 0), text, font=label_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        rounded_panel(draw, (x, y, x + w + 28, y + h + 18), "#FFFFFF", None, radius=18, width=0)
        draw.text((x + 14, y + 8), text, fill=color, font=label_font)

    observe_box = (910, 1010, 1760, 1092)
    rounded_panel(draw, observe_box, "#FFF7F8", "#F0D7DD", radius=24)
    observe_text = wrap_text(draw, "STATUS_REQ 只承担查询职责：Linux 可观测 SAFE_STOP / FAULT，并读取最后一次 fault_code 与 heartbeat 结果。", f_state_sub, 780)
    draw.multiline_text((944, 1032), observe_text, fill=RED, font=f_state_sub, spacing=8)

    footer = (96, 1140, 1980, 1224)
    draw_footer_panel(
        draw,
        footer,
        "FAULT 与 SAFE_STOP 都被设计成“可观测安全态”；状态查询不参与状态推进，因此单独放到图下方说明，而不再压在状态节点之间。",
        font=f_body,
    )
    canvas.convert("RGB").save(target)


def render_mnn_benchmark(target: Path) -> None:
    ensure_dir(target)
    canvas = Image.new("RGBA", (1800, 1040), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(40, bold=True)
    f_sub = load_font(26)
    f_label = load_font(28, bold=True)
    f_body = load_font(24)
    f_value = load_font(28, bold=True)

    draw.text((110, 78), "MNN 动态尺寸配置对比", fill=INK, font=f_title)
    draw.text((110, 140), "同口径真机复测 300 张混合尺寸图像。当前正式最优仍为 2 interpreters + 1 thread/session + FP32(normal)。", fill=MUTED, font=f_sub)

    bar_left = 330
    bar_top = 260
    bar_width = 1180
    labels = [
        ("基线", "1I / 1T / FP32", 140.7, "#8897A8"),
        ("正式最优", "2I / 1T / FP32", 98.2, GREEN),
        ("低精度", "2I / 1T / low", 99.1, ORANGE),
        ("多线程", "2I / 2T / FP32", 101.3, PURPLE),
    ]
    max_value = 150.0

    rounded_panel(draw, (110, 220, 1690, 920), CARD, LINE, radius=34)
    for idx, (label, detail, value, color) in enumerate(labels):
        y = bar_top + idx * 150
        draw.text((150, y + 12), label, fill=INK, font=f_label)
        draw.text((150, y + 54), detail, fill=MUTED, font=f_body)
        rounded_panel(draw, (bar_left, y + 18, bar_left + bar_width, y + 78), "#EEF3F8", None, radius=28, width=0)
        fill_w = int(bar_width * value / max_value)
        rounded_panel(draw, (bar_left, y + 18, bar_left + fill_w, y + 78), color, None, radius=28, width=0)
        draw.text((bar_left + fill_w + 28, y + 24), f"{value:.1f} s", fill=INK, font=f_value)
        draw.text((1540, y + 24), f"{value * 1000 / 300:.1f} ms / image", fill=MUTED, font=f_body)
        if label == "正式最优":
            pill(draw, bar_left + fill_w - 150, y + 24, "当前最优", "#0C8055", font=load_font(22, bold=True), h_pad=16, v_pad=7)

    baseline = labels[0][2]
    best = labels[1][2]
    uplift = baseline / best
    note = (110, 940, 1690, 1010)
    rounded_panel(draw, note, "#EDF7F1", "#CDE8D7", radius=24)
    draw.text((140, 962), f"基线 → 正式最优：{uplift:.2f}x；正式最优的单张平均时间为 {best * 1000 / 300:.1f} ms / image。", fill="#176846", font=f_sub)
    canvas.convert("RGB").save(target)


def render_demo_overview(target: Path) -> None:
    ensure_dir(target)
    running = load_screen(RUNNING_SCREEN)
    canvas = Image.new("RGBA", (2200, 1260), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(40, bold=True)
    f_sub = load_font(26)
    f_card_title = load_font(26, bold=True)
    f_card_body = load_font(24)

    draw.text((100, 70), "Electron 演示界面证据映射", fill=INK, font=f_title)
    draw.text((100, 132), "图中各区域分别对应性能口径、Current 进度、故障注入、结果对比、飞行遥测与 ML-KEM 安全通道。", fill=MUTED, font=f_sub)

    screen_box = (100, 220, 1500, 1120)
    paste_image_card(canvas, running, screen_box, radius=34)
    legend_box = (1560, 220, 2100, 1120)
    shadow(canvas, legend_box, radius=34, alpha=45, y_shift=14)
    rounded_panel(draw, legend_box, CARD, LINE, radius=34)
    pill(draw, 1595, 250, "cockpit_desktop", BLUE, font=load_font(22, bold=True))
    draw.text((1595, 330), "论文中与 Demo 相关的图片\n全部改为 Electron 版实拍。", fill=INK, font=load_font(30, bold=True), spacing=8)

    callouts = [
        Callout(1, (0.27, 0.06), "指标条", "在线状态、payload、baseline 与 uplift 口径同屏展示。", BLUE),
        Callout(2, (0.18, 0.22), "Current 进度", "300 张图像推进到第 247 张，并显示当前阶段与运行日志。", TEAL),
        Callout(3, (0.18, 0.47), "动作入口", "探测板卡、Current 启动、故障注入与 SAFE_STOP 收口。", ORANGE),
        Callout(4, (0.18, 0.72), "结果对比", "Current vs Baseline 条形对比，同时保留 PSNR / SSIM。", GREEN),
        Callout(5, (0.79, 0.28), "航迹与遥测", "无人机位置、航向、速度与高度等任务态势信息。", CYAN),
        Callout(6, (0.80, 0.73), "侧栏状态", "硬件遥测、最后一次 fault 与 ML-KEM 安全信道状态。", PURPLE),
    ]

    sx0, sy0, sx1, sy1 = screen_box
    sw = sx1 - sx0
    sh = sy1 - sy0
    for item in callouts:
        cx = sx0 + int(sw * item.anchor[0])
        cy = sy0 + int(sh * item.anchor[1])
        place_callout_marker(draw, cx, cy, item.idx, item.color)

    cursor_y = 440
    for item in callouts:
        panel = (1590, cursor_y, 2068, cursor_y + 112)
        rounded_panel(draw, panel, "#FBFCFE", "#E4EDF4", radius=24)
        place_callout_marker(draw, 1630, cursor_y + 56, item.idx, item.color, radius=22)
        draw.text((1670, cursor_y + 18), item.title, fill=INK, font=f_card_title)
        wrapped = wrap_text(draw, item.detail, f_card_body, 360)
        draw.multiline_text((1670, cursor_y + 52), wrapped, fill=MUTED, font=f_card_body, spacing=6)
        cursor_y += 126

    canvas.convert("RGB").save(target)


def render_demo_dashboard(target: Path) -> None:
    ensure_dir(target)
    running = load_screen(RUNNING_SCREEN)
    canvas = Image.new("RGBA", (2060, 1360), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(40, bold=True)
    f_sub = load_font(26)
    draw.text((100, 70), "Electron 演示主界面实拍", fill=INK, font=f_title)
    draw.text((100, 132), "运行态界面将控制面状态、Current 进度、结果对比、飞行遥测与安全链路信息压缩到同一屏。", fill=MUTED, font=f_sub)
    pill(draw, 1620, 72, "运行态截图", GREEN, font=load_font(22, bold=True))
    pill(draw, 1610, 128, "247 / 300", BLUE, font=load_font(22, bold=True))
    pill(draw, 1760, 128, "57.4% uplift", TEAL, font=load_font(22, bold=True))

    frame_box = (210, 220, 1850, 1240)
    paste_contained_card(canvas, running, frame_box, radius=36)
    footer = (100, 1240, 1960, 1310)
    rounded_panel(draw, footer, "#EDF4FB", "#D4E1EE", radius=24)
    draw.text((132, 1261), "图像来源为本地 Electron `cockpit_desktop` 真实渲染页面，不再引用早期 web 原型或深色占位界面。", fill=MUTED, font=f_sub)
    canvas.convert("RGB").save(target)


def render_demo_detail_panels(target: Path) -> None:
    ensure_dir(target)
    running = load_screen(RUNNING_SCREEN)
    faults = load_screen(FAULT_SCREEN)

    fw, fh = faults.size
    rw, rh = running.size
    left_crop = faults.crop((0, int(fh * 0.26), int(fw * 0.62), int(fh * 0.92)))
    right_crop = running.crop((int(rw * 0.61), int(rh * 0.12), rw, int(rh * 0.98)))

    canvas = Image.new("RGBA", (2140, 1220), BG)
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(40, bold=True)
    f_sub = load_font(26)
    f_card = load_font(28, bold=True)
    f_body = load_font(24)

    draw.text((100, 70), "Electron 关键细节面板", fill=INK, font=f_title)
    draw.text((100, 132), "左侧聚焦 Current 重建、结果对比与故障注入；右侧聚焦飞行遥测、硬件状态与 ML-KEM 安全信道。", fill=MUTED, font=f_sub)

    left_box = (100, 300, 1110, 1030)
    right_box = (1170, 300, 2040, 1030)
    paste_image_card(canvas, left_crop, left_box, radius=32)
    paste_image_card(canvas, right_crop, right_box, radius=32)

    pill(draw, 128, 220, "局部 A", BLUE, font=load_font(22, bold=True))
    draw.text((128, 270), "Current 重建与故障收口", fill=INK, font=f_card)
    draw.text((128, 314), "进度条、对比条形图、故障注入按钮与 SAFE_STOP 收口入口同屏。", fill=MUTED, font=f_body)

    pill(draw, 1198, 220, "局部 B", TEAL, font=load_font(22, bold=True))
    draw.text((1198, 270), "遥测、硬件与安全链路", fill=INK, font=f_card)
    draw.text((1198, 314), "地图、硬件遥测、最后一次 fault 与 ML-KEM 状态形成右侧监护视图。", fill=MUTED, font=f_body)

    footer = (100, 1070, 2040, 1140)
    rounded_panel(draw, footer, "#EDF4FB", "#D4E1EE", radius=22)
    draw.text((130, 1090), "两块局部图均来自同一套 Electron 演示界面，只是分别放大了“操作与结果”以及“监护与链路”两类高频答辩区域。", fill=MUTED, font=f_sub)
    canvas.convert("RGB").save(target)


def main() -> None:
    if has_demo_screens():
        render_demo_overview(FIG_DIR / "paper_fig_demo_workflow_cn_20260405.png")
        render_demo_dashboard(FIG_DIR / "paper_fig_demo_dashboard_ui_cn_20260405.png")
        render_demo_detail_panels(FIG_DIR / "paper_fig_demo_detail_panels_cn_20260405.png")
    else:
        print("Skip demo figures: cached Electron screenshots are missing.")
    if has_demo_screens():
        print(FIG_DIR / "paper_fig_demo_workflow_cn_20260405.png")
        print(FIG_DIR / "paper_fig_demo_dashboard_ui_cn_20260405.png")
        print(FIG_DIR / "paper_fig_demo_detail_panels_cn_20260405.png")


if __name__ == "__main__":
    main()
