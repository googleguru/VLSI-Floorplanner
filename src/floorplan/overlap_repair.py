"""Overlap repair for macro placements.

Uses a greedy push-apart strategy:
  1. Sort macros by area (largest first).
  2. For each overlapping pair, push the smaller macro in the direction
     that minimises displacement, subject to core boundary constraints.
  3. Repeat until no overlaps remain or max_iters is reached.
"""
from __future__ import annotations

import logging
import math
from typing import List, Tuple

from .macro_abstraction import MacroRegion

log = logging.getLogger(__name__)

_MAX_ITERS = 200


class OverlapRepairer:
    """Push-apart overlap elimination."""

    def __init__(
        self,
        core_area: Tuple[float, float, float, float],
        min_gap: float = 0.5,   # µm minimum clearance between macros
        max_iters: int = _MAX_ITERS,
    ) -> None:
        self.llx, self.lly, self.urx, self.ury = core_area
        self.min_gap  = min_gap
        self.max_iters = max_iters

    def repair(self, macros: List[MacroRegion]) -> List[MacroRegion]:
        """Return overlap-free macro list (in-place repair)."""
        fixed   = [m for m in macros if m.fixed]
        movable = [m for m in macros if not m.fixed]

        for iteration in range(self.max_iters):
            overlap_found = False
            all_macros = fixed + movable

            for i, a in enumerate(all_macros):
                for j, b in enumerate(all_macros):
                    if j <= i:
                        continue
                    if not a.overlaps(b, gap=self.min_gap):
                        continue

                    overlap_found = True
                    # Push b away from a (skip if b is fixed)
                    if b.fixed and a.fixed:
                        continue
                    target = b if not b.fixed else a
                    other  = a if target is b else b

                    dx = (target.cx - other.cx)
                    dy = (target.cy - other.cy)
                    dist = math.hypot(dx, dy)

                    if dist < 1e-9:
                        dx, dy = 1.0, 0.0
                        dist = 1.0

                    # Required push distance
                    push_x = (other.width / 2 + target.width / 2 + self.min_gap
                               - abs(target.cx - other.cx))
                    push_y = (other.height / 2 + target.height / 2 + self.min_gap
                               - abs(target.cy - other.cy))

                    # Push along the axis of least resistance
                    if push_x < push_y:
                        target.x += math.copysign(push_x, dx)
                    else:
                        target.y += math.copysign(push_y, dy)

                    # Clamp to core
                    target.x = max(self.llx, min(self.urx - target.width,  target.x))
                    target.y = max(self.lly, min(self.ury - target.height, target.y))

            if not overlap_found:
                log.debug("Overlap repair converged in %d iterations.", iteration + 1)
                break
        else:
            n = self._count_overlaps(fixed + movable)
            if n > 0:
                log.warning("Overlap repair reached max_iters=%d; %d overlaps remain.",
                             self.max_iters, n)

        return fixed + movable

    def _count_overlaps(self, macros: List[MacroRegion]) -> int:
        count = 0
        for i, a in enumerate(macros):
            for j, b in enumerate(macros):
                if j > i and a.overlaps(b, gap=self.min_gap):
                    count += 1
        return count
