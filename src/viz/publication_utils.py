"""Publication-grade matplotlib style utilities.

All figures:
  - White background
  - No overlapping content
  - Constrained layout
  - Clean fonts and line widths
  - Legends outside the data area
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import matplotlib
matplotlib.use("Agg")   # non-interactive backend for server/Docker use
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


# ── Style constants ───────────────────────────────────────────────────────────
FONT_FAMILY = "DejaVu Sans"
FONT_SIZE   = 10
TITLE_SIZE  = 11
LABEL_SIZE  = 10
TICK_SIZE   = 9
LINE_WIDTH  = 1.5
COLORS      = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
]


def pub_style() -> None:
    """Apply publication-ready rcParams."""
    plt.rcParams.update({
        "figure.facecolor":  "white",
        "axes.facecolor":    "white",
        "axes.edgecolor":    "#333333",
        "axes.linewidth":    1.0,
        "axes.grid":         True,
        "grid.color":        "#dddddd",
        "grid.linewidth":    0.6,
        "font.family":       FONT_FAMILY,
        "font.size":         FONT_SIZE,
        "axes.titlesize":    TITLE_SIZE,
        "axes.labelsize":    LABEL_SIZE,
        "xtick.labelsize":   TICK_SIZE,
        "ytick.labelsize":   TICK_SIZE,
        "legend.fontsize":   TICK_SIZE,
        "legend.framealpha": 0.9,
        "legend.edgecolor":  "#aaaaaa",
        "lines.linewidth":   LINE_WIDTH,
        "savefig.dpi":       200,
        "savefig.facecolor": "white",
        "savefig.bbox":      "tight",
        "figure.constrained_layout.use": True,
    })


def save_fig(
    fig: Figure,
    path: Path,
    also_pdf: bool = False,
) -> None:
    """Save figure as PNG (and optionally PDF)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, facecolor="white", bbox_inches="tight")
    if also_pdf:
        pdf_path = path.with_suffix(".pdf")
        fig.savefig(pdf_path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def make_fig(
    nrows: int = 1,
    ncols: int = 1,
    figsize: Tuple[float, float] = (6.0, 4.0),
) -> tuple[Figure, object]:
    pub_style()
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize,
                              constrained_layout=True,
                              facecolor="white")
    return fig, axes
