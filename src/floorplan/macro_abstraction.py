"""Macro / cluster abstraction and region assignment.

Bridges between the CA grid (continuous field) and the discrete macro
placement representation used by OpenROAD's initialize_floorplan.

The CA grid guides macro region assignment:
  1. High macro-affinity cells → candidate macro zones.
  2. After Rule 235 is applied, the density channel contains clean connected
     regions; these are combined with affinity to form a stronger zone signal.
  3. Macros are assigned to the highest-score zone that fits them.
  4. Overlap repair is applied before emitting final coordinates.
"""
from __future__ import annotations

import dataclasses
import logging
from typing import List, Optional, Tuple

import numpy as np
from scipy.ndimage import label as ndi_label

from src.ca.grid_model import CAGrid, CH_AFF, CH_DEN, CellState
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
    """Assign macros to CA-identified placement zones.

    Zone detection uses a combined signal:
        score = aff_weight * affinity + den_weight * (density > den_threshold)

    When Rule 235 has been run as part of the CA evolution, the density
    channel contains clean connected clusters (isolated islands eliminated,
    gaps filled).  Blending density into the zone signal therefore gives
    the placer direct access to Rule-235-regularised placement regions.
    """

    # Weights for the combined affinity + density zone signal
    AFF_WEIGHT  = 0.65
    DEN_WEIGHT  = 0.35
    DEN_THRESH  = 0.30   # density threshold matching rule_235 default

    def __init__(
        self,
        affinity_threshold: float = 0.4,
        den_threshold: float = DEN_THRESH,
    ) -> None:
        self.affinity_threshold = affinity_threshold
        self.den_threshold      = den_threshold

    def assign(
        self,
        grid: CAGrid,
        macros: List[MacroDef],
        core_area: Tuple[float, float, float, float],
    ) -> List[MacroRegion]:
        """Return macro regions placed according to CA affinity+density field."""
        aff_map = grid.state[:, :, CH_AFF]
        den_map = grid.state[:, :, CH_DEN]

        # Find connected placement zones from combined signal
        zones = self._find_zones(aff_map, den_map)

        placed: List[MacroRegion] = []
        zone_centroids = sorted(
            zones, key=lambda z: z[2], reverse=True
        )   # highest combined score first

        used_zones: set = set()

        for macro in list(macros):
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
                # Fallback: place at core centre
                x = (core_area[0] + core_area[2]) / 2 - macro.width  / 2
                y = (core_area[1] + core_area[3]) / 2 - macro.height / 2
            else:
                _, x, y = best_zone

            placed.append(MacroRegion(
                name=macro.name, x=float(x), y=float(y),
                width=float(macro.width), height=float(macro.height),
                fixed=macro.fixed,
            ))

        log.debug("MacroAssigner placed %d macros into %d zones",
                  len(placed), len(zone_centroids))
        return placed

    def _find_zones(
        self,
        aff_map: np.ndarray,
        den_map: Optional[np.ndarray] = None,
    ) -> List[Tuple[int, int, float]]:
        """Identify high-score connected components; return (row, col, score).

        The combined signal blends affinity with the Rule-235-regularised
        density map so that clean density clusters discovered by Rule 235
        strengthen zone detection even when the affinity field is sparse.
        """
        if den_map is not None:
            den_binary = (den_map >= self.den_threshold).astype(np.float32)
            combined   = (self.AFF_WEIGHT * aff_map
                          + self.DEN_WEIGHT * den_binary)
        else:
            combined = aff_map

        mask = (combined >= self.affinity_threshold).astype(np.int32)
        labeled, n_zones = ndi_label(mask)

        zones = []
        for z in range(1, n_zones + 1):
            zone_mask = labeled == z
            # Score: sum of combined signal within the zone
            score = float(combined[zone_mask].sum())
            rows, cols = np.where(zone_mask)
            cr = int(rows.mean())
            cc = int(cols.mean())
            zones.append((cr, cc, score))

        if not zones:
            # No zones found — fall back to global affinity peak
            peak = np.unravel_index(np.argmax(aff_map), aff_map.shape)
            zones.append((int(peak[0]), int(peak[1]), float(aff_map.max())))
            log.debug("No zones above threshold; using affinity peak as fallback zone.")

        return zones
