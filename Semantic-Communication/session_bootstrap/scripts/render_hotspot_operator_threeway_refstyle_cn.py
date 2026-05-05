#!/usr/bin/env python3
"""Render a three-route hotspot-operator latency chart in the 图4.2 style."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
OUT_PNG = FIG_DIR / "paper_fig_hotspot_operator_threeway_refstyle_cn_20260428.png"
OUT_PDF = FIG_DIR / "paper_fig_hotspot_operator_threeway_refstyle_cn_20260428.pdf"
FONT_CJK = Path("/home/tianxing/.local/share/fonts/vendor/NotoSerifCJK-Regular.ttc")


C = {
    "text": "#000000",
    "meta": "#A6ACAF",
    "hand": "#21618C",
    "acl": "#B03A2E",
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


# Source:
# session_bootstrap/reports/fair_singleop_handwritten_vs_acl_under_openamp3_graph_20260404.md
# Section 3, "Graph-Real Per-Op Results", median_duration_us converted to us.
OPS = ["transpose1", "transpose2", "transpose_add6", "variance3", "mean4"]
META_US = np.array([55016, 43912, 40916, 3581, 3102], dtype=float)
HAND_US = np.array([48025, 38701, 34973, 2744, 4548], dtype=float)
ACL_US = np.array([47858, 38599, 35452, 3766, 11254], dtype=float)


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


def format_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(C["spine"])
    ax.spines["bottom"].set_color(C["spine"])
    ax.tick_params(axis="both", which="major", labelsize=F_SIZE["tick"], color=C["spine"])
    ax.yaxis.grid(True, linestyle="--", color=C["grid"], linewidth=0.5)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)


def format_value(value: float) -> str:
    return f"{value / 1000:.1f}k" if value >= 10000 else f"{int(round(value))}"


def label_bars(ax, bars, values: np.ndarray) -> None:
    for bar, value in zip(bars, values):
        lift = 1050 if value >= 10000 else 360
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + lift,
            format_value(value),
            ha="center",
            va="bottom",
            fontsize=F_SIZE["tick"],
            color=C["text"],
        )


def render() -> None:
    setup_style()

    x = np.arange(len(OPS), dtype=float)
    width = 0.23

    fig, ax = plt.subplots(figsize=(7.16, 3.05), dpi=600)
    ax.set_title("Hotspot Operator Latency", fontsize=F_SIZE["title"], fontweight="bold", pad=8)

    meta_bars = ax.bar(
        x - width,
        META_US,
        width,
        color=C["meta"],
        edgecolor=C["spine"],
        linewidth=0.6,
        label="MetaSchedule",
    )
    hand_bars = ax.bar(
        x,
        HAND_US,
        width,
        color=C["hand"],
        edgecolor=C["spine"],
        linewidth=0.6,
        label="Handwritten",
    )
    acl_bars = ax.bar(
        x + width,
        ACL_US,
        width,
        color=C["acl"],
        edgecolor=C["spine"],
        linewidth=0.6,
        label="ACL line",
    )

    label_bars(ax, meta_bars, META_US)
    label_bars(ax, hand_bars, HAND_US)
    label_bars(ax, acl_bars, ACL_US)

    ax.set_ylim(0, 64000)
    ax.set_xlim(-0.55, len(OPS) - 0.45)
    ax.set_ylabel(r"Latency ($\mu$s)", fontsize=F_SIZE["label"])
    ax.set_xticks(x)
    ax.set_xticklabels(
        ["transpose1", "transpose2", "transpose\nadd6", "variance3", "mean4"],
        fontsize=F_SIZE["tick"],
    )
    ax.legend(loc="upper right", fontsize=F_SIZE["legend"], frameon=False, ncol=1)
    format_axes(ax)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, bbox_inches="tight", dpi=600)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    plt.close(fig)

    print(OUT_PNG)
    print(OUT_PDF)


if __name__ == "__main__":
    render()
