"""Benchmark comparison and ablation bar charts.

All plots use white background, no overlapping legends,
constrained layout, and consistent color palette.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .publication_utils import pub_style, save_fig, COLORS

log = logging.getLogger(__name__)

_METRICS = {
    "hpwl_um":          ("HPWL (µm)",           "lower"),
    "overlap_count":    ("Overlap Count",         "lower"),
    "density_variance": ("Density Variance",      "lower"),
    "whitespace_frag":  ("Whitespace Frag.",      "lower"),
    "outline_success":  ("Outline Success Rate",  "higher"),
    "runtime_s":        ("Runtime (s)",           "lower"),
}


class ComparisonChartPlotter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_from_csv(self, csv_path: Path, also_pdf: bool = False) -> None:
        """Generate per-metric grouped bar charts from a results CSV."""
        df = pd.read_csv(csv_path)
        methods = sorted(df["method"].unique())
        designs = sorted(df["design"].unique())

        for metric_col, (ylabel, direction) in _METRICS.items():
            if metric_col not in df.columns:
                continue
            self._grouped_bar(
                df, designs, methods, metric_col, ylabel, direction,
                title=f"Benchmark Comparison — {ylabel}",
                filename=f"compare_{metric_col}.png",
                also_pdf=also_pdf,
            )

    def plot_ablation(self, csv_path: Path, also_pdf: bool = False) -> None:
        """Ablation-specific bar chart: methods on X-axis, metric on Y."""
        df = pd.read_csv(csv_path)
        methods = ["baseline", "density_only", "density_connectivity", "full_ca"]
        methods = [m for m in methods if m in df["method"].unique()]

        for metric_col, (ylabel, direction) in _METRICS.items():
            if metric_col not in df.columns:
                continue
            self._ablation_bar(
                df, methods, metric_col, ylabel,
                title=f"Ablation — {ylabel}",
                filename=f"ablation_{metric_col}.png",
                also_pdf=also_pdf,
            )

    def plot_pareto(
        self,
        csv_path: Path,
        x_metric: str = "hpwl_um",
        y_metric: str = "whitespace_frag",
        also_pdf: bool = False,
    ) -> Path:
        df = pd.read_csv(csv_path)
        methods = sorted(df["method"].unique())

        pub_style()
        fig, ax = plt.subplots(1, 1, figsize=(6, 5),
                                facecolor="white", constrained_layout=True)

        for i, method in enumerate(methods):
            sub = df[df["method"] == method]
            ax.scatter(
                sub[x_metric], sub[y_metric],
                label=method, color=COLORS[i % len(COLORS)],
                s=60, alpha=0.8, zorder=3,
            )

        ax.set_xlabel(_METRICS.get(x_metric, (x_metric, ""))[0])
        ax.set_ylabel(_METRICS.get(y_metric, (y_metric, ""))[0])
        ax.set_title("Pareto Scatter")
        ax.legend(loc="upper right", framealpha=0.9,
                  bbox_to_anchor=(1.0, 1.0), fontsize=8)

        out_path = self.output_dir / f"pareto_{x_metric}_vs_{y_metric}.png"
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Pareto plot saved: %s", out_path)
        return out_path

    # ── helpers ───────────────────────────────────────────────────────────────

    def _grouped_bar(
        self, df, designs, methods, metric_col, ylabel, direction,
        title, filename, also_pdf,
    ) -> None:
        pub_style()
        n_designs = len(designs)
        n_methods = len(methods)
        x = np.arange(n_designs)
        width = 0.8 / max(n_methods, 1)

        fig, ax = plt.subplots(1, 1, figsize=(max(6, 1.2 * n_designs), 4.5),
                                facecolor="white", constrained_layout=True)
        for i, method in enumerate(methods):
            vals = []
            for design in designs:
                sub = df[(df["method"] == method) & (df["design"] == design)]
                vals.append(float(sub[metric_col].mean()) if len(sub) else 0.0)
            offset = (i - n_methods / 2 + 0.5) * width
            bars = ax.bar(x + offset, vals, width * 0.9,
                           label=method, color=COLORS[i % len(COLORS)],
                           edgecolor="white")

        ax.set_xticks(x)
        ax.set_xticklabels(designs, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=11)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0),
                  fontsize=8, framealpha=0.9)

        out_path = self.output_dir / filename
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Chart saved: %s", out_path)

    def _ablation_bar(self, df, methods, metric_col, ylabel, title, filename, also_pdf) -> None:
        pub_style()
        vals = [float(df[df["method"] == m][metric_col].mean())
                if m in df["method"].unique() else 0.0
                for m in methods]

        fig, ax = plt.subplots(1, 1, figsize=(6, 4), facecolor="white",
                                constrained_layout=True)
        x = np.arange(len(methods))
        ax.bar(x, vals, color=COLORS[:len(methods)], edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(methods, rotation=20, ha="right", fontsize=9)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=11)

        out_path = self.output_dir / filename
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Ablation chart saved: %s", out_path)
