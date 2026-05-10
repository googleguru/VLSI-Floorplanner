"""Whitespace control: fragmentation metric and compaction utility."""
from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from .macro_abstraction import MacroRegion


class WhitespaceController:
    """Measure and control whitespace fragmentation."""

    def __init__(self, core_area: Tuple[float, float, float, float]) -> None:
        self.llx, self.lly, self.urx, self.ury = core_area
        self.core_w = self.urx - self.llx
        self.core_h = self.ury - self.lly

    def fragmentation_score(
        self,
        macros: List[MacroRegion],
        grid_res: int = 64,
    ) -> float:
        """Compute whitespace fragmentation in [0,1].

        Fragmentation = 1 - (largest_free_rect_area / total_free_area).
        Higher = more fragmented. 0 = single contiguous whitespace region.
        """
        occ = self._rasterise(macros, grid_res)
        free = (occ == 0).astype(np.uint8)
        if free.sum() == 0:
            return 1.0

        # Largest free rectangle via skyline scan
        largest = _max_hist_rect(free)
        total_free = free.sum()
        return float(1.0 - largest / max(total_free, 1))

    def _rasterise(self, macros: List[MacroRegion], res: int) -> np.ndarray:
        """Rasterise macro placements onto a binary occupancy grid."""
        grid = np.zeros((res, res), dtype=np.uint8)
        cw   = self.core_w / res
        ch   = self.core_h / res
        for m in macros:
            c0 = int((m.x  - self.llx) / cw)
            c1 = int(math.ceil((m.x2 - self.llx) / cw))
            r0 = int((m.y  - self.lly) / ch)
            r1 = int(math.ceil((m.y2 - self.lly) / ch))
            grid[
                max(0, r0):min(res, r1),
                max(0, c0):min(res, c1),
            ] = 1
        return grid


def _max_hist_rect(binary_grid: np.ndarray) -> int:
    """Largest rectangle of 1s in a binary grid (histogram method)."""
    rows, cols = binary_grid.shape
    heights = np.zeros(cols, dtype=int)
    max_area = 0
    for r in range(rows):
        heights = np.where(binary_grid[r] == 1, heights + 1, 0)
        max_area = max(max_area, _max_rect_in_hist(heights))
    return max_area


def _max_rect_in_hist(heights: np.ndarray) -> int:
    stack = []
    max_area = 0
    for i, h in enumerate(heights):
        start = i
        while stack and stack[-1][1] > h:
            j, hh = stack.pop()
            max_area = max(max_area, hh * (i - j))
            start = j
        stack.append((start, h))
    for j, h in stack:
        max_area = max(max_area, h * (len(heights) - j))
    return max_area
