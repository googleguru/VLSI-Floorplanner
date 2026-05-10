"""ISCAS-85/89 benchmark adapter.

Pipeline for converting ISCAS .bench netlists to floorplan-ready DEF:
  Step 1  bench2blif   – convert ISCAS .bench → BLIF (included utility)
  Step 2  yosys        – technology-map BLIF to a target cell library
  Step 3  openroad     – read mapped netlist → write DEF (floorplan placeholder)

If Yosys or the target library is unavailable, designs are marked SKIPPED
with acquisition instructions.

Acquisition:
  1. ISCAS-85 benchmarks: https://www.pld.ttu.ee/~maksim/benchmarks/iscas85/bench/
  2. ISCAS-89 benchmarks: https://www.pld.ttu.ee/~maksim/benchmarks/iscas89/bench/
  3. Place .bench files in data/benchmarks/iscas/<name>/<name>.bench
  4. Install Yosys: apt-get install yosys  (or build from source)
  5. Run: python -m src.data.iscas_adapter --prepare  to generate DEF stubs
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List

from .benchmark_base import BenchmarkDesign, SkipReason, SizingMode

log = logging.getLogger(__name__)

_YOSYS_AVAILABLE = shutil.which("yosys") is not None


class ISCASAdapter:
    @staticmethod
    def load(cfg: dict, repo_root: Path) -> List[BenchmarkDesign]:
        base_dir = repo_root / cfg["base_dir"]
        sizing_mode = SizingMode(cfg.get("sizing_mode", "die_core"))
        designs: List[BenchmarkDesign] = []

        for entry in cfg.get("designs", []):
            name  = entry["name"]
            bench_file = base_dir / name / entry.get("bench", f"{name}.bench")
            def_path   = base_dir / name / f"{name}.def"
            lef_path   = base_dir / name / f"{name}.lef"

            skip: SkipReason | None = None

            if entry.get("skip_reason"):
                skip = SkipReason("MANUAL", entry["skip_reason"])
            elif not bench_file.exists():
                skip = SkipReason("MISSING_BENCH",
                    f".bench not found: {bench_file}. "
                    "Download from https://www.pld.ttu.ee/~maksim/benchmarks/ "
                    "and place at this path.")
            elif not _YOSYS_AVAILABLE:
                skip = SkipReason("NO_YOSYS",
                    "Yosys not found on PATH. Install with: apt-get install yosys. "
                    "Yosys is required to technology-map ISCAS netlists.")
            elif not def_path.exists():
                # Attempt pipeline conversion
                ok = _run_iscas_pipeline(name, bench_file, def_path, lef_path)
                if not ok:
                    skip = SkipReason("PIPELINE_FAILED",
                        f"ISCAS conversion pipeline failed for {name}. "
                        "See logs for details. Run with --prepare to retry.")

            kwargs: dict = {}
            if sizing_mode == SizingMode.DIE_CORE:
                kwargs.update(
                    die_area  = tuple(cfg.get("default_die_area",  [0, 0, 500, 500])),
                    core_area = tuple(cfg.get("default_core_area", [10, 10, 490, 490])),
                )
            else:
                kwargs.update(
                    utilization  = cfg.get("default_utilization", 0.70),
                    aspect_ratio = cfg.get("default_aspect_ratio", 1.0),
                    core_space   = tuple(cfg.get("default_core_space", [2, 2, 2, 2])),
                )

            d = BenchmarkDesign(
                name        = name,
                family      = "iscas",
                sizing_mode = sizing_mode,
                site        = cfg.get("site", "unit"),
                lef_path    = lef_path if lef_path.exists() else None,
                def_path    = def_path if def_path.exists() else None,
                skip        = skip,
                **kwargs,
            )

            if not skip:
                d.validate_sizing()

            designs.append(d)
            status = "READY" if not skip else f"SKIP({skip.code})"
            log.info("ISCAS %-30s %s", name, status)

        return designs


def _run_iscas_pipeline(name: str, bench: Path, def_out: Path, lef_out: Path) -> bool:
    """Convert .bench → DEF via bench2blif + Yosys stub generation."""
    try:
        def_out.parent.mkdir(parents=True, exist_ok=True)
        blif_path = bench.with_suffix(".blif")

        # Step 1: bench2blif (bundled Python implementation)
        from .bench2blif import convert as bench2blif
        bench2blif(bench, blif_path)

        # Step 2: Yosys – technology-independent synthesis → generic netlist
        synth_cmd = [
            "yosys", "-p",
            f"read_blif {blif_path}; "
            f"synth -top {name}; "
            f"write_verilog {def_out.with_suffix('.v')}"
        ]
        result = subprocess.run(synth_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log.error("Yosys failed for %s:\n%s", name, result.stderr[:500])
            return False

        # Step 3: Generate a stub DEF from the Verilog (OpenROAD not assumed here)
        from .def_stub_writer import write_stub_def
        write_stub_def(name, def_out.with_suffix(".v"), def_out, lef_out)
        return True

    except Exception as exc:
        log.error("ISCAS pipeline error for %s: %s", name, exc)
        return False
