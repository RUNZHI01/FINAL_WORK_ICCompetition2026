#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the route/hotspot comparison in the paper style used by 图4.2."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
OUT_COMBINED = FIG_DIR / "paper_fig_serial_reconstruction_hotspots_refstyle_cn_20260428.png"
OUT_OPERATOR = FIG_DIR / "paper_fig_operator_latency_refstyle_cn_20260428.png"
FONT_CJK = Path("/home/tianxing/.local/share/fonts/vendor/NotoSerifCJK-Regular.ttc")


C = {
    "text": "#000000",
    "baseline": "#A6ACAF",
    "handwritten": "#21618C",
    "acl": "#B03A2E",
    "highlight": "#1B9E77",
    "grid": "#EAECEF",
    "spine": "#000000",
}

F_SIZE = {
    "title": 8.5,
    "label": 7,
    "legend": 7,
    "tick": 6,
    "note": 6,
}


SERIAL_ROUTES = [
    ("MetaSchedule", 347.341, C["baseline"]),
    ("Handwritten\nv7", 345.609, C["handwritten"]),
    ("ACL\nline", 352.158, C["acl"]),
]

# Graph-real per-op profile values from the 2026-04-04/04-06 reports, in us.
OPS = ["transpose1", "transpose2", "transpose_add6", "variance3", "mean4"]
METASCHEDULE_US = np.array([55016, 43912, 40916, 3581, 3102], dtype=float)
HANDWRITTEN_US = np.array([48249, 39143, 34790, 2736, 4648], dtype=float)
ACL_LINE_US = np.array([np.nan, np.nan, np.nan, np.nan, 11178], dtype=float)


def setup_style() -> None:
    font_family = ["DejaVu Serif", "serif"]
    if FONT_CJK.is_file():
        font_manager.fontManager.addfont(str(FONT_CJK))
        font_family.insert(0, font_manager.FontProperties(fname=str(FONT_CJK)).get_name())

    plt.rcParams.update(
        {
            "font.family": font_family,
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.linewidth": 0.75,
            "xtick.major.width": 0.75,
            "ytick.major.width": 0.75,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def format_academic_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(C["spine"])
    ax.spines["bottom"].set_color(C["spine"])
    ax.tick_params(axis="both", which="major", labelsize=F_SIZE["tick"], color=C["spine"])
    ax.yaxis.grid(True, linestyle="--", color=C["grid"], linewidth=0.5)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)


def draw_span_bracket(ax, x_left: float, x_right: float, y_height: float, text: str, color: str, tick_len: float) -> None:
    ax.plot([x_left, x_right], [y_height, y_height], color=color, lw=1.0, clip_on=False)
    ax.plot([x_left, x_left], [y_height - tick_len, y_height], color=color, lw=1.0, clip_on=False)
    ax.plot([x_right, x_right], [y_height - tick_len, y_height], color=color, lw=1.0, clip_on=False)
    ax.text(
        (x_left + x_right) / 2,
        y_height + tick_len * 0.45,
        text,
        ha="center",
        va="bottom",
        fontsize=F_SIZE["note"],
        fontweight="bold",
        color=color,
        clip_on=False,
    )


def draw_serial_panel(ax) -> None:
    x = np.arange(len(SERIAL_ROUTES))
    values = [item[1] for item in SERIAL_ROUTES]
    colors = [item[2] for item in SERIAL_ROUTES]
    labels = [item[0] for item in SERIAL_ROUTES]

    bars = ax.bar(x, values, width=0.46, color=colors, edgecolor=C["spine"], linewidth=0.6)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 5,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=F_SIZE["tick"],
            fontweight="bold",
            color=C["text"],
        )

    hand_vs_meta = (values[0] - values[1]) / values[0] * 100.0
    hand_vs_acl = (values[2] - values[1]) / values[2] * 100.0
    draw_span_bracket(ax, x[0], x[1], 370, f"+{hand_vs_meta:.1f}%", C["highlight"], tick_len=7)
    draw_span_bracket(ax, x[1], x[2], 386, f"+{hand_vs_acl:.1f}%", C["highlight"], tick_len=7)

    ax.set_ylim(0, 410)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=F_SIZE["tick"])
    ax.set_ylabel("Latency (ms/image)", fontsize=F_SIZE["label"])
    ax.set_title("(a) Serial Reconstruction Median", fontsize=F_SIZE["title"], pad=8)
    format_academic_axes(ax)


def draw_operator_panel(ax, show_ylabel: bool = True, title: str = "(b) 关键算子性能路线对比") -> None:
    x = np.arange(len(OPS))
    width = 0.23

    ax.bar(
        x - width,
        METASCHEDULE_US,
        width,
        color=C["baseline"],
        edgecolor=C["spine"],
        linewidth=0.6,
        label="MetaSchedule",
    )
    ax.bar(
        x,
        HANDWRITTEN_US,
        width,
        color=C["handwritten"],
        edgecolor=C["spine"],
        linewidth=0.6,
        label="Handwritten",
    )
    acl_mask = ~np.isnan(ACL_LINE_US)
    ax.bar(
        x + width,
        np.nan_to_num(ACL_LINE_US, nan=0.0),
        width,
        color=C["acl"],
        edgecolor=C["spine"],
        linewidth=0.6,
        label="ACL",
    )
    for patch, visible in zip(ax.containers[-1].patches, acl_mask):
        if not visible:
            patch.set_visible(False)

    series = [
        (x - width, METASCHEDULE_US, C["text"], "right", -0.015),
        (x, HANDWRITTEN_US, C["text"], "left", 0.015),
        (x + width, ACL_LINE_US, C["text"], "center", 0.0),
    ]
    for xs, values, color, ha, dx in series:
        for xpos, value in zip(xs, values):
            if np.isnan(value):
                continue
            lift = 1000 if value > 12000 else 260
            ax.text(
                xpos + dx,
                value + lift,
                f"{int(round(value))}",
                ha=ha,
                va="bottom",
                fontsize=F_SIZE["tick"],
                color=color,
            )

    for i, (base, hand) in enumerate(zip(METASCHEDULE_US, HANDWRITTEN_US)):
        improvement = (base - hand) / base * 100.0
        color = C["highlight"] if improvement >= 0 else C["acl"]
        bracket_y = max(base, hand) + (6000 if max(base, hand) > 12000 else 2500)
        tick_len = 1500 if max(base, hand) > 12000 else 550
        draw_span_bracket(ax, x[i] - width, x[i], bracket_y, f"{improvement:+.1f}%", color, tick_len=tick_len)

    ax.set_ylim(0, 72000)
    tick_positions = [x[i] if acl_mask[i] else x[i] - width / 2 for i in range(len(OPS))]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(["transpose1", "transpose2", "transpose\nadd6", "variance3", "mean4"], fontsize=F_SIZE["tick"])
    if show_ylabel:
        ax.set_ylabel("Latency (μs)", fontsize=F_SIZE["label"])
    ax.set_title(title, fontsize=F_SIZE["title"], pad=8)
    ax.legend(loc="upper right", fontsize=F_SIZE["legend"], frameon=False)
    format_academic_axes(ax)


def render_combined() -> None:
    setup_style()
    fig = plt.figure(figsize=(8.8, 3.2), dpi=600)
    gs = fig.add_gridspec(1, 2, width_ratios=[0.9, 1.75], wspace=0.24)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    fig.suptitle("三条路线 Serial Reconstruction 与热点算子性能对比", fontsize=F_SIZE["title"], fontweight="bold", y=1.02)
    draw_serial_panel(ax1)
    draw_operator_panel(ax2)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_COMBINED, bbox_inches="tight", dpi=600)
    plt.close(fig)


def render_operator_only() -> None:
    setup_style()
    fig, ax = plt.subplots(figsize=(7.16, 3.1), dpi=600)
    fig.suptitle("关键算子性能路线对比", fontsize=F_SIZE["title"], fontweight="bold", y=1.02)
    draw_operator_panel(ax, title="关键算子性能路线对比")
    fig.savefig(OUT_OPERATOR, bbox_inches="tight", dpi=600)
    plt.close(fig)


def main() -> None:
    render_combined()
    render_operator_only()
    print(OUT_COMBINED)
    print(OUT_OPERATOR)


if __name__ == "__main__":
    main()
