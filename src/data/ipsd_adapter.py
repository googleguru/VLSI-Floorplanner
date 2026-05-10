"""IPSD benchmark adapter.

Acquisition steps (must be performed manually before running):
  1. Download ISPD/ICCAD contest benchmark archives from the respective contest pages.
  2. Extract into data/benchmarks/ipsd/<design_name>/
  3. Ensure each design directory contains <design>.lef and <design>.def
  4. Run: python -m src.data.ipsd_adapter --verify  to confirm readiness

File format expected:
  data/benchmarks/ipsd/
    des3/
      des3.lef
      des3.def
    mgc_fft_1/
      mgc_fft_1.lef
      mgc_fft_1.def
    ...
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, List

from .benchmark_base import BenchmarkDesign, SkipReason, SizingMode

log = logging.getLogger(__name__)


class IPSDAdapter:
    @staticmethod
    def load(cfg: dict, repo_root: Path) -> List[BenchmarkDesign]:
        base_dir = repo_root / cfg["base_dir"]
        sizing_mode = SizingMode(cfg.get("sizing_mode", "utilization"))
        designs: List[BenchmarkDesign] = []

        for entry in cfg.get("designs", []):
            name = entry["name"]
            design_dir = base_dir / name

            # Check if the collateral files exist
            lef_path = design_dir / entry.get("lef", f"{name}.lef")
            def_path = design_dir / entry.get("def", f"{name}.def")

            skip: SkipReason | None = None
            if entry.get("skip_reason"):
                skip = SkipReason("MANUAL", entry["skip_reason"])
            elif not lef_path.exists():
                skip = SkipReason("MISSING_LEF",
                    f"LEF not found: {lef_path}. "
                    "Download from ISPD/ICCAD contest archive and place at this path.")
            elif not def_path.exists():
                skip = SkipReason("MISSING_DEF",
                    f"DEF not found: {def_path}. "
                    "Download from ISPD/ICCAD contest archive and place at this path.")

            # Build sizing parameters
            kwargs: dict = {}
            if sizing_mode == SizingMode.UTILIZATION:
                kwargs.update(
                    utilization  = cfg.get("default_utilization", 0.70),
                    aspect_ratio = cfg.get("default_aspect_ratio", 1.0),
                    core_space   = tuple(cfg.get("default_core_space", [2, 2, 2, 2])),
                )
            else:
                kwargs.update(
                    die_area  = tuple(cfg.get("default_die_area",  [0, 0, 500, 500])),
                    core_area = tuple(cfg.get("default_core_area", [10, 10, 490, 490])),
                )

            d = BenchmarkDesign(
                name        = name,
                family      = "ipsd",
                sizing_mode = sizing_mode,
                site        = cfg.get("site", "unit"),
                lef_path    = lef_path if lef_path.exists() else None,
                def_path    = def_path if def_path.exists() else None,
                skip        = skip,
                **kwargs,
            )

            if not skip:
                d.validate_sizing()
                _parse_def_stats(d, def_path)

            designs.append(d)
            status = "READY" if not skip else f"SKIP({skip.code})"
            log.info("IPSD %-30s %s", name, status)

        return designs


def _parse_def_stats(design: BenchmarkDesign, def_path: Path) -> None:
    """Extract macro count and approximate net count from a DEF file (fast scan)."""
    try:
        macros, nets = 0, 0
        with open(def_path) as f:
            for line in f:
                ls = line.strip()
                if ls.startswith("COMPONENTS "):
                    try:
                        design.num_stdcells = int(ls.split()[1])
                    except (IndexError, ValueError):
                        pass
                if ls.startswith("NETS "):
                    try:
                        nets = int(ls.split()[1])
                    except (IndexError, ValueError):
                        pass
    except OSError:
        pass
