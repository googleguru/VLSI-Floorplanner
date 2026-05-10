"""Fixed-outline constraint checker and legalization.

Ensures all macros lie within the core area and reports outline violations.
"""
from __future__ import annotations

import dataclasses
from typing import List, Tuple

from .macro_abstraction import MacroRegion


@dataclasses.dataclass
class OutlineReport:
    violations:     int
    clipped_count:  int
    total_macros:   int
    success_rate:   float   # fraction of macros with no outline violation


class FixedOutlineChecker:
    def __init__(self, core_area: Tuple[float, float, float, float]) -> None:
        self.llx, self.lly, self.urx, self.ury = core_area

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
