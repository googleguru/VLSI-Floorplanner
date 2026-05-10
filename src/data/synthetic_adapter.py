"""Synthetic design generator for smoke-testing the pipeline without real benchmarks."""
from __future__ import annotations

import math
import random
from typing import List

import numpy as np

from .benchmark_base import BenchmarkDesign, MacroDef, NetDef, SizingMode


class SyntheticAdapter:
    @staticmethod
    def load(cfg: dict, seed: int = 42) -> List[BenchmarkDesign]:
        designs = []
        for entry in cfg.get("designs", []):
            designs.append(_make_synthetic(entry, seed))
        return designs


def _make_synthetic(entry: dict, seed: int) -> BenchmarkDesign:
    rng = random.Random(seed)
    name         = entry["name"]
    num_macros   = entry.get("num_macros", 4)
    num_stdcells = entry.get("num_stdcells", 500)
    die_area     = tuple(entry.get("die_area",  [0, 0, 200, 200]))
    core_area    = tuple(entry.get("core_area", [5, 5, 195, 195]))
    site         = entry.get("site", "unit")

    cw = core_area[2] - core_area[0]
    ch = core_area[3] - core_area[1]

    # Place macros on a grid inside the core
    cols = math.ceil(math.sqrt(num_macros))
    rows = math.ceil(num_macros / cols)
    macro_w = cw / (cols * 2.5)
    macro_h = ch / (rows * 2.5)

    macros: List[MacroDef] = []
    for i in range(num_macros):
        r, c = divmod(i, cols)
        x = core_area[0] + (c + 0.5) * (cw / cols)
        y = core_area[1] + (r + 0.5) * (ch / rows)
        macros.append(MacroDef(
            name=f"MACRO_{i}", width=macro_w, height=macro_h,
            x=x - macro_w / 2, y=y - macro_h / 2
        ))

    # Generate synthetic nets connecting random macros
    nets: List[NetDef] = []
    macro_names = [m.name for m in macros]
    for i in range(min(num_macros * 3, 50)):
        driver = rng.choice(macro_names)
        sinks  = rng.sample(macro_names, k=min(rng.randint(1, 3), len(macro_names)))
        nets.append(NetDef(name=f"net_{i}", pins=[f"{n}/Q" for n in [driver] + sinks]))

    return BenchmarkDesign(
        name        = name,
        family      = "synthetic",
        sizing_mode = SizingMode.DIE_CORE,
        die_area    = die_area,
        core_area   = core_area,
        site        = site,
        macros      = macros,
        nets        = nets,
        num_stdcells = num_stdcells,
    )
