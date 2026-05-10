"""Heatmap renderer for CA grid channels (density, net pressure, affinity)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from src.ca.grid_model import CAGrid, CH_DEN, CH_AFF, CH_NET, CH_BND
from .publication_utils import pub_style, save_fig

log = logging.getLogger(__name__)

_CHANNEL_LABELS = {
    CH_DEN: ("Density",       "YlOrRd"),
    CH_AFF: ("Macro Affinity","Blues"),
    CH_NET: ("Net Pressure",  "Purples"),
    CH_BND: ("Boundary Pres.","Greens"),
}


class HeatmapPlotter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_grid(
        self,
        grid:     CAGrid,
        design:   str,
        suffix:   str = "",
        channels: Optional[list] = None,
        also_pdf: bool = False,
    ) -> Path:
        """Plot up to 4 channels side-by-side."""
        channels = channels or [CH_DEN, CH_AFF, CH_NET, CH_BND]
        n = len(channels)
        pub_style()

        fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 4.0),
                                  facecolor="white", constrained_layout=True)
        if n == 1:
            axes = [axes]

        for ax, ch in zip(axes, channels):
            data = grid.state[:, :, ch]
            label, cmap = _CHANNEL_LABELS.get(ch, (f"Ch{ch}", "viridis"))
            im = ax.imshow(data, origin="lower", cmap=cmap,
                            vmin=0, vmax=1, aspect="equal")
            ax.set_title(label, fontsize=10)
            ax.set_xlabel("Col")
            ax.set_ylabel("Row" if ax is axes[0] else "")
            cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cb.ax.tick_params(labelsize=8)

        fig.suptitle(f"{design} — CA Grid Heatmaps {suffix}".strip(), fontsize=11)

        fname = f"{design}_heatmap{('_' + suffix) if suffix else ''}.png"
        out_path = self.output_dir / fname
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Heatmap saved: %s", out_path)
        return out_path

    def plot_density_evolution(
        self,
        history:  list,   # list of float (mean density per generation)
        design:   str,
        also_pdf: bool = False,
    ) -> Path:
        """Plot density convergence across generations."""
        pub_style()
        fig, ax = plt.subplots(1, 1, figsize=(6, 3.5), facecolor="white",
                                constrained_layout=True)
        ax.plot(history, color="#1f77b4", linewidth=1.5)
        ax.set_xlabel("Generation")
        ax.set_ylabel("Mean Density")
        ax.set_title(f"{design} — Density Convergence", fontsize=11)
        ax.set_ylim(0, 1)

        out_path = self.output_dir / f"{design}_convergence.png"
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Convergence plot saved: %s", out_path)
        return out_path
