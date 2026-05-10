"""CA Rule Engine: applies one or more rules to a CAGrid for one generation."""
from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np

from .grid_model import CAGrid, N_CHAN, CH_BLK, CH_OCC, CellState
from .rule_library import RULE_REGISTRY
from .tie_breaking import deterministic_tiebreak

log = logging.getLogger(__name__)


class RuleEngine:
    """Applies weighted, simultaneous rule updates to a CAGrid."""

    def __init__(
        self,
        rule_names: List[str],
        weights: Dict[str, float],
        rule_params: Dict[str, dict],
        neighborhood: str = "moore",
    ) -> None:
        for name in rule_names:
            if name not in RULE_REGISTRY:
                raise ValueError(f"Unknown rule: {name!r}. "
                                 f"Available: {list(RULE_REGISTRY)}")
        self.rule_names  = rule_names
        self.weights     = weights
        self.rule_params = rule_params
        self.neighborhood = neighborhood

    def step(self, grid: CAGrid) -> CAGrid:
        """Apply one generation: compute all rule deltas, sum, apply, clamp."""
        new_grid = grid.clone()
        composite_delta = np.zeros((grid.rows, grid.cols, N_CHAN), dtype=np.float32)

        for name in self.rule_names:
            fn     = RULE_REGISTRY[name]
            params = self.rule_params.get(name, {})
            w      = self.weights.get(name, 1.0)
            try:
                delta = fn(grid.state, params, self.neighborhood)
                composite_delta += w * delta
            except Exception as exc:
                log.error("Rule %s raised an error: %s", name, exc)

        # Deterministic tie-breaking for equal deltas
        composite_delta = deterministic_tiebreak(composite_delta)

        # Apply and clamp
        new_state = grid.state + composite_delta
        # Hard clamps
        new_state[:, :, 1:] = np.clip(new_state[:, :, 1:], 0.0, 1.0)
        # Preserve blockage occupancy
        blk_mask = grid.state[:, :, CH_BLK] > 0.5
        new_state[blk_mask, CH_OCC] = CellState.BLOCKAGE

        new_grid.state = new_state
        return new_grid
