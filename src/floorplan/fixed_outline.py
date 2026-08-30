"""Fixed-outline constraint checker and legalization.

Ensures all macros lie within the core area and reports outline violations.
Provides multiple legalization strategies and detailed metrics.
"""
from __future__ import annotations

import dataclasses
import logging
from typing import List, Tuple

from .macro_abstraction import MacroRegion

log = logging.getLogger(__name__)


@dataclasses.dataclass
class OutlineReport:
    violations:     int
    clipped_count:  int
    total_macros:   int
    success_rate:   float   # fraction of macros with no outline violation


@dataclasses.dataclass
class LegalizationMetrics:
    """Detailed metrics for legalization effectiveness."""
    pre_outline_violations:   int
    pre_clipped_macros:       int
    post_outline_violations:  int
    post_clipped_macros:      int
    total_movement_um:        float
    max_displacement_um:      float
    success_rate_before:      float
    success_rate_after:       float


class FixedOutlineChecker:
    def __init__(self, core_area: Tuple[float, float, float, float]) -> None:
        self.llx, self.lly, self.urx, self.ury = core_area
        self.width = self.urx - self.llx
        self.height = self.ury - self.lly

    def check(self, macros: List[MacroRegion]) -> OutlineReport:
        violations = 0
        for m in macros:
            if (m.x < self.llx or m.y < self.lly or
                    m.x2 > self.urx or m.y2 > self.ury):
                violations += 1
        total = len(macros)
        return OutlineReport(
            violations    = violations,
            clipped_count = 0,
            total_macros  = total,
            success_rate  = 1.0 - violations / max(total, 1),
        )

    def legalize(self, macros: List[MacroRegion]) -> List[MacroRegion]:
        """Clip any out-of-bounds macros back inside the core."""
        clipped = 0
        for m in macros:
            orig_x, orig_y = m.x, m.y
            m.x = max(self.llx, min(self.urx - m.width,  m.x))
            m.y = max(self.lly, min(self.ury - m.height, m.y))
            if m.x != orig_x or m.y != orig_y:
                clipped += 1
        return macros

    def legalize_with_metrics(
        self, 
        macros: List[MacroRegion]
    ) -> Tuple[List[MacroRegion], LegalizationMetrics]:
        """Legalize and return detailed metrics on the process."""
        
        # Pre-legalization state
        pre_report = self.check(macros)
        pre_violations = pre_report.violations
        
        # Measure movements
        movements = []
        for m in macros:
            orig_x, orig_y = m.x, m.y
            m.x = max(self.llx, min(self.urx - m.width,  m.x))
            m.y = max(self.lly, min(self.ury - m.height, m.y))
            displacement = ((m.x - orig_x)**2 + (m.y - orig_y)**2)**0.5
            movements.append(displacement)
        
        # Post-legalization state
        post_report = self.check(macros)
        
        # Build metrics
        metrics = LegalizationMetrics(
            pre_outline_violations=pre_violations,
            pre_clipped_macros=sum(1 for orig, move in zip(macros, movements) if move > 0),
            post_outline_violations=post_report.violations,
            post_clipped_macros=post_report.violations,
            total_movement_um=sum(movements),
            max_displacement_um=max(movements) if movements else 0.0,
            success_rate_before=pre_report.success_rate,
            success_rate_after=post_report.success_rate,
        )
        
        log.info(
            "Legalization: pre_violations=%d, post_violations=%d, "
            "total_movement=%.2f µm, max_displacement=%.2f µm",
            metrics.pre_outline_violations,
            metrics.post_outline_violations,
            metrics.total_movement_um,
            metrics.max_displacement_um,
        )
        
        return macros, metrics
