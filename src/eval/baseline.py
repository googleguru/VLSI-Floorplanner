"""Baseline floorplan flow: OpenROAD ifp only, no CA optimization."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from src.data.benchmark_base import BenchmarkDesign
from src.floorplan.macro_abstraction import FloorplanState, MacroRegion, MacroAssigner
from src.floorplan.overlap_repair import OverlapRepairer
from src.floorplan.fixed_outline import FixedOutlineChecker
from src.ifp_engine.tcl_generator import IFPTclGenerator
from src.ifp_engine.openroad_wrapper import OpenROADRunner, IFPResult
from src.objectives.metrics import FloorplanMetrics, compute_metrics

log = logging.getLogger(__name__)


class BaselineFlow:
    """Runs initialize_floorplan with no CA guidance."""

    def __init__(
        self,
        runner: OpenROADRunner,
        output_dir: Path,
        track_layers: Optional[list] = None,
    ) -> None:
        self.runner      = runner
        self.output_dir  = Path(output_dir)
        self.track_layers = track_layers or []

    def run(self, design: BenchmarkDesign) -> tuple[FloorplanState, FloorplanMetrics]:
        t0 = time.perf_counter()

        # Build initial macro placement from design data
        core = self._core_area(design)
        macros = [
            MacroRegion(
                name=m.name, x=m.x, y=m.y, width=m.width, height=m.height, fixed=m.fixed
            )
            for m in design.macros
        ]

        # Overlap repair and outline legalization
        if macros:
            macros = OverlapRepairer(core).repair(macros)
            macros = FixedOutlineChecker(core).legalize(macros)

        fp = FloorplanState(design=design.name, macros=macros, core_area=core)

        # Generate and run OpenROAD Tcl
        tcl_path = self.output_dir / "tcl" / f"{design.name}_baseline.tcl"
        def_out  = self.output_dir / "floorplans" / f"{design.name}_baseline.def"

        gen = IFPTclGenerator(
            design      = design,
            output_def  = def_out,
            make_tracks = bool(self.track_layers),
            track_layers = self.track_layers,
        )
        gen.write(tcl_path)

        ifp_result: IFPResult = self.runner.run(tcl_path, design.name)

        elapsed = time.perf_counter() - t0
        metrics = compute_metrics(
            fp        = fp,
            method    = "baseline",
            nets      = design.nets,
            runtime_s = elapsed,
        )
        # Record whether OpenROAD was simulated (no binary found)
        metrics._simulated = getattr(ifp_result, "simulated", False)
        log.info("Baseline %-25s  HPWL=%.1f  overlap=%d  runtime=%.2fs",
                  design.name, metrics.hpwl_um, metrics.overlap_count, elapsed)

        return fp, metrics

    def _core_area(self, design: BenchmarkDesign):
        from src.data.benchmark_base import SizingMode
        if design.sizing_mode == SizingMode.DIE_CORE and design.core_area:
            return design.core_area
        # Utilization mode: estimate from die area
        if design.die_area:
            da = design.die_area
            margin = 5.0
            return (da[0]+margin, da[1]+margin, da[2]-margin, da[3]-margin)
        return (0, 0, 200, 200)
