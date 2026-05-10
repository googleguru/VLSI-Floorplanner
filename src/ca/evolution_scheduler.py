"""Evolution scheduler: runs multi-phase CA evolution on a CAGrid.

Phases are defined in the CA rule config as a list of:
  { name, rules, generations }

The scheduler executes phases in order, switching rule sets between phases,
and supports early stopping when state delta < convergence_eps.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .grid_model import CAGrid
from .rule_engine import RuleEngine

log = logging.getLogger(__name__)


@dataclass
class PhaseRecord:
    name:        str
    generations: int
    rules:       List[str]
    converged:   bool = False
    runtime_s:   float = 0.0
    final_delta: float = 0.0


@dataclass
class EvolutionRecord:
    total_generations: int = 0
    total_runtime_s:   float = 0.0
    phases:            List[PhaseRecord] = field(default_factory=list)
    density_history:   List[float] = field(default_factory=list)


class EvolutionScheduler:
    """Orchestrates multi-phase CA evolution."""

    def __init__(
        self,
        phases: List[dict],           # from ca_rules.yaml rule_set.phases
        weights: Dict[str, float],
        rule_params: Dict[str, dict],
        neighborhood: str = "moore",
        convergence_eps: float = 1e-5,
        max_generations: Optional[int] = None,
    ) -> None:
        self.phases          = phases
        self.weights         = weights
        self.rule_params     = rule_params
        self.neighborhood    = neighborhood
        self.convergence_eps = float(convergence_eps)
        self.max_generations = max_generations

    def evolve(self, grid: CAGrid) -> tuple[CAGrid, EvolutionRecord]:
        """Run all phases sequentially; return final grid and evolution record."""
        record  = EvolutionRecord()
        current = grid
        total_gen = 0

        for phase_cfg in self.phases:
            pname      = phase_cfg.get("name", "unnamed")
            rule_names = phase_cfg.get("rules", [])
            max_gen    = phase_cfg.get("generations", 20)

            if self.max_generations and total_gen >= self.max_generations:
                log.info("Phase %s skipped: global max_generations reached.", pname)
                break

            engine = RuleEngine(
                rule_names  = rule_names,
                weights     = self.weights,
                rule_params = self.rule_params,
                neighborhood = self.neighborhood,
            )

            phase_rec = PhaseRecord(name=pname, generations=0, rules=rule_names)
            t0 = time.perf_counter()
            prev = current.clone()   # snapshot for final_delta computation

            for g in range(max_gen):
                if self.max_generations and total_gen >= self.max_generations:
                    break

                next_grid = engine.step(current)
                delta     = current.state_delta(next_grid)
                record.density_history.append(float(current.density().mean()))

                current    = next_grid
                total_gen += 1
                phase_rec.generations += 1

                if delta < self.convergence_eps:
                    phase_rec.converged = True
                    log.debug("Phase %s converged at gen %d (delta=%.2e)",
                              pname, total_gen, delta)
                    break

            phase_rec.runtime_s   = time.perf_counter() - t0
            phase_rec.final_delta = float(current.state_delta(prev))
            record.phases.append(phase_rec)

            log.info("Phase %-12s  gen=%-4d  converged=%-5s  %.3fs",
                     pname, phase_rec.generations, phase_rec.converged, phase_rec.runtime_s)

        record.total_generations = total_gen
        record.total_runtime_s   = sum(p.runtime_s for p in record.phases)
        return current, record
