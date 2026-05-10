"""Unified metric computation for a floorplan state.

All metrics are computed from the FloorplanState (macro positions) and
optionally from the DEFInfo (post-OpenROAD output).

Metrics:
  - area_um2          : total die area in µm²
  - core_area_um2     : usable core area in µm²
  - aspect_ratio      : actual W/H of core area
  - aspect_ratio_err  : |actual - target| if target is given
  - overlap_count     : number of pairwise macro overlaps
  - overlap_area_um2  : total overlap area in µm²
  - hpwl_um           : estimated half-perimeter wirelength (from net bounding boxes)
  - density_variance  : variance of per-cell utilization over core area
  - whitespace_frag   : whitespace fragmentation score [0,1]
  - outline_success   : fraction of macros satisfying outline constraint
  - runtime_s         : measured runtime
"""
from __future__ import annotations

import dataclasses
import math
from typing import List, Optional, Tuple

import numpy as np

from src.floorplan.macro_abstraction import FloorplanState, MacroRegion
from src.floorplan.whitespace_control import WhitespaceController
from src.floorplan.fixed_outline import FixedOutlineChecker
from src.data.benchmark_base import NetDef


@dataclasses.dataclass
class FloorplanMetrics:
    design:           str
    method:           str

    # geometry
    area_um2:         float = 0.0
    core_area_um2:    float = 0.0
    aspect_ratio:     float = 1.0
    aspect_ratio_err: float = 0.0

    # overlap
    overlap_count:    int   = 0
    overlap_area_um2: float = 0.0

    # wirelength
    hpwl_um:          float = 0.0

    # density
    density_variance: float = 0.0

    # whitespace
    whitespace_frag:  float = 0.0

    # outline
    outline_success:  float = 1.0

    # runtime
    runtime_s:        float = 0.0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def compute_metrics(
    fp: FloorplanState,
    method: str,
    nets: Optional[List[NetDef]] = None,
    target_aspect_ratio: float = 1.0,
    runtime_s: float = 0.0,
    grid_res: int = 64,
) -> FloorplanMetrics:
    """Compute all metrics from a FloorplanState."""
    core = fp.core_area
    cw = core[2] - core[0]
    ch = core[3] - core[1]

    # Die / core areas — using core as proxy for die here
    die_area = cw * ch
    core_area = cw * ch
    aspect = cw / max(ch, 1e-9)

    # Overlap
    ov_count, ov_area = _compute_overlap(fp.macros)

    # HPWL
    hpwl = _compute_hpwl(fp.macros, nets or [])

    # Density variance
    den_var = _compute_density_variance(fp.macros, core, grid_res)

    # Whitespace fragmentation
    ws = WhitespaceController(core)
    frag = ws.fragmentation_score(fp.macros, grid_res)

    # Outline success
    checker = FixedOutlineChecker(core)
    rpt = checker.check(fp.macros)

    return FloorplanMetrics(
        design           = fp.design,
        method           = method,
        area_um2         = die_area,
        core_area_um2    = core_area,
        aspect_ratio     = aspect,
        aspect_ratio_err = abs(aspect - target_aspect_ratio),
        overlap_count    = ov_count,
        overlap_area_um2 = ov_area,
        hpwl_um          = hpwl,
        density_variance = den_var,
        whitespace_frag  = frag,
        outline_success  = rpt.success_rate,
        runtime_s        = runtime_s,
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _compute_overlap(macros: List[MacroRegion]) -> Tuple[int, float]:
    count = 0
    total_area = 0.0
    for i, a in enumerate(macros):
        for j, b in enumerate(macros):
            if j <= i:
                continue
            if a.overlaps(b):
                count += 1
                ox = max(0.0, min(a.x2, b.x2) - max(a.x, b.x))
                oy = max(0.0, min(a.y2, b.y2) - max(a.y, b.y))
                total_area += ox * oy
    return count, total_area


def _compute_hpwl(macros: List[MacroRegion], nets: List[NetDef]) -> float:
    """Estimate HPWL from net-macro connectivity bounding boxes."""
    if not nets:
        return 0.0

    macro_map = {m.name: m for m in macros}
    total = 0.0
    for net in nets:
        xs, ys = [], []
        for pin in net.pins:
            cell = pin.split("/")[0]
            if cell in macro_map:
                m = macro_map[cell]
                xs.append(m.cx)
                ys.append(m.cy)
        if len(xs) >= 2:
            total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total


def _compute_density_variance(
    macros: List[MacroRegion],
    core: Tuple[float, float, float, float],
    grid_res: int,
) -> float:
    llx, lly, urx, ury = core
    cw = (urx - llx) / grid_res
    ch = (ury - lly) / grid_res
    grid = np.zeros((grid_res, grid_res), dtype=np.float32)
    cell_area = cw * ch

    for m in macros:
        c0 = int((m.x  - llx) / cw)
        c1 = int(math.ceil((m.x2 - llx) / cw))
        r0 = int((m.y  - lly) / ch)
        r1 = int(math.ceil((m.y2 - lly) / ch))
        for r in range(max(0, r0), min(grid_res, r1)):
            for c in range(max(0, c0), min(grid_res, c1)):
                grid[r, c] = min(1.0, grid[r, c] + m.area / (cell_area * (r1 - r0) * (c1 - c0) + 1e-9))

    return float(grid.var())
