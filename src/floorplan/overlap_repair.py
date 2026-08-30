"""Overlap repair for macro placements.

Implements multiple strategies:
  1. Greedy push-apart: Sort macros by area; push apart pairwise.
  2. Min-cost displacement: Find optimal solution minimizing total movement.
  3. Tetris-style legalization: Place macros in order, fitting each into
     remaining space (for smaller problems).

Strategies are attempted in order of sophistication until convergence.
"""
from __future__ import annotations

import logging
import math
from typing import List, Tuple, Optional

from .macro_abstraction import MacroRegion

log = logging.getLogger(__name__)

_MAX_ITERS = 200


class OverlapRepairer:
    """Multi-strategy overlap elimination with legalization."""

    def __init__(
        self,
        core_area: Tuple[float, float, float, float],
        min_gap: float = 0.5,   # µm minimum clearance between macros
        max_iters: int = _MAX_ITERS,
    ) -> None:
        self.llx, self.lly, self.urx, self.ury = core_area
        self.min_gap  = min_gap
        self.max_iters = max_iters
        self.core_width = self.urx - self.llx
        self.core_height = self.ury - self.lly

    def repair(self, macros: List[MacroRegion]) -> List[MacroRegion]:
        """Return overlap-free macro list using multi-stage repair."""
        if not macros:
            return macros

        # Stage 1: Greedy push-apart (fast, often sufficient)
        macros_copy = [MacroRegion(
            name=m.name, x=m.x, y=m.y, width=m.width, height=m.height, fixed=m.fixed
        ) for m in macros]
        
        overlap_count = self._count_overlaps(macros_copy)
        if overlap_count == 0:
            return macros_copy

        log.debug("Starting overlap repair: %d overlaps detected.", overlap_count)

        # Try greedy push-apart first
        macros_repaired = self._greedy_push_apart(macros_copy)
        remaining = self._count_overlaps(macros_repaired)
        log.debug("After greedy push-apart: %d overlaps remain.", remaining)

        # Stage 2: If still overlaps, try minimum-displacement optimization
        if remaining > 0:
            macros_repaired = self._min_displacement_repair(macros_repaired)
            remaining = self._count_overlaps(macros_repaired)
            log.debug("After min-displacement: %d overlaps remain.", remaining)

        # Stage 3: Last resort - Tetris-style (only if small number of macros)
        if remaining > 0 and len(macros) <= 32:
            macros_repaired = self._tetris_legalize(macros_repaired)
            remaining = self._count_overlaps(macros_repaired)
            log.debug("After Tetris legalization: %d overlaps remain.", remaining)

        if remaining > 0:
            log.warning("Overlap repair: %d overlaps remain after all strategies.",
                        remaining)

        return macros_repaired

    def _greedy_push_apart(self, macros: List[MacroRegion]) -> List[MacroRegion]:
        """Classic greedy push-apart strategy."""
        fixed   = [m for m in macros if m.fixed]
        movable = [m for m in macros if not m.fixed]
        
        # Sort movable by area (largest first)
        movable.sort(key=lambda m: m.area, reverse=True)

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
                    
                    # Skip if both are fixed
                    if a.fixed and b.fixed:
                        continue

                    # Determine which to move
                    if a.fixed and not b.fixed:
                        target, other = b, a
                    elif b.fixed and not a.fixed:
                        target, other = a, b
                    else:
                        # Both movable: move smaller one
                        if a.area <= b.area:
                            target, other = a, b
                        else:
                            target, other = b, a

                    # Calculate push direction
                    dx = target.cx - other.cx
                    dy = target.cy - other.cy
                    dist = math.hypot(dx, dy)

                    if dist < 1e-9:
                        dx, dy = 1.0, 0.0
                        dist = 1.0

                    # Required minimum separation
                    min_sep_x = (other.width + target.width) / 2.0 + self.min_gap
                    min_sep_y = (other.height + target.height) / 2.0 + self.min_gap

                    # How much to push in each direction
                    push_x = min_sep_x - abs(dx)
                    push_y = min_sep_y - abs(dy)

                    # Push along axis of least resistance
                    if push_x < push_y:
                        target.x += math.copysign(max(push_x, 0.1), dx)
                    else:
                        target.y += math.copysign(max(push_y, 0.1), dy)

                    # Clamp to core boundaries
                    self._clamp_to_core(target)

            if not overlap_found:
                log.debug("Greedy push-apart converged in %d iterations.",
                          iteration + 1)
                break

        return fixed + movable

    def _min_displacement_repair(self, macros: List[MacroRegion]) -> List[MacroRegion]:
        """Iteratively resolve overlaps by min-cost displacement."""
        fixed = [m for m in macros if m.fixed]
        movable = [m for m in macros if not m.fixed]
        
        for iteration in range(self.max_iters // 2):
            pairs = self._find_overlapping_pairs(fixed + movable)
            if not pairs:
                break

            # For each overlapping pair, find best resolution direction
            for a, b in pairs:
                if a.fixed and b.fixed:
                    continue

                target = b if not b.fixed else a
                other = a if target is b else b

                # Try 4 cardinal directions, pick one with min total boundary violations
                candidates = [
                    (target.x + 5.0, target.y, "E"),
                    (target.x - 5.0, target.y, "W"),
                    (target.x, target.y + 5.0, "N"),
                    (target.x, target.y - 5.0, "S"),
                ]

                best_cost = float("inf")
                best_pos = (target.x, target.y)

                for cx, cy, _ in candidates:
                    cx = max(self.llx, min(self.urx - target.width, cx))
                    cy = max(self.lly, min(self.ury - target.height, cy))
                    
                    # Cost = distance moved + boundary penalty
                    dist_cost = abs(cx - target.x) + abs(cy - target.y)
                    boundary_penalty = 0.0
                    if cx < self.llx or cx + target.width > self.urx:
                        boundary_penalty += 100.0
                    if cy < self.lly or cy + target.height > self.ury:
                        boundary_penalty += 100.0

                    total_cost = dist_cost + boundary_penalty
                    if total_cost < best_cost:
                        best_cost = total_cost
                        best_pos = (cx, cy)

                target.x, target.y = best_pos

        return fixed + movable

    def _tetris_legalize(self, macros: List[MacroRegion]) -> List[MacroRegion]:
        """Tetris-style legalization: place macros sequentially into remaining space."""
        fixed = [m for m in macros if m.fixed]
        movable = [m for m in macros if not m.fixed]
        
        # Sort by size for better packing
        movable.sort(key=lambda m: m.width * m.height, reverse=True)

        # Place each macro into the lowest valid position (bottom-left priority)
        for macro in movable:
            best_y = self.lly
            best_x = self.llx
            best_cost = float("inf")

            # Grid search for placement
            step = max(1.0, min(macro.width, macro.height) / 2.0)
            for try_x in self._frange(self.llx, self.urx - macro.width, step):
                for try_y in self._frange(self.lly, self.ury - macro.height, step):
                    # Check if position is valid (no overlap with fixed or already-placed)
                    test_macro = MacroRegion(
                        name="test", x=try_x, y=try_y,
                        width=macro.width, height=macro.height
                    )
                    
                    is_valid = True
                    for other in fixed + movable:
                        if other is macro:
                            continue
                        if test_macro.overlaps(other, gap=self.min_gap):
                            is_valid = False
                            break

                    if is_valid:
                        # Prefer lower positions (bottom), then leftmost
                        cost = try_y + try_x * 0.01
                        if cost < best_cost:
                            best_cost = cost
                            best_x, best_y = try_x, try_y

            if best_cost != float("inf"):
                macro.x = best_x
                macro.y = best_y

        return fixed + movable

    def _find_overlapping_pairs(self, macros: List[MacroRegion]) -> List[Tuple[MacroRegion, MacroRegion]]:
        """Return list of overlapping macro pairs."""
        pairs = []
        for i, a in enumerate(macros):
            for j, b in enumerate(macros):
                if i < j and a.overlaps(b, gap=self.min_gap):
                    pairs.append((a, b))
        return pairs

    def _clamp_to_core(self, macro: MacroRegion) -> None:
        """Clamp macro coordinates to core boundaries."""
        macro.x = max(self.llx, min(self.urx - macro.width, macro.x))
        macro.y = max(self.lly, min(self.ury - macro.height, macro.y))

    def _count_overlaps(self, macros: List[MacroRegion]) -> int:
        """Count number of overlapping pairs."""
        count = 0
        for i, a in enumerate(macros):
            for j, b in enumerate(macros):
                if j > i and a.overlaps(b, gap=self.min_gap):
                    count += 1
        return count

    @staticmethod
    def _frange(start: float, end: float, step: float):
        """Range generator for floats."""
        current = start
        while current < end:
            yield current
            current += step
