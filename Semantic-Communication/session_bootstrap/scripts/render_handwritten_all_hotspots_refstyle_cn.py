#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render all handwritten hotspot candidates as a paper-style bar chart."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "session_bootstrap" / "reports" / "figures"
OUT = FIG_DIR / "paper_fig_handwritten_all_hotspots_delta_refstyle_cn_20260428.png"
FONT_CJK = Path("/home/tianxing/.local/share/fonts/vendor/NotoSerifCJK-Regular.ttc")


C = {
    "text": "#000000",
    "handwritten": "#21618C",
    "good": "#1B9E77",
    "bad": "#B03A2E",
    "missing": "#D5D8DC",
    "grid": "#EAECEF",
    "spine": "#000000",
}

F_SIZE = {
    "title": 9,
    "label": 8,
    "legend": 8,
    "tick": 7,
    "note": 7,
}


# Order follows the 8-op handwritten hotspot shortlist.
# Delta is relative to each lane's own board reference/control.
HOTSPOTS = [
    ("transpose1", "v7", -1.97, "promoted"),
    ("transpose2", "v1", +0.92, "board best"),
    ("transpose_add6", "v1", -0.28, "accepted"),
    ("conv2d3", "v2", +0.62, "dropped"),
    ("mean4", "v7", -1.995, "same-day control"),
    ("variance4", "v18", -0.99, "frozen"),
    ("mean3", "N/A", np.nan, "no board result"),
    ("variance3", "v1", -23.18, "standalone"),
]


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


def render() -> None:
    setup_style()

    labels = [row[0] for row in HOTSPOTS]
    versions = [row[1] for row in HOTSPOTS]
    deltas = np.array([row[2] for row in HOTSPOTS], dtype=float)
    statuses = [row[3] for row in HOTSPOTS]

    x = np.arange(len(HOTSPOTS))
    colors = [C["good"] if np.isfinite(v) and v < 0 else C["bad"] if np.isfinite(v) else C["missing"] for v in deltas]
    heights = np.nan_to_num(deltas, nan=0.0)

    fig, ax = plt.subplots(figsize=(7.16, 3.0), dpi=600)
    fig.suptitle("Handwritten 全热点候选性能变化", fontsize=F_SIZE["title"], fontweight="bold", y=1.02)

    bars = ax.bar(x, heights, width=0.52, color=colors, edgecolor=C["spine"], linewidth=0.6)
    for i, (bar, value, version, status) in enumerate(zip(bars, deltas, versions, statuses)):
        if np.isnan(value):
            bar.set_hatch("//")
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                1.2,
                "N/A",
                ha="center",
                va="bottom",
                fontsize=F_SIZE["tick"],
                fontweight="bold",
                color=C["text"],
            )
            ax.text(
                i,
                -3.2,
                "no board\nresult",
                ha="center",
                va="top",
                fontsize=F_SIZE["note"],
                color=C["text"],
            )
            continue

        y_text = value - 1.15 if value < 0 else value + 0.65
        va = "top" if value < 0 else "bottom"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_text,
            f"{version}\n{value:+.2f}%",
            ha="center",
            va=va,
            fontsize=F_SIZE["tick"],
            fontweight="bold",
            color=colors[i],
            linespacing=1.0,
        )
        if status in {"standalone", "same-day control"}:
            ax.text(
                i,
                6.5,
                status,
                ha="center",
                va="bottom",
                fontsize=F_SIZE["note"],
                color=C["text"],
            )

    ax.axhline(0, color=C["spine"], linewidth=0.9)
    ax.set_ylim(-27, 9)
    ax.set_yticks([-25, -20, -15, -10, -5, 0, 5])
    ax.set_ylabel("Latency delta vs reference/control (%)", fontsize=F_SIZE["label"])
    ax.set_xticks(x)
    ax.set_xticklabels(
        ["transpose1", "transpose2", "transpose\nadd6", "conv2d3", "mean4", "variance4", "mean3", "variance3"],
        fontsize=F_SIZE["tick"],
    )
    ax.set_title("8 个 handwritten hotspot 候选；负值表示加速", fontsize=F_SIZE["title"], pad=8)
    ax.legend(
        handles=[
            Patch(facecolor=C["good"], edgecolor=C["spine"], label="faster"),
            Patch(facecolor=C["bad"], edgecolor=C["spine"], label="slower"),
            Patch(facecolor=C["missing"], edgecolor=C["spine"], hatch="//", label="not measured"),
        ],
        loc="lower left",
        fontsize=F_SIZE["legend"],
        frameon=False,
        ncol=3,
    )
    format_academic_axes(ax)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", dpi=600)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
