"""Ablation study driver.

Ablation levels (in order of increasing CA complexity):
  0. baseline      – pure OpenROAD ifp, no CA
  1. density_only  – ifp + density equalization CA
  2. density_connectivity – ifp + density + connectivity CA
  3. full_ca       – ifp + complete 5-rule CA

Each level is run on all ready designs; results are collected and saved.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from src.data.benchmark_base import BenchmarkDesign
from src.eval.baseline import BaselineFlow
from src.eval.ca_flow import CAFlow
from src.ifp_engine.openroad_wrapper import OpenROADRunner
from src.objectives.metrics import FloorplanMetrics

log = logging.getLogger(__name__)

ABLATION_LEVELS = [
    "baseline",
    "density_only",
    "density_connectivity",
    "full_ca",
]


class AblationStudy:
    def __init__(
        self,
        rule_sets_cfg: dict,       # ca_rules.yaml → rule_sets
        rule_params:   dict,       # ca_rules.yaml → rule_params
        global_cfg:    dict,       # ca_rules.yaml → global
        runner:        OpenROADRunner,
        output_dir:    Path,
    ) -> None:
        self.rule_sets_cfg = rule_sets_cfg
        self.rule_params   = rule_params
        self.global_cfg    = global_cfg
        self.runner        = runner
        self.output_dir    = Path(output_dir)

    def run(
        self,
        designs: List[BenchmarkDesign],
        levels:  List[str] = ABLATION_LEVELS,
    ) -> Dict[str, List[FloorplanMetrics]]:
        """Run each ablation level on all designs. Return {level: [metrics]}."""
        results: Dict[str, List[FloorplanMetrics]] = {lvl: [] for lvl in levels}

        for design in designs:
            log.info("Ablation on design: %s", design.name)

            for level in levels:
                if level == "baseline":
                    flow = BaselineFlow(self.runner, self.output_dir)
                    _, metrics = flow.run(design)
                else:
                    rs_cfg = self.rule_sets_cfg.get(level, {})
                    if not rs_cfg.get("enabled", True):
                        log.info("  Skipping disabled rule-set: %s", level)
                        continue

                    flow = CAFlow(
                        runner         = self.runner,
                        output_dir     = self.output_dir,
                        rule_set_cfg   = rs_cfg,
                        rule_params    = self.rule_params,
                        grid_rows      = self.global_cfg.get("grid_resolution", 64),
                        grid_cols      = self.global_cfg.get("grid_resolution", 64),
                        neighborhood   = self.global_cfg.get("neighborhood", "moore"),
                        convergence_eps = self.global_cfg.get("convergence_eps", 1e-5),
                        seed           = self.global_cfg.get("seed", 42),
                    )
                    _, metrics, _ = flow.run(design, rule_set_name=level)

                results[level].append(metrics)
                log.info("  %-22s  HPWL=%.1f  overlap=%d",
                          level, metrics.hpwl_um, metrics.overlap_count)

        return results
