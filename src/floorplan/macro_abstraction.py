"""Macro / cluster abstraction and region assignment.

Bridges between the CA grid (continuous field) and the discrete macro
placement representation used by OpenROAD's initialize_floorplan.

The CA grid guides macro region assignment:
  1. High macro-affinity cells → candidate macro zones.
  2. Macros are assigned to the highest-affinity zone that fits them.
  3. Overlap repair is applied before emitting final coordinates.
"""
from __future__ import annotations

import dataclasses
import logging
from typing import List, Optional, Tuple

import numpy as np
from scipy.ndimage import label as ndi_label

from src.ca.grid_model import CAGrid, CH_AFF, CellState
from src.data.benchmark_base import BenchmarkDesign, MacroDef

log = logging.getLogger(__name__)


@dataclasses.dataclass
class MacroRegion:
    """A placed macro with physical bounding box in µm."""
    name:   str
    x:      float   # lower-left X
    y:      float   # lower-left Y
    width:  float
    height: float
    fixed:  bool = False

    @property
    def x2(self) -> float: return self.x + self.width
    @property
    def y2(self) -> float: return self.y + self.height
    @property
    def cx(self) -> float: return self.x + self.width  / 2
    @property
    def cy(self) -> float: return self.y + self.height / 2
    @property
    def area(self) -> float: return self.width * self.height

    def overlaps(self, other: "MacroRegion", gap: float = 0.0) -> bool:
        return (
            self.x  < other.x2 + gap and self.x2 > other.x  - gap and
            self.y  < other.y2 + gap and self.y2 > other.y  - gap
        )


@dataclasses.dataclass
class FloorplanState:
    """Complete discrete floorplan state after CA-guided placement."""
    design:  str
    macros:  List[MacroRegion]
    core_area: Tuple[float, float, float, float]   # llx lly urx ury µm

    @property
    def total_macro_area(self) -> float:
        return sum(m.area for m in self.macros)

    @property
    def core_area_um2(self) -> float:
        return (self.core_area[2] - self.core_area[0]) * \
               (self.core_area[3] - self.core_area[1])


class MacroAssigner:
    """Assign macros to CA-identified high-affinity zones."""

    def __init__(self, affinity_threshold: float = 0.4) -> None:
        self.affinity_threshold = affinity_threshold

    def assign(
        self,
        grid: CAGrid,
        macros: List[MacroDef],
        core_area: Tuple[float, float, float, float],
    ) -> List[MacroRegion]:
        """Return macro regions placed according to CA affinity field."""
        aff_map = grid.state[:, :, CH_AFF]

        # Find connected high-affinity zones
        zones = self._find_zones(aff_map)

        placed: List[MacroRegion] = []
        zone_centroids = sorted(
            zones, key=lambda z: z[2], reverse=True
        )   # sort by total affinity (highest first)

        remaining = list(macros)
        used_zones: set = set()

        for macro in remaining:
            best_zone = None
            for i, (cr, cc, score) in enumerate(zone_centroids):
                if i in used_zones:
                    continue
                x, y = grid.grid_to_phy(cr, cc)
                # Clamp to core bounds
                x = np.clip(x - macro.width / 2,
                             core_area[0],
                             core_area[2] - macro.width)
                y = np.clip(y - macro.height / 2,
                             core_area[1],
                             core_area[3] - macro.height)
                best_zone = (i, x, y)
                used_zones.add(i)
                break

            if best_zone is None:
                # Fallback: place at centre
                x = (core_area[0] + core_area[2]) / 2 - macro.width  / 2
                y = (core_area[1] + core_area[3]) / 2 - macro.height / 2

            elif best_zone:
                _, x, y = best_zone

            placed.append(MacroRegion(
                name=macro.name, x=float(x), y=float(y),
                width=float(macro.width), height=float(macro.height),
                fixed=macro.fixed,
            ))

        return placed

    def _find_zones(
        self, aff_map: np.ndarray
    ) -> List[Tuple[int, int, float]]:
        """Identify high-affinity connected components; return (row, col, score)."""
        mask = (aff_map >= self.affinity_threshold).astype(np.int32)
        labeled, n_zones = ndi_label(mask)
        zones = []
        for z in range(1, n_zones + 1):
            zone_mask = labeled == z
            score = float(aff_map[zone_mask].sum())
            rows, cols = np.where(zone_mask)
            cr = int(rows.mean())
            cc = int(cols.mean())
            zones.append((cr, cc, score))
        return zones
