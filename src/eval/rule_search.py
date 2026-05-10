"""Rule-search utility: sweep CA hyper-parameters and select best per family.

Sweeps the search space defined in ca_rules.yaml → rule_search and selects
the rule-set configuration that minimises the target metric.

Results are saved as a CSV and the best configuration is logged.
"""
from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.data.benchmark_base import BenchmarkDesign
from src.eval.ca_flow import CAFlow
from src.ifp_engine.openroad_wrapper import OpenROADRunner
from src.objectives.metrics import FloorplanMetrics

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    alpha:       float
    beta:        float
    gamma:       float
    neighborhood: str
    generations: int
    metric_val:  float
    metrics:     FloorplanMetrics


class RuleSearcher:
    def __init__(
        self,
        search_cfg:  dict,
        rule_params: dict,
        global_cfg:  dict,
        runner:      OpenROADRunner,
        output_dir:  Path,
    ) -> None:
        self.search_cfg  = search_cfg
        self.rule_params = rule_params
        self.global_cfg  = global_cfg
        self.runner      = runner
        self.output_dir  = Path(output_dir)

    def search(self, designs: List[BenchmarkDesign]) -> Dict[str, SearchResult]:
        """Run parameter grid search; return {design_name: best_result}."""
        metric_key = self.search_cfg.get("metric", "hpwl")
        alphas     = self.search_cfg.get("alpha_values", [0.25])
        betas      = self.search_cfg.get("beta_values",  [0.30])
        gammas     = self.search_cfg.get("gamma_values", [0.40])
        neighs     = self.search_cfg.get("neighborhood", ["moore"])
        gen_list   = self.search_cfg.get("generations",  [200])

        all_results: List[dict] = []
        best_per_design: Dict[str, SearchResult] = {}

        for design in designs:
            design_best: Optional[SearchResult] = None
            log.info("Rule search on %s  (metric=%s)", design.name, metric_key)

            for alpha, beta, gamma, nbr, gens in itertools.product(
                alphas, betas, gammas, neighs, gen_list
            ):
                params = dict(self.rule_params)
                params["density_equalization"]   = dict(params.get("density_equalization", {}), alpha=alpha)
                params["connectivity_attraction"] = dict(params.get("connectivity_attraction", {}), beta=beta)
                params["repulsion_separation"]    = dict(params.get("repulsion_separation", {}), gamma=gamma)

                rs_cfg = _build_full_ca_rs_cfg()

                flow = CAFlow(
                    runner         = self.runner,
                    output_dir     = self.output_dir,
                    rule_set_cfg   = rs_cfg,
                    rule_params    = params,
                    grid_rows      = self.global_cfg.get("grid_resolution", 64),
                    grid_cols      = self.global_cfg.get("grid_resolution", 64),
                    neighborhood   = nbr,
                    convergence_eps = self.global_cfg.get("convergence_eps", 1e-5),
                    seed           = self.global_cfg.get("seed", 42),
                )
                _, metrics, _ = flow.run(design, rule_set_name=f"search_a{alpha}_b{beta}_g{gamma}")

                val = _get_metric(metrics, metric_key)
                sr = SearchResult(alpha, beta, gamma, nbr, gens, val, metrics)
                all_results.append({
                    "design": design.name,
                    "alpha": alpha, "beta": beta, "gamma": gamma,
                    "neighborhood": nbr, "generations": gens,
                    metric_key: val,
                })

                if design_best is None or val < design_best.metric_val:
                    design_best = sr

            if design_best:
                best_per_design[design.name] = design_best
                log.info("  Best  alpha=%.2f beta=%.2f gamma=%.2f nbr=%s  %s=%.2f",
                          design_best.alpha, design_best.beta, design_best.gamma,
                          design_best.neighborhood, metric_key, design_best.metric_val)

        # Save sweep results
        if all_results:
            df = pd.DataFrame(all_results)
            out = self.output_dir / "tables" / "rule_search.csv"
            out.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out, index=False)
            log.info("Rule search results saved to %s", out)

        return best_per_design


def _get_metric(m: FloorplanMetrics, key: str) -> float:
    mapping = {
        "hpwl":             m.hpwl_um,
        "density_variance": m.density_variance,
        "overlap_area":     m.overlap_area_um2,
        "whitespace_frag":  m.whitespace_frag,
    }
    return mapping.get(key, m.hpwl_um)


def _build_full_ca_rs_cfg() -> dict:
    return {
        "enabled": True,
        "phases": [
            {"name": "seed",     "rules": ["density_equalization"],                              "generations": 20},
            {"name": "compact",  "rules": ["density_equalization", "connectivity_attraction"],   "generations": 40},
            {"name": "separate", "rules": ["repulsion_separation"],                              "generations": 30},
            {"name": "cluster",  "rules": ["connectivity_attraction"],                           "generations": 30},
            {"name": "legalize", "rules": ["boundary_regularization"],                           "generations": 20},
            {"name": "smooth",   "rules": ["whitespace_smoothing"],                              "generations": 20},
        ],
        "weights": {
            "density_equalization":     1.0,
            "connectivity_attraction":  1.2,
            "repulsion_separation":     1.5,
            "boundary_regularization":  0.8,
            "whitespace_smoothing":     0.6,
        },
    }
