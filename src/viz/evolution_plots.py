"""CA evolution phase snapshot plotter.

Produces a multi-panel figure showing occupancy and density maps at the
end of each CA phase, for visual inspection of convergence quality.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from src.ca.grid_model import CAGrid, CH_OCC, CH_DEN
from src.ca.evolution_scheduler import EvolutionRecord
from .publication_utils import pub_style, save_fig

log = logging.getLogger(__name__)


class EvolutionPlotter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_phase_snapshots(
        self,
        snapshots:   List[Tuple[str, CAGrid]],   # (phase_name, grid)
        design:      str,
        also_pdf:    bool = False,
    ) -> Path:
        n = len(snapshots)
        if n == 0:
            return self.output_dir / f"{design}_evolution.png"

        pub_style()
        fig, axes = plt.subplots(
            2, n, figsize=(3.5 * n, 6.0),
            facecolor="white", constrained_layout=True,
        )
        if n == 1:
            axes = np.array([axes]).T

        for col, (pname, grid) in enumerate(snapshots):
            occ = grid.state[:, :, CH_OCC]
            den = grid.state[:, :, CH_DEN]

            ax_occ = axes[0, col]
            ax_den = axes[1, col]

            im0 = ax_occ.imshow(occ, origin="lower", cmap="tab10",
                                 vmin=0, vmax=3, aspect="equal")
            ax_occ.set_title(pname, fontsize=9)
            ax_occ.set_xlabel("Col")
            if col == 0:
                ax_occ.set_ylabel("Occupancy")

            im1 = ax_den.imshow(den, origin="lower", cmap="YlOrRd",
                                 vmin=0, vmax=1, aspect="equal")
            ax_den.set_xlabel("Col")
            if col == 0:
                ax_den.set_ylabel("Density")

        fig.suptitle(f"{design} — Phase Evolution", fontsize=11)

        out_path = self.output_dir / f"{design}_phase_evolution.png"
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Evolution plot saved: %s", out_path)
        return out_path

    def plot_phase_timeline(
        self,
        record: EvolutionRecord,
        design: str,
        also_pdf: bool = False,
    ) -> Path:
        pub_style()
        phases = record.phases
        names    = [p.name for p in phases]
        runtimes = [p.runtime_s for p in phases]
        gens     = [p.generations for p in phases]

        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(9, 3.5),
            facecolor="white", constrained_layout=True,
        )

        x = range(len(phases))
        ax1.bar(x, runtimes, color="#4472C4", edgecolor="white")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(names, rotation=30, ha="right")
        ax1.set_ylabel("Runtime (s)")
        ax1.set_title("Phase Runtime")

        ax2.bar(x, gens, color="#ED7D31", edgecolor="white")
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(names, rotation=30, ha="right")
        ax2.set_ylabel("Generations")
        ax2.set_title("Phase Generations")

        fig.suptitle(f"{design} — Phase Timeline", fontsize=11)
        out_path = self.output_dir / f"{design}_phase_timeline.png"
        save_fig(fig, out_path, also_pdf=also_pdf)
        return out_path
