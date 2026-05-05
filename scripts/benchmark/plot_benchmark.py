#!/usr/bin/env python3
"""
从 benchmark JSON 生成对比柱状图

  python scripts/plot_benchmark.py scripts/benchmark_results.json
  python scripts/plot_benchmark.py scripts/benchmark_results.json scripts/benchmark_board.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUITE_LABELS = {
    "AES_256_GCM": "AES-256-GCM",
    "SM4_GCM": "SM4-128-GCM",
}
SUITE_COLORS = {
    "AES_256_GCM": "#2563eb",
    "SM4_GCM": "#dc2626",
}
ENV_LABELS = {0: "Local x86 (liboqs)", 1: "Board ARM (Tongsuo)"}
ENV_HATCH = {0: "", 1: "//"}


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def plot_comparison(files: list[str]):
    d_local, d_board = load(files[0]), load(files[1])
    payload_kb = d_local["payload_bytes"] / 1024
    datasets = [d_local, d_board]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    suite_order = ["AES_256_GCM", "SM4_GCM"]

    # ── 1. Per-stage E2E breakdown (grouped by suite, side-by-side env) ──
    ax = axes[0]
    stages = ["handshake", "encrypt", "decrypt"]
    stage_labels = ["Handshake", "Encrypt", "Decrypt"]
    x = np.arange(len(stages))
    n_bars = len(suite_order) * len(datasets)
    width = 0.8 / n_bars

    for si, sn in enumerate(suite_order):
        for di, ds in enumerate(datasets):
            if sn not in ds["suites"]:
                continue
            means = [ds["suites"][sn][k]["mean"] for k in stages]
            stds = [ds["suites"][sn][k]["stdev"] for k in stages]
            idx = si * len(datasets) + di
            env_short = "x86" if di == 0 else "ARM"
            label = f"{SUITE_LABELS[sn]} ({env_short})"
            color = SUITE_COLORS[sn]
            bars = ax.bar(x + idx * width, means, width, label=label,
                          color=color, alpha=0.5 + 0.3 * di,
                          hatch=ENV_HATCH[di],
                          yerr=stds, capsize=2)
            for bar, val in zip(bars, means):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.03,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=6.5)

    ax.set_xlabel("Stage")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"Per-Stage Latency ({payload_kb:.0f}KB)")
    ax.set_xticks(x + width * (n_bars - 1) / 2)
    ax.set_xticklabels(stage_labels)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(axis="y", alpha=0.3)

    # ── 2. E2E latency comparison ──
    ax2 = axes[1]
    x = np.arange(len(suite_order))
    width = 0.30
    for di, ds in enumerate(datasets):
        means = [ds["suites"][s]["e2e"]["mean"] if s in ds["suites"] else 0
                 for s in suite_order]
        stds = [ds["suites"][s]["e2e"]["stdev"] if s in ds["suites"] else 0
                for s in suite_order]
        bars = ax2.bar(x + di * width, means, width,
                       label=ENV_LABELS[di],
                       color=["#2563eb", "#f97316"][di], alpha=0.85,
                       yerr=stds, capsize=3)
        for bar, val in zip(bars, means):
            ax2.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + 0.03,
                     f"{val:.2f}", ha="center", va="bottom", fontsize=8)

    ax2.set_xlabel("Cipher Suite")
    ax2.set_ylabel("Latency (ms)")
    ax2.set_title("E2E Latency")
    ax2.set_xticks(x + width / 2)
    ax2.set_xticklabels([SUITE_LABELS[s] for s in suite_order])
    ax2.legend()
    ax2.grid(axis="y", alpha=0.3)

    # ── 3. Crypto overhead vs TVM inference ──
    ax3 = axes[2]
    tvm_ms = 187.0
    labels_r, values_r, colors_r = [], [], []
    for di, ds in enumerate(datasets):
        env_short = "x86" if di == 0 else "ARM"
        for s in suite_order:
            if s in ds["suites"]:
                labels_r.append(f"{SUITE_LABELS[s]}\n({env_short})")
                values_r.append(ds["suites"][s]["e2e"]["mean"])
                colors_r.append(SUITE_COLORS[s] if di == 0 else "#f97316")
    labels_r.append("TVM\nInference")
    values_r.append(tvm_ms)
    colors_r.append("#16a34a")

    bars = ax3.bar(labels_r, values_r, color=colors_r, alpha=0.85)
    for bar, val in zip(bars, values_r):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{val:.2f} ms", ha="center", va="bottom", fontsize=8)
    for i, val in enumerate(values_r[:-1]):
        pct = val / tvm_ms * 100
        ax3.annotate(f"{pct:.2f}%", xy=(i, val),
                     xytext=(0, -18), textcoords="offset points",
                     ha="center", fontsize=7, fontweight="bold",
                     color=colors_r[i])

    ax3.set_ylabel("Latency (ms)")
    ax3.set_title("Crypto Overhead vs TVM Inference")
    ax3.grid(axis="y", alpha=0.3)

    fig.suptitle("ML-KEM Secure Channel: Local (liboqs) vs Board (Tongsuo)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    out = Path(files[0]).parent / "benchmark_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Chart saved: {out}")


def plot_single(json_path: str):
    data = load(json_path)
    suites = data["suites"]
    payload_kb = data["payload_bytes"] / 1024
    backend = data["backend"]
    keys = ["handshake", "encrypt", "decrypt", "e2e"]
    labels = ["Handshake", "Encrypt", "Decrypt", "E2E"]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))
    width = 0.30
    for i, (sn, sd) in enumerate(suites.items()):
        means = [sd[k]["mean"] for k in keys]
        stds = [sd[k]["stdev"] for k in keys]
        bars = ax.bar(x + i * width, means, width,
                      label=SUITE_LABELS.get(sn, sn),
                      color=SUITE_COLORS.get(sn, "#888"),
                      yerr=stds, capsize=3, alpha=0.85)
        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Stage")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"ML-KEM Benchmark ({backend}, {payload_kb:.0f}KB)")
    ax.set_xticks(x + width * (len(suites) - 1) / 2)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    out = Path(json_path).with_suffix(".png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Chart saved: {out}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        plot_comparison(sys.argv[1:])
    else:
        plot_single(sys.argv[1])
