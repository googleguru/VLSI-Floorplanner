"""Floorplan snapshot renderer.

Renders a FloorplanState as a publication-ready PNG with:
  - White background
  - Core area boundary
  - Macro rectangles with labels
  - Die area if available
  - No overlapping text
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from src.floorplan.macro_abstraction import FloorplanState
from .publication_utils import pub_style, save_fig

log = logging.getLogger(__name__)

_MACRO_COLOR = "#4472C4"
_CORE_COLOR  = "#2CA02C"


class FloorplanRenderer:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        fp:         FloorplanState,
        title:      str = "",
        die_area:   Optional[Tuple[float, float, float, float]] = None,
        filename:   Optional[str] = None,
        also_pdf:   bool = False,
    ) -> Path:
        pub_style()
        fig, ax = plt.subplots(1, 1, figsize=(6, 6), facecolor="white",
                                constrained_layout=True)
        ax.set_facecolor("white")

        core = fp.core_area
        # Core outline
        cw = core[2] - core[0]
        ch = core[3] - core[1]
        core_rect = mpatches.Rectangle(
            (core[0], core[1]), cw, ch,
            linewidth=1.5, edgecolor=_CORE_COLOR, facecolor="#f0f8f0",
            label="Core area", zorder=1,
        )
        ax.add_patch(core_rect)

        if die_area:
            dw = die_area[2] - die_area[0]
            dh = die_area[3] - die_area[1]
            die_rect = mpatches.Rectangle(
                (die_area[0], die_area[1]), dw, dh,
                linewidth=1.0, edgecolor="#888888", facecolor="none",
                linestyle="--", label="Die area", zorder=1,
            )
            ax.add_patch(die_rect)

        # Macro rectangles
        for macro in fp.macros:
            rect = mpatches.Rectangle(
                (macro.x, macro.y), macro.width, macro.height,
                linewidth=1.0, edgecolor="white",
                facecolor=_MACRO_COLOR, alpha=0.85, zorder=2,
            )
            ax.add_patch(rect)

            # Label — only if macro is large enough to label
            if macro.width > cw * 0.03 and macro.height > ch * 0.03:
                ax.text(
                    macro.cx, macro.cy, macro.name,
                    ha="center", va="center", fontsize=6,
                    color="white", zorder=3,
                    clip_on=True,
                )

        ax.set_xlim(core[0] - cw * 0.05, core[2] + cw * 0.05)
        ax.set_ylim(core[1] - ch * 0.05, core[3] + ch * 0.05)
        ax.set_aspect("equal")
        ax.set_xlabel("X (µm)")
        ax.set_ylabel("Y (µm)")
        ax.set_title(title or fp.design, fontsize=11, pad=6)
        ax.legend(loc="upper right", fontsize=8)

        out_name = filename or f"{fp.design}_floorplan.png"
        out_path = self.output_dir / out_name
        save_fig(fig, out_path, also_pdf=also_pdf)
        log.info("Floorplan figure saved: %s", out_path)
        return out_path
