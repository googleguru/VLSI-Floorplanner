"""CA-enhanced floorplan flow: CA optimization → OpenROAD ifp."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from src.data.benchmark_base import BenchmarkDesign
from src.ca.grid_model import CAGrid
from src.ca.evolution_scheduler import EvolutionScheduler
from src.floorplan.macro_abstraction import FloorplanState, MacroRegion, MacroAssigner
from src.floorplan.overlap_repair import OverlapRepairer
from src.floorplan.fixed_outline import FixedOutlineChecker
from src.ifp_engine.tcl_generator import IFPTclGenerator
from src.ifp_engine.openroad_wrapper import OpenROADRunner, IFPResult
from src.objectives.metrics import FloorplanMetrics, compute_metrics

log = logging.getLogger(__name__)


class CAFlow:
    """CA-guided floorplanning flow."""

    def __init__(
        self,
        runner:          OpenROADRunner,
        output_dir:      Path,
        rule_set_cfg:    dict,            # one entry from ca_rules.yaml rule_sets
        rule_params:     dict,            # from ca_rules.yaml rule_params
        grid_rows:       int = 64,
        grid_cols:       int = 64,
        neighborhood:    str = "moore",
        convergence_eps: float = 1e-5,
        seed:            int = 42,
        track_layers:    Optional[list] = None,
    ) -> None:
        self.runner          = runner
        self.output_dir      = Path(output_dir)
        self.rule_set_cfg    = rule_set_cfg
        self.rule_params     = rule_params
        self.grid_rows       = grid_rows
        self.grid_cols       = grid_cols
        self.neighborhood    = neighborhood
        self.convergence_eps = convergence_eps
        self.seed            = seed
        self.track_layers    = track_layers or []

    def run(
        self,
        design:      BenchmarkDesign,
        rule_set_name: str = "full_ca",
    ) -> Tuple[FloorplanState, FloorplanMetrics, object]:
        t0 = time.perf_counter()

        core = self._core_area(design)

        # Build CA grid
        grid = CAGrid(
            rows=self.grid_rows, cols=self.grid_cols,
            core_area=core, seed=self.seed,
        )

        # Seed macros onto grid
        for m in design.macros:
            r, c = grid.phy_to_grid(m.x + m.width / 2, m.y + m.height / 2)
            w_cells = max(1, int(m.width  / grid.cell_w))
            h_cells = max(1, int(m.height / grid.cell_h))
            grid.place_macro(r - h_cells // 2, c - w_cells // 2, w_cells, h_cells)

        # Seed density
        total_stdcell_area = design.num_stdcells * 0.19 * 1.4  # unit cell approx
        grid.seed_density(total_stdcell_area, stdcell_density=0.5)

        # Build net pressure map
        if design.nets:
            net_pressure = self._build_net_pressure(design, grid, core)
            grid.set_net_pressure(net_pressure)

        # Run CA evolution
        phases     = self.rule_set_cfg.get("phases", [])
        weights    = self.rule_set_cfg.get("weights", {})
        scheduler  = EvolutionScheduler(
            phases          = phases,
            weights         = weights,
            rule_params     = self.rule_params,
            neighborhood    = self.neighborhood,
            convergence_eps = self.convergence_eps,
        )
        evolved_grid, evo_record = scheduler.evolve(grid)

        # Extract macro regions from evolved grid
        assigner = MacroAssigner(affinity_threshold=0.3)
        macros = assigner.assign(evolved_grid, design.macros, core)

        # Overlap repair + legalization
        macros = OverlapRepairer(core).repair(macros)
        macros = FixedOutlineChecker(core).legalize(macros)

        fp = FloorplanState(design=design.name, macros=macros, core_area=core)

        # Generate and run OpenROAD Tcl
        suffix   = rule_set_name.replace(" ", "_")
        tcl_path = self.output_dir / "tcl" / f"{design.name}_{suffix}.tcl"
        def_out  = self.output_dir / "floorplans" / f"{design.name}_{suffix}.def"

        gen = IFPTclGenerator(
            design       = design,
            output_def   = def_out,
            make_tracks  = bool(self.track_layers),
            track_layers = self.track_layers,
        )
        gen.write(tcl_path)

        ifp_result = self.runner.run(tcl_path, design.name)

        elapsed = time.perf_counter() - t0
        metrics = compute_metrics(
            fp        = fp,
            method    = rule_set_name,
            nets      = design.nets,
            runtime_s = elapsed,
        )
        metrics._simulated = getattr(ifp_result, "simulated", False)

        log.info("CA %-10s %-20s  HPWL=%.1f  overlap=%d  frag=%.3f  %.2fs",
                  rule_set_name, design.name,
                  metrics.hpwl_um, metrics.overlap_count,
                  metrics.whitespace_frag, elapsed)

        return fp, metrics, evo_record

    # ── helpers ───────────────────────────────────────────────────────────────

    def _core_area(self, design: BenchmarkDesign):
        from src.data.benchmark_base import SizingMode
        if design.sizing_mode == SizingMode.DIE_CORE and design.core_area:
            return design.core_area
        if design.die_area:
            da = design.die_area
            margin = 5.0
            return (da[0]+margin, da[1]+margin, da[2]-margin, da[3]-margin)
        return (0, 0, 200, 200)

    def _build_net_pressure(self, design, grid, core) -> np.ndarray:
        """Estimate per-cell net connectivity pressure from net bounding boxes."""
        rows, cols = grid.rows, grid.cols
        pressure = np.zeros((rows, cols), dtype=np.float32)
        macro_map = {m.name: m for m in design.macros}

        for net in design.nets:
            cells = []
            for pin in net.pins:
                cell_name = pin.split("/")[0]
                m = macro_map.get(cell_name)
                if m:
                    r, c = grid.phy_to_grid(m.x + m.width / 2,
                                             m.y + m.height / 2)
                    cells.append((r, c))
            if len(cells) >= 2:
                rs = [c[0] for c in cells]
                cs = [c[1] for c in cells]
                for r in range(min(rs), max(rs) + 1):
                    for c in range(min(cs), max(cs) + 1):
                        pressure[r, c] += 1.0

        max_p = pressure.max()
        if max_p > 0:
            pressure /= max_p
        return pressure
