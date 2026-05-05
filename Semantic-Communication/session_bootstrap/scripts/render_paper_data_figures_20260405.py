#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import scienceplots  # noqa: F401
import seaborn as sns


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "session_bootstrap" / "reports"
FIG_DIR = REPORT_DIR / "figures"
FOLLOWUP_DIR = REPORT_DIR / "daily_20260404_openamp_3core_big_little_followup"

SNR_JSON = REPORT_DIR / "snr_sweep_current_chunk4_20260330_152054.json"
EVIDENCE_JSON = REPORT_DIR / "judge_evidence_pack_20260330_current_chunk4.json"
RESOURCE_JSON = REPORT_DIR / "resource_profile_trusted_current_chunk4_20260330_151728.json"
BIG_LITTLE_4CORE_JSON = REPORT_DIR / "big_little_compare_20260318_123300.json"
BIG_LITTLE_3CORE_JSONS = {
    "metaschedule优化": FOLLOWUP_DIR / "big_little_compare_20260404_200243.json",
    "metaschedule+手写算子优化": FOLLOWUP_DIR / "big_little_compare_20260404_195323.json",
    "ACL 单热点探索线": FOLLOWUP_DIR / "big_little_compare_20260404_195647.json",
}

OUT_SNR = FIG_DIR / "paper_fig_snr_robustness_cn_20260405.png"
OUT_TVM_SUMMARY = FIG_DIR / "paper_fig_tvm_result_summary_cn_20260405.png"
OUT_MNN = FIG_DIR / "paper_fig_mnn_benchmark_cn_20260405.png"
OUT_BIG_LITTLE = FIG_DIR / "paper_fig3_big_little_pipeline_cn_20260404.png"
OUT_FRAMEWORK = FIG_DIR / "paper_fig_framework_positioning_cn_20260405.png"
OUT_TRADEOFF = FIG_DIR / "paper_fig_perf_quality_tradeoff_cn_20260405.png"
OUT_LADDER = FIG_DIR / "paper_fig_performance_ladder_cn_20260405.png"

COLORS = {
    "tvm": "#1F5AA6",
    "tvm_light": "#6B9BD1",
    "pipeline": "#1D8A66",
    "mnn": "#127A90",
    "mnn_light": "#6DB3C2",
    "control": "#D97925",
    "gray": "#7C8895",
    "gray_light": "#C6CED7",
    "danger": "#C94B59",
    "ink": "#16324F",
    "muted": "#5F7286",
    "grid": "#D9E2EB",
    "paper_bg": "#FAFBFD",
}


@dataclass(frozen=True)
class MnnConfig:
    label: str
    total_seconds: float
    avg_ms_per_image: float
    color: str


MNN_CONFIGS = [
    MnnConfig("1I / 1T / FP32", 140.7, 469.1, COLORS["gray"]),
    MnnConfig("2I / 1T / FP32", 98.2, 327.3, COLORS["pipeline"]),
    MnnConfig("2I / 1T / low", 99.1, 330.3, COLORS["control"]),
    MnnConfig("2I / 2T / FP32", 101.3, 337.7, COLORS["mnn"]),
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def choose_font() -> fm.FontProperties:
    candidates = [
        Path("/home/tianxing/.local/share/fonts/windows/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return fm.FontProperties(fname=str(candidate))
    return fm.FontProperties()


FONT = choose_font()


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def apply_style() -> None:
    plt.style.use(["science", "no-latex", "grid"])
    sns.set_theme(style="ticks")
    plt.rcParams["font.family"] = FONT.get_name()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = COLORS["paper_bg"]
    plt.rcParams["axes.facecolor"] = "#FFFFFF"
    plt.rcParams["axes.edgecolor"] = "#AAB8C4"
    plt.rcParams["axes.labelcolor"] = COLORS["ink"]
    plt.rcParams["text.color"] = COLORS["ink"]
    plt.rcParams["xtick.color"] = COLORS["ink"]
    plt.rcParams["ytick.color"] = COLORS["ink"]
    plt.rcParams["grid.color"] = COLORS["grid"]
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.linewidth"] = 0.8
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.titlepad"] = 10
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["legend.frameon"] = False


def add_header(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.suptitle(title, x=0.06, y=0.98, ha="left", fontproperties=FONT, fontsize=20, color=COLORS["ink"])
    fig.text(0.06, 0.92, subtitle, ha="left", va="top", fontproperties=FONT, fontsize=10.8, color=COLORS["muted"])


def label_bars(ax: plt.Axes, decimals: int = 1, suffix: str = "") -> None:
    for patch in ax.patches:
        value = patch.get_width() if patch.get_width() > patch.get_height() else patch.get_height()
        if patch.get_width() > patch.get_height():
            ax.text(
                patch.get_width() + (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.015,
                patch.get_y() + patch.get_height() / 2,
                f"{value:.{decimals}f}{suffix}",
                va="center",
                ha="left",
                fontsize=9.5,
                fontproperties=FONT,
                color=COLORS["ink"],
            )
        else:
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height() + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.03,
                f"{value:.{decimals}f}{suffix}",
                va="bottom",
                ha="center",
                fontsize=9.2,
                fontproperties=FONT,
                color=COLORS["ink"],
            )


def load_paper_metrics() -> dict:
    evidence = read_json(EVIDENCE_JSON)
    resource = read_json(RESOURCE_JSON)
    quality_paper = {
        "baseline_psnr": 34.42,
        "current_psnr": 35.66,
        "baseline_ssim": 0.9705,
        "current_ssim": 0.9728,
    }

    payload = evidence["payload_report"]["fields"]
    e2e = evidence["e2e_report"]["fields"]
    big_little = read_json(BIG_LITTLE_4CORE_JSON)
    artifact_size_mib = evidence["artifact"]["size_bytes"] / 1024.0 / 1024.0

    return {
        "payload_baseline_ms": float(payload["baseline_run_median_ms"]),
        "payload_current_ms": float(payload["current_run_median_ms"]),
        "e2e_baseline_ms": float(e2e["baseline_run_median_ms"]),
        "e2e_current_ms": float(e2e["current_run_median_ms"]),
        "serial_median_ms": float(big_little["serial"]["run_median_ms"]),
        "pipeline_median_ms": float(big_little["pipeline"]["pipeline"]["run_median_ms"]),
        "serial_ips": float(big_little["comparison"]["serial_images_per_sec"]),
        "pipeline_ips": float(big_little["comparison"]["pipeline_images_per_sec"]),
        "serial_total_s": float(big_little["comparison"]["serial_total_wall_ms"]) / 1000.0,
        "pipeline_total_s": float(big_little["comparison"]["pipeline_total_wall_ms"]) / 1000.0,
        "throughput_uplift_pct": float(big_little["comparison"]["throughput_uplift_pct"]),
        "artifact_mib": artifact_size_mib,
        "min_free_kb": int(resource["vmstat_summary"]["min_free_kb"]),
        "cpu_user_pct": float(resource["vmstat_summary"]["avg_cpu_user_pct"]),
        "cpu_system_pct": float(resource["vmstat_summary"]["avg_cpu_system_pct"]),
        "cpu_idle_pct": float(resource["vmstat_summary"]["avg_cpu_idle_pct"]),
        "cpu_wait_pct": float(resource["vmstat_summary"]["avg_cpu_wait_pct"]),
        "quality": quality_paper,
    }


def load_snr_metrics() -> list[dict]:
    snr_report = read_json(SNR_JSON)
    return sorted(snr_report["points"], key=lambda item: item["snr"])


def load_big_little_demo_routes() -> list[dict]:
    rows = []
    for label, path in BIG_LITTLE_3CORE_JSONS.items():
        payload = read_json(path)
        rows.append(
            {
                "route": label,
                "serial_ms": float(payload["serial"]["run_median_ms"]),
                "pipeline_ms": float(payload["pipeline"]["pipeline"]["ms_per_image"]),
                "uplist_pct": float(payload["comparison"]["throughput_uplift_pct"]),
            }
        )
    return rows


def render_snr_curve() -> None:
    apply_style()
    ensure_dir(OUT_SNR)
    points = load_snr_metrics()
    snr = np.array([row["snr"] for row in points], dtype=float)
    latency = np.array([row["run_median_ms"] for row in points], dtype=float)
    psnr = np.array([row["psnr_mean"] for row in points], dtype=float)
    ssim = np.array([row["ssim_mean"] for row in points], dtype=float)

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.5), dpi=240, sharex=True)
    add_header(
        fig,
        "图 4.4 TVM trusted current 的多 SNR 鲁棒性",
        "全部数据来自 `snr_sweep_current_chunk4_20260330_152054.json`。三幅子图共享横轴，分别观察时延、PSNR 与 SSIM 的变化。",
    )
    series = [
        ("端到端中位时间 (ms/image)", latency, COLORS["tvm"], "{:.1f}", 0.0),
        ("PSNR (dB)", psnr, COLORS["pipeline"], "{:.2f}", 0.0),
        ("SSIM", ssim, COLORS["control"], "{:.3f}", 0.0),
    ]
    for ax, (ylabel, values, color, fmt, _) in zip(axes, series):
        ax.plot(snr, values, marker="o", linewidth=2.2, markersize=5.5, color=color)
        ax.fill_between(snr, values, color=color, alpha=0.12)
        ax.set_xlabel("SNR (dB)", fontproperties=FONT, fontsize=10.5)
        ax.set_ylabel(ylabel, fontproperties=FONT, fontsize=10.5)
        ax.set_xticks(snr)
        ax.tick_params(labelsize=9.2)
        for x, y in zip(snr, values):
            ax.text(x, y, fmt.format(y), fontsize=8.7, fontproperties=FONT, color=color, ha="left", va="bottom")
    fig.text(
        0.06,
        0.03,
        "结论：弱网条件下时延基本稳定在 228~234 ms/image，质量则随 SNR 升高单调改善。",
        fontproperties=FONT,
        fontsize=10.0,
        color=COLORS["muted"],
    )
    fig.subplots_adjust(top=0.80, bottom=0.18, left=0.07, right=0.985, wspace=0.30)
    fig.savefig(OUT_SNR, bbox_inches="tight")
    plt.close(fig)


def render_mnn_benchmark() -> None:
    apply_style()
    ensure_dir(OUT_MNN)
    ordered = sorted(MNN_CONFIGS, key=lambda item: item.total_seconds, reverse=True)

    fig, ax = plt.subplots(figsize=(11.2, 5.8), dpi=240)
    add_header(
        fig,
        "图 4.8 MNN 动态尺寸路线关键配置对比",
        "当前仓库没有完整落盘的矩阵原始 JSON，因此这里使用论文正式口径中的 4 组配置结果；横轴主刻度为总耗时，顶轴换算为平均 ms/image。",
    )

    labels = [cfg.label for cfg in ordered]
    totals = [cfg.total_seconds for cfg in ordered]
    colors = [cfg.color for cfg in ordered]
    y = np.arange(len(labels))
    ax.barh(y, totals, color=colors, height=0.58)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontproperties=FONT, fontsize=10.2)
    ax.set_xlabel("300 张总耗时 (s)", fontproperties=FONT, fontsize=10.5)
    ax.set_xlim(0, max(totals) * 1.22)

    def sec_to_ms(value: float) -> float:
        return value * 1000.0 / 300.0

    def ms_to_sec(value: float) -> float:
        return value * 300.0 / 1000.0

    top_ax = ax.secondary_xaxis("top", functions=(sec_to_ms, ms_to_sec))
    top_ax.set_xlabel("平均时间 (ms/image)", fontproperties=FONT, fontsize=10.5)
    top_ax.tick_params(labelsize=9.0)

    best = min(ordered, key=lambda item: item.total_seconds)
    for idx, cfg in enumerate(ordered):
        ax.text(
            cfg.total_seconds + max(totals) * 0.02,
            idx,
            f"{cfg.total_seconds:.1f} s   |   {cfg.avg_ms_per_image:.1f} ms/image",
            va="center",
            ha="left",
            fontproperties=FONT,
            fontsize=9.2,
            color=COLORS["ink"],
            fontweight="bold" if cfg == best else "normal",
        )
        if cfg == best:
            ax.text(
                cfg.total_seconds * 0.60,
                idx,
                "当前正式最优",
                va="center",
                ha="center",
                fontproperties=FONT,
                fontsize=9.2,
                color="#FFFFFF",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS["pipeline"], edgecolor="none"),
            )

    uplift = ordered[0].total_seconds / best.total_seconds
    ax.text(
        0.98,
        0.04,
        f"基线 1I/1T/FP32 -> 正式最优 2I/1T/FP32: {uplift:.2f}x",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontproperties=FONT,
        fontsize=9.8,
        color=COLORS["pipeline"],
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#EEF8F4", edgecolor=COLORS["pipeline"], linewidth=1.0),
    )
    fig.subplots_adjust(top=0.82, bottom=0.12, left=0.21, right=0.97)
    fig.savefig(OUT_MNN, bbox_inches="tight")
    plt.close(fig)


def render_big_little_pipeline() -> None:
    apply_style()
    ensure_dir(OUT_BIG_LITTLE)
    metrics = load_paper_metrics()
    compare_4core = read_json(BIG_LITTLE_4CORE_JSON)
    serial_samples = np.array(compare_4core["serial"]["run_samples_ms"], dtype=float)
    pipeline_samples = np.array(compare_4core["pipeline"]["pipeline"]["run_samples_ms"], dtype=float)
    demo_rows = load_big_little_demo_routes()

    fig = plt.figure(figsize=(13.8, 6.2), dpi=240)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.15])
    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    add_header(
        fig,
        "图 4.9 加入异构大小核流水线性能差异",
        "左图展示 4-core Linux performance mode 下的真实样本分布；右图展示 3-core Linux + RTOS demo mode 下三条路线的 serial-vs-pipeline compare。",
    )

    left_data = [serial_samples, pipeline_samples]
    left_labels = ["串行\n4-core Linux", "流水线\n4-core Linux"]
    box = ax_left.boxplot(
        left_data,
        tick_labels=left_labels,
        patch_artist=True,
        widths=0.55,
        medianprops=dict(color="#FFFFFF", linewidth=2.0),
        showfliers=False,
    )
    for patch, color in zip(box["boxes"], [COLORS["gray"], COLORS["pipeline"]]):
        patch.set_facecolor(color)
        patch.set_alpha(0.92)
        patch.set_edgecolor(color)
    ax_left.set_ylabel("单张时间 (ms/image)", fontproperties=FONT, fontsize=10.5)
    ax_left.tick_params(labelsize=9.4)
    ax_left.text(
        0.03,
        0.95,
        "\n".join(
            [
                f"串行中位: {metrics['serial_median_ms']:.1f} ms",
                f"流水线中位: {metrics['pipeline_median_ms']:.1f} ms",
                f"吞吐: {metrics['serial_ips']:.2f} -> {metrics['pipeline_ips']:.2f} img/s",
                f"总耗时: {metrics['serial_total_s']:.1f} -> {metrics['pipeline_total_s']:.1f} s",
            ]
        ),
        transform=ax_left.transAxes,
        ha="left",
        va="top",
        fontproperties=FONT,
        fontsize=9.0,
        color=COLORS["muted"],
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#F6FAFD", edgecolor=COLORS["grid"]),
    )
    ax_left.set_title("4 核性能模式：分布与吞吐", fontproperties=FONT, fontsize=12.0, loc="left")

    routes = [row["route"] for row in demo_rows]
    serial = np.array([row["serial_ms"] for row in demo_rows], dtype=float)
    pipeline = np.array([row["pipeline_ms"] for row in demo_rows], dtype=float)
    uplift = [row["uplist_pct"] for row in demo_rows]
    x = np.arange(len(routes))
    width = 0.34
    ax_right.bar(x - width / 2, serial, width, color=COLORS["gray"], label="serial")
    ax_right.bar(x + width / 2, pipeline, width, color=COLORS["control"], label="big.LITTLE pipeline")
    ax_right.set_xticks(x)
    ax_right.set_xticklabels(routes, fontproperties=FONT, fontsize=9.4)
    ax_right.set_ylabel("单张时间 (ms/image)", fontproperties=FONT, fontsize=10.5)
    ax_right.set_title("3 核演示模式：三路线对比", fontproperties=FONT, fontsize=12.0, loc="left")
    ax_right.text(
        0.02,
        1.05,
        "● serial",
        transform=ax_right.transAxes,
        ha="left",
        va="bottom",
        fontproperties=FONT,
        fontsize=9.2,
        color=COLORS["gray"],
    )
    ax_right.text(
        0.18,
        1.05,
        "● big.LITTLE pipeline",
        transform=ax_right.transAxes,
        ha="left",
        va="bottom",
        fontproperties=FONT,
        fontsize=9.2,
        color=COLORS["control"],
    )
    for idx, pct in enumerate(uplift):
        top = max(serial[idx], pipeline[idx])
        ax_right.text(
            idx,
            top + 10.0,
            f"+{pct:.1f}%",
            ha="center",
            va="bottom",
            fontproperties=FONT,
            fontsize=9.4,
            color=COLORS["pipeline"],
        )
    fig.text(
        0.06,
        0.03,
        "读图方式：左图回答“4 核性能模式为什么快”，右图回答“3 核演示模式下三条路线的流水线收益是否稳定成立”。",
        fontproperties=FONT,
        fontsize=10.0,
        color=COLORS["muted"],
    )
    fig.subplots_adjust(top=0.80, bottom=0.16, left=0.07, right=0.985, wspace=0.28)
    fig.savefig(OUT_BIG_LITTLE, bbox_inches="tight")
    plt.close(fig)


def render_framework_positioning() -> None:
    apply_style()
    ensure_dir(OUT_FRAMEWORK)

    fig = plt.figure(figsize=(12.8, 7.2), dpi=240)
    add_header(
        fig,
        "图 4.10 双引擎部署定位与端侧性能关系",
        "这张图不再把 TVM 和 MNN 硬拼成一张 benchmark 排名，而是明确展示两条部署路线分别解决什么问题、引用哪些正式结果。",
    )
    ax = fig.add_axes([0.05, 0.12, 0.90, 0.74])
    ax.axis("off")

    top_strip = patches.FancyBboxPatch(
        (0.19, 0.86),
        0.62,
        0.10,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        transform=ax.transAxes,
        facecolor="#F4F8FC",
        edgecolor=COLORS["grid"],
        linewidth=1.2,
    )
    ax.add_patch(top_strip)
    ax.text(0.50, 0.91, "飞腾 Linux 数据面收到 latent 后，按输入形状与部署目标选择引擎", transform=ax.transAxes, ha="center", va="center", fontproperties=FONT, fontsize=10.7, color=COLORS["ink"])

    route_cards = [
        {
            "x": 0.05,
            "color": COLORS["tvm"],
            "title": "TVM fixed-shape performance path",
            "subtitle": "固定形状 256×256 / 已知 artifact / 追求极致性能",
            "metric_main": "230.3 ms/image",
            "metric_sub": "big.LITTLE 流水线可进一步压到 134.6 ms/image",
            "lines": [
                "适合正式性能主口径与多核异构流水线",
                "回答“同尺寸输入下端侧能跑多快”",
                "第 4.1 节与第 4.3 节引用这一条主线",
            ],
        },
        {
            "x": 0.53,
            "color": COLORS["mnn"],
            "title": "MNN mixed-size deployment path",
            "subtitle": "混合尺寸 300 张图像 / 无需预缩放 / 灵活部署",
            "metric_main": "327.3 ms/image",
            "metric_sub": "300 张总耗时 98.2 s，正式最优为 2I / 1T / FP32",
            "lines": [
                "适合 mixed-size 输入与运行时配置 sweep",
                "回答“无需预缩放是否仍可落地”",
                "第 4.2 节引用这一条动态尺寸路线",
            ],
        },
    ]

    for card in route_cards:
        outer = patches.FancyBboxPatch(
            (card["x"], 0.12),
            0.40,
            0.66,
            boxstyle="round,pad=0.016,rounding_size=0.032",
            transform=ax.transAxes,
            facecolor="#FFFFFF",
            edgecolor=COLORS["grid"],
            linewidth=1.25,
        )
        ax.add_patch(outer)
        chip = patches.FancyBboxPatch(
            (card["x"] + 0.025, 0.71),
            0.16,
            0.065,
            boxstyle="round,pad=0.01,rounding_size=0.03",
            transform=ax.transAxes,
            facecolor=card["color"],
            edgecolor="none",
        )
        ax.add_patch(chip)
        ax.text(card["x"] + 0.105, 0.742, "部署路线", transform=ax.transAxes, ha="center", va="center", fontproperties=FONT, fontsize=9.1, color="white")
        ax.text(card["x"] + 0.03, 0.64, card["title"], transform=ax.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=11.2, color=COLORS["ink"], fontweight="bold")
        ax.text(card["x"] + 0.03, 0.58, card["subtitle"], transform=ax.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=9.6, color=COLORS["muted"])

        metric_box = patches.FancyBboxPatch(
            (card["x"] + 0.03, 0.40),
            0.34,
            0.14,
            boxstyle="round,pad=0.012,rounding_size=0.024",
            transform=ax.transAxes,
            facecolor="#F7FBFE",
            edgecolor=COLORS["grid"],
            linewidth=1.0,
        )
        ax.add_patch(metric_box)
        ax.text(card["x"] + 0.05, 0.49, card["metric_main"], transform=ax.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=18.0, color=card["color"], fontweight="bold")
        ax.text(card["x"] + 0.05, 0.43, card["metric_sub"], transform=ax.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=8.9, color=COLORS["muted"])

        for idx, line in enumerate(card["lines"]):
            ax.text(card["x"] + 0.04, 0.31 - idx * 0.08, f"- {line}", transform=ax.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=9.5, color=COLORS["ink"])

    ax.annotate("", xy=(0.25, 0.78), xytext=(0.25, 0.86), xycoords=ax.transAxes, textcoords=ax.transAxes, arrowprops=dict(arrowstyle="-|>", lw=1.4, color=COLORS["tvm"]))
    ax.annotate("", xy=(0.73, 0.78), xytext=(0.73, 0.86), xycoords=ax.transAxes, textcoords=ax.transAxes, arrowprops=dict(arrowstyle="-|>", lw=1.4, color=COLORS["mnn"]))

    foot = patches.FancyBboxPatch(
        (0.05, 0.02),
        0.88,
        0.07,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        transform=ax.transAxes,
        facecolor="#F4F8FC",
        edgecolor=COLORS["grid"],
        linewidth=1.0,
    )
    ax.add_patch(foot)
    ax.text(0.49, 0.055, "结论：TVM 和 MNN 不是同一 deployment regime 下的冠亚军，而是同一系统里的两条可切换执行路线。", transform=ax.transAxes, ha="center", va="center", fontproperties=FONT, fontsize=9.6, color=COLORS["muted"])
    fig.savefig(OUT_FRAMEWORK, bbox_inches="tight")
    plt.close(fig)


def render_perf_quality_tradeoff() -> None:
    apply_style()
    ensure_dir(OUT_TRADEOFF)

    points = [
        ("旧端到端", 1850.0, 34.42, 0.9705, COLORS["gray"]),
        ("TVM 直通", 230.3, 35.66, 0.9728, COLORS["tvm"]),
        ("TVM 流水线", 134.6, 35.66, 0.9728, COLORS["pipeline"]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.0), dpi=240)
    add_header(
        fig,
        "图 4.11 性能-质量权衡图",
        "这里不再放部署概念卡片，而是直接画出真实数据：左图看 latency-PSNR，右图看 latency-SSIM。流水线沿用同一优化产物，因此质量点与 TVM 直通一致。",
    )

    for ax, metric_idx, ylabel in [
        (axes[0], 2, "PSNR (dB)"),
        (axes[1], 3, "SSIM"),
    ]:
        latency = [row[1] for row in points]
        metric = [row[metric_idx] for row in points]
        colors = [row[4] for row in points]
        ax.set_xscale("log")
        for idx, row in enumerate(points):
            ax.scatter(row[1], row[metric_idx], s=78, color=colors[idx], zorder=3)
            ax.text(
                row[1] * 1.05,
                row[metric_idx] + (0.08 if ylabel.startswith("PSNR") else 0.00035),
                row[0],
                fontproperties=FONT,
                fontsize=9.2,
                color=colors[idx],
            )
        ax.plot(latency[:2], metric[:2], color=COLORS["tvm"], linewidth=1.8, alpha=0.9)
        ax.plot(latency[1:], metric[1:], color=COLORS["pipeline"], linewidth=1.8, linestyle="--", alpha=0.9)
        ax.set_xlabel("时间 (ms/image, log scale)", fontproperties=FONT, fontsize=10.2)
        ax.set_ylabel(ylabel, fontproperties=FONT, fontsize=10.2)
        ax.tick_params(labelsize=9.0)
    fig.text(
        0.06,
        0.03,
        "结论：从旧版本到 TVM 直通，系统在大幅降时延的同时没有牺牲质量；big.LITTLE 流水线进一步压低时延，但不改变重建产物本身。",
        fontproperties=FONT,
        fontsize=10.0,
        color=COLORS["muted"],
    )
    fig.subplots_adjust(top=0.80, bottom=0.17, left=0.08, right=0.985, wspace=0.28)
    fig.savefig(OUT_TRADEOFF, bbox_inches="tight")
    plt.close(fig)


def render_performance_ladder() -> None:
    apply_style()
    ensure_dir(OUT_LADDER)
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.0), dpi=240, gridspec_kw={"width_ratios": [1.25, 0.85]})
    add_header(
        fig,
        "图 5.1 系统关键性能跃迁",
        "左图保留固定形状主线的真实收敛路径，右图单列 MNN 动态尺寸路线，避免把 mixed-size benchmark 强行接成同一条单轴故事。",
    )

    tvm_points = [("旧端到端", 1850.0), ("TVM 直通", 230.3), ("TVM 流水线", 134.6)]
    mnn_points = [("MNN 基线", 469.1), ("MNN 正式最优", 327.3)]

    ax = axes[0]
    y = np.arange(len(tvm_points))[::-1]
    x = [value for _, value in tvm_points]
    labels = [label for label, _ in tvm_points]
    ax.plot(x, y, color=COLORS["tvm"], linewidth=2.0)
    ax.scatter(x[0], y[0], color=COLORS["gray"], s=82, zorder=3)
    ax.scatter(x[1], y[1], color=COLORS["tvm"], s=82, zorder=3)
    ax.scatter(x[2], y[2], color=COLORS["pipeline"], s=82, zorder=3)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontproperties=FONT, fontsize=10.0)
    ax.set_xlabel("时间 (ms/image, log scale)", fontproperties=FONT, fontsize=10.2)
    ax.set_title("固定形状 TVM 主线", fontproperties=FONT, fontsize=12.0, loc="left")
    for xi, yi, label in zip(x, y, labels):
        ax.text(xi * 1.05, yi + 0.02, f"{xi:.1f}", fontproperties=FONT, fontsize=9.4, color=COLORS["ink"])
    ax.grid(axis="y", visible=False)

    ax = axes[1]
    y = np.arange(len(mnn_points))[::-1]
    x = [value for _, value in mnn_points]
    labels = [label for label, _ in mnn_points]
    ax.plot(x, y, color=COLORS["mnn"], linewidth=2.0)
    ax.scatter(x[0], y[0], color=COLORS["gray"], s=82, zorder=3)
    ax.scatter(x[1], y[1], color=COLORS["mnn"], s=82, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontproperties=FONT, fontsize=10.0)
    ax.set_xlabel("时间 (ms/image)", fontproperties=FONT, fontsize=10.2)
    ax.set_title("混合尺寸 MNN 路线", fontproperties=FONT, fontsize=12.0, loc="left")
    ax.set_xlim(260, 510)
    for xi, yi in zip(x, y):
        ax.text(xi + 8.0, yi + 0.02, f"{xi:.1f}", fontproperties=FONT, fontsize=9.4, color=COLORS["ink"])
    ax.grid(axis="y", visible=False)
    fig.text(
        0.06,
        0.03,
        "读图方式：左图只讲 fixed-shape TVM 主线收敛，右图只讲 mixed-size MNN 旁路；两者共同服务系统部署，但不混写成同一 apples-to-apples benchmark。",
        fontproperties=FONT,
        fontsize=10.0,
        color=COLORS["muted"],
    )
    fig.subplots_adjust(top=0.76, bottom=0.17, left=0.09, right=0.98, wspace=0.28)
    fig.savefig(OUT_LADDER, bbox_inches="tight")
    plt.close(fig)


def render_tvm_summary() -> None:
    apply_style()
    ensure_dir(OUT_TVM_SUMMARY)
    metrics = load_paper_metrics()
    fig = plt.figure(figsize=(14.2, 8.2), dpi=240)
    gs = fig.add_gridspec(2, 6, height_ratios=[1.0, 1.06], hspace=0.40, wspace=0.34)
    add_header(
        fig,
        "图 4.6 TVM 主线结果总览",
        "把正式结论改成 3+2 布局：上排只放最重要的时间与吞吐，下排分别收口质量/资源与执行边界，减少原来六宫格的碎片感。",
    )

    ax_payload = fig.add_subplot(gs[0, 0:2])
    ax_e2e = fig.add_subplot(gs[0, 2:4])
    ax_ips = fig.add_subplot(gs[0, 4:6])
    ax_quality = fig.add_subplot(gs[1, 0:3])
    ax_boundary = fig.add_subplot(gs[1, 3:6])

    payload_vals = [metrics["payload_baseline_ms"], metrics["payload_current_ms"]]
    ax_payload.hlines(0, payload_vals[1], payload_vals[0], color=COLORS["grid"], linewidth=5.0)
    ax_payload.scatter(payload_vals[0], 0, s=90, color=COLORS["gray"], zorder=3)
    ax_payload.scatter(payload_vals[1], 0, s=90, color=COLORS["tvm"], zorder=3)
    ax_payload.text(payload_vals[0], 0.09, f"baseline\n{payload_vals[0]:.1f} ms", ha="center", va="bottom", fontproperties=FONT, fontsize=9.4, color=COLORS["gray"])
    ax_payload.text(payload_vals[1], -0.13, f"current\n{payload_vals[1]:.1f} ms", ha="center", va="top", fontproperties=FONT, fontsize=9.4, color=COLORS["tvm"])
    ax_payload.text((payload_vals[0] + payload_vals[1]) / 2, 0.02, f"{payload_vals[0] / payload_vals[1]:.1f}x", ha="center", va="bottom", fontproperties=FONT, fontsize=10.0, color=COLORS["tvm"], fontweight="bold")
    ax_payload.set_ylim(-0.28, 0.28)
    ax_payload.set_yticks([])
    ax_payload.set_xlabel("Payload 中位时间 (ms)", fontproperties=FONT, fontsize=10.0)
    ax_payload.set_title("Payload 主指标", fontproperties=FONT, fontsize=12.0, loc="left")

    e2e_vals = [metrics["e2e_baseline_ms"], metrics["e2e_current_ms"], metrics["pipeline_median_ms"]]
    e2e_labels = ["旧端到端", "TVM 直通", "TVM 流水线"]
    e2e_colors = [COLORS["gray"], COLORS["tvm"], COLORS["pipeline"]]
    ax_e2e.bar(e2e_labels, e2e_vals, color=e2e_colors, width=0.60)
    ax_e2e.set_title("端到端正式口径", fontproperties=FONT, fontsize=12.0, loc="left")
    ax_e2e.set_ylabel("ms/image", fontproperties=FONT, fontsize=10.0)
    ax_e2e.tick_params(axis="x", labelrotation=10, labelsize=9.0)
    label_bars(ax_e2e, decimals=1)

    ips_vals = [metrics["serial_ips"], metrics["pipeline_ips"]]
    ax_ips.bar(["serial", "pipeline"], ips_vals, color=[COLORS["gray"], COLORS["pipeline"]], width=0.60)
    ax_ips.set_title("4 核吞吐收益", fontproperties=FONT, fontsize=12.0, loc="left")
    ax_ips.set_ylabel("images/s", fontproperties=FONT, fontsize=10.0)
    label_bars(ax_ips, decimals=2)
    ax_ips.text(
        0.98,
        0.93,
        f"+{metrics['throughput_uplift_pct']:.1f}%",
        transform=ax_ips.transAxes,
        ha="right",
        va="top",
        fontproperties=FONT,
        fontsize=9.2,
        color=COLORS["pipeline"],
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#EEF8F4", edgecolor=COLORS["pipeline"], linewidth=1.0),
    )

    ax_quality.set_title("质量与资源画像", fontproperties=FONT, fontsize=12.0, loc="left")
    ax_quality.axis("off")
    quality_cards = [
        (0.03, COLORS["tvm"], "PSNR", f"{metrics['quality']['baseline_psnr']:.2f} → {metrics['quality']['current_psnr']:.2f} dB"),
        (0.36, COLORS["control"], "SSIM", f"{metrics['quality']['baseline_ssim']:.4f} → {metrics['quality']['current_ssim']:.4f}"),
        (0.69, COLORS["pipeline"], "Artifact", f"{metrics['artifact_mib']:.2f} MiB / min free {metrics['min_free_kb']:,} KB"),
    ]
    for x0, color, title, body in quality_cards:
        rect = patches.FancyBboxPatch(
            (x0, 0.56),
            0.27,
            0.28,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            transform=ax_quality.transAxes,
            facecolor="#FFFFFF",
            edgecolor=COLORS["grid"],
            linewidth=1.1,
        )
        ax_quality.add_patch(rect)
        ax_quality.text(x0 + 0.03, 0.76, title, transform=ax_quality.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=10.0, color=color, fontweight="bold")
        ax_quality.text(x0 + 0.03, 0.64, body, transform=ax_quality.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=9.5, color=COLORS["ink"])

    cpu_box = patches.FancyBboxPatch(
        (0.03, 0.12),
        0.93,
        0.28,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        transform=ax_quality.transAxes,
        facecolor="#F7FBFE",
        edgecolor=COLORS["grid"],
        linewidth=1.0,
    )
    ax_quality.add_patch(cpu_box)
    ax_quality.text(0.05, 0.30, "CPU 画像", transform=ax_quality.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=9.8, color=COLORS["ink"], fontweight="bold")
    ax_quality.text(
        0.05,
        0.19,
        f"user/system/idle/wait = {metrics['cpu_user_pct']:.1f}% / {metrics['cpu_system_pct']:.1f}% / {metrics['cpu_idle_pct']:.1f}% / {metrics['cpu_wait_pct']:.1f}%",
        transform=ax_quality.transAxes,
        ha="left",
        va="center",
        fontproperties=FONT,
        fontsize=9.2,
        color=COLORS["muted"],
    )

    ax_boundary.set_title("执行边界与正式引用条件", fontproperties=FONT, fontsize=12.0, loc="left")
    ax_boundary.axis("off")
    boundary_rows = [
        ("输出完整性", "300 / 300 PNG"),
        ("artifact 校验", "SHA-256 matched"),
        ("性能模式", "4-core Linux"),
        ("信道口径", "SNR = 10, 300 images"),
        ("控制面结论", "另见 OpenAMP / FIT 图组"),
    ]
    for idx, (key, value) in enumerate(boundary_rows):
        y = 0.78 - idx * 0.14
        row_box = patches.FancyBboxPatch(
            (0.03, y - 0.08),
            0.93,
            0.11,
            boxstyle="round,pad=0.01,rounding_size=0.02",
            transform=ax_boundary.transAxes,
            facecolor="#FFFFFF" if idx % 2 == 0 else "#F8FBFD",
            edgecolor=COLORS["grid"],
            linewidth=0.8,
        )
        ax_boundary.add_patch(row_box)
        ax_boundary.text(0.06, y - 0.015, key, transform=ax_boundary.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=9.6, color=COLORS["ink"], fontweight="bold")
        ax_boundary.text(0.58, y - 0.015, value, transform=ax_boundary.transAxes, ha="left", va="center", fontproperties=FONT, fontsize=9.4, color=COLORS["muted"])

    fig.text(
        0.06,
        0.03,
        "这张总览图只汇总 4-core Linux performance mode 下可直接引用的 TVM 主线结论；OpenAMP 控制面和 3 核演示模式结果在别的图里单独报告。",
        fontproperties=FONT,
        fontsize=10.0,
        color=COLORS["muted"],
    )
    fig.subplots_adjust(top=0.84, bottom=0.10, left=0.07, right=0.98)
    fig.savefig(OUT_TVM_SUMMARY, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    render_snr_curve()
    render_tvm_summary()
    render_mnn_benchmark()
    render_big_little_pipeline()
    render_framework_positioning()
    render_performance_ladder()
    print(OUT_SNR)
    print(OUT_TVM_SUMMARY)
    print(OUT_MNN)
    print(OUT_BIG_LITTLE)
    print(OUT_FRAMEWORK)
    print(OUT_LADDER)


if __name__ == "__main__":
    main()
